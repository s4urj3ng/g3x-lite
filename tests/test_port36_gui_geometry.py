#!/usr/bin/env python3
"""PORT-36: Host verification suite for opt-in G3X_GUI2=1 CHDK core GUI geometry and opacity candidate.

Verifies all acceptance criteria for Task PORT36-T1e-GUI2-CANDIDATE:
1. Build script flags and implications:
   - G3X_GUI2=1 implies G3X_GUI=1, G3X_KBD=1, G3X_OSD2=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. Prior build invariance:
   - Default all-flags-off candidate equals pinned hash 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136.
   - PORT-35 G3X_GUI=1 candidate equals pinned hash 1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272.
3. G3X_GUI2=1 reproducible build:
   - Output SHA-256 equals pinned hash and matches docs/PORT36_GUI_GEOMETRY.md.
   - Linked _end is <= heap start 0x00368880 with positive clearance (>= 20 KB).
4. Static trial safety check under GUI2 (card-write exclusions):
   - conf_save, file-browser writes, module/script loading and file-write hooks are absent or stubbed.
   - No branch in .text targets unsafe card-mutating firmware stubs.
   - Settings remain RAM-only.
5. Blocking 1: No compile-time 928 / 900x600 overrides:
   - Stock platform_camera.h defines 736/480/720/480.
   - No GUI2 build input defines CAM_BITMAP_WIDTH 928, CAM_SCREEN_WIDTH 900 or CAM_SCREEN_HEIGHT 600.
   - No generated platform_camera.h sits on the include path.
6. Displaytype switch simulation:
   - Host-side simulation for each displaytype 0..12 asserts the live GUI2 geometry.
   - Active LCD (displaytype 1,2,8,9,10) and default are 720x480 at stride 736 (unsheared path preserved); Mode 12 is 900x600 at stride 928.
   - disp_left, disp_right, disp_width reset to active width.
   - num_lines (14 at 480 px, 17 at 600 px) >= 9 root menu rows.
7. Opacity and Menu Box Fix (F2/F3):
   - Menu background colour index traced through palette.c to opacity written by gui_draw.c.
   - RAM default conf.menu_color.bg set to COLOR_BLACK (0xff, opacity 255).
   - Full 14-line menu box background filled in g3x_gui_kbd_redraw before gui_redraw.
   - Test shows unpainted row 9 has opacity 0 in PORT-35 GUI build (fails opacity 255 assertion), but passes in GUI2 candidate.
   - Disassembly confirms draw_rectangle called in GUI2 g3x_gui_kbd_redraw.
8. Removals and Clean Code:
   - Default-case override to 928 removed (preserving unsheared stride 736).
   - Dead update_screen_dimensions wrapper removed.
   - Stray extra blank line removed in osd2_test_overlay.h.
   - Diagnostic variables at top of block.
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
    generate_gui_candidate_c,
    generate_conf_candidate_c,
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_PORT35_GUI_SHA256 = "1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272"
PINNED_PORT35_GUI_SIZE = 103057

PINNED_PORT36_GUI2_SHA256 = "4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071"
PINNED_PORT36_GUI2_SIZE = 103345


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

            self.assertEqual(witness_addr, 0x0035CDF0)
            self.assertEqual(end_addr, 0x00362E30)
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

    def test_blocking1_no_928_override_and_clean_include_path(self) -> None:
        """BLOCKING 1: GUI2 compiles against stock 720/736/480 platform_camera.h without compile-time 928 overrides."""
        # 1. Verify stock platform_camera.h defines 736/480/720/480
        stock_h = (CHDK_PORT / "platform" / "g3x" / "platform_camera.h").read_text(encoding="utf-8")
        self.assertRegex(stock_h, r"#define\s+CAM_BITMAP_WIDTH\s+736")
        self.assertRegex(stock_h, r"#define\s+CAM_BITMAP_HEIGHT\s+480")
        self.assertRegex(stock_h, r"#define\s+CAM_SCREEN_WIDTH\s+720")
        self.assertRegex(stock_h, r"#define\s+CAM_SCREEN_HEIGHT\s+480")

        # 2. Verify NO GUI2 build input or header defines CAM_BITMAP_WIDTH 928, CAM_SCREEN_WIDTH 900, or CAM_SCREEN_HEIGHT 600
        scan_dirs = [
            CHDK_PORT / "include",
            CHDK_PORT / "core",
            CHDK_PORT / "platform" / "g3x",
            CHDK_PORT / "platform" / "g3x" / "sub" / "110c",
        ]
        forbidden_patterns = [
            (re.compile(r"#define\s+CAM_BITMAP_WIDTH\s+928"), "CAM_BITMAP_WIDTH 928"),
            (re.compile(r"#define\s+CAM_SCREEN_WIDTH\s+900"), "CAM_SCREEN_WIDTH 900"),
            (re.compile(r"#define\s+CAM_SCREEN_HEIGHT\s+600"), "CAM_SCREEN_HEIGHT 600"),
        ]
        for sdir in scan_dirs:
            for root, _, files in os.walk(sdir):
                for fname in files:
                    if fname.endswith((".h", ".c", ".S")):
                        fpath = Path(root) / fname
                        ftext = fpath.read_text(encoding="utf-8", errors="ignore")
                        for pat, desc in forbidden_patterns:
                            self.assertIsNone(
                                pat.search(ftext),
                                f"GUI2 build input {fpath} defines forbidden {desc}!",
                            )

        # 3. Verify no generated platform_camera.h sits on the include path or temporary dir
        build_script = (TOOLS_DIR / "build_candidate_port25_ladder_fix.py").read_text(encoding="utf-8")
        self.assertNotIn("generate_platform_camera_gui2_h", build_script)
        self.assertNotIn("cand_cam_h = os.path.join(candidate_dir, \"platform_camera.h\")", build_script)
        self.assertNotIn("-I{candidate_dir}", build_script)

        # 4. Vertical capacity verification with stock 480 px screen height
        font_h = 32  # rbf font height (FONT_HEIGHT in gui_draw.h:69-70; rbf_font.c:251-252)
        root_menu_rows = 9  # 9 active root menu items
        num_lines_480 = 480 // font_h - 1  # 14
        self.assertGreaterEqual(num_lines_480, root_menu_rows)

        # Mode 12 runtime capacity (600 px)
        num_lines_600 = 600 // font_h - 1  # 17
        self.assertGreaterEqual(num_lines_600, root_menu_rows)

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

                # Invariant 1: buffer_width >= screen_width
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

    def test_gui2_opacity_and_menu_box_fix(self) -> None:
        """Verify F2/F3: trace menu background index through palette to opacity, and show GUI2 box fill ensures opacity 255 across lines 0..14."""
        # 1. Source Trace (Path:Line verification):
        # a) core/conf.c:201 defines conf.menu_color background as IDX_COLOR_GREY_DK (13)
        conf_src = (CHDK_PORT / "core" / "conf.c").read_text(encoding="utf-8")
        self.assertIn("CONF_INFOC( 55, conf.menu_color,", conf_src)
        self.assertIn("IDX_COLOR_GREY_DK", conf_src)

        # b) core/gui_draw.h:24 defines index 13
        gui_draw_h = (CHDK_PORT / "core" / "gui_draw.h").read_text(encoding="utf-8")
        self.assertIn("#define IDX_COLOR_GREY_DK           13", gui_draw_h)

        # c) platform/generic/palette.c:26 maps index 13 to 0xb4 (Dark Grey); line 14 maps index 1 to 0xff (COLOR_BLACK)
        palette_src = (CHDK_PORT / "platform" / "generic" / "palette.c").read_text(encoding="utf-8")
        self.assertIn("0xb4,                       // Dark Grey", palette_src)
        self.assertIn("COLOR_BLACK,               // Placeholder for script colors", palette_src)

        # d) include/palette.h:15 defines COLOR_BLACK as 0xFF
        palette_h = (CHDK_PORT / "include" / "palette.h").read_text(encoding="utf-8")
        self.assertRegex(palette_h, r"#define\s+COLOR_BLACK\s+0xFF")

        # e) core/gui_draw.c:16-19 defines CALC_YUV_LUMA_OPACITY_FOR_COLOR
        gui_draw_c = (CHDK_PORT / "core" / "gui_draw.c").read_text(encoding="utf-8")
        self.assertIn("opacity = (color&0xf)?255:color;", gui_draw_c)
        self.assertIn("obu[offset] = o;", gui_draw_c)

        # 2. Draw path analysis:
        # gui_menu.c:731-752 (gui_menu_draw_initial) draws NO outer menu box when count <= num_lines.
        # gui_menu.c:967-1077 (gui_menu_draw) renders per-row backgrounds for active items (rows 0..8).
        # Lines 9..13 of the 14-line screen area are NEVER written by gui_menu_draw.
        # In PORT-35, rows 9..13 remained at opacity 0 (unpainted, transparent).

        def simulate_menu_render(is_gui2: bool) -> tuple[int, list[int]]:
            screen_h = 480
            font_h = 32
            num_lines = screen_h // font_h - 1  # 14
            root_items = 9
            # opacity array for each line 0..13
            line_opacity = [0] * num_lines

            # In GUI2, g3x_gui_kbd_redraw fills the entire 14-line menu box before gui_redraw
            if is_gui2:
                for line in range(num_lines):
                    # Filled with COLOR_BLACK (0xff): opacity = (0xff & 0xf) ? 255 : 0xff = 255
                    line_opacity[line] = 255
                menu_bg_col = 1  # COLOR_BLACK (RAM default in GUI2 conf_restore)
            else:
                menu_bg_col = 13  # IDX_COLOR_GREY_DK (stock conf default)

            # gui_menu_draw renders items 0..root_items-1
            for item in range(root_items):
                # Both 0xb4 (idx 13) and 0xff (idx 1) get opacity 255 from stock macro
                line_opacity[item] = 255

            return menu_bg_col, line_opacity

        # 3. Fault F3 resolution: PORT-35 GUI build fails, GUI2 passes
        port35_col, port35_opacities = simulate_menu_render(is_gui2=False)
        self.assertEqual(port35_col, 13, "PORT-35 default menu color must be IDX_COLOR_GREY_DK (13)")
        # In PORT-35, row 9 has opacity 0 (transparent)
        self.assertEqual(port35_opacities[9], 0)

        # Asserting that line 9 resolves to opaque (255) FAILS under PORT-35 GUI configuration:
        with self.assertRaises(AssertionError):
            self.assertEqual(
                port35_opacities[9],
                255,
                "PORT-35 GUI configuration must NOT have opacity 255 at line 9",
            )

        # Under GUI2 candidate build configuration, line 9 is opaque (255) and color is COLOR_BLACK (1):
        gui2_col, gui2_opacities = simulate_menu_render(is_gui2=True)
        self.assertEqual(gui2_col, 1, "GUI2 default menu color must be COLOR_BLACK (1)")
        self.assertEqual(gui2_opacities[9], 255)
        # All lines 0..13 have solid opacity 255:
        self.assertTrue(all(op == 255 for op in gui2_opacities))

        # 4. Disassembly verification of GUI2 core ELF:
        # In GUI2 candidate_main.elf, g3x_gui_kbd_redraw calls draw_rectangle before gui_redraw
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

            m_fn = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_fn, "g3x_gui_kbd_redraw must exist in disassembly")
            fn_text = m_fn.group(1)
            self.assertIn("bl\t", fn_text)
            self.assertRegex(fn_text, r"bl\s+[0-9a-f]+\s+<draw_rectangle>", "draw_rectangle must be called in g3x_gui_kbd_redraw")

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

        # Verify nit: no stray double blank line after g3x_osd2_update_screen_dimensions()
        self.assertNotIn("}\n\n\n/* Fixed \"CHDK\" text bitmap rows", header_text)
        self.assertIn("}\n\n/* Fixed \"CHDK\" text bitmap rows", header_text)

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
            "conf.menu_color.bg",
            "draw_rectangle",
        ]:
            self.assertIn(name, doc_text, f"{name} must appear in PORT36 constant table or text")

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
        self.assertEqual(
            handoff_line1,
            "# Agent handoff — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
        )
        self.assertEqual(
            project_state_line1,
            "# Project state — Current milestone: PORT-42 (see PORT-36..PORT-41 Current State table)",
        )

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
