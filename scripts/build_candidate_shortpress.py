#!/usr/bin/env python3
"""PORT-39: Opt-in G3X_SHORTPRESS=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds opt-in short-press power-on candidate DISKBOOT.BIN combining:
1. G3X_SHORTPRESS=1: Active-low physical switch override (bit 17 cleared &= ~0x00020000)
   in physw_status[0] during initial startup polls, with Playback vs Power boot discrimination
   via start-cause word at 0x00009BD0 (*(0x9BC4 + 12)).
   Hold duration of 700 polls (~7.0 s @ 10 ms/poll) covers the ~5 s LED ladder window
   (observed in PORT-38 trial) with ~2.0 s safety margin before releasing the override so a
   normal Power button press can turn off the camera.
   Implies G3X_RESIDENT=1, G3X_KBD=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. Combined G3X_SHORTPRESS=1 + G3X_GUI4=1: Combines the short-press fix with the complete
   GUI4 font (16x32 / advance 16), opaque black menu background (880x576), and high-contrast
   readable header.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
- All prior builds (RESIDENT, OSD, OSD2, KBD, GUI, GUI2, GUI3, GUI4) remain strictly byte-identical.
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
    G3X_GUI4_HEAP_START,
    CANDIDATE_PORT39_SHORTPRESS_GUI4_DIR,
    build_candidate as build_candidate_gui,
)
import build_candidate_port25_ladder_fix as legacy_builder


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-39: Opt-in G3X_SHORTPRESS=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--shortpress",
        action="store_true",
        help="Build opt-in G3X_SHORTPRESS=1 plain candidate (default)",
    )
    group.add_argument(
        "--gui5",
        action="store_true",
        help="Build combined G3X_SHORTPRESS=1 + G3X_GUI5=1 candidate",
    )
    group.add_argument(
        "--gui4",
        "--combined",
        action="store_true",
        help="Build combined G3X_SHORTPRESS=1 + G3X_GUI4=1 candidate",
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
    elif args.gui5:
        res = build_candidate_gui(gui5=True, shortpress=True, out_dir=args.out_dir)
    elif args.gui4:
        res = build_candidate_gui(gui4=True, shortpress=True, out_dir=args.out_dir)
    else:
        # Default action is --shortpress
        res = legacy_builder.build_candidate(shortpress=True, out_dir=args.out_dir)

    print(f"\nFinal DISKBOOT: {res['diskboot_bin']}")
    print(f"SHA-256:        {res['diskboot_sha256']}")
    print(f"Size:           {res['diskboot_size']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
