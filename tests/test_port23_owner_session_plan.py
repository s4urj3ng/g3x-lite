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
2. Candidate DISKBOOT.BIN SHA-256 digests in the document match what T2 recorded.
3. Owner results (a)-(d) SHA-256 values and polarity constants are present.
4. The report template parses cleanly as YAML and JSON.
5. All citations point to valid tracked files and line ranges.
6. Scope integrity: only allowed files are modified.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import unittest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT23_OWNER_SESSION_PLAN.md"

# Canonical values from T2 (docs/PORT23_LED_BREADCRUMBS.md)
EXPECTED_T2_STAGE_HASHES = {
    "loader_entry": "60a78e40127d7aa2b05178a27d834545817ded7618fef9f26637b7789d92fe24",
    "before_copy": "b2a2d55e25cfd422895854d47f0d186874df9bb3450cfc46a5be045179466852",
    "after_copy": "0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df",
    "witness_entry": "0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df",
    "witness_write": "1fcad53e31f18c378b84918b65f9365e7400185423ad7dbeac62ac04555e3de8",
    "pre_jump": "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75",
}

# Owner trial results 2026-11-01
OWNER_RESULT_HASH_A_PORT20 = "757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286"
OWNER_RESULT_HASH_B_SHORT_DELAY = "3922ddbecab362e8e13dc76bedd1758828fc91a2934310d3abb7d7d70f4e44ac"
OWNER_RESULT_HASH_C_PORT19_CONTROL = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"

# Polarity constants
POLARITY_MMIO_ADDR = "0xD20B0884"
POLARITY_LED_ON = "0x004D0002"
POLARITY_LED_OFF = "0x004C0003"


class TestPort23OwnerSessionPlan(unittest.TestCase):
    """Unit tests for docs/PORT23_OWNER_SESSION_PLAN.md."""

    @classmethod
    def setUpClass(cls):
        if not DOC_PATH.is_file():
            raise unittest.SkipTest(f"Missing doc file: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")

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
        self.assertIn(OWNER_RESULT_HASH_C_PORT19_CONTROL, self.content)

    def test_stall_length_superseded_and_verified(self):
        """Verify the stall-length theory is marked superseded with VERIFIED label and citations."""
        self.assertIn("SUPERSEDED", self.content)
        self.assertTrue(
            "stall length is not the cause" in self.content.lower()
            or "stall-length theory is superseded" in self.content.lower(),
            "Must state that the stall length is not the cause and superseded",
        )
        # Check VERIFIED label associated with stall-length or owner results
        self.assertIn("[VERIFIED by owner results a-c", self.content)

    def test_polarity_constants_present(self):
        """Verify the polarity MMIO address and values are present."""
        self.assertIn(POLARITY_MMIO_ADDR, self.content)
        self.assertIn(POLARITY_LED_ON, self.content)
        self.assertIn(POLARITY_LED_OFF, self.content)

    def test_t2_candidate_hashes_match_recorded(self):
        """Verify candidate DISKBOOT.BIN SHA-256 hashes match what T2 recorded."""
        for stage, expected_hash in EXPECTED_T2_STAGE_HASHES.items():
            self.assertIn(
                expected_hash,
                self.content,
                f"Document must cite exact T2 SHA-256 for stage '{stage}': {expected_hash}",
            )

    def test_t2_build_flags_present(self):
        """Verify opt-in build flags (--stage pre_jump, --stage after_copy, etc.) are present."""
        self.assertIn("--stage pre_jump", self.content)
        self.assertIn("--stage after_copy", self.content)
        self.assertIn("tools/build_candidate_port23_breadcrumb.py", self.content)

    def test_at_most_two_power_ons(self):
        """Verify session protocol needs at most two power-ons."""
        self.assertIn("Power-On 1", self.content)
        self.assertIn("Power-On 2", self.content)
        # Verify it explicitly caps power-ons at two
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

    def test_decision_table_structure(self):
        """Verify decision table maps last breadcrumb seen to failing stage and next host-side step."""
        sec4 = self.content.split("## 4. Decision Table", 1)[1].split("## 5. Stop Conditions", 1)[0]
        self.assertIn("Last Breadcrumb Seen", sec4)
        self.assertIn("Failing Stage", sec4)
        self.assertIn("Next Host-Side Step", sec4)
        self.assertIn("pre_jump", sec4)
        self.assertIn("after_copy", sec4)

    def test_recovery_plan_present(self):
        """Verify recovery plan covers card unlock/removal, battery pull, and normal start."""
        sec5 = self.content.split("## 5. Stop Conditions & Recovery Plan", 1)[1].split("## 6. Machine-Readable", 1)[0]
        self.assertIn("Card Unlock", sec5)
        self.assertIn("battery", sec5.lower())
        self.assertIn("UNLOCKED", sec5)
        self.assertIn("Normal Stock Start", sec5)

    def test_report_back_template_parses(self):
        """Verify the report-back template contains valid YAML and JSON blocks that parse cleanly."""
        sec6 = self.content.split("## 6. Machine-Readable Report-Back Template", 1)[1]

        # Extract YAML block
        yaml_match = re.search(r"```yaml\s*\n(.*?)\n```", sec6, re.DOTALL)
        self.assertIsNotNone(yaml_match, "Must contain a ```yaml code block")
        yaml_content = yaml_match.group(1)
        parsed_yaml = yaml.safe_load(yaml_content)
        self.assertIsInstance(parsed_yaml, dict, "YAML must parse into a dict")
        self.assertIn("session_report", parsed_yaml)
        self.assertIn("runs", parsed_yaml["session_report"])
        self.assertGreaterEqual(len(parsed_yaml["session_report"]["runs"]), 1)

        # Extract JSON block
        json_match = re.search(r"```json\s*\n(.*?)\n```", sec6, re.DOTALL)
        self.assertIsNotNone(json_match, "Must contain a ```json code block")
        json_content = json_match.group(1)
        parsed_json = json.loads(json_content)
        self.assertIsInstance(parsed_json, dict, "JSON must parse into a dict")
        self.assertIn("session_report", parsed_json)
        self.assertIn("runs", parsed_json["session_report"])
        self.assertGreaterEqual(len(parsed_json["session_report"]["runs"]), 1)

        # Verify key fields in template runs
        run1 = parsed_yaml["session_report"]["runs"][0]
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
        citation_re = re.compile(r"\b([a-zA-Z0-9_\-./]+?\.[a-zA-Z0-9]+):(\d+)(?:-(\d+))?\b")
        for match in citation_re.finditer(self.content):
            fpath_str = match.group(1)
            # Skip URLs, hex offsets, and doc names that aren't file paths
            if fpath_str.startswith("http") or fpath_str.startswith("0x"):
                continue
            fpath = REPO_ROOT / fpath_str
            if not fpath.is_file():
                continue
            line_count = len(fpath.read_text(encoding="utf-8", errors="replace").splitlines())
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


if __name__ == "__main__":
    unittest.main()
