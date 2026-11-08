#!/usr/bin/env python3
"""PORT-25 T3: Opt-in Combined Breadcrumb Ladder + G3X_POWERON_FIX Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic candidate DISKBOOT.BIN combining:
1. G3X_POWERON_FIX=1: Bypasses the Stage 5 power-cut in sub_fc05b962_my.
2. LED_LADDER=1: Count-coded LED pulse ladder extended past loader into boot_prototype.c stages.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
- PORT-24 --poweron-fix build remains byte-identical:
  DISKBOOT.BIN SHA-256: faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056 (118,001 B).
- Reuses verified power / card-access LED MMIO register 0xD20B0884 (ON: 0x004D0002, OFF: 0x004C0003). Adds no new addresses.
- All pulses use calibrated framed timing with preemption tolerance (>= 50 ms difference at slow bound):
  ON delay: 0x00100000 (1,048,576 iterations) -> 50.0 ms (slow <= 150 ms) / 20.97 ms (nom) / 15.73 ms (fast)
  Pulse OFF gap: 0x00050000 (327,680 iterations) -> 15.625 ms (slow) / 6.55 ms (nom) / 4.91 ms (fast)
  Inter-digit gap: 0x00200000 (2,097,152 iterations) -> 100.0 ms (slow) / 41.94 ms (nom) / 31.46 ms (fast)
  Frame-end gap: 0x00400000 (4,194,304 iterations) -> 200.0 ms (slow) / 83.89 ms (nom) / 62.91 ms (fast)
- Final state is LED OFF (0x004C0003) after each frame and before firmware continuation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
LOADER_DIR = CHDK_PORT / "loader" / "g3x"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import (  # noqa: E402
    CC,
    AR,
    OBJCOPY,
    NM,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_loader as build_default_loader,
    encode_candidate_diskboot,
    generate_candidate_inspector,
    generate_manifest,
    extract_symbol_addr_from_nm,
    sha256_file,
    run_cmd,
)

CANDIDATE_PORT25_LADDER_FIX_DIR = os.path.join(REPO_ROOT, "candidate_port25_ladder_fix")
CANDIDATE_PORT25_LADDER_DIR = os.path.join(REPO_ROOT, "candidate_port25_ladder")
CANDIDATE_PORT25_POWERON_DIR = os.path.join(REPO_ROOT, "candidate_port25_poweron_fix")
CANDIDATE_PORT25_DEFAULT_DIR = os.path.join(REPO_ROOT, "candidate_port25_default")
CANDIDATE_PORT32_RESIDENT_DIR = os.path.join(REPO_ROOT, "candidate_port32_resident")
CANDIDATE_PORT33_OSD_DIR = os.path.join(REPO_ROOT, "candidate_port33_osd")
CANDIDATE_PORT34_KBD_DIR = os.path.join(REPO_ROOT, "candidate_port34_kbd")
CANDIDATE_PORT34_KBD_OSD_DIR = os.path.join(REPO_ROOT, "candidate_port34_kbd_osd")
CANDIDATE_PORT35_OSD2_DIR = os.path.join(REPO_ROOT, "candidate_port35_osd2")
CANDIDATE_PORT35_GUI_DIR = os.path.join(REPO_ROOT, "candidate_port35_gui")
CANDIDATE_PORT36_GUI2_DIR = os.path.join(REPO_ROOT, "candidate_port36_gui2")

# Backward compatibility alias
CANDIDATE_LADDER_FIX_DIR = CANDIDATE_PORT25_LADDER_FIX_DIR

G3X_RESIDENT_HEAP_START = 0x00368680
G3X_KBD_HEAP_START = 0x00368880
G3X_GUI_HEAP_START = 0x00368880
G3X_RESIDENT_CREATETASK_ADDR = 0xBFE14A3D
G3X_RESIDENT_HANDOFF_ADDR = 0xFC0D0126
G3X_RESIDENT_SLEEPTASK_VENEER = 0xFC31BF84
G3X_RESIDENT_SLEEPTASK_ADDR = 0xFCEF33B4
G3X_RESIDENT_STACK_SIZE = 0x2000
G3X_RESIDENT_PRIORITY = 0x19

G3X_KBD_TASKCREATE_ADDR = 0xFC1283D2
G3X_KBD_CREATETASK_STRICTLY = 0xFC31BE8C
G3X_KBD_PHYSW_RUN = 0x000082BC

G3X_OSD_ACTIVE_BITMAP_BUFFER_ADDR = 0x0000D2A4
G3X_OSD_BITMAP_BUFFER_ADDR = 0x0000D2A8
G3X_OSD_OPACITY_BUFFER_ADDR = 0xFC1837FC
G3X_OSD_TRANSFER_SRC_OVERLAY_ADDR = 0xFC380635

G3X_OSD2_ACTIVE_BITMAP_BUFFER_ADDR = 0x0000D2A4
G3X_OSD2_BITMAP_BUFFER_ADDR = 0x0000D2A8
G3X_OSD2_DISPLAYTYPE_ADDR = 0x00009740
G3X_OSD2_BITMAP_BUF0_ADDR = 0x5FE80000
G3X_OSD2_BITMAP_BUF1_ADDR = 0x5FD00000
G3X_OSD2_OPACITY_BUF0_ADDR = 0x5FC40000
G3X_OSD2_OPACITY_BUF1_ADDR = 0x5FB80000
G3X_OSD2_TRANSFER_SRC_OVERLAY_ADDR = 0xFC380635

G3X_GUI_PALETTE_CONTROL_ADDR = 0x00015DA4
G3X_GUI_ACTIVE_PALETTE_BUFFER_ADDR = 0x00015DB4
G3X_GUI_PALETTE_BUFFER_PTR_ADDR = 0x00015DBC
G3X_GUI_CANON_MENU_ACTIVE_ADDR = 0x0000D2E8
G3X_GUI_FOCUS_BUSY_ADDR = 0x00014BC0
G3X_GUI_ZOOM_BUSY_ADDR = 0x0000BEF8
G3X_GUI_ZOOM_STATUS_ADDR = 0x00010D74
G3X_GUI_RECREVIEW_HOLD_ADDR = 0x000095F0

LADDER_ENTRY_S = str(SUB_DIR / "loader_entry_breadcrumb.S")
LADDER_LOADER_C = str(SUB_DIR / "loader_main_breadcrumb.c")

G3X_LED_MMIO_ADDR = 0xD20B0884
G3X_LED_ON_VAL = 0x004D0002
G3X_LED_OFF_VAL = 0x004C0003

def generate_boot_prototype_ladder_c() -> str:
    sub_dir = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
    with open(sub_dir / "boot_prototype.c", "r", encoding="utf-8") as f:
        src = f.read()

    target_pwr = (
        '#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX /* PORT-24 opt-in short-press power-on fix */\n'
        '        "    bl      sub_fc1284ac\\n" "    movs    r0, #1\\n" "    b       loc_fc05b978\\n" "    nop\\n"\n'
        '#else\n'
        '        // Native Canon power-on button check (unmodified stock ROM handler)\n'
        '        "    bl      sub_fc1284ac\\n"\n'
        '        "    cbnz    r0, loc_fc05b978\\n"\n'
        '        "    bl      sub_fc05ba56\\n"\n'
        '#endif\n'
        '        "loc_fc05b976:\\n"\n'
        '        "    b       loc_fc05b976\\n"          // Safe halt if shutdown requested\n'
        '        "loc_fc05b978:\\n"'
    )

    repl_pwr = (
        '#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX /* PORT-24 opt-in short-press power-on fix */\n'
        '        "    bl      sub_fc1284ac\\n" "    movs    r0, #1\\n" "    b       loc_fc05b978\\n" "    nop\\n"\n'
        '#else\n'
        '        // Native Canon power-on button check (unmodified stock ROM handler)\n'
        '        "    bl      sub_fc1284ac\\n"\n'
        '        "    cbz     r0, 1f\\n"\n'
        '        "    b.w     loc_fc05b978\\n"\n'
        '        "1:\\n"\n'
        '        CORE_LADDER_PULSE_28 "    bl      sub_fc05ba56\\n"\n'
        '        "loc_fc05b976:\\n" CORE_LADDER_PULSE_29\n'
        '        "    b       loc_fc05b976\\n"\n'
        '#endif\n'
        '        "loc_fc05b978:\\n" CORE_LADDER_PULSE_25'
    )

    replacements = [
        ("#include \"boot_witness.h\"\n", "#include \"boot_witness.h\"\n#include \"led_breadcrumb.h\"\n"),
        ("\"    mov     sp, r0\\n\"", "\"    mov     sp, r0\\n\" CORE_LADDER_PULSE_11"),
        ("\"    blo     loc_zero_bss\\n\"", "\"    blo     loc_zero_bss\\n\" CORE_LADDER_PULSE_12"),
        ("\"    bl      witness_record_core\\n\"", "\"    bl      witness_record_core\\n\" CORE_LADDER_PULSE_13"),
        ("\"    mov     r0, sp\\n\"\n        \"    blx     sub_fc31b408\\n\"", "CORE_LADDER_PULSE_14 \"    mov     r0, sp\\n\"\n        \"    blx     sub_fc31b408\\n\""),
        ("sub_fc05b558_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"", "sub_fc05b558_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\" CORE_LADDER_PULSE_15"),
        ("sub_fc05b962_my(void)\n{\n    asm volatile (\n        \"    push    {r3, lr}\\n\"", "sub_fc05b962_my(void)\n{\n    asm volatile (\n        \"    push    {r3, lr}\\n\" CORE_LADDER_PULSE_21"),
        ("\"    bl      sub_fc05ba68\\n\"", "CORE_LADDER_PULSE_22 \"    bl      sub_fc05ba68\\n\" CORE_LADDER_PULSE_23"),
        ("\"    bl      sub_fc079404\\n\"", "\"    bl      sub_fc079404\\n\" CORE_LADDER_PULSE_24"),
        (target_pwr, repl_pwr),
        ("\"    ldr     r0, =0xfc05b9a0\\n\"", "\"    ldr     r0, =0xfc05b9a0\\n\"\n        CORE_LADDER_PULSE_26"),
        ("task_Startup_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"", "task_Startup_my(void)\n{\n    asm volatile (\n        \"    push    {r4, lr}\\n\"\n        CORE_LADDER_PULSE_31"),
        ("\"    bl      sub_fc418eec\\n\"", "\"    bl      sub_fc418eec\\n\" CORE_LADDER_PULSE_32"),
        ("\"    movs    r0, #0\\n\"\n        \"    bl      sub_fc05c4e0\\n\"", "CORE_LADDER_PULSE_33 \"    movs    r0, #0\\n\"\n        \"    bl      sub_fc05c4e0\\n\""),
        ("\"    blx     sub_fc31b1f4\\n\"\n        \"1:\\n\"", "\"    blx     sub_fc31b1f4\\n\"\n        \"1:\\n\" CORE_LADDER_PULSE_34"),
        ("\"    bl      sub_fc418f2a\\n\"", "CORE_LADDER_PULSE_35 \"    bl      sub_fc418f2a\\n\" CORE_LADDER_PULSE_41"),
        ("\"    bl      sub_fc1283d2\\n\"", "CORE_LADDER_PULSE_42 \"    bl      sub_fc1283d2\\n\" CORE_LADDER_PULSE_43"),
        ("\"    pop.w   {r4, lr}\\n\"\n        \"    b.w     sub_fc0d0126\\n\"", "CORE_LADDER_PULSE_44 \"    pop.w   {r4, lr}\\n\"\n        \"    b.w     sub_fc0d0126\\n\""),
    ]
    for target, repl in replacements:
        if target not in src:
            raise ValueError(f"Target pattern not found in boot_prototype.c: {target!r}")
        src = src.replace(target, repl, 1)
    return src


BOOT_PROTOTYPE_LADDER_C = generate_boot_prototype_ladder_c()


def generate_boot_prototype_resident_c() -> str:
    """Generate boot_prototype C source with opt-in G3X_RESIDENT=1 blocks."""
    src = generate_boot_prototype_ladder_c()

    target_new_sa = "const char * const new_sa = &_end;\n"
    repl_new_sa = (
        "#if defined(G3X_KBD) && (G3X_KBD == 1)\n"
        "/* Raised heap start 0x00368880 [docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD] */\n"
        "#define G3X_KBD_HEAP_START 0x00368880\n"
        "const char * const new_sa = (const char *)G3X_KBD_HEAP_START;\n"
        "#elif defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "/* Raised heap start 0x00368680 [docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-HEAP-SETUP] */\n"
        "const char * const new_sa = (const char *)G3X_RESIDENT_HEAP_START;\n"
        "#else\n"
        "const char * const new_sa = &_end;\n"
        "#endif\n"
    )

    target_heap_ldr = (
        "        // Load shifted heap base from new_sa (&_end)\n"
        '        "    ldr     r4, =new_sa\\n"\n'
        '        "    ldr     r4, [r4]\\n"'
    )
    repl_heap_ldr = (
        "#if defined(G3X_KBD) && (G3X_KBD == 1)\n"
        "        /* Load raised heap base 0x00368880 [docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD] */\n"
        '        "    ldr     r4, =0x00368880\\n"\n'
        "#elif defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "        /* Load raised heap base 0x00368680 [docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-HEAP-SETUP] */\n"
        '        "    ldr     r4, =0x00368680\\n"\n'
        "#else\n"
        "        // Load shifted heap base from new_sa (&_end)\n"
        '        "    ldr     r4, =new_sa\\n"\n'
        '        "    ldr     r4, [r4]\\n"\n'
        "#endif"
    )

    target_task_physw = 'CORE_LADDER_PULSE_42 "    bl      sub_fc1283d2\\n" CORE_LADDER_PULSE_43'
    repl_task_physw = (
        'CORE_LADDER_PULSE_42\n'
        '#if defined(G3X_KBD) && (G3X_KBD == 1)\n'
        '        "    bl      sub_fc1283d2_my\\n"\n'
        '#else\n'
        '        "    bl      sub_fc1283d2\\n"\n'
        '#endif\n'
        '        CORE_LADDER_PULSE_43'
    )

    target_handoff = (
        'CORE_LADDER_PULSE_44 "    pop.w   {r4, lr}\\n"\n'
        '        "    b.w     sub_fc0d0126\\n"'
    )
    repl_handoff = (
        "CORE_LADDER_PULSE_44\n"
        "#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)\n"
        "        /* Spawn resident heartbeat task via CreateTask at 0xBFE14A3D after ladder\n"
        "         * completes and at the sub_fc0d0126 (0xFC0D0126) handoff point\n"
        "         * [reference/finsig_gm110c/stubs_entry.S:200;\n"
        "         *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-CREATETASK-VENEER;\n"
        "         *  evidence/port31_manifest.json: PORT29-ROM-CREATETASK;\n"
        "         *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-FIRMWARE-CONT] */\n"
        "        G3X_SPAWN_RESIDENT_HEARTBEAT\n"
        "#endif\n"
        '        "    pop.w   {r4, lr}\\n"\n'
        '        "    b.w     sub_fc0d0126\\n"'
    )

    resident_replacements = [
        (target_new_sa, repl_new_sa),
        (target_heap_ldr, repl_heap_ldr),
        (target_task_physw, repl_task_physw),
        (target_handoff, repl_handoff),
    ]
    for target, repl in resident_replacements:
        if target not in src:
            raise ValueError(f"Resident target pattern not found in ladder source: {target!r}")
        src = src.replace(target, repl, 1)

    resident_task_block = """
#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)
#if defined(G3X_OSD) && (G3X_OSD == 1)
#include "osd_test_overlay.h"
#endif
#if defined(G3X_OSD2) && (G3X_OSD2 == 1)
#include "osd2_test_overlay.h"
#endif
#if defined(G3X_KBD) && (G3X_KBD == 1)
#include "kbd_candidate.h"
#endif
/* =============================================================================
 * PORT-32 Resident Heartbeat Task (G3X_RESIDENT=1)
 * Blinks power / card-access LED (0xD20B0884, ON 0x004D0002, OFF 0x004C0003) at ~1 Hz
 * in a double-short-blink pattern (100 ms ON, 100 ms OFF, 100 ms ON, 700 ms OFF)
 * using manifest-cited SleepTask (0xFC31BF84 / 0xFCEF33B4; delay unit ms INFERRED).
 * Stack alignment at task entry is INFERRED (no inline sp write in C task body).
 * Manifest citations:
 * - docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json: PORT25-ROM-GPIO-WRITE-MMIO
 * - docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-SLEEPTASK-VENEER
 * - evidence/port31_manifest.json: PORT30-ROM-SLEEPTASK, PORT31-ROM-SLEEPTASK-BODY
 * ============================================================================= */
void __attribute__((noinline)) g3x_resident_heartbeat_task(void)
{
#if defined(G3X_GUI) && (G3X_GUI == 1)
    /* Signal spytask/GUI start readiness after InitFileModules (0xFC0BB6FE) has
     * completed in task_Startup_my, matching sibling boot sequence
     * [chdk-port/platform/g7x/sub/100d/boot.c:423;
     *  chdk-port/platform/g5x/sub/100c/boot.c:524;
     *  chdk-port/platform/sx60hs/sub/100f/boot.c:556] (INFERRED) */
    extern void core_spytask_can_start(void);
    core_spytask_can_start();
#endif
#if defined(G3X_OSD) && (G3X_OSD == 1)
    g3x_spawn_osd_task();
#endif
    for (;;) {
#if defined(G3X_KBD) && (G3X_KBD == 1)
        if (kbd_is_blocked()) {
            /* ALT mode ON: double blink per second */
            g3x_resident_led_write(G3X_LADDER_ON_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
            g3x_resident_led_write(G3X_LADDER_OFF_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_GAP_MS);
            g3x_resident_led_write(G3X_LADDER_ON_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
            g3x_resident_led_write(G3X_LADDER_OFF_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_PAUSE_MS);
        } else {
            /* ALT mode OFF: ~1 Hz single blink */
            g3x_resident_led_write(G3X_LADDER_ON_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
            g3x_resident_led_write(G3X_LADDER_OFF_VAL);
            g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS + G3X_HEARTBEAT_GAP_MS + G3X_HEARTBEAT_PAUSE_MS);
        }
#else
        g3x_resident_led_write(G3X_LADDER_ON_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
        g3x_resident_led_write(G3X_LADDER_OFF_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_GAP_MS);
        g3x_resident_led_write(G3X_LADDER_ON_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_ON_MS);
        g3x_resident_led_write(G3X_LADDER_OFF_VAL);
        g3x_resident_sleep_inferred_ms(G3X_HEARTBEAT_PAUSE_MS);
#endif
    }
}
#endif
"""
    return src + resident_task_block


BOOT_PROTOTYPE_RESIDENT_C = generate_boot_prototype_resident_c()


def generate_gui_candidate_c() -> str:
    """Generate kbd-task-driven CHDK GUI driver and RAM-only/no-op stubs for G3X_GUI=1."""
    return r'''#include "platform.h"
#include "core.h"
#include "conf.h"
#include "keyboard.h"
#include "gui.h"
#include "gui_draw.h"
#include "gui_menu.h"
#include "gui_lang.h"
#include "gui_osd.h"
#include "camera_info.h"
#include "font.h"

/* =============================================================================
 * PORT-35 Part B: G3X_GUI=1 CHDK core GUI/ALT menu on the OSD2 draw path
 *
 * Sibling citations:
 * - chdk-port/platform/g7x/kbd.c:70-82 (core_spytask / GUI driven from mykbd_task)
 * - chdk-port/platform/g7x/lib.c:136-145, 171-225, 303-358 (DIGIC 6 YUV OSD2 + palette)
 * - chdk-port/platform/g7x/sub/100d/boot.c:410-434 (core_spytask_can_start after InitFileModules)
 * - chdk-port/platform/g5x/lib.c:9-33, 162-220; g5x/sub/100c/boot.c:524
 * - chdk-port/platform/sx60hs/lib.c:14-20, 265-274; sx60hs/sub/100f/boot.c:556
 * - chdk-port/core/main.c:236-337 (core_spytask startup & gui_redraw loop)
 * ============================================================================= */

extern void g3x_osd2_update_screen_dimensions(void);
extern void gui_init(void);

volatile long spytask_can_start = 0;
int chdk_started_flag = 0;
int no_modules_flag = 0;
int memdmp_delay = 0;
int raw_need_postprocess = 0;
char *current_raw_addr = 0;

void core_spytask_can_start(void)
{
    spytask_can_start = 1;
}

void core_spytask(void)
{
    /* Replaced by kbd-task-driven g3x_gui_kbd_redraw() */
}

/* Driven from mykbd_task -> g3x_osd2_kbd_redraw on every keyboard tick
 * [chdk-port/platform/g7x/kbd.c:70-82; chdk-port/core/main.c:236-337] */
void g3x_gui_kbd_redraw(int alt_active)
{
    static int gui_initialized = 0;
    static int prev_alt_active = 0;
    static unsigned int tick_cnt = 0;

    if (!spytask_can_start) {
        return;
    }

    if (!gui_initialized) {
        gui_initialized = 1;
        g3x_osd2_update_screen_dimensions();
        camera_info_init();
        conf_restore();
        /* Ensure built-in fonts are initialized in RAM before gui_init() */
        rbf_load_from_file("", FONT_CP_WIN);
        rbf_load_symbol("");
        gui_init();
        chdk_started_flag = 1;
    }

    int entered_alt = (alt_active != 0) && (prev_alt_active == 0);
    int left_alt = (alt_active == 0) && (prev_alt_active != 0);
    prev_alt_active = (alt_active != 0);

    g3x_osd2_update_screen_dimensions();

    /* Process pending ALT mode transition (ALT_MODE_ENTER / ALT_MODE_LEAVE)
     * [chdk-port/core/main.c:292; chdk-port/core/gui.c:3057-3101] */
    gui_activate_alt_mode();

    if (entered_alt) {
        /* Open CHDK Main Menu immediately on ALT entry; d-pad and SET navigate
         * [chdk-port/core/gui.c:2948-2958, 3078-3082; chdk-port/core/gui_menu.c:212-239] */
        gui_menu_init(&root_menu);
        gui_set_mode(&menuGuiHandler);
    }

    if (left_alt) {
        /* Erase CHDK menu from both OSD2 buffers and return control to stock UI
         * [chdk-port/core/gui.c:2983-2988, 3085-3096] */
        gui_set_need_restore();
        gui_redraw(1);
        return;
    }

    if (alt_active) {
        extern int check_gui_needs_redraw(void);
        int force_redraw = entered_alt
            || check_gui_needs_redraw()
            || (kbd_get_clicked_key() != 0)
            || (kbd_get_pressed_key() != 0)
            || ((tick_cnt & 3u) == 0u);
        tick_cnt++;
        gui_redraw(force_redraw);

#if defined(G3X_GUI2) && (G3X_GUI2 == 1)
        /* Draw 1-px border at (0,0)-(width-1, height-1) [PORT-36 TRIAL DIAGNOSTIC] */
        int w1 = camera_screen.width - 1;
        int h1 = camera_screen.height - 1;
        draw_line(0, 0, w1, 0, COLOR_WHITE);
        draw_line(0, h1, w1, h1, COLOR_WHITE);
        draw_line(0, 0, 0, h1, COLOR_WHITE);
        draw_line(w1, 0, w1, h1, COLOR_WHITE);

        /* Show live displaytype plus camera_screen width/buffer_width/height [PORT-36 TRIAL DIAGNOSTIC] */
        char diag[64];
        extern int displaytype;
        sprintf(diag, "dt=%d w=%d bw=%d h=%d", displaytype, camera_screen.width, camera_screen.buffer_width, camera_screen.height);
        draw_string(2, 2, diag, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
#endif
    }
}

/* FINSIG palette pointers [reference/finsig_gm110c/stubs_entry.S:105-107]
 * Sibling citations: chdk-port/platform/g7x/lib.c:303-358;
 * chdk-port/platform/g5x/lib.c:186-210; chdk-port/platform/sx60hs/lib.c:265-274 */
extern int active_palette_buffer;
extern int **palette_buffer_ptr;

void *vid_get_bitmap_active_palette(void)
{
    unsigned int idx = (unsigned int)active_palette_buffer;
    if (palette_buffer_ptr == 0 || idx > 7u) {
        return 0;
    }
    int *pal = palette_buffer_ptr[idx];
    if (pal == 0) {
        return 0;
    }
    return pal + 1;
}

int vid_get_palette_type(void)
{
    return 3;
}

int vid_get_palette_size(void)
{
    return 256 * 4;
}

/* Outside ALT mode, pass all keys to stock Canon UI without CHDK interception */
int __wrap_gui_kbd_process(void)
{
    extern int kbd_is_blocked(void);
    extern int __real_gui_kbd_process(void);
    if (!kbd_is_blocked()) {
        return 0;
    }
    return __real_gui_kbd_process();
}

/* Keep non-menu OSD drawing off so closing the menu leaves a clean screen */
void __wrap_gui_draw_osd(void)
{
}

const char *__wrap_gui_alt_mode_button_enum(int change, int arg)
{
    (void)change;
    (void)arg;
    conf.alt_mode_button = KEY_PLAYBACK;
    return "Playback";
}

/* Add a selectable "Back" item (MENUITEM_UP) at the bottom of root_menu when
 * user menu is not enabled so d-pad + SET can also close root_menu directly */
void __wrap_set_usermenu_state(void)
{
    extern void __real_set_usermenu_state(void);
    __real_set_usermenu_state();
    if (!conf.user_menu_enable && root_menu.menu != 0) {
        CMenuItem *items = (CMenuItem *)root_menu.menu;
        items[9].symbol = 0x51;
        items[9].opt_len = 0;
        items[9].type = MENUITEM_UP;
        items[9].text = LANG_MENU_BACK;
        items[9].value = 0;
        items[9].arg = 0;
    }
}

int core_get_free_memory(void)
{
    cam_meminfo meminfo;
    GetMemInfo(&meminfo);
    return meminfo.free_size;
}

/* Compile out / stub script loading and execution (RAM-only menu) */
char script_title[36] = "";
_chdk_version_t script_version = { 0 };
sc_param *script_params = 0;

static CMenuItem g3x_script_submenu_items[] = {
    { 0x51, 0, MENUITEM_UP, LANG_MENU_BACK, 0, 0 },
    { 0 }
};
CMenu script_submenu = { 0x27, LANG_MENU_SCRIPT_TITLE, g3x_script_submenu_items };

extern void gui_chdk_draw(int force_redraw);
gui_handler scriptGuiHandler = { GUI_MODE_SCRIPT, gui_chdk_draw, 0, 0, 0, 0 };

void script_load(const char *fn)
{
    (void)fn;
}

void __wrap_script_load(const char *fn)
{
    (void)fn;
}

long script_start_gui(int autostart)
{
    (void)autostart;
    return 0;
}

long __wrap_script_start_gui(int autostart)
{
    (void)autostart;
    return 0;
}

void save_params_values(int unconditional)
{
    (void)unconditional;
}

void __wrap_save_params_values(int unconditional)
{
    (void)unconditional;
}

void script_reset_to_default_params_values(void) {}
void script_check_terminate(void) {}
void script_console_add_line(long str_id) { (void)str_id; }
void script_console_add_error(long str_id) { (void)str_id; }
void script_end(void) {}
int script_is_running(void) { return 0; }
long script_stack_start(void) { return 0; }
void script_wait_terminate(void) {}
void script_print_screen_statement(int val) { (void)val; }
void script_set_terminate_key(int key, const char *key_name) { (void)key; (void)key_name; }

void script_get_alt_text(char *buf)
{
    if (buf) {
        buf[0] = '<';
        buf[1] = 'A';
        buf[2] = 'L';
        buf[3] = 'T';
        buf[4] = '>';
        buf[5] = '\0';
    }
}

/* Compile out / stub fileutil, raw, ptp, remotecap, and card-write hooks */
void make_pixel_list(char *ptr, int size) { (void)ptr; (void)size; }
void patch_bad_pixel(unsigned int x, unsigned int y) { (void)x; (void)y; }
void raw_prepare_develop(const char *filename, int prompt) { (void)filename; (void)prompt; }
int raw_savefile(void) { return 0; }
void raw_postprocess(void) {}
void start_ptp_script(void) {}
void __wrap_mark_filesystem_bootable(void) {}
void schedule_memdump(void) {}

char *load_file(const char *name, int *size, int add0)
{
    (void)name;
    if (size) {
        *size = 0;
    }
    (void)add0;
    return 0;
}

char *__wrap_load_file(const char *name, int *size, int add0)
{
    return load_file(name, size, add0);
}

char *load_file_to_length(const char *name, int *size, int add0, int length)
{
    (void)name;
    if (size) {
        *size = 0;
    }
    (void)add0;
    (void)length;
    return 0;
}

char *__wrap_load_file_to_length(const char *name, int *size, int add0, int length)
{
    return load_file_to_length(name, size, add0, length);
}

int process_file(const char *name, void *callback, int add0)
{
    (void)name;
    (void)callback;
    (void)add0;
    return 0;
}

int __wrap_process_file(const char *name, void *callback, int add0)
{
    return process_file(name, callback, add0);
}

int load_int_value_file(const char *name, int *value_p)
{
    (void)name;
    (void)value_p;
    return 0;
}

int __wrap_load_int_value_file(const char *name, int *value_p)
{
    return load_int_value_file(name, value_p);
}

int save_int_value_file(const char *name, int value)
{
    (void)name;
    (void)value;
    return 0;
}

int __wrap_save_int_value_file(const char *name, int value)
{
    return save_int_value_file(name, value);
}

/* Safe C replacements for stubs_entry_2.S so NULL_SUB (0xFC000011) is never linked */
int _GetFocusLensSubjectDistanceFromLens(void)
{
    /* Delegate to FINSIG _GetFocusLensSubjectDistance (0xFC3821AF)
     * [reference/finsig_gm110c/stubs_entry.S:233] */
    extern int _GetFocusLensSubjectDistance(void);
    return _GetFocusLensSubjectDistance();
}

int _GetDrive_TotalClusters(int drive) { (void)drive; return 0; }
int _Feof_Fut(int fd) { (void)fd; return 1; }
int _Fflush_Fut(int fd) { (void)fd; return 0; }
int _PostLogicalEventToUI(int id, int x) { (void)id; (void)x; return 0; }
int _PostLogicalEventForNotPowerType(int id, int x) { (void)id; (void)x; return 0; }
void _LockMainPower(void) {}
void _UnlockMainPower(void) {}
void _SetAutoShutdownTime_FW(int t, void *cb) { (void)t; (void)cb; }
void _EnterToCompensationEVF(void) {}
void _ExitFromCompensationEVF(void) {}
void _ExpCtrlTool_StartContiAE(int a, int b) { (void)a; (void)b; }
void _ExpCtrlTool_StopContiAE(int a, int b) { (void)a; (void)b; }
int _RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
void _Restart(unsigned int opt) { (void)opt; }
int _SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int _SetFileTimeStamp(const char *fn, int t1, int t2) { (void)fn; (void)t1; (void)t2; return 0; }
int _SetParameterData(int id, void *buf, int size) { (void)id; (void)buf; (void)size; return 0; }
int _WriteSDCard(unsigned int d, unsigned int s, unsigned int n, void *b) { (void)d; (void)s; (void)n; (void)b; return 0; }
int _apex2us(int apex_val) { (void)apex_val; return 0; }
int _reboot_fw_update(const char *fw_update) { (void)fw_update; return 0; }
int _CancelHPTimer(int h) { (void)h; return 0; }
void _UnsetZoomForMovie(void) {}
void _VTMLock(void) {}
void _VTMUnlock(void) {}
void _MakeSDCardBootable(int d) { (void)d; }
int _GetImageFolder(void *a, int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; return 0; }
void _captseq_raw_addr_init(void) {}
void _PutInNdFilter_FW(void) {}
void _PutOutNdFilter_FW(void) {}
void _MoveFocusLensToDistance_FW(short *d) { (void)d; }

/* Safe RAM-only C stubs for uncalled wrappers.o / shooting.thm.o externs so
 * stubs_entry_gui.S contains only the FINSIG entries the menu needs and no
 * file-I/O, directory, or actuator firmware veneers are linked. */
int _Close(int fd) { (void)fd; return -1; }
int _close(int fd) { (void)fd; return -1; }
int _closedir(void *d) { (void)d; return -1; }
int _CreateBinarySemaphore(char *n, int v) { (void)n; (void)v; return 0; }
int _CreateTask(const char *n, int p, int s, void *e, long a) { (void)n; (void)p; (void)s; (void)e; (void)a; return 0; }
int _DeleteDirectory_Fut(const char *n) { (void)n; return -1; }
int _DeleteFile_Fut(const char *n) { (void)n; return -1; }
void _DoAELock(void) {}
void _DoAFLock(void) {}
int _ExecuteEventProcedure(const char *n, ...) { (void)n; return -1; }
void _ExitTask(void) {}
int _Fclose_Fut(void *f) { (void)f; return -1; }
char *_Fgets_Fut(char *s, int n, void *f) { (void)s; (void)n; (void)f; return 0; }
void *_Fopen_Fut(const char *n, const char *m) { (void)n; (void)m; return 0; }
unsigned int _Fread_Fut(void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _Fseek_Fut(void *f, long o, int w) { (void)f; (void)o; (void)w; return -1; }
unsigned int _Fwrite_Fut(const void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _GetAdChValue(int c) { (void)c; return 0; }
unsigned int _GetDrive_ClusterSize(int d) { (void)d; return 0; }
unsigned int _GetDrive_FreeClusters(int d) { (void)d; return 0; }
void _LEDDrive(int l, int a) { (void)l; (void)a; }
int _MakeDirectory_Fut(const char *n, int u) { (void)n; (void)u; return -1; }
int _MoveOpticalZoomAt(int p) { (void)p; return 0; }
int _Open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
int _open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
void *_OpenFastDir(const char *n) { (void)n; return 0; }
void _PB2Rec(void) {}
void _Rec2PB(void) {}
int _PT_MFOff(void) { return 0; }
int _PT_MFOn(void) { return 0; }
int _PT_MoveDigitalZoomToWide(void) { return 0; }
void _PT_PlaySound(short s, void *c, int u) { (void)s; (void)c; (void)u; }
int _Read(int fd, void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _ReadFastDir(void *d, void *b) { (void)d; (void)b; return 0; }
void _SetCurrentCaptureModeType(void) {}
int _SetHPTimerAfterNow(int d, void *g, void *b, int p) { (void)d; (void)g; (void)b; (void)p; return 0; }
void _SetLogicalEventActive(unsigned int id, unsigned int s) { (void)id; (void)s; }
void _SetScriptMode(unsigned int m) { (void)m; }
void _TurnOffBackLight(void) {}
void _TurnOnBackLight(void) {}
void _TurnOffDisplay(void) {}
void _TurnOnDisplay(void) {}
void _UnlockAE(void) {}
void _UnlockAF(void) {}
int _Write(int fd, const void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _add_ptp_handler(int o, void *h, int u) { (void)o; (void)h; (void)u; return 0; }
void *_exmem_ualloc(unsigned int t, unsigned int s, void *a) { (void)t; (void)s; (void)a; return 0; }
void _exmem_ufree(unsigned int t) { (void)t; }
int _get_fstype(int d) { (void)d; return 0; }
int _lseek(int fd, int o, int w) { (void)fd; (void)o; (void)w; return -1; }
void _set_control_event(int e) { (void)e; }
int _stat(const char *n, void *p) { (void)n; (void)p; return -1; }

void __wrap_play_sound(unsigned int sound) { (void)sound; }
void __wrap_camera_set_led(int led, int state, int bright) { (void)led; (void)state; (void)bright; }
void __wrap_debug_led(int state) { (void)state; }

/* Linker wrappers blocking all file open, write, directory, and SD card paths */
int __wrap_write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
unsigned int __wrap_fwrite(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
unsigned int __wrap__Fwrite_Fut(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
int __wrap_open(const char *name, int flags, int mode) { (void)name; (void)flags; (void)mode; return -1; }
int __wrap__open(const char *name, int flags, int mode) { (void)name; (void)flags; (void)mode; return -1; }
int __wrap__Open(const char *name, int flags, int mode) { (void)name; (void)flags; (void)mode; return -1; }
void *__wrap_fopen(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
void *__wrap__Fopen_Fut(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
int __wrap_mkdir(const char *name) { (void)name; return -1; }
int __wrap_mkdir_if_not_exist(const char *dirname) { (void)dirname; return -1; }
int __wrap__MakeDirectory_Fut(const char *name, int unk) { (void)name; (void)unk; return -1; }
int __wrap_remove(const char *name) { (void)name; return -1; }
int __wrap__DeleteFile_Fut(const char *name) { (void)name; return -1; }
int __wrap__DeleteDirectory_Fut(const char *name) { (void)name; return -1; }
int __wrap_rename(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap__RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap_utime(const char *file, void *newTimes) { (void)file; (void)newTimes; return -1; }
int __wrap_stat(const char *name, void *pStat) { (void)name; (void)pStat; return -1; }
void *__wrap_opendir(const char *name) { (void)name; return 0; }
void *__wrap_opendir_chdk(const char *name, unsigned int flags) { (void)name; (void)flags; return 0; }
void *__wrap_readdir(void *d) { (void)d; return 0; }
int __wrap_closedir(void *d) { (void)d; return 0; }
int __wrap__WriteSDCard(unsigned int drive, unsigned int start_sect, unsigned int num_sect, void *buf) { (void)drive; (void)start_sect; (void)num_sect; (void)buf; return 0; }
void __wrap__MakeSDCardBootable(int drive) { (void)drive; }
int __wrap__SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int __wrap__SetFileTimeStamp(const char *fn, int time1, int time2) { (void)fn; (void)time1; (void)time2; return 0; }
int __wrap__ExecuteEventProcedure(const char *name, ...) { (void)name; return -1; }
void __wrap_rbf_load_from_file(char *file, int codepage)
{
    (void)file;
    extern void __real_rbf_load_from_file(char *f, int cp);
    __real_rbf_load_from_file("", codepage);
}
int __wrap_rbf_load_symbol(char *file)
{
    (void)file;
    extern int __real_rbf_load_symbol(char *f);
    return __real_rbf_load_symbol("");
}
void __wrap_lang_load_from_file(const char *file) { (void)file; }
int __wrap_read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap_lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap__lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap_close(int fd) { (void)fd; return -1; }
int __wrap__close(int fd) { (void)fd; return -1; }
int __wrap__Close(int fd) { (void)fd; return -1; }
'''


def generate_stubs_entry_gui_s() -> str:
    """Generate minimal stubs_entry_gui.S with only the FINSIG entries the menu needs."""
    return r'''/* =============================================================================
 * PORT-35 Part B: G3X_GUI=1 minimal FINSIG stubs_entry table
 * Every entry below is from reference/finsig_gm110c/stubs_entry.S (label FINSIG)
 * or chdk-port/platform/g3x/sub/110c/stubs_entry.S.
 * File-write, file-open, file-delete, and directory firmware veneers are omitted.
 * ============================================================================= */
#include "stubs_asm.h"

DEF(ctypes                            ,0xfc616f54) // reference/finsig_gm110c/stubs_entry.S:170
DEF(physw_run                         ,0x000082bc) // reference/finsig_gm110c/stubs_entry.S:171
DEF(physw_sleep_delay                 ,0x000082c4) // reference/finsig_gm110c/stubs_entry.S:172
DEF(physw_status                      ,0x00040dac) // reference/finsig_gm110c/stubs_entry.S:173
DEF(fileio_semaphore                  ,0x000149c0) // reference/finsig_gm110c/stubs_entry.S:174
DEF(focus_len_table                   ,0xfdf317d8) // chdk-port/platform/g3x/sub/110c/stubs_entry.S:179
DEF(FlashParamsTable                  ,0xfca9129c) // reference/finsig_gm110c/stubs_entry.S:176
DEF(playrec_mode                      ,0x0000c4d4) // reference/finsig_gm110c/stubs_entry.S:177
DEF(jpeg_count_str                    ,0x0012c39c) // reference/finsig_gm110c/stubs_entry.S:178
DEF(zoom_busy                         ,0x0000bef8) // reference/finsig_gm110c/stubs_entry.S:179
DEF(focus_busy                        ,0x00014bc0) // reference/finsig_gm110c/stubs_entry.S:180
DEF(imager_active                     ,0x000086bc) // reference/finsig_gm110c/stubs_entry.S:181
DEF(canon_menu_active                 ,0x0000d2e8) // reference/finsig_gm110c/stubs_entry.S:182
DEF(file_counter_var                  ,0x00014864) // reference/finsig_gm110c/stubs_entry.S:183
DEF(active_bitmap_buffer              ,0x0000d2a4) // reference/finsig_gm110c/stubs_entry.S:186
DEF(displaytype                       ,0x00009740) // reference/finsig_gm110c/stubs_entry.S:187
DEF(bitmap_buffer                     ,0x0000d2a8) // reference/finsig_gm110c/stubs_entry.S:188
DEF(palette_control                   ,0x00015da4) // reference/finsig_gm110c/stubs_entry.S:189
DEF(palette_buffer_ptr                ,0x00015dbc) // reference/finsig_gm110c/stubs_entry.S:190
DEF(active_palette_buffer             ,0x00015db4) // reference/finsig_gm110c/stubs_entry.S:191
DEF_CONST(uiprop_count                ,0x000000d1) // reference/finsig_gm110c/stubs_entry.S:192
DEF(exmem_alloc_table                 ,0x00049040) // reference/finsig_gm110c/stubs_entry.S:193
DEF(exmem_types_table                 ,0xfce955fc) // reference/finsig_gm110c/stubs_entry.S:194
DEF_CONST(exmem_type_count            ,0x00000024) // reference/finsig_gm110c/stubs_entry.S:195

NHSTUB(AllocateUncacheableMemory              ,0xfc144471) // reference/finsig_gm110c/stubs_entry.S:197
NHSTUB(DebugAssert                            ,0x010e1001) // reference/finsig_gm110c/stubs_entry.S:201
NHSTUB(FreeUncacheableMemory                  ,0xfc14449d) // reference/finsig_gm110c/stubs_entry.S:218
NHSTUB(GetBatteryTemperature                  ,0xfc12da91) // reference/finsig_gm110c/stubs_entry.S:221
NHSTUB(GetCCDTemperature                      ,0xfc12da35) // reference/finsig_gm110c/stubs_entry.S:222
NHSTUB(GetCurrentAvValue                      ,0xfc0d8e55) // reference/finsig_gm110c/stubs_entry.S:223
NHSTUB(GetCurrentShutterSpeed                 ,0xfc144dd3) // reference/finsig_gm110c/stubs_entry.S:224
NHSTUB(GetUsableMaxAv                         ,0xfc555d21) // reference/finsig_gm110c/stubs_entry.S:225
NHSTUB(GetUsableMinAv                         ,0xfc555d0f) // reference/finsig_gm110c/stubs_entry.S:226
NHSTUB(get_nd_value                           ,0xfc493a51) // reference/finsig_gm110c/stubs_entry.S:227
NHSTUB(get_current_nd_value                   ,0xfc493a2b) // reference/finsig_gm110c/stubs_entry.S:228
NHSTUB(GetFocusLensSubjectDistance            ,0xfc3821af) // reference/finsig_gm110c/stubs_entry.S:232
NHSTUB(GetKbdState                            ,0xfc08ef67) // reference/finsig_gm110c/stubs_entry.S:234
NHSTUB(GetMemInfo                             ,0xfc610ab9) // reference/finsig_gm110c/stubs_entry.S:235
NHSTUB(GetOpticalTemperature                  ,0xfc12daeb) // reference/finsig_gm110c/stubs_entry.S:236
NHSTUB(GetParameterData                       ,0xfc275feb) // reference/finsig_gm110c/stubs_entry.S:237
NHSTUB(GetPropertyCase                        ,0xfc362f91) // reference/finsig_gm110c/stubs_entry.S:238
NHSTUB(GetSystemTime                          ,0xfc60243d) // reference/finsig_gm110c/stubs_entry.S:239
NHSTUB(GetVRAMHPixelsSize                     ,0xfc0d360b) // reference/finsig_gm110c/stubs_entry.S:240
NHSTUB(GetVRAMVPixelsSize                     ,0xfc0d3613) // reference/finsig_gm110c/stubs_entry.S:241
NHSTUB(GetZoomLensCurrentPoint                ,0xfc37deeb) // reference/finsig_gm110c/stubs_entry.S:242
NHSTUB(GetZoomLensCurrentPosition             ,0xfc37decb) // reference/finsig_gm110c/stubs_entry.S:243
NHSTUB(GiveSemaphore                          ,0xbfe15459) // reference/finsig_gm110c/stubs_entry.S:244
NHSTUB(IsStrobeChargeCompleted                ,0xfc0bcaaf) // reference/finsig_gm110c/stubs_entry.S:245
NHSTUB(LocalTime                              ,0x010e1581) // reference/finsig_gm110c/stubs_entry.S:247
NHSTUB(SetPropertyCase                        ,0xfc362e5d) // reference/finsig_gm110c/stubs_entry.S:277
NHSTUB(SleepTask                              ,0xbfe14969) // reference/finsig_gm110c/stubs_entry.S:279
NHSTUB(TakeSemaphore                          ,0xbfe153e1) // reference/finsig_gm110c/stubs_entry.S:280
NHSTUB(VbattGet                               ,0xfc0bb591) // reference/finsig_gm110c/stubs_entry.S:288
NHSTUB(_log                                   ,0x011032f8) // reference/finsig_gm110c/stubs_entry.S:291
NHSTUB(_log10                                 ,0x01103818) // reference/finsig_gm110c/stubs_entry.S:292
NHSTUB(_pow                                   ,0x01103980) // reference/finsig_gm110c/stubs_entry.S:293
NHSTUB(_sqrt                                  ,0x01105a00) // reference/finsig_gm110c/stubs_entry.S:294
NHSTUB(free                                   ,0xfc38155b) // reference/finsig_gm110c/stubs_entry.S:301
NHSTUB(kbd_p1_f                               ,0xfc12868d) // reference/finsig_gm110c/stubs_entry.S:302
NHSTUB(kbd_p1_f_cont                          ,0xfc128695) // reference/finsig_gm110c/stubs_entry.S:303
NHSTUB(kbd_p2_f                               ,0xfc12811f) // reference/finsig_gm110c/stubs_entry.S:304
NHSTUB(kbd_read_keys_r2                       ,0xfc08ee0d) // reference/finsig_gm110c/stubs_entry.S:306
NHSTUB(malloc                                 ,0xfc381525) // reference/finsig_gm110c/stubs_entry.S:308
NHSTUB(memcmp                                 ,0xfc382c01) // reference/finsig_gm110c/stubs_entry.S:309
NHSTUB(memcpy                                 ,0xfc13d68d) // reference/finsig_gm110c/stubs_entry.S:310
NHSTUB(memset                                 ,0xfc5591c9) // reference/finsig_gm110c/stubs_entry.S:311
NHSTUB(mktime_ext                             ,0xfc420545) // reference/finsig_gm110c/stubs_entry.S:312
NHSTUB(qsort                                  ,0xfc468519) // reference/finsig_gm110c/stubs_entry.S:317
NHSTUB(rand                                   ,0xfc42094f) // reference/finsig_gm110c/stubs_entry.S:318
NHSTUB(srand                                  ,0xfc420949) // reference/finsig_gm110c/stubs_entry.S:321
NHSTUB(strcat                                 ,0xfc381489) // reference/finsig_gm110c/stubs_entry.S:323
NHSTUB(strchr                                 ,0xfc13d721) // reference/finsig_gm110c/stubs_entry.S:324
NHSTUB(strcmp                                 ,0xfc382a2d) // reference/finsig_gm110c/stubs_entry.S:325
NHSTUB(strcpy                                 ,0xfc382a09) // reference/finsig_gm110c/stubs_entry.S:326
NHSTUB(strftime                               ,0x010e1689) // reference/finsig_gm110c/stubs_entry.S:327
NHSTUB(strlen                                 ,0xfc382aed) // reference/finsig_gm110c/stubs_entry.S:328
NHSTUB(strncmp                                ,0xfc420997) // reference/finsig_gm110c/stubs_entry.S:329
NHSTUB(strncpy                                ,0xfc381465) // reference/finsig_gm110c/stubs_entry.S:330
NHSTUB(strrchr                                ,0xfc13d733) // reference/finsig_gm110c/stubs_entry.S:331
NHSTUB(strtol                                 ,0xfc13d67f) // reference/finsig_gm110c/stubs_entry.S:332
NHSTUB(strtolx                                ,0xfc13d53d) // reference/finsig_gm110c/stubs_entry.S:333
NHSTUB(time                                   ,0x010e11e3) // reference/finsig_gm110c/stubs_entry.S:344
NHSTUB(vsprintf                               ,0xfc0dcc67) // reference/finsig_gm110c/stubs_entry.S:345
NHSTUB(EngDrvRead                             ,0xfc382b41) // reference/finsig_gm110c/stubs_entry.S:346
NHSTUB(PTM_GetCurrentItem                     ,0xfc35f5cb) // reference/finsig_gm110c/stubs_entry.S:347
NHSTUB(transfer_src_overlay                   ,0xfc380635) // reference/finsig_gm110c/stubs_entry.S:352
NHSTUB(bzero                                  ,0x01100b40) // reference/finsig_gm110c/stubs_entry.S:353
NHSTUB(memset32                               ,0x01100b44) // reference/finsig_gm110c/stubs_entry.S:354
NHSTUB(get_dial_hw_position                   ,0xfc118149) // reference/finsig_gm110c/stubs_entry.S:355
'''


def generate_module_candidate_c() -> str:
    """Generate RAM-only no-op module stubs for G3X_GUI=1 (no card module loading)."""
    return r'''/* =============================================================================
 * PORT-35 Part B: G3X_GUI=1 RAM-only module stubs
 * Replaces core/modules.c and core/module_load.c so no module is ever loaded
 * from the SD card while keeping all lib* pointers valid in RAM.
 * ============================================================================= */

static int stub_ret0(void) { return 0; }
static void stub_void(void) {}

typedef struct {
    const void *lib;
    void *h;
    unsigned int flags;
    const char *name;
} module_handler_t;

typedef struct {
    void *hdr;
    void *f1;
    void *f2;
    void *f3;
    void *f4;
    void *f5;
    void *f6;
    void *f7;
    void *f8;
    void *f9;
    void *f10;
} stub_lib_t;

static const stub_lib_t g3x_stub_lib = {
    0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
};

const stub_lib_t *libscriptapi = &g3x_stub_lib;
const stub_lib_t *libtextbox = &g3x_stub_lib;
const stub_lib_t *libgrids = &g3x_stub_lib;
const stub_lib_t *librawop = &g3x_stub_lib;
const stub_lib_t *libmotiondetect = &g3x_stub_lib;
const stub_lib_t *libcurves = &g3x_stub_lib;
const stub_lib_t *libdng = &g3x_stub_lib;
const stub_lib_t *libfselect = &g3x_stub_lib;
const stub_lib_t *libmpopup = &g3x_stub_lib;
const stub_lib_t *libtxtread = &g3x_stub_lib;
const stub_lib_t *libeyefi = &g3x_stub_lib;
const stub_lib_t *libhisto = &g3x_stub_lib;
const stub_lib_t *libshothisto = &g3x_stub_lib;
const stub_lib_t *libzebra = &g3x_stub_lib;
const stub_lib_t *libedgeovr = &g3x_stub_lib;
const stub_lib_t *libhexbox = &g3x_stub_lib;
const stub_lib_t *libpalette = &g3x_stub_lib;

int module_load(module_handler_t *hMod)
{
    if (hMod && !hMod->lib) {
        hMod->lib = &g3x_stub_lib;
    }
    return 0;
}

void module_unload(const char *name) { (void)name; }
int module_run(char *module, void *callback, int count, int *params, int unload)
{
    (void)module;
    (void)callback;
    (void)count;
    (void)params;
    (void)unload;
    return -1;
}
void module_preload(const char *path, const char *name, int flags) { (void)path; (void)name; (void)flags; }
void module_exit_alt(void) {}
void module_tick_unloader(void) {}
void module_log_clear(void) {}
void *module_get_adr(unsigned int idx) { (void)idx; return (void *)stub_void; }
int get_module_info(int idx, const char **name, int *size, unsigned int *base, int *flags)
{
    (void)idx;
    (void)name;
    (void)size;
    (void)base;
    (void)flags;
    return 0;
}
void module_restore_edge(void *buf, int state) { (void)buf; (void)state; }
void module_save_edge(const char *fn) { (void)fn; }
void module_set_script_lang(const char *fn) { (void)fn; }
'''


def generate_conf_candidate_c() -> str:
    """Generate conf.c with card writes, config file I/O, and script loading compiled out."""
    conf_path = CHDK_PORT / "core" / "conf.c"
    with open(conf_path, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. Make conf_update_prevent_shutdown a safe no-op so ALT transitions do not call unverified power-lock stubs
    target_prevent = """void conf_update_prevent_shutdown(void) {
    if(conf.alt_prevent_shutdown == ALT_PREVENT_SHUTDOWN_ALWAYS 
        || (conf.alt_prevent_shutdown == ALT_PREVENT_SHUTDOWN_ALT && !camera_info.state.gui_mode_none)
        || (conf.alt_prevent_shutdown == ALT_PREVENT_SHUTDOWN_ALT_SCRIPT && camera_info.state.state_kbd_script_run)) {
        disable_shutdown();
    } else {
        enable_shutdown();
    }
}"""
    repl_prevent = """void conf_update_prevent_shutdown(void) {
    /* No-op in G3X_GUI=1 candidate */
}"""
    if target_prevent not in src:
        raise ValueError("Target conf_update_prevent_shutdown not found in core/conf.c")
    src = src.replace(target_prevent, repl_prevent, 1)

    # 2. Remove script_load call from conf_change_param
    src = src.replace("script_load(conf.script_file);", "/* script_load compiled out */")
    src = src.replace('ptr:DEFAULT_SYMBOL_FILE', 'ptr:""')

    # 3. Truncate at config_save so save_config_file / conf_save / load_config_file / conf_restore are replaced with RAM-only versions
    marker = "void config_save(ConfInfo *ci, const char *filename, int config_base)"
    idx = src.find(marker)
    if idx < 0:
        raise ValueError("Marker config_save not found in core/conf.c")
    tail_marker = "// Find ConfInfo entry index for given ID"
    tail_idx = src.find(tail_marker)
    if tail_idx < 0:
        raise ValueError("Marker resetColors not found in core/conf.c")
    src_head = src[:idx]
    src_tail = src[tail_idx:]
    src_tail = src_tail.replace(
        "if (config_autosave)\n            conf_save();",
        "/* conf_save compiled out */",
    )

    ram_only_mid = r'''
void config_save(ConfInfo *ci, const char *filename, int config_base)
{
    (void)ci;
    (void)filename;
    (void)config_base;
}

int save_config_file(int config_base, const char *filename)
{
    (void)config_base;
    (void)filename;
    return 0;
}

void conf_save(void)
{
}

void __wrap_conf_save(void)
{
}

void config_restore(ConfInfo *ci, const char *filename, void (*info_func)(unsigned short id))
{
    (void)ci;
    (void)filename;
    (void)info_func;
}

int load_config_file(int config_base, const char *filename)
{
    (void)config_base;
    (void)filename;
    return 0;
}

void conf_restore(void)
{
    init_user_menu(USER_MENU_ITEMS);
    conf_load_defaults();
    clear_values();
    conf.menu_rbf_file[0] = '\0';
    conf.menu_symbol_rbf_file[0] = '\0';
    conf.menu_symbol_enable = 0;
    conf.alt_mode_button = KEY_PLAYBACK;
    conf.show_osd = 0;
    conf.hide_osd = 1;
    conf.splash_show = 0;
    conf.start_sound = 0;
    conf.show_alt_helper = 0;
    conf.script_startup = 0;
}

void __wrap_conf_restore(void)
{
    conf_restore();
}
'''
    return src_head + ram_only_mid + src_tail


def generate_platform_camera_gui2_h() -> str:
    """Generate candidate platform_camera.h for G3X_GUI2=1."""
    return r'''#ifndef PLATFORM_CAMERA_GUI2_H
#define PLATFORM_CAMERA_GUI2_H

#include_next "platform_camera.h"

/* DIGIC 6 Mode 12 screen resolution and buffer geometry (900x600, stride 928)
 * Evidence & sibling citations:
 * - evidence/port35_manifest.json: PORT35-ROM-BMPDDEV (sub_fc18347e case 12 @ 0xFC18352A) [ROM]
 * - chdk-port/platform/g5x/platform_camera.h:84,91-94; lib.c:162-204
 * - chdk-port/platform/g7x/lib.c:303-358 */
#undef  CAM_BITMAP_WIDTH
#undef  CAM_BITMAP_HEIGHT
#undef  CAM_SCREEN_WIDTH
#undef  CAM_SCREEN_HEIGHT
#define CAM_BITMAP_WIDTH                    928
#define CAM_BITMAP_HEIGHT                   600
#define CAM_SCREEN_WIDTH                    900
#define CAM_SCREEN_HEIGHT                   600

#endif /* PLATFORM_CAMERA_GUI2_H */
'''


def generate_gui_draw_candidate_c() -> str:
    """Generate gui_draw.c for G3X_GUI2=1 with opacity 255 for non-transparent menu colors."""
    gui_draw_path = CHDK_PORT / "core" / "gui_draw.c"
    with open(gui_draw_path, "r", encoding="utf-8") as f:
        src = f.read()

    target = """#define CALC_YUV_LUMA_OPACITY_FOR_COLOR(color,luma,opacity) \\
    { \\
        luma = ((color-1)^0xffffffff)&0xf0; \\
        opacity = (color&0xf)?255:color; \\
    }"""

    replacement = """/* PORT-36 F3: Force opacity 255 for non-transparent colors (G3X_GUI2=1)
 * Note: CALC_YUV_LUMA_OPACITY_FOR_COLOR affects only color 0xb0 (IDX_COLOR_GREY_DK_TRANS);
 * all other non-transparent colors in ply_colors[] already produce opacity 255 in stock macro.
 * INFERRED: no sibling overrides this macro (g7x/g5x/sx60hs use stock core/gui_draw.c:15-19).
 * Hardware trial observation to distinguish: background solid black/dark grey (confirms F3 fixed)
 * vs translucent background remaining (refutes F3 fix). */
#if defined(G3X_GUI2) && (G3X_GUI2 == 1)
#define CALC_YUV_LUMA_OPACITY_FOR_COLOR(color,luma,opacity) \\
    { \\
        luma = ((color-1)^0xffffffff)&0xf0; \\
        opacity = (color == COLOR_TRANSPARENT) ? 0 : 255; \\
    }
#else
#define CALC_YUV_LUMA_OPACITY_FOR_COLOR(color,luma,opacity) \\
    { \\
        luma = ((color-1)^0xffffffff)&0xf0; \\
        opacity = (color&0xf)?255:color; \\
    }
#endif"""

    if target not in src:
        raise ValueError("Target CALC_YUV_LUMA_OPACITY_FOR_COLOR not found in core/gui_draw.c")
    return src.replace(target, replacement, 1)


def ensure_bootstrap():
    """Ensure platform bootstrap has populated platform headers if missing."""
    platform_cam_h = CHDK_PORT / "platform" / "g3x" / "platform_camera.h"
    if not platform_cam_h.is_file():
        bootstrap_script = TOOLS_DIR / "bootstrap_chdk_platform.py"
        run_cmd(["python3", "-B", str(bootstrap_script)], cwd=str(REPO_ROOT))


def build_candidate_core_ladder_fix(
    ladder: bool = True,
    poweron_fix: bool = True,
    candidate_dir: str = CANDIDATE_LADDER_FIX_DIR,
    resident: bool = False,
    osd: bool = False,
    kbd: bool = False,
    osd2: bool = False,
    gui: bool = False,
    gui2: bool = False,
) -> tuple[str, str, int, int]:
    """Compile candidate core with optional LED_LADDER, G3X_POWERON_FIX, G3X_RESIDENT, G3X_OSD, G3X_KBD, G3X_OSD2, G3X_GUI, and G3X_GUI2 defines."""
    print(
        f"--- Building Candidate Core (ladder={ladder}, poweron_fix={poweron_fix}, resident={resident}, osd={osd}, kbd={kbd}, osd2={osd2}, gui={gui}, gui2={gui2}) (@ 0x003489B4) ---"
    )
    os.makedirs(candidate_dir, exist_ok=True)

    if resident:
        boot_proto_c = os.path.join(candidate_dir, "boot_prototype_resident.c")
        with open(boot_proto_c, "w", encoding="utf-8") as f:
            f.write(BOOT_PROTOTYPE_RESIDENT_C)
    elif ladder:
        boot_proto_c = os.path.join(candidate_dir, "boot_prototype_ladder.c")
        with open(boot_proto_c, "w", encoding="utf-8") as f:
            f.write(BOOT_PROTOTYPE_LADDER_C)
    else:
        boot_proto_c = str(SUB_DIR / "boot_prototype.c")
    stubs_proto_s = str(SUB_DIR / "stubs_prototype.S")
    boot_proto_o = os.path.join(candidate_dir, "boot_prototype.o")
    stubs_proto_o = os.path.join(candidate_dir, "stubs_prototype.o")
    lib_proto_a = os.path.join(candidate_dir, "libplatformsub_candidate.a")
    core_elf = os.path.join(candidate_dir, "candidate_main.elf")
    core_bin = os.path.join(candidate_dir, "candidate_main.bin")

    # 1. Compile boot_prototype.c
    base_cflags = [
        CC,
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Imodules",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-DMEMISOSIZE=(&_end-&_start)",
        "-DCAM_DIGIC=60",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_ARAM_MALLOC",
        "-DARAM_HEAP_START=0x006ce000",
        "-DARAM_HEAP_SIZE=0x00022000",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-nostdinc",
    ]
    if poweron_fix:
        base_cflags.append("-DG3X_POWERON_FIX=1")
    if ladder:
        base_cflags.append("-DLED_LADDER=1")
    if resident:
        base_cflags.append("-DG3X_RESIDENT=1")
    if osd:
        base_cflags.append("-DG3X_OSD=1")
    if kbd:
        base_cflags.append("-DG3X_KBD=1")
    if osd2:
        base_cflags.append("-DG3X_OSD2=1")
    if gui:
        base_cflags.append("-DG3X_GUI=1")
    if gui2:
        base_cflags.append("-DG3X_GUI2=1")
        cand_cam_h = os.path.join(candidate_dir, "platform_camera.h")
        with open(cand_cam_h, "w", encoding="utf-8") as f:
            f.write(generate_platform_camera_gui2_h())
        base_cflags.insert(base_cflags.index("-Iinclude"), f"-I{candidate_dir}")
    cflags = list(base_cflags) + ["-c", "-o", boot_proto_o, boot_proto_c]
    run_cmd(cflags, cwd=str(CHDK_PORT))

    # 2. Compile stubs_prototype.S
    sflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-c",
        "-o",
        stubs_proto_o,
        stubs_proto_s,
    ]
    run_cmd(sflags, cwd=str(CHDK_PORT))

    # 3. Create candidate libplatformsub archive
    if os.path.exists(lib_proto_a):
        os.remove(lib_proto_a)
    stubs_min_obj = str(SUB_DIR / "stubs_min.o")
    if osd2:
        stubs_min_osd2_o = os.path.join(candidate_dir, "stubs_min_osd2.o")
        run_cmd([OBJCOPY, "--strip-symbol=opacity_buffer", stubs_min_obj, stubs_min_osd2_o], cwd=str(CHDK_PORT))
        stubs_min_obj = stubs_min_osd2_o

    if gui:
        stubs_entry_gui_s = os.path.join(candidate_dir, "stubs_entry_gui.S")
        stubs_entry_gui_o = os.path.join(candidate_dir, "stubs_entry_gui.o")
        with open(stubs_entry_gui_s, "w", encoding="utf-8") as f:
            f.write(generate_stubs_entry_gui_s())
        run_cmd(
            [
                CC,
                "-march=armv7-r",
                "-mthumb",
                "-DTHUMB_FW",
                "-Iinclude",
                "-Icore",
                "-Iplatform/g3x",
                "-Iplatform/g3x/sub/110c",
                "-c",
                "-o",
                stubs_entry_gui_o,
                stubs_entry_gui_s,
            ],
            cwd=str(CHDK_PORT),
        )

        gui_cand_c = os.path.join(candidate_dir, "gui_candidate.c")
        gui_cand_o = os.path.join(candidate_dir, "gui_candidate.o")
        with open(gui_cand_c, "w", encoding="utf-8") as f:
            f.write(generate_gui_candidate_c())
        run_cmd(list(base_cflags) + ["-c", "-o", gui_cand_o, gui_cand_c], cwd=str(CHDK_PORT))

        mod_cand_c = os.path.join(candidate_dir, "module_candidate.c")
        mod_cand_o = os.path.join(candidate_dir, "module_candidate.o")
        with open(mod_cand_c, "w", encoding="utf-8") as f:
            f.write(generate_module_candidate_c())
        run_cmd(list(base_cflags) + ["-c", "-o", mod_cand_o, mod_cand_c], cwd=str(CHDK_PORT))

        conf_cand_c = os.path.join(candidate_dir, "conf_candidate.c")
        conf_cand_o = os.path.join(candidate_dir, "conf_candidate.o")
        with open(conf_cand_c, "w", encoding="utf-8") as f:
            f.write(generate_conf_candidate_c())
        run_cmd(list(base_cflags) + ["-c", "-o", conf_cand_o, conf_cand_c], cwd=str(CHDK_PORT))

        gui_draw_obj = str(SUB_DIR / "gui_draw.thm.o")
        camera_info_obj = str(SUB_DIR / "camera_info.thm.o")
        if gui2:
            cand_gui_draw_c = os.path.join(candidate_dir, "gui_draw_candidate.c")
            gui_draw_cand_o = os.path.join(candidate_dir, "gui_draw_candidate.o")
            with open(cand_gui_draw_c, "w", encoding="utf-8") as f:
                f.write(generate_gui_draw_candidate_c())
            run_cmd(list(base_cflags) + ["-c", "-o", gui_draw_cand_o, cand_gui_draw_c], cwd=str(CHDK_PORT))
            gui_draw_obj = gui_draw_cand_o

            camera_info_cand_o = os.path.join(candidate_dir, "camera_info_candidate.o")
            cam_cflags = list(base_cflags) + [
                "-Wno-builtin-macro-redefined",
                '-D__DATE__="Oct 24 2026"',
                '-D__TIME__="15:43:43"',
                "-c",
                "-o",
                camera_info_cand_o,
                "core/camera_info.c",
            ]
            run_cmd(cam_cflags, cwd=str(CHDK_PORT))
            camera_info_obj = camera_info_cand_o

        obj_files = [
            boot_proto_o,
            stubs_proto_o,
            stubs_min_obj,
            stubs_entry_gui_o,
            gui_cand_o,
            mod_cand_o,
            conf_cand_o,
            gui_draw_obj,
            str(SUB_DIR / "memmgmt.thm.o"),
            str(SUB_DIR / "gui.thm.o"),
            str(SUB_DIR / "kbd_process.thm.o"),
            str(SUB_DIR / "kbd_common.thm.o"),
            str(SUB_DIR / "gui_osd.thm.o"),
            str(SUB_DIR / "usb_sync.thm.o"),
            str(SUB_DIR / "shooting.thm.o"),
            camera_info_obj,
            str(SUB_DIR / "lib_thumb.thm.o"),
            str(SUB_DIR / "lang_str.thm.o"),
        ]
    else:
        obj_files = [
            boot_proto_o,
            stubs_proto_o,
            stubs_min_obj,
            str(SUB_DIR / "stubs_entry.o"),
            str(SUB_DIR / "stubs_entry_2.o"),
            str(SUB_DIR / "capt_seq.o"),
            str(SUB_DIR / "movie_rec.o"),
            str(SUB_DIR / "filewrite.o"),
            str(SUB_DIR / "main.thm.o"),
            str(SUB_DIR / "gui_draw.thm.o"),
            str(SUB_DIR / "memmgmt.thm.o"),
            str(SUB_DIR / "gui.thm.o"),
            str(SUB_DIR / "kbd_process.thm.o"),
            str(SUB_DIR / "kbd_common.thm.o"),
            str(SUB_DIR / "conf.thm.o"),
            str(SUB_DIR / "gui_osd.thm.o"),
            str(SUB_DIR / "raw.thm.o"),
            str(SUB_DIR / "usb_sync.thm.o"),
            str(SUB_DIR / "shooting.thm.o"),
            str(SUB_DIR / "camera_info.thm.o"),
            str(SUB_DIR / "remotecap.thm.o"),
            str(SUB_DIR / "lib_thumb.thm.o"),
            str(SUB_DIR / "lang_str.thm.o"),
            str(SUB_DIR / "ptp.thm.o"),
        ]
    run_cmd([AR, "cr", lib_proto_a] + obj_files, cwd=str(CHDK_PORT))

    # 4. Link candidate_main.elf
    libplatform_a = str(CHDK_PORT / "platform" / "g3x" / "libplatform.a")
    if osd2:
        libplatform_cand_a = os.path.join(candidate_dir, "libplatform_candidate.a")
        shutil.copyfile(libplatform_a, libplatform_cand_a)
        lib_osd2_o = os.path.join(candidate_dir, "lib.o")
        run_cmd([AR, "x", libplatform_cand_a, "lib.o"], cwd=candidate_dir)
        run_cmd(
            [
                OBJCOPY,
                "--weaken-symbol=vid_get_bitmap_fb",
                "--weaken-symbol=vid_get_opacity_active_buffer",
                "--weaken-symbol=vid_bitmap_refresh",
                lib_osd2_o,
            ],
            cwd=candidate_dir,
        )
        run_cmd([AR, "r", libplatform_cand_a, lib_osd2_o], cwd=candidate_dir)
        libplatform_a = libplatform_cand_a

    liblang_a = str(CHDK_PORT / "lib" / "lang" / ".o2" / "liblang.a")
    libcore_a = str(CHDK_PORT / "lib" / "core" / ".o2" / "libcore.a")
    if gui:
        liblang_cand_a = os.path.join(candidate_dir, "liblang_candidate.a")
        shutil.copyfile(liblang_a, liblang_cand_a)
        run_cmd([AR, "d", liblang_cand_a, "fileutil.o"], cwd=candidate_dir)
        liblang_a = liblang_cand_a

        libcore_cand_a = os.path.join(candidate_dir, "libcore_candidate.a")
        shutil.copyfile(libcore_a, libcore_cand_a)
        run_cmd(
            [
                AR,
                "d",
                libcore_cand_a,
                "modules.o",
                "module_load.o",
                "module_hashlist.o",
                "gui_script.o",
                "script.o",
                "gps.o",
            ],
            cwd=candidate_dir,
        )
        libcore_a = libcore_cand_a

    ld_script = "tools/link-boot.ld"
    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        f"-Wl,-T,{ld_script}",
        "-Wl,-N,-Ttext,0x3489b4",
        "-o",
        core_elf,
    ]
    if gui:
        gui_wraps = [
            "gui_kbd_process",
            "gui_draw_osd",
            "gui_alt_mode_button_enum",
            "set_usermenu_state",
            "conf_save",
            "conf_restore",
            "script_load",
            "script_start_gui",
            "save_params_values",
            "load_file",
            "load_file_to_length",
            "process_file",
            "load_int_value_file",
            "save_int_value_file",
            "play_sound",
            "camera_set_led",
            "debug_led",
            "mark_filesystem_bootable",
            "write",
            "_Write",
            "fwrite",
            "_Fwrite_Fut",
            "open",
            "_open",
            "_Open",
            "fopen",
            "_Fopen_Fut",
            "mkdir",
            "mkdir_if_not_exist",
            "_MakeDirectory_Fut",
            "remove",
            "_DeleteFile_Fut",
            "_DeleteDirectory_Fut",
            "rename",
            "_RenameFile_Fut",
            "utime",
            "stat",
            "opendir",
            "opendir_chdk",
            "readdir",
            "closedir",
            "_WriteSDCard",
            "_MakeSDCardBootable",
            "_SetFileAttributes",
            "_SetFileTimeStamp",
            "_ExecuteEventProcedure",
            "rbf_load_from_file",
            "rbf_load_symbol",
            "lang_load_from_file",
            "read",
            "_Read",
            "lseek",
            "_lseek",
            "close",
            "_close",
            "_Close",
        ]
        for sym in gui_wraps:
            ld_cmd.append(f"-Wl,--wrap={sym}")
    ld_cmd.extend(
        [
            "-Wl,--start-group",
            str(SUB_DIR / "entry.o"),
            libplatform_a,
            lib_proto_a,
            str(CHDK_PORT / "lib" / "font" / ".o2" / "libfont.a"),
            str(CHDK_PORT / "lib" / "math" / ".o2" / "libmath.a"),
            liblang_a,
            str(CHDK_PORT / "lib" / "armutil" / ".o2" / "libarmutil.a"),
            libcore_a,
            "-lgcc",
            "-Wl,--end-group",
        ]
    )
    run_cmd(ld_cmd, cwd=str(CHDK_PORT))

    # 5. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", core_elf, core_bin], cwd=str(CHDK_PORT))
    core_bin_size = os.path.getsize(core_bin)
    print(f"  [OK] candidate_main.bin generated ({core_bin_size} B)")

    # 6. Extract witness and end symbols
    proc = subprocess.run([NM, "-n", core_elf], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    witness_addr = extract_symbol_addr_from_nm(proc.stdout, "boot_witness")
    core_end_addr = extract_symbol_addr_from_nm(proc.stdout, "_end")
    heap_start = G3X_KBD_HEAP_START if kbd else G3X_RESIDENT_HEAP_START
    if resident and core_end_addr > heap_start:
        raise ValueError(
            f"Linked _end (0x{core_end_addr:08X}) overlaps resident heap start (0x{heap_start:08X})"
        )
    print(f"  [OK] boot_witness discovered at 0x{witness_addr:08X}, _end at 0x{core_end_addr:08X}")

    return core_elf, core_bin, witness_addr, core_end_addr


def build_candidate_loader_ladder_fix(
    core_elf: str,
    core_bin: str,
    witness_addr: int,
    ladder: bool = True,
    candidate_dir: str = CANDIDATE_LADDER_FIX_DIR,
) -> tuple[str, str]:
    """Build candidate loader with optional LED_LADDER define."""
    print(f"--- Building Candidate Loader (ladder={ladder}) (@ 0x00008000) ---")
    os.makedirs(candidate_dir, exist_ok=True)

    loader_elf = os.path.join(candidate_dir, "candidate_loader.elf")
    loader_bin = os.path.join(candidate_dir, "candidate_loader.bin")

    if not ladder:
        # Default loader path
        l_elf, l_bin, _, _ = build_default_loader(core_elf, core_bin, candidate_dir=candidate_dir)
        return l_elf, l_bin

    # Ladder loader path
    loader_entry_s = LADDER_ENTRY_S
    if not os.path.isfile(loader_entry_s):
        raise FileNotFoundError(f"Missing loader entry source: {loader_entry_s}")
    loader_entry_o = os.path.join(candidate_dir, "entry_ladder.o")

    run_cmd([
        CC, "-march=armv7-r", "-mthumb", "-DTHUMB_FW", "-nostdinc",
        "-c", "-o", loader_entry_o, loader_entry_s
    ], cwd=str(LOADER_DIR))

    loader_c = LADDER_LOADER_C
    if not os.path.isfile(loader_c):
        raise FileNotFoundError(f"Missing loader C source: {loader_c}")

    blobs_s = os.path.join(str(LOADER_DIR), "blobs.S")
    loader_o = os.path.join(candidate_dir, "main_ladder.o")
    blobs_o = os.path.join(candidate_dir, "blobs_candidate.o")

    cflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-I../../include",
        "-I../../core",
        "-I../../modules",
        "-I../../platform/g3x",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-I.",
        "-I../../platform/g3x/sub/110c",
        f'-DCORE_FILE="{core_bin}"',
        f"-DBOOT_WITNESS_ADDR=0x{witness_addr:08x}",
        "-DLED_LADDER=1",
        "-nostdinc",
        "-c",
        "-o",
        loader_o,
        loader_c,
    ]
    run_cmd(cflags, cwd=str(LOADER_DIR))

    run_cmd([
        CC, "-march=armv7-r", "-mthumb", "-DTHUMB_FW", "-nostdinc",
        f'-DCORE_FILE="{core_bin}"', "-c", "-o", blobs_o, blobs_s
    ], cwd=str(LOADER_DIR))

    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        "-Wl,--no-define-common,-EL,-T,../../tools/link-boot.ld",
        "-Wl,-N,-Ttext,0x8000",
        "-o",
        loader_elf,
        loader_entry_o,
        loader_o,
        blobs_o,
    ]
    run_cmd(ld_cmd, cwd=str(LOADER_DIR))
    run_cmd([OBJCOPY, "-O", "binary", loader_elf, loader_bin], cwd=str(LOADER_DIR))
    print(f"  [OK] candidate_loader.bin generated ({os.path.getsize(loader_bin)} B)")

    return loader_elf, loader_bin


def _check_not_tracked_dir(candidate_dir: str) -> None:
    """Refuse to write build outputs into tracked repository directories."""
    abs_dir = Path(candidate_dir).resolve()
    forbidden_roots = [
        (REPO_ROOT / "chdk-port").resolve(),
        (REPO_ROOT / "docs").resolve(),
        (REPO_ROOT / "tools").resolve(),
        (REPO_ROOT / "tests").resolve(),
        (REPO_ROOT / "evidence").resolve(),
        (REPO_ROOT / "firmware").resolve(),
    ]
    if abs_dir == REPO_ROOT.resolve():
        raise ValueError(f"Refusing to emit candidate outputs directly into repository root: {candidate_dir}")
    for root in forbidden_roots:
        if abs_dir == root or root in abs_dir.parents:
            raise ValueError(f"Refusing to emit candidate outputs into tracked path: {candidate_dir}")


def build_candidate(
    ladder: bool = True,
    poweron_fix: bool = True,
    out_dir: str | None = None,
    resident: bool | None = None,
    osd: bool | None = None,
    kbd: bool | None = None,
    osd2: bool | None = None,
    gui: bool | None = None,
    gui2: bool | None = None,
) -> dict:
    """Execute complete combined candidate build pipeline."""
    ensure_bootstrap()

    if gui2 is None:
        gui2 = os.environ.get("G3X_GUI2", "0") == "1"

    if gui is None:
        gui = os.environ.get("G3X_GUI", "0") == "1"

    if osd2 is None:
        osd2 = os.environ.get("G3X_OSD2", "0") == "1"

    if kbd is None:
        kbd = os.environ.get("G3X_KBD", "0") == "1"

    if osd is None:
        osd = os.environ.get("G3X_OSD", "0") == "1"

    if gui2:
        gui = True
        osd2 = True
        kbd = True
        resident = True
        poweron_fix = True
        ladder = True
    elif gui:
        osd2 = True
        kbd = True
        resident = True
        poweron_fix = True
    elif osd2:
        kbd = True
        resident = True
        poweron_fix = True
    elif kbd:
        resident = True
        poweron_fix = True
    elif osd:
        resident = True
    elif resident is None:
        resident = os.environ.get("G3X_RESIDENT", "0") == "1"

    if out_dir:
        candidate_dir = os.path.abspath(out_dir)
    elif gui2:
        candidate_dir = CANDIDATE_PORT36_GUI2_DIR
    elif gui:
        candidate_dir = CANDIDATE_PORT35_GUI_DIR
    elif osd2:
        candidate_dir = CANDIDATE_PORT35_OSD2_DIR
    elif kbd and osd:
        candidate_dir = CANDIDATE_PORT34_KBD_OSD_DIR
    elif kbd:
        candidate_dir = CANDIDATE_PORT34_KBD_DIR
    elif osd:
        candidate_dir = CANDIDATE_PORT33_OSD_DIR
    elif resident:
        candidate_dir = CANDIDATE_PORT32_RESIDENT_DIR
    elif ladder and poweron_fix:
        candidate_dir = CANDIDATE_PORT25_LADDER_FIX_DIR
    elif ladder:
        candidate_dir = CANDIDATE_PORT25_LADDER_DIR
    elif poweron_fix:
        candidate_dir = CANDIDATE_PORT25_POWERON_DIR
    else:
        candidate_dir = CANDIDATE_PORT25_DEFAULT_DIR

    _check_not_tracked_dir(candidate_dir)
    os.makedirs(candidate_dir, exist_ok=True)

    # 1. Build core
    core_elf, core_bin, witness_addr, core_end_addr = build_candidate_core_ladder_fix(
        ladder=ladder,
        poweron_fix=poweron_fix,
        candidate_dir=candidate_dir,
        resident=resident,
        osd=osd,
        kbd=kbd,
        osd2=osd2,
        gui=gui,
        gui2=gui2,
    )

    # 2. Build loader
    loader_elf, loader_bin = build_candidate_loader_ladder_fix(
        core_elf=core_elf,
        core_bin=core_bin,
        witness_addr=witness_addr,
        ladder=ladder,
        candidate_dir=candidate_dir,
    )

    # 3. Encode DISKBOOT.BIN
    diskboot_bin = encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)

    # 4. Generate inspector
    insp_m, insp_bin = generate_candidate_inspector(
        witness_addr=witness_addr,
        candidate_dir=candidate_dir,
    )

    # 5. Generate manifest
    artifacts = {
        "candidate_main.elf": core_elf,
        "candidate_main.bin": core_bin,
        "candidate_loader.elf": loader_elf,
        "candidate_loader.bin": loader_bin,
        "DISKBOOT.BIN": diskboot_bin,
        "witness_inspector_gm110c.m": insp_m,
        "witness_inspector_payload.bin": insp_bin,
    }

    heap_start_addr = G3X_KBD_HEAP_START if kbd else (G3X_RESIDENT_HEAP_START if resident else core_end_addr)
    if core_end_addr > heap_start_addr:
        raise ValueError(
            f"Linked _end (0x{core_end_addr:08X}) exceeds heap start (0x{heap_start_addr:08X})"
        )

    manifest_path = generate_manifest(
        artifacts,
        witness_addr=witness_addr,
        core_end_addr=core_end_addr,
        candidate_dir=candidate_dir,
        inspector_verified=True,
    )
    if resident:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_data["architectural_invariants"]["core_end_symbol"] = f"0x{core_end_addr:08X}"
        manifest_data["architectural_invariants"]["dryos_heap_base"] = f"0x{heap_start_addr:08X}"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    diskboot_sha256 = sha256_file(diskboot_bin)
    diskboot_size = os.path.getsize(diskboot_bin)
    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")
    print(f"DISKBOOT.BIN SHA-256: {diskboot_sha256}")
    print(f"DISKBOOT.BIN Size:    {diskboot_size} bytes")

    return {
        "candidate_dir": candidate_dir,
        "core_elf": core_elf,
        "core_bin": core_bin,
        "loader_elf": loader_elf,
        "loader_bin": loader_bin,
        "diskboot_bin": diskboot_bin,
        "manifest_path": manifest_path,
        "witness_addr": f"0x{witness_addr:08X}",
        "core_end_addr": f"0x{core_end_addr:08X}",
        "heap_start_addr": f"0x{heap_start_addr:08X}",
        "resident": resident,
        "osd": osd,
        "kbd": kbd,
        "osd2": osd2,
        "gui": gui,
        "gui2": gui2,
        "diskboot_sha256": diskboot_sha256,
        "diskboot_size": diskboot_size,
    }


def main():
    parser = argparse.ArgumentParser(
        description="PORT-25/32/33/34/35/36: Opt-in combined breadcrumb ladder + G3X_POWERON_FIX + G3X_RESIDENT + G3X_OSD + G3X_KBD + G3X_OSD2 + G3X_GUI + G3X_GUI2 builder for G3 X (GM1.10C)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help=f"Output directory for candidate artifacts (default: {CANDIDATE_LADDER_FIX_DIR})",
    )
    parser.add_argument(
        "--default",
        action="store_true",
        help="Build default control candidate (ladder=0, poweron_fix=0) to verify baseline invariance",
    )
    parser.add_argument(
        "--ladder",
        action="store_true",
        help="Build ladder-only candidate (ladder=1, poweron_fix=0)",
    )
    parser.add_argument(
        "--poweron-fix",
        action="store_true",
        help="Build poweron-fix-only candidate (ladder=0, poweron_fix=1)",
    )
    parser.add_argument(
        "--ladder-fix",
        "--combined",
        action="store_true",
        help="Build combined ladder + poweron_fix candidate (ladder=1, poweron_fix=1)",
    )
    parser.add_argument(
        "--resident",
        action="store_true",
        help="Build opt-in G3X_RESIDENT=1 heartbeat candidate (ladder=1, poweron_fix=1, resident=1)",
    )
    parser.add_argument(
        "--osd",
        action="store_true",
        help="Build opt-in G3X_OSD=1 test overlay candidate (ladder=1, poweron_fix=1, resident=1, osd=1)",
    )
    parser.add_argument(
        "--kbd",
        action="store_true",
        help="Build opt-in G3X_KBD=1 keyboard candidate (ladder=1, poweron_fix=1, resident=1, kbd=1)",
    )
    parser.add_argument(
        "--osd2",
        action="store_true",
        help="Build opt-in G3X_OSD2=1 overlay fix candidate (ladder=1, poweron_fix=1, resident=1, kbd=1, osd2=1)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Build opt-in G3X_GUI=1 CHDK core GUI/ALT menu candidate (ladder=1, poweron_fix=1, resident=1, kbd=1, osd2=1, gui=1)",
    )
    parser.add_argument(
        "--gui2",
        action="store_true",
        help="Build opt-in G3X_GUI2=1 CHDK core GUI/ALT menu candidate (ladder=1, poweron_fix=1, resident=1, kbd=1, osd2=1, gui=1, gui2=1)",
    )
    args = parser.parse_args()

    gui2 = bool(args.gui2 or os.environ.get("G3X_GUI2", "0") == "1")
    gui = bool(gui2 or args.gui or os.environ.get("G3X_GUI", "0") == "1")
    osd2 = bool(gui or args.osd2 or os.environ.get("G3X_OSD2", "0") == "1")
    kbd = bool(osd2 or args.kbd or os.environ.get("G3X_KBD", "0") == "1")
    osd = bool(args.osd or os.environ.get("G3X_OSD", "0") == "1")
    resident = bool(osd2 or kbd or osd or args.resident or os.environ.get("G3X_RESIDENT", "0") == "1")

    if args.default:
        ladder = False
        poweron_fix = False
        resident = False
        osd = False
        kbd = False
        osd2 = False
        gui = False
        gui2 = False
    elif args.ladder:
        ladder = True
        poweron_fix = False
        resident = False
        osd = False
        kbd = False
        osd2 = False
        gui = False
        gui2 = False
    elif args.poweron_fix:
        ladder = False
        poweron_fix = True
        resident = False
        osd = False
        kbd = False
        osd2 = False
        gui = False
        gui2 = False
    else:
        # Default behavior: build combined candidate (ladder=1, poweron_fix=1)
        ladder = True
        poweron_fix = True

    res = build_candidate(
        ladder=ladder,
        poweron_fix=poweron_fix,
        out_dir=args.out_dir,
        resident=resident,
        osd=osd,
        kbd=kbd,
        osd2=osd2,
        gui=gui,
        gui2=gui2,
    )

    print("\nSummary:")
    print(f"  Directory:    {res['candidate_dir']}")
    print(f"  DISKBOOT.BIN: {res['diskboot_bin']}")
    print(f"  SHA-256:      {res['diskboot_sha256']}")
    print(f"  Size:         {res['diskboot_size']} bytes")
    print(f"  boot_witness: {res['witness_addr']}")
    print(f"  _end:         {res['core_end_addr']}")
    print(f"  heap_start:   {res['heap_start_addr']}")
    print(f"  resident:     {res['resident']}")
    print(f"  osd:          {res['osd']}")
    print(f"  kbd:          {res['kbd']}")
    print(f"  osd2:         {res['osd2']}")
    print(f"  gui:          {res['gui']}")
    print(f"  gui2:         {res['gui2']}")


if __name__ == "__main__":
    main()
