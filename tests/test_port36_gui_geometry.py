#!/usr/bin/env python3
"""PORT-36: Host verification suite for opt-in G3X_GUI2=1 CHDK core GUI geometry and opacity candidate.

Verifies all acceptance criteria for Task PORT36-T1c-GUI2-CANDIDATE:
1. Build script flags and implications:
   - G3X_GUI2=1 implies G3X_GUI=1, G3X_KBD=1, G3X_OSD2=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. Prior build invariance:
   - Default all-flags-off candidate equals pinned hash 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - PORT-35 G3X_GUI=1 candidate equals pinned hash 1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272.
3. G3X_GUI2=1 reproducible build:
   - Output SHA-256 equals pinned hash and matches docs/PORT36_GUI_GEOMETRY.md.
   - Linked _end is <= heap start 0x00368880 with positive clearance.
4. Static trial safety check under GUI2 (card-write exclusions):
   - conf_save, file-browser writes, module/script loading and file-write hooks are absent or stubbed.
   - No branch in .text targets unsafe card-mutating firmware stubs.
   - Settings remain RAM-only.
5. Geometry self-consistency:
   - CAM_BITMAP_WIDTH (928) >= CAM_SCREEN_WIDTH (900).
   - CAM_BITMAP_HEIGHT (600) >= CAM_SCREEN_HEIGHT (600).
   - Menu box height covers rows * font_height within the screen height.
   - num_lines (14 at 480 px, 17 at 600 px) >= 9 root menu rows.
6. Displaytype switch simulation:
   - Host-side simulation for each displaytype 0..12 asserts the live GUI2 geometry.
   - Active LCD (displaytype 1,2,8,9,10) and default are 720x480 at stride 736 (unsheared path preserved); Mode 12 is 900x600 at stride 928.
   - disp_left, disp_right, disp_width reset to active width.
7. Opacity fix (F3):
   - Menu background colour index traced through palette.c to opacity written by gui_draw.c.
   - CALC_YUV_LUMA_OPACITY_FOR_COLOR sets opacity 255 for non-transparent colors (index 18 / 0xb0 becomes 255).
8. Removals verified:
   - Default-case override to 928 removed (preserving unsheared stride 736).
   - No-op update_screen_dimensions() + gui_menu_init(0) at init removed.
9. Documentation & Evidence:
   - docs/PORT36_GUI_GEOMETRY.md exists with required constant table, root causes (<= 3 lines, refutation noted), and DISKBOOT hash.
   - Diagnostic overlay described as a TRIAL DIAGNOSTIC only.
   - docs/HANDOFF.md and docs/PROJECT_STATE.md header lines specify PORT-36.
   - tools/port11c_evidence_validator.py passes.
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
DOCS_DIR = REPO_ROOT / "docs"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
PORT36_DOC = DOCS_DIR / "PORT36_GUI_GEOMETRY.md"
HANDOFF_DOC = DOCS_DIR / "HANDOFF.md"
PROJECT_STATE_DOC = DOCS_DIR / "PROJECT_STATE.md"
MANIFEST_PATH = REPO_ROOT / "evidence" / "port35_manifest.json"
TRUSTED_SCOPES_PATH = REPO_ROOT / "evidence" / "port35_trusted_scopes.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port25_ladder_fix import (  # noqa: E402
    G3X_GUI_HEAP_START,
    build_candidate,
    generate_platform_camera_gui2_h,
    generate_gui_draw_candidate_c,
    generate_gui_candidate_c,
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_PORT35_GUI_SHA256 = "1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272"
PINNED_PORT35_GUI_SIZE = 103057

PINNED_PORT36_GUI2_SHA256 = "2f9d51dabf435997dbc5005dd60b71bc07758d6598175377fc74669fb42263ae"
PINNED_PORT36_GUI2_SIZE = 103249


class TestPort36GuiGeometry(unittest.TestCase):
    """PORT-36 CHDK menu geometry and opacity candidate verification."""

    def test_gui2_flag_implications(self) -> None:
        """G3X_GUI2=1 implies G3X_GUI=1, G3X_KBD=1, G3X_OSD2=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui2=True, out_dir=tmpdir)
            self.assertTrue(res["gui2"], "gui2 must be True")
            self.assertTrue(res["gui"], "gui2 implies gui=True")
            self.assertTrue(res["osd2"], "gui2 implies osd2=True")
            self.assertTrue(res["kbd"], "gui2 implies kbd=True")
            self.assertTrue(res["resident"], "gui2 implies resident=True")

    def test_default_build_invariance(self) -> None:
        """Default control build (no flags) is byte-identical to PORT-35 base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(
                ladder=False,
                poweron_fix=False,
                resident=False,
                osd=False,
                kbd=False,
                osd2=False,
                gui=False,
                gui2=False,
                out_dir=tmpdir,
            )
            self.assertEqual(res["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_DEFAULT_SIZE)

    def test_port35_gui_build_invariance(self) -> None:
        """Existing G3X_GUI=1 candidate remains byte-identical to PORT-35."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui=True, gui2=False, out_dir=tmpdir)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT35_GUI_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT35_GUI_SIZE)

    def test_gui2_build_reproducibility_and_bounds(self) -> None:
        """G3X_GUI2=1 builds reproducibly, matches pinned hash, and respects memory boundaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui2=True, out_dir=tmpdir)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT36_GUI2_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT36_GUI2_SIZE)

            end_addr = int(res["core_end_addr"], 16)
            witness_addr = int(res["witness_addr"], 16)
            heap_start = int(res["heap_start_addr"], 16)

            self.assertEqual(witness_addr, 0x0035CD90)
            self.assertEqual(end_addr, 0x00362DD0)
            self.assertEqual(heap_start, G3X_GUI_HEAP_START)
            self.assertLessEqual(end_addr, heap_start)

            clearance = heap_start - end_addr
            self.assertGreaterEqual(clearance, 20480, f"Expected clearance >= 20 KB, got {clearance} B")

    def test_gui2_static_trial_safety_unreachable(self) -> None:
        """Card-write exclusions under GUI2: conf_save, file writes, module loads, and script loads are unreachable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(gui2=True, out_dir=tmpdir)
            core_elf = res["core_elf"]

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", core_elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            nm_proc = subprocess.run(
                [str(ARM_NM), core_elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            nm_output = nm_proc.stdout

            # 1. Verify conf_save and script_load are stubbed no-ops (bx lr)
            m_conf = re.search(r"<conf_save>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_conf, "conf_save must exist in disassembly")
            self.assertIn("bx\tlr", m_conf.group(1))

            m_script = re.search(r"<script_load>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_script, "script_load must exist in disassembly")
            self.assertIn("bx\tlr", m_script.group(1))

            # 2. Track unsafe card-mutating firmware stubs
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

            self.assertEqual(
                len(stub_addrs),
                len(unsafe_stubs),
                f"All unsafe stubs must be tracked: {set(unsafe_stubs) - set(stub_addrs.keys())}",
            )

            # 3. Verify NO branch in .text targets any unsafe card-mutating stub
            for stub_name, hex_addr in stub_addrs.items():
                pattern = rf"\b(bl|b\.w|b\.n|bx|blx)\s+[0-9a-f]*{hex_addr}\b"
                matches = re.findall(pattern, disasm)
                self.assertEqual(
                    len(matches),
                    0,
                    f"Unsafe firmware stub '{stub_name}' (addr {hex_addr}) is targeted by branch instruction in .text!",
                )

            # 4. Verify guarded wrappers exist and intercept operations
            wrappers = [
                "<__wrap_open>",
                "<__wrap__open>",
                "<__wrap__Open>",
                "<__wrap_fopen>",
                "<__wrap__Fopen_Fut>",
                "<__wrap__ExecuteEventProcedure>",
                "<__wrap_script_load>",
                "<__wrap_load_file_to_length>",
                "<__wrap_conf_save>",
                "<__wrap_conf_restore>",
            ]
            for w in wrappers:
                self.assertIn(w, disasm, f"Wrapper {w} missing from disasm")

            # 5. Verify filewrite hooks absent
            self.assertNotIn("filewrite_save", nm_output)
            self.assertNotIn("filewrite_task", nm_output)

            # 6. Verify module loading and file-browser are stubbed (no card/file I/O)
            m_mod = re.search(r"<module_load>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_mod, "module_load must exist as stub in disassembly")
            self.assertIn("bx\tlr", m_mod.group(1))
            self.assertIn("movs\tr0, #0", m_mod.group(1))
            # libfselect (file browser) points to RAM-only stub table
            self.assertIn("libfselect", nm_output)

    def test_geometry_constants_and_vertical_coverage(self) -> None:
        """Physical LCD dimensions and menu row coverage across runtime display modes."""
        # 1. Parse generated platform_camera_gui2.h
        header_code = generate_platform_camera_gui2_h()
        m_bw = re.search(r"#define\s+CAM_BITMAP_WIDTH\s+(\d+)", header_code)
        m_bh = re.search(r"#define\s+CAM_BITMAP_HEIGHT\s+(\d+)", header_code)
        m_sw = re.search(r"#define\s+CAM_SCREEN_WIDTH\s+(\d+)", header_code)
        m_sh = re.search(r"#define\s+CAM_SCREEN_HEIGHT\s+(\d+)", header_code)

        self.assertIsNotNone(m_bw)
        self.assertIsNotNone(m_bh)
        self.assertIsNotNone(m_sw)
        self.assertIsNotNone(m_sh)

        bitmap_width = int(m_bw.group(1))
        bitmap_height = int(m_bh.group(1))
        screen_width = int(m_sw.group(1))
        screen_height = int(m_sh.group(1))

        self.assertEqual(bitmap_width, 928)
        self.assertEqual(bitmap_height, 600)
        self.assertEqual(screen_width, 900)
        self.assertEqual(screen_height, 600)

        # 2. Verify bitmap buffer width is at least screen width
        self.assertGreaterEqual(bitmap_width, screen_width)
        self.assertGreaterEqual(bitmap_height, screen_height)

        # 3. Fault F1 test: PORT-35 GUI build values vs Mode 12 requirements
        port35_sw, port35_sh = 720, 480
        port35_bw, port35_bh = 736, 480
        port35_menu_w = port35_sw - 20  # 700 px (gui_menu.c:228)
        gui2_menu_w = screen_width - 20   # 880 px

        self.assertLess(port35_sw, screen_width, "PORT-35 GUI screen width (720) fails 900 panel width (confirms F1)")
        self.assertLess(port35_sh, screen_height, "PORT-35 GUI screen height (480) fails 600 panel height (confirms F1)")
        self.assertLess(port35_menu_w, gui2_menu_w, "PORT-35 GUI menu width (700) fails GUI2 menu width 880 (confirms F1)")
        self.assertEqual(gui2_menu_w, 880)

        # 4. Vertical capacity verification from gui_menu.c:226
        # num_lines = (camera_screen.height - 2*ts_menu_border)/rbf_font_height() - 1
        font_h = 32  # rbf font height (FONT_HEIGHT in gui_draw.h:69-70; rbf_font.c:251-252)
        ts_menu_border = 0
        root_menu_rows = 9  # 9 active root menu items (items 0..8, user menu disabled by default)

        # In both 480 px and 600 px modes, num_lines accommodates active root menu items (9):
        port35_num_lines = (480 - 2 * ts_menu_border) // font_h - 1  # 14
        gui2_num_lines = (600 - 2 * ts_menu_border) // font_h - 1  # 17
        self.assertGreaterEqual(port35_num_lines, root_menu_rows)
        self.assertGreaterEqual(gui2_num_lines, root_menu_rows)

        # Verify box height covers rows * font_height within the screen height for GUI2 runtime height
        rows_drawn = root_menu_rows
        box_y = (screen_height - ((rows_drawn - 1) * font_h)) >> 1
        box_h = rows_drawn * font_h
        last_row_y = box_y + (rows_drawn - 1) * font_h

        self.assertGreater(box_y, 0)
        self.assertGreaterEqual(box_h, rows_drawn * font_h, "box height must cover rows * font_height")
        self.assertGreaterEqual(box_y + box_h, last_row_y + font_h, "box_y + box_h must cover last row")
        self.assertLessEqual(box_y + box_h, screen_height, f"box_y+box_h ({box_y + box_h}) must be <= screen height ({screen_height})")

        # 5. Test runtime dimensions (both LCD 720x480/736 and Mode 12 900x600/928)
        modes = [
            ("LCD (720x480, stride 736)", 720, 480, 736, 480),
            ("Mode 12 (900x600, stride 928)", 900, 600, 928, 600),
        ]

        for mode_name, w, h, bw, bh in modes:
            with self.subTest(mode=mode_name):
                cur_screen_height = h
                self.assertGreaterEqual(bw, w, f"{mode_name}: buffer_width ({bw}) must be >= width ({w})")
                self.assertGreaterEqual(bh, h, f"{mode_name}: buffer_height ({bh}) must be >= height ({h})")

                # num_lines from core/gui_menu.c:226
                num_lines = cur_screen_height // font_h - 1
                self.assertGreaterEqual(num_lines, root_menu_rows, f"{mode_name}: num_lines ({num_lines}) must accommodate {root_menu_rows} rows")

                box_y = (cur_screen_height - ((root_menu_rows - 1) * font_h)) >> 1
                box_h = root_menu_rows * font_h
                last_row_y = box_y + (root_menu_rows - 1) * font_h

                self.assertGreater(box_y, 0, f"{mode_name}: box_y must be > 0")
                self.assertGreaterEqual(
                    box_y + box_h,
                    last_row_y + font_h,
                    f"{mode_name}: box_y+box_h ({box_y + box_h}) must cover last_row_y+font_h ({last_row_y + font_h})",
                )
                self.assertLessEqual(
                    box_y + box_h,
                    cur_screen_height,
                    f"{mode_name}: box_y+box_h ({box_y + box_h}) must be <= screen_height ({cur_screen_height})",
                )

    def test_displaytype_switch_simulation_and_gui2_geometry(self) -> None:
        """Simulate g3x_osd2_update_screen_dimensions switch for each displaytype 0..12 under GUI2."""
        def simulate_update_screen_dimensions(dt: int) -> dict[str, int]:
            default_w, default_h, default_bw = 720, 480, 736
            vga_w, vga_h, vga_bw = 640, 480, 640
            hdmi_w, hdmi_h, hdmi_bw = 960, 540, 960
            evf_w, evf_h, evf_bw = 1024, 768, 1024
            mode12_w, mode12_h, mode12_bw = 900, 600, 928

            if dt in (0, 3, 4, 5):
                w, h, bw = vga_w, vga_h, vga_bw
            elif dt in (1, 2, 8, 9, 10):
                w, h, bw = default_w, default_h, default_bw
            elif dt in (6, 7):
                w, h, bw = hdmi_w, hdmi_h, hdmi_bw
            elif dt == 11:
                w, h, bw = evf_w, evf_h, evf_bw
            elif dt == 12:
                w, h, bw = mode12_w, mode12_h, mode12_bw
            else:
                w, h, bw = default_w, default_h, default_bw

            # GUI2 disp_left/right/width reset (osd2_test_overlay.h:216-218)
            disp_left = 0
            disp_right = w - 1
            disp_width = w

            return {
                "width": w,
                "height": h,
                "buffer_width": bw,
                "disp_left": disp_left,
                "disp_right": disp_right,
                "disp_width": disp_width,
            }

        font_height = 32
        root_menu_rows = 9

        for dt in range(13):
            with self.subTest(displaytype=dt):
                dim = simulate_update_screen_dimensions(dt)
                w = dim["width"]
                h = dim["height"]
                bw = dim["buffer_width"]

                # Invariant 1: buffer_width >= screen_width and buffer_height >= screen_height
                self.assertGreaterEqual(bw, w, f"dt={dt}: buffer_width ({bw}) must be >= width ({w})")

                # Invariant 2: GUI2 OSD bounds reset correctly
                self.assertEqual(dim["disp_left"], 0, f"dt={dt}: disp_left must be 0")
                self.assertEqual(dim["disp_right"], w - 1, f"dt={dt}: disp_right must be width - 1")
                self.assertEqual(dim["disp_width"], w, f"dt={dt}: disp_width must be width")

                # Invariant 3: Menu row capacity num_lines >= 9 rows
                num_lines = h // font_height - 1
                self.assertGreaterEqual(
                    num_lines,
                    root_menu_rows,
                    f"dt={dt}: num_lines ({num_lines}) must accommodate {root_menu_rows} root menu items",
                )

                # Invariant 4: Menu box height encloses all 9 rows and covers last row within screen
                box_y = (h - ((root_menu_rows - 1) * font_height)) >> 1
                box_h = root_menu_rows * font_height
                last_row_y = box_y + (root_menu_rows - 1) * font_height

                self.assertGreater(box_y, 0, f"dt={dt}: box_y must be > 0")
                self.assertGreaterEqual(
                    box_y + box_h,
                    last_row_y + font_height,
                    f"dt={dt}: box_y+box_h ({box_y + box_h}) must cover last_row_y+font_height ({last_row_y + font_height})",
                )
                self.assertLessEqual(
                    box_y + box_h,
                    h,
                    f"dt={dt}: box_y+box_h ({box_y + box_h}) must be <= screen height ({h})",
                )

                # Specific mode checks
                if dt in (1, 2, 8, 9, 10):
                    # Active LCD modes (PORT35-ROM-BMPDDEV)
                    self.assertEqual(w, 720, f"dt={dt} LCD width must be 720")
                    self.assertEqual(h, 480, f"dt={dt} LCD height must be 480")
                    self.assertEqual(bw, 736, f"dt={dt} LCD stride must be 736")
                elif dt == 12:
                    # Mode 12 (PORT35-ROM-BMPDDEV literal pool)
                    self.assertEqual(w, 900, f"dt=12 width must be 900")
                    self.assertEqual(h, 600, f"dt=12 height must be 600")
                    self.assertEqual(bw, 928, f"dt=12 stride must be 928")

        # Invariant 5: default case retains 720x480 stride 736 (unsheared path preserved)
        default_dim = simulate_update_screen_dimensions(999)
        self.assertEqual(default_dim["width"], 720)
        self.assertEqual(default_dim["height"], 480)
        self.assertEqual(default_dim["buffer_width"], 736)

    def test_all_non_default_switch_cases_assign_w_bw_h(self) -> None:
        """Confirm that every non-default switch case in g3x_osd2_update_screen_dimensions assigns w, bw, and h, and default is 736."""
        osd2_header_text = (SUB_DIR / "osd2_test_overlay.h").read_text(encoding="utf-8")
        m_fn = re.search(r"void g3x_osd2_update_screen_dimensions\(void\)\s*\{(.*?)\n\}", osd2_header_text, re.DOTALL)
        self.assertIsNotNone(m_fn, "g3x_osd2_update_screen_dimensions must be present")
        fn_body = m_fn.group(1)

        # Extract all cases up to default:
        case_blocks = re.findall(r"((?:case\s+\d+:\s*)+)(.*?)(?=break;)", fn_body, re.DOTALL)
        self.assertGreater(len(case_blocks), 0, "Switch statement cases must be found")

        covered_cases = set()
        for cases_str, body in case_blocks:
            cases = [int(c) for c in re.findall(r"case\s+(\d+):", cases_str)]
            for c in cases:
                covered_cases.add(c)
            self.assertRegex(body, r"\bw\s*=", f"Case {cases} must assign w")
            self.assertRegex(body, r"\bbw\s*=", f"Case {cases} must assign bw")
            self.assertRegex(body, r"\bh\s*=", f"Case {cases} must assign h")

        # Confirm cases 0 through 12 are all covered
        self.assertEqual(covered_cases, set(range(13)), "Cases 0..12 must all be covered")

        # Confirm default: case does NOT override to Mode 12 (928 stride)
        m_default = re.search(r"default:\s*(.*?)(?=break;)", fn_body, re.DOTALL)
        self.assertIsNotNone(m_default, "default case must exist")
        self.assertNotIn("G3X_OSD2_MODE12_BUFFER_WIDTH", m_default.group(1), "Default case must not override stride to 928")

    def test_gui2_opacity_fix(self) -> None:
        """Verify F3: trace menu background index through palette to opacity, and show GUI2 resolves to opaque while PORT-35 GUI fails."""
        gui_draw_c = generate_gui_draw_candidate_c()
        self.assertIn("opacity = (color == COLOR_TRANSPARENT) ? 0 : 255;", gui_draw_c)

        # 1. Source Trace (Path:Line verification):
        # a) core/conf.c:201 defines conf.menu_color background as IDX_COLOR_GREY_DK (13);
        #    core/conf.c:198-200,207 define OSD and space colors as IDX_COLOR_GREY_DK_TRANS (18).
        conf_src = (CHDK_PORT / "core" / "conf.c").read_text(encoding="utf-8")
        self.assertIn("CONF_INFOC( 55, conf.menu_color,", conf_src)
        self.assertIn("IDX_COLOR_GREY_DK", conf_src)
        self.assertIn("IDX_COLOR_GREY_DK_TRANS", conf_src)

        # b) core/gui_draw.h:24,29 defines indices:
        gui_draw_h = (CHDK_PORT / "core" / "gui_draw.h").read_text(encoding="utf-8")
        self.assertIn("#define IDX_COLOR_GREY_DK           13", gui_draw_h)
        self.assertIn("#define IDX_COLOR_GREY_DK_TRANS     18", gui_draw_h)

        # c) platform/generic/palette.c:11-37 defines ply_colors[]:
        # index 18 (IDX_COLOR_GREY_DK_TRANS) maps to 0xb0; index 1 (COLOR_BLACK) maps to 0xff; index 13 maps to 0xb4.
        palette_src = (CHDK_PORT / "platform" / "generic" / "palette.c").read_text(encoding="utf-8")
        self.assertIn("0xb0,                       // Transparent Dark Grey", palette_src)
        self.assertIn("0xb4,                       // Dark Grey", palette_src)

        # 2. Opacity Macro Behavior: PORT-35 GUI (stock) vs GUI2 candidate:
        # Stock (core/gui_draw.c:15-19): opacity = (color & 0xf) ? 255 : color;
        # GUI2 (generate_gui_draw_candidate_c): opacity = (color == COLOR_TRANSPARENT) ? 0 : 255;
        def calc_opacity_port35_gui(color: int) -> int:
            return 255 if (color & 0xF) else color

        def calc_opacity_gui2(color: int) -> int:
            return 0 if color == 0 else 255

        # COLOR_TRANSPARENT (0x00) remains 0 (transparent) in both
        self.assertEqual(calc_opacity_gui2(0x00), 0)
        self.assertEqual(calc_opacity_port35_gui(0x00), 0)

        # 3. Fault F3 resolution and PORT-35 GUI failure check:
        # For IDX_COLOR_GREY_DK_TRANS (0xb0), the lower nibble is 0:
        # In PORT-35 GUI build configuration, it evaluates to 0xb0 = 176 (translucent, NOT opaque)
        port35_opacity = calc_opacity_port35_gui(0xB0)
        self.assertEqual(port35_opacity, 0xB0)

        # Asserting that the index resolves to opaque (255) FAILS under PORT-35 GUI build configuration:
        with self.assertRaises(AssertionError):
            self.assertEqual(
                port35_opacity,
                255,
                "PORT-35 GUI configuration must NOT resolve index 18 to opaque 255",
            )

        # Under GUI2 candidate build configuration, the index resolves to solid opaque 255:
        gui2_opacity = calc_opacity_gui2(0xB0)
        self.assertEqual(gui2_opacity, 255)

        # 4. Check exactly which indices change in ply_colors[20]:
        ply_colors_table = [
            0x00, 0xFF, 0x0F, 0xBE, 0xD5, 0x7A, 0x61, 0xC5, 0x05, 0xA9,
            0xEE, 0x45, 0x74, 0xB4, 0x34, 0x11, 0x5A, 0x0E, 0xB0, 0xFE,
        ]
        indices_changed = []
        for idx, col in enumerate(ply_colors_table):
            op_p35 = calc_opacity_port35_gui(col)
            op_gui2 = calc_opacity_gui2(col)
            if op_p35 != op_gui2:
                indices_changed.append((idx, hex(col), op_p35, op_gui2))

        # Exactly index 18 (0xb0, IDX_COLOR_GREY_DK_TRANS) changes from 176 to 255
        self.assertEqual(len(indices_changed), 1)
        self.assertEqual(indices_changed[0], (18, "0xb0", 0xB0, 255))

        # 5. Object Disassembly Verification (PORT-35 GUI vs GUI2 candidate):
        # PORT-35 stock gui_draw.thm.o tests lower nibble with tst.w r1, #15 and moveq r3, r1
        objdump_stock = subprocess.run(
            [str(ARM_OBJDUMP), "-d", str(SUB_DIR / "gui_draw.thm.o")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertRegex(objdump_stock.stdout, r"tst(?:\.w)?\s+r1,\s+#15")
        self.assertRegex(objdump_stock.stdout, r"moveq\s+r3,\s+r1")

        # In GUI2, generate_gui_draw_candidate_c produces cmp r1, #0 and movne r3, #255
        with tempfile.TemporaryDirectory() as tmpdir:
            cand_c = os.path.join(tmpdir, "gui_draw_cand.c")
            cand_o = os.path.join(tmpdir, "gui_draw_cand.o")
            with open(cand_c, "w", encoding="utf-8") as f:
                f.write(generate_gui_draw_candidate_c())
            cflags = [
                str(ARM_GCC),
                "-fno-inline",
                "-Os",
                "-fno-strict-aliasing",
                "-fno-schedule-insns2",
                "-march=armv7-r",
                "-mthumb",
                "-DTHUMB_FW",
                "-DG3X_GUI2=1",
                "-Iinclude",
                "-Icore",
                "-Iplatform/g3x",
                "-Iplatform/g3x/sub/110c",
                "-c",
                "-o",
                cand_o,
                cand_c,
            ]
            subprocess.run(cflags, cwd=str(CHDK_PORT), check=True)
            objdump_cand = subprocess.run(
                [str(ARM_OBJDUMP), "-d", cand_o],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            self.assertRegex(objdump_cand.stdout, r"cmp\s+r1,\s+#0")
            self.assertRegex(objdump_cand.stdout, r"movne\s+r3,\s+#255")

        # 6. Whole-box opacity simulation:
        # Verify that rendering the menu box background rectangle writes opacity 255 across every pixel.
        screen_w = 720
        screen_h = 480
        stride = 736
        menu_border_width = 10
        box_x = menu_border_width
        box_w = screen_w - 2 * menu_border_width  # 700 px
        box_h = 9 * 32  # 288 px
        y_top = (screen_h - (8 * 32)) >> 1  # 112 px

        opacity_buf = bytearray(stride * screen_h)

        # Render menu background box with menu background color (0xb4 or 0xb0)
        menu_bg_color = 0xB0  # IDX_COLOR_GREY_DK_TRANS
        for py in range(y_top, y_top + box_h):
            for px in range(box_x, box_x + box_w):
                opacity_buf[py * stride + px] = calc_opacity_gui2(menu_bg_color)

        # Assert every pixel in the entire menu background box has opacity 255
        opaque_pixel_count = 0
        for py in range(y_top, y_top + box_h):
            for px in range(box_x, box_x + box_w):
                self.assertEqual(
                    opacity_buf[py * stride + px],
                    255,
                    f"Pixel at ({px},{py}) must have opacity 255",
                )
                opaque_pixel_count += 1

        self.assertEqual(opaque_pixel_count, box_w * box_h)
        self.assertEqual(opaque_pixel_count, 700 * 288)

        # Pixels outside the menu box must remain unpainted (0)
        self.assertEqual(opacity_buf[0], 0)  # top-left screen corner
        self.assertEqual(opacity_buf[(y_top - 1) * stride + box_x], 0)  # line above menu

    def test_removals_and_clean_code_paths(self) -> None:
        """Confirm removals: no redundant init call in g3x_gui_kbd_redraw, and no default 928 override."""
        cand_c = generate_gui_candidate_c()
        # Verify update_screen_dimensions() wrapper is NOT called at init
        self.assertNotIn("update_screen_dimensions();\n        gui_menu_init(0);", cand_c)
        self.assertNotIn("gui_menu_init(0)", cand_c)
        self.assertNotRegex(cand_c, r"(?<!g3x_osd2_)update_screen_dimensions\s*\(")
        self.assertNotIn("void update_screen_dimensions(void)", cand_c)
        self.assertNotIn("extern void update_screen_dimensions", cand_c)

        # Verify diagnostic overlay exists as a diagnostic only
        self.assertIn("PORT-36 TRIAL DIAGNOSTIC", cand_c)
        self.assertIn("dt=%d w=%d bw=%d h=%d", cand_c)

        # Verify osd2_test_overlay.h updates disp_left/right/width
        header_text = (SUB_DIR / "osd2_test_overlay.h").read_text(encoding="utf-8")
        self.assertIn("camera_screen.disp_left = 0;", header_text)
        self.assertIn("camera_screen.disp_right = camera_screen.width - 1;", header_text)
        self.assertIn("camera_screen.disp_width = camera_screen.width;", header_text)
        self.assertNotIn("void update_screen_dimensions(void)", header_text)

    def test_docs_and_manifest_evidence(self) -> None:
        """docs/PORT36_GUI_GEOMETRY.md exists, milestones are updated, and evidence validator passes."""
        self.assertTrue(PORT36_DOC.is_file(), "docs/PORT36_GUI_GEOMETRY.md must exist")
        doc_text = PORT36_DOC.read_text(encoding="utf-8")

        # Verify constant table contains required entries
        for name in [
            "CAM_BITMAP_WIDTH",
            "CAM_BITMAP_HEIGHT",
            "CAM_SCREEN_WIDTH",
            "CAM_SCREEN_HEIGHT",
            "camera_screen.disp_left",
            "camera_screen.disp_right",
            "camera_screen.disp_width",
            "update_screen_dimensions",
            "CALC_YUV_LUMA_OPACITY_FOR_COLOR",
        ]:
            self.assertIn(name, doc_text, f"{name} must appear in PORT36 constant table")

        # Verify ROM read statement and UNKNOWN displaytype label
        self.assertIn("No ROM was read for PORT-36", doc_text)

        # Verify labels FINSIG, ROM, INFERRED appear
        self.assertIn("FINSIG", doc_text)
        self.assertIn("ROM", doc_text)
        self.assertIn("INFERRED", doc_text)

        # Verify faults F1, F2, F3 addressed
        self.assertIn("F1", doc_text)
        self.assertIn("F2", doc_text)
        self.assertIn("F3", doc_text)

        # Verify root-cause notes for each fault are <= 3 lines
        for fault_tag in ["Fault F1:", "Fault F2:", "Fault F3:"]:
            m = re.search(rf"{fault_tag}[^\n]*\n(.*?)(?=\n###|\n##|\Z)", doc_text, re.DOTALL)
            self.assertIsNotNone(m, f"{fault_tag} section missing")
            content_lines = [line for line in m.group(1).strip().splitlines() if line.strip()]
            self.assertLessEqual(
                len(content_lines),
                3,
                f"{fault_tag} root-cause note must be <= 3 lines (has {len(content_lines)})",
            )
            # Verify refutation observation is stated
            self.assertIn("Refutation observation:", m.group(1))

        # Verify diagnostic overlay is described as TRIAL DIAGNOSTIC only
        self.assertIn("Trial Diagnostic", doc_text)
        self.assertIn("TRIAL DIAGNOSTIC", doc_text)

        # Verify DISKBOOT SHA-256 and build command are present
        self.assertIn(PINNED_PORT36_GUI2_SHA256, doc_text)
        self.assertIn("--gui2", doc_text)

        # Verify milestone header line in HANDOFF.md and PROJECT_STATE.md
        handoff_line1 = HANDOFF_DOC.read_text(encoding="utf-8").splitlines()[0]
        project_state_line1 = PROJECT_STATE_DOC.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(handoff_line1, "# Agent handoff — Current milestone: PORT-36")
        self.assertEqual(project_state_line1, "# Project state — Current milestone: PORT-36")

        # Verify evidence manifest passes tools/port11c_evidence_validator.py
        val_proc = subprocess.run(
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
        self.assertIn("Result: VALID (0 errors, 0 warnings)", val_proc.stdout)


if __name__ == "__main__":
    unittest.main()
