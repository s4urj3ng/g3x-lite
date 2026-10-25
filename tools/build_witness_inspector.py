#!/usr/bin/env python3
"""Build script for PORT-1G.1 Canon Basic Witness Inspector Native Payload.

Target: Canon PowerShot G3 X (GM1.10C)
Toolchain: ARM GNU-RM 5.4.1 (2016q3)

Automatically resolves boot_witness RAM symbol address from candidate_main.elf
using the ARM toolchain (arm-none-eabi-nm) and injects it into the inspector
payload assembly. Emits address metadata and enforces 3-way consistency.
Fails closed: silent fallbacks to prototype ELFs are strictly prohibited.
"""

import argparse
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLCHAIN_BIN = os.path.join(
    REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin"
)
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc")
OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy")
NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
OBJDUMP = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objdump")

FIRMWARE_TOOLS = os.path.join(REPO_ROOT, "firmware", "tools")
PAYLOAD_S = os.path.join(FIRMWARE_TOOLS, "witness_inspector_payload.S")
PAYLOAD_O = os.path.join(FIRMWARE_TOOLS, "witness_inspector_payload.o")
PAYLOAD_BIN = os.path.join(FIRMWARE_TOOLS, "witness_inspector_payload.bin")
LOADER_SCRIPT = os.path.join(FIRMWARE_TOOLS, "witness_inspector_gm110c.m")
METADATA_JSON = os.path.join(FIRMWARE_TOOLS, "witness_inspector_metadata.json")

DEFAULT_CANDIDATE_ELF = os.path.join(REPO_ROOT, "candidate_port2a", "candidate_main.elf")


def extract_witness_addr_from_elf(elf_path, nm_tool=NM):
    """Read boot_witness symbol address from ELF using ARM toolchain.
    
    Rejects missing ELF, missing symbol, incorrect section, or misaligned address.
    """
    if not os.path.exists(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")
    if not os.path.exists(nm_tool):
        raise FileNotFoundError(f"nm tool not found: {nm_tool}")

    res = subprocess.run(
        [nm_tool, "-n", elf_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
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
        raise ValueError(
            f"Symbol 'boot_witness' has unexpected type '{witness_type}' (expected 'D' or 'd') in {elf_path}"
        )
    if witness_addr % 4 != 0:
        raise ValueError(
            f"Symbol 'boot_witness' address 0x{witness_addr:08X} is not 4-byte aligned in {elf_path}"
        )

    return witness_addr


def extract_witness_addr_from_payload_o(obj_path, objdump_tool=OBJDUMP):
    """Extract loaded boot_witness address from disassembled inspector object."""
    if not os.path.exists(obj_path):
        raise FileNotFoundError(f"Object file not found: {obj_path}")
    res = subprocess.run(
        [objdump_tool, "-d", obj_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    dump = res.stdout.decode()
    m_w = re.search(r"movw\s+r7,\s*#(\d+)(?:\s*;\s*0x([0-9a-fA-F]+))?", dump)
    m_t = re.search(r"movt\s+r7,\s*#(\d+)(?:\s*;\s*0x([0-9a-fA-F]+))?", dump)
    if not m_w or not m_t:
        raise ValueError("Could not find movw/movt r7 instructions loading witness address")

    lo = int(m_w.group(2), 16) if m_w.group(2) else int(m_w.group(1), 10)
    hi = int(m_t.group(2), 16) if m_t.group(2) else int(m_t.group(1), 10)
    return (hi << 16) | lo


def update_loader_script_constants(script_path, bin_size):
    """Automatically update generated payload_size constants in Canon Basic script."""
    if not os.path.exists(script_path):
        return
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"DIM payload_size\s*=\s*\d+",
        f"DIM payload_size = {bin_size}",
        content,
    )
    new_content = re.sub(
        r"DIM expected_payload_size\s*=\s*\d+",
        f"DIM expected_payload_size = {bin_size}",
        new_content,
    )
    if new_content != content:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {script_path} with payload_size = {bin_size}")


def write_address_metadata(metadata_path, witness_addr, elf_path, payload_bin, bin_size):
    """Write witness address metadata JSON."""
    meta = {
        "target": "Canon PowerShot G3 X (GM1.10C)",
        "symbol": "boot_witness",
        "witness_address": f"0x{witness_addr:08X}",
        "witness_address_int": witness_addr,
        "elf_file": os.path.relpath(elf_path, REPO_ROOT) if elf_path.startswith(REPO_ROOT) else elf_path,
        "payload_bin": os.path.relpath(payload_bin, REPO_ROOT) if payload_bin.startswith(REPO_ROOT) else payload_bin,
        "payload_size": bin_size,
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Generated address metadata at {metadata_path}")
    return meta


def build_witness_inspector(
    elf_path=None,
    payload_s=PAYLOAD_S,
    payload_o=PAYLOAD_O,
    payload_bin=PAYLOAD_BIN,
    loader_script=LOADER_SCRIPT,
    metadata_json=METADATA_JSON,
    cc=CC,
    objcopy=OBJCOPY,
    nm=NM,
    objdump=OBJDUMP,
):
    """Build the Canon Basic witness inspector payload with dynamic witness address.
    
    Fails closed: if elf_path is None, DEFAULT_CANDIDATE_ELF must exist.
    """
    if not os.path.exists(cc) or not os.path.exists(objcopy) or not os.path.exists(nm):
        raise RuntimeError("Required ARM toolchain binaries (gcc, objcopy, nm) not found")

    if not os.path.exists(payload_s):
        raise FileNotFoundError(f"Payload assembly source not found: {payload_s}")
    if loader_script is not None and not os.path.exists(loader_script):
        raise FileNotFoundError(f"Loader script not found: {loader_script}")

    if elf_path is None:
        if not os.path.exists(DEFAULT_CANDIDATE_ELF):
            raise FileNotFoundError(
                f"Candidate ELF not found: {DEFAULT_CANDIDATE_ELF}. "
                "Silent fallback to prototype ELFs is prohibited. Build fails closed."
            )
        elf_path = DEFAULT_CANDIDATE_ELF

    witness_addr = extract_witness_addr_from_elf(elf_path, nm_tool=nm)
    print(f"Resolved boot_witness symbol address from {elf_path}: 0x{witness_addr:08X}")

    # Assemble payload with dynamic witness address
    cmd_cc = [
        cc,
        "-mcpu=cortex-r4",
        "-mthumb",
        f"-DBOOT_WITNESS_ADDR=0x{witness_addr:08X}",
        "-c",
        payload_s,
        "-o",
        payload_o,
    ]
    res = subprocess.run(cmd_cc, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"Assembly failed:\n{res.stderr.decode()}")

    # Verify assembled address in object file matches symbol address exactly
    loaded_addr = extract_witness_addr_from_payload_o(payload_o, objdump_tool=objdump)
    if loaded_addr != witness_addr:
        raise ValueError(
            f"Assembled address mismatch: payload loads 0x{loaded_addr:08X}, but symbol is 0x{witness_addr:08X}"
        )

    # Extract raw binary
    cmd_objcopy = [objcopy, "-O", "binary", payload_o, payload_bin]
    res = subprocess.run(cmd_objcopy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"Objcopy failed:\n{res.stderr.decode()}")

    bin_size = os.path.getsize(payload_bin)
    print(f"Successfully generated {payload_bin} ({bin_size} bytes, witness @ 0x{witness_addr:08X})")
    assert bin_size % 4 == 0, f"Payload size {bin_size} must be 4-byte aligned"
    assert bin_size <= 512, f"Payload size {bin_size} exceeds 512-byte limit"

    update_loader_script_constants(loader_script, bin_size)
    meta = write_address_metadata(metadata_json, witness_addr, elf_path, payload_bin, bin_size)
    return witness_addr, bin_size, meta


def main():
    parser = argparse.ArgumentParser(description="Build witness inspector payload")
    parser.add_argument("--elf", default=None, help="Path to candidate_main.elf")
    parser.add_argument("--payload-s", default=PAYLOAD_S, help="Path to payload .S source")
    parser.add_argument("--payload-o", default=PAYLOAD_O, help="Path to payload .o output")
    parser.add_argument("--payload-bin", default=PAYLOAD_BIN, help="Path to payload .bin output")
    parser.add_argument("--loader-script", default=LOADER_SCRIPT, help="Path to Canon Basic .m script")
    parser.add_argument("--metadata", default=METADATA_JSON, help="Path to metadata .json output")
    args = parser.parse_args()

    try:
        build_witness_inspector(
            elf_path=args.elf,
            payload_s=args.payload_s,
            payload_o=args.payload_o,
            payload_bin=args.payload_bin,
            loader_script=args.loader_script,
            metadata_json=args.metadata,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
