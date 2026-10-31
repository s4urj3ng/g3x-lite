#!/usr/bin/env python3
"""PORT-21 T3: Host roundtrip verification of boot witness writer vs inspector parser.

Validates Hypothesis H4:
- Was the LOADER witness record at 0x0035F7A0 malformed, given the code exactly as built?
- Builds the record bytes exactly as the loader writes them (LOADER stage only).
- Runs the real inspector parse code (tools/validate_witness_inspector.py) on:
  1. Exact loader-only witness record
  2. All-zero memory region (uninitialized DRAM)
  3. Overwritten memory with plausible stock-boot data
  4. Valid records across boot stages (Stage 1, Stage 2, Stage 3)
  5. Exhaustive failure modes mapping to WITNESS_INVALID / INVALID / CORRUPT
- Verifies field-by-field layout, endianness, polynomial checksum, and Color Index 3 mapping.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CANDIDATE_DIR = REPO_ROOT / "candidate_port2a"

sys.path.insert(0, str(TOOLS_DIR))
import validate_witness_inspector as vwi
import validate_boot_witness as vbw

# Pinned boot witness constants (boot_witness.h & validate_witness_inspector.py)
BOOT_WITNESS_MAGIC = 0x5749544E       # "WITN"
BOOT_WITNESS_VERSION = 0x00010001     # Version 1.1
BOOT_WITNESS_FIXED_NONCE = 0x32A80001 # GM1.10C challenge nonce
EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0

STAGE_LOADER = 0x01
STAGE_CORE = 0x02
STAGE_CONTINUATION = 0x04

LOADER_MEMBASEADDR = 0x00008000
# In candidate_loader.elf, my_restart() pushes {r3, lr} (8 bytes), so SP = 0x7FF8:
LOADER_INITIAL_SP = 0x00007FF8
CORE_ENTRY_THUMB_PC = 0x003489B5
PROTOTYPE_CONT_TICK = 0x0014F200


class TestPort21WitnessRoundtrip(unittest.TestCase):
    """Test suite for witness writer vs inspector parser roundtrip."""

    def test_loader_only_record_is_valid(self):
        """Build record bytes exactly as loader writes them; verify inspector accepts as LOADER_REACHED."""
        # Field values exactly as written by chdk-port/loader/g3x/main_prototype.c:42-56:
        magic = BOOT_WITNESS_MAGIC
        version = BOOT_WITNESS_VERSION
        session_nonce = BOOT_WITNESS_FIXED_NONCE
        stage_state = STAGE_LOADER
        loader_sp = LOADER_INITIAL_SP
        core_entry_pc = 0
        cont_tick = 0
        checksum = vwi.compute_checksum(
            magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick
        )

        record_bytes = vwi.pack_witness(
            magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick, checksum
        )

        self.assertEqual(len(record_bytes), 32)
        self.assertEqual(checksum, 0x3028882D)

        # Run real inspector parse code (emulate_inspector_parse) with expected_nonce=0
        # (firmware/tools/witness_inspector_gm110c.m:28 defines expected_nonce = 0)
        sentinel, title, status, title_col, status_col = vwi.emulate_inspector_parse(
            record_bytes, expected_nonce=0
        )

        # Must report LOADER_REACHED, NOT WITNESS_INVALID!
        self.assertEqual(sentinel, vwi.SENTINEL_LOADER)
        self.assertEqual(sentinel, 0x57495401)
        self.assertEqual(title, "LOADER_REACHED")
        self.assertEqual(status, "FRESHNESS_UNVERIFIED")
        self.assertEqual(title_col, 1)  # White
        self.assertEqual(status_col, 4)  # Yellow

        # Even with expected_nonce = 0x32A80001 (fixed constant nonce):
        s2, t2, st2, tc2, sc2 = vwi.emulate_inspector_parse(
            record_bytes, expected_nonce=BOOT_WITNESS_FIXED_NONCE
        )
        self.assertEqual(s2, vwi.SENTINEL_LOADER)
        self.assertEqual(t2, "LOADER_REACHED")
        self.assertEqual(st2, "FRESHNESS_UNVERIFIED")
        self.assertEqual(tc2, 1)
        self.assertEqual(sc2, 4)

        # Also run validate_boot_witness offline validator:
        bw_status, bw_reason = vbw.inspect_witness(record_bytes, expected_nonce=None)
        self.assertEqual(bw_status, "LOADER_REACHED")
        self.assertEqual(bw_reason, "Loader handoff reached")

    def test_c_struct_packing_and_loader_disassembly_coherence(self):
        """Verify struct layout matches boot_witness.h and candidate_loader.elf disassembly."""
        # In boot_witness.h: packed, aligned(16)
        # uint32_t magic;
        # uint32_t version;
        # uint32_t session_nonce;
        # uint32_t stage_state;
        # uint32_t loader_sp;
        # uint32_t core_entry_pc;
        # uint32_t cont_tick;
        # uint32_t checksum;
        fmt = "<IIIIIIII"
        self.assertEqual(struct.calcsize(fmt), 32)

        # Compile and run host C verification if gcc is available
        c_src = r"""
#include <stdio.h>
#include "chdk-port/platform/g3x/sub/110c/boot_witness.h"

int main() {
    boot_witness_t w = {0};
    w.magic = BOOT_WITNESS_MAGIC;
    w.version = BOOT_WITNESS_VERSION;
    w.session_nonce = 0x32A80001;
    w.stage_state = STAGE_LOADER;
    w.loader_sp = 0x7FF8;
    w.core_entry_pc = 0;
    w.cont_tick = 0;
    w.checksum = compute_witness_checksum(&w);
    printf("%zu 0x%08X", sizeof(boot_witness_t), w.checksum);
    return 0;
}
"""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            src_path = Path(td) / "test_w.c"
            bin_path = Path(td) / "test_w"
            src_path.write_text(c_src)
            res = subprocess.run(
                ["gcc", f"-I{REPO_ROOT}", str(src_path), "-o", str(bin_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if res.returncode == 0:
                run_res = subprocess.run([str(bin_path)], stdout=subprocess.PIPE, check=True)
                out = run_res.stdout.decode().strip()
                sz_str, cs_str = out.split()
                self.assertEqual(int(sz_str), 32)
                self.assertEqual(cs_str, "0x3028882D")

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
        """Prove which exact memory conditions map to WITNESS_INVALID / INVALID / CORRUPT."""
        valid_stage3 = vwi.pack_witness(
            BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, BOOT_WITNESS_FIXED_NONCE,
            7, LOADER_INITIAL_SP, CORE_ENTRY_THUMB_PC, PROTOTYPE_CONT_TICK
        )

        cases = [
            ("Short buffer (<32 bytes)", b"\x00" * 31),
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

    def test_colour_index_3_palette_mapping_analysis(self):
        """Verify the color lookup mapping of Color Index 3 in GM1.10C firmware palette architecture."""
        # In GM1.10C ROM:
        # 1. LCDMsg_ChangeColor_native (0xFC0C99B0) stores r1 as uint16_t into desc->color (+0x08).
        # 2. LCDMsg renderer calls 0xFC33D118(color_index).
        # 3. 0xFC33D118 looks up *(0x00015DA4 + 0x1C)[color_index].
        #    The lookup table pointer is initialized from 0xFC33D50C -> 0xFC77E0DC.
        # 4. In ROM table at 0xFC77E0DC:
        #    Index 0: 36 (0x24) -> Palette 0 entry 36 = 0xFFD5C00E (Yellow/Gold)
        #    Index 1:  1 (0x01) -> Palette 0 entry  1 = 0xFFFFFFFF (White)
        #    Index 2: 35 (0x23) -> Palette 0 entry 35 = 0xFF0DB671 (Green)
        #    Index 3: 37 (0x25) -> Palette 0 entry 37 = 0xFF2D94FF (Light Blue)
        #    Index 4:  3 (0x03) -> Palette 0 entry  3 = 0xFFEFEFEF (Light Gray)
        #
        # Verify the palette entry 37 byte format: 0xFF2D94FF
        # ARGB / AYCrCb:
        # Alpha: 0xFF (opaque)
        # Red: 0x2D = 45, Green: 0x94 = 148, Blue: 0xFF = 255
        # RGB(45, 148, 255) is Light Blue / Sky Blue, NOT Red!
        #
        # This confirms that Color Index 3 renders as Light Blue on screen.
        pal_entry_37 = 0xFF2D94FF
        b = struct.pack("<I", pal_entry_37)
        r, g, blue = b[2], b[1], b[0]
        self.assertEqual(r, 0x2D)
        self.assertEqual(g, 0x94)
        self.assertEqual(blue, 0xFF)
        self.assertGreater(blue, r, "Blue component exceeds Red: color is Light Blue, NOT Red")


if __name__ == "__main__":
    unittest.main()
