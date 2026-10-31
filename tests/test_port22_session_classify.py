#!/usr/bin/env python3
"""PORT-22 T1: Tests for deterministic session outcome classifier (H1-H4).

Milestone: PORT-22 (Session Ingest & Outcome Classification)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p22-t1-session-classifier

Validates:
1. One fixture per hypothesis H1, H2, H3, H4.
2. At least one AMBIGUOUS fixture matches multiple hypotheses with detailed reason.
3. At least one INCONSISTENT fixture contradicts hypotheses with detailed reason.
4. Malformed-input cases: bad JSON, missing required fields, wrong types produce
   clear error messages and non-zero exit codes without tracebacks.
5. Strict validation of booleans: booleans rejected for ramcmp and startup_timing.
6. Strict validation of port20_led: closed set, dict handling, precedence handling.
7. Strict validation of ramcmp & inspector_osd: partial UNREACHABLE rejected,
   unrecognized strings rejected, reachable ramcmp + UNREACHABLE OSD -> INCONSISTENT.
8. Safety invariant refusal: paths ending in .bin or starting with PRIMARY.* are refused.
9. Runtime consistency test: parses docs/PORT21_OWNER_SESSION_PLAN.md markdown table
   at run time, normalizes each cell, compares row-by-row and column-by-column across
   all hypotheses and all columns with STRUCTURED_RULE_TABLE, and computes each fixture's
   expected classification dynamically from the parsed table without hardcoding.
10. All fixtures under tests/fixtures/port22/*.json are synthetic ("synthetic": true).
11. Deterministic output and --json flag support.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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

    def test_all_fixtures_marked_synthetic(self):
        """All fixtures in tests/fixtures/port22/*.json must be marked with synthetic: true."""
        fixture_files = list(FIXTURES_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixture_files), 6, "Must have at least 6 fixtures")
        for f in fixture_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            self.assertIn("synthetic", data, f"Fixture {f.name} missing 'synthetic' key")
            self.assertTrue(data["synthetic"] is True, f"Fixture {f.name} must have 'synthetic': true")

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
        both H3 and H4 match, correctly yielding AMBIGUOUS as dictated by the table.
        """
        fpath = FIXTURES_DIR / "h4_malformed_witness.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "AMBIGUOUS")
        self.assertEqual(res["classification"], "AMBIGUOUS")
        self.assertIn("H4", res["hypotheses"])
        self.assertIn("H3", res["hypotheses"])
        self.assertEqual(res["hypotheses"], ["H3", "H4"])

    def test_fixture_ambiguous(self):
        """Fixture for AMBIGUOUS: LED unobserved, so H1 and H3 cannot be distinguished by RAMCMP alone."""
        fpath = FIXTURES_DIR / "ambiguous_unobserved_led.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "AMBIGUOUS")
        self.assertEqual(res["classification"], "AMBIGUOUS")
        self.assertIn("H1", res["hypotheses"])
        self.assertIn("H3", res["hypotheses"])

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


class TestPort22SessionClassifierInputValidation(unittest.TestCase):
    """Verifies refusal rules, malformed JSON handling, missing fields, and strict type validation."""

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
        bad_paths = ["PRIMARY.DAT", "PRIMARY_ROM.dump", "PRIMARY.json", "path/to/PRIMARY.txt"]
        for p in bad_paths:
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), p],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, f"Expected non-zero exit for {p}")
            self.assertIn("Refusing path with basename starting with PRIMARY", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

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
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }
        for field in ("card_lock_state", "startup_timing", "port20_led", "ramcmp"):
            copy_data = dict(valid_base)
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

    def test_missing_required_ramcmp_fields(self):
        """Missing RAMCMP required fields produce clear error and non-zero exit without traceback."""
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }
        for ram_field in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
            copy_data = dict(valid_base)
            copy_data["ramcmp"] = dict(valid_base["ramcmp"])
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
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }

        # Boolean in startup_timing
        for bool_val in (True, False):
            copy_data = dict(valid_base)
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
                copy_data = dict(valid_base)
                copy_data["ramcmp"] = dict(valid_base["ramcmp"])
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

    def test_port20_led_strict_validation(self):
        """Strict validation of port20_led: rejection of garbage, dict handling, anchored matching."""
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }

        # String 'GARBAGE' rejected
        copy_data = dict(valid_base)
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
        copy_data = dict(valid_base)
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
        copy_data = dict(valid_base)
        copy_data["port20_led"] = {"pulse": "NO_PULSE"}
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["classification"], "H1")

        # Dict with garbage value rejected
        copy_data = dict(valid_base)
        copy_data["port20_led"] = {"pulse": "GARBAGE"}
        proc = subprocess.run(
            [sys.executable, str(TOOL_PATH), "-"],
            input=json.dumps(copy_data),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unrecognized value for 'port20_led'", proc.stderr)

        # 'PULSES ~1-2 s then OFF' handled correctly as PULSE
        copy_data = dict(valid_base)
        copy_data["port20_led"] = "PULSES ~1-2 s then OFF"
        # Since LED is PULSE and ramcmp is all 0, matches H3
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["classification"], "H3")

    def test_inspector_osd_and_partial_ramcmp_strictly(self):
        """Strict validation of inspector_osd and ramcmp."""
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }

        # Unknown string in inspector_osd rejected
        copy_data = dict(valid_base)
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
        copy_data = dict(valid_base)
        copy_data["inspector_osd"] = "UNREACHABLE"
        code, out = classifier.run_classifier("-", use_json_output=True, stdin_content=json.dumps(copy_data))
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "INCONSISTENT")
        self.assertEqual(res["classification"], "INCONSISTENT")

        # Partially UNREACHABLE ramcmp dict rejected as malformed
        copy_data = dict(valid_base)
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
        copy_data = dict(valid_base)
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
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.doc_lines = DOC_PATH.read_text(encoding="utf-8").splitlines()
        cls.table_lines = [
            line.strip()
            for line in cls.doc_lines[classifier.TABLE_START_LINE - 1 : classifier.TABLE_END_LINE]
        ]
        cls.assertTrue(len(cls.table_lines) >= 7, "Table must contain header, separator, and rows")

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
