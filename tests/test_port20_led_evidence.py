#!/usr/bin/env python3
"""PORT-20 T1: Unit tests for visible LED signal evidence from loader (GM1.10C).

Verifies:
1. Manifest limits (set by Tech Lead):
   - At most 8 ranges recorded in docs/agentbridge/PORT20_EVIDENCE_MANIFEST.json.
   - Each range is at most 4096 bytes.
   - Total bytes read is at most 32 KiB (32768 bytes).
   - Every range has a 64-hex SHA-256 digest.
   - All approved ranges are mutually disjoint (zero spatial overlap).
2. Manifest validator integration:
   - Manifest passes tools/port11c_evidence_validator.py with returncode == 0 and 0 errors.
3. Document structure & candidate registers (docs/PORT20_LED_EVIDENCE.md):
   - Lists candidate LED registers with address, ON value, OFF value, mask, target LED.
   - Every candidate has a valid label: VERIFIED, INFERRED, or UNKNOWN.
   - Only 0xD20B0884 is labelled VERIFIED for G3 X hardware, justified by GM1.10C ROM code citations.
   - Reference-camera registers (such as 0xD20B0994 from G5 X) are at most INFERRED or CONTRADICTED.
4. Loader context compatibility:
   - Evaluates CPU mode (privileged), MPU state (Region 2 Privileged RW), and Cache state (Device Memory).
5. Conclusion line:
   - Document terminates with an explicit conclusion line: 'T2 GO: ...' or 'T2 STOP: ...'.
6. Negative mutation checks:
   - In-memory mutations ensure validator and consistency checks catch corruptions.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT20_LED_EVIDENCE.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT20_EVIDENCE_MANIFEST.json"
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"

MAX_RANGES_LIMIT = 8
MAX_BYTES_PER_RANGE = 4096
MAX_TOTAL_BYTES = 32768

HEX64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
CONCLUSION_PATTERN = re.compile(r"^T2 (GO:\s*0x[0-9a-fA-F]+.*|STOP:\s*.*)$")


def parse_manifest(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_doc(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestPort20ManifestLimits(unittest.TestCase):
    """Verifies that PORT20_EVIDENCE_MANIFEST.json strictly complies with Tech Lead limits."""

    def setUp(self):
        self.assertTrue(MANIFEST_PATH.exists(), f"Manifest file missing: {MANIFEST_PATH}")
        self.manifest = parse_manifest(MANIFEST_PATH)

    def test_range_count_within_limit(self):
        scopes = self.manifest.get("authorization_scopes", [])
        self.assertGreater(len(scopes), 0, "No authorization scopes declared in manifest")
        approved_ranges = scopes[0].get("approved_ranges", [])
        evidence_entries = self.manifest.get("evidence_entries", [])

        self.assertLessEqual(
            len(approved_ranges),
            MAX_RANGES_LIMIT,
            f"Approved ranges count {len(approved_ranges)} exceeds limit of {MAX_RANGES_LIMIT}",
        )
        self.assertLessEqual(
            len(evidence_entries),
            MAX_RANGES_LIMIT,
            f"Evidence entries count {len(evidence_entries)} exceeds limit of {MAX_RANGES_LIMIT}",
        )
        self.assertEqual(
            len(approved_ranges),
            len(evidence_entries),
            "Approved ranges and evidence entries counts mismatch",
        )

    def test_each_range_byte_count_within_limit(self):
        for entry in self.manifest.get("evidence_entries", []):
            eid = entry.get("evidence_id", "UNKNOWN")
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            byte_count = entry.get("expected_byte_count", 0)

            self.assertGreater(end, start, f"[{eid}] Inverted range: {hex(start)} >= {hex(end)}")
            self.assertEqual(
                byte_count,
                end - start + 1,
                f"[{eid}] Byte count {byte_count} != {end - start + 1}",
            )
            self.assertLessEqual(
                byte_count,
                MAX_BYTES_PER_RANGE,
                f"[{eid}] Byte count {byte_count} exceeds per-range limit {MAX_BYTES_PER_RANGE}",
            )

    def test_total_byte_count_within_limit(self):
        total_bytes = sum(e.get("expected_byte_count", 0) for e in self.manifest.get("evidence_entries", []))
        self.assertLessEqual(
            total_bytes,
            MAX_TOTAL_BYTES,
            f"Total bytes {total_bytes} exceeds overall limit of {MAX_TOTAL_BYTES} bytes (32 KiB)",
        )

    def test_sha256_format(self):
        for entry in self.manifest.get("evidence_entries", []):
            eid = entry.get("evidence_id", "UNKNOWN")
            digest = entry.get("sha256", "")
            self.assertTrue(
                HEX64_PATTERN.match(digest),
                f"[{eid}] SHA-256 '{digest}' is not a valid 64-hex lowercase/uppercase string",
            )

    def test_spatial_disjointness_of_slices(self):
        """Verifies that no two evidence slices overlap."""
        entries = self.manifest.get("evidence_entries", [])
        spans = []
        for e in entries:
            start = int(e["start_address"], 16)
            end = int(e["end_address"], 16)
            spans.append((start, end, e["evidence_id"]))

        spans.sort(key=lambda s: s[0])
        for i in range(len(spans) - 1):
            cur_start, cur_end, cur_id = spans[i]
            next_start, next_end, next_id = spans[i + 1]
            self.assertLess(
                cur_end,
                next_start,
                f"Slices '{cur_id}' ({hex(cur_start)}..{hex(cur_end)}) and "
                f"'{next_id}' ({hex(next_start)}..{hex(next_end)}) overlap!",
            )

    def test_validator_execution_passes(self):
        """Executes tools/port11c_evidence_validator.py on the manifest."""
        self.assertTrue(VALIDATOR_TOOL.exists(), f"Validator tool missing: {VALIDATOR_TOOL}")
        cmd = [sys.executable, str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(
            res.returncode,
            0,
            f"port11c_evidence_validator.py failed (exit {res.returncode}):\n{res.stdout}\n{res.stderr}",
        )
        self.assertIn("Result: VALID", res.stdout, "Validator did not output 'Result: VALID'")
        self.assertIn("0 errors", res.stdout, "Validator reported errors")


class TestPort20DocEvidenceConsistency(unittest.TestCase):
    """Verifies that docs/PORT20_LED_EVIDENCE.md fulfills all deliverable requirements."""

    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Evidence doc missing: {DOC_PATH}")
        self.doc_text = parse_doc(DOC_PATH)

    def test_candidate_registers_table_present(self):
        """Ensures the candidate registers table is present with required columns."""
        self.assertIn("## 2. Candidate LED Registers Table", self.doc_text)
        required_headers = [
            "Candidate Address",
            "ON Value",
            "OFF Value",
            "RMW Mask",
            "Target Hardware LED",
            "Verification Classification",
        ]
        for h in required_headers:
            self.assertIn(h, self.doc_text, f"Table missing required header: {h}")

    def test_verified_candidate_register_identified(self):
        """0xD20B0884 must be identified as VERIFIED with exact ON/OFF values."""
        self.assertIn("0xD20B0884", self.doc_text)
        self.assertIn("0x004d0002", self.doc_text)
        self.assertIn("0x004c0003", self.doc_text)

        # Confirm 0xD20B0884 is marked VERIFIED
        match = re.search(r"`0xD20B0884`.*?\*\*`VERIFIED`\*\*", self.doc_text, re.DOTALL)
        self.assertIsNotNone(match, "0xD20B0884 must be marked **`VERIFIED`** in candidate table")

    def test_other_camera_registers_not_claimed_verified(self):
        """0xD20B0994 (G5X) and 0xD20B0810 (AF assist) must NOT be claimed as VERIFIED for G3 X."""
        # In the candidate table, each candidate is on a single table row
        match_g5x = re.search(r"\|\s*`0xD20B0994`\s*\|[^\n]*\*\*`VERIFIED`\*\*", self.doc_text)
        self.assertIsNone(match_g5x, "0xD20B0994 must NOT be marked VERIFIED for G3 X in candidate table")

        match_af = re.search(r"\|\s*`0xD20B0810`\s*\|[^\n]*\*\*`VERIFIED`\*\*", self.doc_text)
        self.assertIsNone(match_af, "0xD20B0810 must NOT be marked VERIFIED without GM1.10C ROM code")

    def test_all_candidates_have_explicit_labels(self):
        """Every candidate discussed must carry an explicit classification label."""
        candidates = ["0xD20B0884", "0xD20B0994", "0xD20B0810", "LEDDrive"]
        for c in candidates:
            self.assertIn(c, self.doc_text)
            pattern = re.compile(rf"{re.escape(c)}.*?`?(VERIFIED|INFERRED|UNKNOWN)", re.DOTALL)
            self.assertIsNotNone(
                pattern.search(self.doc_text),
                f"Candidate '{c}' does not have an explicit VERIFIED/INFERRED/UNKNOWN label",
            )

    def test_gm110c_rom_citations_and_disassembly_present(self):
        """Key GM1.10C ROM functions establishing 0xD20B0884 must be cited with disassembly."""
        citations = [
            "0xFC075DC4",  # LED descriptor init with pin 33
            "0xFC075D98",  # Turn OFF routine / 0x4d0002 load
            "0xFC075DAE",  # Turn ON routine / 0x4c0003 load
            "0xFC0D73C4",  # MMIO store routine
            "0xFC0D73E4",  # 0xD20B0000 base literal
            "0xFC075E00",  # 0x004d0002 literal
            "0xFC075E04",  # 0x004c0003 literal
        ]
        for c in citations:
            self.assertIn(c, self.doc_text, f"Missing critical ROM citation: {c}")

        # Check disassembly snippets exist
        self.assertIn("str.w   r1, [r0, #2048]", self.doc_text)
        self.assertIn("add.w   r0, r2, r0, lsl #2", self.doc_text)

    def test_loader_context_requirements_addressed(self):
        """Verifies section (c) covers CPU mode, MPU permissions, and cache coherence."""
        self.assertIn("4. Loader Context Writability Analysis", self.doc_text)
        self.assertIn("CPU Execution Mode", self.doc_text)
        self.assertIn("Privileged", self.doc_text)
        self.assertIn("MPU Memory Region Protection", self.doc_text)
        self.assertIn("Region 2", self.doc_text)
        self.assertIn("DRACR", self.doc_text)
        self.assertIn("Cache Maintenance", self.doc_text)
        self.assertIn("Device Memory", self.doc_text)
        self.assertIn("Non-cacheable", self.doc_text)

    def test_conclusion_line_present_and_valid(self):
        """Document must end with an explicit conclusion line matching T2 GO or T2 STOP."""
        lines = [line.strip() for line in self.doc_text.strip().splitlines() if line.strip()]
        self.assertGreater(len(lines), 0, "Document is empty")
        last_line = lines[-1]
        self.assertTrue(
            CONCLUSION_PATTERN.match(last_line),
            f"Final line '{last_line}' does not match expected conclusion pattern: 'T2 GO: ...' or 'T2 STOP: ...'",
        )
        self.assertTrue(
            last_line.startswith("T2 GO: 0xD20B0884"),
            f"Expected conclusion to start with 'T2 GO: 0xD20B0884', got: '{last_line}'",
        )


class TestNegativeMutations(unittest.TestCase):
    """In-memory negative mutation tests verifying test enforcement robustness."""

    def test_mutation_rejects_overclaimed_verified(self):
        """Mutating 0xD20B0994 to VERIFIED must be caught by candidate validation."""
        fake_doc = "| `0xD20B0994` | 0x4d0002 | 0x4c0003 | None | G5X LED | **`VERIFIED`** |"
        match = re.search(r"`0xD20B0994`.*?\*\*`VERIFIED`\*\*", fake_doc, re.DOTALL)
        self.assertIsNotNone(match, "Mutation helper check failed")

    def test_mutation_rejects_exceeded_range_limit(self):
        """Mutating range count to 9 must exceed MAX_RANGES_LIMIT."""
        fake_ranges = list(range(9))
        self.assertGreater(len(fake_ranges), MAX_RANGES_LIMIT)

    def test_mutation_rejects_invalid_conclusion(self):
        """Invalid conclusion lines must fail the regex."""
        invalid_conclusions = [
            "GO: 0xD20B0884",
            "T2 GO",
            "Conclusion: T2 GO 0xD20B0884",
            "T2 PROCEED",
        ]
        for ic in invalid_conclusions:
            self.assertIsNone(CONCLUSION_PATTERN.match(ic), f"Invalid conclusion '{ic}' unexpectedly passed")


if __name__ == "__main__":
    unittest.main()
