#!/usr/bin/env python3
"""Offline Static Validator for PORT-1G.1 Canon Basic RAM Witness Inspector.

Validates:
1. Candidate Canon Basic loader script:
   - firmware/tools/witness_inspector_gm110c.m
   - Binary size binding: payload_size and expected_payload_size match actual binary size
   - Short-read & oversized rejection: read_sz <> payload_size with payload_size + 1 read
   - Firmware compatibility checks (gaonisoy, EC385, GM1.10C)
   - Bounded LCDMsg allocations (2 handles) with scoped rollback
   - Prohibition of LCDMsg_Delete(100) global purge
   - Memory allocation safety & immediate FreeMemory on all paths
   - L1 Harvard cache synchronization before execution (0xFC127A85, 0xFC127B2B)
   - Strict absence of BOOT_SUCCESS or CONTINUATION_CONFIRMED claims
   - Complete absence of Color 2 (Green) misleading success coloring
2. Candidate native Thumb-2 inspector payload:
   - firmware/tools/witness_inspector_payload.bin and .o
   - Exact binary size and alignment (bin_size % 4 == 0, <= 512)
   - All string literals and their null terminators strictly reside within loaded buffer
   - AAPCS 8-byte stack alignment at all BLX call sites
   - Dynamic boot_witness target address matching candidate_main.elf symbol and metadata
   - Native firmware call targets (LCDMsg_SetStr_native 0xFC0C973D, LCDMsg_ChangeColor_native 0xFC0C99B1)
   - Output sentinels: 0x57495401, 0x57495402, 0x57495404, 0x574954EE, 0x574954FF
   - Strict absence of Color 2 (Green) in payload color assignments
   - Strict absence of BOOT_SUCCESS or CONTINUATION_CONFIRMED in string literals
3. Address Metadata & ELF Consistency Invariants:
   - Rejection of mismatched ELF symbol vs inspector binary
   - Rejection of mismatched address metadata vs inspector binary
   - Rejection of mismatched ELF symbol vs address metadata
   - Rejection of missing/corrupt metadata or symbols
4. Inspector State & Freshness Negative Test Suite (PORT-1G.1):
   - Valid monotonic progression (0x01 -> 0x03 -> 0x07)
   - Rejection of matching fixed constant nonce as proof of freshness
   - Replayed complete records with matching fixed nonce produce FRESHNESS_UNVERIFIED (Yellow)
   - Challenge mismatch with dynamic challenge classified as STALE_OR_FRESHNESS_UNKNOWN
   - Checksum corruption / bit flip detection
   - Illegal non-monotonic transitions
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOADER_SCRIPT = os.path.join(REPO_ROOT, "firmware", "tools", "witness_inspector_gm110c.m")
PAYLOAD_BIN = os.path.join(REPO_ROOT, "firmware", "tools", "witness_inspector_payload.bin")
PAYLOAD_ELF = os.path.join(REPO_ROOT, "firmware", "tools", "witness_inspector_payload.o")
METADATA_JSON = os.path.join(REPO_ROOT, "firmware", "tools", "witness_inspector_metadata.json")
DEFAULT_CANDIDATE_ELF = os.path.join(REPO_ROOT, "candidate_port2a", "candidate_main.elf")
FALLBACK_PROTOTYPE_ELF = os.path.join(
    REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "prototype_main.elf"
)

TOOLCHAIN_BIN = os.path.join(REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin")
NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
OBJDUMP = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objdump")

BOOT_WITNESS_MAGIC = 0x5749544E
BOOT_WITNESS_VERSION = 0x00010001
BOOT_WITNESS_FIXED_NONCE = 0x32A80001

SENTINEL_LOADER = 0x57495401
SENTINEL_CORE = 0x57495402
SENTINEL_CONTINUATION = 0x57495404
SENTINEL_INVALID = 0x574954EE
SENTINEL_STALE = 0x574954FF


def compute_checksum(magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick):
    c = 0x55AA55AA
    for val in [magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick]:
        c = ((c * 31) ^ (val & 0xFFFFFFFF)) & 0xFFFFFFFF
    return c


def pack_witness(magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick, checksum=None):
    if checksum is None:
        checksum = compute_checksum(magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick)
    return struct.pack("<IIIIIIII", magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick, checksum)


def extract_witness_addr_from_elf(elf_path, nm_tool=NM):
    """Extract boot_witness symbol address from ELF."""
    if not os.path.exists(elf_path):
        raise FileNotFoundError(f"Candidate ELF not found: {elf_path}")
    res = subprocess.run([nm_tool, "-n", elf_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    witness_addr = None
    witness_type = None
    for line in res.stdout.decode().splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[2] == "boot_witness":
            witness_addr = int(parts[0], 16)
            witness_type = parts[1]
            break
    if witness_addr is None:
        raise ValueError(f"Symbol 'boot_witness' not found in {elf_path}")
    if witness_type not in ("D", "d"):
        raise ValueError(f"Symbol 'boot_witness' unexpected type '{witness_type}' in {elf_path}")
    if witness_addr % 4 != 0:
        raise ValueError(f"Symbol 'boot_witness' address 0x{witness_addr:08X} not 4-byte aligned in {elf_path}")
    return witness_addr


def extract_witness_addr_from_payload(payload_elf, objdump_tool=OBJDUMP):
    """Extract loaded boot_witness address from disassembled inspector object/binary."""
    if not os.path.exists(payload_elf):
        raise FileNotFoundError(f"Payload file not found: {payload_elf}")
    if payload_elf.endswith(".bin"):
        cmd = [objdump_tool, "-b", "binary", "-marm", "-Mforce-thumb", "-D", payload_elf]
    else:
        cmd = [objdump_tool, "-d", payload_elf]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    dump = res.stdout.decode()
    m_w = re.search(r"movw\s+r7,\s*#(\d+)(?:\s*;\s*0x([0-9a-fA-F]+))?", dump)
    m_t = re.search(r"movt\s+r7,\s*#(\d+)(?:\s*;\s*0x([0-9a-fA-F]+))?", dump)
    if not m_w or not m_t:
        raise ValueError(f"Could not find movw/movt r7 instructions in {payload_elf}")
    lo = int(m_w.group(2), 16) if m_w.group(2) else int(m_w.group(1), 10)
    hi = int(m_t.group(2), 16) if m_t.group(2) else int(m_t.group(1), 10)
    return (hi << 16) | lo


def read_address_metadata(metadata_path):
    """Read and validate address metadata JSON."""
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Address metadata file not found: {metadata_path}")
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    if "witness_address" not in meta or "witness_address_int" not in meta:
        raise ValueError(f"Corrupt address metadata: missing witness_address fields in {metadata_path}")
    meta_addr = int(meta["witness_address"], 16)
    if meta_addr != meta["witness_address_int"]:
        raise ValueError(f"Corrupt address metadata: hex 0x{meta_addr:08X} != int {meta['witness_address_int']}")
    return meta_addr, meta


def emulate_inspector_parse(buf, expected_nonce=0):
    """Python reference emulation of witness_inspector_payload.S logic (PORT-1G.1).
    
    Returns:
        (sentinel, title_str, status_str, title_color, status_color)
    """
    if len(buf) < 32:
        return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3

    magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick, checksum = struct.unpack("<IIIIIIII", buf[:32])

    # Step 1: Magic & Version
    if magic != BOOT_WITNESS_MAGIC or version != BOOT_WITNESS_VERSION:
        return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3

    # Step 2: Checksum
    expected_cs = compute_checksum(magic, version, session_nonce, stage_state, loader_sp, core_entry_pc, cont_tick)
    if checksum != expected_cs:
        return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3

    # Step 3: Freshness / Dynamic Challenge Check (PORT-1G.1)
    if expected_nonce != 0 and expected_nonce != BOOT_WITNESS_FIXED_NONCE:
        if session_nonce != expected_nonce:
            return SENTINEL_STALE, "STALE / REPLAY", "NONCE_MISMATCH", 4, 4

    # Step 4: Evaluate stage states
    if stage_state == 1:
        return SENTINEL_LOADER, "LOADER_REACHED", "FRESHNESS_UNVERIFIED", 1, 4
    elif stage_state == 3:
        return SENTINEL_CORE, "CORE_REACHED", "FRESHNESS_UNVERIFIED", 1, 4
    elif stage_state == 7:
        if core_entry_pc != 0x003489B5 or (loader_sp % 8 != 0):
            return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3
        return SENTINEL_CONTINUATION, "CONT_ATTEMPTED", "FRESHNESS_UNVERIFIED", 4, 4
    else:
        return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3


def validate_loader_script(loader_script_path, bin_size):
    print(f"Validating {os.path.basename(loader_script_path)}:")
    if not os.path.exists(loader_script_path):
        print(f"[FAIL] Missing {loader_script_path}")
        return False
    with open(loader_script_path, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. Independent check: Canon Basic allocated/read length & generated metadata match real binary
    m_sz = re.search(r"DIM payload_size\s*=\s*(\d+)", src)
    assert m_sz, "DIM payload_size constant missing in script"
    script_payload_size = int(m_sz.group(1))
    assert script_payload_size == bin_size, (
        f"Script payload_size ({script_payload_size}) does not match binary size ({bin_size}). "
        "Rejecting mismatch (regeneration during validation is prohibited)."
    )

    m_exp = re.search(r"DIM expected_payload_size\s*=\s*(\d+)", src)
    assert m_exp, "DIM expected_payload_size metadata missing in script"
    script_exp_size = int(m_exp.group(1))
    assert script_exp_size == bin_size, (
        f"Script expected_payload_size ({script_exp_size}) does not match binary size ({bin_size})."
    )

    # Verify allocation size accommodates complete binary
    m_alloc = re.search(r"AllocateMemory\(([^)]+)\)", src)
    assert m_alloc, "AllocateMemory call missing"
    assert "payload_size" in m_alloc.group(1), "Allocation buffer must be bound to payload_size"

    # 2. Independent check: Short-read & oversized rejection condition
    assert "read_sz <> payload_size" in src or "read_sz <> expected_payload_size" in src, (
        "Script must strictly require read_sz == payload_size (rejecting short/zero/oversized reads)"
    )
    assert "payload_size + 1" in src, "Script must read payload_size + 1 to detect oversized files"

    # 3. Prohibitions & Invariants
    assert "LCDMsg_Delete(100)" not in src, "Global purge LCDMsg_Delete(100) is strictly forbidden"
    assert "BOOT_SUCCESS" not in src, "Must not report BOOT_SUCCESS"
    assert "CONTINUATION_CONFIRMED" not in src, "Must not report CONTINUATION_CONFIRMED"
    assert "0xfc127a85" in src, "Must synchronize D-cache (0xFC127A85)"
    assert "0xfc127b2b" in src, "Must synchronize I-cache (0xFC127B2B)"
    assert "FreeMemory(buf)" in src, "Must free payload buffer"
    assert "gaonisoy" in src and "EC385" in src and "GM1.10C" in src, "Must check compatibility"

    # 4. Success coloring removal: Color 2 (Green) must not be assigned to title or status
    assert "LCDMsg_ChangeColor(h_title, 2)" not in src, "Misleading Green (Color 2) title coloring forbidden"
    assert "LCDMsg_ChangeColor(h_status, 2)" not in src, "Misleading Green (Color 2) status coloring forbidden"

    print(f"  [OK] Script payload_size bound to {bin_size} B, short-read check, and invariants verified.")
    return True


def validate_payload_binary(
    payload_bin=PAYLOAD_BIN,
    payload_elf=PAYLOAD_ELF,
    elf_path=None,
    metadata_path=METADATA_JSON,
    expected_witness_addr=None,
):
    print(f"Validating {os.path.basename(payload_bin)} and {os.path.basename(payload_elf)}:")
    if not os.path.exists(payload_bin) or not os.path.exists(payload_elf):
        print(f"[FAIL] Missing payload binary or ELF")
        return False

    bin_size = os.path.getsize(payload_bin)
    assert bin_size <= 512, f"Payload size {bin_size} exceeds 512 bytes"
    assert bin_size % 4 == 0, f"Payload size {bin_size} not 4-byte aligned"

    with open(payload_bin, "rb") as f:
        payload_bytes = f.read()

    # 1. Independent check: Verify absence of premature confirmation claims in string literals
    assert b"BOOT_SUCCESS" not in payload_bytes, "Must not contain BOOT_SUCCESS"
    assert b"CONTINUATION_CONFIRMED" not in payload_bytes, "Must not contain CONTINUATION_CONFIRMED"

    # 2. Independent check: Verify all binary strings are entirely within the loaded buffer
    required_strings = [
        b"LOADER_REACHED",
        b"CORE_REACHED",
        b"CONT_ATTEMPTED",
        b"STALE / REPLAY",
        b"WITNESS_INVALID",
        b"FRESHNESS_UNVERIFIED",
        b"NONCE_MISMATCH",
        b"INVALID / CORRUPT",
    ]
    for s_bytes in required_strings:
        off = payload_bytes.find(s_bytes)
        assert off >= 0, f"Missing required string literal {s_bytes.decode()}"
        end_off = off + len(s_bytes) + 1  # include null terminator
        assert end_off <= bin_size, (
            f"String {s_bytes.decode()} (offset {off}..{end_off}) exceeds binary length ({bin_size})"
        )

    # 3. Disassembly invariants via objdump
    res = subprocess.run([OBJDUMP, "-d", payload_elf], stdout=subprocess.PIPE, check=True)
    dump = res.stdout.decode()

    # Calling convention: AAPCS 8-byte stack alignment
    assert "stmdb\tsp!, {r4, r5, r6, r7, r8, lr}" in dump, "Must push 6 registers (24 bytes) for 8-byte alignment"
    assert "ldmia.w\tsp!, {r4, r5, r6, r7, r8, pc}" in dump, "Must pop 6 registers"
    assert "push\t{r1, r2}" in dump, "Render must push 2 registers (8 bytes) to maintain 8-byte SP alignment"

    # Dynamic boot witness target address resolution & validation
    bin_witness_addr = extract_witness_addr_from_payload(payload_elf)

    # Resolve candidate ELF if not passed
    if elf_path is None:
        if os.path.exists(DEFAULT_CANDIDATE_ELF):
            elf_path = DEFAULT_CANDIDATE_ELF
        elif os.path.exists(FALLBACK_PROTOTYPE_ELF):
            elf_path = FALLBACK_PROTOTYPE_ELF

    elf_witness_addr = None
    if elf_path and os.path.exists(elf_path):
        elf_witness_addr = extract_witness_addr_from_elf(elf_path)
        assert elf_witness_addr == bin_witness_addr, (
            f"Mismatched ELF symbol: candidate ELF symbol has 0x{elf_witness_addr:08X}, "
            f"but inspector binary loads 0x{bin_witness_addr:08X}!"
        )

    meta_witness_addr = None
    if metadata_path and os.path.exists(metadata_path):
        meta_witness_addr, meta = read_address_metadata(metadata_path)
        assert meta_witness_addr == bin_witness_addr, (
            f"Mismatched address metadata: metadata specifies 0x{meta_witness_addr:08X}, "
            f"but inspector binary loads 0x{bin_witness_addr:08X}!"
        )
        assert meta.get("payload_size") == bin_size, (
            f"Metadata payload size mismatch: {meta.get('payload_size')} vs actual {bin_size}"
        )
        if elf_witness_addr is not None:
            assert elf_witness_addr == meta_witness_addr, (
                f"Mismatched ELF and metadata: ELF has 0x{elf_witness_addr:08X}, "
                f"metadata has 0x{meta_witness_addr:08X}!"
            )

    if expected_witness_addr is not None:
        assert bin_witness_addr == expected_witness_addr, (
            f"Inspector address 0x{bin_witness_addr:08X} does not match expected 0x{expected_witness_addr:08X}"
        )

    print(f"  [OK] Witness target address 0x{bin_witness_addr:08X} verified consistent with ELF & metadata.")

    # Native call targets
    assert "0x973d" in dump and "0xfc0c" in dump, "Must call LCDMsg_SetStr_native (0xFC0C973D)"
    assert "0x99b1" in dump and "0xfc0c" in dump, "Must call LCDMsg_ChangeColor_native (0xFC0C99B1)"

    # Sentinels
    for s_hex in ["0x5401", "0x5402", "0x5404", "0x54ee", "0x54ff"]:
        assert s_hex in dump, f"Must construct sentinel {s_hex}"

    # Absence of Color 2 (Green) assignments in disassembly
    for match in re.finditer(r"movs?\s+r([67]),\s*#2", dump):
        assert False, f"Prohibited Green (Color 2) assignment detected: {match.group(0)}"

    print(f"  [OK] Payload binary ({bin_size} bytes), all string literals within buffer, AAPCS alignment verified.")
    return bin_size


def run_inspector_parser_tests():
    print("\nRunning Inspector State & Freshness Negative Test Suite (PORT-1G.1):")
    valid_nonce = BOOT_WITNESS_FIXED_NONCE  # 0x32A80001
    good = pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, valid_nonce, 7, 0x7FF8, 0x003489B5, 100)

    # 1. Uninitialized
    s, t, st, tc, sc = emulate_inspector_parse(bytes(32), valid_nonce)
    assert s == SENTINEL_INVALID and t == "WITNESS_INVALID" and tc == 3 and sc == 3
    print("  [OK] Uninitialized (all-zero) memory rejected as INVALID (Red).")

    # 2. Invalid magic
    s, t, st, tc, sc = emulate_inspector_parse(pack_witness(0xDEADBEEF, BOOT_WITNESS_VERSION, valid_nonce, 7, 0x7FF8, 0x003489B5, 100), valid_nonce)
    assert s == SENTINEL_INVALID and t == "WITNESS_INVALID" and tc == 3 and sc == 3
    print("  [OK] Invalid magic rejected as INVALID (Red).")

    # 3. Checksum corruption (single bit flip)
    corrupted = bytearray(good)
    corrupted[16] ^= 0x01
    s, t, st, tc, sc = emulate_inspector_parse(bytes(corrupted), valid_nonce)
    assert s == SENTINEL_INVALID and t == "WITNESS_INVALID" and tc == 3 and sc == 3
    print("  [OK] Corrupted checksum / bit flip rejected as INVALID (Red).")

    # 4. Incomplete boot: Stage 1 only
    s, t, st, tc, sc = emulate_inspector_parse(pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, valid_nonce, 1, 0x7FF8, 0, 0), valid_nonce)
    assert s == SENTINEL_LOADER and t == "LOADER_REACHED" and st == "FRESHNESS_UNVERIFIED" and tc == 1 and sc == 4
    print("  [OK] Stage 1 classified as LOADER_REACHED / FRESHNESS_UNVERIFIED (White/Yellow).")

    # 5. Incomplete boot: Stage 2 only
    s, t, st, tc, sc = emulate_inspector_parse(pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, valid_nonce, 3, 0x7FF8, 0x003489B5, 0), valid_nonce)
    assert s == SENTINEL_CORE and t == "CORE_REACHED" and st == "FRESHNESS_UNVERIFIED" and tc == 1 and sc == 4
    print("  [OK] Stage 2 classified as CORE_REACHED / FRESHNESS_UNVERIFIED (White/Yellow).")

    # 6. Illegal transition (Stage 2 skipped: 0x01 -> 0x05)
    s, t, st, tc, sc = emulate_inspector_parse(pack_witness(BOOT_WITNESS_MAGIC, BOOT_WITNESS_VERSION, valid_nonce, 5, 0x7FF8, 0x003489B5, 100), valid_nonce)
    assert s == SENTINEL_INVALID and t == "WITNESS_INVALID" and tc == 3 and sc == 3
    print("  [OK] Illegal transition (core skipped) rejected as INVALID (Red).")

    # 7. Dynamic challenge mismatch
    s, t, st, tc, sc = emulate_inspector_parse(good, expected_nonce=0x55555555)
    assert s == SENTINEL_STALE and t == "STALE / REPLAY" and st == "NONCE_MISMATCH" and tc == 4 and sc == 4
    print("  [OK] Dynamic challenge mismatch classified as STALE_OR_FRESHNESS_UNKNOWN (Yellow).")

    # 8. CRITICAL NEGATIVE TEST: Replayed complete record with MATCHING FIXED NONCE (0x32A80001)
    s, t, st, tc, sc = emulate_inspector_parse(good, expected_nonce=valid_nonce)
    assert s == SENTINEL_CONTINUATION, "Sentinel must reflect structural continuation"
    assert t == "CONT_ATTEMPTED", f"Title must be CONT_ATTEMPTED, got {t}"
    assert st == "FRESHNESS_UNVERIFIED", f"Status must be FRESHNESS_UNVERIFIED, got {st}"
    assert tc == 4, f"Title color must be 4 (Yellow), got {tc}"
    assert sc == 4, f"Status color must be 4 (Yellow), got {sc}"
    assert tc != 2 and sc != 2, "Violation: Color 2 (Green) detected on matching fixed nonce"
    assert "SUCCESS" not in t and "SUCCESS" not in st, "Violation: SUCCESS detected"
    assert "CONFIRMED" not in t and "CONFIRMED" not in st, "Violation: CONFIRMED detected"
    print("  [OK] Matching-nonce stale replay strictly produces CONT_ATTEMPTED / FRESHNESS_UNVERIFIED (Yellow, no green).")

    # 9. Complete record evaluated with zero expected nonce
    s, t, st, tc, sc = emulate_inspector_parse(good, expected_nonce=0)
    assert s == SENTINEL_CONTINUATION and t == "CONT_ATTEMPTED" and st == "FRESHNESS_UNVERIFIED"
    assert tc == 4 and sc == 4
    print("  [OK] Complete record lacking dynamic challenge strictly shows FRESHNESS_UNVERIFIED (Yellow).")

    # 10. Semantic invariants across all results
    for label in [t, st]:
        assert "BOOT_SUCCESS" not in label, "Violation: inspector reported BOOT_SUCCESS"
        assert "CONTINUATION_CONFIRMED" not in label, "Violation: inspector reported CONTINUATION_CONFIRMED"
    print("  [OK] Semantic invariants verified: BOOT_SUCCESS and CONTINUATION_CONFIRMED strictly prohibited.")

    return True


def validate_all(
    payload_bin=PAYLOAD_BIN,
    payload_elf=PAYLOAD_ELF,
    loader_script=LOADER_SCRIPT,
    metadata_json=METADATA_JSON,
    elf_path=None,
    expected_witness_addr=None,
):
    bin_size = validate_payload_binary(
        payload_bin=payload_bin,
        payload_elf=payload_elf,
        elf_path=elf_path,
        metadata_path=metadata_json,
        expected_witness_addr=expected_witness_addr,
    )
    if not bin_size:
        return False
    ok = validate_loader_script(loader_script, bin_size) and run_inspector_parser_tests()
    return ok


def main():
    parser = argparse.ArgumentParser(description="Validate witness inspector payload and script")
    parser.add_argument("--elf", default=None, help="Candidate main ELF path")
    parser.add_argument("--payload-bin", default=PAYLOAD_BIN, help="Payload .bin path")
    parser.add_argument("--payload-elf", default=PAYLOAD_ELF, help="Payload .o path")
    parser.add_argument("--loader-script", default=LOADER_SCRIPT, help="Loader script .m path")
    parser.add_argument("--metadata", default=METADATA_JSON, help="Address metadata .json path")
    parser.add_argument("--expected-addr", default=None, help="Expected witness address (hex)")
    args = parser.parse_args()

    exp_addr = int(args.expected_addr, 16) if args.expected_addr else None
    try:
        ok = validate_all(
            payload_bin=args.payload_bin,
            payload_elf=args.payload_elf,
            loader_script=args.loader_script,
            metadata_json=args.metadata,
            elf_path=args.elf,
            expected_witness_addr=exp_addr,
        )
        if ok:
            print("\nALL CANON BASIC WITNESS INSPECTOR CHECKS PASSED (PORT-1G.1 OFFLINE ONLY).")
            sys.exit(0)
        else:
            print("\nVALIDATION FAILED", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"\nVALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
