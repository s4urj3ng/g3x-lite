"""Offline unit and integration tests for PORT-61 (Opt-In Movie Session Cancellation: G3X_MOVIE_SESSION_CANCEL=1).

Verifies:
1. Separately selected opt-in profile extending PORT-60 (G3X_MOVIE_SESSION_CANCEL=1 / --movie-session-cancel):
   - Exposes 'Cancel further restarts' through the existing volatile GUI (video_submenu_items[] in core/gui.c).
   - Requires G3X_MOVIE_RESTART_BUDGET=1 and all PORT-60 GUI/movie prerequisites.
   - Rejects G3X_CONF_SAVE=1, FULL_HOOKS=1, and *-alone combinations explicitly.
   - Continuation boots disabled (AC:OFF / "Off", Cancel further restarts [Idle]) and never persists in struct Conf.
2. Session cancellation latching, status display & restart admission prevention:
   - Cancellation latches for the live session (g3x_movie_autocont_is_session_cancelled() == 1), transitions to
     G3X_AUTOCONT_DISARMED with G3X_AUTOCONT_REASON_SESSION_CANCEL, prevents subsequent synthetic restart admissions,
     and shows a cancelled state through the existing status display (AC:CANC on <ALT> OSD Line 2/3, [Cancel] on
     Auto-Continue Movie and Cancel further restarts, reason "CANC").
3. Active-clip & budget preservation:
   - Cancellation issues no stop command (active clip mr_rec_state == 1 continues running uninterrupted with LIM:OFF)
     and preserves configured allowance (restart_budget), remaining budget (restarts_remaining), and consumed
     attempts (session_restarts_used) without refunding or resetting them.
4. Pending continuation cancellation & continuation-owned synthetic key release:
   - Pending continuation across WAIT_IDLE, SETTLE, PRESSING, RELEASING, and WAIT_CONFIRM is cancelled immediately.
   - Only continuation-owned synthetic keys (synth_owned != 0 in PRESSING) are released through existing ownership rules;
     unowned modifier bits in RECORDING, WAIT_IDLE, SETTLE, RELEASING, and WAIT_CONFIRM are never touched.
5. Pre-admission vs. already-issued start semantics:
   - Cancellation processed before admission (in RECORDING before 1 -> != 1) prevents that attempt from being admitted
     or consuming budget.
   - An already-issued synthetic start (cancelled during PRESSING, RELEASING, or WAIT_CONFIRM before mr_rec_state
     reaches 1) may complete recording with LIM:OFF, does not clear cancellation, and receives no further automatic
     continuation when that clip stops.
6. Physical-stop precedence, idempotence & no-live-session no-op:
   - Physical KEY_VIDEO stop takes precedence over session cancellation across all states and same-poll races.
   - Repeated cancellation is idempotent and cancellation without a live session (at boot, idle RDY, faulted,
     exhausted, or after physical stop) is a strict no-op.
7. Deliberate physical-start clearing vs. synthetic starts & GUI edits:
   - Only a new deliberate physical start after confirmed idle clears cancellation and begins a fresh session with
     restarts_remaining = restart_budget and session_restarts_used = 0.
   - Synthetic starts, unconfirmed-idle presses, and GUI edits (Auto-Continue Movie, Auto-Continue Budget,
     Cancel further restarts) cannot clear cancellation or reset the preserved counters while cancelled.
8. Preserved profiles, default output & disassembly safety:
   - Default build and existing PORT-55..60 profiles remain 100% byte-identical.
   - Disassembly of movie_rec.o and main.elf proves zero stores to MovieRecorder RAM outside 0xFFFFFFFFU -> 0x0000C274.
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

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
GUI_MENU_C = ROOT / "chdk-port/platform/g3x/gui_menu.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
DOC_PORT61 = ROOT / "docs/PORT61_MOVIE_SESSION_CANCEL.md"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_PORT60_COMMIT = "355204f778da2defbc8dd8e2a538be36031958b7"
PORT60_VALIDATE_COMMIT = "018cfa4e95d5eac39dc16b46cbead3c5bf2b43d0"
PORT60_INTEGRATION_TIP = "4c3110a63c5246e29e894eecf2ede6581fd67a7b"
PORT61_INTERFACE_COMMIT = "da5114a63c85bd9e7cedddc940a0f602829afdc2"
PORT61_INTEGRATION_PARENT = "2d114077a43f787c9d21056d3b8b0ac9426ac4c9"
PORT61_BUILD_COMMIT = "81e912f90ba150deea498e6caf505125f5c4515e"
PORT61_BUILD_INTEGRATION_COMMIT = "d6298f2c12627b8359ade3448b3bcf447589b07a"

PORT61_CANCEL_SHA256 = "2612eea17c83dc64f9f6579b59771aa7313e931bb0b7ea47118ad8c6512e1f68"
PORT61_CANCEL_SIZE = 135969
PORT61_CANCEL_END = "0036b970"

KEY_VIDEO = 13
G3X_KEY_VIDEO_BIT = 0x00000008

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

G3X_AUTOCONT_BUDGET_DEFAULT = 1

REQUIRED_CANCEL_PREREQS = [
    "G3X_MOVIE_RESTART_BUDGET",
    "G3X_MOVIE_AUTOCONT_UI",
    "G3X_MOVIE_AUTOCONT",
    "G3X_MOVIE_STATUS",
    "G3X_GUI_MENU",
    "G3X_GUI_SYNC",
    "G3X_GUI_DBUF",
    "G3X_GUI_NOOVERDRAW",
    "G3X_KBD_CHECK",
    "G3X_GUI_DIAG",
    "G3X_GUI_SHADOW2",
]

_BUILD_CACHE = {
    "default": False,
    "port59": False,
    "port60": False,
    "port61": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def ensure_build_default() -> None:
    bin_path = ROOT / "out/build-default/DISKBOOT.BIN"
    elf_path = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
    if _BUILD_CACHE["default"] and bin_path.is_file() and elf_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "tools/build_port41_full.py"),
                "--keep-stage",
                "--out-dir",
                str(ROOT / "out/build-default"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["default"] = True


def ensure_build_port59() -> None:
    bin_path = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
    elf_path = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
    if _BUILD_CACHE["port59"] and bin_path.is_file() and elf_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(BUILD_SCRIPT),
                "--no-overdraw",
                "--kbd-check",
                "--gui-diag",
                "--shadow2",
                "--gui-sync",
                "--gui-menu",
                "--gui-restore2",
                "--playback-menu",
                "--movie-status",
                "--movie-nolimit",
                "--movie-autocont",
                "--movie-autocont-ui",
                "--out-dir",
                str(ROOT / "out/port59-movie-combined"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port59"] = True


def ensure_build_port60() -> None:
    bin_path = ROOT / "out/port60-movie-restart-budget/DISKBOOT.BIN"
    elf_path = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/main.elf"
    if _BUILD_CACHE["port60"] and bin_path.is_file() and elf_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(BUILD_SCRIPT),
                "--no-overdraw",
                "--kbd-check",
                "--gui-diag",
                "--shadow2",
                "--gui-sync",
                "--gui-menu",
                "--gui-restore2",
                "--playback-menu",
                "--movie-status",
                "--movie-nolimit",
                "--movie-autocont",
                "--movie-autocont-ui",
                "--movie-restart-budget",
                "--out-dir",
                str(ROOT / "out/port60-movie-restart-budget"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port60"] = True


def ensure_build_port61() -> None:
    bin_path = ROOT / "out/port61-movie-session-cancel/DISKBOOT.BIN"
    elf_path = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "out/port61-movie-session-cancel/port61_movie_session_cancel_manifest.json"
    if (
        _BUILD_CACHE["port61"]
        and bin_path.is_file()
        and elf_path.is_file()
        and obj_path.is_file()
        and manifest_path.is_file()
    ):
        return
    if not (bin_path.is_file() and elf_path.is_file() and obj_path.is_file() and manifest_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(BUILD_SCRIPT),
                "--no-overdraw",
                "--kbd-check",
                "--gui-diag",
                "--shadow2",
                "--gui-sync",
                "--gui-menu",
                "--gui-restore2",
                "--playback-menu",
                "--movie-status",
                "--movie-nolimit",
                "--movie-autocont",
                "--movie-autocont-ui",
                "--movie-restart-budget",
                "--movie-session-cancel",
                "--out-dir",
                str(ROOT / "out/port61-movie-session-cancel"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port61"] = True


def setUpModule() -> None:
    ensure_build_default()
    ensure_build_port59()
    ensure_build_port60()
    ensure_build_port61()


class _HostPort61CancelHarness:
    """Compiles movie_rec.c, gui_diag.h, and gui_menu.c with G3X_MOVIE_SESSION_CANCEL=1."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port61_host_sm_")
        tmp = Path(self._tmpdir.name)

        (tmp / "conf.h").write_text("#ifndef CONF_H\n#define CONF_H\n/* stub conf.h */\n#endif\n", encoding="utf-8")
        (tmp / "keyboard.h").write_text(f"#ifndef KEYBOARD_H\n#define KEYBOARD_H\n#define KEY_VIDEO {KEY_VIDEO}\n#endif\n", encoding="utf-8")
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

        gui_menu_text = GUI_MENU_C.read_text(encoding="utf-8")
        menu_start = gui_menu_text.index("#if defined(G3X_GUI_FIX) && (G3X_GUI_FIX == 1)")
        menu_end = gui_menu_text.index("#if defined(G3X_PLAYBACK_MENU)", menu_start)
        gui_menu_redraw_slice = (
            "static int gui_menu_curr_item = 0;\n"
            "static int gui_menu_redraw = 0;\n"
            + gui_menu_text[menu_start:menu_end]
        )

        harness_c = tmp / "harness_stubs.c"
        harness_c.write_text(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "#include <string.h>\n"
            '#include "keyboard.h"\n'
            '#include "camera_info.h"\n'
            '#include "movie_status.h"\n'
            "#define G3X_GUI_DIAG_IMPLEMENTATION 1\n"
            "#define MEMINFO_H 1\n"
            "#define CAM_SCREEN_VERSION 1\n"
            "#define GUI_MODE_MENU 2\n"
            "#define FONT_WIDTH 16\n"
            "#define FONT_HEIGHT 32\n"
            "#define COLOR_BLACK 0\n"
            "#define COLOR_WHITE 1\n"
            "#define MAKE_COLOR(bg, fg) (((bg)&0xFF) | (((fg)&0xFF)<<8))\n"
            "typedef short coord;\n"
            "typedef unsigned short color;\n"
            "typedef struct { int free_block_max_size; } cam_meminfo;\n"
            "struct { int width; int height; int buffer_width; int disp_left; int disp_width; } camera_screen = {900, 600, 928, 0, 900};\n"
            "int active_bitmap_buffer = 0;\n"
            "char *bitmap_buffer[2] = {0, 0};\n"
            "volatile char *opacity_buffer[2] = {0, 0};\n"
            "int draw_test_guard(void) { return 1; }\n"
            "void draw_set_guard(void) {}\n"
            "void gui_redraw(int f) { (void)f; }\n"
            "int g3x_dbuf_shadow_is_allocated(void) { return 1; }\n"
            "void g3x_dbuf_shadow_ensure_allocated(void) {}\n"
            "int g3x_dbuf_shadow_restore(void) { return 1; }\n"
            "int g3x_dbuf_shadow_sync_restore(unsigned int idx) { (void)idx; return 1; }\n"
            "void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl) { (void)x1;(void)y1;(void)x2;(void)y2;(void)cl; }\n"
            "char host_last_drawn_line2[128];\n"
            "char host_last_drawn_line3[128];\n"
            "int draw_string(short x, short y, const char *s, unsigned short cl) {\n"
            "    (void)x; (void)cl;\n"
            "    if (y == camera_screen.height - 3 * FONT_HEIGHT) {\n"
            "        snprintf(host_last_drawn_line2, sizeof(host_last_drawn_line2), \"%s\", s ? s : \"\");\n"
            "    } else if (y == camera_screen.height - 4 * FONT_HEIGHT) {\n"
            "        snprintf(host_last_drawn_line3, sizeof(host_last_drawn_line3), \"%s\", s ? s : \"\");\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
            "void *exmem_alloc_cached(unsigned int p, unsigned int s, int u1, int u2) { (void)p;(void)s;(void)u1;(void)u2; return 0; }\n"
            "void *umalloc(unsigned int s) { return malloc(s); }\n"
            "void GetMemInfo(cam_meminfo *m) { if (m) m->free_block_max_size = 512 * 1024; }\n"
            "long get_tick_count(void) { return 0; }\n"
            '#include "gui_diag.h"\n'
            + gui_menu_redraw_slice
            + "\n"
            "cam_info_t camera_info = { { 0, 0, 1, 0, 0 } };\n"
            "long kbd_new_state[3] = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "long kbd_mod_state[3] = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "long physw_status[3]  = { 0xFFFFFFFFL, 0xFFFFFFFFL, 0xFFFFFFFFL };\n"
            "unsigned int host_press_calls = 0;\n"
            "unsigned int host_release_calls = 0;\n"
            "long host_last_key_arg = 0;\n"
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
            "void host_set_mode_play(int play) { camera_info.state.mode_play = play; }\n"
            "void host_set_gui_mode(int mode) { camera_info.state.gui_mode = mode; }\n"
            "void host_set_gui_mode_alt(int alt) {\n"
            "    camera_info.state.gui_mode_alt = alt;\n"
            "    camera_info.state.gui_mode_none = alt ? 0 : 1;\n"
            "}\n"
            "const char *host_get_movie_status_str(void) { return g3x_movie_status_str(); }\n"
            "const char *host_get_nolimit_status_str(void) { return g3x_movie_nolimit_status_str(); }\n"
            "const char *host_get_autocont_status_str(void) { return g3x_movie_autocont_status_str(); }\n"
            "const char *host_get_last_drawn_line2(void) { return host_last_drawn_line2; }\n"
            "const char *host_get_last_drawn_line3(void) { return host_last_drawn_line3; }\n"
            "void host_sim_kbd_tick_before_poll(int in_alt_mode) {\n"
            "    if (!in_alt_mode) {\n"
            "        physw_status[0] = kbd_new_state[0];\n"
            "    } else {\n"
            "        physw_status[0] = (kbd_new_state[0] & ~0x000533F9L) | (kbd_mod_state[0] & 0x000533F9L);\n"
            "    }\n"
            "}\n"
            "void host_simulate_bool_menu_toggle(void) {\n"
            "    int *p = g3x_movie_autocont_get_menu_bool_ptr();\n"
            "    *p = !(*p);\n"
            "    g3x_movie_autocont_menu_cb();\n"
            "}\n"
            f'#include "{MOVIE_REC_C}"\n'
            "void host_force_cancel_state_for_invariant_test(\n"
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

        so_path = tmp / "libport61_movie_session_cancel.so"
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
                "-DG3X_GUI_FIX=1",
                "-DG3X_GUI_DBUF=1",
                "-DG3X_GUI_NOOVERDRAW=1",
                "-DG3X_KBD_CHECK=1",
                "-DG3X_GUI_DIAG=1",
                "-DG3X_GUI_SHADOW2=1",
                "-DG3X_GUI_SYNC=1",
                "-DG3X_GUI_MENU=1",
                "-DG3X_GUI_RESTORE2=1",
                "-DG3X_PLAYBACK_MENU=1",
                "-DG3X_MOVIE_STATUS=1",
                "-DG3X_MOVIE_NOLIMIT=1",
                "-DG3X_MOVIE_AUTOCONT=1",
                "-DG3X_MOVIE_AUTOCONT_UI=1",
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
        self.lib.g3x_movie_autocont_menu_change.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.g3x_movie_autocont_menu_change.restype = ctypes.c_char_p
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
        self.lib.g3x_movie_autocont_cancel_menu_str.argtypes = []
        self.lib.g3x_movie_autocont_cancel_menu_str.restype = ctypes.c_char_p
        self.lib.g3x_movie_autocont_cancel_menu_change.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.g3x_movie_autocont_cancel_menu_change.restype = ctypes.c_char_p

        self.lib.g3x_movie_autocont_menu_cb.argtypes = []
        self.lib.g3x_movie_autocont_menu_cb.restype = None
        self.lib.g3x_movie_autocont_get_menu_bool_ptr.argtypes = []
        self.lib.g3x_movie_autocont_get_menu_bool_ptr.restype = ctypes.POINTER(ctypes.c_int)
        self.lib.host_simulate_bool_menu_toggle.argtypes = []
        self.lib.host_simulate_bool_menu_toggle.restype = None
        self.lib.host_force_cancel_state_for_invariant_test.argtypes = [
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.lib.host_force_cancel_state_for_invariant_test.restype = None
        self.lib.host_set_timer_polls_for_test.argtypes = [ctypes.c_uint]
        self.lib.host_set_timer_polls_for_test.restype = None
        self.lib.host_call_enter_confirmed_recording_for_test.argtypes = []
        self.lib.host_call_enter_confirmed_recording_for_test.restype = None

        self.lib.g3x_diag_format_line2.argtypes = [ctypes.c_char_p]
        self.lib.g3x_diag_format_line2.restype = None
        self.lib.g3x_playback_menu_diag_format.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        self.lib.g3x_playback_menu_diag_format.restype = None
        self.lib.gui_diag_draw.argtypes = []
        self.lib.gui_diag_draw.restype = None
        self.lib.gui_menu_needs_redraw.argtypes = []
        self.lib.gui_menu_needs_redraw.restype = ctypes.c_int
        self.lib.gui_menu_clear_redraw.argtypes = []
        self.lib.gui_menu_clear_redraw.restype = None

        self.lib.host_set_mode_play.argtypes = [ctypes.c_int]
        self.lib.host_set_mode_play.restype = None
        self.lib.host_set_gui_mode.argtypes = [ctypes.c_int]
        self.lib.host_set_gui_mode.restype = None
        self.lib.host_set_gui_mode_alt.argtypes = [ctypes.c_int]
        self.lib.host_set_gui_mode_alt.restype = None
        self.lib.host_get_movie_status_str.argtypes = []
        self.lib.host_get_movie_status_str.restype = ctypes.c_char_p
        self.lib.host_get_nolimit_status_str.argtypes = []
        self.lib.host_get_nolimit_status_str.restype = ctypes.c_char_p
        self.lib.host_get_autocont_status_str.argtypes = []
        self.lib.host_get_autocont_status_str.restype = ctypes.c_char_p
        self.lib.host_get_last_drawn_line2.argtypes = []
        self.lib.host_get_last_drawn_line2.restype = ctypes.c_char_p
        self.lib.host_get_last_drawn_line3.argtypes = []
        self.lib.host_get_last_drawn_line3.restype = ctypes.c_char_p
        self.lib.host_sim_kbd_tick_before_poll.argtypes = [ctypes.c_int]
        self.lib.host_sim_kbd_tick_before_poll.restype = None

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
        self.kbd_mod_state = (ctypes.c_long * 3).in_dll(self.lib, "kbd_mod_state")
        self.physw_status = (ctypes.c_long * 3).in_dll(self.lib, "physw_status")
        self.press_calls = ctypes.c_uint.in_dll(self.lib, "host_press_calls")
        self.release_calls = ctypes.c_uint.in_dll(self.lib, "host_release_calls")
        self.last_key_arg = ctypes.c_long.in_dll(self.lib, "host_last_key_arg")

        self.menu_open_count = ctypes.c_uint.in_dll(self.lib, "g3x_menu_open_count")
        self.conf_save_status = ctypes.c_int.in_dll(self.lib, "g3x_conf_save_status")
        self.sync_restore_count = ctypes.c_uint.in_dll(self.lib, "g3x_diag_sync_restore_count")
        self.poll_restore_count = ctypes.c_uint.in_dll(self.lib, "g3x_diag_poll_restore_count")
        self.playback_open_count = ctypes.c_uint.in_dll(self.lib, "g3x_playback_menu_open_count")
        self.playback_edit_count = ctypes.c_uint.in_dll(self.lib, "g3x_playback_menu_item_edit_count")

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
            self.kbd_mod_state[i] = 0xFFFFFFFF
            self.physw_status[i] = 0xFFFFFFFF
        self.press_calls.value = 0
        self.release_calls.value = 0
        self.last_key_arg.value = 0
        self.menu_open_count.value = 1
        self.conf_save_status.value = 3  # G3X_CONF_SAVE_OFF
        self.sync_restore_count.value = 0
        self.poll_restore_count.value = 0
        self.playback_open_count.value = 1
        self.playback_edit_count.value = 0
        self.lib.host_set_mode_play(0)
        self.lib.host_set_gui_mode(0)
        self.lib.host_set_gui_mode_alt(1)
        self.lib.g3x_movie_autocont_reset()

    def set_physical_video_button(self, pressed: bool) -> None:
        if pressed:
            self.kbd_new_state[0] &= ~G3X_KEY_VIDEO_BIT
        else:
            self.kbd_new_state[0] |= G3X_KEY_VIDEO_BIT

    def step(self, in_alt_mode: bool = False, run_nolimit: bool = True) -> int:
        self.lib.host_sim_kbd_tick_before_poll(1 if in_alt_mode else 0)
        if run_nolimit:
            self.lib.g3x_movie_nolimit_poll()
        self.lib.g3x_movie_autocont_poll()
        return self.state

    def menu_change(self, change: int) -> str:
        res = self.lib.g3x_movie_autocont_menu_change(change, 0)
        return res.decode("utf-8") if res else ""

    def budget_menu_change(self, change: int) -> str:
        res = self.lib.g3x_movie_autocont_budget_menu_change(change, 0)
        return res.decode("utf-8") if res else ""

    def cancel_menu_change(self, change: int) -> str:
        res = self.lib.g3x_movie_autocont_cancel_menu_change(change, 0)
        return res.decode("utf-8") if res else ""

    def format_line2(self) -> str:
        buf = ctypes.create_string_buffer(128)
        self.lib.g3x_diag_format_line2(buf)
        return buf.value.decode("utf-8")

    def format_line3(self) -> str:
        buf = ctypes.create_string_buffer(128)
        self.lib.g3x_playback_menu_diag_format(buf, 128)
        return buf.value.decode("utf-8")

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
    def nolimit_status_str(self) -> str:
        s = self.lib.host_get_nolimit_status_str()
        return s.decode("utf-8") if s else ""

    @property
    def menu_str(self) -> str:
        s = self.lib.g3x_movie_autocont_menu_str()
        return s.decode("utf-8") if s else ""

    @property
    def budget_menu_str(self) -> str:
        s = self.lib.g3x_movie_autocont_budget_menu_str()
        return s.decode("utf-8") if s else ""

    @property
    def cancel_menu_str(self) -> str:
        s = self.lib.g3x_movie_autocont_cancel_menu_str()
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
    def physw_video_pressed(self) -> bool:
        return (self.physw_status[0] & G3X_KEY_VIDEO_BIT) == 0

    @property
    def mod_video_pressed(self) -> bool:
        return (self.kbd_mod_state[0] & G3X_KEY_VIDEO_BIT) == 0


class TestPort61FlagGatesAndUnsupportedCombinations(unittest.TestCase):
    def test_session_cancel_profile_accepts_full_prerequisites_and_rejects_missing_prerequisites(self) -> None:
        expected_err = (
            "G3X_MOVIE_SESSION_CANCEL=1 requires G3X_MOVIE_RESTART_BUDGET=1 "
            "G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 "
            "G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 "
            "G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1"
        )
        full_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_SESSION_CANCEL=1"] + [
            f"-D{f}=1" for f in REQUIRED_CANCEL_PREREQS
        ]
        for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

        for missing in REQUIRED_CANCEL_PREREQS:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_SESSION_CANCEL=1"] + [
                    f"-D{f}=1" for f in REQUIRED_CANCEL_PREREQS if f != missing
                ]
                for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
                    res = subprocess.run(
                        ["cc", "-E", *c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

                make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_SESSION_CANCEL=1"] + [
                    f"{f}=1" for f in REQUIRED_CANCEL_PREREQS if f != missing
                ]
                for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                    res = subprocess.run(
                        ["make", "-f", str(mf), *make_args],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

    def test_session_cancel_profile_rejects_incompatible_flags_and_cli_combinations(self) -> None:
        full_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_SESSION_CANCEL=1"] + [
            f"-D{f}=1" for f in REQUIRED_CANCEL_PREREQS
        ]
        full_make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_SESSION_CANCEL=1"] + [
            f"{f}=1" for f in REQUIRED_CANCEL_PREREQS
        ]
        for bad_flag in ("G3X_CONF_SAVE", "FULL_HOOKS"):
            expected_msg = f"G3X_MOVIE_SESSION_CANCEL=1 is incompatible with {bad_flag}=1"
            for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
                res = subprocess.run(
                    ["cc", "-E", *full_c_flags, f"-D{bad_flag}=1", "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(expected_msg, res.stderr)

            for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                res = subprocess.run(
                    ["make", "-f", str(mf), *full_make_args, f"{bad_flag}=1"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(expected_msg, res.stderr)

        base_cli = [
            sys.executable,
            "-B",
            str(BUILD_SCRIPT),
            "--no-overdraw",
            "--kbd-check",
            "--gui-diag",
            "--shadow2",
            "--gui-sync",
            "--gui-menu",
            "--movie-status",
            "--movie-nolimit",
            "--movie-autocont",
            "--movie-autocont-ui",
            "--movie-restart-budget",
            "--movie-session-cancel",
        ]
        for bad_cli, exp_err in (
            (["--conf-save"], "G3X_MOVIE_SESSION_CANCEL=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_SESSION_CANCEL=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-nolimit-alone"], "G3X_MOVIE_SESSION_CANCEL=1 requires"),
            (["--movie-autocont-alone"], "G3X_MOVIE_SESSION_CANCEL=1 requires"),
            (["--movie-status-alone"], "G3X_MOVIE_SESSION_CANCEL=1 requires"),
            (["--playback-menu-alone"], "G3X_MOVIE_SESSION_CANCEL=1 requires"),
        ):
            res = subprocess.run([*base_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(exp_err, res.stderr)

        missing_budget_cli = [arg for arg in base_cli if arg != "--movie-restart-budget"]
        res = subprocess.run(missing_budget_cli, cwd=str(ROOT), capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("G3X_MOVIE_SESSION_CANCEL=1 requires G3X_MOVIE_RESTART_BUDGET=1", res.stderr)


class TestPort61SessionCancellationRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort61CancelHarness()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sm.close()

    def setUp(self) -> None:
        self.sm.reset()

    def _confirm_idle_enable_and_set_budget(self, budget: int = 1) -> None:
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.can_enable, 1)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(budget), 1)
        self.assertEqual(self.sm.restart_budget, budget)
        self.assertEqual(self.sm.budget_menu_str, str(budget))
        self.assertEqual(self.sm.menu_change(1), "Ready")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.cancel_menu_str, "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)

    def _start_deliberate_physical_recording(self, budget: int = 1, hold_polls_into_rec: int = 0) -> None:
        if not self.sm.enabled or self.sm.restart_budget != budget or self.sm.session_cancelled:
            self._confirm_idle_enable_and_set_budget(budget)
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        if hold_polls_into_rec == 0:
            self.sm.set_physical_video_button(False)

        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")
        self.assertEqual(self.sm.cancel_menu_str, "Active")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.restarts_remaining, budget)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)

        for _ in range(hold_polls_into_rec):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(False)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def _prime_in_bounds_reason3_metrics(self, clip_index: int = 1) -> None:
        self.sm.cur_frames.value = 28000 + clip_index * 100
        self.sm.stream_bytes.value = 0xFF000000 + clip_index * 4096
        self.sm.projected_size.value = 0xFF800000 + clip_index * 4096
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def _run_admitted_reason3_restart_to_confirmed_recording(
        self,
        expected_remaining_after_admission: int,
        expected_used_after_admission: int,
    ) -> None:
        self.sm.projected_size.value = 0x100000400 + expected_used_after_admission * 8192
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
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
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)

    def test_boot_defaults_and_cancellation_without_live_session_is_noop(self) -> None:
        # 1. Boot state: disabled, not session-cancelled, cancel action is a no-op
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.can_cancel_session, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")
        self.assertEqual(self.sm.cancel_menu_str, "Idle")
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
        self.assertEqual(self.sm.cancel_menu_change(1), "Idle")
        self.assertEqual(self.sm.cancel_menu_change(-1), "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.ui_status_str, "OFF")

        # 2. At confirmed idle when enabled (RDY) with budget 2, before a live session starts:
        #    cancellation without a live session is a strict no-op
        self._confirm_idle_enable_and_set_budget(2)
        self.assertEqual(self.sm.can_cancel_session, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
        self.assertEqual(self.sm.cancel_menu_change(1), "Idle")
        self.assertEqual(self.sm.cancel_menu_change(-1), "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.menu_str, "Ready")
        self.assertEqual(self.sm.restart_budget, 2)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 0)

        # 3. Unattributed 0 -> 1 recording transition (no live continuation session armed):
        #    cancellation without a live session is a strict no-op
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.can_cancel_session, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
        self.assertEqual(self.sm.cancel_menu_change(1), "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.ui_status_str, "RDY")

        # 4. After fault (STOP_FAULT) or budget exhaustion (DISARMED at RDY), no live session exists:
        #    cancellation is a strict no-op
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=1)
        self._prime_in_bounds_reason3_metrics(1)
        self.sm.stop_reason.value = 2  # SPACE_FULL (ineligible -> STOP_FAULT)
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.ui_status_str, "FLT")
        self.assertEqual(self.sm.can_cancel_session, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
        self.assertEqual(self.sm.cancel_menu_change(1), "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.ui_status_str, "FLT")

        self.sm.reset()
        self._start_deliberate_physical_recording(budget=1)
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(0, 1)
        self._prime_in_bounds_reason3_metrics(2)
        self.sm.projected_size.value = 0x100008000
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Exhausted
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.can_cancel_session, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
        self.assertEqual(self.sm.cancel_menu_change(1), "Idle")
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.ui_status_str, "RDY")

    def test_active_recording_cancellation_before_admission_preserves_clip_and_budget_and_prevents_restart(self) -> None:
        # Test cancelling during RECORDING across budgets 1, 2, 3 (both before any restart and after 1 consumed restart),
        # including during the initial 50-poll start-hold carry-over
        cases = (
            (1, 0, 0),
            (2, 0, 5),
            (2, 1, 0),
            (3, 1, 0),
            (3, 2, 0),
        )
        for budget, used_before_cancel, hold_polls in cases:
            with self.subTest(budget=budget, used_before_cancel=used_before_cancel, hold_polls=hold_polls):
                self.sm.reset()
                if hold_polls > 0 and used_before_cancel == 0:
                    self._confirm_idle_enable_and_set_budget(budget)
                    self.sm.movie_state.value = 0
                    self.sm.set_physical_video_button(True)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.sm.movie_state.value = 1
                    self.sm.max_frames.value = 54000
                    self.sm.cur_frames.value = 10
                    self.sm.stream_bytes.value = 1024 * 1024
                    self.sm.projected_size.value = 2 * 1024 * 1024
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                else:
                    self._start_deliberate_physical_recording(budget=budget)
                    for idx in range(1, used_before_cancel + 1):
                        self._prime_in_bounds_reason3_metrics(idx)
                        self._run_admitted_reason3_restart_to_confirmed_recording(
                            expected_remaining_after_admission=budget - idx,
                            expected_used_after_admission=idx,
                        )

                expected_rem = budget - used_before_cancel
                self._prime_in_bounds_reason3_metrics(used_before_cancel + 1)
                self.assertEqual(self.sm.can_cancel_session, 1)
                self.assertEqual(self.sm.cancel_menu_str, "Active")

                # Simulate an unowned modifier bit in kbd_mod_state[0] to prove cancellation never releases unowned keys
                self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
                press_before = self.sm.press_calls.value
                rel_before = self.sm.release_calls.value

                # Cancel via volatile GUI action ("Cancel further restarts")
                self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.can_cancel_session, 0)
                self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.enabled, 1)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                self.assertEqual(self.sm.reason_str, "CANC")
                self.assertEqual(self.sm.ui_status_str, "CANC")
                self.assertEqual(self.sm.menu_str, "Cancel")
                self.assertEqual(self.sm.cancel_menu_str, "Cancel")

                # Preserves configured allowance, remaining budget, and consumed attempts without refunding or resetting
                self.assertEqual(self.sm.restart_budget, budget)
                self.assertEqual(self.sm.restarts_remaining, expected_rem)
                self.assertEqual(self.sm.session_restarts_used, used_before_cancel)
                self.assertEqual(self.sm.attempt_admitted, 0)

                # Issues no stop command and releases zero unowned keys
                self.assertEqual(self.sm.movie_state.value, 1)
                self.assertEqual(self.sm.press_calls.value, press_before)
                self.assertEqual(self.sm.release_calls.value, rel_before)
                self.assertTrue(self.sm.mod_video_pressed)
                self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT

                # <ALT> OSD Line 2 and Line 3 display AC:CANC within 55 chars
                line2 = self.sm.format_line2()
                line3 = self.sm.format_line3()
                self.assertIn("SAVE:OFF MOV:REC LIM:OFF AC:CANC", line2)
                self.assertIn("SAVE:OFF MOV:REC LIM:OFF AC:CANC", line3)
                self.assertLessEqual(len(line2), 55)
                self.assertLessEqual(len(line3), 55)

                # Repeated cancellation is idempotent
                for _ in range(3):
                    self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
                    self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                    self.assertEqual(self.sm.cancel_menu_change(-1), "Cancel")
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.restart_budget, budget)
                    self.assertEqual(self.sm.restarts_remaining, expected_rem)
                    self.assertEqual(self.sm.session_restarts_used, used_before_cancel)

                # Active clip continues recording across polls with LIM:OFF
                for _ in range(hold_polls):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                if hold_polls > 0:
                    self.sm.set_physical_video_button(False)

                self.sm.max_frames.value = 54000
                for _ in range(10):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.movie_state.value, 1)
                    self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
                    self.assertEqual(self.sm.nolimit_status_str, "OFF")
                    self.assertEqual(self.sm.ui_status_str, "CANC")

                # When the active clip reaches an eligible Reason 3 stop (1 -> 2 -> 0),
                # cancellation prevents restart admission and preserves remaining/consumed budget
                self.sm.projected_size.value = 0x100008000
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.ui_status_str, "CANC")
                self.assertEqual(self.sm.restarts_remaining, expected_rem)
                self.assertEqual(self.sm.session_restarts_used, used_before_cancel)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.press_calls.value, press_before)

                self.sm.movie_state.value = 0
                for _ in range(60):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.ui_status_str, "CANC")
                    self.assertEqual(self.sm.menu_str, "Cancel")
                    self.assertEqual(self.sm.cancel_menu_str, "Cancel")
                    self.assertEqual(self.sm.restarts_remaining, expected_rem)
                    self.assertEqual(self.sm.session_restarts_used, used_before_cancel)
                    self.assertEqual(self.sm.press_calls.value, press_before)

    def test_pending_continuation_cancellation_owned_key_release_and_already_issued_start_completion(self) -> None:
        # Test cancellation in every pending continuation state (WAIT_IDLE, SETTLE, PRESSING, RELEASING, WAIT_CONFIRM)
        # with budget=3 after 1 attempt has been admitted (restarts_remaining == 2, session_restarts_used == 1).
        pending_phases = (
            "WAIT_IDLE",
            "SETTLE",
            "PRESSING",
            "RELEASING",
            "WAIT_CONFIRM",
        )
        for phase in pending_phases:
            with self.subTest(pending_phase=phase):
                self.sm.reset()
                # Unrelated key bit 4 (KEY_MENU = 0x10) held low to verify never touched
                self.sm.kbd_new_state[0] &= ~0x00000010
                self.sm.kbd_mod_state[0] &= ~0x00000010
                self._start_deliberate_physical_recording(budget=3)
                self._prime_in_bounds_reason3_metrics(1)

                self.sm.projected_size.value = 0x100000400
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                self.assertEqual(self.sm.restarts_remaining, 2)
                self.assertEqual(self.sm.session_restarts_used, 1)
                self.assertEqual(self.sm.attempt_admitted, 1)

                if phase != "WAIT_IDLE":
                    self.sm.movie_state.value = 0
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                if phase in ("PRESSING", "RELEASING", "WAIT_CONFIRM"):
                    for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                    self.assertEqual(self.sm.synth_owned, 1)
                if phase in ("RELEASING", "WAIT_CONFIRM"):
                    for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                    self.assertEqual(self.sm.synth_owned, 0)
                if phase == "WAIT_CONFIRM":
                    for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                    self.assertEqual(self.sm.synth_owned, 0)

                press_before = self.sm.press_calls.value
                rel_before = self.sm.release_calls.value

                if phase == "PRESSING":
                    # In PRESSING, synth_owned == 1: cancellation MUST release the continuation-owned KEY_VIDEO
                    self.assertEqual(self.sm.synth_owned, 1)
                    self.assertTrue(self.sm.mod_video_pressed)
                    self.assertTrue(self.sm.physw_video_pressed)
                    self.assertEqual(self.sm.cancel_menu_change(-1), "Cancel")
                    self.assertEqual(self.sm.synth_owned, 0)
                    self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                    self.assertFalse(self.sm.mod_video_pressed)
                    self.assertFalse(self.sm.physw_video_pressed)
                else:
                    # In WAIT_IDLE, SETTLE, RELEASING, WAIT_CONFIRM, synth_owned == 0:
                    # cancellation MUST NOT release unowned KEY_VIDEO modifier bits
                    self.assertEqual(self.sm.synth_owned, 0)
                    self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
                    self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                    self.assertEqual(self.sm.release_calls.value, rel_before)
                    self.assertTrue(self.sm.mod_video_pressed)
                    self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT

                # Unrelated key bit 4 untouched; pending continuation cancelled; budget counters preserved without refund
                self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                self.assertEqual(self.sm.ui_status_str, "CANC")
                self.assertEqual(self.sm.menu_str, "Cancel")
                self.assertEqual(self.sm.cancel_menu_str, "Cancel")
                self.assertEqual(self.sm.restart_budget, 3)
                self.assertEqual(self.sm.restarts_remaining, 2)
                self.assertEqual(self.sm.session_restarts_used, 1)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.timer_polls, 0)

                if phase in ("WAIT_IDLE", "SETTLE"):
                    # Cancelled before synthetic press: zero synthetic key presses ever issued
                    self.assertEqual(press_before, 0)
                    self.sm.movie_state.value = 0
                    for _ in range(60):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.press_calls.value, 0)
                        self.assertEqual(self.sm.session_cancelled, 1)
                else:
                    # Cancelled in PRESSING, RELEASING, or WAIT_CONFIRM after synthetic start pulse was already issued:
                    # if that already-issued start completes in firmware (movie_state: 0 -> 1), the new clip may
                    # complete with LIM:OFF, does not clear cancellation, and receives NO further automatic continuation!
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.sm.movie_state.value = 1
                    self.sm.max_frames.value = 54000
                    self.sm.cur_frames.value = 50
                    self.sm.stream_bytes.value = 4 * 1024 * 1024
                    self.sm.projected_size.value = 8 * 1024 * 1024
                    for _ in range(10):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.movie_state.value, 1)
                        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
                        self.assertEqual(self.sm.nolimit_status_str, "OFF")
                        self.assertEqual(self.sm.session_cancelled, 1)
                        self.assertEqual(self.sm.ui_status_str, "CANC")
                        self.assertEqual(self.sm.restarts_remaining, 2)
                        self.assertEqual(self.sm.session_restarts_used, 1)
                        self.assertEqual(self.sm.press_calls.value, press_before)

                    # When this synthetically started clip reaches its 4 GiB Reason 3 stop, it receives NO continuation
                    self.sm.cur_frames.value = 29000
                    self.sm.stream_bytes.value = 0xFF800000
                    self.sm.projected_size.value = 0x100008000
                    self.sm.stop_reason.value = 3
                    self.sm.movie_state.value = 2
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.sm.movie_state.value = 0
                    for _ in range(60):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.session_cancelled, 1)
                        self.assertEqual(self.sm.ui_status_str, "CANC")
                        self.assertEqual(self.sm.restarts_remaining, 2)
                        self.assertEqual(self.sm.session_restarts_used, 1)
                        self.assertEqual(self.sm.press_calls.value, press_before)

    def test_physical_stop_precedence_over_session_cancellation(self) -> None:
        # 1. Same-poll race Type A: physical KEY_VIDEO pressed in kbd_new_state[0] BEFORE cancel_session() is called
        #    (matches my_kbd_read_keys() hardware order: kbd_fetch_data -> gui_menu_kbd_process -> autocont_poll)
        for phase in ("RECORDING", "WAIT_IDLE", "SETTLE", "PRESSING", "RELEASING", "WAIT_CONFIRM"):
            with self.subTest(same_poll_phys_before_cancel=phase):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=2)
                self._prime_in_bounds_reason3_metrics(1)
                if phase != "RECORDING":
                    self.sm.projected_size.value = 0x100000400
                    self.sm.stop_reason.value = 3
                    if phase == "WAIT_IDLE":
                        self.sm.movie_state.value = 2
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                    else:
                        self.sm.movie_state.value = 0
                        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                        if phase in ("PRESSING", "RELEASING", "WAIT_CONFIRM"):
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                        if phase in ("RELEASING", "WAIT_CONFIRM"):
                            for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                        if phase == "WAIT_CONFIRM":
                            for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)

                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.can_cancel_session, 0)
                self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 0)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                self.assertEqual(self.sm.cancel_latched, 1)
                self.assertEqual(self.sm.session_cancelled, 0)
                self.assertEqual(self.sm.synth_owned, 0)

        # 2. Physical stop on a LATER poll while a session-cancelled clip is still recording (cur_state == 1)
        #    or stopping (cur_state in 2..4): physical-stop precedence sets PHYS_STOP and cancel_latched=1
        #    while PRESERVING the session-cancelled latch (session_cancelled == 1) and keeping cancellation
        #    visible through the status display until a new deliberate physical start after confirmed idle!
        for stop_state in (1, 2, 3, 4):
            with self.subTest(post_cancel_phys_stop_state=stop_state):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=2)
                self._prime_in_bounds_reason3_metrics(1)
                self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)

                self.sm.movie_state.value = stop_state
                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                self.assertEqual(self.sm.reason_str, "STOP")
                self.assertEqual(self.sm.cancel_latched, 1)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.enabled, 1)
                self.assertEqual(self.sm.ui_status_str, "CANC")
                self.assertEqual(self.sm.menu_str, "Cancel")
                self.assertEqual(self.sm.cancel_menu_str, "Cancel")
                self.assertIn("AC:CANC", self.sm.format_line2())
                self.assertIn("AC:CANC", self.sm.format_line3())

    def _assert_cancelled_post_disarm_invariants_and_qualifying_physical_start_clear(
        self,
        expected_reason: int,
        expected_budget: int = 3,
        expected_remaining: int = 2,
        expected_used: int = 1,
    ) -> None:
        # 1. Session-cancelled latch and budget counters remain preserved; cancellation stays visible in UI
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.disarm_reason, expected_reason)
        if expected_reason == G3X_AUTOCONT_REASON_PHYS_STOP:
            self.assertEqual(self.sm.cancel_latched, 1)
            self.assertEqual(self.sm.reason_str, "STOP")
        elif expected_reason == G3X_AUTOCONT_REASON_PLAYBACK:
            self.assertEqual(self.sm.reason_str, "PLAY")
        elif expected_reason == G3X_AUTOCONT_REASON_INVALID_STATE:
            self.assertEqual(self.sm.reason_str, "STATE")
        elif expected_reason == G3X_AUTOCONT_REASON_TIMEOUT:
            self.assertEqual(self.sm.reason_str, "TMO")
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.menu_str, "Cancel")
        self.assertEqual(self.sm.cancel_menu_str, "Cancel")
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertIn("AC:CANC", line2)
        self.assertIn("AC:CANC", line3)
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)
        self.assertEqual(self.sm.restart_budget, expected_budget)
        self.assertEqual(self.sm.restarts_remaining, expected_remaining)
        self.assertEqual(self.sm.session_restarts_used, expected_used)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.synth_owned, 0)

        # 2. Repeated cancellation and GUI edits immediately after the disarm path cannot clear cancellation
        for edit_fn in (
            lambda: self.sm.lib.g3x_movie_autocont_cancel_session(),
            lambda: self.sm.cancel_menu_change(1),
            lambda: self.sm.cancel_menu_change(-1),
            lambda: self.sm.menu_change(1),
            lambda: self.sm.menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(0),
            lambda: self.sm.lib.host_simulate_bool_menu_toggle(),
            lambda: self.sm.budget_menu_change(1),
            lambda: self.sm.budget_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_restart_budget(1),
        ):
            edit_fn()
            self.assertEqual(self.sm.session_cancelled, 1)
            self.assertEqual(self.sm.enabled, 1)
            self.assertEqual(self.sm.disarm_reason, expected_reason)
            self.assertEqual(self.sm.ui_status_str, "CANC")
            self.assertEqual(self.sm.menu_str, "Cancel")
            self.assertEqual(self.sm.cancel_menu_str, "Cancel")
            self.assertEqual(self.sm.restart_budget, expected_budget)
            self.assertEqual(self.sm.restarts_remaining, expected_remaining)
            self.assertEqual(self.sm.session_restarts_used, expected_used)

        # 3. Recover to shooting mode and test that an unconfirmed-idle physical press (on the first IDLE poll)
        #    cannot latch a start press or clear cancellation
        self.sm.lib.host_set_mode_play(0)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # First IDLE poll (clears cancel_latched if set)
        self.assertEqual(self.sm.cancel_latched, 0)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")

        # 4. At confirmed idle (second consecutive IDLE poll), repeated cancellation, GUI edits, and synthetic
        #    starts still cannot clear cancellation or alter budget counters
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.can_cancel_session, 0)
        for edit_fn in (
            lambda: self.sm.lib.g3x_movie_autocont_cancel_session(),
            lambda: self.sm.cancel_menu_change(1),
            lambda: self.sm.cancel_menu_change(-1),
            lambda: self.sm.menu_change(1),
            lambda: self.sm.menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(0),
            lambda: self.sm.lib.host_simulate_bool_menu_toggle(),
            lambda: self.sm.budget_menu_change(1),
            lambda: self.sm.budget_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_restart_budget(1),
        ):
            edit_fn()
            self.assertEqual(self.sm.session_cancelled, 1)
            self.assertEqual(self.sm.enabled, 1)
            self.assertEqual(self.sm.ui_status_str, "CANC")
            self.assertEqual(self.sm.menu_str, "Cancel")
            self.assertEqual(self.sm.cancel_menu_str, "Cancel")
            self.assertEqual(self.sm.restart_budget, expected_budget)
            self.assertEqual(self.sm.restarts_remaining, expected_remaining)
            self.assertEqual(self.sm.session_restarts_used, expected_used)

        # Synthetic / unattributed 0 -> 1 start and direct enter_confirmed_recording cannot clear cancellation
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.sm.lib.host_call_enter_confirmed_recording_for_test()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.restarts_remaining, expected_remaining)
        self.assertEqual(self.sm.session_restarts_used, expected_used)

        # Unconfirmed-idle physical press on Poll 1 after 1 -> 0 cannot clear cancellation
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")

        # 5. Return to confirmed IDLE and perform a qualifying new deliberate physical start:
        #    clears session_cancelled to 0 and begins a fresh session with full budget
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)  # Still latched at IDLE until 0 -> 1
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")
        self.assertEqual(self.sm.cancel_menu_str, "Active")
        self.assertEqual(self.sm.restart_budget, expected_budget)
        self.assertEqual(self.sm.restarts_remaining, expected_budget)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)

    def test_session_cancelled_latch_preserved_across_phys_stop_playback_invalid_state_and_timeout_disarm_paths(self) -> None:
        # Part 1: Normal post-cancel runtime disarm paths from G3X_AUTOCONT_DISARMED after cancel_menu_change(1)
        post_cancel_scenarios = (
            ("POST_CANCEL_PHYS_STOP_REC", G3X_AUTOCONT_REASON_PHYS_STOP),
            ("POST_CANCEL_PHYS_STOP_STOPPING", G3X_AUTOCONT_REASON_PHYS_STOP),
            ("POST_CANCEL_PHYS_STOP_RACE_PLAYBACK", G3X_AUTOCONT_REASON_PHYS_STOP),
            ("POST_CANCEL_PHYS_STOP_RACE_INVALID_STATE", G3X_AUTOCONT_REASON_PHYS_STOP),
            ("POST_CANCEL_PLAYBACK_REC", G3X_AUTOCONT_REASON_PLAYBACK),
            ("POST_CANCEL_PLAYBACK_IDLE", G3X_AUTOCONT_REASON_PLAYBACK),
            ("POST_CANCEL_INVALID_STATE_HIGH", G3X_AUTOCONT_REASON_INVALID_STATE),
            ("POST_CANCEL_INVALID_STATE_NEG", G3X_AUTOCONT_REASON_INVALID_STATE),
        )
        for name, exp_reason in post_cancel_scenarios:
            with self.subTest(post_cancel_disarm=name):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=3)
                self._prime_in_bounds_reason3_metrics(1)
                self._run_admitted_reason3_restart_to_confirmed_recording(
                    expected_remaining_after_admission=2,
                    expected_used_after_admission=1,
                )
                self._prime_in_bounds_reason3_metrics(2)
                self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                self.assertEqual(self.sm.session_cancelled, 1)

                if name == "POST_CANCEL_PHYS_STOP_REC":
                    self.sm.movie_state.value = 1
                    self.sm.set_physical_video_button(True)
                elif name == "POST_CANCEL_PHYS_STOP_STOPPING":
                    self.sm.movie_state.value = 2
                    self.sm.set_physical_video_button(True)
                elif name == "POST_CANCEL_PHYS_STOP_RACE_PLAYBACK":
                    self.sm.movie_state.value = 1
                    self.sm.lib.host_set_mode_play(1)
                    self.sm.set_physical_video_button(True)
                elif name == "POST_CANCEL_PHYS_STOP_RACE_INVALID_STATE":
                    self.sm.movie_state.value = 99
                    self.sm.set_physical_video_button(True)
                elif name == "POST_CANCEL_PLAYBACK_REC":
                    self.sm.movie_state.value = 1
                    self.sm.lib.host_set_mode_play(1)
                elif name == "POST_CANCEL_PLAYBACK_IDLE":
                    self.sm.movie_state.value = 0
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.sm.lib.host_set_mode_play(1)
                elif name == "POST_CANCEL_INVALID_STATE_HIGH":
                    self.sm.movie_state.value = 99
                elif name == "POST_CANCEL_INVALID_STATE_NEG":
                    self.sm.movie_state.value = -1

                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                # Verify repeated poll in the disarm condition does not clobber disarm_reason or clear latch
                if name == "POST_CANCEL_PHYS_STOP_RACE_PLAYBACK":
                    self.sm.set_physical_video_button(False)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                self._assert_cancelled_post_disarm_invariants_and_qualifying_physical_start_clear(
                    expected_reason=exp_reason,
                    expected_budget=3,
                    expected_remaining=2,
                    expected_used=1,
                )

        # Part 2: Compiled-controller active/pending state disarm paths across PHYS_STOP, PLAYBACK,
        #         INVALID_STATE, and TIMEOUT while session_cancelled == 1, testing both synth_owned in {0, 1}
        in_state_disarm_cases = (
            # (label, state, movie_state, timer_polls, mode_play, phys_pressed, expected_reason)
            ("RECORDING_PHYS_STOP", G3X_AUTOCONT_RECORDING, 1, 0, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("WAIT_IDLE_PHYS_STOP", G3X_AUTOCONT_WAIT_IDLE, 2, 10, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("SETTLE_PHYS_STOP", G3X_AUTOCONT_SETTLE, 0, 10, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("PRESSING_PHYS_STOP", G3X_AUTOCONT_PRESSING, 0, 4, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("RELEASING_PHYS_STOP", G3X_AUTOCONT_RELEASING, 0, 4, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("WAIT_CONFIRM_PHYS_STOP", G3X_AUTOCONT_WAIT_CONFIRM, 0, 10, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("RACE_PLAYBACK_PHYS_STOP", G3X_AUTOCONT_PRESSING, 0, 4, 1, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("RACE_INVALID_PHYS_STOP", G3X_AUTOCONT_PRESSING, 99, 4, 0, True, G3X_AUTOCONT_REASON_PHYS_STOP),
            ("RECORDING_PLAYBACK", G3X_AUTOCONT_RECORDING, 1, 0, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("WAIT_IDLE_PLAYBACK", G3X_AUTOCONT_WAIT_IDLE, 2, 10, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("SETTLE_PLAYBACK", G3X_AUTOCONT_SETTLE, 0, 10, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("PRESSING_PLAYBACK", G3X_AUTOCONT_PRESSING, 0, 4, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("RELEASING_PLAYBACK", G3X_AUTOCONT_RELEASING, 0, 4, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("WAIT_CONFIRM_PLAYBACK", G3X_AUTOCONT_WAIT_CONFIRM, 0, 10, 1, False, G3X_AUTOCONT_REASON_PLAYBACK),
            ("WAIT_IDLE_INVALID_STATE", G3X_AUTOCONT_WAIT_IDLE, 1, 10, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("SETTLE_INVALID_STATE", G3X_AUTOCONT_SETTLE, 2, 10, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("PRESSING_INVALID_STATE", G3X_AUTOCONT_PRESSING, 2, 4, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("RELEASING_INVALID_STATE", G3X_AUTOCONT_RELEASING, 2, 4, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("WAIT_CONFIRM_INVALID_STATE", G3X_AUTOCONT_WAIT_CONFIRM, 2, 10, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("DEFAULT_ENUM_INVALID_STATE", 99, 0, 0, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("OUT_OF_RANGE_REC_INVALID_STATE", G3X_AUTOCONT_RECORDING, 99, 0, 0, False, G3X_AUTOCONT_REASON_INVALID_STATE),
            ("WAIT_IDLE_TIMEOUT", G3X_AUTOCONT_WAIT_IDLE, 2, 1, 0, False, G3X_AUTOCONT_REASON_TIMEOUT),
            ("WAIT_CONFIRM_TIMEOUT", G3X_AUTOCONT_WAIT_CONFIRM, 0, 1, 0, False, G3X_AUTOCONT_REASON_TIMEOUT),
        )
        for label, fstate, mstate, tpolls, mplay, phys_btn, exp_reason in in_state_disarm_cases:
            for owned in (0, 1):
                with self.subTest(in_state_disarm=label, synth_owned=owned):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=3)
                    # Hold unrelated key bit 4 (0x10) low to verify it is never touched
                    self.sm.kbd_new_state[0] &= ~0x00000010
                    self.sm.kbd_mod_state[0] &= ~0x00000010
                    # Set KEY_VIDEO low in kbd_mod_state[0] and physw_status[0] to test ownership release rule
                    self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
                    self.sm.physw_status[0] &= ~G3X_KEY_VIDEO_BIT
                    rel_before = self.sm.release_calls.value
                    press_before = self.sm.press_calls.value

                    self.sm.movie_state.value = mstate
                    self.sm.lib.host_set_mode_play(mplay)
                    self.sm.set_physical_video_button(phys_btn)
                    self.sm.lib.host_force_cancel_state_for_invariant_test(
                        fstate, 3, 2, 1, 1, owned, 1
                    )
                    self.sm.lib.host_set_timer_polls_for_test(tpolls)

                    self.assertEqual(self.sm.step(in_alt_mode=True), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.press_calls.value, press_before)
                    self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)
                    if owned == 1:
                        self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                        self.assertFalse(self.sm.mod_video_pressed)
                        if not phys_btn:
                            self.assertFalse(self.sm.physw_video_pressed)
                    else:
                        self.assertEqual(self.sm.release_calls.value, rel_before)
                        self.assertTrue(self.sm.mod_video_pressed)
                        self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT
                    self.sm.kbd_new_state[0] |= 0x00000010
                    self.sm.kbd_mod_state[0] |= 0x00000010

                    self._assert_cancelled_post_disarm_invariants_and_qualifying_physical_start_clear(
                        expected_reason=exp_reason,
                        expected_budget=3,
                        expected_remaining=2,
                        expected_used=1,
                    )

    def test_only_deliberate_physical_start_after_confirmed_idle_clears_cancellation_and_starts_fresh_session(self) -> None:
        # Start session with budget 3, consume 1 restart (remaining=2, used=1), then cancel during Clip 2
        self._start_deliberate_physical_recording(budget=3)
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(
            expected_remaining_after_admission=2,
            expected_used_after_admission=1,
        )
        self._prime_in_bounds_reason3_metrics(2)
        self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 1)

        # 1. GUI edits during active recording (movie_state == 1) cannot clear cancellation or alter counters
        for edit_fn in (
            lambda: self.sm.menu_change(1),
            lambda: self.sm.menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(0),
            lambda: self.sm.lib.host_simulate_bool_menu_toggle(),
            lambda: self.sm.budget_menu_change(1),
            lambda: self.sm.budget_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_restart_budget(1),
            lambda: self.sm.cancel_menu_change(1),
            lambda: self.sm.cancel_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_cancel_session(),
        ):
            edit_fn()
            self.assertEqual(self.sm.session_cancelled, 1)
            self.assertEqual(self.sm.enabled, 1)
            self.assertEqual(self.sm.ui_status_str, "CANC")
            self.assertEqual(self.sm.menu_str, "Cancel")
            self.assertEqual(self.sm.cancel_menu_str, "Cancel")
            self.assertEqual(self.sm.restart_budget, 3)
            self.assertEqual(self.sm.restarts_remaining, 2)
            self.assertEqual(self.sm.session_restarts_used, 1)

        # 2. Clip 2 finishes to IDLE (1 -> 0): physical KEY_VIDEO press on the FIRST unconfirmed idle poll (prev_state == 1)
        #    cannot latch an idle start press or clear cancellation on 0 -> 1
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Poll 1 at IDLE (prev_state was 1, not confirmed idle)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 1)

        # 3. Return to confirmed IDLE (two consecutive polls at movie_state == 0):
        #    GUI edits at confirmed idle STILL cannot clear cancellation or reset preserved budget counters
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle
        self.assertEqual(self.sm.can_enable, 0)
        for edit_fn in (
            lambda: self.sm.menu_change(1),
            lambda: self.sm.menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(1),
            lambda: self.sm.lib.g3x_movie_autocont_set_enabled(0),
            lambda: self.sm.lib.host_simulate_bool_menu_toggle(),
            lambda: self.sm.budget_menu_change(1),
            lambda: self.sm.budget_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_set_restart_budget(1),
            lambda: self.sm.cancel_menu_change(1),
            lambda: self.sm.cancel_menu_change(-1),
            lambda: self.sm.lib.g3x_movie_autocont_cancel_session(),
        ):
            edit_fn()
            self.assertEqual(self.sm.session_cancelled, 1)
            self.assertEqual(self.sm.enabled, 1)
            self.assertEqual(self.sm.ui_status_str, "CANC")
            self.assertEqual(self.sm.menu_str, "Cancel")
            self.assertEqual(self.sm.cancel_menu_str, "Cancel")
            self.assertEqual(self.sm.restart_budget, 3)
            self.assertEqual(self.sm.restarts_remaining, 2)
            self.assertEqual(self.sm.session_restarts_used, 1)

        # 4. Synthetic start (0 -> 1 without physical press, or defensive enter_confirmed_recording call)
        #    cannot clear cancellation
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.sm.lib.host_call_enter_confirmed_recording_for_test()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 1)

        # 5. Return to confirmed IDLE, perform a NEW deliberate physical start -> clears cancellation
        #    and begins a fresh session with restarts_remaining = 3 and session_restarts_used = 0
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle

        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        # While still at IDLE before 0 -> 1, cancellation remains latched
        self.assertEqual(self.sm.session_cancelled, 1)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")
        self.assertEqual(self.sm.cancel_menu_str, "Active")
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.restarts_remaining, 3)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)

        # Verify the fresh session admits automatic continuation normally
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(
            expected_remaining_after_admission=2,
            expected_used_after_admission=1,
        )

    def test_live_menu_redraw_and_defensive_state_machine_cancellation_guards(self) -> None:
        self.sm.lib.host_set_gui_mode(2)  # GUI_MODE_MENU
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 0)

        self._start_deliberate_physical_recording(budget=2)
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 0)

        # Cancelling session triggers live menu redraw via cur_ac_sig bit 23 and disarm_reason
        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 1)
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 0)

        # Defensive state-machine guards: if state is forced to 1..6 while session_cancelled == 1,
        # poll() immediately disarms to SESSION_CANCEL, preserves active clip, and releases only owned keys
        for fstate, valid_mstate in (
            (G3X_AUTOCONT_RECORDING, 1),
            (G3X_AUTOCONT_WAIT_IDLE, 2),
            (G3X_AUTOCONT_SETTLE, 0),
            (G3X_AUTOCONT_PRESSING, 0),
            (G3X_AUTOCONT_RELEASING, 0),
            (G3X_AUTOCONT_WAIT_CONFIRM, 0),
        ):
            for owned in (0, 1):
                with self.subTest(forced_state=fstate, owned=owned):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=2)
                    self.sm.movie_state.value = valid_mstate
                    self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
                    self.sm.physw_status[0] &= ~G3X_KEY_VIDEO_BIT
                    rel_before = self.sm.release_calls.value
                    press_before = self.sm.press_calls.value
                    self.sm.lib.host_force_cancel_state_for_invariant_test(
                        fstate, 2, 1, 1, 1, owned, 1
                    )
                    self.sm.lib.host_set_timer_polls_for_test(10)
                    self.assertEqual(self.sm.step(in_alt_mode=True), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.synth_owned, 0)
                    self.assertEqual(self.sm.press_calls.value, press_before)
                    if owned == 1:
                        self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                    else:
                        self.assertEqual(self.sm.release_calls.value, rel_before)
                        self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT

    def _prime_in_bounds_reason4_metrics(self, max_f: int = 1800, cur_f: int = 900) -> None:
        self.sm.max_frames.value = max_f
        self.sm.cur_frames.value = cur_f
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_RECORDING)

    def test_cancellation_and_admission_orderings_across_reason3_and_reason4_stops(self) -> None:
        # Exercise both cancellation/admission orderings across Reason 3 (4 GiB size cap) and
        # Reason 4 (frame cap) stops, for both 1 -> 2 (WAIT_IDLE) and 1 -> 0 (SETTLE) transitions:
        #   - Ordering A1: Cancellation during live RECORDING (cur_state == 1) before stop transition
        #   - Ordering A2: Same-tick cancellation right as cur_state becomes 2 or 0 BEFORE g3x_movie_autocont_poll()
        #                  runs (matches my_kbd_read_keys() hardware order: gui_menu_kbd_process -> autocont_poll)
        #   - Ordering A3: In-poll RECORDING cancellation guard evaluated BEFORE stop-onset admission when cur_state != 1
        #   - Ordering B1: Stop-onset admission in g3x_movie_autocont_poll() BEFORE cancellation in pending continuation
        #                  (WAIT_IDLE / SETTLE)
        #   - Ordering B2: Stop-onset admission in g3x_movie_autocont_poll() BEFORE cancellation during an outstanding
        #                  restart attempt (PRESSING / RELEASING / WAIT_CONFIRM)
        for reason in (3, 4):
            for stop_target_state, expected_pending_state in (
                (2, G3X_AUTOCONT_WAIT_IDLE),
                (0, G3X_AUTOCONT_SETTLE),
            ):
                run_nolimit = reason == 3
                with self.subTest(ordering="A1_PRE_STOP_CANCEL", reason=reason, stop_state=stop_target_state):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=2)
                    if reason == 3:
                        self._prime_in_bounds_reason3_metrics(1)
                    else:
                        self._prime_in_bounds_reason4_metrics(1800, 900)
                    press_before = self.sm.press_calls.value
                    rel_before = self.sm.release_calls.value

                    # Cancel before stop-onset admission
                    self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 1)
                    self.assertEqual(self.sm.movie_state.value, 1)
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 0)
                    self.assertEqual(self.sm.attempt_admitted, 0)

                    # Trigger eligible stop transition -> admission is prevented, zero allowance consumed
                    if reason == 3:
                        self.sm.projected_size.value = 0x100000400
                        self.sm.stop_reason.value = 3
                    else:
                        self.sm.max_frames.value = 1800
                        self.sm.cur_frames.value = 1800
                        self.sm.stop_reason.value = 4
                    self.sm.movie_state.value = stop_target_state
                    self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                    self.assertEqual(self.sm.ui_status_str, "CANC")
                    self.assertEqual(self.sm.restart_budget, 2)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 0)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.press_calls.value, press_before)
                    self.assertEqual(self.sm.release_calls.value, rel_before)

                with self.subTest(ordering="A2_SAME_TICK_CANCEL_BEFORE_POLL", reason=reason, stop_state=stop_target_state):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=2)
                    if reason == 3:
                        self._prime_in_bounds_reason3_metrics(1)
                        self.sm.projected_size.value = 0x100000400
                        self.sm.stop_reason.value = 3
                    else:
                        self._prime_in_bounds_reason4_metrics(1800, 900)
                        self.sm.max_frames.value = 1800
                        self.sm.cur_frames.value = 1800
                        self.sm.stop_reason.value = 4
                    # On the same 10 ms tick, mr_rec_state changes to 2 or 0 and gui_menu_kbd_process()
                    # dispatches cancel_menu_change(±1) BEFORE g3x_movie_autocont_poll() runs
                    self.sm.movie_state.value = stop_target_state
                    self.assertEqual(self.sm.can_cancel_session, 1)
                    self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 0)

                    # Now g3x_movie_autocont_poll() runs on that same tick: admission does NOT run
                    self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 0)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.press_calls.value, 0)

                with self.subTest(ordering="A3_IN_POLL_CANCEL_BEFORE_ADMISSION", reason=reason, stop_state=stop_target_state):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=2)
                    if reason == 3:
                        self._prime_in_bounds_reason3_metrics(1)
                        self.sm.projected_size.value = 0x100000400
                        self.sm.stop_reason.value = 3
                    else:
                        self._prime_in_bounds_reason4_metrics(1800, 900)
                        self.sm.max_frames.value = 1800
                        self.sm.cur_frames.value = 1800
                        self.sm.stop_reason.value = 4
                    self.sm.movie_state.value = stop_target_state
                    self.sm.lib.host_force_cancel_state_for_invariant_test(
                        G3X_AUTOCONT_RECORDING, 2, 2, 0, 0, 0, 1
                    )
                    self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 0)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.press_calls.value, 0)

                with self.subTest(ordering="B1_ADMISSION_BEFORE_PENDING_CANCEL", reason=reason, stop_state=stop_target_state):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=2)
                    if reason == 3:
                        self._prime_in_bounds_reason3_metrics(1)
                        self.sm.projected_size.value = 0x100000400
                        self.sm.stop_reason.value = 3
                    else:
                        self._prime_in_bounds_reason4_metrics(1800, 900)
                        self.sm.max_frames.value = 1800
                        self.sm.cur_frames.value = 1800
                        self.sm.stop_reason.value = 4
                    self.sm.movie_state.value = stop_target_state

                    # Admission runs FIRST in g3x_movie_autocont_poll(): consumes 1 unit of budget
                    self.assertEqual(self.sm.step(run_nolimit=run_nolimit), expected_pending_state)
                    self.assertEqual(self.sm.attempt_admitted, 1)
                    self.assertEqual(self.sm.restarts_remaining, 1)
                    self.assertEqual(self.sm.session_restarts_used, 1)
                    self.assertEqual(self.sm.last_stop_reason, reason)

                    # Cancellation runs AFTER admission during pending continuation (WAIT_IDLE / SETTLE):
                    # cancels continuation, clears attempt_admitted, and preserves remaining=1, used=1 without refund
                    self.assertEqual(self.sm.cancel_menu_change(-1), "Cancel")
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.restart_budget, 2)
                    self.assertEqual(self.sm.restarts_remaining, 1)
                    self.assertEqual(self.sm.session_restarts_used, 1)
                    self.assertEqual(self.sm.press_calls.value, 0)

                for outstanding_state in ("PRESSING", "RELEASING", "WAIT_CONFIRM"):
                    with self.subTest(
                        ordering="B2_ADMISSION_BEFORE_OUTSTANDING_ATTEMPT_CANCEL",
                        reason=reason,
                        stop_state=stop_target_state,
                        outstanding_state=outstanding_state,
                    ):
                        self.sm.reset()
                        self._start_deliberate_physical_recording(budget=2)
                        if reason == 3:
                            self._prime_in_bounds_reason3_metrics(1)
                            self.sm.projected_size.value = 0x100000400
                            self.sm.stop_reason.value = 3
                        else:
                            self._prime_in_bounds_reason4_metrics(1800, 900)
                            self.sm.max_frames.value = 1800
                            self.sm.cur_frames.value = 1800
                            self.sm.stop_reason.value = 4
                        self.sm.movie_state.value = stop_target_state
                        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), expected_pending_state)
                        if stop_target_state != 0:
                            self.sm.movie_state.value = 0
                            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_SETTLE)
                        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_SETTLE)
                        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_PRESSING)

                        if outstanding_state in ("RELEASING", "WAIT_CONFIRM"):
                            for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                                self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_PRESSING)
                            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RELEASING)
                        if outstanding_state == "WAIT_CONFIRM":
                            for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                                self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_RELEASING)
                            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_WAIT_CONFIRM)

                        rel_before = self.sm.release_calls.value
                        self.assertEqual(self.sm.attempt_admitted, 1)
                        self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 1)
                        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.session_cancelled, 1)
                        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_SESSION_CANCEL)
                        self.assertEqual(self.sm.attempt_admitted, 0)
                        self.assertEqual(self.sm.synth_owned, 0)
                        self.assertEqual(self.sm.restart_budget, 2)
                        self.assertEqual(self.sm.restarts_remaining, 1)
                        self.assertEqual(self.sm.session_restarts_used, 1)
                        if outstanding_state == "PRESSING":
                            self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                        else:
                            self.assertEqual(self.sm.release_calls.value, rel_before)

    def test_budget_and_synthetic_key_ownership_invariants_across_all_states_and_allowances(self) -> None:
        # 1. Exhaustive (budget, used) matrix across RECORDING (including used == budget on the final (B+1)-th clip
        #    where restarts_remaining == 0) and across every poll of PRESSING (1..6), RELEASING (1..6), and WAIT_CONFIRM:
        #    proves configured allowance, remaining budget, and consumed attempts are preserved and only
        #    continuation-owned KEY_VIDEO is ever released while unrelated synthetic keys across words 0..2 stay intact.
        unrelated_w0_mask = 0x00010110  # KEY_MENU (0x10) | KEY_SET (0x100) | KEY_PLAYBACK (0x10000)
        unrelated_w1_val = 0xCAFEBABE
        unrelated_w2_val = 0x12345678

        for budget in (1, 2, 3):
            for used in range(0, budget + 1):
                with self.subTest(live_recording_budget=budget, used=used):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=budget)
                    for idx in range(1, used + 1):
                        self._prime_in_bounds_reason3_metrics(idx)
                        self._run_admitted_reason3_restart_to_confirmed_recording(
                            expected_remaining_after_admission=budget - idx,
                            expected_used_after_admission=idx,
                        )
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.restarts_remaining, budget - used)
                    self.assertEqual(self.sm.session_restarts_used, used)

                    # Set unrelated synthetic keys in words 0..2 and unowned KEY_VIDEO bit in kbd_mod_state[0]
                    self.sm.kbd_mod_state[0] &= ~(unrelated_w0_mask | G3X_KEY_VIDEO_BIT)
                    self.sm.kbd_mod_state[1] = unrelated_w1_val
                    self.sm.kbd_mod_state[2] = unrelated_w2_val
                    press_before = self.sm.press_calls.value
                    rel_before = self.sm.release_calls.value

                    self.assertEqual(self.sm.lib.g3x_movie_autocont_cancel_session(), 1)
                    self.assertEqual(self.sm.movie_state.value, 1)  # Active clip never stopped
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.restart_budget, budget)
                    self.assertEqual(self.sm.restarts_remaining, budget - used)
                    self.assertEqual(self.sm.session_restarts_used, used)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.press_calls.value, press_before)
                    self.assertEqual(self.sm.release_calls.value, rel_before)
                    self.assertEqual(self.sm.kbd_mod_state[0] & (unrelated_w0_mask | G3X_KEY_VIDEO_BIT), 0)
                    self.assertEqual(self.sm.kbd_mod_state[1] & 0xFFFFFFFF, unrelated_w1_val)
                    self.assertEqual(self.sm.kbd_mod_state[2] & 0xFFFFFFFF, unrelated_w2_val)

        # 2. Every synthetic press poll (1..6) in PRESSING (synth_owned == 1) in both <ALT> and non-<ALT> modes
        for alt_mode in (False, True):
            for press_poll in range(1, G3X_AUTOCONT_PRESS_POLLS + 1):
                with self.subTest(pressing_poll=press_poll, in_alt_mode=alt_mode):
                    self.sm.reset()
                    self._start_deliberate_physical_recording(budget=3)
                    self._prime_in_bounds_reason3_metrics(1)
                    self.sm.projected_size.value = 0x100000400
                    self.sm.stop_reason.value = 3
                    self.sm.movie_state.value = 0
                    for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
                        self.assertEqual(self.sm.step(in_alt_mode=alt_mode), G3X_AUTOCONT_SETTLE)
                    for _ in range(press_poll):
                        self.assertEqual(self.sm.step(in_alt_mode=alt_mode), G3X_AUTOCONT_PRESSING)
                    self.assertEqual(self.sm.synth_owned, 1)
                    self.assertTrue(self.sm.mod_video_pressed)
                    self.assertTrue(self.sm.physw_video_pressed)

                    # Assert unrelated synthetic keys in words 0..2
                    self.sm.kbd_mod_state[0] &= ~unrelated_w0_mask
                    self.sm.physw_status[0] &= ~unrelated_w0_mask
                    self.sm.kbd_mod_state[1] = unrelated_w1_val
                    self.sm.kbd_mod_state[2] = unrelated_w2_val
                    rel_before = self.sm.release_calls.value

                    self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
                    self.assertEqual(self.sm.synth_owned, 0)
                    self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                    self.assertEqual(self.sm.last_key_arg.value, KEY_VIDEO)
                    self.assertFalse(self.sm.mod_video_pressed)
                    self.assertFalse(self.sm.physw_video_pressed)
                    # Unrelated synthetic key bits in words 0..2 remain untouched
                    self.assertEqual(self.sm.kbd_mod_state[0] & unrelated_w0_mask, 0)
                    self.assertEqual(self.sm.physw_status[0] & unrelated_w0_mask, 0)
                    self.assertEqual(self.sm.kbd_mod_state[1] & 0xFFFFFFFF, unrelated_w1_val)
                    self.assertEqual(self.sm.kbd_mod_state[2] & 0xFFFFFFFF, unrelated_w2_val)
                    self.assertEqual(self.sm.restart_budget, 3)
                    self.assertEqual(self.sm.restarts_remaining, 2)
                    self.assertEqual(self.sm.session_restarts_used, 1)
                    self.assertEqual(self.sm.attempt_admitted, 0)

    def test_session_reset_provenance_expired_idle_press_and_restart_eligibility_regressions(self) -> None:
        # 1. Start session with budget=2, cancel during Clip 1 (remaining=2, used=0), then let Clip 1 stop to confirmed IDLE.
        #    Test that an EXPIRED physical KEY_VIDEO press at confirmed IDLE (> 200 polls before 0 -> 1)
        #    cannot clear session_cancelled or start a new session!
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=2)
        self._prime_in_bounds_reason3_metrics(1)
        self.assertEqual(self.sm.cancel_menu_change(1), "Cancel")
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 0)

        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle

        # Physical KEY_VIDEO press observed at confirmed IDLE, then released, then allowed to expire (200 polls)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.session_cancelled, 1)

        # Now 0 -> 1 occurs after the 200-poll idle press age expired: must NOT clear cancellation or arm!
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.menu_str, "Cancel")
        self.assertEqual(self.sm.cancel_menu_str, "Cancel")

        # 2. Physical KEY_VIDEO held continuously from physical stop across IDLE (cancel_latched == 1)
        #    followed by 0 -> 1 cannot clear session_cancelled
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Still held, so cancel_latched stays 1
        self.assertEqual(self.sm.cancel_latched, 1)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")

        # 3. Release physical KEY_VIDEO at IDLE across 2 polls (confirmed idle, cancel_latched == 0),
        #    then perform a qualifying deliberate physical start with button held across 0 -> 1 (start-hold carry-over):
        #    clears session_cancelled to 0 and starts a fresh session that can itself be cancelled again!
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 0)
        self.assertEqual(self.sm.session_cancelled, 1)

        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        # 4. Restart eligibility regressions under G3X_MOVIE_SESSION_CANCEL=1:
        #    ineligible stop causes (0, 1, 2, 5, 99), stale Reason 3, and stale Reason 4 disarm to STOP_FAULT (FLT)
        #    without consuming budget or latching session_cancelled
        for bad_reason in (0, 1, 2, 5, 99):
            self.sm.reset()
            self._start_deliberate_physical_recording(budget=2)
            self._prime_in_bounds_reason3_metrics(1)
            self.sm.projected_size.value = 0x100000400
            self.sm.stop_reason.value = bad_reason
            self.sm.movie_state.value = 2
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
            self.assertEqual(self.sm.session_cancelled, 0)
            self.assertEqual(self.sm.ui_status_str, "FLT")
            self.assertEqual(self.sm.restarts_remaining, 2)
            self.assertEqual(self.sm.session_restarts_used, 0)
            self.assertEqual(self.sm.press_calls.value, 0)


class TestPort61BuildArtifactsDisassemblyAndPreservedProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_port59()
        ensure_build_port60()
        ensure_build_port61()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p59_bin = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
        cls.p59_elf = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p60_bin = ROOT / "out/port60-movie-restart-budget/DISKBOOT.BIN"
        cls.p60_elf = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p61_bin = ROOT / "out/port61-movie-session-cancel/DISKBOOT.BIN"
        cls.p61_elf = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p61_obj = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.p61_manifest = ROOT / "out/port61-movie-session-cancel/port61_movie_session_cancel_manifest.json"
        cls.p61_stage = ROOT / "out/port61-movie-session-cancel/stage_chdk"

    def test_default_and_existing_port55_to_port60_profiles_remain_byte_identical(self) -> None:
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
        self.assertNotIn("g3x_movie_autocont_cancel_session", nm_p59)

        # 3. PORT-60 restart budget profile byte-identical
        self.assertTrue(self.p60_bin.is_file())
        self.assertEqual(sha256_file(self.p60_bin), PORT60_BUDGET_SHA256)
        self.assertEqual(self.p60_bin.stat().st_size, PORT60_BUDGET_SIZE)
        nm_p60 = subprocess.check_output([str(NM), str(self.p60_elf)], text=True)
        self.assertIn(f"{PORT60_BUDGET_END} B _end", nm_p60)
        self.assertNotIn("g3x_movie_autocont_cancel_session", nm_p60)

        # 4. Existing individual profiles (PORT-55, PORT-56, PORT-57, PORT-58) byte-identical
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
                self.assertNotIn("g3x_movie_autocont_cancel_session", nm_out)

    def test_port61_manifest_flags_hashes_and_disassembly_safety(self) -> None:
        self.assertTrue(self.p61_bin.is_file())
        self.assertTrue(self.p61_elf.is_file())
        self.assertTrue(self.p61_obj.is_file())
        self.assertTrue(self.p61_manifest.is_file())

        m = json.loads(self.p61_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_id"], "port61_movie_session_cancel_manifest")
        self.assertEqual(m["milestone"], "PORT-61")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_PORT60_COMMIT)
        self.assertEqual(m["candidate_source_base"], ORIGIN_MAIN_PORT60_COMMIT)
        self.assertEqual(m["integration_parent"], PORT61_INTEGRATION_PARENT)
        self.assertEqual(m["excluded_commits"], {"port54_conf_save": PORT54_EXCLUDED_COMMIT})
        self.assertEqual(m["card_writes"], "disabled")
        self.assertEqual(sha256_file(self.p61_bin), PORT61_CANCEL_SHA256)
        self.assertEqual(self.p61_bin.stat().st_size, PORT61_CANCEL_SIZE)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT61_CANCEL_SHA256)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], PORT61_CANCEL_SIZE)
        self.assertEqual(m["_end"], f"0x{PORT61_CANCEL_END}")

        flags = m["build"]["flags"]
        for req_flag in (
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_GUI_DBUF=1",
            "G3X_GUI_NOOVERDRAW=1",
            "G3X_KBD_CHECK=1",
            "G3X_GUI_DIAG=1",
            "G3X_GUI_SHADOW2=1",
            "G3X_GUI_SYNC=1",
            "G3X_GUI_MENU=1",
            "G3X_GUI_RESTORE2=1",
            "G3X_PLAYBACK_MENU=1",
            "G3X_MOVIE_STATUS=1",
            "G3X_MOVIE_NOLIMIT=1",
            "G3X_MOVIE_AUTOCONT=1",
            "G3X_MOVIE_AUTOCONT_UI=1",
            "G3X_MOVIE_RESTART_BUDGET=1",
            "G3X_MOVIE_SESSION_CANCEL=1",
        ):
            self.assertIn(req_flag, flags)
        for forbidden_flag in ("G3X_CONF_SAVE=1", "FULL_HOOKS=1"):
            self.assertNotIn(forbidden_flag, flags)

        nm_out = subprocess.check_output([str(NM), str(self.p61_elf)], text=True)
        for req_sym in (
            "g3x_get_movie_status",
            "g3x_movie_nolimit_poll",
            "g3x_movie_autocont_poll",
            "g3x_movie_autocont_is_enabled",
            "g3x_movie_autocont_can_enable",
            "g3x_movie_autocont_set_enabled",
            "g3x_movie_autocont_menu_change",
            "g3x_movie_autocont_get_restart_budget",
            "g3x_movie_autocont_set_restart_budget",
            "g3x_movie_autocont_get_restarts_remaining",
            "g3x_movie_autocont_get_session_restarts_used",
            "g3x_movie_autocont_is_attempt_admitted",
            "g3x_movie_autocont_budget_menu_str",
            "g3x_movie_autocont_budget_menu_change",
            "g3x_movie_autocont_can_cancel_session",
            "g3x_movie_autocont_cancel_session",
            "g3x_movie_autocont_is_session_cancelled",
            "g3x_movie_autocont_cancel_menu_str",
            "g3x_movie_autocont_cancel_menu_change",
            "__wrap_open",
            "__wrap_fopen",
            "__wrap_creat",
            "__wrap_write",
            "__wrap_fwrite",
            "__wrap_mkdir",
            "__wrap_remove",
            "__wrap_rename",
            "__wrap_MakeDirectory_Fut",
            "__wrap__MakeDirectory_Fut",
            "__wrap_DeleteFile_Fut",
            "__wrap__DeleteFile_Fut",
            "__wrap_RenameFile_Fut",
            "__wrap__RenameFile_Fut",
        ):
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in PORT-61 main.elf")

        for excluded_sym in ("g3x_conf_save_active", "g3x_is_safe_chdk_write_path", "g3x_is_conf_file_path"):
            self.assertNotIn(excluded_sym, nm_out)

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
        for target_path, _desc in ((self.p61_obj, "movie_rec.o"), (self.p61_elf, "main.elf")):
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

        staged_boot_c = (self.p61_stage / "platform/g3x/sub/110c/boot.c").read_text(encoding="utf-8")
        self.assertIn("0xfc1283ad", staged_boot_c.lower())
        self.assertIn("0xfc0bd071", staged_boot_c.lower())
        self.assertNotIn("0xfc09ac19", staged_boot_c.lower())

        staged_gui_c = (self.p61_stage / "core/gui.c").read_text(encoding="utf-8")
        self.assertIn('"Auto-Continue Movie"', staged_gui_c)
        self.assertIn('"Auto-Continue Budget"', staged_gui_c)
        self.assertIn('"Cancel further restarts"', staged_gui_c)
        self.assertIn("g3x_movie_autocont_menu_change", staged_gui_c)
        self.assertIn("g3x_movie_autocont_budget_menu_change", staged_gui_c)
        self.assertIn("g3x_movie_autocont_cancel_menu_change", staged_gui_c)
        self.assertNotIn("g3x_movie_nolimit", staged_gui_c)

    def test_milestone_doc_records_flags_commits_and_artifact_hashes(self) -> None:
        doc_text = DOC_PORT61.read_text(encoding="utf-8")
        for token in (
            ORIGIN_MAIN_PORT60_COMMIT,
            PORT60_INTEGRATION_TIP,
            PORT60_VALIDATE_COMMIT,
            PORT60_BUILD_COMMIT,
            PORT60_INTERFACES_COMMIT,
            ORIGIN_MAIN_PORT59_COMMIT,
            PORT55_BUILD_COMMIT,
            PORT56_BUILD_COMMIT,
            PORT57_BUILD_COMMIT,
            PORT58_BUILD_COMMIT,
            PORT59_BUILD_COMMIT,
            PORT61_INTERFACE_COMMIT,
            PORT61_INTEGRATION_PARENT,
            PORT61_BUILD_COMMIT,
            PORT61_BUILD_INTEGRATION_COMMIT,
            BASE_DEFAULT_SHA256,
            PORT59_COMBINED_SHA256,
            PORT60_BUDGET_SHA256,
            PORT61_CANCEL_SHA256,
            f"0x{PORT61_CANCEL_END}",
            "G3X_MOVIE_SESSION_CANCEL=1",
            "--movie-session-cancel",
            "Cancel further restarts",
            "port61_movie_session_cancel_manifest.json",
            "out/port61-movie-session-cancel/DISKBOOT.BIN",
            "PORT61-CANCEL-VALIDATE",
            "Battery-Pull Recovery",
            "CAMERA BEHAVIOR UNVERIFIED",
        ):
            self.assertIn(token, doc_text, f"Missing '{token}' in docs/PORT61_MOVIE_SESSION_CANCEL.md")
        for spec in INDIVIDUAL_PROFILES.values():
            self.assertIn(spec["sha256"], doc_text)

        sha256_tokens = set(re.findall(r"\b[0-9a-f]{64}\b", doc_text))
        commit_candidates = set(re.findall(r"\b[0-9a-f]{40}\b", doc_text))
        for commit_hash in commit_candidates:
            if any(commit_hash in s for s in sha256_tokens):
                continue
            res = subprocess.run(
                ["git", "rev-parse", "--verify", f"{commit_hash}^{{commit}}"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Unresolvable commit hash in docs/PORT61_MOVIE_SESSION_CANCEL.md: {commit_hash}")


if __name__ == "__main__":
    unittest.main()
