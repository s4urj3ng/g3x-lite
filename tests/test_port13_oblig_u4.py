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
    is_static_evidence,
    is_static_veneer_or_entry_evidence,
)


class TestPort13ObligU4(unittest.TestCase):
    """Offline test suite for U4 SpyTask launch proof obligations."""

    def test_u4_obligations_catalog_structure_and_citations(self):
        """Invariant: All 9 obligations have valid schema, statuses, and tracked citations."""
        self.assertEqual(len(U4_OBLIGATIONS), 9, "Expected 9 canonical U4 obligations.")
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
            # In baseline GM1.10C, all 9 obligations must be UNKNOWN
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
        expected_runtime = {"OBLIG-U4-01", "OBLIG-U4-02", "OBLIG-U4-05"}
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
        self.assertEqual(len(subset), 8)
        with self.assertRaises(ValueError) as ctx_missing:
            evaluate_u4_obligations(obligations=subset)
        self.assertIn("missing", str(ctx_missing.exception).lower())
        self.assertIn("OBLIG-U4-01", str(ctx_missing.exception))

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
        """Explicit Test: C06b legacy-timeout-bypass -> corruption/panic causal link must remain UNKNOWN."""
        oblig = get_obligation("OBLIG-U4-07")
        self.assertIsNotNone(oblig)
        self.assertEqual(oblig.id, "OBLIG-U4-07")
        self.assertEqual(oblig.current_status, ObligationStatus.UNKNOWN)
        self.assertEqual(oblig.domain, Domain.CAUSAL_ANALYSIS)

        # In baseline, must evaluate to NOT_SATISFIED
        baseline_res = evaluate_obligation(oblig)
        self.assertEqual(baseline_res.verdict, EvaluationVerdict.NOT_SATISFIED)
        self.assertEqual(baseline_res.status, ObligationStatus.UNKNOWN)

        # Non-crash trace (e.g. speculation or inference) must be rejected
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
        self.assertIn("untested conjecture", spec_res.reason)

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
        """Invariant: If 8 of 9 obligations are satisfied, overall verdict remains NOT_SATISFIED."""
        evidence_map = {}
        # Satisfy 8 obligations with valid synthetic runtime artifacts
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
        self.assertEqual(report.satisfied_count, 8)
        self.assertEqual(report.not_satisfied_count, 1)
        self.assertTrue(report.is_fail_closed)

    def test_synthetic_positive_path_when_all_obligations_satisfied(self):
        """Positive test: When ALL 9 obligations receive valid verified runtime artifacts, verdict is SATISFIED."""
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
        self.assertEqual(report.satisfied_count, 9)
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
