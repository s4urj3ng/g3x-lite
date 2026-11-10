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
import tempfile
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
        self.assertIn("Timed GUI State Change Detection", text)

        # Labels
        self.assertIn("VERIFIED by owner trial", text)
        self.assertIn("INFERRED (owner trial to confirm)", text)

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
        self.assertTrue(
            re.search(r"chdk-port/core/gui\.c:\d+", text),
            "Doc must cite chdk-port/core/gui.c with line numbers",
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
        self.assertIn("06f8e1b6da3b9f77525cfc96ab5a25b82dca1a94da25989735826a569d04838b", text)
        self.assertIn("d0e4648719fc37f38f49f1ad202592c87f0604bed9417e60be430c1b6a4f9e38", text)


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

        # Menu navigation getter
        self.assertIn("gui_menu_get_curr_item", text)

    def test_timed_gui_state_changes_and_no_periodic_redraw(self):
        """Verify:
        (a) Helper-expiry transition and splash countdown each lead to a redraw request;
        (b) No periodic forced-redraw pattern exists in the G3X_GUI_FIX build.
        """
        # 1. Static source audit on tools/build_port41_full.py patching logic
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("gui_check_state_changed", build_text)
        self.assertIn("struct gui_vis_sig", build_text)
        self.assertIn("helper_due", build_text)
        self.assertIn("gui_helper_displayat", build_text)
        self.assertIn("splash_sec", build_text)
        self.assertIn("gui_splash_expire", build_text)
        self.assertIn("gui_menu_get_curr_item", build_text)

        # Main loop replacement must NOT contain periodic counter patterns ((cnt++) & N)
        self.assertNotIn("cnt++", build_text[build_text.find("main_replacement"):build_text.find("core_conf_c")])
        self.assertNotIn("& 3", build_text[build_text.find("main_replacement"):build_text.find("core_conf_c")])

        # 2. Host simulation of gui_check_state_changed using host gcc
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }
static int mock_half_shoot = 0;
int kbd_is_key_pressed(int k) { return mock_half_shoot; }
#define KEY_SHOOT_HALF 1
#define SPLASH_TIME 40

static int gui_osd_need_restore = 0;
static int gui_mode_need_redraw = 0;
static int mock_menu_dirty = 0;
int gui_menu_needs_redraw(void) { return mock_menu_dirty; }
static int mock_curr_menu_item = 0;
int gui_menu_get_curr_item(void) { return mock_curr_menu_item; }

static void *gui_mode = (void*)0x1000;
struct {
    struct {
        int gui_mode;
        int gui_mode_alt;
        int gui_mode_none;
    } state;
} camera_info;

struct {
    int show_alt_helper;
    int show_alt_helper_delay;
} conf;

static int gui_helper_displayat = 0;
static int gui_splash = 0;
static char *logo = (char*)0x2000;
void gui_set_need_restore(void) { gui_osd_need_restore = 1; }

#define CAM_DISP_ALT_TEXT 1

struct gui_vis_sig {
    void *mode_ptr;
    int gui_mode;
    int helper_due;
    int splash_sec;
    int menu_item;
};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;
static int gui_splash_expire = 0;

int gui_check_state_changed(void)
{
    extern int gui_menu_needs_redraw(void);
    extern int gui_menu_get_curr_item(void);

    int dirty = gui_osd_need_restore || gui_mode_need_redraw || gui_menu_needs_redraw();

    // 1. GUI mode / handler pointer
    void *current_mode = (void*)gui_mode;
    int current_gui_mode = camera_info.state.gui_mode;

    // 2. Timed ALT helper expiry [core/gui.c:2553-2570]
    int helper_due = 0;
#ifdef CAM_DISP_ALT_TEXT
    if (camera_info.state.gui_mode_alt && conf.show_alt_helper)
    {
        helper_due = (get_tick_count() >= gui_helper_displayat);
    }
#endif

    // 3. Timed splash countdown / active state [core/gui.c:2387-2405]
    int splash_sec = 0;
    if (gui_splash > 0)
    {
        int now = get_tick_count();
        if (gui_splash_expire == 0)
        {
            gui_splash_expire = now + (SPLASH_TIME * 80);
        }
        if (kbd_is_key_pressed(KEY_SHOOT_HALF) || (now >= gui_splash_expire))
        {
            gui_splash = 0;
            gui_splash_expire = 0;
            splash_sec = 0;
            if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)
                gui_set_need_restore();
            if (logo)
            {
                logo = NULL;
            }
            dirty = 1;
        }
        else
        {
            splash_sec = (gui_splash_expire - now + 999) / 1000;
            if (splash_sec <= 0) splash_sec = 1;
        }
    }

    // 4. Current menu item
    int menu_item = gui_menu_get_curr_item();

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {
        gui_sig_initialized = 1;
        sig_changed = 1;
    }
    else if (last_gui_sig.mode_ptr != current_mode ||
             last_gui_sig.gui_mode != current_gui_mode ||
             last_gui_sig.helper_due != helper_due ||
             last_gui_sig.splash_sec != splash_sec ||
             last_gui_sig.menu_item  != menu_item)
    {
        sig_changed = 1;
    }

    last_gui_sig.mode_ptr   = current_mode;
    last_gui_sig.gui_mode   = current_gui_mode;
    last_gui_sig.helper_due = helper_due;
    last_gui_sig.splash_sec = splash_sec;
    last_gui_sig.menu_item  = menu_item;

    return dirty || sig_changed;
}

int main(void)
{
    // Test 1: Initial call requests redraw
    mock_tick = 0;
    assert(gui_check_state_changed() == 1);

    // Test 2: Static state across 100 ticks produces ZERO redraw requests (no periodic forced redraw)
    for (int i = 0; i < 100; i++) {
        mock_tick += 20;
        assert(gui_check_state_changed() == 0);
    }

    // Test 3: ALT helper delay and expiry transition
    gui_mode = (void*)0x3000;
    camera_info.state.gui_mode = 2; // GUI_MODE_ALT
    camera_info.state.gui_mode_alt = 1;
    conf.show_alt_helper = 1;
    gui_helper_displayat = mock_tick + 2000; // expires 2000 ms later
    // Mode switch itself triggers redraw
    assert(gui_check_state_changed() == 1);

    // Ticks before expiry: helper_due stays 0 -> ZERO redraw requests
    for (int t = 0; t < 1980; t += 20) {
        mock_tick += 20;
        assert(gui_check_state_changed() == 0);
    }

    // Helper expiry tick: tick reaches gui_helper_displayat
    mock_tick = gui_helper_displayat;
    // Helper-expiry transition leads to a redraw request
    assert(gui_check_state_changed() == 1);

    // After expiry: helper_due stays 1 -> ZERO redraw requests
    for (int i = 0; i < 50; i++) {
        mock_tick += 20;
        assert(gui_check_state_changed() == 0);
    }

    // Test 4: Splash countdown leads to redraw requests and terminates cleanly
    camera_info.state.gui_mode = 0;
    camera_info.state.gui_mode_alt = 0;
    camera_info.state.gui_mode_none = 1;
    gui_splash = SPLASH_TIME; // 40 units * 80 ms = 3200 ms
    gui_splash_expire = 0;
    mock_tick = 10000;

    // Splash initiation triggers redraw request
    assert(gui_check_state_changed() == 1);

    // Step through splash duration: seconds countdown transitions trigger redraw requests
    int splash_redraw_count = 0;
    for (int t = 20; t <= 3500; t += 20) {
        mock_tick += 20;
        if (gui_check_state_changed()) {
            splash_redraw_count++;
            gui_osd_need_restore = 0; // simulated draw_restore()
        }
    }
    // Countdown from 4 -> 3 -> 2 -> 1 -> expiry (0) = 4 countdown transitions
    assert(splash_redraw_count >= 3 && splash_redraw_count <= 5);
    assert(gui_splash == 0); // splash successfully completed and expired

    // After splash completed: no redraw requests
    for (int i = 0; i < 50; i++) {
        mock_tick += 20;
        assert(gui_check_state_changed() == 0);
    }

    // Test 5: Menu navigation triggers redraw
    mock_curr_menu_item = 1;
    assert(gui_check_state_changed() == 1);
    mock_tick += 20;
    assert(gui_check_state_changed() == 0);
    mock_curr_menu_item = 2;
    assert(gui_check_state_changed() == 1);
    mock_tick += 20;
    assert(gui_check_state_changed() == 0);

    // Test 6: Half-shoot cancellation during splash
    gui_splash = SPLASH_TIME;
    gui_splash_expire = 0;
    mock_tick = 20000;
    assert(gui_check_state_changed() == 1); // Splash started
    mock_tick += 20;
    assert(gui_check_state_changed() == 0);
    mock_half_shoot = 1; // User presses half shoot
    assert(gui_check_state_changed() == 1); // Immediate cancellation redraw request
    assert(gui_splash == 0); // Cancelled

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_state.c"
            bin_file = Path(tmpdir) / "test_state"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation of state change harness failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"State change test harness assertion failed: {run.stderr}")

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
        if not diskboot.is_file() or diskboot.stat().st_size != 123609:
            env = os.environ.copy()
            if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
                env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"
            res = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--out-dir", str(OUT_DIR_GUI)],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"GUI fix build failed: {res.stderr}")

        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertEqual(diskboot.stat().st_size, 123609)
        self.assertEqual(
            sha256_file(diskboot),
            "06f8e1b6da3b9f77525cfc96ab5a25b82dca1a94da25989735826a569d04838b",
        )

        # Check manifests
        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 123609)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "06f8e1b6da3b9f77525cfc96ab5a25b82dca1a94da25989735826a569d04838b",
            )
            self.assertEqual(data["artifacts"]["modules_count"], 34)

    def test_gui_fix_reproducible_build(self):
        """Verify that clean full builds in fresh temporary directories are reproducible."""
        self._require_toolchain()

        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        # 1. Test reproducibility of G3X_GUI_FIX=1: two clean builds in fresh temporary directories
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            res1 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--out-dir", td1],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res1.returncode, 0, f"Clean build 1 (gui-fix) failed: {res1.stderr}")

            res2 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--out-dir", td2],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res2.returncode, 0, f"Clean build 2 (gui-fix) failed: {res2.stderr}")

            s1 = snapshot_distribution(Path(td1))
            s2 = snapshot_distribution(Path(td2))
            self.assertIn("DISKBOOT.BIN", s1)
            self.assertIn("DISKBOOT.BIN", s2)
            self.assertEqual(s1["DISKBOOT.BIN"][0], 123609)
            self.assertEqual(
                s1["DISKBOOT.BIN"][1],
                "06f8e1b6da3b9f77525cfc96ab5a25b82dca1a94da25989735826a569d04838b",
            )
            # Compare DISKBOOT.BIN plus every CHDK/ file hash
            self.assertEqual(s1, s2, "Two clean G3X_GUI_FIX=1 builds produced different hashes")

        # 2. Test reproducibility of G3X_GUI_FIX=1 FULL_HOOKS=1 in fresh temporary directory at least once
        with tempfile.TemporaryDirectory() as td3, tempfile.TemporaryDirectory() as td4:
            res3 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--full-hooks", "--out-dir", td3],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res3.returncode, 0, f"Clean build 3 (gui-fix + full-hooks) failed: {res3.stderr}")

            res4 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--full-hooks", "--out-dir", td4],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res4.returncode, 0, f"Clean build 4 (gui-fix + full-hooks) failed: {res4.stderr}")

            s3 = snapshot_distribution(Path(td3))
            s4 = snapshot_distribution(Path(td4))
            self.assertIn("DISKBOOT.BIN", s3)
            self.assertIn("DISKBOOT.BIN", s4)
            self.assertEqual(s3["DISKBOOT.BIN"][0], 123665)
            self.assertEqual(
                s3["DISKBOOT.BIN"][1],
                "d0e4648719fc37f38f49f1ad202592c87f0604bed9417e60be430c1b6a4f9e38",
            )
            # Compare DISKBOOT.BIN plus every CHDK/ file hash
            self.assertEqual(s3, s4, "Two clean G3X_GUI_FIX=1 FULL_HOOKS=1 builds produced different hashes")

    def test_gui_fix_full_hooks_build_artifacts_and_manifest(self):
        """Verify G3X_GUI_FIX=1 FULL_HOOKS=1 build produces exact manifest matches."""
        self._require_toolchain()

        diskboot = OUT_DIR_GUI_HOOKS / "DISKBOOT.BIN"
        if not diskboot.is_file() or diskboot.stat().st_size != 123665:
            env = os.environ.copy()
            if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
                env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"
            res = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--full-hooks", "--out-dir", str(OUT_DIR_GUI_HOOKS)],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"GUI fix + full hooks build failed: {res.stderr}")

        self.assertEqual(diskboot.stat().st_size, 123665)
        self.assertEqual(
            sha256_file(diskboot),
            "d0e4648719fc37f38f49f1ad202592c87f0604bed9417e60be430c1b6a4f9e38",
        )

        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_full_hooks_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 123665)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "d0e4648719fc37f38f49f1ad202592c87f0604bed9417e60be430c1b6a4f9e38",
            )
            self.assertIn("FULL_HOOKS=1", data["build"]["flags"])
            self.assertIn("G3X_GUI_FIX=1", data["build"]["flags"])

    def test_switch_off_reproduces_port41_manifest(self):
        """Verify that with GUI fix switch OFF, the default full build matches manifests/port41_manifest.json."""
        self._require_toolchain()

        verify_dir = REPO_ROOT / "out" / "port41-full-switch-off"
        # If verify_dir doesn't exist or isn't populated with default baseline, build it
        diskboot = verify_dir / "DISKBOOT.BIN"
        if not diskboot.is_file() or diskboot.stat().st_size != 124097:
            # Fall back to OUT_DIR_FULL if it already has the 124097 baseline
            if (OUT_DIR_FULL / "DISKBOOT.BIN").is_file() and (OUT_DIR_FULL / "DISKBOOT.BIN").stat().st_size == 124097:
                target_dir = OUT_DIR_FULL
                diskboot = target_dir / "DISKBOOT.BIN"
            else:
                env = os.environ.copy()
                env.pop("G3X_GUI_FIX", None)
                env.pop("FULL_HOOKS", None)
                if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
                    env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"
                res = subprocess.run(
                    ["python3", "-B", str(BUILD_SCRIPT), "--out-dir", str(verify_dir)],
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
                self.assertEqual(res.returncode, 0, f"Full build with GUI switch off failed: {res.stderr}")
                target_dir = verify_dir
                diskboot = target_dir / "DISKBOOT.BIN"
        else:
            target_dir = verify_dir

        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertEqual(diskboot.stat().st_size, 124097)
        self.assertEqual(
            sha256_file(diskboot),
            "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9",
        )

        with open(MANIFESTS_DIR / "port41_manifest.json", "r", encoding="utf-8") as f:
            port41_manifest = json.load(f)

        actual = snapshot_distribution(target_dir)
        self.assertEqual(
            actual["DISKBOOT.BIN"],
            (
                port41_manifest["artifacts"]["DISKBOOT.BIN"]["size"],
                port41_manifest["artifacts"]["DISKBOOT.BIN"]["sha256"],
            ),
        )
        for rel, info in port41_manifest["artifacts"]["chdk_files"].items():
            self.assertIn(rel, actual, f"Missing file from switch-off build: {rel}")
            self.assertEqual(actual[rel], (info["size"], info["sha256"]), f"Hash/size mismatch for {rel}")

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
