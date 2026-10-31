#!/usr/bin/env python3
"""PORT-19 T1: Unit tests for GM1.10C DISKBOOT.BIN encoding verification.

Verifies:
1. Candidate DISKBOOT.BIN byte 0 == 0x00 (enforced by ROM sub_fc54de38 at 0xFC54DE3A-0xFC54DE3C).
2. Candidate DISKBOOT.BIN length == len(candidate_loader.bin) + 1 (byte 0 stripped by 0xFC54DE4E).
3. Candidate DISKBOOT.BIN decoded with DancingBits Row 13 (ROM table at 0xFC7C0F8C and
   descrambler at 0xFC469188) matches candidate_loader.bin bit-for-bit.
4. Negative test: raw unencoded DISKBOOT.BIN fails decoding assertion.
5. Negative test: wrong byte 0 (byte 0 != 0x00) fails header assertion.
6. Negative test: synthetic wrong permutation (SYNTHETIC_WRONG_PERMUTATION) fails decoding assertion.
7. Architectural invariants: boot_witness == 0x0035F7A0, _end == 0x00366CB0.
8. Evidence manifest integrity: PORT19_EVIDENCE_MANIFEST.json passes port11c_evidence_validator.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = REPO_ROOT / "candidate_port2a"
DISKBOOT_BIN = CANDIDATE_DIR / "DISKBOOT.BIN"
LOADER_BIN = CANDIDATE_DIR / "candidate_loader.bin"
CORE_ELF = CANDIDATE_DIR / "candidate_main.elf"
MANIFEST_JSON = CANDIDATE_DIR / "candidate_manifest.json"
EVIDENCE_MANIFEST = REPO_ROOT / "docs" / "agentbridge" / "PORT19_EVIDENCE_MANIFEST.json"

# DIGIC 6 dancingbits row 13 permutation table verified in GM1.10C ROM @ 0xFC7C0F8C
ROW13 = [6, 5, 3, 7, 0, 2, 4, 1]

# Neutral synthetic wrong permutation (not attributed to any camera or row), used only
# by the negative test to prove a non-row-13 encoding fails to decode.
SYNTHETIC_WRONG_PERMUTATION = [5, 2, 0, 6, 4, 7, 1, 3]
WRONG_PERMUTATION_SYNTHETIC = SYNTHETIC_WRONG_PERMUTATION

EXPECTED_BOOT_WITNESS = 0x0035F7A0
EXPECTED_CORE_END = 0x00366CB0


def _dance(val: int, fudgey: int) -> int:
    """Byte descrambling transformation matching GM1.10C sub_fc469188."""
    if (fudgey % 3) != 0:
        return val ^ 0xFF
    if (fudgey & 1) == 0:
        return val ^ 0xA0
    return ((val >> 4) | (val << 4)) & 0xFF


def decode_dancingbits(encoded_bytes: bytes, row: list[int] = ROW13) -> bytes:
    """Decode dancingbits binary following ROM sub_fc54de38 and sub_fc42189c."""
    if not encoded_bytes:
        raise ValueError("Cannot decode empty binary")
    if encoded_bytes[0] != 0:
        raise ValueError(f"ROM sub_fc54de38 rejects byte 0 != 0x00 (got 0x{encoded_bytes[0]:02X})")

    # Shift left by 1 byte (ROM 0xFC54DE4E..0xFC54DE5E)
    payload = bytearray(encoded_bytes[1:])
    out = bytearray(len(payload))

    full_blocks = (len(payload) // 8) * 8
    # 8-byte block decode loop (ROM sub_fc42189c @ 0xFC4218BC-0xFC421902)
    for grand in range(0, full_blocks, 8):
        block = payload[grand : grand + 8]
        fudge_base = grand % 1024
        for hacki in range(8):
            fudgey = fudge_base + hacki
            out[grand + hacki] = _dance(block[row[hacki]], fudgey)

    # Remainder loop (ROM sub_fc42189c @ 0xFC421904-0xFC421922)
    # The byte descrambler (_dance) is applied to the trailing len % 8 bytes without permutation.
    for r7 in range(full_blocks, len(payload)):
        out[r7] = _dance(payload[r7], r7 % 1024)

    return bytes(out)


def encode_dancingbits(raw_bytes: bytes, row: list[int] = ROW13) -> bytes:
    """Encode raw bytes with dancingbits and prepend 0x00 header byte."""
    out = bytearray(b"\x00")
    full_blocks = (len(raw_bytes) // 8) * 8
    for grand in range(0, full_blocks, 8):
        block = raw_bytes[grand : grand + 8]
        fudge_base = grand % 1024
        fe50 = bytearray(8)
        for hacki in range(8):
            fe50[row[hacki]] = _dance(block[hacki], fudge_base + hacki)
        out.extend(fe50)
    # Remainder loop (matching ROM sub_fc42189c @ 0xFC421904-0xFC421922)
    for r7 in range(full_blocks, len(raw_bytes)):
        out.append(_dance(raw_bytes[r7], r7 % 1024))
    return bytes(out)


class TestPort19DiskbootEncoding(unittest.TestCase):
    """Test suite for PORT-19 DISKBOOT.BIN encoding acceptance."""

    @classmethod
    def setUpClass(cls):
        """Ensure candidate artifacts exist by running builder if missing."""
        if not DISKBOOT_BIN.exists() or not LOADER_BIN.exists():
            build_script = REPO_ROOT / "tools" / "build_candidate_port2a.py"
            res = subprocess.run([sys.executable, str(build_script)], check=True)
            assert res.returncode == 0

    def test_candidate_diskboot_byte_zero_is_zero(self):
        """ROM 0xFC54DE3A-0xFC54DE3C requires byte 0 to be 0x00; non-zero is rejected."""
        with open(DISKBOOT_BIN, "rb") as f:
            b0 = f.read(1)
        self.assertEqual(
            b0,
            b"\x00",
            f"Expected leading header byte 0x00 (ROM 0xFC54DE3A check), got {b0!r}",
        )

    def test_candidate_diskboot_size(self):
        """DISKBOOT.BIN size must equal candidate_loader.bin size + 1 (header byte)."""
        diskboot_sz = DISKBOOT_BIN.stat().st_size
        loader_sz = LOADER_BIN.stat().st_size
        self.assertEqual(
            diskboot_sz,
            loader_sz + 1,
            f"Expected DISKBOOT.BIN size {loader_sz + 1} bytes, got {diskboot_sz}",
        )

    def test_candidate_diskboot_row13_decodes_to_loader(self):
        """DISKBOOT.BIN decoded with Row 13 must match candidate_loader.bin bit-for-bit."""
        with open(DISKBOOT_BIN, "rb") as f:
            encoded = f.read()
        with open(LOADER_BIN, "rb") as f:
            expected_loader = f.read()

        decoded = decode_dancingbits(encoded, ROW13)
        self.assertEqual(
            decoded,
            expected_loader,
            "Decoded DISKBOOT.BIN does not match candidate_loader.bin bit-for-bit!",
        )

    def test_wrong_encoding_raw_binary_fails(self):
        """A raw unencoded binary must FAIL the decoding assertion.

        If a raw binary is placed on card without dancingbits, ROM sub_fc54de38
        either rejects it at 0xFC54DE3C (if byte 0 != 0) or descrambles raw code
        into garbage instructions at 0xFC42189C (if byte 0 == 0).
        """
        with open(LOADER_BIN, "rb") as f:
            raw_bytes = f.read()

        # Case A: Raw binary with non-zero byte 0 (e.g. Thumb-2 instruction)
        raw_non_zero = b"\x01" + raw_bytes[1:]
        with self.assertRaises(ValueError) as ctx:
            decode_dancingbits(raw_non_zero, ROW13)
        self.assertIn("rejects byte 0 != 0x00", str(ctx.exception))

        # Case B: Raw binary with forced byte 0 == 0x00 passed through decoder
        raw_with_zero = b"\x00" + raw_bytes
        decoded_garbage = decode_dancingbits(raw_with_zero, ROW13)
        self.assertNotEqual(
            decoded_garbage,
            raw_bytes,
            "Raw binary unexpectedly matched after dancingbits decode!",
        )

    def test_wrong_encoding_synthetic_permutation_fails(self):
        """A binary encoded with a synthetic wrong permutation must FAIL decode."""
        with open(LOADER_BIN, "rb") as f:
            raw_bytes = f.read()

        # Encode with the synthetic wrong permutation
        wrong_encoded = encode_dancingbits(raw_bytes, SYNTHETIC_WRONG_PERMUTATION)
        decoded_with_row13 = decode_dancingbits(wrong_encoded, ROW13)

        self.assertNotEqual(
            decoded_with_row13,
            raw_bytes,
            "Synthetic wrong-permutation binary unexpectedly matched Row 13 decode!",
        )

    def test_wrong_encoding_unencoded_suffix_fails(self):
        """Negative test: binary with raw unencoded partial trailing block fails decode.

        With a 12-byte linked image (bytes 0-7, then four 0x00 bytes), if only the
        first 8 bytes are encoded and the 4-byte suffix stays raw (plus leading 0x00
        header byte), the ROM remainder loop at 0xFC421904-0xFC421922 decodes the
        trailing raw [0x00, 0x00, 0x00, 0x00] into ff00ffff, causing the comparison
        against the linked image to FAIL.
        """
        linked_image = bytes(range(8)) + b"\x00\x00\x00\x00"
        # First 8 bytes encoded with Row 13 + leading 0x00 byte; trailing 4 bytes stay raw
        encoded_8 = encode_dancingbits(linked_image[:8], ROW13)  # b"\x00" + 8 bytes
        partially_encoded = encoded_8 + b"\x00\x00\x00\x00"

        decoded = decode_dancingbits(partially_encoded, ROW13)
        # Assert the decoded suffix matches the ROM remainder loop output ff00ffff
        self.assertEqual(
            decoded[8:],
            bytes.fromhex("ff00ffff"),
            "Expected ROM remainder loop @ 0xFC421904-0xFC421922 to decode raw [0x00]*4 into ff00ffff",
        )
        self.assertNotEqual(
            decoded,
            linked_image,
            "Binary with unencoded suffix unexpectedly matched linked image!",
        )

    def test_round_trip_non_multiple_of_eight_lengths(self):
        """Positive test: round-trip encoding and decoding for lengths not multiples of 8.

        Verifies that trailing partial blocks (len % 8 != 0) correctly round-trip
        through encode_dancingbits and decode_dancingbits via the ROM remainder loop
        at 0xFC421904-0xFC421922.
        """
        for length in [1, 2, 3, 5, 7, 9, 12, 13, 15, 23, 77, 123, 1025]:
            raw_data = bytes((i * 37 + 11) & 0xFF for i in range(length))
            encoded = encode_dancingbits(raw_data, ROW13)
            self.assertEqual(encoded[0], 0, "Leading byte 0 must be 0x00")
            self.assertEqual(len(encoded), len(raw_data) + 1)
            decoded = decode_dancingbits(encoded, ROW13)
            self.assertEqual(
                decoded,
                raw_data,
                f"Round-trip failed for non-multiple-of-8 length {length}",
            )

    def test_architectural_invariants(self):
        """Verify boot_witness remains 0x0035F7A0 and _end remains 0x00366CB0."""
        self.assertTrue(MANIFEST_JSON.exists(), f"Missing {MANIFEST_JSON}")
        with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
            m = json.load(f)

        arch = m.get("architectural_invariants", {})
        self.assertEqual(
            arch.get("boot_witness_addr"),
            f"0x{EXPECTED_BOOT_WITNESS:08X}",
            f"boot_witness mismatch in manifest: expected 0x{EXPECTED_BOOT_WITNESS:08X}",
        )
        self.assertEqual(
            arch.get("core_end_symbol"),
            f"0x{EXPECTED_CORE_END:08X}",
            f"_end mismatch in manifest: expected 0x{EXPECTED_CORE_END:08X}",
        )

    def test_evidence_manifest_validation(self):
        """docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json must pass validator."""
        self.assertTrue(EVIDENCE_MANIFEST.exists(), f"Missing {EVIDENCE_MANIFEST}")
        validator_script = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
        res = subprocess.run(
            [sys.executable, str(validator_script), "--manifest", str(EVIDENCE_MANIFEST), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Evidence validator failed with exit {res.returncode}:\n{res.stderr}\n{res.stdout}",
        )
        data = json.loads(res.stdout)
        self.assertTrue(data.get("is_valid"), f"Manifest invalid: {data}")
        self.assertEqual(data.get("error_count"), 0, f"Manifest errors: {data}")


if __name__ == "__main__":
    unittest.main()
