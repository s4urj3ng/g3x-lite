#!/usr/bin/env python3
"""PORT-40: Opt-in G3X_GUI5=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds opt-in G3X_GUI5=1 candidate DISKBOOT.BIN combining:
1. G3X_GUI5=1: Panel resolution (900x600 visible, stride 928) in compiled constants,
   exact match between menu fill rect and painted rect (880x576 at (10,12)-(889,587)),
   even 10-px horizontal and 12-px vertical margins on 900x600 LCD,
   solid opaque black background fill down to row 16,
   zero top or right edge leaks (UYVY even-word alignment),
   implying G3X_GUI4=1 (2x F1 font scaling, title bar white on black, zero-flicker idle, steps 8/9).
2. Combined G3X_GUI5=1 + G3X_SHORTPRESS=1: Combines the GUI5 layout fixes with the shortpress power-on fix.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_candidate_gui3 import (
    CANDIDATE_PORT40_GUI5_DIR,
    CANDIDATE_PORT40_GUI5_SHORTPRESS_DIR,
    build_candidate as build_candidate_gui,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-40: Opt-in G3X_GUI5=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--gui5",
        action="store_true",
        help="Build opt-in G3X_GUI5=1 plain candidate (default)",
    )
    group.add_argument(
        "--shortpress",
        "--combined",
        action="store_true",
        help="Build combined G3X_GUI5=1 + G3X_SHORTPRESS=1 candidate",
    )
    group.add_argument(
        "--default",
        action="store_true",
        help="Build default baseline candidate",
    )
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    if args.default:
        res = build_candidate_gui(ladder=False, poweron_fix=False, resident=False, out_dir=args.out_dir)
    elif args.shortpress:
        res = build_candidate_gui(gui5=True, shortpress=True, out_dir=args.out_dir)
    else:
        # Default action is --gui5
        res = build_candidate_gui(gui5=True, out_dir=args.out_dir)

    print(f"\nFinal DISKBOOT: {res['diskboot_bin']}")
    print(f"SHA-256:        {res['diskboot_sha256']}")
    print(f"Size:           {res['diskboot_size']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
