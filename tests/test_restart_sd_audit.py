#!/usr/bin/env python3
"""Offline ROM pins for the restart SD host audit (docs/RESTART_SD_HOST_AUDIT.md).

Read-only: never builds, never touches candidate_port2a/ or production files.
"""

import os
import struct
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROM_PATH = os.path.join(REPO_ROOT, "firmware", "dumps", "GM1.10C", "PRIMARY.BIN")

ROM_BASE = 0xFC000000
# High RAM image (SD driver), recopied by boot(): (ram_start, ram_end, rom_src)
ROM_COPIES = [
    (0x010E1000, 0x01107D00, 0xFCEC854C),
    (0x00008000, 0x0003F4F4, 0xFCE91058),
]
PROTO_STUBS_S = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "stubs_prototype.S"
)
PROTO_ELF = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "prototype_main.elf"
)

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


@unittest.skipUnless(os.path.exists(ROM_PATH), "GM1.10C ROM dump not present")
class TestRestartSdRomEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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


class TestRestartSdPrototypeImplementation(unittest.TestCase):
    """Verifies the reviewed minimal prototype fix for RESTART-SD-1."""

    def test_task_startup_my_omits_startdiskboot_and_calls_sd1stinit_veneer(self):
        boot_proto_c = os.path.join(
            REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_prototype.c"
        )
        with open(boot_proto_c) as f:
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
        with open(PROTO_STUBS_S) as f:
            stubs_src = f.read()
        self.assertIn("STUB(fc05c4e0)", stubs_src)
        self.assertIn("STUB2(fc31b1f4)", stubs_src)

    def test_prototype_elf_resolves_symbols(self):
        if not os.path.exists(PROTO_ELF):
            self.skipTest("prototype_main.elf not built")
        nm = os.path.join(
            REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin", "arm-none-eabi-nm"
        )
        if not os.path.exists(nm):
            self.skipTest("Toolchain nm not present")
        import subprocess
        out = subprocess.check_output([nm, PROTO_ELF]).decode()
        self.assertIn("sub_fc05c4e0", out)
        self.assertIn("sub_fc31b1f4", out)


if __name__ == "__main__":
    unittest.main()
