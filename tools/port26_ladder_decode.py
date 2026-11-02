#!/usr/bin/env python3
"""PORT-26 T1: LED-Code Ladder Decoder Tool (GM1.10C).

Platform: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
Task: p26-t1-ladder-decode
Milestone: PORT-26 (Ladder Ingest & Short-Press Triage)

Single Source of Truth & Citations:
- Pulse-Code Table:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354 (Stage-Code Table, Codes 1..7, 11..15, 21..26, 31..35, 41..44)
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:358-359 (Codes 28 and 29: Fail path when G3X_POWERON_FIX=0)
  - docs/PORT25_SHORT_PRESS_LOCALISE.md:328-351 (Proposed Breadcrumb Placement in boot_prototype.c)
  - docs/PORT25_OWNER_TRIAL_PLAN.md:199-233 (Owner Reading Table: Mapping LED Codes to Stages and T2 Candidates)
  - chdk-port/platform/g3x/sub/110c/boot_prototype.c:88-442 (CHDK boot prototype stages)
  - chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:45-152 (Loader ladder pulse checkpoints, Steps 1..7)
  - chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:217-266 (CORE_LADDER_PULSE_xx macro definitions)
  - tools/build_candidate_port25_ladder_fix.py:73-132 (generate_boot_prototype_ladder_c stage injection)
- Expected Combined Candidate DISKBOOT SHA-256:
  - docs/PORT25_LADDER_FIX_CANDIDATE.md:385 ("9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15")
  - docs/PORT25_OWNER_TRIAL_PLAN.md:30, 51, 81 (Expected candidate size: 124,865 bytes)

Off-By-One Uncertainty Rule Definition:
  An integer count C is considered adjacent to two valid codes if and only if both
  (C - 1) and (C + 1) are members of the set of valid table codes. When the owner report
  flags uncertainty (via uncertain/uncertainty field or uncertainty notation in pulses/notes)
  AND count C is adjacent to two valid codes ((C - 1) in CODES and (C + 1) in CODES),
  the reading cannot be definitively attributed to a single execution stage without ambiguity
  and is classified as AMBIGUOUS. Conversely, if uncertainty is flagged on a count that has
  at most one adjacent valid code (e.g. boundary codes 1, 7, 11, 15, 21, 26, 28, 29, 31, 35, 41, 44),
  or if uncertainty is not flagged, the off-by-one ambiguity rule does not trigger.

Classification Categories:
- CODE_<N>: Valid in-table code count N.
- NO_PULSES: Zero pulses or 'none' reported.
- UNKNOWN_CODE: Pulse counts that are not in the table.
- AMBIGUOUS: Conflicting multiple counts, or a count adjacent to two valid codes with flagged uncertainty.
- INVALID_CANDIDATE: DISKBOOT SHA-256 does not match the expected combined candidate digest.
- CONTROL_HELD_O1: Held button press that boots into the stock user interface (positive control).

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

# Comprehensive ladder stage-code table
# Primary source: docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354, 358-359
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

# All valid trial classification categories
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

        # Find line number in file
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
      - uncertain / notes: optional flags for ambiguity detection
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
            report["uncertain"] = val.lower() in ("true", "yes", "1")
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
    Returns True if and only if BOTH (count - 1) and (count + 1) are valid codes in table.
    """
    return (count - 1 in table) and (count + 1 in table)


def classify_owner_report(
    input_data: Union[Dict[str, Any], str, Path],
    expected_sha256: str = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256,
    table: Dict[int, Dict[str, Any]] = LADDER_STAGE_TABLE,
) -> Dict[str, Any]:
    """Classifies an owner trial report into a deterministic outcome structure.
    
    Returns a dict with:
      - class: string
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
    # - list of ints -> single count or AMBIGUOUS (conflicting counts)
    # - int -> single count
    count_resolved: Optional[int] = None
    is_ambiguous_multiple = False

    if pulses_raw in ("none", "null", "NONE", None, "", 0, "0"):
        count_resolved = None
    elif isinstance(pulses_raw, list):
        # Filter integers
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
                # Try finding integer in string
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
    uncertainty_flagged = (
        bool(report.get("uncertain"))
        or bool(report.get("uncertainty"))
        or "uncertain" in notes_in.lower()
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

    # 5. Check In-Table Code
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

    # 6. Out-of-Table Code
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
