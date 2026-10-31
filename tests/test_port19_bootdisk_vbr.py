#!/usr/bin/env python3
"""PORT-19 T2: Unit tests for GM1.10C BOOTDISK VBR marker offset verification (P3).

Verifies:
1. docs/PORT19_BOOTDISK_VBR.md states exactly one answer per filesystem type:
   - FAT16: 0x40 (64 dec)
   - FAT32: 0x1E0 (480 dec)
   - exFAT: UNSUPPORTED (no offset / not checked)
   - FAT12: 0x40 (64 dec)
2. docs/PORT19_BOOTDISK_VBR.md states SCRIPT marker offset:
   - FAT16: 0x1F0 (496 dec)
   - FAT32: 0x1F0 (496 dec)
   - exFAT: UNSUPPORTED (no offset / not checked)
   - FAT12: 0x1F0 (496 dec)
3. docs/PORT19_BOOTDISK_VBR.md states EOS_DEVELOP status with scoped wording:
   - VERIFIED that the inspected Mounter VBR-check routine (0xFC37A4B6-0xFC37A680,
     with helper 0xFC37B2AE-0xFC37B2C2) compares only BOOTDISK and SCRIPT and
     does not compare EOS_DEVELOP.
   - UNKNOWN whether EOS_DEVELOP is checked anywhere else in GM1.10C.
   - Fails if the document asserts global absence across the whole bootloader.
4. Separate table parsing bounded by headings:
   - Each table parsed individually between its stable heading and the next heading.
   - In each table, exactly one row per filesystem type (FAT12, FAT16, FAT32, exFAT).
   - In-memory negative mutation tests ensure mutations (a), (b), (c), and global overclaims fail.
5. docs/PORT19_BOOTDISK_VBR.md reconciles P3 conflict in docs/PORT18_OWNER_TRIAL_PLAN.md.
6. All key ROM address citations are present and properly classified (VERIFIED).
7. Evidence manifest integrity: PORT19_EVIDENCE_MANIFEST.json contains the
   PORT19-ROM-MOUNTER-VBR slice (4096 B, 0xFC37A400-0xFC37B3FF) and passes
   tools/port11c_evidence_validator.py without errors.
8. Spatial non-overlap invariants: BOOTDISK and SCRIPT markers do not collide on FAT16/FAT32.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT19_BOOTDISK_VBR.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT19_EVIDENCE_MANIFEST.json"
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"

# Pinned offset constants verified in GM1.10C ROM Mounter.c (0xFC37A4B6..0xFC37B3A8)
PINNED_BOOTDISK_OFFSET_FAT16 = 0x40
PINNED_BOOTDISK_OFFSET_FAT32 = 0x1E0
PINNED_BOOTDISK_OFFSET_FAT12 = 0x40
PINNED_BOOTDISK_STRING = "BOOTDISK"
PINNED_BOOTDISK_LEN = 8

PINNED_SCRIPT_OFFSET_FAT16 = 0x1F0
PINNED_SCRIPT_OFFSET_FAT32 = 0x1F0
PINNED_SCRIPT_OFFSET_FAT12 = 0x1F0
PINNED_SCRIPT_STRING = "SCRIPT"
PINNED_SCRIPT_LEN = 6

VBR_SECTOR_SIZE = 512
VBR_SIGNATURE_OFFSET = 0x1FE


def parse_markdown_table(table_text: str) -> list[dict[str, str]]:
    """Parse a markdown table into a list of row dicts keyed by normalized header name."""
    lines = [line.strip() for line in table_text.strip().splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        raise ValueError(f"Table must have header and separator, got {len(lines)} lines")

    headers = [c.strip().replace("`", "").strip("*").strip() for c in lines[0].split("|")[1:-1]]

    rows = []
    for line in lines[2:]:  # skip header and separator (|---|---|...)
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) != len(headers):
            raise ValueError(f"Row column count {len(cols)} mismatch with header {len(headers)}: {line}")
        row_dict = {headers[i]: cols[i] for i in range(len(headers))}
        rows.append(row_dict)
    return rows


def validate_bootdisk_vbr_doc(doc_text: str) -> dict[str, Any]:
    """Validate and pin the VBR marker tables and statements in docs/PORT19_BOOTDISK_VBR.md.

    Parses each answer table bounded by its heading and the next heading,
    asserting exactly one row per filesystem type with exact offset/status,
    verification label, and ROM address citation.

    Raises ValueError if any assertion, structural invariant, or scoped claim fails.
    """
    expected_fs = {"FAT12", "FAT16", "FAT32", "exFAT"}

    # 1. Bounded extraction of Section 1.2 (BOOTDISK marker table)
    bootdisk_match = re.search(
        r"###\s*1\.2\s+Stated Answers per Filesystem Type:\s*BOOTDISK Marker\s*\n(.*?)(?=###\s*1\.3)",
        doc_text,
        re.DOTALL,
    )
    if not bootdisk_match:
        raise ValueError("Could not find Section 1.2 (BOOTDISK Marker) bounded by Section 1.3")
    bootdisk_section = bootdisk_match.group(1)
    bootdisk_rows = parse_markdown_table(bootdisk_section)

    bootdisk_fs_list = [r["Filesystem Type"].replace("*", "").strip() for r in bootdisk_rows]
    if len(bootdisk_fs_list) != len(set(bootdisk_fs_list)):
        raise ValueError(f"Duplicate filesystem type in BOOTDISK table: {bootdisk_fs_list}")
    if set(bootdisk_fs_list) != expected_fs:
        raise ValueError(f"BOOTDISK table filesystems {set(bootdisk_fs_list)} != {expected_fs}")
    if len(bootdisk_rows) != 4:
        raise ValueError(f"BOOTDISK table must have exactly 4 rows, found {len(bootdisk_rows)}")

    bootdisk_by_fs = {r["Filesystem Type"].replace("*", "").strip(): r for r in bootdisk_rows}

    # Pin BOOTDISK values:
    # FAT16: 0x40
    fat16_bd = bootdisk_by_fs["FAT16"]
    if "0x40" not in fat16_bd["BOOTDISK Marker Offset"] or "0x1E0" in fat16_bd["BOOTDISK Marker Offset"] or "UNSUPPORTED" in fat16_bd["BOOTDISK Marker Offset"]:
        raise ValueError(f"FAT16 BOOTDISK offset must be 0x40, got: {fat16_bd['BOOTDISK Marker Offset']}")
    if "VERIFIED" not in fat16_bd["Status & Classification"]:
        raise ValueError(f"FAT16 BOOTDISK status must be VERIFIED, got: {fat16_bd['Status & Classification']}")
    if "0xFC37A63A" not in fat16_bd["ROM Address Citations"] and "0xFC37A650" not in fat16_bd["ROM Address Citations"]:
        raise ValueError(f"FAT16 BOOTDISK citations missing required address: {fat16_bd['ROM Address Citations']}")

    # FAT32: 0x1E0
    fat32_bd = bootdisk_by_fs["FAT32"]
    if "0x1E0" not in fat32_bd["BOOTDISK Marker Offset"] or "0x40" in fat32_bd["BOOTDISK Marker Offset"] or "UNSUPPORTED" in fat32_bd["BOOTDISK Marker Offset"]:
        raise ValueError(f"FAT32 BOOTDISK offset must be 0x1E0, got: {fat32_bd['BOOTDISK Marker Offset']}")
    if "VERIFIED" not in fat32_bd["Status & Classification"]:
        raise ValueError(f"FAT32 BOOTDISK status must be VERIFIED, got: {fat32_bd['Status & Classification']}")
    if "0xFC37A606" not in fat32_bd["ROM Address Citations"] and "0xFC37A5FA" not in fat32_bd["ROM Address Citations"]:
        raise ValueError(f"FAT32 BOOTDISK citations missing required address: {fat32_bd['ROM Address Citations']}")

    # exFAT: UNSUPPORTED / not checked (no offset)
    exfat_bd = bootdisk_by_fs["exFAT"]
    if "UNSUPPORTED" not in exfat_bd["BOOTDISK Marker Offset"] and "not checked" not in exfat_bd["BOOTDISK Marker Offset"].lower():
        raise ValueError(f"exFAT BOOTDISK must be UNSUPPORTED / not checked, got: {exfat_bd['BOOTDISK Marker Offset']}")
    if any(valid_off in exfat_bd["BOOTDISK Marker Offset"] for valid_off in ["0x40", "0x1E0", "0x1F0"]):
        raise ValueError(f"exFAT BOOTDISK must not contain a supported offset: {exfat_bd['BOOTDISK Marker Offset']}")
    if "VERIFIED" not in exfat_bd["Status & Classification"]:
        raise ValueError(f"exFAT BOOTDISK status must be VERIFIED, got: {exfat_bd['Status & Classification']}")
    if "0xFC37A4CE" not in exfat_bd["ROM Address Citations"] and "0xFC37A55C" not in exfat_bd["ROM Address Citations"]:
        raise ValueError(f"exFAT BOOTDISK citations missing required address: {exfat_bd['ROM Address Citations']}")

    # FAT12: 0x40
    fat12_bd = bootdisk_by_fs["FAT12"]
    if "0x40" not in fat12_bd["BOOTDISK Marker Offset"] or "0x1E0" in fat12_bd["BOOTDISK Marker Offset"] or "UNSUPPORTED" in fat12_bd["BOOTDISK Marker Offset"]:
        raise ValueError(f"FAT12 BOOTDISK offset must be 0x40, got: {fat12_bd['BOOTDISK Marker Offset']}")
    if "VERIFIED" not in fat12_bd["Status & Classification"]:
        raise ValueError(f"FAT12 BOOTDISK status must be VERIFIED, got: {fat12_bd['Status & Classification']}")
    if "0xFC37A63E" not in fat12_bd["ROM Address Citations"] and "0xFC37A650" not in fat12_bd["ROM Address Citations"]:
        raise ValueError(f"FAT12 BOOTDISK citations missing required address: {fat12_bd['ROM Address Citations']}")

    # 2. Bounded extraction of Section 1.3 (SCRIPT marker table)
    script_match = re.search(
        r"###\s*1\.3\s+Secondary Marker:\s*SCRIPT Marker[^\n]*\n(.*?)(?=###\s*1\.4)",
        doc_text,
        re.DOTALL,
    )
    if not script_match:
        raise ValueError("Could not find Section 1.3 (SCRIPT Marker) bounded by Section 1.4")
    script_section = script_match.group(1)
    script_rows = parse_markdown_table(script_section)

    script_fs_list = [r["Filesystem Type"].replace("*", "").strip() for r in script_rows]
    if len(script_fs_list) != len(set(script_fs_list)):
        raise ValueError(f"Duplicate filesystem type in SCRIPT table: {script_fs_list}")
    if set(script_fs_list) != expected_fs:
        raise ValueError(f"SCRIPT table filesystems {set(script_fs_list)} != {expected_fs}")
    if len(script_rows) != 4:
        raise ValueError(f"SCRIPT table must have exactly 4 rows, found {len(script_rows)}")

    script_by_fs = {r["Filesystem Type"].replace("*", "").strip(): r for r in script_rows}

    # Pin SCRIPT values:
    for fs in ["FAT16", "FAT32", "FAT12"]:
        sc = script_by_fs[fs]
        if "0x1F0" not in sc["SCRIPT Marker Offset"] or "0x1E0" in sc["SCRIPT Marker Offset"] or "0x40" in sc["SCRIPT Marker Offset"] or "UNSUPPORTED" in sc["SCRIPT Marker Offset"]:
            raise ValueError(f"{fs} SCRIPT offset must be 0x1F0, got: {sc['SCRIPT Marker Offset']}")
        if "VERIFIED" not in sc["Status & Classification"]:
            raise ValueError(f"{fs} SCRIPT status must be VERIFIED, got: {sc['Status & Classification']}")
        if "0xFC37A668" not in sc["ROM Address Citations"] and "0xFC37A66C" not in sc["ROM Address Citations"]:
            raise ValueError(f"{fs} SCRIPT citations missing required address: {sc['ROM Address Citations']}")

    # exFAT: UNSUPPORTED / not checked (no offset)
    exfat_sc = script_by_fs["exFAT"]
    if "UNSUPPORTED" not in exfat_sc["SCRIPT Marker Offset"] and "not checked" not in exfat_sc["SCRIPT Marker Offset"].lower():
        raise ValueError(f"exFAT SCRIPT must be UNSUPPORTED / not checked, got: {exfat_sc['SCRIPT Marker Offset']}")
    if any(valid_off in exfat_sc["SCRIPT Marker Offset"] for valid_off in ["0x40", "0x1E0", "0x1F0"]):
        raise ValueError(f"exFAT SCRIPT must not contain a supported offset: {exfat_sc['SCRIPT Marker Offset']}")
    if "VERIFIED" not in exfat_sc["Status & Classification"]:
        raise ValueError(f"exFAT SCRIPT status must be VERIFIED, got: {exfat_sc['Status & Classification']}")
    if "0xFC37A4D0" not in exfat_sc["ROM Address Citations"] and "0xFC37A55C" not in exfat_sc["ROM Address Citations"]:
        raise ValueError(f"exFAT SCRIPT citations missing required address: {exfat_sc['ROM Address Citations']}")

    # 3. Bounded extraction of Section 1.4 (EOS_DEVELOP statement / table)
    eos_match = re.search(
        r"###\s*1\.4\s+Other Markers:\s*EOS_DEVELOP[^\n]*\n(.*?)(?=\n---\s*\n|\n##\s*2\.)",
        doc_text,
        re.DOTALL,
    )
    if not eos_match:
        raise ValueError("Could not find Section 1.4 (EOS_DEVELOP) bounded by Section 2 / separator")
    eos_section = eos_match.group(1)

    # Scoped verification requirement:
    scoped_pattern = re.compile(
        r"VERIFIED.*?(?:Mounter|0xFC37A4B6).*?(?:BOOTDISK\s+and\s+SCRIPT|compares\s+only).*?EOS_DEVELOP",
        re.IGNORECASE | re.DOTALL,
    )
    if not scoped_pattern.search(eos_section):
        raise ValueError("Section 1.4 must state VERIFIED for the inspected Mounter routine comparing only BOOTDISK and SCRIPT and not EOS_DEVELOP")

    unknown_pattern = re.compile(
        r"UNKNOWN.*?whether\s+(?:[`\"]?EOS_DEVELOP[`\"]?)\s+is\s+checked\s+anywhere\s+else\s+in\s+GM1\.10C",
        re.IGNORECASE,
    )
    if not unknown_pattern.search(eos_section):
        raise ValueError("Section 1.4 must state UNKNOWN whether EOS_DEVELOP is checked anywhere else in GM1.10C")

    # Disassembled address range citation in Section 1.4
    if "0xFC37A4B6" not in eos_section:
        raise ValueError("Section 1.4 must cite the disassembled Mounter routine address 0xFC37A4B6")

    # Absence of global overclaim:
    forbidden_overclaims = [
        re.compile(r"ABSENT\s*/\s*NOT\s*CHECKED\s*everywhere", re.IGNORECASE),
        re.compile(r"no\s+variant\s+(?:string\s+)?exists\s+anywhere\s+in\s+GM1\.10C", re.IGNORECASE),
        re.compile(r"not\s+checked\s+anywhere\s+in\s+GM1\.10C", re.IGNORECASE),
        re.compile(r"does\s+not\s+exist\s+anywhere\s+in\s+GM1\.10C\s+bootloader", re.IGNORECASE),
        re.compile(r"across\s+the\s+whole\s+bootloader", re.IGNORECASE),
        re.compile(r"no\s+variant\s+exists\s+in\s+GM1\.10C\s+`?Mounter\.c`?\s+or\s+bootloader", re.IGNORECASE),
    ]
    for pat in forbidden_overclaims:
        if pat.search(doc_text):
            raise ValueError(f"Document contains forbidden global absence overclaim matching pattern: {pat.pattern}")

    return {
        "bootdisk": bootdisk_by_fs,
        "script": script_by_fs,
        "eos_section": eos_section,
    }


class TestPort19BootdiskVbr(unittest.TestCase):
    """Test suite pinning GM1.10C VBR marker offsets and document assertions."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Missing required document: {DOC_PATH}")
        cls.assertTrue(MANIFEST_PATH.is_file(), f"Missing manifest: {MANIFEST_PATH}")
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")

        with open(MANIFEST_PATH, encoding="utf-8") as f:
            cls.manifest_data = json.load(f)

    def test_doc_exists_and_nonempty(self):
        """docs/PORT19_BOOTDISK_VBR.md must exist and contain substantial content."""
        self.assertGreater(len(self.doc_text), 1000, "Document content suspiciously short")

    def test_helper_validates_real_doc(self):
        """Validation helper must parse and validate real docs/PORT19_BOOTDISK_VBR.md without errors."""
        res = validate_bootdisk_vbr_doc(self.doc_text)
        self.assertIn("bootdisk", res)
        self.assertIn("script", res)
        self.assertIn("eos_section", res)

    def test_stated_bootdisk_table_pinned(self):
        """Verify that docs/PORT19_BOOTDISK_VBR.md BOOTDISK table contains exactly 1 row per fs with pinned offsets."""
        parsed = validate_bootdisk_vbr_doc(self.doc_text)
        bootdisk = parsed["bootdisk"]

        # Exactly 4 filesystem rows
        self.assertEqual(set(bootdisk.keys()), {"FAT12", "FAT16", "FAT32", "exFAT"})

        # FAT16: 0x40, VERIFIED
        self.assertIn("0x40", bootdisk["FAT16"]["BOOTDISK Marker Offset"])
        self.assertNotIn("0x1E0", bootdisk["FAT16"]["BOOTDISK Marker Offset"])
        self.assertIn("VERIFIED", bootdisk["FAT16"]["Status & Classification"])

        # FAT32: 0x1E0, VERIFIED
        self.assertIn("0x1E0", bootdisk["FAT32"]["BOOTDISK Marker Offset"])
        self.assertNotIn("0x40", bootdisk["FAT32"]["BOOTDISK Marker Offset"])
        self.assertIn("VERIFIED", bootdisk["FAT32"]["Status & Classification"])

        # exFAT: UNSUPPORTED / not checked, VERIFIED
        self.assertIn("UNSUPPORTED", bootdisk["exFAT"]["BOOTDISK Marker Offset"])
        self.assertNotIn("0x40", bootdisk["exFAT"]["BOOTDISK Marker Offset"])
        self.assertNotIn("0x1E0", bootdisk["exFAT"]["BOOTDISK Marker Offset"])
        self.assertIn("VERIFIED", bootdisk["exFAT"]["Status & Classification"])

        # FAT12: 0x40, VERIFIED
        self.assertIn("0x40", bootdisk["FAT12"]["BOOTDISK Marker Offset"])
        self.assertNotIn("0x1E0", bootdisk["FAT12"]["BOOTDISK Marker Offset"])
        self.assertIn("VERIFIED", bootdisk["FAT12"]["Status & Classification"])

    def test_stated_script_table_pinned(self):
        """Verify that SCRIPT table contains exactly 1 row per fs with pinned offsets."""
        parsed = validate_bootdisk_vbr_doc(self.doc_text)
        script = parsed["script"]

        # Exactly 4 filesystem rows
        self.assertEqual(set(script.keys()), {"FAT12", "FAT16", "FAT32", "exFAT"})

        # FAT16: 0x1F0, VERIFIED
        self.assertIn("0x1F0", script["FAT16"]["SCRIPT Marker Offset"])
        self.assertNotIn("0x1E0", script["FAT16"]["SCRIPT Marker Offset"])
        self.assertIn("VERIFIED", script["FAT16"]["Status & Classification"])

        # FAT32: 0x1F0, VERIFIED
        self.assertIn("0x1F0", script["FAT32"]["SCRIPT Marker Offset"])
        self.assertNotIn("0x1E0", script["FAT32"]["SCRIPT Marker Offset"])
        self.assertIn("VERIFIED", script["FAT32"]["Status & Classification"])

        # exFAT: UNSUPPORTED / not checked, VERIFIED
        self.assertIn("UNSUPPORTED", script["exFAT"]["SCRIPT Marker Offset"])
        self.assertNotIn("0x1F0", script["exFAT"]["SCRIPT Marker Offset"])
        self.assertIn("VERIFIED", script["exFAT"]["Status & Classification"])

        # FAT12: 0x1F0, VERIFIED
        self.assertIn("0x1F0", script["FAT12"]["SCRIPT Marker Offset"])
        self.assertNotIn("0x1E0", script["FAT12"]["SCRIPT Marker Offset"])
        self.assertIn("VERIFIED", script["FAT12"]["Status & Classification"])

    def test_eos_develop_scoped_status_pinned(self):
        """Verify EOS_DEVELOP is scoped: VERIFIED for inspected routine, UNKNOWN beyond it."""
        parsed = validate_bootdisk_vbr_doc(self.doc_text)
        eos_sec = parsed["eos_section"]

        # VERIFIED for inspected routine
        self.assertRegex(
            eos_sec,
            r"(?i)VERIFIED.*?(?:Mounter|0xFC37A4B6).*?(?:BOOTDISK\s+and\s+SCRIPT|compares\s+only).*?EOS_DEVELOP",
            "Must state VERIFIED for inspected Mounter VBR-check routine",
        )
        # UNKNOWN beyond it
        self.assertRegex(
            eos_sec,
            r"(?i)UNKNOWN.*?whether\s+(?:[`\"]?EOS_DEVELOP[`\"]?)\s+is\s+checked\s+anywhere\s+else\s+in\s+GM1\.10C",
            "Must state UNKNOWN whether EOS_DEVELOP is checked anywhere else in GM1.10C",
        )
        # Citations present
        self.assertIn("0xFC37A4B6-0xFC37A680", eos_sec)
        self.assertIn("0xFC37B2AE-0xFC37B2C2", eos_sec)

    def test_negative_mutation_duplicate_fat32_bootdisk(self):
        """Negative test (mutation a): adding a contradictory second FAT32 BOOTDISK row must fail."""
        fat32_row_marker = (
            '| **FAT32** | **`0x1E0`** (480 dec) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` |'
        )
        self.assertIn(fat32_row_marker, self.doc_text, "Anchor line for mutation A not found")

        # Duplicate row with contradictory offset
        contradictory_row = (
            '| **FAT32** | **`0x40`** (contradictory) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` | `0xFC37A606` |\n'
        )
        mutated_text = self.doc_text.replace(
            fat32_row_marker,
            f"{contradictory_row}{fat32_row_marker}",
            1,
        )
        self.assertNotEqual(mutated_text, self.doc_text)
        with self.assertRaises(ValueError) as ctx:
            validate_bootdisk_vbr_doc(mutated_text)
        self.assertIn("Duplicate filesystem type in BOOTDISK table", str(ctx.exception))

    def test_negative_mutation_exfat_script_supported(self):
        """Negative test (mutation b): changing exFAT SCRIPT to a supported offset must fail."""
        exfat_script_row = (
            '| **exFAT** | **`UNSUPPORTED`** (No offset / not checked) | None | `VERIFIED` | `0xFC37A4D0`, `0xFC37A55C` |'
        )
        self.assertIn(exfat_script_row, self.doc_text, "Anchor line for mutation B not found")

        supported_exfat_row = (
            '| **exFAT** | **`0x1F0`** (496 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A4D0`, `0xFC37A55C` |'
        )
        mutated_text = self.doc_text.replace(exfat_script_row, supported_exfat_row, 1)
        self.assertNotEqual(mutated_text, self.doc_text)
        with self.assertRaises(ValueError) as ctx:
            validate_bootdisk_vbr_doc(mutated_text)
        self.assertTrue(
            "exFAT SCRIPT must be UNSUPPORTED" in str(ctx.exception)
            or "must not contain a supported offset" in str(ctx.exception),
            f"Unexpected exception message: {ctx.exception}",
        )

    def test_negative_mutation_fat12_script_wrong_offset(self):
        """Negative test (mutation c): changing FAT12 SCRIPT to 0x1E0 must fail."""
        fat12_script_row = (
            '| **FAT12** | **`0x1F0`** (496 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A668`, `0xFC37A66C`, `0xFC37A670`, `0xFC37A67C`, `0xFC37A7F0` |'
        )
        self.assertIn(fat12_script_row, self.doc_text, "Anchor line for mutation C not found")

        wrong_fat12_row = (
            '| **FAT12** | **`0x1E0`** (480 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A668`, `0xFC37A66C`, `0xFC37A670`, `0xFC37A67C`, `0xFC37A7F0` |'
        )
        mutated_text = self.doc_text.replace(fat12_script_row, wrong_fat12_row, 1)
        self.assertNotEqual(mutated_text, self.doc_text)
        with self.assertRaises(ValueError) as ctx:
            validate_bootdisk_vbr_doc(mutated_text)
        self.assertIn("FAT12 SCRIPT offset must be 0x1F0", str(ctx.exception))

    def test_negative_mutation_eos_develop_global_overclaim(self):
        """Negative test: asserting global absence of EOS_DEVELOP must fail."""
        target = "whether `EOS_DEVELOP` is checked anywhere else in GM1.10C."
        self.assertIn(target, self.doc_text, "Anchor text for EOS_DEVELOP mutation not found")
        mutated_text = self.doc_text.replace(
            target,
            "no variant exists anywhere in GM1.10C bootloader code.",
            1,
        )
        self.assertNotEqual(mutated_text, self.doc_text)
        with self.assertRaises(ValueError) as ctx:
            validate_bootdisk_vbr_doc(mutated_text)
        self.assertTrue(
            "forbidden global absence overclaim" in str(ctx.exception)
            or "Section 1.4 must state UNKNOWN" in str(ctx.exception),
            f"Unexpected exception message: {ctx.exception}",
        )

    def test_negative_mutation_missing_filesystem_row(self):
        """Negative test: removing a required filesystem row from BOOTDISK table must fail."""
        fat16_row = (
            '| **FAT16** | **`0x40`** (64 dec) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` | `0xFC37A63A`, `0xFC37A650`, `0xFC37A654`, `0xFC37B2AE`, `0xFC37B3A8` |\n'
        )
        mutated_text = self.doc_text.replace(fat16_row, "", 1)
        self.assertNotEqual(mutated_text, self.doc_text)
        with self.assertRaises(ValueError) as ctx:
            validate_bootdisk_vbr_doc(mutated_text)
        self.assertTrue(
            "BOOTDISK table filesystems" in str(ctx.exception)
            or "BOOTDISK table must have exactly 4 rows" in str(ctx.exception)
        )

    def test_p3_conflict_reconciliation(self):
        """Verify that the document explicitly resolves the P3 conflict from PORT18 plan."""
        self.assertIn("P3", self.doc_text)
        self.assertIn("RESOLVED", self.doc_text)
        self.assertIn("0x1E0", self.doc_text)
        self.assertIn("0x40", self.doc_text)
        self.assertIn("PORT18_OWNER_TRIAL_PLAN", self.doc_text)

    def test_required_rom_citations_present(self):
        """Verify that key ROM instruction addresses and citations are documented."""
        required_citations = [
            "0xFC37A4B6",  # Mounter entry
            "0xFC37A4CE",  # is_bootdisk = 0
            "0xFC37A4D0",  # is_scriptdisk = 0
            "0xFC37A55C",  # exFAT bypass branch
            "0xFC37A606",  # FAT32 0x1E0 offset load
            "0xFC37A650",  # FAT12/16 0x40 offset load
            "0xFC37A654",  # Call to 0xFC37B2AE
            "0xFC37A668",  # SCRIPT check start
            "0xFC37A66C",  # SCRIPT 0x1F0 offset load
            "0xFC37A7F0",  # SCRIPT string literal
            "0xFC37B2AE",  # BOOTDISK strncmp helper
            "0xFC37B318",  # make_bootable sector writer
            "0xFC37B3A8",  # BOOTDISK string literal
            "0xFC05BBEA",  # StartDiskboot entry
            "0xFC05BC18",  # StartDiskboot is_bootdisk check
            "0xFC37AEA6",  # is_bootdisk getter
        ]
        for addr in required_citations:
            with self.subTest(address=addr):
                self.assertIn(
                    addr,
                    self.doc_text,
                    f"Expected ROM citation {addr} not found in docs/PORT19_BOOTDISK_VBR.md",
                )

    def test_evidence_manifest_entry(self):
        """Verify that docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json contains PORT19-ROM-MOUNTER-VBR."""
        entries = self.manifest_data.get("evidence_entries", [])
        entry_map = {e.get("evidence_id"): e for e in entries}

        self.assertIn(
            "PORT19-ROM-MOUNTER-VBR",
            entry_map,
            "Manifest missing PORT19-ROM-MOUNTER-VBR evidence entry",
        )
        entry = entry_map["PORT19-ROM-MOUNTER-VBR"]
        self.assertEqual(entry.get("firmware_revision"), "GM1.10C")
        self.assertEqual(entry.get("start_address"), "0xFC37A400")
        self.assertEqual(entry.get("end_address"), "0xFC37B3FF")
        self.assertEqual(entry.get("expected_byte_count"), 4096)
        self.assertEqual(
            entry.get("sha256"),
            "7706e4438a36a0c42aa584c994571382870d427c945240c66eec86dc02a1f65b",
        )
        self.assertEqual(entry.get("classification"), "STATIC_VERIFIED")

    def test_evidence_manifest_budget_compliance(self):
        """Total byte count in manifest must not exceed 64 KiB (65,536 bytes)."""
        entries = self.manifest_data.get("evidence_entries", [])
        total_bytes = sum(int(e.get("expected_byte_count", 0)) for e in entries)
        self.assertLessEqual(
            total_bytes,
            65536,
            f"Total bytes in manifest ({total_bytes}) exceeds 64 KiB quota (65,536 B)",
        )
        self.assertEqual(total_bytes, 8960, "Expected exactly 8,960 bytes total across T1 + T2")

    def test_evidence_validator_tool(self):
        """tools/port11c_evidence_validator.py must pass on the manifest with 0 errors."""
        res = subprocess.run(
            [sys.executable, str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Evidence validator failed with returncode {res.returncode}:\n{res.stderr}\n{res.stdout}",
        )
        output = json.loads(res.stdout)
        self.assertTrue(output.get("is_valid"), f"Manifest reported invalid: {output}")
        self.assertEqual(output.get("error_count"), 0, f"Validator found errors: {output}")

    def test_spatial_layout_invariants(self):
        """Verify spatial layout properties and non-overlap for FAT16 and FAT32."""
        # FAT32:
        bootdisk_end_fat32 = PINNED_BOOTDISK_OFFSET_FAT32 + PINNED_BOOTDISK_LEN
        script_end_fat32 = PINNED_SCRIPT_OFFSET_FAT32 + PINNED_SCRIPT_LEN

        self.assertEqual(bootdisk_end_fat32, 488)
        self.assertEqual(PINNED_SCRIPT_OFFSET_FAT32, 496)
        self.assertLessEqual(
            bootdisk_end_fat32,
            PINNED_SCRIPT_OFFSET_FAT32,
            "BOOTDISK and SCRIPT overlap on FAT32",
        )
        self.assertLessEqual(
            script_end_fat32,
            VBR_SIGNATURE_OFFSET,
            "SCRIPT overlaps VBR signature on FAT32",
        )

        # FAT16:
        bootdisk_end_fat16 = PINNED_BOOTDISK_OFFSET_FAT16 + PINNED_BOOTDISK_LEN
        script_end_fat16 = PINNED_SCRIPT_OFFSET_FAT16 + PINNED_SCRIPT_LEN

        self.assertEqual(bootdisk_end_fat16, 72)
        self.assertEqual(PINNED_SCRIPT_OFFSET_FAT16, 496)
        self.assertLessEqual(
            bootdisk_end_fat16,
            PINNED_SCRIPT_OFFSET_FAT16,
            "BOOTDISK and SCRIPT overlap on FAT16",
        )
        self.assertLessEqual(
            script_end_fat16,
            VBR_SIGNATURE_OFFSET,
            "SCRIPT overlaps VBR signature on FAT16",
        )

    def test_negative_drift_assertions(self):
        """Negative tests: verify that swapping offsets or claiming exFAT support violates assertions."""
        # 0x40 on FAT32 is inside BPB headers (wrong)
        self.assertNotEqual(PINNED_BOOTDISK_OFFSET_FAT32, 0x40)
        # 0x1E0 on FAT16 is near end of sector, not the 0x40 DOS header area (wrong)
        self.assertNotEqual(PINNED_BOOTDISK_OFFSET_FAT16, 0x1E0)
        # SCRIPT on FAT32 is at 0x1F0, not 0x1E0
        self.assertNotEqual(PINNED_SCRIPT_OFFSET_FAT32, PINNED_BOOTDISK_OFFSET_FAT32)

    def test_filesystem_type_numbers_in_rom(self):
        """Verify that document records internal DryOS filesystem type numbering."""
        for t in [1, 2, 3, 4]:
            self.assertRegex(
                self.doc_text,
                rf"(?i)type\s*=?\s*{t}",
                f"Document must record DryOS filesystem type {t}",
            )


if __name__ == "__main__":
    unittest.main()
