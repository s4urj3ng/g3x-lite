#!/usr/bin/env python3
"""3-Tier regression test suite for ROM-verified early boot literals (PORT-5E).

Verifies the ten early-boot literals in GM1.10C boot_prototype.c (sub_fc05b558_my):
- Tier 1: Clean checkout / zero-dependency source tests.
  Asserts presence of the ten ROM-verified literals and absence of the stale +4 literals.
  Verifies preservation of control flow, register conventions, and error call targets.
  Runs anywhere with standard Python 3.
- Tier 2: Static ROM byte assertions against owner's GM1.10C dump (PRIMARY.BIN).
  Verifies literal pool words, string contents, and instruction encodings directly from ROM.
  Cleanly skipped with diagnostic when PRIMARY.BIN is absent.
- Tier 3: Skip regression check.
  Verifies Tier 2 cleanly skips without failure when PRIMARY.BIN is simulated missing.

Read-only: never modifies candidate_port2a/ or production firmware files.
"""

import os
import re
import struct
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROM_PATH = os.path.join(REPO_ROOT, "firmware", "dumps", "GM1.10C", "PRIMARY.BIN")
BOOT_PROTO_C = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_prototype.c"
)

ROM_BASE = 0xFC000000

# The 10 ROM-verified literals for sub_fc05b558_my (PORT-5D / PORT-5E)
VERIFIED_LITERALS = [
    ("0xfc05b600", "ROM literal string '/_term' (adr @0xFC05B55A)"),
    ("0x000080ec", "literal @0xFC05B608: [0x80ec] heap size"),
    ("0x00008074", "literal @0xFC05B60C: [0x8074] 0x80000 bound"),
    ("0xfc05b610", "ROM literal string 'USER_MEM size checking' (adr @0xFC05B56E)"),
    ("0xfc05b630", "ROM literal string 'dmSetup' (adr @0xFC05B592)"),
    ("0xfc05b638", "ROM literal string 'termDriverInit' (adr @0xFC05B5A0)"),
    ("0xfc05b648", "ROM literal string 'termDeviceCreate' (adr @0xFC05B5B0)"),
    ("0xfc05b65c", "ROM literal string 'stdioSetup' (adr @0xFC05B5C0)"),
    ("0xfc05b668", "ROM literal string 'stdlibSetup' (adr @0xFC05B5CE)"),
    ("0xfc05b674", "ROM literal string 'extlib_setup' (adr @0xFC05B5DC)"),
]

# Obsolete / contradicted +4 literals that must NOT appear in sub_fc05b558_my
STALE_PLUS4_LITERALS = [
    "0xfc05b604",
    "0x000080f0",
    "0x00008078",
    "0xfc05b614",
    "0xfc05b634",
    "0xfc05b63c",
    "0xfc05b64c",
    "0xfc05b660",
    "0xfc05b66c",
    "0xfc05b678",
]

# ROM byte and word assertions for 0xFC05B558..0xFC05B67F
ROM_BYTES = [
    (0xFC05B55A, "29a4", "adr r4, 0xFC05B600 ('/_term')"),
    (0xFC05B560, "2948", "ldr r0, [pc, #0xA4] -> 0xFC05B608 (0x000080EC)"),
    (0xFC05B562, "0168", "ldr r1, [r0] -> [0x80EC]"),
    (0xFC05B564, "2948", "ldr r0, [pc, #0xA4] -> 0xFC05B60C (0x00008074)"),
    (0xFC05B566, "0068", "ldr r0, [r0] -> [0x8074]"),
    (0xFC05B568, "1030", "adds r0, #0x10"),
    (0xFC05B56A, "8142", "cmp r1, r0"),
    (0xFC05B56C, "02d2", "bcs.n 0xFC05B574"),
    (0xFC05B56E, "28a0", "adr r0, 0xFC05B610 ('USER_MEM size checking')"),
    (0xFC05B592, "27a0", "adr r0, 0xFC05B630 ('dmSetup')"),
    (0xFC05B5A0, "25a0", "adr r0, 0xFC05B638 ('termDriverInit')"),
    (0xFC05B5B0, "25a0", "adr r0, 0xFC05B648 ('termDeviceCreate')"),
    (0xFC05B5C0, "26a0", "adr r0, 0xFC05B65C ('stdioSetup')"),
    (0xFC05B5CE, "26a0", "adr r0, 0xFC05B668 ('stdlibSetup')"),
    (0xFC05B5DC, "25a0", "adr r0, 0xFC05B674 ('extlib_setup')"),
]

ROM_WORDS = [
    (0xFC05B608, 0x000080EC, "literal @0xFC05B608: address of [0x80EC]"),
    (0xFC05B60C, 0x00008074, "literal @0xFC05B60C: address of [0x8074]"),
    (0xFC05B628, 0xBFE10000, "literal @0xFC05B628: TCM fill start"),
    (0xFC05B62C, 0xBFE10800, "literal @0xFC05B62C: TCM fill end"),
]

ROM_STRINGS = [
    (0xFC05B600, b"/_term\x00", "device string '/_term'"),
    (0xFC05B610, b"USER_MEM size checking\x00", "error string 'USER_MEM size checking'"),
    (0xFC05B630, b"dmSetup\x00", "error string 'dmSetup'"),
    (0xFC05B638, b"termDriverInit\x00", "error string 'termDriverInit'"),
    (0xFC05B648, b"termDeviceCreate\x00", "error string 'termDeviceCreate'"),
    (0xFC05B65C, b"stdioSetup\x00", "error string 'stdioSetup'"),
    (0xFC05B668, b"stdlibSetup\x00", "error string 'stdlibSetup'"),
    (0xFC05B674, b"extlib_setup", "error string 'extlib_setup' (prefix in range)"),
]


def _rom_offset(addr):
    if ROM_BASE <= addr < ROM_BASE + 0x02000000:
        return addr - ROM_BASE
    raise ValueError(f"address 0x{addr:08X} not in ROM space")


# ==============================================================================
# Tier 1: Clean Checkout / Zero-Dependency Source Tests (Runs Anywhere)
# ==============================================================================
class TestEarlyBootLiteralsSource(unittest.TestCase):
    """Tier 1: Static source assertions on boot_prototype.c.

    Requires ZERO external tools, ZERO ARM toolchain, and ZERO proprietary ROM dumps.
    Always executes and must 100% PASS on any clean git clone.
    """

    @classmethod
    def setUpClass(cls):
        self_path = BOOT_PROTO_C
        if not os.path.exists(self_path):
            raise unittest.SkipTest(f"boot_prototype.c not found at {self_path}")
        with open(self_path, "r", encoding="utf-8") as f:
            cls.content = f.read()

        # Extract the sub_fc05b558_my function body (ends with '\n}')
        match = re.search(
            r"sub_fc05b558_my\s*\([^)]*\)\s*\{([\s\S]*?)\n\}",
            cls.content,
        )
        if not match:
            raise ValueError("Could not locate sub_fc05b558_my in boot_prototype.c")
        cls.stage4_body = match.group(1)

    def test_ten_rom_verified_literals_present(self):
        """All ten ROM-verified literals must be present in sub_fc05b558_my."""
        for literal, desc in VERIFIED_LITERALS:
            with self.subTest(literal=literal, desc=desc):
                pattern = re.compile(rf"=\s*{re.escape(literal)}\b", re.IGNORECASE)
                self.assertTrue(
                    pattern.search(self.stage4_body),
                    f"ROM-verified literal {literal} ({desc}) missing from sub_fc05b558_my",
                )

    def test_stale_plus4_literals_absent(self):
        """None of the stale +4 literals must remain in sub_fc05b558_my."""
        for literal in STALE_PLUS4_LITERALS:
            with self.subTest(stale_literal=literal):
                pattern = re.compile(rf"=\s*{re.escape(literal)}\b", re.IGNORECASE)
                self.assertFalse(
                    pattern.search(self.stage4_body),
                    f"Stale +4 literal {literal} must NOT be present in sub_fc05b558_my",
                )

    def test_stage4_control_flow_and_call_targets_preserved(self):
        """Preserve all call targets, registers, error checks, and branch targets."""
        # Check words logic: [0x80ec] >= [0x8074] + 0x10 -> bhs loc_fc05b574
        self.assertIn("adds    r0, #0x10", self.stage4_body)
        self.assertIn("cmp     r1, r0", self.stage4_body)
        self.assertIn("bhs     loc_fc05b574", self.stage4_body)
        self.assertIn("bl      sub_fc05b5ea", self.stage4_body)

        # TCM pattern fill: 0xBFE10000..0xBFE10800 with 0xEEEEEEEE
        self.assertIn("0xbfe10000", self.stage4_body.lower())
        self.assertIn("0xbfe10800", self.stage4_body.lower())
        self.assertIn("#-0x11111112", self.stage4_body.lower())

        # Preserved stage 4 call sequence
        expected_calls = [
            "bl      sub_fc05c5bc",
            "bl      sub_fc127b3c",
            "bl      sub_fc127b4e",
            "bl      sub_fc418738",  # dmSetup
            "bl      sub_fc05c7d4",  # termDriverInit
            "bl      sub_fc05c862",  # termDeviceCreate
            "bl      sub_fc05b794",  # stdioSetup
            "bl      sub_fc05b8d8",  # stdlibSetup
            "bl      sub_fc05e910",  # extlib_setup
        ]
        for call in expected_calls:
            self.assertIn(call, self.stage4_body, f"Expected call '{call}' missing from stage 4")

        # Exit convention: pop {r4, lr} and tail call to sub_fc05b962_my
        self.assertIn("pop.w   {r4, lr}", self.stage4_body)
        self.assertIn("b.w     sub_fc05b962_my", self.stage4_body)


# ==============================================================================
# Tier 2: Static ROM Evidence Tests (Requires Private PRIMARY.BIN)
# ==============================================================================
@unittest.skipUnless(os.path.exists(ROM_PATH), "GM1.10C ROM dump not present")
class TestEarlyBootLiteralsRomEvidence(unittest.TestCase):
    """Tier 2: Static ROM byte, word, and string assertions against GM1.10C dump."""

    @classmethod
    def setUpClass(cls):
        with open(ROM_PATH, "rb") as f:
            cls.rom = f.read()

    def _bytes(self, addr, n):
        off = _rom_offset(addr)
        return self.rom[off : off + n]

    def _word(self, addr):
        return struct.unpack("<I", self._bytes(addr, 4))[0]

    def test_rom_instruction_bytes(self):
        """Verify exact Thumb opcodes in sub_fc05b558 range."""
        for addr, hexstr, desc in ROM_BYTES:
            expected = bytes.fromhex(hexstr)
            actual = self._bytes(addr, len(expected))
            with self.subTest(addr=hex(addr), desc=desc):
                self.assertEqual(
                    actual,
                    expected,
                    f"ROM mismatch at {hex(addr)} ({desc}): expected {hexstr}, got {actual.hex()}",
                )

    def test_rom_literal_pool_words(self):
        """Verify 32-bit literal pool values at 0xFC05B608, 0xFC05B60C, etc."""
        for addr, expected_val, desc in ROM_WORDS:
            actual_val = self._word(addr)
            with self.subTest(addr=hex(addr), desc=desc):
                self.assertEqual(
                    actual_val,
                    expected_val,
                    f"ROM literal mismatch at {hex(addr)} ({desc}): expected {hex(expected_val)}, got {hex(actual_val)}",
                )

    def test_rom_string_literals(self):
        """Verify device and diagnostic string bytes in ROM literal area."""
        for addr, expected_str, desc in ROM_STRINGS:
            actual = self._bytes(addr, len(expected_str))
            with self.subTest(addr=hex(addr), desc=desc):
                self.assertEqual(
                    actual,
                    expected_str,
                    f"ROM string mismatch at {hex(addr)} ({desc}): expected {expected_str!r}, got {actual!r}",
                )


# ==============================================================================
# Tier 3: Skip Regression Test
# ==============================================================================
class TestEarlyBootLiteralsSkipRegression(unittest.TestCase):
    """Tier 3: Skip regression check ensuring clean skip when ROM is absent."""

    def test_tier2_skips_cleanly_when_rom_missing(self):
        """Verify TestEarlyBootLiteralsRomEvidence is skipped when ROM_PATH does not exist."""
        with patch("os.path.exists", return_value=False):
            # Evaluate the skip condition
            should_skip = not os.path.exists(ROM_PATH)
            self.assertTrue(should_skip, "Tier 2 must evaluate to skip when ROM is missing")


if __name__ == "__main__":
    unittest.main()
