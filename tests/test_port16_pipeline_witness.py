#!/usr/bin/env python3
"""Unit tests for PORT-16 first-boot candidate pipeline witness verification.

Covers:
- Match case: symbol matches documented EXPECTED_BOOT_WITNESS_ADDR (0x0035F7A0)
- Mismatch case: symbol address differs (exits non-zero with expected vs actual message)
- Missing-symbol case: boot_witness symbol missing (exits non-zero with expected address message)
- Malformed / parse-failure case: nm parsing fails (exits non-zero)
- Subprocess failure and missing ELF cases (fail-closed exit non-zero)
- Architecture invariant address definition in build_candidate_port2a

Uses fixtures and mocked symbol table output; no committed binaries.
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


MOCK_NM_MATCH = """
003489b4 T _start
0035aec0 D link_data_start
0035f798 d mz_speed
0035f7a0 D boot_witness
0035f7c4 D chdk_colors
00366cb0 B _end
"""

MOCK_NM_MISMATCH = """
003489b4 T _start
0035aec0 D link_data_start
0035f778 d mz_speed
0035f780 D boot_witness
0035f7a4 D chdk_colors
00366c90 B _end
"""

MOCK_NM_MISSING_SYMBOL = """
003489b4 T _start
0035aec0 D link_data_start
0035f798 d mz_speed
0035f7c4 D chdk_colors
00366cb0 B _end
"""

MOCK_NM_MALFORMED = """
003489b4 T _start
NOT_A_HEX D boot_witness
00366cb0 B _end
"""


class TestCandidateWitnessVerification(unittest.TestCase):
    """Test fail-closed witness symbol extraction and validation in build_candidate_port2a."""

    def test_documented_expected_witness_constant(self):
        """Assert the clearly named constant equals 0x0035F7A0 (PORT16_WITNESS_ADDRESS.md)."""
        self.assertEqual(
            bcp.EXPECTED_BOOT_WITNESS_ADDR,
            0x0035F7A0,
            "EXPECTED_BOOT_WITNESS_ADDR must be 0x0035F7A0 per docs/PORT16_WITNESS_ADDRESS.md",
        )

    def test_extract_witness_addr_from_nm_match(self):
        """extract_witness_addr_from_nm extracts 0x0035F7A0 from valid nm text."""
        addr = bcp.extract_witness_addr_from_nm(MOCK_NM_MATCH)
        self.assertEqual(addr, 0x0035F7A0)
        self.assertEqual(addr % 16, 0, "Witness address must be 16-byte aligned")

    def test_extract_witness_addr_from_nm_missing(self):
        """extract_witness_addr_from_nm raises ValueError when boot_witness is absent."""
        with self.assertRaises(ValueError) as ctx:
            bcp.extract_witness_addr_from_nm(MOCK_NM_MISSING_SYMBOL)
        self.assertIn("boot_witness symbol not found", str(ctx.exception))

    def test_extract_witness_addr_from_nm_malformed(self):
        """extract_witness_addr_from_nm raises ValueError when hex parsing fails."""
        with self.assertRaises(ValueError) as ctx:
            bcp.extract_witness_addr_from_nm(MOCK_NM_MALFORMED)
        self.assertIn("Malformed hex address", str(ctx.exception))

    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_verify_witness_addr_match_case(self, mock_isfile, mock_run):
        """Match case: returns 0x0035F7A0 when symbol table matches expected address."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = MOCK_NM_MATCH
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        addr = bcp.verify_witness_addr_from_elf(
            "dummy_core.elf", expected_addr=0x0035F7A0
        )
        self.assertEqual(addr, 0x0035F7A0)

    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_verify_witness_addr_mismatch_case_fails_closed(
        self, mock_isfile, mock_run
    ):
        """Mismatch case: exits non-zero with error naming expected and actual addresses."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = MOCK_NM_MISMATCH
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_witness_addr_from_elf(
                    "dummy_core.elf", expected_addr=0x0035F7A0
                )

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("boot_witness symbol address mismatch", err)
        self.assertIn("expected 0x0035F7A0", err)
        self.assertIn("got 0x0035F780", err)

    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_verify_witness_addr_missing_symbol_fails_closed(
        self, mock_isfile, mock_run
    ):
        """Missing-symbol case: exits non-zero with message naming expected address."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = MOCK_NM_MISSING_SYMBOL
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_witness_addr_from_elf(
                    "dummy_core.elf", expected_addr=0x0035F7A0
                )

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("boot_witness symbol not found", err)
        self.assertIn("expected 0x0035F7A0", err)

    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_verify_witness_addr_malformed_nm_fails_closed(
        self, mock_isfile, mock_run
    ):
        """Malformed nm output case: exits non-zero with parsing error and expected address."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = MOCK_NM_MALFORMED
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_witness_addr_from_elf(
                    "dummy_core.elf", expected_addr=0x0035F7A0
                )

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Malformed hex address", err)
        self.assertIn("expected 0x0035F7A0", err)

    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_verify_witness_addr_nm_process_error_fails_closed(
        self, mock_isfile, mock_run
    ):
        """nm subprocess returning non-zero exit code causes immediate non-zero exit."""
        mock_proc = MagicMock()
        mock_proc.returncode = 2
        mock_proc.stdout = ""
        mock_proc.stderr = "arm-none-eabi-nm: error: file format not recognized"
        mock_run.return_value = mock_proc

        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_witness_addr_from_elf("corrupted.elf")

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("nm exited with code 2", err)

    def test_verify_witness_addr_missing_elf_file_fails_closed(self):
        """Non-existent ELF file path causes immediate non-zero exit."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_witness_addr_from_elf(
                    "/nonexistent/path/does_not_exist_at_all.elf"
                )

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("ELF file not found", err)

    def test_dancingbits_row13_synthetic_roundtrip(self):
        """Verify pure-Python dancingbits row 13 encoding round-trips with reference decoder.

        Uses an in-file reference decoder to remain 100% self-contained with no untracked imports.
        """
        row13 = [6, 5, 3, 7, 0, 2, 4, 1]

        def ref_dance(val, fudgey):
            if (fudgey % 3) != 0:
                return val ^ 0xFF
            if (fudgey & 1) == 0:
                return val ^ 0xA0
            return ((val >> 4) | (val << 4)) & 0xFF

        def ref_decode_row13(encoded_bytes: bytes) -> bytes:
            self.assertEqual(encoded_bytes[0], 0x00, "Header byte must be 0x00")
            payload = bytearray(encoded_bytes[1:])
            out = bytearray(len(payload))
            for grand in range(0, len(payload), 8):
                block = payload[grand : grand + 8]
                if len(block) < 8:
                    break
                fudge_base = grand % 1024
                for hacki in range(8):
                    fudgey = fudge_base + hacki
                    out[grand + hacki] = ref_dance(block[row13[hacki]], fudgey)
            return bytes(out)

        sample_data = b"G3X_BOOT_LOADER_PAYLOAD_TEST_" * 64
        encoded = bcp.encode_dancingbits_row13(sample_data)
        self.assertEqual(encoded[0], 0x00)
        self.assertEqual(len(encoded), len(sample_data) + 1)

        decoded = ref_decode_row13(encoded)
        self.assertEqual(decoded, sample_data)


def create_mock_payload_bytes(witness_addr: int, size: int = 444) -> bytes:
    """Generate mock 444-byte inspector binary bytes with Thumb-2 MOVW/MOVT opcodes loading witness_addr."""
    lo = witness_addr & 0xFFFF
    hi = (witness_addr >> 16) & 0xFFFF

    # Encode movw r7 at offset 0x0A
    hw1 = 0xF240 | (((lo >> 11) & 1) << 10) | ((lo >> 12) & 0xF)
    hw2 = (((lo >> 8) & 7) << 12) | (7 << 8) | (lo & 0xFF)

    # Encode movt r7 at offset 0x0E
    hw3 = 0xF2C0 | (((hi >> 11) & 1) << 10) | ((hi >> 12) & 0xF)
    hw4 = (((hi >> 8) & 7) << 12) | (7 << 8) | (hi & 0xFF)

    prefix = b"\x00" * 10
    opcodes = struct.pack("<HHHH", hw1, hw2, hw3, hw4)
    suffix = b"\x00" * max(0, size - len(prefix) - len(opcodes))
    return prefix + opcodes + suffix


class TestInspectorBindingVerification(unittest.TestCase):
    """Test fail-closed witness inspector binding verification in build_candidate_port2a."""

    def test_inspector_binding_match_case(self):
        """Match case: returns address when metadata and payload binary both target 0x0035F7A0."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "meta.json")
            bin_path = os.path.join(td, "payload.bin")

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"witness_address": "0x0035F7A0", "payload_size": 444}, f)
            with open(bin_path, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F7A0))

            res = bcp.verify_inspector_binding(
                meta_path, bin_path, expected_witness_addr=0x0035F7A0
            )
            self.assertEqual(res, 0x0035F7A0)

    def test_inspector_binding_metadata_mismatch_fails_closed(self):
        """Metadata mismatch: exits non-zero naming inspector file, target 0x0035F780, and ELF 0x0035F7A0."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "meta.json")
            bin_path = os.path.join(td, "payload.bin")

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"witness_address": "0x0035F780", "payload_size": 444}, f)
            with open(bin_path, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F7A0))

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, bin_path, expected_witness_addr=0x0035F7A0
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Witness inspector target address mismatch", err)
            self.assertIn(meta_path, err)
            self.assertIn("inspector targets 0x0035F780", err)
            self.assertIn("candidate ELF witness is 0x0035F7A0", err)

    def test_inspector_binding_payload_immediate_mismatch_fails_closed(self):
        """Payload immediate mismatch: exits non-zero naming file, target 0x0035F780, and ELF 0x0035F7A0."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "meta.json")
            bin_path = os.path.join(td, "payload.bin")

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"witness_address": "0x0035F7A0", "payload_size": 444}, f)
            with open(bin_path, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F780))

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, bin_path, expected_witness_addr=0x0035F7A0
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Witness inspector payload immediate mismatch", err)
            self.assertIn(bin_path, err)
            self.assertIn("payload loads 0x0035F780", err)
            self.assertIn("candidate ELF witness is 0x0035F7A0", err)

    def test_inspector_binding_missing_metadata_fails_closed(self):
        """Missing metadata file causes immediate non-zero exit naming file and expected address."""
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as ctx:
                bcp.verify_inspector_binding(
                    "/nonexistent/meta.json", "dummy.bin", expected_witness_addr=0x0035F7A0
                )

        self.assertNotEqual(ctx.exception.code, 0)
        err = captured_stderr.getvalue()
        self.assertIn("Witness inspector metadata not found", err)
        self.assertIn("/nonexistent/meta.json", err)
        self.assertIn("expected ELF witness 0x0035F7A0", err)

    def test_inspector_binding_unparseable_metadata_fails_closed(self):
        """Malformed JSON or missing witness_address causes immediate non-zero exit."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "bad_meta.json")
            bin_path = os.path.join(td, "payload.bin")

            with open(meta_path, "w", encoding="utf-8") as f:
                f.write("{not valid json}")
            with open(bin_path, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F7A0))

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, bin_path, expected_witness_addr=0x0035F7A0
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Failed to parse witness inspector metadata", err)
            self.assertIn("expected ELF witness 0x0035F7A0", err)

    def test_inspector_binding_missing_payload_fails_closed(self):
        """Missing payload binary causes immediate non-zero exit naming file and expected address."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"witness_address": "0x0035F7A0", "payload_size": 444}, f)

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, "/nonexistent/payload.bin", expected_witness_addr=0x0035F7A0
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Witness inspector payload binary not found", err)
            self.assertIn("/nonexistent/payload.bin", err)
            self.assertIn("expected ELF witness 0x0035F7A0", err)

    def test_inspector_binding_corrupted_payload_fails_closed(self):
        """Corrupted/truncated binary lacking valid MOVW/MOVT opcodes causes immediate non-zero exit."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "meta.json")
            bin_path = os.path.join(td, "truncated.bin")

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"witness_address": "0x0035F7A0", "payload_size": 444}, f)
            with open(bin_path, "wb") as f:
                f.write(b"\x00" * 8)  # Too small

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, bin_path, expected_witness_addr=0x0035F7A0
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Failed to decode MOVW/MOVT witness address", err)
            self.assertIn("expected ELF witness 0x0035F7A0", err)

    def test_precorrection_inspector_0x0035f780_fails_closed(self):
        """Pre-correction candidate inspector targeting 0x0035F780 fails closed against 0x0035F7A0."""
        with tempfile.TemporaryDirectory() as td:
            meta_path = os.path.join(td, "witness_inspector_metadata.json")
            bin_path = os.path.join(td, "witness_inspector_payload.bin")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "target": "Canon PowerShot G3 X (GM1.10C)",
                        "symbol": "boot_witness",
                        "witness_address": "0x0035F780",
                        "witness_address_int": 3536768,
                        "payload_bin": "firmware/tools/witness_inspector_payload.bin",
                        "payload_size": 444,
                    },
                    f,
                )
            with open(bin_path, "wb") as f:
                f.write(create_mock_payload_bytes(0x0035F780))

            captured_stderr = io.StringIO()
            with patch("sys.stderr", captured_stderr):
                with self.assertRaises(SystemExit) as ctx:
                    bcp.verify_inspector_binding(
                        meta_path, bin_path, expected_witness_addr=bcp.EXPECTED_BOOT_WITNESS_ADDR
                    )

            self.assertNotEqual(ctx.exception.code, 0)
            err = captured_stderr.getvalue()
            self.assertIn("Witness inspector target address mismatch", err)
            self.assertIn(meta_path, err)
            self.assertIn("inspector targets 0x0035F780", err)
            self.assertIn(f"candidate ELF witness is 0x{bcp.EXPECTED_BOOT_WITNESS_ADDR:08X}", err)


if __name__ == "__main__":
    unittest.main()
