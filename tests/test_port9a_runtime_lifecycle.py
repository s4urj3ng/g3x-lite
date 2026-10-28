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


def booted(pre=rt.HYPOTHETICAL_ALL_VERIFIED,
           static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
           hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
           boot_generation=1):
    """Test-only helper that initializes core and installs intercept under explicit synthetic contracts."""
    m = rt.RuntimeLifecycle(
        preconditions=pre,
        static_evidence=static_evidence,
        hook_contract=hook_contract,
        boot_generation=boot_generation,
    )
    m.init_core()
    m.install_intercept()
    return m


def advance_all_fs_stages_for_test(m, boot_generation=None):
    """TEST-ONLY helper: explicitly step through Stages 2-6 and final gate check."""
    m.init_file_modules_started(boot_generation=boot_generation)
    m.init_file_modules_returned(0, boot_generation=boot_generation)
    m.record_mount_observation(True, boot_generation=boot_generation)
    m.record_filesystem_io_readiness(True, boot_generation=boot_generation)
    m.record_warm_restart_storage_safety(True, boot_generation=boot_generation)
    return m.file_modules_finished(True, boot_generation=boot_generation)


def full_boot():
    """Reference order: SpyTask created early (as upstream), PhySw, then all 6 FS stages."""
    m = booted()
    m.create_spytask()
    m.on_firmware_create_task("PhySw")
    m.on_firmware_create_task("InitFileModules")
    advance_all_fs_stages_for_test(m)
    return m


class SpyTaskOrdering(unittest.TestCase):
    def test_spytask_waits_until_fs_ready(self):
        m = booted()
        self.assertIs(m.create_spytask(), TaskState.WAITING_GATE)
        m.on_firmware_create_task("InitFileModules")
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        advance_all_fs_stages_for_test(m)
        self.assertIs(m.spytask, TaskState.RUNNING)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_ready_signal_before_spytask_is_latched(self):
        # Upstream core_spytask clears the flag on entry, so an early signal
        # is lost; the model latches it instead.
        m = booted()
        m.on_firmware_create_task("InitFileModules")
        advance_all_fs_stages_for_test(m)
        self.assertIs(m.create_spytask(), TaskState.RUNNING)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_gate_timeout_fails_instead_of_running(self):
        m = booted()
        m.create_spytask()
        self.assertIs(m.spytask_gate_timeout(), TaskState.FAILED)
        m.on_firmware_create_task("InitFileModules")
        advance_all_fs_stages_for_test(m)
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
        m = rt.RuntimeLifecycle(
            rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.init_core()
        d = m.on_firmware_create_task("PhySw")
        self.assertIs(d.action, Action.PASS_THROUGH)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_no_kbd_with_unverified_physw_entry(self):
        m = booted(rt.Preconditions(True, True, False))
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_intercept_requires_core(self):
        m = rt.RuntimeLifecycle(
            rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        with self.assertRaises(rt.LifecycleError):
            m.install_intercept()

    def test_chdk_key_handling_needs_running_spytask(self):
        m = booted()
        m.on_firmware_create_task("PhySw")
        self.assertFalse(m.chdk_key_handling)  # pass-through only
        m.create_spytask()
        self.assertFalse(m.chdk_key_handling)
        m.on_firmware_create_task("InitFileModules")
        advance_all_fs_stages_for_test(m)
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

    def test_second_creation_of_same_task_is_rejected_not_recreated(self):
        m = booted()
        self.assertIs(m.on_firmware_create_task("PhySw").action, Action.REPLACE)
        d2 = m.on_firmware_create_task("PhySw")
        self.assertIs(d2.action, Action.REJECT_DUPLICATE)
        self.assertEqual(d2.entry, "duplicate_blocked")
        self.assertEqual([e for e, _ in m.trace].count("kbd_running"), 1)
        self.assertNotIn("create_stock", [e for e, _ in m.trace])

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
        m = rt.RuntimeLifecycle(
            rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.init_core()
        m.report_failure("test", "injected")
        self.assertIs(m.install_intercept(), InterceptState.NOT_INSTALLED)


class Gm110cDefaults(unittest.TestCase):
    """With current GM1.10C evidence nothing downstream may activate."""

    def test_default_preconditions_are_all_unverified(self):
        self.assertEqual(rt.GM110C_PRECONDITIONS, rt.Preconditions(False, False, False))
        self.assertIs(rt.RuntimeLifecycle().preconditions, rt.GM110C_PRECONDITIONS)
        self.assertIs(rt.RuntimeLifecycle().static_evidence, rt.GM110C_STATIC_EVIDENCE)
        self.assertIs(rt.RuntimeLifecycle().hook_contract, rt.GM110C_HOOK_CONTRACT)

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
    """PORT-11B Phase 2-5 and PR #16 B1-B4 remediation regression scenarios."""

    def test_static_evidence_present_but_runtime_authorization_absent(self):
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

    def test_b1_file_modules_finished_true_never_auto_promotes_stages(self):
        # Blocker B1 regression: calling file_modules_finished(True) on an armed
        # gate without prior Stage 2-6 witnesses must NEVER synthesize mount, I/O,
        # or warm-restart readiness, even when static_evidence and hook_contract
        # are fully synthetic-verified.
        m = booted(
            pre=rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.create_spytask()
        d = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d.action, Action.REPLACE)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertIs(m.fs.stage, FilesystemStage.TASK_CREATED)

        # Calling file_modules_finished(True) directly at Stage 1 fails closed.
        self.assertIs(m.file_modules_finished(True), GateState.FAILED)
        self.assertIs(m.fs.stage, FilesystemStage.FAILED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertNotIn("fs_ready", [e for e, _ in m.trace])
        self.assertNotIn("fs_mount_observed", [e for e, _ in m.trace])
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_b1_file_modules_finished_true_at_any_partial_stage_fails_closed(self):
        # Verify calling file_modules_finished(True) after Stage 2, 3, 4, or 5
        # still fails closed because Stage 6 (warm_restart_safe) is not established.
        for stop_after in ("started", "returned", "mount", "io"):
            with self.subTest(stop_after=stop_after):
                m = booted()
                m.create_spytask()
                m.on_firmware_create_task("InitFileModules")
                m.init_file_modules_started()
                if stop_after in ("returned", "mount", "io"):
                    m.init_file_modules_returned(0)
                if stop_after in ("mount", "io"):
                    m.record_mount_observation(True)
                if stop_after == "io":
                    m.record_filesystem_io_readiness(True)
                self.assertIs(m.file_modules_finished(True), GateState.FAILED)
                self.assertIs(m.fs.stage, FilesystemStage.FAILED)
                self.assertIs(m.spytask, TaskState.FAILED)
                self.assertEqual(rt.check_trace(m.trace), [])

    def test_b2_missing_or_default_hook_contract_refuses_intercept_even_with_hypothetical_preconditions(self):
        # Blocker B2 regression: RuntimeLifecycle(HYPOTHETICAL_ALL_VERIFIED) with
        # default GM110C_HOOK_CONTRACT or hook_contract=None must refuse install_intercept().
        for label, hc in (("default_gm110c_hook_contract", rt.GM110C_HOOK_CONTRACT),
                          ("none_hook_contract", None)):
            with self.subTest(case=label):
                m = rt.RuntimeLifecycle(
                    preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
                    static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
                    hook_contract=hc,
                )
                m.init_core()
                self.assertIs(m.install_intercept(), InterceptState.REFUSED)
                self.assertIs(m.on_firmware_create_task("PhySw").action, Action.PASS_THROUGH)
                self.assertIs(m.kbd, TaskState.NOT_CREATED)

    def test_b2_u4_unknown_always_blocks_spytask_without_legacy_bypass(self):
        # Blocker B2 regression: even if preconditions == HYPOTHETICAL_ALL_VERIFIED,
        # U4 UNKNOWN in static_evidence (or static_evidence=None) always blocks SpyTask.
        ev_u2_ok_u4_unknown = replace(
            rt.GM110C_STATIC_EVIDENCE,
            u2_sd_fat_mount_readiness=EvidenceStatus.STATIC_VERIFIED,
            u4_spytask_creation_priority_and_dependencies=EvidenceStatus.UNKNOWN,
        )
        m = booted(
            pre=rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=ev_u2_ok_u4_unknown,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        advance_all_fs_stages_for_test(m)
        self.assertIs(m.gate, GateState.READY)
        self.assertTrue(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        self.assertIn(
            ("spytask_blocked_u4", "U4 SpyTask creation/priority/dependencies UNKNOWN"),
            m.trace,
        )

    def test_init_file_modules_created_but_not_started_blocks_spytask(self):
        m = booted()
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
        m = booted(static_evidence=rt.GM110C_STATIC_EVIDENCE)
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
        self.assertIs(m.record_mount_observation(True), FilesystemStage.FAILED)
        self.assertIs(m.gate, GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_mount_observed_without_fs_io_readiness_blocks_spytask(self):
        m = booted()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started()
        m.init_file_modules_returned(0)
        self.assertIs(m.record_mount_observation(True), FilesystemStage.MOUNT_OBSERVED)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        self.assertIs(m.record_warm_restart_storage_safety(True), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_filesystem_ready_without_warm_restart_safety_blocks_spytask(self):
        m = booted()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started()
        m.init_file_modules_returned(0)
        m.record_mount_observation(True)
        self.assertIs(m.record_filesystem_io_readiness(True), FilesystemStage.FS_IO_READY)
        self.assertIs(m.gate, GateState.ARMED)
        self.assertFalse(m.fs.is_ready)
        self.assertIs(m.spytask, TaskState.WAITING_GATE)
        self.assertIs(m.record_warm_restart_storage_safety(False), GateState.FAILED)
        self.assertIs(m.spytask, TaskState.FAILED)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_stale_boot_generation_readiness_evidence_rejected(self):
        m = booted(boot_generation=2)
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started(boot_generation=2)
        m.init_file_modules_returned(0, boot_generation=2)
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
                m = booted()
                m.create_spytask()
                m.on_firmware_create_task("InitFileModules")
                m.init_file_modules_started()
                call_fn(m)
                self.assertIs(m.fs.stage, FilesystemStage.FAILED)
                self.assertIs(m.gate, GateState.FAILED)
                self.assertIs(m.spytask, TaskState.FAILED)
                self.assertEqual(rt.check_trace(m.trace), [])

    def test_b3_duplicate_init_file_modules_creation_returns_reject_duplicate(self):
        # Blocker B3 regression: when intercept is INSTALLED and InitFileModules
        # was already intercepted/replaced once, a second creation request returns
        # Action.REJECT_DUPLICATE ("duplicate_blocked") rather than Action.PASS_THROUGH
        # ("stock"), so no second task (replacement or stock) is created.
        m = booted()
        d1 = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d1.action, Action.REPLACE)
        d2 = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d2.action, Action.REJECT_DUPLICATE)
        self.assertEqual(d2.entry, "duplicate_blocked")
        events = [e for e, _ in m.trace]
        self.assertIn("duplicate_task_creation_blocked", events)
        self.assertNotIn("create_stock", events)
        self.assertEqual(events.count("gate_armed"), 1)
        self.assertEqual(events.count("fs_task_created"), 1)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_b3_repeated_stock_task_calls_without_intercept_remain_pass_through(self):
        # When intercept is NOT_INSTALLED, the offline model has no hook installed
        # and must never claim it blocks Canon firmware on repeated stock requests.
        m = rt.RuntimeLifecycle(
            preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        m.init_core()
        self.assertIs(m.intercept, InterceptState.NOT_INSTALLED)
        for name in ("PhySw", "InitFileModules"):
            d1 = m.on_firmware_create_task(name)
            d2 = m.on_firmware_create_task(name)
            self.assertEqual((d1.action, d1.entry), (Action.PASS_THROUGH, "stock"))
            self.assertEqual((d2.action, d2.entry), (Action.PASS_THROUGH, "stock"))
        events = [e for e, _ in m.trace]
        self.assertNotIn("duplicate_task_creation_blocked", events)
        self.assertEqual(events.count("create_stock"), 4)
        self.assertIsNone(m.fault)

    def test_b3_repeated_stock_task_calls_with_refused_intercept_remain_pass_through(self):
        # When intercept is REFUSED (e.g. GM110C defaults), repeated stock task
        # creation requests must both return PASS_THROUGH ("stock").
        m = rt.RuntimeLifecycle()
        m.init_core()
        self.assertIs(m.install_intercept(), InterceptState.REFUSED)
        for name in ("PhySw", "InitFileModules"):
            d1 = m.on_firmware_create_task(name)
            d2 = m.on_firmware_create_task(name)
            self.assertEqual((d1.action, d1.entry), (Action.PASS_THROUGH, "stock"))
            self.assertEqual((d2.action, d2.entry), (Action.PASS_THROUGH, "stock"))
        events = [e for e, _ in m.trace]
        self.assertNotIn("duplicate_task_creation_blocked", events)
        self.assertEqual(events.count("create_stock"), 4)
        self.assertIsNone(m.fault)

    def test_b3_invalid_creator_context_falls_back_to_stock_and_never_claims_duplicate_blocked(self):
        # When creator-context validation fails on a listed task, the model latches
        # a fault and falls back to stock creation (PASS_THROUGH, not replaced).
        # A subsequent request for the same or another listed task also falls back
        # to stock PASS_THROUGH and must NEVER claim REJECT_DUPLICATE.
        m = booted()
        bad_ctx = CreatorCallContext(
            mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
            predecessor_calls_preserved=False,
        )
        d1 = m.on_firmware_create_task("PhySw", context=bad_ctx)
        self.assertEqual((d1.action, d1.entry), (Action.PASS_THROUGH, "stock"))
        self.assertIsNotNone(m.fault)
        self.assertIs(m.kbd, TaskState.NOT_CREATED)

        # Second call for PhySw (which was never replaced, only fell back to stock)
        # and a call for InitFileModules both remain PASS_THROUGH ("stock").
        d2 = m.on_firmware_create_task("PhySw")
        d3 = m.on_firmware_create_task("InitFileModules")
        self.assertEqual((d2.action, d2.entry), (Action.PASS_THROUGH, "stock"))
        self.assertEqual((d3.action, d3.entry), (Action.PASS_THROUGH, "stock"))
        events = [e for e, _ in m.trace]
        self.assertNotIn("duplicate_task_creation_blocked", events)
        self.assertNotIn("create_replaced", events)
        self.assertEqual(events.count("create_stock"), 3)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_b3_invalid_context_does_not_fault_stock_pass_through_paths(self):
        # Blocker B3 regression: when intercept is NOT installed or task is
        # unlisted, passing an invalid CreatorCallContext must NOT latch a fault
        # on the stock pass-through path.
        bad_ctx = CreatorCallContext(predecessor_calls_preserved=False, singleton_guard_checked=False)

        # Case 1: intercept refused (default GM110C mode)
        m_stock = rt.RuntimeLifecycle()
        m_stock.init_core()
        m_stock.install_intercept()
        d_stock = m_stock.on_firmware_create_task("PhySw", context=bad_ctx)
        self.assertIs(d_stock.action, Action.PASS_THROUGH)
        self.assertIsNone(m_stock.fault)

        # Case 2: intercept installed, but task is unlisted ("FileWrite")
        m_unlisted = booted()
        d_unlisted = m_unlisted.on_firmware_create_task("FileWrite", context=bad_ctx)
        self.assertIs(d_unlisted.action, Action.PASS_THROUGH)
        self.assertIsNone(m_unlisted.fault)

    def test_b4_physw_creation_enforces_create_task_strictly_mechanism(self):
        # Blocker B4 regression: PhySw must use CREATE_TASK_STRICTLY; passing
        # CREATE_TASK for PhySw (to skip the CreateTaskStrictly forwarding check)
        # or CREATE_TASK_STRICTLY for InitFileModules is rejected with a fault.
        m = booted()
        self.assertTrue(rt.DEFAULT_PHYSW_CONTEXT.is_synthetic_witness_only)
        d = m.on_firmware_create_task("PhySw")
        self.assertIs(d.action, Action.REPLACE)
        self.assertEqual(d.entry, "mykbd_task")
        self.assertIs(d.mechanism, CreationMechanism.CREATE_TASK_STRICTLY)
        self.assertIn(("create_task_strictly_forwarded", "PhySw"), m.trace)
        self.assertIs(m.kbd, TaskState.RUNNING)

        # Passing CREATE_TASK for PhySw is rejected fail-closed.
        m_wrong_physw = booted()
        wrong_physw_ctx = CreatorCallContext(mechanism=CreationMechanism.CREATE_TASK)
        d_wrong = m_wrong_physw.on_firmware_create_task("PhySw", context=wrong_physw_ctx)
        self.assertIs(d_wrong.action, Action.PASS_THROUGH)
        self.assertIs(m_wrong_physw.kbd, TaskState.NOT_CREATED)
        self.assertIn("expected CREATE_TASK_STRICTLY", m_wrong_physw.fault)

        # Passing CREATE_TASK_STRICTLY for InitFileModules is also rejected fail-closed.
        m_wrong_fs = booted()
        wrong_fs_ctx = CreatorCallContext(mechanism=CreationMechanism.CREATE_TASK_STRICTLY)
        d_wrong_fs = m_wrong_fs.on_firmware_create_task("InitFileModules", context=wrong_fs_ctx)
        self.assertIs(d_wrong_fs.action, Action.PASS_THROUGH)
        self.assertIs(m_wrong_fs.gate, GateState.NOT_ARMED)
        self.assertIn("expected CREATE_TASK", m_wrong_fs.fault)

        # If CreateTaskStrictly forwarding safety is UNKNOWN, PhySw replacement fails closed.
        bad_contract = replace(
            rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
            create_task_strictly_forwarding_safe=EvidenceStatus.UNKNOWN,
        )
        m2 = booted()
        m2.hook_contract = bad_contract
        d2 = m2.on_firmware_create_task("PhySw")
        self.assertIs(d2.action, Action.PASS_THROUGH)
        self.assertIs(m2.kbd, TaskState.NOT_CREATED)
        self.assertIsNotNone(m2.fault)

    def test_missing_or_invalid_creator_guard_or_predecessors_rejected(self):
        bad_contexts = (
            ("missing_predecessors", CreatorCallContext(
                mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
                predecessor_calls_preserved=False,
            )),
            ("guard_not_checked", CreatorCallContext(
                mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
                singleton_guard_checked=False,
            )),
            ("guard_already_set", CreatorCallContext(
                mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
                singleton_guard_clear=False,
            )),
            ("physw_handle_not_stored", CreatorCallContext(
                mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
                handle_stored_on_return=False,
            )),
        )
        for label, ctx in bad_contexts:
            with self.subTest(case=label):
                m = booted()
                m.create_spytask()
                d = m.on_firmware_create_task("PhySw", context=ctx)
                self.assertIs(d.action, Action.PASS_THROUGH)
                self.assertIs(m.kbd, TaskState.NOT_CREATED)
                self.assertIs(m.spytask, TaskState.FAILED)
                self.assertIsNotNone(m.fault)
                self.assertEqual(rt.check_trace(m.trace), [])

    def test_unknown_interrupt_or_cache_safety_blocks_hook_install(self):
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
        m = booted(static_evidence=evidence_u4_unknown)
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
        m = booted(boot_generation=3)
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
        self.assertIs(m.file_modules_finished(True, boot_generation=3), GateState.READY)

        self.assertTrue(m.fs.is_ready)
        self.assertIs(m.fs.stage, FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.spytask, TaskState.RUNNING)
        self.assertIs(m.kbd, TaskState.RUNNING)
        self.assertTrue(m.chdk_key_handling)
        self.assertEqual(rt.check_trace(m.trace), [])
        self.assertFalse(m.hardware_execution_authorized)
        self.assertFalse(m.static_evidence.authorizes_runtime_activation)
        self.assertEqual(rt.GM110C_PRECONDITIONS, rt.Preconditions(False, False, False))

    def test_post_ready_invalid_observations_fail_closed_and_block_late_spytask(self):
        # Independent Review Blocker B1: once GateState.READY is reached,
        # subsequent stale, ambiguous, or failed observations MUST fail closed
        # and prevent a late create_spytask() from becoming RUNNING.
        def reach_ready(boot_generation=2):
            m = booted(boot_generation=boot_generation)
            m.on_firmware_create_task("InitFileModules")
            m.init_file_modules_started(boot_generation=boot_generation)
            m.init_file_modules_returned(0, boot_generation=boot_generation)
            m.record_mount_observation(True, boot_generation=boot_generation)
            m.record_filesystem_io_readiness(True, boot_generation=boot_generation)
            m.record_warm_restart_storage_safety(True, boot_generation=boot_generation)
            self.assertIs(m.gate, GateState.READY)
            self.assertTrue(m.fs.is_ready)
            return m

        scenarios = (
            (
                "stale_mount_after_ready",
                lambda m: m.record_mount_observation(True, boot_generation=1),
            ),
            (
                "ambiguous_io_after_ready",
                lambda m: m.record_filesystem_io_readiness(True, status="ambiguous"),
            ),
            (
                "failed_warm_restart_after_ready",
                lambda m: m.record_warm_restart_storage_safety(False),
            ),
            (
                "file_modules_finished_false_after_ready",
                lambda m: m.file_modules_finished(False),
            ),
            (
                "stale_started_after_ready",
                lambda m: m.init_file_modules_started(boot_generation=1),
            ),
            (
                "failed_returned_after_ready",
                lambda m: m.init_file_modules_returned(1),
            ),
            (
                "none_mount_after_ready",
                lambda m: m.record_mount_observation(None),
            ),
            (
                "none_io_after_ready",
                lambda m: m.record_filesystem_io_readiness(None),
            ),
            (
                "none_warm_restart_after_ready",
                lambda m: m.record_warm_restart_storage_safety(None),
            ),
            (
                "none_file_modules_finished_after_ready",
                lambda m: m.file_modules_finished(None),
            ),
        )
        for name, invalidate in scenarios:
            with self.subTest(scenario=name):
                # Subcase A: late SpyTask creation AFTER invalid post-READY observation
                m = reach_ready(boot_generation=2)
                invalidate(m)
                self.assertIs(m.gate, GateState.FAILED)
                self.assertIs(m.fs.stage, FilesystemStage.FAILED)
                self.assertFalse(m.fs.is_ready)
                self.assertIsNotNone(m.fault)
                self.assertIs(m.create_spytask(), TaskState.NOT_CREATED)
                self.assertIsNot(m.spytask, TaskState.RUNNING)
                self.assertFalse(m.chdk_key_handling)
                self.assertEqual(rt.check_trace(m.trace), [])

                # Subcase B: SpyTask was already RUNNING at READY, then invalid observation arrives
                m_run = reach_ready(boot_generation=2)
                self.assertIs(m_run.create_spytask(), TaskState.RUNNING)
                invalidate(m_run)
                self.assertIs(m_run.gate, GateState.FAILED)
                self.assertIs(m_run.fs.stage, FilesystemStage.FAILED)
                self.assertIs(m_run.spytask, TaskState.FAILED)
                self.assertFalse(m_run.chdk_key_handling)
                self.assertEqual(rt.check_trace(m_run.trace), [])

    def test_post_ready_valid_same_generation_calls_remain_idempotent(self):
        # Valid same-generation repeat calls after READY remain idempotent without
        # duplicating trace events.
        m = full_boot()
        self.assertIs(m.gate, GateState.READY)
        self.assertIs(m.spytask, TaskState.RUNNING)
        trace_before = list(m.trace)
        self.assertIs(m.init_file_modules_started(), FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.init_file_modules_returned(0), FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.record_mount_observation(True), FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.record_filesystem_io_readiness(True), FilesystemStage.WARM_RESTART_SAFE)
        self.assertIs(m.record_warm_restart_storage_safety(True), GateState.READY)
        self.assertIs(m.file_modules_finished(True), GateState.READY)
        self.assertEqual(m.trace, trace_before)
        self.assertIsNone(m.fault)
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_stock_before_intercept_refuses_replacement_for_physw_and_init_file_modules(self):
        # Independent Review Blocker B2:
        # 1. Create stock PhySw or InitFileModules without intercept.
        # 2. Install intercept.
        # 3. Receive another creation request for the same task.
        # Must NOT return Action.REPLACE (no parallel CHDK singleton while stock
        # task may still exist) and must NOT return Action.REJECT_DUPLICATE (cannot
        # retroactively block Canon's stock task). Must latch a fault and return
        # Action.PASS_THROUGH ("stock").
        for task_name in ("PhySw", "InitFileModules"):
            with self.subTest(task=task_name):
                m = rt.RuntimeLifecycle(
                    preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
                    static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
                    hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                    boot_generation=1,
                )
                m.init_core()
                d_stock = m.on_firmware_create_task(task_name)
                self.assertEqual((d_stock.action, d_stock.entry), (Action.PASS_THROUGH, "stock"))
                self.assertIn(task_name, m.stock_owned_singletons)
                self.assertNotIn(task_name, m.replaced_singletons)

                self.assertIs(m.install_intercept(), InterceptState.INSTALLED)
                d_after = m.on_firmware_create_task(task_name)
                self.assertEqual((d_after.action, d_after.entry), (Action.PASS_THROUGH, "stock"))
                self.assertNotIn(task_name, m.replaced_singletons)
                self.assertIsNotNone(m.fault)
                self.assertIn(f"stock {task_name} singleton already created before intercept", m.fault)
                self.assertIn(("stock_singleton_conflict", task_name), m.trace)
                self.assertIs(m.kbd, TaskState.NOT_CREATED)
                self.assertIs(m.gate, GateState.NOT_ARMED)
                self.assertEqual(rt.check_trace(m.trace), [])

        # Only a fresh RuntimeLifecycle for a new boot_generation resets singleton ownership.
        m_gen2 = booted(boot_generation=2)
        self.assertEqual(m_gen2.stock_owned_singletons, frozenset())
        self.assertIs(m_gen2.on_firmware_create_task("PhySw").action, Action.REPLACE)
        self.assertIs(m_gen2.on_firmware_create_task("InitFileModules").action, Action.REPLACE)

    def test_n2_duplicate_replaced_task_rejected_even_after_subsequent_fault(self):
        # Independent Review N2: once a listed singleton was replaced
        # (task_name in self._replaced), a subsequent duplicate creation request
        # for that replaced task resolves to Action.REJECT_DUPLICATE even after
        # a later fault is latched, whereas an unreplaced task falls back to
        # Action.PASS_THROUGH.
        m = booted()
        d1 = m.on_firmware_create_task("PhySw")
        self.assertEqual((d1.action, d1.entry), (Action.REPLACE, "mykbd_task"))
        self.assertIn("PhySw", m.replaced_singletons)

        m.report_failure("External", "fault after PhySw replacement")
        d_dup = m.on_firmware_create_task("PhySw")
        self.assertEqual((d_dup.action, d_dup.entry), (Action.REJECT_DUPLICATE, "duplicate_blocked"))

        d_other = m.on_firmware_create_task("InitFileModules")
        self.assertEqual((d_other.action, d_other.entry), (Action.PASS_THROUGH, "stock"))
        self.assertEqual(rt.check_trace(m.trace), [])

    def test_stock_observation_does_not_leak_across_boot_generations(self):
        # Boot generation boundary: Stock observation in generation 1 does not leak into
        # generation 2 (tested both via lifecycle reset and separate lifecycle instance).
        m = rt.RuntimeLifecycle(
            preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
            boot_generation=1,
        )
        m.init_core()
        # Gen 1: Stock creation observed without intercept
        d1_p = m.on_firmware_create_task("PhySw")
        d1_f = m.on_firmware_create_task("InitFileModules")
        self.assertEqual((d1_p.action, d1_p.entry), (Action.PASS_THROUGH, "stock"))
        self.assertEqual((d1_f.action, d1_f.entry), (Action.PASS_THROUGH, "stock"))
        self.assertIn("PhySw", m._stock_observed)
        self.assertIn("InitFileModules", m._stock_observed)

        # In-place reset for Generation 2: clears stock observation and replaced lists
        m.reset(boot_generation=2)
        self.assertEqual(m.boot_generation, 2)
        self.assertEqual(m._stock_observed, [])
        self.assertEqual(m._replaced, [])
        self.assertIs(m.intercept, InterceptState.NOT_INSTALLED)
        self.assertIsNone(m.fault)

        # In Gen 2, install intercept and create tasks -> properly replaced!
        m.init_core()
        self.assertIs(m.install_intercept(), InterceptState.INSTALLED)
        d2_p = m.on_firmware_create_task("PhySw")
        self.assertIs(d2_p.action, Action.REPLACE)
        self.assertEqual(d2_p.entry, "mykbd_task")
        self.assertIs(m.kbd, TaskState.RUNNING)

        d2_f = m.on_firmware_create_task("InitFileModules")
        self.assertIs(d2_f.action, Action.REPLACE)
        self.assertEqual(d2_f.entry, "init_file_modules_task")
        self.assertIs(m.gate, GateState.ARMED)
        self.assertTrue(m.fs.task_created)

        # Separate lifecycle instances also do not leak stock observations
        m_sep1 = rt.RuntimeLifecycle(boot_generation=1)
        m_sep1.init_core()
        m_sep1.on_firmware_create_task("PhySw")
        self.assertIn("PhySw", m_sep1._stock_observed)
        m_sep2 = rt.RuntimeLifecycle(boot_generation=2)
        self.assertEqual(m_sep2._stock_observed, [])


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

    def test_checker_rejects_create_replaced_after_fault_even_if_first_was_before_fault(self):
        # Codex Red Team QA finding regression:
        # A trace containing create_replaced before fault and another create_replaced
        # after fault must not evade detection by only checking the first occurrence.
        errs_multi = self.bad([
            "core_initialized",
            "intercept_installed",
            "create_replaced",
            "fault",
            "create_replaced",
        ])
        self.assertIn("create_replaced after fault", errs_multi)

        # Single occurrence after fault is also rejected
        errs_single = self.bad([
            "core_initialized",
            "intercept_installed",
            "fault",
            "create_replaced",
        ])
        self.assertIn("create_replaced after fault", errs_single)

    def test_checker_rejects_spytask_after_fs_failed(self):
        errs = self.bad([
            "core_initialized",
            "intercept_installed",
            "fs_task_created",
            "fs_task_started",
            "fs_init_returned_normally",
            "fs_mount_observed",
            "fs_io_ready",
            "fs_warm_restart_safe",
            "fs_ready",
            "fs_failed",
            "spytask_running",
        ])
        self.assertIn("spytask_running after fs_failed", errs)

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
