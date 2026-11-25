"""Offline unit and integration tests for PORT-62 (Standalone Movie Candidate: G3X_MOVIE_STANDALONE=1).

Verifies:
1. Integrated baseline & PORT-61 inclusion:
   - Confirms integrated baseline commit 7e0f548f990bdd03d4eb0ec52bf2e11d7282f4e7 (Merge PR #230)
     and PORT62-REUSE-MAP integration parent 832806b1f0e1d73f75e540cf3b64f6448948f567 (3d161e110f88a26efdeecdfd030f08dbc254e612).
   - Confirms PORT-61 deliverables and commit ancestry (e6a56328..., da5114a6..., 81e912f9..., 1a9df57d...)
     are present in HEAD, while PORT-54 (af257808...) remains excluded.
2. Standalone opt-in profile & builder isolation:
   - G3X_MOVIE_STANDALONE=1 builds via scripts/build_port62_movie_standalone.py and
     scripts/build_port43_dbuf.py --movie-standalone into build/port62-movie-standalone/DISKBOOT.BIN
     using the pinned toolchain (gcc-arm-none-eabi-5_4-2016q3) and deterministic wrapper.
   - Packages DISKBOOT.BIN and port62_movie_standalone_manifest.json only, with zero CHDK/ directory,
     zero .flt modules, zero fonts, zero language files, zero scripts, zero splash, and zero settings files.
   - Rejects missing movie prerequisites and incompatible flags (G3X_MOVIE_AUTOCONT_UI=1, GUI/menu flags,
     G3X_CONF_SAVE=1, FULL_HOOKS=1, *-alone) across movie_status.h, Makefiles, and CLI.
3. Minimal resident & keyboard path + PORT-41/52 short-press fix + PORT-56 duration patch:
   - core_spytask() runs only camera_info_init(), the spytask_can_start wait, and the 20 ms
     camera_info.state.mode_play = (rec_mode_active() ? 0 : 1) loop.
   - kbd_process() forces kbd_blocked = 0, gui_mode = 0, gui_mode_none = 1, gui_mode_alt = 0 and returns 0.
   - Preserves PORT-41/52 short-press power-on/playback start-cause restoration (0x00009BD0) and 200-poll
     active-low button hold (0x00020000 / 0x00010000 in physw_status[0]).
   - Preserves PORT-56 g3x_movie_nolimit_poll() wiring before g3x_movie_autocont_poll() in my_kbd_read_keys(),
     patching 0x0000C274 (mr_max_frames) to 0xFFFFFFFFU only while mr_rec_state == 1.
4. Shared movie controller behavior under G3X_MOVIE_STANDALONE=1:
   - Boot-enabled continuation (g3x_movie_autocont_is_enabled() == 1 in G3X_AUTOCONT_DISARMED) with fail-closed
     two-stage session admission and finite restart budget (default 1).
   - Admits only confirmed natural stops attributed to Reason 3 (4 GiB size policy cap) or Reason 4 (frame/duration
     cap) with every existing admission predicate satisfied.
   - Vetoes user stop (0), overflow (1), card full (2 or insufficient space), low battery / overheating / card
     error / unknown codes (>= 5), and stale or ambiguous attribution.
   - Physical KEY_VIDEO intent wins during active recording, pending restarts (WAIT_IDLE, SETTLE), and outstanding
     restarts (PRESSING, RELEASING, WAIT_CONFIRM); cancellation releases only continuation-owned synthetic keys.
   - Physical stop latches session cancellation (cancel_latched == 1 and session_cancelled == 1); only a new
     deliberate physical start after confirmed idle in record mode rearms and replenishes the budget. Synthetic
     events never count as deliberate physical starts or replenish the budget.
   - Finite restart budget exhaustion never stops an active clip; bounded start failures (WAIT_IDLE / WAIT_CONFIRM
     timeouts or invalid states) disarm fail-closed without retry or budget refund.
5. Preserved profiles & disassembly safety:
   - Default build and existing PORT-55..61 profiles remain 100% byte-for-byte identical.
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

ROOT = Path(__file__).resolve().parents[1]
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
CORE_MAIN_C = ROOT / "chdk-port/core/main.c"
CORE_KBD_PROCESS_C = ROOT / "chdk-port/core/kbd_process.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
STANDALONE_BUILD_SCRIPT = ROOT / "scripts/build_port62_movie_standalone.py"
DOC_PORT62 = ROOT / "docs/PORT62_MOVIE_STANDALONE.md"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_PORT61_COMMIT = "7e0f548f990bdd03d4eb0ec52bf2e11d7282f4e7"
PORT61_INTEGRATION_TIP = "e6a56328ee25d093ebb5c772356d42d31568c03b"
PORT61_VALIDATE_COMMIT = "1a9df57d167416ae8119b39d84ac50eab9bee1bd"
PORT62_REUSE_MAP_COMMIT = "3d161e110f88a26efdeecdfd030f08dbc254e612"
PORT62_INTEGRATION_PARENT = "832806b1f0e1d73f75e540cf3b64f6448948f567"
PORT62_INTEGRATION_BASELINE_COMMIT = "b718a92014b4a08f979d95347152642e596a10b4"

PORT62_PRE_FIX_DOC_SHA256 = "dab7f816d4eadfc6004b54e2b670f5da8d88d78eed5f4978521ef38f02c3802b"
PORT62_PRE_FIX_DOC_SIZE = 126345
PORT62_PRE_FIX_DOC_END = "00368f90"

PORT62_STANDALONE_SHA256 = "fdef85dbe1703ea4ea9eea3df261bd803c99e7b689041feee918f990f7dc9eb9"
PORT62_STANDALONE_SIZE = 126529
PORT62_STANDALONE_END = "00369070"

KEY_VIDEO = 18
G3X_KEY_VIDEO_BIT = 0x00000008
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

G3X_AUTOCONT_BUDGET_STANDALONE = 50
G3X_AUTOCONT_BUDGET_DEFAULT = G3X_AUTOCONT_BUDGET_STANDALONE

REQUIRED_STANDALONE_PREREQS = [
    "G3X_MOVIE_SESSION_CANCEL",
    "G3X_MOVIE_RESTART_BUDGET",
    "G3X_MOVIE_NOLIMIT",
    "G3X_MOVIE_AUTOCONT",
    "G3X_MOVIE_STATUS",
]

INCOMPATIBLE_GUI_FLAGS = [
    "G3X_GUI5",
    "G3X_GUI_FIX",
    "G3X_GUI_DBUF",
    "G3X_GUI_NOOVERDRAW",
    "G3X_KBD_CHECK",
    "G3X_GUI_DIAG",
    "G3X_GUI_SHADOW2",
    "G3X_GUI_SYNC",
    "G3X_GUI_MENU",
    "G3X_GUI_RESTORE2",
    "G3X_PLAYBACK_MENU",
]

_BUILD_CACHE = {
    "default": False,
    "port59": False,
    "port60": False,
    "port61": False,
    "port62": False,
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
    if _BUILD_CACHE["port61"] and bin_path.is_file() and elf_path.is_file():
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
                "--movie-session-cancel",
                "--out-dir",
                str(ROOT / "out/port61-movie-session-cancel"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port61"] = True


def ensure_build_port62() -> None:
    bin_path = ROOT / "build/port62-movie-standalone/DISKBOOT.BIN"
    elf_path = ROOT / "build/port62-movie-standalone/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "build/port62-movie-standalone/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "build/port62-movie-standalone/port62_movie_standalone_manifest.json"
    if (
        _BUILD_CACHE["port62"]
        and bin_path.is_file()
        and elf_path.is_file()
        and obj_path.is_file()
        and manifest_path.is_file()
        and sha256_file(bin_path) == PORT62_STANDALONE_SHA256
    ):
        return
    if not (
        bin_path.is_file()
        and elf_path.is_file()
        and obj_path.is_file()
        and manifest_path.is_file()
        and sha256_file(bin_path) == PORT62_STANDALONE_SHA256
    ):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(STANDALONE_BUILD_SCRIPT),
                "--out-dir",
                str(ROOT / "build/port62-movie-standalone"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["port62"] = True


class _HostPort62StandaloneHarness:
    """Compiles movie_rec.c, kbd_process.c, core_spytask standalone path, and PORT-41/52 short-press + kbd wiring with G3X_MOVIE_STANDALONE=1 and zero GUI defines."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port62_host_sm_")
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

        harness_c = tmp / "harness_standalone.c"
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
            f'#include "{kbd_proc_staged}"\n'
            f'#include "{MOVIE_REC_C}"\n'
            "/* Replicate standalone core_spytask mode update & init (chdk-port/core/main.c:116-143) */\n"
            "int rec_mode_active(void) {\n"
            "    return (host_playrec_mode == 2 || host_playrec_mode == 4 || host_playrec_mode == 5);\n"
            "}\n"
            "void host_spytask_init_and_tick(void) {\n"
            "    camera_info.state.osd_title_line = 1;\n"
            "    camera_info.state.gui_mode = 0;\n"
            "    camera_info.state.gui_mode_none = 1;\n"
            "    camera_info.state.gui_mode_alt = 0;\n"
            "    camera_info.state.mode_play = rec_mode_active() ? 0 : 1;\n"
            "}\n"
            "/* Replicate full_build/g3x/kbd.c PORT-41/52 short-press & my_kbd_read_keys standalone wiring */\n"
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

        so_path = tmp / "libport62_movie_standalone.so"
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
    def physw_video_pressed(self) -> bool:
        return (self.physw_status[0] & G3X_KEY_VIDEO_BIT) == 0

    @property
    def mod_video_pressed(self) -> bool:
        return (self.kbd_mod_state[0] & G3X_KEY_VIDEO_BIT) == 0


class TestPort62BaselineAndFlagGates(unittest.TestCase):
    def test_integrated_baseline_and_port61_inclusion_in_head(self) -> None:
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
        for src_path in (MOVIE_STATUS_H, MOVIE_REC_C, PLAT_MAKEFILE, SUB_MAKEFILE_INC, BUILD_SCRIPT):
            src_text = src_path.read_text(encoding="utf-8")
            self.assertNotIn("g3x_conf_save_active", src_text)
            self.assertNotIn("apply_port54_conf_save_staging_patches", src_text)

    def test_standalone_profile_accepts_required_movie_flags_and_rejects_missing_prerequisites(self) -> None:
        expected_err = (
            "G3X_MOVIE_STANDALONE=1 requires G3X_MOVIE_SESSION_CANCEL=1 "
            "G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 "
            "G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1"
        )
        full_c_flags = ["-DG3X_MOVIE_STANDALONE=1"] + [f"-D{f}=1" for f in REQUIRED_STANDALONE_PREREQS]
        res = subprocess.run(
            ["cc", "-E", *full_c_flags, "-I", str(MOVIE_STATUS_H.parent), "-x", "c", str(MOVIE_STATUS_H)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)

        for missing in REQUIRED_STANDALONE_PREREQS:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_MOVIE_STANDALONE=1"] + [
                    f"-D{f}=1" for f in REQUIRED_STANDALONE_PREREQS if f != missing
                ]
                res = subprocess.run(
                    ["cc", "-E", *c_flags, "-I", str(MOVIE_STATUS_H.parent), "-x", "c", str(MOVIE_STATUS_H)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(expected_err, res.stderr)

                make_args = ["G3X_MOVIE_STANDALONE=1"] + [
                    f"{f}=1" for f in REQUIRED_STANDALONE_PREREQS if f != missing
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

    def test_standalone_profile_rejects_gui_autocont_ui_conf_save_full_hooks_and_alone_combinations(self) -> None:
        full_c_flags = ["-DG3X_MOVIE_STANDALONE=1"] + [f"-D{f}=1" for f in REQUIRED_STANDALONE_PREREQS]
        full_make_args = ["G3X_MOVIE_STANDALONE=1"] + [f"{f}=1" for f in REQUIRED_STANDALONE_PREREQS]

        incompat_cases = [
            ("G3X_MOVIE_AUTOCONT_UI", "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            ("G3X_CONF_SAVE", "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_CONF_SAVE=1"),
            ("FULL_HOOKS", "G3X_MOVIE_STANDALONE=1 is incompatible with FULL_HOOKS=1"),
        ] + [(gui_flag, "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags") for gui_flag in INCOMPATIBLE_GUI_FLAGS]

        for bad_flag, expected_msg in incompat_cases:
            with self.subTest(bad_flag=bad_flag):
                res = subprocess.run(
                    [
                        "cc",
                        "-E",
                        *full_c_flags,
                        f"-D{bad_flag}=1",
                        "-I",
                        str(MOVIE_STATUS_H.parent),
                        "-x",
                        "c",
                        str(MOVIE_STATUS_H),
                    ],
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

        base_cli = [sys.executable, "-B", str(BUILD_SCRIPT), "--movie-standalone"]
        for bad_cli, exp_err in (
            (["--conf-save"], "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_CONF_SAVE=1"),
            (["--full-hooks"], "G3X_MOVIE_STANDALONE=1 is incompatible with FULL_HOOKS=1"),
            (["--movie-autocont-ui"], "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-combined"], "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-budget-profile"], "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--movie-cancel-profile"], "G3X_MOVIE_STANDALONE=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1"),
            (["--gui-menu"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--gui-sync"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--shadow2"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--gui-diag"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--kbd-check"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--no-overdraw"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--gui-restore2"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--playback-menu"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--playback-menu-alone"], "G3X_MOVIE_STANDALONE=1 is incompatible with GUI/menu flags"),
            (["--movie-nolimit-alone"], "G3X_MOVIE_STANDALONE=1 requires"),
            (["--movie-autocont-alone"], "G3X_MOVIE_STANDALONE=1 requires"),
            (["--movie-status-alone"], "G3X_MOVIE_STANDALONE=1 requires"),
        ):
            with self.subTest(bad_cli=bad_cli):
                res = subprocess.run([*base_cli, *bad_cli], cwd=str(ROOT), capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(exp_err, res.stderr)


class TestPort62StandaloneRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostPort62StandaloneHarness()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sm.close()

    def setUp(self) -> None:
        self.sm.reset()

    def _start_deliberate_physical_recording(
        self,
        budget: int | None = None,
        hold_polls_into_rec: int = 0,
        run_nolimit: bool = True,
        initial_counters_zero: bool = False,
    ) -> None:
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
        if self.sm.prev_idle_needed_for_start():
            self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
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

        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(run_nolimit=run_nolimit), G3X_AUTOCONT_DISARMED)
        if hold_polls_into_rec == 0:
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

        # Simulate MovieRecorder_SetupModeAndLimits re-running on continued clip start (stock 54000 -> patched to 0xFFFFFFFFU)
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

    def test_minimal_resident_and_keyboard_path_without_gui_or_alt(self) -> None:
        # 1. kbd_process(), enter_alt(), exit_alt() never block keys or enter <ALT>
        self.sm.kbd_blocked.value = 1
        self.sm.lib.enter_alt()
        self.assertEqual(self.sm.kbd_blocked.value, 0)
        self.assertEqual(self.sm.lib.kbd_is_blocked(), 0)

        self.sm.kbd_blocked.value = 1
        self.sm.lib.exit_alt()
        self.assertEqual(self.sm.kbd_blocked.value, 0)

        self.sm.kbd_blocked.value = 1
        self.assertEqual(self.sm.lib.kbd_process(), 0)
        self.assertEqual(self.sm.kbd_blocked.value, 0)
        self.assertEqual(self.sm.lib.kbd_is_blocked(), 0)

        # 2. my_kbd_read_keys() passes raw kbd_new_state[0..2] through to physw_status[0..2],
        #    sets physw0_override = -1, and clears SD_READONLY_FLAG (0x20000000) in physw_status[1]
        self.sm.kbd_new_state[0] = 0xFFFFFFEF  # KEY_MENU pressed
        self.sm.kbd_new_state[1] = 0xFFFFFFFF  # SD lock bit 29 set in raw input
        self.sm.kbd_new_state[2] = 0x12345678
        self.sm.step()
        self.assertEqual(self.sm.physw0_override.value, -1)
        self.assertEqual(self.sm.physw_status[0] & 0xFFFFFFFF, 0xFFFFFFEF)
        self.assertEqual(self.sm.physw_status[1] & SD_READONLY_FLAG, 0)
        self.assertEqual(self.sm.physw_status[2] & 0xFFFFFFFF, 0x12345678)

        # 3. core_spytask() mode update tracks playrec_mode ({2, 4, 5} -> record mode 0; else playback mode 1)
        for rec_val in (2, 4, 5):
            self.sm.playrec_mode.value = rec_val
            self.sm.lib.host_spytask_init_and_tick()
            self.sm.step()
            self.assertNotEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)

        for play_val in (0, 1, 3, 6):
            self.sm.reset()
            self.sm.playrec_mode.value = play_val
            self.sm.lib.host_spytask_init_and_tick()
            self.sm.step()
            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)

    def test_shortpress_poweron_fix_and_port56_duration_patch_standalone_wiring(self) -> None:
        # 1. PORT-41/52 Short-press Power-on path (0x00080000, bit 17 0x00020000, or 0/unknown fallback)
        for raw_cause in (G3X_STARTCAUSE_POWER, 0, 0x00000001):
            with self.subTest(power_start_cause=hex(raw_cause)):
                self.sm.reset()
                self.sm.startcause_mem.value = raw_cause
                self.sm.lib.g3x_full_shortpress_boot_entry_hook()
                self.assertEqual(self.sm.saved_start_cause.value, G3X_STARTCAUSE_POWER)
                self.assertEqual(self.sm.selected_button_bit.value, G3X_KEY_POWER_BIT)
                self.assertEqual(self.sm.shortpress_active.value, 1)
                self.assertEqual(self.sm.shortpress_margin_polls.value, G3X_SHORTPRESS_MARGIN_POLLS)

                self.sm.startcause_mem.value = 0
                self.sm.physw_status[0] = 0xFFFFFFFF
                self.sm.lib.g3x_full_shortpress_post_bss_hook()
                self.assertEqual(self.sm.startcause_mem.value, G3X_STARTCAUSE_POWER)
                self.assertEqual(self.sm.physw_status[0] & G3X_KEY_POWER_BIT, 0)
                self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_PLAYBACK_BIT, 0)
                self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_VIDEO_BIT, 0)

                for rem in range(G3X_SHORTPRESS_MARGIN_POLLS - 1, -1, -1):
                    self.sm.startcause_mem.value = 0
                    self.sm.step()
                    self.assertEqual(self.sm.shortpress_active.value, 1)
                    self.assertEqual(self.sm.shortpress_margin_polls.value, rem)
                    self.assertEqual(self.sm.startcause_mem.value, G3X_STARTCAUSE_POWER)
                    self.assertEqual(self.sm.physw_status[0] & G3X_KEY_POWER_BIT, 0)
                    self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_VIDEO_BIT, 0)

                # Poll 201 releases short-press hold automatically
                self.sm.step()
                self.assertEqual(self.sm.shortpress_active.value, 0)
                self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_POWER_BIT, 0)

        # 2. PORT-41/52 Short-press Playback start path (0x00100000, bit 16 0x00010000)
        self.sm.reset()
        self.sm.startcause_mem.value = G3X_STARTCAUSE_PLAYBACK
        self.sm.lib.g3x_full_shortpress_boot_entry_hook()
        self.assertEqual(self.sm.saved_start_cause.value, G3X_STARTCAUSE_PLAYBACK)
        self.assertEqual(self.sm.selected_button_bit.value, G3X_KEY_PLAYBACK_BIT)
        self.sm.lib.g3x_full_shortpress_post_bss_hook()
        self.assertEqual(self.sm.physw_status[0] & G3X_KEY_PLAYBACK_BIT, 0)
        self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_POWER_BIT, 0)
        for _ in range(G3X_SHORTPRESS_MARGIN_POLLS):
            self.sm.step()
            self.assertEqual(self.sm.physw_status[0] & G3X_KEY_PLAYBACK_BIT, 0)
        self.sm.step()
        self.assertEqual(self.sm.shortpress_active.value, 0)
        self.assertNotEqual(self.sm.physw_status[0] & G3X_KEY_PLAYBACK_BIT, 0)

        # 3. PORT-56 duration patch (g3x_movie_nolimit_poll) standalone wiring:
        #    Never writes when mr_rec_state != 1 or when max_frames == 0; patches nonzero stock value to 0xFFFFFFFFU
        #    while mr_rec_state == 1 and re-patches after SetupModeAndLimits runs on continued clips.
        self.sm.reset()
        for non_rec_state in (0, 2, 3, 4):
            self.sm.movie_state.value = non_rec_state
            self.sm.max_frames.value = 54000
            self.sm.step()
            self.assertEqual(self.sm.max_frames.value, 54000)

        self.sm.reset()
        self.sm.movie_state.value = 1
        self.sm.max_frames.value = 0  # SetupModeAndLimits not yet finished
        self.sm.step()
        self.assertEqual(self.sm.max_frames.value, 0)

        self.sm.max_frames.value = 54000  # SetupModeAndLimits stores 29:59 frame limit
        self.sm.step()
        self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)

    def test_boot_enabled_continuation_and_fail_closed_session_admission(self) -> None:
        # 1. Continuation is enabled at boot in G3X_AUTOCONT_DISARMED with fixed compile-time budget 50 and 0 remaining/used
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.menu_str, "Ready")
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.restart_budget, G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_budget_menu_str().decode("utf-8"), "50")
        self.assertEqual(self.sm.lib.g3x_movie_autocont_budget_menu_change(1, 0).decode("utf-8"), "50")
        self.assertEqual(self.sm.lib.g3x_movie_autocont_budget_menu_change(-1, 0).decode("utf-8"), "50")
        for candidate_budget in (0, 1, 2, 3, 4, 49, 50, 51, 100):
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(candidate_budget), 0)
            self.assertEqual(self.sm.restart_budget, G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.session_cancelled, 0)
        self.assertEqual(self.sm.cancel_latched, 0)

        # 2. Staying in IDLE (0) at boot never arms or emits synthetic KEY_VIDEO
        for _ in range(250):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.synth_owned, 0)

        # 3. Booting already in RECORDING (1) without confirmed boot idle stays DISARMED and never restarts
        self.sm.reset()
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 100
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF800000
        for _ in range(10):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(60):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

        # 4. Holding physical KEY_VIDEO at boot before confirmed boot idle with button released refuses to arm
        self.sm.reset()
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)

        # 5. Unattributed 0 -> 1 transition without physical KEY_VIDEO press at confirmed IDLE refuses to arm
        self.sm.reset()
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)

        # 6. Physical KEY_VIDEO press at confirmed IDLE that expires after 200 polls before 0 -> 1 refuses to arm
        self.sm.reset()
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)

    def test_natural_stop_admission_reason_3_and_reason_4_and_vetoes(self) -> None:
        # 1. Confirmed natural stop with Reason 3 (4 GiB size policy cap) and all admission predicates satisfied
        self._start_deliberate_physical_recording()
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(
            expected_remaining_after_admission=G3X_AUTOCONT_BUDGET_STANDALONE - 1,
            expected_used_after_admission=1,
        )
        self.assertEqual(self.sm.last_stop_reason, 3)
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)
        self.assertEqual(self.sm.release_calls.value, 1)

        # 2. Confirmed natural stop with Reason 4 (frame/duration limit cap when max_frames is finite)
        self.sm.reset()
        self._start_deliberate_physical_recording(run_nolimit=False)
        self._prime_in_bounds_reason4_metrics(max_frames=1800, cur_frames=900)
        self.sm.cur_frames.value = 1800
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.last_stop_reason, 4)
        self.assertEqual(self.sm.restarts_remaining, G3X_AUTOCONT_BUDGET_STANDALONE - 1)
        self.assertEqual(self.sm.session_restarts_used, 1)
        self.assertEqual(self.sm.attempt_admitted, 1)

        # 3. Under standalone PORT-56 duration patch (run_nolimit=True, max_frames == 0xFFFFFFFFU),
        #    any spurious Reason 4 stop is vetoed because max_frames == 0xFFFFFFFFU
        self.sm.reset()
        self._start_deliberate_physical_recording(run_nolimit=True)
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(run_nolimit=True), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.is_faulted, 1)
        self.assertEqual(self.sm.restarts_remaining, G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.press_calls.value, 0)

        # 4. Vetoes: user stop (0), overflow/card error (1), card full (2), low battery / overheating /
        #    card error / unknown stop reasons (5, 6, 7, 8, 99, 0xFFFFFFFF) prevent automatic restart
        for veto_reason in (0, 1, 2, 5, 6, 7, 8, 99, 0xFFFFFFFF):
            with self.subTest(veto_reason=veto_reason):
                self.sm.reset()
                self._start_deliberate_physical_recording()
                self._prime_in_bounds_reason3_metrics(1)
                self.sm.projected_size.value = 0x100000400
                self.sm.stop_reason.value = veto_reason
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
                self.assertEqual(self.sm.is_faulted, 1)
                self.assertEqual(self.sm.enabled, 1)  # Remains enabled for future deliberate physical start
                self.assertEqual(self.sm.restarts_remaining, G3X_AUTOCONT_BUDGET_STANDALONE)
                self.assertEqual(self.sm.session_restarts_used, 0)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.press_calls.value, 0)

        # 5. Ambiguous / stale attribution vetoes:
        #    (a) Reason 3 with card full (avail_space < proj_total)
        #    (b) Reason 3 with proj_total <= size_cap (threshold not exceeded)
        #    (c) Reason 3 with segment_index == 0 (size_cap == 0)
        #    (d) Reason 3 without prior in-bounds progression (saw_size_in_bounds == 0)
        #    (e) Reason 3 with unreset counters from previous stop
        #    (f) Reason 4 with cur_frames < max_frames
        #    (g) Reason 4 without prior in-bounds progression (saw_frames_in_bounds == 0)
        ambiguous_cases = (
            ("reason3_card_full", 3, True, 1, 0x008000000, 0x100000400, 54000, 28100),
            ("reason3_below_cap", 3, True, 1, 0x800000000, 0x0FFFFFF00, 54000, 28100),
            ("reason3_zero_seg", 3, True, 0, 0x800000000, 0x100000400, 54000, 28100),
            ("reason3_no_in_bounds", 3, False, 1, 0x800000000, 0x100000400, 54000, 28100),
            ("reason4_below_max", 4, True, 1, 0x800000000, 0x004000000, 1800, 1799),
            ("reason4_no_in_bounds", 4, False, 1, 0x800000000, 0x004000000, 1800, 1800),
        )
        for label, rcode, prime_in_bounds, seg_idx, avail, proj, max_f, cur_f in ambiguous_cases:
            with self.subTest(ambiguous_case=label):
                self.sm.reset()
                run_nl = rcode == 3
                self._start_deliberate_physical_recording(
                    run_nolimit=run_nl,
                    initial_counters_zero=not prime_in_bounds,
                )
                if prime_in_bounds:
                    if rcode == 3:
                        self._prime_in_bounds_reason3_metrics(1, run_nolimit=True)
                    else:
                        self._prime_in_bounds_reason4_metrics(max_frames=max_f, cur_frames=max_f // 2)
                self.sm.segment_index.value = seg_idx
                self.sm.avail_space.value = avail
                self.sm.projected_size.value = proj
                self.sm.max_frames.value = max_f
                self.sm.cur_frames.value = cur_f
                self.sm.stop_reason.value = rcode
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(run_nolimit=run_nl), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
                self.assertEqual(self.sm.press_calls.value, 0)

        # (e) Unreset counters from previous stop rejected before SetupModeAndLimits resets them
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=2)
        self._prime_in_bounds_reason3_metrics(1)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        # Continued clip enters state 1, but stream_bytes and projected_size have NOT moved from last_stop_*
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_STOP_FAULT)
        self.assertEqual(self.sm.restarts_remaining, 1)
        self.assertEqual(self.sm.session_restarts_used, 1)

    def test_physical_synthetic_input_races_and_continuation_owned_key_release(self) -> None:
        unrelated_w0_mask = 0x00010110  # KEY_MENU | KEY_SET | KEY_PLAYBACK
        unrelated_w1_val = 0xCAFEBABE
        unrelated_w2_val = 0x12345678

        # 1. Same-poll race in RECORDING between physical KEY_VIDEO press and eligible Reason 3 / Reason 4 stop:
        #    physical button wins before stop eligibility or budget reservation!
        for reason in (3, 4):
            for hold_into_rec in (0, 5):
                with self.subTest(same_poll_rec_race_reason=reason, hold_into_rec=hold_into_rec):
                    self.sm.reset()
                    run_nl = reason == 3
                    self._start_deliberate_physical_recording(
                        budget=2,
                        hold_polls_into_rec=hold_into_rec,
                        run_nolimit=run_nl,
                    )
                    if reason == 3:
                        self._prime_in_bounds_reason3_metrics(1, run_nolimit=True)
                        self.sm.projected_size.value = 0x100000400
                        self.sm.stop_reason.value = 3
                    else:
                        self._prime_in_bounds_reason4_metrics(1800, 900)
                        self.sm.cur_frames.value = 1800
                        self.sm.stop_reason.value = 4

                    # Set unowned synthetic key bits to prove they are not released when synth_owned == 0
                    self.sm.kbd_mod_state[0] &= ~(unrelated_w0_mask | G3X_KEY_VIDEO_BIT)
                    self.sm.kbd_mod_state[1] = unrelated_w1_val
                    self.sm.kbd_mod_state[2] = unrelated_w2_val
                    rel_before = self.sm.release_calls.value

                    # Same-poll physical stop + 1 -> 2 transition
                    self.sm.set_physical_video_button(True)
                    self.sm.movie_state.value = 2
                    self.assertEqual(self.sm.step(run_nolimit=run_nl), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                    self.assertEqual(self.sm.cancel_latched, 1)
                    self.assertEqual(self.sm.session_cancelled, 1)
                    self.assertEqual(self.sm.restarts_remaining, 2)  # Zero budget consumed!
                    self.assertEqual(self.sm.session_restarts_used, 0)
                    self.assertEqual(self.sm.attempt_admitted, 0)
                    self.assertEqual(self.sm.press_calls.value, 0)
                    self.assertEqual(self.sm.release_calls.value, rel_before)
                    self.assertEqual(self.sm.kbd_mod_state[0] & (unrelated_w0_mask | G3X_KEY_VIDEO_BIT), 0)

        # 2. Physical KEY_VIDEO wins across every pending (WAIT_IDLE, SETTLE) and outstanding
        #    (PRESSING polls 1..6, RELEASING polls 1..6, WAIT_CONFIRM) restart state, releasing ONLY
        #    continuation-owned KEY_VIDEO (in PRESSING) and preserving physical KEY_VIDEO low in physw_status[0].
        for phase in (
            "WAIT_IDLE",
            "SETTLE",
            "PRESSING_1",
            "PRESSING_3",
            "PRESSING_6",
            "RELEASING_1",
            "RELEASING_6",
            "WAIT_CONFIRM",
        ):
            with self.subTest(pending_or_outstanding_race_phase=phase):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=2)
                self._prime_in_bounds_reason3_metrics(1)
                self.sm.projected_size.value = 0x100000400
                self.sm.stop_reason.value = 3

                if phase == "WAIT_IDLE":
                    self.sm.movie_state.value = 2
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                else:
                    self.sm.movie_state.value = 0
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                    if phase != "SETTLE":
                        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                        if phase.startswith("PRESSING_"):
                            p_polls = int(phase.split("_")[1])
                            for _ in range(p_polls):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                        else:
                            for _ in range(G3X_AUTOCONT_PRESS_POLLS):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                            if phase.startswith("RELEASING_"):
                                r_polls = int(phase.split("_")[1])
                                for _ in range(r_polls):
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                            else:
                                for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)

                was_pressing = phase.startswith("PRESSING_")
                self.assertEqual(self.sm.synth_owned, 1 if was_pressing else 0)
                self.assertEqual(self.sm.attempt_admitted, 1)
                self.assertEqual(self.sm.restarts_remaining, 1)
                self.assertEqual(self.sm.session_restarts_used, 1)

                # Assert unrelated modifier bits in kbd_mod_state[0..2]; when not pressing, also assert unowned KEY_VIDEO
                self.sm.kbd_mod_state[0] &= ~unrelated_w0_mask
                if not was_pressing:
                    self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
                self.sm.kbd_mod_state[1] = unrelated_w1_val
                self.sm.kbd_mod_state[2] = unrelated_w2_val
                rel_before = self.sm.release_calls.value

                # Physical KEY_VIDEO pressed -> wins immediately
                self.sm.set_physical_video_button(True)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                self.assertEqual(self.sm.cancel_latched, 1)
                self.assertEqual(self.sm.session_cancelled, 1)
                self.assertEqual(self.sm.synth_owned, 0)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.restarts_remaining, 1)  # Consumed allowance never refunded
                self.assertEqual(self.sm.session_restarts_used, 1)

                if was_pressing:
                    self.assertEqual(self.sm.release_calls.value, rel_before + 1)
                    self.assertFalse(self.sm.mod_video_pressed)
                    # Physical KEY_VIDEO is held, so physw_status[0] bit 3 remains low (0)
                    self.assertTrue(self.sm.physw_video_pressed)
                else:
                    self.assertEqual(self.sm.release_calls.value, rel_before)
                    # Unowned KEY_VIDEO in kbd_mod_state[0] was untouched
                    self.assertTrue(self.sm.mod_video_pressed)
                    self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT

                self.assertEqual(self.sm.kbd_mod_state[0] & unrelated_w0_mask, 0)
                self.assertEqual(self.sm.kbd_mod_state[1] & 0xFFFFFFFF, unrelated_w1_val)
                self.assertEqual(self.sm.kbd_mod_state[2] & 0xFFFFFFFF, unrelated_w2_val)

    def test_physical_stop_latches_session_cancellation_and_rearming_requires_deliberate_physical_start(self) -> None:
        # 1. Start session with budget 2, consume 1 restart (remaining=1, used=1), then physical stop during Clip 2
        self._start_deliberate_physical_recording(budget=2)
        self._prime_in_bounds_reason3_metrics(1)
        self._run_admitted_reason3_restart_to_confirmed_recording(
            expected_remaining_after_admission=1,
            expected_used_after_admission=1,
        )
        self._prime_in_bounds_reason3_metrics(2)

        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
        self.assertEqual(self.sm.reason_str, "STOP")
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.ui_status_str, "CANC")
        self.assertEqual(self.sm.menu_str, "Cancel")
        self.assertEqual(self.sm.restart_budget, 2)
        self.assertEqual(self.sm.restarts_remaining, 1)
        self.assertEqual(self.sm.session_restarts_used, 1)

        # 2. Holding physical KEY_VIDEO across IDLE (0) -> RECORDING (1) cannot clear cancellation or rearm
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.restarts_remaining, 1)

        # 3. Release physical KEY_VIDEO while still in STOPPING (2), then press on the FIRST unconfirmed IDLE poll:
        #    must NOT rearm or clear session_cancelled!
        self.sm.movie_state.value = 2
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)  # Still 1 because IDLE (0) has not been reached with button released

        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)  # Premature press on first IDLE poll
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.restarts_remaining, 1)

        # 4. Reach confirmed IDLE (cur_state == 0 with button released):
        #    synthetic/unattributed 0 -> 1, direct enter_confirmed_recording, and programmatic set_enabled/set_restart_budget
        #    still cannot clear cancellation or replenish budget!
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Clears cancel_latched=0 and confirms idle
        self.assertEqual(self.sm.cancel_latched, 0)
        self.assertEqual(self.sm.session_cancelled, 1)

        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(1), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_enabled(0), 0)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(3), 0)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.restarts_remaining, 1)

        # Synthetic key pulse in kbd_mod_state[0] / physw_status[0] (without kbd_new_state[0]) + 0 -> 1 cannot rearm
        self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
        self.sm.physw_status[0] &= ~G3X_KEY_VIDEO_BIT
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT
        self.sm.physw_status[0] |= G3X_KEY_VIDEO_BIT
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.sm.lib.host_call_enter_confirmed_recording_for_test()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.session_cancelled, 1)
        self.assertEqual(self.sm.restarts_remaining, 1)
        self.assertEqual(self.sm.session_restarts_used, 1)

        # 5. Return to confirmed IDLE with physical KEY_VIDEO released, then perform a NEW deliberate physical start:
        #    clears session_cancelled to 0, rearms G3X_AUTOCONT_RECORDING, and replenishes full budget (2)!
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
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
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 0)

    def test_finite_budget_exhaustion_and_bounded_start_failure(self) -> None:
        # 1. For budget B in (1, 2, 3), admits at most B synthetic restarts across B + 1 clips;
        #    synthetic starts never replenish budget; exhaustion never stops the active (B + 1)-th clip;
        #    when the (B + 1)-th clip stops, disarms immediately to RDY without entering WAIT_IDLE or SETTLE;
        #    and rearms automatically on the next deliberate physical start after confirmed idle.
        for budget in (1, 2, 3):
            with self.subTest(finite_budget=budget):
                self.sm.reset()
                self._start_deliberate_physical_recording(budget=budget)
                for attempt_idx in range(1, budget + 1):
                    self._prime_in_bounds_reason3_metrics(attempt_idx)
                    self._run_admitted_reason3_restart_to_confirmed_recording(
                        expected_remaining_after_admission=budget - attempt_idx,
                        expected_used_after_admission=attempt_idx,
                    )

                # On the final (budget + 1)-th clip, restarts_remaining == 0 while recording continues with LIM:OFF
                self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.movie_state.value, 1)
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.assertEqual(self.sm.session_restarts_used, budget)
                for extra_poll in range(10):
                    self.sm.cur_frames.value = 1000 + extra_poll
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                    self.assertEqual(self.sm.movie_state.value, 1)
                    self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)

                # When the final clip stops at Reason 3, disarms immediately without entering WAIT_IDLE/SETTLE
                self._prime_in_bounds_reason3_metrics(budget + 1)
                presses_before = self.sm.press_calls.value
                self.sm.projected_size.value = 0x100080000
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
                self.assertEqual(self.sm.enabled, 1)
                self.assertEqual(self.sm.ui_status_str, "RDY")
                self.assertEqual(self.sm.restarts_remaining, 0)
                self.assertEqual(self.sm.session_restarts_used, budget)
                self.assertEqual(self.sm.press_calls.value, presses_before)

                # Subsequent deliberate physical start after confirmed idle rearms a fresh session with full budget
                self.sm.movie_state.value = 0
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self._start_deliberate_physical_recording()
                self.assertEqual(self.sm.restarts_remaining, budget)
                self.assertEqual(self.sm.session_restarts_used, 0)

        # 2. Bounded start failure: WAIT_IDLE timeout (500 polls = 5.0 s) disarms with TIMEOUT without synthetic press or refund
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=2)
        self._prime_in_bounds_reason3_metrics(1)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.restarts_remaining, 1)
        self.assertEqual(self.sm.session_restarts_used, 1)
        for _ in range(G3X_AUTOCONT_MAX_STOP_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
        self.assertEqual(self.sm.is_faulted, 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.restarts_remaining, 1)  # Never refunded
        self.assertEqual(self.sm.session_restarts_used, 1)
        self.assertEqual(self.sm.press_calls.value, 0)

        # 3. Bounded start failure: WAIT_CONFIRM timeout (200 polls = 2.0 s) emits exactly one 6-poll pulse,
        #    disarms with TIMEOUT without retry or refund, and rearms on a new deliberate physical start after confirmed idle
        self.sm.reset()
        self._start_deliberate_physical_recording(budget=2)
        self._prime_in_bounds_reason3_metrics(1)
        self.sm.projected_size.value = 0x100000400
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)
        self.assertEqual(self.sm.release_calls.value, 1)

        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
            self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
        self.assertEqual(self.sm.is_faulted, 1)
        self.assertEqual(self.sm.enabled, 1)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.restarts_remaining, 1)  # Never refunded
        self.assertEqual(self.sm.session_restarts_used, 1)
        self.assertEqual(self.sm.press_calls.value, G3X_AUTOCONT_PRESS_POLLS)

        # Unconfirmed-idle physical press on Poll 1 after WAIT_CONFIRM timeout is rejected
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # Rearms cleanly after confirmed idle on a new deliberate physical start
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.restarts_remaining, 2)
        self.assertEqual(self.sm.session_restarts_used, 0)

    def test_fixed_compile_time_budget_50_all_50_attempts_exhaustion_at_51_and_port60_61_range_preserved(self) -> None:
        # 1. Under G3X_MOVIE_STANDALONE=1, compile-time budget is fixed at 50 and runtime mutation is rejected;
        #    while under non-standalone PORT-60/61, default remains 1 and range 1..3 is preserved.
        self.sm.reset()
        self.assertEqual(self.sm.restart_budget, G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(self.sm.restart_budget, 50)
        self.assertEqual(self.sm.lib.g3x_movie_autocont_budget_menu_str().decode("utf-8"), "50")
        for b in (0, 1, 2, 3, 4, 25, 49, 50, 51, 99, 0xFFFFFFFF):
            self.assertEqual(self.sm.lib.g3x_movie_autocont_set_restart_budget(b), 0)
            self.assertEqual(self.sm.restart_budget, 50)

        # Verify shared movie_status.h / movie_rec.c preserves PORT-60/61 default 1 and 1..3 range when G3X_MOVIE_STANDALONE is not set
        from tests.test_port61_movie_session_cancel import _HostPort61CancelHarness

        p61_sm = _HostPort61CancelHarness()
        try:
            self.assertEqual(p61_sm.restart_budget, 1)
            self.assertEqual(p61_sm.budget_menu_str, "1")
            p61_sm.movie_state.value = 0
            p61_sm.step()
            self.assertEqual(p61_sm.lib.g3x_movie_autocont_set_enabled(1), 1)
            for valid_b in (1, 2, 3):
                self.assertEqual(p61_sm.lib.g3x_movie_autocont_set_restart_budget(valid_b), 1)
                self.assertEqual(p61_sm.restart_budget, valid_b)
            for invalid_b in (0, 4, 49, 50, 51):
                self.assertEqual(p61_sm.lib.g3x_movie_autocont_set_restart_budget(invalid_b), 0)
                self.assertEqual(p61_sm.restart_budget, 3)
        finally:
            p61_sm.close()

        # 2. Full 50-restart standalone session across 51 clips:
        #    proves multiple continuations beyond 1, all 50 permitted attempts (mixing Reason 3 and Reason 4),
        #    synthetic starts never resetting budget, and exhaustion after attempt 50 preventing attempt 51.
        self.sm.reset()
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.restart_budget, 50)
        self.assertEqual(self.sm.restarts_remaining, 50)
        self.assertEqual(self.sm.session_restarts_used, 0)
        self.assertEqual(self.sm.restart_count, 0)

        for attempt_idx in range(1, G3X_AUTOCONT_BUDGET_STANDALONE + 1):
            expected_rem = G3X_AUTOCONT_BUDGET_STANDALONE - attempt_idx
            if attempt_idx % 5 == 0:
                # Every 5th continuation tested via Reason 4 (finite frame-limit stop)
                self._prime_in_bounds_reason4_metrics(max_frames=1800, cur_frames=900)
                self.sm.cur_frames.value = 1800
                self.sm.stop_reason.value = 4
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(run_nolimit=False), G3X_AUTOCONT_WAIT_IDLE)
                self.assertEqual(self.sm.last_stop_reason, 4)
                self.assertEqual(self.sm.restarts_remaining, expected_rem)
                self.assertEqual(self.sm.session_restarts_used, attempt_idx)
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
                self.sm.cur_frames.value = attempt_idx + 1
                self.sm.stream_bytes.value = 65536 * (attempt_idx + 1)
                self.sm.projected_size.value = 65536 * (attempt_idx + 1)
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
                self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)
            else:
                self._prime_in_bounds_reason3_metrics(attempt_idx)
                self._run_admitted_reason3_restart_to_confirmed_recording(
                    expected_remaining_after_admission=expected_rem,
                    expected_used_after_admission=attempt_idx,
                )
                self.assertEqual(self.sm.last_stop_reason, 3)

            # Synthetic start confirmation never resets or replenishes budget
            self.assertEqual(self.sm.restart_budget, 50)
            self.assertEqual(self.sm.restarts_remaining, expected_rem)
            self.assertEqual(self.sm.session_restarts_used, attempt_idx)
            self.assertEqual(self.sm.restart_count, attempt_idx)
            self.assertEqual(self.sm.attempt_admitted, 0)
            self.assertEqual(self.sm.press_calls.value, attempt_idx * G3X_AUTOCONT_PRESS_POLLS)
            self.assertEqual(self.sm.release_calls.value, attempt_idx)

        # 3. After all 50 permitted attempts (Clip 51 active):
        #    restarts_remaining == 0, session_restarts_used == 50, active clip continues unimpeded with LIM:OFF
        self.assertEqual(self.sm.state, G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 50)
        self.assertEqual(self.sm.restart_count, 50)
        for extra_poll in range(10):
            self.sm.cur_frames.value = 2000 + extra_poll
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
            self.assertEqual(self.sm.max_frames.value, 0xFFFFFFFF)

        # 4. When Clip 51 reaches an eligible Reason 3 stop, exhaustion prevents attempt 51:
        #    disarms immediately to G3X_AUTOCONT_DISARMED (RDY) with zero synthetic presses
        self._prime_in_bounds_reason3_metrics(51)
        presses_after_50 = self.sm.press_calls.value
        self.assertEqual(presses_after_50, 50 * G3X_AUTOCONT_PRESS_POLLS)
        self.sm.projected_size.value = 0x100200000
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_NONE)
        self.assertEqual(self.sm.ui_status_str, "RDY")
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 50)
        self.assertEqual(self.sm.attempt_admitted, 0)
        self.assertEqual(self.sm.press_calls.value, presses_after_50)

        # 5. Synthetic/unattributed starts and unconfirmed-idle physical presses after exhaustion cannot renew budget
        self.sm.movie_state.value = 0
        self.sm.set_physical_video_button(True)  # Premature press on first unconfirmed idle poll
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.set_physical_video_button(False)
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 50)

        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)  # Confirmed idle
        # Synthetic pulse in kbd_mod_state[0]/physw_status[0] without physical kbd_new_state[0] + 0 -> 1 cannot renew
        self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT
        self.sm.physw_status[0] &= ~G3X_KEY_VIDEO_BIT
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT
        self.sm.physw_status[0] |= G3X_KEY_VIDEO_BIT
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.lib.host_call_enter_confirmed_recording_for_test()
        self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.restarts_remaining, 0)
        self.assertEqual(self.sm.session_restarts_used, 50)

        # 6. Deliberate physical start from confirmed idle renews the full 50-attempt budget
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self._start_deliberate_physical_recording()
        self.assertEqual(self.sm.restarts_remaining, 50)
        self.assertEqual(self.sm.session_restarts_used, 0)

    def test_failed_attempts_consume_budget_without_refund_and_physical_stop_wins_during_outstanding_start(self) -> None:
        # 1. Every failed attempt mode (WAIT_IDLE timeout, WAIT_CONFIRM timeout, invalid state in pending/outstanding
        #    phases, playback entry, and physical stop during pending/outstanding phases) consumes 1 budget unit
        #    from the 50-attempt allowance without refund or retry.
        failure_modes = (
            "wait_idle_timeout",
            "wait_confirm_timeout",
            "settle_invalid_state",
            "pressing_invalid_state",
            "releasing_invalid_state",
            "wait_confirm_invalid_state",
            "pending_playback",
            "outstanding_phys_stop",
        )
        for mode in failure_modes:
            with self.subTest(failure_mode=mode):
                self.sm.reset()
                self._start_deliberate_physical_recording()
                # Complete 2 successful continuations first (remaining=48, used=2)
                for k in (1, 2):
                    self._prime_in_bounds_reason3_metrics(k)
                    self._run_admitted_reason3_restart_to_confirmed_recording(
                        expected_remaining_after_admission=50 - k,
                        expected_used_after_admission=k,
                    )
                self.assertEqual(self.sm.restarts_remaining, 48)
                self.assertEqual(self.sm.session_restarts_used, 2)

                # Admit 3rd continuation (consumes 1 unit: remaining=47, used=3, attempt_admitted=1)
                self._prime_in_bounds_reason3_metrics(3)
                self.sm.projected_size.value = 0x100020000
                self.sm.stop_reason.value = 3
                self.sm.movie_state.value = 2
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                self.assertEqual(self.sm.restarts_remaining, 47)
                self.assertEqual(self.sm.session_restarts_used, 3)
                self.assertEqual(self.sm.attempt_admitted, 1)

                if mode == "wait_idle_timeout":
                    for _ in range(G3X_AUTOCONT_MAX_STOP_POLLS - 1):
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
                elif mode == "pending_playback":
                    self.sm.lib.host_set_mode_play(1)
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PLAYBACK)
                    self.sm.lib.host_set_mode_play(0)
                else:
                    self.sm.movie_state.value = 0
                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                    if mode == "settle_invalid_state":
                        self.sm.movie_state.value = 2
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                        self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                    else:
                        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                        if mode == "pressing_invalid_state":
                            self.sm.movie_state.value = 2
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                            self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                        else:
                            for _ in range(G3X_AUTOCONT_PRESS_POLLS - 1):
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
                            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                            if mode == "releasing_invalid_state":
                                self.sm.movie_state.value = 2
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                            else:
                                for _ in range(G3X_AUTOCONT_RELEASE_POLLS - 1):
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
                                self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                if mode == "wait_confirm_invalid_state":
                                    self.sm.movie_state.value = 2
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_INVALID_STATE)
                                elif mode == "wait_confirm_timeout":
                                    for _ in range(G3X_AUTOCONT_CONFIRM_POLLS - 1):
                                        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_TIMEOUT)
                                elif mode == "outstanding_phys_stop":
                                    # Physical stop in WAIT_CONFIRM just as the camera transitions 0 -> 1 from the
                                    # already-issued synthetic start pulse: physical stop still wins and cancels!
                                    self.sm.kbd_mod_state[0] &= ~G3X_KEY_VIDEO_BIT  # unowned modifier bit
                                    rel_before = self.sm.release_calls.value
                                    self.sm.movie_state.value = 1
                                    self.sm.set_physical_video_button(True)
                                    self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                                    self.assertEqual(self.sm.disarm_reason, G3X_AUTOCONT_REASON_PHYS_STOP)
                                    self.assertEqual(self.sm.session_cancelled, 1)
                                    self.assertEqual(self.sm.cancel_latched, 1)
                                    self.assertEqual(self.sm.release_calls.value, rel_before)  # synth_owned == 0 -> not released
                                    self.sm.kbd_mod_state[0] |= G3X_KEY_VIDEO_BIT
                                    self.sm.set_physical_video_button(False)

                # Consumed unit (47 remaining, 3 used) is never refunded on failure
                self.assertEqual(self.sm.state, G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.attempt_admitted, 0)
                self.assertEqual(self.sm.synth_owned, 0)
                self.assertEqual(self.sm.restarts_remaining, 47)
                self.assertEqual(self.sm.session_restarts_used, 3)


def _prev_idle_helper(sm: _HostPort62StandaloneHarness) -> bool:
    return (
        sm.disarm_reason != G3X_AUTOCONT_REASON_NONE
        or sm.session_cancelled != 0
        or sm.session_restarts_used > 0
        or sm.restart_count > 0
    )


_HostPort62StandaloneHarness.prev_idle_needed_for_start = _prev_idle_helper  # type: ignore[attr-defined]


class TestPort62BuildArtifactsDisassemblyAndPreservedProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_port59()
        ensure_build_port60()
        ensure_build_port61()
        ensure_build_port62()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p59_bin = ROOT / "out/port59-movie-combined/DISKBOOT.BIN"
        cls.p59_elf = ROOT / "out/port59-movie-combined/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p60_bin = ROOT / "out/port60-movie-restart-budget/DISKBOOT.BIN"
        cls.p60_elf = ROOT / "out/port60-movie-restart-budget/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p61_bin = ROOT / "out/port61-movie-session-cancel/DISKBOOT.BIN"
        cls.p61_elf = ROOT / "out/port61-movie-session-cancel/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p62_out_dir = ROOT / "build/port62-movie-standalone"
        cls.p62_bin = cls.p62_out_dir / "DISKBOOT.BIN"
        cls.p62_elf = cls.p62_out_dir / "stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.p62_obj = cls.p62_out_dir / "stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.p62_manifest = cls.p62_out_dir / "port62_movie_standalone_manifest.json"
        cls.p62_stage = cls.p62_out_dir / "stage_chdk"

    def test_default_and_existing_port55_to_port61_profiles_remain_byte_identical(self) -> None:
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

        # 5. Existing individual profiles (PORT-55, PORT-56, PORT-57, PORT-58) byte-identical
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

    def test_port62_standalone_manifest_flags_hashes_no_chdk_dir_and_disassembly_safety(self) -> None:
        self.assertTrue(self.p62_bin.is_file())
        self.assertTrue(self.p62_elf.is_file())
        self.assertTrue(self.p62_obj.is_file())
        self.assertTrue(self.p62_manifest.is_file())
        self.assertFalse((self.p62_out_dir / "CHDK").exists(), "Standalone output must not contain a CHDK/ directory")

        m = json.loads(self.p62_manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_id"], "port62_movie_standalone_manifest")
        self.assertEqual(m["milestone"], "PORT-62")
        self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_PORT61_COMMIT)
        self.assertEqual(m["candidate_source_base"], ORIGIN_MAIN_PORT61_COMMIT)
        self.assertEqual(m["integration_parent"], PORT62_INTEGRATION_PARENT)
        self.assertEqual(m["port62_integration_baseline"], PORT62_INTEGRATION_BASELINE_COMMIT)
        self.assertEqual(m["port63_fixes_commit"], "003facdc4ab64d0bc8320276432763af119b14de")
        self.assertEqual(m["port63_integration_tested_revision"], "e419648a152d9244d8faa01b47ca8e55fd885372")
        self.assertEqual(m["port63_final_integration_validation"], "PENDING_POST_MERGE_PORT_TESTS")
        self.assertEqual(m["reused_commits"]["port61_cancel_validate"], PORT61_VALIDATE_COMMIT)
        self.assertEqual(m["reused_commits"]["port62_reuse_map"], PORT62_REUSE_MAP_COMMIT)
        self.assertEqual(m["reused_commits"]["port62_integration_baseline"], PORT62_INTEGRATION_BASELINE_COMMIT)
        self.assertEqual(m["reused_commits"]["port63_fixes"], "003facdc4ab64d0bc8320276432763af119b14de")
        self.assertEqual(m["reused_commits"]["port63_integration_tested"], "e419648a152d9244d8faa01b47ca8e55fd885372")
        self.assertEqual(m["standalone_policy"]["default_restart_budget"], G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertEqual(m["standalone_policy"]["fixed_compile_time_restart_budget"], G3X_AUTOCONT_BUDGET_STANDALONE)
        self.assertTrue(m["standalone_policy"]["failed_attempts_consume_budget_without_refund"])
        self.assertTrue(m["standalone_policy"]["hermetic_staging"])
        for commit_key, commit_sha in m["reused_commits"].items():
            res = subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
                cwd=str(ROOT),
            )
            self.assertEqual(res.returncode, 0, f"Manifest reused_commits[{commit_key}]={commit_sha} is not an ancestor of HEAD")
        self.assertEqual(m["excluded_commits"], {"port54_conf_save": PORT54_EXCLUDED_COMMIT})
        self.assertEqual(m["card_writes"], "disabled")
        self.assertEqual(sha256_file(self.p62_bin), PORT62_STANDALONE_SHA256)
        self.assertEqual(self.p62_bin.stat().st_size, PORT62_STANDALONE_SIZE)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT62_STANDALONE_SHA256)
        self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], PORT62_STANDALONE_SIZE)
        self.assertEqual(m["artifacts"]["modules_count"], 0)
        self.assertEqual(m["artifacts"]["modules"], {})
        self.assertEqual(m["artifacts"]["chdk_files_count"], 0)
        self.assertEqual(m["artifacts"]["chdk_files"], {})
        self.assertEqual(m["_end"], f"0x{PORT62_STANDALONE_END}")

        flags = m["build"]["flags"]
        expected_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_MOVIE_STANDALONE=1",
            "G3X_MOVIE_STATUS=1",
            "G3X_MOVIE_NOLIMIT=1",
            "G3X_MOVIE_AUTOCONT=1",
            "G3X_MOVIE_RESTART_BUDGET=1",
            "G3X_MOVIE_SESSION_CANCEL=1",
        ]
        self.assertEqual(flags, expected_flags)
        for forbidden_flag in (
            "G3X_MOVIE_AUTOCONT_UI=1",
            "G3X_GUI5=1",
            "G3X_GUI_FIX=1",
            "G3X_GUI_DBUF=1",
            "G3X_GUI_NOOVERDRAW=1",
            "G3X_KBD_CHECK=1",
            "G3X_GUI_DIAG=1",
            "G3X_GUI_SHADOW2=1",
            "G3X_GUI_SYNC=1",
            "G3X_GUI_MENU=1",
            "G3X_GUI_RESTORE2=1",
            "G3X_PLAYBACK_MENU=1",
            "G3X_CONF_SAVE=1",
            "FULL_HOOKS=1",
        ):
            self.assertNotIn(forbidden_flag, flags)

        nm_out = subprocess.check_output([str(NM), str(self.p62_elf)], text=True)
        for req_sym in (
            "g3x_get_movie_status",
            "g3x_movie_nolimit_poll",
            "g3x_movie_autocont_poll",
            "g3x_movie_autocont_is_enabled",
            "g3x_movie_autocont_can_enable",
            "g3x_movie_autocont_set_enabled",
            "g3x_movie_autocont_get_restart_budget",
            "g3x_movie_autocont_set_restart_budget",
            "g3x_movie_autocont_get_restarts_remaining",
            "g3x_movie_autocont_get_session_restarts_used",
            "g3x_movie_autocont_is_attempt_admitted",
            "g3x_movie_autocont_can_cancel_session",
            "g3x_movie_autocont_cancel_session",
            "g3x_movie_autocont_is_session_cancelled",
            "g3x_full_shortpress_boot_entry_hook",
            "g3x_full_shortpress_post_bss_hook",
            "mykbd_task",
            "my_kbd_read_keys",
            "core_spytask",
            "kbd_process",
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
            self.assertIn(req_sym, nm_out, f"Missing symbol {req_sym} in PORT-62 main.elf")

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
        for target_path, _desc in ((self.p62_obj, "movie_rec.o"), (self.p62_elf, "main.elf")):
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

        # Verify minimal core_spytask, kbd_process, and my_kbd_read_keys disassembly in main.elf
        elf_disasm = subprocess.check_output([str(OBJDUMP), "-d", str(self.p62_elf)], text=True)
        spytask_instrs = parse_function_instructions(elf_disasm, "core_spytask")
        spytask_text = "\n".join(i["line"] for i in spytask_instrs)
        self.assertIn("<camera_info_init>", spytask_text)
        self.assertIn("<rec_mode_active>", spytask_text)
        self.assertIn("<msleep>", spytask_text)
        for forbidden_call in (
            "conf_restore",
            "gui_init",
            "gui_redraw",
            "gui_activate_alt_mode",
            "mkdir_if_not_exist",
            "script_autostart",
            "shooting_init",
            "mode_get",
            "set_palette",
            "raw_process",
            "module_tick_unloader",
        ):
            self.assertNotIn(forbidden_call, spytask_text)

        kbd_proc_instrs = parse_function_instructions(elf_disasm, "kbd_process")
        kbd_proc_text = "\n".join(i["line"] for i in kbd_proc_instrs)
        for forbidden_kbd_call in (
            "enter_alt",
            "exit_alt",
            "kbd_key_release_all",
            "gui_kbd_process",
            "action_stack_process_all",
            "script_check_terminate",
            "start_ptp_script",
            "usb_remote_key",
            "handle_usb_remote",
            "shooting_update_state",
        ):
            self.assertNotIn(forbidden_kbd_call, kbd_proc_text)

        kbd_read_instrs = parse_function_instructions(elf_disasm, "my_kbd_read_keys")
        kbd_read_text = "\n".join(i["line"] for i in kbd_read_instrs)
        idx_update = kbd_read_text.index("<kbd_update_key_state>")
        idx_physw = kbd_read_text.index("<kbd_update_physw_bits>")
        idx_nolimit = kbd_read_text.index("<g3x_movie_nolimit_poll>")
        idx_autocont = kbd_read_text.index("<g3x_movie_autocont_poll>")
        self.assertLess(idx_update, idx_physw)
        self.assertLess(idx_physw, idx_nolimit)
        self.assertLess(idx_nolimit, idx_autocont)
        self.assertIn("0x9bd0", kbd_read_text.lower())

        staged_boot_c = (self.p62_stage / "platform/g3x/sub/110c/boot.c").read_text(encoding="utf-8")
        self.assertIn("0xfc1283ad", staged_boot_c.lower())
        self.assertIn("0xfc0bd071", staged_boot_c.lower())
        self.assertNotIn("0xfc09ac19", staged_boot_c.lower())
        self.assertIn("g3x_full_shortpress_boot_entry_hook", staged_boot_c)
        self.assertIn("g3x_full_shortpress_post_bss_hook", staged_boot_c)

    def test_hermetic_standalone_build_resists_conflicting_profile_contamination_and_resolves_ftell(self) -> None:
        # 1. Verify staged core/main.c closes #if defined(G3X_MOVIE_STANDALONE) before long ftell(FILE *file)
        #    and staged main.thm.o + main.elf define T ftell (resolving libcore.a(module_hashlist.o) and ptp.thm.o U ftell)
        staged_main_c = (self.p62_stage / "core/main.c").read_text(encoding="utf-8")
        self.assertIn("        msleep(20);\n        chdk_started_flag=1;\n    }\n#endif\n}\n\nlong ftell(FILE *file) {", staged_main_c)
        staged_main_thm_o = self.p62_stage / "platform/g3x/sub/110c/main.thm.o"
        nm_main_thm = subprocess.check_output([str(NM), str(staged_main_thm_o)], text=True)
        self.assertRegex(nm_main_thm, r"\bT ftell\b")
        nm_elf = subprocess.check_output([str(NM), str(self.p62_elf)], text=True)
        self.assertRegex(nm_elf, r"\bT ftell\b")

        # 2. Reproduce conflicting-profile contamination in a self-established dirty output/staging tree
        #    (does not depend on pre-existing ignored archives in the shared chdk-port tree):
        #    Seed a build directory with conflicting PORT-61 GUI menu profile staging artifacts:
        #    - lib/core/.o2/libcore.a mutated by PORT-50..61 (gui_script.o removed, console.o compiled with G3X_GUI_FIX/DBUF)
        #    - lib/lang/.o2/liblang.a mutated by PORT-50..61 (fileutil.o removed)
        #    - platform/g3x/sub/110c/libplatformsub.a containing PORT-61 GUI objects (gui_script.thm.o, fileutil.thm.o)
        #      and a broken main.thm.o compiled with ftell stripped out (simulating the pre-fix rfind('}') defect)
        #    - stale CHDK/ distribution directory and stale manifest.json
        ar_bin = TOOLCHAIN_BIN / "arm-none-eabi-ar"
        gcc_bin = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
        p61_stage = ROOT / "out/port61-movie-session-cancel/stage_chdk"
        self.assertTrue(p61_stage.is_dir())

        with tempfile.TemporaryDirectory(prefix="port63_contaminate_") as tmpdir:
            dirty_out = Path(tmpdir) / "dirty_standalone_out"
            dirty_stage = dirty_out / "stage_chdk"
            dirty_out.mkdir(parents=True, exist_ok=True)

            # Seed dirty_stage from conflicting PORT-61 GUI profile
            subprocess.run(["cp", "-a", str(p61_stage), str(dirty_stage)], check=True)
            subprocess.run(["chmod", "-R", "u+w", str(dirty_stage)], check=True)

            # Confirm conflicting PORT-61 mutations are present before running standalone builder
            p61_libcore = dirty_stage / "lib/core/.o2/libcore.a"
            p61_libpatsub = dirty_stage / "platform/g3x/sub/110c/libplatformsub.a"
            ar_core_before = subprocess.check_output([str(ar_bin), "-t", str(p61_libcore)], text=True)
            ar_patsub_before = subprocess.check_output([str(ar_bin), "-t", str(p61_libpatsub)], text=True)
            self.assertNotIn("gui_script.o", ar_core_before)
            self.assertIn("module_hashlist.o", ar_core_before)
            self.assertIn("gui_script.thm.o", ar_patsub_before)
            self.assertIn("fileutil.thm.o", ar_patsub_before)

            # Also inject a broken ftell-less main.thm.o into dirty_stage's libplatformsub.a
            broken_main_c = Path(tmpdir) / "broken_main.c"
            broken_main_o = dirty_stage / "platform/g3x/sub/110c/main.thm.o"
            broken_main_c.write_text("void core_spytask(void) {}\n", encoding="utf-8")
            subprocess.run(
                [str(gcc_bin), "-mcpu=cortex-a9", "-mthumb", "-O2", "-c", str(broken_main_c), "-o", str(broken_main_o)],
                check=True,
            )
            subprocess.run([str(ar_bin), "rcs", str(p61_libpatsub), str(broken_main_o)], check=True)
            nm_broken = subprocess.check_output([str(NM), str(broken_main_o)], text=True)
            self.assertNotIn("ftell", nm_broken)

            # Create stale outputs in dirty_out (CHDK/ folder, manifest.json, and bogus DISKBOOT.BIN)
            (dirty_out / "CHDK" / "MODULES").mkdir(parents=True, exist_ok=True)
            (dirty_out / "CHDK" / "MODULES" / "stale.flt").write_bytes(b"STALE")
            (dirty_out / "manifest.json").write_text('{"stale": true}\n', encoding="utf-8")
            (dirty_out / "port61_movie_session_cancel_manifest.json").write_text('{"stale": true}\n', encoding="utf-8")
            (dirty_out / "DISKBOOT.BIN").write_bytes(b"CONTAMINATED")

            # Run standalone builder even with --no-clean on top of the contaminated directory
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(STANDALONE_BUILD_SCRIPT),
                    "--no-clean",
                    "--out-dir",
                    str(dirty_out),
                ],
                cwd=str(ROOT),
                check=True,
            )

            # Verify stale outputs were removed and isolated output contains only DISKBOOT.BIN, manifest, and stage_chdk
            self.assertFalse((dirty_out / "CHDK").exists())
            self.assertFalse((dirty_out / "manifest.json").exists())
            self.assertFalse((dirty_out / "port61_movie_session_cancel_manifest.json").exists())
            self.assertTrue((dirty_out / "DISKBOOT.BIN").is_file())
            self.assertTrue((dirty_out / "port62_movie_standalone_manifest.json").is_file())

            # Verify libcore.a and libplatformsub.a were rebuilt hermetically without PORT-61 mutations
            ar_core_after = subprocess.check_output(
                [str(ar_bin), "-t", str(dirty_stage / "lib/core/.o2/libcore.a")],
                text=True,
            )
            ar_patsub_after = subprocess.check_output(
                [str(ar_bin), "-t", str(dirty_stage / "platform/g3x/sub/110c/libplatformsub.a")],
                text=True,
            )
            self.assertIn("gui_script.o", ar_core_after)
            self.assertIn("module_hashlist.o", ar_core_after)
            self.assertNotIn("gui_script.thm.o", ar_patsub_after)
            self.assertNotIn("fileutil.thm.o", ar_patsub_after)

            nm_rebuilt_main = subprocess.check_output(
                [str(NM), str(dirty_stage / "platform/g3x/sub/110c/main.thm.o")],
                text=True,
            )
            self.assertRegex(nm_rebuilt_main, r"\bT ftell\b")

            # Resulting DISKBOOT.BIN is 100% byte-identical to clean standalone build
            self.assertEqual(sha256_file(dirty_out / "DISKBOOT.BIN"), PORT62_STANDALONE_SHA256)
            self.assertEqual((dirty_out / "DISKBOOT.BIN").stat().st_size, PORT62_STANDALONE_SIZE)
            dirty_manifest = json.loads((dirty_out / "port62_movie_standalone_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(dirty_manifest["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT62_STANDALONE_SHA256)
            self.assertEqual(dirty_manifest["artifacts"]["DISKBOOT.BIN"]["size"], PORT62_STANDALONE_SIZE)
            self.assertEqual(dirty_manifest["standalone_policy"]["default_restart_budget"], 50)

    @staticmethod
    def validate_agentbridge_port_tests_log_evidence(
        doc_text: str,
        *,
        artifacts_root: Path = Path("/var/lib/agentbridge/artifacts"),
    ) -> None:
        """Validate cited AgentBridge validation logs, ensuring every recorded log exists on disk,
        is attributed strictly to its actual tested 40-char revision SHA on its citing line(s),
        and matches the recorded outcome.
        """
        log_pattern = re.compile(
            re.escape(str(artifacts_root)) + r"/[A-Za-z0-9_./-]+\.log"
        )
        cited_logs = log_pattern.findall(doc_text)
        if not cited_logs:
            raise AssertionError("Expected cited AgentBridge validation log paths in docs/PORT62_MOVIE_STANDALONE.md")

        for log_str in cited_logs:
            log_path = Path(log_str)
            if not log_path.is_file():
                raise AssertionError(f"Referenced AgentBridge validation log does not exist on disk: {log_str}")

            if log_path.name == "validation-port_tests.log":
                matching_lines = [line for line in doc_text.splitlines() if log_str in line]
                if not matching_lines:
                    raise AssertionError(f"Log path not found on any line of document: {log_str}")
                attributed_shas: set[str] = set()
                for line in matching_lines:
                    for sha in re.findall(r"\b[0-9a-f]{40}\b", line):
                        if not re.search(rf"[0-9a-f]{re.escape(sha)}|{re.escape(sha)}[0-9a-f]", line):
                            attributed_shas.add(sha)
                if not attributed_shas:
                    raise AssertionError(
                        f"AgentBridge port_tests log {log_str} lacks explicit 40-char commit SHA attribution on its citing line(s)"
                    )

                # Task-level AgentBridge port_tests logs must never be attributed to the integration merge commit e419648
                if "/tasks/" in log_str and "e419648a152d9244d8faa01b47ca8e55fd885372" in attributed_shas:
                    raise AssertionError(
                        f"Task-level AgentBridge port_tests log {log_str} must be attributed only to its actual task revision, not integration revision e419648a152d9244d8faa01b47ca8e55fd885372"
                    )

                log_content = log_path.read_text(encoding="utf-8", errors="replace")
                if "unittest discover -s tests -p" not in log_content:
                    raise AssertionError(
                        f"AgentBridge port_tests log {log_str} does not record unittest discovery command"
                    )

                log_commit_matches = re.findall(r"(?:commit|revision|HEAD)[:=\s]+([0-9a-f]{40})\b", log_content, re.I)
                for log_sha in log_commit_matches:
                    if log_sha.lower() not in attributed_shas:
                        raise AssertionError(
                            f"Log {log_str} internal revision {log_sha} does not match attributed SHA(s) {sorted(attributed_shas)}"
                        )

                if "milestones/50/validation-port_tests.log" in log_str:
                    if PORT62_INTEGRATION_BASELINE_COMMIT not in attributed_shas:
                        raise AssertionError(
                            f"Milestone 50 baseline log {log_str} must be attributed to {PORT62_INTEGRATION_BASELINE_COMMIT}"
                        )
                    if "FAILED (errors=1, skipped=4)" not in log_content or "ftell" not in log_content:
                        raise AssertionError(
                            f"Milestone 50 baseline log {log_str} does not contain expected ftell failure outcome"
                        )
                else:
                    if not re.search(r"Ran \d+ tests in [\d.]+s", log_content):
                        raise AssertionError(f"PORT-63 port_tests log {log_str} missing 'Ran N tests' summary")
                    if "OK (skipped=4)" not in log_content:
                        raise AssertionError(f"PORT-63 port_tests log {log_str} did not finish with 'OK (skipped=4)'")

    def test_milestone_doc_records_commits_hashes_evidence_and_owner_trial_plan(self) -> None:
        doc_text = DOC_PORT62.read_text(encoding="utf-8")
        for token in (
            ORIGIN_MAIN_PORT61_COMMIT,
            PORT61_INTEGRATION_TIP,
            PORT61_VALIDATE_COMMIT,
            PORT61_BUILD_COMMIT,
            PORT61_INTERFACE_COMMIT,
            ORIGIN_MAIN_PORT60_COMMIT,
            PORT60_BUDGET_SHA256,
            PORT59_COMBINED_SHA256,
            PORT61_CANCEL_SHA256,
            BASE_DEFAULT_SHA256,
            PORT62_REUSE_MAP_COMMIT,
            PORT62_INTEGRATION_PARENT,
            PORT62_INTEGRATION_BASELINE_COMMIT,
            "003facdc4ab64d0bc8320276432763af119b14de",
            "e419648a152d9244d8faa01b47ca8e55fd885372",
            "4b95d5a6b7f6eb95cb518ffac0e13c457135abcf",
            "5b4fc25b5bb291757791a1ccb581baaaa0f6e943",
            "e55222db507d895bfe232197e8f055663ef3847f",
            PORT62_STANDALONE_SHA256,
            str(PORT62_STANDALONE_SIZE),
            f"0x{PORT62_STANDALONE_END}",
            "G3X_MOVIE_STANDALONE=1",
            "G3X_AUTOCONT_BUDGET_STANDALONE = 50U",
            "ftell",
            "T2_PRODUCED_CANDIDATE",
            "test_port27_resident.py",
            "build/port62-movie-standalone/DISKBOOT.BIN",
            "port62_movie_standalone_manifest.json",
            "scripts/build_port62_movie_standalone.py",
            "CAMERA BEHAVIOR UNVERIFIED",
            "PENDING_POST_MERGE_PORT_TESTS",
            "Pass / Fail Criteria",
            "Battery-Pull Recovery",
        ):
            self.assertIn(token, doc_text, f"Missing '{token}' in docs/PORT62_MOVIE_STANDALONE.md")

        # Verify documentation makes no unsupported claim that identical Git trees or task passes
        # establish an integration-revision pass, and explicitly leaves final integration validation pending.
        self.assertNotIn("identical git tree", doc_text.lower())
        self.assertIn("do not establish an integration-revision pass", doc_text.lower())
        self.assertIn("milestone completion remains gated", doc_text.lower())

        if Path("/var/lib/agentbridge/artifacts").is_dir():
            self.validate_agentbridge_port_tests_log_evidence(doc_text)

        with tempfile.TemporaryDirectory(prefix="port63_log_evidence_") as tmpdir:
            fake_artifacts = Path(tmpdir) / "artifacts"
            m51_dir = fake_artifacts / "milestones" / "51"
            m51_dir.mkdir(parents=True, exist_ok=True)
            m51_log = m51_dir / "validation-port_tests.log"
            m51_log.write_text(
                "$ python3 -B -m unittest discover -s tests -p test_port*.py\n"
                "--- stdout ---\n"
                "commit: e419648a152d9244d8faa01b47ca8e55fd885372\n"
                "----------------------------------------------------------------------\n"
                "Ran 1629 tests in 646.000s\n\n"
                "OK (skipped=4)\n",
                encoding="utf-8",
            )
            synthetic_doc = (
                f"| Milestone 51 integration (`e419648a152d9244d8faa01b47ca8e55fd885372`) "
                f"| `python3 -B -m unittest discover -s tests -p test_port*.py` "
                f"| `OK (skipped=4)` | `{m51_log}` |\n"
            )
            self.validate_agentbridge_port_tests_log_evidence(synthetic_doc, artifacts_root=fake_artifacts)

            bad_attr_doc = (
                f"| Milestone 51 integration (`003facdc4ab64d0bc8320276432763af119b14de`) "
                f"| `python3 -B -m unittest discover -s tests -p test_port*.py` "
                f"| `OK (skipped=4)` | `{m51_log}` |\n"
            )
            with self.assertRaises(AssertionError):
                self.validate_agentbridge_port_tests_log_evidence(bad_attr_doc, artifacts_root=fake_artifacts)

            m51_log.write_text(
                "$ python3 -B -m unittest discover -s tests -p test_port*.py\n"
                "Ran 1629 tests in 646.000s\n\n"
                "FAILED (errors=1, skipped=4)\n",
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError):
                self.validate_agentbridge_port_tests_log_evidence(synthetic_doc, artifacts_root=fake_artifacts)

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
            self.assertEqual(res.returncode, 0, f"Unresolvable commit hash in docs/PORT62_MOVIE_STANDALONE.md: {commit_hash}")


if __name__ == "__main__":
    unittest.main()
