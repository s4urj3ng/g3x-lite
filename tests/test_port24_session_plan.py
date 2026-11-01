#!/usr/bin/env python3
"""Unit tests for PORT-24 T4 (r2): Owner session plan to localise the failure in one or two power-ons.

Verifies:
1. docs/PORT24_SESSION_PLAN.md exists and is substantive.
2. The cited candidate SHA-256 matches the one parsed from docs/PORT24_BREADCRUMB_LADDER.md (no hardcoding).
3. Every ladder code parsed from docs/PORT24_BREADCRUMB_LADDER.md appears in the decode table.
4. The exact card setup values (LOCKED, FAT32, BOOTDISK 0x1E0, SCRIPT 0x1F0) are present.
5. The plan specifies at most two power-ons with the ladder card inserted, recovery ends diagnosis, and real action paths satisfy criteria (a)-(d).
6. Power button handling (hold vs short press) explicitly accounts for the O1 result and boot_prototype.c:350.
7. StartDiskboot-skip cues from T2 are documented.
8. Recovery procedures (card unlock/removal, long-press/repeated press, capacitor discharge / PMIC reset) are present.
9. Machine-readable report template for the owner is present.
10. Strict line-by-line / row-by-row evidence label and citation validation:
    every claim line and every decode-table row must carry a VERIFIED, INFERRED, or UNKNOWN
    label and an exact citation (a file path plus :line or a § section).
    Allowed exceptions: headings, table header and separator rows, and the report-template code block.
11. Tightened flash-count check: requires a decode-table row for each count from 0 to 7 and an ambiguous/uncertain-count row.
12. Decode table has at least one LED-off-after-ladder row labelled UNKNOWN that points to recovery (§ 5) without assuming the camera is off.
13. GPIO 0x14F to write-protect switch mapping is not labelled VERIFIED (matches T2 INFERRED).
14. SD1stInit ordering statement matches T2 (SD1stInit before GPIO 0x14F check, branch does not skip SD init).
15. Binary guard scoped: added files are valid text and contain no raw binary payloads or ROM dumps.
"""

from __future__ import annotations

import re
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


def parse_ladder_ambiguity_note_line(ladder_doc_path: Path) -> int:
    """Resolve the line number of the Ambiguity note in docs/PORT24_BREADCRUMB_LADDER.md dynamically."""
    lines = ladder_doc_path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        if "Ambiguity note" in line or "without completing its OFF gap" in line:
            return idx
    raise ValueError(f"Could not find Ambiguity note in {ladder_doc_path}")


def parse_ladder_power_on_numbers(doc_text: str) -> set[int]:
    """Parse the doc text for ladder power-on instructions and return distinct power-on numbers.

    Extracts numbers N from:
    - Headings or steps like 'Power-On N' (e.g., 'Power-On 1', 'Power-On 2')
    - Instructions or steps telling the owner to perform or proceed to Power-On N with the ladder card inserted
    - Any branch or triage text referencing a Power-On N
    """
    matches = re.findall(r"Power-On\s*(\d+)", doc_text, re.IGNORECASE)
    return {int(m) for m in matches}


def validate_ladder_power_on_budget(doc_text: str) -> set[int]:
    """Validate that all ladder power-on numbers in doc_text are a subset of {1, 2}.

    Raises ValueError if any ladder power-on number outside {1, 2} is present, or if no power-ons are found.
    """
    numbers = parse_ladder_power_on_numbers(doc_text)
    if not numbers:
        raise ValueError("No ladder power-on instructions found in document text")
    if not numbers.issubset({1, 2}):
        invalid = sorted(numbers - {1, 2})
        raise ValueError(
            f"Power-on budget exceeded: document contains ladder power-on instructions for {invalid}, expected subset of {{1, 2}}"
        )
    return numbers


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
        cls.ladder_ambiguity_line = parse_ladder_ambiguity_note_line(DOCS_LADDER)

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

    def test_power_on_budget_and_action_paths(self):
        """Verify the power-on budget and real action paths per feedback (2):
        (a) Count power-on steps that happen with the ladder card inserted is <= 2 on every branch.
        (b) Every branch ends either at report or at card-removed recovery.
        (c) After a recovery step, no step reinserts the card or runs another ladder power-on.
        (d) No phrase in the doc claims that recovery counts toward the two power-ons.
        """
        # (a) Power-on budget is defined as at most two power-ons with the ladder card inserted
        self.assertIn("Power-On 1", self.content)
        self.assertIn("Power-On 2", self.content)
        self.assertNotIn("Power-On 3", self.content)

        # Budget definition check
        self.assertTrue(
            re.search(
                r"at most two power-ons with the ladder card inserted",
                self.content,
                re.IGNORECASE,
            ),
            "Document must explicitly define budget as 'at most two power-ons with the ladder card inserted'",
        )

        # Parse branches in Section 2
        sec2_match = re.search(
            r"## 2\..*?Step-by-Step Execution Plan.*?\n(.*?)(?=\n## 3\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec2_match, "Section 2 must exist")
        sec2_text = sec2_match.group(1)

        # Parse branches under triage or actions:
        branch_matches = re.findall(
            r"-\s+\*\*(Count[^:]+|Optional Single Power-On Alternative)\*\*:(.*?)(?=\n\s*-\s+\*\*|\n\n|\Z)",
            sec2_text,
            re.DOTALL,
        )
        self.assertGreaterEqual(len(branch_matches), 4, "Must find triage branches in Section 2")

        # Validate that the set of distinct ladder power-on numbers across the document is a subset of {1, 2}
        distinct_numbers = validate_ladder_power_on_budget(self.content)
        self.assertTrue(
            distinct_numbers.issubset({1, 2}),
            f"Set of distinct ladder power-on numbers {distinct_numbers} must be subset of {{1, 2}}",
        )

        # Validate each triage branch in Section 2: any power-on number mentioned must be in {1, 2}
        for branch_name, branch_body in branch_matches:
            branch_numbers = parse_ladder_power_on_numbers(branch_body)
            self.assertTrue(
                branch_numbers.issubset({1, 2}),
                f"Branch '{branch_name}' references ladder power-on numbers outside {{1, 2}}: {branch_numbers}",
            )

        # (b) Every branch ends either at report or at card-removed recovery
        for branch_name, branch_body in branch_matches:
            has_report = bool(re.search(r"(?:Section\s*6|report)", branch_body, re.IGNORECASE))
            has_recovery = bool(re.search(r"(?:Section\s*5|recovery)", branch_body, re.IGNORECASE))
            self.assertTrue(
                has_report or has_recovery,
                f"Branch '{branch_name}' must end either at report or recovery",
            )
            if has_recovery:
                self.assertTrue(
                    re.search(r"(?:card\s*removed|without\s*the\s*ladder\s*card)", branch_body, re.IGNORECASE),
                    f"Branch '{branch_name}' ending at recovery must specify card removed",
                )

        # (c) After a recovery step, no step reinserts the card or runs another ladder power-on
        sec5_match = re.search(
            r"## 5\..*?Recovery Procedures.*?\n(.*?)(?=\n## 6\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec5_match, "Section 5 Recovery Procedures must exist")
        sec5_text = sec5_match.group(1)

        # Must explicitly prohibit reinserting the ladder card
        self.assertTrue(
            re.search(
                r"never\s+(?:tell the owner to\s+)?reinsert\s+or\s+relock\s+the\s+ladder\s+card|never\s+reinsert\s+the\s+(?:locked\s+)?ladder\s+card",
                self.content,
                re.IGNORECASE,
            ),
            "Document must state that after recovery, the ladder card is never reinserted or relocked in the same session",
        )
        self.assertTrue(
            re.search(
                r"no\s+branch\s+may\s+run\s+a\s+diagnostic\s+power-on\s+after\s+any\s+recovery\s+step|no\s+diagnostic\s+power-on\s+may\s+be\s+run\s+after\s+any\s+recovery\s+step",
                self.content,
                re.IGNORECASE,
            ),
            "Document must state that no branch may run a diagnostic power-on after any recovery step",
        )

        # In section 5, ensure no instruction tells the owner to reinsert the ladder card
        for line in sec5_text.splitlines():
            if (
                re.search(r"re-?insert", line, re.IGNORECASE)
                and not re.search(r"battery", line, re.IGNORECASE)
                and not re.search(r"never|not|no\b", line, re.IGNORECASE)
            ):
                # If card is mentioned, it must be UNLOCKED or normal SD card, never ladder card / DISKBOOT
                self.assertNotIn("ladder card", line.lower())
                self.assertNotIn("diskboot", line.lower())

        # (d) No phrase in the doc claims that recovery counts toward the two power-ons
        forbidden_phrases = [
            r"at most two power-ons including recovery",
            r"including recovery",
            r"counts as Power-On 2",
            r"counts toward the two power-ons",
            r"Power-On 2 is either a second diagnostic run or recovery",
            r"which counts as Power-On 2",
            r"outside the diagnostic budget",
            r"exempt from diagnostic budget",
        ]
        for phrase in forbidden_phrases:
            match = re.search(phrase, self.content, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"Document must not contain phrase '{phrase}' claiming recovery counts toward power-ons or using old budget exemption wording",
            )

    def test_power_on_budget_negative_test(self):
        """Negative test per feedback (4): verify validate_ladder_power_on_budget rejects doc text with Power-On 3 or 4."""
        # Baseline document passes
        base_numbers = validate_ladder_power_on_budget(self.content)
        self.assertTrue(base_numbers.issubset({1, 2}))

        # Variant appending 'Perform Power-On 3 with the locked ladder card inserted'
        text_with_p3 = self.content + "\nPerform Power-On 3 with the locked ladder card inserted\n"
        with self.assertRaises(ValueError) as ctx3:
            validate_ladder_power_on_budget(text_with_p3)
        self.assertIn("3", str(ctx3.exception))

        # Variant appending 'Perform Power-On 4 with the locked ladder card inserted'
        text_with_p4 = self.content + "\nPerform Power-On 4 with the locked ladder card inserted\n"
        with self.assertRaises(ValueError) as ctx4:
            validate_ladder_power_on_budget(text_with_p4)
        self.assertIn("4", str(ctx4.exception))

    def test_led_off_lcd_dark_state_handling(self):
        """Verify per feedback (1) and (4) that 'LED off, LCD dark' state is not marked as permitting Power-On 2 unless labelled UNKNOWN and routed to recovery."""
        # 1. State must be labelled UNKNOWN (powered hang vs shutdown)
        self.assertTrue(
            re.search(
                r"LED off.*LCD dark.*(?:labelled|state is)\s+UNKNOWN\s*\(\s*powered hang vs shutdown\s*\)",
                self.content,
                re.IGNORECASE,
            ),
            "'LED off, LCD dark' state must be explicitly labelled UNKNOWN (powered hang vs shutdown)",
        )

        # 2. State must be routed straight to recovery
        self.assertTrue(
            re.search(
                r"LED off.*LCD dark.*(?:send|proceed|go|route).*straight to.*recovery",
                self.content,
                re.IGNORECASE,
            ),
            "'LED off, LCD dark' state must be routed straight to recovery",
        )

        # 3. In Section 2 triage and Section 3 decode table, verify no line marks 'LED off, LCD dark' as permitting Power-On 2
        sec2_match = re.search(
            r"## 2\..*?Step-by-Step Execution Plan.*?\n(.*?)(?=\n## 3\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec2_match)
        sec2_text = sec2_match.group(1)

        sec3_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec3_match)
        sec3_text = sec3_match.group(1)

        for text, sec_name in [(sec2_text, "Section 2"), (sec3_text, "Section 3")]:
            for line in text.splitlines():
                if "LED off" in line and "LCD dark" in line:
                    self.assertNotIn(
                        "proceed optionally to **Power-On 2**",
                        line,
                        f"In {sec_name}, line must not permit Power-On 2 for 'LED off, LCD dark': {line}",
                    )
                    self.assertNotIn(
                        "optionally execute Power-On 2",
                        line,
                        f"In {sec_name}, line must not permit Power-On 2 for 'LED off, LCD dark': {line}",
                    )
                    if "Power-On 2" in line:
                        self.assertTrue(
                            re.search(
                                r"Power-On\s*2\s+is\s+NOT\s+permitted|Power-On\s*2\s+is\s+not\s+run|skip\s+Power-On\s*2|permitted ONLY after an independently established off state|NOT run if final state was LED off",
                                line,
                                re.IGNORECASE,
                            ),
                            f"In {sec_name}, reference to Power-On 2 for 'LED off, LCD dark' must indicate NOT permitted: {line}",
                        )

    def test_hold_guidance_and_evidence_level(self):
        """Verify hold guidance conforms to feedback (2):
        - '~1-2 s' duration removed everywhere
        - Claim that holding 'reliably' reaches stock UI removed
        - Verified fact: owner held button until LCD came on (PORT-19 default build)
        - Repeated or long presses only sometimes succeeded
        - Hold-until-LCD instruction kept and applicability to ladder candidate labelled INFERRED everywhere
        """
        # Duration ~1-2 s removed
        self.assertNotIn("~1-2 s", self.content, "Duration ~1-2 s must be removed")
        self.assertNotIn("~1–2 s", self.content, "Duration ~1–2 s (en-dash) must be removed")

        # Claim of 'reliably' reaching stock UI removed
        self.assertNotIn("reliably", self.content.lower(), "Claim that holding 'reliably' reaches stock UI must be removed")

        # Verified fact: owner held power button until LCD came on with PORT-19 default build
        self.assertTrue(
            re.search(
                r"owner held the power button until the LCD came on.*PORT-19 default build",
                self.content,
                re.IGNORECASE,
            ),
            "Doc must cite that owner held power button until LCD came on with PORT-19 default build",
        )
        self.assertIn("docs/PORT24_POWERON_FIX.md:16-18", self.content)

        # Repeated or long presses only sometimes succeeded
        self.assertTrue(
            re.search(
                r"repeated or long presses only sometimes succeeded",
                self.content,
                re.IGNORECASE,
            ),
            "Doc must state that repeated or long presses only sometimes succeeded per docs/PORT23_POWER_SUPERVISION.md:22",
        )
        self.assertIn("docs/PORT23_POWER_SUPERVISION.md:22", self.content)

        # Applicability of hold guidance to ladder candidate labelled INFERRED everywhere
        self.assertTrue(
            re.search(
                r"applicability.*(?:hold guidance|hold instruction).*INFERRED",
                self.content,
                re.IGNORECASE,
            ),
            "Applicability of hold guidance to ladder candidate must be labelled INFERRED",
        )

    def test_decode_table_t1_rankings_integrity(self):
        """Verify T1 rankings in decode table conform to feedback (3):
        - No attribution of 'Loader Phase I: Low' to T1 (lines 725-731 assign no ranking)
        - No attribution of 'Phase VII display driver' to T1 (lines 788-789 cover Step 23 early driver stubs)
        - Checkpoints unranked by T1 are marked 'unranked by T1'
        - Likelihood judgments in separate column labelled INFERRED with reasoning
        """
        # Forbidden spurious attributions
        self.assertNotIn("Loader Phase I: Low", self.content, "Must not attribute 'Loader Phase I: Low' to T1")
        self.assertNotIn("Phase VII display driver", self.content, "Must not attribute 'Phase VII display driver' to T1")

        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        # Flashes 1 to 6 must be marked unranked by T1
        for count in range(1, 7):
            row_match = re.search(rf"\|\s*\*\*?{count}\*\*?\s*\|(.*?)\n", table_text)
            self.assertIsNotNone(row_match, f"Row {count} must exist in decode table")
            row_text = row_match.group(1)
            self.assertTrue(
                re.search(r"unranked by T1", row_text, re.IGNORECASE),
                f"Row {count} must mark loader checkpoint as unranked by T1: {row_text}",
            )

        # Table header must include separate columns for T1 Ranked Failure Mechanism and Likelihood Assessment
        self.assertTrue(
            re.search(r"T1 Ranked Failure Mechanism", table_text),
            "Decode table must have 'T1 Ranked Failure Mechanism' column",
        )
        self.assertTrue(
            re.search(r"Likelihood Assessment", table_text),
            "Decode table must have 'Likelihood Assessment' column",
        )

    def test_no_first_second_only_observation_instruction(self):
        """Verify the plan does NOT restrict observation to the first second and requires continuous observation."""
        forbidden_patterns = [
            r"during the first second",
            r"for the first second",
            r"first ~?1(?:\.0)?\s*s\b",
            r"first second of the hold",
        ]
        for pat in forbidden_patterns:
            match = re.search(pat, self.content, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"Document must not instruct observation only during the first second (found match for '{pat}')",
            )

        # Must instruct watching continuously
        self.assertTrue(
            re.search(r"watch continuously", self.content, re.IGNORECASE),
            "Document must instruct watching continuously",
        )

        # Must base observation window on 1389.08 ms slowest loop timing
        self.assertIn(
            "1389.08 ms",
            self.content,
            "Document must cite the 1389.08 ms loop timing envelope",
        )

        # Must specify minimum window of at least 10 s, with extra margin labelled INFERRED
        self.assertTrue(
            re.search(r"at least 10\s*s", self.content, re.IGNORECASE),
            "Document must require observation for at least 10 s",
        )
        self.assertTrue(
            re.search(r"extra margin.*INFERRED", self.content, re.IGNORECASE),
            "Extra margin beyond the loop envelope must be labelled INFERRED",
        )

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

        # Check that row 0 labels current-boot execution UNKNOWN
        row_0_match = re.search(r"\|\s*\*\*?0\*\*?\s*\|(.*?)\n", table_text)
        self.assertIsNotNone(row_0_match, "Row 0 must exist in decode table")
        row_0_text = row_0_match.group(1)
        self.assertIn("UNKNOWN", row_0_text, "Row 0 must label current-boot execution UNKNOWN")
        self.assertTrue(
            re.search(r"missed flash", row_0_text, re.IGNORECASE),
            "Row 0 must list missed flash alternative",
        )
        self.assertTrue(
            re.search(r"LED.*failure", row_0_text, re.IGNORECASE),
            "Row 0 must list LED failure alternative",
        )
        self.assertTrue(
            re.search(r"battery collapse", row_0_text, re.IGNORECASE),
            "Row 0 must list battery collapse alternative",
        )
        self.assertTrue(
            re.search(r"early loader failure", row_0_text, re.IGNORECASE),
            "Row 0 must list early loader failure alternative",
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

        # Dark camera / zero flash cue must NOT conclude StartDiskboot was never called
        self.assertNotIn(
            "StartDiskboot was never even called",
            self.content,
            "Section 4 cue must not conclude that StartDiskboot was never called",
        )
        self.assertNotIn(
            "StartDiskboot was never called",
            self.content,
            "Section 4 cue must not conclude that StartDiskboot was never called",
        )

        # Cue must label current-boot execution UNKNOWN and list all T2 alternatives
        cue_match = re.search(
            r"-\s+\*\*Camera Stays Dark with ZERO Flashes Seen\*\*:(.*?)(?=\n###|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(cue_match, "Cue for Camera Stays Dark with ZERO Flashes Seen must exist")
        cue_text = cue_match.group(1)
        self.assertIn("UNKNOWN", cue_text, "Zero-flash cue must label current-boot execution UNKNOWN")
        self.assertTrue(
            re.search(r"docs/PORT24_LOADER_TRACE\.md:985", cue_text),
            "Cue must cite docs/PORT24_LOADER_TRACE.md:985 for missed flash / LED failure",
        )
        self.assertTrue(
            re.search(r"docs/PORT24_LOADER_TRACE\.md:984", cue_text),
            "Cue must cite docs/PORT24_LOADER_TRACE.md:984 for battery collapse / early loader failure",
        )
        self.assertTrue(re.search(r"missed", cue_text, re.IGNORECASE))
        self.assertTrue(re.search(r"LED.*fail", cue_text, re.IGNORECASE))
        self.assertTrue(re.search(r"battery.*collaps", cue_text, re.IGNORECASE))
        self.assertTrue(re.search(r"early loader failure", cue_text, re.IGNORECASE))

    def test_recovery_procedure_present_and_labelled(self):
        """Verify recovery procedures for restoring stock UI are documented with evidence labels."""
        sec5_match = re.search(
            r"## 5\..*?Recovery Procedures.*?\n(.*?)(?=\n## 6\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec5_match, "Section 5 Recovery procedures must exist")
        sec5_text = sec5_match.group(1)

        self.assertTrue(re.search(r"UNLOCKED|remove", sec5_text, re.IGNORECASE))
        self.assertTrue(re.search(r"battery.*pull|capacitor discharge", sec5_text, re.IGNORECASE))

        # Recovery comes first: remove card or swap in card without DISKBOOT, then long press to reach stock UI
        self.assertTrue(
            re.search(r"Recovery comes first:.*remove the card.*long press", sec5_text, re.IGNORECASE),
            "Recovery procedure must state that recovery comes first with card removal then long press",
        )

        # Long-press behavior must be labelled VERIFIED or INFERRED with citation to O1 result
        self.assertTrue(
            re.search(r"docs/PORT24_POWERON_FIX\.md:16-18", sec5_text),
            "Recovery section must cite O1 result (docs/PORT24_POWERON_FIX.md:16-18)",
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

    def test_decode_table_led_off_after_ladder_row(self):
        """Verify decode table has at least one LED-off-after-ladder row labelled UNKNOWN that points to recovery."""
        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        # Parse table rows
        rows = [
            line.strip()
            for line in table_text.splitlines()
            if line.strip().startswith("|") and not re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", line.strip())
        ]
        # Skip table header row
        data_rows = rows[1:]

        matching_rows = []
        for row in data_rows:
            # Check for full ladder / 7 complete flashes and LED off
            has_ladder = bool(re.search(r"(?:7 complete flashes|full ladder)", row, re.IGNORECASE))
            has_led_off = bool(re.search(r"LED (?:turns )?off", row, re.IGNORECASE))
            has_unknown = "[UNKNOWN" in row
            has_recovery = bool(re.search(r"recovery", row, re.IGNORECASE))
            if has_ladder and has_led_off and has_unknown and has_recovery:
                matching_rows.append(row)

        self.assertGreaterEqual(
            len(matching_rows),
            1,
            "Decode table must contain at least one LED-off-after-ladder row labelled UNKNOWN that points to recovery",
        )

        # Cite the ladder lines (docs/PORT24_BREADCRUMB_LADDER.md:453-462)
        self.assertTrue(
            any("docs/PORT24_BREADCRUMB_LADDER.md:453-462" in r for r in matching_rows),
            "LED-off-after-ladder row must cite docs/PORT24_BREADCRUMB_LADDER.md:453-462",
        )

        # Do not tell the owner to assume the camera is off before pressing again
        for r in matching_rows:
            self.assertTrue(
                re.search(r"do not assume.*camera is off", r, re.IGNORECASE),
                f"Row must explicitly instruct not to assume camera is off: {r}",
            )

    def test_write_protect_gpio_mapping_not_verified(self):
        """Verify the doc does NOT label the GPIO 0x14F to write-protect switch mapping VERIFIED (matches T2 INFERRED)."""
        lines = self.content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if "0x14F" in line and re.search(r"write-protect|lock switch", line, re.IGNORECASE):
                # Ensure the line does not label the write-protect mapping itself VERIFIED
                self.assertNotIn(
                    "mapping.*VERIFIED",
                    line,
                    f"Line {idx} must not label write-protect GPIO mapping VERIFIED: {line}",
                )
                self.assertFalse(
                    re.search(r"(?:write-protect|lock switch)[^\]]*\[VERIFIED", line, re.IGNORECASE),
                    f"Line {idx} must not label write-protect switch mapping VERIFIED: {line}",
                )
                self.assertTrue(
                    "INFERRED" in line,
                    f"Line {idx} mentioning GPIO 0x14F write-protect mapping must carry INFERRED label: {line}",
                )

    def test_sd1stinit_ordering_matches_t2(self):
        """Verify that the SD1stInit ordering statement matches T2 (SD1stInit before GPIO 0x14F check)."""
        self.assertTrue(
            re.search(r"SD1stInit.*before.*(?:GPIO\s*0x14F|0xFC05BC02)", self.content, re.IGNORECASE) or
            re.search(r"0xFC05BBFE.*before.*(?:GPIO\s*0x14F|0xFC05BC02)", self.content, re.IGNORECASE),
            "Session plan must state that SD1stInit runs BEFORE the GPIO 0x14F check (matching T2)",
        )
        self.assertTrue(
            re.search(r"does not skip SD initialis?ation", self.content, re.IGNORECASE),
            "Session plan must clarify that the unlocked-card branch does not skip SD initialisation",
        )

    def test_witness_invalid_and_sd_desync_labelled_unknown(self):
        """Verify that WITNESS_INVALID and SD-bus desynchronisation statements are labelled UNKNOWN and not VERIFIED or INFERRED."""
        lines = self.content.splitlines()

        # Check WITNESS_INVALID
        witness_invalid_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if "WITNESS_INVALID" in line
            and not line.strip().startswith("#")
            and not line.strip().startswith("|")
            and not line.strip().startswith("```")
            and "extend.m" not in line
            and "Inspector Overlay" not in line
        ]
        self.assertGreaterEqual(
            len(witness_invalid_lines),
            1,
            "Must find substantive WITNESS_INVALID claim line in Section 4.3",
        )
        for idx, line in witness_invalid_lines:
            self.assertIn(
                "UNKNOWN",
                line,
                f"Line {idx} mentioning WITNESS_INVALID must be labelled UNKNOWN: {line}",
            )
            self.assertIn(
                "docs/PORT18_OWNER_TRIAL_PLAN.md:267",
                line,
                f"Line {idx} mentioning WITNESS_INVALID must cite docs/PORT18_OWNER_TRIAL_PLAN.md:267",
            )
            self.assertNotIn(
                "[VERIFIED",
                line,
                f"Line {idx} mentioning WITNESS_INVALID must NOT carry [VERIFIED: {line}",
            )
            self.assertNotIn(
                "[INFERRED",
                line,
                f"Line {idx} mentioning WITNESS_INVALID must NOT carry [INFERRED: {line}",
            )

        # Check SD-bus desynchronisation
        sd_desync_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if re.search(r"desynchronis?ation", line, re.IGNORECASE)
        ]
        self.assertGreaterEqual(
            len(sd_desync_lines),
            1,
            "Must find SD-bus desynchronisation statement",
        )
        for idx, line in sd_desync_lines:
            self.assertIn(
                "UNKNOWN",
                line,
                f"Line {idx} mentioning SD desync must be labelled UNKNOWN: {line}",
            )
            self.assertIn(
                "docs/PORT24_LOADER_TRACE.md:959",
                line,
                f"Line {idx} mentioning SD desync must cite docs/PORT24_LOADER_TRACE.md:959",
            )
            self.assertNotIn(
                "[VERIFIED",
                line,
                f"Line {idx} mentioning SD desync must NOT carry [VERIFIED: {line}",
            )
            self.assertNotIn(
                "[INFERRED",
                line,
                f"Line {idx} mentioning SD desync must NOT carry [INFERRED: {line}",
            )
            self.assertTrue(
                re.search(r"possible explanation", line, re.IGNORECASE),
                f"Line {idx} must present SD desync as possible explanation: {line}",
            )
            self.assertTrue(
                re.search(r"not (?:as )?a recovery mechanism", line, re.IGNORECASE),
                f"Line {idx} must state SD desync is not a recovery mechanism: {line}",
            )

    def test_sustained_dark_after_k_mentions_off_phase_and_cites_ladder_497(self):
        """Verify per feedback (1) that every decode row whose final observation is 'k flashes then sustained dark':
        - mentions the OFF phase of pulse k
        - covers both 'within the OFF phase of pulse k' and 'between checkpoint k and checkpoint k+1' (or after checkpoint k)
        - does not attribute the failure solely to operations after checkpoint k (e.g. cache operations)
        - cites ladder line 497 (resolved dynamically by searching for the ambiguity text)
        - labels the attribution INFERRED
        """
        ambiguity_line = self.ladder_ambiguity_line
        expected_cite = f"docs/PORT24_BREADCRUMB_LADDER.md:{ambiguity_line}"

        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        rows = [
            line.strip()
            for line in table_text.splitlines()
            if line.strip().startswith("|") and not re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", line.strip())
        ]
        data_rows = rows[1:]

        checked_rows = 0
        for row in data_rows:
            cells = [c.strip() for c in row.split("|")]
            if len(cells) < 5:
                continue
            flash_count_str = cells[1].strip("*")
            obs_cell = cells[2]
            failing_step_cell = cells[4]

            # Identify rows whose final observation is 'k flashes then sustained dark' (k >= 1)
            if not flash_count_str.isdigit() or flash_count_str == "0":
                continue
            is_sustained_dark = (
                bool(re.search(r"(?:complete flash(?:es)?|full ladder).*(?:LED off|dark)", obs_cell, re.IGNORECASE))
                and not bool(re.search(r"Stock Canon UI appears", obs_cell, re.IGNORECASE))
                and not bool(re.search(r"LCD lit", obs_cell, re.IGNORECASE))
            )
            if not is_sustained_dark:
                continue

            # 1. Row must mention OFF phase of pulse k
            self.assertTrue(
                bool(re.search(rf"OFF phase of pulse\s*{flash_count_str}", failing_step_cell, re.IGNORECASE))
                or bool(re.search(r"OFF phase of pulse", failing_step_cell, re.IGNORECASE)),
                f"Row for count {flash_count_str} must mention 'OFF phase of pulse {flash_count_str}': {failing_step_cell}",
            )

            # 2. Row must cover both within OFF phase of pulse k and subsequent execution
            self.assertTrue(
                bool(re.search(r"covers both within the OFF phase of pulse", failing_step_cell, re.IGNORECASE)),
                f"Row for count {flash_count_str} must cover 'within the OFF phase of pulse': {failing_step_cell}",
            )

            # 3. Row must state not to attribute failure solely to operations after checkpoint
            self.assertTrue(
                bool(re.search(r"do not attribute the failure.*as the only cause", failing_step_cell, re.IGNORECASE)),
                f"Row for count {flash_count_str} must state not to attribute failure as only cause: {failing_step_cell}",
            )

            # 4. Row must cite dynamically resolved ladder line 497
            self.assertIn(
                expected_cite,
                failing_step_cell,
                f"Row for count {flash_count_str} must cite {expected_cite}: {failing_step_cell}",
            )

            # 5. Row attribution must be labelled INFERRED
            self.assertIn(
                "INFERRED",
                failing_step_cell,
                f"Row for count {flash_count_str} attribution must be labelled INFERRED: {failing_step_cell}",
            )

            checked_rows += 1

        self.assertGreaterEqual(
            checked_rows,
            6,
            f"Must have validated at least rows 1-6 (validated {checked_rows} rows)",
        )

    def test_checkpoint_citations_match_authoritative_ladder_lines(self):
        """Verify per feedback (2) that:
        - Checkpoint citations in the decode table cite the authoritative ladder rows (476-482), one row per checkpoint.
        - For each ladder:N checkpoint citation in the decode table, ladder line N contains that row's checkpoint name.
        """
        ladder_lines = DOCS_LADDER.read_text(encoding="utf-8").splitlines()

        table_sec_match = re.search(
            r"## 3\..*?Decode Table.*?\n(.*?)(?=\n## 4\.|\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(table_sec_match, "Section 3 Decode Table must exist")
        table_text = table_sec_match.group(1)

        rows = [
            line.strip()
            for line in table_text.splitlines()
            if line.strip().startswith("|") and not re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", line.strip())
        ]
        data_rows = rows[1:]

        checkpoint_cites_found: dict[str, int] = {}
        for row in data_rows:
            cells = [c.strip() for c in row.split("|")]
            if len(cells) < 4:
                continue
            checkpoint_cell = cells[3]
            cp_match = re.search(r"`([a-z_]+)`", checkpoint_cell)
            if not cp_match:
                continue
            cp_name = cp_match.group(1)

            # Extract ladder line citation in checkpoint cell
            ladder_cites = re.findall(r"docs/PORT24_BREADCRUMB_LADDER\.md:(\d+)", checkpoint_cell)
            self.assertGreaterEqual(
                len(ladder_cites),
                1,
                f"Checkpoint cell for '{cp_name}' must cite ladder line: {checkpoint_cell}",
            )
            for line_str in ladder_cites:
                line_num = int(line_str)
                self.assertGreaterEqual(line_num, 476, f"Line {line_num} must be in 476-482 for {cp_name}")
                self.assertLessEqual(line_num, 482, f"Line {line_num} must be in 476-482 for {cp_name}")
                target_line = ladder_lines[line_num - 1]
                self.assertIn(
                    cp_name,
                    target_line,
                    f"Ladder line {line_num} ('{target_line}') must contain checkpoint name '{cp_name}'",
                )
                checkpoint_cites_found[cp_name] = line_num

        # Ensure all 7 ladder checkpoints are cited with authoritative rows 476-482
        expected_checkpoints = {
            "after_prologue": 476,
            "after_copy": 477,
            "before_dcache": 478,
            "after_dcache": 479,
            "before_icache": 480,
            "after_icache": 481,
            "before_bx": 482,
        }
        for name, expected_line in expected_checkpoints.items():
            self.assertIn(name, checkpoint_cites_found, f"Missing citation for checkpoint {name}")
            self.assertEqual(
                checkpoint_cites_found[name],
                expected_line,
                f"Checkpoint {name} must cite authoritative line {expected_line}, got {checkpoint_cites_found[name]}",
            )

    def test_target_file_placement_citation(self):
        """Verify that A/DISKBOOT.BIN file placement does not cite ladder line 35 (which is about timing) and cites actual source."""
        lines = self.content.splitlines()
        placement_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if "Target File" in line and "A/DISKBOOT.BIN" in line
        ]
        self.assertGreaterEqual(len(placement_lines), 1, "Must find Target File A/DISKBOOT.BIN line")
        for idx, line in placement_lines:
            self.assertNotIn(
                "docs/PORT24_BREADCRUMB_LADDER.md:35",
                line,
                f"Line {idx} must not cite docs/PORT24_BREADCRUMB_LADDER.md:35 for file placement: {line}",
            )
            self.assertTrue(
                "docs/PORT19_DISKBOOT_ENCODING.md" in line or "docs/PORT24_LOADER_TRACE.md" in line,
                f"Line {idx} must cite docs/PORT19_DISKBOOT_ENCODING.md or docs/PORT24_LOADER_TRACE.md for file placement: {line}",
            )
            self.assertIn("[VERIFIED", line)

    def test_card_capacity_32gb_recommendation_not_labelled_verified(self):
        """Verify per feedback (3) that:
        (a) FAT32 support and BOOTDISK 0x1E0 / SCRIPT 0x1F0 markers stay VERIFIED, citing actual source.
        (b) The 32 GB card recommendation is INFERRED (not VERIFIED), cites docs/PORT18_OWNER_TRIAL_PLAN.md:184,
            and states that source gives no SDHC-only ceiling.
        """
        lines = self.content.splitlines()

        # Check 32 GB recommendation lines
        card_32gb_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if re.search(r"32\s*GB", line, re.IGNORECASE)
            and not line.strip().startswith("#")
            and not line.strip().startswith("```")
        ]
        self.assertGreaterEqual(len(card_32gb_lines), 1, "Must find at least one line with 32 GB recommendation")

        for idx, line in card_32gb_lines:
            # Must NOT be labelled VERIFIED
            self.assertNotIn(
                "[VERIFIED",
                line,
                f"Line {idx} mentioning 32 GB must NOT be labelled VERIFIED: {line}",
            )
            # If it makes the recommendation, must be INFERRED and cite docs/PORT18_OWNER_TRIAL_PLAN.md:184
            if "recommend" in line.lower() or "capacity" in line.lower() or r"\le 32" in line or "<= 32" in line:
                self.assertIn(
                    "INFERRED",
                    line,
                    f"Line {idx} recommending 32 GB card must be labelled INFERRED: {line}",
                )
                self.assertIn(
                    "docs/PORT18_OWNER_TRIAL_PLAN.md:184",
                    line,
                    f"Line {idx} recommending 32 GB card must cite docs/PORT18_OWNER_TRIAL_PLAN.md:184: {line}",
                )
                self.assertTrue(
                    re.search(r"no SDHC-only ceiling", line, re.IGNORECASE),
                    f"Line {idx} must state that source gives no SDHC-only ceiling: {line}",
                )

        # (a) Check FAT32 support stays VERIFIED
        fat32_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if "Filesystem" in line and "FAT32" in line
        ]
        self.assertGreaterEqual(len(fat32_lines), 1, "Must find FAT32 filesystem specification row")
        for idx, line in fat32_lines:
            self.assertIn(
                "[VERIFIED",
                line,
                f"FAT32 specification row at line {idx} must be labelled VERIFIED: {line}",
            )
            self.assertIn(
                "docs/PORT19_BOOTDISK_VBR.md",
                line,
                f"FAT32 specification row at line {idx} must cite docs/PORT19_BOOTDISK_VBR.md: {line}",
            )

        # Check BOOTDISK 0x1E0 stays VERIFIED in Section 1
        bootdisk_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if idx < 60 and line.strip().startswith("|") and "BOOTDISK" in line and "0x1E0" in line
        ]
        self.assertGreaterEqual(len(bootdisk_lines), 1, "Must find BOOTDISK 0x1E0 specification row in Section 1")
        for idx, line in bootdisk_lines:
            self.assertIn(
                "[VERIFIED",
                line,
                f"BOOTDISK 0x1E0 row at line {idx} must be labelled VERIFIED: {line}",
            )

        # Check SCRIPT 0x1F0 stays VERIFIED in Section 1
        script_lines = [
            (idx, line)
            for idx, line in enumerate(lines, start=1)
            if idx < 60 and line.strip().startswith("|") and "SCRIPT" in line and "0x1F0" in line
        ]
        self.assertGreaterEqual(len(script_lines), 1, "Must find SCRIPT 0x1F0 specification row in Section 1")
        for idx, line in script_lines:
            self.assertIn(
                "[VERIFIED",
                line,
                f"SCRIPT 0x1F0 row at line {idx} must be labelled VERIFIED: {line}",
            )

    def test_binary_guard_scoped(self):
        """Verify that the files touched by this task are plain text and contain no raw binaries or ROM dumps."""
        scoped_files = [
            DOCS_SESSION_PLAN,
            Path(__file__).resolve(),
        ]
        for path in scoped_files:
            self.assertTrue(path.is_file(), f"Expected file {path} to exist")
            raw_bytes = path.read_bytes()
            # Must be valid UTF-8 text
            try:
                raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                self.fail(f"File {path.name} contains invalid UTF-8 bytes: {exc}")
            # Ensure no null bytes
            self.assertNotIn(b"\x00", raw_bytes, f"File {path.name} must not contain null bytes")


if __name__ == "__main__":
    unittest.main()
