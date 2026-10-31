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

Note on H3/H4 Subset Relationship:
- Under docs/PORT21_OWNER_SESSION_PLAN.md:173-174, H4 is a strict subset of H3 because
  H3 specifies wildcards for r_c4, r_ct, and r_wm, while H4 specifies r_c4=1, r_ct=1, r_wm=0.
  Consequently, under the prediction table alone, any observation matching H4 will also match H3,
  resulting in AMBIGUOUS [H3, H4]. H4 can never be the sole match under table rules alone
  without subsequent decision-tree evaluation (lines 159, 201-204).

Closed Input Schema:
  Only the following 7 keys are allowed in the top-level JSON object:
  - synthetic (boolean, optional)
  - description (string, optional)
  - card_lock_state (string or boolean, required)
  - startup_timing (string or number, required; booleans not allowed)
  - port20_led (string or dict, required)
  - ramcmp (dict with 5 fields or 'UNREACHABLE' string, required)
  - inspector_osd (string, optional)

Field Canonical Tokens:
  - port20_led accepts canonical tokens: 'PULSE', 'NO_PULSE', and 'UNOBSERVED'.
    It also accepts the anchored 'PULSES ...' form (e.g. 'PULSES ~1-2 s') cited directly
    from docs/PORT21_OWNER_SESSION_PLAN.md:172-175.
    Non-canonical strings such as 'NONE', 'UNKNOWN', 'N/A', 'MISSING', and 'HANG' are rejected.
  - ramcmp accepts either an 'UNREACHABLE' string (or 'UNREACHABLE / UNKNOWN' citing line 172)
    or a dict of 5 integers (r_l8, r_l4, r_c4, r_ct, r_wm) each equal to 0 or 1.
    Non-canonical strings such as 'HANG' are rejected.
  - inspector_osd accepts canonical tokens: 'WITNESS_INVALID' (or 'INVALID / CORRUPT'),
    'UNREACHABLE' (or 'UNREACHABLE / UNKNOWN'), 'LOADER_REACHED', 'CONT_ATTEMPTED', or 'UNOBSERVED'.
    Non-canonical tokens such as 'N/A', 'UNKNOWN', 'MISSING', and 'HANG' are rejected.
  - Null values (null / None) are strictly rejected for all fields.

CLI & Refusal Rules:
  - Pure Python standard library only.
  - Accepts JSON file path ending in .json (case-insensitive) or '-' for stdin.
  - Refuses paths ending in .bin (case-insensitive) with a specific refusal message.
  - Refuses paths whose basename starts with PRIMARY (case-insensitive) with a specific refusal message.
  - Refuses paths not ending in .json with a specific refusal message.
  - Inspects raw bytes before decoding: rejects binary content containing NUL bytes or invalid UTF-8.
  - Exits with non-zero code on malformed JSON, missing fields, wrong types, or refused paths (no traceback).
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

# Alias for backward compatibility
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
    - Paths whose basename starts with PRIMARY (case-insensitive)
    - Paths not ending in .json (case-insensitive)
    """
    p = Path(path_str)
    name = p.name
    
    if name.lower().endswith(".bin"):
        raise RefusalError(f"Refusing binary file path ending in .bin: '{path_str}'")
        
    if name.upper().startswith("PRIMARY"):
        raise RefusalError(f"Refusing path with basename starting with PRIMARY: '{path_str}'")

    if not name.lower().endswith(".json"):
        raise RefusalError(f"Refusing non-JSON file path: '{path_str}' (expected .json extension)")
        
    return p


# Closed schema definition
ALLOWED_TOP_LEVEL_FIELDS: Tuple[str, ...] = (
    "synthetic",
    "description",
    "card_lock_state",
    "startup_timing",
    "port20_led",
    "ramcmp",
    "inspector_osd",
)

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
    
    Accepts only canonical tokens:
    - 'PULSE'
    - 'NO_PULSE'
    - 'UNOBSERVED'
    Plus the anchored 'PULSES ...' form (e.g. 'PULSES ~1-2 s') cited from
    docs/PORT21_OWNER_SESSION_PLAN.md:172-175.
    
    Rejects null values, booleans, empty strings, and non-canonical strings
    such as 'NONE', 'UNKNOWN', 'N/A', 'MISSING', and 'HANG'.
    """
    if val is None:
        raise ValidationError("Invalid 'port20_led': null value is not allowed")

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
        return normalize_led_observation(inner)

    if isinstance(val, str):
        v = val.strip().upper()
        if not v:
            raise ValidationError("Invalid 'port20_led': empty string")

        # Anchored NO_PULSE check (docs/PORT21_OWNER_SESSION_PLAN.md:171: "**NO PULSE**")
        if (
            v in ("NO_PULSE", "NO PULSE")
            or v.startswith("NO PULSE")
            or v.startswith("NO_PULSE")
            or v.startswith("**NO PULSE")
        ):
            return "NO_PULSE"

        # Anchored PULSE check (docs/PORT21_OWNER_SESSION_PLAN.md:172-175: "**PULSES ~1-2 s**")
        if (
            v == "PULSE"
            or v.startswith("PULSES")
            or v.startswith("**PULSES")
            or "PULSES ~1-2 S" in v
            or "PULSE ~1-2 S" in v
        ):
            return "PULSE"

        # Canonical UNOBSERVED check
        if v == "UNOBSERVED":
            return "UNOBSERVED"

        raise ValidationError(f"Unrecognized value for 'port20_led': '{val}'")

    raise ValidationError(f"Invalid type for 'port20_led': expected string or dict, got {type(val).__name__}")


def parse_and_validate_ramcmp(ramcmp_val: Any) -> Tuple[bool, Optional[Dict[str, int]]]:
    """Validates RAMCMP reading strictly:
    
    Must be either:
    - String 'UNREACHABLE' (or 'UNREACHABLE / UNKNOWN' citing docs/PORT21_OWNER_SESSION_PLAN.md:172)
    - Dict with ALL 5 required fields ('r_l8', 'r_l4', 'r_c4', 'r_ct', 'r_wm') as integers 0 or 1.
    
    Rejects:
    - null (None)
    - booleans (True / False)
    - partial UNREACHABLE inside dict
    - non-canonical strings ('HANG', 'GARBAGE')
    - values other than 0 or 1
    
    Returns (is_ramcmp_unreachable, ramcmp_dict).
    """
    if ramcmp_val is None:
        raise ValidationError("Invalid 'ramcmp': null value is not allowed")

    if isinstance(ramcmp_val, bool):
        raise ValidationError(f"Invalid type for 'ramcmp': booleans not allowed, got {ramcmp_val}")

    if isinstance(ramcmp_val, str):
        v = ramcmp_val.strip().upper()
        if (
            v in ("UNREACHABLE", "UNREACHABLE / UNKNOWN")
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
            if val is None:
                raise ValidationError(f"Invalid value for RAMCMP field '{field}': null value is not allowed")
            if isinstance(val, bool):
                raise ValidationError(f"Invalid type for RAMCMP field '{field}': booleans not allowed, got {val}")
            if not isinstance(val, int):
                raise ValidationError(
                    f"Invalid type for RAMCMP field '{field}': expected integer 0 or 1 (partial UNREACHABLE not allowed), got {type(val).__name__}"
                )
            if val not in (0, 1):
                raise ValidationError(f"Invalid value for RAMCMP field '{field}': expected 0 or 1, got {val}")
            ramcmp_dict[field] = val
        for k in ramcmp_val:
            if k not in REQUIRED_RAMCMP_FIELDS:
                raise ValidationError(f"Unrecognized field in 'ramcmp' dict: '{k}'")
        return False, ramcmp_dict

    raise ValidationError(f"Invalid type for 'ramcmp': expected dict or 'UNREACHABLE' string, got {type(ramcmp_val).__name__}")


def normalize_inspector_osd(osd_val: Any) -> Optional[str]:
    """Validates inspector_osd against the closed set of recognized values:
    - WITNESS_INVALID (or 'INVALID / CORRUPT')
    - UNREACHABLE (or 'UNREACHABLE / UNKNOWN')
    - LOADER_REACHED
    - CONT_ATTEMPTED
    - UNOBSERVED
    
    Rejects null, booleans, empty strings, and non-canonical tokens such as 'N/A', 'UNKNOWN', 'HANG'.
    Returns normalized string.
    """
    if osd_val is None:
        raise ValidationError("Invalid 'inspector_osd': null value is not allowed")
    if isinstance(osd_val, bool):
        raise ValidationError(f"Invalid type for 'inspector_osd': booleans not allowed, got {osd_val}")
    if not isinstance(osd_val, str):
        raise ValidationError(f"Invalid type for 'inspector_osd': expected string, got {type(osd_val).__name__}")

    v = osd_val.strip().upper()
    if not v:
        raise ValidationError("Invalid 'inspector_osd': empty string")

    if (
        v in ("WITNESS_INVALID", "INVALID / CORRUPT")
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

    if v == "UNOBSERVED":
        return "UNOBSERVED"

    raise ValidationError(f"Unrecognized value for 'inspector_osd': '{osd_val}'")


def parse_and_validate_report(raw_data: Union[str, bytes, dict]) -> Dict[str, Any]:
    """Parses JSON data and validates all required fields, closed schema, and strict types."""
    if isinstance(raw_data, bytes):
        if b"\x00" in raw_data:
            raise ValidationError("Binary content detected: input contains NUL bytes")
        try:
            text = raw_data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValidationError(f"Invalid UTF-8 encoding in input: {e}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Malformed JSON: {e}")
    elif isinstance(raw_data, str):
        if "\x00" in raw_data:
            raise ValidationError("Binary content detected: input contains NUL bytes")
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

    # Check required fields first (so alias keys on their own fail missing-field check)
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            raise ValidationError(f"Missing required field: '{field}'")

    # Enforce closed schema
    for k in data:
        if k not in ALLOWED_TOP_LEVEL_FIELDS:
            raise ValidationError(f"Unrecognized field in report schema: '{k}'")

    # Reject null values for any top-level field present in data
    for k, v in data.items():
        if v is None:
            raise ValidationError(f"Invalid null value for field: '{k}'")

    # Validate card_lock_state
    cls_val = data["card_lock_state"]
    if isinstance(cls_val, bool):
        cls_str = "LOCKED" if cls_val else "UNLOCKED"
    elif isinstance(cls_val, str):
        cls_str = cls_val
    else:
        raise ValidationError(f"Invalid type for 'card_lock_state': expected string or bool, got {type(cls_val).__name__}")

    # Validate startup_timing (booleans explicitly rejected)
    timing_val = data["startup_timing"]
    if isinstance(timing_val, bool):
        raise ValidationError(f"Invalid type for 'startup_timing': booleans not allowed, got {timing_val}")
    if not isinstance(timing_val, (str, int, float)):
        raise ValidationError(f"Invalid type for 'startup_timing': expected string or number, got {type(timing_val).__name__}")

    # Validate port20_led
    normalized_led = normalize_led_observation(data["port20_led"])

    # Validate ramcmp
    is_ramcmp_unreachable, ramcmp_dict = parse_and_validate_ramcmp(data["ramcmp"])

    # Validate inspector_osd (optional, but validated strictly if present)
    normalized_osd = None
    if "inspector_osd" in data:
        normalized_osd = normalize_inspector_osd(data["inspector_osd"])

    # Validate synthetic (optional)
    synthetic_val = False
    if "synthetic" in data:
        if not isinstance(data["synthetic"], bool):
            raise ValidationError(f"Invalid type for 'synthetic': expected boolean, got {type(data['synthetic']).__name__}")
        synthetic_val = data["synthetic"]

    # Validate description (optional)
    desc_val = ""
    if "description" in data:
        if not isinstance(data["description"], str):
            raise ValidationError(f"Invalid type for 'description': expected string, got {type(data['description']).__name__}")
        desc_val = data["description"]

    return {
        "synthetic": synthetic_val,
        "description": desc_val,
        "card_lock_state": cls_str,
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
        if matching_sorted == ["H3", "H4"]:
            reason = (
                f"Readings match multiple hypotheses ({hyp_str}). "
                f"Under docs/PORT21_OWNER_SESSION_PLAN.md:173-174, H4 is a strict subset of H3 "
                f"(H3 specifies wildcards for r_c4, r_ct, and r_wm, while H4 specifies r_c4=1, r_ct=1, r_wm=0), "
                f"so H4 can never be the sole match under table rules ({', '.join(citations)}) alone."
            )
        else:
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
    stdin_content: Optional[Union[str, bytes]] = None,
) -> Tuple[int, str]:
    """Executes the classifier on a file path or stdin string.
    
    Returns (exit_code, output_text).
    """
    try:
        if stdin_content is not None:
            raw_bytes = stdin_content.encode("utf-8") if isinstance(stdin_content, str) else stdin_content
        elif input_source in (None, "-", ""):
            raw_bytes = sys.stdin.buffer.read()
        else:
            p = validate_path_safety(str(input_source))
            if not p.is_file():
                return 1, f"Error: File not found: '{input_source}'"
            raw_bytes = p.read_bytes()

        # Check for binary content (NUL byte) before decoding
        if b"\x00" in raw_bytes:
            src_label = str(input_source) if input_source not in (None, "-", "") else "stdin"
            raise ValidationError(f"Binary content detected: input contains NUL bytes: '{src_label}'")

        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValidationError(f"Invalid UTF-8 encoding in input: {e}")

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
