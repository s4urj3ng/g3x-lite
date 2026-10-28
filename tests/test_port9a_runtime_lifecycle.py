"""PORT-9A / PORT-11B: offline tests for tools/port9a_runtime_lifecycle.py.

Runs on any clean clone. Standard library only; no subprocess, ROM, binary,
build or hardware access. The model encodes ordering and safety rules, not
runtime authorization.

Run:
  python3 -B -m unittest discover -s tests -p 'test_port9a_*.py' -v
"""

import ast
from dataclasses import replace
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO_ROOT / "tools" / "port9a_runtime_lifecycle.py"
sys.path.insert(0, str(REPO_ROOT / "tools"))

import port9a_runtime_lifecycle as rt  # noqa: E402
from port9a_runtime_lifecycle import (  # noqa: E402
    Action, CreationMechanism, CreatorCallContext, EvidenceStatus,
    FilesystemStage, GateState, HookSafetyContract, InterceptState,
    StaticEvidenceProfile, TaskState,
)


def booted(pre=rt.HYPOTHETICAL_ALL_VERIFIED):
    m = rt.RuntimeLifecycle(pre)
    m.init_core()
    m.install_intercept()
    return m


def full_boot():
    """Reference order: SpyTask created early (as upstream), PhySw, then files."""
    m = booted()
    m.create_spytask()
    m.on_firmware_create_task("PhySw")
    m.on_firmware_create_task("InitFileModules")
    m.file_modules_finished(True)
    return m


def synthetic_port11b_boot(static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
                           hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                           boot_generation=1):
    m = rt.RuntimeLifecycle(
        preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
        static_evidence=static_evidence,
        hook_contract=hook_contract,
        boot_generation=boot_generation,
    )
    m.init_core()
    m.install_intercept()
    return m


class SpyTaskOrdering(unittest.TestCase):
    def test_spytask_waits_until_fs_ready(self):
        m = booted()
        self.assertIs(m.create_spytask(), TaskState.WAITING_GATE)
        m.on_firmware_create_task("InitFileModules")
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        m.file_modules_finished(True)
        self.assertIs(m.spytask, TaskState.RUNNING)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_ready_signal_before_spytask_is_latched(self):
        # Upstream core_spytask clears the flag on entry, so an early signal
        # is lost; the model latches it instead.
        m = booted()
        m.on_firmware_create_task("InitFileModules")
        m.file_modules_finished(True)
        self.assertIs(m.create_spytask(), TaskState.RUNNING)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_gate_timeout_fails_instead_of_running(self):
        m = booted()
        m.create_spytask()
        self.assertIs(m.spytask_gate_timeout(), TaskState.FAILED)
        m.on_firmware_create_task("InitFileModules")
        m.file_modules_finished(True)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertIsNot(m.gate, GateState.READY)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_unarmed_gate_signal_is_ignored(self):
        # InitFileModules ran stock (no replacement), so nothing can signal.
        m = booted()
        m.create_spytask()
        m.file_modules_finished(True)
        self.assertIs(m.gate, GateState.NOT_ARMED)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)

    def test_spytask_never_runs_with_unverified_init_file_modules_entry(self):
        m = booted(rt.Preconditions(True, False, True))
        m.create_spytask()
        d = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d.action, Action.PASS_THROUGH)
        m.file_modules_finished(True)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)

    def test_create_spytask_before_core_raises(self):
        with self.assertRaises(rt.LifecycleError):
            rt.RuntimeLifecycle(rt.HYPOTHETICAL_ALL_VERIFIED).create_spytask()


class KeyboardTaskPrerequisites(unittest.TestCase):
    def test_kbd_starts_only_via_routed_physw(self):
        m = booted()
        self.assertIs(m.kbd, TaskState.NOT_CREATED)
        d = m.on_firmware_create_task("PhySw")
        self.assertEqual((d.action, d.entry), (Action.REPLACE, "mykbd_task"))
        self.assertIs(m.kbd, TaskState.RUNNING)

    def test_no_kbd_without_intercept(self):
        m = rt.RuntimeLifecycle(rt.HYPOTHETICAL_ALL_VERIFIED)
        m.init_core()
        d = m.on_firmware_create_task("PhySw")
        self.assertIs(d.action, Action.PASS_THROUGH)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_no_kbd_with_unverified_physw_entry(self):
        m = booted(rt.Preconditions(True, True, False))
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_intercept_requires_core(self):
        m = rt.RuntimeLifecycle(rt.HYPOTHETICAL_ALL_VERIFIED)
        with self.assertRaises(rt.LifecycleError):
            m.install_intercept()

    def test_chdk_key_handling_needs_running_spytask(self):
        m = booted()
        m.on_firmware_create_task("PhySw")
        self.assertFalse(m.chdk_key_handling)  # pass-through only
        m.create_spytask()
        self.assertFalse(m.chdk_key_handling)
        m.on_firmware_create_task("InitFileModules")
        m.file_modules_finished(True)
        self.assertTrue(m.chdk_key_handling)


class Idempotence(unittest.TestCase):
    def test_repeated_initialization_is_noop(self):
        m = full_boot()
        before = (m.intercept, m.gate, m.spytask, m.kbd)
        self.assertFalse(m.init_core())
        self.assertIs(m.install_intercept(), InterceptState.INSTALLED)
        self.assertIs(m.create_spytask(), TaskState.RUNNING)
        self.assertIs(m.file_modules_finished(True), GateState.READY)
        self.assertEqual((m.intercept, m.gate, m.spytask, m.kbd), before)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_second_creation_of_same_task_is_not_replaced_again(self):
        m = booted()
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.REPLACE)
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
        self.assertEqual([e for e, _ in m.trace].count("kbd_running"), 1)

    def test_refused_intercept_stays_refused(self):
        m = rt.RuntimeLifecycle()
        m.init_core()
        self.assertIs(m.install_intercept(), InterceptState.REFUSED)
        self.assertIs(m.install_intercept(), InterceptState.REFUSED)


class FailurePaths(unittest.TestCase):
    def test_fs_failure_blocks_spytask_and_key_handling(self):
        m = booted()
        m.create_spytask()
        m.on_firmware_create_task("PhySw")
        m.on_firmware_create_task("InitFileModules")
        self.assertIs(m.file_modules_finished(False), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertFalse(m.chdk_key_handling)
        # A later success cannot revive a failed gate.
        self.assertIs(m.file_modules_finished(True), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_fault_before_tasks_routes_everything_to_stock(self):
        m = booted()
        m.report_failure("test", "injected")
        for name in ("PhySw", "InitFileModules"):
            self.assertIs(m.on_firmware_create_task(name).action, Action.PASS_THROUGH)
        self.assertIs(m.create_spytask(), TaskState.NOT_CREATED)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)
        self.assertIs(m.gate, GateState.NOT_ARMED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_fault_while_armed_prevents_ready(self):
        m = booted()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.report_failure("test", "injected")
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertIs(m.file_modules_finished(True), GateState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_first_fault_wins(self):
        m = booted()
        m.report_failure("a", "first")
        m.report_failure("b", "second")
        self.assertEqual(m.fault, "a: first")

    def test_fault_blocks_intercept_install(self):
        m = rt.RuntimeLifecycle(rt.HYPOTHETICAL_ALL_VERIFIED)
        m.init_core()
        m.report_failure("test", "injected")
        self.assertIs(m.install_intercept(), InterceptState.NOT_INSTALLED)


class Gm110cDefaults(unittest.TestCase):
    """With current GM1.10C evidence nothing downstream may activate."""

    def test_default_preconditions_are_all_unverified(self):
        self.assertEqual(rt.GM110C_PRECONDITIONS, rt.Preconditions(False, False, False))
        self.assertIs(rt.RuntimeLifecycle().preconditions, rt.GM110C_PRECONDITIONS)

    def test_default_boot_activates_nothing(self):
        m = rt.RuntimeLifecycle()
        m.init_core()
        self.assertIs(m.install_intercept(), InterceptState.REFUSED)
        m.create_spytask()
        for name in ("PhySw", "InitFileModules", "FileWrite"):
            self.assertIs(m.on_firmware_create_task(name).action, Action.PASS_THROUGH)
        m.file_modules_finished(True)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)
        self.assertFalse(m.chdk_key_handling)
        self.assertFalse(m.hardware_execution_authorized)


class Port11bSafetyScenarios(unittest.TestCase):
    """PORT-11B Phase 2-5 regression scenarios."""

    def test_static_evidence_present_but_runtime_authorization_absent(self):
        # U1, U2 entry, and U3 are STATIC_VERIFIED in GM110C_STATIC_EVIDENCE,
        # but GM110C_PRECONDITIONS remains all False and never authorizes activation.
        ev = rt.GM110C_STATIC_EVIDENCE
        self.assertTrue(ev.static_targets_verified)
        self.assertIs(ev.u1_create_task_prologue_and_continuation, EvidenceStatus.STATIC_VERIFIED)
        self.assertIs(ev.u2_init_file_modules_entry, EvidenceStatus.STATIC_VERIFIED)
        self.assertIs(ev.u2_sd_fat_mount_readiness, EvidenceStatus.UNKNOWN)
        self.assertIs(ev.u3_physw_creator_entry_and_strictly_chain, EvidenceStatus.STATIC_VERIFIED)
        self.assertIs(ev.u4_spytask_creation_priority_and_dependencies, EvidenceStatus.UNKNOWN)
        self.assertFalse(ev.authorizes_runtime_activation)

        m = rt.RuntimeLifecycle(
            preconditions=rt.GM110C_PRECONDITIONS,
            static_evidence=ev,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.init_core()
        self.assertIs(m.install_intercept(), InterceptState.REFUSED)
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
        self.assertIs(m.on_firmware_create_task("InitFileModules").action, Action.PASS_THROUGH)
        self.assertIs(m.gate, GateState.NOT_ARMED)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)
        self.assertFalse(m.hardware_execution_authorized)

    def test_init_file_modules_created_but_not_started_blocks_spytask(self):
        m = synthetic_port11b_boot()
        m.create_spytask()
        d = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d.action, Action.REPLACE)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertIs(m.fs.stage, FilesystemStage.TASK_CREATED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        # Attempting to jump directly to init_returned_normally before started fails closed.
        m.init_file_modules_returned(0)
        self.assertIs(m.fs.stage, FilesystemStage.FAILED)
        self.assertIs(m.gate, GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_init_returns_zero_and_event_5006_do_not_prove_mount_readiness(self):
        # PORT-11A S2B: sub_fc0d9ccc always returns 0 on normal return;
        # event 0x5006 is not sufficient to prove mount readiness.
        m = synthetic_port11b_boot(static_evidence=rt.GM110C_STATIC_EVIDENCE)
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        self.assertIs(m.init_file_modules_started(), FilesystemStage.TASK_STARTED)
        self.assertIs(
            m.init_file_modules_returned(return_code=0, event_5006_posted=True),
            FilesystemStage.INIT_RETURNED_NORMALLY,
        )
        self.assertIs(m.gate, GateState.ARMED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        # Because u2_sd_fat_mount_readiness is UNKNOWN in GM110C_STATIC_EVIDENCE,
        # attempting to claim mount observation fails closed.
        self.assertIs(m.record_mount_observation(True), FilesystemStage.FAILED)
        self.assertIs(m.gate, GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_mount_observed_without_fs_io_readiness_blocks_spytask(self):
        m = synthetic_port11b_boot()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started()
        m.init_file_modules_returned(0)
        self.assertIs(m.record_mount_observation(True), FilesystemStage.MOUNT_OBSERVED)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        # Skipping fs_io_ready to claim warm_restart_safe fails closed.
        self.assertIs(m.record_warm_restart_storage_safety(True), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_filesystem_ready_without_warm_restart_safety_blocks_spytask(self):
        m = synthetic_port11b_boot()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started()
        m.init_file_modules_returned(0)
        m.record_mount_observation(True)
        self.assertIs(m.record_filesystem_io_readiness(True), FilesystemStage.FS_IO_READY)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        # Explicit False on warm_restart_safe fails closed.
        self.assertIs(m.record_warm_restart_storage_safety(False), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_stale_boot_generation_readiness_evidence_rejected(self):
        m = synthetic_port11b_boot(boot_generation=2)
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started(boot_generation=2)
        m.init_file_modules_returned(0, boot_generation=2)
        # Observation from earlier boot generation 1 must fail closed.
        self.assertIs(
            m.record_mount_observation(True, boot_generation=1),
            FilesystemStage.FAILED,
        )
        self.assertIs(m.gate, GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertIn("boot generation", m.fault)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_explicit_failure_or_ambiguous_status_blocks_spytask(self):
        for label, call_fn in (
            ("nonzero_init_return", lambda m: m.init_file_modules_returned(return_code=1)),
            ("ambiguous_init_status", lambda m: m.init_file_modules_returned(return_code=0, status="ambiguous")),
            ("unobserved_mount", lambda m: (m.init_file_modules_returned(0), m.record_mount_observation(None))),
            ("ambiguous_mount", lambda m: (m.init_file_modules_returned(0), m.record_mount_observation(True, status="stale"))),
            ("ambiguous_io", lambda m: (
                m.init_file_modules_returned(0),
                m.record_mount_observation(True),
                m.record_filesystem_io_readiness(True, status="unknown"),
            )),
            ("ambiguous_warm_restart", lambda m: (
                m.init_file_modules_returned(0),
                m.record_mount_observation(True),
                m.record_filesystem_io_readiness(True),
                m.record_warm_restart_storage_safety(True, status="ambiguous"),
            )),
        ):
            with self.subTest(case=label):
                m = synthetic_port11b_boot()
                m.create_spytask()
                m.on_firmware_create_task("InitFileModules")
                m.init_file_modules_started()
                call_fn(m)
                self.assertIs(m.fs.stage, FilesystemStage.FAILED)
                self.assertIs(m.gate, GateState.FAILED)
                self.assertIs(m.spytask, TaskState.FAILED)
                self.assertEqual(rt.check_trace(m.trace), [])

    def test_duplicate_init_file_modules_creation_blocked(self):
        m = synthetic_port11b_boot()
        d1 = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d1.action, Action.REPLACE)
        d2 = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d2.action, Action.PASS_THROUGH)
        events = [e for e, _ in m.trace]
        self.assertIn("duplicate_task_creation_blocked", events)
        self.assertEqual(events.count("gate_armed"), 1)
        self.assertEqual(events.count("fs_task_created"), 1)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_physw_creation_through_create_task_strictly(self):
        m = synthetic_port11b_boot()
        d = m.on_firmware_create_task("PhySw")
        self.assertIs(d.action, Action.REPLACE)
        self.assertEqual(d.entry, "mykbd_task")
        self.assertIs(d.mechanism, CreationMechanism.CREATE_TASK_STRICTLY)
        self.assertIn(("create_task_strictly_forwarded", "PhySw"), m.trace)
        self.assertIs(m.kbd, TaskState.RUNNING)

        # If CreateTaskStrictly forwarding safety is UNKNOWN, PhySw replacement fails closed.
        bad_contract = replace(
            rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
            static_prologue_and_boundaries=EvidenceStatus.STATIC_VERIFIED,
            create_task_strictly_forwarding_safe=EvidenceStatus.UNKNOWN,
        )
        m2 = rt.RuntimeLifecycle(
            preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m2.init_core()
        m2.install_intercept()
        m2.hook_contract = bad_contract
        d2 = m2.on_firmware_create_task("PhySw")
        self.assertIs(d2.action, Action.PASS_THROUGH)
        self.assertIs(m2.kbd, TaskState.NOT_CREATED)
        self.assertIsNotNone(m2.fault)

    def test_missing_or_invalid_creator_guard_or_predecessors_rejected(self):
        bad_contexts = (
            ("missing_predecessors", CreatorCallContext(predecessor_calls_preserved=False)),
            ("guard_not_checked", CreatorCallContext(singleton_guard_checked=False)),
            ("guard_already_set", CreatorCallContext(singleton_guard_clear=False)),
            ("physw_handle_not_stored", CreatorCallContext(
                mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
                handle_stored_on_return=False,
            )),
        )
        for label, ctx in bad_contexts:
            with self.subTest(case=label):
                m = synthetic_port11b_boot()
                m.create_spytask()
                d = m.on_firmware_create_task("PhySw", context=ctx)
                self.assertIs(d.action, Action.PASS_THROUGH)
                self.assertIs(m.kbd, TaskState.NOT_CREATED)
                self.assertIs(m.spytask, TaskState.FAILED)
                self.assertIsNotNone(m.fault)
                self.assertEqual(rt.check_trace(m.trace), [])

    def test_unknown_interrupt_or_cache_safety_blocks_hook_install(self):
        # Default GM110C_HOOK_CONTRACT has UNKNOWN runtime fields (patch context, IRQ, I-cache, continuation).
        self.assertTrue(rt.GM110C_HOOK_CONTRACT.static_prerequisites_satisfied)
        self.assertFalse(rt.GM110C_HOOK_CONTRACT.runtime_prerequisites_satisfied)
        self.assertFalse(rt.GM110C_HOOK_CONTRACT.all_satisfied)

        for field_name in (
            "patch_execution_context_safe",
            "interrupt_masking_and_concurrency_safe",
            "icache_and_branch_predictor_coherent",
            "continuation_behavior_safe",
        ):
            with self.subTest(missing=field_name):
                incomplete = replace(
                    rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                    **{field_name: EvidenceStatus.UNKNOWN},
                )
                m = rt.RuntimeLifecycle(
                    preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
                    static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
                    hook_contract=incomplete,
                )
                m.init_core()
                self.assertIs(m.install_intercept(), InterceptState.REFUSED)
                self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
                self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_spytask_blocked_by_u4_when_u4_remains_unknown(self):
        evidence_u4_unknown = replace(
            rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            u4_spytask_creation_priority_and_dependencies=EvidenceStatus.UNKNOWN,
        )
        m = synthetic_port11b_boot(static_evidence=evidence_u4_unknown)
        m.create_spytask()
        m.on_firmware_create_task("PhySw")
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started()
        m.init_file_modules_returned(0)
        m.record_mount_observation(True)
        m.record_filesystem_io_readiness(True)
        m.record_warm_restart_storage_safety(True)

        self.assertIs(m.gate, GateState.READY)
        self.assertTrue(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        self.assertFalse(m.chdk_key_handling)
        self.assertIn(
            ("spytask_blocked_u4", "U4 SpyTask creation/priority/dependencies UNKNOWN"),
            m.trace,
        )
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_complete_synthetic_readiness_passes_model_but_never_authorizes_hardware(self):
        m = synthetic_port11b_boot(boot_generation=3)
        m.create_spytask()
        d_physw = m.on_firmware_create_task("PhySw")
        d_fs = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d_physw.action, Action.REPLACE)
        self.assertIs(d_fs.action, Action.REPLACE)
        self.assertIs(m.init_file_modules_started(boot_generation=3), FilesystemStage.TASK_STARTED)
        self.assertIs(m.init_file_modules_returned(0, boot_generation=3), FilesystemStage.INIT_RETURNED_NORMALLY)
        self.assertIs(m.record_mount_observation(True, boot_generation=3), FilesystemStage.MOUNT_OBSERVED)
        self.assertIs(m.record_filesystem_io_readiness(True, boot_generation=3), FilesystemStage.FS_IO_READY)
        self.assertIs(m.record_warm_restart_storage_safety(True, boot_generation=3), GateState.READY)

        self.assertTrue(m.fs.is_ready)
        self.assertIs(m.fs.stage, FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.spytask, TaskState.RUNNING)
        self.assertIs(m.kbd, TaskState.RUNNING)
        self.assertTrue(m.chdk_key_handling)
        self.assertEqual(rt.check_trace(m.trace), [])
        # Even in a complete synthetic scenario, hardware execution is NEVER authorized,
        # and GM110C_PRECONDITIONS remains all False.
        self.assertFalse(m.hardware_execution_authorized)
        self.assertFalse(m.static_evidence.authorizes_runtime_activation)
        self.assertEqual(rt.GM110C_PRECONDITIONS, rt.Preconditions(False, False, False))


class NegativeControls(unittest.TestCase):
    """The checker and the model must reject bad orderings, not pass vacuously."""

    def bad(self, events):
        return rt.check_trace([(e, "") for e in events])

    def test_checker_rejects_spytask_before_fs_ready(self):
        self.assertIn("spytask_running before fs_ready",
                      self.bad(["core_initialized", "spytask_running", "fs_ready"]))

    def test_checker_rejects_spytask_without_fs_ready(self):
        self.assertTrue(self.bad(["core_initialized", "spytask_running"]))

    def test_checker_rejects_kbd_without_intercept(self):
        self.assertIn("kbd_running without intercept_installed",
                      self.bad(["core_initialized", "kbd_running"]))

    def test_checker_rejects_activation_after_fault(self):
        errs = self.bad(["core_initialized", "intercept_installed", "fault",
                         "kbd_running"])
        self.assertIn("kbd_running after fault", errs)

    def test_checker_rejects_duplicate_start(self):
        errs = self.bad(["core_initialized", "intercept_installed", "fs_ready",
                         "spytask_running", "spytask_running"])
        self.assertIn("spytask_running occurs 2 times", errs)

    def test_checker_rejects_out_of_order_filesystem_stages(self):
        errs = self.bad([
            "core_initialized",
            "intercept_installed",
            "fs_task_created",
            "fs_mount_observed",
            "fs_task_started",
        ])
        self.assertIn("fs_mount_observed before fs_init_returned_normally", errs)

    def test_checker_accepts_valid_reference_trace(self):
        self.assertEqual(rt.check_trace(full_boot().trace), [])

    def test_upstream_timeout_semantics_would_be_rejected(self):
        # Emulate r5491 core_spytask: after the wait loop it runs regardless.
        m = booted()
        m.create_spytask()
        m.spytask = TaskState.RUNNING
        m.trace.append(("spytask_running", "upstream timeout bypass"))
        self.assertIn("spytask_running before fs_ready", rt.check_trace(m.trace))

    def test_unlisted_task_is_never_replaced(self):
        m = booted()
        for name in ("FileWrite", "CaptSeqTask", "TricInitTask", "Startup"):
            self.assertIs(m.on_firmware_create_task(name).action, Action.PASS_THROUGH)


class OfflineOnly(unittest.TestCase):
    """The model must stay standard-library, side-effect free and address free."""

    def setUp(self):
        self.src = MODEL_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.src)

    def test_imports_are_allowlisted(self):
        allowed = {"dataclasses", "enum"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            self.assertLessEqual(names, allowed)

    def test_no_io_or_dynamic_execution_calls(self):
        banned = {"open", "exec", "eval", "compile", "__import__"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, banned)

    def test_no_firmware_addresses(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, int):
                self.assertLess(abs(node.value), 0x10000, node.value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotRegex(node.value, r"0x[0-9A-Fa-f]{5,}")


if __name__ == "__main__":
    unittest.main()
