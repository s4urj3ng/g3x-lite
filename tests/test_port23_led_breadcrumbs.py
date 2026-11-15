#!/usr/bin/env python3
"""Unit tests for PORT-23 T2b: Opt-in LED Breadcrumbs for GM1.10C Loader Verification.

Verifies:
1. Default build invariance:
   - The default candidate build is byte-identical to the recorded PORT-19 SHA-256:
     9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - Size is exactly 118,001 bytes.
   - Raw candidate_loader.bin matches recorded SHA-256:
     2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a.
   - Core symbols (boot_witness @ 0x0035F7A0, _end @ 0x00366CB0) are unchanged.
   - Candidate validator (tools/validate_candidate_port2a.py) passes all 7 checks in a tempdir.
2. Stage build coverage and expected hashes:
   - Each of the 6 stages (loader_entry, before_copy, after_copy, witness_entry,
     witness_write, pre_jump) builds cleanly via tools/build_candidate_port23_breadcrumb.py.
   - Exact DISKBOOT.BIN and candidate_loader.bin SHA-256 hashes match docs/PORT23_LED_BREADCRUMBS.md.
   - Candidate core binary (candidate_main.bin) is bit-for-bit identical to default.
3. Instruction-level verification (stage vs default diff):
   - Disassembles _start and my_restart from default and each stage build.
   - Strips the breadcrumb sequence (ldr addr / ldr val / str / dsb sy, literal pool entries, alignment nop).
   - Asserts remaining instructions are 100% equal to the default build.
4. Exactly one ON write at expected checkpoint:
   - For each non-off-next stage, asserts exactly one str of 0x004D0002 to 0xD20B0884.
   - Asserts exactly one literal pool entry for 0xD20B0884 in candidate_loader.elf.
   - Asserts write occurs at expected anchor in _start or my_restart.
5. Delay safety cap and loop enforcement:
   - Documented builds contain no new delay loops (loop count equals default build count).
   - A delay build contains a bounded loop with count <= 0x00600000.
   - Any delay loop > 0x00600000 is rejected fail-closed at CLI and compile time.
6. pre_jump checkpoint positioning:
   - The str of 0x004D0002 comes after cpsid if and is followed only by
     dsb sy, mov r0, ..., add... r0, r0, #1 and bx r0.
7. Loader drift and parity:
   - With no LED_BREADCRUMB* defines, arm-none-eabi-gcc -E output of
     loader_main_breadcrumb.c is identical to main_prototype.c.
8. LED register and values match verified hardware facts:
   - MMIO register 0xD20B0884, ON value 0x004D0002, OFF value 0x004C0003.
9. Scope integrity:
   - The default candidate remains byte-identical; PORT-46 permits shared-builder repairs.
   - chdk-port/platform/g3x/sub/110c/loader_entry_led.S is unchanged.
   - Rebuilding PORT-20 LED candidate produces the exact verified hash
     (757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286).
10. Header inertness:
   - chdk-port/platform/g3x/sub/110c/led_breadcrumb.h emits 0 symbols without LED_BREADCRUMB.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
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
        "diskboot_sha256": "b2a2d55e25cfd422895854d47f0d186874df9bb3450cfc46a5be045179466852",
        "diskboot_size": 118021,
        "loader_sha256": "1ce8051834a6a1a9e778ae1d7433e0db4cc7169e92c9a6f594ba4c3d4598115c",
        "loader_size": 118020,
    },
    "after_copy": {
        "diskboot_sha256": "0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df",
        "diskboot_size": 118021,
        "loader_sha256": "95e833aee0cd7a99cdb574315247efe69cb9c478a2c7333d3d9434f7af444ef4",
        "loader_size": 118020,
    },
    "witness_entry": {
        "diskboot_sha256": "0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df",
        "diskboot_size": 118021,
        "loader_sha256": "95e833aee0cd7a99cdb574315247efe69cb9c478a2c7333d3d9434f7af444ef4",
        "loader_size": 118020,
    },
    "witness_write": {
        "diskboot_sha256": "1fcad53e31f18c378b84918b65f9365e7400185423ad7dbeac62ac04555e3de8",
        "diskboot_size": 118021,
        "loader_sha256": "4a1de051f63822084d72b7bf300cf18bcb5e19ffc7345b0f57e773ffca550463",
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
    "diskboot_sha256": "2021a873fa934e1fd144e868bb961ac313b25bd2d790102bfb31223836c8c765",
    "diskboot_size": 118041,
    "loader_sha256": "95d5acfdf88294865a5feb564b1b7931e9577e83bfda20cc05c39ffa46b95c30",
    "loader_size": 118040,
}


def compute_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_func_instructions(elf_path: Path | str, func_name: str) -> list[str]:
    """Parse disassembly instructions for a given function into normalized opcode/operands."""
    dump = subprocess.check_output([str(OBJDUMP), "-d", str(elf_path)], text=True)
    in_func = False
    instructions = []
    for line in dump.splitlines():
        if f"<{func_name}>:" in line:
            in_func = True
            continue
        if in_func:
            if line.startswith("0000") and ">:" in line:
                break
            if not line.strip():
                continue
            m = re.match(r"^\s*[0-9a-f]+:\s+([0-9a-f ]+)\s+([a-z0-9\._]+)(.*)$", line)
            if m:
                hex_bytes, mnemonic, rest = m.groups()
                if ";" in rest:
                    rest, _ = rest.split(";", 1)
                operands = rest.strip()
                operands = re.sub(r"[0-9a-f]+ <([^>]+)>", r"<\1>", operands)
                operands = re.sub(r"\[pc,\s*#[0-9]+\]", "[pc]", operands)
                if func_name in operands:
                    operands = f"<{func_name}>"
                if mnemonic == ".word":
                    val = int(operands, 16) if operands.startswith("0x") else 0
                    if 0x8000 <= val <= 0x8fff:
                        operands = "<loader_internal_addr>"
                if mnemonic in ("b", "b.w", "b.n"):
                    mnemonic = "b"
                instructions.append(f"{mnemonic} {operands}".strip())
    return instructions


def filter_breadcrumb(instr_list: list[str]) -> list[str]:
    """Remove the breadcrumb sequence and literal-pool entries from an instruction list."""
    filtered = []
    i = 0
    while i < len(instr_list):
        ins = instr_list[i]
        # Breadcrumb sequence: ldr, ldr, str, dsb sy
        if (
            i + 3 < len(instr_list)
            and ins.startswith("ldr ")
            and "[pc]" in ins
            and instr_list[i + 1].startswith("ldr ")
            and "[pc]" in instr_list[i + 1]
            and instr_list[i + 2].startswith("str")
            and instr_list[i + 3] == "dsb sy"
        ):
            i += 4
            continue
        # Breadcrumb literal pool entries
        if ins in (".word 0xd20b0884", ".word 0x004d0002", ".word 0x004c0003"):
            i += 1
            continue
        # Compiler alignment nop before literal pool
        if ins == "nop" and i + 1 < len(instr_list) and instr_list[i + 1].startswith(".word"):
            i += 1
            continue
        filtered.append(ins)
        i += 1
    return filtered


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

            # Run validator checks non-destructively against tmpdir
            import validate_candidate_port2a as vcp

            orig_candidate_dir = vcp.CANDIDATE_DIR
            try:
                vcp.CANDIDATE_DIR = tmpdir
                self.assertTrue(vcp.validate_production_invariance())
                self.assertTrue(vcp.validate_candidate_core())
                self.assertTrue(
                    vcp.validate_candidate_loader(os.path.join(tmpdir, "candidate_main.bin"))
                )
                self.assertTrue(
                    vcp.validate_encoded_diskboot(os.path.join(tmpdir, "candidate_loader.bin"))
                )
                self.assertTrue(vcp.validate_memory_and_stack_disjointness())
                self.assertTrue(vcp.validate_inspector_association())
                self.assertTrue(vcp.validate_manifest_integrity())
            finally:
                vcp.CANDIDATE_DIR = orig_candidate_dir

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
        """Disassembly comparison against default build confirms only breadcrumb instructions differ."""
        with tempfile.TemporaryDirectory() as def_dir:
            subprocess.run(
                ["python3", str(BUILD_PORT2A), "--out-dir", def_dir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            def_start = filter_breadcrumb(
                parse_func_instructions(Path(def_dir) / "candidate_loader.elf", "_start")
            )
            def_restart = filter_breadcrumb(
                parse_func_instructions(Path(def_dir) / "candidate_loader.elf", "my_restart")
            )

        for stage in ("loader_entry", "before_copy", "after_copy", "witness_entry", "witness_write", "pre_jump"):
            with tempfile.TemporaryDirectory() as stg_dir:
                subprocess.run(
                    [
                        "python3",
                        str(BUILD_PORT23),
                        "--stage",
                        stage,
                        "--out-dir",
                        stg_dir,
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                )
                stg_start = filter_breadcrumb(
                    parse_func_instructions(Path(stg_dir) / "candidate_loader.elf", "_start")
                )
                stg_restart = filter_breadcrumb(
                    parse_func_instructions(Path(stg_dir) / "candidate_loader.elf", "my_restart")
                )

                self.assertEqual(
                    def_start,
                    stg_start,
                    f"Stage {stage} _start differs from default after removing breadcrumb",
                )
                self.assertEqual(
                    def_restart,
                    stg_restart,
                    f"Stage {stage} my_restart differs from default after removing breadcrumb",
                )

    def test_exactly_one_on_write(self):
        """For each non-off-next stage, assert exactly one str of 0x004D0002 to 0xD20B0884 at expected checkpoint."""
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
                    capture_output=True,
                )

                loader_elf = Path(tmpdir) / "candidate_loader.elf"
                dump = subprocess.check_output([str(OBJDUMP), "-d", str(loader_elf)], text=True)

                # Exactly one MMIO 0xD20B0884 literal in entire loader
                mmio_literals = re.findall(r"\.word\s+0xd20b0884", dump)
                self.assertEqual(
                    len(mmio_literals),
                    1,
                    f"Stage {stage} must have exactly one 0xD20B0884 literal in loader",
                )

                # Parse function line lists
                func_lines: dict[str, list[str]] = {}
                cur_func = None
                for line in dump.splitlines():
                    m_fn = re.match(r"^[0-9a-f]+ <([^>]+)>:", line)
                    if m_fn:
                        cur_func = m_fn.group(1)
                        func_lines[cur_func] = []
                    elif cur_func:
                        func_lines[cur_func].append(line)

                exp_func = "_start" if stage == "loader_entry" else "my_restart"
                self.assertIn(exp_func, func_lines)
                fn_lines = func_lines[exp_func]
                fn_text = "\n".join(fn_lines)

                # Check literals in expected function
                self.assertIn(".word\t0xd20b0884", fn_text)
                self.assertIn(".word\t0x004d0002", fn_text)

                # Count str instructions using MMIO register in this function
                str_sites = [l for l in fn_lines if re.search(r"str(\.w)?\s+r[0-3],\s*\[r[0-3]", l)]
                # Filter down to the breadcrumb str (storing to MMIO pointer)
                breadcrumb_strs = [
                    l for l in str_sites
                    if ("str\tr1, [r0]" in l or "str\tr1, [r0, #0]" in l
                        or "str\tr3, [r2]" in l or "str\tr3, [r2, #0]" in l)
                ]
                self.assertEqual(
                    len(breadcrumb_strs),
                    1,
                    f"Stage {stage} expected exactly one breadcrumb str in {exp_func}, found {breadcrumb_strs}",
                )

                # Anchor assertions
                if stage == "loader_entry":
                    idx_str = [i for i, l in enumerate(fn_lines) if l == breadcrumb_strs[0]][0]
                    idx_sp = [i for i, l in enumerate(fn_lines) if "sp" in l][0]
                    self.assertLess(idx_str, idx_sp, "loader_entry str must precede sp initialization")
                elif stage == "before_copy":
                    idx_str = [i for i, l in enumerate(fn_lines) if l == breadcrumb_strs[0]][0]
                    idx_compat = [i for i, l in enumerate(fn_lines) if "check_compat" in l][0]
                    idx_copy = [i for i, l in enumerate(fn_lines) if "core_copy" in l][0]
                    self.assertLess(idx_compat, idx_str, "before_copy str must follow check_compat")
                    self.assertLess(idx_str, idx_copy, "before_copy str must precede core_copy")
                elif stage in ("after_copy", "witness_entry"):
                    idx_str = [i for i, l in enumerate(fn_lines) if l == breadcrumb_strs[0]][0]
                    idx_copy = [i for i, l in enumerate(fn_lines) if "core_copy" in l][0]
                    idx_wit = [i for i, l in enumerate(fn_lines) if "compute_witness_checksum" in l][0]
                    self.assertLess(idx_copy, idx_str, f"{stage} str must follow core_copy")
                    self.assertLess(idx_str, idx_wit, f"{stage} str must precede witness store")
                elif stage == "witness_write":
                    idx_str = [i for i, l in enumerate(fn_lines) if l == breadcrumb_strs[0]][0]
                    idx_wit = [i for i, l in enumerate(fn_lines) if "compute_witness_checksum" in l][0]
                    idx_dccisw = [i for i, l in enumerate(fn_lines) if "blx\tr2" in l][0]
                    self.assertLess(idx_wit, idx_str, "witness_write str must follow witness checksum")
                    self.assertLess(idx_str, idx_dccisw, "witness_write str must precede cache maintenance")
                elif stage == "pre_jump":
                    idx_str = [i for i, l in enumerate(fn_lines) if l == breadcrumb_strs[0]][0]
                    idx_cpsid = [i for i, l in enumerate(fn_lines) if "cpsid" in l][0]
                    idx_bx = [i for i, l in enumerate(fn_lines) if "bx\tr0" in l][0]
                    self.assertLess(idx_cpsid, idx_str, "pre_jump str must follow cpsid if")
                    self.assertLess(idx_str, idx_bx, "pre_jump str must precede bx r0")

    def test_pre_jump_stage_position(self):
        """pre_jump checkpoint sits after cpsid if and is followed only by dsb sy, mov r0, add r0, #1, bx r0."""
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
                capture_output=True,
            )

            loader_elf = Path(tmpdir) / "candidate_loader.elf"
            dump = subprocess.check_output([str(OBJDUMP), "-d", str(loader_elf)], text=True)

            lines = dump.splitlines()
            cpsid_indices = [i for i, l in enumerate(lines) if "cpsid\tif" in l]
            bx_indices = [i for i, l in enumerate(lines) if "bx\tr0" in l]
            self.assertTrue(cpsid_indices, "cpsid if not found in pre_jump disassembly")
            self.assertTrue(bx_indices, "bx r0 not found in pre_jump disassembly")

            cpsid_idx = cpsid_indices[0]
            bx_idx = bx_indices[0]
            self.assertLess(cpsid_idx, bx_idx, "cpsid if must come before bx r0")

            between = [l.strip() for l in lines[cpsid_idx + 1 : bx_idx + 1]]
            # Extract mnemonics/instructions between cpsid if and bx r0
            inst_between = []
            for l in between:
                m = re.match(r"^[0-9a-f]+:\s+[0-9a-f ]+\s+([a-z0-9\._]+)(.*)$", l)
                if m:
                    mnem, args = m.groups()
                    args = re.sub(r";.*$", "", args).strip()
                    inst_between.append(f"{mnem} {args}".strip())

            # Expected exact sequence between cpsid if and bx r0:
            # ldr r0, [pc, ...]
            # ldr r1, [pc, ...]
            # str r1, [r0, #0] (or [r0])
            # dsb sy
            # mov r0, r5
            # add.w r0, r0, #1 (or add r0, r0, #1)
            # bx r0
            self.assertTrue(any("str" in x for x in inst_between), "str missing between cpsid and bx")
            str_pos = [i for i, x in enumerate(inst_between) if "str" in x][0]
            after_str = inst_between[str_pos + 1 :]

            self.assertEqual(len(after_str), 4, f"Unexpected instructions after str: {after_str}")
            self.assertEqual(after_str[0], "dsb sy")
            self.assertTrue(after_str[1].startswith("mov r0,"), f"Expected mov r0, got {after_str[1]}")
            self.assertTrue(after_str[2].startswith("add") and "r0, r0, #1" in after_str[2], f"Expected add r0, #1, got {after_str[2]}")
            self.assertEqual(after_str[3], "bx r0")

        # Negative test: assert default build does NOT have a str between cpsid if and bx r0
        with tempfile.TemporaryDirectory() as def_dir:
            subprocess.run(
                ["python3", str(BUILD_PORT2A), "--out-dir", def_dir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            def_dump = subprocess.check_output(
                [str(OBJDUMP), "-d", str(Path(def_dir) / "candidate_loader.elf")], text=True
            )
            def_lines = def_dump.splitlines()
            def_cpsid = [i for i, l in enumerate(def_lines) if "cpsid\tif" in l][0]
            def_bx = [i for i, l in enumerate(def_lines) if "bx\tr0" in l][0]
            def_between = def_lines[def_cpsid + 1 : def_bx]
            self.assertFalse(any("str" in l for l in def_between), "Default build must not have str before bx")

    def test_no_delay_loop_in_documented_builds(self):
        """Documented stage builds have no delay loop (subs/bne count equals default). Delay build <= 0x00600000."""
        with tempfile.TemporaryDirectory() as def_dir:
            subprocess.run(
                ["python3", str(BUILD_PORT2A), "--out-dir", def_dir],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            dump_def = subprocess.check_output(
                [str(OBJDUMP), "-d", str(Path(def_dir) / "candidate_loader.elf")], text=True
            )
            default_loop_count = len(re.findall(r"subs\s+[^,\n]+,\s*#1\s*\n\s*[0-9a-f]+:\s+[0-9a-f ]+\s+bne", dump_def))

        for stage in ("loader_entry", "before_copy", "after_copy", "witness_entry", "witness_write", "pre_jump"):
            with tempfile.TemporaryDirectory() as stg_dir:
                subprocess.run(
                    [
                        "python3",
                        str(BUILD_PORT23),
                        "--stage",
                        stage,
                        "--out-dir",
                        stg_dir,
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                )
                dump_stg = subprocess.check_output(
                    [str(OBJDUMP), "-d", str(Path(stg_dir) / "candidate_loader.elf")], text=True
                )
                stg_loop_count = len(re.findall(r"subs\s+[^,\n]+,\s*#1\s*\n\s*[0-9a-f]+:\s+[0-9a-f ]+\s+bne", dump_stg))
                self.assertEqual(
                    stg_loop_count,
                    default_loop_count,
                    f"Stage {stage} introduced unexpected busy-wait delay loops ({stg_loop_count} vs {default_loop_count})",
                )

        # Delay build test: verify non-documented stage build with LED_BREADCRUMB_DELAY=0x00100000 succeeds
        # and has delay count <= 0x00600000 in disassembly.
        test_delay = 0x00100000
        for test_stage in ("before_copy", "loader_entry"):
            with tempfile.TemporaryDirectory() as delay_dir:
                subprocess.run(
                    [
                        "python3",
                        str(BUILD_PORT23),
                        "--stage",
                        test_stage,
                        "--delay",
                        f"0x{test_delay:X}",
                        "--out-dir",
                        delay_dir,
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                )
                dump_delay = subprocess.check_output(
                    [str(OBJDUMP), "-d", str(Path(delay_dir) / "candidate_loader.elf")], text=True
                )
                delay_loops = len(re.findall(r"subs\s+[^,\n]+,\s*#1\s*\n\s*[0-9a-f]+:\s+[0-9a-f ]+\s+bne", dump_delay))
                self.assertEqual(
                    delay_loops,
                    default_loop_count + 1,
                    f"Delay build for {test_stage} must add exactly 1 delay loop",
                )

                # Check delay loop instruction
                lines = dump_delay.splitlines()
                subs_indices = [i for i, l in enumerate(lines) if "subs\tr2, #1" in l]
                self.assertTrue(subs_indices, f"Delay loop subs r2, #1 not found in {test_stage}")
                idx = subs_indices[0]
                # Immediately preceding instruction should load r2 (either mov.w r2, #... or ldr r2, [pc, ...])
                load_line = lines[idx - 1]
                match_val = re.search(r"#([0-9]+)", load_line)
                if match_val:
                    loaded_count = int(match_val.group(1))
                else:
                    match_hex = re.search(r"0x([0-9a-fA-F]+)", load_line)
                    loaded_count = int(match_hex.group(1), 16) if match_hex else 0
                self.assertEqual(loaded_count, test_delay)
                self.assertLessEqual(loaded_count, MAX_SAFETY_DELAY)

        # Compile-time rejection test: delay > 0x00600000 fails with #error
        hdr_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "led_breadcrumb.h"
        entry_s_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_entry_breadcrumb.S"

        # Check C header #error
        res_hdr = subprocess.run(
            [
                str(CC),
                "-c",
                "-nostdinc",
                "-DLED_BREADCRUMB=1",
                "-DLED_BREADCRUMB_DELAY=0x00600001",
                "-x",
                "c",
                str(hdr_path),
                "-o",
                "/dev/null",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_hdr.returncode, 0, "Delay > 0x00600000 must fail C compilation")
        self.assertIn("#error", res_hdr.stderr)
        self.assertIn("exceeds maximum safety cap of 0x00600000", res_hdr.stderr)

        # Check assembly entry #error
        res_asm = subprocess.run(
            [
                str(CC),
                "-c",
                "-nostdinc",
                "-DLED_BREADCRUMB=1",
                "-DLED_BREADCRUMB_LOADER_ENTRY=1",
                "-DLED_BREADCRUMB_DELAY=0x00600001",
                str(entry_s_path),
                "-o",
                "/dev/null",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_asm.returncode, 0, "Delay > 0x00600000 must fail assembly compilation")
        self.assertIn("#error", res_asm.stderr)
        self.assertIn("exceeds maximum safety cap of 0x00600000", res_asm.stderr)

        # CLI rejection test: delay > 0x00600000 rejected fail-closed
        with tempfile.TemporaryDirectory() as err_dir:
            res_bad = subprocess.run(
                [
                    "python3",
                    str(BUILD_PORT23),
                    "--stage",
                    "before_copy",
                    "--delay",
                    "0x00600001",
                    "--out-dir",
                    err_dir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_bad.returncode, 0, "Delay > 0x00600000 must fail closed at CLI")

    def test_builder_fails_when_loader_main_breadcrumb_missing(self):
        """tools/build_candidate_port23_breadcrumb.py raises FileNotFoundError when loader_main_breadcrumb.c is missing (fail closed, no fallback)."""
        import unittest.mock
        import build_candidate_port23_breadcrumb as bcb

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = "/nonexistent/test/path/loader_main_breadcrumb.c"
            with unittest.mock.patch.object(bcb, "BREADCRUMB_LOADER_C", nonexistent):
                with self.assertRaises(FileNotFoundError) as ctx:
                    bcb.build_breadcrumb_loader(
                        core_elf=str(BUILD_PORT2A),
                        core_bin=str(BUILD_PORT2A),
                        stage="before_copy",
                        candidate_dir=tmpdir,
                    )
                self.assertIn("loader_main_breadcrumb.c", str(ctx.exception))

    def test_loader_drift_and_parity(self):
        """With no LED_BREADCRUMB* defines, gcc -E output of loader_main_breadcrumb.c equals main_prototype.c."""
        proto_c = REPO_ROOT / "chdk-port" / "loader" / "g3x" / "main_prototype.c"
        bread_c = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "loader_main_breadcrumb.c"
        loader_dir = REPO_ROOT / "chdk-port" / "loader" / "g3x"

        self.assertTrue(proto_c.is_file(), f"Missing {proto_c}")
        self.assertTrue(bread_c.is_file(), f"Missing {bread_c}")

        cflags = [
            str(CC),
            "-E",
            "-march=armv7-r",
            "-mthumb",
            "-DTHUMB_FW",
            "-fno-inline",
            "-Os",
            "-fno-strict-aliasing",
            "-fno-schedule-insns2",
            "-I../../include",
            "-I../../core",
            "-I../../modules",
            "-I../../platform/g3x",
            "-DMAXRAMADDR=0x0fffffff",
            "-DROMBASEADDR=0xFC000000",
            "-DVER_CHDK",
            '-DHDK_VERSION="CHDK"',
            '-DBUILD_NUMBER="1.5.0"',
            '-DBUILD_SVNREV="0"',
            "-Wall",
            "-Wno-unused",
            "-Wno-format",
            "-DOPT_CURVES",
            "-DOPT_DEBUGGING",
            "-DOPT_PTP",
            "-DOPT_DISABLE_CAM_ERROR=0",
            "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
            "-mthumb-interwork",
            "-DLOW_LEVEL",
            '-DPLATFORM="g3x"',
            '-DPLATFORMSUB="110c"',
            "-DPLATFORMID=12968",
            "-DCAMERA_g3x=1",
            "-DCAM_DRYOS_REL=57",
            "-DMEMBASEADDR=0x8000",
            "-DMEMISOSTART=0x3489b4",
            "-I.",
            "-I../../platform/g3x/sub/110c",
            "-DBOOT_WITNESS_ADDR=0x0035f7a0",
            "-nostdinc",
        ]

        out_proto = subprocess.check_output(cflags + [str(proto_c)], cwd=str(loader_dir), text=True)
        out_bread = subprocess.check_output(cflags + [str(bread_c)], cwd=str(loader_dir), text=True)

        clean_proto = [l.strip() for l in out_proto.splitlines() if not l.startswith("#") and l.strip()]
        clean_bread = [l.strip() for l in out_bread.splitlines() if not l.startswith("#") and l.strip()]

        self.assertEqual(
            clean_proto,
            clean_bread,
            "loader_main_breadcrumb.c drifted from main_prototype.c when LED_BREADCRUMB is undefined",
        )

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

            ld = Path(tmpdir) / "candidate_loader.bin"
            self.assertEqual(ld.stat().st_size, EXPECTED_OFF_NEXT_MEASUREMENTS["loader_size"])
            self.assertEqual(
                compute_sha256(ld),
                EXPECTED_OFF_NEXT_MEASUREMENTS["loader_sha256"],
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
        clean_lines = [l for l in res.stdout.splitlines() if l and not l.startswith("#")]
        self.assertEqual(clean_lines, [], f"Header emitted unexpected tokens: {clean_lines}")

    def test_scope_integrity_no_port20_files_modified(self):
        """Verify no PORT-20-owned files have been modified."""
        from test_port21_ram_lifetime import find_forbidden_paths

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
        self.assertIn(EXPECTED_DEFAULT_LOADER_SHA256, content)

        # Expected stage hashes stated
        for stage, expected in DOCUMENTED_STAGE_MEASUREMENTS.items():
            self.assertIn(expected["diskboot_sha256"], content, f"Hash for {stage} missing from docs")


if __name__ == "__main__":
    unittest.main()
