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
        """Verify table header contains required columns and basic document structure."""
        self.assertTrue(any(line.startswith("# ") and "PORT-39" in line for line in self.lines), "Doc title missing")
        header_rows = [line for line in self.lines if "|" in line and "sibling path:line" in line.lower()]
        self.assertTrue(len(header_rows) > 0, "Doc must contain a table header row with 'Sibling path:line'")
        header = header_rows[0].lower()
        self.assertIn("sibling path:line", header)
        self.assertIn("gm1.10c", header)
        self.assertIn("label", header)

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
        """Verify all required short-press power-on mechanisms are covered via short keyword checks."""
        table_rows = [line.lower() for line in self.lines if line.startswith("| **")]
        table_text = "\n".join(table_rows)

        self.assertIn("physw", table_text, "Missing physw bit / GPIO read coverage")
        self.assertTrue(
            "still held" in table_text or "physw_status" in table_text,
            "Missing fake button still held / physw_status override coverage",
        )
        self.assertIn("start", table_text, "Missing start-mode / startup flag coverage")
        self.assertTrue(
            "physw" in table_text or "taskcreate" in table_text,
            "Missing task_PhySw / taskcreate_physw override coverage",
        )
        self.assertIn("playback", table_text, "Missing Playback vs Power start distinction coverage")
        self.assertTrue(
            "power-cut" in table_text or "shutdown" in table_text,
            "Missing shutdown/power-cut bypass coverage",
        )

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
            if line.startswith("| **g5x**") and ("power-cut" in line.lower() or "shutdown" in line.lower())
        ]
        self.assertTrue(len(g5x_bypass_rows) >= 1, "Missing g5x row mapping sub_fc0ecf20_my")
        row = g5x_bypass_rows[0]
        self.assertIn("sub_fc0ecf20_my", row, "Row must mention sub_fc0ecf20_my")
        self.assertIn("0xFC05B962", row, "Row must map sub_fc0ecf20_my to 0xFC05B962")
        cols = [c.strip() for c in row.split("|")[1:-1]]
        valid_labels = {"VERIFIED", "FINSIG", "INFERRED", "HISTORICAL_CHDK"}
        self.assertIn(cols[3], valid_labels, f"Mapped row label must be in allowed set: {cols[3]}")

    def test_verified_rom_rows_have_manifest_citations(self) -> None:
        """Verify that any row labelled VERIFIED with a ROM address cites manifest entries <= 4 KiB with SHA-256,
        and that each cited range matches an actual manifest entry.
        """
        table_rows = [line for line in self.lines if line.startswith("| **")]
        slice_pattern = re.compile(
            r"start\s+`?(0x[0-9A-Fa-f]+)`?[,\s]+len(?:gth)?\s+`?(\d+)`?(?:\s*B)?[,\s]+(?:SHA-256|sha256)\s+`?([0-9a-fA-F]{64})`?",
            re.IGNORECASE,
        )
        manifest_path_pattern = re.compile(r"`?([\w/.-]+\.json)`?")

        manifest_cache: dict[str, dict] = {}
        verified_rom_rows = 0

        for row in table_rows:
            cols = [c.strip() for c in row.split("|")[1:-1]]
            label = cols[3]
            equiv = cols[2]
            note = cols[4]

            # If row is marked VERIFIED and mentions a ROM address (0xFC... / 0xFD... / 0xBF...)
            if label == "VERIFIED" and re.search(r"0x(?:FC|FD|BF)[0-9A-Fa-f]{6}", equiv + note):
                verified_rom_rows += 1
                manifest_matches = manifest_path_pattern.findall(note)
                manifest_files = [m for m in manifest_matches if m.endswith(".json")]
                self.assertTrue(len(manifest_files) > 0, f"VERIFIED ROM row must cite manifest json: {row}")

                slices = slice_pattern.findall(note)
                self.assertTrue(len(slices) > 0, f"VERIFIED ROM row must cite manifest slice (start, len, SHA-256): {row}")

                for m_file in manifest_files:
                    if m_file not in manifest_cache:
                        m_path = PROJECT_ROOT / m_file
                        self.assertTrue(m_path.is_file(), f"Manifest file not found: {m_path}")
                        manifest_cache[m_file] = json.loads(m_path.read_text(encoding="utf-8"))

                # For every cited slice, verify it exists in at least one cited manifest
                for start_hex, length_str, sha in slices:
                    length_val = int(length_str)
                    self.assertLessEqual(length_val, 4096, f"ROM slice length exceeds 4 KiB in {row}")

                    match_found = False
                    for m_file in manifest_files:
                        entries = manifest_cache[m_file].get("evidence_entries", [])
                        for entry in entries:
                            entry_start = entry.get("start_address", "")
                            entry_len = entry.get("expected_byte_count") or entry.get("length") or entry.get("size")
                            entry_sha = entry.get("sha256", "")
                            if (
                                entry_start.upper() == start_hex.upper()
                                and entry_len == length_val
                                and entry_sha.lower() == sha.lower()
                            ):
                                match_found = True
                                break
                        if match_found:
                            break

                    self.assertTrue(
                        match_found,
                        f"Slice start={start_hex}, len={length_val}, sha={sha} from row '{cols[0]}' not found in manifests: {manifest_files}",
                    )

        self.assertGreaterEqual(verified_rom_rows, 5, "Expected multiple VERIFIED ROM rows to be validated")

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
