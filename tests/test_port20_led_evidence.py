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
   - The only range allowed without an anchor is the one covered by Tech Lead exception
     TL-EXC-P20-T1-01 (ACKNOWLEDGED_DEVIATIONS, keyed on the exception ID and the exact range
     bounds). Its notes must carry the exception ID and the 'ANCHOR: NONE' / 'SCOPE DEVIATION' /
     'quarantined' markers. Any other unanchored range fails.
   - No manifest entry has classification STATIC_VERIFIED while notes contain 'downgrad', 'unanchored' or 'REJECTED'.
2. Manifest validator integration:
   - Manifest passes tools/port11c_evidence_validator.py with returncode == 0 and 0 errors.
3. Candidate LED register table consistency (docs/PORT20_LED_EVIDENCE.md §2):
   - Table parsed strictly row by row without DOTALL leakage.
   - Evidence label and status are separate columns. Every row, rejected or not, carries exactly
     one of VERIFIED / INFERRED / UNKNOWN in the label column, plus a filled citation and status.
   - A VERIFIED label needs a 'PRIMARY.BIN 0x...' citation inside an anchored range.
   - Reference-camera candidates (0xD20B0994, 0xD20B0810, 0xD20B0888) are never VERIFIED.
4. Quarantine of the excepted deviation:
   - No candidate or claim outside §7 and its §6 accounting row cites an address inside it.
   - §7.1 'Governing exceptions' lists the exception ID with the matching range, reason, scope and
     authority; §6 states the scope accounting line; nothing calls the read compliant.
5. Citations and identity:
   - Every file:line citation in the doc points to a path listed by `git ls-files` and the line exists.
   - The doc's firmware SHA-256 equals the value on docs/REPRODUCIBILITY_MANIFEST.md:62.
6. Range ancestry rows (§6), loader context (§4), conclusion line and polarity:
   - Values are named action0 / action1; ON/OFF polarity is labelled UNKNOWN.
   - No line in the doc or manifest pairs on=/off= or ON/OFF with a concrete value.
7. Negative mutation tests for each of the above.
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

# Tech Lead exceptions for unanchored reads (AUTHORITY_CITATION below), keyed on the exception
# ID and the exact range bounds. No other unanchored range is covered.
AUTHORITY_CITATION = (
    "AgentBridge decision log, milestone PORT-20-BOOT-SIGNAL, task 90, Tech Lead REQUEST_REVISION "
    "for revision 6 (after codex-reviewer review of revision 5)"
)
TRUTHFUL_RECORD = "The read happened without an anchor and is recorded truthfully rather than hidden."
# The CPU core model is UNKNOWN (tracked annotations conflict); no line naming a core may be VERIFIED.
CPU_MODEL_SOURCE = "docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6"
CORE_NAME_PATTERN = re.compile(r"\bCortex-?[ARM]\d+\b|\bARM(?:7|9|11)\w*\b", re.IGNORECASE)
ACKNOWLEDGED_DEVIATIONS = {
    "TL-EXC-P20-T1-01": {
        "evidence_id": "PORT20-ROM-LEDDRIVE",
        "start": 0xFC5572B8,
        "end": 0xFC5573B7,
    },
}
DEVIATION_MARKERS = ("ANCHOR: NONE", "SCOPE DEVIATION", "quarantined")
WAIVER_TEXT = (
    "SCOPE DEVIATION: unanchored read, waived retroactively by Tech Lead exception TL-EXC-P20-T1-01 "
    f"({AUTHORITY_CITATION}) for accounting only; quarantined: no claim in this document relies on it."
)
SCOPE_ACCOUNTING_LINE = (
    "T1 ROM-read scope: 7 ranges anchored, 1 range covered by exception TL-EXC-P20-T1-01 (PORT20-ROM-LEDDRIVE)"
)
EXPECTED_CONCLUSION = (
    "T2 GO: 0xD20B0884 action0=0x004d0002 action1=0x004c0003 (address/values VERIFIED, ON/OFF polarity UNKNOWN)"
)
T2_PROLOGUE = (
    "the prologue must alternate the two values (write action0, wait about 1 s, write action1, wait about 1 s, "
    "then write action0 and action1 once more); this gives a visible transition whichever value lights the LED, "
    "and the owner reports which phase was lit."
)
# Lines that pair on=/off= or ON/OFF with a concrete value (polarity is UNKNOWN, so none may exist).
POLARITY_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:on|off)\s*[=:]\s*`?0x[0-9A-Fa-f]"),
    re.compile(r"(?i)\b(?:on|off)[- ]values?\b"),
    re.compile(r"\b(?:ON|OFF)\b\s*[(\[]?\s*`?0x[0-9A-Fa-f]"),
    re.compile(r"0x[0-9A-Fa-f]+`?\s*[(\[]?\s*(?:=\s*)?(?:ON|OFF)\b"),
)

# Candidate table columns (§2).
COL_ADDR, COL_ACTION0, COL_ACTION1, COL_POLARITY, COL_RMW, COL_TARGET, COL_LABEL, COL_CITATION, COL_STATUS = range(9)

FIRMWARE_HASH_SOURCE = ("docs/REPRODUCIBILITY_MANIFEST.md", 62)

EVIDENCE_LABELS = ("VERIFIED", "INFERRED", "UNKNOWN")
LABEL_PATTERN = re.compile(r"\b(VERIFIED|INFERRED|UNKNOWN)\b")
REFERENCE_CANDIDATES = ("0xD20B0994", "0xD20B0810", "0xD20B0888")
ROM_CITATION_PATTERN = re.compile(r"PRIMARY\.BIN`?\s+`?(0x[0-9A-Fa-f]+)")

HEX64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
HEX64_SEARCH = re.compile(r"\b[0-9a-fA-F]{64}\b")
CONCLUSION_PATTERN = re.compile(
    r"^T2 (?:GO:\s*(0x[0-9a-fA-F]+)\s+action0=(0x[0-9a-fA-F]+)\s+action1=(0x[0-9a-fA-F]+)\s+"
    r"\(address/values\s+(VERIFIED|INFERRED|UNKNOWN),\s+ON/OFF polarity\s+(VERIFIED|INFERRED|UNKNOWN)\)|STOP:\s*.*)$"
)
# path:line citations, e.g. docs/X.md:38, vendor/.../lib.c:45-46, docs/PROJECT_STATE.md:223, 231
FILE_LINE_CITATION = re.compile(
    r"(?P<path>[A-Za-z0-9_\-.]+(?:/[A-Za-z0-9_\-.]+)+\.(?:md|c|h|S|py|json|txt)):"
    r"(?P<lines>\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)"
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


def candidate_section(doc_text: str) -> str:
    section_match = re.search(
        r"## 2\. Candidate LED Registers Table\s*\n(.*?)(?:\n---|\n##|\Z)",
        doc_text,
        re.DOTALL,
    )
    if not section_match:
        raise ValueError("Section '## 2. Candidate LED Registers Table' not found in document")
    return section_match.group(1)


def parse_candidate_table(doc_text: str) -> List[Dict[str, str]]:
    """Parses Section 2 Candidate LED Registers Table strictly row by row."""
    rows = []
    for line in candidate_section(doc_text).strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < COL_STATUS:
            continue
        # Skip header and divider rows
        if "Candidate Address" in cols[0] or cols[0].startswith(":") or cols[0].startswith("-"):
            continue

        raw_addr = cols[COL_ADDR]
        rows.append({
            "raw_address": raw_addr,
            "clean_address": clean_markdown_cell(raw_addr),
            "action0": cols[COL_ACTION0],
            "action1": cols[COL_ACTION1],
            "polarity": cols[COL_POLARITY],
            "rmw": cols[COL_RMW],
            "target": cols[COL_TARGET],
            "classification": cols[COL_LABEL],
            "citation": cols[COL_CITATION],
            "status": cols[COL_STATUS] if len(cols) > COL_STATUS else "",
            "line": line,
        })
    return rows


def cell_value(cell: str) -> int:
    """Returns the single hex value in a candidate value cell."""
    values = HEX_PATTERN.findall(cell)
    if len(values) != 1:
        raise ValueError(f"Value cell must hold exactly one hex value, got {values}: '{cell}'")
    return int(values[0], 16)


def parse_anchor_table(doc_text: str) -> List[Dict[str, str]]:
    """Parses Section 6 Range Ancestry & Anchors Table strictly row by row."""
    section_match = re.search(
        r"## 6\. ROM Range Ancestry & Evidence Manifest Accounting\s*\n(.*?)(?:\n---|\n##|\Z)",
        doc_text,
        re.DOTALL,
    )
    if not section_match:
        raise ValueError("Section '## 6. ROM Range Ancestry...' not found in document")

    rows = []
    for line in section_match.group(1).strip().splitlines():
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


def get_tracked_files() -> set[str]:
    """Returns set of relative paths tracked by git in this repository (raises if git fails)."""
    out = subprocess.check_output(["git", "ls-files"], cwd=str(REPO_ROOT), text=True)
    return set(out.splitlines())


TRACKED_ANCHOR_PATTERN = re.compile(
    r"ANCHOR: tracked (?P<path>[A-Za-z0-9_\-./]+):(?P<line>\d+) cites "
    r"(?P<a>0x[0-9A-Fa-f]+)(?:\.\.(?P<b>0x[0-9A-Fa-f]+))?"
)
RANGE_ANCHOR_PATTERN = re.compile(
    r"ANCHOR: range (?P<parent>PORT20-[A-Z0-9\-]+) (?P<src>0x[0-9A-Fa-f]+) -> (?P<dst>0x[0-9A-Fa-f]+)"
)
HEX_PATTERN = re.compile(r"0x[0-9A-Fa-f]+")


def read_tracked_line(rel_path: str, line_no: int, tracked_files: set[str]) -> str | None:
    """Returns the content of a 1-indexed line of a tracked repository file, or None."""
    if rel_path not in tracked_files:
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


def exception_for_range(eid: str, start: int, end: int) -> str | None:
    """Returns the Tech Lead exception ID covering exactly this range, or None."""
    for exc_id, exc in ACKNOWLEDGED_DEVIATIONS.items():
        if exc["evidence_id"] == eid and exc["start"] == start and exc["end"] == end:
            return exc_id
    return None


def validate_manifest_entry_anchors(manifest: Dict[str, Any], tracked_files: set[str] | None = None) -> List[str]:
    """Verifies the provenance of every manifest range and returns the acknowledged deviations.

    Each entry's notes must carry structured anchors:
    - 'ANCHOR: tracked <path>:<line> cites <addr>[..<addr>]': the tracked line content must
      contain the cited address(es) and they must point at this range (see tracked_anchor_is_valid);
    - 'ANCHOR: range <ID> <src> -> <dst>': <ID> is another recorded range containing <src>,
      and <dst> (Thumb bit ignored) lies inside this range.
    Every range must reach a tracked root through valid parent links (no cycles).
    A range that does not is accepted only if an ACKNOWLEDGED_DEVIATIONS exception names it with
    the exact same start/end bounds, its notes carry that exception ID and the DEVIATION_MARKERS,
    and it claims no anchor."""
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
        exc_id = exception_for_range(eid, *spans[eid])
        if exc_id is None:
            raise ValueError(
                f"Manifest entry '{eid}' has no valid anchor chain to a tracked file:line "
                f"(claimed anchors: {claimed_any[eid]}) and no Tech Lead exception covers its exact range"
            )
        if not flagged:
            raise ValueError(f"Excepted deviation '{eid}' is not flagged {' / '.join(DEVIATION_MARKERS)}")
        if exc_id not in notes:
            raise ValueError(f"Excepted deviation '{eid}' does not cite its exception ID {exc_id}")
        if claimed_any[eid]:
            raise ValueError(f"Manifest entry '{eid}' is flagged as a scope deviation but still claims anchors")
        deviations.append(eid)
    return deviations


def anchored_spans(manifest: Dict[str, Any]) -> List[tuple]:
    deviations = set(validate_manifest_entry_anchors(manifest))
    return [
        (int(e["start_address"], 16), int(e["end_address"], 16), e["evidence_id"])
        for e in manifest["evidence_entries"]
        if e["evidence_id"] not in deviations
    ]


def validate_candidate_table_rows(doc_text: str, manifest: Dict[str, Any] | None = None) -> None:
    """Strictly validates candidate table rows: label and status are separate fields; every row
    carries exactly one evidence label; VERIFIED needs a ROM citation inside an anchored range."""
    if manifest is None:
        manifest = parse_manifest(MANIFEST_PATH)
    spans = anchored_spans(manifest)
    rows = parse_candidate_table(doc_text)
    if not rows:
        raise ValueError("Candidate table has no valid data rows")

    expected_candidates = {"0xD20B0884", "0xD20B0994", "0xD20B0810", "0xD20B0888", "LEDDrv.c"}
    found_candidates = set()

    for r in rows:
        clean_addr = r["clean_address"]
        for ec in expected_candidates:
            if ec in clean_addr:
                found_candidates.add(ec)

        labels = LABEL_PATTERN.findall(r["classification"])
        if len(labels) != 1:
            raise ValueError(
                f"Candidate '{clean_addr}' must carry exactly one of {EVIDENCE_LABELS} in its label column, "
                f"got {labels}: '{r['classification']}'"
            )
        if "REJECTED" in r["classification"]:
            raise ValueError(f"Candidate '{clean_addr}' mixes status into the evidence label column")
        if not r["status"]:
            raise ValueError(f"Candidate '{clean_addr}' lacks a status")
        if not r["citation"] or r["citation"] == "N/A":
            raise ValueError(f"Candidate row for '{clean_addr}' lacks citation")

        if labels[0] == "VERIFIED":
            rom_addrs = [int(h, 16) for h in ROM_CITATION_PATTERN.findall(r["citation"])]
            if not any(s <= a <= e for a in rom_addrs for s, e, _ in spans):
                raise ValueError(
                    f"Candidate '{clean_addr}' is VERIFIED without a GM1.10C ROM citation inside an anchored range"
                )
            if any(ref in clean_addr for ref in REFERENCE_CANDIDATES):
                raise ValueError(f"Reference-camera candidate '{clean_addr}' must not be VERIFIED")

    missing = expected_candidates - found_candidates
    if missing:
        raise ValueError(f"Missing expected candidate entries in candidate table: {missing}")


def primary_polarity_label(row: Dict[str, str]) -> str:
    m = re.search(r"polarity\s*`?\[(VERIFIED|INFERRED|UNKNOWN)", row["polarity"])
    if not m:
        raise ValueError("Primary candidate polarity cell does not label the polarity")
    return m.group(1)


def validate_no_polarity_value_pairs(text: str, source: str = "doc") -> None:
    """Fails if any line pairs on=/off= or ON/OFF with a concrete value."""
    for n, line in enumerate(text.splitlines(), start=1):
        for pattern in POLARITY_VALUE_PATTERNS:
            if pattern.search(line):
                raise ValueError(f"{source} line {n} pairs ON/OFF with a value: '{line.strip()[:120]}'")


def validate_polarity_consistency(doc_text: str) -> None:
    """Verifies that the candidate table and final conclusion agree on the action0/action1 values,
    that ON/OFF polarity is UNKNOWN in both, and that no line names a value ON or OFF."""
    validate_no_polarity_value_pairs(doc_text)
    rows = parse_candidate_table(doc_text)
    primary_row = next((r for r in rows if "0xD20B0884" in r["clean_address"]), None)
    if not primary_row:
        raise ValueError("Primary candidate 0xD20B0884 not found in candidate table")

    table_action0 = cell_value(primary_row["action0"])
    table_action1 = cell_value(primary_row["action1"])
    for name in ("action0", "action1"):
        if LABEL_PATTERN.findall(primary_row[name]) != ["VERIFIED"]:
            raise ValueError(f"Primary candidate {name} value must be labelled VERIFIED")
    if primary_polarity_label(primary_row) != "UNKNOWN":
        raise ValueError("Primary candidate ON/OFF polarity must be labelled UNKNOWN")

    lines = [line.strip() for line in doc_text.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("Document is empty")
    last_line = lines[-1]

    match = CONCLUSION_PATTERN.match(last_line)
    if not match:
        raise ValueError(f"Final line '{last_line}' does not match conclusion pattern")

    if last_line.startswith("T2 GO:"):
        if match.group(1) != "0xD20B0884":
            raise ValueError(f"Conclusion register {match.group(1)} does not match 0xD20B0884")
        if int(match.group(2), 16) != table_action0:
            raise ValueError(f"Conclusion action0 {match.group(2)} disagrees with candidate table {hex(table_action0)}")
        if int(match.group(3), 16) != table_action1:
            raise ValueError(f"Conclusion action1 {match.group(3)} disagrees with candidate table {hex(table_action1)}")
        if match.group(4) != "VERIFIED":
            raise ValueError(f"Conclusion address/values status must be VERIFIED, got {match.group(4)}")
        if match.group(5) != primary_polarity_label(primary_row):
            raise ValueError(
                f"Conclusion polarity {match.group(5)} disagrees with the candidate table polarity label"
            )
        if last_line != EXPECTED_CONCLUSION:
            raise ValueError(f"Conclusion line differs from the required wording: '{last_line}'")
        conclusion = doc_text.split("## 8. Conclusion", 1)[-1]
        if T2_PROLOGUE not in conclusion:
            raise ValueError("Conclusion lacks the T2 prologue sequence that alternates action0 and action1")


def validate_manifest_anchors_in_doc(manifest: Dict[str, Any], doc_text: str) -> None:
    """Ensures every manifest range has an explicit, valid anchor row in Section 6."""
    anchor_dict = {r["range_id"]: r for r in parse_anchor_table(doc_text)}

    for entry in manifest.get("evidence_entries", []):
        eid = entry["evidence_id"]
        if eid not in anchor_dict:
            raise ValueError(f"Manifest entry '{eid}' is missing an anchor row in Section 6 table")
        row = anchor_dict[eid]
        if int(row["start"], 16) != int(entry["start_address"], 16):
            raise ValueError(f"Anchor row start {row['start']} does not match manifest {entry['start_address']} for {eid}")
        if int(row["end"], 16) != int(entry["end_address"], 16):
            raise ValueError(f"Anchor row end {row['end']} does not match manifest {entry['end_address']} for {eid}")
        if row["sha256"].lower() != entry["sha256"].lower():
            raise ValueError(f"Anchor row SHA-256 does not match manifest for {eid}")
        if not row["anchor"]:
            raise ValueError(f"Anchor citation is empty for {eid}")
        if not row["anchor_type"]:
            raise ValueError(f"Anchor type is empty for {eid}")


def parse_scope_deviations_section(doc_text: str) -> str | None:
    match = re.search(r"## \d+\. Scope Deviations\s*\n(.*?)(?:\n---|\n## |\Z)", doc_text, re.DOTALL)
    return match.group(1) if match else None


def parse_governing_exceptions(doc_text: str) -> List[Dict[str, str]]:
    """Parses the 'Governing exceptions' subsection table of §7."""
    match = re.search(r"### [\d.]*\s*Governing exceptions\s*\n(.*?)(?:\n---|\n##|\Z)", doc_text, re.DOTALL)
    if not match:
        raise ValueError("Doc lacks the 'Governing exceptions' subsection")
    rows = []
    for line in match.group(1).strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 5 or "Exception ID" in cols[0] or cols[0].startswith("-"):
            continue
        rows.append({
            "exception_id": clean_markdown_cell(cols[0]),
            "range": cols[1],
            "reason": cols[2],
            "scope": cols[3],
            "authority": cols[4],
        })
    return rows


def validate_governing_exceptions(manifest: Dict[str, Any], doc_text: str) -> None:
    """Every excepted deviation needs a Governing exceptions row whose ID and range bounds match
    ACKNOWLEDGED_DEVIATIONS and the manifest, with reason, scope and authority. The table may not
    list exceptions that are not in ACKNOWLEDGED_DEVIATIONS."""
    deviations = validate_manifest_entry_anchors(manifest)
    entries = {e["evidence_id"]: e for e in manifest["evidence_entries"]}
    rows = {r["exception_id"]: r for r in parse_governing_exceptions(doc_text)}
    unknown = set(rows) - set(ACKNOWLEDGED_DEVIATIONS)
    if unknown:
        raise ValueError(f"Governing exceptions lists IDs not granted by the Tech Lead: {sorted(unknown)}")
    for eid in deviations:
        entry = entries[eid]
        start, end = int(entry["start_address"], 16), int(entry["end_address"], 16)
        exc_id = exception_for_range(eid, start, end)
        row = rows.get(exc_id)
        if row is None:
            raise ValueError(f"Governing exceptions lacks an entry for {exc_id} ({eid})")
        bounds = re.search(r"(0x[0-9A-Fa-f]+)\.\.(0x[0-9A-Fa-f]+)", row["range"])
        if eid not in row["range"] or not bounds or (int(bounds.group(1), 16), int(bounds.group(2), 16)) != (start, end):
            raise ValueError(f"Governing exceptions entry {exc_id} does not match range {eid} {hex(start)}..{hex(end)}")
        reason = row["reason"].lower()
        for term in ("already happened", "within", "quarantined"):
            if term not in reason:
                raise ValueError(f"Governing exceptions entry {exc_id} reason lacks '{term}'")
        if "this range only" not in row["scope"].lower():
            raise ValueError(f"Governing exceptions entry {exc_id} scope is not limited to this range")
        if "Tech Lead decides" not in row["authority"] or "harter" not in row["authority"]:
            raise ValueError(f"Governing exceptions entry {exc_id} lacks the charter authority")
        if AUTHORITY_CITATION not in row["authority"]:
            raise ValueError(f"Governing exceptions entry {exc_id} lacks the decision-log authority citation")
        if TRUTHFUL_RECORD not in row["authority"]:
            raise ValueError(f"Governing exceptions entry {exc_id} lacks the truthful-record sentence")


def validate_cpu_model_not_verified(doc_text: str) -> None:
    """The CPU core model is UNKNOWN (docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6). No line that names a
    specific core may carry a VERIFIED label, and the doc must state the core model as UNKNOWN."""
    for line in doc_text.splitlines():
        if CORE_NAME_PATTERN.search(line) and "VERIFIED" in line:
            raise ValueError(f"Line names a specific CPU core and carries VERIFIED: {line.strip()[:120]}")
    if f"CPU core model: `[UNKNOWN: {CPU_MODEL_SOURCE}]`" not in doc_text:
        raise ValueError(f"Doc does not label the CPU core model UNKNOWN citing {CPU_MODEL_SOURCE}")


def validate_scope_deviations_disclosed(manifest: Dict[str, Any], doc_text: str) -> None:
    """Every excepted deviation must be listed in the doc's Scope Deviations section with the
    waiver text, have a Governing exceptions entry, be marked SCOPE DEVIATION in the Section 6
    table and never be STATIC_VERIFIED. The doc must use the scope accounting line and never call
    the T1 ROM reads compliant."""
    deviations = validate_manifest_entry_anchors(manifest)
    if SCOPE_ACCOUNTING_LINE not in doc_text:
        raise ValueError("Doc lacks the T1 ROM-read scope accounting line")
    if "compliant" in doc_text.lower():
        raise ValueError("Doc calls the T1 ROM-read scope compliant")
    if not deviations:
        return
    validate_governing_exceptions(manifest, doc_text)
    section = parse_scope_deviations_section(doc_text)
    if section is None:
        raise ValueError(f"Manifest has scope deviations {deviations} but the doc has no 'Scope Deviations' section")
    if "does not depend on this range" not in section:
        raise ValueError("Scope Deviations section does not state whether the T2 conclusion depends on the range")

    entries = {e["evidence_id"]: e for e in manifest["evidence_entries"]}
    anchor_rows = {r["range_id"]: r for r in parse_anchor_table(doc_text)}
    for eid in deviations:
        entry = entries[eid]
        if eid not in section:
            raise ValueError(f"Scope deviation '{eid}' is not listed in the doc's Scope Deviations section")
        if WAIVER_TEXT not in section:
            raise ValueError(f"Scope deviation '{eid}' lacks the exception waiver text in the doc")
        if entry.get("classification") == "STATIC_VERIFIED":
            raise ValueError(f"Scope deviation '{eid}' must not be classified STATIC_VERIFIED")
        row = anchor_rows.get(eid)
        if row is None or "SCOPE DEVIATION" not in row["anchor_type"]:
            raise ValueError(f"Section 6 anchor row for '{eid}' is not marked SCOPE DEVIATION")
        if "quarantined" not in row["claims"].lower():
            raise ValueError(f"Section 6 row for '{eid}' must support no claims (quarantined)")


def validate_quarantine(manifest: Dict[str, Any], doc_text: str) -> None:
    """No candidate or claim may cite an address inside a quarantined range. Only the §7 section
    and the deviation's own §6 accounting row may mention its addresses."""
    deviations = validate_manifest_entry_anchors(manifest)
    entries = {e["evidence_id"]: e for e in manifest["evidence_entries"]}
    text = doc_text
    section = parse_scope_deviations_section(text)
    if section:
        text = text.replace(section, "")
    for row in parse_anchor_table(doc_text):
        if row["range_id"] in deviations:
            text = text.replace(row["line"], "")
    for eid in deviations:
        start = int(entries[eid]["start_address"], 16)
        end = int(entries[eid]["end_address"], 16)
        for h in HEX_PATTERN.findall(text):
            if start <= int(h, 16) <= end:
                raise ValueError(f"Doc cites {h} inside quarantined range '{eid}'")


def iter_file_line_citations(doc_text: str):
    for m in FILE_LINE_CITATION.finditer(doc_text):
        for part in m.group("lines").split(","):
            for n in part.strip().split("-"):
                yield m.group("path"), int(n)


def validate_file_line_citations(doc_text: str, tracked_files: set[str] | None = None) -> int:
    """Every path:line citation must point to a `git ls-files` path whose line exists."""
    if tracked_files is None:
        tracked_files = get_tracked_files()
    count = 0
    for path, line_no in iter_file_line_citations(doc_text):
        if path not in tracked_files:
            raise ValueError(f"Citation '{path}:{line_no}' points to a path not listed by git ls-files")
        if read_tracked_line(path, line_no, tracked_files) is None:
            raise ValueError(f"Citation '{path}:{line_no}' points to a line that does not exist")
        count += 1
    return count


def validate_firmware_identity(doc_text: str) -> None:
    """The doc's firmware SHA-256 must equal the value on docs/REPRODUCIBILITY_MANIFEST.md:62."""
    target = next((l for l in doc_text.splitlines() if l.startswith("**Firmware Target**")), None)
    if target is None:
        raise ValueError("Doc lacks the Firmware Target line")
    doc_hashes = HEX64_SEARCH.findall(target)
    if len(doc_hashes) != 1:
        raise ValueError(f"Firmware Target line must carry exactly one full SHA-256, got {doc_hashes}")
    path, line_no = FIRMWARE_HASH_SOURCE
    if f"{path}:{line_no}" not in target:
        raise ValueError("Firmware Target line does not cite the tracked hash source")
    line = read_tracked_line(path, line_no, get_tracked_files())
    if line is None:
        raise ValueError(f"Tracked hash source {path}:{line_no} not found")
    tracked = HEX64_SEARCH.findall(line)
    if len(tracked) != 1 or tracked[0].lower() != doc_hashes[0].lower():
        raise ValueError(f"Doc firmware SHA-256 {doc_hashes[0]} does not match {path}:{line_no} {tracked}")


def validate_manifest_classifications_and_notes(manifest: Dict[str, Any]) -> None:
    """Verifies that no entry has classification STATIC_VERIFIED while its notes
    contain 'downgrad', 'unanchored' or 'REJECTED'."""
    forbidden_terms = ("downgrad", "unanchored", "rejected")
    for entry in manifest.get("evidence_entries", []):
        eid = entry.get("evidence_id", "<unknown>")
        if entry.get("classification", "") == "STATIC_VERIFIED":
            notes_lower = entry.get("notes", "").lower()
            for term in forbidden_terms:
                if term in notes_lower:
                    raise ValueError(
                        f"Manifest entry '{eid}' has classification STATIC_VERIFIED "
                        f"but its notes contain contradictory term '{term}'"
                    )


def mutate_candidate_cell(doc_text: str, address: str, col: int, value: str) -> str:
    """Returns doc_text with one cell of the candidate row for `address` replaced."""
    section = candidate_section(doc_text)
    for line in section.splitlines():
        if line.startswith(f"| **`{address}") or line.startswith(f"| **{address}"):
            cols = line.split("|")
            cols[col + 1] = f" {value} "  # +1: leading empty split before the first '|'
            return doc_text.replace(line, "|".join(cols))
    raise AssertionError(f"Candidate row '{address}' not found")


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
        self.assertLessEqual(len(approved_ranges), MAX_RANGES_LIMIT)
        self.assertLessEqual(len(evidence_entries), MAX_RANGES_LIMIT)
        self.assertEqual(len(approved_ranges), len(evidence_entries), "Approved ranges and evidence entries counts mismatch")

    def test_each_range_byte_count_within_limit(self):
        for entry in self.manifest.get("evidence_entries", []):
            eid = entry.get("evidence_id", "UNKNOWN")
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            byte_count = entry.get("expected_byte_count", 0)
            self.assertGreater(end, start, f"[{eid}] Inverted range")
            self.assertEqual(byte_count, end - start + 1, f"[{eid}] Byte count mismatch")
            self.assertLessEqual(byte_count, MAX_BYTES_PER_RANGE, f"[{eid}] exceeds per-range limit")

    def test_total_byte_count_within_limit(self):
        total_bytes = sum(e.get("expected_byte_count", 0) for e in self.manifest.get("evidence_entries", []))
        self.assertLessEqual(total_bytes, MAX_TOTAL_BYTES)

    def test_sha256_format(self):
        for entry in self.manifest.get("evidence_entries", []):
            self.assertTrue(HEX64_PATTERN.match(entry.get("sha256", "")), f"[{entry.get('evidence_id')}] bad SHA-256")

    def test_spatial_disjointness_of_slices(self):
        spans = sorted(
            (int(e["start_address"], 16), int(e["end_address"], 16), e["evidence_id"])
            for e in self.manifest.get("evidence_entries", [])
        )
        for (cs, ce, cid), (ns, ne, nid) in zip(spans, spans[1:]):
            self.assertLess(ce, ns, f"Slices '{cid}' and '{nid}' overlap")

    def test_validator_execution_passes(self):
        """Executes tools/port11c_evidence_validator.py on the manifest."""
        self.assertTrue(VALIDATOR_TOOL.exists(), f"Validator tool missing: {VALIDATOR_TOOL}")
        cmd = [sys.executable, str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"validator failed (exit {res.returncode}):\n{res.stdout}\n{res.stderr}")
        self.assertIn("Result: VALID", res.stdout)
        self.assertIn("0 errors", res.stdout)

    def test_manifest_entries_have_valid_anchors(self):
        """Every range reaches a tracked root, except the single allowlisted deviation."""
        deviations = validate_manifest_entry_anchors(self.manifest)
        self.assertEqual(deviations, ["PORT20-ROM-LEDDRIVE"])
        for eid in GO_CHAIN_RANGES:
            self.assertNotIn(eid, deviations, f"T2 conclusion range '{eid}' is not anchored")

    def test_deviation_manifest_notes_carry_exception(self):
        entry = next(e for e in self.manifest["evidence_entries"] if e["evidence_id"] == "PORT20-ROM-LEDDRIVE")
        exc = ACKNOWLEDGED_DEVIATIONS["TL-EXC-P20-T1-01"]
        self.assertEqual(int(entry["start_address"], 16), exc["start"])
        self.assertEqual(int(entry["end_address"], 16), exc["end"])
        self.assertIn("TL-EXC-P20-T1-01", entry["notes"])
        self.assertIn(WAIVER_TEXT, entry["notes"])
        self.assertIn(AUTHORITY_CITATION, entry["notes"])
        self.assertIn(TRUTHFUL_RECORD, entry["notes"])
        self.assertNotIn("revision-5 feedback", entry["notes"])
        self.assertIn(SCOPE_ACCOUNTING_LINE, entry["notes"])
        self.assertNotIn("compliant", entry["notes"].lower())
        self.assertNotIn("revision-4", entry["notes"])
        self.assertNotIn("LEDDrive", entry["notes"])
        self.assertNotIn("r1 < 8", entry["notes"])
        self.assertNotIn("0xFC12D838", entry["notes"])

    def test_manifest_static_verified_classification_notes_agreement(self):
        validate_manifest_classifications_and_notes(self.manifest)

    def test_manifest_notes_name_no_on_off_values(self):
        for entry in self.manifest["evidence_entries"]:
            validate_no_polarity_value_pairs(entry.get("notes", ""), entry["evidence_id"])


class TestPort20DocEvidenceConsistency(unittest.TestCase):
    """Verifies that docs/PORT20_LED_EVIDENCE.md fulfills all deliverable requirements."""

    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Evidence doc missing: {DOC_PATH}")
        self.doc_text = parse_doc(DOC_PATH)
        self.manifest = parse_manifest(MANIFEST_PATH)

    def test_candidate_registers_table_present(self):
        self.assertIn("## 2. Candidate LED Registers Table", self.doc_text)
        for h in (
            "Candidate Address",
            "Action-0 Value",
            "Action-1 Value",
            "ON/OFF Polarity",
            "RMW Mask",
            "Target Hardware LED",
            "Evidence Label",
            "Tracked Citation / Primary Disassembly",
            "Status",
        ):
            self.assertIn(h, self.doc_text, f"Table missing required header: {h}")
        self.assertNotIn("ON Value", self.doc_text)
        self.assertNotIn("OFF Value", self.doc_text)

    def test_candidate_rows_strictly_validated(self):
        validate_candidate_table_rows(self.doc_text, self.manifest)

    def test_verified_candidate_register_identified(self):
        """0xD20B0884 must be identified with VERIFIED action0/action1 values and UNKNOWN polarity."""
        primary_row = next((r for r in parse_candidate_table(self.doc_text) if "0xD20B0884" in r["clean_address"]), None)
        self.assertIsNotNone(primary_row, "0xD20B0884 missing from candidate table")
        self.assertEqual(cell_value(primary_row["action0"]), 0x4D0002)
        self.assertEqual(cell_value(primary_row["action1"]), 0x4C0003)
        self.assertEqual(LABEL_PATTERN.findall(primary_row["action0"]), ["VERIFIED"])
        self.assertEqual(LABEL_PATTERN.findall(primary_row["action1"]), ["VERIFIED"])
        self.assertEqual(LABEL_PATTERN.findall(primary_row["classification"]), ["VERIFIED"])
        self.assertIn("INFERRED", primary_row["target"])  # physical location
        self.assertEqual(primary_polarity_label(primary_row), "UNKNOWN")
        self.assertIn("polarity `[UNKNOWN]`", primary_row["polarity"])
        self.assertIn("PRIMARY.BIN", primary_row["citation"])

    def test_conclusion_line_exact(self):
        lines = [l.strip() for l in self.doc_text.strip().splitlines() if l.strip()]
        self.assertEqual(lines[-1], EXPECTED_CONCLUSION)
        self.assertIn("action0=", lines[-1])
        self.assertIn("action1=", lines[-1])
        self.assertIn("polarity UNKNOWN", lines[-1])
        self.assertIn(T2_PROLOGUE, self.doc_text)

    def test_doc_names_no_on_off_values(self):
        validate_no_polarity_value_pairs(self.doc_text)

    def test_governing_exceptions_present(self):
        validate_governing_exceptions(self.manifest, self.doc_text)
        self.assertNotIn("revision-4 feedback", self.doc_text)
        self.assertNotIn("acknowledged deviation", self.doc_text)

    def test_manifest_anchors_present_in_doc(self):
        validate_manifest_anchors_in_doc(self.manifest, self.doc_text)

    def test_gm110c_rom_citations_and_disassembly_present(self):
        for c in (
            "0xFC075DC4", "0xFC075D98", "0xFC075DAE", "0xFC0D73C4",
            "0xFC0D73E4", "0xFC075E00", "0xFC075E04",
        ):
            self.assertIn(c, self.doc_text, f"Missing critical ROM citation: {c}")
        self.assertIn("str.w   r1, [r0, #2048]", self.doc_text)
        self.assertIn("add.w   r0, r2, r0, lsl #2", self.doc_text)

    def test_loader_context_requirements_addressed(self):
        for s in (
            "4. Loader Context Writability Analysis", "CPU Execution Mode", "Privileged",
            "MPU Memory Region Protection", "Region 2", "DRACR", "Cache Maintenance",
            "Device Memory", "Non-cacheable",
        ):
            self.assertIn(s, self.doc_text)

    def test_conclusion_polarity_consistency(self):
        validate_polarity_consistency(self.doc_text)

    def test_scope_deviations_disclosed(self):
        validate_scope_deviations_disclosed(self.manifest, self.doc_text)

    def test_quarantined_range_not_cited(self):
        validate_quarantine(self.manifest, self.doc_text)

    def test_file_line_citations_are_tracked(self):
        self.assertGreater(validate_file_line_citations(self.doc_text), 0)
        self.assertNotIn("chdk-port/loader", self.doc_text.replace("`git ls-files chdk-port/loader`", ""))

    def test_firmware_identity_matches_tracked_hash(self):
        validate_firmware_identity(self.doc_text)
        self.assertNotIn("d8ad5039", self.doc_text)

    def test_no_false_anchor_wording_for_leddrive(self):
        self.assertNotIn("anchored by tracked platform declaration", self.doc_text)
        for entry in self.manifest["evidence_entries"]:
            if entry["evidence_id"] == "PORT20-ROM-LEDDRIVE":
                self.assertNotIn("lib.c:55", entry["notes"])
                self.assertNotIn("PORT17_TRACE_EVIDENCE.md:389", entry["notes"])

    def test_loader_state_split_and_labelled(self):
        self.assertIn("#### (1) At loader entry", self.doc_text)
        self.assertIn(
            "#### (2) After the loader's `cpsid if` (required by `chdk-port/platform/g3x/sub/110c/boot_prototype.c:95`)",
            self.doc_text,
        )
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
        self.assertNotIn("non-cacheable and unbuffered", self.doc_text)
        self.assertIn("store buffer", self.doc_text)
        self.assertIn("dsb sy", self.doc_text)
        self.assertIn("### 4.3 Cache Maintenance and Write Completion `[INFERRED]`", self.doc_text)
        self.assertIn("Regardless of core, a `DSB` after the store", self.doc_text)

    def test_cpu_model_not_verified(self):
        validate_cpu_model_not_verified(self.doc_text)
        # Store-buffer statements tied to a specific core must be conditional.
        for line in self.doc_text.splitlines():
            if "store buffer" in line and CORE_NAME_PATTERN.search(line):
                self.assertIn("if the core is", line.lower(), f"Core-specific store-buffer claim not conditional: {line[:120]}")

    def test_mpu_region2_facts_verified_from_rom_range(self):
        line = next(l for l in self.doc_text.splitlines() if l.startswith("- ROM routine `0xFC0045BE..0xFC0045D6`"))
        self.assertIn("[VERIFIED: PRIMARY.BIN 0xFC0045BE..0xFC0045D6, range PORT20-ROM-MPU-REGION2-SETUP]", line)
        for s in ("`DRBAR`: `0x80000000`", "`DRSR`: `0x3D` (2 GiB", "`DRACR`: `0x1105`", "execute never"):
            self.assertIn(s, self.doc_text)

    def test_exception_authority_and_truthful_record(self):
        section = parse_scope_deviations_section(self.doc_text)
        self.assertIsNotNone(section)
        self.assertIn(TRUTHFUL_RECORD, section)
        self.assertIn(AUTHORITY_CITATION, self.doc_text)
        self.assertNotIn("revision-5 feedback", self.doc_text)


class TestNegativeMutations(unittest.TestCase):
    """In-memory negative mutation tests verifying test enforcement robustness."""

    def setUp(self):
        self.doc_text = parse_doc(DOC_PATH)
        self.manifest = parse_manifest(MANIFEST_PATH)

    def _with_notes(self, eid: str, notes: str) -> Dict[str, Any]:
        mutated = copy.deepcopy(self.manifest)
        for e in mutated["evidence_entries"]:
            if e["evidence_id"] == eid:
                e["notes"] = notes
                return mutated
        self.fail(f"Manifest entry '{eid}' not found")

    # --- candidate labels -------------------------------------------------------------

    def test_mutation_removing_row_label_fails(self):
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0888", COL_LABEL, "")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    def test_mutation_d20b0994_rejected_alone_fails(self):
        """Reviewer mutation: the 0xD20B0994 label set to 'REJECTED' alone must fail."""
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0994", COL_LABEL, "REJECTED")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    def test_mutation_d20b0994_verified_rejected_without_rom_citation_fails(self):
        """Reviewer mutation: 'VERIFIED / REJECTED' with no ROM citation must fail."""
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0994", COL_LABEL, "VERIFIED / REJECTED")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0994", COL_LABEL, "**`VERIFIED`**")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    def test_mutation_two_labels_fails(self):
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0810", COL_LABEL, "VERIFIED / INFERRED")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    def test_mutation_rejected_ledddrv_verified_without_rom_citation_fails(self):
        """A rejected candidate labelled VERIFIED still needs an anchored ROM citation."""
        mutated = mutate_candidate_cell(self.doc_text, "LEDDrv.c", COL_CITATION, "`docs/PROJECT_STATE.md:223`")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    def test_mutation_verified_from_quarantined_range_fails(self):
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0810", COL_LABEL, "**`VERIFIED`**")
        mutated = mutate_candidate_cell(mutated, "0xD20B0810", COL_CITATION, "`PRIMARY.BIN 0xFC5572C0`")
        with self.assertRaises(ValueError):
            validate_candidate_table_rows(mutated, self.manifest)

    # --- conclusion and polarity ------------------------------------------------------

    def _with_conclusion(self, line: str) -> str:
        mutated = re.sub(r"T2 GO:.*", line, self.doc_text)
        self.assertNotEqual(mutated, self.doc_text)
        return mutated

    def test_mutation_conclusion_polarity_disagreement_fails(self):
        mutated = self._with_conclusion(
            "T2 GO: 0xD20B0884 action0=0x004c0003 action1=0x004d0002 (address/values VERIFIED, ON/OFF polarity UNKNOWN)"
        )
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_conclusion_polarity_label_upgrade_fails(self):
        mutated = self._with_conclusion(
            "T2 GO: 0xD20B0884 action0=0x004d0002 action1=0x004c0003 (address/values VERIFIED, ON/OFF polarity INFERRED)"
        )
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_table_polarity_label_upgrade_fails(self):
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0884", COL_POLARITY, "polarity `[INFERRED]`")
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_old_on_off_conclusion_fails(self):
        mutated = self._with_conclusion(
            "T2 GO: 0xD20B0884 on=0x004d0002 off=0x004c0003 (address/value VERIFIED, polarity UNKNOWN)"
        )
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_conclusion_without_prologue_fails(self):
        mutated = self.doc_text.replace(T2_PROLOGUE, "the prologue writes action0 once.")
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_polarity_consistency(mutated)

    def test_mutation_on_off_value_pairs_fail(self):
        for line in (
            "on=0x004d0002",
            "Write OFF=0x004c0003 to the register.",
            "The ON value is `0x004d0002`.",
            "| ON Value | OFF Value |",
            "ON `0x004d0002`",
            "OFF (0x004c0003)",
            "`0x004d0002` (ON)",
            "0x004c0003 = OFF",
            "off: 0x4c0003",
        ):
            with self.assertRaises(ValueError, msg=line):
                validate_no_polarity_value_pairs(self.doc_text + "\n" + line + "\n")
        for line in ("ON/OFF polarity UNKNOWN", "polarity `[UNKNOWN]` for 0x004d0002 / 0x004c0003"):
            validate_no_polarity_value_pairs(line)

    def test_mutation_manifest_notes_on_off_value_fails(self):
        notes = next(e["notes"] for e in self.manifest["evidence_entries"] if e["evidence_id"] == "PORT20-ROM-SS-LED-CONTROL")
        with self.assertRaises(ValueError):
            validate_no_polarity_value_pairs(notes + " ON value 0x4d0002.", "PORT20-ROM-SS-LED-CONTROL")

    def test_mutation_rejects_invalid_conclusion_pattern(self):
        for ic in (
            "GO: 0xD20B0884",
            "T2 GO",
            "Conclusion: T2 GO 0xD20B0884",
            "T2 PROCEED",
            "T2 GO: 0xD20B0884 (missing action0/action1)",
            "T2 GO: 0xD20B0884 on=0x004d0002 off=0x004c0003 (address/value VERIFIED, polarity UNKNOWN)",
        ):
            self.assertIsNone(CONCLUSION_PATTERN.match(ic), f"Invalid conclusion '{ic}' unexpectedly passed")

    def test_mutation_conclusion_citing_quarantined_range_fails(self):
        mutated = self.doc_text.rstrip() + " via 0xFC5572B9\n"
        with self.assertRaises(ValueError):
            validate_quarantine(self.manifest, mutated)

    # --- manifest anchors and deviations ----------------------------------------------

    def test_mutation_missing_anchor_row_fails(self):
        mutated = re.sub(r"\|\s*`PORT20-ROM-TASK-LEDCON-LOOP`\s*\|[^\n]*\n", "", self.doc_text)
        with self.assertRaises(ValueError):
            validate_manifest_anchors_in_doc(self.manifest, mutated)

    def test_mutation_rejects_exceeded_range_limit(self):
        mutated = copy.deepcopy(self.manifest)
        mutated["evidence_entries"].append(copy.deepcopy(mutated["evidence_entries"][0]))
        self.assertGreater(len(mutated["evidence_entries"]), MAX_RANGES_LIMIT)

    def test_mutation_manifest_entry_missing_anchor_fails(self):
        mutated = self._with_notes("PORT20-ROM-MPU-REGION2-SETUP", "Plain CP15 MPU description.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_second_unanchored_range_fails(self):
        """A second unanchored range fails even when flagged and citing the exception ID."""
        mutated = self._with_notes(
            "PORT20-ROM-SS-LED-CONTROL", f"ANCHOR: NONE. {WAIVER_TEXT}"
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)
        extra = copy.deepcopy(self.manifest)
        extra["evidence_entries"].append({
            "evidence_id": "PORT20-ROM-EXTRA",
            "start_address": "0xFC600000",
            "end_address": "0xFC6000FF",
            "expected_byte_count": 256,
            "sha256": "0" * 64,
            "classification": "INFERRED",
            "notes": f"ANCHOR: NONE. {WAIVER_TEXT}",
        })
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(extra)

    def test_mutation_deviation_without_acknowledgement_fails(self):
        """The excepted range must cite its exception ID; free-form wording alone is not enough."""
        mutated = self._with_notes(
            "PORT20-ROM-LEDDRIVE",
            "ANCHOR: NONE. SCOPE DEVIATION: unanchored read, waived by the Tech Lead; quarantined.",
        )
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)
        mutated = self._with_notes("PORT20-ROM-LEDDRIVE", WAIVER_TEXT.replace("TL-EXC-P20-T1-01", "TL-EXC-P20-T1-02"))
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_exception_range_bounds_mismatch_fails(self):
        """The exception covers the exact bounds only; a widened or shifted range fails."""
        for field, value in (("end_address", "0xFC5574B7"), ("start_address", "0xFC5572B0")):
            mutated = copy.deepcopy(self.manifest)
            for e in mutated["evidence_entries"]:
                if e["evidence_id"] == "PORT20-ROM-LEDDRIVE":
                    e[field] = value
            with self.assertRaises(ValueError, msg=field):
                validate_manifest_entry_anchors(mutated)

    def test_mutation_deviation_not_quarantined_fails(self):
        mutated = self._with_notes("PORT20-ROM-LEDDRIVE", "ANCHOR: NONE. SCOPE DEVIATION. TL-EXC-P20-T1-01.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_missing_governing_exceptions_fails(self):
        mutated = re.sub(r"### 7\.1 Governing exceptions\s*\n.*?(\n---)", r"\1", self.doc_text, flags=re.DOTALL)
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_governing_exceptions(self.manifest, mutated)
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(self.manifest, mutated)

    def test_mutation_governing_exception_wrong_id_or_range_fails(self):
        for old, new in (
            ("| `TL-EXC-P20-T1-01` |", "| `TL-EXC-P20-T1-99` |"),
            ("`0xFC5572B8..0xFC5573B7` (256 bytes", "`0xFC5572B8..0xFC5574B7` (512 bytes"),
            ("| This range only.", "| All unanchored ranges."),
            ("| Charter: the Tech Lead decides", "| Agent: the worker decides"),
            ("The read had already happened;", "The read was planned;"),
        ):
            self.assertIn(old, self.doc_text)
            with self.assertRaises(ValueError, msg=new):
                validate_governing_exceptions(self.manifest, self.doc_text.replace(old, new))

    def test_mutation_doc_candidate_citing_quarantined_address_fails(self):
        """A doc candidate or claim citing an address inside 0xFC5572B8..0xFC5573B7 fails."""
        mutated = mutate_candidate_cell(self.doc_text, "0xD20B0810", COL_CITATION, "`PRIMARY.BIN 0xFC5572B9` (LEDDrive)")
        with self.assertRaises(ValueError):
            validate_quarantine(self.manifest, mutated)
        mutated = self.doc_text.replace(
            "### 3.5 Step 5: Polarity Analysis & Uncertainty\n",
            "### 3.5 Step 5: Polarity Analysis & Uncertainty\n- `LEDDrive` at `0xFC5573B7` maps action 0 to lit.\n",
        )
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_quarantine(self.manifest, mutated)

    def test_mutation_anchor_file_exists_but_lacks_address_fails(self):
        line = read_tracked_line("docs/PROJECT_STATE.md", 1, get_tracked_files())
        self.assertIsNotNone(line, "Precondition: docs/PROJECT_STATE.md:1 must exist")
        self.assertNotIn(0xFC0045B0, {int(h, 16) for h in HEX_PATTERN.findall(line)})
        mutated = self._with_notes("PORT20-ROM-MPU-REGION2-SETUP", "ANCHOR: tracked docs/PROJECT_STATE.md:1 cites 0xFC0045B0.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_address_outside_range_fails(self):
        mutated = self._with_notes("PORT20-ROM-MPU-REGION2-SETUP", "ANCHOR: tracked docs/PROJECT_STATE.md:223 cites 0xFC12D724.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_missing_file_fails(self):
        mutated = self._with_notes("PORT20-ROM-MPU-REGION2-SETUP", "ANCHOR: tracked docs/DOES_NOT_EXIST.md:1 cites 0xFC0045B0.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_range_anchor_source_outside_parent_fails(self):
        mutated = self._with_notes("PORT20-ROM-SS-LED-CONTROL", "ANCHOR: range PORT20-ROM-LEDDRV-INIT 0xFC000000 -> 0xFC075DC4 (bl).")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_range_anchor_via_scope_deviation_fails(self):
        mutated = self._with_notes("PORT20-ROM-SS-LED-CONTROL", "ANCHOR: range PORT20-ROM-LEDDRIVE 0xFC5572C0 -> 0xFC075DC4 (bl).")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_anchor_cycle_without_tracked_root_fails(self):
        mutated = self._with_notes("PORT20-ROM-LEDDRV-INIT", "ANCHOR: range PORT20-ROM-LEDDRV-DISPATCH 0xFC12D838 -> 0xFC12D750 (forward).")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_unflagged_unanchored_range_fails(self):
        mutated = self._with_notes("PORT20-ROM-LEDDRIVE", "Candidate entry at 0xFC5572B8.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_old_false_anchor_wording_fails(self):
        mutated = self._with_notes("PORT20-ROM-LEDDRIVE", "ANCHOR: tracked vendor/g3x-platform/platform/g3x/lib.c:55 cites 0xFC5572B9.")
        with self.assertRaises(ValueError):
            validate_manifest_entry_anchors(mutated)

    def test_mutation_doc_missing_scope_deviation_fails(self):
        mutated = re.sub(r"(## 7\. Scope Deviations\s*\n).*?(\n---)", r"\1\n- None.\n\2", self.doc_text, flags=re.DOTALL)
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(self.manifest, mutated)

    def test_mutation_doc_calls_scope_compliant_fails(self):
        mutated = self.doc_text.replace(
            SCOPE_ACCOUNTING_LINE, "The T1 ROM-read scope is fully compliant."
        )
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(self.manifest, mutated)

    def test_mutation_scope_deviation_static_verified_fails(self):
        mutated = copy.deepcopy(self.manifest)
        for e in mutated["evidence_entries"]:
            if e["evidence_id"] == "PORT20-ROM-LEDDRIVE":
                e["classification"] = "STATIC_VERIFIED"
        with self.assertRaises(ValueError):
            validate_scope_deviations_disclosed(mutated, self.doc_text)

    def test_mutation_manifest_static_verified_contradiction_fails(self):
        for term in ("downgraded", "unanchored", "REJECTED"):
            mutated = copy.deepcopy(self.manifest)
            for e in mutated["evidence_entries"]:
                if e["evidence_id"] == "PORT20-ROM-MPU-REGION2-SETUP":
                    e["classification"] = "STATIC_VERIFIED"
                    e["notes"] = f"Tracked file docs/PROJECT_STATE.md:254 with contradictory term {term} present."
                    break
            with self.assertRaises(ValueError):
                validate_manifest_classifications_and_notes(mutated)

    # --- citations and identity -------------------------------------------------------

    def test_mutation_untracked_loader_citation_fails(self):
        mutated = self.doc_text + "\nSee `chdk-port/loader/g3x/main_prototype.c:86`.\n"
        with self.assertRaises(ValueError):
            validate_file_line_citations(mutated)

    def test_mutation_citation_line_out_of_range_fails(self):
        mutated = self.doc_text + "\nSee `vendor/g3x-platform/platform/g3x/lib.c:99999`.\n"
        with self.assertRaises(ValueError):
            validate_file_line_citations(mutated)

    def test_mutation_wrong_firmware_hash_fails(self):
        mutated = self.doc_text.replace(
            "9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578", "d8ad5039" + "0" * 56
        )
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_firmware_identity(mutated)

    def test_mutation_cpu_core_verified_fails(self):
        for claim in (
            "- DIGIC 6 uses an ARM Cortex-R4 with a PMSAv7 MPU `[VERIFIED: docs/PROJECT_STATE.md:254]`.",
            "- The CPU is a Cortex-A9 **VERIFIED**.",
            "- Core: ARM946E-S `[VERIFIED]`.",
        ):
            with self.assertRaises(ValueError):
                validate_cpu_model_not_verified(self.doc_text + "\n" + claim + "\n")

    def test_mutation_cpu_model_unknown_label_removed_fails(self):
        mutated = self.doc_text.replace(f"CPU core model: `[UNKNOWN: {CPU_MODEL_SOURCE}]`", "CPU core model: Cortex-R4")
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_cpu_model_not_verified(mutated)

    def test_mutation_governing_exception_old_authority_fails(self):
        mutated = self.doc_text.replace(f"Record: {AUTHORITY_CITATION}.", "Record: task 90 revision-5 feedback.")
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_governing_exceptions(self.manifest, mutated)

    def test_mutation_governing_exception_without_truthful_record_fails(self):
        row = next(l for l in self.doc_text.splitlines() if l.startswith("| `TL-EXC-P20-T1-01` |"))
        mutated = self.doc_text.replace(row, row.replace(TRUTHFUL_RECORD, ""))
        self.assertNotEqual(mutated, self.doc_text)
        with self.assertRaises(ValueError):
            validate_governing_exceptions(self.manifest, mutated)


if __name__ == "__main__":
    unittest.main()
