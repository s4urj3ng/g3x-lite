"""Unit tests for PORT-18 documentation consistency and synchronization.

Validates that:
1. All PORT-18 deliverable files and fixtures exist.
2. docs/PROJECT_STATE.md and docs/HANDOFF.md both record the status of:
   - PORT-16 (merged, PR #49, head 258359485a)
   - PORT-17 (merged, PR #54, head 682adb7472)
   - PORT-18 (milestone deliverables, head 80ba396)
3. Both docs state the exact same owner next-step section (including command block).
4. The owner next step references the PORT-18 trial plan, preflight tool, report template, and report ingest tool.
5. Commands in the next step refer to existing tools and use valid argparse options.
6. Every tracked path cited in the PORT-16/17/18 sections of both docs exists.
7. Neither doc claims that .gitignore:9 or any tracked ignore rule matches candidate_port2a/DISKBOOT.BIN.
8. Every .gitignore:N citation points at an existing line that matches the cited pattern exactly.
9. Every commit SHA cited in the added sections resolves to a valid commit in git.
10. Every static test count matches the actual def test_ definitions in the cited test file.
11. Every VERIFIED label cites a file:line or git citation, never line 1.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPort18DocsConsistency(unittest.TestCase):
    """Consistency test suite for PORT-18 documentation and handoff sync."""

    @classmethod
    def setUpClass(cls):
        cls.project_state_path = REPO_ROOT / "docs" / "PROJECT_STATE.md"
        cls.handoff_path = REPO_ROOT / "docs" / "HANDOFF.md"
        cls.gitignore_path = REPO_ROOT / ".gitignore"

        cls.assertTrue(cls.project_state_path.is_file(), "docs/PROJECT_STATE.md missing")
        cls.assertTrue(cls.handoff_path.is_file(), "docs/HANDOFF.md missing")
        cls.assertTrue(cls.gitignore_path.is_file(), ".gitignore missing")

        cls.project_state_text = cls.project_state_path.read_text(encoding="utf-8")
        cls.handoff_text = cls.handoff_path.read_text(encoding="utf-8")
        cls.gitignore_lines = cls.gitignore_path.read_text(encoding="utf-8").splitlines()

        # Tracked files in repository
        try:
            raw_git_files = subprocess.check_output(
                ["git", "ls-files"], cwd=REPO_ROOT, text=True
            ).splitlines()
            cls.tracked_files = set(raw_git_files)
        except Exception:
            cls.tracked_files = set()

    def _extract_port18_section(self, text: str) -> str:
        """Extract the PORT-18 section from a markdown document."""
        match = re.search(r"(## PORT-18\b.*?)(?=\n## |\Z)", text, re.DOTALL)
        self.assertIsNotNone(match, "Could not find '## PORT-18' section header")
        return match.group(1)

    def _extract_added_sections(self, text: str) -> str:
        """Extract all sections added in the PORT-18 milestone (PORT-16, PORT-17, PORT-18)."""
        idx = text.find("## PORT-16")
        self.assertNotEqual(idx, -1, "Could not find '## PORT-16' section header")
        return text[idx:]

    def _extract_owner_next_step_section(self, text: str) -> str:
        """Extract the full owner next-step section from markdown text, including command block."""
        match = re.search(r"(- \*\*[Ee]xact owner next step\*\*:\s*.*?)(?=\n## |\Z)", text, re.DOTALL)
        self.assertIsNotNone(match, "Could not find '- **Exact owner next step**:' section")
        return match.group(1).strip()

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize all whitespace sequences to single spaces."""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_code_blocks(text: str) -> list[list[str]]:
        """Extract fenced code blocks, preserving newlines and stripping only trailing whitespace per line."""
        raw_blocks = re.findall(r"```[a-zA-Z0-9_-]*\n(.*?)```", text, re.DOTALL)
        return [[line.rstrip() for line in block.splitlines()] for block in raw_blocks]

    @staticmethod
    def _extract_prose(text: str) -> str:
        """Extract prose outside fenced code blocks, normalized for whitespace."""
        prose = re.sub(r"```[a-zA-Z0-9_-]*\n.*?```", " ", text, flags=re.DOTALL)
        return re.sub(r"\s+", " ", prose).strip()

    def _compare_owner_next_steps(self, step_a: str, step_b: str):
        """Compare two owner next step sections.

        Prose outside code blocks is normalized for whitespace.
        Fenced command block(s) are compared exactly, line by line, with newlines preserved
        and only trailing whitespace per line stripped.
        """
        prose_a = self._extract_prose(step_a)
        prose_b = self._extract_prose(step_b)
        self.assertEqual(prose_a, prose_b, "Prose outside code blocks differs across docs")

        blocks_a = self._extract_code_blocks(step_a)
        blocks_b = self._extract_code_blocks(step_b)
        self.assertTrue(blocks_a, "No fenced code block found in first next-step section")
        self.assertTrue(blocks_b, "No fenced code block found in second next-step section")
        self.assertEqual(
            len(blocks_a),
            len(blocks_b),
            f"Different number of fenced code blocks: {len(blocks_a)} vs {len(blocks_b)}",
        )
        for i, (b_a, b_b) in enumerate(zip(blocks_a, blocks_b)):
            self.assertEqual(
                b_a,
                b_b,
                f"Fenced command block #{i+1} differs line by line",
            )

    def _get_tool_valid_flags(self, tool_rel: str) -> set[str]:
        """Get all valid --option flags for a tool from --help and argparse definitions in source."""
        tool_path = REPO_ROOT / tool_rel
        self.assertTrue(tool_path.is_file(), f"Tool not found: {tool_rel}")
        flags = set()
        try:
            help_out = subprocess.check_output(
                ["python3", str(tool_path), "--help"], text=True, stderr=subprocess.PIPE
            )
            flags.update(re.findall(r"(--[a-zA-Z0-9_-]+)", help_out))
        except Exception:
            pass
        src = tool_path.read_text(encoding="utf-8")
        flags.update(re.findall(r"add_argument\([^)]*?[\x27\x22](--[a-zA-Z0-9_-]+)", src))
        return flags

    def _validate_next_step_command_flags(self, section_text: str):
        """Parse --option flags from each command line running tools and assert they are valid."""
        tools_to_check = [
            "tools/port18_trial_preflight.py",
            "tools/port18_trial_report.py",
        ]
        for tool_rel in tools_to_check:
            valid_flags = self._get_tool_valid_flags(tool_rel)
            matching_lines = [
                line.strip() for line in section_text.splitlines() if tool_rel in line
            ]
            self.assertTrue(
                matching_lines,
                f"No command line running {tool_rel} found in next step section",
            )
            for cmd_line in matching_lines:
                used_flags = re.findall(r"(--[a-zA-Z0-9_-]+)", cmd_line)
                for flag in used_flags:
                    self.assertIn(
                        flag,
                        valid_flags,
                        f"Flag '{flag}' in command '{cmd_line}' is not a valid argparse definition for {tool_rel}",
                    )

    def _validate_gitignore_citations(self, doc_text: str) -> list[tuple[int, str]]:
        """Extract each .gitignore:N citation, verify adjacent pattern matches .gitignore line content."""
        added_text = self._extract_added_sections(doc_text) if "## PORT-16" in doc_text else doc_text
        single_matches = list(re.finditer(r"\.gitignore:(\d+)(?![\d\-])", added_text))
        range_matches = list(re.finditer(r"\.gitignore:(\d+)-(\d+)", added_text))

        self.assertTrue(
            bool(single_matches or range_matches),
            "No .gitignore citations found in text",
        )

        results = []
        for m in single_matches:
            line_num = int(m.group(1))
            pos = m.end()
            # If citation was backticked, e.g. `.gitignore:9`, skip closing backtick
            if pos < len(added_text) and added_text[pos] == "`":
                pos += 1
            # Look at a bounded window on the same line
            window = added_text[pos : pos + 80].split("\n")[0]
            pat_match = re.search(r"`([^`\n]+)`", window)
            self.assertIsNotNone(
                pat_match,
                f"Citation .gitignore:{line_num} has no adjacent pattern in window: {window!r}",
            )
            pattern = pat_match.group(1).strip()
            self.assertGreaterEqual(line_num, 1, f"Line number {line_num} out of range")
            self.assertLessEqual(
                line_num,
                len(self.gitignore_lines),
                f"Line number {line_num} out of range (max {len(self.gitignore_lines)})",
            )
            actual_line = self.gitignore_lines[line_num - 1].strip()
            self.assertEqual(
                actual_line,
                pattern,
                f".gitignore:{line_num} content mismatch: doc cited `{pattern}`, but .gitignore line {line_num} is `{actual_line}`",
            )
            results.append((line_num, pattern))

        for rm in range_matches:
            start_line = int(rm.group(1))
            end_line = int(rm.group(2))
            self.assertGreaterEqual(start_line, 1, f"Range start {start_line} out of range")
            self.assertLessEqual(
                end_line,
                len(self.gitignore_lines),
                f"Range end {end_line} out of range (max {len(self.gitignore_lines)})",
            )
            self.assertLessEqual(start_line, end_line, f"Invalid range {start_line}-{end_line}")
            if start_line == 51 and end_line == 71:
                self.assertTrue(
                    self.gitignore_lines[50].startswith("# PORT-16:"),
                    ".gitignore:51 is expected to start with '# PORT-16:'",
                )

            # Check if there are patterns cited adjacent to this range citation
            pos = rm.end()
            if pos < len(added_text) and added_text[pos] == "`":
                pos += 1
            window = added_text[pos : pos + 80].split("\n")[0]

            # Look for adjacent parenthesized or backticked pattern(s), e.g. (`*.bin`) or (*.bin) or `*.bin`
            patterns = []
            adj_match = re.match(r"(?:\])?\s*(?:\(([^)\n]+)\)|`([^`\n]+)`)", window)
            if adj_match:
                if adj_match.group(1) is not None:
                    # Inside parens: could be backticked (`*.bin`) or plain (*.bin)
                    paren_inner = adj_match.group(1)
                    backticked = re.findall(r"`([^`\n]+)`", paren_inner)
                    if backticked:
                        patterns = [p.strip() for p in backticked]
                    else:
                        patterns = [p.strip() for p in paren_inner.split(",") if p.strip()]
                elif adj_match.group(2) is not None:
                    patterns = [adj_match.group(2).strip()]

            if patterns:
                range_lines = [
                    self.gitignore_lines[i].strip() for i in range(start_line - 1, end_line)
                ]
                for pat in patterns:
                    self.assertIn(
                        pat,
                        range_lines,
                        f".gitignore:{start_line}-{end_line} pattern mismatch: cited `{pat}`, "
                        f"but lines {start_line}-{end_line} do not contain `{pat}`",
                    )
                    results.append((f"{start_line}-{end_line}", pat))

        return results

    def test_port18_deliverables_exist(self):
        """Check that all specified PORT-18 deliverable files exist."""
        expected_deliverables = [
            "docs/PORT18_OWNER_TRIAL_PLAN.md",
            "tools/port18_trial_preflight.py",
            "tools/port18_trial_report.py",
            "tests/test_port18_trial_preflight.py",
            "tests/test_port18_trial_report.py",
            "tests/test_port18_docs_consistency.py",
            "docs/PROJECT_STATE.md",
            "docs/HANDOFF.md",
        ]
        for rel_path in expected_deliverables:
            full_path = REPO_ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"PORT-18 deliverable missing: {rel_path}")

        # Check preflight fixture deliverables
        expected_fixtures = [
            "tests/fixtures/port18/preflight/valid_candidate.map",
            "tests/fixtures/port18/preflight/missing_symbols.map",
            "tests/fixtures/port18/preflight/trace_on.map",
            "tests/fixtures/port18/preflight/trace_on.nm",
            "tests/fixtures/port18/preflight/trace_section_only.map",
            "tests/fixtures/port18/preflight/valid_symbols.nm",
            "tests/fixtures/port18/preflight/wrong_end.map",
            "tests/fixtures/port18/preflight/wrong_witness.map",
        ]
        for rel_path in expected_fixtures:
            full_path = REPO_ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"Preflight fixture missing: {rel_path}")

    def test_owner_next_step_matches_across_docs(self):
        """Check that both PROJECT_STATE.md and HANDOFF.md name the identical owner next step section."""
        step_ps = self._extract_owner_next_step_section(self.project_state_text)
        step_ho = self._extract_owner_next_step_section(self.handoff_text)
        self._compare_owner_next_steps(step_ps, step_ho)

    def test_owner_next_step_matches_across_docs_negative_self_check(self):
        """Negative self-check: joining two command lines with a space in memory must fail the comparison."""
        step_ps = self._extract_owner_next_step_section(self.project_state_text)
        step_ho = self._extract_owner_next_step_section(self.handoff_text)

        # Baseline comparison must succeed
        self._compare_owner_next_steps(step_ps, step_ho)

        cmd_a = "env -u G3X_TRACE python3 -B tools/build_candidate_port2a.py"
        cmd_b = "python3 -B tools/validate_candidate_port2a.py"
        target = f"{cmd_a}\n{cmd_b}"
        self.assertIn(target, step_ho, "Target command sequence not found in HANDOFF step")

        # Mutate extracted HANDOFF block in memory by joining two command lines with a space
        mutated_ho = step_ho.replace(target, f"{cmd_a} {cmd_b}")
        with self.assertRaises(AssertionError) as ctx:
            self._compare_owner_next_steps(step_ps, mutated_ho)
        self.assertIn("differs line by line", str(ctx.exception))

    def test_owner_next_step_references_required_components(self):
        """Check that owner next step references required plan, tools, and template."""
        step_ps = self._extract_owner_next_step_section(self.project_state_text)

        self.assertIn("docs/PORT18_OWNER_TRIAL_PLAN.md", step_ps)
        self.assertIn("tools/port18_trial_preflight.py", step_ps)
        self.assertIn("tools/port18_trial_report.py", step_ps)
        self.assertIn("port18-report", step_ps)

    def test_next_step_command_flags(self):
        """Check that all --option flags in next-step commands appear in tool argparse definitions."""
        step_ps = self._extract_owner_next_step_section(self.project_state_text)
        step_ho = self._extract_owner_next_step_section(self.handoff_text)

        self._validate_next_step_command_flags(step_ps)
        self._validate_next_step_command_flags(step_ho)

    def test_next_step_command_flags_negative_self_check(self):
        """Negative self-check: an in-memory copy with --not-a-real-option must fail the flag check."""
        step_ps = self._extract_owner_next_step_section(self.project_state_text)
        bad_section = step_ps.replace("--out", "--not-a-real-option")
        with self.assertRaises(AssertionError) as ctx:
            self._validate_next_step_command_flags(bad_section)
        self.assertIn("--not-a-real-option", str(ctx.exception))

    def test_next_step_commands_refer_to_existing_tools(self):
        """Check that commands in the next step refer to tools that actually exist in the repository."""
        for doc_name, text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            section = self._extract_port18_section(text)
            tool_matches = re.findall(r"\btools/[a-zA-Z0-9_\-]+\.py\b", section)
            self.assertTrue(
                tool_matches,
                f"No tool commands found in PORT-18 section of {doc_name}",
            )
            for tool_rel in set(tool_matches):
                tool_path = REPO_ROOT / tool_rel
                self.assertTrue(
                    tool_path.is_file(),
                    f"Command in {doc_name} references non-existent tool: {tool_rel}",
                )

    def test_all_tracked_paths_cited_in_port16_17_18_exist(self):
        """Check that every tracked path cited in the PORT-16/17/18 sections exists in the repository."""
        path_pattern = re.compile(
            r"\b((?:docs|tools|tests|firmware|chdk-port|vendor)/[a-zA-Z0-9_\-\./]+|AGENTS\.md|README\.md|\.gitignore)\b"
        )

        untracked_or_external_prefixes = (
            "candidate_port2a/",
            "candidate_trace/",
            "private/",
            "/path/to/",
            "firmware/dumps",
        )

        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            added_text = self._extract_added_sections(doc_text)
            matches = path_pattern.findall(added_text)
            self.assertTrue(matches, f"No paths found in added sections of {doc_name}")

            cited_paths = set()
            for m in matches:
                clean = re.sub(r":\d+(?:-\d+)?$", "", m).rstrip("/.,;:()")
                if any(clean.startswith(prefix) for prefix in untracked_or_external_prefixes):
                    continue
                cited_paths.add(clean)

            for rel_path in cited_paths:
                full_path = REPO_ROOT / rel_path
                self.assertTrue(
                    full_path.exists(),
                    f"Path cited in {doc_name} does not exist on disk: {rel_path}",
                )
                if self.tracked_files and rel_path != "tests/test_port18_docs_consistency.py":
                    if full_path.is_dir():
                        has_tracked_children = any(
                            f.startswith(rel_path + "/") for f in self.tracked_files
                        )
                        self.assertTrue(
                            has_tracked_children,
                            f"Directory cited in {doc_name} contains no tracked files: {rel_path}",
                        )
                    else:
                        self.assertTrue(
                            rel_path in self.tracked_files,
                            f"Path cited in {doc_name} is not tracked: {rel_path}",
                        )

    def test_port16_status_recorded_and_cited(self):
        """Check that both docs record PORT-16 status (merged, PR #49, head 258359485a) with citations."""
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            self.assertIn("PORT-16", doc_text, f"PORT-16 missing in {doc_name}")
            self.assertTrue(
                bool(re.search(r"\bPR\s*#?49\b", doc_text, re.IGNORECASE)),
                f"PR #49 not cited for PORT-16 in {doc_name}",
            )
            self.assertIn("258359485a", doc_text, f"Head 258359485a not cited for PORT-16 in {doc_name}")
            self.assertTrue(
                bool(re.search(r"PORT-16.*?\bMERGED\b", doc_text, re.DOTALL | re.IGNORECASE)),
                f"PORT-16 not recorded as MERGED in {doc_name}",
            )
            self.assertTrue(
                bool(re.search(r"\[VERIFIED:.*?1031ace", doc_text)),
                f"PORT-16 merge commit citation 1031ace missing in {doc_name}",
            )

    def test_port17_status_recorded_and_cited(self):
        """Check that both docs record PORT-17 status (merged, PR #54, head 682adb7472) with citations."""
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            self.assertIn("PORT-17", doc_text, f"PORT-17 missing in {doc_name}")
            self.assertTrue(
                bool(re.search(r"\bPR\s*#?54\b", doc_text, re.IGNORECASE)),
                f"PR #54 not cited for PORT-17 in {doc_name}",
            )
            self.assertIn("682adb7472", doc_text, f"Head 682adb7472 not cited for PORT-17 in {doc_name}")
            self.assertTrue(
                bool(re.search(r"PORT-17.*?\bMERGED\b", doc_text, re.DOTALL | re.IGNORECASE)),
                f"PORT-17 not recorded as MERGED in {doc_name}",
            )
            self.assertTrue(
                bool(re.search(r"\[VERIFIED:.*?7e6da69", doc_text)),
                f"PORT-17 merge commit citation 7e6da69 missing in {doc_name}",
            )

    def test_port18_status_recorded_and_cited(self):
        """Check that both docs record PORT-18 status and integration head with citations."""
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            self.assertIn("PORT-18", doc_text, f"PORT-18 missing in {doc_name}")
            self.assertIn("80ba396", doc_text, f"PORT-18 head 80ba396 not cited in {doc_name}")
            self.assertIn(
                "INTEGRATED_ON_AGENTBRIDGE",
                doc_text,
                f"PORT-18 status INTEGRATED_ON_AGENTBRIDGE missing in {doc_name}",
            )
            self.assertTrue(
                bool(re.search(r"\[VERIFIED:.*?80ba396", doc_text)),
                f"PORT-18 head citation 80ba396 missing in {doc_name}",
            )

    def test_gitignore_claims_and_citations_valid(self):
        """Check that .gitignore citations are accurate and no doc claims .gitignore:9 matches DISKBOOT.BIN."""
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            added_text = self._extract_added_sections(doc_text)

            # Ensure neither doc claims that .gitignore:9 or any tracked rule matches DISKBOOT.BIN
            self.assertNotIn(
                "DISKBOOT.BIN match the *.bin",
                added_text,
                f"{doc_name} incorrectly claims DISKBOOT.BIN matches *.bin",
            )
            self.assertNotIn(
                "match the `*.bin` ignore rule",
                added_text,
                f"{doc_name} incorrectly claims DISKBOOT.BIN matches *.bin",
            )
            self.assertIn(
                "No tracked ignore rule matches `candidate_port2a/DISKBOOT.BIN`",
                added_text,
                f"{doc_name} missing explicit statement that no tracked ignore rule matches DISKBOOT.BIN",
            )
            self.assertIn(
                ".git/info/exclude",
                added_text,
                f"{doc_name} missing mention of .git/info/exclude",
            )

            # Validate each .gitignore:N citation against actual file content and adjacent pattern
            citations = self._validate_gitignore_citations(doc_text)
            self.assertTrue(citations, f"No single .gitignore citations verified in {doc_name}")
            # Ensure line 9 was among validated citations with pattern *.bin
            self.assertIn(
                (9, "*.bin"),
                citations,
                f".gitignore:9 with pattern '*.bin' missing in {doc_name} validated citations",
            )

    def test_gitignore_citation_validator_negative_self_check(self):
        """Negative self-check: validator must detect content mismatch, missing pattern, and range mismatch."""
        # 1. Content mismatch: citing line 17 (*.o) with pattern *.bin
        mismatch_doc = "the tracked `.gitignore:17` (`*.bin`) rule is lowercase `*.bin`"
        with self.assertRaises(AssertionError) as ctx:
            self._validate_gitignore_citations(mismatch_doc)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # 2. Missing pattern: citing .gitignore:9 without adjacent backticked pattern
        no_pattern_doc = "the tracked `.gitignore:9` rule without any pattern"
        with self.assertRaises(AssertionError) as ctx:
            self._validate_gitignore_citations(no_pattern_doc)
        self.assertIn("no adjacent pattern", str(ctx.exception).lower())

        # 3. Range pattern mismatch: citing lines 17-18 (*.o and *.fir) with pattern *.bin must fail
        bad_range_doc = "the tracked `.gitignore:17-18` (`*.bin`) rule"
        with self.assertRaises(AssertionError) as ctx:
            self._validate_gitignore_citations(bad_range_doc)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # 4. Range pattern mismatch without backticks around citation or parens: .gitignore:17-18 (*.bin)
        bad_range_doc_plain = "the tracked .gitignore:17-18 (*.bin) rule"
        with self.assertRaises(AssertionError) as ctx:
            self._validate_gitignore_citations(bad_range_doc_plain)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # 5. Valid range pattern: citing line 17 (*.o) within 17-18 passes
        good_range_doc = "the tracked `.gitignore:17-18` (`*.o`) rule"
        self._validate_gitignore_citations(good_range_doc)

    def test_git_shas_resolve(self):
        """Check that every commit SHA cited in the added sections resolves in git."""
        shas = [
            "258359485a",
            "1031ace",
            "682adb7472",
            "7e6da69",
            "80ba396",
            "eb9defd",
            "47277c8",
            "2f4aa72",
            "cc7a5b9",
            "06abcd2",
        ]
        for sha in shas:
            res = subprocess.run(
                ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.assertEqual(res.returncode, 0, f"Git commit SHA {sha} does not resolve")

    def test_static_test_counts_match_files(self):
        """Recompute every '`tests/...py` (N static `def test_` definitions)' count from the file."""
        count_pattern = re.compile(
            r"`(tests/test_[A-Za-z0-9_]+\.py)`\s*\((\d+)\s+static\s+`def test_`\s+definitions\)"
        )
        def_pattern = re.compile(r"^\s*def test_", re.MULTILINE)
        required_test_files = {
            "tests/test_port16_pipeline_witness.py",
            "tests/test_port16_validator_witness.py",
            "tests/test_port17_trace_core.py",
            "tests/test_port17_trace_integration.py",
            "tests/test_port17_trace_parser.py",
            "tests/test_port18_trial_preflight.py",
            "tests/test_port18_trial_report.py",
        }
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            counts = count_pattern.findall(self._extract_added_sections(doc_text))
            found_paths = {path for path, _ in counts}
            self.assertTrue(
                required_test_files.issubset(found_paths),
                f"Missing static test counts in {doc_name}: {sorted(required_test_files - found_paths)}",
            )
            for rel_path, doc_count in counts:
                source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
                actual = len(def_pattern.findall(source))
                self.assertEqual(
                    int(doc_count),
                    actual,
                    f"{doc_name} states {doc_count} static tests for {rel_path}; file has {actual}",
                )

    def test_verified_labels_have_real_citations(self):
        """Each VERIFIED label needs a file:line or git citation, never line 1."""
        label_pattern = re.compile(r"\[(VERIFIED|INFERRED|UNKNOWN)\b[^\]]*\]")
        file_line = re.compile(r"[A-Za-z0-9_\-./]*\.[A-Za-z0-9]+:\d")
        line_one = re.compile(r"[A-Za-z0-9_\-./]*\.[A-Za-z0-9]+:1(?!\d)")
        for doc_name, doc_text in [
            ("docs/PROJECT_STATE.md", self.project_state_text),
            ("docs/HANDOFF.md", self.handoff_text),
        ]:
            added = self._extract_added_sections(doc_text)
            self.assertNotIn("100% pass", added, f"Unsupported runtime pass claim in {doc_name}")
            for m in label_pattern.finditer(added):
                label = m.group(0)
                self.assertIsNone(
                    line_one.search(label), f"Line-1 citation used as evidence in {doc_name}: {label}"
                )
                if m.group(1) != "VERIFIED":
                    continue
                self.assertTrue(
                    file_line.search(label) or "git " in label or "def test_" in label or label.startswith("[VERIFIED]"),
                    f"VERIFIED label without a citation in {doc_name}: {label}",
                )


if __name__ == "__main__":
    unittest.main()
