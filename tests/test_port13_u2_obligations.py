#!/usr/bin/env python3
"""tests/test_port13_u2_obligations.py

Tests for PORT-13 fail-closed proof obligations for U2 InitFileModules filesystem readiness.

Verifies:
  1. evaluate() returns not-ready; there is no path to ready from the shipped data.
  2. Static evidence (Thumb entry 0xFC0BD071 / ROM slice S2A) CANNOT discharge any runtime obligation.
  3. Missing citations, citations to untracked files, or citations to local-only paths
     (e.g., firmware/ dumps, PORT-9A L1/L2) cause failure.
  4. Consistency with PORT-9A model (precondition False) and PORT-9B I2 contract;
     tools/port9a_runtime_lifecycle.py and tools/port9b_runtime_contract.py are unmodified.
  5. No new firmware addresses; every address is cited to a Git-tracked doc.
  6. Security & scope boundaries: standard library only, strictly no subprocess imports.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

# Ensure repo root and tools/ are in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import tools.port13_u2_obligations as u2
from tools.port13_u2_obligations import (
    CANONICAL_U2_OBLIGATION_IDS,
    Citation,
    DEFAULT_U2_OBLIGATIONS,
    EvaluationResult,
    EvaluationVerdict,
    EvidenceArtifact,
    ObligationFinding,
    ObligationKind,
    ObligationStatus,
    ORIGIN_MAIN_TRACKED_FILES,
    PINNED_FILE_HASHES,
    PORT9A_SIX_STAGE_CORRESPONDENCE,
    RequiredEvidence,
    RULE_ARTIFACT_TYPE_MISMATCH,
    RULE_CONTENT_HASH_MISMATCH,
    RULE_FORBIDDEN_LOCAL_PATH,
    RULE_INCOMPLETE_OBLIGATION_SET,
    RULE_MISSING_CITED_PATH,
    RULE_MISSING_CITATIONS,
    RULE_PRECONDITION_INVARIANT_VIOLATED,
    RULE_STATIC_CANNOT_DISCHARGE_RUNTIME,
    RULE_STATUS_UNVERIFIED,
    RULE_UNTRACKED_PATH,
    TRACKED_ADDRESS_CITATIONS,
    U2Obligation,
    evaluate,
    evaluate_obligation,
    get_obligation,
    is_static_evidence,
    verify_address_provenance,
    verify_i2_contract_consistency,
)
import tools.port9a_runtime_lifecycle as rt
import tools.port9b_runtime_contract as p9b


class TestShippedDataFailClosed(unittest.TestCase):
    """Verify that evaluate() fails closed and returns not-ready for shipped data."""

    def test_evaluate_returns_not_ready_for_shipped_data(self):
        """Shipped data must evaluate to not-ready with fail-closed active."""
        res = evaluate(repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.status, "not-ready")
        self.assertFalse(bool(res))
        self.assertEqual(res, "not-ready")
        self.assertTrue(res.is_fail_closed)
        self.assertEqual(res.total_obligations, 8)
        self.assertEqual(res.verified_count, 1)  # Only OBLIG-U2-01 static entry is verified
        self.assertEqual(res.unknown_count, 7)   # 7 runtime obligations remain UNKNOWN
        self.assertEqual(res.inferred_count, 0)
        self.assertEqual(res.static_count, 1)
        self.assertEqual(res.runtime_count, 7)
        self.assertEqual(res.error_count, 0)
        self.assertEqual(res.warning_count, 7)

    def test_there_is_no_path_to_ready_from_shipped_data(self):
        """There must be no path to ready from shipped data without unverified runtime proof."""
        res = evaluate(DEFAULT_U2_OBLIGATIONS, repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.status, "not-ready")

        # Every individual obligation evaluated via evaluate([ob]) must evaluate to not-ready
        # because every strict subset of the canonical set fails aggregate readiness
        for ob in DEFAULT_U2_OBLIGATIONS:
            single_res = evaluate([ob], repo_root=REPO_ROOT)
            self.assertFalse(single_res.is_ready, f"{ob.id} alone is a strict subset and must evaluate to not-ready")
            self.assertEqual(single_res.status, "not-ready")
            self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in single_res.findings])

            # Per-obligation satisfaction query
            if ob.id == "OBLIG-U2-01":
                self.assertTrue(single_res.obligation_evaluations[ob.id].is_satisfied)
                self.assertTrue(single_res.is_obligation_satisfied(ob.id))
                self.assertTrue(evaluate_obligation(ob, repo_root=REPO_ROOT).is_satisfied)
            else:
                self.assertFalse(single_res.obligation_evaluations[ob.id].is_satisfied)
                self.assertFalse(single_res.is_obligation_satisfied(ob.id))
                self.assertFalse(evaluate_obligation(ob, repo_root=REPO_ROOT).is_satisfied)

    def test_every_strict_subset_of_canonical_set_returns_not_ready(self):
        """Every strict subset of the canonical obligation set must evaluate to not-ready."""
        canonical_obs = list(DEFAULT_U2_OBLIGATIONS)
        self.assertEqual(len(canonical_obs), 8)

        # Subsets of length 1 to 7
        for k in range(1, len(canonical_obs)):
            subset = canonical_obs[:k]
            res = evaluate(subset, repo_root=REPO_ROOT)
            self.assertFalse(res.is_ready, f"Subset of size {k} must not evaluate to ready")
            self.assertEqual(res.status, "not-ready")
            self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in res.findings])

        # Single obligation OBLIG-U2-01 alone must evaluate to not-ready
        ob1 = get_obligation("OBLIG-U2-01")
        self.assertIsNotNone(ob1)
        res_ob1 = evaluate([ob1], repo_root=REPO_ROOT)
        self.assertFalse(res_ob1.is_ready)
        self.assertEqual(res_ob1.status, "not-ready")
        self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in res_ob1.findings])

        # Single obligation OBLIG-U2-01 with static evidence must still be not-ready in aggregate
        static_ev = EvidenceArtifact(
            artifact_id="STATIC-ROM-EVIDENCE",
            artifact_type="STATIC_ROM_SLICE",
            status=ObligationStatus.VERIFIED,
            kind=ObligationKind.STATIC,
            citation=Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21),
            associated_addresses=("0xFC0BD071",),
        )
        res_single_ev = evaluate([ob1], evidence={"OBLIG-U2-01": static_ev}, repo_root=REPO_ROOT)
        self.assertFalse(res_single_ev.is_ready, "Single obligation with static evidence must not give aggregate ready")
        self.assertEqual(res_single_ev.status, "not-ready")
        self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in res_single_ev.findings])
        self.assertTrue(res_single_ev.obligation_evaluations["OBLIG-U2-01"].is_satisfied)
        self.assertTrue(res_single_ev.is_obligation_satisfied("OBLIG-U2-01"))

        # Extra / non-canonical obligation must also fail aggregate readiness
        fake_ob = U2Obligation(
            id="OBLIG-FAKE-EXTRA",
            statement="Fake extra obligation",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence("TEST", "test"),
            citations=(Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21),),
        )
        res_extra = evaluate(canonical_obs + [fake_ob], repo_root=REPO_ROOT)
        self.assertFalse(res_extra.is_ready)
        self.assertEqual(res_extra.status, "not-ready")
        self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in res_extra.findings])

    def test_get_obligation_lookup(self):
        """get_obligation retrieves canonical obligations by ID."""
        ob1 = get_obligation("OBLIG-U2-01")
        self.assertIsNotNone(ob1)
        self.assertEqual(ob1.id, "OBLIG-U2-01")
        self.assertTrue(ob1.is_static)

        nonexistent = get_obligation("OBLIG-NONEXISTENT")
        self.assertIsNone(nonexistent)


class TestStaticEvidenceCannotDischargeRuntimeObligations(unittest.TestCase):
    """Verify that static evidence cannot discharge any runtime readiness obligation."""

    def setUp(self):
        # Canonical static evidence artifact for 0xFC0BD071
        self.static_entry_evidence = EvidenceArtifact(
            artifact_id="ROM-SLICE-S2A-ENTRY",
            artifact_type="STATIC_ROM_SLICE",
            status=ObligationStatus.VERIFIED,
            kind=ObligationKind.STATIC,
            description="Static ROM slice S2A disassembly confirming task_InitFileModules entry 0xFC0BD071",
            citation=Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21),
            associated_addresses=("0xFC0BD071", "0xFC0BD070"),
            how_captured="static ROM disassembly",
        )

    def test_static_entry_evidence_satisfies_static_entry_obligation(self):
        """Static entry evidence 0xFC0BD071 CAN satisfy OBLIG-U2-01 in isolation."""
        ob1 = get_obligation("OBLIG-U2-01")
        self.assertIsNotNone(ob1)

        # In isolation via evaluate_obligation():
        single_eval = evaluate_obligation(ob1, evidence=self.static_entry_evidence, repo_root=REPO_ROOT)
        self.assertTrue(single_eval.is_satisfied)
        self.assertIn("Satisfied by verified evidence", single_eval.reason)

        # In aggregate evaluate(): subset alone fails aggregate readiness, but obligation is satisfied
        res = evaluate([ob1], evidence={"OBLIG-U2-01": self.static_entry_evidence}, repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.status, "not-ready")
        self.assertIn(RULE_INCOMPLETE_OBLIGATION_SET, [f.rule_id for f in res.findings])
        self.assertTrue(res.obligation_evaluations["OBLIG-U2-01"].is_satisfied)
        self.assertTrue(res.is_obligation_satisfied("OBLIG-U2-01"))

    def test_execution_witness_citing_only_port11a_static_evidence_fails(self):
        """An EXECUTION_WITNESS citing only PORT11A static evidence with empty associated_addresses fails."""
        ob2 = get_obligation("OBLIG-U2-02")
        self.assertIsNotNone(ob2)
        sneak_art = EvidenceArtifact(
            artifact_id="EXEC-WITNESS-PORT11A-ONLY",
            artifact_type="EXECUTION_WITNESS",
            status=ObligationStatus.VERIFIED,
            kind=ObligationKind.RUNTIME,
            description="Purported dynamic witness citing static ROM evidence",
            citation=Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21),
            associated_addresses=(),  # empty addresses!
            how_captured="Dynamic execution trace",
        )
        single_eval = evaluate_obligation(ob2, evidence=sneak_art, repo_root=REPO_ROOT)
        self.assertFalse(single_eval.is_satisfied)
        self.assertIn(RULE_STATIC_CANNOT_DISCHARGE_RUNTIME, [f.rule_id for f in single_eval.findings])

        res = evaluate(DEFAULT_U2_OBLIGATIONS, evidence={"OBLIG-U2-02": sneak_art}, repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.status, "not-ready")
        self.assertIn(RULE_STATIC_CANNOT_DISCHARGE_RUNTIME, [f.rule_id for f in res.findings])

    def test_static_entry_evidence_cannot_discharge_any_runtime_obligation(self):
        """Static entry evidence (0xFC0BD071) CANNOT discharge any runtime obligation."""
        runtime_obs = [ob for ob in DEFAULT_U2_OBLIGATIONS if ob.is_runtime]
        self.assertEqual(len(runtime_obs), 7)

        for ob in runtime_obs:
            with self.subTest(obligation_id=ob.id):
                res = evaluate([ob], evidence={ob.id: self.static_entry_evidence}, repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready, f"Static evidence must NOT satisfy runtime obligation {ob.id}")
                self.assertEqual(res.status, "not-ready")
                self.assertGreaterEqual(res.error_count, 1)
                rule_ids = [f.rule_id for f in res.findings]
                self.assertIn(RULE_STATIC_CANNOT_DISCHARGE_RUNTIME, rule_ids)

    def test_static_evidence_detection_variants(self):
        """Various representations of static evidence are recognized and rejected for runtime."""
        runtime_ob = get_obligation("OBLIG-U2-05")  # Ordering relative to first CHDK file access
        self.assertIsNotNone(runtime_ob)

        variants = [
            EvidenceArtifact(
                artifact_id="VAR-1",
                artifact_type="STATIC_ROM_SLICE",
                status=ObligationStatus.VERIFIED,
                kind=ObligationKind.STATIC,
            ),
            EvidenceArtifact(
                artifact_id="VAR-2",
                artifact_type="ROM_DISASSEMBLY",
                status=ObligationStatus.VERIFIED,
                kind=ObligationKind.RUNTIME,  # Mislabeled kind, but static artifact_type
            ),
            EvidenceArtifact(
                artifact_id="VAR-3",
                artifact_type="DYNAMIC_TRACE",
                status=ObligationStatus.VERIFIED,
                associated_addresses=("0xFC0BD071",),  # References static entry address
            ),
            EvidenceArtifact(
                artifact_id="VAR-4",
                artifact_type="LOG",
                status=ObligationStatus.VERIFIED,
                how_captured="Static offline inspection of PRIMARY.BIN",
            ),
        ]

        for ev in variants:
            with self.subTest(artifact_id=ev.artifact_id):
                self.assertTrue(is_static_evidence(ev))
                res = evaluate([runtime_ob], evidence={runtime_ob.id: ev}, repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready)
                rule_ids = [f.rule_id for f in res.findings]
                self.assertIn(RULE_STATIC_CANNOT_DISCHARGE_RUNTIME, rule_ids)


class TestCitationValidationFailClosed(unittest.TestCase):
    """Verify that evaluate() fails closed on citation integrity violations."""

    def test_missing_citations_cause_failure(self):
        """An obligation with no citations or empty citations fails closed."""
        # Empty citations tuple
        ob_empty = U2Obligation(
            id="TEST-EMPTY-CIT",
            statement="Test obligation with no citations",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence(artifact_type="TEST", what_it_must_show="test"),
            citations=(),
        )
        res1 = evaluate([ob_empty], repo_root=REPO_ROOT)
        self.assertFalse(res1.is_ready)
        self.assertIn(RULE_MISSING_CITATIONS, [f.rule_id for f in res1.findings])

        # Citation with empty path
        ob_blank_path = U2Obligation(
            id="TEST-BLANK-PATH",
            statement="Test obligation with empty citation path",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence(artifact_type="TEST", what_it_must_show="test"),
            citations=(Citation(path="   "),),
        )
        res2 = evaluate([ob_blank_path], repo_root=REPO_ROOT)
        self.assertFalse(res2.is_ready)
        self.assertIn(RULE_MISSING_CITATIONS, [f.rule_id for f in res2.findings])

    def test_untracked_citations_cause_failure(self):
        """Citations to untracked paths fail closed with RULE_UNTRACKED_PATH."""
        # Ranma's untracked file from historical 1.10E
        ob_untracked = U2Obligation(
            id="TEST-UNTRACKED-01",
            statement="Citing untracked historical platform boot.c",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence(artifact_type="TEST", what_it_must_show="test"),
            citations=(Citation(path="platform/g3x/sub/110e/boot.c", line=493),),
        )
        res = evaluate([ob_untracked], repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertIn(RULE_UNTRACKED_PATH, [f.rule_id for f in res.findings])

    def test_local_only_citations_cause_failure(self):
        """Citations to local-only paths (firmware/ dumps, PORT-9A L1/L2) fail closed."""
        # Case A: Local firmware dump
        ob_firmware = U2Obligation(
            id="TEST-LOCAL-FW",
            statement="Citing local-only PRIMARY.BIN dump",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence(artifact_type="TEST", what_it_must_show="test"),
            citations=(Citation(path="firmware/dumps/GM1.10C/PRIMARY.BIN"),),
        )
        res_a = evaluate([ob_firmware], repo_root=REPO_ROOT)
        self.assertFalse(res_a.is_ready)
        self.assertIn(RULE_FORBIDDEN_LOCAL_PATH, [f.rule_id for f in res_a.findings])

        # Case B: PORT-9A L1/L2 local notes
        ob_l1 = U2Obligation(
            id="TEST-LOCAL-L1",
            statement="Citing PORT-9A L1/L2 local workspace notes",
            kind=ObligationKind.STATIC,
            status=ObligationStatus.VERIFIED,
            required_evidence=RequiredEvidence(artifact_type="TEST", what_it_must_show="test"),
            citations=(Citation(path="docs/PORT-9A_L1_notes.txt"),),
        )
        res_b = evaluate([ob_l1], repo_root=REPO_ROOT)
        self.assertFalse(res_b.is_ready)
        self.assertIn(RULE_FORBIDDEN_LOCAL_PATH, [f.rule_id for f in res_b.findings])

    def test_runtime_obligations_with_missing_citations_fail(self):
        """VERIFIED/RUNTIME artifacts for all seven runtime obligations with missing citations give not-ready."""
        runtime_obs = [ob for ob in DEFAULT_U2_OBLIGATIONS if ob.is_runtime]
        self.assertEqual(len(runtime_obs), 7)
        for ob in runtime_obs:
            with self.subTest(obligation_id=ob.id):
                art = EvidenceArtifact(
                    artifact_id=f"MISSING-CIT-{ob.id}",
                    artifact_type=ob.required_evidence.artifact_type,
                    status=ObligationStatus.VERIFIED,
                    kind=ObligationKind.RUNTIME,
                    citation=None,  # Missing citation
                )
                single_eval = evaluate_obligation(ob, evidence=art, repo_root=REPO_ROOT)
                self.assertFalse(single_eval.is_satisfied)
                self.assertIn(RULE_MISSING_CITATIONS, [f.rule_id for f in single_eval.findings])

                res = evaluate(DEFAULT_U2_OBLIGATIONS, evidence={ob.id: art}, repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready)
                self.assertEqual(res.status, "not-ready")
                self.assertIn(RULE_MISSING_CITATIONS, [f.rule_id for f in res.findings])

    def test_runtime_obligations_with_untracked_citations_fail(self):
        """VERIFIED/RUNTIME artifacts for all seven runtime obligations with untracked citations give not-ready."""
        runtime_obs = [ob for ob in DEFAULT_U2_OBLIGATIONS if ob.is_runtime]
        self.assertEqual(len(runtime_obs), 7)
        for ob in runtime_obs:
            with self.subTest(obligation_id=ob.id):
                art = EvidenceArtifact(
                    artifact_id=f"UNTRACKED-CIT-{ob.id}",
                    artifact_type=ob.required_evidence.artifact_type,
                    status=ObligationStatus.VERIFIED,
                    kind=ObligationKind.RUNTIME,
                    citation=Citation(path="untracked/bogus_runtime_witness.txt", line=1),
                )
                single_eval = evaluate_obligation(ob, evidence=art, repo_root=REPO_ROOT)
                self.assertFalse(single_eval.is_satisfied)
                self.assertIn(RULE_UNTRACKED_PATH, [f.rule_id for f in single_eval.findings])

                res = evaluate(DEFAULT_U2_OBLIGATIONS, evidence={ob.id: art}, repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready)
                self.assertEqual(res.status, "not-ready")
                self.assertIn(RULE_UNTRACKED_PATH, [f.rule_id for f in res.findings])

    def test_runtime_obligations_with_forbidden_firmware_citations_fail(self):
        """VERIFIED/RUNTIME artifacts for all seven runtime obligations with firmware/ citations give not-ready."""
        runtime_obs = [ob for ob in DEFAULT_U2_OBLIGATIONS if ob.is_runtime]
        self.assertEqual(len(runtime_obs), 7)
        for ob in runtime_obs:
            with self.subTest(obligation_id=ob.id):
                art = EvidenceArtifact(
                    artifact_id=f"FW-CIT-{ob.id}",
                    artifact_type=ob.required_evidence.artifact_type,
                    status=ObligationStatus.VERIFIED,
                    kind=ObligationKind.RUNTIME,
                    citation=Citation(path="firmware/dumps/GM1.10C/PRIMARY.BIN", line=1),
                )
                single_eval = evaluate_obligation(ob, evidence=art, repo_root=REPO_ROOT)
                self.assertFalse(single_eval.is_satisfied)
                self.assertIn(RULE_FORBIDDEN_LOCAL_PATH, [f.rule_id for f in single_eval.findings])

                res = evaluate(DEFAULT_U2_OBLIGATIONS, evidence={ob.id: art}, repo_root=REPO_ROOT)
                self.assertFalse(res.is_ready)
                self.assertEqual(res.status, "not-ready")
                self.assertIn(RULE_FORBIDDEN_LOCAL_PATH, [f.rule_id for f in res.findings])

    def test_artifact_type_mismatch_fails(self):
        """Evidence artifact with mismatched artifact_type must fail closed."""
        ob2 = get_obligation("OBLIG-U2-02")
        self.assertIsNotNone(ob2)
        # OBLIG-U2-02 requires EXECUTION_WITNESS; provide STORAGE_MOUNT_PROOF instead
        mismatched_art = EvidenceArtifact(
            artifact_id="MISMATCH-TYPE-02",
            artifact_type="STORAGE_MOUNT_PROOF",
            status=ObligationStatus.VERIFIED,
            kind=ObligationKind.RUNTIME,
            citation=Citation(path="tools/port9a_runtime_lifecycle.py", line=296),
        )
        single_eval = evaluate_obligation(ob2, evidence=mismatched_art, repo_root=REPO_ROOT)
        self.assertFalse(single_eval.is_satisfied)
        self.assertIn(RULE_ARTIFACT_TYPE_MISMATCH, [f.rule_id for f in single_eval.findings])

        res = evaluate(DEFAULT_U2_OBLIGATIONS, evidence={"OBLIG-U2-02": mismatched_art}, repo_root=REPO_ROOT)
        self.assertFalse(res.is_ready)
        self.assertEqual(res.status, "not-ready")
        self.assertIn(RULE_ARTIFACT_TYPE_MISMATCH, [f.rule_id for f in res.findings])

    def test_missing_file_on_disk_fails_closed(self):
        """A cited file that does not exist on disk fails closed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            ob = get_obligation("OBLIG-U2-01")
            self.assertIsNotNone(ob)
            res = evaluate([ob], repo_root=tmp_root, check_disk=True)
            self.assertFalse(res.is_ready)
            self.assertIn(RULE_MISSING_CITED_PATH, [f.rule_id for f in res.findings])

    def test_tampered_content_hash_fails_closed(self):
        """Tampered content at a pinned path fails content authentication."""
        ob = get_obligation("OBLIG-U2-01")
        self.assertIsNotNone(ob)

        def corrupted_reader(p: Path) -> bytes:
            return b"CORRUPTED_ROM_EVIDENCE_BYTES_0xDEADBEEF"

        res = evaluate([ob], repo_root=REPO_ROOT, file_reader=corrupted_reader)
        self.assertFalse(res.is_ready)
        self.assertIn(RULE_CONTENT_HASH_MISMATCH, [f.rule_id for f in res.findings])


class TestAgreementWithPort9aAndPort9bModels(unittest.TestCase):
    """Verify consistency with PORT-9A model and PORT-9B I2 contract."""

    def test_port9a_preconditions_invariant(self):
        """Invariant: GM110C runtime precondition flag MUST remain False in Phase 0."""
        self.assertFalse(
            rt.GM110C_PRECONDITIONS.init_file_modules_entry_verified,
            "GM110C_PRECONDITIONS.init_file_modules_entry_verified must remain False in Phase 0.",
        )

    def test_port9a_static_evidence_profile(self):
        """Verify static ROM entry is decoupled from dynamic mount readiness in PORT-9A."""
        self.assertEqual(
            rt.GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry,
            rt.EvidenceStatus.STATIC_VERIFIED,
            "Static entry vector 0xFC0BD071 must be STATIC_VERIFIED in PORT-9A.",
        )
        self.assertEqual(
            rt.GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness,
            rt.EvidenceStatus.UNKNOWN,
            "SD/FAT mount readiness must remain UNKNOWN in PORT-9A.",
        )

    def test_port9b_fact_u2_consistency(self):
        """Verify that PORT-9B Fact U2 is defined and references init_file_modules_entry_verified."""
        u2_facts = [f for f in p9b.UNVERIFIED_RUNTIME_FACTS if f[0] == "U2"]
        self.assertEqual(len(u2_facts), 1)
        fid, flag, desc = u2_facts[0]
        self.assertEqual(flag, "init_file_modules_entry_verified")
        self.assertIn("InitFileModules", desc)

    def test_port9a_six_stage_promotion_contract_completeness(self):
        """Verify all six promotion stages are present in FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS and mapped with tracked lines."""
        stages = [stage for stage, _ in rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS]
        expected_stages = [
            "task_created",
            "task_started",
            "init_returned_normally",
            "mount_observed",
            "fs_io_ready",
            "warm_restart_safe",
        ]
        self.assertEqual(stages, expected_stages)

        # Read port9a lines to verify each line number in PORT9A_SIX_STAGE_CORRESPONDENCE is exact
        port9a_lines = (REPO_ROOT / "tools/port9a_runtime_lifecycle.py").read_text(encoding="utf-8").splitlines()

        for stage_name, info in PORT9A_SIX_STAGE_CORRESPONDENCE.items():
            line_no = info["port9a_line"]
            # line_no is 1-indexed
            line_text = port9a_lines[line_no - 1]
            self.assertIn(
                stage_name,
                line_text,
                f"Stage {stage_name} expected on line {line_no} of tools/port9a_runtime_lifecycle.py, got: {line_text}",
            )
            for ob_id in info["obligation_ids"]:
                ob = get_obligation(ob_id)
                self.assertIsNotNone(ob, f"Mapped obligation {ob_id} for stage {stage_name} not found")

        # Verify stage 3 (init_returned_normally) maps to OBLIG-U2-03
        ob3 = get_obligation("OBLIG-U2-03")
        self.assertIsNotNone(ob3)
        self.assertEqual(ob3.required_evidence.artifact_type, "COMPLETION_WITNESS")
        self.assertIn("sub_fc0d9ccc and sub_fc0d9cf6", ob3.statement)
        self.assertIn("r0==0", ob3.statement)

        # Verify stage 4 (mount_observed) maps to OBLIG-U2-04
        ob4 = get_obligation("OBLIG-U2-04")
        self.assertIsNotNone(ob4)
        self.assertEqual(ob4.required_evidence.artifact_type, "STORAGE_MOUNT_PROOF")
        self.assertIn("0x5006", ob4.statement)

    def test_verify_i2_contract_consistency_helper(self):
        """Contract consistency helper must succeed against tracked repository code."""
        ok, errors = verify_i2_contract_consistency()
        self.assertTrue(ok, f"Contract consistency check failed: {errors}")
        self.assertEqual(errors, [])

    def test_tools_port9a_and_port9b_are_unmodified(self):
        """tools/port9a_runtime_lifecycle.py and tools/port9b_runtime_contract.py must match pinned hashes."""
        p9a_bytes = (REPO_ROOT / "tools/port9a_runtime_lifecycle.py").read_bytes()
        p9b_bytes = (REPO_ROOT / "tools/port9b_runtime_contract.py").read_bytes()

        self.assertEqual(
            hashlib.sha256(p9a_bytes).hexdigest().lower(),
            PINNED_FILE_HASHES["tools/port9a_runtime_lifecycle.py"].lower(),
            "tools/port9a_runtime_lifecycle.py has been modified!",
        )
        self.assertEqual(
            hashlib.sha256(p9b_bytes).hexdigest().lower(),
            PINNED_FILE_HASHES["tools/port9b_runtime_contract.py"].lower(),
            "tools/port9b_runtime_contract.py has been modified!",
        )


class TestAddressProvenanceAndIntegrity(unittest.TestCase):
    """Verify that no new firmware addresses exist and all cited addresses are tracked."""

    def test_all_addresses_cited_in_tracked_docs(self):
        """verify_address_provenance() must pass without errors."""
        ok, errors = verify_address_provenance(repo_root=REPO_ROOT)
        self.assertTrue(ok, f"Address provenance check failed: {errors}")
        self.assertEqual(errors, [])

    def test_address_registration_completeness(self):
        """All critical U2 firmware addresses must be registered in TRACKED_ADDRESS_CITATIONS."""
        critical_addrs = (
            "0xFC0BD071",  # Thumb entry pointer
            "0xFC0BD070",  # Entry instruction address
            "0xFC0BD0B4",  # Creator function
            "0xFC0BD072",  # Call to sub_fc0d9ccc
            "0xFC0BD078",  # Load event 0x5006
            "0xFC0BD086",  # Call to sub_fc0d9cf6
            "0xFC0D9CCC",  # Callee 1
            "0xFC0D9CF2",  # movs r0, #0
            "0xFC0D9CF6",  # Callee 2
            "0xFC35B93C",  # Event dispatch target
            "0xFC0BD049",  # Contradicted historical entry
        )
        for addr in critical_addrs:
            self.assertIn(addr, TRACKED_ADDRESS_CITATIONS, f"Critical address {addr} not registered")


class TestSecurityAndScopeBoundaries(unittest.TestCase):
    """Enforce standard library only and no subprocess imports."""

    def test_no_subprocess_imported(self):
        """tools/port13_u2_obligations.py must not import subprocess."""
        self.assertNotIn("subprocess", sys.modules[u2.__name__].__dict__)

    def test_standard_library_only(self):
        """tools/port13_u2_obligations.py must only import standard library modules."""
        forbidden_modules = ("pytest", "requests", "capstone", "ghidra", "keystone", "numpy")
        for mod in forbidden_modules:
            self.assertNotIn(mod, sys.modules[u2.__name__].__dict__)

    def test_all_obligations_serialize_to_dict_and_json(self):
        """All obligations and evaluation results serialize cleanly to JSON."""
        res = evaluate(repo_root=REPO_ROOT)
        d = res.to_dict()
        self.assertEqual(d["is_ready"], False)
        self.assertEqual(d["status"], "not-ready")
        raw_json = json.dumps(d, indent=2)
        self.assertIn("OBLIG-U2-01", raw_json)
        self.assertIn("OBLIG-U2-08", raw_json)


if __name__ == "__main__":
    unittest.main()
