#!/usr/bin/env python3
"""Tests for PORT-13 fail-closed GM1.10C memory ownership proof obligations.

Covers:
  1. Current overall readiness is False for shipped data.
  2. Historical-firmware-only (1.00C/1.10E) citations cannot be VERIFIED.
  3. Nonexistent cited path fails fail-closed.
  4. Untracked / local-only source fails fail-closed.
  5. There is no path to True from the shipped data.
  6. PR #23-only evidence is recorded as UNKNOWN with pending PR note.
  7. Every address appearing in the module is present on origin/main, cited file:line.
  8. Security invariants: standard library only, strictly no subprocess calls.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import unittest

# Ensure repo root and tools are in sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import tools.port13_memory_obligations as pmo
from tools.port13_memory_obligations import (
    Citation,
    DEFAULT_MEMORY_OBLIGATIONS,
    EvaluationResult,
    HISTORICAL_FIRMWARES,
    HISTORICAL_ONLY_PATHS,
    MemoryObligation,
    ObligationFinding,
    ObligationStatus,
    ORIGIN_MAIN_PIN_COMMIT,
    ORIGIN_MAIN_TRACKED_FILES,
    PINNED_ORIGIN_MAIN_FILE_HASHES,
    RULE_CONTENT_HASH_MISMATCH,
    RULE_EMPTY_CITATIONS,
    RULE_HISTORICAL_CANNOT_VERIFY,
    RULE_MISSING_CITED_PATH,
    RULE_PENDING_PR_CANNOT_VERIFY,
    RULE_STATUS_NOT_VERIFIED,
    RULE_UNACCEPTABLE_SOURCE,
    RULE_UNPINNED_SOURCE,
    RULE_UNREADABLE_SOURCE,
    RULE_UNTRACKED_SOURCE,
    SUPPORTED_FIRMWARE,
    SUPPORTED_FIRMWARES,
    TRACKED_ADDRESS_CITATIONS,
    evaluate,
    is_supported_firmware,
    normalize_firmware,
    verify_address_provenance,
)


class TestCurrentReadinessAndShippedData(unittest.TestCase):
    """Verify that current overall readiness is False and cannot evaluate to True."""

    def test_current_overall_readiness_is_false(self):
        """Current overall readiness must evaluate to False (fail-closed)."""
        res = evaluate(repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertFalse(bool(res))
        self.assertEqual(res.total_obligations, 18)
        self.assertEqual(res.verified_count, 1)
        self.assertEqual(res.inferred_count, 11)
        self.assertEqual(res.unknown_count, 6)
        self.assertEqual(res.error_count, 0)
        self.assertEqual(res.warning_count, 17)

    def test_there_is_no_path_to_true_from_shipped_data(self):
        """The shipped data contains real unproven preconditions; there is no path to True."""
        res = evaluate(DEFAULT_MEMORY_OBLIGATIONS, repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)

        # 17 of 18 obligations are not verified in the shipped data
        unverified_ids = [
            ob.id for ob in DEFAULT_MEMORY_OBLIGATIONS
            if ob.current_status != ObligationStatus.VERIFIED
        ]
        self.assertEqual(len(unverified_ids), 17)

        # Even if individual subsets are evaluated, any subset containing
        # an INFERRED or UNKNOWN obligation must evaluate to is_ready == False
        for ob in DEFAULT_MEMORY_OBLIGATIONS:
            sub_res = evaluate([ob], repo_root=REPO_ROOT)
            if ob.id == "OBLIG-MEM-16A":
                # OBLIG-MEM-16A is the only verified static copy bound
                self.assertTrue(sub_res.is_ready)
            else:
                self.assertFalse(sub_res.is_ready)


class TestFailClosedCitationValidation(unittest.TestCase):
    """Verify that evaluate() fails closed on citation integrity violations."""

    def test_historical_only_citation_cannot_be_verified(self):
        """A historical-firmware-only citation (1.00C/1.10E) forces False if marked VERIFIED."""
        # Case A: Explicit historical firmware tag
        ob_hist_fw = MemoryObligation(
            id="TEST-HIST-01",
            statement="Test historical firmware citation failure",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                    line=166,
                    firmware="GM1.10E",
                    is_historical=True,
                ),
            ),
        )
        res_a = evaluate([ob_hist_fw], repo_root=REPO_ROOT)
        self.assertFalse(res_a.is_ready)
        self.assertGreaterEqual(res_a.error_count, 1)
        hist_rules = [f.rule_id for f in res_a.findings]
        self.assertIn(RULE_HISTORICAL_CANNOT_VERIFY, hist_rules)

        # Case B: Historical file path
        ob_hist_file = MemoryObligation(
            id="TEST-HIST-02",
            statement="Test historical symbols file failure",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("research/historical/g3x/g3x_100c_historical_symbols.csv",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="research/historical/g3x/g3x_100c_historical_symbols.csv",
                    line=1,
                    firmware="1.00C",
                ),
            ),
        )
        res_b = evaluate([ob_hist_file], repo_root=REPO_ROOT)
        self.assertFalse(res_b.is_ready)
        self.assertIn(RULE_HISTORICAL_CANNOT_VERIFY, [f.rule_id for f in res_b.findings])

    def test_nonexistent_cited_path_fails(self):
        """A nonexistent cited path forces False and records an error finding."""
        ob_missing = MemoryObligation(
            id="TEST-MISSING-01",
            statement="Test missing file failure",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/NONEXISTENT_PROOF_DOC_12345.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="docs/NONEXISTENT_PROOF_DOC_12345.md",
                    line=1,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_missing], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertGreaterEqual(res.error_count, 1)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_MISSING_CITED_PATH, rules)

    def test_untracked_source_fails(self):
        """A source that is not tracked on origin/main forces False and records an error."""
        ob_untracked = MemoryObligation(
            id="TEST-UNTRACKED-01",
            statement="Test untracked source failure",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/CHDK_PORT1B_HEAP_PROOF.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="docs/CHDK_PORT1B_HEAP_PROOF.md",
                    line=92,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_untracked], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_UNTRACKED_SOURCE, rules)

    def test_unacceptable_source_for_obligation_fails(self):
        """A source tracked on origin/main but not in acceptable_tracked_sources forces False."""
        ob_unacceptable = MemoryObligation(
            id="TEST-UNACCEPTABLE-01",
            statement="Test acceptable sources restriction",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/PORT11A_GM110C_ROM_EVIDENCE.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                # docs/SAFETY.md is tracked on origin/main, but not in acceptable_tracked_sources
                Citation(
                    path="docs/SAFETY.md",
                    line=1,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_unacceptable], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_UNACCEPTABLE_SOURCE, rules)

    def test_empty_citations_fails(self):
        """An obligation with no citations cannot be evaluated as ready."""
        ob_empty = MemoryObligation(
            id="TEST-EMPTY-01",
            statement="Test empty citations list",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/PORT11A_GM110C_ROM_EVIDENCE.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(),
        )
        res = evaluate([ob_empty], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_EMPTY_CITATIONS, rules)


class TestStatusAndPendingPRHandling(unittest.TestCase):
    """Verify handling of UNKNOWN, INFERRED, and pending PR evidence."""

    def test_unknown_status_forces_false(self):
        """Any obligation with status UNKNOWN forces overall readiness to False."""
        ob_unknown = MemoryObligation(
            id="TEST-UNKNOWN-01",
            statement="Test unknown status behavior",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/PORT11A_GM110C_ROM_EVIDENCE.md",),
            current_status=ObligationStatus.UNKNOWN,
            citations=(
                Citation(
                    path="docs/PORT11A_GM110C_ROM_EVIDENCE.md",
                    line=20,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_unknown], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.unknown_count, 1)
        self.assertEqual(res.verified_count, 0)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_STATUS_NOT_VERIFIED, rules)

    def test_inferred_status_forces_false(self):
        """Any obligation with status INFERRED forces overall readiness to False."""
        ob_inferred = MemoryObligation(
            id="TEST-INFERRED-01",
            statement="Test inferred status behavior",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("docs/PORT11A_GM110C_ROM_EVIDENCE.md",),
            current_status=ObligationStatus.INFERRED,
            citations=(
                Citation(
                    path="docs/PORT11A_GM110C_ROM_EVIDENCE.md",
                    line=20,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_inferred], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.inferred_count, 1)
        self.assertEqual(res.verified_count, 0)

    def test_pr23_evidence_marked_unknown_with_pending_note(self):
        """Evidence found only in unmerged PR #23 must be UNKNOWN with pending PR note."""
        pr23_obligations = [
            ob for ob in DEFAULT_MEMORY_OBLIGATIONS
            if ob.pending_pr == "PR #23"
        ]
        self.assertGreaterEqual(len(pr23_obligations), 3)

        for ob in pr23_obligations:
            self.assertEqual(
                ob.current_status,
                ObligationStatus.UNKNOWN,
                f"Obligation {ob.id} relying on PR #23 must have status UNKNOWN",
            )
            self.assertEqual(ob.pending_pr, "PR #23")
            self.assertIn("PR #23", ob.notes + " ".join(c.note for c in ob.citations))

    def test_pending_pr_evidence_cannot_be_verified(self):
        """An obligation citing evidence found only in unmerged PR #23 cannot be marked VERIFIED."""
        ob_pending_pr_claim = MemoryObligation(
            id="TEST-PR23-CLAIM-01",
            statement="Test pending PR over-promotion",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("chdk-port/platform/g3x/sub/110c/boot_prototype.c",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                    line=179,
                    firmware="GM1.10C",
                ),
            ),
            pending_pr="PR #23",
        )
        res = evaluate([ob_pending_pr_claim], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_PENDING_PR_CANNOT_VERIFY, rules)


class TestAddressProvenanceAndIntegrity(unittest.TestCase):
    """Verify that every address appearing in the module is tracked and cited file:line."""

    def test_every_address_is_present_in_tracked_origin_main_doc(self):
        """All addresses in TRACKED_ADDRESS_CITATIONS must be present on origin/main."""
        ok, errors = verify_address_provenance(repo_root=REPO_ROOT)
        self.assertTrue(ok, f"Address provenance check failed with errors:\n" + "\n".join(errors))
        self.assertEqual(len(errors), 0)

    def test_tracked_address_citations_count(self):
        """Ensure a robust registry of tracked addresses."""
        self.assertGreaterEqual(len(TRACKED_ADDRESS_CITATIONS), 45)

    def test_all_tracked_citations_have_valid_lines(self):
        """Verify that every address citation references an existing file and valid line."""
        for addr_str, citation in TRACKED_ADDRESS_CITATIONS.items():
            full_path = REPO_ROOT / citation.document_ref
            self.assertTrue(
                full_path.is_file(),
                f"Document {citation.document_ref} cited for {addr_str} does not exist",
            )
            self.assertIn(
                citation.document_ref,
                ORIGIN_MAIN_TRACKED_FILES,
                f"Document {citation.document_ref} cited for {addr_str} is not on origin/main",
            )
            lines = full_path.read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(citation.line, 1)
            self.assertLessEqual(citation.line, len(lines))
            target_line = lines[citation.line - 1].lower()
            self.assertIn(
                addr_str.lower(),
                target_line,
                f"Address {addr_str} not found in {citation.document_ref}:{citation.line}",
            )


class TestFirmwareIdentityAllowlist(unittest.TestCase):
    """Enforce strict GM1.10C firmware identity allowlist on VERIFIED obligations."""

    def test_strict_allowlist_accepts_only_normalized_gm110c(self):
        """Allowlist helper accepts only GM1.10C after normalization, rejecting everything else."""
        self.assertTrue(is_supported_firmware("GM1.10C"))
        self.assertTrue(is_supported_firmware("gm1.10c"))
        self.assertTrue(is_supported_firmware(" GM1.10C "))
        self.assertTrue(is_supported_firmware("gm1.10c\t"))

        # Strict rejection of historical, unknown, or malformed revisions
        self.assertFalse(is_supported_firmware("gm1.10e"))
        self.assertFalse(is_supported_firmware("GM1.10E "))
        self.assertFalse(is_supported_firmware("UNKNOWN"))
        self.assertFalse(is_supported_firmware(""))
        self.assertFalse(is_supported_firmware(None))
        self.assertFalse(is_supported_firmware("GM1.10X"))
        self.assertFalse(is_supported_firmware("1.00C"))
        self.assertFalse(is_supported_firmware("1.10E"))
        self.assertFalse(is_supported_firmware("GM1.00C"))

    def test_verified_obligation_rejects_unsupported_firmware_variants(self):
        """Changing the VERIFIED obligation's citation firmware to non-GM1.10C fails closed."""
        base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == "OBLIG-MEM-16A"][0]

        test_variants = ["gm1.10e", "GM1.10E ", "UNKNOWN", "", "GM1.10X", None]
        for bad_fw in test_variants:
            with self.subTest(firmware=bad_fw):
                bad_cit = Citation(
                    path=base_ob.citations[0].path,
                    line=base_ob.citations[0].line,
                    end_line=base_ob.citations[0].end_line,
                    firmware=bad_fw,  # type: ignore
                    note="Tampered citation firmware for test",
                )
                tampered_ob = MemoryObligation(
                    id=base_ob.id,
                    statement=base_ob.statement,
                    required_evidence_type=base_ob.required_evidence_type,
                    acceptable_tracked_sources=base_ob.acceptable_tracked_sources,
                    current_status=ObligationStatus.VERIFIED,
                    citations=(bad_cit,),
                )
                res = evaluate([tampered_ob], repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready, f"Failed to fail-closed on firmware variant {bad_fw!r}")
                self.assertGreaterEqual(res.error_count, 1)
                rules = [f.rule_id for f in res.findings]
                self.assertIn(
                    RULE_HISTORICAL_CANNOT_VERIFY,
                    rules,
                    f"Expected RULE_HISTORICAL_CANNOT_VERIFY for firmware {bad_fw!r}",
                )


class TestHistoricalProvenanceMixedVersionDocs(unittest.TestCase):
    """Enforce fail-closed handling of historical evidence in mixed-version docs."""

    def test_shipped_oblig_mem_10_fails_if_promoted_to_verified(self):
        """OBLIG-MEM-10 documents OMAR only for GM1.10E; promoting to VERIFIED forces False."""
        base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == "OBLIG-MEM-10"][0]
        promoted = MemoryObligation(
            id=base_ob.id,
            statement=base_ob.statement,
            required_evidence_type=base_ob.required_evidence_type,
            acceptable_tracked_sources=base_ob.acceptable_tracked_sources,
            current_status=ObligationStatus.VERIFIED,
            citations=base_ob.citations,
            pending_pr=base_ob.pending_pr,
            notes=base_ob.notes,
        )
        res = evaluate([promoted], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertGreaterEqual(res.error_count, 1)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_HISTORICAL_CANNOT_VERIFY, rules)

    def test_all_shipped_historical_obligations_fail_if_promoted_to_verified(self):
        """Obligations citing historical firmware lines cannot be verified."""
        historical_ob_ids = (
            "OBLIG-MEM-01",
            "OBLIG-MEM-10",
            "OBLIG-MEM-11",
            "OBLIG-MEM-12",
            "OBLIG-MEM-13",
            "OBLIG-MEM-17",
        )
        for ob_id in historical_ob_ids:
            with self.subTest(obligation_id=ob_id):
                base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == ob_id][0]
                promoted = MemoryObligation(
                    id=base_ob.id,
                    statement=base_ob.statement,
                    required_evidence_type=base_ob.required_evidence_type,
                    acceptable_tracked_sources=base_ob.acceptable_tracked_sources,
                    current_status=ObligationStatus.VERIFIED,
                    citations=base_ob.citations,
                    pending_pr=base_ob.pending_pr,
                    notes=base_ob.notes,
                )
                res = evaluate([promoted], repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready)
                self.assertGreaterEqual(res.error_count, 1)
                rules = [f.rule_id for f in res.findings]
                self.assertIn(RULE_HISTORICAL_CANNOT_VERIFY, rules)

    def test_no_shipped_verified_obligation_depends_only_on_historical_citations(self):
        """Generic invariant: no shipped VERIFIED obligation depends solely on historical evidence."""
        verified_obligations = [
            ob for ob in DEFAULT_MEMORY_OBLIGATIONS
            if ob.current_status == ObligationStatus.VERIFIED
        ]
        self.assertGreater(len(verified_obligations), 0, "Shipped dataset has no VERIFIED obligations")
        for ob in verified_obligations:
            self.assertGreater(len(ob.citations), 0)
            for cit in ob.citations:
                self.assertFalse(
                    cit.is_historical,
                    f"VERIFIED obligation {ob.id} has citation marked is_historical=True",
                )
                self.assertEqual(
                    normalize_firmware(cit.firmware),
                    SUPPORTED_FIRMWARE,
                    f"VERIFIED obligation {ob.id} cites non-{SUPPORTED_FIRMWARE} firmware {cit.firmware!r}",
                )
                self.assertNotIn(
                    cit.path,
                    HISTORICAL_ONLY_PATHS,
                    f"VERIFIED obligation {ob.id} cites historical-only path {cit.path}",
                )


class TestContentAuthenticationAndDigestPinning(unittest.TestCase):
    """Verify cryptographic SHA-256 provenance authentication for cited files."""

    def test_all_pinned_hashes_match_disk_files(self):
        """Every entry in PINNED_ORIGIN_MAIN_FILE_HASHES must exist and match its pin."""
        self.assertGreaterEqual(len(PINNED_ORIGIN_MAIN_FILE_HASHES), 9)
        for rel_path, expected_hash in PINNED_ORIGIN_MAIN_FILE_HASHES.items():
            full_path = REPO_ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"Pinned file '{rel_path}' missing on disk")
            actual_sha = hashlib.sha256(full_path.read_bytes()).hexdigest()
            self.assertEqual(
                actual_sha.lower(),
                expected_hash.lower(),
                f"Digest mismatch for '{rel_path}' against pinned commit {ORIGIN_MAIN_PIN_COMMIT}",
            )

    def test_altered_content_at_allowed_path_fails_via_injectable_reader(self):
        """Content alteration at an allowed path must be rejected fail-closed via file_reader."""
        base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == "OBLIG-MEM-16A"][0]

        def corrupted_reader(p: pathlib.Path) -> bytes:
            return b"TAMPERED_ROM_EVIDENCE_BYTES_0xDEADBEEF"

        res = evaluate([base_ob], repo_root=REPO_ROOT, file_reader=corrupted_reader)
        self.assertFalse(res.is_ready)
        self.assertGreaterEqual(res.error_count, 1)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_CONTENT_HASH_MISMATCH, rules)

    def test_altered_content_at_allowed_path_fails_via_temp_root(self):
        """Content alteration at an allowed path must be rejected fail-closed via repo_root."""
        base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == "OBLIG-MEM-16A"][0]
        cited_rel_path = base_ob.citations[0].path

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = pathlib.Path(tmp_dir)
            fake_file = tmp_root / cited_rel_path
            fake_file.parent.mkdir(parents=True, exist_ok=True)
            fake_file.write_text("Altered documentation bytes", encoding="utf-8")

            res = evaluate([base_ob], repo_root=tmp_root)
            self.assertFalse(res.is_ready)
            self.assertGreaterEqual(res.error_count, 1)
            rules = [f.rule_id for f in res.findings]
            self.assertIn(RULE_CONTENT_HASH_MISMATCH, rules)

    def test_unpinned_path_at_allowed_path_fails(self):
        """A tracked origin/main file that lacks a pinned SHA-256 digest must fail closed."""
        # README.md is tracked on origin/main but not in PINNED_ORIGIN_MAIN_FILE_HASHES
        self.assertIn("README.md", ORIGIN_MAIN_TRACKED_FILES)
        self.assertNotIn("README.md", PINNED_ORIGIN_MAIN_FILE_HASHES)

        ob_unpinned = MemoryObligation(
            id="TEST-UNPINNED-01",
            statement="Test unpinned source rejection",
            required_evidence_type="ROM_VERIFIED",
            acceptable_tracked_sources=("README.md",),
            current_status=ObligationStatus.VERIFIED,
            citations=(
                Citation(
                    path="README.md",
                    line=1,
                    firmware="GM1.10C",
                ),
            ),
        )
        res = evaluate([ob_unpinned], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertGreaterEqual(res.error_count, 1)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_UNPINNED_SOURCE, rules)

    def test_unreadable_file_fails_closed(self):
        """An unreadable source file forces fail-closed evaluate()."""
        base_ob = [ob for ob in DEFAULT_MEMORY_OBLIGATIONS if ob.id == "OBLIG-MEM-16A"][0]

        def failing_reader(p: pathlib.Path) -> bytes:
            raise PermissionError("EACCES: Permission denied")

        res = evaluate([base_ob], repo_root=REPO_ROOT, file_reader=failing_reader)
        self.assertFalse(res.is_ready)
        self.assertGreaterEqual(res.error_count, 1)
        rules = [f.rule_id for f in res.findings]
        self.assertIn(RULE_UNREADABLE_SOURCE, rules)


class TestSecurityAndScopeBoundaries(unittest.TestCase):
    """Enforce security and scope boundaries: standard library only, no subprocess."""

    def test_no_subprocess_imported(self):
        """port13_memory_obligations must not import subprocess."""
        self.assertNotIn("subprocess", sys.modules[pmo.__name__].__dict__)

    def test_stdlib_only(self):
        """port13_memory_obligations must only use Python standard library modules."""
        # Non-exhaustive list of external libraries that must never be imported
        forbidden_modules = ("pytest", "requests", "capstone", "ghidra", "keystone", "numpy")
        for mod in forbidden_modules:
            self.assertNotIn(mod, sys.modules[pmo.__name__].__dict__)

    def test_all_obligations_serialize_to_dict(self):
        """All obligations and citations must serialize cleanly to dict / JSON."""
        for ob in DEFAULT_MEMORY_OBLIGATIONS:
            d = ob.to_dict()
            self.assertEqual(d["id"], ob.id)
            self.assertIsInstance(d["citations"], list)
            # Ensure JSON serializable
            import json
            raw_json = json.dumps(d)
            self.assertIn(ob.id, raw_json)


if __name__ == "__main__":
    unittest.main()
