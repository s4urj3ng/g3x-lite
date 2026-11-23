"""Offline unit and integration tests for PORT-59 (Combined Movie Profile: G3X_MOVIE_NOLIMIT=1 + G3X_MOVIE_AUTOCONT_UI=1).

Verifies:
1. Combined opt-in profile build & provenance:
   - Builds cleanly with the pinned toolchain (gcc-arm-none-eabi-5_4-2016q3) via explicit flags and --movie-combined.
   - Emits out/port59-movie-combined/DISKBOOT.BIN and port59_movie_combined_manifest.json with exact flags and
     resolvable reused source commits (origin/main, PORT-55, PORT-56, PORT-57, PORT-58, PORT59-COMPAT).
2. Separate feature gates & explicit rejection of unsupported combinations:
   - Standalone/separate PORT-55, PORT-56, PORT-57, and PORT-58 feature gates remain usable and unchanged.
   - Missing prerequisites for G3X_MOVIE_AUTOCONT_UI=1 (with or without G3X_MOVIE_NOLIMIT=1), combining
     G3X_MOVIE_NOLIMIT=1 + G3X_MOVIE_AUTOCONT=1 without G3X_MOVIE_AUTOCONT_UI=1, omitting G3X_MOVIE_STATUS=1,
     or combining with G3X_CONF_SAVE=1, FULL_HOOKS=1, or *-alone fail explicitly across headers, Makefiles, and CLI.
3. Boot initialization, confirmed-idle enable gating & deliberate physical start arming:
   - Continuation initializes disabled on every boot (AC:OFF / "Off") and never persists in struct Conf.
   - Enabling requires confirmed idle in record mode with physical KEY_VIDEO released and never starts recording.
   - Arming requires a subsequent physical KEY_VIDEO press observed at IDLE followed by 0 -> 1 (AC:ARM / "Armed").
4. Combined PORT-56 time-limit defeat + PORT-57/58 continuation & physical-stop precedence:
   - g3x_movie_nolimit_poll() runs before g3x_movie_autocont_poll() on every 10 ms tick in my_kbd_read_keys().
   - Time-limit patch writes 0xFFFFFFFFU to 0x0000C274 (mr_max_frames) only while mr_rec_state == 1 (LIM:OFF),
     adds no restart trigger when continuation is Off/Ready/Faulted, and bypasses no continuation control.
   - Suppresses Reason 4 (29:59 / 59:59 frame limit) stops when max_frames == 0xFFFFFFFFU while preserving
     Reason 3 (4 GiB size cap) automatic continuation and re-patching 0x0000C274 on every continued clip after
     MovieRecorder_SetupModeAndLimits re-runs.
   - Physical KEY_VIDEO stop precedence wins all state/race transitions and latches terminal session stop.
5. Immediate user disable & owned-only synthetic key release:
   - Disabling cancels pending continuation and releases only continuation-owned synthetic keys (including in
     RELEASING) without stopping an active clip.
6. Combined <ALT> OSD formatting & protected runtime / card-write restrictions:
   - Line 2 and Line 3 format MOV:%s LIM:%s AC:%s within G3X_DIAG_LINE_MAX_CHARS = 55 across all states.
   - Default build remains byte-identical to origin/main (24b8a024..., 124,097 B, _end 0x003686b0).
   - Boot, CreateTask_my (task_PhySw and task_InitFileModules only), task hooks, PORT-54 exclusion (SAVE:OFF),
     absence of runtime time-limit toggles, and all 14 write-blocking linker wrappers remain intact.
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

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
GUI_MENU_C = ROOT / "chdk-port/platform/g3x/gui_menu.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
DOC_PORT59 = ROOT / "docs/PORT59_MOVIE_COMBINED.md"
EVIDENCE_MANIFEST = ROOT / "docs/port34_evidence_manifest.json"
TRUSTED_SCOPES = ROOT / "docs/port34_trusted_scopes.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_COMMIT = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
PORT55_BUILD_COMMIT = "dc915e6257981f48223fa2f38839bc28e31c73cf"
PORT56_BUILD_COMMIT = "ded3832e4a6cc1cc8401f67cb454d5d420191844"
PORT57_BUILD_COMMIT = "ed374e7d332bce36a9c76682074aa9516e15e3be"
PORT58_BUILD_COMMIT = "6696c8390780043e0c5fc67c306143dacf0bcd7c"
PORT59_COMPAT_COMMIT = "c38d6c66dba62ee7b048a0cf56f52cbd1f567adc"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097
BASE_DEFAULT_END = "003686b0"

PORT59_COMBINED_SHA256 = "a29bd5d3aae297cbbdb34eae0cb6d96b5f804e4e3b4fea03304b0a34cc4d8fbf"
PORT59_COMBINED_SIZE = 134801
PORT59_COMBINED_END = "0036b4d0"

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

REQUIRED_PREREQS = [
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
    "combined": False,
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


def ensure_build_combined() -> None:
    bin_path = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
    elf_path = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "out/port59-movie-combined/port59_movie_combined_manifest.json"
    if (
        _BUILD_CACHE["combined"]
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
                "--out-dir",
                str(ROOT / "out/port59-movie-combined"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["combined"] = True


def setUpModule() -> None:
    ensure_build_default()
    ensure_build_combined()


def parse_function_instructions(disasm: str, symbol_name: str) -> list[dict[str, str]]:
    marker = f"<{symbol_name}>:"
    start_pos = disasm.find(marker)
    if start_pos == -1:
        return []
    lines = disasm[start_pos:].splitlines()
    instrs: list[dict[str, str]] = []
    for line in lines[1:]:
        line_s = line.strip()
        if not line_s:
            continue
        if re.match(r"^[0-9a-fA-F]+\s+<[^>]+>:", line):
            break
        if line_s == "...":
            continue
        m = re.match(
            r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{2,8}(?:\s+[0-9a-fA-F]{2,8})?)\s+([a-z0-9\._]+)\s*(.*)$",
            line,
        )
        if m:
            addr, raw_bytes, mnemonic, rest = m.groups()
            operands = rest.split(";")[0].strip()
            comment = rest.split(";")[1].strip() if ";" in rest else ""
            instrs.append({
                "addr": addr,
                "raw_bytes": raw_bytes.strip(),
                "mnemonic": mnemonic.lower(),
                "operands": operands,
                "comment": comment,
                "line": line.strip(),
            })
    return instrs


class _HostPort59CombinedHarness:
    """Compiles movie_rec.c, gui_diag.h, and gui_menu.c redraw logic with both G3X_MOVIE_NOLIMIT=1 and G3X_MOVIE_AUTOCONT_UI=1."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port59_host_sm_")
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
            "const char *host_get_nolimit_diag_str(void) { return g3x_movie_nolimit_diag_str(); }\n"
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

        so_path = tmp / "libport59_movie_combined.so"
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

        # Bind time-limit and continuation functions
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

        self.lib.g3x_diag_format_line2.argtypes = [ctypes.c_char_p]
        self.lib.g3x_diag_format_line2.restype = None
        self.lib.g3x_playback_menu_diag_format.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        self.lib.g3x_playback_menu_diag_format.restype = None
        self.lib.gui_diag_draw.argtypes = []
        self.lib.gui_diag_draw.restype = None
        self.lib.gui_menu_needs_redraw.argtypes = []
        self.lib.gui_menu_needs_redraw.restype = ctypes.c_int

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
        self.lib.host_get_nolimit_diag_str.argtypes = []
        self.lib.host_get_nolimit_diag_str.restype = ctypes.c_char_p
        self.lib.host_get_autocont_status_str.argtypes = []
        self.lib.host_get_autocont_status_str.restype = ctypes.c_char_p
        self.lib.host_get_last_drawn_line2.argtypes = []
        self.lib.host_get_last_drawn_line2.restype = ctypes.c_char_p
        self.lib.host_get_last_drawn_line3.argtypes = []
        self.lib.host_get_last_drawn_line3.restype = ctypes.c_char_p
        self.lib.host_sim_kbd_tick_before_poll.argtypes = [ctypes.c_int]
        self.lib.host_sim_kbd_tick_before_poll.restype = None

        # Bind globals
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
        """Execute one 10 ms my_kbd_read_keys() tick: g3x_movie_nolimit_poll() then g3x_movie_autocont_poll()."""
        self.lib.host_sim_kbd_tick_before_poll(1 if in_alt_mode else 0)
        if run_nolimit:
            self.lib.g3x_movie_nolimit_poll()
        self.lib.g3x_movie_autocont_poll()
        return self.state

    def menu_change(self, change: int) -> str:
        res = self.lib.g3x_movie_autocont_menu_change(change, 0)
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


class TestPort59FlagGatesAndUnsupportedCombinations(unittest.TestCase):
    def test_combined_profile_accepts_full_prerequisites_and_rejects_missing_prerequisites(self) -> None:
        expected_err = (
            "G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 "
            "G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 "
            "G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1"
        )
        # 1. Full combined flag stack (G3X_MOVIE_NOLIMIT=1 + G3X_MOVIE_AUTOCONT_UI=1 + 9 prerequisites) passes
        combined_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_AUTOCONT_UI=1"] + [
            f"-D{f}=1" for f in REQUIRED_PREREQS
        ]
        for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                ["cc", "-E", *combined_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

        # 2. Missing any of the 9 prerequisites fails even when G3X_MOVIE_NOLIMIT=1 is present
        for missing in REQUIRED_PREREQS:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_AUTOCONT_UI=1"] + [
                    f"-D{f}=1" for f in REQUIRED_PREREQS if f != missing
                ]
                for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
                    res = subprocess.run(
                        ["cc", "-E", *c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_err, res.stderr)

                make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_AUTOCONT_UI=1"] + [
                    f"{f}=1" for f in REQUIRED_PREREQS if f != missing
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

    def test_unsupported_feature_combinations_fail_explicitly(self) -> None:
        # 1. Combining G3X_MOVIE_NOLIMIT=1 and G3X_MOVIE_AUTOCONT=1 without G3X_MOVIE_AUTOCONT_UI=1 fails
        headless_msg = "Combining G3X_MOVIE_NOLIMIT=1 and G3X_MOVIE_AUTOCONT=1 requires G3X_MOVIE_AUTOCONT_UI=1"
        for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                [
                    "cc",
                    "-E",
                    "-DG3X_MOVIE_STATUS=1",
                    "-DG3X_MOVIE_NOLIMIT=1",
                    "-DG3X_MOVIE_AUTOCONT=1",
                    "-I",
                    str(DIAG_HEADER.parent),
                    "-x",
                    "c",
                    str(hdr),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(headless_msg, res.stderr)

        for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
            res = subprocess.run(
                ["make", "-f", str(mf), "G3X_MOVIE_STATUS=1", "G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_AUTOCONT=1"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(headless_msg, res.stderr)

        # 2. G3X_MOVIE_NOLIMIT=1 without G3X_MOVIE_STATUS=1 fails
        nolimit_msg = "G3X_MOVIE_NOLIMIT=1 requires G3X_MOVIE_STATUS=1"
        for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                ["cc", "-E", "-DG3X_MOVIE_NOLIMIT=1", "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(nolimit_msg, res.stderr)

        for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
            res = subprocess.run(
                ["make", "-f", str(mf), "G3X_MOVIE_NOLIMIT=1"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(nolimit_msg, res.stderr)

        # 3. Combined profile with G3X_CONF_SAVE=1 or FULL_HOOKS=1 fails across headers and Makefiles
        combined_c_flags = ["-DG3X_MOVIE_NOLIMIT=1", "-DG3X_MOVIE_AUTOCONT_UI=1"] + [
            f"-D{f}=1" for f in REQUIRED_PREREQS
        ]
        combined_make_args = ["G3X_MOVIE_NOLIMIT=1", "G3X_MOVIE_AUTOCONT_UI=1"] + [
            f"{f}=1" for f in REQUIRED_PREREQS
        ]
        for bad_flag in ("G3X_CONF_SAVE", "FULL_HOOKS"):
            expected_msg = f"G3X_MOVIE_AUTOCONT_UI=1 is incompatible with {bad_flag}=1"
            for hdr in (MOVIE_STATUS_H, DIAG_HEADER):
                res = subprocess.run(
                    ["cc", "-E", *combined_c_flags, f"-D{bad_flag}=1", "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(expected_msg, res.stderr)

            for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                res = subprocess.run(
                    ["make", "-f", str(mf), *combined_make_args, f"{bad_flag}=1"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(expected_msg, res.stderr)

        # 4. build_port43_dbuf.py CLI rejects unsupported combinations
        combined_cli = [
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
        ]
        for bad_cli, exp_err in (
            (["--conf-save"], "G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_AUTOCONT_UI=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-nolimit-alone"], "G3X_MOVIE_AUTOCONT_UI=1 requires"),
            (["--movie-autocont-alone"], "G3X_MOVIE_AUTOCONT_UI=1 requires"),
            (["--movie-status-alone"], "G3X_MOVIE_AUTOCONT_UI=1 requires"),
            (["--playback-menu-alone"], "G3X_MOVIE_AUTOCONT_UI=1 requires"),
        ):
            res = subprocess.run([*combined_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(exp_err, res.stderr)

        # CLI also rejects --movie-nolimit + --movie-autocont when --movie-autocont-ui is omitted
        headless_cli = [arg for arg in combined_cli if arg != "--movie-autocont-ui"]
        res = subprocess.run(headless_cli, cwd=str(ROOT), capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(headless_msg, res.stderr)


class TestPort59CombinedRuntimeBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort59CombinedHarness()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sm.close()

    def setUp(self) -> None:
        self.sm.reset()

    def _confirm_idle_and_enable(self) -> None:
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.can_enable, 1)
        self.assertEqual(self.sm.menu_change(1), "Ready")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")

    def _start_deliberate_physical_recording(self, hold_polls_into_rec: int = 0) -> None:
        if not self.sm.enabled:
            self._confirm_idle_and_enable()
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
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

        for _ in range(hold_polls_into_rec):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(False)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def test_boot_disabled_confirmed_idle_enable_and_deliberate_start_arming(self) -> None:
        # 1. Boots disabled on every boot; cannot enable before boot idle is confirmed
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")
        self.assertEqual(self.sm.nolimit_status_str, "?")
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.menu_change(1), "Off")
        self.assertEqual(self.sm.enabled, 0)

        # 2. Cannot enable while recording, stopping, in playback, or while physical KEY_VIDEO is held
        for bad_state in (1, 2, 3, 4):
            self.sm.reset()
            self.sm.movie_state.value = bad_state
            self.sm.step()
            self.assertEqual(self.sm.can_enable, 0)
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)

        self.sm.reset()
        self.sm.movie_state.value = 0
        self.sm.step()
        self.sm.lib.host_set_mode_play(1)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.sm.lib.host_set_mode_play(0)

        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.sm.set_physical_video_button(False)

        # 3. Enabling at confirmed idle succeeds and never initiates recording
        self.assertEqual(self.sm.can_enable, 1)
        self.assertEqual(self.sm.menu_change(1), "Ready")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        for _ in range(50):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.synth_owned, 0)

        # 4. Recording transition 0 -> 1 WITHOUT a deliberate physical press at IDLE does NOT arm continuation,
        #    even though g3x_movie_nolimit_poll() still patches max_frames to 0xFFFFFFFFU (LIM:OFF)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

        # 5. Return to IDLE, press physical KEY_VIDEO at IDLE, then transition 0 -> 1 -> arms to ARM!
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

    def test_nolimit_patch_adds_no_restart_trigger_and_bypasses_no_continuation_control(self) -> None:
        # 1. With continuation disabled (AC:OFF), starting recording patches max_frames to 0xFFFFFFFF (LIM:OFF)
        #    and stopping at 4 GiB Reason 3 triggers zero restart
        self.sm.movie_state.value = 0
        self.sm.step()
        self.assertEqual(self.sm.enabled, 0)
        self.sm.set_physical_video_button(True)
        self.sm.step()
        self.sm.set_physical_video_button(False)

        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 28000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")
        self.assertEqual(self.sm.ui_status_str, "OFF")

        # Clip hits 4 GiB Reason 3 while continuation is disabled -> no restart
        self.sm.projected_size.value = 0x100000200
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(150):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.restart_count, 0)

        # 2. When armed (AC:ARM) and max_frames is patched to 0xFFFFFFFF by g3x_movie_nolimit_poll(),
        #    recording continues past 54,000 frames (29:59); if a clip stops with stale/spurious stop_reason == 4
        #    while max_frames == 0xFFFFFFFF, Reason 4 is rejected and disarms to AC:FLT (STOP_FAULT)
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.sm.cur_frames.value = 90000  # Well past 54,000 frames (50 minutes @ 30fps)
        self.sm.stream_bytes.value = 0x90000000
        self.sm.projected_size.value = 0x90800000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.ui_status_str, "FLT")
        self.assertEqual(self.sm.press_calls.value, 0)

    def test_combined_reason_3_continuation_and_repatching_max_frames_on_continued_clips(self) -> None:
        # Clip 1: Deliberate physical start; SetupModeAndLimits sets max_frames=54000 after mr_rec_state=1
        self._confirm_idle_and_enable()
        self.sm.set_physical_video_button(True)
        self.sm.step()
        self.sm.set_physical_video_button(False)

        # Poll 1 of recording: mr_rec_state == 1, max_frames still 0 before SetupModeAndLimits finishes
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 0
        self.sm.cur_frames.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.max_frames.value, 0)
        self.assertEqual(self.sm.nolimit_status_str, "?")

        # Poll 2 of recording: SetupModeAndLimits writes 54000 to 0x0000C274 -> g3x_movie_nolimit_poll() patches to 0xFFFFFFFF
        self.sm.max_frames.value = 54000
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 2 * 1024 * 1024
        self.sm.projected_size.value = 4 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

        # Clip 1 records past 29:59 (e.g. 80,000 frames in 720p) and reaches 4 GiB Reason 3 size cap
        self.sm.cur_frames.value = 80000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2  # STOPPING
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.ui_status_str, "WAIT")
        self.assertEqual(self.sm.nolimit_status_str, "?")

        # Reaches IDLE (0) -> SETTLE (50 polls) -> PRESSING (6 polls) -> RELEASING (6 polls) -> WAIT_CONFIRM
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.ui_status_str, "SETL")
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
            self.assertEqual(self.sm.ui_status_str, "PRS")
            self.assertEqual(self.sm.synth_owned, 1)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
            self.assertEqual(self.sm.ui_status_str, "REL")
            self.assertEqual(self.sm.synth_owned, 0)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.ui_status_str, "CONF")

        # Clip 2 starts: MovieRecorder_SetupModeAndLimits (BL 0xFC097D72 @ 0xFC09A97C) resets max_frames to 107940
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 107940
        self.sm.cur_frames.value = 1
        self.sm.stream_bytes.value = 65536
        self.sm.projected_size.value = 65536
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        # g3x_movie_nolimit_poll() immediately re-patched max_frames on Clip 2!
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")

    def test_physical_stop_precedence_and_user_disable_owned_key_release(self) -> None:
        # 1. Physical KEY_VIDEO press during active RECORDING or pending continuation wins races and is terminal
        self._start_deliberate_physical_recording()
        self.sm.projected_size.value = 0x100000200
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.sm.set_physical_video_button(True)  # Same-poll race with Reason 3 stop
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 0
        for _ in range(80):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

        # 2. Disabling during active recording keeps recording running (LIM:OFF) and never presses/releases KEY_VIDEO
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.menu_change(-1), "Off")
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
        self.assertEqual(self.sm.movie_state.value, 1)
        self.assertEqual(self.sm.nolimit_status_str, "OFF")
        self.assertEqual(self.sm.press_calls.value, 0)
        self.assertEqual(self.sm.release_calls.value, 0)

        # 3. Disabling during PRESSING releases continuation-owned synthetic key without disturbing unrelated keys
        self.sm.reset()
        self.sm.kbd_new_state[0] &= ~0x00000010
        self.sm.kbd_mod_state[0] &= ~0x00000010
        self._start_deliberate_physical_recording()
        self.sm.cur_frames.value = 30000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        self.sm.step()
        self.sm.projected_size.value = 0x100000200
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.synth_owned, 1)
        self.assertTrue(self.sm.mod_video_pressed)

        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertFalse(self.sm.mod_video_pressed)
        self.assertFalse(self.sm.physw_video_pressed)
        self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)

        # 4. In RELEASING (synth_owned == 0), non-owned synthetic key state in kbd_mod_state[0] is never released
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.cur_frames.value = 30000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        self.sm.step()
        self.sm.projected_size.value = 0x100000200
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.synth_owned, 0)
        rel_before = self.sm.release_calls.value
        self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
        self.assertEqual(self.sm.step(in_alt_mode=True), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.release_calls.value, rel_before)
        self.assertTrue(self.sm.mod_video_pressed)

    def test_combined_alt_diag_line2_and_line3_format_within_55_chars(self) -> None:
        self.sm.menu_open_count.value = 99999
        self.sm.sync_restore_count.value = 99999
        self.sm.poll_restore_count.value = 99999
        self.sm.playback_open_count.value = 99999
        self.sm.playback_edit_count.value = 99999

        # Boot idle: MOV:IDLE LIM:? AC:OFF
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertEqual(line2, "MENU:9999 SAVE:OFF MOV:IDLE LIM:? AC:OFF Rs:9999")
        self.assertEqual(line3, "MENU:9999 SAVE:OFF MOV:IDLE LIM:? AC:OFF ED:9999")
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)

        # Armed & recording with limit defeated: MOV:REC LIM:OFF AC:ARM
        self._start_deliberate_physical_recording()
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertEqual(line2, "MENU:9999 SAVE:OFF MOV:REC LIM:OFF AC:ARM Rs:9999")
        self.assertEqual(line3, "MENU:9999 SAVE:OFF MOV:REC LIM:OFF AC:ARM ED:9999")
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)

        # Worst-case length check across all 9 AC tokens and all 3 MOV/LIM tokens
        self.sm.cur_frames.value = 30000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        self.sm.step()
        self.sm.projected_size.value = 0x100000200
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertIn("MOV:? LIM:? AC:WAIT", line2)
        self.assertIn("MOV:? LIM:? AC:WAIT", line3)
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)

        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertEqual(line2, "MENU:9999 SAVE:OFF MOV:IDLE LIM:? AC:SETL Rs:9999")
        self.assertEqual(line3, "MENU:9999 SAVE:OFF MOV:IDLE LIM:? AC:SETL ED:9999")
        self.assertEqual(len(line2), 49)
        self.assertEqual(len(line3), 49)
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)


class TestPort59BuildArtifactsDisassemblyAndSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_combined()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.comb_bin = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
        cls.comb_elf = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.comb_obj = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.comb_manifest = ROOT / "out/port59-movie-combined/port59_movie_combined_manifest.json"
        cls.comb_stage = ROOT / "out/port59-movie-combined/stage_chdk"

    def test_default_build_byte_identical_to_origin_main(self) -> None:
        self.assertTrue(self.default_bin.is_file())
        self.assertEqual(sha256_file(self.default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(self.default_bin.stat().st_size, BASE_DEFAULT_SIZE)

        res = subprocess.run([str(NM), str(self.default_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", res.stdout)
        self.assertNotIn("g3x_movie_nolimit_poll", res.stdout)
        self.assertNotIn("g3x_movie_autocont_poll", res.stdout)

    def test_combined_manifest_flags_and_reused_commits(self) -> None:
        self.assertTrue(self.comb_bin.is_file())
        self.assertTrue(self.comb_elf.is_file())
        self.assertTrue(self.comb_obj.is_file())
        self.assertTrue(self.comb_manifest.is_file())

        m = json.loads(self.comb_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_id"], "port59_movie_combined_manifest")
        self.assertEqual(m["milestone"], "PORT-59")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_COMMIT)
        self.assertEqual(m["card_writes"], "disabled")
        self.assertEqual(sha256_file(self.comb_bin), PORT59_COMBINED_SHA256)
        self.assertEqual(self.comb_bin.stat().st_size, PORT59_COMBINED_SIZE)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT59_COMBINED_SHA256)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], PORT59_COMBINED_SIZE)
        self.assertEqual(m["_end"], f"0x{PORT59_COMBINED_END}")

        expected_commits = {
            "origin_main": ORIGIN_MAIN_COMMIT,
            "port55_movie_status": PORT55_BUILD_COMMIT,
            "port56_movie_nolimit": PORT56_BUILD_COMMIT,
            "port57_movie_autocont": PORT57_BUILD_COMMIT,
            "port58_movie_control": PORT58_BUILD_COMMIT,
            "port59_compat": PORT59_COMPAT_COMMIT,
        }
        self.assertEqual(m["reused_commits"], expected_commits)
        for key, commit_hash in expected_commits.items():
            res = subprocess.run(
                ["git", "rev-parse", "--verify", f"{commit_hash}^{{commit}}"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Unresolvable commit for {key}: {commit_hash}")

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
        ):
            self.assertIn(req_flag, flags)
        for forbidden_flag in ("G3X_CONF_SAVE=1", "FULL_HOOKS=1"):
            self.assertNotIn(forbidden_flag, flags)

    def test_combined_disassembly_write_allowlist_poll_order_and_protected_runtime(self) -> None:
        # 1. Verify symbols in combined main.elf
        nm_out = subprocess.check_output([str(NM), str(self.comb_elf)], text=True)
        for req_sym in (
            "g3x_get_movie_status",
            "g3x_movie_nolimit_poll",
            "g3x_get_movie_max_frames",
            "g3x_get_movie_cur_frames",
            "g3x_movie_autocont_poll",
            "g3x_movie_autocont_is_enabled",
            "g3x_movie_autocont_can_enable",
            "g3x_movie_autocont_set_enabled",
            "g3x_movie_autocont_get_disarm_reason",
            "g3x_movie_autocont_ui_status_str",
            "g3x_movie_autocont_menu_change",
            "g3x_movie_autocont_get_restart_count",
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
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in combined main.elf")

        for excluded_sym in (
            "g3x_conf_save_active",
            "g3x_is_safe_chdk_write_path",
            "g3x_is_conf_file_path",
        ):
            self.assertNotIn(excluded_sym, nm_out, f"Excluded PORT-54 symbol {excluded_sym} present in combined main.elf")

        # 2. Verify g3x_movie_nolimit_poll writes strictly 0xFFFFFFFF to 0x0000C274 only,
        #    and all 10 MovieRecorder accessors emit zero stores
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
        for target_path, desc in ((self.comb_obj, "movie_rec.o"), (self.comb_elf, "main.elf")):
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

            # g3x_movie_nolimit_poll never calls kbd_key_press, kbd_key_release, or autocont functions
            nolimit_instrs = parse_function_instructions(disasm, "g3x_movie_nolimit_poll")
            for instr in nolimit_instrs:
                self.assertNotIn("kbd_key_", instr["line"])
                self.assertNotIn("autocont", instr["line"])
                self.assertNotIn("40dac", instr["line"].lower())

            for fn in accessors:
                instrs = parse_function_instructions(disasm, fn)
                self.assertGreater(len(instrs), 0, f"Missing instructions for {fn} in {desc}")
                for instr in instrs:
                    mnem = instr["mnemonic"]
                    self.assertFalse(
                        mnem.startswith("str") or mnem.startswith("stm") or mnem.startswith("push"),
                        f"Forbidden store '{mnem}' in read-only accessor {fn} ({desc}): {instr['line']}",
                    )

            # Zero stores to any MovieRecorder address other than 0x0000C274
            for fhex in ("c078", "c0c0", "c0c8", "c0d4", "c0d8", "c0e4", "c278", "c290", "c298", "c2a0", "c2a8"):
                for match in re.finditer(
                    rf"^\s*([0-9a-f]+):\s+([0-9a-f\s]+?)\t([a-z0-9\._]+)\s*([^;\n]*;\s*.*{fhex}.*)",
                    disasm,
                    re.M | re.I,
                ):
                    mnem = match.group(3).lower()
                    self.assertFalse(
                        mnem.startswith("str") or mnem.startswith("stm"),
                        f"Forbidden store referencing 0x0000{fhex} in {desc}: {match.group(0)}",
                    )

        # 3. Verify my_kbd_read_keys calls g3x_movie_nolimit_poll before g3x_movie_autocont_poll
        elf_disasm = subprocess.check_output([str(OBJDUMP), "-d", str(self.comb_elf)], text=True)
        kbd_instrs = parse_function_instructions(elf_disasm, "my_kbd_read_keys")
        nolimit_call_idx = next((idx for idx, i in enumerate(kbd_instrs) if "g3x_movie_nolimit_poll" in i["line"]), -1)
        autocont_call_idx = next((idx for idx, i in enumerate(kbd_instrs) if "g3x_movie_autocont_poll" in i["line"]), -1)
        self.assertGreaterEqual(nolimit_call_idx, 0, "g3x_movie_nolimit_poll not called in my_kbd_read_keys")
        self.assertGreaterEqual(autocont_call_idx, 0, "g3x_movie_autocont_poll not called in my_kbd_read_keys")
        self.assertLess(nolimit_call_idx, autocont_call_idx, "g3x_movie_nolimit_poll must run before g3x_movie_autocont_poll")

        # 4. Verify CreateTask_my in staged boot.c hooks only task_PhySw and task_InitFileModules
        staged_boot_c = (self.comb_stage / "platform/g3x/sub/110c/boot.c").read_text(encoding="utf-8")
        self.assertIn("0xfc1283ad", staged_boot_c.lower())  # task_PhySw
        self.assertIn("0xfc0bd071", staged_boot_c.lower())  # task_InitFileModules
        self.assertNotIn("0xfc09ac19", staged_boot_c.lower())  # task_MovieRecord unhooked

        # 5. Verify staged core/gui.c adds only "Auto-Continue Movie" and no runtime time-limit toggle
        staged_gui_c = (self.comb_stage / "core/gui.c").read_text(encoding="utf-8")
        self.assertIn('"Auto-Continue Movie"', staged_gui_c)
        self.assertIn("g3x_movie_autocont_menu_change", staged_gui_c)
        self.assertNotIn("g3x_movie_nolimit", staged_gui_c)

        # 6. Verify Evidence Manifest passes offline validator with zero new ROM reads
        res = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "tools/port11c_evidence_validator.py"),
                "--manifest",
                str(EVIDENCE_MANIFEST),
                "--trusted-scopes",
                str(TRUSTED_SCOPES),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Result: VALID (0 errors, 0 warnings)", res.stdout)

    def test_doc_records_reused_commits_flags_and_artifact_hashes(self) -> None:
        doc_text = DOC_PORT59.read_text(encoding="utf-8")
        for token in (
            ORIGIN_MAIN_COMMIT,
            PORT55_BUILD_COMMIT,
            PORT56_BUILD_COMMIT,
            PORT57_BUILD_COMMIT,
            PORT58_BUILD_COMMIT,
            PORT59_COMPAT_COMMIT,
            BASE_DEFAULT_SHA256,
            PORT59_COMBINED_SHA256,
            f"0x{PORT59_COMBINED_END}",
            "G3X_MOVIE_NOLIMIT=1",
            "G3X_MOVIE_AUTOCONT_UI=1",
            "port59_movie_combined_manifest.json",
        ):
            self.assertIn(token, doc_text, f"Missing '{token}' in docs/PORT59_MOVIE_COMBINED.md")

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
            self.assertEqual(res.returncode, 0, f"Unresolvable commit hash in docs/PORT59_MOVIE_COMBINED.md: {commit_hash}")


if __name__ == "__main__":
    unittest.main()
