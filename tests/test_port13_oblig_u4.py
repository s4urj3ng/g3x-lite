#!/usr/bin/env python3
"""tests/test_port13_oblig_u4.py

Unit tests for U4 SpyTask launch dependencies proof obligations (PORT-13).
Verifies:
  - Catalog schema, valid citations to tracked files, and completeness.
  - Fail-closed baseline evaluation: any unverified obligation returns NOT_SATISFIED,
    and overall U4 verdict is strictly NOT_SATISFIED for GM1.10C today.
  - Static evidence (CreateTask veneer 0xFC31BBC4 -> ATCM 0xBFE14A3C, PhySw Thumb
    entry 0xFC1283AD) NEVER satisfies runtime hook placement, task launch ordering,
    or runtime readiness obligations.
  - Evidence provenance classification: genuine runtime evidence referencing anchor
    addresses (such as 0xBFE14A3C) is NOT rejected as static.
  - Completeness validation: evaluate_u4_obligations requires exact canonical IDs
    OBLIG-U4-01..09 and raises ValueError on empty, missing, duplicate, or unknown IDs.
  - The legacy-timeout-bypass -> storage corruption/kernel panic causal link remains UNKNOWN.
  - Fail-closed containment on partial satisfaction, unverified evidence, and mismatched types.
  - Positive synthetic path when all obligations are provided with valid runtime evidence.
  - No new firmware addresses or offsets are introduced.

Standard library only.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.port13_oblig_u4 import (
    CANONICAL_OBLIGATION_IDS,
    Domain,
    EvaluationVerdict,
    EvidenceArtifact,
    ObligationResult,
    ObligationStatus,
    RequiredEvidence,
    STATIC_ANCHOR_CREATETASK_VENEER,
    STATIC_ANCHOR_PHYSW_THUMB_ENTRY,
    U4_OBLIGATIONS,
    U4Obligation,
    evaluate_obligation,
    evaluate_u4_obligations,
    get_obligation,
    is_empirical_evidence,
    is_static_evidence,
    is_static_veneer_or_entry_evidence,
)


class TestPort13ObligU4(unittest.TestCase):
    """Offline test suite for U4 SpyTask launch proof obligations."""

    def test_u4_obligations_catalog_structure_and_citations(self):
        """Invariant: All 11 obligations have valid schema, statuses, and tracked citations."""
        self.assertEqual(len(U4_OBLIGATIONS), 11, "Expected 11 canonical U4 obligations.")
        self.assertEqual(
            tuple(o.id for o in U4_OBLIGATIONS),
            CANONICAL_OBLIGATION_IDS,
            "Catalog IDs must match CANONICAL_OBLIGATION_IDS in order.",
        )
        ids_seen = set()

        for oblig in U4_OBLIGATIONS:
            # Check ID format
            self.assertRegex(oblig.id, r"^OBLIG-U4-\d{2}$", f"Invalid ID format: {oblig.id}")
            self.assertNotIn(oblig.id, ids_seen, f"Duplicate ID: {oblig.id}")
            ids_seen.add(oblig.id)

            # Check statements and required evidence
            self.assertTrue(oblig.statement.strip(), f"Empty statement in {oblig.id}")
            self.assertTrue(oblig.required_evidence.artifact_type.strip(), f"Empty artifact_type in {oblig.id}")
            self.assertTrue(oblig.required_evidence.what_it_must_show.strip(), f"Empty what_it_must_show in {oblig.id}")

            # Check status
            self.assertIsInstance(oblig.current_status, ObligationStatus)
            # In baseline GM1.10C, all 11 obligations must be UNKNOWN
            self.assertEqual(
                oblig.current_status,
                ObligationStatus.UNKNOWN,
                f"Obligation {oblig.id} must be UNKNOWN in GM1.10C baseline.",
            )

            # Check citation to tracked files
            self.assertIn(":", oblig.citation, f"Citation must have file:lines in {oblig.id}")
            cited_files = [c.split(":")[0].strip() for c in oblig.citation.split(";")]
            for cited_file in cited_files:
                target_path = REPO_ROOT / cited_file
                self.assertTrue(
                    target_path.is_file(),
                    f"Cited file '{cited_file}' in {oblig.id} must exist in repository.",
                )

        # Check explicit runtime evidence requirements
        runtime_flagged = {o.id for o in U4_OBLIGATIONS if o.requires_runtime_evidence}
        expected_runtime = {
            "OBLIG-U4-01",
            "OBLIG-U4-02",
            "OBLIG-U4-05",
            "OBLIG-U4-07",
            "OBLIG-U4-09",
            "OBLIG-U4-10",
            "OBLIG-U4-11",
        }
        self.assertEqual(
            runtime_flagged,
            expected_runtime,
            f"Expected runtime-flagged obligations to be {expected_runtime}, got {runtime_flagged}",
        )

    def test_baseline_evaluator_fails_closed(self):
        """Invariant: In GM1.10C baseline, every obligation evaluates as NOT_SATISFIED, overall NOT_SATISFIED."""
        report = evaluate_u4_obligations()

        self.assertEqual(
            report.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "Overall U4 verdict for GM1.10C today must be NOT_SATISFIED.",
        )
        self.assertTrue(report.is_fail_closed, "Report must report fail-closed active.")
        self.assertEqual(report.satisfied_count, 0, "No obligation may be satisfied in GM1.10C baseline.")
        self.assertEqual(
            report.not_satisfied_count,
            len(U4_OBLIGATIONS),
            f"All {len(U4_OBLIGATIONS)} obligations must be NOT_SATISFIED.",
        )

        for result in report.results:
            self.assertEqual(
                result.verdict,
                EvaluationVerdict.NOT_SATISFIED,
                f"Obligation {result.obligation_id} must evaluate to NOT_SATISFIED.",
            )
            self.assertIn("fails closed", result.reason)

    def test_static_veneer_evidence_cannot_satisfy_runtime_hook_placement(self):
        """Explicit Test: CreateTask veneer (0xFC31BBC4 -> 0xBFE14A3C) CANNOT satisfy runtime hook placement."""
        oblig = get_obligation("OBLIG-U4-02")
        self.assertIsNotNone(oblig)
        self.assertTrue(oblig.requires_runtime_evidence)
        self.assertEqual(oblig.domain, Domain.RUNTIME_HOOK_PLACEMENT)

        # Construct synthetic evidence containing the static veneer address
        static_veneer_evidence = EvidenceArtifact(
            artifact_id="STATIC-VENEER-01",
            artifact_type="STATIC_ROM_DISASSEMBLY",
            status=ObligationStatus.VERIFIED,
            description="CreateTask veneer 0xFC31BBC4 -> ATCM 0xBFE14A3C in Slice S1B",
            citation="docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 61-62",
            is_static=True,
            associated_addresses=("0xFC31BBC4", "0xBFE14A3C"),
            how_captured="static_rom_disassembly",
        )

        res = evaluate_obligation(oblig, static_veneer_evidence)
        self.assertEqual(
            res.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "Static CreateTask veneer evidence must NEVER satisfy runtime hook placement.",
        )
        self.assertIn("Static evidence", res.reason)
        self.assertIn("cannot satisfy runtime hook placement", res.reason)

    def test_static_physw_entry_evidence_cannot_satisfy_launch_ordering(self):
        """Explicit Test: PhySw Thumb entry (0xFC1283AD) CANNOT satisfy SpyTask launch ordering."""
        oblig = get_obligation("OBLIG-U4-01")
        self.assertIsNotNone(oblig)
        self.assertTrue(oblig.requires_runtime_evidence)
        self.assertEqual(oblig.domain, Domain.LAUNCH_ORDERING)

        # Construct synthetic evidence containing the static PhySw entry
        static_physw_evidence = EvidenceArtifact(
            artifact_id="STATIC-PHYSW-01",
            artifact_type="STATIC_ENTRY_REFERENCE",
            status=ObligationStatus.VERIFIED,
            description="PhySw Thumb entry 0xFC1283AD in Slice S3B",
            citation="docs/PORT11A_GM110C_ROM_EVIDENCE.md:22, 314",
            is_static=True,
            associated_addresses=("0xFC1283AD",),
            how_captured="static_rom_disassembly",
        )

        res = evaluate_obligation(oblig, static_physw_evidence)
        self.assertEqual(
            res.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "Static PhySw Thumb entry evidence must NEVER satisfy SpyTask launch ordering.",
        )
        self.assertIn("Static evidence", res.reason)
        self.assertIn("cannot satisfy runtime hook placement or launch-ordering", res.reason)

    def test_oblig_u4_05_with_static_evidence_stays_not_satisfied(self):
        """Regression Test [P1]: OBLIG-U4-05 with is_static=True evidence stays NOT_SATISFIED."""
        oblig = get_obligation("OBLIG-U4-05")
        self.assertIsNotNone(oblig)
        self.assertTrue(
            oblig.requires_runtime_evidence,
            "OBLIG-U4-05 must be explicitly marked with requires_runtime_evidence=True.",
        )
        self.assertEqual(oblig.domain, Domain.FS_GATING)

        # Construct verified artifact matching required type LIFECYCLE_STATE_TRACE, but is_static=True
        static_trace_evidence = EvidenceArtifact(
            artifact_id="STATIC-TRACE-01",
            artifact_type="LIFECYCLE_STATE_TRACE",
            status=ObligationStatus.VERIFIED,
            description="Static lifecycle trace referencing 0xFC31BBC4 -> ATCM 0xBFE14A3C",
            citation="docs/PORT13_REVIEW_U4.md:92-96",
            is_static=True,
            associated_addresses=("0xFC31BBC4", "0xBFE14A3C"),
            how_captured="static_disassembly",
        )

        res = evaluate_obligation(oblig, static_trace_evidence)
        self.assertEqual(
            res.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "OBLIG-U4-05 with is_static=True evidence must evaluate to NOT_SATISFIED.",
        )
        self.assertEqual(res.status, ObligationStatus.UNKNOWN)
        self.assertIn("Static evidence", res.reason)

    def test_oblig_u4_09_with_static_evidence_evaluates_not_satisfied(self):
        """Negative Test [P1]: OBLIG-U4-09 rejects static CONTINUATION_TRACE evidence."""
        oblig = get_obligation("OBLIG-U4-09")
        self.assertIsNotNone(oblig)
        self.assertTrue(
            oblig.requires_runtime_evidence,
            "OBLIG-U4-09 must be explicitly marked with requires_runtime_evidence=True.",
        )
        self.assertEqual(oblig.domain, Domain.CONTINUATION)

        static_continuation_evidence = EvidenceArtifact(
            artifact_id="STATIC-CONT-01",
            artifact_type="CONTINUATION_TRACE",
            status=ObligationStatus.VERIFIED,
            description="Static tail branch opcode match b.w sub_fc0d0126 at boot_prototype.c:434",
            citation="docs/PORT13_REVIEW_U4.md:126-129, 181, 281, 302",
            is_static=True,
            how_captured="static_disassembly",
        )

        res = evaluate_obligation(oblig, static_continuation_evidence)
        self.assertEqual(
            res.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "OBLIG-U4-09 with is_static=True evidence must evaluate to NOT_SATISFIED.",
        )
        self.assertEqual(res.status, ObligationStatus.UNKNOWN)
        self.assertIn("Static evidence", res.reason)

    def test_all_runtime_flagged_obligations_reject_static_evidence(self):
        """Regression Test [P1]: Loop over every runtime-flagged obligation and verify static evidence rejection."""
        runtime_obligations = [o for o in U4_OBLIGATIONS if o.requires_runtime_evidence]
        self.assertGreater(
            len(runtime_obligations),
            0,
            "Expected at least one obligation with requires_runtime_evidence=True.",
        )

        for oblig in runtime_obligations:
            static_evidence = EvidenceArtifact(
                artifact_id=f"STATIC-{oblig.id}",
                artifact_type=oblig.required_evidence.artifact_type,
                status=ObligationStatus.VERIFIED,
                description=f"Static evidence artifact attempting to satisfy {oblig.id}",
                citation=oblig.citation,
                is_static=True,
                associated_addresses=("0xFC31BBC4", "0xBFE14A3C"),
                how_captured="static_disassembly",
            )
            res = evaluate_obligation(oblig, static_evidence)
            self.assertEqual(
                res.verdict,
                EvaluationVerdict.NOT_SATISFIED,
                f"Obligation {oblig.id} requires runtime evidence but accepted is_static=True evidence!",
            )
            self.assertEqual(res.status, ObligationStatus.UNKNOWN)
            self.assertIn("Static evidence", res.reason)

    def test_genuine_runtime_hook_safety_evidence_referencing_atcm_is_eligible(self):
        """Provenance Test [P2]: Genuine runtime HOOK_SAFETY_EVIDENCE referencing ATCM address 0xBFE14A3C is eligible."""
        oblig = get_obligation("OBLIG-U4-02")
        self.assertIsNotNone(oblig)
        self.assertTrue(oblig.requires_runtime_evidence)

        # Genuine runtime evidence with is_static=False referencing ATCM address 0xBFE14A3C
        runtime_evidence = EvidenceArtifact(
            artifact_id="RUNTIME-HOOK-SAFETY-01",
            artifact_type="HOOK_SAFETY_EVIDENCE",
            status=ObligationStatus.VERIFIED,
            description="Dynamic trace of ATCM 0xBFE14A3C hook installation with cache flush and IRQ safety",
            citation="docs/PORT13_REVIEW_U4.md:41-46",
            is_static=False,
            associated_addresses=("0xBFE14A3C",),
            how_captured="runtime_execution_trace",
        )

        # Evidence should NOT be classified as static based on mentioning 0xBFE14A3C
        self.assertFalse(
            is_static_evidence(runtime_evidence),
            "Genuine runtime evidence with is_static=False must NOT be classified as static.",
        )

        res = evaluate_obligation(oblig, runtime_evidence)
        self.assertEqual(
            res.verdict,
            EvaluationVerdict.SATISFIED,
            "Genuine runtime evidence with is_static=False referencing ATCM 0xBFE14A3C must evaluate to SATISFIED.",
        )
        self.assertEqual(res.status, ObligationStatus.VERIFIED)

    def test_evaluate_u4_obligations_canonical_set_validation(self):
        """Completeness Tests [P2]: evaluate_u4_obligations enforces complete canonical ID set."""
        # 1. Empty set must raise ValueError
        with self.assertRaises(ValueError) as ctx_empty:
            evaluate_u4_obligations(obligations=())
        self.assertIn("empty", str(ctx_empty.exception).lower())

        # 2. Missing ID (subset) must raise ValueError
        subset = tuple(o for o in U4_OBLIGATIONS if o.id != "OBLIG-U4-01")
        self.assertEqual(len(subset), 10)
        with self.assertRaises(ValueError) as ctx_missing:
            evaluate_u4_obligations(obligations=subset)
        self.assertIn("missing", str(ctx_missing.exception).lower())
        self.assertIn("OBLIG-U4-01", str(ctx_missing.exception))

        # Check subset missing OBLIG-U4-10
        subset_10 = tuple(o for o in U4_OBLIGATIONS if o.id != "OBLIG-U4-10")
        self.assertEqual(len(subset_10), 10)
        with self.assertRaises(ValueError) as ctx_missing_10:
            evaluate_u4_obligations(obligations=subset_10)
        self.assertIn("missing", str(ctx_missing_10.exception).lower())
        self.assertIn("OBLIG-U4-10", str(ctx_missing_10.exception))

        # Check subset missing OBLIG-U4-11
        subset_11 = tuple(o for o in U4_OBLIGATIONS if o.id != "OBLIG-U4-11")
        self.assertEqual(len(subset_11), 10)
        with self.assertRaises(ValueError) as ctx_missing_11:
            evaluate_u4_obligations(obligations=subset_11)
        self.assertIn("missing", str(ctx_missing_11.exception).lower())
        self.assertIn("OBLIG-U4-11", str(ctx_missing_11.exception))

        # 3. Duplicate ID must raise ValueError
        duplicates = list(U4_OBLIGATIONS)
        duplicates.append(U4_OBLIGATIONS[0])  # Duplicate OBLIG-U4-01
        with self.assertRaises(ValueError) as ctx_dup:
            evaluate_u4_obligations(obligations=tuple(duplicates))
        self.assertIn("duplicate", str(ctx_dup.exception).lower())
        self.assertIn("OBLIG-U4-01", str(ctx_dup.exception))

        # 4. Unknown ID must raise ValueError
        bogus_oblig = U4Obligation(
            id="OBLIG-U4-99",
            statement="Bogus obligation outside canonical set",
            required_evidence=RequiredEvidence(artifact_type="NONE", what_it_must_show="None"),
            current_status=ObligationStatus.UNKNOWN,
            citation="docs/PORT13_REVIEW_U4.md:1",
            domain=Domain.LAUNCH_ORDERING,
            requires_runtime_evidence=True,
        )
        unknown_set = list(U4_OBLIGATIONS)[:-1] + [bogus_oblig]
        with self.assertRaises(ValueError) as ctx_unk:
            evaluate_u4_obligations(obligations=tuple(unknown_set))
        self.assertIn("unknown", str(ctx_unk.exception).lower())
        self.assertIn("OBLIG-U4-99", str(ctx_unk.exception))

    def test_timeout_bypass_causal_link_remains_unknown(self):
        """Explicit Test [P1]: C06b legacy-timeout-bypass causal link must remain UNKNOWN (never INFERRED)."""
        oblig = get_obligation("OBLIG-U4-07")
        self.assertIsNotNone(oblig)
        self.assertEqual(oblig.id, "OBLIG-U4-07")
        self.assertEqual(oblig.current_status, ObligationStatus.UNKNOWN)
        self.assertEqual(oblig.domain, Domain.CAUSAL_ANALYSIS)
        self.assertTrue(oblig.requires_runtime_evidence)

        # Baseline evaluation (no evidence): must evaluate to NOT_SATISFIED, UNKNOWN
        baseline_res = evaluate_obligation(oblig)
        self.assertEqual(baseline_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(baseline_res.status, ObligationStatus.UNKNOWN)

        # Case (a): VERIFIED STORAGE_CORRUPTION_TRACE with is_static=True gives status UNKNOWN and NOT_SATISFIED
        static_trace = EvidenceArtifact(
            artifact_id="STATIC-CORRUPT-01",
            artifact_type="STORAGE_CORRUPTION_TRACE",
            status=ObligationStatus.VERIFIED,
            description="Static inspection of storage timeout logic",
            citation="docs/PORT13_REVIEW_U4.md:71-74, 174",
            is_static=True,
            how_captured="static_disassembly",
        )
        static_res = evaluate_obligation(oblig, static_trace)
        self.assertEqual(static_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(static_res.status, ObligationStatus.UNKNOWN)

        # Case (b1): Unverified STORAGE_CORRUPTION_TRACE (status=INFERRED) gives status UNKNOWN, not INFERRED, and NOT_SATISFIED
        inferred_trace = EvidenceArtifact(
            artifact_id="INFERRED-CORRUPT-01",
            artifact_type="STORAGE_CORRUPTION_TRACE",
            status=ObligationStatus.INFERRED,
            description="Inferred causal link between timeout bypass and storage corruption",
            citation="docs/PORT13_REVIEW_U4.md:71-74, 174",
            is_static=False,
            how_captured="historical_analysis",
        )
        inferred_res = evaluate_obligation(oblig, inferred_trace)
        self.assertEqual(inferred_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(inferred_res.status, ObligationStatus.UNKNOWN)
        self.assertNotEqual(inferred_res.status, ObligationStatus.INFERRED)

        # Case (b2): Non-empirical STORAGE_CORRUPTION_TRACE gives status UNKNOWN, not INFERRED, and NOT_SATISFIED
        non_empirical_trace = EvidenceArtifact(
            artifact_id="THEORETICAL-CORRUPT-01",
            artifact_type="STORAGE_CORRUPTION_TRACE",
            status=ObligationStatus.VERIFIED,
            description="Theoretical simulation of filesystem state machine timeout",
            citation="docs/PORT13_REVIEW_U4.md:71-74, 174",
            is_static=False,
            how_captured="theoretical_model",
        )
        non_emp_res = evaluate_obligation(oblig, non_empirical_trace)
        self.assertEqual(non_emp_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(non_emp_res.status, ObligationStatus.UNKNOWN)
        self.assertNotEqual(non_emp_res.status, ObligationStatus.INFERRED)

        # Case (b3): Non-matching artifact type (e.g. historical anecdote) gives status UNKNOWN and NOT_SATISFIED
        speculative_evidence = EvidenceArtifact(
            artifact_id="SPECULATIVE-CLAIM-01",
            artifact_type="HISTORICAL_ANECDOTE",
            status=ObligationStatus.VERIFIED,
            description="Informal claim that timeout caused storage corruptions",
            citation="docs/PORT13_REVIEW_U4.md:71-74",
            is_static=False,
            how_captured="historical_text_mining",
        )
        spec_res = evaluate_obligation(oblig, speculative_evidence)
        self.assertEqual(spec_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(spec_res.status, ObligationStatus.UNKNOWN)

        # Positive Case: Genuine verified empirical runtime crash dump evaluates to SATISFIED
        genuine_trace = EvidenceArtifact(
            artifact_id="EMPIRICAL-CORRUPT-01",
            artifact_type="STORAGE_CORRUPTION_TRACE",
            status=ObligationStatus.VERIFIED,
            description="Empirical hardware crash dump demonstrating storage bus timeout fault",
            citation="docs/PORT13_REVIEW_U4.md:71-74, 174",
            is_static=False,
            how_captured="hardware_crash_dump",
        )
        self.assertTrue(is_empirical_evidence(genuine_trace))
        gen_res = evaluate_obligation(oblig, genuine_trace)
        self.assertEqual(gen_res.verdict, EvaluationVerdict.SATISFIED)
        self.assertEqual(gen_res.status, ObligationStatus.VERIFIED)

    def test_unresolved_c17_or_c18_obligations_block_overall_u4_verdict(self):
        """Catalog completeness [P2]: Overall U4 verdict cannot be SATISFIED while C17 or C18 are unresolved."""
        oblig_10 = get_obligation("OBLIG-U4-10")
        oblig_11 = get_obligation("OBLIG-U4-11")
        self.assertIsNotNone(oblig_10)
        self.assertIsNotNone(oblig_11)
        self.assertTrue(oblig_10.requires_runtime_evidence)
        self.assertTrue(oblig_11.requires_runtime_evidence)
        self.assertEqual(oblig_10.domain, Domain.CONCURRENCY_CONSTRAINTS)
        self.assertEqual(oblig_11.domain, Domain.WARM_RESTART_CLEANUP)

        # Baseline: All obligations UNKNOWN -> NOT_SATISFIED
        baseline_report = evaluate_u4_obligations()
        self.assertEqual(baseline_report.verdict, EvaluationVerdict.NOT_SATISFIED)

        # Build evidence map satisfying OBLIG-U4-01..09
        base_evidence_map = {}
        for oblig in U4_OBLIGATIONS:
            if oblig.id in ("OBLIG-U4-10", "OBLIG-U4-11"):
                continue
            base_evidence_map[oblig.id] = EvidenceArtifact(
                artifact_id=f"SYNTHETIC-{oblig.id}",
                artifact_type=oblig.required_evidence.artifact_type,
                status=ObligationStatus.VERIFIED,
                description=f"Synthetic valid artifact for {oblig.id}",
                citation=oblig.citation,
                is_static=False,
                how_captured="runtime_execution_trace",
            )

        # Case 1: OBLIG-U4-10 and OBLIG-U4-11 unresolved -> NOT_SATISFIED
        report_10_11_unresolved = evaluate_u4_obligations(evidence_map=base_evidence_map)
        self.assertEqual(report_10_11_unresolved.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(report_10_11_unresolved.satisfied_count, 9)
        self.assertEqual(report_10_11_unresolved.not_satisfied_count, 2)
        self.assertTrue(report_10_11_unresolved.is_fail_closed)

        # Case 2: Only OBLIG-U4-11 unresolved (OBLIG-U4-10 satisfied) -> NOT_SATISFIED
        evidence_with_10 = dict(base_evidence_map)
        evidence_with_10["OBLIG-U4-10"] = EvidenceArtifact(
            artifact_id="SYNTHETIC-OBLIG-U4-10",
            artifact_type=oblig_10.required_evidence.artifact_type,
            status=ObligationStatus.VERIFIED,
            description="Synthetic valid yield and interrupt spec",
            citation=oblig_10.citation,
            is_static=False,
            how_captured="runtime_execution_trace",
        )
        report_11_unresolved = evaluate_u4_obligations(evidence_map=evidence_with_10)
        self.assertEqual(report_11_unresolved.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(report_11_unresolved.satisfied_count, 10)
        self.assertEqual(report_11_unresolved.not_satisfied_count, 1)
        self.assertTrue(report_11_unresolved.is_fail_closed)

        # Case 3: Only OBLIG-U4-10 unresolved (OBLIG-U4-11 satisfied) -> NOT_SATISFIED
        evidence_with_11 = dict(base_evidence_map)
        evidence_with_11["OBLIG-U4-11"] = EvidenceArtifact(
            artifact_id="SYNTHETIC-OBLIG-U4-11",
            artifact_type=oblig_11.required_evidence.artifact_type,
            status=ObligationStatus.VERIFIED,
            description="Synthetic valid warm restart semaphore trace",
            citation=oblig_11.citation,
            is_static=False,
            how_captured="runtime_execution_trace",
        )
        report_10_unresolved = evaluate_u4_obligations(evidence_map=evidence_with_11)
        self.assertEqual(report_10_unresolved.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(report_10_unresolved.satisfied_count, 10)
        self.assertEqual(report_10_unresolved.not_satisfied_count, 1)
        self.assertTrue(report_10_unresolved.is_fail_closed)

    def test_unverified_evidence_fails_closed(self):
        """Invariant: Evidence with INFERRED or UNKNOWN status must fail closed."""
        oblig = get_obligation("OBLIG-U4-03")
        self.assertIsNotNone(oblig)

        inferred_evidence = EvidenceArtifact(
            artifact_id="INFERRED-SCHED-01",
            artifact_type="RTOS_SCHEDULER_SPEC",
            status=ObligationStatus.INFERRED,
            description="Inferred DryOS priority scheduling behavior",
            citation="docs/PORT13_REVIEW_U4.md:108-112",
            is_static=False,
            how_captured="static_analysis",
        )
        res = evaluate_obligation(oblig, inferred_evidence)
        self.assertEqual(res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertIn("fails closed without VERIFIED evidence", res.reason)

    def test_mismatched_artifact_type_fails_closed(self):
        """Invariant: Verified evidence of wrong artifact type must fail closed."""
        oblig = get_obligation("OBLIG-U4-04")
        self.assertIsNotNone(oblig)
        self.assertEqual(oblig.required_evidence.artifact_type, "KERNEL_HEAP_SPEC")

        wrong_type_evidence = EvidenceArtifact(
            artifact_id="WRONG-TYPE-01",
            artifact_type="TASK_CONTEXT_EVIDENCE",  # Mismatch
            status=ObligationStatus.VERIFIED,
            description="Verified context evidence, but wrong type for heap obligation",
            citation="docs/PORT13_REVIEW_U4.md:121-125",
            is_static=False,
            how_captured="disassembly",
        )
        res = evaluate_obligation(oblig, wrong_type_evidence)
        self.assertEqual(res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertIn("does not match required artifact type", res.reason)

    def test_partial_satisfaction_fails_closed(self):
        """Invariant: If 10 of 11 obligations are satisfied, overall verdict remains NOT_SATISFIED."""
        evidence_map = {}
        # Satisfy 10 obligations with valid synthetic runtime artifacts
        for oblig in U4_OBLIGATIONS:
            if oblig.id == "OBLIG-U4-01":
                continue  # Leave OBLIG-U4-01 unsatisfied
            evidence_map[oblig.id] = EvidenceArtifact(
                artifact_id=f"SYNTHETIC-{oblig.id}",
                artifact_type=oblig.required_evidence.artifact_type,
                status=ObligationStatus.VERIFIED,
                description=f"Synthetic valid artifact for {oblig.id}",
                citation=oblig.citation,
                is_static=False,
                how_captured="runtime_execution_trace",
            )

        report = evaluate_u4_obligations(evidence_map=evidence_map)
        self.assertEqual(
            report.verdict,
            EvaluationVerdict.NOT_SATISFIED,
            "Overall verdict must remain NOT_SATISFIED if even one obligation is unsatisfied.",
        )
        self.assertEqual(report.satisfied_count, 10)
        self.assertEqual(report.not_satisfied_count, 1)
        self.assertTrue(report.is_fail_closed)

    def test_synthetic_positive_path_when_all_obligations_satisfied(self):
        """Positive test: When ALL 11 obligations receive valid verified runtime artifacts, verdict is SATISFIED."""
        evidence_map = {}
        for oblig in U4_OBLIGATIONS:
            evidence_map[oblig.id] = EvidenceArtifact(
                artifact_id=f"SYNTHETIC-VALID-{oblig.id}",
                artifact_type=oblig.required_evidence.artifact_type,
                status=ObligationStatus.VERIFIED,
                description=f"Synthetic dynamic verified artifact for {oblig.id}",
                citation=oblig.citation,
                is_static=False,
                how_captured="runtime_execution_trace",
            )

        report = evaluate_u4_obligations(evidence_map=evidence_map)
        self.assertEqual(
            report.verdict,
            EvaluationVerdict.SATISFIED,
            "When all obligations have valid runtime verified evidence, verdict must be SATISFIED.",
        )
        self.assertEqual(report.satisfied_count, 11)
        self.assertEqual(report.not_satisfied_count, 0)
        self.assertFalse(report.is_fail_closed)

    def test_no_new_firmware_addresses_in_obligations_module(self):
        """Invariant: No new firmware addresses or offsets are introduced in port13_oblig_u4.py."""
        tool_code = (REPO_ROOT / "tools" / "port13_oblig_u4.py").read_text(encoding="utf-8")

        # Tracked addresses and register/size constants already documented in docs/PORT13_REVIEW_U4.md:
        allowed_addresses = {
            "0xFC31BBC4",
            "0xBFE14A3C",
            "0xFC1283AD",
            "0xFC05B8FC",
            "0xFC05B558",
            "0xFC0BD0B4",
            "0xFC0D0126",
            "0x00600013",
            "0x003C89B4",
            "0xFC267BE6",
            "0xFC267BEA",
            "0xFC267BF2",
            "0x2000",
            "0x1000",
            "0x000000F3",
        }

        # Find all hex literals with 4 or more digits
        found_addresses = set(re.findall(r"0x[0-9a-fA-F]{4,8}", tool_code))
        # Exclude common formatting like 0xFFFF or similar masks if any, though here all should be allowed
        disallowed = [addr for addr in found_addresses if addr.upper() not in {a.upper() for a in allowed_addresses}]
        self.assertEqual(
            disallowed,
            [],
            f"Found unauthorized new firmware addresses in port13_oblig_u4.py: {disallowed}",
        )


if __name__ == "__main__":
    unittest.main()
