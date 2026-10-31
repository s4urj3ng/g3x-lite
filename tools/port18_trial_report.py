#!/usr/bin/env python3
"""PORT-18: Owner Trial Results Report Ingest Tool.

Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p18-report-ingest-r2
Phase: Phase 0 Read-Only / Results Ingestion

Parses and validates a filled-in results report for the PORT-18 physical hardware
trial, conforming to the template and rules defined in docs/PORT18_OWNER_TRIAL_PLAN.md.

Capabilities:
(a) Parses the 'port18-report' fenced block from a Markdown file or a raw key: value file.
(b) Validates all 11 fixed keys and their enumerated values against the plan.
(c) Optionally runs the tracked PORT-17 trace parser (tools/port17_trace_parser.py) on a TRACE.LOG file.
(d) Optionally runs the tracked witness inspector (tools/validate_witness_inspector.py) on a witness dump.
(e) Classifies the outcome using the plan's outcome table (O1 - O16), citations, and evidence labels.
(f) Flags when the owner's reported outcome_id disagrees with trial inputs or tool results.
(g) Refuses any path whose basename matches 'PRIMARY.*' or any path under 'firmware/dumps/' (Phase 0 safety).
(h) Writes a structured JSON summary (to stdout or to --out).

Only Python standard library is used (no external dependencies).
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# TRACKED REPOSITORY PATHS (PRIMARY SOURCE CITATIONS)
# =============================================================================

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TRACE_PARSER_PATH: Path = REPO_ROOT / "tools" / "port17_trace_parser.py"
WITNESS_INSPECTOR_PATH: Path = REPO_ROOT / "tools" / "validate_witness_inspector.py"

# =============================================================================
# FIXED REPORT TEMPLATE KEYS & ENUMS (docs/PORT18_OWNER_TRIAL_PLAN.md Section 6.1)
# =============================================================================

REQUIRED_REPORT_KEYS: Tuple[str, ...] = (
    "candidate_sha256",
    "candidate_size",
    "trial_date",
    "card_prepared",
    "camera_behaviour",
    "witness_observed",
    "trace_log_present",
    "trace_log_path",
    "witness_dump_path",
    "outcome_id",
    "notes",
)

VALID_CARD_PREPARED: Tuple[str, ...] = ("yes", "no")

VALID_CAMERA_BEHAVIOUR: Tuple[str, ...] = (
    "normal_stock_boot",
    "hang",
    "no_power_on",
    "abnormal_state",
    "unclassifiable",
)

VALID_WITNESS_OBSERVED: Tuple[str, ...] = ("yes", "no", "unknown")

VALID_TRACE_LOG_PRESENT: Tuple[str, ...] = ("yes", "no")

VALID_OUTCOME_IDS: Tuple[str, ...] = tuple(f"O{i}" for i in range(1, 17))

# Literal template placeholders defined in docs/PORT18_OWNER_TRIAL_PLAN.md:360-361, 390-391
TEMPLATE_KEY_PLACEHOLDERS: Dict[str, str] = {
    "candidate_sha256": "<sha256-recorded-locally>",
    "candidate_size": "<size-bytes>",
}

# =============================================================================
# OUTCOME TABLE DEFINITIONS (docs/PORT18_OWNER_TRIAL_PLAN.md Section 4.1)
# =============================================================================

OUTCOME_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "O1": {
        "outcome_id": "O1",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: CONT_ATTEMPTED / FRESHNESS_UNVERIFIED (Yellow/Yellow)",
        "trace_log_on_card": "no",
        "meaning": (
            "Witness RAM holds stage 0x07 with core entry 0x003489B5 and an 8-aligned loader SP. "
            "This does not confirm boot success or that the record is from this attempt (INCONCLUSIVE)."
        ),
        "evidence": (
            "[VERIFIED: firmware/tools/witness_inspector_gm110c.m:8, 19-24; "
            "tools/validate_witness_inspector.py:244-247; "
            "chdk-port/platform/g3x/sub/110c/boot_witness.h:16, 25-27; "
            "tools/build_candidate_port2a.py:941]; "
            "attribution [UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:476-477]"
        ),
        "evidence_labels": ["VERIFIED", "UNKNOWN"],
        "next_action": (
            "Keep the photo. File port18-report with O1. Independent post-continuation evidence is still "
            "needed [VERIFIED: firmware/tools/witness_inspector_gm110c.m:24]; no tracked mechanism exists "
            "[VERIFIED: docs/PORT16_OWNER_TRIAL_PLAN.md:234]."
        ),
    },
    "O2": {
        "outcome_id": "O2",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: CORE_REACHED / FRESHNESS_UNVERIFIED (White/Yellow)",
        "trace_log_on_card": "no",
        "meaning": "Witness RAM holds stage 0x03. Continuation was not recorded. INCONCLUSIVE attribution.",
        "evidence": (
            "[VERIFIED: firmware/tools/witness_inspector_gm110c.m:9, 14; "
            "tools/validate_witness_inspector.py:242-243; "
            "chdk-port/platform/g3x/sub/110c/boot_witness.h:14, 25; "
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c:39]; "
            "why Stage 3 is missing [UNKNOWN]"
        ),
        "evidence_labels": ["VERIFIED", "UNKNOWN"],
        "next_action": "Keep the photo. Review chdk-port/platform/g3x/sub/110c/boot_prototype.c:168-439 (core -> task_Startup_my) offline.",
    },
    "O3": {
        "outcome_id": "O3",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: LOADER_REACHED / FRESHNESS_UNVERIFIED (White/Yellow)",
        "trace_log_on_card": "no",
        "meaning": "Witness RAM holds stage 0x01. Core stage not recorded. INCONCLUSIVE attribution.",
        "evidence": (
            "[VERIFIED: firmware/tools/witness_inspector_gm110c.m:10, 14; "
            "tools/validate_witness_inspector.py:240-241; "
            "chdk-port/platform/g3x/sub/110c/boot_witness.h:13, 25; "
            "firmware/tools/witness_inspector_payload.S:12]; "
            "cause [UNKNOWN]"
        ),
        "evidence_labels": ["VERIFIED", "UNKNOWN"],
        "next_action": (
            "Keep the photo. Review the loader handoff checks (tools/validate_candidate_port2a.py:400-444) "
            "and docs/PORT16_CANDIDATE_BUILD.md:165-167 offline."
        ),
    },
    "O4": {
        "outcome_id": "O4",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Absent or unknown (no overlay)",
        "trace_log_on_card": "no",
        "meaning": (
            "Inconclusive. Possible causes: card not seen as script disk, script.req/SCRIPT marker problem, "
            "FUNC./SET did not start extend.m, setup() failed to get message handles (script exits silently), "
            "overlay hidden, or DISKBOOT.BIN not run at all (P3/P4)."
        ),
        "evidence": (
            "[INFERRED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:10, 12, 47-53; "
            "firmware/tools/witness_inspector_gm110c.m:52-81, 169-174; docs/HANDOFF.md:923]"
        ),
        "evidence_labels": ["INFERRED"],
        "next_action": (
            "On the host, check the card: script.req bytes, SCRIPT at VBR 0x1F0, file names and sizes, "
            "lock tab. Do not retry until P3/P4 are resolved."
        ),
    },
    "O5": {
        "outcome_id": "O5",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present (any readout)",
        "trace_log_on_card": "yes",
        "meaning": "A TRACE.LOG exists, but the OFF candidate cannot write one. Its source and age are UNKNOWN.",
        "evidence": (
            "[VERIFIED: chdk-port/platform/g3x/sub/110c/g3x_trace.h:131-137; "
            "chdk-port/platform/g3x/sub/110c/g3x_trace.c:133-140; tools/build_candidate_port2a.py:248-300]; "
            "origin [UNKNOWN]"
        ),
        "evidence_labels": ["VERIFIED", "UNKNOWN"],
        "next_action": (
            "Copy the file to the host. Run python3 tools/port17_trace_parser.py <path> -H. "
            "Record that parsing does not tie it to this trial. Map the witness readout as in O1-O3/O6/O7/O13 in notes."
        ),
    },
    "O6": {
        "outcome_id": "O6",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: WITNESS_INVALID / INVALID / CORRUPT (Red/Red)",
        "trace_log_on_card": "no",
        "meaning": (
            "The payload read the witness and rejected it. The reference parser returns the same strings "
            "and colours for all of these causes: (a) buffer under 32 bytes; (b) bad magic or bad version; "
            "(c) bad checksum; (d) invalid stage mask; (e) at Stage 3, unexpected core entry address or misaligned "
            "loader stack. Header and checksum may be valid in cases (d) and (e). The specific cause is UNKNOWN "
            "from the overlay alone."
        ),
        "evidence": (
            "[VERIFIED: tools/validate_witness_inspector.py:219-249; tools/validate_witness_inspector.py:65-66; "
            "firmware/tools/witness_inspector_gm110c.m:12, 16; chdk-port/platform/g3x/sub/110c/boot_witness.h:8-9, "
            "13-16, 21-30]; that the reference parser matches the on-camera payload [INFERRED: tools/validate_witness_inspector.py:219]"
        ),
        "evidence_labels": ["VERIFIED", "INFERRED"],
        "next_action": (
            "Keep the photo. On the host, rerun step 7 (tools/validate_witness_inspector.py with explicit candidate "
            "arguments) and read its full output to confirm that payload and script match the candidate. If a witness dump "
            "exists, decode its 8 words against cases (a)-(e). No tracked tool produces such a dump "
            "[VERIFIED: docs/PORT16_OWNER_TRIAL_PLAN.md:199-200]."
        ),
    },
    "O7": {
        "outcome_id": "O7",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: STALE / REPLAY / NONCE_MISMATCH (Yellow/Yellow)",
        "trace_log_on_card": "no",
        "meaning": "A non-zero, non-fixed expected_nonce did not match session_nonce. Not expected with the shipped script (expected_nonce = 0).",
        "evidence": "[VERIFIED: tools/validate_witness_inspector.py:235-237; firmware/tools/witness_inspector_gm110c.m:11, 15, 28]",
        "evidence_labels": ["VERIFIED"],
        "next_action": "Keep the photo. Compare the extend.m on the card with candidate_port2a/witness_inspector_gm110c.m byte for byte (cmp).",
    },
    "O8": {
        "outcome_id": "O8",
        "camera_behaviour": "hang",
        "witness_readout": "Any",
        "trace_log_on_card": "no",
        "meaning": (
            "Freeze, black screen or no response after power-on. Cause UNKNOWN. Tracked candidates include "
            "the halt loops in boot_prototype.c, a crash from executing scrambled code (P4), or something else."
        ),
        "evidence": (
            "[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:183-190, 349-354; "
            "docs/HANDOFF.md:987]; cause [UNKNOWN]"
        ),
        "evidence_labels": ["INFERRED", "UNKNOWN"],
        "next_action": "Recovery 5.1. Record the time to hang and the screen state. Do not retry before root-cause review.",
    },
    "O9": {
        "outcome_id": "O9",
        "camera_behaviour": "hang",
        "witness_readout": "Any",
        "trace_log_on_card": "yes",
        "meaning": "Hang as in O8, plus a TRACE.LOG of UNKNOWN origin (see O5).",
        "evidence": "[INFERRED: as O8 and O5]",
        "evidence_labels": ["INFERRED"],
        "next_action": "Recovery 5.1. Parse TRACE.LOG on the host with tools/port17_trace_parser.py <path> -H; record that it is not tied to this attempt.",
    },
    "O10": {
        "outcome_id": "O10",
        "camera_behaviour": "no_power_on",
        "witness_readout": "Any",
        "trace_log_on_card": "no",
        "meaning": "No LCD, no LED, no lens movement. Whether any code ran is UNKNOWN. Possible causes include a battery or door problem.",
        "evidence": "[INFERRED: docs/SAFETY.md:7]; cause [UNKNOWN]",
        "evidence_labels": ["INFERRED", "UNKNOWN"],
        "next_action": "Recovery 5.2.",
    },
    "O11": {
        "outcome_id": "O11",
        "camera_behaviour": "abnormal_state",
        "witness_readout": "Any",
        "trace_log_on_card": "no",
        "meaning": "Restart loop, error message, lens error or erratic behaviour. Cause UNKNOWN.",
        "evidence": "[INFERRED: docs/SAFETY.md:7; docs/PORT16_OWNER_TRIAL_PLAN.md:272-274]",
        "evidence_labels": ["INFERRED"],
        "next_action": "Recovery 5.3. Stop. Do not retry.",
    },
    "O12": {
        "outcome_id": "O12",
        "camera_behaviour": "abnormal_state",
        "witness_readout": "Any",
        "trace_log_on_card": "yes",
        "meaning": "As O11, plus a TRACE.LOG of UNKNOWN origin.",
        "evidence": "[INFERRED: as O11 and O5]",
        "evidence_labels": ["INFERRED"],
        "next_action": "Recovery 5.3. Parse TRACE.LOG on the host with tools/port17_trace_parser.py <path> -H. Stop.",
    },
    "O13": {
        "outcome_id": "O13",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Present: script error, White/White (PORT-1G: ERR_COMPAT, ERR_ALLOC, ERR_OPEN, ERR_READ or ERR_CLOSE)",
        "trace_log_on_card": "no",
        "meaning": "extend.m ran but stopped before or around the payload: firmware mismatch, allocation failure, WITNESS.BIN not found, size != 444 B, or close failure.",
        "evidence": "[VERIFIED: firmware/tools/witness_inspector_gm110c.m:85-86, 95-122, 176-180]",
        "evidence_labels": ["VERIFIED"],
        "next_action": "Keep the photo. On the host, check that WITNESS.BIN exists and is 444 B, and rerun step 7. ERR_COMPAT -> recheck P2.",
    },
    "O14": {
        "outcome_id": "O14",
        "camera_behaviour": "normal_stock_boot",
        "witness_readout": "Absent or unknown",
        "trace_log_on_card": "yes",
        "meaning": "As O4, plus a TRACE.LOG of UNKNOWN origin (see O5).",
        "evidence": "[INFERRED: as O4 and O5]",
        "evidence_labels": ["INFERRED"],
        "next_action": "As O4. Parse TRACE.LOG on the host with tools/port17_trace_parser.py <path> -H.",
    },
    "O15": {
        "outcome_id": "O15",
        "camera_behaviour": "no_power_on",
        "witness_readout": "Any",
        "trace_log_on_card": "yes",
        "meaning": (
            "As O10, plus a TRACE.LOG found although tracing is OFF and card preparation (2.3) requires "
            "removing any existing log. This is an anomaly; its origin and age are UNKNOWN (whether any code ran is UNKNOWN, see O10)."
        ),
        "evidence": "[INFERRED: as O10 and O5]; origin and age [UNKNOWN]",
        "evidence_labels": ["INFERRED", "UNKNOWN"],
        "next_action": (
            "Recovery 5.2. Keep the file unmodified. Record its SHA-256, size and timestamp locally (never committed). "
            "Run python3 tools/port17_trace_parser.py <path> -H on it. Record its provenance as UNKNOWN."
        ),
    },
    "O16": {
        "outcome_id": "O16",
        "camera_behaviour": "unclassifiable",
        "witness_readout": "Any",
        "trace_log_on_card": "Any",
        "meaning": "None of O1-O15 fits.",
        "evidence": "[UNKNOWN]",
        "evidence_labels": ["UNKNOWN"],
        "next_action": "Power off (or pull the battery). Keep the card unmodified. Describe the behaviour in notes. Wait for human review.",
    },
}

# =============================================================================
# SAFETY CHECKS (docs/SAFETY.md:7 & Phase 0 Invariants)
# =============================================================================

def validate_path_safety(path_str: Union[str, Path]) -> Path:
    """Validate that path does not violate Phase 0 safety invariants.

    The path is treated as a real filesystem path. No sentinel value (such as
    'none') is exempt; callers that read optional report fields handle the
    'none' sentinel themselves and simply do not call a tool.

    The safety decision is made on os.path.realpath(original_path), which
    follows symlinks component by component before applying '..'. The path is
    never lexically normalised first, because os.path.normpath would collapse
    'alias/..' before 'alias' is resolved.

    Refuses:
    1. Basenames matching PRIMARY.* (ROM dumps), case-insensitive, on both the
       original and the resolved path.
    2. Consecutive path components 'firmware','dumps' anywhere in the resolved
       path (via Path.parts comparison).
    3. Any resolved path under REPO_ROOT/firmware/dumps/.
    Lexical checks on the original string may only refuse more paths.

    Returns:
        The resolved Path that was checked. Callers open this path.
    """
    raw_str = str(path_str)
    if not raw_str.strip():
        raise ValueError("Phase 0 safety violation: empty path refused.")

    resolved_path = Path(os.path.realpath(raw_str))
    slash_str = raw_str.replace("\\", "/")

    # 1. PRIMARY.* on the original and resolved basenames. The backslash-split
    # variant is an extra lexical refusal only.
    for base in (os.path.basename(raw_str), os.path.basename(slash_str), resolved_path.name):
        if fnmatch.fnmatch(base.upper(), "PRIMARY.*"):
            raise ValueError(
                f"Phase 0 safety violation: Basename '{base}' matches forbidden pattern 'PRIMARY.*'. "
                "Raw ROM dumps must never be accessed or ingested."
            )

    # 2. Consecutive 'firmware','dumps' parts on the resolved path, plus the
    # un-normalised original components (lexical, refuse-only).
    lexical_parts = [part for part in slash_str.split("/") if part not in ("", ".")]
    for parts in (resolved_path.parts, lexical_parts):
        lowered = [part.lower() for part in parts]
        for i in range(len(lowered) - 1):
            if lowered[i] == "firmware" and lowered[i + 1] == "dumps":
                raise ValueError(
                    f"Phase 0 safety violation: Path '{raw_str}' contains forbidden directory 'firmware/dumps/'. "
                    "Raw firmware dump directories must never be accessed or ingested."
                )

    if "firmware/dumps" in slash_str.lower():
        raise ValueError(
            f"Phase 0 safety violation: Path '{raw_str}' contains forbidden directory 'firmware/dumps/'. "
            "Raw firmware dump directories must never be accessed or ingested."
        )

    # 3. Containment of the resolved path in REPO_ROOT/firmware/dumps.
    dumps_dir = Path(os.path.realpath(REPO_ROOT / "firmware" / "dumps"))
    if resolved_path == dumps_dir or dumps_dir in resolved_path.parents:
        raise ValueError(
            f"Phase 0 safety violation: Resolved path '{resolved_path}' is inside forbidden directory '{dumps_dir}'."
        )

    return resolved_path


def validate_no_clobber(out_path: str, input_paths: List[str]) -> None:
    """Verify that --out will not clobber any input file."""
    if not out_path:
        return

    out_p = Path(out_path).resolve()
    for inp in input_paths:
        if not inp:
            continue
        try:
            inp_p = Path(inp).resolve()
            if out_p == inp_p:
                raise ValueError(
                    f"Output collision protection: --out path '{out_path}' resolves to input path '{inp}'. "
                    "Evidence files must never be overwritten."
                )
            if inp_p.exists() and out_p.exists():
                try:
                    if os.path.samefile(out_p, inp_p):
                        raise ValueError(
                            f"Output collision protection: --out path '{out_path}' is the same file as input '{inp}'."
                        )
                except OSError:
                    pass
        except ValueError:
            raise
        except Exception:
            pass


def resolve_evidence_path(field_path: str, report_dir: Path) -> Path:
    """Resolve evidence path relative to report directory if present, else relative to cwd."""
    p = Path(field_path)
    if p.is_absolute():
        return p
    rep_rel = report_dir / p
    if rep_rel.exists():
        return rep_rel
    return Path.cwd() / p


# =============================================================================
# REPORT TEMPLATE PARSER & VALIDATOR
# =============================================================================

def parse_report_text(content: str) -> Dict[str, Any]:
    """Parse port18-report block from raw string content.

    Accepts:
    - Markdown document containing a ```port18-report ... ``` fenced code block.
    - Raw plain-text file containing only key: value lines.

    Validates:
    - Exactly the 11 required keys.
    - No unknown or duplicate keys.
    - No unfilled template placeholders.
    - All enumerated values strictly match docs/PORT18_OWNER_TRIAL_PLAN.md:356-384.

    Returns:
        Dictionary of validated report values with typed fields.
    """
    if not content or not content.strip():
        raise ValueError("Empty report content: file has no report lines.")

    # 1. Extract block content
    fence_pattern = re.compile(r"^```port18-report\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
    match = fence_pattern.search(content)
    if match:
        block_text = match.group(1)
    else:
        # Check if file has an unclosed fence
        if "```port18-report" in content:
            raise ValueError(
                "Malformed report file: opening '```port18-report' fence found without matching closing '```' fence."
            )
        # If no fence markers exist, treat the entire content as raw key: value lines
        block_text = content

    parsed_raw: Dict[str, str] = {}
    seen_keys: set[str] = set()

    for line_num, line in enumerate(block_text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            raise ValueError(
                f"Malformed line {line_num} in port18-report (missing ':', expected 'key: value'): '{line}'"
            )

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key in seen_keys:
            raise ValueError(f"Duplicate key in port18-report: '{key}' on line {line_num}")
        seen_keys.add(key)

        if key not in REQUIRED_REPORT_KEYS:
            raise ValueError(f"Unknown key in port18-report: '{key}' on line {line_num}")

        parsed_raw[key] = value

    # Check for missing required keys
    missing_keys = [k for k in REQUIRED_REPORT_KEYS if k not in parsed_raw]
    if missing_keys:
        raise ValueError(
            f"Missing required key(s) in port18-report: {', '.join(missing_keys)} "
            f"(required keys: {', '.join(REQUIRED_REPORT_KEYS)})"
        )

    # Reject unfilled placeholders in any field:
    # Reject if value equals the plan template's literal placeholder for that key,
    # or if the whole value is a single <...> token.
    # Notes and paths that contain '<' or '>' inside other text must be accepted.
    for key, val in parsed_raw.items():
        v = val.strip()
        template_ph = TEMPLATE_KEY_PLACEHOLDERS.get(key)
        if template_ph and v == template_ph:
            raise ValueError(
                f"Unfilled placeholder '{v}' detected in field '{key}'. "
                "Template placeholders must be replaced with permitted values before ingestion "
                f"[docs/PORT18_OWNER_TRIAL_PLAN.md:360-361, 390-391]."
            )
        if re.fullmatch(r"<[^>]+>", v):
            raise ValueError(
                f"Unfilled placeholder '{v}' detected in field '{key}'. "
                "Template placeholders must be replaced with permitted values before ingestion."
            )

    # Validate individual keys & enumerated values
    validated: Dict[str, Any] = {}

    # 1. candidate_sha256 [docs/PORT18_OWNER_TRIAL_PLAN.md:360]
    val_sha = parsed_raw["candidate_sha256"]
    if val_sha == "none":
        validated["candidate_sha256"] = val_sha
    elif re.match(r"^[0-9a-f]{64}$", val_sha):
        validated["candidate_sha256"] = val_sha
    else:
        raise ValueError(
            f"Invalid value for 'candidate_sha256': '{val_sha}'. "
            "Must be exactly 64 lowercase hex characters or 'none'."
        )

    # 2. candidate_size [docs/PORT18_OWNER_TRIAL_PLAN.md:361]
    val_size = parsed_raw["candidate_size"]
    if val_size.isdigit():
        validated["candidate_size"] = int(val_size)
    else:
        raise ValueError(
            f"Invalid value for 'candidate_size': '{val_size}'. "
            "Must be a non-negative decimal integer byte count or 0."
        )

    # 3. trial_date [docs/PORT18_OWNER_TRIAL_PLAN.md:362]
    val_date = parsed_raw["trial_date"]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", val_date):
        raise ValueError(
            f"Invalid format for 'trial_date': '{val_date}'. "
            "Must be ISO 8601 calendar date YYYY-MM-DD (e.g. 2026-10-31)."
        )
    try:
        datetime.date.fromisoformat(val_date)
        validated["trial_date"] = val_date
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date for 'trial_date': '{val_date}': {exc}") from exc

    # 4. card_prepared [docs/PORT18_OWNER_TRIAL_PLAN.md:363-365]
    val_card = parsed_raw["card_prepared"]
    if val_card not in VALID_CARD_PREPARED:
        raise ValueError(
            f"Invalid value for 'card_prepared': '{val_card}'. "
            f"Allowed values: {', '.join(VALID_CARD_PREPARED)}."
        )
    validated["card_prepared"] = val_card

    # 5. camera_behaviour [docs/PORT18_OWNER_TRIAL_PLAN.md:366-371]
    val_cam = parsed_raw["camera_behaviour"]
    if val_cam not in VALID_CAMERA_BEHAVIOUR:
        raise ValueError(
            f"Invalid value for 'camera_behaviour': '{val_cam}'. "
            f"Allowed values: {', '.join(VALID_CAMERA_BEHAVIOUR)}."
        )
    validated["camera_behaviour"] = val_cam

    # 6. witness_observed [docs/PORT18_OWNER_TRIAL_PLAN.md:372-375]
    val_wit = parsed_raw["witness_observed"]
    if val_wit not in VALID_WITNESS_OBSERVED:
        raise ValueError(
            f"Invalid value for 'witness_observed': '{val_wit}'. "
            f"Allowed values: {', '.join(VALID_WITNESS_OBSERVED)}."
        )
    validated["witness_observed"] = val_wit

    # 7. trace_log_present [docs/PORT18_OWNER_TRIAL_PLAN.md:376-378]
    val_trace = parsed_raw["trace_log_present"]
    if val_trace not in VALID_TRACE_LOG_PRESENT:
        raise ValueError(
            f"Invalid value for 'trace_log_present': '{val_trace}'. "
            f"Allowed values: {', '.join(VALID_TRACE_LOG_PRESENT)}."
        )
    validated["trace_log_present"] = val_trace

    # 8. trace_log_path [docs/PORT18_OWNER_TRIAL_PLAN.md:379]
    # 'none' is the plan's "not provided" sentinel; any other value is a real path.
    val_tpath = parsed_raw["trace_log_path"]
    if val_tpath != "none":
        validate_path_safety(val_tpath)
    validated["trace_log_path"] = val_tpath

    # 9. witness_dump_path [docs/PORT18_OWNER_TRIAL_PLAN.md:380]
    val_wpath = parsed_raw["witness_dump_path"]
    if val_wpath != "none":
        validate_path_safety(val_wpath)
    validated["witness_dump_path"] = val_wpath

    # 10. outcome_id [docs/PORT18_OWNER_TRIAL_PLAN.md:381-382]
    val_oid = parsed_raw["outcome_id"]
    if val_oid not in VALID_OUTCOME_IDS:
        raise ValueError(
            f"Invalid value for 'outcome_id': '{val_oid}'. "
            f"Must be one of: {', '.join(VALID_OUTCOME_IDS)}."
        )
    validated["outcome_id"] = val_oid

    # 11. notes [docs/PORT18_OWNER_TRIAL_PLAN.md:383]
    val_notes = parsed_raw["notes"]
    validated["notes"] = val_notes

    return validated


def parse_report_file(file_path: str | Path) -> Dict[str, Any]:
    """Read and parse report file from filesystem."""
    p = validate_path_safety(file_path)

    if not p.exists():
        raise FileNotFoundError(f"Report file not found: '{p}'")

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Report file '{p}' must be UTF-8 encoded text: {exc}") from exc

    return parse_report_text(content)


# =============================================================================
# EXTERNAL TOOL INTEGRATION (PORT-17 Trace Parser & Witness Inspector)
# =============================================================================

def run_trace_parser(trace_path: str | Path, use_subprocess: bool = False) -> Dict[str, Any]:
    """Run existing tracked PORT-17 trace parser on trace_path without duplication.

    Uses exact tracked path: tools/port17_trace_parser.py.
    """
    path_str = str(trace_path)
    path_obj = validate_path_safety(path_str)

    if not path_obj.exists():
        raise FileNotFoundError(f"Trace log file not found: '{path_str}'")

    if not TRACE_PARSER_PATH.exists():
        raise FileNotFoundError(f"Tracked trace parser tool not found at: '{TRACE_PARSER_PATH}'")

    if use_subprocess:
        cmd = [sys.executable, str(TRACE_PARSER_PATH), str(path_obj), "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            return {
                "tool": "port17_trace_parser",
                "tracked_path": str(TRACE_PARSER_PATH),
                "target_file": path_str,
                "status": "error",
                "error": proc.stderr.strip() or f"Trace parser exited with code {proc.returncode}",
            }
        try:
            parsed_data = json.loads(proc.stdout)
            return {
                "tool": "port17_trace_parser",
                "tracked_path": str(TRACE_PARSER_PATH),
                "target_file": path_str,
                "status": "success",
                "data": parsed_data,
            }
        except json.JSONDecodeError as exc:
            return {
                "tool": "port17_trace_parser",
                "tracked_path": str(TRACE_PARSER_PATH),
                "target_file": path_str,
                "status": "error",
                "error": f"Failed to parse JSON output: {exc}",
            }
    else:
        # Import module directly from exact tracked path
        mod = sys.modules.get("port17_trace_parser")
        if mod is None:
            spec = importlib.util.spec_from_file_location("port17_trace_parser", str(TRACE_PARSER_PATH))
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module from tracked path: '{TRACE_PARSER_PATH}'")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["port17_trace_parser"] = mod
            spec.loader.exec_module(mod)

        with open(path_obj, "rb") as f:
            blob = f.read()

        try:
            res = mod.parse_trace(blob)
            return {
                "tool": "port17_trace_parser",
                "tracked_path": str(TRACE_PARSER_PATH),
                "target_file": path_str,
                "status": "success",
                "data": res.to_dict(),
            }
        except Exception as exc:
            return {
                "tool": "port17_trace_parser",
                "tracked_path": str(TRACE_PARSER_PATH),
                "target_file": path_str,
                "status": "error",
                "error": str(exc),
            }


def run_witness_inspector(dump_path: str | Path, expected_nonce: int = 0) -> Dict[str, Any]:
    """Run existing tracked witness inspector on dump_path without duplication.

    Uses exact tracked path: tools/validate_witness_inspector.py.
    """
    path_str = str(dump_path)
    path_obj = validate_path_safety(path_str)

    if not path_obj.exists():
        raise FileNotFoundError(f"Witness dump file not found: '{path_str}'")

    if not WITNESS_INSPECTOR_PATH.exists():
        raise FileNotFoundError(f"Tracked witness inspector tool not found at: '{WITNESS_INSPECTOR_PATH}'")

    # Import module directly from exact tracked path
    mod = sys.modules.get("validate_witness_inspector")
    if mod is None:
        spec = importlib.util.spec_from_file_location("validate_witness_inspector", str(WITNESS_INSPECTOR_PATH))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from tracked path: '{WITNESS_INSPECTOR_PATH}'")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["validate_witness_inspector"] = mod
        spec.loader.exec_module(mod)

    with open(path_obj, "rb") as f:
        blob = f.read()

    try:
        sentinel, title, status_str, c1, c2 = mod.emulate_inspector_parse(blob, expected_nonce=expected_nonce)

        raw_words = None
        magic = version = session_nonce = stage_state = 0
        loader_sp = core_entry_pc = cont_tick = checksum = 0
        if len(blob) >= 32:
            magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick, checksum = (
                struct.unpack("<IIIIIIII", blob[:32])
            )
            raw_words = {
                "magic": f"0x{magic:08X}",
                "version": f"0x{version:08X}",
                "session_nonce": f"0x{session_nonce:08X}",
                "stage_state": f"0x{stage_state:08X}",
                "loader_sp": f"0x{loader_sp:08X}",
                "core_entry_pc": f"0x{core_entry_pc:08X}",
                "cont_tick": f"0x{cont_tick:08X}",
                "checksum": f"0x{checksum:08X}",
            }

        # Challenge states, taken from the tracked inspector rather than a local copy:
        # - the fixed nonce constant is mod.BOOT_WITNESS_FIXED_NONCE
        #   [VERIFIED: tools/validate_witness_inspector.py:67];
        # - the nonce is only compared when expected_nonce is non-zero and not the fixed
        #   nonce, and only after magic/version (step 1) and checksum (step 2) pass
        #   [VERIFIED: tools/validate_witness_inspector.py:221-237].
        header_valid = (
            len(blob) >= 32
            and magic == getattr(mod, "BOOT_WITNESS_MAGIC", 0x5749544E)
            and version == getattr(mod, "BOOT_WITNESS_VERSION", 0x00010001)
            and checksum == mod.compute_checksum(magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick)
        )
        fixed_nonce = getattr(mod, "BOOT_WITNESS_FIXED_NONCE", 0x32A80001)
        challenge_supplied = bool(expected_nonce != 0)
        challenge_checked = bool(header_valid and expected_nonce != 0 and expected_nonce != fixed_nonce)
        challenge_verified = bool(challenge_checked and session_nonce == expected_nonce)
        freshness_failed = bool(challenge_checked and not challenge_verified)

        role = "supporting_evidence_only"
        attribution = "UNKNOWN"
        if challenge_verified:
            role = "freshness_verified"
            attribution = "VERIFIED_CHALLENGE"
        elif freshness_failed:
            role = "challenge_failed"
            attribution = "UNKNOWN"

        return {
            "tool": "validate_witness_inspector",
            "tracked_path": str(WITNESS_INSPECTOR_PATH),
            "target_file": path_str,
            "status": "success",
            "sentinel": f"0x{sentinel:08X}",
            "title": title,
            "status_string": status_str,
            "color1": c1,
            "color2": c2,
            "expected_nonce": f"0x{expected_nonce:08X}",
            "challenge_supplied": challenge_supplied,
            "challenge_checked": challenge_checked,
            "challenge_verified": challenge_verified,
            "freshness_failed": freshness_failed,
            "role": role,
            "attribution": attribution,
            "raw_witness_words": raw_words,
        }
    except Exception as exc:
        return {
            "tool": "validate_witness_inspector",
            "tracked_path": str(WITNESS_INSPECTOR_PATH),
            "target_file": path_str,
            "status": "error",
            "error": str(exc),
        }


# =============================================================================
# OUTCOME CLASSIFICATION & DECISION MATRIX (docs/PORT18_OWNER_TRIAL_PLAN.md 4.2)
# =============================================================================

# Readout pattern definitions
READOUT_INDICATORS: List[Tuple[str, re.Pattern]] = [
    ("CONT_ATTEMPTED", re.compile(r"\bCONT_ATTEMPTED\b|\bStage\s*3\b", re.IGNORECASE)),
    ("CORE_REACHED", re.compile(r"\bCORE_REACHED\b|\bStage\s*2\b", re.IGNORECASE)),
    ("LOADER_REACHED", re.compile(r"\bLOADER_REACHED\b|\bStage\s*1\b", re.IGNORECASE)),
    ("WITNESS_INVALID", re.compile(r"\bWITNESS_INVALID\b|\bINVALID\s*/\s*CORRUPT\b", re.IGNORECASE)),
    ("STALE / REPLAY", re.compile(r"\bSTALE\s*/\s*REPLAY\b|\bNONCE_MISMATCH\b", re.IGNORECASE)),
    ("SCRIPT_ERROR", re.compile(r"\bPORT-1G:\s*ERR(?:_[A-Z0-9]+)?\b|\bERR_(?:COMPAT|ALLOC|OPEN|READ|CLOSE)\b", re.IGNORECASE)),
]

# Readout title -> plan outcome ID for a normal_stock_boot with witness observed and no
# TRACE.LOG [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:257-259, 262-263, 269 (Section 4.1)
# and :280-285 (Section 4.2)].
READOUT_TO_OUTCOME_ID: Dict[str, str] = {
    "CONT_ATTEMPTED": "O1",
    "CORE_REACHED": "O2",
    "LOADER_REACHED": "O3",
    "WITNESS_INVALID": "O6",
    "STALE / REPLAY": "O7",
    "SCRIPT_ERROR": "O13",
}

# Clause boundaries: ; ! ? \n or a '.' followed by whitespace or end of text.
# A '.' inside a path like gm110c.m:18 does not end a clause.
CLAUSE_DELIMITER_RE = re.compile(r"[;!?\r\n]|\.(?:\s|$)")

# Negation words earlier in the same clause:
# not, no, never, none, nothing, nor, neither, without, absent, absence, lack, lacking,
# unobserved, unseen, cannot, n't contractions (with any words in between).
LEADING_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|none|nothing|nor|neither|without|absent|absence|lack|lacking|unobserved|unseen|cannot|\w+n['’]t)\b",
    re.IGNORECASE,
)

# Trailing negations in the same clause:
# not, never, absent, unobserved, unseen, missing (or n't contractions).
TRAILING_NEGATION_RE = re.compile(
    r"\b(?:not|never|absent|unobserved|unseen|missing|\w+n['’]t)\b",
    re.IGNORECASE,
)


def split_into_clauses(text: str) -> List[Tuple[str, int, int]]:
    """Split text into clauses based on clause boundary delimiters.

    Clauses end at ; ! ? a newline, or a '.' followed by whitespace or end of text.
    A '.' inside a path like gm110c.m:18 does not end a clause.
    """
    clauses: List[Tuple[str, int, int]] = []
    last_idx = 0
    for m in CLAUSE_DELIMITER_RE.finditer(text):
        clause = text[last_idx:m.start()]
        clauses.append((clause, last_idx, m.start()))
        last_idx = m.end()
    if last_idx < len(text):
        clause = text[last_idx:]
        clauses.append((clause, last_idx, len(text)))
    return clauses


def extract_readout_indicators_from_notes(notes: str) -> Tuple[Optional[str], str]:
    """Parse readout indicators from free-text notes according to PORT-18 plan.

    Matches complete readout tokens.
    A negation word anywhere earlier in the same clause cancels the readout token,
    with any words in between (not, no, never, none, nothing, nor, neither, without,
    absent, absence, lack, lacking, unobserved, unseen, cannot, n't contractions).
    So do trailing negations in the same clause (not, never, absent, unobserved, unseen, missing).
    Clauses end at ; ! ? a newline, or a '.' followed by whitespace or end of text.

    Returns:
        (detail, status) where:
        - status == "exact": exactly one unambiguous uncancelled indicator matched
        - status == "ambiguous": multiple conflicting uncancelled indicators found
        - status == "cancelled": indicator(s) were cancelled by negation in the same clause
        - status == "none": no indicators found
    """
    if not notes:
        return None, "none"

    clauses = split_into_clauses(notes)
    uncancelled_matches: List[Tuple[str, str]] = []
    cancelled_matches: List[Tuple[str, str]] = []

    for clause_text, _, _ in clauses:
        for name, pattern in READOUT_INDICATORS:
            for m in pattern.finditer(clause_text):
                r_start, r_end = m.start(), m.end()
                preceding = clause_text[:r_start]
                following = clause_text[r_end:]

                has_leading = bool(LEADING_NEGATION_RE.search(preceding))
                has_trailing = bool(TRAILING_NEGATION_RE.search(following))

                if has_leading or has_trailing:
                    cancelled_matches.append((name, m.group(0)))
                else:
                    uncancelled_matches.append((name, m.group(0)))

    if uncancelled_matches:
        unique_types = {name for name, _ in uncancelled_matches}
        if len(unique_types) == 1:
            return unique_types.pop(), "exact"
        return "ambiguous", "ambiguous"

    if cancelled_matches:
        return None, "cancelled"

    return None, "none"


def derive_implied_outcome(
    camera_behaviour: str,
    witness_observed: str,
    trace_log_present: str,
    notes: str = "",
    witness_result: Optional[Dict[str, Any]] = None,
    trace_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive the implied outcome from evidence only (Section 4.2 Decision Matrix).

    Inputs are camera_behaviour, witness_observed, trace_log_present, readout
    detail from witness dump (if challenge-verified) or notes. The owner's
    reported outcome_id is deliberately NOT an input to this derivation.

    Readout detail resolution rules:
    1. A checked challenge from witness_inspector_payload.S takes precedence.
    2. Readout indicators the owner recorded in notes.
    3. A dump without a checked challenge (none supplied, or the fixed nonce) is
       supporting evidence only (attribution UNKNOWN). It never sets the readout.
    """
    notes_detail, notes_status = extract_readout_indicators_from_notes(notes)

    detail: Optional[str] = None
    detail_source: Optional[str] = None
    witness_ok = bool(witness_result and witness_result.get("status") == "success")
    challenge_checked = bool(witness_ok and witness_result.get("challenge_checked"))
    challenge_verified = bool(challenge_checked and witness_result.get("challenge_verified"))

    if challenge_checked:
        detail = witness_result.get("title")
        detail_source = (
            "witness_inspector (challenge verified)"
            if challenge_verified
            else "witness_inspector (challenge freshness failed)"
        )
    elif notes_status == "exact":
        detail = notes_detail
        detail_source = "notes"
    elif notes_status == "ambiguous":
        detail = "ambiguous"
        detail_source = "notes (ambiguous)"
    elif notes_status == "cancelled":
        detail = None
        detail_source = "notes (cancelled readout)"

    readout_outcome_id = READOUT_TO_OUTCOME_ID.get(detail) if detail else None

    supporting_readout: Optional[Dict[str, Any]] = None
    if witness_ok and not challenge_checked:
        title = witness_result.get("title")
        supporting_readout = {
            "title": title,
            "readout_outcome_id": READOUT_TO_OUTCOME_ID.get(title),
            "role": "supporting_evidence_only",
            "attribution": "UNKNOWN",
        }

    notes_conflict = bool(
        challenge_checked
        and notes_status == "exact"
        and READOUT_TO_OUTCOME_ID.get(notes_detail) != readout_outcome_id
    )

    implied_outcome_id: Optional[str] = None
    implied_candidates: List[str]
    classification_status: str = "conclusive"

    if camera_behaviour == "unclassifiable":
        implied_outcome_id = "O16"
        implied_candidates = ["O16"]

    elif camera_behaviour == "hang":
        implied_outcome_id = "O9" if trace_log_present == "yes" else "O8"
        implied_candidates = [implied_outcome_id]

    elif camera_behaviour == "no_power_on":
        implied_outcome_id = "O15" if trace_log_present == "yes" else "O10"
        implied_candidates = [implied_outcome_id]

    elif camera_behaviour == "abnormal_state":
        implied_outcome_id = "O12" if trace_log_present == "yes" else "O11"
        implied_candidates = [implied_outcome_id]

    elif camera_behaviour == "normal_stock_boot":
        if trace_log_present == "yes":
            if witness_observed == "yes":
                implied_outcome_id = "O5"
                implied_candidates = ["O5"]
            else:
                implied_outcome_id = "O14"
                implied_candidates = ["O14"]
        else:  # trace_log_present == "no"
            if witness_observed in ("no", "unknown"):
                implied_outcome_id = "O4"
                implied_candidates = ["O4"]
            else:  # witness_observed == "yes"
                if readout_outcome_id is not None:
                    implied_outcome_id = readout_outcome_id
                    implied_candidates = [readout_outcome_id]
                else:
                    # Observables cannot distinguish between candidate outcomes without readout detail.
                    # Never derive implied outcome from owner's outcome_id, and never fabricate O1.
                    classification_status = "insufficient_evidence"
                    implied_outcome_id = None
                    implied_candidates = ["O1", "O2", "O3", "O6", "O7", "O13"]
    else:
        implied_outcome_id = "O16"
        implied_candidates = ["O16"]

    if witness_ok and challenge_checked:
        witness_attribution = "VERIFIED_CHALLENGE" if challenge_verified else "UNKNOWN"
    elif witness_ok:
        witness_attribution = "UNKNOWN"
    else:
        witness_attribution = None

    return {
        "implied_outcome_id": implied_outcome_id,
        "implied_candidates": implied_candidates,
        "classification_status": classification_status,
        "derived_detail": detail,
        "detail_source": detail_source,
        "readout_outcome_id": readout_outcome_id,
        "supporting_readout": supporting_readout,
        "notes_readout_conflict": notes_conflict,
        "challenge_checked": challenge_checked,
        "challenge_verified": challenge_verified,
        "witness_attribution": witness_attribution,
        "trace_parsed": bool(trace_result and trace_result.get("status") == "success"),
    }


def classify_outcome(
    report: Dict[str, Any],
    witness_result: Optional[Dict[str, Any]] = None,
    trace_result: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Classify the trial outcome and compare it with the owner's outcome_id.

    The implied outcome is fixed first by derive_implied_outcome() from evidence
    only; only then is it compared with the owner's outcome_id to set the
    mismatch flag.
    """
    camera_behaviour = report["camera_behaviour"]
    witness_observed = report["witness_observed"]
    trace_log_present = report["trace_log_present"]

    derived = derive_implied_outcome(
        camera_behaviour=camera_behaviour,
        witness_observed=witness_observed,
        trace_log_present=trace_log_present,
        notes=report.get("notes", ""),
        witness_result=witness_result,
        trace_result=trace_result,
    )
    implied_outcome_id: Optional[str] = derived["implied_outcome_id"]
    implied_candidates: List[str] = derived["implied_candidates"]
    classification_status: str = derived["classification_status"]
    detail = derived["derived_detail"]
    detail_source = derived["detail_source"]

    owner_outcome_id = report["outcome_id"]

    # Evaluate mismatch & agreement
    mismatch: bool
    outcome_id_matches: Optional[bool]
    mismatch_details: Optional[str]

    if classification_status == "insufficient_evidence":
        # Check whether owner's outcome_id is within the observable candidate set
        if owner_outcome_id in implied_candidates:
            mismatch = False
            outcome_id_matches = None  # undetermined / not verified conclusively
            mismatch_details = None
        else:
            mismatch = True
            outcome_id_matches = False
            mismatch_details = (
                f"Owner outcome '{owner_outcome_id}' is outside candidate set {implied_candidates} "
                f"implied by observable inputs (camera_behaviour='{camera_behaviour}', "
                f"witness_observed='{witness_observed}', trace_log_present='{trace_log_present}')."
            )

        evidence_labels = ["UNKNOWN"]
        meaning = (
            "Observable inputs (normal stock boot, witness observed on LCD, no TRACE.LOG) indicate "
            "an on-screen inspector readout, but execution attribution is UNKNOWN during this attempt; "
            f"without witness readout detail or a witness dump the outcome cannot be disambiguated among candidate set {implied_candidates}."
        )
        evidence = (
            "[UNKNOWN: docs/PORT18_OWNER_TRIAL_PLAN.md Section 4.1, Section 4.2:278-285] "
            "Execution attribution and stage attribution are UNKNOWN without readout strings or witness dump."
        )
        next_action = (
            "Inspect photo of LCD screen or obtain witness dump to determine whether Stage 3 (O1), "
            "Stage 2 (O2), Stage 1 (O3), corrupt witness (O6), nonce mismatch (O7), or script error (O13) occurred."
        )
        witness_readout = "Present (unspecified readout)"
        camera_behaviour_val = camera_behaviour
        trace_log_val = trace_log_present

    else:
        assert implied_outcome_id is not None
        mismatch = (owner_outcome_id != implied_outcome_id)
        outcome_id_matches = not mismatch
        if mismatch:
            detail_desc = f", detail='{detail}' ({detail_source})" if detail else ""
            mismatch_details = (
                f"Owner outcome '{owner_outcome_id}' disagrees with implied outcome '{implied_outcome_id}' "
                f"derived from inputs (camera_behaviour='{camera_behaviour}', witness_observed='{witness_observed}', "
                f"trace_log_present='{trace_log_present}'{detail_desc})."
            )
        else:
            mismatch_details = None

        meta = OUTCOME_DEFINITIONS.get(implied_outcome_id, OUTCOME_DEFINITIONS["O16"])
        evidence_labels = meta["evidence_labels"]
        meaning = meta["meaning"]
        evidence = meta["evidence"]
        next_action = meta["next_action"]
        witness_readout = meta["witness_readout"]
        camera_behaviour_val = meta["camera_behaviour"]
        trace_log_val = meta["trace_log_on_card"]

    return {
        "outcome_id": implied_outcome_id,
        "implied_outcome": implied_outcome_id if classification_status == "conclusive" else implied_candidates,
        "implied_candidates": implied_candidates,
        "classification_status": classification_status,
        "owner_outcome_id": owner_outcome_id,
        "outcome_id_matches": outcome_id_matches,
        "mismatch": mismatch,
        "mismatch_details": mismatch_details,
        "camera_behaviour": camera_behaviour_val,
        "witness_readout": witness_readout,
        "trace_log_on_card": trace_log_val,
        "meaning": meaning,
        "evidence": evidence,
        "evidence_labels": evidence_labels,
        "next_action": next_action,
        "derived_detail": detail,
        "detail_source": detail_source,
        "readout_outcome_id": derived["readout_outcome_id"],
        "supporting_readout": derived["supporting_readout"],
        "notes_readout_conflict": derived["notes_readout_conflict"],
        "challenge_checked": derived["challenge_checked"],
        "challenge_verified": derived["challenge_verified"],
        "witness_attribution": derived["witness_attribution"],
        "trace_parsed": derived["trace_parsed"],
    }


# =============================================================================
# INGESTION PIPELINE
# =============================================================================

def ingest_report(
    report_path: str | Path,
    trace_log_path: Optional[str | Path] = None,
    witness_dump_path: Optional[str | Path] = None,
    out_path: Optional[str | Path] = None,
    use_subprocess_for_trace: bool = False,
    expected_nonce: int = 0,
) -> Dict[str, Any]:
    """Execute complete report ingestion, tool verification, and outcome classification.

    Resolution rules for report evidence paths:
    Paths given in report fields (trace_log_path, witness_dump_path) are resolved
    relative to the directory containing the report file if they exist there, or relative
    to the current working directory.
    Output collision protection checks ALL input paths (report file, CLI arguments,
    and report field paths in both report-relative and cwd-relative forms) against --out
    using os.path.realpath plus os.path.samefile (when files exist) to ensure no evidence
    files can be clobbered. Refuses with a non-zero exit before opening --out for writing.

    Returns:
        Structured JSON-serializable dictionary.
    """
    report_path_str = str(report_path)
    report_resolved = validate_path_safety(report_path_str)

    if out_path:
        validate_path_safety(str(out_path))

    # 1. Parse report file first to extract fields and validate structure
    report_data = parse_report_file(report_path_str)
    report_dir = report_resolved.parent

    # 2. Resolve trace log path if requested
    actual_trace_path: Optional[str] = None
    if trace_log_path is not None:
        if trace_log_path == "__FROM_REPORT__":
            val = report_data.get("trace_log_path")
            if not val or val == "none":
                raise ValueError(
                    "--trace-log was specified without an explicit path, but report contains trace_log_path: 'none'."
                )
            actual_trace_path = str(resolve_evidence_path(val, report_dir))
        else:
            actual_trace_path = str(trace_log_path)

    # 3. Resolve witness dump path if requested
    actual_witness_path: Optional[str] = None
    if witness_dump_path is not None:
        if witness_dump_path == "__FROM_REPORT__":
            val = report_data.get("witness_dump_path")
            if not val or val == "none":
                raise ValueError(
                    "--witness-dump was specified without an explicit path, but report contains witness_dump_path: 'none'."
                )
            actual_witness_path = str(resolve_evidence_path(val, report_dir))
        else:
            actual_witness_path = str(witness_dump_path)

    # 4. Check safety on resolved tool paths and report evidence paths
    if actual_trace_path:
        validate_path_safety(actual_trace_path)
    if actual_witness_path:
        validate_path_safety(actual_witness_path)

    val_tlp = report_data.get("trace_log_path")
    if val_tlp and val_tlp != "none":
        validate_path_safety(resolve_evidence_path(val_tlp, report_dir))

    val_wdp = report_data.get("witness_dump_path")
    if val_wdp and val_wdp != "none":
        validate_path_safety(resolve_evidence_path(val_wdp, report_dir))

    # 5. Collision protection against --out
    if out_path:
        input_paths_to_check = [report_path_str]
        if trace_log_path and trace_log_path != "__FROM_REPORT__":
            input_paths_to_check.append(str(trace_log_path))
        if witness_dump_path and witness_dump_path != "__FROM_REPORT__":
            input_paths_to_check.append(str(witness_dump_path))

        val_tlp = report_data.get("trace_log_path")
        if val_tlp and val_tlp != "none":
            input_paths_to_check.append(val_tlp)
            input_paths_to_check.append(str(resolve_evidence_path(val_tlp, report_dir)))

        val_wdp = report_data.get("witness_dump_path")
        if val_wdp and val_wdp != "none":
            input_paths_to_check.append(val_wdp)
            input_paths_to_check.append(str(resolve_evidence_path(val_wdp, report_dir)))

        validate_no_clobber(str(out_path), input_paths_to_check)

    # 6. Execute external tools if requested
    tool_results: Dict[str, Any] = {}

    trace_result: Optional[Dict[str, Any]] = None
    if actual_trace_path:
        trace_result = run_trace_parser(actual_trace_path, use_subprocess=use_subprocess_for_trace)
        tool_results["trace_parser"] = trace_result

    witness_result: Optional[Dict[str, Any]] = None
    if actual_witness_path:
        witness_result = run_witness_inspector(actual_witness_path, expected_nonce=expected_nonce)
        tool_results["witness_inspector"] = witness_result

    # 7. Classify outcome
    classification = classify_outcome(
        report=report_data,
        witness_result=witness_result,
        trace_result=trace_result,
    )

    report_path_obj = Path(report_path_str)
    summary: Dict[str, Any] = {
        "status": "ok",
        "report_file": str(report_path_obj.resolve()),
        "parsed_fields": report_data,
        "report_fields": report_data,
        "tool_results": tool_results,
        "outcome_classification": classification,
        "ingest_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # 8. Write to --out if provided
    if out_path:
        out_path_obj = Path(out_path)
        out_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path_obj, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            f.write("\n")

    return summary


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def parse_nonce_arg(val: str) -> int:
    """Parse uint32 challenge nonce from CLI string (decimal or hex)."""
    try:
        n = int(val, 0)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(
            f"Invalid nonce/challenge: '{val}' (expected integer or hex, e.g. 0x12345678)"
        )
    if not (0 <= n <= 0xFFFFFFFF):
        raise argparse.ArgumentTypeError(
            f"Nonce/challenge out of range: '{val}' (expected 32-bit unsigned integer 0..0xFFFFFFFF)"
        )
    return n


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for port18_trial_report.py."""
    parser = argparse.ArgumentParser(
        description="PORT-18 Owner Trial Results Report Ingest Tool (Phase 0)",
    )
    parser.add_argument(
        "report",
        nargs="?",
        default=None,
        help="Path to report file (Markdown with ```port18-report block or raw key: value file)",
    )
    parser.add_argument(
        "--report",
        "-r",
        dest="report_opt",
        default=None,
        help="Path to report file",
    )
    parser.add_argument(
        "--trace-log",
        "-t",
        nargs="?",
        const="__FROM_REPORT__",
        default=None,
        help=(
            "Optional path to TRACE.LOG to parse with PORT-17 trace parser. "
            "If given without an argument, uses trace_log_path from report."
        ),
    )
    parser.add_argument(
        "--witness-dump",
        "-w",
        nargs="?",
        const="__FROM_REPORT__",
        default=None,
        help=(
            "Optional path to witness dump to inspect with witness inspector. "
            "If given without an argument, uses witness_dump_path from report."
        ),
    )
    parser.add_argument(
        "--expected-nonce",
        "--challenge",
        dest="expected_nonce",
        type=parse_nonce_arg,
        default=0,
        help="Optional expected session nonce / challenge for witness inspector validation (e.g. 0x12345678)",
    )
    parser.add_argument(
        "--out",
        "-o",
        default=None,
        help="Optional path to write JSON summary (default: write to stdout)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if owner's outcome_id disagrees with implied outcome",
    )
    parser.add_argument(
        "--subprocess-trace",
        action="store_true",
        help="Run trace parser via subprocess instead of direct module import",
    )

    args = parser.parse_args(argv)

    report_path = args.report_opt or args.report
    if not report_path:
        parser.print_usage(file=sys.stderr)
        print("ERROR: Report file path is required.", file=sys.stderr)
        return 2

    try:
        summary = ingest_report(
            report_path=report_path,
            trace_log_path=args.trace_log,
            witness_dump_path=args.witness_dump,
            out_path=args.out,
            use_subprocess_for_trace=args.subprocess_trace,
            expected_nonce=args.expected_nonce,
        )

        # If --out was omitted, emit pure JSON to stdout
        if not args.out:
            print(json.dumps(summary, indent=2))
        else:
            print(f"Report ingested: {report_path}")
            display_id = (
                summary["outcome_classification"]["outcome_id"]
                or summary["outcome_classification"]["classification_status"]
            )
            print(f"Outcome classification: {display_id}")
            if summary["outcome_classification"]["mismatch"]:
                print(
                    f"WARNING: Outcome mismatch flagged: {summary['outcome_classification']['mismatch_details']}",
                    file=sys.stderr,
                )
            print(f"Summary written to: {args.out}")

        if args.strict and summary["outcome_classification"]["mismatch"]:
            print("ERROR: Strict mode failed due to outcome mismatch.", file=sys.stderr)
            return 1

        return 0

    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Ingest failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
