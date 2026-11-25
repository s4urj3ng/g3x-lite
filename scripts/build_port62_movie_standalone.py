#!/usr/bin/env python3
"""PORT-62 / PORT-63: Hermetic opt-in builder for the standalone movie candidate (G3X_MOVIE_STANDALONE=1).

Builds the minimal non-GUI movie time-limit + automatic continuation candidate
for PowerShot G3 X (GM1.10C) using a dedicated PORT-41-style hermetic staging copy
and the pinned toolchain:
  toolchains/gcc-arm-none-eabi-5_4-2016q3 via scripts/gcc_deterministic_wrapper.sh

Baseline integration commit (PORT-62):
  b718a92014b4a08f979d95347152642e596a10b4

Standalone policy (PORT-63):
  - Fixed compile-time budget of 50 automatic restart attempts per session
  - Dedicated clean staging copy under <out-dir>/stage_chdk (never reuses out/.port43_seed_stage,
    chdk-port/lib/core/.o2, or prebuilt libplatformsub.a from other profiles)
  - Preserves long ftell(FILE *file) outside core_spytask() #if/#else/#endif guard in staged core/main.c

Produces isolated final outputs under:
  build/port62-movie-standalone/DISKBOOT.BIN
  build/port62-movie-standalone/port62_movie_standalone_manifest.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "build" / "port62-movie-standalone"
PORT62_INTEGRATION_BASELINE_COMMIT = "b718a92014b4a08f979d95347152642e596a10b4"
STANDALONE_RESTART_BUDGET = 50

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_port43_dbuf import build_port43_dbuf  # type: ignore


def build_port62_movie_standalone(
    *,
    clean_stage: bool = True,
    keep_stage: bool = True,
    out_dir: Path | str = DEFAULT_OUT_DIR,
) -> int:
    return build_port43_dbuf(
        clean_stage=clean_stage,
        keep_stage=keep_stage,
        out_dir=out_dir,
        movie_standalone=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-62/63 Hermetic Standalone Movie Candidate Builder (G3X_MOVIE_STANDALONE=1) for PowerShot G3 X"
    )
    parser.add_argument("--no-clean", action="store_true", help="Accepted for CLI compatibility; standalone always stages hermetically")
    parser.add_argument("--discard-stage", action="store_true", help="Remove stage directory after build")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help="Isolated output directory (default: build/port62-movie-standalone)",
    )
    args = parser.parse_args()

    return build_port62_movie_standalone(
        clean_stage=not args.no_clean,
        keep_stage=not args.discard_stage,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
