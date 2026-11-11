#!/usr/bin/env python3
"""tests/test_port12b_filesystem_u2.py

PORT-12B: Deterministic offline verification of U2 filesystem readiness proof obligations,
generation binding, event 0x5006 insufficiency, and fail-closed precondition invariants.

Safety: Zero ROM scans, zero hardware interactions, zero firmware execution.
"""

import unittest
import sys
from pathlib import Path

# Ground to local repository root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import tools.port9a_runtime_lifecycle as rt


def make_booted_lifecycle(boot_generation=1):
    """Test-only helper: initialize core and intercept under synthetic verification contracts."""
    m = rt.RuntimeLifecycle(
        preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
        static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
        hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        boot_generation=boot_generation,
    )
    m.init_core()
    m.install_intercept()
    return m


class TestPort12bFilesystemU2Obligations(unittest.TestCase):
    """Offline test suite for U2 filesystem readiness obligations."""

    def test_gm110c_preconditions_invariant(self):
        """Invariant: GM110C runtime precondition flag MUST remain False."""
        self.assertFalse(
            rt.GM110C_PRECONDITIONS.init_file_modules_entry_verified,
            "GM110C_PRECONDITIONS.init_file_modules_entry_verified must remain False in Phase 0."
        )

    def test_static_evidence_profile_separation(self):
        """Verify that static ROM entry is decoupled from dynamic mount readiness."""
        # Entry vector is statically verified in ROM slice S2A
        self.assertEqual(
            rt.GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry,
            rt.EvidenceStatus.STATIC_VERIFIED,
            "Entry vector 0xFC0BD071 must be STATIC_VERIFIED from slice S2A."
        )
        # Dynamic SD/FAT mount readiness remains strictly UNKNOWN
        self.assertEqual(
            rt.GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness,
            rt.EvidenceStatus.UNKNOWN,
            "Mount readiness semantics must remain UNKNOWN without dynamic storage proof."
        )

    def test_six_stage_promotion_contract_completeness(self):
        """Verify that all six promotion obligations are explicitly codified in the lifecycle model."""
        keys = [req[0] for req in rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS]
        expected_keys = [
            "task_created",
            "task_started",
            "init_returned_normally",
            "mount_observed",
            "fs_io_ready",
            "warm_restart_safe",
        ]
        self.assertEqual(keys, expected_keys, "Filesystem promotion must require all 6 explicit stages.")

    def test_constant_zero_return_cannot_grant_fs_io_readiness(self):
        """Adversarial test: Normal return (r0=0) of sub_fc0d9ccc/sub_fc0d9cf6 CANNOT advance to FS_IO_READY."""
        m = make_booted_lifecycle()

        # Stage 1: Task created
        decision = m.on_firmware_create_task("InitFileModules")
        self.assertEqual(decision.action, rt.Action.REPLACE)
        self.assertEqual(m.fs.stage, rt.FilesystemStage.TASK_CREATED)

        # Stage 2: Task started
        stage = m.init_file_modules_started(boot_generation=m.boot_generation)
        self.assertEqual(stage, rt.FilesystemStage.TASK_STARTED)

        # Stage 3: Subroutine returns normally with return_code=0
        stage = m.init_file_modules_returned(
            return_code=0,
            event_5006_posted=False,
            boot_generation=m.boot_generation,
            status="ok",
        )
        self.assertEqual(stage, rt.FilesystemStage.INIT_RETURNED_NORMALLY)

        # Assert: Constant r0=0 return does NOT open FS_IO_READY or WARM_RESTART_SAFE
        self.assertNotEqual(m.fs.stage, rt.FilesystemStage.FS_IO_READY)
        self.assertNotEqual(m.fs.stage, rt.FilesystemStage.WARM_RESTART_SAFE)
        self.assertFalse(m.fs.fs_io_ready)
        self.assertFalse(m.fs.warm_restart_safe)

    def test_event_5006_alone_does_not_open_fs_io_gate(self):
        """Adversarial test: Posting UI event 0x5006 does NOT independently open filesystem I/O readiness."""
        m = make_booted_lifecycle()
        m.on_firmware_create_task("InitFileModules")
        m.init_file_modules_started(boot_generation=m.boot_generation)

        # Return with event_5006_posted=True
        stage = m.init_file_modules_returned(
            return_code=0,
            event_5006_posted=True,
            boot_generation=m.boot_generation,
            status="ok",
        )
        self.assertEqual(stage, rt.FilesystemStage.INIT_RETURNED_NORMALLY)

        # Still cannot claim FS_IO_READY or WARM_RESTART_SAFE without explicit storage proof
        self.assertFalse(m.fs.fs_io_ready)
        self.assertFalse(m.fs.warm_restart_safe)

    def test_out_of_order_init_returned_fails_closed(self):
        """Adversarial test: Receiving init_returned before task_started must fail the filesystem."""
        m = make_booted_lifecycle()
        m.on_firmware_create_task("InitFileModules")

        # Task not started yet; directly invoke returned
        stage = m.init_file_modules_returned(return_code=0, boot_generation=m.boot_generation)
        self.assertEqual(stage, rt.FilesystemStage.FAILED)
        self.assertTrue(m.fs.failed)

    def test_generation_mismatch_fails_closed(self):
        """Adversarial test: An obsolete generation token across warm restart is rejected."""
        m = make_booted_lifecycle(boot_generation=2)
        m.on_firmware_create_task("InitFileModules")

        # Attempt to start with stale generation ID (1 != 2)
        stage = m.init_file_modules_started(boot_generation=1)
        # Must ignore stale generation and not advance
        self.assertNotEqual(stage, rt.FilesystemStage.TASK_STARTED)

    def test_fault_latched_blocks_subsequent_stages(self):
        """Adversarial test: When a CPU fault is latched, subsequent filesystem stages fail."""
        m = make_booted_lifecycle()
        m.on_firmware_create_task("InitFileModules")

        # Induce fault via report_failure
        m.report_failure("cpu", "Instruction prefetch abort")

        # Now attempt to start init task
        stage = m.init_file_modules_started(boot_generation=m.boot_generation)
        self.assertEqual(stage, rt.FilesystemStage.FAILED)
        self.assertTrue(m.fs.failed)


if __name__ == "__main__":
    unittest.main()
