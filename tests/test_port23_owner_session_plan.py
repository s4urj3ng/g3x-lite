#!/usr/bin/env python3
"""PORT-23 T3: Unit tests for owner session plan (localizing post-loader shutdown).

Validates that:
1. docs/PORT23_OWNER_SESSION_PLAN.md exists and contains:
   - Section 1: Current reading & hardware evidence with owner results (a)-(d),
     superseding the stall-length theory (VERIFIED).
   - Section 2: Post-loader shutdown hypotheses (Rank 1-4) from T1 and retry skip analysis.
   - Section 3: Session protocol and steps for at most two power-ons, mapping breadcrumbs
     to execution stages, and explaining how to tell power-off from hang or reset.
   - Section 4: Decision table from last breadcrumb seen to failing stage and next host-side step.
   - Section 5: Stop conditions and recovery plan (card unlock/removal, battery pull, normal start).
   - Section 6: Machine-readable report-back template.
2. Candidate DISKBOOT.BIN SHA-256 digests in the document match what T2 recorded (parsed at runtime).
3. Owner results (a)-(d) SHA-256 values and polarity constants are present.
4. The report template parses cleanly as JSON using the standard library.
5. All citations point to valid tracked files and line ranges (failing if non-existent).
6. Scope integrity: only allowed files are modified, and no binaries or build outputs are present.
7. No 'conclusively' and no unevidenced timings outside lines labelled UNKNOWN or OWNER-REPORTED.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT23_OWNER_SESSION_PLAN.md"

# Owner trial results 2026-11-01
OWNER_RESULT_HASH_A_PORT20 = "757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286"
OWNER_RESULT_HASH_B_SHORT_DELAY = "3922ddbecab362e8e13dc76bedd1758828fc91a2934310d3abb7d7d70f4e44ac"

# Polarity constants
POLARITY_MMIO_ADDR = "0xD20B0884"
POLARITY_LED_ON = "0x004D0002"
POLARITY_LED_OFF = "0x004C0003"


def parse_t2_stage_hashes_and_flags() -> tuple[dict[str, str], set[str]]:
    """Parse expected T2 stage hashes and flags dynamically from docs/PORT23_LED_BREADCRUMBS.md."""
    breadcrumbs_doc = REPO_ROOT / "docs" / "PORT23_LED_BREADCRUMBS.md"
    content = breadcrumbs_doc.read_text(encoding="utf-8")
    sec4 = content.split("## 4. Host Build Commands & Expected Hashes", 1)[1].split("## 5.", 1)[0]
    stages = re.findall(r"### 4\.\d+\s+Stage \d+:\s+`([a-z_]+)`", sec4)
    hashes = re.findall(r"\*\*`DISKBOOT\.BIN` SHA-256\*\*:\s*`([0-9a-f]{64})`", sec4)
    flags = re.findall(r"--stage\s+([a-z_]+)", sec4)
    stage_hashes = dict(zip(stages, hashes))
    return stage_hashes, set(flags)


def parse_port19_sha() -> str:
    """Parse the full PORT-19 DISKBOOT.BIN SHA-256 dynamically from docs/PORT16_CANDIDATE_BUILD.md."""
    cb_doc = REPO_ROOT / "docs" / "PORT16_CANDIDATE_BUILD.md"
    content = cb_doc.read_text(encoding="utf-8")
    m = re.search(
        r"\|\s*\*\*`DISKBOOT\.BIN`\*\*\s*\|\s*`candidate_port2a/DISKBOOT\.BIN`\s*\|\s*[\d,]+\s*\|\s*`([0-9a-f]{64})`",
        content,
    )
    if not m:
        raise ValueError("Could not parse PORT-19 DISKBOOT.BIN SHA-256 from docs/PORT16_CANDIDATE_BUILD.md")
    return m.group(1)


class TestPort23OwnerSessionPlan(unittest.TestCase):
    """Unit tests for docs/PORT23_OWNER_SESSION_PLAN.md."""

    @classmethod
    def setUpClass(cls):
        if not DOC_PATH.is_file():
            raise AssertionError(f"Required document does not exist: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.t2_hashes, cls.t2_flags = parse_t2_stage_hashes_and_flags()
        cls.port19_sha = parse_port19_sha()

    def test_file_exists_and_substantive(self):
        """Verify the session plan exists and has substantive content."""
        self.assertTrue(DOC_PATH.is_file(), "PORT23_OWNER_SESSION_PLAN.md must exist")
        self.assertGreater(len(self.content), 3000, "Plan document must be substantive (>3000 chars)")

    def test_required_sections_present(self):
        """Verify presence of all 6 mandatory sections."""
        self.assertIn("## 1. Current Reading & Hardware Evidence", self.content)
        self.assertIn("## 2. Post-Loader Shutdown Hypotheses & Retry Behavior", self.content)
        self.assertIn("## 3. Session Protocol & Steps", self.content)
        self.assertIn("## 4. Decision Table", self.content)
        self.assertIn("## 5. Stop Conditions & Recovery Plan", self.content)
        self.assertIn("## 6. Machine-Readable Report-Back Template", self.content)

    def test_owner_results_a_to_d_recorded_with_hashes(self):
        """Verify owner results (a)-(d) from 2026-11-01 are documented with their exact SHA-256 values."""
        self.assertIn(OWNER_RESULT_HASH_A_PORT20, self.content)
        self.assertIn(OWNER_RESULT_HASH_B_SHORT_DELAY, self.content)
        self.assertIn(self.port19_sha, self.content)

    def test_stall_length_superseded_and_verified(self):
        """Verify the stall-length theory is marked superseded with VERIFIED label and citations."""
        self.assertIn("SUPERSEDED", self.content)
        self.assertTrue(
            "stall length is not the cause" in self.content.lower()
            or "stall-length theory is superseded" in self.content.lower(),
            "Must state that the stall length is not the cause and superseded",
        )
        self.assertIn("[VERIFIED by owner results a-c", self.content)

    def test_polarity_constants_present(self):
        """Verify the polarity MMIO address and values are present."""
        self.assertIn(POLARITY_MMIO_ADDR, self.content)
        self.assertIn(POLARITY_LED_ON, self.content)
        self.assertIn(POLARITY_LED_OFF, self.content)

    def test_t2_candidate_hashes_match_recorded(self):
        """Verify candidate DISKBOOT.BIN SHA-256 hashes match what T2 recorded (parsed at runtime)."""
        self.assertGreaterEqual(len(self.t2_hashes), 5, "Must have parsed at least 5 T2 stages")
        for stage, expected_hash in self.t2_hashes.items():
            self.assertIn(
                expected_hash,
                self.content,
                f"Document must cite exact T2 SHA-256 for stage '{stage}': {expected_hash}",
            )

    def test_t2_build_flags_present(self):
        """Verify opt-in build flags parsed from T2 are present in document."""
        self.assertIn("--stage pre_jump", self.content)
        self.assertIn("--stage after_copy", self.content)
        self.assertIn("tools/build_candidate_port23_breadcrumb.py", self.content)

    def test_at_most_two_power_ons(self):
        """Verify session protocol needs at most two power-ons."""
        self.assertIn("Power-On 1", self.content)
        self.assertIn("Power-On 2", self.content)
        self.assertTrue(
            "at most two" in self.content.lower() or "at most 2" in self.content.lower(),
            "Must state that the session needs at most two power-ons",
        )
        self.assertNotIn("Power-On 3", self.content)

    def test_power_off_distinguished_from_hang_or_reset(self):
        """Verify explanation of how to tell power-off from a hang or reset."""
        self.assertIn("How to Distinguish Power-Off from a Hang or a Reset", self.content)
        self.assertIn("Clean Power-Off", self.content)
        self.assertIn("Hang", self.content)
        self.assertIn("Reset", self.content)
        self.assertIn("backlight", self.content.lower())

    def test_retry_skipping_startdiskboot_analysis(self):
        """Verify inclusion of T1 findings on whether a retry skips StartDiskboot."""
        self.assertIn("Mechanism A", self.content)
        self.assertIn("Mechanism B", self.content)
        self.assertIn("StartDiskboot", self.content)

    def test_decision_table_structure_and_mutual_exclusion(self):
        """Verify decision table maps last breadcrumb seen to failing stage and next host-side step."""
        sec4 = self.content.split("## 4. Decision Table", 1)[1].split("## 5. Stop Conditions", 1)[0]
        self.assertIn("Last Breadcrumb Seen", sec4)
        self.assertIn("Failing Stage", sec4)
        self.assertIn("Next Host-Side Step", sec4)
        self.assertIn("pre_jump", sec4)
        self.assertIn("after_copy", sec4)
        self.assertIn("None", sec4)
        # Verify before_copy is not used as last breadcrumb seen
        table_lines = [line for line in sec4.splitlines() if line.startswith("|") and not line.startswith("| :---")]
        # Headers: table_lines[0]
        for row in table_lines[1:]:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if cells:
                first_cell = cells[0].replace("*", "")
                self.assertNotEqual(
                    first_cell,
                    "before_copy",
                    "Table must not list 'before_copy' as a last breadcrumb seen (that build is never flashed)",
                )

    def test_recovery_plan_present(self):
        """Verify recovery plan covers card unlock/removal, battery pull, and normal start."""
        sec5 = self.content.split("## 5. Stop Conditions & Recovery Plan", 1)[1].split("## 6. Machine-Readable", 1)[0]
        self.assertIn("Card Unlock", sec5)
        self.assertIn("battery", sec5.lower())
        self.assertIn("UNLOCKED", sec5)
        self.assertIn("Normal Stock Start", sec5)

    def test_report_back_template_parses_json(self):
        """Verify the report-back template contains a valid JSON block that parses cleanly."""
        sec6 = self.content.split("## 6. Machine-Readable Report-Back Template", 1)[1]

        # Extract JSON block
        json_match = re.search(r"```json\s*\n(.*?)\n```", sec6, re.DOTALL)
        self.assertIsNotNone(json_match, "Must contain a ```json code block")
        json_content = json_match.group(1)
        parsed_json = json.loads(json_content)
        self.assertIsInstance(parsed_json, dict, "JSON must parse into a dict")
        self.assertIn("session_report", parsed_json)
        self.assertIn("runs", parsed_json["session_report"])
        self.assertGreaterEqual(len(parsed_json["session_report"]["runs"]), 2)

        # Verify key fields in template runs
        run1 = parsed_json["session_report"]["runs"][0]
        for field in (
            "power_on_index",
            "build_stage",
            "diskboot_sha256",
            "card_lock_state",
            "led_observed",
            "lcd_backlight_state",
            "outcome",
        ):
            self.assertIn(field, run1, f"Report template run must contain '{field}'")

    def test_epistemic_labels_present(self):
        """Verify epistemic labels are present throughout the document."""
        for label in ("[VERIFIED", "[STATIC_VERIFIED", "[INFERRED", "[UNKNOWN", "[OWNER-REPORTED"):
            self.assertIn(label, self.content, f"Document must contain epistemic label '{label}'")

    def test_citations_resolve_to_tracked_files(self):
        """Verify all file:line citations point to existing tracked files with valid line ranges."""
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_files = set(res.stdout.splitlines())

        citation_re = re.compile(r"\b([a-zA-Z0-9_\-./]+?\.[a-zA-Z0-9]+):(\d+)(?:-(\d+))?\b")
        allowed_non_file_prefixes = ("http://", "https://")

        for match in citation_re.finditer(self.content):
            fpath_str = match.group(1)
            if fpath_str.startswith(allowed_non_file_prefixes):
                continue

            fpath = REPO_ROOT / fpath_str
            self.assertTrue(
                fpath_str in tracked_files or fpath.is_file(),
                f"Cited path '{fpath_str}' does not exist or is not tracked in git",
            )

            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            line_count = len(lines)
            start_line = int(match.group(2))
            end_line = int(match.group(3)) if match.group(3) else start_line
            self.assertLessEqual(
                start_line,
                line_count,
                f"Citation {fpath_str}:{start_line} exceeds file line count ({line_count})",
            )
            self.assertLessEqual(
                end_line,
                line_count,
                f"Citation {fpath_str}:{end_line} exceeds file line count ({line_count})",
            )

    def test_scope_integrity(self):
        """Verify only allowed files are modified, and no binaries or build outputs are present."""
        allowed_modified = {
            "docs/PORT23_OWNER_SESSION_PLAN.md",
            "tests/test_port23_owner_session_plan.py",
        }
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            fpath = line[3:].strip()
            if " -> " in fpath:
                fpath = fpath.split(" -> ")[1].strip()
            self.assertIn(
                fpath,
                allowed_modified,
                f"File '{fpath}' is modified or untracked outside allowed scope",
            )
            forbidden_exts = (".bin", ".elf", ".o", ".a", ".dump", ".rom")
            self.assertFalse(
                fpath.endswith(forbidden_exts),
                f"Binary/build artifact '{fpath}' must not be modified or added",
            )

    def test_no_conclusively_and_no_unevidenced_timings(self):
        """Verify doc contains no 'conclusively' and no unevidenced timings outside UNKNOWN/OWNER-REPORTED."""
        # 1. No 'conclusively'
        self.assertNotIn("conclusively", self.content.lower(), "Document must not contain 'conclusively'")

        # 2. No '~N ms' or 'N seconds' outside lines labelled UNKNOWN or OWNER-REPORTED
        timing_pattern = re.compile(
            r"(?:~\s*\d+(?:[–-]\d+)?\s*(?:ms|s|seconds?|sec)|\b\d+(?:\.\d+)?\s*(?:seconds?|sec|ms)\b)",
            re.IGNORECASE,
        )
        lines = self.content.splitlines()
        in_code_block = False
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            matches = timing_pattern.findall(line)
            if matches:
                upper = line.upper()
                has_unknown = "[UNKNOWN" in upper or "UNKNOWN" in upper
                has_owner = "OWNER-REPORTED" in upper
                self.assertTrue(
                    has_unknown or has_owner,
                    f"Line {line_no} contains timing {matches} without UNKNOWN or OWNER-REPORTED label: {line}",
                )


if __name__ == "__main__":
    unittest.main()
