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
    N_on  = 0x00134000 (1,261,568 iterations) -> ~20.05 ms (fast 100ms) / ~25.07 ms (nom 125ms) / ~60.16 ms (slow 300ms) [INFERRED]
    N_off = 0x002AC000 (2,801,664 iterations) -> ~44.53 ms (fast 100ms) / ~55.66 ms (nom 125ms) / ~133.59 ms (slow 300ms) [INFERRED]
    Total loop = 0x003E0000 (4,063,232 iterations) -> ~64.58 ms (fast) / ~80.73 ms (nom) / 193.75 ms (slow) [INFERRED]
- Non-loop overhead: conservative 1.0 ms allocated for ~9 instructions + 2 barriers (< 200 cycles).
- Full step (loops + overhead): 193.75 ms + 1.0 ms = 194.75 ms strictly < 200.0 ms cap [INFERRED].
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

PULSE_ON_ITERATIONS = 0x00134000            # 1,261,568 iterations
PULSE_OFF_ITERATIONS = 0x002AC000           # 2,801,664 iterations
SINGLE_STEP_ITERATIONS = PULSE_ON_ITERATIONS + PULSE_OFF_ITERATIONS  # 4,063,232 (0x003E0000)

NON_LOOP_OVERHEAD_MARGIN_MS = 1.0           # 1.0 ms justified non-loop instruction overhead bound
MAX_SAFETY_LIMIT_MS = 200.0

STATIC_REFERENCE_ADDRS = [
    "0x000081E2",
    "0x00008246",
    "0x00008268",
    "0x00008296",
    "0x000082B8",
    "0x000082EA",
    "0x0000830E",
]

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

TRIAGE_RULES = [
    ("0 flashes", "Failed before or during Step 1 pulse (MBR, dancingbits row 13, PID mismatch in check_compat, or early power loss)."),
    ("1 flash",   "Failed between Step 1 and Step 2 (payload relocation in core_copy, or Boot Witness Stage 1 write/checksum)."),
    ("2 flashes", "Failed between Step 2 and Step 3 (preparation for D-cache maintenance, or entry into cache asm block)."),
    ("3 flashes", "Failed during D-cache clean & invalidate (ROM_DCACHE_CLEAN_INV 0xFC127AB1 subroutine call or dsb sy)."),
    ("4 flashes", "Failed between Step 4 and Step 5 (instructions between D-cache and I-cache maintenance)."),
    ("5 flashes", "Failed during I-cache & branch predictor invalidation (ROM_ICACHE_INV_BP 0xFC127B09 subroutine call, dsb sy, or isb sy)."),
    ("6 flashes", "Failed between Step 6 and Step 7 (interrupt mask cpsid if)."),
    ("7 flashes", "Step 7 pulse completed. Core entry address setup, terminal bx hand-off, and core execution are UNKNOWN (uninstrumented); fault occurred during terminal hand-off or inside CHDK core."),
]

AMBIGUITY_NOTE = (
    "Ambiguity note: A failure during a pulse (camera goes dark while LED is ON or OFF) "
    "can make the count ambiguous by one. If a pulse cuts off abruptly without completing "
    "its OFF gap, the fault occurred during that pulse."
)


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
    full_step_ms_slowest = total_ms_max + NON_LOOP_OVERHEAD_MARGIN_MS

    return {
        "iterations_on": PULSE_ON_ITERATIONS,
        "iterations_off": PULSE_OFF_ITERATIONS,
        "total_iterations": SINGLE_STEP_ITERATIONS,
        "overhead_margin_ms": NON_LOOP_OVERHEAD_MARGIN_MS,
        "on_ms_fastest": round(on_ms_fast, 2),
        "off_ms_fastest": round(off_ms_fast, 2),
        "total_ms_fastest": round(total_ms_fast, 2),
        "on_ms_nominal": round(on_ms_nom, 2),
        "off_ms_nominal": round(off_ms_nom, 2),
        "total_ms_nominal": round(total_ms_nom, 2),
        "on_ms_slowest": round(on_ms_max, 2),
        "off_ms_slowest": round(off_ms_max, 2),
        "total_ms_slowest": round(total_ms_max, 2),
        "full_step_ms_slowest": round(full_step_ms_slowest, 2),
        "under_safety_limit": full_step_ms_slowest < MAX_SAFETY_LIMIT_MS,
    }


def parse_and_validate_ladder_stores(disasm_text: str, exit_on_error: bool = True) -> list[str]:
    """Parse and validate ladder stores from objdump disassembly.

    Validates:
    - Exactly 14 stores forming 7 complete ON->OFF pairs in order.
    - Base register was loaded with 0xD20B0884 for every store.
    - Value register was loaded with 0x004D0002 (ON) for even stores (0, 2, 4...)
      and 0x004C0003 (OFF) for odd stores (1, 3, 5...).
    - Exits non-zero (or raises ValueError if exit_on_error is False) otherwise.
    - Returns the list of 7 ON store disassembly addresses.
    """
    lines = disasm_text.splitlines()

    # Pass 1: Parse 32-bit literal words across disassembly
    literal_pool: dict[int, int] = {}
    for line in lines:
        m = re.match(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+(?:\.word\s+(?:0x)?([0-9a-fA-F]+))?", line)
        if m:
            addr = int(m.group(1), 16)
            val = int(m.group(3), 16) if m.group(3) else int(m.group(2), 16)
            literal_pool[addr] = val

    # Pass 2: Instruction tracing inside my_restart
    in_restart = False
    regs: dict[str, int | None] = {}
    stores: list[tuple[str, str, int | None, str, int | None]] = []

    for line in lines:
        if "<my_restart>:" in line:
            in_restart = True
            regs = {}
            continue
        if in_restart and line.startswith("0000") and "<" in line:
            break
        if not in_restart:
            continue

        # Subroutine call clobbers caller-saved scratch registers
        if re.search(r"\bblx?\s+", line):
            for r in ("r0", "r1", "r2", "r3", "r12", "lr"):
                regs.pop(r, None)
            continue

        # ldr rX, [pc, #offset] ; (target_addr ...)
        m_ldr_pc = re.search(r"ldr\s+(r\d+),\s*\[pc,\s*#\d+\]\s*;\s*\(([0-9a-fA-F]+)", line)
        if m_ldr_pc:
            reg = m_ldr_pc.group(1)
            target = int(m_ldr_pc.group(2), 16)
            regs[reg] = literal_pool.get(target)
            continue

        # ldr rX, =const
        m_ldr_const = re.search(r"ldr\s+(r\d+),\s*=(0x[0-9a-fA-F]+|\d+)", line)
        if m_ldr_const:
            reg = m_ldr_const.group(1)
            regs[reg] = int(m_ldr_const.group(2), 0)
            continue

        # movw rX, #imm16
        m_movw = re.search(r"movw\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)", line)
        if m_movw:
            reg = m_movw.group(1)
            regs[reg] = int(m_movw.group(2), 0) & 0xFFFF
            continue

        # movt rX, #imm16
        m_movt = re.search(r"movt\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)", line)
        if m_movt:
            reg = m_movt.group(1)
            old = regs.get(reg, 0) or 0
            regs[reg] = (old & 0xFFFF) | ((int(m_movt.group(2), 0) & 0xFFFF) << 16)
            continue

        # mov / mov.w / movs rX, #imm
        m_mov_imm = re.search(r"mov(?:\.w|s)?\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)", line)
        if m_mov_imm:
            reg = m_mov_imm.group(1)
            regs[reg] = int(m_mov_imm.group(2), 0)
            continue

        # str rVal, [rBase...]
        m_str = re.search(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+str(?:\.w)?\s+(r\d+),\s*\[(r\d+)", line)
        if m_str:
            addr = int(m_str.group(1), 16)
            vreg = m_str.group(2)
            breg = m_str.group(3)
            # Exclude Boot Witness struct stores (which all use base r1)
            if breg == "r1":
                continue
            stores.append((f"0x{addr:08X}", breg, regs.get(breg), vreg, regs.get(vreg)))

    def fail(msg: str):
        if exit_on_error:
            sys.stderr.write(msg + "\n")
            sys.exit(1)
        raise ValueError(msg)

    # 1. Validate exactly 14 stores
    if len(stores) != 14:
        fail(f"Error: ELF does not contain exactly 14 ladder stores (found {len(stores)}). Expected 7 complete ON->OFF pairs.")

    # 2. Validate each store in order (forming 7 complete ON->OFF pairs)
    for i, (addr, breg, bval, vreg, vval) in enumerate(stores):
        # Base register check
        if bval != G3X_LED_MMIO:
            bval_str = f"0x{bval:08X}" if bval is not None else "unknown/None"
            fail(f"Error: Store {i} at {addr}: base register {breg} loaded with {bval_str}, expected 0x{G3X_LED_MMIO:08X}.")

        # Value register check
        is_on = (i % 2 == 0)
        expected_val = G3X_LED_ON if is_on else G3X_LED_OFF
        kind_str = f"ON (0x{G3X_LED_ON:08X})" if is_on else f"OFF (0x{G3X_LED_OFF:08X})"
        if vval != expected_val:
            vval_str = f"0x{vval:08X}" if vval is not None else "unknown/None"
            fail(f"Error: Store {i} at {addr}: value register {vreg} loaded with {vval_str}, expected {kind_str}.")

    # Return ON store addresses (first store of each of the 7 pairs)
    return [s[0] for s in stores[0::2]]


def extract_disasm_addresses(loader_elf: str | Path, exit_on_error: bool = True) -> list[str]:
    """Extract str addresses for 7 ladder pulses from candidate_loader.elf objdump.
    
    Exits with non-zero status if file missing, objdump fails, or validation fails.
    """
    elf_path = Path(loader_elf)
    if not elf_path.is_file():
        msg = f"Error: Specified loader ELF does not exist: {elf_path}"
        if exit_on_error:
            sys.stderr.write(msg + "\n")
            sys.exit(1)
        raise FileNotFoundError(msg)

    if not OBJDUMP.is_file():
        msg = f"Error: objdump tool not found at {OBJDUMP}"
        if exit_on_error:
            sys.stderr.write(msg + "\n")
            sys.exit(1)
        raise FileNotFoundError(msg)

    res = subprocess.run(
        [str(OBJDUMP), "-d", str(elf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        msg = f"Error: objdump failed on {elf_path} (returncode {res.returncode}):\n{res.stderr}"
        if exit_on_error:
            sys.stderr.write(msg + "\n")
            sys.exit(1)
        raise RuntimeError(msg)

    return parse_and_validate_ladder_stores(res.stdout, exit_on_error=exit_on_error)


def generate_ladder_table(loader_elf: str | Path | None = None, is_reference: bool = False) -> list[dict]:
    """Generate complete step-to-code ladder table."""
    timing = calculate_timing()
    if is_reference:
        addrs = list(STATIC_REFERENCE_ADDRS)
    else:
        if not loader_elf:
            sys.stderr.write(
                "Error: No candidate loader ELF provided. Specify --loader-elf <path> or use --reference.\n"
            )
            sys.exit(1)
        addrs = extract_disasm_addresses(loader_elf)

    table = []
    for i, step in enumerate(LADDER_STEPS_DEFINITION):
        row = dict(step)
        row["disassembly_addr"] = addrs[i] if i < len(addrs) else "N/A"
        row["timing"] = timing
        table.append(row)
    return table


def print_table_text(table: list[dict], is_reference: bool = False):
    """Print table in formatted human-readable ASCII text."""
    timing = table[0]["timing"]
    print("=" * 105)
    if is_reference:
        print("STATIC REFERENCE, not extracted from a build")
        print("-" * 105)
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
    for signal, desc in TRIAGE_RULES:
        print(f"  {signal:<10} {desc}")
    print(f"  {AMBIGUITY_NOTE}")
    print("=" * 105)


def print_table_markdown(table: list[dict], is_reference: bool = False):
    """Print table formatted as GitHub Markdown."""
    timing = table[0]["timing"]
    if is_reference:
        print("> **STATIC REFERENCE, not extracted from a build**\n")
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
    parser.add_argument(
        "--reference",
        action="store_true",
        help="Print static reference table (not extracted from a build).",
    )
    args = parser.parse_args(argv)

    if args.reference:
        table = generate_ladder_table(is_reference=True)
    else:
        loader_elf = args.loader_elf
        if not loader_elf:
            default_candidate_elf = REPO_ROOT / "candidate_breadcrumb_ladder" / "candidate_loader.elf"
            if default_candidate_elf.is_file():
                loader_elf = default_candidate_elf
            else:
                sys.stderr.write(
                    "Error: No candidate loader ELF found at candidate_breadcrumb_ladder/candidate_loader.elf. "
                    "Specify --loader-elf <path> or use --reference.\n"
                )
                sys.exit(1)
        table = generate_ladder_table(loader_elf=loader_elf, is_reference=False)

    if args.json:
        print(json.dumps(table, indent=2))
    elif args.markdown:
        print_table_markdown(table, is_reference=args.reference)
    else:
        print_table_text(table, is_reference=args.reference)


if __name__ == "__main__":
    main()
