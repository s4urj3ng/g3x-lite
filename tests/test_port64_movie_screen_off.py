"""Offline unit and integration tests for PORT-64 (Standalone Movie Screen-Off & Deliberate-Start Arming Candidate: G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SCREEN_OFF=1).

Verifies:
1. Integrated PORT-63 / PORT-64 research baseline, canonical manifest provenance & flag gates:
   - Confirms PORT-63 integration commit 4f8c41dbad1d75382ab33c8c8371382a165d0491 and PORT-64 research
     integration commit 4130de5ce8a513dee88cb426ed08a5d85d94b2f6 are ancestors of HEAD, while PORT-54
     (af257808...) remains excluded.
   - Validates canonical docs/port34_evidence_manifest.json and docs/port34_trusted_scopes.json via
     tools/port11c_evidence_validator.py, confirming PORT64-ROM-BACKLIGHT-CORE-WINDOW (0xFC37C3E0..0xFC37C4FF,
     288 B, SHA-256 cb1c330f2daf5163d111813d8c03e6b134994d162f099f73ebf38e03e761e0e7) and
     PORT64-ROM-DISPCON-BACKLIGHT-WINDOW (0xFC37CD20..0xFC37CE1F, 256 B, SHA-256
     cdd7b5b019f6aec27594524856ffaf3e5d5f3c7d79e851cbc8ea8034f68a045b) under SCOPE-PORT64-BACKLIGHT.
   - Verifies G3X_MOVIE_SCREEN_OFF=1 is strictly scoped to G3X_MOVIE_STANDALONE=1 and requires all
     standalone movie prerequisites while rejecting G3X_MOVIE_AUTOCONT_UI=1, GUI/menu flags,
     G3X_CONF_SAVE=1, FULL_HOOKS=1, and *-alone combinations across C preprocessor, makefile.inc, and CLI.
2. Deliberate movie-button start arming across shooting modes & confirmed-IDLE transitions:
   - Deliberate physical KEY_VIDEO starts arm continuation across all shooting-mode playrec_mode inputs
     ({2, 4, 5}), across dynamic shooting-mode transitions (2 -> 5 -> 2, 4 -> 5 -> 2, 4 -> 2), and after
     returning from Playback mode ({0, 1, 3, 6}) to confirmed IDLE in any shooting mode.
   - Arms cleanly across confirmed-IDLE transitions:
     * IDLE (0) -> press in IDLE (0) -> RECORDING (1) (released or held into RECORDING)
     * Confirmed IDLE (0) -> same-poll physical KEY_VIDEO press + RECORDING (1)
     * Confirmed IDLE (0) -> press in IDLE (0) -> transitional mr_rec_state in {2, 3, 4} -> RECORDING (1)
     * Confirmed IDLE (0) -> press in IDLE (0) -> transitional {2, 3, 4} -> IDLE (0) -> RECORDING (1)
     * Confirmed IDLE (0) -> same-poll physical KEY_VIDEO press + transitional {2, 3, 4} -> RECORDING (1)
   - Preserves held/released button rules, latch resets (200-poll age expiry across IDLE and transitional
     polls, playback reset, invalid-state reset, second physical press abort during transitional polls,
     held-past-50-polls stop), and rejects already-recording startup or unattributed/synthetic transitions
     without deliberate physical intent.
3. Bounded screen-off and restoration policy & firmware-call integration:
   - Calls TurnOffBackLight (0xFC37C449) and TurnOnBackLight (0xFC37C3EF) from mykbd_task resident-task
     context via g3x_movie_autocont_poll().
   - Engages TurnOffBackLight() once after a 100-poll (1.0 s) post-start settle in confirmed
     G3X_AUTOCONT_RECORDING (mr_rec_state == 1, mode_play == 0, physical KEY_VIDEO released).
   - Executes a bounded 3000-poll (30.0 s) periodic idempotent TurnOffBackLight() refresh capped at 120
     refreshes per clip to account for unknown Canon wake behavior without uncontrolled repeated calls.
   - Re-asserts TurnOffBackLight() once after the 100-poll settle on each continued segment while keeping
     screen_off_active latched across inter-segment transitions so early stops still restore the backlight.
   - Supports edge-triggered manual screen wake/off toggle via physical KEY_DISPLAY (0x00001000) during
     active armed recording while masking bit 12 in physw_status[0] so Canon UI does not receive levent 0x0D.
   - Guarantees a single TurnOnBackLight() restoration call on every exit/disarm/playback/non-recording/reset
     transition so the LCD is never stranded dark.
4. Regressions & profile isolation:
   - Preserves physical-button priority, cancellation, stop attribution (Reason 3 & Reason 4), continuation
     eligibility, PORT-63 50-attempt restart budget, PORT-41/52 short-press fix, and PORT-56 duration patch.
   - Produces build/port64-movie-screen-off/DISKBOOT.BIN and port64_movie_screen_off_manifest.json with zero
     GUI, ALT, modules, fonts, scripts, splash, settings-file, or CHDK/ directory dependency.
   - Preserves 100% byte identity of the default build and all existing PORT-55..63 profiles.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tests.test_port56_movie_nolimit import verify_movie_nolimit_stores
from tests.test_port59_movie_combined import (
    BASE_DEFAULT_END,
    BASE_DEFAULT_SHA256,
    BASE_DEFAULT_SIZE,
    INDIVIDUAL_PROFILES,
    PORT54_EXCLUDED_COMMIT,
    PORT55_BUILD_COMMIT,
    PORT56_BUILD_COMMIT,
    PORT57_BUILD_COMMIT,
    PORT58_BUILD_COMMIT,
    PORT59_COMBINED_END,
    PORT59_COMBINED_SHA256,
    PORT59_COMBINED_SIZE,
    parse_function_instructions,
)
from tests.test_port60_movie_restart_budget import (
    ORIGIN_MAIN_PORT59_COMMIT,
    PORT59_BUILD_COMMIT,
    PORT60_BUDGET_END,
    PORT60_BUDGET_SHA256,
    PORT60_BUDGET_SIZE,
    PORT60_BUILD_COMMIT,
    PORT60_INTERFACES_COMMIT,
)
from tests.test_port61_movie_session_cancel import (
    ORIGIN_MAIN_PORT60_COMMIT,
    PORT60_INTEGRATION_TIP,
    PORT60_VALIDATE_COMMIT,
    PORT61_BUILD_COMMIT,
    PORT61_BUILD_INTEGRATION_COMMIT,
    PORT61_CANCEL_END,
    PORT61_CANCEL_SHA256,
    PORT61_CANCEL_SIZE,
    PORT61_INTEGRATION_PARENT,
    PORT61_INTERFACE_COMMIT,
)
from tests.test_port62_movie_standalone import (
    INCOMPATIBLE_GUI_FLAGS,
    ORIGIN_MAIN_PORT61_COMMIT,
    PORT61_INTEGRATION_TIP,
    PORT61_VALIDATE_COMMIT,
    PORT62_INTEGRATION_BASELINE_COMMIT,
    PORT62_INTEGRATION_PARENT,
    PORT62_REUSE_MAP_COMMIT,
    PORT62_STANDALONE_END,
    PORT62_STANDALONE_SHA256,
    PORT62_STANDALONE_SIZE,
    PORT63_FIXES_COMMIT,
    PORT63_INTEGRATION_TESTED_COMMIT,
    ensure_build_default,
    ensure_build_port59,
    ensure_build_port60,
    ensure_build_port61,
    ensure_build_port62,
)

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
CORE_KBD_PROCESS_C = ROOT / "chdk-port/core/kbd_process.c"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
PORT62_BUILD_SCRIPT = ROOT / "scripts/build_port62_movie_standalone.py"
PORT64_BUILD_SCRIPT = ROOT / "scripts/build_port64_movie_screen_off.py"
DOC_PORT64 = ROOT / "docs/PORT64_MOVIE_SCREEN_OFF.md"
EVIDENCE_MANIFEST = ROOT / "docs/port34_evidence_manifest.json"
TRUSTED_SCOPES = ROOT / "docs/port34_trusted_scopes.json"
EVIDENCE_VALIDATOR = ROOT / "tools/port11c_evidence_validator.py"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

PORT63_INTEGRATION_READY_COMMIT = "b713294e192a2ddd587c76d2c0018ff8add8e560"
PORT63_FINAL_INTEGRATION_COMMIT = "4f8c41dbad1d75382ab33c8c8371382a165d0491"
PORT64_RESEARCH_SCOPE_FIX_COMMIT = "4833a00570a4e5eb63a03208cc53f8905f16c233"
PORT64_RESEARCH_INTEGRATION_COMMIT = "4130de5ce8a513dee88cb426ed08a5d85d94b2f6"
PORT64_IMPLEMENT_ATTEMPT1_COMMIT = "1f7ff801db64ed82c71aa2104e25bc0113a00af6"
PORT64_IMPLEMENT_PARTIAL_COMMIT = "01a9ddd1a29abca5e0dd3014cd26d9dbe3190742"

PORT64_SCREEN_OFF_SHA256 = "39802ac521470a980e16101f8f5766620ac750ee1f67c073f8d9c08738b100f5"
PORT64_SCREEN_OFF_SIZE = 127465
PORT64_SCREEN_OFF_END = "00369440"

PORT64_BACKLIGHT_CORE_WINDOW_SHA256 = "cb1c330f2daf5163d111813d8c03e6b134994d162f099f73ebf38e03e761e0e7"
PORT64_DISPCON_BACKLIGHT_WINDOW_SHA256 = "cdd7b5b019f6aec27594524856ffaf3e5d5f3c7d79e851cbc8ea8034f68a045b"

KEY_VIDEO = 18
G3X_KEY_VIDEO_BIT = 0x00000008
G3X_KEY_DISPLAY_BIT = 0x00001000
G3X_KEY_PLAYBACK_BIT = 0x00010000
G3X_KEY_POWER_BIT = 0x00020000
G3X_STARTCAUSE_POWER = 0x00080000
G3X_STARTCAUSE_PLAYBACK = 0x00100000
G3X_SHORTPRESS_MARGIN_POLLS = 200
SD_READONLY_FLAG = 0x20000000

G3X_AUTOCONT_DISARMED = 0
G3X_AUTOCONT_RECORDING = 1
G3X_AUTOCONT_WAIT_IDLE = 2
G3X_AUTOCONT_SETTLE = 3
G3X_AUTOCONT_PRESSING = 4
G3X_AUTOCONT_RELEASING = 5
G3X_AUTOCONT_WAIT_CONFIRM = 6

G3X_AUTOCONT_REASON_NONE = 0
G3X_AUTOCONT_REASON_USER_OFF = 1
G3X_AUTOCONT_REASON_PHYS_STOP = 2
G3X_AUTOCONT_REASON_PLAYBACK = 3
G3X_AUTOCONT_REASON_INVALID_STATE = 4
G3X_AUTOCONT_REASON_STOP_FAULT = 5
G3X_AUTOCONT_REASON_TIMEOUT = 6
G3X_AUTOCONT_REASON_SESSION_CANCEL = 7

G3X_AUTOCONT_MAX_STOP_POLLS = 500
G3X_AUTOCONT_SETTLE_POLLS = 50
G3X_AUTOCONT_PRESS_POLLS = 6
G3X_AUTOCONT_RELEASE_POLLS = 6
G3X_AUTOCONT_CONFIRM_POLLS = 200
G3X_AUTOCONT_START_HOLD_POLLS = 50

G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS = 100
G3X_AUTOCONT_SCREEN_REFRESH_POLLS = 3000
G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS = 120

G3X_AUTOCONT_BUDGET_STANDALONE = 50

REQUIRED_PORT64_PREREQS = [
    "G3X_MOVIE_STANDALONE",
    "G3X_MOVIE_SESSION_CANCEL",
    "G3X_MOVIE_RESTART_BUDGET",
    "G3X_MOVIE_NOLIMIT",
    "G3X_MOVIE_AUTOCONT",
    "G3X_MOVIE_STATUS",
]

_PORT64_BUILD_DONE = False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def ensure_build_port64() -> None:
    global _PORT64_BUILD_DONE
    out_dir = ROOT / "build/port64-movie-screen-off"
    bin_path = out_dir / "DISKBOOT.BIN"
    elf_path = out_dir / "stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = out_dir / "stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = out_dir / "port64_movie_screen_off_manifest.json"
    if (
        _PORT64_BUILD_DONE
        and bin_path.is_file()
        and elf_path.is_file()
        and obj_path.is_file()
        and manifest_path.is_file()
        and sha256_file(bin_path) == PORT64_SCREEN_OFF_SHA256
    ):
        return
    if not (
        bin_path.is_file()
        and elf_path.is_file()
        and obj_path.is_file()
        and manifest_path.is_file()
        and sha256_file(bin_path) == PORT64_SCREEN_OFF_SHA256
    ):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(PORT64_BUILD_SCRIPT),
                "--out-dir",
                str(out_dir),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _PORT64_BUILD_DONE = True


class _HostPort64ScreenOffHarness:
    """Compiles movie_rec.c, kbd_process.c, core_spytask standalone path, PORT-41/52 short-press + kbd wiring, and mock TurnOffBackLight/TurnOnBackLight with G3X_MOVIE_STANDALONE=1 and G3X_MOVIE_SCREEN_OFF=1."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port64_host_sm_")
        tmp = Path(self._tmpdir.name)

        for stub_hdr in (
            "camera.h",
            "conf.h",
            "action_stack.h",
            "lang.h",
            "gui.h",
            "gui_lang.h",
            "console.h",
            "usb_remote.h",
            "clock.h",
            "debug_led.h",
        ):
            (tmp / stub_hdr).write_text(f"/* stub {stub_hdr} */\n", encoding="utf-8")

        (tmp / "keyboard.h").write_text(
            f"#ifndef KEYBOARD_H\n"
            f"#define KEYBOARD_H\n"
            f"#define KEY_VIDEO {KEY_VIDEO}\n"
            f"#define KBD_REPEAT_DELAY 140\n"
            f"#define KBD_INITIAL_DELAY 300\n"
            f"long kbd_get_clicked_key(void);\n"
            f"long kbd_is_key_pressed(long key);\n"
            f"long get_tick_count(void);\n"
            f"#endif\n",
            encoding="utf-8",
        )
        (tmp / "camera_info.h").write_text(
            "#ifndef CAMERA_INFO_H\n"
            "#define CAMERA_INFO_H\n"
            "typedef struct {\n"
            "    struct {\n"
            "        int mode_play;\n"
            "        int gui_mode;\n"
            "        int gui_mode_none;\n"
            "        int gui_mode_alt;\n"
            "        int osd_title_line;\n"
            "    } state;\n"
            "} cam_info_t;\n"
            "extern cam_info_t camera_info;\n"
            "#endif\n",
            encoding="utf-8",
        )

        kbd_proc_src = CORE_KBD_PROCESS_C.read_text(encoding="utf-8")
        if "G3X_MOVIE_STANDALONE" not in kbd_proc_src:
            enter_alt_anchor = (
                "void enter_alt()\n"
                "{\n"
                "    clear_usb_power();         // Prevent previous USB remote pulse from starting script.\n"
                "    kbd_blocked = 1;\n"
                "    gui_set_alt_mode_state(ALT_MODE_ENTER);\n"
                "}\n"
                "\n"
                "void exit_alt()\n"
                "{\n"
                "    kbd_blocked = 0;\n"
                "    gui_set_alt_mode_state(ALT_MODE_LEAVE);\n"
                "}"
            )
            enter_alt_repl = (
                "void enter_alt()\n"
                "{\n"
                "#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)\n"
                "    kbd_blocked = 0;\n"
                "#else\n"
                "    clear_usb_power();         // Prevent previous USB remote pulse from starting script.\n"
                "    kbd_blocked = 1;\n"
                "    gui_set_alt_mode_state(ALT_MODE_ENTER);\n"
                "#endif\n"
                "}\n"
                "\n"
                "void exit_alt()\n"
                "{\n"
                "#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)\n"
                "    kbd_blocked = 0;\n"
                "#else\n"
                "    kbd_blocked = 0;\n"
                "    gui_set_alt_mode_state(ALT_MODE_LEAVE);\n"
                "#endif\n"
                "}"
            )
            kbd_proc_anchor = "long kbd_process()\n{\n    static int key_pressed;\n"
            kbd_proc_repl = (
                "long kbd_process()\n"
                "{\n"
                "#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)\n"
                "    kbd_blocked = 0;\n"
                "    camera_info.state.gui_mode = 0;\n"
                "    camera_info.state.gui_mode_none = 1;\n"
                "    camera_info.state.gui_mode_alt = 0;\n"
                "    return 0;\n"
                "#else\n"
                "    static int key_pressed;\n"
            )
            kbd_proc_src = kbd_proc_src.replace(enter_alt_anchor, enter_alt_repl, 1)
            kbd_proc_src = kbd_proc_src.replace(kbd_proc_anchor, kbd_proc_repl, 1)
            last_brace = kbd_proc_src.rfind("}")
            kbd_proc_src = kbd_proc_src[:last_brace] + "#endif\n}" + kbd_proc_src[last_brace + 1:]
        kbd_proc_staged = tmp / "kbd_process_standalone.c"
        kbd_proc_staged.write_text(kbd_proc_src, encoding="utf-8")

        harness_c = tmp / "harness_port64.c"
        harness_c.write_text(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "#include <string.h>\n"
            '#include "keyboard.h"\n'
            '#include "camera_info.h"\n'
            '#include "movie_status.h"\n'
            "cam_info_t camera_info = { { 0, 0, 1, 0, 1 } };\n"
            "long kbd_new_state[3]  = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "long kbd_prev_state[3] = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "long kbd_mod_state[3]  = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "long physw_status[3]   = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "unsigned int host_press_calls = 0;\n"
            "unsigned int host_release_calls = 0;\n"
            "long host_last_key_arg = 0;\n"
            "long host_tick_count = 0;\n"
            "int host_playrec_mode = 2;\n"
            "int host_backlight_hw_on = 1;\n"
            "int host_dispcon_display_active = 1;\n"
            "unsigned int host_turn_off_backlight_calls = 0;\n"
            "unsigned int host_turn_on_backlight_calls = 0;\n"
            "int host_last_backlight_call_rec_state = -1;\n"
            "int host_last_backlight_call_mode_play = -1;\n"
            "extern volatile int g3x_host_movie_state;\n"
            "void TurnOffBackLight(void) {\n"
            "    host_turn_off_backlight_calls++;\n"
            "    host_last_backlight_call_rec_state = g3x_host_movie_state;\n"
            "    host_last_backlight_call_mode_play = camera_info.state.mode_play;\n"
            "    /* ROM 0xFC37C449: idempotent on [r4, #0x10] == 1; writes [r4, #0x10] = 0 */\n"
            "    if (host_backlight_hw_on == 1) {\n"
            "        host_backlight_hw_on = 0;\n"
            "    }\n"
            "}\n"
            "void TurnOnBackLight(void) {\n"
            "    host_turn_on_backlight_calls++;\n"
            "    host_last_backlight_call_rec_state = g3x_host_movie_state;\n"
            "    host_last_backlight_call_mode_play = camera_info.state.mode_play;\n"
            "    /* ROM 0xFC37C3EF: idempotent on [r4, #0x10] == 1; checks [r4, #0x14] == 1; writes [r4, #0x10] = 1 */\n"
            "    if (host_backlight_hw_on != 1 && host_dispcon_display_active == 1) {\n"
            "        host_backlight_hw_on = 1;\n"
            "    }\n"
            "}\n"
            "long get_tick_count(void) { return host_tick_count; }\n"
            "long kbd_get_clicked_key(void) { return 0; }\n"
            "long kbd_is_key_pressed(long key) {\n"
            "    if (key == KEY_VIDEO) {\n"
            "        return ((kbd_new_state[0] & 0x00000008L) == 0L) ? 1L : 0L;\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
            "void kbd_key_press(long key) {\n"
            "    host_press_calls++;\n"
            "    host_last_key_arg = key;\n"
            "    if (key == KEY_VIDEO) {\n"
            "        kbd_mod_state[0] &= ~0x00000008L;\n"
            "    }\n"
            "}\n"
            "void kbd_key_release(long key) {\n"
            "    host_release_calls++;\n"
            "    host_last_key_arg = key;\n"
            "    if (key == KEY_VIDEO) {\n"
            "        kbd_mod_state[0] |= 0x00000008L;\n"
            "    }\n"
            "}\n"
            "int rec_mode_active(void) {\n"
            "    return (host_playrec_mode == 2 || host_playrec_mode == 4 || host_playrec_mode == 5);\n"
            "}\n"
            f'#include "{kbd_proc_staged}"\n'
            f'#include "{MOVIE_REC_C}"\n'
            "void host_spytask_init_and_tick(void) {\n"
            "    camera_info.state.osd_title_line = 1;\n"
            "    camera_info.state.gui_mode = 0;\n"
            "    camera_info.state.gui_mode_none = 1;\n"
            "    camera_info.state.gui_mode_alt = 0;\n"
            "    camera_info.state.mode_play = rec_mode_active() ? 0 : 1;\n"
            "}\n"
            "#define G3X_STARTCAUSE_POWER        0x00080000U\n"
            "#define G3X_STARTCAUSE_PLAYBACK     0x00100000U\n"
            "#define G3X_KEY_POWER_BIT           0x00020000U\n"
            "#define G3X_KEY_PLAYBACK_BIT        0x00010000U\n"
            "#define G3X_SHORTPRESS_MARGIN_POLLS 200\n"
            "#define KEYS_MASK0                  0x000533F9L\n"
            "#define SD_READONLY_FLAG            0x20000000L\n"
            "volatile unsigned int host_startcause_mem = 0U;\n"
            "volatile unsigned int g3x_full_saved_start_cause = 0U;\n"
            "volatile int g3x_full_shortpress_active = 0;\n"
            "volatile int g3x_full_shortpress_margin_polls = 0;\n"
            "volatile unsigned int g3x_full_selected_button_bit = 0U;\n"
            "int physw0_override = -1;\n"
            "void g3x_full_shortpress_boot_entry_hook(void) {\n"
            "    g3x_full_saved_start_cause = host_startcause_mem;\n"
            "    if (g3x_full_saved_start_cause & G3X_STARTCAUSE_PLAYBACK) {\n"
            "        g3x_full_selected_button_bit = G3X_KEY_PLAYBACK_BIT;\n"
            "    } else {\n"
            "        g3x_full_saved_start_cause = G3X_STARTCAUSE_POWER;\n"
            "        g3x_full_selected_button_bit = G3X_KEY_POWER_BIT;\n"
            "    }\n"
            "    g3x_full_shortpress_active = 1;\n"
            "    g3x_full_shortpress_margin_polls = G3X_SHORTPRESS_MARGIN_POLLS;\n"
            "}\n"
            "void g3x_full_shortpress_post_bss_hook(void) {\n"
            "    host_startcause_mem = g3x_full_saved_start_cause;\n"
            "    physw_status[0] &= ~((long)g3x_full_selected_button_bit);\n"
            "}\n"
            "long kbd_update_key_state(void) {\n"
            "    kbd_prev_state[0] = kbd_new_state[0];\n"
            "    kbd_prev_state[1] = kbd_new_state[1];\n"
            "    kbd_prev_state[2] = kbd_new_state[2];\n"
            "    long status = kbd_process();\n"
            "    if (status == 0) {\n"
            "        physw_status[0] = kbd_new_state[0];\n"
            "        physw_status[1] = kbd_new_state[1];\n"
            "        physw_status[2] = kbd_new_state[2];\n"
            "    } else {\n"
            "        physw_status[0] = (kbd_new_state[0] & (~KEYS_MASK0)) | (kbd_mod_state[0] & KEYS_MASK0);\n"
            "        physw_status[1] = kbd_new_state[1];\n"
            "        physw_status[2] = kbd_new_state[2];\n"
            "    }\n"
            "    return status;\n"
            "}\n"
            "void kbd_update_physw_bits(void) {\n"
            "    physw_status[1] = physw_status[1] & ~SD_READONLY_FLAG;\n"
            "}\n"
            "void my_kbd_read_keys(void) {\n"
            "    if (kbd_update_key_state())\n"
            "        physw0_override = physw_status[0];\n"
            "    else\n"
            "        physw0_override = -1;\n"
            "    kbd_update_physw_bits();\n"
            "    g3x_movie_nolimit_poll();\n"
            "    g3x_movie_autocont_poll();\n"
            "    if (g3x_full_shortpress_active) {\n"
            "        if (g3x_full_shortpress_margin_polls > 0) {\n"
            "            g3x_full_shortpress_margin_polls--;\n"
            "            physw_status[0] &= ~((long)g3x_full_selected_button_bit);\n"
            "            host_startcause_mem = g3x_full_saved_start_cause;\n"
            "        } else {\n"
            "            g3x_full_shortpress_active = 0;\n"
            "        }\n"
            "    }\n"
            "}\n"
            "void host_set_mode_play(int play) {\n"
            "    camera_info.state.mode_play = play;\n"
            "    host_playrec_mode = play ? 1 : 2;\n"
            "}\n"
            "void host_force_state_for_invariant_test(\n"
            "    int state,\n"
            "    unsigned int budget,\n"
            "    unsigned int remaining,\n"
            "    unsigned int used,\n"
            "    int admitted,\n"
            "    int synth_owned_val,\n"
            "    int cancelled_val)\n"
            "{\n"
            "    g3x_autocont_state = state;\n"
            "    g3x_autocont_restart_budget = budget;\n"
            "    g3x_autocont_restarts_remaining = remaining;\n"
            "    g3x_autocont_session_restarts_used = used;\n"
            "    g3x_autocont_attempt_admitted = admitted;\n"
            "    g3x_autocont_synth_owned = synth_owned_val;\n"
            "    g3x_autocont_session_cancelled = cancelled_val;\n"
            "}\n"
            "void host_set_timer_polls_for_test(unsigned int polls)\n"
            "{\n"
            "    g3x_autocont_timer_polls = polls;\n"
            "}\n"
            "void host_call_enter_confirmed_recording_for_test(void)\n"
            "{\n"
            "    g3x_autocont_enter_confirmed_recording();\n"
            "}\n",
            encoding="utf-8",
        )

        so_path = tmp / "libport64_movie_screen_off.so"
        subprocess.run(
            [
                "gcc",
                "-shared",
                "-fPIC",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Wno-unused-function",
                "-DG3X_MOVIE_STANDALONE=1",
                "-DG3X_MOVIE_SCREEN_OFF=1",
                "-DG3X_MOVIE_STATUS=1",
                "-DG3X_MOVIE_NOLIMIT=1",
                "-DG3X_MOVIE_AUTOCONT=1",
                "-DG3X_MOVIE_RESTART_BUDGET=1",
                "-DG3X_MOVIE_SESSION_CANCEL=1",
                f"-I{tmp}",
                f"-I{ROOT / 'chdk-port/platform/g3x'}",
                str(harness_c),
                "-o",
                str(so_path),
            ],
            check=True,
        )
        self.lib = ctypes.CDLL(str(so_path))

        self.lib.g3x_movie_nolimit_poll.argtypes = []
        self.lib.g3x_movie_nolimit_poll.restype = None
        self.lib.g3x_movie_autocont_poll.argtypes = []
        self.lib.g3x_movie_autocont_poll.restype = None
        self.lib.g3x_movie_autocont_reset.argtypes = []
        self.lib.g3x_movie_autocont_reset.restype = None
        self.lib.g3x_movie_autocont_is_enabled.argtypes = []
        self.lib.g3x_movie_autocont_is_enabled.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_can_enable.argtypes = []
        self.lib.g3x_movie_autocont_can_enable.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_set_enabled.argtypes = [ctypes.c_int]
        self.lib.g3x_movie_autocont_set_enabled.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_disarm_reason.argtypes = []
        self.lib.g3x_movie_autocont_get_disarm_reason.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_is_faulted.argtypes = []
        self.lib.g3x_movie_autocont_is_faulted.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_reason_str.argtypes = []
        self.lib.g3x_movie_autocont_reason_str.restype = ctypes.c_char_p
        self.lib.g3x_movie_autocont_ui_status_str.argtypes = []
        self.lib.g3x_movie_autocont_ui_status_str.restype = ctypes.c_char_p
        self.lib.g3x_movie_autocont_menu_str.argtypes = []
        self.lib.g3x_movie_autocont_menu_str.restype = ctypes.c_char_p
        self.lib.g3x_movie_autocont_get_state.argtypes = []
        self.lib.g3x_movie_autocont_get_state.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_timer_polls.argtypes = []
        self.lib.g3x_movie_autocont_get_timer_polls.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_is_synth_owned.argtypes = []
        self.lib.g3x_movie_autocont_is_synth_owned.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_is_cancel_latched.argtypes = []
        self.lib.g3x_movie_autocont_is_cancel_latched.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_last_stop_reason.argtypes = []
        self.lib.g3x_movie_autocont_get_last_stop_reason.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_get_restart_count.argtypes = []
        self.lib.g3x_movie_autocont_get_restart_count.restype = ctypes.c_uint

        self.lib.g3x_movie_autocont_get_restart_budget.argtypes = []
        self.lib.g3x_movie_autocont_get_restart_budget.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_set_restart_budget.argtypes = [ctypes.c_uint]
        self.lib.g3x_movie_autocont_set_restart_budget.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_restarts_remaining.argtypes = []
        self.lib.g3x_movie_autocont_get_restarts_remaining.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_get_session_restarts_used.argtypes = []
        self.lib.g3x_movie_autocont_get_session_restarts_used.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_is_attempt_admitted.argtypes = []
        self.lib.g3x_movie_autocont_is_attempt_admitted.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_budget_menu_str.argtypes = []
        self.lib.g3x_movie_autocont_budget_menu_str.restype = ctypes.c_char_p
        self.lib.g3x_movie_autocont_budget_menu_change.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.g3x_movie_autocont_budget_menu_change.restype = ctypes.c_char_p

        self.lib.g3x_movie_autocont_can_cancel_session.argtypes = []
        self.lib.g3x_movie_autocont_can_cancel_session.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_cancel_session.argtypes = []
        self.lib.g3x_movie_autocont_cancel_session.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_is_session_cancelled.argtypes = []
        self.lib.g3x_movie_autocont_is_session_cancelled.restype = ctypes.c_int

        self.lib.g3x_movie_autocont_is_screen_off_active.argtypes = []
        self.lib.g3x_movie_autocont_is_screen_off_active.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_screen_off_delay_polls.argtypes = []
        self.lib.g3x_movie_autocont_get_screen_off_delay_polls.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_get_screen_refresh_polls.argtypes = []
        self.lib.g3x_movie_autocont_get_screen_refresh_polls.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_get_backlight_off_count.argtypes = []
        self.lib.g3x_movie_autocont_get_backlight_off_count.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_get_backlight_on_count.argtypes = []
        self.lib.g3x_movie_autocont_get_backlight_on_count.restype = ctypes.c_uint
        self.lib.g3x_movie_autocont_is_confirmed_idle_ready.argtypes = []
        self.lib.g3x_movie_autocont_is_confirmed_idle_ready.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_is_idle_start_press_seen.argtypes = []
        self.lib.g3x_movie_autocont_is_idle_start_press_seen.restype = ctypes.c_int
        self.lib.g3x_movie_autocont_get_idle_press_age.argtypes = []
        self.lib.g3x_movie_autocont_get_idle_press_age.restype = ctypes.c_uint

        self.lib.kbd_process.argtypes = []
        self.lib.kbd_process.restype = ctypes.c_long
        self.lib.kbd_is_blocked.argtypes = []
        self.lib.kbd_is_blocked.restype = ctypes.c_int
        self.lib.enter_alt.argtypes = []
        self.lib.enter_alt.restype = None
        self.lib.exit_alt.argtypes = []
        self.lib.exit_alt.restype = None
        self.lib.my_kbd_read_keys.argtypes = []
        self.lib.my_kbd_read_keys.restype = None
        self.lib.g3x_full_shortpress_boot_entry_hook.argtypes = []
        self.lib.g3x_full_shortpress_boot_entry_hook.restype = None
        self.lib.g3x_full_shortpress_post_bss_hook.argtypes = []
        self.lib.g3x_full_shortpress_post_bss_hook.restype = None
        self.lib.host_spytask_init_and_tick.argtypes = []
        self.lib.host_spytask_init_and_tick.restype = None
        self.lib.host_set_mode_play.argtypes = [ctypes.c_int]
        self.lib.host_set_mode_play.restype = None
        self.lib.host_force_state_for_invariant_test.argtypes = [
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.lib.host_force_state_for_invariant_test.restype = None
        self.lib.host_set_timer_polls_for_test.argtypes = [ctypes.c_uint]
        self.lib.host_set_timer_polls_for_test.restype = None
        self.lib.host_call_enter_confirmed_recording_for_test.argtypes = []
        self.lib.host_call_enter_confirmed_recording_for_test.restype = None

        self.movie_state = ctypes.c_int.in_dll(self.lib, "g3x_host_movie_state")
        self.max_frames = ctypes.c_uint.in_dll(self.lib, "g3x_host_movie_max_frames")
        self.cur_frames = ctypes.c_uint.in_dll(self.lib, "g3x_host_movie_cur_frames")
        self.stop_reason = ctypes.c_uint.in_dll(self.lib, "g3x_host_movie_stop_reason")
        self.segment_index = ctypes.c_uint.in_dll(self.lib, "g3x_host_movie_segment_index")
        self.fs_reserve_size = ctypes.c_uint.in_dll(self.lib, "g3x_host_movie_fs_reserve_size")
        self.avail_space = ctypes.c_ulonglong.in_dll(self.lib, "g3x_host_movie_avail_space")
        self.stream_bytes = ctypes.c_ulonglong.in_dll(self.lib, "g3x_host_movie_stream_bytes")
        self.projected_size = ctypes.c_ulonglong.in_dll(self.lib, "g3x_host_movie_projected_size")
        self.projected_base_offset = ctypes.c_ulonglong.in_dll(self.lib, "g3x_host_movie_projected_base_offset")

        self.kbd_new_state = (ctypes.c_long * 3).in_dll(self.lib, "kbd_new_state")
        self.kbd_prev_state = (ctypes.c_long * 3).in_dll(self.lib, "kbd_prev_state")
        self.kbd_mod_state = (ctypes.c_long * 3).in_dll(self.lib, "kbd_mod_state")
        self.physw_status = (ctypes.c_long * 3).in_dll(self.lib, "physw_status")
        self.press_calls = ctypes.c_uint.in_dll(self.lib, "host_press_calls")
        self.release_calls = ctypes.c_uint.in_dll(self.lib, "host_release_calls")
        self.last_key_arg = ctypes.c_long.in_dll(self.lib, "host_last_key_arg")
        self.playrec_mode = ctypes.c_int.in_dll(self.lib, "host_playrec_mode")
        self.kbd_blocked = ctypes.c_int.in_dll(self.lib, "kbd_blocked")
        self.physw0_override = ctypes.c_int.in_dll(self.lib, "physw0_override")

        self.backlight_hw_on = ctypes.c_int.in_dll(self.lib, "host_backlight_hw_on")
        self.dispcon_display_active = ctypes.c_int.in_dll(self.lib, "host_dispcon_display_active")
        self.turn_off_backlight_calls = ctypes.c_uint.in_dll(self.lib, "host_turn_off_backlight_calls")
        self.turn_on_backlight_calls = ctypes.c_uint.in_dll(self.lib, "host_turn_on_backlight_calls")
        self.last_backlight_call_rec_state = ctypes.c_int.in_dll(self.lib, "host_last_backlight_call_rec_state")
        self.last_backlight_call_mode_play = ctypes.c_int.in_dll(self.lib, "host_last_backlight_call_mode_play")

        self.startcause_mem = ctypes.c_uint.in_dll(self.lib, "host_startcause_mem")
        self.saved_start_cause = ctypes.c_uint.in_dll(self.lib, "g3x_full_saved_start_cause")
        self.shortpress_active = ctypes.c_int.in_dll(self.lib, "g3x_full_shortpress_active")
        self.shortpress_margin_polls = ctypes.c_int.in_dll(self.lib, "g3x_full_shortpress_margin_polls")
        self.selected_button_bit = ctypes.c_uint.in_dll(self.lib, "g3x_full_selected_button_bit")

        self.reset()

    def close(self) -> None:
        self._tmpdir.cleanup()

    def reset(self) -> None:
        self.movie_state.value = 0
        self.max_frames.value = 54000
        self.cur_frames.value = 0
        self.stop_reason.value = 0
        self.segment_index.value = 1
        self.fs_reserve_size.value = 0
        self.avail_space.value = 32 * 1024 * 1024 * 1024
        self.stream_bytes.value = 0
        self.projected_size.value = 0
        self.projected_base_offset.value = 0
        for i in range(3):
            self.kbd_new_state[i] = 0xFFFFFFFF
            self.kbd_prev_state[i] = 0xFFFFFFFF
            self.kbd_mod_state[i] = 0xFFFFFFFF
            self.physw_status[i] = 0xFFFFFFFF
        self.press_calls.value = 0
        self.release_calls.value = 0
        self.last_key_arg.value = 0
        self.playrec_mode.value = 2
        self.kbd_blocked.value = 0
        self.physw0_override.value = -1
        self.backlight_hw_on.value = 1
        self.dispcon_display_active.value = 1
        self.turn_off_backlight_calls.value = 0
        self.turn_on_backlight_calls.value = 0
        self.last_backlight_call_rec_state.value = -1
        self.last_backlight_call_mode_play.value = -1
        self.startcause_mem.value = G3X_STARTCAUSE_POWER
        self.saved_start_cause.value = 0
        self.shortpress_active.value = 0
        self.shortpress_margin_polls.value = 0
        self.selected_button_bit.value = 0
        self.lib.host_set_mode_play(0)
        self.lib.host_spytask_init_and_tick()
        self.lib.g3x_movie_autocont_reset()

    def set_physical_video_button(self, pressed: bool) -> None:
        if pressed:
            self.kbd_new_state[0] &= ~G3X_KEY_VIDEO_BIT
        else:
            self.kbd_new_state[0] |= G3X_KEY_VIDEO_BIT

    def set_physical_display_button(self, pressed: bool) -> None:
        if pressed:
            self.kbd_new_state[0] &= ~G3X_KEY_DISPLAY_BIT
        else:
            self.kbd_new_state[0] |= G3X_KEY_DISPLAY_BIT

    def step(self, run_nolimit: bool = True) -> int:
        if run_nolimit:
            self.lib.my_kbd_read_keys()
        else:
            self.lib.kbd_update_key_state()
            self.lib.kbd_update_physw_bits()
            self.lib.g3x_movie_autocont_poll()
        return self.state

    @property
    def state(self) -> int:
        return self.lib.g3x_movie_autocont_get_state()

    @property
    def enabled(self) -> int:
        return self.lib.g3x_movie_autocont_is_enabled()

    @property
    def can_enable(self) -> int:
        return self.lib.g3x_movie_autocont_can_enable()

    @property
    def can_cancel_session(self) -> int:
        return self.lib.g3x_movie_autocont_can_cancel_session()

    @property
    def session_cancelled(self) -> int:
        return self.lib.g3x_movie_autocont_is_session_cancelled()

    @property
    def disarm_reason(self) -> int:
        return self.lib.g3x_movie_autocont_get_disarm_reason()

    @property
    def is_faulted(self) -> int:
        return self.lib.g3x_movie_autocont_is_faulted()

    @property
    def reason_str(self) -> str:
        s = self.lib.g3x_movie_autocont_reason_str()
        return s.decode("utf-8") if s else ""

    @property
    def ui_status_str(self) -> str:
        s = self.lib.g3x_movie_autocont_ui_status_str()
        return s.decode("utf-8") if s else ""

    @property
    def menu_str(self) -> str:
        s = self.lib.g3x_movie_autocont_menu_str()
        return s.decode("utf-8") if s else ""

    @property
    def restart_budget(self) -> int:
        return self.lib.g3x_movie_autocont_get_restart_budget()

    @property
    def restarts_remaining(self) -> int:
        return self.lib.g3x_movie_autocont_get_restarts_remaining()

    @property
    def session_restarts_used(self) -> int:
        return self.lib.g3x_movie_autocont_get_session_restarts_used()

    @property
    def attempt_admitted(self) -> int:
        return self.lib.g3x_movie_autocont_is_attempt_admitted()

    @property
    def timer_polls(self) -> int:
        return self.lib.g3x_movie_autocont_get_timer_polls()

    @property
    def synth_owned(self) -> int:
        return self.lib.g3x_movie_autocont_is_synth_owned()

    @property
    def cancel_latched(self) -> int:
        return self.lib.g3x_movie_autocont_is_cancel_latched()

    @property
    def last_stop_reason(self) -> int:
        return self.lib.g3x_movie_autocont_get_last_stop_reason()

    @property
    def restart_count(self) -> int:
        return self.lib.g3x_movie_autocont_get_restart_count()

    @property
    def screen_off_active(self) -> int:
        return self.lib.g3x_movie_autocont_is_screen_off_active()

    @property
    def screen_off_delay_polls(self) -> int:
        return self.lib.g3x_movie_autocont_get_screen_off_delay_polls()

    @property
    def screen_refresh_polls(self) -> int:
        return self.lib.g3x_movie_autocont_get_screen_refresh_polls()

    @property
    def backlight_off_count(self) -> int:
        return self.lib.g3x_movie_autocont_get_backlight_off_count()

    @property
    def backlight_on_count(self) -> int:
        return self.lib.g3x_movie_autocont_get_backlight_on_count()

    @property
    def confirmed_idle_ready(self) -> int:
        return self.lib.g3x_movie_autocont_is_confirmed_idle_ready()

    @property
    def idle_start_press_seen(self) -> int:
        return self.lib.g3x_movie_autocont_is_idle_start_press_seen()

    @property
    def idle_press_age(self) -> int:
        return self.lib.g3x_movie_autocont_get_idle_press_age()

    @property
    def physw_video_pressed(self) -> bool:
        return (self.physw_status[0] & G3X_KEY_VIDEO_BIT) == 0

    @property
    def mod_video_pressed(self) -> bool:
        return (self.kbd_mod_state[0] & G3X_KEY_VIDEO_BIT) == 0

    @property
    def physw_display_pressed(self) -> bool:
        return (self.physw_status[0] & G3X_KEY_DISPLAY_BIT) == 0


class TestPort64BaselineManifestAndFlagGates(unittest.TestCase):
    def test_port63_and_port64_research_baseline_in_head_and_canonical_manifest_validation(self) -> None:
        for ancestor_commit in (
            ORIGIN_MAIN_PORT61_COMMIT,
            PORT61_INTEGRATION_TIP,
            PORT61_VALIDATE_COMMIT,
            PORT61_BUILD_INTEGRATION_COMMIT,
            PORT61_BUILD_COMMIT,
            PORT61_INTEGRATION_PARENT,
            PORT61_INTERFACE_COMMIT,
            ORIGIN_MAIN_PORT60_COMMIT,
            PORT60_INTEGRATION_TIP,
            PORT60_VALIDATE_COMMIT,
            PORT60_BUILD_COMMIT,
            PORT60_INTERFACES_COMMIT,
            ORIGIN_MAIN_PORT59_COMMIT,
            PORT59_BUILD_COMMIT,
            PORT58_BUILD_COMMIT,
            PORT57_BUILD_COMMIT,
            PORT56_BUILD_COMMIT,
            PORT55_BUILD_COMMIT,
            PORT62_REUSE_MAP_COMMIT,
            PORT62_INTEGRATION_PARENT,
            PORT62_INTEGRATION_BASELINE_COMMIT,
            PORT63_FIXES_COMMIT,
            PORT63_INTEGRATION_TESTED_COMMIT,
            PORT63_INTEGRATION_READY_COMMIT,
            PORT63_FINAL_INTEGRATION_COMMIT,
            PORT64_RESEARCH_SCOPE_FIX_COMMIT,
            PORT64_RESEARCH_INTEGRATION_COMMIT,
        ):
            res = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor_commit, "HEAD"],
                cwd=str(ROOT),
            )
            self.assertEqual(res.returncode, 0, f"Expected {ancestor_commit} to be an ancestor of HEAD")

        self.assertFalse(
            (ROOT / "tests/test_port54_conf_save.py").exists(),
            "PORT-54 (G3X_CONF_SAVE=1) must remain excluded from delivered sources",
        )

        # Validate canonical evidence manifest and trusted scopes via port11c_evidence_validator.py
        res = subprocess.run(
            [
                sys.executable,
                "-B",
                str(EVIDENCE_VALIDATOR),
                "--manifest",
                str(EVIDENCE_MANIFEST),
                "--trusted-scopes",
                str(TRUSTED_SCOPES),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("VALID (0 errors, 0 warnings)", res.stdout)

        manifest_json = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
        entries_by_id = {e["evidence_id"]: e for e in manifest_json["evidence_entries"]}
        self.assertIn("PORT64-ROM-BACKLIGHT-CORE-WINDOW", entries_by_id)
        self.assertIn("PORT64-ROM-DISPCON-BACKLIGHT-WINDOW", entries_by_id)
        core_win = entries_by_id["PORT64-ROM-BACKLIGHT-CORE-WINDOW"]
        disp_win = entries_by_id["PORT64-ROM-DISPCON-BACKLIGHT-WINDOW"]
        self.assertEqual(core_win["start_address"], "0xFC37C3E0")
        self.assertEqual(core_win["end_address"], "0xFC37C4FF")
        self.assertEqual(core_win["expected_byte_count"], 288)
        self.assertEqual(core_win["sha256"], PORT64_BACKLIGHT_CORE_WINDOW_SHA256)
        self.assertEqual(disp_win["start_address"], "0xFC37CD20")
        self.assertEqual(disp_win["end_address"], "0xFC37CE1F")
        self.assertEqual(disp_win["expected_byte_count"], 256)
        self.assertEqual(disp_win["sha256"], PORT64_DISPCON_BACKLIGHT_WINDOW_SHA256)

    def test_port64_profile_requires_movie_standalone_and_rejects_missing_prerequisites_or_incompatible_flags(self) -> None:
        expected_err = (
            "G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 "
            "G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 "
            "G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1"
        )
        with tempfile.TemporaryDirectory(prefix="port64_pp_") as tmpdir:
            tmp = Path(tmpdir)
            for hdr in ("conf.h", "keyboard.h", "camera_info.h"):
                (tmp / hdr).write_text(f"/* stub {hdr} */\n", encoding="utf-8")

            full_c_flags = ["-DG3X_MOVIE_SCREEN_OFF=1"] + [f"-D{f}=1" for f in REQUIRED_PORT64_PREREQS]
            res = subprocess.run(
                [
                    "cc",
                    "-E",
                    *full_c_flags,
                    "-I",
                    str(tmp),
                    "-I",
                    str(MOVIE_STATUS_H.parent),
                    "-x",
                    "c",
                    str(MOVIE_REC_C),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

            for missing in REQUIRED_PORT64_PREREQS:
                with self.subTest(missing=missing):
                    c_flags = ["-DG3X_MOVIE_SCREEN_OFF=1"] + [
                        f"-D{f}=1" for f in REQUIRED_PORT64_PREREQS if f != missing
                    ]
                    res = subprocess.run(
                        [
                            "cc",
                            "-E",
                            *c_flags,
                            "-I",
                            str(tmp),
                            "-I",
                            str(MOVIE_STATUS_H.parent),
                            "-x",
                            "c",
                            str(MOVIE_REC_C),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

                    make_args = ["G3X_MOVIE_SCREEN_OFF=1"] + [
                        f"{f}=1" for f in REQUIRED_PORT64_PREREQS if f != missing
                    ]
                    res = subprocess.run(
                        ["make", "-f", str(SUB_MAKEFILE_INC), *make_args],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

            full_make_args = ["G3X_MOVIE_SCREEN_OFF=1"] + [f"{f}=1" for f in REQUIRED_PORT64_PREREQS]
            incompat_cases = [
                ("G3X_MOVIE_AUTOCONT_UI", "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
                ("G3X_CONF_SAVE", "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1"),
                ("FULL_HOOKS", "is incompatible with FULL_HOOKS=1"),
            ] + [(gui_flag, "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags") for gui_flag in INCOMPATIBLE_GUI_FLAGS]

            for bad_flag, expected_msg in incompat_cases:
                with self.subTest(bad_flag=bad_flag):
                    res = subprocess.run(
                        [
                            "cc",
                            "-E",
                            *full_c_flags,
                            f"-D{bad_flag}=1",
                            "-I",
                            str(tmp),
                            "-I",
                            str(MOVIE_STATUS_H.parent),
                            "-x",
                            "c",
                            str(MOVIE_REC_C),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_msg, res.stderr)

                    res = subprocess.run(
                        ["make", "-f", str(SUB_MAKEFILE_INC), *full_make_args, f"{bad_flag}=1"],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_msg, res.stderr)

        base_cli = [sys.executable, "-B", str(PORT64_BUILD_SCRIPT)]
        for bad_cli, exp_err in (
            (["--without-movie-standalone"], "G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1"),
            (["--conf-save"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-autocont-ui"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-combined"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-budget-profile"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-cancel-profile"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--gui-menu"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--gui-sync"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--shadow2"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--gui-diag"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--kbd-check"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--no-overdraw"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--gui-restore2"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--playback-menu"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--playback-menu-alone"], "G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags"),
            (["--movie-nolimit-alone"], "G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1"),
            (["--movie-autocont-alone"], "G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1"),
            (["--movie-status-alone"], "G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1"),
        ):
            with self.subTest(bad_cli=bad_cli):
                res = subprocess.run([*base_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(exp_err, res.stderr)


class TestPort64DeliberateStartArmingAndScreenOffPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort64ScreenOffHarness()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sm.close()

    def setUp(self) -> None:
        self.sm.reset()

    def _start_deliberate_physical_recording(
        self,
        *,
        playrec_mode: int = 2,
        transitional_states: tuple[int, ...] = (),
        same_poll_start: bool = False,
        same_poll_transitional: bool = False,
        hold_across_transitional: bool = False,
        hold_polls_into_rec: int = 0,
        budget: int | None = None,
        run_nolimit: bool = True,
        initial_counters_zero: bool = False,
    ) -> None:
        self.sm.playrec_mode.value = playrec_mode
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.confirmed_idle_ready, 1)

        if budget is not None and self.sm.restart_budget != budget:
            self.sm.lib.host_force_state_for_invariant_test(
                self.sm.state,
                budget,
                0,
                0,
                0,
                0,
                self.sm.session_cancelled,
            )
            self.assertEqual(self.sm.restart_budget, budget)
        expected_budget = self.sm.restart_budget

        if same_poll_start and not transitional_states:
            # Same-poll IDLE (0) -> RECORDING (1) physical press
            self.sm.set_physical_video_button(True)
        elif same_poll_transitional and transitional_states:
            # Same-poll IDLE (0) -> transitional {2, 3, 4} physical press
            self.sm.set_physical_video_button(True)
            self.sm.movie_state.value = transitional_states[0]
            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.idle_start_press_seen, 1)
            if not hold_across_transitional and hold_polls_into_rec == 0:
                self.sm.set_physical_video_button(False)
            for t_state in transitional_states[1:]:
                self.sm.movie_state.value = t_state
                self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 1)
            if hold_across_transitional and hold_polls_into_rec == 0:
                self.sm.set_physical_video_button(False)
        else:
            # Physical press observed in confirmed IDLE (0)
            self.sm.set_physical_video_button(True)
            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.idle_start_press_seen, 1)
            if not hold_across_transitional and hold_polls_into_rec == 0:
                self.sm.set_physical_video_button(False)
            for t_state in transitional_states:
                self.sm.movie_state.value = t_state
                self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 1)
            if hold_across_transitional and hold_polls_into_rec == 0:
                self.sm.set_physical_video_button(False)

        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        if initial_counters_zero:
            self.sm.cur_frames.value = 0
            self.sm.stream_bytes.value = 0
            self.sm.projected_size.value = 0
        else:
            self.sm.cur_frames.value = 10
            self.sm.stream_bytes.value = 1024 * 1024
            self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RECORDING)
        if same_poll_start and hold_polls_into_rec == 0:
            self.sm.set_physical_video_button(False)
        if run_nolimit:
            self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.cancel_latched, 0)
        self.assertEqual(self.sm.restarts_remaining, expected_budget)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)

        for _ in range(hold_polls_into_rec):
            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RECORDING)
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(False)
            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RECORDING)

    def _prime_in_bounds_reason3_metrics(self, clip_index: int = 1, run_nolimit: bool = True) -> None:
        self.sm.cur_frames.value = 28000 + clip_index * 100
        self.sm.stream_bytes.value = 0xFF000000 + clip_index * 4096
        self.sm.projected_size.value = 0xFF800000 + clip_index * 4096
        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RECORDING)

    def _prime_in_bounds_reason4_metrics(self, max_frames: int = 1800, cur_frames: int = 900) -> None:
        self.sm.max_frames.value = max_frames
        self.sm.cur_frames.value = cur_frames
        self.sm.stream_bytes.value = 64 * 1024 * 1024
        self.sm.projected_size.value = 64 * 1024 * 1024
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_RECORDING)

    def _run_admitted_reason3_restart_to_confirmed_recording(
        self,
        expected_remaining_after_admission: int,
        expected_used_after_admission: int,
    ) -> None:
        self.sm.projected_size.value = 0x100000400 + expected_used_after_admission * 8192
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
        self.assertEqual(self.sm.attempt_admitted, 1)

        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)

        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = expected_used_after_admission + 1
        self.sm.stream_bytes.value = 65536 * (expected_used_after_admission + 1)
        self.sm.projected_size.value = 65536 * (expected_used_after_admission + 1)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
        self.assertEqual(self.sm.attempt_admitted, 0)

    def test_deliberate_starts_across_shooting_mode_inputs_and_mode_transitions(self) -> None:
        # 1. Deliberate physical start arms continuation in every shooting-mode playrec_mode value:
        #    2 (stills/movie shooting mode), 4 (Canon menu in record mode), 5 (stills-to-movie mode transition)
        for rec_mode in (2, 4, 5):
            for trans in ((), (2,), (3,), (4,), (2, 3), (3, 4, 0)):
                with self.subTest(playrec_mode=rec_mode, transitional_states=trans):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(
                        playrec_mode=rec_mode,
                        transitional_states=trans,
                    )
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.restarts_remaining, G3X_AUTOCONT_BUDGET_STANDALONE)
                    self._prime_in_bounds_reason3_metrics(1)
                    self._run_admitted_reason3_restart_to_confirmed_recording(
                        expected_remaining_after_admission=49,
                        expected_used_after_admission=1,
                    )
                    self.assertEqual(self.sm.restart_count, 1)

        # 2. Dynamic playrec_mode changes across {2, 4, 5} during stills-to-movie startup
        #    (e.g. pressing KEY_VIDEO in stills mode 2 -> mode switch 5 with transitional mr_rec_state 3 -> movie rec 2)
        for mode_seq, state_seq in (
            ((2, 5, 2), (0, 3, 1)),
            ((4, 5, 2), (0, 2, 1)),
            ((2, 5, 5, 2), (0, 2, 4, 1)),
            ((5, 2, 2), (0, 0, 1)),
        ):
            with self.subTest(mode_seq=mode_seq, state_seq=state_seq):
                self.sm.reset()
                self.sm.playrec_mode.value = mode_seq[0]
                self.sm.movie_state.value = 0
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.confirmed_idle_ready, 1)

                # Press KEY_VIDEO in confirmed IDLE
                self.sm.set_physical_video_button(True)
                self.sm.movie_state.value = state_seq[0]
                if state_seq[0] == 1:
                    self.sm.cur_frames.value = 10
                    self.sm.stream_bytes.value = 1024 * 1024
                    self.sm.projected_size.value = 2 * 1024 * 1024
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 1)
                self.sm.set_physical_video_button(False)

                for m_val, s_val in zip(mode_seq[1:], state_seq[1:]):
                    self.sm.playrec_mode.value = m_val
                    self.sm.movie_state.value = s_val
                    if s_val == 1:
                        self.sm.max_frames.value = 54000
                        self.sm.cur_frames.value = 10
                        self.sm.stream_bytes.value = 1024 * 1024
                        self.sm.projected_size.value = 2 * 1024 * 1024
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                    else:
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.idle_start_press_seen, 1)

                self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.restarts_remaining, 50)

        # 3. Returning from Playback mode (playrec_mode in {0, 1, 3, 6}) to any shooting mode ({2, 4, 5})
        #    re-establishes confirmed IDLE on the first released IDLE poll and arms on deliberate start
        for play_val in (0, 1, 3, 6):
            for rec_val in (2, 4, 5):
                with self.subTest(from_playback=play_val, to_shooting=rec_val):
                    self.sm.reset()
                    self.sm.playrec_mode.value = play_val
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
                    self.assertEqual(self.sm.confirmed_idle_ready, 0)

                    self._start_deliberate_physical_recording(
                        playrec_mode=rec_val,
                        transitional_states=(2, 3),
                    )
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
                    self.assertEqual(self.sm.restarts_remaining, 50)

    def test_confirmed_idle_transitions_same_poll_starts_and_transitional_states(self) -> None:
        # 1. Same-poll Confirmed IDLE (0) -> RECORDING (1) with physical KEY_VIDEO pressed
        for hold_into_rec in (0, 1, 10, G3X_AUTOCONT_START_HOLD_POLLS):
            with self.subTest(same_poll_start_hold_into_rec=hold_into_rec):
                self.sm.reset()
                self._start_deliberate_physical_recording(
                    same_poll_start=True,
                    hold_polls_into_rec=hold_into_rec,
                )
                self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.cancel_latched, 0)
                self.assertEqual(self.sm.session_cancelled, 0)
                self.assertEqual(self.sm.restarts_remaining, 50)

        # 2. Same-poll Confirmed IDLE (0) -> transitional {2, 3, 4} with physical KEY_VIDEO pressed -> RECORDING (1)
        for trans in ((2,), (3,), (4,), (2, 3, 4), (3, 0, 2)):
            for hold_trans in (False, True):
                with self.subTest(same_poll_transitional=trans, hold_trans=hold_trans):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(
                        transitional_states=trans,
                        same_poll_transitional=True,
                        hold_across_transitional=hold_trans,
                    )
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.restarts_remaining, 50)

        # 3. Confirmed IDLE (0) -> press in IDLE (0) -> transitional {2, 3, 4} -> RECORDING (1)
        #    with button either released in IDLE, released during transitional polls, or held across transitional polls into RECORDING
        for trans in ((2,), (3,), (4,), (2, 3), (2, 3, 4), (2, 0), (2, 0, 3)):
            for hold_trans in (False, True):
                for hold_rec in (0, 5):
                    with self.subTest(trans=trans, hold_trans=hold_trans, hold_rec=hold_rec):
                        self.sm.reset()
                        self._start_deliberate_physical_recording(
                            transitional_states=trans,
                            hold_across_transitional=hold_trans,
                            hold_polls_into_rec=hold_rec,
                        )
                        self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                        self.assertEqual(self.sm.restarts_remaining, 50)

        # 4. Pre-recording transitional sequence up to 199 released polls (just under 200-poll confirm window) still arms
        self.sm.reset()
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        for i in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
            self.sm.movie_state.value = 2 if (i % 2 == 0) else 3
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.idle_start_press_seen, 1)
            self.assertEqual(self.sm.idle_press_age, G3X_AUTOCONT_CONFIRM_POLLS - 1 - i)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restarts_remaining, 50)

    def test_held_released_buttons_latch_resets_and_already_recording_startup_without_deliberate_intent(self) -> None:
        # 1. Booting already in RECORDING (1) without confirmed boot idle stays DISARMED and never calls backlight or synth press
        self.sm.reset()
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 100
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        for _ in range(150):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.confirmed_idle_ready, 0)
        self.assertEqual(self.sm.backlight_off_count, 0)
        self.assertEqual(self.sm.backlight_on_count, 0)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(60):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

        # 2. Booting in transitional state {2, 3, 4} (even with button pressed) followed by RECORDING (1) refuses to arm
        for boot_state in (2, 3, 4):
            for pressed in (False, True):
                with self.subTest(boot_transitional_state=boot_state, pressed=pressed):
                    self.sm.reset()
                    self.sm.movie_state.value = boot_state
                    self.sm.set_physical_video_button(pressed)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.confirmed_idle_ready, 0)
                    self.assertEqual(self.sm.idle_start_press_seen, 0)
                    self.sm.set_physical_video_button(False)
                    self.sm.movie_state.value = 1
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.restarts_remaining, 0)

        # 3. Holding physical KEY_VIDEO at boot in IDLE (0) before any released IDLE poll refuses to arm
        self.sm.reset()
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.confirmed_idle_ready, 0)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)

        # 4. Unattributed IDLE (0) -> RECORDING (1) or IDLE (0) -> {2, 3, 4} -> RECORDING (1) without physical KEY_VIDEO press refuses to arm
        for trans in ((), (2,), (3,), (4,), (2, 3)):
            with self.subTest(unattributed_transition=trans):
                self.sm.reset()
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.confirmed_idle_ready, 1)
                for t_state in trans:
                    self.sm.movie_state.value = t_state
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.confirmed_idle_ready, 0)
                self.sm.movie_state.value = 1
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.confirmed_idle_ready, 0)
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.assertEqual(self.sm.backlight_off_count, 0)

        # 5. Pressing physical KEY_VIDEO only AFTER mr_rec_state has already entered {2, 3, 4} without a confirmed-IDLE press
        #    is treated as a stop/cancel press, NOT a start press!
        for t_state in (2, 3, 4):
            with self.subTest(press_after_entering_transitional=t_state):
                self.sm.reset()
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed IDLE
                self.sm.movie_state.value = t_state  # Enters transitional state without press
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.confirmed_idle_ready, 0)
                self.sm.set_physical_video_button(True)  # Late press while already in transitional state
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.cancel_latched, 1)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.sm.set_physical_video_button(False)
                self.sm.movie_state.value = 1
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # 6. Pressing physical KEY_VIDEO in confirmed IDLE, releasing during transitional {2, 3, 4}, and pressing
        #    KEY_VIDEO a SECOND time during {2, 3, 4} or on the transition to RECORDING (1) aborts arming and latches PHYS_STOP
        for second_press_target in ("during_transitional", "on_recording_entry"):
            with self.subTest(second_press_target=second_press_target):
                self.sm.reset()
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 1)
                # Release during transitional state 2
                self.sm.set_physical_video_button(False)
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 1)

                # Second press!
                self.sm.set_physical_video_button(True)
                if second_press_target == "during_transitional":
                    self.sm.movie_state.value = 3
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.idle_start_press_seen, 0)
                    self.assertEqual(self.sm.cancel_latched, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.sm.set_physical_video_button(False)
                    self.sm.movie_state.value = 1
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                else:
                    self.sm.movie_state.value = 1
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.idle_start_press_seen, 0)
                    self.assertEqual(self.sm.cancel_latched, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                    self.assertEqual(self.sm.session_cancelled, 1)

        # 7. Holding physical KEY_VIDEO in transitional {2, 3, 4} past G3X_AUTOCONT_START_HOLD_POLLS (50 polls)
        #    resets the start latch and latches PHYS_STOP
        self.sm.reset()
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 2
        for _ in range(G3X_AUTOCONT_START_HOLD_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.idle_start_press_seen, 1)
        # Poll 51 while still held in transitional state 2 -> cancels
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.idle_start_press_seen, 0)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # 8. Latch age expiry after 200 released polls in IDLE (0) or across transitional {2, 3, 4} polls refuses to arm
        for expiry_state in (0, 2, 3, 4):
            with self.subTest(expiry_state=expiry_state):
                self.sm.reset()
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(False)
                self.sm.movie_state.value = expiry_state
                for _ in range(G3X_AUTOCONT_CONFIRM_POLLS):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 0)
                self.sm.movie_state.value = 1
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.restarts_remaining, 0)

        # 9. Latch resets on Playback mode entry or invalid mr_rec_state after confirmed-IDLE press
        for reset_trigger in ("playback", "invalid_neg", "invalid_high"):
            with self.subTest(reset_trigger=reset_trigger):
                self.sm.reset()
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(False)
                self.assertEqual(self.sm.idle_start_press_seen, 1)

                if reset_trigger == "playback":
                    self.sm.playrec_mode.value = 1
                elif reset_trigger == "invalid_neg":
                    self.sm.movie_state.value = -1
                else:
                    self.sm.movie_state.value = 5
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.idle_start_press_seen, 0)
                self.assertEqual(self.sm.confirmed_idle_ready, 0)

                # Returning directly to shooting mode in RECORDING (1) without a new confirmed-IDLE press cannot arm
                self.sm.playrec_mode.value = 2
                self.sm.movie_state.value = 1
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

    def test_bounded_screen_off_periodic_refresh_display_toggle_and_restoration_policy(self) -> None:
        # 1. Start deliberate recording with 5-poll initial KEY_VIDEO hold:
        #    while KEY_VIDEO is held in RECORDING, screen_off_delay_polls does not decrement and TurnOffBackLight is not called
        self._start_deliberate_physical_recording(
            playrec_mode=2,
            transitional_states=(2, 3),
            hold_polls_into_rec=5,
        )
        # Note: _start_deliberate_physical_recording released KEY_VIDEO on the last step, which consumed poll 1 of the 100-poll delay
        self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.screen_off_active, 0)
        self.assertEqual(self.sm.backlight_off_count, 0)
        self.assertEqual(self.sm.backlight_on_count, 0)
        self.assertEqual(self.sm.backlight_hw_on.value, 1)
        self.assertEqual(self.sm.screen_off_delay_polls, G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1)

        # 2. Step through remaining 98 polls of post-start settle: still 0 TurnOffBackLight calls
        for rem in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 2, 0, -1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.screen_off_active, 0)
            self.assertEqual(self.sm.screen_off_delay_polls, rem)
            self.assertEqual(self.sm.backlight_off_count, 0)
            self.assertEqual(self.sm.backlight_hw_on.value, 1)

        # 3. Poll 100 after release: TurnOffBackLight() is called exactly once
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.screen_off_active, 1)
        self.assertEqual(self.sm.screen_off_delay_polls, 0)
        self.assertEqual(self.sm.screen_refresh_polls, G3X_AUTOCONT_SCREEN_REFRESH_POLLS)
        self.assertEqual(self.sm.backlight_off_count, 1)
        self.assertEqual(self.sm.turn_off_backlight_calls.value, 1)
        self.assertEqual(self.sm.backlight_on_count, 0)
        self.assertEqual(self.sm.backlight_hw_on.value, 0)
        self.assertEqual(self.sm.last_backlight_call_rec_state.value, 1)
        self.assertEqual(self.sm.last_backlight_call_mode_play.value, 0)

        # 4. Bounded 3000-poll (30.0 s) periodic refresh:
        #    Simulate an unknown asynchronous Canon wake (backlight_hw_on = 1) during recording;
        #    polls 1..2999 make 0 firmware calls; poll 3000 calls TurnOffBackLight() once and re-blanks hardware!
        self.sm.backlight_hw_on.value = 1
        for _ in range(G3X_AUTOCONT_SCREEN_REFRESH_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.backlight_off_count, 1)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.backlight_off_count, 2)
        self.assertEqual(self.sm.backlight_hw_on.value, 0)
        self.assertEqual(self.sm.screen_refresh_polls, G3X_AUTOCONT_SCREEN_REFRESH_POLLS)

        # 5. Manual KEY_DISPLAY (0x00001000) edge-triggered wake & re-blank toggle while recording:
        #    Pressing KEY_DISPLAY wakes the screen once (TurnOnBackLight), masks bit 12 in physw_status[0] while held,
        #    and pauses automatic blanking until KEY_DISPLAY is pressed again.
        self.sm.set_physical_display_button(True)
        for _ in range(5):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.screen_off_active, 0)
            self.assertEqual(self.sm.backlight_on_count, 1)
            self.assertEqual(self.sm.backlight_off_count, 2)
            self.assertEqual(self.sm.backlight_hw_on.value, 1)
            # Consumed KEY_DISPLAY is masked high (released) in physw_status[0]
            self.assertFalse(self.sm.physw_display_pressed)
        self.sm.set_physical_display_button(False)
        for _ in range(250):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.screen_off_active, 0)
            self.assertEqual(self.sm.backlight_off_count, 2)
            self.assertEqual(self.sm.backlight_on_count, 1)

        # Pressing KEY_DISPLAY a second time turns the screen back off immediately and resumes bounded refresh
        self.sm.set_physical_display_button(True)
        for _ in range(4):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.screen_off_active, 1)
            self.assertEqual(self.sm.backlight_off_count, 3)
            self.assertEqual(self.sm.backlight_on_count, 1)
            self.assertEqual(self.sm.backlight_hw_on.value, 0)
            self.assertFalse(self.sm.physw_display_pressed)
        self.sm.set_physical_display_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        # 6. Multi-segment continuation re-assertion:
        #    When Clip 1 hits Reason 3 and continues to Clip 2, screen_off_active stays 1 across WAIT_IDLE..WAIT_CONFIRM
        #    without calling TurnOnBackLight(), and 100 polls into Clip 2 calls TurnOffBackLight() once!
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(
            expected_remaining_after_admission=49,
            expected_used_after_admission=1,
        )
        self.assertEqual(self.sm.screen_off_active, 1)
        self.assertEqual(self.sm.backlight_on_count, 1)
        self.assertEqual(self.sm.backlight_off_count, 3)
        # g3x_autocont_enter_confirmed_recording() + sample + poll in step() already ran 1 poll of Clip 2's 100-poll delay
        self.assertEqual(self.sm.screen_off_delay_polls, G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1)
        for _ in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 2):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.backlight_off_count, 3)
        self.sm.backlight_hw_on.value = 1  # Simulate Canon waking display on Clip 2 start
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.backlight_off_count, 4)
        self.assertEqual(self.sm.backlight_hw_on.value, 0)

        # 7. Stopping recording via physical KEY_VIDEO restores backlight once via TurnOnBackLight()
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.assertEqual(self.sm.screen_off_active, 0)
        self.assertEqual(self.sm.backlight_on_count, 2)
        self.assertEqual(self.sm.backlight_hw_on.value, 1)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 0
        for _ in range(200):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.backlight_on_count, 2)
            self.assertEqual(self.sm.backlight_off_count, 4)

        # 8. In DISARMED, pressing KEY_DISPLAY passes through to physw_status[0] unmasked and makes 0 backlight calls
        self.sm.set_physical_display_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertTrue(self.sm.physw_display_pressed)
        self.assertEqual(self.sm.backlight_on_count, 2)
        self.assertEqual(self.sm.backlight_off_count, 4)
        self.sm.set_physical_display_button(False)

    def test_screen_off_restoration_across_every_disarm_and_exit_path_and_refresh_cap(self) -> None:
        # 1. Verify single-call TurnOnBackLight() restoration across every disarm/exit path while screen_off_active == 1
        exit_modes = (
            "phys_stop_in_recording",
            "phys_stop_same_poll_as_display_key",
            "phys_stop_in_early_clip2_before_reassert",
            "phys_stop_in_wait_idle",
            "phys_stop_in_settle",
            "phys_stop_in_pressing",
            "phys_stop_in_releasing",
            "phys_stop_in_wait_confirm",
            "ineligible_stop_fault",
            "budget_exhaustion",
            "wait_idle_timeout",
            "wait_confirm_timeout",
            "invalid_rec_state",
            "playback_entry",
            "session_cancel_api",
            "user_disable_api",
        )
        for mode in exit_modes:
            with self.subTest(exit_mode=mode):
                self.sm.reset()
                budget = 1 if mode == "budget_exhaustion" else 50
                self._start_deliberate_physical_recording(budget=budget)
                # Advance 99 more polls so initial TurnOffBackLight() engages
                for _ in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.screen_off_active, 1)
                self.assertEqual(self.sm.backlight_off_count, 1)
                self.assertEqual(self.sm.backlight_on_count, 0)
                self.assertEqual(self.sm.backlight_hw_on.value, 0)

                if mode == "phys_stop_in_recording":
                    self.sm.set_physical_video_button(True)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                elif mode == "phys_stop_same_poll_as_display_key":
                    self.sm.set_physical_display_button(True)
                    self.sm.set_physical_video_button(True)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                elif mode == "phys_stop_in_early_clip2_before_reassert":
                    self._prime_in_bounds_reason3_metrics(1)
                    self._run_admitted_reason3_restart_to_confirmed_recording(49, 1)
                    # Stop during Clip 2 poll 10 (before poll 100 reassert fires): must still call TurnOnBackLight()!
                    for _ in range(10):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.screen_off_active, 1)
                    self.sm.set_physical_video_button(True)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                elif mode == "ineligible_stop_fault":
                    self._prime_in_bounds_reason3_metrics(1)
                    self.sm.stop_reason.value = 2  # Card full
                    self.sm.movie_state.value = 2
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
                elif mode == "budget_exhaustion":
                    self._prime_in_bounds_reason3_metrics(1)
                    self._run_admitted_reason3_restart_to_confirmed_recording(0, 1)
                    self._prime_in_bounds_reason3_metrics(2)
                    self.sm.projected_size.value = 0x100080000
                    self.sm.stop_reason.value = 3
                    self.sm.movie_state.value = 2
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
                elif mode == "invalid_rec_state":
                    self.sm.movie_state.value = 5
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                elif mode == "playback_entry":
                    self.sm.playrec_mode.value = 1
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
                elif mode == "session_cancel_api":
                    self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 1)
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                elif mode == "user_disable_api":
                    self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                else:
                    self._prime_in_bounds_reason3_metrics(1)
                    self.sm.projected_size.value = 0x100000400
                    self.sm.stop_reason.value = 3
                    if mode in ("phys_stop_in_wait_idle", "wait_idle_timeout"):
                        self.sm.movie_state.value = 2
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                        self.assertEqual(self.sm.screen_off_active, 1)
                        if mode == "phys_stop_in_wait_idle":
                            self.sm.set_physical_video_button(True)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        else:
                            for _ in range(G3X_AUTOCONT_MAX_STOP_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    else:
                        self.sm.movie_state.value = 0
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                        if mode == "phys_stop_in_settle":
                            self.sm.set_physical_video_button(True)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        else:
                            for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                            if mode == "phys_stop_in_pressing":
                                self.sm.set_physical_video_button(True)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                            else:
                                for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                                if mode == "phys_stop_in_releasing":
                                    self.sm.set_physical_video_button(True)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                else:
                                    for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                    if mode == "phys_stop_in_wait_confirm":
                                        self.sm.set_physical_video_button(True)
                                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    else:
                                        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
                                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

                self.assertEqual(self.sm.screen_off_active, 0)
                self.assertEqual(self.sm.backlight_on_count, 1)
                self.assertEqual(self.sm.turn_on_backlight_calls.value, 1)
                self.assertEqual(self.sm.backlight_hw_on.value, 1)
                # Subsequent disarmed polls never emit extra TurnOnBackLight calls
                self.sm.set_physical_video_button(False)
                self.sm.set_physical_display_button(False)
                for _ in range(25):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.backlight_on_count, 1)

        # 2. Verify finite per-clip cap (120 refreshes) on periodic TurnOffBackLight() calls
        self.sm.reset()
        self._start_deliberate_physical_recording()
        for _ in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.backlight_off_count, 1)
        for refresh_idx in range(1, G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS + 1):
            for _ in range(G3X_AUTOCONT_SCREEN_REFRESH_POLLS):
                self.sm.lib.g3x_movie_autocont_poll()
            self.assertEqual(self.sm.backlight_off_count, 1 + refresh_idx)
        # After 120 refreshes (total 121 TurnOffBackLight calls), further polls in the same clip make 0 calls
        for _ in range(G3X_AUTOCONT_SCREEN_REFRESH_POLLS * 2):
            self.sm.lib.g3x_movie_autocont_poll()
        self.assertEqual(self.sm.backlight_off_count, 1 + G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS)

    def test_regressions_preserve_priority_cancellation_stop_attribution_and_50_restart_budget(self) -> None:
        # 1. Stop attribution: Reason 3 and Reason 4 admitted; user stop (0), overflow (1), card full (2),
        #    and unknown/fault reasons (>= 5) vetoed and restore backlight
        for veto_reason in (0, 1, 2, 5, 6, 99):
            with self.subTest(veto_reason=veto_reason):
                self.sm.reset()
                self._start_deliberate_physical_recording(transitional_states=(2, 3))
                for _ in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1):
                    self.sm.step()
                self.assertEqual(self.sm.screen_off_active, 1)
                self._prime_in_bounds_reason3_metrics(1)
                self.sm.projected_size.value = 0x100000400
                self.sm.stop_reason.value = veto_reason
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
                self.assertEqual(self.sm.screen_off_active, 0)
                self.assertEqual(self.sm.backlight_on_count, 1)
                self.assertEqual(self.sm.press_calls.value, 0)

        # 2. Full 50-restart standalone session across 51 clips (started from stills-mode transitional sequence 0 -> 2 -> 3 -> 1)
        self.sm.reset()
        self._start_deliberate_physical_recording(
            playrec_mode=2,
            transitional_states=(2, 3),
        )
        self.assertEqual(self.sm.restart_budget, 50)
        self.assertEqual(self.sm.restarts_remaining, 50)
        for attempt_idx in range(1, G3X_AUTOCONT_BUDGET_STANDALONE + 1):
            expected_rem = G3X_AUTOCONT_BUDGET_STANDALONE - attempt_idx
            self._prime_in_bounds_reason3_metrics(attempt_idx)
            self._run_admitted_reason3_restart_to_confirmed_recording(
                expected_remaining_after_admission=expected_rem,
                expected_used_after_admission=attempt_idx,
            )
            self.assertEqual(self.sm.restarts_remaining, expected_rem)
            self.assertEqual(self.sm.session_restarts_used, attempt_idx)
            self.assertEqual(self.sm.restart_count, attempt_idx)

        # Exhaustion on Clip 51 stop disarms cleanly without attempt 51 and restores backlight if active
        for _ in range(G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS - 1):
            self.sm.step()
        self.assertEqual(self.sm.screen_off_active, 1)
        self._prime_in_bounds_reason3_metrics(51)
        presses_after_50 = self.sm.press_calls.value
        self.sm.projected_size.value = 0x100200000
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 50)
        self.assertEqual(self.sm.press_calls.value, presses_after_50)
        self.assertEqual(self.sm.screen_off_active, 0)
        self.assertEqual(self.sm.backlight_on_count, 1)


class TestPort64BuildArtifactsDisassemblyAndPreservedProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_port59()
        ensure_build_port60()
        ensure_build_port61()
        p62_out = ROOT / "out/port62-movie-standalone"
        p62_bin = p62_out / "DISKBOOT.BIN"
        p62_elf = p62_out / "stage_chdk/platform/g3x/sub/110c/main.elf"
        if not (p62_bin.is_file() and p62_elf.is_file() and sha256_file(p62_bin) == PORT62_STANDALONE_SHA256):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port62_movie_standalone.py"),
                    "--out-dir",
                    str(p62_out),
                ],
                cwd=str(ROOT),
                check=True,
            )
        ensure_build_port64()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p59_bin = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
        cls.p59_elf = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p60_bin = ROOT / "out/port60-movie-restart-budget/DISKBOOT.BIN"
        cls.p60_elf = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p61_bin = ROOT / "out/port61-movie-session-cancel/DISKBOOT.BIN"
        cls.p61_elf = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p62_bin = p62_bin
        cls.p62_elf = p62_elf

        cls.p64_out_dir = ROOT / "build/port64-movie-screen-off"
        cls.p64_bin = cls.p64_out_dir / "DISKBOOT.BIN"
        cls.p64_elf = cls.p64_out_dir / "stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p64_obj = cls.p64_out_dir / "stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.p64_manifest = cls.p64_out_dir / "port64_movie_screen_off_manifest.json"
        cls.p64_stage = cls.p64_out_dir / "stage_chdk"

    def test_default_and_existing_port55_to_port63_profiles_remain_byte_identical(self) -> None:
        # 1. Default build byte-identical
        self.assertTrue(self.default_bin.is_file())
        self.assertEqual(sha256_file(self.default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(self.default_bin.stat().st_size, BASE_DEFAULT_SIZE)
        nm_default = subprocess.check_output([str(NM), str(self.default_elf)], text=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", nm_default)

        # 2. PORT-59 combined profile byte-identical
        self.assertTrue(self.p59_bin.is_file())
        self.assertEqual(sha256_file(self.p59_bin), PORT59_COMBINED_SHA256)
        self.assertEqual(self.p59_bin.stat().st_size, PORT59_COMBINED_SIZE)
        nm_p59 = subprocess.check_output([str(NM), str(self.p59_elf)], text=True)
        self.assertIn(f"{PORT59_COMBINED_END} B _end", nm_p59)

        # 3. PORT-60 restart budget profile byte-identical
        self.assertTrue(self.p60_bin.is_file())
        self.assertEqual(sha256_file(self.p60_bin), PORT60_BUDGET_SHA256)
        self.assertEqual(self.p60_bin.stat().st_size, PORT60_BUDGET_SIZE)
        nm_p60 = subprocess.check_output([str(NM), str(self.p60_elf)], text=True)
        self.assertIn(f"{PORT60_BUDGET_END} B _end", nm_p60)

        # 4. PORT-61 session cancel profile byte-identical
        self.assertTrue(self.p61_bin.is_file())
        self.assertEqual(sha256_file(self.p61_bin), PORT61_CANCEL_SHA256)
        self.assertEqual(self.p61_bin.stat().st_size, PORT61_CANCEL_SIZE)
        nm_p61 = subprocess.check_output([str(NM), str(self.p61_elf)], text=True)
        self.assertIn(f"{PORT61_CANCEL_END} B _end", nm_p61)

        # 5. PORT-62/63 standalone profile byte-identical
        self.assertTrue(self.p62_bin.is_file())
        self.assertEqual(sha256_file(self.p62_bin), PORT62_STANDALONE_SHA256)
        self.assertEqual(self.p62_bin.stat().st_size, PORT62_STANDALONE_SIZE)
        nm_p62 = subprocess.check_output([str(NM), str(self.p62_elf)], text=True)
        self.assertIn(f"{PORT62_STANDALONE_END} B _end", nm_p62)

        # 6. Existing individual profiles (PORT-55, PORT-56, PORT-57, PORT-58) byte-identical
        for name, spec in INDIVIDUAL_PROFILES.items():
            with self.subTest(profile=name):
                bin_path = spec["bin"]
                elf_path = spec["elf"]
                if not (bin_path.is_file() and elf_path.is_file()):
                    subprocess.run(
                        [sys.executable, "-B", str(BUILD_SCRIPT), *spec["args"]],
                        cwd=str(ROOT),
                        check=True,
                    )
                self.assertEqual(sha256_file(bin_path), spec["sha256"], f"SHA-256 mismatch for {name}")
                self.assertEqual(bin_path.stat().st_size, spec["size"], f"Size mismatch for {name}")
                nm_out = subprocess.check_output([str(NM), str(elf_path)], text=True)
                self.assertIn(f"{spec['end']} B _end", nm_out, f"_end mismatch for {name}")

    def test_port64_manifest_flags_hashes_no_chdk_dir_backlight_stubs_and_disassembly_safety(self) -> None:
        self.assertTrue(self.p64_bin.is_file())
        self.assertTrue(self.p64_elf.is_file())
        self.assertTrue(self.p64_obj.is_file())
        self.assertTrue(self.p64_manifest.is_file())
        self.assertFalse((self.p64_out_dir / "CHDK").exists(), "PORT-64 standalone output must not contain a CHDK/ directory")

        m = json.loads(self.p64_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_id"], "port64_movie_screen_off_manifest")
        self.assertEqual(m["milestone"], "PORT-64")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_PORT61_COMMIT)
        self.assertEqual(m["candidate_source_base"], PORT63_FINAL_INTEGRATION_COMMIT)
        self.assertEqual(m["port63_final_integration_commit"], PORT63_FINAL_INTEGRATION_COMMIT)
        self.assertEqual(m["port64_research_integration_commit"], PORT64_RESEARCH_INTEGRATION_COMMIT)
        self.assertEqual(m["standalone_policy"]["default_restart_budget"], G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(m["standalone_policy"]["fixed_compile_time_restart_budget"], G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertTrue(m["standalone_policy"]["deliberate_start_arming_across_shooting_modes"])
        self.assertTrue(m["standalone_policy"]["hermetic_staging"])
        self.assertTrue(m["screen_off_policy"]["supported"])
        self.assertEqual(m["screen_off_policy"]["turn_off_backlight_address"], "0xFC37C449")
        self.assertEqual(m["screen_off_policy"]["turn_on_backlight_address"], "0xFC37C3EF")
        self.assertEqual(m["screen_off_policy"]["post_start_settle_delay_polls"], G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS)
        self.assertEqual(m["screen_off_policy"]["periodic_refresh_interval_polls"], G3X_AUTOCONT_SCREEN_REFRESH_POLLS)
        self.assertEqual(m["screen_off_policy"]["max_periodic_refresh_calls_per_clip"], G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS)
        self.assertEqual(m["screen_off_policy"]["runtime_canon_wake_behavior"], "UNVERIFIED / UNKNOWN")

        self.assertEqual(sha256_file(self.p64_bin), PORT64_SCREEN_OFF_SHA256)
        self.assertEqual(self.p64_bin.stat().st_size, PORT64_SCREEN_OFF_SIZE)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT64_SCREEN_OFF_SHA256)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], PORT64_SCREEN_OFF_SIZE)
        self.assertEqual(m["artifacts"]["modules_count"], 0)
        self.assertEqual(m["artifacts"]["modules"], {})
        self.assertEqual(m["artifacts"]["chdk_files_count"], 0)
        self.assertEqual(m["artifacts"]["chdk_files"], {})
        self.assertEqual(m["_end"], f"0x{PORT64_SCREEN_OFF_END}")

        flags = m["build"]["flags"]
        expected_flags = [
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
        self.assertEqual(flags, expected_flags)

        nm_out = subprocess.check_output([str(NM), str(self.p64_elf)], text=True)
        for req_sym in (
            "g3x_get_movie_status",
            "g3x_movie_nolimit_poll",
            "g3x_movie_autocont_poll",
            "g3x_movie_autocont_is_screen_off_active",
            "g3x_movie_autocont_get_screen_off_delay_polls",
            "g3x_movie_autocont_get_screen_refresh_polls",
            "g3x_movie_autocont_get_backlight_off_count",
            "g3x_movie_autocont_get_backlight_on_count",
            "g3x_movie_autocont_is_confirmed_idle_ready",
            "g3x_movie_autocont_is_idle_start_press_seen",
            "g3x_movie_autocont_get_idle_press_age",
            "TurnOffBackLight",
            "_TurnOffBackLight",
            "TurnOnBackLight",
            "_TurnOnBackLight",
            "rec_mode_active",
            "mykbd_task",
            "my_kbd_read_keys",
            "core_spytask",
            "kbd_process",
            "ftell",
        ):
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in PORT-64 main.elf")

        # Verify MovieRecorder write allowlist and read-only accessors in movie_rec.o and main.elf
        accessors = (
            "g3x_get_movie_status",
            "g3x_get_movie_max_frames",
            "g3x_get_movie_cur_frames",
            "g3x_get_movie_stop_reason",
            "g3x_get_movie_segment_index",
            "g3x_get_movie_fs_reserve_size",
            "g3x_get_movie_avail_space",
            "g3x_get_movie_stream_bytes",
            "g3x_get_movie_projected_size",
            "g3x_get_movie_projected_base_offset",
        )
        movie_rec_helpers = {
            "g3x_get_movie_status",
            "g3x_get_movie_max_frames",
            "g3x_get_movie_cur_frames",
            "change_video_tables",
            "set_quality",
        }
        for target_path in (self.p64_obj, self.p64_elf):
            disasm = subprocess.check_output([str(OBJDUMP), "-d", str(target_path)], text=True)
            stores = verify_movie_nolimit_stores(
                disasm,
                entry_symbol="g3x_movie_nolimit_poll",
                allowed_helpers=movie_rec_helpers,
            )
            self.assertGreaterEqual(len(stores), 1)
            for s in stores:
                self.assertEqual(s["dest_addr"], 0x0000C274)
                self.assertEqual(s["stored_val"], 0xFFFFFFFF)

            for fn in accessors:
                instrs = parse_function_instructions(disasm, fn)
                self.assertGreater(len(instrs), 0)
                for instr in instrs:
                    mnem = instr["mnemonic"]
                    self.assertFalse(mnem.startswith("str") or mnem.startswith("stm") or mnem.startswith("push"))

            for fhex in ("c078", "c0c0", "c0c8", "c0d4", "c0d8", "c0e4", "c278", "c290", "c298", "c2a0", "c2a8"):
                for match in re.finditer(
                    rf"^\s*([0-9a-f]+):\s+([0-9a-f\s]+?)\t([a-z0-9\._]+)\s*([^;\n]*;\s*.*{fhex}.*)",
                    disasm,
                    re.M | re.I,
                ):
                    mnem = match.group(3).lower()
                    self.assertFalse(mnem.startswith("str") or mnem.startswith("stm"))

        # Verify _TurnOffBackLight (0xfc37c449) and _TurnOnBackLight (0xfc37c3ef) stub targets in main.elf disassembly
        elf_disasm = subprocess.check_output([str(OBJDUMP), "-d", str(self.p64_elf)], text=True)
        self.assertIn("fc37c449", elf_disasm.lower())
        self.assertIn("fc37c3ef", elf_disasm.lower())
        poll_instrs = parse_function_instructions(elf_disasm, "g3x_movie_autocont_poll")
        poll_text = "\n".join(i["line"] for i in poll_instrs)
        self.assertIn("<TurnOffBackLight>", elf_disasm)
        self.assertIn("<TurnOnBackLight>", elf_disasm)
        self.assertIn("<rec_mode_active>", elf_disasm)
        self.assertTrue(
            "<g3x_autocont_sync_mode_play>" in poll_text or "<rec_mode_active>" in poll_text,
            "g3x_movie_autocont_poll must synchronize mode_play via rec_mode_active()",
        )

    def test_hermetic_port64_build_resists_conflicting_profile_contamination(self) -> None:
        p61_stage = ROOT / "out/port61-movie-session-cancel/stage_chdk"
        self.assertTrue(p61_stage.is_dir())
        with tempfile.TemporaryDirectory(prefix="port64_contaminate_") as tmpdir:
            dirty_out = Path(tmpdir) / "dirty_port64_out"
            dirty_stage = dirty_out / "stage_chdk"
            dirty_out.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", "-a", str(p61_stage), str(dirty_stage)], check=True)
            subprocess.run(["chmod", "-R", "u+w", str(dirty_stage)], check=True)
            (dirty_out / "CHDK" / "MODULES").mkdir(parents=True, exist_ok=True)
            (dirty_out / "CHDK" / "MODULES" / "stale.flt").write_bytes(b"STALE")
            (dirty_out / "DISKBOOT.BIN").write_bytes(b"CONTAMINATED")

            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(PORT64_BUILD_SCRIPT),
                    "--no-clean",
                    "--out-dir",
                    str(dirty_out),
                ],
                cwd=str(ROOT),
                check=True,
            )
            self.assertFalse((dirty_out / "CHDK").exists())
            self.assertTrue((dirty_out / "DISKBOOT.BIN").is_file())
            self.assertTrue((dirty_out / "port64_movie_screen_off_manifest.json").is_file())
            self.assertEqual(sha256_file(dirty_out / "DISKBOOT.BIN"), PORT64_SCREEN_OFF_SHA256)
            self.assertEqual((dirty_out / "DISKBOOT.BIN").stat().st_size, PORT64_SCREEN_OFF_SIZE)

    def test_port64_doc_records_evidence_policy_hashes_and_unverified_runtime_wake_behavior(self) -> None:
        doc_text = DOC_PORT64.read_text(encoding="utf-8")
        for token in (
            PORT63_FINAL_INTEGRATION_COMMIT,
            PORT64_RESEARCH_INTEGRATION_COMMIT,
            PORT64_IMPLEMENT_ATTEMPT1_COMMIT,
            PORT64_IMPLEMENT_PARTIAL_COMMIT,
            PORT62_STANDALONE_SHA256,
            PORT64_SCREEN_OFF_SHA256,
            str(PORT64_SCREEN_OFF_SIZE),
            f"0x{PORT64_SCREEN_OFF_END}",
            "PORT64-ROM-BACKLIGHT-CORE-WINDOW",
            "PORT64-ROM-DISPCON-BACKLIGHT-WINDOW",
            "SCOPE-PORT64-BACKLIGHT",
            PORT64_BACKLIGHT_CORE_WINDOW_SHA256,
            PORT64_DISPCON_BACKLIGHT_WINDOW_SHA256,
            "0xFC37C449",
            "0xFC37C3EF",
            "TurnOffBackLight",
            "TurnOnBackLight",
            "G3X_MOVIE_STANDALONE=1",
            "G3X_MOVIE_SCREEN_OFF=1",
            "G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS",
            "G3X_AUTOCONT_SCREEN_REFRESH_POLLS",
            "G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS",
            "scripts/build_port64_movie_screen_off.py",
            "tests/test_port64_movie_screen_off.py",
            "build/port64-movie-screen-off/DISKBOOT.BIN",
            "port64_movie_screen_off_manifest.json",
            "UNVERIFIED",
            "UNKNOWN",
        ):
            self.assertIn(token, doc_text, f"Missing '{token}' in docs/PORT64_MOVIE_SCREEN_OFF.md")


if __name__ == "__main__":
    unittest.main()
