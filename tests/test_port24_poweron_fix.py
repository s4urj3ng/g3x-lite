#!/usr/bin/env python3
"""Unit tests for PORT-24: Opt-in short-press boot fix for second power-on check.

Verifies:
1. Default build invariance:
   - Without opt-in flag, build output is byte-identical to PORT-19 baseline.
   - DISKBOOT.BIN SHA-256 == 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136
   - DISKBOOT.BIN size == 118001 bytes.
   - Core symbols boot_witness (0x0035F7A0) and _end (0x00366CB0) remain locked.
2. Opt-in candidate build:
   - DISKBOOT.BIN SHA-256 == faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056
   - DISKBOOT.BIN size == 118001 bytes.
   - Core binary SHA-256 == b9c5b718cd90f7a791c216f07f92758cbdfcd56e4e34702235cffdcc204e6580
   - Core symbols boot_witness (0x0035F7A0) and _end (0x00366CB0) remain locked.
3. Confinement:
   - The disassembly diff between default and opt-in candidate_main.elf is strictly
     confined to sub_fc05b962_my; all other functions across the binary are identical.
4. Evidence manifest:
   - docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json validates cleanly via
     tools/port11c_evidence_validator.py.
5. Documentation & Citations:
   - docs/PORT24_POWERON_FIX.md records reference port citations (file:line), ROM addresses,
     claims with VERIFIED / INFERRED / UNKNOWN labels, and both DISKBOOT SHA-256 values.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_candidate_port24_poweron_fix.py"
MANIFEST_FILE = REPO_ROOT / "docs" / "agentbridge" / "PORT24_POWERON_EVIDENCE_MANIFEST.json"
DOC_FILE = REPO_ROOT / "docs" / "PORT24_POWERON_FIX.md"
VALIDATOR_SCRIPT = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_PATH = Path(
    os.environ.get(
        "PORT24_ROM_PATH",
        os.environ.get("PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")),
    )
)
ROM_BASE = 0xFC000000

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001

EXPECTED_OPTIN_DISKBOOT_SHA256 = (
    "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056"
)
EXPECTED_OPTIN_CORE_BIN_SHA256 = (
    "b9c5b718cd90f7a791c216f07f92758cbdfcd56e4e34702235cffdcc204e6580"
)

EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0
EXPECTED_CORE_END_ADDR = 0x00366CB0


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort24PoweronFix(unittest.TestCase):
    """Test suite covering PORT-24 power-on fix candidate, invariance, confinement, and docs."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(BUILD_SCRIPT.is_file(), f"Build script missing: {BUILD_SCRIPT}")
        cls.assertTrue(MANIFEST_FILE.is_file(), f"Manifest file missing: {MANIFEST_FILE}")
        cls.assertTrue(DOC_FILE.is_file(), f"Documentation missing: {DOC_FILE}")
        cls.assertTrue(OBJDUMP.is_file(), f"arm-none-eabi-objdump missing: {OBJDUMP}")
        cls.assertTrue(NM.is_file(), f"arm-none-eabi-nm missing: {NM}")

        # Create temporary build directories for test execution
        cls.tmp_dir = tempfile.mkdtemp(prefix="port24_test_")
        cls.default_dir = Path(cls.tmp_dir) / "default"
        cls.optin_dir = Path(cls.tmp_dir) / "optin"

        # Build default candidate into cls.default_dir
        cmd_default = [
            "python3",
            "-B",
            str(BUILD_SCRIPT),
            "--default",
            "--out-dir",
            str(cls.default_dir),
        ]
        res_default = subprocess.run(
            cmd_default, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert res_default.returncode == 0, f"Default build failed: {res_default.stderr}"

        # Build opt-in candidate into cls.optin_dir
        cmd_optin = [
            "python3",
            "-B",
            str(BUILD_SCRIPT),
            "--poweron-fix",
            "--out-dir",
            str(cls.optin_dir),
        ]
        res_optin = subprocess.run(
            cmd_optin, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert res_optin.returncode == 0, f"Opt-in build failed: {res_optin.stderr}"

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.tmp_dir):
            shutil.rmtree(cls.tmp_dir)

    def _get_symbols(self, elf_path: Path) -> dict[str, int]:
        res = subprocess.run(
            [str(NM), str(elf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        syms = {}
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                addr_str, _, name = parts[0], parts[1], parts[2]
                try:
                    syms[name] = int(addr_str, 16)
                except ValueError:
                    pass
        return syms

    def test_default_build_invariance(self):
        """Default candidate output is byte-identical to PORT-19/20/21/23 baseline."""
        diskboot = self.default_dir / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), "Default DISKBOOT.BIN not found")
        self.assertEqual(diskboot.stat().st_size, EXPECTED_DEFAULT_DISKBOOT_SIZE)
        self.assertEqual(sha256_file(diskboot), EXPECTED_DEFAULT_DISKBOOT_SHA256)

        # Check symbol positions
        core_elf = self.default_dir / "candidate_main.elf"
        syms = self._get_symbols(core_elf)
        self.assertIn("boot_witness", syms)
        self.assertEqual(syms["boot_witness"], EXPECTED_BOOT_WITNESS_ADDR)
        self.assertIn("_end", syms)
        self.assertEqual(syms["_end"], EXPECTED_CORE_END_ADDR)

    def test_optin_build_hash_and_size(self):
        """Opt-in candidate produces exact expected hashes and sizes."""
        diskboot = self.optin_dir / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), "Opt-in DISKBOOT.BIN not found")
        self.assertEqual(diskboot.stat().st_size, EXPECTED_DEFAULT_DISKBOOT_SIZE)
        self.assertEqual(sha256_file(diskboot), EXPECTED_OPTIN_DISKBOOT_SHA256)

        core_bin = self.optin_dir / "candidate_main.bin"
        self.assertTrue(core_bin.is_file(), "Opt-in candidate_main.bin not found")
        self.assertEqual(sha256_file(core_bin), EXPECTED_OPTIN_CORE_BIN_SHA256)

        # Symbol addresses must be preserved
        core_elf = self.optin_dir / "candidate_main.elf"
        syms = self._get_symbols(core_elf)
        self.assertIn("boot_witness", syms)
        self.assertEqual(syms["boot_witness"], EXPECTED_BOOT_WITNESS_ADDR)
        self.assertIn("_end", syms)
        self.assertEqual(syms["_end"], EXPECTED_CORE_END_ADDR)

    def test_diff_confined_to_intended_function(self):
        """Disassembly diff between default and opt-in candidate_main.elf is strictly in sub_fc05b962_my."""
        default_elf = self.default_dir / "candidate_main.elf"
        optin_elf = self.optin_dir / "candidate_main.elf"

        # Disassemble both
        res_default = subprocess.run(
            [str(OBJDUMP), "-d", str(default_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        res_optin = subprocess.run(
            [str(OBJDUMP), "-d", str(optin_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        def split_functions(disasm_text: str) -> dict[str, list[str]]:
            funcs = {}
            current_func = None
            current_lines = []
            func_header_re = re.compile(r"^[0-9a-fA-F]{8}\s+<([^>]+)>:")
            for line in disasm_text.splitlines():
                m = func_header_re.match(line)
                if m:
                    if current_func:
                        funcs[current_func] = current_lines
                    current_func = m.group(1)
                    current_lines = [line]
                elif current_func:
                    current_lines.append(line)
            if current_func:
                funcs[current_func] = current_lines
            return funcs

        funcs_default = split_functions(res_default.stdout)
        funcs_optin = split_functions(res_optin.stdout)

        # Both must have the identical set of function names
        self.assertEqual(set(funcs_default.keys()), set(funcs_optin.keys()))

        differing_funcs = []
        for name in funcs_default:
            lines_def = funcs_default[name]
            lines_opt = funcs_optin[name]
            if lines_def != lines_opt:
                differing_funcs.append(name)

        # ONLY sub_fc05b962_my may differ
        self.assertEqual(
            differing_funcs,
            ["sub_fc05b962_my"],
            f"Diff escaped intended function! Differing functions: {differing_funcs}",
        )

        # Check the instructions inside sub_fc05b962_my
        optin_func_disasm = "\n".join(funcs_optin["sub_fc05b962_my"])
        # Must contain movs r0, #1
        self.assertIn("movs\tr0, #1", optin_func_disasm)
        # Must NOT contain call to power-cut sub_fc05ba56
        self.assertNotIn("fc05ba56", optin_func_disasm)

    def test_evidence_manifest_validates(self):
        """PORT24_POWERON_EVIDENCE_MANIFEST.json passes tools/port11c_evidence_validator.py."""
        cmd = ["python3", "-B", str(VALIDATOR_SCRIPT), "--manifest", str(MANIFEST_FILE)]
        res = subprocess.run(
            cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Manifest validation failed with returncode {res.returncode}:\n{res.stdout}\n{res.stderr}",
        )
        self.assertIn("Result: VALID", res.stdout)
        self.assertIn("0 errors", res.stdout)

        # Verify required slice IDs are declared
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        slice_ids = {entry["evidence_id"] for entry in manifest.get("evidence_entries", [])}
        required_slices = {
            "PORT24-ROM-CALLER-STARTUP",
            "PORT24-ROM-POWERCUT",
            "PORT24-ROM-NORMAL-MODE",
            "PORT24-ROM-NORMAL-FLAG",
            "PORT24-ROM-STARTCAUSE-SAVE",
            "PORT24-ROM-STARTCAUSE-PTR",
            "PORT24-ROM-GPIO-PRIMITIVES",
            "PORT24-ROM-POWERON-CHECK",
        }
        self.assertTrue(required_slices.issubset(slice_ids))

    def test_documentation_and_citations(self):
        """docs/PORT24_POWERON_FIX.md contains DIGIC 6 references, ROM addresses, labels, and hashes."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            doc_content = f.read()

        # DIGIC 6 reference port citations
        self.assertIn("platform/g5x/sub/100c/boot.c", doc_content)
        self.assertIn("platform/sx60hs/sub/100b/boot.c", doc_content)
        self.assertIn("loader/g7x/main.c", doc_content)
        self.assertIn("g3x_110e.patch", doc_content)

        # ROM addresses
        self.assertIn("0xFC05B962", doc_content)
        self.assertIn("0xFC05BA56", doc_content)
        self.assertIn("0xFC079404", doc_content)
        self.assertIn("0xFC1284AC", doc_content)
        self.assertIn("0x00009BC4", doc_content)
        self.assertIn("0xFDF20380", doc_content)
        self.assertIn("0xD20B099C", doc_content)

        # Confidence labels
        self.assertIn("VERIFIED", doc_content)
        self.assertIn("INFERRED", doc_content)
        self.assertIn("UNKNOWN", doc_content)

        # Expected hashes
        self.assertIn(EXPECTED_DEFAULT_DISKBOOT_SHA256, doc_content)
        self.assertIn(EXPECTED_OPTIN_DISKBOOT_SHA256, doc_content)

    def test_doc_evidence_hashes_match_manifest(self):
        """Check every 64-hex hash next to an evidence ID in docs/PORT24_POWERON_FIX.md against manifest."""
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest_map = {e["evidence_id"]: e["sha256"] for e in manifest.get("evidence_entries", [])}

        with open(DOC_FILE, "r", encoding="utf-8") as f:
            doc_content = f.read()

        # Find occurrences of evidence IDs and nearby 64-hex SHA-256 strings
        pattern = re.compile(
            r"(PORT24-ROM-[A-Z0-9-]+)(?:(?!(PORT24-ROM-[A-Z0-9-]+)).)*?([0-9a-fA-F]{64})",
            re.DOTALL,
        )
        matches = list(pattern.finditer(doc_content))
        self.assertGreater(len(matches), 0, "No evidence hashes found in documentation")

        found_eids = set()
        for m in matches:
            eid = m.group(1)
            sha = m.group(3).lower()
            self.assertIn(eid, manifest_map, f"Evidence ID '{eid}' from doc not present in manifest")
            expected_sha = manifest_map[eid]
            self.assertEqual(
                sha,
                expected_sha,
                f"SHA-256 mismatch for {eid} in docs/PORT24_POWERON_FIX.md: doc={sha} != manifest={expected_sha}",
            )
            found_eids.add(eid)

        # Every manifest entry must be cited with hash at least once in the documentation
        self.assertEqual(
            found_eids,
            set(manifest_map.keys()),
            f"Some manifest entries were not cited with hash in docs: {set(manifest_map.keys()) - found_eids}",
        )

    def test_in_tree_citations(self):
        """Every in-tree source citation exists in git and the cited line contains the quoted text."""
        # Check in-tree citation for chdk-port/platform/g3x/sub/110c/boot_prototype.c
        res = subprocess.run(
            ["git", "ls-files", "chdk-port/platform/g3x/sub/110c/boot_prototype.c"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        tracked = res.stdout.strip()
        self.assertEqual(tracked, "chdk-port/platform/g3x/sub/110c/boot_prototype.c")
        target_file = REPO_ROOT / tracked
        self.assertTrue(target_file.is_file(), f"In-tree file missing: {target_file}")

        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        expected_citations = {
            351: "// Native Canon power-on button check (unmodified stock ROM handler)",
            352: '"    bl      sub_fc1284ac\\n"',
            353: '"    cbnz    r0, loc_fc05b978\\n"',
            354: '"    bl      sub_fc05ba56\\n"',
        }
        for line_no, expected_text in expected_citations.items():
            actual_line = lines[line_no - 1]
            self.assertIn(
                expected_text,
                actual_line,
                f"Line {line_no} of {tracked} does not contain '{expected_text}'. Actual: {actual_line!r}",
            )

    def test_rom_disassembly_bytes_against_primary_bin(self):
        """Every documented disassembly row matches PRIMARY.BIN bytes and lies inside a manifest range."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            doc_content = f.read()

        row_re = re.compile(
            r"^\s*([0-9a-fA-F]{8}):\s+([0-9a-fA-F]{4}(?:\s+[0-9a-fA-F]{4})?)\s+(.*)$",
            re.MULTILINE,
        )
        listing_rows = row_re.findall(doc_content)
        self.assertGreaterEqual(
            len(listing_rows), 50, f"Expected at least 50 listing rows, found {len(listing_rows)}"
        )

        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        approved_ranges = []
        for entry in manifest.get("evidence_entries", []):
            s = int(entry["start_address"], 16)
            e = int(entry["end_address"], 16)
            approved_ranges.append((s, e, entry["sha256"], entry["evidence_id"]))

        # 1. Assert every documented address lies inside an approved manifest range
        for addr_str, hex_str, asm in listing_rows:
            addr = int(addr_str, 16)
            in_range = any(s <= addr <= e for s, e, _, _ in approved_ranges)
            self.assertTrue(
                in_range,
                f"Address 0x{addr:08X} in doc ({asm}) does not lie inside any manifest range",
            )

        # 2. Check against PRIMARY.BIN if present
        if not ROM_PATH.is_file():
            self.skipTest(f"PRIMARY.BIN not present at {ROM_PATH}")

        with open(ROM_PATH, "rb") as f:
            rom_bytes = f.read()

        # Assert manifest range SHA-256 matches actual ROM dump
        for s, e, expected_sha, eid in approved_ranges:
            offset = s - ROM_BASE
            length = e - s + 1
            slice_data = rom_bytes[offset : offset + length]
            actual_sha = hashlib.sha256(slice_data).hexdigest()
            self.assertEqual(
                actual_sha,
                expected_sha,
                f"Manifest SHA-256 mismatch for range {eid}: actual={actual_sha} != manifest={expected_sha}",
            )

        # Assert every instruction row matches byte-for-byte
        for addr_str, hex_str, asm in listing_rows:
            addr = int(addr_str, 16)
            hex_parts = hex_str.split()
            expected_bytes = b"".join(struct.pack("<H", int(p, 16)) for p in hex_parts)
            offset = addr - ROM_BASE
            actual_bytes = rom_bytes[offset : offset + len(expected_bytes)]
            self.assertEqual(
                actual_bytes,
                expected_bytes,
                f"Byte mismatch at 0x{addr:08X}: doc={hex_str} actual={actual_bytes.hex()} ({asm})",
            )


if __name__ == "__main__":
    unittest.main()
