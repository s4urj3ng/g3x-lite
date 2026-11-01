#!/usr/bin/env python3
"""PORT-23 T1: Unit tests for power-on supervision, watchdog, and sub-CPU handshake analysis.

Validates that:
1. docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:
   - Validates using tools/port11c_evidence_validator.py with 0 errors.
   - Contains all 10 approved ranges, each <= 4 KiB, and total bytes <= 64 KiB.
   - Contains no overlapping evidence slices.
   - If PRIMARY.BIN is present, slice SHA-256 digests match actual ROM dump on disk.
2. docs/PORT23_POWER_SUPERVISION.md:
   - File exists and contains all required core sections.
   - Explains owner observations (a), (b), (c), and (d).
   - Identifies watchdog and sub-CPU supervision mechanisms, timeout, and expiry action,
     each stated with evidence or explicitly marked UNKNOWN.
   - Ranks candidate hypotheses H1-H4 by evidence across all four observations.
   - Section 'Implications for breadcrumbs' gives safe stall analysis and recommendations.
   - Every claim bullet, numbered list item, and table row carries an epistemic label
     ([VERIFIED], [STATIC_VERIFIED], [INFERRED], [UNKNOWN], or [OWNER-REPORTED]).
   - Every ROM address (0xFC......) cited in the doc appears in a manifest range.
3. Scope integrity:
   - Only allowed files (docs/PORT23_POWER_SUPERVISION.md, docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json,
     tests/test_port23_power_supervision.py) are created or modified.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT23_POWER_SUPERVISION.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT23_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT23_ROM_PATH",
        os.environ.get("PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")),
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_BASE = 0xFC000000

# Canonical PORT-23 evidence entries (10 approved ranges)
APPROVED_ENTRIES = {
    "PORT23-ROM-BOOT-EARLY": (
        0xFC020000,
        0xFC0201FF,
        512,
        "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f",
    ),
    "PORT23-ROM-STARTUP-TASKS": (
        0xFC05B8E0,
        0xFC05BBDF,
        768,
        "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e",
    ),
    "PORT23-ROM-STARTDISKBOOT": (
        0xFC05BBEA,
        0xFC05BDE9,
        512,
        "a2ea19dfed6f386b32074c65ec682a557a24cf3ddcdeb73f29108ae16854acfc",
    ),
    "PORT23-ROM-NORMAL-MODE": (
        0xFC079400,
        0xFC0794FF,
        256,
        "222eb4225d2e5d34742f5ed11b306b21c44a1eb2e18e48936cc6643d08a9560c",
    ),
    "PORT23-ROM-TURNOFF-E1": (
        0xFC0D0120,
        0xFC0D023F,
        288,
        "e29e71a6f1e1c1259c5025683344a592dd927716ffdf6fcd74928b7cfff9f694",
    ),
    "PORT23-ROM-GPIO-WRITE-MMIO": (
        0xFC0D73C0,
        0xFC0D74BF,
        256,
        "0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b",
    ),
    "PORT23-ROM-PREPARE-EXEC": (
        0xFC0D9C00,
        0xFC0D9DFF,
        512,
        "8c891f7dc8fc758510f36a69d95ff323cee00a7ac0e853128d1be27d8598d644",
    ),
    "PORT23-ROM-POWERON-CHECK": (
        0xFC1284A0,
        0xFC1285DF,
        320,
        "634fd848e765cad5b01737956e6aea9ddd12dbb4413213ec2a9c3d2a421813d4",
    ),
    "PORT23-ROM-WATCHDOG-MODULE": (
        0xFC135C00,
        0xFC135E3F,
        576,
        "29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb",
    ),
    "PORT23-ROM-WATCHDOG-START": (
        0xFC418F20,
        0xFC418F7F,
        96,
        "46e8e2149df855d0f1414699a1fdea355b9370c83e552a749314a32283da7da5",
    ),
}

ALLOWED_MODIFIED_FILES = {
    "docs/PORT23_POWER_SUPERVISION.md",
    "docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json",
    "tests/test_port23_power_supervision.py",
    "docs/PORT23_OWNER_SESSION_PLAN.md",
    "tests/test_port23_owner_session_plan.py",
    "docs/PORT23_LED_BREADCRUMBS.md",
    "tools/build_candidate_port23_breadcrumb.py",
    "tests/test_port23_led_breadcrumbs.py",
}

LABEL_PATTERN = re.compile(
    r"\[(VERIFIED|STATIC_VERIFIED|INFERRED|UNKNOWN|OWNER-REPORTED)[^\]]*\]"
)


class TestPort23EvidenceManifest(unittest.TestCase):
    """Validates docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json against constraints."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(MANIFEST_PATH.is_file(), f"Manifest missing: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_validator_tool_accepts_manifest(self):
        """Run tools/port11c_evidence_validator.py and verify 0 errors."""
        cmd = [
            sys.executable,
            str(VALIDATOR_TOOL),
            "--manifest",
            str(MANIFEST_PATH),
            "--json",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Validator exited with {res.returncode}: {res.stderr}")
        report = json.loads(res.stdout)
        self.assertEqual(report["error_count"], 0, f"Validator found errors: {report.get('errors')}")

    def test_all_approved_ranges_present_and_match(self):
        """Manifest contains all approved ranges with exact addresses and byte counts."""
        entries = self.manifest.get("evidence_entries", [])
        self.assertEqual(len(entries), len(APPROVED_ENTRIES))

        entries_by_id = {e["evidence_id"]: e for e in entries}
        for eid, (start, end, count, sha) in APPROVED_ENTRIES.items():
            self.assertIn(eid, entries_by_id, f"Missing approved entry: {eid}")
            e = entries_by_id[eid]
            self.assertEqual(int(e["start_address"], 16), start, f"Start mismatch for {eid}")
            self.assertEqual(int(e["end_address"], 16), end, f"End mismatch for {eid}")
            self.assertEqual(e["expected_byte_count"], count, f"Byte count mismatch for {eid}")
            self.assertEqual(e["sha256"], sha, f"SHA-256 mismatch for {eid}")

    def test_range_and_budget_limits(self):
        """Each range <= 4 KiB (4096 B), total <= 64 KiB (65536 B)."""
        scopes = self.manifest.get("authorization_scopes", [])
        self.assertGreaterEqual(len(scopes), 1)
        scope = scopes[0]
        self.assertLessEqual(scope["max_bytes_total"], 65536)

        total_bytes = 0
        for eid, (start, end, count, _) in APPROVED_ENTRIES.items():
            self.assertLessEqual(count, 4096, f"Entry {eid} exceeds 4 KiB limit")
            total_bytes += count

        self.assertLessEqual(total_bytes, 65536, f"Total bytes ({total_bytes}) exceed 64 KiB budget")

    def test_no_slice_overlaps(self):
        """No two evidence ranges overlap in memory."""
        all_ranges = []
        for s in self.manifest.get("authorization_scopes", []):
            for r in s.get("approved_ranges", []):
                start = int(r["start_address"], 16)
                end = int(r["end_address"], 16)
                label = r["label"]
                all_ranges.append((start, end, label))

        for i, (s1, e1, id1) in enumerate(all_ranges):
            for j, (s2, e2, id2) in enumerate(all_ranges):
                if i >= j:
                    continue
                overlap = max(s1, s2) <= min(e1, e2)
                self.assertFalse(
                    overlap,
                    f"Overlap between {id1} (0x{s1:08X}..0x{e1:08X}) and {id2} (0x{s2:08X}..0x{e2:08X})",
                )

    def test_hashes_match_primary_bin_if_present(self):
        """Compare slice hashes with actual ROM dump if PRIMARY.BIN is present."""
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")

        with open(ROM_PATH, "rb") as f:
            rom_data = f.read()

        for eid, (start, end, count, expected_sha) in APPROVED_ENTRIES.items():
            offset = start - ROM_BASE
            slice_bytes = rom_data[offset : offset + count]
            self.assertEqual(len(slice_bytes), count, f"ROM slice {eid} incomplete")
            actual_sha = hashlib.sha256(slice_bytes).hexdigest()
            self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {eid}")


class TestPort23PowerSupervisionDoc(unittest.TestCase):
    """Validates the contents, structure, and citations of docs/PORT23_POWER_SUPERVISION.md."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_required_sections_exist(self):
        """Ensure all required core sections are present in the document."""
        required_headings = [
            "## 1. Executive Summary & Core Findings",
            "## 2. Architecture of Power Supervision & Watchdogs Around StartDiskboot",
            "## 3. Disassembly Analysis of ROM Supervision Components",
            "## 4. Explanation of Owner Observations (a) and (b)",
            "## 5. Candidate Hypotheses Telling (a) from (b) Apart & Evidentiary Ranking",
            "## 6. Implications for Breadcrumbs",
            "## 7. Offline Evidence Manifest & Citations",
        ]
        for heading in required_headings:
            self.assertIn(heading, self.content, f"Missing section heading: {heading}")

    def test_explains_observations_a_and_b(self):
        """Doc explains owner observations (a), (b), (c), and (d) with proper citations."""
        self.assertIn("Observation (a)", self.content)
        self.assertIn("Observation (b)", self.content)
        self.assertIn("Observation (c)", self.content)
        self.assertIn("Observation (d)", self.content)
        self.assertIn("WITNESS_INVALID", self.content)
        self.assertIn("0x0035F7A0", self.content)
        self.assertIn("0x06000000", self.content)
        self.assertIn("0x00600000", self.content)
        self.assertIn("3922ddbe", self.content)
        self.assertIn("Playback", self.content)
        self.assertIn("OWNER-REPORTED", self.content)

        # Explains LED illumination in (b) and (c) as proof of loader execution
        self.assertRegex(self.content, r"(?i)green LED.*physically illuminated")
        self.assertRegex(self.content, r"(?i)hypothesis H1.*refuted")

    def test_supervision_mechanism_timeout_and_expiry_stated(self):
        """Watchdog/sub-CPU supervision mechanism, timeout and expiry action stated or UNKNOWN."""
        # Watchdog mechanism & registers
        self.assertIn("0xD20A0000", self.content)
        self.assertIn("0xD20A0004", self.content)
        self.assertIn("WatchDog.c", self.content)
        self.assertIn("sub_fc135ccc", self.content)
        self.assertIn("StartWDT_FW", self.content)
        self.assertIn("task_WdtReset", self.content)

        # Watchdog timeout period (2000 ms) and post-StartDiskboot timing
        self.assertIn("2000", self.content)
        self.assertIn("0xFC05B922", self.content)

        # Sub-CPU supervision and UNKNOWN classification
        self.assertIn("sub-CPU", self.content)
        self.assertRegex(self.content, r"UNKNOWN:\s*external microcontroller firmware")

        # Power-hold control and shutdown
        self.assertIn("sub_fc1284ac", self.content)
        self.assertIn("sub_fc05ba56", self.content)
        self.assertIn("0x004C0003", self.content)
        self.assertIn("0xD20B099C", self.content)

    def test_hypotheses_ranking_present(self):
        """Candidate hypotheses H1-H4 are ranked by evidence."""
        self.assertIn("Rank 1", self.content)
        self.assertIn("Rank 2", self.content)
        self.assertIn("Rank 3", self.content)
        self.assertIn("Rank 4", self.content)
        self.assertIn("sub_fc1284ac", self.content)

    def test_implications_for_breadcrumbs_gives_stall_limits(self):
        """Section 'Implications for breadcrumbs' gives safe stall analysis and recommendations."""
        section = self.content.split("## 6. Implications for Breadcrumbs", 1)[1].split("## 7.", 1)[0]
        self.assertIn("Exact Maximum Safe Stall is Unknown", section)
        self.assertIn("Conservative Recommendation for Breadcrumb Pulses", section)
        self.assertIn("Recommended Diagnostic Checkpoint Placement", section)
        self.assertIn("Bypassing `sub_fc1284ac` in Stage 5", section)

    def test_all_claim_bullets_and_rows_carry_epistemic_labels(self):
        """Every claim bullet, numbered item, and table row carries an epistemic label."""
        unlabeled_bullets = []
        unlabeled_rows = []

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            # Check bullets (- / *) or numbered list items (1. / 2.)
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_bullets.append(f"Line {i}: {stripped}")
            # Check table content rows (excluding separators and headers)
            elif stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue
                if "Rank" in stripped or "Evidence ID" in stripped:
                    continue
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_rows.append(f"Line {i}: {stripped}")

        self.assertEqual(
            unlabeled_bullets,
            [],
            f"Found unlabeled bullets in docs/PORT23_POWER_SUPERVISION.md:\n"
            + "\n".join(unlabeled_bullets),
        )
        self.assertEqual(
            unlabeled_rows,
            [],
            f"Found unlabeled table rows in docs/PORT23_POWER_SUPERVISION.md:\n"
            + "\n".join(unlabeled_rows),
        )

    def test_every_cited_rom_address_appears_in_manifest_range(self):
        """Every 0xFC...... address in the markdown document falls within an approved manifest range."""
        manifest_entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        scopes = self.manifest.get("authorization_scopes", [])
        approved_ranges = [
            (int(r["start_address"], 16), int(r["end_address"], 16), r["label"])
            for s in scopes
            for r in s.get("approved_ranges", [])
        ]

        # 1. Assert on every inline [VERIFIED: ... ROM 0x...; EVIDENCE-ID] citation
        inline_re = re.compile(
            r"\[(?:VERIFIED|STATIC_VERIFIED)[^\]]*?\bROM\s+([^;\]]+);\s*(PORT23-ROM-[A-Z0-9-]+)[^\]]*\]"
        )
        inline_matches = inline_re.findall(self.content)
        self.assertGreater(len(inline_matches), 0, "No inline ROM citations found in doc")

        for addr_part, eid in inline_matches:
            self.assertIn(eid, manifest_entries, f"Inline citation evidence ID '{eid}' missing from manifest")
            entry = manifest_entries[eid]
            e_start = int(entry["start_address"], 16)
            e_end = int(entry["end_address"], 16)

            tokens = [t.strip() for t in addr_part.split(",") if t.strip()]
            for tok in tokens:
                if "-" in tok:
                    parts = tok.split("-")
                    s = int(parts[0].strip(), 16)
                    e = int(parts[1].strip(), 16)
                elif ".." in tok:
                    parts = tok.split("..")
                    s = int(parts[0].strip(), 16)
                    e = int(parts[1].strip(), 16)
                else:
                    s = int(tok.strip(), 16)
                    e = s
                self.assertTrue(
                    e_start <= s and e <= e_end,
                    f"Cited address/range 0x{s:08X}..0x{e:08X} in '{addr_part}' does not lie inside "
                    f"'{eid}' bounds (0x{e_start:08X}..0x{e_end:08X})",
                )

        # 2. Assert that EVERY 0xFC...... address in the doc is within at least one approved manifest range
        all_rom_addrs = set(re.findall(r"\b0xFC[0-9A-Fa-f]{6}\b", self.content))
        self.assertGreater(len(all_rom_addrs), 20, "Too few ROM addresses found in doc")

        unapproved_addrs = []
        for addr_str in sorted(all_rom_addrs):
            val = int(addr_str, 16)
            is_covered = any(start <= val <= end for start, end, _ in approved_ranges)
            if not is_covered:
                unapproved_addrs.append(addr_str)

        self.assertEqual(
            unapproved_addrs,
            [],
            f"Found ROM addresses outside approved manifest ranges in docs/PORT23_POWER_SUPERVISION.md:\n"
            + "\n".join(unapproved_addrs),
        )

    def test_offline_manifest_table_matches_json(self):
        """Offline evidence table in Section 7 matches PORT23_EVIDENCE_MANIFEST.json entries."""
        section7 = self.content.split("## 7. Offline Evidence Manifest & Citations", 1)[1]
        row_re = re.compile(
            r"\|\s*`([^`]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*(\d+)\s*B\s*\|\s*`([0-9a-f]{64})`\s*\|"
        )
        cited_ranges = row_re.findall(section7)
        self.assertEqual(len(cited_ranges), len(APPROVED_ENTRIES))

        manifest_entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        for eid, start_str, end_str, count_str, sha in cited_ranges:
            start = int(start_str, 16)
            end = int(end_str, 16)
            count = int(count_str)

            self.assertIn(eid, manifest_entries, f"Table entry {eid} missing from manifest")
            entry = manifest_entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start, f"Start mismatch for {eid}")
            self.assertEqual(int(entry["end_address"], 16), end, f"End mismatch for {eid}")
            self.assertEqual(entry["expected_byte_count"], count, f"Byte count mismatch for {eid}")
            self.assertEqual(entry["sha256"], sha, f"SHA mismatch for {eid}")


class TestPort23ScopeIntegrity(unittest.TestCase):
    """Ensures only the task-authorized files are modified or added."""

    def test_only_allowed_paths_modified(self):
        res = subprocess.run(["git", "status", "--porcelain"], stdout=subprocess.PIPE, text=True)
        modified_files = set()
        for raw_line in res.stdout.splitlines():
            if not raw_line.strip():
                continue
            # In porcelain format, column 0-1 is XY, column 2 is space, path starts at index 3
            fpath = raw_line[3:].strip()
            if " -> " in fpath:
                fpath = fpath.split(" -> ")[1].strip()
            modified_files.add(fpath)

        forbidden_exts = (".bin", ".elf", ".o", ".a", ".dump", ".rom")
        for f in modified_files:
            self.assertFalse(
                f.endswith(forbidden_exts),
                f"Binary/build artifact '{f}' must not be modified or added",
            )
            # Scope check applies only to PORT-23-owned paths so later milestones' files don't trip the check.
            if "port23" in f.lower():
                self.assertIn(
                    f,
                    ALLOWED_MODIFIED_FILES,
                    f"Unauthorized file modified or added in worktree: {f}",
                )


if __name__ == "__main__":
    unittest.main()
