#!/usr/bin/env python3
"""PORT-35 Part A: Host verification suite for opt-in G3X_OSD2=1 overlay fix candidate.

Verifies all acceptance criteria for Task p35-t1a-osd2-overlay:
1. Prior build invariance: default (PORT-2A), combined (PORT-25), RESIDENT (PORT-32),
   OSD (PORT-33), KBD (PORT-34), and KBD+OSD (PORT-34) equal their pinned SHA-256 hashes.
2. G3X_OSD2=1 builds reproducibly with toolchains/gcc-arm-none-eabi-5_4-2016q3; its SHA-256
   is recorded in docs/PORT35_GUI_ADDRESSES.md; linked _end <= 0x00368880; no binaries committed.
3. The OSD2 draw path uses the active bitmap buffer (vid_get_bitmap_active_buffer and
   vid_get_opacity_active_buffer with active_bitmap_buffer & 1 and opacity_buffer =
   {0x5FC40000, 0x5FB80000}), the 16-bpp UYVY + 8-bpp opacity pixel format and buffer_width (736)
   adapted from g7x/g5x lib.c (cited by path:line), and redraws from the kbd task loop without
   calling vid_bitmap_refresh() after drawing; h1-h3 are INFERRED rows in the table.
4. Every address or constant in the new code appears in the table in docs/PORT35_GUI_ADDRESSES.md
   labelled FINSIG, ROM-manifest, or INFERRED with a sibling path:line citation.
5. ROM reads are recorded in evidence/port35_manifest.json and pass tools/port11c_evidence_validator.py.
6. PORT-34 heartbeat and ALT LED patterns and short-press path are unchanged; LED 0xD20B0884
   is called the power / card-access LED in all new text; only the 'Current milestone' lines
   of docs/HANDOFF.md and docs/PROJECT_STATE.md change to name PORT-35.
"""

from __future__ import annotations

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

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import extract_symbol_addr_from_nm  # noqa: E402
from build_candidate_port25_ladder_fix import (  # noqa: E402
    G3X_KBD_HEAP_START,
    build_candidate,
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
HAVE_TOOLCHAIN = ARM_GCC.is_file() and ARM_OBJDUMP.is_file() and ARM_NM.is_file()

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_PORT25_SHA256 = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
PINNED_PORT32_RESIDENT_SHA256 = "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a"
PINNED_PORT33_OSD_SHA256 = "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855"
PINNED_PORT34_KBD_SHA256 = "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33"
PINNED_PORT34_KBD_OSD_SHA256 = "686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8"

PINNED_PORT35_OSD2_SHA256 = "20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57"
PINNED_PORT35_OSD2_DISKBOOT_SIZE = 125329
PINNED_PORT35_OSD2_MAIN_SIZE = 123888
PINNED_PORT35_OSD2_WITNESS_ADDR = 0x00361340
PINNED_PORT35_OSD2_END_ADDR = 0x00368850

EXPECTED_DISPLAYTYPE_GEOMETRY: dict[int, tuple[int, int, int, int, int]] = {
    0: (640, 480, 640, 640 * 480, 640 * 480),
    1: (720, 480, 736, 720 * 480, 736 * 480),
    2: (720, 480, 736, 720 * 480, 736 * 480),
    3: (640, 480, 640, 640 * 480, 640 * 480),
    4: (640, 480, 640, 640 * 480, 640 * 480),
    5: (640, 480, 640, 640 * 480, 640 * 480),
    6: (960, 540, 960, 960 * 540, 960 * 540),
    7: (960, 540, 960, 960 * 540, 960 * 540),
    8: (720, 480, 736, 720 * 480, 736 * 480),
    9: (720, 480, 736, 720 * 480, 736 * 480),
    10: (720, 480, 736, 720 * 480, 736 * 480),
    11: (1024, 768, 1024, 1024 * 768, 1024 * 768),
    12: (900, 600, 928, 900 * 600, 928 * 600),
}

OSD2_HEADER = SUB_DIR / "osd2_test_overlay.h"
KBD_HEADER = SUB_DIR / "kbd_candidate.h"
PORT35_DOC = DOCS_DIR / "PORT35_GUI_ADDRESSES.md"
MANIFEST_PATH = REPO_ROOT / "evidence" / "port35_manifest.json"
TRUSTED_SCOPES_PATH = REPO_ROOT / "evidence" / "port35_trusted_scopes.json"


def _parse_port35_address_table(doc_text: str) -> list[dict[str, str]]:
    """Parse Section 2 table rows from docs/PORT35_GUI_ADDRESSES.md."""
    in_sec2 = False
    rows: list[dict[str, str]] = []
    for line in doc_text.splitlines():
        s = line.strip()
        if s.startswith("## 2."):
            in_sec2 = True
            continue
        if in_sec2 and s.startswith("## "):
            break
        if not in_sec2 or not s.startswith("|") or not s.endswith("|"):
            continue
        cols = [c.strip() for c in s.split("|")[1:-1]]
        if len(cols) < 5:
            continue
        if cols[0].lower() == "name" or set(cols[0]) <= {":", "-"}:
            continue
        rows.append(
            {
                "name": cols[0].replace("`", ""),
                "value": cols[1].replace("`", ""),
                "label": cols[2].replace("`", ""),
                "sibling": cols[3].replace("`", ""),
                "observation": cols[4],
            }
        )
    return rows


class TestPort35Osd2Candidate(unittest.TestCase):
    """Host test suite for PORT-35 Part A (G3X_OSD2=1 overlay fix)."""

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_a_prior_hashes_invariant(self) -> None:
        """All prior build configurations produce their exact pinned DISKBOOT.BIN SHA-256."""
        configs = [
            ("default", dict(ladder=False, poweron_fix=False, resident=False, osd=False, kbd=False, osd2=False), PINNED_DEFAULT_SHA256),
            ("port25", dict(ladder=True, poweron_fix=True, resident=False, osd=False, kbd=False, osd2=False), PINNED_PORT25_SHA256),
            ("port32_resident", dict(ladder=True, poweron_fix=True, resident=True, osd=False, kbd=False, osd2=False), PINNED_PORT32_RESIDENT_SHA256),
            ("port33_osd", dict(ladder=True, poweron_fix=True, resident=True, osd=True, kbd=False, osd2=False), PINNED_PORT33_OSD_SHA256),
            ("port34_kbd", dict(ladder=True, poweron_fix=True, resident=True, osd=False, kbd=True, osd2=False), PINNED_PORT34_KBD_SHA256),
            ("port34_kbd_osd", dict(ladder=True, poweron_fix=True, resident=True, osd=True, kbd=True, osd2=False), PINNED_PORT34_KBD_OSD_SHA256),
        ]
        for label, kwargs, expected_sha in configs:
            with self.subTest(build=label), tempfile.TemporaryDirectory() as tmpdir:
                res = build_candidate(out_dir=tmpdir, **kwargs)
                self.assertEqual(res["diskboot_sha256"], expected_sha, f"Hash mismatch for {label}")

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_b_osd2_reproducible_build_and_doc_hash(self) -> None:
        """G3X_OSD2=1 builds reproducibly, matches pinned SHA-256 in docs/PORT35_GUI_ADDRESSES.md, and fits below heap base."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            res1 = build_candidate(out_dir=tmp1, osd2=True)
            res2 = build_candidate(out_dir=tmp2, osd2=True)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_PORT35_OSD2_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_PORT35_OSD2_DISKBOOT_SIZE)
            self.assertEqual(os.path.getsize(res1["core_bin"]), PINNED_PORT35_OSD2_MAIN_SIZE)
            self.assertEqual(int(res1["witness_addr"], 16), PINNED_PORT35_OSD2_WITNESS_ADDR)

            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res1["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            linked_end = extract_symbol_addr_from_nm(nm_proc.stdout, "_end")
            self.assertEqual(linked_end, PINNED_PORT35_OSD2_END_ADDR)
            self.assertLessEqual(linked_end, G3X_KBD_HEAP_START)

        doc_text = PORT35_DOC.read_text(encoding="utf-8")
        self.assertIn(PINNED_PORT35_OSD2_SHA256, doc_text)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_c_disassembly_and_osd2_draw_path(self) -> None:
        """OSD2 uses active bitmap/opacity buffers, 16-bpp UYVY + 8-bpp opacity at stride 736, and kbd-loop redraw."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(out_dir=tmpdir, osd2=True)
            disasm = subprocess.check_output(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                text=True,
            )
            rodata = subprocess.check_output(
                [str(ARM_OBJDUMP), "-s", "-j", ".data", res["core_elf"]],
                text=True,
            )

        # Verify opacity_buffer in .data contains 0x5FC40000 and 0x5FB80000 (little-endian: 0000c45f 0000b85f)
        self.assertIn("0000c45f 0000b85f", rodata.lower())

        # Verify vid_get_bitmap_active_buffer masks active_bitmap_buffer (0x0000D2A4) with & 1 and indexes bitmap_buffer (0x0000D2A8)
        m_bmp_act = re.search(r"<vid_get_bitmap_active_buffer>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_bmp_act)
        bmp_act_body = m_bmp_act.group(1).lower()
        self.assertIn("0000d2a4", bmp_act_body)
        self.assertIn("0000d2a8", bmp_act_body)
        self.assertIn("and.w", bmp_act_body)

        # Verify vid_get_opacity_active_buffer masks active_bitmap_buffer (0x0000D2A4) with & 1
        m_op_act = re.search(r"<vid_get_opacity_active_buffer>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_op_act)
        op_act_body = m_op_act.group(1).lower()
        self.assertIn("0000d2a4", op_act_body)
        self.assertIn("and.w", op_act_body)

        # Verify g3x_osd2_update_screen_dimensions reads displaytype (0x00009740) and sets buffer_width 736 (0x2e0)
        m_dim = re.search(r"<g3x_osd2_update_screen_dimensions>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_dim)
        dim_body = m_dim.group(1).lower()
        self.assertIn("00009740", dim_body)
        self.assertIn("#736", dim_body)

        # Verify g3x_osd2_draw_test_overlay calls vid_get_bitmap_active_buffer and vid_get_opacity_active_buffer,
        # writes 16-bit halfwords (strh) with 0xff80 / 0x0080 and 8-bit opacity bytes (strb), and does NOT call vid_bitmap_refresh
        m_draw = re.search(r"<g3x_osd2_draw_test_overlay>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_draw)
        draw_body = m_draw.group(1).lower()
        self.assertIn("<g3x_osd2_update_screen_dimensions>", draw_body)
        self.assertIn("<vid_get_bitmap_active_buffer>", draw_body)
        self.assertIn("<vid_get_opacity_active_buffer>", draw_body)
        self.assertIn("strh", draw_body)
        self.assertIn("strb", draw_body)
        self.assertNotIn("<vid_bitmap_refresh>", draw_body)
        self.assertNotIn("<_transfer_src_overlay>", draw_body)

        # Verify mykbd_task calls kbd_is_blocked and g3x_osd2_draw_test_overlay on every loop iteration
        m_kbd = re.search(r"<mykbd_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_kbd)
        kbd_body = m_kbd.group(1)
        self.assertIn("<kbd_is_blocked>", kbd_body)
        self.assertIn("<g3x_osd2_draw_test_overlay>", kbd_body)

    def test_d_every_address_and_constant_in_table_with_sibling_citation(self) -> None:
        """Every address and constant in osd2_test_overlay.h and G3X_OSD2_* build constants appears in docs/PORT35_GUI_ADDRESSES.md."""
        self.assertTrue(OSD2_HEADER.is_file())
        self.assertTrue(PORT35_DOC.is_file())

        header_text = OSD2_HEADER.read_text(encoding="utf-8")
        doc_text = PORT35_DOC.read_text(encoding="utf-8")
        rows = _parse_port35_address_table(doc_text)
        self.assertGreaterEqual(len(rows), 25)

        valid_labels = {"FINSIG", "ROM-manifest", "INFERRED"}
        by_name: dict[str, dict[str, str]] = {}
        hex_values_in_table: set[int] = set()
        dec_values_in_table: set[int] = set()

        for row in rows:
            self.assertIn(row["label"], valid_labels, f"Invalid label in row: {row}")
            self.assertRegex(
                row["sibling"],
                r"chdk-port/[A-Za-z0-9_./-]+:\d+",
                f"Missing sibling path:line citation in row: {row}",
            )
            self.assertTrue(len(row["observation"]) >= 15, f"Missing owner observation in row: {row}")
            by_name[row["name"]] = row

            for m_hex in re.findall(r"0x[0-9A-Fa-f]+", row["value"]):
                hex_values_in_table.add(int(m_hex, 16))
            for m_dec in re.findall(r"\b\d+\b", row["value"]):
                dec_values_in_table.add(int(m_dec, 10))

        # Verify h1, h2, h3 are present and labelled INFERRED
        for hyp in ("h1", "h2", "h3"):
            matching = [r for r in rows if r["name"].startswith(hyp)]
            self.assertEqual(len(matching), 1, f"Hypothesis {hyp} must appear in table")
            self.assertEqual(matching[0]["label"], "INFERRED")

        # Extract all #define constants and glyph array hex literals from osd2_test_overlay.h
        for m in re.finditer(r"^\s*#define\s+(G3X_OSD2_[A-Z0-9_]+)\s+([^\s/]+)", header_text, re.M):
            macro_name, raw_val = m.group(1), m.group(2).rstrip("uUlL")
            if raw_val.startswith("0x") or raw_val.startswith("0X"):
                val_int = int(raw_val, 16)
                self.assertIn(
                    val_int,
                    hex_values_in_table,
                    f"Hex macro {macro_name}={raw_val} missing from PORT35_GUI_ADDRESSES.md table",
                )
            elif raw_val.isdigit():
                val_int = int(raw_val, 10)
                self.assertIn(
                    val_int,
                    dec_values_in_table,
                    f"Decimal macro {macro_name}={raw_val} missing from PORT35_GUI_ADDRESSES.md table",
                )

        # Check all 4-to-8-digit hex literals in non-comment lines of osd2_test_overlay.h
        non_comment_lines = [
            line for line in header_text.splitlines() if not line.strip().startswith(("/*", "*", "//"))
        ]
        for hex_lit in re.findall(r"0x[0-9A-Fa-f]{4,8}", "\n".join(non_comment_lines)):
            self.assertIn(
                int(hex_lit, 16),
                hex_values_in_table,
                f"Hex literal {hex_lit} in osd2_test_overlay.h missing from table",
            )

        # Verify FINSIG rows match reference/finsig_gm110c/stubs_entry.S
        finsig_text = (REPO_ROOT / "reference" / "finsig_gm110c" / "stubs_entry.S").read_text(encoding="utf-8").lower()
        for row in rows:
            if row["label"] == "FINSIG":
                self.assertIn(row["value"].lower(), finsig_text, f"FINSIG value {row['value']} not in stubs_entry.S")

        # Verify ROM-manifest buffer addresses appear in evidence/port35_manifest.json notes
        manifest_text = MANIFEST_PATH.read_text(encoding="utf-8").lower()
        for addr_str in ("0x5fe80000", "0x5fd00000", "0x5fc40000", "0x5fb80000"):
            self.assertIn(addr_str, manifest_text)

    def test_e_evidence_manifest_passes_validator(self) -> None:
        """evidence/port35_manifest.json passes tools/port11c_evidence_validator.py."""
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertTrue(TRUSTED_SCOPES_PATH.is_file())
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TOOLS_DIR / "port11c_evidence_validator.py"),
                "--manifest",
                str(MANIFEST_PATH),
                "--trusted-scopes",
                str(TRUSTED_SCOPES_PATH),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertIn("Result: VALID (0 errors, 0 warnings)", proc.stdout)

    def test_f_led_wording_milestone_lines_and_no_committed_binaries(self) -> None:
        """Power / card-access LED wording is used, only Current milestone lines changed in HANDOFF/PROJECT_STATE, and no binaries exist."""
        for path in (OSD2_HEADER, PORT35_DOC, TOOLS_DIR / "build_candidate_port25_ladder_fix.py"):
            txt = path.read_text(encoding="utf-8")
            if "0xD20B0884" in txt:
                self.assertIn("power / card-access LED", txt, f"{path.name} must call 0xD20B0884 the power / card-access LED")

        handoff_first = (DOCS_DIR / "HANDOFF.md").read_text(encoding="utf-8").splitlines()[0]
        state_first = (DOCS_DIR / "PROJECT_STATE.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            handoff_first,
            "# Agent handoff — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
        )
        self.assertEqual(
            state_first,
            "# Project state — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
        )

        diff_proc = subprocess.run(
            ["git", "diff", "-U0", "1c33fd7", "--", "docs/HANDOFF.md", "docs/PROJECT_STATE.md"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        changed_lines = []
        for chunk in re.split(r"(?=^diff --git )", diff_proc.stdout, flags=re.M):
            if not chunk.strip():
                continue
            is_handoff = "b/docs/HANDOFF.md" in chunk.splitlines()[0]
            is_project_state = "b/docs/PROJECT_STATE.md" in chunk.splitlines()[0]
            in_later_section = False
            for subhunk in re.split(r"(?=^@@ )", chunk, flags=re.M):
                hunk_lines = [
                    l for l in subhunk.splitlines()
                    if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))
                ]
                if not hunk_lines:
                    continue
                if is_handoff or is_project_state:
                    for l in hunk_lines:
                        if l.startswith("+### PORT-36..PORT-41 Current State"):
                            in_later_section = True
                        else:
                            m = re.match(r"^\+###\s+PORT-3(\d+)", l)
                            if m and int(m.group(1)) >= 7:
                                in_later_section = True
                            elif re.match(r"^[+-]###\s+", l):
                                in_later_section = False
                    if in_later_section and all(l.startswith("+") for l in hunk_lines):
                        continue
                changed_lines.extend(hunk_lines)
        self.assertEqual(
            changed_lines,
            [
                "-# Agent handoff — Current milestone: PORT-33",
                "+# Agent handoff — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
                "-# Project state — Current milestone: PORT-33",
                "+# Project state — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
            ],
        )

        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        for line in status_proc.stdout.splitlines():
            filepath = line[3:].strip()
            self.assertFalse(
                filepath.endswith((".bin", ".elf", ".o", ".a", "DISKBOOT.BIN")),
                f"Binary artifact must not be untracked/modified in worktree: {filepath}",
            )

    def test_g1_displaytype_geometry_static_switch_parser(self) -> None:
        """Statically parse g3x_osd2_update_screen_dimensions switch and verify width, height, buffer_width, size, and buffer_size for displaytype 0..12."""
        header_text = OSD2_HEADER.read_text(encoding="utf-8")
        doc_text = PORT35_DOC.read_text(encoding="utf-8")

        # Verify citations to 0xFC1834F8 jump table and chdk-port/platform/g7x/lib.c:323-332
        self.assertIn("0xFC1834F8", header_text)
        self.assertIn("chdk-port/platform/g7x/lib.c:323-332", header_text)
        self.assertIn("0xFC1834F8", doc_text)
        self.assertIn("chdk-port/platform/g7x/lib.c:323-332", doc_text)

        # Verify camera_screen.size = w * h and camera_screen.buffer_size = bw * h, and row_off uses buf_w
        self.assertIn("camera_screen.size = w * h;", header_text)
        self.assertIn("camera_screen.buffer_size = bw * h;", header_text)
        self.assertIn("int buf_w = camera_screen.buffer_width;", header_text)
        self.assertIn("int row_off = py * buf_w + G3X_OSD2_BOX_X;", header_text)

        # Parse all integer #define macros
        macros: dict[str, int] = {}
        for m in re.finditer(r"^\s*#define\s+(G3X_OSD2_[A-Z0-9_]+)\s+(\d+)\b", header_text, re.M):
            macros[m.group(1)] = int(m.group(2), 10)

        # Extract switch (dt) block in g3x_osd2_update_screen_dimensions
        m_fn = re.search(
            r"void\s+g3x_osd2_update_screen_dimensions\s*\(\s*void\s*\)\s*\{(.*?)\n\}",
            header_text,
            re.DOTALL,
        )
        self.assertIsNotNone(m_fn, "g3x_osd2_update_screen_dimensions not found")
        fn_body = m_fn.group(1)

        m_sw = re.search(r"switch\s*\(\s*dt\s*\)\s*\{(.*?)\n\s*\}", fn_body, re.DOTALL)
        self.assertIsNotNone(m_sw, "switch (dt) block not found in g3x_osd2_update_screen_dimensions")
        sw_body = m_sw.group(1)

        # Parse case groups and their assignments to w, bw, h
        case_map: dict[int, tuple[int, int, int, int, int]] = {}
        pending_cases: list[int] = []
        cur_assigns: dict[str, int] = {}
        for raw_line in sw_body.splitlines():
            line = raw_line.strip()
            m_case = re.match(r"^case\s+(\d+)\s*:$", line)
            if m_case:
                pending_cases.append(int(m_case.group(1), 10))
                continue
            m_assign = re.match(r"^(w|bw|h)\s*=\s*(G3X_OSD2_[A-Z0-9_]+)\s*;$", line)
            if m_assign:
                var_name, macro_name = m_assign.group(1), m_assign.group(2)
                self.assertIn(macro_name, macros, f"Unknown macro {macro_name}")
                cur_assigns[var_name] = macros[macro_name]
                continue
            if line == "break;":
                if pending_cases:
                    w = cur_assigns["w"]
                    h = cur_assigns["h"]
                    bw = cur_assigns["bw"]
                    for dt_val in pending_cases:
                        self.assertNotIn(dt_val, case_map, f"Duplicate case {dt_val}")
                        case_map[dt_val] = (w, h, bw, w * h, bw * h)
                pending_cases = []
                cur_assigns = {}

        for dt in range(13):
            with self.subTest(displaytype=dt):
                self.assertIn(dt, case_map, f"displaytype {dt} missing from switch (dt)")
                self.assertEqual(
                    case_map[dt],
                    EXPECTED_DISPLAYTYPE_GEOMETRY[dt],
                    f"Mismatch for displaytype {dt}: got {case_map[dt]}, expected {EXPECTED_DISPLAYTYPE_GEOMETRY[dt]}",
                )

    def test_g2_displaytype_geometry_host_compiled_harness(self) -> None:
        """Compile a host C harness of g3x_osd2_update_screen_dimensions and verify displaytype 0..12 runtime behavior."""
        host_cc = "gcc"
        try:
            subprocess.run([host_cc, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.skipTest("Host C compiler (gcc) not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "lolevel.h").write_text("/* stub lolevel.h */\n", encoding="utf-8")
            (tmp_path / "platform.h").write_text(
                "#ifndef PLATFORM_H\n"
                "#define PLATFORM_H\n"
                "typedef struct {\n"
                "    int width;\n"
                "    int physical_width;\n"
                "    int height;\n"
                "    int buffer_width;\n"
                "    int buffer_height;\n"
                "    int size;\n"
                "    int buffer_size;\n"
                "} t_camera_screen;\n"
                "extern t_camera_screen camera_screen;\n"
                "#endif\n",
                encoding="utf-8",
            )
            harness_c = tmp_path / "harness.c"
            harness_bin = tmp_path / "harness"
            harness_c.write_text(
                '#include <stdio.h>\n'
                '#include "platform.h"\n'
                "t_camera_screen camera_screen;\n"
                "char *bitmap_buffer[2] = { 0, 0 };\n"
                "int active_bitmap_buffer = 0;\n"
                "int displaytype = 0;\n"
                "void _transfer_src_overlay(int n) { (void)n; }\n"
                '#include "osd2_test_overlay.h"\n'
                "int main(void) {\n"
                "    for (int dt = 0; dt <= 12; dt++) {\n"
                "        displaytype = dt;\n"
                "        g3x_osd2_update_screen_dimensions();\n"
                '        printf("%d:%d,%d,%d,%d,%d,%d,%d\\n",\n'
                "            dt,\n"
                "            camera_screen.width,\n"
                "            camera_screen.physical_width,\n"
                "            camera_screen.height,\n"
                "            camera_screen.buffer_height,\n"
                "            camera_screen.buffer_width,\n"
                "            camera_screen.size,\n"
                "            camera_screen.buffer_size);\n"
                "    }\n"
                "    return 0;\n"
                "}\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    host_cc,
                    "-DG3X_OSD2=1",
                    "-Wno-pointer-to-int-cast",
                    "-Wno-int-to-pointer-cast",
                    f"-I{tmpdir}",
                    f"-I{SUB_DIR}",
                    str(harness_c),
                    "-o",
                    str(harness_bin),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out = subprocess.check_output([str(harness_bin)], text=True)

        results: dict[int, tuple[int, ...]] = {}
        for line in out.strip().splitlines():
            dt_str, vals_str = line.split(":")
            results[int(dt_str)] = tuple(int(v) for v in vals_str.split(","))

        for dt in range(13):
            with self.subTest(displaytype=dt):
                exp_w, exp_h, exp_bw, exp_sz, exp_bsz = EXPECTED_DISPLAYTYPE_GEOMETRY[dt]
                self.assertEqual(
                    results[dt],
                    (exp_w, exp_w, exp_h, exp_h, exp_bw, exp_sz, exp_bsz),
                    f"Host harness mismatch for displaytype {dt}",
                )


if __name__ == "__main__":
    unittest.main()
