#!/usr/bin/env python3
"""Static validator for G3X Lite HDMI-001 GM1.10C Clean Overlay script and ROM invariants.

A PASS means only that the script text and ROM bytes match the reviewed static
model. It is not evidence of runtime safety or of Clean HDMI working on hardware.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ROM_SIZE = 0x02000000
EXPECTED_ROM_SHA256 = "9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578"
ROM_BASE = 0xFC000000

FORBIDDEN_ADDRESSES = {
    0xFC000584: "GM1.10E/M100 model string offset (wrong on GM1.10C)",
    0xFC54E0B5: "GM1.10E version string offset (wrong on GM1.10C)",
    0xD20B0884: "GPIO LED register (not part of HDMI-001)",
    0xD20B0810: "GPIO AF LED register (not part of HDMI-001)",
    0xD20B0994: "Reference-port GPIO register (not verified on G3 X)",
}

# Every hex literal in the script must be one of these reviewed values.
ALLOWED_LITERALS = {
    0x00015DA4: "palette_control (SCM.c base, dirty byte)",
    0x00015DB0: "palette_init_flag (+0x0C)",
    0x00015DB4: "active palette index (+0x10), read-only diagnostic",
    0x00015DBC: "palette_buffer_ptr (+0x18)",
    0x001231B8: "PaletteClass* array (0x00123140 + 0x78)",
    0xFC77B62C: "'Palette Class.' magic",
    0xFC77C8B0: "ROM default Palette 0 payload",
    0x00001000: "fail-closed lower bound for heap object pointer",
    0x10000000: "fail-closed upper bound for heap object pointer",
    0xFC020004: "'gaonisoy' guard",
    0xFC00052C: "'EC385\\n\\r' guard",
    0xFC54E08D: "'GM1.10C' guard",
}

# Functions that write camera RAM, and how many call sites are permitted.
WRITE_CALL_LIMITS = {"memset": 1, "memcpy": 1, "Poke8": 2, "Poke16": 0, "Poke32": 0, "strcpy": 0}

REQUIRED_GUARDS = [
    'memcmp(0xfc020004, "gaonisoy", 8) <> 0',
    'strcmp("EC385\\n\\r", 0xfc00052c) <> 0',
    'strcmp("GM1.10C", 0xfc54e08d) <> 0',
    "if *palette_init_flag <> 1 then",
    "if tbl <> expected_table_addr then",
    "if slot = 0 then",
    "if slot < slot_min then",
    "if slot >= slot_max then",
    "if *slot <> expected_magic then",
]

REQUIRED_OPERATIONS = [
    "memset(payload, 0, 1024)",
    "memcpy(payload, rom_default_pal0, 1024)",
    "Poke8(palette_control, 3)",
]

REQUIRED_DIMS = {
    "palette_control": 0x00015DA4,
    "palette_init_flag": 0x00015DB0,
    "active_palette_index": 0x00015DB4,
    "palette_buffer_ptr": 0x00015DBC,
    "expected_table_addr": 0x001231B8,
    "expected_magic": 0xFC77B62C,
    "rom_default_pal0": 0xFC77C8B0,
    "slot_min": 0x00001000,
    "slot_max": 0x10000000,
    "palette_to_zero": 0,
}


def u32(rom: bytes, addr: int) -> int:
    return struct.unpack_from("<I", rom, addr - ROM_BASE)[0]


def rb(rom: bytes, addr: int, n: int) -> bytes:
    return rom[addr - ROM_BASE : addr - ROM_BASE + n]


def rom_checks(data: bytes) -> dict:
    return {
        # Identity guards used by the script
        "gaonisoy_0xfc020004": rb(data, 0xFC020004, 8) == b"gaonisoy",
        "ec385_0xfc00052c": rb(data, 0xFC00052C, 8) == b"EC385\n\r\x00",
        "gm110c_0xfc54e08d": rb(data, 0xFC54E08D, 8) == b"GM1.10C\x00",
        # SCM.c state block
        "scm_palette_control_lit_0xfc33d500": u32(data, 0xFC33D500) == 0x00015DA4,
        "scm_palette_control_lit_0xfc33d618": u32(data, 0xFC33D618) == 0x00015DA4,
        "scm_table_base_lit_0xfc33d508": u32(data, 0xFC33D508) == 0x00123140,
        "scm_init_sets_flag_plus0c_0xfc33d260": rb(data, 0xFC33D25E, 4) == bytes.fromhex("0121d160"),
        "scm_init_adds_0x78_str_plus18_0xfc33d264": rb(data, 0xFC33D264, 4) == bytes.fromhex("78319161"),
        "getactive_reads_index_plus10_0xfc33d132": rb(data, 0xFC33D132, 2) == bytes.fromhex("2c69"),
        "getactive_reads_tbl_plus18_0xfc33d14a": rb(data, 0xFC33D14A, 6) == bytes.fromhex("a86950f82400"),
        "getactive_offset_flags_all_zero_0xfc77c8a8": rb(data, 0xFC77C8A8, 4) == b"\x00\x00\x00\x00",
        # Dirty byte: only bits 0/1 are used; push clears whole byte
        "push_tests_dirty_byte_0xfc33d2f4": rb(data, 0xFC33D2F4, 2) == bytes.fromhex("2078"),
        "push_clears_dirty_byte_0xfc33d30c": rb(data, 0xFC33D30A, 4) == bytes.fromhex("00202070"),
        "setactive_ors_3_0xfc33d2aa": rb(data, 0xFC33D2AA, 4) == bytes.fromhex("40f00300"),
        # PaletteClass object layout
        "palette_class_alloc_0x408_0xfc19d82c": rb(data, 0xFC19D82C, 4) == bytes.fromhex("40f20840"),
        "palette_class_copy_0x404_0xfc19d846": rb(data, 0xFC19D846, 4) == bytes.fromhex("40f20442"),
        "palette_class_entry_index_max_0x100_0xfc19d866": rb(data, 0xFC19D866, 4) == bytes.fromhex("b5f5807f"),
        "palette_class_magic_lit_0xfc19d908": u32(data, 0xFC19D908) == 0xFC77B62C,
        "palette_class_string_0xfc77b62c": rb(data, 0xFC77B62C, 15) == b"Palette Class.\x00",
        # ROM default palette 0
        "rom_default_pal_base_lit_0xfc33d61c": u32(data, 0xFC33D61C) == 0xFC77C8AC,
        "rom_default_pal0_entry0_transparent": u32(data, 0xFC77C8B0) == 0x00800080,
        "rom_default_pal0_entry1_white": u32(data, 0xFC77C8B4) == 0xFFFFFFFF,
        "rom_default_pal0_entries1_3_nonzero": all(u32(data, 0xFC77C8B0 + 4 * i) != 0 for i in (1, 2, 3)),
        # Entry 256 (+0x404) is real palette data, not a zero footer; script leaves it untouched
        "rom_default_pal0_entry256_nonzero": u32(data, 0xFC77C8B0 + 0x400) != 0,
        # Canon Basic System eventprocs used by the script (pointer precedes name)
        "evp_poke8_is_strb": u32(data, 0xFC557D94) == 0xFC557801 and rb(data, 0xFC602428, 4) == bytes.fromhex("01707047"),
        "evp_memset_name": rb(data, 0xFC557AAC, 7) == b"memset\x00" and u32(data, 0xFC557AA8) == 0xFC5591C9,
        "evp_memcpy_name": rb(data, 0xFC557AA0, 7) == b"memcpy\x00" and u32(data, 0xFC557A9C) == 0xFC13D68D,
        "evp_strcmp_impl": rb(data, 0xFC557A88, 7) == b"strcmp\x00" and u32(data, 0xFC557A84) == 0xFC382A19,
    }


def validate_rom_invariants(rom_path: Path) -> dict:
    errors = []
    if not rom_path.is_file():
        return {"rom_path": str(rom_path), "errors": [f"ROM not found: {rom_path}"], "invariants": {}}
    data = rom_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_ROM_SIZE:
        errors.append(f"ROM size mismatch: {len(data)} != {EXPECTED_ROM_SIZE}")
        return {"rom_path": str(rom_path), "rom_size": len(data), "rom_sha256": sha256, "invariants": {}, "errors": errors}
    if sha256 != EXPECTED_ROM_SHA256:
        errors.append(f"ROM SHA-256 mismatch: {sha256} != {EXPECTED_ROM_SHA256}")
    checks = rom_checks(data)
    for name, ok in checks.items():
        if not ok:
            errors.append(f"Failed ROM invariant: {name}")
    return {"rom_path": str(rom_path), "rom_size": len(data), "rom_sha256": sha256, "invariants": checks, "errors": errors}


def _code_lines(text: str):
    """Yield (line_no, code) with Canon Basic ' comments stripped (outside strings)."""
    for idx, line in enumerate(text.splitlines(), 1):
        out, in_str = [], False
        for ch in line:
            if ch == '"':
                in_str = not in_str
            if ch == "'" and not in_str:
                break
            out.append(ch)
        yield idx, "".join(out).strip()


def validate_script_text(raw: bytes, label: str = "<script>") -> dict:
    sha256 = hashlib.sha256(raw).hexdigest()
    errors = []

    if b"\r" in raw:
        errors.append("Script contains CR bytes; must use LF line endings only")
    non_ascii = [i for i, b in enumerate(raw) if b > 0x7F]
    if non_ascii:
        errors.append(f"Script contains non-ASCII bytes at offsets: {non_ascii[:10]}")

    text = raw.decode("ascii", errors="replace")
    code = list(_code_lines(text))
    code_text = "\n".join(c for _, c in code)

    # Block balance
    sub_stack = if_stack = 0
    for idx, c in code:
        low = c.lower()
        if not low:
            continue
        if re.match(r"^(private|public)\s+sub\s+\w+", low):
            sub_stack += 1
        elif low == "end sub":
            sub_stack -= 1
            if sub_stack < 0:
                errors.append(f"Line {idx}: unmatched 'end sub'")
        elif low.startswith("if ") and low.endswith(" then"):
            if_stack += 1
        elif low == "end if":
            if_stack -= 1
            if if_stack < 0:
                errors.append(f"Line {idx}: unmatched 'end if'")
    if sub_stack != 0:
        errors.append(f"Unbalanced sub blocks: remaining={sub_stack}")
    if if_stack != 0:
        errors.append(f"Unbalanced if blocks: remaining={if_stack}")

    # Literal allowlist / denylist
    hex_literals = [int(m.group(0), 16) for m in re.finditer(r"0x[0-9a-fA-F]+", code_text)]
    for addr in hex_literals:
        if addr in FORBIDDEN_ADDRESSES:
            errors.append(f"Forbidden address 0x{addr:08X}: {FORBIDDEN_ADDRESSES[addr]}")
        elif addr not in ALLOWED_LITERALS:
            errors.append(f"Unreviewed hex literal 0x{addr:08X}")

    # DIM values must match the reviewed model exactly
    for name, value in REQUIRED_DIMS.items():
        m = re.search(rf"^DIM\s+{name}\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*$", code_text, re.M)
        if not m:
            errors.append(f"Missing DIM {name}")
        elif int(m.group(1), 0) != value:
            errors.append(f"DIM {name} = {m.group(1)} (expected 0x{value:08X})")
    for name in REQUIRED_DIMS:
        if len(re.findall(rf"^\s*{name}\s*=", code_text, re.M)) > 0:
            errors.append(f"Constant {name} is reassigned after DIM")

    # Required guards and operations
    for snippet in REQUIRED_GUARDS + REQUIRED_OPERATIONS:
        if snippet not in code_text:
            errors.append(f"Missing required guard/operation snippet: {snippet}")

    # RAM-write call budget
    for fn, limit in WRITE_CALL_LIMITS.items():
        n = len(re.findall(rf"\b{fn}\s*\(", code_text))
        if n > limit:
            errors.append(f"{fn} called {n} times (limit {limit})")

    # Ordering: every guard inside toggle_palette must precede the first RAM write
    m = re.search(r"private sub toggle_palette\(\)(.*?)end sub", code_text, re.S | re.I)
    if not m:
        errors.append("toggle_palette() not found")
    else:
        body = m.group(1)
        writes = [body.find(w) for w in ("memset(", "memcpy(", "Poke8(") if body.find(w) >= 0]
        first_write = min(writes) if writes else -1
        for g in REQUIRED_GUARDS[3:]:
            pos = body.find(g)
            if pos < 0 or (first_write >= 0 and pos > first_write):
                errors.append(f"Guard not before first RAM write in toggle_palette: {g}")
    # RAM writes must not appear outside toggle_palette
    outside = code_text.replace(m.group(0), "") if m else code_text
    for fn in ("memset(", "memcpy(", "Poke8(", "Poke16(", "Poke32("):
        if fn in outside:
            errors.append(f"RAM write {fn} outside toggle_palette")

    # toggle_palette must only run after check_compat() succeeded
    init = re.search(r"private sub Initialize\(\)(.*?)end sub", code_text, re.S | re.I)
    if not init:
        errors.append("Initialize() not found")
    else:
        ib = init.group(1)
        if not re.search(r"if compat = 0 then.*?else.*?toggle_palette\(\)", ib, re.S):
            errors.append("toggle_palette() is not gated by check_compat()")

    return {
        "script_path": label,
        "script_size": len(raw),
        "script_lines": len(text.splitlines()),
        "script_sha256": sha256,
        "hex_literals": sorted({f"0x{x:08x}" for x in hex_literals}),
        "errors": errors,
    }


def validate_script(script_path: Path) -> dict:
    if not script_path.is_file():
        return {"script_path": str(script_path), "errors": [f"Script not found: {script_path}"]}
    return validate_script_text(script_path.read_bytes(), str(script_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=REPO_ROOT / "firmware/dumps/GM1.10C/PRIMARY.BIN")
    parser.add_argument("--script", type=Path, default=REPO_ROOT / "firmware/tools/hdmi001_clean_overlay_gm110c.m")
    args = parser.parse_args()

    rom_report = validate_rom_invariants(args.rom)
    script_report = validate_script(args.script)
    all_errors = rom_report["errors"] + script_report["errors"]
    report = {"status": "PASS" if not all_errors else "FAIL", "rom": rom_report, "script": script_report}
    print(json.dumps(report, indent=2))
    return 0 if not all_errors else 1


if __name__ == "__main__":
    sys.exit(main())
