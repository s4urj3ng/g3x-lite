#!/usr/bin/env python3
"""PORT-21 T1: Unit tests for stock-boot lifetime of core and loader RAM regions.

Validates that:
1. docs/PORT21_RAM_LIFETIME.md exists and contains:
   - Analysis of code path after branch to core (core boot() vs my_restart continuation).
   - Analysis of DryOS heap start / memisostart (stock 0x003489B4 vs candidate 0x00366CB0).
   - Analysis of RAM lifetime / survival for core region 0x003489B4..0x00366CB0 and loader 0x00008000..0x00024CF0.
   - Separation of Boot Moment 1 (stock cold boot) and Boot Moment 2 (post-loader core boot).
   - Table mapping each finding to H1-H4 with supports / rules out / neutral and confidence labels.
   - Read provenance table and the read-start exception approved after the fact.
   - Owner observations labeled OWNER-REPORTED without invented citations.
2. docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json exists, is validated by port11c_evidence_validator.py,
   satisfies slice constraints (<= 4 KiB per slice, <= 64 KiB total), and lists exactly the six
   approved ranges and SHA-256 values.
3. Every address cited on a line labeled VERIFIED has exact, verifiable provenance:
   a tracked file:line (from git ls-files alone), a ROM address within a manifest range, an address
   recorded in a cited manifest entry, or an explicit derivation. This check never reads the ROM.
4. Derivations are strictly recomputed from cited operands and rejected if self-referential.
5. Negative tests proving that missing, wrong, uncited table rows, or self-referential derivations fail validation.
6. ROM-word tests (skipped when PRIMARY.BIN is absent) check the SHA-256 of every slice and every
   literal-pool value claimed in the doc and the manifest notes.
7. No PORT-20-owned files are modified.

PORT21_ROM_PATH overrides the ROM location, e.g. PORT21_ROM_PATH=/nonexistent to run without the ROM.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT21_RAM_LIFETIME.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT21_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_BASE = 0xFC000000

HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{4,8}\b")
CITATION_BLOCK_RE = re.compile(r"\[VERIFIED(?::\s*([^\]]+))?\]")

# Ranges and hashes approved after the fact by the Tech Lead decision,
# AgentBridge task 93 revision 3 (2026-10-31). No other ranges are approved.
APPROVED_READS = {
    "PORT21-ROM-BOOT-EARLY": (0xFC020000, 0xFC0201FF, "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f", None),
    "PORT21-ROM-HEAP-SETUP": (0xFC05B3C0, 0xFC05B53F, "68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6", (8, "0xFC05B3C8")),
    "PORT21-ROM-INIT-TASK": (0xFC05B540, 0xFC05B73F, "15a153beaeabe9770d5016f7240b0b5bbd9ff6ebf56141341cb1e5eebf2a97fe", (24, "0xFC05B558")),
    "PORT21-ROM-STARTUP-TASKS": (0xFC05B8E0, 0xFC05BBDF, "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e", (28, "0xFC05B8FC")),
    "PORT21-ROM-CONTINUATION": (0xFC0D0120, 0xFC0D01FF, "1d536b259e101bf27771a54cd76a617a23ea2f8ea8759c14b054698084959692", (6, "0xFC0D0126")),
    "PORT21-ROM-KERNEL-INIT-VENEER": (0xFC31B400, 0xFC31B47F, "be7ee2c5d2b00286374e2ace906811cc775f0ff2d4c7e16d50855df8d0e589c4", (8, "0xFC31B408")),
}
APPROVAL_SUFFIX = "approved after the fact by Tech Lead decision, AgentBridge task 93 revision 3 (2026-10-31)"

FORBIDDEN_PREFIXES = ("docs/PORT20_", "tests/test_port20_")
FORBIDDEN_FILES = ("tools/build_candidate_port2a.py",)

# Set by TestPort21WithoutRom: a nested unittest run records unittest.SkipTest as a skip
# but would record pytest's Skipped exception as an error.
_FORCE_UNITTEST_SKIP = False


def skip_without_rom() -> None:
    """Skip the calling test when PRIMARY.BIN is absent (pytest.skip under pytest, else unittest)."""
    if ROM_PATH.is_file():
        return
    reason = (
        f"ROM dump not present at {ROM_PATH}; this test compares actual ROM words/hashes "
        "and cannot run without firmware/dumps/GM1.10C/PRIMARY.BIN"
    )
    if "pytest" in sys.modules and not _FORCE_UNITTEST_SKIP:
        import pytest

        pytest.skip(reason)
    raise unittest.SkipTest(reason)


def find_forbidden_paths(changed_paths: list[str]) -> list[str]:
    """Return the PORT-20-owned paths among changed_paths."""
    return [
        p
        for p in changed_paths
        if p.startswith(FORBIDDEN_PREFIXES) or p in FORBIDDEN_FILES
    ]


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

            # ROM citation (e.g. ROM 0xFC05B450, 0xFC05B474; PORT21-ROM-HEAP-SETUP).
            # Only the manifest ranges are consulted; ROM words are never read here
            # (literal values are checked by TestPort21RomWords).
            if cit.startswith("ROM "):
                rom_part = cit[len("ROM ") :].strip()
                for addr_str in HEX_ADDR_RE.findall(rom_part):
                    rom_addr = int(addr_str, 16)
                    in_manifest = False
                    for entry in manifest_entries.values():
                        s, e = entry["start"], entry["end"]
                        if s <= rom_addr <= e:
                            in_manifest = True
                            proven_addrs.add(rom_addr)
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

    def test_read_start_exception_present(self):
        """Section 6.2 records the read-start exception as an after-the-fact approval, not compliance."""
        section = self.content.split("### 6.2 Read Provenance & Start Address Justification", 1)[1]
        self.assertIn("#### Read-start exception", section)
        exc = section.split("#### Read-start exception", 1)[1]
        self.assertIn("start exactly at", exc)
        self.assertIn("5 of the 6 reads broke that rule", exc)
        self.assertIn("BEFORE any approval", exc)
        self.assertIn(
            "AgentBridge milestone PORT-21-OVERNIGHT-DISCRIMINATION, task 93 (T1-ram-lifetime), "
            "REQUEST_REVISION for revision 3, dated 2026-10-31",
            exc,
        )
        self.assertIn("approved exception, NOT compliance", exc)
        self.assertNotIn("ratif", self.content.lower())
        for eid, (_, _, _, exception) in APPROVED_READS.items():
            if exception is None:
                continue
            n, addr = exception
            self.assertIn(f"starts {n} bytes before `{addr}`", section, eid)


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

    def test_manifest_matches_approved_reads(self):
        """The manifest lists exactly the six approved ranges with their approved SHA-256 values."""
        entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        self.assertEqual(set(entries), set(APPROVED_READS))
        for eid, (start, end, sha, _) in APPROVED_READS.items():
            entry = entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start, eid)
            self.assertEqual(int(entry["end_address"], 16), end, eid)
            self.assertEqual(entry["expected_byte_count"], end - start + 1, eid)
            self.assertEqual(entry["sha256"], sha, eid)

    def test_manifest_read_start_notes(self):
        """Each manifest note states its read-start status in the approved wording."""
        for entry in self.manifest.get("evidence_entries", []):
            eid = entry["evidence_id"]
            notes = entry.get("notes", "")
            self.assertNotIn("ratified", notes, eid)
            exception = APPROVED_READS[eid][3]
            if exception is None:
                self.assertIn("starts at cited address; no exception needed", notes, eid)
            else:
                n, addr = exception
                self.assertIn(
                    f"read-start exception: starts {n} bytes before {addr}; {APPROVAL_SUFFIX}",
                    notes,
                    eid,
                )


class TestPort21RomWords(unittest.TestCase):
    """Checks that need the actual ROM bytes; each test skips when PRIMARY.BIN is absent."""

    DOC_LITERAL_RES = (
        re.compile(r"\[(0xFC[0-9A-Fa-f]{6})\]\s*=\s*(0x[0-9A-Fa-f]{1,8})"),
        re.compile(r"`(0xFC[0-9A-Fa-f]{6})`:\s*`(0x[0-9A-Fa-f]{1,8})`"),
    )
    NOTE_LITERAL_RE = re.compile(r"(0x[0-9A-Fa-f]{1,8}) from \[(0xFC[0-9A-Fa-f]{6})\]")

    @classmethod
    def setUpClass(cls):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def _check_literals(self, claims: list[tuple[int, int, str]]) -> None:
        for addr, value, where in claims:
            word = RomSliceCache.lookup_word(addr)
            self.assertIsNotNone(word, f"{where}: {hex(addr)} is not inside a manifest slice")
            self.assertEqual(
                word, value, f"{where}: ROM [{hex(addr)}] = {hex(word)}, claimed {hex(value)}"
            )

    def test_doc_literal_values_match_rom(self):
        """Every '[0xFC......] = value' claim in the doc matches the ROM word."""
        skip_without_rom()
        text = DOC_PATH.read_text(encoding="utf-8")
        claims = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            for regex in self.DOC_LITERAL_RES:
                for m in regex.finditer(line):
                    claims.append((int(m.group(1), 16), int(m.group(2), 16), f"doc line {line_no}"))
        self.assertGreaterEqual(len(claims), 10, "too few literal claims found; regex drift?")
        self._check_literals(claims)

    def test_manifest_note_literal_values_match_rom(self):
        """Every 'value from [0xFC......]' claim in the manifest notes matches the ROM word."""
        skip_without_rom()
        claims = []
        for entry in self.manifest.get("evidence_entries", []):
            for m in self.NOTE_LITERAL_RE.finditer(entry.get("notes", "")):
                claims.append((int(m.group(2), 16), int(m.group(1), 16), entry["evidence_id"]))
        self.assertGreaterEqual(len(claims), 6, "too few note literal claims found; regex drift?")
        self._check_literals(claims)

    def test_manifest_sha256_against_rom(self):
        """Verify each manifest entry against firmware/dumps/GM1.10C/PRIMARY.BIN via single-pass cached reads."""
        skip_without_rom()

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

    def _validate_doc(self):
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        for line_idx, line in enumerate(doc_text.splitlines(), start=1):
            if "VERIFIED" in line:
                parse_and_validate_citation(
                    line, line_idx, self.manifest_entries, self.tracked_files
                )

    def test_verified_addresses_have_provenance(self):
        """Validate every line in docs/PORT21_RAM_LIFETIME.md that makes a VERIFIED claim."""
        self._validate_doc()

    def test_verified_addresses_have_provenance_without_rom(self):
        """The provenance check passes with a nonexistent ROM path and never touches the ROM cache."""
        rom_access = AssertionError("provenance check must not read the ROM")
        with mock.patch(f"{__name__}.ROM_PATH", REPO_ROOT / "nonexistent" / "PRIMARY.BIN"), \
                mock.patch.object(RomSliceCache, "get_slices", side_effect=rom_access), \
                mock.patch.object(RomSliceCache, "lookup_word", side_effect=rom_access):
            self._validate_doc()

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

    @staticmethod
    def _changed_paths() -> list[str]:
        """Paths changed in the working tree and on this branch since its merge-base with origin/main.

        origin/main is preferred because a local main may lag behind merged PRs this branch is based on.
        """
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        )
        paths = []
        for line in status.splitlines():
            entry = line[3:].strip()
            paths.extend(p.strip() for p in entry.split(" -> "))
        base_ref = "origin/main"
        if subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", base_ref],
            cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode != 0:
            base_ref = "main"
        base = subprocess.check_output(
            ["git", "merge-base", "HEAD", base_ref], cwd=REPO_ROOT, text=True
        ).strip()
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", base, "HEAD"], cwd=REPO_ROOT, text=True
        )
        paths.extend(diff.splitlines())
        return paths

    def test_no_port20_files_changed(self):
        try:
            changed = self._changed_paths()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            self.skipTest(f"git changed-path listing unavailable: {exc}")
        forbidden = find_forbidden_paths(changed)
        self.assertEqual(forbidden, [], f"Forbidden changes to PORT-20-owned files: {forbidden}")

    def test_forbidden_path_helper_rejects_port20_paths(self):
        """Negative test: each PORT-20-owned path is rejected; T1 paths are allowed."""
        for bad in (
            "docs/PORT20_FORBIDDEN.md",
            "tests/test_port20_x.py",
            "tools/build_candidate_port2a.py",
        ):
            self.assertEqual(find_forbidden_paths([bad]), [bad], bad)
        allowed = [
            "docs/PORT21_RAM_LIFETIME.md",
            "docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json",
            "tests/test_port21_ram_lifetime.py",
        ]
        self.assertEqual(find_forbidden_paths(allowed), [])


class TestPort21WithoutRom(unittest.TestCase):
    """Re-runs the other test classes with ROM_PATH pointing at a missing file."""

    def test_suite_passes_without_rom(self):
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for cls in (
            TestPort21RamLifetimeDoc,
            TestPort21EvidenceManifest,
            TestPort21RomWords,
            TestPort21AddressCitations,
            TestPort21ScopeIntegrity,
        ):
            suite.addTests(loader.loadTestsFromTestCase(cls))
        result = unittest.TestResult()
        with mock.patch(f"{__name__}.ROM_PATH", REPO_ROOT / "nonexistent" / "PRIMARY.BIN"), \
                mock.patch(f"{__name__}._FORCE_UNITTEST_SKIP", True):
            suite.run(result)
        problems = [f"{t.id()}: {tb}" for t, tb in result.failures + result.errors]
        self.assertEqual(problems, [], "failures without ROM")
        skipped = sorted(t.id().rsplit(".", 1)[1] for t, _ in result.skipped)
        rom_word_tests = sorted(loader.getTestCaseNames(TestPort21RomWords))
        self.assertEqual(skipped, rom_word_tests, "only the ROM-word tests may skip without ROM")
        for _, reason in result.skipped:
            self.assertIn("ROM dump not present", reason)


if __name__ == "__main__":
    unittest.main()
