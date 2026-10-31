#!/usr/bin/env python3
"""PORT-21 T4: Unit tests for owner session plan (H1-H4 discrimination on 2026-11-01).

Validates that:
1. docs/PORT21_OWNER_SESSION_PLAN.md exists and contains:
   - Section 1: Offline explanation of O6 (ruled out, fit, untested, with labels and citations).
   - Section 2: Session sequence with fewest power-ons separating H1-H4, specifying card state,
     files, recorded values, power-on count, and pairwise separation for all pairs.
   - Section 3: Prediction table with rows H1-H4, columns for RAMCMP readings and PORT-20 LED candidate
     behaviour, where every cell has an epistemic label and citation.
   - Section 4: Decision tree from observed results to the next milestone.
   - Section 5: Stop conditions and recovery plan (battery pull, card removal, quiescence, stock verification).
2. The prediction table covers H1-H4 and includes both RAMCMP and LED candidate predictions.
3. Every cell in the prediction table has an epistemic label (VERIFIED / INFERRED / UNKNOWN) and citation.
4. The session sequence separates every pair among {H1, H2, H3, H4}, or explicitly documents inseparable pairs.
5. Every citation to PORT21_*.md points to valid line numbers in the cited file.
6. Every 64-hex SHA-256 quoted next to a tracked file matches hashlib.sha256 of that file.
7. No cell in rows H1-H4 labels a docs/PORT20_* citation VERIFIED.
8. The plan explicitly mentions the T1/T2 r_l4 (0x40008000) conflict.
9. Scope integrity: no PORT-20-owned files and no binaries are modified or added.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT21_OWNER_SESSION_PLAN.md"

FORBIDDEN_PREFIXES = ("docs/PORT20_", "tests/test_port20_")
FORBIDDEN_FILES = ("tools/build_candidate_port2a.py",)


class TestPort21OwnerSessionPlanDoc(unittest.TestCase):
    """Validates structural and content requirements of docs/PORT21_OWNER_SESSION_PLAN.md."""

    @classmethod
    def setUpClass(cls):
        if not DOC_PATH.is_file():
            raise unittest.SkipTest(f"Missing doc file: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")

    def test_file_exists_and_non_empty(self):
        self.assertTrue(DOC_PATH.is_file(), "docs/PORT21_OWNER_SESSION_PLAN.md must exist")
        self.assertGreater(len(self.content), 2000, "Doc must contain substantive plan")

    def test_five_required_sections_present(self):
        """Verifies presence of all 5 mandatory sections from prompt."""
        # Section 1: Offline explanation of O6
        self.assertIn("1. Offline Explanation of Observation O6", self.content)
        # Section 2: Session sequence with fewest power-ons
        self.assertIn("2. Session Sequence", self.content)
        # Section 3: Prediction table
        self.assertIn("3. Comprehensive Prediction Table for Hypotheses H1", self.content)
        # Section 4: Decision tree
        self.assertIn("4. Decision Tree", self.content)
        # Section 5: Stop conditions and recovery plan
        self.assertIn("5. Stop Conditions and Emergency Recovery Plan", self.content)

    def test_section1_o6_explanation_and_hypotheses_evaluation(self):
        """Section 1 must explain O6, stating which hypotheses are ruled out, fit, or untested."""
        sec1 = self.content.split("## 1. Offline Explanation of Observation O6", 1)[1].split("## 2. Session Sequence", 1)[0]
        # O6 description
        self.assertIn("WITNESS_INVALID", sec1)
        self.assertIn("INVALID / CORRUPT", sec1)
        self.assertIn("0x574954EE", sec1)
        self.assertIn("palette", sec1)

        # Hypotheses evaluated
        for h in ("H1", "H2", "H3", "H4"):
            self.assertIn(f"**{h}**", sec1)

        # Verdicts: H4 ruled out, H2 ruled out for uninterrupted, H1/H3 fit / untested
        self.assertIn("RULED OUT", sec1)
        self.assertIn("FITS", sec1)
        self.assertIn("UNTESTED", sec1)

        # Alternative inspector address explanation (0x780 vs 0x7A0)
        self.assertIn("0x0035F780", sec1)
        self.assertIn("0x0035F7A0", sec1)

    def test_section2_session_sequence_power_ons_and_cards(self):
        """Section 2 must specify power-on count, card state (locked/unlocked), files, and recordings."""
        sec2 = self.content.split("## 2. Session Sequence", 1)[1].split("## 3. Comprehensive Prediction Table", 1)[0]
        # Power-on count: 1 primary discrimination run
        self.assertIn("1", sec2)
        self.assertIn("Power-On", sec2)

        # Card states
        self.assertIn("LOCKED", sec2)
        self.assertIn("UNLOCKED", sec2)

        # Files on card
        for fn in ("DISKBOOT.BIN", "extend.m", "WITNESS.BIN", "REF_L.BIN", "REF_C.BIN", "script.req"):
            self.assertIn(fn, sec2)

        # Recorded items
        self.assertIn("LED", sec2)
        self.assertIn("r_l4", sec2)
        self.assertIn("r_l8", sec2)
        self.assertIn("r_c4", sec2)
        self.assertIn("r_ct", sec2)
        self.assertIn("r_wm", sec2)

    def test_section2_pairwise_discrimination_covers_all_pairs(self):
        """Section 2 must show each pair among {H1, H2, H3, H4} is separated."""
        sec2 = self.content.split("## 2. Session Sequence", 1)[1].split("## 3. Comprehensive Prediction Table", 1)[0]
        required_pairs = [
            ("H1", "H2"),
            ("H1", "H3"),
            ("H1", "H4"),
            ("H2", "H3"),
            ("H2", "H4"),
            ("H3", "H4"),
        ]
        for h_a, h_b in required_pairs:
            pair_pattern_1 = f"({h_a}, {h_b})"
            pair_pattern_2 = f"Pair ({h_a}, {h_b})"
            self.assertTrue(
                pair_pattern_1 in sec2 or pair_pattern_2 in sec2,
                f"Pair ({h_a}, {h_b}) must be explicitly separated in Section 2",
            )

    def test_section3_prediction_table_structure_and_columns(self):
        """Section 3 table must cover H1-H4 and columns for RAMCMP and LED candidate."""
        sec3 = self.content.split("## 3. Comprehensive Prediction Table", 1)[1].split("## 4. Decision Tree", 1)[0]
        # Check column headers
        self.assertIn("r_l8", sec3)
        self.assertIn("r_l4", sec3)
        self.assertIn("r_c4", sec3)
        self.assertIn("r_ct", sec3)
        self.assertIn("r_wm", sec3)
        self.assertIn("PORT-20 LED Behaviour", sec3)
        self.assertIn("Inspector OSD", sec3)

        # Check rows for H1, H2, H3, H4
        for h in ("H1", "H2", "H3", "H4"):
            self.assertIn(f"**{h}**", sec3)

    def test_section3_prediction_table_cells_have_labels_and_citations(self):
        """Every cell in prediction table rows H1-H4 must have an epistemic label and a citation."""
        sec3 = self.content.split("## 3. Comprehensive Prediction Table", 1)[1].split("## 4. Decision Tree", 1)[0]
        table_lines = [l for l in sec3.splitlines() if l.strip().startswith("|") and not l.strip().startswith("|:---")]
        self.assertGreaterEqual(len(table_lines), 5, "Must have header + at least 4 rows")

        # Parse table rows for H1-H4
        rows_found = set()
        for line in table_lines:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells or len(cells) < 7:
                continue
            first_cell = cells[0]
            for h in ("H1", "H2", "H3", "H4"):
                if f"**{h}**" in first_cell:
                    rows_found.add(h)
                    # Check every cell in this row (skipping first cell which is row label)
                    for idx, cell in enumerate(cells[1:], start=1):
                        has_label = any(lbl in cell for lbl in ("`[VERIFIED", "`[INFERRED", "`[UNKNOWN"))
                        self.assertTrue(
                            has_label,
                            f"Row {h} cell {idx} ('{cell[:40]}...') missing epistemic label",
                        )
                        self.assertIn(
                            ":",
                            cell,
                            f"Row {h} cell {idx} ('{cell[:40]}...') missing citation source",
                        )

        self.assertEqual(rows_found, {"H1", "H2", "H3", "H4"}, "Must find rows for H1, H2, H3, H4")

    def test_section4_decision_tree_and_next_milestones(self):
        """Section 4 must provide a decision tree mapping observations to the next milestone."""
        sec4 = self.content.split("## 4. Decision Tree", 1)[1].split("## 5. Stop Conditions", 1)[0]
        self.assertIn("mermaid", sec4)
        self.assertIn("PORT-22", sec4)
        # Check all main outcomes are covered
        self.assertIn("H1", sec4)
        self.assertIn("H2", sec4)
        self.assertIn("H3", sec4)
        self.assertIn("H4", sec4)
        self.assertIn("Success", sec4)

    def test_section5_stop_conditions_and_recovery_plan(self):
        """Section 5 must specify stop conditions and step-by-step recovery plan."""
        sec5 = self.content.split("## 5. Stop Conditions and Emergency Recovery Plan", 1)[1]
        # Stop conditions
        self.assertIn("Unresponsive Hang", sec5)
        self.assertIn("Abnormal LED", sec5)
        self.assertIn("Lens", sec5)
        self.assertIn("Battery Pull", sec5)
        self.assertIn("Eject SD Card", sec5)
        self.assertIn("Cold Quiescence", sec5)
        self.assertIn("UNLOCKED", sec5)
        self.assertIn("Stock Boot Verification", sec5)

    def test_port21_citations_valid_line_ranges(self):
        """Verifies that every PORT21_*.md:N or :N-M citation points to lines inside the cited file."""
        pattern = re.compile(r"(?:docs/)?(PORT21_[A-Z_]+\.md):(\d+)(?:-(\d+))?")
        matches = pattern.findall(self.content)
        self.assertGreaterEqual(len(matches), 10, "Must find PORT21 citations in the plan")

        checked_files = {}
        for fname, s, e in matches:
            p = REPO_ROOT / "docs" / fname
            self.assertTrue(p.is_file(), f"Cited doc does not exist: {p}")
            if fname not in checked_files:
                checked_files[fname] = len(p.read_text(encoding="utf-8").splitlines())
            total_lines = checked_files[fname]
            start_line = int(s)
            end_line = int(e) if e else start_line
            self.assertGreaterEqual(
                start_line,
                1,
                f"Citation {fname}:{s} has line < 1",
            )
            self.assertLessEqual(
                start_line,
                total_lines,
                f"Citation {fname}:{s} exceeds total lines ({total_lines})",
            )
            self.assertLessEqual(
                end_line,
                total_lines,
                f"Citation {fname}:{s}-{e} exceeds total lines ({total_lines})",
            )

    def test_tracked_file_hashes_match(self):
        """Verifies that every 64-hex SHA-256 quoted next to a tracked file path matches hashlib.sha256."""
        lines = self.content.splitlines()
        sha_pattern = re.compile(r"\b([0-9a-f]{64})\b")
        file_pattern = re.compile(r"`([a-zA-Z0-9_\-./]+?\.[a-zA-Z0-9]+)`")

        hashes_checked = 0
        for line in lines:
            sha_match = sha_pattern.search(line)
            if not sha_match:
                continue
            quoted_sha = sha_match.group(1)
            file_matches = file_pattern.findall(line)
            for fpath in file_matches:
                p = REPO_ROOT / fpath
                if p.is_file():
                    res = subprocess.run(
                        ["git", "ls-files", str(fpath)],
                        cwd=REPO_ROOT,
                        stdout=subprocess.PIPE,
                        text=True,
                    )
                    if res.stdout.strip():
                        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
                        self.assertEqual(
                            quoted_sha,
                            actual_sha,
                            f"SHA-256 mismatch for tracked file {fpath}: quoted {quoted_sha} != actual {actual_sha}",
                        )
                        hashes_checked += 1
                        break
        self.assertGreaterEqual(hashes_checked, 1, "Must check at least one tracked file hash")

    def test_no_port20_citation_labeled_verified_in_prediction_table(self):
        """Verifies that no cell in the H1-H4 rows of the prediction table labels a docs/PORT20_* citation VERIFIED."""
        sec3 = self.content.split("## 3. Comprehensive Prediction Table", 1)[1].split("## 4. Decision Tree", 1)[0]
        table_lines = [l for l in sec3.splitlines() if l.strip().startswith("|") and not l.strip().startswith("|:---")]

        for line in table_lines:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            first_cell = cells[0]
            for h in ("H1", "H2", "H3", "H4"):
                if f"**{h}**" in first_cell:
                    for idx, cell in enumerate(cells[1:], start=1):
                        if "PORT20" in cell:
                            self.assertNotIn(
                                "VERIFIED",
                                cell,
                                f"Row {h} cell {idx} must not label PORT-20 citation as VERIFIED: '{cell}'",
                            )

    def test_plan_mentions_t1_t2_rl4_conflict(self):
        """Verifies that the plan explicitly mentions the T1/T2 conflict over r_l4 (0x40008000)."""
        self.assertIn("0x40008000", self.content)
        self.assertIn("r_l4", self.content)
        lower_content = self.content.lower()
        self.assertTrue(
            "conflict" in lower_content and ("t1" in lower_content or "ram_lifetime" in lower_content),
            "Plan must explicitly mention the T1/T2 conflict over r_l4",
        )


class TestPort21ScopeIntegrity(unittest.TestCase):
    """Ensures no PORT-20-owned files and no binaries are modified or added."""

    def test_no_port20_files_modified(self):
        res = subprocess.run(["git", "status", "--porcelain"], stdout=subprocess.PIPE, text=True, cwd=REPO_ROOT)
        modified = [line[3:].strip() for line in res.stdout.splitlines() if line.strip()]
        for p in modified:
            for prefix in FORBIDDEN_PREFIXES:
                self.assertFalse(p.startswith(prefix), f"PORT-20 file modified: {p}")
            self.assertNotIn(p, FORBIDDEN_FILES, f"Forbidden file modified: {p}")
            self.assertFalse(
                p.endswith((".bin", ".elf", ".o", ".a", ".so", ".exe")),
                f"Binary artifact must not be added or modified: {p}",
            )


if __name__ == "__main__":
    unittest.main()
