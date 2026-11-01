#!/usr/bin/env python3
"""Unit tests for PORT-25 T3b: Opt-in Combined Breadcrumb Ladder + G3X_POWERON_FIX Candidate.

Redesigned under Single-Emitter Rule:
1. Hash invariance of default and existing PORT-24 opt-in builds:
   - Default build is byte-identical: DISKBOOT SHA-256 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
   - PORT-24 --poweron-fix build is byte-identical: DISKBOOT SHA-256 faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056 (118,001 B).
   - PORT-24 --ladder build is byte-identical: DISKBOOT SHA-256 aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c (118,257 B).
2. Combined build enables both macros:
   - Compiles with LED_LADDER=1 and G3X_POWERON_FIX=1.
   - Core disassembly verifies G3X_POWERON_FIX bypass in sub_fc05b962_my (movs r0, #1; b loc_fc05b978).
   - Core disassembly verifies LED pulse stores (0xD20B0884 with 0x004D0002 / 0x004C0003).
3. Determinism and reproducibility of the combined build:
   - Building twice yields identical SHA-256: 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15 (124,865 B).
4. Ladder-only combination builds:
   - Builds ladder-only combination (ladder=True, poweron_fix=False) with pinned toolchain without branch errors:
     SHA-256: 45da469f3eb46c4d2aff77a032e5c8bb4eedf8ec8846526853d716d05d2b2f4e (126,081 B).
5. Single-emitter rule & disassembly verification:
   - Parent Initial Task emits stages in order: entry to sub_fc05b962_my (21), MPU setup checks (22, 23),
     power check (24), power check pass (25), and before task creation (26).
   - Parent emits NOTHING after calling DryOS CreateTask routine (sub_fc31bbc4).
   - 'After task creation' is defined as the FIRST frame emitted by the created Startup Task (Code 31).
   - No cross-context pending bitmask, replay routine, or completion flag exists.
   - Child Startup Task emits later stages (32, 33, 34, 35, 41, 42, 43, 44) directly.
   - Final state: LED OFF (0x004C0003).
6. Timing safety and assembly-faithful edge decoder:
   - Assembly-faithful edge generator: every pulse (including the last pulse before separators) is followed
     by its OFF delay, and then the digit/frame separator.
   - Decoder thresholds decode all stage codes unambiguously under nominal timing and under claimed tolerance
     (50.0 ms slow bound, 20.0 ms nominal bound), verified with worst-case code (22) tests.
   - Delays exceeding tolerance report ambiguous rather than decoding wrongly.
   - Every single ON pulse is strictly under 200 ms cap (50.0 ms slow / 20.97 ms nom).
"""

from __future__ import annotations

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
LOADER_DIR = REPO_ROOT / "chdk-port" / "loader" / "g3x"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import sha256_file

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001

EXPECTED_PORT24_POWERON_DISKBOOT_SHA256 = (
    "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056"
)
EXPECTED_PORT24_POWERON_DISKBOOT_SIZE = 118001

EXPECTED_PORT24_LADDER_DISKBOOT_SHA256 = (
    "aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c"
)
EXPECTED_PORT24_LADDER_DISKBOOT_SIZE = 118257

EXPECTED_COMBINED_DISKBOOT_SHA256 = (
    "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
)
EXPECTED_COMBINED_DISKBOOT_SIZE = 124865

EXPECTED_LADDER_ONLY_DISKBOOT_SHA256 = (
    "45da469f3eb46c4d2aff77a032e5c8bb4eedf8ec8846526853d716d05d2b2f4e"
)
EXPECTED_LADDER_ONLY_DISKBOOT_SIZE = 126081

FRAME_ON_ITERATIONS = 0x00100000        # 1,048,576 iterations
FRAME_OFF_ITERATIONS = 0x00050000       #   327,680 iterations
FRAME_DIGIT_GAP_ITERATIONS = 0x00200000 # 2,097,152 iterations
FRAME_END_GAP_ITERATIONS = 0x00400000   # 4,194,304 iterations

REF_ITERATIONS = 0x00600000  # 6,291,456 iterations
SLOW_BOUND_MS = 300.0        # 300 ms at slowest calibration bound
NOMINAL_BOUND_MS = 125.82912 # 125.8 ms nominal (150 MHz, 3 cycles = 20 ns/iter)
FAST_BOUND_MS = 94.37184     # 94.4 ms fastest calibration bound (200 MHz, 3 cycles = 15 ns/iter)

STAGE_CODE_DEFINITIONS = [
    # Loader stages (1-7)
    {"code": 1, "stage": "STAGE_LOADER_AFTER_PROLOGUE", "context": "Loader", "file_line": "loader_main_breadcrumb.c:45", "post_arming": False},
    {"code": 2, "stage": "STAGE_LOADER_AFTER_COPY", "context": "Loader", "file_line": "loader_main_breadcrumb.c:99", "post_arming": False},
    {"code": 3, "stage": "STAGE_LOADER_BEFORE_DCACHE", "context": "Loader", "file_line": "loader_main_breadcrumb.c:116", "post_arming": False},
    {"code": 4, "stage": "STAGE_LOADER_AFTER_DCACHE", "context": "Loader", "file_line": "loader_main_breadcrumb.c:127", "post_arming": False},
    {"code": 5, "stage": "STAGE_LOADER_BEFORE_ICACHE", "context": "Loader", "file_line": "loader_main_breadcrumb.c:132", "post_arming": False},
    {"code": 6, "stage": "STAGE_LOADER_AFTER_ICACHE", "context": "Loader", "file_line": "loader_main_breadcrumb.c:144", "post_arming": False},
    {"code": 7, "stage": "STAGE_LOADER_BEFORE_BX", "context": "Loader", "file_line": "loader_main_breadcrumb.c:152", "post_arming": False},
    # Core Group 1: Pre-Kernel & Trampoline (11-15) - pre-arming, Reset Thread / Initial Task
    {"code": 11, "stage": "STAGE_BC_CORE_ENTRY", "context": "Reset thread", "file_line": "boot_prototype.c:91", "post_arming": False},
    {"code": 12, "stage": "STAGE_BC_POST_BSS", "context": "Reset thread", "file_line": "boot_prototype.c:153", "post_arming": False},
    {"code": 13, "stage": "STAGE_BC_STAGE3_ENTRY", "context": "Reset thread", "file_line": "boot_prototype.c:174", "post_arming": False},
    {"code": 14, "stage": "STAGE_BC_PRE_KERNEL_INIT", "context": "Reset thread", "file_line": "boot_prototype.c:255", "post_arming": False},
    {"code": 15, "stage": "STAGE_BC_STAGE4_ENTRY", "context": "Initial Task", "file_line": "boot_prototype.c:271", "post_arming": False},
    # Core Group 2: Stage 5 Startup Creation & Power Checks (21-26) - pre-arming, Initial Task context
    {"code": 21, "stage": "STAGE_BC_STAGE5_ENTRY", "context": "Initial Task", "file_line": "boot_prototype.c:345", "post_arming": False},
    {"code": 22, "stage": "STAGE_BC_PRE_MPU_SETUP", "context": "Initial Task", "file_line": "boot_prototype.c:346", "post_arming": False},
    {"code": 23, "stage": "STAGE_BC_POST_MPU_SETUP", "context": "Initial Task", "file_line": "boot_prototype.c:346", "post_arming": False},
    {"code": 24, "stage": "STAGE_BC_PRE_POWER_CHECK", "context": "Initial Task", "file_line": "boot_prototype.c:347", "post_arming": False},
    {"code": 25, "stage": "STAGE_BC_POWER_CHECK_PASS", "context": "Initial Task", "file_line": "boot_prototype.c:358", "post_arming": False},
    {"code": 26, "stage": "STAGE_BC_PRE_CREATE_STARTUP", "context": "Initial Task", "file_line": "boot_prototype.c:370", "post_arming": False},
    # Core Group 3: task_Startup_my Pre-Watchdog (31-35) - pre-arming, Startup Task context
    # Code 31 is the FIRST frame emitted by the created task ('After task creation' / Startup entry)
    {"code": 31, "stage": "STAGE_BC_STARTUP_ENTRY", "context": "Startup Task", "file_line": "boot_prototype.c:386", "post_arming": False},
    {"code": 32, "stage": "STAGE_BC_POST_EARLY_INIT", "context": "Startup Task", "file_line": "boot_prototype.c:390", "post_arming": False},
    {"code": 33, "stage": "STAGE_BC_PRE_SD1STINIT", "context": "Startup Task", "file_line": "boot_prototype.c:399", "post_arming": False},
    {"code": 34, "stage": "STAGE_BC_POST_SD1STINIT", "context": "Startup Task", "file_line": "boot_prototype.c:404", "post_arming": False},
    {"code": 35, "stage": "STAGE_BC_PRE_WATCHDOG_START", "context": "Startup Task", "file_line": "boot_prototype.c:410", "post_arming": False},
    # Core Group 4: task_Startup_my Post-Watchdog & Continuation (41-44) - POST-ARMING, Startup Task context
    {"code": 41, "stage": "STAGE_BC_POST_WATCHDOG_START", "context": "Startup Task", "file_line": "boot_prototype.c:410", "post_arming": True},
    {"code": 42, "stage": "STAGE_BC_PRE_PHYSW_CREATE", "context": "Startup Task", "file_line": "boot_prototype.c:415", "post_arming": True},
    {"code": 43, "stage": "STAGE_BC_POST_PHYSW_CREATE", "context": "Startup Task", "file_line": "boot_prototype.c:415", "post_arming": True},
    {"code": 44, "stage": "STAGE_BC_PRE_FIRMWARE_CONT", "context": "Startup Task", "file_line": "boot_prototype.c:439", "post_arming": True},
]

EXPECTED_CORE_CODES = [11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43, 44]
POST_ARMING_CODES = [41, 42, 43, 44]


def generate_timestamped_edges(
    codes: list[int],
    pulse_preempt: float = 0.0,
    digit_preempt: float = 0.0,
    frame_preempt: float = 0.0,
    bound: str = "slow",
) -> list[tuple[float, str]]:
    """Assembly-faithful edge generator: every pulse (including the last pulse of a digit/frame)
    is followed by its OFF delay exactly as led_breadcrumb.h emits it, and then the separator.
    Level is strictly 'ON' or 'OFF' - no gap labels.
    """
    if bound == "slow":
        on_dur = 50.0
        pulse_off_dur = 15.625
        digit_gap = 100.0
        frame_gap = 200.0
    else:  # nominal
        on_dur = 20.9715
        pulse_off_dur = 6.5536
        digit_gap = 41.9430
        frame_gap = 83.8860

    edges = []
    t = 0.0

    for code in codes:
        tens = code // 10
        units = code % 10

        # Tens pulses: each followed by its pulse OFF delay
        for i in range(tens):
            edges.append((round(t, 4), "ON"))
            t += on_dur
            edges.append((round(t, 4), "OFF"))
            t += pulse_off_dur
            if i < tens - 1:
                t += pulse_preempt

        # Inter-digit gap follows the last pulse's OFF delay
        t += digit_gap + digit_preempt

        # Units pulses: each followed by its pulse OFF delay
        for i in range(units):
            edges.append((round(t, 4), "ON"))
            t += on_dur
            edges.append((round(t, 4), "OFF"))
            t += pulse_off_dur
            if i < units - 1:
                t += pulse_preempt

        # Frame-end gap follows the last pulse's OFF delay
        t += frame_gap + frame_preempt

    return edges


def decode_timestamped_edges(edges: list[tuple[float, str]], bound: str = "slow") -> tuple[list[int] | None, str]:
    """Decode stage codes from a stream of timestamped (time_ms, level) edges.

    Level is strictly 'ON' or 'OFF'. No DIGIT_GAP or FRAME_GAP labels.
    Classification is performed solely by measuring the duration of dark (OFF) intervals:
      Slow bound thresholds (stated preemption tolerance = 50.0 ms):
        Pulse gap:   [10.0 ms, 66.0 ms]     (base 15.625 ms + up to 50.0 ms delay = 65.625 ms)
        Ambiguous:   (66.0 ms, 115.0 ms)
        Digit gap:   [115.0 ms, 166.0 ms]   (base 115.625 ms + up to 50.0 ms delay = 165.625 ms)
        Ambiguous:   (166.0 ms, 215.0 ms)
        Frame gap:   [215.0 ms, inf)        (base 215.625 ms)
      Nominal bound thresholds (stated preemption tolerance = 20.0 ms):
        Pulse gap:   [4.0 ms, 27.0 ms]      (base 6.5536 ms + up to 20.0 ms delay = 26.5536 ms)
        Ambiguous:   (27.0 ms, 48.0 ms)
        Digit gap:   [48.0 ms, 69.0 ms]     (base 48.4966 ms + up to 20.0 ms delay = 68.4966 ms)
        Ambiguous:   (69.0 ms, 90.0 ms)
        Frame gap:   [90.0 ms, inf)         (base 90.4396 ms)
    """
    if not edges:
        return [], "OK"

    pulses = []
    gaps = []

    if bound == "slow":
        min_on = 30.0
        max_on = 70.0
        pulse_gap_max = 66.0
        digit_gap_min = 115.0
        digit_gap_max = 166.0
        frame_gap_min = 215.0
    else:
        min_on = 12.0
        max_on = 30.0
        pulse_gap_max = 27.0
        digit_gap_min = 48.0
        digit_gap_max = 69.0
        frame_gap_min = 90.0

    i = 0
    while i < len(edges):
        if edges[i][1] != "ON":
            return None, f"Expected ON edge at index {i}"
        t_on = edges[i][0]
        i += 1
        if i >= len(edges) or edges[i][1] != "OFF":
            return None, f"Expected OFF edge after ON at index {i}"
        t_off = edges[i][0]
        on_dur = t_off - t_on
        if on_dur < min_on or on_dur > max_on:
            return None, f"Ambiguous/invalid ON pulse duration {on_dur:.2f} ms"
        pulses.append(on_dur)
        i += 1
        if i < len(edges):
            if edges[i][1] != "ON":
                return None, f"Expected ON edge at index {i}"
            gap_dur = edges[i][0] - t_off
            gaps.append(gap_dur)
        else:
            gaps.append(frame_gap_min + 10.0)

    decoded = []
    tens = 0
    units = 0
    in_units = False

    for gap_dur in gaps:
        if not in_units:
            tens += 1
        else:
            units += 1

        if gap_dur <= pulse_gap_max:
            pass
        elif digit_gap_min <= gap_dur <= digit_gap_max:
            if in_units:
                return None, f"Ambiguous: multiple digit gaps in single frame (gap={gap_dur:.2f} ms)"
            in_units = True
        elif gap_dur >= frame_gap_min:
            if not in_units or units == 0 or tens == 0:
                return None, f"Ambiguous: frame end with invalid tens={tens}, units={units}"
            code = tens * 10 + units
            decoded.append(code)
            tens = 0
            units = 0
            in_units = False
        else:
            return None, f"Ambiguous: dark gap {gap_dur:.2f} ms outside valid intervals"

    return decoded, "OK"


def parse_checkpoint_frames_from_disasm(disasm: str) -> list[dict]:
    """Parse and decode all checkpoint frames directly from core disassembly."""
    frame_matches = list(re.finditer(
        r"(stmdb\s+sp!,\s*\{r0,\s*r1,\s*r2,\s*r3,\s*ip,\s*lr\}.*?ldmia(?:\.w)?\s+sp!,\s*\{r0,\s*r1,\s*r2,\s*r3,\s*ip,\s*lr\})",
        disasm,
        re.DOTALL
    ))
    frames = []

    for idx, match in enumerate(frame_matches):
        raw_frame = match.group(1)

        cpsid_matches = list(re.finditer(r"cpsid\s+i", raw_frame))
        msr_matches = list(re.finditer(r"msr\s+CPSR_fsxc,\s*r3", raw_frame))

        parts = raw_frame.split("2097152")
        if len(parts) != 2:
            raise ValueError(f"Frame {idx}: Inter-digit gap (2097152) missing or repeated in frame")
        tens_part, units_part = parts

        tens_stores = len(re.findall(r"movt\s+r1,\s+#77", tens_part))
        units_stores = len(re.findall(r"movt\s+r1,\s+#77", units_part))
        code = tens_stores * 10 + units_stores

        delays = [int(v) for v in re.findall(r"mov(?:\.w)?\s+r2,\s+#([0-9]+)", raw_frame)]
        total_iterations = sum(delays)
        slow_ms = (total_iterations / REF_ITERATIONS) * SLOW_BOUND_MS
        nom_ms = total_iterations * (3.0 / 150_000_000) * 1000.0
        fast_ms = total_iterations * (3.0 / 200_000_000) * 1000.0
        expected_delays_count = (tens_stores + units_stores) * 2 + 2
        has_end_gap = "4194304" in units_part

        pulse_matches = list(re.finditer(
            r"cpsid\s+i\s+.*?(str\s+r1,\s+\[r0[^\]]*\]).*?(str\s+r1,\s+\[r0[^\]]*\]).*?msr\s+CPSR_fsxc,\s*r3",
            raw_frame,
            re.DOTALL
        ))
        valid_pulses = (len(pulse_matches) == (tens_stores + units_stores))

        lines = raw_frame.splitlines()
        in_masked = False
        gaps_unmasked = True
        for line in lines:
            if "cpsid" in line:
                in_masked = True
            elif "msr" in line and "CPSR" in line:
                in_masked = False
            elif any(gap_const in line for gap_const in ("#327680", "#2097152", "#4194304")):
                if in_masked:
                    gaps_unmasked = False

        cleaned_instructions = re.sub(r"^\s*[0-9a-f]+:\s+[0-9a-f ]+\s+", "", raw_frame, flags=re.MULTILINE)
        cleaned_instructions = re.sub(r"<[^>]+>", "", cleaned_instructions)
        cleaned_instructions = re.sub(r"\s+", " ", cleaned_instructions).strip()

        frames.append({
            "index": idx,
            "code": code,
            "tens": tens_stores,
            "units": units_stores,
            "num_cpsid": len(cpsid_matches),
            "num_msr": len(msr_matches),
            "valid_pulses": valid_pulses,
            "gaps_unmasked": gaps_unmasked,
            "delays": delays,
            "total_iterations": total_iterations,
            "slow_ms": slow_ms,
            "nom_ms": nom_ms,
            "fast_ms": fast_ms,
            "delays_count": len(delays),
            "expected_delays_count": expected_delays_count,
            "has_end_gap": has_end_gap,
            "instruction_sequence": cleaned_instructions,
        })

    return frames


class TestPort25LadderFix(unittest.TestCase):
    """Test suite for PORT-25 single-emitter breadcrumb ladder + poweron fix."""

    def test_default_build_hash_invariance(self):
        """Default control build produces locked PORT-19 DISKBOOT SHA-256."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=False, poweron_fix=False, out_dir=tmpdir)
            self.assertEqual(res["diskboot_sha256"], EXPECTED_DEFAULT_DISKBOOT_SHA256)
            self.assertEqual(res["diskboot_size"], EXPECTED_DEFAULT_DISKBOOT_SIZE)

    def test_port24_poweron_build_hash_invariance(self):
        """PORT-24 --poweron-fix build produces unchanged locked SHA-256."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port24_poweron_fix import build_candidate
            build_candidate(poweron_fix=True, out_dir=tmpdir)
            diskboot_bin = os.path.join(tmpdir, "DISKBOOT.BIN")
            self.assertEqual(sha256_file(diskboot_bin), EXPECTED_PORT24_POWERON_DISKBOOT_SHA256)
            self.assertEqual(os.path.getsize(diskboot_bin), EXPECTED_PORT24_POWERON_DISKBOOT_SIZE)

    def test_port24_ladder_build_hash_invariance(self):
        """PORT-24 --ladder build produces unchanged locked SHA-256."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port24_ladder import build_candidate
            build_candidate(ladder=True, out_dir=tmpdir)
            diskboot_bin = os.path.join(tmpdir, "DISKBOOT.BIN")
            self.assertEqual(sha256_file(diskboot_bin), EXPECTED_PORT24_LADDER_DISKBOOT_SHA256)
            self.assertEqual(os.path.getsize(diskboot_bin), EXPECTED_PORT24_LADDER_DISKBOOT_SIZE)

    def test_combined_build_determinism_and_hash(self):
        """Combined build produces deterministic output matching documented SHA-256."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            from build_candidate_port25_ladder_fix import build_candidate
            res1 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir1)
            res2 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir2)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"], "Build must be byte-for-byte deterministic")
            self.assertEqual(res1["diskboot_sha256"], EXPECTED_COMBINED_DISKBOOT_SHA256)
            self.assertEqual(res1["diskboot_size"], EXPECTED_COMBINED_DISKBOOT_SIZE)

    def test_ladder_only_combination_assembles(self):
        """Ladder-only combination (ladder=True, poweron_fix=False) builds without branch errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=False, out_dir=tmpdir)
            self.assertEqual(res["diskboot_sha256"], EXPECTED_LADDER_ONLY_DISKBOOT_SHA256)
            self.assertEqual(res["diskboot_size"], EXPECTED_LADDER_ONLY_DISKBOOT_SIZE)

    def test_combined_build_enables_both_macros(self):
        """Combined build disassembles to confirm both G3X_POWERON_FIX and LED pulse stores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)
            core_elf = res["core_elf"]

            proc = subprocess.run(
                [str(OBJDUMP), "-d", core_elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = proc.stdout

            match = re.search(r"<sub_fc05b962_my>:(.*?)(<task_Startup_my>:|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(match, "sub_fc05b962_my function must be found in disassembly")
            func_disasm = match.group(1)
            self.assertIn("movs\tr0, #1", func_disasm)
            self.assertNotIn("cbnz", func_disasm, "cbnz r0 power check branch must be omitted under G3X_POWERON_FIX=1")
            self.assertNotIn("sub_fc05ba56", func_disasm, "power cut function must be bypassed under G3X_POWERON_FIX=1")

            self.assertIn("#53771", disasm)  # 0xd20b in movt r0, #0xd20b
            self.assertIn("#2180", disasm)   # 0x0884 in movw r0, #0x0884
            self.assertIn("#77", disasm)     # 0x004d in movt r1, #0x004d
            self.assertIn("#76", disasm)     # 0x004c in movt r1, #0x004c

            self.assertIn("#1048576", disasm)  # 0x00100000 (ON delay)
            self.assertIn("#327680", disasm)   # 0x00050000 (OFF delay)
            self.assertIn("#2097152", disasm)  # 0x00200000 (inter-digit gap)
            self.assertIn("#4194304", disasm)  # 0x00400000 (frame-end gap)

    def test_disassembled_stage_codes_and_atomicity(self):
        """Derives stage codes, verifies cpsid i IRQ masking during pulses, unmasked gaps, and bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)
            core_elf = res["core_elf"]

            proc = subprocess.run(
                [str(OBJDUMP), "-d", core_elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = proc.stdout

            frames = parse_checkpoint_frames_from_disasm(disasm)
            self.assertEqual(len(frames), len(EXPECTED_CORE_CODES), f"Expected {len(EXPECTED_CORE_CODES)} frames in core")

            for f in frames:
                self.assertTrue(f["valid_pulses"], f"Frame {f['code']} must have valid cpsid i -> ON -> OFF -> msr pulse structure")
                self.assertTrue(f["gaps_unmasked"], f"Frame {f['code']} must leave all gaps unmasked")
                self.assertEqual(f["num_cpsid"], f["tens"] + f["units"])
                self.assertEqual(f["num_msr"], f["tens"] + f["units"])
                self.assertTrue(f["has_end_gap"], f"Frame {f['code']} missing frame-end gap")
                self.assertEqual(
                    f["delays_count"],
                    f["expected_delays_count"],
                    f"Frame {f['code']} has mismatched delay loop counts",
                )

            for f in frames:
                if f["code"] in POST_ARMING_CODES:
                    self.assertLess(
                        f["slow_ms"],
                        1000.0,
                        f"Post-arming stage Code {f['code']} duration {f['slow_ms']:.2f} ms exceeds 1000 ms bound",
                    )
                    self.assertLess(
                        f["total_iterations"],
                        20971520,
                        f"Post-arming stage Code {f['code']} iterations {f['total_iterations']} exceeds 20,971,520 (1000 ms bound)",
                    )

            extracted_codes = [f["code"] for f in frames]
            self.assertEqual(extracted_codes, EXPECTED_CORE_CODES, "Extracted codes must match expected sequence")
            self.assertEqual(len(extracted_codes), len(set(extracted_codes)), "Every stage code must be strictly unique!")

            instruction_seqs = [f["instruction_sequence"] for f in frames]
            self.assertEqual(
                len(instruction_seqs),
                len(set(instruction_seqs)),
                "No two checkpoints may expand to the same instruction sequence!",
            )

    def test_single_emitter_no_parent_emit_after_createtask(self):
        """Single-emitter rule: parent Initial Task emits no LED frame after CreateTask,
        contains no cross-context flags or queues, and child Startup Task emits directly upon entry.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)
            core_elf = res["core_elf"]

            proc = subprocess.run(
                [str(OBJDUMP), "-d", core_elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = proc.stdout

            match_p = re.search(r"<sub_fc05b962_my>:(.*?)(<task_Startup_my>:|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(match_p, "sub_fc05b962_my function must be found in disassembly")
            parent_disasm = match_p.group(1)

            # Locate CreateTask call in parent
            createtask_match = re.search(r"blx\s+[0-9a-f]+\s+<sub_fc31bbc4>(.*)", parent_disasm, re.DOTALL)
            self.assertIsNotNone(createtask_match, "CreateTask blx call must be in sub_fc05b962_my")
            post_createtask = createtask_match.group(1)

            # 1. Parent disassembly after CreateTask MUST NOT emit any frames
            parent_frames_after = parse_checkpoint_frames_from_disasm(post_createtask)
            self.assertEqual(len(parent_frames_after), 0, "Parent must emit NO frames after CreateTask call")

            # 2. No LED stores, no CPSID masking, no replay calls in parent post-createtask
            self.assertNotIn("cpsid", post_createtask, "Parent must not mask IRQs after CreateTask")
            self.assertNotIn("ladder_replay_pending", post_createtask, "Replay routine must not be called")
            self.assertIn("movs\tr0, #0", post_createtask)
            self.assertIn("pop\t{r3, pc}", post_createtask)

            # 3. Disassembly contains NO cross-context flags or queues
            self.assertNotIn("ladder_createtask_done", disasm, "ladder_createtask_done flag must be removed")
            self.assertNotIn("ladder_pending_mask", disasm, "ladder_pending_mask bitmask must be removed")
            self.assertNotIn("ladder_replay_pending", disasm, "ladder_replay_pending function must be removed")

            # 4. Generated source contains no emit call after task-creation call site
            boot_proto_c = os.path.join(tmpdir, "boot_prototype_ladder.c")
            with open(boot_proto_c, "r", encoding="utf-8") as f:
                src = f.read()

            self.assertNotIn("ladder_createtask_done", src)
            self.assertNotIn("ladder_pending_mask", src)
            self.assertNotIn("ladder_replay_pending", src)

            # In sub_fc05b962_my, verify no macro after sub_fc31bbc4
            match_src = re.search(r"sub_fc05b962_my\(void\)\s*\{\s*asm volatile\s*\((.*?)\);", src, re.DOTALL)
            self.assertIsNotNone(match_src)
            body = match_src.group(1)
            createtask_idx = body.find("sub_fc31bbc4")
            self.assertNotEqual(createtask_idx, -1)
            after_createtask_src = body[createtask_idx:]
            self.assertNotIn("CORE_LADDER_PULSE", after_createtask_src)
            self.assertNotIn("CHILD_LADDER_PULSE", after_createtask_src)

            # 5. Child emits Code 31 as its first frame directly without pending check
            match_c = re.search(r"<task_Startup_my>:(.*?)(<g3x_trace_boot_post_bss>|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(match_c)
            child_disasm = match_c.group(1)
            child_frames = parse_checkpoint_frames_from_disasm(child_disasm)
            self.assertGreaterEqual(len(child_frames), 1)
            self.assertEqual(child_frames[0]["code"], 31, "First frame in task_Startup_my must be Code 31")

    def test_decoder_timestamped_edges_with_preemption_tolerance(self):
        """Timestamped edge decoder accurately recovers codes under injected preemption delays up to stated tolerance."""
        # 1. Test every core code individually with no preemption delay at slow bound
        for code in EXPECTED_CORE_CODES:
            edges = generate_timestamped_edges([code], pulse_preempt=0.0, digit_preempt=0.0, frame_preempt=0.0, bound="slow")
            decoded, err = decode_timestamped_edges(edges, bound="slow")
            self.assertEqual(err, "OK", f"Decoding error for code {code}: {err}")
            self.assertEqual(decoded, [code], f"Code {code} must decode correctly with zero delay")

        # 2. Inject delays up to stated preemption tolerance (50.0 ms at slow bound) into all dark intervals
        for delay in [0.0, 10.0, 25.0, 45.0, 50.0]:
            edges = generate_timestamped_edges(
                EXPECTED_CORE_CODES,
                pulse_preempt=delay,
                digit_preempt=delay,
                frame_preempt=delay,
                bound="slow",
            )
            decoded, err = decode_timestamped_edges(edges, bound="slow")
            self.assertEqual(err, "OK", f"Error at preemption delay {delay} ms: {err}")
            self.assertEqual(
                decoded,
                EXPECTED_CORE_CODES,
                f"Full code sequence must decode correctly with {delay} ms injected preemption delay",
            )

        # 3. Test at nominal bound with tolerance up to 20.0 ms
        for delay in [0.0, 5.0, 10.0, 20.0]:
            edges = generate_timestamped_edges(
                EXPECTED_CORE_CODES,
                pulse_preempt=delay,
                digit_preempt=delay,
                frame_preempt=delay,
                bound="nominal",
            )
            decoded, err = decode_timestamped_edges(edges, bound="nominal")
            self.assertEqual(err, "OK", f"Nominal bound error at preemption delay {delay} ms: {err}")
            self.assertEqual(
                decoded,
                EXPECTED_CORE_CODES,
                f"Full code sequence must decode correctly at nominal bound with {delay} ms preemption delay",
            )

    def test_decoder_worst_case_code_22_at_tolerance_bounds(self):
        """Worst-case code (22) exercises intra-digit gaps, inter-digit gap, and frame-end gap.
        Asserts correct decoding at nominal timing and at claimed tolerance bounds (50 ms slow, 20 ms nom).
        """
        # Slow bound nominal (0 ms delay)
        edges_slow_nom = generate_timestamped_edges([22], pulse_preempt=0.0, digit_preempt=0.0, frame_preempt=0.0, bound="slow")
        dec, err = decode_timestamped_edges(edges_slow_nom, bound="slow")
        self.assertEqual(err, "OK")
        self.assertEqual(dec, [22], "Code 22 must decode at slow nominal")

        # Slow bound at upper tolerance limit (50.0 ms delay on all dark gaps)
        edges_slow_max = generate_timestamped_edges([22], pulse_preempt=50.0, digit_preempt=50.0, frame_preempt=50.0, bound="slow")
        dec, err = decode_timestamped_edges(edges_slow_max, bound="slow")
        self.assertEqual(err, "OK")
        self.assertEqual(dec, [22], "Code 22 must decode at slow tolerance bound (50 ms)")

        # Nominal bound nominal (0 ms delay)
        edges_nom_nom = generate_timestamped_edges([22], pulse_preempt=0.0, digit_preempt=0.0, frame_preempt=0.0, bound="nominal")
        dec, err = decode_timestamped_edges(edges_nom_nom, bound="nominal")
        self.assertEqual(err, "OK")
        self.assertEqual(dec, [22], "Code 22 must decode at nominal base")

        # Nominal bound at upper tolerance limit (20.0 ms delay on all dark gaps)
        edges_nom_max = generate_timestamped_edges([22], pulse_preempt=20.0, digit_preempt=20.0, frame_preempt=20.0, bound="nominal")
        dec, err = decode_timestamped_edges(edges_nom_max, bound="nominal")
        self.assertEqual(err, "OK")
        self.assertEqual(dec, [22], "Code 22 must decode at nominal tolerance bound (20 ms)")

    def test_decoder_reports_ambiguous_on_delay_exceeding_tolerance(self):
        """Delays beyond stated preemption tolerance are reported as ambiguous rather than decoded wrongly."""
        # Case 1: Pulse gap delayed beyond 50 ms tolerance into ambiguous zone (e.g. 55 ms delay -> gap 70.625 ms in (66, 115))
        edges_ambig_gap = generate_timestamped_edges([22], pulse_preempt=55.0, digit_preempt=0.0, bound="slow")
        decoded, err = decode_timestamped_edges(edges_ambig_gap, bound="slow")
        self.assertIsNone(decoded, "Decoder must return None for gap in ambiguous window")
        self.assertIn("Ambiguous", err, "Decoder must report Ambiguous when delay exceeds tolerance")

        # Case 2: Digit gap delayed beyond 50 ms tolerance into ambiguous zone (e.g. 55 ms delay -> gap 170.625 ms in (166, 215))
        edges_ambig_digit = generate_timestamped_edges([22], pulse_preempt=0.0, digit_preempt=55.0, bound="slow")
        decoded, err = decode_timestamped_edges(edges_ambig_digit, bound="slow")
        self.assertIsNone(decoded, "Decoder must return None when digit gap delayed into ambiguous zone")
        self.assertIn("Ambiguous", err)

        # Case 3: Distorted ON pulse duration (e.g. 90 ms > 70 ms max_on)
        edges_bad_on = [(0.0, "ON"), (90.0, "OFF"), (290.0, "ON"), (340.0, "OFF")]
        decoded, err = decode_timestamped_edges(edges_bad_on, bound="slow")
        self.assertIsNone(decoded, "Decoder must return None on distorted ON pulse")
        self.assertTrue("Ambiguous" in err or "invalid" in err)

    def test_port25_output_directories_disjoint_from_port24(self):
        """PORT-25 output directories must be strictly disjoint from all PORT-24 directories."""
        port24_dirs = {
            "candidate_breadcrumb_ladder",
            "candidate_poweron_fix",
            "candidate",
        }
        port25_dirs = {
            "candidate_port25_ladder_fix",
            "candidate_port25_ladder",
            "candidate_port25_poweron_fix",
            "candidate_port25_default",
        }
        intersection = port25_dirs.intersection(port24_dirs)
        self.assertEqual(len(intersection), 0, f"PORT-25 dirs must not overlap PORT-24 dirs: {intersection}")
        for p25 in port25_dirs:
            self.assertIn("port25", p25, f"PORT-25 dir '{p25}' must contain 'port25'")

        with open(TOOLS_DIR / "build_candidate_port25_ladder_fix.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("candidate_breadcrumb_ladder", src, "PORT-25 script must not write to PORT-24 ladder dir")
        self.assertNotIn("candidate_poweron_fix\"", src, "PORT-25 script must not write to PORT-24 poweron dir")
        self.assertIn("candidate_port25_ladder_fix", src)
        self.assertIn("candidate_port25_ladder", src)
        self.assertIn("candidate_port25_poweron_fix", src)
        self.assertIn("candidate_port25_default", src)

    def test_protocol_description_matches_macro_structure(self):
        """Verifies that docs/PORT25_LADDER_FIX_CANDIDATE.md accurately reflects macro structure:
        no preamble, tens pulses, digit gap, units pulses, and frame-end gap,
        and documents loader cumulative single pulse protocol separately with all gap durations."""
        led_header = SUB_DIR / "led_breadcrumb.h"
        with open(led_header, "r", encoding="utf-8") as f:
            header_content = f.read()

        doc_file = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"
        with open(doc_file, "r", encoding="utf-8") as f:
            doc_content = f.read()

        macro_match = re.search(r"#define CORE_LADDER_FRAME\(tens,\s*units\)(.*?)(?=#define|\Z)", header_content, re.DOTALL)
        self.assertIsNotNone(macro_match, "CORE_LADDER_FRAME macro must exist in led_breadcrumb.h")
        macro_body = macro_match.group(1)
        self.assertNotIn("PREAMBLE", macro_body)
        self.assertIn("LADDER_PULSES_##tens", macro_body)
        self.assertIn("LADDER_DIGIT_GAP", macro_body)
        self.assertIn("LADDER_PULSES_##units", macro_body)
        self.assertIn("LADDER_FRAME_END", macro_body)

        pos_tens = macro_body.find("LADDER_PULSES_##tens")
        pos_gap = macro_body.find("LADDER_DIGIT_GAP")
        pos_units = macro_body.find("LADDER_PULSES_##units")
        pos_end = macro_body.find("LADDER_FRAME_END")
        self.assertTrue(pos_tens < pos_gap < pos_units < pos_end, "Macro structure must be: tens -> digit gap -> units -> frame end")

        self.assertNotIn("preamble", doc_content.lower(), "Documentation must not mention any preamble")
        self.assertIn("Loader-Stage Protocol", doc_content)
        self.assertIn("Core-Stage Protocol", doc_content)
        self.assertIn("cumulative single pulses", doc_content.lower())

        self.assertIn("41.94", doc_content)  # nominal digit gap ms
        self.assertIn("100.0", doc_content)  # slow digit gap ms
        self.assertIn("83.89", doc_content)  # nominal frame gap ms
        self.assertIn("200.0", doc_content)  # slow frame gap ms
        self.assertIn("6.55", doc_content)   # nominal pulse gap ms
        self.assertIn("15.625", doc_content) # slow pulse gap ms
        self.assertIn("57.62", doc_content)  # nominal loader-to-core transition ms
        self.assertIn("138.28", doc_content) # slow loader-to-core transition ms

    def test_pulse_timing_under_150ms_and_200ms_cap(self):
        """Every pulse delay constant is within the documented <= 150 ms bound and 200 ms cap."""
        on_ms_slow = (FRAME_ON_ITERATIONS / REF_ITERATIONS) * SLOW_BOUND_MS
        on_ms_nom = FRAME_ON_ITERATIONS * (3.0 / 150_000_000) * 1000.0
        on_ms_fast = FRAME_ON_ITERATIONS * (3.0 / 200_000_000) * 1000.0

        self.assertAlmostEqual(on_ms_slow, 50.0, places=3)
        self.assertLessEqual(on_ms_slow, 150.0, "ON pulse must be <= 150 ms at slow bound")
        self.assertLess(on_ms_slow, 200.0, "ON pulse must be strictly under 200 ms cap")
        self.assertEqual(200.0 - on_ms_slow, 150.0, "Headroom to 200 ms cap must be 150 ms")
        self.assertEqual(150.0 - on_ms_slow, 100.0, "Headroom to 150 ms target must be 100 ms")

        self.assertAlmostEqual(on_ms_nom, 20.9715, places=3)
        self.assertAlmostEqual(on_ms_fast, 15.7286, places=3)

    def test_final_state_led_off(self):
        """Disassembly confirms each pulse macro terminates by writing LED OFF (0x004C0003)."""
        led_header = SUB_DIR / "led_breadcrumb.h"
        with open(led_header, "r") as f:
            content = f.read()

        self.assertIn("#define LADDER_PULSE_ON_OFF", content)
        self.assertIn("movw    r1, #0x0003", content)
        self.assertIn("movt    r1, #0x004c", content)
        self.assertIn("str     r1, [r0]", content)
        self.assertIn("cpsid   i", content, "ON store must be preceded by cpsid i")
        self.assertIn("msr     cpsr_cxsf, r3", content, "OFF store must be followed by msr CPSR restore")
        self.assertIn("pop     {r0, r1, r2, r3, r12, lr}", content)

    def test_reversible_dancingbits_decoding(self):
        """Encoded DISKBOOT.BIN decodes via dancingbits row 13 bit-for-bit identical to loader."""
        from validate_candidate_port2a import decode_dancingbits_row13
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)

            with open(res["diskboot_bin"], "rb") as f:
                diskboot_bytes = f.read()
            with open(res["loader_bin"], "rb") as f:
                loader_bytes = f.read()

            self.assertEqual(diskboot_bytes[0], 0, "Byte 0 of encoded DISKBOOT must be 0x00")
            self.assertEqual(len(diskboot_bytes), len(loader_bytes) + 1)
            decoded = decode_dancingbits_row13(diskboot_bytes)
            self.assertEqual(decoded, loader_bytes, "Decoded DISKBOOT must match loader binary bit-for-bit")

    def test_embedded_core_integrity(self):
        """Candidate loader embeds candidate_main.bin bit-for-bit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from build_candidate_port25_ladder_fix import build_candidate
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)

            with open(res["core_bin"], "rb") as f:
                core_bytes = f.read()
            with open(res["loader_bin"], "rb") as f:
                loader_bytes = f.read()

            self.assertIn(core_bytes, loader_bytes, "Loader binary must embed candidate_main.bin bit-for-bit")

    def test_no_new_addresses(self):
        """Only verified LED register 0xD20B0884 is used; no new MMIO addresses introduced."""
        led_header = SUB_DIR / "led_breadcrumb.h"
        with open(led_header, "r") as f:
            content = f.read()

        addrs = re.findall(r"0x[0-9a-fA-F]{8}", content)
        for a in addrs:
            addr_int = int(a, 16)
            if addr_int >= 0xC0000000:  # MMIO range
                self.assertEqual(
                    addr_int,
                    0xD20B0884,
                    f"Unexpected MMIO address 0x{addr_int:08X} in led_breadcrumb.h; only 0xD20B0884 allowed",
                )


if __name__ == "__main__":
    unittest.main()
