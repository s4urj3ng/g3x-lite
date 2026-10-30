#!/usr/bin/env python3
"""PORT-17: Standard-library-only TRACE.LOG and raw ring dump parser.

Platform: Canon PowerShot G3 X (GM1.10C / Platform ID 0x32A8 = 12968 decimal)
Subsystem: Early-boot & post-continuation telemetry ring buffer and stage markers
Safety Scope: Phase 0 host static analysis / offline tools (docs/SAFETY.md)

Trace Core Header Citations:
- Byte layout and endianness specification:
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:16-44
- Trace header, record, and ring buffer layout specification:
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:22-43
- Format constants, signatures, and stage identifiers:
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:53-73
- TRACE.LOG destination path and max size:
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:135-137
- C structure definitions (g3x_trace_header_t, g3x_trace_record_t, g3x_trace_ring_t):
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:141-165
- Struct size and field offset static assertions:
  chdk-port/platform/g3x/sub/110c/g3x_trace.h:167-187

Interpretation Modes and Detection Rules:
------------------------------------------
The parser supports two interpretation modes:
1. 'ring' mode: Fixed-capacity ring buffer dump (g3x_trace_ring_t, 2080 bytes).
   - Extent is strictly bounded to header_size + capacity * record_size (2080 bytes)
     from the header offset; any trailing bytes beyond this extent are ignored as
     memory dump suffix.
   - If write_idx > capacity (or dropped_count > 0): the ring has wrapped. Records
     are unwound starting at oldest_slot = (write_idx % capacity) with sequence
     seq = (write_idx - capacity) + i, restoring chronological order.
   - If write_idx <= capacity: the ring has not wrapped; only the valid write_idx
     records are returned (slots 0..write_idx-1) unless all_slots=True.
2. 'log' mode (alias 'linear'): Append-only log file (TRACE.LOG, up to 64 KiB).
   - Records are read sequentially from slot 0 up to available records or log cap.
   - Suffix bytes not forming a complete 32-byte record are flagged as trailing.
3. 'auto' mode (default):
   - If dropped_count > 0 or (write_idx > capacity and dropped_count == write_idx - capacity):
     definitively a wrapped ring dump -> 'ring' mode.
   - If write_idx > capacity and dropped_count == 0:
     definitively an append-only linear log -> 'log' mode.
   - If write_idx <= capacity and dropped_count == 0:
     ambiguous between unwrapped ring and short linear log. Defaults to 'ring' mode,
     bounding the extent to the ring buffer size and returning the write_idx valid records.
   - Explicit CLI/API selection (--mode ring|log) is available when required.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import struct
import sys
from typing import Any, List, Optional, Tuple

# =============================================================================
# Format Constants & Signatures
# Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:22-43, 53-73, 135-137
# =============================================================================
G3X_TRACE_MAGIC = 0x43415254          # ASCII "TRAC", Little-Endian word 0x43415254 (b"TRAC")
G3X_TRACE_MAGIC_BYTES = b"TRAC"       # Raw 4-byte signature
G3X_TRACE_VERSION = 0x00010000        # Version 1.0 (Major 1, Minor 0)

G3X_TRACE_RECORD_TEXT_LEN = 20        # Fixed length of record text (g3x_trace.h:56)
G3X_TRACE_CAPACITY = 64               # Ring buffer capacity (records) (g3x_trace.h:26,57)
G3X_TRACE_RECORD_SIZE = 32            # sizeof(g3x_trace_record_t) (g3x_trace.h:29,58)
G3X_TRACE_HEADER_SIZE = 32            # sizeof(g3x_trace_header_t) (g3x_trace.h:22,59)
G3X_TRACE_RING_SIZE = 2080            # 32 + (64 * 32) = 2080 bytes (g3x_trace.h:40,60)
G3X_TRACE_LOG_MAX_SIZE = 64 * 1024    # 64 KiB maximum log size (g3x_trace.h:136)
G3X_TRACE_LOG_MAX_RECORDS = (G3X_TRACE_LOG_MAX_SIZE - G3X_TRACE_HEADER_SIZE) // G3X_TRACE_RECORD_SIZE  # 2047 records

# Struct pack/unpack formats (Little-Endian)
HEADER_STRUCT_FORMAT = "<IIIIIIII"
RECORD_STRUCT_FORMAT = "<III20s"

# =============================================================================
# Stage Identifiers
# Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:65-73
# =============================================================================
G3X_STAGE_NONE = 0x00000000           # Empty / uninitialized record
G3X_STAGE_ENTRY = 0x00000001          # Stage 1: Core entry
G3X_STAGE_RELOC = 0x00000002          # Stage 2: Relocation / BSS zero completed
G3X_STAGE_TASK_HOOK = 0x00000003      # Stage 3: Task startup / task hooks registered
G3X_STAGE_KBD = 0x00000004            # Stage 4: Keyboard / PhySw initialized
G3X_STAGE_DISPLAY = 0x00000005        # Stage 5: Display / framebuffer initialized
G3X_STAGE_ASSERT = 0x000000FE         # Assertion failure witness
G3X_STAGE_FLUSH = 0x000000FF          # Explicit flush marker

STAGE_NAMES = {
    G3X_STAGE_NONE: "G3X_STAGE_NONE",
    G3X_STAGE_ENTRY: "G3X_STAGE_ENTRY",
    G3X_STAGE_RELOC: "G3X_STAGE_RELOC",
    G3X_STAGE_TASK_HOOK: "G3X_STAGE_TASK_HOOK",
    G3X_STAGE_KBD: "G3X_STAGE_KBD",
    G3X_STAGE_DISPLAY: "G3X_STAGE_DISPLAY",
    G3X_STAGE_ASSERT: "G3X_STAGE_ASSERT",
    G3X_STAGE_FLUSH: "G3X_STAGE_FLUSH",
}


def stage_id_to_name(stage_id: int) -> str:
    """Map a numerical stage ID to its canonical symbolic name."""
    return STAGE_NAMES.get(stage_id, f"STAGE_UNKNOWN_0x{stage_id:08X}")


# =============================================================================
# Exceptions
# =============================================================================
class TraceParserError(Exception):
    """Base exception for all trace parser errors."""
    pass


class BadMagicError(TraceParserError, ValueError):
    """Raised when trace header magic is invalid or not found."""
    pass


class UnknownVersionError(TraceParserError, ValueError):
    """Raised when trace header version is unsupported."""
    pass


class TruncatedDataError(TraceParserError, ValueError):
    """Raised when trace data is shorter than expected."""
    pass


class MalformedHeaderError(TraceParserError, ValueError):
    """Raised when trace header layout fields fail specification validation (g3x_trace.h:22-43)."""
    pass


# =============================================================================
# Data Structures
# =============================================================================
@dataclass
class TraceHeader:
    """Decoded 32-byte trace header.

    Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:22-32, 143-151.
    """
    magic: int
    magic_ascii: str
    version: int
    version_major: int
    version_minor: int
    capacity: int
    write_idx: int
    dropped_count: int
    record_size: int
    reserved: Tuple[int, int]
    offset: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert header to JSON-serializable dictionary."""
        return {
            "magic": f"0x{self.magic:08X}",
            "magic_ascii": self.magic_ascii,
            "version": f"0x{self.version:08X}",
            "version_major": self.version_major,
            "version_minor": self.version_minor,
            "capacity": self.capacity,
            "write_idx": self.write_idx,
            "dropped_count": self.dropped_count,
            "record_size": self.record_size,
            "reserved": list(self.reserved),
            "offset": self.offset,
        }


@dataclass
class TraceRecord:
    """Decoded single 32-byte trace record.

    Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:34-39, 153-159.
    """
    index: int
    seq: int
    slot: int
    stage_id: int
    stage_name: str
    tick: int
    pc_lr_val: int
    pc_lr_val_hex: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        """Convert record to JSON-serializable dictionary."""
        return {
            "index": self.index,
            "seq": self.seq,
            "slot": self.slot,
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "tick": self.tick,
            "pc_lr_val": self.pc_lr_val,
            "pc_lr_val_hex": self.pc_lr_val_hex,
            "text": self.text,
        }


@dataclass
class TraceParseResult:
    """Full trace parse result containing header, records, and metadata."""
    header: TraceHeader
    records: List[TraceRecord]
    wrapped: bool
    truncated: bool
    records_decoded: int
    records_expected: int
    trailing_bytes: int
    mode: str
    total_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            "header": self.header.to_dict(),
            "status": {
                "header_offset": self.header.offset,
                "total_bytes": self.total_bytes,
                "mode": self.mode,
                "records_decoded": self.records_decoded,
                "records_expected": self.records_expected,
                "wrapped": self.wrapped,
                "truncated": self.truncated,
                "trailing_bytes": self.trailing_bytes,
            },
            "records": [r.to_dict() for r in self.records],
        }

    def to_json(self, indent: int = 2) -> str:
        """Format the result as machine-readable JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_table(self) -> str:
        """Format the result as a human-readable table."""
        lines: list[str] = []
        lines.append("=== G3X Trace Header ===")
        lines.append(f"Magic:          0x{self.header.magic:08X} ({self.header.magic_ascii})")
        lines.append(f"Version:        {self.header.version_major}.{self.header.version_minor} (0x{self.header.version:08X})")
        lines.append(f"Capacity:       {self.header.capacity} records")
        lines.append(f"Write Index:    {self.header.write_idx}")
        lines.append(f"Dropped Count:  {self.header.dropped_count} (wrapped: {self.wrapped})")
        lines.append(f"Record Size:    {self.header.record_size} bytes")
        lines.append(f"Header Offset:  0x{self.header.offset:08X} ({self.header.offset})")
        lines.append(f"Total Bytes:    {self.total_bytes}")
        lines.append("")
        lines.append("=== Trace Status ===")
        lines.append(f"Mode:           {self.mode}")
        lines.append(f"Decoded:        {self.records_decoded} records")
        lines.append(f"Wrapped:        {self.wrapped} ({self.header.dropped_count} records overwritten)")
        lines.append(f"Truncated:      {self.truncated} ({self.trailing_bytes} trailing incomplete bytes)")
        if self.truncated:
            lines.append(
                f"WARNING:        Log data is truncated! Expected {self.records_expected} records, found {self.records_decoded}."
            )
        lines.append("")
        lines.append(f"=== Trace Records ({len(self.records)} records) ===")
        if not self.records:
            lines.append("(no records recorded)")
        else:
            header_fmt = "{:<5} {:<6} {:<5} {:<24} {:<10} {:<12} {:<20}"
            lines.append(header_fmt.format("#", "Seq", "Slot", "Stage", "Tick", "Value", "Text"))
            lines.append("-" * 88)
            row_fmt = "{:<5} {:<6} {:<5} {:<24} {:<10} {:<12} {:<20}"
            for r in self.records:
                stage_display = f"{r.stage_name} ({r.stage_id})" if len(r.stage_name) <= 18 else r.stage_name
                lines.append(row_fmt.format(
                    r.index,
                    r.seq,
                    r.slot,
                    stage_display,
                    r.tick,
                    r.pc_lr_val_hex,
                    r.text,
                ))
        return "\n".join(lines)


# =============================================================================
# Parsing & Validation Logic
# =============================================================================
def _is_header_consistent(
    write_idx: int,
    dropped_count: int,
    capacity: int,
    mode: Optional[str] = None,
) -> bool:
    """Validate write_idx and dropped_count consistency against g3x_trace.h:26-28, 136."""
    if capacity <= 0:
        return False
    if not (0 <= write_idx <= 0xFFFFFFFF and 0 <= dropped_count <= 0xFFFFFFFF):
        return False
    if mode == "ring":
        if write_idx <= capacity:
            return dropped_count == 0
        return dropped_count == (write_idx - capacity)
    elif mode in ("log", "linear"):
        return dropped_count == 0 and write_idx <= G3X_TRACE_LOG_MAX_RECORDS
    else:
        # auto / unspecified: must be valid under at least one interpretation
        is_ring = (
            (write_idx <= capacity and dropped_count == 0)
            or (write_idx > capacity and dropped_count == (write_idx - capacity))
        )
        is_log = (dropped_count == 0 and write_idx <= G3X_TRACE_LOG_MAX_RECORDS)
        return is_ring or is_log


def _validate_header_at(
    blob: bytes,
    offset: int,
    mode: Optional[str] = None,
) -> Tuple[Optional[TraceParserError], Optional[Tuple[int, int, int, int, int, int, int, int]]]:
    """Validate 32-byte header at offset and return (error, unpacked_fields)."""
    if len(blob) - offset < 4:
        return (
            BadMagicError(
                f"Data at offset 0x{offset:X} too short for magic ({len(blob) - offset} bytes)"
            ),
            None,
        )

    magic = struct.unpack_from("<I", blob, offset)[0]
    if magic != G3X_TRACE_MAGIC:
        return (
            BadMagicError(
                f"Bad trace magic at offset 0x{offset:X}: 0x{magic:08X} "
                f"(expected 0x{G3X_TRACE_MAGIC:08X} / 'TRAC')"
            ),
            None,
        )

    if len(blob) - offset < G3X_TRACE_HEADER_SIZE:
        return (
            TruncatedDataError(
                f"Truncated header at offset 0x{offset:X}: {len(blob) - offset} bytes "
                f"(expected {G3X_TRACE_HEADER_SIZE} bytes)"
            ),
            None,
        )

    fields = struct.unpack_from(HEADER_STRUCT_FORMAT, blob, offset)
    magic, version, capacity, write_idx, dropped_count, record_size, res0, res1 = fields

    if version != G3X_TRACE_VERSION:
        return (
            UnknownVersionError(
                f"Unknown trace version at offset 0x{offset:X}: 0x{version:08X} "
                f"(expected 0x{G3X_TRACE_VERSION:08X})"
            ),
            fields,
        )

    if record_size != G3X_TRACE_RECORD_SIZE:
        return (
            MalformedHeaderError(
                f"Invalid record_size {record_size} at offset 0x{offset:X}: "
                f"expected {G3X_TRACE_RECORD_SIZE} (g3x_trace.h:29,58)"
            ),
            fields,
        )

    if capacity != G3X_TRACE_CAPACITY:
        return (
            MalformedHeaderError(
                f"Invalid capacity {capacity} at offset 0x{offset:X}: "
                f"expected {G3X_TRACE_CAPACITY} (g3x_trace.h:26,57)"
            ),
            fields,
        )

    if res0 != 0 or res1 != 0:
        return (
            MalformedHeaderError(
                f"Non-zero reserved padding at offset 0x{offset:X}: "
                f"reserved=(0x{res0:08X}, 0x{res1:08X}) (g3x_trace.h:30-31)"
            ),
            fields,
        )

    if not _is_header_consistent(write_idx, dropped_count, capacity, mode):
        return (
            MalformedHeaderError(
                f"Inconsistent dropped_count={dropped_count} for write_idx={write_idx}, "
                f"capacity={capacity} at offset 0x{offset:X} (g3x_trace.h:28)"
            ),
            fields,
        )

    return None, fields


def locate_header(
    blob: bytes,
    start_offset: Optional[int] = None,
    mode: Optional[str] = None,
) -> int:
    """Locate the trace header within the byte blob.

    If start_offset is specified, validates that a complete and valid header
    begins at that offset. Otherwise, scans candidate occurrences of signature
    0x43415254 (b"TRAC"), validating every v1 header field (version, record_size,
    capacity, reserved padding, write_idx/dropped_count consistency). If a candidate
    fails validation, scanning continues to the next candidate.

    Returns:
        The byte offset of the valid header.

    Raises:
        BadMagicError: If signature 0x43415254 ('TRAC') is not found, or magic at
                       start_offset does not match.
        TruncatedDataError: If all candidate occurrences are shorter than 32 bytes.
        UnknownVersionError: If no candidate has a valid header and all candidates
                             failed due to unrecognized versions.
        MalformedHeaderError: If a candidate matched magic and version but failed
                              field validation and no valid header was found.
    """
    if start_offset is not None:
        if start_offset < 0:
            raise BadMagicError(f"Invalid negative offset: {start_offset}")
        err, _ = _validate_header_at(blob, start_offset, mode=mode)
        if err is not None:
            raise err
        return start_offset

    # Scanning mode: start_offset is None
    if len(blob) < 4:
        raise BadMagicError("Input data too short to contain trace magic signature (less than 4 bytes)")

    # Find occurrences of b"TRAC"
    candidates: list[int] = []
    pos = 0
    while True:
        idx = blob.find(G3X_TRACE_MAGIC_BYTES, pos)
        if idx == -1:
            break
        candidates.append(idx)
        pos = idx + 1

    if not candidates:
        raise BadMagicError(
            f"Bad trace magic: signature 0x{G3X_TRACE_MAGIC:08X} ('TRAC') not found in input data"
        )

    # Filter candidates that have at least a full header
    full_candidates = [idx for idx in candidates if len(blob) - idx >= G3X_TRACE_HEADER_SIZE]

    if not full_candidates:
        # Every candidate occurrence of 'TRAC' is cut short before a full header
        raise TruncatedDataError(
            f"Truncated header at offset 0x{candidates[0]:X}: {len(blob) - candidates[0]} bytes "
            f"(expected {G3X_TRACE_HEADER_SIZE} bytes)"
        )

    candidate_errors: list[TraceParserError] = []
    for idx in full_candidates:
        err, _ = _validate_header_at(blob, idx, mode=mode)
        if err is None:
            return idx
        candidate_errors.append(err)

    # If no candidate matched all valid header requirements:
    # Prefer MalformedHeaderError (more specific: matched version 1.0 but fields invalid)
    for err in candidate_errors:
        if isinstance(err, MalformedHeaderError):
            raise err

    if candidate_errors:
        raise candidate_errors[0]

    raise BadMagicError("No valid trace header found")


def parse_header(
    blob: bytes,
    offset: int = 0,
    mode: Optional[str] = None,
) -> TraceHeader:
    """Parse and validate a 32-byte trace header from blob at the given offset.

    Validates header fields against specification constants cited from:
    chdk-port/platform/g3x/sub/110c/g3x_trace.h:22-43, 53-61.

    Raises:
        TruncatedDataError: If blob has fewer than 32 bytes from offset.
        BadMagicError: If magic != 0x43415254 (b"TRAC").
        UnknownVersionError: If version != 0x00010000.
        MalformedHeaderError: If record_size, capacity, reserved padding,
                              or write_idx/dropped_count consistency are invalid.
    """
    err, fields = _validate_header_at(blob, offset, mode=mode)
    if err is not None:
        raise err

    assert fields is not None
    magic, version, capacity, write_idx, dropped_count, record_size, res0, res1 = fields

    magic_ascii = struct.pack("<I", magic).decode("ascii", errors="replace")
    version_major = (version >> 16) & 0xFFFF
    version_minor = version & 0xFFFF

    return TraceHeader(
        magic=magic,
        magic_ascii=magic_ascii,
        version=version,
        version_major=version_major,
        version_minor=version_minor,
        capacity=capacity,
        write_idx=write_idx,
        dropped_count=dropped_count,
        record_size=record_size,
        reserved=(res0, res1),
        offset=offset,
    )


def decode_record(
    raw_bytes: bytes,
    index: int = 0,
    seq: int = 0,
    slot: int = 0,
) -> TraceRecord:
    """Decode a single 32-byte trace record.

    Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:34-39, 153-159.
    """
    if len(raw_bytes) < G3X_TRACE_RECORD_SIZE:
        raise TruncatedDataError(
            f"Record data too short: have {len(raw_bytes)} bytes, need {G3X_TRACE_RECORD_SIZE}"
        )

    stage_id, tick, pc_lr_val, text_raw = struct.unpack_from(
        RECORD_STRUCT_FORMAT, raw_bytes, 0
    )

    # ASCII text: null-padded up to 20 bytes (g3x_trace.h:38,56)
    text = text_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
    stage_name = stage_id_to_name(stage_id)
    pc_lr_val_hex = f"0x{pc_lr_val:08x}"

    return TraceRecord(
        index=index,
        seq=seq,
        slot=slot,
        stage_id=stage_id,
        stage_name=stage_name,
        tick=tick,
        pc_lr_val=pc_lr_val,
        pc_lr_val_hex=pc_lr_val_hex,
        text=text,
    )


def parse_trace(
    blob: bytes,
    offset: Optional[int] = None,
    mode: Optional[str] = None,
    all_slots: bool = False,
) -> TraceParseResult:
    """Parse TRACE.LOG or a raw trace ring dump from a byte blob.

    Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:16-44, 141-165.

    Interpretation Modes:
    - 'ring': Fixed-capacity ring buffer dump (g3x_trace_ring_t, 2080 bytes).
      Decodes exactly header_size + capacity * record_size bytes (g3x_trace.h:40,60).
      Any trailing suffix bytes beyond this extent are ignored as dump suffix.
      When wrapped (write_idx > capacity), unwinds records in chronological order
      starting from oldest slot (write_idx % capacity) with sequence (write_idx - capacity) + i.
      When unwrapped (write_idx <= capacity), returns only the valid write_idx records.
    - 'log' (or 'linear'): Append-only TRACE.LOG file (g3x_trace.h:135-136).
      Decodes records sequentially from slot 0.
    - None / 'auto': Auto-detects mode from documented header fields (g3x_trace.h:26-28):
      * If dropped_count > 0 or (write_idx > capacity and dropped_count == write_idx - capacity):
        definitively wrapped ring buffer -> 'ring' mode.
      * If write_idx > capacity and dropped_count == 0:
        definitively append-only log -> 'log' mode.
      * If write_idx <= capacity and dropped_count == 0:
        defaults to 'ring' mode, decoding write_idx valid records within ring extent.

    Args:
        blob: Raw byte buffer containing the trace header and records.
        offset: Explicit byte offset where trace header begins (None for auto-detect).
        mode: Interpretation mode: 'ring', 'log' / 'linear', or None / 'auto'.
        all_slots: If True, decode all ring slots including unwritten padding records.

    Returns:
        TraceParseResult containing the header, decoded records, and status.

    Raises:
        BadMagicError: If header magic is missing or invalid.
        UnknownVersionError: If header version is unknown.
        TruncatedDataError: If header itself is truncated.
        MalformedHeaderError: If header fields (record_size, capacity, reserved padding, dropped_count) are invalid.
    """
    if mode is not None and mode not in ("auto", "ring", "log", "linear"):
        raise ValueError(f"Invalid mode '{mode}'; expected 'auto', 'ring', 'log', or 'linear'")

    mode_filter = "ring" if mode == "ring" else ("log" if mode in ("log", "linear") else None)
    hdr_offset = locate_header(blob, offset, mode=mode_filter)
    header = parse_header(blob, hdr_offset, mode=mode_filter)

    rec_size = header.record_size
    cap = header.capacity
    widx = header.write_idx
    dropped = header.dropped_count

    # Determine effective mode
    if mode in ("ring", "log", "linear"):
        effective_mode = "ring" if mode == "ring" else "log"
    else:
        # Auto-detect from documented header fields (g3x_trace.h:26-28)
        if dropped > 0 or (widx > cap and dropped == widx - cap):
            effective_mode = "ring"
        elif widx > cap and dropped == 0:
            effective_mode = "log"
        elif widx <= cap and dropped == 0:
            effective_mode = "ring"
        else:
            raise MalformedHeaderError(
                f"Inconsistent dropped_count={dropped} for write_idx={widx}, capacity={cap} (g3x_trace.h:28)"
            )

    # Validate header fields specific to mode
    if effective_mode == "ring":
        if widx <= cap:
            if dropped != 0:
                raise MalformedHeaderError(
                    f"Inconsistent dropped_count={dropped} for unwrapped ring with write_idx={widx} "
                    f"(expected 0 per g3x_trace.h:28)"
                )
        else:
            expected_dropped = widx - cap
            if dropped != expected_dropped:
                raise MalformedHeaderError(
                    f"Inconsistent dropped_count={dropped} for wrapped ring with write_idx={widx} "
                    f"(expected {expected_dropped} per g3x_trace.h:28)"
                )
    else:
        # log mode
        if widx > G3X_TRACE_LOG_MAX_RECORDS:
            raise MalformedHeaderError(
                f"Out-of-range write_idx {widx} exceeds max log records {G3X_TRACE_LOG_MAX_RECORDS} (g3x_trace.h:136)"
            )
        if dropped != 0:
            raise MalformedHeaderError(
                f"Inconsistent dropped_count={dropped} in log mode (expected 0 per g3x_trace.h:28)"
            )

    records: List[TraceRecord] = []
    data_start = hdr_offset + G3X_TRACE_HEADER_SIZE

    if effective_mode == "ring":
        # In ring mode, decode exactly header_size + capacity * record_size bytes
        # from hdr_offset and ignore any trailing bytes outside the ring buffer extent.
        # Cited: chdk-port/platform/g3x/sub/110c/g3x_trace.h:40-43, 60.
        ring_max_bytes = cap * rec_size
        ring_data = blob[data_start : data_start + ring_max_bytes]
        available_records = len(ring_data) // rec_size
        trailing_bytes = len(ring_data) % rec_size

        wrapped = (widx > cap)
        if wrapped:
            expected_records = cap
            truncated = (available_records < cap) or (trailing_bytes > 0)
            oldest_slot = widx % cap
            rec_index = 0
            for i in range(cap):
                slot = (oldest_slot + i) % cap
                seq = (widx - cap) + i
                if slot < available_records:
                    rec_raw = ring_data[slot * rec_size : (slot + 1) * rec_size]
                    records.append(decode_record(rec_raw, index=rec_index, seq=seq, slot=slot))
                    rec_index += 1
                else:
                    truncated = True
        else:
            # Unwrapped ring: write_idx <= capacity
            # Clamp write index to capacity
            clamped_widx = min(widx, cap)
            expected_records = clamped_widx
            truncated = (available_records < expected_records) or (trailing_bytes > 0 and available_records < cap)

            if all_slots:
                count_to_read = min(cap, available_records)
            else:
                if widx == 0:
                    # If write_idx == 0, check if any slot has a non-zero stage ID
                    non_zero = [
                        s for s in range(available_records)
                        if struct.unpack_from("<I", ring_data, s * rec_size)[0] != 0
                    ]
                    count_to_read = max(non_zero) + 1 if non_zero else 0
                else:
                    count_to_read = min(clamped_widx, available_records)

            for slot in range(count_to_read):
                rec_raw = ring_data[slot * rec_size : (slot + 1) * rec_size]
                records.append(decode_record(rec_raw, index=slot, seq=slot, slot=slot))

    else:
        # Linear log mode
        log_bytes = blob[data_start:]
        available_records = len(log_bytes) // rec_size
        trailing_bytes = len(log_bytes) % rec_size
        wrapped = False
        expected_records = widx if widx > 0 else available_records
        truncated = (trailing_bytes > 0) or (available_records < expected_records)

        count_to_read = min(available_records, G3X_TRACE_LOG_MAX_RECORDS)
        for i in range(count_to_read):
            rec_raw = log_bytes[i * rec_size : (i + 1) * rec_size]
            records.append(decode_record(rec_raw, index=i, seq=i, slot=i))

    return TraceParseResult(
        header=header,
        records=records,
        wrapped=wrapped,
        truncated=truncated,
        records_decoded=len(records),
        records_expected=expected_records,
        trailing_bytes=trailing_bytes,
        mode=effective_mode,
        total_bytes=len(blob),
    )


# =============================================================================
# Synthetic Packing Helpers
# =============================================================================
def pack_header(
    magic: int = G3X_TRACE_MAGIC,
    version: int = G3X_TRACE_VERSION,
    capacity: int = G3X_TRACE_CAPACITY,
    write_idx: int = 0,
    dropped_count: int = 0,
    record_size: int = G3X_TRACE_RECORD_SIZE,
    reserved: Tuple[int, int] = (0, 0),
) -> bytes:
    """Pack a 32-byte trace header."""
    return struct.pack(
        HEADER_STRUCT_FORMAT,
        magic,
        version,
        capacity,
        write_idx,
        dropped_count,
        record_size,
        reserved[0],
        reserved[1],
    )


def pack_record(
    stage_id: int,
    tick: int = 0,
    pc_lr_val: int = 0,
    text: str = "",
) -> bytes:
    """Pack a 32-byte trace record."""
    text_bytes = text.encode("ascii", errors="replace")[:G3X_TRACE_RECORD_TEXT_LEN]
    text_padded = text_bytes.ljust(G3X_TRACE_RECORD_TEXT_LEN, b"\x00")
    return struct.pack(
        RECORD_STRUCT_FORMAT,
        stage_id,
        tick,
        pc_lr_val,
        text_padded,
    )


# =============================================================================
# CLI Interface
# =============================================================================
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="G3X Lite TRACE.LOG & raw ring dump parser (PORT-17)"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to trace log file or raw memory dump (default: read from stdin)",
    )
    parser.add_argument(
        "-H", "--human", "--table",
        action="store_true",
        dest="table",
        help="Display human-readable table instead of JSON (default is JSON)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Explicitly request JSON output (default)",
    )
    parser.add_argument(
        "-o", "--offset",
        type=lambda x: int(x, 0),
        default=None,
        help="Byte offset of the trace header (default: auto-detect)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "ring", "log", "linear"],
        default="auto",
        help="Interpretation mode: 'ring' (bounded ring buffer), 'log'/'linear' (linear log), or 'auto' (default)",
    )
    parser.add_argument(
        "--all-slots",
        action="store_true",
        help="Decode all ring slots, including empty padding records",
    )

    args = parser.parse_args(argv)

    # Read input data
    if args.file and args.file != "-":
        if not os.path.isfile(args.file):
            sys.stderr.write(f"Error: file not found: {args.file}\n")
            return 1
        with open(args.file, "rb") as f:
            blob = f.read()
    else:
        # Check if stdin has data
        if sys.stdin.isatty():
            sys.stderr.write("Error: no input file specified and stdin is a tty\n")
            parser.print_help(sys.stderr)
            return 1
        blob = sys.stdin.buffer.read()

    try:
        mode_param = None if args.mode == "auto" else args.mode
        result = parse_trace(
            blob,
            offset=args.offset,
            mode=mode_param,
            all_slots=args.all_slots,
        )
    except (BadMagicError, UnknownVersionError, TruncatedDataError, TraceParserError) as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 1

    if args.table:
        print(result.to_table())
    else:
        print(result.to_json())

    return 0


if __name__ == "__main__":
    sys.exit(main())
