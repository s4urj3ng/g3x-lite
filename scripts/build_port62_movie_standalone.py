#!/usr/bin/env python3
"""PORT-62: Dedicated opt-in builder for the standalone movie candidate (G3X_MOVIE_STANDALONE=1).

Builds the minimal non-GUI movie time-limit + automatic continuation candidate
for PowerShot G3 X (GM1.10C) using the pinned toolchain:
  toolchains/gcc-arm-none-eabi-5_4-2016q3 via scripts/gcc_deterministic_wrapper.sh

Produces isolated output under:
  build/port62-movie-standalone/DISKBOOT.BIN
  build/port62-movie-standalone/port62_movie_standalone_manifest.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "build" / "port62-movie-standalone"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_port43_dbuf import build_port43_dbuf  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-62 Standalone Movie Candidate Builder (G3X_MOVIE_STANDALONE=1) for PowerShot G3 X"
    )
    parser.add_argument("--no-clean", action="store_true", help="Do not clean staging before building")
    parser.add_argument("--discard-stage", action="store_true", help="Remove stage directory after build")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help="Isolated output directory (default: build/port62-movie-standalone)",
    )
    args = parser.parse_args()

    return build_port43_dbuf(
        clean_stage=not args.no_clean,
        keep_stage=not args.discard_stage,
        out_dir=args.out_dir,
        movie_standalone=True,
    )


if __name__ == "__main__":
    sys.exit(main())
