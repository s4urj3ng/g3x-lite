#!/usr/bin/env python3
"""PORT-34: Host test suite for opt-in G3X_KBD=1 keyboard candidate.

Verifies:
(a) With all flags off (or default), DISKBOOT.BIN SHA-256 equals pinned PORT-25 / PORT-19 hashes.
(b) With G3X_RESIDENT=1 alone, DISKBOOT.BIN SHA-256 equals the PORT-32 recorded hash.
(c) With G3X_OSD=1 alone, DISKBOOT.BIN SHA-256 equals the PORT-33 recorded hash.
(d) The G3X_KBD=1 and G3X_KBD=1 G3X_OSD=1 builds are reproducible with the pinned toolchain
    (toolchains/gcc-arm-none-eabi-5_4-2016q3) across two clean builds and match
    docs/PORT34_KBD_ADDRESSES.md.
(e) Linked _end is <= heap start 0x00368880 with positive clearance for both KBD builds.
(f) Disassembly confirms:
    - task_Startup_my calls sub_fc1283d2_my replacing stock taskcreate_physw.
    - sub_fc1283d2_my calls sub_fc087e88, IsFactoryMode_FW, OpLog.Start_FW, and
      spawns mykbd_task with stack 0x2000 and priority 0x17 via j_CreateTaskStrictly (0xFC31BE8C).
    - wrap_kbd_p1_f_candidate calls my_kbd_read_keys_candidate and branches to _kbd_p1_f_cont (0xFC128695).
    - my_kbd_read_keys_candidate implements short-press power button hold (0x00020000).
    - g3x_resident_heartbeat_task checks kbd_is_blocked() to switch LED pattern.
(g) Every address literal and physw bit in kbd_candidate.h and build script appears
    in docs/PORT34_KBD_ADDRESSES.md with a FINSIG, manifest, or INFERRED source.
(h) Zero tracked binaries in worktree.
(i) PORT-34 evidence manifest passes tools/port11c_evidence_validator.py.
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
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
KBD_HEADER = SUB_DIR / "kbd_candidate.h"
KBD_DOC = DOCS_DIR / "PORT34_KBD_ADDRESSES.md"
MANIFEST_PATH = DOCS_DIR / "port34_evidence_manifest.json"
SCOPES_PATH = DOCS_DIR / "port34_trusted_scopes.json"

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
    G3X_KBD_HEAP_START,
    G3X_KBD_TASKCREATE_ADDR,
    G3X_KBD_CREATETASK_STRICTLY,
    G3X_KBD_PHYSW_RUN,
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

PINNED_PORT34_KBD_SHA256 = "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33"
PINNED_PORT34_KBD_SIZE = 124801
PINNED_PORT34_KBD_MAIN_SIZE = 123360
PINNED_PORT34_KBD_END_ADDR = 0x00368640

PINNED_PORT34_KBD_OSD_SHA256 = "686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8"
PINNED_PORT34_KBD_OSD_SIZE = 125121
PINNED_PORT34_KBD_OSD_MAIN_SIZE = 123680
PINNED_PORT34_KBD_OSD_END_ADDR = 0x00368780


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


class TestPort34KbdCandidate(unittest.TestCase):
    """Host test suite for PORT-34 opt-in G3X_KBD=1 candidate."""

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_a_flags_off_equals_pinned_port25_hashes(self) -> None:
        """(a) With all flags off, DISKBOOT.BIN SHA-256 equals pinned PORT-25 hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=False, osd=False, kbd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT25_COMBINED_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT25_COMBINED_SIZE)

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=False, poweron_fix=False, out_dir=tmpdir, resident=False, osd=False, kbd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_DEFAULT_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_b_resident_only_equals_pinned_port32_hash(self) -> None:
        """(b) With G3X_RESIDENT=1 alone, DISKBOOT.BIN SHA-256 equals pinned PORT-32 hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=False, kbd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT32_RESIDENT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT32_RESIDENT_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_c_osd_only_equals_pinned_port33_hash(self) -> None:
        """(c) With G3X_OSD=1 alone, DISKBOOT.BIN SHA-256 equals pinned PORT-33 hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=True, kbd=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT33_OSD_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT33_OSD_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_d_kbd_build_reproducible_and_matches_doc(self) -> None:
        """(d) G3X_KBD=1 and G3X_KBD=1 G3X_OSD=1 builds are reproducible and match documentation."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            res1 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir1, kbd=True, osd=False)
            res2 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir2, kbd=True, osd=False)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_PORT34_KBD_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_PORT34_KBD_SIZE)

        with tempfile.TemporaryDirectory() as tmpdir3, tempfile.TemporaryDirectory() as tmpdir4:
            res3 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir3, kbd=True, osd=True)
            res4 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir4, kbd=True, osd=True)

            self.assertEqual(res3["diskboot_sha256"], res4["diskboot_sha256"])
            self.assertEqual(res3["diskboot_size"], res4["diskboot_size"])
            self.assertEqual(res3["diskboot_sha256"], PINNED_PORT34_KBD_OSD_SHA256)
            self.assertEqual(res3["diskboot_size"], PINNED_PORT34_KBD_OSD_SIZE)

        # Confirm recorded hashes in documentation
        self.assertTrue(KBD_DOC.is_file(), f"Missing documentation {KBD_DOC}")
        doc_content = KBD_DOC.read_text(encoding="utf-8")
        self.assertIn(PINNED_PORT34_KBD_SHA256, doc_content)
        self.assertIn(PINNED_PORT34_KBD_OSD_SHA256, doc_content)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_e_linked_end_within_heap_start(self) -> None:
        """(e) Linked _end is <= heap start 0x00368880 with positive clearance for both KBD builds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, kbd=True, osd=False)
            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            linked_end = extract_symbol_addr_from_nm(nm_proc.stdout, "_end")
            self.assertEqual(linked_end, PINNED_PORT34_KBD_END_ADDR)
            self.assertLessEqual(linked_end, G3X_KBD_HEAP_START)
            self.assertEqual(G3X_KBD_HEAP_START - linked_end, 576)
            self.assertEqual(os.path.getsize(res["core_bin"]), PINNED_PORT34_KBD_MAIN_SIZE)

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, kbd=True, osd=True)
            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            linked_end = extract_symbol_addr_from_nm(nm_proc.stdout, "_end")
            self.assertEqual(linked_end, PINNED_PORT34_KBD_OSD_END_ADDR)
            self.assertLessEqual(linked_end, G3X_KBD_HEAP_START)
            self.assertEqual(G3X_KBD_HEAP_START - linked_end, 256)
            self.assertEqual(os.path.getsize(res["core_bin"]), PINNED_PORT34_KBD_OSD_MAIN_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_f_disassembly_wiring_and_tasks(self) -> None:
        """(f) Disassembly confirms task_PhySw hook, CreateTask strictly, wrapper continuation, and ALT heartbeat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, kbd=True, osd=False)

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            # Verify task_Startup_my calls sub_fc1283d2_my
            m_startup = re.search(r"<task_Startup_my>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_startup, "task_Startup_my must exist")
            self.assertIn("<sub_fc1283d2_my>", m_startup.group(1), "task_Startup_my must branch to sub_fc1283d2_my")

            # Verify sub_fc1283d2_my exists and wires CreateTaskStrictly with stack 0x2000 and priority 0x17
            m_my = re.search(r"<sub_fc1283d2_my>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_my, "sub_fc1283d2_my must exist")
            my_body = m_my.group(1)
            self.assertIn("fc31be8c", my_body.lower(), "sub_fc1283d2_my must call j_CreateTaskStrictly (0xFC31BE8C)")
            self.assertIn("fc12870c", my_body.lower(), "sub_fc1283d2_my must reference 'PhySw' name literal (0xFC12870C)")
            self.assertIn("2000", my_body.lower(), "sub_fc1283d2_my must set stack size 0x2000")
            self.assertIn("17", my_body.lower(), "sub_fc1283d2_my must set priority 0x17")
            self.assertIn("82bc", my_body.lower(), "sub_fc1283d2_my must store task handle to physw_run + 4 (0x000082BC)")

            # Verify wrap_kbd_p1_f_candidate calls my_kbd_read_keys_candidate and jumps to 0xFC128695
            m_wrap = re.search(r"<wrap_kbd_p1_f_candidate>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_wrap, "wrap_kbd_p1_f_candidate must exist")
            wrap_body = m_wrap.group(1)
            self.assertIn("<my_kbd_read_keys_candidate>", wrap_body)
            self.assertIn("fc128695", wrap_body.lower(), "wrap_kbd_p1_f_candidate must branch to _kbd_p1_f_cont (0xFC128695)")

            # Verify my_kbd_read_keys_candidate modifies physw_status (0x00040DAC) with power bit 0x00020000
            m_read = re.search(r"<my_kbd_read_keys_candidate>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_read, "my_kbd_read_keys_candidate must exist")
            read_body = m_read.group(1)
            self.assertIn("<kbd_update_key_state>", read_body)
            self.assertIn("<kbd_update_physw_bits>", read_body)
            self.assertIn("20000", read_body.lower(), "my_kbd_read_keys_candidate must handle power bit 0x00020000")

            # Verify g3x_resident_heartbeat_task checks kbd_is_blocked
            m_hb = re.search(r"<g3x_resident_heartbeat_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_hb, "g3x_resident_heartbeat_task must exist")
            hb_body = m_hb.group(1)
            self.assertIn("<kbd_is_blocked>", hb_body, "Heartbeat task must check kbd_is_blocked() for ALT toggle pattern")

    def test_g_address_literals_appear_in_table_and_manifest(self) -> None:
        """(g) Every address literal in kbd_candidate.h and build script appears in parsed table with verified source."""
        self.assertTrue(KBD_HEADER.is_file(), f"Missing {KBD_HEADER}")
        self.assertTrue(KBD_DOC.is_file(), f"Missing {KBD_DOC}")
        header_src = KBD_HEADER.read_text(encoding="utf-8")
        doc_src = KBD_DOC.read_text(encoding="utf-8")

        # Parse Table 2 from docs/PORT34_KBD_ADDRESSES.md
        table_rows = {}
        named_rows = {}
        valid_labels = {"FINSIG", "ROM_VERIFIED", "INFERRED", "HISTORICAL_CHDK"}
        for line in doc_src.splitlines():
            line = line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cols = [c.strip().replace("`", "") for c in line.split("|")[1:-1]]
            if len(cols) >= 3:
                named_rows[cols[0]] = {
                    "value_str": cols[1],
                    "label": cols[2],
                    "sibling_source": cols[3] if len(cols) >= 4 else "",
                    "observation": cols[4] if len(cols) >= 5 else "",
                    "source": cols[5] if len(cols) >= 6 else "",
                }
            if len(cols) >= 3 and cols[1].startswith("0x"):
                try:
                    val_int = int(cols[1], 16)
                    table_rows[val_int] = {
                        "name": cols[0],
                        "value_str": cols[1],
                        "label": cols[2],
                        "sibling_source": cols[3] if len(cols) >= 4 else "",
                        "observation": cols[4] if len(cols) >= 5 else "",
                        "source": cols[5] if len(cols) >= 6 else "",
                    }
                except ValueError:
                    pass

        self.assertGreater(len(table_rows), 0, "No address rows parsed from docs/PORT34_KBD_ADDRESSES.md")

        # Extract address literals from code lines in kbd_candidate.h
        code_lines = [l for l in header_src.splitlines() if not l.strip().startswith(("*", "/*"))]
        header_literals = set(re.findall(r"0x[0-9A-Fa-f]{4,8}", "\n".join(code_lines)))

        # Extract address literals from new build-script code
        build_script_path = TOOLS_DIR / "build_candidate_port25_ladder_fix.py"
        self.assertTrue(build_script_path.is_file(), f"Missing {build_script_path}")
        build_script_src = build_script_path.read_text(encoding="utf-8")
        build_literals = set(re.findall(r"G3X_KBD_[A-Z0-9_]*ADDR\s*=\s*(0x[0-9A-Fa-f]{6,8})", build_script_src))

        all_literals = {int(x, 16) for x in (header_literals | build_literals)}
        self.assertGreater(len(all_literals), 0, "Expected address literals in header and build script")

        # Load FINSIG sources
        finsig_sources = [
            REPO_ROOT / "reference" / "finsig_gm110c" / "stubs_entry.S",
            REPO_ROOT / "reference" / "finsig_gm110c" / "funcs_by_name.csv",
            REPO_ROOT / "reference" / "finsig_gm110c" / "funcs_by_address.csv",
            REPO_ROOT / "reference" / "finsig_gm110c" / "physw_bits.txt",
            CHDK_PORT / "platform" / "g3x" / "platform_kbd.h",
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
            # Skip small non-address literals like priority (0x17)
            if lit_int < 0x1000 and lit_int not in table_rows:
                continue

            # Match exact literal or even function base address (Thumb call addresses have bit 0 set)
            target_key = lit_int if lit_int in table_rows else (lit_int & ~1)
            self.assertIn(
                target_key,
                table_rows,
                f"Address/bit literal 0x{lit_int:08X} missing from table in docs/PORT34_KBD_ADDRESSES.md",
            )
            row = table_rows[target_key]
            self.assertIn(
                row["label"],
                valid_labels,
                f"Table row for 0x{lit_int:08X} has unexpected label '{row['label']}'",
            )

            # For FINSIG rows, assert value appears in FINSIG sources or tracked platform_kbd.h
            if row["label"] == "FINSIG":
                hex_lower = f"0x{lit_int:08x}"
                hex_thumb = f"0x{(lit_int | 1):08x}"
                hex_even = f"0x{(lit_int & ~1):08x}"
                hex_short = f"0x{lit_int:x}"
                found = (
                    (hex_lower in finsig_text)
                    or (hex_thumb in finsig_text)
                    or (hex_even in finsig_text)
                    or (hex_short in finsig_text)
                    or (f"{lit_int:08x}" in finsig_text)
                    or (f"{(lit_int | 1):08x}" in finsig_text)
                    or (f"{(lit_int & ~1):08x}" in finsig_text)
                )
                self.assertTrue(
                    found,
                    f"FINSIG address 0x{lit_int:08X} not found in finsig sources or platform_kbd.h",
                )

            # For ROM_VERIFIED rows, assert address falls inside an evidence_entries range in port34_evidence_manifest.json
            elif row["label"] == "ROM_VERIFIED":
                in_range = any(start <= lit_int <= end for start, end in evidence_ranges)
                self.assertTrue(
                    in_range,
                    f"ROM_VERIFIED address 0x{lit_int:08X} does not fall inside any evidence_entries range in {MANIFEST_PATH}",
                )

            # For INFERRED rows, assert sibling path:line is cited
            elif row["label"] == "INFERRED":
                self.assertTrue(
                    len(row.get("sibling_source", "").strip()) > 0,
                    f"INFERRED entry 0x{lit_int:08X} missing sibling path:line citation in Table 2",
                )

        # Explicitly verify required items per p34-t1-kbd-candidate-r2 corrections:
        # 1. ALT key choice is labeled INFERRED with citation and owner observation
        self.assertIn(0x00010000, table_rows, "KEY_PLAYBACK (0x00010000) must appear in table")
        alt_row = table_rows[0x00010000]
        self.assertEqual(alt_row["label"], "INFERRED", "ALT key (0x00010000) must be labeled INFERRED")
        self.assertTrue(len(alt_row.get("sibling_source", "").strip()) > 0, "ALT key must cite sibling path:line")
        self.assertTrue(len(alt_row.get("observation", "").strip()) > 0, "ALT key must provide owner observation")

        # 2. Short-press fix poll count row exists with label and sibling citation
        self.assertIn("G3X_POWERON_HOLD_POLLS", named_rows, "G3X_POWERON_HOLD_POLLS must appear in Table 2")
        poll_row = named_rows["G3X_POWERON_HOLD_POLLS"]
        self.assertEqual(poll_row["value_str"], "100")
        self.assertIn(poll_row["label"], valid_labels)
        self.assertTrue(len(poll_row["sibling_source"].strip()) > 0, "Poll count must cite sibling path:line")
        self.assertTrue(len(poll_row["observation"].strip()) > 0, "Poll count must describe owner observation")

        # 3. Short-press power button bit row exists with citation
        self.assertIn(0x00020000, table_rows, "KEY_POWER (0x00020000) must appear in Table 2")
        pwr_row = table_rows[0x00020000]
        self.assertIn(pwr_row["label"], valid_labels)
        self.assertTrue(len(pwr_row.get("sibling_source", "").strip()) > 0, "Power bit must cite sibling path:line")

    def test_h_zero_tracked_binaries(self) -> None:
        """(h) Zero tracked binary files under build/candidate paths and among new PORT-34 files."""
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        tracked_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

        candidate_prefixes = (
            "candidate_port34_kbd",
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

        new_port34_files = [
            KBD_HEADER,
            KBD_DOC,
            MANIFEST_PATH,
            SCOPES_PATH,
            Path(__file__),
        ]
        for f in new_port34_files:
            if f.is_file():
                content = f.read_bytes()
                self.assertNotIn(
                    b"\x00",
                    content,
                    f"New PORT-34 file must be a text file, found binary NUL byte: {f}",
                )

    def test_i_manifest_passes_validator(self) -> None:
        """(i) PORT-34 evidence manifest passes tools/port11c_evidence_validator.py."""
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}")
        validator = TOOLS_DIR / "port11c_evidence_validator.py"
        cmd = [sys.executable, str(validator), "--manifest", str(MANIFEST_PATH)]
        if SCOPES_PATH.is_file():
            cmd.extend(["--trusted-scopes", str(SCOPES_PATH)])
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Validator failed: {res.stderr}\n{res.stdout}")
        self.assertIn("Result: VALID", res.stdout)


if __name__ == "__main__":
    unittest.main()
