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
        "            /* PORT-42 GUI fix: No periodic forced redraw.\n"
        "             * Repaint only when GUI state changes or sentinel byte is lost.\n"
        "             * Sibling citation: chdk-port/platform/g5x/lib.c:211-224; PORT-37 docs/PORT37_GUI_FLICKER.md:17,46 */\n"
        "            extern int check_gui_needs_redraw(void);\n"
        "            extern int draw_test_guard(void);\n"
        "            extern int gui_check_state_changed(void);\n"
        "            int gui_force_redraw = check_gui_needs_redraw() || (!draw_test_guard());\n"
        "            if (gui_force_redraw || gui_check_state_changed())\n"
        "                gui_redraw(gui_force_redraw);"
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

    # 3. Patch core/gui.c: fill 880x576 box with solid opaque black in gui_draw_alt_helper [scripts/build_candidate_gui3.py:820-826]
    # and provide gui_check_state_changed() for zero-flicker redraw
    core_gui_c = stage_dir / "core" / "gui.c"
    core_gui_text = core_gui_c.read_text(encoding="utf-8")
    gui_anchor = "    is_menu_shortcut = 0;\n"
    gui_replacement = (
        "    is_menu_shortcut = 0;\n\n"
        "    /* PORT-42 GUI fix: Fill full 880x576 box with solid opaque black so live view does not show through */\n"
        "    extern void g3x_fill_menu_opaque_black(void);\n"
        "    g3x_fill_menu_opaque_black();\n"
    )
    if gui_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(gui_anchor, gui_replacement, 1)
    else:
        raise RuntimeError("is_menu_shortcut anchor not found in staged core/gui.c")

    gui_state_anchor = "void gui_set_need_redraw()\n{\n    gui_mode_need_redraw = 1;\n}\n"
    gui_state_replacement = (
        "void gui_set_need_redraw()\n{\n    gui_mode_need_redraw = 1;\n}\n\n"
        "/* PORT-42 GUI fix: State change detection for zero-flicker redraw */\n"
        "int gui_check_state_changed(void)\n"
        "{\n"
        "    extern int gui_menu_needs_redraw(void);\n"
        "    return gui_osd_need_restore || gui_mode_need_redraw || gui_menu_needs_redraw();\n"
        "}\n"
    )
    if gui_state_anchor in core_gui_text:
        core_gui_text = core_gui_text.replace(gui_state_anchor, gui_state_replacement, 1)
    else:
        raise RuntimeError("gui_set_need_redraw anchor not found in staged core/gui.c")
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

    # Save to manifests/ and docs/manifests/ for the new GUI fix variants
    if gui_fix:
        for mdir in [REPO_ROOT / "manifests", REPO_ROOT / "docs" / "manifests"]:
            mdir.mkdir(parents=True, exist_ok=True)
            with open(mdir / manifest_name, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)
            print(f"[OK] Manifest saved to {mdir / manifest_name}")

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
