#!/usr/bin/env python3
"""PORT-29 T1 Evidence and Manifest Verification Test Suite.

Verifies:
1. evidence/port29_manifest.json and evidence/port29_trusted_scopes.json exist.
2. port11c_evidence_validator.py validates the manifest against trusted scopes with 0 errors.
3. Every range in the manifest is <= 4 KiB (4,096 bytes).
4. Every range in the manifest falls inside the authorized list from PORT-27 / PORT-28.
5. Slices match exact byte hashes against PRIMARY.BIN (with manifest safety gate prior to seek/read).
6. Change set vs merge-base with origin/main contains only allowed paths and no binary artifacts.
7. docs/PORT29_CREATETASK_EVIDENCE.md contains required tables, citations, and verdict.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "evidence" / "port29_manifest.json"
SCOPES_PATH = PROJECT_ROOT / "evidence" / "port29_trusted_scopes.json"
EVIDENCE_DOC_PATH = PROJECT_ROOT / "docs" / "PORT29_CREATETASK_EVIDENCE.md"
ROM_PATH = PROJECT_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN"
ROM_BASE = 0xFC000000

# Exact authorized slices from docs/PORT27_RESIDENT_CANDIDATE.md §3 and docs/PORT28_PORT27_OUTCOME.md §4.2-4.3
AUTHORIZED_RANGES = {
    "PORT29-ROM-N1": (0xFC31B408, 0xFC31B507, 256),
    "PORT29-ROM-N3": (0xFCEEF5C0, 0xFCEEF7BF, 512),
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
        """Verify port11c_evidence_validator.py reports VALID with 0 errors."""
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
        self.assertIn("Result: VALID (0 errors", proc.stdout)
        self.assertIn("Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED", proc.stdout)

    def _validate_manifest_safety(self, manifest_path: Path) -> dict:
        """Validate every manifest entry against authorized list and 4 KiB limit before any ROM read."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        entries = manifest.get("evidence_entries", [])
        self.assertEqual(len(entries), 5, "Expected exactly 5 evidence entries in manifest")

        total_bytes = 0
        for entry in entries:
            eid = entry.get("evidence_id")
            self.assertIn(eid, AUTHORIZED_RANGES, f"Unauthorized evidence entry: {eid}")

            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            byte_count = entry["expected_byte_count"]
            span = end - start + 1

            self.assertEqual(byte_count, span, f"{eid}: span {span} != byte_count {byte_count}")
            self.assertLessEqual(byte_count, 4096, f"{eid}: byte count {byte_count} exceeds 4 KiB")

            exp_start, exp_end, exp_count = AUTHORIZED_RANGES[eid]
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

    def test_no_rom_bytes_or_build_artifacts_tracked(self) -> None:
        """Verify change set vs origin/main contains only allowed paths and no binary artifacts."""
        mb_proc = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if mb_proc.returncode != 0 or not mb_proc.stdout.strip():
            self.skipTest("origin/main unavailable for merge-base check")
        merge_base = mb_proc.stdout.strip()

        # Check committed changes against merge-base
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(diff_proc.returncode, 0, f"git diff failed: {diff_proc.stderr}")
        changed_paths = set(line.strip() for line in diff_proc.stdout.splitlines() if line.strip())

        # Also check uncommitted/untracked files in worktree
        status_proc = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(status_proc.returncode, 0, f"git status failed: {status_proc.stderr}")
        for line in status_proc.stdout.splitlines():
            line = line.strip()
            if line:
                changed_paths.add(line.split()[-1])

        allowed_paths = {
            "evidence/port29_manifest.json",
            "evidence/port29_trusted_scopes.json",
            "docs/PORT29_CREATETASK_EVIDENCE.md",
            "tests/test_port29_evidence.py",
        }
        for path in changed_paths:
            self.assertIn(
                path,
                allowed_paths,
                f"Unpermitted changed or untracked path: {path}",
            )

        forbidden_suffixes = {".bin", ".BIN", ".elf", ".o", ".a", ".so", ".dylib"}
        for path in changed_paths:
            p = PROJECT_ROOT / path
            self.assertNotIn(
                p.suffix,
                forbidden_suffixes,
                f"Forbidden binary artifact detected: {path}",
            )
            if p.is_file():
                self.assertLess(
                    p.stat().st_size,
                    500 * 1024,
                    f"File unexpectedly large (>500 KiB): {path}",
                )

    def test_evidence_document_structure_and_verdict(self) -> None:
        """Verify docs/PORT29_CREATETASK_EVIDENCE.md content requirements."""
        content = EVIDENCE_DOC_PATH.read_text(encoding="utf-8")

        # Required sections and content
        self.assertIn("PORT-29 T1", content)
        self.assertIn("0xFCEF3488", content)
        self.assertIn("0xFCEEF5C0", content)
        self.assertIn("r0", content)
        self.assertIn("r1", content)
        self.assertIn("r2", content)
        self.assertIn("sp[0]", content)
        self.assertIn("VERIFIED", content)
        self.assertIn("INFERRED", content)
        self.assertIn("UNKNOWN", content)

        # Exact validator command output citation
        self.assertIn(
            "Evidence Manifest Validation: 5 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED",
            content,
        )
        self.assertIn("Result: VALID (0 errors, 0 warnings)", content)

        # Verdict check
        self.assertIn("Verdict", content)
        self.assertIn("NO-GO", content)


if __name__ == "__main__":
    unittest.main()
