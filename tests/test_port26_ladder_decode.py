#!/usr/bin/env python3
"""PORT-26 T1: Comprehensive Test Suite for LED-Code Ladder Decoder Tool.

Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p26-t1-ladder-decode

Coverage Requirements:
1. Every table code in LADDER_STAGE_TABLE (29 codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44).
2. 'none' / zero pulses -> NO_PULSES.
3. Out-of-table counts and all in-range gaps within 1..44 -> UNKNOWN_CODE.
4. Off-by-one ambiguity (conflicting multiple counts, count adjacent to two valid codes with uncertainty).
5. Comprehensive owner-uncertainty flag spelling variants in both JSON and key=value formats.
6. Wrong candidate hash -> INVALID_CANDIDATE.
7. Held-press control reaching stock UI -> CONTROL_HELD_O1.
8. Refusal of forbidden paths (.bin, .rom, PRIMARY*).
9. Both input formats (JSON and key=value text) producing byte-identical outputs.
10. Single source of truth consistency:
    - Runtime parsing of docs/PORT25_LADDER_FIX_CANDIDATE.md matches in-tool table.
    - Runtime extraction of p25-t3b build source emit sites (loader_main_breadcrumb.c,
      build_candidate_port25_ladder_fix.py, led_breadcrumb.h) asserts every pulse count in the doc
      appears as an LED-ladder emit site in the source, and both doc and source agree on all 29 codes.
11. Deterministic byte-identical JSON outputs.
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
    extract_build_source_pulse_codes,
    is_count_adjacent_to_two_valid_codes,
    is_truthy,
    parse_expected_diskboot_sha256,
    parse_ladder_table_from_build_source,
    parse_ladder_table_from_source,
    parse_owner_report,
    validate_safety_path,
)


class TestPort26LadderDecode(unittest.TestCase):
    """Test suite for PORT-26 ladder decoder tool and owner report classification."""

    def setUp(self) -> None:
        self.valid_hash = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256

    def test_table_equals_doc_consistency(self) -> None:
        """Asserts that in-tool LADDER_STAGE_TABLE equals the runtime-parsed doc table."""
        doc_path = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"
        self.assertTrue(doc_path.is_file(), f"Missing candidate doc: {doc_path}")

        parsed_table = parse_ladder_table_from_source(doc_path)
        self.assertEqual(
            set(parsed_table.keys()),
            set(LADDER_STAGE_TABLE.keys()),
            "Mismatch in registered code sets between doc and in-tool table",
        )
        self.assertEqual(len(parsed_table), 29, "Expected exactly 29 codes in doc table")

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

    def test_table_equals_build_source_consistency(self) -> None:
        """Asserts that every pulse count in the doc appears as an LED-ladder emit site in the build source.
        
        Build sources:
          - Loader emit sites: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:43-154
          - Core injection sites: tools/build_candidate_port25_ladder_fix.py:90-128
          - Framed timing macro defs: chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266
        """
        build_info = extract_build_source_pulse_codes(REPO_ROOT)

        # 1. Loader steps: Steps 1..7 must match exactly
        expected_loader_steps = {
            1: "STAGE_LOADER_AFTER_PROLOGUE",
            2: "STAGE_LOADER_AFTER_COPY",
            3: "STAGE_LOADER_BEFORE_DCACHE",
            4: "STAGE_LOADER_AFTER_DCACHE",
            5: "STAGE_LOADER_BEFORE_ICACHE",
            6: "STAGE_LOADER_AFTER_ICACHE",
            7: "STAGE_LOADER_BEFORE_BX",
        }
        self.assertEqual(
            build_info["loader_steps"],
            expected_loader_steps,
            "Mismatch in loader ladder steps extracted from loader_main_breadcrumb.c",
        )

        # 2. Core injected codes: exactly 22 codes in tools/build_candidate_port25_ladder_fix.py
        expected_core_codes = [
            11, 12, 13, 14, 15,
            21, 22, 23, 24, 25, 26,
            28, 29,
            31, 32, 33, 34, 35,
            41, 42, 43, 44,
        ]
        self.assertEqual(
            build_info["core_injected_codes"],
            expected_core_codes,
            "Mismatch in core injected codes extracted from build_candidate_port25_ladder_fix.py",
        )

        # 3. Macro definitions in led_breadcrumb.h must include all core codes
        for code in expected_core_codes:
            self.assertIn(
                code,
                build_info["header_macro_codes"],
                f"Missing CORE_LADDER_PULSE_{code} definition in led_breadcrumb.h",
            )

        # 4. Total emitted codes from build source must equal exactly the 29 table codes
        self.assertEqual(len(build_info["all_emitted_codes"]), 29)
        self.assertEqual(
            set(build_info["all_emitted_codes"]),
            set(LADDER_STAGE_TABLE.keys()),
            "Mismatch between build source emit codes and LADDER_STAGE_TABLE codes",
        )

        # 5. Full combined verification via parse_ladder_table_from_build_source()
        combined_table = parse_ladder_table_from_build_source(REPO_ROOT)
        self.assertEqual(len(combined_table), 29)
        self.assertEqual(set(combined_table.keys()), set(LADDER_STAGE_TABLE.keys()))

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

    def test_in_range_gap_codes(self) -> None:
        """Covers all in-range gaps within 1..44 and out-of-range counts mapping to UNKNOWN_CODE.
        
        Inside 1..44, the 15 gap values are:
          8, 9, 10, 16, 17, 18, 19, 20, 27, 30, 36, 37, 38, 39, 40.
        All must map to UNKNOWN_CODE when uncertainty is not flagged.
        """
        in_range_gaps = [8, 9, 10, 16, 17, 18, 19, 20, 27, 30, 36, 37, 38, 39, 40]
        out_of_range_counts = [-5, -1, 45, 50, 99, 120]

        all_unknown_counts = in_range_gaps + out_of_range_counts

        for count in all_unknown_counts:
            with self.subTest(count=count):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": count,
                    "lcd": "dark",
                    "inspector_status": "none",
                    "uncertain": False,
                }
                res = classify_owner_report(report)
                self.assertEqual(res["class"], "UNKNOWN_CODE")
                self.assertIsNone(res["last_stage_reached"])
                self.assertIsNone(res["next_stage"])
                self.assertIn(f"Pulse count {count} does not match", res["notes"])

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
        # Count 27 (out-of-table gap) has 26 and 28 in table -> adjacent to two valid codes
        self.assertTrue(is_count_adjacent_to_two_valid_codes(27))
        # Count 11 has 10 (gap) and 12 (in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(11))
        # Count 7 has 6 (in table) and 8 (gap) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(7))
        # Count 1 has 0 (gap) and 2 (in table) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(1))
        # Count 44 has 43 (in table) and 45 (out) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(44))
        # Count 8 has 7 (in table) and 9 (gap) -> only ONE neighbor
        self.assertFalse(is_count_adjacent_to_two_valid_codes(8))

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

        # 3. In-range gap 27 with uncertainty -> AMBIGUOUS (adjacent to 26 and 28)
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

        # 5. In-range gap 27 WITHOUT uncertainty -> UNKNOWN_CODE
        res5 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 27,
            "uncertain": False,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res5["class"], "UNKNOWN_CODE")

        # 6. Boundary count 11 with uncertainty -> NOT ambiguous under off-by-one rule (10 is a gap)
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

        # 7. Boundary count 1 with uncertainty -> NOT ambiguous (0 is not in table)
        res7 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 1,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res7["class"], "CODE_1")

        # 8. Boundary count 44 with uncertainty -> NOT ambiguous (45 is not in table)
        res8 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 44,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res8["class"], "CODE_44")

        # 9. Isolated gap 8 with uncertainty -> UNKNOWN_CODE (9 is a gap, only 7 is valid)
        res9 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 8,
            "uncertain": True,
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res9["class"], "UNKNOWN_CODE")

    def test_owner_uncertainty_spelling_variants(self) -> None:
        """Covers all spelling variants of the owner uncertainty flag in JSON and key=value."""
        # 1. JSON variants that must trigger uncertainty on adjacent code 24:
        json_uncertain_variants = [
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": true, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": "true", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertainty": true, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertainty": "yes", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": 1, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": "24 (uncertain)", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": "24?", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "pulse count uncertain", "lcd": "dark", "inspector_status": "none"}',
        ]
        for tmpl in json_uncertain_variants:
            raw = tmpl % self.valid_hash
            with self.subTest(json_tmpl=tmpl[:45]):
                res = classify_owner_report(raw)
                self.assertEqual(res["class"], "AMBIGUOUS", f"Failed for template: {tmpl}")

        # 2. JSON negative variants that must NOT trigger uncertainty:
        json_not_uncertain = [
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": false, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": "false", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": 0, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertainty": false, "lcd": "dark", "inspector_status": "none"}',
        ]
        for tmpl in json_not_uncertain:
            raw = tmpl % self.valid_hash
            with self.subTest(json_neg=tmpl[:45]):
                res = classify_owner_report(raw)
                self.assertEqual(res["class"], "CODE_24", f"Should be CODE_24 for: {tmpl}")

        # 3. Key=Value variants that must trigger uncertainty on code 24:
        kv_uncertain_variants = [
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = true\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = yes\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = 1\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertainty = true\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertainty = yes\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24 (uncertain)\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24?\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = count was uncertain\n",
        ]
        for kv in kv_uncertain_variants:
            with self.subTest(kv_raw=kv.splitlines()[-1]):
                res = classify_owner_report(kv)
                self.assertEqual(res["class"], "AMBIGUOUS", f"Failed for KV: {kv!r}")

        # 4. Key=Value negative variants that must NOT trigger uncertainty:
        kv_not_uncertain = [
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = false\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = no\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertain = 0\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nuncertainty = false\n",
        ]
        for kv in kv_not_uncertain:
            with self.subTest(kv_neg=kv.splitlines()[-1]):
                res = classify_owner_report(kv)
                self.assertEqual(res["class"], "CODE_24", f"Should be CODE_24 for: {kv!r}")

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
