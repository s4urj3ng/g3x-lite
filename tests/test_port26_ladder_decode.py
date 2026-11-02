#!/usr/bin/env python3
"""PORT-26 T1: Comprehensive Test Suite for LED-Code Ladder Decoder Tool.

Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p26-t1-ladder-decode

Coverage Requirements:
1. Every table code in LADDER_STAGE_TABLE (29 codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44).
2. 'none' / zero pulses -> NO_PULSES.
3. Out-of-table counts -> UNKNOWN_CODE.
4. Off-by-one ambiguity (conflicting multiple counts, count adjacent to two valid codes with uncertainty).
5. Wrong candidate hash -> INVALID_CANDIDATE.
6. Held-press control reaching stock UI -> CONTROL_HELD_O1.
7. Refusal of forbidden paths (.bin, .rom, PRIMARY*).
8. Both input formats (JSON and key=value text) producing byte-identical outputs.
9. Table-equals-source consistency test verifying runtime parsing matches in-tool table.
10. Deterministic byte-identical JSON outputs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "port26_ladder_decode.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.port26_ladder_decode as decoder
from tools.port26_ladder_decode import (
    EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    LADDER_STAGE_TABLE,
    NEXT_STAGE_MAP,
    VALID_CLASSES,
    SafetyViolationError,
    classify_owner_report,
    decode_ladder_report,
    is_count_adjacent_to_two_valid_codes,
    parse_expected_diskboot_sha256,
    parse_ladder_table_from_source,
    parse_owner_report,
    validate_safety_path,
)


class TestPort26LadderDecode(unittest.TestCase):
    """Test suite for PORT-26 ladder decoder tool and owner report classification."""

    def setUp(self) -> None:
        self.valid_hash = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256

    def test_table_equals_source_consistency(self) -> None:
        """Asserts that in-tool LADDER_STAGE_TABLE equals the runtime-parsed source table."""
        doc_path = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"
        self.assertTrue(doc_path.is_file(), f"Missing candidate doc: {doc_path}")

        parsed_table = parse_ladder_table_from_source(doc_path)
        self.assertEqual(
            set(parsed_table.keys()),
            set(LADDER_STAGE_TABLE.keys()),
            "Mismatch in registered code sets between source and in-tool table",
        )

        for code, expected_entry in LADDER_STAGE_TABLE.items():
            parsed_entry = parsed_table[code]
            self.assertEqual(
                parsed_entry["code"],
                expected_entry["code"],
                f"Code mismatch for {code}",
            )
            self.assertEqual(
                parsed_entry["stage_symbol"],
                expected_entry["stage_symbol"],
                f"Stage symbol mismatch for code {code}",
            )
            self.assertEqual(
                parsed_entry["context"],
                expected_entry["context"],
                f"Context mismatch for code {code}",
            )
            self.assertEqual(
                parsed_entry["file_line"],
                expected_entry["file_line"],
                f"File/line mismatch for code {code}",
            )

        # Assert parsed SHA-256 equals expected constant
        parsed_sha256 = parse_expected_diskboot_sha256(doc_path)
        self.assertEqual(
            parsed_sha256,
            EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
            "Parsed candidate SHA-256 does not match pinned constant",
        )

    def test_every_table_code(self) -> None:
        """Covers every single registered code in the table across loader and core stages."""
        self.assertEqual(len(LADDER_STAGE_TABLE), 29, "Expected exactly 29 registered codes")

        for code, entry in LADDER_STAGE_TABLE.items():
            with self.subTest(code=code, stage=entry["stage_symbol"]):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": code,
                    "lcd": "dark",
                    "inspector_status": "none",
                }
                res = classify_owner_report(report)

                self.assertEqual(res["class"], f"CODE_{code}")
                self.assertEqual(res["last_stage_reached"], entry["stage_symbol"])
                self.assertEqual(res["next_stage"], NEXT_STAGE_MAP[code])
                self.assertIn("docs/PORT25_LADDER_FIX_CANDIDATE.md", res["evidence"])
                self.assertTrue(len(res["notes"]) > 0)
                self.assertIn(res["class"], VALID_CLASSES)

    def test_none_pulses(self) -> None:
        """Covers 'none' pulse variations mapping to NO_PULSES."""
        none_variations = ["none", "NONE", "null", "", 0, "0", []]
        for val in none_variations:
            with self.subTest(pulses=val):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": val,
                    "lcd": "dark",
                    "inspector_status": "none",
                }
                res = classify_owner_report(report)
                self.assertEqual(res["class"], "NO_PULSES")
                self.assertIsNone(res["last_stage_reached"])
                self.assertEqual(res["next_stage"], "STAGE_LOADER_AFTER_PROLOGUE")
                self.assertIn("Zero pulses", res["notes"])
                self.assertIn("docs/PORT25_OWNER_TRIAL_PLAN.md:201", res["evidence"])

    def test_out_of_table_counts(self) -> None:
        """Covers pulse counts that are not in the table mapping to UNKNOWN_CODE."""
        out_of_table = [8, 9, 10, 16, 17, 18, 19, 20, 30, 36, 37, 40, 45, 50, 99]
        for count in out_of_table:
            with self.subTest(count=count):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": count,
                    "lcd": "dark",
                    "inspector_status": "none",
                }
                res = classify_owner_report(report)
                self.assertEqual(res["class"], "UNKNOWN_CODE")
                self.assertIsNone(res["last_stage_reached"])
                self.assertIsNone(res["next_stage"])
                self.assertIn(f"Pulse count {count} does not match", res["notes"])

    def test_off_by_one_ambiguity_conflicting_multiple(self) -> None:
        """Covers AMBIGUOUS classification when conflicting multiple counts are reported."""
        conflicting_lists = [
            [21, 24],
            [1, 2],
            [24, 25],
            [11, 12, 13],
            [31, 35],
        ]
        for counts in conflicting_lists:
            with self.subTest(counts=counts):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": counts,
                    "lcd": "dark",
                    "inspector_status": "none",
                }
                res = classify_owner_report(report)
                self.assertEqual(res["class"], "AMBIGUOUS")
                self.assertIsNone(res["last_stage_reached"])
                self.assertIsNone(res["next_stage"])
                self.assertIn("Conflicting multiple pulse counts", res["notes"])

        # Identical counts in a list should NOT be ambiguous
        single_in_list = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": [24, 24],
            "lcd": "dark",
            "inspector_status": "none",
        }
        res_single = classify_owner_report(single_in_list)
        self.assertEqual(res_single["class"], "CODE_24")

    def test_off_by_one_ambiguity_uncertainty_rule(self) -> None:
        """Covers the explicit off-by-one uncertainty rule:
        Triggers AMBIGUOUS when owner flags uncertainty AND count is adjacent to two valid codes.
        """
        # Count 23 has 22 and 24 in table -> adjacent to two valid codes
        self.assertTrue(is_count_adjacent_to_two_valid_codes(23))
        # Count 24 has 23 and 25 in table -> adjacent to two valid codes
        self.assertTrue(is_count_adjacent_to_two_valid_codes(24))
        # Count 27 (out-of-table) has 26 and 28 in table -> adjacent to two valid codes
        self.assertTrue(is_count_adjacent_to_two_valid_codes(27))
        # Count 11 has 10 (not in table) and 12 (in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(11))
        # Count 7 has 6 (in table) and 8 (not in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(7))
        # Count 1 has 0 (not in table) and 2 (in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(1))
        # Count 44 has 43 (in table) and 45 (not in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(44))

        # 1. Count 23 with uncertainty flagged -> AMBIGUOUS
        res1 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 23,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res1["class"], "AMBIGUOUS")
        self.assertIsNone(res1["last_stage_reached"])
        self.assertIn("off-by-one uncertainty rule", res1["notes"])

        # 2. Count 24 with uncertainty in notes -> AMBIGUOUS
        res2 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 24,
            "notes": "uncertain if 23, 24, or 25",
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res2["class"], "AMBIGUOUS")

        # 3. Out-of-table Count 27 with uncertainty -> AMBIGUOUS (adjacent to 26 and 28)
        res3 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 27,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res3["class"], "AMBIGUOUS")

        # 4. Count 23 WITHOUT uncertainty -> decodes cleanly to CODE_23
        res4 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 23,
            "uncertain": False,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res4["class"], "CODE_23")

        # 5. Out-of-table Count 27 WITHOUT uncertainty -> UNKNOWN_CODE
        res5 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 27,
            "uncertain": False,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res5["class"], "UNKNOWN_CODE")

        # 6. Count 11 with uncertainty -> NOT ambiguous under off-by-one rule (10 is not in table)
        res6 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 11,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res6["class"], "CODE_11")
        self.assertEqual(res6["last_stage_reached"], "STAGE_BC_CORE_ENTRY")

    def test_wrong_candidate_hash(self) -> None:
        """Covers INVALID_CANDIDATE when candidate SHA-256 does not match."""
        invalid_hashes = [
            "0000000000000000000000000000000000000000000000000000000000000000",
            "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136",  # default build hash
            "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056",  # poweron-fix hash
            "",
            "bad_hash",
        ]
        for bad_hash in invalid_hashes:
            with self.subTest(bad_hash=bad_hash):
                report = {
                    "diskboot_sha256": bad_hash,
                    "press": "short",
                    "pulses": 25,
                    "lcd": "dark",
                    "inspector_status": "none",
                }
                res = classify_owner_report(report)
                self.assertEqual(res["class"], "INVALID_CANDIDATE")
                self.assertIsNone(res["last_stage_reached"])
                self.assertIsNone(res["next_stage"])
                self.assertIn("mismatch", res["notes"])
                self.assertIn("docs/PORT25_LADDER_FIX_CANDIDATE.md:385", res["evidence"])

    def test_held_press_o1_control(self) -> None:
        """Covers CONTROL_HELD_O1 when a held press reaches the stock UI."""
        # 1. Standard held press booting to stock UI with inspector status O1
        res1 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "held",
            "pulses": "none",
            "lcd": "stock_ui",
            "inspector_status": "O1",
        })
        self.assertEqual(res1["class"], "CONTROL_HELD_O1")
        self.assertEqual(res1["last_stage_reached"], "STOCK_UI")
        self.assertIsNone(res1["next_stage"])
        self.assertIn("positive control", res1["notes"])

        # 2. Held press with live_view and inspector O6 (WITNESS_INVALID)
        res2 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "held",
            "pulses": 44,
            "lcd": "live_view",
            "inspector_status": "WITNESS_INVALID",
        })
        self.assertEqual(res2["class"], "CONTROL_HELD_O1")

        # 3. Held press that HUNG or powered off early (lcd: dark, pulses: 24)
        # Should NOT be CONTROL_HELD_O1; should decode to the stage reached
        res3 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "held",
            "pulses": 24,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res3["class"], "CODE_24")
        self.assertEqual(res3["last_stage_reached"], "STAGE_BC_PRE_POWER_CHECK")

    def test_refusal_of_forbidden_paths(self) -> None:
        """Covers strict Phase 0 refusal of paths ending in .bin, .rom, or starting with PRIMARY*."""
        forbidden_paths = [
            "PRIMARY.BIN",
            "primary.bin",
            "/some/dir/PRIMARY.BIN",
            "firmware.rom",
            "ROM.ROM",
            "camera_dump.bin",
            "test.BIN",
            "PRIMARY_dump.txt",
            "PRIMARY_test.json",
            Path("firmware.rom"),
            Path("PRIMARY.BIN"),
        ]
        for forbidden in forbidden_paths:
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(SafetyViolationError):
                    validate_safety_path(forbidden)
                with self.assertRaises(SafetyViolationError):
                    parse_owner_report(forbidden)
                with self.assertRaises(SafetyViolationError):
                    decode_ladder_report(forbidden)

        # CLI refusal test
        for forbidden in ["test.bin", "firmware.rom", "PRIMARY.BIN", "PRIMARY_report.txt"]:
            with self.subTest(cli_forbidden=forbidden):
                proc = subprocess.run(
                    [sys.executable, str(TOOL_PATH), forbidden],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(proc.returncode, 2)
                self.assertIn("Safety violation", proc.stderr)

    def test_both_input_formats(self) -> None:
        """Covers both JSON and simple key=value text formats producing byte-identical JSON outputs."""
        json_payload = (
            '{\n'
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "press": "short",\n'
            '  "pulses": 25,\n'
            '  "lcd": "dark",\n'
            '  "inspector_status": "none"\n'
            '}'
        )

        kv_payload = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 25\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )

        out_json_from_json = decode_ladder_report(json_payload)
        out_json_from_kv = decode_ladder_report(kv_payload)

        self.assertEqual(out_json_from_json, out_json_from_kv)

        # Verify parsed dictionary values
        dict_from_json = json.loads(out_json_from_json)
        self.assertEqual(dict_from_json["class"], "CODE_25")
        self.assertEqual(dict_from_json["last_stage_reached"], "STAGE_BC_POWER_CHECK_PASS")
        self.assertEqual(dict_from_json["next_stage"], "STAGE_BC_PRE_CREATE_STARTUP")

        # Test from temporary files on disk
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "report.json"
            txt_file = Path(tmpdir) / "report.txt"

            json_file.write_text(json_payload, encoding="utf-8")
            txt_file.write_text(kv_payload, encoding="utf-8")

            out_file_json = decode_ladder_report(json_file)
            out_file_txt = decode_ladder_report(txt_file)

            self.assertEqual(out_file_json, out_json_from_json)
            self.assertEqual(out_file_txt, out_json_from_json)

    def test_determinism(self) -> None:
        """Asserts that decoding the exact same input repeatedly produces byte-identical JSON."""
        sample_input = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 14,
            "lcd": "dark",
            "inspector_status": "none",
        }

        first_output = decode_ladder_report(sample_input)
        for _ in range(50):
            repeated_output = decode_ladder_report(sample_input)
            self.assertEqual(first_output, repeated_output)

        # Validate JSON formatting
        parsed = json.loads(first_output)
        self.assertEqual(list(parsed.keys()), sorted(list(parsed.keys())))


if __name__ == "__main__":
    unittest.main()
