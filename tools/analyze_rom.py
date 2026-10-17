#!/usr/bin/env python3
"""Read-only structural inventory for a flat Canon firmware ROM image.

The script uses only Python's standard library, never opens the input writable,
and emits JSON to stdout. It intentionally does not disassemble or infer
function boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mmap
import os
import struct
import sys
from collections import Counter
from pathlib import Path


DEFAULT_BASE = 0xFC000000
DEFAULT_BLOCK_SIZE = 0x10000
DEFAULT_MIN_RUN = 0x1000


def entropy(data: bytes | mmap.mmap) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def uniform_runs(data: mmap.mmap, minimum: int) -> list[dict[str, int | str]]:
    runs: list[dict[str, int | str]] = []
    start = 0
    size = len(data)
    while start < size:
        value = data[start]
        end = start + 1
        while end < size and data[end] == value:
            end += 1
        if end - start >= minimum:
            runs.append({"offset": start, "length": end - start, "byte": f"0x{value:02x}"})
        start = end
    return runs


def ascii_hits(data: mmap.mmap, needles: list[bytes]) -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    for needle in needles:
        offsets: list[int] = []
        pos = data.find(needle)
        while pos >= 0:
            offsets.append(pos)
            pos = data.find(needle, pos + 1)
        hits[needle.decode("ascii")] = offsets
    return hits


def pointer_stats(block: bytes, base: int, image_size: int) -> dict[str, int]:
    aligned = len(block) - (len(block) % 4)
    values = struct.unpack(f"<{aligned // 4}I", block[:aligned]) if aligned else ()
    rom = sum(base <= value < base + image_size for value in values)
    thumb_rom = sum(base <= (value & ~1) < base + image_size and value & 1 for value in values)
    low_ram = sum(0x1000 <= value < 0x10000000 for value in values)
    return {"rom_words": rom, "thumb_rom_words": thumb_rom, "low_ram_words": low_ram}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=DEFAULT_BASE)
    parser.add_argument("--block-size", type=lambda value: int(value, 0), default=DEFAULT_BLOCK_SIZE)
    parser.add_argument("--minimum-run", type=lambda value: int(value, 0), default=DEFAULT_MIN_RUN)
    parser.add_argument("--expect-size", type=lambda value: int(value, 0))
    parser.add_argument("--expect-sha256")
    args = parser.parse_args()

    if args.block_size <= 0 or args.minimum_run <= 0:
        parser.error("block size and minimum run must be positive")

    before = args.image.stat()
    digest = hashlib.sha256()
    with args.image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()

    errors: list[str] = []
    if args.expect_size is not None and before.st_size != args.expect_size:
        errors.append(f"size mismatch: expected {args.expect_size}, got {before.st_size}")
    if args.expect_sha256 is not None and sha256.lower() != args.expect_sha256.lower():
        errors.append(f"SHA-256 mismatch: expected {args.expect_sha256.lower()}, got {sha256}")

    needles = [
        b"gaonisoy",
        b"GM1.10C",
        b"Firmware Ver GM1.10C",
        b"DRYOS version 2.3, release #0057",
        b"Canon PowerShot G3 X",
    ]
    blocks: list[dict[str, object]] = []
    whole_counts: Counter[int] = Counter()
    with args.image.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as image:
            hits = ascii_hits(image, needles)
            runs = uniform_runs(image, args.minimum_run)
            for offset in range(0, len(image), args.block_size):
                block = image[offset : offset + args.block_size]
                whole_counts.update(block)
                blocks.append(
                    {
                        "offset": offset,
                        "address": args.base + offset,
                        "length": len(block),
                        "entropy_bits_per_byte": round(entropy(block), 6),
                        "counts": {
                            "zero": block.count(0),
                            "ff": block.count(0xFF),
                            "printable_ascii": sum(0x20 <= byte <= 0x7E for byte in block),
                        },
                        "word_candidates": pointer_stats(block, args.base, len(image)),
                    }
                )

    after = args.image.stat()
    metadata_unchanged = (
        before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ino == after.st_ino
    )
    result = {
        "tool": "tools/analyze_rom.py",
        "analysis_scope": "read-only structural inventory; no disassembly or function inference",
        "image": str(args.image),
        "base_address": args.base,
        "size": before.st_size,
        "sha256": sha256,
        "whole_image_entropy_bits_per_byte": round(
            -sum(
                (count / before.st_size) * math.log2(count / before.st_size)
                for count in whole_counts.values()
            ),
            6,
        ),
        "block_size": args.block_size,
        "blocks": blocks,
        "uniform_runs": runs,
        "ascii_hits": hits,
        "metadata_unchanged_during_analysis": metadata_unchanged,
        "validation_errors": errors,
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 1 if errors or not metadata_unchanged else 0


if __name__ == "__main__":
    raise SystemExit(main())
