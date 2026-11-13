#!/usr/bin/env python3
"""PORT-44: G3X_GUI_DBUF=1 Double-Buffered Overlay with Lazy Runtime Heap Allocation.

Builds full CHDK for PowerShot G3 X (GM1.10C) with:
- G3X_GUI_FIX=1
- G3X_GUI_DBUF=1
- Runtime heap allocation for shadow buffer (outside BSS)
- Pinned toolchain: toolchains/gcc-arm-none-eabi-5_4-2016q3

Produces:
  out/port44-dbuf/DISKBOOT.BIN
  out/port44-dbuf/CHDK/ (MODULES, FONTS, LANG)
  out/port44-dbuf/port44_dbuf_manifest.json
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
DEFAULT_OUT_DIR = REPO_ROOT / "out" / "port44-dbuf"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_port43_dbuf import build_port43_dbuf, sha256_file  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="PORT-44 DBUF HEAP CHDK Full Build for PowerShot G3 X")
    parser.add_argument("--full-hooks", action="store_true", help="Enable FULL_HOOKS=1")
    parser.add_argument("--no-clean", action="store_true", help="Do not clean staging before building")
    parser.add_argument("--discard-stage", action="store_true", help="Remove stage directory after build")
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR), help="Custom output directory")
    args = parser.parse_args()

    ret = build_port43_dbuf(
        clean_stage=not args.no_clean,
        keep_stage=not args.discard_stage,
        full_hooks=args.full_hooks,
        out_dir=args.out_dir,
    )
    if ret != 0:
        return ret

    # Create PORT-44 manifest
    out_dir = Path(args.out_dir)
    diskboot = out_dir / "DISKBOOT.BIN"
    if diskboot.is_file():
        mpath_src = out_dir / "port43_dbuf_manifest.json"
        if mpath_src.is_file():
            with open(mpath_src, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["build"]["name"] = "port44_dbuf_heap"
            with open(out_dir / "port44_dbuf_manifest.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
