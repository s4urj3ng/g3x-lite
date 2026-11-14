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
        _remove_prototype_files(SEED_STAGE_DIR)
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
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    env["G3X_GUI_FIX"] = "1"
    env["G3X_GUI_DBUF"] = "1"
    subprocess.run(cmd, cwd=str(SEED_STAGE_DIR), env=env, check=True, stdout=subprocess.DEVNULL)

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
        " * _exmem_alloc = 0xFC092537 (FINSIG, reference/finsig_gm110c/stubs_entry.S:302) */\n"
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

    pixel_helper_anchor = "void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd)\n"
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
        + pixel_helper_anchor
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

    for odd_val in ["1", "0"]:
        s1_anchor = f"            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, {odd_val});\n"
        s1_repl = (
            "#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)\n"
            f"            g3x_dbuf_shadow2_draw_pixel(offset, y_luma, op, u_val, v_val, {odd_val}, simple_clr[px & 1]);\n"
            "#else\n"
            f"            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, {odd_val});\n"
            "#endif\n"
        )
        draw_text = draw_text.replace(s1_anchor, s1_repl)

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


def build_port43_dbuf(
    clean_stage: bool = True,
    keep_stage: bool = True,
    full_hooks: bool = False,
    no_overdraw: bool = False,
    out_dir: Path | str | None = None,
    kbd_check: bool = False,
    gui_diag: bool = False,
    shadow2: bool = False,
) -> int:
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
            if kbd_check:
                clean_cmd.append("G3X_KBD_CHECK=1")
            if gui_diag:
                clean_cmd.append("G3X_GUI_DIAG=1")
            if shadow2:
                clean_cmd.append("G3X_GUI_SHADOW2=1")
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
    if kbd_check:
        cmd.append("G3X_KBD_CHECK=1")
    if gui_diag:
        cmd.append("G3X_GUI_DIAG=1")
    if shadow2:
        cmd.append("G3X_GUI_SHADOW2=1")
    if full_hooks:
        cmd.append("FULL_HOOKS=1")
    cmd.extend(["SKIP_TOOLS=1", "SKIP_MODULES=1", "SKIP_CHDK=1", "fir"])

    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if "MAKEFLAGS" not in env and wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
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
    if kbd_check:
        build_flags.append("G3X_KBD_CHECK=1")
    if gui_diag:
        build_flags.append("G3X_GUI_DIAG=1")
    if shadow2:
        build_flags.append("G3X_GUI_SHADOW2=1")
    if full_hooks:
        build_flags.insert(1, "FULL_HOOKS=1")

    manifest_name = "port45_no_overdraw_manifest.json" if no_overdraw else "port43_dbuf_manifest.json"
    if kbd_check:
        manifest_name = "port46_kbd_check_manifest.json"
    if gui_diag:
        manifest_name = "port47_gui_diag_manifest.json"
    if shadow2:
        manifest_name = "port48_shadow_alloc_manifest.json"
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
    if gui_diag:
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

    manifest_path = effective_out_dir / manifest_name
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")
    print(f"[OK] Manifest written to {manifest_path}")

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
    )



if __name__ == "__main__":
    sys.exit(main())
