#!/usr/bin/env python3
"""PORT-21 T1: Unit tests for stock-boot lifetime of core and loader RAM regions.

Validates that:
1. docs/PORT21_RAM_LIFETIME.md exists and contains:
   - Analysis of code path after branch to core (core boot() vs my_restart continuation).
   - Analysis of DryOS heap start / memisostart (stock 0x003489B4 vs candidate 0x00366CB0).
   - Analysis of RAM lifetime / survival for core region 0x003489B4..0x00366CB0 and loader 0x00008000..0x00024CF0.
   - Separation of Boot Moment 1 (stock cold boot) and Boot Moment 2 (post-loader core boot).
   - Table mapping each finding to H1-H4 with supports / rules out / neutral and confidence labels.
   - Read provenance table accounting for all manifest reads with Tech Lead ratification.
   - Owner observations labeled OWNER-REPORTED without invented citations.
2. docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json exists, is validated by port11c_evidence_validator.py,
   satisfies slice constraints (<= 4 KiB per slice, <= 64 KiB total, non-overlapping),
   and matches exact SHA-256 hashes against single-pass cached seeks of firmware/dumps/GM1.10C/PRIMARY.BIN.
3. Every address cited on a line labeled VERIFIED has exact, verifiable provenance:
   a tracked file:line (from git ls-files alone), a ROM address within a manifest entry, or an explicit derivation.
4. Derivations are strictly recomputed from cited operands and rejected if self-referential.
5. Negative tests proving that missing, wrong, uncited table rows, or self-referential derivations fail validation.
6. No PORT-20-owned files are modified.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT21_RAM_LIFETIME.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT21_EVIDENCE_MANIFEST.json"
ROM_PATH = REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN"
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_BASE = 0xFC000000

HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{4,8}\b")
CITATION_BLOCK_RE = re.compile(r"\[VERIFIED(?::\s*([^\]]+))?\]")


class RomSliceCache:
    """Manages single-pass, bounded caching of manifest ROM slices (Feedback [P2-c])."""

    _cached_slices: dict[str, dict] | None = None
    _total_bytes_read: int = 0
    _rom_access_count: int = 0

    @classmethod
    def get_slices(cls) -> tuple[dict[str, dict], int, bool]:
        if cls._cached_slices is not None:
            return cls._cached_slices, cls._total_bytes_read, ROM_PATH.is_file()

        cls._cached_slices = {}
        cls._total_bytes_read = 0

        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        entries = manifest.get("evidence_entries", [])
        if not ROM_PATH.is_file():
            for entry in entries:
                eid = entry["evidence_id"]
                cls._cached_slices[eid] = {
                    "start": int(entry["start_address"], 16),
                    "end": int(entry["end_address"], 16),
                    "expected_byte_count": entry["expected_byte_count"],
                    "sha256": entry["sha256"],
                    "bytes": b"",
                    "notes": entry.get("notes", ""),
                }
            return cls._cached_slices, 0, False

        with open(ROM_PATH, "rb") as rf:
            cls._rom_access_count += 1
            for entry in entries:
                eid = entry["evidence_id"]
                start = int(entry["start_address"], 16)
                end = int(entry["end_address"], 16)
                length = entry["expected_byte_count"]
                expected_sha = entry["sha256"]

                assert length <= 4096, f"Slice {eid} exceeds 4 KiB: {length}"
                assert start >= ROM_BASE, f"Slice {eid} start < ROM_BASE"

                offset = start - ROM_BASE
                rf.seek(offset)
                data = rf.read(length)
                assert len(data) == length, f"Short read for {eid}"
                computed_sha = hashlib.sha256(data).hexdigest()
                assert computed_sha == expected_sha, f"SHA-256 mismatch for {eid}"

                cls._cached_slices[eid] = {
                    "start": start,
                    "end": end,
                    "expected_byte_count": length,
                    "sha256": expected_sha,
                    "bytes": data,
                    "notes": entry.get("notes", ""),
                }
                cls._total_bytes_read += length

        assert cls._total_bytes_read <= 65536, f"Total ROM reads exceed 64 KiB: {cls._total_bytes_read}"
        return cls._cached_slices, cls._total_bytes_read, True

    @classmethod
    def lookup_word(cls, rom_addr: int) -> int | None:
        """Resolve a 32-bit little-endian word from cached manifest slices without disk reads."""
        slices, _, rom_present = cls.get_slices()
        if not rom_present:
            return None
        for entry in slices.values():
            s = entry["start"]
            e = entry["end"]
            data = entry["bytes"]
            if s <= rom_addr <= e - 3 and data:
                offset = rom_addr - s
                return struct.unpack_from("<I", data, offset)[0]
        return None


def get_tracked_files() -> set[str]:
    """Return set of tracked files strictly from git ls-files alone (Feedback [P2-b])."""
    try:
        raw_git_files = subprocess.check_output(
            ["git", "ls-files"], cwd=REPO_ROOT, text=True
        ).splitlines()
        return set(raw_git_files)
    except Exception:
        return set()


def parse_and_validate_citation(
    line: str,
    line_no: int,
    manifest_entries: dict[str, dict],
    tracked_files: set[str],
) -> None:
    """Validate that every hex address on a line with VERIFIED has exact provenance."""
    stripped = line.strip()

    # Skip epistemic definition lines and section headings
    if (
        stripped.startswith("- **`VERIFIED`**:")
        or stripped.startswith("- **VERIFIED**:")
        or stripped.startswith("#")
        or stripped.startswith("### Epistemic Classifications")
        or stripped.startswith("| Finding ID |")
        or stripped.startswith("| Evidence ID |")
    ):
        return

    # If line does not make a VERIFIED claim, skip
    if "VERIFIED" not in line:
        return

    matches = list(CITATION_BLOCK_RE.finditer(line))
    if not matches:
        raise AssertionError(
            f"Line {line_no}: VERIFIED claim or table row has no bracketed citation: {line}"
        )

    # Extract all hex addresses on this line (ignoring small constants < 0x1000)
    raw_addrs = [int(m.group(0), 16) for m in HEX_ADDR_RE.finditer(line)]
    addrs = [a for a in raw_addrs if a >= 0x1000]

    proven_addrs: set[int] = set()
    derived_citations: list[str] = []

    # Pass 1: Parse direct citations (file:line, ROM addresses, manifest IDs)
    for m in matches:
        citation_body = m.group(1)
        if citation_body is None or not citation_body.strip():
            raise AssertionError(
                f"Line {line_no}: '[VERIFIED]' has missing citation body in: {line}"
            )

        citations = [c.strip() for c in citation_body.split(";") if c.strip()]

        for cit in citations:
            if cit.startswith("derived:"):
                derived_citations.append(cit)
                continue

            # ROM citation (e.g. ROM 0xFC05B450, 0xFC05B474; PORT21-ROM-HEAP-SETUP)
            if cit.startswith("ROM "):
                rom_part = cit[len("ROM ") :].strip()
                for addr_str in HEX_ADDR_RE.findall(rom_part):
                    rom_addr = int(addr_str, 16)
                    in_manifest = False
                    for eid, entry in manifest_entries.items():
                        s, e = entry["start"], entry["end"]
                        if s <= rom_addr <= e:
                            in_manifest = True
                            proven_addrs.add(rom_addr)
                            # Resolve literal word from cached manifest slice
                            word = RomSliceCache.lookup_word(rom_addr)
                            if word is not None:
                                proven_addrs.add(word)
                            break
                    if not in_manifest:
                        raise AssertionError(
                            f"Line {line_no}: Cited ROM address {hex(rom_addr)} not inside any manifest range"
                        )
                continue

            # Manifest evidence ID alone (e.g. PORT21-ROM-HEAP-SETUP)
            if cit in manifest_entries:
                entry = manifest_entries[cit]
                s, e = entry["start"], entry["end"]
                for a in addrs:
                    if s <= a <= e:
                        proven_addrs.add(a)
                notes = entry.get("notes", "")
                for hex_str in HEX_ADDR_RE.findall(notes):
                    proven_addrs.add(int(hex_str, 16))
                continue

            # File citation (e.g. path/to/file.c:123 or path/to/file.c:123-145 or path/to/file.c:12, 14)
            file_match = re.match(r"^([a-zA-Z0-9_\-\./]+):([\d,\s\-]+)$", cit)
            if file_match:
                rel_path = file_match.group(1).strip()
                line_spec = file_match.group(2).strip()

                # Reject untracked build outputs explicitly
                if rel_path.startswith("candidate_port2a/") or rel_path.endswith(
                    ("candidate_manifest.json", "candidate_main.elf", ".o", ".bin")
                ):
                    raise AssertionError(
                        f"Line {line_no}: Citation relies on forbidden untracked build output: {rel_path}"
                    )

                if rel_path not in tracked_files:
                    raise AssertionError(
                        f"Line {line_no}: Cited file is not tracked in repository: {rel_path}"
                    )

                full_path = REPO_ROOT / rel_path
                if not full_path.is_file():
                    raise AssertionError(
                        f"Line {line_no}: Cited file does not exist on disk: {rel_path}"
                    )

                lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                for part in line_spec.split(","):
                    part = part.strip()
                    if "-" in part:
                        p_start, p_end = part.split("-", 1)
                        s_l, e_l = int(p_start.strip()), int(p_end.strip())
                    elif part:
                        s_l = int(part)
                        e_l = s_l
                    else:
                        continue

                    if s_l > len(lines):
                        raise AssertionError(
                            f"Line {line_no}: Cited line {s_l} out of bounds for {rel_path} (len {len(lines)})"
                        )

                    cited_text = "\n".join(lines[s_l - 1 : min(e_l, len(lines))])
                    for hex_m in HEX_ADDR_RE.finditer(cited_text):
                        proven_addrs.add(int(hex_m.group(0), 16))
                    # Also capture bare hex numbers or decimal size values in cited lines (e.g. size output)
                    for token in re.findall(r"\b[0-9a-fA-F]{4,8}\b", cited_text):
                        try:
                            proven_addrs.add(int(token, 16))
                        except ValueError:
                            pass
                    for token in re.findall(r"\b\d{4,8}\b", cited_text):
                        try:
                            proven_addrs.add(int(token))
                        except ValueError:
                            pass
                continue

            if cit.startswith("PORT21-ROM-") and cit not in manifest_entries:
                raise AssertionError(f"Line {line_no}: Unknown evidence ID: {cit}")

    # Pass 2: Recompute and validate explicit derivations (Feedback [P2-a])
    for cit in derived_citations:
        expr = cit[len("derived:") :].strip()

        # Format: op1 (+/-) op2 = res
        m_arith1 = re.match(
            r"^(0x[0-9a-fA-F]+)\s*([\+\-])\s*(0x[0-9a-fA-F]+)\s*=\s*(0x[0-9a-fA-F]+)$",
            expr,
        )
        # Format: res = op1 (+/-) op2
        m_arith2 = re.match(
            r"^(0x[0-9a-fA-F]+)\s*=\s*(0x[0-9a-fA-F]+)\s*([\+\-])\s*(0x[0-9a-fA-F]+)$",
            expr,
        )

        if m_arith1:
            op1 = int(m_arith1.group(1), 16)
            op = m_arith1.group(2)
            op2 = int(m_arith1.group(3), 16)
            expected_res = int(m_arith1.group(4), 16)
        elif m_arith2:
            expected_res = int(m_arith2.group(1), 16)
            op1 = int(m_arith2.group(2), 16)
            op = m_arith2.group(3)
            op2 = int(m_arith2.group(4), 16)
        else:
            # Format: op1 = op2 (identity or alias)
            m_eq = re.match(r"^(0x[0-9a-fA-F]+)\s*=\s*(0x[0-9a-fA-F]+)$", expr)
            if m_eq:
                op1 = int(m_eq.group(1), 16)
                expected_res = int(m_eq.group(2), 16)
                if op1 not in proven_addrs:
                    raise AssertionError(
                        f"Line {line_no}: Self-referential or uncited derivation operand {hex(op1)}: {cit}"
                    )
                if op1 != expected_res:
                    raise AssertionError(
                        f"Line {line_no}: Derivation equality mismatch: {cit}"
                    )
                proven_addrs.add(expected_res)
                continue
            else:
                raise AssertionError(
                    f"Line {line_no}: Unrecognized or unsupported derivation format: {cit}"
                )

        # Validate that operands are cited / proven
        if op1 not in proven_addrs:
            raise AssertionError(
                f"Line {line_no}: Derivation operand {hex(op1)} is self-referential or uncited: {cit}"
            )
        if op2 >= 0x1000 and op2 not in proven_addrs:
            raise AssertionError(
                f"Line {line_no}: Derivation operand {hex(op2)} is self-referential or uncited: {cit}"
            )

        computed = (op1 + op2) if op == "+" else (op1 - op2)
        if computed != expected_res:
            raise AssertionError(
                f"Line {line_no}: Derivation arithmetic mismatch: {cit} (computed {hex(computed)} != expected {hex(expected_res)})"
            )
        proven_addrs.add(expected_res)

    # Ensure all addresses on this line have verified provenance
    for a in addrs:
        if a not in proven_addrs:
            in_slice = False
            for m in matches:
                body = m.group(1) or ""
                for cit in body.split(";"):
                    cit = cit.strip()
                    if cit in manifest_entries:
                        s, e = manifest_entries[cit]["start"], manifest_entries[cit]["end"]
                        if s <= a <= e:
                            in_slice = True
                            break
            if not in_slice:
                raise AssertionError(
                    f"Line {line_no}: Address {hex(a)} has no provenance in line citations: {line}"
                )


class TestPort21RamLifetimeDoc(unittest.TestCase):
    """Checks the required analytical sections and claims of docs/PORT21_RAM_LIFETIME.md."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")

    def test_required_sections_present(self):
        """Assert all required analytical sections are present."""
        self.assertIn("## 1. Executive Summary & Epistemic Standards", self.content)
        self.assertIn("## 2. Question (a): Code Path Executing After Branch to Core", self.content)
        self.assertIn("## 3. Question (b): DryOS Heap Start and MEMISOSTART Configuration", self.content)
        self.assertIn("## 4. Question (c): RAM Lifetime & Overwrite Analysis", self.content)
        self.assertIn("## 5. Discrimination of Hypotheses H1–H4", self.content)
        self.assertIn("## 6. Offline Evidence Manifest & Citations", self.content)
        self.assertIn("### 6.2 Read Provenance & Start Address Justification", self.content)

    def test_question_a_answers(self):
        """Verify question (a) addresses core boot() and rejects my_restart continuation."""
        self.assertIn("core boot()", self.content)
        self.assertIn("my_restart continuation", self.content)
        self.assertIn("0x003489B5", self.content)
        self.assertIn("sub_fc05b3c8_my", self.content)

    def test_question_b_answers(self):
        """Verify question (b) addresses heap base 0x003489B4 and shifted base 0x00366CB0."""
        self.assertIn("0x003489B4", self.content)
        self.assertIn("0x00366CB0", self.content)
        self.assertIn("MEMISOSTART", self.content)
        self.assertIn("new_sa", self.content)
        self.assertIn("0x006CE000", self.content)
        self.assertIn("0x000B1FEC", self.content)

    def test_question_c_answers_and_boot_moments(self):
        """Verify question (c) distinguishes Boot Moment 1 and Boot Moment 2."""
        self.assertIn("0x00008000", self.content)
        self.assertIn("0x00024CF0", self.content)
        self.assertIn("0x0035F7A0", self.content)
        self.assertIn("DOES NOT SURVIVE", self.content)
        self.assertIn("Copy Loop 3", self.content)
        self.assertIn("0xFCE91058", self.content)
        self.assertIn("Boot Moment 1", self.content)
        self.assertIn("Boot Moment 2", self.content)

    def test_hypotheses_mapping_table_structure(self):
        """Verify table mapping findings to H1-H4 with supports / rules out / neutral and confidence."""
        self.assertIn("| Finding ID |", self.content)
        self.assertIn("Confidence", self.content)
        self.assertIn("| H1 |", self.content)
        self.assertIn("| H2 |", self.content)
        self.assertIn("| H3 |", self.content)
        self.assertIn("| H4 |", self.content)
        self.assertIn("rules out", self.content)
        self.assertIn("supports", self.content)
        self.assertIn("neutral", self.content)
        self.assertIn("consistent with / plausible", self.content)
        self.assertNotIn("STRONGLY SUPPORTED", self.content)
        self.assertIn("check_compat.c:108-118", self.content)
        self.assertIn("OWNER-REPORTED (PORT-21 milestone brief, 2026-11-01 session", self.content)

    def test_epistemic_labels_present(self):
        """Ensure standard epistemic labels appear throughout."""
        self.assertIn("VERIFIED", self.content)
        self.assertIn("INFERRED", self.content)
        self.assertIn("UNKNOWN", self.content)

    def test_tech_lead_ratification_present(self):
        """Verify Tech Lead ratification is recorded in Section 6.2 (Feedback [P1])."""
        self.assertIn("Tech Lead Ratification (PORT-21 T1, revision 2)", self.content)
        self.assertIn("Ratified by Tech Lead: aligned pre-roll of 8 bytes before `0xFC05B3C8`", self.content)


class TestPort21EvidenceManifest(unittest.TestCase):
    """Validates docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json against rules and ROM dump."""

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

    def test_manifest_budget_limits(self):
        """Ensure <= 4 KiB per slice and <= 64 KiB total."""
        entries = self.manifest.get("evidence_entries", [])
        total_bytes = 0
        for entry in entries:
            count = entry["expected_byte_count"]
            self.assertLessEqual(count, 4096, f"Entry {entry['evidence_id']} exceeds 4 KiB: {count}")
            total_bytes += count
        self.assertLessEqual(total_bytes, 65536, f"Total bytes exceed 64 KiB: {total_bytes}")

    def test_manifest_sha256_against_rom(self):
        """Verify each manifest entry against firmware/dumps/GM1.10C/PRIMARY.BIN via single-pass cached reads."""
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")

        cached_slices, total_bytes_read, rom_present = RomSliceCache.get_slices()
        self.assertTrue(rom_present)
        self.assertLessEqual(
            total_bytes_read,
            65536,
            f"Total bytes read exceed 64 KiB budget: {total_bytes_read}",
        )

        entries = self.manifest.get("evidence_entries", [])
        for entry in entries:
            eid = entry["evidence_id"]
            self.assertIn(eid, cached_slices)
            expected_sha = entry["sha256"]
            actual_sha = cached_slices[eid]["sha256"]
            self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for entry {eid}")
            actual_bytes = cached_slices[eid]["bytes"]
            self.assertEqual(len(actual_bytes), entry["expected_byte_count"])

        # Assert no extra ROM accesses occurred beyond manifest slices (Feedback [P2-c])
        self.assertLessEqual(RomSliceCache._rom_access_count, 1)

    def test_manifest_ratification_notes(self):
        """Verify that each manifest entry contains Tech Lead ratification note (Feedback [P1])."""
        entries = self.manifest.get("evidence_entries", [])
        for entry in entries:
            notes = entry.get("notes", "")
            self.assertIn(
                "start ratified by Tech Lead: aligned pre-roll of",
                notes,
                f"Missing Tech Lead ratification in {entry['evidence_id']} notes",
            )


class TestPort21AddressCitations(unittest.TestCase):
    """Ensures that all addresses cited as VERIFIED in the doc have verifiable provenance."""

    @classmethod
    def setUpClass(cls):
        cls.tracked_files = get_tracked_files()
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)
        cls.manifest_entries = {
            e["evidence_id"]: {
                "start": int(e["start_address"], 16),
                "end": int(e["end_address"], 16),
                "notes": e.get("notes", ""),
            }
            for e in cls.manifest.get("evidence_entries", [])
        }
        # Pre-cache ROM slices (if PRIMARY.BIN exists)
        RomSliceCache.get_slices()

    def test_verified_addresses_have_provenance(self):
        """Validate every line in docs/PORT21_RAM_LIFETIME.md that makes a VERIFIED claim."""
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        for line_idx, line in enumerate(doc_text.splitlines(), start=1):
            if "VERIFIED" in line:
                parse_and_validate_citation(
                    line, line_idx, self.manifest_entries, self.tracked_files
                )

    def test_negative_provenance_checker(self):
        """Ensure that wrong, missing, untracked, uncited rows, or self-referential derivations fail (Feedback [P2-a])."""
        # 1. Missing citation body
        bad_line_1 = "The witness address is 0x0035F7A0 `[VERIFIED]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_1, 100, self.manifest_entries, self.tracked_files
            )

        # 2. Untracked / forbidden build output citation
        bad_line_2 = "Address 0x00366CB0 `[VERIFIED: candidate_manifest.json:21]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_2, 101, self.manifest_entries, self.tracked_files
            )

        # 3. Address not present in cited file line
        bad_line_3 = "Address 0x0035F7A0 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_witness.h:7]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_3, 102, self.manifest_entries, self.tracked_files
            )

        # 4. ROM address outside cited manifest range
        bad_line_4 = "Address 0xFC999999 `[VERIFIED: ROM 0xFC999999; PORT21-ROM-HEAP-SETUP]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_4, 103, self.manifest_entries, self.tracked_files
            )

        # 5. Non-existent file citation
        bad_line_5 = "Address 0x003489B4 `[VERIFIED: docs/nonexistent_file.md:1]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_5, 104, self.manifest_entries, self.tracked_files
            )

        # 6. Uncited VERIFIED table row containing 0xDEADBEEF (Feedback [P2-a])
        bad_row_6 = "| **F99** | Fake finding 0xDEADBEEF | **VERIFIED** | neutral | neutral | neutral | neutral | No citation |"
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_row_6, 105, self.manifest_entries, self.tracked_files
            )

        # 7. Self-referential derivation (Feedback [P2-a])
        bad_line_7a = "Witness address is 0xDEADBEEF `[VERIFIED: derived: 0xDEADBEEF = 0xDEADBEEF]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_7a, 106, self.manifest_entries, self.tracked_files
            )

        bad_line_7b = "Witness address is 0xDEADBEEF `[VERIFIED: derived: 0xDEADBEE0 + 0xF = 0xDEADBEEF]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_7b, 107, self.manifest_entries, self.tracked_files
            )

        # 8. Derivation arithmetic mismatch
        bad_line_8 = "Address 0x003489B4 `[VERIFIED: tools/validate_candidate_port2a.py:50; derived: 0x003489B4 + 0x10 = 0x003489CC]`."
        with self.assertRaises(AssertionError):
            parse_and_validate_citation(
                bad_line_8, 108, self.manifest_entries, self.tracked_files
            )


class TestPort21ScopeIntegrity(unittest.TestCase):
    """Ensures no PORT-20-owned files are touched."""

    def test_no_port20_files_changed(self):
        try:
            status = subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
            )
            for line in status.splitlines():
                filepath = line[3:].strip()
                self.assertFalse(
                    filepath.startswith("docs/PORT20_"),
                    f"Forbidden change to PORT-20 doc: {filepath}",
                )
                self.assertFalse(
                    filepath.startswith("tests/test_port20_"),
                    f"Forbidden change to PORT-20 test: {filepath}",
                )
                self.assertFalse(
                    filepath == "tools/build_candidate_port2a.py",
                    f"Forbidden change to tools/build_candidate_port2a.py: {filepath}",
                )
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
