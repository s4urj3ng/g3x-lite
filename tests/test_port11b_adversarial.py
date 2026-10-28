"""Bounded, deterministic adversarial QA of PORT-11B against merged main (7f39946).

Run: python3 -B -m unittest discover -s tests -p test_port11b_adversarial.py -v

Standard library only. No ROM/binary reads, subprocesses, hardware, builds or
production-file edits. Contract tests read only tracked text through the existing
source loader. Synthetic profiles below are scenario assertions, never evidence.

All 21 adversarial test methods pass against current merged origin/main (7f39946).
- KnownClaudeBlockers (K1/K2/K3): Verified fixed regression controls.
- TraceValidationDefect (QA-N1): Fixed in PR #16 (commit dcf1b19) and verified as
  durable negative coverage; post-fault replacement detection passes across all
  task permutations.

Historical Baseline Context:
Originally authored against older baseline 4e2f7929 (local commit 38710842) where
QA-N1 was first identified as a trace validation defect. In merged main 7f39946,
tools/port9a_runtime_lifecycle.py check_trace() examines all post-fault events,
so all 21 methods pass with zero expectedFailure, zero skips, and zero failures.
"""

from dataclasses import dataclass, fields, replace
from itertools import permutations, product
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import port9a_runtime_lifecycle as rt  # noqa: E402
import port9b_runtime_contract as pc  # noqa: E402

GENERATION = 2
TASKS = ("InitFileModules", "PhySw")
EVENTS = ("start", "return", "mount", "io", "warm")


def synthetic_model(install=True, **overrides):
    """Explicit, TEST-ONLY satisfied scenario; no mutation of GM110C defaults."""
    kwargs = dict(
        preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
        static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
        hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        boot_generation=GENERATION,
    )
    kwargs.update(overrides)
    model = rt.RuntimeLifecycle(**kwargs)
    model.init_core()
    if install:
        model.install_intercept()
    return model


def event(model, name, generation=GENERATION, status="ok", value=True):
    """Supply one explicit synthetic observation, without synthesizing others."""
    if name == "start":
        return model.init_file_modules_started(boot_generation=generation)
    if name == "return":
        return model.init_file_modules_returned(
            return_code=0 if value is True else None,
            boot_generation=generation, status=status,
        )
    if name == "mount":
        return model.record_mount_observation(value, boot_generation=generation, status=status)
    if name == "io":
        return model.record_filesystem_io_readiness(value, boot_generation=generation, status=status)
    if name == "warm":
        return model.record_warm_restart_storage_safety(value, boot_generation=generation, status=status)
    if name == "finish":
        return model.file_modules_finished(value, boot_generation=generation)
    raise AssertionError("unknown test observation: " + name)


def ready_without_spytask():
    model = synthetic_model()
    model.on_firmware_create_task("InitFileModules")
    for name in EVENTS:
        event(model, name)
    return model


@dataclass
class FilesystemOracle:
    """Independent minimal ordering oracle, not a copy of production transitions.

    Ordinals count accepted stages: 1=created, 2=started, ..., 6=warm safe.
    Unarmed observations are ignored; a latched failure cannot be repaired.
    Accepted same-generation success repeats are idempotent at every stage.
    """
    ordinal: int = 1
    failed: bool = False

    def observe_success(self, name):
        if self.failed or self.ordinal == 0:
            return
        required = EVENTS.index(name) + 1
        if self.ordinal < required:
            self.failed = True
        else:
            self.ordinal = max(self.ordinal, required + 1)


class BoundedFilesystemExploration(unittest.TestCase):
    def test_order_and_repetition_against_independent_oracle(self):
        # 625 bounded words plus 120 complete permutations, each with early and
        # late SpyTask creation: 1,490 independently reconstructed scenarios.
        sequences = tuple(product(EVENTS, repeat=4)) + tuple(permutations(EVENTS))
        for sequence, early_spy in product(sequences, (False, True)):
            with self.subTest(sequence=sequence, early_spy=early_spy):
                model = synthetic_model()
                oracle = FilesystemOracle()
                if early_spy:
                    model.create_spytask()
                model.on_firmware_create_task("InitFileModules")
                for name in sequence:
                    oracle.observe_success(name)
                    event(model, name)
                    self.assertEqual(model.fs.failed, oracle.failed)
                    self.assertEqual(model.fs.is_ready, not oracle.failed and oracle.ordinal == 6)
                    self.assertEqual(model.gate is rt.GateState.READY,
                                     not oracle.failed and oracle.ordinal == 6)
                model.create_spytask()
                self.assertEqual(model.spytask is rt.TaskState.RUNNING,
                                 not oracle.failed and oracle.ordinal == 6)

    def test_success_repeats_do_not_regress_or_duplicate_readiness(self):
        for stop in range(6):
            model = synthetic_model()
            model.on_firmware_create_task("InitFileModules")
            for name in EVENTS[:stop]:
                event(model, name)
            before = model.fs
            for name in EVENTS[:stop]:
                event(model, name)
            self.assertEqual(model.fs, before)
            for name in EVENTS[stop:]:
                event(model, name)
            model.create_spytask()
            self.assertIs(model.spytask, rt.TaskState.RUNNING)
            self.assertEqual(sum(e == "fs_ready" for e, _ in model.trace), 1)

    def test_unarmed_observations_are_not_used_as_readiness_evidence(self):
        # Ignoring observations before task creation is legitimate; demanding a
        # fault here would be a false positive, not an ordering bypass.
        model = synthetic_model()
        for name in EVENTS:
            event(model, name)
        self.assertIs(model.gate, rt.GateState.NOT_ARMED)
        self.assertFalse(model.fs.is_ready)
        model.on_firmware_create_task("InitFileModules")
        self.assertIs(model.fs.stage, rt.FilesystemStage.TASK_CREATED)
        self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)

    def test_failed_state_cannot_recover_from_later_positive_observations(self):
        for stop in range(5):
            with self.subTest(stop=stop):
                model = synthetic_model()
                model.on_firmware_create_task("InitFileModules")
                for name in EVENTS[:stop]:
                    event(model, name)
                event(model, EVENTS[stop], generation=GENERATION - 1)
                first_fault = model.fault
                self.assertIsNotNone(first_fault)
                for name in EVENTS:
                    event(model, name)
                model.file_modules_finished(True, boot_generation=GENERATION)
                self.assertIs(model.gate, rt.GateState.FAILED)
                self.assertTrue(model.fs.failed)
                self.assertEqual(model.fault, first_fault)
                self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)

    def test_final_success_boolean_at_each_partial_stage_cannot_promote(self):
        for stop in range(5):
            model = synthetic_model()
            model.on_firmware_create_task("InitFileModules")
            for name in EVENTS[:stop]:
                event(model, name)
            model.file_modules_finished(True, boot_generation=GENERATION)
            self.assertTrue(model.fs.failed)
            self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)

    def test_failed_missing_ambiguous_and_stale_witnesses_before_ready(self):
        bad_observations = ((False, "ok", GENERATION), (None, "ok", GENERATION),
                            (True, "ambiguous", GENERATION), (True, "ok", GENERATION - 1))
        for index, bad in product(range(1, 5), bad_observations):
            with self.subTest(stage=EVENTS[index], observation=bad):
                model = synthetic_model()
                model.on_firmware_create_task("InitFileModules")
                for name in EVENTS[:index]:
                    event(model, name)
                value, status, generation = bad
                event(model, EVENTS[index], generation=generation, status=status, value=value)
                self.assertTrue(model.fs.failed)
                self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)

    def test_timeout_and_fault_are_latched_without_spawning_new_replacements(self):
        for stop, failure in product(range(5), ("timeout", "fault")):
            with self.subTest(stop=stop, failure=failure):
                model = synthetic_model()
                model.create_spytask()
                model.on_firmware_create_task("InitFileModules")
                for name in EVENTS[:stop]:
                    event(model, name)
                if failure == "timeout":
                    model.spytask_gate_timeout()
                else:
                    model.report_failure("QA", "explicit synthetic fault")
                for name in EVENTS:
                    event(model, name)
                model.init_core()
                model.install_intercept()
                for task in TASKS:
                    self.assertIsNot(model.on_firmware_create_task(task).action, rt.Action.REPLACE)
                self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)
                self.assertFalse(model.chdk_key_handling)


class KnownClaudeBlockers(unittest.TestCase):
    """K1/K2/K3 are fixed on 4e2f7929; these tests implement no production fix."""

    def test_K1_failed_or_stale_observations_after_ready_block_late_spytask(self):
        # Revalidate both late creation and the newly explicit post-READY rule
        # that an already-running SpyTask is invalidated by filesystem failure.
        cases = [(name, "stale", True, "ok", GENERATION - 1)
                 for name in EVENTS + ("finish",)]
        cases += [(name, "failure", False, "ok", GENERATION)
                  for name in ("return", "mount", "io", "warm", "finish")]
        cases += [(name, "ambiguous", True, "ambiguous", GENERATION)
                  for name in ("return", "mount", "io", "warm")]
        for case, already_running in product(cases, (False, True)):
            name, label, value, status, generation = case
            with self.subTest(case="K1", observation=name, label=label,
                              already_running=already_running):
                model = ready_without_spytask()
                if already_running:
                    self.assertIs(model.create_spytask(), rt.TaskState.RUNNING)
                event(model, name, generation=generation, status=status, value=value)
                self.assertIsNot(model.create_spytask(), rt.TaskState.RUNNING)
                self.assertIs(model.gate, rt.GateState.FAILED)
                self.assertTrue(model.fs.failed)
                self.assertIsNotNone(model.fault)

    def test_K2_stock_singleton_before_intercept_is_not_created_again_as_replacement(self):
        for task in TASKS:
            with self.subTest(case="K2", task=task):
                model = synthetic_model(install=False)
                first = model.on_firmware_create_task(task)
                self.assertIs(first.action, rt.Action.PASS_THROUGH)
                model.install_intercept()
                # There was no task exit or new-generation observation.
                second = model.on_firmware_create_task(task)
                self.assertIs(second.action, rt.Action.PASS_THROUGH)
                self.assertEqual(second.entry, "stock")
                self.assertIn(task, model.stock_owned_singletons)
                self.assertNotIn(task, model.replaced_singletons)
                self.assertIsNotNone(model.fault)

    def test_K3_unknown_inputs_are_not_silently_replaced_by_satisfied_witnesses(self):
        sources, _ = pc.load_sources()
        sources["platform/g3x/kbd.c"] += "\nvoid qa_candidate(void) { core_spytask(); }\n"
        findings = pc.check_contract(
            sources, preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            allow_hypothetical=True,
            static_evidence=rt.UNVERIFIED_STATIC_EVIDENCE,
            hook_contract=rt.GM110C_HOOK_CONTRACT,
        )
        # UNKNOWN supplied profiles must reject this active SpyTask marker.
        self.assertTrue(pc.violations(findings), "K3: accepted active source with UNKNOWN supplied contracts")
        by_name = {finding.check: finding for finding in findings}
        self.assertFalse(by_name["C3.spytask"].ok)
        self.assertEqual(by_name["C5.U4"].label, pc.UNVERIFIED_RUNTIME)

        # Deliberately explicit satisfied witnesses remain a hypothetical scenario.
        synthetic = pc.check_contract(
            sources, preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            allow_hypothetical=True,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        self.assertEqual(pc.violations(synthetic), [])
        by_name = {finding.check: finding for finding in synthetic}
        for check in ("C4.model_trace", "C5.U4", "C6.hook_safety_contract", "C6.fs_readiness_contract"):
            self.assertEqual(by_name[check].label, pc.HYPOTHETICAL)


class CreationAndAuthorizationMatrices(unittest.TestCase):
    def test_unknown_names_always_pass_stock_without_context_validation(self):
        for install, name in product((False, True), ("Unknown", "PhySw ", "physw", "", "FileTask")):
            model = synthetic_model(install=install)
            for _ in range(3):
                decision = model.on_firmware_create_task(name, context=object())
                self.assertIs(decision.action, rt.Action.PASS_THROUGH)
                self.assertEqual(decision.entry, "stock")
                self.assertIsNone(model.fault)

    def test_well_typed_creator_context_matrix(self):
        # 2 tasks x 2 mechanisms x 16 boolean combinations = 64 scenarios.
        for task, mechanism, bits in product(TASKS, tuple(rt.CreationMechanism), tuple(product((False, True), repeat=4))):
            with self.subTest(task=task, mechanism=mechanism.value, bits=bits):
                predecessor, checked, clear, stored = bits
                context = rt.CreatorCallContext(mechanism, predecessor, checked, clear, stored)
                model = synthetic_model()
                expected = (mechanism is rt.EXPECTED_CREATION_MECHANISMS[task]
                            and predecessor and checked and clear
                            and (task != "PhySw" or stored))
                decision = model.on_firmware_create_task(task, context=context)
                self.assertEqual(decision.action is rt.Action.REPLACE, expected)
                if not expected:
                    self.assertIsNotNone(model.fault)
                    self.assertIsNot(model.on_firmware_create_task(task).action, rt.Action.REPLACE)

    def test_invalid_outer_context_fails_closed_for_replacement_candidate(self):
        for context in (object(), {}, "unknown", False):
            model = synthetic_model()
            decision = model.on_firmware_create_task("PhySw", context=context)
            self.assertIsNot(decision.action, rt.Action.REPLACE)
            self.assertIsNotNone(model.fault)

    def test_stock_and_intercepted_duplicate_ownership(self):
        for mode, task in product(("uninstalled", "refused", "installed", "faulted"), TASKS):
            with self.subTest(mode=mode, task=task):
                model = synthetic_model(install=mode != "uninstalled",
                                        **({"hook_contract": None} if mode == "refused" else {}))
                if mode == "faulted":
                    model.report_failure("QA", "fault before first creation")
                decisions = [model.on_firmware_create_task(task) for _ in range(3)]
                expected = ([rt.Action.REPLACE, rt.Action.REJECT_DUPLICATE, rt.Action.REJECT_DUPLICATE]
                            if mode == "installed" else [rt.Action.PASS_THROUGH] * 3)
                self.assertEqual([d.action for d in decisions], expected)

    def test_fault_after_replacement_never_creates_another_replacement(self):
        for task in TASKS:
            model = synthetic_model()
            self.assertIs(model.on_firmware_create_task(task).action, rt.Action.REPLACE)
            model.report_failure("QA", "fault after replacement")
            # 4e2f7929 explicitly documents owned-duplicate rejection before
            # post-fault stock fallback; the invalid context is not a new task.
            self.assertIs(model.on_firmware_create_task(task, context=object()).action,
                          rt.Action.REJECT_DUPLICATE)

    def test_authorization_and_static_evidence_lattices(self):
        # 8 authorization combinations x 32 evidence combinations = 256 cases.
        status_values = (rt.EvidenceStatus.UNKNOWN, rt.EvidenceStatus.STATIC_VERIFIED)
        for flags, statuses in product(tuple(product((False, True), repeat=3)), tuple(product(status_values, repeat=5))):
            with self.subTest(flags=flags, statuses=tuple(s.value for s in statuses)):
                evidence = rt.StaticEvidenceProfile(*statuses)
                model = synthetic_model(preconditions=rt.Preconditions(*flags), static_evidence=evidence)
                installed = flags[0] and statuses[0] is rt.EvidenceStatus.STATIC_VERIFIED
                self.assertEqual(model.intercept is rt.InterceptState.INSTALLED, installed)
                self.assertFalse(model.hardware_execution_authorized)
                self.assertFalse(evidence.authorizes_runtime_activation)
                model.create_spytask()
                init = model.on_firmware_create_task("InitFileModules")
                physw = model.on_firmware_create_task("PhySw")
                init_replaced = installed and flags[1] and statuses[1] is rt.EvidenceStatus.STATIC_VERIFIED
                physw_replaced = installed and flags[2] and statuses[3] is rt.EvidenceStatus.STATIC_VERIFIED
                self.assertEqual(init.action is rt.Action.REPLACE, init_replaced)
                self.assertEqual(physw.action is rt.Action.REPLACE, physw_replaced)
                for name in EVENTS:
                    event(model, name)
                ready = init_replaced and statuses[2] is rt.EvidenceStatus.STATIC_VERIFIED
                spy = ready and statuses[4] is rt.EvidenceStatus.STATIC_VERIFIED
                self.assertEqual(model.gate is rt.GateState.READY, ready)
                self.assertEqual(model.spytask is rt.TaskState.RUNNING, spy)

    def test_each_unknown_hook_requirement_refuses_interception(self):
        for field in fields(rt.HookSafetyContract):
            with self.subTest(requirement=field.name):
                contract = replace(rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                                   **{field.name: rt.EvidenceStatus.UNKNOWN})
                model = synthetic_model(hook_contract=contract)
                self.assertIs(model.intercept, rt.InterceptState.REFUSED)
                for task in TASKS:
                    self.assertIs(model.on_firmware_create_task(task).action, rt.Action.PASS_THROUGH)
        model = synthetic_model(hook_contract=None)
        self.assertIs(model.intercept, rt.InterceptState.REFUSED)


class ContractStructureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources, _ = pc.load_sources()

    def test_missing_reordered_duplicated_or_empty_requirements_fail_c6(self):
        original = rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS
        mutations = (
            original[:-1], tuple(reversed(original)), original + (original[-1],),
            tuple((name, "" if index == 3 else description)
                  for index, (name, description) in enumerate(original)),
        )
        for requirements in mutations:
            with self.subTest(requirements=requirements):
                with patch.object(rt, "FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS", requirements):
                    findings = pc.check_contract(self.sources)
                self.assertTrue(any(f.check == "C6.fs_readiness_contract" and not f.ok for f in findings))

    def test_default_and_refused_hypothetical_runs_preserve_inert_contract(self):
        for preconditions in (rt.GM110C_PRECONDITIONS, rt.HYPOTHETICAL_ALL_VERIFIED):
            findings = pc.check_contract(self.sources, preconditions=preconditions)
            by_name = {f.check: f for f in findings}
            self.assertTrue(by_name["C4.defaults_inert"].ok)
            self.assertEqual(by_name["C4.model_trace"].label, pc.VERIFIED_SOURCE)
            if preconditions is rt.HYPOTHETICAL_ALL_VERIFIED:
                self.assertFalse(by_name["C4.preconditions"].ok)

        for field in ("patch_execution_context_safe", "interrupt_masking_and_concurrency_safe",
                      "icache_and_branch_predictor_coherent", "continuation_behavior_safe"):
            with self.subTest(partial_hook_claim=field):
                contract = replace(rt.GM110C_HOOK_CONTRACT,
                                   **{field: rt.EvidenceStatus.STATIC_VERIFIED})
                findings = pc.check_contract(self.sources, hook_contract=contract)
                by_name = {finding.check: finding for finding in findings}
                self.assertFalse(by_name["C6.hook_safety_contract"].ok)


class NewTraceValidationDefect(unittest.TestCase):
    def test_N1_every_replacement_after_fault_is_rejected_by_trace_validator(self):
        # Pure trace mutation: start with an actual legal public-API trace, then
        # inject one forbidden creation of a DIFFERENT task after its fault.
        # This is a checker false negative, not a claim that the model emitted it.
        for first, later in ((TASKS[0], TASKS[1]), (TASKS[1], TASKS[0])):
            with self.subTest(case="N1", first=first, later=later):
                model = synthetic_model()
                model.on_firmware_create_task(first)
                model.report_failure("QA", "synthetic trace fault")
                self.assertEqual(rt.check_trace(model.trace), [])
                corrupted = model.trace + [("create_replaced", later + "->" + rt.REPLACEMENTS[later])]
                self.assertTrue(rt.check_trace(corrupted), "N1: post-fault replacement hidden by an earlier replacement")

    def test_first_post_fault_replacement_is_detected_positive_control(self):
        model = synthetic_model()
        model.report_failure("QA", "synthetic trace fault")
        trace = model.trace + [("create_replaced", "PhySw->mykbd_task")]
        self.assertTrue(rt.check_trace(trace))


if __name__ == "__main__":
    unittest.main(verbosity=2)
