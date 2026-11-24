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
import re
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
SEED_STAGE_DIR = REPO_ROOT / "out" / ".port43_seed_stage"

sys.path.insert(0, str(REPO_ROOT / "tools"))
from build_port41_full import (  # type: ignore
    apply_full_hooks_staging_patches,
    apply_gui_fix_staging_patches,
    clean_staging_artifacts,
    overlay_tree,
    sha256_file,
)


def _clean_platform_and_core_artifacts(stage_dir: Path) -> None:
    """Clean stale objects/archives/binaries in core, platform, loader, and bin while preserving prebuilt tools/lib/modules/CHDK."""
    subprocess.run(["chmod", "-R", "u+w", str(stage_dir)], check=True)
    for sub in ["core", "platform", "loader", "bin"]:
        target = stage_dir / sub
        if not target.is_dir():
            continue
        for o2 in target.glob("**/.o2"):
            if o2.is_dir():
                shutil.rmtree(o2, ignore_errors=True)
        for ext in ("*.o", "*.a", "*.d", "*.flt", "*.dump", "*.elf", "*.bin"):
            for f in target.glob(f"**/{ext}"):
                try:
                    f.unlink()
                except OSError:
                    pass


def _remove_prototype_files(stage_dir: Path) -> None:
    """Remove boot_prototype.c and stubs_prototype.S from a staged CHDK tree."""
    for proto_name in ["boot_prototype.c", "stubs_prototype.S"]:
        proto_file = stage_dir / "platform" / "g3x" / "sub" / "110c" / proto_name
        if proto_file.exists():
            proto_file.unlink()


def _ensure_dbuf_seed_stage() -> Path:
    """Build or return a cached staging seed with prebuilt tools/, lib/, modules/, and CHDK/."""
    sentinel = SEED_STAGE_DIR / ".seed_ready"
    if (
        sentinel.is_file()
        and (SEED_STAGE_DIR / "tools" / "dancingbits").is_file()
        and (SEED_STAGE_DIR / "lib" / "core" / ".o2" / "libcore.a").is_file()
        and len(list((SEED_STAGE_DIR / "modules" / ".o2").glob("*.flt"))) == 34
    ):
        for rel in ["core", "include", "platform/g3x", "loader/g3x"]:
            dst = SEED_STAGE_DIR / rel
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(CHDK_PORT / rel, dst, symlinks=True)
        _remove_prototype_files(SEED_STAGE_DIR)
        _clean_platform_and_core_artifacts(SEED_STAGE_DIR)
        return SEED_STAGE_DIR

    if SEED_STAGE_DIR.exists():
        shutil.rmtree(SEED_STAGE_DIR)
    SEED_STAGE_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CHDK_PORT, SEED_STAGE_DIR, symlinks=True)
    clean_staging_artifacts(SEED_STAGE_DIR)

    platform_target = SEED_STAGE_DIR / "platform" / "g3x"
    overlay_tree(FULL_BUILD_SRC, platform_target, ignore={"loader"})
    loader_src = FULL_BUILD_SRC / "loader"
    if loader_src.is_dir():
        overlay_tree(loader_src, SEED_STAGE_DIR / "loader" / "g3x")
    dbuf_menu = CHDK_PORT / "platform" / "g3x" / "gui_menu.c"
    if dbuf_menu.is_file():
        shutil.copy2(dbuf_menu, platform_target / "gui_menu.c")
    _remove_prototype_files(SEED_STAGE_DIR)

    apply_gui_fix_staging_patches(SEED_STAGE_DIR, legacy_dbuf_snapshot=False)
    apply_dbuf_staging_patches(SEED_STAGE_DIR)

    cmd = [
        "make",
        "-C",
        str(SEED_STAGE_DIR),
        "PLATFORM=g3x",
        "PLATFORMSUB=110c",
        "G3X_FULL_BUILD=1",
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
        "G3X_GUI_FIX=1",
        "G3X_GUI_DBUF=1",
        "fir",
    ]
    env = os.environ.copy()
    gcc_tmp = SEED_STAGE_DIR.parent / ".tmp_gcc"
    gcc_tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(gcc_tmp)
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    env["G3X_GUI_FIX"] = "1"
    env["G3X_GUI_DBUF"] = "1"
    env["G3X_DISABLE_CARD_WRITES"] = "1"
    env["OPT_DISABLE_FILE_WRITES"] = "1"
    subprocess.run(cmd, cwd=str(SEED_STAGE_DIR), env=env, check=True, stdout=subprocess.DEVNULL)
    shutil.rmtree(gcc_tmp, ignore_errors=True)

    for rel in ["core", "include", "platform/g3x", "loader/g3x"]:
        dst = SEED_STAGE_DIR / rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(CHDK_PORT / rel, dst, symlinks=True)
    _remove_prototype_files(SEED_STAGE_DIR)
    _clean_platform_and_core_artifacts(SEED_STAGE_DIR)

    sentinel.write_text("ok\n", encoding="utf-8")
    return SEED_STAGE_DIR


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
            "/* PORT-45: Multi-point perimeter sentinels:\n"
            " * (0,0) is always set and tested as in PORT-44.\n"
            " * The 4 corner sentinels are placed outside the 880x576 menu fill ([10,889]x[12,587])\n"
            " * but inside the 928x600 bitmap buffer (disp_width 900, disp_height 600):\n"
            " * Top-left:     (8, 10)\n"
            " * Top-right:    (891, 10)\n"
            " * Bottom-left:  (8, 589)\n"
            " * Bottom-right: (891, 589)\n"
            " *\n"
            " * Gating: With ALT off (gui_mode == NONE) or NULL shadow, only the PORT-44 (0,0)\n"
            " * sentinel is written and tested. The 4 corner sentinels are written and checked ONLY\n"
            " * while ALT/menu is active (!camera_info.state.gui_mode_none) AND the heap shadow is non-NULL\n"
            " * (g3x_dbuf_shadow_is_allocated()).\n"
            " */\n"
            "#define G3X_SENTINEL_TL_X 8\n"
            "#define G3X_SENTINEL_TL_Y 10\n"
            "#define G3X_SENTINEL_TR_X 891\n"
            "#define G3X_SENTINEL_TR_Y 10\n"
            "#define G3X_SENTINEL_BL_X 8\n"
            "#define G3X_SENTINEL_BL_Y 589\n"
            "#define G3X_SENTINEL_BR_X 891\n"
            "#define G3X_SENTINEL_BR_Y 589\n"
            "\n"
            "void draw_set_guard(void)\n"
            "{\n"
            "    opacity_buffer[0][0] = 0x42;\n"
            "    opacity_buffer[1][0] = 0x42;\n"
            "    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated())\n"
            "    {\n"
            "        int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
            "        unsigned int offsets[4] = {\n"
            "            (unsigned int)(G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X),\n"
            "            (unsigned int)(G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X),\n"
            "            (unsigned int)(G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X),\n"
            "            (unsigned int)(G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X)\n"
            "        };\n"
            "        for (int i = 0; i < 4; i++) {\n"
            "            opacity_buffer[0][offsets[i]] = 0x42;\n"
            "            opacity_buffer[1][offsets[i]] = 0x42;\n"
            "        }\n"
            "    }\n"
            "}\n"
            "\n"
            "int draw_test_guard(void)\n"
            "{\n"
            "    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42) return 0;\n"
            "    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated())\n"
            "    {\n"
            "        int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
            "        unsigned int offsets[4] = {\n"
            "            (unsigned int)(G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X),\n"
            "            (unsigned int)(G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X),\n"
            "            (unsigned int)(G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X),\n"
            "            (unsigned int)(G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X)\n"
            "        };\n"
            "        for (int i = 0; i < 4; i++) {\n"
            "            if (opacity_buffer[0][offsets[i]] != 0x42 || opacity_buffer[1][offsets[i]] != 0x42)\n"
            "                return 0;\n"
            "        }\n"
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
            "            if (chdk_overlay_active)\n"
            "            {\n"
            "                if (g3x_shadow_valid && g3x_dbuf_shadow_is_allocated())\n"
            "                {\n"
            "                    if (buffer_changed || !draw_test_guard())\n"
            "                    {\n"
            "                        if (!g3x_dbuf_shadow_restore())\n"
            "                        {\n"
            "                            forced = 1;\n"
            "                        }\n"
            "                    }\n"
            "                }\n"
            "                else\n"
            "                {\n"
            "                    /* Fallback to PORT-44: ignore buffer flips, only sentinel loss triggers redraw */\n"
            "                    if (!draw_test_guard())\n"
            "                    {\n"
            "                        forced = 1;\n"
            "                    }\n"
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



def apply_kbd_check_staging_patches(stage_dir: Path) -> None:
    """Add the ALT diagnostic after either DBUF scheduler has been selected."""
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        text = (
            "ifeq ($(G3X_KBD_CHECK),1)\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_KBD_CHECK=1 requires G3X_GUI_DBUF=1)\n"
            "endif\n"
            "endif\n\n"
        ) + text
        anchor = "CFLAGS += -DG3X_FULL_BUILD=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-46 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_KBD_CHECK=1", 1)
        mpath.write_text(text, encoding="utf-8")

    gui = stage_dir / "core/gui.c"
    text = gui.read_text(encoding="utf-8")
    anchor = "void gui_chdk_draw(int force_redraw)\n"
    if text.count(anchor) != 1:
        raise RuntimeError("PORT-46 ALT draw definition anchor not found")
    text = text.replace(anchor, '#include "../platform/g3x/kbd_check.h"\n\n' + anchor, 1)
    anchor = "    console_draw(force_redraw);\n"
    if text.count(anchor) != 1:
        raise RuntimeError("PORT-46 ALT console draw anchor not found")
    text = text.replace(anchor, anchor + (
        "#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)\n"
        "    gui_kbd_check_draw();\n"
        "#endif\n"
    ), 1)
    gui.write_text(text, encoding="utf-8")

    main = stage_dir / "core/main.c"
    text = main.read_text(encoding="utf-8")
    anchor = "            else if (gui_is_module_mode())\n"
    if text.count(anchor) != 1:
        raise RuntimeError("PORT-46 DBUF idle scheduler anchor not found")
    text = text.replace(anchor, (
        "#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)\n"
        "            else if (camera_info.state.gui_mode_alt)\n"
        "            {\n"
        "                extern void gui_kbd_check_draw(void);\n"
        "                gui_kbd_check_draw();\n"
        "            }\n"
        "#endif\n"
    ) + anchor, 1)
    main.write_text(text, encoding="utf-8")


def apply_gui_diag_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_DIAG=1 compile flags, shadow retry, blit-only restore, sibling suppression, and ALT counter line."""
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        text = (
            "ifeq ($(G3X_GUI_DIAG),1)\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
            "$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)\n"
            "endif\n"
            "ifneq ($(G3X_KBD_CHECK),1)\n"
            "$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)\n"
            "endif\n"
            "endif\n\n"
        ) + text
        anchor = "CFLAGS += -DG3X_FULL_BUILD=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-47 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_GUI_DIAG=1", 1)
        mpath.write_text(text, encoding="utf-8")

    # 1. Patch platform/g3x/lib.c: adapt G5X check_gui_needs_redraw() (chdk-port/platform/g5x/lib.c:206)
    lib_c = stage_dir / "platform/g3x/lib.c"
    lib_text = lib_c.read_text(encoding="utf-8")
    lib_anchor = (
        "int check_gui_needs_redraw(void)\n"
        "{\n"
        "    // draw_test_guard sentinel check is executed directly in main loop redraw condition\n"
        "    extern int draw_test_guard(void);\n"
        "    (void)draw_test_guard;\n"
        "    return 0;\n"
        "}"
    )
    lib_replacement = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        '#include "gui_diag.h"\n'
        "int check_gui_needs_redraw(void)\n"
        "{\n"
        "    return g3x_diag_check_suppress();\n"
        "}\n"
        "#else\n"
        "int check_gui_needs_redraw(void)\n"
        "{\n"
        "    // draw_test_guard sentinel check is executed directly in main loop redraw condition\n"
        "    extern int draw_test_guard(void);\n"
        "    (void)draw_test_guard;\n"
        "    return 0;\n"
        "}\n"
        "#endif"
    )
    if lib_text.count(lib_anchor) != 1:
        raise RuntimeError("PORT-47 check_gui_needs_redraw anchor not found in staged platform/g3x/lib.c")
    lib_c.write_text(lib_text.replace(lib_anchor, lib_replacement, 1), encoding="utf-8")

    # 2. Patch core/gui_draw.c: reliable shadow allocation retry on ALT entry and blit-only shadow restore
    draw_c = stage_dir / "core/gui_draw.c"
    draw_text = draw_c.read_text(encoding="utf-8")
    alloc_anchor = (
        "void g3x_dbuf_shadow_ensure_allocated(void)\n"
        "{\n"
        "    if (g3x_shadow_alloc_attempted)\n"
        "        return;\n"
        "    g3x_shadow_alloc_attempted = 1;\n"
        "\n"
        "    void *buf = malloc(G3X_SHADOW_TOTAL_SIZE);\n"
        "    if (!buf)\n"
        "    {\n"
        "        buf = umalloc(G3X_SHADOW_TOTAL_SIZE);\n"
        "    }\n"
        "    if (buf)\n"
        "    {\n"
        "        g3x_shadow_bitmap = (unsigned char *)buf;\n"
        "        g3x_shadow_opacity = (unsigned char *)buf + G3X_SHADOW_BM_SIZE;\n"
        "        memset(buf, 0, G3X_SHADOW_TOTAL_SIZE);\n"
        "    }\n"
        "    else\n"
        "    {\n"
        "        g3x_shadow_bitmap = 0;\n"
        "        g3x_shadow_opacity = 0;\n"
        "        g3x_shadow_valid = 0;\n"
        "    }\n"
        "}\n"
        "\n"
        "void g3x_dbuf_shadow_reset(void)\n"
        "{\n"
        "    g3x_shadow_valid = 0;"
    )
    alloc_replacement = (
        '#include "../platform/g3x/gui_diag.h"\n\n'
        "void g3x_dbuf_shadow_ensure_allocated(void)\n"
        "{\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_diag_shadow_ensure_allocated(&g3x_shadow_bitmap, &g3x_shadow_opacity,\n"
        "                                     &g3x_shadow_valid, &g3x_shadow_alloc_attempted);\n"
        "#else\n"
        "    if (g3x_shadow_alloc_attempted)\n"
        "        return;\n"
        "    g3x_shadow_alloc_attempted = 1;\n"
        "\n"
        "    void *buf = malloc(G3X_SHADOW_TOTAL_SIZE);\n"
        "    if (!buf)\n"
        "    {\n"
        "        buf = umalloc(G3X_SHADOW_TOTAL_SIZE);\n"
        "    }\n"
        "    if (buf)\n"
        "    {\n"
        "        g3x_shadow_bitmap = (unsigned char *)buf;\n"
        "        g3x_shadow_opacity = (unsigned char *)buf + G3X_SHADOW_BM_SIZE;\n"
        "        memset(buf, 0, G3X_SHADOW_TOTAL_SIZE);\n"
        "    }\n"
        "    else\n"
        "    {\n"
        "        g3x_shadow_bitmap = 0;\n"
        "        g3x_shadow_opacity = 0;\n"
        "        g3x_shadow_valid = 0;\n"
        "    }\n"
        "#endif\n"
        "}\n"
        "\n"
        "void g3x_dbuf_shadow_reset(void)\n"
        "{\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_shadow_valid = g3x_dbuf_shadow_is_allocated();\n"
        "#else\n"
        "    g3x_shadow_valid = 0;\n"
        "#endif"
    )
    if draw_text.count(alloc_anchor) != 1:
        raise RuntimeError("PORT-47 shadow alloc anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(alloc_anchor, alloc_replacement, 1)

    restore_anchor = (
        "int g3x_dbuf_shadow_restore(void)\n"
        "{\n"
        "    /* Restore only when shadow is valid, buffer allocated, AND CHDK overlay layer is active (not in defaultGuiHandler/live view) */\n"
        "    if (!g3x_shadow_valid || !g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "\n"
        "    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry)\n"
        "    {\n"
        "        int screen_y = G3X_MENU_Y0 + ry;\n"
        "        unsigned int offset_op = (unsigned int)(screen_y * buf_w + G3X_MENU_X0);\n"
        "        unsigned int offset_bm = offset_op * 2;\n"
        "\n"
        "        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;\n"
        "        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;\n"
        "\n"
        "        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "\n"
        "        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "    }\n"
        "\n"
        "    draw_set_guard();\n"
        "    /* NOTE: No vid_bitmap_refresh() here! On G3X (DIGIC 6), vid_bitmap_refresh calls _transfer_src_overlay,\n"
        "     * which wipes the overlay plane back to stock Canon UI (docs/PORT35_GUI_ADDRESSES.md:35).\n"
        "     * The synchronous blit into both bitmap buffers and both opacity buffers stands on its own. */\n"
        "    return 1;\n"
        "}"
    )
    restore_replacement = (
        "int g3x_dbuf_shadow_restore(void)\n"
        "{\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    if (!g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "#else\n"
        "    /* Restore only when shadow is valid, buffer allocated, AND CHDK overlay layer is active (not in defaultGuiHandler/live view) */\n"
        "    if (!g3x_shadow_valid || !g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "#endif\n"
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "\n"
        "    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry)\n"
        "    {\n"
        "        int screen_y = G3X_MENU_Y0 + ry;\n"
        "        unsigned int offset_op = (unsigned int)(screen_y * buf_w + G3X_MENU_X0);\n"
        "        unsigned int offset_bm = offset_op * 2;\n"
        "\n"
        "        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;\n"
        "        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;\n"
        "\n"
        "        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "\n"
        "        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "    }\n"
        "\n"
        "    draw_set_guard();\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_diag_record_shadow_restore();\n"
        "#endif\n"
        "    /* NOTE: No vid_bitmap_refresh() here! On G3X (DIGIC 6), vid_bitmap_refresh calls _transfer_src_overlay,\n"
        "     * which wipes the overlay plane back to stock Canon UI (docs/PORT35_GUI_ADDRESSES.md:35).\n"
        "     * The synchronous blit into both bitmap buffers and both opacity buffers stands on its own. */\n"
        "    return 1;\n"
        "}"
    )
    if draw_text.count(restore_anchor) != 1:
        raise RuntimeError("PORT-47 shadow restore anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(restore_anchor, restore_replacement, 1)
    draw_c.write_text(draw_text, encoding="utf-8")

    # 3. Patch core/gui.c: include gui_diag.h, draw counter line, engage/release suppression on ALT enter/leave,
    # and enforce shadow-blit-only restore when shadow is non-NULL
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")

    include_anchor = '#include "../platform/g3x/kbd_check.h"\n\nvoid gui_chdk_draw(int force_redraw)\n'
    include_replacement = (
        '#include "../platform/g3x/kbd_check.h"\n'
        '#define G3X_GUI_DIAG_IMPLEMENTATION 1\n'
        '#include "../platform/g3x/gui_diag.h"\n\n'
        'void gui_chdk_draw(int force_redraw)\n'
    )
    if gui_text.count(include_anchor) != 1:
        raise RuntimeError("PORT-47 gui_chdk_draw include anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(include_anchor, include_replacement, 1)

    draw_call_anchor = (
        "#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)\n"
        "    gui_kbd_check_draw();\n"
        "#endif\n"
    )
    draw_call_replacement = draw_call_anchor + (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    gui_diag_draw();\n"
        "#endif\n"
    )
    if gui_text.count(draw_call_anchor) != 1:
        raise RuntimeError("PORT-47 gui_kbd_check_draw call anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(draw_call_anchor, draw_call_replacement, 1)

    set_mode_alloc_anchor = (
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "    if (mode && mode->mode != GUI_MODE_NONE)\n"
        "    {\n"
        "        extern void g3x_dbuf_shadow_ensure_allocated(void);\n"
        "        g3x_dbuf_shadow_ensure_allocated();\n"
        "    }\n"
        "    /* Invalidation: GUI handler/layer changed - reset shadow until new layer completes full draw */\n"
        "    g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    set_mode_alloc_replacement = (
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "#if !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1)\n"
        "    if (mode && mode->mode != GUI_MODE_NONE)\n"
        "    {\n"
        "        extern void g3x_dbuf_shadow_ensure_allocated(void);\n"
        "        g3x_dbuf_shadow_ensure_allocated();\n"
        "    }\n"
        "#endif\n"
        "    /* Invalidation: GUI handler/layer changed - reset shadow until new layer completes full draw */\n"
        "    g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    if gui_text.count(set_mode_alloc_anchor) != 1:
        raise RuntimeError("PORT-47 gui_set_mode alloc anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(set_mode_alloc_anchor, set_mode_alloc_replacement, 1)

    gui_redraw_anchor = (
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "    /* Restore on sentinel loss ONLY when shadow is valid AND a CHDK overlay layer is active */\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash) && g3x_shadow_valid)\n"
        "    {\n"
        "        extern int g3x_dbuf_restore_if_sentinel_lost(void);\n"
        "        if (g3x_dbuf_restore_if_sentinel_lost())\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "    else if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#else"
    )
    gui_redraw_replacement = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        g3x_diag_record_sentinel_loss();\n"
        "        if (g3x_dbuf_shadow_is_allocated())\n"
        "        {\n"
        "            (void)g3x_dbuf_shadow_restore();\n"
        "            return;\n"
        "        }\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#elif defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "    /* Restore on sentinel loss ONLY when shadow is valid AND a CHDK overlay layer is active */\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash) && g3x_shadow_valid)\n"
        "    {\n"
        "        extern int g3x_dbuf_restore_if_sentinel_lost(void);\n"
        "        if (g3x_dbuf_restore_if_sentinel_lost())\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "    else if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#else"
    )
    if gui_text.count(gui_redraw_anchor) != 1:
        raise RuntimeError("PORT-47 gui_redraw guard anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(gui_redraw_anchor, gui_redraw_replacement, 1)

    alt_enter_anchor = (
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "        /* PORT-44: Lazy runtime allocation on first ALT entry */\n"
        "        extern void g3x_dbuf_shadow_ensure_allocated(void);\n"
        "        g3x_dbuf_shadow_ensure_allocated();\n"
        "        /* Invalidation: ALT enter - reset shadow */\n"
        "        g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    alt_enter_replacement = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "        g3x_diag_on_alt_enter();\n"
        "        g3x_dbuf_shadow_reset();\n"
        "#elif defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "        /* PORT-44: Lazy runtime allocation on first ALT entry */\n"
        "        extern void g3x_dbuf_shadow_ensure_allocated(void);\n"
        "        g3x_dbuf_shadow_ensure_allocated();\n"
        "        /* Invalidation: ALT enter - reset shadow */\n"
        "        g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    if gui_text.count(alt_enter_anchor) != 1:
        raise RuntimeError("PORT-47 ALT_MODE_ENTER anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(alt_enter_anchor, alt_enter_replacement, 1)

    alt_leave_anchor = (
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "        /* Invalidation: ALT exit - reset shadow so live view never restores stale overlay */\n"
        "        g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    alt_leave_replacement = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "        g3x_diag_on_alt_leave();\n"
        "#endif\n"
        "#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
        "        /* Invalidation: ALT exit - reset shadow so live view never restores stale overlay */\n"
        "        g3x_dbuf_shadow_reset();\n"
        "#endif"
    )
    if gui_text.count(alt_leave_anchor) != 1:
        raise RuntimeError("PORT-47 ALT_MODE_LEAVE anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(alt_leave_anchor, alt_leave_replacement, 1)
    gui_c.write_text(gui_text, encoding="utf-8")

    # 4. Patch core/main.c: shadow-blit-only restore while shadow exists, full redraw only when shadow is NULL,
    # and draw both kbd_check and gui_diag lines in ALT mode
    main_c = stage_dir / "core/main.c"
    main_text = main_c.read_text(encoding="utf-8")
    main_anchor = (
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
        "            if (chdk_overlay_active)\n"
        "            {\n"
        "                if (g3x_shadow_valid && g3x_dbuf_shadow_is_allocated())\n"
        "                {\n"
        "                    if (buffer_changed || !draw_test_guard())\n"
        "                    {\n"
        "                        if (!g3x_dbuf_shadow_restore())\n"
        "                        {\n"
        "                            forced = 1;\n"
        "                        }\n"
        "                    }\n"
        "                }\n"
        "                else\n"
        "                {\n"
        "                    /* Fallback to PORT-44: ignore buffer flips, only sentinel loss triggers redraw */\n"
        "                    if (!draw_test_guard())\n"
        "                    {\n"
        "                        forced = 1;\n"
        "                    }\n"
        "                }\n"
        "            }\n"
        "            int state_changed = gui_check_state_changed();\n"
        "            int need_redraw = forced || state_changed;\n"
        "            if (need_redraw)\n"
        "                gui_redraw(forced);\n"
        "            else if (gui_is_osd_mode())\n"
        "                gui_draw_osd_tick();\n"
        "#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)\n"
        "            else if (camera_info.state.gui_mode_alt)\n"
        "            {\n"
        "                extern void gui_kbd_check_draw(void);\n"
        "                gui_kbd_check_draw();\n"
        "            }\n"
        "#endif\n"
        "            else if (gui_is_module_mode())\n"
        "                gui_draw_module_tick();"
    )
    main_replacement = (
        "            /* PORT-47 GUI_DIAG scheduler:\n"
        "             * While shadow exists (non-NULL), restore ONLY by single fast blit (g3x_dbuf_shadow_restore)\n"
        "             * and never fall back to banded gui_redraw.\n"
        "             * Full redraw (gui_redraw) is reachable from restore ONLY when shadow is NULL. */\n"
        "            extern int g3x_diag_restore_overlay(int trigger);\n"
        "            extern void gui_diag_draw(void);\n"
        "            extern void gui_kbd_check_draw(void);\n"
        "\n"
        "            gui_maintenance_tick();\n"
        "            int buffer_changed = check_bitmap_buffer_changed();\n"
        "            int suppress_hit = check_gui_needs_redraw();\n"
        "            int chdk_overlay_active = !camera_info.state.gui_mode_none;\n"
        "            int restored_via_full_redraw = 0;\n"
        "            if (chdk_overlay_active)\n"
        "            {\n"
        "                restored_via_full_redraw = g3x_diag_restore_overlay(suppress_hit || buffer_changed);\n"
        "            }\n"
        "            int state_changed = gui_check_state_changed();\n"
        "            if (!restored_via_full_redraw && state_changed)\n"
        "                gui_redraw(0);\n"
        "            else if (gui_is_osd_mode())\n"
        "                gui_draw_osd_tick();\n"
        "#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)\n"
        "            else if (camera_info.state.gui_mode_alt)\n"
        "            {\n"
        "                gui_kbd_check_draw();\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "                gui_diag_draw();\n"
        "#endif\n"
        "            }\n"
        "#endif\n"
        "            else if (gui_is_module_mode())\n"
        "                gui_draw_module_tick();"
    )
    if main_text.count(main_anchor) != 1:
        raise RuntimeError("PORT-47 NOOVERDRAW scheduler anchor not found in staged core/main.c")
    main_c.write_text(main_text.replace(main_anchor, main_replacement, 1), encoding="utf-8")


def apply_shadow2_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_SHADOW2=1 compile flags, exmem_alloc_cached adapter, and multi-mode shadow draw/restore hooks."""
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        text = (
            "ifeq ($(G3X_GUI_SHADOW2),1)\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
            "$(error G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1)\n"
            "endif\n"
            "ifneq ($(G3X_KBD_CHECK),1)\n"
            "$(error G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DIAG),1)\n"
            "$(error G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1)\n"
            "endif\n"
            "endif\n\n"
        ) + text
        anchor = "CFLAGS += -DG3X_FULL_BUILD=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-48 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_GUI_SHADOW2=1", 1)
        mpath.write_text(text, encoding="utf-8")

    # 1. Patch platform/g3x/lib.c: add exmem_alloc_cached adapter calling _exmem_alloc (0xFC092537, FINSIG)
    lib_c = stage_dir / "platform/g3x/lib.c"
    lib_text = lib_c.read_text(encoding="utf-8")
    lib_anchor = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        '#include "gui_diag.h"\n'
    )
    lib_replacement = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        '#include "gui_diag.h"\n'
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "/* Adapted from chdk-port/platform/generic/wrappers.c:1003 and chdk-port/core/memmgmt.c:181-182:\n"
        " * _exmem_alloc = 0xFC092537 (FINSIG, reference/finsig_gm110c/stubs_entry.S:298;\n"
        " * chdk-port/platform/g3x/sub/110c/stubs_entry.S:302) */\n"
        "extern void *_exmem_alloc(unsigned int pool_id, unsigned int size, int unk, int unk2);\n"
        "void *exmem_alloc_cached(unsigned int pool_id, unsigned int size, int unk, int unk2)\n"
        "{\n"
        "    return _exmem_alloc(pool_id, size, unk, unk2);\n"
        "}\n"
        "#endif\n"
    )
    if lib_text.count(lib_anchor) != 1:
        raise RuntimeError("PORT-48 gui_diag.h anchor not found in staged platform/g3x/lib.c")
    lib_c.write_text(lib_text.replace(lib_anchor, lib_replacement, 1), encoding="utf-8")

    # 2. Patch core/gui_draw.c: route shadow reset, pixel/rect/simple writes, and restore through G3X_GUI_SHADOW2 helpers
    draw_c = stage_dir / "core/gui_draw.c"
    draw_text = draw_c.read_text(encoding="utf-8")

    reset_anchor = (
        "void g3x_dbuf_shadow_reset(void)\n"
        "{\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_shadow_valid = g3x_dbuf_shadow_is_allocated();\n"
        "#else\n"
        "    g3x_shadow_valid = 0;\n"
        "#endif\n"
        "    if (g3x_shadow_bitmap && g3x_shadow_opacity)\n"
        "    {\n"
        "        memset(g3x_shadow_bitmap, 0, G3X_SHADOW_BM_SIZE);\n"
        "        memset(g3x_shadow_opacity, 0, G3X_SHADOW_OP_SIZE);\n"
        "    }\n"
        "}"
    )
    reset_replacement = (
        "void g3x_dbuf_shadow_reset(void)\n"
        "{\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_shadow_valid = g3x_dbuf_shadow_is_allocated();\n"
        "#else\n"
        "    g3x_shadow_valid = 0;\n"
        "#endif\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    g3x_shadow2_reset_buffer(g3x_shadow_bitmap, g3x_shadow_opacity);\n"
        "#else\n"
        "    if (g3x_shadow_bitmap && g3x_shadow_opacity)\n"
        "    {\n"
        "        memset(g3x_shadow_bitmap, 0, G3X_SHADOW_BM_SIZE);\n"
        "        memset(g3x_shadow_opacity, 0, G3X_SHADOW_OP_SIZE);\n"
        "    }\n"
        "#endif\n"
        "}"
    )
    if draw_text.count(reset_anchor) != 1:
        raise RuntimeError("PORT-48 shadow reset anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(reset_anchor, reset_replacement, 1)

    pixel_helper_anchor = (
        "void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd)\n"
        "{\n"
        "    (void)offs2;\n"
        "    if (!g3x_shadow_bitmap || !g3x_shadow_opacity)\n"
        "        return;"
    )
    pixel_helper_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "static void g3x_dbuf_shadow2_draw_pixel(unsigned int offset, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd, unsigned char cl)\n"
        "{\n"
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "    int screen_y = (int)(offset / buf_w);\n"
        "    int screen_x = (int)(offset % buf_w);\n"
        "    g3x_shadow2_write_pixel(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                            screen_x, screen_y,\n"
        "                            (unsigned char)y, (unsigned char)o,\n"
        "                            (unsigned char)u, (unsigned char)v,\n"
        "                            is_odd, cl);\n"
        "}\n"
        "#endif\n\n"
        "void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd)\n"
        "{\n"
        "    (void)offs2;\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    if (g3x_shadow2_mode != G3X_SHADOW_MODE_RECT)\n"
        "        return;\n"
        "#endif\n"
        "    if (!g3x_shadow_bitmap || !g3x_shadow_opacity)\n"
        "        return;"
    )
    if draw_text.count(pixel_helper_anchor) != 1:
        raise RuntimeError("PORT-48 shadow_draw_pixel anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(pixel_helper_anchor, pixel_helper_replacement, 1)

    fill_lead_anchor = (
        "            if (g3x_shadow_opacity && g3x_shadow_bitmap &&\n"
        "                cur_x >= G3X_MENU_X0 && cur_x <= G3X_MENU_X1 &&\n"
        "                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)\n"
        "            {\n"
        "                int rx = cur_x - G3X_MENU_X0;\n"
        "                int ry = y - G3X_MENU_Y0;\n"
        "                unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);\n"
        "                unsigned int sh_offs2 = (sh_offset >> 1) << 2;\n"
        "                if (sh_offset < G3X_SHADOW_OP_SIZE)\n"
        "                {\n"
        "                    g3x_shadow_opacity[sh_offset] = op_byte;\n"
        "                    g3x_shadow_bitmap[sh_offs2 + 3] = (unsigned char)y_luma;\n"
        "                }\n"
        "            }"
    )
    fill_lead_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "            g3x_shadow2_write_pixel(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                                    cur_x, y, (unsigned char)y_luma, op_byte,\n"
        "                                    (unsigned char)u_val, (unsigned char)v_val,\n"
        "                                    1, (unsigned char)cl);\n"
        "#else\n"
        + fill_lead_anchor + "\n"
        "#endif"
    )
    if draw_text.count(fill_lead_anchor) != 1:
        raise RuntimeError("PORT-48 fast_fill leading pixel anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(fill_lead_anchor, fill_lead_replacement, 1)

    fill_span_anchor = (
        "            if (g3x_shadow_opacity && g3x_shadow_bitmap &&\n"
        "                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)\n"
        "            {\n"
        "                int sh_x_start = cur_x > G3X_MENU_X0 ? cur_x : G3X_MENU_X0;\n"
        "                int sh_x_end = (cur_x + n_pixels - 1) < G3X_MENU_X1 ? (cur_x + n_pixels - 1) : G3X_MENU_X1;\n"
        "                if (sh_x_start <= sh_x_end)\n"
        "                {\n"
        "                    int ry = y - G3X_MENU_Y0;\n"
        "                    int rx_start = sh_x_start - G3X_MENU_X0;\n"
        "                    int sh_pixels = sh_x_end - sh_x_start + 1;\n"
        "                    unsigned int sh_op_off = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx_start);\n"
        "                    unsigned int sh_bm_off = sh_op_off * 2;\n"
        "\n"
        "                    if ((sh_op_off + sh_pixels) <= G3X_SHADOW_OP_SIZE)\n"
        "                    {\n"
        "                        memset(&g3x_shadow_opacity[sh_op_off], op_byte, sh_pixels);\n"
        "                        int sh_pairs = sh_pixels / 2;\n"
        "                        unsigned int *sp = (unsigned int *)(&g3x_shadow_bitmap[sh_bm_off]);\n"
        "                        for (int sw = 0; sw < sh_pairs; ++sw)\n"
        "                        {\n"
        "                            sp[sw] = uyvy_word;\n"
        "                        }\n"
        "                    }\n"
        "                }\n"
        "            }"
    )
    fill_span_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "            g3x_shadow2_fill_span(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                                  cur_x, cur_x + n_pixels - 1, y,\n"
        "                                  uyvy_word, op_byte, (unsigned char)cl);\n"
        "#else\n"
        + fill_span_anchor + "\n"
        "#endif"
    )
    if draw_text.count(fill_span_anchor) != 1:
        raise RuntimeError("PORT-48 fast_fill span anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(fill_span_anchor, fill_span_replacement, 1)

    fill_trail_anchor = (
        "            if (g3x_shadow_opacity && g3x_shadow_bitmap &&\n"
        "                cur_x >= G3X_MENU_X0 && cur_x <= G3X_MENU_X1 &&\n"
        "                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)\n"
        "            {\n"
        "                int rx = cur_x - G3X_MENU_X0;\n"
        "                int ry = y - G3X_MENU_Y0;\n"
        "                unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);\n"
        "                unsigned int sh_offs2 = (sh_offset >> 1) << 2;\n"
        "                if (sh_offset < G3X_SHADOW_OP_SIZE)\n"
        "                {\n"
        "                    g3x_shadow_opacity[sh_offset] = op_byte;\n"
        "                    g3x_shadow_bitmap[sh_offs2 + 0] = (unsigned char)u_val;\n"
        "                    g3x_shadow_bitmap[sh_offs2 + 1] = (unsigned char)y_luma;\n"
        "                    g3x_shadow_bitmap[sh_offs2 + 2] = (unsigned char)v_val;\n"
        "                }\n"
        "            }"
    )
    fill_trail_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "            g3x_shadow2_write_pixel(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                                    cur_x, y, (unsigned char)y_luma, op_byte,\n"
        "                                    (unsigned char)u_val, (unsigned char)v_val,\n"
        "                                    0, (unsigned char)cl);\n"
        "#else\n"
        + fill_trail_anchor + "\n"
        "#endif"
    )
    if draw_text.count(fill_trail_anchor) != 1:
        raise RuntimeError("PORT-48 fast_fill trailing pixel anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(fill_trail_anchor, fill_trail_replacement, 1)

    restore2_anchor = (
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "\n"
        "    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry)\n"
        "    {\n"
        "        int screen_y = G3X_MENU_Y0 + ry;\n"
        "        unsigned int offset_op = (unsigned int)(screen_y * buf_w + G3X_MENU_X0);\n"
        "        unsigned int offset_bm = offset_op * 2;\n"
        "\n"
        "        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;\n"
        "        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;\n"
        "\n"
        "        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "\n"
        "        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "    }\n"
    )
    restore2_replacement = (
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    if (!g3x_shadow2_blit_restore(g3x_shadow_bitmap, g3x_shadow_opacity, buf_w))\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "#else\n"
        "    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry)\n"
        "    {\n"
        "        int screen_y = G3X_MENU_Y0 + ry;\n"
        "        unsigned int offset_op = (unsigned int)(screen_y * buf_w + G3X_MENU_X0);\n"
        "        unsigned int offset_bm = offset_op * 2;\n"
        "\n"
        "        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;\n"
        "        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;\n"
        "\n"
        "        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);\n"
        "\n"
        "        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);\n"
        "    }\n"
        "#endif\n"
    )
    if draw_text.count(restore2_anchor) != 1:
        raise RuntimeError("PORT-48 shadow restore loop anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(restore2_anchor, restore2_replacement, 1)

    std_px_anchor = "    g3x_dbuf_shadow_draw_pixel(offset, offs2, y, o, u, v, is_odd);\n"
    std_px_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    g3x_dbuf_shadow2_draw_pixel(offset, y, o, u, v, is_odd, (unsigned char)cl);\n"
        "#else\n"
        "    g3x_dbuf_shadow_draw_pixel(offset, offs2, y, o, u, v, is_odd);\n"
        "#endif\n"
    )
    if draw_text.count(std_px_anchor) != 1:
        raise RuntimeError("PORT-48 draw_pixel_std shadow anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(std_px_anchor, std_px_replacement, 1)

    simple_start_anchor = (
        "static unsigned char yuvclr[8]; // order of bytes: background u,y,v,opacity; foreground u,y,v,opacity\n"
        "\n"
        "// sets up decoded colors and buffer addresses for the following drawing operation\n"
        "static void draw_pixel_simple_start(twoColors tc)\n"
        "{\n"
        "    color cl;\n"
    )
    simple_start_replacement = (
        "static unsigned char yuvclr[8]; // order of bytes: background u,y,v,opacity; foreground u,y,v,opacity\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "static unsigned char simple_clr[2];\n"
        "#endif\n"
        "\n"
        "// sets up decoded colors and buffer addresses for the following drawing operation\n"
        "static void draw_pixel_simple_start(twoColors tc)\n"
        "{\n"
        "    color cl;\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    simple_clr[0] = (unsigned char)BG_COLOR(tc);\n"
        "    simple_clr[1] = (unsigned char)FG_COLOR(tc);\n"
        "#endif\n"
    )
    if draw_text.count(simple_start_anchor) != 1:
        raise RuntimeError("PORT-48 draw_pixel_simple_start anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(simple_start_anchor, simple_start_replacement, 1)

    expected_s1_counts = {"1": 3, "0": 1}
    for odd_val, expected_count in expected_s1_counts.items():
        s1_pat = re.compile(
            rf"^([ \t]+)g3x_dbuf_shadow_draw_pixel\(offset, offs2, y_luma, op, u_val, v_val, {odd_val}\);\n",
            re.MULTILINE,
        )
        matches = s1_pat.findall(draw_text)
        if len(matches) != expected_count:
            raise RuntimeError(
                f"PORT-48 simple shadow_draw_pixel(is_odd={odd_val}) count mismatch in staged core/gui_draw.c: "
                f"expected {expected_count}, got {len(matches)}"
            )
        draw_text, sub_count = s1_pat.subn(
            "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
            rf"\1g3x_dbuf_shadow2_draw_pixel(offset, y_luma, op, u_val, v_val, {odd_val}, simple_clr[px & 1]);" "\n"
            "#else\n"
            rf"\1g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, {odd_val});" "\n"
            "#endif\n",
            draw_text,
        )
        if sub_count != expected_count:
            raise RuntimeError(
                f"PORT-48 simple shadow_draw_pixel(is_odd={odd_val}) replacement count mismatch: "
                f"expected {expected_count}, got {sub_count}"
            )

    s2_anchor = (
        "        // Shadow copy update (16-bit opacity word, 32-bit UYVY bitmap word)\n"
        "        if (!conf.rotate_osd && g3x_shadow_opacity && g3x_shadow_bitmap)\n"
        "        {\n"
        "            if (x >= G3X_MENU_X0 && (x + 1) <= G3X_MENU_X1 &&\n"
        "                cur_y >= G3X_MENU_Y0 && cur_y <= G3X_MENU_Y1)\n"
        "            {\n"
        "                int rx = x - G3X_MENU_X0;\n"
        "                int ry = cur_y - G3X_MENU_Y0;\n"
        "                unsigned int sh_pair = (unsigned int)((ry * G3X_SHADOW_WIDTH + rx) >> 1);\n"
        "                if (sh_pair < (G3X_SHADOW_OP_SIZE / 2))\n"
        "                {\n"
        "                    ((unsigned short *)g3x_shadow_opacity)[sh_pair] = co;\n"
        "                    ((unsigned int *)g3x_shadow_bitmap)[sh_pair] = yuv;\n"
        "                }\n"
        "            }\n"
        "        }"
    )
    s2_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "        if (!conf.rotate_osd)\n"
        "        {\n"
        "            g3x_shadow2_write_pair(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                                   x, cur_y, yuv, co,\n"
        "                                   simple_clr[(px >> 1) & 1], simple_clr[px & 1]);\n"
        "        }\n"
        "#else\n"
        + s2_anchor + "\n"
        "#endif"
    )
    if draw_text.count(s2_anchor) != 1:
        raise RuntimeError("PORT-48 draw_2pixels_simple shadow anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(s2_anchor, s2_replacement, 1)

    hl_anchor = (
        "        if (!conf.rotate_osd && g3x_shadow_opacity && g3x_shadow_bitmap)\n"
        "        {\n"
        "            if (cur_x >= G3X_MENU_X0 && (cur_x + 1) <= G3X_MENU_X1 &&\n"
        "                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)\n"
        "            {\n"
        "                int rx = cur_x - G3X_MENU_X0;\n"
        "                int ry = y - G3X_MENU_Y0;\n"
        "                unsigned int sh_pair = (unsigned int)((ry * G3X_SHADOW_WIDTH + rx) >> 1);\n"
        "                if (sh_pair < (G3X_SHADOW_OP_SIZE / 2))\n"
        "                {\n"
        "                    ((unsigned short *)g3x_shadow_opacity)[sh_pair] = co;\n"
        "                    ((unsigned int *)g3x_shadow_bitmap)[sh_pair] = yuv;\n"
        "                }\n"
        "            }\n"
        "        }"
    )
    hl_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "        if (!conf.rotate_osd)\n"
        "        {\n"
        "            g3x_shadow2_write_pair(g3x_shadow_bitmap, g3x_shadow_opacity,\n"
        "                                   cur_x, y, yuv, co,\n"
        "                                   simple_clr[px & 1], simple_clr[px & 1]);\n"
        "        }\n"
        "#else\n"
        + hl_anchor + "\n"
        "#endif"
    )
    if draw_text.count(hl_anchor) != 1:
        raise RuntimeError("PORT-48 draw_hline_simple shadow anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(hl_anchor, hl_replacement, 1)

    draw_c.write_text(draw_text, encoding="utf-8")

    # 3. Patch core/gui.c: record ALT title/status bounds (y = height - FONT_HEIGHT .. height - 1)
    # and allow sentinel-loss branch in gui_redraw to restore inside region from shadow and fall back to
    # gui_redraw (incrementing F only for that fallback) when overlay content extends outside the shadow.
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")

    title_anchor = (
        "    if (camera_info.state.osd_title_line) \n"
        "    {\n"
        "        int w = camera_screen.disp_width;\n"
    )
    title_replacement = (
        "    if (camera_info.state.osd_title_line) \n"
        "    {\n"
        "        int w = camera_screen.disp_width;\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "        g3x_shadow2_record_overlay_rect(camera_screen.disp_left,\n"
        "                                        camera_screen.height - FONT_HEIGHT,\n"
        "                                        camera_screen.disp_left + w - 1,\n"
        "                                        camera_screen.height - 1);\n"
        "#endif\n"
    )
    if gui_text.count(title_anchor) != 1:
        raise RuntimeError("PORT-48 osd_title_line anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(title_anchor, title_replacement, 1)

    gui_sentinel_anchor = (
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        g3x_diag_record_sentinel_loss();\n"
        "        if (g3x_dbuf_shadow_is_allocated())\n"
        "        {\n"
        "            (void)g3x_dbuf_shadow_restore();\n"
        "            return;\n"
        "        }\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#elif defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
    )
    gui_sentinel_replacement = (
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        if (g3x_shadow2_handle_gui_redraw_sentinel(&flag_gui_enforce_redraw))\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#elif defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))\n"
        "    {\n"
        "        g3x_diag_record_sentinel_loss();\n"
        "        if (g3x_dbuf_shadow_is_allocated())\n"
        "        {\n"
        "            (void)g3x_dbuf_shadow_restore();\n"
        "            return;\n"
        "        }\n"
        "        draw_set_guard();\n"
        "        flag_gui_enforce_redraw = 1;\n"
        "#ifdef CAM_TOUCHSCREEN_UI\n"
        "        redraw_buttons = 1;\n"
        "#endif\n"
        "    }\n"
        "#elif defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)\n"
    )
    if gui_text.count(gui_sentinel_anchor) != 1:
        raise RuntimeError("PORT-48 gui_redraw sentinel anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(gui_sentinel_anchor, gui_sentinel_replacement, 1)
    gui_c.write_text(gui_text, encoding="utf-8")

    verify_shadow2_staged_sources(stage_dir)


def verify_shadow2_staged_sources(stage_dir: Path) -> None:
    """Verify that staged core/gui_draw.c has no active G3X_GUI_SHADOW2=1 calls to g3x_dbuf_shadow_draw_pixel,
    that the legacy g3x_dbuf_shadow_draw_pixel body is guarded by G3X_SHADOW_MODE_RECT, and that staged
    core/gui.c hooks the ALT title bounds and sentinel-loss partial-shadow restore path."""
    draw_c = stage_dir / "core" / "gui_draw.c"
    if not draw_c.is_file():
        raise RuntimeError(f"Missing staged file: {draw_c}")
    text = draw_c.read_text(encoding="utf-8")

    gui_c = stage_dir / "core" / "gui.c"
    if not gui_c.is_file():
        raise RuntimeError(f"Missing staged file: {gui_c}")
    gui_text = gui_c.read_text(encoding="utf-8")
    if gui_text.count("g3x_shadow2_record_overlay_rect(") != 1:
        raise RuntimeError("PORT-48 verification failed: staged core/gui.c is missing g3x_shadow2_record_overlay_rect")
    if gui_text.count("g3x_shadow2_handle_gui_redraw_sentinel(&flag_gui_enforce_redraw)") != 1:
        raise RuntimeError(
            "PORT-48 verification failed: staged core/gui.c is missing g3x_shadow2_handle_gui_redraw_sentinel"
        )

    guard_snippet = (
        "void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd)\n"
        "{\n"
        "    (void)offs2;\n"
        "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
        "    if (g3x_shadow2_mode != G3X_SHADOW_MODE_RECT)\n"
        "        return;\n"
        "#endif\n"
    )
    if text.count(guard_snippet) != 1:
        raise RuntimeError(
            "PORT-48 verification failed: g3x_dbuf_shadow_draw_pixel is missing the G3X_SHADOW_MODE_RECT guard"
        )

    pp_stack: list[str] = []
    def_count = 0
    inactive_call_count = 0
    shadow2_call_count = 0

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#if"):
            if "G3X_GUI_SHADOW2" in stripped and "!defined(G3X_GUI_SHADOW2)" not in stripped and "!= 1" not in stripped:
                pp_stack.append("shadow2_then")
            elif "G3X_GUI_SHADOW2" in stripped:
                pp_stack.append("shadow2_else")
            else:
                pp_stack.append("other")
        elif stripped.startswith("#elif"):
            if not pp_stack:
                raise RuntimeError(f"Unmatched #elif at {draw_c}:{lineno}")
            if "G3X_GUI_SHADOW2" in stripped and "!defined(G3X_GUI_SHADOW2)" not in stripped and "!= 1" not in stripped:
                pp_stack[-1] = "shadow2_then"
            else:
                pp_stack[-1] = "other"
        elif stripped.startswith("#else"):
            if not pp_stack:
                raise RuntimeError(f"Unmatched #else at {draw_c}:{lineno}")
            if pp_stack[-1] == "shadow2_then":
                pp_stack[-1] = "shadow2_else"
            elif pp_stack[-1] == "shadow2_else":
                pp_stack[-1] = "shadow2_then"
        elif stripped.startswith("#endif"):
            if not pp_stack:
                raise RuntimeError(f"Unmatched #endif at {draw_c}:{lineno}")
            pp_stack.pop()

        if "g3x_dbuf_shadow2_draw_pixel(" in stripped and not stripped.startswith("static void g3x_dbuf_shadow2_draw_pixel("):
            if "shadow2_then" not in pp_stack or "shadow2_else" in pp_stack:
                raise RuntimeError(
                    f"PORT-48 verification failed: g3x_dbuf_shadow2_draw_pixel call outside active SHADOW2 branch at {draw_c}:{lineno}"
                )
            shadow2_call_count += 1

        if "g3x_dbuf_shadow_draw_pixel(" in stripped:
            if stripped.startswith("void g3x_dbuf_shadow_draw_pixel("):
                def_count += 1
            else:
                if "shadow2_else" not in pp_stack:
                    raise RuntimeError(
                        f"PORT-48 verification failed: active SHADOW2 call to old g3x_dbuf_shadow_draw_pixel at {draw_c}:{lineno}: {stripped}"
                    )
                inactive_call_count += 1

    if def_count != 1:
        raise RuntimeError(f"PORT-48 verification failed: expected 1 definition of g3x_dbuf_shadow_draw_pixel, got {def_count}")
    if inactive_call_count != 5:
        raise RuntimeError(
            f"PORT-48 verification failed: expected 5 #else-guarded g3x_dbuf_shadow_draw_pixel calls, got {inactive_call_count}"
        )
    if shadow2_call_count != 5:
        raise RuntimeError(
            f"PORT-48 verification failed: expected 5 active g3x_dbuf_shadow2_draw_pixel calls, got {shadow2_call_count}"
        )


def apply_gui_sync_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_SYNC=1 compile flags, boot hook installation at 0x0000E26C, and target-buffer sync restore."""
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_diag.h", stage_dir / "platform/g3x/gui_diag.h")
    shutil.copy2(
        CHDK_PORT / "platform/g3x/sub/110c/gui_sync.h",
        stage_dir / "platform/g3x/sub/110c/gui_sync.h",
    )

    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        text = (
            "ifeq ($(G3X_GUI_SYNC),1)\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
            "$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_KBD_CHECK),1)\n"
            "$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DIAG),1)\n"
            "$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_SHADOW2),1)\n"
            "$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "endif\n\n"
        ) + text
        anchor = "-DG3X_GUI_SHADOW2=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-49 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_GUI_SYNC=1", 1)
        mpath.write_text(text, encoding="utf-8")

    # 1. Patch platform/g3x/sub/110c/boot.c: install 0x0000E26C callback pointer after BSS zeroing
    boot_c = stage_dir / "platform/g3x/sub/110c/boot.c"
    boot_text = boot_c.read_text(encoding="utf-8")
    boot_inc_anchor = '#include "led_breadcrumb.h"\n'
    boot_inc_replacement = (
        '#include "led_breadcrumb.h"\n'
        '#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)\n'
        '#include "gui_sync.h"\n'
        '#endif\n'
    )
    if boot_text.count(boot_inc_anchor) != 1:
        raise RuntimeError("PORT-49 boot.c include anchor not found in staged platform/g3x/sub/110c/boot.c")
    boot_text = boot_text.replace(boot_inc_anchor, boot_inc_replacement, 1)

    boot_hook_anchor = '        "    bl      g3x_full_shortpress_post_bss_hook\\n"\n'
    boot_hook_replacement = (
        '        "    bl      g3x_full_shortpress_post_bss_hook\\n"\n'
        '#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)\n'
        '        // PORT-49: Install synchronous display-flip callback pointer at 0x0000E26C\n'
        '        // (ROM_VERIFIED: docs/PORT49_GUI_SYNC.md answer (c); manifests/port49_gui_sync_evidence.json)\n'
        '        "    bl      g3x_gui_sync_install_hook\\n"\n'
        '#endif\n'
    )
    if boot_text.count(boot_hook_anchor) != 1:
        raise RuntimeError("PORT-49 boot.c post_bss_hook anchor not found in staged platform/g3x/sub/110c/boot.c")
    boot_text = boot_text.replace(boot_hook_anchor, boot_hook_replacement, 1)
    boot_c.write_text(boot_text, encoding="utf-8")

    # 2. Patch core/gui_draw.c: add g3x_dbuf_shadow_sync_restore(target_idx) for single-buffer post-transfer blit
    draw_c = stage_dir / "core/gui_draw.c"
    draw_text = draw_c.read_text(encoding="utf-8")
    sync_restore_anchor = (
        "    draw_set_guard();\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_diag_record_shadow_restore();\n"
        "#endif\n"
        "    /* NOTE: No vid_bitmap_refresh() here! On G3X (DIGIC 6), vid_bitmap_refresh calls _transfer_src_overlay,\n"
        "     * which wipes the overlay plane back to stock Canon UI (docs/PORT35_GUI_ADDRESSES.md:35).\n"
        "     * The synchronous blit into both bitmap buffers and both opacity buffers stands on its own. */\n"
        "    return 1;\n"
        "}"
    )
    sync_restore_replacement = sync_restore_anchor + (
        "\n\n"
        "#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)\n"
        "int g3x_dbuf_shadow_sync_restore(unsigned int target_idx)\n"
        "{\n"
        "    if (!g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;\n"
        "    if (!g3x_shadow2_blit_restore_target(g3x_shadow_bitmap, g3x_shadow_opacity, buf_w, target_idx))\n"
        "    {\n"
        "        return 0;\n"
        "    }\n"
        "    g3x_sync_set_guard_target(target_idx);\n"
        "    g3x_diag_record_shadow_restore();\n"
        "    return 1;\n"
        "}\n"
        "#endif"
    )
    if draw_text.count(sync_restore_anchor) != 1:
        raise RuntimeError("PORT-49 shadow sync restore anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(sync_restore_anchor, sync_restore_replacement, 1)
    draw_c.write_text(draw_text, encoding="utf-8")


def apply_conf_save_staging_patches(stage_dir: Path) -> None:
    """Gate conf_save, config_save, and save_config_file under write-disable flags and record SAVE:OFF."""
    conf_c = stage_dir / "core/conf.c"
    conf_text = conf_c.read_text(encoding="utf-8")
    if "g3x_conf_record_save_result" in conf_text and "save_config_file" in conf_text and "int save_config_file(int config_base, const char *filename)\n{\n#if" in conf_text:
        return

    # 1. config_save guard
    guard_anchor = "void config_save(ConfInfo *ci, const char *filename, int config_base)\n{\n"
    guard_code = (
        "void config_save(ConfInfo *ci, const char *filename, int config_base)\n"
        "{\n"
        "#if ((defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
        "     (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    (void)ci;\n"
        "    (void)filename;\n"
        "    (void)config_base;\n"
        "    extern void g3x_conf_record_save_result(int ok);\n"
        "    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);\n"
        "    return;\n"
        "#else\n"
    )
    if "void config_save(ConfInfo *ci, const char *filename, int config_base)\n{\n#if" not in conf_text:
        if conf_text.count(guard_anchor) != 1:
            raise RuntimeError("PORT-50/53 config_save start anchor not found in staged core/conf.c")
        conf_text = conf_text.replace(guard_anchor, guard_code, 1)
        end_anchor = "\n#if defined(OPT_FORCE_LUA_CALL_NATIVE)\n    conf.script_allow_lua_native_calls = 1;\n#endif\n}"
        if conf_text.count(end_anchor) != 1:
            raise RuntimeError("PORT-50/53 config_save end anchor not found in staged core/conf.c")
        conf_text = conf_text.replace(end_anchor, end_anchor[:-1] + "#endif\n}", 1)

    # 2. conf_save guard (skips config_save AND save_params_values, records SAVE:OFF)
    conf_save_anchor = "void conf_save()\n{\n"
    conf_save_code = (
        "void conf_save()\n"
        "{\n"
        "#if ((defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
        "     (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    extern void g3x_conf_record_save_result(int ok);\n"
        "    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);\n"
        "    return;\n"
        "#else\n"
    )
    if "void conf_save()\n{\n#if" not in conf_text:
        if conf_text.count(conf_save_anchor) != 1:
            raise RuntimeError("PORT-50/53 conf_save start anchor not found in staged core/conf.c")
        conf_text = conf_text.replace(conf_save_anchor, conf_save_code, 1)
        conf_save_end_anchor = "    // Save current script parameters if they have changed.\n    save_params_values(0);\n}"
        if conf_text.count(conf_save_end_anchor) != 1:
            raise RuntimeError("PORT-50/53 conf_save end anchor not found in staged core/conf.c")
        conf_text = conf_text.replace(conf_save_end_anchor, conf_save_end_anchor[:-1] + "#endif\n}", 1)

    # 3. save_config_file guard (skips config_save, records SAVE:OFF)
    save_cfg_anchor = (
        "int save_config_file(int config_base, const char *filename)\n"
        "{\n"
        "    int i;\n"
        "    for (i=0; confinfo_handlers[i].ci != 0; i++)\n"
        "    {\n"
        "        if ((config_base >= confinfo_handlers[i].start_id) && (config_base <= confinfo_handlers[i].end_id))\n"
        "        {\n"
        "            config_save(confinfo_handlers[i].ci, (filename != 0) ? filename : confinfo_handlers[i].filename, confinfo_handlers[i].start_id);\n"
        "            if (filename == 0)  // Reset 'last_saved' values after saving default file\n"
        "                config_update_last_saved(confinfo_handlers[i].ci);\n"
        "            return 1;\n"
        "        }\n"
        "    }\n"
        "    return 0;\n"
        "}"
    )
    save_cfg_replacement = (
        "int save_config_file(int config_base, const char *filename)\n"
        "{\n"
        "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    (void)config_base;\n"
        "    (void)filename;\n"
        "    extern void g3x_conf_record_save_result(int ok);\n"
        "    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);\n"
        "    return 0;\n"
        "#else\n"
        "    int i;\n"
        "    for (i=0; confinfo_handlers[i].ci != 0; i++)\n"
        "    {\n"
        "        if ((config_base >= confinfo_handlers[i].start_id) && (config_base <= confinfo_handlers[i].end_id))\n"
        "        {\n"
        "            config_save(confinfo_handlers[i].ci, (filename != 0) ? filename : confinfo_handlers[i].filename, confinfo_handlers[i].start_id);\n"
        "            if (filename == 0)  // Reset 'last_saved' values after saving default file\n"
        "                config_update_last_saved(confinfo_handlers[i].ci);\n"
        "            return 1;\n"
        "        }\n"
        "    }\n"
        "    return 0;\n"
        "#endif\n"
        "}"
    )
    if "int save_config_file(int config_base, const char *filename)\n{\n#if" not in conf_text:
        if conf_text.count(save_cfg_anchor) != 1:
            raise RuntimeError("PORT-50/53 save_config_file anchor not found in staged core/conf.c")
        conf_text = conf_text.replace(save_cfg_anchor, save_cfg_replacement, 1)

    conf_c.write_text(conf_text, encoding="utf-8")


def apply_gui_menu_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_MENU=1 compile flags, unwrap conf_save/param save, retain blocking write wrappers, and gate conf/script save paths."""
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_diag.h", stage_dir / "platform/g3x/gui_diag.h")
    shutil.copy2(
        CHDK_PORT / "platform/g3x/sub/110c/gui_sync.h",
        stage_dir / "platform/g3x/sub/110c/gui_sync.h",
    )

    # 1. Update makefiles with prerequisite checks and -DG3X_GUI_MENU=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        prereq = (
            "ifeq ($(G3X_GUI_MENU),1)\n"
            "ifneq ($(G3X_GUI_SYNC),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_KBD_CHECK),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DIAG),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_SHADOW2),1)\n"
            "$(error G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "endif\n\n"
        )
        text = prereq + text
        anchor = "-DG3X_GUI_SYNC=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-50 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_GUI_MENU=1", 1)
        mpath.write_text(text, encoding="utf-8")

    # 2. In platform/g3x/sub/110c/Makefile:
    # Under G3X_GUI_MENU=1:
    # - Unwrap conf_save, save_params_values, save_int_value_file (gated in source)
    # - DEFENSE IN DEPTH: RETAIN all blocking write wrappers (write, fwrite, open, fopen, creat, mkdir, remove, rename)
    # - Include gui_script.thm.o and fileutil.thm.o in CORE_OBJS so camera-flags versions are linked into libplatformsub.a
    sub_makefile = stage_dir / "platform/g3x/sub/110c/Makefile"
    sub_text = sub_makefile.read_text(encoding="utf-8")
    wrap_anchor = (
        "LDOPTS = -nostdlib -Wl,--allow-shlib-undefined -Wl,-EL,-T,$(tools)/link-boot.ld \\\n"
        "         -Wl,-N,-Ttext,$(MEMISOSTART) \\\n"
        "         -Wl,--wrap=conf_save -Wl,--wrap=save_params_values -Wl,--wrap=save_int_value_file \\\n"
        "         -Wl,--wrap=write -Wl,--wrap=fwrite -Wl,--wrap=open -Wl,--wrap=fopen -Wl,--wrap=creat \\\n"
        "         -Wl,--wrap=mkdir -Wl,--wrap=MakeDirectory_Fut -Wl,--wrap=_MakeDirectory_Fut \\\n"
        "         -Wl,--wrap=remove -Wl,--wrap=DeleteFile_Fut -Wl,--wrap=_DeleteFile_Fut \\\n"
        "         -Wl,--wrap=DeleteDirectory_Fut -Wl,--wrap=_DeleteDirectory_Fut \\\n"
        "         -Wl,--wrap=rename -Wl,--wrap=RenameFile_Fut -Wl,--wrap=_RenameFile_Fut\n"
    )
    wrap_replacement = (
        "ifeq ($(G3X_GUI_MENU),1)\n"
        "CORE_OBJS += gui_script.thm.o fileutil.thm.o\n"
        "LDOPTS = -nostdlib -Wl,--allow-shlib-undefined -Wl,-EL,-T,$(tools)/link-boot.ld \\\n"
        "         -Wl,-N,-Ttext,$(MEMISOSTART) \\\n"
        "         -Wl,--wrap=write -Wl,--wrap=fwrite -Wl,--wrap=open -Wl,--wrap=fopen -Wl,--wrap=creat \\\n"
        "         -Wl,--wrap=mkdir -Wl,--wrap=MakeDirectory_Fut -Wl,--wrap=_MakeDirectory_Fut \\\n"
        "         -Wl,--wrap=remove -Wl,--wrap=DeleteFile_Fut -Wl,--wrap=_DeleteFile_Fut \\\n"
        "         -Wl,--wrap=DeleteDirectory_Fut -Wl,--wrap=_DeleteDirectory_Fut \\\n"
        "         -Wl,--wrap=rename -Wl,--wrap=RenameFile_Fut -Wl,--wrap=_RenameFile_Fut\n"
        "else\n"
        + wrap_anchor +
        "endif\n"
    )
    if sub_text.count(wrap_anchor) != 1:
        raise RuntimeError("PORT-50 LDOPTS wrap anchor not found in staged sub/110c/Makefile")
    sub_text = sub_text.replace(wrap_anchor, wrap_replacement, 1)

    rules_code = (
        "\nfileutil.thm.o: $(topdir)lib/lang/fileutil.c\n"
        "\t@echo $< \\-\\> $@\n"
        "\t$(CC) $(CFLAGS) -mthumb -nostdinc -c -o $@ $<\n"
        "\ngui_script.thm.o: $(core)/gui_script.c\n"
        "\t@echo $< \\-\\> $@\n"
        "\t$(CC) $(CFLAGS) -mthumb -nostdinc -c -o $@ $<\n"
    )
    sub_text += rules_code
    sub_makefile.write_text(sub_text, encoding="utf-8")

    # 3. In platform/g3x/lib.c: only omit __wrap_conf_save, __wrap_save_params_values, __wrap_save_int_value_file under G3X_GUI_MENU=1.
    # Keep ALL write-side blocking wrappers (__wrap_write, __wrap_fwrite, __wrap_creat, __wrap_open, __wrap_fopen,
    # __wrap_mkdir, __wrap_remove, __wrap_rename, etc.) fully active!
    lib_c = stage_dir / "platform/g3x/lib.c"
    lib_text = lib_c.read_text(encoding="utf-8")
    lib_wrap_anchor = (
        "void __wrap_conf_save(void) { }\n"
        "void __wrap_save_params_values(int enforce) { (void)enforce; }\n"
        "void __wrap_save_int_value_file(const char *fn, int v) { (void)fn; (void)v; }"
    )
    lib_wrap_replacement = (
        "#if !defined(G3X_GUI_MENU) || (G3X_GUI_MENU != 1)\n"
        + lib_wrap_anchor + "\n"
        "#endif"
    )
    if lib_text.count(lib_wrap_anchor) != 1:
        raise RuntimeError("PORT-50 lib.c wrap anchor not found in staged platform/g3x/lib.c")
    lib_text = lib_text.replace(lib_wrap_anchor, lib_wrap_replacement, 1)
    lib_c.write_text(lib_text, encoding="utf-8")

    # 4. In core/gui.c: record menu open event when transitioning to menuGuiHandler
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")
    gui_anchor = "    gui_handler *old_mode = gui_mode;\n    gui_mode = mode;\n"
    gui_replacement = (
        "    gui_handler *old_mode = gui_mode;\n"
        "    gui_mode = mode;\n"
        "#if (defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))\n"
        "    if (mode == &menuGuiHandler && old_mode != &menuGuiHandler)\n"
        "    {\n"
        "        extern void g3x_menu_record_open(void);\n"
        "        g3x_menu_record_open();\n"
        "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
        "        extern void g3x_playback_menu_record_open(void);\n"
        "        g3x_playback_menu_record_open();\n"
        "#endif\n"
        "    }\n"
        "#endif\n"
    )
    if gui_text.count(gui_anchor) != 1:
        raise RuntimeError("PORT-50 gui.c old_mode anchor not found in staged core/gui.c")
    gui_text = gui_text.replace(gui_anchor, gui_replacement, 1)
    gui_c.write_text(gui_text, encoding="utf-8")

    # 5. In core/conf.c: gate conf_save, config_save, and save_config_file under write-disable flags
    apply_conf_save_staging_patches(stage_dir)

    # 6. In core/gui_script.c: gate save_params_values and do_save_param_file write sinks
    gui_script_c = stage_dir / "core/gui_script.c"
    gui_script_text = gui_script_c.read_text(encoding="utf-8")
    # 6a. do_save_param_file guard
    do_save_anchor = "static void do_save_param_file()\n{\n"
    do_save_code = (
        "static void do_save_param_file()\n"
        "{\n"
        "#if ((defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
        "     (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    return;\n"
        "#else\n"
    )
    if gui_script_text.count(do_save_anchor) == 1:
        gui_script_text = gui_script_text.replace(do_save_anchor, do_save_code, 1)
        do_save_end = "        close(fd);\n    }\n}"
        if gui_script_text.count(do_save_end) == 1:
            gui_script_text = gui_script_text.replace(do_save_end, do_save_end[:-1] + "#endif\n}", 1)
        else:
            raise RuntimeError("PORT-50 do_save_param_file end anchor not found in staged core/gui_script.c")
    # 6b. save_params_values guard
    save_params_anchor = "void save_params_values( int enforce )\n{\n"
    save_params_code = (
        "void save_params_values( int enforce )\n"
        "{\n"
        "#if ((defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
        "     (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    (void)enforce;\n"
        "    return;\n"
        "#else\n"
    )
    if gui_script_text.count(save_params_anchor) == 1:
        gui_script_text = gui_script_text.replace(save_params_anchor, save_params_code, 1)
        save_params_end = "            // Write parameters file\n            do_save_param_file();\n        }\n    }\n}"
        if gui_script_text.count(save_params_end) == 1:
            gui_script_text = gui_script_text.replace(save_params_end, save_params_end[:-1] + "#endif\n}", 1)
        else:
            raise RuntimeError("PORT-50 save_params_values end anchor not found in staged core/gui_script.c")
    gui_script_c.write_text(gui_script_text, encoding="utf-8")

    # 7. In lib/lang/fileutil.c: gate save_int_value_file write sink
    fileutil_c = stage_dir / "lib/lang/fileutil.c"
    fileutil_text = fileutil_c.read_text(encoding="utf-8")
    save_int_anchor = "void save_int_value_file( const char* filename, int value )\n{\n"
    save_int_code = (
        "void save_int_value_file( const char* filename, int value )\n"
        "{\n"
        "#if ((defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \\\n"
        "     (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))) && \\\n"
        "    ((defined(G3X_DISABLE_CARD_WRITES) && (G3X_DISABLE_CARD_WRITES == 1)) || \\\n"
        "     (defined(OPT_DISABLE_FILE_WRITES) && (OPT_DISABLE_FILE_WRITES == 1)))\n"
        "    (void)filename;\n"
        "    (void)value;\n"
        "    return;\n"
        "#else\n"
    )
    if fileutil_text.count(save_int_anchor) == 1:
        fileutil_text = fileutil_text.replace(save_int_anchor, save_int_code, 1)
        save_int_end = "\t\twrite(fd, buf, strlen(buf)+1);\n\t\tclose(fd);\n\t} \n\tufree(buf);\n}"
        if fileutil_text.count(save_int_end) == 1:
            fileutil_text = fileutil_text.replace(save_int_end, save_int_end[:-1] + "#endif\n}", 1)
        else:
            raise RuntimeError("PORT-50 save_int_value_file end anchor not found in staged lib/lang/fileutil.c")
        fileutil_c.write_text(fileutil_text, encoding="utf-8")

    # 8. Remove prebuilt gui_script.o and fileutil.o from prebuilt archives in staging copy
    # so libplatformsub.a provides the camera-built patched versions exclusively
    ar_bin = TOOLCHAIN_BIN / "arm-none-eabi-ar"
    libcore_a = stage_dir / "lib/core/.o2/libcore.a"
    if libcore_a.is_file():
        subprocess.run([str(ar_bin), "d", str(libcore_a), "gui_script.o"], check=True)
    liblang_a = stage_dir / "lib/lang/.o2/liblang.a"
    if liblang_a.is_file():
        subprocess.run([str(ar_bin), "d", str(liblang_a), "fileutil.o"], check=True)


def apply_gui_restore2_staging_patches(stage_dir: Path) -> None:
    """Apply G3X_GUI_RESTORE2=1 compile flags, rect-only shadow blit, and duration timing / path counters."""
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_diag.h", stage_dir / "platform/g3x/gui_diag.h")
    shutil.copy2(
        CHDK_PORT / "platform/g3x/sub/110c/gui_sync.h",
        stage_dir / "platform/g3x/sub/110c/gui_sync.h",
    )

    # 1. Update makefiles with prerequisite checks and -DG3X_GUI_RESTORE2=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        prereq = (
            "ifeq ($(G3X_GUI_RESTORE2),1)\n"
            "ifneq ($(G3X_GUI_MENU),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_SYNC),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DBUF),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_KBD_CHECK),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_DIAG),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "ifneq ($(G3X_GUI_SHADOW2),1)\n"
            "$(error G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
            "endif\n"
            "endif\n\n"
        )
        text = prereq + text
        anchor = "-DG3X_GUI_MENU=1"
        if text.count(anchor) != 1:
            raise RuntimeError(f"PORT-51 compile flag anchor not found in {rel}")
        text = text.replace(anchor, anchor + " -DG3X_GUI_RESTORE2=1", 1)
        mpath.write_text(text, encoding="utf-8")

    # 2. In core/gui_draw.c: route shadow restores to record sync vs poll counts
    draw_c = stage_dir / "core/gui_draw.c"
    draw_text = draw_c.read_text(encoding="utf-8")

    # Sync restore path
    sync_anchor = (
        "    g3x_sync_set_guard_target(target_idx);\n"
        "    g3x_diag_record_shadow_restore();\n"
        "    return 1;"
    )
    sync_replacement = (
        "    g3x_sync_set_guard_target(target_idx);\n"
        "#if defined(G3X_GUI_RESTORE2) && (G3X_GUI_RESTORE2 == 1)\n"
        "    g3x_diag_record_shadow_restore_sync();\n"
        "#else\n"
        "    g3x_diag_record_shadow_restore();\n"
        "#endif\n"
        "    return 1;"
    )
    if draw_text.count(sync_anchor) != 1:
        raise RuntimeError("PORT-51 sync restore record anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(sync_anchor, sync_replacement, 1)

    # Poll restore path
    poll_anchor = (
        "    draw_set_guard();\n"
        "#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_diag_record_shadow_restore();\n"
        "#endif"
    )
    poll_replacement = (
        "    draw_set_guard();\n"
        "#if defined(G3X_GUI_RESTORE2) && (G3X_GUI_RESTORE2 == 1)\n"
        "    g3x_diag_record_shadow_restore_poll();\n"
        "#elif defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)\n"
        "    g3x_diag_record_shadow_restore();\n"
        "#endif"
    )
    if draw_text.count(poll_anchor) != 1:
        raise RuntimeError("PORT-51 poll restore record anchor not found in staged core/gui_draw.c")
    draw_text = draw_text.replace(poll_anchor, poll_replacement, 1)

    draw_c.write_text(draw_text, encoding="utf-8")


def apply_playback_menu_staging_patches(stage_dir: Path, alone: bool = False) -> None:
    """Apply G3X_PLAYBACK_MENU=1 compile flags, playback mode kbd/gui handlers, and menu redraw hooks."""
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_diag.h", stage_dir / "platform/g3x/gui_diag.h")
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_menu.c", stage_dir / "platform/g3x/gui_menu.c")

    # 1. Update makefiles with -DG3X_PLAYBACK_MENU=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if alone:
            if "-DG3X_PLAYBACK_MENU=1" not in text:
                anchor = "CFLAGS += -DG3X_FULL_BUILD=1"
                if anchor in text:
                    text = text.replace(anchor, anchor + " -DG3X_PLAYBACK_MENU=1", 1)
                else:
                    text += "\nCFLAGS += -DG3X_PLAYBACK_MENU=1\n"
        else:
            anchor = "-DG3X_GUI_RESTORE2=1"
            if anchor in text and "-DG3X_PLAYBACK_MENU=1" not in text:
                text = text.replace(anchor, anchor + " -DG3X_PLAYBACK_MENU=1", 1)
            elif "-DG3X_PLAYBACK_MENU=1" not in text:
                anchor = "CFLAGS += -DG3X_FULL_BUILD=1"
                if anchor in text:
                    text = text.replace(anchor, anchor + " -DG3X_PLAYBACK_MENU=1", 1)
                else:
                    text += "\nCFLAGS += -DG3X_PLAYBACK_MENU=1\n"
        mpath.write_text(text, encoding="utf-8")

    # 2. Patch stage_chdk/platform/g3x/kbd.c
    kbd_c = stage_dir / "platform/g3x/kbd.c"
    kbd_text = kbd_c.read_text(encoding="utf-8")
    kbd_read_anchor = "void my_kbd_read_keys()\n{"
    if kbd_read_anchor in kbd_text and "g3x_playback_menu_kbd_process" not in kbd_text:
        kbd_read_call = (
            "void my_kbd_read_keys()\n{\n"
            "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "    extern int g3x_playback_menu_kbd_process(void);\n"
            "    if (g3x_playback_menu_kbd_process())\n"
            "    {\n"
            "        /* Playback menu active: keyboard input consumed */\n"
            "    }\n"
            "#endif\n"
        )
        kbd_text = kbd_text.replace(kbd_read_anchor, kbd_read_call, 1)
    if "\nint g3x_playback_menu_kbd_process(void)\n" not in kbd_text:
        kbd_hook = (
            "\n#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "int g3x_playback_menu_is_active(void)\n"
            "{\n"
            "    return camera_info.state.mode_play && !camera_info.state.gui_mode_none;\n"
            "}\n\n"
            "int g3x_playback_menu_kbd_process(void)\n"
            "{\n"
            "    if (g3x_playback_menu_is_active())\n"
            "    {\n"
            "        return 1;\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
            "#endif\n"
        )
        kbd_text += kbd_hook
    kbd_c.write_text(kbd_text, encoding="utf-8")

    # 3. Patch stage_chdk/platform/g3x/lib.c
    lib_c = stage_dir / "platform/g3x/lib.c"
    lib_text = lib_c.read_text(encoding="utf-8")
    vp_anchor = "int vid_get_viewport_width()\n{"
    if vp_anchor in lib_text and "g3x_playback_menu_get_viewport_mode" not in lib_text:
        vp_call = (
            "int vid_get_viewport_width()\n{\n"
            "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "    extern int g3x_playback_menu_get_viewport_mode(void);\n"
            "    if (g3x_playback_menu_get_viewport_mode())\n"
            "        return 720;\n"
            "#endif\n"
        )
        lib_text = lib_text.replace(vp_anchor, vp_call, 1)

    redraw_call_body = (
        "\n#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
        "    extern int g3x_playback_menu_gui_mode_active(void);\n"
        "    extern int g3x_playback_menu_redraw_needed(void);\n"
        "    extern void g3x_playback_menu_diag_draw(void);\n"
        "#if !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1)\n"
        "    if (g3x_playback_menu_gui_mode_active())\n"
        "    {\n"
        "        g3x_playback_menu_diag_draw();\n"
        "    }\n"
        "#endif\n"
        "    if (g3x_playback_menu_gui_mode_active() && g3x_playback_menu_redraw_needed())\n"
        "        return 1;\n"
        "#endif\n"
    )
    for redraw_anchor in [
        "int check_gui_needs_redraw(void)\n{",
        "int check_gui_needs_redraw()\n{",
    ]:
        start = 0
        while True:
            idx = lib_text.find(redraw_anchor, start)
            if idx == -1:
                break
            after = lib_text[idx + len(redraw_anchor):idx + len(redraw_anchor) + 120]
            if "g3x_playback_menu_redraw_needed" not in after:
                lib_text = lib_text[:idx] + redraw_anchor + redraw_call_body + lib_text[idx + len(redraw_anchor):]
                start = idx + len(redraw_anchor) + len(redraw_call_body)
            else:
                start = idx + len(redraw_anchor)

    if "\nint g3x_playback_menu_gui_mode_active(void)\n" not in lib_text:
        lib_hook = (
            "\n#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "int g3x_playback_menu_gui_mode_active(void)\n"
            "{\n"
            "    return camera_info.state.mode_play && (camera_info.state.gui_mode_alt || !camera_info.state.gui_mode_none);\n"
            "}\n\n"
            "int g3x_playback_menu_get_viewport_mode(void)\n"
            "{\n"
            "    return camera_info.state.mode_play ? 1 : 0;\n"
            "}\n"
            "#endif\n"
        )
        lib_text += lib_hook
    if alone:
        wrap_conf_anchor = "void __wrap_conf_save(void) { }"
        if wrap_conf_anchor in lib_text:
            wrap_conf_rep = (
                "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
                "#define G3X_GUI_DIAG_IMPLEMENTATION 1\n"
                '#include "gui_diag.h"\n'
                "#endif\n"
                "void __wrap_conf_save(void) {\n"
                "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
                "    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);\n"
                "#endif\n"
                "}"
            )
            lib_text = lib_text.replace(wrap_conf_anchor, wrap_conf_rep, 1)
    lib_c.write_text(lib_text, encoding="utf-8")

    # 4. Patch stage_chdk/platform/g3x/main.c
    main_c = stage_dir / "platform/g3x/main.c"
    main_text = main_c.read_text(encoding="utf-8")
    if "g3x_playback_menu_mode_check" not in main_text:
        main_hook = (
            "\n#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "int g3x_playback_menu_mode_check(void)\n"
            "{\n"
            "    extern int g3x_playback_menu_gui_mode_active(void);\n"
            "    return g3x_playback_menu_gui_mode_active();\n"
            "}\n"
            "#endif\n"
        )
        main_text += main_hook
        main_c.write_text(main_text, encoding="utf-8")

    # 5. Gate conf_save, config_save, and save_config_file in core/conf.c
    apply_conf_save_staging_patches(stage_dir)

    # 6. In core/gui.c: record menu open event when transitioning to menuGuiHandler
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")
    if "g3x_playback_menu_record_open" not in gui_text:
        gui_anchor = "    gui_handler *old_mode = gui_mode;\n    gui_mode = mode;\n"
        gui_replacement = (
            "    gui_handler *old_mode = gui_mode;\n"
            "    gui_mode = mode;\n"
            "#if (defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))\n"
            "    if (mode == &menuGuiHandler && old_mode != &menuGuiHandler)\n"
            "    {\n"
            "        extern void g3x_menu_record_open(void);\n"
            "        g3x_menu_record_open();\n"
            "#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)\n"
            "        extern void g3x_playback_menu_record_open(void);\n"
            "        g3x_playback_menu_record_open();\n"
            "#endif\n"
            "    }\n"
            "#endif\n"
        )
        if gui_text.count(gui_anchor) == 1:
            gui_text = gui_text.replace(gui_anchor, gui_replacement, 1)
            gui_c.write_text(gui_text, encoding="utf-8")


def apply_movie_status_staging_patches(stage_dir: Path, alone: bool = False) -> None:
    """PORT-55: Apply G3X_MOVIE_STATUS=1 compile flags, movie status headers, and stubs."""
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_diag.h", stage_dir / "platform/g3x/gui_diag.h")
    shutil.copy2(CHDK_PORT / "platform/g3x/movie_status.h", stage_dir / "platform/g3x/movie_status.h")
    shutil.copy2(CHDK_PORT / "platform/g3x/sub/110c/movie_rec.c", stage_dir / "platform/g3x/sub/110c/movie_rec.c")
    shutil.copy2(CHDK_PORT / "platform/g3x/sub/110c/stubs_min.S", stage_dir / "platform/g3x/sub/110c/stubs_min.S")

    # Update makefiles with -DG3X_MOVIE_STATUS=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "-DG3X_MOVIE_STATUS=1" not in text:
            if "CFLAGS += -DG3X_PLAYBACK_MENU=1" in text:
                text = text.replace("CFLAGS += -DG3X_PLAYBACK_MENU=1", "CFLAGS += -DG3X_PLAYBACK_MENU=1 -DG3X_MOVIE_STATUS=1")
            elif "CFLAGS += -DG3X_FULL_BUILD=1" in text:
                text = text.replace("CFLAGS += -DG3X_FULL_BUILD=1", "CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_MOVIE_STATUS=1")
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_STATUS=1", 1)
            elif "CFLAGS =" in text:
                text = text.replace("CFLAGS =", "CFLAGS = -DG3X_MOVIE_STATUS=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_STATUS=1\n"
        mpath.write_text(text, encoding="utf-8")


def apply_movie_nolimit_staging_patches(stage_dir: Path, alone: bool = False) -> None:
    """PORT-56: Apply G3X_MOVIE_NOLIMIT=1 compile flags, headers, and stubs."""
    apply_movie_status_staging_patches(stage_dir, alone=alone)

    # Ensure kbd.c calls g3x_movie_nolimit_poll inside my_kbd_read_keys
    kbd_c = stage_dir / "platform/g3x/kbd.c"
    if kbd_c.is_file():
        kbd_text = kbd_c.read_text(encoding="utf-8")
        if "g3x_movie_nolimit_poll" not in kbd_text:
            anchor = "kbd_update_physw_bits();\n"
            if anchor in kbd_text:
                replacement = (
                    "kbd_update_physw_bits();\n"
                    "#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)\n"
                    "    extern void g3x_movie_nolimit_poll(void);\n"
                    "    g3x_movie_nolimit_poll();\n"
                    "#endif\n"
                )
                kbd_text = kbd_text.replace(anchor, replacement, 1)
                kbd_c.write_text(kbd_text, encoding="utf-8")

    # Update makefiles with -DG3X_MOVIE_NOLIMIT=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "-DG3X_MOVIE_NOLIMIT=1" not in text:
            if "CFLAGS += -DG3X_MOVIE_STATUS=1" in text:
                text = text.replace("CFLAGS += -DG3X_MOVIE_STATUS=1", "CFLAGS += -DG3X_MOVIE_STATUS=1 -DG3X_MOVIE_NOLIMIT=1")
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_NOLIMIT=1", 1)
            elif "CFLAGS =" in text:
                text = text.replace("CFLAGS =", "CFLAGS = -DG3X_MOVIE_NOLIMIT=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_NOLIMIT=1\n"
        mpath.write_text(text, encoding="utf-8")


def apply_movie_autocont_staging_patches(stage_dir: Path, alone: bool = False) -> None:
    """PORT-57: Apply G3X_MOVIE_AUTOCONT=1 compile flags, headers, stubs, and kbd poll hook."""
    apply_movie_status_staging_patches(stage_dir, alone=alone)

    # Ensure kbd.c calls g3x_movie_autocont_poll inside my_kbd_read_keys (after g3x_movie_nolimit_poll if present)
    kbd_c = stage_dir / "platform/g3x/kbd.c"
    if kbd_c.is_file():
        kbd_text = kbd_c.read_text(encoding="utf-8")
        if "g3x_movie_autocont_poll" not in kbd_text:
            nolimit_block = (
                "#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)\n"
                "    extern void g3x_movie_nolimit_poll(void);\n"
                "    g3x_movie_nolimit_poll();\n"
                "#endif\n"
            )
            autocont_block = (
                "#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)\n"
                "    extern void g3x_movie_autocont_poll(void);\n"
                "    g3x_movie_autocont_poll();\n"
                "#endif\n"
            )
            if nolimit_block in kbd_text:
                kbd_text = kbd_text.replace(nolimit_block, nolimit_block + autocont_block, 1)
                kbd_c.write_text(kbd_text, encoding="utf-8")
            elif "kbd_update_physw_bits();\n" in kbd_text:
                kbd_text = kbd_text.replace(
                    "kbd_update_physw_bits();\n",
                    "kbd_update_physw_bits();\n" + autocont_block,
                    1,
                )
                kbd_c.write_text(kbd_text, encoding="utf-8")

    # Update makefiles with -DG3X_MOVIE_AUTOCONT=1
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "-DG3X_MOVIE_AUTOCONT=1" not in text:
            if "CFLAGS += -DG3X_MOVIE_STATUS=1" in text:
                text = text.replace("CFLAGS += -DG3X_MOVIE_STATUS=1", "CFLAGS += -DG3X_MOVIE_STATUS=1 -DG3X_MOVIE_AUTOCONT=1")
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_AUTOCONT=1", 1)
            elif "CFLAGS =" in text:
                text = text.replace("CFLAGS =", "CFLAGS = -DG3X_MOVIE_AUTOCONT=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_AUTOCONT=1\n"
        mpath.write_text(text, encoding="utf-8")


def apply_movie_autocont_ui_staging_patches(stage_dir: Path) -> None:
    """PORT-58: Apply G3X_MOVIE_AUTOCONT_UI=1 prerequisite checks, menu item in video_submenu, and live redraw."""
    apply_movie_autocont_staging_patches(stage_dir, alone=False)
    shutil.copy2(CHDK_PORT / "platform/g3x/gui_menu.c", stage_dir / "platform/g3x/gui_menu.c")

    # 1. Insert volatile "Auto-Continue Movie" item into video_submenu_items[] in staged core/gui.c
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")
    video_menu_anchor = "static CMenuItem video_submenu_items[] = {\n"
    if "g3x_movie_autocont_menu_change" not in gui_text:
        if gui_text.count(video_menu_anchor) != 1:
            raise RuntimeError("PORT-58 video_submenu_items anchor not found in staged core/gui.c")
        video_menu_replacement = (
            "#if defined(G3X_MOVIE_AUTOCONT_UI) && (G3X_MOVIE_AUTOCONT_UI == 1)\n"
            "extern const char *g3x_movie_autocont_menu_change(int change, int arg);\n"
            "#endif\n"
            "static CMenuItem video_submenu_items[] = {\n"
            "#if defined(G3X_MOVIE_AUTOCONT_UI) && (G3X_MOVIE_AUTOCONT_UI == 1)\n"
            '    MENU_ITEM   (0x5c, (int)"Auto-Continue Movie",          MENUITEM_ENUM,          g3x_movie_autocont_menu_change,     0 ),\n'
            "#endif\n"
        )
        gui_text = gui_text.replace(video_menu_anchor, video_menu_replacement, 1)
        gui_c.write_text(gui_text, encoding="utf-8")

    # 2. Update staged makefiles with prerequisite/incompatibility checks and -DG3X_MOVIE_AUTOCONT_UI=1
    prereq = (
        "ifeq ($(G3X_MOVIE_AUTOCONT_UI),1)\n"
        "ifneq ($(G3X_MOVIE_AUTOCONT),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_STATUS),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_MENU),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_SYNC),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_DBUF),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_KBD_CHECK),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_DIAG),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_SHADOW2),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifeq ($(G3X_CONF_SAVE),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_CONF_SAVE=1)\n"
        "endif\n"
        "ifeq ($(FULL_HOOKS),1)\n"
        "$(error G3X_MOVIE_AUTOCONT_UI=1 is incompatible with FULL_HOOKS=1)\n"
        "endif\n"
        "endif\n\n"
    )
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "ifeq ($(G3X_MOVIE_AUTOCONT_UI),1)" not in text:
            text = prereq + text
        if "-DG3X_MOVIE_AUTOCONT_UI=1" not in text:
            if "-DG3X_MOVIE_AUTOCONT=1" in text:
                text = text.replace("-DG3X_MOVIE_AUTOCONT=1", "-DG3X_MOVIE_AUTOCONT=1 -DG3X_MOVIE_AUTOCONT_UI=1", 1)
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_AUTOCONT_UI=1", 1)
            elif "CFLAGS =" in text:
                text = text.replace("CFLAGS =", "CFLAGS = -DG3X_MOVIE_AUTOCONT_UI=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_AUTOCONT_UI=1\n"
        mpath.write_text(text, encoding="utf-8")


def apply_movie_restart_budget_staging_patches(stage_dir: Path) -> None:
    """PORT-60: Apply G3X_MOVIE_RESTART_BUDGET=1 prerequisite checks, volatile budget menu item, and compile flags."""
    apply_movie_autocont_ui_staging_patches(stage_dir)

    # 1. Insert volatile "Auto-Continue Budget" item into video_submenu_items[] in staged core/gui.c
    gui_c = stage_dir / "core/gui.c"
    gui_text = gui_c.read_text(encoding="utf-8")
    if "g3x_movie_autocont_budget_menu_change" not in gui_text:
        ext_anchor = "extern const char *g3x_movie_autocont_menu_change(int change, int arg);\n"
        item_anchor = '    MENU_ITEM   (0x5c, (int)"Auto-Continue Movie",          MENUITEM_ENUM,          g3x_movie_autocont_menu_change,     0 ),\n'
        if gui_text.count(ext_anchor) != 1 or gui_text.count(item_anchor) != 1:
            raise RuntimeError("PORT-60 video_submenu_items anchor not found in staged core/gui.c")
        gui_text = gui_text.replace(
            ext_anchor,
            ext_anchor
            + "#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)\n"
            + "extern const char *g3x_movie_autocont_budget_menu_change(int change, int arg);\n"
            + "#endif\n",
            1,
        )
        gui_text = gui_text.replace(
            item_anchor,
            item_anchor
            + "#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)\n"
            + '    MENU_ITEM   (0x5c, (int)"Auto-Continue Budget",         MENUITEM_ENUM,          g3x_movie_autocont_budget_menu_change, 0 ),\n'
            + "#endif\n",
            1,
        )
        gui_c.write_text(gui_text, encoding="utf-8")

    # 2. Update staged makefiles with prerequisite/incompatibility checks and -DG3X_MOVIE_RESTART_BUDGET=1
    prereq = (
        "ifeq ($(G3X_MOVIE_RESTART_BUDGET),1)\n"
        "ifneq ($(G3X_MOVIE_AUTOCONT_UI),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_AUTOCONT),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_MOVIE_STATUS),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_MENU),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_SYNC),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_DBUF),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_NOOVERDRAW),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_KBD_CHECK),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_DIAG),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifneq ($(G3X_GUI_SHADOW2),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)\n"
        "endif\n"
        "ifeq ($(G3X_CONF_SAVE),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 is incompatible with G3X_CONF_SAVE=1)\n"
        "endif\n"
        "ifeq ($(FULL_HOOKS),1)\n"
        "$(error G3X_MOVIE_RESTART_BUDGET=1 is incompatible with FULL_HOOKS=1)\n"
        "endif\n"
        "endif\n\n"
    )
    for rel in ["platform/g3x/Makefile", "platform/g3x/sub/110c/Makefile"]:
        mpath = stage_dir / rel
        text = mpath.read_text(encoding="utf-8")
        if "ifeq ($(G3X_MOVIE_RESTART_BUDGET),1)" not in text:
            text = prereq + text
        if "-DG3X_MOVIE_RESTART_BUDGET=1" not in text:
            if "-DG3X_MOVIE_AUTOCONT_UI=1" in text:
                text = text.replace(
                    "-DG3X_MOVIE_AUTOCONT_UI=1",
                    "-DG3X_MOVIE_AUTOCONT_UI=1 -DG3X_MOVIE_RESTART_BUDGET=1",
                    1,
                )
            elif "CFLAGS +=" in text:
                text = text.replace("CFLAGS +=", "CFLAGS += -DG3X_MOVIE_RESTART_BUDGET=1", 1)
            elif "CFLAGS =" in text:
                text = text.replace("CFLAGS =", "CFLAGS = -DG3X_MOVIE_RESTART_BUDGET=1", 1)
            else:
                text += "\nCFLAGS += -DG3X_MOVIE_RESTART_BUDGET=1\n"
        mpath.write_text(text, encoding="utf-8")


def build_port43_dbuf(
    clean_stage: bool = True,
    keep_stage: bool = True,
    full_hooks: bool = False,
    no_overdraw: bool = False,
    out_dir: Path | str | None = None,
    kbd_check: bool = False,
    gui_diag: bool = False,
    shadow2: bool = False,
    gui_sync: bool = False,
    gui_menu: bool = False,
    gui_restore2: bool = False,
    playback_menu: bool = False,
    playback_menu_alone: bool = False,
    conf_save: bool = False,
    conf_save_alone: bool = False,
    movie_status: bool = False,
    movie_status_alone: bool = False,
    movie_nolimit: bool = False,
    movie_nolimit_alone: bool = False,
    movie_autocont: bool = False,
    movie_autocont_alone: bool = False,
    movie_autocont_ui: bool = False,
    movie_combined: bool = False,
    movie_restart_budget: bool = False,
    movie_budget_profile: bool = False,
) -> int:
    if movie_budget_profile:
        movie_restart_budget = True
        movie_combined = True
    if movie_combined:
        movie_nolimit = True
        movie_autocont_ui = True
        movie_autocont = True
        movie_status = True
        playback_menu = True
        gui_restore2 = True
        gui_menu = True
        gui_sync = True
        shadow2 = True
        gui_diag = True
        kbd_check = True
        no_overdraw = True
    if movie_restart_budget:
        if conf_save or conf_save_alone:
            print("ERROR: G3X_MOVIE_RESTART_BUDGET=1 is incompatible with G3X_CONF_SAVE=1", file=sys.stderr)
            return 1
        if full_hooks:
            print("ERROR: G3X_MOVIE_RESTART_BUDGET=1 is incompatible with FULL_HOOKS=1", file=sys.stderr)
            return 1
        if movie_nolimit_alone or movie_autocont_alone or movie_status_alone or playback_menu_alone:
            print(
                "ERROR: G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                file=sys.stderr,
            )
            return 1
        if not (
            movie_autocont_ui
            and movie_autocont
            and movie_status
            and gui_menu
            and gui_sync
            and shadow2
            and gui_diag
            and kbd_check
            and no_overdraw
        ):
            print(
                "ERROR: G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                file=sys.stderr,
            )
            return 1
    if movie_autocont_ui:
        if conf_save or conf_save_alone:
            print("ERROR: G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_CONF_SAVE=1", file=sys.stderr)
            return 1
        if full_hooks:
            print("ERROR: G3X_MOVIE_AUTOCONT_UI=1 is incompatible with FULL_HOOKS=1", file=sys.stderr)
            return 1
        if movie_nolimit_alone or movie_autocont_alone or movie_status_alone or playback_menu_alone:
            print(
                "ERROR: G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                file=sys.stderr,
            )
            return 1
        if not (
            movie_autocont
            and movie_status
            and gui_menu
            and gui_sync
            and shadow2
            and gui_diag
            and kbd_check
            and no_overdraw
        ):
            print(
                "ERROR: G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                file=sys.stderr,
            )
            return 1
    if (movie_autocont or movie_autocont_alone) and (movie_nolimit or movie_nolimit_alone) and not movie_autocont_ui:
        print(
            "ERROR: Combining G3X_MOVIE_NOLIMIT=1 and G3X_MOVIE_AUTOCONT=1 requires G3X_MOVIE_AUTOCONT_UI=1",
            file=sys.stderr,
        )
        return 1
    if movie_autocont or movie_autocont_alone:
        if conf_save or conf_save_alone:
            print("ERROR: G3X_MOVIE_AUTOCONT=1 is incompatible with G3X_CONF_SAVE=1", file=sys.stderr)
            return 1
        if full_hooks:
            print("ERROR: G3X_MOVIE_AUTOCONT=1 is incompatible with FULL_HOOKS=1", file=sys.stderr)
            return 1
    if movie_nolimit or movie_nolimit_alone:
        if conf_save or conf_save_alone:
            print("ERROR: G3X_MOVIE_NOLIMIT=1 is incompatible with G3X_CONF_SAVE=1", file=sys.stderr)
            return 1
        if full_hooks:
            print("ERROR: G3X_MOVIE_NOLIMIT=1 is incompatible with FULL_HOOKS=1", file=sys.stderr)
            return 1
    if conf_save or conf_save_alone:
        print("ERROR: G3X_CONF_SAVE=1 (PORT-54) is excluded from this build", file=sys.stderr)
        return 1
    has_menu_or_dbuf = (
        playback_menu
        or playback_menu_alone
        or gui_restore2
        or gui_menu
        or gui_sync
        or shadow2
        or gui_diag
        or kbd_check
        or no_overdraw
        or full_hooks
    )
    if movie_autocont:
        movie_status = True
    if movie_autocont and not has_menu_or_dbuf and not movie_nolimit:
        movie_autocont_alone = True
    if movie_nolimit:
        movie_status = True
    if movie_nolimit and not has_menu_or_dbuf and not movie_autocont:
        movie_nolimit_alone = True
    if movie_status and not has_menu_or_dbuf and not movie_nolimit and not movie_autocont:
        movie_status_alone = True

    if movie_autocont_alone:
        movie_autocont = True
        movie_status = True
        movie_status_alone = False
        movie_nolimit = False
        movie_nolimit_alone = False
        playback_menu = False
        playback_menu_alone = False
        gui_restore2 = False
        gui_menu = False
        gui_sync = False
        shadow2 = False
        gui_diag = False
        kbd_check = False
        no_overdraw = False
        full_hooks = False
    elif movie_nolimit_alone:
        movie_nolimit = True
        movie_status = True
        movie_status_alone = False
        playback_menu = False
        playback_menu_alone = False
        gui_restore2 = False
        gui_menu = False
        gui_sync = False
        shadow2 = False
        gui_diag = False
        kbd_check = False
        no_overdraw = False
        full_hooks = False
    elif movie_status_alone:
        movie_status = True
        playback_menu = False
        playback_menu_alone = False
        gui_restore2 = False
        gui_menu = False
        gui_sync = False
        shadow2 = False
        gui_diag = False
        kbd_check = False
        no_overdraw = False
        full_hooks = False
    elif playback_menu_alone:
        playback_menu = True
        gui_restore2 = False
        gui_menu = False
        gui_sync = False
        shadow2 = False
        gui_diag = False
        kbd_check = False
        no_overdraw = False
        full_hooks = False
    elif gui_restore2:
        gui_menu = True
    if gui_menu:
        gui_sync = True
    if gui_sync:
        shadow2 = True
    if shadow2:
        gui_diag = True
    if gui_diag:
        no_overdraw = True
        kbd_check = True

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
    elif movie_restart_budget:
        effective_out_dir = REPO_ROOT / "out" / "port60-movie-restart-budget"
    elif movie_autocont_ui and movie_nolimit:
        effective_out_dir = REPO_ROOT / "out" / "port59-movie-combined"
    elif movie_autocont_ui:
        effective_out_dir = REPO_ROOT / "out" / "port58-movie-control"
    elif movie_autocont_alone:
        effective_out_dir = REPO_ROOT / "out" / "build-autocont-alone"
    elif movie_autocont:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port57-movie-autocont" + suffix)
    elif movie_nolimit_alone:
        effective_out_dir = REPO_ROOT / "out" / "build-nolimit-alone"
    elif movie_nolimit:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port56-movie-nolimit" + suffix)
    elif movie_status_alone:
        effective_out_dir = REPO_ROOT / "out" / "build-movie-alone"
    elif movie_status:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port55-movie-status" + suffix)
    elif playback_menu_alone:
        effective_out_dir = REPO_ROOT / "out" / "port53-playback-menu-alone"
    elif playback_menu:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port53-playback-menu" + suffix)
    elif gui_restore2:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port51-restore2-core" + suffix)
    elif gui_menu:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port50-gui-menu" + suffix)
    elif gui_sync:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port49-gui-sync" + suffix)
    elif shadow2:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port48-shadow-alloc" + suffix)
    elif gui_diag:
        suffix = "-full-hooks" if full_hooks else ""
        effective_out_dir = REPO_ROOT / "out" / ("port47-gui-diag" + suffix)
    elif kbd_check:
        suffix = "-no-overdraw" if no_overdraw else ""
        if full_hooks:
            suffix += "-full-hooks"
        effective_out_dir = REPO_ROOT / "out" / ("port46-kbd-check" + suffix)
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
        seed_dir = _ensure_dbuf_seed_stage()
        print(f"Staging CHDK tree to {effective_stage_dir}...")
        shutil.copytree(seed_dir, effective_stage_dir, symlinks=True)

    _clean_platform_and_core_artifacts(effective_stage_dir)

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
    if not playback_menu_alone and not movie_status_alone and not movie_nolimit_alone and not movie_autocont_alone:
        if full_hooks:
            print("FULL_HOOKS=1 enabled: Applying FINSIG-confirmed hook staging patches...")
            apply_full_hooks_staging_patches(effective_stage_dir)

        # Apply GUI fix patches
        print("G3X_GUI_FIX=1: Applying GUI flicker, colour and 2x font staging patches...")
        if kbd_check:
            apply_gui_fix_staging_patches(effective_stage_dir, legacy_dbuf_snapshot=False)
        else:
            apply_gui_fix_staging_patches(effective_stage_dir)

        # Apply DBUF compile flag patches
        print("G3X_GUI_DBUF=1: Applying double-buffered overlay staging patches...")
        apply_dbuf_staging_patches(effective_stage_dir)

        # Apply NOOVERDRAW compile flag and scheduler/sentinel patches if requested
        if no_overdraw:
            print("G3X_GUI_NOOVERDRAW=1: Applying opt-in overlay protection staging patches...")
            apply_no_overdraw_staging_patches(effective_stage_dir)

        if kbd_check:
            print("G3X_KBD_CHECK=1: Applying ALT key-check draw hooks...")
            apply_kbd_check_staging_patches(effective_stage_dir)

        if gui_diag:
            print("G3X_GUI_DIAG=1: Applying overdraw/restore counters, shadow-blit-only restore, and sibling suppression...")
            apply_gui_diag_staging_patches(effective_stage_dir)

        if shadow2:
            print("G3X_GUI_SHADOW2=1: Applying ordered shadow fallback chain (exmem -> rect -> idx) and GetMemInfo diagnostic...")
            apply_shadow2_staging_patches(effective_stage_dir)

        if gui_sync:
            print("G3X_GUI_SYNC=1: Applying synchronous display-flip hook at 0x0000E26C and target-buffer shadow restore...")
            apply_gui_sync_staging_patches(effective_stage_dir)

        if gui_menu:
            print("G3X_GUI_MENU=1: Applying standard CHDK menu hooks and unwrapping file I/O stubs...")
            apply_gui_menu_staging_patches(effective_stage_dir)

        if gui_restore2:
            print("G3X_GUI_RESTORE2=1: Applying rect-only shadow blit, duration timing, and restore path counters...")
            apply_gui_restore2_staging_patches(effective_stage_dir)

    if playback_menu:
        print("G3X_PLAYBACK_MENU=1: Applying playback-mode ALT menu hooks and key mapping...")
        apply_playback_menu_staging_patches(effective_stage_dir, alone=playback_menu_alone)

    if movie_nolimit:
        print("G3X_MOVIE_NOLIMIT=1: Applying movie time-limit defeat and LIM: diag marker...")
        apply_movie_nolimit_staging_patches(effective_stage_dir, alone=movie_nolimit_alone)
    elif movie_status and not movie_autocont:
        print("G3X_MOVIE_STATUS=1: Applying read-only movie status accessor and MOV: diag marker...")
        apply_movie_status_staging_patches(effective_stage_dir, alone=movie_status_alone)

    if movie_restart_budget:
        print("G3X_MOVIE_RESTART_BUDGET=1: Applying volatile finite session restart budget (1/2/3, default 1)...")
        apply_movie_restart_budget_staging_patches(effective_stage_dir)
    elif movie_autocont_ui:
        print("G3X_MOVIE_AUTOCONT_UI=1: Applying volatile movie continuation menu control and status readout...")
        apply_movie_autocont_ui_staging_patches(effective_stage_dir)
    elif movie_autocont:
        print("G3X_MOVIE_AUTOCONT=1: Applying gated movie automatic continuation state machine...")
        apply_movie_autocont_staging_patches(effective_stage_dir, alone=movie_autocont_alone)

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
                "G3X_DISABLE_CARD_WRITES=1",
                "OPT_DISABLE_FILE_WRITES=1",
            ]
            if movie_status:
                clean_cmd.append("G3X_MOVIE_STATUS=1")
            if movie_nolimit:
                clean_cmd.append("G3X_MOVIE_NOLIMIT=1")
            if movie_autocont:
                clean_cmd.append("G3X_MOVIE_AUTOCONT=1")
            if movie_autocont_ui:
                clean_cmd.append("G3X_MOVIE_AUTOCONT_UI=1")
            if movie_restart_budget:
                clean_cmd.append("G3X_MOVIE_RESTART_BUDGET=1")
            if not playback_menu_alone and not movie_status_alone and not movie_nolimit_alone and not movie_autocont_alone:
                clean_cmd.extend(["G3X_GUI_FIX=1", "G3X_GUI_DBUF=1"])
                if no_overdraw:
                    clean_cmd.append("G3X_GUI_NOOVERDRAW=1")
                if kbd_check:
                    clean_cmd.append("G3X_KBD_CHECK=1")
                if gui_diag:
                    clean_cmd.append("G3X_GUI_DIAG=1")
                if shadow2:
                    clean_cmd.append("G3X_GUI_SHADOW2=1")
                if gui_sync:
                    clean_cmd.append("G3X_GUI_SYNC=1")
                if gui_menu:
                    clean_cmd.append("G3X_GUI_MENU=1")
                if gui_restore2:
                    clean_cmd.append("G3X_GUI_RESTORE2=1")
                if full_hooks:
                    clean_cmd.append("FULL_HOOKS=1")
            if playback_menu:
                clean_cmd.append("G3X_PLAYBACK_MENU=1")
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
        "G3X_DISABLE_CARD_WRITES=1",
        "OPT_DISABLE_FILE_WRITES=1",
    ]
    if movie_status:
        cmd.append("G3X_MOVIE_STATUS=1")
    if movie_nolimit:
        cmd.append("G3X_MOVIE_NOLIMIT=1")
    if movie_autocont:
        cmd.append("G3X_MOVIE_AUTOCONT=1")
    if movie_autocont_ui:
        cmd.append("G3X_MOVIE_AUTOCONT_UI=1")
    if movie_restart_budget:
        cmd.append("G3X_MOVIE_RESTART_BUDGET=1")
    cmd.extend([
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
    ])
    if not playback_menu_alone and not movie_status_alone and not movie_nolimit_alone and not movie_autocont_alone:
        cmd.extend(["G3X_GUI_FIX=1", "G3X_GUI_DBUF=1"])
        if no_overdraw:
            cmd.append("G3X_GUI_NOOVERDRAW=1")
        if kbd_check:
            cmd.append("G3X_KBD_CHECK=1")
        if gui_diag:
            cmd.append("G3X_GUI_DIAG=1")
        if shadow2:
            cmd.append("G3X_GUI_SHADOW2=1")
        if gui_sync:
            cmd.append("G3X_GUI_SYNC=1")
        if gui_menu:
            cmd.append("G3X_GUI_MENU=1")
        if gui_restore2:
            cmd.append("G3X_GUI_RESTORE2=1")
        if full_hooks:
            cmd.append("FULL_HOOKS=1")
    if playback_menu:
        cmd.append("G3X_PLAYBACK_MENU=1")
    cmd.extend(["SKIP_TOOLS=1", "SKIP_MODULES=1", "SKIP_CHDK=1", "fir"])

    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    gcc_tmp = REPO_ROOT / "out" / ".tmp_gcc"
    gcc_tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(gcc_tmp)
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if "MAKEFLAGS" not in env and wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    env["G3X_DISABLE_CARD_WRITES"] = "1"
    env["OPT_DISABLE_FILE_WRITES"] = "1"
    if movie_status:
        env["G3X_MOVIE_STATUS"] = "1"
    if movie_nolimit:
        env["G3X_MOVIE_NOLIMIT"] = "1"
    if movie_autocont:
        env["G3X_MOVIE_AUTOCONT"] = "1"
    if movie_autocont_ui:
        env["G3X_MOVIE_AUTOCONT_UI"] = "1"
    if movie_restart_budget:
        env["G3X_MOVIE_RESTART_BUDGET"] = "1"
    if not playback_menu_alone and not movie_status_alone and not movie_nolimit_alone and not movie_autocont_alone:
        env["G3X_GUI_FIX"] = "1"
        env["G3X_GUI_DBUF"] = "1"
        if no_overdraw:
            env["G3X_GUI_NOOVERDRAW"] = "1"
        if kbd_check:
            env["G3X_KBD_CHECK"] = "1"
        if gui_diag:
            env["G3X_GUI_DIAG"] = "1"
        if shadow2:
            env["G3X_GUI_SHADOW2"] = "1"
        if gui_sync:
            env["G3X_GUI_SYNC"] = "1"
        if gui_menu:
            env["G3X_GUI_MENU"] = "1"
        if gui_restore2:
            env["G3X_GUI_RESTORE2"] = "1"
        if full_hooks:
            env["FULL_HOOKS"] = "1"
    if playback_menu:
        env["G3X_PLAYBACK_MENU"] = "1"

    res = subprocess.run(cmd, cwd=str(effective_stage_dir), env=env)
    shutil.rmtree(gcc_tmp, ignore_errors=True)
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
    if movie_autocont_alone:
        build_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_MOVIE_STATUS=1",
            "G3X_MOVIE_AUTOCONT=1",
        ]
    elif movie_nolimit_alone:
        build_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_MOVIE_STATUS=1",
            "G3X_MOVIE_NOLIMIT=1",
        ]
    elif movie_status_alone:
        build_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_MOVIE_STATUS=1",
        ]
    elif playback_menu_alone:
        build_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_PLAYBACK_MENU=1",
        ]
    else:
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
        if kbd_check:
            build_flags.append("G3X_KBD_CHECK=1")
        if gui_diag:
            build_flags.append("G3X_GUI_DIAG=1")
        if shadow2:
            build_flags.append("G3X_GUI_SHADOW2=1")
        if gui_sync:
            build_flags.append("G3X_GUI_SYNC=1")
        if gui_menu:
            build_flags.append("G3X_GUI_MENU=1")
        if gui_restore2:
            build_flags.append("G3X_GUI_RESTORE2=1")
        if playback_menu:
            build_flags.append("G3X_PLAYBACK_MENU=1")
        if movie_status:
            build_flags.append("G3X_MOVIE_STATUS=1")
        if movie_nolimit:
            build_flags.append("G3X_MOVIE_NOLIMIT=1")
        if movie_autocont:
            build_flags.append("G3X_MOVIE_AUTOCONT=1")
        if movie_autocont_ui:
            build_flags.append("G3X_MOVIE_AUTOCONT_UI=1")
        if movie_restart_budget:
            build_flags.append("G3X_MOVIE_RESTART_BUDGET=1")
        if full_hooks:
            build_flags.insert(1, "FULL_HOOKS=1")

    manifest_name = "port45_no_overdraw_manifest.json" if no_overdraw else "port43_dbuf_manifest.json"
    if kbd_check:
        manifest_name = "port46_kbd_check_manifest.json"
    if gui_diag:
        manifest_name = "port47_gui_diag_manifest.json"
    if shadow2:
        manifest_name = "port48_shadow_alloc_manifest.json"
    if gui_sync:
        manifest_name = "port49_gui_sync_manifest.json"
    if gui_menu:
        manifest_name = "port50_gui_menu_manifest.json"
    if gui_restore2:
        manifest_name = "port51_restore2_core_manifest.json"
    if playback_menu_alone:
        manifest_name = "port53_playback_menu_alone_manifest.json"
    elif playback_menu:
        manifest_name = "port53_playback_menu_manifest.json"
    if movie_restart_budget:
        manifest_name = "port60_movie_restart_budget_manifest.json"
    elif movie_autocont_ui and movie_nolimit:
        manifest_name = "port59_movie_combined_manifest.json"
    elif movie_autocont_ui:
        manifest_name = "port58_movie_control_manifest.json"
    elif movie_autocont_alone:
        manifest_name = "port57_movie_autocont_alone_manifest.json"
    elif movie_autocont:
        manifest_name = "port57_movie_autocont_manifest.json"
    elif movie_nolimit_alone:
        manifest_name = "port56_movie_nolimit_alone_manifest.json"
    elif movie_nolimit:
        manifest_name = "port56_movie_nolimit_manifest.json"
    elif movie_status_alone:
        manifest_name = "port55_movie_status_alone_manifest.json"
    elif movie_status:
        manifest_name = "port55_movie_status_manifest.json"
    manifest_data: dict[str, object] = {
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
    if gui_diag or playback_menu or movie_status or movie_autocont:
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
        manifest_data["core_end"] = core_end_hex
        manifest_data["_end"] = core_end_hex
        artifacts_dict = manifest_data["artifacts"]
        assert isinstance(artifacts_dict, dict)
        artifacts_dict["core_end"] = core_end_hex
        artifacts_dict["_end"] = core_end_hex

    if gui_menu or playback_menu or movie_autocont:
        manifest_data["card_writes"] = "disabled"
        manifest_data["card_writes_note"] = (
            "Config save disabled under G3X_DISABLE_CARD_WRITES=1 OPT_DISABLE_FILE_WRITES=1 "
            "(SAVE:OFF); blocking write wrappers (write, fwrite, open, fopen, creat, mkdir, remove, rename) remain active in link; physical SD card remains write-protected (LOCK)"
        )
        build_dict = manifest_data["build"]
        assert isinstance(build_dict, dict)
        build_dict["card_writes"] = "disabled"
        build_dict["card_writes_note"] = (
            "Config save disabled under G3X_DISABLE_CARD_WRITES=1 OPT_DISABLE_FILE_WRITES=1 "
            "(SAVE:OFF); blocking write wrappers (write, fwrite, open, fopen, creat, mkdir, remove, rename) remain active in link; physical SD card remains write-protected (LOCK)"
        )
        if gui_menu or playback_menu:
            manifest_data["removed_wrappers"] = [
                "conf_save",
                "save_params_values",
                "save_int_value_file",
            ]

    if movie_restart_budget:
        manifest_data["manifest_id"] = "port60_movie_restart_budget_manifest"
        manifest_data["milestone"] = "PORT-60"
        manifest_data["origin_main_baseline"] = "0579e70d39f0bd4156b1266e5187f97275a9b0a8"
        manifest_data["candidate_source_base"] = "0579e70d39f0bd4156b1266e5187f97275a9b0a8"
        manifest_data["integration_parent"] = "5ed0b6a345d5e8d9e4866146451c1c360848553d"
        manifest_data["reused_commits"] = {
            "origin_main_port59": "0579e70d39f0bd4156b1266e5187f97275a9b0a8",
            "port59_build": "32d6e0aa60766fdb4223d86403c37fca2c82c920",
            "port58_movie_control": "6696c8390780043e0c5fc67c306143dacf0bcd7c",
            "port57_movie_autocont": "ed374e7d332bce36a9c76682074aa9516e15e3be",
            "port56_movie_nolimit": "ded3832e4a6cc1cc8401f67cb454d5d420191844",
            "port55_movie_status": "dc915e6257981f48223fa2f38839bc28e31c73cf",
            "port60_budget_interfaces": "85ee3571b3624d2e26c81d77136ca7d1b0627f2e",
        }
        manifest_data["excluded_commits"] = {
            "port54_conf_save": "af2578089a39e9a2143f83003e92ea5236d542bc",
        }
        manifest_data["restart_budget_policy"] = {
            "allowances": [1, 2, 3],
            "default_allowance": 1,
            "boot_enabled": False,
            "volatile_only": True,
            "confirmed_idle_required_for_edits": True,
            "deliberate_physical_start_initializes_session": True,
            "atomic_pre_input_reservation": True,
            "no_refund_on_failed_or_interrupted_attempts": True,
        }
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-nolimit --movie-autocont --movie-autocont-ui --movie-restart-budget --out-dir out/port60-movie-restart-budget"
        )
        manifest_data["configurations"] = {
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
            "full_candidate": {
                "path": "out/port60-movie-restart-budget/DISKBOOT.BIN",
                "size": out_diskboot.stat().st_size,
                "sha256": sha256_file(out_diskboot),
                "_end": manifest_data.get("_end"),
                "card_writes": "disabled",
            },
        }
    elif movie_autocont_ui and movie_nolimit:
        manifest_data["manifest_id"] = "port59_movie_combined_manifest"
        manifest_data["milestone"] = "PORT-59"
        manifest_data["origin_main_baseline"] = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
        manifest_data["candidate_source_base"] = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
        manifest_data["integration_parent"] = "732fe9a7190e4445d707dd68aae5b65badffc271"
        manifest_data["reused_commits"] = {
            "origin_main": "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5",
            "port55_movie_status": "dc915e6257981f48223fa2f38839bc28e31c73cf",
            "port56_movie_nolimit": "ded3832e4a6cc1cc8401f67cb454d5d420191844",
            "port57_movie_autocont": "ed374e7d332bce36a9c76682074aa9516e15e3be",
            "port58_movie_control": "6696c8390780043e0c5fc67c306143dacf0bcd7c",
            "port59_compat": "c38d6c66dba62ee7b048a0cf56f52cbd1f567adc",
        }
        manifest_data["excluded_commits"] = {
            "port54_conf_save": "af2578089a39e9a2143f83003e92ea5236d542bc",
        }
        manifest_data["source_delta_vs_origin_main"] = {
            "base_commit": "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5",
            "integration_parent": "732fe9a7190e4445d707dd68aae5b65badffc271",
            "port54_conf_save_removed_from_source_delta": True,
            "delivered_paths": [
                "Makefile",
                "chdk-port/platform/g3x/Makefile",
                "chdk-port/platform/g3x/gui_diag.h",
                "chdk-port/platform/g3x/gui_menu.c",
                "chdk-port/platform/g3x/movie_status.h",
                "chdk-port/platform/g3x/sub/110c/makefile.inc",
                "chdk-port/platform/g3x/sub/110c/movie_rec.c",
                "chdk-port/platform/g3x/sub/110c/stubs_min.S",
                "scripts/build_port43_dbuf.py",
            ],
        }
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-nolimit --movie-autocont --movie-autocont-ui --out-dir out/port59-movie-combined"
        )
        manifest_data["configurations"] = {
            "default": {
                "path": "out/build-default/DISKBOOT.BIN",
                "size": 124097,
                "sha256": "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
                "_end": "0x003686b0",
                "card_writes": "disabled"
            },
            "full_candidate": {
                "path": "out/port59-movie-combined/DISKBOOT.BIN",
                "size": out_diskboot.stat().st_size,
                "sha256": sha256_file(out_diskboot),
                "_end": manifest_data.get("_end"),
                "card_writes": "disabled"
            }
        }
    elif movie_autocont_ui:
        manifest_data["manifest_id"] = "port58_movie_control_manifest"
        manifest_data["milestone"] = "PORT-58"
        manifest_data["origin_main_baseline"] = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-autocont --movie-autocont-ui --out-dir out/port58-movie-control"
        )
        manifest_data["configurations"] = {
            "default": {
                "path": "out/build-default/DISKBOOT.BIN",
                "size": 124097,
                "sha256": "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
                "_end": "0x003686b0",
                "card_writes": "disabled"
            },
            "full_candidate": {
                "path": "out/port58-movie-control/DISKBOOT.BIN",
                "size": out_diskboot.stat().st_size,
                "sha256": sha256_file(out_diskboot),
                "_end": manifest_data.get("_end"),
                "card_writes": "disabled"
            }
        }
    elif movie_autocont and not movie_autocont_alone:
        manifest_data["manifest_id"] = "port57_movie_autocont_manifest"
        manifest_data["milestone"] = "PORT-57"
        manifest_data["origin_main_baseline"] = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-autocont --out-dir out/port57-movie-autocont"
        )
        manifest_data["configurations"] = {
            "default": {
                "path": "out/build-default/DISKBOOT.BIN",
                "size": 124097,
                "sha256": "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
                "_end": "0x003686b0",
                "card_writes": "disabled"
            },
            "movie_autocont_alone": {
                "path": "out/build-autocont-alone/DISKBOOT.BIN",
                "size": 126425,
                "sha256": "5162fb5ad30e9985a3904c5028fc59d4419c87a783921d86a9e46f28026c5cce",
                "_end": "0x00369030",
                "card_writes": "disabled"
            },
            "full_candidate": {
                "path": "out/port57-movie-autocont/DISKBOOT.BIN",
                "size": 134617,
                "sha256": "2da299cdc9b336fe74e726ca33f081a0cd5f88cebad227a317cff2c5d764eec7",
                "_end": "0x0036b410",
                "card_writes": "disabled"
            }
        }
    elif movie_autocont_alone:
        manifest_data["manifest_id"] = "port57_movie_autocont_alone_manifest"
        manifest_data["milestone"] = "PORT-57"
        manifest_data["origin_main_baseline"] = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --movie-autocont-alone --out-dir out/build-autocont-alone"
        )
    elif movie_nolimit and not movie_nolimit_alone:
        manifest_data["manifest_id"] = "port56_movie_nolimit_manifest"
        manifest_data["milestone"] = "PORT-56"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-nolimit --out-dir out/port56-movie-nolimit"
        )
        manifest_data["configurations"] = {
            "default": {
                "path": "out/build-default/DISKBOOT.BIN",
                "size": 124097,
                "sha256": "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
                "_end": "0x003686b0",
                "card_writes": "disabled",
                "diag_status": "LIM:?"
            },
            "movie_nolimit_alone": {
                "path": "out/build-nolimit-alone/DISKBOOT.BIN",
                "size": 124145,
                "sha256": "12c0635ffd11d2c6a1d158aaac436885a4a3b9b7830841a8c65410c193439b33",
                "_end": "0x003686e0",
                "card_writes": "disabled",
                "diag_status": "LIM:OFF/LIM:ON/LIM:?"
            },
            "full_candidate": {
                "path": "out/port56-movie-nolimit/DISKBOOT.BIN",
                "size": 132385,
                "sha256": "c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352",
                "_end": "0x0036aaf0",
                "card_writes": "disabled",
                "diag_status": "LIM:OFF/LIM:ON/LIM:?"
            }
        }
    elif movie_status and not movie_status_alone and not movie_nolimit and not movie_autocont:
        manifest_data["manifest_id"] = "port55_movie_status_manifest"
        manifest_data["milestone"] = "PORT-55"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --out-dir out/port55-movie-status"
        )
    elif playback_menu and not playback_menu_alone:
        manifest_data["manifest_id"] = "port53_playback_menu_manifest"
        manifest_data["milestone"] = "PORT-53"
        manifest_data["command"] = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --out-dir out/port53-playback-menu"
        )

    manifest_path = effective_out_dir / manifest_name
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")
    print(f"[OK] Manifest written to {manifest_path}")

    if playback_menu and not playback_menu_alone and not movie_status and not movie_nolimit and not movie_autocont:
        repo_manifest = REPO_ROOT / "manifests" / "port53_playback_menu_manifest.json"
        repo_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path, repo_manifest)
        print(f"[OK] Candidate manifest copied to {repo_manifest}")

    # Convenience aliases
    with open(effective_out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")

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
    parser.add_argument("--kbd-check", action="store_true", default=os.environ.get("G3X_KBD_CHECK") == "1", help="Enable G3X_KBD_CHECK=1 ALT key diagnostic (also accepts environment flag)")
    parser.add_argument("--gui-diag", action="store_true", default=os.environ.get("G3X_GUI_DIAG") == "1", help="Enable G3X_GUI_DIAG=1 overdraw/restore counters, shadow-blit-only restore, and sibling suppression")
    parser.add_argument("--shadow2", action="store_true", default=os.environ.get("G3X_GUI_SHADOW2") == "1", help="Enable G3X_GUI_SHADOW2=1 ordered shadow allocation fallback chain (exmem -> rect -> idx) and GetMemInfo diagnostic")
    parser.add_argument("--gui-sync", action="store_true", default=os.environ.get("G3X_GUI_SYNC") == "1", help="Enable G3X_GUI_SYNC=1 synchronous display-flip restore hook at 0x0000E26C")
    parser.add_argument("--gui-menu", action="store_true", default=os.environ.get("G3X_GUI_MENU") == "1", help="Enable G3X_GUI_MENU=1 standard CHDK menu and FINSIG file I/O stubs")
    parser.add_argument("--gui-restore2", action="store_true", default=os.environ.get("G3X_GUI_RESTORE2") == "1", help="Enable G3X_GUI_RESTORE2=1 rect-only blit, blit duration timing, and restore path breakdown")
    parser.add_argument("--playback-menu", action="store_true", default=os.environ.get("G3X_PLAYBACK_MENU") == "1", help="Enable G3X_PLAYBACK_MENU=1 playback-mode ALT menu hooks and key mapping")
    parser.add_argument("--playback-menu-alone", action="store_true", help="Build G3X_PLAYBACK_MENU=1 alone without DBUF/menu stack")
    parser.add_argument("--conf-save", action="store_true", default=os.environ.get("G3X_CONF_SAVE") == "1", help="Enable G3X_CONF_SAVE=1 opt-in settings save with central A/CHDK/ path check")
    parser.add_argument("--conf-save-alone", action="store_true", help="Build G3X_CONF_SAVE=1 alone without DBUF/menu stack")
    parser.add_argument("--movie-status", action="store_true", default=os.environ.get("G3X_MOVIE_STATUS") == "1", help="Enable G3X_MOVIE_STATUS=1 read-only movie state accessor and MOV: diag marker")
    parser.add_argument("--movie-status-alone", action="store_true", help="Build G3X_MOVIE_STATUS=1 alone without DBUF/menu stack")
    parser.add_argument("--movie-nolimit", action="store_true", default=os.environ.get("G3X_MOVIE_NOLIMIT") == "1", help="Enable G3X_MOVIE_NOLIMIT=1 runtime frame-limit defeat and LIM: diag marker")
    parser.add_argument("--movie-nolimit-alone", action="store_true", help="Build G3X_MOVIE_NOLIMIT=1 alone without DBUF/menu stack")
    parser.add_argument("--movie-autocont", action="store_true", default=os.environ.get("G3X_MOVIE_AUTOCONT") == "1", help="Enable G3X_MOVIE_AUTOCONT=1 gated movie automatic continuation")
    parser.add_argument("--movie-autocont-alone", action="store_true", help="Build G3X_MOVIE_AUTOCONT=1 alone without DBUF/menu stack")
    parser.add_argument("--movie-autocont-ui", action="store_true", default=os.environ.get("G3X_MOVIE_AUTOCONT_UI") == "1", help="Enable G3X_MOVIE_AUTOCONT_UI=1 volatile movie continuation menu toggle and status readout")
    parser.add_argument("--movie-combined", action="store_true", default=os.environ.get("G3X_MOVIE_COMBINED") == "1", help="Enable PORT-59 combined movie profile (G3X_MOVIE_NOLIMIT=1 + G3X_MOVIE_AUTOCONT_UI=1 with all prerequisites)")
    parser.add_argument("--movie-restart-budget", "--movie-budget", dest="movie_restart_budget", action="store_true", default=os.environ.get("G3X_MOVIE_RESTART_BUDGET") == "1", help="Enable G3X_MOVIE_RESTART_BUDGET=1 volatile finite session restart budget (allowances 1/2/3, default 1)")
    parser.add_argument("--movie-budget-profile", action="store_true", default=os.environ.get("G3X_MOVIE_BUDGET_PROFILE") == "1", help="Enable PORT-60 movie restart budget profile (PORT-59 combined profile + G3X_MOVIE_RESTART_BUDGET=1)")
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
        kbd_check=args.kbd_check,
        gui_diag=args.gui_diag,
        shadow2=args.shadow2,
        gui_sync=args.gui_sync,
        gui_menu=args.gui_menu,
        gui_restore2=args.gui_restore2,
        playback_menu=args.playback_menu,
        playback_menu_alone=args.playback_menu_alone,
        conf_save=args.conf_save,
        conf_save_alone=args.conf_save_alone,
        movie_status=args.movie_status,
        movie_status_alone=args.movie_status_alone,
        movie_nolimit=args.movie_nolimit,
        movie_nolimit_alone=args.movie_nolimit_alone,
        movie_autocont=args.movie_autocont,
        movie_autocont_alone=args.movie_autocont_alone,
        movie_autocont_ui=args.movie_autocont_ui,
        movie_combined=args.movie_combined,
        movie_restart_budget=args.movie_restart_budget,
        movie_budget_profile=args.movie_budget_profile,
    )



if __name__ == "__main__":
    sys.exit(main())
