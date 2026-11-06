#!/usr/bin/env python3
"""PORT-25 T3: Opt-in Combined Breadcrumb Ladder + G3X_POWERON_FIX Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic candidate DISKBOOT.BIN combining:
1. G3X_POWERON_FIX=1: Bypasses the Stage 5 power-cut in sub_fc05b962_my.
2. LED_LADDER=1: Count-coded LED pulse ladder extended past loader into boot_prototype.c stages.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
- PORT-24 --poweron-fix build remains byte-identical:
  DISKBOOT.BIN SHA-256: faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056 (118,001 B).
- Reuses verified green LED MMIO register 0xD20B0884 (ON: 0x004D0002, OFF: 0x004C0003). Adds no new addresses.
- All pulses use calibrated framed timing with preemption tolerance (>= 50 ms difference at slow bound):
  ON delay: 0x00100000 (1,048,576 iterations) -> 50.0 ms (slow <= 150 ms) / 20.97 ms (nom) / 15.73 ms (fast)
  Pulse OFF gap: 0x00050000 (327,680 iterations) -> 15.625 ms (slow) / 6.55 ms (nom) / 4.91 ms (fast)
  Inter-digit gap: 0x00200000 (2,097,152 iterations) -> 100.0 ms (slow) / 41.94 ms (nom) / 31.46 ms (fast)
  Frame-end gap: 0x00400000 (4,194,304 iterations) -> 200.0 ms (slow) / 83.89 ms (nom) / 62.91 ms (fast)
- Final state is LED OFF (0x004C0003) after each frame and before firmware continuation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
LOADER_DIR = CHDK_PORT / "loader" / "g3x"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import (  # noqa: E402
    CC,
    AR,
    OBJCOPY,
    NM,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_loader as build_default_loader,
    encode_candidate_diskboot,
    generate_candidate_inspector,
    generate_manifest,
    extract_symbol_addr_from_nm,
    sha256_file,
    run_cmd,
)

CANDIDATE_PORT25_LADDER_FIX_DIR = os.path.join(REPO_ROOT, "candidate_port25_ladder_fix")
CANDIDATE_PORT25_LADDER_DIR = os.path.join(REPO_ROOT, "candidate_port25_ladder")
CANDIDATE_PORT25_POWERON_DIR = os.path.join(REPO_ROOT, "candidate_port25_poweron_fix")
CANDIDATE_PORT25_DEFAULT_DIR = os.path.join(REPO_ROOT, "candidate_port25_default")
CANDIDATE_PORT32_RESIDENT_DIR = os.path.join(REPO_ROOT, "candidate_port32_resident")

# Backward compatibility alias
CANDIDATE_LADDER_FIX_DIR = CANDIDATE_PORT25_LADDER_FIX_DIR

G3X_RESIDENT_HEAP_START = 0x00368680
G3X_RESIDENT_CREATETASK_ADDR = 0xBFE14A3D
G3X_RESIDENT_HANDOFF_ADDR = 0xFC0D0126
G3X_RESIDENT_SLEEPTASK_VENEER = 0xFC31BF84
G3X_RESIDENT_SLEEPTASK_ADDR = 0xFCEF33B4
G3X_RESIDENT_STACK_SIZE = 0x2000
G3X_RESIDENT_PRIORITY = 0x19

LADDER_ENTRY_S = str(SUB_DIR / "loader_entry_breadcrumb.S")
LADDER_LOADER_C = str(SUB_DIR / "loader_main_breadcrumb.c")

G3X_LED_MMIO_ADDR = 0xD20B0884
G3X_LED_ON_VAL = 0x004D0002
G3X_LED_OFF_VAL = 0x004C0003

def generate_boot_prototype_ladder_c() -> str:
    sub_dir = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
    with open(sub_dir / "boot_prototype.c", "r", encoding="utf-8") as f:
        src = f.read()

    target_pwr = (
        '#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX /* PORT-24 opt-in short-press power-on fix */\n'
        '        "    bl      sub_fc1284ac\\n" "    movs    r0, #1\\n" "    b       loc_fc05b978\\n" "    nop\\n"\n'
        '#else\n'
        '        // Native Canon power-on button check (unmodified stock ROM handler)\n'
        '        "    bl      sub_fc1284ac\\n"\n'
        '        "    cbnz    r0, loc_fc05b978\\n"\n'
        '        "    bl      sub_fc05ba56\\n"\n'
        '#endif\n'
        '        "loc_fc05b976:\\n"\n'
        '        "    b       loc_fc05b976\\n"          // Safe halt if shutdown requested\n'
        '        "loc_fc05b978:\\n"'
    )

    repl_pwr = (
        '#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX /* PORT-24 opt-in short-press power-on fix */\n'
        '        "    bl      sub_fc1284ac\\n" "    movs    r0, #1\\n" "    b       loc_fc05b978\\n" "    nop\\n"\n'
        '#else\n'
        '        // Native Canon power-on button check (unmodified stock ROM handler)\n'
        '        "    bl      sub_fc1284ac\\n"\n'
        '        "    cbz     r0, 1f\\n"\n'
        '        "    b.w     loc_fc05b978\\n"\n'
        '        "1:\\n"\n'
        '        CORE_LADDER_PULSE_28 "    bl      sub_fc05ba56\\n"\n'
        '        "loc_fc05b976:\\n" CORE_LADDER_PULSE_29\n'
        '        "    b       loc_fc05b976\\n"\n'
        '#endif\n'
        '        "loc_fc05b978:\\n" CORE_LADDER_PULSE_25'
    )

    replacements = [
        ("#include \"boot_witness.h\"\n", "#include \"boot_witness.h\"\n#include \"led_breadcrumb.h\"\n"),
        ("\"    mov     sp, r0\\n\"", "\"    mov     sp, r0\\n\" CORE_LADDER_PULSE_11"),
        ("\"    blo     loc_zero_bss\\n\"", "\"    blo     loc_zero_bss\\n\" CORE_LADDER_PULSE_12"),
        ("\"    bl      witness_record_core\\n\"", "\"    bl      witness_record_core\\n\" CORE_LADDER_PULSE_13"),
        ("\"    mov     r0, sp\\n\"\n        \"    blx     sub_fc31b408\\n\"", "CORE_LADDER_PULSE_14 \"    mov     r0, sp\\n\"\n        \"    blx     sub_fc31b408\\n\""),
        ("sub_fc05b558_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"", "sub_fc05b558_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\" CORE_LADDER_PULSE_15"),
        ("sub_fc05b962_my(void)\n{\n    asm volatile (\n        \"    push    {r3, lr}\\n\"", "sub_fc05b962_my(void)\n{\n    asm volatile (\n        \"    push    {r3, lr}\\n\" CORE_LADDER_PULSE_21"),
        ("\"    bl      sub_fc05ba68\\n\"", "CORE_LADDER_PULSE_22 \"    bl      sub_fc05ba68\\n\" CORE_LADDER_PULSE_23"),
        ("\"    bl      sub_fc079404\\n\"", "\"    bl      sub_fc079404\\n\" CORE_LADDER_PULSE_24"),
        (target_pwr, repl_pwr),
        ("\"    ldr     r0, =0xfc05b9a0\\n\"", "\"    ldr     r0, =0xfc05b9a0\\n\"\n        CORE_LADDER_PULSE_26"),
        ("task_Startup_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"", "task_Startup_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"\n        CORE_LADDER_PULSE_31"),
        ("\"    bl      sub_fc418eec\\n\"", "\"    bl      sub_fc418eec\\n\" CORE_LADDER_PULSE_32"),
        ("\"    movs    r0, #0\\n\"\n        \"    bl      sub_fc05c4e0\\n\"", "CORE_LADDER_PULSE_33 \"    movs    r0, #0\\n\"\n        \"    bl      sub_fc05c4e0\\n\""),
        ("\"    blx     sub_fc31b1f4\\n\"\n        \"1:\\n\"", "\"    blx     sub_fc31b1f4\\n\"\n        \"1:\\n\" CORE_LADDER_PULSE_34"),
        ("\"    bl      sub_fc418f2a\\n\"", "CORE_LADDER_PULSE_35 \"    bl      sub_fc418f2a\\n\" CORE_LADDER_PULSE_41"),
        ("\"    bl      sub_fc1283d2\\n\"", "CORE_LADDER_PULSE_42 \"    bl      sub_fc1283d2\\n\" CORE_LADDER_PULSE_43"),
        ("\"    pop.w   {r4, lr}\\n\"\n        \"    b.w     sub_fc0d0126\\n\"", "CORE_LADDER_PULSE_44 \"    pop.w   {r4, lr}\\n\"\n        \"    b.w     sub_fc0d0126\\n\""),
    ]
    for target, repl in replacements:
        if target not in src:
            raise ValueError(f"Target pattern not found in boot_prototype.c: {target!r}")
        src = src.replace(target, repl, 1)
    return src


BOOT_PROTOTYPE_LADDER_C = generate_boot_prototype_ladder_c()


def generate_boot_prototype_resident_c() -> str:
    """Generate boot_prototype C source with opt-in G3X_RESIDENT=1 blocks."""
    src = generate_boot_prototype_ladder_c()

    target_new_sa = "const char * const new_sa = &_end;\n"
    repl_new_sa = (
        "#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "/* Raised heap start 0x00368680 [docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-HEAP-SETUP] */\n"
        "const char * const new_sa = (const char *)G3X_RESIDENT_HEAP_START;\n"
        "#else\n"
        "const char * const new_sa = &_end;\n"
        "#endif\n"
    )

    target_heap_ldr = (
        "        // Load shifted heap base from new_sa (&_end)\n"
        '        "    ldr     r4, =new_sa\\n"\n'
        '        "    ldr     r4, [r4]\\n"'
    )
    repl_heap_ldr = (
        "#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "        /* Load raised heap base 0x00368680 [docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-HEAP-SETUP] */\n"
        '        "    ldr     r4, =0x00368680\\n"\n'
        "#else\n"
        "        // Load shifted heap base from new_sa (&_end)\n"
        '        "    ldr     r4, =new_sa\\n"\n'
        '        "    ldr     r4, [r4]\\n"\n'
        "#endif"
    )

    target_handoff = (
        'CORE_LADDER_PULSE_44 "    pop.w   {r4, lr}\\n"\n'
        '        "    b.w     sub_fc0d0126\\n"'
    )
    repl_handoff = (
        "CORE_LADDER_PULSE_44\n"
        "#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "        /* Spawn resident heartbeat task via CreateTask at 0xBFE14A3D after ladder\n"
        "         * completes and at the sub_fc0d0126 (0xFC0D0126) handoff point\n"
        "         * [reference/finsig_gm110c/stubs_entry.S:200;\n"
        "         *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-CREATETASK-VENEER;\n"
        "         *  evidence/port31_manifest.json: PORT29-ROM-CREATETASK;\n"
        "         *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-FIRMWARE-CONT] */\n"
        "        G3X_SPAWN_RESIDENT_HEARTBEAT\n"
        "#endif\n"
        '        "    pop.w   {r4, lr}\\n"\n'
        '        "    b.w     sub_fc0d0126\\n"'
    )

    resident_replacements = [
        (target_new_sa, repl_new_sa),
        (target_heap_ldr, repl_heap_ldr),
        (target_handoff, repl_handoff),
    ]
    for target, repl in resident_replacements:
        if target not in src:
            raise ValueError(f"Resident target pattern not found in ladder source: {target!r}")
        src = src.replace(target, repl, 1)

    resident_task_block = """
#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)
/* =============================================================================
 * PORT-32 Resident Heartbeat Task (G3X_RESIDENT=1)
 * Blinks rear green LED (0xD20B0884, ON 0x004D0002, OFF 0x004C0003) at ~1 Hz
 * in a double-short-blink pattern (100 ms ON, 100 ms OFF, 100 ms ON, 700 ms OFF)
 * using manifest-cited SleepTask (0xFC31BF84 / 0xFCEF33B4; delay unit ms INFERRED).
 * Stack alignment at task entry is INFERRED (no inline sp write in C task body).
 * Manifest citations:
 * - docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json: PORT25-ROM-GPIO-WRITE-MMIO
 * - docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-SLEEPTASK-VENEER
 * - evidence/port31_manifest.json: PORT30-ROM-SLEEPTASK, PORT31-ROM-SLEEPTASK-BODY
 * ============================================================================= */
void __attribute__((noinline)) g3x_resident_heartbeat_task(void)
{
    for (;;) {
        g3x_resident_led_write(G3X_LADDER_ON_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
        g3x_resident_led_write(G3X_LADDER_OFF_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_GAP_MS);
        g3x_resident_led_write(G3X_LADDER_ON_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
        g3x_resident_led_write(G3X_LADDER_OFF_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_PAUSE_MS);
    }
}
#endif
"""
    return src + resident_task_block


BOOT_PROTOTYPE_RESIDENT_C = generate_boot_prototype_resident_c()



def ensure_bootstrap():
    """Ensure platform bootstrap has populated platform headers if missing."""
    platform_cam_h = CHDK_PORT / "platform" / "g3x" / "platform_camera.h"
    if not platform_cam_h.is_file():
        bootstrap_script = TOOLS_DIR / "bootstrap_chdk_platform.py"
        run_cmd(["python3", "-B", str(bootstrap_script)], cwd=str(REPO_ROOT))


def build_candidate_core_ladder_fix(
    ladder: bool = True,
    poweron_fix: bool = True,
    candidate_dir: str = CANDIDATE_LADDER_FIX_DIR,
    resident: bool = False,
) -> tuple[str, str, int, int]:
    """Compile candidate core with optional LED_LADDER, G3X_POWERON_FIX, and G3X_RESIDENT defines."""
    print(
        f"--- Building Candidate Core (ladder={ladder}, poweron_fix={poweron_fix}, resident={resident}) (@ 0x003489B4) ---"
    )
    os.makedirs(candidate_dir, exist_ok=True)

    if resident:
        boot_proto_c = os.path.join(candidate_dir, "boot_prototype_resident.c")
        with open(boot_proto_c, "w", encoding="utf-8") as f:
            f.write(BOOT_PROTOTYPE_RESIDENT_C)
    elif ladder:
        boot_proto_c = os.path.join(candidate_dir, "boot_prototype_ladder.c")
        with open(boot_proto_c, "w", encoding="utf-8") as f:
            f.write(BOOT_PROTOTYPE_LADDER_C)
    else:
        boot_proto_c = str(SUB_DIR / "boot_prototype.c")
    stubs_proto_s = str(SUB_DIR / "stubs_prototype.S")
    boot_proto_o = os.path.join(candidate_dir, "boot_prototype.o")
    stubs_proto_o = os.path.join(candidate_dir, "stubs_prototype.o")
    lib_proto_a = os.path.join(candidate_dir, "libplatformsub_candidate.a")
    core_elf = os.path.join(candidate_dir, "candidate_main.elf")
    core_bin = os.path.join(candidate_dir, "candidate_main.bin")

    # 1. Compile boot_prototype.c
    cflags = [
        CC,
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Imodules",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-DMEMISOSIZE=(&_end-&_start)",
        "-DCAM_DIGIC=60",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_ARAM_MALLOC",
        "-DARAM_HEAP_START=0x006ce000",
        "-DARAM_HEAP_SIZE=0x00022000",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-nostdinc",
    ]
    if poweron_fix:
        cflags.append("-DG3X_POWERON_FIX=1")
    if ladder:
        cflags.append("-DLED_LADDER=1")
    if resident:
        cflags.append("-DG3X_RESIDENT=1")
    cflags.extend(["-c", "-o", boot_proto_o, boot_proto_c])
    run_cmd(cflags, cwd=str(CHDK_PORT))

    # 2. Compile stubs_prototype.S
    sflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-c",
        "-o",
        stubs_proto_o,
        stubs_proto_s,
    ]
    run_cmd(sflags, cwd=str(CHDK_PORT))

    # 3. Create candidate libplatformsub archive
    if os.path.exists(lib_proto_a):
        os.remove(lib_proto_a)
    obj_files = [
        boot_proto_o,
        stubs_proto_o,
        str(SUB_DIR / "stubs_min.o"),
        str(SUB_DIR / "stubs_entry.o"),
        str(SUB_DIR / "stubs_entry_2.o"),
        str(SUB_DIR / "capt_seq.o"),
        str(SUB_DIR / "movie_rec.o"),
        str(SUB_DIR / "filewrite.o"),
        str(SUB_DIR / "main.thm.o"),
        str(SUB_DIR / "gui_draw.thm.o"),
        str(SUB_DIR / "memmgmt.thm.o"),
        str(SUB_DIR / "gui.thm.o"),
        str(SUB_DIR / "kbd_process.thm.o"),
        str(SUB_DIR / "kbd_common.thm.o"),
        str(SUB_DIR / "conf.thm.o"),
        str(SUB_DIR / "gui_osd.thm.o"),
        str(SUB_DIR / "raw.thm.o"),
        str(SUB_DIR / "usb_sync.thm.o"),
        str(SUB_DIR / "shooting.thm.o"),
        str(SUB_DIR / "camera_info.thm.o"),
        str(SUB_DIR / "remotecap.thm.o"),
        str(SUB_DIR / "lib_thumb.thm.o"),
        str(SUB_DIR / "lang_str.thm.o"),
        str(SUB_DIR / "ptp.thm.o"),
    ]
    run_cmd([AR, "cr", lib_proto_a] + obj_files, cwd=str(CHDK_PORT))

    # 4. Link candidate_main.elf
    ld_script = "tools/link-boot.ld"
    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        f"-Wl,-T,{ld_script}",
        "-Wl,-N,-Ttext,0x3489b4",
        "-o",
        core_elf,
        "-Wl,--start-group",
        str(SUB_DIR / "entry.o"),
        str(CHDK_PORT / "platform" / "g3x" / "libplatform.a"),
        lib_proto_a,
        str(CHDK_PORT / "lib" / "font" / ".o2" / "libfont.a"),
        str(CHDK_PORT / "lib" / "math" / ".o2" / "libmath.a"),
        str(CHDK_PORT / "lib" / "lang" / ".o2" / "liblang.a"),
        str(CHDK_PORT / "lib" / "armutil" / ".o2" / "libarmutil.a"),
        str(CHDK_PORT / "lib" / "core" / ".o2" / "libcore.a"),
        "-lgcc",
        "-Wl,--end-group",
    ]
    run_cmd(ld_cmd, cwd=str(CHDK_PORT))

    # 5. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", core_elf, core_bin], cwd=str(CHDK_PORT))
    core_bin_size = os.path.getsize(core_bin)
    print(f"  [OK] candidate_main.bin generated ({core_bin_size} B)")

    # 6. Extract witness and end symbols
    proc = subprocess.run([NM, "-n", core_elf], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    witness_addr = extract_symbol_addr_from_nm(proc.stdout, "boot_witness")
    core_end_addr = extract_symbol_addr_from_nm(proc.stdout, "_end")
    if resident and core_end_addr > G3X_RESIDENT_HEAP_START:
        raise ValueError(
            f"Linked _end (0x{core_end_addr:08X}) overlaps resident heap start (0x{G3X_RESIDENT_HEAP_START:08X})"
        )
    print(f"  [OK] boot_witness discovered at 0x{witness_addr:08X}, _end at 0x{core_end_addr:08X}")

    return core_elf, core_bin, witness_addr, core_end_addr


def build_candidate_loader_ladder_fix(
    core_elf: str,
    core_bin: str,
    witness_addr: int,
    ladder: bool = True,
    candidate_dir: str = CANDIDATE_LADDER_FIX_DIR,
) -> tuple[str, str]:
    """Build candidate loader with optional LED_LADDER define."""
    print(f"--- Building Candidate Loader (ladder={ladder}) (@ 0x00008000) ---")
    os.makedirs(candidate_dir, exist_ok=True)

    loader_elf = os.path.join(candidate_dir, "candidate_loader.elf")
    loader_bin = os.path.join(candidate_dir, "candidate_loader.bin")

    if not ladder:
        # Default loader path
        l_elf, l_bin, _, _ = build_default_loader(core_elf, core_bin, candidate_dir=candidate_dir)
        return l_elf, l_bin

    # Ladder loader path
    loader_entry_s = LADDER_ENTRY_S
    if not os.path.isfile(loader_entry_s):
        raise FileNotFoundError(f"Missing loader entry source: {loader_entry_s}")
    loader_entry_o = os.path.join(candidate_dir, "entry_ladder.o")

    run_cmd([
        CC, "-march=armv7-r", "-mthumb", "-DTHUMB_FW", "-nostdinc",
        "-c", "-o", loader_entry_o, loader_entry_s
    ], cwd=str(LOADER_DIR))

    loader_c = LADDER_LOADER_C
    if not os.path.isfile(loader_c):
        raise FileNotFoundError(f"Missing loader C source: {loader_c}")

    blobs_s = os.path.join(str(LOADER_DIR), "blobs.S")
    loader_o = os.path.join(candidate_dir, "main_ladder.o")
    blobs_o = os.path.join(candidate_dir, "blobs_candidate.o")

    cflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-I../../include",
        "-I../../core",
        "-I../../modules",
        "-I../../platform/g3x",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-I.",
        "-I../../platform/g3x/sub/110c",
        f'-DCORE_FILE="{core_bin}"',
        f"-DBOOT_WITNESS_ADDR=0x{witness_addr:08x}",
        "-DLED_LADDER=1",
        "-nostdinc",
        "-c",
        "-o",
        loader_o,
        loader_c,
    ]
    run_cmd(cflags, cwd=str(LOADER_DIR))

    run_cmd([
        CC, "-march=armv7-r", "-mthumb", "-DTHUMB_FW", "-nostdinc",
        f'-DCORE_FILE="{core_bin}"', "-c", "-o", blobs_o, blobs_s
    ], cwd=str(LOADER_DIR))

    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        "-Wl,--no-define-common,-EL,-T,../../tools/link-boot.ld",
        "-Wl,-N,-Ttext,0x8000",
        "-o",
        loader_elf,
        loader_entry_o,
        loader_o,
        blobs_o,
    ]
    run_cmd(ld_cmd, cwd=str(LOADER_DIR))
    run_cmd([OBJCOPY, "-O", "binary", loader_elf, loader_bin], cwd=str(LOADER_DIR))
    print(f"  [OK] candidate_loader.bin generated ({os.path.getsize(loader_bin)} B)")

    return loader_elf, loader_bin


def _check_not_tracked_dir(candidate_dir: str) -> None:
    """Refuse to write build outputs into tracked repository directories."""
    abs_dir = Path(candidate_dir).resolve()
    forbidden_roots = [
        (REPO_ROOT / "chdk-port").resolve(),
        (REPO_ROOT / "docs").resolve(),
        (REPO_ROOT / "tools").resolve(),
        (REPO_ROOT / "tests").resolve(),
        (REPO_ROOT / "evidence").resolve(),
        (REPO_ROOT / "firmware").resolve(),
    ]
    if abs_dir == REPO_ROOT.resolve():
        raise ValueError(f"Refusing to emit candidate outputs directly into repository root: {candidate_dir}")
    for root in forbidden_roots:
        if abs_dir == root or root in abs_dir.parents:
            raise ValueError(f"Refusing to emit candidate outputs into tracked path: {candidate_dir}")


def build_candidate(
    ladder: bool = True,
    poweron_fix: bool = True,
    out_dir: str | None = None,
    resident: bool | None = None,
) -> dict:
    """Execute complete combined candidate build pipeline."""
    ensure_bootstrap()

    if resident is None:
        resident = os.environ.get("G3X_RESIDENT", "0") == "1"

    if out_dir:
        candidate_dir = os.path.abspath(out_dir)
    elif resident:
        candidate_dir = CANDIDATE_PORT32_RESIDENT_DIR
    elif ladder and poweron_fix:
        candidate_dir = CANDIDATE_PORT25_LADDER_FIX_DIR
    elif ladder:
        candidate_dir = CANDIDATE_PORT25_LADDER_DIR
    elif poweron_fix:
        candidate_dir = CANDIDATE_PORT25_POWERON_DIR
    else:
        candidate_dir = CANDIDATE_PORT25_DEFAULT_DIR

    _check_not_tracked_dir(candidate_dir)
    os.makedirs(candidate_dir, exist_ok=True)

    # 1. Build core
    core_elf, core_bin, witness_addr, core_end_addr = build_candidate_core_ladder_fix(
        ladder=ladder,
        poweron_fix=poweron_fix,
        candidate_dir=candidate_dir,
        resident=resident,
    )

    # 2. Build loader
    loader_elf, loader_bin = build_candidate_loader_ladder_fix(
        core_elf=core_elf,
        core_bin=core_bin,
        witness_addr=witness_addr,
        ladder=ladder,
        candidate_dir=candidate_dir,
    )

    # 3. Encode DISKBOOT.BIN
    diskboot_bin = encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)

    # 4. Generate inspector
    insp_m, insp_bin = generate_candidate_inspector(
        witness_addr=witness_addr,
        candidate_dir=candidate_dir,
    )

    # 5. Generate manifest
    artifacts = {
        "candidate_main.elf": core_elf,
        "candidate_main.bin": core_bin,
        "candidate_loader.elf": loader_elf,
        "candidate_loader.bin": loader_bin,
        "DISKBOOT.BIN": diskboot_bin,
        "witness_inspector_gm110c.m": insp_m,
        "witness_inspector_payload.bin": insp_bin,
    }

    heap_start_addr = G3X_RESIDENT_HEAP_START if resident else core_end_addr
    if core_end_addr > heap_start_addr:
        raise ValueError(
            f"Linked _end (0x{core_end_addr:08X}) exceeds heap start (0x{heap_start_addr:08X})"
        )

    manifest_path = generate_manifest(
        artifacts,
        witness_addr=witness_addr,
        core_end_addr=core_end_addr,
        candidate_dir=candidate_dir,
        inspector_verified=True,
    )
    if resident:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_data["architectural_invariants"]["core_end_symbol"] = f"0x{core_end_addr:08X}"
        manifest_data["architectural_invariants"]["dryos_heap_base"] = f"0x{heap_start_addr:08X}"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    diskboot_sha256 = sha256_file(diskboot_bin)
    diskboot_size = os.path.getsize(diskboot_bin)
    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")
    print(f"DISKBOOT.BIN SHA-256: {diskboot_sha256}")
    print(f"DISKBOOT.BIN Size:    {diskboot_size} bytes")

    return {
        "candidate_dir": candidate_dir,
        "core_elf": core_elf,
        "core_bin": core_bin,
        "loader_elf": loader_elf,
        "loader_bin": loader_bin,
        "diskboot_bin": diskboot_bin,
        "manifest_path": manifest_path,
        "witness_addr": f"0x{witness_addr:08X}",
        "core_end_addr": f"0x{core_end_addr:08X}",
        "heap_start_addr": f"0x{(G3X_RESIDENT_HEAP_START if resident else core_end_addr):08X}",
        "resident": resident,
        "diskboot_sha256": diskboot_sha256,
        "diskboot_size": diskboot_size,
    }


def main():
    parser = argparse.ArgumentParser(
        description="PORT-25/32: Opt-in combined breadcrumb ladder + G3X_POWERON_FIX + G3X_RESIDENT builder for G3 X (GM1.10C)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help=f"Output directory for candidate artifacts (default: {CANDIDATE_LADDER_FIX_DIR})",
    )
    parser.add_argument(
        "--default",
        action="store_true",
        help="Build default control candidate (ladder=0, poweron_fix=0) to verify baseline invariance",
    )
    parser.add_argument(
        "--ladder",
        action="store_true",
        help="Build ladder-only candidate (ladder=1, poweron_fix=0)",
    )
    parser.add_argument(
        "--poweron-fix",
        action="store_true",
        help="Build poweron-fix-only candidate (ladder=0, poweron_fix=1)",
    )
    parser.add_argument(
        "--ladder-fix",
        "--combined",
        action="store_true",
        help="Build combined ladder + poweron_fix candidate (ladder=1, poweron_fix=1)",
    )
    parser.add_argument(
        "--resident",
        action="store_true",
        help="Build opt-in G3X_RESIDENT=1 heartbeat candidate (ladder=1, poweron_fix=1, resident=1)",
    )
    args = parser.parse_args()

    resident = bool(args.resident or os.environ.get("G3X_RESIDENT", "0") == "1")

    if args.default:
        ladder = False
        poweron_fix = False
        resident = False
    elif args.ladder:
        ladder = True
        poweron_fix = False
        resident = False
    elif args.poweron_fix:
        ladder = False
        poweron_fix = True
        resident = False
    else:
        # Default behavior: build combined candidate (ladder=1, poweron_fix=1)
        ladder = True
        poweron_fix = True

    res = build_candidate(
        ladder=ladder,
        poweron_fix=poweron_fix,
        out_dir=args.out_dir,
        resident=resident,
    )

    print("\nSummary:")
    print(f"  Directory:    {res['candidate_dir']}")
    print(f"  DISKBOOT.BIN: {res['diskboot_bin']}")
    print(f"  SHA-256:      {res['diskboot_sha256']}")
    print(f"  Size:         {res['diskboot_size']} bytes")
    print(f"  boot_witness: {res['witness_addr']}")
    print(f"  _end:         {res['core_end_addr']}")
    print(f"  heap_start:   {res['heap_start_addr']}")
    print(f"  resident:     {res['resident']}")


if __name__ == "__main__":
    main()
