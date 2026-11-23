"""Offline unit and integration tests for PORT-58 (G3X_MOVIE_AUTOCONT_UI=1).

Verifies:
1. Prerequisite & incompatibility enforcement:
   - G3X_MOVIE_AUTOCONT_UI=1 explicitly requires G3X_MOVIE_AUTOCONT=1, G3X_MOVIE_STATUS=1,
     G3X_GUI_MENU=1, G3X_GUI_SYNC=1, G3X_GUI_DBUF=1, G3X_GUI_NOOVERDRAW=1, G3X_KBD_CHECK=1,
     G3X_GUI_DIAG=1, and G3X_GUI_SHADOW2=1 across C headers, Makefiles, and build_port43_dbuf.py.
   - Incompatible flags (G3X_MOVIE_NOLIMIT=1, G3X_CONF_SAVE=1, FULL_HOOKS=1, *-alone) fail clearly.
2. Volatile menu toggle & non-persistence:
   - Starts disabled every boot, never persists in struct Conf / conf_info[], enables only at
     confirmed idle in record mode with the physical movie key released, and never starts recording.
3. Deliberate physical recording start arming:
   - Only a subsequent deliberate physical recording start (physical KEY_VIDEO press observed at
     confirmed IDLE after enabling, followed by IDLE -> RECORDING) arms continuation; a recording-state
     transition 0 -> 1 alone cannot arm it.
4. Immediate disable & continuation-owned synthetic-key release (including in RELEASING):
   - Disable cancels pending continuation without stopping an active clip and releases only
     continuation-owned synthetic keys.
   - Unconditional key-release behavior in RELEASING is removed; RELEASING never calls kbd_key_release
     or touches physw_status[0] when synth_owned == 0.
5. Terminal physical-stop precedence:
   - Physical movie-button stop wins races across all states and remains terminal for the session
     until confirmed idle + physical key release + a new deliberate physical start.
6. 5-category status projections & explicit reason semantics without polling overwrite:
   - Disabled (OFF/Off), Enabled/Unarmed (RDY/Ready), Armed (ARM/Armed),
     Waiting/Restarting (WAIT/SETL/PRS/REL/CONF), and Fault/Disarmed (FLT/Fault).
   - User disable displays OFF (G3X_AUTOCONT_REASON_USER_OFF); playback (G3X_AUTOCONT_REASON_PLAYBACK),
     invalid-state (G3X_AUTOCONT_REASON_INVALID_STATE), stop-fault (G3X_AUTOCONT_REASON_STOP_FAULT),
     and timeout (G3X_AUTOCONT_REASON_TIMEOUT) have explicit reason semantics that repeated polling
     never overwrites.
7. Existing rendering & diagnostic line limit:
   - Line 2 and Line 3 diagnostic formatters reuse existing rendering within G3X_DIAG_LINE_MAX_CHARS = 55.
   - Boot, task hooks, CreateTask, and firmware interfaces remain unchanged; MovieRecorder RAM is 100%
     read-only; runtime file writes are disabled; G3X_MOVIE_NOLIMIT is off.
8. Default build byte-identity & documentation reconciliation:
   - Default build remains byte-identical to origin/main default (24b8a024..., 124,097 B, _end 0x003686b0).
   - docs/PORT58_MOVIE_CONTROL.md review notes, resolving git commit hashes, function/constant names,
     and source citations are verified against the repository.
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

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
FULL_MOVIE_STATUS_H = ROOT / "full_build/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
FULL_MOVIE_REC_C = ROOT / "full_build/g3x/sub/110c/movie_rec.c"
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
GUI_MENU_C = ROOT / "chdk-port/platform/g3x/gui_menu.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
DOC_PORT58 = ROOT / "docs/PORT58_MOVIE_CONTROL.md"
EVIDENCE_MANIFEST = ROOT / "docs/port34_evidence_manifest.json"
TRUSTED_SCOPES = ROOT / "docs/port34_trusted_scopes.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_COMMIT = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"
PORT57_BUILD_COMMIT = "ed374e7d332bce36a9c76682074aa9516e15e3be"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097
BASE_DEFAULT_END = "003686b0"

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

INCOMPATIBLE_FLAGS = [
    "G3X_MOVIE_NOLIMIT",
    "G3X_CONF_SAVE",
    "FULL_HOOKS",
]

_BUILD_CACHE = {
    "default": False,
    "candidate": False,
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


def ensure_build_candidate() -> None:
    bin_path = ROOT / "out/port58-movie-control/DISKBOOT.BIN"
    elf_path = ROOT / "out/port58-movie-control/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "out/port58-movie-control/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "out/port58-movie-control/port58_movie_control_manifest.json"
    if (
        _BUILD_CACHE["candidate"]
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
                "--movie-autocont",
                "--movie-autocont-ui",
                "--out-dir",
                str(ROOT / "out/port58-movie-control"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["candidate"] = True


def setUpModule() -> None:
    ensure_build_default()
    ensure_build_candidate()


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


class _HostPort58Harness:
    """Compiles movie_rec.c and gui_diag.h as a host shared library and drives them via ctypes."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port58_host_sm_")
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
            "}\n",
            encoding="utf-8",
        )

        so_path = tmp / "libport58_autocont_ui.so"
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

        # Bind continuation and UI functions
        self.lib.g3x_movie_autocont_poll.argtypes = []
        self.lib.g3x_movie_autocont_poll.restype = None
        self.lib.g3x_movie_autocont_reset.argtypes = []
        self.lib.g3x_movie_autocont_reset.restype = None
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
        self.lib.g3x_movie_autocont_menu_cb.argtypes = []
        self.lib.g3x_movie_autocont_menu_cb.restype = None
        self.lib.g3x_movie_autocont_get_menu_bool_ptr.argtypes = []
        self.lib.g3x_movie_autocont_get_menu_bool_ptr.restype = ctypes.POINTER(ctypes.c_int)
        self.lib.host_simulate_bool_menu_toggle.argtypes = []
        self.lib.host_simulate_bool_menu_toggle.restype = None

        self.lib.g3x_diag_format_line2.argtypes = [ctypes.c_char_p]
        self.lib.g3x_diag_format_line2.restype = None
        self.lib.g3x_playback_menu_diag_format.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        self.lib.g3x_playback_menu_diag_format.restype = None

        self.lib.host_set_mode_play.argtypes = [ctypes.c_int]
        self.lib.host_set_mode_play.restype = None
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
        self.playback_menu_open_count = ctypes.c_uint.in_dll(self.lib, "g3x_playback_menu_open_count")
        self.playback_menu_item_edit_count = ctypes.c_uint.in_dll(self.lib, "g3x_playback_menu_item_edit_count")
        self.sync_restore_count = ctypes.c_uint.in_dll(self.lib, "g3x_diag_sync_restore_count")
        self.poll_restore_count = ctypes.c_uint.in_dll(self.lib, "g3x_diag_poll_restore_count")

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
        self.lib.host_set_mode_play(0)
        self.lib.g3x_movie_autocont_reset()

    def set_physical_video_button(self, pressed: bool) -> None:
        if pressed:
            self.kbd_new_state[0] &= ~G3X_KEY_VIDEO_BIT
        else:
            self.kbd_new_state[0] |= G3X_KEY_VIDEO_BIT

    def step(self, in_alt_mode: bool = False) -> int:
        self.lib.host_sim_kbd_tick_before_poll(1 if in_alt_mode else 0)
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
    def disarm_reason(self) -> int:
        return self.lib.g3x_movie_autocont_get_disarm_reason()

    @property
    def faulted(self) -> int:
        return self.lib.g3x_movie_autocont_is_faulted()

    @property
    def reason_str(self) -> str:
        return self.lib.g3x_movie_autocont_reason_str().decode("utf-8")

    @property
    def ui_status_str(self) -> str:
        return self.lib.g3x_movie_autocont_ui_status_str().decode("utf-8")

    @property
    def menu_str(self) -> str:
        return self.lib.g3x_movie_autocont_menu_str().decode("utf-8")

    def menu_change(self, change: int, arg: int = 0) -> str:
        return self.lib.g3x_movie_autocont_menu_change(change, arg).decode("utf-8")

    def format_line2(self) -> str:
        buf = ctypes.create_string_buffer(128)
        self.lib.g3x_diag_format_line2(buf)
        return buf.value.decode("utf-8")

    def format_line3(self) -> str:
        buf = ctypes.create_string_buffer(128)
        self.lib.g3x_playback_menu_diag_format(buf, 128)
        return buf.value.decode("utf-8")

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


class TestPort58FlagPrerequisitesAndIncompatibilities(unittest.TestCase):
    def test_c_headers_and_makefiles_reject_missing_prerequisites(self) -> None:
        expected_err = (
            "G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 "
            "G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 "
            "G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1"
        )
        for missing in REQUIRED_PREREQS:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_MOVIE_AUTOCONT_UI=1"] + [
                    f"-D{f}=1" for f in REQUIRED_PREREQS if f != missing
                ]
                for hdr in (MOVIE_STATUS_H, FULL_MOVIE_STATUS_H, DIAG_HEADER):
                    res = subprocess.run(
                        ["cc", "-E", *c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0, f"Expected failure when {missing} missing in {hdr}")
                    self.assertIn(expected_err, res.stderr)

                make_args = ["G3X_MOVIE_AUTOCONT_UI=1"] + [
                    f"{f}=1" for f in REQUIRED_PREREQS if f != missing
                ]
                for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                    res = subprocess.run(
                        ["make", "-f", str(mf), *make_args],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0, f"Expected make failure when {missing} missing in {mf}")
                    self.assertIn(expected_err, res.stderr)

        # Complete prerequisite stack passes C preprocessor check on all headers
        full_c_flags = ["-DG3X_MOVIE_AUTOCONT_UI=1"] + [f"-D{f}=1" for f in REQUIRED_PREREQS]
        for hdr in (MOVIE_STATUS_H, FULL_MOVIE_STATUS_H, DIAG_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_c_headers_makefiles_and_build_script_reject_incompatible_flags(self) -> None:
        base_c_flags = ["-DG3X_MOVIE_AUTOCONT_UI=1"] + [f"-D{f}=1" for f in REQUIRED_PREREQS]
        base_make_args = ["G3X_MOVIE_AUTOCONT_UI=1"] + [f"{f}=1" for f in REQUIRED_PREREQS]

        for bad_flag in INCOMPATIBLE_FLAGS:
            expected_msg = f"G3X_MOVIE_AUTOCONT_UI=1 is incompatible with {bad_flag}=1"
            with self.subTest(incompatible=bad_flag):
                for hdr in (MOVIE_STATUS_H, FULL_MOVIE_STATUS_H, DIAG_HEADER):
                    res = subprocess.run(
                        [
                            "cc",
                            "-E",
                            *base_c_flags,
                            f"-D{bad_flag}=1",
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
                    self.assertIn(expected_msg, res.stderr)

                for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                    res = subprocess.run(
                        ["make", "-f", str(mf), *base_make_args, f"{bad_flag}=1"],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(expected_msg, res.stderr)

        # Also verify build_port43_dbuf.py CLI rejects missing prerequisites and incompatible flags
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
            "--movie-autocont",
            "--movie-autocont-ui",
        ]
        for bad_cli, exp_err in (
            (["--movie-nolimit"], "G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_MOVIE_NOLIMIT=1"),
            (["--conf-save"], "G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_AUTOCONT_UI=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-autocont-alone"], "G3X_MOVIE_AUTOCONT_UI=1 requires"),
        ):
            res = subprocess.run([*base_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(exp_err, res.stderr)

        for omit_cli in ("--movie-autocont", "--movie-status", "--gui-menu", "--gui-sync", "--shadow2", "--gui-diag"):
            cli = [arg for arg in base_cli if arg != omit_cli]
            res = subprocess.run(cli, cwd=str(ROOT), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0, f"Expected CLI failure when omitting {omit_cli}")
            self.assertIn("G3X_MOVIE_AUTOCONT_UI=1 requires", res.stderr)


class TestPort58VolatileControlAndReasonSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort58Harness()

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
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.menu_str, "Ready")

    def _start_deliberate_physical_recording(self, hold_polls_into_rec: int = 0) -> None:
        if not self.sm.enabled:
            self._confirm_idle_and_enable()
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        if hold_polls_into_rec == 0:
            self.sm.set_physical_video_button(False)

        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")

        for _ in range(hold_polls_into_rec):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(False)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def test_volatile_toggle_starts_disabled_never_persists_and_enables_only_at_confirmed_idle(self) -> None:
        # 1. Boot default is disabled (OFF)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.faulted, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")
        self.assertEqual(self.sm.lib.g3x_movie_autocont_get_menu_bool_ptr().contents.value, 0)

        # 2. Refused before boot idle is confirmed by polling (saw_boot_idle == 0)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_change(1), "Off")
        self.sm.lib.host_simulate_bool_menu_toggle()
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_get_menu_bool_ptr().contents.value, 0)

        # 3. Confirm boot idle, then test refusal under each invalid enable condition
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.can_enable, 1)

        # 3a. Refused when physical KEY_VIDEO is held down
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.menu_change(1), "Off")
        self.sm.lib.host_simulate_bool_menu_toggle()
        self.assertEqual(self.sm.enabled, 0)
        self.sm.set_physical_video_button(False)

        # 3b. Refused in playback mode (mode_play != 0)
        self.sm.lib.host_set_mode_play(1)
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.sm.lib.host_set_mode_play(0)

        # 3c. Refused when mr_rec_state is RECORDING (1), STOPPING (2..4), or invalid (-1, 5)
        for non_idle_state in (1, 2, 3, 4, -1, 5):
            self.sm.movie_state.value = non_idle_state
            self.assertEqual(self.sm.can_enable, 0)
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
            self.assertEqual(self.sm.enabled, 0)
            self.assertEqual(self.sm.ui_status_str, "OFF")

        # 3d. Even when movie_state returns to 0, prev_rec_state is non-zero until a poll confirms IDLE
        self.sm.movie_state.value = 1
        self.sm.step()
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.can_enable, 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)

        # Next poll confirms IDLE (0): enabling now succeeds and never starts recording
        self.sm.step()
        self.assertEqual(self.sm.can_enable, 1)
        self.assertEqual(self.sm.menu_change(1), "Ready")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.press_calls.value, 0)
        self.assertEqual(self.sm.release_calls.value, 0)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertFalse(self.sm.physw_video_pressed)

        # 4. Simulate reboot (reset): volatile toggle returns to disabled (OFF)
        self.sm.reset()
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")

    def test_only_subsequent_deliberate_physical_start_arms_continuation(self) -> None:
        # 1. Recording transition while disabled never arms
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.sm.step()
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 100
        self.sm.step()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "OFF")

        # 2. Pre-enable physical button press cannot carry over into after enabling
        self.sm.reset()
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.sm.step()
        self.sm.set_physical_video_button(False)
        self.sm.step()
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")

        # Transition 0 -> 1 alone (without a physical button press AFTER enabling) MUST NOT arm!
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 50
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        for _ in range(10):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.ui_status_str, "RDY")

        # Even if that un-armed clip stops at max_frames with Reason 4, it never triggers continuation
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        for _ in range(60):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

        # 3. Transition 0 -> 1 where physical KEY_VIDEO is pressed on the RECORDING poll without being seen in IDLE refuses to arm
        self.sm.set_physical_video_button(True)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 0)

        # 4. If user presses and releases KEY_VIDEO in IDLE, but recording doesn't start within 200 polls, the idle press expires
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        # Transition 0 -> 1 after expiry is treated as a state transition alone and does not arm
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # 5. Now perform a deliberate physical start from IDLE -> arms cleanly!
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")

    def test_disable_cancels_continuation_without_stopping_clip_and_releases_only_owned_keys_including_in_releasing(self) -> None:
        # 1. Disable while Armed (RECORDING): does not stop active clip, emits zero key press/release calls
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.press_calls.value, 0)
        self.assertEqual(self.sm.release_calls.value, 0)

        self.assertEqual(self.sm.menu_change(1), "Off")
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.press_calls.value, 0)
        self.assertEqual(self.sm.release_calls.value, 0)

        # Clip continues recording in firmware (movie_state == 1) and later stops at max_frames (Reason 4): no restart!
        for _ in range(10):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.ui_status_str, "OFF")
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        for _ in range(100):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.release_calls.value, 0)
            self.assertEqual(self.sm.ui_status_str, "OFF")

        # 2. Disable during WAIT_IDLE and SETTLE (synth_owned == 0): zero key releases
        for cancel_in_settle in (False, True):
            self.sm.reset()
            self._start_deliberate_physical_recording()
            self.sm.cur_frames.value = 54000
            self.sm.stop_reason.value = 4
            self.sm.movie_state.value = 0 if cancel_in_settle else 2
            expected_st = G3X_AUTOCONT_SETTLE if cancel_in_settle else G3X_AUTOCONT_WAIT_IDLE
            self.assertEqual(self.sm.step(), expected_st)
            self.assertEqual(self.sm.synth_owned, 0)
            rel_before = self.sm.release_calls.value

            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
            self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.ui_status_str, "OFF")
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
            self.assertEqual(self.sm.release_calls.value, rel_before)

        # 3. Disable during PRESSING (synth_owned == 1): releases owned synthetic key once and cancels restart
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.synth_owned, 1)
        self.assertTrue(self.sm.mod_video_pressed)
        self.assertTrue(self.sm.physw_video_pressed)
        rel_before = self.sm.release_calls.value

        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertEqual(self.sm.release_calls.value, rel_before + 1)
        self.assertFalse(self.sm.mod_video_pressed)
        self.assertFalse(self.sm.physw_video_pressed)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "OFF")

        # 4. RELEASING state: verify unconditional key-release behavior is removed!
        # Once PRESSING completes its final poll and releases the owned synthetic key,
        # RELEASING has synth_owned == 0 and must NEVER call kbd_key_release or clobber unowned kbd_mod_state[0].
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)

        # Next poll finishes PRESSING (releasing owned synthetic key once) and enters RELEASING
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertEqual(self.sm.ui_status_str, "REL")
        self.assertEqual(self.sm.menu_str, "Restart")
        rel_after_pressing_end = self.sm.release_calls.value
        self.assertEqual(rel_after_pressing_end, 1)

        # Simulate an unowned external modifier bit on KEY_VIDEO during RELEASING:
        # because continuation no longer owns the synthetic key (synth_owned == 0),
        # RELEASING polls and disabling in RELEASING must NOT call kbd_key_release(KEY_VIDEO)!
        self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
        self.assertEqual(self.sm.step(in_alt_mode=True), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.release_calls.value, rel_after_pressing_end)
        self.assertTrue(self.sm.mod_video_pressed)

        # Disabling during RELEASING also does not call kbd_key_release because synth_owned == 0
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
        self.assertEqual(self.sm.release_calls.value, rel_after_pressing_end)
        self.assertTrue(self.sm.mod_video_pressed)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "OFF")

    def test_physical_movie_button_stop_remains_terminal_until_new_deliberate_physical_start(self) -> None:
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")

        # User presses physical movie button during RECORDING to stop the session
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.assertEqual(self.sm.reason_str, "STOP")
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "RDY")

        # Terminal for the session even if firmware reaches Reason 4 before stopping
        self.sm.set_physical_video_button(False)
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)

        # Reaches IDLE (0) with physical button released -> cancel_latched clears
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 0)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)

        # A recording-state transition 0 -> 1 alone still cannot re-arm it!
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # Only a new deliberate physical start from IDLE re-arms continuation
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)

    def test_all_five_status_projections_and_explicit_reason_semantics_without_polling_overwrite(self) -> None:
        # Category 1: Disabled ("OFF" / "Off")
        self.assertEqual(self.sm.ui_status_str, "OFF")
        self.assertEqual(self.sm.menu_str, "Off")

        # Polling in playback mode or invalid state while ALREADY disabled ("OFF") never overwrites OFF with FLT!
        self.sm.lib.host_set_mode_play(1)
        for _ in range(50):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.ui_status_str, "OFF")
            self.assertEqual(self.sm.menu_str, "Off")
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.sm.lib.host_set_mode_play(0)
        self.sm.movie_state.value = 99
        for _ in range(50):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.ui_status_str, "OFF")
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)

        # Category 2: Enabled / Unarmed ("RDY" / "Ready")
        self.sm.reset()
        self._confirm_idle_and_enable()
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.menu_str, "Ready")

        # Category 3: Armed ("ARM" / "Armed")
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.ui_status_str, "ARM")
        self.assertEqual(self.sm.menu_str, "Armed")

        # Category 4: Waiting / Restarting ("WAIT", "SETL", "PRS", "REL", "CONF")
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.ui_status_str, "WAIT")
        self.assertEqual(self.sm.menu_str, "Wait")

        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.ui_status_str, "SETL")
        self.assertEqual(self.sm.menu_str, "Settle")
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.ui_status_str, "PRS")
        self.assertEqual(self.sm.menu_str, "Restart")
        for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.ui_status_str, "REL")
        self.assertEqual(self.sm.menu_str, "Restart")
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)

        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.ui_status_str, "CONF")
        self.assertEqual(self.sm.menu_str, "Confirm")

        # Category 5a: Fault / Disarmed on WAIT_CONFIRM timeout (G3X_AUTOCONT_REASON_TIMEOUT)
        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.faulted, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
        self.assertEqual(self.sm.reason_str, "TMO")
        self.assertEqual(self.sm.ui_status_str, "FLT")
        self.assertEqual(self.sm.menu_str, "Fault")

        # Repeated polling across IDLE, invalid movie_state, and playback mode must NEVER overwrite TIMEOUT!
        for _ in range(30):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
            self.assertEqual(self.sm.ui_status_str, "FLT")
        self.sm.movie_state.value = 99
        for _ in range(30):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
            self.assertEqual(self.sm.ui_status_str, "FLT")
        self.sm.lib.host_set_mode_play(1)
        for _ in range(30):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
            self.assertEqual(self.sm.ui_status_str, "FLT")

        # User disable while still in playback mode clears FLT to OFF (USER_OFF), and repeated polling preserves OFF!
        self.assertEqual(self.sm.menu_change(-1), "Off")
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
        self.assertEqual(self.sm.reason_str, "USER")
        self.assertEqual(self.sm.faulted, 0)
        self.assertEqual(self.sm.ui_status_str, "OFF")
        for _ in range(50):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_USER_OFF)
            self.assertEqual(self.sm.ui_status_str, "OFF")

        # Category 5b: Fault / Disarmed on Playback entry while enabled/armed (G3X_AUTOCONT_REASON_PLAYBACK)
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.lib.host_set_mode_play(1)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.faulted, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
        self.assertEqual(self.sm.reason_str, "PLAY")
        self.assertEqual(self.sm.ui_status_str, "FLT")
        # Subsequent invalid movie_state or return to record IDLE does not overwrite PLAYBACK reason
        self.sm.movie_state.value = -1
        for _ in range(20):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
        self.sm.lib.host_set_mode_play(0)
        self.sm.movie_state.value = 0
        for _ in range(20):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
            self.assertEqual(self.sm.ui_status_str, "FLT")

        # Category 5c: Fault / Disarmed on Invalid movie state (G3X_AUTOCONT_REASON_INVALID_STATE)
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.movie_state.value = 6
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.faulted, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
        self.assertEqual(self.sm.reason_str, "STATE")
        self.assertEqual(self.sm.ui_status_str, "FLT")
        # Subsequent playback mode or return to record IDLE does not overwrite INVALID_STATE reason
        self.sm.lib.host_set_mode_play(1)
        for _ in range(20):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
        self.sm.lib.host_set_mode_play(0)
        self.sm.movie_state.value = 0
        for _ in range(20):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
            self.assertEqual(self.sm.ui_status_str, "FLT")

        # Category 5d: Fault / Disarmed on Ineligible stop reason (G3X_AUTOCONT_REASON_STOP_FAULT)
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 2  # Card space full
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.enabled, 0)
        self.assertEqual(self.sm.faulted, 1)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.reason_str, "LIMIT")
        self.assertEqual(self.sm.ui_status_str, "FLT")
        self.sm.movie_state.value = 0
        for _ in range(20):
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
            self.assertEqual(self.sm.ui_status_str, "FLT")

    def test_diag_line2_and_line3_formatting_within_55_char_limit(self) -> None:
        self.sm.menu_open_count.value = 9999
        self.sm.playback_menu_open_count.value = 9999
        self.sm.playback_menu_item_edit_count.value = 9999
        self.sm.sync_restore_count.value = 9999
        self.sm.poll_restore_count.value = 9999

        # Check across OFF, RDY, ARM, WAIT, SETL, PRS, REL, CONF, FLT
        observed_tokens: list[str] = []

        for expected_tok, setup_fn in (
            ("OFF", lambda: self.sm.reset()),
            ("RDY", lambda: (self.sm.reset(), self._confirm_idle_and_enable())),
            ("ARM", lambda: (self.sm.reset(), self._start_deliberate_physical_recording())),
        ):
            setup_fn()
            line2 = self.sm.format_line2()
            line3 = self.sm.format_line3()
            self.assertIn(f"AC:{expected_tok}", line2)
            self.assertIn(f"AC:{expected_tok}", line3)
            self.assertLessEqual(len(line2), 55, f"Line 2 exceeded 55 chars ({len(line2)}): {line2}")
            self.assertLessEqual(len(line3), 55, f"Line 3 exceeded 55 chars ({len(line3)}): {line3}")
            observed_tokens.append(expected_tok)

        # Step through WAIT -> SETL -> PRS -> REL -> CONF -> FLT
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.sm.step()
        for tok in ("WAIT",):
            line2 = self.sm.format_line2()
            line3 = self.sm.format_line3()
            self.assertIn(f"AC:{tok}", line2)
            self.assertIn(f"AC:{tok}", line3)
            self.assertLessEqual(len(line2), 55)
            self.assertLessEqual(len(line3), 55)
            observed_tokens.append(tok)

        self.sm.movie_state.value = 0
        self.sm.step()
        line2 = self.sm.format_line2()
        self.assertIn("AC:SETL", line2)
        self.assertLessEqual(len(line2), 55)
        observed_tokens.append("SETL")

        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.sm.step()
        self.sm.step()
        line2 = self.sm.format_line2()
        self.assertIn("AC:PRS", line2)
        self.assertLessEqual(len(line2), 55)
        observed_tokens.append("PRS")

        for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
            self.sm.step()
        self.sm.step()
        line2 = self.sm.format_line2()
        self.assertIn("AC:REL", line2)
        self.assertLessEqual(len(line2), 55)
        observed_tokens.append("REL")

        for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
            self.sm.step()
        self.sm.step()
        line2 = self.sm.format_line2()
        self.assertIn("AC:CONF", line2)
        self.assertLessEqual(len(line2), 55)
        observed_tokens.append("CONF")

        self.sm.movie_state.value = 6
        self.sm.step()
        line2 = self.sm.format_line2()
        line3 = self.sm.format_line3()
        self.assertIn("AC:FLT", line2)
        self.assertIn("AC:FLT", line3)
        self.assertLessEqual(len(line2), 55)
        self.assertLessEqual(len(line3), 55)
        observed_tokens.append("FLT")

        self.assertEqual(
            observed_tokens,
            ["OFF", "RDY", "ARM", "WAIT", "SETL", "PRS", "REL", "CONF", "FLT"],
        )


class TestPort58BuildArtifactsDisassemblyAndDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_candidate()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.cand_bin = ROOT / "out/port58-movie-control/DISKBOOT.BIN"
        cls.cand_elf = ROOT / "out/port58-movie-control/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.cand_obj = ROOT / "out/port58-movie-control/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.cand_manifest = ROOT / "out/port58-movie-control/port58_movie_control_manifest.json"

    def test_default_build_byte_identical_to_origin_main(self) -> None:
        self.assertTrue(self.default_bin.is_file())
        self.assertEqual(sha256_file(self.default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(self.default_bin.stat().st_size, BASE_DEFAULT_SIZE)

        res = subprocess.run([str(NM), str(self.default_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", res.stdout)
        self.assertNotIn("g3x_movie_autocont_poll", res.stdout)
        self.assertNotIn("g3x_movie_autocont_set_enabled", res.stdout)

    def test_primary_candidate_manifest_flags_and_disassembly_invariants(self) -> None:
        self.assertTrue(self.cand_bin.is_file())
        self.assertTrue(self.cand_elf.is_file())
        self.assertTrue(self.cand_obj.is_file())
        self.assertTrue(self.cand_manifest.is_file())

        m = json.loads(self.cand_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["milestone"], "PORT-58")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_COMMIT)
        self.assertEqual(m["card_writes"], "disabled")
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], sha256_file(self.cand_bin))
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], self.cand_bin.stat().st_size)

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
            "G3X_MOVIE_AUTOCONT=1",
            "G3X_MOVIE_AUTOCONT_UI=1",
        ):
            self.assertIn(req_flag, flags)
        for forbidden_flag in ("G3X_MOVIE_NOLIMIT=1", "G3X_CONF_SAVE=1", "FULL_HOOKS=1"):
            self.assertNotIn(forbidden_flag, flags)

        # Verify symbols in main.elf
        nm_res = subprocess.run([str(NM), str(self.cand_elf)], capture_output=True, text=True, check=True)
        nm_out = nm_res.stdout
        for req_sym in (
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
        ):
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in candidate main.elf")
        for forbidden_sym in ("g3x_movie_nolimit_poll", "g3x_conf_save_active"):
            self.assertNotIn(forbidden_sym, nm_out, f"Forbidden symbol {forbidden_sym} present in candidate main.elf")

        # Verify all 10 MovieRecorder RAM accessors emit strictly loads and zero stores
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
        for target_path, desc in ((self.cand_obj, "movie_rec.o"), (self.cand_elf, "main.elf")):
            dis_res = subprocess.run([str(OBJDUMP), "-d", str(target_path)], capture_output=True, text=True, check=True)
            disasm = dis_res.stdout
            for fn in accessors:
                instrs = parse_function_instructions(disasm, fn)
                self.assertGreater(len(instrs), 0, f"Missing instructions for {fn} in {desc}")
                for instr in instrs:
                    mnem = instr["mnemonic"]
                    self.assertFalse(
                        mnem.startswith("str") or mnem.startswith("stm") or mnem.startswith("push"),
                        f"Forbidden store '{mnem}' in read-only accessor {fn} ({desc}): {instr['line']}",
                    )

            for fhex in ("c078", "c0c0", "c0c8", "c0d4", "c0d8", "c0e4", "c274", "c278", "c290", "c298", "c2a0", "c2a8"):
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

        # Verify staged core/gui.c wires "Auto-Continue Movie" in video_submenu_items[]
        staged_gui_c = ROOT / "out/port58-movie-control/stage_chdk/core/gui.c"
        self.assertTrue(staged_gui_c.is_file())
        gui_text = staged_gui_c.read_text(encoding="utf-8")
        self.assertIn('"Auto-Continue Movie"', gui_text)
        self.assertIn("g3x_movie_autocont_menu_change", gui_text)

    def test_interface_doc_reconciliation_and_provenance_commits_resolve(self) -> None:
        doc_text = DOC_PORT58.read_text(encoding="utf-8")

        # 1. Verify review notes corrected:
        #    - g3x_movie_autocont_get_restart_count() used (not g3x_movie_autocont_get_count())
        #    - Actual PORT-57 build hash ed374e7d332bce36a9c76682074aa9516e15e3be used (not corrupted hash)
        #    - Actual function and constant names used
        self.assertIn("g3x_movie_autocont_get_restart_count()", doc_text)
        self.assertNotIn("g3x_movie_autocont_get_count()", doc_text)
        self.assertIn(PORT57_BUILD_COMMIT, doc_text)
        self.assertNotIn("ed374e7d332bce36a9c7668207152e28d18b861", doc_text)
        self.assertNotIn("af25780422bf2a96ef1b3f36362d9f8187822c0d", doc_text)
        self.assertNotIn("ded38329e9a01a71808234267060a726925efde1", doc_text)
        self.assertNotIn("6c1474c25e1e49e8cf2fb601207152e28d18b861", doc_text)
        self.assertNotIn("992421bd9d6db9126f435a3047d7876944b57234", doc_text)

        for required_name in (
            "G3X_MOVIE_AUTOCONT_UI",
            "g3x_autocont_sample_recording_metrics",
            "g3x_autocont_check_eligible_stop",
            "G3X_AUTOCONT_MAX_STOP_POLLS",
            "G3X_AUTOCONT_CONFIRM_POLLS",
            "G3X_AUTOCONT_REASON_NONE",
            "G3X_AUTOCONT_REASON_USER_OFF",
            "G3X_AUTOCONT_REASON_PHYS_STOP",
            "G3X_AUTOCONT_REASON_PLAYBACK",
            "G3X_AUTOCONT_REASON_INVALID_STATE",
            "G3X_AUTOCONT_REASON_STOP_FAULT",
            "G3X_AUTOCONT_REASON_TIMEOUT",
            BASE_DEFAULT_SHA256,
            sha256_file(self.cand_bin),
        ):
            self.assertIn(required_name, doc_text, f"Missing '{required_name}' in docs/PORT58_MOVIE_CONTROL.md")

        # 2. Verify every 40-hex commit hash cited as a git commit in docs/PORT58_MOVIE_CONTROL.md resolves locally
        # (Exclude known 64-hex SHA-256 artifact/slice hashes)
        sha256_tokens = set(re.findall(r"\b[0-9a-f]{64}\b", doc_text))
        commit_candidates = set(re.findall(r"\b[0-9a-f]{40}\b", doc_text))
        self.assertIn(ORIGIN_MAIN_COMMIT, commit_candidates)
        self.assertIn(PORT57_BUILD_COMMIT, commit_candidates)
        for commit_hash in commit_candidates:
            if any(commit_hash in s for s in sha256_tokens):
                continue
            res = subprocess.run(
                ["git", "rev-parse", "--verify", f"{commit_hash}^{{commit}}"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Unresolvable commit hash in docs/PORT58_MOVIE_CONTROL.md: {commit_hash}")


if __name__ == "__main__":
    unittest.main()
