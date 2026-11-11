#!/usr/bin/env python3
"""tests/test_port12c_spytask_u4.py

PORT-12C: Deterministic offline verification of U4 SpyTask scheduling,
gating contracts, parameter separation, and synthetic failure traces.

Safety: Zero ROM scans, zero hardware interactions, zero firmware execution.
"""

import unittest
import sys
from pathlib import Path

# Ground to local repository root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import tools.port9a_runtime_lifecycle as rt


def make_booted_lifecycle(pre=rt.HYPOTHETICAL_ALL_VERIFIED,
                          static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
                          hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                          boot_generation=1):
    """Test-only helper: initialize core and intercept under explicit test contracts."""
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
    """TEST-ONLY helper: step through all 6 filesystem readiness stages."""
    m.init_file_modules_started(boot_generation=boot_generation)
    m.init_file_modules_returned(0, boot_generation=boot_generation)
    m.record_mount_observation(True, boot_generation=boot_generation)
    m.record_filesystem_io_readiness(True, boot_generation=boot_generation)
    m.record_warm_restart_storage_safety(True, boot_generation=boot_generation)
    return m.file_modules_finished(True, boot_generation=boot_generation)


class TestPort12cSpyTaskU4Contract(unittest.TestCase):
    """Offline test suite for PORT-12C SpyTask scheduling and gating contract."""

    def test_gm110c_baseline_evidence_u4_is_unknown(self):
        """Invariant: In GM1.10C baseline evidence, U4 must be strictly UNKNOWN."""
        self.assertEqual(
            rt.GM110C_STATIC_EVIDENCE.u4_spytask_creation_priority_and_dependencies,
            rt.EvidenceStatus.UNKNOWN,
            "U4 SpyTask creation, priority, and dependencies must be UNKNOWN in GM110C_STATIC_EVIDENCE."
        )

    def test_trace1_early_start_remains_waiting_gate(self):
        """Trace 1: Creating SpyTask early leaves it in WAITING_GATE until filesystem is ready."""
        m = make_booted_lifecycle()
        state = m.create_spytask()
        self.assertEqual(state, rt.TaskState.WAITING_GATE)

        # Create tasks, but filesystem has not completed 6 stages
        m.on_firmware_create_task("InitFileModules")
        self.assertEqual(m.spytask, rt.TaskState.WAITING_GATE, "SpyTask must wait on gate")
        self.assertEqual(m.gate, rt.GateState.ARMED)

    def test_trace2_absent_u2_proof_blocks_spytask(self):
        """Trace 2: If U2 filesystem mount verification fails, gate and SpyTask fail closed."""
        m = make_booted_lifecycle()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started(boot_generation=m.boot_generation)

        # Invalidate mount observation (e.g. status='error')
        m.record_mount_observation(False, boot_generation=m.boot_generation, status="error")
        self.assertEqual(m.gate, rt.GateState.FAILED)
        self.assertEqual(m.spytask, rt.TaskState.FAILED)
        self.assertNotEqual(m.spytask, rt.TaskState.RUNNING)

    def test_trace3_gate_ready_but_u4_unknown_blocks_spytask(self):
        """Trace 3: When gate is READY but U4 is UNKNOWN (GM1.10C profile), SpyTask cannot start."""
        # Use profile where U1-U3 and U2 mount are verified, but U4 is UNKNOWN
        evidence_u4_unknown = rt.StaticEvidenceProfile(
            u1_create_task_prologue_and_continuation=rt.EvidenceStatus.STATIC_VERIFIED,
            u2_init_file_modules_entry=rt.EvidenceStatus.STATIC_VERIFIED,
            u2_sd_fat_mount_readiness=rt.EvidenceStatus.STATIC_VERIFIED,
            u3_physw_creator_entry_and_strictly_chain=rt.EvidenceStatus.STATIC_VERIFIED,
            u4_spytask_creation_priority_and_dependencies=rt.EvidenceStatus.UNKNOWN,
        )
        m = make_booted_lifecycle(static_evidence=evidence_u4_unknown)
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")

        # Advance all filesystem stages
        advance_all_fs_stages_for_test(m)
        self.assertEqual(m.gate, rt.GateState.READY)

        # SpyTask must remain WAITING_GATE because U4 is UNKNOWN
        self.assertEqual(m.spytask, rt.TaskState.WAITING_GATE)
        self.assertNotEqual(m.spytask, rt.TaskState.RUNNING)
        self.assertTrue(any("spytask_blocked_u4" in entry[0] for entry in m.trace))

    def test_trace4_duplicate_spytask_creation_is_ignored(self):
        """Trace 4: Duplicate create_spytask calls do not corrupt task state or re-spawn."""
        m = make_booted_lifecycle()
        state1 = m.create_spytask()
        self.assertEqual(state1, rt.TaskState.WAITING_GATE)

        state2 = m.create_spytask()
        self.assertEqual(state2, rt.TaskState.WAITING_GATE)
        self.assertTrue(any("create_spytask_repeat" in entry[0] for entry in m.trace))

    def test_trace5_generation_mismatch_blocks_spytask(self):
        """Trace 5: Stale boot generation fails the filesystem and transitions SpyTask to FAILED."""
        m = make_booted_lifecycle(boot_generation=2)
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")

        # Attempt to supply signal from generation 1
        m.file_modules_finished(True, boot_generation=1)
        self.assertEqual(m.gate, rt.GateState.FAILED)
        self.assertEqual(m.spytask, rt.TaskState.FAILED)
        self.assertNotEqual(m.spytask, rt.TaskState.RUNNING)

    def test_trace6_fault_after_replacement_contains_spytask(self):
        """Trace 6: CPU fault during or after task replacement prevents SpyTask release."""
        m = make_booted_lifecycle()
        m.create_spytask()
        m.on_firmware_create_task("InitFileModules")

        # Induce fault
        m.report_failure("kernel", "TLB miss in ATCM")
        advance_all_fs_stages_for_test(m)

        # Must not reach RUNNING
        self.assertNotEqual(m.spytask, rt.TaskState.RUNNING)

    def test_spytask_timeout_fails_instead_of_running(self):
        """Unlike legacy CHDK, spytask_gate_timeout() transitions to FAILED (no bypass)."""
        m = make_booted_lifecycle()
        m.create_spytask()
        self.assertEqual(m.spytask, rt.TaskState.WAITING_GATE)

        # Trigger gate timeout
        state = m.spytask_gate_timeout()
        self.assertEqual(state, rt.TaskState.FAILED)
        self.assertIsNotNone(m.fault)
        self.assertIn("gate timeout", m.fault)

    def test_positive_path_when_all_conditions_satisfied(self):
        """Positive verification: When ALL 6 FS stages AND U4 are verified, SpyTask runs."""
        m = make_booted_lifecycle(static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED)
        m.create_spytask()
        m.on_firmware_create_task("PhySw")
        m.on_firmware_create_task("InitFileModules")

        advance_all_fs_stages_for_test(m)
        self.assertEqual(m.gate, rt.GateState.READY)
        self.assertEqual(m.spytask, rt.TaskState.RUNNING)
        self.assertEqual(rt.check_trace(m.trace), [])


if __name__ == "__main__":
    unittest.main()
