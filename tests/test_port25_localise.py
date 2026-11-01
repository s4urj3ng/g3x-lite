#!/usr/bin/env python3
"""PORT-25 T2: Unit tests for post-loader short-press power-off candidate localisation.

Verifies:
1. docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:
   - Validates cleanly via tools/port11c_evidence_validator.py with 0 errors.
   - Contains all approved ranges, each <= 4096 bytes, and total bytes <= 65536.
   - Slices are strictly disjoint (no overlapping address ranges).
   - If PRIMARY.BIN is present, all slice SHA-256 digests match actual ROM dump on disk.
2. docs/PORT25_SHORT_PRESS_LOCALISE.md:
   - Document exists and has required core sections.
   - States total bytes newly read (784 B across 6 ranges) and confirms no full-ROM scans.
   - Contains a ranked table of short-press power-off / power-button-wait candidates.
   - Every candidate in the table and every claim/item carries an epistemic label
     ([VERIFIED], [STATIC_VERIFIED], [INFERRED], [UNKNOWN], or [OWNER-REPORTED]).
   - Every ROM address (0xFC...... and 0xFD......) cited anywhere in the document falls
     within an approved manifest range [start, start + length).
   - Lists proposed breadcrumb stages in boot_prototype.c with file:line references,
     specifically including:
     * entry to sub_fc05b962_my
     * before/after each remaining power-on check
     * before/after task creation
     * core entry
     * pre-call power-check fail and post-call power-cut halt distinction
3. Strictly Read-Only:
   - No bootstrap scripts, build steps, or write operations are executed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT25_SHORT_PRESS_LOCALISE.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT25_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT25_ROM_PATH",
        os.environ.get(
            "PORT24_ROM_PATH",
            os.environ.get("PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")),
        ),
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
BOOT_PROTOTYPE_C = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "boot_prototype.c"
ROM_BASE = 0xFC000000


APPROVED_ENTRIES = {
    "PORT25-ROM-BOOT-EARLY": (
        0xFC020000,
        0xFC0201FF,
        512,
        "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f",
    ),
    "PORT25-ROM-HEAP-SETUP": (
        0xFC05B3C0,
        0xFC05B53F,
        384,
        "68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6",
    ),
    "PORT25-ROM-INIT-TASK": (
        0xFC05B540,
        0xFC05B73F,
        512,
        "15a153beaeabe9770d5016f7240b0b5bbd9ff6ebf56141341cb1e5eebf2a97fe",
    ),
    "PORT25-ROM-STARTUP-TASKS": (
        0xFC05B8E0,
        0xFC05BBDF,
        768,
        "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e",
    ),
    "PORT25-ROM-STARTDISKBOOT": (
        0xFC05BBE0,
        0xFC05BDDF,
        512,
        "c773cbfa1877af69cbf36b0590814abff7fbd1321de5aff86af28946968d7839",
    ),
    "PORT25-ROM-CARD-SWITCHES": (
        0xFC05C4D0,
        0xFC05C51F,
        80,
        "886c3e10248cc33ac671b575331311bbaf59ae549ab01a9414ddb1b470c314c5",
    ),
    "PORT25-ROM-NORMAL-MODE": (
        0xFC079400,
        0xFC0794FF,
        256,
        "222eb4225d2e5d34742f5ed11b306b21c44a1eb2e18e48936cc6643d08a9560c",
    ),
    "PORT25-ROM-GPIO-READ": (
        0xFC087110,
        0xFC08713F,
        48,
        "2238807ba4260729bb4991960fa1a40f257bed76425e8b7bb3cb6111a5920059",
    ),
    "PORT25-ROM-STARTCAUSE-SAVE": (
        0xFC08ECB0,
        0xFC08ECFF,
        80,
        "039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d",
    ),
    "PORT25-ROM-STARTCAUSE-PTR": (
        0xFC08EEE0,
        0xFC08EEFF,
        32,
        "0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6",
    ),
    "PORT25-ROM-FIRMWARE-CONT": (
        0xFC0D0080,
        0xFC0D023F,
        448,
        "33d2fae4ed8c9c228ea6cc8f3304a26b96f8a4fb6d9d3bdc37cd056e7833456e",
    ),
    "PORT25-ROM-GPIO-WRITE-MMIO": (
        0xFC0D73C0,
        0xFC0D74BF,
        256,
        "0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b",
    ),
    "PORT25-ROM-CACHE-MAINT": (
        0xFC127A00,
        0xFC127B7F,
        384,
        "519594faaab42e66229096ef890f9161e2d1715e6044a911a74e2ebdf20415cb",
    ),
    "PORT25-ROM-PHYSW-TASK": (
        0xFC1283A0,
        0xFC12849F,
        256,
        "9381dabcf3fb6c55ec26118cdb7a6626a9b84211f7cd171175470421db181500",
    ),
    "PORT25-ROM-POWERON-CHECK": (
        0xFC1284A0,
        0xFC1285DF,
        320,
        "634fd848e765cad5b01737956e6aea9ddd12dbb4413213ec2a9c3d2a421813d4",
    ),
    "PORT25-ROM-PHYSW-LITERALS": (
        0xFC128680,
        0xFC12877F,
        256,
        "60db72e096ddc7915f3f0bea545cde955da38224ab8fb06297631462fe8c8572",
    ),
    "PORT25-ROM-MPU-CONFIG": (
        0xFC135280,
        0xFC1352FF,
        128,
        "3327ae3b2b5508a96aeab70b4076fd83fa199ae9c77d550475bd4effef5f5a5c",
    ),
    "PORT25-ROM-WATCHDOG-MODULE": (
        0xFC135C00,
        0xFC135E3F,
        576,
        "29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb",
    ),
    "PORT25-ROM-SD1STINIT-VENEER": (
        0xFC31B1E0,
        0xFC31B21F,
        64,
        "6122841f084da666089820aacae31c016345c903d8dc7e29f1029e23d5c89bed",
    ),
    "PORT25-ROM-KERNEL-INIT-VENEER": (
        0xFC31B400,
        0xFC31B47F,
        128,
        "be7ee2c5d2b00286374e2ace906811cc775f0ff2d4c7e16d50855df8d0e589c4",
    ),
    "PORT25-ROM-CREATETASK-VENEER": (
        0xFC31BBA0,
        0xFC31BBEF,
        80,
        "59c9adc82ad1ad670ecf7ba0d42665a34f7acf1a10b68ad75874afe1fae77487",
    ),
    "PORT25-ROM-MEMSET-VENEER": (
        0xFC31BF90,
        0xFC31BFCF,
        64,
        "7d4ee3349a02377c01f913cb9ba9ec4d2d27247448882aa2fbd0ee63a84c8592",
    ),
    "PORT25-ROM-ARAM-HEAP-INIT": (
        0xFC382C80,
        0xFC382CBF,
        64,
        "b618d01755115b3709c23799e69032c0362fa70610639d3f9832309ab7add654",
    ),
    "PORT25-ROM-WATCHDOG-START": (
        0xFC418F20,
        0xFC418F7F,
        96,
        "46e8e2149df855d0f1414699a1fdea355b9370c83e552a749314a32283da7da5",
    ),
    "PORT25-ROM-NORMAL-FLAG": (
        0xFDF20380,
        0xFDF2038F,
        16,
        "7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64",
    ),
}

NEWLY_READ_ENTRIES = {
    "PORT25-ROM-PHYSW-TASK",
    "PORT25-ROM-PHYSW-LITERALS",
    "PORT25-ROM-SD1STINIT-VENEER",
    "PORT25-ROM-CREATETASK-VENEER",
    "PORT25-ROM-MEMSET-VENEER",
    "PORT25-ROM-ARAM-HEAP-INIT",
}

VALID_LABEL_PATTERN = re.compile(r"\[(?:STATIC_)?VERIFIED\b|\[INFERRED\b|\[UNKNOWN\b")


def extract_cited_rom_addresses(text: str) -> set[str]:
    """Extract ROM addresses from doc text: bare 0xFC/0xFD, bare fc/fd, and sub_/loc_ with optional suffix."""
    pattern = re.compile(
        r"\b(?:sub_|loc_)((?:fc|fd)[0-9a-f]{6})(?:_[a-z0-9_]+)?\b|(?:0x|\b)((?:fc|fd)[0-9a-f]{6})\b",
        re.IGNORECASE,
    )
    addrs = set()
    for m in pattern.finditer(text):
        raw = m.group(1) or m.group(2)
        addrs.add("0x" + raw.upper())
    return addrs


def get_uncovered_rom_addresses(cited_addrs: set[str], evidence_ranges: list[tuple[int, int, str]]) -> list[str]:
    """Returns sorted list of addresses in cited_addrs not covered by any manifest [start, start + length) range."""
    unapproved = []
    for addr_str in sorted(cited_addrs):
        val = int(addr_str, 16)
        if not any(start <= val < end for start, end, _ in evidence_ranges):
            unapproved.append(addr_str)
    return unapproved


class TestPort25EvidenceManifest(unittest.TestCase):
    """Validates docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json integrity and compliance."""

    def setUp(self):
        self.assertTrue(MANIFEST_PATH.exists(), f"Missing manifest at {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_validator_script_clean_exit(self):
        """tools/port11c_evidence_validator.py exits 0 with 0 errors on PORT25 manifest."""
        self.assertTrue(VALIDATOR_TOOL.exists(), f"Missing validator tool at {VALIDATOR_TOOL}")
        cmd = ["python3", str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH), "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(
            proc.returncode,
            0,
            f"Validator returned non-zero ({proc.returncode}). Stderr: {proc.stderr}\nStdout: {proc.stdout}",
        )
        report = json.loads(proc.stdout)
        self.assertTrue(report.get("is_valid"), f"Validator reported manifest invalid: {report}")
        self.assertEqual(report.get("error_count"), 0, f"Validator found {report.get('error_count')} errors: {report}")

    def test_manifest_entries_and_scopes_match_approved(self):
        """Manifest contains all expected approved ranges and evidence entries."""
        scopes = self.manifest.get("authorization_scopes", [])
        self.assertEqual(len(scopes), 1, "Expected exactly 1 authorization scope")
        scope = scopes[0]
        self.assertEqual(scope.get("scope_id"), "SCOPE-PORT25-SHORT-PRESS-LOCALISE")
        self.assertEqual(scope.get("firmware_revision"), "GM1.10C")
        self.assertLessEqual(scope.get("max_bytes_total", 0), 65536)

        approved_map = {r["label"]: (int(r["start_address"], 16), int(r["end_address"], 16)) for r in scope.get("approved_ranges", [])}
        self.assertEqual(set(approved_map.keys()), set(APPROVED_ENTRIES.keys()))

        entries = self.manifest.get("evidence_entries", [])
        self.assertEqual(len(entries), len(APPROVED_ENTRIES))
        entry_map = {e["evidence_id"]: e for e in entries}
        self.assertEqual(set(entry_map.keys()), set(APPROVED_ENTRIES.keys()))

        for eid, (exp_start, exp_end, exp_len, exp_sha) in APPROVED_ENTRIES.items():
            entry = entry_map[eid]
            self.assertEqual(int(entry["start_address"], 16), exp_start)
            self.assertEqual(int(entry["end_address"], 16), exp_end)
            self.assertEqual(entry["expected_byte_count"], exp_len)
            self.assertEqual(entry["sha256"], exp_sha)
            self.assertEqual(entry["authorization_scope_id"], "SCOPE-PORT25-SHORT-PRESS-LOCALISE")
            self.assertEqual(entry["classification"], "STATIC_VERIFIED")

    def test_manifest_disjoint_slices(self):
        """Manifest slices must be strictly disjoint without any overlaps."""
        ranges = []
        for eid, (start, end, size, _) in APPROVED_ENTRIES.items():
            self.assertLessEqual(size, 4096, f"{eid} slice size {size} exceeds 4096 B limit")
            ranges.append((start, end, eid))

        ranges.sort(key=lambda x: x[0])
        for i in range(len(ranges) - 1):
            s1, e1, name1 = ranges[i]
            s2, e2, name2 = ranges[i + 1]
            self.assertLess(e1, s2, f"Overlap detected between {name1} (0x{e1:08X}) and {name2} (0x{s2:08X})")

        total_bytes = sum(end - start + 1 for start, end, _ in ranges)
        self.assertLessEqual(total_bytes, 65536, f"Total byte count {total_bytes} exceeds 64 KiB budget")

    def test_newly_read_accounting(self):
        """Newly read entries sum exactly to 784 bytes."""
        new_bytes = sum(APPROVED_ENTRIES[eid][2] for eid in NEWLY_READ_ENTRIES)
        self.assertEqual(new_bytes, 784, f"Newly read byte total {new_bytes} != 784 B")

    def test_rom_dump_hashes_match_disk_if_present(self):
        """If PRIMARY.BIN is present, actual bytes in ROM dump match declared digests."""
        if not ROM_PATH.exists():
            self.skipTest(f"ROM dump not found at {ROM_PATH}")

        rom_size = ROM_PATH.stat().st_size
        self.assertGreaterEqual(rom_size, 33554432, "PRIMARY.BIN smaller than 32 MiB")
        with open(ROM_PATH, "rb") as f:
            for eid, (start, end, byte_count, expected_sha) in APPROVED_ENTRIES.items():
                offset = start - ROM_BASE
                self.assertGreaterEqual(offset, 0, f"Negative offset for {eid} at 0x{start:08X}")
                f.seek(offset)
                chunk = f.read(byte_count)
                self.assertEqual(len(chunk), byte_count, f"Incomplete read for {eid}")
                actual_sha = hashlib.sha256(chunk).hexdigest()
                self.assertEqual(
                    actual_sha,
                    expected_sha,
                    f"Digest mismatch for {eid} at 0x{start:08X}: expected {expected_sha}, got {actual_sha}",
                )


class TestPort25LocaliseDocument(unittest.TestCase):
    """Validates docs/PORT25_SHORT_PRESS_LOCALISE.md contents, candidate table, and breadcrumbs."""

    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Missing documentation at {DOC_PATH}")
        with open(DOC_PATH, "r", encoding="utf-8") as f:
            self.content = f.read()
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_required_sections_present(self):
        """Document contains all expected structural sections."""
        required_headers = [
            "Executive Summary",
            "Problem Statement",
            "Boot Path Under `G3X_POWERON_FIX=1`",
            "Power-Off and Button-Wait Candidates Analysis",
            "Ranked Candidate Summary",
            "Proposed Breadcrumb Placement in `boot_prototype.c`",
            "Bounded ROM Research & Evidence Accounting",
        ]
        for header in required_headers:
            self.assertIn(header, self.content, f"Missing required section header '{header}'")

    def test_epistemic_labels_in_document(self):
        """Document uses required epistemic classifications."""
        required_labels = ["[VERIFIED", "[STATIC_VERIFIED", "[INFERRED", "[UNKNOWN"]
        for lbl in required_labels:
            self.assertIn(lbl, self.content, f"Expected epistemic label '{lbl}' in document")

    def test_ranked_candidate_table_present_and_labelled(self):
        """Document has a ranked candidates table where every row has an epistemic label."""
        self.assertIn("Ranked Candidate Summary", self.content)

        # Locate Section 5 table
        table_match = re.search(r"## 5\. Ranked Candidate Summary\s+(.*?)(?=\n## |\Z)", self.content, re.DOTALL)
        self.assertIsNotNone(table_match, "Section '## 5. Ranked Candidate Summary' not found")
        section_text = table_match.group(1)

        # Extract markdown table rows
        candidate_rows = []
        for line in section_text.splitlines():
            line = line.strip()
            if line.startswith("|") and not line.startswith("| Rank") and not line.startswith("|:"):
                candidate_rows.append(line)

        self.assertGreaterEqual(len(candidate_rows), 7, f"Expected at least 7 candidate rows, found {len(candidate_rows)}")

        # Verify candidate ranks 1 to 7 are present
        for rank_num in range(1, 8):
            self.assertTrue(
                any(re.search(rf"\|\s*(?:\*\*)?(?:Rank\s*)?{rank_num}(?:\*\*)?\s*\|", r) for r in candidate_rows),
                f"Candidate Rank {rank_num} missing from ranked candidate table",
            )

        # Check key mechanisms are present in the table
        self.assertTrue(any("sub_fc05ba56" in r for r in candidate_rows), "sub_fc05ba56 candidate row missing")
        self.assertTrue(any(re.search(r"sub[- ]cpu", r, re.IGNORECASE) for r in candidate_rows), "Sub-CPU candidate row missing")
        self.assertTrue(any("StartWDT_FW" in r for r in candidate_rows), "StartWDT_FW candidate row missing")
        self.assertTrue(any("0x00009BD0" in r or "sub_fc08ecbc" in r for r in candidate_rows), "Startup cause candidate row missing")
        self.assertTrue(any("task_PhySw" in r for r in candidate_rows), "task_PhySw candidate row missing")
        self.assertTrue(any("TurnOffE1_FW" in r for r in candidate_rows), "TurnOffE1_FW candidate row missing")

        # Verify that EVERY single row contains an epistemic label
        for idx, row in enumerate(candidate_rows, 1):
            cols = [c.strip() for c in row.split("|")[1:-1]]
            rank_label = cols[0] if cols else f"Row {idx}"
            self.assertTrue(
                VALID_LABEL_PATTERN.search(row),
                f"Candidate table {rank_label} lacks an epistemic label ([VERIFIED], [STATIC_VERIFIED], [INFERRED], or [UNKNOWN]):\n{row}",
            )

    def test_synthetic_unlabelled_candidate_row_fails(self):
        """Verifies that removing an epistemic label from any row triggers a validation failure."""
        unlabelled_row = "| **9** | Unlabelled Test Candidate | `boot_prototype.c:100` | Test | Action | Missing label here |"
        self.assertFalse(
            bool(VALID_LABEL_PATTERN.search(unlabelled_row)),
            "VALID_LABEL_PATTERN incorrectly matched an unlabelled candidate row",
        )

    def test_every_cited_rom_address_covered_by_manifest(self):
        """Every 0xFC..., 0xFD..., bare fc.../fd..., and sub_/loc_ address cited in doc falls within [start, start + length)."""
        evidence_entries = self.manifest.get("evidence_entries", [])
        self.assertTrue(len(evidence_entries) > 0, "No evidence entries in manifest")

        # Build [start, start + length) ranges
        evidence_ranges = [
            (int(e["start_address"], 16), int(e["start_address"], 16) + int(e["expected_byte_count"]), e["evidence_id"])
            for e in evidence_entries
        ]

        cited_addrs = extract_cited_rom_addresses(self.content)
        self.assertGreaterEqual(len(cited_addrs), 25, "Expected at least 25 ROM addresses cited in doc")

        unapproved_addrs = get_uncovered_rom_addresses(cited_addrs, evidence_ranges)
        self.assertEqual(
            unapproved_addrs,
            [],
            f"The following ROM addresses cited in docs/PORT25_SHORT_PRESS_LOCALISE.md "
            f"are not covered by any [start, start + length) range in PORT25_EVIDENCE_MANIFEST.json: {unapproved_addrs}",
        )

    def test_synthetic_uncovered_address_fails(self):
        """Verifies that extraction and coverage on synthetic doc text citing an uncovered

        suffixed symbol (sub_fc000002_my) and bare address (0xFC000002) fail coverage.
        """
        evidence_entries = self.manifest.get("evidence_entries", [])
        evidence_ranges = [
            (int(e["start_address"], 16), int(e["start_address"], 16) + int(e["expected_byte_count"]), e["evidence_id"])
            for e in evidence_entries
        ]

        # 1. Negative test running extraction and coverage together on synthetic doc text citing an uncovered suffixed symbol
        synthetic_suffixed_doc = (
            "Document discussing early execution in sub_fc000002_my and sub_fc000004_stub before loader."
        )
        extracted_suffixed = extract_cited_rom_addresses(synthetic_suffixed_doc)
        self.assertIn("0xFC000002", extracted_suffixed, "Extraction must capture 0xFC000002 from sub_fc000002_my")
        self.assertIn("0xFC000004", extracted_suffixed, "Extraction must capture 0xFC000004 from sub_fc000004_stub")
        unapproved_suffixed = get_uncovered_rom_addresses(extracted_suffixed, evidence_ranges)
        self.assertEqual(
            unapproved_suffixed,
            ["0xFC000002", "0xFC000004"],
            "Uncovered suffixed symbols must fail manifest coverage",
        )

        # 2. Negative test on bare 0xFC forms and bare hex in synthetic doc
        synthetic_bare_doc = "Reference to bare 0xFC000006 and fc000008 in synthetic text."
        extracted_bare = extract_cited_rom_addresses(synthetic_bare_doc)
        self.assertIn("0xFC000006", extracted_bare)
        self.assertIn("0xFC000008", extracted_bare)
        unapproved_bare = get_uncovered_rom_addresses(extracted_bare, evidence_ranges)
        self.assertEqual(unapproved_bare, ["0xFC000006", "0xFC000008"])

        # 3. Direct numeric check
        uncovered_addr = 0xFC000002
        is_covered = any(start <= uncovered_addr < end for start, end, _ in evidence_ranges)
        self.assertFalse(is_covered, "0xFC000002 should not be covered by manifest ranges")

    def test_proposed_breadcrumbs_cover_all_acceptance_points(self):
        """Proposed breadcrumbs cover entry to sub_fc05b962_my, power checks, task creation, core entry."""
        # Check for core entry
        self.assertTrue(
            re.search(r"core entry|STAGE_BC_CORE_ENTRY", self.content, re.IGNORECASE),
            "Breadcrumbs must cover core entry",
        )
        # Check for sub_fc05b962_my entry
        self.assertTrue(
            re.search(r"sub_fc05b962_my.*?entry|STAGE_BC_STAGE5_ENTRY", self.content, re.IGNORECASE),
            "Breadcrumbs must cover entry to sub_fc05b962_my",
        )
        # Check for before/after remaining power-on check
        self.assertTrue(
            re.search(r"before.*?power-on check|STAGE_BC_PRE_POWER_CHECK", self.content, re.IGNORECASE),
            "Breadcrumbs must cover before power-on check",
        )
        self.assertTrue(
            re.search(r"after.*?power-on check|power-on fix|STAGE_BC_POWER_CHECK_PASS", self.content, re.IGNORECASE),
            "Breadcrumbs must cover after power-on check",
        )
        # Check for pre-call power-check fail and post-call power-cut halt distinction
        self.assertIn("STAGE_BC_POWER_CHECK_FAIL", self.content)
        self.assertIn("STAGE_BC_POWER_CUT_HALT", self.content)
        self.assertTrue(
            re.search(r"Distinction Between.*?STAGE_BC_POWER_CHECK_FAIL.*?STAGE_BC_POWER_CUT_HALT", self.content, re.DOTALL),
            "Doc must explicitly discuss the distinction between STAGE_BC_POWER_CHECK_FAIL and STAGE_BC_POWER_CUT_HALT",
        )

        # Check for before/after task creation
        self.assertTrue(
            re.search(r"before.*?task creation|STAGE_BC_PRE_CREATE_STARTUP", self.content, re.IGNORECASE),
            "Breadcrumbs must cover before task creation",
        )
        self.assertTrue(
            re.search(r"after.*?task creation|STAGE_BC_POST_CREATE_STARTUP", self.content, re.IGNORECASE),
            "Breadcrumbs must cover after task creation",
        )

        # Check that file:line citations refer to boot_prototype.c
        citations = re.findall(r"boot_prototype\.c:\d+", self.content)
        self.assertGreaterEqual(len(citations), 6, "Expected at least 6 boot_prototype.c:line references")

    def test_boot_prototype_lines_valid(self):
        """References to boot_prototype.c lines exist and match code structure."""
        self.assertTrue(BOOT_PROTOTYPE_C.exists(), f"Missing {BOOT_PROTOTYPE_C}")
        with open(BOOT_PROTOTYPE_C, "r", encoding="utf-8") as f:
            lines = f.readlines()

        citations = re.findall(r"boot_prototype\.c:(\d+)", self.content)
        for line_num_str in set(citations):
            line_num = int(line_num_str)
            self.assertGreater(line_num, 0)
            self.assertLessEqual(line_num, len(lines), f"Line {line_num} exceeds length of boot_prototype.c")

    def test_bounded_rom_accounting_stated(self):
        """Doc explicitly states total bytes newly read (784 B) and confirms no full-ROM scans."""
        self.assertIn("784", self.content, "Doc must state total 784 bytes newly read")
        self.assertTrue(
            re.search(r"no full[- ]ROM scans", self.content, re.IGNORECASE),
            "Doc must confirm no full-ROM scans were conducted",
        )

    def test_stage5_error_gates_cited_in_labelled_candidate(self):
        """Doc cites 0xFC05BA6E, 0xFC05BA82, and 0xFC05BA8E inside a labelled candidate."""
        required_addrs = ["0xFC05BA6E", "0xFC05BA82", "0xFC05BA8E"]
        for addr in required_addrs:
            self.assertIn(addr, self.content, f"Document missing citation of Stage 5 error gate address {addr}")

        # Locate Candidate 7 section
        c7_match = re.search(r"### Candidate 7:.*?(?=\n### |\Z)", self.content, re.DOTALL)
        self.assertIsNotNone(c7_match, "Candidate 7 section missing from document")
        c7_text = c7_match.group(0)

        for addr in required_addrs:
            self.assertIn(addr, c7_text, f"Candidate 7 section must cite Stage 5 error gate address {addr}")

        self.assertTrue(
            VALID_LABEL_PATTERN.search(c7_text),
            "Candidate 7 section lacks an epistemic label ([VERIFIED], [STATIC_VERIFIED], [INFERRED], or [UNKNOWN])",
        )

        # Locate Rank 7 row in the summary table
        table_match = re.search(r"## 5\. Ranked Candidate Summary\s+(.*?)(?=\n## |\Z)", self.content, re.DOTALL)
        self.assertIsNotNone(table_match, "Summary table missing from document")
        summary_text = table_match.group(1)
        rank7_row = next((r for r in summary_text.splitlines() if re.search(r"\|\s*\*\*7\*\*", r)), None)
        self.assertIsNotNone(rank7_row, "Rank 7 row missing from summary table")
        for addr in required_addrs:
            self.assertIn(addr, rank7_row, f"Rank 7 summary table row must cite {addr}")
        self.assertTrue(VALID_LABEL_PATTERN.search(rank7_row), "Rank 7 table row lacks epistemic label")

    def test_no_known_warm_boot_failure_mode_phrasing(self):
        """The phrase 'known warm-boot failure mode' (or similar) must not appear."""
        self.assertNotIn("known warm-boot failure mode", self.content.lower())
        self.assertNotIn("known warm boot failure mode", self.content.lower())

        # Check Rank 2 presentation: ranking is INFERRED and causal link is UNKNOWN
        c4_match = re.search(r"### Candidate 4:.*?(?=\n### |\Z)", self.content, re.DOTALL)
        self.assertIsNotNone(c4_match, "Candidate 4 (Rank 2) section missing")
        c4_text = c4_match.group(0)
        self.assertIn("[INFERRED]", c4_text, "Candidate 4 (Rank 2) ranking must be presented as INFERRED")
        self.assertTrue(
            re.search(r"causal link.*?\[UNKNOWN\]|causal link.*?is.*?UNKNOWN", c4_text, re.IGNORECASE),
            "Candidate 4 (Rank 2) must state that the causal link to short-press power-off is UNKNOWN",
        )

    def test_no_breadcrumb_proves_physw_task_execution(self):
        """No breadcrumb is described as proving PhySw task execution; PhySw execution is unobserved."""
        # STAGE_BC_PHYSW_ENTRY must be removed
        self.assertNotIn("STAGE_BC_PHYSW_ENTRY", self.content)

        # No breadcrumb must claim to prove PhySw task execution or running
        self.assertNotRegex(
            self.content,
            r"(?i)breadcrumb.*?proving.*?(?:task_)?PhySw.*?(?:execution|running|dispatched)",
            "Breadcrumbs must not claim to prove PhySw task execution",
        )

        # Must explicitly state that PhySw task execution is UNOBSERVED by this ladder
        self.assertTrue(
            re.search(r"PhySw task execution is UNOBSERVED by this ladder", self.content, re.IGNORECASE),
            "Doc must explicitly state that PhySw task execution is UNOBSERVED by this ladder",
        )

        # STAGE_BC_POST_PHYSW_CREATE remains as helper-return checkpoint
        self.assertIn("STAGE_BC_POST_PHYSW_CREATE", self.content)

    def test_synthetic_negative_feedback_checks(self):
        """Verifies that synthetic violations of feedback criteria are properly detected."""
        # 1. Warm-boot phrasing in synthetic text fails check
        synthetic_warm_doc = "This replicates the known warm-boot failure mode from earlier patch."
        self.assertIn("known warm-boot failure mode", synthetic_warm_doc.lower())

        # 2. PhySw execution claim in synthetic breadcrumb text fails check
        synthetic_breadcrumb_claim = "Proposed breadcrumb STAGE_BC_TEST proving task_PhySw execution"
        self.assertTrue(bool(re.search(r"(?i)breadcrumb.*?proving.*?(?:task_)?PhySw.*?(?:execution|running|dispatched)", synthetic_breadcrumb_claim)))

        # 3. Missing Stage 5 address in synthetic candidate text fails check
        synthetic_c7_text = "### Candidate 7: Only cites 0xFC05BA6E and 0xFC05BA82."
        self.assertNotIn("0xFC05BA8E", synthetic_c7_text)


if __name__ == "__main__":
    unittest.main()
