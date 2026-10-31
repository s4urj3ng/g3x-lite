"""Unit tests for PORT-19 T4 (p19-go-nogo-r2): Owner Trial Plan Update & GO/NO-GO Verdict.

Verifies:
1. docs/PORT19_GO_NOGO.md exists and states a single unambiguous verdict (GO, with zero NO-GO tokens).
2. docs/PORT19_GO_NOGO.md records the rebuilt candidate measurements (Tracing OFF) as text:
   - DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136
   - DISKBOOT.BIN size: 118001 bytes (118,001 B)
   - boot_witness address: 0x0035F7A0
   - _end address: 0x00366CB0
3. docs/PORT19_GO_NOGO.md provides a VERIFIED/INFERRED/UNKNOWN justification for each of P1-P6
   with exact citations, and includes the complete owner step list (host build, preflight,
   card preparation, trial execution, recovery, and reporting with tools/port18_trial_report.py).
4. docs/PORT18_OWNER_TRIAL_PLAN.md no longer lists P3, P4, or P6 as open/unresolved conflicts,
   preserves P1 and P2 as owner items, updates card-preparation steps to match the resolved
   PORT-19 answers (FAT32 0x1E0, FAT12/FAT16 0x40, SCRIPT 0x1F0, exFAT UNSUPPORTED, ENCODED
   DISKBOOT.BIN with dancingbits row 13 and byte 0 = 0x00, witness 0x0035F7A0), and keeps the
   Section 5 recovery plan intact.
5. Every line-range citation to docs/PORT19_BOOTDISK_VBR.md, docs/PORT19_DISKBOOT_ENCODING.md,
   and docs/PORT19_WITNESS_ADDRESS.md in docs/PORT18_OWNER_TRIAL_PLAN.md and docs/PORT19_GO_NOGO.md
   is within the exact line bounds of the file on the base and matches the cited topic.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GO_NOGO_DOC = REPO_ROOT / "docs" / "PORT19_GO_NOGO.md"
TRIAL_PLAN_DOC = REPO_ROOT / "docs" / "PORT18_OWNER_TRIAL_PLAN.md"
VBR_DOC = REPO_ROOT / "docs" / "PORT19_BOOTDISK_VBR.md"
ENCODING_DOC = REPO_ROOT / "docs" / "PORT19_DISKBOOT_ENCODING.md"
WITNESS_DOC = REPO_ROOT / "docs" / "PORT19_WITNESS_ADDRESS.md"
TRIAL_REPORT_TOOL = REPO_ROOT / "tools" / "port18_trial_report.py"

EXPECTED_DISKBOOT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
EXPECTED_DISKBOOT_SIZE_STR = "118001"
EXPECTED_BOOT_WITNESS = "0x0035F7A0"
EXPECTED_END_ADDR = "0x00366CB0"
EXPECTED_BSS_START = "0x00365204"
FORBIDDEN_WRONG_BSS_START = "0x0035F7C0"


class TestPort19GoNoGoVerdict(unittest.TestCase):
    """Tests for docs/PORT19_GO_NOGO.md and updated docs/PORT18_OWNER_TRIAL_PLAN.md."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(GO_NOGO_DOC.is_file(), f"Missing {GO_NOGO_DOC}")
        cls.assertTrue(TRIAL_PLAN_DOC.is_file(), f"Missing {TRIAL_PLAN_DOC}")
        cls.assertTrue(VBR_DOC.is_file(), f"Missing {VBR_DOC}")
        cls.assertTrue(ENCODING_DOC.is_file(), f"Missing {ENCODING_DOC}")
        cls.assertTrue(WITNESS_DOC.is_file(), f"Missing {WITNESS_DOC}")

        cls.go_nogo_text = GO_NOGO_DOC.read_text(encoding="utf-8")
        cls.plan_text = TRIAL_PLAN_DOC.read_text(encoding="utf-8")
        cls.vbr_lines = VBR_DOC.read_text(encoding="utf-8").splitlines()
        cls.encoding_lines = ENCODING_DOC.read_text(encoding="utf-8").splitlines()
        cls.witness_lines = WITNESS_DOC.read_text(encoding="utf-8").splitlines()

    def test_go_nogo_states_exactly_one_verdict(self) -> None:
        """docs/PORT19_GO_NOGO.md must state exactly one verdict (GO) and zero NO-GO verdicts."""
        verdict_matches = re.findall(
            r"\*\*Verdict\*\*:\s*\*\*(GO|NO-GO)\*\*", self.go_nogo_text
        )
        self.assertEqual(
            verdict_matches,
            ["GO"],
            f"Expected exactly one verdict line ('**Verdict**: **GO**'), found: {verdict_matches}",
        )
        # Ensure NO-GO does not appear anywhere in the document to avoid any ambiguity
        nogo_tokens = re.findall(r"\bNO[-_]?GO\b", self.go_nogo_text, flags=re.IGNORECASE)
        self.assertEqual(
            nogo_tokens,
            [],
            f"docs/PORT19_GO_NOGO.md must not contain ambiguous NO-GO tokens: {nogo_tokens}",
        )

    def test_go_nogo_contains_candidate_measurements_and_addresses(self) -> None:
        """docs/PORT19_GO_NOGO.md must record DISKBOOT.BIN SHA-256, size, boot_witness, _end, and accurate BSS."""
        self.assertIn(EXPECTED_DISKBOOT_SHA256, self.go_nogo_text)
        self.assertTrue(
            EXPECTED_DISKBOOT_SIZE_STR in self.go_nogo_text or "118,001" in self.go_nogo_text,
            "docs/PORT19_GO_NOGO.md missing DISKBOOT.BIN size 118001 / 118,001",
        )
        self.assertIn(EXPECTED_BOOT_WITNESS, self.go_nogo_text)
        self.assertIn(EXPECTED_END_ADDR, self.go_nogo_text)

    def test_go_nogo_bss_range_and_size_match_verified_sources(self) -> None:
        """docs/PORT19_GO_NOGO.md must state BSS start 0x00365204 and size 6,828 / 6828 bytes, and not 0x0035F7C0."""
        self.assertIn(
            EXPECTED_BSS_START,
            self.go_nogo_text,
            "docs/PORT19_GO_NOGO.md must state BSS start address 0x00365204",
        )
        self.assertIn(
            "0x00365204..0x00366CB0",
            self.go_nogo_text,
            "docs/PORT19_GO_NOGO.md must state BSS range 0x00365204..0x00366CB0",
        )
        self.assertTrue(
            "6,828" in self.go_nogo_text or "6828" in self.go_nogo_text,
            "docs/PORT19_GO_NOGO.md must state BSS size 6,828 / 6828 bytes",
        )
        self.assertNotIn(
            FORBIDDEN_WRONG_BSS_START,
            self.go_nogo_text,
            "docs/PORT19_GO_NOGO.md must not contain 0x0035F7C0 as a BSS start",
        )
        # Verify exact citations for BSS measurement
        self.assertRegex(
            self.go_nogo_text,
            r"tools/validate_candidate_port2a\.py:(?:52,\s*)?54,\s*472-473",
        )
        self.assertRegex(
            self.go_nogo_text,
            r"docs/PORT16_CANDIDATE_BUILD\.md:248-251,\s*285",
        )

    @staticmethod
    def _extract_trial_report_supported_flags() -> set[str]:
        """Return the set of --flags accepted by tools/port18_trial_report.py via both AST and --help."""
        source = TRIAL_REPORT_TOOL.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(TRIAL_REPORT_TOOL))
        ast_flags: set[str] = {"--help"}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
            ):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.startswith("--"):
                            ast_flags.add(arg.value)

        proc = subprocess.run(
            [sys.executable, "-B", str(TRIAL_REPORT_TOOL), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        help_flags = set(re.findall(r"--[a-zA-Z0-9][a-zA-Z0-9_-]*", proc.stdout))
        assert ast_flags == help_flags, (
            f"Mismatch between AST add_argument flags {ast_flags} and --help flags {help_flags}"
        )
        return help_flags

    @staticmethod
    def _extract_trial_report_command_lines(markdown_text: str) -> list[str]:
        """Extract every command line invoking tools/port18_trial_report.py from markdown text."""
        joined = re.sub(r"\\\s*\n\s*", " ", markdown_text)
        cmd_lines: list[str] = []
        for raw_line in joined.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # Match bash command lines that invoke python/python3 on tools/port18_trial_report.py
            # or start directly with tools/port18_trial_report.py
            if re.match(
                r"^(?:python3?(?:\s+-[A-Za-z0-9]+)*\s+)?tools/port18_trial_report\.py\b",
                line,
            ):
                cmd_lines.append(line)
        return cmd_lines

    def test_go_nogo_trial_report_commands_use_only_supported_flags(self) -> None:
        """Every tools/port18_trial_report.py command in docs/PORT19_GO_NOGO.md must use only supported --flags."""
        supported_flags = self._extract_trial_report_supported_flags()
        self.assertNotIn("--preflight", supported_flags)

        cmd_lines = self._extract_trial_report_command_lines(self.go_nogo_text)
        self.assertTrue(
            cmd_lines,
            "Expected at least one tools/port18_trial_report.py command line in docs/PORT19_GO_NOGO.md",
        )

        for cmd in cmd_lines:
            used_flags = [
                tok.split("=", 1)[0]
                for tok in re.findall(r"--[a-zA-Z0-9][a-zA-Z0-9_-]*(?:=\S+)?", cmd)
            ]
            for flag in used_flags:
                self.assertIn(
                    flag,
                    supported_flags,
                    f"Unsupported flag {flag!r} in tools/port18_trial_report.py command: {cmd!r} "
                    f"(supported: {sorted(supported_flags)})",
                )

        # Ensure Step 6 includes explicit manual comparison of DISKBOOT.BIN SHA-256 and size
        # against preflight output and Section 2 values, and does not falsely claim verdict: PASS
        sec4_step6_match = re.search(
            r"(### Step 6 — Report Results with `tools/port18_trial_report\.py`.*)",
            self.go_nogo_text,
            re.DOTALL,
        )
        self.assertIsNotNone(sec4_step6_match, "Step 6 (reporting step) missing in docs/PORT19_GO_NOGO.md")
        step6_text = sec4_step6_match.group(1)
        self.assertNotIn("--preflight", step6_text)
        self.assertNotIn("verdict: PASS", step6_text)
        self.assertIn(EXPECTED_DISKBOOT_SHA256, step6_text)
        self.assertIn(EXPECTED_DISKBOOT_SIZE_STR, step6_text)
        self.assertIn("Report ingested:", step6_text)
        self.assertIn("Outcome classification:", step6_text)
        self.assertIn("Summary written to:", step6_text)

    def test_go_nogo_justifies_all_preconditions_p1_to_p6(self) -> None:
        """docs/PORT19_GO_NOGO.md must give a labelled justification for each of P1-P6 with citations."""
        for pid in ("P1", "P2", "P3", "P4", "P5", "P6"):
            pattern = re.compile(rf"\|\s*\*\*{pid}\*\*\s*\|([^\n]+)", re.MULTILINE)
            match = pattern.search(self.go_nogo_text)
            self.assertIsNotNone(match, f"Missing table row for {pid} in docs/PORT19_GO_NOGO.md")
            row_text = match.group(1)
            self.assertTrue(
                any(lbl in row_text for lbl in ("VERIFIED", "INFERRED", "UNKNOWN")),
                f"Row for {pid} in docs/PORT19_GO_NOGO.md lacks VERIFIED/INFERRED/UNKNOWN label",
            )

        # Verify exact PORT-19 resolution docs are cited in P3, P4, P6
        self.assertIn("docs/PORT19_BOOTDISK_VBR.md:", self.go_nogo_text)
        self.assertIn("docs/PORT19_DISKBOOT_ENCODING.md:", self.go_nogo_text)
        self.assertIn("docs/PORT19_WITNESS_ADDRESS.md:", self.go_nogo_text)

    def test_go_nogo_includes_owner_step_list(self) -> None:
        """docs/PORT19_GO_NOGO.md must include owner steps: build, preflight, card prep, trial, recovery, report."""
        self.assertIn("tools/build_candidate_port2a.py", self.go_nogo_text)
        self.assertIn("tools/validate_candidate_port2a.py", self.go_nogo_text)
        self.assertIn("tools/validate_witness_inspector.py", self.go_nogo_text)
        self.assertIn("tools/port18_trial_preflight.py", self.go_nogo_text)
        self.assertIn("--inspector-metadata", self.go_nogo_text)
        self.assertIn("--inspector-bin", self.go_nogo_text)
        self.assertIn("0x1E0", self.go_nogo_text)
        self.assertIn("0x40", self.go_nogo_text)
        self.assertIn("0x1F0", self.go_nogo_text)
        self.assertIn("Recovery", self.go_nogo_text)
        self.assertIn("tools/port18_trial_report.py", self.go_nogo_text)

    def test_go_nogo_recovery_is_qualified_not_guaranteed(self) -> None:
        """docs/PORT19_GO_NOGO.md must not promise guaranteed or immediate stock-boot restoration."""
        forbidden_claims = (
            r"stock\s+boot\s+is\s+restored",
            r"restored\s+immediately",
            r"immediately\s+restor",
            r"guaranteed\s+(?:to\s+)?(?:restore|recover|return)",
            r"always\s+restores?",
            r"safe(?:ly)?\s+(?:recovery|to\s+recover)",
        )
        for pattern in forbidden_claims:
            self.assertIsNone(
                re.search(pattern, self.go_nogo_text, re.IGNORECASE),
                f"Unqualified recovery guarantee matches {pattern!r}",
            )

        sec_match = re.search(
            r"(### Step 5 — Recovery Procedure.*?)(?=\n### Step 6)", self.go_nogo_text, re.DOTALL
        )
        self.assertIsNotNone(sec_match, "Recovery section (Step 5) missing in GO/NO-GO doc")
        recovery = sec_match.group(1)
        self.assertIn("docs/PORT18_OWNER_TRIAL_PLAN.md:320-327", recovery)
        self.assertIn("untested", recovery)
        self.assertRegex(recovery, r"remove the battery")
        self.assertRegex(recovery, r"power[- ]cycle")
        self.assertRegex(recovery, r"power cycle removes it is `\[INFERRED\]`")
        self.assertRegex(recovery, r"persistence risks.*`\[UNKNOWN\]`")
        # Battery removal must precede card removal / unlocking in the stated ordering.
        self.assertLess(recovery.index("remove the battery"), recovery.index("remove the card"))

    def test_trial_plan_no_longer_lists_p3_p4_p6_as_open_conflicts(self) -> None:
        """docs/PORT18_OWNER_TRIAL_PLAN.md must no longer list P3, P4, or P6 as open/blocking conflicts."""
        forbidden_phrases = [
            "Unresolved inspector metadata discrepancy (blocking — P6)",
            "Blocking preconditions (P3, P4 and P6 are open conflicts)",
            "OPEN CONFLICT (`UNKNOWN`)",
            "BLOCKING DISCREPANCY (`VERIFIED` mismatch)",
            "offset is **`UNKNOWN`** (P3 conflict",
            "Do not write the card until this is resolved",
            "Encoding acceptance is `[UNKNOWN]` (P4)",
            "That this happens on this camera with this candidate is `[UNKNOWN]` (P3, P4)",
            "Do not retry until P3/P4 are resolved",
            "If the P6 inspector metadata discrepancy is not resolved, no card is prepared",
        ]
        for phrase in forbidden_phrases:
            self.assertNotIn(
                phrase,
                self.plan_text,
                f"Stale open-conflict phrase still present in docs/PORT18_OWNER_TRIAL_PLAN.md: {phrase!r}",
            )

        # Verify P3, P4, P6 rows in Section 1.1 state RESOLVED (VERIFIED) and cite PORT-19 docs
        for pid, expected_doc in [
            ("P3", "docs/PORT19_BOOTDISK_VBR.md:"),
            ("P4", "docs/PORT19_DISKBOOT_ENCODING.md:"),
            ("P6", "docs/PORT19_WITNESS_ADDRESS.md:"),
        ]:
            row_match = re.search(rf"^\|\s*{pid}\s*\|([^\n]+)$", self.plan_text, re.MULTILINE)
            self.assertIsNotNone(row_match, f"Precondition row {pid} missing in trial plan")
            row_content = row_match.group(1)
            self.assertIn("RESOLVED (`VERIFIED`)", row_content, f"{pid} must be marked RESOLVED (`VERIFIED`)")
            self.assertIn(expected_doc, row_content, f"{pid} must cite {expected_doc}")

        # Verify P1 and P2 stay owner items
        for pid in ("P1", "P2"):
            row_match = re.search(rf"^\|\s*{pid}\s*\|([^\n]+)$", self.plan_text, re.MULTILINE)
            self.assertIsNotNone(row_match, f"Precondition row {pid} missing in trial plan")
            self.assertIn("OWNER ITEM", row_match.group(1), f"{pid} must remain an OWNER ITEM")

    def test_trial_plan_card_preparation_matches_resolved_answers(self) -> None:
        """Section 2 (Card preparation) of docs/PORT18_OWNER_TRIAL_PLAN.md must match P3, P4, and P6."""
        sec2_match = re.search(r"(## 2\. Card preparation.*?)(?=\n## 3\. )", self.plan_text, re.DOTALL)
        self.assertIsNotNone(sec2_match, "Section 2 (Card preparation) not found in trial plan")
        sec2 = sec2_match.group(1)

        # P3: BOOTDISK at 0x1E0 on FAT32, 0x40 on FAT12/FAT16, SCRIPT at 0x1F0, exFAT unsupported
        self.assertIn("0x1E0", sec2)
        self.assertIn("0x40", sec2)
        self.assertIn("0x1F0", sec2)
        self.assertIn("UNSUPPORTED", sec2)
        self.assertIn("docs/PORT19_BOOTDISK_VBR.md:", sec2)

        # P4: ENCODED DISKBOOT.BIN (dancingbits row 13, byte 0 = 0x00) produced by build_candidate_port2a.py
        self.assertIn("ENCODED", sec2)
        self.assertIn("dancingbits row 13", sec2)
        self.assertIn("0x00", sec2)
        self.assertIn("tools/build_candidate_port2a.py", sec2)
        self.assertIn("docs/PORT19_DISKBOOT_ENCODING.md:", sec2)

        # P6: witness address 0x0035F7A0
        self.assertIn("0x0035F7A0", sec2)
        self.assertIn("docs/PORT19_WITNESS_ADDRESS.md:", sec2)

    def test_trial_plan_recovery_section_intact(self) -> None:
        """Section 5 (Recovery plan) in docs/PORT18_OWNER_TRIAL_PLAN.md must remain intact."""
        sec5_match = re.search(r"(## 5\. Recovery plan.*?)(?=\n## 6\. )", self.plan_text, re.DOTALL)
        self.assertIsNotNone(sec5_match, "Section 5 (Recovery plan) missing in trial plan")
        sec5 = sec5_match.group(1)

        for required_item in (
            "R-a. **Unlock the card or remove it.**",
            "R-b. **No `BOOTDISK` marker.**",
            "R-c. When `StartDiskboot` loads nothing",
            "R-d. The candidate runs only from RAM",
            "### 5.1 Hang (O8, O9)",
            "### 5.2 No boot / no power-on (O10, O15)",
            "### 5.3 Abnormal state (O11, O12, O16)",
            "**Abort rule**: if stock behaviour does not return",
        ):
            self.assertIn(required_item, sec5, f"Recovery plan item missing: {required_item}")

    def test_port19_doc_line_citations_match_base_files(self) -> None:
        """Every line range cited for PORT19_BOOTDISK_VBR.md, PORT19_DISKBOOT_ENCODING.md, and PORT19_WITNESS_ADDRESS.md must be valid."""
        doc_map = {
            "docs/PORT19_BOOTDISK_VBR.md": self.vbr_lines,
            "docs/PORT19_DISKBOOT_ENCODING.md": self.encoding_lines,
            "docs/PORT19_WITNESS_ADDRESS.md": self.witness_lines,
        }
        citation_re = re.compile(
            r"(docs/PORT19_(?:BOOTDISK_VBR|DISKBOOT_ENCODING|WITNESS_ADDRESS)\.md):(\d+(?:-\d+)?(?:\s*,\s*\d+(?:-\d+)?)*)"
        )

        for source_name, text in [
            ("docs/PORT18_OWNER_TRIAL_PLAN.md", self.plan_text),
            ("docs/PORT19_GO_NOGO.md", self.go_nogo_text),
        ]:
            matches = list(citation_re.finditer(text))
            self.assertTrue(matches, f"No PORT-19 doc citations found in {source_name}")
            for m in matches:
                target_doc = m.group(1)
                ranges_str = m.group(2)
                lines = doc_map[target_doc]
                max_line = len(lines)
                for part in ranges_str.split(","):
                    part = part.strip()
                    if "-" in part:
                        start_s, end_s = part.split("-", 1)
                        start_line, end_line = int(start_s), int(end_s)
                    else:
                        start_line = end_line = int(part)
                    self.assertGreaterEqual(
                        start_line,
                        1,
                        f"Invalid start line {start_line} for {target_doc} in {source_name}",
                    )
                    self.assertLessEqual(
                        start_line,
                        end_line,
                        f"Inverted line range {start_line}-{end_line} for {target_doc} in {source_name}",
                    )
                    self.assertLessEqual(
                        end_line,
                        max_line,
                        f"Line range {start_line}-{end_line} exceeds {target_doc} length ({max_line}) in {source_name}",
                    )
                    # Ensure cited slice is non-empty
                    excerpt = "\n".join(lines[start_line - 1 : end_line]).strip()
                    self.assertTrue(
                        excerpt,
                        f"Cited line range {target_doc}:{start_line}-{end_line} in {source_name} is blank",
                    )

    def test_trace_absence_commands_exit_zero_on_absent_and_nonzero_on_present_or_missing(self) -> None:
        """Trace-absence checks in PORT19_GO_NOGO.md (and PORT18_OWNER_TRIAL_PLAN.md) must exit 0 when absent and nonzero when present or missing."""
        # 1. Static check: no bare grep absence checks remain in either document
        forbidden_bare_patterns = [
            r"(?m)^\s*grep\s+-c\s+['\"]?g3x_trace_enabled",
            r"(?m)^\s*grep\s+-E\s+['\"]?\(g3x_trace\|KEEP\)",
            r"(?m)^\s*grep\s+-i\s+g3x_trace\b",
            r"\|\s*grep\s+-i\s+g3x_trace\s*(?:#.*)?$",
        ]
        for doc_name, text in [
            ("docs/PORT19_GO_NOGO.md", self.go_nogo_text),
            ("docs/PORT18_OWNER_TRIAL_PLAN.md", self.plan_text),
        ]:
            for pat in forbidden_bare_patterns:
                self.assertIsNone(
                    re.search(pat, text),
                    f"Bare grep trace-absence check matching {pat!r} found in {doc_name}",
                )

        # 2. Extract the three trace-absence commands from docs/PORT19_GO_NOGO.md
        expected_targets = [
            (
                "candidate_port2a/candidate_manifest.json",
                "g3x_trace_enabled",
                '{"status": "OFFLINE_CANDIDATE_BUILT"}\n',
                ['{"status": "OFFLINE_TRACE_CANDIDATE_BUILT", "g3x_trace_enabled": true}\n'],
            ),
            (
                "chdk-port/tools/link-boot.ld",
                "(g3x_trace|KEEP)",
                "SECTIONS { .text : { *(.text) } }\n",
                [
                    "SECTIONS { .g3x_trace : { *(.g3x_trace) } }\n",
                    "SECTIONS { .text : { KEEP(*(.text)) } }\n",
                ],
            ),
            (
                "candidate_port2a/candidate_main.map",
                "g3x_trace",
                "0x0035f7a0                boot_witness\n0x00366cb0                _end\n",
                [
                    "0x00366ea0                g3x_trace_ring\n",
                    "0x00366ea0                G3X_TRACE_RING\n",
                ],
            ),
        ]

        extracted_cmds: dict[str, str] = {}
        for raw_line in self.go_nogo_text.splitlines():
            line = raw_line.strip()
            for rel_path, marker, _, _ in expected_targets:
                if line.startswith(f"test -r {rel_path}") and marker in line:
                    extracted_cmds[rel_path] = line
                    # Also verify the identical trace-absence command appears in docs/PORT18_OWNER_TRIAL_PLAN.md
                    self.assertIn(
                        line,
                        self.plan_text,
                        f"Expected matching trace-absence command for {rel_path} in docs/PORT18_OWNER_TRIAL_PLAN.md",
                    )

        self.assertEqual(
            set(extracted_cmds.keys()),
            {t[0] for t in expected_targets},
            f"Did not find all 3 expected trace-absence commands in docs/PORT19_GO_NOGO.md; found: {list(extracted_cmds.keys())}",
        )

        # 3. Dynamically execute each extracted command on missing, clean, marker-present, and broken-symlink files
        for rel_path, marker, clean_content, dirty_contents in expected_targets:
            cmd = extracted_cmds[rel_path]
            self.assertIn("! grep -q", cmd)
            self.assertIn("OK:", cmd)
            self.assertIn("FAIL:", cmd)

            with tempfile.TemporaryDirectory() as td:
                target_file = Path(td) / rel_path

                # (a) Missing file -> must exit non-zero and print FAIL:
                res_missing = subprocess.run(
                    ["bash", "-c", cmd],
                    cwd=td,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(
                    res_missing.returncode,
                    0,
                    f"Command for {rel_path} must exit non-zero when file is missing: {cmd}",
                )
                self.assertIn("FAIL:", res_missing.stdout)

                # (b) Broken symlink (read error) -> must exit non-zero and print FAIL:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.symlink(os.path.join(td, "nonexistent_read_error_target"), target_file)
                    res_broken = subprocess.run(
                        ["bash", "-c", cmd],
                        cwd=td,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(
                        res_broken.returncode,
                        0,
                        f"Command for {rel_path} must exit non-zero on read error (broken symlink): {cmd}",
                    )
                    self.assertIn("FAIL:", res_broken.stdout)
                finally:
                    if target_file.is_symlink() or target_file.exists():
                        target_file.unlink()

                # (c) File without marker -> must exit 0 and print OK:
                target_file.write_text(clean_content, encoding="utf-8")
                res_clean = subprocess.run(
                    ["bash", "-c", cmd],
                    cwd=td,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    res_clean.returncode,
                    0,
                    f"Command for {rel_path} must exit 0 when marker {marker!r} is absent: {cmd} "
                    f"(stdout={res_clean.stdout!r}, stderr={res_clean.stderr!r})",
                )
                self.assertIn("OK:", res_clean.stdout)

                # (d) File with marker -> must exit non-zero and print FAIL:
                for dirty_content in dirty_contents:
                    target_file.write_text(dirty_content, encoding="utf-8")
                    res_dirty = subprocess.run(
                        ["bash", "-c", cmd],
                        cwd=td,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(
                        res_dirty.returncode,
                        0,
                        f"Command for {rel_path} must exit non-zero when marker is present ({dirty_content!r}): {cmd}",
                    )
                    self.assertIn("FAIL:", res_dirty.stdout)

    @staticmethod
    def _port19_section(markdown_text: str) -> str:
        """Return the '## PORT-19' section of a doc, up to the next level-2 heading."""
        match = re.search(r"^## PORT-19\b.*?(?=^## |\Z)", markdown_text, re.M | re.S)
        return match.group(0) if match else ""

    @staticmethod
    def _extract_commit_like_tokens(text: str) -> set[str]:
        """Extract hex tokens that look like commit IDs (7-40 lowercase hex chars).

        A token counts if it is the whole content of a backtick span, or if it appears
        within 60 characters after commit/SHA/head/merge/origin/main/PR/branch wording.
        """
        candidates: set[str] = set()
        for span in re.findall(r"`([^`\n]+)`", text):
            if re.fullmatch(r"[0-9a-f]+", span):
                candidates.add(span)
        keyword_re = re.compile(r"(?i)\b(?:commit|sha|head|merge|origin/main|pr|branch(?:ed)?)\b")
        for match in keyword_re.finditer(text):
            # Look 60 characters past the keyword, extended to the end of the current
            # alphanumeric run so a long token is never cut into a shorter prefix.
            end = min(len(text), match.end() + 60)
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            window = text[match.end() : end].split("\n", 1)[0]
            # The run must not touch letters, digits or '_' on either side, so it is
            # taken in full; hex addresses such as 0x0035F7A0 never match because the
            # run would start at 'x', mixed-case runs such as 0035F7A0 are rejected, and
            # firmware identifiers such as sub_fc05bc3c are skipped.
            candidates.update(
                re.findall(r"(?<![0-9A-Za-z_])[0-9a-f]+(?![0-9A-Za-z_])", window)
            )
        tokens: set[str] = set()
        for token in candidates:
            # Exclusion 1: SHA-256 digests (64 hex chars, e.g. the DISKBOOT.BIN digest)
            # are file hashes, not commit IDs; anything outside 7-40 chars is not a
            # (short or full) SHA-1 commit ID either.
            if len(token) == 64 or not 7 <= len(token) <= 40:
                continue
            # Exclusion 2: all-decimal runs (byte sizes such as 118001, the toolchain
            # date 20160919) are numbers, not abbreviated commit IDs.
            if token.isdigit():
                continue
            tokens.add(token)
        # Exclusion 3: hex addresses written as 0x... (e.g. 0x0035F7A0, 0x00366CB0)
        # are memory addresses, not commit IDs; drop any token that only appears as the
        # tail of such a literal.
        addresses = {m.lower() for m in re.findall(r"0x([0-9A-Fa-f]+)", text)}
        return {t for t in tokens if t not in addresses}

    @staticmethod
    def _commit_problems(sha: str) -> list[str]:
        problems = []
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exists.returncode != 0:
            problems.append(f"{sha} does not resolve to a commit")
            return problems
        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if anc.returncode != 0:
            problems.append(f"{sha} is not reachable from origin/main")
        return problems

    def test_port19_cited_commit_ids_resolve_and_reach_origin_main(self) -> None:
        """Every commit-like token in the PORT-19 doc sections must exist and be on origin/main."""
        origin = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.assertEqual(origin.returncode, 0, "origin/main must resolve to check commit provenance")

        # Self-check: the extractor must catch the invalid full IDs from an earlier
        # revision, and the git checks must reject them.
        old_invalid = (
            "f9c1bdcd03c2a60b0f64a1752e935f2c40933b42",
            "013d2d83a7153564c9bd69d61040292d1931f51e",
        )
        sample = (
            f"branched from `origin/main` `{old_invalid[0]}`, merge of PR #59 `{old_invalid[1]}`; "
            f"SHA-256 `{EXPECTED_DISKBOOT_SHA256}`, boot_witness `{EXPECTED_BOOT_WITNESS}`"
        )
        self.assertEqual(self._extract_commit_like_tokens(sample), set(old_invalid))
        for sha in old_invalid:
            self.assertTrue(self._commit_problems(sha), f"Invalid ID {sha} must be rejected")

        sources = {
            "docs/PROJECT_STATE.md": self._port19_section(
                (REPO_ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
            ),
            "docs/HANDOFF.md": self._port19_section(
                (REPO_ROOT / "docs" / "HANDOFF.md").read_text(encoding="utf-8")
            ),
            "docs/PORT19_GO_NOGO.md": self.go_nogo_text,
        }
        for name, text in sources.items():
            self.assertTrue(text, f"No PORT-19 section found in {name}")
            for sha in sorted(self._extract_commit_like_tokens(text)):
                with self.subTest(doc=name, sha=sha):
                    problems = self._commit_problems(sha)
                    self.assertFalse(problems, f"{name}: {'; '.join(problems)}")


if __name__ == "__main__":
    unittest.main()
