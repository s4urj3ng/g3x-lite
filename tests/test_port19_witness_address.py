#!/usr/bin/env python3
"""PORT-19 T3: Verification of Boot Witness Address Alignment (P6 Resolution).

Asserts that:
1. The built candidate (candidate_main.elf symbol table, candidate_manifest.json),
2. The preflight tool (tools/port18_trial_preflight.py), and
3. The witness inspector (tools, metadata, and payload binary)
agree on boot_witness = 0x0035F7A0 (.data section, 16-byte aligned, 32 bytes).

Verifies fail-closed behavior:
- If FORBIDDEN_WITNESS_ADDR is reintroduced in symbols, maps, metadata, or inspector payload,
  the inspector, preflight tool, and candidate validator fail with hard errors.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CANDIDATE_DIR = REPO_ROOT / "candidate_port2a"
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
READELF = TOOLCHAIN_BIN / "arm-none-eabi-readelf"
CC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"

sys.path.insert(0, str(TOOLS_DIR))
import build_candidate_port2a as bcp
import validate_candidate_port2a as vcp
import build_witness_inspector as bwi
import validate_witness_inspector as vwi
import port18_trial_preflight as ptp

PINNED_BOOT_WITNESS_ADDR = 0x0035F7A0
FORBIDDEN_WITNESS_ADDR = 0x0035F780  # sole literal: stale pre-correction address
FORBIDDEN_WITNESS_HEX = f"0x{FORBIDDEN_WITNESS_ADDR:08X}"
FORBIDDEN_WITNESS_NM = f"{FORBIDDEN_WITNESS_ADDR:08x}"


def create_mock_payload_bytes(target_addr: int) -> bytes:
    """Generate a valid 444-byte inspector payload mock targeting target_addr."""
    buf = bytearray(444)
    # Header: push {r4, r5, r6, r7, r8, lr}
    buf[0x00:0x04] = b"\x2d\xe9\xf0\x41"
    # MOVW r7, #:lower16:target_addr
    lo = target_addr & 0xFFFF
    lo_i = (lo >> 11) & 1
    lo_imm4 = (lo >> 12) & 0xF
    lo_imm3 = (lo >> 8) & 0x7
    lo_imm8 = lo & 0xFF
    hw1 = 0xF240 | (lo_i << 10) | lo_imm4
    hw2 = (lo_imm3 << 12) | (7 << 8) | lo_imm8
    buf[0x0A:0x0E] = struct.pack("<HH", hw1, hw2)
    # MOVT r7, #:upper16:target_addr
    hi = (target_addr >> 16) & 0xFFFF
    hi_i = (hi >> 11) & 1
    hi_imm4 = (hi >> 12) & 0xF
    hi_imm3 = (hi >> 8) & 0x7
    hi_imm8 = hi & 0xFF
    hw3 = 0xF2C0 | (hi_i << 10) | hi_imm4
    hw4 = (hi_imm3 << 12) | (7 << 8) | hi_imm8
    buf[0x0E:0x12] = struct.pack("<HH", hw3, hw4)
    # Required string literals
    for s in [
        b"LOADER_REACHED",
        b"CORE_REACHED",
        b"CONT_ATTEMPTED",
        b"STALE / REPLAY",
        b"WITNESS_INVALID",
        b"FRESHNESS_UNVERIFIED",
        b"NONCE_MISMATCH",
        b"INVALID / CORRUPT",
    ]:
        idx = buf.find(b"\x00" * (len(s) + 1), 0x20)
        if idx >= 0:
            buf[idx : idx + len(s)] = s
    return bytes(buf)


class TestPort19WitnessAddress(unittest.TestCase):
    """Test suite resolving trial conflict P6: witness address agreement on 0x0035F7A0."""

    @classmethod
    def setUpClass(cls):
        """Ensure candidate is built before inspecting artifacts."""
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        if not core_elf.exists():
            subprocess.run(
                [sys.executable, "-B", str(TOOLS_DIR / "bootstrap_chdk_platform.py")],
                cwd=str(REPO_ROOT),
                check=True,
            )
            env = os.environ.copy()
            env.pop("G3X_TRACE", None)
            subprocess.run(
                [sys.executable, "-B", str(TOOLS_DIR / "build_candidate_port2a.py")],
                cwd=str(REPO_ROOT),
                env=env,
                check=True,
            )

    def test_pinned_constants_coherence(self):
        """All tools define EXPECTED_BOOT_WITNESS_ADDR as 0x0035F7A0, never FORBIDDEN_WITNESS_ADDR."""
        self.assertEqual(bcp.EXPECTED_BOOT_WITNESS_ADDR, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(vcp.EXPECTED_BOOT_WITNESS_ADDR, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(ptp.EXPECTED_BOOT_WITNESS_ADDR, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(bwi.EXPECTED_BOOT_WITNESS_ADDR, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(vwi.EXPECTED_BOOT_WITNESS_ADDR, PINNED_BOOT_WITNESS_ADDR)

        # Disallow stale pre-correction address across all tools
        for tool_const in [
            bcp.EXPECTED_BOOT_WITNESS_ADDR,
            vcp.EXPECTED_BOOT_WITNESS_ADDR,
            ptp.EXPECTED_BOOT_WITNESS_ADDR,
            bwi.EXPECTED_BOOT_WITNESS_ADDR,
            vwi.EXPECTED_BOOT_WITNESS_ADDR,
        ]:
            self.assertNotEqual(tool_const, FORBIDDEN_WITNESS_ADDR)

    def test_built_candidate_symbol_table(self):
        """Built candidate ELF symbol table defines boot_witness = 0x0035F7A0."""
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        self.assertTrue(core_elf.exists(), f"Candidate ELF missing: {core_elf}")

        res = subprocess.run(
            [str(NM), "-n", str(core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )

        witness_addr = None
        witness_type = None
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[2] == "boot_witness":
                witness_addr = int(parts[0], 16)
                witness_type = parts[1]
                break

        self.assertIsNotNone(witness_addr, "boot_witness symbol missing from candidate_main.elf")
        self.assertEqual(witness_addr, PINNED_BOOT_WITNESS_ADDR)
        self.assertNotEqual(witness_addr, FORBIDDEN_WITNESS_ADDR)
        self.assertIn(witness_type, ("D", "d"), "boot_witness must reside in .data")
        self.assertEqual(witness_addr % 16, 0, "boot_witness must be 16-byte aligned")

        # Verify symbol size using readelf
        res_re = subprocess.run(
            [str(READELF), "-s", str(core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        found_size = None
        for line in res_re.stdout.splitlines():
            if "boot_witness" in line and "OBJECT" in line:
                parts = line.split()
                found_size = int(parts[2])
                break
        self.assertEqual(found_size, 32, "boot_witness struct size must be 32 bytes (0x20)")

    def test_built_candidate_manifest(self):
        """candidate_manifest.json specifies boot_witness_addr = 0x0035F7A0."""
        manifest_path = CANDIDATE_DIR / "candidate_manifest.json"
        self.assertTrue(manifest_path.exists(), f"Manifest missing: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        arch = manifest.get("architectural_invariants", {})
        self.assertEqual(arch.get("boot_witness_addr"), "0x0035F7A0")
        self.assertNotEqual(arch.get("boot_witness_addr"), FORBIDDEN_WITNESS_HEX)

    def test_candidate_inspector_artifacts(self):
        """candidate_port2a inspector metadata and binary target 0x0035F7A0."""
        meta_path = CANDIDATE_DIR / "witness_inspector_metadata.json"
        bin_path = CANDIDATE_DIR / "witness_inspector_payload.bin"
        self.assertTrue(meta_path.exists(), f"Inspector metadata missing: {meta_path}")
        self.assertTrue(bin_path.exists(), f"Inspector payload missing: {bin_path}")

        # Metadata
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["witness_address"], "0x0035F7A0")
        self.assertEqual(meta["witness_address_int"], PINNED_BOOT_WITNESS_ADDR)
        self.assertNotEqual(meta["witness_address"], FORBIDDEN_WITNESS_HEX)

        # Payload binary MOVW/MOVT opcode decode
        decoded_addr = vwi.extract_witness_addr_from_binary_bytes(str(bin_path))
        self.assertEqual(decoded_addr, PINNED_BOOT_WITNESS_ADDR)
        self.assertNotEqual(decoded_addr, FORBIDDEN_WITNESS_ADDR)

    def test_tripartite_witness_address_agreement(self):
        """Inspector, preflight tool, and built candidate strictly agree on 0x0035F7A0."""
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        candidate_addr = bwi.extract_witness_addr_from_elf(str(core_elf))
        preflight_expected = ptp.EXPECTED_BOOT_WITNESS_ADDR
        inspector_val_expected = vwi.EXPECTED_BOOT_WITNESS_ADDR
        inspector_bld_expected = bwi.EXPECTED_BOOT_WITNESS_ADDR

        # Inspector metadata
        meta_path = CANDIDATE_DIR / "witness_inspector_metadata.json"
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_addr = int(json.load(f)["witness_address"], 16)

        # Inspector binary
        bin_path = CANDIDATE_DIR / "witness_inspector_payload.bin"
        payload_addr = vwi.extract_witness_addr_from_binary_bytes(str(bin_path))

        # Tripartite assertion
        self.assertEqual(candidate_addr, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(preflight_expected, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(inspector_val_expected, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(inspector_bld_expected, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(meta_addr, PINNED_BOOT_WITNESS_ADDR)
        self.assertEqual(payload_addr, PINNED_BOOT_WITNESS_ADDR)

        # Explicit pairwise agreement
        self.assertEqual(candidate_addr, preflight_expected)
        self.assertEqual(candidate_addr, meta_addr)
        self.assertEqual(candidate_addr, payload_addr)

        # Absence of FORBIDDEN_WITNESS_ADDR
        for addr in [candidate_addr, preflight_expected, inspector_val_expected, meta_addr, payload_addr]:
            self.assertNotEqual(addr, FORBIDDEN_WITNESS_ADDR)

    def test_preflight_tool_passes_candidate_and_rejects_0035f780(self):
        """Preflight tool accepts 0x0035F7A0 candidate symbols and rejects FORBIDDEN_WITNESS_ADDR with exit 1."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        meta_path = CANDIDATE_DIR / "witness_inspector_metadata.json"
        bin_path = CANDIDATE_DIR / "witness_inspector_payload.bin"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"

        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run(
                    [str(NM), "-n", str(core_elf)],
                    stdout=f,
                    check=True,
                )

            # Preflight passes on genuine candidate DISKBOOT + candidate symbols + candidate inspector
            exit_code, report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(meta_path),
                inspector_bin_path=str(bin_path),
            )
            self.assertEqual(exit_code, 0, f"Preflight failed: {report}")
            self.assertEqual(report["verdict"], "PASS")
            self.assertTrue(report["checks_by_name"]["boot_witness"]["pass"])
            self.assertEqual(report["checks_by_name"]["boot_witness"]["actual"], "0x0035F7A0")
            self.assertTrue(report["checks_by_name"]["inspector_metadata_witness"]["pass"])
            self.assertTrue(report["checks_by_name"]["inspector_payload_witness"]["pass"])

            # Stale FORBIDDEN_WITNESS_ADDR in symbol table fails closed with exit code 1
            bad_symbols = Path(td) / "bad_symbols.nm"
            bad_symbols.write_text(
                "003489b4 T _start\n"
                f"{FORBIDDEN_WITNESS_NM} D boot_witness\n"
                "00366cb0 B _end\n"
            )
            bad_exit, bad_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(bad_symbols),
            )
            self.assertEqual(bad_exit, 1, f"Preflight must fail on stale {FORBIDDEN_WITNESS_HEX} symbols")
            self.assertEqual(bad_report["verdict"], "FAIL")
            self.assertFalse(bad_report["checks_by_name"]["boot_witness"]["pass"])
            self.assertEqual(bad_report["checks_by_name"]["boot_witness"]["actual"], FORBIDDEN_WITNESS_HEX)

            # Stale FORBIDDEN_WITNESS_ADDR in metadata fails closed with exit code 1
            bad_meta = Path(td) / "bad_meta.json"
            bad_meta.write_text(json.dumps({"witness_address": FORBIDDEN_WITNESS_HEX}))
            meta_exit, meta_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(bad_meta),
            )
            self.assertEqual(meta_exit, 1, f"Preflight must fail on stale {FORBIDDEN_WITNESS_HEX} inspector metadata")
            self.assertEqual(meta_report["verdict"], "FAIL")
            self.assertFalse(meta_report["checks_by_name"]["inspector_metadata_witness"]["pass"])
            self.assertEqual(meta_report["checks_by_name"]["inspector_metadata_witness"]["actual"], FORBIDDEN_WITNESS_HEX)

            # Stale FORBIDDEN_WITNESS_ADDR in inspector payload binary fails closed with exit code 1
            bad_bin = Path(td) / "bad_inspector.bin"
            bad_bin.write_bytes(create_mock_payload_bytes(FORBIDDEN_WITNESS_ADDR))
            bin_exit, bin_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bad_bin),
            )
            self.assertEqual(bin_exit, 1, f"Preflight must fail on stale {FORBIDDEN_WITNESS_HEX} inspector payload binary")
            self.assertEqual(bin_report["verdict"], "FAIL")
            self.assertFalse(bin_report["checks_by_name"]["inspector_payload_witness"]["pass"])
            self.assertEqual(bin_report["checks_by_name"]["inspector_payload_witness"]["actual"], FORBIDDEN_WITNESS_HEX)

    def test_inspector_validator_rejects_0035f780(self):
        """Inspector validator fails closed when encountering FORBIDDEN_WITNESS_ADDR in metadata or payload."""
        payload_bin = CANDIDATE_DIR / "witness_inspector_payload.bin"
        payload_o = CANDIDATE_DIR / "witness_inspector_payload.o"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"

        # Stale metadata targeting FORBIDDEN_WITNESS_ADDR raises AssertionError
        with tempfile.TemporaryDirectory() as td:
            stale_meta = Path(td) / "stale_meta.json"
            stale_meta.write_text(
                json.dumps(
                    {
                        "target": "Canon PowerShot G3 X (GM1.10C)",
                        "symbol": "boot_witness",
                        "witness_address": FORBIDDEN_WITNESS_HEX,
                        "witness_address_int": FORBIDDEN_WITNESS_ADDR,
                        "payload_size": 444,
                    }
                )
            )
            with self.assertRaises((ValueError, AssertionError)) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=str(payload_bin),
                    payload_elf=str(payload_o),
                    elf_path=str(core_elf),
                    metadata_path=str(stale_meta),
                    expected_witness_addr=PINNED_BOOT_WITNESS_ADDR,
                )
            self.assertIn(FORBIDDEN_WITNESS_HEX, str(ctx.exception))

        # Stale payload binary targeting FORBIDDEN_WITNESS_ADDR raises ValueError
        with tempfile.TemporaryDirectory() as td:
            stale_payload = Path(td) / "stale_payload.bin"
            stale_payload.write_bytes(create_mock_payload_bytes(FORBIDDEN_WITNESS_ADDR))
            with self.assertRaises((ValueError, AssertionError)) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=str(stale_payload),
                    payload_elf=str(payload_o),
                    elf_path=str(core_elf),
                    expected_witness_addr=PINNED_BOOT_WITNESS_ADDR,
                )
            err_msg = str(ctx.exception)
            self.assertTrue(
                FORBIDDEN_WITNESS_HEX in err_msg or "does not match" in err_msg,
                f"Expected mismatch error, got: {err_msg}",
            )

    def test_inspector_builder_rejects_0035f780_symbol_table(self):
        """Inspector builder extract_witness_addr_from_elf rejects FORBIDDEN_WITNESS_ADDR with ValueError."""
        with tempfile.TemporaryDirectory() as td:
            dummy_elf = Path(td) / "dummy.elf"
            dummy_elf.touch()

            def mock_run(*args, **kwargs):
                class MockRes:
                    stdout = f"{FORBIDDEN_WITNESS_NM} D boot_witness\n".encode()
                    stderr = b""
                    returncode = 0
                return MockRes()

            import unittest.mock as mock
            with mock.patch("subprocess.run", side_effect=mock_run):
                with self.assertRaises(ValueError) as ctx:
                    bwi.extract_witness_addr_from_elf(
                        str(dummy_elf),
                        nm_tool=str(NM),
                        expected_addr=PINNED_BOOT_WITNESS_ADDR,
                    )
                self.assertIn(FORBIDDEN_WITNESS_HEX, str(ctx.exception))
                self.assertIn("0x0035F7A0", str(ctx.exception))

    def test_inspector_metadata_missing_field_reports_clean_fail(self):
        """Inspector metadata missing 'witness_address' field reports clean FAIL without crashing (Fix b)."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            bad_meta = Path(td) / "missing_field.json"
            bad_meta.write_text(json.dumps({"target": "Canon PowerShot G3 X"}))

            exit_code, report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(bad_meta),
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["verdict"], "FAIL")
            check = report["checks_by_name"]["inspector_metadata_witness"]
            self.assertFalse(check["pass"])
            self.assertEqual(check["actual"], "None")
            self.assertEqual(check["status"], "FAIL")
            self.assertIn("missing", check["reason"].lower())

    def test_inspector_payload_binary_invalid_opcodes_reports_clean_fail(self):
        """Inspector payload binary with non-MOVW/MOVT bytes reports clean FAIL (Fix c)."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            bad_bin = Path(td) / "corrupt_payload.bin"
            bad_bin.write_bytes(b"\x00" * 32)

            exit_code, report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bad_bin),
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["verdict"], "FAIL")
            check = report["checks_by_name"]["inspector_payload_witness"]
            self.assertFalse(check["pass"])
            self.assertEqual(check["actual"], "None")
            self.assertEqual(check["status"], "FAIL")
            self.assertTrue(
                "Invalid Thumb-2 MOVW" in check["reason"] or "Failed to decode" in check["reason"],
                f"Unexpected failure reason: {check['reason']}",
            )

    # =========================================================================
    # Regression Tests: Inspector Metadata witness_address_int Validation
    # =========================================================================

    def test_inspector_metadata_witness_address_int_disagreement_fails(self):
        """Metadata with witness_address string OK but witness_address_int = FORBIDDEN_WITNESS_ADDR fails (non-zero exit)."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            meta_file = Path(td) / "disagree_meta.json"
            meta_file.write_text(json.dumps({
                "target": "Canon PowerShot G3 X (GM1.10C)",
                "symbol": "boot_witness",
                "witness_address": "0x0035F7A0",
                "witness_address_int": FORBIDDEN_WITNESS_ADDR,
            }))

            exit_code, report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(meta_file),
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["verdict"], "FAIL")
            check = report["checks_by_name"]["inspector_metadata_witness"]
            self.assertFalse(check["pass"])
            self.assertEqual(check["status"], "FAIL")
            self.assertIn("disagrees", check["reason"])
            self.assertIn(FORBIDDEN_WITNESS_HEX, check["reason"])

    def test_inspector_metadata_witness_address_int_non_integer_fails(self):
        """Metadata with witness_address_int not an integer fails with clean FAIL reason."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            for non_int in ["0x0035F7A0", True, 3.14]:
                meta_file = Path(td) / f"non_int_{type(non_int).__name__}.json"
                meta_file.write_text(json.dumps({
                    "target": "Canon PowerShot G3 X (GM1.10C)",
                    "symbol": "boot_witness",
                    "witness_address": "0x0035F7A0",
                    "witness_address_int": non_int,
                }))

                exit_code, report = ptp.run_preflight(
                    binary_path=str(diskboot),
                    symbols_path=str(symbols_txt),
                    inspector_metadata_path=str(meta_file),
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["verdict"], "FAIL")
                check = report["checks_by_name"]["inspector_metadata_witness"]
                self.assertFalse(check["pass"])
                self.assertEqual(check["status"], "FAIL")
                self.assertIn("not an integer", check["reason"])

    def test_inspector_metadata_both_fields_pinned_passes(self):
        """Metadata with both witness_address and witness_address_int pinned to 0x0035F7A0 passes."""
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"
        with tempfile.TemporaryDirectory() as td:
            symbols_txt = Path(td) / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            meta_file = Path(td) / "pinned_meta.json"
            meta_file.write_text(json.dumps({
                "target": "Canon PowerShot G3 X (GM1.10C)",
                "symbol": "boot_witness",
                "witness_address": "0x0035F7A0",
                "witness_address_int": PINNED_BOOT_WITNESS_ADDR,
            }))

            exit_code, report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(meta_file),
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["verdict"], "PASS")
            check = report["checks_by_name"]["inspector_metadata_witness"]
            self.assertTrue(check["pass"])
            self.assertEqual(check["status"], "PASS")
            self.assertEqual(check["actual"], "0x0035F7A0")
            self.assertIsNone(check["reason"])

    # =========================================================================
    # Regression Tests: Output Collision Protection for Inspector Inputs
    # =========================================================================

    def _run_preflight_cli(self, *args):
        cmd = [sys.executable, str(TOOLS_DIR / "port18_trial_preflight.py")] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_refuse_out_equal_to_inspector_metadata(self):
        """--out pointing directly to --inspector-metadata file is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            meta_bytes = b'{"target": "Canon PowerShot G3 X", "witness_address": "0x0035F7A0", "witness_address_int": 3536800}\n'
            meta_path = Path(td) / "inspector_meta.json"
            meta_path.write_bytes(meta_bytes)

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            # Direct CLI check
            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-metadata", str(meta_path),
                "--out", str(meta_path),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(meta_path.read_bytes(), meta_bytes, "Inspector metadata bytes must be unchanged")

            # Direct Python API check
            with self.assertRaises(ValueError) as ctx:
                ptp.run_preflight(
                    binary_path=str(bin_path),
                    symbols_path=str(sym_path),
                    inspector_metadata_path=str(meta_path),
                    out_path=str(meta_path),
                )
            self.assertIn("Output collision error", str(ctx.exception))
            self.assertEqual(meta_path.read_bytes(), meta_bytes, "Inspector metadata bytes must be unchanged")

    def test_refuse_out_as_symlink_to_inspector_metadata(self):
        """--out given as symlink alias to --inspector-metadata is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            meta_bytes = b'{"target": "Canon PowerShot G3 X", "witness_address": "0x0035F7A0", "witness_address_int": 3536800}\n'
            meta_path = Path(td) / "inspector_meta.json"
            meta_path.write_bytes(meta_bytes)
            out_link = Path(td) / "meta_symlink.json"
            try:
                os.symlink(meta_path, out_link)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks not supported")

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-metadata", str(meta_path),
                "--out", str(out_link),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(meta_path.read_bytes(), meta_bytes, "Inspector metadata bytes must be unchanged")

    def test_refuse_out_as_hardlink_to_inspector_metadata(self):
        """--out given as hardlink alias to --inspector-metadata is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            meta_bytes = b'{"target": "Canon PowerShot G3 X", "witness_address": "0x0035F7A0", "witness_address_int": 3536800}\n'
            meta_path = Path(td) / "inspector_meta.json"
            meta_path.write_bytes(meta_bytes)
            out_hardlink = Path(td) / "meta_hardlink.json"
            try:
                os.link(meta_path, out_hardlink)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("hard links not supported")

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-metadata", str(meta_path),
                "--out", str(out_hardlink),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(meta_path.read_bytes(), meta_bytes, "Inspector metadata bytes must be unchanged")

    def test_refuse_out_equal_to_inspector_bin(self):
        """--out pointing directly to --inspector-bin file is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            payload_bytes = create_mock_payload_bytes(PINNED_BOOT_WITNESS_ADDR)
            bin_target = Path(td) / "witness_inspector_payload.bin"
            bin_target.write_bytes(payload_bytes)

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            # Direct CLI check
            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-bin", str(bin_target),
                "--out", str(bin_target),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(bin_target.read_bytes(), payload_bytes, "Inspector binary bytes must be unchanged")

            # Direct Python API check
            with self.assertRaises(ValueError) as ctx:
                ptp.run_preflight(
                    binary_path=str(bin_path),
                    symbols_path=str(sym_path),
                    inspector_bin_path=str(bin_target),
                    out_path=str(bin_target),
                )
            self.assertIn("Output collision error", str(ctx.exception))
            self.assertEqual(bin_target.read_bytes(), payload_bytes, "Inspector binary bytes must be unchanged")

    def test_refuse_out_as_symlink_to_inspector_bin(self):
        """--out given as symlink alias to --inspector-bin is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            payload_bytes = create_mock_payload_bytes(PINNED_BOOT_WITNESS_ADDR)
            bin_target = Path(td) / "witness_inspector_payload.bin"
            bin_target.write_bytes(payload_bytes)
            out_link = Path(td) / "payload_symlink.json"
            try:
                os.symlink(bin_target, out_link)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks not supported")

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-bin", str(bin_target),
                "--out", str(out_link),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(bin_target.read_bytes(), payload_bytes, "Inspector binary bytes must be unchanged")

    def test_refuse_out_as_hardlink_to_inspector_bin(self):
        """--out given as hardlink alias to --inspector-bin is rejected, leaving file untouched."""
        with tempfile.TemporaryDirectory() as td:
            payload_bytes = create_mock_payload_bytes(PINNED_BOOT_WITNESS_ADDR)
            bin_target = Path(td) / "witness_inspector_payload.bin"
            bin_target.write_bytes(payload_bytes)
            out_hardlink = Path(td) / "payload_hardlink.json"
            try:
                os.link(bin_target, out_hardlink)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("hard links not supported")

            bin_path = Path(td) / "candidate.bin"
            bin_path.write_bytes(b"CANDIDATE_DATA")
            sym_path = Path(td) / "symbols.nm"
            sym_path.write_text("0035f7a0 D boot_witness\n00366cb0 B _end\n")

            res = self._run_preflight_cli(
                str(bin_path), str(sym_path),
                "--inspector-bin", str(bin_target),
                "--out", str(out_hardlink),
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Output collision error", res.stderr)
            self.assertEqual(bin_target.read_bytes(), payload_bytes, "Inspector binary bytes must be unchanged")

    # =========================================================================
    # Hardening Tests: Pinned Verification Integrity (-O / AST / Thumb-2 Bit 15)
    # =========================================================================

    def test_validator_contains_no_assert_statements(self):
        """Inspector validator contains zero assert statements (enforces invariants under python -O)."""
        validator_path = TOOLS_DIR / "validate_witness_inspector.py"
        source = validator_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(validator_path))
        assert_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        self.assertEqual(
            len(assert_nodes),
            0,
            f"Found assert statement(s) in {validator_path}: {[node.lineno for node in assert_nodes]}",
        )

    def test_validator_rejects_self_consistent_0035f780_under_python_optimize(self):
        """Validator rejects a self-consistent FORBIDDEN_WITNESS_ADDR fixture when run under -O / PYTHONOPTIMIZE=1."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            mock_c = td_path / "mock.c"
            mock_c.write_text(
                "void _start(void) {}\n"
                "__attribute__((aligned(16), section(\".data\"))) char boot_witness[32] = {0};\n"
            )
            mock_elf = td_path / "mock_780.elf"
            subprocess.run(
                [str(CC), "-nostdlib", f"-Wl,-Ttext,0x350000,-Tdata,0x{FORBIDDEN_WITNESS_ADDR:08x}", str(mock_c), "-o", str(mock_elf)],
                check=True,
            )

            mock_addr = bwi.extract_witness_addr_from_elf(str(mock_elf))
            self.assertEqual(mock_addr, FORBIDDEN_WITNESS_ADDR)

            fixture_o = td_path / "payload.o"
            fixture_bin = td_path / "payload.bin"
            fixture_script = td_path / "script.m"
            fixture_meta = td_path / "meta.json"

            shutil.copyfile(
                REPO_ROOT / "firmware" / "tools" / "witness_inspector_gm110c.m",
                fixture_script,
            )

            bwi.build_witness_inspector(
                elf_path=str(mock_elf),
                payload_o=str(fixture_o),
                payload_bin=str(fixture_bin),
                loader_script=str(fixture_script),
                metadata_json=str(fixture_meta),
                expected_witness_addr=FORBIDDEN_WITNESS_ADDR,
            )

            # Confirm fixture is internally self-consistent on FORBIDDEN_WITNESS_ADDR
            bin_addr = vwi.extract_witness_addr_from_binary_bytes(str(fixture_bin))
            self.assertEqual(bin_addr, FORBIDDEN_WITNESS_ADDR)
            with open(fixture_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.assertEqual(meta["witness_address_int"], FORBIDDEN_WITNESS_ADDR)

            # Test 1: Subprocess invocation with python3 -O
            cmd_opt = [
                sys.executable,
                "-O",
                str(TOOLS_DIR / "validate_witness_inspector.py"),
                "--elf", str(mock_elf),
                "--payload-bin", str(fixture_bin),
                "--payload-elf", str(fixture_o),
                "--loader-script", str(fixture_script),
                "--metadata", str(fixture_meta),
            ]
            res_opt = subprocess.run(cmd_opt, capture_output=True, text=True)
            self.assertNotEqual(
                res_opt.returncode,
                0,
                f"Validator unexpectedly passed on {FORBIDDEN_WITNESS_HEX} under -O:\nSTDOUT: {res_opt.stdout}\nSTDERR: {res_opt.stderr}",
            )
            self.assertIn(FORBIDDEN_WITNESS_HEX, res_opt.stderr)

            # Test 2: Subprocess invocation with PYTHONOPTIMIZE=1
            env_opt = os.environ.copy()
            env_opt["PYTHONOPTIMIZE"] = "1"
            cmd_env = [
                sys.executable,
                str(TOOLS_DIR / "validate_witness_inspector.py"),
                "--elf", str(mock_elf),
                "--payload-bin", str(fixture_bin),
                "--payload-elf", str(fixture_o),
                "--loader-script", str(fixture_script),
                "--metadata", str(fixture_meta),
            ]
            res_env = subprocess.run(cmd_env, capture_output=True, text=True, env=env_opt)
            self.assertNotEqual(
                res_env.returncode,
                0,
                f"Validator unexpectedly passed on {FORBIDDEN_WITNESS_HEX} under PYTHONOPTIMIZE=1:\nSTDOUT: {res_env.stdout}\nSTDERR: {res_env.stderr}",
            )
            self.assertIn(FORBIDDEN_WITNESS_HEX, res_env.stderr)

    def test_preflight_movw_movt_thumb2_opcode_and_bit15_validation(self):
        """Decoder fully validates Thumb-2 T3 MOVW / T1 MOVT: opcode bits and second halfword bit 15 == 0.

        Tests:
        - 0xF7A0 variant alone (bit 15 set in MOVW second halfword) -> clean FAIL
        - 0x8735 variant alone (bit 15 set in MOVT second halfword) -> clean FAIL
        - Both 0xF7A0 and 0x8735 together -> clean FAIL
        - Correct pinned encoding (0x77A0 / 0x0735) -> PASS
        """
        diskboot = CANDIDATE_DIR / "DISKBOOT.BIN"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            symbols_txt = td_path / "symbols.nm"
            with open(symbols_txt, "w") as f:
                subprocess.run([str(NM), "-n", str(core_elf)], stdout=f, check=True)

            canonical_payload = bytearray(create_mock_payload_bytes(PINNED_BOOT_WITNESS_ADDR))

            # Verify baseline: correct pinned encoding (0x77A0 / 0x0735) gives PASS
            bin_canonical = td_path / "payload_canonical.bin"
            bin_canonical.write_bytes(bytes(canonical_payload))
            exit_code_ok, report_ok = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bin_canonical),
            )
            self.assertEqual(exit_code_ok, 0, f"Canonical pinned encoding failed preflight: {report_ok}")
            self.assertEqual(report_ok["verdict"], "PASS")
            check_ok = report_ok["checks_by_name"]["inspector_payload_witness"]
            self.assertTrue(check_ok["pass"])
            self.assertEqual(check_ok["status"], "PASS")
            self.assertEqual(check_ok["actual"], "0x0035F7A0")
            self.assertIsNone(check_ok["reason"])

            # Variant 1: 0xF7A0 alone (bit 15 set in MOVW second halfword, 0xF7A0 instead of 0x77A0)
            payload_f7a0 = bytearray(canonical_payload)
            payload_f7a0[12:14] = struct.pack("<H", 0xF7A0)
            bin_f7a0 = td_path / "payload_f7a0.bin"
            bin_f7a0.write_bytes(bytes(payload_f7a0))

            # Direct decoder check
            addr_v1, err_v1 = ptp.decode_inspector_payload_witness_addr_details(bytes(payload_f7a0))
            self.assertIsNone(addr_v1)
            self.assertIsNotNone(err_v1)
            self.assertIn("bit 15", err_v1)
            self.assertIn("0xF7A0", err_v1)

            # Preflight tool check
            exit_code_v1, report_v1 = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bin_f7a0),
            )
            self.assertEqual(exit_code_v1, 1, "0xF7A0 alone must fail preflight")
            self.assertEqual(report_v1["verdict"], "FAIL")
            check_v1 = report_v1["checks_by_name"]["inspector_payload_witness"]
            self.assertFalse(check_v1["pass"])
            self.assertEqual(check_v1["status"], "FAIL")
            self.assertEqual(check_v1["actual"], "None")
            self.assertIn("bit 15", check_v1["reason"])
            self.assertIn("0xF7A0", check_v1["reason"])

            # Validator binary check
            with self.assertRaises(ValueError):
                vwi.extract_witness_addr_from_binary_bytes(str(bin_f7a0))

            # Variant 2: 0x8735 alone (bit 15 set in MOVT second halfword, 0x8735 instead of 0x0735)
            payload_8735 = bytearray(canonical_payload)
            payload_8735[16:18] = struct.pack("<H", 0x8735)
            bin_8735 = td_path / "payload_8735.bin"
            bin_8735.write_bytes(bytes(payload_8735))

            # Direct decoder check
            addr_v2, err_v2 = ptp.decode_inspector_payload_witness_addr_details(bytes(payload_8735))
            self.assertIsNone(addr_v2)
            self.assertIsNotNone(err_v2)
            self.assertIn("bit 15", err_v2)
            self.assertIn("0x8735", err_v2)

            # Preflight tool check
            exit_code_v2, report_v2 = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bin_8735),
            )
            self.assertEqual(exit_code_v2, 1, "0x8735 alone must fail preflight")
            self.assertEqual(report_v2["verdict"], "FAIL")
            check_v2 = report_v2["checks_by_name"]["inspector_payload_witness"]
            self.assertFalse(check_v2["pass"])
            self.assertEqual(check_v2["status"], "FAIL")
            self.assertEqual(check_v2["actual"], "None")
            self.assertIn("bit 15", check_v2["reason"])
            self.assertIn("0x8735", check_v2["reason"])

            # Validator binary check
            with self.assertRaises(ValueError):
                vwi.extract_witness_addr_from_binary_bytes(str(bin_8735))

            # Variant 3: both 0xF7A0 and 0x8735 together
            payload_both = bytearray(canonical_payload)
            payload_both[12:14] = struct.pack("<H", 0xF7A0)
            payload_both[16:18] = struct.pack("<H", 0x8735)
            bin_both = td_path / "payload_both.bin"
            bin_both.write_bytes(bytes(payload_both))

            # Direct decoder check
            addr_v3, err_v3 = ptp.decode_inspector_payload_witness_addr_details(bytes(payload_both))
            self.assertIsNone(addr_v3)
            self.assertIsNotNone(err_v3)
            self.assertIn("bit 15", err_v3)

            # Preflight tool check
            exit_code_v3, report_v3 = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bin_both),
            )
            self.assertEqual(exit_code_v3, 1, "Both 0xF7A0 and 0x8735 together must fail preflight")
            self.assertEqual(report_v3["verdict"], "FAIL")
            check_v3 = report_v3["checks_by_name"]["inspector_payload_witness"]
            self.assertFalse(check_v3["pass"])
            self.assertEqual(check_v3["status"], "FAIL")
            self.assertEqual(check_v3["actual"], "None")
            self.assertIn("bit 15", check_v3["reason"])

            # Validator binary check
            with self.assertRaises(ValueError):
                vwi.extract_witness_addr_from_binary_bytes(str(bin_both))


if __name__ == "__main__":
    unittest.main()
