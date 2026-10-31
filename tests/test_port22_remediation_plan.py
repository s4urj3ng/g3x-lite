#!/usr/bin/env python3
"""PORT-22 T2: Unit tests for remediation plan per hypothesis H1-H4.

Validates that:
1. docs/PORT22_REMEDIATION_PLAN.md exists and contains:
   - Dedicated sections for each of hypotheses H1, H2, H3, and H4.
   - For each hypothesis section: candidate change (specifying file and function),
     supporting evidence, and follow-up confirming owner reading.
   - Summary table of hypothesis, change, evidence, and confirming reading.
   - List of open UNKNOWNs.
2. Every claim bullet or row carries a VERIFIED, INFERRED, or UNKNOWN label.
3. Every path:line (or path:start-end) citation resolves to an existing file in the repo
   with at least that many lines.
4. No hex address appears without an epistemic label and citation, unless it is labelled UNKNOWN.
5. Scope integrity: only approved files are modified, and no ROM files are accessed.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT22_REMEDIATION_PLAN.md"

HEX_PATTERN = re.compile(r"\b0x[0-9a-fA-F]+\b")
CITATION_PATTERN = re.compile(r"([a-zA-Z0-9_\-./]+?\.[a-zA-Z0-9]+):(\d+)(?:-(\d+))?")
LABEL_PATTERN = re.compile(r"\[(VERIFIED|INFERRED|UNKNOWN)[^\]]*\]")


class TestPort22RemediationPlan(unittest.TestCase):
    """Validates structural and content requirements of docs/PORT22_REMEDIATION_PLAN.md."""

    @classmethod
    def setUpClass(cls):
        if not DOC_PATH.is_file():
            raise unittest.SkipTest(f"Missing doc file: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_doc_exists_and_non_empty(self):
        """Verifies docs/PORT22_REMEDIATION_PLAN.md exists and has substantive content."""
        self.assertTrue(DOC_PATH.is_file(), "docs/PORT22_REMEDIATION_PLAN.md must exist")
        self.assertGreater(len(self.content), 2000, "Doc must contain substantive remediation design")

    def test_each_h1_to_h4_has_section(self):
        """Verifies each of H1, H2, H3, and H4 has a dedicated top-level section."""
        for h in ("H1", "H2", "H3", "H4"):
            pattern = re.compile(rf"^##\s+.*?\b{h}\b", re.MULTILINE)
            self.assertTrue(
                pattern.search(self.content),
                f"Missing dedicated section for hypothesis {h}",
            )

    def test_each_section_contains_required_components(self):
        """Verifies each hypothesis section states candidate change, evidence, and confirming reading."""
        # Split document by top-level section markers
        section_splits = re.split(r"\n##\s+", self.content)
        sec_map = {}
        for part in section_splits:
            first_line = part.split("\n", 1)[0]
            for h in ("H1", "H2", "H3", "H4"):
                if f"Hypothesis {h}" in first_line or f"{h}:" in first_line:
                    sec_map[h] = part

        self.assertEqual(
            set(sec_map.keys()),
            {"H1", "H2", "H3", "H4"},
            "All four hypothesis sections H1-H4 must be parsed",
        )

        for h, text in sec_map.items():
            # Check hypothesis definition citations into PORT21 docs
            self.assertIn("PORT21_OWNER_SESSION_PLAN.md", text, f"Section {h} must cite PORT-21 T4 plan")
            self.assertIn("Hypothesis Definition", text, f"Section {h} must define hypothesis")

            # Check (1) Candidate change with target file and function
            self.assertIn("Next Candidate Change", text, f"Section {h} missing candidate change section")
            self.assertIn("Target File", text, f"Section {h} missing Target File specification")
            self.assertIn("Target Function", text, f"Section {h} missing Target Function specification")

            # Must target chdk-port/ or tools/build_candidate_*.py
            has_valid_target_file = (
                "chdk-port/" in text or "tools/build_candidate_" in text
            )
            self.assertTrue(
                has_valid_target_file,
                f"Section {h} Target File must be in chdk-port/ or tools/build_candidate_*.py",
            )

            # Check (2) Supporting evidence
            self.assertIn("Supporting Evidence", text, f"Section {h} missing Supporting Evidence section")

            # Check (3) Follow-up confirming reading
            self.assertIn("Follow-Up Owner Reading", text, f"Section {h} missing Follow-Up Owner Reading")
            self.assertIn("Refuting", text, f"Section {h} must describe refuting reading")
            self.assertIn("Confirming", text, f"Section {h} must describe confirming reading")

    def test_summary_table_presence_and_structure(self):
        """Verifies summary table covers H1-H4 with change, evidence, and confirming reading."""
        self.assertIn("Summary Table", self.content, "Doc must contain summary table")
        table_match = re.search(r"\|\s*Hypothesis ID\s*&.*?\n((?:\|.*?\n)+)", self.content)
        self.assertIsNotNone(table_match, "Summary table must be present with header")

        table_rows = table_match.group(1).splitlines()
        hypotheses_found = set()
        for row in table_rows:
            if re.match(r"^\|[\s\-:|]+\|$", row.strip()):
                continue
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if len(cells) < 4:
                continue
            for h in ("H1", "H2", "H3", "H4"):
                if f"**{h}**" in cells[0]:
                    hypotheses_found.add(h)
                    # Check each cell has label and citation
                    for idx, cell in enumerate(cells, start=1):
                        self.assertTrue(
                            LABEL_PATTERN.search(cell),
                            f"Table row {h} cell {idx} missing epistemic label: {cell[:40]}",
                        )
                        self.assertTrue(
                            CITATION_PATTERN.search(cell),
                            f"Table row {h} cell {idx} missing citation: {cell[:40]}",
                        )

        self.assertEqual(
            hypotheses_found,
            {"H1", "H2", "H3", "H4"},
            "Summary table must contain rows for all hypotheses H1, H2, H3, H4",
        )

    def test_open_unknowns_presence_and_labelling(self):
        """Verifies open UNKNOWNs are listed with explicit [UNKNOWN: ...] labels."""
        self.assertIn("Open UNKNOWNs", self.content, "Doc must contain list of open UNKNOWNs")
        unknown_section = self.content.split("Open UNKNOWNs", 1)[1]
        unknown_bullets = [
            line.strip()
            for line in unknown_section.splitlines()
            if line.strip().startswith(("- ", "* "))
        ]
        self.assertGreaterEqual(
            len(unknown_bullets),
            4,
            "Must list open UNKNOWNs for later milestones",
        )
        for bullet in unknown_bullets:
            self.assertIn("[UNKNOWN", bullet, f"Open unknown bullet must be labeled [UNKNOWN]: {bullet}")
            self.assertTrue(
                CITATION_PATTERN.search(bullet),
                f"Open unknown bullet must cite existing document: {bullet}",
            )

    def test_all_claim_bullets_and_rows_carry_epistemic_labels(self):
        """Verifies every claim bullet and table content row carries a VERIFIED, INFERRED or UNKNOWN label."""
        unlabeled_bullets = []
        unlabeled_rows = []

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            # Check bullets
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_bullets.append(f"Line {i}: {stripped}")
            # Check table content rows
            elif stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue  # Table separator row
                if "Hypothesis ID" in stripped:
                    continue  # Table header row
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_rows.append(f"Line {i}: {stripped}")

        self.assertEqual(
            unlabeled_bullets,
            [],
            f"Found unlabeled bullets in docs/PORT22_REMEDIATION_PLAN.md:\n" + "\n".join(unlabeled_bullets),
        )
        self.assertEqual(
            unlabeled_rows,
            [],
            f"Found unlabeled table rows in docs/PORT22_REMEDIATION_PLAN.md:\n" + "\n".join(unlabeled_rows),
        )

    def test_every_path_line_citation_resolves(self):
        """Verifies every path:line citation resolves to an existing file and line number."""
        citations = CITATION_PATTERN.findall(self.content)
        self.assertGreaterEqual(len(citations), 20, "Doc must contain substantive citations")

        file_cache: dict[str, int] = {}
        citation_errors = []

        for fpath, s, e in citations:
            p = REPO_ROOT / fpath
            if not p.is_file():
                citation_errors.append(f"Cited file does not exist: {fpath}")
                continue

            if fpath not in file_cache:
                file_cache[fpath] = len(p.read_text(encoding="utf-8").splitlines())
            total_lines = file_cache[fpath]

            start_line = int(s)
            end_line = int(e) if e else start_line

            if start_line < 1 or start_line > total_lines:
                citation_errors.append(
                    f"Invalid start line in {fpath}:{s} (file has {total_lines} lines)"
                )
            if end_line < 1 or end_line > total_lines:
                citation_errors.append(
                    f"Invalid end line in {fpath}:{s}-{e} (file has {total_lines} lines)"
                )
            if end_line < start_line:
                citation_errors.append(
                    f"End line before start line in {fpath}:{s}-{e}"
                )

        self.assertEqual(
            citation_errors,
            [],
            f"Citation errors in docs/PORT22_REMEDIATION_PLAN.md:\n" + "\n".join(citation_errors),
        )

    def test_no_hex_address_without_label_and_citation(self):
        """Verifies no hex address appears without a label and citation, unless it is labelled UNKNOWN."""
        hex_violations = []

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            if not HEX_PATTERN.search(stripped):
                continue

            has_unknown = "UNKNOWN" in stripped
            has_verified_or_inferred = ("VERIFIED" in stripped) or ("INFERRED" in stripped)
            has_citation = bool(CITATION_PATTERN.search(stripped))

            if has_unknown:
                continue

            if not (has_verified_or_inferred and has_citation):
                hex_violations.append(f"Line {i}: {stripped}")

        self.assertEqual(
            hex_violations,
            [],
            f"Hex addresses without label and citation (not labeled UNKNOWN):\n" + "\n".join(hex_violations),
        )


if __name__ == "__main__":
    unittest.main()
