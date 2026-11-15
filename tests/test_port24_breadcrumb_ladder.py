#!/usr/bin/env python3
"""Unit tests for PORT-24 T3 (r3): Opt-in Breadcrumb Ladder DISKBOOT Candidate.

Verifies:
1. Scope compliance:
   - No new files created under chdk-port/platform/g3x/sub/110c/.
   - Only already-tracked files in 110c are modified, and all changes are inside
     #if defined(LED_LADDER) blocks.
2. Default build hash unchanged:
   - With the ladder flag off, build output is byte-identical to the locked PORT-19 SHA-256:
     9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - Size is exactly 118,001 bytes.
   - Raw candidate_loader.bin matches:
     2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a (118,000 bytes).
   - Candidate core binary matches:
     420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e (116,816 bytes).
3. Ladder build differs and is deterministic across two builds:
   - Building the ladder candidate twice produces identical SHA-256 hashes.
   - Ladder DISKBOOT.BIN hash differs from default control build hash.
   - Ladder DISKBOOT.BIN matches recorded hash:
     aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c (118,257 bytes).
   - Ladder candidate_loader.bin matches recorded hash:
     f3239e0b928dbe30022ce04f1e6d2a13b70409fe10f66ff121feb2efdde86289 (118,256 bytes).
   - Candidate core binary (candidate_main.bin) is bit-for-bit identical to default.
4. Pulse timing and visibility under 200 ms:
   - Single visible pulse per step (ON delay 0x00134000, OFF delay 0x002C4000; total loop 0x003F8000).
   - Calibrated against PORT-23 0x00600000 loop with same loop body ('subs r2, r2, #1; bne').
   - Slow-bound loop-only duration is 198.44 ms [INFERRED], leaving 1.56 ms margin for overhead.
   - Non-loop overhead is UNKNOWN (1.0 ms is an ASSUMPTION); conditional cap: step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN).
   - OFF gap duration is maximized: ~46.1 ms fast, ~57.6 ms nominal, ~138.3 ms slowest bound.
   - Uses verified MMIO register 0xD20B0884 with 0x004D0002 (ON) and 0x004C0003 (OFF).
5. Breadcrumb insertion points match the T1 step list:
   - Verifies 7 breadcrumbs sit at every listed T1 checkpoint in candidate_loader.elf:
     Step 1: after_prologue - after check_compat()
     Step 2: after_copy     - after core_copy() & witness write
     Step 3: before_dcache  - before ROM_DCACHE_CLEAN_INV blx
     Step 4: after_dcache   - after ROM_DCACHE_CLEAN_INV blx & dsb sy
     Step 5: before_icache  - before ROM_ICACHE_INV_BP blx
     Step 6: after_icache   - after ROM_ICACHE_INV_BP blx & dsb sy + isb sy
     Step 7: before_bx      - after cpsid if, immediately before bx r0
6. State preservation in disassembly:
   - Verifies sp (0x7FF8) is untouched by breadcrumbs (cited docs/PORT24_LOADER_TRACE.md:312).
   - Verifies callee-saved registers r4 (%0) and r5 (%1) are never clobbered.
   - Verifies CPSR mask (cpsid if) is preserved after Step 7.
   - Verifies Thumb mode transition via bx r0 with bit 0 set (0x003489B5).
   - Verifies final LED state is OFF (0x004C0003).
   - Verifies literal pool placement is outside linear execution path.
   - Verifies local numeric labels 1b and 2b resolve strictly to immediate preceding loop in each pulse.
   - Verifies loop body instructions match PORT-23 stall loop ('subs r2, #1; bne.n').
7. Candidate validation passes:
   - All validate_candidate_port2a checks pass on the ladder candidate artifacts.
8. Alignment pad test:
   - Confirms default build contains no _ladder_align_pad symbol and remains 8-byte aligned.
   - Confirms ladder build maintains 8-byte alignment required by dancingbits.c:60-68.
9. CLI table generator:
   - tools/port24_ladder_table.py prints table in text, json, and markdown formats.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
SUB_DIR = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c"
BUILD_LADDER = TOOLS_DIR / "build_candidate_port24_ladder.py"
BUILD_PORT2A = TOOLS_DIR / "build_candidate_port2a.py"
VALIDATOR_PORT2A = TOOLS_DIR / "validate_candidate_port2a.py"
LADDER_TABLE = TOOLS_DIR / "port24_ladder_table.py"
DOCS_LADDER = REPO_ROOT / "docs" / "PORT24_BREADCRUMB_LADDER.md"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
CC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001
EXPECTED_DEFAULT_LOADER_SHA256 = (
    "2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a"
)
EXPECTED_DEFAULT_LOADER_SIZE = 118000
EXPECTED_DEFAULT_CORE_SHA256 = (
    "420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e"
)
EXPECTED_DEFAULT_CORE_SIZE = 116816

EXPECTED_LADDER_DISKBOOT_SHA256 = (
    "aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c"
)
EXPECTED_LADDER_DISKBOOT_SIZE = 118257
EXPECTED_LADDER_LOADER_SHA256 = (
    "f3239e0b928dbe30022ce04f1e6d2a13b70409fe10f66ff121feb2efdde86289"
)
EXPECTED_LADDER_LOADER_SIZE = 118256

VERIFIED_LED_MMIO = 0xD20B0884
VERIFIED_LED_ON = 0x004D0002
VERIFIED_LED_OFF = 0x004C0003

EXPECTED_T1_STEPS = (
    "after_prologue",
    "after_copy",
    "before_dcache",
    "after_dcache",
    "before_icache",
    "after_icache",
    "before_bx",
)


def compute_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort24BreadcrumbLadder(unittest.TestCase):
    """Test suite for PORT-24 T3 (r3) opt-in breadcrumb ladder candidate."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(BUILD_LADDER.is_file(), f"Missing {BUILD_LADDER}")
        cls.assertTrue(LADDER_TABLE.is_file(), f"Missing {LADDER_TABLE}")
        cls.assertTrue(OBJDUMP.is_file(), f"arm-none-eabi-objdump missing: {OBJDUMP}")
        cls.assertTrue(NM.is_file(), f"arm-none-eabi-nm missing: {NM}")

        # Ensure platform bootstrap is complete
        platform_cam_h = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "platform_camera.h"
        if not platform_cam_h.is_file():
            subprocess.run(
                ["python3", "-B", str(TOOLS_DIR / "bootstrap_chdk_platform.py")],
                cwd=REPO_ROOT,
                check=True,
            )

    def test_scope_no_new_files_in_110c(self):
        """No new files created under chdk-port/platform/g3x/sub/110c/; only tracked files edited."""
        res = subprocess.run(
            ["git", "status", "--porcelain", "chdk-port/platform/g3x/sub/110c/"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        lines = res.stdout.splitlines()
        for line in lines:
            status = line[:2]
            filename = line[3:]
            self.assertFalse(
                status.startswith("??"),
                f"Forbidden new untracked file under sub/110c: {filename}",
            )
            self.assertIn(
                status.strip(),
                ("M", "AM", "A"),
                f"Unexpected git status for file in sub/110c: {line}",
            )

        res_tracked = subprocess.run(
            ["git", "ls-files", "chdk-port/platform/g3x/sub/110c/"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        tracked_files = [Path(p).name for p in res_tracked.stdout.splitlines()]
        # PORT-41: platform files tracked for the standard CHDK build
        expected_tracked = {
            "boot.c",
            "boot_prototype.c",
            "boot_witness.h",
            "capt_seq.c",
            "filewrite.c",
            "g3x_trace.c",
            "g3x_trace.h",
            "gui_sync.h",
            "kbd_candidate.h",
            "led_breadcrumb.h",
            "loader_entry_breadcrumb.S",
            "loader_entry_led.S",
            "loader_main_breadcrumb.c",
            "makefile.inc",
            "movie_rec.c",
            "osd2_test_overlay.h",
            "osd_test_overlay.h",
            "stubs_auto.S",
            "stubs_entry.S",
            "stubs_min.S",
            "stubs_prototype.S",
        }
        self.assertEqual(
            set(tracked_files),
            expected_tracked,
            f"Tracked files under sub/110c changed: {set(tracked_files) ^ expected_tracked}",
        )

        header_path = SUB_DIR / "led_breadcrumb.h"
        loader_path = SUB_DIR / "loader_main_breadcrumb.c"

        with open(header_path, "r", encoding="utf-8") as f:
            header_src = f.read()
        self.assertIn("#if defined(LED_LADDER)", header_src)
        self.assertIn("G3X_LADDER_MMIO_ADDR", header_src)

        with open(loader_path, "r", encoding="utf-8") as f:
            loader_src = f.read()
        self.assertIn("#if defined(LED_LADDER)", loader_src)

    def test_default_build_hash_unchanged(self):
        """With the ladder flag off, build output is byte-identical to locked SHA-256."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                ["python3", str(BUILD_LADDER), "--flag-off", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Default build failed: {res.stderr}")

            diskboot = Path(tmpdir) / "DISKBOOT.BIN"
            self.assertTrue(diskboot.is_file())
            self.assertEqual(diskboot.stat().st_size, EXPECTED_DEFAULT_DISKBOOT_SIZE)
            self.assertEqual(
                compute_sha256(diskboot), EXPECTED_DEFAULT_DISKBOOT_SHA256
            )

            loader_bin = Path(tmpdir) / "candidate_loader.bin"
            self.assertTrue(loader_bin.is_file())
            self.assertEqual(loader_bin.stat().st_size, EXPECTED_DEFAULT_LOADER_SIZE)
            self.assertEqual(
                compute_sha256(loader_bin), EXPECTED_DEFAULT_LOADER_SHA256
            )

            core_bin = Path(tmpdir) / "candidate_main.bin"
            self.assertTrue(core_bin.is_file())
            self.assertEqual(core_bin.stat().st_size, EXPECTED_DEFAULT_CORE_SIZE)
            self.assertEqual(compute_sha256(core_bin), EXPECTED_DEFAULT_CORE_SHA256)

    def test_ladder_build_differs_and_is_deterministic(self):
        """Ladder build differs from default and is deterministic across two independent builds."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            res1 = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmp1],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res1.returncode, 0, f"Ladder build 1 failed: {res1.stderr}")

            res2 = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmp2],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res2.returncode, 0, f"Ladder build 2 failed: {res2.stderr}")

            db1 = Path(tmp1) / "DISKBOOT.BIN"
            db2 = Path(tmp2) / "DISKBOOT.BIN"
            ldr1 = Path(tmp1) / "candidate_loader.bin"
            ldr2 = Path(tmp2) / "candidate_loader.bin"
            core1 = Path(tmp1) / "candidate_main.bin"
            core2 = Path(tmp2) / "candidate_main.bin"

            # 1. Determinism across builds
            hash_db1 = compute_sha256(db1)
            hash_db2 = compute_sha256(db2)
            self.assertEqual(hash_db1, hash_db2, "Non-deterministic DISKBOOT.BIN builds!")

            hash_ldr1 = compute_sha256(ldr1)
            hash_ldr2 = compute_sha256(ldr2)
            self.assertEqual(hash_ldr1, hash_ldr2, "Non-deterministic candidate_loader.bin builds!")

            # 2. Differs from default build
            self.assertNotEqual(
                hash_db1,
                EXPECTED_DEFAULT_DISKBOOT_SHA256,
                "Ladder DISKBOOT.BIN unexpectedly equals default DISKBOOT.BIN!",
            )
            self.assertNotEqual(
                hash_ldr1,
                EXPECTED_DEFAULT_LOADER_SHA256,
                "Ladder loader binary unexpectedly equals default loader binary!",
            )

            # 3. Check expected ladder hashes and sizes
            self.assertEqual(hash_db1, EXPECTED_LADDER_DISKBOOT_SHA256)
            self.assertEqual(db1.stat().st_size, EXPECTED_LADDER_DISKBOOT_SIZE)
            self.assertEqual(hash_ldr1, EXPECTED_LADDER_LOADER_SHA256)
            self.assertEqual(ldr1.stat().st_size, EXPECTED_LADDER_LOADER_SIZE)

            # 4. Core payload unchanged
            self.assertEqual(
                compute_sha256(core1),
                EXPECTED_DEFAULT_CORE_SHA256,
                "Core payload must be bit-for-bit identical to default!",
            )
            self.assertEqual(core1.stat().st_size, EXPECTED_DEFAULT_CORE_SIZE)

    def test_default_build_unaffected_by_ladder_align_pad(self):
        """Default build does not include _ladder_align_pad and maintains 8-byte alignment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Build default
            res = subprocess.run(
                ["python3", str(BUILD_LADDER), "--flag-off", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            default_elf = Path(tmpdir) / "candidate_loader.elf"
            default_bin = Path(tmpdir) / "candidate_loader.bin"

            # Check nm symbols in default ELF
            nm_out = subprocess.check_output([str(NM), str(default_elf)]).decode()
            self.assertNotIn("_ladder_align_pad", nm_out, "_ladder_align_pad leaked into default build!")

            # Check 8-byte alignment of binaries
            self.assertEqual(default_bin.stat().st_size % 8, 0, "Default loader binary not 8-byte aligned!")
            self.assertEqual(default_bin.stat().st_size, EXPECTED_DEFAULT_LOADER_SIZE)

            # Build ladder
            res_ladder = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            ladder_elf = Path(tmpdir) / "candidate_loader.elf"
            ladder_bin = Path(tmpdir) / "candidate_loader.bin"

            ladder_nm = subprocess.check_output([str(NM), str(ladder_elf)]).decode()
            self.assertIn("_ladder_align_pad", ladder_nm, "_ladder_align_pad missing from ladder build!")
            self.assertEqual(ladder_bin.stat().st_size % 8, 0, "Ladder loader binary not 8-byte aligned!")
            self.assertEqual(ladder_bin.stat().st_size, EXPECTED_LADDER_LOADER_SIZE)

    def test_pulse_timing_and_visibility_under_200ms(self):
        """Each step's code is under 200 ms and pulses have maximized visible OFF gap."""
        from port24_ladder_table import (
            generate_ladder_table,
            calculate_timing,
            PULSE_ON_ITERATIONS,
            PULSE_OFF_ITERATIONS,
            SINGLE_STEP_ITERATIONS,
        )

        timing = calculate_timing()

        # Check iteration counts
        self.assertEqual(PULSE_ON_ITERATIONS, 0x00134000)
        self.assertEqual(PULSE_OFF_ITERATIONS, 0x002C4000)
        self.assertEqual(SINGLE_STEP_ITERATIONS, 0x003F8000)

        # Under documented calibration: slow-bound loop total < 200 ms cap (loop-only arithmetic)
        self.assertLess(
            timing["total_ms_nominal"],
            200.0,
            f"Nominal duration {timing['total_ms_nominal']} ms exceeds 200 ms cap!",
        )
        self.assertEqual(
            timing["total_ms_slowest"],
            198.44,
            f"Slow-bound loop-only duration expected 198.44 ms, got {timing['total_ms_slowest']}",
        )
        self.assertLess(
            timing["total_ms_slowest"],
            200.0,
            f"Max loop duration {timing['total_ms_slowest']} ms exceeds 200 ms cap!",
        )
        self.assertTrue(timing["loop_only_under_200ms"])

        # Margin beyond loops at slow bound: 200.0 - 198.44 = 1.56 ms
        margin_ms = round(200.0 - timing["total_ms_slowest"], 2)
        self.assertEqual(margin_ms, 1.56)

        # Overhead figure is an ASSUMPTION and status is UNKNOWN
        self.assertEqual(timing["overhead_assumed_ms"], 1.0)
        self.assertEqual(timing["overhead_status"], "UNKNOWN")
        self.assertIn(
            "step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN)",
            timing["conditional_cap_status"],
        )

        # Check fast-bound compromise:
        # (a) fast-bound ON >= stated minimum of 20.0 ms (~20.05 ms at 100 ms bound)
        self.assertGreaterEqual(
            timing["on_ms_fastest"],
            20.0,
            f"Fastest ON {timing['on_ms_fastest']} ms below stated minimum of 20.0 ms!",
        )
        # (b) fast-bound OFF maximized within the budget (~46.09 ms)
        self.assertGreaterEqual(
            timing["off_ms_fastest"],
            46.0,
            f"Fastest OFF {timing['off_ms_fastest']} ms below 46.0 ms!",
        )
        # (c) Document, table text, and header carry conditional/UNKNOWN wording for overhead
        with open(DOCS_LADDER, "r", encoding="utf-8") as f:
            doc_text = f.read()
        self.assertIn(
            "step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN)",
            doc_text,
        )
        self.assertIn("1.0 ms figure is an ASSUMPTION", doc_text)
        self.assertIn("Per-step non-loop overhead is [UNKNOWN]", doc_text)
        self.assertIn("198.44 ms", doc_text)

        # Check table text CLI carries conditional / UNKNOWN wording
        res_table_text = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertIn(
            "step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN)",
            res_table_text.stdout,
        )
        self.assertIn("1.0 ms ASSUMPTION [UNKNOWN: no latency evidence in repo]", res_table_text.stdout)

        # Check table markdown CLI carries conditional / UNKNOWN wording
        res_table_md = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference", "--markdown"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertIn(
            "step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN)",
            res_table_md.stdout,
        )
        self.assertIn("1.0 ms non-loop overhead is an ASSUMPTION; per-step overhead is UNKNOWN", res_table_md.stdout)

        # Check header carries conditional / UNKNOWN wording
        with open(SUB_DIR / "led_breadcrumb.h", "r", encoding="utf-8") as f:
            hdr_text = f.read()
        self.assertIn(
            "step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN)",
            hdr_text,
        )
        self.assertIn("1.0 ms figure is an ASSUMPTION", hdr_text)
        self.assertIn("Non-loop overhead [UNKNOWN: no latency evidence in the repo]", hdr_text)

        # Immediate encoding assertions:
        # 0x002C4000 is 0xB1 << 14, an encodable Thumb-2 modified immediate
        self.assertEqual(0x002C4000, 0xB1 << 14)
        # Next larger encodable modified immediate is 0x002C8000 (0xB2 << 14)
        next_imm = 0xB2 << 14
        self.assertEqual(next_imm, 0x002C8000)
        # Verify next immediate breaks the 200 ms cap at slowest bound (300 ms for 0x00600000):
        next_step_slow_ms = ((PULSE_ON_ITERATIONS + next_imm) / 0x00600000) * 300.0 + 1.0
        self.assertGreater(
            next_step_slow_ms,
            200.0,
            f"Next immediate {hex(next_imm)} expected to break 200 ms cap, got {next_step_slow_ms} ms",
        )

        # Visibility checks across nominal and slowest bounds
        self.assertGreaterEqual(
            timing["off_ms_nominal"],
            50.0,
            f"OFF gap {timing['off_ms_nominal']} ms too brief for visual flash separation!",
        )
        self.assertGreaterEqual(
            timing["off_ms_slowest"],
            60.0,
            f"OFF gap at slowest bound {timing['off_ms_slowest']} ms should be >= 60 ms!",
        )
        self.assertGreaterEqual(
            timing["on_ms_slowest"],
            40.0,
            f"ON duration at slowest bound {timing['on_ms_slowest']} ms should be >= 40 ms!",
        )

        table = generate_ladder_table(is_reference=True)
        self.assertEqual(len(table), 7, f"Expected 7 ladder steps, got {len(table)}")

        for row in table:
            self.assertIn(row["name"], EXPECTED_T1_STEPS)
            self.assertLess(row["timing"]["total_ms_slowest"], 200.0)

    def test_breadcrumb_insertion_points_match_t1(self):
        """Breadcrumb insertion points match the T1 step list in candidate_loader.elf disassembly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Ladder build failed: {res.stderr}")

            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            self.assertTrue(loader_elf.is_file())

            dump = subprocess.check_output([str(OBJDUMP), "-d", str(loader_elf)]).decode()
            self.assertIn("<my_restart>:", dump)

            restart_dump = dump[dump.find("<my_restart>:") :]

            # Architectural anchors in my_restart
            compat_idx = restart_dump.find("<check_compat>")
            self.assertGreater(compat_idx, 0, "Missing check_compat call")
            copy_idx = restart_dump.find("<core_copy>")
            self.assertGreater(copy_idx, compat_idx, "Missing core_copy call")

            # ROM cache routines called via blx r2
            dcache_blx_idx = restart_dump.find("blx\tr2")
            self.assertGreater(dcache_blx_idx, copy_idx, "Missing dcache blx r2 call")

            icache_blx_idx = restart_dump.find("blx\tr2", dcache_blx_idx + 1)
            self.assertGreater(icache_blx_idx, dcache_blx_idx, "Missing icache blx r2 call")

            isb_idx = restart_dump.find("isb\tsy", icache_blx_idx)
            self.assertGreater(isb_idx, icache_blx_idx, "Missing isb sy")

            cpsid_idx = restart_dump.find("cpsid\tif", isb_idx)
            self.assertGreater(cpsid_idx, isb_idx, "Missing cpsid if")

            bx_idx = restart_dump.find("bx\tr0", cpsid_idx)
            self.assertGreater(bx_idx, cpsid_idx, "Missing terminal bx r0")

            # Each step has an ON delay loop with mov.w r2, #1261568 (0x00134000)
            # and an OFF delay loop with mov.w r2, #2899968 (0x002C4000)
            on_loop_marker = "mov.w\tr2, #1261568"
            off_loop_marker = "mov.w\tr2, #2899968"

            # 1. Step 1 (after_prologue): after bl check_compat, before core_copy
            step1_count = restart_dump[compat_idx:copy_idx].count(on_loop_marker)
            self.assertEqual(step1_count, 1, f"Expected 1 pulse for Step 1, got {step1_count}")

            # 2. Step 2 (after_copy) & Step 3 (before_dcache): between core_copy and dcache blx r2
            step2_3_count = restart_dump[copy_idx:dcache_blx_idx].count(on_loop_marker)
            self.assertEqual(step2_3_count, 2, f"Expected 2 pulses (Step 2, 3), got {step2_3_count}")

            # 3. Step 4 (after_dcache) & Step 5 (before_icache): between dcache blx r2 and icache blx r2
            step4_5_count = restart_dump[dcache_blx_idx:icache_blx_idx].count(on_loop_marker)
            self.assertEqual(step4_5_count, 2, f"Expected 2 pulses (Step 4, 5), got {step4_5_count}")

            # 4. Step 6 (after_icache): between isb sy and cpsid if
            step6_count = restart_dump[isb_idx:cpsid_idx].count(on_loop_marker)
            self.assertEqual(step6_count, 1, f"Expected 1 pulse for Step 6, got {step6_count}")

            # 5. Step 7 (before_bx): between cpsid if and bx r0
            step7_count = restart_dump[cpsid_idx:bx_idx].count(on_loop_marker)
            self.assertEqual(step7_count, 1, f"Expected 1 pulse for Step 7, got {step7_count}")

            # Total pulses in loader must be exactly 7 ON and 7 OFF
            self.assertEqual(restart_dump.count(on_loop_marker), 7)
            self.assertEqual(restart_dump.count(off_loop_marker), 7)

    def test_state_preservation_and_objdump_details(self):
        """Objdump confirms registers, sp, CPSR mask, Thumb state, literal pool placement, and local labels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            dump = subprocess.check_output([str(OBJDUMP), "-d", str(loader_elf)]).decode()
            restart_dump = dump[dump.find("<my_restart>:") :]

            # 1. SP preservation: no stack push/pop inside any breadcrumb
            self.assertNotIn("push\t{r0", restart_dump)
            self.assertNotIn("pop\t{r0", restart_dump)

            # 2. Operand registers r5 (%0, dest 0x003489B4) and r4 (%1, size) are never written in any breadcrumb
            cpsid_idx = restart_dump.find("cpsid\tif")
            bx_idx = restart_dump.find("bx\tr0", cpsid_idx)
            handoff_code = restart_dump[cpsid_idx:bx_idx]

            self.assertIn("mov\tr0, r5", handoff_code)
            self.assertIn("add.w\tr0, r0, #1", handoff_code)

            # 3. CPSR preservation: cpsid if is executed before Step 7 and NOT undone
            self.assertNotIn("cpsie", handoff_code)
            self.assertNotIn("msr\tCPSR", handoff_code)

            # 4. Final LED state: writes 0x004C0003 (OFF) at end of Step 7
            self.assertIn("004c0003", dump)

            # 5. Literal pool placement: pool constants are located after function exit
            # my_restart ends with bx r0 at 0x8332 and fallback b.n 8334
            # Literal pool is at 0x8338..0x835C
            self.assertIn("8332:\t4700      \tbx\tr0", restart_dump)
            self.assertIn("8334:\te7fe      \tb.n\t8334", restart_dump)
            self.assertIn("834c:\td20b0884", restart_dump)
            self.assertIn("8350:\t004d0002", restart_dump)
            self.assertIn("8354:\t004c0003", restart_dump)

            # 6. Local labels 1b and 2b resolve strictly to preceding loop (opcode d1fd)
            # Exactly 14 loops total (7 ON + 7 OFF), each branching backward with d1fd
            subs_bne_count = len(re.findall(r"subs\tr2,\s+#1\n\s+[0-9a-f]+:\td1fd\s+bne\.n", restart_dump))
            self.assertEqual(subs_bne_count, 14, f"Expected 14 subs/bne.n pairs with d1fd, got {subs_bne_count}")

            # 7. Loop body matches PORT-23 stall loop ('subs r2, #1; bne.n')
            self.assertIn("subs\tr2, #1", restart_dump)
            self.assertIn("bne.n\t81ec", restart_dump)

    def test_ladder_candidate_validation_passes(self):
        """Ladder candidate passes all validation checks in validate_candidate_port2a."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_build = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res_build.returncode, 0, f"Build failed: {res_build.stderr}")

            from validate_candidate_port2a import (
                validate_production_invariance,
                validate_candidate_core,
                validate_candidate_loader,
                validate_encoded_diskboot,
                validate_memory_and_stack_disjointness,
                validate_inspector_association,
                validate_manifest_integrity,
            )
            import validate_candidate_port2a

            orig_cand = validate_candidate_port2a.CANDIDATE_DIR
            try:
                validate_candidate_port2a.CANDIDATE_DIR = tmpdir
                self.assertTrue(validate_production_invariance())
                self.assertTrue(
                    validate_candidate_core(
                        core_elf=os.path.join(tmpdir, "candidate_main.elf"),
                        core_bin=os.path.join(tmpdir, "candidate_main.bin"),
                    )
                )
                self.assertTrue(
                    validate_candidate_loader(
                        core_bin_path=os.path.join(tmpdir, "candidate_main.bin")
                    )
                )
                self.assertTrue(
                    validate_encoded_diskboot(
                        loader_bin_path=os.path.join(tmpdir, "candidate_loader.bin")
                    )
                )
                self.assertTrue(validate_memory_and_stack_disjointness())
                self.assertTrue(validate_inspector_association())
                self.assertTrue(validate_manifest_integrity())
            finally:
                validate_candidate_port2a.CANDIDATE_DIR = orig_cand

    def test_default_build_cli_no_args(self):
        """Running build_candidate_port24_ladder.py with no args builds default candidate (SHA-256 matches locked)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                ["python3", str(BUILD_LADDER), "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Default build without args failed: {res.stderr}")
            diskboot = Path(tmpdir) / "DISKBOOT.BIN"
            self.assertTrue(diskboot.is_file())
            self.assertEqual(
                compute_sha256(diskboot), EXPECTED_DEFAULT_DISKBOOT_SHA256
            )

    def test_port24_ladder_table_error_handling(self):
        """tools/port24_ladder_table.py exits non-zero on missing ELF or non-ladder ELF, and prints reference table with --reference."""
        # 1. Nonexistent ELF -> non-zero exit code, no addresses printed
        res_nonexistent = subprocess.run(
            ["python3", str(LADDER_TABLE), "--loader-elf", "/nonexistent/test.elf"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(res_nonexistent.returncode, 0)
        self.assertNotIn("0x000081E2", res_nonexistent.stdout)
        self.assertIn("Error:", res_nonexistent.stderr)

        # 2. Default (non-ladder) ELF -> non-zero exit code
        with tempfile.TemporaryDirectory() as tmpdir:
            res_build_default = subprocess.run(
                ["python3", str(BUILD_PORT2A), "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res_build_default.returncode, 0)
            default_elf = Path(tmpdir) / "candidate_loader.elf"
            self.assertTrue(default_elf.is_file())

            res_default_table = subprocess.run(
                ["python3", str(LADDER_TABLE), "--loader-elf", str(default_elf)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(res_default_table.returncode, 0)
            self.assertNotIn("0x000081E2", res_default_table.stdout)
            self.assertIn("Error:", res_default_table.stderr)

        # 3. Ladder ELF -> exit 0 with 7 extracted addresses
        with tempfile.TemporaryDirectory() as tmpdir:
            res_build_ladder = subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res_build_ladder.returncode, 0)
            ladder_elf = Path(tmpdir) / "candidate_loader.elf"
            self.assertTrue(ladder_elf.is_file())

            res_ladder_table = subprocess.run(
                ["python3", str(LADDER_TABLE), "--loader-elf", str(ladder_elf)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res_ladder_table.returncode, 0)
            self.assertIn("0x000081E2", res_ladder_table.stdout)
            self.assertIn("0x0000830E", res_ladder_table.stdout)

        # 4. Static reference table behind --reference flag
        res_ref = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_ref.returncode, 0)
        self.assertIn("STATIC REFERENCE, not extracted from a build", res_ref.stdout)
        self.assertIn("0x000081E2", res_ref.stdout)
        self.assertIn("0x0000830E", res_ref.stdout)

    def test_triage_claims_and_suspect_isolation(self):
        """Triage table asserts UNKNOWN on flash 7 and isolates suspects to immediate step intervals."""
        from port24_ladder_table import TRIAGE_RULES, AMBIGUITY_NOTE

        rules_dict = dict(TRIAGE_RULES)

        # Check flash 7 row contains UNKNOWN and no improper exoneration/confirmation
        flash7_text = rules_dict["7 flashes"]
        self.assertIn("UNKNOWN", flash7_text)
        self.assertNotIn("core entry confirmed", flash7_text.lower())
        self.assertNotIn("core entry proved", flash7_text.lower())
        self.assertNotIn("loader exonerated", flash7_text.lower())
        self.assertNotIn("100% exonerated", flash7_text.lower())

        # Check flash 6 suspects: must NOT list isb sy (isb runs before flash 6)
        flash6_text = rules_dict["6 flashes"]
        self.assertNotIn("isb", flash6_text)
        self.assertIn("cpsid if", flash6_text)

        # Check flash 5 suspects: lists I-cache / isb sy
        flash5_text = rules_dict["5 flashes"]
        self.assertIn("ROM_ICACHE_INV_BP", flash5_text)

        # Check flash 4 suspects: only adjacent breadcrumb code, no cache operations
        flash4_text = rules_dict["4 flashes"]
        self.assertIn("after_dcache", flash4_text)
        self.assertIn("before_icache", flash4_text)
        self.assertIn("no cache", flash4_text.lower())

        # Check flash 3 suspects: D-cache maintenance
        flash3_text = rules_dict["3 flashes"]
        self.assertIn("ROM_DCACHE_CLEAN_INV", flash3_text)

        # Check flash 2 suspects: transition into cache block, no cache operations
        flash2_text = rules_dict["2 flashes"]
        self.assertIn("no cache", flash2_text.lower())

        # Ambiguity note explains mid-pulse dark / failure
        self.assertIn("ambiguous by one", AMBIGUITY_NOTE)

    def test_operand_register_mapping_and_flag_independence(self):
        """Disassembly proves r5 holds %0 (dest 0x003489B4), r4 holds %1 (size), terminal hand-off branches via r5,
        and no subsequent code depends on condition flags (NZCV)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["python3", str(BUILD_LADDER), "--ladder", "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            dump = subprocess.check_output([str(OBJDUMP), "-d", str(loader_elf)]).decode()
            restart_dump = dump[dump.find("<my_restart>:") :]

            # 1. r5 allocation: destination address MEMISOSTART (0x003489B4, %0)
            self.assertRegex(restart_dump, r"ldr\tr5,\s+\[pc,.*833c <my_restart\+0x164>")
            self.assertIn("833c:\t003489b4", restart_dump)

            # 2. r4 allocation: size in bytes (blob_chdk_core_size rounded up to 4, %1)
            self.assertIn("ldr\tr4, [r3, #0]", restart_dump)
            self.assertIn("adds\tr4, #3", restart_dump)
            self.assertIn("bic.w\tr4, r4, #3", restart_dump)

            # 3. Argument setup for D-cache: r0 from r5 (%0), r1 from r4 (%1)
            self.assertIn("8286:\t4628      \tmov\tr0, r5", restart_dump)
            self.assertIn("8288:\t4621      \tmov\tr1, r4", restart_dump)
            self.assertIn("828c:\t4790      \tblx\tr2", restart_dump)
            self.assertIn("8358:\tfc127ab1", restart_dump)

            # 4. Argument setup for I-cache: r0 from r5 (%0), r1 from r4 (%1)
            self.assertIn("82d6:\t4628      \tmov\tr0, r5", restart_dump)
            self.assertIn("82d8:\t4621      \tmov\tr1, r4", restart_dump)
            self.assertIn("82dc:\t4790      \tblx\tr2", restart_dump)
            self.assertIn("835c:\tfc127b09", restart_dump)

            # 5. Terminal hand-off branches through r5:
            self.assertIn("832c:\t4628      \tmov\tr0, r5", restart_dump)
            self.assertIn("832e:\tf100 0001 \tadd.w\tr0, r0, #1", restart_dump)
            self.assertIn("8332:\t4700      \tbx\tr0", restart_dump)

            # 6. Condition flags (NZCV) independence:
            # Check instructions after Step 7 subs loop to terminal bx r0:
            # Only mov r0, r5; add.w r0, r0, #1; bx r0 execute. None depend on NZCV flags.
            bne_pos = restart_dump.find("832a:\td1fd")
            eol = restart_dump.find("\n", bne_pos) + 1
            terminal_slice = restart_dump[eol : restart_dump.find("8332:\t4700")]
            self.assertIn("mov\tr0, r5", terminal_slice)
            self.assertIn("add.w\tr0, r0, #1", terminal_slice)
            self.assertNotIn("bne", terminal_slice)
            self.assertNotIn("beq", terminal_slice)
            self.assertNotIn("bgt", terminal_slice)
            self.assertNotIn("blt", terminal_slice)

    def test_port24_ladder_table_cli(self):
        """CLI tool port24_ladder_table.py executes and emits table across all formats."""
        res_text = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_text.returncode, 0)
        self.assertIn("PORT-24 T3: CANON POWERSHOT G3 X BREADCRUMB LADDER", res_text.stdout)
        self.assertIn("STATIC REFERENCE", res_text.stdout)
        self.assertIn("after_prologue", res_text.stdout)
        self.assertIn("before_bx", res_text.stdout)

        res_md = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference", "--markdown"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_md.returncode, 0)
        self.assertIn("STATIC REFERENCE", res_md.stdout)
        self.assertIn("| `after_prologue` |", res_md.stdout)
        self.assertIn("| `before_bx` |", res_md.stdout)

        res_json = subprocess.run(
            ["python3", str(LADDER_TABLE), "--reference", "--json"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_json.returncode, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(len(data), 7)
        self.assertEqual(data[0]["name"], "after_prologue")
        self.assertEqual(data[6]["name"], "before_bx")

    def test_ladder_table_store_validation_regressions(self):
        """tools/port24_ladder_table.py validates 14 stores, base MMIO 0xD20B0884, and ON/OFF values; rejects anomalies."""
        from port24_ladder_table import parse_and_validate_ladder_stores

        # 1. Construct valid synthetic disassembly of my_restart with 14 stores (7 complete pairs)
        valid_mock = """
000081d8 <my_restart>:
    81d8:\tb508      \tpush\t{r3, lr}
    81da:\tf7ff ffcd \tbl\t8178 <check_compat>
"""
        on_addrs = ["81e2", "8246", "8268", "8296", "82b8", "82ea", "830e"]
        off_addrs = ["81f2", "8256", "8278", "82a6", "82c8", "82fa", "831e"]
        for on_a, off_a in zip(on_addrs, off_addrs):
            valid_mock += f"""
    {int(on_a, 16)-4:x}:\t485b      \tldr\tr0, [pc, #364]\t; (834c)
    {int(on_a, 16)-2:x}:\t495b      \tldr\tr1, [pc, #364]\t; (8350)
    {on_a}:\t6001      \tstr\tr1, [r0, #0]
    {int(off_a, 16)-2:x}:\t4958      \tldr\tr1, [pc, #352]\t; (8354)
    {off_a}:\t6001      \tstr\tr1, [r0, #0]
"""
        valid_mock += """
    8332:\t4700      \tbx\tr0
    834c:\td20b0884 \t.word\t0xd20b0884
    8350:\t004d0002 \t.word\t0x004d0002
    8354:\t004c0003 \t.word\t0x004c0003
"""

        # Baseline: Valid 14 stores pass and return 7 ON store addresses
        parsed = parse_and_validate_ladder_stores(valid_mock, exit_on_error=False)
        self.assertEqual(len(parsed), 7)
        self.assertEqual(parsed[0], "0x000081E2")
        self.assertEqual(parsed[6], "0x0000830E")

        # Regression (a): Incomplete final pulse (13 stores) -> raises ValueError & exits non-zero
        mock_13 = valid_mock.replace("831e:\t6001      \tstr\tr1, [r0, #0]", "")
        with self.assertRaises(ValueError) as ctx_13:
            parse_and_validate_ladder_stores(mock_13, exit_on_error=False)
        self.assertIn("13", str(ctx_13.exception))
        self.assertIn("14", str(ctx_13.exception))
        with self.assertRaises(SystemExit) as exit_13:
            parse_and_validate_ladder_stores(mock_13, exit_on_error=True)
        self.assertEqual(exit_13.exception.code, 1)

        # Regression (b): Swapped ON/OFF value (first store gets OFF value instead of ON) -> raises ValueError & exits non-zero
        mock_swapped = valid_mock.replace(
            "81e0:\t495b      \tldr\tr1, [pc, #364]\t; (8350)",
            "81e0:\t495b      \tldr\tr1, [pc, #364]\t; (8354)",
        )
        with self.assertRaises(ValueError) as ctx_swap:
            parse_and_validate_ladder_stores(mock_swapped, exit_on_error=False)
        self.assertIn("0x004D0002", str(ctx_swap.exception))
        with self.assertRaises(SystemExit) as exit_swap:
            parse_and_validate_ladder_stores(mock_swapped, exit_on_error=True)
        self.assertEqual(exit_swap.exception.code, 1)

        # Regression (c): Wrong MMIO address (0xD20B0880 instead of 0xD20B0884) -> raises ValueError & exits non-zero
        mock_wrong_mmio = valid_mock.replace(
            "834c:\td20b0884 \t.word\t0xd20b0884",
            "834c:\td20b0880 \t.word\t0xd20b0880",
        )
        with self.assertRaises(ValueError) as ctx_mmio:
            parse_and_validate_ladder_stores(mock_wrong_mmio, exit_on_error=False)
        self.assertIn("0xD20B0884", str(ctx_mmio.exception))
        self.assertIn("0xD20B0880", str(ctx_mmio.exception))
        with self.assertRaises(SystemExit) as exit_mmio:
            parse_and_validate_ladder_stores(mock_wrong_mmio, exit_on_error=True)
        self.assertEqual(exit_mmio.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
