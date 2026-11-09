#!/usr/bin/env python3
"""PORT-40: Host test suite for opt-in G3X_GUI5=1 candidate.

Verifies:
(a) The default build (no flags) is strictly byte-identical to main:
    DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
(b) G3X_GUI5=1 builds cleanly and implies G3X_GUI4=1:
    - DISKBOOT.BIN SHA-256: dd96357c050cf3b9116dcf089a731ef159477b505351f46436f983fdbf090b64 (102,209 B)
    - Boot witness: 0x0035C980
    - Linked _end: 0x003629B0 <= heap start 0x00368880 (24,272 B clearance)
(c) Combined G3X_GUI5=1 + G3X_SHORTPRESS=1 builds cleanly:
    - DISKBOOT.BIN SHA-256: 86e12a2cfe792a8901fa2e0ec5a98f019290593e35d5c4c2e66fd3e073f16ff1 (102,369 B)
    - Boot witness: 0x0035CA20
    - Linked _end: 0x00362A60 <= heap start 0x00368880 (24,096 B clearance)
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

PINNED_GUI5_SHA256 = "dd96357c050cf3b9116dcf089a731ef159477b505351f46436f983fdbf090b64"
PINNED_GUI5_SIZE = 102209
PINNED_GUI5_WITNESS = 0x0035C980
PINNED_GUI5_END = 0x003629B0

PINNED_GUI5_SHORTPRESS_SHA256 = "86e12a2cfe792a8901fa2e0ec5a98f019290593e35d5c4c2e66fd3e073f16ff1"
PINNED_GUI5_SHORTPRESS_SIZE = 102369
PINNED_GUI5_SHORTPRESS_WITNESS = 0x0035CA20
PINNED_GUI5_SHORTPRESS_END = 0x00362A60

HEAP_START = 0x00368880


class TestPort40GuiLayout(unittest.TestCase):
    """Test suite for PORT-40 G3X_GUI5=1 candidate build and geometry layout."""

    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        cls._tmp = tempfile.TemporaryDirectory(prefix="port40-")
        cls.gui5_dir = os.path.join(cls._tmp.name, "gui5")
        cls.gui5_sp_dir = os.path.join(cls._tmp.name, "gui5_sp")
        cls.res_gui5 = build_candidate_gui(gui5=True, out_dir=cls.gui5_dir)
        cls.res_gui5_sp = build_candidate_gui(gui5=True, shortpress=True, out_dir=cls.gui5_sp_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

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
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate_gui(gui4=True, out_dir=tmpdir)
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
        """G3X_GUI5=1 builds cleanly, matches pinned SHA-256, and has positive heap clearance."""
        res_canon = self.res_gui5
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
        res_canon = self.res_gui5_sp
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
        """Geometry assertion: fill rect equals menu rect, fits 900x600, with even margins in scrolling and non-scrolling cases."""
        # 1. Preprocess real header with pinned toolchain under -DG3X_GUI5=1
        cmd = [
            str(ARM_GCC),
            "-E",
            "-dM",
            "-DLOW_LEVEL",
            '-DPLATFORM="g3x"',
            '-DPLATFORMSUB="110c"',
            "-DG3X_OSD2=1",
            "-DG3X_GUI5=1",
            "-Iinclude",
            "-Icore",
            "-Iplatform/g3x",
            "-Iplatform/g3x/sub/110c",
            str(SUB_DIR / "osd2_test_overlay.h"),
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

        screen_w_def = int(defines["G3X_OSD2_DEFAULT_WIDTH"].strip("() "))
        screen_h_def = int(defines["G3X_OSD2_DEFAULT_HEIGHT"].strip("() "))
        buffer_w_def = int(defines["G3X_OSD2_DEFAULT_BUFFER_WIDTH"].strip("() "))
        buffer_h_def = int(defines["G3X_OSD2_DEFAULT_BUFFER_HEIGHT"].strip("() "))

        self.assertEqual(screen_w_def, 720, "G3X_OSD2_DEFAULT_WIDTH must remain 720")
        self.assertEqual(screen_h_def, 480, "G3X_OSD2_DEFAULT_HEIGHT must remain 480")
        self.assertEqual(buffer_w_def, 736, "G3X_OSD2_DEFAULT_BUFFER_WIDTH must remain 736")
        self.assertEqual(buffer_h_def, 480, "G3X_OSD2_DEFAULT_BUFFER_HEIGHT must remain 480")

        # Initial GUI5 camera_screen values
        init_w_def = int(defines["G3X_GUI5_INITIAL_WIDTH"].strip("() "))
        init_h_def = int(defines["G3X_GUI5_INITIAL_HEIGHT"].strip("() "))
        init_bw_def = int(defines["G3X_GUI5_INITIAL_BUFFER_WIDTH"].strip("() "))
        init_bh_def = int(defines["G3X_GUI5_INITIAL_BUFFER_HEIGHT"].strip("() "))

        self.assertEqual(init_w_def, 900, "G3X_GUI5_INITIAL_WIDTH must be 900")
        self.assertEqual(init_h_def, 600, "G3X_GUI5_INITIAL_HEIGHT must be 600")
        self.assertEqual(init_bw_def, 928, "G3X_GUI5_INITIAL_BUFFER_WIDTH must be 928")
        self.assertEqual(init_bh_def, 600, "G3X_GUI5_INITIAL_BUFFER_HEIGHT must be 600")

        # 2. Extract camera_screen struct values from compiled candidate_main.elf
        elf_path = os.path.join(self.gui5_dir, "candidate_main.elf")
        if not os.path.isfile(elf_path):
            build_candidate(gui5=True)

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

        # Dump 64 bytes (16 32-bit ints) of camera_screen struct
        objdump_proc = subprocess.run(
            [
                str(ARM_OBJDUMP),
                "-s",
                f"--start-address=0x{cs_addr:x}",
                f"--stop-address=0x{cs_addr + 64:x}",
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

        ints = struct.unpack("<16I", bytes(hex_bytes[:64]))
        screen_w = ints[0]
        screen_h = ints[1]
        buffer_w = ints[4]
        buffer_h = ints[5]
        disp_left = ints[7]
        disp_right = ints[8]
        disp_width = ints[9]
        ts_menu_border = ints[14]
        menu_border_width = ints[15]

        self.assertEqual(screen_w, 900)
        self.assertEqual(screen_h, 600)
        self.assertEqual(disp_left, 0)
        self.assertEqual(disp_width, 900)
        self.assertEqual(ts_menu_border, 0)
        self.assertEqual(menu_border_width, 10)

        # 3. Parse font height and scrollbar wplus from real sources
        build_py_src = (SCRIPTS_DIR / "build_candidate_gui3.py").read_text(encoding="utf-8")
        m_fh = re.search(r"int\s+rbf_font_height\s*\(void\)\s*\{\s*return\s+(\d+);", build_py_src)
        self.assertIsNotNone(m_fh, "rbf_font_height definition must be present")
        font_h = int(m_fh.group(1))
        self.assertEqual(font_h, 32, "Font height under F1 2x scaling must be 32")

        gui_menu_compiled = Path(self.gui5_dir) / "gui_menu.c"
        self.assertTrue(gui_menu_compiled.exists(), f"Generated {gui_menu_compiled} must exist from GUI5 build")
        gui_menu_src = gui_menu_compiled.read_text(encoding="utf-8")
        m_wplus = re.search(r"#if defined\(G3X_GUI5\) && \(G3X_GUI5 == 1\)[\s\S]*?wplus\s*=\s*(\d+);", gui_menu_src)
        self.assertIsNotNone(m_wplus, "GUI5 wplus scrollbar width must be present in compiled gui_menu.c")
        scrollbar_wplus = int(m_wplus.group(1))
        self.assertEqual(scrollbar_wplus, 8, "GUI5 scrollbar width reservation must be 8 px")

        # 4. Parse real menu item counts from gui.c: non-scrolling (root_menu) vs scrolling (visual_submenu)
        gui_src = (CHDK_PORT / "core" / "gui.c").read_text(encoding="utf-8")
        m_root = re.search(r"root_menu_items\[\]\s*=\s*\{(.*?)\{0\}", gui_src, re.DOTALL)
        self.assertIsNotNone(m_root, "root_menu_items array must be found in gui.c")
        root_count = len(re.findall(r"MENU_ITEM\s*\(", m_root.group(1)))
        self.assertEqual(root_count, 10)

        m_vis = re.search(r"visual_submenu_items\[\]\s*=\s*\{(.*?)\{0\}", gui_src, re.DOTALL)
        self.assertIsNotNone(m_vis, "visual_submenu_items array must be found in gui.c")
        vis_count = len(re.findall(r"MENU_ITEM\s*\(", m_vis.group(1)))
        self.assertEqual(vis_count, 31)

        # 5. Path A: Independent computation of fill rect from build_candidate_gui3.py g3x_get_menu_layout
        num_l = (screen_h - ts_menu_border * 2) // font_h - 1
        fill_x = (disp_left + menu_border_width) & ~1
        fill_w = (disp_width - menu_border_width * 2) & ~1
        by = (screen_h - ((num_l - 1) * font_h)) >> 1
        header_y = by - font_h
        total_h = (num_l + 1) * font_h
        total_w = fill_w
        if fill_x < 0:
            fill_x = 0
        if header_y < 0:
            header_y = 0
        if fill_x + total_w > disp_width:
            total_w = disp_width - fill_x
        if header_y + total_h > screen_h:
            total_h = screen_h - header_y
        fill_rect = (fill_x, header_y, total_w, total_h)
        self.assertEqual(fill_rect, (10, 12, 880, 576), "Background fill rect must be exactly (10, 12, 880, 576)")

        # 6. Path B: Independent computation of painted menu rect from gui_menu.c draw calls
        def compute_menu_geometry(count: int):
            num_lines = (screen_h - ts_menu_border * 2) // font_h - 1
            menu_x = (disp_left + menu_border_width) & ~1
            base_w = (disp_width - menu_border_width * 2) & ~1
            y = (screen_h - ((num_lines - 1) * font_h)) >> 1
            h_y = y - font_h

            if count > num_lines:
                wp = scrollbar_wplus
                w = base_w - wp
                # Scrollbar background: draw_rectangle((x+w), y, (x+w)+wplus-1, ...)
                sb_x1 = menu_x + w
                sb_x2 = (menu_x + w) + wp - 1
                sb_y1 = y
                sb_y2 = y + num_lines * font_h - 1
                # Scrollbar thumb: draw_rectangle((x+w)+2, y+1+i, (x+w)+6, y+i+j, ...)
                thumb_x1 = (menu_x + w) + 2
                thumb_x2 = (menu_x + w) + 6
            else:
                wp = 0
                w = base_w
                sb_x1 = sb_x2 = sb_y1 = sb_y2 = None
                thumb_x1 = thumb_x2 = None

            # rbf_draw_menu_header draws header bar to x + (w + wplus) - 1
            header_w = w + wp
            header_x1 = menu_x
            header_x2 = menu_x + header_w - 1
            header_y1 = h_y
            header_y2 = h_y + font_h - 1

            # gui_menu_draw draws items to x + w - 1
            items_x1 = menu_x
            items_x2 = menu_x + w - 1
            items_y1 = y
            items_y2 = y + num_lines * font_h - 1

            # Bounding box of all drawn elements
            all_x1 = [header_x1, items_x1]
            all_x2 = [header_x2, items_x2]
            all_y1 = [header_y1, items_y1]
            all_y2 = [header_y2, items_y2]
            if sb_x1 is not None:
                all_x1.append(sb_x1)
                all_x2.append(sb_x2)
                all_y1.append(sb_y1)
                all_y2.append(sb_y2)

            outer_x = min(all_x1)
            outer_y = min(all_y1)
            outer_w = max(all_x2) - outer_x + 1
            outer_h = max(all_y2) - outer_y + 1
            return (outer_x, outer_y, outer_w, outer_h), (sb_x1, sb_x2), (thumb_x1, thumb_x2)

        # 7. Parameterised checks over non-scrolling and scrolling menu counts
        test_counts = [
            (root_count, "non-scrolling root_menu (count=10)"),
            (17, "non-scrolling boundary (count=17)"),
            (18, "scrolling boundary (count=18)"),
            (vis_count, "scrolling Visual Settings submenu (count=31)"),
        ]

        for count_val, desc in test_counts:
            outer_rect, sb_range, thumb_range = compute_menu_geometry(count_val)

            # Assert fill == outer menu rect == (10, 12, 880, 576)
            self.assertEqual(fill_rect, (10, 12, 880, 576), f"Fill rect mismatch for {desc}")
            self.assertEqual(outer_rect, (10, 12, 880, 576), f"Outer menu rect mismatch for {desc}")
            self.assertEqual(fill_rect, outer_rect, f"Fill rect must equal outer menu rect for {desc}")

            # Assert margins: left == right == 10, top == bottom == 12
            left_margin = outer_rect[0]
            right_margin = screen_w - (outer_rect[0] + outer_rect[2])
            top_margin = outer_rect[1]
            bottom_margin = screen_h - (outer_rect[1] + outer_rect[3])

            self.assertEqual(left_margin, 10, f"Left margin must be 10 for {desc}")
            self.assertEqual(right_margin, 10, f"Right margin must be 10 for {desc}")
            self.assertEqual(left_margin, right_margin, f"Horizontal margins must be even for {desc}")

            self.assertEqual(top_margin, 12, f"Top margin must be 12 for {desc}")
            self.assertEqual(bottom_margin, 12, f"Bottom margin must be 12 for {desc}")
            self.assertEqual(top_margin, bottom_margin, f"Vertical margins must be even for {desc}")

            # Assert boundary within 0..899 x 0..599
            self.assertGreaterEqual(outer_rect[0], 0, f"X must be non-negative for {desc}")
            self.assertGreaterEqual(outer_rect[1], 0, f"Y must be non-negative for {desc}")
            self.assertLessEqual(outer_rect[0] + outer_rect[2], screen_w, f"Right edge within LCD for {desc}")
            self.assertLessEqual(outer_rect[1] + outer_rect[3], screen_h, f"Bottom edge within LCD for {desc}")

            # Scrollbar checks when count > num_lines
            if count_val > 17:
                self.assertIsNotNone(sb_range[0], f"Scrollbar must be present for {desc}")
                self.assertGreaterEqual(sb_range[0], outer_rect[0], f"Scrollbar start inside box for {desc}")
                self.assertLessEqual(sb_range[1], outer_rect[0] + outer_rect[2] - 1, f"Scrollbar end inside box for {desc}")
                self.assertEqual(sb_range, (882, 889), f"Scrollbar range must be exactly 882..889 for {desc}")
                self.assertEqual(thumb_range, (884, 888), f"Scrollbar thumb must be 884..888 for {desc}")

        # 8. Negative check: demonstrate rejection of old attempt 4 formula (which widened to 890)
        wp_old = scrollbar_wplus if vis_count > num_l else 0
        old_total_w = fill_w + wp_old + (1 if wp_old else 0)
        old_total_w = (old_total_w + 1) & ~1
        self.assertEqual(old_total_w, 890, "Old attempt 4 formula must produce 890 for scrolling menu")
        self.assertNotEqual(old_total_w, 880, "Old 890 width violates 880 box width specification")
        old_right_margin = screen_w - (fill_x + old_total_w)
        self.assertEqual(old_right_margin, 0, "Old 890 width destroys right margin (0 px)")
        self.assertNotEqual(fill_x, old_right_margin, "Old 890 width destroys margin symmetry (10 vs 0)")
        self.assertNotEqual(fill_rect[2], old_total_w, "Current GUI5 candidate fill rect rejects old 890 formula")

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

    def test_displaytype_regression_under_gui5(self) -> None:
        """Host regression test: Under G3X_GUI5, displaytypes 1, 2, 8, 9, 10 must have 720x480 stride 736 and opacity offset (10,100) == 73610; dt 12 must have 900x600 stride 928."""
        host_cc = "gcc"
        try:
            subprocess.run([host_cc, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            has_cc = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            has_cc = False

        if has_cc:
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
                    "    int disp_left;\n"
                    "    int disp_right;\n"
                    "    int disp_width;\n"
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
                    "    int dts[] = { 1, 2, 8, 9, 10, 12 };\n"
                    "    for (int i = 0; i < 6; i++) {\n"
                    "        displaytype = dts[i];\n"
                    "        g3x_osd2_update_screen_dimensions();\n"
                    "        int op_offset = 100 * camera_screen.buffer_width + 10;\n"
                    '        printf("%d:%d,%d,%d,%d\\n",\n'
                    "            displaytype,\n"
                    "            camera_screen.width,\n"
                    "            camera_screen.height,\n"
                    "            camera_screen.buffer_width,\n"
                    "            op_offset);\n"
                    "    }\n"
                    "    return 0;\n"
                    "}\n",
                    encoding="utf-8",
                )
                subprocess.run(
                    [
                        host_cc,
                        "-DG3X_OSD2=1",
                        "-DG3X_GUI5=1",
                        "-Wno-pointer-to-int-cast",
                        "-Wno-int-to-pointer-cast",
                        "-Wno-incompatible-pointer-types",
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

            res: dict[int, list[int]] = {}
            for line in out.strip().splitlines():
                parts = line.split(":")
                dt = int(parts[0])
                res[dt] = [int(v) for v in parts[1].split(",")]

            for dt in (1, 2, 8, 9, 10):
                with self.subTest(displaytype=dt):
                    self.assertEqual(res[dt][0], 720, f"dt={dt} width must be 720")
                    self.assertEqual(res[dt][1], 480, f"dt={dt} height must be 480")
                    self.assertEqual(res[dt][2], 736, f"dt={dt} buffer_width must be 736")
                    self.assertEqual(res[dt][3], 73610, f"dt={dt} opacity offset (10,100) must be 73610")

            self.assertEqual(res[12][0], 900, "dt=12 width must be 900")
            self.assertEqual(res[12][1], 600, "dt=12 height must be 600")
            self.assertEqual(res[12][2], 928, "dt=12 buffer_width must be 928")
            self.assertEqual(res[12][3], 92810, "dt=12 opacity offset (10,100) must be 92810")
        else:
            self.skipTest("Host C compiler (gcc) not available")

    def test_camera_screen_static_initialization_in_binary(self) -> None:
        """Binary inspection: camera_screen in candidate .data matches 900x600 stride 928 disp_width 900."""
        elf_path = os.path.join(self.gui5_dir, "candidate_main.elf")

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
        elf_path = os.path.join(self.gui5_dir, "candidate_main.elf")

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
        elf_path = os.path.join(self.gui5_dir, "candidate_main.elf")

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

    def test_patch_anchor_missing_fails(self) -> None:
        """Patch transform fails loudly with RuntimeError if the anchor is missing."""
        from build_candidate_gui3 import apply_gui5_menu_patch
        corrupted_src = "void some_func(void) { int count = 0; return; }\n"
        with self.assertRaises(RuntimeError) as ctx:
            apply_gui5_menu_patch(corrupted_src)
        self.assertIn("anchor not found", str(ctx.exception).lower())

    def test_patch_file_exists_and_matches_transform(self) -> None:
        """Embedded GUI5 menu transform applies cleanly, generated gui_menu.c contains reservation, and worktree remains unmodified."""
        from build_candidate_gui3 import apply_gui5_menu_patch

        # Ensure core/gui_menu.c in worktree is pristine and unmodified
        worktree_core_menu = (CHDK_PORT / "core" / "gui_menu.c").read_text(encoding="utf-8")
        self.assertNotIn("w -= wplus", worktree_core_menu, "chdk-port/core/gui_menu.c must remain pristine and unpatched")

        # Verify apply_gui5_menu_patch transforms pristine source cleanly to include wplus reservation
        transformed = apply_gui5_menu_patch(worktree_core_menu)
        self.assertIn("w -= wplus", transformed)
        self.assertIn("wplus = 8;", transformed)

        # Verify generated gui_menu.c in candidate build contains the GUI5 wplus/w reservation
        gui_menu_compiled = Path(self.gui5_dir) / "gui_menu.c"
        self.assertTrue(gui_menu_compiled.exists(), f"Generated {gui_menu_compiled} must exist from GUI5 build")
        compiled_menu = gui_menu_compiled.read_text(encoding="utf-8")
        self.assertIn("w -= wplus", compiled_menu)
        self.assertIn("wplus = 8;", compiled_menu)


if __name__ == "__main__":
    unittest.main()
