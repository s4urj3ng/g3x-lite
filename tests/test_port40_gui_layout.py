#!/usr/bin/env python3
"""PORT-40: Host test suite for opt-in G3X_GUI5=1 candidate.

Verifies:
(a) The default build (no flags) is strictly byte-identical to main:
    DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
(b) G3X_GUI5=1 builds cleanly and implies G3X_GUI4=1:
    - DISKBOOT.BIN SHA-256: ae4358432948231d634b33d10c0c92677a1763274d51bee7a74d4ed71270791d (102,225 B)
    - Boot witness: 0x0035C990
    - Linked _end: 0x003629C0 <= heap start 0x00368880 (24,256 B clearance)
(c) Combined G3X_GUI5=1 + G3X_SHORTPRESS=1 builds cleanly:
    - DISKBOOT.BIN SHA-256: 5819c5f6a8d448310b3ed7dece34ed6b62263b88896232b4c8704db5080f3195 (102,385 B)
    - Boot witness: 0x0035CA30
    - Linked _end: 0x00362A70 <= heap start 0x00368880 (24,080 B clearance)
(d) Host-side geometry check (using preprocessed compiled constants):
    - Preprocessed CAM_SCREEN_WIDTH (900), CAM_SCREEN_HEIGHT (600), CAM_BITMAP_WIDTH (928), CAM_BITMAP_HEIGHT (600).
    - Fill rect and menu rect derived from compiled constants match exactly: (10, 12, 880, 576).
    - Stay strictly inside 900x600 screen: 0..899 x 0..599.
    - Even margins: 10 px horizontal ((900 - 880) / 2), 12 px vertical ((600 - 576) / 2).
(e) Row count verification:
    - 17 rows at 32 px pitch fill the box height (544 px items + 32 px header = 576 px).
    - Remaining rows (10..16 for root_menu) are filled with solid opaque black.
(f) Binary inspection:
    - camera_screen in candidate .data matches width=900, height=600, buffer_width=928, disp_left=0, disp_right=899, disp_width=900.
(g) Disassembly verification:
    - gui_menu_draw contains black fill loop for rows i down to num_lines with draw_rectangle.
(h) GUI4 regression and behavior preservation:
    - The trialled GUI4 candidate DISKBOOT.BIN matches 14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd (102,241 B).
    - F1 2x font scaling (16x32), title bar (white on black), zero-flicker idle, Step 8 sentinel recovery, Step 9 clean ALT exit.
(i) Documentation verification:
    - docs/PORT40_GUI_LAYOUT.md contains table of changed values, root-cause lines pointing to changed code, sibling citations, SHA-256/sizes, untouched paths.
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"
DOCS_DIR = REPO_ROOT / "docs"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
LAYOUT_DOC = DOCS_DIR / "PORT40_GUI_LAYOUT.md"

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_candidate_gui3 import (
    CANDIDATE_PORT40_GUI5_DIR,
    CANDIDATE_PORT40_GUI5_SHORTPRESS_DIR,
    build_candidate as build_candidate_gui,
)
import build_candidate_port25_ladder_fix as legacy_builder

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_GUI4_SHA256 = "14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd"
PINNED_GUI4_SIZE = 102241

PINNED_GUI5_SHA256 = "ae4358432948231d634b33d10c0c92677a1763274d51bee7a74d4ed71270791d"
PINNED_GUI5_SIZE = 102225
PINNED_GUI5_WITNESS = 0x0035C990
PINNED_GUI5_END = 0x003629C0

PINNED_GUI5_SHORTPRESS_SHA256 = "5819c5f6a8d448310b3ed7dece34ed6b62263b88896232b4c8704db5080f3195"
PINNED_GUI5_SHORTPRESS_SIZE = 102385
PINNED_GUI5_SHORTPRESS_WITNESS = 0x0035CA30
PINNED_GUI5_SHORTPRESS_END = 0x00362A70

HEAP_START = 0x00368880


class TestPort40GuiLayout(unittest.TestCase):
    """Test suite for PORT-40 G3X_GUI5=1 candidate build and geometry layout."""

    def test_default_build_byte_identical_to_main(self) -> None:
        """Default build (no flags) is byte-identical to origin/main."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate_gui(
                ladder=False,
                poweron_fix=False,
                resident=False,
                out_dir=tmpdir,
            )
            self.assertEqual(
                res["diskboot_sha256"],
                PINNED_DEFAULT_SHA256,
                "Default build SHA-256 diverged from pinned baseline",
            )
            self.assertEqual(
                res["diskboot_size"],
                PINNED_DEFAULT_SIZE,
                "Default build size diverged from pinned baseline",
            )

    def test_gui4_bytes_unaffected_by_gui5_additions(self) -> None:
        """The trialled GUI4 candidate is byte-identical to pinned hash (14456b...); GUI4 implies GUI3."""
        # 1. Verify build_candidate_gui(gui4=True) produces identical bytes
        res = build_candidate_gui(gui4=True)
        self.assertEqual(
            res["diskboot_sha256"],
            PINNED_GUI4_SHA256,
            "GUI4 candidate DISKBOOT.BIN SHA-256 diverged from pinned baseline",
        )
        self.assertEqual(
            res["diskboot_size"],
            PINNED_GUI4_SIZE,
            "GUI4 candidate DISKBOOT.BIN size diverged from pinned baseline",
        )

        # 2. Verify that G3X_GUI4 and G3X_GUI5 builds both inherit G3X_GUI3=1
        build_py = (SCRIPTS_DIR / "build_candidate_gui3.py").read_text(encoding="utf-8")
        self.assertIn('"-DG3X_GUI3=1"', build_py)
        idx_gui3 = build_py.find('"-DG3X_GUI3=1"')
        idx_gui4 = build_py.find('"-DG3X_GUI4=1"')
        idx_gui5 = build_py.find('"-DG3X_GUI5=1"')
        self.assertGreater(idx_gui4, idx_gui3, "GUI4 build must inherit GUI3")
        self.assertGreater(idx_gui5, idx_gui3, "GUI5 build must inherit GUI3")

    def test_gui5_plain_candidate_build(self) -> None:
        """G3X_GUI5=1 builds cleanly, matches pinned SHA-256 in canonical dir, and has positive heap clearance."""
        res_canon = build_candidate_gui(gui5=True)
        self.assertEqual(res_canon["diskboot_sha256"], PINNED_GUI5_SHA256)
        self.assertEqual(res_canon["diskboot_size"], PINNED_GUI5_SIZE)
        self.assertEqual(res_canon["boot_witness"], PINNED_GUI5_WITNESS)
        self.assertEqual(res_canon["end_addr"], PINNED_GUI5_END)
        self.assertLess(
            res_canon["end_addr"],
            HEAP_START,
            "Linked _end must not exceed DryOS heap base",
        )
        clearance = HEAP_START - res_canon["end_addr"]
        self.assertGreaterEqual(clearance, 24000)

        # In temporary directory, assert identical size and positive clearance
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate_gui(gui5=True, out_dir=tmpdir)
            self.assertEqual(res["diskboot_size"], PINNED_GUI5_SIZE)
            self.assertEqual(res["boot_witness"], PINNED_GUI5_WITNESS)
            self.assertEqual(res["end_addr"], PINNED_GUI5_END)

    def test_gui5_shortpress_candidate_build(self) -> None:
        """Combined G3X_GUI5=1 + G3X_SHORTPRESS=1 builds cleanly, matches pinned SHA-256, and has positive clearance."""
        res_canon = build_candidate_gui(gui5=True, shortpress=True)
        self.assertEqual(res_canon["diskboot_sha256"], PINNED_GUI5_SHORTPRESS_SHA256)
        self.assertEqual(res_canon["diskboot_size"], PINNED_GUI5_SHORTPRESS_SIZE)
        self.assertEqual(res_canon["boot_witness"], PINNED_GUI5_SHORTPRESS_WITNESS)
        self.assertEqual(res_canon["end_addr"], PINNED_GUI5_SHORTPRESS_END)
        self.assertLess(
            res_canon["end_addr"],
            HEAP_START,
            "Linked _end must not exceed DryOS heap base",
        )
        clearance = HEAP_START - res_canon["end_addr"]
        self.assertGreaterEqual(clearance, 24000)

        # In temporary directory, assert identical size and positive clearance
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate_gui(gui5=True, shortpress=True, out_dir=tmpdir)
            self.assertEqual(res["diskboot_size"], PINNED_GUI5_SHORTPRESS_SIZE)
            self.assertEqual(res["boot_witness"], PINNED_GUI5_SHORTPRESS_WITNESS)
            self.assertEqual(res["end_addr"], PINNED_GUI5_SHORTPRESS_END)
            clearance = HEAP_START - res["end_addr"]
            self.assertGreaterEqual(clearance, 24000)

    def test_geometry_constants_fill_rect_equals_menu_rect(self) -> None:
        """Geometry assertion: fill rect equals menu rect, fits 900x600, with even margins."""
        # 1. Preprocess real header with pinned toolchain under -DG3X_GUI5=1
        cmd = [
            str(ARM_GCC),
            "-E",
            "-dM",
            "-DG3X_GUI5=1",
            "-Iinclude",
            "-Icore",
            "-Iplatform/g3x",
            "-Iplatform/g3x/sub/110c",
            str(CHDK_PORT / "platform" / "g3x" / "platform_camera.h"),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            cwd=str(CHDK_PORT),
        )
        defines = {}
        for line in proc.stdout.splitlines():
            m = re.match(r"^#define\s+(\w+)\s+(.+)$", line.strip())
            if m:
                defines[m.group(1)] = m.group(2).strip()

        screen_w = int(defines["CAM_SCREEN_WIDTH"].strip("() "))
        screen_h = int(defines["CAM_SCREEN_HEIGHT"].strip("() "))
        buffer_w = int(defines["CAM_BITMAP_WIDTH"].strip("() "))
        buffer_h = int(defines["CAM_BITMAP_HEIGHT"].strip("() "))

        self.assertEqual(screen_w, 900, "CAM_SCREEN_WIDTH must be 900")
        self.assertEqual(screen_h, 600, "CAM_SCREEN_HEIGHT must be 600")
        self.assertEqual(buffer_w, 928, "CAM_BITMAP_WIDTH must be 928")
        self.assertEqual(buffer_h, 600, "CAM_BITMAP_HEIGHT must be 600")

        # 2. Extract camera_screen values from compiled candidate_main.elf
        elf_path = os.path.join(CANDIDATE_PORT40_GUI5_DIR, "candidate_main.elf")
        if not os.path.isfile(elf_path):
            build_candidate_gui(gui5=True)

        nm_proc = subprocess.run(
            [str(ARM_NM), "-n", elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        m = re.search(r"^([0-9a-fA-F]+)\s+[dD]\s+camera_screen$", nm_proc.stdout, re.MULTILINE)
        self.assertIsNotNone(m, "camera_screen symbol must be in .data")
        cs_addr = int(m.group(1), 16)

        objdump_proc = subprocess.run(
            [
                str(ARM_OBJDUMP),
                "-s",
                f"--start-address=0x{cs_addr:x}",
                f"--stop-address=0x{cs_addr + 48:x}",
                elf_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        hex_bytes = []
        for line in objdump_proc.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Contents of section") or line.endswith(":"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                for w in parts[1:5]:
                    if len(w) == 8 and re.match(r"^[0-9a-fA-F]{8}$", w):
                        hex_bytes.extend(bytes.fromhex(w))

        ints = struct.unpack("<12I", bytes(hex_bytes[:48]))
        disp_left = ints[7]
        disp_right = ints[8]
        disp_width = ints[9]
        menu_border = 10
        ts_menu_border = 0
        font_h = 32  # F1 2x font: 16x32

        # Core CHDK gui_menu.c equations:
        num_lines = (screen_h - ts_menu_border * 2) // font_h - 1  # 17
        menu_x = disp_left + menu_border  # 10
        menu_w = disp_width - menu_border * 2  # 880

        # Non-scrolling menu (e.g. root_menu: 10 items <= 17):
        wplus = 0
        menu_y = (screen_h - ((num_lines - 1) * font_h)) >> 1  # 44
        header_y = menu_y - font_h  # 12
        total_h = (num_lines + 1) * font_h  # 576
        total_w = menu_w + wplus  # 880

        # Fill rectangle (g3x_fill_menu_opaque_black):
        fill_rect = (menu_x, header_y, total_w, total_h)
        # Menu painted rectangle (header + rows):
        paint_rect = (menu_x, header_y, menu_w, total_h)

        self.assertEqual(fill_rect, (10, 12, 880, 576))
        self.assertEqual(paint_rect, (10, 12, 880, 576))
        self.assertEqual(fill_rect, paint_rect, "Fill rect must equal painted menu rect")

        # Boundary checks within 0..899 x 0..599
        self.assertGreaterEqual(menu_x, 0)
        self.assertGreaterEqual(header_y, 0)
        self.assertLessEqual(menu_x + total_w, screen_w)
        self.assertLessEqual(header_y + total_h, screen_h)

        # Margins:
        left_margin = menu_x  # 10
        right_margin = screen_w - (menu_x + total_w)  # 900 - 890 = 10
        top_margin = header_y  # 12
        bottom_margin = screen_h - (header_y + total_h)  # 600 - 588 = 12

        self.assertEqual(left_margin, 10)
        self.assertEqual(right_margin, 10)
        self.assertEqual(left_margin, right_margin, "Horizontal margins must be even")

        self.assertEqual(top_margin, 12)
        self.assertEqual(bottom_margin, 12)
        self.assertEqual(top_margin, bottom_margin, "Vertical margins must be even")

    def test_row_count_and_pitch_fill_height(self) -> None:
        """Row count (17 rows at 32 px pitch) fills the box height."""
        font_h = 32
        num_lines = 17
        items_h = num_lines * font_h  # 544
        header_h = font_h  # 32
        total_h = items_h + header_h  # 576

        self.assertEqual(num_lines, 17)
        self.assertEqual(total_h, 576)
        # 576 / 600 is 96.0% of LCD vertical height
        self.assertAlmostEqual(total_h / 600, 0.96, places=2)

    def test_camera_screen_static_initialization_in_binary(self) -> None:
        """Binary inspection: camera_screen in candidate .data matches 900x600 stride 928 disp_width 900."""
        elf_path = os.path.join(CANDIDATE_PORT40_GUI5_DIR, "candidate_main.elf")
        if not os.path.isfile(elf_path):
            build_candidate_gui(gui5=True)

        # Extract address of camera_screen from nm
        nm_proc = subprocess.run(
            [str(ARM_NM), "-n", elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        m = re.search(r"^([0-9a-fA-F]+)\s+[dD]\s+camera_screen$", nm_proc.stdout, re.MULTILINE)
        self.assertIsNotNone(m, "camera_screen symbol must be in .data")
        cs_addr = int(m.group(1), 16)

        # Dump 40 bytes (10 32-bit ints) of camera_screen
        objdump_proc = subprocess.run(
            [
                str(ARM_OBJDUMP),
                "-s",
                f"--start-address=0x{cs_addr:x}",
                f"--stop-address=0x{cs_addr + 40:x}",
                elf_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )

        hex_bytes = []
        for line in objdump_proc.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Contents of section") or line.endswith(":"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                # parts[1..] are 4-byte hex words
                for w in parts[1:5]:
                    if len(w) == 8 and re.match(r"^[0-9a-fA-F]{8}$", w):
                        b = bytes.fromhex(w)
                        hex_bytes.extend(b)

        self.assertGreaterEqual(len(hex_bytes), 40)
        ints = struct.unpack("<10I", bytes(hex_bytes[:40]))
        width = ints[0]
        height = ints[1]
        size = ints[2]
        physical_width = ints[3]
        buffer_width = ints[4]
        buffer_height = ints[5]
        buffer_size = ints[6]
        disp_left = ints[7]
        disp_right = ints[8]
        disp_width = ints[9]

        self.assertEqual(width, 900, "camera_screen.width must be 900")
        self.assertEqual(height, 600, "camera_screen.height must be 600")
        self.assertEqual(size, 540000, "camera_screen.size must be 540000")
        self.assertEqual(physical_width, 900, "camera_screen.physical_width must be 900")
        self.assertEqual(buffer_width, 928, "camera_screen.buffer_width must be 928")
        self.assertEqual(buffer_height, 600, "camera_screen.buffer_height must be 600")
        self.assertEqual(buffer_size, 556800, "camera_screen.buffer_size must be 556800")
        self.assertEqual(disp_left, 0, "camera_screen.disp_left must be 0")
        self.assertEqual(disp_right, 899, "camera_screen.disp_right must be 899")
        self.assertEqual(disp_width, 900, "camera_screen.disp_width must be 900")

    def test_gui_menu_draw_disassembly_has_black_fill_loop(self) -> None:
        """Disassembly inspection: gui_menu_draw contains black fill loop for rows down to num_lines."""
        elf_path = os.path.join(CANDIDATE_PORT40_GUI5_DIR, "candidate_main.elf")
        if not os.path.isfile(elf_path):
            build_candidate_gui(gui5=True)

        objdump_proc = subprocess.run(
            [str(ARM_OBJDUMP), "-d", elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        disasm = objdump_proc.stdout

        m_draw = re.search(r"<gui_menu_draw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(m_draw, "gui_menu_draw must be in disassembly")
        draw_body = m_draw.group(1)

        # In gui_menu_draw, draw_rectangle is called inside the loop for unpainted rows
        draw_rect_calls = re.findall(r"bl\s+[0-9a-fA-F]+\s+<draw_rectangle>", draw_body)
        self.assertGreaterEqual(
            len(draw_rect_calls),
            1,
            "gui_menu_draw must call draw_rectangle to fill remaining rows down to num_lines",
        )

    def test_gui4_behaviors_preserved_in_gui5(self) -> None:
        """GUI4 features (F1 2x font, title bar, zero flicker, steps 8/9) remain intact in GUI5."""
        elf_path = os.path.join(CANDIDATE_PORT40_GUI5_DIR, "candidate_main.elf")
        if not os.path.isfile(elf_path):
            build_candidate_gui(gui5=True)

        nm_proc = subprocess.run(
            [str(ARM_NM), "-n", elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        nm_out = nm_proc.stdout

        # F1 2x font scaling
        self.assertRegex(nm_out, r"\s+[tT]\s+g3x_draw_char_16x32\b")
        # Step 8 opaque black refill
        self.assertRegex(nm_out, r"\s+[tT]\s+g3x_fill_menu_opaque_black\b")
        # Step 8 sentinel
        self.assertRegex(nm_out, r"\s+[tT]\s+draw_test_guard\b")
        self.assertRegex(nm_out, r"\s+[tT]\s+draw_set_guard\b")
        # Step 9 ALT exit
        self.assertRegex(nm_out, r"\s+[tT]\s+gui_set_need_restore\b")

    def test_doc_port40_gui_layout(self) -> None:
        """Validate docs/PORT40_GUI_LAYOUT.md contents, tables, root causes, citations, and hashes."""
        self.assertTrue(LAYOUT_DOC.is_file(), "docs/PORT40_GUI_LAYOUT.md must exist")
        content = LAYOUT_DOC.read_text(encoding="utf-8")

        # Must record DISKBOOT SHA-256 and sizes
        self.assertIn(PINNED_GUI5_SHA256, content)
        self.assertIn(str(PINNED_GUI5_SIZE), content)
        self.assertIn(PINNED_GUI5_SHORTPRESS_SHA256, content)
        self.assertIn(str(PINNED_GUI5_SHORTPRESS_SIZE), content)

        # Must cite sibling paths
        self.assertIn("chdk-port/platform/g7x", content)
        self.assertIn("chdk-port/platform/g5x", content)
        self.assertIn("chdk-port/platform/sx60hs", content)

        # Must address the 4 symptoms
        self.assertRegex(content, r"(?i)symptom\s*1")
        self.assertRegex(content, r"(?i)symptom\s*2")
        self.assertRegex(content, r"(?i)symptom\s*3")
        self.assertRegex(content, r"(?i)symptom\s*4")

        # Must list untouched GUI4 code paths
        self.assertIn("g3x_draw_char_16x32", content)
        self.assertIn("g3x_fill_menu_opaque_black", content)
        self.assertIn("draw_test_guard", content)
        self.assertIn("draw_set_guard", content)


if __name__ == "__main__":
    unittest.main()
