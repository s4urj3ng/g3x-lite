#!/usr/bin/env python3
"""PORT-19 T3: Verification of Boot Witness Address Alignment (P6 Resolution).

Asserts that:
1. The built candidate (candidate_main.elf symbol table, candidate_manifest.json),
2. The preflight tool (tools/port18_trial_preflight.py), and
3. The witness inspector (tools, metadata, and payload binary)
agree on boot_witness = 0x0035F7A0 (.data section, 16-byte aligned, 32 bytes).

Verifies fail-closed behavior:
- If 0x0035F780 is reintroduced in symbols, maps, metadata, or inspector payload,
  the inspector, preflight tool, and candidate validator fail with hard errors.
"""

from __future__ import annotations

import json
import os
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

sys.path.insert(0, str(TOOLS_DIR))
import build_candidate_port2a as bcp
import validate_candidate_port2a as vcp
import build_witness_inspector as bwi
import validate_witness_inspector as vwi
import port18_trial_preflight as ptp

PINNED_BOOT_WITNESS_ADDR = 0x0035F7A0
STALE_PRECORRECTION_ADDR = 0x0035F780


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
        """All tools define EXPECTED_BOOT_WITNESS_ADDR as 0x0035F7A0, never 0x0035F780."""
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
            self.assertNotEqual(tool_const, STALE_PRECORRECTION_ADDR)

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
        self.assertNotEqual(witness_addr, STALE_PRECORRECTION_ADDR)
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
        self.assertNotEqual(arch.get("boot_witness_addr"), "0x0035F780")

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
        self.assertNotEqual(meta["witness_address"], "0x0035F780")

        # Payload binary MOVW/MOVT opcode decode
        decoded_addr = vwi.extract_witness_addr_from_binary_bytes(str(bin_path))
        self.assertEqual(decoded_addr, PINNED_BOOT_WITNESS_ADDR)
        self.assertNotEqual(decoded_addr, STALE_PRECORRECTION_ADDR)

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

        # Absence of 0x0035F780
        for addr in [candidate_addr, preflight_expected, inspector_val_expected, meta_addr, payload_addr]:
            self.assertNotEqual(addr, STALE_PRECORRECTION_ADDR)

    def test_preflight_tool_passes_candidate_and_rejects_0035f780(self):
        """Preflight tool accepts 0x0035F7A0 candidate symbols and rejects 0x0035F780 with exit 1."""
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

            # Stale 0x0035F780 in symbol table fails closed with exit code 1
            bad_symbols = Path(td) / "bad_symbols.nm"
            bad_symbols.write_text(
                "003489b4 T _start\n"
                "0035f780 D boot_witness\n"
                "00366cb0 B _end\n"
            )
            bad_exit, bad_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(bad_symbols),
            )
            self.assertEqual(bad_exit, 1, "Preflight must fail on stale 0x0035F780 symbols")
            self.assertEqual(bad_report["verdict"], "FAIL")
            self.assertFalse(bad_report["checks_by_name"]["boot_witness"]["pass"])
            self.assertEqual(bad_report["checks_by_name"]["boot_witness"]["actual"], "0x0035F780")

            # Stale 0x0035F780 in metadata fails closed with exit code 1
            bad_meta = Path(td) / "bad_meta.json"
            bad_meta.write_text(json.dumps({"witness_address": "0x0035F780"}))
            meta_exit, meta_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_metadata_path=str(bad_meta),
            )
            self.assertEqual(meta_exit, 1, "Preflight must fail on stale 0x0035F780 inspector metadata")
            self.assertEqual(meta_report["verdict"], "FAIL")
            self.assertFalse(meta_report["checks_by_name"]["inspector_metadata_witness"]["pass"])
            self.assertEqual(meta_report["checks_by_name"]["inspector_metadata_witness"]["actual"], "0x0035F780")

            # Stale 0x0035F780 in inspector payload binary fails closed with exit code 1
            bad_bin = Path(td) / "bad_inspector.bin"
            bad_bin.write_bytes(create_mock_payload_bytes(STALE_PRECORRECTION_ADDR))
            bin_exit, bin_report = ptp.run_preflight(
                binary_path=str(diskboot),
                symbols_path=str(symbols_txt),
                inspector_bin_path=str(bad_bin),
            )
            self.assertEqual(bin_exit, 1, "Preflight must fail on stale 0x0035F780 inspector payload binary")
            self.assertEqual(bin_report["verdict"], "FAIL")
            self.assertFalse(bin_report["checks_by_name"]["inspector_payload_witness"]["pass"])
            self.assertEqual(bin_report["checks_by_name"]["inspector_payload_witness"]["actual"], "0x0035F780")

    def test_inspector_validator_rejects_0035f780(self):
        """Inspector validator fails closed when encountering 0x0035F780 in metadata or payload."""
        payload_bin = CANDIDATE_DIR / "witness_inspector_payload.bin"
        payload_o = CANDIDATE_DIR / "witness_inspector_payload.o"
        core_elf = CANDIDATE_DIR / "candidate_main.elf"

        # Stale metadata targeting 0x0035F780 raises AssertionError
        with tempfile.TemporaryDirectory() as td:
            stale_meta = Path(td) / "stale_meta.json"
            stale_meta.write_text(
                json.dumps(
                    {
                        "target": "Canon PowerShot G3 X (GM1.10C)",
                        "symbol": "boot_witness",
                        "witness_address": "0x0035F780",
                        "witness_address_int": 3536768,
                        "payload_size": 444,
                    }
                )
            )
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=str(payload_bin),
                    payload_elf=str(payload_o),
                    elf_path=str(core_elf),
                    metadata_path=str(stale_meta),
                    expected_witness_addr=PINNED_BOOT_WITNESS_ADDR,
                )
            self.assertIn("0x0035F780", str(ctx.exception))

        # Stale payload binary targeting 0x0035F780 raises AssertionError
        with tempfile.TemporaryDirectory() as td:
            stale_payload = Path(td) / "stale_payload.bin"
            stale_payload.write_bytes(create_mock_payload_bytes(STALE_PRECORRECTION_ADDR))
            with self.assertRaises(AssertionError) as ctx:
                vwi.validate_payload_binary(
                    payload_bin=str(stale_payload),
                    payload_elf=str(payload_o),
                    elf_path=str(core_elf),
                    expected_witness_addr=PINNED_BOOT_WITNESS_ADDR,
                )
            err_msg = str(ctx.exception)
            self.assertTrue(
                "0x0035F780" in err_msg or "does not match" in err_msg,
                f"Expected mismatch error, got: {err_msg}",
            )

    def test_inspector_builder_rejects_0035f780_symbol_table(self):
        """Inspector builder extract_witness_addr_from_elf rejects 0x0035F780 with ValueError."""
        with tempfile.TemporaryDirectory() as td:
            dummy_elf = Path(td) / "dummy.elf"
            dummy_elf.touch()

            def mock_run(*args, **kwargs):
                class MockRes:
                    stdout = b"0035f780 D boot_witness\n"
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
                self.assertIn("0x0035F780", str(ctx.exception))
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
            self.assertEqual(check["reason"], "Failed to decode MOVW/MOVT opcodes")


if __name__ == "__main__":
    unittest.main()
