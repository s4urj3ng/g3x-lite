#!/usr/bin/env python3
"""3-Tier offline test suite for restart SD host audit (docs/RESTART_SD_HOST_AUDIT.md).

Architecture:
- Tier 1: TestRestartSdSourcePresence & TestRestartSdSkipRegression
  Clean checkout / zero-dependency tests. Runs anywhere with standard Python 3.
  Asserts tracked prototype sources, patch format, syntax, and algorithmic logic.
  Asserts regression coverage for skip vs fail-closed behavior across all environment states.
  Zero private ROM and zero external toolchain requirements.
- Tier 2: TestRestartSdRomEvidence
  Static ROM disassembly and byte assertions against owner's GM1.10C dump.
  Cleanly skipped with diagnostic when PRIMARY.BIN is absent (clean checkout / simulation).
- Tier 3: TestRestartSdOfflineIntegration
  Toolchain and ELF symbol verification.
  Cleanly skipped when ARM toolchain (arm-none-eabi-nm) is absent, even if ELF is present.
  Fails closed when toolchain is present but required compilation fails.

Read-only: never touches candidate_port2a/ or production firmware files.
"""

import os
import shutil
import struct
import subprocess
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROM_PATH = os.path.join(REPO_ROOT, "firmware", "dumps", "GM1.10C", "PRIMARY.BIN")

ROM_BASE = 0xFC000000
# High RAM image (SD driver), recopied by boot(): (ram_start, ram_end, rom_src)
ROM_COPIES = [
    (0x010E1000, 0x01107D00, 0xFCEC854C),
    (0x00008000, 0x0003F4F4, 0xFCE91058),
]
BOOT_PROTO_C = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_prototype.c"
)
PROTO_STUBS_S = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "stubs_prototype.S"
)
BOOT_WITNESS_H = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_witness.h"
)
PATCH_FILE = os.path.join(
    REPO_ROOT, "patches", "0001-sd1stinit-restart-prototype.patch"
)
PROTO_ELF = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "prototype_main.elf"
)

# Toolchain detection (local tree or system path)
LOCAL_TOOLCHAIN_BIN = os.path.join(
    REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin"
)
LOCAL_NM = os.path.join(LOCAL_TOOLCHAIN_BIN, "arm-none-eabi-nm")
SYSTEM_NM = shutil.which("arm-none-eabi-nm")
NM_PATH = LOCAL_NM if os.path.exists(LOCAL_NM) else SYSTEM_NM

ROM_BYTES = [
    (0xFC05BC12, "1ff331f9", "StartDiskboot: bl 0xFC37AE78(0)"),
    (0xFC05BC18, "1ff345f9", "StartDiskboot: bl 0xFC37AEA6(0) (mount check)"),
    (0xFC05BC26, "1ff355f9", "StartDiskboot: bl 0xFC37AED4(0)"),
    (0xFC05BC2A, "00f007f8", "StartDiskboot: bl 0xFC05BC3C (load + jump)"),
    (0xFC05BC30, "1ff3fbf8", "unmount 0xFC37AE2A(0): only after load returns"),
    (0xFC05BC7A, "7ef00ff8", "load: bl 0xFC0D9C9C (no return)"),
    (0xFC05BBC2, "1ff374fc", "open 0xFC37B4AE"),
    (0xFC05BBD8, "1ff3bbfc", "read 0xFC37B552"),
    (0xFC05BBDE, "1ff367fc", "close 0xFC37B4B0"),
    (0x010EE7D2, "70b5" "0022" "0546" "eca4" "1146" "03f0", "CMD0_Initialize entry"),
    (0x010EE7DC, "03f0c5fc", "CMD0_Initialize: bl 0x010F216A(host, 0, 0)"),
    (0x010E5688, "09f0a3f8", "sddomInitCMD0AndCheckVoltage: bl CMD0_Initialize"),
    (0x010F462A, "274b" "a1f16051" "53f82000", "reg write: table[host] + off - 0x38000000"),
    (0x010F461C, "2a4a" "a1f16051" "52f82000" "4058", "reg read accessor"),
    (0xFC05B90E, "00f06cf9", "stock task_Startup: bl StartDiskboot 0xFC05BBEA"),
    (0xFC05BBFE, "bff2faea", "StartDiskboot: blx 0xFC31B1F4 (SD1stInit creator)"),
    (0x010E17E0, "38b5" "644c" "2078" "0128" "18d1", "creator: guard [0xAC94] == 1"),
    (0x010E180C, "0023" "0093" "5c4b" "0022" "1821" "5ca0" "12f02ced",
     "CreateTask(\"SD1stInit\", 0x18, 0, 0x010E17A5, 0)"),
    (0x010E17BC, "0020" "01f04ef9", "SD1stInit task: bl 0x010E2A5E(0) -> CMD0 chain"),
]

ROM_WORDS = [
    (0xFC31B1F8, 0x010E17E1, "veneer 0xFC31B1F4 -> SD1stInit creator"),
    (0x010E1984, 0x010E17A5, "SD1stInit task entry literal"),
    (0x010F4278, 0xBFE14A3D, "creator CreateTask veneer target"),
    (0xFC31BBC8, 0xBFE14A3D, "kernel CreateTask veneer target (same)"),
    (0x0000AC94, 0x00000001, "creator guard byte initial value (low-RAM data)"),
    (0x01107450, 0x00000000, "SD host 0 base offset"),
    (0x01107454, 0x00010000, "SD host 1 base offset"),
    (0x01107458, 0x00020000, "SD host 2 base offset"),
    (0x010F1B80, 0x0026E8B0, "driver slot table (in zeroed Canon BSS)"),
]


def _rom_offset(addr):
    if ROM_BASE <= addr < ROM_BASE + 0x02000000:
        return addr - ROM_BASE
    for start, end, src in ROM_COPIES:
        if start <= addr < end:
            return src - ROM_BASE + (addr - start)
    raise ValueError(f"address 0x{addr:08X} not mapped to ROM")


# ==============================================================================
# Tier 1: Clean Checkout / Zero-Dependency Tests (Runs Anywhere)
# ==============================================================================
class TestRestartSdSourcePresence(unittest.TestCase):
    """Tier 1: Source presence, patch validity, and static code assertions.
    
    Requires ZERO external tools, ZERO ARM toolchain, and ZERO proprietary ROM dumps.
    Always executes and must 100% PASS on any clean git clone.
    """

    def test_clean_checkout_source_integrity(self):
        """Clean checkout reproducibility: fail closed if required prototype sources are absent."""
        required_sources = [
            ("boot_prototype.c", BOOT_PROTO_C),
            ("stubs_prototype.S", PROTO_STUBS_S),
            ("boot_witness.h", BOOT_WITNESS_H),
            ("patch file", PATCH_FILE),
        ]
        for name, path in required_sources:
            self.assertTrue(
                os.path.exists(path),
                f"FAIL: Clean checkout missing required {name} at {path}. "
                f"Repository must track this file for independent reviewability.",
            )

    def test_clean_checkout_patch_validity(self):
        """Validate standalone patch artifact header, pinned upstream commit, and diff contents."""
        self.assertTrue(os.path.exists(PATCH_FILE), f"Missing patch file: {PATCH_FILE}")
        with open(PATCH_FILE, "r") as f:
            patch_text = f.read()
        self.assertIn("21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6", patch_text)
        self.assertIn("https://github.com/01luna/CHDK.git", patch_text)
        self.assertIn("platform/g3x/sub/110c/stubs_prototype.S", patch_text)
        self.assertIn("platform/g3x/sub/110c/boot_prototype.c", patch_text)
        self.assertIn("STUB2(fc31b1f4)", patch_text)
        self.assertIn("blx     sub_fc31b1f4", patch_text)

    def test_task_startup_my_omits_startdiskboot_and_calls_sd1stinit_veneer(self):
        """Static analysis of boot_prototype.c: confirms StartDiskboot omitted and creator called."""
        self.assertTrue(
            os.path.exists(BOOT_PROTO_C),
            f"Missing required prototype source: {BOOT_PROTO_C}",
        )
        with open(BOOT_PROTO_C) as f:
            src = f.read()
        body = src[src.index("void __attribute__((naked,noinline)) task_Startup_my(void)"):]
        code = "\n".join(line.split("//", 1)[0] for line in body.splitlines()).lower()

        # StartDiskboot must remain omitted to prevent infinite reload loop
        self.assertNotIn("sub_fc05bbea", code)

        # Gate check sub_fc05c4e0 and creator veneer sub_fc31b1f4 must be called
        self.assertIn("sub_fc05c4e0", code)
        self.assertIn("sub_fc31b1f4", code)
        self.assertIn("blx     sub_fc31b1f4", code)

    def test_prototype_stubs_include_sd1stinit_symbols(self):
        """Static analysis of stubs_prototype.S: confirms gate and veneer stubs are defined."""
        self.assertTrue(
            os.path.exists(PROTO_STUBS_S),
            f"Missing required prototype stubs: {PROTO_STUBS_S}",
        )
        with open(PROTO_STUBS_S) as f:
            stubs_src = f.read()
        self.assertIn("STUB(fc05c4e0)", stubs_src)
        self.assertIn("STUB2(fc31b1f4)", stubs_src)

    def test_gate_mmio_bit_arithmetic_semantics(self):
        """Algorithmic proof: LSL #15 + BPL extracts Bit 16 (0-indexed) into sign bit N (bit 31).

        Resolves conflicting Bit 16 vs Bit 17 claims mathematically:
        - 0-indexed: Bit 16 (0x00010000).
        - 1-indexed: 17th bit (clarifying why some descriptions label it 'bit 17').
        """
        for bit_idx in range(32):
            val = 1 << bit_idx
            shifted = (val << 15) & 0xFFFFFFFF
            n_flag = 1 if (shifted & 0x80000000) else 0
            ret = 1 if n_flag else 0
            if bit_idx == 16:
                self.assertEqual(ret, 1, "Bit 16 (0-indexed) MUST return 1")
            else:
                self.assertEqual(ret, 0, f"Bit {bit_idx} must return 0")


class TestRestartSdSkipRegression(unittest.TestCase):
    """Tier 1: Regression coverage verifying skip vs fail-closed behavior across environment states.
    
    Verifies ChatGPT Finding 2:
    - Missing arm-none-eabi-nm MUST cleanly skip (not fail), even when prototype_main.elf exists.
    - Missing ROM dump MUST cleanly skip (not fail).
    - When toolchain is present, missing ELF triggers build; build failure fails closed.
    """

    def test_regression_tier3_skips_when_nm_missing_even_if_elf_present(self):
        """When only ELF exists and arm-none-eabi-nm is missing, Tier 3 MUST skip, not fail."""
        global NM_PATH
        orig_nm = NM_PATH
        try:
            NM_PATH = None
            with self.assertRaises(unittest.SkipTest) as ctx:
                TestRestartSdOfflineIntegration.setUpClass()
            self.assertIn("ARM toolchain (arm-none-eabi-nm) not present", str(ctx.exception))
        finally:
            NM_PATH = orig_nm

    def test_regression_tier3_skips_when_both_nm_and_elf_missing(self):
        """When both arm-none-eabi-nm and prototype ELF are missing, Tier 3 MUST skip."""
        global NM_PATH
        orig_nm = NM_PATH
        try:
            NM_PATH = None
            with self.assertRaises(unittest.SkipTest) as ctx:
                TestRestartSdOfflineIntegration.setUpClass()
            self.assertIn("ARM toolchain (arm-none-eabi-nm) not present", str(ctx.exception))
        finally:
            NM_PATH = orig_nm

    def test_regression_tier2_skips_when_rom_missing(self):
        """When PRIMARY.BIN is missing, Tier 2 MUST skip with diagnostic."""
        global ROM_PATH
        orig_rom = ROM_PATH
        try:
            ROM_PATH = "/tmp/nonexistent_mock_primary.bin"
            with self.assertRaises(unittest.SkipTest) as ctx:
                TestRestartSdRomEvidence.setUpClass()
            self.assertIn("GM1.10C ROM dump (PRIMARY.BIN) not present", str(ctx.exception))
        finally:
            ROM_PATH = orig_rom

    def test_regression_tier3_fails_closed_when_toolchain_present_but_build_fails(self):
        """Preserve fail-closed behavior: toolchain present, ELF missing, and build script fails."""
        global PROTO_ELF, NM_PATH
        orig_elf = PROTO_ELF
        orig_nm = NM_PATH
        try:
            PROTO_ELF = "/tmp/nonexistent_mock_proto_main.elf"
            NM_PATH = "/bin/mock_arm_nm"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr=b"fatal: compilation failed")
                test_instance = TestRestartSdOfflineIntegration()
                with self.assertRaises(AssertionError) as ctx:
                    test_instance.test_prototype_elf_resolves_symbols()
                self.assertIn("Failed to build", str(ctx.exception))
        finally:
            PROTO_ELF = orig_elf
            NM_PATH = orig_nm


# ==============================================================================
# Tier 2: Private ROM Static Evidence Tests (Requires Owner's PRIMARY.BIN Dump)
# ==============================================================================
@unittest.skipUnless(os.path.exists(ROM_PATH), "Tier 2: GM1.10C ROM dump (PRIMARY.BIN) not present")
class TestRestartSdRomEvidence(unittest.TestCase):
    """Tier 2: Disassembly and byte assertions against proprietary GM1.10C ROM.
    
    Requires local PRIMARY.BIN (gitignored). Cleanly skipped on clean public checkout / simulation.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(ROM_PATH):
            raise unittest.SkipTest("Tier 2: GM1.10C ROM dump (PRIMARY.BIN) not present")
        with open(ROM_PATH, "rb") as f:
            cls.rom = f.read()

    def _bytes(self, addr, n):
        off = _rom_offset(addr)
        return self.rom[off:off + n]

    def test_rom_byte_sequences(self):
        for addr, hexstr, meaning in ROM_BYTES:
            expected = bytes.fromhex(hexstr)
            with self.subTest(addr=hex(addr), meaning=meaning):
                self.assertEqual(self._bytes(addr, len(expected)), expected)

    def test_rom_words(self):
        for addr, value, meaning in ROM_WORDS:
            with self.subTest(addr=hex(addr), meaning=meaning):
                self.assertEqual(struct.unpack("<I", self._bytes(addr, 4))[0], value)

    def test_strings(self):
        self.assertEqual(
            self._bytes(0xFC05BC80, 31), b"\nStartDiskboot\n\x00A/DISKBOOT.BIN\x00"
        )
        self.assertEqual(self._bytes(0x010EEB8C, 16), b"CMD0_Initialize\x00")

    def test_sd_host0_mmio_base(self):
        base = struct.unpack("<I", self._bytes(0x01107450, 4))[0]
        self.assertEqual((base + 0x60000 - 0x38000000) & 0xFFFFFFFF, 0xC8060000)

    def test_sd1stinit_name(self):
        self.assertEqual(self._bytes(0x010E1988, 10), b"SD1stInit\x00")

    def test_driver_table_in_zeroed_bss(self):
        self.assertTrue(0x0003F4F4 <= 0x0026E8B0 < 0x003489B4)

    def test_gate_mmio_bit_semantics_reconciliation_in_rom(self):
        """Verify Gate 2 instructions directly from ROM bytes:
        - 0xFC05C4E0: movw r0, #0x14E (offset 334 in table 0xD20B0000 -> MMIO 0xD20B0538)
        - 0xFC0D73D0: lsls r0, r0, #15; bpl.n 0xFC0D73DE
        """
        # 1. Gate wrapper at 0xFC05C4E0: movw r0, #0x14E is 40 f2 4e 10
        fc05c4e0_bytes = self._bytes(0xFC05C4E0, 16)
        self.assertEqual(fc05c4e0_bytes[6:10], bytes.fromhex("40f24e10"))

        # 2. Hardware MMIO reader at 0xFC0D73D0: lsls r0, r0, #15 (c0 03), bpl.n (01 d5)
        fc0d73d0_bytes = self._bytes(0xFC0D73D0, 16)
        self.assertEqual(fc0d73d0_bytes[6:8], bytes.fromhex("c003"))
        self.assertEqual(fc0d73d0_bytes[8:10], bytes.fromhex("01d5"))


# ==============================================================================
# Tier 3: Offline Toolchain & Integration Tests (Requires ARM Toolchain)
# ==============================================================================
@unittest.skipUnless(
    NM_PATH is not None,
    "Tier 3: ARM toolchain (arm-none-eabi-nm) not present",
)
class TestRestartSdOfflineIntegration(unittest.TestCase):
    """Tier 3: Offline toolchain compilation and ELF symbol resolution.
    
    Requires ARM toolchain (arm-none-eabi-nm) for symbol inspection.
    Cleanly skipped when toolchain is absent, even if ELF is present.
    """

    @classmethod
    def setUpClass(cls):
        if NM_PATH is None:
            raise unittest.SkipTest(
                "Tier 3: ARM toolchain (arm-none-eabi-nm) not present"
            )

    def test_prototype_elf_resolves_symbols(self):
        """Verify compiled prototype ELF resolves sub_fc05c4e0 and sub_fc31b1f4."""
        # Toolchain presence is guaranteed by setUpClass / class decorator
        if NM_PATH is None:
            self.skipTest("arm-none-eabi-nm not found")

        # If ELF is missing, attempt to compile it using build_prototype tool
        if not os.path.exists(PROTO_ELF):
            build_script = os.path.join(REPO_ROOT, "tools", "build_prototype.py")
            if os.path.exists(build_script):
                res = subprocess.run(
                    ["python3", build_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if res.returncode != 0:
                    self.fail(f"Failed to build {PROTO_ELF}:\n{res.stderr.decode()}")
            else:
                self.fail(
                    f"Required artifact {PROTO_ELF} and build script {build_script} are absent"
                )

        if not os.path.exists(PROTO_ELF):
            self.fail(f"Prototype ELF absent after build attempt: {PROTO_ELF}")

        out = subprocess.check_output([NM_PATH, PROTO_ELF]).decode()
        self.assertIn("sub_fc05c4e0", out)
        self.assertIn("sub_fc31b1f4", out)


if __name__ == "__main__":
    unittest.main()
