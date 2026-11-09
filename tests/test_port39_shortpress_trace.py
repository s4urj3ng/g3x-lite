#!/usr/bin/env python3
"""PORT-39: Verification suite for sibling DIGIC 6 short-press power-on trace.

Acceptance criteria verified:
1. docs/port39_shortpress_trace.md exists and contains the comparison table.
2. Each row maps sibling path:line -> GM1.10C value -> label (VERIFIED/FINSIG/INFERRED/HISTORICAL_CHDK).
3. g7x is covered first, followed by g5x, sx60hs, and g16.
4. Covered mechanisms include:
   - power-button or playback physw bit / GPIO read at startup
   - fake 'button still held' bit / physw_status override
   - start-mode or startup-flag write
   - task_PhySw / taskcreate_physw / kbd override with hold duration / condition
   - playback-button vs power-button start distinction
   - shutdown/power-cut bypass (g5x sub_fc0ecf20_my mapped to GM1.10C 0xFC05B962)
5. Every VERIFIED ROM-derived row references an approved manifest entry (start, length <= 4 KiB, SHA-256).
6. The physw_status address (0x00040DAC) and hold length (100 polls) cite their source.
7. The Power bit 17 / Playback bit 16 history in tracked G3X code is cited by path:line.
8. The Recommended Adaptation section is <= 10 lines and names a sibling.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = PROJECT_ROOT / "docs" / "port39_shortpress_trace.md"


class TestPort39ShortpressTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(DOC_PATH.is_file(), f"Missing required doc at {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_doc_structure_and_table_presence(self) -> None:
        """Verify markdown table headers and basic document structure."""
        self.assertIn("# PORT-39:", self.lines[0])
        self.assertIn(
            "| Item / Mechanism | Sibling path:line | GM1.10C Equivalent (address, bit, word index) | Label | Note / How it works |",
            self.content,
        )

    def test_sibling_coverage_order(self) -> None:
        """Verify g7x is covered first, followed by g5x, sx60hs, and g16."""
        pos_g7x = self.content.find("**g7x**")
        pos_g5x = self.content.find("**g5x**")
        pos_sx60hs = self.content.find("**sx60hs**")
        pos_g16 = self.content.find("**g16**")

        self.assertNotEqual(pos_g7x, -1, "g7x must be covered")
        self.assertNotEqual(pos_g5x, -1, "g5x must be covered")
        self.assertNotEqual(pos_sx60hs, -1, "sx60hs must be covered")
        self.assertNotEqual(pos_g16, -1, "g16 must be covered")

        self.assertTrue(
            pos_g7x < pos_g5x < pos_sx60hs < pos_g16,
            "Siblings must be covered in order: g7x first, then g5x, sx60hs, g16",
        )

    def test_required_mechanisms_covered(self) -> None:
        """Verify all six required short-press power-on mechanisms are covered."""
        required_items = [
            "Power & Playback physw bits read at startup",
            "Fake 'button still held' bit / physw_status override",
            "Start-mode or startup-flag write",
            "task_PhySw / taskcreate_physw override & hold duration",
            "Playback vs Power start distinction",
            "Shutdown/power-cut bypass",
        ]
        for item in required_items:
            self.assertIn(item, self.content, f"Missing required mechanism item: {item}")

    def test_evidence_labels_used(self) -> None:
        """Verify each row has a valid label from the approved set."""
        valid_labels = {"VERIFIED", "FINSIG", "INFERRED", "HISTORICAL_CHDK"}
        table_rows = [line for line in self.lines if line.startswith("| **")]
        self.assertGreaterEqual(len(table_rows), 20, "Expected at least 20 detailed comparison rows")

        for row in table_rows:
            cols = [c.strip() for c in row.split("|")[1:-1]]
            label = cols[3]
            self.assertIn(label, valid_labels, f"Invalid label '{label}' in row: {row}")

    def test_g5x_sub_fc0ecf20_my_mapping_and_consistency(self) -> None:
        """Verify explicit row mapping g5x sub_fc0ecf20_my to GM1.10C 0xFC05B962."""
        g5x_bypass_rows = [
            line for line in self.lines
            if line.startswith("| **g5x**: Shutdown/power-cut bypass")
        ]
        self.assertTrue(len(g5x_bypass_rows) >= 1, "Missing g5x row mapping sub_fc0ecf20_my")
        row = g5x_bypass_rows[0]
        self.assertIn("sub_fc0ecf20_my", row, "Row must mention sub_fc0ecf20_my")
        self.assertIn("0xFC05B962", row, "Row must map sub_fc0ecf20_my to 0xFC05B962")
        self.assertIn("VERIFIED", row, "Mapped row must be labelled VERIFIED")

    def test_verified_rom_rows_have_manifest_citations(self) -> None:
        """Verify that any row labelled VERIFIED with a ROM address cites manifest entries <= 4 KiB with SHA-256."""
        table_rows = [line for line in self.lines if line.startswith("| **")]
        sha256_pattern = re.compile(r"\b[0-9a-fA-F]{64}\b")

        for row in table_rows:
            cols = [c.strip() for c in row.split("|")[1:-1]]
            label = cols[3]
            equiv = cols[2]
            note = cols[4]

            # If row is marked VERIFIED and mentions a ROM address (0xFC... / 0xFD... / 0xBF...)
            if label == "VERIFIED" and re.search(r"0x(?:FC|FD|BF)[0-9A-Fa-f]{6}", equiv + note):
                # Must cite an evidence manifest and a SHA-256 hash
                self.assertIn(".json", note, f"VERIFIED ROM row must cite manifest json: {row}")
                shas = sha256_pattern.findall(note)
                self.assertTrue(len(shas) > 0, f"VERIFIED ROM row must cite SHA-256 hash: {row}")

                # Check lengths in note are <= 4096 / 4 KiB
                lens = re.findall(r"\b(?:len|length)\s+(\d+)\b", note)
                for l in lens:
                    self.assertLessEqual(int(l), 4096, f"ROM slice length exceeds 4 KiB limit in {row}")

    def test_physw_status_and_hold_duration_sources(self) -> None:
        """Verify physw_status 0x00040DAC address and hold duration (100 polls) cite their source."""
        self.assertIn("0x00040DAC", self.content)
        self.assertIn("stubs_entry.S:173", self.content)
        self.assertIn("100", self.content)
        self.assertIn("kbd_candidate.h:26", self.content)

    def test_tracked_g3x_power_and_playback_bit_history_citations(self) -> None:
        """Verify Power bit 17 / Playback bit 16 history is cited with exact path:line."""
        # Check platform_kbd.h citation
        self.assertRegex(self.content, r"chdk-port/platform/g3x/platform_kbd\.h:\d+(?:-\d+)?")
        # Check kbd_candidate.h citation
        self.assertRegex(self.content, r"chdk-port/platform/g3x/sub/110c/kbd_candidate\.h:\d+(?:-\d+)?")
        # Check PORT-7B documentation citation
        self.assertIn("PORT7B_PLAYBACK_MASK_CORRECTION.md", self.content)
        # Check mask values
        self.assertIn("0x000433F9", self.content)
        self.assertIn("0x000533F9", self.content)
        self.assertIn("0x00010000", self.content)  # Playback bit 16
        self.assertIn("0x00020000", self.content)  # Power bit 17

    def test_recommended_adaptation_section_length_and_content(self) -> None:
        """Verify recommended adaptation section is <= 10 lines and specifies closest sibling."""
        section_start = None
        for i, line in enumerate(self.lines):
            if line.strip() == "## Recommended Adaptation":
                section_start = i
                break
        self.assertIsNotNone(section_start, "Missing '## Recommended Adaptation' section")

        section_lines = self.lines[section_start:]
        self.assertLessEqual(
            len(section_lines),
            10,
            f"Recommended adaptation must be <= 10 lines (found {len(section_lines)})",
        )

        section_text = "\n".join(section_lines)
        self.assertTrue(
            "G5 X" in section_text or "g5x" in section_text,
            "Recommended adaptation must name closest sibling (G5 X)",
        )
        self.assertIn("0x9BC4", section_text, "Recommended adaptation must mention start cause structure (0x9BC4)")
        self.assertIn("0xFC05B962", section_text, "Recommended adaptation must mention early boot caller (0xFC05B962)")
        self.assertIn("physw_status", section_text, "Recommended adaptation must mention physw_status")


if __name__ == "__main__":
    unittest.main()
