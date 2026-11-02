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
- Architectural Specification & Canonical Symbol Mapping:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354 (Section 5 Stage-Code Table, Codes 1..7, 11..15, 21..26, 31..35, 41..44)
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:358-359 (Section 5.1 Native Power-Cut Failure Path, Codes 28 and 29)
  - docs/PORT25_SHORT_PRESS_LOCALISE.md:328-351 (Proposed Breadcrumb Placement in boot_prototype.c)
  - docs/PORT25_OWNER_TRIAL_PLAN.md:199-233 (Owner Reading Table: Mapping LED Codes to Stages and T2 Candidates)
- Expected Combined Candidate DISKBOOT SHA-256:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:385 ("9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15")
  - docs/PORT25_OWNER_TRIAL_PLAN.md:30, 51, 81 (Expected candidate size: 124,865 bytes)

Machine-Readable Pulse Table Status & Extraction:
- [VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:43-154]:
  Loader ladder emit sites define Steps 1..7 directly before/after cache operations and relocation.
- [VERIFIED: tools/build_candidate_port25_ladder_fix.py:90-128]:
  Build script generate_boot_prototype_ladder_c() injects exactly 22 CORE_LADDER_PULSE_xx macros into boot_prototype.c.
- [VERIFIED: chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266]:
  Header defines framed timing macros CORE_LADDER_FRAME(tens, units).
- [VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:328-359]:
  The specification provides the authoritative machine-parseable table mapping pulse counts to stage symbols.
- [UNKNOWN / INFERRED]:
  In the C firmware / build source, there is no standalone C lookup table (such as a `const char* stage_names[]` array)
  pairing integer pulse counts directly to string stage names. Instead, pulse counts are embedded as discrete macro
  injection calls in tools/build_candidate_port25_ladder_fix.py and step comments in loader_main_breadcrumb.c.
  The decoder provides extract_build_source_pulse_codes() to parse emit sites directly from the build source,
  and tests assert that every pulse count in the doc appears as an active LED-ladder emit site in the p25-t3b build source,
  and that the union of build source emit counts exactly equals the 29 codes of LADDER_STAGE_TABLE.

Code Range & Classes:
- Valid Table Code Classes (exactly 29 codes):
  * Loader (7 codes): CODE_1, CODE_2, CODE_3, CODE_4, CODE_5, CODE_6, CODE_7
  * Core Group 1 (5 codes): CODE_11, CODE_12, CODE_13, CODE_14, CODE_15
  * Core Group 2 (6 codes): CODE_21, CODE_22, CODE_23, CODE_24, CODE_25, CODE_26
  * Native Power-Cut Fail Path (2 codes): CODE_28, CODE_29
  * Core Group 3 (5 codes): CODE_31, CODE_32, CODE_33, CODE_34, CODE_35
  * Core Group 4 (4 codes): CODE_41, CODE_42, CODE_43, CODE_44
- In-Range Gaps within 1..44 (15 gap counts):
  8, 9, 10, 16, 17, 18, 19, 20, 27, 30, 36, 37, 38, 39, 40.
  Every in-range gap count maps to UNKNOWN_CODE (with the sole exception of count 27 when flagged uncertain,
  which maps to AMBIGUOUS because both 26 and 28 are valid table codes).
- Out-of-Range Counts:
  Any integer count < 1 or > 44 maps to UNKNOWN_CODE.
- Special Trial Classes:
  * NO_PULSES: Zero pulses observed ('none', 0, null, or empty string).
  * UNKNOWN_CODE: Pulse counts not registered in the 29-code table.
  * AMBIGUOUS: Conflicting multiple counts reported, or a count adjacent to two valid codes with owner uncertainty.
  * INVALID_CANDIDATE: Candidate DISKBOOT SHA-256 does not match the expected combined-candidate digest.
  * CONTROL_HELD_O1: Held button press that boots into the stock user interface (positive control).

Off-By-One Uncertainty Rule (AMBIGUOUS Classification):
- Purpose:
  Human observation of LED flashes is subject to perceptual ambiguity or blink-counting errors.
  When an owner flags uncertainty in a trial report, an off-by-one count could represent either of
  two adjacent stages. To avoid false triage, the reading must be classified as AMBIGUOUS.
- When it applies:
  The rule triggers IF AND ONLY IF:
  1. The owner trial report explicitly flags uncertainty (see spelling variants below); AND
  2. The reported pulse count C is adjacent to TWO valid codes in the source table:
     both (C - 1) in LADDER_STAGE_TABLE and (C + 1) in LADDER_STAGE_TABLE.
  When both conditions hold, the trial outcome is classified as `AMBIGUOUS`.
- Which neighbours count:
  Only immediate integer predecessor (C - 1) and successor (C + 1) that are valid members of
  the 29-code `LADDER_STAGE_TABLE`.
  * Counts with two valid neighbours:
    - Loader: 2, 3, 4, 5, 6 (1 and 7 have only one neighbour in the table).
    - Core Group 1: 12, 13, 14 (11 and 15 have only one neighbour in the table).
    - Core Group 2: 22, 23, 24, 25 (21 and 26 have only one neighbour in the table).
    - Core Group 3: 32, 33, 34 (31 and 35 have only one neighbour in the table).
    - Core Group 4: 42, 43 (41 and 44 have only one neighbour in the table).
    - In-range gap 27: (26 in table and 28 in table). If count 27 is reported with uncertainty,
      it triggers AMBIGUOUS.
  * Counts with at most one valid neighbour (boundary codes & isolated gaps):
    - Boundary codes: 1, 7, 11, 15, 21, 26, 28, 29, 31, 35, 41, 44.
    - Isolated in-range gaps: 8, 9, 10, 16, 17, 18, 19, 20, 30, 36, 37, 38, 39, 40.
    For these counts, the off-by-one rule does NOT trigger AMBIGUOUS even if uncertainty is flagged;
    they are classified as their valid code (with an explanatory note) or UNKNOWN_CODE.
- Owner Uncertainty Flag Spelling:
  The decoder recognizes uncertainty indications in both JSON and key=value formats:
  1. JSON Format:
     - Top-level boolean or truthy string field:
       `"uncertain": true` (or `"true"`, `"yes"`, `"1"`)
       `"uncertainty": true` (or `"true"`, `"yes"`, `"1"`)
     - Inline pulse annotation:
       `"pulses": "24 (uncertain)"` or `"pulses": "24?"`
     - Descriptive notes field:
       `"notes": "... uncertain ..."` (case-insensitive substring)
     Note: explicit negative values (`"uncertain": false`, `"uncertain": "false"`, `"uncertain": 0`)
     are recognized as FALSE and do NOT trigger uncertainty.
  2. Simple Key=Value Text Format:
     - Field line:
       `uncertain = true` (or `yes`, `1`)
       `uncertainty = true` (or `yes`, `1`)
     - Inline pulse annotation:
       `pulses = 24 (uncertain)` or `pulses = 24?`
     - Descriptive notes line:
       `notes = count uncertain due to rapid blinking`
     Note: explicit negative lines (`uncertain = false`, `uncertain = no`, `uncertain = 0`)
     are recognized as FALSE.

Phase 0 Safety Governance:
- Pure Python standard library only.
- Strict refusal of paths ending in .bin, .rom, or .BIN (case-insensitive) or basenames starting with PRIMARY*.
- Reads no ROM or binary files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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
    },
    2: {
        "code": 2,
        "stage_symbol": "STAGE_LOADER_AFTER_COPY",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:99",
        "candidate_line": 329,
        "timing_state": "Pre-Arming",
        "purpose": "Step 2: Core payload copied to 0x003489B4",
    },
    3: {
        "code": 3,
        "stage_symbol": "STAGE_LOADER_BEFORE_DCACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:116",
        "candidate_line": 330,
        "timing_state": "Pre-Arming",
        "purpose": "Step 3: Immediately before ROM D-cache clean/invalidate (0xFC127AB1)",
    },
    4: {
        "code": 4,
        "stage_symbol": "STAGE_LOADER_AFTER_DCACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:127",
        "candidate_line": 331,
        "timing_state": "Pre-Arming",
        "purpose": "Step 4: D-cache clean/invalidate completed",
    },
    5: {
        "code": 5,
        "stage_symbol": "STAGE_LOADER_BEFORE_ICACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:132",
        "candidate_line": 332,
        "timing_state": "Pre-Arming",
        "purpose": "Step 5: Immediately before ROM I-cache invalidate (0xFC127B09)",
    },
    6: {
        "code": 6,
        "stage_symbol": "STAGE_LOADER_AFTER_ICACHE",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:144",
        "candidate_line": 333,
        "timing_state": "Pre-Arming",
        "purpose": "Step 6: I-cache invalidate completed",
    },
    7: {
        "code": 7,
        "stage_symbol": "STAGE_LOADER_BEFORE_BX",
        "context": "Loader",
        "file_line": "loader_main_breadcrumb.c:152",
        "candidate_line": 334,
        "timing_state": "Pre-Arming",
        "purpose": "Step 7: Final loader step immediately before bx r0 to core (0x003489B5)",
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
    },
    12: {
        "code": 12,
        "stage_symbol": "STAGE_BC_POST_BSS",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:154",
        "candidate_line": 336,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Low/High RAM copies and Canon BSS zeroing completed",
    },
    13: {
        "code": 13,
        "stage_symbol": "STAGE_BC_STAGE3_ENTRY",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:175",
        "candidate_line": 337,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to sub_fc05b3c8_my immediately after witness_record_core",
    },
    14: {
        "code": 14,
        "stage_symbol": "STAGE_BC_PRE_KERNEL_INIT",
        "context": "Reset thread",
        "file_line": "boot_prototype_ladder.c:256",
        "candidate_line": 338,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: DryOS memory descriptors initialized; immediately before blx sub_fc31b408",
    },
    15: {
        "code": 15,
        "stage_symbol": "STAGE_BC_STAGE4_ENTRY",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:272",
        "candidate_line": 339,
        "timing_state": "Pre-Arming",
        "purpose": "Entry Checkpoint: Entry to sub_fc05b558_my (Initial Task) after push {r4, lr}",
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
    },
    22: {
        "code": 22,
        "stage_symbol": "STAGE_BC_PRE_MPU_SETUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:347",
        "candidate_line": 341,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before bl sub_fc05ba68 (pxSetup, dhcpc_setup, mpuSetup)",
    },
    23: {
        "code": 23,
        "stage_symbol": "STAGE_BC_POST_MPU_SETUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:347",
        "candidate_line": 342,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately after bl sub_fc05ba68; proves setup calls returned",
    },
    24: {
        "code": 24,
        "stage_symbol": "STAGE_BC_PRE_POWER_CHECK",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:348",
        "candidate_line": 343,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately after bl sub_fc079404, before button check sub_fc1284ac",
    },
    25: {
        "code": 25,
        "stage_symbol": "STAGE_BC_POWER_CHECK_PASS",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:361",
        "candidate_line": 344,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Label loc_fc05b978; button check passed or bypassed via G3X_POWERON_FIX",
    },
    26: {
        "code": 26,
        "stage_symbol": "STAGE_BC_PRE_CREATE_STARTUP",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:373",
        "candidate_line": 345,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before blx sub_fc31bbc4 (DryOS CreateTask 'Startup')",
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
    },
    29: {
        "code": 29,
        "stage_symbol": "STAGE_BC_HALT_SHUTDOWN",
        "context": "Initial Task",
        "file_line": "boot_prototype_ladder.c:358",
        "candidate_line": 359,
        "timing_state": "Pre-Arming",
        "purpose": "Flashes at label loc_fc05b976 if sub_fc05ba56 returns without immediate cut",
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
    },
    32: {
        "code": 32,
        "stage_symbol": "STAGE_BC_POST_EARLY_INIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:393",
        "candidate_line": 347,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Early driver calls (sub_fc0d0150..sub_fc418eec) returned",
    },
    33: {
        "code": 33,
        "stage_symbol": "STAGE_BC_PRE_SD1STINIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:402",
        "candidate_line": 348,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before SD1stInit gate check sub_fc05c4e0",
    },
    34: {
        "code": 34,
        "stage_symbol": "STAGE_BC_POST_SD1STINIT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:407",
        "candidate_line": 349,
        "timing_state": "Pre-Arming",
        "purpose": "Helper-Return Checkpoint: Label 1: after SD1stInit task creation veneer",
    },
    35: {
        "code": 35,
        "stage_symbol": "STAGE_BC_PRE_WATCHDOG_START",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:413",
        "candidate_line": 350,
        "timing_state": "Pre-Arming",
        "purpose": "Checkpoint: Immediately before bl sub_fc418f2a (watchdog arming helper)",
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
    },
    42: {
        "code": 42,
        "stage_symbol": "STAGE_BC_PRE_PHYSW_CREATE",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:418",
        "candidate_line": 352,
        "timing_state": "POST-ARMING",
        "purpose": "Checkpoint: Immediately before bl sub_fc1283d2 (task_PhySw launcher helper)",
    },
    43: {
        "code": 43,
        "stage_symbol": "STAGE_BC_POST_PHYSW_CREATE",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:418",
        "candidate_line": 353,
        "timing_state": "POST-ARMING",
        "purpose": "Helper-Return Checkpoint: sub_fc1283d2 returned (does NOT prove task_PhySw ran)",
    },
    44: {
        "code": 44,
        "stage_symbol": "STAGE_BC_PRE_FIRMWARE_CONT",
        "context": "Startup Task",
        "file_line": "boot_prototype_ladder.c:442",
        "candidate_line": 354,
        "timing_state": "POST-ARMING",
        "purpose": "Checkpoint: Immediately before pop.w {r4, lr}; b.w sub_fc0d0126 (stock handoff)",
    },
}

# Next expected execution stage map following each table checkpoint
# In the combined candidate (ladder=1, poweron_fix=1):
NEXT_STAGE_MAP: Dict[int, Optional[str]] = {
    1: "STAGE_LOADER_AFTER_COPY",
    2: "STAGE_LOADER_BEFORE_DCACHE",
    3: "STAGE_LOADER_AFTER_DCACHE",
    4: "STAGE_LOADER_BEFORE_ICACHE",
    5: "STAGE_LOADER_AFTER_ICACHE",
    6: "STAGE_LOADER_BEFORE_BX",
    7: "STAGE_BC_CORE_ENTRY",
    11: "STAGE_BC_POST_BSS",
    12: "STAGE_BC_STAGE3_ENTRY",
    13: "STAGE_BC_PRE_KERNEL_INIT",
    14: "STAGE_BC_STAGE4_ENTRY",
    15: "STAGE_BC_STAGE5_ENTRY",
    21: "STAGE_BC_PRE_MPU_SETUP",
    22: "STAGE_BC_POST_MPU_SETUP",
    23: "STAGE_BC_PRE_POWER_CHECK",
    24: "STAGE_BC_POWER_CHECK_PASS",
    25: "STAGE_BC_PRE_CREATE_STARTUP",
    26: "STAGE_BC_STARTUP_ENTRY",
    28: "STAGE_BC_HALT_SHUTDOWN",
    29: None,
    31: "STAGE_BC_POST_EARLY_INIT",
    32: "STAGE_BC_PRE_SD1STINIT",
    33: "STAGE_BC_POST_SD1STINIT",
    34: "STAGE_BC_PRE_WATCHDOG_START",
    35: "STAGE_BC_POST_WATCHDOG_START",
    41: "STAGE_BC_PRE_PHYSW_CREATE",
    42: "STAGE_BC_POST_PHYSW_CREATE",
    43: "STAGE_BC_PRE_FIRMWARE_CONT",
    44: "STOCK_BOOT_SUCCESS",
}

# All valid trial classification categories: exactly 29 CODE_<N> classes plus 5 special categories
VALID_CLASSES: Set[str] = {
    *(f"CODE_{c}" for c in LADDER_STAGE_TABLE),
    "NO_PULSES",
    "UNKNOWN_CODE",
    "AMBIGUOUS",
    "INVALID_CANDIDATE",
    "CONTROL_HELD_O1",
}


class SafetyViolationError(ValueError):
    """Raised when an access to a forbidden file path (.bin, .rom, PRIMARY*) is attempted."""
    pass


def validate_safety_path(path: Union[str, Path]) -> Path:
    """Enforces Phase 0 read-only safety rules on input file paths.
    
    Refuses any path that:
    - ends in .bin, .rom, or .BIN (case-insensitive)
    - has a basename starting with PRIMARY (case-insensitive)
    """
    p = Path(path)
    name = p.name
    name_lower = name.lower()
    suffix_lower = p.suffix.lower()

    if suffix_lower in (".bin", ".rom") or name_lower.endswith((".bin", ".rom")):
        raise SafetyViolationError(
            f"Safety violation: forbidden access to binary or ROM file path '{path}'"
        )

    if name.upper().startswith("PRIMARY"):
        raise SafetyViolationError(
            f"Safety violation: forbidden access to PRIMARY file path '{path}'"
        )

    return p


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

    # 1. Parse markdown table rows:
    # | **1** | `STAGE_LOADER_AFTER_PROLOGUE` | Loader | `loader_main_breadcrumb.c:45` | Pre-Arming | Step 1... |
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

    # 2. Parse section 5.1 bullet entries:
    # - **Code 28** (`STAGE_BC_FAIL_POWER_CUT`, `boot_prototype_ladder.c:357`, Initial Task): Flashes...
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
    """Validates and extracts the stage table combining build source emit sites and doc stage symbols.
    
    Verifies that the p25-t3b build source emit sites exactly match the specification table.
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    doc_path = repo_root / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"
    doc_table = parse_ladder_table_from_source(doc_path)

    build_info = extract_build_source_pulse_codes(repo_root)
    emitted_codes = set(build_info["all_emitted_codes"])

    if emitted_codes != set(doc_table.keys()):
        raise ValueError(
            f"Build source emit codes mismatch with doc table: "
            f"build={sorted(emitted_codes)}, doc={sorted(doc_table.keys())}"
        )

    # Cross-verify loader stage symbols
    for step_num, stage_sym in build_info["loader_steps"].items():
        if doc_table[step_num]["stage_symbol"] != stage_sym:
            raise ValueError(
                f"Loader stage symbol mismatch for code {step_num}: "
                f"build={stage_sym}, doc={doc_table[step_num]['stage_symbol']}"
            )

    return doc_table


def parse_expected_diskboot_sha256(doc_path: Optional[Path] = None) -> str:
    """Parses the expected PORT-25 combined candidate SHA-256 from docs/PORT25_LADDER_FIX_CANDIDATE.md:385."""
    if doc_path is None:
        doc_path = REPO_ROOT / "docs" / "PORT25_LADDER_FIX_CANDIDATE.md"

    validate_safety_path(doc_path)

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Search for PORT-25 Combined Candidate row in Section 6 (line 385)
    m = re.search(
        r"\|\s*\*\*PORT-25 Combined Candidate\*\*\s*\|[^|]*\|\s*`?([0-9a-fA-F]{64})`?\s*\|",
        content,
    )
    if not m:
        raise ValueError(f"Could not locate PORT-25 Combined Candidate SHA-256 in {doc_path}")

    return m.group(1).lower()


def parse_owner_report(input_data: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    """Parses an owner trial report from a dict, raw text (JSON or key=value), or a safe file path.
    
    Fields extracted:
      - diskboot_sha256: string
      - press: string ('short' or 'held')
      - pulses: integer, list of integers, or 'none'
      - lcd: string
      - inspector_status: string
      - uncertain / uncertainty: optional flags for ambiguity detection
      - notes: optional notes
    """
    if isinstance(input_data, dict):
        return dict(input_data)

    # First enforce path safety on string/Path inputs if they have path-like signatures
    if isinstance(input_data, (str, Path)):
        p_str = str(input_data).strip()
        p_candidate = Path(p_str)
        if (
            p_candidate.suffix.lower() in (".bin", ".rom")
            or p_candidate.name.upper().startswith("PRIMARY")
            or p_candidate.name.lower().endswith((".bin", ".rom"))
        ):
            validate_safety_path(p_candidate)

    raw_text: str = ""
    is_path_candidate = isinstance(input_data, Path) or (
        isinstance(input_data, str) and (os.path.exists(input_data) or "/" in input_data)
    )
    if is_path_candidate:
        try:
            path_obj = Path(input_data)
            validate_safety_path(path_obj)
            if path_obj.is_file():
                with open(path_obj, "rb") as bf:
                    raw_bytes = bf.read()
                if b"\x00" in raw_bytes:
                    raise SafetyViolationError(f"Safety violation: refused binary content in {path_obj}")
                raw_text = raw_bytes.decode("utf-8")
        except SafetyViolationError:
            raise
        except (OSError, ValueError):
            raw_text = str(input_data)

    if not raw_text:
        raw_text = str(input_data).strip()

    # Try parsing as JSON first
    if raw_text.startswith("{") and raw_text.endswith("}"):
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

    # Parse simple key=value or key: value text format
    report: Dict[str, Any] = {}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        sep = "=" if "=" in line else (":" if ":" in line else None)
        if sep is None:
            continue

        key, val = line.split(sep, 1)
        key = key.strip().lower()
        val = val.strip()

        # Strip surrounding quotes if present
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1].strip()

        # Canonicalize field values
        if key == "pulses":
            val_lower = val.lower()
            if val_lower in ("none", "null", "no_pulses", "0", ""):
                report[key] = "none"
            elif val.startswith("[") and val.endswith("]"):
                try:
                    report[key] = [int(x.strip()) for x in val[1:-1].split(",") if x.strip()]
                except ValueError:
                    report[key] = val
            elif "," in val:
                try:
                    report[key] = [int(x.strip()) for x in val.split(",") if x.strip()]
                except ValueError:
                    report[key] = val
            else:
                try:
                    report[key] = int(val)
                except ValueError:
                    # Check if uncertainty notation in pulses (e.g. "24 (uncertain)" or "24?")
                    m_int = re.search(r"\b(\d+)\b", val)
                    if m_int:
                        report[key] = int(m_int.group(1))
                        if "uncertain" in val_lower or "?" in val:
                            report["uncertain"] = True
                    else:
                        report[key] = val
        elif key in ("uncertain", "uncertainty"):
            report["uncertain"] = is_truthy(val)
        elif key == "diskboot_sha256":
            report[key] = val.lower()
        elif key == "press":
            report[key] = val.lower()
        else:
            report[key] = val

    return report


def is_count_adjacent_to_two_valid_codes(
    count: int,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> bool:
    """Evaluates the off-by-one adjacency rule:
    Returns True if and only if BOTH immediate neighbours (count - 1) and (count + 1)
    are registered codes in the source table.
    """
    return (count - 1 in table) and (count + 1 in table)


def classify_owner_report(
    input_data: Union[Dict[str, Any], str, Path],
    expected_sha256: str = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> Dict[str, Any]:
    """Classifies an owner trial report into a deterministic outcome structure.
    
    Returns a dict with:
      - class: string (CODE_<N>, NO_PULSES, UNKNOWN_CODE, AMBIGUOUS, INVALID_CANDIDATE, CONTROL_HELD_O1)
      - last_stage_reached: string or None
      - next_stage: string or None
      - evidence: string citation
      - notes: string explanation
    """
    report = parse_owner_report(input_data)

    reported_sha256 = str(report.get("diskboot_sha256", "")).strip().lower()
    press = str(report.get("press", "short")).strip().lower()
    pulses_raw = report.get("pulses", "none")
    lcd = str(report.get("lcd", "")).strip().lower()
    inspector_status = str(report.get("inspector_status", "")).strip().lower()
    notes_in = str(report.get("notes", "")).strip()

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
    # Condition: Held button press that successfully booted into the stock UI.
    # Citations: docs/PORT24_POWERON_FIX.md:19-24, docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55,
    #            docs/PORT25_OWNER_TRIAL_PLAN.md:162-173
    stock_ui_indicators = (
        "stock_ui", "stock ui", "live_view", "live view", "shooting",
        "canon_ui", "canon ui", "stock", "booted", "menu"
    )
    stock_inspector_indicators = ("o1", "o6", "witness_invalid", "reached", "pass", "ok")

    reached_stock_ui = (
        any(ind in lcd for ind in stock_ui_indicators)
        or any(ind == inspector_status for ind in stock_inspector_indicators)
    )

    if press == "held" and reached_stock_ui:
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

    # 3. Canonicalize pulses
    # Pulses can be:
    # - 'none' / None / 0 -> NO_PULSES
    # - list of ints -> single count or AMBIGUOUS (conflicting multiple counts)
    # - int -> single count
    count_resolved: Optional[int] = None
    is_ambiguous_multiple = False

    if pulses_raw in ("none", "null", "NONE", None, "", 0, "0"):
        count_resolved = None
    elif isinstance(pulses_raw, list):
        int_list: List[int] = []
        for x in pulses_raw:
            try:
                int_list.append(int(x))
            except (ValueError, TypeError):
                pass
        unique_counts = sorted(list(set(int_list)))
        if len(unique_counts) == 0:
            count_resolved = None
        elif len(unique_counts) == 1:
            count_resolved = unique_counts[0]
        else:
            is_ambiguous_multiple = True
    elif isinstance(pulses_raw, (int, float)):
        count_resolved = int(pulses_raw)
    elif isinstance(pulses_raw, str):
        if pulses_raw.strip().lower() in ("none", "null", "0", ""):
            count_resolved = None
        else:
            try:
                count_resolved = int(pulses_raw.strip())
            except ValueError:
                # Try finding integer in string (e.g. '24 (uncertain)')
                m_int = re.search(r"\b(\d+)\b", pulses_raw)
                if m_int:
                    count_resolved = int(m_int.group(1))
                else:
                    count_resolved = None

    # Handle Conflicting Multiple Counts
    if is_ambiguous_multiple:
        return {
            "class": "AMBIGUOUS",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
            "notes": (
                f"Conflicting multiple pulse counts reported: {pulses_raw}. "
                "Unable to definitively isolate terminal stage due to conflicting observations."
            ),
        }

    # Handle NO_PULSES
    if count_resolved is None:
        return {
            "class": "NO_PULSES",
            "last_stage_reached": None,
            "next_stage": "STAGE_LOADER_AFTER_PROLOGUE",
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:201; docs/PORT25_LADDER_FIX_CANDIDATE.md:328",
            "notes": (
                "Zero pulses observed (camera dark from start). Camera remained unpowered, "
                "StartDiskboot did not execute loader (card lock / VBR issue), or loader stalled "
                "in check_compat() before Step 1 pulse (docs/PORT25_OWNER_TRIAL_PLAN.md:201)."
            ),
        }

    # 4. Check Off-By-One Uncertainty Rule
    # "AMBIGUOUS for conflicting multiple counts, or a count adjacent to two valid codes
    #  when the owner flags uncertainty (an off-by-one rule; define it explicitly and document it)"
    uncertain_val = report.get("uncertain")
    uncertainty_val = report.get("uncertainty")

    explicit_uncertain = is_truthy(uncertain_val) or is_truthy(uncertainty_val)
    explicit_not_uncertain = (
        (uncertain_val is not None and not is_truthy(uncertain_val))
        or (uncertainty_val is not None and not is_truthy(uncertainty_val))
    )

    if explicit_uncertain:
        uncertainty_flagged = True
    elif explicit_not_uncertain:
        uncertainty_flagged = False
    else:
        uncertainty_flagged = (
            "uncertain" in notes_in.lower()
            or "uncertain" in str(pulses_raw).lower()
            or "?" in str(pulses_raw)
        )

    if uncertainty_flagged and is_count_adjacent_to_two_valid_codes(count_resolved, table):
        prev_sym = table[count_resolved - 1]["stage_symbol"]
        next_sym = table[count_resolved + 1]["stage_symbol"]
        return {
            "class": "AMBIGUOUS",
            "last_stage_reached": None,
            "next_stage": None,
            "evidence": "docs/PORT25_OWNER_TRIAL_PLAN.md:155-161; docs/PORT25_LADDER_FIX_CANDIDATE.md:265, 274",
            "notes": (
                f"Owner flagged uncertainty on pulse count {count_resolved}, which is adjacent to two valid "
                f"codes ({count_resolved - 1}: {prev_sym}, {count_resolved + 1}: {next_sym}). "
                "Classified as AMBIGUOUS under the off-by-one uncertainty rule."
            ),
        }

    # 5. Check In-Table Code (emits only the 29 registered codes)
    if count_resolved in table:
        entry = table[count_resolved]
        stage_symbol = entry["stage_symbol"]
        next_stage = NEXT_STAGE_MAP.get(count_resolved)
        candidate_line = entry.get("candidate_line", 328)
        file_line = entry.get("file_line", "boot_prototype.c")
        purpose = entry.get("purpose", "")
        context = entry.get("context", "")

        note_text = f"{purpose} ({context})."
        if uncertainty_flagged:
            note_text += " (Note: owner flagged uncertainty, but count is not adjacent to two valid codes)."

        return {
            "class": f"CODE_{count_resolved}",
            "last_stage_reached": stage_symbol,
            "next_stage": next_stage,
            "evidence": f"docs/PORT25_LADDER_FIX_CANDIDATE.md:{candidate_line}; {file_line}",
            "notes": note_text,
        }

    # 6. Out-of-Table Code (all in-range gaps within 1..44 and out-of-range counts map here)
    return {
        "class": "UNKNOWN_CODE",
        "last_stage_reached": None,
        "next_stage": None,
        "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354",
        "notes": (
            f"Pulse count {count_resolved} does not match any registered code in the PORT-25 "
            "ladder stage table (valid codes: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44)."
        ),
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
