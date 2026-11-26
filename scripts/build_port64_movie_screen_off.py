#!/usr/bin/env python3
"""PORT-64: Hermetic opt-in builder for the standalone movie screen-off candidate (G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SCREEN_OFF=1).

Builds from the recorded PORT-63 integration commit (4f8c41dbad1d75382ab33c8c8371382a165d0491)
using its shared continuation controller (chdk-port/platform/g3x/sub/110c/movie_rec.c) and
hermetic staging approach with the pinned toolchain:
  toolchains/gcc-arm-none-eabi-5_4-2016q3 via scripts/gcc_deterministic_wrapper.sh

PORT-64 standalone policy (G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SCREEN_OFF=1):
  - Fixed compile-time budget of 50 automatic restart attempts per session
  - Deliberate movie-button start arming across shooting modes (playrec_mode in {2, 4, 5}),
    pre-recording transitional mr_rec_state polls ({2, 3, 4}), and same-poll IDLE -> RECORDING
    physical presses while preserving confirmed-IDLE provenance and rejecting unattributed starts
  - Bounded screen-off and restoration policy via research-verified TurnOffBackLight (0xFC37C449)
    and TurnOnBackLight (0xFC37C3EF) from mykbd_task resident-task context (100-poll / 1.0 s
    post-start settle delay, 3000-poll / 30.0 s bounded idempotent refresh capped at 120 calls
    per clip, edge-triggered KEY_DISPLAY 0x00001000 manual toggle with physw_status[0] masking,
    and guaranteed single-call TurnOnBackLight restoration on any non-recording / disarm / playback /
    reset transition)
  - Dedicated clean staging copy under <out-dir>/stage_chdk (never reuses out/.port43_seed_stage,
    chdk-port/lib/core/.o2, or prebuilt libplatformsub.a from other profiles)

Produces isolated final outputs under:
  build/port64-movie-screen-off/DISKBOOT.BIN
  build/port64-movie-screen-off/port64_movie_screen_off_manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
CHDK_PORT = REPO_ROOT / "chdk-port"
FULL_BUILD_SRC = REPO_ROOT / "full_build" / "g3x"
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
CROSS_COMPILE = str(TOOLCHAIN_BIN / "arm-none-eabi-")

DEFAULT_OUT_DIR = REPO_ROOT / "build" / "port64-movie-screen-off"

ORIGIN_MAIN_PORT61_COMMIT = "7e0f548f990bdd03d4eb0ec52bf2e11d7282f4e7"
PORT62_INTEGRATION_BASELINE_COMMIT = "b718a92014b4a08f979d95347152642e596a10b4"
PORT63_FIXES_COMMIT = "003facdc4ab64d0bc8320276432763af119b14de"
PORT63_INTEGRATION_TESTED_COMMIT = "e419648a152d9244d8faa01b47ca8e55fd885372"
PORT63_INTEGRATION_READY_COMMIT = "b713294e192a2ddd587c76d2c0018ff8add8e560"
PORT63_FINAL_INTEGRATION_COMMIT = "4f8c41dbad1d75382ab33c8c8371382a165d0491"
PORT64_RESEARCH_SCOPE_FIX_COMMIT = "4833a00570a4e5eb63a03208cc53f8905f16c233"
PORT64_RESEARCH_INTEGRATION_COMMIT = "4130de5ce8a513dee88cb426ed08a5d85d94b2f6"
PORT64_IMPLEMENT_SCOPE_FIX_ATTEMPT1_COMMIT = "4dcf5b5d58b7048ac06931598bed16103c5fec7f"
PORT54_EXCLUDED_COMMIT = "af2578089a39e9a2143f83003e92ea5236d542bc"

STANDALONE_RESTART_BUDGET = 50
SCREEN_OFF_DELAY_POLLS = 100
SCREEN_REFRESH_POLLS = 3000
SCREEN_MAX_REFRESH_CALLS = 120
TURNOFFBACKLIGHT_ADDR = "0xFC37C449"
TURNONBACKLIGHT_ADDR = "0xFC37C3EF"
KEY_DISPLAY_BIT = "0x00001000"

sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_port41_full import overlay_tree, sha256_file  # type: ignore
from build_port43_dbuf import (  # type: ignore
    _clean_standalone_staging_artifacts,
    apply_movie_standalone_staging_patches,
)


def apply_port64_movie_screen_off_staging_patches(stage_dir: Path) -> None:
    """Apply PORT-64 standalone screen-off + deliberate-start arming staging patches on top of PORT-63 standalone staging."""
    apply_movie_standalone_staging_patches(stage_dir)

    shutil.copy2(
        CHDK_PORT / "platform/g3x/sub/110c/movie_rec.c",
        stage_dir / "platform/g3x/sub/110c/movie_rec.c",
    )
    shutil.copy2(
        CHDK_PORT / "platform/g3x/sub/110c/makefile.inc",
        stage_dir / "platform/g3x/sub/110c/makefile.inc",
    )

    # Patch staged platform/g3x/movie_status.h with G3X_MOVIE_SCREEN_OFF=1 compile-time guard and prototypes
    staged_status_h = stage_dir / "platform/g3x/movie_status.h"
    if staged_status_h.is_file():
        sh_text = staged_status_h.read_text(encoding="utf-8")
        if "G3X_MOVIE_SCREEN_OFF" not in sh_text:
            screen_off_guard = (
                "#if defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)\n"
                "#if !defined(G3X_MOVIE_STANDALONE) || (G3X_MOVIE_STANDALONE != 1) || \\\n"
                "    !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1) || \\\n"
                "    !defined(G3X_MOVIE_RESTART_BUDGET) || (G3X_MOVIE_RESTART_BUDGET != 1) || \\\n"
                "    !defined(G3X_MOVIE_NOLIMIT) || (G3X_MOVIE_NOLIMIT != 1) || \\\n"
                "    !defined(G3X_MOVIE_AUTOCONT) || (G3X_MOVIE_AUTOCONT != 1) || \\\n"
                "    !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1)\n"
                "#error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1\n"
                "#endif\n"
                "#if defined(G3X_MOVIE_AUTOCONT_UI) && (G3X_MOVIE_AUTOCONT_UI == 1)\n"
                "#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1\n"
                "#endif\n"
                "#if (defined(G3X_GUI5) && (G3X_GUI5 == 1)) || \\\n"
                "    (defined(G3X_GUI_FIX) && (G3X_GUI_FIX == 1)) || \\\n"
                "    (defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)) || \\\n"
                "    (defined(G3X_GUI_NOOVERDRAW) && (G3X_GUI_NOOVERDRAW == 1)) || \\\n"
                "    (defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)) || \\\n"
                "    (defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)) || \\\n"
                "    (defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)) || \\\n"
                "    (defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)) || \\\n"
                "    (defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
                "    (defined(G3X_GUI_RESTORE2) && (G3X_GUI_RESTORE2 == 1)) || \\\n"
                "    (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))\n"
                "#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags\n"
                "#endif\n"
                "#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)\n"
                "#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1\n"
                "#endif\n"
                "#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)\n"
                "#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with FULL_HOOKS=1\n"
                "#endif\n"
                "#endif\n\n"
            )
            anchor = "#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)"
            if anchor not in sh_text:
                raise RuntimeError("PORT-64 movie_status.h anchor not found")
            sh_text = sh_text.replace(anchor, screen_off_guard + anchor, 1)
            staged_status_h.write_text(sh_text, encoding="utf-8")

    prereq = (
        "ifeq ($(G3X_MOVIE_SCREEN_OFF),1)\n"
        "ifneq ($(G3X_MOVIE_STANDALONE),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_SESSION_CANCEL),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_RESTART_BUDGET),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_NOLIMIT),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_AUTOCONT),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_STATUS),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1)\n"
        "endif\n"
        "ifeq ($(G3X_MOVIE_AUTOCONT_UI),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1)\n"
        "endif\n"
        "ifeq ($(G3X_GUI5),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_FIX),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_DBUF),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_NOOVERDRAW),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_KBD_CHECK),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_DIAG),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_SHADOW2),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_SYNC),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_MENU),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_GUI_RESTORE2),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_PLAYBACK_MENU),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags)\n"
        "endif\n"
        "ifeq ($(G3X_CONF_SAVE),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1)\n"
        "endif\n"
        "ifeq ($(FULL_HOOKS),1)\n"
        "$(error G3X_MOVIE_SCREEN_OFF=1 is incompatible with FULL_HOOKS=1)\n"
        "endif\n"
        "endif\n\n"
    )
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "ifeq ($(G3X_MOVIE_SCREEN_OFF),1)" not in text:
            text = prereq + text
        if "-DG3X_MOVIE_SCREEN_OFF=1" not in text:
            if "-DG3X_MOVIE_STANDALONE=1" in text:
                text = text.replace(
                    "-DG3X_MOVIE_STANDALONE=1",
                    "-DG3X_MOVIE_STANDALONE=1 -DG3X_MOVIE_SCREEN_OFF=1",
                    1,
                )
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_SCREEN_OFF=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_SCREEN_OFF=1\n"
        mpath.write_text(text, encoding="utf-8")


def build_port64_movie_screen_off(
    *,
    clean_stage: bool = True,
    keep_stage: bool = True,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    without_movie_standalone: bool = False,
    conf_save: bool = False,
    full_hooks: bool = False,
    movie_autocont_ui: bool = False,
    gui_flag: bool = False,
    alone_flag: bool = False,
) -> int:
    _ = clean_stage
    if without_movie_standalone or alone_flag:
        print(
            "ERROR: G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1",
            file=sys.stderr,
        )
        return 1
    if conf_save:
        print("ERROR: G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1", file=sys.stderr)
        return 1
    if full_hooks:
        print("ERROR: G3X_MOVIE_SCREEN_OFF=1 is incompatible with FULL_HOOKS=1", file=sys.stderr)
        return 1
    if movie_autocont_ui:
        print("ERROR: G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1", file=sys.stderr)
        return 1
    if gui_flag:
        print("ERROR: G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags", file=sys.stderr)
        return 1

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

    effective_out_dir = Path(out_dir).resolve()
    effective_stage_dir = effective_out_dir / "stage_chdk"

    effective_out_dir.mkdir(parents=True, exist_ok=True)
    # Write local .gitignore so build outputs remain on disk in build/port64-movie-screen-off/
    # without staging forbidden binaries into git ls-files.
    (effective_out_dir / ".gitignore").write_text("*\n", encoding="utf-8")

    # Clean stale outputs in effective_out_dir before building
    for stale_name in (
        "DISKBOOT.BIN",
        "port64_movie_screen_off_manifest.json",
        "port62_movie_standalone_manifest.json",
        "manifest.json",
    ):
        stale_path = effective_out_dir / stale_name
        if stale_path.is_file():
            stale_path.unlink()
    stale_chdk = effective_out_dir / "CHDK"
    if stale_chdk.exists():
        shutil.rmtree(stale_chdk)
    for stale_manifest in effective_out_dir.glob("*_manifest.json"):
        if stale_manifest.is_file():
            stale_manifest.unlink()

    # Hermetic PORT-63-style dedicated staging copy directly from CHDK_PORT
    if effective_stage_dir.exists():
        subprocess.run(["chmod", "-R", "u+w", str(effective_stage_dir)], check=False)
        shutil.rmtree(effective_stage_dir)
    print(f"Staging hermetic CHDK tree to {effective_stage_dir}...")
    shutil.copytree(CHDK_PORT, effective_stage_dir, symlinks=True)
    _clean_standalone_staging_artifacts(effective_stage_dir)

    platform_target = effective_stage_dir / "platform" / "g3x"
    print(f"Overlaying {FULL_BUILD_SRC} onto {platform_target}...")
    overlay_tree(FULL_BUILD_SRC, platform_target, ignore={"loader"})

    loader_target = effective_stage_dir / "loader" / "g3x"
    loader_src = FULL_BUILD_SRC / "loader"
    if loader_src.is_dir():
        print(f"Overlaying {loader_src} onto {loader_target}...")
        overlay_tree(loader_src, loader_target)

    dbuf_menu = CHDK_PORT / "platform" / "g3x" / "gui_menu.c"
    if dbuf_menu.is_file():
        shutil.copy2(dbuf_menu, platform_target / "gui_menu.c")

    for proto_name in ["boot_prototype.c", "stubs_prototype.S"]:
        proto_file = platform_target / "sub" / "110c" / proto_name
        if proto_file.exists():
            proto_file.unlink()

    print("G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SCREEN_OFF=1: Applying PORT-64 standalone screen-off + deliberate-start arming patches...")
    apply_port64_movie_screen_off_staging_patches(effective_stage_dir)

    _clean_standalone_staging_artifacts(effective_stage_dir)
    tools_build_cmd = [
        "make",
        "-C",
        str(effective_stage_dir / "tools"),
        "dancingbits",
        "makeexport",
        "font_8x16_pack",
    ]
    tools_res = subprocess.run(tools_build_cmd, cwd=str(effective_stage_dir))
    if tools_res.returncode != 0:
        print(f"ERROR: Host tools build failed with exit code {tools_res.returncode}", file=sys.stderr)
        return tools_res.returncode

    clean_subpaths = [
        "lib/armutil",
        "lib/math",
        "lib/lang",
        "lib/font",
        "lib/core",
        "platform/g3x",
        "platform/g3x/sub/110c",
        "loader/g3x",
    ]
    make_flags = [
        "PLATFORM=g3x",
        "PLATFORMSUB=110c",
        "G3X_FULL_BUILD=1",
        "G3X_DISABLE_CARD_WRITES=1",
        "OPT_DISABLE_FILE_WRITES=1",
        "G3X_MOVIE_STANDALONE=1",
        "G3X_MOVIE_SCREEN_OFF=1",
        "G3X_MOVIE_STATUS=1",
        "G3X_MOVIE_NOLIMIT=1",
        "G3X_MOVIE_AUTOCONT=1",
        "G3X_MOVIE_RESTART_BUDGET=1",
        "G3X_MOVIE_SESSION_CANCEL=1",
    ]
    for subpath in clean_subpaths:
        p = effective_stage_dir / subpath
        if p.is_dir():
            subprocess.run(
                ["make", "-C", str(p), *make_flags, "clean"],
                cwd=str(effective_stage_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    cmd = [
        "make",
        "-C",
        str(effective_stage_dir),
        *make_flags,
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
        "SKIP_TOOLS=1",
        "SKIP_MODULES=1",
        "SKIP_CHDK=1",
        "fir",
    ]
    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    gcc_tmp = REPO_ROOT / "out" / ".tmp_gcc"
    gcc_tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(gcc_tmp)
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if "MAKEFLAGS" not in env and wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    for flag_kv in make_flags[2:]:
        k, v = flag_kv.split("=", 1)
        env[k] = v

    res = subprocess.run(cmd, cwd=str(effective_stage_dir), env=env)
    shutil.rmtree(gcc_tmp, ignore_errors=True)
    if res.returncode != 0:
        print(f"ERROR: Build failed with exit code {res.returncode}", file=sys.stderr)
        return res.returncode

    stage_diskboot = effective_stage_dir / "bin" / "DISKBOOT.BIN"
    if not stage_diskboot.is_file() or stage_diskboot.stat().st_size == 0:
        print(f"ERROR: Expected output missing or empty: {stage_diskboot}", file=sys.stderr)
        return 1

    out_diskboot = effective_out_dir / "DISKBOOT.BIN"
    shutil.copy2(stage_diskboot, out_diskboot)
    print(f"[OK] Generated {out_diskboot} ({out_diskboot.stat().st_size} bytes)")

    out_chdk = effective_out_dir / "CHDK"
    if out_chdk.exists():
        shutil.rmtree(out_chdk)

    nm_bin = TOOLCHAIN_BIN / "arm-none-eabi-nm"
    main_elf = effective_stage_dir / "platform" / "g3x" / "sub" / "110c" / "main.elf"
    nm_out = subprocess.check_output([str(nm_bin), str(main_elf)], text=True)
    core_end_hex = None
    for line in nm_out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == "_end":
            core_end_hex = f"0x{int(parts[0], 16):08x}"
            break
    if core_end_hex is None:
        raise RuntimeError("Could not find _end symbol in staged main.elf")

    build_flags = [
        "G3X_FULL_BUILD=1",
        "G3X_DISABLE_CARD_WRITES=1",
        "OPT_DISABLE_FILE_WRITES=1",
        "G3X_MOVIE_STANDALONE=1",
        "G3X_MOVIE_SCREEN_OFF=1",
        "G3X_MOVIE_STATUS=1",
        "G3X_MOVIE_NOLIMIT=1",
        "G3X_MOVIE_AUTOCONT=1",
        "G3X_MOVIE_RESTART_BUDGET=1",
        "G3X_MOVIE_SESSION_CANCEL=1",
    ]
    diskboot_sha256 = sha256_file(out_diskboot)
    diskboot_size = out_diskboot.stat().st_size

    manifest_data: dict[str, object] = {
        "manifest_id": "port64_movie_screen_off_manifest",
        "milestone": "PORT-64",
        "origin_main_baseline": ORIGIN_MAIN_PORT61_COMMIT,
        "candidate_source_base": PORT63_FINAL_INTEGRATION_COMMIT,
        "port62_integration_baseline": PORT62_INTEGRATION_BASELINE_COMMIT,
        "port63_fixes_commit": PORT63_FIXES_COMMIT,
        "port63_integration_tested_revision": PORT63_INTEGRATION_TESTED_COMMIT,
        "port63_integration_ready_commit": PORT63_INTEGRATION_READY_COMMIT,
        "port63_final_integration_commit": PORT63_FINAL_INTEGRATION_COMMIT,
        "port64_research_scope_fix_commit": PORT64_RESEARCH_SCOPE_FIX_COMMIT,
        "port64_research_integration_commit": PORT64_RESEARCH_INTEGRATION_COMMIT,
        "port64_implement_scope_fix_attempt1_commit": PORT64_IMPLEMENT_SCOPE_FIX_ATTEMPT1_COMMIT,
        "reused_commits": {
            "origin_main_port61": ORIGIN_MAIN_PORT61_COMMIT,
            "port62_integration_baseline": PORT62_INTEGRATION_BASELINE_COMMIT,
            "port63_fixes": PORT63_FIXES_COMMIT,
            "port63_integration_tested": PORT63_INTEGRATION_TESTED_COMMIT,
            "port63_integration_ready": PORT63_INTEGRATION_READY_COMMIT,
            "port63_final_integration": PORT63_FINAL_INTEGRATION_COMMIT,
            "port64_research_scope_fix": PORT64_RESEARCH_SCOPE_FIX_COMMIT,
            "port64_research_integration": PORT64_RESEARCH_INTEGRATION_COMMIT,
            "port64_implement_scope_fix_attempt1": PORT64_IMPLEMENT_SCOPE_FIX_ATTEMPT1_COMMIT,
        },
        "excluded_commits": {
            "port54_conf_save": PORT54_EXCLUDED_COMMIT,
        },
        "build": {
            "platform": "g3x",
            "platform_sub": "110c",
            "flags": build_flags,
            "toolchain": "gcc-arm-none-eabi-5_4-2016q3",
            "deterministic_wrapper": "scripts/gcc_deterministic_wrapper.sh",
            "card_writes": "disabled",
            "card_writes_note": (
                "Config save disabled under G3X_DISABLE_CARD_WRITES=1 OPT_DISABLE_FILE_WRITES=1 "
                "(SAVE:OFF); blocking write wrappers (write, fwrite, open, fopen, creat, mkdir, remove, rename) remain active in link; physical SD card remains write-protected (LOCK)"
            ),
        },
        "artifacts": {
            "DISKBOOT.BIN": {
                "path": "DISKBOOT.BIN",
                "size": diskboot_size,
                "sha256": diskboot_sha256,
            },
            "modules_count": 0,
            "modules": {},
            "chdk_files_count": 0,
            "chdk_files": {},
            "core_end": core_end_hex,
            "_end": core_end_hex,
        },
        "core_end": core_end_hex,
        "_end": core_end_hex,
        "card_writes": "disabled",
        "card_writes_note": (
            "Config save disabled under G3X_DISABLE_CARD_WRITES=1 OPT_DISABLE_FILE_WRITES=1 "
            "(SAVE:OFF); blocking write wrappers (write, fwrite, open, fopen, creat, mkdir, remove, rename) remain active in link; physical SD card remains write-protected (LOCK)"
        ),
        "standalone_policy": {
            "boot_enabled": True,
            "gui_dependencies": False,
            "alt_mode_dependencies": False,
            "chdk_dir_dependency": False,
            "modules_required": 0,
            "default_restart_budget": STANDALONE_RESTART_BUDGET,
            "fixed_compile_time_restart_budget": STANDALONE_RESTART_BUDGET,
            "eligible_stop_reasons": [3, 4],
            "deliberate_start_arming_across_shooting_modes": True,
            "shooting_mode_playrec_values": [2, 4, 5],
            "transitional_pre_record_states_supported": [2, 3, 4],
            "same_poll_idle_to_recording_physical_press_supported": True,
            "confirmed_idle_provenance_required": True,
            "already_recording_without_deliberate_intent_rejected": True,
            "physical_stop_latches_session_cancellation": True,
            "rearm_requires_deliberate_physical_start_after_confirmed_idle": True,
            "synthetic_events_excluded_from_deliberate_start_and_budget_reset": True,
            "failed_attempts_consume_budget_without_refund": True,
            "releases_only_continuation_owned_synthetic_keys": True,
            "shortpress_poweron_fix_preserved": True,
            "port56_duration_patch_preserved": True,
            "hermetic_staging": True,
        },
        "screen_off_policy": {
            "supported": True,
            "evidence_manifest": "docs/port34_evidence_manifest.json",
            "evidence_ids": [
                "PORT64-ROM-BACKLIGHT-CORE-WINDOW",
                "PORT64-ROM-DISPCON-BACKLIGHT-WINDOW",
            ],
            "turn_off_backlight_symbol": "TurnOffBackLight",
            "turn_off_backlight_target": "_TurnOffBackLight",
            "turn_off_backlight_address": TURNOFFBACKLIGHT_ADDR,
            "turn_on_backlight_symbol": "TurnOnBackLight",
            "turn_on_backlight_target": "_TurnOnBackLight",
            "turn_on_backlight_address": TURNONBACKLIGHT_ADDR,
            "execution_context": "mykbd_task (DryOS resident task context, 10 ms poll via my_kbd_read_keys -> g3x_movie_autocont_poll)",
            "post_start_settle_delay_polls": SCREEN_OFF_DELAY_POLLS,
            "post_start_settle_delay_ms": SCREEN_OFF_DELAY_POLLS * 10,
            "periodic_refresh_interval_polls": SCREEN_REFRESH_POLLS,
            "periodic_refresh_interval_ms": SCREEN_REFRESH_POLLS * 10,
            "max_periodic_refresh_calls_per_clip": SCREEN_MAX_REFRESH_CALLS,
            "manual_toggle_key_symbol": "KEY_DISPLAY",
            "manual_toggle_key_bit": KEY_DISPLAY_BIT,
            "masks_consumed_display_key_in_physw_status0": True,
            "restores_backlight_once_on_disarm_non_recording_playback_or_reset": True,
            "runtime_canon_wake_behavior": "UNVERIFIED / UNKNOWN",
        },
        "command": (
            "python3 -B scripts/build_port64_movie_screen_off.py --out-dir build/port64-movie-screen-off"
        ),
        "configurations": {
            "default": {
                "path": "out/build-default/DISKBOOT.BIN",
                "size": 124097,
                "sha256": "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
                "_end": "0x003686b0",
                "card_writes": "disabled",
            },
            "port59_movie_combined": {
                "path": "out/port59-movie-combined/DISKBOOT.BIN",
                "size": 134801,
                "sha256": "a29bd5d3aae297cbbdb34eae0cb6d96b5f804e4e3b4fea03304b0a34cc4d8fbf",
                "_end": "0x0036b4d0",
                "card_writes": "disabled",
            },
            "port60_movie_restart_budget": {
                "path": "out/port60-movie-restart-budget/DISKBOOT.BIN",
                "size": 135313,
                "sha256": "5bb1b93b0a3246ab5e37c689daa223dd2c6a9e3e84a53956678992b97be00a90",
                "_end": "0x0036b6e0",
                "card_writes": "disabled",
            },
            "port61_movie_session_cancel": {
                "path": "out/port61-movie-session-cancel/DISKBOOT.BIN",
                "size": 135969,
                "sha256": "2612eea17c83dc64f9f6579b59771aa7313e931bb0b7ea47118ad8c6512e1f68",
                "_end": "0x0036b970",
                "card_writes": "disabled",
            },
            "port62_63_movie_standalone": {
                "path": "build/port62-movie-standalone/DISKBOOT.BIN",
                "size": 126529,
                "sha256": "fdef85dbe1703ea4ea9eea3df261bd803c99e7b689041feee918f990f7dc9eb9",
                "_end": "0x00369070",
                "card_writes": "disabled",
            },
            "port64_movie_screen_off": {
                "path": "build/port64-movie-screen-off/DISKBOOT.BIN",
                "size": diskboot_size,
                "sha256": diskboot_sha256,
                "_end": core_end_hex,
                "card_writes": "disabled",
            },
        },
    }

    manifest_path = effective_out_dir / "port64_movie_screen_off_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Wrote manifest: {manifest_path}")

    if not keep_stage and effective_stage_dir.exists():
        subprocess.run(["chmod", "-R", "u+w", str(effective_stage_dir)], check=False)
        shutil.rmtree(effective_stage_dir)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-64 Hermetic Standalone Movie Screen-Off Candidate Builder (G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SCREEN_OFF=1) for PowerShot G3 X"
    )
    parser.add_argument("--no-clean", action="store_true", help="Accepted for CLI compatibility; standalone always stages hermetically")
    parser.add_argument("--discard-stage", action="store_true", help="Remove stage directory after build")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help="Isolated output directory (default: build/port64-movie-screen-off)",
    )
    parser.add_argument("--without-movie-standalone", action="store_true", help="Negative test flag: omit G3X_MOVIE_STANDALONE=1")
    parser.add_argument("--conf-save", action="store_true", help="Negative test flag: incompatible G3X_CONF_SAVE=1")
    parser.add_argument("--full-hooks", action="store_true", help="Negative test flag: incompatible FULL_HOOKS=1")
    parser.add_argument("--movie-autocont-ui", action="store_true", help="Negative test flag: incompatible G3X_MOVIE_AUTOCONT_UI=1")
    parser.add_argument("--movie-combined", action="store_true", help="Negative test flag: incompatible GUI movie profile")
    parser.add_argument("--movie-budget-profile", action="store_true", help="Negative test flag: incompatible GUI budget profile")
    parser.add_argument("--movie-cancel-profile", action="store_true", help="Negative test flag: incompatible GUI cancel profile")
    parser.add_argument("--gui-menu", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--gui-sync", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--shadow2", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--gui-diag", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--kbd-check", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--no-overdraw", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--gui-restore2", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--playback-menu", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--playback-menu-alone", action="store_true", help="Negative test flag: incompatible GUI flag")
    parser.add_argument("--movie-nolimit-alone", action="store_true", help="Negative test flag: missing standalone prerequisites")
    parser.add_argument("--movie-autocont-alone", action="store_true", help="Negative test flag: missing standalone prerequisites")
    parser.add_argument("--movie-status-alone", action="store_true", help="Negative test flag: missing standalone prerequisites")
    args = parser.parse_args()

    return build_port64_movie_screen_off(
        clean_stage=not args.no_clean,
        keep_stage=not args.discard_stage,
        out_dir=args.out_dir,
        without_movie_standalone=args.without_movie_standalone,
        conf_save=args.conf_save,
        full_hooks=args.full_hooks,
        movie_autocont_ui=(
            args.movie_autocont_ui
            or args.movie_combined
            or args.movie_budget_profile
            or args.movie_cancel_profile
        ),
        gui_flag=(
            args.gui_menu
            or args.gui_sync
            or args.shadow2
            or args.gui_diag
            or args.kbd_check
            or args.no_overdraw
            or args.gui_restore2
            or args.playback_menu
            or args.playback_menu_alone
        ),
        alone_flag=(
            args.movie_nolimit_alone
            or args.movie_autocont_alone
            or args.movie_status_alone
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
