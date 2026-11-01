#!/usr/bin/env python3
"""PORT-24 T3 (r3): Opt-in Breadcrumb Ladder Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic DISKBOOT.BIN containing the progressive breadcrumb ladder:
Step 1: after_prologue - after entry prologue & check_compat()
Step 2: after_copy     - after core_copy() & witness recording
Step 3: before_dcache  - before ROM_DCACHE_CLEAN_INV (0xFC127AB1)
Step 4: after_dcache   - after ROM_DCACHE_CLEAN_INV + dsb sy
Step 5: before_icache  - before ROM_ICACHE_INV_BP (0xFC127B09)
Step 6: after_icache   - after ROM_ICACHE_INV_BP + dsb sy + isb sy
Step 7: before_bx      - before handoff branch bx r0 (after cpsid if)

Pulse scheme: One visible pulse per step.
Iteration parameters:
  ON:  0x00134000 (1,261,568 iterations) -> ~20.05 ms (fast 100ms) / ~25.07 ms (nom 125ms) / ~60.16 ms (slow 300ms) [INFERRED]
  OFF: 0x002C4000 (2,899,968 iterations) -> ~46.09 ms (fast 100ms) / ~57.62 ms (nom 125ms) / ~138.28 ms (slow 300ms) [INFERRED]
  Total loop: 0x003F8000 (4,161,536 iterations) -> ~66.15 ms (fast) / ~82.68 ms (nom) / 198.44 ms (slow) [INFERRED]

Total flashes observed before shutdown indicates the last step reached.
Full step (loops + 1.0 ms overhead) duration at slowest bound is 199.44 ms strictly under 200.0 ms.

When --no-ladder / --flag-off is specified (or when flags are omitted by default), output is byte-identical
to the locked PORT-19 default control:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136
  Size: 118,001 bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
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
    OBJCOPY,
    NM,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_core,
    build_candidate_loader as build_default_loader,
    encode_candidate_diskboot,
    generate_candidate_inspector,
    verify_witness_addr_from_elf,
    sha256_file,
    run_cmd,
)

EXPECTED_CORE_END_ADDR = 0x00366CB0
EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)

G3X_LED_MMIO_ADDR = 0xD20B0884
G3X_LED_ON_VAL = 0x004D0002
G3X_LED_OFF_VAL = 0x004C0003

LADDER_ENTRY_S = str(SUB_DIR / "loader_entry_breadcrumb.S")
LADDER_LOADER_C = str(SUB_DIR / "loader_main_breadcrumb.c")


def ensure_bootstrap():
    """Ensure platform bootstrap has populated platform headers if missing."""
    platform_cam_h = CHDK_PORT / "platform" / "g3x" / "platform_camera.h"
    if not platform_cam_h.is_file():
        bootstrap_script = TOOLS_DIR / "bootstrap_chdk_platform.py"
        run_cmd(["python3", "-B", str(bootstrap_script)], cwd=str(REPO_ROOT))


def build_ladder_loader(
    core_elf: str,
    core_bin: str,
    candidate_dir: str,
) -> tuple[str, str, int, int]:
    """Build candidate loader with opt-in breadcrumb ladder defined."""
    print("--- Building Breadcrumb Ladder Loader (@ 0x00008000) ---")
    os.makedirs(candidate_dir, exist_ok=True)

    loader_entry_s = LADDER_ENTRY_S
    if not os.path.isfile(loader_entry_s):
        raise FileNotFoundError(f"Missing loader entry source: {loader_entry_s}")
    loader_entry_o = os.path.join(candidate_dir, "entry_ladder.o")

    entry_cmd = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-nostdinc",
        "-c",
        "-o",
        loader_entry_o,
        loader_entry_s,
    ]
    run_cmd(entry_cmd, cwd=str(LOADER_DIR))

    loader_c = LADDER_LOADER_C
    if not os.path.isfile(loader_c):
        raise FileNotFoundError(f"Missing loader C source: {loader_c}")

    blobs_s = os.path.join(str(LOADER_DIR), "blobs.S")

    loader_o = os.path.join(candidate_dir, "main_ladder.o")
    blobs_o = os.path.join(candidate_dir, "blobs_candidate.o")
    loader_elf = os.path.join(candidate_dir, "candidate_loader.elf")
    loader_bin = os.path.join(candidate_dir, "candidate_loader.bin")

    witness_addr = verify_witness_addr_from_elf(core_elf, EXPECTED_BOOT_WITNESS_ADDR)
    print(
        f"  [OK] boot_witness confirmed at 0x{witness_addr:08X} "
        f"(matches expected 0x{EXPECTED_BOOT_WITNESS_ADDR:08X})"
    )

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
    run_cmd(bflags, cwd=str(LOADER_DIR))

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

    return loader_elf, loader_bin, witness_addr, EXPECTED_CORE_END_ADDR


def build_candidate(
    ladder: bool = True,
    out_dir: str | None = None,
) -> dict:
    """Execute complete candidate build pipeline."""
    ensure_bootstrap()

    if out_dir:
        candidate_dir = os.path.abspath(out_dir)
    elif ladder:
        candidate_dir = str(REPO_ROOT / "candidate_breadcrumb_ladder")
    else:
        candidate_dir = str(REPO_ROOT / "candidate_port2a")

    os.makedirs(candidate_dir, exist_ok=True)

    # 1. Build core
    core_elf, core_bin = build_candidate_core(candidate_dir=candidate_dir)

    # 2. Build loader
    if ladder:
        loader_elf, loader_bin, witness_addr, core_end_addr = build_ladder_loader(
            core_elf, core_bin, candidate_dir=candidate_dir
        )
    else:
        loader_elf, loader_bin, witness_addr, core_end_addr = build_default_loader(
            core_elf, core_bin, candidate_dir=candidate_dir
        )

    # 3. Encode DISKBOOT.BIN
    diskboot_bin = encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)

    # 4. Generate inspector
    insp_m, insp_bin = generate_candidate_inspector(
        witness_addr, candidate_dir=candidate_dir
    )

    # 5. Generate manifest
    manifest_path = os.path.join(candidate_dir, "candidate_manifest.json")
    artifacts = {
        "candidate_main.elf": {
            "path": os.path.relpath(core_elf, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(core_elf),
            "sha256": sha256_file(core_elf),
        },
        "candidate_main.bin": {
            "path": os.path.relpath(core_bin, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(core_bin),
            "sha256": sha256_file(core_bin),
        },
        "candidate_loader.elf": {
            "path": os.path.relpath(loader_elf, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(loader_elf),
            "sha256": sha256_file(loader_elf),
        },
        "candidate_loader.bin": {
            "path": os.path.relpath(loader_bin, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(loader_bin),
            "sha256": sha256_file(loader_bin),
        },
        "DISKBOOT.BIN": {
            "path": os.path.relpath(diskboot_bin, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(diskboot_bin),
            "sha256": sha256_file(diskboot_bin),
        },
        "witness_inspector_gm110c.m": {
            "path": os.path.relpath(insp_m, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(insp_m),
            "sha256": sha256_file(insp_m),
        },
        "witness_inspector_payload.bin": {
            "path": os.path.relpath(insp_bin, str(REPO_ROOT)),
            "size_bytes": os.path.getsize(insp_bin),
            "sha256": sha256_file(insp_bin),
        },
    }

    manifest = {
        "candidate_name": "PORT-24-BREADCRUMB-LADDER" if ladder else "PORT-2A-FIRST-BOOT",
        "target_camera": "Canon PowerShot G3 X (GM1.10C)",
        "platform_id": "0x32A8",
        "ladder_enabled": ladder,
        "status": "OFFLINE_CANDIDATE_BUILT",
        "independent_review": "PENDING",
        "hardware_readiness": "NO-GO",
        "architectural_invariants": {
            "boot_witness_addr": f"0x{witness_addr:08X}",
            "core_end_symbol": f"0x{core_end_addr:08X}",
            "core_entry_target": "0x003489B4",
            "loader_load_addr": "0x00008000",
            "loader_stack_addr": "0x00008000",
        },
        "candidate_artifacts": artifacts,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"  [OK] Manifest written to {manifest_path}")

    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")
    print(f"DISKBOOT.BIN SHA-256: {artifacts['DISKBOOT.BIN']['sha256']}")
    print(f"DISKBOOT.BIN Size:    {artifacts['DISKBOOT.BIN']['size_bytes']} bytes")

    if not ladder:
        actual_hash = artifacts["DISKBOOT.BIN"]["sha256"]
        if actual_hash != EXPECTED_DEFAULT_DISKBOOT_SHA256:
            raise ValueError(
                f"Default build invariance violated!\n"
                f"Expected: {EXPECTED_DEFAULT_DISKBOOT_SHA256}\n"
                f"Actual:   {actual_hash}"
            )
        print("  [OK] Default build invariance confirmed (matches locked SHA-256).")

    return manifest


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build opt-in PORT-24 breadcrumb ladder candidate or verify default invariance."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--ladder",
        dest="ladder",
        action="store_true",
        default=False,
        help="Build opt-in breadcrumb ladder candidate.",
    )
    group.add_argument(
        "--no-ladder",
        "--flag-off",
        dest="ladder",
        action="store_false",
        help="Build default control without ladder (default behavior; asserts byte-identity to locked SHA-256).",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for candidate artifacts.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    build_candidate(ladder=args.ladder, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
