#!/usr/bin/env python3
"""PORT-22 T1: Deterministic Session Outcome Classifier (H1-H4).

Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p22-t1-session-classifier
Milestone: PORT-22 (Session Ingest & Outcome Classification)

Source of truth:
  docs/PORT21_OWNER_SESSION_PLAN.md, lines 169-175
  Section 3: "Comprehensive Prediction Table for Hypotheses H1–H4"

Hypothesis rules & line citations:
- H1: docs/PORT21_OWNER_SESSION_PLAN.md:171
- H2: docs/PORT21_OWNER_SESSION_PLAN.md:172
- H3: docs/PORT21_OWNER_SESSION_PLAN.md:173
- H4: docs/PORT21_OWNER_SESSION_PLAN.md:174
Wildcard fields (card_lock_state, startup_timing) not specified in table:
  Treated as wildcards per docs/PORT21_OWNER_SESSION_PLAN.md:169-175.

This tool reads a JSON owner session report containing:
- RAMCMP readings (r_l8, r_l4, r_c4, r_ct, r_wm)
- PORT-20 LED observations (GPIO 33, 0xD20B0884)
- SD card lock state (card_lock_state)
- Start-up timing (startup_timing)
- Optional Inspector OSD title/status (extend.m)

It outputs:
- A matching hypothesis (H1, H2, H3, or H4) if uniquely matched
- AMBIGUOUS with matching hypotheses and detailed reason if multiple match
- INCONSISTENT with detailed reason if readings contradict every hypothesis or each other

CLI rules:
- Pure Python standard library only.
- Accepts JSON file path or stdin (-).
- Refuses any path ending in .bin (case-insensitive) or with basename starting with PRIMARY.
- Exits with non-zero code on malformed JSON, missing fields, wrong types, or refused paths.
- Deterministic output ordering; provides --json flag for machine-readable JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# =============================================================================
# SOURCE OF TRUTH: PORT-21 T4 PLAN PREDICTION TABLE
# Document: docs/PORT21_OWNER_SESSION_PLAN.md
# Line range: 169-175
# =============================================================================

TABLE_SOURCE_PATH: str = "docs/PORT21_OWNER_SESSION_PLAN.md"
TABLE_START_LINE: int = 169
TABLE_END_LINE: int = 175

# Encoded table from docs/PORT21_OWNER_SESSION_PLAN.md:169-175
# Exact text row by row and column by column:
ENCODED_TABLE: Dict[str, Any] = {
    "path": TABLE_SOURCE_PATH,
    "line_range": (TABLE_START_LINE, TABLE_END_LINE),
    "columns": [
        "Hypothesis ID & Summary",
        "`r_l8` (RAMCMP at `0x00008000`)",
        "`r_l4` (RAMCMP at `0x40008000`)",
        "`r_c4` (RAMCMP at `0x003489B4`)",
        "`r_ct` (RAMCMP Core Continuation)",
        "`r_wm` (RAMCMP Witness at `0x0035F7A0`)",
        "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)",
        "Inspector OSD Title & Status (`extend.m`)",
    ],
    "rows": {
        "H1": {
            "Hypothesis ID & Summary": "**H1**: `StartDiskboot` never reached loader (ROM rejected binary or skipped)",
            "`r_l8` (RAMCMP at `0x00008000`)": "`0` (differs / stock Low RAM initialized data) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:221, 282]`",
            "`r_l4` (RAMCMP at `0x40008000`)": "`0` (differs / unwritten DRAM: ROM rejected before copy) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:221, 282; docs/PORT21_DISKBOOT_TIMING.md:298-302]`",
            "`r_c4` (RAMCMP at `0x003489B4`)": "`0` (differs / unwritten core) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:282]`",
            "`r_ct` (RAMCMP Core Continuation)": "`0` (differs / continuation code absent) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:282]`",
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "`0` (differs / unwritten witness) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:282]`",
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "**NO PULSE** (0 s delay, normal stock LED sequence; rejected before loader prologue) `[INFERRED: origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_LED_CANDIDATE.md:31-37; docs/PORT21_DISKBOOT_TIMING.md:20-22]`",
            "Inspector OSD Title & Status (`extend.m`)": "`WITNESS_INVALID` / `INVALID / CORRUPT` (Color 3, Light Blue) `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:220-222; tools/validate_witness_inspector.py:273]`",
        },
        "H2": {
            "Hypothesis ID & Summary": "**H2**: Loader reached, but hung in `check_compat()`",
            "`r_l8` (RAMCMP at `0x00008000`)": "`UNREACHABLE / UNKNOWN` (camera hangs in `check_compat()`; watchdog reset is UNKNOWN) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
            "`r_l4` (RAMCMP at `0x40008000`)": "`UNREACHABLE / UNKNOWN` (camera hangs in `check_compat()`; watchdog reset is UNKNOWN) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
            "`r_c4` (RAMCMP at `0x003489B4`)": "`UNREACHABLE / UNKNOWN` (camera hangs in `check_compat()`; core copy never ran) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
            "`r_ct` (RAMCMP Core Continuation)": "`UNREACHABLE / UNKNOWN` (camera hangs in `check_compat()`; continuation absent) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "`UNREACHABLE / UNKNOWN` (camera hangs in `check_compat()`; witness write never ran) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "**PULSES ~1-2 s** in loader entry prologue, then hangs in `check_compat()`; subsequent blink activity on PORT-20 LED is UNKNOWN `[INFERRED / UNKNOWN: origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_LED_CANDIDATE.md:31-37; docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:280-282]`",
            "Inspector OSD Title & Status (`extend.m`)": "**UNREACHABLE / UNKNOWN** (camera hangs before stock UI; Canon Basic cannot run without watchdog reset) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`",
        },
        "H3": {
            "Hypothesis ID & Summary": "**H3**: Loader wrote witness, but stock boot later overwrote `0x0035F7A0`",
            "`r_l8` (RAMCMP at `0x00008000`)": "`0` (differs / overwritten by Boot Moment 2 copy loop) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:215-221, 267]`",
            "`r_l4` (RAMCMP at `0x40008000`)": "`UNKNOWN` (T1/T2 conflict: T1:221,293 predicts `0` via post-reboot overwrite; T2:298-302 predicts `1` in uncached DRAM alias) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:221, 293; docs/PORT21_DISKBOOT_TIMING.md:298-302]`",
            "`r_c4` (RAMCMP at `0x003489B4`)": "`UNKNOWN` (`0` if overwritten by stock heap, but whether stock boot overwrites `0x003489B4` before Canon Basic runs is UNKNOWN) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:247-249, 269, 290]`",
            "`r_ct` (RAMCMP Core Continuation)": "`UNKNOWN` (`0` if overwritten by stock heap, but overwrite timing before Canon Basic is UNKNOWN) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:247-249, 269, 290]`",
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "`UNKNOWN` (`0` if destroyed by stock heap allocations, but actual overwrite before Canon Basic is UNKNOWN) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:47, 247-249, 269, 290]`",
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "**PULSES ~1-2 s** (loader entry executed prologue) `[INFERRED: origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_LED_CANDIDATE.md:31-37, 189; origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_OWNER_SESSION.md:38-44]`",
            "Inspector OSD Title & Status (`extend.m`)": "`WITNESS_INVALID` / `INVALID / CORRUPT` (Color 3, Light Blue) `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:225-226; tools/validate_witness_inspector.py:273]`",
        },
        "H4": {
            "Hypothesis ID & Summary": "**H4**: Witness record at `0x0035F7A0` was malformed as built",
            "`r_l8` (RAMCMP at `0x00008000`)": "`0` (differs / overwritten by Boot Moment 2 copy loop) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:215-221, 267]`",
            "`r_l4` (RAMCMP at `0x40008000`)": "`UNKNOWN` (T1/T2 conflict: T1:221,293 predicts `0`; T2:298-302 predicts `1` in uncached DRAM alias) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:221, 293; docs/PORT21_DISKBOOT_TIMING.md:298-302]`",
            "`r_c4` (RAMCMP at `0x003489B4`)": "`1` (matches `REF_C.BIN` protected by shifted heap `new_sa = 0x00366CB0`) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:238, 295]`",
            "`r_ct` (RAMCMP Core Continuation)": "`1` (matches core continuation intact) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:238, 295]`",
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "`0` (differs / checksum or field malformed while magic intact) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:295; docs/PORT21_WITNESS_AUDIT.md:162-176]`",
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "**PULSES ~1-2 s** (loader entry executed prologue) `[INFERRED: origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_LED_CANDIDATE.md:31-37, 189; origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_OWNER_SESSION.md:38-44]`",
            "Inspector OSD Title & Status (`extend.m`)": "`WITNESS_INVALID` / `INVALID / CORRUPT` (Color 3, Light Blue) `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:162-176; tools/validate_witness_inspector.py:273]`",
        },
        "Alternative / Baseline": {
            "Hypothesis ID & Summary": "**Alternative / Baseline**: Candidate Succeeded (O6 was tracked `0x780` payload error)",
            "`r_l8` (RAMCMP at `0x00008000`)": "`0` (differs / overwritten by Boot Moment 2 copy loop) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:215-221, 267]`",
            "`r_l4` (RAMCMP at `0x40008000`)": "`UNKNOWN` (T1/T2 conflict: T1:221 predicts `0`; T2:298-302 predicts `1` in uncached DRAM alias) `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:221; docs/PORT21_DISKBOOT_TIMING.md:298-302]`",
            "`r_c4` (RAMCMP at `0x003489B4`)": "`1` (matches `REF_C.BIN` protected by shifted heap) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:238]`",
            "`r_ct` (RAMCMP Core Continuation)": "`1` (matches core continuation intact) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:238]`",
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "`1` (matches valid witness struct at `0x0035F7A0`) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:238; docs/PORT21_WITNESS_AUDIT.md:27-38]`",
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "**PULSES ~1-2 s** (loader entry executed prologue) `[INFERRED: origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_LED_CANDIDATE.md:31-37, 189; origin/agentbridge/g3x-lite/port-20-boot-signal/integration docs/PORT20_OWNER_SESSION.md:38-44]`",
            "Inspector OSD Title & Status (`extend.m`)": "**`LOADER_REACHED`** (Color 1,4 White/Yellow) or **`CONT_ATTEMPTED`** (Color 4,4 Yellow/Yellow) `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:33-38; tools/validate_witness_inspector.py:266, 271]`",
        },
    },
}

# =============================================================================
# EXPLICIT HYPOTHESIS RULES & CITATIONS
# =============================================================================
#
# RULE H1 (docs/PORT21_OWNER_SESSION_PLAN.md:171):
#   - r_l8 == 0
#   - r_l4 == 0 (unwritten DRAM: ROM rejected before copy)
#   - r_c4 == 0 (unwritten core)
#   - r_ct == 0 (continuation absent)
#   - r_wm == 0 (unwritten witness)
#   - LED: NO PULSE (0 s delay, normal stock LED sequence; rejected before loader)
#   - OSD: WITNESS_INVALID / INVALID / CORRUPT (Light Blue)
#   - Wildcard fields: card_lock_state, startup_timing are not specified as table
#     columns in docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and are treated as wildcards
#     per line 171.
#
# RULE H2 (docs/PORT21_OWNER_SESSION_PLAN.md:172):
#   - r_l8, r_l4, r_c4, r_ct, r_wm: UNREACHABLE / UNKNOWN (camera hangs in
#     check_compat(); Canon Basic cannot run without watchdog reset)
#   - LED: PULSES ~1-2 s in loader entry prologue, then hangs in check_compat()
#   - OSD: UNREACHABLE / UNKNOWN (camera hangs before stock UI)
#   - Wildcard fields: card_lock_state, startup_timing are not specified as table
#     columns in docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and are treated as wildcards
#     per line 172.
#
# RULE H3 (docs/PORT21_OWNER_SESSION_PLAN.md:173):
#   - r_l8 == 0 (overwritten by Boot Moment 2 copy loop)
#   - r_l4: UNKNOWN (T1/T2 conflict: T1 predicts 0 via overwrite, T2 predicts 1
#     in uncached DRAM alias) -> treated as wildcard per line 173.
#   - r_c4: 0 (predicted 0 if overwritten by stock heap; docs/PORT21_OWNER_SESSION_PLAN.md:159, 203, 225)
#   - r_ct: 0 (predicted 0 if overwritten by stock heap; docs/PORT21_OWNER_SESSION_PLAN.md:159, 203, 225)
#   - r_wm: 0 (predicted 0 if destroyed by stock heap; docs/PORT21_OWNER_SESSION_PLAN.md:159, 203, 225)
#   - LED: PULSES ~1-2 s (loader entry executed prologue)
#   - OSD: WITNESS_INVALID / INVALID / CORRUPT (Light Blue)
#   - Wildcard fields: card_lock_state, startup_timing are not specified as table
#     columns in docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and are treated as wildcards
#     per line 173.
#
# RULE H4 (docs/PORT21_OWNER_SESSION_PLAN.md:174):
#   - r_l8 == 0 (overwritten by Boot Moment 2 copy loop)
#   - r_l4: UNKNOWN (T1/T2 conflict: T1 predicts 0, T2 predicts 1) -> treated
#     as wildcard per line 174.
#   - r_c4 == 1 (matches REF_C.BIN protected by shifted heap new_sa = 0x00366CB0)
#   - r_ct == 1 (matches core continuation intact)
#   - r_wm == 0 (differs / checksum or field malformed while magic intact)
#   - LED: PULSES ~1-2 s (loader entry executed prologue)
#   - OSD: WITNESS_INVALID / INVALID / CORRUPT (Light Blue)
#   - Wildcard fields: card_lock_state, startup_timing are not specified as table
#     columns in docs/PORT21_OWNER_SESSION_PLAN.md:169-175 and are treated as wildcards
#     per line 174.


class RefusalError(Exception):
    """Raised when an input path is refused due to Phase 0 safety invariants."""
    pass


class ValidationError(Exception):
    """Raised when JSON input is malformed, missing required fields, or has wrong types."""
    pass


def validate_path_safety(path_str: str) -> Path:
    """Validates that a path is safe to access according to Phase 0 rules.
    
    Refuses:
    - Paths ending in .bin (case-insensitive)
    - Paths whose basename starts with PRIMARY (case-sensitive and insensitive)
    """
    p = Path(path_str)
    name = p.name
    
    if name.lower().endswith(".bin"):
        raise RefusalError(f"Refusing binary file path ending in .bin: '{path_str}'")
        
    if name.upper().startswith("PRIMARY"):
        raise RefusalError(f"Refusing path with basename starting with PRIMARY: '{path_str}'")
        
    return p


REQUIRED_TOP_LEVEL_FIELDS: Tuple[str, ...] = (
    "card_lock_state",
    "startup_timing",
    "port20_led",
    "ramcmp",
)

REQUIRED_RAMCMP_FIELDS: Tuple[str, ...] = (
    "r_l8",
    "r_l4",
    "r_c4",
    "r_ct",
    "r_wm",
)


def normalize_led_observation(val: Any) -> str:
    """Normalizes the PORT-20 LED observation to PULSE, NO_PULSE, or UNOBSERVED."""
    if isinstance(val, bool):
        return "PULSE" if val else "NO_PULSE"
    if isinstance(val, dict):
        pulse = val.get("pulse", val.get("pulse_observed", val.get("led_pulse")))
        if pulse is None:
            return "UNOBSERVED"
        return "PULSE" if bool(pulse) else "NO_PULSE"
    if isinstance(val, str):
        v = val.strip().upper()
        if any(term in v for term in ("NO PULSE", "NO_PULSE", "0 S DELAY", "NONE", "NO_BLINK", "OFF")):
            return "NO_PULSE"
        if any(term in v for term in ("PULSE", "PULSES", "BLINK", "YES", "1-2 S", "FLASH")):
            return "PULSE"
        if any(term in v for term in ("UNOBSERVED", "UNKNOWN", "UNRECORDED", "N/A", "MISSING")):
            return "UNOBSERVED"
        # If string doesn't match known patterns:
        return v
    raise ValidationError(f"Invalid type for 'port20_led': expected str, bool, or dict, got {type(val).__name__}")


def normalize_ramcmp_value(val: Any) -> Optional[int]:
    """Normalizes a single RAMCMP comparison value (0, 1, or None for UNKNOWN/UNREACHABLE)."""
    if val is None:
        return None
    if isinstance(val, int):
        if val in (0, 1):
            return val
        raise ValidationError(f"Invalid RAMCMP integer value: {val} (expected 0 or 1)")
    if isinstance(val, str):
        v = val.strip().upper()
        if v in ("0", "ZERO", "DIFFERS"):
            return 0
        if v in ("1", "ONE", "MATCHES"):
            return 1
        if any(term in v for term in ("UNKNOWN", "UNREACHABLE", "N/A", "WILDCARD", "*")):
            return None
        raise ValidationError(f"Unrecognized RAMCMP string value: '{val}'")
    raise ValidationError(f"Invalid type for RAMCMP value: expected int, str, or null, got {type(val).__name__}")


def parse_and_validate_report(raw_data: Union[str, bytes, dict]) -> Dict[str, Any]:
    """Parses JSON data and validates all required fields and types."""
    if isinstance(raw_data, (str, bytes)):
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Malformed JSON: {e}")
    elif isinstance(raw_data, dict):
        data = raw_data
    else:
        raise ValidationError(f"Expected JSON object/dict, got {type(raw_data).__name__}")

    if not isinstance(data, dict):
        raise ValidationError(f"Top-level JSON must be an object/dict, got {type(data).__name__}")

    # Check top-level required fields
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            # Check common aliases
            if field == "card_lock_state" and "card_locked" in data:
                continue
            if field == "startup_timing" and "start_up_timing" in data:
                continue
            if field == "port20_led" and ("led_observation" in data or "port20_led_observation" in data):
                continue
            raise ValidationError(f"Missing required field: '{field}'")

    # Validate card_lock_state
    cls_val = data.get("card_lock_state", data.get("card_locked"))
    if not isinstance(cls_val, (str, bool)):
        raise ValidationError(f"Invalid type for 'card_lock_state': expected string or bool, got {type(cls_val).__name__}")

    # Validate startup_timing
    timing_val = data.get("startup_timing", data.get("start_up_timing"))
    if not isinstance(timing_val, (str, int, float)):
        raise ValidationError(f"Invalid type for 'startup_timing': expected string or number, got {type(timing_val).__name__}")

    # Validate port20_led
    led_val = data.get("port20_led", data.get("led_observation", data.get("port20_led_observation")))
    if not isinstance(led_val, (str, bool, dict)):
        raise ValidationError(f"Invalid type for 'port20_led': expected string, bool, or dict, got {type(led_val).__name__}")
    normalized_led = normalize_led_observation(led_val)

    # Validate ramcmp
    ramcmp_val = data.get("ramcmp")
    ramcmp_normalized: Optional[Dict[str, Optional[int]]] = None
    is_ramcmp_unreachable = False

    if ramcmp_val is None:
        is_ramcmp_unreachable = True
    elif isinstance(ramcmp_val, str):
        if any(term in ramcmp_val.upper() for term in ("UNREACHABLE", "HANG", "NONE", "N/A", "UNKNOWN")):
            is_ramcmp_unreachable = True
        else:
            raise ValidationError(f"Invalid string value for 'ramcmp': '{ramcmp_val}'")
    elif isinstance(ramcmp_val, dict):
        for field in REQUIRED_RAMCMP_FIELDS:
            if field not in ramcmp_val:
                raise ValidationError(f"Missing required RAMCMP field: '{field}'")
        ramcmp_normalized = {
            field: normalize_ramcmp_value(ramcmp_val[field])
            for field in REQUIRED_RAMCMP_FIELDS
        }
        # Check if all values are unreachable/unknown
        if all(v is None for v in ramcmp_normalized.values()):
            is_ramcmp_unreachable = True
    else:
        raise ValidationError(f"Invalid type for 'ramcmp': expected dict, null, or string, got {type(ramcmp_val).__name__}")

    # Validate inspector_osd if present
    osd_val = data.get("inspector_osd", data.get("inspector_status"))
    if osd_val is not None and not isinstance(osd_val, str):
        raise ValidationError(f"Invalid type for 'inspector_osd': expected string or null, got {type(osd_val).__name__}")

    return {
        "synthetic": bool(data.get("synthetic", False)),
        "card_lock_state": str(cls_val),
        "startup_timing": timing_val,
        "port20_led": normalized_led,
        "ramcmp": ramcmp_normalized,
        "is_ramcmp_unreachable": is_ramcmp_unreachable,
        "inspector_osd": osd_val,
    }


def evaluate_hypothesis_h1(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Checks whether the report matches Hypothesis H1 (StartDiskboot rejected binary).
    
    Source citation: docs/PORT21_OWNER_SESSION_PLAN.md:171.
    """
    reasons = []
    # LED rule: NO PULSE (0 s delay)
    led = report["port20_led"]
    if led == "PULSE":
        return False, ["LED pulse observed (H1 predicts NO PULSE)"]
    if led == "NO_PULSE":
        reasons.append("LED shows NO PULSE (fits H1)")
    elif led == "UNOBSERVED":
        reasons.append("LED unobserved (plausible for H1)")

    # RAMCMP rule: RAM was not unreachable, all 5 fields == 0
    if report["is_ramcmp_unreachable"]:
        return False, ["RAMCMP is UNREACHABLE (H1 reaches stock UI and Canon Basic runs)"]

    ram = report["ramcmp"]
    if ram is None:
        return False, ["Missing RAMCMP readings for H1"]

    for k in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
        v = ram.get(k)
        if v is not None and v != 0:
            return False, [f"{k} == {v} (H1 predicts {k} == 0)"]
    reasons.append("RAMCMP shows r_l8=0, r_l4=0, r_c4=0, r_ct=0, r_wm=0 (fits H1)")

    # OSD rule: WITNESS_INVALID / INVALID / CORRUPT (or unobserved/null)
    osd = report.get("inspector_osd")
    if osd is not None:
        osd_u = osd.upper()
        if "INVALID" in osd_u or "CORRUPT" in osd_u:
            reasons.append("Inspector OSD shows WITNESS_INVALID (fits H1)")
        elif "LOADER_REACHED" in osd_u or "CONT_ATTEMPTED" in osd_u:
            return False, [f"Inspector OSD shows {osd} (H1 predicts WITNESS_INVALID)"]

    # Wildcard fields: card_lock_state and startup_timing not specified in table
    # per docs/PORT21_OWNER_SESSION_PLAN.md:171, treated as wildcards.
    return True, reasons


def evaluate_hypothesis_h2(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Checks whether the report matches Hypothesis H2 (Loader hung in check_compat).
    
    Source citation: docs/PORT21_OWNER_SESSION_PLAN.md:172.
    """
    reasons = []
    # LED rule: PULSES ~1-2 s in loader entry prologue, then hangs in check_compat()
    led = report["port20_led"]
    if led == "NO_PULSE":
        return False, ["NO PULSE observed (H2 executed loader prologue and pulsed ~1-2 s)"]
    if led == "PULSE":
        reasons.append("LED pulses ~1-2 s (fits H2)")
    elif led == "UNOBSERVED":
        reasons.append("LED unobserved (plausible for H2)")

    # RAMCMP rule: camera hangs before stock UI, so Canon Basic cannot run; RAMCMP is UNREACHABLE
    if not report["is_ramcmp_unreachable"]:
        return False, ["RAMCMP was reachable (H2 hangs before stock UI; Canon Basic cannot run)"]
    reasons.append("Camera hung before stock UI / RAMCMP UNREACHABLE (fits H2)")

    # OSD rule: UNREACHABLE / UNKNOWN
    osd = report.get("inspector_osd")
    if osd is not None and "UNREACHABLE" not in osd.upper() and "UNKNOWN" not in osd.upper():
        return False, [f"Inspector OSD was reachable with {osd} (H2 hangs before stock UI)"]

    # Wildcard fields: card_lock_state and startup_timing not specified in table
    # per docs/PORT21_OWNER_SESSION_PLAN.md:172, treated as wildcards.
    return True, reasons


def evaluate_hypothesis_h3(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Checks whether the report matches Hypothesis H3 (Stock boot later overwrote witness).
    
    Source citation: docs/PORT21_OWNER_SESSION_PLAN.md:173.
    """
    reasons = []
    # LED rule: PULSES ~1-2 s
    led = report["port20_led"]
    if led == "NO_PULSE":
        return False, ["NO PULSE observed (H3 executed loader prologue and pulsed ~1-2 s)"]
    if led == "PULSE":
        reasons.append("LED pulses ~1-2 s (fits H3)")
    elif led == "UNOBSERVED":
        reasons.append("LED unobserved (plausible for H3)")

    # RAMCMP rule: camera reaches stock UI, RAMCMP runs
    if report["is_ramcmp_unreachable"]:
        return False, ["RAMCMP is UNREACHABLE (H3 reaches stock UI and Canon Basic runs)"]

    ram = report["ramcmp"]
    if ram is None:
        return False, ["Missing RAMCMP readings for H3"]

    # r_l8 must be 0
    if ram.get("r_l8") is not None and ram["r_l8"] != 0:
        return False, [f"r_l8 == {ram['r_l8']} (H3 predicts r_l8 == 0)"]

    # r_l4 is UNKNOWN (wildcard due to T1/T2 conflict per line 173) -> any value fits
    reasons.append("r_l4 is treated as wildcard due to T1/T2 conflict (line 173)")

    # r_c4: under H3, stock boot ran without heap shift, yielding r_c4 == 0 (lines 159, 203, 225)
    # If r_c4 == 1, that indicates shifted heap succeeded (H4), refuting H3.
    if ram.get("r_c4") is not None and ram["r_c4"] == 1:
        return False, ["r_c4 == 1 (H3 predicts r_c4 == 0 if overwritten; r_c4 == 1 indicates heap shift succeeded)"]
    
    # r_ct: predicted 0 if overwritten
    if ram.get("r_ct") is not None and ram["r_ct"] == 1:
        return False, ["r_ct == 1 (H3 predicts r_ct == 0 if overwritten; r_ct == 1 indicates core continuation intact)"]

    # r_wm: predicted 0 if overwritten
    if ram.get("r_wm") is not None and ram["r_wm"] == 1:
        return False, ["r_wm == 1 (H3 predicts witness destroyed / r_wm == 0)"]

    reasons.append("RAMCMP shows r_l8=0, r_c4=0, r_ct=0, r_wm=0 (fits H3)")

    # OSD rule: WITNESS_INVALID
    osd = report.get("inspector_osd")
    if osd is not None:
        osd_u = osd.upper()
        if "INVALID" in osd_u or "CORRUPT" in osd_u:
            reasons.append("Inspector OSD shows WITNESS_INVALID (fits H3)")
        elif "LOADER_REACHED" in osd_u or "CONT_ATTEMPTED" in osd_u:
            return False, [f"Inspector OSD shows {osd} (H3 predicts WITNESS_INVALID)"]

    # Wildcard fields: card_lock_state and startup_timing not specified in table
    # per docs/PORT21_OWNER_SESSION_PLAN.md:173, treated as wildcards.
    return True, reasons


def evaluate_hypothesis_h4(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Checks whether the report matches Hypothesis H4 (Witness malformed as built).
    
    Source citation: docs/PORT21_OWNER_SESSION_PLAN.md:174.
    """
    reasons = []
    # LED rule: PULSES ~1-2 s
    led = report["port20_led"]
    if led == "NO_PULSE":
        return False, ["NO PULSE observed (H4 executed loader prologue and pulsed ~1-2 s)"]
    if led == "PULSE":
        reasons.append("LED pulses ~1-2 s (fits H4)")
    elif led == "UNOBSERVED":
        reasons.append("LED unobserved (plausible for H4)")

    # RAMCMP rule: camera reaches stock UI, RAMCMP runs
    if report["is_ramcmp_unreachable"]:
        return False, ["RAMCMP is UNREACHABLE (H4 reaches stock UI and Canon Basic runs)"]

    ram = report["ramcmp"]
    if ram is None:
        return False, ["Missing RAMCMP readings for H4"]

    # r_l8 must be 0
    if ram.get("r_l8") is not None and ram["r_l8"] != 0:
        return False, [f"r_l8 == {ram['r_l8']} (H4 predicts r_l8 == 0)"]

    # r_l4 is UNKNOWN (wildcard due to T1/T2 conflict per line 174) -> any value fits
    reasons.append("r_l4 is treated as wildcard due to T1/T2 conflict (line 174)")

    # r_c4 must be 1 (protected by shifted heap new_sa = 0x00366CB0)
    if ram.get("r_c4") is not None and ram["r_c4"] != 1:
        return False, [f"r_c4 == {ram['r_c4']} (H4 predicts r_c4 == 1 via shifted heap)"]

    # r_ct must be 1 (core continuation intact)
    if ram.get("r_ct") is not None and ram["r_ct"] != 1:
        return False, [f"r_ct == {ram['r_ct']} (H4 predicts r_ct == 1 via core continuation intact)"]

    # r_wm must be 0 (checksum or field malformed while magic intact)
    if ram.get("r_wm") is not None and ram["r_wm"] != 0:
        return False, [f"r_wm == {ram['r_wm']} (H4 predicts r_wm == 0 due to witness malformation)"]

    reasons.append("RAMCMP shows r_l8=0, r_c4=1, r_ct=1, r_wm=0 (fits H4)")

    # OSD rule: WITNESS_INVALID
    osd = report.get("inspector_osd")
    if osd is not None:
        osd_u = osd.upper()
        if "INVALID" in osd_u or "CORRUPT" in osd_u:
            reasons.append("Inspector OSD shows WITNESS_INVALID (fits H4)")
        elif "LOADER_REACHED" in osd_u or "CONT_ATTEMPTED" in osd_u:
            return False, [f"Inspector OSD shows {osd} (H4 predicts WITNESS_INVALID)"]

    # Wildcard fields: card_lock_state and startup_timing not specified in table
    # per docs/PORT21_OWNER_SESSION_PLAN.md:174, treated as wildcards.
    return True, reasons


def classify_session_report(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies an owner session report against hypotheses H1-H4.
    
    Returns a deterministic dictionary:
    {
      "status": "MATCH" | "AMBIGUOUS" | "INCONSISTENT",
      "classification": "H1" | "H2" | "H3" | "H4" | "AMBIGUOUS" | "INCONSISTENT",
      "hypotheses": List of matching hypothesis strings (e.g. ["H1"], ["H1", "H3"], or []),
      "reason": Human-readable explanation with citations,
      "details": Dict of per-hypothesis evaluation reasons
    }
    """
    evaluators = {
        "H1": evaluate_hypothesis_h1,
        "H2": evaluate_hypothesis_h2,
        "H3": evaluate_hypothesis_h3,
        "H4": evaluate_hypothesis_h4,
    }

    matching: List[str] = []
    details: Dict[str, List[str]] = {}

    for h_id in sorted(evaluators.keys()):
        matched, reasons = evaluators[h_id](report_data)
        details[h_id] = reasons
        if matched:
            matching.append(h_id)

    matching_sorted = sorted(matching)

    if len(matching_sorted) == 1:
        matched_h = matching_sorted[0]
        summary_text = ENCODED_TABLE["rows"][matched_h]["Hypothesis ID & Summary"]
        reason = f"Readings uniquely match hypothesis {matched_h}: {summary_text}."
        return {
            "status": "MATCH",
            "classification": matched_h,
            "hypotheses": matching_sorted,
            "reason": reason,
            "details": details,
        }
    elif len(matching_sorted) > 1:
        hyp_str = ", ".join(matching_sorted)
        reason = f"Readings match multiple hypotheses ({hyp_str}). "
        if matching_sorted == ["H1", "H3"]:
            reason += (
                "LED observation is unobserved or ambiguous, so H1 (no pulse) and "
                "H3 (pulse) cannot be distinguished by RAMCMP alone (cite docs/PORT21_OWNER_SESSION_PLAN.md:147)."
            )
        elif matching_sorted == ["H3", "H4"]:
            reason += (
                "RAMCMP r_c4 / r_ct readings are indeterminate, so H3 (overwritten) "
                "and H4 (protected by shifted heap) cannot be separated."
            )
        else:
            reason += "Further discrimination trial is required to resolve ambiguity."
        return {
            "status": "AMBIGUOUS",
            "classification": "AMBIGUOUS",
            "hypotheses": matching_sorted,
            "reason": reason,
            "details": details,
        }
    else:
        # 0 hypotheses matched
        inconsistencies = []
        for h_id, r_list in sorted(details.items()):
            inconsistencies.append(f"{h_id} contradicted: {'; '.join(r_list)}")
        reason = (
            "Readings contradict every hypothesis in docs/PORT21_OWNER_SESSION_PLAN.md:169-175: "
            + "; ".join(inconsistencies)
        )
        return {
            "status": "INCONSISTENT",
            "classification": "INCONSISTENT",
            "hypotheses": [],
            "reason": reason,
            "details": details,
        }


def format_text_output(result: Dict[str, Any]) -> str:
    """Formats classification result as human-readable text."""
    lines = [
        result["classification"],
        f"Reason: {result['reason']}",
    ]
    if result["hypotheses"]:
        lines.append(f"Matching hypotheses: {', '.join(result['hypotheses'])}")
    return "\n".join(lines)


def run_classifier(
    input_source: Union[str, Path, None],
    use_json_output: bool = False,
    stdin_content: Optional[str] = None,
) -> Tuple[int, str]:
    """Executes the classifier on a file path or stdin string.
    
    Returns (exit_code, output_text).
    """
    try:
        if stdin_content is not None or input_source in (None, "-", ""):
            raw_text = stdin_content if stdin_content is not None else sys.stdin.read()
        else:
            p = validate_path_safety(str(input_source))
            if not p.is_file():
                return 1, f"Error: File not found: '{input_source}'"
            raw_text = p.read_text(encoding="utf-8")

        report = parse_and_validate_report(raw_text)
        result = classify_session_report(report)

        if use_json_output:
            # Deterministic sorted json
            out = json.dumps(result, indent=2, sort_keys=True)
        else:
            out = format_text_output(result)

        return 0, out

    except RefusalError as e:
        return 1, f"Error: {e}"
    except ValidationError as e:
        return 2, f"Error: {e}"
    except Exception as e:
        return 1, f"Error: Unexpected failure: {e}"


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="PORT-22 T1: Deterministic session outcome classifier for hypotheses H1-H4.",
    )
    parser.add_argument(
        "report_path",
        nargs="?",
        default="-",
        help="Path to JSON owner session report, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="use_json",
        help="Emit machine-readable JSON output instead of human-readable text.",
    )

    args = parser.parse_args(argv)

    code, output = run_classifier(args.report_path, use_json_output=args.use_json)
    if code != 0:
        sys.stderr.write(output + "\n")
    else:
        sys.stdout.write(output + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
