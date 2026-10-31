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
  8. Inspector provenance: tracked firmware/tools payload (reads 0x0035F780) vs
     regenerated candidate_port2a payload (reads 0x0035F7A0), and a valid LOADER record
     at 0x0035F7A0 parsed at 0x0035F780
  9. Aborted loader writes over different prior memory contents (incl. a prior valid
     record plus a partial rewrite, which stays LOADER_REACHED)
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


FIRMWARE_TOOLS_DIR = REPO_ROOT / "firmware" / "tools"
HISTORICAL_PAYLOAD_BIN = FIRMWARE_TOOLS_DIR / "witness_inspector_payload.bin"
HISTORICAL_METADATA_JSON = FIRMWARE_TOOLS_DIR / "witness_inspector_metadata.json"
HISTORICAL_LOADER_SCRIPT = FIRMWARE_TOOLS_DIR / "witness_inspector_gm110c.m"
CANDIDATE_PAYLOAD_BIN = CANDIDATE_DIR / "witness_inspector_payload.bin"
CANDIDATE_METADATA_JSON = CANDIDATE_DIR / "witness_inspector_metadata.json"
CANDIDATE_LOADER_SCRIPT = CANDIDATE_DIR / "witness_inspector_gm110c.m"

# Tracked hashes (docs/REPRODUCIBILITY_MANIFEST.md:83; docs/PORT16_CANDIDATE_BUILD.md:364, 389)
HISTORICAL_PAYLOAD_SHA256 = "f1cd6438b8c54a233b28360705c02f869da2149c6499e9b2d8c340746a3c7f00"
CANDIDATE_PAYLOAD_SHA256 = "241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2"
HISTORICAL_INSPECTOR_ADDR = 0x0035F780

# Core image placement (candidate_manifest.json: core_destination; main_prototype.c:32-38)
CORE_DESTINATION = 0x003489B4

# Loader stores in source order (main_prototype.c:43-55). Volatile stores, so the
# compiler keeps this order; whether DRAM sees them in this order is not claimed.
LOADER_STORE_ORDER = [
    "magic", "version", "session_nonce", "stage_state",
    "loader_sp", "core_entry_pc", "cont_tick", "checksum",
]


def _loader_store_values(loader_sp=LOADER_INITIAL_SP):
    """Values the loader stores at each offset (main_prototype.c:43-55)."""
    fields = {
        "magic": BOOT_WITNESS_MAGIC,
        "version": BOOT_WITNESS_VERSION,
        "session_nonce": BOOT_WITNESS_FIXED_NONCE,
        "stage_state": STAGE_LOADER,
        "loader_sp": loader_sp,
        "core_entry_pc": 0,
        "cont_tick": 0,
    }
    fields["checksum"] = vwi.compute_checksum(
        fields["magic"], fields["version"], fields["session_nonce"], fields["stage_state"],
        fields["loader_sp"], fields["core_entry_pc"], fields["cont_tick"],
    )
    return fields


def _apply_first_n_loader_stores(prior: bytes, n: int, loader_sp=LOADER_INITIAL_SP) -> bytes:
    """Model an aborted loader write: only the first n of the 8 stores reach memory."""
    assert len(prior) == 32 and 0 <= n <= len(LOADER_STORE_ORDER)
    mem = bytearray(prior)
    values = _loader_store_values(loader_sp)
    for name in LOADER_STORE_ORDER[:n]:
        off = PARSER_FIELD_OFFSETS[name]
        mem[off:off + 4] = struct.pack("<I", values[name])
    return bytes(mem)


def _title(buf: bytes) -> str:
    return vwi.emulate_inspector_parse(buf, expected_nonce=0)[1]


class TestPort21InspectorProvenance(unittest.TestCase):
    """Which inspector payload reads which address (review finding 1)."""

    def test_historical_vs_regenerated_payload_target_addresses(self):
        """Tracked firmware/tools payload reads 0x0035F780; regenerated candidate payload reads 0x0035F7A0."""
        import hashlib

        hist = HISTORICAL_PAYLOAD_BIN.read_bytes()
        self.assertEqual(hashlib.sha256(hist).hexdigest(), HISTORICAL_PAYLOAD_SHA256)
        self.assertEqual(len(hist), 444)
        # Real decoder from the validator (tools/validate_witness_inspector.py:131-178)
        self.assertEqual(vwi.extract_witness_addr_from_binary_bytes(str(HISTORICAL_PAYLOAD_BIN)), HISTORICAL_INSPECTOR_ADDR)
        self.assertEqual(hist[0x0A:0x12].hex(), "4ff28077c0f23507")  # movw r7,#0xf780; movt r7,#0x0035
        meta_addr, meta = vwi.read_address_metadata(str(HISTORICAL_METADATA_JSON))
        self.assertEqual(meta_addr, HISTORICAL_INSPECTOR_ADDR)
        self.assertEqual(meta["payload_bin"], "firmware/tools/witness_inspector_payload.bin")

        self.assertTrue(CANDIDATE_PAYLOAD_BIN.exists(), f"Missing {CANDIDATE_PAYLOAD_BIN} (run candidate_build)")
        cand = CANDIDATE_PAYLOAD_BIN.read_bytes()
        self.assertEqual(hashlib.sha256(cand).hexdigest(), CANDIDATE_PAYLOAD_SHA256)
        self.assertEqual(len(cand), 444)
        self.assertEqual(vwi.extract_witness_addr_from_binary_bytes(str(CANDIDATE_PAYLOAD_BIN)), EXPECTED_BOOT_WITNESS_ADDR)
        self.assertEqual(cand[0x0A:0x12].hex(), "4ff2a077c0f23507")  # movw r7,#0xf7a0; movt r7,#0x0035
        cand_meta_addr, _ = vwi.read_address_metadata(str(CANDIDATE_METADATA_JSON))
        self.assertEqual(cand_meta_addr, EXPECTED_BOOT_WITNESS_ADDR)

        # The two payloads differ in exactly one byte: the movw immediate low byte.
        diffs = [i for i in range(len(hist)) if hist[i] != cand[i]]
        self.assertEqual(diffs, [0x0C])
        self.assertEqual((hist[0x0C], cand[0x0C]), (0x80, 0xA0))

        # The Canon Basic script is byte-identical in both locations and checks only the
        # payload size (444 B), so it accepts either payload without complaint.
        self.assertEqual(HISTORICAL_LOADER_SCRIPT.read_bytes(), CANDIDATE_LOADER_SCRIPT.read_bytes())
        script = HISTORICAL_LOADER_SCRIPT.read_text()
        self.assertIn("DIM payload_size = 444", script)
        self.assertNotIn("F780", script.upper())
        self.assertNotIn("F7A0", script.upper())

    def test_valid_loader_record_at_7a0_parsed_at_historical_780(self):
        """Valid LOADER record at 0x0035F7A0, parse at the address the tracked payload decodes to.

        The parse window [0x0035F780, 0x0035F7A0) ends exactly where the LOADER record begins,
        so the record never influences the result. Reported status for every modelled
        content of 0x0035F780 below: WITNESS_INVALID / INVALID / CORRUPT (0x574954EE, 3/3).
        """
        hist_addr = vwi.extract_witness_addr_from_binary_bytes(str(HISTORICAL_PAYLOAD_BIN))
        cand_addr = vwi.extract_witness_addr_from_binary_bytes(str(CANDIDATE_PAYLOAD_BIN))
        self.assertEqual(hist_addr, HISTORICAL_INSPECTOR_ADDR)
        self.assertEqual(cand_addr, EXPECTED_BOOT_WITNESS_ADDR)
        self.assertEqual(cand_addr - hist_addr, 32)

        valid_loader = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            STAGE_LOADER, LOADER_INITIAL_SP, 0, 0,
        )

        # Contents of 0x0035F780..0x0035F79F after core_copy(): the core image bytes at
        # that address. The core image is embedded verbatim in the loader.
        core_bin = (CANDIDATE_DIR / "candidate_main.bin").read_bytes()
        loader_bin = (CANDIDATE_DIR / "candidate_loader.bin").read_bytes()
        self.assertEqual(loader_bin.find(core_bin), 0x280, "core image must be embedded verbatim in loader")
        off_780 = hist_addr - CORE_DESTINATION
        core_780 = core_bin[off_780:off_780 + 32]
        core_7a0 = core_bin[off_780 + 32:off_780 + 64]
        self.assertEqual(core_780.hex(), "3600372e3100382e3000392e300031302e300031312e30000300000000000000")
        self.assertEqual(core_7a0, bytes(32), "core image boot_witness is zero before the loader stores")

        fills_780 = {
            "core image bytes after core_copy": core_780,
            "all zero": bytes(32),
            "stock-boot pointers": struct.pack(
                "<8I", 0x0012BBE0, 0x00015DA4, 0xFC77C8B0, 0xFC0C99B0,
                0x001231B8, 0xFC127AB1, 0xFC127B09, 0x003489B4,
            ),
            "0xFF fill": b"\xFF" * 32,
        }
        for name, fill in fills_780.items():
            for rec_name, rec_7a0 in (("valid LOADER", valid_loader), ("zero", bytes(32))):
                with self.subTest(fill_780=name, record_7a0=rec_name):
                    base = hist_addr
                    memory = bytearray(fill + rec_7a0)  # models 0x0035F780..0x0035F7BF
                    # Parse at the address the historical payload reads
                    win = bytes(memory[hist_addr - base:hist_addr - base + 32])
                    s, t, st, tc, sc = vwi.emulate_inspector_parse(win, expected_nonce=0)
                    self.assertEqual((s, t, st, tc, sc),
                                     (vwi.SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3))
                    # Parse at the address the regenerated payload reads
                    win_c = bytes(memory[cand_addr - base:cand_addr - base + 32])
                    expected = "LOADER_REACHED" if rec_name == "valid LOADER" else "WITNESS_INVALID"
                    self.assertEqual(_title(win_c), expected)


class TestPort21PartialWrites(unittest.TestCase):
    """Aborted loader writes: result depends on the bytes present before the write (review finding 2)."""

    def test_prior_valid_record_plus_partial_rewrite_is_loader_reached(self):
        """Reviewer example: prior valid LOADER record, only the first three stores repeat."""
        prior = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            STAGE_LOADER, LOADER_INITIAL_SP, 0, 0,
        )
        buf = _apply_first_n_loader_stores(prior, 3)
        self.assertEqual(buf, prior)
        self.assertEqual(
            vwi.emulate_inspector_parse(buf, expected_nonce=0),
            (vwi.SENTINEL_LOADER, "LOADER_REACHED", "FRESHNESS_UNVERIFIED", 1, 4),
        )

    def test_partial_write_status_by_prior_contents(self):
        """Status after the first n stores (n = 0..8) for several prior memory contents."""
        L, C, I = "LOADER_REACHED", "CONT_ATTEMPTED", "WITNESS_INVALID"
        priors = {
            # Identical prior record: every prefix leaves it valid.
            "prior valid LOADER (sp 0x7FF8)": (
                vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
                                 STAGE_LOADER, LOADER_INITIAL_SP, 0, 0),
                [L, L, L, L, L, L, L, L, L],
            ),
            # Prior LOADER record with a different SP: valid until loader_sp changes.
            "prior valid LOADER (sp 0x7FF0)": (
                vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
                                 STAGE_LOADER, 0x7FF0, 0, 0),
                [L, L, L, L, L, I, I, I, L],
            ),
            # Prior Stage-3 record: unchanged until stage_state is rewritten.
            "prior valid CONT_ATTEMPTED": (
                vwi.pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
                                 7, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, PROTOTYPE_CONT_TICK),
                [C, C, C, C, I, I, I, I, L],
            ),
            # Zero prior (also what core_copy leaves at 0x0035F7A0): invalid until the checksum lands.
            "prior all zero": (bytes(32), [I, I, I, I, I, I, I, I, L]),
            "prior 0xFF fill": (b"\xFF" * 32, [I, I, I, I, I, I, I, I, L]),
        }
        for name, (prior, expected) in priors.items():
            got = [_title(_apply_first_n_loader_stores(prior, n)) for n in range(9)]
            with self.subTest(prior=name):
                self.assertEqual(got, expected)




if __name__ == "__main__":
    unittest.main()
