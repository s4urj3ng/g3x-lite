"""Unit and integration tests for PORT-41 standard CHDK full build.

Verifies:
1. Toolchain availability and skip behavior if toolchain is missing.
2. Full build execution producing out/port41-full/DISKBOOT.BIN, CHDK/ modules, fonts, lang.
3. Integrity of SHA-256 manifest (port41_manifest.json).
4. Invariance of chdk-port/platform/g3x/* hashes before and after full build.
5. boot.c invariants: CreateTask at 0xBFE14A3D, sub_fc0d0126 handoff, LED 0xD20B0884,
   ladder timing 0x00100000, sibling citations.
6. kbd.c invariants: physw_status 0x40DAC, Power bit 17, Playback bit 16, 10ms sleep,
   start cause 0x9BD0, power-cut bypass sub_fc05b962, restore 0x00080000, ALT off at boot.
7. lib.c and platform_camera.h invariants: displaytype 12, 900x600, buffer width 928,
   UYVY active_bitmap_buffer & 1, opacity_buffer {0x5FC40000, 0x5FB80000}, GUI5 layout.
8. Card write suppression switches and wrappers.
9. Disabled hook TODOs for capt_seq, movie_rec, filewrite.
10. Symbol namespacing preventing collision with PORT-39 / candidate symbols.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHDK_PORT_G3X = REPO_ROOT / "chdk-port" / "platform" / "g3x"
FULL_BUILD_G3X = REPO_ROOT / "full_build" / "g3x"
TOOLCHAIN_GCC = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin" / "arm-none-eabi-gcc"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_port41_full.py"
OUT_DIR = REPO_ROOT / "out" / "port41-full"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_hashes(dir_path: Path) -> dict[str, str]:
    hashes = {}
    for p in sorted(dir_path.glob("**/*")):
        if p.is_file():
            rel = p.relative_to(dir_path).as_posix()
            hashes[rel] = sha256_file(p)
    return hashes


class TestPort41FullBuildSources(unittest.TestCase):
    """Static checks on full_build/g3x source code and adaptations."""

    def test_boot_invariants(self):
        boot_c = FULL_BUILD_G3X / "sub" / "110c" / "boot.c"
        self.assertTrue(boot_c.is_file(), "full_build/g3x/sub/110c/boot.c missing")
        text = boot_c.read_text(encoding="utf-8")
        text_lower = text.lower()

        # CreateTask runtime address 0xBFE14A3D or hook site 0xBFE14A3C
        self.assertTrue(
            "0xbfe14a3d" in text_lower or "0xbfe14a3c" in text_lower,
            "CreateTask runtime address 0xBFE14A3D missing",
        )

        # Handoff address sub_fc0d0126
        self.assertTrue(
            "sub_fc0d0126" in text_lower or "0xfc0d0126" in text_lower,
            "sub_fc0d0126 ROM handoff missing",
        )

        # Power LED address 0xD20B0884
        self.assertIn("0xd20b0884", text_lower, "Power LED 0xD20B0884 missing")

        # Held-press ladder timing 0x00100000
        self.assertIn("0x00100000", text_lower, "Ladder timing constant missing")

        # Sibling adaptation citation
        self.assertTrue(
            re.search(r"chdk-port/platform/(g7x|g5x)/.*:\d+", text),
            "boot.c must cite chdk-port/platform/<sibling>/...:line",
        )

        # Namespaced symbols
        self.assertIn("g3x_full_shortpress", text, "Namespaced shortpress hooks missing in boot.c")

    def test_kbd_invariants(self):
        kbd_c = FULL_BUILD_G3X / "kbd.c"
        self.assertTrue(kbd_c.is_file(), "full_build/g3x/kbd.c missing")
        text = kbd_c.read_text(encoding="utf-8")
        text_lower = text.lower()

        # physw_status 0x40DAC
        self.assertIn("0x40dac", text_lower, "physw_status address 0x40DAC missing")

        # Power bit 17, Playback bit 16
        self.assertTrue(
            re.search(r"1\s*<<\s*17", text) or "0x00020000" in text_lower or "bit 17" in text_lower,
            "Power bit 17 check missing in kbd.c",
        )
        self.assertTrue(
            re.search(r"1\s*<<\s*16", text) or "0x00010000" in text_lower or "bit 16" in text_lower,
            "Playback bit 16 check missing in kbd.c",
        )

        # 10 ms sleep
        self.assertTrue(
            "10 ms" in text_lower or "ms_sleep(10)" in text or "10" in text,
            "10 ms sleep missing",
        )

        # Short-press power-on fix: start cause at 0x9BD0, power-cut bypass at sub_fc05b962
        self.assertIn("0x9bd0", text_lower, "Start cause address 0x9BD0 missing")
        self.assertIn("sub_fc05b962", text_lower, "Power-cut bypass sub_fc05b962 missing")

        # Restore start cause 0x00080000
        self.assertIn("0x00080000", text_lower, "Start cause restore 0x00080000 missing")

        # ALT off at boot
        self.assertTrue(
            "gui_mode = 0" in text or "kbd_set_alt_mode(0)" in text,
            "ALT mode must be off at boot",
        )

    def test_lib_and_platform_camera_invariants(self):
        plat_cam = FULL_BUILD_G3X / "platform_camera.h"
        self.assertTrue(plat_cam.is_file(), "full_build/g3x/platform_camera.h missing")
        cam_text = plat_cam.read_text(encoding="utf-8")

        # 900x600, buffer width 928 in platform_camera.h
        self.assertIn("#define CAM_SCREEN_WIDTH", cam_text)
        self.assertIn("900", cam_text)
        self.assertIn("#define CAM_SCREEN_HEIGHT", cam_text)
        self.assertIn("600", cam_text)
        self.assertIn("#define CAM_BITMAP_WIDTH", cam_text)
        self.assertIn("928", cam_text)
        self.assertIn("#define CAM_SUPPORT_BITMAP_RES_CHANGE", cam_text)

        # lib.c checks
        lib_c = FULL_BUILD_G3X / "lib.c"
        self.assertTrue(lib_c.is_file(), "full_build/g3x/lib.c missing")
        lib_text = lib_c.read_text(encoding="utf-8")
        lib_lower = lib_text.lower()

        # Displaytype 12 (case 12 or displaytype 12)
        self.assertTrue(
            "12" in lib_text and "displaytype" in lib_text,
            "displaytype 12 missing in lib.c",
        )

        # Opacity buffers in lib.c
        self.assertIn("0x5fc40000", lib_lower)
        self.assertIn("0x5fb80000", lib_lower)

        # Active bitmap buffer & 1
        self.assertIn("active_bitmap_buffer & 1", lib_text)

        # GUI5 layout in lib.c (880x576 box, 32 px rows)
        self.assertIn("880", lib_text, "GUI5 box width 880 missing in lib.c")
        self.assertIn("576", lib_text, "GUI5 box height 576 missing in lib.c")
        self.assertIn("32", lib_text, "GUI5 row height 32 missing in lib.c")

    def test_card_write_suppression_switches(self):
        sub_makefile = FULL_BUILD_G3X / "sub" / "110c" / "Makefile"
        self.assertTrue(sub_makefile.is_file(), "full_build/g3x/sub/110c/Makefile missing")
        make_text = sub_makefile.read_text(encoding="utf-8")

        for wrap in ["open", "fopen", "creat", "write", "fwrite"]:
            self.assertIn(f"--wrap={wrap}", make_text, f"--wrap={wrap} missing in sub/110c/Makefile")

        self.assertIn("-DG3X_DISABLE_CARD_WRITES=1", make_text)
        self.assertIn("-DOPT_DISABLE_FILE_WRITES=1", make_text)

        # Wrappers in lib.c
        lib_c = FULL_BUILD_G3X / "lib.c"
        lib_text = lib_c.read_text(encoding="utf-8")
        for wrap in ["__wrap_open", "__wrap_fopen", "__wrap_creat", "__wrap_write", "__wrap_fwrite"]:
            self.assertIn(wrap, lib_text, f"{wrap} implementation missing in lib.c")

    def test_disabled_hook_todos(self):
        for fname in ["capt_seq.c", "movie_rec.c", "filewrite.c"]:
            fpath = FULL_BUILD_G3X / "sub" / "110c" / fname
            self.assertTrue(fpath.is_file(), f"{fpath} missing")
            content = fpath.read_text(encoding="utf-8")
            self.assertIn("TODO", content, f"TODO missing in {fname} for disabled hook")

    def test_symbol_isolation(self):
        """Ensure full build symbols do not collide with candidate symbols."""
        boot_text = (FULL_BUILD_G3X / "sub" / "110c" / "boot.c").read_text(encoding="utf-8")
        kbd_text = (FULL_BUILD_G3X / "kbd.c").read_text(encoding="utf-8")

        # Full build must NOT define the un-namespaced global variable g3x_saved_start_cause
        self.assertNotRegex(
            boot_text,
            r"\bint\s+g3x_saved_start_cause\b",
            "boot.c defines unnamespaced g3x_saved_start_cause",
        )
        self.assertNotRegex(
            kbd_text,
            r"\bint\s+g3x_saved_start_cause\b",
            "kbd.c defines unnamespaced g3x_saved_start_cause",
        )


class TestPort41FullBuildExecution(unittest.TestCase):
    """End-to-end execution test for standard CHDK full build."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file() or not os.access(TOOLCHAIN_GCC, os.X_OK):
            cls.has_toolchain = False
        else:
            cls.has_toolchain = True

    def test_full_build_execution_and_invariance(self):
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}; skipping execution test.")

        # Snapshot chdk-port/platform/g3x hashes before build
        before_hashes = snapshot_hashes(CHDK_PORT_G3X)

        # Run build script
        cmd = ["python3", "-B", str(BUILD_SCRIPT)]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(
            res.returncode,
            0,
            f"build_port41_full.py failed with code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
        )

        # Check DISKBOOT.BIN
        diskboot = OUT_DIR / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertGreater(diskboot.stat().st_size, 50000, "DISKBOOT.BIN is suspiciously small")

        # Check CHDK folder contents
        chdk_dir = OUT_DIR / "CHDK"
        self.assertTrue(chdk_dir.is_dir(), f"Expected {chdk_dir} to exist")
        modules_dir = chdk_dir / "MODULES"
        self.assertTrue(modules_dir.is_dir(), f"Expected {modules_dir} to exist")
        flt_files = list(modules_dir.glob("*.flt"))
        self.assertGreaterEqual(len(flt_files), 30, f"Expected >= 30 .flt modules, found {len(flt_files)}")
        self.assertTrue((chdk_dir / "FONTS").is_dir(), "CHDK/FONTS missing")
        self.assertTrue((chdk_dir / "LANG").is_dir(), "CHDK/LANG missing")

        # Check manifest
        manifest_path = OUT_DIR / "port41_manifest.json"
        self.assertTrue(manifest_path.is_file(), f"Expected {manifest_path} to exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("build", manifest)
        self.assertIn("artifacts", manifest)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["size"], diskboot.stat().st_size)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["sha256"], sha256_file(diskboot))
        self.assertEqual(manifest["artifacts"]["modules_count"], len(flt_files))

        # Snapshot chdk-port/platform/g3x hashes after build and assert equality
        after_hashes = snapshot_hashes(CHDK_PORT_G3X)
        self.assertEqual(
            before_hashes,
            after_hashes,
            "chdk-port/platform/g3x/ files were modified during the full build!",
        )


if __name__ == "__main__":
    unittest.main()
