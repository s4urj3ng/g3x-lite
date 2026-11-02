#!/usr/bin/env python3
"""PORT-26 T1: Comprehensive Test Suite for LED-Code Ladder Decoder Tool.

Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p26-t1-ladder-decode

Coverage Requirements:
1. Every table code in LADDER_STAGE_TABLE (29 codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44).
2. 'none' / zero pulses -> NO_PULSES (exact case-insensitive 'none' ONLY).
3. Out-of-table counts, out-of-range counts, and invalid inputs -> UNKNOWN_CODE.
4. Off-by-one ambiguity (conflicting multiple counts, count adjacent to two valid codes with uncertainty).
5. Comprehensive owner-uncertainty flag spelling variants in both JSON and key=value formats.
6. Wrong candidate hash -> INVALID_CANDIDATE.
7. Held-press control reaching stock UI -> CONTROL_HELD_O1 with affirmative allow-list.
8. Refusal of forbidden paths (.bin, .rom, PRIMARY*, and symlinks before any open).
9. File parsing: JSON with trailing newline, JSON without, and key=value all decode identically.
10. Single source of truth consistency:
    - Runtime parsing of docs/PORT25_LADDER_FIX_CANDIDATE.md matches in-tool table.
    - Runtime extraction of p25-t3b build source emit sites (loader_main_breadcrumb.c,
      build_candidate_port25_ladder_fix.py, led_breadcrumb.h).
    - Parse actual CORE_LADDER_FRAME(tens, units) digits and assert tens*10+units == code.
    - Loader steps 1..7 emit site order and stage association.
    - Negative consistency test: modifying CORE_LADDER_FRAME(2, 4) to (2, 5) FAILS.
11. Code 44 next_stage is sub_fc0d0126; no boot-success claim when lcd='dark'.
12. Deterministic byte-identical JSON outputs.
"""

from __future__ import annotations

import builtins
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "port26_ladder_decode.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.port26_ladder_decode as decoder
from tools.port26_ladder_decode import (
    EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    LADDER_STAGE_TABLE,
    NEXT_STAGE_MAP,
    STOCK_UI_LCD_ALLOWLIST,
    VALID_CLASSES,
    CountConfidence,
    LcdState,
    SafetyViolationError,
    classify_owner_report,
    decode_ladder_report,
    derive_next_stage_map,
    extract_build_source_pulse_codes,
    get_canonical_ladder_path,
    is_affirmative_stock_ui,
    is_count_adjacent_to_two_valid_codes,
    is_truthy,
    normalize_count_confidence,
    normalize_lcd_state,
    normalize_uncertainty,
    parse_expected_diskboot_sha256,
    parse_header_pulse_digits,
    parse_ladder_table_from_build_source,
    parse_ladder_table_from_source,
    parse_owner_report,
    parse_recognized_boolean,
    safe_open_report,
    validate_ordered_code_sequence,
    validate_safety_path,
    verify_source_consistency,
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

    def test_source_consistency_macro_digits_and_emit_sites(self) -> None:
        """[P2 Regression] Detailed verification of CORE_LADDER_FRAME(tens, units) and loader/core emit sites."""
        consistency_result = verify_source_consistency(repo_root=REPO_ROOT)
        code_digits = consistency_result["code_digits"]

        # Assert every core code >= 11 has tens*10+units == code == table code
        core_codes = [c for c in LADDER_STAGE_TABLE if c >= 11]
        for c in core_codes:
            self.assertIn(c, code_digits, f"Code {c} not found in parsed header digits")
            tens, units = code_digits[c]
            self.assertEqual(
                tens * 10 + units,
                c,
                f"Code {c} digits mismatch: {tens}*10+{units} != {c}",
            )

        # Assert loader steps 1..7 match table
        loader_steps = consistency_result["loader_steps"]
        self.assertEqual(len(loader_steps), 7)
        for step in range(1, 8):
            self.assertEqual(loader_steps[step], LADDER_STAGE_TABLE[step]["stage_symbol"])

        # Assert full mapping {code -> (adjacent_call, before|after, order_index, last_stage_reached, next_stage)}
        full_mapping = consistency_result["full_mapping"]
        self.assertEqual(len(full_mapping), len(LADDER_STAGE_TABLE))
        for code, expected_entry in LADDER_STAGE_TABLE.items():
            self.assertIn(code, full_mapping)
            adj, pos, ord_idx, last_stage, next_stage = full_mapping[code]
            self.assertEqual(adj, expected_entry["adjacent_call"], f"Emit site mismatch for code {code}")
            self.assertEqual(pos, expected_entry["call_position"], f"Position mismatch for code {code}")
            self.assertEqual(ord_idx, expected_entry["order_index"], f"Order index mismatch for code {code}")
            self.assertEqual(last_stage, expected_entry["stage_symbol"], f"Last stage mismatch for code {code}")
            self.assertEqual(next_stage, NEXT_STAGE_MAP[code], f"Next stage mismatch for code {code}")

    def test_source_consistency_negative_tampered_digits(self) -> None:
        """[P2 Regression] Negative test: changing CORE_LADDER_FRAME(2, 4) to (2, 5) in header FAILS consistency."""
        header_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h"
        with open(header_path, "r", encoding="utf-8") as f:
            header_text = f.read()

        target_macro = "CORE_LADDER_PULSE_24 CORE_LADDER_FRAME(2, 4)"
        self.assertIn(target_macro, header_text)
        tampered_header = header_text.replace(
            target_macro,
            "CORE_LADDER_PULSE_24 CORE_LADDER_FRAME(2, 5)",
        )

        with self.assertRaises(ValueError) as ctx:
            verify_source_consistency(header_content=tampered_header, repo_root=REPO_ROOT)

        self.assertIn("PULSE_24", str(ctx.exception))
        self.assertIn("25 != 24", str(ctx.exception))

    def test_source_consistency_negative_swapped_22_23_around_sub_fc05ba68(self) -> None:
        """[P2 Negative Test] Swapping CORE_LADDER_PULSE_22 and 23 emit sites around sub_fc05ba68 in memory raises ValueError."""
        build_script_path = REPO_ROOT / "tools" / "build_candidate_port25_ladder_fix.py"
        with open(build_script_path, "r", encoding="utf-8") as f:
            build_script_text = f.read()

        target = r'CORE_LADDER_PULSE_22 \"    bl      sub_fc05ba68\\n\" CORE_LADDER_PULSE_23'
        replacement = r'CORE_LADDER_PULSE_23 \"    bl      sub_fc05ba68\\n\" CORE_LADDER_PULSE_22'
        self.assertIn(target, build_script_text)

        tampered_script = build_script_text.replace(target, replacement)
        self.assertNotEqual(tampered_script, build_script_text)

        with self.assertRaises(ValueError) as ctx:
            verify_source_consistency(build_script_content=tampered_script, repo_root=REPO_ROOT)

        err_msg = str(ctx.exception)
        self.assertTrue(
            "Position mismatch" in err_msg or "Order index mismatch" in err_msg,
            f"Expected position or order index mismatch, got: {err_msg}",
        )

    def test_source_consistency_negative_reordered_loader_steps(self) -> None:
        """[P2 Negative Test] Reordering two loader steps in loader_main_breadcrumb.c in memory raises ValueError."""
        loader_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_main_breadcrumb.c"
        with open(loader_path, "r", encoding="utf-8") as f:
            loader_text = f.read()

        s3_pat = re.search(
            r"#if defined\(LED_LADDER\)\s*//\s*Step 3: before_dcache\s*LADDER_ASM_PULSE\s*#endif",
            loader_text,
        )
        s4_pat = re.search(
            r"#if defined\(LED_LADDER\)\s*//\s*Step 4: after_dcache\s*LADDER_ASM_PULSE\s*#endif",
            loader_text,
        )
        self.assertIsNotNone(s3_pat)
        self.assertIsNotNone(s4_pat)

        s3_text = s3_pat.group(0)
        s4_text = s4_pat.group(0)

        # Swap Step 3 and Step 4 in memory
        tampered_loader = (
            loader_text.replace(s3_text, "TEMP_STEP_SWAP")
            .replace(s4_text, s3_text)
            .replace("TEMP_STEP_SWAP", s4_text)
        )
        self.assertNotEqual(tampered_loader, loader_text)

        with self.assertRaises(ValueError) as ctx:
            verify_source_consistency(loader_content=tampered_loader, repo_root=REPO_ROOT)

        err_msg = str(ctx.exception)
        self.assertTrue(
            "Loader steps out of order" in err_msg
            or "emitted before" in err_msg
            or "emitted after" in err_msg,
            f"Expected loader step order or position failure, got: {err_msg}",
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

    def test_code_44_continuation_and_stock_ui_evidence(self) -> None:
        """[P2 Regression] Code 44 next_stage must be sub_fc0d0126, not STOCK_BOOT_SUCCESS.
        
        When lcd='dark', no success claim is made. When affirmative stock UI is observed,
        the claim is recorded in notes, never in next_stage.
        """
        # Code 44 with lcd='dark' -> next_stage is sub_fc0d0126, no success claim
        report_dark = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 44,
            "lcd": "dark",
            "inspector_status": "none",
        }
        res_dark = classify_owner_report(report_dark)
        self.assertEqual(res_dark["class"], "CODE_44")
        self.assertEqual(res_dark["last_stage_reached"], "STAGE_BC_PRE_FIRMWARE_CONT")
        self.assertEqual(res_dark["next_stage"], "sub_fc0d0126")
        self.assertNotIn("success", res_dark["notes"].lower())
        self.assertNotIn("stock_boot_success", str(res_dark["next_stage"]).lower())
        self.assertIn("sub_fc0d0126", res_dark["notes"])

        # Code 44 with affirmative lcd='stock_ui' -> records affirmative UI evidence in notes
        report_stock = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 44,
            "lcd": "stock_ui",
            "inspector_status": "none",
        }
        res_stock = classify_owner_report(report_stock)
        self.assertEqual(res_stock["class"], "CODE_44")
        self.assertEqual(res_stock["next_stage"], "sub_fc0d0126")
        self.assertIn("Independent affirmative UI evidence", res_stock["notes"])

    def test_in_range_gap_codes(self) -> None:
        """Covers all in-range gaps within 1..44 mapping to UNKNOWN_CODE when uncertainty is not flagged."""
        in_range_gaps = [8, 9, 10, 16, 17, 18, 19, 20, 27, 30, 36, 37, 38, 39, 40]

        for count in in_range_gaps:
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
        """Covers exact case-insensitive 'none' mapping to NO_PULSES."""
        for val in ["none", "NONE", "None", "  none  "]:
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
                self.assertEqual(res["last_stage_reached"], "UNKNOWN (no LED evidence)")
                self.assertEqual(res["next_stage"], "UNKNOWN (no LED evidence)")
                self.assertIn("no ladder checkpoint was observed", res["notes"].lower())
                self.assertNotIn("dark from start", res["notes"].lower())
                self.assertIn("docs/PORT25_OWNER_TRIAL_PLAN.md:201", res["evidence"])

    def test_no_pulses_observations_and_conflict_regressions(self) -> None:
        """[P2 Regression] Owner reports with pulses='none':
        (a) pulses=none + lcd=stock_ui + expected hash + short press:
            class NO_PULSES, last_stage_reached/next_stage UNKNOWN, no 'dark from start' text.
            Observations conflict with ladder expected behaviour, labelled UNKNOWN.
            Both JSON and key=value input tested, asserting byte-identical output.
        (b) pulses=none + an illuminated or backlight-on LCD:
            same expectations (class NO_PULSES, last_stage_reached/next_stage UNKNOWN,
            no 'dark from start' text, conflict note labelled UNKNOWN).
        (c) pulses=none + lcd=off:
            gives NO_PULSES with no contradictory text and no 'dark from start' text.
        """
        # (a) pulses=none + lcd=stock_ui + expected hash + short press
        stock_ui_json = (
            "{\n"
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "inspector_status": "none",\n'
            '  "lcd": "stock_ui",\n'
            '  "press": "short",\n'
            '  "pulses": "none"\n'
            "}"
        )
        stock_ui_kv = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = none\n"
            "lcd = stock_ui\n"
            "inspector_status = none\n"
        )

        res_json = classify_owner_report(stock_ui_json)
        res_kv = classify_owner_report(stock_ui_kv)

        self.assertEqual(res_json["class"], "NO_PULSES")
        self.assertEqual(res_kv["class"], "NO_PULSES")
        self.assertEqual(res_json["last_stage_reached"], "UNKNOWN (no LED evidence)")
        self.assertEqual(res_kv["last_stage_reached"], "UNKNOWN (no LED evidence)")
        self.assertEqual(res_json["next_stage"], "UNKNOWN (no LED evidence)")
        self.assertEqual(res_kv["next_stage"], "UNKNOWN (no LED evidence)")

        # Verify no 'dark from start' text
        self.assertNotIn("dark from start", res_json["notes"].lower())
        self.assertNotIn("dark from start", res_kv["notes"].lower())

        # Verify observed inputs echoed verbatim
        self.assertIn("lcd='stock_ui'", res_json["notes"])
        self.assertIn("inspector_status='none'", res_json["notes"])
        self.assertIn("press='short'", res_json["notes"])

        # Verify conflict note labelled UNKNOWN
        self.assertIn("conflict with the ladder's expected behaviour", res_json["notes"].lower())
        self.assertIn("unknown", res_json["notes"].lower())

        # Verify byte-identical JSON output between JSON and key=value inputs
        out_json_from_json = decode_ladder_report(stock_ui_json)
        out_json_from_kv = decode_ladder_report(stock_ui_kv)
        self.assertEqual(out_json_from_json, out_json_from_kv)

        # (b) pulses=none + an illuminated or backlight-on LCD
        for illuminated_val in [
            "illuminated",
            "backlight_on",
            "backlight on",
            "an illuminated lcd",
            "backlight",
        ]:
            with self.subTest(lcd=illuminated_val):
                report_b = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": "none",
                    "lcd": illuminated_val,
                    "inspector_status": "none",
                }
                res_b = classify_owner_report(report_b)
                self.assertEqual(res_b["class"], "NO_PULSES")
                self.assertEqual(res_b["last_stage_reached"], "UNKNOWN (no LED evidence)")
                self.assertEqual(res_b["next_stage"], "UNKNOWN (no LED evidence)")
                self.assertNotIn("dark from start", res_b["notes"].lower())
                self.assertIn(f"lcd='{illuminated_val}'", res_b["notes"])
                self.assertIn("conflict with the ladder's expected behaviour", res_b["notes"].lower())
                self.assertIn("unknown", res_b["notes"].lower())

        # (c) pulses=none + lcd=off still gives NO_PULSES with no contradictory text
        for off_val in ["off", "OFF", "dark"]:
            with self.subTest(lcd=off_val):
                report_c = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "pulses": "none",
                    "lcd": off_val,
                    "inspector_status": "none",
                }
                res_c = classify_owner_report(report_c)
                self.assertEqual(res_c["class"], "NO_PULSES")
                self.assertEqual(res_c["last_stage_reached"], "UNKNOWN (no LED evidence)")
                self.assertEqual(res_c["next_stage"], "UNKNOWN (no LED evidence)")
                self.assertNotIn("dark from start", res_c["notes"].lower())
                self.assertNotIn("conflict", res_c["notes"].lower())
                self.assertIn(f"lcd='{off_val}'", res_c["notes"])

    def test_pulse_input_validation_regressions(self) -> None:
        """[P2 Regression] Rigorous pulse input validation:
        Tests for missing, 'unknown', 24.9, True, -1, '24.0', 0, '', and '?'.
        None of these must become NO_PULSES or CODE_xx.
        """
        cases = [
            ("missing", {}),
            ("unknown", {"pulses": "unknown"}),
            ("float_24_9", {"pulses": 24.9}),
            ("bool_True", {"pulses": True}),
            ("bool_False", {"pulses": False}),
            ("negative_minus_1", {"pulses": -1}),
            ("decimal_str_24_0", {"pulses": "24.0"}),
            ("zero_int", {"pulses": 0}),
            ("zero_str", {"pulses": "0"}),
            ("empty_str", {"pulses": ""}),
            ("question_mark", {"pulses": "?"}),
        ]

        for name, extra in cases:
            with self.subTest(case=name):
                report = {
                    "diskboot_sha256": self.valid_hash,
                    "press": "short",
                    "lcd": "dark",
                    "inspector_status": "none",
                    **extra,
                }
                res = classify_owner_report(report)
                self.assertEqual(
                    res["class"],
                    "UNKNOWN_CODE",
                    f"Case {name} expected UNKNOWN_CODE, got {res['class']}",
                )
                self.assertNotEqual(res["class"], "NO_PULSES")
                self.assertFalse(res["class"].startswith("CODE_"))
                self.assertIsNone(res["last_stage_reached"])

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
        self.assertTrue(is_count_adjacent_to_two_valid_codes(23))
        self.assertTrue(is_count_adjacent_to_two_valid_codes(24))
        self.assertTrue(is_count_adjacent_to_two_valid_codes(27))
        self.assertFalse(is_count_adjacent_to_two_valid_codes(11))
        self.assertFalse(is_count_adjacent_to_two_valid_codes(7))
        self.assertFalse(is_count_adjacent_to_two_valid_codes(1))
        self.assertFalse(is_count_adjacent_to_two_valid_codes(44))
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
        """Covers all spelling variants of the owner uncertainty flag in JSON and key=value,
        including explicit flags and negated free-text regression cases.
        """
        # 1. JSON variants that must trigger uncertainty on adjacent code 24:
        json_uncertain_variants = [
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": true, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": "true", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertainty": true, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertainty": "yes", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "uncertain": 1, "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "count_confidence": "uncertain", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "pulse count uncertain", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "unsure, maybe 23 or 24", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "approx 24 pulses", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "counted 24, +/-1 pulse error", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "counted 24; might have been 23", "lcd": "dark", "inspector_status": "none"}',
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
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "count_confidence": "exact", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "count is not uncertain", "lcd": "dark", "inspector_status": "none"}',
            '{"diskboot_sha256": "%s", "press": "short", "pulses": 24, "notes": "no uncertainty; counted exactly 24", "lcd": "dark", "inspector_status": "none"}',
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
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\ncount_confidence = uncertain\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = count was uncertain\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = unsure, maybe 23 or 24\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = approx 24\n",
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
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\ncount_confidence = exact\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = count is not uncertain\n",
            f"diskboot_sha256 = {self.valid_hash}\npress = short\npulses = 24\nnotes = no uncertainty; counted exactly 24\n",
        ]
        for kv in kv_not_uncertain:
            with self.subTest(kv_neg=kv.splitlines()[-1]):
                res = classify_owner_report(kv)
                self.assertEqual(res["class"], "CODE_24", f"Should be CODE_24 for: {kv!r}")

    def test_uncertainty_normalization_and_duplicate_keys_regression(self) -> None:
        """[P2 Regression] Normalise uncertainty and reject conflicting duplicate keys:
        1. pulses=24 with uncertain=true and uncertainty=false gives AMBIGUOUS in JSON,
           in key=value with one field order, and in key=value with the reversed order.
           All three outputs must be byte-identical JSON.
        2. Mirror case: uncertain=false and uncertainty=true also gives AMBIGUOUS in both
           formats and both orders; all outputs are byte-identical.
        3. An unrecognised alias value (for example uncertain=maybe) is treated as uncertain.
        4. Duplicate conflicting key=value lines (for example two pulses= lines with different
           values) never give a definite CODE_* class.
        """
        # 1. pulses=24 with uncertain=true and uncertainty=false
        json_true_false = (
            '{\n'
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "press": "short",\n'
            '  "pulses": 24,\n'
            '  "uncertain": true,\n'
            '  "uncertainty": false,\n'
            '  "lcd": "dark",\n'
            '  "inspector_status": "none"\n'
            '}'
        )
        kv_order1 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "uncertain = true\n"
            "uncertainty = false\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        kv_order2 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "uncertainty = false\n"
            "uncertain = true\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )

        out_json = decode_ladder_report(json_true_false)
        out_kv1 = decode_ladder_report(kv_order1)
        out_kv2 = decode_ladder_report(kv_order2)

        dict_json = json.loads(out_json)
        self.assertEqual(dict_json["class"], "AMBIGUOUS")
        self.assertIn("off-by-one uncertainty rule", dict_json["notes"])
        self.assertIn("conflicting uncertainty alias values", dict_json["notes"])

        # All three outputs must be byte-identical JSON
        self.assertEqual(out_json, out_kv1)
        self.assertEqual(out_json, out_kv2)

        # 2. Mirror case: uncertain=false and uncertainty=true
        json_false_true = (
            '{\n'
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "press": "short",\n'
            '  "pulses": 24,\n'
            '  "uncertain": false,\n'
            '  "uncertainty": true,\n'
            '  "lcd": "dark",\n'
            '  "inspector_status": "none"\n'
            '}'
        )
        kv_mirror1 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "uncertain = false\n"
            "uncertainty = true\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        kv_mirror2 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "uncertainty = true\n"
            "uncertain = false\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )

        out_mirror_json = decode_ladder_report(json_false_true)
        out_mirror_kv1 = decode_ladder_report(kv_mirror1)
        out_mirror_kv2 = decode_ladder_report(kv_mirror2)

        dict_mirror_json = json.loads(out_mirror_json)
        self.assertEqual(dict_mirror_json["class"], "AMBIGUOUS")
        self.assertIn("off-by-one uncertainty rule", dict_mirror_json["notes"])
        self.assertIn("conflicting uncertainty alias values", dict_mirror_json["notes"])

        self.assertEqual(out_mirror_json, out_mirror_kv1)
        self.assertEqual(out_mirror_json, out_mirror_kv2)
        # Symmetrical consistency: mirror outputs are also byte-identical to primary outputs
        self.assertEqual(out_mirror_json, out_json)

        # 3. Unrecognised alias value (e.g. uncertain=maybe) treated as uncertain (never false)
        kv_unrecognized = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "uncertain = maybe\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        res_unrec_kv = classify_owner_report(kv_unrecognized)
        self.assertEqual(res_unrec_kv["class"], "AMBIGUOUS")
        self.assertIn("unrecognised boolean value for uncertainty alias", res_unrec_kv["notes"])
        self.assertIn("maybe", res_unrec_kv["notes"])

        json_unrecognized = (
            '{\n'
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "press": "short",\n'
            '  "pulses": 24,\n'
            '  "uncertain": "maybe",\n'
            '  "lcd": "dark",\n'
            '  "inspector_status": "none"\n'
            '}'
        )
        res_unrec_json = classify_owner_report(json_unrecognized)
        self.assertEqual(res_unrec_json["class"], "AMBIGUOUS")
        self.assertEqual(decode_ladder_report(kv_unrecognized), decode_ladder_report(json_unrecognized))

        # Unrecognised boolean with in-table code not adjacent to two valid codes (e.g. code 11)
        res_unrec_11 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 11,
            "uncertain": "maybe",
            "lcd": "dark",
            "inspector_status": "none",
        })
        self.assertEqual(res_unrec_11["class"], "CODE_11")
        self.assertIn("unrecognised boolean value for uncertainty alias", res_unrec_11["notes"])
        self.assertIn("not adjacent to two valid codes", res_unrec_11["notes"])

        # 4. Duplicate conflicting key=value lines never give a definite CODE_* class
        kv_conflicting_pulses_1 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "pulses = 25\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        res_dup_p1 = classify_owner_report(kv_conflicting_pulses_1)
        self.assertEqual(res_dup_p1["class"], "AMBIGUOUS")
        self.assertNotEqual(res_dup_p1["class"], "CODE_24")
        self.assertNotEqual(res_dup_p1["class"], "CODE_25")
        self.assertIn("Conflicting duplicate values for key 'pulses'", res_dup_p1["notes"])

        kv_conflicting_pulses_2 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 25\n"
            "pulses = 24\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        res_dup_p2 = classify_owner_report(kv_conflicting_pulses_2)
        self.assertEqual(res_dup_p2["class"], "AMBIGUOUS")
        self.assertNotEqual(res_dup_p2["class"], "CODE_24")
        self.assertNotEqual(res_dup_p2["class"], "CODE_25")

        # Conflicting press keys
        kv_conflicting_press = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "press = held\n"
            "pulses = 24\n"
            "lcd = stock_ui\n"
            "inspector_status = none\n"
        )
        res_dup_press = classify_owner_report(kv_conflicting_press)
        self.assertEqual(res_dup_press["class"], "AMBIGUOUS")
        self.assertIn("Conflicting duplicate values for key 'press'", res_dup_press["notes"])
        self.assertNotEqual(res_dup_press["class"], "CONTROL_HELD_O1")
        self.assertNotEqual(res_dup_press["class"], "CODE_24")

        # Duplicate IDENTICAL pulses lines (no conflict) decodes cleanly
        kv_identical_pulses = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            "pulses = 24\n"
            "pulses = 24\n"
            "lcd = dark\n"
            "inspector_status = none\n"
        )
        res_ident = classify_owner_report(kv_identical_pulses)
        self.assertEqual(res_ident["class"], "CODE_24")

    def test_wrong_candidate_hash(self) -> None:
        """Covers INVALID_CANDIDATE when candidate SHA-256 does not match."""
        invalid_hashes = [
            "0000000000000000000000000000000000000000000000000000000000000000",
            "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136",
            "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056",
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

    def test_stock_ui_detection_regressions(self) -> None:
        """[P2 Regression] Affirmative Stock-UI detection:
        - Exact allowlist strings map to LcdState.STOCK_UI and yield CONTROL_HELD_O1 when press='held'.
        - Reviewer strings and hedging/questioning phrases map to LcdState.UNKNOWN and NEVER yield CONTROL_HELD_O1:
          'maybe reached stock UI', 'unknown whether stock UI appeared', 'waiting for stock UI',
          'not stock UI', 'stock UI?', 'possibly stock ui'.
        - Held press with pulses=24 and hedging LCD yields CODE_24 with note 'lcd state not affirmatively stock UI'.
        - A short press with 'reached stock UI' does NOT give CONTROL_HELD_O1 (gives CODE_44 on pulses=44).
        - lcd='dark' with inspector_status=WITNESS_INVALID gives no CONTROL_HELD_O1.
        """
        # 1. Affirmative allowlist strings lead to CONTROL_HELD_O1 in JSON and key=value
        json_affirmative = (
            f'{{"diskboot_sha256": "{self.valid_hash}", "press": "held", '
            f'"pulses": 44, "lcd": "reached stock UI", "inspector_status": "none"}}'
        )
        res_json = classify_owner_report(json_affirmative)
        self.assertEqual(res_json["class"], "CONTROL_HELD_O1")
        self.assertEqual(res_json["last_stage_reached"], "STOCK_UI")
        self.assertIsNone(res_json["next_stage"])

        kv_affirmative = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = held\n"
            "pulses = 44\n"
            "lcd = reached stock UI\n"
            "inspector_status = none\n"
        )
        res_kv = classify_owner_report(kv_affirmative)
        self.assertEqual(res_kv["class"], "CONTROL_HELD_O1")
        self.assertEqual(res_kv["last_stage_reached"], "STOCK_UI")
        self.assertIsNone(res_kv["next_stage"])

        # 2. Reviewer specified test strings + hedging/negation phrases that must NEVER yield CONTROL_HELD_O1:
        reviewer_non_affirmative = [
            "maybe reached stock UI",
            "unknown whether stock UI appeared",
            "waiting for stock UI",
            "not stock UI",
            "stock UI?",
            "possibly stock ui",
            "did not reach stock UI",
            "never reached stock ui",
            "stock ui not shown",
            "stock ui didn't show",
            "stock UI failed",
        ]
        for phrase in reviewer_non_affirmative:
            with self.subTest(reviewer_phrase=phrase):
                self.assertEqual(
                    normalize_lcd_state(phrase),
                    LcdState.UNKNOWN,
                    f"Phrase {phrase!r} should normalize to LcdState.UNKNOWN",
                )
                self.assertFalse(is_affirmative_stock_ui(phrase))

                # Held press with pulses=24 must yield CODE_24, never CONTROL_HELD_O1
                res_neg = classify_owner_report({
                    "diskboot_sha256": self.valid_hash,
                    "press": "held",
                    "pulses": 24,
                    "lcd": phrase,
                    "inspector_status": "none",
                })
                self.assertEqual(res_neg["class"], "CODE_24", f"Failed for phrase: {phrase}")
                self.assertNotEqual(res_neg["class"], "CONTROL_HELD_O1")
                self.assertIn("lcd state not affirmatively stock UI", res_neg["notes"])

                # Held press with pulses=44 must yield CODE_44, never CONTROL_HELD_O1
                res_neg_44 = classify_owner_report({
                    "diskboot_sha256": self.valid_hash,
                    "press": "held",
                    "pulses": 44,
                    "lcd": phrase,
                    "inspector_status": "none",
                })
                self.assertEqual(res_neg_44["class"], "CODE_44", f"Failed for phrase: {phrase}")
                self.assertNotEqual(res_neg_44["class"], "CONTROL_HELD_O1")
                self.assertIn("lcd state not affirmatively stock UI", res_neg_44["notes"])

                # Held press with pulses='unknown' must yield UNKNOWN_CODE, never CONTROL_HELD_O1
                res_unknown = classify_owner_report({
                    "diskboot_sha256": self.valid_hash,
                    "press": "held",
                    "pulses": "unknown",
                    "lcd": phrase,
                    "inspector_status": "none",
                })
                self.assertEqual(res_unknown["class"], "UNKNOWN_CODE")
                self.assertNotEqual(res_unknown["class"], "CONTROL_HELD_O1")
                self.assertIn("lcd state not affirmatively stock UI", res_unknown["notes"])

        # 3. Short press with 'reached stock UI' does NOT give CONTROL_HELD_O1 (gives CODE_44)
        res_short = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 44,
            "lcd": "reached stock UI",
            "inspector_status": "none",
        })
        self.assertEqual(res_short["class"], "CODE_44")
        self.assertNotEqual(res_short["class"], "CONTROL_HELD_O1")

        # 4. lcd='dark' with inspector_status=WITNESS_INVALID must NOT imply stock UI
        res_dark = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "held",
            "pulses": 24,
            "lcd": "dark",
            "inspector_status": "WITNESS_INVALID",
        })
        self.assertEqual(res_dark["class"], "CODE_24")
        self.assertNotEqual(res_dark["class"], "CONTROL_HELD_O1")

        # 5. Valid held + stock_ui report still gives CONTROL_HELD_O1
        res_stock = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "held",
            "pulses": "none",
            "lcd": "stock_ui",
            "inspector_status": "O1",
        })
        self.assertEqual(res_stock["class"], "CONTROL_HELD_O1")
        self.assertEqual(res_stock["last_stage_reached"], "STOCK_UI")

        # 6. Affirmative and allow-list check
        self.assertTrue(is_affirmative_stock_ui("stock_ui"))
        self.assertTrue(is_affirmative_stock_ui("STOCK UI"))
        self.assertTrue(is_affirmative_stock_ui("live_view"))
        self.assertTrue(is_affirmative_stock_ui("reached stock UI"))
        self.assertTrue(is_affirmative_stock_ui("stock UI reached"))
        self.assertTrue(is_affirmative_stock_ui("menu shown"))
        self.assertTrue(is_affirmative_stock_ui("shooting screen"))
        self.assertFalse(is_affirmative_stock_ui("did not reach stock UI"))
        self.assertFalse(is_affirmative_stock_ui("never reached stock ui"))
        self.assertFalse(is_affirmative_stock_ui("stock ui not shown"))
        self.assertFalse(is_affirmative_stock_ui("not stock ui"))
        self.assertFalse(is_affirmative_stock_ui("dark"))
        self.assertFalse(is_affirmative_stock_ui("blank screen"))
        self.assertFalse(is_affirmative_stock_ui("free text without menu"))

    def test_file_parsing_whitespace_regressions(self) -> None:
        """[P2 Regression] File parsing with whitespace and newline variations:
        JSON with trailing newline, JSON without, and key=value all decode to CODE_24.
        """
        json_content_no_nl = (
            f'{{"diskboot_sha256": "{self.valid_hash}", '
            f'"press": "short", "pulses": 24, "lcd": "dark", "inspector_status": "none"}}'
        )
        json_content_with_nl = json_content_no_nl + "\n\n  \n"
        kv_content = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            f"press = short\n"
            f"pulses = 24\n"
            f"lcd = dark\n"
            f"inspector_status = none\n"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            p_json_no_nl = Path(tmpdir) / "report_no_nl.json"
            p_json_with_nl = Path(tmpdir) / "report_with_nl.json"
            p_kv = Path(tmpdir) / "report.txt"

            p_json_no_nl.write_text(json_content_no_nl, encoding="utf-8")
            p_json_with_nl.write_text(json_content_with_nl, encoding="utf-8")
            p_kv.write_text(kv_content, encoding="utf-8")

            res1 = classify_owner_report(p_json_no_nl)
            res2 = classify_owner_report(p_json_with_nl)
            res3 = classify_owner_report(p_kv)

            self.assertEqual(res1["class"], "CODE_24")
            self.assertEqual(res2["class"], "CODE_24")
            self.assertEqual(res3["class"], "CODE_24")

            # Deterministic byte-identical output across all three
            out1 = decode_ladder_report(p_json_no_nl)
            out2 = decode_ladder_report(p_json_with_nl)
            out3 = decode_ladder_report(p_kv)
            self.assertEqual(out1, out2)
            self.assertEqual(out1, out3)

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

    def test_path_safety_symlink_regressions(self) -> None:
        """[P1 Regression] Path safety symlink and refusal bypass tests:
        (a) tmp 'report.json ' symlink (trailing whitespace) pointing to PRIMARY.BIN is refused.
        (b) tmp 'x.json' symlink pointing to a.bin is refused.
        (c) a name with trailing whitespace is refused.
        (d) 'PRIMARY.json' is refused.
        (e) parent component with PRIMARY* name is refused.
        Assert builtins.open is NEVER called for any of these (empty placeholders, no ROM bytes).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            primary_file = tmp_path / "PRIMARY.BIN"
            primary_file.write_text("", encoding="utf-8")  # empty placeholder, no ROM bytes

            bin_file = tmp_path / "a.bin"
            bin_file.write_text("", encoding="utf-8")  # empty placeholder, no ROM bytes

            # Case 1: 'report.json ' symlink (trailing space in name) -> PRIMARY.BIN
            symlink_trailing_space = tmp_path / "report.json "
            os.symlink(primary_file, symlink_trailing_space)

            # Case 2: 'x.json' symlink -> a.bin
            symlink_x = tmp_path / "x.json"
            os.symlink(bin_file, symlink_x)

            # Case 3: name with trailing whitespace
            trailing_whitespace_file = tmp_path / "trailing_report.json "

            # Case 4: PRIMARY.json
            primary_json = tmp_path / "PRIMARY.json"
            primary_json.write_text("", encoding="utf-8")

            # Case 5: parent component with PRIMARY* name
            primary_dir = tmp_path / "PRIMARY_DIR"
            primary_dir.mkdir()
            nested_in_primary = primary_dir / "report.json"
            nested_in_primary.write_text("", encoding="utf-8")

            forbidden_targets = [
                ("report.json _to_PRIMARY.BIN", symlink_trailing_space),
                ("x.json_to_a.bin", symlink_x),
                ("trailing_whitespace_name", trailing_whitespace_file),
                ("PRIMARY.json", primary_json),
                ("parent_component_PRIMARY_DIR", nested_in_primary),
            ]

            for case_name, target in forbidden_targets:
                with self.subTest(case=case_name):
                    # Verify both Path and str forms raise SafetyViolationError
                    with self.assertRaises(SafetyViolationError):
                        validate_safety_path(target)
                    with self.assertRaises(SafetyViolationError):
                        validate_safety_path(str(target))

                    with self.assertRaises(SafetyViolationError):
                        safe_open_report(target)
                    with self.assertRaises(SafetyViolationError):
                        safe_open_report(str(target))

                    with self.assertRaises(SafetyViolationError):
                        parse_owner_report(target)
                    with self.assertRaises(SafetyViolationError):
                        parse_owner_report(str(target))

                    with self.assertRaises(SafetyViolationError):
                        decode_ladder_report(target)
                    with self.assertRaises(SafetyViolationError):
                        decode_ladder_report(str(target))

            # Prove refusal happens before any open() by patching builtins.open
            with patch("builtins.open") as mock_open:
                mock_open.side_effect = AssertionError("builtins.open() was called on a forbidden path!")
                for case_name, target in forbidden_targets:
                    with self.subTest(mock_open_case=case_name):
                        with self.assertRaises(SafetyViolationError):
                            validate_safety_path(target)
                        with self.assertRaises(SafetyViolationError):
                            validate_safety_path(str(target))
                        with self.assertRaises(SafetyViolationError):
                            safe_open_report(target)
                        with self.assertRaises(SafetyViolationError):
                            safe_open_report(str(target))
                        with self.assertRaises(SafetyViolationError):
                            parse_owner_report(target)
                        with self.assertRaises(SafetyViolationError):
                            parse_owner_report(str(target))
                        with self.assertRaises(SafetyViolationError):
                            decode_ladder_report(target)
                        with self.assertRaises(SafetyViolationError):
                            decode_ladder_report(str(target))
                # Ensure builtins.open was NEVER called across all tests
                mock_open.assert_not_called()

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

        dict_from_json = json.loads(out_json_from_json)
        self.assertEqual(dict_from_json["class"], "CODE_25")
        self.assertEqual(dict_from_json["last_stage_reached"], "STAGE_BC_POWER_CHECK_PASS")
        self.assertEqual(dict_from_json["next_stage"], "STAGE_BC_PRE_CREATE_STARTUP")

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

        parsed = json.loads(first_output)
        self.assertEqual(list(parsed.keys()), sorted(list(parsed.keys())))

    def test_owner_report_2026_11_02_fixture(self) -> None:
        """[PORT-26 T4] Ingests the 2026-11-02 owner short-press report fixture.
        
        Verifies:
        1. Fixture file exists at tests/fixtures/port26/owner_report_2026-11-02_port25_short.json.
        2. Ingestion classifies as last stage Code 43 (STAGE_BC_POST_PHYSW_CREATE) and Code 44 not reached.
        3. Both names are extracted from the source-of-truth table, never hard-coded.
        4. JSON and key=value fixtures decode byte-identically.
        5. CLI execution matches programmatic classification.
        """
        json_fixture_path = REPO_ROOT / "tests" / "fixtures" / "port26" / "owner_report_2026-11-02_port25_short.json"
        txt_fixture_path = REPO_ROOT / "tests" / "fixtures" / "port26" / "owner_report_2026-11-02_port25_short.txt"

        self.assertTrue(json_fixture_path.is_file(), f"Missing fixture: {json_fixture_path}")
        self.assertTrue(txt_fixture_path.is_file(), f"Missing fixture: {txt_fixture_path}")

        # Derive expected stage names dynamically from parsed source table
        parsed_table = parse_ladder_table_from_build_source()
        expected_code43_sym = parsed_table[43]["stage_symbol"]
        expected_code44_sym = parsed_table[44]["stage_symbol"]
        expected_next_stage = derive_next_stage_map(parsed_table)[43]
        self.assertEqual(expected_next_stage, expected_code44_sym)

        # 1. Classify JSON fixture file
        res_json = classify_owner_report(json_fixture_path)
        self.assertEqual(res_json["class"], "CODE_43")
        self.assertEqual(res_json["last_stage_reached"], expected_code43_sym)
        self.assertEqual(res_json["next_stage"], expected_next_stage)
        self.assertIn("Full ordered ladder sequence verified", res_json["notes"])
        self.assertIn(expected_code43_sym, res_json["notes"])
        self.assertIn(expected_code44_sym, res_json["notes"])

        # 2. Classify key=value fixture file
        res_txt = classify_owner_report(txt_fixture_path)
        self.assertEqual(res_txt["class"], "CODE_43")
        self.assertEqual(res_txt["last_stage_reached"], expected_code43_sym)
        self.assertEqual(res_txt["next_stage"], expected_next_stage)

        # 3. Assert JSON and key=value decode_ladder_report outputs are byte-identical
        out_json_str = decode_ladder_report(json_fixture_path)
        out_txt_str = decode_ladder_report(txt_fixture_path)
        self.assertEqual(out_json_str, out_txt_str)

        # 4. Run CLI tool via subprocess
        cmd = [sys.executable, str(TOOL_PATH), str(json_fixture_path)]
        sub_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(sub_res.returncode, 0, f"CLI invocation failed: {sub_res.stderr}")
        self.assertEqual(sub_res.stdout, out_json_str)

    def test_default_decode_uses_parsed_source_table_when_mocked_build_source(self) -> None:
        """[Feedback P2] Default decoding must use parsed source-of-truth table without table arg.

        Verifies that when parse_ladder_table_from_build_source is mocked to return
        renamed symbols for Code 43 and Code 44, decode_ladder_report and classify_owner_report
        (and CLI main()) invoke the parser and emit the renamed symbols.
        """
        json_fixture_path = REPO_ROOT / "tests" / "fixtures" / "port26" / "owner_report_2026-11-02_port25_short.json"
        self.assertTrue(json_fixture_path.is_file())

        real_table = parse_ladder_table_from_build_source()
        mock_table = copy.deepcopy(real_table)
        mock_code43 = "STAGE_BC_POST_PHYSW_CREATE_RENAMED_BUILD"
        mock_code44 = "STAGE_BC_PRE_FIRMWARE_CONT_RENAMED_BUILD"
        mock_table[43]["stage_symbol"] = mock_code43
        mock_table[44]["stage_symbol"] = mock_code44

        with patch("tools.port26_ladder_decode.parse_ladder_table_from_build_source", return_value=mock_table) as mock_parser:
            # 1. Programmatic classify WITHOUT passing table
            res = classify_owner_report(json_fixture_path)
            mock_parser.assert_called()
            self.assertEqual(res["last_stage_reached"], mock_code43)
            self.assertEqual(res["next_stage"], mock_code44)
            self.assertIn(mock_code43, res["notes"])
            self.assertIn(mock_code44, res["notes"])

            # 2. Programmatic decode_ladder_report WITHOUT passing table
            out_str = decode_ladder_report(json_fixture_path)
            mock_parser.assert_called()
            res_obj = json.loads(out_str)
            self.assertEqual(res_obj["last_stage_reached"], mock_code43)
            self.assertEqual(res_obj["next_stage"], mock_code44)

            # 3. CLI execution via main() WITHOUT passing table
            buf = io.StringIO()
            with patch("sys.argv", [str(TOOL_PATH), str(json_fixture_path)]), patch("sys.stdout", buf):
                decoder.main()
            mock_parser.assert_called()
            cli_obj = json.loads(buf.getvalue())
            self.assertEqual(cli_obj["last_stage_reached"], mock_code43)
            self.assertEqual(cli_obj["next_stage"], mock_code44)

    def test_default_decode_uses_parsed_source_table_when_mocked_doc_source(self) -> None:
        """[Feedback P2] Default decoding must propagate parsed doc table through build source parser.

        Verifies that when parse_ladder_table_from_source is mocked to return
        renamed symbols for Code 43 and Code 44, decode_ladder_report and classify_owner_report
        (and CLI main()) invoke the parser and emit the renamed symbols.
        """
        json_fixture_path = REPO_ROOT / "tests" / "fixtures" / "port26" / "owner_report_2026-11-02_port25_short.json"
        self.assertTrue(json_fixture_path.is_file())

        real_table = parse_ladder_table_from_source()
        mock_table = copy.deepcopy(real_table)
        mock_code43 = "STAGE_BC_POST_PHYSW_CREATE_RENAMED_DOC"
        mock_code44 = "STAGE_BC_PRE_FIRMWARE_CONT_RENAMED_DOC"
        mock_table[43]["stage_symbol"] = mock_code43
        mock_table[44]["stage_symbol"] = mock_code44

        with patch("tools.port26_ladder_decode.parse_ladder_table_from_source", return_value=mock_table) as mock_parser:
            # 1. Programmatic classify WITHOUT passing table
            res = classify_owner_report(json_fixture_path)
            mock_parser.assert_called()
            self.assertEqual(res["last_stage_reached"], mock_code43)
            self.assertEqual(res["next_stage"], mock_code44)
            self.assertIn(mock_code43, res["notes"])
            self.assertIn(mock_code44, res["notes"])

            # 2. Programmatic decode_ladder_report WITHOUT passing table
            out_str = decode_ladder_report(json_fixture_path)
            mock_parser.assert_called()
            res_obj = json.loads(out_str)
            self.assertEqual(res_obj["last_stage_reached"], mock_code43)
            self.assertEqual(res_obj["next_stage"], mock_code44)

            # 3. CLI execution via main() WITHOUT passing table
            buf = io.StringIO()
            with patch("sys.argv", [str(TOOL_PATH), str(json_fixture_path)]), patch("sys.stdout", buf):
                decoder.main()
            mock_parser.assert_called()
            cli_obj = json.loads(buf.getvalue())
            self.assertEqual(cli_obj["last_stage_reached"], mock_code43)
            self.assertEqual(cli_obj["next_stage"], mock_code44)

    def test_default_decode_fails_loudly_on_parser_error(self) -> None:
        """[Feedback P2] Default decoding must fail loudly if parsing fails, never falling back silently."""
        json_fixture_path = REPO_ROOT / "tests" / "fixtures" / "port26" / "owner_report_2026-11-02_port25_short.json"

        with patch("tools.port26_ladder_decode.parse_ladder_table_from_build_source", side_effect=ValueError("Boom: source parse failure")):
            with self.assertRaises(ValueError):
                classify_owner_report(json_fixture_path)

            with self.assertRaises(ValueError):
                decode_ladder_report(json_fixture_path)

            stderr_buf = io.StringIO()
            with patch("sys.argv", [str(TOOL_PATH), str(json_fixture_path)]), patch("sys.stderr", stderr_buf):
                with self.assertRaises(SystemExit) as cm:
                    decoder.main()
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Boom: source parse failure", stderr_buf.getvalue())

    def test_canonical_ladder_path_derivation(self) -> None:
        """[PORT-26 T4] Asserts that get_canonical_ladder_path derives paths from table/NEXT_STAGE_MAP."""
        core_path, loader_path = get_canonical_ladder_path(LADDER_STAGE_TABLE)

        # Loader path must be [1, 2, 3, 4, 5, 6, 7]
        self.assertEqual(loader_path, [1, 2, 3, 4, 5, 6, 7])

        # Core path must start at 11, end at 44, and contain all 19 normal boot core codes
        self.assertEqual(core_path[0], 11)
        self.assertEqual(core_path[-1], 44)
        expected_core = [11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43, 44]
        self.assertEqual(core_path, expected_core)

    def test_full_ordered_code_sequences(self) -> None:
        """[PORT-26 T4] Tests classification of valid full ordered sequences."""
        expected_code43_sym = LADDER_STAGE_TABLE[43]["stage_symbol"]
        expected_code44_sym = LADDER_STAGE_TABLE[44]["stage_symbol"]

        # Full sequence up to Code 43 (loader count 7 prefix)
        seq_43_loader7 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43]
        report_43a = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_43_loader7,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_43a = classify_owner_report(report_43a)
        self.assertEqual(res_43a["class"], "CODE_43")
        self.assertEqual(res_43a["last_stage_reached"], expected_code43_sym)
        self.assertEqual(res_43a["next_stage"], expected_code44_sym)

        # Full sequence up to Code 43 (loader steps 1..7 prefix)
        seq_43_loader1_7 = [1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43]
        report_43b = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_43_loader1_7,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_43b = classify_owner_report(report_43b)
        self.assertEqual(res_43b["class"], "CODE_43")
        self.assertEqual(res_43b["last_stage_reached"], expected_code43_sym)
        self.assertEqual(res_43b["next_stage"], expected_code44_sym)

        # Full sequence reaching terminal Code 44
        seq_44 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43, 44]
        report_44 = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_44,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_44 = classify_owner_report(report_44)
        self.assertEqual(res_44["class"], "CODE_44")
        self.assertEqual(res_44["last_stage_reached"], expected_code44_sym)
        self.assertEqual(res_44["next_stage"], "sub_fc0d0126")

        # Explicit sequence key with matching pulses count
        report_seq_key = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 43,
            "sequence": seq_43_loader7,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_seq_key = classify_owner_report(report_seq_key)
        self.assertEqual(res_seq_key["class"], "CODE_43")
        self.assertEqual(res_seq_key["last_stage_reached"], expected_code43_sym)
        self.assertEqual(res_seq_key["next_stage"], expected_code44_sym)

    def test_ordered_sequence_gap_and_non_monotonic_cases(self) -> None:
        """[PORT-26 T4] Asserts that gapped, non-monotonic, or out-of-table sequences give AMBIGUOUS/UNKNOWN."""
        # Case 1: Sequence with gap - skips Code 13
        seq_gap_13 = [7, 11, 12, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43]
        res_gap_13 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_gap_13,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_gap_13["class"], "AMBIGUOUS")
        self.assertIsNone(res_gap_13["last_stage_reached"])
        self.assertIsNone(res_gap_13["next_stage"])
        self.assertIn("skips expected stage", res_gap_13["notes"])

        # Case 2: Sequence with gap - skips Code 25
        seq_gap_25 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 26]
        res_gap_25 = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_gap_25,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_gap_25["class"], "AMBIGUOUS")
        self.assertIsNone(res_gap_25["last_stage_reached"])
        self.assertIsNone(res_gap_25["next_stage"])
        self.assertIn("skips expected stage", res_gap_25["notes"])

        # Case 3: Non-monotonic sequence - Code 13 before Code 12
        seq_non_mono = [7, 11, 13, 12, 14, 15]
        res_non_mono = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_non_mono,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_non_mono["class"], "AMBIGUOUS")
        self.assertIsNone(res_non_mono["last_stage_reached"])
        self.assertIsNone(res_non_mono["next_stage"])

        # Case 4: Repeating code - Code 12 repeated
        seq_repeating = [7, 11, 12, 12, 13, 14, 15]
        res_repeating = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_repeating,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_repeating["class"], "AMBIGUOUS")
        self.assertIsNone(res_repeating["last_stage_reached"])
        self.assertIsNone(res_repeating["next_stage"])
        self.assertIn("not strictly monotonic", res_repeating["notes"])

        # Case 5: Out-of-table invalid code (Code 99)
        seq_invalid_code = [7, 11, 12, 99, 14, 15]
        res_invalid_code = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": seq_invalid_code,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_invalid_code["class"], "UNKNOWN_CODE")
        self.assertIsNone(res_invalid_code["last_stage_reached"])
        self.assertIsNone(res_invalid_code["next_stage"])
        self.assertIn("does not match any registered code", res_invalid_code["notes"])

        # Case 6: Sequence that does not start with loader count
        seq_no_loader = [11, 12, 13, 14, 15]
        res_no_loader = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": seq_no_loader,
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_no_loader["class"], "AMBIGUOUS")
        self.assertIsNone(res_no_loader["last_stage_reached"])
        self.assertIsNone(res_no_loader["next_stage"])
        self.assertIn("Sequence does not start with initial loader stage", res_no_loader["notes"])

        # Case 7: Conflicting pulses count and sequence terminal code
        res_conflict_p_seq = classify_owner_report({
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 42,
            "sequence": [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43],
            "lcd": "dark",
            "inspector_status": "not_run",
        })
        self.assertEqual(res_conflict_p_seq["class"], "AMBIGUOUS")
        self.assertIsNone(res_conflict_p_seq["last_stage_reached"])
        self.assertIsNone(res_conflict_p_seq["next_stage"])
        self.assertIn("conflicts with terminal code of sequence", res_conflict_p_seq["notes"])

    def test_owner_hash_verification_and_mismatch(self) -> None:
        """[PORT-26 T4] Tests owner hash verification against pinned candidate digest.
        
        Verifies:
        1. Owner reported digest matches EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256 (VERIFIED).
        2. Any mismatched digest triggers INVALID_CANDIDATE, never silently accepted.
        """
        owner_reported_hash = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
        self.assertEqual(
            owner_reported_hash,
            EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
            "Owner reported hash does not match decoder pinned hash [VERIFIED check failed]",
        )

        # Valid owner hash produces CODE_43 on full sequence
        report_valid_hash = {
            "diskboot_sha256": owner_reported_hash,
            "press": "short",
            "pulses": [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43],
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_valid = classify_owner_report(report_valid_hash)
        self.assertEqual(res_valid["class"], "CODE_43")

        # Off-by-one char in hash must produce INVALID_CANDIDATE
        corrupted_hash = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a14"
        report_corrupted = dict(report_valid_hash, diskboot_sha256=corrupted_hash)
        res_corrupted = classify_owner_report(report_corrupted)
        self.assertEqual(res_corrupted["class"], "INVALID_CANDIDATE")
        self.assertIsNone(res_corrupted["last_stage_reached"])
        self.assertIsNone(res_corrupted["next_stage"])
        self.assertIn("mismatch", res_corrupted["notes"])

        # Default build hash (94682573...136) on PORT-25 ladder report must also produce INVALID_CANDIDATE
        default_build_hash = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
        report_default_build = dict(report_valid_hash, diskboot_sha256=default_build_hash)
        res_default_build = classify_owner_report(report_default_build)
        self.assertEqual(res_default_build["class"], "INVALID_CANDIDATE")
        self.assertIsNone(res_default_build["last_stage_reached"])
        self.assertIsNone(res_default_build["next_stage"])

    def test_both_pulses_and_sequence_validation_and_comparison_regressions(self) -> None:
        """[P1 Regression] When both pulses and sequence are present, validate both and compare them.
        
        If they differ, or if either one is invalid (gap, non-monotonic, missing the final code),
        the result must be AMBIGUOUS, never CODE_43 'verified'.
        Regression tests:
        1. Keep fixture sequence and set pulses to [7, 11, 13] -> AMBIGUOUS
        2. Keep fixture sequence and set pulses to [7, 12, 11] -> AMBIGUOUS
        3. Keep fixture sequence and set pulses to full sequence ending at 42 -> AMBIGUOUS
        """
        fixture_seq = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43]

        # Case 1: pulses has gap [7, 11, 13] while sequence is fixture sequence
        rep_gap = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": fixture_seq,
            "pulses": [7, 11, 13],
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_gap = classify_owner_report(rep_gap)
        self.assertEqual(res_gap["class"], "AMBIGUOUS")
        self.assertIsNone(res_gap["last_stage_reached"])
        self.assertIsNone(res_gap["next_stage"])
        self.assertNotEqual(res_gap["class"], "CODE_43")

        # Case 2: pulses is non-monotonic [7, 12, 11] while sequence is fixture sequence
        rep_non_mono = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": fixture_seq,
            "pulses": [7, 12, 11],
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_non_mono = classify_owner_report(rep_non_mono)
        self.assertEqual(res_non_mono["class"], "AMBIGUOUS")
        self.assertIsNone(res_non_mono["last_stage_reached"])
        self.assertIsNone(res_non_mono["next_stage"])
        self.assertNotEqual(res_non_mono["class"], "CODE_43")

        # Case 3: pulses is full sequence ending at 42 (missing final code 43) while sequence ends at 43
        seq_ending_42 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42]
        rep_missing_final = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": fixture_seq,
            "pulses": seq_ending_42,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_missing_final = classify_owner_report(rep_missing_final)
        self.assertEqual(res_missing_final["class"], "AMBIGUOUS")
        self.assertIsNone(res_missing_final["last_stage_reached"])
        self.assertIsNone(res_missing_final["next_stage"])
        self.assertNotEqual(res_missing_final["class"], "CODE_43")

    def test_sequence_alias_normalisation_and_order_invariance(self) -> None:
        """[P2 Regression] Normalise aliases (sequence, code_sequence) before duplicate detection.
        
        If aliases conflict, return AMBIGUOUS regardless of field order.
        If aliases match, return valid classification.
        Test swaps the order and checks the result is byte-identical.
        """
        seq43 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43]
        seq42 = [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42]

        # 1. Conflicting aliases: sequence first, then code_sequence
        kv_conf_order1 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            f"sequence = {seq43}\n"
            f"code_sequence = {seq42}\n"
            "lcd = dark\n"
        )
        # 2. Conflicting aliases: code_sequence first, then sequence
        kv_conf_order2 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            f"code_sequence = {seq42}\n"
            f"sequence = {seq43}\n"
            "lcd = dark\n"
        )

        res_order1 = classify_owner_report(kv_conf_order1)
        res_order2 = classify_owner_report(kv_conf_order2)

        self.assertEqual(res_order1["class"], "AMBIGUOUS")
        self.assertEqual(res_order2["class"], "AMBIGUOUS")
        self.assertIn("Conflicting duplicate values for alias/key 'sequence'", res_order1["notes"])
        self.assertIn("Conflicting duplicate values for alias/key 'sequence'", res_order2["notes"])

        # Both swapped orders produce byte-identical JSON
        out_order1 = decode_ladder_report(kv_conf_order1)
        out_order2 = decode_ladder_report(kv_conf_order2)
        self.assertEqual(out_order1, out_order2)

        # 3. Matching aliases in both orders: decodes cleanly to CODE_43
        kv_match1 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            f"sequence = {seq43}\n"
            f"code_sequence = {seq43}\n"
            "lcd = dark\n"
        )
        kv_match2 = (
            f"diskboot_sha256 = {self.valid_hash}\n"
            "press = short\n"
            f"code_sequence = {seq43}\n"
            f"sequence = {seq43}\n"
            "lcd = dark\n"
        )
        res_m1 = classify_owner_report(kv_match1)
        res_m2 = classify_owner_report(kv_match2)
        self.assertEqual(res_m1["class"], "CODE_43")
        self.assertEqual(res_m2["class"], "CODE_43")
        self.assertEqual(decode_ladder_report(kv_match1), decode_ladder_report(kv_match2))

    def test_empty_sequence_or_pulses_presence_not_truthiness(self) -> None:
        """[P2 Regression] Check whether field is present, not whether it is truthy.
        
        An explicit sequence=[] (or pulses=[]) with a valid hash must return
        UNKNOWN_CODE (or AMBIGUOUS) cleanly, with no assertion or crash.
        """
        # Case 1: explicit sequence=[] with valid hash and short press
        rep_empty_seq = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": [],
            "lcd": "dark",
        }
        res_empty_seq = classify_owner_report(rep_empty_seq)
        self.assertIn(res_empty_seq["class"], ("UNKNOWN_CODE", "AMBIGUOUS"))
        self.assertIsNone(res_empty_seq["last_stage_reached"])

        # Case 2: explicit pulses=[] with valid hash and short press
        rep_empty_pulses = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": [],
            "lcd": "dark",
        }
        res_empty_pulses = classify_owner_report(rep_empty_pulses)
        self.assertIn(res_empty_pulses["class"], ("UNKNOWN_CODE", "AMBIGUOUS"))
        self.assertIsNone(res_empty_pulses["last_stage_reached"])

        # Case 3: both sequence=[] and pulses=[] with valid hash
        rep_both_empty = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "sequence": [],
            "pulses": [],
            "lcd": "dark",
        }
        res_both_empty = classify_owner_report(rep_both_empty)
        self.assertIn(res_both_empty["class"], ("UNKNOWN_CODE", "AMBIGUOUS"))
        self.assertIsNone(res_both_empty["last_stage_reached"])

        # Case 4: JSON string with sequence: []
        json_empty_seq = (
            '{\n'
            f'  "diskboot_sha256": "{self.valid_hash}",\n'
            '  "press": "short",\n'
            '  "sequence": [],\n'
            '  "lcd": "dark"\n'
            '}'
        )
        res_json = classify_owner_report(json_empty_seq)
        self.assertIn(res_json["class"], ("UNKNOWN_CODE", "AMBIGUOUS"))
        self.assertIsNone(res_json["last_stage_reached"])

    def test_parsed_table_dynamic_next_stage_with_renamed_code44(self) -> None:
        """[P2 Regression] Both stage reached and next_stage are taken from parsed table.
        
        Passes a parsed table with a renamed Code 44 symbol and checks that:
        1. Next stage of Code 43 shows the renamed Code 44 symbol.
        2. Notes echo the renamed Code 44 symbol.
        3. Code 44 itself shows the renamed symbol as last_stage_reached.
        """
        import copy
        renamed_symbol = "STAGE_BC_PRE_FIRMWARE_CONT_RENAMED_CUSTOM"

        custom_table = copy.deepcopy(LADDER_STAGE_TABLE)
        custom_table[44]["stage_symbol"] = renamed_symbol

        # Verify derive_next_stage_map produces renamed symbol for Code 43
        derived_map = decoder.derive_next_stage_map(custom_table)
        self.assertEqual(derived_map[43], renamed_symbol)

        # 1. Code 43 report with custom table
        report_43 = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43],
            "sequence": [7, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43],
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_43 = classify_owner_report(report_43, table=custom_table)
        self.assertEqual(res_43["class"], "CODE_43")
        self.assertEqual(res_43["last_stage_reached"], custom_table[43]["stage_symbol"])
        self.assertEqual(res_43["next_stage"], renamed_symbol)
        self.assertIn(renamed_symbol, res_43["notes"])

        # 2. Code 44 report with custom table
        report_44 = {
            "diskboot_sha256": self.valid_hash,
            "press": "short",
            "pulses": 44,
            "lcd": "dark",
            "inspector_status": "not_run",
        }
        res_44 = classify_owner_report(report_44, table=custom_table)
        self.assertEqual(res_44["class"], "CODE_44")
        self.assertEqual(res_44["last_stage_reached"], renamed_symbol)
        self.assertEqual(res_44["next_stage"], "sub_fc0d0126")

        # 3. decode_ladder_report with custom table outputs JSON containing renamed symbol
        out_json = decode_ladder_report(report_43, table=custom_table)
        self.assertIn(renamed_symbol, out_json)


if __name__ == "__main__":
    unittest.main()
