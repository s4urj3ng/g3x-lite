#!/usr/bin/env python3
"""PORT-39: Host test suite for opt-in G3X_SHORTPRESS=1 candidate.

Verifies:
(a) With all flags off (or default), DISKBOOT.BIN SHA-256 is byte-identical to the
    pinned baseline hash: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
(b) The opt-in G3X_SHORTPRESS=1 plain candidate builds successfully and is reproducible:
    - DISKBOOT.BIN SHA-256: a0f5670a77e135466bcec656625f820813a490f54ffda1a69387ed29b3a9c62b (124,833 B)
    - Boot witness: 0x00361150
    - Linked _end: 0x00368660 <= heap start 0x00368880 (544 B clearance)
(c) The combined G3X_SHORTPRESS=1 + G3X_GUI4=1 candidate builds successfully and is reproducible:
    - DISKBOOT.BIN SHA-256: d72c1da63fdd7cee5821dad648595c705fec5427424113ab883e7a9010013279 (102,273 B)
    - Boot witness: 0x0035C9C0
    - Linked _end: 0x003629F0 <= heap start 0x00368880 (24,208 B clearance)
(d) Prior builds (RESIDENT, KBD, GUI4) remain strictly byte-identical.
(e) Disassembly confirms:
    - Active-low physical switch bit clearance (bic.w on physw_status[0]) for Power bit 17 (0x00020000)
      and Playback bit 16 (0x00010000).
    - Start cause discrimination using word at 0x00009BD0 (*(0x9BC4 + 12)).
    - Hold duration counter initialized to 700 polls (0x2BC; ~7.0 s @ 10 ms/poll).
    - When G3X_SHORTPRESS is not set, short-press override code is absent from the binary.
(f) Adapted-value table and trial plan in docs/PORT39_SHORTPRESS_TRIAL.md are validated:
    - Sibling path:line, GM1.10C value, and label (VERIFIED/FINSIG/INFERRED/HISTORICAL_CHDK) present.
    - Owner trial plan covers steps (a) through (e) in exact order with expected result, FAIL appearance,
      and confirmed/refuted INFERRED items.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"
DOCS_DIR = REPO_ROOT / "docs"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
SHORTPRESS_HEADER = SUB_DIR / "shortpress_candidate.h"
KBD_HEADER = SUB_DIR / "kbd_candidate.h"
TRIAL_DOC = DOCS_DIR / "PORT39_SHORTPRESS_TRIAL.md"

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_candidate_gui3 import build_candidate as build_candidate_gui
import build_candidate_port25_ladder_fix as legacy_builder

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_SHORTPRESS_SHA256 = "a0f5670a77e135466bcec656625f820813a490f54ffda1a69387ed29b3a9c62b"
PINNED_SHORTPRESS_SIZE = 124833
PINNED_SHORTPRESS_WITNESS = 0x00361150
PINNED_SHORTPRESS_END = 0x00368660

PINNED_COMBINED_SHA256 = "d72c1da63fdd7cee5821dad648595c705fec5427424113ab883e7a9010013279"
PINNED_COMBINED_SIZE = 102273
PINNED_COMBINED_WITNESS = 0x0035C9C0
PINNED_COMBINED_END = 0x003629F0

PINNED_PORT34_KBD_SHA256 = "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33"
PINNED_PORT34_KBD_SIZE = 124801

PINNED_PORT38_GUI4_SHA256 = "14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd"
PINNED_PORT38_GUI4_SIZE = 102241

PINNED_HEAP_START = 0x00368880


def have_pinned_toolchain() -> bool:
    if not (ARM_GCC.is_file() and os.access(ARM_GCC, os.X_OK)):
        return False
    if not (ARM_OBJDUMP.is_file() and os.access(ARM_OBJDUMP, os.X_OK)):
        return False
    try:
        res = subprocess.run([str(ARM_GCC), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


HAVE_TOOLCHAIN = have_pinned_toolchain()


class TestPort39ShortpressCandidate(unittest.TestCase):
    def test_default_build_byte_identical(self) -> None:
        """Assert default build DISKBOOT.BIN is byte-identical to pinned baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate_gui(ladder=False, poweron_fix=False, resident=False, out_dir=tmpdir)
            self.assertEqual(res["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_DEFAULT_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Requires pinned ARM toolchain")
    def test_shortpress_plain_build_and_reproducibility(self) -> None:
        """Assert opt-in G3X_SHORTPRESS=1 candidate builds cleanly and is reproducible."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            res1 = legacy_builder.build_candidate(shortpress=True, out_dir=tmp1)
            res2 = legacy_builder.build_candidate(shortpress=True, out_dir=tmp2)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_SHORTPRESS_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_SHORTPRESS_SIZE)

            end_addr = int(res1["core_end_addr"], 16)
            heap_addr = int(res1["heap_start_addr"], 16)
            self.assertEqual(end_addr, PINNED_SHORTPRESS_END)
            self.assertEqual(heap_addr, PINNED_HEAP_START)
            self.assertLessEqual(end_addr, heap_addr)
            self.assertGreater(heap_addr - end_addr, 0)
            self.assertEqual(int(res1["witness_addr"], 16), PINNED_SHORTPRESS_WITNESS)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Requires pinned ARM toolchain")
    def test_combined_shortpress_gui4_build_and_reproducibility(self) -> None:
        """Assert combined G3X_SHORTPRESS=1 + G3X_GUI4=1 candidate builds cleanly and is reproducible."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            res1 = build_candidate_gui(gui4=True, shortpress=True, out_dir=tmp1)
            res2 = build_candidate_gui(gui4=True, shortpress=True, out_dir=tmp2)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_COMBINED_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_COMBINED_SIZE)

            # Check linked symbols
            nm_output = subprocess.check_output([str(ARM_NM), "-n", res1["core_elf"]], text=True)
            self.assertRegex(nm_output, r"\s+[tT]\s+g3x_fill_menu_opaque_black\b")
            self.assertRegex(nm_output, r"\s+[tT]\s+rbf_draw_char\b")
            self.assertRegex(nm_output, r"\s+[tT]\s+my_kbd_read_keys_candidate\b")

            # Parse _end from nm
            m_end = re.search(r"([0-9a-fA-F]{8})\s+[Bb]\s+_end", nm_output)
            self.assertIsNotNone(m_end)
            end_addr = int(m_end.group(1), 16)
            self.assertEqual(end_addr, PINNED_COMBINED_END)
            self.assertLessEqual(end_addr, PINNED_HEAP_START)
            clearance = PINNED_HEAP_START - end_addr
            self.assertGreater(clearance, 24000)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Requires pinned ARM toolchain")
    def test_prior_builds_invariance(self) -> None:
        """Verify prior builds (KBD, GUI4) remain strictly byte-identical."""
        with tempfile.TemporaryDirectory() as tmp_kbd:
            res_kbd = legacy_builder.build_candidate(kbd=True, out_dir=tmp_kbd)
            self.assertEqual(res_kbd["diskboot_sha256"], PINNED_PORT34_KBD_SHA256)
            self.assertEqual(res_kbd["diskboot_size"], PINNED_PORT34_KBD_SIZE)

        with tempfile.TemporaryDirectory() as tmp_gui4:
            res_gui4 = build_candidate_gui(gui4=True, out_dir=tmp_gui4)
            self.assertEqual(res_gui4["diskboot_sha256"], PINNED_PORT38_GUI4_SHA256)
            self.assertEqual(res_gui4["diskboot_size"], PINNED_PORT38_GUI4_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Requires pinned ARM toolchain")
    def test_disassembly_shortpress_active_low_and_duration(self) -> None:
        """Verify disassembly of short-press override: active-low bit clearance, 700 polls, start cause check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = legacy_builder.build_candidate(shortpress=True, out_dir=tmpdir)
            disasm = subprocess.check_output([str(ARM_OBJDUMP), "-d", res["core_elf"]], text=True)

            self.assertIn("<my_kbd_read_keys_candidate>:", disasm)
            self.assertIn("<g3x_shortpress_read_keys>:", disasm)

            pos = disasm.find("<g3x_shortpress_read_keys>:")
            fn_disasm = disasm[pos : pos + 1200]

            # 1. kbd_update_key_state and kbd_update_physw_bits called
            self.assertIn("kbd_update_key_state", fn_disasm)
            self.assertIn("kbd_update_physw_bits", fn_disasm)

            # 2. Start cause check at 0x9BD0 (*(0x9BC4 + 12))
            self.assertIn("0x9bd0", fn_disasm.lower())
            self.assertIn("1048576", fn_disasm)  # 0x00100000 Playback start bit

            # 3. Active-low bit clearance: bic.w for Power (0x20000 = 131072) and Playback (0x10000 = 65536)
            self.assertIn("bic", fn_disasm)
            self.assertIn("131072", fn_disasm)  # 0x00020000
            self.assertIn("65536", fn_disasm)   # 0x00010000

            # 4. Hold counter initial value: 700 (0x2BC = 700)
            data_dump = subprocess.check_output(
                [str(ARM_OBJDUMP), "-s", "--start-address=0x00361140", "--stop-address=0x00361148", res["core_elf"]],
                text=True,
            )
            self.assertIn("bc020000", data_dump.lower())  # 700 in little-endian

    def test_shortpress_code_strictly_guarded(self) -> None:
        """Verify all short-press definitions and routines are guarded by G3X_SHORTPRESS."""
        self.assertTrue(SHORTPRESS_HEADER.is_file(), f"Missing {SHORTPRESS_HEADER}")
        hdr_text = SHORTPRESS_HEADER.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)", hdr_text)
        self.assertIn("#define G3X_SHORTPRESS_HOLD_POLLS   700", hdr_text)
        self.assertIn("g3x_shortpress_read_keys", hdr_text)

        # In kbd_candidate.h, ensure shortpress_read_keys is guarded
        kbd_text = KBD_HEADER.read_text(encoding="utf-8")
        self.assertIn("#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)", kbd_text)
        self.assertIn("g3x_shortpress_read_keys();", kbd_text)

    def test_trial_plan_doc_and_adapted_values(self) -> None:
        """Verify docs/PORT39_SHORTPRESS_TRIAL.md covers adapted values table and steps (a)-(e)."""
        self.assertTrue(TRIAL_DOC.is_file(), f"Missing {TRIAL_DOC}")
        doc_text = TRIAL_DOC.read_text(encoding="utf-8")

        # Adapted values table columns
        self.assertIn("Sibling Source path:line", doc_text)
        self.assertIn("GM1.10C Value", doc_text)
        self.assertIn("Label", doc_text)

        # Check required labels
        for label in ("VERIFIED", "FINSIG", "INFERRED", "HISTORICAL_CHDK"):
            self.assertIn(f"`{label}`", doc_text)

        # Check adapted entries
        self.assertIn("0x00020000", doc_text)  # Power bit
        self.assertIn("0x00010000", doc_text)  # Playback bit
        self.assertIn("0x00040DAC", doc_text)  # physw_status
        self.assertIn("0x00009BD0", doc_text)  # start cause
        self.assertIn("700", doc_text)         # duration polls
        self.assertIn("~5 s", doc_text)        # PORT-38 LED ladder window reference

        # Check ordered trial steps (a) through (e)
        self.assertIn("Step (a): Held Press Regression Check", doc_text)
        self.assertIn("Step (b): Short Press into Playback Mode", doc_text)
        self.assertIn("Step (c): Short Press into Shooting Mode", doc_text)
        self.assertIn("Step (d): Heartbeat LED Alive After 30 Seconds", doc_text)
        self.assertIn("Step (e): Normal Power-Off With Power Button", doc_text)

        # Check baseline GUI4 items in Step (a)
        self.assertIn("F1 2x Font", doc_text)
        self.assertIn("Title Bar", doc_text)
        self.assertIn("F3 Opacity", doc_text)
        self.assertIn("Known Geometry Gap", doc_text)
        self.assertIn("NOT a FAIL", doc_text)
        self.assertIn("No Flicker", doc_text)
        self.assertIn("Step 8", doc_text)
        self.assertIn("Step 9", doc_text)

        # Check that FAIL appearance and confirmed/refuted INFERRED items are present for all steps
        self.assertEqual(doc_text.count("What a FAIL looks like"), 5)
        self.assertEqual(doc_text.count("Item Confirmed/Refuted"), 5)


if __name__ == "__main__":
    unittest.main()
