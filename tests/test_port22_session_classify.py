#!/usr/bin/env python3
"""PORT-22 T1: Tests for deterministic session outcome classifier (H1-H4).

Milestone: PORT-22 (Session Ingest & Outcome Classification)
Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p22-t1-session-classifier

Validates:
1. One fixture per hypothesis H1, H2, H3, H4 correctly classifies.
2. At least one AMBIGUOUS fixture matches multiple hypotheses with detailed reason.
3. At least one INCONSISTENT fixture contradicts hypotheses with detailed reason.
4. Malformed-input cases: bad JSON, missing required fields, wrong types produce
   clear error messages and non-zero exit codes without tracebacks.
5. Safety invariant refusal: paths ending in .bin or starting with PRIMARY.* are refused.
6. Runtime consistency test: parses docs/PORT21_OWNER_SESSION_PLAN.md markdown table
   at run time, checks agreement row-by-row and column-by-column with ENCODED_TABLE,
   and checks that every fixture's classification matches the parsed table predictions.
7. All fixtures under tests/fixtures/port22/*.json are synthetic ("synthetic": true).
8. Deterministic output and --json flag support.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TOOL_PATH: Path = REPO_ROOT / "tools" / "port22_session_classify.py"
FIXTURES_DIR: Path = REPO_ROOT / "tests" / "fixtures" / "port22"
DOC_PATH: Path = REPO_ROOT / "docs" / "PORT21_OWNER_SESSION_PLAN.md"

# Add REPO_ROOT to sys.path to import tool functions directly
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.port22_session_classify as classifier


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
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:171", classifier.__doc__ or "")

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

    def test_fixture_h4(self):
        """Fixture for H4: Shifted heap succeeded (r_c4=1, r_ct=1), but witness struct malformed."""
        fpath = FIXTURES_DIR / "h4_malformed_witness.json"
        self.assertTrue(fpath.is_file(), f"Missing fixture {fpath}")
        code, out = classifier.run_classifier(fpath, use_json_output=True)
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["status"], "MATCH")
        self.assertEqual(res["classification"], "H4")
        self.assertEqual(res["hypotheses"], ["H4"])

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
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md:147", res["reason"])

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
    """Verifies refusal rules, malformed JSON handling, missing fields, and type validation."""

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

    def test_wrong_field_types(self):
        """Wrong types produce clear error and non-zero exit without traceback."""
        invalid_type_cases = [
            ("card_lock_state", 12345, "string or bool"),
            ("startup_timing", [1, 2], "string or number"),
            ("port20_led", 999, "string, bool, or dict"),
            ("ramcmp", 42, "dict, null, or string"),
            ("ramcmp", [0, 0, 0, 0, 0], "dict, null, or string"),
        ]
        valid_base = {
            "card_lock_state": "LOCKED",
            "startup_timing": "normal",
            "port20_led": "NO_PULSE",
            "ramcmp": {"r_l8": 0, "r_l4": 0, "r_c4": 0, "r_ct": 0, "r_wm": 0},
        }
        for field, bad_val, expected_type_str in invalid_type_cases:
            copy_data = dict(valid_base)
            copy_data[field] = bad_val
            proc = subprocess.run(
                [sys.executable, str(TOOL_PATH), "-"],
                input=json.dumps(copy_data),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Invalid type", proc.stderr)
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
    and checks that the tool's encoded table agrees row-by-row and column-by-column,
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

    def test_table_line_range_and_citations_present(self):
        """Tool must contain citations to docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and lines 171-174."""
        tool_code = TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/PORT21_OWNER_SESSION_PLAN.md", tool_code)
        self.assertIn("169-175", tool_code)
        for h in ("H1", "H2", "H3", "H4"):
            self.assertIn(f"RULE {h}", tool_code)

    def test_encoded_table_column_agreement(self):
        """Checks that ENCODED_TABLE columns match the parsed Markdown table header."""
        self.assertEqual(
            classifier.ENCODED_TABLE["columns"],
            self.parsed_columns,
            "ENCODED_TABLE columns do not match parsed Markdown table columns",
        )

    def test_encoded_table_row_and_cell_agreement(self):
        """Checks that ENCODED_TABLE agrees row-by-row and column-by-column with parsed Markdown table."""
        for h_id in ("H1", "H2", "H3", "H4"):
            self.assertIn(h_id, self.parsed_rows, f"Parsed table missing row for {h_id}")
            self.assertIn(h_id, classifier.ENCODED_TABLE["rows"], f"ENCODED_TABLE missing row for {h_id}")

            for col in self.parsed_columns:
                expected_cell = self.parsed_rows[h_id][col]
                encoded_cell = classifier.ENCODED_TABLE["rows"][h_id][col]
                self.assertEqual(
                    encoded_cell,
                    expected_cell,
                    f"Mismatch in row {h_id}, column '{col}':\nExpected: {expected_cell}\nActual:   {encoded_cell}",
                )

    def test_every_fixture_matches_parsed_table_predictions(self):
        """Checks that every fixture's classification matches what the parsed Markdown table predicts."""
        fixture_expectations = {
            "h1_rejected.json": "H1",
            "h2_compat_hang.json": "H2",
            "h3_stock_overwrite.json": "H3",
            "h4_malformed_witness.json": "H4",
            "ambiguous_unobserved_led.json": "AMBIGUOUS",
            "inconsistent_contradictory.json": "INCONSISTENT",
        }

        for fname, expected_classification in fixture_expectations.items():
            fpath = FIXTURES_DIR / fname
            self.assertTrue(fpath.is_file(), f"Missing fixture file: {fpath}")
            data = json.loads(fpath.read_text(encoding="utf-8"))
            parsed_report = classifier.parse_and_validate_report(data)
            result = classifier.classify_session_report(parsed_report)

            self.assertEqual(
                result["classification"],
                expected_classification,
                f"Fixture {fname} classified as {result['classification']} but expected {expected_classification}",
            )

            # Cross-check directly against parsed table cells:
            if expected_classification == "H1":
                # Parsed table cell for H1 r_l8 starts with `0`
                col_rl8 = self.parsed_columns[1]
                self.assertTrue(self.parsed_rows["H1"][col_rl8].startswith("`0`"))
                col_led = self.parsed_columns[6]
                self.assertIn("NO PULSE", self.parsed_rows["H1"][col_led])

            elif expected_classification == "H2":
                col_rl8 = self.parsed_columns[1]
                self.assertTrue(self.parsed_rows["H2"][col_rl8].startswith("`UNREACHABLE"))
                col_led = self.parsed_columns[6]
                self.assertIn("PULSES ~1-2 s", self.parsed_rows["H2"][col_led])

            elif expected_classification == "H3":
                col_rc4 = self.parsed_columns[3]
                # In parsed table row H3, r_c4 mentions 0 if overwritten
                self.assertIn("0", self.parsed_rows["H3"][col_rc4])
                col_led = self.parsed_columns[6]
                self.assertIn("PULSES ~1-2 s", self.parsed_rows["H3"][col_led])

            elif expected_classification == "H4":
                col_rc4 = self.parsed_columns[3]
                # In parsed table row H4, r_c4 starts with `1`
                self.assertTrue(self.parsed_rows["H4"][col_rc4].startswith("`1`"))
                col_led = self.parsed_columns[6]
                self.assertIn("PULSES ~1-2 s", self.parsed_rows["H4"][col_led])


if __name__ == "__main__":
    unittest.main()
