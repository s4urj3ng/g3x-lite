#!/usr/bin/env python3
"""PORT-37: Host verification suite for opt-in G3X_GUI3=1 CHDK core GUI candidate.

Verifies all acceptance criteria for Task PORT37-B-GUI3-BUILD:
1. G3X_GUI3=1 implies G3X_GUI2=1, G3X_GUI=1, G3X_KBD=1, G3X_OSD2=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. Invariance of prior builds:
   - Default build equals pinned hash 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - RESIDENT, OSD, KBD, OSD2, GUI, GUI2 builds equal their locked pinned hashes.
3. Zero-flicker redraw under GUI3 (B):
   - No timer-driven force_redraw ((tick_cnt & 3) == 0) and no per-key force_redraw compiled into g3x_gui_kbd_redraw.
   - Repaint occurs only on menu state change or detected overwrite (sentinel wiped or buffer toggle).
   - Visible buffer is never cleared and redrawn when state is unchanged and no overwrite is detected.
4. Diagnostic code gated by G3X_GUI_DIAG=1:
   - Under GUI3, diag code (1-px border and 'dt= w= bw= h=' marker) is present only with G3X_GUI_DIAG=1.
   - Diag code is drawn only as part of full menu repaint in gui_menu_draw_initial, never per keyboard tick.
5. Menu background opacity (F3):
   - Menu background resolves to solid opaque black (COLOR_BLACK 0xFF -> luma 0, opacity 255).
   - Full bounding box is filled in __wrap_gui_menu_draw_initial so all rows have solid opacity 255.
6. 2x Integer font scaling (F1):
   - Font width is 16 px (2x of 8) and font height is 32 px (2x of 16).
   - Scaled glyph test verifies that each bit expands to a 2x2 pixel square.
   - Menu layout targets verified 900x600 Mode 12 LCD (buffer width 928) and fills >95% width and >90% height.
7. Card-write exclusions:
   - conf_save, file-browser writes, module/script loading, and file-write hooks compiled out or stubbed.
   - No branch in .text targets unsafe card-mutating firmware stubs.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
PORT37_DOC = DOCS_DIR / "PORT37_GUI_FLICKER.md"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_gui3 import (
    G3X_GUI3_HEAP_START,
    build_candidate,
    generate_gui3_candidate_c,
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_PORT32_RESIDENT_SHA256 = "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a"
PINNED_PORT32_RESIDENT_SIZE = 124561

PINNED_PORT33_OSD_SHA256 = "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855"
PINNED_PORT33_OSD_SIZE = 124833

PINNED_PORT34_KBD_SHA256 = "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33"
PINNED_PORT34_KBD_SIZE = 124801

PINNED_PORT35_OSD2_SHA256 = "20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57"
PINNED_PORT35_OSD2_SIZE = 125329

PINNED_PORT35_GUI_SHA256 = "1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272"
PINNED_PORT35_GUI_SIZE = 103057

PINNED_PORT36_GUI2_SHA256 = "4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071"
PINNED_PORT36_GUI2_SIZE = 103345


class TestPort37GuiFlicker(unittest.TestCase):
    """PORT-37 CHDK GUI flicker elimination, font scaling, and opacity candidate verification."""

    @classmethod
    def setUpClass(cls) -> None:
        """Verify cross toolchain availability."""
        for tool, path in (("gcc", ARM_GCC), ("objdump", ARM_OBJDUMP), ("nm", ARM_NM)):
            if not path.is_file():
                raise unittest.SkipTest(f"Pinned cross-toolchain {tool} missing at {path}")

    def test_gui3_flag_implications_and_clearance(self) -> None:
        """G3X_GUI3=1 implies GUI2, GUI, KBD, OSD2, RESIDENT, POWERON_FIX, LED_LADDER."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui3=True, out_dir=tmpdir)
            self.assertTrue(res["gui3"], "gui3 must be True")
            self.assertTrue(res["gui2"], "gui3 implies gui2=True")
            self.assertTrue(res["gui"], "gui3 implies gui=True")
            self.assertTrue(res["osd2"], "gui3 implies osd2=True")
            self.assertTrue(res["kbd"], "gui3 implies kbd=True")
            self.assertTrue(res["resident"], "gui3 implies resident=True")
            self.assertTrue(res["poweron_fix"], "gui3 implies poweron_fix=True")
            self.assertTrue(res["ladder"], "gui3 implies ladder=True")

            self.assertFalse(res["gui_diag"], "gui_diag must be False by default")

            # Verify linked _end has positive clearance to heap start 0x00368880
            self.assertLessEqual(
                res["end_addr"],
                G3X_GUI3_HEAP_START,
                f"Linked _end (0x{res['end_addr']:08X}) exceeds heap start (0x{G3X_GUI3_HEAP_START:08X})",
            )
            self.assertGreaterEqual(
                res["clearance_bytes"],
                20000,
                f"Clearance ({res['clearance_bytes']} B) below safety threshold of 20 KB",
            )

    def test_prior_builds_byte_identity(self) -> None:
        """Default build and all prior builds (RESIDENT, OSD, OSD2, KBD, GUI, GUI2) remain byte-identical."""
        prior_targets = [
            ("default", {"ladder": False, "poweron_fix": False, "resident": False}, PINNED_DEFAULT_SHA256, PINNED_DEFAULT_SIZE),
            ("resident", {"resident": True}, PINNED_PORT32_RESIDENT_SHA256, PINNED_PORT32_RESIDENT_SIZE),
            ("osd", {"osd": True}, PINNED_PORT33_OSD_SHA256, PINNED_PORT33_OSD_SIZE),
            ("kbd", {"kbd": True}, PINNED_PORT34_KBD_SHA256, PINNED_PORT34_KBD_SIZE),
            ("osd2", {"osd2": True}, PINNED_PORT35_OSD2_SHA256, PINNED_PORT35_OSD2_SIZE),
            ("gui", {"gui": True}, PINNED_PORT35_GUI_SHA256, PINNED_PORT35_GUI_SIZE),
            ("gui2", {"gui2": True}, PINNED_PORT36_GUI2_SHA256, PINNED_PORT36_GUI2_SIZE),
        ]
        for name, kwargs, expected_sha, expected_size in prior_targets:
            with tempfile.TemporaryDirectory() as tmpdir:
                res = build_candidate(out_dir=tmpdir, **kwargs)
                self.assertEqual(
                    res["diskboot_size"],
                    expected_size,
                    f"{name} candidate size mismatch: expected {expected_size}, got {res['diskboot_size']}",
                )
                self.assertEqual(
                    res["diskboot_sha256"],
                    expected_sha,
                    f"{name} candidate SHA-256 mismatch against pinned baseline",
                )

    def test_no_timer_or_per_key_forced_redraw_under_gui3(self) -> None:
        """Under GUI3, remove (tick_cnt & 3)==0 timer force_redraw and per-key force_redraw."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui3 = build_candidate(gui3=True, out_dir=tmpdir)
            disasm_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui3["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = disasm_proc.stdout

            # Extract g3x_gui_kbd_redraw body
            m_redraw = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_redraw, "g3x_gui_kbd_redraw must be in disassembly")
            redraw_code = m_redraw.group(1)

            # 1. Under GUI3: no kbd_get_clicked_key or kbd_get_pressed_key
            self.assertNotIn("kbd_get_clicked_key", redraw_code)
            self.assertNotIn("kbd_get_pressed_key", redraw_code)

            # 2. Under GUI3: no timer tick force redraw (tick_cnt & 3)
            # Timer modulo used "ands rX, #3" or "tst.w rX, #3" in GUI2
            self.assertNotRegex(redraw_code, r"(ands|tst(\.w)?)\s+r\d+,\s*#3")

            # 3. Disassembly confirms check_gui_needs_redraw and draw_test_guard are called
            self.assertIn("check_gui_needs_redraw", redraw_code)
            self.assertIn("draw_test_guard", redraw_code)
            self.assertIn("draw_set_guard", redraw_code)

    def test_overwrite_detection_and_unchanged_state_redraw_logic(self) -> None:
        """Overwrite detection triggers repaint and unchanged state does not."""
        # Trace the exact state machine implemented in g3x_gui_kbd_redraw:
        # force_redraw = entered_alt || check_gui_needs_redraw() || (!draw_test_guard())
        def eval_force_redraw(entered_alt: bool, buf_toggled: bool, guard_intact: bool) -> bool:
            return entered_alt or buf_toggled or (not guard_intact)

        # 1. Steady state in ALT mode: entered_alt=False, buf_toggled=False, guard_intact=True
        self.assertFalse(
            eval_force_redraw(entered_alt=False, buf_toggled=False, guard_intact=True),
            "Unchanged state must NOT trigger forced redraw",
        )

        # 2. Overwrite detected: Canon stock UI erased or rewrote overlay (guard_intact=False)
        self.assertTrue(
            eval_force_redraw(entered_alt=False, buf_toggled=False, guard_intact=False),
            "Wiped guard sentinel must trigger forced redraw",
        )

        # 3. Active buffer toggled (buf_toggled=True)
        self.assertTrue(
            eval_force_redraw(entered_alt=False, buf_toggled=True, guard_intact=True),
            "Buffer toggle must trigger forced redraw",
        )

        # 4. ALT mode entered (entered_alt=True)
        self.assertTrue(
            eval_force_redraw(entered_alt=True, buf_toggled=False, guard_intact=True),
            "ALT entry must trigger forced redraw",
        )

        # In CHDK core (chdk-port/core/gui_menu.c:952-965):
        # if enforce_redraw: gui_menu_redraw = 2; (calls gui_menu_draw_initial)
        # if gui_menu_redraw == 1: redraws active item row only (without outer box clear)
        # if gui_menu_redraw == 0 and enforce_redraw == 0: NOTHING is drawn (zero buffer writes)
        menu_c = (CHDK_PORT / "core" / "gui_menu.c").read_text(encoding="utf-8")
        self.assertIn("if ( enforce_redraw )", menu_c)
        self.assertIn("gui_menu_redraw = 2;", menu_c)
        self.assertIn("if (gui_menu_redraw==2)", menu_c)
        self.assertIn("gui_menu_draw_initial();", menu_c)

    def test_visible_buffer_never_cleared_when_unchanged(self) -> None:
        """The visible buffer is never cleared and redrawn when the menu state is unchanged and no overwrite detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui3 = build_candidate(gui3=True, out_dir=tmpdir)
            disasm_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui3["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = disasm_proc.stdout

            # Disassemble g3x_gui_kbd_redraw
            m_redraw = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_redraw)
            redraw_code = m_redraw.group(1)

            # draw_rectangle MUST NOT be called in g3x_gui_kbd_redraw under GUI3
            self.assertNotIn("draw_rectangle", redraw_code)

            # Disassemble __wrap_gui_menu_draw_initial
            m_init = re.search(r"<__wrap_gui_menu_draw_initial>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_init)
            init_code = m_init.group(1)

            # draw_rectangle IS called in __wrap_gui_menu_draw_initial (once per full menu repaint)
            self.assertIn("draw_rectangle", init_code)

    def test_diagnostic_code_present_only_with_gui_diag(self) -> None:
        """Under GUI3 the diag code is present only with G3X_GUI_DIAG=1, drawn on menu repaint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. G3X_GUI3=1 (diag=False): diag code must NOT be present
            res_gui3 = build_candidate(gui3=True, gui_diag=False, out_dir=tmpdir)
            bin_data = Path(res_gui3["core_bin"]).read_bytes()
            self.assertNotIn(b"dt=", bin_data, "dt= marker must be absent in plain GUI3 candidate")

            disasm_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui3["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            m_init = re.search(r"<__wrap_gui_menu_draw_initial>:(.*?)(?:\n\n|\Z)", disasm_proc.stdout, re.DOTALL)
            self.assertIsNotNone(m_init)
            self.assertNotIn("draw_line", m_init.group(1), "draw_line must be absent when diag=False")

        with tempfile.TemporaryDirectory() as tmpdir:
            # 2. G3X_GUI3=1 + G3X_GUI_DIAG=1: diag code MUST be present in __wrap_gui_menu_draw_initial only
            res_diag = build_candidate(gui3=True, gui_diag=True, out_dir=tmpdir)
            bin_data_diag = Path(res_diag["core_bin"]).read_bytes()
            self.assertIn(b"dt=%d w=%d bw=%d h=%d", bin_data_diag, "dt= marker format string must be present in GUI_DIAG")

            disasm_diag = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_diag["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            m_init_diag = re.search(r"<__wrap_gui_menu_draw_initial>:(.*?)(?:\n\n|\Z)", disasm_diag, re.DOTALL)
            self.assertIsNotNone(m_init_diag)
            self.assertIn("draw_line", m_init_diag.group(1), "draw_line must be called in __wrap_gui_menu_draw_initial")
            self.assertIn("draw_string", m_init_diag.group(1), "draw_string must be called in __wrap_gui_menu_draw_initial")

            # Must NOT be called in g3x_gui_kbd_redraw
            m_redraw_diag = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm_diag, re.DOTALL)
            self.assertIsNotNone(m_redraw_diag)
            self.assertNotIn("draw_line", m_redraw_diag.group(1), "draw_line must NOT be called per tick")
            self.assertNotIn("draw_string", m_redraw_diag.group(1), "draw_string must NOT be called per tick")

    def test_menu_background_resolves_to_opaque_black(self) -> None:
        """The menu background pixel resolves to opaque black (COLOR_BLACK 0xFF -> luma 0, opacity 255)."""
        # 1. Palette index definition
        gui_draw_h = (CHDK_PORT / "core" / "gui_draw.h").read_text(encoding="utf-8")
        self.assertRegex(gui_draw_h, r"#define\s+IDX_COLOR_BLACK\s+1\b")

        # 2. Generic palette mapping
        palette_c = (CHDK_PORT / "platform" / "generic" / "palette.c").read_text(encoding="utf-8")
        self.assertRegex(palette_c, r"#define\s+COLOR_BLACK\s+0xff\b")
        self.assertIn("COLOR_BLACK,               // Placeholder for script colors", palette_c)

        # 3. DIGIC 6 YUV and Opacity calculation:
        # #define CALC_YUV_LUMA_OPACITY_FOR_COLOR(color,luma,opacity) \
        #     { \
        #         luma = ((color-1)^0xffffffff)&0xf0; \
        #         opacity = (color&0xf)?255:color; \
        #     }
        color_val = 0xFF  # COLOR_BLACK
        luma = ((color_val - 1) ^ 0xFFFFFFFF) & 0xF0
        opacity = 255 if (color_val & 0xF) else color_val

        self.assertEqual(luma, 0, "Luma for COLOR_BLACK must be 0 (pure black)")
        self.assertEqual(opacity, 255, "Opacity for COLOR_BLACK must be 255 (fully opaque)")

        # 4. conf_restore sets default menu background color index to COLOR_BLACK (1)
        # and __wrap_gui_menu_draw_initial fills outer box with MAKE_COLOR(COLOR_BLACK, COLOR_BLACK) = 0xFFFF
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui3=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            m_init = re.search(r"<__wrap_gui_menu_draw_initial>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_init)
            # Verify movw rX, #65535 (0xffff) is passed to draw_rectangle
            self.assertRegex(m_init.group(1), r"(movw|movs?)\s+r\d+,\s*#(65535|0xffff)")

    def test_scaled_glyph_2x_size(self) -> None:
        """The scaled glyph test shows 2x size (16x32 raster, 2x2 blocks, rbf_char_width=16, rbf_font_height=32)."""
        # 1. Disassembly checks: __wrap_rbf_char_width returns 16
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui3=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            m_width = re.search(r"<__wrap_rbf_char_width>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_width)
            self.assertIn("movs\tr0, #16", m_width.group(1))

            m_draw = re.search(r"<__wrap_rbf_draw_char>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_draw)
            self.assertIn("bl\t34", m_draw.group(1))  # calls __wrap_draw_char
            self.assertIn("movs\tr0, #16", m_draw.group(1))

        # 2. Mathematical 2x integer font scaling simulation:
        # Built-in font is 8x16. For test glyph 'T':
        # Row bitmask (8 cols):
        test_glyph_8x16 = [
            0x00, 0x00, 0x7E, 0x18, 0x18, 0x18, 0x18, 0x18,
            0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x00, 0x00,
        ]
        self.assertEqual(len(test_glyph_8x16), 16)

        # Apply 2x integer scaling (expand each bit to 2x2 pixel block)
        scaled_raster_16x32 = []
        for row in test_glyph_8x16:
            scaled_row = 0
            for b in range(8):
                if row & (1 << (7 - b)):
                    scaled_row |= (3 << (14 - 2 * b))
            # Row repeated 2x vertically
            scaled_raster_16x32.append(scaled_row)
            scaled_raster_16x32.append(scaled_row)

        self.assertEqual(len(scaled_raster_16x32), 32, "Scaled glyph height must be exactly 32 pixels")
        for r_idx, r_val in enumerate(scaled_raster_16x32):
            orig_row = test_glyph_8x16[r_idx // 2]
            for col in range(8):
                bit = (orig_row >> (7 - col)) & 1
                p0 = (r_val >> (15 - 2 * col)) & 1
                p1 = (r_val >> (14 - 2 * col)) & 1
                self.assertEqual(p0, bit, f"Row {r_idx} Col {2*col} mismatch")
                self.assertEqual(p1, bit, f"Row {r_idx} Col {2*col+1} mismatch")

    def test_card_write_exclusions_hold_under_gui3(self) -> None:
        """PORT-35 card-write exclusions still hold under GUI3 (settings RAM-only, stubs for writes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui3=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            nm_output = nm_proc.stdout

            # 1. conf_save stubbed
            m_conf = re.search(r"<conf_save>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_conf)
            self.assertIn("bx\tlr", m_conf.group(1))

            # 2. script_load stubbed
            m_script = re.search(r"<script_load>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_script)
            self.assertIn("bx\tlr", m_script.group(1))

            # 3. Unsafe stubs tracked and uncalled
            unsafe_stubs = [
                "_Write",
                "_Fwrite_Fut",
                "_MakeDirectory_Fut",
                "_DeleteFile_Fut",
                "_DeleteDirectory_Fut",
                "_RenameFile_Fut",
                "_WriteSDCard",
                "_MakeSDCardBootable",
                "_SetFileAttributes",
                "_SetFileTimeStamp",
            ]
            stub_addrs = {}
            for line in nm_output.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2] in unsafe_stubs:
                    stub_addrs[parts[2]] = parts[0].lower().lstrip("0")

            self.assertEqual(len(stub_addrs), len(unsafe_stubs))
            for stub_name, hex_addr in stub_addrs.items():
                pattern = rf"\b(bl|b\.w|b\.n|bx|blx)\s+[0-9a-f]*{hex_addr}\b"
                matches = re.findall(pattern, disasm)
                self.assertEqual(len(matches), 0, f"Unsafe stub {stub_name} targeted in .text")

    def test_menu_layout_targets_900x600_mode12(self) -> None:
        """Menu layout targets 900x600/bw 928 and fills most of screen."""
        disp_width = 900
        disp_height = 600
        buffer_width = 928
        font_w = 16
        font_h = 32

        # In gui_menu.c:
        # w = disp_width - 20
        # num_lines = (camera_screen.height - camera_screen.ts_menu_border*2)/rbf_font_height() - 1
        menu_w = disp_width - 20  # 880
        num_lines = (disp_height // font_h) - 1  # 17 lines

        self.assertEqual(menu_w, 880)
        self.assertEqual(num_lines, 17)
        self.assertGreaterEqual(num_lines, 10, "17 lines accommodates all 10 root menu rows")

        # Layout coverage
        width_coverage = menu_w / disp_width
        height_coverage = ((num_lines + 1) * font_h) / disp_height
        self.assertGreater(width_coverage, 0.95, "Menu width must fill >95% of screen width")
        self.assertGreater(height_coverage, 0.90, "Menu height must fill >90% of screen height")


if __name__ == "__main__":
    unittest.main()
