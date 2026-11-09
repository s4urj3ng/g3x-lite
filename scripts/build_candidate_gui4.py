#!/usr/bin/env python3
"""PORT-38: Opt-in G3X_GUI4=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic candidate DISKBOOT.BIN combining:
1. G3X_GUI4=1: CHDK GUI candidate fixing font scaling (F1: real 2x integer font 16x32 / advance 16 / row pitch 32 / direct font driver),
   background opacity (F3: solid opaque black background across full menu rectangle 880x576, opacity 255 into displayed opacity buffer),
   and title bar readability (contrasting white text on black background).
   Implies G3X_GUI3=1, G3X_GUI2=1, G3X_GUI=1, G3X_OSD2=1, G3X_KBD=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. G3X_GUI_DIAG=1: Valid with G3X_GUI4=1; keeps 1-px border (0,0)-(899,599) and 'dt= w= bw= h=' marker,
   drawn only as part of full menu repaints, never per tick.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
- All prior builds (RESIDENT, OSD, OSD2, KBD, GUI, GUI2, GUI3) remain strictly byte-identical.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_candidate_gui3 import (
    G3X_GUI4_HEAP_START,
    CANDIDATE_PORT38_GUI4_DIR,
    CANDIDATE_PORT38_GUI4_DIAG_DIR,
    build_candidate,
    generate_gui4_candidate_c,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-38: Opt-in G3X_GUI4=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui4", action="store_true", help="Build opt-in G3X_GUI4=1 candidate (default)")
    group.add_argument("--gui3", action="store_true", help="Build opt-in G3X_GUI3=1 candidate")
    group.add_argument("--gui2", action="store_true", help="Build opt-in G3X_GUI2=1 candidate")
    group.add_argument("--gui", action="store_true", help="Build opt-in G3X_GUI=1 candidate")
    group.add_argument("--osd2", action="store_true", help="Build opt-in G3X_OSD2=1 candidate")
    group.add_argument("--kbd", action="store_true", help="Build opt-in G3X_KBD=1 candidate")
    group.add_argument("--osd", action="store_true", help="Build opt-in G3X_OSD=1 candidate")
    group.add_argument("--resident", action="store_true", help="Build opt-in G3X_RESIDENT=1 candidate")
    group.add_argument("--combined", action="store_true", help="Build opt-in ladder + poweron fix candidate")
    group.add_argument("--default", action="store_true", help="Build default baseline candidate")
    parser.add_argument("--gui-diag", action="store_true", help="Include 1-px frame and marker under GUI4/GUI3")
    parser.add_argument("--shortpress", action="store_true", help="Include opt-in G3X_SHORTPRESS=1 short-press handling")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()
    shortpress = bool(args.shortpress or os.environ.get("G3X_SHORTPRESS", "0") == "1")

    if args.default:
        res = build_candidate(ladder=False, poweron_fix=False, resident=False, out_dir=args.out_dir)
    elif args.gui3:
        gui_diag = bool(args.gui_diag or os.environ.get("G3X_GUI_DIAG", "0") == "1")
        res = build_candidate(gui3=True, gui_diag=gui_diag, shortpress=shortpress, out_dir=args.out_dir)
    elif args.gui2:
        res = build_candidate(gui2=True, out_dir=args.out_dir)
    elif args.gui:
        res = build_candidate(gui=True, out_dir=args.out_dir)
    elif args.osd2:
        res = build_candidate(osd2=True, out_dir=args.out_dir)
    elif args.kbd:
        res = build_candidate(kbd=True, shortpress=shortpress, out_dir=args.out_dir)
    elif args.osd:
        res = build_candidate(osd=True, out_dir=args.out_dir)
    elif args.resident:
        res = build_candidate(resident=True, out_dir=args.out_dir)
    elif args.combined:
        res = build_candidate(ladder=True, poweron_fix=True, out_dir=args.out_dir)
    else:
        # Default action is --gui4
        gui_diag = bool(args.gui_diag or os.environ.get("G3X_GUI_DIAG", "0") == "1")
        res = build_candidate(gui4=True, gui_diag=gui_diag, shortpress=shortpress, out_dir=args.out_dir)

    print(f"\nFinal DISKBOOT: {res['diskboot_bin']}")
    print(f"SHA-256:        {res['diskboot_sha256']}")
    print(f"Size:           {res['diskboot_size']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
