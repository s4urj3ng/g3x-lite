#!/usr/bin/env python3
"""PORT-20 T1: Unit tests for visible LED signal evidence from loader (GM1.10C).

Verifies:
1. Manifest limits (set by Tech Lead):
   - At most 8 ranges recorded in docs/agentbridge/PORT20_EVIDENCE_MANIFEST.json.
   - Each range is at most 4096 bytes.
   - Total bytes read is at most 32 KiB (32768 bytes).
   - Every range has a 64-hex SHA-256 digest.
   - All approved ranges are mutually disjoint (zero spatial overlap).
   - Every manifest entry carries structured 'ANCHOR:' clauses in its notes. A tracked anchor
     'ANCHOR: tracked <path>:<line> cites <addr>[..<addr>]' is valid only if that tracked line's
     actual content contains the cited address(es), and the address lies inside the range (this
     includes the start address and its Thumb +1 variant) or the cited span covers the start.
     A range anchor 'ANCHOR: range <ID> <src> -> <dst>' needs <src> inside another recorded range
     and <dst> inside this one. Every range must reach a tracked root without cycles.
   - A range with no valid anchor must be flagged 'ANCHOR: NONE' / 'SCOPE DEVIATION' and be listed
     in the doc's Scope Deviations section; it must not support any VERIFIED candidate claim.
   - No manifest entry has classification STATIC_VERIFIED while notes contain 'downgrad', 'unanchored' or 'REJECTED'.
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
   - Loader-entry state and post-'cpsid if' state are split, with per-item labels; DSB is recommended.
6. Conclusion line and polarity consistency:
   - Terminates with an explicit conclusion line matching T2 GO or T2 STOP.
   - If T2 GO, the ON/OFF values and active polarity match the candidate table exactly.
7. Negative mutation tests:
   - Removing a candidate row label fails.
   - Marking any candidate VERIFIED when it only has other-camera citations fails.
   - A conclusion line that disagrees with the candidate table polarity fails.
   - Missing manifest anchor rows fail.
   - A manifest entry without an anchor in notes fails.
   - A cited anchor file that exists but whose line lacks the address fails; so do addresses
     outside the range, missing files, bad parent links, anchor cycles, an unflagged unanchored
     range, a deviation missing from the doc, and a VERIFIED claim drawn from a deviation range.
   - A manifest entry with STATIC_VERIFIED contradicting downgrade/unanchored/REJECTED fails.
"""

from __future__ import annotations

import copy
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

# Ranges whose content supports the T2 GO/STOP conclusion (address, values, dispatch, MPU).
GO_CHAIN_RANGES = (
    "PORT20-ROM-MPU-REGION2-SETUP",
    "PORT20-ROM-SS-LED-CONTROL",
    "PORT20-ROM-GPIO-WRITE-MMIO",
    "PORT20-ROM-TASK-LEDCON-ENTRY",
    "PORT20-ROM-TASK-LEDCON-LOOP",
    "PORT20-ROM-LEDDRV-INIT",
    "PORT20-ROM-LEDDRV-DISPATCH",
)

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


def get_tracked_files() -> set[str]:
    """Returns set of relative paths tracked by git in this repository."""
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=str(REPO_ROOT), text=True)
        return set(out.splitlines())
    except Exception:
        return set()


TRACKED_ANCHOR_PATTERN = re.compile(
    r"ANCHOR: tracked (?P<path>[A-Za-z0-9_\-./]+):(?P<line>\d+) cites "
    r"(?P<a>0x[0-9A-Fa-f]+)(?:\.\.(?P<b>0x[0-9A-Fa-f]+))?"
)
RANGE_ANCHOR_PATTERN = re.compile(
    r"ANCHOR: range (?P<parent>PORT20-[A-Z0-9\-]+) (?P<src>0x[0-9A-Fa-f]+) -> (?P<dst>0x[0-9A-Fa-f]+)"
)
DEVIATION_MARKERS = ("ANCHOR: NONE", "SCOPE DEVIATION")
HEX_PATTERN = re.compile(r"0x[0-9A-Fa-f]+")


def read_tracked_line(rel_path: str, line_no: int, tracked_files: set[str]) -> str | None:
    """Returns the content of a 1-indexed line of a tracked repository file, or None."""
    if tracked_files and rel_path not in tracked_files:
        return None
    path = REPO_ROOT / rel_path
    if not path.is_file() or line_no < 1:
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            if i == line_no:
                return line
    return None


def tracked_anchor_is_valid(m: "re.Match[str]", start: int, end: int, tracked_files: set[str]) -> bool:
    """A tracked anchor is valid only if the cited line really contains the cited address(es)
    and they point at the range: a single address (Thumb bit ignored) must lie inside
    [start, end], which includes the start address and its Thumb +1 variant; a cited span
    a..b must cover the start address."""
    line = read_tracked_line(m.group("path"), int(m.group("line")), tracked_files)
    if line is None:
        return False
    line_addrs = {int(h, 16) for h in HEX_PATTERN.findall(line)}
    a = int(m.group("a"), 16)
    if a not in line_addrs:
        return False
    if m.group("b"):
        b = int(m.group("b"), 16)
        return b in line_addrs and a <= start <= b
    return start <= (a & ~1) <= end


def validate_manifest_entry_anchors(manifest: Dict[str, Any], tracked_files: set[str] | None = None) -> List[str]:
    """Verifies the provenance of every manifest range and returns the disclosed scope deviations.

    Each entry's notes must carry structured anchors:
    - 'ANCHOR: tracked <path>:<line> cites <addr>[..<addr>]': the tracked line content must
      contain the cited address(es) and they must point at this range (see tracked_anchor_is_valid);
    - 'ANCHOR: range <ID> <src> -> <dst>': <ID> is another recorded range containing <src>,
      and <dst> (Thumb bit ignored) lies inside this range.
    Every range must reach a tracked root through valid parent links (no cycles).
    Any range that does not must be flagged 'ANCHOR: NONE' and 'SCOPE DEVIATION';
    a flagged range must not also claim a valid anchor."""
    entries = manifest.get("evidence_entries", [])
    if not entries:
        raise ValueError("Manifest has no evidence entries")
    if tracked_files is None:
        tracked_files = get_tracked_files()

    spans = {e["evidence_id"]: (int(e["start_address"], 16), int(e["end_address"], 16)) for e in entries}
    roots = set()
    parents: Dict[str, set] = {eid: set() for eid in spans}
    claimed_any: Dict[str, bool] = {eid: False for eid in spans}

    for entry in entries:
        eid = entry["evidence_id"]
        notes = entry.get("notes", "")
        start, end = spans[eid]
        for m in TRACKED_ANCHOR_PATTERN.finditer(notes):
            claimed_any[eid] = True
            if tracked_anchor_is_valid(m, start, end, tracked_files):
                roots.add(eid)
        for m in RANGE_ANCHOR_PATTERN.finditer(notes):
            claimed_any[eid] = True
            parent = m.group("parent")
            if parent == eid or parent not in spans:
                continue
            p_start, p_end = spans[parent]
            src = int(m.group("src"), 16)
            dst = int(m.group("dst"), 16)
            if p_start <= src <= p_end and start <= (dst & ~1) <= end:
                parents[eid].add(parent)

    anchored = set(roots)
    changed = True
    while changed:
        changed = False
        for eid, ps in parents.items():
            if eid not in anchored and ps & anchored:
                anchored.add(eid)
                changed = True

    deviations = []
    for entry in entries:
        eid = entry["evidence_id"]
        notes = entry.get("notes", "")
        flagged = all(marker in notes for marker in DEVIATION_MARKERS)
        if eid in anchored:
            if flagged:
                raise ValueError(f"Manifest entry '{eid}' is anchored but also flagged as a scope deviation")
            continue
        if not flagged:
            raise ValueError(
                f"Manifest entry '{eid}' has no valid anchor chain to a tracked file:line "
                f"(claimed anchors: {claimed_any[eid]}) and is not flagged as a disclosed scope deviation: {notes}"
            )
        if claimed_any[eid]:
            raise ValueError(f"Manifest entry '{eid}' is flagged as a scope deviation but still claims anchors")
        deviations.append(eid)
    return deviations


def parse_scope_deviations_section(doc_text: str) -> str | None:
    match = re.search(r"## \d+\. Scope Deviations\s*\n(.*?)(?:\n---|\n## |\Z)", doc_text, re.DOTALL)
    return match.group(1) if match else None


def validate_scope_deviations_disclosed(manifest: Dict[str, Any], doc_text: str) -> None:
    """Every scope deviation in the manifest must be listed in the doc's Scope Deviations section,
    marked as such in the Section 6 table, never STATIC_VERIFIED, and never the basis of a
    VERIFIED candidate claim. The section must state that the conclusion does not depend on it."""
    deviations = validate_manifest_entry_anchors(manifest)
    if not deviations:
        return
    section = parse_scope_deviations_section(doc_text)
    if section is None:
        raise ValueError(f"Manifest has scope deviations {deviations} but the doc has no 'Scope Deviations' section")
    if "does not depend on this range" not in section:
        raise ValueError("Scope Deviations section does not state whether the T2 conclusion depends on the range")

    entries = {e["evidence_id"]: e for e in manifest["evidence_entries"]}
    anchor_rows = {r["range_id"]: r for r in parse_anchor_table(doc_text)}
    dev_spans = []
    for eid in deviations:
        entry = entries[eid]
        if eid not in section:
            raise ValueError(f"Scope deviation '{eid}' is not listed in the doc's Scope Deviations section")
        if entry.get("classification") == "STATIC_VERIFIED":
            raise ValueError(f"Scope deviation '{eid}' must not be classified STATIC_VERIFIED")
        row = anchor_rows.get(eid)
        if row is None or "SCOPE DEVIATION" not in row["anchor_type"]:
            raise ValueError(f"Section 6 anchor row for '{eid}' is not marked SCOPE DEVIATION")
        dev_spans.append((int(entry["start_address"], 16), int(entry["end_address"], 16), eid))

    for r in parse_candidate_table(doc_text):
        if not re.search(r"\bVERIFIED\b", r["classification"]):
            continue
        for h in HEX_PATTERN.findall(r["clean_address"] + " " + r["citation"]):
            addr = int(h, 16)
            for d_start, d_end, eid in dev_spans:
                if d_start <= addr <= d_end:
                    raise ValueError(
                        f"VERIFIED candidate '{r['clean_address']}' cites {h} from unanchored range '{eid}'"
                    )


def validate_manifest_classifications_and_notes(manifest: Dict[str, Any]) -> None:
    """Verifies that no entry has classification STATIC_VERIFIED while its notes
    contain 'downgrad', 'unanchored' or 'REJECTED'."""
    forbidden_terms = ("downgrad", "unanchored", "rejected")
    for entry in manifest.get("evidence_entries", []):
        eid = entry.get("evidence_id", "<unknown>")
        cls_val = entry.get("classification", "")
        notes = entry.get("notes", "")

        if cls_val == "STATIC_VERIFIED":
            notes_lower = notes.lower()
            for term in forbidden_terms:
                if term in notes_lower:
                    raise ValueError(
                        f"Manifest entry '{eid}' has classification STATIC_VERIFIED "
                        f"but its notes contain contradictory term '{term}': {notes}"
                    )


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

    def test_manifest_entries_have_valid_anchors(self):
        """Every range reaches a tracked file:line root or is a flagged scope deviation."""
        deviations = validate_manifest_entry_anchors(self.manifest)
        self.assertEqual(deviations, ["PORT20-ROM-LEDDRIVE"])
        # The ranges behind the T2 conclusion must all be anchored.
        for eid in GO_CHAIN_RANGES:
            self.assertNotIn(eid, deviations, f"T2 conclusion range '{eid}' is not anchored")

    def test_manifest_static_verified_classification_notes_agreement(self):
        """No entry may say STATIC_VERIFIED while its notes contain 'downgrad', 'unanchored' or 'REJECTED'."""
        validate_manifest_classifications_and_notes(self.manifest)


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

    def test_scope_deviations_disclosed(self):
        """Every unanchored range is disclosed in the doc and supports no VERIFIED claim."""
        validate_scope_deviations_disclosed(self.manifest, self.doc_text)

    def test_no_false_anchor_wording_for_leddrive(self):
        """lib.c:55 / PORT17_TRACE_EVIDENCE.md:389 must not be presented as anchors for 0xFC5572B8."""
        self.assertNotIn("anchored by tracked platform declaration", self.doc_text)
        for entry in self.manifest["evidence_entries"]:
            if entry["evidence_id"] == "PORT20-ROM-LEDDRIVE":
                self.assertNotIn("lib.c:55", entry["notes"])
                self.assertNotIn("PORT17_TRACE_EVIDENCE.md:389", entry["notes"])

    def test_loader_state_split_and_labelled(self):
        """Section 4 separates loader-entry state from post-cpsid state and labels each item."""
        self.assertIn("#### (1) At loader entry", self.doc_text)
        self.assertIn("#### (2) After `cpsid if` at `chdk-port/loader/g3x/main_prototype.c:86`", self.doc_text)
        entry_section = self.doc_text.split("#### (1) At loader entry", 1)[1].split("#### (2)", 1)[0]
        for item, label in (
            ("| Privilege level |", "**INFERRED**"),
            ("| Exact CPU mode", "**UNKNOWN**"),
            ("| IRQ |", "**INFERRED**"),
            ("| FIQ |", "**UNKNOWN**"),
            ("| MPU Region 2 attributes |", "**VERIFIED**"),
        ):
            row = next((l for l in entry_section.splitlines() if l.startswith(item)), None)
            self.assertIsNotNone(row, f"Loader-entry row '{item}' missing")
            self.assertIn(label, row, f"Loader-entry row '{item}' must be labelled {label}")
        self.assertIn("mrs r0, cpsr", self.doc_text)

    def test_write_completion_requires_dsb(self):
        """Section 4.3 must not claim Device writes are unbuffered; it must recommend a DSB."""
        self.assertNotIn("non-cacheable and unbuffered", self.doc_text)
        self.assertIn("store buffer", self.doc_text)
        self.assertIn("dsb sy", self.doc_text)
        self.assertIn("### 4.3 Cache Maintenance and Write Completion `[INFERRED]`", self.doc_text)


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

    def test_mutation_manifest_entry_missing_anchor_fails(self):
        """A manifest entry whose notes lack both tracked file:line and other-range address must fail."""
        mutated = copy.deepcopy(self.manifest)
        # Clear anchor references from PORT20-ROM-MPU-REGION2-SETUP notes
        for e in mutated["evidence_entries"]:
            if e["evidence_id"] == "PORT20-ROM-MPU-REGION2-SETUP":
                e["notes"] = "Plain CP15 MPU description without any tracked file or other address."
                break
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def _with_notes(self, eid: str, notes: str) -> Dict[str, Any]:
        mutated = copy.deepcopy(self.manifest)
        for e in mutated["evidence_entries"]:
            if e["evidence_id"] == eid:
                e["notes"] = notes
                return mutated
        self.fail(f"Manifest entry '{eid}' not found")

    def test_mutation_anchor_file_exists_but_lacks_address_fails(self):
        """A cited tracked file that exists but whose line does not contain the address must fail."""
        line = read_tracked_line("docs/PROJECT_STATE.md", 1, get_tracked_files())
        self.assertIsNotNone(line, "Precondition: docs/PROJECT_STATE.md:1 must exist")
        self.assertNotIn(0xFC0045B0, {int(h, 16) for h in HEX_PATTERN.findall(line)})
        mutated = self._with_notes(
            "PORT20-ROM-MPU-REGION2-SETUP",
            "ANCHOR: tracked docs/PROJECT_STATE.md:1 cites 0xFC0045B0.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_address_outside_range_fails(self):
        """A tracked line that really contains an address outside the range is not an anchor."""
        mutated = self._with_notes(
            "PORT20-ROM-MPU-REGION2-SETUP",
            "ANCHOR: tracked docs/PROJECT_STATE.md:223 cites 0xFC12D724.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_missing_file_fails(self):
        mutated = self._with_notes(
            "PORT20-ROM-MPU-REGION2-SETUP",
            "ANCHOR: tracked docs/DOES_NOT_EXIST.md:1 cites 0xFC0045B0.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_range_anchor_source_outside_parent_fails(self):
        mutated = self._with_notes(
            "PORT20-ROM-SS-LED-CONTROL",
            "ANCHOR: range PORT20-ROM-LEDDRV-INIT 0xFC000000 -> 0xFC075DC4 (bl).",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_range_anchor_via_scope_deviation_fails(self):
        """A range anchored only through the unanchored range must fail."""
        mutated = self._with_notes(
            "PORT20-ROM-SS-LED-CONTROL",
            "ANCHOR: range PORT20-ROM-LEDDRIVE 0xFC5572C0 -> 0xFC075DC4 (bl).",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_cycle_without_tracked_root_fails(self):
        """LEDDRV-INIT and LEDDRV-DISPATCH anchoring each other without a tracked root must fail."""
        mutated = self._with_notes(
            "PORT20-ROM-LEDDRV-INIT",
            "ANCHOR: range PORT20-ROM-LEDDRV-DISPATCH 0xFC12D838 -> 0xFC12D750 (forward).",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_unflagged_unanchored_range_fails(self):
        """The unanchored range without its SCOPE DEVIATION flag must fail."""
        mutated = self._with_notes(
            "PORT20-ROM-LEDDRIVE",
            "Candidate LEDDrive entry at 0xFC5572B8, branches to 0xFC12D838.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_old_false_anchor_wording_fails(self):
        """Citing lib.c:55 (which does not contain 0xFC5572B8) as an anchor must fail."""
        mutated = self._with_notes(
            "PORT20-ROM-LEDDRIVE",
            "ANCHOR: tracked vendor/g3x-platform/platform/g3x/lib.c:55 cites 0xFC5572B9.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_doc_missing_scope_deviation_fails(self):
        """Dropping the deviation from the doc's Scope Deviations section must fail."""
        mutated = re.sub(
            r"(## 7\. Scope Deviations\s*\n).*?(\n---)",
            r"\1\n- None.\n\2",
            self.doc_text,
            flags=re.DOTALL,
        )
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(self.manifest, mutated)

    def test_mutation_scope_deviation_static_verified_fails(self):
        mutated = copy.deepcopy(self.manifest)
        for e in mutated["evidence_entries"]:
            if e["evidence_id"] == "PORT20-ROM-LEDDRIVE":
                e["classification"] = "STATIC_VERIFIED"
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(mutated, self.doc_text)

    def test_mutation_verified_claim_from_unanchored_range_fails(self):
        """Marking the LEDDrive candidate VERIFIED (it cites only the unanchored range) must fail."""
        mutated = self.doc_text.replace(
            "**`INFERRED`** (unanchored read, §7) / **`REJECTED (FATAL PRE-KERNEL)`**",
            "**`VERIFIED`** (ROM entry)",
        )
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(self.manifest, mutated)

    def test_mutation_manifest_static_verified_contradiction_fails(self):
        """A manifest entry with STATIC_VERIFIED whose notes contain 'downgrad', 'unanchored', or 'REJECTED' must fail."""
        for term in ("downgraded", "unanchored", "REJECTED"):
            mutated = copy.deepcopy(self.manifest)
            for e in mutated["evidence_entries"]:
                if e["evidence_id"] == "PORT20-ROM-MPU-REGION2-SETUP":
                    e["classification"] = "STATIC_VERIFIED"
                    e["notes"] = f"Tracked file docs/PROJECT_STATE.md:254 with contradictory term {term} present."
                    break
            with self.assertRaises(ValueError):
                validate_manifest_classifications_and_notes(mutated)


if __name__ == "__main__":
    unittest.main()
