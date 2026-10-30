#!/usr/bin/env python3
"""Build script for CHDK-PORT-2A First-Boot Candidate.

Creates an isolated, non-deployable candidate build in `candidate_port2a/`:
1. Candidate relocated core: candidate_main.elf, candidate_main.bin (@ 0x003489B4)
2. Candidate loader: candidate_loader.elf, candidate_loader.bin (@ 0x8000)
3. Encoded bootloader: DISKBOOT.BIN (encoded via dancingbits row 13)
4. Associated Canon Basic inspector: witness_inspector_gm110c.m, witness_inspector_payload.bin
5. Locked manifest: candidate_manifest.json

Strictly preserves canonical production artifacts:
- loader/g3x/main.c
- platform/g3x/sub/110c/boot.c
- canonical bin/DISKBOOT.BIN

Target: Canon PowerShot G3 X (GM1.10C)
Toolchain: ARM GNU-RM 5.4.1 (2016q3)
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

# Ensure TMPDIR points to a valid writable directory (fallback to /dev/shm if /tmp is unavailable)
if "TMPDIR" not in os.environ or not os.path.isdir(os.environ.get("TMPDIR", "")):
    if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
        os.environ["TMPDIR"] = "/dev/shm"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHDK_PORT = os.path.join(REPO_ROOT, "chdk-port")
TOOLCHAIN_BIN = os.path.join(
    REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin"
)
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc")
AR = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-ar")
NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
SIZE = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-size")
OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy")
OBJDUMP = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objdump")

DANCINGBITS = os.path.join(CHDK_PORT, "tools", "dancingbits")

CANDIDATE_DIR = os.path.join(REPO_ROOT, "candidate_port2a")
SUB_DIR = os.path.join(CHDK_PORT, "platform", "g3x", "sub", "110c")
LOADER_DIR = os.path.join(CHDK_PORT, "loader", "g3x")
FIRMWARE_TOOLS = os.path.join(REPO_ROOT, "firmware", "tools")

PROD_DISKBOOT = os.path.join(CHDK_PORT, "bin", "DISKBOOT.BIN")
PROD_LOADER_C = os.path.join(LOADER_DIR, "main.c")
PROD_BOOT_C = os.path.join(SUB_DIR, "boot.c")

# Documented expected boot_witness address derived from corrected boot source
# (docs/PORT16_WITNESS_ADDRESS.md: 16-byte aligned, .data section)
EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0


def extract_symbol_addr_from_nm(nm_text: str, sym_name: str) -> int:
    """Parse symbol address from arm-none-eabi-nm output text.

    Returns the integer address of the symbol.
    Raises ValueError if symbol is missing or address is not a valid hex integer.
    """
    for line in nm_text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[2] == sym_name:
            try:
                return int(parts[0], 16)
            except ValueError as err:
                raise ValueError(
                    f"Malformed hex address '{parts[0]}' for {sym_name} in nm output"
                ) from err
    raise ValueError(f"{sym_name} symbol not found in nm output")


def extract_witness_addr_from_nm(nm_text: str) -> int:
    """Parse boot_witness symbol address from arm-none-eabi-nm output text."""
    return extract_symbol_addr_from_nm(nm_text, "boot_witness")


def verify_witness_addr_from_elf(
    elf_path: str,
    expected_addr: int = EXPECTED_BOOT_WITNESS_ADDR,
    nm_bin: str = NM,
) -> int:
    """Extract and verify boot_witness symbol address from the built ELF symbol table.

    Fail-closed policy:
    - If nm execution fails or ELF cannot be read, exits non-zero.
    - If boot_witness symbol is missing, exits non-zero with clear error.
    - If nm output cannot be parsed, exits non-zero with clear error.
    - If boot_witness address mismatches expected_addr, exits non-zero
      with clear expected-vs-actual error message.

    Returns the verified integer address.
    """
    if not os.path.isfile(elf_path):
        print(f"ERROR: ELF file not found: {elf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        proc = subprocess.run(
            [nm_bin, "-n", elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as exc:
        print(
            f"ERROR: Failed to run nm ({nm_bin}) on {elf_path}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if proc.returncode != 0:
        print(
            f"ERROR: nm exited with code {proc.returncode} for {elf_path}:\n{proc.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(proc.returncode if proc.returncode != 0 else 1)

    try:
        witness_addr = extract_witness_addr_from_nm(proc.stdout)
    except ValueError as exc:
        print(
            f"ERROR: Failed to resolve boot_witness from {elf_path} symbol table: {exc} "
            f"(expected 0x{expected_addr:08X})",
            file=sys.stderr,
        )
        sys.exit(1)

    if witness_addr != expected_addr:
        print(
            f"ERROR: boot_witness symbol address mismatch in {elf_path}: "
            f"expected 0x{expected_addr:08X}, got 0x{witness_addr:08X}",
            file=sys.stderr,
        )
        sys.exit(1)

    return witness_addr


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd, cwd=CHDK_PORT):
    env = dict(os.environ)
    if "TMPDIR" not in env or not os.path.isdir(env.get("TMPDIR", "")):
        if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
            env["TMPDIR"] = "/dev/shm"
    res = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"FAILED: {' '.join(cmd)}", file=sys.stderr)
        print(res.stderr.decode(), file=sys.stderr)
        sys.exit(res.returncode)
    return res.stdout.decode()


def build_candidate_core():
    print("--- Building Candidate Core (@ 0x003489B4) ---")
    boot_proto_c = os.path.join(SUB_DIR, "boot_prototype.c")
    stubs_proto_s = os.path.join(SUB_DIR, "stubs_prototype.S")
    boot_proto_o = os.path.join(CANDIDATE_DIR, "boot_prototype.o")
    stubs_proto_o = os.path.join(CANDIDATE_DIR, "stubs_prototype.o")
    lib_proto_a = os.path.join(CANDIDATE_DIR, "libplatformsub_candidate.a")
    core_elf = os.path.join(CANDIDATE_DIR, "candidate_main.elf")
    core_bin = os.path.join(CANDIDATE_DIR, "candidate_main.bin")

    # 1. Compile boot_prototype.c
    cflags = [
        CC,
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Imodules",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-DMEMISOSIZE=(&_end-&_start)",
        "-DCAM_DIGIC=60",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_ARAM_MALLOC",
        "-DARAM_HEAP_START=0x006ce000",
        "-DARAM_HEAP_SIZE=0x00022000",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-nostdinc",
        "-c",
        "-o",
        boot_proto_o,
        boot_proto_c,
    ]
    run_cmd(cflags)

    # 2. Compile stubs_prototype.S
    sflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-c",
        "-o",
        stubs_proto_o,
        stubs_proto_s,
    ]
    run_cmd(sflags)

    # 3. Create candidate sub platform archive
    obj_files = [
        boot_proto_o,
        stubs_proto_o,
        os.path.join(SUB_DIR, "stubs_min.o"),
        os.path.join(SUB_DIR, "stubs_entry.o"),
        os.path.join(SUB_DIR, "stubs_entry_2.o"),
        os.path.join(SUB_DIR, "capt_seq.o"),
        os.path.join(SUB_DIR, "movie_rec.o"),
        os.path.join(SUB_DIR, "filewrite.o"),
        os.path.join(SUB_DIR, "main.thm.o"),
        os.path.join(SUB_DIR, "gui_draw.thm.o"),
        os.path.join(SUB_DIR, "memmgmt.thm.o"),
        os.path.join(SUB_DIR, "gui.thm.o"),
        os.path.join(SUB_DIR, "kbd_process.thm.o"),
        os.path.join(SUB_DIR, "kbd_common.thm.o"),
        os.path.join(SUB_DIR, "conf.thm.o"),
        os.path.join(SUB_DIR, "gui_osd.thm.o"),
        os.path.join(SUB_DIR, "raw.thm.o"),
        os.path.join(SUB_DIR, "usb_sync.thm.o"),
        os.path.join(SUB_DIR, "shooting.thm.o"),
        os.path.join(SUB_DIR, "camera_info.thm.o"),
        os.path.join(SUB_DIR, "remotecap.thm.o"),
        os.path.join(SUB_DIR, "lib_thumb.thm.o"),
        os.path.join(SUB_DIR, "lang_str.thm.o"),
        os.path.join(SUB_DIR, "ptp.thm.o"),
    ]
    run_cmd([AR, "cr", lib_proto_a] + obj_files)

    # 4. Link candidate_main.elf
    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        "-Wl,-T,tools/link-boot.ld",
        "-Wl,-N,-Ttext,0x3489b4",
        "-o",
        core_elf,
        "-Wl,--start-group",
        os.path.join(SUB_DIR, "entry.o"),
        os.path.join(CHDK_PORT, "platform", "g3x", "libplatform.a"),
        lib_proto_a,
        os.path.join(CHDK_PORT, "lib", "font", ".o2", "libfont.a"),
        os.path.join(CHDK_PORT, "lib", "math", ".o2", "libmath.a"),
        os.path.join(CHDK_PORT, "lib", "lang", ".o2", "liblang.a"),
        os.path.join(CHDK_PORT, "lib", "armutil", ".o2", "libarmutil.a"),
        os.path.join(CHDK_PORT, "lib", "core", ".o2", "libcore.a"),
        "-lgcc",
        "-Wl,--end-group",
    ]
    run_cmd(ld_cmd)

    # 5. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", core_elf, core_bin])
    print(f"  [OK] candidate_main.bin generated ({os.path.getsize(core_bin)} B)")
    return core_elf, core_bin


def build_candidate_loader(core_elf, core_bin):
    print("--- Building Candidate Loader (@ 0x00008000) ---")
    loader_c = os.path.join(LOADER_DIR, "main_prototype.c")
    loader_entry_o = os.path.join(LOADER_DIR, "entry.o")
    blobs_s = os.path.join(LOADER_DIR, "blobs.S")

    loader_o = os.path.join(CANDIDATE_DIR, "main_prototype.o")
    blobs_o = os.path.join(CANDIDATE_DIR, "blobs_candidate.o")
    loader_elf = os.path.join(CANDIDATE_DIR, "candidate_loader.elf")
    loader_bin = os.path.join(CANDIDATE_DIR, "candidate_loader.bin")

    # Discover and verify boot_witness symbol address from the build's own symbol table
    witness_addr = verify_witness_addr_from_elf(core_elf, EXPECTED_BOOT_WITNESS_ADDR)
    print(
        f"  [OK] boot_witness confirmed at 0x{witness_addr:08X} "
        f"(matches expected 0x{EXPECTED_BOOT_WITNESS_ADDR:08X})"
    )

    # 1. Compile loader
    cflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-I../../include",
        "-I../../core",
        "-I../../modules",
        "-I../../platform/g3x",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-I.",
        "-I../../platform/g3x/sub/110c",
        f'-DCORE_FILE="{core_bin}"',
        f"-DBOOT_WITNESS_ADDR=0x{witness_addr:08x}",
        "-nostdinc",
        "-c",
        "-o",
        loader_o,
        loader_c,
    ]
    run_cmd(cflags, cwd=LOADER_DIR)

    # 2. Assemble blobs
    bflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-nostdinc",
        f'-DCORE_FILE="{core_bin}"',
        "-c",
        "-o",
        blobs_o,
        blobs_s,
    ]
    run_cmd(bflags, cwd=LOADER_DIR)

    # 3. Link candidate_loader.elf
    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        "-Wl,--no-define-common,-EL,-T,../../tools/link-boot.ld",
        "-Wl,-N,-Ttext,0x8000",
        "-o",
        loader_elf,
        loader_entry_o,
        loader_o,
        blobs_o,
    ]
    run_cmd(ld_cmd, cwd=LOADER_DIR)

    # 4. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", loader_elf, loader_bin])
    print(f"  [OK] candidate_loader.bin generated ({os.path.getsize(loader_bin)} B)")

    try:
        nm_out = run_cmd([NM, "-n", core_elf])
        core_end_addr = extract_symbol_addr_from_nm(nm_out, "_end")
    except Exception:
        core_end_addr = 0x00366CB0

    return loader_elf, loader_bin, witness_addr, core_end_addr


ROW13 = [6, 5, 3, 7, 0, 2, 4, 1]


def _dance(val, fudgey):
    if (fudgey % 3) != 0:
        return val ^ 0xff
    if (fudgey & 1) == 0:
        return val ^ 0xa0
    return ((val >> 4) | (val << 4)) & 0xff


def encode_dancingbits_row13(in_bytes: bytes) -> bytes:
    out = bytearray(b"\x00")
    for grand in range(0, len(in_bytes), 8):
        block = in_bytes[grand : grand + 8]
        fudge_base = grand % 1024
        fe50 = bytearray(8)
        for hacki in range(len(block)):
            fe50[ROW13[hacki]] = _dance(block[hacki], fudge_base + hacki)
        out.extend(fe50[: len(block)])
    return bytes(out)


def encode_candidate_diskboot(loader_bin):
    print("--- Encoding Candidate DISKBOOT.BIN (dancingbits row 13) ---")
    diskboot_out = os.path.join(CANDIDATE_DIR, "DISKBOOT.BIN")
    encoded = None
    if os.path.exists(DANCINGBITS):
        try:
            res = subprocess.run(
                [DANCINGBITS, loader_bin, diskboot_out, "13"],
                cwd=CHDK_PORT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if res.returncode == 0 and os.path.exists(diskboot_out):
                with open(diskboot_out, "rb") as f:
                    encoded = f.read()
        except OSError:
            encoded = None

    if encoded is None:
        # Fallback to deterministic Python encoder (e.g. host cross-platform compatibility)
        with open(loader_bin, "rb") as f:
            raw = f.read()
        encoded = encode_dancingbits_row13(raw)
        with open(diskboot_out, "wb") as f:
            f.write(encoded)

    in_sz = os.path.getsize(loader_bin)
    out_sz = os.path.getsize(diskboot_out)
    assert out_sz == in_sz + 1, f"Expected {in_sz + 1} bytes, got {out_sz}"
    with open(diskboot_out, "rb") as f:
        b0 = f.read(1)
    assert b0 == b"\x00", f"Expected header byte 0x00, got {b0}"
    print(f"  [OK] candidate_port2a/DISKBOOT.BIN successfully encoded ({out_sz} B)")
    return diskboot_out


def extract_witness_addr_from_metadata(metadata_path: str) -> int:
    """Read witness target address from an inspector metadata JSON file.

    Raises FileNotFoundError if metadata_path does not exist.
    Raises ValueError if metadata is malformed or lacks a valid witness_address.
    """
    if not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"Witness inspector metadata file not found: {metadata_path}")
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise ValueError(f"Malformed JSON in witness inspector metadata {metadata_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Metadata root in {metadata_path} must be a JSON object")

    raw_addr = data.get("witness_address")
    if raw_addr is not None:
        try:
            return int(str(raw_addr), 16)
        except ValueError as exc:
            raise ValueError(f"Invalid hex witness_address '{raw_addr}' in {metadata_path}") from exc

    raw_int = data.get("witness_address_int")
    if raw_int is not None and isinstance(raw_int, int):
        return raw_int

    raise ValueError(f"Missing 'witness_address' in inspector metadata {metadata_path}")


def extract_witness_addr_from_payload_bytes(data: bytes, bin_path: str = "payload.bin") -> int:
    """Decode MOVW/MOVT r7 instructions directly from raw inspector binary bytes.

    Layout in witness_inspector_payload.bin (Thumb-2):
      Offset 0x0A: movw r7, #:lower16:BOOT_WITNESS_ADDR
      Offset 0x0E: movt r7, #:upper16:BOOT_WITNESS_ADDR
    """
    if len(data) < 0x12:
        raise ValueError(
            f"Binary payload {bin_path} too small ({len(data)} B) to contain MOVW/MOVT sequence"
        )

    # Decode movw r7 at offset 0x0A
    hw1 = data[0x0A] | (data[0x0B] << 8)
    hw2 = data[0x0C] | (data[0x0D] << 8)
    if (hw1 & 0xFBF0) != 0xF240:
        raise ValueError(
            f"Expected movw instruction at offset 0x0A in {bin_path}, got halfword 0x{hw1:04X}"
        )
    rd_w = (hw2 >> 8) & 0xF
    if rd_w != 7:
        raise ValueError(
            f"Expected target register r7 for movw at offset 0x0A in {bin_path}, got r{rd_w}"
        )
    i_w = (hw1 >> 10) & 1
    imm4_w = hw1 & 0xF
    imm3_w = (hw2 >> 12) & 0x7
    imm8_w = hw2 & 0xFF
    lo = (imm4_w << 12) | (i_w << 11) | (imm3_w << 8) | imm8_w

    # Decode movt r7 at offset 0x0E
    hw3 = data[0x0E] | (data[0x0F] << 8)
    hw4 = data[0x10] | (data[0x11] << 8)
    if (hw3 & 0xFBF0) != 0xF2C0:
        raise ValueError(
            f"Expected movt instruction at offset 0x0E in {bin_path}, got halfword 0x{hw3:04X}"
        )
    rd_t = (hw4 >> 8) & 0xF
    if rd_t != 7:
        raise ValueError(
            f"Expected target register r7 for movt at offset 0x0E in {bin_path}, got r{rd_t}"
        )
    i_t = (hw3 >> 10) & 1
    imm4_t = hw3 & 0xF
    imm3_t = (hw4 >> 12) & 0x7
    imm8_t = hw4 & 0xFF
    hi = (imm4_t << 12) | (i_t << 11) | (imm3_t << 8) | imm8_t

    return (hi << 16) | lo


def extract_witness_addr_from_payload_bin(bin_path: str) -> int:
    """Read and decode MOVW/MOVT boot_witness immediate address from payload binary."""
    if not os.path.isfile(bin_path):
        raise FileNotFoundError(f"Witness inspector payload binary not found: {bin_path}")
    with open(bin_path, "rb") as f:
        data = f.read()
    return extract_witness_addr_from_payload_bytes(data, bin_path)


def verify_inspector_binding(
    metadata_path: str,
    payload_bin_path: str,
    expected_witness_addr: int = EXPECTED_BOOT_WITNESS_ADDR,
) -> int:
    """Verify that an inspector's metadata and binary payload both target the expected ELF witness address.

    Fail-closed policy:
    - If metadata file is missing or unparseable, exits non-zero naming file and expected address.
    - If metadata witness_address mismatches expected_witness_addr, exits non-zero naming
      inspector file, target address, and ELF witness address.
    - If payload binary is missing, exits non-zero naming file and expected address.
    - If payload binary MOVW/MOVT cannot be decoded, exits non-zero with decoding error.
    - If payload binary MOVW/MOVT loads an address differing from expected_witness_addr,
      exits non-zero naming file, target address, and ELF witness address.
    - Never write a manifest or candidate bundling a mismatched inspector.
    - Returns verified integer address on success.
    """
    try:
        meta_addr = extract_witness_addr_from_metadata(metadata_path)
    except FileNotFoundError as exc:
        print(
            f"ERROR: Witness inspector metadata not found: {metadata_path} "
            f"(expected ELF witness 0x{expected_witness_addr:08X})",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(
            f"ERROR: Failed to parse witness inspector metadata from {metadata_path}: {exc} "
            f"(expected ELF witness 0x{expected_witness_addr:08X})",
            file=sys.stderr,
        )
        sys.exit(1)

    if meta_addr != expected_witness_addr:
        print(
            f"ERROR: Witness inspector target address mismatch in {metadata_path}: "
            f"inspector targets 0x{meta_addr:08X}, but candidate ELF witness is 0x{expected_witness_addr:08X}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        bin_addr = extract_witness_addr_from_payload_bin(payload_bin_path)
    except FileNotFoundError as exc:
        print(
            f"ERROR: Witness inspector payload binary not found: {payload_bin_path} "
            f"(expected ELF witness 0x{expected_witness_addr:08X})",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(
            f"ERROR: Failed to decode MOVW/MOVT witness address from {payload_bin_path}: {exc} "
            f"(expected ELF witness 0x{expected_witness_addr:08X})",
            file=sys.stderr,
        )
        sys.exit(1)

    if bin_addr != expected_witness_addr:
        print(
            f"ERROR: Witness inspector payload immediate mismatch in {payload_bin_path}: "
            f"payload loads 0x{bin_addr:08X}, but candidate ELF witness is 0x{expected_witness_addr:08X}",
            file=sys.stderr,
        )
        sys.exit(1)

    bin_size = os.path.getsize(payload_bin_path)
    if bin_size != 444:
        print(
            f"ERROR: Unexpected payload binary size in {payload_bin_path}: {bin_size} B (expected 444 B)",
            file=sys.stderr,
        )
        sys.exit(1)

    return expected_witness_addr


def generate_candidate_inspector(witness_addr: int = EXPECTED_BOOT_WITNESS_ADDR):
    """Regenerate witness inspector payload targeted to witness_addr and verify fail-closed.

    Writes ONLY into CANDIDATE_DIR (build output directory). Never edits anything under firmware/.
    Enforces 3-way consistency check (metadata, MOVW/MOVT immediates, ELF witness symbol).
    """
    print(f"--- Associating Canon Basic Witness Inspector (@ 0x{witness_addr:08X}) ---")
    src_s = os.path.join(FIRMWARE_TOOLS, "witness_inspector_payload.S")
    src_m = os.path.join(FIRMWARE_TOOLS, "witness_inspector_gm110c.m")

    dst_o = os.path.join(CANDIDATE_DIR, "witness_inspector_payload.o")
    dst_bin = os.path.join(CANDIDATE_DIR, "witness_inspector_payload.bin")
    dst_m = os.path.join(CANDIDATE_DIR, "witness_inspector_gm110c.m")
    dst_meta = os.path.join(CANDIDATE_DIR, "witness_inspector_metadata.json")

    # 1. Assemble payload with dynamic witness address
    cmd_cc = [
        CC,
        "-mcpu=cortex-r4",
        "-mthumb",
        f"-DBOOT_WITNESS_ADDR=0x{witness_addr:08X}",
        "-c",
        src_s,
        "-o",
        dst_o,
    ]
    run_cmd(cmd_cc, cwd=REPO_ROOT)

    # 2. Extract raw binary
    cmd_objcopy = [OBJCOPY, "-O", "binary", dst_o, dst_bin]
    run_cmd(cmd_objcopy, cwd=REPO_ROOT)

    # 3. Copy loader script
    shutil.copy2(src_m, dst_m)

    # 4. Generate address metadata in candidate output directory
    bin_size = os.path.getsize(dst_bin)
    meta = {
        "target": "Canon PowerShot G3 X (GM1.10C)",
        "symbol": "boot_witness",
        "witness_address": f"0x{witness_addr:08X}",
        "witness_address_int": witness_addr,
        "elf_file": "candidate_port2a/candidate_main.elf",
        "payload_bin": "candidate_port2a/witness_inspector_payload.bin",
        "payload_size": bin_size,
    }
    with open(dst_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # 5. Verify binding fail-closed
    verify_inspector_binding(dst_meta, dst_bin, witness_addr)
    print(
        f"  [OK] Inspector script and payload ({bin_size} B, target 0x{witness_addr:08X}) "
        f"verified and associated in candidate_port2a/"
    )
    return dst_m, dst_bin


def copy_inspector_artifacts(
    src_m=None,
    src_bin=None,
    src_meta=None,
    expected_witness_addr=EXPECTED_BOOT_WITNESS_ADDR,
):
    """Copy pre-existing inspector artifacts into candidate_port2a/ after verifying them fail-closed.

    Refuses to copy or bundle any mismatched inspector.
    """
    print(f"--- Associating Canon Basic Witness Inspector (verifying against 0x{expected_witness_addr:08X}) ---")
    if src_m is None:
        src_m = os.path.join(FIRMWARE_TOOLS, "witness_inspector_gm110c.m")
    if src_bin is None:
        src_bin = os.path.join(FIRMWARE_TOOLS, "witness_inspector_payload.bin")
    if src_meta is None:
        src_meta = os.path.join(FIRMWARE_TOOLS, "witness_inspector_metadata.json")

    # Verify inspector binding fail-closed before copying
    verify_inspector_binding(src_meta, src_bin, expected_witness_addr)

    dst_m = os.path.join(CANDIDATE_DIR, "witness_inspector_gm110c.m")
    dst_bin = os.path.join(CANDIDATE_DIR, "witness_inspector_payload.bin")

    shutil.copy2(src_m, dst_m)
    shutil.copy2(src_bin, dst_bin)
    print(f"  [OK] Verified inspector script and payload ({os.path.getsize(dst_bin)} B) copied to candidate_port2a/")
    return dst_m, dst_bin


def generate_manifest(
    artifacts,
    witness_addr=EXPECTED_BOOT_WITNESS_ADDR,
    core_end_addr=0x00366CB0,
):
    print("--- Generating Locked Candidate Manifest ---")
    manifest_path = os.path.join(CANDIDATE_DIR, "candidate_manifest.json")

    # Production invariant hashes
    prod_hashes = {
        "DISKBOOT.BIN": sha256_file(PROD_DISKBOOT),
        "loader/g3x/main.c": sha256_file(PROD_LOADER_C),
        "platform/g3x/sub/110c/boot.c": sha256_file(PROD_BOOT_C),
    }

    candidate_hashes = {
        name: {
            "path": os.path.relpath(path, REPO_ROOT),
            "size_bytes": os.path.getsize(path),
            "sha256": sha256_file(path),
        }
        for name, path in artifacts.items()
    }

    manifest = {
        "milestone": "CHDK-PORT-2A",
        "target": "Canon PowerShot G3 X (GM1.10C)",
        "platform_id": "0x32A8 (12968)",
        "chdk_revision": "r5491",
        "toolchain": "ARM GNU-RM 5.4.1 2016q3",
        "status": "OFFLINE_CANDIDATE_BUILT",
        "independent_review": "PENDING",
        "hardware_readiness": "NO-GO",
        "production_invariance": prod_hashes,
        "architectural_invariants": {
            "loader_entry": "0x00008000",
            "loader_stack": "0x00007FE0..0x00008000",
            "core_destination": "0x003489B4",
            "core_thumb_entry": "0x003489B5",
            "core_boot_stack": "0x00003F00..0x00004000",
            "core_end_symbol": f"0x{core_end_addr:08X}",
            "boot_witness_addr": f"0x{witness_addr:08X}",
            "boot_witness_magic": "0x5749544E",
            "boot_witness_version": "0x00010001",
            "fixed_nonce": "0x32A80001",
            "dryos_heap_base": f"0x{core_end_addr:08X}",
            "dryos_heap_upper": "0x00600014",
            "continuation_target": "0xFC0D0126",
            "encoding_row": 13,
            "encoding_type": "dancingbits",
            "spytask_active": False,
            "gui_hooks_active": False,
            "keyboard_hooks_active": False,
        },
        "candidate_artifacts": candidate_hashes,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"  [OK] Manifest written to {manifest_path}")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(
        description="Build and lock CHDK-PORT-2A First-Boot Candidate artifacts"
    )
    parser.add_argument(
        "--check-inspector",
        nargs=2,
        metavar=("METADATA_JSON", "PAYLOAD_BIN"),
        help="Verify an inspector metadata and payload binary pair against EXPECTED_BOOT_WITNESS_ADDR and exit",
    )
    parser.add_argument(
        "--use-existing-inspector",
        action="store_true",
        help="Attempt to copy pre-existing inspector artifacts from firmware/tools/ after fail-closed check",
    )
    args = parser.parse_args()

    if args.check_inspector:
        meta_file, bin_file = args.check_inspector
        verify_inspector_binding(meta_file, bin_file, EXPECTED_BOOT_WITNESS_ADDR)
        print(f"  [OK] Inspector {bin_file} verified bound to 0x{EXPECTED_BOOT_WITNESS_ADDR:08X}")
        sys.exit(0)

    os.makedirs(CANDIDATE_DIR, exist_ok=True)
    core_elf, core_bin = build_candidate_core()
    loader_elf, loader_bin, witness_addr, core_end_addr = build_candidate_loader(core_elf, core_bin)
    diskboot_bin = encode_candidate_diskboot(loader_bin)

    if args.use_existing_inspector:
        insp_m, insp_bin = copy_inspector_artifacts(expected_witness_addr=witness_addr)
    else:
        insp_m, insp_bin = generate_candidate_inspector(witness_addr)

    artifacts = {
        "candidate_main.elf": core_elf,
        "candidate_main.bin": core_bin,
        "candidate_loader.elf": loader_elf,
        "candidate_loader.bin": loader_bin,
        "DISKBOOT.BIN": diskboot_bin,
        "witness_inspector_gm110c.m": insp_m,
        "witness_inspector_payload.bin": insp_bin,
    }
    manifest_path = generate_manifest(
        artifacts, witness_addr=witness_addr, core_end_addr=core_end_addr
    )
    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")


if __name__ == "__main__":
    main()
