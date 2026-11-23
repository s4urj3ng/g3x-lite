"""Offline unit and integration tests for PORT-53 (G3X_PLAYBACK_MENU=1).

Verifies:
1. Flag gating: No PLAYBACK_MENU symbols or code emitted when the flag is off.
2. Key mapping and physw bits match physw_bits.txt and docs/PORT46_KEYMAP.md.
3. Card write safety: conf save is unreachable when writes are disabled and SAVE:OFF marker is set.
4. Default build DISKBOOT.BIN is byte-identical to the PORT-52 default.
5. Deliverables: Candidate manifest for config (c) (without FULL_HOOKS), notes.txt, trial plan, and evidence manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
SYNC_HEADER = ROOT / "chdk-port/platform/g3x/sub/110c/gui_sync.h"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
SUB_MAKEFILE = ROOT / "chdk-port/platform/g3x/sub/110c/Makefile"
KBD_C = ROOT / "chdk-port/platform/g3x/kbd.c"
LIB_C = ROOT / "chdk-port/platform/g3x/lib.c"
MAIN_C = ROOT / "chdk-port/platform/g3x/main.c"
GUI_MENU_C = ROOT / "chdk-port/platform/g3x/gui_menu.c"
PLAT_CAMERA_H = ROOT / "chdk-port/platform/g3x/platform_camera.h"
PLAT_KBD_H = ROOT / "chdk-port/platform/g3x/platform_kbd.h"
PHYSW_BITS = ROOT / "reference/finsig_gm110c/physw_bits.txt"
DOC_KEYMAP = ROOT / "docs/PORT46_KEYMAP.md"
DOC_TRIAL = ROOT / "docs/PORT53_TRIAL.md"
NOTES_TXT = ROOT / "chdk-port/platform/g3x/notes.txt"
G5X_NOTES_TXT = ROOT / "chdk-port/platform/g5x/notes.txt"
MANIFEST_P53 = ROOT / "manifests/port53_playback_menu_manifest.json"
MANIFEST_EVIDENCE = ROOT / "manifests/evidence/port53_evidence_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_PORT52_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_PORT52_DEFAULT_SIZE = 124097

BASE_PORT51_RESTORE2_NO_FULLHOOKS_SHA256 = "f8df17f182289b4a100e8c348ecdca1ea7f2e9a8c1613058d9777dd832fed3cf"
BASE_PORT51_RESTORE2_NO_FULLHOOKS_SIZE = 131865
BASE_PORT51_RESTORE2_NO_FULLHOOKS_END = "0x0036a8e0"

BASE_PORT53_CANDIDATE_SHA256 = "620f39ccae74eceae96f9e4b6c41c77f3ed5e5219c42a013067b36241d6bf759"
BASE_PORT53_CANDIDATE_SIZE = 132209
BASE_PORT53_CORE_END = "0x0036aa40"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def distribution_snapshot(path: Path) -> dict[str, dict[str, int | str]]:
    files = [path / "DISKBOOT.BIN", *sorted((path / "CHDK").rglob("*"))]
    if not (path / "CHDK").is_dir():
        raise AssertionError(f"Missing CHDK distribution: {path}")
    return {
        p.relative_to(path).as_posix(): {
            "size": p.stat().st_size,
            "sha256": sha256_file(p),
        }
        for p in files
        if p.is_file()
    }


class TestPort53FlagPlumbing(unittest.TestCase):
    def test_flag_definitions_in_makefiles(self):
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        sub_mf = SUB_MAKEFILE_INC.read_text(encoding="utf-8")

        self.assertIn("ifeq ($(G3X_PLAYBACK_MENU),1)", plat_mf)
        self.assertIn("CFLAGS += -DG3X_PLAYBACK_MENU=1", plat_mf)
        self.assertIn("ifeq ($(G3X_PLAYBACK_MENU),1)", sub_mf)
        self.assertIn("CFLAGS += -DG3X_PLAYBACK_MENU=1", sub_mf)

    def test_source_code_properly_gated(self):
        for path in (MAIN_C, GUI_MENU_C, DIAG_HEADER):
            self.assertTrue(path.is_file(), f"Missing {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn("G3X_PLAYBACK_MENU", text, f"G3X_PLAYBACK_MENU not referenced in {path}")
            self.assertIn("#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)", text,
                          f"G3X_PLAYBACK_MENU preprocessor check missing in {path}")


class TestPort53KeymapAndPhysw(unittest.TestCase):
    def test_physw_bits_match_keymap_for_playback_navigation(self):
        self.assertTrue(PHYSW_BITS.is_file(), f"Missing {PHYSW_BITS}")
        self.assertTrue(KBD_C.is_file(), f"Missing {KBD_C}")
        self.assertTrue(PLAT_CAMERA_H.is_file(), f"Missing {PLAT_CAMERA_H}")
        self.assertTrue(PLAT_KBD_H.is_file(), f"Missing {PLAT_KBD_H}")
        self.assertTrue(DOC_KEYMAP.is_file(), f"Missing {DOC_KEYMAP}")

        physw_text = PHYSW_BITS.read_text(encoding="utf-8")
        kbd_text = KBD_C.read_text(encoding="utf-8")
        cam_text = PLAT_CAMERA_H.read_text(encoding="utf-8")
        kbd_h_text = PLAT_KBD_H.read_text(encoding="utf-8")
        keymap_doc = DOC_KEYMAP.read_text(encoding="utf-8")

        # Parse navigation and ALT key bits from docs/PORT46_KEYMAP.md
        nav_and_alt_keys = [
            "KEY_MENU",
            "KEY_UP",
            "KEY_DOWN",
            "KEY_RIGHT",
            "KEY_LEFT",
            "KEY_SET",
            "KEY_VIDEO",
            "KEY_DISPLAY",
            "KEY_WIFI",
            "KEY_PLAYBACK",
        ]
        parsed_doc_keys = {}
        for k in nav_and_alt_keys:
            m = re.search(rf"\|\s*{re.escape(k)}[^\n|]*\|\s*w(\d+)\.b(\d+),\s*`?(0x[0-9a-fA-F]+)`?", keymap_doc)
            self.assertIsNotNone(m, f"Could not parse {k} from {DOC_KEYMAP}")
            word = int(m.group(1))
            bit = int(m.group(2))
            hex_str = m.group(3)
            mask_val = int(hex_str, 16)
            self.assertEqual(mask_val, 1 << bit, f"Mask for {k} ({hex_str}) does not match bit {bit}")
            parsed_doc_keys[k] = (word, bit, mask_val, hex_str)

        # Assert parsed doc values match both physw_bits.txt and kbd.c / platform headers
        for k, (word, bit, mask_val, hex_str) in parsed_doc_keys.items():
            # 1. Matches kbd.c key mapping table
            kbd_pattern = rf"\{{\s*{word},\s*{re.escape(k)}\s*,\s*{re.escape(hex_str)}\s*\}}"
            self.assertRegex(kbd_text, kbd_pattern, f"{k} mapping in kbd.c does not match {DOC_KEYMAP}")

            # 2. Matches reference/finsig_gm110c/physw_bits.txt
            physw_pattern = rf"\s+{word}\s+{re.escape(hex_str)}"
            self.assertRegex(physw_text, physw_pattern, f"{k} bit in physw_bits.txt does not match {DOC_KEYMAP}")

        # 1. KEY_MENU: w0.b4, mask 0x00000010, event 0x14
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_MENU\s*,\s*0x00000010\s*\}')
        self.assertRegex(physw_text, r'0x00000014\s+0\s+0x00000010')

        # 2. D-pad navigation keys:
        #    UP: w0.b5, 0x20, event 0x06
        #    DOWN: w0.b6, 0x40, event 0x07
        #    RIGHT: w0.b7, 0x80, event 0x09
        #    LEFT: w0.b8, 0x100, event 0x08
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_UP\s*,\s*0x00000020\s*\}')
        self.assertRegex(physw_text, r'0x00000006\s+0\s+0x00000020')

        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_DOWN\s*,\s*0x00000040\s*\}')
        self.assertRegex(physw_text, r'0x00000007\s+0\s+0x00000040')

        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_RIGHT\s*,\s*0x00000080\s*\}')
        self.assertRegex(physw_text, r'0x00000009\s+0\s+0x00000080')

        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_LEFT\s*,\s*0x00000100\s*\}')
        self.assertRegex(physw_text, r'0x00000008\s+0\s+0x00000100')

        # 3. KEY_SET: w0.b9, mask 0x00000200, event 0x0a
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_SET\s*,\s*0x00000200\s*\}')
        self.assertRegex(physw_text, r'0x0000000a\s+0\s+0x00000200')

        # 4. KEY_DISPLAY: w0.b12, mask 0x00001000, event 0x0d
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_DISPLAY\s*,\s*0x00001000\s*\}')
        self.assertRegex(physw_text, r'0x0000000d\s+0\s+0x00001000')

        # 5. ALT button: KEY_WIFI (default), KEY_VIDEO, KEY_DISPLAY, KEY_PLAYBACK
        self.assertIn("KEY_WIFI, KEY_VIDEO, KEY_DISPLAY, KEY_PLAYBACK", cam_text)
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_WIFI\s*,\s*0x00002000\s*\}')
        self.assertRegex(physw_text, r'0x00000103\s+0\s+0x00002000')

        # 6. KEY_PLAYBACK: w0.b16, mask 0x00010000, event 0x101
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_PLAYBACK\s*,\s*0x00010000\s*\}')
        self.assertRegex(physw_text, r'0x00000101\s+0\s+0x00010000')

        # 7. KEYS_MASK0 covers all menu and navigation keys
        self.assertIn("0x000533F9", kbd_h_text)
        keys_mask0 = 0x000533F9
        for k in nav_and_alt_keys:
            word, bit, mask_val, _ = parsed_doc_keys[k]
            if word == 0:
                self.assertTrue(keys_mask0 & mask_val, f"KEYS_MASK0 does not cover {k} (mask {hex(mask_val)})")
        self.assertFalse(keys_mask0 & 0x00020000) # KEY_POWER pass-through

    def test_playback_menu_active_predicate(self):
        build_script = ROOT / "scripts/build_port43_dbuf.py"
        self.assertTrue(build_script.is_file(), f"Missing {build_script}")
        script_text = build_script.read_text(encoding="utf-8")
        main_text = MAIN_C.read_text(encoding="utf-8")

        self.assertIn("int g3x_playback_menu_is_active(void)", script_text)
        self.assertIn("camera_info.state.mode_play && !camera_info.state.gui_mode_none", script_text)
        self.assertIn("int g3x_playback_menu_gui_mode_active(void)", script_text)
        self.assertIn("camera_info.state.mode_play && (camera_info.state.gui_mode_alt || !camera_info.state.gui_mode_none)", script_text)
        self.assertIn("int g3x_playback_menu_mode_check(void)", main_text)


class TestPort53BuildAndArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_c = ROOT / "out/port53-playback-menu"
        cls.build_b = ROOT / "out/build-playback-alone"
        cls.build_a = ROOT / "out/build-default"
        cls.build_p51_nofull = ROOT / "out/build-p51-nofull"

        # Ensure all builds are present and fresh
        if (
            not (cls.build_c / "DISKBOOT.BIN").is_file()
            or sha256_file(cls.build_c / "DISKBOOT.BIN") != BASE_PORT53_CANDIDATE_SHA256
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--no-overdraw",
                    "--kbd-check",
                    "--gui-diag",
                    "--shadow2",
                    "--gui-sync",
                    "--gui-menu",
                    "--gui-restore2",
                    "--playback-menu",
                    "--out-dir",
                    str(cls.build_c),
                ],
                cwd=ROOT,
                check=True,
            )

        # Ensure fresh build for build_b and build_c so cached artifacts do not mask link failures
        if (cls.build_b / "DISKBOOT.BIN").is_file():
            shutil.rmtree(cls.build_b, ignore_errors=True)

        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--playback-menu-alone",
                "--out-dir",
                str(cls.build_b),
            ],
            cwd=ROOT,
            check=True,
        )

        if (
            not (cls.build_a / "DISKBOOT.BIN").is_file()
            or not (cls.build_a / "stage_chdk/platform/g3x/sub/110c/main.elf").is_file()
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "tools/build_port41_full.py"),
                    "--keep-stage",
                    "--out-dir",
                    str(cls.build_a),
                ],
                cwd=ROOT,
                check=True,
            )

        if not (cls.build_p51_nofull / "DISKBOOT.BIN").is_file():
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--no-overdraw",
                    "--kbd-check",
                    "--gui-diag",
                    "--shadow2",
                    "--gui-sync",
                    "--gui-menu",
                    "--gui-restore2",
                    "--out-dir",
                    str(cls.build_p51_nofull),
                ],
                cwd=ROOT,
                check=True,
            )

    def test_default_build_is_byte_identical_to_port52_default(self):
        default_diskboot = self.build_a / "DISKBOOT.BIN"
        self.assertTrue(default_diskboot.is_file(), f"Missing {default_diskboot}")
        self.assertEqual(default_diskboot.stat().st_size, BASE_PORT52_DEFAULT_SIZE)
        self.assertEqual(sha256_file(default_diskboot), BASE_PORT52_DEFAULT_SHA256)

    def test_earlier_candidates_preserved_port51_restore2_nofullhooks(self):
        p51_diskboot = self.build_p51_nofull / "DISKBOOT.BIN"
        self.assertTrue(p51_diskboot.is_file(), f"Missing {p51_diskboot}")
        self.assertEqual(sha256_file(p51_diskboot), BASE_PORT51_RESTORE2_NO_FULLHOOKS_SHA256)
        self.assertEqual(p51_diskboot.stat().st_size, BASE_PORT51_RESTORE2_NO_FULLHOOKS_SIZE)

        manifest = json.loads((self.build_p51_nofull / "port51_restore2_core_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["_end"], BASE_PORT51_RESTORE2_NO_FULLHOOKS_END)
        self.assertEqual(manifest["core_end"], BASE_PORT51_RESTORE2_NO_FULLHOOKS_END)
        self.assertNotIn("FULL_HOOKS=1", manifest["build"]["flags"])
        self.assertNotIn("G3X_PLAYBACK_MENU=1", manifest["build"]["flags"])

    def test_playback_alone_build_artifacts(self):
        alone_diskboot = self.build_b / "DISKBOOT.BIN"
        self.assertTrue(alone_diskboot.is_file(), f"Missing {alone_diskboot}")
        self.assertGreater(alone_diskboot.stat().st_size, 0)

        manifest = json.loads((self.build_b / "port53_playback_menu_alone_manifest.json").read_text(encoding="utf-8"))
        self.assertIn("G3X_PLAYBACK_MENU=1", manifest["build"]["flags"])
        self.assertNotIn("FULL_HOOKS=1", manifest["build"]["flags"])
        self.assertNotIn("G3X_GUI_RESTORE2=1", manifest["build"]["flags"])

    def test_config_c_manifest_and_candidate_artifacts(self):
        self.assertTrue(MANIFEST_P53.is_file(), f"Missing {MANIFEST_P53}")
        pinned = json.loads(MANIFEST_P53.read_text(encoding="utf-8"))
        generated = json.loads((self.build_c / "port53_playback_menu_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(pinned, generated)

        expected_flags = [
            "G3X_FULL_BUILD=1",
            "G3X_DISABLE_CARD_WRITES=1",
            "CAM_SUPPORT_BITMAP_RES_CHANGE=1",
            "OPT_DISABLE_FILE_WRITES=1",
            "G3X_GUI5=1",
            "G3X_GUI_FIX=1",
            "G3X_GUI_DBUF=1",
            "G3X_GUI_NOOVERDRAW=1",
            "G3X_KBD_CHECK=1",
            "G3X_GUI_DIAG=1",
            "G3X_GUI_SHADOW2=1",
            "G3X_GUI_SYNC=1",
            "G3X_GUI_MENU=1",
            "G3X_GUI_RESTORE2=1",
            "G3X_PLAYBACK_MENU=1",
        ]
        self.assertEqual(pinned["build"]["flags"], expected_flags)
        self.assertNotIn("FULL_HOOKS=1", pinned["build"]["flags"])
        self.assertEqual(pinned["card_writes"], "disabled")
        self.assertIn("SAVE:OFF", pinned["card_writes_note"])

        self.assertEqual(pinned["core_end"], BASE_PORT53_CORE_END)
        self.assertEqual(pinned["_end"], BASE_PORT53_CORE_END)

        self.assertEqual(pinned["artifacts"]["DISKBOOT.BIN"]["sha256"], BASE_PORT53_CANDIDATE_SHA256)
        self.assertEqual(pinned["artifacts"]["DISKBOOT.BIN"]["size"], BASE_PORT53_CANDIDATE_SIZE)
        self.assertEqual(pinned["artifacts"]["modules_count"], 34)

        # Build command in manifest
        expected_cmd = (
            "python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --out-dir out/port53-playback-menu"
        )
        self.assertEqual(pinned["command"], expected_cmd)

    def test_flag_gating_symbol_presence_and_absence(self):
        default_elf = self.build_a / "stage_chdk/platform/g3x/sub/110c/main.elf"
        candidate_elf = self.build_c / "stage_chdk/platform/g3x/sub/110c/main.elf"
        alone_elf = self.build_b / "stage_chdk/platform/g3x/sub/110c/main.elf"

        self.assertTrue(default_elf.is_file(), f"Missing {default_elf}")
        self.assertTrue(candidate_elf.is_file(), f"Missing {candidate_elf}")
        self.assertTrue(alone_elf.is_file(), f"Missing {alone_elf}")

        default_nm = subprocess.check_output([str(NM), str(default_elf)], text=True)
        candidate_nm = subprocess.check_output([str(NM), str(candidate_elf)], text=True)
        alone_nm = subprocess.check_output([str(NM), str(alone_elf)], text=True)

        playback_symbols = [
            "g3x_playback_menu_is_active",
            "g3x_playback_menu_kbd_process",
            "g3x_playback_menu_gui_mode_active",
            "g3x_playback_menu_get_viewport_mode",
            "g3x_playback_menu_mode_check",
            "g3x_playback_menu_record_item_edit",
            "g3x_playback_menu_redraw_needed",
            "g3x_playback_menu_open_count",
            "g3x_playback_menu_item_edit_count",
            "g3x_playback_menu_diag_format",
            "g3x_playback_menu_diag_draw",
        ]

        # 1. Gating check: default build must NOT have any of the playback menu symbols
        for sym in playback_symbols:
            self.assertNotIn(sym, default_nm, f"Symbol {sym} leaked into default build!")

        # 2. Candidate build (config c) MUST have the playback menu symbols
        for sym in playback_symbols:
            self.assertIn(sym, candidate_nm, f"Symbol {sym} missing from config (c) candidate build!")

        # 3. Alone build (config b) MUST have the playback menu functions and definitions
        for sym in [
            "g3x_playback_menu_is_active",
            "g3x_playback_menu_kbd_process",
            "g3x_playback_menu_gui_mode_active",
            "g3x_playback_menu_get_viewport_mode",
            "g3x_playback_menu_mode_check",
            "g3x_playback_menu_record_item_edit",
            "g3x_conf_record_save_result",
            "g3x_playback_menu_item_edit_count",
            "g3x_playback_menu_diag_draw",
            "g3x_playback_menu_diag_format",
        ]:
            self.assertIn(sym, alone_nm, f"Symbol {sym} missing from config (b) alone build!")

    def test_playback_menu_alone_clean_build_and_link(self):
        """Verify that config (b) (G3X_PLAYBACK_MENU=1 alone) links cleanly without undefined symbols."""
        alone_elf = self.build_b / "stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(alone_elf.is_file(), f"Missing {alone_elf}")

        alone_diskboot = self.build_b / "DISKBOOT.BIN"
        self.assertTrue(alone_diskboot.is_file(), f"Missing {alone_diskboot}")
        self.assertGreater(alone_diskboot.stat().st_size, 0)

        nm_out = subprocess.check_output([str(NM), str(alone_elf)], text=True)
        undefined_symbols = set()
        defined_symbols = set()
        for line in nm_out.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == "U":
                undefined_symbols.add(parts[1])
            elif len(parts) == 3 and parts[1] != "U":
                defined_symbols.add(parts[2])

        self.assertNotIn("g3x_conf_record_save_result", undefined_symbols)
        self.assertNotIn("g3x_playback_menu_item_edit_count", undefined_symbols)
        self.assertIn("g3x_conf_record_save_result", defined_symbols)
        self.assertIn("g3x_playback_menu_item_edit_count", defined_symbols)

        g3x_undefined = [s for s in undefined_symbols if s.startswith("g3x_")]
        self.assertEqual(g3x_undefined, [], f"Unexpected undefined g3x symbols in config (b): {g3x_undefined}")

    def test_call_sites_inside_target_function_bodies(self):
        """Parse staged kbd.c and lib.c to assert each playback hook sits INSIDE the body of its target function."""
        def extract_function_body(source: str, func_pattern: str) -> str:
            m = re.search(rf"{func_pattern}\s*\{{", source)
            self.assertIsNotNone(m, f"Function matching {func_pattern} not found")
            open_pos = m.end() - 1
            depth = 0
            close_pos = -1
            for i in range(open_pos, len(source)):
                if source[i] == '{':
                    depth += 1
                elif source[i] == '}':
                    depth -= 1
                    if depth == 0:
                        close_pos = i
                        break
            self.assertGreater(close_pos, open_pos, f"Could not find matching closing brace for {func_pattern}")
            return source[open_pos + 1:close_pos]

        # 1. Check staged kbd.c in config (c)
        staged_kbd_c = self.build_c / "stage_chdk/platform/g3x/kbd.c"
        self.assertTrue(staged_kbd_c.is_file(), f"Missing {staged_kbd_c}")
        kbd_content = staged_kbd_c.read_text(encoding="utf-8")

        my_kbd_body = extract_function_body(kbd_content, r"void\s+my_kbd_read_keys\s*\(\s*\)")
        self.assertIn("g3x_playback_menu_kbd_process()", my_kbd_body,
                      "g3x_playback_menu_kbd_process() call missing from body of my_kbd_read_keys() in staged kbd.c")

        # 2. Check staged lib.c in config (c)
        staged_lib_c = self.build_c / "stage_chdk/platform/g3x/lib.c"
        self.assertTrue(staged_lib_c.is_file(), f"Missing {staged_lib_c}")
        lib_content = staged_lib_c.read_text(encoding="utf-8")

        vp_body = extract_function_body(lib_content, r"int\s+vid_get_viewport_width\s*\(\s*\)")
        self.assertIn("g3x_playback_menu_get_viewport_mode()", vp_body,
                      "g3x_playback_menu_get_viewport_mode() call missing from body of vid_get_viewport_width() in staged lib.c")

        # Find all check_gui_needs_redraw definitions in staged lib.c and verify hooks inside
        redraw_matches = list(re.finditer(r"int\s+check_gui_needs_redraw\s*\([^)]*\)\s*\{", lib_content))
        self.assertGreater(len(redraw_matches), 0, "No check_gui_needs_redraw definition found in staged lib.c")
        for match in redraw_matches:
            open_pos = match.end() - 1
            depth = 0
            close_pos = -1
            for i in range(open_pos, len(lib_content)):
                if lib_content[i] == '{':
                    depth += 1
                elif lib_content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        close_pos = i
                        break
            body = lib_content[open_pos + 1:close_pos]
            self.assertIn("g3x_playback_menu_gui_mode_active()", body,
                          "g3x_playback_menu_gui_mode_active() call missing from check_gui_needs_redraw body in staged lib.c")
            self.assertIn("g3x_playback_menu_redraw_needed()", body,
                          "g3x_playback_menu_redraw_needed() call missing from check_gui_needs_redraw body in staged lib.c")

    def test_conf_save_unreachable_and_save_off(self):
        candidate_elf = self.build_c / "stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(candidate_elf.is_file(), f"Missing {candidate_elf}")

        dump_out = subprocess.check_output([str(OBJDUMP), "-d", str(candidate_elf)], text=True)

        def get_func_body(func_name: str) -> str:
            m = re.search(rf"<{func_name}>:([\s\S]*?)(?:\n[0-9a-f]{{8}}\s+<|$)", dump_out)
            self.assertIsNotNone(m, f"Could not find <{func_name}> in objdump")
            return m.group(1)

        forbidden_write_calls = [
            "<write>",
            "<open>",
            "<close>",
            "<_Write>",
            "<_Open>",
            "<_Close>",
            "<fwrite>",
            "<fopen>",
            "<fclose>",
            "<__wrap_write>",
            "<__wrap_open>",
            "<__wrap_fwrite>",
        ]

        # conf_save() must call g3x_conf_record_save_result and must NOT call config_save or write stubs
        conf_save_body = get_func_body("conf_save")
        self.assertIn("<g3x_conf_record_save_result>", conf_save_body)
        self.assertNotIn("<config_save>", conf_save_body)
        self.assertNotIn("<save_params_values>", conf_save_body)
        for call in forbidden_write_calls:
            self.assertNotIn(call, conf_save_body)

        # config_save() must call g3x_conf_record_save_result and must NOT call write stubs
        config_save_body = get_func_body("config_save")
        self.assertIn("<g3x_conf_record_save_result>", config_save_body)
        for call in forbidden_write_calls:
            self.assertNotIn(call, config_save_body)

        # save_config_file() must call g3x_conf_record_save_result and must NOT call config_save or write stubs
        save_cfg_body = get_func_body("save_config_file")
        self.assertIn("<g3x_conf_record_save_result>", save_cfg_body)
        self.assertNotIn("<config_save>", save_cfg_body)
        for call in forbidden_write_calls:
            self.assertNotIn(call, save_cfg_body)

        # save_params_values() must not call write stubs
        save_params_body = get_func_body("save_params_values")
        for call in forbidden_write_calls:
            self.assertNotIn(call, save_params_body)

        # save_int_value_file() must not call write stubs
        save_int_body = get_func_body("save_int_value_file")
        for call in forbidden_write_calls:
            self.assertNotIn(call, save_int_body)

    def test_save_entry_points_guarded_in_staged_sources_config_b_and_c(self):
        """Host test: check that in actual staged sources for config (b) and (c),
        every save entry point (conf_save, config_save, save_config_file) is guarded
        and returns early with SAVE:OFF when card writes are disabled.
        """
        for build_name, build_path in [("config_b", self.build_b), ("config_c", self.build_c)]:
            staged_conf_c = build_path / "stage_chdk/core/conf.c"
            self.assertTrue(staged_conf_c.is_file(), f"Missing staged conf.c in {build_name}: {staged_conf_c}")
            conf_text = staged_conf_c.read_text(encoding="utf-8")

            # 1. config_save is guarded with early return calling g3x_conf_record_save_result(3)
            self.assertIn("void config_save(ConfInfo *ci, const char *filename, int config_base)\n{", conf_text)
            self.assertRegex(
                conf_text,
                r"void config_save\(ConfInfo \*ci, const char \*filename, int config_base\)\s*\{\s*"
                r"#if\s+\(\(defined\(G3X_GUI_MENU\)[\s\S]*?g3x_conf_record_save_result\(3\s*/\*\s*G3X_CONF_SAVE_OFF\s*\*/\);\s*return;\s*#else"
            )

            # 2. conf_save is guarded with early return calling g3x_conf_record_save_result(3)
            self.assertIn("void conf_save()\n{", conf_text)
            self.assertRegex(
                conf_text,
                r"void conf_save\(\)\s*\{\s*"
                r"#if\s+\(\(defined\(G3X_GUI_MENU\)[\s\S]*?g3x_conf_record_save_result\(3\s*/\*\s*G3X_CONF_SAVE_OFF\s*\*/\);\s*return;\s*#else"
            )

            # 3. save_config_file is guarded with early return calling g3x_conf_record_save_result(3)
            self.assertIn("int save_config_file(int config_base, const char *filename)\n{", conf_text)
            self.assertRegex(
                conf_text,
                r"int save_config_file\(int config_base, const char \*filename\)\s*\{\s*"
                r"#if\s+defined\(G3X_PLAYBACK_MENU\)[\s\S]*?g3x_conf_record_save_result\(3\s*/\*\s*G3X_CONF_SAVE_OFF\s*\*/\);\s*return 0;\s*#else"
            )

    def test_save_entry_points_compiled_asm_config_b_and_c(self):
        """Host test: check that in compiled ELFs for config (b) and (c),
        every save entry point (conf_save, config_save, save_config_file) calls
        g3x_conf_record_save_result and no unguarded call to config_save, save_params_values,
        or write calls remains.
        """
        forbidden_write_calls = [
            "<write>",
            "<open>",
            "<close>",
            "<_Write>",
            "<_Open>",
            "<_Close>",
            "<fwrite>",
            "<fopen>",
            "<fclose>",
            "<__wrap_write>",
            "<__wrap_open>",
            "<__wrap_fwrite>",
        ]

        for build_name, build_path in [("config_b", self.build_b), ("config_c", self.build_c)]:
            main_elf = build_path / "stage_chdk/platform/g3x/sub/110c/main.elf"
            self.assertTrue(main_elf.is_file(), f"Missing main.elf in {build_name}: {main_elf}")
            dump_out = subprocess.check_output([str(OBJDUMP), "-d", str(main_elf)], text=True)

            def get_func_body(func_name: str) -> str:
                m = re.search(rf"<{func_name}>:([\s\S]*?)(?:\n[0-9a-f]{{8}}\s+<|$)", dump_out)
                self.assertIsNotNone(m, f"Could not find <{func_name}> in objdump of {build_name}")
                return m.group(1)

            # conf_save: calls g3x_conf_record_save_result, NO call to config_save or save_params_values or write
            conf_save_body = get_func_body("conf_save")
            self.assertIn("<g3x_conf_record_save_result>", conf_save_body, f"conf_save in {build_name} missing record call")
            self.assertNotIn("<config_save>", conf_save_body, f"conf_save in {build_name} calls config_save")
            self.assertNotIn("<save_params_values>", conf_save_body, f"conf_save in {build_name} calls save_params_values")
            for call in forbidden_write_calls:
                self.assertNotIn(call, conf_save_body, f"conf_save in {build_name} contains forbidden call {call}")

            # config_save: calls g3x_conf_record_save_result, NO write calls
            config_save_body = get_func_body("config_save")
            self.assertIn("<g3x_conf_record_save_result>", config_save_body, f"config_save in {build_name} missing record call")
            for call in forbidden_write_calls:
                self.assertNotIn(call, config_save_body, f"config_save in {build_name} contains forbidden call {call}")

            # save_config_file: calls g3x_conf_record_save_result, NO call to config_save or write
            save_config_file_body = get_func_body("save_config_file")
            self.assertIn("<g3x_conf_record_save_result>", save_config_file_body, f"save_config_file in {build_name} missing record call")
            self.assertNotIn("<config_save>", save_config_file_body, f"save_config_file in {build_name} calls config_save")
            for call in forbidden_write_calls:
                self.assertNotIn(call, save_config_file_body, f"save_config_file in {build_name} contains forbidden call {call}")

    def test_diag_format_displays_save_off(self):
        diag_text = DIAG_HEADER.read_text(encoding="utf-8")
        self.assertIn("G3X_CONF_SAVE_OFF", diag_text)
        self.assertIn('"OFF"', diag_text)
        self.assertIn('"MENU:%04u SAVE:%s ED:%04u"', diag_text)

    def test_playback_menu_diag_reachable_from_gui_draw_path_config_b(self):
        """In staged and linked config (b) build, find a caller of g3x_playback_menu_diag_format
        (or equivalent draw function) reachable from the GUI draw path.
        """
        # 1. Staged source inspection
        staged_lib_c = self.build_b / "stage_chdk/platform/g3x/lib.c"
        self.assertTrue(staged_lib_c.is_file(), f"Missing {staged_lib_c}")
        lib_text = staged_lib_c.read_text(encoding="utf-8")
        self.assertIn("g3x_playback_menu_diag_draw()", lib_text)

        # 2. Linked binary call-graph inspection in config (b) ELF
        alone_elf = self.build_b / "stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(alone_elf.is_file(), f"Missing {alone_elf}")
        objdump_out = subprocess.check_output([str(OBJDUMP), "-d", str(alone_elf)], text=True)

        def extract_asm_body(func_name: str) -> str:
            m = re.search(rf"<{func_name}>:([\s\S]*?)(?:\n[0-9a-f]{{8}}\s+<|$)", objdump_out)
            self.assertIsNotNone(m, f"Function <{func_name}> not found in disassembly")
            return m.group(1)

        # core_spytask (main CHDK scheduler loop) calls check_gui_needs_redraw
        spytask_body = extract_asm_body("core_spytask")
        self.assertIn("<check_gui_needs_redraw>", spytask_body,
                      "core_spytask does not call check_gui_needs_redraw")

        # check_gui_needs_redraw calls g3x_playback_menu_diag_draw
        check_redraw_body = extract_asm_body("check_gui_needs_redraw")
        self.assertIn("<g3x_playback_menu_diag_draw>", check_redraw_body,
                      "check_gui_needs_redraw does not call g3x_playback_menu_diag_draw")

        # g3x_playback_menu_diag_draw calls g3x_playback_menu_diag_format and draw_string
        diag_draw_body = extract_asm_body("g3x_playback_menu_diag_draw")
        self.assertIn("<g3x_playback_menu_diag_format>", diag_draw_body,
                      "g3x_playback_menu_diag_draw does not call g3x_playback_menu_diag_format")
        self.assertIn("<draw_string>", diag_draw_body,
                      "g3x_playback_menu_diag_draw does not call draw_string")

    def test_skipped_conf_save_sets_save_off_formatter(self):
        """Host-compiled unit test: after a skipped save in config (b) and config (c),
        the formatted string contains SAVE:OFF.
        """
        import tempfile
        test_c = r"""
#include <stdio.h>
#include <string.h>
#include <assert.h>

#define G3X_PLAYBACK_MENU 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#include "gui_diag.h"

struct camera_screen_fallback camera_screen = {900, 600};

int draw_string(short x, short y, const char *s, unsigned short cl) {
    (void)x; (void)y; (void)s; (void)cl;
    return 0;
}

// Simulated config (b) wrapper
void __wrap_conf_save(void) {
    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);
}

// Simulated config (c) conf_save guard
void conf_save_candidate(void) {
    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);
}

int main(void) {
    char buf[64];

    // Initial state: no save attempted
    g3x_conf_save_status = G3X_CONF_SAVE_NONE;
    g3x_playback_menu_diag_format(buf, sizeof(buf));
    assert(strstr(buf, "SAVE:-") != NULL);

    // Test Config (b): __wrap_conf_save() executes on save attempt
    __wrap_conf_save();
    g3x_playback_menu_diag_format(buf, sizeof(buf));
    assert(strstr(buf, "SAVE:OFF") != NULL);
    assert(strcmp(buf, "MENU:0000 SAVE:OFF ED:0000") == 0);

    // Reset and test Config (c): conf_save_candidate() executes on save attempt
    g3x_conf_save_status = G3X_CONF_SAVE_NONE;
    conf_save_candidate();
    g3x_playback_menu_diag_format(buf, sizeof(buf));
    assert(strstr(buf, "SAVE:OFF") != NULL);
    assert(strcmp(buf, "MENU:0000 SAVE:OFF ED:0000") == 0);

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "test_save_off.c"
            bin_path = Path(td) / "test_save_off"
            src.write_text(test_c, encoding="utf-8")
            inc = ROOT / "chdk-port/platform/g3x"
            subprocess.run(
                ["gcc", "-O2", "-I", str(inc), str(src), "-o", str(bin_path)],
                check=True,
            )
            res = subprocess.run([str(bin_path)], capture_output=True, text=True, check=True)
            self.assertEqual(res.returncode, 0)


class TestPort53DeliverablesAndNotes(unittest.TestCase):
    def test_notes_txt_content_and_g5x_alignment(self):
        self.assertTrue(NOTES_TXT.is_file(), f"Missing {NOTES_TXT}")
        self.assertTrue(G5X_NOTES_TXT.is_file(), f"Missing {G5X_NOTES_TXT}")

        notes = NOTES_TXT.read_text(encoding="utf-8")
        self.assertIn("PowerShot G3 X", notes)
        self.assertIn("Face+Tracking AF", notes)
        self.assertIn("1-point AF", notes)
        self.assertIn("playback", notes.lower())
        self.assertIn("canon menu", notes.lower())

    def test_trial_plan_doc_content(self):
        self.assertTrue(DOC_TRIAL.is_file(), f"Missing {DOC_TRIAL}")
        trial = DOC_TRIAL.read_text(encoding="utf-8")

        self.assertIn(BASE_PORT53_CANDIDATE_SHA256, trial)
        self.assertTrue(str(BASE_PORT53_CANDIDATE_SIZE) in trial or f"{BASE_PORT53_CANDIDATE_SIZE:,}" in trial)
        self.assertIn(BASE_PORT53_CORE_END, trial)
        self.assertIn("short press", trial.lower())
        self.assertIn("PORT-52", trial)
        self.assertIn("SAVE:OFF", trial)
        self.assertIn("battery", trial.lower())
        self.assertIn("checklist", trial.lower())

        # Recovery and rollback checks
        self.assertNotIn("port52_shortpress_manifest.json", trial)
        self.assertTrue(
            "manifests/port51_restore2_nofullhooks_manifest.json" in trial
            or "manifests/port51_restore2_manifest.json" in trial
        )
        self.assertTrue(
            BASE_PORT51_RESTORE2_NO_FULLHOOKS_SHA256 in trial
            or "4fad35b503be9f0a0ed799cf4cd62721db61e8dc6fa0ba348a507e52937d622a" in trial
        )
        self.assertIn("stops the current session", trial.lower())

        # Check numbered items
        for step in range(1, 11):
            self.assertIn(f"**{step}**", trial, f"Checklist step {step} missing in trial doc")

    def test_evidence_manifest_declares_zero_rom_reads(self):
        self.assertTrue(MANIFEST_EVIDENCE.is_file(), f"Missing {MANIFEST_EVIDENCE}")
        evidence = json.loads(MANIFEST_EVIDENCE.read_text(encoding="utf-8"))
        self.assertFalse(evidence["rom_reads"]["rom_read_needed"])
        self.assertEqual(len(evidence["rom_reads"]["ranges_read"]), 0)
        self.assertIn("finsig", evidence["rom_reads"]["reason"].lower())

    def test_evidence_manifest_reference_files_match_disk(self):
        self.assertTrue(MANIFEST_EVIDENCE.is_file(), f"Missing {MANIFEST_EVIDENCE}")
        evidence = json.loads(MANIFEST_EVIDENCE.read_text(encoding="utf-8"))
        reference_files = evidence.get("reference_files", [])
        self.assertGreater(len(reference_files), 0, "No reference_files in evidence manifest")
        for ref in reference_files:
            rel_path = ref["path"]
            expected_sha256 = ref["sha256"]
            target_path = ROOT / rel_path
            self.assertTrue(target_path.is_file(), f"Reference file missing on disk: {target_path}")
            actual_sha256 = sha256_file(target_path)
            self.assertEqual(
                actual_sha256,
                expected_sha256,
                f"Reference file {rel_path} SHA-256 mismatch: manifest has {expected_sha256}, disk has {actual_sha256}",
            )


if __name__ == "__main__":
    unittest.main()
