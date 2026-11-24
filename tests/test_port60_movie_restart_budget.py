"""Offline unit and integration tests for PORT-60 (Opt-In Finite Movie Restart Budget: G3X_MOVIE_RESTART_BUDGET=1).

Verifies:
1. Separately selected opt-in profile (G3X_MOVIE_RESTART_BUDGET=1 / --movie-restart-budget):
   - Provides volatile restart allowances 1, 2, or 3 with default 1.
   - Continuation starts disabled (AC:OFF / "Off") after every boot and never persists in struct Conf.
   - Missing prerequisites or incompatible flags (G3X_CONF_SAVE=1, FULL_HOOKS=1, *-alone) fail explicitly.
2. Confirmed-idle gating for enable and allowance edits:
   - Both enable (0 -> 1) and allowance edits (1/2/3) require confirmed idle in record mode with physical
     KEY_VIDEO released, no owned synthetic key, and state == G3X_AUTOCONT_DISARMED.
   - Edits are rejected before boot idle, during recording/stopping, on the first idle poll after recording,
     in playback mode, while physical KEY_VIDEO is held, or during any pending continuation state.
   - Enable and allowance edits never initiate recording or issue synthetic key presses.
3. Session allowance initialization & synthetic start invariance:
   - Only a subsequent deliberate physical recording start (physical KEY_VIDEO press observed at confirmed
     IDLE after enabling/editing, followed by IDLE -> RECORDING within 200 polls) initializes session
     allowance (restarts_remaining = restart_budget, session_restarts_used = 0).
   - Synthetic continuation starts (RELEASING / WAIT_CONFIRM -> RECORDING) never initialize, reset, or
     replenish session allowance.
4. Atomic pre-input allowance reservation & no-refund invariant:
   - Each admitted synthetic restart attempt atomically consumes 1 allowance at restart admission
     (RECORDING -> WAIT_IDLE / SETTLE), before entering PRESSING and before issuing synthetic input.
   - Failed, interrupted, or duplicate attempts (timeout, invalid state, playback, physical stop, user
     disable, or unreset stop counters) never refund allowance or exceed the selected budget.
5. Exhaustion behavior & continuation-owned key handling:
   - For selected budget B in {1, 2, 3}, at most B synthetic restart attempts are admitted across B + 1 clips.
   - When remaining allowance reaches zero, the active continued clip keeps running uninterrupted, any
     further automatic start is prevented, pending continuation is cancelled, and only continuation-owned
     synthetic keys are released.
6. Preserved PORT-55..59 invariants, default build byte-identity & individual profile hashes:
   - Physical-stop precedence, Reason 3 / Reason 4 eligibility checks, boot path, task hooks, CreateTask_my,
     runtime file-write blockers, and PORT-54 exclusion (SAVE:OFF) remain intact.
   - Default build and existing PORT-55..59 profiles remain byte-identical.
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

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
GUI_MENU_C = ROOT / "chdk-port/platform/g3x/gui_menu.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
DOC_PORT60 = ROOT / "docs/PORT60_MOVIE_RESTART_BUDGET.md"
EVIDENCE_MANIFEST = ROOT / "docs/port34_evidence_manifest.json"
TRUSTED_SCOPES = ROOT / "docs/port34_trusted_scopes.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_PORT59_COMMIT = "0579e70d39f0bd4156b1266e5187f97275a9b0a8"
PORT59_BUILD_COMMIT = "32d6e0aa60766fdb4223d86403c37fca2c82c920"
PORT60_INTERFACES_COMMIT = "85ee3571b3624d2e26c81d77136ca7d1b0627f2e"
PORT60_INTEGRATION_PARENT = "5ed0b6a345d5e8d9e4866146451c1c360848553d"

PORT60_BUDGET_SHA256 = "5bb1b93b0a3246ab5e37c689daa223dd2c6a9e3e84a53956678992b97be00a90"
PORT60_BUDGET_SIZE = 135313
PORT60_BUDGET_END = "0036b6e0"

KEY_VIDEO = 13
G3X_KEY_VIDEO_BIT = 0x00000008
UNRELATED_KEY_BITS = 0x000533F1

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

G3X_AUTOCONT_MAX_STOP_POLLS = 500
G3X_AUTOCONT_SETTLE_POLLS = 50
G3X_AUTOCONT_PRESS_POLLS = 6
G3X_AUTOCONT_RELEASE_POLLS = 6
G3X_AUTOCONT_CONFIRM_POLLS = 200
G3X_AUTOCONT_START_HOLD_POLLS = 50

G3X_AUTOCONT_BUDGET_MIN = 1
G3X_AUTOCONT_BUDGET_MAX = 3
G3X_AUTOCONT_BUDGET_DEFAULT = 1

REQUIRED_BUDGET_PREREQS = [
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
    obj_path = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "out/port60-movie-restart-budget/port60_movie_restart_budget_manifest.json"
    if (
        _BUILD_CACHE["port60"]
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
                "--out-dir",
                str(ROOT / "out/port60-movie-restart-budget"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port60"] = True


def setUpModule() -> None:
    ensure_build_default()
    ensure_build_port59()
    ensure_build_port60()


class _HostPort60BudgetHarness:
    """Compiles movie_rec.c, gui_diag.h, and gui_menu.c with G3X_MOVIE_RESTART_BUDGET=1."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port60_host_sm_")
        tmp = Path(self._tmpdir.name)

        (tmp / "conf.h").write_text("/* stub conf.h */\n", encoding="utf-8")
        (tmp / "keyboard.h").write_text(f"#define KEY_VIDEO {KEY_VIDEO}\n", encoding="utf-8")
        (tmp / "camera_info.h").write_text(
            "typedef struct {\n"
            "    struct {\n"
            "        int mode_play;\n"
            "        int gui_mode;\n"
            "        int gui_mode_none;\n"
            "        int gui_mode_alt;\n"
            "        int osd_title_line;\n"
            "    } state;\n"
            "} cam_info_t;\n"
            "extern cam_info_t camera_info;\n",
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
            "}\n",
            encoding="utf-8",
        )

        so_path = tmp / "libport60_movie_restart_budget.so"
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
                f"-I{tmp}",
                f"-I{ROOT / 'chdk-port/platform/g3x'}",
                str(MOVIE_REC_C),
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


class TestPort60FlagGatesAndUnsupportedCombinations(unittest.TestCase):
    def test_budget_profile_accepts_full_prerequisites_and_rejects_missing_prerequisites(self) -> None:
        expected_err = (
            "G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 "
            "G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 "
            "G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1"
        )
        full_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_RESTART_BUDGET=1"] + [
            f"-D{f}=1" for f in REQUIRED_BUDGET_PREREQS
        ]
        for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

        for missing in REQUIRED_BUDGET_PREREQS:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_RESTART_BUDGET=1"] + [
                    f"-D{f}=1" for f in REQUIRED_BUDGET_PREREQS if f != missing
                ]
                for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
                    res = subprocess.run(
                        ["cc", "-E", *c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

                make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_RESTART_BUDGET=1"] + [
                    f"{f}=1" for f in REQUIRED_BUDGET_PREREQS if f != missing
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

    def test_budget_profile_rejects_incompatible_flags_and_cli_combinations(self) -> None:
        full_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_RESTART_BUDGET=1"] + [
            f"-D{f}=1" for f in REQUIRED_BUDGET_PREREQS
        ]
        full_make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_RESTART_BUDGET=1"] + [
            f"{f}=1" for f in REQUIRED_BUDGET_PREREQS
        ]
        for bad_flag in ("G3X_CONF_SAVE", "FULL_HOOKS"):
            expected_msg = f"G3X_MOVIE_RESTART_BUDGET=1 is incompatible with {bad_flag}=1"
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
        ]
        for bad_cli, exp_err in (
            (["--conf-save"], "G3X_MOVIE_RESTART_BUDGET=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_RESTART_BUDGET=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-nolimit-alone"], "G3X_MOVIE_RESTART_BUDGET=1 requires"),
            (["--movie-autocont-alone"], "G3X_MOVIE_RESTART_BUDGET=1 requires"),
            (["--movie-status-alone"], "G3X_MOVIE_RESTART_BUDGET=1 requires"),
            (["--playback-menu-alone"], "G3X_MOVIE_RESTART_BUDGET=1 requires"),
        ):
            res = subprocess.run([*base_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(exp_err, res.stderr)

        missing_ui_cli = [arg for arg in base_cli if arg != "--movie-autocont-ui"]
        res = subprocess.run(missing_ui_cli, cwd=str(ROOT), capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1", res.stderr)


class TestPort60FiniteRestartBudgetRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort60BudgetHarness()

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
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 0)

    def _start_deliberate_physical_recording(self, budget: int = 1, hold_polls_into_rec: int = 0) -> None:
        if not self.sm.enabled or self.sm.restart_budget != budget:
            self._confirm_idle_enable_and_set_budget(budget)
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)
        if hold_polls_into_rec == 0:
            self.sm.set_physical_video_button(False)

        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.restarts_remaining, budget)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

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
        confirm_in_releasing: bool = False,
    ) -> None:
        press_before = self.sm.press_calls.value
        self.sm.projected_size.value = 0x100000400 + expected_used_after_admission * 8192
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2  # STOPPING

        # Stop-onset admission atomically consumes 1 allowance BEFORE entering PRESSING or issuing synthetic input
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
        self.assertEqual(self.sm.attempt_admitted, 1)
        self.assertEqual(self.sm.press_calls.value, press_before)
        self.assertEqual(self.sm.synth_owned, 0)

        # Transition WAIT_IDLE -> SETTLE
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
        self.assertEqual(self.sm.attempt_admitted, 1)
        self.assertEqual(self.sm.press_calls.value, press_before)
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
            self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
            self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
            self.assertEqual(self.sm.press_calls.value, press_before)

        # Transition SETTLE -> PRESSING (6 polls): issues synthetic input without consuming another allowance
        for i in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
            self.assertEqual(self.sm.synth_owned, 1)
            self.assertEqual(self.sm.press_calls.value, press_before + i + 1)
            self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
            self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
            self.assertEqual(self.sm.attempt_admitted, 1)

        # Transition PRESSING -> RELEASING (6 polls)
        for i in range(G3X_AUTOCONT_RELEASE_POLLS):
            if confirm_in_releasing and i == G3X_AUTOCONT_RELEASE_POLLS - 1:
                self.sm.movie_state.value = 1
                self.sm.max_frames.value = 54000
                self.sm.cur_frames.value = expected_used_after_admission + 1
                self.sm.stream_bytes.value = 65536 * (expected_used_after_admission + 1)
                self.sm.projected_size.value = 65536 * (expected_used_after_admission + 1)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
            self.assertEqual(self.sm.synth_owned, 0)
            self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
            self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)

        if confirm_in_releasing:
            # Final poll of RELEASING with cur_state == 1 enters RECORDING directly
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        else:
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
            self.assertEqual(self.sm.attempt_admitted, 1)
            self.sm.movie_state.value = 1
            self.sm.max_frames.value = 54000
            self.sm.cur_frames.value = expected_used_after_admission + 1
            self.sm.stream_bytes.value = 65536 * (expected_used_after_admission + 1)
            self.sm.projected_size.value = 65536 * (expected_used_after_admission + 1)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        # Synthetic start never resets or replenishes session allowance
        self.assertEqual(self.sm.restarts_remaining, expected_remaining_after_admission)
        self.assertEqual(self.sm.session_restarts_used, expected_used_after_admission)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.restart_count, expected_used_after_admission)
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)

    def test_boot_defaults_volatile_allowances_1_2_3_and_confirmed_idle_edit_gating(self) -> None:
        # 1. Boot state: disabled, default allowance 1, remaining session allowance 0
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")
        self.assertEqual(self.sm.restart_budget, G3X_AUTOCONT_BUDGET_DEFAULT)
        self.assertEqual(self.sm.budget_menu_str, "1")
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.can_enable, 0)

        # 2. Cannot enable or edit allowance before boot idle is confirmed
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.menu_change(1), "Off")
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(2), 0)
        self.assertEqual(self.sm.budget_menu_change(1), "1")
        self.assertEqual(self.sm.restart_budget, 1)

        # 3. Cannot enable or edit allowance in any non-idle movie_state, first poll after 1->0,
        #    playback mode, or while physical KEY_VIDEO is pressed
        for bad_state in (1, 2, 3, 4, -1, 5):
            self.sm.reset()
            self.sm.movie_state.value = bad_state
            self.sm.step()
            self.assertEqual(self.sm.can_enable, 0)
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(2), 0)
            self.assertEqual(self.sm.budget_menu_change(1), "1")
            self.assertEqual(self.sm.restart_budget, 1)

        # First poll after 1 -> 0 (prev_rec_state != 0) rejects both enable and budget edits
        self.sm.reset()
        self.sm.movie_state.value = 0
        self.sm.step()
        self.sm.movie_state.value = 1
        self.sm.step()
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(3), 0)
        self.assertEqual(self.sm.budget_menu_change(1), "1")
        self.sm.step()  # Confirms IDLE (0)

        # Playback mode rejects both enable and budget edits
        self.sm.lib.host_set_mode_play(1)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(2), 0)
        self.assertEqual(self.sm.budget_menu_change(1), "1")
        self.sm.lib.host_set_mode_play(0)

        # Physical KEY_VIDEO held down rejects both enable and budget edits
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(2), 0)
        self.assertEqual(self.sm.budget_menu_change(1), "1")
        self.sm.set_physical_video_button(False)
        self.sm.step()

        # 4. At confirmed idle: invalid budget values (<1 or >3) are rejected; valid allowances 1/2/3 succeed
        #    and never initiate recording or initialize active session allowance before a deliberate physical start
        self.assertEqual(self.sm.can_enable, 1)
        for bad_budget in (0, 4, 5, 99, 0xFFFFFFFF):
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(bad_budget), 0)
            self.assertEqual(self.sm.restart_budget, 1)

        self.assertEqual(self.sm.budget_menu_change(1), "2")
        self.assertEqual(self.sm.restart_budget, 2)
        self.assertEqual(self.sm.budget_menu_change(1), "3")
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.budget_menu_change(1), "1")
        self.assertEqual(self.sm.restart_budget, 1)
        self.assertEqual(self.sm.budget_menu_change(-1), "3")
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.budget_menu_change(-1), "2")
        self.assertEqual(self.sm.restart_budget, 2)

        self.assertEqual(self.sm.menu_change(1), "Ready")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.restarts_remaining, 0)
        for _ in range(30):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.synth_owned, 0)
            self.assertEqual(self.sm.restarts_remaining, 0)

        # 5. Reboot (reset) restores disabled state and default allowance 1
        self.sm.reset()
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.restart_budget, 1)
        self.assertEqual(self.sm.budget_menu_str, "1")
        self.assertEqual(self.sm.restarts_remaining, 0)

    def test_only_subsequent_deliberate_physical_start_initializes_allowance_and_active_edits_rejected(self) -> None:
        self._confirm_idle_enable_and_set_budget(2)

        # 1. Pre-edit physical press at IDLE is cleared by a subsequent budget edit at confirmed idle
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.budget_menu_change(1), "3")
        self.assertEqual(self.sm.restart_budget, 3)

        # Recording start 0 -> 1 without a NEW physical press after the edit does NOT arm or initialize allowance
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.restarts_remaining, 0)

        # Return to IDLE, confirm idle, then perform a deliberate physical start -> initializes allowance to 3
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.restarts_remaining, 3)
        self.assertEqual(self.sm.session_restarts_used, 0)

        # 2. While in RECORDING or any pending continuation phase (WAIT_IDLE, SETTLE, PRESSING, RELEASING, WAIT_CONFIRM),
        #    allowance edits and enable(1) edits are rejected and cannot alter the active session budget
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        self.assertEqual(self.sm.budget_menu_change(-1), "3")
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.restarts_remaining, 3)

        self._prime_in_bounds_reason3_metrics(1)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        self.assertEqual(self.sm.budget_menu_change(1), "3")

        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(1), 0)
        self.assertEqual(self.sm.restart_budget, 3)
        self.assertEqual(self.sm.restarts_remaining, 2)

    def test_exact_finite_restart_budgets_1_2_3_and_exhaustion_leaves_active_clip_running(self) -> None:
        for budget in (1, 2, 3):
            with self.subTest(budget=budget, confirm_in_releasing=(budget == 2)):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=budget)
                self.assertEqual(self.sm.restarts_remaining, budget)
                self.assertEqual(self.sm.session_restarts_used, 0)

                # Execute exactly `budget` automatic restarts across `budget + 1` clips
                for attempt_idx in range(1, budget + 1):
                    self._prime_in_bounds_reason3_metrics(attempt_idx)
                    self._run_admitted_reason3_restart_to_confirmed_recording(
                        expected_remaining_after_admission=budget - attempt_idx,
                        expected_used_after_admission=attempt_idx,
                        confirm_in_releasing=(budget == 2 and attempt_idx == 1),
                    )

                # At exhaustion (restarts_remaining == 0), the final (budget + 1)-th clip is actively recording
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.assertEqual(self.sm.session_restarts_used, budget)
                self.assertEqual(self.sm.restart_count, budget)
                self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.movie_state.value, 1)
                self.assertEqual(self.sm.synth_owned, 0)
                total_presses = budget * G3X_AUTOCONT_PRESS_POLLS
                self.assertEqual(self.sm.press_calls.value, total_presses)

                # Final clip continues recording uninterrupted across many polls with 0 remaining allowance
                self._prime_in_bounds_reason3_metrics(budget + 1)
                for _ in range(25):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.movie_state.value, 1)
                    self.assertEqual(self.sm.press_calls.value, total_presses)
                    self.assertEqual(self.sm.restarts_remaining, 0)

                # When the final clip hits an eligible 4 GiB Reason 3 stop, exhaustion prevents any further
                # automatic start, cancels continuation, and disarms cleanly to RDY without entering WAIT_IDLE/SETTLE
                self.sm.projected_size.value = 0x100008000
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.enabled, 1)
                self.assertEqual(self.sm.ui_status_str, "RDY")
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.assertEqual(self.sm.session_restarts_used, budget)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.synth_owned, 0)

                self.sm.movie_state.value = 0
                for _ in range(100):
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.press_calls.value, total_presses)
                    self.assertEqual(self.sm.restart_count, budget)

                # A subsequent synthetic/unattributed 0 -> 1 cannot re-initialize allowance;
                # only a new deliberate physical start initializes a fresh session budget
                self.sm.movie_state.value = 1
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.sm.movie_state.value = 0
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.sm.set_physical_video_button(False)
                self.sm.movie_state.value = 1
                self.sm.cur_frames.value = 10
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.restarts_remaining, budget)
                self.assertEqual(self.sm.session_restarts_used, 0)

    def test_failed_interrupted_and_duplicate_attempts_never_refund_allowance_or_exceed_budget(self) -> None:
        # Test every failure and interruption mode after an attempt is admitted with budget=2:
        # 1 allowance is consumed at admission before input issuance (restarts_remaining: 2 -> 1, used: 0 -> 1),
        # and is NEVER refunded back to 2 on failure or interruption.
        failure_modes = (
            "WAIT_IDLE_TIMEOUT",
            "WAIT_IDLE_INVALID_STATE",
            "WAIT_IDLE_PHYS_STOP",
            "WAIT_IDLE_USER_DISABLE",
            "SETTLE_INVALID_STATE",
            "SETTLE_PLAYBACK",
            "SETTLE_PHYS_STOP",
            "PRESSING_INVALID_STATE",
            "PRESSING_PLAYBACK",
            "PRESSING_PHYS_STOP",
            "PRESSING_USER_DISABLE",
            "RELEASING_INVALID_STATE",
            "RELEASING_PHYS_STOP",
            "WAIT_CONFIRM_TIMEOUT",
            "WAIT_CONFIRM_INVALID_STATE",
            "WAIT_CONFIRM_PHYS_STOP",
        )
        for mode in failure_modes:
            with self.subTest(failure_mode=mode):
                self.sm.reset()
                self.sm.kbd_new_state[0] &= ~0x00000010
                self.sm.kbd_mod_state[0] &= ~0x00000010
                self._start_deliberate_physical_recording(budget=2)
                self.assertEqual(self.sm.restarts_remaining, 2)
                self.assertEqual(self.sm.session_restarts_used, 0)

                self._prime_in_bounds_reason3_metrics(1)
                self.sm.projected_size.value = 0x100000400
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2

                # Admission atomically reserves 1 allowance before any synthetic key press
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                self.assertEqual(self.sm.restarts_remaining, 1)
                self.assertEqual(self.sm.session_restarts_used, 1)
                self.assertEqual(self.sm.attempt_admitted, 1)
                self.assertEqual(self.sm.press_calls.value, 0)

                if mode == "WAIT_IDLE_TIMEOUT":
                    for _ in range(G3X_AUTOCONT_MAX_STOP_POLLS - 1):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
                elif mode == "WAIT_IDLE_INVALID_STATE":
                    self.sm.movie_state.value = 1
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                elif mode == "WAIT_IDLE_PHYS_STOP":
                    self.sm.set_physical_video_button(True)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                elif mode == "WAIT_IDLE_USER_DISABLE":
                    self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
                    self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
                else:
                    self.sm.movie_state.value = 0
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                    if mode == "SETTLE_INVALID_STATE":
                        self.sm.movie_state.value = 2
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                    elif mode == "SETTLE_PLAYBACK":
                        self.sm.lib.host_set_mode_play(1)
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
                    elif mode == "SETTLE_PHYS_STOP":
                        self.sm.set_physical_video_button(True)
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                    else:
                        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                        self.assertEqual(self.sm.synth_owned, 1)
                        if mode == "PRESSING_INVALID_STATE":
                            self.sm.movie_state.value = 2
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                        elif mode == "PRESSING_PLAYBACK":
                            self.sm.lib.host_set_mode_play(1)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
                        elif mode == "PRESSING_PHYS_STOP":
                            self.sm.set_physical_video_button(True)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                        elif mode == "PRESSING_USER_DISABLE":
                            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
                            self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
                        else:
                            for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                            self.assertEqual(self.sm.synth_owned, 0)
                            if mode == "RELEASING_INVALID_STATE":
                                self.sm.movie_state.value = 2
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                            elif mode == "RELEASING_PHYS_STOP":
                                self.sm.set_physical_video_button(True)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                            else:
                                for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                if mode == "WAIT_CONFIRM_TIMEOUT":
                                    for _ in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
                                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
                                elif mode == "WAIT_CONFIRM_INVALID_STATE":
                                    self.sm.movie_state.value = 2
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                                elif mode == "WAIT_CONFIRM_PHYS_STOP":
                                    self.sm.set_physical_video_button(True)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)

                # Allowance was consumed at admission and never refunded; owned synthetic key was released
                self.assertEqual(self.sm.restarts_remaining, 1)
                self.assertEqual(self.sm.session_restarts_used, 1)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.synth_owned, 0)
                self.assertFalse(self.sm.mod_video_pressed)
                self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)
                self.assertEqual(self.sm.restart_count, 0)

        # Duplicate / unreset stop counters on a continued clip with budget=3 are rejected as STOP_FAULT
        # without consuming a second allowance or issuing a duplicate synthetic pulse
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=3)
        self.sm.cur_frames.value = 29000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF000000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.sm.projected_size.value = 0x100000100
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        # Clip 2 starts with unreset counters still matching Clip 1's stop snapshot
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 1)
        # Immediately stop with unreset counters matching last_stop_* -> rejected without consuming allowance 2
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 1)
        self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)

    def test_reason4_eligibility_and_live_menu_redraw_with_restart_budget(self) -> None:
        # 1. Live menu redraw triggers on budget edits (1 -> 2 -> 3) and remaining-allowance changes
        self.sm.lib.host_set_gui_mode(2)  # GUI_MODE_MENU
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 0)

        self._confirm_idle_enable_and_set_budget(2)
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()

        self.assertEqual(self.sm.budget_menu_change(1), "3")
        self.assertEqual(self.sm.lib.gui_menu_needs_redraw(), 1)
        self.sm.lib.gui_menu_clear_redraw()

        # 2. Reason 4 (finite frame limit) continuation consumes budget=1 and stops after 1 restart
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=1)
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 12000
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_RECORDING)
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.last_stop_reason, 4)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 1)
        self.assertEqual(self.sm.attempt_admitted, 1)
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_WAIT_CONFIRM)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.restarts_remaining, 0)

        # Clip 2 hits Reason 4 -> budget exhausted (0 remaining) -> disarms to RDY without a 2nd restart
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)


class TestPort60BuildArtifactsDisassemblyAndPreservedProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_port59()
        ensure_build_port60()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p59_bin = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
        cls.p59_elf = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p60_bin = ROOT / "out/port60-movie-restart-budget/DISKBOOT.BIN"
        cls.p60_elf = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p60_obj = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.p60_manifest = ROOT / "out/port60-movie-restart-budget/port60_movie_restart_budget_manifest.json"
        cls.p60_stage = ROOT / "out/port60-movie-restart-budget/stage_chdk"

    def test_default_and_existing_individual_and_port59_profiles_remain_byte_identical(self) -> None:
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
        self.assertNotIn("g3x_movie_autocont_get_restart_budget", nm_p59)

        # 3. Existing individual profiles (PORT-55, PORT-56, PORT-57, PORT-58) byte-identical
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
                self.assertNotIn("g3x_movie_autocont_get_restart_budget", nm_out)

    def test_port60_manifest_flags_hashes_and_disassembly_safety(self) -> None:
        self.assertTrue(self.p60_bin.is_file())
        self.assertTrue(self.p60_elf.is_file())
        self.assertTrue(self.p60_obj.is_file())
        self.assertTrue(self.p60_manifest.is_file())

        m = json.loads(self.p60_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_id"], "port60_movie_restart_budget_manifest")
        self.assertEqual(m["milestone"], "PORT-60")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_PORT59_COMMIT)
        self.assertEqual(m["candidate_source_base"], ORIGIN_MAIN_PORT59_COMMIT)
        self.assertEqual(m["integration_parent"], PORT60_INTEGRATION_PARENT)
        self.assertEqual(m["excluded_commits"], {"port54_conf_save": PORT54_EXCLUDED_COMMIT})
        self.assertEqual(m["card_writes"], "disabled")
        self.assertEqual(sha256_file(self.p60_bin), PORT60_BUDGET_SHA256)
        self.assertEqual(self.p60_bin.stat().st_size, PORT60_BUDGET_SIZE)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT60_BUDGET_SHA256)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], PORT60_BUDGET_SIZE)
        self.assertEqual(m["_end"], f"0x{PORT60_BUDGET_END}")

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
        ):
            self.assertIn(req_flag, flags)
        for forbidden_flag in ("G3X_CONF_SAVE=1", "FULL_HOOKS=1"):
            self.assertNotIn(forbidden_flag, flags)

        nm_out = subprocess.check_output([str(NM), str(self.p60_elf)], text=True)
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
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in PORT-60 main.elf")

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
        for target_path, desc in ((self.p60_obj, "movie_rec.o"), (self.p60_elf, "main.elf")):
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

        staged_boot_c = (self.p60_stage / "platform/g3x/sub/110c/boot.c").read_text(encoding="utf-8")
        self.assertIn("0xfc1283ad", staged_boot_c.lower())
        self.assertIn("0xfc0bd071", staged_boot_c.lower())
        self.assertNotIn("0xfc09ac19", staged_boot_c.lower())

        staged_gui_c = (self.p60_stage / "core/gui.c").read_text(encoding="utf-8")
        self.assertIn('"Auto-Continue Movie"', staged_gui_c)
        self.assertIn('"Auto-Continue Budget"', staged_gui_c)
        self.assertIn("g3x_movie_autocont_menu_change", staged_gui_c)
        self.assertIn("g3x_movie_autocont_budget_menu_change", staged_gui_c)
        self.assertNotIn("g3x_movie_nolimit", staged_gui_c)

    def test_milestone_doc_records_flags_commits_and_artifact_hashes(self) -> None:
        doc_text = DOC_PORT60.read_text(encoding="utf-8")
        for token in (
            ORIGIN_MAIN_PORT59_COMMIT,
            PORT60_INTERFACES_COMMIT,
            PORT60_INTEGRATION_PARENT,
            PORT55_BUILD_COMMIT,
            PORT56_BUILD_COMMIT,
            PORT57_BUILD_COMMIT,
            PORT58_BUILD_COMMIT,
            PORT59_BUILD_COMMIT,
            BASE_DEFAULT_SHA256,
            PORT59_COMBINED_SHA256,
            PORT60_BUDGET_SHA256,
            f"0x{PORT60_BUDGET_END}",
            "G3X_MOVIE_RESTART_BUDGET=1",
            "--movie-restart-budget",
            "port60_movie_restart_budget_manifest.json",
            "out/port60-movie-restart-budget/DISKBOOT.BIN",
            "CAMERA BEHAVIOR UNVERIFIED",
        ):
            self.assertIn(token, doc_text, f"Missing '{token}' in docs/PORT60_MOVIE_RESTART_BUDGET.md")

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
            self.assertEqual(res.returncode, 0, f"Unresolvable commit hash in docs/PORT60_MOVIE_RESTART_BUDGET.md: {commit_hash}")


if __name__ == "__main__":
    unittest.main()
