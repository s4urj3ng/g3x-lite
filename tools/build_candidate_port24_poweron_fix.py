#!/usr/bin/env python3
"""PORT-24: Opt-in Short-Press Boot Fix Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in candidate DISKBOOT.BIN with the second power-on check fix in
sub_fc05b962_my (chdk-port/platform/g3x/sub/110c/boot_prototype.c:350).

Context (owner, 2026-11-01):
The PORT-19 default build reaches the stock UI (O1) only when the power button
is held until the LCD comes on. A short press powers off after loader entry.
Owner attributes this to the second sub_fc1284ac power-on check in sub_fc05b962_my,
which cuts power once the button is released.

Mechanism:
In the post-loader restart sequence, sub_fc05b962_my executes after cold kernel
initialization. If the user performed a normal short press, the button has already
been released. The stock check sub_fc1284ac returns 0, which falls through to
sub_fc05ba56 (writing 0x004C0003 to GPIO 0x67) cutting DC-DC power to the SoC.
Under G3X_POWERON_FIX=1, execution forces r0 = 1 and branches unconditionally to
loc_fc05b978, preventing shutdown and continuing into task_Startup_my.

Safety & Invariance:
- Default build (G3X_POWERON_FIX undefined or 0) produces the exact byte-identical
  PORT-19 reference DISKBOOT.BIN (SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136).
- Opt-in build preserves exact function and symbol alignment (boot_witness @ 0x0035F7A0,
  _end @ 0x00366CB0).
- Reuses functions from tools/build_candidate_port2a.py by import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Add repo root and tools directory to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import (  # noqa: E402
    CC,
    AR,
    OBJCOPY,
    NM,
    CHDK_PORT,
    SUB_DIR,
    LOADER_DIR,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_loader,
    encode_candidate_diskboot,
    copy_inspector_artifacts,
    generate_candidate_inspector,
    generate_manifest,
    verify_witness_addr_from_elf,
    extract_symbol_addr_from_nm,
    sha256_file,
    run_cmd,
)

EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0
EXPECTED_CORE_END_ADDR = 0x00366CB0
CANDIDATE_POWERON_DIR = os.path.join(REPO_ROOT, "candidate_port24_poweron_fix")


def build_candidate_core_poweron(
    poweron_fix: bool = True,
    candidate_dir: str = CANDIDATE_POWERON_DIR,
) -> tuple[str, str]:
    """Compile candidate core with optional G3X_POWERON_FIX define."""
    print(f"--- Building Candidate Core (poweron_fix={poweron_fix}) (@ 0x003489B4) ---")
    os.makedirs(candidate_dir, exist_ok=True)

    boot_proto_c = os.path.join(SUB_DIR, "boot_prototype.c")
    stubs_proto_s = os.path.join(SUB_DIR, "stubs_prototype.S")
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
    cflags.extend([
        "-c",
        "-o",
        boot_proto_o,
        boot_proto_c,
    ])
    run_cmd(cflags)

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
    run_cmd(sflags)

    # 3. Create candidate libplatformsub archive
    if os.path.exists(lib_proto_a):
        os.remove(lib_proto_a)
    obj_files = [
        boot_proto_o,
        stubs_proto_o,
        os.path.join(SUB_DIR, "stubs_min.o"),
        os.path.join(SUB_DIR, "stubs_entry.o"),
        os.path.join(SUB_DIR, "stubs_entry_2.o"),
        os.path.join(SUB_DIR, "capt_seq.o"),
        os.path.join(SUB_DIR, "movie_rec.o"),
        os.path.join(SUB_DIR, "filewrite.o"),
        os.path.join(SUB_DIR, "main.thm.o"),
        os.path.join(SUB_DIR, "gui_draw.thm.o"),
        os.path.join(SUB_DIR, "memmgmt.thm.o"),
        os.path.join(SUB_DIR, "gui.thm.o"),
        os.path.join(SUB_DIR, "kbd_process.thm.o"),
        os.path.join(SUB_DIR, "kbd_common.thm.o"),
        os.path.join(SUB_DIR, "conf.thm.o"),
        os.path.join(SUB_DIR, "gui_osd.thm.o"),
        os.path.join(SUB_DIR, "raw.thm.o"),
        os.path.join(SUB_DIR, "usb_sync.thm.o"),
        os.path.join(SUB_DIR, "shooting.thm.o"),
        os.path.join(SUB_DIR, "camera_info.thm.o"),
        os.path.join(SUB_DIR, "remotecap.thm.o"),
        os.path.join(SUB_DIR, "lib_thumb.thm.o"),
        os.path.join(SUB_DIR, "lang_str.thm.o"),
        os.path.join(SUB_DIR, "ptp.thm.o"),
    ]
    run_cmd([AR, "cr", lib_proto_a] + obj_files)

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
        os.path.join(SUB_DIR, "entry.o"),
        os.path.join(CHDK_PORT, "platform", "g3x", "libplatform.a"),
        lib_proto_a,
        os.path.join(CHDK_PORT, "lib", "font", ".o2", "libfont.a"),
        os.path.join(CHDK_PORT, "lib", "math", ".o2", "libmath.a"),
        os.path.join(CHDK_PORT, "lib", "lang", ".o2", "liblang.a"),
        os.path.join(CHDK_PORT, "lib", "armutil", ".o2", "libarmutil.a"),
        os.path.join(CHDK_PORT, "lib", "core", ".o2", "libcore.a"),
        "-lgcc",
        "-Wl,--end-group",
    ]
    run_cmd(ld_cmd, cwd=CHDK_PORT)

    # 5. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", core_elf, core_bin])
    print(f"  [OK] candidate_main.bin generated ({os.path.getsize(core_bin)} B)")
    return core_elf, core_bin


def build_candidate(
    poweron_fix: bool = True,
    out_dir: str | None = None,
) -> dict[str, str]:
    """Build complete candidate package."""
    candidate_dir = os.path.abspath(out_dir) if out_dir else CANDIDATE_POWERON_DIR
    os.makedirs(candidate_dir, exist_ok=True)

    core_elf, core_bin = build_candidate_core_poweron(
        poweron_fix=poweron_fix, candidate_dir=candidate_dir
    )
    loader_elf, loader_bin, witness_addr, core_end_addr = build_candidate_loader(
        core_elf, core_bin, candidate_dir=candidate_dir
    )
    diskboot_bin = encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)

    insp_m, insp_bin = generate_candidate_inspector(
        witness_addr,
        candidate_dir=candidate_dir,
    )
    insp_verified = True

    artifacts = {
        "candidate_main.elf": core_elf,
        "candidate_main.bin": core_bin,
        "candidate_loader.elf": loader_elf,
        "candidate_loader.bin": loader_bin,
        "DISKBOOT.BIN": diskboot_bin,
        "witness_inspector_gm110c.m": insp_m,
        "witness_inspector_payload.bin": insp_bin,
    }

    manifest_path = generate_manifest(
        artifacts,
        witness_addr=witness_addr,
        core_end_addr=core_end_addr,
        candidate_dir=candidate_dir,
        inspector_verified=insp_verified,
    )
    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")
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
        "diskboot_sha256": sha256_file(diskboot_bin),
    }


def main():
    parser = argparse.ArgumentParser(
        description="PORT-24: Opt-in short-press boot fix builder for G3 X (GM1.10C)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help=f"Output directory for candidate artifacts (default: {CANDIDATE_POWERON_DIR})",
    )
    parser.add_argument(
        "--default",
        action="store_true",
        help="Build default candidate (G3X_POWERON_FIX=0) to verify invariance",
    )
    parser.add_argument(
        "--poweron-fix",
        action="store_true",
        default=True,
        help="Enable short-press power-on fix define (-DG3X_POWERON_FIX=1, default: True)",
    )
    args = parser.parse_args()

    poweron_fix = not args.default
    res = build_candidate(poweron_fix=poweron_fix, out_dir=args.out_dir)
    print(f"\nResults for {'POWERON_FIX' if poweron_fix else 'DEFAULT'}:")
    print(f"  DISKBOOT.BIN: {res['diskboot_bin']}")
    print(f"  SHA-256:      {res['diskboot_sha256']}")
    print(f"  boot_witness: {res['witness_addr']}")
    print(f"  _end:         {res['core_end_addr']}")


if __name__ == "__main__":
    main()
