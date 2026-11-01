#!/usr/bin/env python3
"""PORT-24: Unit tests for loader post-prologue trace analysis and restart path.

Validates that:
1. docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:
   - Validates using tools/port11c_evidence_validator.py with 0 errors.
   - Preserves all 14 T1 approved ranges and appends 5 T2 approved ranges.
   - Each window is <= 4 KiB, and total bytes <= 32 KiB.
   - Total bytes of T2 entries <= 32 KiB, each T2 entry <= 4 KiB.
   - Contains no overlapping evidence slices.
   - If PRIMARY.BIN is present, slice SHA-256 digests match actual ROM dump on disk.
2. docs/PORT24_LOADER_TRACE.md:
   - File exists and contains all required core sections (Sections 1-7 and ## Restart path).
   - T1 trace and tables intact (Steps 1 to 29, failure ranking, stubs, size pairs).
   - '## Restart path' section exists and explains what decides whether a power-on
     runs StartDiskboot on GM1.10C with exact citations.
   - Explains the repeated/long-press stock-boot observation and states whether a later
     power-on can skip StartDiskboot and under which conditions (citing branch addresses).
   - Connects the held power button to the O1 result (CONT_ATTEMPTED / FRESHNESS_UNVERIFIED).
   - '## Restart path' contains no 'STATIC_VERIFIED' and no 'X / Y' combined labels.
   - Every claim in '## Restart path' carries exactly one label from {VERIFIED, INFERRED, UNKNOWN}.
   - Every 0xFC...... and 0xFD...... address cited falls inside an approved manifest range.
   - Concludes with a list of observable physical cues for the owner (used by T4).
3. Scope integrity:
   - git ls-files tracks no build outputs or ROM images.
   - The evidence manifest holds only ranges, digests and metadata, never raw ROM bytes.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT24_LOADER_TRACE.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT24_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT24_ROM_PATH",
        os.environ.get(
            "PORT23_ROM_PATH",
            os.environ.get("PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")),
        ),
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"

# ROM base and size as defined by repository sources:
ROM_BASE = 0xFC000000
ROM_SIZE = 0x02000000
ROM_END = ROM_BASE + ROM_SIZE

# Canonical PORT-24 T1 evidence entries (14 approved ranges)
APPROVED_ENTRIES_T1 = {
    "PORT24-ROM-BOOT-EARLY": (
        0xFC020000,
        0xFC0201FF,
        512,
        "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f",
    ),
    "PORT24-ROM-STARTUP-TASKS": (
        0xFC05B8E0,
        0xFC05BBDF,
        768,
        "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e",
    ),
    "PORT24-ROM-STARTDISKBOOT": (
        0xFC05BBEA,
        0xFC05BDE9,
        512,
        "a2ea19dfed6f386b32074c65ec682a557a24cf3ddcdeb73f29108ae16854acfc",
    ),
    "PORT24-ROM-NORMAL-MODE": (
        0xFC079400,
        0xFC0794FF,
        256,
        "222eb4225d2e5d34742f5ed11b306b21c44a1eb2e18e48936cc6643d08a9560c",
    ),
    "PORT24-ROM-FIRMWARE-CONT": (
        0xFC0D0080,
        0xFC0D023F,
        448,
        "33d2fae4ed8c9c228ea6cc8f3304a26b96f8a4fb6d9d3bdc37cd056e7833456e",
    ),
    "PORT24-ROM-GPIO-WRITE-MMIO": (
        0xFC0D73C0,
        0xFC0D74BF,
        256,
        "0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b",
    ),
    "PORT24-ROM-HANDOFF-PREPARE": (
        0xFC0D9C00,
        0xFC0D9DFF,
        512,
        "8c891f7dc8fc758510f36a69d95ff323cee00a7ac0e853128d1be27d8598d644",
    ),
    "PORT24-ROM-CACHE-MAINT": (
        0xFC127A00,
        0xFC127B7F,
        384,
        "519594faaab42e66229096ef890f9161e2d1715e6044a911a74e2ebdf20415cb",
    ),
    "PORT24-ROM-POWERON-CHECK": (
        0xFC1284A0,
        0xFC1285DF,
        320,
        "634fd848e765cad5b01737956e6aea9ddd12dbb4413213ec2a9c3d2a421813d4",
    ),
    "PORT24-ROM-MPU-CONFIG": (
        0xFC135280,
        0xFC1352FF,
        128,
        "3327ae3b2b5508a96aeab70b4076fd83fa199ae9c77d550475bd4effef5f5a5c",
    ),
    "PORT24-ROM-WATCHDOG-MODULE": (
        0xFC135C00,
        0xFC135E3F,
        576,
        "29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb",
    ),
    "PORT24-ROM-IRQ-DISABLE": (
        0xFC31BEE0,
        0xFC31BF3F,
        96,
        "a15cb37e666e3349c0453b294d1283d99ae116214f36fc69671cdc3131db7826",
    ),
    "PORT24-ROM-CACHE-HELPERS": (
        0xFC418700,
        0xFC41875F,
        96,
        "7b087b15bbda1469b0809961e58fb50b83968ec36285733590b4bed66244dd4a",
    ),
    "PORT24-ROM-WATCHDOG-START": (
        0xFC418F20,
        0xFC418F7F,
        96,
        "46e8e2149df855d0f1414699a1fdea355b9370c83e552a749314a32283da7da5",
    ),
}

# Canonical PORT-24 T2 evidence entries (5 appended ranges)
APPROVED_ENTRIES_T2 = {
    "PORT24-ROM-CARD-SWITCHES": (
        0xFC05C4D0,
        0xFC05C51F,
        80,
        "886c3e10248cc33ac671b575331311bbaf59ae549ab01a9414ddb1b470c314c5",
    ),
    "PORT24-ROM-STARTCAUSE-SAVE": (
        0xFC08ECB0,
        0xFC08ECFF,
        80,
        "039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d",
    ),
    "PORT24-ROM-STARTCAUSE-PTR": (
        0xFC08EEE0,
        0xFC08EEFF,
        32,
        "0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6",
    ),
    "PORT24-ROM-VBR-CHECK": (
        0xFC37AE60,
        0xFC37AEFF,
        160,
        "fc69a8c1639c873ca00c80edca02bdccdc52b1396fbb90eedc49821463c3ce17",
    ),
    "PORT24-ROM-NORMAL-FLAG": (
        0xFDF20380,
        0xFDF2038F,
        16,
        "7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64",
    ),
}

APPROVED_ENTRIES = {**APPROVED_ENTRIES_T1, **APPROVED_ENTRIES_T2}

# Strict label pattern: only VERIFIED, INFERRED, UNKNOWN allowed
LABEL_PATTERN = re.compile(
    r"\[(VERIFIED|INFERRED|UNKNOWN)[^\]]*\]"
)

# Build-output / binary patterns that must never be tracked (matched against the basename).
FORBIDDEN_TRACKED_PATTERNS = ("*.bin", "*.BIN", "*.elf", "*.o", "*.fir", "DISKBOOT*", "PRIMARY*")

# Tracked before PORT-24 and outside this task's scope: the witness inspector payload.
PRE_EXISTING_TRACKED_BINARIES = {
    "firmware/tools/witness_inspector_payload.bin",
}

# Keys that would indicate raw ROM bytes stored in the manifest.
FORBIDDEN_MANIFEST_KEYS = {
    "bytes", "raw", "raw_bytes", "data", "hex", "hexdump", "hex_dump",
    "payload", "content", "contents", "base64", "dump", "rom_bytes",
}

ALLOWED_EVIDENCE_ENTRY_KEYS = {
    "evidence_id", "firmware_revision", "start_address", "end_address",
    "expected_byte_count", "sha256", "provenance_source", "authorization_scope_id",
    "classification", "notes",
}

P_ROM_HEX = re.compile(r"\b0x([fF][c-fC-F0-9][0-9a-fA-F]{5,6})\b")
P_ROM_DISASM = re.compile(r"\b([fF][c-fC-F0-9][0-9a-fA-F]{6}):")
P_ROM_SYM = re.compile(r"\b(?:sub|loc|stub)_([fF][cC0-9][0-9a-fA-F]{6})\b", re.IGNORECASE)


class TestPort24LoaderTrace(unittest.TestCase):
    """Test suite verifying PORT-24 evidence manifest and loader trace document."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(MANIFEST_PATH.exists(), f"Manifest missing: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

        cls.assertTrue(DOC_PATH.exists(), f"Doc missing: {DOC_PATH}")
        with open(DOC_PATH, "r", encoding="utf-8") as f:
            cls.content = f.read()
            cls.lines = cls.content.splitlines()

    def test_validator_tool_accepts_manifest(self):
        """Manifest validates using tools/port11c_evidence_validator.py."""
        self.assertTrue(VALIDATOR_TOOL.exists(), f"Validator tool missing: {VALIDATOR_TOOL}")
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Validator failed:\n{res.stderr}\n{res.stdout}")
        self.assertIn("Result: VALID (0 errors", res.stdout)

    def test_all_approved_ranges_present_and_match(self):
        """All approved evidence ranges (T1 and T2) are declared with exact bounds and SHA-256."""
        entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        self.assertEqual(len(entries), len(APPROVED_ENTRIES))

        for eid, (start, end, count, sha) in APPROVED_ENTRIES_T1.items():
            self.assertIn(eid, entries, f"T1 evidence entry '{eid}' missing from manifest")
            entry = entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start)
            self.assertEqual(int(entry["end_address"], 16), end)
            self.assertEqual(entry["expected_byte_count"], count)
            self.assertEqual(entry["sha256"], sha)
            self.assertEqual(entry["classification"], "STATIC_VERIFIED")
            self.assertEqual(entry["firmware_revision"], "GM1.10C")
            self.assertEqual(entry["provenance_source"]["reference"], "firmware/dumps/GM1.10C/PRIMARY.BIN")

        for eid, (start, end, count, sha) in APPROVED_ENTRIES_T2.items():
            self.assertIn(eid, entries, f"T2 evidence entry '{eid}' missing from manifest")
            entry = entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start)
            self.assertEqual(int(entry["end_address"], 16), end)
            self.assertEqual(entry["expected_byte_count"], count)
            self.assertEqual(entry["sha256"], sha)
            self.assertEqual(entry["classification"], "STATIC_VERIFIED")
            self.assertEqual(entry["firmware_revision"], "GM1.10C")
            self.assertEqual(entry["provenance_source"]["reference"], "firmware/dumps/GM1.10C/PRIMARY.BIN")

    def test_range_and_budget_limits(self):
        """Each slice is <= 4 KiB and total budget is <= 32 KiB (both overall and T2 specific)."""
        entries = self.manifest.get("evidence_entries", [])
        total_bytes = 0
        for entry in entries:
            count = entry["expected_byte_count"]
            self.assertLessEqual(count, 4096, f"Slice '{entry['evidence_id']}' exceeds 4 KiB limit")
            total_bytes += count
        self.assertLessEqual(total_bytes, 32768, f"Total byte count ({total_bytes}) exceeds 32 KiB budget")

        # T2 budget verification
        entries_by_id = {e["evidence_id"]: e for e in entries}
        t2_bytes = sum(entries_by_id[eid]["expected_byte_count"] for eid in APPROVED_ENTRIES_T2)
        self.assertLessEqual(t2_bytes, 32768, f"T2 byte count ({t2_bytes}) exceeds 32 KiB budget")
        for eid in APPROVED_ENTRIES_T2:
            count = entries_by_id[eid]["expected_byte_count"]
            self.assertLessEqual(count, 4096, f"T2 slice '{eid}' exceeds 4 KiB limit: {count} B")

    def test_no_slice_overlaps(self):
        """Evidence ranges are completely non-overlapping and sorted."""
        entries = self.manifest.get("evidence_entries", [])
        spans = []
        for e in entries:
            start = int(e["start_address"], 16)
            end = int(e["end_address"], 16)
            self.assertLessEqual(start, end)
            self.assertEqual(end - start + 1, e["expected_byte_count"])
            spans.append((start, end, e["evidence_id"]))

        spans.sort(key=lambda x: x[0])
        for i in range(len(spans) - 1):
            curr_start, curr_end, curr_id = spans[i]
            next_start, next_end, next_id = spans[i + 1]
            self.assertLess(
                curr_end,
                next_start,
                f"Range overlap between {curr_id} (0x{curr_start:08X}..0x{curr_end:08X}) "
                f"and {next_id} (0x{next_start:08X}..0x{next_end:08X})",
            )

    def test_hashes_match_primary_bin_if_present(self):
        """If PRIMARY.BIN is present on disk, actual slice SHA-256 matches declared digest."""
        if not ROM_PATH.exists():
            self.skipTest(f"PRIMARY.BIN not present at {ROM_PATH}")

        with open(ROM_PATH, "rb") as f:
            for eid, (start, end, count, expected_sha) in APPROVED_ENTRIES.items():
                offset = start - ROM_BASE
                f.seek(offset)
                data = f.read(count)
                self.assertEqual(len(data), count, f"Short read for {eid}")
                actual_sha = hashlib.sha256(data).hexdigest()
                self.assertEqual(
                    actual_sha,
                    expected_sha,
                    f"SHA-256 mismatch for {eid} at offset 0x{offset:08X}",
                )

    def test_required_sections_exist(self):
        """PORT24_LOADER_TRACE.md contains all required structural sections including ## Restart path."""
        required_headers = [
            "# PORT-24 T1: Loader Post-Prologue Trace",
            "## 1. Executive Summary & Purpose",
            "## 2. StartDiskboot Hand-Off State & Environment",
            "## 3. Disassembly Excerpts of Build Candidates",
            "## 4. Comprehensive Step Trace: 0x8000 to CHDK Core and Firmware Hand-Off",
            "## 5. Summary Trace Matrix (Steps 1 to 29)",
            "## 6. Ranked Table of Failure Steps (Post-Prologue Shutdown Likelihood)",
            "## 7. Offline Evidence Manifest & Citations",
            "## Restart path",
        ]
        for header in required_headers:
            self.assertIn(header, self.content, f"Missing required section header: {header}")

    def test_handoff_environment_coverage(self):
        """Doc covers entry 0x8001 Thumb, registers, stack, cache/MMU, IRQs, watchdog, and power."""
        self.assertIn("0x8001", self.content)
        self.assertIn("Thumb", self.content)
        self.assertIn("0xFC0D9C9C", self.content)
        self.assertIn("0xFC31BEFC", self.content)
        self.assertIn("0xFC41870C", self.content)
        self.assertIn("0xFC135284", self.content)
        self.assertIn("0xFC0D00B2", self.content)
        self.assertIn("Region 7", self.content)
        self.assertIn("0x40008000", self.content)
        self.assertIn("cpsid", self.content)
        self.assertIn("watchdog", self.content.lower())

    def test_no_static_verified_labels(self):
        """Ensure STATIC_VERIFIED does not appear anywhere in docs/PORT24_LOADER_TRACE.md."""
        matches = re.findall(r"\bSTATIC_VERIFIED\b", self.content)
        self.assertEqual(
            matches,
            [],
            f"Found STATIC_VERIFIED in {DOC_PATH}: {len(matches)} occurrences. "
            f"Use only VERIFIED, INFERRED, UNKNOWN.",
        )

    def test_step_trace_matrix_complete(self):
        """Step trace table covers all 29 distinct steps from 0x8000 to continuation."""
        table_section = self.content.split("## 5. Summary Trace Matrix (Steps 1 to 29)", 1)[1]
        table_section = table_section.split("## 6. Ranked Table", 1)[0]

        for step_num in range(1, 30):
            pattern = rf"\|\s*\*\*{step_num}\*\*\s*\|"
            self.assertTrue(
                re.search(pattern, table_section),
                f"Step {step_num} missing from summary trace matrix",
            )

        self.assertIn("`_start` (`0x8000`)", table_section)
        self.assertIn("`check_compat`", table_section)
        self.assertIn("`core_copy`", table_section)
        self.assertIn("`0xFC127AB1`", table_section)
        self.assertIn("`0xFC127B09`", table_section)
        self.assertIn("Handoff Jump", table_section)
        self.assertIn("Core Entry", table_section)
        self.assertIn("Sanity Check", table_section)
        self.assertIn("Stack Pointer Reset", table_section)
        self.assertIn("Vector Table Copy", table_section)
        self.assertIn("High RAM Copy", table_section)
        self.assertIn("ATCM Copy", table_section)
        self.assertIn("Low RAM Copy", table_section)
        self.assertIn("Canon BSS Zero", table_section)
        self.assertIn("Power-On Check", table_section)
        self.assertIn("Power Cut Action", table_section)
        self.assertIn("Firmware Handoff", table_section)

        section4 = self.content.split("## 4. Comprehensive Step Trace", 1)[1]
        section4 = section4.split("## 5. Summary Trace Matrix", 1)[0]
        for step_num in range(1, 30):
            step_header_re = rf"-\s*\*\*Step {step_num}:"
            self.assertTrue(
                re.search(step_header_re, section4),
                f"Step {step_num} detail header missing in Section 4",
            )

        comparison_count = len(re.findall(r"-\s*Comparison with StartDiskboot Hand-Off:", section4, re.IGNORECASE))
        self.assertEqual(
            comparison_count,
            29,
            f"Expected exactly 29 'Comparison with StartDiskboot Hand-Off' lines in Section 4, found {comparison_count}",
        )

    def test_failure_steps_ranking_present(self):
        """Ranked table ranks candidate failure steps and identifies primary root cause."""
        ranking_section = self.content.split("## 6. Ranked Table of Failure Steps", 1)[1]
        ranking_section = ranking_section.split("## 7. Offline Evidence Manifest", 1)[0]

        for rank_num in range(1, 6):
            pattern = rf"\|\s*\*\*{rank_num}\*\*\s*\|"
            self.assertTrue(
                re.search(pattern, ranking_section),
                f"Rank {rank_num} missing from failure steps ranking table",
            )

        self.assertIn("PRIMARY ROOT CAUSE", ranking_section)
        self.assertIn("sub_fc1284ac", ranking_section)
        self.assertIn("sub_fc05ba56", ranking_section)
        self.assertIn("0xD20B099C", ranking_section)

    def test_all_claim_bullets_and_rows_carry_epistemic_labels(self):
        """Every claim bullet, numbered item, table row, and prose paragraph carries an epistemic label."""
        unlabeled_bullets = []
        unlabeled_rows = []
        unlabeled_prose = []

        in_code_block = False
        paragraph_lines = []
        paragraph_start_line = 0

        def check_paragraph(lines, start_line):
            text = " ".join(l.strip() for l in lines).strip()
            if not text:
                return
            if not LABEL_PATTERN.search(text):
                unlabeled_prose.append(f"Line {start_line}: {text}")

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_code_block and paragraph_lines:
                    check_paragraph(paragraph_lines, paragraph_start_line)
                    paragraph_lines = []
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            if not stripped or stripped.startswith(("#", "---", "<!--")):
                if paragraph_lines:
                    check_paragraph(paragraph_lines, paragraph_start_line)
                    paragraph_lines = []
                continue

            # Check bullets (- / *) or numbered list items (1. / 2.)
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
                if paragraph_lines:
                    check_paragraph(paragraph_lines, paragraph_start_line)
                    paragraph_lines = []
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_bullets.append(f"Line {i}: {stripped}")
            # Check table content rows (excluding separators and headers)
            elif stripped.startswith("|") and stripped.endswith("|"):
                if paragraph_lines:
                    check_paragraph(paragraph_lines, paragraph_start_line)
                    paragraph_lines = []
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue
                if any(hdr in stripped for hdr in ["Rank", "Evidence ID", "Step #", "Operation", "Stub Symbol"]):
                    continue
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_rows.append(f"Line {i}: {stripped}")
            else:
                if not paragraph_lines:
                    paragraph_start_line = i
                paragraph_lines.append(stripped)

        if paragraph_lines:
            check_paragraph(paragraph_lines, paragraph_start_line)

        self.assertEqual(
            unlabeled_bullets,
            [],
            f"Found unlabeled bullets in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unlabeled_bullets[:10]),
        )
        self.assertEqual(
            unlabeled_rows,
            [],
            f"Found unlabeled table rows in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unlabeled_rows[:10]),
        )
        self.assertEqual(
            unlabeled_prose,
            [],
            f"Found unlabeled prose paragraphs in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unlabeled_prose[:10]),
        )

    def check_rom_addresses_coverage(self, text_or_lines):
        """Extract all ROM addresses and check if they are covered by manifest evidence entries."""
        if isinstance(text_or_lines, str):
            lines = text_or_lines.splitlines()
        else:
            lines = text_or_lines

        entries = self.manifest.get("evidence_entries", [])
        evidence_ranges = [
            (int(e["start_address"], 16), int(e["end_address"], 16), e["evidence_id"])
            for e in entries
        ]

        def is_in_evidence_entries(addr_int: int) -> bool:
            return any(start <= addr_int <= end for start, end, _ in evidence_ranges)

        verified_rom_addrs = set()
        uncovered_addrs = []

        for line_no, line in enumerate(lines, start=1):
            hex_matches = P_ROM_HEX.findall(line)
            disasm_matches = P_ROM_DISASM.findall(line)
            sym_matches = P_ROM_SYM.findall(line)
            all_addr_strs = set(hex_matches + disasm_matches + sym_matches)
            if not all_addr_strs:
                continue

            is_sb = bool(re.search(r"\bsource/build\b", line, re.IGNORECASE))

            for addr_str in all_addr_strs:
                val = int(addr_str, 16)
                if not (ROM_BASE <= val < ROM_END):
                    continue

                if is_in_evidence_entries(val):
                    verified_rom_addrs.add(f"0x{val:08X}")
                elif is_sb:
                    continue
                else:
                    uncovered_addrs.append(
                        f"Line {line_no}: 0x{val:08X} lies in ROM mapping [0x{ROM_BASE:08X}, 0x{ROM_END:08X}) but is outside manifest evidence entries: {line.strip()}"
                    )

        return uncovered_addrs, verified_rom_addrs

    def test_every_cited_rom_address_covered_by_manifest_entries(self):
        """Strict coverage test: every ROM address cited in the doc must fall within
        an evidence entry declared in docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json.
        """
        uncovered_addrs, verified_rom_addrs = self.check_rom_addresses_coverage(self.lines)

        self.assertGreater(
            len(verified_rom_addrs),
            15,
            f"Too few verified manifest addresses found in doc ({len(verified_rom_addrs)})",
        )
        self.assertEqual(
            uncovered_addrs,
            [],
            f"Found uncovered ROM addresses in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(uncovered_addrs[:10]),
        )

    def test_negative_checker_reports_uncovered_for_bare_disasm_and_stub(self):
        """Negative unit tests: checker reports bare disasm addresses ('fcdead00: bx lr')
        and stub symbols ('call stub_fcdead00') as uncovered when outside manifest entries.
        """
        uncovered_disasm, _ = self.check_rom_addresses_coverage("fcdead00: bx lr")
        self.assertTrue(
            any("FCDEAD00" in u for u in uncovered_disasm),
            f"Bare disassembly address 'fcdead00: bx lr' was not reported as uncovered: {uncovered_disasm}",
        )

        uncovered_stub, _ = self.check_rom_addresses_coverage("call stub_fcdead00")
        self.assertTrue(
            any("FCDEAD00" in u for u in uncovered_stub),
            f"Stub symbol 'call stub_fcdead00' was not reported as uncovered: {uncovered_stub}",
        )

    def test_offline_manifest_table_matches_json(self):
        """Offline evidence table in Section 7 matches PORT24_EVIDENCE_MANIFEST.json T1 entries."""
        section7 = self.content.split("## 7. Offline Evidence Manifest & Citations", 1)[1]
        section7_only = section7.split("## Restart path", 1)[0]
        row_re = re.compile(
            r"\|\s*`([^`]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*(\d+)\s*B\s*\|\s*`([0-9a-f]{64})`\s*\|"
        )
        cited_ranges = row_re.findall(section7_only)
        self.assertEqual(len(cited_ranges), len(APPROVED_ENTRIES_T1))

        manifest_entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        for eid, start_str, end_str, byte_count_str, sha in cited_ranges:
            self.assertIn(eid, manifest_entries, f"Table row '{eid}' missing from JSON manifest")
            entry = manifest_entries[eid]
            self.assertEqual(int(start_str, 16), int(entry["start_address"], 16))
            self.assertEqual(int(end_str, 16), int(entry["end_address"], 16))
            self.assertEqual(int(byte_count_str), entry["expected_byte_count"])
            self.assertEqual(sha.lower(), entry["sha256"].lower())

    def test_atcm_copied_extent_in_step_table(self):
        """Step table (Section 5, Step 15) must state the ATCM copied extent 0x6C1C = 27,676 B."""
        table = self.content.split("## 5. Summary Trace Matrix (Steps 1 to 29)", 1)[1]
        table = table.split("## 6. Ranked Table", 1)[0]
        step15_lines = [l for l in table.splitlines() if re.match(r"^\|\s*\*\*15\*\*\s*\|", l.strip())]
        self.assertEqual(len(step15_lines), 1, "Missing Step 15 row in step table")
        step15_row = step15_lines[0]
        self.assertIn("0x6C1C", step15_row)
        self.assertIn("27,676", step15_row)
        self.assertIn("27,673", step15_row)
        self.assertIn("6,919 words", step15_row)

    def test_step28_branch_trace_and_stubs_table(self):
        """Step 28 must include the branch trace for boot_prototype.c:397-407 and all 46 stubs."""
        step28_text = self.content.split("- **Step 28: Driver Initialization", 1)[1]
        step28_text = step28_text.split("- **Step 29:", 1)[0]
        self.assertIn("boot_prototype.c:397-407", step28_text)
        self.assertIn("bne.n", step28_text.lower())
        self.assertIn("blx", step28_text.lower())
        self.assertIn("stub_fc31b1f4", step28_text)
        self.assertIn("Stubs LDR PC Branch Table (stubs_asm.h:60-74)", step28_text)
        with open(REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "stubs_prototype.S") as f:
            stubs = re.findall(r"STUB2?\(([0-9a-fA-F]+)\)", f.read())
        self.assertEqual(len(stubs), 46)
        for s in stubs:
            self.assertIn(f"stub_{s}", step28_text)

    def test_hex_decimal_size_conversions_exact(self):
        """Every '0xHEX = N bytes' pair, 'N bytes (`0xHEX`)' pair and 'N bytes (M words)' pair is exact."""
        p_hex_eq = re.compile(r"`?0x([0-9A-Fa-f]+)`?\s*=\s*`?([\d,]+)`?\s*(?:bytes|B)\b")
        p_dec_hex = re.compile(r"`?([\d,]+)`?\s*bytes\s*\(`0x([0-9A-Fa-f]+)`\s*(?:B\b)?[,)]")
        p_words = re.compile(r"([\d,]+)\s*bytes\s*\(([\d,]+)\s*words\)")

        def num(s: str) -> int:
            return int(s.replace(",", ""))

        errors = []
        pairs = 0
        for line_no, line in enumerate(self.lines, start=1):
            for h, n in p_hex_eq.findall(line):
                pairs += 1
                if int(h, 16) != num(n):
                    errors.append(f"Line {line_no}: 0x{h} = {int(h, 16)}, doc says {n}")
            for n, h in p_dec_hex.findall(line):
                pairs += 1
                if int(h, 16) != num(n):
                    errors.append(f"Line {line_no}: 0x{h} = {int(h, 16)}, doc says {n}")
            for n, w in p_words.findall(line):
                if num(n) != 4 * num(w):
                    errors.append(f"Line {line_no}: {n} bytes != 4 * {w} words")
        self.assertEqual(errors, [], "Inexact size conversions:\n" + "\n".join(errors))

        table = self.content.split("## 5. Summary Trace Matrix (Steps 1 to 29)", 1)[1]
        table = table.split("## 6. Ranked Table", 1)[0]
        table_pairs = p_hex_eq.findall(table)
        self.assertGreaterEqual(len(table_pairs), 8, f"Too few hex/byte pairs in step table: {table_pairs}")
        for h, n in table_pairs:
            self.assertEqual(int(h, 16), num(n), f"Step table: 0x{h} != {n} bytes")
        self.assertGreater(pairs, len(table_pairs))

    def test_ranking_judgements_not_verified(self):
        """Every ranking row's final epistemic status is INFERRED or UNKNOWN, never VERIFIED."""
        ranking = self.content.split("## 6. Ranked Table of Failure Steps", 1)[1]
        ranking = ranking.split("## 7. Offline Evidence Manifest", 1)[0]
        rows = [l for l in ranking.splitlines() if re.match(r"^\|\s*\*\*\d+\*\*\s*\|", l.strip())]
        self.assertGreaterEqual(len(rows), 5)
        for row in rows:
            status_cell = row.strip().strip("|").split("|")[-1]
            self.assertRegex(status_cell, r"\[(INFERRED|UNKNOWN)\b", f"Ranking row not INFERRED/UNKNOWN: {row}")
            self.assertNotIn("[VERIFIED", status_cell, f"Ranking judgement labelled VERIFIED: {row}")

    def test_led_build_provenance_disclosed(self):
        """Section 6 states that observations (b)/(c) came from the LED build and compares its prologue."""
        ranking = self.content.split("## 6. Ranked Table of Failure Steps", 1)[1]
        ranking = ranking.split("## 7. Offline Evidence Manifest", 1)[0]
        self.assertIn("docs/PORT23_POWER_SUPERVISION.md:20-21, 34", ranking)
        self.assertIn("loader_entry_led.S:47-49", ranking)
        self.assertIn("entry.S:7-8", ranking)

    def test_no_build_outputs_or_rom_images_tracked(self):
        """git ls-files tracks no build outputs, binaries or ROM images (post-merge safe)."""
        try:
            res = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("git not available")
        if res.returncode != 0:
            self.skipTest(f"not a git checkout: {res.stderr.strip()}")
        tracked = [p for p in res.stdout.split("\0") if p]
        self.assertTrue(tracked, "git ls-files returned no files")
        offending = sorted(
            p
            for p in tracked
            if p not in PRE_EXISTING_TRACKED_BINARIES
            and any(fnmatch.fnmatchcase(os.path.basename(p), pat) for pat in FORBIDDEN_TRACKED_PATTERNS)
        )
        self.assertEqual(offending, [], f"Build outputs / binaries tracked in git: {offending}")

    def test_manifest_has_no_raw_byte_payload(self):
        """The evidence manifest records only ranges, digests and metadata, never ROM bytes."""
        bad_keys = []
        long_hex = []
        p_long_hex = re.compile(r"[0-9A-Fa-f]{65,}")

        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.lower() in FORBIDDEN_MANIFEST_KEYS:
                        bad_keys.append(f"{path}.{k}")
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
            elif isinstance(node, str) and p_long_hex.search(node):
                long_hex.append(path)

        walk(self.manifest, "$")
        self.assertEqual(bad_keys, [], f"Raw-byte payload keys in manifest: {bad_keys}")
        self.assertEqual(long_hex, [], f"Hex blobs longer than a SHA-256 digest in manifest: {long_hex}")

        for entry in self.manifest.get("evidence_entries", []):
            extra = set(entry) - ALLOWED_EVIDENCE_ENTRY_KEYS
            self.assertEqual(extra, set(), f"Unexpected fields in {entry.get('evidence_id')}: {extra}")
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    # =========================================================================
    # T2 specific tests: Restart path section, labels, and coverage
    # =========================================================================

    def test_restart_path_section_content_coverage(self):
        """Section '## Restart path' exists and covers all required gating and restart logic."""
        self.assertIn("## Restart path", self.content)
        sec = self.content.split("## Restart path", 1)[1]

        # Power gate coverage
        self.assertIn("sub_fc05b962", sec)
        self.assertIn("sub_fc1284ac", sec)
        self.assertIn("sub_fc05ba56", sec)
        self.assertIn("task_Startup", sec)
        self.assertIn("StartDiskboot", sec)
        self.assertIn("0xFC05B8FC", sec)
        self.assertIn("0xFC05B90E", sec)
        self.assertIn("0xFC05BBEA", sec)
        self.assertIn("0xFC05BC04", sec)
        self.assertIn("BOOTDISK", sec)
        self.assertIn("DISKBOOT.BIN", sec)

        # Retry lockout statements per feedback item 2
        self.assertIn("no retry or lockout flag is read on the path from task_Startup to StartDiskboot", sec)
        self.assertIn("whether any other code stores or reads such a flag", sec.lower())

        # Evidenced skip conditions & branch addresses per feedback item 3
        self.assertIn("0xFC05BC0A", sec)
        self.assertIn("0xFC05BBFC", sec)
        self.assertIn("0xFC05BC1C", sec)
        self.assertIn("0xFC05BC34", sec)

        # GPIO & register meaning citations per feedback item 4
        self.assertIn("0x14E", sec)
        self.assertIn("0x14F", sec)
        self.assertIn("0x67", sec)
        self.assertIn("0xD20B099C", sec)
        self.assertIn("0x97", sec)
        self.assertIn("0x98", sec)
        self.assertIn("0x88", sec)
        self.assertIn("0x02", sec)

        # Owner observation, long press, O1 witness, and freshness per feedback item 5
        self.assertIn("O1", sec)
        self.assertIn("CONT_ATTEMPTED", sec)
        self.assertIn("FRESHNESS_UNVERIFIED", sec)
        self.assertIn("0x0035F7A0", sec)
        self.assertIn("boot_prototype.c:350", sec)

        # Observable cues list
        self.assertIn("Rear Green Status LED", sec)
        self.assertIn("Power Button Hold Duration", sec)
        self.assertIn("Playback Button", sec)
        self.assertIn("SD Card Lock Switch", sec)
        self.assertIn("Witness Inspector", sec)

    def test_restart_path_labels_strict(self):
        """Section '## Restart path' strictly follows epistemic labelling rules."""
        self.assertIn("## Restart path", self.content)
        sec = self.content.split("## Restart path", 1)[1]

        # No STATIC_VERIFIED in Restart path
        self.assertNotIn("STATIC_VERIFIED", sec)

        # No mixed/combined labels like [STATIC_VERIFIED / INFERRED] or [VERIFIED / INFERRED]
        # Check every label tag
        bracket_labels = re.findall(r"\[([A-Z0-9_\-\s/]+?)(?::[^\]]*)?\]", sec)
        self.assertGreater(len(bracket_labels), 10, "Too few labels in Restart path")
        for tag in bracket_labels:
            stripped = tag.strip()
            self.assertNotIn(
                "/",
                stripped,
                f"Combined label '{stripped}' found in Restart path (split into separate claims)",
            )
            self.assertIn(
                stripped,
                {"VERIFIED", "INFERRED", "UNKNOWN"},
                f"Invalid label type '{stripped}' in Restart path",
            )

    def test_restart_path_all_cited_rom_addresses_covered(self):
        """Every 0xFC...... and 0xFD...... address cited in '## Restart path' falls inside a manifest range."""
        self.assertIn("## Restart path", self.content)
        sec = self.content.split("## Restart path", 1)[1]

        entries = self.manifest.get("evidence_entries", [])
        ranges = [(int(e["start_address"], 16), int(e["end_address"], 16), e["evidence_id"]) for e in entries]

        rom_addrs = set(re.findall(r"(?i)\b0xF[CD][0-9A-F]{6}\b", sec))
        self.assertGreater(len(rom_addrs), 20, "Too few ROM addresses found in Restart path")

        uncovered = []
        for addr_str in sorted(rom_addrs, key=lambda x: int(x, 16)):
            val = int(addr_str, 16)
            if not any(s <= val <= e for s, e, _ in ranges):
                uncovered.append(addr_str)

        self.assertEqual(
            uncovered,
            [],
            f"Uncovered ROM addresses found in Restart path: {uncovered}",
        )

    def test_t2_manifest_quota_and_slice_bounds(self):
        """T2 manifest entries meet quota (total <= 32 KiB) and max slice (<= 4 KiB)."""
        entries_by_id = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        t2_bytes = 0
        for eid in APPROVED_ENTRIES_T2:
            self.assertIn(eid, entries_by_id, f"T2 entry '{eid}' missing from manifest")
            count = entries_by_id[eid]["expected_byte_count"]
            self.assertLessEqual(count, 4096, f"T2 entry '{eid}' exceeds 4 KiB: {count} B")
            t2_bytes += count

        self.assertLessEqual(t2_bytes, 32768, f"Total T2 bytes exceed 32 KiB: {t2_bytes} B")


if __name__ == "__main__":
    unittest.main()
