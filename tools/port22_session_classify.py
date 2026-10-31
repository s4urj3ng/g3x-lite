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

Wildcard fields:
- card_lock_state and startup_timing: Not specified as columns in the prediction
  table at docs/PORT21_OWNER_SESSION_PLAN.md:169-175; treated as wildcards per the table.
- H3: r_l4, r_c4, r_ct, r_wm are UNKNOWN in the table at docs/PORT21_OWNER_SESSION_PLAN.md:173;
  treated as explicit WILDCARDs citing line 173.
- H4: r_l4 is UNKNOWN in the table at docs/PORT21_OWNER_SESSION_PLAN.md:174 (T1/T2 conflict);
  treated as an explicit WILDCARD citing line 174.

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

WILDCARD: str = "WILDCARD"

TABLE_COLUMNS: List[str] = [
    "Hypothesis ID & Summary",
    "`r_l8` (RAMCMP at `0x00008000`)",
    "`r_l4` (RAMCMP at `0x40008000`)",
    "`r_c4` (RAMCMP at `0x003489B4`)",
    "`r_ct` (RAMCMP Core Continuation)",
    "`r_wm` (RAMCMP Witness at `0x0035F7A0`)",
    "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)",
    "Inspector OSD Title & Status (`extend.m`)",
]

COLUMN_TO_FIELD: Dict[str, str] = {
    "`r_l8` (RAMCMP at `0x00008000`)": "r_l8",
    "`r_l4` (RAMCMP at `0x40008000`)": "r_l4",
    "`r_c4` (RAMCMP at `0x003489B4`)": "r_c4",
    "`r_ct` (RAMCMP Core Continuation)": "r_ct",
    "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": "r_wm",
    "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": "port20_led",
    "Inspector OSD Title & Status (`extend.m`)": "inspector_osd",
}

# Structured rule table mapping every hypothesis H1-H4 across all table columns
# from docs/PORT21_OWNER_SESSION_PLAN.md:169-175 to explicit expected values or WILDCARDs.
# Each cell explicitly cites its source line in the document.
STRUCTURED_RULE_TABLE: Dict[str, Dict[str, Any]] = {
    "H1": {
        "line": 171,
        "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
        "summary": "StartDiskboot never reached loader (ROM rejected binary or skipped)",
        "columns": {
            "`r_l8` (RAMCMP at `0x00008000`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "`r_l4` (RAMCMP at `0x40008000`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "`r_c4` (RAMCMP at `0x003489B4`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "`r_ct` (RAMCMP Core Continuation)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": {
                "expected": "NO_PULSE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
            "Inspector OSD Title & Status (`extend.m`)": {
                "expected": "WITNESS_INVALID",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:171",
            },
        },
    },
    "H2": {
        "line": 172,
        "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
        "summary": "Loader reached, but hung in check_compat()",
        "columns": {
            "`r_l8` (RAMCMP at `0x00008000`)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "`r_l4` (RAMCMP at `0x40008000`)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "`r_c4` (RAMCMP at `0x003489B4`)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "`r_ct` (RAMCMP Core Continuation)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": {
                "expected": "PULSE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
            "Inspector OSD Title & Status (`extend.m`)": {
                "expected": "UNREACHABLE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:172",
            },
        },
    },
    "H3": {
        "line": 173,
        "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
        "summary": "Loader wrote witness, but stock boot later overwrote 0x0035F7A0",
        "columns": {
            "`r_l8` (RAMCMP at `0x00008000`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "`r_l4` (RAMCMP at `0x40008000`)": {
                "expected": WILDCARD,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "`r_c4` (RAMCMP at `0x003489B4`)": {
                "expected": WILDCARD,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "`r_ct` (RAMCMP Core Continuation)": {
                "expected": WILDCARD,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": {
                "expected": WILDCARD,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": {
                "expected": "PULSE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
            "Inspector OSD Title & Status (`extend.m`)": {
                "expected": "WITNESS_INVALID",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:173",
            },
        },
    },
    "H4": {
        "line": 174,
        "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
        "summary": "Witness record at 0x0035F7A0 was malformed as built",
        "columns": {
            "`r_l8` (RAMCMP at `0x00008000`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "`r_l4` (RAMCMP at `0x40008000`)": {
                "expected": WILDCARD,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "`r_c4` (RAMCMP at `0x003489B4`)": {
                "expected": 1,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "`r_ct` (RAMCMP Core Continuation)": {
                "expected": 1,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "`r_wm` (RAMCMP Witness at `0x0035F7A0`)": {
                "expected": 0,
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "PORT-20 LED Behaviour (GPIO 33, `0xD20B0884`)": {
                "expected": "PULSE",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
            "Inspector OSD Title & Status (`extend.m`)": {
                "expected": "WITNESS_INVALID",
                "citation": "docs/PORT21_OWNER_SESSION_PLAN.md:174",
            },
        },
    },
}

# Alias for backward compatibility if needed
ENCODED_TABLE = STRUCTURED_RULE_TABLE


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
    """Normalizes the PORT-20 LED observation to PULSE, NO_PULSE, or UNOBSERVED.
    
    Validates strictly against the closed set:
    - NO_PULSE
    - PULSE
    - UNOBSERVED
    
    Anchored token matching prevents substrings (e.g. 'OFF') from misclassifying
    strings such as 'PULSES ~1-2 s then OFF' as NO_PULSE.
    """
    if isinstance(val, bool):
        raise ValidationError(f"Invalid type for 'port20_led': booleans not allowed, got {val}")

    if isinstance(val, dict):
        if not val:
            raise ValidationError("Invalid 'port20_led': empty dict is not allowed")
        recognized_keys = ("pulse", "observation", "value", "state", "port20_led", "led_pulse")
        found_key = None
        for k in recognized_keys:
            if k in val:
                found_key = k
                break
        if found_key is None:
            raise ValidationError(
                f"Invalid 'port20_led' dict: missing recognized key ({recognized_keys}), got {list(val.keys())}"
            )
        inner = val[found_key]
        if isinstance(inner, bool):
            raise ValidationError(f"Invalid type for 'port20_led' dict field '{found_key}': booleans not allowed")
        if not isinstance(inner, str):
            raise ValidationError(
                f"Invalid type for 'port20_led' dict field '{found_key}': expected string, got {type(inner).__name__}"
            )
        return normalize_led_observation(inner)

    if isinstance(val, str):
        v = val.strip().upper()
        if not v:
            raise ValidationError("Invalid 'port20_led': empty string")

        # Anchored NO_PULSE check
        if (
            v in ("NO_PULSE", "NO PULSE", "NO-PULSE", "NONE", "NO BLINK", "NO_BLINK")
            or v.startswith("NO PULSE")
            or v.startswith("NO_PULSE")
            or v.startswith("0 S DELAY")
            or v.startswith("**NO PULSE")
        ):
            return "NO_PULSE"

        # Anchored PULSE check (takes precedence over secondary 'OFF' in 'PULSES ~1-2 s then OFF')
        if (
            v in ("PULSE", "PULSES", "BLINK", "FLASH")
            or v.startswith("PULSE")
            or v.startswith("PULSES")
            or v.startswith("**PULSES")
            or "PULSES ~1-2 S" in v
            or "PULSE ~1-2 S" in v
        ):
            return "PULSE"

        # Anchored UNOBSERVED check
        if (
            v in ("UNOBSERVED", "UNKNOWN", "UNRECORDED", "N/A", "MISSING")
            or v.startswith("UNOBSERVED")
        ):
            return "UNOBSERVED"

        raise ValidationError(f"Unrecognized value for 'port20_led': '{val}'")

    raise ValidationError(f"Invalid type for 'port20_led': expected string or dict, got {type(val).__name__}")


def parse_and_validate_ramcmp(ramcmp_val: Any) -> Tuple[bool, Optional[Dict[str, int]]]:
    """Validates RAMCMP reading strictly:
    
    Must be either:
    - String 'UNREACHABLE' (or recognized UNREACHABLE string variant)
    - Dict with ALL 5 required fields ('r_l8', 'r_l4', 'r_c4', 'r_ct', 'r_wm') as integers 0 or 1.
    
    Rejects:
    - Booleans (True / False) in dict or for ramcmp
    - Partial UNREACHABLE inside dict
    - Unknown strings ('GARBAGE')
    - Missing fields in dict
    - Values other than 0 or 1
    
    Returns (is_ramcmp_unreachable, ramcmp_dict).
    """
    if ramcmp_val is None:
        return True, None

    if isinstance(ramcmp_val, bool):
        raise ValidationError(f"Invalid type for 'ramcmp': booleans not allowed, got {ramcmp_val}")

    if isinstance(ramcmp_val, str):
        v = ramcmp_val.strip().upper()
        if (
            v in ("UNREACHABLE", "UNREACHABLE / UNKNOWN", "HANG")
            or v.startswith("UNREACHABLE")
            or v.startswith("**UNREACHABLE")
        ):
            return True, None
        raise ValidationError(f"Unrecognized string value for 'ramcmp': '{ramcmp_val}'")

    if isinstance(ramcmp_val, dict):
        ramcmp_dict: Dict[str, int] = {}
        for field in REQUIRED_RAMCMP_FIELDS:
            if field not in ramcmp_val:
                raise ValidationError(f"Missing required RAMCMP field: '{field}'")
            val = ramcmp_val[field]
            if isinstance(val, bool):
                raise ValidationError(f"Invalid type for RAMCMP field '{field}': booleans not allowed, got {val}")
            if not isinstance(val, int):
                raise ValidationError(
                    f"Invalid type for RAMCMP field '{field}': expected integer 0 or 1 (partial UNREACHABLE not allowed), got {type(val).__name__}"
                )
            if val not in (0, 1):
                raise ValidationError(f"Invalid value for RAMCMP field '{field}': expected 0 or 1, got {val}")
            ramcmp_dict[field] = val
        return False, ramcmp_dict

    raise ValidationError(f"Invalid type for 'ramcmp': expected dict or 'UNREACHABLE' string, got {type(ramcmp_val).__name__}")


def normalize_inspector_osd(osd_val: Any) -> Optional[str]:
    """Validates inspector_osd against a closed set of recognized values:
    - WITNESS_INVALID
    - UNREACHABLE
    - LOADER_REACHED
    - CONT_ATTEMPTED
    - UNOBSERVED
    
    Returns normalized string, or None if omitted.
    Rejects any unrecognized string with ValidationError.
    """
    if osd_val is None:
        return None
    if isinstance(osd_val, bool):
        raise ValidationError(f"Invalid type for 'inspector_osd': booleans not allowed, got {osd_val}")
    if not isinstance(osd_val, str):
        raise ValidationError(f"Invalid type for 'inspector_osd': expected string, got {type(osd_val).__name__}")

    v = osd_val.strip().upper()
    if not v:
        return None

    if (
        v in ("WITNESS_INVALID", "INVALID", "CORRUPT", "INVALID / CORRUPT")
        or v.startswith("WITNESS_INVALID")
        or "WITNESS_INVALID" in v
        or "INVALID / CORRUPT" in v
    ):
        return "WITNESS_INVALID"

    if (
        v in ("UNREACHABLE", "UNREACHABLE / UNKNOWN")
        or v.startswith("UNREACHABLE")
        or v.startswith("**UNREACHABLE")
    ):
        return "UNREACHABLE"

    if (
        v in ("LOADER_REACHED",)
        or v.startswith("LOADER_REACHED")
        or "LOADER_REACHED" in v
    ):
        return "LOADER_REACHED"

    if (
        v in ("CONT_ATTEMPTED",)
        or v.startswith("CONT_ATTEMPTED")
        or "CONT_ATTEMPTED" in v
    ):
        return "CONT_ATTEMPTED"

    if v in ("UNOBSERVED", "UNKNOWN", "N/A", "MISSING"):
        return "UNOBSERVED"

    raise ValidationError(f"Unrecognized value for 'inspector_osd': '{osd_val}'")


def parse_and_validate_report(raw_data: Union[str, bytes, dict]) -> Dict[str, Any]:
    """Parses JSON data and validates all required fields and strict types."""
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

    # Validate startup_timing (booleans explicitly rejected)
    timing_val = data.get("startup_timing", data.get("start_up_timing"))
    if isinstance(timing_val, bool):
        raise ValidationError(f"Invalid type for 'startup_timing': booleans not allowed, got {timing_val}")
    if not isinstance(timing_val, (str, int, float)):
        raise ValidationError(f"Invalid type for 'startup_timing': expected string or number, got {type(timing_val).__name__}")

    # Validate port20_led
    led_val = data.get("port20_led", data.get("led_observation", data.get("port20_led_observation")))
    normalized_led = normalize_led_observation(led_val)

    # Validate ramcmp
    ramcmp_val = data.get("ramcmp")
    is_ramcmp_unreachable, ramcmp_dict = parse_and_validate_ramcmp(ramcmp_val)

    # Validate inspector_osd
    osd_val = data.get("inspector_osd", data.get("inspector_status"))
    normalized_osd = normalize_inspector_osd(osd_val)

    return {
        "synthetic": bool(data.get("synthetic", False)),
        "card_lock_state": str(cls_val),
        "startup_timing": timing_val,
        "port20_led": normalized_led,
        "ramcmp": ramcmp_dict,
        "is_ramcmp_unreachable": is_ramcmp_unreachable,
        "inspector_osd": normalized_osd,
    }


def evaluate_hypothesis_against_rules(
    h_id: str,
    rule: Dict[str, Any],
    report: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Evaluates an owner report generically against the structured rule for hypothesis h_id.
    
    Checks every column from docs/PORT21_OWNER_SESSION_PLAN.md:169-175 without hardcoded
    assumptions or out-of-table logic.
    
    Returns (matched, messages).
    """
    reasons: List[str] = []
    contradictions: List[str] = []

    columns = rule["columns"]
    for col_name, col_rule in columns.items():
        field_name = COLUMN_TO_FIELD[col_name]
        expected = col_rule["expected"]
        citation = col_rule["citation"]

        if field_name in ("r_l8", "r_l4", "r_c4", "r_ct", "r_wm"):
            if expected == "UNREACHABLE":
                if not report["is_ramcmp_unreachable"]:
                    actual_v = report["ramcmp"][field_name] if report["ramcmp"] else "reachable"
                    contradictions.append(
                        f"RAMCMP was reachable ({field_name}={actual_v}), but {h_id} predicts UNREACHABLE [{citation}]"
                    )
                else:
                    reasons.append(f"RAMCMP UNREACHABLE matches {h_id} [{citation}]")
            elif expected == WILDCARD:
                reasons.append(f"{field_name} is WILDCARD for {h_id} [{citation}]")
            elif expected in (0, 1):
                if report["is_ramcmp_unreachable"]:
                    contradictions.append(
                        f"RAMCMP was UNREACHABLE, but {h_id} predicts {field_name}={expected} [{citation}]"
                    )
                else:
                    actual = report["ramcmp"][field_name]
                    if actual != expected:
                        contradictions.append(
                            f"{field_name}={actual}, but {h_id} predicts {field_name}={expected} [{citation}]"
                        )
                    else:
                        reasons.append(f"{field_name}={actual} matches {h_id} [{citation}]")

        elif field_name == "port20_led":
            actual_led = report["port20_led"]
            if actual_led == "UNOBSERVED":
                reasons.append(f"LED is UNOBSERVED; compatible with {h_id} ({expected}) [{citation}]")
            elif actual_led == expected:
                reasons.append(f"LED observation '{actual_led}' matches {h_id} [{citation}]")
            else:
                contradictions.append(
                    f"LED observation '{actual_led}' contradicts {h_id} (expected {expected}) [{citation}]"
                )

        elif field_name == "inspector_osd":
            actual_osd = report.get("inspector_osd")
            if actual_osd is None or actual_osd == "UNOBSERVED":
                reasons.append(f"Inspector OSD unobserved; compatible with {h_id} [{citation}]")
            elif actual_osd == expected:
                reasons.append(f"Inspector OSD '{actual_osd}' matches {h_id} [{citation}]")
            else:
                contradictions.append(
                    f"Inspector OSD '{actual_osd}' contradicts {h_id} (expected {expected}) [{citation}]"
                )

    if contradictions:
        return False, contradictions
    return True, reasons


def classify_session_report(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies an owner session report generically against hypotheses H1-H4.
    
    Evaluates report against STRUCTURED_RULE_TABLE driven entirely by
    docs/PORT21_OWNER_SESSION_PLAN.md:169-175.
    
    Returns a deterministic dictionary:
    {
      "status": "MATCH" | "AMBIGUOUS" | "INCONSISTENT",
      "classification": "H1" | "H2" | "H3" | "H4" | "AMBIGUOUS" | "INCONSISTENT",
      "hypotheses": List of matching hypothesis strings (e.g. ["H1"], ["H3", "H4"], or []),
      "reason": Human-readable explanation with citations,
      "details": Dict of per-hypothesis evaluation reasons/contradictions
    }
    """
    matching: List[str] = []
    details: Dict[str, List[str]] = {}

    for h_id in sorted(STRUCTURED_RULE_TABLE.keys()):
        rule = STRUCTURED_RULE_TABLE[h_id]
        matched, msgs = evaluate_hypothesis_against_rules(h_id, rule, report_data)
        details[h_id] = msgs
        if matched:
            matching.append(h_id)

    matching_sorted = sorted(matching)

    if len(matching_sorted) == 1:
        matched_h = matching_sorted[0]
        summary = STRUCTURED_RULE_TABLE[matched_h]["summary"]
        citation = STRUCTURED_RULE_TABLE[matched_h]["citation"]
        reason = f"Readings uniquely match hypothesis {matched_h}: {summary} [{citation}]."
        return {
            "status": "MATCH",
            "classification": matched_h,
            "hypotheses": matching_sorted,
            "reason": reason,
            "details": details,
        }
    elif len(matching_sorted) > 1:
        hyp_str = ", ".join(matching_sorted)
        citations = [STRUCTURED_RULE_TABLE[h]["citation"] for h in matching_sorted]
        reason = (
            f"Readings match multiple hypotheses ({hyp_str}). "
            f"Table rules ({', '.join(citations)}) alone cannot distinguish these hypotheses without further data."
        )
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
        for h_id in sorted(details.keys()):
            inconsistencies.append(f"{h_id} contradicted: {'; '.join(details[h_id])}")
        reason = (
            f"Readings contradict every hypothesis in docs/PORT21_OWNER_SESSION_PLAN.md:169-175: "
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
