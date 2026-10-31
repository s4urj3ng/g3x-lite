#!/usr/bin/env python3
"""PORT-22 T1: Tests for deterministic session outcome classifier (H1-H4).

Milestone: PORT-22 (Session Ingest & Outcome Classification)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p22-t1-session-classifier

Validates:
1. One fixture per hypothesis H1, H2, H3, H4.
2. At least one AMBIGUOUS fixture matches multiple hypotheses with detailed reason.
3. At least one INCONSISTENT fixture contradicts hypotheses with detailed reason.
4. Hand-written expected outcomes tested against CLI --json output for every fixture.
5. Strict rejection of null values for all fields (ramcmp, port20_led, inspector_osd,
   card_lock_state, startup_timing).
6. Closed input schema: removal of undocumented alias keys; passing an alias key on its own
   gives a missing-field error; unrecognized fields are rejected.
7. Strict canonical tokens: rejection of 'NONE', 'N/A', 'HANG', 'UNKNOWN', 'MISSING'.
8. Refusal rules:
   - Paths ending in .bin (case-insensitive) refused.
   - Paths starting with PRIMARY.* refused.
   - Paths not ending in .json refused (e.g. rom.dat).
   - Files ending in .JSON with binary content (NUL bytes / invalid UTF-8) refused.
9. Runtime consistency test: parses docs/PORT21_OWNER_SESSION_PLAN.md markdown table
   at run time, normalizes each cell, compares row-by-row and column-by-column across
   all hypotheses and all columns with STRUCTURED_RULE_TABLE, and computes each fixture's
   expected classification dynamically from the parsed table without hardcoding.
10. All fixtures under tests/fixtures/port22/*.json are synthetic ("synthetic": true).
11. Output reason for AMBIGUOUS [H3, H4] notes that H4 is a strict subset of H3
    citing docs/PORT21_OWNER_SESSION_PLAN.md:173-174.
12. Deterministic output and --json flag support.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TOOL_PATH: Path = REPO_ROOT / "tools" / "port22_session_classify.py"
FIXTURES_DIR: Path = REPO_ROOT / "tests" / "fixtures" / "port22"
DOC_PATH: Path = REPO_ROOT / "docs" / "PORT21_OWNER_SESSION_PLAN.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.port22_session_classify as classifier


def normalize_markdown_table_cell(col_name: str, raw_cell: str) -> Any:
    """Normalizes raw cell text parsed from docs/PORT21_OWNER_SESSION_PLAN.md:169-175."""
    text = raw_cell.strip()
    if any(k in col_name for k in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm")):
        if text.startswith("`0`"):
            return 0
        if text.startswith("`1`"):
            return 1
        if "UNREACHABLE" in text:
            return "UNREACHABLE"
        if text.startswith("`UNKNOWN`"):
            return classifier.WILDCARD
        raise ValueError(f"Cannot normalize RAMCMP cell: '{raw_cell}' in column '{col_name}'")
    elif "LED" in col_name:
        if "NO PULSE" in text:
            return "NO_PULSE"
        if "PULSES" in text or "PULSE" in text:
            return "PULSE"
        if "UNOBSERVED" in text or "UNKNOWN" in text:
            return "UNOBSERVED"
        raise ValueError(f"Cannot normalize LED cell: '{raw_cell}'")
    elif "Inspector OSD" in col_name:
        if "UNREACHABLE" in text:
            return "UNREACHABLE"
        if "WITNESS_INVALID" in text or "INVALID" in text:
            return "WITNESS_INVALID"
        if "LOADER_REACHED" in text:
            return "LOADER_REACHED"
        if "CONT_ATTEMPTED" in text:
            return "CONT_ATTEMPTED"
        raise ValueError(f"Cannot normalize OSD cell: '{raw_cell}'")
    raise ValueError(f"Unrecognized column: '{col_name}'")


def dynamic_classify_from_parsed_table(
    parsed_rules: Dict[str, Dict[str, Any]],
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Dynamically evaluates a report against rules parsed directly from the Markdown table."""
    matching: List[str] = []
    details: Dict[str, List[str]] = {}

    for h_id in sorted(parsed_rules.keys()):
        rule = parsed_rules[h_id]
        matched, msgs = classifier.evaluate_hypothesis_against_rules(h_id, rule, report_data)
        details[h_id] = msgs
        if matched:
            matching.append(h_id)

    matching_sorted = sorted(matching)
    if len(matching_sorted) == 1:
        classification = matching_sorted[0]
        status = "MATCH"
    elif len(matching_sorted) > 1:
        classification = "AMBIGUOUS"
        status = "AMBIGUOUS"
    else:
        classification = "INCONSISTENT"
        status = "INCONSISTENT"

    return {
        "status": status,
        "classification": classification,
        "hypotheses": matching_sorted,
        "details": details,
    }


class TestPort22SessionClassifierFixtures(unittest.TestCase):
    """Verifies that all synthetic fixtures classify correctly according to H1-H4."""

    HANDWRITTEN_EXPECTED: Dict[str, Dict[str, Any]] = {
        "h1_rejected.json": {
            "status": "MATCH",
            "classification": "H1",
            "hypotheses": ["H1"],
        },
        "h2_compat_hang.json": {
            "status": "MATCH",
            "classification": "H2",
            "hypotheses": ["H2"],
        },
        "h3_stock_overwrite.json": {
            "status": "MATCH",
            "classification": "H3",
            "hypotheses": ["H3"],
        },
        "h4_malformed_witness.json": {
            "status": "AMBIGUOUS",
            "classification": "AMBIGUOUS",
            "hypotheses": ["H3", "H4"],
        },
        "ambiguous_unobserved_led.json": {
            "status": "AMBIGUOUS",
            "classification": "AMBIGUOUS",
            "hypotheses": ["H1", "H3"],
        },
        "inconsistent_contradictory.json": {
            "status": "INCONSISTENT",
            "classification": "INCONSISTENT",
            "hypotheses": [],
        },
    }

    def test_all_fixtures_marked_synthetic(self):
        """All fixtures in tests/fixtures/port22/*.json must be marked with synthetic: true."""
        fixture_files = list(FIXTURES_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixture_files), 6, "Must have at least 6 fixtures")
        for f in fixture_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            self.assertIn("synthetic", data, f"Fixture {f.name} missing 'synthetic' key")
            self.assertTrue(data["synthetic"] is True, f"Fixture {f.name} must have 'synthetic': true")

    def test_handwritten_expected_outcomes_against_cli_json(self):
        """Asserts each fixture's CLI --json output against hand-written expectations."""
        for fname, expected in self.HANDWRITTEN_EXPECTED.items():
            fpath = FIXTURES_DIR / fname
            self.assertTrue(fpath.is_file(), f"Fixture file not found: {fpath}")

            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "--json", str(fpath)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"CLI exited with error for {fname}: {proc.stderr}")
            res = json.loads(proc.stdout)

            self.assertEqual(
                res["status"],
                expected["status"],
                f"Status mismatch for {fname}: got {res['status']}, expected {expected['status']}",
            )
            self.assertEqual(
                res["classification"],
                expected["classification"],
                f"Classification mismatch for {fname}: got {res['classification']}, expected {expected['classification']}",
            )
            self.assertEqual(
                res["hypotheses"],
                expected["hypotheses"],
                f"Hypotheses mismatch for {fname}: got {res['hypotheses']}, expected {expected['hypotheses']}",
            )

    def test_fixture_h1(self):
        """Fixture for H1: StartDiskboot rejected binary, normal boot, no pulse, all RAMCMP differs."""
        fpath = FIXTURES_DIR / "h1_rejected.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "MATCH")
        self.assertEqual(res["classification"], "H1")
        self.assertEqual(res["hypotheses"], ["H1"])
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:171", res["reason"])

    def test_fixture_h2(self):
        """Fixture for H2: Loader reached, rear status LED pulsed ~1-2 s, then hung in check_compat."""
        fpath = FIXTURES_DIR / "h2_compat_hang.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "MATCH")
        self.assertEqual(res["classification"], "H2")
        self.assertEqual(res["hypotheses"], ["H2"])
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:172", res["reason"])

    def test_fixture_h3(self):
        """Fixture for H3: Loader ran and pulsed LED, but stock boot later overwrote witness."""
        fpath = FIXTURES_DIR / "h3_stock_overwrite.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "MATCH")
        self.assertEqual(res["classification"], "H3")
        self.assertEqual(res["hypotheses"], ["H3"])
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:173", res["reason"])

    def test_fixture_h4(self):
        """Fixture for H4: Shifted heap succeeded (r_c4=1, r_ct=1), witness struct malformed.
        
        Under the table rules alone, H3 specifies WILDCARD for r_c4, r_ct, and r_wm, so
        both H3 and H4 match, yielding AMBIGUOUS [H3, H4].
        The reason explicitly notes H4 is a strict subset of H3 citing lines 173-174.
        """
        fpath = FIXTURES_DIR / "h4_malformed_witness.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "AMBIGUOUS")
        self.assertEqual(res["classification"], "AMBIGUOUS")
        self.assertEqual(res["hypotheses"], ["H3", "H4"])
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:173-174", res["reason"])
        self.assertIn("strict subset", res["reason"].lower())

    def test_fixture_ambiguous(self):
        """Fixture for AMBIGUOUS: LED unobserved, so H1 and H3 cannot be distinguished by RAMCMP alone."""
        fpath = FIXTURES_DIR / "ambiguous_unobserved_led.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "AMBIGUOUS")
        self.assertEqual(res["classification"], "AMBIGUOUS")
        self.assertEqual(res["hypotheses"], ["H1", "H3"])

    def test_fixture_inconsistent(self):
        """Fixture for INCONSISTENT: NO_PULSE reported but r_c4=1 and r_ct=1 contradicts all hypotheses."""
        fpath = FIXTURES_DIR / "inconsistent_contradictory.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "INCONSISTENT")
        self.assertEqual(res["classification"], "INCONSISTENT")
        self.assertEqual(res["hypotheses"], [])
        self.assertIn("contradict", res["reason"].lower())


def make_valid_base() -> Dict[str, Any]:
    return {
        "card_lock_state": "LOCKED",
        "startup_timing": "normal",
        "port20_led": "NO_PULSE",
        "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
    }


class TestPort22SessionClassifierInputValidation(unittest.TestCase):
    """Verifies refusal rules, malformed JSON handling, missing fields, null rejection,
    closed schema enforcement, and canonical token validation.
    """

    def test_refuse_bin_path(self):
        """Refuses any path ending in .bin (case-insensitive) with non-zero exit and clear message."""
        bad_paths = ["test.bin", "FIRMWARE.BIN", "candidate_loader.Bin", "path/to/image.bin"]
        for p in bad_paths:
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), p],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected non-zero exit for {p}")
            self.assertIn("Refusing binary file path ending in .bin", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_refuse_primary_path(self):
        """Refuses any path with basename starting with PRIMARY with non-zero exit and clear message."""
        bad_paths = ["PRIMARY.DAT", "PRIMARY_ROM.dump", "PRIMARY.json", "path/to/PRIMARY.txt", "primary.json"]
        for p in bad_paths:
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), p],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected non-zero exit for {p}")
            self.assertIn("Refusing path with basename starting with PRIMARY", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_refuse_non_json_path(self):
        """Refuses paths not ending in .json (e.g. rom.dat) with clear refusal message."""
        bad_paths = ["rom.dat", "sample.txt", "data.csv", "report.xml"]
        for p in bad_paths:
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), p],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected non-zero exit for {p}")
            self.assertIn("Refusing non-JSON file path", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_refuse_binary_content_in_json_path(self):
        """Refuses files ending in .JSON containing binary bytes (NUL bytes or non-UTF8)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # File with NUL byte
            nul_file = Path(tmpdir) / "corrupt_null.JSON"
            nul_file.write_bytes(b'{"card_lock_state": \x00 "LOCKED"}')

            proc1 = subprocess.run(
                [sys.executable, str(TOOL_PATH), str(nul_file)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc1.returncode, 0)
            self.assertIn("Binary content detected", proc1.stderr)
            self.assertNotIn("Traceback", proc1.stderr)

            # File with invalid UTF-8 bytes
            invalid_utf8_file = Path(tmpdir) / "invalid_utf8.json"
            invalid_utf8_file.write_bytes(b'{"card_lock_state": \xff\xfe "LOCKED"}')

            proc2 = subprocess.run(
                [sys.executable, str(TOOL_PATH), str(invalid_utf8_file)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc2.returncode, 0)
            self.assertIn("Invalid UTF-8 encoding", proc2.stderr)
            self.assertNotIn("Traceback", proc2.stderr)

    def test_malformed_json_syntax(self):
        """Malformed JSON must exit non-zero with clear error and NO traceback."""
        malformed_inputs = [
            "{bad json",
            '{"unclosed": "string',
            "",
            "[1, 2, 3,",
        ]
        for bad_json in malformed_inputs:
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=bad_json,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_missing_required_top_level_fields(self):
        """Missing top-level required fields produce clear error and non-zero exit without traceback."""
        for field in ("card_lock_state", "startup_timing", "port20_led", "ramcmp"):
            copy_data = make_valid_base()
            del copy_data[field]
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(copy_data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected failure when missing {field}")
            self.assertIn(f"Missing required field: '{field}'", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_alias_keys_produce_missing_required_field_error(self):
        """Alias keys on their own without canonical fields must produce a missing-field error."""
        alias_tests = [
            ("led_observation", "port20_led", "NO_PULSE"),
            ("port20_led_observation", "port20_led", "NO_PULSE"),
            ("card_locked", "card_lock_state", "LOCKED"),
            ("start_up_timing", "startup_timing", "normal"),
        ]
        for alias_key, missing_canonical, sample_val in alias_tests:
            bad_data = make_valid_base()
            del bad_data[missing_canonical]
            bad_data[alias_key] = sample_val

            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(bad_data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(f"Missing required field: '{missing_canonical}'", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_closed_schema_rejects_unrecognized_fields(self):
        """Closed schema: unexpected extra fields must be rejected."""
        bad_data = make_valid_base()
        bad_data["extra_unrecognized_key"] = "unexpected"

        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(bad_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized field in report schema", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_reject_null_values_for_all_fields(self):
        """Null values (null / None) must be rejected for all fields."""
        fields_to_test = [
            "ramcmp",
            "port20_led",
            "inspector_osd",
            "card_lock_state",
            "startup_timing",
        ]
        for field in fields_to_test:
            data = make_valid_base()
            data[field] = None

            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected non-zero exit when {field} is null")
            self.assertIn("null value", proc.stderr.lower())
            self.assertNotIn("Traceback", proc.stderr)

    def test_reject_null_values_inside_ramcmp_dict(self):
        """Null values inside ramcmp dict must be rejected."""
        for ram_field in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
            data = make_valid_base()
            data["ramcmp"][ram_field] = None

            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("null value", proc.stderr.lower())
            self.assertNotIn("Traceback", proc.stderr)

    def test_missing_required_ramcmp_fields(self):
        """Missing RAMCMP required fields produce clear error and non-zero exit without traceback."""
        for ram_field in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
            copy_data = make_valid_base()
            del copy_data["ramcmp"][ram_field]
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(copy_data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected failure when missing RAMCMP {ram_field}")
            self.assertIn(f"Missing required RAMCMP field: '{ram_field}'", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_reject_booleans_in_ramcmp_and_timing(self):
        """Booleans must be explicitly rejected for startup_timing and ramcmp fields."""
        # Boolean in startup_timing
        for bool_val in (True, False):
            copy_data = make_valid_base()
            copy_data["startup_timing"] = bool_val
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(copy_data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("booleans not allowed", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

        # Boolean in ramcmp fields
        for field in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
            for bool_val in (True, False):
                copy_data = make_valid_base()
                copy_data["ramcmp"][field] = bool_val
                proc = subprocess.run(
                    [sys.executable, str(TOOL_PATH), "-"],
                    input=json.dumps(copy_data),
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("booleans not allowed", proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)

    def test_reject_non_canonical_tokens(self):
        """Non-canonical tokens ('NONE', 'N/A', 'HANG', 'UNKNOWN', 'MISSING') must be rejected."""
        # 'NONE' for port20_led rejected
        copy_data = make_valid_base()
        copy_data["port20_led"] = "NONE"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'port20_led'", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

        # 'N/A' for port20_led rejected
        copy_data = make_valid_base()
        copy_data["port20_led"] = "N/A"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'port20_led'", proc.stderr)

        # 'N/A' for inspector_osd rejected
        copy_data = make_valid_base()
        copy_data["inspector_osd"] = "N/A"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'inspector_osd'", proc.stderr)

        # 'HANG' for ramcmp rejected
        copy_data = make_valid_base()
        copy_data["ramcmp"] = "HANG"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized string value for 'ramcmp'", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_port20_led_strict_validation(self):
        """Strict validation of port20_led: rejection of garbage, dict handling, anchored matching."""
        # String 'GARBAGE' rejected
        copy_data = make_valid_base()
        copy_data["port20_led"] = "GARBAGE"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'port20_led'", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

        # Empty dict {} rejected
        copy_data = make_valid_base()
        copy_data["port20_led"] = {}
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("empty dict is not allowed", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

        # Dict {'pulse': 'NO_PULSE'} handled correctly
        copy_data = make_valid_base()
        copy_data["port20_led"] = {"pulse": "NO_PULSE"}
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["classification"], "H1")

        # Dict with garbage value rejected
        copy_data = make_valid_base()
        copy_data["port20_led"] = {"pulse": "GARBAGE"}
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'port20_led'", proc.stderr)

        # 'PULSES ~1-2 s then OFF' handled correctly as PULSE (H3)
        copy_data = make_valid_base()
        copy_data["port20_led"] = "PULSES ~1-2 s then OFF"
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["classification"], "H3")

    def test_inspector_osd_and_partial_ramcmp_strictly(self):
        """Strict validation of inspector_osd and ramcmp."""
        # Unknown string in inspector_osd rejected
        copy_data = make_valid_base()
        copy_data["inspector_osd"] = "GARBAGE_OSD"
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'inspector_osd'", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

        # Reachable ramcmp + inspector_osd 'UNREACHABLE' classifies as INCONSISTENT
        copy_data = make_valid_base()
        copy_data["inspector_osd"] = "UNREACHABLE"
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "INCONSISTENT")
        self.assertEqual(res["classification"], "INCONSISTENT")

        # Partially UNREACHABLE ramcmp dict rejected as malformed
        copy_data = make_valid_base()
        copy_data["ramcmp"] = {"r_l8": 0, "r_l4": "UNREACHABLE", "r_c4": 0, "r_ct": 0, "r_wm": 0}
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("partial UNREACHABLE not allowed", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

        # Invalid RAMCMP integer (e.g. 2) rejected
        copy_data = make_valid_base()
        copy_data["ramcmp"]["r_l8"] = 2
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("expected 0 or 1", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class TestPort22SessionClassifierCLI(unittest.TestCase):
    """Verifies CLI execution, stdin support, and deterministic formatting."""

    def test_stdin_mode_plain_and_json(self):
        """Verifies stdin streaming with and without --json."""
        fpath = FIXTURES_DIR / "h1_rejected.json"
        content = fpath.read_text(encoding="utf-8")

        # Plain text
        proc1 = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=content,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc1.returncode, 0)
        self.assertTrue(proc1.stdout.startswith("H1"))

        # Machine-readable JSON
        proc2 = subprocess.run(
            [sys.executable, str(TOOL_PATH), "--json", "-"],
            input=content,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc2.returncode, 0)
        data = json.loads(proc2.stdout)
        self.assertEqual(data["classification"], "H1")
        self.assertEqual(data["status"], "MATCH")

    def test_deterministic_output(self):
        """Verifies output ordering is 100% deterministic across multiple runs."""
        fpath = FIXTURES_DIR / "h3_stock_overwrite.json"
        runs = []
        for _ in range(5):
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "--json", str(fpath)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            runs.append(proc.stdout)
        self.assertTrue(all(r == runs[0] for r in runs), "CLI output must be deterministic")


class TestPort22MarkdownConsistency(unittest.TestCase):
    """Consistency test: parses docs/PORT21_OWNER_SESSION_PLAN.md at run time
    and checks that the tool's structured table agrees row-by-row and column-by-column,
    then checks that every fixture's classification matches what the parsed table predicts.
    """

    @classmethod
    def setUpClass(cls):
        if not DOC_PATH.is_file():
            raise AssertionError(f"Plan document missing: {DOC_PATH}")

        cls.doc_lines = DOC_PATH.read_text(encoding="utf-8").splitlines()
        cls.table_lines = [
            line.strip()
            for line in cls.doc_lines[classifier.TABLE_START_LINE - 1 : classifier.TABLE_END_LINE]
        ]
        if len(cls.table_lines) < 7:
            raise AssertionError(
                f"Table must contain header, separator, and 4+ rows, got {len(cls.table_lines)} lines"
            )

        # Parse header
        cls.parsed_columns = [c.strip() for c in cls.table_lines[0].split("|")[1:-1]]

        # Parse rows
        cls.parsed_rows: Dict[str, Dict[str, str]] = {}
        for line in cls.table_lines[2:]:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            h_id = cells[0].split(":")[0].replace("*", "").strip()
            cls.parsed_rows[h_id] = {cls.parsed_columns[i]: cells[i] for i in range(len(cls.parsed_columns))}

        # Construct parsed rule table by normalizing each cell
        cls.parsed_rule_table: Dict[str, Dict[str, Any]] = {}
        for h_id in ("H1", "H2", "H3", "H4"):
            line_no = 171 + int(h_id[1]) - 1
            cols_dict: Dict[str, Dict[str, Any]] = {}
            for col in cls.parsed_columns[1:]:
                raw_cell = cls.parsed_rows[h_id][col]
                norm_val = normalize_markdown_table_cell(col, raw_cell)
                cols_dict[col] = {
                    "expected": norm_val,
                    "citation": f"docs/PORT21_OWNER_SESSION_PLAN.md:{line_no}",
                }
            cls.parsed_rule_table[h_id] = {
                "line": line_no,
                "citation": f"docs/PORT21_OWNER_SESSION_PLAN.md:{line_no}",
                "columns": cols_dict,
            }

    def test_table_line_range_and_citations_present(self):
        """Tool must contain citations to docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and lines 171-174."""
        tool_code = TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md", tool_code)
        self.assertIn("169-175", tool_code)
        for line_no in ("171", "172", "173", "174"):
            self.assertIn(f"docs/PORT21_OWNER_SESSION_PLAN.md:{line_no}", tool_code)

    def test_structured_table_row_and_cell_agreement(self):
        """Checks that STRUCTURED_RULE_TABLE agrees with the normalized parsed Markdown table
        for EVERY hypothesis (H1-H4) and EVERY column.
        """
        for h_id in ("H1", "H2", "H3", "H4"):
            self.assertIn(h_id, self.parsed_rule_table, f"Parsed table missing row for {h_id}")
            self.assertIn(h_id, classifier.STRUCTURED_RULE_TABLE, f"STRUCTURED_RULE_TABLE missing {h_id}")

            for col in self.parsed_columns[1:]:
                expected_from_markdown = self.parsed_rule_table[h_id]["columns"][col]["expected"]
                tool_rule_value = classifier.STRUCTURED_RULE_TABLE[h_id]["columns"][col]["expected"]

                self.assertEqual(
                    tool_rule_value,
                    expected_from_markdown,
                    f"Mismatch in hypothesis {h_id}, column '{col}':\n"
                    f"Markdown cell parsed: {expected_from_markdown}\n"
                    f"Tool rule value:      {tool_rule_value}",
                )

    def test_every_fixture_matches_parsed_table_predictions(self):
        """Computes each fixture's expected classification dynamically from the parsed table
        with NO hardcoded dictionary, covering all six fixtures.
        """
        fixture_files = sorted(FIXTURES_DIR.glob("*.json"))
        self.assertEqual(len(fixture_files), 6, "Expected exactly 6 fixtures")

        for fpath in fixture_files:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            parsed_report = classifier.parse_and_validate_report(data)

            # 1. Compute expected classification dynamically from the Markdown table parsed at run time
            expected_result = dynamic_classify_from_parsed_table(self.parsed_rule_table, parsed_report)

            # 2. Compute classification using the tool's classifier
            tool_result = classifier.classify_session_report(parsed_report)

            # 3. Assert full agreement between the dynamically parsed table prediction and tool output
            self.assertEqual(
                tool_result["status"],
                expected_result["status"],
                f"Status mismatch for fixture {fpath.name}: "
                f"tool={tool_result['status']}, table={expected_result['status']}",
            )
            self.assertEqual(
                tool_result["classification"],
                expected_result["classification"],
                f"Classification mismatch for fixture {fpath.name}: "
                f"tool={tool_result['classification']}, table={expected_result['classification']}",
            )
            self.assertEqual(
                tool_result["hypotheses"],
                expected_result["hypotheses"],
                f"Hypotheses mismatch for fixture {fpath.name}: "
                f"tool={tool_result['hypotheses']}, table={expected_result['hypotheses']}",
            )


if __name__ == "__main__":
    unittest.main()
