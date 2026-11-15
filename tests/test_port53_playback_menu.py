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

BASE_PORT53_CANDIDATE_SHA256 = "b054f24264084bd51fd50d90dfa9af9e54c9bef1e8afb318aa1bc6a6f2185fe6"
BASE_PORT53_CANDIDATE_SIZE = 132145
BASE_PORT53_CORE_END = "0x0036aa00"


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
        for path in (KBD_C, LIB_C, MAIN_C, GUI_MENU_C, DIAG_HEADER):
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
        self.assertTrue(keys_mask0 & 0x00000010)  # KEY_MENU
        self.assertTrue(keys_mask0 & 0x00000020)  # KEY_UP
        self.assertTrue(keys_mask0 & 0x00000040)  # KEY_DOWN
        self.assertTrue(keys_mask0 & 0x00000080)  # KEY_RIGHT
        self.assertTrue(keys_mask0 & 0x00000100)  # KEY_LEFT
        self.assertTrue(keys_mask0 & 0x00000200)  # KEY_SET
        self.assertTrue(keys_mask0 & 0x00001000)  # KEY_DISPLAY
        self.assertTrue(keys_mask0 & 0x00002000)  # KEY_WIFI
        self.assertTrue(keys_mask0 & 0x00010000)  # KEY_PLAYBACK
        self.assertFalse(keys_mask0 & 0x00020000) # KEY_POWER pass-through

    def test_playback_menu_active_predicate(self):
        kbd_text = KBD_C.read_text(encoding="utf-8")
        lib_text = LIB_C.read_text(encoding="utf-8")
        main_text = MAIN_C.read_text(encoding="utf-8")

        self.assertIn("int g3x_playback_menu_is_active(void)", kbd_text)
        self.assertIn("camera_info.state.mode_play && !camera_info.state.gui_mode_none", kbd_text)
        self.assertIn("int g3x_playback_menu_gui_mode_active(void)", lib_text)
        self.assertIn("camera_info.state.mode_play && (camera_info.state.gui_mode_alt || !camera_info.state.gui_mode_none)", lib_text)
        self.assertIn("int g3x_playback_menu_mode_check(void)", main_text)


class TestPort53BuildAndArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_c = ROOT / "out/port53-playback-menu"
        cls.build_b = ROOT / "out/build-playback-alone"
        cls.build_a = ROOT / "out/build-default"

        # Ensure all three builds are present
        if not (cls.build_c / "DISKBOOT.BIN").is_file():
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

        if not (cls.build_b / "DISKBOOT.BIN").is_file():
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

        if not (cls.build_a / "DISKBOOT.BIN").is_file():
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "tools/build_port41_full.py"),
                    "--clean-stage",
                    "--out-dir",
                    str(cls.build_a),
                ],
                cwd=ROOT,
                check=True,
            )

    def test_default_build_is_byte_identical_to_port52_default(self):
        default_diskboot = self.build_a / "DISKBOOT.BIN"
        self.assertTrue(default_diskboot.is_file(), f"Missing {default_diskboot}")
        self.assertEqual(default_diskboot.stat().st_size, BASE_PORT52_DEFAULT_SIZE)
        self.assertEqual(sha256_file(default_diskboot), BASE_PORT52_DEFAULT_SHA256)

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
        ]

        # 1. Gating check: default build must NOT have any of the playback menu symbols
        for sym in playback_symbols:
            self.assertNotIn(sym, default_nm, f"Symbol {sym} leaked into default build!")

        # 2. Candidate build (config c) MUST have the playback menu symbols
        for sym in playback_symbols:
            self.assertIn(sym, candidate_nm, f"Symbol {sym} missing from config (c) candidate build!")

        # 3. Alone build (config b) MUST have the playback menu functions
        for sym in [
            "g3x_playback_menu_is_active",
            "g3x_playback_menu_kbd_process",
            "g3x_playback_menu_gui_mode_active",
            "g3x_playback_menu_mode_check",
            "g3x_playback_menu_record_item_edit",
        ]:
            self.assertIn(sym, alone_nm, f"Symbol {sym} missing from config (b) alone build!")

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

        # conf_save() must call g3x_conf_record_save_result and must NOT call write stubs
        conf_save_body = get_func_body("conf_save")
        self.assertIn("<g3x_conf_record_save_result>", conf_save_body)
        for call in forbidden_write_calls:
            self.assertNotIn(call, conf_save_body)

        # config_save() must call g3x_conf_record_save_result and must NOT call write stubs
        config_save_body = get_func_body("config_save")
        self.assertIn("<g3x_conf_record_save_result>", config_save_body)
        for call in forbidden_write_calls:
            self.assertNotIn(call, config_save_body)

        # save_params_values() must not call write stubs
        save_params_body = get_func_body("save_params_values")
        for call in forbidden_write_calls:
            self.assertNotIn(call, save_params_body)

        # save_int_value_file() must not call write stubs
        save_int_body = get_func_body("save_int_value_file")
        for call in forbidden_write_calls:
            self.assertNotIn(call, save_int_body)

    def test_diag_format_displays_save_off(self):
        diag_text = DIAG_HEADER.read_text(encoding="utf-8")
        self.assertIn("G3X_CONF_SAVE_OFF", diag_text)
        self.assertIn('"OFF"', diag_text)
        self.assertIn('"MENU:%04u SAVE:%s ED:%04u"', diag_text)


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

        # Check numbered items
        for step in range(1, 11):
            self.assertIn(f"**{step}**", trial, f"Checklist step {step} missing in trial doc")

    def test_evidence_manifest_declares_zero_rom_reads(self):
        self.assertTrue(MANIFEST_EVIDENCE.is_file(), f"Missing {MANIFEST_EVIDENCE}")
        evidence = json.loads(MANIFEST_EVIDENCE.read_text(encoding="utf-8"))
        self.assertFalse(evidence["rom_reads"]["rom_read_needed"])
        self.assertEqual(len(evidence["rom_reads"]["ranges_read"]), 0)
        self.assertIn("finsig", evidence["rom_reads"]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
