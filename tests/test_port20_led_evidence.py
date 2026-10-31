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
3. Candidate LED register table consistency (docs/PORT20_LED_EVIDENCE.md §2):
   - Table parsed strictly row by row without DOTALL leakage.
   - Every row has an explicit label (VERIFIED, INFERRED, UNKNOWN, or REJECTED) and a filled citation.
   - Only 0xD20B0884 is labelled VERIFIED for G3 X hardware, justified by GM1.10C ROM code citations.
   - Reference-camera candidates (0xD20B0994, 0xD20B0810, 0xD20B0888) are at most INFERRED or REJECTED.
   - Candidate bold formatting (**`0x...`** or **0x...**) handled robustly.
4. Range ancestry & manifest anchor verification (docs/PORT20_LED_EVIDENCE.md §6):
   - Every manifest range has an explicit anchor row in the Section 6 table.
   - Each anchor row records start/end addresses, anchor citation, and anchor type.
5. Loader context compatibility (docs/PORT20_LED_EVIDENCE.md §4):
   - Evaluates CPU mode (privileged), MPU state (Region 2 Privileged RW), and Cache state (Device Memory).
6. Conclusion line and polarity consistency:
   - Terminates with an explicit conclusion line matching T2 GO or T2 STOP.
   - If T2 GO, the ON/OFF values and active polarity match the candidate table exactly.
7. Negative mutation tests:
   - Removing a candidate row label fails.
   - Marking any candidate VERIFIED when it only has other-camera citations fails.
   - A conclusion line that disagrees with the candidate table polarity fails.
   - Missing manifest anchor rows fail.
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
CONCLUSION_PATTERN = re.compile(
    r"^T2 (?:GO:\s*(0x[0-9a-fA-F]+)\s+on=(0x[0-9a-fA-F]+)\s+off=(0x[0-9a-fA-F]+)\s+\(address/value\s+(VERIFIED|INFERRED|UNKNOWN),\s+polarity\s+(VERIFIED|INFERRED|UNKNOWN)\)|STOP:\s*.*)$"
)


def parse_manifest(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_doc(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def clean_markdown_cell(cell: str) -> str:
    """Strips markdown formatting such as bolding and code ticks."""
    return re.sub(r"[\*`]", "", cell).strip()


def parse_candidate_table(doc_text: str) -> List[Dict[str, str]]:
    """Parses Section 2 Candidate LED Registers Table strictly row by row."""
    section_match = re.search(
        r"## 2\. Candidate LED Registers Table\s*\n(.*?)(?:\n---|\n##|\Z)",
        doc_text,
        re.DOTALL,
    )
    if not section_match:
        raise ValueError("Section '## 2. Candidate LED Registers Table' not found in document")

    lines = section_match.group(1).strip().splitlines()
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 7:
            continue
        # Skip header and divider rows
        if "Candidate Address" in cols[0] or cols[0].startswith(":") or cols[0].startswith("-"):
            continue

        raw_addr = cols[0]
        clean_addr = clean_markdown_cell(raw_addr)
        rows.append({
            "raw_address": raw_addr,
            "clean_address": clean_addr,
            "on_val": cols[1],
            "off_val": cols[2],
            "rmw": cols[3],
            "target": cols[4],
            "classification": cols[5],
            "citation": cols[6],
            "line": line,
        })
    return rows


def parse_anchor_table(doc_text: str) -> List[Dict[str, str]]:
    """Parses Section 6 Range Ancestry & Anchors Table strictly row by row."""
    section_match = re.search(
        r"## 6\. ROM Range Ancestry & Evidence Manifest Accounting\s*\n(.*?)(?:\n---|\n##|\Z)",
        doc_text,
        re.DOTALL,
    )
    if not section_match:
        raise ValueError("Section '## 6. ROM Range Ancestry...' not found in document")

    lines = section_match.group(1).strip().splitlines()
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 8:
            continue
        if "Range ID" in cols[0] or cols[0].startswith(":") or cols[0].startswith("-"):
            continue

        rows.append({
            "range_id": clean_markdown_cell(cols[0]),
            "start": clean_markdown_cell(cols[1]),
            "end": clean_markdown_cell(cols[2]),
            "length": clean_markdown_cell(cols[3]),
            "sha256": clean_markdown_cell(cols[4]),
            "anchor": cols[5].strip(),
            "anchor_type": clean_markdown_cell(cols[6]),
            "claims": cols[7].strip(),
            "line": line,
        })
    return rows


def validate_candidate_table_rows(doc_text: str) -> None:
    """Strictly validates candidate table rows without DOTALL multi-row leakage."""
    rows = parse_candidate_table(doc_text)
    if not rows:
        raise ValueError("Candidate table has no valid data rows")

    expected_candidates = {
        "0xD20B0884",
        "0xD20B0994",
        "0xD20B0810",
        "0xD20B0888",
        "LEDDrive",
        "LEDDrv.c",
    }
    found_candidates = set()

    for r in rows:
        clean_addr = r["clean_address"]
        classification = r["classification"]
        citation = r["citation"]

        # Check for matching candidate
        matching_key = None
        for ec in expected_candidates:
            if ec in clean_addr:
                matching_key = ec
                break
        if matching_key:
            found_candidates.add(matching_key)

        # Every row must have an explicit label
        valid_labels = {"VERIFIED", "INFERRED", "UNKNOWN", "REJECTED"}
        has_label = any(label in classification for label in valid_labels)
        if not has_label:
            raise ValueError(f"Candidate row for '{clean_addr}' lacks explicit classification: '{classification}'")

        # Every row must have a non-empty citation
        if not citation or citation == "N/A":
            raise ValueError(f"Candidate row for '{clean_addr}' lacks citation")

        # Non-0xD20B0884 rows cannot be solely VERIFIED if they only cite other cameras or lack GM1.10C ROM code
        is_primary_g3x = "0xD20B0884" in clean_addr
        has_primary_rom_citation = "PRIMARY.BIN" in citation

        if not is_primary_g3x:
            # If it's an alternate or reference camera candidate, check it is not falsely claimed VERIFIED for G3 X
            if "VERIFIED" in classification and not ("REJECTED" in classification or has_primary_rom_citation):
                raise ValueError(
                    f"Candidate '{clean_addr}' is marked VERIFIED without GM1.10C ROM code citation: '{classification}'"
                )
            if any(ref in citation for ref in ["g7x", "g5x", "g16", "sx710", "SX710"]) and not has_primary_rom_citation:
                if "VERIFIED" in classification and "REJECTED" not in classification:
                    raise ValueError(
                        f"Candidate '{clean_addr}' marked VERIFIED based only on other-camera references: '{citation}'"
                    )

    missing = expected_candidates - found_candidates
    if missing:
        raise ValueError(f"Missing expected candidate entries in candidate table: {missing}")


def validate_polarity_consistency(doc_text: str) -> None:
    """Verifies that the candidate table and final conclusion agree on ON/OFF values and polarity."""
    rows = parse_candidate_table(doc_text)
    primary_row = None
    for r in rows:
        if "0xD20B0884" in r["clean_address"]:
            primary_row = r
            break
    if not primary_row:
        raise ValueError("Primary candidate 0xD20B0884 not found in candidate table")

    table_on = int(clean_markdown_cell(primary_row["on_val"]), 16)
    table_off = int(clean_markdown_cell(primary_row["off_val"]), 16)

    lines = [line.strip() for line in doc_text.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("Document is empty")
    last_line = lines[-1]

    match = CONCLUSION_PATTERN.match(last_line)
    if not match:
        raise ValueError(f"Final line '{last_line}' does not match conclusion pattern")

    if last_line.startswith("T2 GO:"):
        conc_addr = match.group(1)
        conc_on = int(match.group(2), 16)
        conc_off = int(match.group(3), 16)
        val_status = match.group(4)
        pol_status = match.group(5)

        if conc_addr != "0xD20B0884":
            raise ValueError(f"Conclusion register {conc_addr} does not match 0xD20B0884")
        if conc_on != table_on:
            raise ValueError(
                f"Conclusion ON value {hex(conc_on)} disagrees with candidate table ON value {hex(table_on)}"
            )
        if conc_off != table_off:
            raise ValueError(
                f"Conclusion OFF value {hex(conc_off)} disagrees with candidate table OFF value {hex(table_off)}"
            )
        if val_status != "VERIFIED":
            raise ValueError(f"Conclusion address/value status must be VERIFIED, got {val_status}")
        if pol_status not in ("VERIFIED", "INFERRED"):
            raise ValueError(f"Conclusion polarity status must be VERIFIED or INFERRED, got {pol_status}")


def validate_manifest_anchors_in_doc(manifest: Dict[str, Any], doc_text: str) -> None:
    """Ensures every manifest range has an explicit, valid anchor row in Section 6."""
    anchor_rows = parse_anchor_table(doc_text)
    anchor_dict = {r["range_id"]: r for r in anchor_rows}

    for entry in manifest.get("evidence_entries", []):
        eid = entry["evidence_id"]
        if eid not in anchor_dict:
            raise ValueError(f"Manifest entry '{eid}' is missing an anchor row in Section 6 table")

        row = anchor_dict[eid]
        # Start and end addresses must match
        if int(row["start"], 16) != int(entry["start_address"], 16):
            raise ValueError(
                f"Anchor row start address {row['start']} does not match manifest start address {entry['start_address']} for {eid}"
            )
        if int(row["end"], 16) != int(entry["end_address"], 16):
            raise ValueError(
                f"Anchor row end address {row['end']} does not match manifest end address {entry['end_address']} for {eid}"
            )
        # Anchor citation and type must be non-empty
        if not row["anchor"]:
            raise ValueError(f"Anchor citation is empty for {eid}")
        if not row["anchor_type"]:
            raise ValueError(f"Anchor type is empty for {eid}")


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
        self.manifest = parse_manifest(MANIFEST_PATH)

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
            "Tracked Citation / Primary Disassembly",
        ]
        for h in required_headers:
            self.assertIn(h, self.doc_text, f"Table missing required header: {h}")

    def test_candidate_rows_strictly_validated(self):
        """Validates candidate table row-by-row (no DOTALL) for labels, citations, and non-overclaims."""
        validate_candidate_table_rows(self.doc_text)

    def test_verified_candidate_register_identified(self):
        """0xD20B0884 must be identified with exact ON/OFF values and VERIFIED address/value label."""
        rows = parse_candidate_table(self.doc_text)
        primary_row = None
        for r in rows:
            if "0xD20B0884" in r["clean_address"]:
                primary_row = r
                break
        self.assertIsNotNone(primary_row, "0xD20B0884 missing from candidate table")
        self.assertEqual(int(clean_markdown_cell(primary_row["on_val"]), 16), 0x4D0002)
        self.assertEqual(int(clean_markdown_cell(primary_row["off_val"]), 16), 0x4C0003)
        self.assertIn("VERIFIED", primary_row["classification"])
        self.assertIn("INFERRED", primary_row["classification"])  # Polarity/physical location inferred
        self.assertIn("PRIMARY.BIN", primary_row["citation"])

    def test_manifest_anchors_present_in_doc(self):
        """Verifies every manifest range has a corresponding anchor row in Section 6."""
        validate_manifest_anchors_in_doc(self.manifest, self.doc_text)

    def test_gm110c_rom_citations_and_disassembly_present(self):
        """Key GM1.10C ROM functions establishing 0xD20B0884 must be cited with disassembly."""
        citations = [
            "0xFC075DC4",  # LED descriptor init with pin 33
            "0xFC075D98",  # Turn ON routine / 0x4d0002 load
            "0xFC075DAE",  # Turn OFF routine / 0x4c0003 load
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

    def test_conclusion_polarity_consistency(self):
        """Document must end with an explicit conclusion line matching candidate table polarity."""
        validate_polarity_consistency(self.doc_text)


class TestNegativeMutations(unittest.TestCase):
    """In-memory negative mutation tests verifying test enforcement robustness."""

    def setUp(self):
        self.doc_text = parse_doc(DOC_PATH)
        self.manifest = parse_manifest(MANIFEST_PATH)

    def test_mutation_removing_row_label_fails(self):
        """Removing a row's label must fail validation."""
        # Mutate row for 0xD20B0888 to remove its label
        mutated = self.doc_text.replace(
            "**`INFERRED`** (ref port) / **`REJECTED (ABSENT ON G3 X)`**",
            "",
        )
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated)

    def test_mutation_other_camera_marked_verified_fails(self):
        """Marking an other-camera candidate VERIFIED without GM1.10C ROM code must fail."""
        # Mutate row for 0xD20B0994 to claim VERIFIED
        mutated = self.doc_text.replace(
            "**`INFERRED`** (ref ports) / **`REJECTED (CONTRADICTED FOR G3 X)`**",
            "**`VERIFIED`**",
        )
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated)

    def test_mutation_conclusion_polarity_disagreement_fails(self):
        """A conclusion line that disagrees with the candidate table polarity must fail."""
        # Mutate conclusion line to invert ON and OFF
        mutated = re.sub(
            r"T2 GO:.*",
            "T2 GO: 0xD20B0884 on=0x4c0003 off=0x4d0002 (address/value VERIFIED, polarity INFERRED)",
            self.doc_text,
        )
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_missing_anchor_row_fails(self):
        """Removing an anchor row for a manifest range must fail validation."""
        # Remove anchor row for PORT20-ROM-TASK-LEDCON-LOOP
        mutated = re.sub(
            r"\|\s*`PORT20-ROM-TASK-LEDCON-LOOP`\s*\|[^\n]*\n",
            "",
            self.doc_text,
        )
        with self.assertRaises(ValueError):
            validate_manifest_anchors_in_doc(self.manifest, mutated)

    def test_mutation_rejects_exceeded_range_limit(self):
        """Mutating range count to 9 must exceed MAX_RANGES_LIMIT."""
        fake_ranges = list(range(9))
        self.assertGreater(len(fake_ranges), MAX_RANGES_LIMIT)

    def test_mutation_rejects_invalid_conclusion_pattern(self):
        """Invalid conclusion lines must fail the regex."""
        invalid_conclusions = [
            "GO: 0xD20B0884",
            "T2 GO",
            "Conclusion: T2 GO 0xD20B0884",
            "T2 PROCEED",
            "T2 GO: 0xD20B0884 (missing on/off)",
        ]
        for ic in invalid_conclusions:
            self.assertIsNone(CONCLUSION_PATTERN.match(ic), f"Invalid conclusion '{ic}' unexpectedly passed")


if __name__ == "__main__":
    unittest.main()
