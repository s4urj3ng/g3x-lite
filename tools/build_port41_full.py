#!/usr/bin/env python3
"""PORT-41: Standard CHDK Full Build for PowerShot G3 X (GM1.10C).

Performs a standard CHDK build in an isolated staging tree under out/port41-full/.
Overlays full_build/g3x onto platform/g3x in the staging directory only.
Produces:
  out/port41-full/DISKBOOT.BIN
  out/port41-full/CHDK/ (MODULES, FONTS, LANG)
  out/port41-full/port41_manifest.json (SHA-256 manifest)

No files outside out/port41-full/ are written or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHDK_PORT = REPO_ROOT / "chdk-port"
FULL_BUILD_SRC = REPO_ROOT / "full_build" / "g3x"
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
CROSS_COMPILE = str(TOOLCHAIN_BIN / "arm-none-eabi-")

OUT_DIR = REPO_ROOT / "out" / "port41-full"
STAGE_DIR = OUT_DIR / "stage_chdk"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def overlay_tree(src: Path, dst: Path) -> None:
    """Recursively overlay files from src directory onto dst directory."""
    for root, dirs, files in os.walk(src):
        rel_path = Path(root).relative_to(src)
        target_dir = dst / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)


def clean_staging_artifacts(stage_dir: Path) -> None:
    """Remove any stale precompiled objects/archives/binaries from the staging copy."""
    # Ensure all files and directories in staging are user-writable
    subprocess.run(["chmod", "-R", "u+w", str(stage_dir)], check=True)

    # Clean tools binaries and objects
    tools_dir = stage_dir / "tools"
    if tools_dir.is_dir():
        for ext in ("*.o", "*.a", "*.d"):
            for f in tools_dir.glob(f"**/{ext}"):
                try:
                    f.unlink()
                except OSError:
                    pass

    # Clean lib, core, modules, platform, loader stale objects and archives
    for sub in ["lib", "core", "modules", "platform", "loader", "bin"]:
        target = stage_dir / sub
        if not target.is_dir():
            continue
        for o2 in target.glob("**/.o2"):
            if o2.is_dir():
                shutil.rmtree(o2, ignore_errors=True)
        for ext in ("*.o", "*.a", "*.d", "*.flt", "*.dump"):
            for f in target.glob(f"**/{ext}"):
                try:
                    f.unlink()
                except OSError:
                    pass


def build_port41_full(clean_stage: bool = True, keep_stage: bool = False) -> int:
    gcc_path = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
    if not gcc_path.is_file() or not os.access(gcc_path, os.X_OK):
        print(f"ERROR: Pinned toolchain compiler not found: {gcc_path}", file=sys.stderr)
        return 2

    if not CHDK_PORT.is_dir():
        print(f"ERROR: Source CHDK tree not found: {CHDK_PORT}", file=sys.stderr)
        return 1

    if not FULL_BUILD_SRC.is_dir():
        print(f"ERROR: full_build sources not found: {FULL_BUILD_SRC}", file=sys.stderr)
        return 1

    # Prepare staging directory
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if clean_stage and STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)

    if not STAGE_DIR.exists():
        print(f"Staging CHDK tree to {STAGE_DIR}...")
        # Copy chdk-port into stage_chdk
        shutil.copytree(CHDK_PORT, STAGE_DIR, symlinks=True)

    # Clean stale objects, ensure permissions
    clean_staging_artifacts(STAGE_DIR)

    # Overlay full_build/g3x onto stage_chdk/platform/g3x/
    platform_target = STAGE_DIR / "platform" / "g3x"
    print(f"Overlaying {FULL_BUILD_SRC} onto {platform_target}...")
    overlay_tree(FULL_BUILD_SRC, platform_target)

    # Ensure clean platform objects in staging copy so full build compiles freshly
    for subpath in ["platform/g3x", "platform/g3x/sub/110c", "loader/g3x"]:
        p = STAGE_DIR / subpath
        if p.is_dir():
            subprocess.run(
                ["make", "-C", str(p), "PLATFORM=g3x", "PLATFORMSUB=110c", "G3X_FULL_BUILD=1", "clean"],
                cwd=str(STAGE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Run normal CHDK make
    cmd = [
        "make",
        "-C",
        str(STAGE_DIR),
        "PLATFORM=g3x",
        "PLATFORMSUB=110c",
        "G3X_FULL_BUILD=1",
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
        "fir",
    ]

    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    res = subprocess.run(cmd, cwd=str(STAGE_DIR), env=env)
    if res.returncode != 0:
        print(f"ERROR: Build failed with exit code {res.returncode}", file=sys.stderr)
        return res.returncode

    # Verify generated DISKBOOT.BIN
    stage_diskboot = STAGE_DIR / "bin" / "DISKBOOT.BIN"
    if not stage_diskboot.is_file() or stage_diskboot.stat().st_size == 0:
        print(f"ERROR: Expected output missing or empty: {stage_diskboot}", file=sys.stderr)
        return 1

    out_diskboot = OUT_DIR / "DISKBOOT.BIN"
    shutil.copy2(stage_diskboot, out_diskboot)
    print(f"[OK] Generated {out_diskboot} ({out_diskboot.stat().st_size} bytes)")

    # Verify and copy CHDK/ distribution folder
    stage_chdk = STAGE_DIR / "CHDK"
    out_chdk = OUT_DIR / "CHDK"
    if out_chdk.exists():
        shutil.rmtree(out_chdk)
    shutil.copytree(stage_chdk, out_chdk, symlinks=True)

    modules_dir = out_chdk / "MODULES"
    fonts_dir = out_chdk / "FONTS"
    lang_dir = out_chdk / "LANG"

    flt_files = sorted(modules_dir.glob("*.flt"))
    if not flt_files:
        print(f"ERROR: No .flt modules found in {modules_dir}", file=sys.stderr)
        return 1

    print(f"[OK] {len(flt_files)} modules copied to {modules_dir}")
    print(f"[OK] Fonts directory present: {fonts_dir.is_dir()}")
    print(f"[OK] Lang directory present: {lang_dir.is_dir()}")

    # Generate SHA-256 manifest
    manifest_data = {
        "build": {
            "platform": "g3x",
            "platform_sub": "110c",
            "flags": [
                "G3X_FULL_BUILD=1",
                "G3X_DISABLE_CARD_WRITES=1",
                "CAM_SUPPORT_BITMAP_RES_CHANGE=1",
                "OPT_DISABLE_FILE_WRITES=1",
                "G3X_GUI5=1",
            ],
            "toolchain": "gcc-arm-none-eabi-5_4-2016q3",
        },
        "artifacts": {
            "DISKBOOT.BIN": {
                "path": "DISKBOOT.BIN",
                "size": out_diskboot.stat().st_size,
                "sha256": sha256_file(out_diskboot),
            },
            "modules_count": len(flt_files),
            "modules": {
                f.name: {
                    "size": f.stat().st_size,
                    "sha256": sha256_file(f),
                }
                for f in flt_files
            },
        },
    }

    manifest_path = OUT_DIR / "port41_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"[OK] Manifest written to {manifest_path}")

    # Also create manifest.json as convenience alias
    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Clean up scratch staging directory so no duplicate source files linger in workspace
    if not keep_stage and STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)

    print("\nPORT-41 FULL BUILD COMPLETE.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Standard CHDK full build for G3 X GM1.10C")
    parser.add_argument("--no-clean", action="store_true", help="Do not clean staging directory before building")
    parser.add_argument("--keep-stage", action="store_true", help="Keep scratch staging directory after building")
    args = parser.parse_args()

    return build_port41_full(clean_stage=not args.no_clean, keep_stage=args.keep_stage)


if __name__ == "__main__":
    sys.exit(main())
