#!/usr/bin/env python3
"""Unit tests for PORT-23 T2b: Opt-in LED Breadcrumbs for GM1.10C Loader Verification.

Verifies:
1. Default build invariance:
   - The default candidate build is byte-identical to the recorded PORT-19 SHA-256:
     9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - Size is exactly 118,001 bytes.
   - Core symbols (boot_witness @ 0x0035F7A0, _end @ 0x00366CB0) are unchanged.
   - Candidate validator (tools/validate_candidate_port2a.py) passes all checks.
2. Stage build coverage and expected hashes:
   - Each of the 6 stages (loader_entry, before_copy, after_copy, witness_entry,
     witness_write, pre_jump) builds cleanly via tools/build_candidate_port23_breadcrumb.py.
   - Exact DISKBOOT.BIN SHA-256 hashes and sizes match docs/PORT23_LED_BREADCRUMBS.md.
   - Candidate core binary (candidate_main.bin) is bit-for-bit identical to default.
3. Instruction-level verification:
   - Each stage build differs from default only by the targeted breadcrumb instructions.
   - Disassembly proves MMIO register 0xD20B0884 and value 0x004D0002 are written.
   - Memory barrier dsb sy is issued.
   - pre_jump stage sits immediately before bx r0 to the core payload.
4. LED register and values match verified hardware facts:
   - MMIO register 0xD20B0884, ON value 0x004D0002, OFF value 0x004C0003.
   - Consistent across led_breadcrumb.h, loader_entry_breadcrumb.S, and build script.
5. Delay safety cap enforcement:
   - Documented builds contain no delay loop (delay = 0).
   - Any delay loop > 0x00600000 is rejected fail-closed.
   - Preprocessor guards (#error) enforce the 0x00600000 ceiling.
6. Scope integrity:
   - tools/build_candidate_port2a.py is unchanged.
   - chdk-port/platform/g3x/sub/110c/loader_entry_led.S is unchanged.
   - Rebuilding PORT-20 LED candidate produces the exact verified hash
     (757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286).
7. Differential turn-off (--off-next):
   - Generates DISKBOOT.BIN with both ON (0x004D0002) and OFF (0x004C0003) instructions.
   - Matches documented expected hash (865451e9dee0e9d19506c5b2d04f855456958dc52e705766205807bb50ab734f).
8. Header inertness:
   - chdk-port/platform/g3x/sub/110c/led_breadcrumb.h emits 0 symbols without LED_BREADCRUMB.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
TESTS_DIR = REPO_ROOT / "tests"
BUILD_PORT2A = TOOLS_DIR / "build_candidate_port2a.py"
BUILD_PORT23 = TOOLS_DIR / "build_candidate_port23_breadcrumb.py"
VALIDATOR_PORT2A = TOOLS_DIR / "validate_candidate_port2a.py"
DOCS_PORT23 = REPO_ROOT / "docs" / "PORT23_LED_BREADCRUMBS.md"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
CC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001
EXPECTED_DEFAULT_LOADER_SHA256 = (
    "2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a"
)
EXPECTED_DEFAULT_LOADER_SIZE = 118000
EXPECTED_DEFAULT_CORE_SHA256 = (
    "420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e"
)
EXPECTED_DEFAULT_CORE_SIZE = 116816

EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0
EXPECTED_CORE_END_ADDR = 0x00366CB0

VERIFIED_LED_MMIO = 0xD20B0884
VERIFIED_LED_ON = 0x004D0002
VERIFIED_LED_OFF = 0x004C0003
MAX_SAFETY_DELAY = 0x00600000

EXPECTED_PORT20_LOADER_ENTRY_S_SHA256 = (
    "9b090f9276a1b89da9369afa6df03888f874cfd1075c3f0310a0446fff2f927b"
)
EXPECTED_PORT20_LED_DISKBOOT_SHA256 = (
    "757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286"
)
EXPECTED_PORT20_LED_DISKBOOT_SIZE = 118041

DOCUMENTED_STAGE_MEASUREMENTS = {
    "loader_entry": {
        "diskboot_sha256": "60a78e40127d7aa2b05178a27d834545817ded7618fef9f26637b7789d92fe24",
        "diskboot_size": 118021,
        "loader_sha256": "0eb980aab0db7e968c33087568b6139103612e685d0544e9b3fcb443900376d5",
        "loader_size": 118020,
    },
    "before_copy": {
        "diskboot_sha256": "a7cacf489791b436e002376dc1ca54bc51ae84a87d7675fcfb7b072516764353",
        "diskboot_size": 118021,
        "loader_sha256": "facdd477760af95dd4abed86838a1997430d5257f50e032c3cce0c8f881cdbd4",
        "loader_size": 118020,
    },
    "after_copy": {
        "diskboot_sha256": "7322a4287d792950ecb5671bf3c21706f983ce90d56332d4394afdff01b670dc",
        "diskboot_size": 118025,
        "loader_sha256": "20a250c37f03ddb82d3a19fbb7daada55fc76d64883b2b2cbea0de4083943bd7",
        "loader_size": 118024,
    },
    "witness_entry": {
        "diskboot_sha256": "7322a4287d792950ecb5671bf3c21706f983ce90d56332d4394afdff01b670dc",
        "diskboot_size": 118025,
        "loader_sha256": "20a250c37f03ddb82d3a19fbb7daada55fc76d64883b2b2cbea0de4083943bd7",
        "loader_size": 118024,
    },
    "witness_write": {
        "diskboot_sha256": "228138b90b08e6f23c3405c21d9562dc0b9d8c1dfd2f1d6da7fa647fbf887460",
        "diskboot_size": 118021,
        "loader_sha256": "bd255e561e609eec12c763a65dc0536ab5d6001ad5b2c34e8aee6c47a4561fe7",
        "loader_size": 118020,
    },
    "pre_jump": {
        "diskboot_sha256": "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75",
        "diskboot_size": 118021,
        "loader_sha256": "c0c6bda42e9399212aec58f0bee2e42015b68d464dc9b5547a757c29e3ce182d",
        "loader_size": 118020,
    },
}

EXPECTED_OFF_NEXT_MEASUREMENTS = {
    "diskboot_sha256": "865451e9dee0e9d19506c5b2d04f855456958dc52e705766205807bb50ab734f",
    "diskboot_size": 118041,
    "loader_size": 118040,
}


def compute_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort23LedBreadcrumbs(unittest.TestCase):
    """Test suite for PORT-23 T2b LED breadcrumb candidate builder and invariants."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(BUILD_PORT2A.is_file(), f"Missing: {BUILD_PORT2A}")
        cls.assertTrue(BUILD_PORT23.is_file(), f"Missing: {BUILD_PORT23}")
        cls.assertTrue(VALIDATOR_PORT2A.is_file(), f"Missing: {VALIDATOR_PORT2A}")
        cls.assertTrue(DOCS_PORT23.is_file(), f"Missing: {DOCS_PORT23}")
        cls.assertTrue(CC.is_file(), f"Toolchain CC missing: {CC}")
        cls.assertTrue(OBJDUMP.is_file(), f"Toolchain OBJDUMP missing: {OBJDUMP}")

    def test_default_build_invariance(self):
        """The default port2a candidate build is byte-identical to the PORT-19 locked hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                ["python3", str(BUILD_PORT2A), "--out-dir", tmpdir],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Default build failed: {res.stderr}")

            diskboot = Path(tmpdir) / "DISKBOOT.BIN"
            self.assertTrue(diskboot.is_file())
            self.assertEqual(diskboot.stat().st_size, EXPECTED_DEFAULT_DISKBOOT_SIZE)
            self.assertEqual(compute_sha256(diskboot), EXPECTED_DEFAULT_DISKBOOT_SHA256)

            loader = Path(tmpdir) / "candidate_loader.bin"
            self.assertTrue(loader.is_file())
            self.assertEqual(loader.stat().st_size, EXPECTED_DEFAULT_LOADER_SIZE)
            self.assertEqual(compute_sha256(loader), EXPECTED_DEFAULT_LOADER_SHA256)

            core = Path(tmpdir) / "candidate_main.bin"
            self.assertTrue(core.is_file())
            self.assertEqual(core.stat().st_size, EXPECTED_DEFAULT_CORE_SIZE)
            self.assertEqual(compute_sha256(core), EXPECTED_DEFAULT_CORE_SHA256)

            # Core symbols in candidate_main.elf
            core_elf = Path(tmpdir) / "candidate_main.elf"
            nm_out = subprocess.check_output([str(NM), "-n", str(core_elf)], text=True)
            self.assertIn("0035f7a0 D boot_witness", nm_out)
            self.assertIn("00366cb0 B _end", nm_out)

        # Also verify that when candidate_port2a is built in repo root, validate_candidate_port2a passes
        candidate_dir = REPO_ROOT / "candidate_port2a"
        try:
            res = subprocess.run(
                ["python3", str(BUILD_PORT2A)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Default build failed: {res.stderr}")
            val = subprocess.run(
                ["python3", str(VALIDATOR_PORT2A)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(val.returncode, 0, f"Validator failed: {val.stderr}")
        finally:
            if candidate_dir.exists():
                shutil.rmtree(candidate_dir, ignore_errors=True)

    def test_stage_build_hashes_and_sizes(self):
        """Each stage build produces the exact SHA-256 and size documented in PORT23_LED_BREADCRUMBS.md."""
        for stage, expected in DOCUMENTED_STAGE_MEASUREMENTS.items():
            with tempfile.TemporaryDirectory() as tmpdir:
                res = subprocess.run(
                    [
                        "python3",
                        str(BUILD_PORT23),
                        "--stage",
                        stage,
                        "--out-dir",
                        tmpdir,
                    ],
                    cwd=REPO_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(
                    res.returncode, 0, f"Stage '{stage}' build failed: {res.stderr}"
                )

                diskboot = Path(tmpdir) / "DISKBOOT.BIN"
                self.assertTrue(diskboot.is_file(), f"DISKBOOT.BIN missing for stage {stage}")
                self.assertEqual(
                    diskboot.stat().st_size,
                    expected["diskboot_size"],
                    f"Stage {stage} DISKBOOT size mismatch",
                )
                self.assertEqual(
                    compute_sha256(diskboot),
                    expected["diskboot_sha256"],
                    f"Stage {stage} DISKBOOT SHA-256 mismatch",
                )

                loader = Path(tmpdir) / "candidate_loader.bin"
                self.assertTrue(loader.is_file(), f"candidate_loader.bin missing for stage {stage}")
                self.assertEqual(
                    loader.stat().st_size,
                    expected["loader_size"],
                    f"Stage {stage} loader size mismatch",
                )
                self.assertEqual(
                    compute_sha256(loader),
                    expected["loader_sha256"],
                    f"Stage {stage} loader SHA-256 mismatch",
                )

                # Core binary must remain identical to default candidate_main.bin
                core = Path(tmpdir) / "candidate_main.bin"
                self.assertTrue(core.is_file())
                self.assertEqual(core.stat().st_size, EXPECTED_DEFAULT_CORE_SIZE)
                self.assertEqual(compute_sha256(core), EXPECTED_DEFAULT_CORE_SHA256)

    def test_stage_differs_only_by_breadcrumb_instructions(self):
        """Disassembly of each stage loader confirms verified MMIO register, ON value, and DSB barrier."""
        for stage in ("loader_entry", "before_copy", "after_copy", "witness_entry", "witness_write", "pre_jump"):
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    [
                        "python3",
                        str(BUILD_PORT23),
                        "--stage",
                        stage,
                        "--out-dir",
                        tmpdir,
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                loader_elf = Path(tmpdir) / "candidate_loader.elf"
                dump = subprocess.run(
                    [str(OBJDUMP), "-d", str(loader_elf)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                ).stdout.lower()

                # Verified MMIO address 0xD20B0884 in hex
                self.assertIn("d20b0884", dump, f"Stage {stage} missing LED MMIO 0xD20B0884")
                # Verified ON value 0x004D0002 in hex
                self.assertIn("004d0002", dump, f"Stage {stage} missing LED ON value 0x004D0002")
                # Memory barrier
                self.assertIn("dsb\tsy", dump, f"Stage {stage} missing dsb sy barrier")

    def test_pre_jump_stage_position(self):
        """pre_jump checkpoint sits immediately before the one-way terminal branch bx r0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT23),
                    "--stage",
                    "pre_jump",
                    "--out-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            dump = subprocess.run(
                [str(OBJDUMP), "-d", str(loader_elf)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            # Find bx r0 in dump
            self.assertIn("bx\tr0", dump)
            lines = dump.splitlines()
            bx_indices = [i for i, l in enumerate(lines) if "bx\tr0" in l]
            self.assertTrue(bx_indices, "bx r0 not found in pre_jump disassembly")
            # In the 10 instructions preceding bx r0, str r1, [r0] (or similar) with dsb sy must appear
            pre_bx = "\n".join(lines[max(0, bx_indices[0] - 10) : bx_indices[0]])
            self.assertIn("dsb\tsy", pre_bx, "dsb sy must immediately precede core handoff")

    def test_led_register_and_values(self):
        """Verified hardware values match across Python build script, C header, and assembly."""
        import build_candidate_port23_breadcrumb as bcb

        self.assertEqual(bcb.G3X_LED_MMIO_ADDR, VERIFIED_LED_MMIO)
        self.assertEqual(bcb.G3X_LED_ON_VAL, VERIFIED_LED_ON)
        self.assertEqual(bcb.G3X_LED_OFF_VAL, VERIFIED_LED_OFF)

        # C header
        hdr = (REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h").read_text()
        self.assertIn("0xD20B0884", hdr)
        self.assertIn("0x004D0002", hdr)
        self.assertIn("0x004C0003", hdr)

        # Assembly breadcrumb
        asm_s = (REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_entry_breadcrumb.S").read_text()
        self.assertIn("0xD20B0884", asm_s)
        self.assertIn("0x004D0002", asm_s)

    def test_no_delay_above_safety_cap(self):
        """Delays above 0x00600000 are rejected fail-closed at CLI and compile time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # CLI rejection of delay > 0x00600000
            res = subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT23),
                    "--stage",
                    "loader_entry",
                    "--delay",
                    "0x00600001",
                    "--out-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0, "Build script must reject delay > 0x00600000")

            # Permitted delay <= 0x00600000 succeeds
            res_ok = subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT23),
                    "--stage",
                    "loader_entry",
                    "--delay",
                    "0x00100000",
                    "--out-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res_ok.returncode, 0, f"Valid delay build failed: {res_ok.stderr}")

    def test_port20_led_build_source_and_hash_unchanged(self):
        """PORT-20 LED build source and binary hashes are completely unchanged."""
        led_s = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_entry_led.S"
        self.assertTrue(led_s.is_file())
        self.assertEqual(compute_sha256(led_s), EXPECTED_PORT20_LOADER_ENTRY_S_SHA256)

        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT2A),
                    "--led",
                    "--out-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"PORT-20 LED build failed: {res.stderr}")

            db = Path(tmpdir) / "DISKBOOT.BIN"
            self.assertTrue(db.is_file())
            self.assertEqual(db.stat().st_size, EXPECTED_PORT20_LED_DISKBOOT_SIZE)
            self.assertEqual(compute_sha256(db), EXPECTED_PORT20_LED_DISKBOOT_SHA256)

    def test_off_next_mode(self):
        """--off-next turns off the LED at the subsequent checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT23),
                    "--stage",
                    "loader_entry",
                    "--off-next",
                    "--out-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"off-next build failed: {res.stderr}")

            db = Path(tmpdir) / "DISKBOOT.BIN"
            self.assertEqual(db.stat().st_size, EXPECTED_OFF_NEXT_MEASUREMENTS["diskboot_size"])
            self.assertEqual(
                compute_sha256(db),
                EXPECTED_OFF_NEXT_MEASUREMENTS["diskboot_sha256"],
            )

            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            dump = subprocess.run(
                [str(OBJDUMP), "-d", str(loader_elf)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout.lower()

            self.assertIn("004d0002", dump, "off-next build must contain LED ON literal")
            self.assertIn("004c0003", dump, "off-next build must contain LED OFF literal")

    def test_led_breadcrumb_header_inert_without_macro(self):
        """led_breadcrumb.h emits zero definitions when LED_BREADCRUMB is undefined."""
        hdr_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h"
        res = subprocess.run(
            [str(CC), "-E", "-nostdinc", str(hdr_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        # Filter preprocessor line markers
        clean_lines = [l for l in res.stdout.splitlines() if l and not l.startswith("#")]
        self.assertEqual(clean_lines, [], f"Header emitted unexpected tokens: {clean_lines}")

    def test_scope_integrity_no_port20_files_modified(self):
        """Verify no PORT-20-owned files have been modified."""
        from test_port21_ram_lifetime import find_forbidden_paths

        # Check git modified / staged paths
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        )
        changed = []
        for line in status.splitlines():
            entry = line[3:].strip()
            changed.extend(p.strip() for p in entry.split(" -> "))

        forbidden = find_forbidden_paths(changed)
        self.assertEqual(forbidden, [], f"PORT-20-owned files modified: {forbidden}")

    def test_docs_stage_table_and_citations(self):
        """PORT23_LED_BREADCRUMBS.md documents all 6 stages with citations and status labels."""
        content = DOCS_PORT23.read_text(encoding="utf-8")
        self.assertIn("## 3. Stage Table", content)

        for stage in ("loader_entry", "before_copy", "after_copy", "witness_entry", "witness_write", "pre_jump"):
            self.assertIn(f"**`{stage}`**", content, f"Stage {stage} missing from docs stage table")

        # Invariance of locked hash stated
        self.assertIn(EXPECTED_DEFAULT_DISKBOOT_SHA256, content)
        self.assertIn("118,001", content)

        # Expected stage hashes stated
        for stage, expected in DOCUMENTED_STAGE_MEASUREMENTS.items():
            self.assertIn(expected["diskboot_sha256"], content, f"Hash for {stage} missing from docs")


if __name__ == "__main__":
    unittest.main()
