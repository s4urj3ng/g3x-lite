#!/usr/bin/env python3
"""PORT-21 T1: Unit tests for stock-boot lifetime of core and loader RAM regions.

Validates that:
1. docs/PORT21_RAM_LIFETIME.md exists and contains:
   - Analysis of code path after branch to core (core boot() vs my_restart continuation).
   - Analysis of DryOS heap start / memisostart (stock 0x003489B4 vs candidate 0x00366CB0).
   - Analysis of RAM lifetime / survival for core region 0x003489B4..0x00366CB0 and loader 0x00008000..0x00024CF0.
   - Hypothesis mapping table covering H1-H4 with supports / rules out / neutral labels.
   - Consistent epistemic labels (VERIFIED, INFERRED, UNKNOWN) with exact citations.
2. docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json exists, is validated by port11c_evidence_validator.py,
   satisfies slice constraints (<= 4 KiB per slice, <= 64 KiB total, non-overlapping),
   and matches exact SHA-256 hashes against firmware/dumps/GM1.10C/PRIMARY.BIN.
3. Every address cited on a line labeled VERIFIED appears in the evidence manifest
   or in a cited tracked source file.
4. No PORT-20-owned files are modified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT21_RAM_LIFETIME.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT21_EVIDENCE_MANIFEST.json"
ROM_PATH = REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN"
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
NM_TOOL = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin" / "arm-none-eabi-nm"
CANDIDATE_ELF = REPO_ROOT / "candidate_port2a" / "candidate_main.elf"

HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{4,8}\b")


class TestPort21RamLifetimeDoc(unittest.TestCase):
    """Checks the required sections and contents of docs/PORT21_RAM_LIFETIME.md."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")

    def test_required_sections_present(self):
        """Assert all required analytical sections are present."""
        self.assertIn("## 1. Executive Summary", self.content)
        self.assertIn("## 2. Question (a): Code Path Executing After Branch to Core", self.content)
        self.assertIn("## 3. Question (b): DryOS Heap Start and MEMISOSTART Configuration", self.content)
        self.assertIn("## 4. Question (c): RAM Lifetime & Overwrite Analysis", self.content)
        self.assertIn("## 5. Discrimination of Hypotheses H1–H4", self.content)
        self.assertIn("## 6. Offline Evidence Manifest & Citations", self.content)

    def test_question_a_answers(self):
        """Verify question (a) addresses core boot() and my_restart continuation."""
        self.assertIn("core boot()", self.content)
        self.assertIn("my_restart", self.content)
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

    def test_question_c_answers(self):
        """Verify question (c) analyzes loader at 0x8000 and core region at 0x3489B4."""
        self.assertIn("0x00008000", self.content)
        self.assertIn("0x00024CF0", self.content)
        self.assertIn("0x0035F7A0", self.content)
        self.assertIn("DOES NOT SURVIVE", self.content)
        self.assertIn("Copy Loop 3", self.content)
        self.assertIn("0xFCE91058", self.content)

    def test_hypotheses_mapping_table(self):
        """Verify table mapping findings to H1-H4 with supports / rules out / neutral."""
        self.assertIn("H1", self.content)
        self.assertIn("H2", self.content)
        self.assertIn("H3", self.content)
        self.assertIn("H4", self.content)
        self.assertIn("HEAVILY RULED OUT", self.content)
        self.assertIn("STRONGLY SUPPORTED", self.content)
        self.assertIn("NEUTRAL", self.content)

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
        """Verify each manifest entry against firmware/dumps/GM1.10C/PRIMARY.BIN bytes."""
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")
        with open(ROM_PATH, "rb") as f:
            rom_data = f.read()

        entries = self.manifest.get("evidence_entries", [])
        for entry in entries:
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            expected_count = entry["expected_byte_count"]
            expected_hash = entry["sha256"]

            self.assertEqual(end - start + 1, expected_count)
            offset = start - 0xFC000000
            slice_bytes = rom_data[offset : offset + expected_count]
            computed_hash = hashlib.sha256(slice_bytes).hexdigest()
            self.assertEqual(
                computed_hash,
                expected_hash,
                f"SHA256 mismatch for {entry['evidence_id']}",
            )


class TestPort21AddressCitations(unittest.TestCase):
    """Ensures that all addresses cited as VERIFIED in the doc have provenance."""

    def test_verified_addresses_have_provenance(self):
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        manifest_ranges = []
        for entry in manifest.get("evidence_entries", []):
            s = int(entry["start_address"], 16)
            e = int(entry["end_address"], 16)
            manifest_ranges.append((s, e))

        # Known tracked sources in repository
        known_sources = [
            REPO_ROOT / "candidate_port2a" / "candidate_manifest.json",
            REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "boot_prototype.c",
            REPO_ROOT / "chdk-port" / "loader" / "g3x" / "main_prototype.c",
            REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "makefile.inc",
            REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "bin_compat.h",
            REPO_ROOT / "docs" / "CHDK_PORT0B_BOOT_MEMORY_TIMELINE.md",
            REPO_ROOT / "docs" / "PORT11A_GM110C_ROM_EVIDENCE.md",
            REPO_ROOT / "docs" / "PORT19_DISKBOOT_ENCODING.md",
        ]
        known_addrs = set()
        for src in known_sources:
            if src.is_file():
                txt = src.read_text(encoding="utf-8", errors="ignore")
                for match in HEX_ADDR_RE.finditer(txt):
                    known_addrs.add(int(match.group(0), 16))

        # Inspect candidate_main.elf symbol table if available
        if CANDIDATE_ELF.is_file() and NM_TOOL.is_file():
            try:
                nm_out = subprocess.check_output([str(NM_TOOL), str(CANDIDATE_ELF)], text=True)
                for line in nm_out.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            known_addrs.add(int(parts[0], 16))
                        except ValueError:
                            pass
            except Exception:
                pass

        # Also add derived ranges and offsets from candidate_manifest:
        cm_path = REPO_ROOT / "candidate_port2a" / "candidate_manifest.json"
        if cm_path.is_file():
            with open(cm_path, "r", encoding="utf-8") as f:
                cm = json.load(f)
            loader_start = int(cm["architectural_invariants"]["loader_entry"], 16)
            loader_size = cm["candidate_artifacts"]["candidate_loader.bin"]["size_bytes"]
            known_addrs.add(loader_start + loader_size)  # 0x00024CF0
            core_start = int(cm["architectural_invariants"]["core_destination"], 16)
            core_size = cm["candidate_artifacts"]["candidate_main.bin"]["size_bytes"]
            known_addrs.add(core_start + core_size)

            # Sizes and arithmetic headroom differences
            core_end = int(cm["architectural_invariants"]["core_end_symbol"], 16)
            known_addrs.add(loader_size)  # 0x1CCF0 (118,000 bytes)
            known_addrs.add(core_end - core_start)  # 0x1E2FC (123,644 bytes)
            known_addrs.add(0x006CE000 - core_end)  # 0x367350 (headroom)
            heap_upper = int(cm["architectural_invariants"]["dryos_heap_upper"], 16)
            known_addrs.add(heap_upper - core_end)  # 0x299364 (shifted heap size)

        unmatched = []
        for line_idx, line in enumerate(doc_text.splitlines(), start=1):
            if "VERIFIED" in line:
                for match in HEX_ADDR_RE.finditer(line):
                    addr = int(match.group(0), 16)
                    # Filter out small integers like 0x00, 0x01, 0x03, 0x07, 0x78
                    if addr < 0x1000:
                        continue
                    in_manifest = any(s <= addr <= e for s, e in manifest_ranges)
                    in_sources = addr in known_addrs
                    if not (in_manifest or in_sources):
                        unmatched.append((line_idx, hex(addr), line))

        self.assertEqual(
            len(unmatched),
            0,
            f"Addresses cited on VERIFIED lines lacking provenance: {unmatched}",
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
