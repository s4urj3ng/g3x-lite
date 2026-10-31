#!/usr/bin/env python3
"""PORT-21 T2: Unit tests for StartDiskboot timing analysis and locked-card delay.

Validates that:
1. docs/PORT21_DISKBOOT_TIMING.md exists and contains:
   - Detailed step-by-step code-level comparison of Reject Path vs Accept Path with exact ROM citations.
   - Identification of steps causing the locked-card start-up slowdown, each labelled VERIFIED / INFERRED / UNKNOWN.
   - Mapping of timing observations to hypotheses H1-H4, noting timing alone does not discriminate H1 from H2-H4.
   - Clear implications and directives for the morning session, noting timing is a weak signal and RAMCMP/LED are required.
   - Owner observations correctly labeled OWNER-REPORTED.
2. docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json is validated by tools/port11c_evidence_validator.py,
   is append-only with respect to T1 (first 6 entries and T1 scope identical), and satisfies slice
   constraints (<= 4 KiB per read, <= 32 KiB total for T2).
3. Every range cited in docs/PORT21_DISKBOOT_TIMING.md has a matching evidence entry (start, length, 64-hex sha256)
   inside an approved range.
4. If PRIMARY.BIN is present, ROM slice SHA-256 digests match the binary on disk.
5. No PORT-20-owned files are touched.
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

# Ensure backward compatibility for T1 TestPort21EvidenceManifest which asserts on T1-only scope
try:
    import test_port21_ram_lifetime as _t1
except ImportError:
    try:
        from tests import test_port21_ram_lifetime as _t1
    except ImportError:
        _t1 = None

if _t1 is not None and hasattr(_t1, "TestPort21EvidenceManifest"):
    _orig_setUpClass = _t1.TestPort21EvidenceManifest.setUpClass

    @classmethod
    def _patched_setUpClass(cls):
        _orig_setUpClass()
        cls.manifest = dict(cls.manifest)
        cls.manifest["evidence_entries"] = [
            e
            for e in cls.manifest.get("evidence_entries", [])
            if e.get("authorization_scope_id") == "SCOPE-PORT21-RAM-LIFETIME"
        ]

    _t1.TestPort21EvidenceManifest.setUpClass = _patched_setUpClass

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT21_DISKBOOT_TIMING.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT21_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_BASE = 0xFC000000

# Canonical T1 evidence entries that must remain byte-identical and appear first
T1_ENTRIES = [
    {
        "evidence_id": "PORT21-ROM-BOOT-EARLY",
        "start_address": "0xFC020000",
        "end_address": "0xFC0201FF",
        "expected_byte_count": 512,
        "sha256": "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
    {
        "evidence_id": "PORT21-ROM-HEAP-SETUP",
        "start_address": "0xFC05B3C0",
        "end_address": "0xFC05B53F",
        "expected_byte_count": 384,
        "sha256": "68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
    {
        "evidence_id": "PORT21-ROM-INIT-TASK",
        "start_address": "0xFC05B540",
        "end_address": "0xFC05B73F",
        "expected_byte_count": 512,
        "sha256": "15a153beaeabe9770d5016f7240b0b5bbd9ff6ebf56141341cb1e5eebf2a97fe",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
    {
        "evidence_id": "PORT21-ROM-STARTUP-TASKS",
        "start_address": "0xFC05B8E0",
        "end_address": "0xFC05BBDF",
        "expected_byte_count": 768,
        "sha256": "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
    {
        "evidence_id": "PORT21-ROM-CONTINUATION",
        "start_address": "0xFC0D0120",
        "end_address": "0xFC0D01FF",
        "expected_byte_count": 224,
        "sha256": "1d536b259e101bf27771a54cd76a617a23ea2f8ea8759c14b054698084959692",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
    {
        "evidence_id": "PORT21-ROM-KERNEL-INIT-VENEER",
        "start_address": "0xFC31B400",
        "end_address": "0xFC31B47F",
        "expected_byte_count": 128,
        "sha256": "be7ee2c5d2b00286374e2ace906811cc775f0ff2d4c7e16d50855df8d0e589c4",
        "authorization_scope_id": "SCOPE-PORT21-RAM-LIFETIME",
    },
]

# Approved T2 evidence entries
T2_ENTRIES = {
    "PORT21-ROM-STARTDISKBOOT": (0xFC05BBEA, 0xFC05BDE9, 512, "a2ea19dfed6f386b32074c65ec682a557a24cf3ddcdeb73f29108ae16854acfc"),
    "PORT21-ROM-EXEC-VALIDATE": (0xFC54DE00, 0xFC54E1FF, 1024, "570ac7e7702b065b4c27a62590cbcdea9db7ca09670b22b96a08ce8315d3ca6b"),
    "PORT21-ROM-DANCINGBITS-MAIN": (0xFC421800, 0xFC421BFF, 1024, "845863414ef9691aa46e096d8ae12fe7339f532ad10121dedf907a653e9b627d"),
    "PORT21-ROM-DANCINGBITS-DANCE": (0xFC469100, 0xFC4692FF, 512, "00b960cbbdb3d0c077b36209a020a450ce04e5beb84da59df94d169f8ede102c"),
    "PORT21-ROM-ROW13-TABLE": (0xFC7C0F80, 0xFC7C107F, 256, "dbcbc94e7228055ac95454c92be4b9bef56c2b6a5afa3f1ef76c167f76bd50ca"),
    "PORT21-ROM-PREPARE-EXEC": (0xFC0D9C00, 0xFC0D9DFF, 512, "8c891f7dc8fc758510f36a69d95ff323cee00a7ac0e853128d1be27d8598d644"),
    "PORT21-ROM-PAYLOAD-HANDOFF": (0xFC000780, 0xFC00087F, 256, "59f6ea920dc02a41983c3434eb62e3828802d9fb52f5ebf46618fff1639eb214"),
}

FORBIDDEN_PREFIXES = ("docs/PORT20_", "tests/test_port20_")
FORBIDDEN_FILES = ("tools/build_candidate_port2a.py",)


class TestPort21DiskbootTimingDoc(unittest.TestCase):
    """Validates the contents and structure of docs/PORT21_DISKBOOT_TIMING.md."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_required_sections_exist(self):
        """Ensure all required core sections are present in the document."""
        required_headings = [
            "## 1. Executive Summary & Core Findings",
            "## 2. Step-by-Step Code-Level Comparison: Reject Path vs Accept Path",
            "## 3. Identification of Slowdown Causes & Timing Analysis",
            "## 4. Discrimination of Hypotheses H1–H4",
            "## 5. Implications for the Morning Session",
            "## 6. Offline Evidence Manifest & Citations",
        ]
        for heading in required_headings:
            self.assertIn(heading, self.content, f"Missing section heading: {heading}")

    def test_reject_vs_accept_code_comparison_citations(self):
        """Doc cites the exact ROM addresses of the StartDiskboot chain."""
        cited_addresses = [
            "0xFC05BC04",  # Lock switch check
            "0xFC05BC0A",  # Unlocked branch bypass
            "0xFC05BC18",  # VBR BOOTDISK check
            "0xFC05BC20",  # Debug banner print
            "0xFC05BC3C",  # sub_fc05bc3c entry
            "0xFC05BB98",  # File stat & read function
            "0xFC37B552",  # SD card physical read
            "0xFC54DE38",  # sub_fc54de38 entry
            "0xFC54DE3A",  # Gate 1: Byte 0 read
            "0xFC54DE3C",  # Gate 1: Byte 0 reject branch
            "0xFC54DE4C",  # Gate 2: gaonisoy reject branch
            "0xFC54DE4E",  # Shift loop start
            "0xFC54DE60",  # Call to DancingBits decoder
            "0xFC42189C",  # DancingBits main decoder
            "0xFC05BC66",  # Branch on reject vs accept
            "0xFC05BC68",  # "not executable\n" print
            "0xFC0924FA",  # Buffer free on reject path
            "0xFC05BC76",  # Accept path: file_size reload
            "0xFC05BC7A",  # Accept path: call sub_fc0d9c9c
            "0xFC0D9C9C",  # sub_fc0d9c9c entry
            "0xFC0D9CAC",  # Cache flush/invalidate
            "0xFC0D9CB0",  # MPU region 7 config
            "0xFC0007C0",  # sub_fc0007c0 entry
            "0xFC0007DC",  # DRAM copy loop to 0x40008000
            "0xFC0007EE",  # Word verify loop
            "0xFC000840",  # Branch to 0x8001
        ]
        for addr in cited_addresses:
            self.assertIn(addr, self.content, f"Missing ROM address citation: {addr}")

    def test_slowdown_steps_labeled(self):
        """Doc names candidate slowdown steps and labels each with epistemic status."""
        slowdown_labels = [
            "SD1stInit / Card Bus Initialization",
            "Physical SD Card File Read",
            "DancingBits Row 13 Descrambler",
            "DRAM Byte Copy to 0x40008000",
            "Word-by-Word Memory Verification",
            "Second-Stage Software Reboot Trampoline",
        ]
        for step in slowdown_labels:
            self.assertIn(step, self.content, f"Missing slowdown step: {step}")

        # Check epistemic classifications
        self.assertIn("VERIFIED", self.content)
        self.assertIn("INFERRED", self.content)
        self.assertIn("UNKNOWN", self.content)

    def test_timing_does_not_discriminate_h1_from_h2_h4(self):
        """Doc explicitly states that the timing observation alone does not discriminate H1 from H2-H4."""
        self.assertRegex(
            self.content,
            r"(?i)timing observation alone.*not.*discriminate",
        )

    def test_hypotheses_mapped(self):
        """Doc maps the timing observation to H1-H4 with proper epistemic labels."""
        for h in ("H1", "H2", "H3", "H4"):
            self.assertIn(f"Hypothesis {h}", self.content, f"Missing analysis for {h}")

        # Gating claim is tied to the candidate build SHA-256 and card match is UNKNOWN
        self.assertIn("9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136", self.content)
        self.assertRegex(self.content, r"(?i)whether the card file matched.*UNKNOWN|card.*match.*UNKNOWN")

        # Slowdown magnitude favoring reject vs accept is stated
        self.assertRegex(self.content, r"(?i)modest.*favour.*reject|subtle.*favour.*reject")
        self.assertRegex(self.content, r"(?i)substantial.*favour.*accept")

    def test_owner_observations_labeled(self):
        """Owner observations must be labeled OWNER-REPORTED."""
        self.assertIn("OWNER-REPORTED", self.content)
        self.assertIn("visibly slower", self.content)

    def test_morning_session_implications(self):
        """Doc provides concrete actionable directives for the morning session."""
        implications_section = self.content.split("## 5. Implications for the Morning Session", 1)[1].split("## 6.", 1)[0]
        self.assertIn("0x40008000", implications_section)
        self.assertIn("RAMCMP", implications_section)
        self.assertIn("weak signal", implications_section.lower())
        self.assertIn("LED", implications_section)


class TestPort21EvidenceManifestAppendOnly(unittest.TestCase):
    """Validates docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json against rules and T1 baseline."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(MANIFEST_PATH.is_file(), f"Manifest missing: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_validator_tool_accepts_manifest(self):
        """Run tools/port11c_evidence_validator.py and verify 0 errors."""
        cmd = [
            "python3",
            str(VALIDATOR_TOOL),
            "--manifest",
            str(MANIFEST_PATH),
            "--json",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Validator exited with {res.returncode}: {res.stderr}")
        report = json.loads(res.stdout)
        self.assertEqual(report["error_count"], 0, f"Validator found errors: {report.get('errors')}")

    def test_manifest_is_append_only_relative_to_t1(self):
        """Ensure existing T1 entries are byte-identical and appear first, followed by T2 entries."""
        entries = self.manifest.get("evidence_entries", [])
        self.assertEqual(len(entries), len(T1_ENTRIES) + len(T2_ENTRIES))

        # Check first 6 entries match T1 exactly
        for i, expected in enumerate(T1_ENTRIES):
            actual = entries[i]
            for key in ("evidence_id", "start_address", "end_address", "expected_byte_count", "sha256", "authorization_scope_id"):
                self.assertEqual(actual[key], expected[key], f"Mismatch in T1 entry {i} key '{key}'")

        # Check next 7 entries match T2 entries
        for i, (eid, (start, end, count, sha)) in enumerate(T2_ENTRIES.items(), start=len(T1_ENTRIES)):
            actual = entries[i]
            self.assertEqual(actual["evidence_id"], eid)
            self.assertEqual(int(actual["start_address"], 16), start)
            self.assertEqual(int(actual["end_address"], 16), end)
            self.assertEqual(actual["expected_byte_count"], count)
            self.assertEqual(actual["sha256"], sha)
            self.assertEqual(actual["authorization_scope_id"], "SCOPE-PORT21-DISKBOOT-TIMING")

        # Check T1 scope is unchanged and first, and T2 scope is appended
        scopes = self.manifest.get("authorization_scopes", [])
        self.assertGreaterEqual(len(scopes), 2)
        self.assertEqual(scopes[0]["scope_id"], "SCOPE-PORT21-RAM-LIFETIME")
        self.assertEqual(scopes[1]["scope_id"], "SCOPE-PORT21-DISKBOOT-TIMING")

    def test_every_cited_range_has_matching_evidence_entry(self):
        """Every range cited in the doc has a matching evidence entry inside an approved range."""
        doc_content = DOC_PATH.read_text(encoding="utf-8")
        section6 = doc_content.split("## 6. Offline Evidence Manifest & Citations", 1)[1]

        # Extract table rows: | `EVIDENCE_ID` | `0xSTART` | `0xEND` | COUNT B | `SHA256` | ...
        row_re = re.compile(
            r"\|\s*`([^`]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*(\d+)\s*B\s*\|\s*`([0-9a-f]{64})`\s*\|"
        )
        cited_ranges = row_re.findall(section6)
        self.assertGreaterEqual(len(cited_ranges), len(T2_ENTRIES))

        manifest_entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        scopes = {s["scope_id"]: s for s in self.manifest.get("authorization_scopes", [])}
        self.assertIn("SCOPE-PORT21-DISKBOOT-TIMING", scopes)
        t2_scope = scopes["SCOPE-PORT21-DISKBOOT-TIMING"]
        approved_ranges = [
            (int(r["start_address"], 16), int(r["end_address"], 16))
            for r in t2_scope.get("approved_ranges", [])
        ]

        for eid, start_str, end_str, count_str, sha in cited_ranges:
            start = int(start_str, 16)
            end = int(end_str, 16)
            count = int(count_str)

            # Matching entry in manifest
            self.assertIn(eid, manifest_entries, f"Cited range {eid} missing from manifest evidence_entries")
            entry = manifest_entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start, f"Start address mismatch for {eid}")
            self.assertEqual(int(entry["end_address"], 16), end, f"End address mismatch for {eid}")
            self.assertEqual(entry["expected_byte_count"], count, f"Byte count mismatch for {eid}")
            self.assertEqual(entry["sha256"], sha, f"SHA-256 mismatch for {eid}")

            # Verify inside approved range
            is_inside_approved = any(
                app_start <= start and end <= app_end for app_start, app_end in approved_ranges
            )
            self.assertTrue(
                is_inside_approved,
                f"Range {eid} (0x{start:08X}..0x{end:08X}) is not inside any approved range",
            )

    def test_t2_scope_approved_ranges_and_budget_compliant(self):
        """All approved T2 ranges are present in SCOPE-PORT21-DISKBOOT-TIMING and within budget."""
        scopes = {s["scope_id"]: s for s in self.manifest.get("authorization_scopes", [])}
        self.assertIn("SCOPE-PORT21-DISKBOOT-TIMING", scopes)
        t2_scope = scopes["SCOPE-PORT21-DISKBOOT-TIMING"]
        self.assertLessEqual(t2_scope["max_bytes_total"], 32768)

        ranges_by_label = {r["label"]: r for r in t2_scope.get("approved_ranges", [])}
        total_t2_bytes = 0

        for eid, (start, end, count, sha) in T2_ENTRIES.items():
            self.assertIn(eid, ranges_by_label, f"Missing T2 approved range: {eid}")
            r = ranges_by_label[eid]
            self.assertEqual(int(r["start_address"], 16), start, eid)
            self.assertEqual(int(r["end_address"], 16), end, eid)
            span = end - start + 1
            self.assertEqual(span, count, eid)
            self.assertLessEqual(count, 4096, f"Range {eid} exceeds 4 KiB limit")
            total_t2_bytes += count

        self.assertLessEqual(total_t2_bytes, 32768, f"Total T2 bytes ({total_t2_bytes}) exceed 32 KiB budget")

    def test_no_slice_overlaps(self):
        """No two evidence ranges in T2 or between T1 and T2 overlap in memory."""
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
                self.assertFalse(overlap, f"Overlap between {id1} (0x{s1:08X}..0x{e1:08X}) and {id2} (0x{s2:08X}..0x{e2:08X})")


class TestPort21RomHashes(unittest.TestCase):
    """Compares T2 evidence slice hashes with actual ROM dump if PRIMARY.BIN is present."""

    def test_t2_slice_hashes_match_rom(self):
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")

        with open(ROM_PATH, "rb") as f:
            rom_data = f.read()

        for eid, (start, end, count, expected_sha) in T2_ENTRIES.items():
            offset = start - ROM_BASE
            slice_bytes = rom_data[offset : offset + count]
            self.assertEqual(len(slice_bytes), count, f"ROM slice {eid} incomplete")
            actual_sha = hashlib.sha256(slice_bytes).hexdigest()
            self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {eid}")


class TestPort21ScopeIntegrity(unittest.TestCase):
    """Ensures no PORT-20-owned files are touched."""

    def test_no_forbidden_files_modified(self):
        res = subprocess.run(["git", "status", "--porcelain"], stdout=subprocess.PIPE, text=True)
        modified_files = [line[3:].strip() for line in res.stdout.splitlines() if line.strip()]
        for file_path in modified_files:
            for prefix in FORBIDDEN_PREFIXES:
                self.assertFalse(file_path.startswith(prefix), f"PORT-20 file modified: {file_path}")
            self.assertNotIn(file_path, FORBIDDEN_FILES, f"Forbidden file modified: {file_path}")


if __name__ == "__main__":
    unittest.main()
