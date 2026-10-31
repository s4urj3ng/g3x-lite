#!/usr/bin/env python3
"""PORT-18: Candidate Trial Preflight Verification Tool.

Platform: Canon PowerShot G3 X (Firmware GM1.10C)
Task: p18-preflight
Phase: Phase 0 Read-Only / Pre-Trial Verification

Validates locally built candidate binaries and linker maps / nm symbol tables:
(a) Parses 'boot_witness' and '_end' from the map or symbol file and checks them
    against the PORT-16 pinned architectural values.
(b) Verifies that the PORT-17 compile-time trace option is OFF (no trace symbols
    or .g3x_trace sections present).
(c) Computes and prints the candidate binary SHA-256 digest and byte size.
(d) Writes a structured JSON preflight report (to stdout or to --out) with each
    check's name, its expected and actual values, pass/fail, and an overall verdict.
    Exits non-zero if any check fails.

Refuses any input path whose basename matches 'PRIMARY.*' and any path under
'firmware/dumps/', and exits non-zero with a clear security violation message.

Only Python standard library is used (no external dependencies).
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# PINNED ARCHITECTURAL VALUES & PRIMARY SOURCE CITATIONS (PORT-16 / PORT-17)
# =============================================================================

# Pinned boot_witness symbol RAM address:
# Pinned to 0x0035F7A0 (.data section, 16-byte aligned) in PORT-16.
# Primary Source Citations:
# - docs/PORT16_WITNESS_ADDRESS.md:15 ("Derived boot_witness Symbol Address: 0x0035F7A0")
# - docs/PORT16_WITNESS_ADDRESS.md:171 ("0x0035f7a0 boot_witness")
# - docs/PORT16_CANDIDATE_BUILD.md:21 ("Candidate Witness Symbol (boot_witness) Address: 0x0035F7A0")
# - docs/PORT16_CANDIDATE_BUILD.md:247 ("0035f7a0 D boot_witness")
# - tools/build_candidate_port2a.py:54 ("EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0")
# - tools/validate_candidate_port2a.py:48 ("EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0")
EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0

# Pinned _end symbol RAM address:
# Pinned to 0x00366CB0 (.bss section, heap base) in PORT-16.
# Primary Source Citations:
# - docs/PORT16_WITNESS_ADDRESS.md:218 ("Section Bounds (_end) ... 0x00366CB0")
# - docs/PORT16_WITNESS_ADDRESS.md:278 ("_end Address ... 0x00366CB0")
# - docs/PORT16_CANDIDATE_BUILD.md:24 ("Candidate End Symbol (_end) Address: 0x00366CB0")
# - docs/PORT16_CANDIDATE_BUILD.md:250 ("00366cb0 B _end")
# - tools/build_candidate_port2a.py:553 ("core_end_addr = 0x00366CB0")
# - tools/validate_candidate_port2a.py:52 ("EXPECTED_CORE_END_ADDR = 0x00366CB0")
EXPECTED_CORE_END_ADDR: int = 0x00366CB0

# Trace compile-time option and OFF layout invariant:
# In PORT-17, runtime tracing is opt-in (-DG3X_TRACE=1).
# When tracing is OFF (trial requirement):
# - All trace symbols and .g3x_trace stanzas are completely omitted from the link.
# - Memory layout is identical to the PORT-16 baseline.
# Primary Source Citations:
# - docs/PORT17_TRACE_EVIDENCE.md:230-236 (Section 3: Conditionally Absent Section when Tracing is OFF)
#   "When G3X_TRACE is OFF, the whole .g3x_trace stanza is left out of the link:
#    no output-section statement, no ALIGN, no location-counter assignment,
#    no KEEP, and no reference symbols (for example g3x_trace_start/g3x_trace_end)."
# - docs/PORT17_TRACE_EVIDENCE.md:490-493 (Q-P17-01: OFF-layout check: tracing OFF leaves
#   boot_witness = 0x0035F7A0 and _end = 0x00366CB0 unchanged)
# - tools/build_candidate_port2a.py:983, 1000 ("--trace" CLI flag and "G3X_TRACE" env var)
# - tests/test_port17_trace_integration.py:404-405 (assertNotIn g3x_trace_ring,
#   g3x_trace_init, g3x_trace_record, g3x_trace_boot_post_bss when tracing is OFF)
# - chdk-port/platform/g3x/sub/110c/g3x_trace.h:11-20 (Scope Note: Wiring into candidate build
#   is opt-in via tools/build_candidate_port2a.py; with tracing OFF, candidate build is
#   byte-for-byte identical to the PORT-16 baseline)
# - chdk-port/platform/g3x/sub/110c/boot_prototype.c:156-160 (guarding stage markers)
TRACE_FORBIDDEN_SYMBOLS = (
    "g3x_trace_ring",
    "g3x_trace_init",
    "g3x_trace_record",
    "g3x_trace_boot_post_bss",
    "g3x_trace_start",
    "g3x_trace_end",
    "g3x_trace_mark_entry",
    "g3x_trace_mark_reloc",
)


# =============================================================================
# PATH SAFETY & SECURITY ENFORCEMENT (PHASE 0 RULES)
# =============================================================================

def validate_path_safety(path: str) -> None:
    """Validate that an input or output path does not violate Phase 0 safety invariants.

    Refuses:
    1. Any path whose basename matches 'PRIMARY.*' (case-insensitive).
    2. Any path containing or resolving under 'firmware/dumps/'.

    Policy checks are executed on both the literal given path and the fully resolved
    realpath, strictly outside of resolution exception handlers to avoid swallowing
    violations.

    Raises ValueError if forbidden.
    """
    if not path:
        return

    def _check_policy(p: str, path_kind: str) -> None:
        base = os.path.basename(os.path.normpath(p))
        # Check basename for PRIMARY.*
        if (
            fnmatch.fnmatch(base.upper(), "PRIMARY.*")
            or base.upper() == "PRIMARY"
            or re.match(r"^PRIMARY(?:\..*)?$", base, re.IGNORECASE)
        ):
            raise ValueError(
                f"Security Violation: Refusing forbidden {path_kind} '{p}' (input: '{path}'). "
                f"Basename '{base}' matches forbidden pattern 'PRIMARY.*' "
                "(Phase 0 safety policy: never operate on raw Canon firmware dumps)."
            )

        # Check normalized relative/absolute path components for firmware/dumps/
        norm_path = os.path.normpath(p).replace("\\", "/")
        parts = [part.lower() for part in norm_path.split("/") if part and part != "."]
        for i in range(len(parts) - 1):
            if parts[i] == "firmware" and parts[i + 1] == "dumps":
                raise ValueError(
                    f"Security Violation: Refusing forbidden {path_kind} '{p}' (input: '{path}'). "
                    f"Path is located under forbidden directory 'firmware/dumps/' "
                    "(Phase 0 safety policy: never operate on raw Canon firmware dumps)."
                )

    # 1. Enforce policy checks on literal given path
    _check_policy(path, "path")

    # 2. Resolve realpath (handling filesystem resolution errors separately)
    try:
        resolved = os.path.realpath(path)
    except OSError as exc:
        raise ValueError(
            f"Security Violation: Failed to resolve path '{path}': {exc}"
        ) from exc

    # 3. Enforce policy checks on resolved realpath strictly outside any resolution handler
    _check_policy(resolved, "resolved path")


def validate_output_target(
    out_path: str,
    binary_path: str,
    symbols_path: str,
    inspector_metadata_path: Optional[str] = None,
    inspector_bin_path: Optional[str] = None,
) -> None:
    """Reject --out path if it refers to candidate binary, symbol/map file, or inspector inputs.

    Guards against clobbering input files through direct path equality, symlinks,
    hardlinks, or relative traversal aliases.
    """
    inputs: List[Tuple[str, str]] = [
        ("candidate binary", binary_path),
        ("symbols/map file", symbols_path),
    ]
    if inspector_metadata_path:
        inputs.append(("inspector metadata file", inspector_metadata_path))
    if inspector_bin_path:
        inputs.append(("inspector binary file", inspector_bin_path))

    try:
        real_out = os.path.realpath(out_path)
    except OSError as exc:
        raise ValueError(f"Path resolution error during output collision check: {exc}") from exc

    for input_name, in_path in inputs:
        if not in_path:
            continue
        try:
            real_in = os.path.realpath(in_path)
        except OSError as exc:
            raise ValueError(f"Path resolution error during output collision check: {exc}") from exc

        if real_out == real_in:
            raise ValueError(
                f"Output collision error: --out path '{out_path}' resolves to {input_name} '{in_path}' "
                "(refusing to clobber input file)."
            )

        # If both target and input exist on disk, check samefile and st_dev/st_ino for hardlinks or alias handles
        if os.path.exists(out_path) and os.path.exists(in_path):
            is_same = False
            try:
                is_same = os.path.samefile(out_path, in_path)
            except (OSError, AttributeError):
                pass
            if not is_same:
                try:
                    st_out = os.stat(out_path)
                    st_in = os.stat(in_path)
                    is_same = (st_out.st_dev == st_in.st_dev and st_out.st_ino == st_in.st_ino)
                except OSError:
                    pass
            if is_same:
                raise ValueError(
                    f"Output collision error: --out path '{out_path}' refers to the same file as "
                    f"{input_name} '{in_path}' (target would be clobbered). Refusing."
                )


# =============================================================================
# SYMBOL & TRACE PARSER (MAP OR NM-STYLE SYMBOL FILES)
# =============================================================================

def parse_symbols_and_trace(
    symbols_text: str,
) -> Tuple[List[int], List[int], bool, str, Dict[str, List[int]]]:
    """Parse boot_witness and _end from link map or nm-style symbol output.

    Collects every definition of boot_witness and _end from the input (not only the last one)
    to detect duplicate or conflicting symbol definitions.
    Also checks whether the PORT-17 trace flag is OFF (no trace symbols or sections).

    Returns:
        (boot_witness_addrs, end_addrs, trace_is_off, trace_detail, symbol_definitions_dict)
    """
    symbols: Dict[str, List[int]] = {}
    found_trace_indicators: List[str] = []

    for line in symbols_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for nm format: <hex_addr> <type> <sym_name>
        parts = line_stripped.split()
        if len(parts) >= 3 and len(parts[1]) == 1 and parts[1].isalpha():
            try:
                addr = int(parts[0], 16)
                sym_name = parts[2]
                symbols.setdefault(sym_name, []).append(addr)
                if (
                    sym_name.startswith("g3x_trace")
                    or sym_name.startswith(".g3x_trace")
                    or sym_name in TRACE_FORBIDDEN_SYMBOLS
                ):
                    found_trace_indicators.append(f"symbol {sym_name} (0x{addr:08X})")
                continue
            except ValueError:
                pass

        # Check for GNU ld map symbol assignment/definition line:
        # e.g.:
        #   0x0035f7a0                boot_witness
        #   0x00366cb0                _end = .
        #   0x00366cb0                PROVIDE (_end, .)
        m = re.match(
            r"^\s*(?:0x)?([0-9a-fA-F]{1,16})\s+(?:PROVIDE\s*\(\s*)?([A-Za-z_.][A-Za-z0-9_.]*)\b",
            line,
        )
        if m:
            try:
                addr = int(m.group(1), 16)
                sym_name = m.group(2)
                symbols.setdefault(sym_name, []).append(addr)
                if (
                    sym_name.startswith("g3x_trace")
                    or sym_name.startswith(".g3x_trace")
                    or sym_name in TRACE_FORBIDDEN_SYMBOLS
                ):
                    found_trace_indicators.append(f"symbol {sym_name} (0x{addr:08X})")
            except ValueError:
                pass

        # Check for trace sections in linker map (e.g. .g3x_trace, .g3x_trace_text, and any .g3x_trace* section)
        # Primary Source Citations for trace sections:
        # - docs/PORT17_TRACE_EVIDENCE.md:13, 212, 233 (.g3x_trace buffer section)
        # - chdk-port/platform/g3x/sub/110c/g3x_trace.h:17-18 (.g3x_trace_text trace code/rodata section)
        # - tools/build_candidate_port2a.py:61, 386 (TRACE_TEXT_SECT = ".g3x_trace_text")
        # - tests/test_port17_trace_integration.py:492, 548 (.g3x_trace_text section)
        if re.search(r"\.g3x_trace[a-zA-Z0-9_]*\b", line):
            found_trace_indicators.append(f"section: '{line_stripped}'")

        # Check for explicit trace-enabled definitions:
        if re.search(r"\b(?:G3X_TRACE\s*=\s*[1-9]|-DG3X_TRACE=1|trace_enabled\s*=\s*1)\b", line):
            found_trace_indicators.append(f"flag setting: '{line_stripped}'")

    boot_witness_addrs = symbols.get("boot_witness", [])
    end_addrs = symbols.get("_end", [])

    trace_is_off = (len(found_trace_indicators) == 0)
    trace_detail = "OFF" if trace_is_off else f"ON ({'; '.join(found_trace_indicators)})"

    return boot_witness_addrs, end_addrs, trace_is_off, trace_detail, symbols


def evaluate_symbol_check(
    sym_name: str,
    expected_addr: int,
    addrs: List[int],
) -> Dict[str, Any]:
    """Evaluate symbol check against pinned architectural address.

    Handles:
    - Missing symbol: fail with actual="missing".
    - Conflicting definitions with different addresses: fail closed with clear
      'conflicting definitions' reason and actual listing every address seen.
    - Duplicate definitions with identical address: pass if address matches expected.
    - Single definition: pass if matches expected, fail with mismatch if not.
    """
    expected_hex = f"0x{expected_addr:08X}"

    if not addrs:
        return {
            "name": sym_name,
            "expected": expected_hex,
            "actual": "missing",
            "pass": False,
            "status": "FAIL",
            "reason": f"symbol '{sym_name}' not found",
        }

    unique_addrs = set(addrs)
    if len(unique_addrs) > 1:
        all_addrs_hex = [f"0x{a:08X}" for a in addrs]
        return {
            "name": sym_name,
            "expected": expected_hex,
            "actual": all_addrs_hex,
            "pass": False,
            "status": "FAIL",
            "reason": f"conflicting definitions: {', '.join(all_addrs_hex)}",
        }

    single_addr = addrs[0]
    actual_hex = f"0x{single_addr:08X}"
    is_match = (single_addr == expected_addr)
    return {
        "name": sym_name,
        "expected": expected_hex,
        "actual": actual_hex,
        "pass": is_match,
        "status": "PASS" if is_match else "FAIL",
        "reason": None if is_match else f"address mismatch (expected {expected_hex}, got {actual_hex})",
    }


# =============================================================================
# PREFLIGHT VERIFICATION WORKFLOW
# =============================================================================

def decode_inspector_payload_witness_addr(payload_bytes: bytes) -> Optional[int]:
    """Decode MOVW/MOVT r7 immediate address from witness inspector payload binary bytes."""
    if len(payload_bytes) < 18:
        return None
    lo_w1, lo_w2, hi_w1, hi_w2 = struct.unpack("<HHHH", payload_bytes[10:18])
    if (lo_w1 & 0xFBF0) != 0xF240 or (hi_w1 & 0xFBF0) != 0xF2C0:
        return None
    if ((lo_w2 >> 8) & 0xF) != 7 or ((hi_w2 >> 8) & 0xF) != 7:
        return None
    lo = ((lo_w1 & 0x0400) << 1) | ((lo_w1 & 0x000F) << 12) | ((lo_w2 & 0x7000) >> 4) | (lo_w2 & 0x00FF)
    hi = ((hi_w1 & 0x0400) << 1) | ((hi_w1 & 0x000F) << 12) | ((hi_w2 & 0x7000) >> 4) | (hi_w2 & 0x00FF)
    return (hi << 16) | lo


def run_preflight(
    binary_path: str,
    symbols_path: str,
    out_path: Optional[str] = None,
    inspector_metadata_path: Optional[str] = None,
    inspector_bin_path: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Execute preflight checks on candidate binary and symbols file.

    Returns:
        (exit_code, report_dict)
    """
    # 1. Enforce path safety checks on all provided paths (fail-closed Phase 0 policy)
    validate_path_safety(binary_path)
    validate_path_safety(symbols_path)
    if inspector_metadata_path:
        validate_path_safety(inspector_metadata_path)
    if inspector_bin_path:
        validate_path_safety(inspector_bin_path)
    if out_path:
        validate_path_safety(out_path)
        validate_output_target(
            out_path,
            binary_path,
            symbols_path,
            inspector_metadata_path=inspector_metadata_path,
            inspector_bin_path=inspector_bin_path,
        )

    # 2. Inspect candidate binary file
    if not os.path.isfile(binary_path):
        raise FileNotFoundError(f"Candidate binary file not found: '{binary_path}'")

    with open(binary_path, "rb") as f:
        binary_data = f.read()

    candidate_size = len(binary_data)
    candidate_sha256 = hashlib.sha256(binary_data).hexdigest()

    # 3. Inspect symbols / link map file
    if not os.path.isfile(symbols_path):
        raise FileNotFoundError(f"Symbols or link map file not found: '{symbols_path}'")

    with open(symbols_path, "r", encoding="utf-8", errors="replace") as f:
        symbols_text = f.read()

    bw_addrs, end_addrs, trace_is_off, trace_detail, _ = parse_symbols_and_trace(symbols_text)

    # Check for binary-level trace signatures as well
    if b"g3x_trace_" in binary_data or b"TRAC\x00\x00\x01\x00" in binary_data:
        trace_is_off = False
        trace_detail = "ON (trace signature detected in binary payload)"

    # 4. Construct check items
    bw_check = evaluate_symbol_check("boot_witness", EXPECTED_BOOT_WITNESS_ADDR, bw_addrs)
    end_check = evaluate_symbol_check("_end", EXPECTED_CORE_END_ADDR, end_addrs)

    trace_pass = trace_is_off
    trace_check: Dict[str, Any] = {
        "name": "trace_flag_off",
        "expected": "OFF",
        "actual": "OFF" if trace_pass else trace_detail,
        "pass": trace_pass,
        "status": "PASS" if trace_pass else "FAIL",
        "reason": None if trace_pass else trace_detail,
    }

    checks: List[Dict[str, Any]] = [
        bw_check,
        end_check,
        trace_check,
    ]

    # Optional Inspector Metadata Witness Alignment Check
    if inspector_metadata_path:
        if not os.path.isfile(inspector_metadata_path):
            raise FileNotFoundError(f"Inspector metadata file not found: '{inspector_metadata_path}'")
        try:
            with open(inspector_metadata_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            meta_raw = meta_data.get("witness_address")
            if meta_raw is None:
                meta_addr = None
                meta_err = "Inspector metadata missing 'witness_address' field"
            else:
                try:
                    meta_addr = int(meta_raw, 16)
                    meta_err = None
                except (ValueError, TypeError) as exc:
                    meta_addr = None
                    meta_err = f"Malformed inspector metadata 'witness_address': {exc}"

            if meta_err is None and "witness_address_int" in meta_data:
                meta_int = meta_data["witness_address_int"]
                if type(meta_int) is not int:
                    meta_err = f"Inspector metadata 'witness_address_int' is not an integer: {meta_int!r}"
                elif meta_int != meta_addr:
                    meta_err = (
                        f"Inspector metadata 'witness_address_int' (0x{meta_int:08X}) "
                        f"disagrees with 'witness_address' (0x{meta_addr:08X})"
                    )
                elif meta_int != EXPECTED_BOOT_WITNESS_ADDR:
                    meta_err = (
                        f"Inspector metadata 'witness_address_int' 0x{meta_int:08X} "
                        f"!= 0x{EXPECTED_BOOT_WITNESS_ADDR:08X}"
                    )
        except Exception as exc:
            meta_addr = None
            meta_err = f"Malformed inspector metadata: {exc}"

        meta_pass = (meta_err is None and meta_addr == EXPECTED_BOOT_WITNESS_ADDR)
        if meta_pass:
            meta_reason = None
        elif meta_err:
            meta_reason = meta_err
        elif meta_addr is not None:
            meta_reason = f"Inspector metadata target 0x{meta_addr:08X} != 0x{EXPECTED_BOOT_WITNESS_ADDR:08X}"
        else:
            meta_reason = "Inspector metadata missing witness address"

        checks.append({
            "name": "inspector_metadata_witness",
            "expected": f"0x{EXPECTED_BOOT_WITNESS_ADDR:08X}",
            "actual": f"0x{meta_addr:08X}" if meta_addr is not None else "None",
            "pass": meta_pass,
            "status": "PASS" if meta_pass else "FAIL",
            "reason": meta_reason,
        })

    # Optional Inspector Payload Binary Witness Alignment Check
    if inspector_bin_path:
        if not os.path.isfile(inspector_bin_path):
            raise FileNotFoundError(f"Inspector payload binary file not found: '{inspector_bin_path}'")
        with open(inspector_bin_path, "rb") as f:
            insp_bytes = f.read()
        payload_addr = decode_inspector_payload_witness_addr(insp_bytes)
        bin_pass = (payload_addr == EXPECTED_BOOT_WITNESS_ADDR)
        if bin_pass:
            bin_reason = None
        elif payload_addr is not None:
            bin_reason = f"Inspector payload decoded address 0x{payload_addr:08X} != 0x{EXPECTED_BOOT_WITNESS_ADDR:08X}"
        else:
            bin_reason = "Failed to decode MOVW/MOVT opcodes"

        checks.append({
            "name": "inspector_payload_witness",
            "expected": f"0x{EXPECTED_BOOT_WITNESS_ADDR:08X}",
            "actual": f"0x{payload_addr:08X}" if payload_addr is not None else "None",
            "pass": bin_pass,
            "status": "PASS" if bin_pass else "FAIL",
            "reason": bin_reason,
        })

    all_passed = all(c["pass"] for c in checks)
    verdict = "PASS" if all_passed else "FAIL"

    checks_by_name = {c["name"]: c for c in checks}
    # Convenient aliases
    checks_by_name["trace_flag"] = checks_by_name["trace_flag_off"]
    checks_by_name["trace_off"] = checks_by_name["trace_flag_off"]

    report: Dict[str, Any] = {
        "verdict": verdict,
        "overall_verdict": verdict,
        "status": verdict,
        "all_passed": all_passed,
        "candidate": {
            "path": binary_path,
            "sha256": candidate_sha256,
            "size_bytes": candidate_size,
        },
        "candidate_sha256": candidate_sha256,
        "candidate_size_bytes": candidate_size,
        "candidate_size": candidate_size,
        "symbols_source": symbols_path,
        "checks": checks,
        "checks_by_name": checks_by_name,
    }

    # 5. Output handling:
    # (c) prints the candidate's SHA-256 and size.
    # (d) writes a JSON preflight report (to stdout or to --out).
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        print(f"Candidate: {binary_path}")
        print(f"Candidate SHA-256: {candidate_sha256}")
        print(f"Candidate size: {candidate_size} bytes")
        print(f"Preflight verdict: {verdict}")
        print(f"Preflight report written to: {out_path}")
    else:
        # Emit candidate SHA-256 and size to stderr for operator visibility,
        # while keeping stdout pure valid JSON for report consumers.
        print(f"Candidate SHA-256: {candidate_sha256}", file=sys.stderr)
        print(f"Candidate size: {candidate_size} bytes", file=sys.stderr)
        print(f"Preflight verdict: {verdict}", file=sys.stderr)
        print(json.dumps(report, indent=2))

    exit_code = 0 if all_passed else 1
    return exit_code, report


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="PORT-18: G3 X Candidate Trial Preflight Verification Tool (Phase 0)",
    )
    parser.add_argument(
        "binary",
        nargs="?",
        default=None,
        help="Path to locally built candidate binary (e.g. candidate_main.bin)",
    )
    parser.add_argument(
        "symbols",
        nargs="?",
        default=None,
        help="Path to link map or nm-style symbol output",
    )
    parser.add_argument(
        "--binary",
        "-b",
        dest="binary_opt",
        help="Path to locally built candidate binary",
    )
    parser.add_argument(
        "--symbols",
        "--map",
        "-s",
        dest="symbols_opt",
        help="Path to link map or nm-style symbol output",
    )
    parser.add_argument(
        "--out",
        "-o",
        dest="out",
        default=None,
        help="Optional path to write JSON preflight report (default: write to stdout)",
    )
    parser.add_argument(
        "--inspector-metadata",
        "--metadata",
        dest="inspector_metadata",
        default=None,
        help="Optional path to witness_inspector_metadata.json to verify witness address alignment",
    )
    parser.add_argument(
        "--inspector-bin",
        dest="inspector_bin",
        default=None,
        help="Optional path to witness_inspector_payload.bin to verify witness address alignment",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    binary_path = args.binary_opt or args.binary
    symbols_path = args.symbols_opt or args.symbols

    if not binary_path or not symbols_path:
        parser.print_usage(file=sys.stderr)
        print(
            "ERROR: Both candidate binary path and map/symbol path are required.",
            file=sys.stderr,
        )
        return 2

    try:
        exit_code, _ = run_preflight(
            binary_path=binary_path,
            symbols_path=symbols_path,
            out_path=args.out,
            inspector_metadata_path=args.inspector_metadata,
            inspector_bin_path=args.inspector_bin,
        )
        return exit_code
    except ValueError as exc:
        # Path safety or security violations
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Preflight execution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
