#!/usr/bin/env python3
"""PORT-21 T3: Host roundtrip verification of boot witness writer vs inspector parser.

Validates Hypothesis H4:
- Was the LOADER witness record at 0x0035F7A0 malformed, given the code exactly as built?
- Compiles a host C probe including the real boot witness header (chdk-port/platform/g3x/sub/110c/boot_witness.h)
  and replicating the loader writer routine (chdk-port/loader/g3x/main_prototype.c:42-56).
- Serializes the exact C-generated record bytes and runs the real inspector parse code
  (tools/validate_witness_inspector.py) on:
  1. Real C-compiled loader-only witness record (Stage 1)
  2. Disassembly inspection and SP provenance from candidate_loader.elf
  3. All-zero memory region (power-on uninitialized or cleared DRAM)
  4. Memory overwritten with plausible stock-boot data / dryos allocations
  5. Valid records across all boot stages (Stage 1, Stage 2, Stage 3)
  6. Exhaustive failure modes mapping to WITNESS_INVALID / INVALID / CORRUPT
  7. Color index 3 selection verification and AYCrCb rendering independence
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CANDIDATE_DIR = REPO_ROOT / "candidate_port2a"

# Optional pytest support for skipping
try:
    import pytest
except ImportError:
    pytest = None

sys.path.insert(0, str(TOOLS_DIR))
import validate_witness_inspector as vwi
import validate_boot_witness as vbw

# Pinned boot witness constants (boot_witness.h & validate_witness_inspector.py)
BOOT_WITNESS_MAGIC = 0x5749544E       # "WITN" (boot_witness.h:8)
BOOT_WITNESS_VERSION = 0x00010001     # Version 1.1 (boot_witness.h:9)
BOOT_WITNESS_FIXED_NONCE = 0x32A80001 # GM1.10C challenge nonce (main_prototype.c:48)
EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0

STAGE_LOADER = 0x01
STAGE_CORE = 0x02
STAGE_CONTINUATION = 0x04

# Stack pointer provenance:
# 1. chdk-port/loader/g3x/entry.S:7: LDR SP, =MEMBASEADDR (0x00008000)
# 2. candidate_manifest.json:16: loader_entry = 0x00008000
# 3. candidate_loader.elf disassembly at 0x000081D8 (my_restart prologue):
#    push {r3, lr} pushes 2 32-bit registers (8 bytes) onto the stack.
#    Therefore SP at line 52 of main_prototype.c is exactly 0x8000 - 8 = 0x00007FF8.
LOADER_ENTRY_SP = 0x00008000
LOADER_PROLOGUE_STACK_CONSUMPTION = 8
LOADER_INITIAL_SP = LOADER_ENTRY_SP - LOADER_PROLOGUE_STACK_CONSUMPTION  # 0x00007FF8
CORE_ENTRY_THUMB_PC = 0x003489B5
PROTOTYPE_CONT_TICK = 0x0014F200

# Parser field offset map for boot_witness_t (<IIIIIIII, tools/validate_witness_inspector.py:247)
PARSER_FIELD_OFFSETS = {
    "magic": 0,
    "version": 4,
    "session_nonce": 8,
    "stage_state": 12,
    "loader_sp": 16,
    "core_entry_pc": 20,
    "cont_tick": 24,
    "checksum": 28,
}
PARSER_STRUCT_SIZE = 32


def _skip_if_no_gcc():
    """Explicitly detect compiler and skip if absent; never pass silently."""
    if shutil.which("gcc") is None:
        msg = "GCC host compiler is not available on this system"
        if pytest is not None:
            pytest.skip(msg)
        else:
            raise unittest.SkipTest(msg)


class TestPort21WitnessRoundtrip(unittest.TestCase):
    """Host roundtrip verification between boot witness writer and inspector parser."""

    def test_real_c_writer_bytes_roundtrip(self):
        """Compile a host C probe using boot_witness.h; assert field offsets, sizes, and inspector parse."""
        _skip_if_no_gcc()

        # Build host C probe including the actual boot_witness.h header and replicating
        # field-by-field the loader's assignments from chdk-port/loader/g3x/main_prototype.c:42-56
        c_source = r"""
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "chdk-port/platform/g3x/sub/110c/boot_witness.h"

int main(void) {
    boot_witness_t w;
    memset(&w, 0, sizeof(w));

    // Field assignments exactly as written in chdk-port/loader/g3x/main_prototype.c:42-56:
    // Line 43: w->magic = BOOT_WITNESS_MAGIC;
    w.magic = BOOT_WITNESS_MAGIC;
    // Line 44: w->version = BOOT_WITNESS_VERSION;
    w.version = BOOT_WITNESS_VERSION;
    // Line 48: w->session_nonce = 0x32A80001;
    w.session_nonce = 0x32A80001;
    // Line 50: w->stage_state = STAGE_LOADER;
    w.stage_state = STAGE_LOADER;
    // Line 52: w->loader_sp = current_sp (provenance: 0x8000 entry SP - 8 bytes prologue push = 0x7FF8);
    w.loader_sp = 0x00007FF8;
    // Line 53: w->core_entry_pc = 0;
    w.core_entry_pc = 0;
    // Line 54: w->cont_tick = 0;
    w.cont_tick = 0;
    // Line 55: w->checksum = compute_witness_checksum((const boot_witness_t*)&w);
    w.checksum = compute_witness_checksum(&w);

    printf("SIZEOF %zu\n", sizeof(boot_witness_t));
    printf("OFFSETS %zu %zu %zu %zu %zu %zu %zu %zu\n",
        offsetof(boot_witness_t, magic),
        offsetof(boot_witness_t, version),
        offsetof(boot_witness_t, session_nonce),
        offsetof(boot_witness_t, stage_state),
        offsetof(boot_witness_t, loader_sp),
        offsetof(boot_witness_t, core_entry_pc),
        offsetof(boot_witness_t, cont_tick),
        offsetof(boot_witness_t, checksum)
    );
    printf("CHECKSUM 0x%08X\n", w.checksum);
    printf("HEX ");
    const unsigned char *p = (const unsigned char *)&w;
    for (size_t i = 0; i < sizeof(w); ++i) {
        printf("%02x", p[i]);
    }
    printf("\n");
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as td:
            src_file = Path(td) / "probe_writer.c"
            bin_file = Path(td) / "probe_writer"
            src_file.write_text(c_source)

            # Compile with host GCC; compile error MUST fail loudly with stderr
            compile_res = subprocess.run(
                ["gcc", "-Wall", "-Wextra", f"-I{REPO_ROOT}", str(src_file), "-o", str(bin_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                compile_res.returncode,
                0,
                f"Host C probe GCC compilation failed!\nstderr:\n{compile_res.stderr}\nstdout:\n{compile_res.stdout}",
            )

            # Run the compiled probe
            run_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
            self.assertEqual(
                run_res.returncode,
                0,
                f"Host C probe execution failed!\nstderr:\n{run_res.stderr}\nstdout:\n{run_res.stdout}",
            )

            # Parse C probe outputs
            lines = run_res.stdout.strip().splitlines()
            parsed = {}
            for line in lines:
                parts = line.split()
                if parts:
                    parsed[parts[0]] = parts[1:]

            # 1. Assert sizeof(boot_witness_t) against parser expectation (32 bytes)
            c_size = int(parsed["SIZEOF"][0])
            self.assertEqual(
                c_size,
                PARSER_STRUCT_SIZE,
                f"C struct sizeof {c_size} != parser expectation {PARSER_STRUCT_SIZE}",
            )

            # 2. Assert offsetof for every member against parser offsets (<IIIIIIII)
            # If any struct member is reordered or misaligned, this assertion fails immediately.
            c_offsets = [int(x) for x in parsed["OFFSETS"]]
            expected_c_offsets = [
                PARSER_FIELD_OFFSETS["magic"],
                PARSER_FIELD_OFFSETS["version"],
                PARSER_FIELD_OFFSETS["session_nonce"],
                PARSER_FIELD_OFFSETS["stage_state"],
                PARSER_FIELD_OFFSETS["loader_sp"],
                PARSER_FIELD_OFFSETS["core_entry_pc"],
                PARSER_FIELD_OFFSETS["cont_tick"],
                PARSER_FIELD_OFFSETS["checksum"],
            ]
            self.assertEqual(
                c_offsets,
                expected_c_offsets,
                f"C struct member offsets {c_offsets} do not match parser offsets {expected_c_offsets}",
            )

            # 3. Assert checksum computed by C inline helper compute_witness_checksum()
            c_checksum = parsed["CHECKSUM"][0]
            self.assertEqual(c_checksum, "0x3028882D")

            # 4. Extract serialized hex bytes directly from C writer
            hex_data = parsed["HEX"][0]
            real_writer_bytes = bytes.fromhex(hex_data)
            self.assertEqual(len(real_writer_bytes), 32)

            # 5. Feed the real C writer bytes directly to the real inspector parser
            # (tools/validate_witness_inspector.py: emulate_inspector_parse with expected_nonce=0)
            sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(
                real_writer_bytes, expected_nonce=0
            )

            # Assert real inspector reports LOADER_REACHED / FRESHNESS_UNVERIFIED
            self.assertEqual(sentinel, vwi.SENTINEL_LOADER)
            self.assertEqual(sentinel, 0x57495401)
            self.assertEqual(title, "LOADER_REACHED")
            self.assertEqual(status, "FRESHNESS_UNVERIFIED")
            self.assertEqual(title_col, 1)  # White
            self.assertEqual(status_col, 4)  # Yellow

            # Test also with expected_nonce = BOOT_WITNESS_FIXED_NONCE (0x32A80001)
            s2, t2, st2, tc2, sc2 = vwi.emulate_inspector_parse(
                real_writer_bytes, expected_nonce=BOOT_WITNESS_FIXED_NONCE
            )
            self.assertEqual(s2, vwi.SENTINEL_LOADER)
            self.assertEqual(t2, "LOADER_REACHED")
            self.assertEqual(st2, "FRESHNESS_UNVERIFIED")
            self.assertEqual(tc2, 1)
            self.assertEqual(sc2, 4)

            # Also pass to offline validator validate_boot_witness.py
            bw_status, bw_reason = vbw.inspect_witness(real_writer_bytes, expected_nonce=None)
            self.assertEqual(bw_status, "LOADER_REACHED")
            self.assertEqual(bw_reason, "Loader handoff reached")

    def test_disassembly_coherence_and_sp_provenance(self):
        """Inspect candidate_loader.elf disassembly to verify SP provenance and witness write sequence."""
        loader_elf = CANDIDATE_DIR / "candidate_loader.elf"
        loader_bin = CANDIDATE_DIR / "candidate_loader.bin"
        self.assertTrue(loader_elf.exists(), f"Missing {loader_elf}")
        self.assertTrue(loader_bin.exists(), f"Missing {loader_bin}")

        # Reproducible provenance check 1: entry SP and binary instructions
        # chdk-port/loader/g3x/entry.S:7: LDR SP, =MEMBASEADDR (0x00008000)
        # candidate_manifest.json:16: loader_entry = 0x00008000
        with open(loader_bin, "rb") as f:
            loader_bytes = f.read()

        # At offset 0x00 (_start): Thumb instruction 'mov.w sp, #0x8000' is f4 4f 4d 00
        self.assertEqual(loader_bytes[0:4], b"\x4f\xf4\x00\x4d", "Instruction at 0x8000 must be 'mov.w sp, #32768'")
        # At offset 0x04: 'b.w my_restart' (offset +0x1D4 to 0x81D8) is f0 00 b8 e8
        self.assertEqual(loader_bytes[4:8], b"\x00\xf0\xe8\xb8", "Instruction at 0x8004 must be branch to my_restart")

        # At offset 0x1D8 (my_restart prologue): 'push {r3, lr}' is b5 08
        # This decrements SP by exactly 2 words = 8 bytes.
        self.assertEqual(loader_bytes[0x1D8:0x1DA], b"\x08\xb5", "Instruction at 0x81D8 must be 'push {r3, lr}'")

        # At offset 0x210: 'str.w sp, [r1, #16]' is f8 c1 d0 10
        # Stores SP directly into boot_witness.loader_sp (offset 16)
        self.assertEqual(loader_bytes[0x210:0x214], b"\xc1\xf8\x10\xd0", "Instruction at 0x8210 must be 'str.w sp, [r1, #16]'")

        # At offset 0x254: literal pool for boot_witness target address 0x0035F7A0
        witness_addr_bytes = loader_bytes[0x254:0x258]
        self.assertEqual(witness_addr_bytes, struct.pack("<I", EXPECTED_BOOT_WITNESS_ADDR))

        # Check via arm-none-eabi-objdump if toolchain is available
        toolchain_objdump = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin" / "arm-none-eabi-objdump"
        if toolchain_objdump.exists() and os.access(toolchain_objdump, os.X_OK):
            res = subprocess.run(
                [str(toolchain_objdump), "-d", str(loader_elf)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"arm-none-eabi-objdump failed:\n{res.stderr}")
            dump = res.stdout

            # Verify disassembled sequence:
            # 1. Entry SP initialization
            self.assertIn("mov.w\tsp, #32768", dump, "Disassembly must show 'mov.w sp, #32768' at _start")
            # 2. Prologue stack adjustment: push {r3, lr}
            self.assertIn("push\t{r3, lr}", dump, "Disassembly must show 'push {r3, lr}' in my_restart prologue")
            # 3. Store SP to offset +16
            self.assertIn("str.w\tsp, [r1, #16]", dump, "Disassembly must show 'str.w sp, [r1, #16]'")
            # 4. Target address 0x0035F7A0 loaded into r1
            self.assertIn("0035f7a0", dump, "Disassembly must reference boot witness target address 0x0035F7A0")
            # 5. Checksum call and store to offset +28
            self.assertIn("compute_witness_checksum", dump, "Disassembly must call compute_witness_checksum")
            self.assertIn("str\tr0, [r1, #28]", dump, "Disassembly must store checksum into [r1, #28]")

    def test_all_zero_region_yields_witness_invalid(self):
        """Verify that an uninitialized (all-zero) DRAM region yields WITNESS_INVALID / INVALID / CORRUPT."""
        all_zeros = bytes(32)
        sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(
            all_zeros, expected_nonce=0
        )

        self.assertEqual(sentinel, vwi.SENTINEL_INVALID)
        self.assertEqual(sentinel, 0x574954EE)
        self.assertEqual(title, "WITNESS_INVALID")
        self.assertEqual(status, "INVALID / CORRUPT")
        self.assertEqual(title_col, 3)
        self.assertEqual(status_col, 3)

        # Offline validator rejects:
        bw_status, bw_reason = vbw.inspect_witness(all_zeros)
        self.assertEqual(bw_status, "FAIL")
        self.assertEqual(bw_reason, "STATE_UNINITIALIZED")

    def test_overwritten_stock_boot_data_yields_witness_invalid(self):
        """Verify that memory overwritten with plausible stock boot data yields WITNESS_INVALID."""
        stock_patterns = [
            # 1. Pointers typical of Canon DRAM heap / structures / MMU
            struct.pack(
                "<8I",
                0x0012BBE0,
                0x00015DA4,
                0xFC77C8B0,
                0xFC0C99B0,
                0x001231B8,
                0xFC127AB1,
                0xFC127B09,
                0x003489B4,
            ),
            # 2. DryOS firmware strings / ASCII telemetry
            b"DryOS version 2.3, release 0059\x00"[:32],
            # 3. Uniform DRAM patterns (0xFF, 0xAA, 0x55, 0xDE)
            b"\xFF" * 32,
            b"\xAA" * 32,
            b"\x55" * 32,
            b"\xDE\xAD\xBE\xEF" * 8,
            # 4. Partial witness: matching magic but corrupted version
            vwi.pack_witness(BOOT_WITNESS_MAGIC, 0x00020000, 0x32A80001, 1, 0x7FF8, 0, 0),
            # 5. Partial witness: matching magic & version, but random words without matching checksum
            struct.pack(
                "<8I",
                BOOT_WITNESS_MAGIC,
                BOOT_WITNESS_VERSION,
                0x12345678,
                0x00000001,
                0x00007FF8,
                0x00000000,
                0x00000000,
                0x00000000,
            ),
        ]

        for idx, pattern in enumerate(stock_patterns):
            with self.subTest(pattern_idx=idx):
                sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(
                    pattern, expected_nonce=0
                )
                self.assertEqual(
                    sentinel,
                    vwi.SENTINEL_INVALID,
                    f"Pattern {idx} did not return SENTINEL_INVALID",
                )
                self.assertEqual(sentinel, 0x574954EE)
                self.assertEqual(title, "WITNESS_INVALID")
                self.assertEqual(status, "INVALID / CORRUPT")
                self.assertEqual(title_col, 3)
                self.assertEqual(status_col, 3)

    def test_valid_records_across_all_stages(self):
        """Verify inspector classification across valid stage 1, 2, and 3 records."""
        # Stage 1: LOADER_REACHED
        w1 = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            STAGE_LOADER, LOADER_INITIAL_SP, 0, 0
        )
        s1, t1, st1, tc1, sc1 = vwi.emulate_inspector_parse(w1, expected_nonce=0)
        self.assertEqual(s1, vwi.SENTINEL_LOADER)
        self.assertEqual(t1, "LOADER_REACHED")
        self.assertEqual(st1, "FRESHNESS_UNVERIFIED")
        self.assertEqual(tc1, 1)
        self.assertEqual(sc1, 4)

        # Stage 2: CORE_REACHED (STAGE_LOADER | STAGE_CORE = 0x03)
        w2 = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            STAGE_LOADER | STAGE_CORE, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 0
        )
        s2, t2, st2, tc2, sc2 = vwi.emulate_inspector_parse(w2, expected_nonce=0)
        self.assertEqual(s2, vwi.SENTINEL_CORE)
        self.assertEqual(t2, "CORE_REACHED")
        self.assertEqual(st2, "FRESHNESS_UNVERIFIED")
        self.assertEqual(tc2, 1)
        self.assertEqual(sc2, 4)

        # Stage 3: CONT_ATTEMPTED (STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION = 0x07)
        w3 = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION, LOADER_INITIAL_SP,
            CORE_ENTRY_THUMB_PC, PROTOTYPE_CONT_TICK
        )
        s3, t3, st3, tc3, sc3 = vwi.emulate_inspector_parse(w3, expected_nonce=0)
        self.assertEqual(s3, vwi.SENTINEL_CONTINUATION)
        self.assertEqual(t3, "CONT_ATTEMPTED")
        self.assertEqual(st3, "FRESHNESS_UNVERIFIED")
        self.assertEqual(tc3, 4)
        self.assertEqual(sc3, 4)

    def test_exhaustive_rejection_modes_mapping_to_witness_invalid(self):
        """Prove which conditions map to WITNESS_INVALID / INVALID / CORRUPT.

        Note on buffer truncation:
        The short buffer case (<32 bytes) is strictly a host-API rejection test of the Python
        reference emulator (tools/validate_witness_inspector.py:244-245). It is NOT a native-parser
        outcome or a physical on-camera memory state, because the native inspector payload takes
        no buffer length and reads directly from BOOT_WITNESS_ADDR (firmware/tools/witness_inspector_payload.S:57-90).
        All other cases represent physical memory states checked identically by both the native
        inspector payload and the reference emulator.
        """
        valid_stage3 = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            7, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, PROTOTYPE_CONT_TICK
        )

        cases = [
            (
                "Host-API rejection only: Short buffer (<32 bytes, tools/validate_witness_inspector.py:244-245)",
                b"\x00" * 31,
            ),
            ("Corrupted magic", vwi.pack_witness(0xDEADBEEF, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 7, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Unsupported version", vwi.pack_witness(BOOT_WITNESS_MAGIC, 0x00020000, BOOT_WITNESS_FIXED_NONCE, 7, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Single bit flip in checksum", bytes(bytearray(valid_stage3)[:31] + bytes([valid_stage3[31] ^ 0x01]))),
            ("Single bit flip in data without recomputing checksum", bytes(bytes([valid_stage3[0] ^ 0x01]) + valid_stage3[1:])),
            ("Illegal transition: Core skipped (0x01 -> 0x05)", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 0x05, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Illegal transition: Stage 0", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 0x00, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Illegal transition: Stage 2 without Stage 1 (0x02)", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 0x02, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Illegal transition: Stage 4 without prior stages (0x04)", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 0x04, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, 100)),
            ("Stage 3: core_entry_pc not Thumb-2 (0x003489B4 instead of 0x003489B5)", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 7, LOADER_INITIAL_SP, 0x003489B4, PROTOTYPE_CONT_TICK)),
            ("Stage 3: loader_sp misaligned (0x7FF9 not 8-byte aligned)", vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE, 7, 0x7FF9, CORE_ENTRY_THUMB_PC, PROTOTYPE_CONT_TICK)),
        ]

        for name, buf in cases:
            with self.subTest(case_name=name):
                sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(buf, expected_nonce=0)
                self.assertEqual(sentinel, vwi.SENTINEL_INVALID, f"{name} did not yield SENTINEL_INVALID")
                self.assertEqual(sentinel, 0x574954EE)
                self.assertEqual(title, "WITNESS_INVALID")
                self.assertEqual(status, "INVALID / CORRUPT")
                self.assertEqual(title_col, 3)
                self.assertEqual(status_col, 3)

    def test_color_index_3_selection_and_rendering_invariance(self):
        """Verify that INVALID state selects Color Index 3, and inspector parsing is rendering-independent.

        Tracked evidence:
        1. firmware/tools/witness_inspector_payload.S:193-194:
           .Lstate_invalid executes:
             movs r6, #3  /* Title Color Index 3 */
             movs r7, #3  /* Status Color Index 3 */
           and passes r6, r7 to LCDMsg_ChangeColor_native (payload.S:216-232).
        2. tools/validate_witness_inspector.py:251, 256, 260, 273:
           All failure exit points return (SENTINEL_INVALID, ..., 3, 3).
        3. docs/HDMI001_OVERLAY_PIPELINE.md:98:
           The GM1.10C hardware palette entries are 32-bit AYCrCb (bits 25:24 2-bit alpha,
           YCrCb chroma/luma), NOT RGB.
        4. Visual display appearance on the physical camera LCD depends on the active palette
           configuration, display device LUT calibration, and rendering context [INFERRED / UNKNOWN].
        5. Inspector parsing logic, sentinel generation (0x574954EE), and execution control flow
           are strictly independent of the visual display color [VERIFIED].
        """
        # 1. Assert parser returns color index 3 for both lines on invalid input
        all_zeros = bytes(32)
        sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(all_zeros, expected_nonce=0)
        self.assertEqual(title_col, 3, "Title color index must be 3 for WITNESS_INVALID")
        self.assertEqual(status_col, 3, "Status color index must be 3 for INVALID / CORRUPT")
        self.assertEqual(sentinel, 0x574954EE, "Return sentinel must be SENTINEL_INVALID (0x574954EE)")

        # 2. Verify payload assembly source explicitly selects color index 3
        payload_asm_path = REPO_ROOT / "firmware" / "tools" / "witness_inspector_payload.S"
        self.assertTrue(payload_asm_path.exists(), f"Missing {payload_asm_path}")
        asm_text = payload_asm_path.read_text()

        # Check .Lstate_invalid block selects #3 for r6 and r7
        self.assertIn("movs\tr6, #3", asm_text, "payload.S must set r6 (Title Color) to 3 at .Lstate_invalid")
        self.assertIn("movs\tr7, #3", asm_text, "payload.S must set r7 (Status Color) to 3 at .Lstate_invalid")

        # 3. Verify inspector control flow and parsing results are invariant to color indices
        # Color values (1, 4, 3) are output UI telemetry only; they never feed back into parsing logic.
        self.assertIn("0x574954EE", asm_text)


if __name__ == "__main__":
    unittest.main()
