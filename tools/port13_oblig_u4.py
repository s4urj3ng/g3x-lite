#!/usr/bin/env python3
"""tools/port13_oblig_u4.py

Fail-closed offline proof obligations for U4 (SpyTask launch dependencies).

Grounded strictly in:
  - docs/PORT13_REVIEW_U4.md (Review of PR #25, findings C01-C21, remediation list)
  - tools/port9b_runtime_contract.py (Contracts I1, I3, C3.spytask, C5.U4)
  - tools/port9a_runtime_lifecycle.py (RuntimeLifecycle, TaskState, GateState)
  - docs/PORT9A_RUNTIME_INTEGRATION_MAP.md (U4 and I3 specifications)

Standard library only. No subprocess, binary, ROM scan or hardware execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


class ObligationStatus(str, Enum):
    """Classification status for proof obligations and evidence artifacts."""
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvaluationVerdict(str, Enum):
    """Evaluator outcome."""
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"


class Domain(str, Enum):
    """Technical domain for U4 obligations."""
    LAUNCH_ORDERING = "LAUNCH_ORDERING"
    RUNTIME_HOOK_PLACEMENT = "RUNTIME_HOOK_PLACEMENT"
    SCHEDULER_POLICY = "SCHEDULER_POLICY"
    MEMORY_OWNERSHIP = "MEMORY_OWNERSHIP"
    FS_GATING = "FS_GATING"
    FAILCLOSED_TIMEOUT = "FAILCLOSED_TIMEOUT"
    CAUSAL_ANALYSIS = "CAUSAL_ANALYSIS"
    EXECUTION_CONTEXT = "EXECUTION_CONTEXT"
    CONTINUATION = "CONTINUATION"
    CONCURRENCY_CONSTRAINTS = "CONCURRENCY_CONSTRAINTS"
    WARM_RESTART_CLEANUP = "WARM_RESTART_CLEANUP"


# Tracked static ROM anchor points (PORT-11A).
# These verify static presence in ROM/relocation only and NEVER satisfy
# runtime hook placement or task start ordering.
STATIC_ANCHOR_CREATETASK_VENEER = "0xFC31BBC4 -> 0xBFE14A3C"
STATIC_ANCHOR_PHYSW_THUMB_ENTRY = "0xFC1283AD"
STATIC_ANCHOR_ADDRESSES = frozenset({"0xFC31BBC4", "0xBFE14A3C", "0xFC1283AD"})

CANONICAL_OBLIGATION_IDS: Tuple[str, ...] = (
    "OBLIG-U4-01",
    "OBLIG-U4-02",
    "OBLIG-U4-03",
    "OBLIG-U4-04",
    "OBLIG-U4-05",
    "OBLIG-U4-06",
    "OBLIG-U4-07",
    "OBLIG-U4-08",
    "OBLIG-U4-09",
    "OBLIG-U4-10",
    "OBLIG-U4-11",
)


@dataclass(frozen=True)
class RequiredEvidence:
    """Specification of artifact required to satisfy an obligation."""
    artifact_type: str
    what_it_must_show: str


@dataclass(frozen=True)
class U4Obligation:
    """A formal offline proof obligation for U4."""
    id: str
    statement: str
    required_evidence: RequiredEvidence
    current_status: ObligationStatus
    citation: str
    domain: Domain
    requires_runtime_evidence: bool = False

    @property
    def is_runtime_obligation(self) -> bool:
        """Backwards compatibility alias for requires_runtime_evidence."""
        return self.requires_runtime_evidence


@dataclass(frozen=True)
class EvidenceArtifact:
    """An evidence artifact submitted for evaluation.

    Fail-closed defaults:
      - is_static defaults to True.
      - how_captured defaults to "".
    Without explicit runtime provenance (is_static=False and an allowlisted
    how_captured value), the artifact is treated as non-empirical and cannot
    satisfy runtime obligations.
    """
    artifact_id: str
    artifact_type: str
    status: ObligationStatus
    description: str
    citation: str
    is_static: bool = True
    associated_addresses: Tuple[str, ...] = ()
    how_captured: str = ""


@dataclass(frozen=True)
class ObligationResult:
    """Evaluation result for an individual obligation."""
    obligation_id: str
    verdict: EvaluationVerdict
    status: ObligationStatus
    reason: str
    citation: str


@dataclass(frozen=True)
class U4EvaluationReport:
    """Aggregated evaluation report for U4 proof obligations."""
    verdict: EvaluationVerdict
    results: List[ObligationResult]
    satisfied_count: int
    not_satisfied_count: int
    obligations_count: int

    @property
    def is_fail_closed(self) -> bool:
        """True if any obligation is NOT_SATISFIED and overall verdict is NOT_SATISFIED."""
        return self.not_satisfied_count > 0 and self.verdict is EvaluationVerdict.NOT_SATISFIED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "satisfied_count": self.satisfied_count,
            "not_satisfied_count": self.not_satisfied_count,
            "obligations_count": self.obligations_count,
            "is_fail_closed": self.is_fail_closed,
            "results": [
                {
                    "obligation_id": r.obligation_id,
                    "verdict": r.verdict.value,
                    "status": r.status.value,
                    "reason": r.reason,
                    "citation": r.citation,
                }
                for r in self.results
            ],
        }


# -----------------------------------------------------------------------------
# Canonical U4 Obligations Catalog
# -----------------------------------------------------------------------------

U4_OBLIGATIONS: Tuple[U4Obligation, ...] = (
    U4Obligation(
        id="OBLIG-U4-01",
        statement="SpyTask launch site and caller execution ordering in GM1.10C startup sequence",
        required_evidence=RequiredEvidence(
            artifact_type="STARTUP_DISPATCH_TRACE",
            what_it_must_show=(
                "Dynamic execution trace or exhaustive caller graph from sub_fc05b558 and "
                "task_Startup (0xFC05B8FC) proving safe reachability and dispatch point "
                "without destabilizing concurrent tasks or hanging early boot."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:50-55, 85-90, 167, 176, 277, 296-298",
        domain=Domain.LAUNCH_ORDERING,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-02",
        statement="Runtime hook placement and CreateTask interception authorization (Contract I1)",
        required_evidence=RequiredEvidence(
            artifact_type="HOOK_SAFETY_EVIDENCE",
            what_it_must_show=(
                "Proof of safe runtime hook installation context, instruction cache / branch "
                "predictor coherence at patch time in ATCM, IRQ safety, and execution authorization."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:41-46, 86, 141-144, 177, 258, 297",
        domain=Domain.RUNTIME_HOOK_PLACEMENT,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-03",
        statement="RTOS scheduling priority assignment and kernel scheduler policy validation",
        required_evidence=RequiredEvidence(
            artifact_type="RTOS_SCHEDULER_SPEC",
            what_it_must_show=(
                "Disassembly or specification of DryOS scheduler on DIGIC 6 proving numerical "
                "priority ordering direction, preemption/round-robin/FIFO rules for equal priority "
                "tasks (resolving collision with stock InitFileModules priority 0x19), and absence "
                "of filesystem starvation or priority inversion."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:60-61, 103-112, 168-170, 275-276, 293-294",
        domain=Domain.SCHEDULER_POLICY,
        requires_runtime_evidence=False,
    ),
    U4Obligation(
        id="OBLIG-U4-04",
        statement="Task stack sizing and DryOS dynamic memory pool ownership validation",
        required_evidence=RequiredEvidence(
            artifact_type="KERNEL_HEAP_SPEC",
            what_it_must_show=(
                "Kernel heap allocator disassembly proving that CreateTask dynamically allocates "
                "0x2000 bytes stack from a verified heap pool without buffer exhaustion or collision "
                "with camera OS buffers or executable RAM."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:98-101, 121-125, 171, 184, 274, 279, 292, 300",
        domain=Domain.MEMORY_OWNERSHIP,
        requires_runtime_evidence=False,
    ),
    U4Obligation(
        id="OBLIG-U4-05",
        statement="Filesystem readiness gating and monotonic latch synchronization (Contract I3)",
        required_evidence=RequiredEvidence(
            artifact_type="LIFECYCLE_STATE_TRACE",
            what_it_must_show=(
                "SpyTask is created in WAITING_GATE and moves to RUNNING strictly after all 6 filesystem "
                "stages are satisfied (GateState.READY) with no latched fault; while U4 is UNKNOWN, "
                "SpyTask remains blocked in WAITING_GATE."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:63-64, 92-96, 145-152, 172, 175, 179, 215-216, 273, 291",
        domain=Domain.FS_GATING,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-06",
        statement="Fail-closed gate timeout enforcement eliminating upstream CHDK legacy bypass",
        required_evidence=RequiredEvidence(
            artifact_type="TIMEOUT_GATING_SPEC",
            what_it_must_show=(
                "Deterministic transition of SpyTask to FAILED upon gate timeout (spytask_gate_timeout), "
                "never allowing the task to bypass the gate or launch into unmapped routines."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:63-64, 145-152, 173, 209-210",
        domain=Domain.FAILCLOSED_TIMEOUT,
        requires_runtime_evidence=False,
    ),
    U4Obligation(
        id="OBLIG-U4-07",
        statement="Isolation of legacy timeout-bypass causal claim (storage corruption / kernel panic)",
        required_evidence=RequiredEvidence(
            artifact_type="STORAGE_CORRUPTION_TRACE",
            what_it_must_show=(
                "Empirical crash dump or hardware trace demonstrating whether the upstream 10-second "
                "timeout bypass directly caused storage media corruption and kernel panics, or if that "
                "link is merely unproven correlation."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:71-74, 174, 272, 290",
        domain=Domain.CAUSAL_ANALYSIS,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-08",
        statement="Task execution CPU mode and interrupt mask conformance (Privileged Supervisor Mode)",
        required_evidence=RequiredEvidence(
            artifact_type="TASK_CONTEXT_EVIDENCE",
            what_it_must_show=(
                "Proof that SpyTask executes in Privileged Supervisor Mode (M = 0x13) with initial "
                "CPSR 0x000000F3, unmasked to IRQ enabled and FIQ disabled (CPSR[7:6] = 0b01), "
                "never assuming System Mode or unmasked FIQ."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:113-120, 183, 278, 299",
        domain=Domain.EXECUTION_CONTEXT,
        requires_runtime_evidence=False,
    ),
    U4Obligation(
        id="OBLIG-U4-09",
        statement="Continuation branch runtime safety (tail branch sub_fc0d0126)",
        required_evidence=RequiredEvidence(
            artifact_type="CONTINUATION_TRACE",
            what_it_must_show=(
                "Runtime proof that executing the tail branch b.w sub_fc0d0126 (boot_prototype.c:434) "
                "successfully continues startup without stack corruption, CPU exception, or hang."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:126-129, 181, 281, 302",
        domain=Domain.CONTINUATION,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-10",
        statement="SpyTask cooperative yield behavior and global-interrupt disable constraints (Finding C17)",
        required_evidence=RequiredEvidence(
            artifact_type="SPYTASK_YIELD_CONCURRENCY_SPEC",
            what_it_must_show=(
                "Specification or execution trace proving DryOS kernel scheduling yield rules (via SleepTask "
                "or message queues) and verifying whether SpyTask is forbidden from globally disabling "
                "interrupts or starving concurrent real-time tasks on GM1.10C."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:185, 280, 301",
        domain=Domain.CONCURRENCY_CONSTRAINTS,
        requires_runtime_evidence=True,
    ),
    U4Obligation(
        id="OBLIG-U4-11",
        statement="Isolation of warm-restart semaphore-freeze hypothesis across reboot (Finding C18 / Remediation #9)",
        required_evidence=RequiredEvidence(
            artifact_type="SEMAPHORE_CLEANUP_TRACE",
            what_it_must_show=(
                "Empirical reboot trace or kernel teardown analysis demonstrating whether lingering "
                "semaphores from aborted tasks induce a boot freeze during warm restart, or if kernel "
                "re-initialization cleanly resets Low RAM OS structures."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:186, 280, 301",
        domain=Domain.WARM_RESTART_CLEANUP,
        requires_runtime_evidence=True,
    ),
)


# -----------------------------------------------------------------------------
# Static Evidence and Evaluation Guards
# -----------------------------------------------------------------------------

# Explicit allowlist of recognized empirical runtime evidence capture methods.
# Any provenance value not in this set (including empty, whitespace-only, simulated,
# emulated, modelled, synthetic, or unrecognized provenance) fails closed and is
# treated as non-empirical.
EMPIRICAL_PROVENANCE_ALLOWLIST: frozenset[str] = frozenset({
    "runtime_execution_trace",
    "hardware_crash_dump",
    "dynamic_execution_trace",
    "hardware_trace",
    "hardware_log",
    "empirical_crash_dump",
    "empirical_reboot_trace",
    "runtime_trace",
    "runtime_log",
    "in_situ_execution_trace",
})
RECOGNIZED_EMPIRICAL_PROVENANCE = EMPIRICAL_PROVENANCE_ALLOWLIST


def is_static_evidence(evidence: EvidenceArtifact) -> bool:
    """Classify evidence by provenance fields and properties demonstrated, not addresses.

    Evidence is classified as static if:
      - is_static is True (explicit or default provenance flag),
      - artifact_type indicates static analysis/disassembly (e.g. starts with 'STATIC_'),
      - how_captured indicates static extraction/inspection (e.g. contains 'static',
        'rom_disassembly', 'offline_inspection', or 'static_analysis').

    Crucially, referencing anchor addresses (such as 0xFC31BBC4, 0xBFE14A3C, or 0xFC1283AD)
    does NOT classify evidence as static; genuine runtime traces referencing these addresses
    remain eligible for evaluation.
    """
    if evidence.is_static is True:
        return True
    if evidence.artifact_type.upper().startswith("STATIC_"):
        return True
    if evidence.how_captured and isinstance(evidence.how_captured, str):
        hc = evidence.how_captured.strip().lower()
        if any(term in hc for term in ("static", "rom_disassembly", "offline_inspection", "static_analysis")):
            return True
    return False


# Backward-compatible alias
is_static_veneer_or_entry_evidence = is_static_evidence


def is_empirical_evidence(evidence: EvidenceArtifact) -> bool:
    """Classify whether evidence artifact represents genuine empirical runtime observation.

    Fail-closed allowlist evaluation: returns True ONLY if:
      1. evidence.is_static is explicitly False (is_static is False), AND
      2. evidence.how_captured, after normalization (strip and lowercase),
         is present in EMPIRICAL_PROVENANCE_ALLOWLIST.

    Missing, empty, whitespace-only, unknown, simulated, emulated, modelled,
    or synthetic provenance values return False.
    Non-empirical artifact types (such as ANECDOTE, SPECULATION, THEORY, INFERENCE)
    always return False regardless of provenance string.
    """
    if evidence.is_static is not False:
        return False
    if not isinstance(evidence.how_captured, str):
        return False
    normalized = evidence.how_captured.strip().lower()
    if not normalized or normalized not in EMPIRICAL_PROVENANCE_ALLOWLIST:
        return False
    at = evidence.artifact_type.upper()
    if any(term in at for term in ("ANECDOTE", "SPECULATION", "THEORY", "INFERENCE", "INFERRED")):
        return False
    return True


def evaluate_obligation(
    obligation: U4Obligation,
    evidence: Optional[EvidenceArtifact] = None,
) -> ObligationResult:
    """Evaluate an individual U4 obligation fail-closed.

    Rules:
      1. If evidence is absent, rely strictly on obligation.current_status.
         Any status other than VERIFIED evaluates as NOT_SATISFIED.
      2. If evidence is present, evidence.status must be VERIFIED.
      3. Obligations marked with requires_runtime_evidence=True (runtime hook placement,
         task start ordering, continuation, readiness, or causal effects) require
         VERIFIED evidence with allowlisted empirical runtime provenance.
         Static evidence (e.g. CreateTask veneer 0xFC31BBC4 -> ATCM 0xBFE14A3C,
         PhySw Thumb entry 0xFC1283AD) and non-empirical evidence (missing, empty,
         whitespace, unknown, simulated, synthetic, or unallowlisted provenance)
         CANNOT satisfy these obligations and evaluate as NOT_SATISFIED.
      4. Legacy timeout-bypass causal link (OBLIG-U4-07 / Finding C06b) must stay
         UNKNOWN (never INFERRED or VERIFIED) whenever evidence is unverified, static,
         or lacks allowlisted empirical provenance.
    """
    # Case 1: No external evidence passed (evaluating current baseline state)
    if evidence is None:
        if obligation.current_status == ObligationStatus.VERIFIED:
            return ObligationResult(
                obligation_id=obligation.id,
                verdict=EvaluationVerdict.SATISFIED,
                status=obligation.current_status,
                reason="Obligation has VERIFIED evidence in repository baseline.",
                citation=obligation.citation,
            )
        return ObligationResult(
            obligation_id=obligation.id,
            verdict=EvaluationVerdict.NOT_SATISFIED,
            status=obligation.current_status,
            reason=(
                f"Obligation status is {obligation.current_status.value}; "
                "evaluator fails closed without VERIFIED evidence."
            ),
            citation=obligation.citation,
        )

    # Invariant: C06b causal link between legacy timeout bypass and corruption/panic
    # must stay UNKNOWN (never INFERRED or VERIFIED) whenever evidence is unverified, static,
    # non-empirical, or wrong artifact type. Both provenance and artifact type checks are enforced.
    if obligation.id == "OBLIG-U4-07":
        if (
            evidence.status != ObligationStatus.VERIFIED
            or is_static_evidence(evidence)
            or not is_empirical_evidence(evidence)
            or evidence.artifact_type != "STORAGE_CORRUPTION_TRACE"
        ):
            return ObligationResult(
                obligation_id=obligation.id,
                verdict=EvaluationVerdict.NOT_SATISFIED,
                status=ObligationStatus.UNKNOWN,
                reason=(
                    "Static evidence (CreateTask veneer 0xFC31BBC4 -> ATCM 0xBFE14A3C, "
                    "PhySw Thumb entry 0xFC1283AD) proves static code presence only and "
                    "cannot satisfy runtime hook placement or launch-ordering obligations; "
                    "the legacy timeout-bypass -> storage corruption/kernel panic link is "
                    "untested conjecture; status must stay UNKNOWN (never INFERRED) whenever "
                    "evidence is unverified, static, or non-empirical."
                    if is_static_evidence(evidence)
                    else (
                        "The legacy timeout-bypass -> storage corruption/kernel panic link is "
                        "untested conjecture; status must stay UNKNOWN (never INFERRED) whenever "
                        "evidence is unverified, static, or non-empirical."
                    )
                ),
                citation=evidence.citation,
            )

    # Invariant: Static and non-empirical evidence cannot satisfy obligations requiring runtime evidence
    # (such as runtime hook placement, task start ordering, continuation, readiness, or causal effects).
    if obligation.requires_runtime_evidence:
        if is_static_evidence(evidence):
            return ObligationResult(
                obligation_id=obligation.id,
                verdict=EvaluationVerdict.NOT_SATISFIED,
                status=ObligationStatus.UNKNOWN,
                reason=(
                    "Static evidence (CreateTask veneer 0xFC31BBC4 -> ATCM 0xBFE14A3C, "
                    "PhySw Thumb entry 0xFC1283AD) proves static code presence only and "
                    "cannot satisfy runtime hook placement or launch-ordering obligations."
                ),
                citation=evidence.citation,
            )
        if not is_empirical_evidence(evidence):
            return ObligationResult(
                obligation_id=obligation.id,
                verdict=EvaluationVerdict.NOT_SATISFIED,
                status=ObligationStatus.UNKNOWN,
                reason=(
                    f"Obligation '{obligation.id}' requires verified empirical runtime evidence with "
                    "allowlisted provenance; non-empirical, simulated, synthetic, or unprovenanced "
                    f"evidence (how_captured={evidence.how_captured!r}, is_static={evidence.is_static!r}) "
                    "cannot satisfy runtime obligations."
                ),
                citation=evidence.citation,
            )

    # Case 2: Evidence artifact provided
    if evidence.status != ObligationStatus.VERIFIED:
        return ObligationResult(
            obligation_id=obligation.id,
            verdict=EvaluationVerdict.NOT_SATISFIED,
            status=evidence.status,
            reason=(
                f"Provided evidence status is {evidence.status.value}; "
                "evaluator fails closed without VERIFIED evidence."
            ),
            citation=evidence.citation,
        )

    # Invariant: Artifact type must match required type
    if evidence.artifact_type != obligation.required_evidence.artifact_type:
        return ObligationResult(
            obligation_id=obligation.id,
            verdict=EvaluationVerdict.NOT_SATISFIED,
            status=evidence.status,
            reason=(
                f"Evidence artifact type '{evidence.artifact_type}' does not match "
                f"required artifact type '{obligation.required_evidence.artifact_type}'."
            ),
            citation=evidence.citation,
        )

    return ObligationResult(
        obligation_id=obligation.id,
        verdict=EvaluationVerdict.SATISFIED,
        status=ObligationStatus.VERIFIED,
        reason=f"Satisfied by verified artifact '{evidence.artifact_id}'.",
        citation=evidence.citation,
    )


def evaluate_u4_obligations(
    obligations: Optional[Tuple[U4Obligation, ...]] = None,
    evidence_map: Optional[Dict[str, EvidenceArtifact]] = None,
) -> U4EvaluationReport:
    """Evaluate all U4 obligations fail closed.

    Enforces that an overall U4 verdict may only be issued when the supplied set
    exactly matches the canonical IDs OBLIG-U4-01..11.
    An empty set, a missing ID, a duplicate ID, or an unknown ID raises ValueError.

    Returns NOT_SATISFIED if any obligation lacks VERIFIED evidence.
    """
    if obligations is None:
        target_obligations = U4_OBLIGATIONS
    else:
        target_obligations = tuple(obligations)

    if not target_obligations:
        raise ValueError(
            "Obligation set cannot be empty; an overall U4 verdict requires "
            "the complete canonical set of obligations (OBLIG-U4-01..11)."
        )

    ids = [o.id for o in target_obligations]
    if len(ids) != len(set(ids)):
        duplicates = sorted(set(x for x in ids if ids.count(x) > 1))
        raise ValueError(
            f"Duplicate obligation ID(s) detected: {duplicates}; "
            "each canonical obligation must appear exactly once."
        )

    supplied_ids = set(ids)
    canonical_set = set(CANONICAL_OBLIGATION_IDS)

    unknown_ids = supplied_ids - canonical_set
    if unknown_ids:
        raise ValueError(
            f"Unknown obligation ID(s) detected: {sorted(unknown_ids)}; "
            f"only canonical IDs {list(CANONICAL_OBLIGATION_IDS)} are permitted."
        )

    missing_ids = canonical_set - supplied_ids
    if missing_ids:
        raise ValueError(
            f"Missing canonical obligation ID(s): {sorted(missing_ids)}; "
            "an overall U4 verdict requires all canonical obligations to be evaluated."
        )

    results: List[ObligationResult] = []

    for oblig in target_obligations:
        ev = evidence_map.get(oblig.id) if evidence_map else None
        res = evaluate_obligation(oblig, ev)
        results.append(res)

    satisfied = sum(1 for r in results if r.verdict == EvaluationVerdict.SATISFIED)
    not_satisfied = sum(1 for r in results if r.verdict == EvaluationVerdict.NOT_SATISFIED)

    overall_verdict = (
        EvaluationVerdict.SATISFIED
        if (not_satisfied == 0 and satisfied == len(target_obligations))
        else EvaluationVerdict.NOT_SATISFIED
    )

    return U4EvaluationReport(
        verdict=overall_verdict,
        results=results,
        satisfied_count=satisfied,
        not_satisfied_count=not_satisfied,
        obligations_count=len(target_obligations),
    )


def get_obligation(obligation_id: str) -> Optional[U4Obligation]:
    """Retrieve an obligation by ID."""
    for oblig in U4_OBLIGATIONS:
        if oblig.id == obligation_id:
            return oblig
    return None


def main() -> int:
    """CLI runner for U4 obligations evaluation."""
    report = evaluate_u4_obligations()
    print("=" * 70)
    print("PORT-13 Fail-Closed Proof Obligations: U4 SpyTask Launch Dependencies")
    print("=" * 70)
    print(f"Overall U4 Verdict: {report.verdict.value}")
    print(f"Obligations Total : {report.obligations_count}")
    print(f"Satisfied         : {report.satisfied_count}")
    print(f"Not Satisfied     : {report.not_satisfied_count}")
    print(f"Fail-Closed Active: {report.is_fail_closed}")
    print("-" * 70)
    for res in report.results:
        print(f"[{res.verdict.value:13}] {res.obligation_id} ({res.status.value}): {res.reason}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
