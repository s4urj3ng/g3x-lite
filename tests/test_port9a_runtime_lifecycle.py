"""PORT-9A: offline tests for tools/port9a_runtime_lifecycle.py.

Runs on any clean clone. Standard library only; no subprocess, ROM, binary,
build or hardware access. The model encodes ordering rules, not GM1.10C facts.

Run:
  python3 -B -m unittest discover -s tests -p 'test_port9a_*.py' -v
"""

import ast
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO_ROOT / "tools" / "port9a_runtime_lifecycle.py"
sys.path.insert(0, str(REPO_ROOT / "tools"))

import port9a_runtime_lifecycle as rt  # noqa: E402
from port9a_runtime_lifecycle import (  # noqa: E402
    Action, GateState, InterceptState, TaskState,
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
