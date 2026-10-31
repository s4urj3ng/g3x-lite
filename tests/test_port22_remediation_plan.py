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
3. Every path:line (or path:start-end, comma-separated) citation resolves to a file tracked
   in git (``git ls-files``) with at least that many lines. Untracked local files never count.
4. No hex address appears without an epistemic label and citation, unless it is labelled UNKNOWN.
5. Evidence citations adhere strictly to the allowed source boundary (PORT16-PORT21 docs and manifests),
   and every hex literal appears within the cited line range (±3 lines) of an allowed-source
   citation on the same line; UNKNOWN lines are exempt from the range check but the value must
   still occur in a cited allowed source, so no guessed value can appear.
6. Proposed changes are never labelled VERIFIED.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT22_REMEDIATION_PLAN.md"

HEX_PATTERN = re.compile(r"\b0x[0-9a-fA-F]+\b")
CITATION_PATTERN = re.compile(r"([a-zA-Z0-9_\-./]+?\.[a-zA-Z0-9]+):(\d+(?:-\d+)?(?:\s*,\s*\d+(?:-\d+)?)*)")
LABEL_PATTERN = re.compile(r"\[(VERIFIED|INFERRED|UNKNOWN)[^\]]*\]")
ALLOWED_SOURCE_PATTERN = re.compile(r"^(docs/PORT(1[6-9]|2[0-1])_.*\.md|docs/agentbridge/PORT.*_EVIDENCE_MANIFEST\.json)$")
HEX_LINE_TOLERANCE = 3


def parse_citations(text: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Parses path:line or path:start-end (including comma-separated ranges) citations."""
    results = []
    for match in CITATION_PATTERN.finditer(text):
        fpath = match.group(1)
        range_str = match.group(2)
        parsed_ranges = []
        for r in range_str.split(","):
            r = r.strip()
            if not r:
                continue
            if "-" in r:
                parts = r.split("-")
                s = int(parts[0])
                e = int(parts[1])
            else:
                s = e = int(r)
            parsed_ranges.append((s, e))
        results.append((fpath, parsed_ranges))
    return results


def _read_repo_lines(rel_path: str) -> list[str]:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8").splitlines()


def hex_backing_violations(lines, tracked_files, read_lines=_read_repo_lines, tolerance=HEX_LINE_TOLERANCE):
    """Returns hex literals in ``lines`` that no allowed citation on the same line backs.

    On lines without UNKNOWN, a value is backed only if it appears within a cited line range
    widened by ``tolerance`` lines. On UNKNOWN lines the range check is waived, but the value must
    still appear somewhere in a cited allowed source. Values compare numerically.
    """
    cache: dict[str, list[set[int]]] = {}

    def line_values(rel_path: str) -> list[set[int]]:
        if rel_path not in cache:
            cache[rel_path] = [
                {int(h, 16) for h in HEX_PATTERN.findall(text)} for text in read_lines(rel_path)
            ]
        return cache[rel_path]

    def backed(value: int, rel_path: str, ranges, check_range: bool) -> bool:
        per_line = line_values(rel_path)
        if not check_range:
            return any(value in vals for vals in per_line)
        for s, e in ranges:
            lo = max(1, s - tolerance)
            hi = min(len(per_line), e + tolerance)
            if any(value in per_line[n - 1] for n in range(lo, hi + 1)):
                return True
        return False

    violations = []
    for i, line in enumerate(lines, start=1):
        literals = HEX_PATTERN.findall(line)
        if not literals:
            continue
        citations = [
            (fpath, ranges)
            for fpath, ranges in parse_citations(line)
            if ALLOWED_SOURCE_PATTERN.match(fpath) and fpath in tracked_files
        ]
        if not citations:
            violations.append(f"Line {i}: hex {literals} without an allowed-source citation")
            continue
        check_range = "UNKNOWN" not in line
        for h in literals:
            if not any(backed(int(h, 16), fpath, ranges, check_range) for fpath, ranges in citations):
                scope = "cited line ranges" if check_range else "cited sources"
                violations.append(f"Line {i}: hex {h} not found in {scope} {citations}")
    return violations


class TestPort22RemediationPlan(unittest.TestCase):
    """Validates structural, content, and evidential requirements of docs/PORT22_REMEDIATION_PLAN.md."""

    @classmethod
    def setUpClass(cls):
        # Must fail, not skip, if the document does not exist
        if not DOC_PATH.is_file():
            raise AssertionError(f"Required document does not exist: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

        # Query git ls-files via subprocess from REPO_ROOT
        try:
            cls.tracked_files = set(
                subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT, text=True).splitlines()
            )
        except Exception as e:
            raise AssertionError(f"Failed to query git ls-files: {e}")

        # Assemble corpus of allowed source documents
        cls.allowed_sources = [
            f for f in cls.tracked_files
            if ALLOWED_SOURCE_PATTERN.match(f)
        ]
        corpus_parts = []
        for rel_path in cls.allowed_sources:
            full_path = REPO_ROOT / rel_path
            if full_path.is_file():
                corpus_parts.append(full_path.read_text(encoding="utf-8").lower())
        cls.allowed_corpus = " ".join(corpus_parts)

    def test_doc_exists_and_non_empty(self):
        """Verifies docs/PORT22_REMEDIATION_PLAN.md exists, is tracked, and has substantive content."""
        self.assertTrue(DOC_PATH.is_file(), "docs/PORT22_REMEDIATION_PLAN.md must exist")
        self.assertIn("docs/PORT22_REMEDIATION_PLAN.md", self.tracked_files, "Doc must be tracked in git")
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

            # Extract Target File path(s) and verify tracked or untracked chdk-port/
            target_line_match = re.search(r"-\s+\*\*Target File\*\*:\s*([^\n]+)", text)
            self.assertIsNotNone(target_line_match, f"Section {h} missing Target File line")
            target_line = target_line_match.group(1)
            target_files = [
                span for span in re.findall(r"`([^`]+)`", target_line)
                if span.startswith("chdk-port/") or span.startswith("tools/")
            ]
            self.assertGreaterEqual(len(target_files), 1, f"Section {h} must specify at least one Target File")
            for tf in target_files:
                self.assertTrue(
                    tf.startswith("chdk-port/") or tf.startswith("tools/build_candidate_"),
                    f"Section {h} Target File {tf} must be under chdk-port/ or tools/build_candidate_*.py",
                )
                if tf in self.tracked_files:
                    # File is tracked in git; verify it exists
                    self.assertTrue(
                        (REPO_ROOT / tf).is_file(),
                        f"Tracked Target File {tf} must exist on disk",
                    )
                else:
                    # Untracked path: must be under chdk-port/, described as untracked, carry INFERRED or UNKNOWN label,
                    # and cite the doc that names it.
                    self.assertTrue(
                        tf.startswith("chdk-port/"),
                        f"Untracked target file {tf} must be under chdk-port/",
                    )
                    self.assertTrue(
                        ("INFERRED" in target_line) or ("UNKNOWN" in target_line),
                        f"Target File line for untracked {tf} must carry INFERRED or UNKNOWN label: {target_line}",
                    )
                    tf_citations = parse_citations(target_line)
                    self.assertGreater(
                        len(tf_citations),
                        0,
                        f"Target File line for untracked {tf} must cite allowed doc naming it: {target_line}",
                    )
                    self.assertIn(
                        tf.lower(),
                        self.allowed_corpus,
                        f"Untracked target file {tf} must be named in allowed PORT16-21 docs",
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
        unknown_section_parts = re.split(r"##\s+.*?Open UNKNOWNs", self.content)
        self.assertGreaterEqual(len(unknown_section_parts), 2, "Section 7 Open UNKNOWNs must be present")
        unknown_section = unknown_section_parts[1]
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
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_bullets.append(f"Line {i}: {stripped}")
            elif stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue
                if "Hypothesis ID" in stripped:
                    continue
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

    def test_every_path_line_citation_resolves_and_is_tracked(self):
        """Verifies every citation resolves to a git-tracked file with valid line bounds.

        Tracked status comes from ``git ls-files``, so a citation cannot pass just because a
        gitignored or untracked file happens to exist in the local worktree.
        """
        citations = parse_citations(self.content)
        self.assertGreaterEqual(len(citations), 20, "Doc must contain substantive citations")

        file_cache: dict[str, int] = {}
        citation_errors = []

        for fpath, ranges in citations:
            if fpath not in self.tracked_files:
                citation_errors.append(f"Cited file is not tracked in git: {fpath}")
                continue
            p = REPO_ROOT / fpath
            if not p.is_file():
                citation_errors.append(f"Tracked cited file missing from worktree: {fpath}")
                continue

            if fpath not in file_cache:
                file_cache[fpath] = len(p.read_text(encoding="utf-8").splitlines())
            total_lines = file_cache[fpath]

            for s, e in ranges:
                if s < 1 or s > total_lines:
                    citation_errors.append(
                        f"Invalid start line in {fpath}:{s} (file has {total_lines} lines)"
                    )
                if e < 1 or e > total_lines:
                    citation_errors.append(
                        f"Invalid end line in {fpath}:{s}-{e} (file has {total_lines} lines)"
                    )
                if e < s:
                    citation_errors.append(
                        f"End line before start line in {fpath}:{s}-{e}"
                    )

        self.assertEqual(
            citation_errors,
            [],
            f"Citation errors in docs/PORT22_REMEDIATION_PLAN.md:\n" + "\n".join(citation_errors),
        )

    def test_untracked_loader_sources_are_never_cited_with_lines(self):
        """Verifies untracked loader sources are named only, never cited as path:line."""
        for fpath, _ in parse_citations(self.content):
            self.assertFalse(
                fpath.startswith("chdk-port/loader/"),
                f"Untracked loader source must not carry a line citation: {fpath}",
            )

    def test_every_claim_bullet_and_row_has_citation(self):
        """Verifies every labelled bullet and table row also carries a path:line citation."""
        missing = []
        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            is_bullet = stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped)
            is_row = (
                stripped.startswith("|")
                and stripped.endswith("|")
                and not re.match(r"^\|[\s\-:|]+\|$", stripped)
                and "Hypothesis ID" not in stripped
            )
            if (is_bullet or is_row) and not CITATION_PATTERN.search(stripped):
                missing.append(f"Line {i}: {stripped}")
        self.assertEqual(missing, [], "Claims without path:line citation:\n" + "\n".join(missing))

    def test_proposals_are_never_labelled_verified(self):
        """Verifies every proposed change leads with an INFERRED (or UNKNOWN) label, never VERIFIED."""
        proposals = [
            (i, line.strip())
            for i, line in enumerate(self.lines, start=1)
            if line.strip().startswith("- **Proposal")
        ]
        self.assertGreaterEqual(len(proposals), 4, "Each hypothesis must have at least one proposal")
        for i, text in proposals:
            first = LABEL_PATTERN.search(text)
            self.assertIsNotNone(first, f"Line {i}: proposal without label")
            self.assertIn(
                first.group(1),
                ("INFERRED", "UNKNOWN"),
                f"Line {i}: proposal must not lead with VERIFIED: {text[:80]}",
            )

    def test_evidence_citations_source_boundary(self):
        """Verifies every evidence citation points to PORT16-PORT21 docs or manifests."""
        boundary_violations = []

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            citations = parse_citations(stripped)

            for fpath, _ in citations:
                # Target code files under chdk-port/ or tools/ name candidate change locations
                if fpath.startswith("chdk-port/") or fpath.startswith("tools/"):
                    continue

                if not ALLOWED_SOURCE_PATTERN.match(fpath):
                    boundary_violations.append(f"Line {i}: citation {fpath} outside allowed sources")

        self.assertEqual(
            boundary_violations,
            [],
            f"Evidence citations violating source boundary:\n" + "\n".join(boundary_violations),
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

    def test_every_hex_literal_is_cited_from_allowed_source_on_same_line(self):
        """Verifies every hex literal appears in the cited line range of an allowed source on its line.

        For lines not labelled UNKNOWN, the value must appear within the cited line range (widened by
        HEX_LINE_TOLERANCE lines) of at least one allowed PORT16-PORT21 citation on the same line.
        UNKNOWN lines are exempt from the range check but must still cite an allowed source that
        contains the value somewhere, so no guessed value can appear.
        """
        violations = hex_backing_violations(self.lines, self.tracked_files)
        self.assertEqual(
            violations,
            [],
            "Hex literals not backed by a cited PORT16-PORT21 source:\n" + "\n".join(violations),
        )

    def test_hex_range_check_rejects_citation_to_wrong_lines(self):
        """Synthetic check: a hex value cited to lines that do not contain it must be rejected."""
        sources = {
            "docs/PORT18_FAKE.md": [f"line {n}" for n in range(1, 21)],
        }
        sources["docs/PORT18_FAKE.md"][9] = "offset 0x1E0 on FAT32"  # line 10

        def reader(rel_path: str) -> list[str]:
            return sources[rel_path]

        tracked = set(sources)
        good = ["- value `0x1E0` [VERIFIED: docs/PORT18_FAKE.md:10]"]
        near = ["- value `0x1E0` [VERIFIED: docs/PORT18_FAKE.md:13]"]
        wrong = ["- value `0x1E0` [VERIFIED: docs/PORT18_FAKE.md:14-16]"]
        absent = ["- value `0x52` [VERIFIED: docs/PORT18_FAKE.md:10]"]
        unknown_ok = ["- value `0x1E0` [UNKNOWN: docs/PORT18_FAKE.md:18]"]
        unknown_absent = ["- value `0x52` [UNKNOWN: docs/PORT18_FAKE.md:18]"]

        self.assertEqual(hex_backing_violations(good, tracked, reader), [])
        self.assertEqual(hex_backing_violations(near, tracked, reader), [])
        self.assertEqual(len(hex_backing_violations(wrong, tracked, reader)), 1)
        self.assertEqual(len(hex_backing_violations(absent, tracked, reader)), 1)
        self.assertEqual(hex_backing_violations(unknown_ok, tracked, reader), [])
        self.assertEqual(len(hex_backing_violations(unknown_absent, tracked, reader)), 1)


if __name__ == "__main__":
    unittest.main()
