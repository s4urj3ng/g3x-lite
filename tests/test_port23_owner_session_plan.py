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

    def _decision_rows(self) -> list[list[str]]:
        sec4 = self.content.split("## 4. Decision Table", 1)[1].split("## 5. Stop Conditions", 1)[0]
        rows = [line for line in sec4.splitlines() if line.startswith("|") and not line.startswith("| :---")]
        return [[c.strip() for c in row.split("|")[1:-1]] for row in rows[1:]]

    def _rows_starting_with(self, name: str) -> list[str]:
        return [
            " | ".join(cells)
            for cells in self._decision_rows()
            if cells and cells[0].replace("*", "").replace("`", "").strip().lower().startswith(name.lower())
        ]

    @staticmethod
    def _has_missed_flash_caveat(text: str) -> bool:
        lower = text.lower()
        return "UNKNOWN" in text and "flash" in lower and ("too short" in lower or "not visible" in lower)

    def test_missed_flash_caveat_in_section3(self):
        """Verify §3 carries the UNKNOWN false-negative caveat, including in §3.2 and Branch B."""
        sec3 = self.content.split("## 3. Session Protocol & Steps", 1)[1].split("## 4. Decision Table", 1)[0]
        sec32 = sec3.split("### 3.2", 1)[1].split("### 3.3", 1)[0]
        branch_b = sec3.split("#### Branch B", 1)[1].split("### 3.4", 1)[0]
        self.assertTrue(self._has_missed_flash_caveat(sec32), "§3.2 must carry the missed-flash caveat")
        self.assertTrue(self._has_missed_flash_caveat(branch_b), "Branch B must carry the missed-flash caveat")
        self.assertIn("justified only if a missed flash has been ruled out", branch_b)

    def test_missed_flash_caveat_in_after_copy_and_none_rows(self):
        """Verify the after_copy and None rows give the missed-flash alternative, labelled UNKNOWN."""
        for name in ("after_copy", "none"):
            rows = self._rows_starting_with(name)
            self.assertTrue(rows, f"Decision table must have a '{name}' row")
            for row in rows:
                self.assertTrue(
                    self._has_missed_flash_caveat(row),
                    f"Row '{name}' must give the UNKNOWN missed-flash alternative: {row}",
                )
                self.assertIn("Covers both", row, f"Row '{name}' next step must cover both explanations")

    def test_decision_table_catch_all_and_combinations(self):
        """Verify the catch-all row and the added observation combinations exist."""
        catch_all = self._rows_starting_with("other / unclear")
        self.assertEqual(len(catch_all), 1, "Decision table must have exactly one catch-all row")
        self.assertIn("report template", catch_all[0].lower())
        rows = [" | ".join(cells) for cells in self._decision_rows()]
        self.assertTrue(
            any("LED on, then dark" in r and "LED solid on" in r and "backlight glowing" in r for r in rows),
            "Must cover Power-On 1 'LED on, then dark' followed by 2A solid on with backlight glowing",
        )
        self.assertTrue(
            any("LED remains solid ON, backlight ON" in r for r in rows),
            "Must cover Power-On 1 LED solid on with backlight on",
        )
        self.assertNotIn("mutually exclusive", self.content.lower())

    def test_no_wrong_t1_flowchart_citation(self):
        """Verify the wrong T1 citation is gone and Mechanism B cites T1:266 plus the ROM evidence ID."""
        self.assertNotIn("PORT23_POWER_SUPERVISION.md:84-86", self.content)
        rows = [" | ".join(cells) for cells in self._decision_rows() if "Mechanism B" in " | ".join(cells)]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("docs/PORT23_POWER_SUPERVISION.md:266", row)
            self.assertIn("PORT23-ROM-STARTDISKBOOT", row)
            self.assertIn("0xFC05BC34-0xFC05BC38", row)

    def test_decision_table_structure(self):
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
                first_cell = cells[0].replace("*", "").strip()
                self.assertNotEqual(
                    first_cell,
                    "before_copy",
                    "Table must not list 'before_copy' as a last breadcrumb seen (that build is never flashed)",
                )
                # Verify that if Power-On 1 observed an LED ("LED on"), the last breadcrumb is not None
                po1_cell = cells[1]
                if "led on" in po1_cell.lower():
                    self.assertFalse(
                        first_cell.lower().startswith("none"),
                        f"Row with Power-On 1 observation '{po1_cell}' must not have 'None' as last breadcrumb: {row}",
                    )
        # Verify that Power-On 2A showing no LED is explicitly noted in the table
        self.assertIn("Power-On 2A showed no LED", sec4)

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

        # 1. session_id placeholder verification
        session_id = parsed_json["session_report"].get("session_id", "")
        self.assertTrue(
            session_id.startswith("YYYYMMDD"),
            f"session_id must be an unfilled placeholder starting with 'YYYYMMDD', got '{session_id}'",
        )
        self.assertNotIn("20261101", session_id, "session_id must not contain fixed past date 20261101")

        # 2. Verify all observation fields in all runs are null or empty
        observation_fields = [
            "led_observed",
            "lcd_backlight_state",
            "outcome",
            "button_hold_duration_measured_ms",
            "led_duration_measured_ms",
            "time_to_dark_measured_ms",
        ]
        for run in parsed_json["session_report"]["runs"]:
            for field in observation_fields:
                self.assertIn(field, run, f"Run {run.get('power_on_index')} must contain field '{field}'")
                val = run[field]
                self.assertTrue(
                    val is None or val == "",
                    f"Run {run.get('power_on_index')} observation field '{field}' must be null or empty, got {val!r}",
                )
            notes_val = run.get("notes", "")
            self.assertTrue(
                notes_val is None or notes_val == "",
                f"Run {run.get('power_on_index')} notes must be null or empty string, got {notes_val!r}",
            )

        # 3. Verify Run 2 build_stage and diskboot_sha256 are NOT fixed to pre_jump
        run2 = parsed_json["session_report"]["runs"][1]
        self.assertTrue(
            run2.get("build_stage") is None or run2.get("build_stage") == "",
            f"Run 2 build_stage must be null/empty for owner to choose, got {run2.get('build_stage')!r}",
        )
        self.assertTrue(
            run2.get("diskboot_sha256") is None or run2.get("diskboot_sha256") == "",
            f"Run 2 diskboot_sha256 must be null/empty for owner to choose, got {run2.get('diskboot_sha256')!r}",
        )

        # 4. Verify all allowed enum options are listed
        self.assertIn("allowed_enums", parsed_json, "Template must contain 'allowed_enums' block")
        enums = parsed_json["allowed_enums"]
        expected_enums = {
            "button_action": ["brief_tap", "continuous_hold"],
            "card_lock_state": ["LOCKED", "UNLOCKED"],
            "led_observed": ["flash_brief_then_dark", "led_lit_before_ui", "solid_on", "never_lit"],
            "lcd_backlight_state": ["off_unpowered", "on_stock_ui", "on_blank_glow"],
            "outcome": ["power_off", "stock_ui", "hang", "reset_loop"],
        }
        for enum_name, expected_options in expected_enums.items():
            self.assertIn(enum_name, enums, f"allowed_enums must list '{enum_name}'")
            actual_options = enums[enum_name]
            for opt in expected_options:
                self.assertIn(
                    opt,
                    actual_options,
                    f"allowed_enums['{enum_name}'] must list option '{opt}'",
                )

        # Verify build_stage options in allowed_enums include both pre_jump and after_copy with T2 hashes
        stage_options = {item["stage"]: item["diskboot_sha256"] for item in enums.get("build_stage", [])}
        self.assertIn("pre_jump", stage_options)
        self.assertIn("after_copy", stage_options)
        self.assertEqual(stage_options["pre_jump"], self.t2_hashes["pre_jump"])
        self.assertEqual(stage_options["after_copy"], self.t2_hashes["after_copy"])

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

    def test_stop_conditions_no_invalid_citation_and_observable(self):
        """Verify stop conditions do not cite SAFETY.md:1-8 and use observable conditions."""
        sec5 = self.content.split("## 5. Stop Conditions & Recovery Plan", 1)[1].split("## 6. Machine-Readable", 1)[0]
        # Must not cite SAFETY.md:1-8 for stop conditions
        self.assertNotIn("[VERIFIED: docs/SAFETY.md:1-8]", sec5)
        self.assertIn("[INFERRED (owner protocol)]", sec5)
        # Must not mention measuring battery voltage threshold
        self.assertNotIn("battery voltage drops below nominal threshold", sec5.lower())
        self.assertIn("low-battery indicator", sec5.lower())

    def test_no_overreaching_rom_citations(self):
        """Verify no overreaching ROM citations for LED identity, early boot writes, or reset vector."""
        # 0xFC0D73C0 must not be cited in document
        self.assertNotIn("0xFC0D73C0", self.content)
        # LED identity must cite T1 and owner result (d)
        self.assertIn("docs/PORT23_POWER_SUPERVISION.md:33", self.content)
        self.assertIn("owner result (d)", self.content)
        # Never writes claim must be INFERRED
        m_never = re.search(r"never writes.*?`0x004D0002`.*?(\[[^\]]+\])", self.content, re.IGNORECASE)
        self.assertIsNotNone(m_never)
        self.assertIn("INFERRED", m_never.group(1))
        # Reset vector reboot must be INFERRED
        m_reset = re.search(r"reset vector `0xFC02000C`\s*`?(\[[^\]]+\])`?", self.content)
        self.assertIsNotNone(m_reset)
        self.assertIn("INFERRED", m_reset.group(1))


if __name__ == "__main__":
    unittest.main()
