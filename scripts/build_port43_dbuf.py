#!/usr/bin/env python3
"""PORT-43: G3X_GUI_DBUF=1 Double-Buffered Overlay, Fast Fills, Partial Redraw, Shadow Restore.

Builds full CHDK for PowerShot G3 X (GM1.10C) with:
- G3X_GUI_FIX=1
- G3X_GUI_DBUF=1
- Pinned toolchain: toolchains/gcc-arm-none-eabi-5_4-2016q3

Produces:
  out/port43-dbuf/DISKBOOT.BIN
  out/port43-dbuf/CHDK/ (MODULES, FONTS, LANG)
  out/port43-dbuf/port43_dbuf_manifest.json
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

OUT_DIR = REPO_ROOT / "out" / "port43-dbuf"
STAGE_DIR = OUT_DIR / "stage_chdk"

sys.path.insert(0, str(REPO_ROOT / "tools"))
from build_port41_full import (  # type: ignore
    apply_full_hooks_staging_patches,
    apply_gui_fix_staging_patches,
    clean_staging_artifacts,
    overlay_tree,
    sha256_file,
)


def apply_dbuf_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_DBUF=1 compile flags to staging makefiles and DBUF scheduler patch to core/main.c."""
    for mpath in [
        stage_dir / "platform" / "g3x" / "Makefile",
        stage_dir / "platform" / "g3x" / "sub" / "110c" / "Makefile",
    ]:
        if mpath.is_file():
            mtext = mpath.read_text(encoding="utf-8")
            if "-DG3X_GUI_DBUF=1" not in mtext:
                if "-DG3X_GUI_FIX=1" in mtext:
                    mtext = mtext.replace(
                        "-DG3X_GUI_FIX=1",
                        "-DG3X_GUI_FIX=1 -DG3X_GUI_DBUF=1",
                        1,
                    )
                else:
                    mtext = mtext.replace(
                        "CFLAGS += -DG3X_FULL_BUILD=1",
                        "CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_GUI_FIX=1 -DG3X_GUI_DBUF=1",
                        1,
                    )
                mpath.write_text(mtext, encoding="utf-8")

    # Patch core/main.c scheduler for G3X_GUI_DBUF=1:
    # Under DBUF, a flip with intact sentinels in both opacity buffers causes NO redraw.
    # Only a lost sentinel triggers restoration, and that is a single shadow blit, NOT gui_redraw.
    core_main_c = stage_dir / "core" / "main.c"
    if core_main_c.is_file():
        cm_text = core_main_c.read_text(encoding="utf-8")
        port42_scheduler = (
            "            gui_maintenance_tick();\n"
            "            int forced = check_gui_needs_redraw();\n"
            "            int sentinel_lost = !draw_test_guard();\n"
            "            int buffer_changed = check_bitmap_buffer_changed();\n"
            "            int state_changed = gui_check_state_changed();\n"
            "            int need_redraw = forced || sentinel_lost || buffer_changed || state_changed;\n"
            "            if (need_redraw)\n"
            "                gui_redraw(forced || sentinel_lost || buffer_changed);\n"
            "            else if (gui_is_osd_mode())\n"
            "                gui_draw_osd_tick();\n"
            "            else if (gui_is_module_mode())\n"
            "                gui_draw_module_tick();"
        )
        dbuf_scheduler = (
            "            /* PORT-43 DBUF GUI scheduler:\n"
            "             * Double-buffered overlay: buffer flip causes NO redraw when sentinels in both opacity buffers are intact.\n"
            "             * Only a lost sentinel triggers restoration, and that is a single fast shadow blit, NOT gui_redraw.\n"
            "             * Sentinel loss triggers shadow restore ONLY when the shadow is valid AND a CHDK overlay layer is currently active (not in defaultGuiHandler/live view).\n"
            "             * Navigation and state changes trigger partial gui_redraw without enforce_redraw (redraw=1). */\n"
            "            extern int g3x_dbuf_shadow_restore(void);\n"
            "            extern int g3x_shadow_valid;\n"
            "\n"
            "            gui_maintenance_tick();\n"
            "            (void)check_bitmap_buffer_changed();\n"
            "            int forced = check_gui_needs_redraw();\n"
            "            int chdk_overlay_active = !camera_info.state.gui_mode_none;\n"
            "            if (!draw_test_guard() && chdk_overlay_active)\n"
            "            {\n"
            "                if (!g3x_shadow_valid || !g3x_dbuf_shadow_restore())\n"
            "                {\n"
            "                    forced = 1;\n"
            "                }\n"
            "            }\n"
            "            int state_changed = gui_check_state_changed();\n"
            "            int need_redraw = forced || state_changed;\n"
            "            if (need_redraw)\n"
            "                gui_redraw(forced);\n"
            "            else if (gui_is_osd_mode())\n"
            "                gui_draw_osd_tick();\n"
            "            else if (gui_is_module_mode())\n"
            "                gui_draw_module_tick();"
        )
        if port42_scheduler in cm_text:
            cm_text = cm_text.replace(port42_scheduler, dbuf_scheduler, 1)
            core_main_c.write_text(cm_text, encoding="utf-8")
        else:
            raise RuntimeError("PORT-42 scheduler anchor not found in staged core/main.c")


def apply_no_overdraw_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_NOOVERDRAW=1 compile flags, multi-point sentinel check, and NOOVERDRAW scheduler."""
    for mpath in [
        stage_dir / "platform" / "g3x" / "Makefile",
        stage_dir / "platform" / "g3x" / "sub" / "110c" / "Makefile",
    ]:
        if mpath.is_file():
            mtext = mpath.read_text(encoding="utf-8")
            if "-DG3X_GUI_NOOVERDRAW=1" not in mtext:
                if "-DG3X_GUI_DBUF=1" in mtext:
                    mtext = mtext.replace(
                        "-DG3X_GUI_DBUF=1",
                        "-DG3X_GUI_DBUF=1 -DG3X_GUI_NOOVERDRAW=1",
                        1,
                    )
                else:
                    mtext = mtext.replace(
                        "CFLAGS += -DG3X_FULL_BUILD=1",
                        "CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_GUI_FIX=1 -DG3X_GUI_DBUF=1 -DG3X_GUI_NOOVERDRAW=1",
                        1,
                    )
                mpath.write_text(mtext, encoding="utf-8")

    # 1. Multi-point perimeter sentinels in core/gui_draw.c
    core_draw_c = stage_dir / "core" / "gui_draw.c"
    if core_draw_c.is_file():
        cd_text = core_draw_c.read_text(encoding="utf-8")
        port44_guards = (
            "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
            "void draw_set_guard(void)\n"
            "{\n"
            "    opacity_buffer[0][0] = 0x42;\n"
            "    opacity_buffer[1][0] = 0x42;\n"
            "}\n"
            "\n"
            "int draw_test_guard(void)\n"
            "{\n"
            "    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42) return 0;\n"
            "    return 1;\n"
            "}\n"
            "#else"
        )
        nooverdraw_guards = (
            "#if defined(G3X_GUI_NOOVERDRAW) && (G3X_GUI_NOOVERDRAW == 1)\n"
            "/* PORT-45: Multi-point perimeter sentinels: (0,0) and 4 menu corners:\n"
            " * (G3X_MENU_X0, G3X_MENU_Y0) = (10, 12)\n"
            " * (G3X_MENU_X1, G3X_MENU_Y0) = (889, 12)\n"
            " * (G3X_MENU_X0, G3X_MENU_Y1) = (10, 587)\n"
            " * (G3X_MENU_X1, G3X_MENU_Y1) = (889, 587)\n"
            " */\n"
            "void draw_set_guard(void)\n"
            "{\n"
            "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
            "    unsigned int offsets[5] = {\n"
            "        0,\n"
            "        (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X0),\n"
            "        (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X1),\n"
            "        (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X0),\n"
            "        (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X1)\n"
            "    };\n"
            "    for (int i = 0; i < 5; i++) {\n"
            "        opacity_buffer[0][offsets[i]] = 0x42;\n"
            "        opacity_buffer[1][offsets[i]] = 0x42;\n"
            "    }\n"
            "}\n"
            "\n"
            "int draw_test_guard(void)\n"
            "{\n"
            "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
            "    unsigned int offsets[5] = {\n"
            "        0,\n"
            "        (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X0),\n"
            "        (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X1),\n"
            "        (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X0),\n"
            "        (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X1)\n"
            "    };\n"
            "    for (int i = 0; i < 5; i++) {\n"
            "        if (opacity_buffer[0][offsets[i]] != 0x42 || opacity_buffer[1][offsets[i]] != 0x42)\n"
            "            return 0;\n"
            "    }\n"
            "    return 1;\n"
            "}\n"
            "#elif defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
            "void draw_set_guard(void)\n"
            "{\n"
            "    opacity_buffer[0][0] = 0x42;\n"
            "    opacity_buffer[1][0] = 0x42;\n"
            "}\n"
            "\n"
            "int draw_test_guard(void)\n"
            "{\n"
            "    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42) return 0;\n"
            "    return 1;\n"
            "}\n"
            "#else"
        )
        if port44_guards in cd_text:
            cd_text = cd_text.replace(port44_guards, nooverdraw_guards, 1)
            core_draw_c.write_text(cd_text, encoding="utf-8")
        else:
            raise RuntimeError("PORT-44 guard anchor not found in staged core/gui_draw.c")

    # 2. Patch stage_chdk/core/main.c scheduler for G3X_GUI_NOOVERDRAW=1
    core_main_c = stage_dir / "core" / "main.c"
    if core_main_c.is_file():
        cm_text = core_main_c.read_text(encoding="utf-8")
        dbuf_scheduler = (
            "            /* PORT-43 DBUF GUI scheduler:\n"
            "             * Double-buffered overlay: buffer flip causes NO redraw when sentinels in both opacity buffers are intact.\n"
            "             * Only a lost sentinel triggers restoration, and that is a single fast shadow blit, NOT gui_redraw.\n"
            "             * Sentinel loss triggers shadow restore ONLY when the shadow is valid AND a CHDK overlay layer is currently active (not in defaultGuiHandler/live view).\n"
            "             * Navigation and state changes trigger partial gui_redraw without enforce_redraw (redraw=1). */\n"
            "            extern int g3x_dbuf_shadow_restore(void);\n"
            "            extern int g3x_shadow_valid;\n"
            "\n"
            "            gui_maintenance_tick();\n"
            "            (void)check_bitmap_buffer_changed();\n"
            "            int forced = check_gui_needs_redraw();\n"
            "            int chdk_overlay_active = !camera_info.state.gui_mode_none;\n"
            "            if (!draw_test_guard() && chdk_overlay_active)\n"
            "            {\n"
            "                if (!g3x_shadow_valid || !g3x_dbuf_shadow_restore())\n"
            "                {\n"
            "                    forced = 1;\n"
            "                }\n"
            "            }\n"
            "            int state_changed = gui_check_state_changed();\n"
            "            int need_redraw = forced || state_changed;\n"
            "            if (need_redraw)\n"
            "                gui_redraw(forced);\n"
            "            else if (gui_is_osd_mode())\n"
            "                gui_draw_osd_tick();\n"
            "            else if (gui_is_module_mode())\n"
            "                gui_draw_module_tick();"
        )
        nooverdraw_scheduler = (
            "            /* PORT-45 NOOVERDRAW GUI scheduler:\n"
            "             * Double-buffered overlay with asynchronous heap shadow restore on buffer flip or sentinel loss.\n"
            "             * Active only while CHDK ALT mode or menu is active.\n"
            "             * Fallback to PORT-44 if shadow is NULL or unavailable. */\n"
            "            extern int g3x_dbuf_shadow_restore(void);\n"
            "            extern int g3x_shadow_valid;\n"
            "            extern int g3x_dbuf_shadow_is_allocated(void);\n"
            "\n"
            "            gui_maintenance_tick();\n"
            "            int buffer_changed = check_bitmap_buffer_changed();\n"
            "            int forced = check_gui_needs_redraw();\n"
            "            int chdk_overlay_active = !camera_info.state.gui_mode_none;\n"
            "            if (chdk_overlay_active && (buffer_changed || !draw_test_guard()))\n"
            "            {\n"
            "                if (!g3x_shadow_valid || !g3x_dbuf_shadow_is_allocated() || !g3x_dbuf_shadow_restore())\n"
            "                {\n"
            "                    forced = 1;\n"
            "                }\n"
            "            }\n"
            "            int state_changed = gui_check_state_changed();\n"
            "            int need_redraw = forced || state_changed;\n"
            "            if (need_redraw)\n"
            "                gui_redraw(forced);\n"
            "            else if (gui_is_osd_mode())\n"
            "                gui_draw_osd_tick();\n"
            "            else if (gui_is_module_mode())\n"
            "                gui_draw_module_tick();"
        )
        if dbuf_scheduler in cm_text:
            cm_text = cm_text.replace(dbuf_scheduler, nooverdraw_scheduler, 1)
            core_main_c.write_text(cm_text, encoding="utf-8")
        else:
            raise RuntimeError("DBUF scheduler anchor not found in staged core/main.c")



def build_port43_dbuf(
    clean_stage: bool = True,
    keep_stage: bool = True,
    full_hooks: bool = False,
    no_overdraw: bool = False,
    out_dir: Path | str | None = None,
) -> int:
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

    if out_dir is not None:
        effective_out_dir = Path(out_dir).resolve()
    elif no_overdraw:
        if full_hooks:
            effective_out_dir = REPO_ROOT / "out" / "port45-no-overdraw-full-hooks"
        else:
            effective_out_dir = REPO_ROOT / "out" / "port45-no-overdraw"
    elif full_hooks:
        effective_out_dir = REPO_ROOT / "out" / "port43-dbuf-full-hooks"
    else:
        effective_out_dir = REPO_ROOT / "out" / "port43-dbuf"

    effective_stage_dir = effective_out_dir / "stage_chdk"

    effective_out_dir.mkdir(parents=True, exist_ok=True)
    if clean_stage and effective_stage_dir.exists():
        shutil.rmtree(effective_stage_dir)

    if not effective_stage_dir.exists():
        print(f"Staging CHDK tree to {effective_stage_dir}...")
        shutil.copytree(CHDK_PORT, effective_stage_dir, symlinks=True)

    clean_staging_artifacts(effective_stage_dir)

    # 1. Overlay full_build/g3x onto stage_chdk/platform/g3x/ (excluding loader)
    platform_target = effective_stage_dir / "platform" / "g3x"
    print(f"Overlaying {FULL_BUILD_SRC} onto {platform_target}...")
    overlay_tree(FULL_BUILD_SRC, platform_target, ignore={"loader"})

    # 2. Overlay full_build/g3x/loader onto stage_chdk/loader/g3x/
    loader_target = effective_stage_dir / "loader" / "g3x"
    loader_src = FULL_BUILD_SRC / "loader"
    if loader_src.is_dir():
        print(f"Overlaying {loader_src} onto {loader_target}...")
        overlay_tree(loader_src, loader_target)

    # 3. Copy DBUF gui_menu.c onto stage_chdk/platform/g3x/
    dbuf_menu = CHDK_PORT / "platform" / "g3x" / "gui_menu.c"
    if dbuf_menu.is_file():
        print(f"Copying DBUF gui_menu.c to {platform_target}...")
        shutil.copy2(dbuf_menu, platform_target / "gui_menu.c")

    # Remove prototype files
    for proto_name in ["boot_prototype.c", "stubs_prototype.S"]:
        proto_file = platform_target / "sub" / "110c" / proto_name
        if proto_file.exists():
            proto_file.unlink()

    # Apply FULL_HOOKS patches if requested
    if full_hooks:
        print("FULL_HOOKS=1 enabled: Applying FINSIG-confirmed hook staging patches...")
        apply_full_hooks_staging_patches(effective_stage_dir)

    # Apply GUI fix patches
    print("G3X_GUI_FIX=1: Applying GUI flicker, colour and 2x font staging patches...")
    apply_gui_fix_staging_patches(effective_stage_dir)

    # Apply DBUF compile flag patches
    print("G3X_GUI_DBUF=1: Applying double-buffered overlay staging patches...")
    apply_dbuf_staging_patches(effective_stage_dir)

    # Apply NOOVERDRAW compile flag and scheduler/sentinel patches if requested
    if no_overdraw:
        print("G3X_GUI_NOOVERDRAW=1: Applying opt-in overlay protection staging patches...")
        apply_no_overdraw_staging_patches(effective_stage_dir)


    # Clean platform objects in staging copy
    for subpath in ["platform/g3x", "platform/g3x/sub/110c", "loader/g3x"]:
        p = effective_stage_dir / subpath
        if p.is_dir():
            clean_cmd = [
                "make",
                "-C",
                str(p),
                "PLATFORM=g3x",
                "PLATFORMSUB=110c",
                "G3X_FULL_BUILD=1",
                "G3X_GUI_FIX=1",
                "G3X_GUI_DBUF=1",
            ]
            if no_overdraw:
                clean_cmd.append("G3X_GUI_NOOVERDRAW=1")
            if full_hooks:
                clean_cmd.append("FULL_HOOKS=1")
            clean_cmd.append("clean")
            subprocess.run(
                clean_cmd,
                cwd=str(effective_stage_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Run make
    cmd = [
        "make",
        "-C",
        str(effective_stage_dir),
        "PLATFORM=g3x",
        "PLATFORMSUB=110c",
        "G3X_FULL_BUILD=1",
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
        "G3X_GUI_FIX=1",
        "G3X_GUI_DBUF=1",
    ]
    if no_overdraw:
        cmd.append("G3X_GUI_NOOVERDRAW=1")
    if full_hooks:
        cmd.append("FULL_HOOKS=1")
    cmd.append("fir")

    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if "MAKEFLAGS" not in env and wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    env["G3X_GUI_FIX"] = "1"
    env["G3X_GUI_DBUF"] = "1"
    if no_overdraw:
        env["G3X_GUI_NOOVERDRAW"] = "1"
    if full_hooks:
        env["FULL_HOOKS"] = "1"

    res = subprocess.run(cmd, cwd=str(effective_stage_dir), env=env)
    if res.returncode != 0:
        print(f"ERROR: Build failed with exit code {res.returncode}", file=sys.stderr)
        return res.returncode

    # Verify generated DISKBOOT.BIN
    stage_diskboot = effective_stage_dir / "bin" / "DISKBOOT.BIN"
    if not stage_diskboot.is_file() or stage_diskboot.stat().st_size == 0:
        print(f"ERROR: Expected output missing or empty: {stage_diskboot}", file=sys.stderr)
        return 1

    out_diskboot = effective_out_dir / "DISKBOOT.BIN"
    shutil.copy2(stage_diskboot, out_diskboot)
    print(f"[OK] Generated {out_diskboot} ({out_diskboot.stat().st_size} bytes)")

    # Verify and copy CHDK/ distribution folder
    stage_chdk = effective_stage_dir / "CHDK"
    out_chdk = effective_out_dir / "CHDK"
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

    # Collect all CHDK files
    chdk_files_map: dict[str, dict[str, int | str]] = {}
    for root, dirs, files in os.walk(out_chdk):
        for f in sorted(files):
            p = Path(root) / f
            rel = str(p.relative_to(effective_out_dir))
            chdk_files_map[rel] = {
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            }

    # Manifest
    build_flags = [
        "G3X_FULL_BUILD=1",
        "G3X_DISABLE_CARD_WRITES=1",
        "CAM_SUPPORT_BITMAP_RES_CHANGE=1",
        "OPT_DISABLE_FILE_WRITES=1",
        "G3X_GUI5=1",
        "G3X_GUI_FIX=1",
        "G3X_GUI_DBUF=1",
    ]
    if no_overdraw:
        build_flags.append("G3X_GUI_NOOVERDRAW=1")
    if full_hooks:
        build_flags.insert(1, "FULL_HOOKS=1")

    manifest_name = "port45_no_overdraw_manifest.json" if no_overdraw else "port43_dbuf_manifest.json"
    manifest_data = {
        "build": {
            "platform": "g3x",
            "platform_sub": "110c",
            "flags": build_flags,
            "toolchain": "gcc-arm-none-eabi-5_4-2016q3",
            "deterministic_wrapper": "scripts/gcc_deterministic_wrapper.sh",
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
            "chdk_files_count": len(chdk_files_map),
            "chdk_files": chdk_files_map,
        },
    }

    manifest_path = effective_out_dir / manifest_name
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"[OK] Manifest written to {manifest_path}")

    # Convenience aliases
    with open(effective_out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    if not keep_stage and effective_stage_dir.exists():
        shutil.rmtree(effective_stage_dir)

    print("\nFULL BUILD COMPLETE (with G3X_GUI_FIX=1 G3X_GUI_DBUF=1).")
    print(f"DISKBOOT.BIN SHA-256: {manifest_data['artifacts']['DISKBOOT.BIN']['sha256']}")
    print(f"DISKBOOT.BIN Size:    {manifest_data['artifacts']['DISKBOOT.BIN']['size']} bytes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PORT-43 DBUF CHDK Full Build for PowerShot G3 X")
    parser.add_argument("--full-hooks", action="store_true", help="Enable FULL_HOOKS=1")
    parser.add_argument("--no-overdraw", action="store_true", help="Enable G3X_GUI_NOOVERDRAW=1 opt-in overlay protection")
    parser.add_argument("--no-clean", action="store_true", help="Do not clean staging before building")
    parser.add_argument("--discard-stage", action="store_true", help="Remove stage directory after build")
    parser.add_argument("--out-dir", type=str, default=None, help="Custom output directory")
    args = parser.parse_args()

    return build_port43_dbuf(
        clean_stage=not args.no_clean,
        keep_stage=not args.discard_stage,
        full_hooks=args.full_hooks,
        no_overdraw=args.no_overdraw,
        out_dir=args.out_dir,
    )



if __name__ == "__main__":
    sys.exit(main())
