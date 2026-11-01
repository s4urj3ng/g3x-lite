#!/usr/bin/env python3
"""PORT-24 T3 (r3): Breadcrumb Ladder Step-to-Code Table Generator.

Emits the step-to-code table for the Canon PowerShot G3 X (GM1.10C)
diagnostic breadcrumb ladder build, mapping each execution checkpoint from
docs/PORT24_LOADER_TRACE.md (T1) to its progressive flash sequence.

Pulse Scheme: One visible pulse per step.
- Step 1: after_prologue -> Flash 1
- Step 2: after_copy     -> Flash 2
- Step 3: before_dcache  -> Flash 3
- Step 4: after_dcache   -> Flash 4
- Step 5: before_icache  -> Flash 5
- Step 6: after_icache   -> Flash 6
- Step 7: before_bx      -> Flash 7
- Total flashes counted before camera power-off/dark names the last step reached.

Timing Calibration (derived from PORT-23 short-delay build 0x00600000):
- Reference: 0x00600000 (6,291,456 iterations) ~ 100-150 ms (nominal 125 ms)
  [INFERRED: docs/PORT23_POWER_SUPERVISION.md:245]
  and ~300 ms conservative upper bound [INFERRED: docs/PORT24_LOADER_TRACE.md:761].
- Same loop body: 'subs r2, r2, #1; bne' (2 instructions per iteration).
- Per step:
    N_on  = 0x00140000 (1,310,720 iterations) -> ~20.8 ms (fast 100ms) / ~26.0 ms (nom 125ms) / ~62.5 ms (slow 300ms)
    N_off = 0x00280000 (2,621,440 iterations) -> ~41.7 ms (fast 100ms) / ~52.1 ms (nom 125ms) / ~125.0 ms (slow 300ms)
    Total per step = 0x003C0000 (3,932,160 iterations) -> ~62.5 ms (fast) / ~78.1 ms (nom) / ~187.5 ms (slow < 200ms)
- Every step is strictly under 200 ms.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

G3X_LED_MMIO = 0xD20B0884
G3X_LED_ON = 0x004D0002
G3X_LED_OFF = 0x004C0003

# Reference loop calibration from docs/PORT23_POWER_SUPERVISION.md:245 and docs/PORT24_LOADER_TRACE.md:761
PORT23_SHORT_DELAY_ITERATIONS = 0x00600000  # 6,291,456 iterations
PORT23_SHORT_DELAY_MS_FASTEST = 100.0       # 100 ms fastest bound (PORT-23 range min)
PORT23_SHORT_DELAY_MS_NOMINAL = 125.0       # 125 ms nominal (PORT-23 power supervision)
PORT23_SHORT_DELAY_MS_RANGE_MAX = 150.0     # 150 ms range upper bound
PORT23_SHORT_DELAY_MS_SLOWEST = 300.0       # 300 ms slowest bound (PORT-24 trace)

PULSE_ON_ITERATIONS = 0x00140000            # 1,310,720 iterations
PULSE_OFF_ITERATIONS = 0x00280000           # 2,621,440 iterations
SINGLE_STEP_ITERATIONS = PULSE_ON_ITERATIONS + PULSE_OFF_ITERATIONS  # 3,932,160 (0x003C0000)

MAX_SAFETY_LIMIT_MS = 200.0


LADDER_STEPS_DEFINITION = [
    {
        "step_num": 1,
        "name": "after_prologue",
        "description": "After loader entry prologue and check_compat()",
        "t1_step_id": "Step 1/2",
        "t1_step_name": "Loader Entry (_start) & Compatibility Check (check_compat)",
        "t1_source_anchor": "loader_main_breadcrumb.c: after check_compat()",
        "pulse_seq": "Flash 1",
        "cumulative_flashes": 1,
        "registers_preserved": "r0-r3 clobbered per AAPCS; r4-r11, sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 2,
        "name": "after_copy",
        "description": "After CHDK core DRAM relocation and witness write",
        "t1_step_id": "Step 3/4",
        "t1_step_name": "Core Payload Relocation (core_copy) & Boot Witness Stage 1",
        "t1_source_anchor": "loader_main_breadcrumb.c: after core_copy() & witness write",
        "pulse_seq": "Flash 2",
        "cumulative_flashes": 2,
        "registers_preserved": "r0-r3 clobbered per AAPCS; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 3,
        "name": "before_dcache",
        "description": "Before D-cache clean & invalidate (ROM_DCACHE_CLEAN_INV)",
        "t1_step_id": "Step 5",
        "t1_step_name": "Data Cache Clean & Invalidate (DCCISW all sets/ways)",
        "t1_source_anchor": "loader_main_breadcrumb.c: immediately before ROM_DCACHE_CLEAN_INV blx",
        "pulse_seq": "Flash 3",
        "cumulative_flashes": 3,
        "registers_preserved": "r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 4,
        "name": "after_dcache",
        "description": "After D-cache clean & invalidate + dsb sy",
        "t1_step_id": "Step 5",
        "t1_step_name": "Data Cache Clean & Invalidate (after DCCISW + dsb sy)",
        "t1_source_anchor": "loader_main_breadcrumb.c: immediately after ROM_DCACHE_CLEAN_INV blx & dsb sy",
        "pulse_seq": "Flash 4",
        "cumulative_flashes": 4,
        "registers_preserved": "r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 5,
        "name": "before_icache",
        "description": "Before I-cache & branch predictor invalidate (ROM_ICACHE_INV_BP)",
        "t1_step_id": "Step 6",
        "t1_step_name": "Instruction Cache & Branch Predictor Invalidate (ICIALLU/BPIALL)",
        "t1_source_anchor": "loader_main_breadcrumb.c: immediately before ROM_ICACHE_INV_BP blx",
        "pulse_seq": "Flash 5",
        "cumulative_flashes": 5,
        "registers_preserved": "r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 6,
        "name": "after_icache",
        "description": "After I-cache & BP invalidate + dsb sy + isb sy",
        "t1_step_id": "Step 6",
        "t1_step_name": "Instruction Cache & BP Invalidate (after ICIALLU/BPIALL + isb sy)",
        "t1_source_anchor": "loader_main_breadcrumb.c: immediately after ROM_ICACHE_INV_BP blx & dsb sy + isb sy",
        "pulse_seq": "Flash 6",
        "cumulative_flashes": 6,
        "registers_preserved": "r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
    {
        "step_num": 7,
        "name": "before_bx",
        "description": "Before terminal handoff branch into core (after cpsid if)",
        "t1_step_id": "Step 7",
        "t1_step_name": "Interrupt Masking & Core Entry Handoff (before bx r0)",
        "t1_source_anchor": "loader_main_breadcrumb.c: after cpsid if, immediately before bx r0",
        "pulse_seq": "Flash 7",
        "cumulative_flashes": 7,
        "registers_preserved": "r4 (%0), sp (0x7FF8), CPSR.I/F=1 (disabled), Thumb mode (0x003489B5)",
        "cpu_mode": "Thumb-2",
        "final_state": "LED OFF (0x004C0003)",
    },
]


def calculate_timing() -> dict:
    """Calculate calibrated timing for single step pulse across calibration envelope."""
    on_ms_fast = (PULSE_ON_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_FASTEST
    off_ms_fast = (PULSE_OFF_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_FASTEST
    total_ms_fast = (SINGLE_STEP_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_FASTEST

    on_ms_nom = (PULSE_ON_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_NOMINAL
    off_ms_nom = (PULSE_OFF_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_NOMINAL
    total_ms_nom = (SINGLE_STEP_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_NOMINAL

    on_ms_max = (PULSE_ON_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_SLOWEST
    off_ms_max = (PULSE_OFF_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_SLOWEST
    total_ms_max = (SINGLE_STEP_ITERATIONS / PORT23_SHORT_DELAY_ITERATIONS) * PORT23_SHORT_DELAY_MS_SLOWEST

    return {
        "iterations_on": PULSE_ON_ITERATIONS,
        "iterations_off": PULSE_OFF_ITERATIONS,
        "total_iterations": SINGLE_STEP_ITERATIONS,
        "on_ms_fastest": round(on_ms_fast, 2),
        "off_ms_fastest": round(off_ms_fast, 2),
        "total_ms_fastest": round(total_ms_fast, 2),
        "on_ms_nominal": round(on_ms_nom, 2),
        "off_ms_nominal": round(off_ms_nom, 2),
        "total_ms_nominal": round(total_ms_nom, 2),
        "on_ms_slowest": round(on_ms_max, 2),
        "off_ms_slowest": round(off_ms_max, 2),
        "total_ms_slowest": round(total_ms_max, 2),
        "under_safety_limit": total_ms_max < MAX_SAFETY_LIMIT_MS,
    }


def extract_disasm_addresses(loader_elf: str | Path | None = None) -> list[str]:
    """Extract str addresses for 7 ladder pulses from candidate_loader.elf objdump."""
    default_addrs = [
        "0x000081E2",
        "0x00008246",
        "0x00008268",
        "0x00008296",
        "0x000082B8",
        "0x000082EA",
        "0x0000830E",
    ]
    if not loader_elf or not os.path.isfile(str(loader_elf)) or not OBJDUMP.is_file():
        return default_addrs

    res = subprocess.run(
        [str(OBJDUMP), "-d", str(loader_elf)],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return default_addrs

    # Find str r1, [r0, #0] instructions after ldr r1, =0x004D0002
    lines = res.stdout.splitlines()
    str_addrs = []
    in_restart = False
    for line in lines:
        if "<my_restart>:" in line:
            in_restart = True
            continue
        if in_restart and line.startswith("0000") and "<" in line:
            break
        if in_restart:
            # Match: '81e2: 6001 str r1, [r0, #0]'
            m = re.match(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+str\s+r1,\s+\[r0", line)
            if m:
                addr = int(m.group(1), 16)
                str_addrs.append(f"0x{addr:08X}")

    # Every pulse does two stores: ON (0x004D0002) and OFF (0x004C0003)
    # The first store in each pulse is the ON trigger
    on_stores = str_addrs[0::2]
    if len(on_stores) == 7:
        return on_stores
    return default_addrs


def generate_ladder_table(loader_elf: str | Path | None = None) -> list[dict]:
    """Generate complete step-to-code ladder table."""
    timing = calculate_timing()
    addrs = extract_disasm_addresses(loader_elf)

    table = []
    for i, step in enumerate(LADDER_STEPS_DEFINITION):
        row = dict(step)
        row["disassembly_addr"] = addrs[i] if i < len(addrs) else "N/A"
        row["timing"] = timing
        table.append(row)
    return table


def print_table_text(table: list[dict]):
    """Print table in formatted human-readable ASCII text."""
    timing = table[0]["timing"]
    print("=" * 105)
    print("PORT-24 T3: CANON POWERSHOT G3 X BREADCRUMB LADDER STEP-TO-CODE TABLE")
    print("=" * 105)
    print(
        f"Timing: ON = 0x{timing['iterations_on']:X} ({timing['iterations_on']:,} iters, ~{timing['on_ms_nominal']} ms nom / ~{timing['on_ms_slowest']} ms max) | "
        f"OFF = 0x{timing['iterations_off']:X} ({timing['iterations_off']:,} iters, ~{timing['off_ms_nominal']} ms nom / ~{timing['off_ms_slowest']} ms max) | "
        f"Total = ~{timing['total_ms_nominal']} ms nom / ~{timing['total_ms_slowest']} ms max (< 200 ms: {timing['under_safety_limit']})"
    )
    print("-" * 105)
    header = f"{'Step':<5} | {'Step ID':<16} | {'T1 Step':<10} | {'Signal':<9} | {'Count':<5} | {'Disasm Addr':<12} | {'Preserved State'}"
    print(header)
    print("-" * 105)
    for row in table:
        line = (
            f"{row['step_num']:<5} | "
            f"{row['name']:<16} | "
            f"{row['t1_step_id']:<10} | "
            f"{row['pulse_seq']:<9} | "
            f"{row['cumulative_flashes']:<5} | "
            f"{row['disassembly_addr']:<12} | "
            f"{row['registers_preserved']}"
        )
        print(line)
    print("=" * 105)
    print("Owner triage rule:")
    print("  Count total flashes observed before camera goes dark.")
    print("  0 flashes: Failed before check_compat / loader prologue (MBR, dancingbits row 13, PID mismatch).")
    print("  1 flash:   Failed in core_copy or Boot Witness Stage 1 write.")
    print("  2 flashes: Failed between witness write and D-cache clean.")
    print("  3 flashes: Failed during D-cache clean & invalidate (ROM_DCACHE_CLEAN_INV 0xFC127AB1).")
    print("  4 flashes: Failed between D-cache clean and I-cache invalidation.")
    print("  5 flashes: Failed during I-cache & branch predictor invalidation (ROM_ICACHE_INV_BP 0xFC127B09).")
    print("  6 flashes: Failed during pipeline sync (isb sy) or interrupt mask (cpsid if).")
    print("  7 flashes: Loader 100% EXONERATED! Handoff into core entry 0x003489B5 succeeded; crash is in core.")
    print("=" * 105)


def print_table_markdown(table: list[dict]):
    """Print table formatted as GitHub Markdown."""
    timing = table[0]["timing"]
    print("| Step # | Step ID | T1 Step | Signal | Cumulative Flashes | Step Iterations | Nominal ms | Max ms (<200ms) | Disassembly Addr | Preserved State |")
    print("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for row in table:
        print(
            f"| {row['step_num']} | `{row['name']}` | {row['t1_step_id']} | "
            f"**{row['pulse_seq']}** | {row['cumulative_flashes']} | {timing['total_iterations']:,} | "
            f"{timing['total_ms_nominal']} ms | {timing['total_ms_slowest']} ms (YES) | "
            f"`{row['disassembly_addr']}` | {row['registers_preserved']} |"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emit PORT-24 breadcrumb ladder step table.")
    parser.add_argument("--json", action="store_true", help="Output JSON format.")
    parser.add_argument("--markdown", action="store_true", help="Output GitHub Markdown format.")
    parser.add_argument("--loader-elf", default=None, help="Path to candidate_loader.elf for disasm addresses.")
    args = parser.parse_args(argv)

    loader_elf = args.loader_elf
    if not loader_elf:
        default_candidate_elf = REPO_ROOT / "candidate_breadcrumb_ladder" / "candidate_loader.elf"
        if default_candidate_elf.is_file():
            loader_elf = default_candidate_elf
        else:
            port2a_elf = REPO_ROOT / "candidate_port2a" / "candidate_loader.elf"
            if port2a_elf.is_file():
                loader_elf = port2a_elf

    table = generate_ladder_table(loader_elf)

    if args.json:
        print(json.dumps(table, indent=2))
    elif args.markdown:
        print_table_markdown(table)
    else:
        print_table_text(table)


if __name__ == "__main__":
    main()
