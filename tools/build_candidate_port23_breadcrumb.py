#!/usr/bin/env python3
"""PORT-23 T2b: Opt-in LED Breadcrumb Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic DISKBOOT.BIN with an LED breadcrumb at exactly one
execution checkpoint, allowing the camera owner to observe how far execution
progresses after loader entry (0x8000).

Hardware facts VERIFIED on camera (owner, 2026-11-01):
- MMIO 0xD20B0884 is the green LED register.
- Writing 0x004D0002 turns the green LED ON.
- Writing 0x004C0003 turns the green LED OFF.
- Loader entry prologue at 0x8000 runs.
- Stalls of 0x06000000 and 0x00600000 both ended with the camera dark.

Stages supported:
  1. loader_entry:  At 0x8000 in loader_entry_breadcrumb.S before my_restart.
  2. before_copy:   In my_restart immediately before core_copy().
  3. after_copy:    In my_restart immediately after core_copy().
  4. witness_entry: In my_restart at boot_witness entry.
  5. witness_write: In my_restart immediately after w->checksum store.
  6. pre_jump:      In my_restart immediately before bx r0 to payload.

Safety invariants:
- Documented builds have NO delay loop (delay = 0, LED stays on).
- Optional delay is capped at 0x00600000.
- Reuses functions from tools/build_candidate_port2a.py by import.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add repo root and tools directory to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(REPO_ROOT))

# Import reusable functions and constants from build_candidate_port2a.py
from build_candidate_port2a import (  # noqa: E402
    CC,
    OBJCOPY,
    NM,
    CHDK_PORT,
    LOADER_DIR,
    SUB_DIR,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_core,
    encode_candidate_diskboot,
    generate_candidate_inspector,
    copy_inspector_artifacts,
    verify_witness_addr_from_elf,
    extract_symbol_addr_from_nm,
    sha256_file,
    run_cmd,
)

EXPECTED_CORE_END_ADDR = 0x00366CB0

STAGES = (
    "loader_entry",
    "before_copy",
    "after_copy",
    "witness_entry",
    "witness_write",
    "pre_jump",
)

STAGE_MACROS = {
    "loader_entry": "LED_BREADCRUMB_LOADER_ENTRY",
    "before_copy": "LED_BREADCRUMB_BEFORE_COPY",
    "after_copy": "LED_BREADCRUMB_AFTER_COPY",
    "witness_entry": "LED_BREADCRUMB_WITNESS_ENTRY",
    "witness_write": "LED_BREADCRUMB_WITNESS_WRITE",
    "pre_jump": "LED_BREADCRUMB_PRE_JUMP",
}

G3X_LED_MMIO_ADDR = 0xD20B0884
G3X_LED_ON_VAL = 0x004D0002
G3X_LED_OFF_VAL = 0x004C0003
MAX_SAFETY_DELAY = 0x00600000  # 6,291,456 iterations max


def build_breadcrumb_loader(
    core_elf: str,
    core_bin: str,
    stage: str,
    candidate_dir: str,
    off_next: bool = False,
    delay: int = 0,
) -> tuple[str, str, int, int]:
    """Build candidate loader for the given breadcrumb stage."""
    print(f"--- Building Breadcrumb Loader for stage '{stage}' (@ 0x00008000) ---")
    os.makedirs(candidate_dir, exist_ok=True)

    stage_norm = stage.lower()
    if stage_norm not in STAGE_MACROS:
        raise ValueError(f"Unknown breadcrumb stage: {stage} (valid: {STAGES})")

    if delay < 0 or delay > MAX_SAFETY_DELAY:
        raise ValueError(
            f"Delay 0x{delay:X} exceeds maximum safety cap 0x{MAX_SAFETY_DELAY:X}"
        )

    macro_name = STAGE_MACROS[stage_norm]

    # Entry assembly source
    loader_entry_s = os.path.join(SUB_DIR, "loader_entry_breadcrumb.S")
    loader_entry_o = os.path.join(candidate_dir, "entry_breadcrumb.o")

    entry_cmd = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-nostdinc",
        "-DLED_BREADCRUMB=1",
        f"-D{macro_name}=1",
    ]
    if delay > 0:
        entry_cmd.append(f"-DLED_BREADCRUMB_DELAY={delay}")
    if off_next:
        entry_cmd.append("-DLED_BREADCRUMB_OFF_NEXT=1")

    entry_cmd.extend(["-c", "-o", loader_entry_o, loader_entry_s])
    run_cmd(entry_cmd, cwd=LOADER_DIR)

    # Loader C source: prefer tracked loader_main_breadcrumb.c if available, else main_prototype.c
    sub_loader_c = os.path.join(SUB_DIR, "loader_main_breadcrumb.c")
    if os.path.isfile(sub_loader_c):
        loader_c = sub_loader_c
    else:
        loader_c = os.path.join(LOADER_DIR, "main_prototype.c")

    blobs_s = os.path.join(LOADER_DIR, "blobs.S")

    loader_o = os.path.join(candidate_dir, "main_breadcrumb.o")
    blobs_o = os.path.join(candidate_dir, "blobs_candidate.o")
    loader_elf = os.path.join(candidate_dir, "candidate_loader.elf")
    loader_bin = os.path.join(candidate_dir, "candidate_loader.bin")

    witness_addr = verify_witness_addr_from_elf(core_elf, EXPECTED_BOOT_WITNESS_ADDR)
    print(
        f"  [OK] boot_witness confirmed at 0x{witness_addr:08X} "
        f"(matches expected 0x{EXPECTED_BOOT_WITNESS_ADDR:08X})"
    )

    # 1. Compile loader C source with stage flags
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
        "-DLED_BREADCRUMB=1",
        f"-D{macro_name}=1",
    ]
    if off_next:
        cflags.append("-DLED_BREADCRUMB_OFF_NEXT=1")
    if delay > 0:
        cflags.append(f"-DLED_BREADCRUMB_DELAY={delay}")

    cflags.extend(["-nostdinc", "-c", "-o", loader_o, loader_c])
    run_cmd(cflags, cwd=LOADER_DIR)

    # 2. Assemble blobs
    bflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-nostdinc",
        f'-DCORE_FILE="{core_bin}"',
        "-c",
        "-o",
        blobs_o,
        blobs_s,
    ]
    run_cmd(bflags, cwd=LOADER_DIR)

    # 3. Link candidate_loader.elf
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
    run_cmd(ld_cmd, cwd=LOADER_DIR)

    # 4. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", loader_elf, loader_bin])
    print(f"  [OK] candidate_loader.bin generated ({os.path.getsize(loader_bin)} B)")

    try:
        nm_out = run_cmd([NM, "-n", core_elf])
        core_end_addr = extract_symbol_addr_from_nm(nm_out, "_end")
    except Exception:
        core_end_addr = EXPECTED_CORE_END_ADDR

    return loader_elf, loader_bin, witness_addr, core_end_addr


def build_breadcrumb_candidate(
    stage: str,
    out_dir: str,
    off_next: bool = False,
    delay: int = 0,
    trace: bool = False,
) -> dict:
    """End-to-end breadcrumb candidate build."""
    stage_norm = stage.lower()
    if stage_norm not in STAGES:
        raise ValueError(f"Invalid stage '{stage}'. Valid stages: {STAGES}")

    if delay > MAX_SAFETY_DELAY:
        raise ValueError(
            f"Requested delay 0x{delay:X} exceeds maximum allowed cap 0x{MAX_SAFETY_DELAY:X}"
        )

    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_dir = str(out_path)

    # 1. Build Candidate Core (reused from build_candidate_port2a)
    core_elf, core_bin = build_candidate_core(trace=trace, candidate_dir=candidate_dir)

    # 2. Build Candidate Loader with stage breadcrumb
    loader_elf, loader_bin, witness_addr, core_end = build_breadcrumb_loader(
        core_elf=core_elf,
        core_bin=core_bin,
        stage=stage_norm,
        candidate_dir=candidate_dir,
        off_next=off_next,
        delay=delay,
    )

    # 3. Encode dancingbits DISKBOOT.BIN
    diskboot_bin = encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)

    # 4. Generate inspector artifacts
    insp_m, insp_bin = generate_candidate_inspector(
        witness_addr=witness_addr, candidate_dir=candidate_dir
    )

    # 5. Build manifest
    manifest_path = out_path / "candidate_manifest.json"
    manifest_data = {
        "candidate": "PORT-23-LED-BREADCRUMB",
        "stage": stage_norm,
        "stage_macro": STAGE_MACROS[stage_norm],
        "off_next": off_next,
        "delay": delay,
        "led_mmio": f"0x{G3X_LED_MMIO_ADDR:08X}",
        "led_on_val": f"0x{G3X_LED_ON_VAL:08X}",
        "led_off_val": f"0x{G3X_LED_OFF_VAL:08X}",
        "witness_address": f"0x{witness_addr:08X}",
        "core_end_address": f"0x{core_end:08X}",
        "artifacts": {
            "candidate_main.elf": {
                "size": os.path.getsize(core_elf),
                "sha256": sha256_file(core_elf),
            },
            "candidate_main.bin": {
                "size": os.path.getsize(core_bin),
                "sha256": sha256_file(core_bin),
            },
            "candidate_loader.elf": {
                "size": os.path.getsize(loader_elf),
                "sha256": sha256_file(loader_elf),
            },
            "candidate_loader.bin": {
                "size": os.path.getsize(loader_bin),
                "sha256": sha256_file(loader_bin),
            },
            "DISKBOOT.BIN": {
                "size": os.path.getsize(diskboot_bin),
                "sha256": sha256_file(diskboot_bin),
            },
        },
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"  [OK] Breadcrumb manifest written to {manifest_path}")
    print(f"  Stage: {stage_norm}")
    print(f"  DISKBOOT.BIN SHA-256: {manifest_data['artifacts']['DISKBOOT.BIN']['sha256']}")
    print(f"  DISKBOOT.BIN Size:    {manifest_data['artifacts']['DISKBOOT.BIN']['size']} B")

    return manifest_data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build opt-in LED breadcrumb candidate for Canon PowerShot G3 X (GM1.10C)."
    )
    parser.add_argument(
        "--stage",
        required=True,
        choices=STAGES,
        help="Breadcrumb checkpoint stage to signal via LED ON.",
    )
    parser.add_argument(
        "--off-next",
        action="store_true",
        default=False,
        help="Turn LED OFF (0x004C0003) at the subsequent checkpoint.",
    )
    parser.add_argument(
        "--delay",
        type=lambda x: int(x, 0),
        default=0,
        help=f"Optional busy-wait delay iterations (default: 0; cap: 0x{MAX_SAFETY_DELAY:X}).",
    )
    parser.add_argument(
        "--out-dir",
        default="candidate_breadcrumb",
        help="Output directory (default: candidate_breadcrumb).",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        default=False,
        help="Enable core tracing buffer (default: False).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.delay > MAX_SAFETY_DELAY:
        sys.exit(
            f"ERROR: delay {args.delay} (0x{args.delay:X}) exceeds safety limit 0x{MAX_SAFETY_DELAY:X}"
        )
    build_breadcrumb_candidate(
        stage=args.stage,
        out_dir=args.out_dir,
        off_next=args.off_next,
        delay=args.delay,
        trace=args.trace,
    )


if __name__ == "__main__":
    main()
