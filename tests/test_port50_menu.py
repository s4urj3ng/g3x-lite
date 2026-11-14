"""Offline unit and integration tests for PORT-50 (G3X_GUI_MENU=1)."""

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
PLAT_CAMERA_H = ROOT / "chdk-port/platform/g3x/platform_camera.h"
PLAT_KBD_H = ROOT / "chdk-port/platform/g3x/platform_kbd.h"
PHYSW_BITS = ROOT / "reference/finsig_gm110c/physw_bits.txt"
STUBS_ENTRY = ROOT / "reference/finsig_gm110c/stubs_entry.S"
PORT50_STUBS_ENTRY = ROOT / "chdk-port/platform/g3x/sub/110c/stubs_entry.S"
DOC_ALT_MENU = ROOT / "docs/PORT50_ALT_MENU.md"
DOC_TRIAL = ROOT / "docs/PORT50_TRIAL.md"
MANIFEST_P50 = ROOT / "manifests/port50_gui_menu_manifest.json"
MANIFEST_P49 = ROOT / "manifests/port49_gui_sync_manifest.json"
MANIFEST_P41 = ROOT / "manifests/port41_manifest.json"
OUT = ROOT / "out/port50-test"
TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_CANONICAL_DISKBOOT_SHA256 = "3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72"
BASE_CANONICAL_DISKBOOT_SIZE = 116073
BASE_PORT41_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_PORT41_DEFAULT_SIZE = 124097
BASE_PORT49_DEFAULT_SHA256 = BASE_PORT41_DEFAULT_SHA256
BASE_PORT49_DEFAULT_SIZE = BASE_PORT41_DEFAULT_SIZE
BASE_PORT49_CANDIDATE_SHA256 = "e31e97a1b4e700aaff36e1da80ffff8e335fd162d29be2e6b3400afe8aa5a2a1"
BASE_PORT50_CANDIDATE_SHA256 = "7fa091329c0d3d43e531004bcd135ab4f452e2a574aad4949888445720d6fca8"
BASE_PORT50_CANDIDATE_SIZE = 131321


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


class TestPort50FlagPlumbing(unittest.TestCase):
    def test_flag_plumbing_rejects_missing_prerequisites_and_accepts_full_stack(self):
        required = [
            "G3X_GUI_SYNC",
            "G3X_GUI_DBUF",
            "G3X_GUI_NOOVERDRAW",
            "G3X_KBD_CHECK",
            "G3X_GUI_DIAG",
            "G3X_GUI_SHADOW2",
        ]
        for missing in required:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_GUI_MENU=1"] + [
                    f"-D{f}=1" for f in required if f != missing
                ]
                for hdr in (DIAG_HEADER, SYNC_HEADER):
                    res = subprocess.run(
                        ["cc", "-E", *c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(
                        "G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

                make_args = ["G3X_GUI_MENU=1"] + [
                    f"{f}=1" for f in required if f != missing
                ]
                for mf in (PLAT_MAKEFILE, SUB_MAKEFILE_INC):
                    res = subprocess.run(
                        ["make", "-f", str(mf), *make_args],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(
                        "G3X_GUI_MENU=1 requires G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

        full_c_flags = ["-DG3X_GUI_MENU=1"] + [f"-D{f}=1" for f in required]
        for hdr in (DIAG_HEADER, SYNC_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)


class TestPort50KeymapAndPhysw(unittest.TestCase):
    def test_physw_bits_match_keymap_for_menu_alt_dpad_set_disp(self):
        self.assertTrue(PHYSW_BITS.is_file(), f"Missing {PHYSW_BITS}")
        self.assertTrue(KBD_C.is_file(), f"Missing {KBD_C}")
        self.assertTrue(PLAT_CAMERA_H.is_file(), f"Missing {PLAT_CAMERA_H}")
        self.assertTrue(PLAT_KBD_H.is_file(), f"Missing {PLAT_KBD_H}")

        physw_text = PHYSW_BITS.read_text(encoding="utf-8")
        kbd_text = KBD_C.read_text(encoding="utf-8")
        cam_text = PLAT_CAMERA_H.read_text(encoding="utf-8")
        kbd_h_text = PLAT_KBD_H.read_text(encoding="utf-8")

        # 1. KEY_MENU: w0.b4, mask 0x00000010, event 0x14
        self.assertIn("KEY_MENU", kbd_text)
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_MENU\s*,\s*0x00000010\s*\}')
        self.assertRegex(physw_text, r'0x00000014\s+0\s+0x00000010')

        # 2. D-pad: UP (w0.b5, 0x20, event 0x06), DOWN (w0.b6, 0x40, event 0x07),
        #    RIGHT (w0.b7, 0x80, event 0x09), LEFT (w0.b8, 0x100, event 0x08)
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

        # 5. ALT button options: KEY_WIFI (default), KEY_VIDEO, KEY_DISPLAY, KEY_PLAYBACK
        self.assertIn("#define CAM_ALT_BUTTON_NAMES", cam_text)
        self.assertIn("KEY_WIFI, KEY_VIDEO, KEY_DISPLAY, KEY_PLAYBACK", cam_text)
        self.assertRegex(kbd_text, r'\{\s*0,\s*KEY_WIFI\s*,\s*0x00002000\s*\}')
        self.assertRegex(physw_text, r'0x00000103\s+0\s+0x00002000')

        # 6. Zoom mismatch documented: physw events 0x16 (zoom out) and 0x12 (zoom in)
        #    differ from standard CHDK 0x04/0x03 and are intentionally absent from keymap[]
        self.assertRegex(physw_text, r'0x00000016\s+0\s+0x00000002')
        self.assertRegex(physw_text, r'0x00000012\s+0\s+0x00000004')
        self.assertNotIn("KEY_ZOOM_IN", kbd_text)
        self.assertNotIn("KEY_ZOOM_OUT", kbd_text)

        # 7. KEYS_MASK0: 0x000533F9 covers menu, ALT, d-pad, SET, DISP, video, playback,
        #    and intentionally excludes KEY_POWER (w0.b17, 0x00020000)
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
        self.assertFalse(keys_mask0 & 0x00020000) # KEY_POWER pass-through


class TestPort50FileIoStubs(unittest.TestCase):
    def test_finsig_fatfs_stubs_are_present_and_match_port50_alt_menu_doc(self):
        self.assertTrue(STUBS_ENTRY.is_file(), f"Missing {STUBS_ENTRY}")
        self.assertTrue(PORT50_STUBS_ENTRY.is_file(), f"Missing {PORT50_STUBS_ENTRY}")
        self.assertTrue(DOC_ALT_MENU.is_file(), f"Missing {DOC_ALT_MENU}")

        stubs_text = STUBS_ENTRY.read_text(encoding="utf-8")
        doc_text = DOC_ALT_MENU.read_text(encoding="utf-8")

        expected_stubs = {
            "Open": "0xfc37b3b5",
            "Write": "0xfc37b471",
            "Close": "0xfc37b439",
            "Read": "0xfc418d61",
            "lseek": "0xfc37b595",
            "stat": "0xfc37b5cd",
            "MakeDirectory_Fut": "0xfc37b723",
            "Fopen_Fut": "0xfc37efa7",
            "Fclose_Fut": "0xfc37efcf",
            "Fread_Fut": "0xfc37f041",
            "Fwrite_Fut": "0xfc37f077",
            "Fseek_Fut": "0xfc37f0df",
            "Fgets_Fut": "0xfc37f0ad",
        }

        for stub, addr in expected_stubs.items():
            with self.subTest(stub=stub):
                pattern = rf'NHSTUB\(\s*{stub}\s*,\s*{addr}\s*\)'
                self.assertRegex(stubs_text, pattern)
                self.assertIn(addr[2:].upper(), doc_text.upper())


class TestPort50BuildAndArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.build_p50 = OUT / "build-p50"
        cls.build_default = OUT / "build-default"

        env = os.environ.copy()
        for k in [
            "G3X_GUI_FIX",
            "G3X_GUI_DBUF",
            "G3X_GUI_NOOVERDRAW",
            "G3X_KBD_CHECK",
            "G3X_GUI_DIAG",
            "G3X_GUI_SHADOW2",
            "G3X_GUI_SYNC",
            "G3X_GUI_MENU",
        ]:
            env.pop(k, None)

        # 1. Build PORT-50 candidate
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--gui-menu",
                "--out-dir",
                str(cls.build_p50),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )

        # 2. Build default build (PORT-41 full build)
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "tools/build_port41_full.py"),
                "--clean-stage",
                "--out-dir",
                str(cls.build_default),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_port50_manifest_and_candidate_artifacts_match(self):
        self.assertTrue(MANIFEST_P50.is_file(), f"Missing {MANIFEST_P50}")
        pinned = json.loads(MANIFEST_P50.read_text(encoding="utf-8"))
        generated = json.loads((self.build_p50 / "port50_gui_menu_manifest.json").read_text(encoding="utf-8"))
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
        ]
        self.assertEqual(pinned["build"]["flags"], expected_flags)
        self.assertEqual(pinned["core_end"], pinned["artifacts"]["core_end"])
        self.assertRegex(pinned["core_end"], r"^0x003[0-9a-f]{5}$")
        self.assertEqual(pinned["card_writes"], "enabled")
        self.assertIn("G3X_GUI_MENU=1 overrides G3X_DISABLE_CARD_WRITES=1", pinned["card_writes_note"])
        expected_removed_wrappers = [
            "write",
            "fwrite",
            "open",
            "fopen",
            "creat",
            "mkdir",
            "MakeDirectory_Fut",
            "remove",
            "DeleteFile_Fut",
            "DeleteDirectory_Fut",
            "rename",
            "RenameFile_Fut",
        ]
        self.assertEqual(pinned["removed_wrappers"], expected_removed_wrappers)

        snap = distribution_snapshot(self.build_p50)
        expected = dict(pinned["artifacts"]["chdk_files"])
        expected["DISKBOOT.BIN"] = {
            k: pinned["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")
        }
        self.assertEqual(snap, expected)
        self.assertEqual(pinned["artifacts"]["chdk_files_count"], len(snap) - 1)
        self.assertEqual(pinned["artifacts"]["DISKBOOT.BIN"]["sha256"], BASE_PORT50_CANDIDATE_SHA256)
        self.assertEqual(pinned["artifacts"]["DISKBOOT.BIN"]["size"], BASE_PORT50_CANDIDATE_SIZE)

    def test_port50_elf_symbols_and_unwrapped_file_io(self):
        main_elf = self.build_p50 / "stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(main_elf.is_file(), f"Missing {main_elf}")

        # Check symbols using nm
        nm_out = subprocess.check_output([str(NM), str(main_elf)], text=True)

        # 1. No __wrap_ symbols anywhere in the binary
        wrap_symbols = [line for line in nm_out.splitlines() if "__wrap_" in line]
        self.assertEqual(wrap_symbols, [], f"Unexpected __wrap_ symbols in PORT-50 ELF: {wrap_symbols}")

        # 2. conf_save is present as real text function
        self.assertRegex(nm_out, r"[0-9a-f]{8}\s+T\s+conf_save")

        # 3. Diagnostic hooks exist
        self.assertRegex(nm_out, r"[0-9a-f]{8}\s+T\s+g3x_menu_record_open")
        self.assertRegex(nm_out, r"[0-9a-f]{8}\s+T\s+g3x_conf_record_save_result")
        self.assertRegex(nm_out, r"[0-9a-f]{8}\s+B\s+g3x_menu_open_count")
        self.assertRegex(nm_out, r"[0-9a-f]{8}\s+B\s+g3x_conf_save_status")

        # Check disassembly using objdump
        dump_out = subprocess.check_output([str(OBJDUMP), "-d", str(main_elf)], text=True)

        # 4. config_save calls write, close, and g3x_conf_record_save_result
        self.assertRegex(dump_out, r"<config_save>:[\s\S]*?bl\s+[0-9a-f]+\s+<write>")
        self.assertRegex(dump_out, r"<config_save>:[\s\S]*?bl\s+[0-9a-f]+\s+<close>")
        self.assertRegex(dump_out, r"<config_save>:[\s\S]*?bl\s+[0-9a-f]+\s+<g3x_conf_record_save_result>")

        # 5. write calls _Write stub (0xFC37B471)
        self.assertRegex(dump_out, r"<write>:[\s\S]*?bl\s+[0-9a-f]+\s+<_Write>")
        self.assertRegex(dump_out, r"<_Write>:[\s\S]*?\.word\s+0xfc37b471")

        # 6. open calls _Open stub (0xFC37B3B5)
        self.assertRegex(dump_out, r"<open>:[\s\S]*?bl\s+[0-9a-f]+\s+<_Open>")
        self.assertRegex(dump_out, r"<_Open>:[\s\S]*?\.word\s+0xfc37b3b5")

        # 7. close calls _Close stub (0xFC37B439)
        self.assertRegex(dump_out, r"<close>:[\s\S]*?bl\s+[0-9a-f]+\s+<_Close>")
        self.assertRegex(dump_out, r"<_Close>:[\s\S]*?\.word\s+0xfc37b439")

    def test_default_build_is_byte_identical_to_port49_default(self):
        canonical_diskboot = ROOT / "chdk-port/bin/DISKBOOT.BIN"
        self.assertEqual(canonical_diskboot.stat().st_size, BASE_CANONICAL_DISKBOOT_SIZE)
        self.assertEqual(sha256_file(canonical_diskboot), BASE_CANONICAL_DISKBOOT_SHA256)

        default_diskboot = self.build_default / "DISKBOOT.BIN"
        self.assertEqual(default_diskboot.stat().st_size, BASE_PORT49_DEFAULT_SIZE)
        self.assertEqual(sha256_file(default_diskboot), BASE_PORT49_DEFAULT_SHA256)

        # The PORT-49 default build output is byte-identical to PORT-41 default
        port41_pinned = json.loads(MANIFEST_P41.read_text(encoding="utf-8"))
        default_snap = distribution_snapshot(self.build_default)
        expected_p49_default = dict(port41_pinned["artifacts"]["chdk_files"])
        expected_p49_default["DISKBOOT.BIN"] = {
            k: port41_pinned["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")
        }
        self.assertEqual(default_snap, expected_p49_default)

    def test_default_build_is_byte_identical_to_port41_default(self):
        self.test_default_build_is_byte_identical_to_port49_default()

    def test_trial_plan_document_structure(self):
        self.assertTrue(DOC_TRIAL.is_file(), f"Missing {DOC_TRIAL}")
        text = DOC_TRIAL.read_text(encoding="utf-8")

        # Required sections per prompt
        self.assertIn("## 1. Assumptions Table", text)
        self.assertIn("Trial (A): PORT-49 Baseline", text)
        self.assertIn("Trial (B): PORT-50 Menu", text)
        self.assertIn("Battery-pull recovery", text)
        self.assertIn("Rollback to PORT-49", text)
        self.assertIn("7fa091329c0d3d43e531004bcd135ab4f452e2a574aad4949888445720d6fca8", text)

        # Feedback Item 1: Card writes row or section, writes ARE enabled, wrappers listed, files named, card recommendation
        self.assertIn("Card Writes", text)
        self.assertIn("are enabled", text.lower())
        for w in [
            "write", "fwrite", "open", "fopen", "creat", "mkdir",
            "MakeDirectory_Fut", "remove", "DeleteFile_Fut",
            "DeleteDirectory_Fut", "rename", "RenameFile_Fut",
        ]:
            self.assertIn(f"`{w}`", text)
        self.assertIn("A/CHDK/", text)
        self.assertIn("spare", text.lower())

        # Feedback Item 2: Trial (B) fallback
        self.assertIn("Fallback", text)
        self.assertIn("explicit save option", text)

        # Feedback Item 4: Optional hints
        self.assertIn("scripts/build_port43_dbuf.py --gui-menu", text)
        self.assertIn("does not use zoom", text.lower())
        self.assertIn("height - 3 * FONT_HEIGHT", text)


if __name__ == "__main__":
    unittest.main()
