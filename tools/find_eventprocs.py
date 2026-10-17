#!/usr/bin/env python3
"""Find candidate Canon event-procedure table entries in a flat ROM.

The scanner recognizes adjacent 32-bit words where one points to a printable,
NUL-terminated ASCII name in the ROM and the other is an in-ROM Thumb pointer.
It is intentionally structural: a match is a table candidate, not proof of a
function's semantics. The ROM is opened read-only and JSON is written to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import re
import struct
import sys
from pathlib import Path


DEFAULT_BASE = 0xFC000000
DEFAULT_PATTERN = (
    r"(?i)(AF|focus|shutter|exposure|iris|aperture|NDFilter|zoom|lens|movie|video|"
    r"CaptSeq|ExpDrv|FileWrite|InitFile|CreateTask|EventProc|MFOn|MFOff)"
)


def read_ascii(image: mmap.mmap, offset: int, minimum: int, maximum: int) -> str | None:
    if offset < 0 or offset >= len(image):
        return None
    end = image.find(b"\0", offset, min(len(image), offset + maximum + 1))
    if end < 0 or not minimum <= end - offset <= maximum:
        return None
    raw = image[offset:end]
    if not raw or any(byte < 0x20 or byte > 0x7E for byte in raw):
        return None
    return raw.decode("ascii")


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def first_thumb_bl_target(image: mmap.mmap, address: int, base: int, limit: int = 16) -> int | None:
    """Decode the first Thumb-2 BL immediate near a candidate entry point."""
    offset = (address & ~1) - base
    if offset < 0 or offset + 4 > len(image):
        return None
    for relative in range(0, min(limit, len(image) - offset - 3), 2):
        first, second = struct.unpack_from("<HH", image, offset + relative)
        if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
            continue
        s = (first >> 10) & 1
        j1 = (second >> 13) & 1
        j2 = (second >> 11) & 1
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        immediate = (
            (s << 24)
            | (i1 << 23)
            | (i2 << 22)
            | ((first & 0x03FF) << 12)
            | ((second & 0x07FF) << 1)
        )
        instruction_address = (address & ~1) + relative
        return ((instruction_address + 4 + sign_extend(immediate, 25)) & 0xFFFFFFFF) | 1
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=DEFAULT_BASE)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="regular expression applied to names")
    parser.add_argument("--expect-sha256")
    parser.add_argument("--minimum-name", type=int, default=3)
    parser.add_argument("--maximum-name", type=int, default=96)
    args = parser.parse_args()

    if args.minimum_name < 1 or args.maximum_name < args.minimum_name:
        parser.error("invalid name-length limits")
    try:
        name_pattern = re.compile(args.pattern)
    except re.error as error:
        parser.error(f"invalid pattern: {error}")

    digest = hashlib.sha256()
    with args.image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    if args.expect_sha256 and sha256.lower() != args.expect_sha256.lower():
        print("input SHA-256 mismatch", file=sys.stderr)
        return 1

    before = args.image.stat()
    matches: list[dict[str, int | str]] = []
    seen: set[tuple[int, int, str]] = set()
    with args.image.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as image:
            end_address = args.base + len(image)
            for offset in range(0, len(image) - 7, 4):
                first, second = struct.unpack_from("<II", image, offset)
                for function, name_pointer, order in (
                    (first, second, "function,name"),
                    (second, first, "name,function"),
                ):
                    if not (function & 1 and args.base <= (function & ~1) < end_address):
                        continue
                    if not (args.base <= name_pointer < end_address):
                        continue
                    name = read_ascii(
                        image,
                        name_pointer - args.base,
                        args.minimum_name,
                        args.maximum_name,
                    )
                    if name is None or name_pattern.search(name) is None:
                        continue
                    key = (offset, function, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    call_target = first_thumb_bl_target(image, function, args.base)
                    matches.append(
                        {
                            "table_address": args.base + offset,
                            "table_file_offset": offset,
                            "order": order,
                            "name": name,
                            "name_address": name_pointer,
                            "function_address": function,
                            "instruction_state": "Thumb (bit 0 set)",
                            "first_thumb_bl_target": call_target,
                        }
                    )

    after = args.image.stat()
    result = {
        "tool": "tools/find_eventprocs.py",
        "scope": "structural candidates only; names and function semantics require disassembly review",
        "image": str(args.image),
        "base_address": args.base,
        "sha256": sha256,
        "pattern": args.pattern,
        "metadata_unchanged_during_analysis": (
            before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
        ),
        "match_count": len(matches),
        "matches": matches,
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["metadata_unchanged_during_analysis"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
