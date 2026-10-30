#!/usr/bin/env python3
"""Unit tests for tools/port17_trace_parser.py.

Platform: Canon PowerShot G3 X (GM1.10C / Platform ID 0x32A8 = 12968 decimal)
Safety Scope: Phase 0 host static analysis / offline tools (docs/SAFETY.md)

Acceptance Criteria & Feedback Verified:
1. tools/port17_trace_parser.py uses only the Python standard library.
2. Exact record layout matches the trace core header (cited by file:line).
3. Locates and parses magic/version header; unknown versions and bad magic yield
   a clear non-zero error and specific exceptions.
4. Bounded ring buffer extent: ignores suffix and prefix junk bytes; wraps/unwinds
   chronologically based on write_idx and capacity.
5. Handles unwrapped ring with suffix junk and returns only the valid records.
6. Validates v1 layout fields (record_size, capacity, write_idx) against constants in
   g3x_trace.h:22-43; malformed headers raise MalformedHeaderError cleanly without large loops.
7. Handles truncated records, truncated wrapped rings, and size-capped logs without crashing.
8. JSON output is the default; human-readable table output is available.
9. Synthetic fixtures generated inside tests: no committed binary fixtures or ROM bytes.
10. All file-based tests use tempfile / TemporaryDirectory and never write into the repo.
"""

from __future__ import annotations

import ast
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from tools.port17_trace_parser import (
    BadMagicError,
    G3X_STAGE_ASSERT,
    G3X_STAGE_DISPLAY,
    G3X_STAGE_ENTRY,
    G3X_STAGE_FLUSH,
    G3X_STAGE_KBD,
    G3X_STAGE_NONE,
    G3X_STAGE_RELOC,
    G3X_STAGE_TASK_HOOK,
    G3X_TRACE_CAPACITY,
    G3X_TRACE_HEADER_SIZE,
    G3X_TRACE_LOG_MAX_RECORDS,
    G3X_TRACE_LOG_MAX_SIZE,
    G3X_TRACE_MAGIC,
    G3X_TRACE_MAGIC_BYTES,
    G3X_TRACE_RECORD_SIZE,
    G3X_TRACE_RECORD_TEXT_LEN,
    G3X_TRACE_RING_SIZE,
    G3X_TRACE_VERSION,
    MalformedHeaderError,
    STAGE_NAMES,
    TraceHeader,
    TraceParseResult,
    TraceParserError,
    TraceRecord,
    TruncatedDataError,
    UnknownVersionError,
    decode_record,
    locate_header,
    pack_header,
    pack_record,
    parse_header,
    parse_trace,
    stage_id_to_name,
)

PARSER_SCRIPT = os.path.join(REPO_ROOT, "tools", "port17_trace_parser.py")
TRACE_H_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "g3x_trace.h")


class TestPort17TraceParser(unittest.TestCase):
    """Test suite for PORT-17 trace parser using synthetic fixtures."""

    # -------------------------------------------------------------------------
    # 1. Standard Library & Specification Conformance
    # -------------------------------------------------------------------------
    def test_standard_library_only(self):
        """tools/port17_trace_parser.py must import only standard library modules."""
        with open(PARSER_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code, filename=PARSER_SCRIPT)
        imported_modules: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and not node.level:
                    imported_modules.add(node.module.split(".")[0])

        stdlib_names = sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else {
            "argparse", "dataclasses", "json", "os", "struct", "sys", "typing", "__future__", "ast"
        }

        for mod in imported_modules:
            self.assertIn(
                mod,
                stdlib_names,
                f"Forbidden third-party module imported in port17_trace_parser.py: {mod}",
            )

    def test_docstring_cites_trace_core_header(self):
        """Module docstring must cite g3x_trace.h by file:line."""
        with open(PARSER_SCRIPT, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("chdk-port/platform/g3x/sub/110c/g3x_trace.h:16-44", content)
        self.assertIn("chdk-port/platform/g3x/sub/110c/g3x_trace.h:22-43", content)
        self.assertIn("chdk-port/platform/g3x/sub/110c/g3x_trace.h:53-73", content)
        self.assertIn("chdk-port/platform/g3x/sub/110c/g3x_trace.h:141-165", content)

    def test_constants_match_c_header(self):
        """Constants in port17_trace_parser.py must exactly match g3x_trace.h."""
        with open(TRACE_H_PATH, "r", encoding="utf-8") as f:
            h_text = f.read()

        self.assertIn("#define G3X_TRACE_MAGIC             0x43415254U", h_text)
        self.assertEqual(G3X_TRACE_MAGIC, 0x43415254)
        self.assertEqual(G3X_TRACE_MAGIC_BYTES, b"TRAC")
        self.assertEqual(struct.pack("<I", G3X_TRACE_MAGIC), b"TRAC")

        self.assertIn("#define G3X_TRACE_VERSION           0x00010000U", h_text)
        self.assertEqual(G3X_TRACE_VERSION, 0x00010000)

        self.assertEqual(G3X_TRACE_RECORD_TEXT_LEN, 20)
        self.assertEqual(G3X_TRACE_CAPACITY, 64)
        self.assertEqual(G3X_TRACE_RECORD_SIZE, 32)
        self.assertEqual(G3X_TRACE_HEADER_SIZE, 32)
        self.assertEqual(G3X_TRACE_RING_SIZE, 2080)
        self.assertEqual(G3X_TRACE_LOG_MAX_SIZE, 64 * 1024)

    # -------------------------------------------------------------------------
    # 2. Valid Log Parsing (Unwrapped, Monotonic)
    # -------------------------------------------------------------------------
    def test_valid_log_parsing(self):
        """Parse a valid synthetic log with 5 sequential stage records."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=G3X_TRACE_CAPACITY,
            write_idx=5,
            dropped_count=0,
            record_size=G3X_TRACE_RECORD_SIZE,
        )
        self.assertEqual(len(header_bytes), 32)

        records_data = bytearray()
        stages = [
            (G3X_STAGE_ENTRY, 100, 0x003489B4, "CORE_ENTRY"),
            (G3X_STAGE_RELOC, 105, 0x00000000, "RELOC_DONE"),
            (G3X_STAGE_TASK_HOOK, 110, 0x00000000, "TASK_STARTUP"),
            (G3X_STAGE_KBD, 115, 0x00000000, "KBD_INIT"),
            (G3X_STAGE_DISPLAY, 120, 0x00000000, "DISP_INIT"),
        ]
        for stage_id, tick, val, text in stages:
            rec_bytes = pack_record(stage_id=stage_id, tick=tick, pc_lr_val=val, text=text)
            self.assertEqual(len(rec_bytes), 32)
            records_data.extend(rec_bytes)

        full_blob = bytes(header_bytes + records_data)
        self.assertEqual(len(full_blob), 32 + 5 * 32)

        # Parse blob
        result = parse_trace(full_blob)

        # Validate header
        self.assertEqual(result.header.magic, 0x43415254)
        self.assertEqual(result.header.magic_ascii, "TRAC")
        self.assertEqual(result.header.version, 0x00010000)
        self.assertEqual(result.header.version_major, 1)
        self.assertEqual(result.header.version_minor, 0)
        self.assertEqual(result.header.capacity, 64)
        self.assertEqual(result.header.write_idx, 5)
        self.assertEqual(result.header.dropped_count, 0)
        self.assertEqual(result.header.offset, 0)

        # Validate status
        self.assertFalse(result.wrapped)
        self.assertFalse(result.truncated)
        self.assertEqual(result.records_decoded, 5)
        self.assertEqual(result.records_expected, 5)
        self.assertEqual(result.trailing_bytes, 0)

        # Validate records
        self.assertEqual(len(result.records), 5)
        for i, (stage_id, tick, val, text) in enumerate(stages):
            rec = result.records[i]
            self.assertEqual(rec.index, i)
            self.assertEqual(rec.seq, i)
            self.assertEqual(rec.slot, i)
            self.assertEqual(rec.stage_id, stage_id)
            self.assertEqual(rec.stage_name, STAGE_NAMES[stage_id])
            self.assertEqual(rec.tick, tick)
            self.assertEqual(rec.pc_lr_val, val)
            self.assertEqual(rec.text, text)

        # Validate JSON serialization
        json_str = result.to_json()
        parsed_json = json.loads(json_str)
        self.assertEqual(parsed_json["header"]["magic"], "0x43415254")
        self.assertEqual(parsed_json["status"]["records_decoded"], 5)
        self.assertEqual(len(parsed_json["records"]), 5)
        self.assertEqual(parsed_json["records"][0]["text"], "CORE_ENTRY")
        self.assertEqual(parsed_json["records"][0]["pc_lr_val_hex"], "0x003489b4")

        # Validate human-readable table output
        table_str = result.to_table()
        self.assertIn("=== G3X Trace Header ===", table_str)
        self.assertIn("TRAC", table_str)
        self.assertIn("G3X_STAGE_ENTRY", table_str)
        self.assertIn("CORE_ENTRY", table_str)
        self.assertIn("DISP_INIT", table_str)

    # -------------------------------------------------------------------------
    # 3. Wrapped Ring Buffer Parsing
    # -------------------------------------------------------------------------
    def test_wrapped_ring_parsing(self):
        """Parse a wrapped synthetic ring buffer (write_idx=70, capacity=64).

        Records 0..5 are overwritten by records 64..69 in slots 0..5.
        Slots 6..63 contain records 6..63.
        Unwrapping must reconstruct chronological sequence 6..69.
        """
        capacity = 64
        write_idx = 70
        dropped_count = write_idx - capacity  # 6

        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=write_idx,
            dropped_count=dropped_count,
            record_size=G3X_TRACE_RECORD_SIZE,
        )

        slots = [bytearray() for _ in range(capacity)]

        # Slots 6..63 hold records 6..63
        for seq in range(6, 64):
            slot = seq % capacity
            slots[slot] = pack_record(
                stage_id=G3X_STAGE_TASK_HOOK,
                tick=1000 + seq,
                pc_lr_val=0x1000 + seq,
                text=f"REC_{seq:03d}",
            )

        # Slots 0..5 hold wrapped records 64..69
        for seq in range(64, 70):
            slot = seq % capacity  # 0..5
            slots[slot] = pack_record(
                stage_id=G3X_STAGE_DISPLAY if seq == 69 else G3X_STAGE_KBD,
                tick=1000 + seq,
                pc_lr_val=0x1000 + seq,
                text=f"REC_{seq:03d}",
            )

        # Concatenate header + all 64 slots = 2080 bytes
        ring_bytes = bytearray(header_bytes)
        for s in slots:
            ring_bytes.extend(s)
        self.assertEqual(len(ring_bytes), G3X_TRACE_RING_SIZE)

        # Parse wrapped ring
        result = parse_trace(bytes(ring_bytes))

        self.assertTrue(result.wrapped)
        self.assertFalse(result.truncated)
        self.assertEqual(result.records_decoded, 64)
        self.assertEqual(result.records_expected, 64)
        self.assertEqual(result.header.dropped_count, 6)

        # Verify chronological ordering from sequence 6 to 69
        for i, rec in enumerate(result.records):
            expected_seq = 6 + i
            expected_slot = expected_seq % capacity
            self.assertEqual(rec.index, i)
            self.assertEqual(rec.seq, expected_seq)
            self.assertEqual(rec.slot, expected_slot)
            self.assertEqual(rec.tick, 1000 + expected_seq)
            self.assertEqual(rec.pc_lr_val, 0x1000 + expected_seq)
            self.assertEqual(rec.text, f"REC_{expected_seq:03d}")

        # First record must be sequence 6 (slot 6, oldest surviving)
        self.assertEqual(result.records[0].seq, 6)
        self.assertEqual(result.records[0].slot, 6)

        # Last record must be sequence 69 (slot 5, newest)
        self.assertEqual(result.records[-1].seq, 69)
        self.assertEqual(result.records[-1].slot, 5)

    def test_wrapped_ring_with_prefix_and_suffix_junk(self):
        """Wrapped ring surrounded by prefix and suffix junk decodes chronologically (Issue 1.a).

        Tests: 64 prefix junk bytes + valid ring (write_idx=70, capacity=64, dropped=6)
        + 96 suffix junk bytes.
        Must decode exactly 64 records starting from sequence 6, without suffix pollution.
        """
        capacity = 64
        write_idx = 70
        dropped_count = 6

        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=write_idx,
            dropped_count=dropped_count,
            record_size=G3X_TRACE_RECORD_SIZE,
        )

        slots = [bytearray() for _ in range(capacity)]
        for seq in range(6, 64):
            slot = seq % capacity
            slots[slot] = pack_record(
                stage_id=G3X_STAGE_TASK_HOOK,
                tick=1000 + seq,
                pc_lr_val=0x1000 + seq,
                text=f"REC_{seq:03d}",
            )
        for seq in range(64, 70):
            slot = seq % capacity
            slots[slot] = pack_record(
                stage_id=G3X_STAGE_KBD,
                tick=1000 + seq,
                pc_lr_val=0x1000 + seq,
                text=f"REC_{seq:03d}",
            )

        ring_body = bytearray(header_bytes)
        for s in slots:
            ring_body.extend(s)
        self.assertEqual(len(ring_body), G3X_TRACE_RING_SIZE)

        # Add prefix and suffix junk
        prefix_junk = b"\xAA\x55" * 32  # 64 bytes
        suffix_junk = b"\xDE\xAD\xBE\xEF" * 24  # 96 unrelated bytes
        blob = prefix_junk + ring_body + suffix_junk

        # Parse without explicit offset or mode (auto-detects header and ring mode)
        result = parse_trace(blob)

        self.assertEqual(result.header.offset, 64)
        self.assertEqual(result.mode, "ring")
        self.assertTrue(result.wrapped)
        self.assertEqual(result.records_decoded, 64)
        self.assertEqual(result.records_expected, 64)
        self.assertEqual(result.trailing_bytes, 0)
        self.assertFalse(result.truncated)

        # First record must be sequence 6
        self.assertEqual(result.records[0].seq, 6)
        self.assertEqual(result.records[0].slot, 6)
        self.assertEqual(result.records[0].text, "REC_006")

        # Last record must be sequence 69
        self.assertEqual(result.records[-1].seq, 69)
        self.assertEqual(result.records[-1].slot, 5)
        self.assertEqual(result.records[-1].text, "REC_069")

    def test_unwrapped_ring_with_suffix_junk(self):
        """Unwrapped ring with suffix junk returns only valid records (Issue 1.b).

        Tests: ring with write_idx=5, capacity=64, followed by 128 suffix junk bytes.
        Must return only the 5 valid records without decoding unused slots or suffix junk.
        """
        capacity = 64
        write_idx = 5
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=write_idx,
            dropped_count=0,
            record_size=G3X_TRACE_RECORD_SIZE,
        )

        slots = [bytearray() for _ in range(capacity)]
        for i in range(write_idx):
            slots[i] = pack_record(
                stage_id=G3X_STAGE_ENTRY + i,
                tick=10 + i,
                pc_lr_val=0x100 * (i + 1),
                text=f"VALID_{i}",
            )
        for i in range(write_idx, capacity):
            slots[i] = pack_record(stage_id=G3X_STAGE_NONE, tick=0, pc_lr_val=0, text="")

        ring_body = bytearray(header_bytes)
        for s in slots:
            ring_body.extend(s)
        self.assertEqual(len(ring_body), G3X_TRACE_RING_SIZE)

        suffix_junk = b"\x33\xCC\x55\xAA" * 32  # 128 bytes
        blob = bytes(ring_body + suffix_junk)

        result = parse_trace(blob)

        self.assertEqual(result.mode, "ring")
        self.assertFalse(result.wrapped)
        self.assertEqual(result.records_decoded, 5)
        self.assertEqual(result.records_expected, 5)
        self.assertEqual(len(result.records), 5)
        for i in range(5):
            self.assertEqual(result.records[i].text, f"VALID_{i}")
            self.assertEqual(result.records[i].seq, i)
            self.assertEqual(result.records[i].slot, i)

    # -------------------------------------------------------------------------
    # 4. Truncated Tail & Size-Capped Log Handling
    # -------------------------------------------------------------------------
    def test_truncated_tail_partial_record(self):
        """Parser must not crash when data ends with a partial (truncated) record."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=3,
            dropped_count=0,
        )
        rec1 = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, pc_lr_val=0x11, text="REC_1")
        rec2 = pack_record(stage_id=G3X_STAGE_RELOC, tick=2, pc_lr_val=0x22, text="REC_2")
        # 17 bytes of trailing incomplete record (< 32 bytes)
        trailing_partial = b"PARTIAL_REC_BYTES"
        self.assertEqual(len(trailing_partial), 17)

        blob = header_bytes + rec1 + rec2 + trailing_partial
        self.assertEqual(len(blob), 32 + 32 + 32 + 17)

        result = parse_trace(blob)

        # Must decode the 2 complete records without error
        self.assertEqual(result.records_decoded, 2)
        self.assertTrue(result.truncated)
        self.assertEqual(result.trailing_bytes, 17)
        self.assertEqual(result.records[0].text, "REC_1")
        self.assertEqual(result.records[1].text, "REC_2")

    def test_truncated_wrapped_ring(self):
        """Parser must handle a wrapped ring dump cut short before all 64 slots."""
        capacity = 64
        write_idx = 70  # wrapped (oldest at slot 6)
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=write_idx,
            dropped_count=6,
        )

        # Only 40 records present instead of 64
        present_count = 40
        slots_data = bytearray()
        for slot in range(present_count):
            slots_data.extend(pack_record(
                stage_id=G3X_STAGE_ENTRY,
                tick=100 + slot,
                pc_lr_val=slot,
                text=f"SLOT_{slot:02d}",
            ))

        blob = bytes(header_bytes + slots_data)
        self.assertEqual(len(blob), 32 + present_count * 32)

        # Parse truncated wrapped ring
        result = parse_trace(blob)

        self.assertTrue(result.wrapped)
        self.assertTrue(result.truncated)
        self.assertEqual(result.records_decoded, present_count)
        self.assertEqual(result.records_expected, capacity)
        # Verify chronological ordering of present slots:
        # Slots 6..39 are present (seq 6..39)
        # Slots 0..5 are present (seq 64..69)
        self.assertEqual(result.records[0].slot, 6)
        self.assertEqual(result.records[33].slot, 39)
        self.assertEqual(result.records[34].slot, 0)
        self.assertEqual(result.records[-1].slot, 5)

    def test_truncated_header_raises_error(self):
        """Data smaller than 32-byte header must raise TruncatedDataError."""
        short_blob = b"TRAC" + b"\x00" * 12
        self.assertEqual(len(short_blob), 16)

        with self.assertRaises(TruncatedDataError):
            locate_header(short_blob)

        with self.assertRaises(TruncatedDataError):
            parse_trace(short_blob)

    def test_size_capped_log(self):
        """Parse a full size-capped TRACE.LOG (64 KiB = 2047 records)."""
        num_records = G3X_TRACE_LOG_MAX_RECORDS
        self.assertEqual(num_records, 2047)
        self.assertEqual(G3X_TRACE_HEADER_SIZE + num_records * G3X_TRACE_RECORD_SIZE, 65536)

        header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=num_records,
            dropped_count=0,
        )

        rec = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, pc_lr_val=0, text="CAP_TEST")
        capped_blob = header + (rec * num_records)
        self.assertEqual(len(capped_blob), 65536)

        result = parse_trace(capped_blob)
        self.assertEqual(result.mode, "log")
        self.assertEqual(result.records_decoded, num_records)
        self.assertEqual(result.trailing_bytes, 0)
        self.assertFalse(result.truncated)

    # -------------------------------------------------------------------------
    # 5. Bad Magic & Unknown Version Handling
    # -------------------------------------------------------------------------
    def test_bad_magic_detection(self):
        """Header with invalid magic must raise BadMagicError."""
        bad_magics = [
            0xDEADBEEF,
            0x00000000,
            0xFFFFFFFF,
            0x43415255,  # b"URAC" (one bit off)
        ]
        for bm in bad_magics:
            header_bytes = pack_header(
                magic=bm,
                version=G3X_TRACE_VERSION,
                capacity=64,
                write_idx=0,
            )
            with self.assertRaises(BadMagicError):
                locate_header(header_bytes)
            with self.assertRaises(BadMagicError):
                parse_header(header_bytes)
            with self.assertRaises(BadMagicError):
                parse_trace(header_bytes)

    def test_bad_magic_embedded_offset(self):
        """Non-trace random bytes without magic must raise BadMagicError."""
        random_blob = os.urandom(512)
        random_blob = random_blob.replace(b"TRAC", b"ZZZZ")
        with self.assertRaises(BadMagicError):
            locate_header(random_blob)
        with self.assertRaises(BadMagicError):
            parse_trace(random_blob)

    def test_unknown_version_detection(self):
        """Header with unsupported version must raise UnknownVersionError."""
        unknown_versions = [
            0x00000001,  # v0.1
            0x00020000,  # v2.0
            0xFFFFFFFF,
            0x00010001,  # v1.1
        ]
        for uv in unknown_versions:
            header_bytes = pack_header(
                magic=G3X_TRACE_MAGIC,
                version=uv,
                capacity=64,
                write_idx=0,
            )
            with self.assertRaises(UnknownVersionError):
                locate_header(header_bytes)
            with self.assertRaises(UnknownVersionError):
                parse_header(header_bytes)
            with self.assertRaises(UnknownVersionError):
                parse_trace(header_bytes)

    # -------------------------------------------------------------------------
    # 6. Malformed Header Field Validation (Issue 2)
    # -------------------------------------------------------------------------
    def test_malformed_header_wrong_record_size(self):
        """Header declaring record_size != 32 must raise MalformedHeaderError."""
        for bad_size in [64, 16, 0, 128]:
            header_bytes = pack_header(
                magic=G3X_TRACE_MAGIC,
                version=G3X_TRACE_VERSION,
                capacity=G3X_TRACE_CAPACITY,
                write_idx=2,
                dropped_count=0,
                record_size=bad_size,
            )
            rec = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, pc_lr_val=0, text="TEST")
            blob = header_bytes + rec * 2

            with self.assertRaises(MalformedHeaderError) as ctx:
                parse_header(blob)
            self.assertIn("record_size", str(ctx.exception))

            with self.assertRaises(MalformedHeaderError):
                parse_trace(blob)

    def test_malformed_header_zero_capacity(self):
        """Header declaring capacity == 0 must raise MalformedHeaderError cleanly."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=0,
            write_idx=0,
            dropped_count=0,
            record_size=G3X_TRACE_RECORD_SIZE,
        )
        with self.assertRaises(MalformedHeaderError) as ctx:
            parse_header(header_bytes)
        self.assertIn("capacity", str(ctx.exception))

        with self.assertRaises(MalformedHeaderError):
            parse_trace(header_bytes)

    def test_malformed_header_oversized_capacity(self):
        """Header declaring oversized capacity (e.g. 0xFFFFFFFF) must fail immediately without loop."""
        for bad_cap in [0xFFFFFFFF, 128, 1024]:
            header_bytes = pack_header(
                magic=G3X_TRACE_MAGIC,
                version=G3X_TRACE_VERSION,
                capacity=bad_cap,
                write_idx=0,
                dropped_count=0,
                record_size=G3X_TRACE_RECORD_SIZE,
            )
            with self.assertRaises(MalformedHeaderError) as ctx:
                parse_header(header_bytes)
            self.assertIn("capacity", str(ctx.exception))

            with self.assertRaises(MalformedHeaderError):
                parse_trace(header_bytes)

    def test_large_write_idx_0x01000000_wrapped_ring(self):
        """Full wrapped ring with write_idx=0x01000000 decodes successfully in reconstructed order."""
        widx = 0x01000000
        capacity = G3X_TRACE_CAPACITY  # 64
        dropped = widx - capacity

        header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=widx,
            dropped_count=dropped,
            record_size=G3X_TRACE_RECORD_SIZE,
        )

        # In C, with widx = 0x01000000 (16777216) and capacity = 64:
        # widx % 64 == 0.
        # The last 64 writes were seq = (widx - 64) + s for s in 0..63.
        # Written slot = seq % 64 = ((widx - 64) + s) % 64 = s.
        # So slot s holds the record written at sequence (widx - 64) + s.
        records_raw = bytearray()
        for s in range(capacity):
            seq = (widx - capacity) + s
            records_raw.extend(
                pack_record(
                    stage_id=G3X_STAGE_TASK_HOOK,
                    tick=seq,
                    pc_lr_val=s * 4,
                    text=f"WIDX_{s:02d}",
                )
            )

        blob = header + bytes(records_raw)
        result = parse_trace(blob)

        self.assertTrue(result.wrapped)
        self.assertEqual(result.records_decoded, capacity)
        self.assertEqual(result.header.write_idx, widx)
        self.assertEqual(result.header.dropped_count, dropped)

        # Assert reconstructed record order
        for i in range(capacity):
            expected_seq = (widx - capacity) + i
            expected_slot = i
            self.assertEqual(result.records[i].index, i)
            self.assertEqual(result.records[i].seq, expected_seq)
            self.assertEqual(result.records[i].slot, expected_slot)
            self.assertEqual(result.records[i].tick, expected_seq)
            self.assertEqual(result.records[i].text, f"WIDX_{expected_slot:02d}")

    def test_large_write_idx_near_uint32_max_wrapped_ring(self):
        """Full wrapped ring with write_idx near 0xFFFFFFFF decodes successfully in reconstructed order."""
        widx = 0xFFFFFFFF  # Max 32-bit uint (4294967295)
        capacity = G3X_TRACE_CAPACITY  # 64
        dropped = widx - capacity

        header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=capacity,
            write_idx=widx,
            dropped_count=dropped,
            record_size=G3X_TRACE_RECORD_SIZE,
        )

        # In C:
        # widx % 64 == 63.
        # The last 64 writes were for seq = (widx - 64) + i for i in 0..63.
        # Written slot = seq % 64 = ((widx - 64) + i) % 64 = (63 + i) % 64.
        # So slot (63 + i) % 64 holds record with seq = (widx - 64) + i.
        slots_data: dict[int, bytes] = {}
        for i in range(capacity):
            seq = (widx - capacity) + i
            slot = (63 + i) % 64
            slots_data[slot] = pack_record(
                stage_id=G3X_STAGE_DISPLAY,
                tick=seq,
                pc_lr_val=0xFC000000 + slot,
                text=f"MAX_{slot:02d}",
            )

        records_raw = bytearray()
        for s in range(capacity):
            records_raw.extend(slots_data[s])

        blob = header + bytes(records_raw)
        result = parse_trace(blob)

        self.assertTrue(result.wrapped)
        self.assertEqual(result.records_decoded, capacity)
        self.assertEqual(result.header.write_idx, widx)
        self.assertEqual(result.header.dropped_count, dropped)

        # Assert reconstructed record order
        # Oldest record in sequence must be slot 63 (seq = widx - 64)
        self.assertEqual(result.records[0].slot, 63)
        self.assertEqual(result.records[0].seq, widx - capacity)
        self.assertEqual(result.records[0].text, "MAX_63")

        # Newest record in sequence must be slot 62 (seq = widx - 1)
        self.assertEqual(result.records[-1].slot, 62)
        self.assertEqual(result.records[-1].seq, widx - 1)
        self.assertEqual(result.records[-1].text, "MAX_62")

        for i in range(capacity):
            expected_slot = (63 + i) % 64
            expected_seq = (widx - capacity) + i
            self.assertEqual(result.records[i].index, i)
            self.assertEqual(result.records[i].seq, expected_seq)
            self.assertEqual(result.records[i].slot, expected_slot)
            self.assertEqual(result.records[i].tick, expected_seq)
            self.assertEqual(result.records[i].text, f"MAX_{expected_slot:02d}")

    def test_scan_skips_false_candidate_before_valid_ring(self):
        """Scanner skips false candidate b'TRAC'+version+bytes(24) and locates valid ring at offset 32."""
        false_candidate = b"TRAC" + struct.pack("<I", 0x10000) + bytes(24)
        self.assertEqual(len(false_candidate), 32)

        valid_header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=2,
            dropped_count=0,
            record_size=32,
        )
        rec0 = pack_record(stage_id=G3X_STAGE_ENTRY, tick=100, pc_lr_val=0x1111, text="STAGE1")
        rec1 = pack_record(stage_id=G3X_STAGE_RELOC, tick=200, pc_lr_val=0x2222, text="STAGE2")
        padding_recs = pack_record(stage_id=G3X_STAGE_NONE) * 62
        valid_ring = valid_header + rec0 + rec1 + padding_recs

        blob = false_candidate + valid_ring

        offset = locate_header(blob)
        self.assertEqual(offset, 32)

        result = parse_trace(blob)
        self.assertEqual(result.header.offset, 32)
        self.assertEqual(result.records_decoded, 2)
        self.assertEqual(result.records[0].text, "STAGE1")
        self.assertEqual(result.records[1].text, "STAGE2")

    def test_scan_skips_false_candidate_before_valid_log(self):
        """Scanner skips false candidate before a valid header in log mode."""
        false_candidate = b"TRAC" + struct.pack("<I", 0x10000) + bytes(24)
        self.assertEqual(len(false_candidate), 32)

        valid_header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=3,
            dropped_count=0,
            record_size=32,
        )
        rec0 = pack_record(stage_id=G3X_STAGE_ENTRY, tick=10, pc_lr_val=0, text="LOG_ENTRY")
        rec1 = pack_record(stage_id=G3X_STAGE_TASK_HOOK, tick=20, pc_lr_val=0, text="LOG_HOOK")
        rec2 = pack_record(stage_id=G3X_STAGE_FLUSH, tick=30, pc_lr_val=0, text="LOG_FLUSH")
        valid_log = valid_header + rec0 + rec1 + rec2

        blob = false_candidate + valid_log

        offset_auto = locate_header(blob)
        self.assertEqual(offset_auto, 32)

        offset_log = locate_header(blob, mode="log")
        self.assertEqual(offset_log, 32)

        result = parse_trace(blob, mode="log")
        self.assertEqual(result.header.offset, 32)
        self.assertEqual(result.mode, "log")
        self.assertEqual(result.records_decoded, 3)
        self.assertEqual(result.records[0].text, "LOG_ENTRY")
        self.assertEqual(result.records[1].text, "LOG_HOOK")
        self.assertEqual(result.records[2].text, "LOG_FLUSH")

    def test_false_candidate_alone_raises_malformed_header(self):
        """A blob with only a false candidate raises MalformedHeaderError."""
        false_candidate = b"TRAC" + struct.pack("<I", 0x10000) + bytes(24)
        with self.assertRaises(MalformedHeaderError):
            locate_header(false_candidate)
        with self.assertRaises(MalformedHeaderError):
            parse_trace(false_candidate)

    def test_scan_skips_wrapped_ring_candidate_when_log_mode_requested(self):
        """When log mode is explicitly requested, scanner skips a wrapped ring header before valid log."""
        ring_candidate = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=70,
            dropped_count=6,
            record_size=32,
        )
        rec = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, text="RING_REC")
        ring_blob = ring_candidate + (rec * 64)

        log_header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=1,
            dropped_count=0,
            record_size=32,
        )
        log_rec = pack_record(stage_id=G3X_STAGE_FLUSH, tick=99, text="LOG_REC")
        log_blob = log_header + log_rec

        combined = ring_blob + log_blob
        result = parse_trace(combined, mode="log")
        self.assertEqual(result.header.offset, len(ring_blob))
        self.assertEqual(result.mode, "log")
        self.assertEqual(result.records_decoded, 1)
        self.assertEqual(result.records[0].text, "LOG_REC")

    def test_malformed_header_inconsistent_dropped_count(self):
        """Inconsistent dropped_count vs write_idx in ring mode must raise MalformedHeaderError."""
        # Unwrapped ring with non-zero dropped_count
        bad_hdr_1 = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=G3X_TRACE_CAPACITY,
            write_idx=5,
            dropped_count=10,  # Expected 0
            record_size=G3X_TRACE_RECORD_SIZE,
        )
        with self.assertRaises(MalformedHeaderError):
            parse_trace(bad_hdr_1, mode="ring")

        # Wrapped ring with incorrect dropped_count
        bad_hdr_2 = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=G3X_TRACE_CAPACITY,
            write_idx=70,
            dropped_count=0,  # Expected 70 - 64 = 6
            record_size=G3X_TRACE_RECORD_SIZE,
        )
        with self.assertRaises(MalformedHeaderError):
            parse_trace(bad_hdr_2, mode="ring")

    # -------------------------------------------------------------------------
    # 7. Mode Selection & Offset Handling
    # -------------------------------------------------------------------------
    def test_explicit_mode_ring_and_log(self):
        """Explicit mode selection via API and CLI."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=2,
            dropped_count=0,
        )
        rec1 = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, text="REC1")
        rec2 = pack_record(stage_id=G3X_STAGE_RELOC, tick=2, text="REC2")
        blob = header_bytes + rec1 + rec2

        res_ring = parse_trace(blob, mode="ring")
        self.assertEqual(res_ring.mode, "ring")
        self.assertEqual(res_ring.records_decoded, 2)

        res_log = parse_trace(blob, mode="log")
        self.assertEqual(res_log.mode, "log")
        self.assertEqual(res_log.records_decoded, 2)

        with self.assertRaises(ValueError):
            parse_trace(blob, mode="invalid_mode")

    def test_header_scanning_and_explicit_offset(self):
        """Header located at non-zero offset via auto-scan and explicit offset."""
        prefix = b"\x00" * 120
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=1,
            dropped_count=0,
        )
        rec = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, pc_lr_val=0, text="OFFSET_TEST")
        blob = prefix + header_bytes + rec

        # Auto-detect offset
        result_auto = parse_trace(blob)
        self.assertEqual(result_auto.header.offset, 120)
        self.assertEqual(result_auto.records_decoded, 1)
        self.assertEqual(result_auto.records[0].text, "OFFSET_TEST")

        # Explicit offset
        result_explicit = parse_trace(blob, offset=120)
        self.assertEqual(result_explicit.header.offset, 120)
        self.assertEqual(result_explicit.records_decoded, 1)

        # Wrong explicit offset raises BadMagicError
        with self.assertRaises(BadMagicError):
            parse_trace(blob, offset=60)

    def test_all_slots_option(self):
        """all_slots=True returns all 64 slots in an unwrapped ring buffer."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=2,
            dropped_count=0,
        )
        slots = [pack_record(stage_id=G3X_STAGE_ENTRY, tick=i, text=f"REC_{i}") for i in range(64)]
        blob = header_bytes + b"".join(slots)

        result_default = parse_trace(blob, all_slots=False)
        self.assertEqual(result_default.records_decoded, 2)

        result_all = parse_trace(blob, all_slots=True)
        self.assertEqual(result_all.records_decoded, 64)

    # -------------------------------------------------------------------------
    # 8. Command-Line Interface (CLI) Testing (using TemporaryDirectory)
    # -------------------------------------------------------------------------
    def test_cli_json_output(self):
        """CLI default execution outputs valid JSON."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=2,
            dropped_count=0,
        )
        rec1 = pack_record(stage_id=G3X_STAGE_ENTRY, tick=1, pc_lr_val=0x003489B4, text="ENTRY")
        rec2 = pack_record(stage_id=G3X_STAGE_RELOC, tick=2, pc_lr_val=0, text="RELOC")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test.bin")
            with open(tmp_path, "wb") as f:
                f.write(header_bytes + rec1 + rec2)

            cmd = [sys.executable, PARSER_SCRIPT, tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"CLI failed: {res.stderr}")

            parsed = json.loads(res.stdout)
            self.assertEqual(parsed["header"]["magic"], "0x43415254")
            self.assertEqual(parsed["status"]["records_decoded"], 2)
            self.assertEqual(parsed["records"][0]["text"], "ENTRY")
            self.assertEqual(parsed["records"][1]["text"], "RELOC")

    def test_cli_table_output(self):
        """CLI with --table / -H displays human-readable output."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=1,
            dropped_count=0,
        )
        rec = pack_record(stage_id=G3X_STAGE_KBD, tick=50, pc_lr_val=0x1234, text="KBD_TEST")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test.bin")
            with open(tmp_path, "wb") as f:
                f.write(header_bytes + rec)

            cmd = [sys.executable, PARSER_SCRIPT, "--table", tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("=== G3X Trace Header ===", res.stdout)
            self.assertIn("G3X_STAGE_KBD", res.stdout)
            self.assertIn("KBD_TEST", res.stdout)

    def test_cli_bad_magic_exits_nonzero(self):
        """CLI with bad magic exits non-zero and prints clear error to stderr."""
        bad_header = pack_header(
            magic=0xDEADBEEF,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test.bin")
            with open(tmp_path, "wb") as f:
                f.write(bad_header)

            cmd = [sys.executable, PARSER_SCRIPT, tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("magic", res.stderr.lower())

    def test_cli_unknown_version_exits_nonzero(self):
        """CLI with unknown version exits non-zero and prints clear error to stderr."""
        bad_ver_header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=0x00020000,
            capacity=64,
            write_idx=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test.bin")
            with open(tmp_path, "wb") as f:
                f.write(bad_ver_header)

            cmd = [sys.executable, PARSER_SCRIPT, tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("version", res.stderr.lower())

    def test_cli_malformed_header_exits_nonzero(self):
        """CLI with malformed header fields (e.g. record_size=64) exits non-zero with clear error."""
        malformed_header = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=0,
            dropped_count=0,
            record_size=64,  # Expected 32
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test.bin")
            with open(tmp_path, "wb") as f:
                f.write(malformed_header)

            cmd = [sys.executable, PARSER_SCRIPT, tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("record_size", res.stderr.lower())

    def test_cli_stdin_pipeline(self):
        """CLI accepts trace data piped via standard input."""
        header_bytes = pack_header(
            magic=G3X_TRACE_MAGIC,
            version=G3X_TRACE_VERSION,
            capacity=64,
            write_idx=1,
            dropped_count=0,
        )
        rec = pack_record(stage_id=G3X_STAGE_FLUSH, tick=99, pc_lr_val=0, text="FLUSH_PIPE")
        payload = header_bytes + rec

        cmd = [sys.executable, PARSER_SCRIPT, "-"]
        res = subprocess.run(
            cmd,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(res.returncode, 0, f"Stdin pipe failed: {res.stderr.decode()}")
        parsed = json.loads(res.stdout.decode())
        self.assertEqual(parsed["records"][0]["text"], "FLUSH_PIPE")


if __name__ == "__main__":
    unittest.main()
