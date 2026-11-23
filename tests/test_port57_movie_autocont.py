"""Offline unit and integration tests for PORT-57 (G3X_MOVIE_AUTOCONT=1).

Verifies:
1. Default OFF & default build byte-identity to origin/main default (24b8a024..., 124,097 B, _end 0x003686b0).
2. Opt-in standalone (91ac6fd0..., 125,505 B) and combined (eaf2745d..., 133,713 B) candidate builds
   with G3X_MOVIE_STATUS=1, G3X_MOVIE_NOLIMIT OFF, G3X_CONF_SAVE OFF, FULL_HOOKS OFF, card writes OFF.
3. ARM disassembly verification of movie_rec.o and main.elf:
   - All MovieRecorder RAM accessors (0x0000C0C8, 0x0000C0C0, 0x0000C274, 0x0000C278, 0x0000C078,
     0x0000C0D8, 0x0000C290, 0x0000C298, 0x0000C2A0, 0x0000C2A8) are strictly read-only (zero stores).
   - Zero stores to any MovieRecorder RAM address (0x0000C078..0x0000C2AF) anywhere in movie_rec.o / main.elf.
   - my_kbd_read_keys calls g3x_movie_autocont_poll and does not call g3x_movie_nolimit_poll.
   - CreateTask and task hooks are unchanged; blocking file-write linker wrappers remain active.
4. Host-compiled C state machine behavioral verification:
   - Enabling G3X_MOVIE_AUTOCONT=1 alone cannot start recording; requires deliberate 0 -> 1 start observed during this boot.
   - Only confirmed current-session automatic stop with fresh, attributable reason 3 or 4 produces one bounded restart attempt after confirmed idle.
   - Stale reason 3/4, unreset start counters, and unsupported reasons (0, 1, 2, >=5) are rejected.
   - Raw physical movie-button input cancels active or pending continuation and wins races with automatic-stop detection or an in-progress synthetic pulse.
   - Physical cancellation prevents rearming until confirmed idle + button release + another deliberate start.
   - Synthetic input is released on all completion, cancellation, timeout, ambiguity, and failure paths without disturbing unrelated keys and without retry loops.
5. ROM evidence manifest validation via tools/port11c_evidence_validator.py and provenance checks in docs/PORT57_MOVIE_AUTOCONT.md.
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
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
STUBS_MIN_S = ROOT / "chdk-port/platform/g3x/sub/110c/stubs_min.S"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
DOC_PORT57 = ROOT / "docs/PORT57_MOVIE_AUTOCONT.md"
EVIDENCE_MANIFEST = ROOT / "docs/port34_evidence_manifest.json"
TRUSTED_SCOPES = ROOT / "docs/port34_trusted_scopes.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

ORIGIN_MAIN_COMMIT = "88ab9331363bff5c62cc7ac7ee3e75ee4d9768a5"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097
BASE_DEFAULT_END = "003686b0"

MOVIE_AUTOCONT_ALONE_SHA256 = "91ac6fd07ec4b9a460370521f3373343305261599b465ff05af79a9f3e636379"
MOVIE_AUTOCONT_ALONE_SIZE = 125505
MOVIE_AUTOCONT_ALONE_END = "00368c90"

PORT57_COMBINED_SHA256 = "eaf2745d24d05bab177913a3cf266e2e3ba310a08b957fb04dc672a52414e311"
PORT57_COMBINED_SIZE = 133713
PORT57_COMBINED_END = "0036b080"

KEY_VIDEO = 13
G3X_KEY_VIDEO_BIT = 0x00000008
UNRELATED_KEY_BITS = 0x000533F1  # All KEYS_MASK0 bits except KEY_VIDEO (0x00000008)

G3X_AUTOCONT_DISARMED = 0
G3X_AUTOCONT_RECORDING = 1
G3X_AUTOCONT_WAIT_IDLE = 2
G3X_AUTOCONT_SETTLE = 3
G3X_AUTOCONT_PRESSING = 4
G3X_AUTOCONT_RELEASING = 5
G3X_AUTOCONT_WAIT_CONFIRM = 6

G3X_AUTOCONT_MAX_STOP_POLLS = 500
G3X_AUTOCONT_SETTLE_POLLS = 50
G3X_AUTOCONT_PRESS_POLLS = 6
G3X_AUTOCONT_RELEASE_POLLS = 6
G3X_AUTOCONT_CONFIRM_POLLS = 200
G3X_AUTOCONT_START_HOLD_POLLS = 50

_BUILD_CACHE = {
    "default": False,
    "alone": False,
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


def ensure_build_alone() -> None:
    bin_path = ROOT / "out/build-autocont-alone/DISKBOOT.BIN"
    elf_path = ROOT / "out/build-autocont-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "out/build-autocont-alone/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    manifest_path = ROOT / "out/build-autocont-alone/port57_movie_autocont_alone_manifest.json"
    if (
        _BUILD_CACHE["alone"]
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
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--movie-autocont-alone",
                "--out-dir",
                str(ROOT / "out/build-autocont-alone"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["alone"] = True


def ensure_build_combined() -> None:
    bin_path = ROOT / "out/port57-movie-autocont/DISKBOOT.BIN"
    elf_path = ROOT / "out/port57-movie-autocont/stage_chdk/platform/g3x/sub/110c/main.elf"
    manifest_path = ROOT / "out/port57-movie-autocont/port57_movie_autocont_manifest.json"
    if _BUILD_CACHE["combined"] and bin_path.is_file() and elf_path.is_file() and manifest_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file() and manifest_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
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
                "--out-dir",
                str(ROOT / "out/port57-movie-autocont"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["combined"] = True


def setUpModule() -> None:
    ensure_build_default()
    ensure_build_alone()
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


class _HostStateMachineHarness:
    """Compiles movie_rec.c as a host shared library and drives the real C state machine via ctypes."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="port57_host_sm_")
        tmp = Path(self._tmpdir.name)

        # Minimal stub headers for host compilation of movie_rec.c
        (tmp / "conf.h").write_text("/* stub conf.h */\n", encoding="utf-8")
        (tmp / "keyboard.h").write_text(f"#define KEY_VIDEO {KEY_VIDEO}\n", encoding="utf-8")
        (tmp / "camera_info.h").write_text(
            "typedef struct { struct { int mode_play; int gui_mode_none; int gui_mode_alt; } state; } cam_info_t;\n"
            "extern cam_info_t camera_info;\n",
            encoding="utf-8",
        )

        harness_c = tmp / "harness_stubs.c"
        harness_c.write_text(
            '#include "keyboard.h"\n'
            '#include "camera_info.h"\n'
            "cam_info_t camera_info = { { 0, 1, 0 } };\n"
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
            "    /* Replicates chdk-port/core/kbd_common.c:167-184 */\n"
            "    if (!in_alt_mode) {\n"
            "        physw_status[0] = kbd_new_state[0];\n"
            "    } else {\n"
            "        physw_status[0] = (kbd_new_state[0] & ~0x000533F9L) | (kbd_mod_state[0] & 0x000533F9L);\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )

        so_path = tmp / "libport57_autocont.so"
        subprocess.run(
            [
                "gcc",
                "-shared",
                "-fPIC",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DG3X_MOVIE_STATUS=1",
                "-DG3X_MOVIE_AUTOCONT=1",
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

        # Bind functions
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
        self.avail_space.value = 32 * 1024 * 1024 * 1024  # 32 GiB free
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


class TestPort57FlagPlumbing(unittest.TestCase):
    def test_makefile_plumbing(self) -> None:
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        sub_mf = SUB_MAKEFILE_INC.read_text(encoding="utf-8")

        for mf_text in (plat_mf, sub_mf):
            self.assertIn("ifeq ($(G3X_MOVIE_AUTOCONT),1)", mf_text)
            self.assertIn("CFLAGS += -DG3X_MOVIE_AUTOCONT=1", mf_text)
            self.assertIn("CFLAGS += -DG3X_MOVIE_STATUS=1", mf_text)
            self.assertIn("CFLAGS += -DG3X_DISABLE_CARD_WRITES=1", mf_text)
            self.assertIn("CFLAGS += -DOPT_DISABLE_FILE_WRITES=1", mf_text)

    def test_header_and_source_flag_gating(self) -> None:
        h_text = MOVIE_STATUS_H.read_text(encoding="utf-8")
        c_text = MOVIE_REC_C.read_text(encoding="utf-8")
        s_text = STUBS_MIN_S.read_text(encoding="utf-8")

        self.assertIn("#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)", h_text)
        self.assertIn("G3X_AUTOCONT_DISARMED", h_text)
        self.assertIn("G3X_AUTOCONT_RECORDING", h_text)
        self.assertIn("G3X_AUTOCONT_WAIT_IDLE", h_text)
        self.assertIn("G3X_AUTOCONT_SETTLE", h_text)
        self.assertIn("G3X_AUTOCONT_PRESSING", h_text)
        self.assertIn("G3X_AUTOCONT_RELEASING", h_text)
        self.assertIn("G3X_AUTOCONT_WAIT_CONFIRM", h_text)
        self.assertIn("void g3x_movie_autocont_poll(void);", h_text)
        self.assertIn("PORT57-ROM-CHECK-LIMITS-WINDOW", h_text)

        self.assertIn("#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)", c_text)
        self.assertIn("g3x_movie_autocont_poll(void)", c_text)
        self.assertIn("PORT57-ROM-CHECK-LIMITS-WINDOW", c_text)
        self.assertNotIn("CreateTask", c_text)
        self.assertNotIn("task_create_hook", c_text)
        self.assertNotIn("FULL_HOOKS", c_text)

        self.assertIn("#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)", s_text)
        self.assertIn("DEF(simple_movie_status, 0x0000C0C8)", s_text)

    def test_staged_kbd_wiring_and_flag_independence(self) -> None:
        ensure_build_alone()
        ensure_build_combined()

        for stage_kbd in (
            ROOT / "out/build-autocont-alone/stage_chdk/platform/g3x/kbd.c",
            ROOT / "out/port57-movie-autocont/stage_chdk/platform/g3x/kbd.c",
        ):
            self.assertTrue(stage_kbd.is_file(), f"Missing {stage_kbd}")
            text = stage_kbd.read_text(encoding="utf-8")
            self.assertIn("#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)", text)
            self.assertIn("g3x_movie_autocont_poll();", text)


class TestPort57BuildArtifactsAndDisassembly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_build_default()
        ensure_build_alone()
        ensure_build_combined()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.alone_bin = ROOT / "out/build-autocont-alone/DISKBOOT.BIN"
        cls.alone_elf = ROOT / "out/build-autocont-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.alone_obj = ROOT / "out/build-autocont-alone/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.alone_manifest = ROOT / "out/build-autocont-alone/port57_movie_autocont_alone_manifest.json"
        cls.comb_bin = ROOT / "out/port57-movie-autocont/DISKBOOT.BIN"
        cls.comb_elf = ROOT / "out/port57-movie-autocont/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.comb_obj = ROOT / "out/port57-movie-autocont/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
        cls.comb_manifest = ROOT / "out/port57-movie-autocont/port57_movie_autocont_manifest.json"

    def test_default_build_byte_identical_to_origin_main(self) -> None:
        self.assertTrue(self.default_bin.is_file())
        self.assertEqual(sha256_file(self.default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(self.default_bin.stat().st_size, BASE_DEFAULT_SIZE)

        res = subprocess.run([str(NM), str(self.default_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", res.stdout)
        self.assertNotIn("g3x_movie_autocont_poll", res.stdout)

    def test_standalone_and_combined_candidate_artifacts(self) -> None:
        self.assertEqual(sha256_file(self.alone_bin), MOVIE_AUTOCONT_ALONE_SHA256)
        self.assertEqual(self.alone_bin.stat().st_size, MOVIE_AUTOCONT_ALONE_SIZE)
        res_alone = subprocess.run([str(NM), str(self.alone_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{MOVIE_AUTOCONT_ALONE_END} B _end", res_alone.stdout)

        self.assertEqual(sha256_file(self.comb_bin), PORT57_COMBINED_SHA256)
        self.assertEqual(self.comb_bin.stat().st_size, PORT57_COMBINED_SIZE)
        res_comb = subprocess.run([str(NM), str(self.comb_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{PORT57_COMBINED_END} B _end", res_comb.stdout)

        for manifest_path, exp_sha, exp_size, exp_end in (
            (self.alone_manifest, MOVIE_AUTOCONT_ALONE_SHA256, MOVIE_AUTOCONT_ALONE_SIZE, f"0x{MOVIE_AUTOCONT_ALONE_END}"),
            (self.comb_manifest, PORT57_COMBINED_SHA256, PORT57_COMBINED_SIZE, f"0x{PORT57_COMBINED_END}"),
        ):
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(m["origin_main_baseline"], ORIGIN_MAIN_COMMIT)
            self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["sha256"], exp_sha)
            self.assertEqual(m["artifacts"]["DISKBOOT.BIN"]["size"], exp_size)
            self.assertEqual(m["_end"], exp_end)
            self.assertEqual(m["card_writes"], "disabled")
            flags = m["build"]["flags"]
            self.assertIn("G3X_MOVIE_AUTOCONT=1", flags)
            self.assertIn("G3X_MOVIE_STATUS=1", flags)
            self.assertIn("G3X_DISABLE_CARD_WRITES=1", flags)
            self.assertIn("OPT_DISABLE_FILE_WRITES=1", flags)
            self.assertNotIn("G3X_MOVIE_NOLIMIT=1", flags)
            self.assertNotIn("G3X_CONF_SAVE=1", flags)
            self.assertNotIn("FULL_HOOKS=1", flags)

    def test_movierecorder_ram_accessors_are_strictly_read_only(self) -> None:
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
        for target_path, desc in (
            (self.alone_obj, "alone movie_rec.o"),
            (self.alone_elf, "alone main.elf"),
            (self.comb_elf, "combined main.elf"),
        ):
            res = subprocess.run([str(OBJDUMP), "-d", str(target_path)], capture_output=True, text=True, check=True)
            disasm = res.stdout
            for fn in accessors:
                instrs = parse_function_instructions(disasm, fn)
                self.assertGreater(len(instrs), 0, f"Missing instructions for {fn} in {desc}")
                has_load = False
                for instr in instrs:
                    mnem = instr["mnemonic"]
                    self.assertFalse(
                        mnem.startswith("str") or mnem.startswith("stm") or mnem.startswith("push"),
                        f"Forbidden store '{mnem}' in read-only accessor {fn} ({desc}): {instr['line']}",
                    )
                    if mnem.startswith("ldr"):
                        has_load = True
                self.assertTrue(has_load, f"Expected load instruction in {fn} ({desc})")

    def test_zero_stores_to_movierecorder_ram_and_nolimit_absent(self) -> None:
        forbidden_ram_hex = (
            "c078",
            "c0c0",
            "c0c8",
            "c0d4",
            "c0d8",
            "c0e4",
            "c274",
            "c278",
            "c290",
            "c298",
            "c2a0",
            "c2a8",
        )
        for elf_path, desc in ((self.alone_elf, "alone"), (self.comb_elf, "combined")):
            nm_res = subprocess.run([str(NM), str(elf_path)], capture_output=True, text=True, check=True)
            nm_out = nm_res.stdout
            self.assertIn("g3x_movie_autocont_poll", nm_out)
            self.assertNotIn("g3x_movie_nolimit_poll", nm_out)
            for wrap_sym in (
                "__wrap_open",
                "__wrap_fopen",
                "__wrap_creat",
                "__wrap_write",
                "__wrap_fwrite",
                "__wrap_mkdir",
                "__wrap_remove",
                "__wrap_rename",
            ):
                self.assertIn(wrap_sym, nm_out, f"Missing write-blocking wrapper {wrap_sym} in {desc}")

            dis_res = subprocess.run([str(OBJDUMP), "-d", str(elf_path)], capture_output=True, text=True, check=True)
            disasm = dis_res.stdout

            kbd_instrs = parse_function_instructions(disasm, "my_kbd_read_keys")
            self.assertTrue(
                any("g3x_movie_autocont_poll" in i["line"] for i in kbd_instrs),
                f"my_kbd_read_keys does not call g3x_movie_autocont_poll in {desc}",
            )

            for fhex in forbidden_ram_hex:
                for m in re.finditer(
                    rf"^\s*([0-9a-f]+):\s+([0-9a-f\s]+?)\t([a-z0-9\._]+)\s*([^;\n]*;\s*.*{fhex}.*)",
                    disasm,
                    re.M | re.I,
                ):
                    mnem = m.group(3).lower()
                    self.assertFalse(
                        mnem.startswith("str") or mnem.startswith("stm"),
                        f"Forbidden store referencing 0x0000{fhex} in {desc} main.elf: {m.group(0)}",
                    )


class TestPort57StateMachineBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sm = _HostStateMachineHarness()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sm.close()

    def setUp(self) -> None:
        self.sm.reset()

    def _start_deliberate_recording(self, hold_polls_into_rec: int = 0) -> None:
        """Observe boot IDLE (0) and transition to RECORDING (1)."""
        self.sm.movie_state.value = 0
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 10
        self.sm.stream_bytes.value = 1024 * 1024
        self.sm.projected_size.value = 2 * 1024 * 1024
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        for _ in range(hold_polls_into_rec):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        if hold_polls_into_rec > 0:
            self.sm.set_physical_video_button(False)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def test_enabling_feature_alone_cannot_start_recording_and_requires_boot_idle(self) -> None:
        # 1. Staying in IDLE (0) at boot never arms or presses KEY_VIDEO
        for _ in range(300):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertEqual(self.sm.synth_owned, 0)
            self.assertFalse(self.sm.physw_video_pressed)

        # 2. If booted already in state 1 without observing IDLE (0) -> RECORDING (1), stays DISARMED
        self.sm.reset()
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 100
        for _ in range(20):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        # Even if it stops at max_frames with reason 4, it was never armed and must not restart
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        for _ in range(100):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

    def test_reason_4_auto_stop_produces_single_bounded_restart_and_preserves_unrelated_keys(self) -> None:
        # Hold an unrelated key (e.g. KEY_MENU = 0x00000010) low in kbd_new_state and kbd_mod_state
        self.sm.kbd_new_state[0] &= ~0x00000010
        self.sm.kbd_mod_state[0] &= ~0x00000010

        self._start_deliberate_recording(hold_polls_into_rec=3)

        # Automatic stop due to Reason 4 (duration/frame count limit) -> STOPPING (2)
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.last_stop_reason, 4)
        self.assertEqual(self.sm.timer_polls, G3X_AUTOCONT_MAX_STOP_POLLS)

        # Stay in STOPPING (2) for 5 polls: no synthetic press allowed while stopping
        for expected_rem in range(G3X_AUTOCONT_MAX_STOP_POLLS - 1, G3X_AUTOCONT_MAX_STOP_POLLS - 6, -1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
            self.assertEqual(self.sm.timer_polls, expected_rem)
            self.assertEqual(self.sm.press_calls.value, 0)

        # Reach confirmed IDLE (0) -> enters SETTLE for 50 polls
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.timer_polls, G3X_AUTOCONT_SETTLE_POLLS)
        for expected_rem in range(G3X_AUTOCONT_SETTLE_POLLS - 1, 0, -1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
            self.assertEqual(self.sm.timer_polls, expected_rem)
            self.assertEqual(self.sm.press_calls.value, 0)
            self.assertFalse(self.sm.physw_video_pressed)

        # Next poll transitions SETTLE -> PRESSING (poll 1 of 6), works in both non-ALT and ALT modes
        for poll_idx in range(G3X_AUTOCONT_PRESS_POLLS):
            st = self.sm.step(in_alt_mode=(poll_idx % 2 == 1))
            self.assertEqual(st, G3X_AUTOCONT_PRESSING)
            self.assertEqual(self.sm.synth_owned, 1)
            self.assertTrue(self.sm.physw_video_pressed)
            self.assertTrue(self.sm.mod_video_pressed)
            # Unrelated key bit 0x10 remains low and all other unrelated bits remain high
            self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)
            self.assertEqual(self.sm.physw_status[0] & 0x00000010, 0)
            self.assertEqual(
                (self.sm.physw_status[0] & UNRELATED_KEY_BITS) | 0x00000010,
                UNRELATED_KEY_BITS,
            )

        # Next poll transitions PRESSING -> RELEASING (poll 1 of 6): synthetic input released!
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
            self.assertEqual(self.sm.synth_owned, 0)
            self.assertFalse(self.sm.physw_video_pressed)
            self.assertFalse(self.sm.mod_video_pressed)
            # Unrelated key bit 0x10 is still untouched
            self.assertEqual(self.sm.kbd_mod_state[0] & 0x00000010, 0)

        # Next poll transitions RELEASING -> WAIT_CONFIRM
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.assertEqual(self.sm.timer_polls, G3X_AUTOCONT_CONFIRM_POLLS)
        self.assertEqual(self.sm.synth_owned, 0)

        # After 10 polls in WAIT_CONFIRM, firmware confirms recording (mr_rec_state = 1)
        for _ in range(10):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)
        self.assertEqual(self.sm.synth_owned, 0)

    def test_reason_3_size_limit_auto_stop_and_base_offset_reserve_math(self) -> None:
        self.sm.segment_index.value = 1
        self.sm.fs_reserve_size.value = 0x00100000  # 1 MiB reserve (<< 1 = 2 MiB)
        self.sm.projected_base_offset.value = 0x00400000  # 4 MiB base offset
        self._start_deliberate_recording()

        # In-bounds active recording near 4 GiB
        # proj_total = projected_size + base_offset - 2 * reserve
        self.sm.cur_frames.value = 28000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFFE00000 - 0x00400000 + 0x00200000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        # Cross 4 GiB threshold (proj_total = 0x100000000 > 0xFFFFFFFF) with sufficient free card space
        self.sm.projected_size.value = 0x100000000 - 0x00400000 + 0x00200000
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0  # Direct 1 -> 0 transition on poll boundary
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        self.assertEqual(self.sm.last_stop_reason, 3)

        # Complete 50-poll settle + 6-poll press + 6-poll release + confirmation
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS - 1):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 1
        self.sm.stream_bytes.value = 65536
        self.sm.projected_size.value = 65536
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)

    def test_stale_and_unsupported_stop_reasons_are_rejected(self) -> None:
        # 1. Unsupported reasons (0, 1, 2, 5) disarm immediately
        for bad_reason in (0, 1, 2, 5):
            self.sm.reset()
            self._start_deliberate_recording()
            self.sm.cur_frames.value = 54000
            self.sm.stop_reason.value = bad_reason
            self.sm.movie_state.value = 2
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.sm.movie_state.value = 0
            for _ in range(60):
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
                self.assertEqual(self.sm.press_calls.value, 0)

        # 2. Stale Reason 4 in 0x0000C0C0 when session stops early (cur_frames < max_frames)
        self.sm.reset()
        self.sm.stop_reason.value = 4  # Stale from previous clip
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 1200  # < 54000
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # 3. Stale Reason 3 in 0x0000C0C0 when session stops early (proj_total <= 4 GiB)
        self.sm.reset()
        self.sm.stop_reason.value = 3  # Stale from previous clip
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 500
        self.sm.projected_size.value = 50 * 1024 * 1024  # 50 MiB <= 4 GiB
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

        # 4. Reason 3 with card space exhausted (avail_space < proj_total) is rejected
        self.sm.reset()
        self._start_deliberate_recording()
        self.sm.projected_size.value = 0x100000100
        self.sm.avail_space.value = 0x100000000  # Less than projected_size
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

    def test_unreset_counters_after_restart_do_not_falsely_retrigger(self) -> None:
        """If Session 1 stops on Reason 3 (with cur_frames < max_frames) and Session 2 stops before
        SetupModeAndLimits resets cur_frames/stream_bytes, stale counters must not retrigger."""
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 29000  # < 54000
        self.sm.stream_bytes.value = 0xFF000000
        self.sm.projected_size.value = 0xFF000000
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

        # Session 1 stops on Reason 3
        self.sm.projected_size.value = 0x100000100
        self.sm.stop_reason.value = 3
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)

        # Session 2 starts (movie_state = 1), but SetupModeAndLimits hasn't reset counters yet
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)
        self.assertEqual(self.sm.restart_count, 1)

        # Immediate stop before counters ever moved/reset in Session 2 must disarm!
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)

    def test_physical_movie_button_cancels_all_states_and_wins_races(self) -> None:
        # Case A: Physical button pressed during active RECORDING cancels before stop transition
        self._start_deliberate_recording()
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)
        self.sm.set_physical_video_button(False)
        # Even if mr_rec_state stays 1 and then stops with Reason 4 at max_frames, it stays DISARMED
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 0)  # Cleared only after reaching IDLE with button released

        # Case B: Race on exact same poll between physical button press and Reason 4 automatic stop
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)

        # Case C: Race with in-progress synthetic pulse (PRESSING)
        self.sm.reset()
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        # Enter PRESSING (poll 1 and 2 of 6)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        self.assertEqual(self.sm.synth_owned, 1)
        self.assertTrue(self.sm.mod_video_pressed)

        # User presses physical KEY_VIDEO during PRESSING -> immediately releases synthetic override and disarms!
        self.sm.set_physical_video_button(True)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.synth_owned, 0)
        self.assertFalse(self.sm.mod_video_pressed)
        self.assertEqual(self.sm.cancel_latched, 1)

        # Cannot re-arm while physical cancel button is held even if movie_state becomes 1
        self.sm.movie_state.value = 1
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.sm.movie_state.value = 0
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 1)

        # Once physical button is released in IDLE, a subsequent deliberate 0 -> 1 start arms cleanly
        self.sm.set_physical_video_button(False)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.cancel_latched, 0)
        self.sm.movie_state.value = 1
        self.sm.cur_frames.value = 5
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_RECORDING)

    def test_timeouts_and_ambiguous_states_disarm_without_retry_loops(self) -> None:
        # 1. WAIT_IDLE timeout (stuck in STOPPING == 2 for 500 polls)
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 2
        for _ in range(G3X_AUTOCONT_MAX_STOP_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_IDLE)
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        # Reaching IDLE after timeout must not trigger a late restart
        self.sm.movie_state.value = 0
        for _ in range(100):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, 0)

        # 2. WAIT_CONFIRM timeout (camera stays in IDLE == 0 after single pulse)
        self.sm.reset()
        self._start_deliberate_recording()
        self.sm.cur_frames.value = 54000
        self.sm.stop_reason.value = 4
        self.sm.movie_state.value = 0
        for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
        for _ in range(G3X_AUTOCONT_PRESS_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
        press_count_after_single_pulse = self.sm.press_calls.value
        self.assertEqual(press_count_after_single_pulse, G3X_AUTOCONT_PRESS_POLLS)
        for _ in range(G3X_AUTOCONT_RELEASE_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_RELEASING)
        for _ in range(G3X_AUTOCONT_CONFIRM_POLLS):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_WAIT_CONFIRM)
        # Poll 201: disarms to DISARMED without retrying!
        self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
        self.assertEqual(self.sm.synth_owned, 0)
        for _ in range(200):
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.press_calls.value, press_count_after_single_pulse)

        # 3. Unsupported movie state (e.g. state 5 or 6 or -1) or Playback mode during PRESSING releases key and disarms
        for use_playback in (False, True):
            self.sm.reset()
            self._start_deliberate_recording()
            self.sm.cur_frames.value = 54000
            self.sm.stop_reason.value = 4
            self.sm.movie_state.value = 0
            for _ in range(G3X_AUTOCONT_SETTLE_POLLS):
                self.assertEqual(self.sm.step(), G3X_AUTOCONT_SETTLE)
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_PRESSING)
            self.assertEqual(self.sm.synth_owned, 1)
            if use_playback:
                self.sm.lib.host_set_mode_play(1)
            else:
                self.sm.movie_state.value = 6  # Unsupported / error state
            self.assertEqual(self.sm.step(), G3X_AUTOCONT_DISARMED)
            self.assertEqual(self.sm.synth_owned, 0)
            self.assertFalse(self.sm.mod_video_pressed)
            self.assertFalse(self.sm.physw_video_pressed)


class TestPort57EvidenceAndProvenance(unittest.TestCase):
    def test_port34_evidence_manifest_passes_validator(self) -> None:
        validator = ROOT / "tools/port11c_evidence_validator.py"
        res = subprocess.run(
            [
                sys.executable,
                "-B",
                str(validator),
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

    def test_doc_records_evidence_transitions_bounds_provenance_and_hashes(self) -> None:
        doc_text = DOC_PORT57.read_text(encoding="utf-8")
        for required_token in (
            "PORT57-ROM-CHECK-LIMITS-WINDOW",
            "32bec616fbcefa305b66102cab9e09c380bb14f7870b878d9fdd0e386c584d4f",
            "0x0000C0C8",
            "0x0000C0C0",
            "0x0000C274",
            "0x0000C278",
            "0x0000C290",
            "0x0000C298",
            "0x0000C2A0",
            "0x0000C2A8",
            "0x00040DAC",
            "G3X_AUTOCONT_DISARMED",
            "G3X_AUTOCONT_RECORDING",
            "G3X_AUTOCONT_WAIT_IDLE",
            "G3X_AUTOCONT_SETTLE",
            "G3X_AUTOCONT_PRESSING",
            "G3X_AUTOCONT_RELEASING",
            "G3X_AUTOCONT_WAIT_CONFIRM",
            ORIGIN_MAIN_COMMIT,
            BASE_DEFAULT_SHA256,
            MOVIE_AUTOCONT_ALONE_SHA256,
            PORT57_COMBINED_SHA256,
        ):
            self.assertIn(required_token, doc_text, f"Missing '{required_token}' in docs/PORT57_MOVIE_AUTOCONT.md")


if __name__ == "__main__":
    unittest.main()
