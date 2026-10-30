#!/usr/bin/env python3
"""Unit tests for CHDK-PORT-2A candidate validator symbol verification (PORT-16).

Covers:
- Expected address constants defined in one clearly named place:
  EXPECTED_BOOT_WITNESS_ADDR (0x0035F7A0) and EXPECTED_CORE_END_ADDR (0x00366CB0)
  per docs/PORT16_WITNESS_ADDRESS.md:218
- Match case: corrected build symbol table passes verification
- Mismatch cases: boot_witness mismatch (e.g. historical 0x0035F780),
  _end mismatch (e.g. historical 0x00366C90), _start mismatch
  fail closed with non-zero exit and expected-vs-actual error messages
- Missing symbol cases: missing boot_witness, missing _end, missing _start
  fail closed with non-zero exit and expected-vs-actual error messages
- Malformed / unparseable symbol cases: non-hex addresses, undefined symbols
  fail closed with non-zero exit and clear expected-vs-actual error messages
- Subprocess and missing file error cases: missing ELF, missing bin, nm failure,
  entry instruction mismatch fail closed with non-zero exit
- Builder-to-validator coherence: output from corrected builder passes validator,
  while historical 0x0035F780 output is rejected
- Inspector binding and manifest integrity coherence
"""

import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import build_candidate_port2a as bcp
import validate_candidate_port2a as vcp

# Mock symbol tables
MOCK_NM_CORRECTED_MATCH = """
003489b4 T _start
0035aec0 D link_text_end
0035aec0 D link_data_start
0035f798 d mz_speed
0035f7a0 D boot_witness
0035f7c4 D chdk_colors
00365204 B link_data_end
00365204 B link_bss_start
00366cb0 B _end
00366cb0 B link_bss_end
"""

MOCK_NM_HISTORICAL_WITNESS_0035F780 = """
003489b4 T _start
0035aea0 D link_text_end
0035aea0 D link_data_start
0035f778 d mz_speed
0035f780 D boot_witness
0035f7a4 D chdk_colors
003651e4 B link_data_end
003651e4 B link_bss_start
00366cb0 B _end
00366cb0 B link_bss_end
"""

MOCK_NM_HISTORICAL_END_00366C90 = """
003489b4 T _start
0035aec0 D link_text_end
0035aec0 D link_data_start
0035f798 d mz_speed
0035f7a0 D boot_witness
0035f7c4 D chdk_colors
00365204 B link_data_end
00365204 B link_bss_start
00366c90 B _end
00366c90 B link_bss_end
"""

MOCK_NM_START_MISMATCH = """
00348000 T _start
0035f7a0 D boot_witness
00366cb0 B _end
"""

MOCK_NM_MISSING_WITNESS = """
003489b4 T _start
0035aec0 D link_data_start
0035f798 d mz_speed
0035f7c4 D chdk_colors
00366cb0 B _end
"""

MOCK_NM_MISSING_END = """
003489b4 T _start
0035f7a0 D boot_witness
"""

MOCK_NM_MISSING_START = """
0035f7a0 D boot_witness
00366cb0 B _end
"""

MOCK_NM_MALFORMED_HEX = """
003489b4 T _start
NOT_A_HEX D boot_witness
00366cb0 B _end
"""

# P1 test mocks: strict nm parsing and ambiguous definition detection
MOCK_NM_TRUNCATED_RECORD = """
003489b4 T _start
0035f7a0 boot_witness
00366cb0 B _end
"""

MOCK_NM_VALID_THEN_GARBAGE = """
003489b4 T _start
0035f7a0 D boot_witness
00366cb0 B _end
garbage boot_witness
"""

MOCK_NM_AMBIGUOUS_WITNESS_ORDER1 = """
003489b4 T _start
0035f780 D boot_witness
0035f7a0 D boot_witness
00366cb0 B _end
"""

MOCK_NM_AMBIGUOUS_WITNESS_ORDER2 = """
003489b4 T _start
0035f7a0 D boot_witness
0035f780 D boot_witness
00366cb0 B _end
"""

MOCK_NM_INVALID_TYPE_TOKEN = """
003489b4 T _start
0035f7a0 123 boot_witness
00366cb0 B _end
"""

MOCK_NM_EXTRA_FIELDS = """
003489b4 T _start
0035f7a0 D boot_witness EXTRA_FIELD
00366cb0 B _end
"""

MOCK_NM_DUPLICATE_END = """
003489b4 T _start
0035f7a0 D boot_witness
00366cb0 B _end
00366cb0 B _end
"""

# P2 test mocks: unparseable hex address on required symbols
MOCK_NM_UNPARSEABLE_WITNESS = """
003489b4 T _start
NOT_HEX D boot_witness
00366cb0 B _end
"""

MOCK_NM_UNPARSEABLE_END = """
003489b4 T _start
0035f7a0 D boot_witness
NOT_HEX B _end
"""

MOCK_NM_UNPARSEABLE_START = """
NOT_HEX T _start
0035f7a0 D boot_witness
00366cb0 B _end
"""

MOCK_NM_UNPARSEABLE_NON_REQUIRED = """
003489b4 T _start
0035f7a0 D boot_witness
00366cb0 B _end
NOT_HEX D non_required_sym
"""

MOCK_NM_UNDEFINED_SYMBOLS = """
003489b4 T _start
0035f7a0 D boot_witness
00366cb0 B _end
         U unresolved_external_function
"""


def create_mock_payload_bytes(witness_addr: int, size: int = 444) -> bytes:
    """Generate mock 444-byte inspector binary bytes with Thumb-2 MOVW/MOVT opcodes loading witness_addr."""
    lo = witness_addr & 0xFFFF
    hi = (witness_addr >> 16) & 0xFFFF

    hw1 = 0xF240 | (((lo >> 11) & 1) << 10) | ((lo >> 12) & 0xF)
    hw2 = (((lo >> 8) & 7) << 12) | (7 << 8) | (lo & 0xFF)

    hw3 = 0xF2C0 | (((hi >> 11) & 1) << 10) | ((hi >> 12) & 0xF)
    hw4 = (((hi >> 8) & 7) << 12) | (7 << 8) | (hi & 0xFF)

    prefix = b"\x00" * 10
    opcodes = struct.pack("<HHHH", hw1, hw2, hw3, hw4)
    suffix = b"\x00" * max(0, size - len(prefix) - len(opcodes))
    return prefix + opcodes + suffix


class TestValidatorExpectedConstants(unittest.TestCase):
    """Test expected address constants defined in validate_candidate_port2a."""

    def test_expected_constants_values_and_coherence(self):
        """Assert constants match docs/PORT16_WITNESS_ADDRESS.md and builder."""
        self.assertEqual(
            vcp.EXPECTED_BOOT_WITNESS_ADDR,
            0x0035F7A0,
            "EXPECTED_BOOT_WITNESS_ADDR must be 0x0035F7A0 per docs/PORT16_WITNESS_ADDRESS.md",
        )
        self.assertEqual(
            vcp.EXPECTED_CORE_END_ADDR,
            0x00366CB0,
            "EXPECTED_CORE_END_ADDR must be 0x00366CB0 per docs/PORT16_WITNESS_ADDRESS.md:218",
        )
        self.assertEqual(
            vcp.EXPECTED_CORE_START_ADDR,
            0x003489B4,
            "EXPECTED_CORE_START_ADDR must be 0x003489B4",
        )
        self.assertEqual(
            vcp.EXPECTED_BOOT_WITNESS_ADDR,
            bcp.EXPECTED_BOOT_WITNESS_ADDR,
            "Validator and builder must share the same EXPECTED_BOOT_WITNESS_ADDR",
        )
        self.assertEqual(
            vcp.EXPECTED_CORE_BSS_START,
            0x00365204,
            "EXPECTED_CORE_BSS_START must be 0x00365204 per docs/PORT16_WITNESS_ADDRESS.md:217",
        )


class TestCandidateCoreSymbolVerification(unittest.TestCase):
    """Test fail-closed core symbol extraction and verification."""

    def test_extract_symbols_from_nm_valid(self):
        """extract_symbols_from_nm successfully parses symbols and undefined list."""
        syms, undef = vcp.extract_symbols_from_nm(MOCK_NM_CORRECTED_MATCH)
        self.assertEqual(syms["_start"], 0x003489B4)
        self.assertEqual(syms["boot_witness"], 0x0035F7A0)
        self.assertEqual(syms["_end"], 0x00366CB0)
        self.assertEqual(undef, [])

    def test_extract_symbols_from_nm_malformed_hex_raises(self):
        """extract_symbols_from_nm raises ValueError on malformed hex address."""
        with self.assertRaises(ValueError) as ctx:
            vcp.extract_symbols_from_nm(MOCK_NM_MALFORMED_HEX)
        self.assertIn("Malformed hex address", str(ctx.exception))

    def test_verify_candidate_core_symbols_match(self):
        """Matching symbol table succeeds and returns parsed symbols."""
        syms = vcp.verify_candidate_core_symbols(MOCK_NM_CORRECTED_MATCH)
        self.assertEqual(syms["boot_witness"], 0x0035F7A0)
        self.assertEqual(syms["_end"], 0x00366CB0)
        self.assertEqual(syms["_start"], 0x003489B4)

    def test_verify_candidate_core_symbols_witness_mismatch_fails_closed(self):
        """Mismatched boot_witness exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_HISTORICAL_WITNESS_0035F780)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Symbol 'boot_witness' address mismatch in candidate core", err)
        self.assertIn("expected=0x0035F7A0", err)
        self.assertIn("actual=0x0035F780", err)

    def test_verify_candidate_core_symbols_end_mismatch_fails_closed(self):
        """Mismatched _end exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_HISTORICAL_END_00366C90)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Symbol '_end' address mismatch in candidate core", err)
        self.assertIn("expected=0x00366CB0", err)
        self.assertIn("actual=0x00366C90", err)

    def test_verify_candidate_core_symbols_start_mismatch_fails_closed(self):
        """Mismatched _start exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_START_MISMATCH)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Symbol '_start' address mismatch in candidate core", err)
        self.assertIn("expected=0x003489B4", err)
        self.assertIn("actual=0x00348000", err)

    def test_verify_candidate_core_symbols_missing_witness_fails_closed(self):
        """Missing boot_witness exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_MISSING_WITNESS)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Missing symbol 'boot_witness' in candidate core", err)
        self.assertIn("expected=0x0035F7A0", err)
        self.assertIn("actual=missing", err)

    def test_verify_candidate_core_symbols_missing_end_fails_closed(self):
        """Missing _end exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_MISSING_END)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Missing symbol '_end' in candidate core", err)
        self.assertIn("expected=0x00366CB0", err)
        self.assertIn("actual=missing", err)

    def test_verify_candidate_core_symbols_missing_start_fails_closed(self):
        """Missing _start exits non-zero with expected vs actual message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_MISSING_START)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Missing symbol '_start' in candidate core", err)
        self.assertIn("expected=0x003489B4", err)
        self.assertIn("actual=missing", err)

    def test_verify_candidate_core_symbols_malformed_nm_fails_closed(self):
        """Malformed nm output exits non-zero with unparseable nm error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_UNPARSEABLE_NON_REQUIRED)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Failed to parse candidate core symbol table", err)
        self.assertIn("expected=valid hex symbol addresses", err)
        self.assertIn("actual=unparseable nm output", err)

    def test_verify_candidate_core_symbols_truncated_record_fails_closed(self):
        """P1: Truncated nm record (< 3 fields) fails closed with malformed nm error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_TRUNCATED_RECORD)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("truncated record", err)
        self.assertIn("Malformed nm output", err)

    def test_verify_candidate_core_symbols_valid_table_then_garbage_fails_closed(self):
        """P1(a): Valid symbol table followed by truncated record 'garbage boot_witness' fails closed."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_VALID_THEN_GARBAGE)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("garbage boot_witness", err)
        self.assertIn("Malformed nm output", err)

    def test_verify_candidate_core_symbols_ambiguous_witness_order1_fails_closed(self):
        """P1(b): Stale 0x0035F780 followed by corrected 0x0035F7A0 boot_witness fails closed with ambiguous error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_AMBIGUOUS_WITNESS_ORDER1)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Ambiguous definition of required symbol 'boot_witness'", err)
        self.assertIn("0x0035F780", err)
        self.assertIn("0x0035F7A0", err)
        self.assertIn("expected=0x0035F7A0", err)

    def test_verify_candidate_core_symbols_ambiguous_witness_order2_fails_closed(self):
        """P1(b): Corrected 0x0035F7A0 followed by stale 0x0035F780 boot_witness fails closed with ambiguous error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_AMBIGUOUS_WITNESS_ORDER2)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Ambiguous definition of required symbol 'boot_witness'", err)
        self.assertIn("0x0035F780", err)
        self.assertIn("0x0035F7A0", err)
        self.assertIn("expected=0x0035F7A0", err)

    def test_verify_candidate_core_symbols_invalid_type_token_fails_closed(self):
        """P1(c): Invalid nm symbol type token fails closed with offending line in error message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_INVALID_TYPE_TOKEN)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("invalid symbol type token '123'", err)
        self.assertIn("0035f7a0 123 boot_witness", err)

    def test_verify_candidate_core_symbols_extra_fields_fails_closed(self):
        """P1(d): nm line with extra fields fails closed with offending line in error message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_EXTRA_FIELDS)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("extra fields", err)
        self.assertIn("0035f7a0 D boot_witness EXTRA_FIELD", err)

    def test_verify_candidate_core_symbols_duplicate_end_fails_closed(self):
        """P1(e): Duplicate _end symbol definition fails closed with ambiguous error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_DUPLICATE_END)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Ambiguous definition of required symbol '_end'", err)
        self.assertIn("0x00366CB0", err)
        self.assertIn("expected=0x00366CB0", err)

    def test_verify_candidate_core_symbols_unparseable_witness_hex_fails_closed(self):
        """P2: Unparseable hex address for boot_witness names symbol, expected address, and actual=unparseable."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_UNPARSEABLE_WITNESS)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn(
            "Symbol 'boot_witness' address unparseable: expected=0x0035F7A0 actual=unparseable ('NOT_HEX')",
            err,
        )
        self.assertIn("NOT_HEX D boot_witness", err)

    def test_verify_candidate_core_symbols_unparseable_end_hex_fails_closed(self):
        """P2: Unparseable hex address for _end names symbol, expected address, and actual=unparseable."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_UNPARSEABLE_END)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn(
            "Symbol '_end' address unparseable: expected=0x00366CB0 actual=unparseable ('NOT_HEX')",
            err,
        )
        self.assertIn("NOT_HEX B _end", err)

    def test_verify_candidate_core_symbols_unparseable_start_hex_fails_closed(self):
        """P2: Unparseable hex address for _start names symbol, expected address, and actual=unparseable."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_UNPARSEABLE_START)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn(
            "Symbol '_start' address unparseable: expected=0x003489B4 actual=unparseable ('NOT_HEX')",
            err,
        )
        self.assertIn("NOT_HEX T _start", err)

    def test_verify_candidate_core_symbols_undefined_symbols_fails_closed(self):
        """Undefined symbols exit non-zero with unresolved error message."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_UNDEFINED_SYMBOLS)
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Unresolved undefined symbols in candidate core", err)
        self.assertIn("unresolved_external_function", err)


class TestValidateCandidateCoreExecution(unittest.TestCase):
    """Test full validate_candidate_core workflow error handling."""

    def test_missing_elf_file_fails_closed(self):
        """Missing candidate_main.elf exits non-zero with error."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.validate_candidate_core(
                    core_elf="/nonexistent/candidate_main.elf",
                    core_bin="/nonexistent/candidate_main.bin",
                )
        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Missing candidate_main.elf", err)
        self.assertIn("actual=file not found", err)

    def test_missing_bin_file_fails_closed(self):
        """Missing candidate_main.bin exits non-zero with error."""
        with tempfile.NamedTemporaryFile() as elf_file:
            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    vcp.validate_candidate_core(
                        core_elf=elf_file.name,
                        core_bin="/nonexistent/candidate_main.bin",
                    )
            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Missing candidate_main.bin", err)
            self.assertIn("actual=file not found", err)

    @patch("subprocess.run")
    def test_nm_execution_failure_fails_closed(self, mock_run):
        """nm process failure exits non-zero."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "nm: internal error"
        mock_run.return_value = mock_proc

        with tempfile.NamedTemporaryFile() as elf_file, tempfile.NamedTemporaryFile() as bin_file:
            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    vcp.validate_candidate_core(
                        core_elf=elf_file.name,
                        core_bin=bin_file.name,
                    )
            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("nm exited with code 1", err)

    @patch("subprocess.run")
    def test_entry_instruction_mismatch_fails_closed(self, mock_run):
        """Invalid entry instruction bytes exit non-zero."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = MOCK_NM_CORRECTED_MATCH
        mock_run.return_value = mock_proc

        with tempfile.NamedTemporaryFile() as elf_file, tempfile.NamedTemporaryFile() as bin_file:
            bin_file.write(b"\x00\x00\x00\x00")  # Not Thumb-2 b.w startup
            bin_file.flush()

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    vcp.validate_candidate_core(
                        core_elf=elf_file.name,
                        core_bin=bin_file.name,
                    )
            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Core entry instruction mismatch", err)
            self.assertIn("expected=0x00F000B8 ('b.w startup')", err)


class TestBuilderToValidatorCoherence(unittest.TestCase):
    """Test coherence between build_candidate_port2a and validate_candidate_port2a."""

    def test_corrected_builder_output_passes_validator(self):
        """Symbols produced by the corrected builder (witness=0x0035F7A0, end=0x00366CB0) pass validation."""
        syms = vcp.verify_candidate_core_symbols(MOCK_NM_CORRECTED_MATCH)
        self.assertEqual(syms["boot_witness"], bcp.EXPECTED_BOOT_WITNESS_ADDR)
        self.assertEqual(syms["boot_witness"], 0x0035F7A0)
        self.assertEqual(syms["_end"], 0x00366CB0)

    def test_historical_0035f780_output_fails_validator(self):
        """Historical 0x0035F780 candidate symbol table is rejected by validator fail-closed."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                vcp.verify_candidate_core_symbols(MOCK_NM_HISTORICAL_WITNESS_0035F780)

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Symbol 'boot_witness' address mismatch", err)
        self.assertIn(f"expected=0x{vcp.EXPECTED_BOOT_WITNESS_ADDR:08X}", err)
        self.assertIn("actual=0x0035F780", err)

    def test_manifest_architectural_invariants_coherence(self):
        """Manifest integrity check accepts 0x0035F7A0 and rejects 0x0035F780."""
        with tempfile.TemporaryDirectory() as td:
            manifest_path = os.path.join(td, "candidate_manifest.json")

            # Valid manifest with corrected addresses
            manifest_data = {
                "status": "OFFLINE_CANDIDATE_BUILT",
                "independent_review": "PENDING",
                "hardware_readiness": "NO-GO",
                "architectural_invariants": {
                    "boot_witness_addr": "0x0035F7A0",
                    "core_end_symbol": "0x00366CB0",
                },
                "candidate_artifacts": {},
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)

            with patch("validate_candidate_port2a.CANDIDATE_DIR", td):
                self.assertTrue(vcp.validate_manifest_integrity())

            # Stale manifest with 0x0035F780
            manifest_data["architectural_invariants"]["boot_witness_addr"] = "0x0035F780"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)

            with patch("validate_candidate_port2a.CANDIDATE_DIR", td):
                with self.assertRaises(AssertionError) as ctx:
                    vcp.validate_manifest_integrity()
                self.assertIn("Manifest boot_witness_addr mismatch", str(ctx.exception))
                self.assertIn("expected 0x0035F7A0", str(ctx.exception))
                self.assertIn("got 0x0035F780", str(ctx.exception))

    def test_inspector_payload_binding_coherence(self):
        """Inspector association check accepts 0x0035F7A0 payload and rejects 0x0035F780."""
        with tempfile.TemporaryDirectory() as td:
            insp_m = os.path.join(td, "witness_inspector_gm110c.m")
            insp_bin = os.path.join(td, "witness_inspector_payload.bin")

            with open(insp_m, "w", encoding="utf-8") as f:
                f.write('DIM payload_size = 444\nIF read_sz <> payload_size THEN\n')

            # Correct payload (0x0035F7A0)
            with open(insp_bin, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F7A0))

            with patch("validate_candidate_port2a.CANDIDATE_DIR", td):
                self.assertTrue(vcp.validate_inspector_association())

            # Stale payload (0x0035F780)
            with open(insp_bin, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F780))

            with patch("validate_candidate_port2a.CANDIDATE_DIR", td):
                with self.assertRaises(AssertionError) as ctx:
                    vcp.validate_inspector_association()
                self.assertIn("Inspector payload witness address mismatch", str(ctx.exception))
                self.assertIn("expected 0x0035F7A0", str(ctx.exception))
                self.assertIn("got 0x0035F780", str(ctx.exception))

    def test_disjointness_validation_passes(self):
        """Disjointness validation passes with updated constants."""
        self.assertTrue(vcp.validate_memory_and_stack_disjointness())


if __name__ == "__main__":
    unittest.main()
