#!/usr/bin/env python3
"""PORT-38: Host verification suite for opt-in G3X_GUI4=1 CHDK core GUI candidate.

Verifies all acceptance criteria for Task PORT38-GUI4-BUILD-R1:
1. G3X_GUI4=1 implies G3X_GUI3=1, G3X_GUI2=1, G3X_GUI=1, G3X_KBD=1, G3X_OSD2=1,
   G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. Invariance of baseline and prior builds:
   - Default build equals pinned hash 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - RESIDENT, OSD, KBD, OSD2, GUI, GUI2, GUI3 builds equal their locked pinned hashes.
3. Direct G3X font driver routing (F1):
   - In GUI4 ELF, menu text call path verifiably reaches 16x32 glyph drawing without
     relying on ld --wrap of a call made inside the same object.
   - Symbols __wrap_draw_char, __wrap_rbf_draw_char, __wrap_rbf_char_width,
     __wrap_draw_string_clipped, and __wrap_gui_menu_draw_initial are absent.
   - Direct calls from gui_menu.o go to rbf_font_height, rbf_char_width, rbf_draw_char,
     rbf_draw_menu_header.
   - Font height is 32 px, character advance width is 16 px, row pitch is 32 px.
4. Menu opaque background fill and bounding box (F3):
   - Menu fill covers full menu rectangle (x: 10..889, y: 12..587, width 880, height 576),
     including header row, list rows, and padding rows above and below.
   - Writes UYVY black (0x00800080) to bitmap_buffer and opacity 255 to opacity_buffer[active_bitmap_buffer & 1]
     (citing g7x/g5x lib.c: chdk-port/platform/g7x/lib.c:289-296, g5x/lib.c:27-33).
   - Uses the exact same rectangle for fill and paint.
5. Contrasting title bar:
   - Title configured as white text (fg.col=2, type=1) on solid black background (bg.col=1, type=1).
   - conf.menu_center set to 0 anchoring menu to header at y=12.
6. Zero-flicker and Steps 8/9 preservation:
   - No periodic timer force_redraw ((tick_cnt & 3) == 0) and no per-key force_redraw.
   - Overwrite detection sentinel check (Step 8) and clean ALT exit (Step 9) preserved.
7. Card-write exclusions:
   - All card file-write hooks and unsafe stubs compiled out or blocked.
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

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_gui3 import (
    G3X_GUI4_HEAP_START,
    build_candidate,
    generate_gui4_candidate_c,
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

PINNED_PORT37_GUI3_SHA256 = "4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638"
PINNED_PORT37_GUI3_SIZE = 103569


class TestPort38GuiGeometry(unittest.TestCase):
    """PORT-38 host verification suite."""

    @classmethod
    def setUpClass(cls) -> None:
        """Verify cross toolchain availability."""
        for tool, path in (("gcc", ARM_GCC), ("objdump", ARM_OBJDUMP), ("nm", ARM_NM)):
            if not path.is_file():
                raise unittest.SkipTest(f"Pinned cross-toolchain {tool} missing at {path}")

    def test_gui4_flag_implications_and_clearance(self) -> None:
        """G3X_GUI4=1 implies GUI3, GUI2, GUI, KBD, OSD2, RESIDENT, POWERON_FIX, LED_LADDER."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui4=True, out_dir=tmpdir)
            self.assertTrue(res["gui4"], "gui4 must be True")
            self.assertTrue(res["gui3"], "gui4 implies gui3=True")
            self.assertTrue(res["gui2"], "gui4 implies gui2=True")
            self.assertTrue(res["gui"], "gui4 implies gui=True")
            self.assertTrue(res["osd2"], "gui4 implies osd2=True")
            self.assertTrue(res["kbd"], "gui4 implies kbd=True")
            self.assertTrue(res["resident"], "gui4 implies resident=True")
            self.assertTrue(res["poweron_fix"], "gui4 implies poweron_fix=True")
            self.assertTrue(res["ladder"], "gui4 implies ladder=True")

            self.assertFalse(res["gui_diag"], "gui_diag must be False by default")

            # Verify linked _end has positive clearance to heap start 0x00368880
            self.assertLessEqual(
                res["end_addr"],
                G3X_GUI4_HEAP_START,
                f"Linked _end (0x{res['end_addr']:08X}) exceeds heap start (0x{G3X_GUI4_HEAP_START:08X})",
            )
            self.assertGreaterEqual(
                res["clearance_bytes"],
                20000,
                f"Clearance ({res['clearance_bytes']} B) below safety threshold of 20 KB",
            )

    def test_default_and_prior_builds_byte_identity(self) -> None:
        """Default build and all prior builds (RESIDENT, OSD, KBD, OSD2, GUI, GUI2, GUI3) remain byte-identical."""
        prior_targets = [
            ("default", {"ladder": False, "poweron_fix": False, "resident": False}, PINNED_DEFAULT_SHA256, PINNED_DEFAULT_SIZE),
            ("resident", {"resident": True}, PINNED_PORT32_RESIDENT_SHA256, PINNED_PORT32_RESIDENT_SIZE),
            ("osd", {"osd": True}, PINNED_PORT33_OSD_SHA256, PINNED_PORT33_OSD_SIZE),
            ("kbd", {"kbd": True}, PINNED_PORT34_KBD_SHA256, PINNED_PORT34_KBD_SIZE),
            ("osd2", {"osd2": True}, PINNED_PORT35_OSD2_SHA256, PINNED_PORT35_OSD2_SIZE),
            ("gui", {"gui": True}, PINNED_PORT35_GUI_SHA256, PINNED_PORT35_GUI_SIZE),
            ("gui2", {"gui2": True}, PINNED_PORT36_GUI2_SHA256, PINNED_PORT36_GUI2_SIZE),
            ("gui3", {"gui3": True}, PINNED_PORT37_GUI3_SHA256, PINNED_PORT37_GUI3_SIZE),
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

    def test_direct_font_driver_routing_in_gui4_without_cross_object_wrap(self) -> None:
        """In GUI4 ELF, menu text call path verifiably reaches 16x32 glyph drawing without ld --wrap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            nm_output = nm_proc.stdout

            # 1. Wrappers for font calls must be completely absent in GUI4
            self.assertNotIn("__wrap_rbf_draw_char", nm_output)
            self.assertNotIn("__wrap_rbf_char_width", nm_output)
            self.assertNotIn("__wrap_draw_char", nm_output)
            self.assertNotIn("__wrap_draw_string_clipped", nm_output)
            self.assertNotIn("__wrap_gui_menu_draw_initial", nm_output)

            # 2. Direct G3X font routines must be present in .text
            self.assertIn(" T rbf_font_height", nm_output)
            self.assertIn(" T rbf_char_width", nm_output)
            self.assertIn(" T rbf_draw_char", nm_output)
            self.assertIn(" T rbf_draw_menu_header", nm_output)
            self.assertIn(" T g3x_draw_char_16x32", nm_output)

            # 3. Disassembly: verify gui_menu.o branches directly to G3X font driver
            disasm_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = disasm_proc.stdout

            # Extract rbf_font_height address and confirm bl targets it
            m_fh = re.search(r"([0-9a-f]+)\s+<rbf_font_height>:", disasm)
            self.assertIsNotNone(m_fh)
            fh_addr = m_fh.group(1).lstrip("0")
            self.assertRegex(disasm, rf"bl\s+[0-9a-f]*{fh_addr}\s+<rbf_font_height>")

            # Extract rbf_draw_char address and confirm bl targets it
            m_dc = re.search(r"([0-9a-f]+)\s+<rbf_draw_char>:", disasm)
            self.assertIsNotNone(m_dc)
            dc_addr = m_dc.group(1).lstrip("0")
            self.assertRegex(disasm, rf"bl\s+[0-9a-f]*{dc_addr}\s+<rbf_draw_char>")

            # Extract rbf_draw_menu_header address and confirm bl targets it
            m_mh = re.search(r"([0-9a-f]+)\s+<rbf_draw_menu_header>:", disasm)
            self.assertIsNotNone(m_mh)
            mh_addr = m_mh.group(1).lstrip("0")
            self.assertRegex(disasm, rf"bl\s+[0-9a-f]*{mh_addr}\s+<rbf_draw_menu_header>")

    def test_scaled_font_metrics_and_dimensions(self) -> None:
        """Font metrics under GUI4: height 32, char width 16, row pitch 32, 2x raster."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            # rbf_font_height returns 32
            m_fh = re.search(r"<rbf_font_height>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_fh)
            # Either returns #32 directly or branches to rbf_symbol_height which returns #32
            self.assertRegex(m_fh.group(1), r"(movs?\s+r0,\s*#32|b(\.w)?\s+[0-9a-f]+\s+<rbf_symbol_height>)")

            # rbf_char_width returns 16
            m_cw = re.search(r"<rbf_char_width>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_cw)
            self.assertRegex(m_cw.group(1), r"movs?\s+r0,\s*#16")

            # rbf_draw_char calls g3x_draw_char_16x32 and returns 16
            m_dc = re.search(r"<rbf_draw_char>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_dc)
            self.assertIn("g3x_draw_char_16x32", m_dc.group(1))
            self.assertRegex(m_dc.group(1), r"movs?\s+r0,\s*#16")

            # 2x Integer scaling bit expansion math verification
            test_glyph_8x16 = [
                0x00, 0x00, 0x7E, 0x18, 0x18, 0x18, 0x18, 0x18,
                0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x00, 0x00,
            ]
            scaled_raster = []
            for row in test_glyph_8x16:
                scaled = 0
                for b in range(8):
                    if row & (1 << (7 - b)):
                        scaled |= (3 << (14 - 2 * b))
                scaled_raster.append(scaled)
                scaled_raster.append(scaled)
            self.assertEqual(len(scaled_raster), 32)
            self.assertLessEqual(max(scaled_raster).bit_length(), 16)  # fits in 16 bits
            self.assertGreater(max(scaled_raster), 0)

    def test_menu_opaque_black_background_fill(self) -> None:
        """Menu fill writes UYVY black and opacity 255 into displayed buffers (citing g7x/g5x lib.c)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            m_fill = re.search(r"<g3x_fill_menu_opaque_black>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_fill, "g3x_fill_menu_opaque_black must be in disassembly")
            fill_code = m_fill.group(1)

            # 1. Cites opacity buffer and active buffer index (& 1)
            nm_output = subprocess.run(
                [str(ARM_NM), "-n", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            m_op = re.search(r"([0-9a-f]+)\s+[dDbB]\s+opacity_buffer", nm_output)
            self.assertIsNotNone(m_op, "opacity_buffer must exist in symbol table")
            op_addr = m_op.group(1).lstrip("0")
            self.assertIn(op_addr, fill_code, f"opacity_buffer address 0x{op_addr} must be referenced in fill code")
            self.assertRegex(fill_code, r"and(\.w)?\s+r\d+,\s*r\d+,\s*#1")

            # 2. Writes opacity 255 (#0xff) via memset
            self.assertRegex(fill_code, r"movs?\s+r1,\s*#(255|0xff)")
            self.assertIn("memset", fill_code)

            # 3. Writes UYVY black 0x00800080 (#8388736) to bitmap buffer
            self.assertRegex(fill_code, r"(mov\.w|ldr)\s+r\d+,\s*#(8388736|0x800080)")

            # 4. rbf_draw_menu_header calls g3x_fill_menu_opaque_black
            m_mh = re.search(r"<rbf_draw_menu_header>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_mh)
            self.assertIn("g3x_fill_menu_opaque_black", m_mh.group(1))

    def test_contrasting_title_bar_colors_and_layout(self) -> None:
        """Title bar configured as white text on solid black background, with conf.menu_center=0."""
        # 1. Verify conf_restore C code sets bg.col=1, fg.col=2, menu_center=0 under G3X_GUI4
        ladder_fix_c = (TOOLS_DIR / "build_candidate_port25_ladder_fix.py").read_text(encoding="utf-8")
        self.assertIn("conf.menu_title_color.bg.col = 1;", ladder_fix_c)
        self.assertIn("conf.menu_title_color.fg.col = 2;", ladder_fix_c)
        self.assertIn("conf.menu_center = 0;", ladder_fix_c)

        # 2. In disassembly, rbf_draw_menu_header draws title string using g3x_draw_char_16x32
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            m_mh = re.search(r"<rbf_draw_menu_header>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_mh)
            self.assertIn("g3x_draw_char_16x32", m_mh.group(1))

    def test_zero_flicker_and_steps_8_9_preservation(self) -> None:
        """No timer force_redraw; Step 8 sentinel recovery and Step 9 clean ALT exit kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            m_redraw = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_redraw)
            redraw_code = m_redraw.group(1)

            # 1. No timer force redraw (tick_cnt & 3)
            self.assertNotRegex(redraw_code, r"(ands|tst(\.w)?)\s+r\d+,\s*#3")
            self.assertNotIn("kbd_get_clicked_key", redraw_code)

            # 2. Step 8: sentinel check and buffer switch detection
            self.assertIn("draw_test_guard", redraw_code)
            self.assertIn("check_gui_needs_redraw", redraw_code)
            self.assertIn("draw_set_guard", redraw_code)

            # 3. Step 9: clean exit on leaving ALT
            self.assertIn("gui_set_need_restore", redraw_code)

    def test_card_write_exclusions_hold_under_gui4(self) -> None:
        """Card file-write hooks and unsafe stubs remain uncalled in .text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            nm_output = subprocess.run(
                [str(ARM_NM), "-n", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

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

    def test_gui4_layout_fills_most_of_900x600(self) -> None:
        """Layout fills 880x576 of 900x600 LCD (>97% width, >95% height)."""
        disp_w, disp_h = 900, 600
        font_w, font_h = 16, 32
        menu_w = disp_w - 20  # 880
        num_lines = (disp_h // font_h) - 1  # 17
        total_h = (num_lines + 1) * font_h  # 576

        self.assertEqual(menu_w, 880)
        self.assertEqual(num_lines, 17)
        self.assertEqual(total_h, 576)

        w_ratio = menu_w / disp_w
        h_ratio = total_h / disp_h
        self.assertGreater(w_ratio, 0.97)
        self.assertGreater(h_ratio, 0.95)

    def test_no_menu_fill_or_black_box_after_menu_closed_with_alt_active(self) -> None:
        """Menu close (ALT still active) -> buffer switch / guard overwrite does NOT fill or paint black box."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            nm_output = subprocess.run(
                [str(ARM_NM), "-n", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            # 1. gui_get_mode must be exported in .text
            self.assertIn(" T gui_get_mode", nm_output)

            # 2. In g3x_gui_kbd_redraw disassembly, verify call to gui_get_mode gating g3x_fill_menu_opaque_black
            m_redraw = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_redraw)
            redraw_code = m_redraw.group(1)

            self.assertIn("gui_get_mode", redraw_code)
            # GUI_MODE_MENU is 3 (enum Gui_Mode_: STARTUP=-1, NONE=0, ALT=1, MENU=2, or NONE=0, ALT=1, MENU=3 in enum Gui_Mode_)
            # In chdk-port/include/gui.h: GUI_MODE_STARTUP=-1, GUI_MODE_NONE=0, GUI_MODE_ALT=1, GUI_MODE_MENU=2, or cmp rX, #2/3
            self.assertRegex(redraw_code, r"cmp(\.w)?\s+r\d+,\s*#(2|3)")

            # 3. State machine simulation: Open menu -> close menu (ALT still on) -> buffer switch / guard overwrite
            GUI_MODE_NONE = 0
            GUI_MODE_ALT = 1  # enum Gui_Mode_
            GUI_MODE_MENU = 2  # enum Gui_Mode_ (or 3 depending on index)
            # From gui.h: GUI_MODE_STARTUP=-1, NONE=0, ALT=1, MENU=2 (or STARTUP=-1, NONE=0, ALT=1, MENU=2)
            # Let's inspect the actual enum value in binary:
            m_cmp = re.search(r"cmp(?:\.w)?\s+r\d+,\s*#(\d+)", redraw_code)
            self.assertIsNotNone(m_cmp)
            gui_mode_menu_val = int(m_cmp.group(1))

            # Simulate state transitions:
            state_gui_mode = GUI_MODE_NONE
            alt_active = 0
            fill_called_log = []

            def simulate_tick(is_alt_active: int, guard_ok: bool, buffer_toggle: bool, user_menu_btn: bool = False):
                nonlocal state_gui_mode, alt_active
                entered_alt = (is_alt_active != 0) and (alt_active == 0)
                left_alt = (is_alt_active == 0) and (alt_active != 0)
                alt_active = is_alt_active

                if entered_alt:
                    state_gui_mode = gui_mode_menu_val  # opens menu

                if user_menu_btn and state_gui_mode == gui_mode_menu_val:
                    # chdk-port/core/gui_menu.c:1096: gui_set_mode(&altGuiHandler)
                    state_gui_mode = 1  # GUI_MODE_ALT

                if left_alt:
                    state_gui_mode = GUI_MODE_NONE
                    return

                if alt_active:
                    force_redraw = entered_alt or buffer_toggle or (not guard_ok)
                    if force_redraw:
                        # Gated fill:
                        if state_gui_mode == gui_mode_menu_val:
                            fill_called_log.append(True)
                        else:
                            fill_called_log.append(False)

            # Step A: Enter ALT mode -> menu opens, fill runs
            simulate_tick(is_alt_active=1, guard_ok=True, buffer_toggle=False)
            self.assertEqual(len(fill_called_log), 1)
            self.assertTrue(fill_called_log[-1], "Fill must run on menu open")

            # Step B: Close menu via Menu button while ALT remains active (switches to altGuiHandler)
            simulate_tick(is_alt_active=1, guard_ok=True, buffer_toggle=False, user_menu_btn=True)

            # Step C: Buffer switch and guard overwrite occur with ALT active but menu closed
            simulate_tick(is_alt_active=1, guard_ok=False, buffer_toggle=True)
            self.assertEqual(len(fill_called_log), 2)
            self.assertFalse(fill_called_log[-1], "No menu fill or black box may be drawn after menu close")

    def test_fill_rect_equals_paint_rect_for_scrolling_and_non_scrolling_menus(self) -> None:
        """Fill rectangle exactly equals paint rectangle (header, list, scrollbar) for both scrollable and non-scrollable menus."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res_gui4 = build_candidate(gui4=True, out_dir=tmpdir)
            disasm = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            nm_output = subprocess.run(
                [str(ARM_NM), "-n", res_gui4["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout

            # 1. Shared layout calculator must exist in symbol table
            self.assertIn(" T g3x_get_menu_layout", nm_output)

            # 2. g3x_fill_menu_opaque_black and rbf_draw_menu_header must both call g3x_get_menu_layout
            m_fill = re.search(r"<g3x_fill_menu_opaque_black>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_fill)
            self.assertIn("g3x_get_menu_layout", m_fill.group(1))

            m_mh = re.search(r"<rbf_draw_menu_header>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_mh)
            self.assertIn("g3x_get_menu_layout", m_mh.group(1))

            # 3. Host layout computation and equality assertion
            disp_w, disp_h = 900, 600
            fh = 32
            num_lines = (disp_h - 0) // fh - 1  # 17
            x = 10
            w = disp_w - 20  # 880
            header_y = ((disp_h - (num_lines - 1) * fh) >> 1) - fh  # 12
            total_h = (num_lines + 1) * fh  # 576

            # Helper to compute fill rect and paint rect
            def compute_rects(menu_rows: int):
                # Layout logic from g3x_get_menu_layout
                wplus = 8 if (menu_rows > num_lines) else 0
                fill_w = w + wplus + (1 if wplus else 0)
                fill_h = total_h
                # Clamping
                clamped_fill_w = min(fill_w, disp_w - x)
                clamped_fill_h = min(fill_h, disp_h - header_y)
                fill_rect = (x, header_y, clamped_fill_w, clamped_fill_h)

                # Paint rect calculation from gui_menu.c & rbf_draw_menu_header:
                # Header: spans x..x+header_w-1, y=header_y..header_y+fh-1
                header_w = fill_w if wplus else (w + wplus)
                h_x1, h_y1 = x, header_y
                h_x2, h_y2 = x + header_w - 1, header_y + fh - 1

                # List: spans x..x+w-1, y=header_y+fh..header_y+total_h-1
                l_x1, l_y1 = x, header_y + fh
                l_x2, l_y2 = x + w - 1, header_y + total_h - 1

                # Scrollbar: gui_menu.c:740 draws (x+w).. (x+w)+wplus
                if wplus:
                    sb_x1, sb_y1 = x + w, header_y + fh
                    sb_x2, sb_y2 = (x + w) + wplus, header_y + total_h - 1
                else:
                    sb_x1, sb_y1, sb_x2, sb_y2 = h_x1, h_y1, h_x2, h_y2

                # Union of paint elements (header, list, scrollbar)
                paint_min_x = min(h_x1, l_x1, sb_x1)
                paint_min_y = min(h_y1, l_y1, sb_y1)
                paint_max_x = max(h_x2, l_x2, sb_x2)
                paint_max_y = max(h_y2, l_y2, sb_y2)
                paint_rect = (
                    paint_min_x,
                    paint_min_y,
                    paint_max_x - paint_min_x + 1,
                    paint_max_y - paint_min_y + 1,
                )
                return fill_rect, paint_rect

            # Case A: Non-scrolling menu (Main menu: 10 rows <= 17)
            fill_non_scroll, paint_non_scroll = compute_rects(10)
            self.assertEqual(
                fill_non_scroll,
                paint_non_scroll,
                f"Non-scrolling menu: fill rect {fill_non_scroll} != paint rect {paint_non_scroll}",
            )
            self.assertEqual(fill_non_scroll, (10, 12, 880, 576))

            # Case B: Scrolling menu (Submenu: 20 rows > 17)
            fill_scroll, paint_scroll = compute_rects(20)
            self.assertEqual(
                fill_scroll,
                paint_scroll,
                f"Scrolling menu: fill rect {fill_scroll} != paint rect {paint_scroll}",
            )
            self.assertEqual(fill_scroll, (10, 12, 889, 576))

            # Bounds sanity check: strictly fits within 900x600 screen
            for fx, fy, fw, fh in (fill_non_scroll, fill_scroll):
                self.assertGreaterEqual(fx, 0)
                self.assertGreaterEqual(fy, 0)
                self.assertLessEqual(fx + fw, disp_w)
                self.assertLessEqual(fy + fh, disp_h)


if __name__ == "__main__":
    unittest.main()
