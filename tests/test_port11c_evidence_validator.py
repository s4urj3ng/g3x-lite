#!/usr/bin/env python3
"""PORT-11C: Unit tests for offline evidence validator.

Tests all validation rules, failure modes, security boundaries, and synthetic
byte fixtures without accessing ROM, camera hardware, or external tools.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import port11c_evidence_validator as pev  # noqa: E402
from port11c_evidence_validator import (  # noqa: E402
    ApprovedRange,
    AuthorizationScope,
    Classification,
    EvidenceEntry,
    EvidenceManifest,
    EvidenceValidator,
    ProvenanceSource,
    ProvenanceType,
    ValidationResult,
    load_manifest_file,
    load_scopes_file,
    RULE_DUPLICATE_ID,
    RULE_FIXTURE_HASH_MISMATCH,
    RULE_FIXTURE_LENGTH_MISMATCH,
    RULE_INCONSISTENT_SLICES,
    RULE_MALFORMED_RANGE,
    RULE_MISSING_SCOPE,
    RULE_OVERLAPPING_SLICES,
    RULE_SCOPE_EXCEEDED,
    RULE_SCOPE_POLICY_VIOLATION,
    RULE_TRUST_BOUNDARY_NOTICE,
    RULE_UNAPPROVED_SCOPE,
    RULE_UNSUPPORTED_PROVENANCE,
)


def make_synthetic_fixture(byte_count: int, pattern_byte: int = 0xAA) -> bytes:
    """Generate synthetic deterministic byte fixture."""
    return bytes([(pattern_byte + i) % 256 for i in range(byte_count)])


def make_valid_manifest_dict() -> dict:
    """Create a minimal valid manifest dictionary using synthetic fixtures."""
    fix1 = make_synthetic_fixture(64, 0x10)
    fix2 = make_synthetic_fixture(32, 0x20)
    sha1 = hashlib.sha256(fix1).hexdigest()
    sha2 = hashlib.sha256(fix2).hexdigest()

    return {
        "manifest_version": "1.0.0",
        "authorization_scopes": [
            {
                "scope_id": "SCOPE-SYNTHETIC-01",
                "firmware_revision": "GM1.10C",
                "approved_ranges": [
                    {
                        "start_address": "0xFC020000",
                        "end_address": "0xFC0200FF",
                        "label": "Synthetic Range A",
                    },
                    {
                        "start_address": "0xFC030000",
                        "end_address": "0xFC03007F",
                        "label": "Synthetic Range B",
                    },
                ],
                "max_bytes_total": 512,
                "allowed_classifications": ["STATIC_VERIFIED", "INFERRED"],
                "description": "Synthetic test scope",
            }
        ],
        "evidence_entries": [
            {
                "evidence_id": "SYNTH-001",
                "firmware_revision": "GM1.10C",
                "start_address": "0xFC020000",
                "end_address": "0xFC02003F",
                "expected_byte_count": 64,
                "sha256": sha1,
                "provenance_source": "SYNTHETIC_FIXTURE:test_slice_1",
                "authorization_scope_id": "SCOPE-SYNTHETIC-01",
                "classification": "STATIC_VERIFIED",
                "notes": "First synthetic slice",
            },
            {
                "evidence_id": "SYNTH-002",
                "firmware_revision": "GM1.10C",
                "start_address": "0xFC030000",
                "end_address": "0xFC03001F",
                "expected_byte_count": 32,
                "sha256": sha2,
                "provenance_source": {
                    "type": "SYNTHETIC_FIXTURE",
                    "reference": "test_slice_2",
                },
                "authorization_scope_id": "SCOPE-SYNTHETIC-01",
                "classification": "INFERRED",
                "notes": "Second synthetic slice",
            },
        ],
    }


class TestManifestParsing(unittest.TestCase):
    """Test schema parsing, address handling, and type normalization."""

    def test_valid_manifest_dict_parsed(self):
        d = make_valid_manifest_dict()
        manifest = EvidenceManifest.from_dict(d)
        self.assertEqual(manifest.manifest_version, "1.0.0")
        self.assertEqual(len(manifest.scopes), 1)
        self.assertEqual(len(manifest.entries), 2)
        e1 = manifest.entries[0]
        self.assertEqual(e1.evidence_id, "SYNTH-001")
        self.assertEqual(e1.start_hex, "0xFC020000")
        self.assertEqual(e1.end_hex, "0xFC02003F")
        self.assertEqual(e1.expected_byte_count, 64)
        self.assertEqual(e1.classification, Classification.STATIC_VERIFIED)

    def test_parse_address_range_string_syntax(self):
        d = make_valid_manifest_dict()
        del d["evidence_entries"][0]["start_address"]
        del d["evidence_entries"][0]["end_address"]
        d["evidence_entries"][0]["address_range"] = "0xFC020000..0xFC02003F"

        manifest = EvidenceManifest.from_dict(d)
        e1 = manifest.entries[0]
        self.assertEqual(e1.start_address, 0xFC020000)
        self.assertEqual(e1.end_address, 0xFC02003F)

    def test_invalid_json_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceManifest.from_json("not valid json {")

    def test_non_dict_root_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceManifest.from_json("['not', 'a', 'dict']")

    def test_missing_evidence_id_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["evidence_id"] = ""
        with self.assertRaises(ValueError):
            EvidenceManifest.from_dict(d)

    def test_invalid_classification_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["classification"] = "DEFINITELY_VERIFIED"
        with self.assertRaises(ValueError):
            EvidenceManifest.from_dict(d)


class TestValidationRules(unittest.TestCase):
    """Test individual validation rules enforced by EvidenceValidator."""

    def setUp(self):
        self.validator = EvidenceValidator(allow_overlapping_slices=False)
        self.valid_data = make_valid_manifest_dict()

    def test_valid_manifest_passes(self):
        manifest = EvidenceManifest.from_dict(self.valid_data)
        result = self.validator.validate_manifest(manifest)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_count, 0)

    # 1. Duplicate evidence ID
    def test_duplicate_evidence_id_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"].append(dict(d["evidence_entries"][0]))
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn(RULE_DUPLICATE_ID, rule_ids)

    # 2. Malformed address range
    def test_inverted_range_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["start_address"] = "0xFC020050"
        d["evidence_entries"][0]["end_address"] = "0xFC020010"
        d["evidence_entries"][0]["expected_byte_count"] = 64
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_MALFORMED_RANGE, [f.rule_id for f in result.findings])

    def test_byte_count_mismatch_rejected(self):
        d = make_valid_manifest_dict()
        # Span is 0xFC020000..0xFC02003F = 64 bytes, but claim says 128
        d["evidence_entries"][0]["expected_byte_count"] = 128
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_MALFORMED_RANGE, [f.rule_id for f in result.findings])

    def test_non_positive_byte_count_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["expected_byte_count"] = 0
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_MALFORMED_RANGE, [f.rule_id for f in result.findings])

    # 3. Provenance validation
    def test_unsupported_provenance_rejected(self):
        with self.assertRaises(ValueError):
            ProvenanceSource.parse("unverified forum rumor without category")

    def test_empty_provenance_rejected(self):
        with self.assertRaises(ValueError):
            ProvenanceSource.parse("")

    # 4. Missing authorization scope
    def test_missing_scope_id_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["authorization_scope_id"] = "   "
        with self.assertRaises(ValueError):
            EvidenceManifest.from_dict(d)

    def test_unapproved_scope_id_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][0]["authorization_scope_id"] = "SCOPE-NONEXISTENT"
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_UNAPPROVED_SCOPE, [f.rule_id for f in result.findings])

    # 5. Scope exceeded
    def test_address_outside_approved_scope_rejected(self):
        d = make_valid_manifest_dict()
        # Scope authorizes 0xFC020000..0xFC0200FF and 0xFC030000..0xFC03007F
        # Move entry to 0xFC079130 (out of scope)
        d["evidence_entries"][0]["start_address"] = "0xFC079130"
        d["evidence_entries"][0]["end_address"] = "0xFC07916F"
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_EXCEEDED, [f.rule_id for f in result.findings])

    def test_slice_extending_beyond_scope_boundary_rejected(self):
        d = make_valid_manifest_dict()
        # Scope range ends at 0xFC0200FF. Set entry start at 0xFC0200C0 and end at 0xFC02013F (extending past scope)
        d["evidence_entries"][0]["start_address"] = "0xFC0200C0"
        d["evidence_entries"][0]["end_address"] = "0xFC02013F"
        d["evidence_entries"][0]["expected_byte_count"] = 0x80
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_EXCEEDED, [f.rule_id for f in result.findings])

    def test_firmware_revision_mismatch_against_scope_rejected(self):
        d = make_valid_manifest_dict()
        # Scope authorizes GM1.10C; entry claims GM1.10E
        d["evidence_entries"][0]["firmware_revision"] = "GM1.10E"
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_EXCEEDED, [f.rule_id for f in result.findings])

    def test_classification_disallowed_by_scope_rejected(self):
        d = make_valid_manifest_dict()
        # Scope allows STATIC_VERIFIED and INFERRED, but not UNKNOWN
        d["evidence_entries"][0]["classification"] = "UNKNOWN"
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_EXCEEDED, [f.rule_id for f in result.findings])

    def test_scope_byte_quota_exceeded_rejected(self):
        d = make_valid_manifest_dict()
        # Scope max_bytes_total = 512. Make entry span 600 bytes within approved range
        d["authorization_scopes"][0]["approved_ranges"][0]["end_address"] = "0xFC0203FF"
        d["evidence_entries"][0]["end_address"] = "0xFC020257"  # 600 bytes
        d["evidence_entries"][0]["expected_byte_count"] = 600
        manifest = EvidenceManifest.from_dict(d)
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_EXCEEDED, [f.rule_id for f in result.findings])

    # 6. Overlapping and inconsistent slices
    def test_overlapping_slices_rejected_under_strict_policy(self):
        d = make_valid_manifest_dict()
        # Entry 1: 0xFC020000..0xFC02003F (64 B)
        # Entry 2: Move to 0xFC020020..0xFC02003F (32 B, overlaps Entry 1)
        d["evidence_entries"][1]["start_address"] = "0xFC020020"
        d["evidence_entries"][1]["end_address"] = "0xFC02003F"
        d["evidence_entries"][1]["expected_byte_count"] = 32
        manifest = EvidenceManifest.from_dict(d)

        # Strict policy: no overlapping slices allowed
        result = self.validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_OVERLAPPING_SLICES, [f.rule_id for f in result.findings])

    def test_conflicting_hash_for_same_range_rejected(self):
        d = make_valid_manifest_dict()
        # Create second entry covering same range with different SHA
        d["evidence_entries"][1]["evidence_id"] = "SYNTH-003"
        d["evidence_entries"][1]["start_address"] = d["evidence_entries"][0]["start_address"]
        d["evidence_entries"][1]["end_address"] = d["evidence_entries"][0]["end_address"]
        d["evidence_entries"][1]["expected_byte_count"] = d["evidence_entries"][0]["expected_byte_count"]
        d["evidence_entries"][1]["sha256"] = "00" * 32
        manifest = EvidenceManifest.from_dict(d)

        perm_validator = EvidenceValidator(allow_overlapping_slices=True)
        result = perm_validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_INCONSISTENT_SLICES, [f.rule_id for f in result.findings])

    def test_conflicting_classification_for_same_range_rejected(self):
        d = make_valid_manifest_dict()
        d["evidence_entries"][1]["evidence_id"] = "SYNTH-003"
        d["evidence_entries"][1]["start_address"] = d["evidence_entries"][0]["start_address"]
        d["evidence_entries"][1]["end_address"] = d["evidence_entries"][0]["end_address"]
        d["evidence_entries"][1]["expected_byte_count"] = d["evidence_entries"][0]["expected_byte_count"]
        d["evidence_entries"][1]["sha256"] = d["evidence_entries"][0]["sha256"]
        d["evidence_entries"][1]["classification"] = "INFERRED"
        manifest = EvidenceManifest.from_dict(d)

        perm_validator = EvidenceValidator(allow_overlapping_slices=True)
        result = perm_validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_INCONSISTENT_SLICES, [f.rule_id for f in result.findings])


class TestSyntheticByteFixtures(unittest.TestCase):
    """Test verification against synthetic byte fixtures."""

    def setUp(self):
        self.validator = EvidenceValidator(allow_overlapping_slices=False)
        self.valid_data = make_valid_manifest_dict()
        self.fix1 = make_synthetic_fixture(64, 0x10)
        self.fix2 = make_synthetic_fixture(32, 0x20)

    def test_matching_synthetic_fixtures_pass(self):
        manifest = EvidenceManifest.from_dict(self.valid_data)
        fixtures = {
            "SYNTH-001": self.fix1,
            "SYNTH-002": self.fix2,
        }
        result = self.validator.validate_manifest(manifest, fixtures=fixtures)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_count, 0)

    def test_synthetic_fixture_length_mismatch_rejected(self):
        manifest = EvidenceManifest.from_dict(self.valid_data)
        fixtures = {
            "SYNTH-001": self.fix1[:40],  # Truncated
            "SYNTH-002": self.fix2,
        }
        result = self.validator.validate_manifest(manifest, fixtures=fixtures)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_FIXTURE_LENGTH_MISMATCH, [f.rule_id for f in result.findings])

    def test_synthetic_fixture_hash_mismatch_rejected(self):
        manifest = EvidenceManifest.from_dict(self.valid_data)
        corrupted = bytearray(self.fix1)
        corrupted[10] ^= 0xFF  # Flip bit
        fixtures = {
            "SYNTH-001": bytes(corrupted),
            "SYNTH-002": self.fix2,
        }
        result = self.validator.validate_manifest(manifest, fixtures=fixtures)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_FIXTURE_HASH_MISMATCH, [f.rule_id for f in result.findings])

    def test_overlapping_synthetic_fixtures_byte_conflict_rejected(self):
        # Entry 1: 0xFC020000..0xFC02003F (64 B)
        # Entry 2: 0xFC020020..0xFC02003F (32 B)
        # In the overlap (0xFC020020..0xFC02003F), provide conflicting bytes
        fix1 = make_synthetic_fixture(64, 0x10)
        fix2 = make_synthetic_fixture(32, 0x99)  # Different bytes

        d = make_valid_manifest_dict()
        d["evidence_entries"][1]["start_address"] = "0xFC020020"
        d["evidence_entries"][1]["end_address"] = "0xFC02003F"
        d["evidence_entries"][1]["expected_byte_count"] = 32
        d["evidence_entries"][1]["sha256"] = hashlib.sha256(fix2).hexdigest()
        manifest = EvidenceManifest.from_dict(d)

        perm_validator = EvidenceValidator(allow_overlapping_slices=True)
        fixtures = {
            "SYNTH-001": fix1,
            "SYNTH-002": fix2,
        }
        result = perm_validator.validate_manifest(manifest, fixtures=fixtures)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_INCONSISTENT_SLICES, [f.rule_id for f in result.findings])


class TestSecurityAndScopeEnforcement(unittest.TestCase):
    """Enforce strict security boundaries of the evidence harness."""

    def test_tool_does_not_import_subprocess(self):
        self.assertNotIn("subprocess", sys.modules[pev.__name__].__dict__)

    def test_tool_refuses_forbidden_binary_file_extensions(self):
        with tempfile.TemporaryDirectory() as td:
            for ext in (".bin", ".rom", ".dump", ".fir", ".img"):
                dummy_path = Path(td) / f"fake_firmware{ext}"
                dummy_path.write_bytes(b"\x00" * 128)
                manifest, err = load_manifest_file(dummy_path)
                self.assertIsNone(manifest)
                self.assertIn("Security Violation", str(err))

    def test_tool_refuses_primary_bin_named_file(self):
        with tempfile.TemporaryDirectory() as td:
            dummy_path = Path(td) / "PRIMARY.json"
            dummy_path.write_text("{}", encoding="utf-8")
            manifest, err = load_manifest_file(dummy_path)
            self.assertIsNone(manifest)
            self.assertIn("Security Violation", str(err))

    def test_oversized_manifest_rejected(self):
        huge_str = " " * (11 * 1024 * 1024)
        with self.assertRaises(ValueError) as ctx:
            EvidenceManifest.from_json(huge_str)
        self.assertIn("exceeds maximum allowed size", str(ctx.exception))


class TestPort11AEvidenceScenario(unittest.TestCase):
    """Real-world scenario: validate the 9 canonical PORT-11A pinned ROM slices."""

    def test_port11a_nine_canonical_slices_validate_cleanly(self):
        """Verify that the 9 canonical slices S1A-S3B (1,284 B) validate with 0 errors."""
        port11a_manifest = {
            "manifest_version": "1.0.0",
            "authorization_scopes": [
                {
                    "scope_id": "SCOPE-PORT11A-U1",
                    "firmware_revision": "GM1.10C",
                    "approved_ranges": [
                        {"start_address": "0xFC020040", "end_address": "0xFC0200CF", "label": "S1A ATCM copy loop"},
                        {"start_address": "0xFC31BBC4", "end_address": "0xFC31BBCB", "label": "S1B j_CreateTask veneer"},
                        {"start_address": "0xFCEF3488", "end_address": "0xFCEF36B3", "label": "S1C CreateTask ATCM ROM source"},
                        {"start_address": "0xFC31BE8C", "end_address": "0xFC31BE93", "label": "S1D j_CreateTaskStrictly veneer"},
                        {"start_address": "0xFCEF3F34", "end_address": "0xFCEF3F55", "label": "S1E CreateTaskStrictly ATCM ROM source"},
                    ],
                    "max_bytes_total": 1024,
                    "allowed_classifications": ["STATIC_VERIFIED", "INFERRED", "UNKNOWN"],
                    "description": "PORT-11A U1 CreateTask and CreateTaskStrictly scope",
                },
                {
                    "scope_id": "SCOPE-PORT11A-U2",
                    "firmware_revision": "GM1.10C",
                    "approved_ranges": [
                        {"start_address": "0xFC0BD070", "end_address": "0xFC0BD1BB", "label": "S2A task_InitFileModules creator/entry"},
                        {"start_address": "0xFC0D9CCC", "end_address": "0xFC0D9D25", "label": "S2B sub_fc0d9ccc callees"},
                    ],
                    "max_bytes_total": 512,
                    "allowed_classifications": ["STATIC_VERIFIED", "INFERRED", "UNKNOWN"],
                    "description": "PORT-11A U2 task_InitFileModules entry scope",
                },
                {
                    "scope_id": "SCOPE-PORT11A-U3",
                    "firmware_revision": "GM1.10C",
                    "approved_ranges": [
                        {"start_address": "0xFC1283AC", "end_address": "0xFC1283FF", "label": "S3A task_PhySw creator/entry"},
                        {"start_address": "0xFC128704", "end_address": "0xFC12871F", "label": "S3B PhySw literal and string pool"},
                    ],
                    "max_bytes_total": 256,
                    "allowed_classifications": ["STATIC_VERIFIED", "INFERRED", "UNKNOWN"],
                    "description": "PORT-11A U3 task_PhySw entry scope",
                },
            ],
            "evidence_entries": [
                {
                    "evidence_id": "PORT11A-S1A",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC020040",
                    "end_address": "0xFC0200CF",
                    "expected_byte_count": 144,
                    "sha256": "a8bea578f65643701322d3ce2fc500d04485323dbb28bfab6e89a51a6344c54b",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1A",
                    "authorization_scope_id": "SCOPE-PORT11A-U1",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S1B",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC31BBC4",
                    "end_address": "0xFC31BBCB",
                    "expected_byte_count": 8,
                    "sha256": "e7f6fb4484c3a010e0db4a97edd252a10e92c529f0e75190a0cf98a479fa566d",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1B",
                    "authorization_scope_id": "SCOPE-PORT11A-U1",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S1C",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFCEF3488",
                    "end_address": "0xFCEF36B3",
                    "expected_byte_count": 556,
                    "sha256": "409dcaec41a0e5aeba37110254919995f018aae13fcc942b832ffc244c223b36",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1C",
                    "authorization_scope_id": "SCOPE-PORT11A-U1",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S1D",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC31BE8C",
                    "end_address": "0xFC31BE93",
                    "expected_byte_count": 8,
                    "sha256": "f4a9356c75017083e2dbabbc309815595ae745a3787bbb5128e1e823601079b3",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1D",
                    "authorization_scope_id": "SCOPE-PORT11A-U1",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S1E",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFCEF3F34",
                    "end_address": "0xFCEF3F55",
                    "expected_byte_count": 34,
                    "sha256": "ce4d1016656cd6053e9808a6cf718d18e885948f0b7102a15cef88bcaacad612",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1E",
                    "authorization_scope_id": "SCOPE-PORT11A-U1",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S2A",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC0BD070",
                    "end_address": "0xFC0BD1BB",
                    "expected_byte_count": 332,
                    "sha256": "2c939717866f0a5c4c8df88e8f75942890347cdd7453fbe54bdcc33125020c94",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S2A",
                    "authorization_scope_id": "SCOPE-PORT11A-U2",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S2B",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC0D9CCC",
                    "end_address": "0xFC0D9D25",
                    "expected_byte_count": 90,
                    "sha256": "4e3f0f99e5605d08d6ba093146e86f009b28121220c632dae05f0a479e218ee8",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S2B",
                    "authorization_scope_id": "SCOPE-PORT11A-U2",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S3A",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC1283AC",
                    "end_address": "0xFC1283FF",
                    "expected_byte_count": 84,
                    "sha256": "8d38c2112b67283d302f77bd881ab9ccf4b2f7f1b4bfffc51bb531fd2151385a",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S3A",
                    "authorization_scope_id": "SCOPE-PORT11A-U3",
                    "classification": "STATIC_VERIFIED",
                },
                {
                    "evidence_id": "PORT11A-S3B",
                    "firmware_revision": "GM1.10C",
                    "start_address": "0xFC128704",
                    "end_address": "0xFC12871F",
                    "expected_byte_count": 28,
                    "sha256": "fdace2c951b23e71497dab6d9e160a439a72f20f24fbcb362bbd014d3714b376",
                    "provenance_source": "ROM_VERIFIED:PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S3B",
                    "authorization_scope_id": "SCOPE-PORT11A-U3",
                    "classification": "STATIC_VERIFIED",
                },
            ],
        }

        manifest = EvidenceManifest.from_dict(port11a_manifest)
        validator = EvidenceValidator(allow_overlapping_slices=False)
        result = validator.validate_manifest(manifest)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(len(manifest.entries), 9)
        total_bytes = sum(e.expected_byte_count for e in manifest.entries)
        self.assertEqual(total_bytes, 1284)

    def test_out_of_scope_scan_claim_is_rejected(self):
        """Demonstrate that claiming out-of-scope ROM caller scan 0xFC079130 fails validation."""
        d = make_valid_manifest_dict()
        out_of_scope_claim = {
            "evidence_id": "PORT11A-UNAPPROVED-CALLER-SCAN",
            "firmware_revision": "GM1.10C",
            "start_address": "0xFC079130",
            "end_address": "0xFC079133",
            "expected_byte_count": 4,
            "sha256": "aa" * 32,
            "provenance_source": "ROM_VERIFIED:out_of_scope_scan",
            "authorization_scope_id": "SCOPE-SYNTHETIC-01",
            "classification": "STATIC_VERIFIED",
        }
        d["evidence_entries"].append(out_of_scope_claim)
        manifest = EvidenceManifest.from_dict(d)

        validator = EvidenceValidator()
        result = validator.validate_manifest(manifest)
        self.assertFalse(result.is_valid)
        exceeded_findings = [f for f in result.findings if f.rule_id == RULE_SCOPE_EXCEEDED]
        self.assertTrue(any(f.evidence_id == "PORT11A-UNAPPROVED-CALLER-SCAN" for f in exceeded_findings))


class TestCommandLineInterface(unittest.TestCase):
    """Test CLI exit codes, JSON outputs, and argument parsing."""

    def test_cli_valid_manifest_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            manifest_path = Path(td) / "manifest.json"
            manifest_path.write_text(json.dumps(make_valid_manifest_dict()), encoding="utf-8")

            old_argv = sys.argv
            try:
                sys.argv = ["port11c_evidence_validator.py", "--manifest", str(manifest_path)]
                exit_code = pev.main()
                self.assertEqual(exit_code, 0)
            finally:
                sys.argv = old_argv

    def test_cli_invalid_manifest_returns_one(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_valid_manifest_dict()
            d["evidence_entries"].append(dict(d["evidence_entries"][0]))  # duplicate ID
            manifest_path = Path(td) / "manifest.json"
            manifest_path.write_text(json.dumps(d), encoding="utf-8")

            old_argv = sys.argv
            try:
                sys.argv = ["port11c_evidence_validator.py", "--manifest", str(manifest_path)]
                exit_code = pev.main()
                self.assertEqual(exit_code, 1)
            finally:
                sys.argv = old_argv

    def test_cli_missing_file_returns_two(self):
        old_argv = sys.argv
        try:
            sys.argv = ["port11c_evidence_validator.py", "--manifest", "/tmp/nonexistent_12345.json"]
            exit_code = pev.main()
            self.assertEqual(exit_code, 2)
        finally:
            sys.argv = old_argv

    def test_cli_forbidden_extension_returns_two(self):
        old_argv = sys.argv
        try:
            sys.argv = ["port11c_evidence_validator.py", "--manifest", "firmware.bin"]
            exit_code = pev.main()
            self.assertEqual(exit_code, 2)
        finally:
            sys.argv = old_argv

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as td:
            manifest_path = Path(td) / "manifest.json"
            manifest_path.write_text(json.dumps(make_valid_manifest_dict()), encoding="utf-8")

            import io
            old_stdout = sys.stdout
            old_argv = sys.argv
            captured = io.StringIO()
            try:
                sys.stdout = captured
                sys.argv = ["port11c_evidence_validator.py", "--manifest", str(manifest_path), "--json"]
                exit_code = pev.main()
                self.assertEqual(exit_code, 0)
                output = json.loads(captured.getvalue())
                self.assertTrue(output.get("is_valid"))
                self.assertEqual(output.get("error_count"), 0)
            finally:
                sys.stdout = old_stdout
                sys.argv = old_argv


class TestAuthorizationTrustBoundary(unittest.TestCase):
    """Test separation of trusted human scope policy from manifest-declared scopes."""

    def test_trust_boundary_warning_emitted_when_no_trusted_scopes_passed(self):
        manifest = EvidenceManifest.from_dict(make_valid_manifest_dict())
        validator = EvidenceValidator()
        result = validator.validate_manifest(manifest, trusted_scopes=None)
        self.assertTrue(result.is_valid)  # Valid structurally
        self.assertEqual(result.trust_level, "SELF_DECLARED_INTERNAL_ONLY")
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn(RULE_TRUST_BOUNDARY_NOTICE, rule_ids)

    def test_trusted_policy_verified_when_scopes_passed(self):
        d = make_valid_manifest_dict()
        manifest = EvidenceManifest.from_dict(d)
        trusted_scopes = {
            s.scope_id: s for s in [AuthorizationScope.from_dict(d["authorization_scopes"][0])]
        }
        validator = EvidenceValidator()
        result = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.trust_level, "TRUSTED_POLICY_VERIFIED")
        # Notice is not emitted when trusted scopes are explicitly provided
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn(RULE_TRUST_BOUNDARY_NOTICE, rule_ids)

    def test_manifest_declaring_unapproved_scope_rejected_by_policy(self):
        d = make_valid_manifest_dict()
        # Add an unapproved scope to manifest
        d["authorization_scopes"].append({
            "scope_id": "SCOPE-ROGUE-UNAUTHORIZED",
            "firmware_revision": "GM1.10C",
            "approved_ranges": [{"start_address": "0xFC050000", "end_address": "0xFC050100"}],
            "max_bytes_total": 256,
        })
        manifest = EvidenceManifest.from_dict(d)
        trusted_scopes = {
            s.scope_id: s for s in [AuthorizationScope.from_dict(d["authorization_scopes"][0])]
        }
        validator = EvidenceValidator()
        result = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_POLICY_VIOLATION, [f.rule_id for f in result.findings])

    def test_manifest_expanding_approved_range_rejected_by_policy(self):
        d = make_valid_manifest_dict()
        # Legitimate trusted policy has range 0xFC020000..0xFC0200FF
        trusted_scopes = {
            s.scope_id: s for s in [AuthorizationScope.from_dict(d["authorization_scopes"][0])]
        }
        # Manifest attempts to self-declare expanded range up to 0xFC020FFF
        d["authorization_scopes"][0]["approved_ranges"][0]["end_address"] = "0xFC020FFF"
        manifest = EvidenceManifest.from_dict(d)
        validator = EvidenceValidator()
        result = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes)
        self.assertFalse(result.is_valid)
        self.assertIn(RULE_SCOPE_POLICY_VIOLATION, [f.rule_id for f in result.findings])

    def test_cli_with_trusted_scopes_policy_file(self):
        with tempfile.TemporaryDirectory() as td:
            manifest_path = Path(td) / "manifest.json"
            policy_path = Path(td) / "trusted_policy.json"
            d = make_valid_manifest_dict()
            manifest_path.write_text(json.dumps(d), encoding="utf-8")
            policy_path.write_text(json.dumps(d["authorization_scopes"]), encoding="utf-8")

            old_argv = sys.argv
            try:
                sys.argv = [
                    "port11c_evidence_validator.py",
                    "--manifest", str(manifest_path),
                    "--trusted-scopes", str(policy_path),
                ]
                exit_code = pev.main()
                self.assertEqual(exit_code, 0)
            finally:
                sys.argv = old_argv


class TestPort11cAuditedSafetyControls(unittest.TestCase):
    """Targeted negative and security controls added during Worker G2 post-PR #16 audit."""

    def test_validator_never_grants_rom_reading_permission(self):
        """The validator must NEVER claim to grant ROM-reading or hardware execution permission."""
        manifest = EvidenceManifest.from_dict(make_valid_manifest_dict())
        validator = EvidenceValidator()

        # Case 1: Self-declared internal mode
        res1 = validator.validate_manifest(manifest)
        self.assertFalse(res1.rom_permission_granted)
        self.assertIn("possesses NO authority to grant ROM-reading", res1.rom_permission_disclaimer)
        dict1 = res1.to_dict()
        self.assertFalse(dict1["rom_permission_granted"])
        self.assertIn("rom_permission_disclaimer", dict1)

        # Case 2: Trusted policy verified mode
        trusted_scopes = {
            s.scope_id: s for s in [AuthorizationScope.from_dict(make_valid_manifest_dict()["authorization_scopes"][0])]
        }
        res2 = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes)
        self.assertFalse(res2.rom_permission_granted)
        self.assertIn("possesses NO authority to grant ROM-reading", res2.rom_permission_disclaimer)
        dict2 = res2.to_dict()
        self.assertFalse(dict2["rom_permission_granted"])

    def test_scopes_file_rejects_forbidden_rom_or_binary_names(self):
        """Scopes loader must refuse files with forbidden extensions or binary-like names."""
        for bad_name in ["scopes.rom", "primary.json", "rom_scopes.txt", "scopes.bin"]:
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / bad_name
                p.write_text("{}", encoding="utf-8")
                scopes, err = pev.load_scopes_file(p)
                self.assertIsNone(scopes)
                self.assertIn("Security Violation: Refusing to open forbidden binary", err)

    def test_scopes_file_rejects_non_dict_list_roots(self):
        """Scopes loader must fail closed if root JSON is not a dict or list."""
        for invalid_root in ["12345", '"string"', "true", "null"]:
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "scopes.json"
                p.write_text(invalid_root, encoding="utf-8")
                scopes, err = pev.load_scopes_file(p)
                self.assertIsNone(scopes)
                self.assertIn("Error parsing authorization scopes", err)

    def test_scopes_file_rejects_malformed_scopes_list(self):
        """Scopes loader must fail closed if 'authorization_scopes' is not a list."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "scopes.json"
            p.write_text(json.dumps({"authorization_scopes": "not a list"}), encoding="utf-8")
            scopes, err = pev.load_scopes_file(p)
            self.assertIsNone(scopes)
            self.assertIn("must be a list", err)

    def test_scopes_file_rejects_non_dict_scope_entry(self):
        """Scopes loader must fail closed if any scope entry in the list is not a dictionary."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "scopes.json"
            p.write_text(json.dumps({"authorization_scopes": [123]}), encoding="utf-8")
            scopes, err = pev.load_scopes_file(p)
            self.assertIsNone(scopes)
            self.assertIn("Scope entry must be a dictionary", err)

    def test_scope_cumulative_quota_boundary_enforcement(self):
        """Verify that cumulative byte quota per scope is enforced at exact boundary."""
        validator = EvidenceValidator()
        d = make_valid_manifest_dict()
        d["authorization_scopes"][0]["max_bytes_total"] = 100
        # Set first entry to 50 bytes within approved range (0xFC020040..0xFC020071 = 50 B)
        d["evidence_entries"][0]["start_address"] = "0xFC020040"
        d["evidence_entries"][0]["end_address"] = "0xFC020071"
        d["evidence_entries"][0]["expected_byte_count"] = 50
        # Set second entry to 50 bytes within approved range (0xFC020072..0xFC0200A3 = 50 B)
        d["evidence_entries"][1]["start_address"] = "0xFC020072"
        d["evidence_entries"][1]["end_address"] = "0xFC0200A3"
        d["evidence_entries"][1]["expected_byte_count"] = 50

        manifest_exact = EvidenceManifest.from_dict(d)
        res_exact = validator.validate_manifest(manifest_exact)
        self.assertTrue(res_exact.is_valid)

        # Exceeds quota by 1 byte: 50 + 51 = 101 bytes (FAIL)
        d["evidence_entries"][1]["end_address"] = "0xFC0200A4"
        d["evidence_entries"][1]["expected_byte_count"] = 51
        manifest_over = EvidenceManifest.from_dict(d)
        res_over = validator.validate_manifest(manifest_over)
        self.assertFalse(res_over.is_valid)
        rule_ids = [f.rule_id for f in res_over.findings]
        self.assertIn(RULE_SCOPE_EXCEEDED, rule_ids)


if __name__ == "__main__":
    unittest.main()


