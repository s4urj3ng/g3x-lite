"""Host-side and build verification tests for PORT-47 (G3X_GUI_DIAG=1)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
KBD_HEADER = ROOT / "chdk-port/platform/g3x/kbd_check.h"
OVERDRAW_DOC = ROOT / "docs/PORT47_OVERDRAW.md"
TRIAL_DOC = ROOT / "docs/PORT47_TRIAL.md"
MANIFEST = ROOT / "manifests/port47_gui_diag_manifest.json"
ROLLBACK_MANIFEST = ROOT / "manifests/port46_kbd_check_manifest.json"
OUT = ROOT / "out/port47-test"
NM = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


class TestPort47FlagGating(unittest.TestCase):
    def test_preprocessor_and_makefile_reject_missing_layered_flags(self) -> None:
        """G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1."""
        missing_combos = [
            [],
            ["-DG3X_GUI_DBUF=1"],
            ["-DG3X_GUI_DBUF=1", "-DG3X_GUI_NOOVERDRAW=1"],
            ["-DG3X_GUI_DBUF=1", "-DG3X_KBD_CHECK=1"],
            ["-DG3X_GUI_NOOVERDRAW=1", "-DG3X_KBD_CHECK=1"],
        ]
        for extra in missing_combos:
            with self.subTest(cc_flags=extra):
                res = subprocess.run(
                    ["cc", "-E", "-DG3X_GUI_DIAG=1", *extra, "-x", "c", str(DIAG_HEADER)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(
                    "G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1",
                    res.stderr,
                )

        make_missing = [
            ["G3X_GUI_DIAG=1"],
            ["G3X_GUI_DIAG=1", "G3X_GUI_DBUF=1"],
            ["G3X_GUI_DIAG=1", "G3X_GUI_DBUF=1", "G3X_GUI_NOOVERDRAW=1"],
            ["G3X_GUI_DIAG=1", "G3X_GUI_DBUF=1", "G3X_KBD_CHECK=1"],
        ]
        for make_args in make_missing:
            with self.subTest(make_args=make_args):
                res = subprocess.run(
                    ["make", "-f", "chdk-port/platform/g3x/Makefile", *make_args],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(
                    "G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1",
                    res.stderr,
                )

    def test_default_build_without_flags_stays_byte_identical_to_origin_main(self) -> None:
        """Default build (no flags) and candidate_port2a remain byte-identical to origin/main."""
        res_build = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools/build_candidate_port2a.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_build.returncode, 0, res_build.stdout + res_build.stderr)

        res_val = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools/validate_candidate_port2a.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_val.returncode, 0, res_val.stdout + res_val.stderr)

        prod_diskboot = ROOT / "chdk-port/bin/DISKBOOT.BIN"
        self.assertEqual(
            sha256_file(prod_diskboot),
            "3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72",
        )

        # Also verify default scripts/build_port43_dbuf.py (no opt-in flags) is byte-identical to origin/main
        default_out = OUT / "default-no-flags"
        env = os.environ.copy()
        for flag in ["G3X_GUI_FIX", "G3X_GUI_DBUF", "G3X_GUI_NOOVERDRAW", "G3X_KBD_CHECK", "G3X_GUI_DIAG", "FULL_HOOKS", "MAKEFLAGS"]:
            env.pop(flag, None)
        env["MAKEFLAGS"] = f"CC={ROOT / 'scripts/gcc_deterministic_wrapper.sh'}"
        res_def = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--out-dir",
                str(default_out),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_def.returncode, 0, res_def.stdout + res_def.stderr)
        pinned_default = json.loads((ROOT / "manifests/port43_gui_dbuf_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            sha256_file(default_out / "DISKBOOT.BIN"),
            pinned_default["artifacts"]["DISKBOOT.BIN"]["sha256"],
        )


class TestPort47HostDiagnosticsAndRestore(unittest.TestCase):
    def test_counter_line_formatting_layout_retry_restore_and_suppression(self) -> None:
        """Compile and run gui_diag.h on host to verify (a), (b), (c), and (d)."""
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define G3X_GUI_DBUF 1
#define G3X_GUI_NOOVERDRAW 1
#define G3X_KBD_CHECK 1
#define G3X_GUI_DIAG 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1

#define FONT_WIDTH 16
#define FONT_HEIGHT 32
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define MAKE_COLOR(bg, fg) (((bg) << 8) | (fg))

struct {
    struct {
        int gui_mode_none;
        int gui_mode_alt;
    } state;
} camera_info = {{1, 0}};

struct {
    int width;
    int height;
    int buffer_width;
} camera_screen = {900, 600, 928};

int active_bitmap_buffer = 0;

/* Controllable allocator stubs for Requirement (b) */
static int allow_malloc = 0;
static int allow_umalloc = 0;
static int malloc_calls = 0;
static int umalloc_calls = 0;
static unsigned char backing_shadow[1520640];

static void *test_malloc(size_t sz)
{
    assert(sz == 1520640u);
    malloc_calls++;
    if (!allow_malloc)
        return NULL;
    return backing_shadow;
}

static void *test_umalloc(size_t sz)
{
    assert(sz == 1520640u);
    umalloc_calls++;
    if (!allow_umalloc)
        return NULL;
    return backing_shadow;
}

#define malloc test_malloc
#define umalloc test_umalloc

/* Shadow state and restore/redraw tracking for Requirement (c) */
static unsigned char *shadow_bm = 0;
static unsigned char *shadow_op = 0;
static int shadow_valid = 0;
static int shadow_attempted = 0;

static int guard_intact = 1;
static int blit_restore_calls = 0;
static int full_redraw_calls = 0;
static int last_redraw_arg = -1;

int draw_test_guard(void)
{
    return guard_intact;
}

int g3x_dbuf_shadow_is_allocated(void)
{
    return (shadow_bm != 0 && shadow_op != 0);
}

static int draw_calls = 0;
static int last_draw_x = -1;
static int last_draw_y = -1;
static int last_draw_color = -1;
static char last_draw_line[128];

static void draw_string(int x, int y, const char *s, int color)
{
    /* Must fit strictly inside the 880x576 layout box: x in [10, 889], y in [12, 587] */
    int len = (int)strlen(s);
    int px_w = len * FONT_WIDTH;
    int px_h = FONT_HEIGHT;
    assert(len == 51);
    assert(x == 42 && y == 536);
    assert((x & 1) == 0);
    assert(x >= 10 && (x + px_w) <= 890);
    assert(y >= 12 && (y + px_h) <= 588);
    /* Must not overlap kbd_check line at y = 504..535 or <ALT> title at y = 568..599 */
    assert(y >= 504 + FONT_HEIGHT);
    assert(y + FONT_HEIGHT <= 568);
    assert(color == MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
    strcpy(last_draw_line, s);
    last_draw_x = x;
    last_draw_y = y;
    last_draw_color = color;
    draw_calls++;
}

#include "gui_diag.h"

void g3x_dbuf_shadow_ensure_allocated(void)
{
    g3x_diag_shadow_ensure_allocated(&shadow_bm, &shadow_op, &shadow_valid, &shadow_attempted);
}

int g3x_dbuf_shadow_restore(void)
{
    if (!shadow_bm || !shadow_op || camera_info.state.gui_mode_none)
        return 0;
    blit_restore_calls++;
    guard_intact = 1;
    g3x_diag_record_shadow_restore();
    return 1;
}

void gui_redraw(int flag_gui_enforce_redraw)
{
    full_redraw_calls++;
    last_redraw_arg = flag_gui_enforce_redraw;
    guard_intact = 1;
}

int main(void)
{
    /* 1. Boot state: nothing allocated at boot, suppression disengaged, no draws when ALT off */
    assert(malloc_calls == 0 && umalloc_calls == 0);
    assert(!g3x_dbuf_shadow_is_allocated());
    assert(g3x_diag_suppress_engaged == 0);
    gui_diag_draw();
    assert(draw_calls == 0);

    /* Buffer switches outside ALT do not trigger suppression mechanism */
    active_bitmap_buffer = 1;
    assert(g3x_diag_check_suppress() == 0);
    assert(g3x_diag_suppress_hit_count == 0);

    /* 2. ALT Entry #1 with failing malloc + umalloc -> shadow stays NULL */
    allow_malloc = 0;
    allow_umalloc = 0;
    camera_info.state.gui_mode_none = 0;
    camera_info.state.gui_mode_alt = 1;
    g3x_diag_on_alt_enter();
    assert(malloc_calls == 1 && umalloc_calls == 1);
    assert(!g3x_dbuf_shadow_is_allocated());
    assert(g3x_diag_suppress_engaged == 1);
    assert(g3x_diag_last_bitmap_buffer == 1);

    gui_diag_draw();
    assert(draw_calls == 1);
    assert(strcmp(last_draw_line, "H:1/0000 S:NULL/1520640 L:0000 R:0000 F:0000 M:0000") == 0);

    /* 3. Restore branch when shadow is NULL -> full redraw ONLY, increments full-redraw counter */
    guard_intact = 0; /* simulate sentinel loss */
    int used_full = g3x_diag_restore_overlay(0);
    assert(used_full == 1);
    assert(blit_restore_calls == 0);
    assert(full_redraw_calls == 1 && last_redraw_arg == 1);
    assert(g3x_diag_sentinel_loss_count == 1);
    assert(g3x_diag_shadow_restore_count == 0);
    assert(g3x_diag_full_redraw_count == 1);
    assert(g3x_diag_hook_hits == 1);

    gui_diag_draw();
    assert(strcmp(last_draw_line, "H:1/0001 S:NULL/1520640 L:0001 R:0000 F:0001 M:0000") == 0);

    /* Exit ALT -> releases suppression mechanism cleanly */
    camera_info.state.gui_mode_alt = 0;
    camera_info.state.gui_mode_none = 1;
    g3x_diag_on_alt_leave();
    assert(g3x_diag_suppress_engaged == 0);
    assert(g3x_diag_last_bitmap_buffer == -1);
    active_bitmap_buffer = 0;
    assert(g3x_diag_check_suppress() == 0);
    assert(g3x_diag_suppress_hit_count == 0);

    /* 4. ALT Entry #2: retry allocation when shadow was NULL; umalloc succeeds! */
    allow_malloc = 0;
    allow_umalloc = 1;
    memset(backing_shadow, 0xAA, sizeof(backing_shadow));
    camera_info.state.gui_mode_none = 0;
    camera_info.state.gui_mode_alt = 1;
    g3x_diag_on_alt_enter();
    assert(malloc_calls == 2 && umalloc_calls == 2);
    assert(g3x_dbuf_shadow_is_allocated());
    assert(shadow_bm == backing_shadow);
    assert(shadow_op == backing_shadow + (880 * 576 * 2));
    assert(backing_shadow[0] == 0 && backing_shadow[1520639] == 0);

    gui_diag_draw();
    assert(strcmp(last_draw_line, "H:1/0001 S:OK/1520640   L:0001 R:0000 F:0001 M:0000") == 0);

    /* 5. Subsequent ALT Entry #3: already allocated -> does not re-allocate */
    g3x_diag_on_alt_leave();
    g3x_diag_on_alt_enter();
    assert(malloc_calls == 2 && umalloc_calls == 2);
    assert(g3x_dbuf_shadow_is_allocated());

    /* 6. Restore branch while shadow exists (non-NULL):
     *    Uses ONLY single fast blit; gui_redraw is NEVER called, even if shadow_valid is 0! */
    shadow_valid = 0;
    active_bitmap_buffer = 1; /* buffer switch while ALT engaged */
    int sup = g3x_diag_check_suppress();
    assert(sup == 1);
    assert(g3x_diag_suppress_hit_count == 1);

    guard_intact = 0; /* also lose sentinel */
    used_full = g3x_diag_restore_overlay(sup);
    assert(used_full == 0);
    assert(blit_restore_calls == 1);
    assert(full_redraw_calls == 1); /* UNCHANGED: gui_redraw was NOT called! */
    assert(g3x_diag_shadow_restore_count == 1);
    assert(g3x_diag_full_redraw_count == 1); /* UNCHANGED */
    assert(g3x_diag_sentinel_loss_count == 2);
    assert(g3x_diag_hook_hits == 2);

    gui_diag_draw();
    assert(strcmp(last_draw_line, "H:1/0002 S:OK/1520640   L:0002 R:0001 F:0001 M:0001") == 0);

    /* 7. Test hook_installed = 0 formatting */
    g3x_diag_set_hook_installed(0);
    gui_diag_draw();
    assert(strcmp(last_draw_line, "H:0/0002 S:OK/1520640   L:0002 R:0001 F:0001 M:0001") == 0);

    return 0;
}
'''
        OUT.mkdir(parents=True, exist_ok=True)
        OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUT) as td:
            cfile = Path(td) / "test_diag.c"
            exe = Path(td) / "test_diag"
            cfile.write_text(source, encoding="utf-8")
            res = subprocess.run(
                [
                    "cc",
                    "-std=c99",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-fstack-protector-all",
                    "-I",
                    str(DIAG_HEADER.parent),
                    str(cfile),
                    "-o",
                    str(exe),
                ],
                env={**os.environ, "TMPDIR": str(td)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


class TestPort47DocsAndAdaptedAddresses(unittest.TestCase):
    def test_overdraw_doc_has_single_chosen_mechanism_and_adapted_addresses(self) -> None:
        text = OVERDRAW_DOC.read_text(encoding="utf-8")
        self.assertIn("## Adapted addresses (`G3X_GUI_DIAG=1`)", text)

        # Main mechanism table must have exactly one row marked chosen=yes
        main_table_Section = text.split("## Adapted addresses")[0]
        yes_rows = [
            line for line in main_table_Section.splitlines()
            if line.startswith("|") and line.rstrip().endswith("| yes |")
        ]
        self.assertEqual(len(yes_rows), 1)
        self.assertIn("check_gui_needs_redraw", yes_rows[0])
        self.assertIn("chdk-port/platform/g5x/lib.c:206", yes_rows[0])
        self.assertIn("0x0000D2A4", yes_rows[0])

        # Verify adapted addresses against FINSIG stubs_entry.S
        finsig_stubs = (ROOT / "reference/finsig_gm110c/stubs_entry.S").read_text(encoding="utf-8")
        self.assertIn("DEF(active_bitmap_buffer              ,0x0000d2a4)", finsig_stubs)
        self.assertIn("DEF(bitmap_buffer                     ,0x0000d2a8)", finsig_stubs)
        self.assertIn("NHSTUB(AllocateUncacheableMemory              ,0xfc144471)", finsig_stubs)

        adapted_section = text.split("## Adapted addresses (`G3X_GUI_DIAG=1`)")[1]
        for expected_token in [
            "0x0000D2A4",
            "0x0000D2A8",
            "0xFC144471",
            "FINSIG",
            "chdk-port/platform/g5x/lib.c:206",
            "chdk-port/platform/g5x/platform_camera.h:85",
        ]:
            self.assertIn(expected_token, adapted_section)

    def test_trial_doc_covers_required_steps_recovery_and_rollback(self) -> None:
        text = TRIAL_DOC.read_text(encoding="utf-8")
        pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rollback = json.loads(ROLLBACK_MANIFEST.read_text(encoding="utf-8"))
        rollback_hash = rollback["variants"]["no-overdraw"]["artifacts"]["DISKBOOT.BIN"]["sha256"]
        self.assertTrue(rollback_hash.startswith("7c91eaa6"))

        self.assertIn(pinned["artifacts"]["DISKBOOT.BIN"]["sha256"], text)
        self.assertIn(rollback_hash, text)
        self.assertIn("held press", text.lower())
        self.assertIn("short press", text.lower())
        self.assertIn("at rest", text.lower())
        self.assertIn("panning", text.lower())
        self.assertIn("half-press", text.lower())
        self.assertIn("battery", text.lower())
        self.assertIn("- [ ]", text)


class TestPort47CandidateBuildAndManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        cls.build_a = OUT / "diag-a"
        cls.build_b = OUT / "diag-b"
        for build_dir in (cls.build_a, cls.build_b):
            env = os.environ.copy()
            for flag in ["G3X_GUI_FIX", "G3X_GUI_DBUF", "G3X_GUI_NOOVERDRAW", "G3X_KBD_CHECK", "G3X_GUI_DIAG", "FULL_HOOKS", "MAKEFLAGS"]:
                env.pop(flag, None)
            env["G3X_GUI_DBUF"] = "1"
            env["G3X_GUI_NOOVERDRAW"] = "1"
            env["G3X_KBD_CHECK"] = "1"
            env["G3X_GUI_DIAG"] = "1"
            env["MAKEFLAGS"] = f"CC={ROOT / 'scripts/gcc_deterministic_wrapper.sh'}"
            with (OUT / f"{build_dir.name}.log").open("w") as log:
                subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(ROOT / "scripts/build_port43_dbuf.py"),
                        "--no-overdraw",
                        "--kbd-check",
                        "--gui-diag",
                        "--out-dir",
                        str(build_dir),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )

    def test_two_clean_builds_are_byte_identical_and_match_manifest(self) -> None:
        pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))
        generated_a = json.loads((self.build_a / "port47_gui_diag_manifest.json").read_text(encoding="utf-8"))
        generated_b = json.loads((self.build_b / "port47_gui_diag_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(generated_a, pinned)
        self.assertEqual(generated_b, pinned)

        for required_flag in [
            "G3X_GUI_DBUF=1",
            "G3X_GUI_NOOVERDRAW=1",
            "G3X_KBD_CHECK=1",
            "G3X_GUI_DIAG=1",
        ]:
            self.assertIn(required_flag, pinned["build"]["flags"])

        snap_a = distribution_snapshot(self.build_a)
        snap_b = distribution_snapshot(self.build_b)
        self.assertEqual(snap_a, snap_b)

        expected = dict(pinned["artifacts"]["chdk_files"])
        expected["DISKBOOT.BIN"] = {
            "size": pinned["artifacts"]["DISKBOOT.BIN"]["size"],
            "sha256": pinned["artifacts"]["DISKBOOT.BIN"]["sha256"],
        }
        self.assertEqual(snap_a, expected)
        self.assertEqual(pinned["artifacts"]["chdk_files_count"], 242)
        self.assertEqual(pinned["artifacts"]["modules_count"], 34)

        for rel in snap_a:
            self.assertEqual(
                (self.build_a / rel).read_bytes(),
                (self.build_b / rel).read_bytes(),
                rel,
            )

    def test_elf_symbols_and_core_end_guard(self) -> None:
        pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))
        elf = self.build_a / "stage_chdk/platform/g3x/sub/110c/main.elf"
        symbols = subprocess.check_output([str(NM), "-S", str(elf)], text=True)
        end_match = re.search(r"^([0-9a-f]+) B _end$", symbols, re.M)
        self.assertIsNotNone(end_match)
        end_addr = int(end_match.group(1), 16)
        self.assertLessEqual(end_addr, 0x003687B0 + 65536)
        self.assertEqual(f"0x{end_addr:08x}", pinned["core_end"])
        self.assertEqual(f"0x{end_addr:08x}", pinned["_end"])

        for sym in [
            "gui_kbd_check_draw",
            "gui_diag_draw",
            "g3x_diag_on_alt_enter",
            "g3x_diag_on_alt_leave",
            "g3x_diag_check_suppress",
            "g3x_diag_restore_overlay",
            "g3x_diag_shadow_ensure_allocated",
        ]:
            self.assertRegex(symbols, rf" T {sym}\b")

        # Ensure staging/seed directories never retain prototype files that break shorthand uniqueness tests
        out_root = ROOT / "out"
        for proto_name in ("boot_prototype.c", "stubs_prototype.S"):
            self.assertEqual(list(out_root.rglob(proto_name)), [])


if __name__ == "__main__":
    unittest.main()
