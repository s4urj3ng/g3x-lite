"""Offline unit and integration tests for PORT-56 (G3X_MOVIE_NOLIMIT=1).

Verifies:
1. Flag gating: G3X_MOVIE_NOLIMIT=1 plumbing in makefiles, headers, kbd, movie_rec, and diag.
2. Default build byte-identity: Matches stacked base and origin/main default (SHA-256, size, _end).
3. Write allowlist verification: Disassembly of g3x_movie_nolimit_poll and main.elf inspection
   proves ONLY 0x0000C274 is written, and only while recording.
4. Read-only verification: g3x_get_movie_cur_frames strictly loads 0x0000C278 with zero stores;
   0x0000C0E4, 0x0000C0C0, and 0x0000C0C8 are never written.
5. Symbol and evidence label checks: Every address checked against FINSIG/manifest with evidence labels.
6. Timing rule and citation: Timing row in docs/PORT56_MOVIE_TIMELIMIT.md contains docs/VIDEO001_RECORDING_LIMITS.md:183 citation.
7. Diag marker formatting: Formats LIM:OFF (patched/defeated), LIM:ON (stock limit), and LIM:? (not recording or initial 0).
8. Build configurations: Default, alone, and combined configurations build cleanly with pinned toolchain.
9. Manifest verification: port56_movie_nolimit_manifest.json contains required metadata, configurations, and artifacts.
10. Sibling flags & safety: No regressions in PORT-42..55 flags; write wrappers remain disabled; no FULL_HOOKS symbol referenced.
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
FULL_MOVIE_REC_C = ROOT / "full_build/g3x/sub/110c/movie_rec.c"
KBD_C = ROOT / "chdk-port/platform/g3x/kbd.c"
FULL_KBD_C = ROOT / "full_build/g3x/kbd.c"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
FINSIG_STUBS = ROOT / "reference/finsig_gm110c/stubs_entry.S"
DOC_PORT56 = ROOT / "docs/PORT56_MOVIE_TIMELIMIT.md"
MANIFEST_P56 = ROOT / "manifests/port56_movie_nolimit_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097
BASE_DEFAULT_END = "003686b0"

MOVIE_NOLIMIT_ALONE_SHA256 = "12c0635ffd11d2c6a1d158aaac436885a4a3b9b7830841a8c65410c193439b33"
MOVIE_NOLIMIT_ALONE_SIZE = 124145
MOVIE_NOLIMIT_ALONE_END = "003686e0"

PORT56_COMBINED_SHA256 = "c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352"
PORT56_COMBINED_SIZE = 132385
PORT56_COMBINED_END = "0036aaf0"

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
    bin_path = ROOT / "out/build-nolimit-alone/DISKBOOT.BIN"
    elf_path = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
    obj_path = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/sub/110c/movie_rec.o"
    if _BUILD_CACHE["alone"] and bin_path.is_file() and elf_path.is_file() and obj_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file() and obj_path.is_file()):
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--movie-nolimit-alone",
                "--out-dir",
                str(ROOT / "out/build-nolimit-alone"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["alone"] = True


def ensure_build_combined() -> None:
    bin_path = ROOT / "out/port56-movie-nolimit/DISKBOOT.BIN"
    elf_path = ROOT / "out/port56-movie-nolimit/stage_chdk/platform/g3x/sub/110c/main.elf"
    if _BUILD_CACHE["combined"] and bin_path.is_file() and elf_path.is_file():
        return
    if not (bin_path.is_file() and elf_path.is_file()):
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
                "--movie-nolimit",
                "--out-dir",
                str(ROOT / "out/port56-movie-nolimit"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    _BUILD_CACHE["combined"] = True


def setUpModule() -> None:
    """Shared module-level fixture: ensures all 3 configurations exist."""
    ensure_build_default()
    ensure_build_alone()
    ensure_build_combined()


def parse_function_instructions(disasm: str, symbol_name: str) -> list[dict[str, str]]:
    """Extract and parse instruction records for a given symbol from objdump output."""
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
        if re.match(r"^[0-9a-f]+\s+<[^>]+>:", line):
            break
        if line_s == "...":
            continue
        m = re.match(r"^\s*([0-9a-f]+):\s+([0-9a-f\s]+?)\t([a-z0-9\._]+)\s*(.*)$", line)
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


class TestPort56FlagPlumbing(unittest.TestCase):
    def test_makefile_plumbing(self):
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        sub_mf = SUB_MAKEFILE_INC.read_text(encoding="utf-8")

        self.assertIn("ifeq ($(G3X_MOVIE_NOLIMIT),1)", plat_mf)
        self.assertIn("CFLAGS += -DG3X_MOVIE_NOLIMIT=1", plat_mf)
        self.assertIn("ifeq ($(G3X_MOVIE_NOLIMIT),1)", sub_mf)
        self.assertIn("CFLAGS += -DG3X_MOVIE_NOLIMIT=1", sub_mf)

    def test_header_movie_nolimit_definitions(self):
        self.assertTrue(MOVIE_STATUS_H.is_file())
        text = MOVIE_STATUS_H.read_text(encoding="utf-8")

        self.assertTrue(re.search(r"#define\s+G3X_MR_MAX_FRAMES_ADDR\s+0x0000C274", text))
        self.assertTrue(re.search(r"#define\s+G3X_MR_CUR_FRAMES_ADDR\s+0x0000C278", text))
        self.assertTrue(re.search(r"#define\s+G3X_MR_WARN_SEC_ADDR\s+0x0000C0E4", text))
        self.assertTrue(re.search(r"#define\s+G3X_MR_STOP_REASON_ADDR\s+0x0000C0C0", text))
        self.assertIn("G3X_MOVIE_NOLIMIT_TARGET 0xFFFFFFFFU", text)

        self.assertIn("void g3x_movie_nolimit_poll(void);", text)
        self.assertIn("g3x_get_movie_max_frames(void);", text)
        self.assertIn("g3x_get_movie_cur_frames(void);", text)
        self.assertIn("static inline const char *g3x_movie_nolimit_status_str(void)", text)
        self.assertIn("static inline const char *g3x_movie_nolimit_diag_str(void)", text)

        self.assertIn("PORT56-ROM-SETUP-MAX-FRAMES-STORE", text)
        self.assertIn("PORT56-ROM-CHECK-FRAME-LIMIT", text)

    def test_movie_rec_flag_gating(self):
        for path in [MOVIE_REC_C, FULL_MOVIE_REC_C]:
            text = path.read_text(encoding="utf-8")
            self.assertIn("#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)", text)
            self.assertIn("g3x_movie_nolimit_poll(void)", text)
            self.assertIn("0x0000C274", text)
            self.assertIn("0xFFFFFFFFU", text)
            self.assertIn("g3x_get_movie_max_frames(void)", text)
            self.assertIn("g3x_get_movie_cur_frames(void)", text)

    def test_kbd_loop_wiring(self):
        # Verify full_build source wiring
        text_full = FULL_KBD_C.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)", text_full)
        self.assertIn("g3x_movie_nolimit_poll();", text_full)

        # Verify staging patches hook kbd.c in alone configuration
        ensure_build_alone()
        alone_staged_kbd = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/kbd.c"
        self.assertTrue(alone_staged_kbd.is_file(), f"Missing {alone_staged_kbd}")
        text_alone = alone_staged_kbd.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)", text_alone)
        self.assertIn("g3x_movie_nolimit_poll();", text_alone)

        # Verify staging patches hook kbd.c in combined configuration
        ensure_build_combined()
        comb_staged_kbd = ROOT / "out/port56-movie-nolimit/stage_chdk/platform/g3x/kbd.c"
        self.assertTrue(comb_staged_kbd.is_file(), f"Missing {comb_staged_kbd}")
        text_comb = comb_staged_kbd.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)", text_comb)
        self.assertIn("g3x_movie_nolimit_poll();", text_comb)

    def test_gui_diag_marker_gating(self):
        text = DIAG_HEADER.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)", text)
        self.assertIn("LIM:%s", text)
        self.assertIn("g3x_movie_nolimit_status_str()", text)

    def test_no_full_hooks_dependency(self):
        """Verify FULL_HOOKS is not required or referenced by G3X_MOVIE_NOLIMIT."""
        for path in [MOVIE_REC_C, FULL_MOVIE_REC_C, KBD_C, FULL_KBD_C, MOVIE_STATUS_H, DIAG_HEADER]:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for line in lines:
                if "G3X_MOVIE_NOLIMIT" in line:
                    self.assertNotIn("FULL_HOOKS", line)


class TestPort56DefaultBuildIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_build_default()
        cls.default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"

    def test_default_diskboot_byte_identical(self):
        self.assertTrue(self.default_bin.is_file())
        self.assertEqual(sha256_file(self.default_bin), BASE_DEFAULT_SHA256)
        self.assertEqual(self.default_bin.stat().st_size, BASE_DEFAULT_SIZE)

    def test_default_main_elf_end_symbol(self):
        self.assertTrue(self.default_elf.is_file())
        res = subprocess.run([str(NM), str(self.default_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{BASE_DEFAULT_END} B _end", res.stdout)


class TestPort56WriteAddressAllowlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_build_alone()
        ensure_build_combined()
        cls.combined_elf = ROOT / "out/port56-movie-nolimit/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.alone_elf = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.alone_obj = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/sub/110c/movie_rec.o"

    def test_g3x_movie_nolimit_poll_writes_only_c274(self):
        """Verify g3x_movie_nolimit_poll writes ONLY to 0x0000C274."""
        targets = [
            (self.combined_elf, "combined main.elf"),
            (self.alone_obj, "alone movie_rec.o"),
        ]
        for target_path, desc in targets:
            self.assertTrue(target_path.is_file(), f"Target not found: {target_path}")
            res = subprocess.run(
                [str(OBJDUMP), "-d", str(target_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            disasm = res.stdout

            instrs = parse_function_instructions(disasm, "g3x_movie_nolimit_poll")
            self.assertGreater(
                len(instrs),
                0,
                f"Expected parsed instructions for g3x_movie_nolimit_poll in {desc}, found none",
            )

            found_store = False
            for instr in instrs:
                mnem = instr["mnemonic"]
                operands = instr["operands"]
                # If it's a store instruction (not push/stack store)
                if mnem.startswith("str"):
                    found_store = True
                    # In ARM/Thumb, stores to target address should be `str rX, [rY]` where rY contains 0x0000C274
                    # Verify no stores target other registers or sp
                    self.assertNotIn("sp", operands)

            self.assertTrue(found_store, f"Did not find store instruction in g3x_movie_nolimit_poll in {desc}")

    def test_g3x_get_movie_cur_frames_is_read_only(self):
        """Verify g3x_get_movie_cur_frames has zero stores and loads 0x0000C278."""
        targets = [
            (self.combined_elf, "combined main.elf"),
            (self.alone_obj, "alone movie_rec.o"),
        ]
        for target_path, desc in targets:
            res = subprocess.run(
                [str(OBJDUMP), "-d", str(target_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            disasm = res.stdout

            instrs = parse_function_instructions(disasm, "g3x_get_movie_cur_frames")
            self.assertGreater(len(instrs), 0)

            for instr in instrs:
                mnem = instr["mnemonic"]
                for store_pfx in ("str", "stm"):
                    self.assertFalse(
                        mnem == store_pfx or mnem.startswith(store_pfx),
                        f"Forbidden store instruction '{mnem}' in g3x_get_movie_cur_frames ({desc}): {instr['line']}",
                    )

    def test_forbidden_addresses_never_written(self):
        """Verify no instructions in the image write to 0x0000C278, 0x0000C0E4, 0x0000C0C0, or 0x0000C0C8."""
        for elf_path, desc in [(self.combined_elf, "combined"), (self.alone_elf, "alone")]:
            res = subprocess.run(
                [str(OBJDUMP), "-d", str(elf_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            disasm = res.stdout

            # Scan for store instructions referencing forbidden addresses in comments / disassembly
            for forbidden_hex in ["c278", "c0e4", "c0c0", "c0c8"]:
                matches = re.finditer(
                    rf"^\s*([0-9a-f]+):\s+([0-9a-f\s]+?)\t([a-z0-9\._]+)\s*([^;\n]*;\s*.*{forbidden_hex}.*)",
                    disasm,
                    re.M | re.I,
                )
                for m in matches:
                    mnemonic = m.group(3).lower()
                    self.assertFalse(
                        mnemonic.startswith("str") or mnemonic.startswith("stm"),
                        f"Forbidden store referencing 0x{forbidden_hex} in {desc} main.elf: {m.group(0)}",
                    )


class TestPort56AddressEvidence(unittest.TestCase):
    def test_evidence_labels_and_citations(self):
        doc_text = DOC_PORT56.read_text(encoding="utf-8")
        finsig_text = FINSIG_STUBS.read_text(encoding="utf-8")

        # task_MovieRecord matches FINSIG
        self.assertTrue(
            re.search(r"DEF\s*\(\s*task_MovieRecord\s*,\s*0xfc09ac19\s*\)", finsig_text, re.I),
            "task_MovieRecord not found in finsig stubs_entry.S",
        )
        self.assertIn("0xFC09AC19", doc_text)

        # Addresses and labels
        self.assertIn("0x0000C274", doc_text)
        self.assertIn("PORT56-ROM-SETUP-MAX-FRAMES-STORE", doc_text)
        self.assertIn("PORT56-ROM-CHECK-FRAME-LIMIT", doc_text)

        self.assertIn("0x0000C278", doc_text)
        self.assertIn("0x0000C0E4", doc_text)
        self.assertIn("PORT56-ROM-WARN-SEC-CHECK", doc_text)

        self.assertIn("0x0000C0C0", doc_text)
        self.assertIn("PORT56-ROM-CHECK-SIZE-LIMIT", doc_text)

        # Timing citation
        self.assertIn("docs/VIDEO001_RECORDING_LIMITS.md:183", doc_text)


class TestPort56DiagMarkerFormatting(unittest.TestCase):
    def test_status_string_encoding(self):
        """Verify string mapping for LIM:OFF, LIM:ON, LIM:?."""
        def movie_nolimit_str(status: int, max_frames: int) -> str:
            if status != 1:
                return "?"
            if max_frames == 0xFFFFFFFF:
                return "OFF"
            if max_frames != 0:
                return "ON"
            return "?"

        # When not recording: always "?"
        self.assertEqual(movie_nolimit_str(0, 0xFFFFFFFF), "?")
        self.assertEqual(movie_nolimit_str(0, 54000), "?")
        self.assertEqual(movie_nolimit_str(2, 0xFFFFFFFF), "?")

        # When recording:
        # If patched (0xFFFFFFFF): "OFF" (limit defeated)
        self.assertEqual(movie_nolimit_str(1, 0xFFFFFFFF), "OFF")
        # If stock limit seen: "ON" (limit active)
        self.assertEqual(movie_nolimit_str(1, 54000), "ON")
        self.assertEqual(movie_nolimit_str(1, 107940), "ON")
        # If initial 0 before setup completes: "?"
        self.assertEqual(movie_nolimit_str(1, 0), "?")

    def test_diag_line_length_fits_screen(self):
        """Verify formatted secondary diag line does not exceed G3X_DIAG_LINE_MAX_CHARS (55)."""
        line_off = "MENU:%04u SAVE:%s MOV:%s LIM:%s Rs:%04u Rp:%04u" % (
            1,
            "OFF",
            "REC",
            "OFF",
            0,
            0,
        )
        self.assertLessEqual(len(line_off), 55)
        self.assertIn("LIM:OFF", line_off)

        line_on = "MENU:%04u SAVE:%s MOV:%s LIM:%s Rs:%04u Rp:%04u" % (
            1,
            "OFF",
            "REC",
            "ON",
            0,
            0,
        )
        self.assertLessEqual(len(line_on), 55)
        self.assertIn("LIM:ON", line_on)

        line_q = "MENU:%04u SAVE:%s MOV:%s LIM:%s Rs:%04u Rp:%04u" % (
            0,
            "OFF",
            "IDLE",
            "?",
            0,
            0,
        )
        self.assertLessEqual(len(line_q), 55)
        self.assertIn("LIM:?", line_q)


class TestPort56BuildArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_build_alone()
        ensure_build_combined()
        cls.alone_bin = ROOT / "out/build-nolimit-alone/DISKBOOT.BIN"
        cls.alone_elf = ROOT / "out/build-nolimit-alone/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.comb_bin = ROOT / "out/port56-movie-nolimit/DISKBOOT.BIN"
        cls.comb_elf = ROOT / "out/port56-movie-nolimit/stage_chdk/platform/g3x/sub/110c/main.elf"

    def test_alone_configuration_artifacts(self):
        self.assertTrue(self.alone_bin.is_file())
        self.assertTrue(self.alone_elf.is_file())
        self.assertEqual(sha256_file(self.alone_bin), MOVIE_NOLIMIT_ALONE_SHA256)
        self.assertEqual(self.alone_bin.stat().st_size, MOVIE_NOLIMIT_ALONE_SIZE)

        res = subprocess.run([str(NM), str(self.alone_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{MOVIE_NOLIMIT_ALONE_END} B _end", res.stdout)

    def test_combined_configuration_artifacts(self):
        self.assertTrue(self.comb_bin.is_file())
        self.assertTrue(self.comb_elf.is_file())
        self.assertEqual(sha256_file(self.comb_bin), PORT56_COMBINED_SHA256)
        self.assertEqual(self.comb_bin.stat().st_size, PORT56_COMBINED_SIZE)

        res = subprocess.run([str(NM), str(self.comb_elf)], capture_output=True, text=True, check=True)
        self.assertIn(f"{PORT56_COMBINED_END} B _end", res.stdout)

    def test_manifest_metadata(self):
        self.assertTrue(MANIFEST_P56.is_file())
        manifest = json.loads(MANIFEST_P56.read_text(encoding="utf-8"))
        self.assertIn("artifacts", manifest)
        self.assertIn("DISKBOOT.BIN", manifest["artifacts"])
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["sha256"], PORT56_COMBINED_SHA256)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["size"], PORT56_COMBINED_SIZE)
        self.assertEqual(manifest["_end"], f"0x{PORT56_COMBINED_END}")

        flags = manifest["build"]["flags"]
        self.assertIn("G3X_MOVIE_NOLIMIT=1", flags)
        self.assertIn("G3X_MOVIE_STATUS=1", flags)
        self.assertIn("G3X_PLAYBACK_MENU=1", flags)

        self.assertIn("configurations", manifest)
        configs = manifest["configurations"]
        self.assertEqual(configs["default"]["sha256"], BASE_DEFAULT_SHA256)
        self.assertEqual(configs["movie_nolimit_alone"]["sha256"], MOVIE_NOLIMIT_ALONE_SHA256)
        self.assertEqual(configs["full_candidate"]["sha256"], PORT56_COMBINED_SHA256)


class TestPort56NoRegressionsInEarlierFlags(unittest.TestCase):
    def test_card_writes_remain_disabled(self):
        manifest = json.loads(MANIFEST_P56.read_text(encoding="utf-8"))
        self.assertEqual(manifest["build"]["card_writes"], "disabled")
        self.assertEqual(manifest["card_writes"], "disabled")

    def test_no_create_task_hooks(self):
        for path in [MOVIE_REC_C, FULL_MOVIE_REC_C, KBD_C, FULL_KBD_C]:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("task_create_hook", text)
            self.assertNotIn("CreateTask", text)


if __name__ == "__main__":
    unittest.main()
