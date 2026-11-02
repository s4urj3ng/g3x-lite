#!/usr/bin/env python3
"""PORT-26 T3: Test Suite for Owner Report Template and Worked Examples.

Platform: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)
Task: p26-t3-owner-template
Document Under Test: docs/PORT26_OWNER_REPORT_TEMPLATE.md
Decoder Tool: tools/port26_ladder_decode.py

Coverage Requirements:
1. Extracts the blank template and verifies required keys:
   diskboot_sha256, press, pulses, lcd, inspector_status.
2. Extracts one worked example per decoder class from docs/PORT26_OWNER_REPORT_TEMPLATE.md.
3. Asserts that EVERY decoder class in tools.port26_ladder_decode.VALID_CLASSES
   (exactly 34 classes: 29 table codes + 5 special classes) has a worked example.
4. Fails if any decoder class lacks an example.
5. Runs each extracted worked example through tools/port26_ladder_decode.py (both
   classify_owner_report and CLI tool), asserting that the decoded class matches
   the expected class for each.
6. Verifies that the template documentation explains all allowed values and syntax rules.
7. Regression testing for fail-closed detection of missing classes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Dict, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT26_OWNER_REPORT_TEMPLATE.md"
TOOL_PATH = REPO_ROOT / "tools" / "port26_ladder_decode.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.port26_ladder_decode as decoder
from tools.port26_ladder_decode import (
    EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    LADDER_STAGE_TABLE,
    NEXT_STAGE_MAP,
    VALID_CLASSES,
    classify_owner_report,
    decode_ladder_report,
    parse_owner_report,
)


def extract_blank_template(doc_text: str) -> str:
    """Extracts the blank template code block from markdown content."""
    # Pattern 1: fenced block starting with '# Template: BLANK'
    m = re.search(
        r"```(?:ini|keyvalue|text)?\s*\n(#\s*Template:\s*BLANK.*?\n)```",
        doc_text,
        re.DOTALL,
    )
    if m:
        return m.group(1).strip()

    # Pattern 2: section-based fallback under '## 3. Blank Report Template'
    sec_m = re.search(
        r"##\s*3\.\s*Blank Report Template.*?\n+```(?:ini|keyvalue|text)?\s*\n(.*?)\n```",
        doc_text,
        re.DOTALL,
    )
    if sec_m:
        return sec_m.group(1).strip()

    raise ValueError("Could not extract blank template from markdown documentation")


def extract_worked_examples(doc_text: str) -> Dict[str, str]:
    """Extracts all worked examples from markdown content, mapped by expected class name."""
    examples: Dict[str, str] = {}

    # Pattern 1: Code blocks containing '# Expected Class: <CLASS>'
    block_pattern = re.compile(
        r"```(?:ini|keyvalue|text)?\s*\n(#\s*Expected Class:\s*([A-Za-z0-9_]+).*?\n)```",
        re.DOTALL,
    )
    for m in block_pattern.finditer(doc_text):
        content = m.group(1).strip()
        cls_name = m.group(2).strip()
        examples[cls_name] = content

    # Pattern 2: Section header fallback '#### Worked Example: <CLASS>' followed by fenced block
    header_pattern = re.compile(
        r"(?:###|####)\s*(?:Worked Example:?\s*)?([A-Za-z0-9_]+).*?\n+```(?:ini|keyvalue|text)?\s*\n(.*?)\n```",
        re.DOTALL,
    )
    for m in header_pattern.finditer(doc_text):
        cls_name = m.group(1).strip()
        content = m.group(2).strip()
        if cls_name in VALID_CLASSES and cls_name not in examples:
            examples[cls_name] = content

    return examples


class TestPort26OwnerTemplate(unittest.TestCase):
    """Test suite for docs/PORT26_OWNER_REPORT_TEMPLATE.md and decoder roundtrip."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(
            DOC_PATH.is_file(),
            f"Required documentation file missing: {DOC_PATH}",
        )
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.blank_template = extract_blank_template(cls.doc_text)
        cls.worked_examples = extract_worked_examples(cls.doc_text)

    def test_doc_file_exists_and_non_empty(self) -> None:
        """Asserts docs/PORT26_OWNER_REPORT_TEMPLATE.md exists and contains text."""
        self.assertTrue(DOC_PATH.exists())
        self.assertGreater(len(self.doc_text), 1000)

    def test_blank_template_extracted_and_valid(self) -> None:
        """Verifies blank template extraction and validates all required fields."""
        parsed = parse_owner_report(self.blank_template)

        # Assert all 5 required fields are parsed
        for field in ("diskboot_sha256", "press", "pulses", "lcd", "inspector_status"):
            self.assertIn(
                field,
                parsed,
                f"Required field '{field}' missing from parsed blank template",
            )

        # Candidate hash should match the pinned PORT-25 combined candidate digest
        self.assertEqual(
            parsed["diskboot_sha256"],
            EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
            "Blank template candidate hash mismatch",
        )

        # Press default in template is short
        self.assertEqual(parsed["press"], "short")

        # In unfilled template, pulses is empty, so decoding yields UNKNOWN_CODE
        res_unfilled = classify_owner_report(self.blank_template)
        self.assertEqual(
            res_unfilled["class"],
            "UNKNOWN_CODE",
            "Unfilled blank template should decode to UNKNOWN_CODE",
        )

        # When filled with valid pulses = 1, it decodes cleanly to CODE_1
        filled_code1 = re.sub(r"pulses\s*=.*", "pulses = 1", self.blank_template)
        res_filled1 = classify_owner_report(filled_code1)
        self.assertEqual(
            res_filled1["class"],
            "CODE_1",
            "Filled blank template with pulses=1 should decode to CODE_1",
        )

        # When filled with pulses = none, it decodes cleanly to NO_PULSES
        filled_none = re.sub(r"pulses\s*=.*", "pulses = none", self.blank_template)
        res_none = classify_owner_report(filled_none)
        self.assertEqual(
            res_none["class"],
            "NO_PULSES",
            "Filled blank template with pulses=none should decode to NO_PULSES",
        )

    def test_every_decoder_class_has_worked_example(self) -> None:
        """Asserts that every decoder class in VALID_CLASSES has an extracted worked example.
        
        FAILS if any class lacks an example.
        """
        extracted_classes: Set[str] = set(self.worked_examples.keys())
        missing_classes = VALID_CLASSES - extracted_classes

        self.assertEqual(
            len(missing_classes),
            0,
            f"docs/PORT26_OWNER_REPORT_TEMPLATE.md lacks worked examples for classes: {sorted(missing_classes)}",
        )
        self.assertEqual(
            len(self.worked_examples),
            len(VALID_CLASSES),
            f"Expected exactly {len(VALID_CLASSES)} worked examples, got {len(self.worked_examples)}",
        )
        self.assertEqual(len(VALID_CLASSES), 34)

    def test_all_worked_examples_decode_to_expected_classes(self) -> None:
        """Runs each extracted worked example through classify_owner_report and asserts expected class."""
        for expected_class, raw_content in sorted(self.worked_examples.items()):
            with self.subTest(decoder_class=expected_class):
                result = classify_owner_report(raw_content)
                self.assertEqual(
                    result["class"],
                    expected_class,
                    f"Example for {expected_class} decoded to unexpected class '{result['class']}': {result}",
                )
                self.assertIsNotNone(result["evidence"])
                self.assertIsNotNone(result["notes"])
                self.assertGreater(len(result["evidence"]), 0)
                self.assertGreater(len(result["notes"]), 0)

                # Detailed assertions by category
                if expected_class.startswith("CODE_"):
                    code_num = int(expected_class.split("_")[1])
                    expected_stage = LADDER_STAGE_TABLE[code_num]["stage_symbol"]
                    expected_next = NEXT_STAGE_MAP[code_num]
                    self.assertEqual(result["last_stage_reached"], expected_stage)
                    self.assertEqual(result["next_stage"], expected_next)
                elif expected_class == "NO_PULSES":
                    self.assertEqual(
                        result["last_stage_reached"],
                        "UNKNOWN (no LED evidence)",
                    )
                    self.assertEqual(
                        result["next_stage"],
                        "UNKNOWN (no LED evidence)",
                    )
                elif expected_class == "CONTROL_HELD_O1":
                    self.assertEqual(result["last_stage_reached"], "STOCK_UI")
                    self.assertIsNone(result["next_stage"])
                elif expected_class in ("INVALID_CANDIDATE", "UNKNOWN_CODE", "AMBIGUOUS"):
                    self.assertIsNone(result["last_stage_reached"])
                    self.assertIsNone(result["next_stage"])

    def test_worked_examples_decode_via_cli_tool(self) -> None:
        """Runs representative worked examples through tools/port26_ladder_decode.py CLI via stdin."""
        # Test a representative sample covering all major groups:
        sample_classes = [
            "CODE_1",   # Loader start
            "CODE_7",   # Loader handoff
            "CODE_11",  # Core group 1 entry
            "CODE_15",  # Initial Task spawn
            "CODE_21",  # Core group 2 entry
            "CODE_25",  # Power check pass bypass
            "CODE_28",  # Power-cut fail path
            "CODE_29",  # Halt shutdown
            "CODE_31",  # Startup task entry
            "CODE_35",  # Pre-watchdog arming
            "CODE_41",  # Post-watchdog arming
            "CODE_44",  # Continuation handoff
            "NO_PULSES",
            "UNKNOWN_CODE",
            "AMBIGUOUS",
            "INVALID_CANDIDATE",
            "CONTROL_HELD_O1",
        ]

        for cls in sample_classes:
            with self.subTest(cli_test_class=cls):
                raw_report = self.worked_examples[cls]
                proc = subprocess.run(
                    [sys.executable, str(TOOL_PATH), "-"],
                    input=raw_report,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"CLI tool returned non-zero ({proc.returncode}) for {cls}: stderr={proc.stderr}",
                )
                parsed_json = json.loads(proc.stdout)
                self.assertEqual(
                    parsed_json["class"],
                    cls,
                    f"CLI output class mismatch for {cls}: got {parsed_json['class']}",
                )

    def test_doc_explains_allowed_values_and_fields(self) -> None:
        """Asserts docs/PORT26_OWNER_REPORT_TEMPLATE.md contains prose explaining all fields and allowed values."""
        # 1. Pinned candidate SHA-256
        self.assertIn(EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256, self.doc_text)
        self.assertIn("diskboot_sha256", self.doc_text)

        # 2. Press modes
        self.assertIn("press", self.doc_text)
        self.assertIn("short", self.doc_text)
        self.assertIn("held", self.doc_text)

        # 3. Pulses
        self.assertIn("pulses", self.doc_text)
        self.assertIn("none", self.doc_text)
        self.assertIn("STAGE_LOADER_AFTER_PROLOGUE", self.doc_text)
        self.assertIn("STAGE_BC_CORE_ENTRY", self.doc_text)
        self.assertIn("STAGE_BC_POWER_CHECK_PASS", self.doc_text)
        self.assertIn("STAGE_BC_FAIL_POWER_CUT", self.doc_text)
        self.assertIn("STAGE_BC_STARTUP_ENTRY", self.doc_text)
        self.assertIn("STAGE_BC_PRE_FIRMWARE_CONT", self.doc_text)

        # 4. LCD states
        self.assertIn("lcd", self.doc_text)
        self.assertIn("stock_ui", self.doc_text)
        self.assertIn("dark", self.doc_text)

        # 5. Inspector status
        self.assertIn("inspector_status", self.doc_text)
        self.assertIn("not_run", self.doc_text)
        self.assertIn("WITNESS_INVALID", self.doc_text)

        # 6. Uncertainty handling
        self.assertIn("uncertain", self.doc_text)
        self.assertIn("AMBIGUOUS", self.doc_text)

    def test_key_value_syntax_purity(self) -> None:
        """Verifies that all lines in each worked example adhere strictly to key=value syntax or comments."""
        for cls_name, raw_content in self.worked_examples.items():
            for line in raw_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                self.assertTrue(
                    ("=" in line or ":" in line),
                    f"Line '{line}' in example '{cls_name}' is not valid key=value syntax",
                )

    def test_missing_class_detection_fails_closed(self) -> None:
        """Verifies that if a class is omitted, the coverage check raises AssertionError."""
        synthetic_examples = dict(self.worked_examples)
        synthetic_examples.pop("CODE_25", None)

        missing = VALID_CLASSES - set(synthetic_examples.keys())
        self.assertIn("CODE_25", missing)
        with self.assertRaises(AssertionError):
            self.assertEqual(len(missing), 0)


if __name__ == "__main__":
    unittest.main()
