#!/usr/bin/env python3
"""Unit tests for PORT-24 T4 (r2): Owner session plan to localise the failure in one or two power-ons.

Verifies:
1. docs/PORT24_SESSION_PLAN.md exists and is substantive.
2. The cited candidate SHA-256 matches the one parsed from docs/PORT24_BREADCRUMB_LADDER.md (no hardcoding).
3. Every ladder code parsed from docs/PORT24_BREADCRUMB_LADDER.md appears in the decode table.
4. The exact card setup values (LOCKED, FAT32, BOOTDISK 0x1E0, SCRIPT 0x1F0) are present.
5. The plan specifies at most two power-ons (Power-On 1 and Power-On 2, no Power-On 3).
6. Power button handling (hold vs short press) explicitly accounts for the O1 result and boot_prototype.c:350.
7. StartDiskboot-skip cues from T2 are documented.
8. Recovery procedures (card unlock/removal, long-press/repeated press, capacitor discharge / PMIC reset) are present.
9. Machine-readable report template for the owner is present.
10. Strict line-by-line / row-by-row evidence label and citation validation:
    every claim line and every decode-table row must carry a VERIFIED, INFERRED, or UNKNOWN
    label and an exact citation (a file path plus :line or a § section).
    Allowed exceptions: headings, table header and separator rows, and the report-template code block.
11. Tightened flash-count check: requires a decode-table row for each count from 0 to 7 and an ambiguous/uncertain-count row.
12. Scope compliance: only allowed paths are modified.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_SESSION_PLAN = REPO_ROOT / "docs" / "PORT24_SESSION_PLAN.md"
DOCS_LADDER = REPO_ROOT / "docs" / "PORT24_BREADCRUMB_LADDER.md"
DOCS_LOADER_TRACE = REPO_ROOT / "docs" / "PORT24_LOADER_TRACE.md"


def parse_ladder_sha256(ladder_doc_path: Path) -> str:
    """Parse the ladder candidate DISKBOOT.BIN SHA-256 from docs/PORT24_BREADCRUMB_LADDER.md."""
    content = ladder_doc_path.read_text(encoding="utf-8")
    # Search table in section 8.2 or text in section 1
    m = re.search(
        r"\|\s*\*\*`?DISKBOOT\.BIN`?\*\*\s*\|\s*`?118,257`?\s*\|\s*`?([0-9a-f]{64})`?",
        content,
    )
    if m:
        return m.group(1).lower()
    m2 = re.search(r"DISKBOOT\.BIN SHA-256 `([0-9a-f]{64})`", content)
    if m2:
        return m2.group(1).lower()
    raise ValueError(f"Could not parse ladder DISKBOOT.BIN SHA-256 from {ladder_doc_path}")


def parse_ladder_codes(ladder_doc_path: Path) -> list[str]:
    """Parse the list of ladder step codes from docs/PORT24_BREADCRUMB_LADDER.md."""
    content = ladder_doc_path.read_text(encoding="utf-8")
    # Matches codes from the table in Section 7.1: | 1 | `after_prologue` | ...
    codes = re.findall(r"\|\s*\d+\s*\|\s*`([a-z_]+)`\s*\|\s*Step", content)
    if not codes:
        # Fallback to headings: ### Step 1: `after_prologue`
        codes = re.findall(r"###\s+Step\s+\d+:\s+`([a-z_]+)`", content)
    if not codes:
        raise ValueError(f"Could not parse ladder codes from {ladder_doc_path}")
    return codes


class TestPort24SessionPlan(unittest.TestCase):
    """Test suite validating docs/PORT24_SESSION_PLAN.md against all acceptance criteria and reviewer feedback."""

    @classmethod
    def setUpClass(cls):
        if not DOCS_SESSION_PLAN.is_file():
            raise AssertionError(f"Required document does not exist: {DOCS_SESSION_PLAN}")
        if not DOCS_LADDER.is_file():
            raise AssertionError(f"Prerequisite document does not exist: {DOCS_LADDER}")
        if not DOCS_LOADER_TRACE.is_file():
            raise AssertionError(f"Prerequisite document does not exist: {DOCS_LOADER_TRACE}")

        cls.content = DOCS_SESSION_PLAN.read_text(encoding="utf-8")
        cls.ladder_sha256 = parse_ladder_sha256(DOCS_LADDER)
        cls.ladder_codes = parse_ladder_codes(DOCS_LADDER)

    def test_file_exists_and_substantive(self):
        """Verify the session plan exists and has substantive length (>3000 chars)."""
        self.assertTrue(DOCS_SESSION_PLAN.is_file())
        self.assertGreater(len(self.content), 3000)

    def test_prerequisite_documents_exist_and_verified(self):
        """Verify that prerequisite documents exist on base without making up data."""
        self.assertTrue(DOCS_LADDER.is_file(), "docs/PORT24_BREADCRUMB_LADDER.md must exist")
        loader_trace = DOCS_LOADER_TRACE.read_text(encoding="utf-8")
        self.assertIn("## Restart path", loader_trace, "docs/PORT24_LOADER_TRACE.md must have '## Restart path'")

    def test_cited_sha256_matches_ladder_doc(self):
        """Verify the cited ladder candidate SHA-256 matches the one parsed from the ladder doc."""
        self.assertIn(
            self.ladder_sha256,
            self.content.lower(),
            f"Parsed ladder SHA-256 {self.ladder_sha256} must appear in PORT24_SESSION_PLAN.md",
        )

    def test_exact_card_setup_present(self):
        """Verify exact card setup parameters matching owner sessions are documented."""
        # Check locked write-protect switch
        self.assertTrue(
            re.search(r"\bLOCKED\b", self.content, re.IGNORECASE),
            "Card setup must specify LOCKED write-protect switch",
        )
        # Check FAT32
        self.assertIn("FAT32", self.content, "Card setup must specify FAT32 filesystem")
        # Check BOOTDISK 0x1E0
        self.assertTrue(
            re.search(r"BOOTDISK.*0x1E0", self.content, re.IGNORECASE) or
            re.search(r"0x1E0.*BOOTDISK", self.content, re.IGNORECASE),
            "Card setup must specify BOOTDISK marker at offset 0x1E0",
        )
        # Check SCRIPT 0x1F0
        self.assertTrue(
            re.search(r"SCRIPT.*0x1F0", self.content, re.IGNORECASE) or
            re.search(r"0x1F0.*SCRIPT", self.content, re.IGNORECASE),
            "Card setup must specify SCRIPT marker at offset 0x1F0",
        )

    def test_at_most_two_power_ons_in_plan(self):
        """Verify the execution plan specifies at most two power-ons."""
        self.assertIn("Power-On 1", self.content)
        self.assertIn("Power-On 2", self.content)
        # Ensure there is no Power-On 3
        self.assertNotIn("Power-On 3", self.content)

    def test_power_button_handling_and_o1_result(self):
        """Verify explicit guidance on hold vs short press accounting for the O1 result and boot_prototype.c:350."""
        self.assertIn("O1", self.content)
        self.assertIn("sub_fc1284ac", self.content)
        self.assertTrue("boot_prototype.c:350" in self.content or "boot_prototype.c:352" in self.content)
        self.assertIn("sub_fc05ba56", self.content)
        self.assertIn("GPIO 0x67", self.content)
        # Ensure hold vs short press is explicitly discussed
        self.assertTrue(re.search(r"short press|brief tap", self.content, re.IGNORECASE))
        self.assertTrue(re.search(r"held press|continuous hold|long press", self.content, re.IGNORECASE))

    def test_decode_table_contains_all_ladder_codes(self):
        """Verify that every ladder code parsed from docs/PORT24_BREADCRUMB_LADDER.md appears in the decode table."""
        self.assertGreaterEqual(len(self.ladder_codes), 7, "Ladder doc must define at least 7 ladder codes")

        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        for code in self.ladder_codes:
            self.assertIn(
                code,
                table_text,
                f"Ladder code '{code}' parsed from docs/PORT24_BREADCRUMB_LADDER.md must appear in the decode table",
            )

    def test_decode_table_flash_counts_and_ambiguous(self):
        """Tightened check: verify that decode table has a dedicated row for each count 0-7 and an ambiguous row."""
        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        # Check explicit decode table row for each count from 0 to 7
        for count in range(8):
            row_pattern = rf"\|\s*\*\*?{count}\*\*?\s*\|"
            self.assertTrue(
                re.search(row_pattern, table_text),
                f"Decode table must contain a dedicated row for flash count {count}",
            )

        # Check explicit ambiguous or uncertain count row
        ambiguous_pattern = r"\|\s*\*\*?(?:Truncated|Merged|Uncertain|Ambiguous)"
        self.assertTrue(
            re.search(ambiguous_pattern, table_text, re.IGNORECASE),
            "Decode table must contain a row for truncated, merged, or ambiguous/uncertain counts",
        )

        # Check T1 ranking mention (Rank 1, Rank 2, etc.)
        self.assertTrue(re.search(r"T1.*Rank\s*1", table_text, re.IGNORECASE))

    def test_startdiskboot_skip_cues_from_t2(self):
        """Verify explanation of physical cues from T2 indicating whether StartDiskboot was skipped."""
        self.assertTrue(
            re.search(r"## 4\..*?StartDiskboot", self.content, re.IGNORECASE),
            "Section 4 StartDiskboot-skip cues must exist",
        )
        self.assertIn("0xFC05BC34", self.content, "Clean return address 0xFC05BC34 must be cited")
        self.assertIn("task_Startup", self.content)
        self.assertTrue("stale" in self.content.lower() or "freshness" in self.content.lower())

    def test_recovery_procedure_present_and_labelled(self):
        """Verify recovery procedures for restoring stock UI are documented with evidence labels."""
        self.assertTrue(
            re.search(r"## 5\..*?Recovery", self.content, re.IGNORECASE),
            "Section 5 Recovery procedures must exist",
        )
        self.assertTrue(re.search(r"UNLOCKED|remove", self.content, re.IGNORECASE))
        self.assertTrue(re.search(r"battery.*pull|capacitor discharge", self.content, re.IGNORECASE))

    def test_report_template_present(self):
        """Verify short report template for the owner is present."""
        self.assertTrue(
            re.search(r"## 6\..*?Report", self.content, re.IGNORECASE),
            "Section 6 Report template must exist",
        )
        self.assertIn("Power-On 1", self.content)
        self.assertIn("Flashes Observed", self.content)
        # Template should include fields for truncated, merged, or ambiguous sequence
        self.assertTrue(re.search(r"Truncated|Merged|Uncertain|Ambiguous", self.content))

    def test_claims_and_rows_labelled_and_cited(self):
        """Verify that every claim line and decode-table row carries an evidence label and exact citation.

        Allowed exceptions: headings, table header and separator rows, and the report-template code block.
        Each non-excepted line must contain:
        - A label: VERIFIED, INFERRED, or UNKNOWN
        - An exact citation: a file path plus :line or a § section.
        """
        lines = self.content.splitlines()
        in_report_template = False
        non_compliant_lines: list[tuple[int, str]] = []

        label_regex = re.compile(r"\[(VERIFIED|INFERRED|UNKNOWN)")
        citation_regex = re.compile(r"(?:[\w\.\-/]+\.[a-zA-Z0-9]+:(?:\d+|0x[0-9a-fA-F]+)|§\s*\d+)")

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Skip empty lines and markdown horizontal rules
            if not stripped or stripped == "---":
                continue

            # Track fenced code blocks (report template)
            if stripped.startswith("```"):
                if not in_report_template and "markdown" in stripped:
                    in_report_template = True
                    continue
                elif in_report_template:
                    in_report_template = False
                    continue

            # Allowed exception: inside report-template code block
            if in_report_template:
                continue

            # Allowed exception: Headings
            if stripped.startswith("#"):
                continue

            # Allowed exception: Table separator rows (e.g. | :---: | :--- | ...)
            if re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", stripped):
                continue

            # Allowed exception: Table header rows (detected when next non-empty line is a separator row)
            next_non_empty = ""
            for next_idx in range(idx, len(lines)):
                candidate = lines[next_idx].strip()
                if candidate:
                    next_non_empty = candidate
                    break
            if stripped.startswith("|") and re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", next_non_empty):
                continue

            # Every remaining line must be a claim line or table data row
            has_label = bool(label_regex.search(stripped))
            has_citation = bool(citation_regex.search(stripped))

            if not (has_label and has_citation):
                non_compliant_lines.append((idx, stripped))

        self.assertEqual(
            len(non_compliant_lines),
            0,
            f"Found {len(non_compliant_lines)} lines missing evidence label or exact citation:\n"
            + "\n".join(f"Line {n}: {text}" for n, text in non_compliant_lines[:15]),
        )

    def test_scope_compliance_git_status(self):
        """Verify that only allowed files are modified in the working tree."""
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        modified_files = []
        for line in res.stdout.splitlines():
            if line.strip():
                path = line[2:].lstrip()
                modified_files.append(path)

        allowed = {
            "docs/PORT24_SESSION_PLAN.md",
            "tests/test_port24_session_plan.py",
        }
        for path in modified_files:
            self.assertIn(
                path,
                allowed,
                f"File '{path}' is not in the list of allowed paths: {allowed}",
            )


if __name__ == "__main__":
    unittest.main()
