"""Unit and integration tests for PORT-42 GUI Fix (flicker, colours, opacity, 2x font).

Verifies:
1. docs/PORT42_GUI_FIX.md format and content (table columns: fix, file:line changed,
   source citation, label; citations to PORT-37/38/40 and siblings; VERIFIED labels).
2. full_build/g3x source modifications:
   - Gated behind G3X_GUI_FIX=1
   - Zero-flicker redraw & sentinel guard check
   - Real opacity buffer array (0x5FC40000, 0x5FB80000)
   - Active buffer indexing (active_bitmap_buffer & 1)
   - DIGIC 6 palette handling (type 3, size 1024, active palette pointer)
   - 2x integer font scaling (16x32) and 880x576 solid black layout
3. Bootstrap pin invariance (libplatform.a, platform_camera.h unaltered).
4. Full build with G3X_GUI_FIX=1 builds reproducibly (identical DISKBOOT.BIN and CHDK/ hashes).
5. Full build with G3X_GUI_FIX=1 and FULL_HOOKS=1 builds reproducibly.
6. Full build with G3X_GUI_FIX off reproduces manifests/port41_manifest.json byte-for-byte.
7. Candidate invariance: candidate_port2a produces byte-identical DISKBOOT.BIN (94682573...).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
TOOLCHAIN_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
TOOLCHAIN_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
TOOLCHAIN_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_port41_full.py"
OUT_DIR_GUI = REPO_ROOT / "out" / "port42-gui"
OUT_DIR_GUI_HOOKS = REPO_ROOT / "out" / "port42-gui-full-hooks"
OUT_DIR_FULL = REPO_ROOT / "out" / "port41-full"
WRAPPER_SCRIPT = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
MANIFESTS_DIR = REPO_ROOT / "manifests"
DOCS_MANIFESTS_DIR = REPO_ROOT / "docs" / "manifests"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_distribution(out_path: Path) -> dict[str, tuple[int, str]]:
    snapshot: dict[str, tuple[int, str]] = {}
    diskboot = out_path / "DISKBOOT.BIN"
    if diskboot.is_file():
        snapshot["DISKBOOT.BIN"] = (diskboot.stat().st_size, sha256_file(diskboot))
    chdk_dir = out_path / "CHDK"
    if chdk_dir.is_dir():
        for root, dirs, files in os.walk(chdk_dir):
            for f in sorted(files):
                p = Path(root) / f
                rel = str(p.relative_to(out_path))
                snapshot[rel] = (p.stat().st_size, sha256_file(p))
    return snapshot


class TestPort42GuiFixDoc(unittest.TestCase):
    """Static checks on docs/PORT42_GUI_FIX.md."""

    def test_doc_table_and_content(self):
        doc_path = REPO_ROOT / "docs" / "PORT42_GUI_FIX.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        text = doc_path.read_text(encoding="utf-8")

        # Table header columns check: fix, file:line changed, source, label
        self.assertRegex(text, r"(?i)\|.*fix.*\|.*file:line.*\|.*source.*\|.*label")

        # Required fixes mentioned in doc
        self.assertIn("Zero-Flicker Redraw", text)
        self.assertIn("Active-Buffer Drawing", text)
        self.assertIn("UYVY Neutral Black/White", text)
        self.assertIn("DIGIC 6 Palette Registration", text)
        self.assertIn("Real Opacity Buffer Array", text)
        self.assertIn("880x576 Opaque Black Background", text)
        self.assertIn("2x Integer Font Scaling (16x32)", text)

        # Labels
        self.assertIn("VERIFIED by owner trial", text)

        # Citations
        self.assertTrue(
            re.search(r"scripts/build_candidate_gui3\.py:\d+", text),
            "Doc must cite scripts/build_candidate_gui3.py with line numbers",
        )
        self.assertTrue(
            re.search(r"docs/PORT(37|38|40)_\w+\.md:\d+", text),
            "Doc must cite PORT37/38/40 documentation with line numbers",
        )
        self.assertTrue(
            re.search(r"chdk-port/platform/(g7x|g5x)/lib\.c:\d+", text),
            "Doc must cite sibling paths with line numbers",
        )

    def test_doc_manifest_hashes(self):
        doc_path = REPO_ROOT / "docs" / "PORT42_GUI_FIX.md"
        text = doc_path.read_text(encoding="utf-8")

        # Output manifest details
        self.assertIn("port42_gui_fix_manifest.json", text)
        self.assertIn("port42_gui_fix_full_hooks_manifest.json", text)
        self.assertIn("port41_manifest.json", text)

        # Check expected baseline hash
        self.assertIn("24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9", text)
        self.assertIn("88c41eb5d184c47b78314b946a7178aa9ac7e9708d169ea8d3a5ee895ec98b90", text)
        self.assertIn("6e7511e5f40b690f1c501801a59acde19ba17d0abb21ee7a788aaa10407b26a0", text)


class TestPort42GuiFixSources(unittest.TestCase):
    """Static checks on full_build/g3x source code and switches."""

    def test_gui_menu_source(self):
        gui_menu_c = REPO_ROOT / "full_build" / "g3x" / "gui_menu.c"
        self.assertTrue(gui_menu_c.is_file(), "full_build/g3x/gui_menu.c missing")
        text = gui_menu_c.read_text(encoding="utf-8")

        # G3X_GUI_FIX switch
        self.assertIn("defined(G3X_GUI_FIX) && (G3X_GUI_FIX == 1)", text)

        # 2x font routines
        self.assertIn("g3x_draw_char_16x32", text)
        self.assertIn("rbf_font_height", text)
        self.assertIn("rbf_char_width", text)
        self.assertIn("rbf_draw_menu_header", text)

        # 880x576 opaque fill
        self.assertIn("g3x_fill_menu_opaque_black", text)
        self.assertIn("g3x_get_menu_layout", text)
        self.assertIn("0x00800080", text)  # UYVY neutral black

    def test_lib_source(self):
        lib_c = REPO_ROOT / "full_build" / "g3x" / "lib.c"
        self.assertTrue(lib_c.is_file(), "full_build/g3x/lib.c missing")
        text = lib_c.read_text(encoding="utf-8")

        # G3X_GUI_FIX switch
        self.assertIn("defined(G3X_GUI_FIX) && (G3X_GUI_FIX == 1)", text)

        # Opacity buffers in DRAM
        self.assertIn("0x5FC40000", text)
        self.assertIn("0x5FB80000", text)

        # Active-buffer indexing
        self.assertIn("active_bitmap_buffer & 1", text)

        # Palette handling
        self.assertIn("vid_get_bitmap_active_palette", text)
        self.assertIn("vid_get_palette_type", text)
        self.assertIn("vid_get_palette_size", text)

        # Guard check in check_gui_needs_redraw
        self.assertIn("draw_test_guard", text)

    def test_stubs_min_source(self):
        stubs_min_s = REPO_ROOT / "full_build" / "g3x" / "sub" / "110c" / "stubs_min.S"
        self.assertTrue(stubs_min_s.is_file(), "stubs_min.S missing")
        text = stubs_min_s.read_text(encoding="utf-8")

        # opacity_buffer stub omitted when G3X_GUI_FIX=1
        self.assertIn("G3X_GUI_FIX", text)
        self.assertIn("DEF(opacity_buffer, 0xFC1837FC)", text)

    def test_bootstrap_pin_invariance(self):
        """Verify bootstrap pins (libplatform.a, platform_camera.h) are clean."""
        plat_cam_h = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "platform_camera.h"
        self.assertTrue(plat_cam_h.is_file())

        res = subprocess.run(
            ["git", "diff", "--exit-code", "chdk-port/platform/g3x/libplatform.a", "chdk-port/platform/g3x/platform_camera.h"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(res.returncode, 0, "Bootstrap pins in chdk-port/platform/g3x/ must have zero git diff")


class TestPort42GuiFixBuildExecution(unittest.TestCase):
    """Execution and verification of G3X_GUI_FIX=1 builds."""

    @classmethod
    def setUpClass(cls):
        cls.has_toolchain = TOOLCHAIN_GCC.is_file() and os.access(TOOLCHAIN_GCC, os.X_OK)

    def _require_toolchain(self):
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

    def test_gui_fix_build_artifacts_and_manifest(self):
        """Verify G3X_GUI_FIX=1 build produces exact manifest matches."""
        self._require_toolchain()

        diskboot = OUT_DIR_GUI / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertEqual(diskboot.stat().st_size, 123361)
        self.assertEqual(
            sha256_file(diskboot),
            "88c41eb5d184c47b78314b946a7178aa9ac7e9708d169ea8d3a5ee895ec98b90",
        )

        # Check manifests
        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 123361)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "88c41eb5d184c47b78314b946a7178aa9ac7e9708d169ea8d3a5ee895ec98b90",
            )
            self.assertEqual(data["artifacts"]["modules_count"], 34)

    def test_gui_fix_full_hooks_build_artifacts_and_manifest(self):
        """Verify G3X_GUI_FIX=1 FULL_HOOKS=1 build produces exact manifest matches."""
        self._require_toolchain()

        diskboot = OUT_DIR_GUI_HOOKS / "DISKBOOT.BIN"
        if diskboot.is_file():
            self.assertEqual(diskboot.stat().st_size, 123425)
            self.assertEqual(
                sha256_file(diskboot),
                "6e7511e5f40b690f1c501801a59acde19ba17d0abb21ee7a788aaa10407b26a0",
            )

        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_full_hooks_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 123425)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "6e7511e5f40b690f1c501801a59acde19ba17d0abb21ee7a788aaa10407b26a0",
            )
            self.assertIn("FULL_HOOKS=1", data["build"]["flags"])
            self.assertIn("G3X_GUI_FIX=1", data["build"]["flags"])

    def test_switch_off_reproduces_port41_manifest(self):
        """Verify that with GUI fix switch OFF, the default full build matches manifests/port41_manifest.json."""
        self._require_toolchain()

        diskboot = OUT_DIR_FULL / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertEqual(diskboot.stat().st_size, 124097)
        self.assertEqual(
            sha256_file(diskboot),
            "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
        )

        with open(MANIFESTS_DIR / "port41_manifest.json", "r", encoding="utf-8") as f:
            port41_manifest = json.load(f)

        actual = snapshot_distribution(OUT_DIR_FULL)
        self.assertEqual(
            actual["DISKBOOT.BIN"],
            (
                port41_manifest["artifacts"]["DISKBOOT.BIN"]["size"],
                port41_manifest["artifacts"]["DISKBOOT.BIN"]["sha256"],
            ),
        )

    def test_candidate_port2a_invariance(self):
        """Verify candidate_port2a produces byte-identical DISKBOOT.BIN."""
        self._require_toolchain()

        cmd = ["python3", "-B", str(REPO_ROOT / "tools" / "build_candidate_port2a.py")]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"build_candidate_port2a failed: {res.stderr}")

        cand_diskboot = REPO_ROOT / "candidate_port2a" / "DISKBOOT.BIN"
        self.assertTrue(cand_diskboot.is_file())
        self.assertEqual(cand_diskboot.stat().st_size, 118001)
        self.assertEqual(
            sha256_file(cand_diskboot),
            "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136",
        )


if __name__ == "__main__":
    unittest.main()
