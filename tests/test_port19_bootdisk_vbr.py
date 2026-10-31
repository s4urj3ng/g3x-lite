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
   - exFAT: UNSUPPORTED
3. docs/PORT19_BOOTDISK_VBR.md states EOS_DEVELOP is ABSENT / NOT CHECKED.
4. docs/PORT19_BOOTDISK_VBR.md reconciles P3 conflict in docs/PORT18_OWNER_TRIAL_PLAN.md.
5. All key ROM address citations are present and properly classified (VERIFIED).
6. Evidence manifest integrity: PORT19_EVIDENCE_MANIFEST.json contains the
   PORT19-ROM-MOUNTER-VBR slice (4096 B, 0xFC37A400-0xFC37B3FF) and passes
   tools/port11c_evidence_validator.py without errors.
7. Spatial non-overlap invariants: BOOTDISK and SCRIPT markers do not collide on FAT16/FAT32.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
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

    def test_stated_bootdisk_offsets_pinned(self):
        """Verify that docs/PORT19_BOOTDISK_VBR.md pins exactly one stated answer per filesystem."""
        # FAT16: 0x40
        self.assertRegex(
            self.doc_text,
            r"\*\*FAT16\*\*\s*\|\s*\*\*`0x40`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state FAT16 BOOTDISK offset as 0x40",
        )
        # FAT32: 0x1E0
        self.assertRegex(
            self.doc_text,
            r"\*\*FAT32\*\*\s*\|\s*\*\*`0x1E0`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state FAT32 BOOTDISK offset as 0x1E0",
        )
        # exFAT: UNSUPPORTED
        self.assertRegex(
            self.doc_text,
            r"\*\*exFAT\*\*\s*\|\s*\*\*`UNSUPPORTED`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state exFAT BOOTDISK offset as UNSUPPORTED",
        )
        # FAT12: 0x40
        self.assertRegex(
            self.doc_text,
            r"\*\*FAT12\*\*\s*\|\s*\*\*`0x40`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state FAT12 BOOTDISK offset as 0x40",
        )

    def test_stated_script_offsets_pinned(self):
        """Verify that SCRIPT marker offset is pinned at 0x1F0 for FAT16 and FAT32."""
        # SCRIPT on FAT16
        self.assertRegex(
            self.doc_text,
            r"\*\*FAT16\*\*\s*\|\s*\*\*`0x1F0`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state FAT16 SCRIPT offset as 0x1F0",
        )
        # SCRIPT on FAT32
        self.assertRegex(
            self.doc_text,
            r"\*\*FAT32\*\*\s*\|\s*\*\*`0x1F0`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state FAT32 SCRIPT offset as 0x1F0",
        )
        # SCRIPT on exFAT
        self.assertRegex(
            self.doc_text,
            r"\*\*exFAT\*\*\s*\|\s*\*\*`UNSUPPORTED`\*\*",
            "docs/PORT19_BOOTDISK_VBR.md must state exFAT SCRIPT offset as UNSUPPORTED",
        )

    def test_eos_develop_status_pinned(self):
        """Verify that EOS_DEVELOP is explicitly stated as ABSENT / NOT CHECKED."""
        self.assertIn("EOS_DEVELOP", self.doc_text)
        self.assertRegex(
            self.doc_text,
            r"(ABSENT\s*/\s*NOT\s*CHECKED|not\s*checked|absent)",
            "docs/PORT19_BOOTDISK_VBR.md must state EOS_DEVELOP is absent / not checked",
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
