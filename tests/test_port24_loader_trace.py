#!/usr/bin/env python3
"""PORT-24 T1: Unit tests for loader post-prologue trace analysis.

Validates that:
1. docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:
   - Validates using tools/port11c_evidence_validator.py with 0 errors.
   - Contains all 17 approved ranges, each <= 4 KiB, and total bytes <= 32 KiB.
   - Contains no overlapping evidence slices.
   - If PRIMARY.BIN is present, slice SHA-256 digests match actual ROM dump on disk.
2. docs/PORT24_LOADER_TRACE.md:
   - File exists and contains all required core sections.
   - Lists every loader step from 0x8000 to the CHDK core and firmware hand-off.
   - Compares each step with StartDiskboot hand-off state (0x8001 Thumb, registers, stack, cache/MMU, IRQs).
   - Contains disassembly excerpts from both default and breadcrumb candidates.
   - Contains the step trace table (Steps 1 to 29) and the ranked table of steps by failure likelihood.
   - Every claim bullet, numbered list item, and table row carries an epistemic label
     ([VERIFIED], [INFERRED], or [UNKNOWN]). STATIC_VERIFIED does not appear.
   - Every ROM address cited falls strictly within an evidence entry in docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json.
     Decided by ROM base and size defined by the repo (chdk-port/platform/g3x/makefile.inc:17 and firmware/tools/extend.m:4),
     with no allow-lists or blanket exemptions.
   - Every '0xHEX = N bytes' conversion (and 'N bytes (M words)' pair) is arithmetically exact.
3. Scope integrity (stays valid after merge; independent of worktree state and branch):
   - git ls-files tracks no build outputs or ROM images (*.bin, *.BIN, *.elf, *.o, *.fir,
     DISKBOOT*, PRIMARY*), apart from the pre-existing tracked files listed below.
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
# ROM_BASE: chdk-port/platform/g3x/makefile.inc:17 (ROMBASEADDR=0xFC000000)
# ROM_SIZE: firmware/tools/extend.m:4 and docs/FIRMWARE_ACQUISITION_PLAN.md:51 (romsize = 0x2000000 / 32 MiB)
ROM_BASE = 0xFC000000
ROM_SIZE = 0x02000000
ROM_DUMP_END = ROM_BASE + ROM_SIZE
# Required ROM coverage interval: 0xFC000000..0xFFFFFFFF inclusive
ROM_COVERAGE_START = 0xFC000000
ROM_COVERAGE_END = 0xFFFFFFFF

# Canonical PORT-24 evidence entries (17 approved ranges)
APPROVED_ENTRIES = {
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
    "PORT24-ROM-VECTOR-TABLE": (
        0xFC05B47C,
        0xFC05B4B3,
        56,
        "23345164d5691b49674466f26c6eb46384c7247d2aa4c270e90dd2f934ea5a91",
    ),
}

# Disclosed out-of-scope reads from earlier attempts per task instructions;
# marked out of scope and not relied upon as evidence.
OUT_OF_SCOPE_ENTRIES: dict[str, tuple[int, int, int, str]] = {
    "PORT24-ROM-OUT-OF-SCOPE-VER": (
        0xFC54E000,
        0xFC54E0FF,
        256,
        "6828d1a977736227ecad15c6fee4b6b4bd358749a585c1b1ebcc55b7f7dec413",
    ),
    "PORT24-ROM-OUT-OF-SCOPE-PID": (
        0xFDF20200,
        0xFDF202FF,
        256,
        "19a0057d572b8040e18349f9266768b6ece0bf8e60c41591a964cca8d9bb1733",
    ),
}

# Explicit, narrow allowlist of source-level operands (literals in candidate source/build,
# where the claim is strictly about the operand value in the source code / ELF literal pool,
# not about unread ROM firmware contents).
# Each entry: address_int: (justification, file_line)
ROM_SOURCE_OPERAND_ALLOWLIST: dict[int, tuple[str, str]] = {
    # 3 Copy Source Operands from boot_prototype.c:
    0xFC05B4B4: (
        "End bound operand for vector table copy loop in sub_fc02007e and boot_prototype.c:93",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:93",
    ),
    0xFCEC854C: (
        "Literal pool operand for High RAM copy source address in boot(); claim is about the operand loaded into r0, not the unread ROM image contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:107",
    ),
    0xFCEEF24C: (
        "Literal pool operand for ATCM copy source address in boot(); claim is about the operand loaded into r0, not the unread ROM image contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:123",
    ),
    0xFCE91058: (
        "Literal pool operand for Low RAM copy source address in boot(); claim is about the operand loaded into r0, not the unread ROM image contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:134",
    ),
    # 6 Literal String Pointer Operands from boot_prototype.c:
    0xFC05B630: (
        "Literal pool pointer operand for error string 'dmSetup' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:296",
    ),
    0xFC05B638: (
        "Literal pool pointer operand for error string 'termDriverInit' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:302",
    ),
    0xFC05B648: (
        "Literal pool pointer operand for error string 'termDeviceCreate' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:309",
    ),
    0xFC05B65C: (
        "Literal pool pointer operand for error string 'stdioSetup' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:316",
    ),
    0xFC05B668: (
        "Literal pool pointer operand for error string 'stdlibSetup' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:322",
    ),
    0xFC05B674: (
        "Literal pool pointer operand for error string 'extlib_setup' in boot(); claim is about the operand loaded into r0, not ROM contents",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:328",
    ),
    # 6 Local Branch Labels in boot_prototype.c (named after ROM addresses):
    0xFC05B598: (
        "Local branch label operand loc_fc05b598 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:298",
    ),
    0xFC05B5A6: (
        "Local branch label operand loc_fc05b5a6 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:304",
    ),
    0xFC05B5B6: (
        "Local branch label operand loc_fc05b5b6 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:311",
    ),
    0xFC05B5C6: (
        "Local branch label operand loc_fc05b5c6 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:318",
    ),
    0xFC05B5D4: (
        "Local branch label operand loc_fc05b5d4 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:324",
    ),
    0xFC05B5E2: (
        "Local branch label operand loc_fc05b5e2 in boot(); operand label from source, target is prototype ELF symbol",
        "chdk-port/platform/g3x/sub/110c/boot_prototype.c:330",
    ),
    # 29 External Canon Driver Stubs from stubs_prototype.S (uncovered by manifest):
    0xFC05C5BC: (
        "Driver stub address operand stub_fc05c5bc from STUB(fc05c5bc); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:11",
    ),
    0xFC05B5EA: (
        "Driver stub address operand stub_fc05b5ea from STUB(fc05b5ea); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:12",
    ),
    0xFC05C7D4: (
        "Driver stub address operand stub_fc05c7d4 from STUB(fc05c7d4); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:16",
    ),
    0xFC05C862: (
        "Driver stub address operand stub_fc05c862 from STUB(fc05c862); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:17",
    ),
    0xFC05B794: (
        "Driver stub address operand stub_fc05b794 from STUB(fc05b794); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:18",
    ),
    0xFC05B8D8: (
        "Driver stub address operand stub_fc05b8d8 from STUB(fc05b8d8); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:19",
    ),
    0xFC05E910: (
        "Driver stub address operand stub_fc05e910 from STUB(fc05e910); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:20",
    ),
    0xFC382C8C: (
        "Driver stub address operand stub_fc382c8c from STUB(fc382c8c); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:25",
    ),
    0xFC418EEC: (
        "Driver stub address operand stub_fc418eec from STUB(fc418eec); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:29",
    ),
    0xFC0BBA02: (
        "Driver stub address operand stub_fc0bba02 from STUB(fc0bba02); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:30",
    ),
    0xFC0D046C: (
        "Driver stub address operand stub_fc0d046c from STUB(fc0d046c); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:31",
    ),
    0xFC090674: (
        "Driver stub address operand stub_fc090674 from STUB(fc090674); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:35",
    ),
    0xFC0D0472: (
        "Driver stub address operand stub_fc0d0472 from STUB(fc0d0472); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:36",
    ),
    0xFC1283D2: (
        "Driver stub address operand stub_fc1283d2 from STUB(fc1283d2); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:37",
    ),
    0xFC2A75F6: (
        "Driver stub address operand stub_fc2a75f6 from STUB(fc2a75f6); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:38",
    ),
    0xFC0D0488: (
        "Driver stub address operand stub_fc0d0488 from STUB(fc0d0488); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:39",
    ),
    0xFC127F24: (
        "Driver stub address operand stub_fc127f24 from STUB(fc127f24); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:40",
    ),
    0xFC0BB76E: (
        "Driver stub address operand stub_fc0bb76e from STUB(fc0bb76e); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:41",
    ),
    0xFC0D02DE: (
        "Driver stub address operand stub_fc0d02de from STUB(fc0d02de); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:42",
    ),
    0xFC0BB9CC: (
        "Driver stub address operand stub_fc0bb9cc from STUB(fc0bb9cc); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:43",
    ),
    0xFC0BB72A: (
        "Driver stub address operand stub_fc0bb72a from STUB(fc0bb72a); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:44",
    ),
    0xFC33319A: (
        "Driver stub address operand stub_fc33319a from STUB(fc33319a); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:46",
    ),
    0xFC0BB6FE: (
        "Driver stub address operand stub_fc0bb6fe from STUB(fc0bb6fe); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:47",
    ),
    0xFC05C4E0: (
        "Driver stub address operand stub_fc05c4e0 from STUB(fc05c4e0); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:48",
    ),
    0xFC31BFAC: (
        "Driver stub address operand stub_fc31bfac from STUB2(fc31bfac); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:52",
    ),
    0xFC31B408: (
        "Driver stub address operand stub_fc31b408 from STUB2(fc31b408); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:53",
    ),
    0xFC31B460: (
        "Driver stub address operand stub_fc31b460 from STUB2(fc31b460); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:54",
    ),
    0xFC31BBC4: (
        "Driver stub address operand stub_fc31bbc4 from STUB2(fc31bbc4); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:55",
    ),
    0xFC31B1F4: (
        "Driver stub address operand stub_fc31b1f4 from STUB2(fc31b1f4); claim is about literal pool operand in stub veneer, contents unread from ROM",
        "chdk-port/platform/g3x/sub/110c/stubs_prototype.S:56",
    ),
}

# Strict label pattern: only VERIFIED, INFERRED, UNKNOWN allowed
LABEL_PATTERN = re.compile(
    r"\[(VERIFIED|INFERRED|UNKNOWN)[^\]]*\]"
)

# Build-output / binary patterns that must never be tracked (matched against the basename).
FORBIDDEN_TRACKED_PATTERNS = ("*.bin", "*.BIN", "*.elf", "*.o", "*.fir", "DISKBOOT*", "PRIMARY*")

# Tracked before PORT-24 and outside this task's scope: the witness inspector payload
# (source firmware/tools/witness_inspector_payload.S), not a DISKBOOT candidate build output.
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
    "classification", "notes", "status", "out_of_scope", "relied_upon",
}

P_ROM_HEX = re.compile(r"\b0x([fF][c-fC-F0-9][0-9a-fA-F]{5,6})\b")
P_ROM_DISASM = re.compile(r"\b([fF][c-fC-F0-9][0-9a-fA-F]{6}):")
P_ROM_SYM = re.compile(r"\b(?:sub|loc|stub)_([fF][c-fC-F0-9][0-9a-fA-F]{6})\b", re.IGNORECASE)


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
        """All 15 approved evidence ranges are declared with exact bounds and SHA-256."""
        entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        for eid, (start, end, count, sha) in APPROVED_ENTRIES.items():
            self.assertIn(eid, entries, f"Evidence entry '{eid}' missing from manifest")
            entry = entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start)
            self.assertEqual(int(entry["end_address"], 16), end)
            self.assertEqual(entry["expected_byte_count"], count)
            self.assertEqual(entry["sha256"], sha)
            self.assertEqual(entry["classification"], "STATIC_VERIFIED")
            self.assertEqual(entry["firmware_revision"], "GM1.10C")
            self.assertEqual(entry["provenance_source"]["reference"], "firmware/dumps/GM1.10C/PRIMARY.BIN")

    def test_out_of_scope_entries_present_and_marked(self):
        """The two disclosed out-of-scope reads are recorded with out-of-scope status and not relied upon."""
        entries = {e["evidence_id"]: e for e in self.manifest.get("evidence_entries", [])}
        for eid, (start, end, count, sha) in OUT_OF_SCOPE_ENTRIES.items():
            self.assertIn(eid, entries, f"Out-of-scope entry '{eid}' missing from manifest")
            entry = entries[eid]
            self.assertEqual(int(entry["start_address"], 16), start)
            self.assertEqual(int(entry["end_address"], 16), end)
            self.assertEqual(entry["expected_byte_count"], count)
            self.assertEqual(entry["sha256"], sha)
            self.assertEqual(entry.get("classification"), "UNKNOWN")
            self.assertEqual(entry.get("status"), "out_of_scope")
            self.assertTrue(entry.get("out_of_scope"))
            self.assertFalse(entry.get("relied_upon"))
            self.assertIn("OUT-OF-SCOPE", entry.get("notes", ""))

    def test_range_and_budget_limits(self):
        """Each slice is <= 4 KiB and total budget is <= 32 KiB, matching doc byte total."""
        entries = self.manifest.get("evidence_entries", [])
        total_bytes = 0
        for entry in entries:
            count = entry["expected_byte_count"]
            self.assertLessEqual(count, 4096, f"Slice '{entry['evidence_id']}' exceeds 4 KiB limit")
            total_bytes += count
        self.assertLessEqual(total_bytes, 32768, f"Total byte count ({total_bytes}) exceeds 32 KiB budget")
        self.assertEqual(total_bytes, 5528)
        self.assertEqual(len(entries), 17)

        # Assert doc declared byte total equals manifest total
        doc_total_matches = re.findall(r"total\s+([\d,]+)\s*B", self.content)
        self.assertTrue(doc_total_matches, "Doc does not declare total byte count")
        doc_total = int(doc_total_matches[0].replace(",", ""))
        self.assertEqual(total_bytes, doc_total, f"Manifest total ({total_bytes}) != doc total ({doc_total})")

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
        """PORT24_LOADER_TRACE.md contains all required structural sections."""
        required_headers = [
            "# PORT-24 T1: Loader Post-Prologue Trace",
            "## 1. Executive Summary & Purpose",
            "## 2. StartDiskboot Hand-Off State & Environment",
            "## 3. Disassembly Excerpts of Build Candidates",
            "## 4. Comprehensive Step Trace: 0x8000 to CHDK Core and Firmware Hand-Off",
            "## 5. Summary Trace Matrix (Steps 1 to 29)",
            "## 6. Ranked Table of Failure Steps (Post-Prologue Shutdown Likelihood)",
            "## 7. Offline Evidence Manifest & Citations",
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
        """Step trace table covers all 29 distinct steps and Step 22b from 0x8000 to continuation."""
        table_section = self.content.split("## 5. Summary Trace Matrix (Steps 1 to 29)", 1)[1]
        table_section = table_section.split("## 6. Ranked Table", 1)[0]

        for step_num in range(1, 30):
            pattern = rf"\|\s*\*\*{step_num}\*\*\s*\|"
            self.assertTrue(
                re.search(pattern, table_section),
                f"Step {step_num} missing from summary trace matrix",
            )
        self.assertTrue(
            re.search(r"\|\s*\*\*22b\*\*\s*\|", table_section),
            "Step 22b missing from summary trace matrix",
        )
        self.assertIn("IC Reinit & First IRQ Unmask", table_section)

        # Check key transitional symbols
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

        # Check that every detail step in Section 4 has a Comparison line
        section4 = self.content.split("## 4. Comprehensive Step Trace", 1)[1]
        section4 = section4.split("## 5. Summary Trace Matrix", 1)[0]
        for step_num in range(1, 30):
            step_header_re = rf"-\s*\*\*Step {step_num}:"
            self.assertTrue(
                re.search(step_header_re, section4),
                f"Step {step_num} detail header missing in Section 4",
            )
        self.assertTrue(
            re.search(r"-\s*\*\*Step 22b:", section4),
            "Step 22b detail header missing in Section 4",
        )

        comparison_count = len(re.findall(r"-\s*Comparison with StartDiskboot Hand-Off:", section4, re.IGNORECASE))
        self.assertEqual(
            comparison_count,
            30,
            f"Expected exactly 30 'Comparison with StartDiskboot Hand-Off' lines in Section 4, found {comparison_count}",
        )

    def test_failure_steps_ranking_present(self):
        """Ranked table ranks candidate failure steps and identifies primary root cause."""
        ranking_section = self.content.split("## 6. Ranked Table of Failure Steps", 1)[1]
        ranking_section = ranking_section.split("## 7. Offline Evidence Manifest", 1)[0]

        for rank_num in range(1, 7):
            pattern = rf"\|\s*\*\*{rank_num}\*\*\s*\|"
            self.assertTrue(
                re.search(pattern, ranking_section),
                f"Rank {rank_num} missing from failure steps ranking table",
            )

        self.assertIn("PRIMARY ROOT CAUSE", ranking_section)
        self.assertIn("sub_fc1284ac", ranking_section)
        self.assertIn("sub_fc05ba56", ranking_section)
        self.assertIn("0xD20B099C", ranking_section)
        self.assertTrue(
            "loc_fc05b3d8" in ranking_section or "Headroom" in ranking_section,
            "Headroom verification halt loop missing from ranking table",
        )
        self.assertTrue(
            "startup" in ranking_section.lower() and "shutdown" in ranking_section.lower(),
            "startup() sanity-check/shutdown halt step missing from ranking table",
        )
        # Check Rank 4 Panic Hang from stray interrupt vs direct power cut comparison
        self.assertIn("Step 22b", ranking_section)
        self.assertIn("Illegal inter", ranking_section)
        self.assertIn("docs/RESTART_IRQ_PENDING_AUDIT.md", ranking_section)
        self.assertIn("Contrast with Direct Power Cut", ranking_section)
        self.assertIn("LED flashed, then LCD backlight off", ranking_section)
        self.assertIn("HIGH confidence", ranking_section)
        # Qualified panic-hang checks (Issue 3):
        self.assertNotIn("eventually", ranking_section.lower())
        self.assertNotIn("regardless of button", ranking_section.lower())
        self.assertIn("POSSIBLE but UNKNOWN", ranking_section)
        self.assertIn("docs/PORT23_POWER_SUPERVISION.md:211, 295-300", ranking_section)
        self.assertIn("conditional mechanism", ranking_section.lower())

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
                # Prose paragraph line
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
        """Extract all ROM addresses and check if they are covered by manifest evidence entries.

        As required by PORT-24 and reviewer feedback:
        - Covers bare disassembly addresses ('fcdead00: ...', 8 hex digits starting fc/fd/fe/ff followed by a colon).
        - Covers stub_XXXXXXXX and sub_XXXXXXXX symbols, and 0xFC...... hex addresses.
        - Any ROM address cited must fall inside an approved manifest range.
        - Operands cited from source/build only (per Point 1: 'if a target is outside every range,
          cite it from source/build only, do not add new ROM reads for it, and keep its behavior UNKNOWN')
          are verified from source/build, not unverified ROM firmware reads.
        """
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

        def is_in_source_operand_allowlist(addr_int: int) -> bool:
            return addr_int in ROM_SOURCE_OPERAND_ALLOWLIST

        source_file_line_pattern = re.compile(r"\b[\w\-\.\/]+\.(?:c|h|S):\d+\b")
        p_manifest_id = re.compile(r"\bPORT24-ROM-[A-Z0-9\-]+\b")
        p_disasm_line = re.compile(r"\b(?:0x)?[fF][c-fC-F0-9][0-9a-fA-F]{6}\s*:\s*[a-zA-Z]", re.IGNORECASE)
        p_rom_cite = re.compile(r"\bROM\s+(?:at\s+)?[`*_]*0x[0-9a-fA-F]+", re.IGNORECASE)
        p_rom_content_claim = re.compile(
            r"\b(?:ROM\s+(?:at\s+)?(?:source\s+address\s+)?(?:`?0x[0-9a-fA-F]+`?\s+)?(?:contains?|holds?)|bytes\s+at|instructions?\s+at|disassembly|reads\b|loads?\s+from\s+ROM|ROM\s+contents?|image\s+in\s+ROM)\b",
            re.IGNORECASE,
        )

        verified_rom_addrs = set()
        allowed_source_operands = set()
        uncovered_addrs = []

        for line_no, line in enumerate(lines, start=1):
            hex_matches = P_ROM_HEX.findall(line)
            disasm_matches = P_ROM_DISASM.findall(line)
            sym_matches = P_ROM_SYM.findall(line)
            all_addr_strs = set(hex_matches + disasm_matches + sym_matches)
            if not all_addr_strs:
                continue

            # Line-wide disqualification flags for allowlisted addresses:
            # (a) Any ROM disassembly line (pattern like `fcXXXXXX: <mnemonic>`)
            has_disasm_line = bool(disasm_matches) or bool(p_disasm_line.search(line))

            # (b) Any `ROM 0x...` citation claiming ROM content/address directly as evidence,
            # in any form including Markdown-wrapped `ROM \`0x...\`` or `ROM **0x...**`
            has_rom_citation = bool(p_rom_cite.search(line))

            # (c) Any manifest evidence ID (any PORT24-ROM-* identifier)
            has_manifest_id = bool(p_manifest_id.search(line))

            # (d) Any ROM content claim (e.g. 'ROM contains', 'ROM holds', 'bytes at', 'instruction at', 'disassembly', 'reads', 'loads from ROM')
            has_rom_content_claim = bool(p_rom_content_claim.search(line))

            # (e) Allowlisted addresses may be exempt ONLY when they appear as explicit
            # source-code operands or constants cited by file:line
            has_source_citation = bool(source_file_line_pattern.search(line))

            for addr_str in all_addr_strs:
                val = int(addr_str, 16)
                if not (ROM_COVERAGE_START <= val <= ROM_COVERAGE_END):
                    continue

                if is_in_evidence_entries(val):
                    verified_rom_addrs.add(f"0x{val:08X}")
                elif is_in_source_operand_allowlist(val):
                    if has_disasm_line:
                        uncovered_addrs.append(
                            f"Line {line_no}: 0x{val:08X} is allowlisted but appears on a ROM disassembly line: {line.strip()}"
                        )
                    elif has_rom_citation:
                        uncovered_addrs.append(
                            f"Line {line_no}: 0x{val:08X} is allowlisted but appears on a line with a ROM citation: {line.strip()}"
                        )
                    elif has_manifest_id:
                        uncovered_addrs.append(
                            f"Line {line_no}: 0x{val:08X} is allowlisted but appears on a line with a manifest evidence ID: {line.strip()}"
                        )
                    elif has_rom_content_claim:
                        uncovered_addrs.append(
                            f"Line {line_no}: 0x{val:08X} is allowlisted but appears on a line with a ROM content claim: {line.strip()}"
                        )
                    elif not has_source_citation:
                        uncovered_addrs.append(
                            f"Line {line_no}: 0x{val:08X} is in allowlist but lacks an explicit source file:line citation: {line.strip()}"
                        )
                    else:
                        allowed_source_operands.add(f"0x{val:08X}")
                else:
                    uncovered_addrs.append(
                        f"Line {line_no}: 0x{val:08X} lies in ROM region [0x{ROM_COVERAGE_START:08X}, 0x{ROM_COVERAGE_END:08X}] but is outside manifest evidence entries and source allowlist: {line.strip()}"
                    )

        return uncovered_addrs, verified_rom_addrs

    def test_every_cited_rom_address_covered_by_manifest_entries(self):
        """Strict coverage test: every ROM address cited in the doc must fall within
        an evidence entry declared in docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json
        unless it is an operand cited from source/build only.
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

    def test_negative_source_build_line_fails_coverage_without_allowlist(self):
        """Negative test proving that a line like 'fcdead00: bx lr [VERIFIED (source/build): unrelated.c:1]'
        now FAILS coverage because blanket 'source/build' exemptions are removed.
        """
        uncovered, _ = self.check_rom_addresses_coverage("fcdead00: bx lr [VERIFIED (source/build): unrelated.c:1]")
        self.assertTrue(
            any("FCDEAD00" in u for u in uncovered),
            f"Line with 'source/build' outside allowlist should have failed coverage: {uncovered}",
        )

    def test_negative_allowlisted_address_in_disasm_or_rom_citation_fails_coverage(self):
        """Negative tests: an allowlisted address fails coverage if on a ROM disassembly line,
        if cited as 'ROM 0x...', or if asserting a ROM-content claim outside manifest.
        """
        # Synthetic doc line 1: ROM disassembly line with ROM citation at allowlisted address
        uncovered_disasm, _ = self.check_rom_addresses_coverage(
            "fc05c5bc: bx lr [VERIFIED: ROM 0xFC05C5BC]"
        )
        self.assertTrue(
            any("FC05C5BC" in u for u in uncovered_disasm),
            f"Line 'fc05c5bc: bx lr [VERIFIED: ROM 0xFC05C5BC]' should have failed coverage: {uncovered_disasm}",
        )

        # Synthetic doc line 2: ROM content claim at an allowlisted address outside manifest
        uncovered_content, _ = self.check_rom_addresses_coverage(
            "ROM contents at 0xFC05C5BC are 0x4770 [VERIFIED: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:11]"
        )
        self.assertTrue(
            any("FC05C5BC" in u for u in uncovered_content),
            f"Line with ROM content claim at 0xFC05C5BC should have failed coverage: {uncovered_content}",
        )

        # Synthetic doc line 3: 'ROM at 0x... contains' claim at allowlisted address outside manifest
        uncovered_contains, _ = self.check_rom_addresses_coverage(
            "ROM at 0xFC05C5BC contains: bx lr [VERIFIED: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:11]"
        )
        self.assertTrue(
            any("FC05C5BC" in u for u in uncovered_contains),
            f"Line with 'ROM at ... contains' at 0xFC05C5BC should have failed coverage: {uncovered_contains}",
        )

    def test_positive_legitimate_source_operand_mention_passes_coverage(self):
        """Positive test: an allowlisted address cited legitimately as an explicit
        source-code operand with file:line and without ROM content claim passes coverage.
        """
        sample_stub_line = (
            "| `stub_fc05c5bc` (`stubs_prototype.S:11`) | `STUB` | `0x00349894: ldr.w pc, [pc]` | "
            "`0x00349898` | `0xFC05C5BC` | `1` | `Thumb` | "
            "[VERIFIED (source/build): candidate_main.elf:0x00349898; stubs_prototype.S:11; stubs_asm.h:60] "
            "[UNKNOWN: callee target unread from ROM] |"
        )
        uncovered, verified = self.check_rom_addresses_coverage(sample_stub_line)
        self.assertEqual(
            uncovered,
            [],
            f"Legitimate source-operand line failed coverage: {uncovered}",
        )

    def test_source_operand_allowlist_entries_are_justified(self):
        """Every entry in ROM_SOURCE_OPERAND_ALLOWLIST is justified and literally occurs at its cited source line."""
        for addr, (justification, file_line) in ROM_SOURCE_OPERAND_ALLOWLIST.items():
            self.assertTrue(ROM_COVERAGE_START <= addr <= ROM_COVERAGE_END, f"Invalid allowlist address: 0x{addr:08X}")
            self.assertTrue(justification and len(justification) > 10, f"Missing justification for 0x{addr:08X}")
            self.assertIn(":", file_line, f"Invalid file:line citation '{file_line}' for 0x{addr:08X}")
            rel_file, line_num_str = file_line.split(":", 1)
            self.assertTrue(
                rel_file.endswith((".c", ".h", ".S")),
                f"Allowlist citation file '{rel_file}' for 0x{addr:08X} is not a C or assembly source file",
            )
            file_path = REPO_ROOT / rel_file
            self.assertTrue(file_path.exists(), f"Allowlist citation file missing: {file_path}")
            file_lines = file_path.read_text(encoding="utf-8").splitlines()
            line_num = int(line_num_str)
            self.assertTrue(1 <= line_num <= len(file_lines), f"Line {line_num} out of bounds for {rel_file}")
            line_text = file_lines[line_num - 1]
            addr_hex = f"{addr:x}".lower()
            self.assertIn(
                addr_hex,
                line_text.lower(),
                f"Address 0x{addr:08X} does not literally occur in {rel_file} at line {line_num}: {line_text!r}",
            )

    def test_regression_unmanifested_address_with_source_citation_fails_coverage(self):
        """Regression test: an unmanifested ROM address on a line with a source file:line citation must FAIL coverage."""
        unmanifested_addr = 0xFC778899  # In ROM range, not in manifest, not in allowlist
        synthetic_line = (
            f"Candidate step references unmanifested address 0x{unmanifested_addr:08X} "
            f"as cited in chdk-port/platform/g3x/sub/110c/boot_prototype.c:100 [INFERRED]."
        )
        uncovered, verified = self.check_rom_addresses_coverage(synthetic_line)
        self.assertTrue(
            any(f"{unmanifested_addr:08X}" in u for u in uncovered),
            f"Unmanifested address 0x{unmanifested_addr:08X} with file:line citation should have failed coverage: {uncovered}",
        )

    def test_regression_allowlist_entry_with_wrong_source_line_fails(self):
        """Regression test: an allowlist entry whose source line does not contain the address must FAIL verification."""
        def verify_allowlist_entry(addr: int, file_line: str) -> bool:
            rel_file, line_num_str = file_line.split(":", 1)
            file_path = REPO_ROOT / rel_file
            if not file_path.exists():
                return False
            file_lines = file_path.read_text(encoding="utf-8").splitlines()
            line_num = int(line_num_str)
            if not (1 <= line_num <= len(file_lines)):
                return False
            line_text = file_lines[line_num - 1]
            return f"{addr:x}".lower() in line_text.lower()

        # Legitimate entry must pass
        self.assertTrue(verify_allowlist_entry(0xFC05B4B4, "chdk-port/platform/g3x/sub/110c/boot_prototype.c:93"))

        # Wrong line must fail
        self.assertFalse(verify_allowlist_entry(0xFC05B4B4, "chdk-port/platform/g3x/sub/110c/boot_prototype.c:100"))
        # Non-occurring address on line 93 must fail
        self.assertFalse(verify_allowlist_entry(0xFC999999, "chdk-port/platform/g3x/sub/110c/boot_prototype.c:93"))

    def test_regression_rom_coverage_interval_fe_and_ff_fail(self):
        """Regression test for coverage upper bound: interval is 0xFC000000..0xFFFFFFFF inclusive.
        Synthetic docs citing 0xFE123456, and separately 0xFFFFFFFF, with no manifest range must FAIL coverage.
        """
        uncovered_fe, _ = self.check_rom_addresses_coverage("Candidate cites address 0xFE123456 [UNKNOWN].")
        self.assertTrue(
            any("FE123456" in u for u in uncovered_fe),
            f"Synthetic citation of 0xFE123456 outside manifest should have failed coverage: {uncovered_fe}",
        )

        uncovered_fe_sym, _ = self.check_rom_addresses_coverage("Candidate calls symbol sub_fe123456 [UNKNOWN].")
        self.assertTrue(
            any("FE123456" in u for u in uncovered_fe_sym),
            f"Synthetic symbol sub_fe123456 outside manifest should have failed coverage: {uncovered_fe_sym}",
        )

        uncovered_ff, _ = self.check_rom_addresses_coverage("Candidate cites address 0xFFFFFFFF [UNKNOWN].")
        self.assertTrue(
            any("FFFFFFFF" in u for u in uncovered_ff),
            f"Synthetic citation of 0xFFFFFFFF outside manifest should have failed coverage: {uncovered_ff}",
        )

    def test_regression_allowlisted_address_with_rom_citation_fails(self):
        """Regression tests for line-wide ROM citation exclusion:
        (a) An allowlisted address plus a ROM citation of a different address on the same line must FAIL.
        (b) 'ROM `0xFCEC854C`' in backticks must FAIL.
        """
        # (a) Allowlisted address 0xFCEC854C paired with a ROM citation of a different address (0xFC127A62)
        line_a = "0xFCEC854C is defined in chdk-port/platform/g3x/sub/110c/boot_prototype.c:107 [VERIFIED: ROM 0xFC127A62]"
        uncovered_a, _ = self.check_rom_addresses_coverage(line_a)
        self.assertTrue(
            any("FCEC854C" in u for u in uncovered_a),
            f"Allowlisted address paired with ROM citation on same line must fail coverage: {uncovered_a}",
        )

        # (b) 'ROM `0xFCEC854C`' in backticks
        line_b = "ROM `0xFCEC854C` [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"
        uncovered_b, _ = self.check_rom_addresses_coverage(line_b)
        self.assertTrue(
            any("FCEC854C" in u for u in uncovered_b),
            f"'ROM `0xFCEC854C`' in backticks must fail coverage: {uncovered_b}",
        )

    def test_regression_odd_thumb_address_without_allowlist_entry_fails(self):
        """Regression test for Issue 1: removing addr_int & ~1 normalisation.
        An odd Thumb-bit form like 0xFCEC854D does not pass just because 0xFCEC854C is allowlisted.
        A synthetic doc line citing 0xFCEC854D with boot_prototype.c:107 citation must FAIL coverage.
        """
        synth_line = "Candidate references 0xFCEC854D [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"
        uncovered, _ = self.check_rom_addresses_coverage(synth_line)
        self.assertTrue(
            any("FCEC854D" in u for u in uncovered),
            f"Synthetic citation of 0xFCEC854D with boot_prototype.c:107 should have failed coverage: {uncovered}",
        )

    def test_regression_enforce_source_only_rule_for_allowlisted_addresses(self):
        """Regression tests for Issue 2: allowlisted addresses must be rejected when on a line with:
        (1) ROM content claim: 'At address 0xFCEC854C the ROM contains a copy image [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]'
        (2) A manifest evidence ID (PORT24-ROM-*): line mixing an allowlisted operand with a PORT24-ROM-* ID
        (3) Words indicating ROM content: 'ROM holds', 'bytes at', 'instruction at', 'disassembly', 'reads', 'loads from ROM'
        """
        # (1) Exact reviewer test sentence
        line_content = "At address 0xFCEC854C the ROM contains a copy image [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"
        uncovered_c, _ = self.check_rom_addresses_coverage(line_content)
        self.assertTrue(
            any("FCEC854C" in u for u in uncovered_c),
            f"Line with 'the ROM contains' should have failed coverage: {uncovered_c}",
        )

        # (2) Mixed allowlisted operand with PORT24-ROM-* ID
        line_mixed = "0xFCEC854C operand is verified [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107; PORT24-ROM-CACHE-HELPERS]"
        uncovered_m, _ = self.check_rom_addresses_coverage(line_mixed)
        self.assertTrue(
            any("FCEC854C" in u for u in uncovered_m),
            f"Line mixing allowlisted address with PORT24-ROM-* ID should have failed coverage: {uncovered_m}",
        )

        # (3) Other ROM content claim forms
        for wording, test_line in [
            ("ROM holds", "ROM holds data at 0xFCEC854C [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"),
            ("bytes at", "bytes at 0xFCEC854C are copied [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"),
            ("instruction at", "instruction at 0xFCEC854C executes [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"),
            ("disassembly", "disassembly of 0xFCEC854C shows veneer [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"),
            ("reads", "stub_fc05c5bc reads hardware state [VERIFIED: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:11]"),
            ("loads from ROM", "loads from ROM 0xFCEC854C [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:107]"),
        ]:
            uncovered_w, _ = self.check_rom_addresses_coverage(test_line)
            self.assertTrue(
                len(uncovered_w) > 0,
                f"Line with wording '{wording}' should have failed coverage: {uncovered_w}",
            )


    def test_offline_manifest_table_matches_json(self):
        """Offline evidence table in Section 7 matches PORT24_EVIDENCE_MANIFEST.json entries."""
        section7 = self.content.split("## 7. Offline Evidence Manifest & Citations", 1)[1]
        row_re = re.compile(
            r"\|\s*`([^`]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*`(0x[0-9A-Fa-f]+)`\s*\|\s*(\d+)\s*B\s*\|\s*`([0-9a-f]{64})`\s*\|"
        )
        cited_ranges = row_re.findall(section7)
        self.assertEqual(len(cited_ranges), len(APPROVED_ENTRIES))

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

        # The step table itself must state each copy/zero length as an exact hex/decimal pair.
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


if __name__ == "__main__":
    unittest.main()
