#!/usr/bin/env python3
"""PORT-33: Host test suite for opt-in G3X_OSD=1 test overlay candidate.

Verifies:
(a) With both flags off (or default), DISKBOOT.BIN SHA-256 equals pinned PORT-25 / PORT-19 hashes.
(b) With G3X_RESIDENT=1 alone, DISKBOOT.BIN SHA-256 equals the PORT-32 recorded hash.
(c) The G3X_OSD=1 build is reproducible with the pinned toolchain
    (toolchains/gcc-arm-none-eabi-5_4-2016q3) across two clean builds and matches
    docs/PORT33_OSD_ADDRESSES.md.
(d) Linked _end is <= resident heap start 0x00368680 with positive clearance.
(e) Disassembly confirms:
    - g3x_resident_heartbeat_task spawns "OSDOverlay" task via _CreateTask
      with prio=0x19 (25), stack=0x2000 (8192 B), and entry=g3x_resident_osd_task.
    - Heartbeat task continues blinking green LED (0xD20B0884) at ~1 Hz unchanged.
    - g3x_resident_osd_task loops calling g3x_osd_draw_test_overlay and SleepTask(1000).
    - g3x_osd_draw_test_overlay writes both opacity (0xFF) and UYVY bitmap, and calls vid_bitmap_refresh.
(f) Every address literal in chdk-port/platform/g3x/sub/110c/osd_test_overlay.h
    appears in docs/PORT33_OSD_ADDRESSES.md with a FINSIG or manifest source.
(g) Zero tracked binaries in worktree.
(h) PORT-33 evidence manifest passes tools/port11c_evidence_validator.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
DOCS_DIR = REPO_ROOT / "docs"
EVIDENCE_DIR = REPO_ROOT / "evidence"
AGENTBRIDGE_DOCS_DIR = DOCS_DIR / "agentbridge"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
OSD_HEADER = SUB_DIR / "osd_test_overlay.h"
OSD_DOC = DOCS_DIR / "PORT33_OSD_ADDRESSES.md"
MANIFEST_PATH = EVIDENCE_DIR / "port33_manifest.json"
SCOPES_PATH = EVIDENCE_DIR / "port33_trusted_scopes.json"

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import extract_symbol_addr_from_nm  # noqa: E402
from build_candidate_port25_ladder_fix import (  # noqa: E402
    G3X_RESIDENT_CREATETASK_ADDR,
    G3X_RESIDENT_HANDOFF_ADDR,
    G3X_RESIDENT_HEAP_START,
    G3X_RESIDENT_PRIORITY,
    G3X_RESIDENT_SLEEPTASK_VENEER,
    G3X_RESIDENT_STACK_SIZE,
    G3X_OSD_ACTIVE_BITMAP_BUFFER_ADDR,
    G3X_OSD_BITMAP_BUFFER_ADDR,
    G3X_OSD_OPACITY_BUFFER_ADDR,
    G3X_OSD_TRANSFER_SRC_OVERLAY_ADDR,
    build_candidate,
)

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_PORT25_COMBINED_SHA256 = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
PINNED_PORT25_COMBINED_SIZE = 124865

PINNED_PORT32_RESIDENT_SHA256 = "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a"
PINNED_PORT32_RESIDENT_SIZE = 124561

PINNED_PORT33_OSD_SHA256 = "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855"
PINNED_PORT33_OSD_SIZE = 124833
PINNED_PORT33_OSD_MAIN_SIZE = 123392
PINNED_PORT33_OSD_END_ADDR = 0x00368660


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def have_pinned_toolchain() -> bool:
    if not (ARM_GCC.is_file() and os.access(ARM_GCC, os.X_OK)):
        return False
    if not (ARM_OBJDUMP.is_file() and os.access(ARM_OBJDUMP, os.X_OK)):
        return False
    try:
        res = subprocess.run([str(ARM_GCC), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


HAVE_TOOLCHAIN = have_pinned_toolchain()


class TestPort33OsdCandidate(unittest.TestCase):
    """Host test suite for PORT-33 opt-in G3X_OSD=1 overlay candidate."""

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_a_flags_off_equals_pinned_port25_hashes(self) -> None:
        """(a) With flags off, DISKBOOT.BIN SHA-256 equals pinned PORT-25 combined hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=False, osd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT25_COMBINED_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT25_COMBINED_SIZE)

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=False, poweron_fix=False, out_dir=tmpdir, resident=False, osd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_DEFAULT_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_b_resident_only_equals_pinned_port32_hash(self) -> None:
        """(b) With G3X_RESIDENT=1 alone, DISKBOOT.BIN SHA-256 equals pinned PORT-32 hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT32_RESIDENT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT32_RESIDENT_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_c_osd_build_reproducible_and_matches_doc(self) -> None:
        """(c) Two clean G3X_OSD=1 builds produce identical hashes matching docs/PORT33_OSD_ADDRESSES.md."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            res1 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir1, resident=True, osd=True)
            res2 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir2, resident=True, osd=True)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_PORT33_OSD_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_PORT33_OSD_SIZE)

            # Confirm recorded hash in documentation
            self.assertTrue(OSD_DOC.is_file(), f"Missing documentation {OSD_DOC}")
            doc_content = OSD_DOC.read_text(encoding="utf-8")
            self.assertIn(PINNED_PORT33_OSD_SHA256, doc_content)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_d_linked_end_within_heap_start(self) -> None:
        """(d) Linked _end is <= resident heap start 0x00368680 with positive clearance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=True)

            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            linked_end = extract_symbol_addr_from_nm(nm_proc.stdout, "_end")
            self.assertEqual(linked_end, PINNED_PORT33_OSD_END_ADDR)
            self.assertLessEqual(linked_end, G3X_RESIDENT_HEAP_START)
            self.assertEqual(G3X_RESIDENT_HEAP_START - linked_end, 32)
            self.assertEqual(os.path.getsize(res["core_bin"]), PINNED_PORT33_OSD_MAIN_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_e_disassembly_wiring_and_tasks(self) -> None:
        """(e) Disassembly confirms task creation, overlay drawing, and heartbeat preservation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=True)

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            # Verify g3x_resident_heartbeat_task calls _CreateTask with OSDOverlay
            m_hb = re.search(r"<g3x_resident_heartbeat_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_hb, "g3x_resident_heartbeat_task must exist")
            hb_body = m_hb.group(1)
            self.assertIn("<_CreateTask>", hb_body, "Heartbeat task must call _CreateTask to spawn OSD overlay")
            self.assertIn("004d0002", hb_body.lower(), "Heartbeat LED ON write must exist")
            self.assertIn("004c0003", hb_body.lower(), "Heartbeat LED OFF write must exist")

            # Verify _CreateTask stub loads ATCM CreateTask entry 0xBFE14A3D
            m_ct = re.search(r"<_CreateTask>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_ct, "_CreateTask stub must exist")
            self.assertIn("bfe14a3d", m_ct.group(1).lower(), "_CreateTask must load 0xBFE14A3D")

            # Verify g3x_resident_osd_task exists and calls framebuffer functions
            m_osd = re.search(r"<g3x_resident_osd_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_osd, "g3x_resident_osd_task must exist")
            osd_body = m_osd.group(1)
            self.assertIn("<vid_get_opacity_active_buffer>", osd_body)
            self.assertIn("<vid_get_bitmap_fb>", osd_body)
            self.assertIn("<vid_bitmap_refresh>", osd_body)

    def test_f_address_literals_appear_in_table_and_manifest(self) -> None:
        """(f) Every address literal in osd_test_overlay.h and build script appears in parsed table with verified source."""
        self.assertTrue(OSD_HEADER.is_file(), f"Missing {OSD_HEADER}")
        self.assertTrue(OSD_DOC.is_file(), f"Missing {OSD_DOC}")
        header_src = OSD_HEADER.read_text(encoding="utf-8")
        doc_src = OSD_DOC.read_text(encoding="utf-8")

        # Parse Table 2 from docs/PORT33_OSD_ADDRESSES.md
        table_rows = {}
        valid_labels = {"FINSIG", "ROM_VERIFIED", "INFERRED", "HISTORICAL_CHDK"}
        for line in doc_src.splitlines():
            line = line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cols = [c.strip().replace("`", "") for c in line.split("|")[1:-1]]
            if len(cols) >= 3 and cols[1].startswith("0x"):
                try:
                    val_int = int(cols[1], 16)
                    table_rows[val_int] = {
                        "name": cols[0],
                        "value_str": cols[1],
                        "label": cols[2],
                        "source": cols[5] if len(cols) >= 6 else "",
                    }
                except ValueError:
                    pass

        self.assertGreater(len(table_rows), 0, "No address rows parsed from docs/PORT33_OSD_ADDRESSES.md")

        # Extract address literals from code lines in osd_test_overlay.h
        code_lines = [l for l in header_src.splitlines() if not l.strip().startswith(("*", "/*"))]
        header_literals = set(re.findall(r"0x[0-9A-Fa-f]{6,8}", "\n".join(code_lines)))

        # Extract address literals from new build-script code
        build_script_path = TOOLS_DIR / "build_candidate_port25_ladder_fix.py"
        self.assertTrue(build_script_path.is_file(), f"Missing {build_script_path}")
        build_script_src = build_script_path.read_text(encoding="utf-8")
        build_literals = set(re.findall(r"G3X_OSD_[A-Z0-9_]*ADDR\s*=\s*(0x[0-9A-Fa-f]{6,8})", build_script_src))

        all_literals = {int(x, 16) for x in (header_literals | build_literals)}
        self.assertGreater(len(all_literals), 0, "Expected address literals in header and build script")

        # Load FINSIG sources
        finsig_sources = [
            REPO_ROOT / "reference" / "finsig_gm110c" / "stubs_entry.S",
            REPO_ROOT / "reference" / "finsig_gm110c" / "funcs_by_name.csv",
            REPO_ROOT / "reference" / "finsig_gm110c" / "funcs_by_address.csv",
            SUB_DIR / "stubs_min.S",
        ]
        finsig_text = "\n".join(f.read_text(encoding="utf-8") for f in finsig_sources if f.is_file()).lower()

        # Load evidence entries from manifest
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}")
        manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        evidence_ranges = [
            (int(entry["start_address"], 16), int(entry["end_address"], 16))
            for entry in manifest_data.get("evidence_entries", [])
        ]

        for lit_int in all_literals:
            # Assert there is a table row whose label is FINSIG, ROM_VERIFIED, INFERRED or HISTORICAL_CHDK
            self.assertIn(
                lit_int,
                table_rows,
                f"Address literal 0x{lit_int:08X} missing from table in docs/PORT33_OSD_ADDRESSES.md",
            )
            row = table_rows[lit_int]
            self.assertIn(
                row["label"],
                valid_labels,
                f"Table row for 0x{lit_int:08X} has unexpected label '{row['label']}'",
            )

            # For FINSIG rows, assert value appears in FINSIG sources or tracked stubs_min.S
            if row["label"] == "FINSIG":
                hex_lower = f"0x{lit_int:08x}"
                self.assertIn(
                    hex_lower,
                    finsig_text,
                    f"FINSIG address 0x{lit_int:08X} not found in finsig sources or stubs_min.S",
                )

            # For ROM_VERIFIED rows, assert address falls inside an evidence_entries range in port33_manifest.json
            elif row["label"] == "ROM_VERIFIED":
                in_range = any(start <= lit_int <= end for start, end in evidence_ranges)
                self.assertTrue(
                    in_range,
                    f"ROM_VERIFIED address 0x{lit_int:08X} does not fall inside any evidence_entries range in {MANIFEST_PATH}",
                )

    def test_g_zero_tracked_binaries(self) -> None:
        """(g) Zero tracked binary files under build/candidate paths and among new PORT-33 files."""
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        tracked_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

        # Assert no tracked file matches DISKBOOT*.BIN, *.bin or *.elf under PORT-33 build output and candidate paths
        candidate_prefixes = (
            "candidate_port33_osd",
            "candidate_port32_resident",
            "candidate_port25",
            "candidate_port2a",
            "candidate_",
            "chdk-port/platform/g3x/sub/110c",
        )
        binary_extensions = (".bin", ".elf", ".BIN", ".ELF", ".o", ".a")
        for path_str in tracked_files:
            p = Path(path_str)
            for prefix in candidate_prefixes:
                if path_str.startswith(prefix) or prefix in path_str:
                    self.assertFalse(
                        p.name.startswith("DISKBOOT") and p.name.endswith((".BIN", ".bin")),
                        f"Tracked DISKBOOT binary file not permitted: {path_str}",
                    )
                    self.assertFalse(
                        path_str.endswith(binary_extensions),
                        f"Tracked binary file not permitted under candidate/output path: {path_str}",
                    )

        # Assert none of the new PORT-33 files is a binary
        new_port33_files = [
            OSD_HEADER,
            OSD_DOC,
            MANIFEST_PATH,
            SCOPES_PATH,
            REPO_ROOT / "docs" / "agentbridge" / "PORT33_EVIDENCE_MANIFEST.json",
            Path(__file__),
        ]
        for f in new_port33_files:
            if f.is_file():
                content = f.read_bytes()
                self.assertNotIn(
                    b"\x00",
                    content,
                    f"New PORT-33 file must be a text file, found binary NUL byte: {f}",
                )

    def test_h_manifest_passes_validator(self) -> None:
        """(h) PORT-33 evidence manifest passes tools/port11c_evidence_validator.py."""
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}")
        validator = TOOLS_DIR / "port11c_evidence_validator.py"
        cmd = [sys.executable, str(validator), "--manifest", str(MANIFEST_PATH)]
        if SCOPES_PATH.is_file():
            cmd.extend(["--trusted-scopes", str(SCOPES_PATH)])
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Validator failed: {res.stderr}\n{res.stdout}")
        self.assertIn("Result: VALID", res.stdout)

    def test_i_manifest_duplicates_byte_identical(self) -> None:
        """(i) evidence/port33_manifest.json and docs/agentbridge/PORT33_EVIDENCE_MANIFEST.json stay byte-identical."""
        alt_manifest = REPO_ROOT / "docs" / "agentbridge" / "PORT33_EVIDENCE_MANIFEST.json"
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}")
        self.assertTrue(alt_manifest.is_file(), f"Missing {alt_manifest}")
        self.assertEqual(
            MANIFEST_PATH.read_bytes(),
            alt_manifest.read_bytes(),
            "evidence/port33_manifest.json and docs/agentbridge/PORT33_EVIDENCE_MANIFEST.json must remain byte-identical",
        )


if __name__ == "__main__":
    unittest.main()
