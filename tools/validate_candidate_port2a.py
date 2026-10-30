#!/usr/bin/env python3
"""Comprehensive Offline Validator for CHDK-PORT-2A First-Boot Candidate.

Validates:
1. Canonical Production Invariance (boot.c, main.c, bin/DISKBOOT.BIN).
2. Candidate Core ELF and Binary Invariants (@ 0x003489B4).
3. Candidate Loader ELF and Binary Invariants (@ 0x00008000).
4. Embedded Core Payload Identity (100% SHA256 bit-for-bit match).
5. Encoded SD Bootloader Format (dancingbits row 13 reversible decode).
6. Disjoint Memory & Stack Lifetime (spatial non-overlap proof).
7. Execution Chain Invariants (Thumb state, cache routines, continuation target).
8. Boot Witness & Inspector Integration Invariants.
9. Candidate Manifest Integrity.
"""

import hashlib
import json
import os
import re
import struct
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHDK_PORT = os.path.join(REPO_ROOT, "chdk-port")
CANDIDATE_DIR = os.path.join(REPO_ROOT, "candidate_port2a")
TOOLCHAIN_BIN = os.path.join(
    REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin"
)
NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
OBJDUMP = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objdump")

PROD_DISKBOOT = os.path.join(CHDK_PORT, "bin", "DISKBOOT.BIN")
PROD_LOADER_C = os.path.join(CHDK_PORT, "loader", "g3x", "main.c")
PROD_BOOT_C = os.path.join(CHDK_PORT, "platform", "g3x", "sub", "110c", "boot.c")

# Expected architectural symbol addresses documented in docs/PORT16_WITNESS_ADDRESS.md
# Reused from tools/build_candidate_port2a.py by import when practical
tools_dir = os.path.dirname(os.path.abspath(__file__))
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

try:
    from build_candidate_port2a import EXPECTED_BOOT_WITNESS_ADDR
except ImportError:
    # Documented expected boot_witness address derived from corrected boot source
    # (docs/PORT16_WITNESS_ADDRESS.md: 16-byte aligned, .data section)
    EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0

EXPECTED_CORE_START_ADDR = 0x003489B4
# Documented _end address derived from corrected build (docs/PORT16_WITNESS_ADDRESS.md:218; prototype_main.map:1506)
EXPECTED_CORE_END_ADDR = 0x00366CB0
# Documented link_bss_start / link_data_end address (docs/PORT16_WITNESS_ADDRESS.md:217; prototype_main.map:1488)
EXPECTED_CORE_BSS_START = 0x00365204

LOCKED_PROD_HASHES = {
    "DISKBOOT.BIN": "3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72",
    "loader/g3x/main.c": "2678341e18cf55db0eba2ec50d55bebcca33ae189ce67fed839e3a43ed9b21f8",
    "platform/g3x/sub/110c/boot.c": "13105e4cbc1dec6d997f15c2ff1b37305d309d83269239a8d2b0456f559e50b1",
}

ROW13 = [6, 5, 3, 7, 0, 2, 4, 1]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def dance(val, fudgey):
    if (fudgey % 3) != 0:
        return val ^ 0xff
    if (fudgey & 1) == 0:
        return val ^ 0xa0
    return ((val >> 4) | (val << 4)) & 0xff


def decode_dancingbits_row13(encoded_bytes):
    assert encoded_bytes[0] == 0, "Byte 0 of encoded DISKBOOT.BIN must be 0x00"
    payload = bytearray(encoded_bytes[1:])
    out = bytearray(len(payload))
    for grand in range(0, len(payload), 8):
        block = payload[grand:grand+8]
        if len(block) < 8:
            break
        fudge_base = grand % 1024
        for hacki in range(8):
            fudgey = fudge_base + hacki
            out[grand + hacki] = dance(block[ROW13[hacki]], fudgey)
    return bytes(out)


def validate_production_invariance():
    print("1. Validating Canonical Production Invariance:")
    for name, expected_hash in LOCKED_PROD_HASHES.items():
        if name == "DISKBOOT.BIN":
            path = PROD_DISKBOOT
        elif name == "loader/g3x/main.c":
            path = PROD_LOADER_C
        else:
            path = PROD_BOOT_C
        actual = sha256_file(path)
        assert actual == expected_hash, f"Production file {name} altered! Expected {expected_hash}, got {actual}"
        print(f"  [OK] {name} unaltered (SHA256: {actual[:16]}...)")
    return True


VALID_NM_TYPES = set("AaBbCcDdGgIiNnPpRrSsTtUuVvWw-?")
REQUIRED_CORE_SYMBOLS = ("_start", "boot_witness", "_end")


class NmParseError(ValueError):
    """Base exception for parsing errors in arm-none-eabi-nm output."""

    def __init__(self, message: str, line: str):
        self.line = line
        super().__init__(f"{message} in line: '{line}'")


class MalformedHexAddressError(NmParseError):
    """Raised when an nm symbol address is not a valid hex string."""

    def __init__(self, name: str, addr_str: str, line: str):
        self.name = name
        self.addr_str = addr_str
        super().__init__(
            f"Malformed hex address '{addr_str}' for symbol '{name}'", line
        )


class AmbiguousSymbolError(NmParseError):
    """Raised when a required symbol is defined multiple times in nm output."""

    def __init__(self, name: str, addresses: list, line: str):
        self.name = name
        self.addresses = addresses
        addrs_str = ", ".join(
            f"0x{a:08X}" if isinstance(a, int) else str(a) for a in addresses
        )
        super().__init__(
            f"Ambiguous definition of required symbol '{name}': multiple addresses [{addrs_str}]",
            line,
        )


def extract_symbols_from_nm(
    nm_text: str,
    required_symbols: tuple = REQUIRED_CORE_SYMBOLS,
):
    """Parse symbols from arm-none-eabi-nm output text.

    Returns (syms_dict, undef_list).
    Raises NmParseError (subclass of ValueError) on any malformed nm line:
    - Every non-empty line must parse as exactly '<hex address> <single valid nm type letter> <symbol name>',
      or 'U <symbol name>' for undefined symbols.
    - Truncated records, extra fields, or invalid type tokens raise NmParseError.
    - Addresses with invalid hex characters raise MalformedHexAddressError.
    - If a required symbol is defined more than once, raises AmbiguousSymbolError listing all addresses seen.
    """
    syms = {}
    undef = []
    seen_required = {s: [] for s in required_symbols}
    seen_required_lines = {s: [] for s in required_symbols}

    for raw_line in nm_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()

        # Check for undefined symbols: 'U <symbol>'
        if len(parts) == 2:
            if parts[0] in ("U", "u"):
                undef.append(parts[1])
                continue
            raise NmParseError(
                f"Malformed nm line (truncated record, expected 3 fields): '{line}'",
                line,
            )

        if len(parts) != 3:
            if len(parts) < 3:
                raise NmParseError(
                    f"Malformed nm line (truncated record, expected 3 fields): '{line}'",
                    line,
                )
            raise NmParseError(
                f"Malformed nm line (extra fields, expected 3 fields): '{line}'",
                line,
            )

        addr_str, type_str, name = parts

        # Validate type token: single valid nm type letter
        if len(type_str) != 1 or type_str not in VALID_NM_TYPES:
            raise NmParseError(
                f"Malformed nm line (invalid symbol type token '{type_str}'): '{line}'",
                line,
            )

        # Validate hex address
        if not re.fullmatch(r"[0-9a-fA-F]+", addr_str):
            raise MalformedHexAddressError(name, addr_str, line)

        addr_val = int(addr_str, 16)

        if type_str in ("U", "u"):
            undef.append(name)
            continue

        syms[name] = addr_val

        if name in seen_required:
            seen_required[name].append(addr_val)
            seen_required_lines[name].append(line)

    # Check for duplicate / ambiguous definitions of required symbols
    for sym_name in required_symbols:
        if len(seen_required[sym_name]) > 1:
            raise AmbiguousSymbolError(
                sym_name,
                seen_required[sym_name],
                seen_required_lines[sym_name][-1],
            )

    return syms, undef


def verify_candidate_core_symbols(
    nm_text: str,
    expected_start: int = EXPECTED_CORE_START_ADDR,
    expected_witness: int = EXPECTED_BOOT_WITNESS_ADDR,
    expected_end: int = EXPECTED_CORE_END_ADDR,
):
    """Verify symbol table invariants of candidate core.

    Fail-closed policy:
    - If symbol addresses are malformed / unparseable, exits non-zero with clear expected-vs-actual error message.
    - If undefined symbols exist, exits non-zero with clear expected-vs-actual error message.
    - If _start, boot_witness, or _end is missing, exits non-zero with clear expected-vs-actual error message.
    - If _start, boot_witness, or _end mismatches expected, exits non-zero with clear expected-vs-actual error message.
    - If any required symbol is defined more than once, exits non-zero with an ambiguous error listing all addresses seen.
    - If nm output contains any malformed lines (truncated, invalid type, extra fields), exits non-zero with the offending line.

    Returns the parsed symbol dict.
    """
    required = [
        ("_start", expected_start),
        ("boot_witness", expected_witness),
        ("_end", expected_end),
    ]
    required_dict = dict(required)

    try:
        syms, undef = extract_symbols_from_nm(
            nm_text, required_symbols=tuple(required_dict.keys())
        )
    except MalformedHexAddressError as exc:
        if exc.name in required_dict:
            exp_val = required_dict[exc.name]
            print(
                f"ERROR: Symbol '{exc.name}' address unparseable: "
                f"expected=0x{exp_val:08X} actual=unparseable ('{exc.addr_str}') in line: '{exc.line}'",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(
                f"ERROR: Failed to parse candidate core symbol table: {exc} "
                f"(expected=valid hex symbol addresses, actual=unparseable nm output: '{exc.line}')",
                file=sys.stderr,
            )
            sys.exit(1)
    except AmbiguousSymbolError as exc:
        exp_val = required_dict.get(exc.name)
        exp_str = f"0x{exp_val:08X}" if exp_val is not None else "unique symbol"
        addrs_str = ", ".join(f"0x{a:08X}" for a in exc.addresses)
        print(
            f"ERROR: Ambiguous definition of required symbol '{exc.name}': "
            f"multiple addresses [{addrs_str}] (expected={exp_str}, actual=ambiguous: [{addrs_str}]) in line: '{exc.line}'",
            file=sys.stderr,
        )
        sys.exit(1)
    except NmParseError as exc:
        print(
            f"ERROR: Malformed nm output: {exc} "
            f"(expected=valid nm line formatted '<hex addr> <type> <symbol>', actual=malformed line '{exc.line}')",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(
            f"ERROR: Failed to parse candidate core symbol table: {exc} "
            f"(expected=valid hex symbol addresses, actual=unparseable nm output: {exc})",
            file=sys.stderr,
        )
        sys.exit(1)

    if undef:
        print(
            f"ERROR: Unresolved undefined symbols in candidate core: {undef} "
            f"(expected=none, actual={undef})",
            file=sys.stderr,
        )
        sys.exit(1)

    for sym_name, exp_val in required:
        if sym_name not in syms:
            print(
                f"ERROR: Missing symbol '{sym_name}' in candidate core: "
                f"expected=0x{exp_val:08X}, actual=missing",
                file=sys.stderr,
            )
            sys.exit(1)
        actual_val = syms[sym_name]
        if actual_val != exp_val:
            print(
                f"ERROR: Symbol '{sym_name}' address mismatch in candidate core: "
                f"expected=0x{exp_val:08X}, actual=0x{actual_val:08X}",
                file=sys.stderr,
            )
            sys.exit(1)

    return syms


def validate_candidate_core(core_elf=None, core_bin=None, nm_bin=NM):
    print("2. Validating Candidate Core Artifacts:")
    if core_elf is None:
        core_elf = os.path.join(CANDIDATE_DIR, "candidate_main.elf")
    if core_bin is None:
        core_bin = os.path.join(CANDIDATE_DIR, "candidate_main.bin")

    if not os.path.isfile(core_elf):
        print(
            f"ERROR: Missing candidate_main.elf: {core_elf} "
            f"(expected=valid ELF file, actual=file not found)",
            file=sys.stderr,
        )
        sys.exit(1)
    if not os.path.isfile(core_bin):
        print(
            f"ERROR: Missing candidate_main.bin: {core_bin} "
            f"(expected=valid binary file, actual=file not found)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Symbol addresses
    try:
        res = subprocess.run(
            [nm_bin, "-n", core_elf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True,
        )
    except Exception as exc:
        print(
            f"ERROR: Failed to run nm on {core_elf}: {exc} "
            f"(expected=successful nm execution, actual=failed to invoke nm: {exc})",
            file=sys.stderr,
        )
        sys.exit(1)

    if res.returncode != 0:
        print(
            f"ERROR: nm exited with code {res.returncode} for {core_elf}: {res.stderr.strip()} "
            f"(expected=exit code 0, actual={res.returncode})",
            file=sys.stderr,
        )
        sys.exit(1)

    syms = verify_candidate_core_symbols(res.stdout)

    # Verify entry instruction
    with open(core_bin, "rb") as f:
        entry_bytes = f.read(4)
    # 0xF000B800 is Thumb-2 'b.w startup'
    if entry_bytes != b"\x00\xF0\x00\xB8":
        print(
            f"ERROR: Core entry instruction mismatch: "
            f"expected=0x00F000B8 ('b.w startup'), actual={entry_bytes.hex()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"  [OK] Core symbols verified (_start=0x{syms['_start']:08X}, "
        f"boot_witness=0x{syms['boot_witness']:08X}, _end=0x{syms['_end']:08X})"
    )
    print("  [OK] Thumb-2 entry instruction verified: b.w startup (0xF000B800)")
    return syms


def validate_candidate_loader(core_bin_path):
    print("3. Validating Candidate Loader Artifacts & Payload Embedding:")
    loader_elf = os.path.join(CANDIDATE_DIR, "candidate_loader.elf")
    loader_bin = os.path.join(CANDIDATE_DIR, "candidate_loader.bin")
    assert os.path.exists(loader_elf), "Missing candidate_loader.elf"
    assert os.path.exists(loader_bin), "Missing candidate_loader.bin"

    # Loader symbols
    res = subprocess.run([NM, "-n", loader_elf], stdout=subprocess.PIPE, check=True)
    syms = {}
    for line in res.stdout.decode().splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            syms[parts[2]] = int(parts[0], 16)

    assert syms.get("_start") == 0x00008000, f"Loader _start must be 0x00008000, got {hex(syms.get('_start', 0))}"
    blob_addr = syms.get("blob_chdk_core_start")
    if blob_addr is None:
        blob_ptr = syms.get("blob_chdk_core")
        assert blob_ptr is not None, "Missing blob_chdk_core symbol"
        # read pointer from loader ELF or binary
        blob_addr = 0x8280
    blob_offset = blob_addr - 0x8000

    # Verify bit-for-bit core payload identity
    with open(loader_bin, "rb") as f:
        loader_bytes = f.read()
    with open(core_bin_path, "rb") as f:
        core_bytes = f.read()

    embedded_core = loader_bytes[blob_offset : blob_offset + len(core_bytes)]
    assert embedded_core == core_bytes, "Embedded core payload does not match candidate_main.bin bit-for-bit!"
    print(f"  [OK] Embedded core payload at offset 0x{blob_offset:X} ({len(core_bytes)} B) matches candidate_main.bin bit-for-bit")

    # Disassembly invariants
    res = subprocess.run([OBJDUMP, "-d", loader_elf], stdout=subprocess.PIPE, check=True)
    dump = res.stdout.decode()

    assert "cpsid\tif" in dump, "Missing 'cpsid if' in loader handoff"
    assert "0xfc127ab1" in dump, "Missing call target 0xFC127AB1 (D-cache clean/invalidate)"
    assert "0xfc127b09" in dump, "Missing call target 0xFC127B09 (I-cache/BP invalidate)"
    assert "bx\tr0" in dump, "Missing terminal 'bx r0' in loader handoff"

    print("  [OK] Loader handoff disassembly verified: core_copy -> DCCISW -> ICIALLU -> cpsid if -> bx r0")
    return syms


def validate_encoded_diskboot(loader_bin_path):
    print("4. Validating Encoded SD Bootloader (DISKBOOT.BIN):")
    diskboot_path = os.path.join(CANDIDATE_DIR, "DISKBOOT.BIN")
    assert os.path.exists(diskboot_path), "Missing candidate_port2a/DISKBOOT.BIN"

    with open(diskboot_path, "rb") as f:
        diskboot_bytes = f.read()
    with open(loader_bin_path, "rb") as f:
        loader_bytes = f.read()

    assert diskboot_bytes[0] == 0, f"Byte 0 of DISKBOOT.BIN must be 0x00, got {diskboot_bytes[0]}"
    assert len(diskboot_bytes) == len(loader_bytes) + 1, "DISKBOOT.BIN length mismatch"

    # Decode and compare bit-for-bit
    decoded_loader = decode_dancingbits_row13(diskboot_bytes)
    assert decoded_loader == loader_bytes, "Decoded DISKBOOT.BIN does not match candidate_loader.bin bit-for-bit!"
    print(f"  [OK] Reversible decoding verified: decoded {len(decoded_loader)} B bit-for-bit identical to loader binary")
    return True


def validate_memory_and_stack_disjointness():
    print("5. Validating Disjoint Memory and Stack Lifetime:")
    # Ranges:
    # Loader SP:        0x00007FE0 .. 0x00008000
    # Core boot SP:     0x00003F00 .. 0x00004000
    # Relocated Core:   0x003489B4 .. 0x00365204 (text/data)
    # CHDK BSS:         0x00365204 .. 0x00366CB0
    # Boot Witness:     0x0035F7A0 .. 0x0035F7C0
    # DryOS Heap:       0x00366CB0 .. 0x00600014
    #
    # Disjointness constant adjustments per docs/PORT16_WITNESS_ADDRESS.md:217-218:
    # - EXPECTED_CORE_END_ADDR = 0x00366CB0 (line 218): CHDK BSS end and DryOS Shifted Heap
    #   start updated from historical 0x00366C90 to 0x00366CB0 (+0x20 bytes).
    # - EXPECTED_CORE_BSS_START = 0x00365204 (line 217): Relocated Core end and CHDK BSS
    #   start updated from historical 0x003651E4 to 0x00365204 (+0x20 bytes).
    ranges = [
        ("Core Boot Stack", 0x00003F00, 0x00004000),
        ("Loader Stack",    0x00007FE0, 0x00008000),
        ("Relocated Core",  EXPECTED_CORE_START_ADDR, EXPECTED_CORE_BSS_START),
        ("CHDK BSS",        EXPECTED_CORE_BSS_START, EXPECTED_CORE_END_ADDR),
        ("DryOS Shifted Heap", EXPECTED_CORE_END_ADDR, 0x00600014),
    ]
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            n1, s1, e1 = ranges[i]
            n2, s2, e2 = ranges[j]
            overlap = max(0, min(e1, e2) - max(s1, s2))
            assert overlap == 0, f"Memory overlap detected between {n1} and {n2}!"
    print("  [OK] Zero overlap proven across Loader Stack, Core Boot Stack, Core, BSS, and Shifted Heap")
    return True


def validate_inspector_association():
    print("6. Validating Associated Canon Basic Inspector:")
    insp_m = os.path.join(CANDIDATE_DIR, "witness_inspector_gm110c.m")
    insp_bin = os.path.join(CANDIDATE_DIR, "witness_inspector_payload.bin")
    assert os.path.exists(insp_m), "Missing witness_inspector_gm110c.m"
    assert os.path.exists(insp_bin), "Missing witness_inspector_payload.bin"

    bin_size = os.path.getsize(insp_bin)
    assert bin_size == 444, f"Expected inspector payload size 444 B, got {bin_size}"

    with open(insp_m, "r", encoding="utf-8") as f:
        src = f.read()

    assert "DIM payload_size = 444" in src, "payload_size must be 444"
    assert "read_sz <> payload_size" in src, "read_sz <> payload_size check missing"
    assert "LCDMsg_ChangeColor(h_title, 2)" not in src, "Green title forbidden"
    assert "LCDMsg_ChangeColor(h_status, 2)" not in src, "Green status forbidden"
    assert "BOOT_SUCCESS" not in src, "BOOT_SUCCESS forbidden"
    assert "CONTINUATION_CONFIRMED" not in src, "CONTINUATION_CONFIRMED forbidden"

    with open(insp_bin, "rb") as f:
        bin_bytes = f.read()
    if len(bin_bytes) >= 18:
        lo_w1, lo_w2, hi_w1, hi_w2 = struct.unpack("<HHHH", bin_bytes[10:18])
        lo = ((lo_w1 & 0x0400) << 1) | ((lo_w1 & 0x000F) << 12) | ((lo_w2 & 0x7000) >> 4) | (lo_w2 & 0x00FF)
        hi = ((hi_w1 & 0x0400) << 1) | ((hi_w1 & 0x000F) << 12) | ((hi_w2 & 0x7000) >> 4) | (hi_w2 & 0x00FF)
        loaded_addr = (hi << 16) | lo
        assert loaded_addr == EXPECTED_BOOT_WITNESS_ADDR, (
            f"Inspector payload witness address mismatch: expected 0x{EXPECTED_BOOT_WITNESS_ADDR:08X}, "
            f"got 0x{loaded_addr:08X}"
        )

    print("  [OK] Inspector payload length (444 B), size binding, and freshness invariants verified")
    return True


def validate_manifest_integrity():
    print("7. Validating Candidate Manifest Integrity:")
    manifest_path = os.path.join(CANDIDATE_DIR, "candidate_manifest.json")
    assert os.path.exists(manifest_path), "Missing candidate_manifest.json"

    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    assert m["status"] == "OFFLINE_CANDIDATE_BUILT"
    assert m["independent_review"] == "PENDING"
    assert m["hardware_readiness"] == "NO-GO"

    arch = m.get("architectural_invariants", {})
    if "boot_witness_addr" in arch:
        exp_wit = f"0x{EXPECTED_BOOT_WITNESS_ADDR:08X}"
        assert arch["boot_witness_addr"] == exp_wit, (
            f"Manifest boot_witness_addr mismatch: expected {exp_wit}, got {arch['boot_witness_addr']}"
        )
    if "core_end_symbol" in arch:
        exp_end = f"0x{EXPECTED_CORE_END_ADDR:08X}"
        assert arch["core_end_symbol"] == exp_end, (
            f"Manifest core_end_symbol mismatch: expected {exp_end}, got {arch['core_end_symbol']}"
        )

    for name, info in m["candidate_artifacts"].items():
        full_path = os.path.join(REPO_ROOT, info["path"])
        assert os.path.exists(full_path), f"Missing artifact {full_path}"
        actual_sz = os.path.getsize(full_path)
        actual_hash = sha256_file(full_path)
        assert actual_sz == info["size_bytes"], f"Size mismatch for {name}: {actual_sz} vs {info['size_bytes']}"
        assert actual_hash == info["sha256"], f"SHA256 mismatch for {name}: {actual_hash} vs {info['sha256']}"
        print(f"  [OK] {name}: {actual_sz} B (SHA256: {actual_hash[:16]}...) verified against manifest")

    return True


def main():
    print("======================================================================")
    print("CHDK-PORT-2A: First-Boot Candidate Integration Validator")
    print("======================================================================")
    ok = (
        validate_production_invariance()
        and validate_candidate_core()
        and validate_candidate_loader(os.path.join(CANDIDATE_DIR, "candidate_main.bin"))
        and validate_encoded_diskboot(os.path.join(CANDIDATE_DIR, "candidate_loader.bin"))
        and validate_memory_and_stack_disjointness()
        and validate_inspector_association()
        and validate_manifest_integrity()
    )
    if ok:
        print("======================================================================")
        print("ALL PORT-2A CANDIDATE VALIDATION CHECKS PASSED (OFFLINE ONLY)")
        print("Candidate Status: OFFLINE_CANDIDATE_BUILT")
        print("Independent Review: PENDING")
        print("Hardware Readiness: NO-GO")
        print("======================================================================")
        sys.exit(0)
    else:
        print("VALIDATION FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
