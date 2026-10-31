#!/usr/bin/env python3
"""Unit tests for PORT-20 T2: Loader-Entry LED Signal Prologue in Opt-In Candidate.

Verifies:
1. Default build invariance:
   - Without opt-in flag, build output is byte-identical to PORT-19 candidate.
   - candidate_port2a/DISKBOOT.BIN SHA-256 == 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136
   - candidate_port2a/DISKBOOT.BIN size == 118001 bytes.
   - Core symbols boot_witness (0x0035F7A0) and _end (0x00366CB0) remain unchanged.
2. Opt-in flag directory separation:
   - --led writes artifacts to candidate_led/ (or --out-dir) and never overwrites candidate_port2a/.
   - candidate_port2a/ remains unaltered after building with --led.
   - G3X_LED=1 environment variable also enables the LED build.
3. Prologue verification:
   - Candidate loader entry (_start @ 0x8000) contains the prologue before falling through to the loader path.
   - Contains T1 VERIFIED MMIO address 0xD20B0884.
   - Contains T1 VERIFIED action-0 value 0x004d0002.
   - Contains T1 VERIFIED action-1 value 0x004c0003.
   - Contains bounded busy-wait delay loop with fixed constant 0x06000000 (subs, bne).
   - Contains memory barrier (dsb sy) after each MMIO store.
   - Contains NO cpsid, NO cpsie, NO msr, NO mrs in the prologue (interrupt/mode state unaltered).
   - Preserves registers (dead registers r0, r1, r2 and flags overwritten) and falls through to
     existing loader entry (ldr sp, =0x8000; b.w my_restart).
4. Manifest verification:
   - Records LED fields (register, action values, iterations) and trial_ready=True when inspector is verified.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PORT2A_DIR = REPO_ROOT / "candidate_port2a"
CANDIDATE_LED_DIR = REPO_ROOT / "candidate_led"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_candidate_port2a.py"
PROLOGUE_SOURCE = (
    REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_entry_led.S"
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001
EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0
EXPECTED_CORE_END_ADDR = 0x00366CB0

T1_LED_MMIO_ADDR = 0xD20B0884
T1_ACTION_0_VALUE = 0x004D0002
T1_ACTION_1_VALUE = 0x004C0003
T1_BUSY_WAIT_CONSTANT = 0x06000000


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort20LedCandidate(unittest.TestCase):
    """Test suite covering PORT-20 T2 LED candidate build, directory separation, and prologue."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(BUILD_SCRIPT.is_file(), f"Build script missing: {BUILD_SCRIPT}")
        cls.assertTrue(PROLOGUE_SOURCE.is_file(), f"Prologue source missing: {PROLOGUE_SOURCE}")

        # Build default candidate if not present
        if not (CANDIDATE_PORT2A_DIR / "DISKBOOT.BIN").is_file():
            res = subprocess.run(
                ["python3", str(BUILD_SCRIPT)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert res.returncode == 0, f"Default build failed: {res.stderr.decode()}"

        # Build LED candidate if not present
        if not (CANDIDATE_LED_DIR / "DISKBOOT.BIN").is_file():
            res = subprocess.run(
                ["python3", str(BUILD_SCRIPT), "--led"],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert res.returncode == 0, f"LED build failed: {res.stderr.decode()}"

    @classmethod
    def tearDownClass(cls):
        # Do not leave candidate_led committed or dirty in worktree
        if CANDIDATE_LED_DIR.is_dir():
            shutil.rmtree(CANDIDATE_LED_DIR, ignore_errors=True)

    def test_default_build_invariance(self):
        """Default build (flag OFF) must produce byte-identical candidate matching PORT-19."""
        diskboot_bin = CANDIDATE_PORT2A_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_PORT2A_DIR / "candidate_main.elf"

        # If not present, run default build
        if not diskboot_bin.is_file():
            cmd = ["python3", str(BUILD_SCRIPT)]
            res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(res.returncode, 0, f"Default build failed: {res.stderr.decode()}")

        self.assertTrue(diskboot_bin.is_file(), "candidate_port2a/DISKBOOT.BIN missing")
        actual_size = diskboot_bin.stat().st_size
        actual_hash = sha256_file(diskboot_bin)

        self.assertEqual(
            actual_size,
            EXPECTED_DEFAULT_DISKBOOT_SIZE,
            f"DISKBOOT.BIN size mismatch: expected {EXPECTED_DEFAULT_DISKBOOT_SIZE}, got {actual_size}",
        )
        self.assertEqual(
            actual_hash,
            EXPECTED_DEFAULT_DISKBOOT_SHA256,
            f"DISKBOOT.BIN SHA-256 mismatch: expected {EXPECTED_DEFAULT_DISKBOOT_SHA256}, got {actual_hash}",
        )

        # Core symbol verification
        res = subprocess.run(
            [str(NM), "-n", str(core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        sym_lines = res.stdout.splitlines()
        witness_line = [l for l in sym_lines if len(l.strip().split()) >= 3 and l.strip().split()[-1] == "boot_witness"]
        end_line = [l for l in sym_lines if len(l.strip().split()) >= 3 and l.strip().split()[-1] == "_end"]

        self.assertTrue(witness_line, "boot_witness symbol missing from core ELF")
        self.assertTrue(end_line, "_end symbol missing from core ELF")
        self.assertEqual(
            witness_line[0].split()[0],
            f"{EXPECTED_BOOT_WITNESS_ADDR:08x}",
            "boot_witness address shifted in default build",
        )
        self.assertEqual(
            end_line[0].split()[0],
            f"{EXPECTED_CORE_END_ADDR:08x}",
            "_end address shifted in default build",
        )

    def test_led_build_directory_separation(self):
        """Building with --led must write to candidate_led/ and not overwrite candidate_port2a/."""
        diskboot_default = CANDIDATE_PORT2A_DIR / "DISKBOOT.BIN"
        default_hash_before = sha256_file(diskboot_default)

        # Run --led build
        cmd = ["python3", str(BUILD_SCRIPT), "--led"]
        res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"LED build failed: {res.stderr.decode()}")

        led_diskboot = CANDIDATE_LED_DIR / "DISKBOOT.BIN"
        led_loader_elf = CANDIDATE_LED_DIR / "candidate_loader.elf"
        led_loader_bin = CANDIDATE_LED_DIR / "candidate_loader.bin"
        led_core_elf = CANDIDATE_LED_DIR / "candidate_main.elf"
        led_manifest = CANDIDATE_LED_DIR / "candidate_manifest.json"

        self.assertTrue(led_diskboot.is_file(), "candidate_led/DISKBOOT.BIN was not created")
        self.assertTrue(led_loader_elf.is_file(), "candidate_led/candidate_loader.elf missing")
        self.assertTrue(led_loader_bin.is_file(), "candidate_led/candidate_loader.bin missing")
        self.assertTrue(led_core_elf.is_file(), "candidate_led/candidate_main.elf missing")
        self.assertTrue(led_manifest.is_file(), "candidate_led/candidate_manifest.json missing")

        # Verify default build directory was NOT altered or overwritten
        default_hash_after = sha256_file(diskboot_default)
        self.assertEqual(
            default_hash_before,
            default_hash_after,
            "candidate_port2a/DISKBOOT.BIN was altered by --led build",
        )
        self.assertEqual(
            default_hash_after,
            EXPECTED_DEFAULT_DISKBOOT_SHA256,
            "candidate_port2a/DISKBOOT.BIN hash altered",
        )

        # Verify manifest flags
        with open(led_manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        self.assertEqual(manifest_data.get("status"), "OFFLINE_LED_CANDIDATE_BUILT")
        self.assertTrue(manifest_data.get("led_prologue_enabled"))
        self.assertEqual(manifest_data.get("led_register"), "0xD20B0884")
        self.assertEqual(
            manifest_data.get("led_values"),
            {"action_0": "0x004d0002", "action_1": "0x004c0003"},
        )
        self.assertEqual(manifest_data.get("led_busy_wait_iterations"), "0x06000000")
        self.assertTrue(manifest_data.get("trial_ready"))

    def test_custom_out_dir_option(self):
        """Custom --out-dir with --led writes to the specified directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cmd = ["python3", str(BUILD_SCRIPT), "--led", "--out-dir", tmp_dir]
            res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(res.returncode, 0, f"Custom out-dir build failed: {res.stderr.decode()}")

            tmp_diskboot = Path(tmp_dir) / "DISKBOOT.BIN"
            self.assertTrue(tmp_diskboot.is_file(), "DISKBOOT.BIN not written to custom out-dir")
            self.assertGreater(tmp_diskboot.stat().st_size, 0)

    def test_environment_variable_activation(self):
        """G3X_LED=1 activates the LED candidate build without CLI flag."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = dict(os.environ)
            env["G3X_LED"] = "1"
            cmd = ["python3", str(BUILD_SCRIPT), "--out-dir", tmp_dir]
            res = subprocess.run(
                cmd, cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.assertEqual(res.returncode, 0, f"Env build failed: {res.stderr.decode()}")

            tmp_manifest = Path(tmp_dir) / "candidate_manifest.json"
            self.assertTrue(tmp_manifest.is_file())
            with open(tmp_manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("status"), "OFFLINE_LED_CANDIDATE_BUILT")
            self.assertTrue(data.get("led_prologue_enabled"))
            self.assertTrue(data.get("trial_ready"))

    def test_loader_entry_prologue_disassembly(self):
        """candidate_loader.elf must contain the LED prologue without any CPSR/mode modifications."""
        led_loader_elf = CANDIDATE_LED_DIR / "candidate_loader.elf"
        if not led_loader_elf.is_file():
            cmd = ["python3", str(BUILD_SCRIPT), "--led"]
            res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(res.returncode, 0)

        proc = subprocess.run(
            [str(OBJDUMP), "-d", str(led_loader_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        disasm = proc.stdout

        # Extract disassembly from _start to compute_witness_checksum
        self.assertIn("00008000 <_start>:", disasm)
        start_idx = disasm.find("00008000 <_start>:")
        end_idx = disasm.find("00008030 <compute_witness_checksum", start_idx)
        self.assertNotEqual(end_idx, -1, "compute_witness_checksum boundary not found")
        start_section = disasm[start_idx:end_idx]

        # 1. Verify NO CPSR / interrupt / mode state changes
        self.assertNotIn("cpsid", start_section.lower(), "Prologue must NOT contain cpsid")
        self.assertNotIn("cpsie", start_section.lower(), "Prologue must NOT contain cpsie")
        self.assertNotIn("msr", start_section.lower(), "Prologue must NOT contain msr")
        self.assertNotIn("mrs", start_section.lower(), "Prologue must NOT contain mrs (PL0 check dropped)")

        # 2. Verify T1 MMIO address
        self.assertIn("d20b0884", start_section.lower(), "T1 address 0xD20B0884 missing in prologue")

        # 3. Verify T1 action values
        self.assertIn("004d0002", start_section.lower(), "T1 action-0 value 0x004D0002 missing in prologue")
        self.assertIn("004c0003", start_section.lower(), "T1 action-1 value 0x004C0003 missing in prologue")

        # 4. Verify bounded delay loop: fixed constant loop count (0x06000000 = 100663296)
        self.assertIn(
            "100663296",
            start_section,
            f"Bounded delay loop constant missing (expected {T1_BUSY_WAIT_CONSTANT} / 100663296)",
        )
        self.assertIn("subs\tr2, #1", start_section, "Delay loop must decrement loop counter with subs")
        self.assertIn("bne", start_section, "Delay loop must loop on bne")

        # 5. Verify DSB memory barriers
        self.assertIn("dsb\tsy", start_section, "Prologue must issue dsb sy after MMIO stores")

        # 6. Verify fall through to existing loader entry path
        self.assertIn("mov.w\tsp, #32768", start_section, "Prologue must set SP to 0x8000 (MEMBASEADDR)")
        self.assertIn("b.w", start_section, "Prologue must branch to my_restart")
        self.assertIn("<my_restart>", start_section, "Prologue must fall through and branch to my_restart")

    def test_binary_contains_t1_literals(self):
        """candidate_loader.bin must contain 32-bit little-endian representations of T1 constants."""
        led_loader_bin = CANDIDATE_LED_DIR / "candidate_loader.bin"
        if not led_loader_bin.is_file():
            cmd = ["python3", str(BUILD_SCRIPT), "--led"]
            res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(res.returncode, 0)

        with open(led_loader_bin, "rb") as f:
            data = f.read()

        # Check in the first 64 bytes (entry section)
        entry_bytes = data[:64]
        addr_le = struct.pack("<I", T1_LED_MMIO_ADDR)
        val0_le = struct.pack("<I", T1_ACTION_0_VALUE)
        val1_le = struct.pack("<I", T1_ACTION_1_VALUE)

        self.assertIn(addr_le, entry_bytes, "0xD20B0884 little-endian bytes missing in loader entry")
        self.assertIn(val0_le, entry_bytes, "0x004D0002 little-endian bytes missing in loader entry")
        self.assertIn(val1_le, entry_bytes, "0x004C0003 little-endian bytes missing in loader entry")

    def test_default_build_lacks_prologue(self):
        """Default candidate_loader.elf must NOT contain the prologue at 0x8000."""
        default_loader_elf = CANDIDATE_PORT2A_DIR / "candidate_loader.elf"
        proc = subprocess.run(
            [str(OBJDUMP), "-d", str(default_loader_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        disasm = proc.stdout

        # Entry should be directly mov.w sp, #32768 ; b.w <my_restart>
        start_section = disasm[
            disasm.find("00008000 <_start>:") : disasm.find("00008008 <compute_witness_checksum")
        ]
        self.assertIn("mov.w\tsp, #32768", start_section)
        self.assertIn("b.w", start_section)
        self.assertNotIn("mrs", start_section)
        self.assertNotIn("cpsid", start_section)
        self.assertNotIn("d20b0884", start_section.lower())

    def test_core_symbols_identical_across_builds(self):
        """Core symbols boot_witness and _end must be identical between default and LED builds."""
        default_core = CANDIDATE_PORT2A_DIR / "candidate_main.elf"
        led_core = CANDIDATE_LED_DIR / "candidate_main.elf"

        def get_symbols(elf_path):
            res = subprocess.run(
                [str(NM), "-n", str(elf_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            syms = {}
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2] in ("boot_witness", "_end", "_start"):
                    syms[parts[2]] = int(parts[0], 16)
            return syms

        def_syms = get_symbols(default_core)
        led_syms = get_symbols(led_core)

        self.assertEqual(def_syms["_start"], led_syms["_start"])
        self.assertEqual(def_syms["boot_witness"], led_syms["boot_witness"])
        self.assertEqual(def_syms["_end"], led_syms["_end"])
        self.assertEqual(led_syms["boot_witness"], EXPECTED_BOOT_WITNESS_ADDR)
        self.assertEqual(led_syms["_end"], EXPECTED_CORE_END_ADDR)


if __name__ == "__main__":
    unittest.main()
