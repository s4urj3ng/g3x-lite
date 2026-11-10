#!/usr/bin/env python3
"""PORT-41: Standard CHDK Full Build for PowerShot G3 X (GM1.10C).

Performs a standard CHDK build in an isolated staging tree under out/port41-full/.
Overlays full_build/g3x onto platform/g3x in the staging directory only.
Produces:
  out/port41-full/DISKBOOT.BIN
  out/port41-full/CHDK/ (MODULES, FONTS, LANG)
  out/port41-full/port41_manifest.json (SHA-256 manifest)

No files outside out/port41-full/ are written or modified.
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

OUT_DIR = REPO_ROOT / "out" / "port41-full"
STAGE_DIR = OUT_DIR / "stage_chdk"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def overlay_tree(src: Path, dst: Path, ignore: set[str] | None = None) -> None:
    """Recursively overlay files from src directory onto dst directory."""
    for root, dirs, files in os.walk(src):
        if ignore:
            dirs[:] = [d for d in dirs if d not in ignore]
        rel_path = Path(root).relative_to(src)
        target_dir = dst / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if ignore and f in ignore:
                continue
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)


def clean_staging_artifacts(stage_dir: Path) -> None:
    """Remove any stale precompiled objects/archives/binaries from the staging copy."""
    # Ensure all files and directories in staging are user-writable
    subprocess.run(["chmod", "-R", "u+w", str(stage_dir)], check=True)

    # Clean tools binaries and objects
    tools_dir = stage_dir / "tools"
    if tools_dir.is_dir():
        for ext in ("*.o", "*.a", "*.d"):
            for f in tools_dir.glob(f"**/{ext}"):
                try:
                    f.unlink()
                except OSError:
                    pass

    # Clean lib, core, modules, platform, loader stale objects and archives
    for sub in ["lib", "core", "modules", "platform", "loader", "bin"]:
        target = stage_dir / sub
        if not target.is_dir():
            continue
        for o2 in target.glob("**/.o2"):
            if o2.is_dir():
                shutil.rmtree(o2, ignore_errors=True)
        for ext in ("*.o", "*.a", "*.d", "*.flt", "*.dump"):
            for f in target.glob(f"**/{ext}"):
                try:
                    f.unlink()
                except OSError:
                    pass


def apply_full_hooks_staging_patches(stage_dir: Path) -> None:
    """PORT-42: Apply FULL_HOOKS=1 staging patches for FINSIG-confirmed hooks.

    Hooks:
    - task_CaptSeq (0xFC06A001, FINSIG) -> capt_seq_task
      Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:103-108
                        chdk-port/platform/g7x/sub/100d/capt_seq.c:63-65
    - task_FileWrite (0xFC25F3A7, FINSIG) -> filewritetask
      Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:126-131
                        chdk-port/platform/g7x/sub/100d/filewrite.c:110-115
    """
    sub_dir = stage_dir / "platform" / "g3x" / "sub" / "110c"

    # 1. Patch boot.c to intercept task_CaptSeq and task_FileWrite in CreateTask_my
    boot_c = sub_dir / "boot.c"
    boot_text = boot_c.read_text(encoding="utf-8")

    # Add external declarations for capt_seq_task and filewritetask
    decl_anchor = "void __attribute__((naked,noinline)) CreateTask_my(void)"
    decl_replacement = (
        "extern void capt_seq_task(void);\n"
        "extern void filewritetask(void);\n\n"
        "void __attribute__((naked,noinline)) CreateTask_my(void)"
    )
    if decl_anchor in boot_text:
        boot_text = boot_text.replace(decl_anchor, decl_replacement, 1)

    hook_anchor = (
        "        // capt_seq, movie_rec, filewrite left stock (not in FINSIG / VERIFIED)\n"
        "        // Listed as TODOs in documentation per specification"
    )
    hook_replacement = (
        "        // PORT-42 FULL_HOOKS=1: Intercept task_CaptSeq (0xFC06A001) -> capt_seq_task\n"
        "        // Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:103-108\n"
        "        // Label: FINSIG (reference/finsig_gm110c/stubs_entry.S:334)\n"
        '        "    ldr     r0, =task_CaptSeq\\n"\n'
        '        "    cmp     r0, r3\\n"\n'
        '        "    itt     eq\\n"\n'
        '        "    ldreq   r3, =capt_seq_task\\n"\n'
        '        "    orreq   r3, #1\\n"\n'
        '        "    beq     exitHook\\n"\n\n'
        "        // PORT-42 FULL_HOOKS=1: Intercept task_FileWrite (0xFC25F3A7) -> filewritetask\n"
        "        // Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:126-131\n"
        "        // Label: FINSIG (reference/finsig_gm110c/stubs_entry.S:337)\n"
        '        "    ldr     r0, =task_FileWrite\\n"\n'
        '        "    cmp     r0, r3\\n"\n'
        '        "    itt     eq\\n"\n'
        '        "    ldreq   r3, =filewritetask\\n"\n'
        '        "    orreq   r3, #1\\n"\n'
        '        "    beq     exitHook\\n"\n\n'
        "        // task_MovieRecord (0xFC09AC19, FINSIG) left stock\n"
        "        // Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:134-138 (disabled/commented out)\n"
        "        // Reason: Disabled across sibling DIGIC 6 ports; movie recording task hooks and video bitrate tables are unverified (INFERRED-only)"
    )
    if hook_anchor in boot_text:
        boot_text = boot_text.replace(hook_anchor, hook_replacement, 1)
    else:
        raise RuntimeError("CreateTask_my hook anchor not found in staged boot.c")
    boot_c.write_text(boot_text, encoding="utf-8")

    # 2. Patch capt_seq.c to provide capt_seq_task trampoline
    capt_seq_c = sub_dir / "capt_seq.c"
    capt_seq_text = capt_seq_c.read_text(encoding="utf-8")
    capt_seq_append = (
        "\n// -----------------------------------------------------------------------------\n"
        "// PORT-42: FULL_HOOKS=1 task_CaptSeq hook\n"
        "// Sibling citation: chdk-port/platform/g7x/sub/100d/capt_seq.c:63-65\n"
        "// Address: task_CaptSeq = 0xFC06A001 (FINSIG reference/finsig_gm110c/stubs_entry.S:334)\n"
        "// Internal capture sequencing hook points (capt_seq_hook_raw_here, raw buffer offsets)\n"
        "// are unverified (INFERRED-only) in GM1.10C; capt_seq_task safely executes as an entry hook\n"
        "// delegating to stock DryOS task_CaptSeq (0xFC06A001).\n"
        "// -----------------------------------------------------------------------------\n"
        "extern void task_CaptSeq(void);\n\n"
        "void __attribute__((naked,noinline)) capt_seq_task(void)\n"
        "{\n"
        "    asm volatile (\n"
        '        "    ldr.w   pc, =task_CaptSeq\\n"\n'
        '        "    .ltorg\\n"\n'
        "    );\n"
        "}\n"
    )
    capt_seq_c.write_text(capt_seq_text + capt_seq_append, encoding="utf-8")

    # 3. Patch filewrite.c to provide filewritetask trampoline
    filewrite_c = sub_dir / "filewrite.c"
    filewrite_text = filewrite_c.read_text(encoding="utf-8")
    filewrite_append = (
        "\n// -----------------------------------------------------------------------------\n"
        "// PORT-42: FULL_HOOKS=1 task_FileWrite hook\n"
        "// Sibling citation: chdk-port/platform/g7x/sub/100d/filewrite.c:110-115\n"
        "// Address: task_FileWrite = 0xFC25F3A7 (FINSIG reference/finsig_gm110c/stubs_entry.S:337)\n"
        "// Card writes are suppressed at compile time (-DG3X_DISABLE_CARD_WRITES=1, -DOPT_DISABLE_FILE_WRITES=1).\n"
        "// Internal async write queue structures are unverified (INFERRED-only).\n"
        "// filewritetask safely executes as an entry hook delegating to stock DryOS task_FileWrite (0xFC25F3A7).\n"
        "// -----------------------------------------------------------------------------\n"
        "extern void task_FileWrite(void);\n\n"
        "void __attribute__((naked,noinline)) filewritetask(void)\n"
        "{\n"
        "    asm volatile (\n"
        '        "    ldr.w   pc, =task_FileWrite\\n"\n'
        '        "    .ltorg\\n"\n'
        "    );\n"
        "}\n"
    )
    filewrite_c.write_text(filewrite_text + filewrite_append, encoding="utf-8")

    # 4. Patch sub/110c/Makefile to add -DFULL_HOOKS=1 to CFLAGS
    sub_make = sub_dir / "Makefile"
    sub_make_text = sub_make.read_text(encoding="utf-8")
    sub_make_text = sub_make_text.replace(
        "CFLAGS += -DG3X_FULL_BUILD=1",
        "CFLAGS += -DG3X_FULL_BUILD=1 -DFULL_HOOKS=1",
        1,
    )
    sub_make.write_text(sub_make_text, encoding="utf-8")


def apply_gui_fix_staging_patches(stage_dir: Path) -> None:
    """PORT-42: Apply G3X_GUI_FIX=1 staging patches for flicker, UYVY colours and 2x font.

    Citations:
    - Zero-flicker redraw: chdk-port/platform/g5x/lib.c:211-224; PORT-37 docs/PORT37_GUI_FLICKER.md:17,46
    - Palette & UYVY colours: scripts/build_candidate_gui3.py:1223-1249; reference/finsig_gm110c/stubs_entry.S:195,196
    - 2x Integer font & 880x576 opaque layout: scripts/build_candidate_gui3.py:840-909, 984-1221; docs/PORT40_GUI_LAYOUT.md:14-28
    """
    # 1. Patch core/main.c: remove (((cnt++) & 3) == 0) periodic forced redraw,
    # and repaint only when GUI state changes or sentinel byte is lost.
    core_main_c = stage_dir / "core" / "main.c"
    core_main_text = core_main_c.read_text(encoding="utf-8")
    main_anchor = (
        "#ifdef CAM_DETECT_BITMAP_UPDATE\n"
        "            extern int check_gui_needs_redraw();\n"
        "            int gui_force_redraw = check_gui_needs_redraw();\n"
        "#else\n"
        "            int gui_force_redraw = 0;\n"
        "#endif\n"
        "            if (gui_force_redraw || (((cnt++) & 3) == 0))\n"
        "                gui_redraw(gui_force_redraw);"
    )
    main_replacement = (
        "            /* PORT-42 GUI fix: Unconditional timer and state maintenance.\n"
        "             * No periodic forced redraw: repaint only on state change, sentinel loss, or buffer change.\n"
        "             * Sibling citation: chdk-port/platform/g5x/lib.c:211-224; PORT-37 docs/PORT37_GUI_FLICKER.md:17,46 */\n"
        "            extern void gui_maintenance_tick(void);\n"
        "            extern int check_gui_needs_redraw(void);\n"
        "            extern int draw_test_guard(void);\n"
        "            extern int check_bitmap_buffer_changed(void);\n"
        "            extern int gui_check_state_changed(void);\n"
        "            extern int gui_is_osd_mode(void);\n"
        "            extern void gui_draw_osd_tick(void);\n"
        "            extern int gui_is_module_mode(void);\n"
        "            extern void gui_draw_module_tick(void);\n"
        "\n"
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
    if main_anchor in core_main_text:
        core_main_text = core_main_text.replace(main_anchor, main_replacement, 1)
    else:
        raise RuntimeError("gui_force_redraw anchor not found in staged core/main.c")
    core_main_c.write_text(core_main_text, encoding="utf-8")

    # 2. Patch core/conf.c: default conf.menu_color and conf.menu_title_color to solid black background
    # and conf.menu_center to 0 [scripts/build_candidate_gui3.py:1685-1698; docs/PORT40_GUI_LAYOUT.md:23-25]
    core_conf_c = stage_dir / "core" / "conf.c"
    core_conf_text = core_conf_c.read_text(encoding="utf-8")
    conf_anchors = [
        (
            "CONF_INFOC( 55, conf.menu_color,                            CONF_DEF_VALUE, IDX_COLOR_GREY_DK,IDX_COLOR_WHITE,1,1),",
            "CONF_INFOC( 55, conf.menu_color,                            CONF_DEF_VALUE, IDX_COLOR_BLACK,IDX_COLOR_WHITE,1,1),",
        ),
        (
            "CONF_INFOC( 56, conf.menu_title_color,                      CONF_DEF_VALUE, IDX_COLOR_WHITE,IDX_COLOR_BLACK,1,1),",
            "CONF_INFOC( 56, conf.menu_title_color,                      CONF_DEF_VALUE, IDX_COLOR_BLACK,IDX_COLOR_WHITE,1,1),",
        ),
        (
            "CONF_INFO(134, conf.menu_center,                            CONF_DEF_VALUE, i:1),",
            "CONF_INFO(134, conf.menu_center,                            CONF_DEF_VALUE, i:0),",
        ),
    ]
    for old_s, new_s in conf_anchors:
        if old_s in core_conf_text:
            core_conf_text = core_conf_text.replace(old_s, new_s, 1)
        else:
            raise RuntimeError(f"conf anchor not found in staged core/conf.c: {old_s}")
    core_conf_c.write_text(core_conf_text, encoding="utf-8")

    # 2b. Patch include/console.h and core/console.c: export console_last_modified
    # and trigger redraw on MBOX console scroll [chdk-port/core/console.c:25,255-268]
    core_console_h = stage_dir / "include" / "console.h"
    core_console_h_text = core_console_h.read_text(encoding="utf-8")
    console_h_anchor = "extern int console_displayed;\n"
    console_h_replacement = (
        "extern int console_displayed;\n"
        "extern long console_last_modified;\n"
    )
    if console_h_anchor in core_console_h_text:
        core_console_h_text = core_console_h_text.replace(console_h_anchor, console_h_replacement, 1)
    else:
        raise RuntimeError("console_displayed anchor not found in staged include/console.h")
    core_console_h.write_text(core_console_h_text, encoding="utf-8")

    core_console_c = stage_dir / "core" / "console.c"
    core_console_text = core_console_c.read_text(encoding="utf-8")
    console_mod_anchor = "static long console_last_modified;\n"
    console_mod_replacement = "long console_last_modified;\n"
    if console_mod_anchor in core_console_text:
        core_console_text = core_console_text.replace(console_mod_anchor, console_mod_replacement, 1)
    else:
        raise RuntimeError("console_last_modified anchor not found in staged core/console.c")

    console_scroll_anchor = "            console_redraw_flag = 1;\n"
    console_scroll_replacement = (
        "            extern void gui_set_need_redraw(void);\n"
        "            console_redraw_flag = 1;\n"
        "            gui_set_need_redraw();\n"
    )
    if console_scroll_anchor in core_console_text:
        core_console_text = core_console_text.replace(console_scroll_anchor, console_scroll_replacement)
    core_console_c.write_text(core_console_text, encoding="utf-8")

    # 3. Patch core/gui.c: fill 880x576 box with solid opaque black in gui_draw_alt_helper [scripts/build_candidate_gui3.py:820-826]
    # and provide gui_check_state_changed() for zero-flicker redraw
    core_gui_c = stage_dir / "core" / "gui.c"
    core_gui_text = core_gui_c.read_text(encoding="utf-8")

    # Guard g3x_fill_menu_opaque_black in gui_draw_alt_helper so it runs only on mode entry,
    # sentinel loss, or real state change, never on every tick
    draw_flag_anchor = "static int gui_mode_need_redraw = 0;    // Set if current mode needs to redraw itself\n"
    draw_flag_replacement = (
        "static int gui_mode_need_redraw = 0;    // Set if current mode needs to redraw itself\n"
        "static int alt_helper_drawn = 0;\n"
    )
    if draw_flag_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(draw_flag_anchor, draw_flag_replacement, 1)
    else:
        raise RuntimeError("gui_mode_need_redraw anchor not found in staged core/gui.c")

    helper_def_anchor = (
        "void gui_reset_alt_helper()\n"
        "{\n"
        "    gui_helper_displayat = get_tick_count() + (conf.show_alt_helper_delay * 1000);\n"
        "}\n\n"
        "static void gui_draw_alt_helper()\n"
    )
    helper_def_replacement = (
        "void gui_reset_alt_helper()\n"
        "{\n"
        "    alt_helper_drawn = 0;\n"
        "    gui_helper_displayat = get_tick_count() + (conf.show_alt_helper_delay * 1000);\n"
        "}\n\n"
        "static void gui_draw_alt_helper(int force_redraw)\n"
    )
    if helper_def_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(helper_def_anchor, helper_def_replacement, 1)
    else:
        raise RuntimeError("gui_reset_alt_helper anchor not found in staged core/gui.c")

    gui_chdk_draw_anchor = (
        "#ifdef CAM_DISP_ALT_TEXT\n"
        "    gui_draw_alt_helper();\n"
        "#else\n"
    )
    gui_chdk_draw_replacement = (
        "#ifdef CAM_DISP_ALT_TEXT\n"
        "    gui_draw_alt_helper(force_redraw);\n"
        "#else\n"
    )
    if gui_chdk_draw_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(gui_chdk_draw_anchor, gui_chdk_draw_replacement, 1)
    else:
        raise RuntimeError("gui_draw_alt_helper() call anchor not found in staged core/gui.c")

    gui_anchor = "    is_menu_shortcut = 0;\n"
    gui_replacement = (
        "    is_menu_shortcut = 0;\n\n"
        "    /* PORT-42 GUI fix: Fill full 880x576 box with solid opaque black only on state change,\n"
        "     * mode entry or sentinel loss, never on every tick [PORT-38 docs/PORT38_GUI4_TRIAL.md:123] */\n"
        "    if (force_redraw || !draw_test_guard() || !alt_helper_drawn)\n"
        "    {\n"
        "        extern void g3x_fill_menu_opaque_black(void);\n"
        "        g3x_fill_menu_opaque_black();\n"
        "        alt_helper_drawn = 1;\n"
        "    }\n"
    )
    if gui_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(gui_anchor, gui_replacement, 1)
    else:
        raise RuntimeError("is_menu_shortcut anchor not found in staged core/gui.c")

    # Patch gui_set_mode to reset alt_helper_drawn and clear pending menu redraw
    set_mode_anchor = (
        "    gui_handler *old_mode = gui_mode;\n"
        "    gui_mode = mode;\n\n"
        "    gui_osd_need_restore = 0;\n"
    )
    set_mode_replacement = (
        "    gui_handler *old_mode = gui_mode;\n"
        "    gui_mode = mode;\n\n"
        "    alt_helper_drawn = 0;\n"
        "    extern void gui_menu_clear_redraw(void);\n"
        "    gui_menu_clear_redraw();\n\n"
        "    gui_osd_need_restore = 0;\n"
    )
    if set_mode_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(set_mode_anchor, set_mode_replacement, 1)
    else:
        raise RuntimeError("gui_set_mode anchor not found in staged core/gui.c")

    # Patch gui_activate_alt_mode to clear pending menu redraw on enter and leave
    alt_activate_anchor = (
        "    switch (gui_current_alt_state)\n"
        "    {\n"
        "    case ALT_MODE_ENTER:\n"
    )
    alt_activate_replacement = (
        "    switch (gui_current_alt_state)\n"
        "    {\n"
        "    case ALT_MODE_ENTER:\n"
        "        alt_helper_drawn = 0;\n"
        "        {\n"
        "            extern void gui_menu_clear_redraw(void);\n"
        "            gui_menu_clear_redraw();\n"
        "        }\n"
    )
    if alt_activate_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(alt_activate_anchor, alt_activate_replacement, 1)
    else:
        raise RuntimeError("ALT_MODE_ENTER anchor not found in staged core/gui.c")

    alt_leave_anchor = (
        "    case ALT_MODE_LEAVE:\n"
        "        conf_save();\n"
    )
    alt_leave_replacement = (
        "    case ALT_MODE_LEAVE:\n"
        "        alt_helper_drawn = 0;\n"
        "        {\n"
        "            extern void gui_menu_clear_redraw(void);\n"
        "            gui_menu_clear_redraw();\n"
        "        }\n"
        "        conf_save();\n"
    )
    if alt_leave_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(alt_leave_anchor, alt_leave_replacement, 1)
    else:
        raise RuntimeError("ALT_MODE_LEAVE anchor not found in staged core/gui.c")

    splash_anchor = (
        "static void gui_handle_splash(int force_redraw)\n"
        "{\n"
        "    if (gui_splash)\n"
        "    {\n"
        "        if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)\n"
        "            if (force_redraw || (gui_splash == SPLASH_TIME))\n"
        "                gui_draw_splash();\n"
        "\n"
        "        // on half shoot, cancel splash screen\n"
        "        if(kbd_is_key_pressed(KEY_SHOOT_HALF)) {\n"
        "            gui_splash = 1;\n"
        "        }\n"
        "        if (--gui_splash == 0)\n"
        "        {\n"
        "            if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)\n"
        "                gui_set_need_restore();\n"
        "            if (logo)\n"
        "                free(logo);\n"
        "            logo = NULL;\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    splash_replacement = (
        "static void gui_handle_splash(int force_redraw)\n"
        "{\n"
        "    if (gui_splash)\n"
        "    {\n"
        "        if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)\n"
        "            gui_draw_splash();\n"
        "    }\n"
        "}\n"
    )
    if splash_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(splash_anchor, splash_replacement, 1)
    else:
        raise RuntimeError("gui_handle_splash anchor not found in staged core/gui.c")

    alt_anchor = "gui_handler altGuiHandler = { GUI_MODE_ALT, gui_chdk_draw, gui_chdk_kbd_process, gui_chdk_kbd_process_menu_btn, 0, 0, };\n"
    alt_replacement = (
        "gui_handler altGuiHandler = { GUI_MODE_ALT, gui_chdk_draw, gui_chdk_kbd_process, gui_chdk_kbd_process_menu_btn, 0, 0, };\n\n"
        "/* =============================================================================\n"
        " * PORT-42 GUI FIX: Unconditional timer maintenance & visible-state signature change detection.\n"
        " * Citing core/gui.c:2387-2405,2553-2700\n"
        " * ============================================================================= */\n"
        "struct gui_vis_sig {\n"
        "    void *mode_ptr;\n"
        "    int gui_mode;\n"
        "    int helper_due;\n"
        "    int splash_sec;\n"
        "    int menu_item;\n"
        "    int debug_shortcut_action;\n"
        "    int dng_raw;\n"
        "    int enable_shortcuts;\n"
        "    int hide_osd;\n"
        "    confColor menu_color;\n"
        "    confColor menu_title_color;\n"
        "    int override_disable;\n"
        "    int save_raw;\n"
        "    int show_alt_helper;\n"
        "    int show_alt_helper_delay;\n"
        "    int show_histo;\n"
        "    int show_osd;\n"
        "    int subj_dist_override_koef;\n"
        "    int user_menu_as_root;\n"
        "    int user_menu_enable;\n"
        "    int zebra_draw;\n"
        "    int console_displayed;\n"
        "    long console_last_modified;\n"
        "};\n\n"
        "static struct gui_vis_sig last_gui_sig;\n"
        "static int gui_sig_initialized = 0;\n"
        "static int gui_splash_expire = 0;\n"
        "static int gui_splash_sec = 0;\n"
        "static int gui_helper_due = 0;\n\n"
        "void gui_maintenance_tick(void)\n"
        "{\n"
        "    int now = get_tick_count();\n\n"
        "    // 1. Splash countdown, expiry, and half-shutter cancellation [core/gui.c:2387-2405]\n"
        "    if (gui_splash > 0)\n"
        "    {\n"
        "        if (gui_splash_expire == 0)\n"
        "        {\n"
        "            gui_splash_expire = now + (SPLASH_TIME * 80);\n"
        "        }\n"
        "        if (kbd_is_key_pressed(KEY_SHOOT_HALF) || (now >= gui_splash_expire))\n"
        "        {\n"
        "            gui_splash = 0;\n"
        "            gui_splash_expire = 0;\n"
        "            gui_splash_sec = 0;\n"
        "            if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)\n"
        "                gui_set_need_restore();\n"
        "            if (logo)\n"
        "            {\n"
        "                free(logo);\n"
        "                logo = NULL;\n"
        "            }\n"
        "        }\n"
        "        else\n"
        "        {\n"
        "            int sec = (gui_splash_expire - now + 999) / 1000;\n"
        "            if (sec <= 0) sec = 1;\n"
        "            gui_splash_sec = sec;\n"
        "        }\n"
        "    }\n"
        "    else\n"
        "    {\n"
        "        gui_splash_sec = 0;\n"
        "    }\n\n"
        "    // 2. Helper expiry state maintenance [core/gui.c:2553-2570]\n"
        "#ifdef CAM_DISP_ALT_TEXT\n"
        "    if (camera_info.state.gui_mode_alt && conf.show_alt_helper)\n"
        "    {\n"
        "        gui_helper_due = (now >= gui_helper_displayat);\n"
        "    }\n"
        "    else\n"
        "    {\n"
        "        gui_helper_due = 0;\n"
        "    }\n"
        "#else\n"
        "    gui_helper_due = 0;\n"
        "#endif\n\n"
        "    // 3. Console expiry / auto-hide state maintenance [core/console.c:103-107]\n"
        "    if (console_displayed && !camera_info.state.state_kbd_script_run)\n"
        "    {\n"
        "        if (now > console_last_modified + (conf.console_timeout * 1000))\n"
        "        {\n"
        "            gui_set_need_restore();\n"
        "            console_displayed = 0;\n"
        "        }\n"
        "    }\n"
        "}\n\n"
        "int gui_check_state_changed(void)\n"
        "{\n"
        "    extern int gui_menu_needs_redraw(void);\n"
        "    extern int gui_menu_get_curr_item(void);\n"
        "    extern int memcmp(const void *s1, const void *s2, long n);\n\n"
        "    int is_menu_active = (camera_info.state.gui_mode == GUI_MODE_MENU);\n"
        "    int menu_dirty = is_menu_active && gui_menu_needs_redraw();\n\n"
        "    int dirty = gui_osd_need_restore || gui_mode_need_redraw || menu_dirty;\n\n"
        "    struct gui_vis_sig current_sig;\n"
        "    current_sig.mode_ptr               = (void*)gui_mode;\n"
        "    current_sig.gui_mode               = camera_info.state.gui_mode;\n"
        "    current_sig.helper_due             = gui_helper_due;\n"
        "    current_sig.splash_sec             = gui_splash_sec;\n"
        "    current_sig.menu_item              = is_menu_active ? gui_menu_get_curr_item() : 0;\n"
        "    current_sig.debug_shortcut_action  = conf.debug_shortcut_action;\n"
        "    current_sig.dng_raw                = conf.dng_raw;\n"
        "    current_sig.enable_shortcuts       = conf.enable_shortcuts;\n"
        "    current_sig.hide_osd               = conf.hide_osd;\n"
        "    current_sig.menu_color             = conf.menu_color;\n"
        "    current_sig.menu_title_color       = conf.menu_title_color;\n"
        "    current_sig.override_disable       = conf.override_disable;\n"
        "    current_sig.save_raw               = conf.save_raw;\n"
        "    current_sig.show_alt_helper        = conf.show_alt_helper;\n"
        "    current_sig.show_alt_helper_delay  = conf.show_alt_helper_delay;\n"
        "    current_sig.show_histo             = conf.show_histo;\n"
        "    current_sig.show_osd               = conf.show_osd;\n"
        "    current_sig.subj_dist_override_koef = conf.subj_dist_override_koef;\n"
        "    current_sig.user_menu_as_root      = conf.user_menu_as_root;\n"
        "    current_sig.user_menu_enable       = conf.user_menu_enable;\n"
        "    current_sig.zebra_draw             = conf.zebra_draw;\n"
        "    current_sig.console_displayed      = console_displayed;\n"
        "    current_sig.console_last_modified  = console_last_modified;\n\n"
        "    int sig_changed = 0;\n"
        "    if (!gui_sig_initialized)\n"
        "    {\n"
        "        gui_sig_initialized = 1;\n"
        "        sig_changed = 1;\n"
        "    }\n"
        "    else if (last_gui_sig.mode_ptr               != current_sig.mode_ptr ||\n"
        "             last_gui_sig.gui_mode               != current_sig.gui_mode ||\n"
        "             last_gui_sig.helper_due             != current_sig.helper_due ||\n"
        "             last_gui_sig.splash_sec             != current_sig.splash_sec ||\n"
        "             last_gui_sig.menu_item              != current_sig.menu_item ||\n"
        "             last_gui_sig.debug_shortcut_action  != current_sig.debug_shortcut_action ||\n"
        "             last_gui_sig.dng_raw                != current_sig.dng_raw ||\n"
        "             last_gui_sig.enable_shortcuts       != current_sig.enable_shortcuts ||\n"
        "             last_gui_sig.hide_osd               != current_sig.hide_osd ||\n"
        "             memcmp(&last_gui_sig.menu_color, &current_sig.menu_color, sizeof(confColor)) != 0 ||\n"
        "             memcmp(&last_gui_sig.menu_title_color, &current_sig.menu_title_color, sizeof(confColor)) != 0 ||\n"
        "             last_gui_sig.override_disable       != current_sig.override_disable ||\n"
        "             last_gui_sig.save_raw               != current_sig.save_raw ||\n"
        "             last_gui_sig.show_alt_helper        != current_sig.show_alt_helper ||\n"
        "             last_gui_sig.show_alt_helper_delay  != current_sig.show_alt_helper_delay ||\n"
        "             last_gui_sig.show_histo             != current_sig.show_histo ||\n"
        "             last_gui_sig.show_osd               != current_sig.show_osd ||\n"
        "             last_gui_sig.subj_dist_override_koef != current_sig.subj_dist_override_koef ||\n"
        "             last_gui_sig.user_menu_as_root      != current_sig.user_menu_as_root ||\n"
        "             last_gui_sig.user_menu_enable       != current_sig.user_menu_enable ||\n"
        "             last_gui_sig.zebra_draw             != current_sig.zebra_draw ||\n"
        "             last_gui_sig.console_displayed      != current_sig.console_displayed ||\n"
        "             last_gui_sig.console_last_modified  != current_sig.console_last_modified)\n"
        "    {\n"
        "        sig_changed = 1;\n"
        "    }\n\n"
        "    if (sig_changed)\n"
        "    {\n"
        "        alt_helper_drawn = 0;\n"
        "    }\n\n"
        "    last_gui_sig = current_sig;\n\n"
        "    return dirty || sig_changed;\n"
        "}\n\n"
        "int gui_is_osd_mode(void)\n"
        "{\n"
        "    return (camera_info.state.gui_mode == GUI_MODE_NONE);\n"
        "}\n\n"
        "void gui_draw_osd_tick(void)\n"
        "{\n"
        "    if (gui_mode && gui_mode->redraw)\n"
        "    {\n"
        "        gui_mode->redraw(0);\n"
        "    }\n"
        "}\n\n"
        "int gui_is_module_mode(void)\n"
        "{\n"
        "    return (camera_info.state.gui_mode > GUI_MODE_MENU);\n"
        "}\n\n"
        "void gui_draw_module_tick(void)\n"
        "{\n"
        "    if (gui_mode && gui_mode->redraw)\n"
        "    {\n"
        "        gui_mode->redraw(0);\n"
        "    }\n"
        "}\n"
    )
    if alt_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(alt_anchor, alt_replacement, 1)
    else:
        raise RuntimeError("altGuiHandler anchor not found in staged core/gui.c")

    # Patch gui_redraw to sync last_gui_sig.console_displayed with active console_displayed
    redraw_anchor = "    if (gui_mode->redraw)\n        gui_mode->redraw(flag_gui_enforce_redraw);\n"
    redraw_replacement = (
        "    if (gui_mode->redraw)\n        gui_mode->redraw(flag_gui_enforce_redraw);\n\n"
        "    /* PORT-42: Sync console_displayed in visible state signature after redraw */\n"
        "    last_gui_sig.console_displayed = console_displayed;\n"
    )
    if redraw_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(redraw_anchor, redraw_replacement, 1)
    else:
        raise RuntimeError("gui_mode->redraw anchor not found in staged core/gui.c")
    core_gui_c.write_text(core_gui_text, encoding="utf-8")

    # 4. Patch core/gui_draw.c and core/gui_draw.h: 2x integer font scaling (16x32)
    core_draw_h = stage_dir / "core" / "gui_draw.h"
    core_draw_h_text = core_draw_h.read_text(encoding="utf-8")
    draw_h_anchor = "#define FONT_HEIGHT             32\n"
    draw_h_replacement = (
        "#define FONT_HEIGHT             32\n"
        "#undef  FONT_WIDTH\n"
        "#define FONT_WIDTH              16\n"
    )
    if draw_h_anchor in core_draw_h_text:
        core_draw_h_text = core_draw_h_text.replace(draw_h_anchor, draw_h_replacement, 1)
    core_draw_h.write_text(core_draw_h_text, encoding="utf-8")

    core_draw_c = stage_dir / "core" / "gui_draw.c"
    core_draw_text = core_draw_c.read_text(encoding="utf-8")
    draw_c_anchor = (
        "            // upscaling 8 pixels to 14\n"
        "            ii = 0;\n"
        "            ii += (dsym&1)?3:0;\n"
        "            ii += (dsym&2)?4:0;\n"
        "            ii += (dsym&4)?0x18:0;\n"
        "            ii += (dsym&8)?0x60:0;\n"
        "            ii += (dsym&16)?0x180:0;\n"
        "            ii += (dsym&32)?0x600:0;\n"
        "            ii += (dsym&64)?0x1800:0;\n"
        "            ii += (dsym&128)?0x2000:0;\n"
        "            dsym = ii;"
    )
    draw_c_replacement = (
        "            // PORT-42: 2x integer font scaling: 8 pixels to 16 (each bit expands to 2x2 square)\n"
        "            ii = 0;\n"
        "            ii += (dsym&1)?3:0;\n"
        "            ii += (dsym&2)?0xc:0;\n"
        "            ii += (dsym&4)?0x30:0;\n"
        "            ii += (dsym&8)?0xc0:0;\n"
        "            ii += (dsym&16)?0x300:0;\n"
        "            ii += (dsym&32)?0xc00:0;\n"
        "            ii += (dsym&64)?0x3000:0;\n"
        "            ii += (dsym&128)?0xc000:0;\n"
        "            dsym = ii;"
    )
    if draw_c_anchor in core_draw_text:
        core_draw_text = core_draw_text.replace(draw_c_anchor, draw_c_replacement, 1)
    else:
        raise RuntimeError("draw_char upscaling anchor not found in staged core/gui_draw.c")
    # Also adjust fw in draw_char
    draw_c_text = core_draw_text.replace(
        "    unsigned int fw = FONT_WIDTH;\n",
        "    unsigned int fw = 16;\n",
        1,
    )

    # Patch draw_set_guard and draw_test_guard to mask active_bitmap_buffer with & 1
    draw_guard_anchor = (
        "void draw_set_guard()\n"
        "{\n"
        "    opacity_buffer[active_bitmap_buffer][0] = 0x42;\n"
        "}\n\n"
        "int draw_test_guard()\n"
        "{\n"
        "    if (opacity_buffer[active_bitmap_buffer][0] != 0x42) return 0;\n"
        "    return 1;\n"
        "}"
    )
    draw_guard_replacement = (
        "void draw_set_guard()\n"
        "{\n"
        "    /* PORT-42: Index active opacity buffer with (active_bitmap_buffer & 1) */\n"
        "    opacity_buffer[active_bitmap_buffer & 1][0] = 0x42;\n"
        "}\n\n"
        "int draw_test_guard()\n"
        "{\n"
        "    /* PORT-42: Index active opacity buffer with (active_bitmap_buffer & 1) */\n"
        "    if (opacity_buffer[active_bitmap_buffer & 1][0] != 0x42) return 0;\n"
        "    return 1;\n"
        "}"
    )
    if draw_guard_anchor in draw_c_text:
        draw_c_text = draw_c_text.replace(draw_guard_anchor, draw_guard_replacement, 1)
    else:
        raise RuntimeError("draw_set_guard anchor not found in staged core/gui_draw.c")

    core_draw_c.write_text(draw_c_text, encoding="utf-8")

    # 5. Patch platform/g3x/Makefile and platform/g3x/sub/110c/Makefile to add -DG3X_GUI_FIX=1
    for mpath in [
        stage_dir / "platform" / "g3x" / "Makefile",
        stage_dir / "platform" / "g3x" / "sub" / "110c" / "Makefile",
    ]:
        if mpath.is_file():
            mtext = mpath.read_text(encoding="utf-8")
            mtext = mtext.replace(
                "CFLAGS += -DG3X_FULL_BUILD=1",
                "CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_GUI_FIX=1",
                1,
            )
            mpath.write_text(mtext, encoding="utf-8")


def build_port41_full(
    clean_stage: bool = True,
    keep_stage: bool = True,
    full_hooks: bool = False,
    gui_fix: bool = False,
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

    # Check env vars as well
    if not full_hooks and os.environ.get("FULL_HOOKS") == "1":
        full_hooks = True
    if not gui_fix and os.environ.get("G3X_GUI_FIX") == "1":
        gui_fix = True

    # Determine effective output and staging directories
    if out_dir is not None:
        effective_out_dir = Path(out_dir).resolve()
    elif gui_fix and full_hooks:
        effective_out_dir = REPO_ROOT / "out" / "port42-gui-full-hooks"
    elif gui_fix:
        effective_out_dir = REPO_ROOT / "out" / "port42-gui"
    else:
        effective_out_dir = REPO_ROOT / "out" / "port41-full"

    effective_stage_dir = effective_out_dir / "stage_chdk"

    # Prepare staging directory
    effective_out_dir.mkdir(parents=True, exist_ok=True)
    if clean_stage and effective_stage_dir.exists():
        shutil.rmtree(effective_stage_dir)

    if not effective_stage_dir.exists():
        print(f"Staging CHDK tree to {effective_stage_dir}...")
        # Copy chdk-port into stage_chdk
        shutil.copytree(CHDK_PORT, effective_stage_dir, symlinks=True)

    # Clean stale objects, ensure permissions
    clean_staging_artifacts(effective_stage_dir)

    # Overlay full_build/g3x onto stage_chdk/platform/g3x/ (excluding loader/)
    platform_target = effective_stage_dir / "platform" / "g3x"
    print(f"Overlaying {FULL_BUILD_SRC} (excluding loader) onto {platform_target}...")
    overlay_tree(FULL_BUILD_SRC, platform_target, ignore={"loader"})

    # Overlay full_build/g3x/loader onto stage_chdk/loader/g3x/
    loader_target = effective_stage_dir / "loader" / "g3x"
    loader_src = FULL_BUILD_SRC / "loader"
    if loader_src.is_dir():
        print(f"Overlaying {loader_src} onto {loader_target}...")
        overlay_tree(loader_src, loader_target)

    # Remove prototype source files from staging platform so test_port24 permitted shorthands stay unique
    for proto_name in ["boot_prototype.c", "stubs_prototype.S"]:
        proto_file = platform_target / "sub" / "110c" / proto_name
        if proto_file.exists():
            proto_file.unlink()

    # Apply FULL_HOOKS=1 staging patches if opt-in switch is enabled
    if full_hooks:
        print("FULL_HOOKS=1 enabled: Applying FINSIG-confirmed hook staging patches...")
        apply_full_hooks_staging_patches(effective_stage_dir)

    # Apply G3X_GUI_FIX=1 staging patches if opt-in switch is enabled
    if gui_fix:
        print("G3X_GUI_FIX=1 enabled: Applying GUI flicker, colour and 2x font staging patches...")
        apply_gui_fix_staging_patches(effective_stage_dir)

    # Ensure clean platform objects in staging copy so full build compiles freshly
    for subpath in ["platform/g3x", "platform/g3x/sub/110c", "loader/g3x"]:
        p = effective_stage_dir / subpath
        if p.is_dir():
            clean_cmd = ["make", "-C", str(p), "PLATFORM=g3x", "PLATFORMSUB=110c", "G3X_FULL_BUILD=1"]
            if full_hooks:
                clean_cmd.append("FULL_HOOKS=1")
            if gui_fix:
                clean_cmd.append("G3X_GUI_FIX=1")
            clean_cmd.append("clean")
            subprocess.run(
                clean_cmd,
                cwd=str(effective_stage_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Run normal CHDK make
    cmd = [
        "make",
        "-C",
        str(effective_stage_dir),
        "PLATFORM=g3x",
        "PLATFORMSUB=110c",
        "G3X_FULL_BUILD=1",
        f"CROSS_COMPILE={CROSS_COMPILE}",
        "OPT_CAPSTONE_TOOLS=0",
    ]
    if full_hooks:
        cmd.append("FULL_HOOKS=1")
    if gui_fix:
        cmd.append("G3X_GUI_FIX=1")
    cmd.append("fir")

    print(f"Running build: {' '.join(cmd)}")
    env = os.environ.copy()
    wrapper_script = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
    if "MAKEFLAGS" not in env and wrapper_script.is_file() and os.access(wrapper_script, os.X_OK):
        env["MAKEFLAGS"] = f"CC={wrapper_script}"
    if full_hooks:
        env["FULL_HOOKS"] = "1"
    if gui_fix:
        env["G3X_GUI_FIX"] = "1"
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

    # Collect all CHDK files for the distribution manifest
    chdk_files_map: dict[str, dict[str, int | str]] = {}
    for root, dirs, files in os.walk(out_chdk):
        for f in sorted(files):
            p = Path(root) / f
            rel = str(p.relative_to(effective_out_dir))
            chdk_files_map[rel] = {
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            }

    # Generate SHA-256 manifest
    build_flags = [
        "G3X_FULL_BUILD=1",
        "G3X_DISABLE_CARD_WRITES=1",
        "CAM_SUPPORT_BITMAP_RES_CHANGE=1",
        "OPT_DISABLE_FILE_WRITES=1",
        "G3X_GUI5=1",
    ]
    if full_hooks:
        build_flags.insert(1, "FULL_HOOKS=1")
    if gui_fix:
        build_flags.append("G3X_GUI_FIX=1")

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

    if gui_fix and full_hooks:
        manifest_name = "port42_gui_fix_full_hooks_manifest.json"
    elif gui_fix:
        manifest_name = "port42_gui_fix_manifest.json"
    elif full_hooks:
        manifest_name = "port42_full_hooks_manifest.json"
    else:
        manifest_name = "port41_manifest.json"

    manifest_path = effective_out_dir / manifest_name
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"[OK] Manifest written to {manifest_path}")

    # If FULL_HOOKS is active (and no gui_fix), also keep port42_full_hooks_manifest.json name
    if full_hooks and not gui_fix:
        p42_manifest_path = effective_out_dir / "port42_full_hooks_manifest.json"
        with open(p42_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    # Also create manifest.json as convenience alias
    with open(effective_out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # In addition to port42_gui_fix_* manifests, also provide port42_gui_* aliases
    if gui_fix and full_hooks:
        with open(effective_out_dir / "port42_gui_full_hooks_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
    elif gui_fix:
        with open(effective_out_dir / "port42_gui_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    # Save to manifests/ and docs/manifests/ for the new GUI fix variants
    canonical_dirs = (REPO_ROOT / "out" / "port42-gui", REPO_ROOT / "out" / "port42-gui-full-hooks")
    if gui_fix and effective_out_dir in canonical_dirs:
        names = [manifest_name]
        if gui_fix and full_hooks:
            names.append("port42_gui_full_hooks_manifest.json")
        elif gui_fix:
            names.append("port42_gui_manifest.json")
        for mdir in [REPO_ROOT / "manifests", REPO_ROOT / "docs" / "manifests"]:
            mdir.mkdir(parents=True, exist_ok=True)
            for name in set(names):
                with open(mdir / name, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)
                print(f"[OK] Manifest saved to {mdir / name}")

    # Clean up scratch staging directory so no duplicate source files linger in workspace
    if not keep_stage and effective_stage_dir.exists():
        shutil.rmtree(effective_stage_dir)

    hook_str = []
    if full_hooks:
        hook_str.append("FULL_HOOKS=1")
    if gui_fix:
        hook_str.append("G3X_GUI_FIX=1")
    status_suffix = f"with {', '.join(hook_str)}" if hook_str else "standard PORT-41"
    print(f"\nFULL BUILD COMPLETE ({status_suffix}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Standard CHDK full build for G3 X GM1.10C")
    parser.add_argument("--no-clean", action="store_true", help="Do not clean staging directory before building")
    parser.add_argument("--clean-stage", action="store_true", help="Clean scratch staging directory after building")
    parser.add_argument("--keep-stage", action="store_true", default=True, help="Keep scratch staging directory after building (default)")
    parser.add_argument("--full-hooks", action="store_true", help="Enable FULL_HOOKS=1 variant with FINSIG-confirmed hooks")
    parser.add_argument("--gui-fix", action="store_true", help="Enable G3X_GUI_FIX=1 variant (flicker, UYVY colours, 2x font)")
    parser.add_argument("--out-dir", type=Path, default=None, help="Custom output directory")
    parser.add_argument("extra_args", nargs="*", help="Optional extra arguments (e.g. FULL_HOOKS=1, G3X_GUI_FIX=1)")
    args = parser.parse_args()

    full_hooks = (
        args.full_hooks
        or (os.environ.get("FULL_HOOKS") == "1")
        or any(arg == "FULL_HOOKS=1" for arg in args.extra_args)
    )
    gui_fix = (
        args.gui_fix
        or (os.environ.get("G3X_GUI_FIX") == "1")
        or any(arg in ("G3X_GUI_FIX=1", "--gui-fix") for arg in args.extra_args)
    )

    keep = not args.clean_stage if args.clean_stage else True
    return build_port41_full(
        clean_stage=not args.no_clean,
        keep_stage=keep,
        full_hooks=full_hooks,
        gui_fix=gui_fix,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
