#!/usr/bin/env python3
"""Unit test suite for PORT-1G.1 Canon Basic RAM Witness Inspector.

Includes tests for:
- Building witness inspector payload with dynamic symbol address resolution
- Fail-closed enforcement on missing candidate artifacts (Finding 2)
- Rejection of raw .bin mutation, mismatched ELF, and corrupted metadata (Finding 1)
- General test assertions dynamically derived from selected ELF without address pinning (Finding 3)
- Simulated symbol address change with linker output verification (Scope 5 & 6)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
import build_witness_inspector as bwi
import validate_witness_inspector as vwi

TOOLCHAIN_BIN = os.path.join(
    REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin"
)
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc")
NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
CANDIDATE_MAIN_ELF = os.path.join(REPO_ROOT, "candidate_port2a", "candidate_main.elf")


class TestG3XWitnessInspector(unittest.TestCase):
    """PORT-1G.1: Offline Validation of Canon Basic Witness Inspector Prototype."""

    def test_build_witness_inspector_payload(self):
        """Build witness inspector payload and verify assembly succeeds."""
        build_script = os.path.join(REPO_ROOT, "tools", "build_witness_inspector.py")
        res = subprocess.run([sys.executable, build_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"Build script failed:\n{res.stdout.decode()}\n{res.stderr.decode()}")
        out = res.stdout.decode()
        self.assertIn("Resolved boot_witness symbol address", out)
        self.assertIn("Successfully generated", out)
        self.assertIn("Generated address metadata", out)

    def test_validate_witness_inspector(self):
        """Run comprehensive witness inspector validator and verify all checks pass without address pinning."""
        expected_addr = bwi.extract_witness_addr_from_elf(CANDIDATE_MAIN_ELF)

        val_script = os.path.join(REPO_ROOT, "tools", "validate_witness_inspector.py")
        res = subprocess.run([sys.executable, val_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"Validator failed:\n{res.stdout.decode()}\n{res.stderr.decode()}")
        out = res.stdout.decode()
        self.assertIn("ALL CANON BASIC WITNESS INSPECTOR CHECKS PASSED", out)
        # Dynamically check the derived symbol address rather than hardcoded 0x0035F780
        self.assertIn(f"Witness target address 0x{expected_addr:08X} verified consistent with ELF & metadata", out)
        self.assertIn("Raw .bin MOVW/MOVT opcodes verified identical to object .text bit-for-bit", out)
        self.assertIn("Stage 1 classified as LOADER_REACHED / FRESHNESS_UNVERIFIED", out)
        self.assertIn("Stage 2 classified as CORE_REACHED / FRESHNESS_UNVERIFIED", out)
        self.assertIn("Matching-nonce stale replay strictly produces CONT_ATTEMPTED / FRESHNESS_UNVERIFIED", out)
        self.assertIn("Dynamic challenge mismatch classified as STALE_OR_FRESHNESS_UNKNOWN", out)
        self.assertIn("BOOT_SUCCESS and CONTINUATION_CONFIRMED strictly prohibited.", out)

    def test_dynamic_address_symbol_extraction(self):
        """Verify automatic extraction of boot_witness address derived from candidate_main.elf."""
        addr = bwi.extract_witness_addr_from_elf(CANDIDATE_MAIN_ELF)
        expected_addr = vwi.extract_witness_addr_from_elf(CANDIDATE_MAIN_ELF)
        self.assertEqual(addr, expected_addr)
        self.assertEqual(addr % 16, 0, "Witness address must be 16-byte aligned")

        # Missing symbol rejection
        with tempfile.TemporaryDirectory() as td:
            empty_c = os.path.join(td, "empty.c")
            with open(empty_c, "w") as f:
                f.write("void _start(void) {}\n")
            empty_elf = os.path.join(td, "empty.elf")
            subprocess.run([CC, "-nostdlib", empty_c, "-o", empty_elf], check=True)
            with self.assertRaises(ValueError):
                bwi.extract_witness_addr_from_elf(empty_elf)

    def test_fail_closed_on_missing_candidate_artifacts(self):
        """Verify fail-closed policy: missing candidate ELF or metadata raises FileNotFoundError (Finding 2)."""
        non_existent_elf = os.path.join(REPO_ROOT, "candidate_port2a", "does_not_exist.elf")
        with self.assertRaises(FileNotFoundError):
            bwi.build_witness_inspector(elf_path=non_existent_elf)

        non_existent_meta = os.path.join(REPO_ROOT, "firmware", "tools", "does_not_exist.json")
        with self.assertRaises(FileNotFoundError):
            vwi.validate_payload_binary(metadata_path=non_existent_meta, fail_closed=True)

    def test_rejection_of_raw_binary_mutation(self):
        """Reject mutation of only .bin bytes, verifying opcode decode & text-matching integrity (Finding 1)."""
        with tempfile.TemporaryDirectory() as td:
            mut_bin = os.path.join(td, "mutated_payload.bin")
            with open(vwi.PAYLOAD_BIN, "rb") as f:
                data = bytearray(f.read())

            # Mutate low-halfword of MOVW at offset 0x0A (flip immediate bits)
            data[0x0c] ^= 0x01
            with open(mut_bin, "w+b") as f:
                f.write(data)

            # 1. Direct raw opcode decoder must detect address change
            orig_addr = vwi.extract_witness_addr_from_binary_bytes(vwi.PAYLOAD_BIN)
            mut_addr = vwi.extract_witness_addr_from_binary_bytes(mut_bin)
            self.assertNotEqual(orig_addr, mut_addr)

            # 2. validate_payload_binary must fail on mutated binary vs .o
            with self.assertRaises((AssertionError, ValueError)):
                vwi.validate_payload_binary(
                    payload_bin=mut_bin,
                    payload_elf=vwi.PAYLOAD_ELF,
                    elf_path=CANDIDATE_MAIN_ELF,
                    metadata_path=vwi.METADATA_JSON,
                )

    def test_rejection_of_mismatched_elf(self):
        """Reject mismatched ELF where boot_witness address differs from inspector binary."""
        expected_addr = bwi.extract_witness_addr_from_elf(CANDIDATE_MAIN_ELF)
        with tempfile.TemporaryDirectory() as td:
            mock_c = os.path.join(td, "mock.c")
            with open(mock_c, "w") as f:
                f.write(
                    "void _start(void) {}\n"
                    "char pad[0x100] = {1};\n"
                    "__attribute__((aligned(16), section(\".data\"))) char boot_witness[32] = {0};\n"
                )
            mock_elf = os.path.join(td, "mock.elf")
            subprocess.run([CC, "-nostdlib", "-Wl,-Ttext,0x3489b4", mock_c, "-o", mock_elf], check=True)
            mock_addr = bwi.extract_witness_addr_from_elf(mock_elf)
            self.assertNotEqual(mock_addr, expected_addr)

            # Validating with mismatched ELF must fail assertion
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(elf_path=mock_elf)
            self.assertIn("Mismatched ELF symbol", str(ctx.exception))

    def test_rejection_of_mismatched_metadata(self):
        """Reject mismatched address metadata where address differs from inspector binary."""
        with tempfile.TemporaryDirectory() as td:
            bad_meta = os.path.join(td, "bad_metadata.json")
            with open(bad_meta, "w") as f:
                json.dump(
                    {
                        "target": "Canon PowerShot G3 X (GM1.10C)",
                        "symbol": "boot_witness",
                        "witness_address": "0x0035F990",
                        "witness_address_int": 0x0035F990,
                        "elf_file": "candidate_port2a/candidate_main.elf",
                        "payload_bin": "firmware/tools/witness_inspector_payload.bin",
                        "payload_size": 444,
                    },
                    f,
                )
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(metadata_path=bad_meta)
            self.assertIn("Mismatched address metadata", str(ctx.exception))

    def test_rejection_of_mismatched_binary(self):
        """Reject inspector binary that loads an address different from ELF/metadata."""
        with tempfile.TemporaryDirectory() as td:
            bad_s = os.path.join(td, "bad.S")
            with open(vwi.PAYLOAD_ELF.replace(".o", ".S")) as f:
                content = f.read()
            with open(bad_s, "w") as f:
                f.write(content)

            bad_o = os.path.join(td, "bad.o")
            bad_bin = os.path.join(td, "bad.bin")
            # Assemble with wrong address 0x00359990
            subprocess.run(
                [CC, "-mcpu=cortex-r4", "-mthumb", "-DBOOT_WITNESS_ADDR=0x00359990", "-c", bad_s, "-o", bad_o],
                check=True,
            )
            subprocess.run([bwi.OBJCOPY, "-O", "binary", bad_o, bad_bin], check=True)

            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=bad_bin,
                    payload_elf=bad_o,
                    elf_path=CANDIDATE_MAIN_ELF,
                )
            self.assertIn("Mismatched ELF symbol", str(ctx.exception))

    def test_simulated_symbol_address_change_and_linker_output(self):
        """Test with simulated symbol-address change and verify using linker output (Scope 5 & 6).
        
        Demonstrates that:
        1. Adding code within an aligned block does NOT necessarily move .data (Scope 6).
        2. Linker output must be verified to confirm actual symbol movement.
        3. Build system automatically resolves the shifted symbol address and compiles the inspector.
        4. Validator confirms matching address and rejects cross-mismatches.
        """
        current_canonical_addr = bwi.extract_witness_addr_from_elf(CANDIDATE_MAIN_ELF)

        with tempfile.TemporaryDirectory() as td:
            # Step 1: Demonstrate adding code does not necessarily move .data (due to section alignment)
            src_base = os.path.join(td, "base.c")
            with open(src_base, "w") as f:
                f.write(
                    "__attribute__((aligned(64))) void _start(void) { asm volatile(\"nop\"); }\n"
                    "__attribute__((aligned(16), section(\".data\"))) char boot_witness[32] = {1};\n"
                )
            elf_base = os.path.join(td, "base.elf")
            subprocess.run([CC, "-nostdlib", "-Wl,-Ttext,0x3489b4", src_base, "-o", elf_base], check=True)
            addr_base = bwi.extract_witness_addr_from_elf(elf_base)

            # Add 2 bytes of code (another nop)
            src_extra = os.path.join(td, "extra.c")
            with open(src_extra, "w") as f:
                f.write(
                    "__attribute__((aligned(64))) void _start(void) { asm volatile(\"nop; nop\"); }\n"
                    "__attribute__((aligned(16), section(\".data\"))) char boot_witness[32] = {1};\n"
                )
            elf_extra = os.path.join(td, "extra.elf")
            subprocess.run([CC, "-nostdlib", "-Wl,-Ttext,0x3489b4", src_extra, "-o", elf_extra], check=True)
            addr_extra = bwi.extract_witness_addr_from_elf(elf_extra)

            # Linker output verification: .data DID NOT move despite adding code
            self.assertEqual(
                addr_base,
                addr_extra,
                "Linker proof: adding code did not move .data because of section alignment",
            )

            # Step 2: Now induce an actual, verified symbol address change via data layout
            src_sim = os.path.join(td, "sim.c")
            with open(src_sim, "w") as f:
                f.write(
                    "void _start(void) {}\n"
                    "char shift_padding[0x140] = {1, 2, 3};\n"
                    "__attribute__((aligned(16), section(\".data\"))) char boot_witness[32] = {0};\n"
                )
            elf_sim = os.path.join(td, "sim_main.elf")
            subprocess.run([CC, "-nostdlib", "-Wl,-Ttext,0x3489b4", src_sim, "-o", elf_sim], check=True)

            # Verify actual movement via linker output
            sim_witness_addr = bwi.extract_witness_addr_from_elf(elf_sim)
            self.assertNotEqual(
                sim_witness_addr,
                current_canonical_addr,
                f"Simulated address 0x{sim_witness_addr:08X} must differ from canonical 0x{current_canonical_addr:08X}",
            )
            self.assertEqual(sim_witness_addr % 16, 0, "Address must maintain 16-byte alignment")

            # Step 3: Run build_witness_inspector with the simulated ELF in isolated test paths
            sim_o = os.path.join(td, "sim_witness_payload.o")
            sim_bin = os.path.join(td, "sim_witness_payload.bin")
            sim_meta = os.path.join(td, "sim_witness_metadata.json")
            sim_script = os.path.join(td, "sim_witness_inspector.m")

            # Copy Canon Basic script template
            with open(vwi.LOADER_SCRIPT, "r", encoding="utf-8") as f:
                with open(sim_script, "w", encoding="utf-8") as f_out:
                    f_out.write(f.read())

            built_addr, bin_sz, meta = bwi.build_witness_inspector(
                elf_path=elf_sim,
                payload_o=sim_o,
                payload_bin=sim_bin,
                loader_script=sim_script,
                metadata_json=sim_meta,
            )

            self.assertEqual(built_addr, sim_witness_addr)
            self.assertEqual(meta["witness_address"], f"0x{sim_witness_addr:08X}")
            self.assertEqual(meta["witness_address_int"], sim_witness_addr)

            # Step 4: Validate the newly generated inspector artifacts
            val_ok = vwi.validate_all(
                payload_bin=sim_bin,
                payload_elf=sim_o,
                loader_script=sim_script,
                metadata_json=sim_meta,
                elf_path=elf_sim,
                expected_witness_addr=sim_witness_addr,
            )
            self.assertTrue(val_ok, "Validation of dynamically rebuilt inspector must pass")

            # Step 5: Verify cross-mismatch rejection
            # New binary + Old candidate ELF -> REJECT
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=sim_bin,
                    payload_elf=sim_o,
                    elf_path=CANDIDATE_MAIN_ELF,
                    metadata_path=sim_meta,
                )
            self.assertIn("Mismatched ELF symbol", str(ctx.exception))

            # Old binary + New simulated ELF -> REJECT
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=vwi.PAYLOAD_BIN,
                    payload_elf=vwi.PAYLOAD_ELF,
                    elf_path=elf_sim,
                    metadata_path=vwi.METADATA_JSON,
                )
            self.assertIn("Mismatched ELF symbol", str(ctx.exception))

    def test_independent_freshness_semantics(self):
        """Verify that matching fixed constant nonce NEVER produces a success-like result."""
        good_fixed = vwi.pack_witness(
            vwi.BOOT_WITNESS_MAGIC,
            vwi.BOOT_WITNESS_VERSION,
            vwi.BOOT_WITNESS_FIXED_NONCE,
            7,
            0x7FF8,
            0x003489B5,
            100,
        )
        s, title, status, t_col, s_col = vwi.emulate_inspector_parse(
            good_fixed, expected_nonce=vwi.BOOT_WITNESS_FIXED_NONCE
        )
        self.assertEqual(s, vwi.SENTINEL_CONTINUATION)
        self.assertEqual(title, "CONT_ATTEMPTED")
        self.assertEqual(status, "FRESHNESS_UNVERIFIED")
        self.assertEqual(t_col, 4)  # Yellow
        self.assertEqual(s_col, 4)  # Yellow
        self.assertNotEqual(t_col, 2)  # Never green
        self.assertNotEqual(s_col, 2)  # Never green
        self.assertNotIn("SUCCESS", title)
        self.assertNotIn("SUCCESS", status)
        self.assertNotIn("CONFIRMED", title)
        self.assertNotIn("CONFIRMED", status)


if __name__ == "__main__":
    unittest.main()
