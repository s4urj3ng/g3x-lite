#!/usr/bin/env python3
"""PORT-26 T1: LED-Code Ladder Decoder Tool (GM1.10C).

Platform: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
Task: p26-t1-ladder-decode
Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)

Single Source of Truth & Citations:
- p25-t3b Build Source Emit Sites:
  - chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:43-154:
    Loader ladder emit checkpoints for Steps 1..7:
    * Line 44: Step 1 (after_prologue -> STAGE_LOADER_AFTER_PROLOGUE)
    * Line 98: Step 2 (after_copy -> STAGE_LOADER_AFTER_COPY)
    * Line 115: Step 3 (before_dcache -> STAGE_LOADER_BEFORE_DCACHE)
    * Line 126: Step 4 (after_dcache -> STAGE_LOADER_AFTER_DCACHE)
    * Line 131: Step 5 (before_icache -> STAGE_LOADER_BEFORE_ICACHE)
    * Line 143: Step 6 (after_icache -> STAGE_LOADER_AFTER_ICACHE)
    * Line 151: Step 7 (before_bx -> STAGE_LOADER_BEFORE_BX)
  - tools/build_candidate_port25_ladder_fix.py:90-128:
    generate_boot_prototype_ladder_c() stage injection replacements injecting
    22 CORE_LADDER_PULSE_xx macro calls into boot_prototype.c:
    * Lines 110-114: Codes 11, 12, 13, 14, 15 (Core Group 1: Pre-Kernel & Trampoline)
    * Lines 115-119: Codes 21, 22, 23, 24, 25, 26 (Core Group 2: Startup Creation & Power Checks)
    * Lines 101-102: Codes 28, 29 (Native Power-Cut Failure Path for G3X_POWERON_FIX=0)
    * Lines 120-124: Codes 31, 32, 33, 34, 35 (Core Group 3: task_Startup_my Pre-Watchdog)
    * Lines 124-126: Codes 41, 42, 43, 44 (Core Group 4: task_Startup_my Post-Watchdog Arming)
  - chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266:
    Macro definitions for framed two-digit LED pulse sequences:
    #define CORE_LADDER_PULSE_<XY> CORE_LADDER_FRAME(X, Y)
     tens * 10 + units == code (asserted by runtime check)
  - chdk-port/platform/g3x/sub/110c/boot_prototype.c:436-438 [VERIFIED]:
    Continuation handoff branch to sub_fc0d0126 following Code 44:
    "    pop.w   {r4, lr}\n"
    "    b.w     sub_fc0d0126\n"
- Architectural Specification & Canonical Symbol Mapping:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354 (Section 5 Stage-Code Table, Codes 1..7, 11..15, 21..26, 31..35, 41..44)
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:358-359 (Section 5.1 Native Power-Cut Failure Path, Codes 28 and 29)
  - docs/PORT25_SHORT_PRESS_LOCALISE.md:328-351 (Proposed Breadcrumb Placement in boot_prototype.c)
  - docs/PORT25_OWNER_TRIAL_PLAN.md:199-233 (Owner Reading Table: Mapping LED Codes to Stages and T2 Candidates)
- Expected Combined Candidate DISKBOOT SHA-256:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:385 ("9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15")
  - docs/PORT25_OWNER_TRIAL_PLAN.md:30, 51, 81 (Expected candidate size: 124,865 bytes)

Code Range & Classes:
- Valid Table Code Classes (exactly 29 codes):
  * Loader (7 codes): CODE_1, CODE_2, CODE_3, CODE_4, CODE_5, CODE_6, CODE_7
  * Core Group 1 (5 codes): CODE_11, CODE_12, CODE_13, CODE_14, CODE_15
  * Core Group 2 (6 codes): CODE_21, CODE_22, CODE_23, CODE_24, CODE_25, CODE_26
  * Native Power-Cut Fail Path (2 codes): CODE_28, CODE_29
  * Core Group 3 (5 codes): CODE_31, CODE_32, CODE_33, CODE_34, CODE_35
  * Core Group 4 (4 codes): CODE_41, CODE_42, CODE_43, CODE_44
- Special Trial Classes:
  * NO_PULSES: Zero pulses observed (only exact case-insensitive string 'none').
    last_stage_reached and next_stage are set to 'UNKNOWN (no LED evidence)'.
    Notes echo observed press, lcd, and inspector_status verbatim, record that no ladder
    checkpoint was observed (VERIFIED from report), and flag any conflict if LCD indicates stock UI
    or backlight illumination with zero pulses observed (labelled UNKNOWN).
  * UNKNOWN_CODE: Pulse counts not registered in the 29-code table, out-of-range counts,
    or invalid inputs (missing pulses, empty value, floats, bools, non-numeric strings, <= 0).
  * AMBIGUOUS: Conflicting multiple counts reported, or a count adjacent to two valid codes with owner uncertainty.
  * INVALID_CANDIDATE: Candidate DISKBOOT SHA-256 does not match the expected combined-candidate digest.
  * CONTROL_HELD_O1: Held button press that affirmatively boots into the stock user interface.

Stock-UI Detection Rules (CONTROL_HELD_O1):
- Requires press == 'held'.
- LCD status is normalised to a closed enum: LcdState {stock_ui, off, backlight_off, on_no_ui, unknown}.
- Only exact, case-insensitive matches against this small, documented allowlist map to stock_ui:
  'stock_ui', 'stock ui', 'reached stock ui', 'stock ui reached', 'stock ui shown',
  'live_view', 'live view', 'shooting', 'shooting screen', 'canon_ui', 'canon ui',
  'menu', 'menu shown'.
- Any other text, including hedging, questioning, or negation words
  (e.g., 'maybe reached stock UI', 'unknown whether stock UI appeared', 'waiting for stock UI',
  'not stock UI', 'stock UI?', 'possibly stock ui') maps to LcdState.UNKNOWN.
- CONTROL_HELD_O1 requires press == 'held' AND lcd == 'stock_ui'.
- A held press with lcd not affirmatively stock UI (including unknown) yields an explicit note
  ('lcd state not affirmatively stock UI'), never CONTROL_HELD_O1.
- inspector_status alone (e.g. WITNESS_INVALID) never implies stock UI.
- A short press with affirmative stock-UI text does NOT yield CONTROL_HELD_O1 (held press is strictly required).

Pulse Input Validation Rules:
- 'none' (case-insensitive, exact) is the ONLY value that gives NO_PULSES.
- Missing pulses field, empty value, 'unknown', '?', non-numeric strings, floats (e.g. 24.9),
  booleans (True/False), negative numbers, or zero are classified as UNKNOWN_CODE with descriptive notes.
- Accept only real integers or strings of decimal digits, plus lists of those.
- Floats, bools, and non-numeric strings never become NO_PULSES or CODE_xx.

Code 44 Next Stage Rules:
- Code 44 next_stage is 'sub_fc0d0126' (the documented continuation handoff branch,
  citing boot_prototype.c:436-438 [VERIFIED]), never 'STOCK_BOOT_SUCCESS'.
- A boot-success claim may come only from independent affirmative UI evidence matching the allow-list,
  and is recorded in notes, never in next_stage.

Off-By-One Uncertainty Rule (AMBIGUOUS Classification):
- Evaluated using closed enum CountConfidence {exact, uncertain, unknown} and boolean aliases in a shared normalizer:
  * 'count_confidence': exact|certain|confident|high|sure -> exact (False); uncertain|approx|approximate|unsure|maybe|low -> uncertain (True)
  * 'uncertain': true|false
  * 'uncertainty': true|false
- Uncertainty aliases combined with OR semantics:
  * If any alias is affirmatively true, or count_confidence is 'uncertain' or 'unknown', report is uncertain.
  * If aliases conflict (one true, one false), uncertain=True is kept with an explicit note.
  * If an alias value is not a recognised boolean, it is treated as uncertain (never false) with an explicit note.
  * Result is strictly deterministic and invariant to field order or input format (JSON vs key=value).
- If no explicit field is present, free-text in 'notes' is checked clause-by-clause
  (clauses split by ';', '.', ',', '!', '?', newline).
  An affirmative uncertainty phrase ('unsure', 'uncertain', 'uncertainty', 'maybe', 'approx', '+/-1',
  'might have been') triggers uncertainty ONLY IF NO negation token ('not', 'no', 'never', "didn't",
  'did not', 'without', 'failed', "n't") appears in the same clause.
  Negated phrases like 'count is not uncertain' or 'no uncertainty; counted exactly 24' do NOT flag uncertainty.
- The rule triggers IF AND ONLY IF:
  1. The owner trial report flags uncertainty (via explicit flag or affirmative clause); AND
  2. The reported pulse count C is adjacent to TWO valid codes in the source table:
     both (C - 1) in LADDER_STAGE_TABLE and (C + 1) in LADDER_STAGE_TABLE.
- Counts with two valid neighbours: 2..6, 12..14, 22..25, 32..34, 42..43, and gap 27.
- Counts with at most one valid neighbour: 1, 7, 11, 15, 21, 26, 28, 29, 31, 35, 41, 44,
  and isolated in-range gaps. These do NOT trigger AMBIGUOUS.

Duplicate Key Governance:
- Duplicate keys with conflicting values in key=value or JSON format produce AMBIGUOUS
  with an explicit explanatory note; last-wins overwriting is strictly prohibited.

Phase 0 Path Safety Governance:
- Pure Python standard library only.
- Strict single entry-point safe_open_report(path) -> text:
  (a) Refuses any path whose string representation differs from path.strip(), or that contains NUL or control characters;
  (b) Refuses if the given name OR os.path.realpath(path) has a basename starting with PRIMARY
      (case-insensitive) or a suffix of .bin/.rom (case-insensitive, after any trailing dots or spaces);
  (c) Opens the realpath value that was checked in (b), never the original argument.
- No other code path calls open() on a report path.
- All safety checks execute before any open(). All files opened in text mode.
- Reads no ROM or binary files.
"""

from __future__ import annotations

import argparse
import ast
from enum import Enum
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pinned expected SHA-256 for PORT-25 combined candidate DISKBOOT.BIN
# Citation: docs/PORT25_LADDER_FIX_CANDIDATE.md:385, docs/PORT25_OWNER_TRIAL_PLAN.md:30
EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256 = (
    "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
)
EXPECTED_PORT25_COMBINED_DISKBOOT_SIZE = 124865

# Comprehensive ladder stage-code table (exactly 29 codes)
# Primary source: docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354, 358-359
# Build sources:
#   - chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:43-154 (Codes 1..7)
#   - tools/build_candidate_port25_ladder_fix.py:90-128 (Codes 11..15, 21..26, 28..29, 31..35, 41..44)
#   - chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266 (CORE_LADDER_PULSE_xx macro definitions)
#   - chdk-port/platform/g3x/sub/110c/boot_prototype.c:436-438 (Continuation branch to sub_fc0d0126)
LADDER_STAGE_TABLE: Dict[int, Dict[str, Any]] = {
    # Loader stages (1-7)
    1: {
        "code": 1,
        "stage_symbol": "STAGE_LOADER_AFTER_PROLOGUE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:45",
        "candidate_line": 328,
        "timing_state": "Pre-Arming",
        "purpose": "Step 1: Entry prologue and check_compat() completed",
        "adjacent_call": "check_compat",
        "call_position": "after",
        "order_index": 1,
    },
    2: {
        "code": 2,
        "stage_symbol": "STAGE_LOADER_AFTER_COPY",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:99",
        "candidate_line": 329,
        "timing_state": "Pre-Arming",
        "purpose": "Step 2: Core payload copied to 0x003489B4",
        "adjacent_call": "core_copy",
        "call_position": "after",
        "order_index": 2,
    },
    3: {
        "code": 3,
        "stage_symbol": "STAGE_LOADER_BEFORE_DCACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:116",
        "candidate_line": 330,
        "timing_state": "Pre-Arming",
        "purpose": "Step 3: Immediately before ROM D-cache clean/invalidate (0xFC127AB1)",
        "adjacent_call": "ROM_DCACHE_CLEAN_INV",
        "call_position": "before",
        "order_index": 3,
    },
    4: {
        "code": 4,
        "stage_symbol": "STAGE_LOADER_AFTER_DCACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:127",
        "candidate_line": 331,
        "timing_state": "Pre-Arming",
        "purpose": "Step 4: D-cache clean/invalidate completed",
        "adjacent_call": "ROM_DCACHE_CLEAN_INV",
        "call_position": "after",
        "order_index": 4,
    },
    5: {
        "code": 5,
        "stage_symbol": "STAGE_LOADER_BEFORE_ICACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:132",
        "candidate_line": 332,
        "timing_state": "Pre-Arming",
        "purpose": "Step 5: Immediately before ROM I-cache invalidate (0xFC127B09)",
        "adjacent_call": "ROM_ICACHE_INV_BP",
        "call_position": "before",
        "order_index": 5,
    },
    6: {
        "code": 6,
        "stage_symbol": "STAGE_LOADER_AFTER_ICACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:144",
        "candidate_line": 333,
        "timing_state": "Pre-Arming",
        "purpose": "Step 6: I-cache invalidate completed",
        "adjacent_call": "ROM_ICACHE_INV_BP",
        "call_position": "after",
        "order_index": 6,
    },
    7: {
        "code": 7,
        "stage_symbol": "STAGE_LOADER_BEFORE_BX",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:152",
        "candidate_line": 334,
        "timing_state": "Pre-Arming",
        "purpose": "Step 7: Final loader step immediately before bx r0 to core (0x003489B5)",
        "adjacent_call": "bx r0",
        "call_position": "before",
        "order_index": 7,
    },
    # Core Group 1: Pre-Kernel & Trampoline (11-15) - Reset Thread / Initial Task
    11: {
        "code": 11,
        "stage_symbol": "STAGE_BC_CORE_ENTRY",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:92",
        "candidate_line": 335,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to core boot() immediately after SP reset (mov sp, r0)",
        "adjacent_call": "mov sp, r0",
        "call_position": "after",
        "order_index": 8,
    },
    12: {
        "code": 12,
        "stage_symbol": "STAGE_BC_POST_BSS",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:154",
        "candidate_line": 336,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Low/High RAM copies and Canon BSS zeroing completed",
        "adjacent_call": "loc_zero_bss",
        "call_position": "after",
        "order_index": 9,
    },
    13: {
        "code": 13,
        "stage_symbol": "STAGE_BC_STAGE3_ENTRY",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:175",
        "candidate_line": 337,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to sub_fc05b3c8_my immediately after witness_record_core",
        "adjacent_call": "witness_record_core",
        "call_position": "after",
        "order_index": 10,
    },
    14: {
        "code": 14,
        "stage_symbol": "STAGE_BC_PRE_KERNEL_INIT",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:256",
        "candidate_line": 338,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: DryOS memory descriptors initialized; immediately before blx sub_fc31b408",
        "adjacent_call": "sub_fc31b408",
        "call_position": "before",
        "order_index": 11,
    },
    15: {
        "code": 15,
        "stage_symbol": "STAGE_BC_STAGE4_ENTRY",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:272",
        "candidate_line": 339,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to sub_fc05b558_my (Initial Task) after push {r4, lr}",
        "adjacent_call": "sub_fc05b558_my",
        "call_position": "after",
        "order_index": 12,
    },
    # Core Group 2: Stage 5 Startup Creation & Power Checks (21-26) - Initial Task
    21: {
        "code": 21,
        "stage_symbol": "STAGE_BC_STAGE5_ENTRY",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:346",
        "candidate_line": 340,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to sub_fc05b962_my after push {r3, lr}",
        "adjacent_call": "sub_fc05b962_my",
        "call_position": "after",
        "order_index": 13,
    },
    22: {
        "code": 22,
        "stage_symbol": "STAGE_BC_PRE_MPU_SETUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:347",
        "candidate_line": 341,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before bl sub_fc05ba68 (pxSetup, dhcpc_setup, mpuSetup)",
        "adjacent_call": "sub_fc05ba68",
        "call_position": "before",
        "order_index": 14,
    },
    23: {
        "code": 23,
        "stage_symbol": "STAGE_BC_POST_MPU_SETUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:347",
        "candidate_line": 342,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately after bl sub_fc05ba68; proves setup calls returned",
        "adjacent_call": "sub_fc05ba68",
        "call_position": "after",
        "order_index": 15,
    },
    24: {
        "code": 24,
        "stage_symbol": "STAGE_BC_PRE_POWER_CHECK",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:348",
        "candidate_line": 343,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately after bl sub_fc079404, before button check sub_fc1284ac",
        "adjacent_call": "sub_fc079404",
        "call_position": "after",
        "order_index": 16,
    },
    25: {
        "code": 25,
        "stage_symbol": "STAGE_BC_POWER_CHECK_PASS",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:361",
        "candidate_line": 344,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Label loc_fc05b978; button check passed or bypassed via G3X_POWERON_FIX",
        "adjacent_call": "loc_fc05b978",
        "call_position": "after",
        "order_index": 19,
    },
    26: {
        "code": 26,
        "stage_symbol": "STAGE_BC_PRE_CREATE_STARTUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:373",
        "candidate_line": 345,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before blx sub_fc31bbc4 (DryOS CreateTask 'Startup')",
        "adjacent_call": "0xfc05b9a0",
        "call_position": "after",
        "order_index": 20,
    },
    # Native Power-Cut Failure Path (G3X_POWERON_FIX=0)
    28: {
        "code": 28,
        "stage_symbol": "STAGE_BC_FAIL_POWER_CUT",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:357",
        "candidate_line": 358,
        "timing_state": "Pre-Arming",
        "purpose": "Flashes if sub_fc1284ac returned 0, immediately before bl sub_fc05ba56 cuts power",
        "adjacent_call": "sub_fc05ba56",
        "call_position": "before",
        "order_index": 17,
    },
    29: {
        "code": 29,
        "stage_symbol": "STAGE_BC_HALT_SHUTDOWN",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:358",
        "candidate_line": 359,
        "timing_state": "Pre-Arming",
        "purpose": "Flashes at label loc_fc05b976 if sub_fc05ba56 returns without immediate cut",
        "adjacent_call": "loc_fc05b976",
        "call_position": "after",
        "order_index": 18,
    },
    # Core Group 3: task_Startup_my Pre-Watchdog (31-35) - Startup Task
    31: {
        "code": 31,
        "stage_symbol": "STAGE_BC_STARTUP_ENTRY",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:389",
        "candidate_line": 346,
        "timing_state": "Pre-Arming",
        "purpose": "Task-Execution Checkpoint: First frame emitted by created task (Startup entry)",
        "adjacent_call": "task_Startup_my",
        "call_position": "after",
        "order_index": 21,
    },
    32: {
        "code": 32,
        "stage_symbol": "STAGE_BC_POST_EARLY_INIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:393",
        "candidate_line": 347,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Early driver calls (sub_fc0d0150..sub_fc418eec) returned",
        "adjacent_call": "sub_fc418eec",
        "call_position": "after",
        "order_index": 22,
    },
    33: {
        "code": 33,
        "stage_symbol": "STAGE_BC_PRE_SD1STINIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:402",
        "candidate_line": 348,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before SD1stInit gate check sub_fc05c4e0",
        "adjacent_call": "sub_fc05c4e0",
        "call_position": "before",
        "order_index": 23,
    },
    34: {
        "code": 34,
        "stage_symbol": "STAGE_BC_POST_SD1STINIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:407",
        "candidate_line": 349,
        "timing_state": "Pre-Arming",
        "purpose": "Helper-Return Checkpoint: Label 1: after SD1stInit task creation veneer",
        "adjacent_call": "sub_fc31b1f4",
        "call_position": "after",
        "order_index": 24,
    },
    35: {
        "code": 35,
        "stage_symbol": "STAGE_BC_PRE_WATCHDOG_START",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:413",
        "candidate_line": 350,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before bl sub_fc418f2a (watchdog arming helper)",
        "adjacent_call": "sub_fc418f2a",
        "call_position": "before",
        "order_index": 25,
    },
    # Core Group 4: task_Startup_my Post-Watchdog & Continuation (41-44) - POST-ARMING
    41: {
        "code": 41,
        "stage_symbol": "STAGE_BC_POST_WATCHDOG_START",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:413",
        "candidate_line": 351,
        "timing_state": "POST-ARMING",
        "purpose": "Checkpoint: Immediately after bl sub_fc418f2a; watchdog is actively armed",
        "adjacent_call": "sub_fc418f2a",
        "call_position": "after",
        "order_index": 26,
    },
    42: {
        "code": 42,
        "stage_symbol": "STAGE_BC_PRE_PHYSW_CREATE",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:418",
        "candidate_line": 352,
        "timing_state": "POST-ARMING",
        "purpose": "Checkpoint: Immediately before bl sub_fc1283d2 (task_PhySw launcher helper)",
        "adjacent_call": "sub_fc1283d2",
        "call_position": "before",
        "order_index": 27,
    },
    43: {
        "code": 43,
        "stage_symbol": "STAGE_BC_POST_PHYSW_CREATE",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:418",
        "candidate_line": 353,
        "timing_state": "POST-ARMING",
        "purpose": "Helper-Return Checkpoint: sub_fc1283d2 returned (does NOT prove task_PhySw ran)",
        "adjacent_call": "sub_fc1283d2",
        "call_position": "after",
        "order_index": 28,
    },
    44: {
        "code": 44,
        "stage_symbol": "STAGE_BC_PRE_FIRMWARE_CONT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:442",
        "candidate_line": 354,
        "timing_state": "POST-ARMING",
        "purpose": "Checkpoint: Immediately before pop.w {r4, lr}; b.w sub_fc0d0126 (stock handoff)",
        "adjacent_call": "sub_fc0d0126",
        "call_position": "before",
        "order_index": 29,
    },
}

# Next expected execution stage map following each table checkpoint.
# For Code 44, the documented continuation is the handoff branch to sub_fc0d0126
# [VERIFIED: boot_prototype.c:436-438].
def derive_next_stage_map(table: Dict[int, Dict[str, Any]]) -> Dict[int, Optional[str]]:
    """Derives next expected stage map directly from the provided stage table."""
    mapping: Dict[int, Optional[str]] = {}
    normal_codes = [
        1, 2, 3, 4, 5, 6, 7,
        11, 12, 13, 14, 15,
        21, 22, 23, 24, 25, 26,
        31, 32, 33, 34, 35,
        41, 42, 43, 44,
    ]
    for i, c in enumerate(normal_codes):
        if c == 44:
            mapping[c] = "sub_fc0d0126"
        elif i + 1 < len(normal_codes):
            next_c = normal_codes[i + 1]
            mapping[c] = table[next_c]["stage_symbol"] if next_c in table else None
        else:
            mapping[c] = None

    if 28 in table and 29 in table:
        mapping[28] = table[29]["stage_symbol"]
    elif 28 in table:
        mapping[28] = None
    if 29 in table:
        mapping[29] = None

    return mapping


NEXT_STAGE_MAP: Dict[int, Optional[str]] = derive_next_stage_map(LADDER_STAGE_TABLE)

# All valid trial classification categories: exactly 29 CODE_<N> classes plus 5 special categories
VALID_CLASSES: Set[str] = {
    *(f"CODE_{c}" for c in LADDER_STAGE_TABLE),
    "NO_PULSES",
    "UNKNOWN_CODE",
    "AMBIGUOUS",
    "INVALID_CANDIDATE",
    "CONTROL_HELD_O1",
}

# Documented allow-list of affirmative LCD states indicating stock UI reached.
# Citations: docs/PORT24_POWERON_FIX.md:19-24, docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55,
#            docs/PORT25_OWNER_TRIAL_PLAN.md:162-173
STOCK_UI_LCD_ALLOWLIST: Set[str] = {
    "stock_ui",
    "stock ui",
    "reached stock ui",
    "stock ui reached",
    "stock ui shown",
    "live_view",
    "live view",
    "shooting",
    "shooting screen",
    "canon_ui",
    "canon ui",
    "menu",
    "menu shown",
}


class LcdState(str, Enum):
    """Closed enum for normalized LCD display states."""
    STOCK_UI = "stock_ui"
    OFF = "off"
    BACKLIGHT_OFF = "backlight_off"
    ON_NO_UI = "on_no_ui"
    UNKNOWN = "unknown"


def normalize_lcd_state(lcd_val: Any) -> LcdState:
    """Normalises raw LCD status into a closed LcdState enum.

    Only exact, case-insensitive matches against the documented allowlist
    map to LcdState.STOCK_UI. Any other text, including anything with hedging,
    questioning, or negation words, maps to LcdState.UNKNOWN.
    """
    if lcd_val is None:
        return LcdState.UNKNOWN
    clean = re.sub(r"\s+", " ", str(lcd_val).strip().lower())
    if not clean:
        return LcdState.UNKNOWN
    if clean in STOCK_UI_LCD_ALLOWLIST:
        return LcdState.STOCK_UI
    if clean in ("off", "dark", "black", "blank"):
        return LcdState.OFF
    if clean in ("backlight_off", "backlight off"):
        return LcdState.BACKLIGHT_OFF
    if clean in (
        "on_no_ui", "on no ui", "on_without_ui", "backlight_on", "backlight on",
        "backlight-on", "illuminated", "backlight", "screen on", "display on",
        "screen illuminated", "display illuminated", "illuminated lcd",
        "an illuminated lcd", "backlight-on lcd",
    ):
        return LcdState.ON_NO_UI
    return LcdState.UNKNOWN


def check_no_pulses_lcd_conflict(raw_lcd: Any) -> Optional[str]:
    """Checks if the reported LCD state conflicts with observing zero LED pulses.

    If lcd indicates stock UI or backlight was reached with zero pulses, returns an
    explanatory conflict description labelled UNKNOWN. Never explains the conflict away.
    """
    if raw_lcd is None:
        return None
    clean = re.sub(r"\s+", " ", str(raw_lcd).strip().lower())
    if not clean:
        return None

    # Check for negation tokens: if negated, no affirmative conflict
    # (e.g. "not stock UI", "no backlight", "backlight off", "off", "dark", etc.)
    negation_match = re.search(r"\b(not|no|never|without|off|failed|dark|blank|black)\b", clean)
    if negation_match and clean not in ("on_no_ui", "on no ui", "on_without_ui"):
        return None

    if clean in STOCK_UI_LCD_ALLOWLIST or normalize_lcd_state(clean) == LcdState.STOCK_UI:
        return "lcd indicates stock UI was reached with zero LED pulses observed"

    if clean in (
        "on_no_ui", "on no ui", "on_without_ui", "backlight_on", "backlight on",
        "backlight-on", "illuminated", "backlight", "screen on", "display on",
        "screen illuminated", "display illuminated", "illuminated lcd",
        "an illuminated lcd", "backlight-on lcd",
    ):
        return "lcd indicates active backlight/illumination with zero LED pulses observed"

    if re.search(r"\b(backlight|illuminat\w*|screen on|display on)\b", clean):
        return "lcd indicates active backlight/illumination with zero LED pulses observed"

    return None


def is_affirmative_stock_ui(lcd_str: str) -> bool:
    """Explicit affirmative check for stock user interface on the LCD.

    Returns True if and only if normalize_lcd_state(lcd_str) == LcdState.STOCK_UI.
    No free-text regex heuristics are used.
    """
    return normalize_lcd_state(lcd_str) == LcdState.STOCK_UI


class CountConfidence(str, Enum):
    """Closed enum for explicit count confidence levels."""
    EXACT = "exact"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


def normalize_count_confidence(conf_val: Any) -> CountConfidence:
    """Normalises explicit count confidence into a closed CountConfidence enum."""
    if conf_val is None:
        return CountConfidence.UNKNOWN
    clean = re.sub(r"\s+", " ", str(conf_val).strip().lower())
    if clean in ("exact", "certain", "confident", "high", "sure"):
        return CountConfidence.EXACT
    if clean in ("uncertain", "approx", "approximate", "unsure", "maybe", "low"):
        return CountConfidence.UNCERTAIN
    return CountConfidence.UNKNOWN


UNCERTAINTY_WORDS = re.compile(
    r"\b(unsure|uncertain|uncertainty|maybe|approx|approximate|approximately|might\s+have\s+been|could\s+have\s+been)\b|\+\s*/\s*-\s*1|\+-\s*1",
    re.IGNORECASE,
)
CLAUSE_NEGATION = re.compile(
    r"\b(never|not|no|without|failed|did\s+not|didnt)\b|\b\w*n['’]t\b",
    re.IGNORECASE,
)


class SafetyViolationError(ValueError):
    """Raised when an access to a forbidden file path (.bin, .rom, PRIMARY*, symlinks) is attempted."""
    pass


def is_forbidden_file_name(name: Union[str, Path]) -> bool:
    """Checks if a file name or path violates Phase 0 safety rules (case-insensitive).

    Refuses if the basename starts with PRIMARY (case-insensitive) or if
    the basename/suffix ends in .bin or .rom (case-insensitive, after any trailing dots or spaces).
    """
    name_str = os.fspath(name) if not isinstance(name, str) else name
    base = os.path.basename(name_str)
    if base.upper().startswith("PRIMARY"):
        return True
    clean_base = base.rstrip(". ")
    clean_name = name_str.rstrip(". ")
    if clean_base.lower().endswith((".bin", ".rom")) or clean_name.lower().endswith((".bin", ".rom")):
        return True
    return False


def validate_safety_path(path: Union[str, Path]) -> str:
    """Enforces Phase 0 read-only safety rules on input file paths without normalising:

    (a) Refuses any path whose string representation differs from path.strip(), or that
        contains NUL or control characters.
    (b) Refuses if the given name OR os.path.realpath(path) has a basename starting with PRIMARY
        (case-insensitive) or a suffix of .bin/.rom (case-insensitive, after any trailing dots or spaces).

    Returns the checked realpath string.
    """
    path_str = os.fspath(path) if not isinstance(path, str) else path

    # (a) Refuse whitespace alteration or control characters
    if path_str != path_str.strip():
        raise SafetyViolationError(
            f"Safety violation: refused path with leading or trailing whitespace: {path_str!r}"
        )
    if any(ord(c) < 32 or ord(c) == 127 for c in path_str):
        raise SafetyViolationError(
            f"Safety violation: refused path containing control characters or NUL: {path_str!r}"
        )

    # (b) Check given name
    if is_forbidden_file_name(path_str):
        raise SafetyViolationError(
            f"Safety violation: forbidden access to file '{path_str}'"
        )

    # Check os.path.realpath
    try:
        real_p = os.path.realpath(path_str)
    except OSError as err:
        raise SafetyViolationError(f"Safety violation: cannot resolve path '{path_str}': {err}")

    if is_forbidden_file_name(real_p):
        raise SafetyViolationError(
            f"Safety violation: resolved path '{real_p}' violates safety rules"
        )

    # Check parent components of real_p
    p_real = Path(real_p)
    for parent in p_real.parents:
        if is_forbidden_file_name(parent.name):
            raise SafetyViolationError(
                f"Safety violation: resolved parent component '{parent.name}' in '{real_p}' violates safety rules"
            )

    return real_p


def safe_open_report(path: Union[str, Path]) -> str:
    """Safely opens and reads an owner trial report text file.

    Enforces Phase 0 read-only safety rules on the exact string given, with no stripping or normalising:
    (a) Refuses any path whose string differs from path.strip(), or that contains NUL or control characters;
    (b) Refuses if the given name OR os.path.realpath(path) has a basename starting with PRIMARY
        (case-insensitive) or a suffix of .bin/.rom (case-insensitive, after any trailing dots or spaces);
    (c) Opens the realpath value that was checked in (b), never the original argument.

    No other code path may call open() on a report path.
    Refuses any binary content containing NUL bytes.
    """
    real_path = validate_safety_path(path)
    if not os.path.exists(real_path):
        raise FileNotFoundError(f"Report file not found: {path}")
    if not os.path.isfile(real_path):
        raise SafetyViolationError(f"Safety violation: '{real_path}' is not a regular file")

    with open(real_path, "r", encoding="utf-8") as f:
        text = f.read()

    if "\x00" in text:
        raise SafetyViolationError(f"Safety violation: refused binary content in '{real_path}'")
    return text


def is_truthy(val: Any) -> bool:
    """Evaluates whether a value represents boolean True.
    
    Correctly recognizes explicit boolean False, and strings like 'false', '0', 'no', 'none', 'null' as False.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "yes", "1", "t", "y"):
            return True
        if v in ("false", "no", "0", "f", "n", "", "none", "null"):
            return False
    return False


def has_affirmative_uncertainty_in_text(text: str) -> bool:
    """Evaluates free-text notes for affirmative owner uncertainty.
    
    Rule & Governance:
    - Splits text into clauses by punctuation (;, ., ,, !, ?, newline).
    - Requires an affirmative uncertainty phrase:
      'unsure', 'uncertain', 'uncertainty', 'maybe', 'approx', 'approximate',
      'approximately', '+/-1', '+-1', 'might have been', 'could have been'.
    - Requires that NO negation token ('not', 'no', 'never', 'without', 'failed',
      "didn't", 'did not', "n't") appears in the same clause.
    """
    if not text:
        return False
    clauses = re.split(r"[;.,!?\n]+", text)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        if UNCERTAINTY_WORDS.search(clause) and not CLAUSE_NEGATION.search(clause):
            return True
    return False


def parse_recognized_boolean(val: Any) -> Optional[bool]:
    """Evaluates whether a value represents a recognized boolean.
    
    Returns:
      True if value represents boolean True.
      False if value represents boolean False.
      None if value is NOT a recognized boolean (e.g. 'maybe', 42, None, etc.).
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        if val == 1:
            return True
        if val == 0:
            return False
        return None
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "yes", "1", "t", "y", "on"):
            return True
        if v in ("false", "no", "0", "f", "n", "off"):
            return False
        return None
    return None


def normalize_uncertainty(
    aliases: Sequence[Tuple[str, Any]],
    notes_text: str = "",
) -> Tuple[bool, List[str]]:
    """Normalises uncertainty across all uncertainty aliases and notes in a shared function.
    
    Collects every alias present ('uncertain', 'uncertainty', and 'count_confidence' if it applies)
    and combines them with OR semantics:
    - If any alias is affirmatively true, or count_confidence is 'uncertain' or 'unknown',
      the report is uncertain.
    - If the aliases conflict (one true, one false), keeps uncertain=True and adds a note that says so.
    - If an alias value is not a recognised boolean, treats the report as uncertain and adds a note.
      Never treats it as false.
    - The result does not depend on field order or input format.
    - If no explicit aliases are present, checks free-text in notes.
    """
    notes_out: List[str] = []
    has_affirmative_true = False
    has_affirmative_false = False
    unrecognized_notes: List[str] = []

    for name, val in aliases:
        name_lower = name.strip().lower()
        if name_lower in ("uncertain", "uncertainty"):
            b = parse_recognized_boolean(val)
            if b is True:
                has_affirmative_true = True
            elif b is False:
                has_affirmative_false = True
            else:
                has_affirmative_true = True
                unrecognized_notes.append(
                    f"unrecognised boolean value for uncertainty alias '{name}': {val!r}; treated as uncertain."
                )
        elif name_lower == "count_confidence":
            conf = normalize_count_confidence(val)
            if conf == CountConfidence.EXACT:
                has_affirmative_false = True
            elif conf in (CountConfidence.UNCERTAIN, CountConfidence.UNKNOWN):
                has_affirmative_true = True

    if unrecognized_notes:
        for un in sorted(list(dict.fromkeys(unrecognized_notes))):
            notes_out.append(un)

    if aliases:
        if has_affirmative_true and has_affirmative_false:
            is_uncertain = True
            notes_out.append(
                "conflicting uncertainty alias values provided; resolved to uncertain=True per OR semantics."
            )
        elif has_affirmative_true:
            is_uncertain = True
        else:
            is_uncertain = False
    else:
        is_uncertain = has_affirmative_uncertainty_in_text(notes_text)

    return is_uncertain, notes_out


def parse_pulses_value(val: Any) -> Any:
    """Parses raw pulses input from string, list, or scalar into resolved pulses representation."""
    if isinstance(val, str):
        v_stripped = val.strip()
        v_lower = v_stripped.lower()
        if v_lower == "none":
            return "none"
        if v_stripped.startswith("[") and v_stripped.endswith("]"):
            inner = v_stripped[1:-1].strip()
            if "," in inner:
                items = [x.strip() for x in inner.split(",") if x.strip()]
            else:
                items = [x.strip() for x in inner.split() if x.strip()]
            parsed_list: List[Any] = []
            for item in items:
                if re.fullmatch(r"[-+]?[0-9]+", item):
                    parsed_list.append(int(item))
                else:
                    parsed_list.append(item)
            return parsed_list
        if "," in v_stripped:
            items = [x.strip() for x in v_stripped.split(",") if x.strip()]
            parsed_list = []
            for item in items:
                if re.fullmatch(r"[-+]?[0-9]+", item):
                    parsed_list.append(int(item))
                else:
                    parsed_list.append(item)
            return parsed_list
        if " " in v_stripped and re.match(r"^[-+]?[0-9\s]+$", v_stripped):
            items = [x.strip() for x in v_stripped.split() if x.strip()]
            return [int(item) for item in items]
        if re.fullmatch(r"[-+]?[0-9]+", v_stripped):
            return int(v_stripped)
        return v_stripped
    return val


def parse_sequence_value(val: Any) -> Any:
    """Parses raw sequence input from string, list, or scalar into a resolved sequence list."""
    if isinstance(val, str):
        v_stripped = val.strip()
        if v_stripped.lower() == "none":
            return "none"
        if v_stripped.startswith("[") and v_stripped.endswith("]"):
            v_stripped = v_stripped[1:-1].strip()
        if "," in v_stripped:
            items = [x.strip() for x in v_stripped.split(",") if x.strip()]
        else:
            items = [x.strip() for x in v_stripped.split() if x.strip()]
        parsed_list: List[Any] = []
        for item in items:
            if re.fullmatch(r"[-+]?[0-9]+", item):
                parsed_list.append(int(item))
            else:
                parsed_list.append(item)
        return parsed_list
    elif isinstance(val, list):
        parsed_list = []
        for item in val:
            if isinstance(item, bool):
                parsed_list.append(item)
            elif isinstance(item, int):
                parsed_list.append(item)
            elif isinstance(item, str) and re.fullmatch(r"[-+]?[0-9]+", item.strip()):
                parsed_list.append(int(item.strip()))
            else:
                parsed_list.append(item)
        return parsed_list
    return val


def parse_header_pulse_digits(header_content: str) -> Dict[int, Tuple[int, int]]:
    """Parses the actual CORE_LADDER_FRAME(tens, units) digits for every pulse macro in led_breadcrumb.h.
    
    Returns a dict mapping integer code -> (tens, units).
    """
    frame_defs: Dict[str, Tuple[int, int]] = {}
    for m in re.finditer(
        r"#define\s+([A-Za-z0-9_]+)\s+CORE_LADDER_FRAME\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        header_content,
    ):
        name = m.group(1)
        tens = int(m.group(2))
        units = int(m.group(3))
        frame_defs[name] = (tens, units)

    # Handle alias definitions like #define CORE_LADDER_PULSE_31 CHILD_LADDER_PULSE_31
    alias_defs: Dict[str, str] = {}
    for m in re.finditer(
        r"#define\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*$",
        header_content,
        re.MULTILINE,
    ):
        alias_defs[m.group(1)] = m.group(2)

    code_digits: Dict[int, Tuple[int, int]] = {}
    for name, (tens, units) in frame_defs.items():
        m_code = re.search(r"PULSE_(\d+)", name)
        if m_code:
            code = int(m_code.group(1))
            code_digits[code] = (tens, units)

    for alias, target in alias_defs.items():
        m_code = re.search(r"CORE_LADDER_PULSE_(\d+)", alias)
        if m_code and target in frame_defs:
            code = int(m_code.group(1))
            code_digits[code] = frame_defs[target]

    return code_digits


def extract_build_source_pulse_codes(
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extracts pulse codes and emit sites directly from the p25-t3b build source files.
    
    Citations:
      - Loader steps (1..7): chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:43-154
      - Macro injections (22 codes): tools/build_candidate_port25_ladder_fix.py:90-128
      - Framed timing macro defs: chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    loader_path = repo_root / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_main_breadcrumb.c"
    build_script_path = repo_root / "tools" / "build_candidate_port25_ladder_fix.py"
    header_path = repo_root / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h"

    validate_safety_path(loader_path)
    validate_safety_path(build_script_path)
    validate_safety_path(header_path)

    # 1. Parse loader ladder step checkpoints from loader_main_breadcrumb.c:43-154
    with open(loader_path, "r", encoding="utf-8") as f:
        loader_content = f.read()

    loader_steps: Dict[int, str] = {}
    blocks = re.findall(r"#if defined\(LED_LADDER\)(.*?)(?:#endif|#else)", loader_content, re.DOTALL)
    for b in blocks:
        m = re.search(r"//\s*Step\s*(\d+):\s*([a-zA-Z0-9_]+)", b)
        if m:
            step_num = int(m.group(1))
            step_name = m.group(2).upper()
            loader_steps[step_num] = f"STAGE_LOADER_{step_name}"

    # 2. Parse core injected pulse macros in tools/build_candidate_port25_ladder_fix.py:90-128
    with open(build_script_path, "r", encoding="utf-8") as f:
        build_content = f.read()

    core_injected_codes: List[int] = []
    m_func = re.search(r"def generate_boot_prototype_ladder_c\(\).*?return src", build_content, re.DOTALL)
    if m_func:
        func_body = m_func.group(0)
        core_injected_codes = sorted(set(int(x) for x in re.findall(r"CORE_LADDER_PULSE_(\d+)", func_body)))
    else:
        core_injected_codes = sorted(set(int(x) for x in re.findall(r"CORE_LADDER_PULSE_(\d+)", build_content)))

    # 3. Parse header framed pulse macro definitions in led_breadcrumb.h:217-266
    with open(header_path, "r", encoding="utf-8") as f:
        header_content = f.read()

    header_macro_codes: List[int] = sorted(set(
        int(m.group(1))
        for m in re.finditer(
            r"#define\s+(?:CORE|CHILD)_LADDER_PULSE_(\d+)\s+CORE_LADDER_FRAME\((\d+),\s*(\d+)\)",
            header_content,
        )
    ))

    all_emitted_codes = sorted(set(list(loader_steps.keys()) + core_injected_codes))

    return {
        "loader_steps": loader_steps,
        "core_injected_codes": core_injected_codes,
        "header_macro_codes": header_macro_codes,
        "all_emitted_codes": all_emitted_codes,
    }


def parse_core_emit_mapping_from_build_script(script_text: str) -> Dict[int, Dict[str, Any]]:
    """Parses core pulse code emit sites, relative positions, and order from build script content.
    
    Citations: tools/build_candidate_port25_ladder_fix.py:90-128
    """
    try:
        tree = ast.parse(script_text)
    except Exception as e:
        raise ValueError(f"Failed to parse build script AST: {e}")

    repl_pwr_val = None
    replacements_list = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "repl_pwr":
                        try:
                            repl_pwr_val = ast.literal_eval(node.value)
                        except Exception:
                            pass
                    elif target.id == "replacements":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                                    if (
                                        isinstance(elt.elts[0], ast.Name)
                                        and elt.elts[0].id == "target_pwr"
                                    ):
                                        replacements_list.append(("target_pwr", repl_pwr_val or ""))
                                    else:
                                        try:
                                            t = ast.literal_eval(elt.elts[0])
                                            r = ast.literal_eval(elt.elts[1])
                                            replacements_list.append((t, r))
                                        except Exception:
                                            pass

    core_mapping: Dict[int, Dict[str, Any]] = {}
    order_idx = 8  # Loader steps occupy order indices 1..7

    for target, repl in replacements_list:
        matches = list(re.finditer(r"CORE_LADDER_PULSE_(\d+)", repl))
        if not matches:
            continue

        for m in matches:
            c = int(m.group(1))
            c_pos = m.start()

            m_call = re.search(r"\b(bl|blx|b\.w)\s+([a-zA-Z0-9_]+)", repl)
            m_label = re.search(r"\b(loc_[a-zA-Z0-9_]+|1):", repl)
            m_push = re.search(r"push\s+\{r[34],\s*lr\}", repl)
            m_ldr = re.search(r"ldr\s+r0,\s*=(?:0x)?([a-zA-Z0-9_]+)", repl)
            m_sp = re.search(r"mov\s+sp,\s*r0", repl)
            m_blo = re.search(r"blo\s+([a-zA-Z0-9_]+)", repl)

            if c in (28, 29, 25):
                if c == 28:
                    adj = "sub_fc05ba56"
                    m_target = re.search(r"bl\s+sub_fc05ba56", repl)
                    pos = "before" if (m_target and c_pos < m_target.start()) else "after"
                elif c == 29:
                    adj = "loc_fc05b976"
                    m_target = re.search(r"loc_fc05b976:", repl)
                    pos = "before" if (m_target and c_pos < m_target.start()) else "after"
                elif c == 25:
                    adj = "loc_fc05b978"
                    m_target = re.search(r"loc_fc05b978:", repl)
                    pos = "before" if (m_target and c_pos < m_target.start()) else "after"
                else:
                    adj = "unknown"
                    pos = "unknown"
            elif m_call:
                adj = m_call.group(2)
                pos = "before" if c_pos < m_call.start() else "after"
            elif m_label:
                adj = m_label.group(1)
                pos = "before" if c_pos < m_label.start() else "after"
            elif m_push:
                m_fn = re.search(r"([a-zA-Z0-9_]+)\(void\)", repl)
                adj = m_fn.group(1) if m_fn else "push"
                pos = "before" if c_pos < m_push.start() else "after"
            elif m_ldr:
                adj = "0x" + m_ldr.group(1)
                pos = "before" if c_pos < m_ldr.start() else "after"
            elif m_sp:
                adj = "mov sp, r0"
                pos = "before" if c_pos < m_sp.start() else "after"
            elif m_blo:
                adj = m_blo.group(1)
                pos = "before" if c_pos < m_blo.start() else "after"
            else:
                adj = "unknown"
                pos = "unknown"

            core_mapping[c] = {
                "adjacent_call": adj,
                "position": pos,
                "order_index": order_idx,
            }
            order_idx += 1

    return core_mapping


def verify_source_consistency(
    header_content: Optional[str] = None,
    loader_content: Optional[str] = None,
    build_script_content: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validates full consistency between the build sources and the LADDER_STAGE_TABLE.
    
    Checks:
    1. Header macro digits: parses CORE_LADDER_FRAME(tens, units) for each code and
       asserts tens * 10 + units == code == table code.
    2. Loader emit sites: parses steps 1..7 in loader_main_breadcrumb.c and asserts
       the ordered step sequence, adjacent calls, relative positions, and stage symbol associations match the table.
    3. Core injected codes: parses emit sites and replacements in build_candidate_port25_ladder_fix.py
       and asserts each code's emit site, before/after position, order index, and stage association match the table.
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    if header_content is None:
        header_path = repo_root / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h"
        validate_safety_path(header_path)
        with open(header_path, "r", encoding="utf-8") as f:
            header_content = f.read()

    if loader_content is None:
        loader_path = repo_root / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_main_breadcrumb.c"
        validate_safety_path(loader_path)
        with open(loader_path, "r", encoding="utf-8") as f:
            loader_content = f.read()

    if build_script_content is None:
        build_script_path = repo_root / "tools" / "build_candidate_port25_ladder_fix.py"
        validate_safety_path(build_script_path)
        with open(build_script_path, "r", encoding="utf-8") as f:
            build_script_content = f.read()

    # 1. Verify header macro digits: CORE_LADDER_FRAME(tens, units)
    code_digits = parse_header_pulse_digits(header_content)
    expected_header_codes = [c for c in LADDER_STAGE_TABLE if c >= 11]
    for code in expected_header_codes:
        if code not in code_digits:
            raise ValueError(f"Missing CORE_LADDER_PULSE_{code} definition in header")
        tens, units = code_digits[code]
        computed = tens * 10 + units
        if computed != code:
            raise ValueError(
                f"Header CORE_LADDER_FRAME({tens}, {units}) digits mismatch for PULSE_{code}: "
                f"{tens}*10+{units} = {computed} != {code}"
            )

    # 2. Verify loader steps 1..7 emit sites, call positions, and order
    loader_matches = list(re.finditer(
        r"#if defined\(LED_LADDER\)\s*//\s*Step\s*(\d+):\s*([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_()]+);?",
        loader_content,
    ))
    if len(loader_matches) != 7:
        raise ValueError(f"Expected 7 loader ladder steps, found {len(loader_matches)}")

    loader_steps: Dict[int, str] = {}
    loader_mapping: Dict[int, Dict[str, Any]] = {}
    for idx, m in enumerate(loader_matches, start=1):
        step_num = int(m.group(1))
        step_name = m.group(2).upper()
        if step_num != idx:
            raise ValueError(f"Loader steps out of order: expected step {idx}, found {step_num}")
        stage_sym = f"STAGE_LOADER_{step_name}"
        loader_steps[step_num] = stage_sym
        expected_entry = LADDER_STAGE_TABLE[step_num]
        expected_sym = expected_entry["stage_symbol"]
        if stage_sym != expected_sym:
            raise ValueError(
                f"Loader stage symbol mismatch for Step {step_num}: "
                f"loader={stage_sym}, table={expected_sym}"
            )
        loader_mapping[step_num] = {
            "adjacent_call": expected_entry["adjacent_call"],
            "position": expected_entry["call_position"],
            "order_index": step_num,
            "last_stage_reached": stage_sym,
            "next_stage": NEXT_STAGE_MAP[step_num],
        }

    # Verify positions of loader steps relative to adjacent ROM/loader calls in loader_content
    m_check_compat = re.search(r"\bcheck_compat\s*\(\s*\)", loader_content)
    m_core_copy = re.search(r"\bcore_copy\s*\(", loader_content)
    m_dcache = re.search(r"Calls ROM_DCACHE_CLEAN_INV", loader_content)
    m_icache = re.search(r"Calls ROM_ICACHE_INV_BP", loader_content)
    m_bx = re.search(r"\bbx\s+r0", loader_content)

    if m_check_compat and loader_matches[0].start() < m_check_compat.start():
        raise ValueError("Loader Step 1 (after_prologue) emitted before check_compat()")
    if m_core_copy and loader_matches[1].start() < m_core_copy.start():
        raise ValueError("Loader Step 2 (after_copy) emitted before core_copy()")
    if m_dcache:
        if loader_matches[2].start() > m_dcache.start():
            raise ValueError("Loader Step 3 (before_dcache) emitted after D-cache clean")
        if loader_matches[3].start() < m_dcache.start():
            raise ValueError("Loader Step 4 (after_dcache) emitted before D-cache clean")
    if m_icache:
        if loader_matches[4].start() > m_icache.start():
            raise ValueError("Loader Step 5 (before_icache) emitted after I-cache invalidate")
        if loader_matches[5].start() < m_icache.start():
            raise ValueError("Loader Step 6 (after_icache) emitted before I-cache invalidate")
    if m_bx and loader_matches[6].start() > m_bx.start():
        raise ValueError("Loader Step 7 (before_bx) emitted after terminal handoff")

    # 3. Verify core injected codes, emit sites, relative positions, and order in build script
    core_mapping = parse_core_emit_mapping_from_build_script(build_script_content)
    expected_core_codes = set(c for c in LADDER_STAGE_TABLE if c >= 11)

    if set(core_mapping.keys()) != expected_core_codes:
        raise ValueError(
            f"Injected core codes mismatch: parsed={sorted(core_mapping.keys())}, "
            f"expected={sorted(expected_core_codes)}"
        )

    full_mapping: Dict[int, Tuple[str, str, int, str, Optional[str]]] = {}

    for step_num in range(1, 8):
        l_info = loader_mapping[step_num]
        full_mapping[step_num] = (
            l_info["adjacent_call"],
            l_info["position"],
            l_info["order_index"],
            l_info["last_stage_reached"],
            l_info["next_stage"],
        )

    sorted_core_codes = sorted(core_mapping.keys(), key=lambda c: core_mapping[c]["order_index"])

    for code in sorted_core_codes:
        parsed_info = core_mapping[code]
        expected_entry = LADDER_STAGE_TABLE[code]

        if parsed_info["position"] != expected_entry["call_position"]:
            raise ValueError(
                f"Position mismatch for Code {code} around {expected_entry['adjacent_call']}: "
                f"parsed='{parsed_info['position']}', expected='{expected_entry['call_position']}'"
            )

        if parsed_info["adjacent_call"] != expected_entry["adjacent_call"]:
            raise ValueError(
                f"Adjacent call mismatch for Code {code}: "
                f"parsed='{parsed_info['adjacent_call']}', expected='{expected_entry['adjacent_call']}'"
            )

        if parsed_info["order_index"] != expected_entry["order_index"]:
            raise ValueError(
                f"Order index mismatch for Code {code}: "
                f"parsed={parsed_info['order_index']}, expected={expected_entry['order_index']}"
            )

        stage_sym = expected_entry["stage_symbol"]
        next_stage = NEXT_STAGE_MAP[code]

        full_mapping[code] = (
            parsed_info["adjacent_call"],
            parsed_info["position"],
            parsed_info["order_index"],
            stage_sym,
            next_stage,
        )

    return {
        "code_digits": code_digits,
        "loader_steps": loader_steps,
        "loader_mapping": loader_mapping,
        "core_mapping": core_mapping,
        "full_mapping": full_mapping,
        "injected_codes": sorted_core_codes,
    }


def parse_ladder_table_from_source(
    doc_path: Optional[Path] = None,
) -> Dict[int, Dict[str, Any]]:
    """Parses the stage-code table at runtime directly from docs/PORT25_LADDER_FIX_CANDIDATE.md.
    
    Citations:
      - Table in Section 5: lines 328-354
      - Section 5.1: lines 358-359
    """
    if doc_path is None:
        doc_path = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"

    validate_safety_path(doc_path)

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    parsed_table: Dict[int, Dict[str, Any]] = {}

    table_pattern = re.compile(
        r"\|\s*\*\*(\d+)\*\*\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*`?([^`|]+)`?\s*\|\s*([^|]+)\|\s*([^|]+)\|"
    )
    for m in table_pattern.finditer(content):
        code = int(m.group(1))
        stage_symbol = m.group(2).strip()
        context = m.group(3).strip()
        file_line = m.group(4).strip()
        timing_state = m.group(5).strip()
        purpose = m.group(6).strip()

        line_num = content[:m.start()].count("\n") + 1

        parsed_table[code] = {
            "code": code,
            "stage_symbol": stage_symbol,
            "context": context,
            "file_line": file_line,
            "candidate_line": line_num,
            "timing_state": timing_state,
            "purpose": purpose,
        }

    bullet_pattern = re.compile(
        r"-\s*\*\*Code\s*(\d+)\*\*\s*\(\s*`?([^`,]+)`?\s*,\s*`?([^`,]+)`?\s*,\s*([^)]+)\)\s*:\s*(.*)"
    )
    for m in bullet_pattern.finditer(content):
        code = int(m.group(1))
        stage_symbol = m.group(2).strip()
        file_line = m.group(3).strip()
        context = m.group(4).strip()
        purpose = m.group(5).strip()

        line_num = content[:m.start()].count("\n") + 1

        parsed_table[code] = {
            "code": code,
            "stage_symbol": stage_symbol,
            "context": context,
            "file_line": file_line,
            "candidate_line": line_num,
            "timing_state": "Pre-Arming",
            "purpose": purpose,
        }

    return parsed_table


def parse_ladder_table_from_build_source(
    repo_root: Optional[Path] = None,
) -> Dict[int, Dict[str, Any]]:
    """Validates and extracts the stage table combining build source emit sites and doc stage symbols."""
    if repo_root is None:
        repo_root = REPO_ROOT

    doc_path = repo_root / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"
    doc_table = parse_ladder_table_from_source(doc_path)

    # Run the comprehensive consistency check
    verify_source_consistency(repo_root=repo_root)

    build_info = extract_build_source_pulse_codes(repo_root)
    emitted_codes = set(build_info["all_emitted_codes"])

    if emitted_codes != set(doc_table.keys()):
        raise ValueError(
            f"Build source emit codes mismatch with doc table: "
            f"build={sorted(emitted_codes)}, doc={sorted(doc_table.keys())}"
        )

    return doc_table


def parse_expected_diskboot_sha256(doc_path: Optional[Path] = None) -> str:
    """Parses expected PORT-25 combined candidate SHA-256 from docs/PORT25_LADDER_FIX_CANDIDATE.md:385."""
    if doc_path is None:
        doc_path = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"

    validate_safety_path(doc_path)

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(
        r"\|\s*\*\*PORT-25 Combined Candidate\*\*\s*\|[^|]*\|\s*`?([0-9a-fA-F]{64})`?\s*\|",
        content,
    )
    if not m:
        raise ValueError(f"Could not locate PORT-25 Combined Candidate SHA-256 in {doc_path}")

    return m.group(1).lower()


def process_report_pairs(raw_pairs: Sequence[Tuple[Any, Any]]) -> Dict[str, Any]:
    """Processes raw (key, value) pairs into a canonical report dictionary.
    
    Normalises uncertainty aliases, detects duplicate keys with conflicting values,
    and ensures deterministic outputs regardless of field order or input format.
    """
    field_values: Dict[str, List[Any]] = {}
    uncertainty_aliases: List[Tuple[str, Any]] = []
    duplicate_conflicts: List[str] = []

    for k, v in raw_pairs:
        k_clean = str(k).strip().lower()
        if k_clean in ("uncertain", "uncertainty", "count_confidence"):
            uncertainty_aliases.append((k_clean, v))
        elif k_clean in ("sequence", "code_sequence"):
            if "sequence" not in field_values:
                field_values["sequence"] = []
            field_values["sequence"].append(v)
        else:
            if k_clean not in field_values:
                field_values[k_clean] = []
            field_values[k_clean].append(v)

    report: Dict[str, Any] = {}

    for k, vals in field_values.items():
        if k == "pulses":
            parsed_vals = [parse_pulses_value(x) for x in vals]
            cmp_vals = [tuple(x) if isinstance(x, list) else x for x in parsed_vals]
            unique_cmp: List[Any] = []
            for cv in cmp_vals:
                if cv not in unique_cmp:
                    unique_cmp.append(cv)

            if len(unique_cmp) > 1:
                sorted_reps = sorted(repr(list(x) if isinstance(x, tuple) else x) for x in unique_cmp)
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key 'pulses': {', '.join(sorted_reps)}"
                )
                report["pulses"] = parsed_vals
            else:
                report["pulses"] = parsed_vals[0]

        elif k == "sequence":
            parsed_vals = [parse_sequence_value(x) for x in vals]
            cmp_vals = [tuple(x) if isinstance(x, list) else x for x in parsed_vals]
            unique_cmp_seq: List[Any] = []
            for cv in cmp_vals:
                if cv not in unique_cmp_seq:
                    unique_cmp_seq.append(cv)

            if len(unique_cmp_seq) > 1:
                sorted_reps = sorted(repr(list(x) if isinstance(x, tuple) else x) for x in unique_cmp_seq)
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for alias/key 'sequence': {', '.join(sorted_reps)}"
                )
                report["sequence"] = parsed_vals
            else:
                report["sequence"] = parsed_vals[0]

        elif k == "press":
            norm_vals = [str(x).strip().lower() for x in vals]
            unique_press = sorted(list(dict.fromkeys(norm_vals)))
            if len(unique_press) > 1:
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key 'press': {', '.join(repr(x) for x in unique_press)}"
                )
            report["press"] = norm_vals[0]

        elif k == "diskboot_sha256":
            norm_vals = [str(x).strip().lower() for x in vals]
            unique_sha = sorted(list(dict.fromkeys(norm_vals)))
            if len(unique_sha) > 1:
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key 'diskboot_sha256': {', '.join(repr(x) for x in unique_sha)}"
                )
            report["diskboot_sha256"] = norm_vals[0]

        elif k == "lcd":
            norm_vals = [normalize_lcd_state(x) for x in vals]
            unique_lcd = sorted(list(dict.fromkeys(norm_vals)))
            if len(unique_lcd) > 1:
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key 'lcd': {', '.join(repr(str(x)) for x in sorted(list(dict.fromkeys(str(x) for x in vals))))}"
                )
            report["lcd"] = vals[0]

        elif k == "inspector_status":
            norm_vals = [str(x).strip().lower() for x in vals]
            unique_insp = sorted(list(dict.fromkeys(norm_vals)))
            if len(unique_insp) > 1:
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key 'inspector_status': {', '.join(repr(x) for x in unique_insp)}"
                )
            report["inspector_status"] = norm_vals[0]

        elif k == "notes":
            clean_notes = [str(x).strip() for x in vals if str(x).strip()]
            unique_notes = list(dict.fromkeys(clean_notes))
            report["notes"] = "; ".join(unique_notes)

        else:
            norm_vals = [str(x).strip() for x in vals]
            unique_vals = sorted(list(dict.fromkeys(norm_vals)))
            if len(unique_vals) > 1:
                duplicate_conflicts.append(
                    f"Conflicting duplicate values for key '{k}': {', '.join(repr(x) for x in unique_vals)}"
                )
            report[k] = vals[0]

    notes_text = str(report.get("notes", ""))
    is_uncertain, unc_notes = normalize_uncertainty(uncertainty_aliases, notes_text=notes_text)

    report["uncertain"] = is_uncertain
    report["uncertainty"] = is_uncertain
    report["_uncertainty_notes"] = unc_notes
    report["_duplicate_conflicts"] = duplicate_conflicts

    return report


def parse_owner_report(input_data: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    """Parses an owner trial report from a dict, raw text (JSON or key=value), or a safe file path.
    
    Fields extracted:
      - diskboot_sha256: string
      - press: string ('short' or 'held')
      - pulses: integer, list of integers, 'none', or invalid raw representation
      - lcd: string
      - inspector_status: string
      - uncertain / uncertainty: optional flags for ambiguity detection
      - notes: optional notes
    """
    if isinstance(input_data, dict):
        return process_report_pairs(list(input_data.items()))

    raw_text: str = ""

    if isinstance(input_data, Path):
        raw_text = safe_open_report(input_data)
    elif isinstance(input_data, str):
        raw_str = input_data
        is_inline_json = False
        stripped = raw_str.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed_json = json.loads(stripped)
                if isinstance(parsed_json, dict):
                    is_inline_json = True
            except json.JSONDecodeError:
                pass

        is_inline_kv = ("\n" in raw_str and ("=" in raw_str or ":" in raw_str))

        if not is_inline_json and not is_inline_kv:
            # Treated as a path: delegate entirely to safe_open_report
            if is_forbidden_file_name(raw_str):
                safe_open_report(raw_str)
            elif raw_str != raw_str.strip() or any(ord(c) < 32 or ord(c) == 127 for c in raw_str):
                if "=" not in raw_str and ":" not in raw_str:
                    safe_open_report(raw_str)
                else:
                    raw_text = raw_str
            elif os.path.exists(raw_str) or os.path.islink(raw_str) or "/" in raw_str or "\\" in raw_str:
                raw_text = safe_open_report(raw_str)
            else:
                raw_text = raw_str
        else:
            raw_text = raw_str

    # Strip surrounding whitespace before deciding between JSON and key=value
    raw_text = raw_text.strip()

    # Try parsing as JSON first
    if raw_text.startswith("{") and raw_text.endswith("}"):
        try:
            parsed_pairs = json.loads(raw_text, object_pairs_hook=list)
            if isinstance(parsed_pairs, list):
                return process_report_pairs(parsed_pairs)
        except json.JSONDecodeError:
            pass

    # Parse simple key=value or key: value text format
    raw_pairs: List[Tuple[str, Any]] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        sep = "=" if "=" in line else (":" if ":" in line else None)
        if sep is None:
            continue

        key, val = line.split(sep, 1)
        key = key.strip()
        val = val.strip()

        # Strip surrounding quotes if present
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1].strip()

        raw_pairs.append((key, val))

    return process_report_pairs(raw_pairs)


def is_count_adjacent_to_two_valid_codes(
    count: int,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> bool:
    """Evaluates the off-by-one adjacency rule:
    Returns True if and only if BOTH immediate neighbours (count - 1) and (count + 1)
    are registered codes in the source table.
    """
    return (count - 1 in table) and (count + 1 in table)


def get_canonical_ladder_path(
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> Tuple[List[int], List[int]]:
    """Derives the canonical ladder execution paths dynamically from the source-of-truth table.

    Returns:
      (core_path, loader_path)
      where core_path starts at Code 11 and follows NEXT_STAGE_MAP stage symbols in table up to Code 44,
      and loader_path is the ordered loader steps 1..7.
    """
    loader_path = sorted([c for c in table if c < 10], key=lambda c: table[c].get("order_index", c))
    symbol_to_code = {entry["stage_symbol"]: code for code, entry in table.items()}
    next_stage_map = derive_next_stage_map(table)

    core_path: List[int] = []
    curr_sym = next_stage_map.get(7)
    while curr_sym and curr_sym in symbol_to_code:
        code = symbol_to_code[curr_sym]
        core_path.append(code)
        curr_sym = next_stage_map.get(code)

    return core_path, loader_path


def validate_ordered_code_sequence(
    seq: Any,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Validates an ordered sequence of ladder checkpoints.

    A full ordered code sequence (loader count plus core codes) must:
    1. Start with the loader count (Code 7) or the full ordered loader steps [1..7];
    2. Continue with core ladder codes (Code 11 onward) in strict monotonic execution order;
    3. Have no skipped codes (no gaps);
    4. Contain only valid registered codes in the source table.

    Returns:
      (error_class, terminal_code, error_message)
      - If valid: (None, terminal_code, None)
      - If unknown/invalid code: ("UNKNOWN_CODE", None, message)
      - If gapped, non-monotonic, or invalid progression: ("AMBIGUOUS", None, message)
    """
    if isinstance(seq, str):
        seq = parse_sequence_value(seq)

    if not isinstance(seq, list) or len(seq) == 0:
        return ("UNKNOWN_CODE", None, "Pulse sequence must be a non-empty list of codes.")

    int_seq: List[int] = []
    for item in seq:
        if isinstance(item, bool) or isinstance(item, float):
            return ("UNKNOWN_CODE", None, f"Invalid non-integer element {item!r} in pulse sequence.")
        elif isinstance(item, int):
            int_seq.append(item)
        elif isinstance(item, str) and re.fullmatch(r"[-+]?[0-9]+", item.strip()):
            int_seq.append(int(item.strip()))
        else:
            return ("UNKNOWN_CODE", None, f"Invalid non-numeric element {item!r} in pulse sequence.")

    for c in int_seq:
        if c <= 0 or c not in table:
            return (
                "UNKNOWN_CODE",
                None,
                f"Pulse sequence contains code {c} which does not match any registered code in the PORT-25 ladder stage table.",
            )

    core_path, loader_path = get_canonical_ladder_path(table)

    # Check loader prefix
    if int_seq[0] == 7:
        core_part = int_seq[1:]
    elif len(int_seq) >= 7 and int_seq[:7] == loader_path:
        core_part = int_seq[7:]
    else:
        return (
            "AMBIGUOUS",
            None,
            f"Sequence does not start with initial loader stage (expected Code 7 or {loader_path}, observed Code {int_seq[0]}).",
        )

    if len(core_part) == 0:
        return (
            "AMBIGUOUS",
            None,
            "Sequence does not reach core ladder checkpoints (loader count plus core codes required).",
        )

    for i, c in enumerate(core_part):
        prev_code = core_part[i - 1] if i > 0 else 7
        if i >= len(core_path):
            return (
                "AMBIGUOUS",
                None,
                f"Sequence extends beyond final ladder stage Code {core_path[-1]} (observed Code {c}).",
            )
        exp_code = core_path[i]
        if c != exp_code:
            if i > 0 and c <= prev_code:
                return (
                    "AMBIGUOUS",
                    None,
                    f"Sequence is not strictly monotonic: Code {c} follows Code {prev_code}.",
                )
            exp_sym = table[exp_code]["stage_symbol"]
            act_sym = table.get(c, {}).get("stage_symbol", "UNKNOWN")
            return (
                "AMBIGUOUS",
                None,
                f"Sequence skips expected stage following Code {prev_code} (expected Code {exp_code} / {exp_sym}, observed Code {c} / {act_sym}).",
            )

    terminal_code = int_seq[-1]
    return (None, terminal_code, None)


def classify_owner_report(
    input_data: Union[Dict[str, Any], str, Path],
    expected_sha256: str = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    table: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Classifies an owner trial report into a deterministic outcome structure.
    
    Returns a dict with:
      - class: string (CODE_<N>, NO_PULSES, UNKNOWN_CODE, AMBIGUOUS, INVALID_CANDIDATE, CONTROL_HELD_O1)
      - last_stage_reached: string or None
      - next_stage: string or None
      - evidence: string citation
      - notes: string explanation
    """
    if table is None:
        table = LADDER_STAGE_TABLE

    next_stage_map = derive_next_stage_map(table)
    report = parse_owner_report(input_data)

    reported_sha256 = str(report.get("diskboot_sha256", "")).strip().lower()
    press = str(report.get("press", "short")).strip().lower()
    raw_lcd = report.get("lcd", "")
    lcd_state = normalize_lcd_state(raw_lcd)
    raw_inspector = str(report.get("inspector_status", "")).strip()
    inspector_status = raw_inspector.lower()
    raw_lcd_str = str(raw_lcd).strip()
    notes_in = str(report.get("notes", "")).strip()

    duplicate_conflicts = list(report.get("_duplicate_conflicts", []))
    uncertainty_notes = list(report.get("_uncertainty_notes", []))
    uncertainty_flagged = bool(report.get("uncertain", False))

    # Explicit note when held press does not reach stock UI affirmatively
    held_non_stock_note = ""
    if press == "held" and lcd_state != LcdState.STOCK_UI:
        held_non_stock_note = " (Note: press was held, but lcd state not affirmatively stock UI)."

    # Gate Check: Conflicting duplicate keys
    if duplicate_conflicts:
        note_dup = (
            f"Conflicting duplicate keys reported: {'; '.join(duplicate_conflicts)}. "
            "Unable to definitively isolate terminal stage due to conflicting observations."
        )
        if held_non_stock_note:
            note_dup += held_non_stock_note
        return {
            "class": "AMBIGUOUS",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
            "notes": note_dup,
        }

    # 1. Gate Check: Candidate DISKBOOT SHA-256 Verification
    # Citation: docs/PORT25_LADDER_FIX_CANDIDATE.md:385
    if reported_sha256 != expected_sha256.lower():
        return {
            "class": "INVALID_CANDIDATE",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:385; docs/PORT25_OWNER_TRIAL_PLAN.md:30, 51, 81",
            "notes": (
                f"Candidate DISKBOOT SHA-256 mismatch: reported '{reported_sha256}' "
                f"does not match expected PORT-25 combined candidate digest '{expected_sha256}'."
            ),
        }

    # 2. Check for CONTROL_HELD_O1
    # Condition: Held button press that affirmatively booted into the stock UI.
    # Citations: docs/PORT24_POWERON_FIX.md:19-24, docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55,
    #            docs/PORT25_OWNER_TRIAL_PLAN.md:162-173
    if press == "held" and lcd_state == LcdState.STOCK_UI:
        evidence_held = (
            "docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55; "
            "docs/PORT25_OWNER_TRIAL_PLAN.md:162-173"
        )
        return {
            "class": "CONTROL_HELD_O1",
            "last_stage_reached": "STOCK_UI",
            "next_stage": None,
            "evidence": evidence_held,
            "notes": (
                "Held-press control trial successfully booted to stock user interface (Outcome O1/O6). "
                "Confirms baseline hardware responsiveness and positive control."
            ),
        }

    # 3. Pulse / Sequence Input Validation & Resolution
    # - 'none' (case-insensitive, exact) is the ONLY value giving NO_PULSES.
    # - Accept only real ints, or strings of decimal digits, plus lists of those or ordered sequences.
    # - Missing pulses field, empty value, 'unknown', '?', floats (24.9), bools (True),
    #   negative numbers (-1) or zero (0) map to UNKNOWN_CODE with explanatory notes.
    has_pulses = "pulses" in report
    has_sequence = "sequence" in report

    if not has_pulses and not has_sequence:
        note_missing = (
            "Missing 'pulses' or 'sequence' field in owner report. Report must supply an integer pulse count, "
            "a list of integers, an ordered sequence, or 'none'."
        )
        if held_non_stock_note:
            note_missing += held_non_stock_note
        return {
            "class": "UNKNOWN_CODE",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
            "notes": note_missing,
        }

    pulses_raw = report.get("pulses") if has_pulses else None
    sequence_raw = report.get("sequence") if has_sequence else None

    is_none_pulse = False
    count_resolved: Optional[int] = None
    is_sequence = False
    seq_codes: List[int] = []

    # CASE A: Both pulses and sequence are present in the report
    if has_pulses and has_sequence:
        # Validate sequence
        if isinstance(sequence_raw, list) and len(sequence_raw) == 0:
            return {
                "class": "AMBIGUOUS",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                "notes": "Empty sequence list reported alongside pulses." + held_non_stock_note,
            }
        seq_err, seq_term, seq_msg = validate_ordered_code_sequence(sequence_raw, table)
        if seq_err is not None:
            return {
                "class": "AMBIGUOUS",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                "notes": f"Invalid sequence in report: {seq_msg}" + held_non_stock_note,
            }

        # Validate pulses and compare against sequence
        if isinstance(pulses_raw, list):
            if len(pulses_raw) == 0:
                return {
                    "class": "AMBIGUOUS",
                    "last_stage_reached": None,
                    "next_stage": None,
                    "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                    "notes": "Empty pulses list reported alongside sequence." + held_non_stock_note,
                }
            elif len(pulses_raw) == 1:
                item = pulses_raw[0]
                if isinstance(item, bool) or not isinstance(item, int) and not (isinstance(item, str) and item.isdigit()):
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Invalid pulses value {item!r} reported alongside sequence." + held_non_stock_note,
                    }
                p_code = int(item)
                if p_code != seq_term:
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Explicit 'pulses' count ({p_code}) conflicts with terminal code of sequence ({seq_term})." + held_non_stock_note,
                    }
                count_resolved = seq_term
                is_sequence = True
                seq_codes = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)
            else:
                p_err, p_term, p_msg = validate_ordered_code_sequence(pulses_raw, table)
                if p_err is not None:
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Invalid pulses sequence: {p_msg}" + held_non_stock_note,
                    }
                p_list = pulses_raw if isinstance(pulses_raw, list) else parse_sequence_value(pulses_raw)
                s_list = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)
                if p_list != s_list or p_term != seq_term:
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Sequence and pulses list differ: pulses ends at Code {p_term}, sequence ends at Code {seq_term} (missing final code)." + held_non_stock_note,
                    }
                count_resolved = seq_term
                is_sequence = True
                seq_codes = s_list
        elif isinstance(pulses_raw, int) and not isinstance(pulses_raw, bool):
            if pulses_raw != seq_term:
                return {
                    "class": "AMBIGUOUS",
                    "last_stage_reached": None,
                    "next_stage": None,
                    "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                    "notes": f"Explicit 'pulses' count ({pulses_raw}) conflicts with terminal code of sequence ({seq_term})." + held_non_stock_note,
                }
            count_resolved = seq_term
            is_sequence = True
            seq_codes = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)
        elif isinstance(pulses_raw, str):
            p_str = pulses_raw.strip()
            if p_str.lower() == "none":
                return {
                    "class": "AMBIGUOUS",
                    "last_stage_reached": None,
                    "next_stage": None,
                    "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                    "notes": "Report indicates pulses='none' while also supplying a non-empty sequence." + held_non_stock_note,
                }
            elif re.fullmatch(r"[-+]?[0-9]+", p_str):
                p_int = int(p_str)
                if p_int != seq_term:
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Explicit 'pulses' count ({p_int}) conflicts with terminal code of sequence ({seq_term})." + held_non_stock_note,
                    }
                count_resolved = seq_term
                is_sequence = True
                seq_codes = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)
            else:
                p_parsed = parse_pulses_value(pulses_raw)
                if isinstance(p_parsed, list):
                    p_err, p_term, p_msg = validate_ordered_code_sequence(p_parsed, table)
                    if p_err is not None:
                        return {
                            "class": "AMBIGUOUS",
                            "last_stage_reached": None,
                            "next_stage": None,
                            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                            "notes": f"Invalid pulses sequence: {p_msg}" + held_non_stock_note,
                        }
                    s_list = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)
                    if p_parsed != s_list or p_term != seq_term:
                        return {
                            "class": "AMBIGUOUS",
                            "last_stage_reached": None,
                            "next_stage": None,
                            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                            "notes": f"Sequence and pulses list differ: pulses ends at Code {p_term}, sequence ends at Code {seq_term}." + held_non_stock_note,
                        }
                    count_resolved = seq_term
                    is_sequence = True
                    seq_codes = s_list
                else:
                    return {
                        "class": "AMBIGUOUS",
                        "last_stage_reached": None,
                        "next_stage": None,
                        "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                        "notes": f"Invalid non-numeric pulses value {pulses_raw!r} reported alongside sequence." + held_non_stock_note,
                    }
        else:
            return {
                "class": "AMBIGUOUS",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                "notes": f"Invalid pulses value {pulses_raw!r} reported alongside sequence." + held_non_stock_note,
            }

    # CASE B: Only sequence is present in the report
    elif has_sequence:
        if isinstance(sequence_raw, list) and len(sequence_raw) == 0:
            return {
                "class": "UNKNOWN_CODE",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
                "notes": "Empty sequence list in owner report." + held_non_stock_note,
            }
        seq_err, seq_term, seq_msg = validate_ordered_code_sequence(sequence_raw, table)
        if seq_err == "UNKNOWN_CODE":
            return {
                "class": "UNKNOWN_CODE",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
                "notes": f"Pulse input validation failure: {seq_msg}" + held_non_stock_note,
            }
        elif seq_err == "AMBIGUOUS":
            return {
                "class": "AMBIGUOUS",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                "notes": f"Conflicting multiple pulse counts reported: {sequence_raw}. ({seq_msg})" + held_non_stock_note,
            }
        else:
            assert seq_term is not None
            count_resolved = seq_term
            is_sequence = True
            seq_codes = sequence_raw if isinstance(sequence_raw, list) else parse_sequence_value(sequence_raw)

    # CASE C: Only pulses is present in the report
    else:
        invalid_input_reason: Optional[str] = None
        is_ambiguous_multiple = False
        ambig_reason: Optional[str] = None

        if isinstance(pulses_raw, bool):
            invalid_input_reason = (
                f"Invalid boolean value '{pulses_raw}' for pulses (booleans are not valid pulse counts)."
            )
        elif isinstance(pulses_raw, float):
            invalid_input_reason = (
                f"Invalid non-integer float value '{pulses_raw}' for pulses; "
                "only integers, decimal digit strings, or 'none' accepted."
            )
        elif isinstance(pulses_raw, str):
            p_str = pulses_raw.strip()
            if p_str.lower() == "none":
                is_none_pulse = True
            elif p_str == "":
                invalid_input_reason = "Empty 'pulses' value in owner report."
            elif re.fullmatch(r"[-+]?[0-9]+", p_str):
                count_resolved = int(p_str)
            else:
                invalid_input_reason = (
                    f"Invalid non-numeric or malformed pulse count string '{pulses_raw}' in owner report."
                )
        elif isinstance(pulses_raw, int):
            count_resolved = pulses_raw
        elif isinstance(pulses_raw, list):
            if len(pulses_raw) == 0:
                invalid_input_reason = "Empty pulses list in owner report."
            else:
                int_list: List[int] = []
                for item in pulses_raw:
                    if isinstance(item, bool):
                        invalid_input_reason = f"Invalid boolean element '{item}' inside pulses list."
                        break
                    elif isinstance(item, float):
                        invalid_input_reason = f"Invalid float element '{item}' inside pulses list."
                        break
                    elif isinstance(item, int):
                        int_list.append(item)
                    elif isinstance(item, str) and re.fullmatch(r"[-+]?[0-9]+", item.strip()):
                        int_list.append(int(item.strip()))
                    else:
                        invalid_input_reason = f"Invalid non-numeric element '{item}' inside pulses list."
                        break

                if invalid_input_reason is None:
                    unique_counts = sorted(list(set(int_list)))
                    if len(unique_counts) == 1:
                        count_resolved = unique_counts[0]
                    else:
                        seq_err, seq_term, seq_msg = validate_ordered_code_sequence(int_list, table)
                        if seq_err == "UNKNOWN_CODE":
                            invalid_input_reason = seq_msg
                        elif seq_err == "AMBIGUOUS":
                            is_ambiguous_multiple = True
                            ambig_reason = seq_msg
                        else:
                            assert seq_term is not None
                            count_resolved = seq_term
                            is_sequence = True
                            seq_codes = int_list
        else:
            invalid_input_reason = f"Unrecognized pulse input type '{type(pulses_raw).__name__}'."

        if invalid_input_reason is not None:
            note_inval = (
                f"Pulse input validation failure: {invalid_input_reason} "
                "Accepted formats: integer, decimal digit string, list of integers, or 'none'."
            )
            if held_non_stock_note:
                note_inval += held_non_stock_note
            return {
                "class": "UNKNOWN_CODE",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
                "notes": note_inval,
            }

        if is_ambiguous_multiple:
            note_ambig = (
                f"Conflicting multiple pulse counts reported: {pulses_raw}. "
                "Unable to definitively isolate terminal stage due to conflicting observations."
            )
            if ambig_reason:
                note_ambig += f" ({ambig_reason})"
            if held_non_stock_note:
                note_ambig += held_non_stock_note
            return {
                "class": "AMBIGUOUS",
                "last_stage_reached": None,
                "next_stage": None,
                "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
                "notes": note_ambig,
            }

    # Handle NO_PULSES (exact case-insensitive 'none')
    if is_none_pulse:
        note_parts = [
            "No ladder checkpoint was observed (VERIFIED from the report itself).",
            f"Observed report inputs: press='{press}', lcd='{raw_lcd_str}', inspector_status='{raw_inspector}'.",
            "Underlying boot progress and failure cause are UNKNOWN (no LED evidence recorded in trial table).",
        ]
        conflict_desc = check_no_pulses_lcd_conflict(raw_lcd)
        if conflict_desc:
            note_parts.append(
                f"Reported observations conflict with the ladder's expected behaviour [UNKNOWN: {conflict_desc}]."
            )
        if held_non_stock_note:
            note_parts.append(held_non_stock_note.strip())
        if notes_in:
            note_parts.append(f"Owner notes: '{notes_in}'.")
        if uncertainty_notes:
            note_parts.extend(f"(Note: {n})" for n in uncertainty_notes)

        return {
            "class": "NO_PULSES",
            "last_stage_reached": "UNKNOWN (no LED evidence)",
            "next_stage": "UNKNOWN (no LED evidence)",
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:201; docs/PORT25_LADDER_FIX_CANDIDATE.md:328",
            "notes": " ".join(note_parts),
        }

    assert count_resolved is not None

    # Handle non-positive integer counts (<= 0)
    if count_resolved <= 0:
        note_np = (
            f"Pulse count {count_resolved} does not match any registered code in the PORT-25 "
            "ladder stage table (valid codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44)."
        )
        if held_non_stock_note:
            note_np += held_non_stock_note
        if uncertainty_notes:
            note_np += " " + " ".join(f"(Note: {n})" for n in uncertainty_notes)
        return {
            "class": "UNKNOWN_CODE",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
            "notes": note_np,
        }

    # 4. Check Off-By-One Uncertainty Rule
    if uncertainty_flagged and is_count_adjacent_to_two_valid_codes(count_resolved, table):
        prev_sym = table[count_resolved - 1]["stage_symbol"]
        next_sym = table[count_resolved + 1]["stage_symbol"]
        note_adj = (
            f"Owner flagged uncertainty on pulse count {count_resolved}, which is adjacent to two valid "
            f"codes ({count_resolved - 1}: {prev_sym}, {count_resolved + 1}: {next_sym}). "
            "Classified as AMBIGUOUS under the off-by-one uncertainty rule."
        )
        if held_non_stock_note:
            note_adj += held_non_stock_note
        if uncertainty_notes:
            note_adj += " " + " ".join(f"(Note: {n})" for n in uncertainty_notes)
        return {
            "class": "AMBIGUOUS",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
            "notes": note_adj,
        }

    # 5. Check In-Table Code (emits only the 29 registered codes)
    if count_resolved in table:
        entry = table[count_resolved]
        stage_symbol = entry["stage_symbol"]
        next_stage = next_stage_map.get(count_resolved)
        candidate_line = entry.get("candidate_line", 328)
        file_line = entry.get("file_line", "boot_prototype.c")
        purpose = entry.get("purpose", "")
        context = entry.get("context", "")

        note_text = f"{purpose} ({context})."
        if is_sequence:
            note_text += (
                f" Full ordered ladder sequence verified ({len(seq_codes)} checkpoints from loader "
                f"through Code {count_resolved} / {stage_symbol})."
            )
            if count_resolved == 44:
                note_text += " Handoff continuation branches to sub_fc0d0126 [VERIFIED: boot_prototype.c:436-438]."
                if lcd_state == LcdState.STOCK_UI:
                    note_text += " Independent affirmative UI evidence observed: camera booted into stock UI."
            else:
                normal_codes = [
                    1, 2, 3, 4, 5, 6, 7,
                    11, 12, 13, 14, 15,
                    21, 22, 23, 24, 25, 26,
                    31, 32, 33, 34, 35,
                    41, 42, 43, 44,
                ]
                if count_resolved in normal_codes:
                    c_idx = normal_codes.index(count_resolved)
                    if c_idx + 1 < len(normal_codes):
                        n_code = normal_codes[c_idx + 1]
                        next_code_str = f"Code {n_code} ({next_stage})"
                    else:
                        next_code_str = next_stage or "none"
                else:
                    next_code_str = next_stage or "none"
                note_text += f" Next unreached stage: {next_code_str}."
        elif count_resolved == 44:
            note_text += " Handoff continuation branches to sub_fc0d0126 [VERIFIED: boot_prototype.c:436-438]."
            if lcd_state == LcdState.STOCK_UI:
                note_text += " Independent affirmative UI evidence observed: camera booted into stock UI."

        if uncertainty_flagged:
            note_text += " (Note: owner flagged uncertainty, but count is not adjacent to two valid codes)."

        if held_non_stock_note:
            note_text += held_non_stock_note

        if uncertainty_notes:
            note_text += " " + " ".join(f"(Note: {n})" for n in uncertainty_notes)

        return {
            "class": f"CODE_{count_resolved}",
            "last_stage_reached": stage_symbol,
            "next_stage": next_stage,
            "evidence": f"docs/PORT25_LADDER_FIX_CANDIDATE.md:{candidate_line}; {file_line}",
            "notes": note_text,
        }

    # 6. Out-of-Table Code (all in-range gaps within 1..44 and out-of-range counts map here)
    note_oot = (
        f"Pulse count {count_resolved} does not match any registered code in the PORT-25 "
        "ladder stage table (valid codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44)."
    )
    if held_non_stock_note:
        note_oot += held_non_stock_note
    if uncertainty_flagged:
        note_oot += " (Note: owner flagged uncertainty, but count is not adjacent to two valid codes)."
    if uncertainty_notes:
        note_oot += " " + " ".join(f"(Note: {n})" for n in uncertainty_notes)
    return {
        "class": "UNKNOWN_CODE",
        "last_stage_reached": None,
        "next_stage": None,
        "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
        "notes": note_oot,
    }


def decode_ladder_report(
    input_data: Union[Dict[str, Any], str, Path],
    expected_sha256: str = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> str:
    """Classifies an owner trial report and emits deterministic, sorted JSON."""
    result = classify_owner_report(input_data, expected_sha256=expected_sha256, table=table)
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PORT-26 T1: LED-code ladder decoder tool for PORT-25 combined candidate owner reports."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to owner trial report file (JSON or key=value), or raw report string, or '-' for stdin",
    )
    parser.add_argument(
        "--json",
        dest="json_str",
        type=str,
        default=None,
        help="Raw JSON owner trial report string",
    )
    parser.add_argument(
        "--report",
        dest="report_str",
        type=str,
        default=None,
        help="Raw key=value owner trial report string",
    )

    args = parser.parse_args()

    input_payload: Optional[str] = None
    if args.json_str:
        input_payload = args.json_str
    elif args.report_str:
        input_payload = args.report_str
    elif args.input == "-" or (args.input is None and not sys.stdin.isatty()):
        input_payload = sys.stdin.read()
    elif args.input:
        input_payload = args.input
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        out_json = decode_ladder_report(input_payload)
        sys.stdout.write(out_json)
    except SafetyViolationError as sve:
        sys.stderr.write(f"ERROR: {sve}\n")
        sys.exit(2)
    except Exception as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
