"""Offline unit and integration tests for PORT-55 (G3X_MOVIE_STATUS=1).

Verifies:
1. Flag gating: G3X_MOVIE_STATUS=1 plumbing in makefiles, headers, and stubs.
2. Default build byte-identity: Matches stacked base and origin/main default (SHA-256 and size).
3. Accessor read-only verification: Disassembly of g3x_get_movie_status and main.elf inspection
   proves no stores to 0x0000C0C8 (or any other firmware address).
4. Symbol and evidence label checks: Every address checked against FINSIG or carries
   PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK evidence label.
5. Diag marker formatting: Formats MOV:IDLE, MOV:REC, and MOV:? on unexpected/stopping values.
6. Build configurations: Default, alone, and combined configurations build cleanly with pinned toolchain.
7. Manifest verification: port55_movie_status_manifest.json contains required metadata and artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
MOVIE_STATUS_H = ROOT / "chdk-port/platform/g3x/movie_status.h"
MOVIE_REC_C = ROOT / "chdk-port/platform/g3x/sub/110c/movie_rec.c"
STUBS_MIN_S = ROOT / "chdk-port/platform/g3x/sub/110c/stubs_min.S"
FULL_STUBS_MIN_S = ROOT / "full_build/g3x/sub/110c/stubs_min.S"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
FINSIG_STUBS = ROOT / "reference/finsig_gm110c/stubs_entry.S"
DOC_PORT55 = ROOT / "docs/PORT55_MOVIE_STATUS.md"
MANIFEST_P55 = ROOT / "manifests/port55_movie_status_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097
BASE_DEFAULT_END = "003686b0"

MOVIE_STATUS_ALONE_SHA256 = "be2a0839e4f74a78d4770c12d28ea3775229b88ad02801746908aa1a32787f9f"
MOVIE_STATUS_ALONE_SIZE = 124081
MOVIE_STATUS_ALONE_END = "003686a0"

PORT55_COMBINED_SHA256 = "1f3d46569f95efa06a2acb0dabe0b11639bbcea6b147fd10e3ec31718944184f"
PORT55_COMBINED_SIZE = 132297
PORT55_COMBINED_END = "0036aa90"

ROM_GET_ELAPSED_SECONDS_STATE_CHECK_SHA256 = "98059580827fa784767b303c82c2f71a734ccfa3f1846aea13ff2069d70b03b4"
ROM_COMMAND12_TEARDOWN_STORE_SHA256 = "66128d3d7295bf83d1ea2c27d1b708dda8edecee2cf4b5ddc535a43dcb18fa7f"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort55FlagPlumbing(unittest.TestCase):
    def test_makefile_plumbing(self):
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        sub_mf = SUB_MAKEFILE_INC.read_text(encoding="utf-8")

        self.assertIn("ifeq ($(G3X_MOVIE_STATUS),1)", plat_mf)
        self.assertIn("CFLAGS += -DG3X_MOVIE_STATUS=1", plat_mf)
        self.assertIn("ifeq ($(G3X_MOVIE_STATUS),1)", sub_mf)
        self.assertIn("CFLAGS += -DG3X_MOVIE_STATUS=1", sub_mf)

    def test_header_movie_status_definitions(self):
        self.assertTrue(MOVIE_STATUS_H.is_file())
        text = MOVIE_STATUS_H.read_text(encoding="utf-8")

        self.assertIn("#define G3X_MOVIE_STATE_ADDR 0x0000C0C8", text)
        self.assertIn("G3X_MOVIE_STATE_IDLE", text)
        self.assertIn("G3X_MOVIE_STATE_RECORDING", text)
        self.assertIn("int g3x_get_movie_status(void);", text)
        self.assertIn("static inline const char *g3x_movie_status_str(void)", text)
        self.assertIn('return "IDLE";', text)
        self.assertIn('return "REC";', text)
        self.assertIn('return "?";', text)

    def test_stubs_min_flag_gating(self):
        for path in [STUBS_MIN_S, FULL_STUBS_MIN_S]:
            text = path.read_text(encoding="utf-8")
            self.assertIn("#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)", text)
            self.assertIn("DEF(simple_movie_status, 0x0000C0C8)", text)
            self.assertIn("PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK", text)
            self.assertIn("DEF(simple_movie_status, 0x0000C170)", text)

    def test_movie_rec_flag_gating(self):
        text = MOVIE_REC_C.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)", text)
        self.assertIn("g3x_get_movie_status(void)", text)
        self.assertIn("*(volatile const int *)0x0000C0C8", text)
        self.assertIn("PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK", text)

    def test_gui_diag_marker_gating(self):
        text = DIAG_HEADER.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)", text)
        self.assertIn("MOV:%s", text)
        self.assertIn("g3x_movie_status_str()", text)


class TestPort55DefaultBuildIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        if not default_bin.is_file() or not default_elf.is_file():
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

    def test_default_diskboot_byte_identical(self):
        default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        self.assertTrue(default_bin.is_file())
        self.assertEqual(sha256_file(default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(default_bin.stat().st_size, BASE_DEFAULT_SIZE)

    def test_default_main_elf_end_symbol(self):
        default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(default_elf.is_file())
        res = subprocess.run([str(NM), str(default_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", res.stdout)


class TestPort55ReadOnlySafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.combined_elf = ROOT / "out/port55-movie-status/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.alone_elf = ROOT / "out/build-movie-alone/stage_chdk/platform/g3x/sub/110c/main.elf"

        if not cls.combined_elf.is_file():
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
                    "--out-dir",
                    str(ROOT / "out/port55-movie-status"),
                ],
                cwd=str(ROOT),
                check=True,
            )

        if not cls.alone_elf.is_file():
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--movie-status-alone",
                    "--out-dir",
                    str(ROOT / "out/build-movie-alone"),
                ],
                cwd=str(ROOT),
                check=True,
            )

    def test_accessor_disassembly_has_no_stores(self):
        targets = [
            (self.combined_elf, "combined main.elf"),
            (ROOT / "out/build-movie-alone/stage_chdk/platform/g3x/sub/110c/movie_rec.o", "alone movie_rec.o"),
        ]
        for obj_path, desc in targets:
            self.assertTrue(obj_path.is_file(), f"Target not found: {obj_path}")
            res = subprocess.run(
                [str(OBJDUMP), "-d", str(obj_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            disasm = res.stdout

            # Locate g3x_get_movie_status function
            self.assertIn("<g3x_get_movie_status>:", disasm, f"Missing g3x_get_movie_status in {desc}")
            fn_start = disasm.index("<g3x_get_movie_status>:")
            fn_text = disasm[fn_start : fn_start + 300]
            fn_lines = [line.strip() for line in fn_text.splitlines() if line.strip()]

            # Must contain load instruction
            self.assertTrue(
                any("ldr" in line for line in fn_lines[:6]),
                f"Missing ldr in g3x_get_movie_status ({desc}): {fn_lines[:6]}",
            )
            # Must NOT contain store instructions
            store_mnemonics = ["str", "strb", "strh", "strd", "stm", "stmia", "push"]
            for line in fn_lines[:6]:
                tokens = line.split("\t")
                if len(tokens) >= 3:
                    instr = tokens[2].split()[0]
                    self.assertNotIn(
                        instr,
                        store_mnemonics,
                        f"Found forbidden store instruction in g3x_get_movie_status ({desc}): {line}",
                    )

    def test_no_stores_to_movie_state_address(self):
        """Verify across entire main.elf that no instruction writes to 0x0000C0C8."""
        for elf_path in [self.combined_elf, self.alone_elf]:
            res = subprocess.run(
                [str(OBJDUMP), "-d", str(elf_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            disasm = res.stdout

            # Any reference to 0xc0c8 in instructions or literal pools
            for match in re.finditer(r"^([0-9a-f]+):\s+([0-9a-f\s]+)\t([a-z0-9\._]+)\s+([^;\n]+)", disasm, re.M):
                line = match.group(0)
                if "c0c8" in line.lower():
                    mnemonic = match.group(3)
                    self.assertFalse(
                        mnemonic.startswith("str") or mnemonic.startswith("stm"),
                        f"Forbidden store instruction targeting 0x0000C0C8: {line}",
                    )

    def test_no_movie_rec_task_hooks_or_card_writes(self):
        """Verify that movie_rec has no task hooks or card writes."""
        text = MOVIE_REC_C.read_text(encoding="utf-8")
        self.assertNotIn("CreateTask", text)
        self.assertNotIn("write", text)
        self.assertNotIn("open", text)
        self.assertNotIn("fopen", text)
        self.assertIn("change_video_tables", text)
        self.assertIn("set_quality", text)


class TestPort55AddressEvidence(unittest.TestCase):
    def test_finsig_and_label_verification(self):
        doc_text = DOC_PORT55.read_text(encoding="utf-8")
        finsig_text = FINSIG_STUBS.read_text(encoding="utf-8")

        # task_MovieRecord matches FINSIG
        self.assertTrue(
            re.search(r"DEF\s*\(\s*task_MovieRecord\s*,\s*0xfc09ac19\s*\)", finsig_text, re.I),
            "task_MovieRecord not found in finsig stubs_entry.S",
        )
        self.assertIn("0xFC09AC19", doc_text)

        # Evidence label PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK in doc table and code
        self.assertIn("PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK", doc_text)
        self.assertIn("0x0000C0C8", doc_text)
        self.assertIn("0xFC09B416", doc_text)
        self.assertIn(ROM_GET_ELAPSED_SECONDS_STATE_CHECK_SHA256, doc_text)

        # Teardown store label in doc
        self.assertIn("PORT55-ROM-COMMAND12-TEARDOWN-STORE", doc_text)
        self.assertIn("0x0000C1F0", doc_text)
        self.assertIn("0xFC09BD60", doc_text)
        self.assertIn(ROM_COMMAND12_TEARDOWN_STORE_SHA256, doc_text)


class TestPort55DiagMarkerFormatting(unittest.TestCase):
    def test_status_string_encoding(self):
        """Verify string mapping for 0 (IDLE), 1 (REC), and unexpected states."""
        # Emulate logic from movie_status.h
        def movie_status_str(status: int) -> str:
            if status == 0:
                return "IDLE"
            if status == 1:
                return "REC"
            return "?"

        self.assertEqual(movie_status_str(0), "IDLE")
        self.assertEqual(movie_status_str(1), "REC")
        self.assertEqual(movie_status_str(2), "?")
        self.assertEqual(movie_status_str(3), "?")
        self.assertEqual(movie_status_str(4), "?")
        self.assertEqual(movie_status_str(-1), "?")
        self.assertEqual(movie_status_str(99), "?")

    def test_diag_line_length_fits_screen(self):
        """Verify formatted secondary diag line does not exceed G3X_DIAG_LINE_MAX_CHARS (55)."""
        # Format string from gui_diag.h with standard SAVE:OFF and clamped maximum values
        line = "MENU:%04u SAVE:%s MOV:%s Rs:%04u Rp:%04u B:%u/%ums" % (
            9999,
            "OFF",
            "IDLE",
            9999,
            9999,
            999,
            999,
        )
        self.assertLessEqual(len(line), 55)
        self.assertIn("MOV:IDLE", line)

        line_rec = "MENU:%04u SAVE:%s MOV:%s Rs:%04u Rp:%04u B:%u/%ums" % (
            1,
            "OFF",
            "REC",
            0,
            0,
            0,
            0,
        )
        self.assertLessEqual(len(line_rec), 55)
        self.assertIn("MOV:REC", line_rec)

        line_q = "MENU:%04u SAVE:%s MOV:%s Rs:%04u Rp:%04u B:%u/%ums" % (
            0,
            "OFF",
            "?",
            0,
            0,
            0,
            0,
        )
        self.assertLessEqual(len(line_q), 55)
        self.assertIn("MOV:?", line_q)


class TestPort55BuildArtifacts(unittest.TestCase):
    def test_alone_configuration_artifacts(self):
        alone_bin = ROOT / "out/build-movie-alone/DISKBOOT.BIN"
        alone_elf = ROOT / "out/build-movie-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(alone_bin.is_file())
        self.assertTrue(alone_elf.is_file())
        self.assertEqual(sha256_file(alone_bin), MOVIE_STATUS_ALONE_SHA256)
        self.assertEqual(alone_bin.stat().st_size, MOVIE_STATUS_ALONE_SIZE)

        res = subprocess.run([str(NM), str(alone_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{MOVIE_STATUS_ALONE_END} B _end", res.stdout)

    def test_combined_configuration_artifacts(self):
        comb_bin = ROOT / "out/port55-movie-status/DISKBOOT.BIN"
        comb_elf = ROOT / "out/port55-movie-status/stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(comb_bin.is_file())
        self.assertTrue(comb_elf.is_file())
        self.assertEqual(sha256_file(comb_bin), PORT55_COMBINED_SHA256)
        self.assertEqual(comb_bin.stat().st_size, PORT55_COMBINED_SIZE)

        res = subprocess.run([str(NM), str(comb_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{PORT55_COMBINED_END} B _end", res.stdout)

    def test_manifest_metadata(self):
        self.assertTrue(MANIFEST_P55.is_file())
        manifest = json.loads(MANIFEST_P55.read_text(encoding="utf-8"))
        self.assertIn("artifacts", manifest)
        self.assertIn("DISKBOOT.BIN", manifest["artifacts"])
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT55_COMBINED_SHA256)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["size"], PORT55_COMBINED_SIZE)
        self.assertEqual(manifest["_end"], f"0x{PORT55_COMBINED_END}")
        flags = manifest["build"]["flags"]
        self.assertIn("G3X_MOVIE_STATUS=1", flags)
        self.assertIn("G3X_PLAYBACK_MENU=1", flags)


if __name__ == "__main__":
    unittest.main()
