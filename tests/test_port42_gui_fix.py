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
        self.assertIn("760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738", text)
        self.assertIn("d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb", text)


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
        self.assertIn("gui_maintenance_tick", build_text)
        self.assertIn("gui_check_state_changed", build_text)
        self.assertIn("struct gui_vis_sig", build_text)
        self.assertIn("helper_due", build_text)
        self.assertIn("gui_helper_displayat", build_text)
        self.assertIn("splash_sec", build_text)
        self.assertIn("gui_splash_expire", build_text)
        self.assertIn("gui_menu_get_curr_item", build_text)
        self.assertIn("console_displayed", build_text)
        self.assertIn("console_last_modified", build_text)

        # Main loop replacement must NOT contain periodic counter patterns ((cnt++) & N)
        self.assertNotIn("cnt++", build_text[build_text.find("main_replacement"):build_text.find("core_conf_c")])
        self.assertNotIn("& 3", build_text[build_text.find("main_replacement"):build_text.find("core_conf_c")])

        # 2. Host simulation of gui_maintenance_tick + gui_check_state_changed using host gcc
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
        int state_kbd_script_run;
    } state;
} camera_info;

typedef struct {
    unsigned char   col;
    unsigned char   type;
} chdkColor;

typedef struct {
    chdkColor       fg;
    chdkColor       bg;
} confColor;

struct {
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_timeout;
} conf;

static int gui_helper_displayat = 0;
static int gui_splash = 0;
static char *logo = (char*)0x2000;
void gui_set_need_restore(void) { gui_osd_need_restore = 1; }
void gui_set_need_redraw(void) { gui_mode_need_redraw = 1; }

static int console_displayed = 0;
static long console_last_modified = 0;

void console_draw(int force_redraw)
{
    long t = get_tick_count();
    if (t <= console_last_modified + (conf.console_timeout * 1000))
    {
        if ((console_displayed == 0) || force_redraw)
        {
            console_displayed = 1;
        }
    }
    else if (console_displayed && !camera_info.state.state_kbd_script_run)
    {
        gui_set_need_restore();
        console_displayed = 0;
    }
}

void console_add_line(const char *str)
{
    (void)str;
    console_displayed = 0;
    console_last_modified = get_tick_count();
}

void console_clear(void)
{
    gui_set_need_restore();
    console_displayed = 0;
    console_last_modified = get_tick_count();
}

#define CAM_DISP_ALT_TEXT 1

struct gui_vis_sig {
    void *mode_ptr;
    int gui_mode;
    int helper_due;
    int splash_sec;
    int menu_item;
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_displayed;
    long console_last_modified;
};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;
static int gui_splash_expire = 0;
static int gui_splash_sec = 0;
static int gui_helper_due = 0;

void gui_redraw(int forced)
{
    if (gui_osd_need_restore)
    {
        gui_osd_need_restore = 0;
    }
    if (gui_mode_need_redraw)
    {
        gui_mode_need_redraw = 0;
    }
    console_draw(forced);
    last_gui_sig.console_displayed = console_displayed;
}

void gui_maintenance_tick(void)
{
    int now = get_tick_count();

    // 1. Splash timer, expiry and half-shutter cancellation [core/gui.c:2387-2405]
    if (gui_splash > 0)
    {
        if (gui_splash_expire == 0)
        {
            gui_splash_expire = now + (SPLASH_TIME * 80);
        }
        if (kbd_is_key_pressed(KEY_SHOOT_HALF) || (now >= gui_splash_expire))
        {
            gui_splash = 0;
            gui_splash_expire = 0;
            gui_splash_sec = 0;
            if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)
                gui_set_need_restore();
            if (logo)
            {
                logo = NULL;
            }
        }
        else
        {
            int sec = (gui_splash_expire - now + 999) / 1000;
            if (sec <= 0) sec = 1;
            gui_splash_sec = sec;
        }
    }
    else
    {
        gui_splash_sec = 0;
    }

    // 2. Helper expiry state maintenance [core/gui.c:2553-2570]
#ifdef CAM_DISP_ALT_TEXT
    if (camera_info.state.gui_mode_alt && conf.show_alt_helper)
    {
        gui_helper_due = (now >= gui_helper_displayat);
    }
    else
    {
        gui_helper_due = 0;
    }
#else
    gui_helper_due = 0;
#endif

    // 3. Console expiry / auto-hide state maintenance [core/console.c:103-107]
    if (console_displayed && !camera_info.state.state_kbd_script_run)
    {
        if (now > console_last_modified + (conf.console_timeout * 1000))
        {
            gui_set_need_restore();
            console_displayed = 0;
        }
    }
}

int gui_check_state_changed(void)
{
    extern int gui_menu_needs_redraw(void);
    extern int gui_menu_get_curr_item(void);

    int dirty = gui_osd_need_restore || gui_mode_need_redraw || gui_menu_needs_redraw();

    struct gui_vis_sig current_sig;
    current_sig.mode_ptr               = (void*)gui_mode;
    current_sig.gui_mode               = camera_info.state.gui_mode;
    current_sig.helper_due             = gui_helper_due;
    current_sig.splash_sec             = gui_splash_sec;
    current_sig.menu_item              = gui_menu_get_curr_item();
    current_sig.debug_shortcut_action  = conf.debug_shortcut_action;
    current_sig.dng_raw                = conf.dng_raw;
    current_sig.enable_shortcuts       = conf.enable_shortcuts;
    current_sig.hide_osd               = conf.hide_osd;
    current_sig.menu_color             = conf.menu_color;
    current_sig.menu_title_color       = conf.menu_title_color;
    current_sig.override_disable       = conf.override_disable;
    current_sig.save_raw               = conf.save_raw;
    current_sig.show_alt_helper        = conf.show_alt_helper;
    current_sig.show_alt_helper_delay  = conf.show_alt_helper_delay;
    current_sig.show_histo             = conf.show_histo;
    current_sig.show_osd               = conf.show_osd;
    current_sig.subj_dist_override_koef = conf.subj_dist_override_koef;
    current_sig.user_menu_as_root      = conf.user_menu_as_root;
    current_sig.user_menu_enable       = conf.user_menu_enable;
    current_sig.zebra_draw             = conf.zebra_draw;
    current_sig.console_displayed      = console_displayed;
    current_sig.console_last_modified  = console_last_modified;

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {
        gui_sig_initialized = 1;
        sig_changed = 1;
    }
    else if (last_gui_sig.mode_ptr               != current_sig.mode_ptr ||
             last_gui_sig.gui_mode               != current_sig.gui_mode ||
             last_gui_sig.helper_due             != current_sig.helper_due ||
             last_gui_sig.splash_sec             != current_sig.splash_sec ||
             last_gui_sig.menu_item              != current_sig.menu_item ||
             last_gui_sig.debug_shortcut_action  != current_sig.debug_shortcut_action ||
             last_gui_sig.dng_raw                != current_sig.dng_raw ||
             last_gui_sig.enable_shortcuts       != current_sig.enable_shortcuts ||
             last_gui_sig.hide_osd               != current_sig.hide_osd ||
             memcmp(&last_gui_sig.menu_color, &current_sig.menu_color, sizeof(confColor)) != 0 ||
             memcmp(&last_gui_sig.menu_title_color, &current_sig.menu_title_color, sizeof(confColor)) != 0 ||
             last_gui_sig.override_disable       != current_sig.override_disable ||
             last_gui_sig.save_raw               != current_sig.save_raw ||
             last_gui_sig.show_alt_helper        != current_sig.show_alt_helper ||
             last_gui_sig.show_alt_helper_delay  != current_sig.show_alt_helper_delay ||
             last_gui_sig.show_histo             != current_sig.show_histo ||
             last_gui_sig.show_osd               != current_sig.show_osd ||
             last_gui_sig.subj_dist_override_koef != current_sig.subj_dist_override_koef ||
             last_gui_sig.user_menu_as_root      != current_sig.user_menu_as_root ||
             last_gui_sig.user_menu_enable       != current_sig.user_menu_enable ||
             last_gui_sig.zebra_draw             != current_sig.zebra_draw ||
             last_gui_sig.console_displayed      != current_sig.console_displayed ||
             last_gui_sig.console_last_modified  != current_sig.console_last_modified)
    {
        sig_changed = 1;
    }

    last_gui_sig = current_sig;

    return dirty || sig_changed;
}

int main(void)
{
    // Test 1: Initial call requests redraw
    mock_tick = 0;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);

    // Test 2: Static state across 100 ticks produces ZERO redraw requests (no periodic forced redraw)
    for (int i = 0; i < 100; i++) {
        mock_tick += 20;
        gui_maintenance_tick();
        assert(gui_check_state_changed() == 0);
    }

    // Test 3: ALT helper delay and expiry transition
    gui_mode = (void*)0x3000;
    camera_info.state.gui_mode = 2; // GUI_MODE_ALT
    camera_info.state.gui_mode_alt = 1;
    conf.show_alt_helper = 1;
    gui_helper_displayat = mock_tick + 2000; // expires 2000 ms later
    // Mode switch itself triggers redraw
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);

    // Ticks before expiry: helper_due stays 0 -> ZERO redraw requests
    for (int t = 0; t < 1980; t += 20) {
        mock_tick += 20;
        gui_maintenance_tick();
        assert(gui_check_state_changed() == 0);
    }

    // Helper expiry tick: tick reaches gui_helper_displayat
    mock_tick = gui_helper_displayat;
    // Helper-expiry transition leads to a redraw request
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);

    // After expiry: helper_due stays 1 -> ZERO redraw requests
    for (int i = 0; i < 50; i++) {
        mock_tick += 20;
        gui_maintenance_tick();
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
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);

    // Step through splash duration: seconds countdown transitions trigger redraw requests
    int splash_redraw_count = 0;
    for (int t = 20; t <= 3500; t += 20) {
        mock_tick += 20;
        gui_maintenance_tick();
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
        gui_maintenance_tick();
        assert(gui_check_state_changed() == 0);
    }

    // Test 5: Menu navigation triggers redraw
    mock_curr_menu_item = 1;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0);
    mock_curr_menu_item = 2;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0);

    // Test 6: Half-shoot cancellation during splash
    gui_splash = SPLASH_TIME;
    gui_splash_expire = 0;
    mock_tick = 20000;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1); // Splash started
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0);
    mock_half_shoot = 1; // User presses half shoot
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1); // Immediate cancellation redraw request
    assert(gui_splash == 0); // Cancelled

    // Test 7: Console script print, clear, and expiry/auto-hide
    conf.console_timeout = 3; // 3 seconds = 3000 ms
    mock_tick = 30000;
    mock_half_shoot = 0;
    camera_info.state.gui_mode = 2; // ALT mode
    camera_info.state.gui_mode_alt = 1;
    camera_info.state.gui_mode_none = 0;
    gui_maintenance_tick();
    gui_check_state_changed();
    gui_redraw(0);

    // 7a. Simulate script print (console_add_line)
    console_add_line("script output line 1");
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1); // Redraw decision is true on next tick
    gui_redraw(0); // Repaint completes

    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0); // False again on tick after that

    // 7b. Simulate console clear (console_clear)
    console_clear();
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1); // Redraw decision is true on next tick
    gui_redraw(0);

    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0); // False again on tick after that

    // 7c. Simulate console timeout expiry / auto-hide (script not running)
    console_add_line("line before timeout");
    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1);
    gui_redraw(0);

    // Stable ticks during display window produce zero redraw requests
    for (int i = 0; i < 20; i++) {
        mock_tick += 20;
        gui_maintenance_tick();
        assert(gui_check_state_changed() == 0);
    }

    // Advance past timeout
    mock_tick += (conf.console_timeout * 1000) + 1;
    camera_info.state.state_kbd_script_run = 0;
    gui_maintenance_tick(); // Maintenance detects timeout, clears console_displayed & sets need_restore
    assert(gui_check_state_changed() == 1); // Redraw decision is true on next tick to erase console
    gui_redraw(0);

    mock_tick += 20;
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 0); // False again on tick after that

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

    def test_unconditional_gui_maintenance_and_draw_decision(self):
        """Verify Reviewer P1 requirement:
        (a) gui_maintenance_tick() is reached unconditionally on the forced-redraw path,
            with no short-circuit '||' or early return skipping it before draw decisions;
        (b) splash expiry and half-shutter cancel live in that unconditional step;
        (c) need_redraw is computed as forced || sentinel_lost || buffer_changed || state_changed.
        """
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")

        # 1. Structural checks on main loop patch
        main_repl_start = build_text.find("main_replacement = (")
        self.assertGreater(main_repl_start, 0)
        main_repl = build_text[main_repl_start : main_repl_start + 2000]

        # gui_maintenance_tick() called unconditionally
        self.assertIn("gui_maintenance_tick();", main_repl)
        # Check redraw condition formula
        self.assertIn("need_redraw = forced || sentinel_lost || buffer_changed || state_changed;", main_repl)
        self.assertIn("gui_redraw(forced || sentinel_lost || buffer_changed);", main_repl)

        # Confirm gui_maintenance_tick() call appears BEFORE any need_redraw computation
        maint_pos = main_repl.find("gui_maintenance_tick();")
        need_pos = main_repl.find("need_redraw =")
        self.assertGreater(need_pos, maint_pos, "gui_maintenance_tick() must be called before need_redraw computation")

        # Confirm no '||' or '&&' precedes gui_maintenance_tick()
        code_before_maint = main_repl[:maint_pos]
        self.assertNotIn("if (", code_before_maint)
        self.assertNotIn("||", code_before_maint)

        # 2. Structural checks on gui_maintenance_tick in core/gui.c
        alt_repl_start = build_text.find("alt_replacement = (")
        self.assertGreater(alt_repl_start, 0)
        alt_repl = build_text[alt_repl_start : alt_repl_start + 4500]

        maint_def = alt_repl.find("void gui_maintenance_tick(void)")
        state_def = alt_repl.find("int gui_check_state_changed(void)")
        self.assertGreater(maint_def, 0, "gui_maintenance_tick definition missing")
        self.assertGreater(state_def, maint_def, "gui_check_state_changed must appear after gui_maintenance_tick")

        maint_body = alt_repl[maint_def:state_def]
        # Splash expiry and half-shutter cancellation must live in gui_maintenance_tick
        self.assertIn("kbd_is_key_pressed(KEY_SHOOT_HALF)", maint_body)
        self.assertIn("now >= gui_splash_expire", maint_body)
        self.assertIn("gui_splash = 0;", maint_body)
        self.assertIn("gui_splash_expire = 0;", maint_body)
        self.assertIn("gui_helper_due = (now >= gui_helper_displayat);", maint_body)
        # Console expiry / auto-hide must live in gui_maintenance_tick
        self.assertIn("now > console_last_modified", maint_body)
        self.assertIn("console_displayed = 0;", maint_body)

        # 3. Host C simulation: verify maintenance executes and advances splash expiry & cancel
        # even when forced = 1 (or sentinel_lost = 1) on every single tick.
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }
static int mock_half_shoot = 0;
int kbd_is_key_pressed(int k) { return mock_half_shoot; }
#define KEY_SHOOT_HALF 1
#define SPLASH_TIME 40

static int gui_osd_need_restore = 0;
static int gui_splash = 0;
static char *logo = (char*)0x2000;
void gui_set_need_restore(void) { gui_osd_need_restore = 1; }

static int gui_splash_expire = 0;
static int gui_splash_sec = 0;

void gui_maintenance_tick(void)
{
    int now = get_tick_count();
    if (gui_splash > 0)
    {
        if (gui_splash_expire == 0)
        {
            gui_splash_expire = now + (SPLASH_TIME * 80);
        }
        if (kbd_is_key_pressed(KEY_SHOOT_HALF) || (now >= gui_splash_expire))
        {
            gui_splash = 0;
            gui_splash_expire = 0;
            gui_splash_sec = 0;
            gui_set_need_restore();
            if (logo)
            {
                logo = NULL;
            }
        }
        else
        {
            int sec = (gui_splash_expire - now + 999) / 1000;
            if (sec <= 0) sec = 1;
            gui_splash_sec = sec;
        }
    }
    else
    {
        gui_splash_sec = 0;
    }
}

int main(void)
{
    // Simulation 1: Under continuous forced redraw (e.g. forced = 1 or sentinel_lost = 1),
    // gui_maintenance_tick() MUST still run and expire splash cleanly after 3200ms.
    gui_splash = SPLASH_TIME;
    gui_splash_expire = 0;
    mock_tick = 5000;

    int forced = 1;
    int sentinel_lost = 1;
    int buffer_changed = 0;

    for (int t = 0; t <= 3500; t += 20) {
        mock_tick += 20;
        // Unconditional maintenance call on forced redraw path
        gui_maintenance_tick();
        int state_changed = 0;
        int need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
        assert(need_redraw == 1);
    }
    // Verify splash expired to 0 despite continuous forced-redraw
    assert(gui_splash == 0);
    assert(gui_splash_expire == 0);

    // Simulation 2: Under continuous forced redraw, half-shutter cancellation MUST cancel splash immediately
    gui_splash = SPLASH_TIME;
    gui_splash_expire = 0;
    mock_tick = 20000;
    gui_maintenance_tick();
    assert(gui_splash > 0);

    mock_tick += 20;
    mock_half_shoot = 1; // User presses half-shutter
    gui_maintenance_tick(); // Maintenance tick must catch cancel
    assert(gui_splash == 0); // Immediately cancelled

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_unconditional.c"
            bin_file = Path(tmpdir) / "test_unconditional"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

    def test_console_script_print_clear_and_expiry_regression(self):
        """Verify Reviewer P2 requirement:
        Console updates trigger redraws under G3X_GUI_FIX=1:
        (a) Static audit: console_displayed and console_last_modified are in struct gui_vis_sig,
            gui_maintenance_tick() handles console timeout expiry,
            core/console.c exports console_last_modified and triggers redraw on MBOX scroll,
            gui_redraw() syncs last_gui_sig.console_displayed.
        (b) Host C regression test: After the first repaint, keep active buffer and sentinel stable,
            simulate script print (console_add_line) -> redraw decision is true on next tick, false again on tick after.
            Simulate console clear (console_clear) -> redraw decision is true on next tick, false again on tick after.
            Simulate console expiry/auto-hide -> redraw decision is true on next tick to erase console, false on tick after.
        """
        # 1. Static audit on tools/build_port41_full.py patching
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("extern long console_last_modified;", build_text)
        self.assertIn("long console_last_modified;", build_text)
        self.assertIn("console_displayed = 0;", build_text)
        self.assertIn("now > console_last_modified + (conf.console_timeout * 1000)", build_text)
        self.assertIn("last_gui_sig.console_displayed = console_displayed;", build_text)
        self.assertIn("gui_set_need_redraw();", build_text)

        # 2. Host simulation of exact main.c redraw decision logic
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }

static int gui_osd_need_restore = 0;
static int gui_mode_need_redraw = 0;
void gui_set_need_restore(void) { gui_osd_need_restore = 1; }
void gui_set_need_redraw(void) { gui_mode_need_redraw = 1; }

static struct {
    struct {
        int gui_mode;
        int state_kbd_script_run;
    } state;
} camera_info;

static struct {
    int console_timeout;
} conf;

static int console_displayed = 0;
static long console_last_modified = 0;

void console_draw(int force_redraw)
{
    long t = get_tick_count();
    if (t <= console_last_modified + (conf.console_timeout * 1000))
    {
        if ((console_displayed == 0) || force_redraw)
        {
            console_displayed = 1;
        }
    }
    else if (console_displayed && !camera_info.state.state_kbd_script_run)
    {
        gui_set_need_restore();
        console_displayed = 0;
    }
}

void console_add_line(const char *str)
{
    (void)str;
    console_displayed = 0;
    console_last_modified = get_tick_count();
}

void console_clear(void)
{
    gui_set_need_restore();
    console_displayed = 0;
    console_last_modified = get_tick_count();
}

struct gui_vis_sig {
    int gui_mode;
    int console_displayed;
    long console_last_modified;
};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;

void gui_redraw(int forced)
{
    if (gui_osd_need_restore)
    {
        gui_osd_need_restore = 0;
    }
    if (gui_mode_need_redraw)
    {
        gui_mode_need_redraw = 0;
    }
    console_draw(forced);
    last_gui_sig.console_displayed = console_displayed;
}

void gui_maintenance_tick(void)
{
    int now = get_tick_count();
    if (console_displayed && !camera_info.state.state_kbd_script_run)
    {
        if (now > console_last_modified + (conf.console_timeout * 1000))
        {
            gui_set_need_restore();
            console_displayed = 0;
        }
    }
}

int gui_check_state_changed(void)
{
    int dirty = gui_osd_need_restore || gui_mode_need_redraw;

    struct gui_vis_sig current_sig;
    current_sig.gui_mode = camera_info.state.gui_mode;
    current_sig.console_displayed = console_displayed;
    current_sig.console_last_modified = console_last_modified;

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {
        gui_sig_initialized = 1;
        sig_changed = 1;
    }
    else if (last_gui_sig.gui_mode != current_sig.gui_mode ||
             last_gui_sig.console_displayed != current_sig.console_displayed ||
             last_gui_sig.console_last_modified != current_sig.console_last_modified)
    {
        sig_changed = 1;
    }

    last_gui_sig = current_sig;
    return dirty || sig_changed;
}

int main(void)
{
    conf.console_timeout = 3; // 3 seconds timeout
    camera_info.state.gui_mode = 2; // ALT mode
    camera_info.state.state_kbd_script_run = 0;

    // Stable active buffer and sentinel guards
    int forced = 0;
    int sentinel_lost = 0;
    int buffer_changed = 0;

    // Step 0: Initial boot / first repaint
    mock_tick = 1000;
    gui_maintenance_tick();
    int state_changed = gui_check_state_changed();
    int need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 1);
    gui_redraw(0);

    // After first repaint: tick with no changes produces need_redraw == 0
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 0);

    // Step 1: Simulate script print (console_add_line)
    console_add_line("print statement 1");

    // Next tick: redraw decision must be true
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 1);
    gui_redraw(0); // Repaint completes

    // Tick after that: false again if nothing changed
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 0);

    // Another stable tick check
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 0);

    // Step 2: Simulate console clear (console_clear)
    console_clear();

    // Next tick: redraw decision must be true
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 1);
    gui_redraw(0);

    // Tick after that: false again if nothing changed
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 0);

    // Step 3: Simulate console print followed by timeout expiry / auto-hide
    console_add_line("print statement 2");
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 1);
    gui_redraw(0);

    // Ticks while displayed (before timeout) remain false
    for (int i = 0; i < 50; i++) {
        mock_tick += 20;
        gui_maintenance_tick();
        state_changed = gui_check_state_changed();
        need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
        assert(need_redraw == 0);
    }

    // Advance past timeout (3000 ms) with script inactive
    mock_tick += (conf.console_timeout * 1000) + 1;
    camera_info.state.state_kbd_script_run = 0;
    gui_maintenance_tick(); // Maintenance catches expiry: calls gui_set_need_restore(), console_displayed = 0
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 1); // Redraw decision is true on next tick to erase console!
    gui_redraw(0); // Console erased

    // Tick after that: false again if nothing changed
    mock_tick += 20;
    gui_maintenance_tick();
    state_changed = gui_check_state_changed();
    need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    assert(need_redraw == 0);

    for (int i = 0; i < 50; i++) {
        mock_tick += 20;
        gui_maintenance_tick();
        state_changed = gui_check_state_changed();
        need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
        assert(need_redraw == 0);
    }

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_console.c"
            bin_file = Path(tmpdir) / "test_console"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

    def test_alt_helper_conf_fields_tracked_in_signature(self):
        """Verify Reviewer P2 requirement:
        All conf fields read by gui_draw_alt_helper() in chdk-port/core/gui.c:2553-2700
        are tracked in struct gui_vis_sig, and any value change triggers a redraw request.
        Citing: chdk-port/core/gui.c:2553-2700, chdk-port/core/gui_osd.c:860-882.
        """
        # 1. Parse chdk-port/core/gui.c:2553-2700 to extract all conf.* fields read by helper drawing
        gui_c_lines = (REPO_ROOT / "chdk-port" / "core" / "gui.c").read_text(encoding="utf-8").splitlines()[2552:2700]
        helper_text = "\n".join(gui_c_lines)
        helper_conf_fields = sorted(set(re.findall(r"\bconf\.(\w+)", helper_text)))

        # Required minimums specified by reviewer
        self.assertIn("show_histo", helper_conf_fields)
        self.assertIn("zebra_draw", helper_conf_fields)
        self.assertIn("show_osd", helper_conf_fields)
        self.assertIn("save_raw", helper_conf_fields)
        self.assertIn("override_disable", helper_conf_fields)

        # 2. Verify all extracted fields are present in struct gui_vis_sig in tools/build_port41_full.py
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        sig_start = build_text.find("struct gui_vis_sig {")
        self.assertGreater(sig_start, 0)
        sig_end = build_text.find("};", sig_start)
        sig_body = build_text[sig_start:sig_end]

        for field in helper_conf_fields:
            self.assertIn(
                field,
                sig_body,
                f"conf.{field} read in chdk-port/core/gui.c:2553-2700 must be tracked in struct gui_vis_sig",
            )

        # 3. Host C simulation: mutate each conf field and verify gui_check_state_changed() returns 1
        fields_c_struct = "\n    ".join(
            f"confColor {f};" if f in ("menu_color", "menu_title_color") else f"int {f};"
            for f in helper_conf_fields
        )
        fields_sig_struct = fields_c_struct
        fields_assign = "\n    ".join(f"current_sig.{f} = conf.{f};" for f in helper_conf_fields)
        fields_compare = " ||\n             ".join(
            f"memcmp(&last_gui_sig.{f}, &current_sig.{f}, sizeof(confColor)) != 0"
            if f in ("menu_color", "menu_title_color")
            else f"last_gui_sig.{f} != current_sig.{f}"
            for f in helper_conf_fields
        )
        fields_array = ", ".join(
            f"(int*)&conf.{f}" if f in ("menu_color", "menu_title_color") else f"&conf.{f}"
            for f in helper_conf_fields
        )
        num_fields = len(helper_conf_fields)

        harness_c = f"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

typedef struct {{
    unsigned char   col;
    unsigned char   type;
}} chdkColor;

typedef struct {{
    chdkColor       fg;
    chdkColor       bg;
}} confColor;

static int mock_tick = 0;
int get_tick_count(void) {{ return mock_tick; }}
int kbd_is_key_pressed(int k) {{ (void)k; return 0; }}
int gui_menu_needs_redraw(void) {{ return 0; }}
int gui_menu_get_curr_item(void) {{ return 0; }}

static void *gui_mode = (void*)0x1000;
struct {{
    struct {{
        int gui_mode;
        int gui_mode_alt;
        int gui_mode_none;
    }} state;
}} camera_info;

struct {{
    {fields_c_struct}
}} conf;

struct gui_vis_sig {{
    void *mode_ptr;
    int gui_mode;
    int helper_due;
    int splash_sec;
    int menu_item;
    {fields_sig_struct}
}};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;

int gui_check_state_changed(void)
{{
    int dirty = 0;
    struct gui_vis_sig current_sig;
    current_sig.mode_ptr = (void*)gui_mode;
    current_sig.gui_mode = camera_info.state.gui_mode;
    current_sig.helper_due = 0;
    current_sig.splash_sec = 0;
    current_sig.menu_item = 0;
    {fields_assign}

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {{
        gui_sig_initialized = 1;
        sig_changed = 1;
    }}
    else if (last_gui_sig.mode_ptr != current_sig.mode_ptr ||
             last_gui_sig.gui_mode != current_sig.gui_mode ||
             {fields_compare})
    {{
        sig_changed = 1;
    }}

    last_gui_sig = current_sig;
    return dirty || sig_changed;
}}

int main(void)
{{
    int *conf_ptrs[] = {{ {fields_array} }};
    int count = {num_fields};

    // Initialize state
    assert(gui_check_state_changed() == 1);
    assert(gui_check_state_changed() == 0);

    // Verify each conf field mutation triggers redraw and stays clean afterwards
    for (int i = 0; i < count; i++) {{
        (*conf_ptrs[i]) += 1;
        // Mutation must trigger redraw
        assert(gui_check_state_changed() == 1);
        // Clean tick must not trigger redraw
        assert(gui_check_state_changed() == 0);
    }}

    return 0;
}}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_conf_fields.c"
            bin_file = Path(tmpdir) / "test_conf_fields"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

    def test_palette_exit_alt_reenter_alt_regression(self):
        """Reviewer P1 regression test:
        Sequence:
        1. User in Menu mode
        2. User selects palette (sets gui_menu_redraw = 2, mode -> GUI_MODE_PALETTE)
        3. User exits ALT straight from palette module (ALT_MODE_LEAVE -> GUI_MODE_NONE)
        4. User re-enters ALT (ALT_MODE_ENTER -> GUI_MODE_ALT)
        5. Over N idle ticks:
           - Shows at most one full repaint
           - Zero per-tick g3x_fill_menu_opaque_black calls
        """
        # 1. Static audit on full_build/g3x/gui_menu.c and tools/build_port41_full.py
        menu_c = (REPO_ROOT / "full_build" / "g3x" / "gui_menu.c").read_text(encoding="utf-8")
        self.assertIn("camera_info.state.gui_mode != GUI_MODE_MENU", menu_c)
        self.assertIn("void gui_menu_clear_redraw(void)", menu_c)

        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("is_menu_active = (camera_info.state.gui_mode == GUI_MODE_MENU);", build_text)
        self.assertIn("menu_dirty = is_menu_active && gui_menu_needs_redraw();", build_text)
        self.assertIn("gui_menu_clear_redraw();", build_text)
        self.assertIn("alt_helper_drawn = 0;", build_text)
        self.assertIn("if (force_redraw || !draw_test_guard() || !alt_helper_drawn)", build_text)

        # 2. Host simulation of exact sequence
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#define GUI_MODE_STARTUP -1
#define GUI_MODE_NONE     0
#define GUI_MODE_ALT      1
#define GUI_MODE_MENU     2
#define GUI_MODE_SCRIPT   3
#define GUI_MODE_PALETTE  6
#define GUI_MODE_MODULE   9

#define ALT_MODE_NORMAL 0
#define ALT_MODE_ENTER  1
#define ALT_MODE_LEAVE  2

typedef struct gui_handler {
    int mode;
    void (*redraw)(int);
    int (*kbd_process)(void);
    int flags;
} gui_handler;

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }
static int mock_sentinel = 1;
int draw_test_guard(void) { return mock_sentinel; }
int check_gui_needs_redraw(void) { return 0; }
int check_bitmap_buffer_changed(void) { return 0; }

struct {
    struct {
        int gui_mode;
        int gui_mode_alt;
        int gui_mode_none;
        int state_kbd_script_run;
    } state;
} camera_info;

typedef struct { unsigned char col, type; } chdkColor;
typedef struct { chdkColor fg, bg; } confColor;

struct {
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_timeout;
} conf;

static int opaque_black_fill_count = 0;
void g3x_fill_menu_opaque_black(void)
{
    opaque_black_fill_count++;
}

static int gui_menu_redraw = 0;
static int gui_menu_curr_item = 0;

int gui_menu_needs_redraw(void)
{
    if (camera_info.state.gui_mode != GUI_MODE_MENU)
        return 0;
    return gui_menu_redraw != 0;
}

void gui_menu_clear_redraw(void)
{
    gui_menu_redraw = 0;
}

int gui_menu_get_curr_item(void)
{
    return gui_menu_curr_item;
}

static int gui_helper_displayat = 0;
static int alt_helper_drawn = 0;

void gui_reset_alt_helper(void)
{
    alt_helper_drawn = 0;
    gui_helper_displayat = get_tick_count() + (conf.show_alt_helper_delay * 1000);
}

static int alt_helper_draw_count = 0;
static void gui_draw_alt_helper(int force_redraw)
{
    alt_helper_draw_count++;
    if (force_redraw || !draw_test_guard() || !alt_helper_drawn)
    {
        g3x_fill_menu_opaque_black();
        alt_helper_drawn = 1;
    }
}

static int menu_draw_count = 0;
static void gui_menu_draw(int force_redraw)
{
    menu_draw_count++;
    if (force_redraw)
        gui_menu_redraw = 2;
    if (gui_menu_redraw)
    {
        if (gui_menu_redraw == 2)
        {
            g3x_fill_menu_opaque_black();
        }
        gui_menu_redraw = 0;
    }
}

static int default_draw_count = 0;
static void gui_default_draw(int force_redraw)
{
    default_draw_count++;
}

static int palette_draw_count = 0;
static int gui_palette_redraw = 0;
static void gui_palette_draw(int force_redraw)
{
    palette_draw_count++;
    if (force_redraw) gui_palette_redraw = 1;
    if (gui_palette_redraw)
    {
        gui_palette_redraw = 0;
    }
}

gui_handler defaultGuiHandler = { GUI_MODE_NONE, gui_default_draw, 0, 0 };
gui_handler altGuiHandler     = { GUI_MODE_ALT,  gui_draw_alt_helper, 0, 0 };
gui_handler menuGuiHandler    = { GUI_MODE_MENU, gui_menu_draw, 0, 0 };
gui_handler paletteGuiHandler = { GUI_MODE_PALETTE, gui_palette_draw, 0, 0 };

static gui_handler *gui_mode = &defaultGuiHandler;
static int gui_osd_need_restore = 0;
static int gui_mode_need_redraw = 0;

void gui_set_mode(gui_handler *mode)
{
    camera_info.state.gui_mode = mode->mode;
    camera_info.state.gui_mode_none = (mode->mode == GUI_MODE_NONE);
    camera_info.state.gui_mode_alt = (mode->mode == GUI_MODE_ALT);

    if (gui_mode == mode)
        return;

    gui_mode = mode;
    alt_helper_drawn = 0;
    gui_menu_clear_redraw();
    gui_osd_need_restore = 1;
}

void gui_activate_alt_mode(int state)
{
    switch (state)
    {
    case ALT_MODE_ENTER:
        alt_helper_drawn = 0;
        gui_menu_clear_redraw();
        gui_set_mode(&altGuiHandler);
        gui_reset_alt_helper();
        break;
    case ALT_MODE_LEAVE:
        alt_helper_drawn = 0;
        gui_menu_clear_redraw();
        gui_set_mode(&defaultGuiHandler);
        break;
    }
}

struct gui_vis_sig {
    void *mode_ptr;
    int gui_mode;
    int helper_due;
    int splash_sec;
    int menu_item;
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_displayed;
    long console_last_modified;
};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;
static int gui_helper_due = 0;

void gui_maintenance_tick(void)
{
    int now = get_tick_count();
    if (camera_info.state.gui_mode_alt && conf.show_alt_helper)
    {
        gui_helper_due = (now >= gui_helper_displayat);
    }
    else
    {
        gui_helper_due = 0;
    }
}

int gui_check_state_changed(void)
{
    int is_menu_active = (camera_info.state.gui_mode == GUI_MODE_MENU);
    int menu_dirty = is_menu_active && gui_menu_needs_redraw();
    int dirty = gui_osd_need_restore || gui_mode_need_redraw || menu_dirty;

    struct gui_vis_sig current_sig;
    memset(&current_sig, 0, sizeof(current_sig));
    current_sig.mode_ptr = (void*)gui_mode;
    current_sig.gui_mode = camera_info.state.gui_mode;
    current_sig.helper_due = gui_helper_due;
    current_sig.menu_item = is_menu_active ? gui_menu_get_curr_item() : 0;
    current_sig.show_alt_helper = conf.show_alt_helper;

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {
        gui_sig_initialized = 1;
        sig_changed = 1;
    }
    else if (last_gui_sig.mode_ptr != current_sig.mode_ptr ||
             last_gui_sig.gui_mode != current_sig.gui_mode ||
             last_gui_sig.helper_due != current_sig.helper_due ||
             last_gui_sig.menu_item != current_sig.menu_item ||
             last_gui_sig.show_alt_helper != current_sig.show_alt_helper)
    {
        sig_changed = 1;
    }

    if (sig_changed)
    {
        alt_helper_drawn = 0;
    }

    last_gui_sig = current_sig;
    return dirty || sig_changed;
}

void gui_redraw(int forced)
{
    gui_osd_need_restore = 0;
    gui_mode_need_redraw = 0;
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(forced);
}

int gui_is_module_mode(void)
{
    return (camera_info.state.gui_mode > GUI_MODE_MENU);
}

void gui_draw_module_tick(void)
{
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(0);
}

int main(void)
{
    conf.show_alt_helper = 1;
    conf.show_alt_helper_delay = 0; // immediate display for test
    mock_tick = 1000;

    // Step 1: Enter ALT mode
    gui_activate_alt_mode(ALT_MODE_ENTER);
    gui_maintenance_tick();
    gui_check_state_changed();
    gui_redraw(0);
    assert(opaque_black_fill_count == 1); // initial ALT helper fill
    opaque_black_fill_count = 0;

    // Step 2: Open Menu
    gui_set_mode(&menuGuiHandler);
    gui_maintenance_tick();
    gui_check_state_changed();
    gui_redraw(1);
    assert(opaque_black_fill_count == 1); // menu initial fill
    opaque_black_fill_count = 0;

    // Step 3: Open Palette from Menu (gui_menu.c:682 sets gui_menu_redraw = 2)
    gui_set_mode(&paletteGuiHandler);
    gui_menu_redraw = 2; // simulates gui_menu.c:682
    gui_maintenance_tick();
    gui_check_state_changed();
    gui_redraw(0);
    assert(opaque_black_fill_count == 0); // palette does not run menu opaque black

    // Step 4: Exit ALT straight from palette module (ALT_MODE_LEAVE)
    gui_activate_alt_mode(ALT_MODE_LEAVE);
    gui_maintenance_tick();
    gui_check_state_changed();
    gui_redraw(0);
    assert(camera_info.state.gui_mode == GUI_MODE_NONE);
    assert(opaque_black_fill_count == 0);

    // Step 5: Re-enter ALT (ALT_MODE_ENTER)
    gui_activate_alt_mode(ALT_MODE_ENTER);
    gui_maintenance_tick();
    assert(gui_check_state_changed() == 1); // entry triggers one state change / repaint
    gui_redraw(0);
    assert(opaque_black_fill_count == 1); // one full repaint on re-entry
    opaque_black_fill_count = 0;

    // Step 6: Over N (100) idle ticks:
    // MUST show ZERO full repaints and ZERO g3x_fill_menu_opaque_black calls!
    int idle_repaints = 0;
    for (int i = 0; i < 100; i++)
    {
        mock_tick += 20;
        gui_maintenance_tick();
        int forced = check_gui_needs_redraw();
        int sentinel_lost = !draw_test_guard();
        int buffer_changed = check_bitmap_buffer_changed();
        int state_changed = gui_check_state_changed();
        int need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
        if (need_redraw)
        {
            idle_repaints++;
            gui_redraw(forced || sentinel_lost || buffer_changed);
        }
        else if (gui_is_module_mode())
        {
            gui_draw_module_tick();
        }
    }

    assert(idle_repaints == 0); // No per-tick redraws!
    assert(opaque_black_fill_count == 0); // Zero per-tick g3x_fill_menu_opaque_black calls!

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_palette_reenter.c"
            bin_file = Path(tmpdir) / "test_palette_reenter"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

    def test_module_mode_keypress_draw_and_no_opaque_fill(self):
        """Reviewer P2 test:
        When active GUI mode is a module mode (anything other than menu, ALT helper, splash):
        - Calls that mode's draw handler every tick via gui_draw_module_tick.
        - Idle call draws nothing (module checks private redraw flag).
        - Key press in module mode sets private flag and reaches draw handler on next tick.
        - Opaque black fill does NOT run every tick.
        """
        # 1. Static audit on tools/build_port41_full.py
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("extern int gui_is_module_mode(void);", build_text)
        self.assertIn("extern void gui_draw_module_tick(void);", build_text)
        self.assertIn("else if (gui_is_module_mode())", build_text)
        self.assertIn("gui_draw_module_tick();", build_text)
        self.assertIn("camera_info.state.gui_mode > GUI_MODE_MENU", build_text)

        # 2. Host simulation of module mode key press and draw dispatch
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#define GUI_MODE_NONE     0
#define GUI_MODE_ALT      1
#define GUI_MODE_MENU     2
#define GUI_MODE_MODULE   9

typedef struct gui_handler {
    int mode;
    void (*redraw)(int);
    int (*kbd_process)(void);
} gui_handler;

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }
int draw_test_guard(void) { return 1; }
int check_gui_needs_redraw(void) { return 0; }
int check_bitmap_buffer_changed(void) { return 0; }

struct {
    struct {
        int gui_mode;
    } state;
} camera_info;

static int opaque_black_fill_count = 0;
void g3x_fill_menu_opaque_black(void)
{
    opaque_black_fill_count++;
}

static int mock_tbox_redraw = 0;
static int mock_tbox_draw_count = 0;
static int mock_tbox_chars_rendered = 0;

static void gui_tbox_draw(int force_redraw)
{
    mock_tbox_draw_count++;
    if (force_redraw)
        mock_tbox_redraw = 2;
    if (mock_tbox_redraw)
    {
        // Actual module draw operation
        mock_tbox_chars_rendered += 5;
        mock_tbox_redraw = 0;
    }
}

static int gui_tbox_kbd_process(void)
{
    // Key press in module sets private flag [modules/gui_tbox.c:385-409]
    mock_tbox_redraw = 1;
    return 1;
}

gui_handler tboxGuiHandler = { GUI_MODE_MODULE, gui_tbox_draw, gui_tbox_kbd_process };
static gui_handler *gui_mode = &tboxGuiHandler;

int gui_is_module_mode(void)
{
    return (camera_info.state.gui_mode > GUI_MODE_MENU);
}

void gui_draw_module_tick(void)
{
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(0);
}

int gui_check_state_changed(void)
{
    // Signature tracker sees no global change during module editing
    return 0;
}

void gui_redraw(int forced)
{
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(forced);
}

int main(void)
{
    camera_info.state.gui_mode = GUI_MODE_MODULE; // 9 > 2
    mock_tick = 1000;
    assert(gui_is_module_mode() == 1);

    // Initial 20 idle ticks: mock_tbox_redraw is 0
    for (int i = 0; i < 20; i++)
    {
        mock_tick += 20;
        int need_redraw = gui_check_state_changed();
        if (need_redraw)
            gui_redraw(0);
        else if (gui_is_module_mode())
            gui_draw_module_tick();
    }

    // Called draw handler every tick, but drew nothing (mock_tbox_redraw was 0)
    assert(mock_tbox_draw_count == 20);
    assert(mock_tbox_chars_rendered == 0);
    assert(opaque_black_fill_count == 0); // No opaque black fill!

    // User presses a key in textbox:
    gui_mode->kbd_process();
    assert(mock_tbox_redraw == 1);

    // Next tick: key press reaches draw handler and gets rendered immediately
    mock_tick += 20;
    int need_redraw = gui_check_state_changed();
    assert(need_redraw == 0);
    assert(gui_is_module_mode() == 1);
    gui_draw_module_tick();

    assert(mock_tbox_draw_count == 21);
    assert(mock_tbox_chars_rendered == 5); // Rendered!
    assert(mock_tbox_redraw == 0); // Consumed!
    assert(opaque_black_fill_count == 0); // Opaque fill stayed completely out of path!

    // Next 20 idle ticks: no redraws
    for (int i = 0; i < 20; i++)
    {
        mock_tick += 20;
        if (gui_check_state_changed())
            gui_redraw(0);
        else if (gui_is_module_mode())
            gui_draw_module_tick();
    }
    assert(mock_tbox_draw_count == 41);
    assert(mock_tbox_chars_rendered == 5); // Still 5, no extra draws
    assert(opaque_black_fill_count == 0); // Zero opaque fills!

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_module_tick.c"
            bin_file = Path(tmpdir) / "test_module_tick"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

    def test_normal_mode_osd_incremental_draw_and_no_erase(self):
        """Verify:
        (a) after splash expiry, with an unchanged signature and intact sentinel,
            a change in the clock second leads to a clock draw with no opaque fill or full erase;
        (b) a half-shutter state change in NORMAL mode leads to an OSD draw;
        (c) the existing ALT/menu no-forced-redraw and module-mode tests still pass.
        """
        # 1. Static audit on tools/build_port41_full.py
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("extern int gui_is_osd_mode(void);", build_text)
        self.assertIn("extern void gui_draw_osd_tick(void);", build_text)
        self.assertIn("else if (gui_is_osd_mode())", build_text)
        self.assertIn("gui_draw_osd_tick();", build_text)
        self.assertIn("camera_info.state.gui_mode == GUI_MODE_NONE", build_text)

        # 2. Host C simulation of exact normal OSD incremental drawing path
        harness_c = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <assert.h>

#define GUI_MODE_NONE     0
#define GUI_MODE_ALT      1
#define GUI_MODE_MENU     2
#define GUI_MODE_MODULE   9

typedef struct gui_handler {
    int mode;
    void (*redraw)(int);
    int (*kbd_process)(void);
} gui_handler;

static int mock_tick = 0;
int get_tick_count(void) { return mock_tick; }
static int mock_half_shoot = 0;
int kbd_is_key_pressed(int k) { return mock_half_shoot; }
#define KEY_SHOOT_HALF 1
#define SPLASH_TIME 40

static int mock_guard = 1;
int draw_test_guard(void) { return mock_guard; }
void draw_set_guard(void) { mock_guard = 1; }

static int mock_buffer_changed = 0;
int check_bitmap_buffer_changed(void) { return mock_buffer_changed; }
static int mock_gui_needs_redraw = 0;
int check_gui_needs_redraw(void) { return mock_gui_needs_redraw; }

static int gui_osd_need_restore = 0;
static int gui_mode_need_redraw = 0;
void gui_set_need_restore(void) { gui_osd_need_restore = 1; }
void gui_set_need_redraw(void) { gui_mode_need_redraw = 1; }

static int draw_restore_count = 0;
void draw_restore(void) { draw_restore_count++; }

static int opaque_black_fill_count = 0;
void g3x_fill_menu_opaque_black(void) { opaque_black_fill_count++; }

struct {
    struct {
        int gui_mode;
        int gui_mode_alt;
        int gui_mode_none;
        int is_shutter_half_press;
        int state_kbd_script_run;
    } state;
} camera_info;

typedef struct {
    unsigned char col;
    unsigned char type;
} chdkColor;

typedef struct {
    chdkColor fg;
    chdkColor bg;
} confColor;

struct {
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_timeout;
} conf;

static int gui_helper_displayat = 0;
static int gui_splash = 0;
static char *logo = (char*)0x2000;
static int console_displayed = 0;
static long console_last_modified = 0;

struct gui_vis_sig {
    void *mode_ptr;
    int gui_mode;
    int helper_due;
    int splash_sec;
    int menu_item;
    int debug_shortcut_action;
    int dng_raw;
    int enable_shortcuts;
    int hide_osd;
    confColor menu_color;
    confColor menu_title_color;
    int override_disable;
    int save_raw;
    int show_alt_helper;
    int show_alt_helper_delay;
    int show_histo;
    int show_osd;
    int subj_dist_override_koef;
    int user_menu_as_root;
    int user_menu_enable;
    int zebra_draw;
    int console_displayed;
    long console_last_modified;
};

static struct gui_vis_sig last_gui_sig;
static int gui_sig_initialized = 0;
static int gui_splash_expire = 0;
static int gui_splash_sec = 0;
static int gui_helper_due = 0;
static int alt_helper_drawn = 0;

void gui_maintenance_tick(void)
{
    int now = get_tick_count();
    if (gui_splash > 0)
    {
        if (gui_splash_expire == 0)
            gui_splash_expire = now + (SPLASH_TIME * 80);
        if (kbd_is_key_pressed(KEY_SHOOT_HALF) || (now >= gui_splash_expire))
        {
            gui_splash = 0;
            gui_splash_expire = 0;
            gui_splash_sec = 0;
            if (camera_info.state.gui_mode_none || camera_info.state.gui_mode_alt)
                gui_set_need_restore();
            if (logo) logo = NULL;
        }
        else
        {
            int sec = (gui_splash_expire - now + 999) / 1000;
            if (sec <= 0) sec = 1;
            gui_splash_sec = sec;
        }
    }
    else
    {
        gui_splash_sec = 0;
    }

    if (camera_info.state.gui_mode_alt && conf.show_alt_helper)
        gui_helper_due = (now >= gui_helper_displayat);
    else
        gui_helper_due = 0;

    if (console_displayed && !camera_info.state.state_kbd_script_run)
    {
        if (now > console_last_modified + (conf.console_timeout * 1000))
        {
            gui_set_need_restore();
            console_displayed = 0;
        }
    }
}

static gui_handler *gui_mode = NULL;

int gui_check_state_changed(void)
{
    int is_menu_active = (camera_info.state.gui_mode == GUI_MODE_MENU);
    (void)is_menu_active;
    int menu_dirty = 0;
    int dirty = gui_osd_need_restore || gui_mode_need_redraw || menu_dirty;

    struct gui_vis_sig current_sig;
    memset(&current_sig, 0, sizeof(current_sig));
    current_sig.mode_ptr = (void*)gui_mode;
    current_sig.gui_mode = camera_info.state.gui_mode;
    current_sig.helper_due = gui_helper_due;
    current_sig.splash_sec = gui_splash_sec;
    current_sig.menu_item = 0;
    current_sig.debug_shortcut_action = conf.debug_shortcut_action;
    current_sig.dng_raw = conf.dng_raw;
    current_sig.enable_shortcuts = conf.enable_shortcuts;
    current_sig.hide_osd = conf.hide_osd;
    current_sig.menu_color = conf.menu_color;
    current_sig.menu_title_color = conf.menu_title_color;
    current_sig.override_disable = conf.override_disable;
    current_sig.save_raw = conf.save_raw;
    current_sig.show_alt_helper = conf.show_alt_helper;
    current_sig.show_alt_helper_delay = conf.show_alt_helper_delay;
    current_sig.show_histo = conf.show_histo;
    current_sig.show_osd = conf.show_osd;
    current_sig.subj_dist_override_koef = conf.subj_dist_override_koef;
    current_sig.user_menu_as_root = conf.user_menu_as_root;
    current_sig.user_menu_enable = conf.user_menu_enable;
    current_sig.zebra_draw = conf.zebra_draw;
    current_sig.console_displayed = console_displayed;
    current_sig.console_last_modified = console_last_modified;

    int sig_changed = 0;
    if (!gui_sig_initialized)
    {
        gui_sig_initialized = 1;
        sig_changed = 1;
    }
    else if (memcmp(&last_gui_sig, &current_sig, sizeof(struct gui_vis_sig)) != 0)
    {
        sig_changed = 1;
    }

    if (sig_changed)
        alt_helper_drawn = 0;

    last_gui_sig = current_sig;
    return dirty || sig_changed;
}

// Mock time for gui_osd_draw_clock
static struct tm mock_tm = { .tm_hour = 12, .tm_min = 34, .tm_sec = 0 };
struct tm *get_mock_localtime(void) { return &mock_tm; }

static int clock_draw_count = 0;
static int last_drawn_clock_sec = -1;
static int osd_draw_count = 0;
static int half_shutter_osd_drawn = 0;

void gui_osd_draw_clock(void)
{
    struct tm *ttm = get_mock_localtime();
    clock_draw_count++;
    last_drawn_clock_sec = ttm->tm_sec;
}

void gui_draw_osd(void)
{
    gui_osd_draw_clock();
    if (camera_info.state.is_shutter_half_press)
        half_shutter_osd_drawn++;
}

static void gui_default_draw(int force_redraw)
{
    osd_draw_count++;
    gui_draw_osd();
}

static int alt_draw_count = 0;
static void gui_chdk_draw(int force_redraw)
{
    alt_draw_count++;
    if (force_redraw || !draw_test_guard() || !alt_helper_drawn)
    {
        g3x_fill_menu_opaque_black();
        alt_helper_drawn = 1;
    }
}

static int module_draw_count = 0;
static void gui_module_draw(int force_redraw)
{
    module_draw_count++;
}

gui_handler defaultGuiHandler = { GUI_MODE_NONE, gui_default_draw, NULL };
gui_handler altGuiHandler     = { GUI_MODE_ALT,  gui_chdk_draw,    NULL };
gui_handler moduleGuiHandler  = { GUI_MODE_MODULE, gui_module_draw, NULL };

int gui_is_osd_mode(void)
{
    return (camera_info.state.gui_mode == GUI_MODE_NONE);
}

void gui_draw_osd_tick(void)
{
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(0);
}

int gui_is_module_mode(void)
{
    return (camera_info.state.gui_mode > GUI_MODE_MENU);
}

void gui_draw_module_tick(void)
{
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(0);
}

void gui_redraw(int forced)
{
    if (!draw_test_guard() && (!camera_info.state.gui_mode_none || gui_splash))
    {
        draw_set_guard();
        forced = 1;
    }
    if (gui_osd_need_restore)
    {
        draw_restore();
        gui_osd_need_restore = 0;
        forced = 1;
    }
    if (gui_mode_need_redraw)
    {
        gui_mode_need_redraw = 0;
        forced = 1;
    }
    if (gui_mode && gui_mode->redraw)
        gui_mode->redraw(forced);
}

void step_main_tick(void)
{
    mock_tick += 20;
    gui_maintenance_tick();
    int forced = check_gui_needs_redraw();
    int sentinel_lost = !draw_test_guard();
    int buffer_changed = check_bitmap_buffer_changed();
    int state_changed = gui_check_state_changed();
    int need_redraw = forced || sentinel_lost || buffer_changed || state_changed;
    if (need_redraw)
        gui_redraw(forced || sentinel_lost || buffer_changed);
    else if (gui_is_osd_mode())
        gui_draw_osd_tick();
    else if (gui_is_module_mode())
        gui_draw_module_tick();
}

int main(void)
{
    // Step 1: Boot with splash screen in GUI_MODE_NONE
    camera_info.state.gui_mode = GUI_MODE_NONE;
    camera_info.state.gui_mode_none = 1;
    camera_info.state.gui_mode_alt = 0;
    gui_mode = &defaultGuiHandler;
    gui_splash = SPLASH_TIME;
    mock_tick = 1000;

    // Splash initiation tick
    step_main_tick();
    assert(gui_splash > 0);

    // Fast-forward mock_tick past splash expiry (SPLASH_TIME * 80 ms = 3200 ms)
    mock_tick = 5000;
    // Splash expiry tick: should trigger draw_restore() to clear splash logo
    step_main_tick();
    assert(gui_splash == 0);
    assert(draw_restore_count == 1); // Splash logo erased

    // Reset counters to cleanly measure post-splash steady state
    clock_draw_count = 0;
    last_drawn_clock_sec = -1;
    osd_draw_count = 0;
    half_shutter_osd_drawn = 0;
    opaque_black_fill_count = 0;
    draw_restore_count = 0;

    // Verify post-splash steady state: intact sentinel, unchanged signature
    assert(draw_test_guard() == 1);
    assert(gui_check_state_changed() == 0);

    // Requirement 4(a): With unchanged signature and intact sentinel,
    // a change in the clock second leads to a clock draw with NO opaque fill or full erase
    mock_tm.tm_sec = 42;
    step_main_tick();

    assert(gui_check_state_changed() == 0); // Signature remains unchanged!
    assert(clock_draw_count == 1);          // Clock was drawn!
    assert(last_drawn_clock_sec == 42);     // Clock drew the updated second!
    assert(opaque_black_fill_count == 0);   // ZERO opaque fill!
    assert(draw_restore_count == 0);        // ZERO full-panel erase!

    // Advance clock second again
    mock_tm.tm_sec = 43;
    step_main_tick();
    assert(gui_check_state_changed() == 0);
    assert(clock_draw_count == 2);
    assert(last_drawn_clock_sec == 43);
    assert(opaque_black_fill_count == 0);
    assert(draw_restore_count == 0);

    // Requirement 4(b): A half-shutter state change in NORMAL mode leads to an OSD draw
    camera_info.state.is_shutter_half_press = 1;
    step_main_tick();

    assert(osd_draw_count == 3);
    assert(half_shutter_osd_drawn == 1);  // Half-shutter element rendered!
    assert(opaque_black_fill_count == 0); // Still NO opaque fill!
    assert(draw_restore_count == 0);      // Still NO full erase!

    // Release half-shutter
    camera_info.state.is_shutter_half_press = 0;
    step_main_tick();
    assert(osd_draw_count == 4);
    assert(half_shutter_osd_drawn == 1); // Not incremented when released
    assert(opaque_black_fill_count == 0);
    assert(draw_restore_count == 0);

    // Requirement 4(c): ALT/menu no-forced-redraw and module-mode tests pass
    // Switch to ALT mode
    camera_info.state.gui_mode = GUI_MODE_ALT;
    camera_info.state.gui_mode_none = 0;
    camera_info.state.gui_mode_alt = 1;
    gui_mode = &altGuiHandler;
    alt_draw_count = 0;

    // Entry into ALT mode: triggers redraw due to mode change
    step_main_tick();
    assert(alt_draw_count == 1);
    assert(opaque_black_fill_count == 1); // Initial opaque black fill on ALT entry

    // Run 50 ticks in ALT mode with unchanged state
    for (int i = 0; i < 50; i++)
        step_main_tick();

    // In ALT mode, no per-tick redraw occurs: draw count and opaque fill stay at 1!
    assert(alt_draw_count == 1);
    assert(opaque_black_fill_count == 1);

    // Switch to MODULE mode
    camera_info.state.gui_mode = GUI_MODE_MODULE;
    camera_info.state.gui_mode_none = 0;
    camera_info.state.gui_mode_alt = 0;
    gui_mode = &moduleGuiHandler;
    module_draw_count = 0;

    // Run 20 ticks in MODULE mode: dispatches draw handler every tick without opaque fill
    for (int i = 0; i < 20; i++)
        step_main_tick();

    assert(module_draw_count == 20);      // Dispatched every tick
    assert(opaque_black_fill_count == 1); // ZERO additional opaque fills

    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_file = Path(tmpdir) / "test_normal_osd_tick.c"
            bin_file = Path(tmpdir) / "test_normal_osd_tick"
            c_file.write_text(harness_c, encoding="utf-8")
            comp = subprocess.run(
                ["gcc", "-O2", "-Wall", str(c_file), "-o", str(bin_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(comp.returncode, 0, f"Compilation failed: {comp.stderr}")
            run = subprocess.run([str(bin_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run.returncode, 0, f"Execution failed: {run.stderr}")

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
        if not diskboot.is_file() or diskboot.stat().st_size != 124257:
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
        self.assertEqual(diskboot.stat().st_size, 124257)
        self.assertEqual(
            sha256_file(diskboot),
            "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738",
        )

        # Check manifests
        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 124257)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738",
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
            self.assertEqual(s1["DISKBOOT.BIN"][0], 124257)
            self.assertEqual(
                s1["DISKBOOT.BIN"][1],
                "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738",
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
            self.assertEqual(s3["DISKBOOT.BIN"][0], 124321)
            self.assertEqual(
                s3["DISKBOOT.BIN"][1],
                "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb",
            )
            # Compare DISKBOOT.BIN plus every CHDK/ file hash
            self.assertEqual(s3, s4, "Two clean G3X_GUI_FIX=1 FULL_HOOKS=1 builds produced different hashes")

    def test_gui_fix_full_hooks_build_artifacts_and_manifest(self):
        """Verify G3X_GUI_FIX=1 FULL_HOOKS=1 build produces exact manifest matches."""
        self._require_toolchain()

        diskboot = OUT_DIR_GUI_HOOKS / "DISKBOOT.BIN"
        if not diskboot.is_file() or diskboot.stat().st_size != 124281:
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

        self.assertEqual(diskboot.stat().st_size, 124321)
        self.assertEqual(
            sha256_file(diskboot),
            "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb",
        )

        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_fix_full_hooks_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected {mpath} to exist")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], 124321)
            self.assertEqual(
                data["artifacts"]["DISKBOOT.BIN"]["sha256"],
                "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb",
            )
            self.assertIn("FULL_HOOKS=1", data["build"]["flags"])
            self.assertIn("G3X_GUI_FIX=1", data["build"]["flags"])
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
