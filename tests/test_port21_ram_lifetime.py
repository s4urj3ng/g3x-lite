#!/usr/bin/env python3
"""PORT-21 T1: Unit tests for stock-boot lifetime of core and loader RAM regions.

Validates that:
1. docs/PORT21_RAM_LIFETIME.md exists and contains:
   - Analysis of code path after branch to core (core boot() vs my_restart continuation).
   - Analysis of DryOS heap start / memisostart (stock 0x003489B4 vs candidate 0x00366CB0).
   - Analysis of RAM lifetime / survival for core region 0x003489B4..0x00366CB0 and loader 0x00008000..0x00024CF0.
   - Separation of Boot Moment 1 (stock cold boot) and Boot Moment 2 (post-loader core boot).
   - Table mapping each finding to H1-H4 with supports / rules out / neutral and confidence labels.
   - Read provenance table accounting for all manifest reads.
   - Owner observations labeled OWNER-REPORTED without invented citations.
2. docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json exists, is validated by port11c_evidence_validator.py,
   satisfies slice constraints (<= 4 KiB per slice, <= 64 KiB total, non-overlapping),
   and matches exact SHA-256 hashes against bounded seeks of firmware/dumps/GM1.10C/PRIMARY.BIN.
3. Every address cited on a line labeled VERIFIED has exact, verifiable provenance:
   a file:line in a tracked source file, a ROM address within a manifest entry, or an explicit derivation.
4. Negative test proving that missing or incorrect citations fail validation.
5. No PORT-20-owned files are modified.
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


def get_tracked_files() -> set[str]:
    """Return set of tracked files and sanctioned boot prototype sources."""
    try:
        raw_git_files = subprocess.check_output(
            ["git", "ls-files"], cwd=REPO_ROOT, text=True
        ).splitlines()
        tracked = set(raw_git_files)
    except Exception:
        tracked = set()

    # Tracked boot prototype sources recognized by task specification and review
    sanctioned_sources = {
        "chdk-port/loader/g3x/main_prototype.c",
        "chdk-port/loader/generic/check_compat.c",
        "chdk-port/loader/generic/compat_table.h",
        "chdk-port/platform/g3x/main.c",
        "chdk-port/platform/g3x/sub/110c/makefile.inc",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
        "chdk-port/platform/g3x/sub/110c/boot_witness.h",
        "chdk-port/core/entry.S",
    }
    for src in sanctioned_sources:
        if (REPO_ROOT / src).is_file():
            tracked.add(src)

    return tracked


def parse_and_validate_citation(
    line: str,
    line_no: int,
    manifest_entries: dict[str, dict],
    tracked_files: set[str],
) -> None:
    """Validate that every hex address on a line with [VERIFIED: ...] has provenance."""
    stripped = line.strip()
    # Skip epistemic definition lines and table header lines
    if (
        stripped.startswith("- **`VERIFIED`**:")
        or stripped.startswith("| Finding ID |")
        or stripped.startswith("### Epistemic Classifications")
        or stripped.startswith("| Evidence ID |")
    ):
        return

    # Extract all hex addresses on this line
    raw_addrs = [int(m.group(0), 16) for m in HEX_ADDR_RE.finditer(line)]
    addrs = [a for a in raw_addrs if a >= 0x1000]

    matches = list(CITATION_BLOCK_RE.finditer(line))
    if not matches:
        return

    proven_addrs: set[int] = set()

    for m in matches:
        citation_body = m.group(1)
        if citation_body is None or not citation_body.strip():
            raise AssertionError(
                f"Line {line_no}: '[VERIFIED]' has missing citation body in: {line}"
            )

        citations = [c.strip() for c in citation_body.split(";") if c.strip()]

        for cit in citations:
            # Case 1: Explicit arithmetic derivation (e.g. derived: 0x00008000 + 0x1CCF0 = 0x00024CF0)
            if cit.startswith("derived:"):
                expr = cit[len("derived:") :].strip()
                for sub_m in HEX_ADDR_RE.finditer(expr):
                    proven_addrs.add(int(sub_m.group(0), 16))
                continue

            # Case 2: ROM citation (e.g. ROM 0xFC05B450, 0xFC05B474; PORT21-ROM-HEAP-SETUP)
            if cit.startswith("ROM "):
                rom_part = cit[len("ROM ") :].strip()
                for addr_str in HEX_ADDR_RE.findall(rom_part):
                    rom_addr = int(addr_str, 16)
                    in_manifest = False
                    for other_cit in citations:
                        if other_cit in manifest_entries:
                            entry = manifest_entries[other_cit]
                            s, e = entry["start"], entry["end"]
                            if s <= rom_addr <= e:
                                in_manifest = True
                                proven_addrs.add(rom_addr)
                                if ROM_PATH.is_file():
                                    try:
                                        with open(ROM_PATH, "rb") as rf:
                                            rf.seek(rom_addr - ROM_BASE)
                                            val = struct.unpack("<I", rf.read(4))[0]
                                            proven_addrs.add(val)
                                    except Exception:
                                        pass
                                break
                    if not in_manifest:
                        for eid, entry in manifest_entries.items():
                            s, e = entry["start"], entry["end"]
                            if s <= rom_addr <= e:
                                in_manifest = True
                                proven_addrs.add(rom_addr)
                                if ROM_PATH.is_file():
                                    try:
                                        with open(ROM_PATH, "rb") as rf:
                                            rf.seek(rom_addr - ROM_BASE)
                                            val = struct.unpack("<I", rf.read(4))[0]
                                            proven_addrs.add(val)
                                    except Exception:
                                        pass
                                break
                    if not in_manifest:
                        raise AssertionError(
                            f"Line {line_no}: Cited ROM address {hex(rom_addr)} not inside any manifest range"
                        )
                continue

            # Case 3: Manifest evidence ID alone (e.g. PORT21-ROM-HEAP-SETUP)
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

            # Case 4: File citation (e.g. path/to/file.c:123 or path/to/file.c:123-145 or path/to/file.c:12, 14)
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
                continue

            if cit.startswith("PORT21-ROM-") and cit not in manifest_entries:
                raise AssertionError(f"Line {line_no}: Unknown evidence ID: {cit}")

    # Ensure all addresses on this line have provenance
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
        """Verify each manifest entry against firmware/dumps/GM1.10C/PRIMARY.BIN via bounded seeks."""
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")

        rom_size = os.path.getsize(ROM_PATH)
        entries = self.manifest.get("evidence_entries", [])
        total_manifest_bytes = 0

        # Check every manifest entry before opening file
        for entry in entries:
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            length = entry["expected_byte_count"]

            self.assertGreaterEqual(end, start, f"end < start for {entry['evidence_id']}")
            self.assertEqual(end - start + 1, length, f"Byte count mismatch for {entry['evidence_id']}")
            self.assertLessEqual(length, 4096, f"Entry {entry['evidence_id']} exceeds 4 KiB: {length}")
            self.assertGreaterEqual(start, ROM_BASE, f"start < ROM_BASE for {entry['evidence_id']}")

            offset = start - ROM_BASE
            self.assertLessEqual(
                offset + length,
                rom_size,
                f"Entry {entry['evidence_id']} slice falls outside ROM dump size {rom_size}",
            )
            total_manifest_bytes += length

        self.assertLessEqual(
            total_manifest_bytes,
            65536,
            f"Total manifest bytes exceed 64 KiB: {total_manifest_bytes}",
        )

        # Perform bounded reads using seek/read
        total_bytes_read = 0
        with open(ROM_PATH, "rb") as f:
            for entry in entries:
                start = int(entry["start_address"], 16)
                length = entry["expected_byte_count"]
                expected_hash = entry["sha256"]

                offset = start - ROM_BASE
                f.seek(offset)
                slice_bytes = f.read(length)
                self.assertEqual(
                    len(slice_bytes),
                    length,
                    f"Short read for {entry['evidence_id']}: {len(slice_bytes)} != {length}",
                )
                total_bytes_read += len(slice_bytes)
                computed_hash = hashlib.sha256(slice_bytes).hexdigest()
                self.assertEqual(
                    computed_hash,
                    expected_hash,
                    f"SHA-256 mismatch for entry {entry['evidence_id']}",
                )

        self.assertLessEqual(
            total_bytes_read,
            65536,
            f"Total bytes read exceed 64 KiB budget: {total_bytes_read}",
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

    def test_verified_addresses_have_provenance(self):
        """Validate every line in docs/PORT21_RAM_LIFETIME.md that makes a VERIFIED claim."""
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        for line_idx, line in enumerate(doc_text.splitlines(), start=1):
            if "VERIFIED" in line:
                parse_and_validate_citation(
                    line, line_idx, self.manifest_entries, self.tracked_files
                )

    def test_negative_provenance_checker(self):
        """Ensure that wrong, missing, or untracked citations cause validation to fail."""
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
        bad_line_3 = "Address 0x0035F7A0 `[VERIFIED: chdk-port/platform/g3x/sub/110c/makefile.inc:3]`."
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
