#!/usr/bin/env python3
"""PORT-29 T1 Evidence and Manifest Verification Test Suite.

Verifies:
1. evidence/port29_manifest.json and evidence/port29_trusted_scopes.json exist.
2. port11c_evidence_validator.py validates the manifest against trusted scopes with 0 errors (no --allow-overlap).
3. No two manifest ranges overlap.
4. Every range in the manifest is <= 4 KiB (4,096 bytes).
5. Every range in the manifest falls inside the authorized list from PORT-27 / PORT-28.
6. Slices match exact byte hashes against PRIMARY.BIN (with manifest safety gate prior to seek/read).
7. PORT-29 artifacts contain no binary or ROM blobs, and no forbidden binaries/build outputs are tracked in git.
8. docs/PORT29_CREATETASK_EVIDENCE.md contains required tables, citations, and verdict.
"""

import fnmatch
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "evidence" / "port29_manifest.json"
SCOPES_PATH = PROJECT_ROOT / "evidence" / "port29_trusted_scopes.json"
EVIDENCE_DOC_PATH = PROJECT_ROOT / "docs" / "PORT29_CREATETASK_EVIDENCE.md"
ROM_PATH = PROJECT_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN"
ROM_BASE = 0xFC000000

# Exact authorized outer ranges from docs/PORT27_RESIDENT_CANDIDATE.md §3 and docs/PORT28_PORT27_OUTCOME.md §4.2-4.3
AUTHORIZED_RANGES = {
    "PORT29-ROM-N1": (0xFC31B408, 0xFC31B507, 256),
    "PORT29-ROM-N3": (0xFCEEF5C0, 0xFCEEF7BF, 512),
    "PORT29-ROM-N4": (0xFCEEF760, 0xFCEEF9C3, 612),  # Full authorized window in PORT27/PORT28
    "PORT29-ROM-N5": (0xFCEF28B0, 0xFCEF29AF, 256),
    "PORT29-ROM-CREATETASK": (0xFCEF3488, 0xFCEF34F9, 114),
    "PORT29-ROM-N6": (0xFCEF3A20, 0xFCEF3A5F, 64),
}

# Exact non-overlapping entries declared in evidence/port29_manifest.json
# Note: N4 authorized start is 0xFCEEF760; narrowed to 0xFCEEF7C0..0xFCEEF9C3 (516 B) to eliminate
# overlap with N3 (0xFCEEF760..0xFCEEF7BF, 96 B). Overlapping prefix bytes are hashed under N3.
EXPECTED_MANIFEST_ENTRIES = {
    "PORT29-ROM-N1": (0xFC31B408, 0xFC31B507, 256),
    "PORT29-ROM-N3": (0xFCEEF5C0, 0xFCEEF7BF, 512),
    "PORT29-ROM-N4": (0xFCEEF7C0, 0xFCEEF9C3, 516),
    "PORT29-ROM-N5": (0xFCEF28B0, 0xFCEF29AF, 256),
    "PORT29-ROM-CREATETASK": (0xFCEF3488, 0xFCEF34F9, 114),
    "PORT29-ROM-N6": (0xFCEF3A20, 0xFCEF3A5F, 64),
}


class TestPort29Evidence(unittest.TestCase):
    """Test suite for PORT-29 T1 evidence manifest, scopes, and documentation."""

    def test_files_exist(self) -> None:
        """Verify manifest and trusted scopes files exist at expected locations."""
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing manifest at {MANIFEST_PATH}")
        self.assertTrue(SCOPES_PATH.is_file(), f"Missing scopes at {SCOPES_PATH}")
        self.assertTrue(EVIDENCE_DOC_PATH.is_file(), f"Missing evidence doc at {EVIDENCE_DOC_PATH}")

    def test_validator_execution(self) -> None:
        """Verify port11c_evidence_validator.py reports VALID with 0 errors without --allow-overlap."""
        validator_script = PROJECT_ROOT / "tools" / "port11c_evidence_validator.py"
        self.assertTrue(validator_script.is_file())

        cmd = [
            "python3",
            "-B",
            str(validator_script),
            "--manifest",
            str(MANIFEST_PATH),
            "--trusted-scopes",
            str(SCOPES_PATH),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0, f"Validator failed with exit {proc.returncode}: {proc.stderr}")
        self.assertIn("Result: VALID (0 errors, 0 warnings)", proc.stdout)
        self.assertIn("Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED", proc.stdout)

    def test_no_overlapping_manifest_ranges(self) -> None:
        """Verify that no two manifest entries overlap in address range."""
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        ranges = []
        for entry in manifest.get("evidence_entries", []):
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            ranges.append((start, end, entry["evidence_id"]))
        ranges.sort()
        for i in range(len(ranges) - 1):
            s1, e1, id1 = ranges[i]
            s2, e2, id2 = ranges[i + 1]
            self.assertLessEqual(
                e1,
                s2 - 1,
                f"Overlap detected between {id1} (0x{s1:08X}..0x{e1:08X}) and {id2} (0x{s2:08X}..0x{e2:08X})",
            )

    def _validate_manifest_safety(self, manifest_path: Path) -> dict:
        """Validate every manifest entry against authorized list and 4 KiB limit before any ROM read."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        entries = manifest.get("evidence_entries", [])
        self.assertEqual(len(entries), 6, "Expected exactly 6 evidence entries in manifest")

        total_bytes = 0
        for entry in entries:
            eid = entry.get("evidence_id")
            self.assertIn(eid, EXPECTED_MANIFEST_ENTRIES, f"Unexpected evidence entry: {eid}")
            self.assertIn(eid, AUTHORIZED_RANGES, f"Unauthorized evidence entry: {eid}")

            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            byte_count = entry["expected_byte_count"]
            span = end - start + 1

            self.assertEqual(byte_count, span, f"{eid}: span {span} != byte_count {byte_count}")
            self.assertLessEqual(byte_count, 4096, f"{eid}: byte count {byte_count} exceeds 4 KiB")

            # Check that range falls completely inside the authorized window from PORT27/PORT28
            auth_start, auth_end, _ = AUTHORIZED_RANGES[eid]
            self.assertGreaterEqual(start, auth_start, f"{eid}: start {hex(start)} < authorized {hex(auth_start)}")
            self.assertLessEqual(end, auth_end, f"{eid}: end {hex(end)} > authorized {hex(auth_end)}")

            # Check exact expected non-overlapping manifest parameters
            exp_start, exp_end, exp_count = EXPECTED_MANIFEST_ENTRIES[eid]
            self.assertEqual(start, exp_start, f"{eid}: start {hex(start)} != {hex(exp_start)}")
            self.assertEqual(end, exp_end, f"{eid}: end {hex(end)} != {hex(exp_end)}")
            self.assertEqual(byte_count, exp_count, f"{eid}: count {byte_count} != {exp_count}")

            total_bytes += byte_count

        self.assertLessEqual(total_bytes, 4096, f"Total bytes {total_bytes} exceeds scope limit")
        return manifest

    def test_manifest_ranges_within_budget_and_authorized(self) -> None:
        """Verify each manifest entry is <= 4 KiB and is an authorized range."""
        self._validate_manifest_safety(MANIFEST_PATH)

    def test_byte_hashes_match_primary_bin(self) -> None:
        """Verify SHA-256 hashes in manifest match exact bytes in PRIMARY.BIN.

        Enforces strict safety gate: manifest must be validated against authorized list
        and 4 KiB limit before any file seek or read on PRIMARY.BIN occurs.
        """
        manifest = self._validate_manifest_safety(MANIFEST_PATH)

        if not ROM_PATH.is_file():
            self.skipTest(f"PRIMARY.BIN not found at {ROM_PATH}")

        with open(ROM_PATH, "rb") as rom_file:
            for entry in manifest.get("evidence_entries", []):
                eid = entry["evidence_id"]
                start = int(entry["start_address"], 16)
                byte_count = entry["expected_byte_count"]
                exp_sha256 = entry["sha256"].lower()

                offset = start - ROM_BASE
                rom_file.seek(offset)
                data = rom_file.read(byte_count)
                self.assertEqual(len(data), byte_count)

                calc_sha256 = hashlib.sha256(data).hexdigest().lower()
                self.assertEqual(
                    calc_sha256,
                    exp_sha256,
                    f"Hash mismatch for {eid}: calculated {calc_sha256} != expected {exp_sha256}",
                )

    def test_port29_files_contain_no_binary_or_rom_blobs(self) -> None:
        """Verify PORT-29 artifact files exist, are text, and contain no binary or ROM blobs."""
        port29_paths = [
            MANIFEST_PATH,
            SCOPES_PATH,
            EVIDENCE_DOC_PATH,
            PROJECT_ROOT / "tests" / "test_port29_evidence.py",
        ]
        forbidden_suffixes = {".bin", ".BIN", ".elf", ".o", ".a", ".so", ".dylib"}
        for p in port29_paths:
            self.assertTrue(p.is_file(), f"Missing PORT-29 artifact: {p}")
            self.assertNotIn(
                p.suffix,
                forbidden_suffixes,
                f"Forbidden binary artifact suffix: {p}",
            )
            self.assertLess(
                p.stat().st_size,
                500 * 1024,
                f"File unexpectedly large (>500 KiB): {p}",
            )
            content = p.read_text(encoding="utf-8")
            self.assertNotIn("\x00", content, f"NUL byte found in text file: {p}")

    def test_no_unapproved_binaries_tracked_in_git(self) -> None:
        """Verify git tracks no *.BIN or *.bin files or build outputs under repo (independent of branch diff)."""
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"git ls-files failed: {proc.stderr}")
        tracked = [p for p in proc.stdout.split("\0") if p]
        self.assertTrue(tracked, "git ls-files returned empty list")

        forbidden_patterns = ("*.bin", "*.BIN", "*.elf", "*.o", "*.a", "*.so", "*.dylib", "DISKBOOT*", "PRIMARY*")
        pre_existing_tracked_binaries = {
            "firmware/tools/witness_inspector_payload.bin",
        }
        offending = [
            p
            for p in tracked
            if p not in pre_existing_tracked_binaries
            and any(fnmatch.fnmatchcase(Path(p).name, pat) for pat in forbidden_patterns)
        ]
        self.assertEqual(offending, [], f"Forbidden binaries or build outputs tracked in git: {offending}")

    def test_evidence_document_structure_and_verdict(self) -> None:
        """Verify docs/PORT29_CREATETASK_EVIDENCE.md content requirements."""
        content = EVIDENCE_DOC_PATH.read_text(encoding="utf-8")

        # Required sections and content
        self.assertIn("PORT-29 T1", content)
        self.assertIn("0xFCEF3488", content)
        self.assertIn("0xFCEEF5C0", content)
        self.assertIn("0xFCEEF760", content)
        self.assertIn("0xFCEEF7C0", content)
        self.assertIn("r0", content)
        self.assertIn("r1", content)
        self.assertIn("r2", content)
        self.assertIn("sp[0]", content)
        self.assertIn("VERIFIED", content)
        self.assertIn("INFERRED", content)
        self.assertIn("UNKNOWN", content)

        # Exact validator command output citation
        self.assertIn(
            "Evidence Manifest Validation: 6 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED",
            content,
        )
        self.assertIn("Result: VALID (0 errors, 0 warnings)", content)

        # No --allow-overlap should be present in the doc
        self.assertNotIn("--allow-overlap", content)

        # Verdict check
        self.assertIn("Verdict", content)
        self.assertIn("NO-GO", content)

        # Verified ADR target and instruction word
        self.assertIn("0xA17A", content)
        self.assertIn("0xFCEF36A8", content)
        self.assertIn("0xBFE14C5C", content)
        self.assertNotIn("0xFCEF36A4", content)

        # activate_task local data flow table and instruction verification
        self.assertIn("0xFCEEF77E", content)
        self.assertIn("0xFCEEF79C", content)
        self.assertIn("0x4990", content)
        self.assertIn("0x9800", content)
        self.assertNotIn("never reads or modifies r1", content)
        self.assertNotIn("no access to r1", content)

    def test_instruction_words_notation_and_rom_match(self) -> None:
        """Verify instruction words cited in doc use 0xHHHH notation and match PRIMARY.BIN."""
        doc_content = EVIDENCE_DOC_PATH.read_text(encoding="utf-8")

        # Verify notation convention is stated in doc
        self.assertIn("0xHHHH", doc_content)
        self.assertIn("1.3 Instruction Word Notation Convention", doc_content)

        # Key addresses and expected halfword tuples in execution order
        key_instructions = {
            0xFCEF3488: (0xE92D, 0x43FE),
            0xFCEF34B8: (0x22A0,),
            0xFCEF34BC: (0xA17A,),
            0xFCEF34BE: (0xF7FF, 0xEA02),
            0xFCEEF764: (0xF04F, 0x34FF),
            0xFCEEF9B8: (0x80F0, 0x0000),
        }

        # Check that the document contains each cited instruction word in 0xHHHH form
        for addr, words in key_instructions.items():
            formatted = " ".join(f"0x{w:04X}" for w in words)
            self.assertIn(
                formatted,
                doc_content,
                f"Expected instruction word {formatted} at 0x{addr:08X} cited in doc",
            )

        if not ROM_PATH.is_file():
            self.skipTest(f"PRIMARY.BIN not found at {ROM_PATH}")

        # Safety gate: validate manifest entries before reading ROM
        self._validate_manifest_safety(MANIFEST_PATH)

        with open(ROM_PATH, "rb") as f:
            for addr, words in key_instructions.items():
                offset = addr - ROM_BASE
                f.seek(offset)
                raw = f.read(len(words) * 2)
                self.assertEqual(len(raw), len(words) * 2)
                actual_words = struct.unpack(f"<{len(words)}H", raw)
                self.assertEqual(
                    actual_words,
                    words,
                    f"Instruction word mismatch at 0x{addr:08X}: actual {actual_words} != expected {words}",
                )


if __name__ == "__main__":
    unittest.main()
