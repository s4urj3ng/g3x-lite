"""Offline unit and integration tests for PORT-51a (G3X_GUI_RESTORE2=1)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
SYNC_HEADER = ROOT / "chdk-port/platform/g3x/sub/110c/gui_sync.h"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
SUB_MAKEFILE = ROOT / "chdk-port/platform/g3x/sub/110c/Makefile"
BUILD_SCRIPT = ROOT / "scripts/build_port43_dbuf.py"
MANIFEST_P50 = ROOT / "manifests/port50_gui_menu_manifest.json"
MANIFEST_P51 = ROOT / "out/port51-restore2-core/port51_restore2_core_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

BASE_CANONICAL_DISKBOOT_SHA256 = "3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72"
BASE_CANONICAL_DISKBOOT_SIZE = 116073

BASE_PORT50_CANDIDATE_SHA256 = "c5cd59f05c026e540681039a8184bcedb5718030d4d108db8e6e7c5cefcf4480"
BASE_PORT50_CANDIDATE_SIZE = 130745

BASE_PORT50_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_PORT50_DEFAULT_SIZE = 124097

BASE_PORT51_RESTORE2_SHA256 = "4fad35b503be9f0a0ed799cf4cd62721db61e8dc6fa0ba348a507e52937d622a"
BASE_PORT51_RESTORE2_SIZE = 131929


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort51FlagPlumbing(unittest.TestCase):
    def test_flag_plumbing_rejects_missing_prerequisites_and_accepts_full_stack(self):
        required = [
            "G3X_GUI_MENU",
            "G3X_GUI_SYNC",
            "G3X_GUI_DBUF",
            "G3X_GUI_NOOVERDRAW",
            "G3X_KBD_CHECK",
            "G3X_GUI_DIAG",
            "G3X_GUI_SHADOW2",
        ]
        for missing in required:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_GUI_RESTORE2=1"] + [
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
                        "G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

                make_args = ["G3X_GUI_RESTORE2=1"] + [
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
                        "G3X_GUI_RESTORE2=1 requires G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

        full_c_flags = ["-DG3X_GUI_RESTORE2=1"] + [f"-D{f}=1" for f in required]
        for hdr in (DIAG_HEADER, SYNC_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)


class TestPort51PureRectLogic(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.bin_path = Path(self.tmp_dir.name) / "test_rect"
        c_src = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#define G3X_GUI_DBUF 1
#define G3X_GUI_NOOVERDRAW 1
#define G3X_KBD_CHECK 1
#define G3X_GUI_DIAG 1
#define G3X_GUI_SHADOW2 1
#define G3X_GUI_SYNC 1
#define G3X_GUI_MENU 1
#define G3X_GUI_RESTORE2 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#define MEMINFO_H 1

#define FONT_WIDTH 16
#define FONT_HEIGHT 32
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define MAKE_COLOR(bg, fg) (((bg) << 8) | (fg))

typedef short coord;
typedef unsigned short color;
typedef struct {
    int free_block_max_size;
} cam_meminfo;

struct {
    struct {
        int gui_mode_none;
        int gui_mode_alt;
        int osd_title_line;
    } state;
} camera_info;

struct {
    int width;
    int height;
    int buffer_width;
    int disp_left;
    int disp_width;
} camera_screen = {900, 600, 928, 0, 900};

int active_bitmap_buffer = 0;
char *bitmap_buffer[2] = {0, 0};
volatile char *opacity_buffer[2] = {0, 0};

int draw_test_guard(void) { return 1; }
int g3x_dbuf_shadow_is_allocated(void) { return 1; }
void g3x_dbuf_shadow_ensure_allocated(void) {}
int g3x_dbuf_shadow_restore(void) { return 1; }
int g3x_dbuf_shadow_sync_restore(unsigned int target_idx) { (void)target_idx; return 1; }
long get_tick_count(void) { return 0; }
void gui_redraw(int f) { (void)f; }
void GetMemInfo(cam_meminfo *info) { (void)info; }
void *exmem_alloc_cached(unsigned int a, unsigned int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; return 0; }
void *umalloc(size_t s) { return malloc(s); }
void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl) { (void)x1; (void)y1; (void)x2; (void)y2; (void)cl; }
void draw_set_guard(void) {}
void draw_string(int x, int y, const char *s, int c) { (void)x; (void)y; (void)s; (void)c; }

#include "gui_diag.h"

int main(void)
{
    int clip_x0 = 10, clip_y0 = 12, clip_x1 = 889, clip_y1 = 587;

    /* 1. NULL pointer rejection */
    assert(g3x_rect_clip(NULL, &clip_y0, &clip_x1, &clip_y1, 10, 12, 889, 587) == 0);
    assert(g3x_rect_union(NULL, &clip_y0, &clip_x1, &clip_y1, &clip_x0, 0, 0, 10, 10, 10, 12, 889, 587) == 0);

    /* 2. Empty / completely out-of-bounds rect */
    int x0 = -50, y0 = -20, x1 = 5, y1 = 9;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 0);

    int cur_x0 = 0, cur_y0 = 0, cur_x1 = 0, cur_y1 = 0, cur_valid = 0;
    assert(g3x_rect_union(&cur_x0, &cur_y0, &cur_x1, &cur_y1, &cur_valid,
                          -50, -20, 5, 9, clip_x0, clip_y0, clip_x1, clip_y1) == 0);
    assert(cur_valid == 0);

    /* Inverted coords are normalised */
    x0 = 50; y0 = 60; x1 = 20; y1 = 30;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(x0 == 20 && y0 == 30 && x1 == 50 && y1 == 60);

    /* 3. Single rectangle completely inside bounds */
    x0 = 100; y0 = 150; x1 = 300; y1 = 400;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(x0 == 100 && y0 == 150 && x1 == 300 && y1 == 400);

    assert(g3x_rect_union(&cur_x0, &cur_y0, &cur_x1, &cur_y1, &cur_valid,
                          100, 150, 300, 400, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(cur_valid == 1);
    assert(cur_x0 == 100 && cur_y0 == 150 && cur_x1 == 300 && cur_y1 == 400);

    /* 4. Union of multiple rectangles */
    /* Add a disjoint rect to top-left of previous: [50, 60, 80, 90] */
    assert(g3x_rect_union(&cur_x0, &cur_y0, &cur_x1, &cur_y1, &cur_valid,
                          50, 60, 80, 90, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(cur_valid == 1);
    assert(cur_x0 == 50 && cur_y0 == 60 && cur_x1 == 300 && cur_y1 == 400);

    /* Add an overlapping rect to bottom-right: [250, 350, 500, 450] */
    assert(g3x_rect_union(&cur_x0, &cur_y0, &cur_x1, &cur_y1, &cur_valid,
                          250, 350, 500, 450, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(cur_x0 == 50 && cur_y0 == 60 && cur_x1 == 500 && cur_y1 == 450);

    /* 5. Out-of-bounds clipping */
    x0 = 0; y0 = 0; x1 = 50; y1 = 50;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(x0 == 10 && y0 == 12 && x1 == 50 && y1 == 50);

    x0 = 800; y0 = 550; x1 = 950; y1 = 650;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(x0 == 800 && y0 == 550 && x1 == 889 && y1 == 587);

    /* 6. Full-screen rectangle clipped to active menu bounds */
    x0 = 0; y0 = 0; x1 = 927; y1 = 599;
    assert(g3x_rect_clip(&x0, &y0, &x1, &y1, clip_x0, clip_y0, clip_x1, clip_y1) == 1);
    assert(x0 == 10 && y0 == 12 && x1 == 889 && y1 == 587);

    /* Reset and set dirty full */
    g3x_restore2_reset_dirty_rect();
    assert(g3x_restore2_dirty_valid == 0);
    g3x_restore2_set_dirty_full();
    assert(g3x_restore2_dirty_valid == 1);
    assert(g3x_restore2_dirty_x0 == 10 && g3x_restore2_dirty_y0 == 12);
    assert(g3x_restore2_dirty_x1 == 889 && g3x_restore2_dirty_y1 == 587);

    printf("RECT_LOGIC_OK\n");
    return 0;
}
"""
        src_file = Path(self.tmp_dir.name) / "test_rect.c"
        src_file.write_text(c_src, encoding="utf-8")
        build_res = subprocess.run(
            ["cc", "-O2", f"-I{ROOT}/chdk-port/platform/g3x", str(src_file), "-o", str(self.bin_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(build_res.returncode, 0, build_res.stderr)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_rect_tracking_and_clipping(self):
        res = subprocess.run([str(self.bin_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RECT_LOGIC_OK", res.stdout)


class TestPort51BlitRestoreAndDiagLine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.bin_path = Path(self.tmp_dir.name) / "test_blit"
        c_src = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#define G3X_GUI_DBUF 1
#define G3X_GUI_NOOVERDRAW 1
#define G3X_KBD_CHECK 1
#define G3X_GUI_DIAG 1
#define G3X_GUI_SHADOW2 1
#define G3X_GUI_SYNC 1
#define G3X_GUI_MENU 1
#define G3X_GUI_RESTORE2 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#define MEMINFO_H 1

typedef short coord;
typedef unsigned short color;
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define MAKE_COLOR(bg, fg) (((bg) << 8) | (fg))

typedef struct {
    int mode;
} gui_handler;

typedef struct {
    int free_block_max_size;
} cam_meminfo;

typedef struct {
    struct {
        int gui_mode_alt;
        int gui_mode_none;
        int osd_title_line;
    } state;
} cam_info_t;

cam_info_t camera_info = {{1, 0, 0}};

struct {
    int width;
    int height;
    int buffer_width;
    int disp_width;
    int disp_left;
} camera_screen = {900, 600, 928, 900, 0};

#define FONT_WIDTH  16
#define FONT_HEIGHT 32

/* Simulated tick counter */
static long fake_tick = 1000;
long get_tick_count(void)
{
    return fake_tick++;
}

/* Mock buffers */
static unsigned char bm0[928 * 600 * 2];
static unsigned char bm1[928 * 600 * 2];
static unsigned char op0[928 * 600];
static unsigned char op1[928 * 600];

char *bitmap_buffer[2] = { (char *)bm0, (char *)bm1 };
volatile char *opacity_buffer[2] = { (volatile char *)op0, (volatile char *)op1 };

int active_bitmap_buffer = 0;

static unsigned char sh_bm[928 * 600 * 2];
static unsigned char sh_op[928 * 600];
int sh_valid = 1;
int sh_attempted = 1;

void GetMemInfo(cam_meminfo *m) { if (m) m->free_block_max_size = 500000; }
void *exmem_alloc_cached(unsigned int a, unsigned int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; return 0; }
void *umalloc(size_t s) { return malloc(s); }
int draw_test_guard(void) { return 1; }
int g3x_dbuf_shadow_is_allocated(void) { return 1; }
void g3x_dbuf_shadow_ensure_allocated(void) {}
int g3x_dbuf_shadow_restore(void) { return 1; }
int g3x_dbuf_shadow_sync_restore(unsigned int target_idx) { (void)target_idx; return 1; }
void draw_set_guard(void) {}
void gui_redraw(int f) { (void)f; }

static char last_diag_line[128];
static char last_menu_line[128];
static int last_draw_x = -1;
static int last_draw_y = -1;

void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl)
{
    (void)x1; (void)y1; (void)x2; (void)y2; (void)cl;
}

void draw_string(int x, int y, const char *s, int c)
{
    (void)c;
    last_draw_x = x;
    last_draw_y = y;
    if (strstr(s, "MENU:") != NULL) {
        strcpy(last_menu_line, s);
    } else {
        strcpy(last_diag_line, s);
    }
}

#include "gui_diag.h"

int main(void)
{
    /* 1. Initialize shadow parameters for RECT tier (880x576 at [10, 12]) */
    g3x_shadow2_mode = G3X_SHADOW_MODE_RECT;
    g3x_shadow2_bytes = G3X_SHADOW_RECT_TOTAL_SIZE;
    g3x_shadow2_x0 = G3X_MENU_X0;
    g3x_shadow2_y0 = G3X_MENU_Y0;
    g3x_shadow2_w = G3X_MENU_WIDTH;
    g3x_shadow2_h = G3X_MENU_HEIGHT;

    memset(sh_bm, 0x11, sizeof(sh_bm));
    memset(sh_op, 0x22, sizeof(sh_op));

    /* 2. Test dirty rect tracking */
    g3x_restore2_reset_dirty_rect();
    assert(g3x_restore2_dirty_valid == 0);

    /* Record small dirty rect: [100, 100, 120, 120] */
    g3x_restore2_record_rect(100, 100, 120, 120);
    assert(g3x_restore2_dirty_valid == 1);
    assert(g3x_restore2_dirty_x0 == 100 && g3x_restore2_dirty_y0 == 100);
    assert(g3x_restore2_dirty_x1 == 120 && g3x_restore2_dirty_y1 == 120);

    /* 3. Rect-only restore test */
    /* Fill destination buffers 0 and 1 with 0x00, place markers outside dirty rect at (300, 300) */
    memset(bm0, 0, sizeof(bm0));
    memset(op0, 0, sizeof(op0));
    memset(bm1, 0, sizeof(bm1));
    memset(op1, 0, sizeof(op1));
    unsigned int outside_off = 300u * 928u + 300u;
    op0[outside_off] = 0xAA;
    bm0[outside_off * 2] = 0xBB;
    op1[outside_off] = 0xAA;
    bm1[outside_off * 2] = 0xBB;

    /* Perform blit restore (restores both buffers 0 and 1 under RESTORE2) */
    int res = g3x_shadow2_blit_restore_target(sh_bm, sh_op, 928, 1u);
    assert(res == 1);

    /* Verify inside dirty rect: copied from shadow for BOTH buffers */
    unsigned int inside_off = 100u * 928u + 100u;
    assert(op0[inside_off] == 0x22);
    assert(bm0[inside_off * 2] == 0x11);
    assert(op1[inside_off] == 0x22);
    assert(bm1[inside_off * 2] == 0x11);

    /* Verify outside dirty rect: untouched on both buffers */
    assert(op0[outside_off] == 0xAA);
    assert(bm0[outside_off * 2] == 0xBB);
    assert(op1[outside_off] == 0xAA);
    assert(bm1[outside_off * 2] == 0xBB);

    /* 4. Timing measurement */
    assert(g3x_diag_blit_last_ms > 0u);
    assert(g3x_diag_blit_max_ms >= g3x_diag_blit_last_ms);

    /* 5. Path counters: sync vs poll */
    assert(g3x_diag_sync_restore_count == 0u);
    assert(g3x_diag_poll_restore_count == 0u);
    assert(g3x_diag_shadow_restore_count == 0u);

    g3x_diag_record_shadow_restore_sync();
    assert(g3x_diag_sync_restore_count == 1u);
    assert(g3x_diag_poll_restore_count == 0u);
    assert(g3x_diag_shadow_restore_count == 1u);

    g3x_diag_record_shadow_restore_poll();
    assert(g3x_diag_sync_restore_count == 1u);
    assert(g3x_diag_poll_restore_count == 1u);
    assert(g3x_diag_shadow_restore_count == 2u);

    /* 6. Formatting & character limit */
    g3x_conf_record_save_result(3 /* G3X_CONF_SAVE_OFF */);
    gui_diag_draw();

    assert(strlen(last_diag_line) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strlen(last_menu_line) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(last_draw_x >= 10 && (last_draw_x + (int)strlen(last_diag_line) * FONT_WIDTH) <= 890);

    /* Verify all counters are present across the two lines */
    assert(strstr(last_diag_line, "H:") != NULL);
    assert(strstr(last_diag_line, "S:OK/rect") != NULL);
    assert(strstr(last_diag_line, "L:") != NULL);
    assert(strstr(last_diag_line, "R:0002") != NULL);
    assert(strstr(last_diag_line, "F:") != NULL);
    assert(strstr(last_diag_line, "M:") != NULL);
    assert(strstr(last_diag_line, "Y:") != NULL);

    assert(strstr(last_menu_line, "MENU:") != NULL);
    assert(strstr(last_menu_line, "SAVE:OFF") != NULL);
    assert(strstr(last_menu_line, "Rs:0001") != NULL);
    assert(strstr(last_menu_line, "Rp:0001") != NULL);
    assert(strstr(last_menu_line, "B:") != NULL);
    assert(strstr(last_menu_line, "ms") != NULL);

    /* 7. Zero, Typical, and Saturated formatted line tests */
    /* Canary test helper: 64-byte buffer with guard bytes before and after */
    char buf1_canary[66];
    char buf2_canary[66];
    buf1_canary[0] = (char)0x5A; buf1_canary[65] = (char)0xA5;
    buf2_canary[0] = (char)0x5A; buf2_canary[65] = (char)0xA5;
    char *b1 = &buf1_canary[1];
    char *b2 = &buf2_canary[1];

    /* 7a. Zero values */
    g3x_diag_hook_hits = 0;
    g3x_diag_sentinel_loss_count = 0;
    g3x_diag_shadow_restore_count = 0;
    g3x_diag_sync_restore_count = 0;
    g3x_diag_poll_restore_count = 0;
    g3x_diag_full_redraw_count = 0;
    g3x_diag_suppress_hit_count = 0;
    g3x_diag_blit_last_ms = 0;
    g3x_diag_blit_max_ms = 0;
    g3x_menu_open_count = 0;
    g3x_conf_record_save_result(3 /* SAVE_OFF */);

    g3x_diag_format_line(b1);
    g3x_diag_format_line2(b2);

    assert(buf1_canary[0] == (char)0x5A && buf1_canary[65] == (char)0xA5);
    assert(buf2_canary[0] == (char)0x5A && buf2_canary[65] == (char)0xA5);
    assert(strlen(b1) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strlen(b2) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strstr(b1, "H:") != NULL && strstr(b1, "S:OK/rect") != NULL && strstr(b1, "L:0000") != NULL);
    assert(strstr(b1, "R:0000") != NULL && strstr(b1, "F:0000") != NULL && strstr(b1, "M:0000") != NULL && strstr(b1, "Y:0000") != NULL);
    assert(strstr(b2, "MENU:0000") != NULL && strstr(b2, "SAVE:OFF") != NULL);
    assert(strstr(b2, "Rs:0000") != NULL && strstr(b2, "Rp:0000") != NULL && strstr(b2, "B:0/0ms") != NULL);

    /* 7b. Typical values (~1000) */
    g3x_diag_hook_hits = 1000;
    g3x_diag_sentinel_loss_count = 20;
    g3x_diag_shadow_restore_count = 1000;
    g3x_diag_sync_restore_count = 950;
    g3x_diag_poll_restore_count = 50;
    g3x_diag_full_redraw_count = 5;
    g3x_diag_suppress_hit_count = 10;
    g3x_diag_blit_last_ms = 12;
    g3x_diag_blit_max_ms = 28;
    g3x_menu_open_count = 10;

    g3x_diag_format_line(b1);
    g3x_diag_format_line2(b2);

    assert(buf1_canary[0] == (char)0x5A && buf1_canary[65] == (char)0xA5);
    assert(buf2_canary[0] == (char)0x5A && buf2_canary[65] == (char)0xA5);
    assert(strlen(b1) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strlen(b2) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strstr(b1, "H:1/1000") != NULL && strstr(b1, "L:0020") != NULL && strstr(b1, "R:1000") != NULL);
    assert(strstr(b2, "MENU:0010") != NULL && strstr(b2, "SAVE:OFF") != NULL);
    assert(strstr(b2, "Rs:0950") != NULL && strstr(b2, "Rp:0050") != NULL && strstr(b2, "B:12/28ms") != NULL);

    /* 7c. Maximum saturated values */
    g3x_diag_hook_hits = 99999;
    g3x_diag_sentinel_loss_count = 99999;
    g3x_diag_shadow_restore_count = 99999;
    g3x_diag_sync_restore_count = 99999;
    g3x_diag_poll_restore_count = 99999;
    g3x_diag_full_redraw_count = 99999;
    g3x_diag_suppress_hit_count = 99999;
    g3x_diag_blit_last_ms = 99999;
    g3x_diag_blit_max_ms = 99999;
    g3x_menu_open_count = 99999;

    g3x_diag_format_line(b1);
    g3x_diag_format_line2(b2);

    assert(buf1_canary[0] == (char)0x5A && buf1_canary[65] == (char)0xA5);
    assert(buf2_canary[0] == (char)0x5A && buf2_canary[65] == (char)0xA5);
    assert(strlen(b1) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strlen(b2) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(strstr(b1, "H:1/9999") != NULL && strstr(b1, "L:9999") != NULL && strstr(b1, "R:9999") != NULL);
    assert(strstr(b2, "MENU:9999") != NULL && strstr(b2, "SAVE:OFF") != NULL);
    assert(strstr(b2, "Rs:9999") != NULL && strstr(b2, "Rp:9999") != NULL && strstr(b2, "B:999/999ms") != NULL);

    printf("BLIT_RESTORE_OK: %s | %s\n", b1, b2);
    return 0;
}
"""
        src_file = Path(self.tmp_dir.name) / "test_blit.c"
        src_file.write_text(c_src, encoding="utf-8")
        build_res = subprocess.run(
            ["cc", "-O2", f"-I{ROOT}/chdk-port/platform/g3x", str(src_file), "-o", str(self.bin_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(build_res.returncode, 0, build_res.stderr)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_blit_timing_path_counters_and_diag_formatting(self):
        res = subprocess.run([str(self.bin_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("BLIT_RESTORE_OK", res.stdout)
        self.assertIn("Rs:", res.stdout)
        self.assertIn("Rp:", res.stdout)
        self.assertIn("B:", res.stdout)
        self.assertIn("SAVE:OFF", res.stdout)


class TestPort51BuildAndArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT_TEST = ROOT / "out/port51-test"
        OUT_TEST.mkdir(parents=True, exist_ok=True)
        cls.build_default = OUT_TEST / "build-default"
        cls.build_p51 = ROOT / "out/port51-restore2-core"

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
            "G3X_GUI_RESTORE2",
        ]:
            env.pop(k, None)

        # 1. Build default build (standard PORT-41 full build with RESTORE2 off)
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

        # 2. Build full RESTORE2 candidate with pinned toolchain
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--full-hooks",
                "--no-overdraw",
                "--kbd-check",
                "--gui-diag",
                "--shadow2",
                "--gui-sync",
                "--gui-menu",
                "--gui-restore2",
                "--out-dir",
                str(cls.build_p51),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_default_build_is_byte_identical_to_port50_default(self):
        default_diskboot = self.build_default / "DISKBOOT.BIN"
        self.assertTrue(default_diskboot.is_file(), f"Missing default build DISKBOOT.BIN at {default_diskboot}")
        default_size = default_diskboot.stat().st_size
        default_sha = sha256_file(default_diskboot)

        # Assert build produced exactly the PORT-50 default baseline hash and size
        self.assertEqual(default_sha, BASE_PORT50_DEFAULT_SHA256)
        self.assertEqual(default_size, BASE_PORT50_DEFAULT_SIZE)

        # In-tree canonical DISKBOOT.BIN is also untouched and byte-identical
        canonical_diskboot = ROOT / "chdk-port/bin/DISKBOOT.BIN"
        self.assertEqual(canonical_diskboot.stat().st_size, BASE_CANONICAL_DISKBOOT_SIZE)
        self.assertEqual(sha256_file(canonical_diskboot), BASE_CANONICAL_DISKBOOT_SHA256)

        # Also verify against PORT-41 / PORT-50 default manifest if available
        p50_default_manifest = ROOT / "out/port50-test/build-default/manifest.json"
        if p50_default_manifest.is_file():
            p50_data = json.loads(p50_default_manifest.read_text(encoding="utf-8"))
            self.assertEqual(default_sha, p50_data["artifacts"]["DISKBOOT.BIN"]["sha256"])
            self.assertEqual(default_size, p50_data["artifacts"]["DISKBOOT.BIN"]["size"])

    def test_full_restore2_candidate_build_and_manifest(self):
        self.assertTrue(MANIFEST_P51.is_file(), f"Missing {MANIFEST_P51}")
        p51_data = json.loads(MANIFEST_P51.read_text(encoding="utf-8"))
        build_info = p51_data["build"]
        artifacts = p51_data["artifacts"]

        self.assertIn("G3X_GUI_RESTORE2=1", build_info["flags"])
        self.assertIn("G3X_GUI_MENU=1", build_info["flags"])
        self.assertIn("G3X_GUI_SYNC=1", build_info["flags"])
        self.assertIn("G3X_GUI_SHADOW2=1", build_info["flags"])
        self.assertIn("G3X_GUI_DIAG=1", build_info["flags"])
        self.assertIn("G3X_KBD_CHECK=1", build_info["flags"])
        self.assertIn("G3X_GUI_NOOVERDRAW=1", build_info["flags"])
        self.assertIn("G3X_GUI_DBUF=1", build_info["flags"])
        self.assertIn("G3X_DISABLE_CARD_WRITES=1", build_info["flags"])
        self.assertIn("OPT_DISABLE_FILE_WRITES=1", build_info["flags"])

        self.assertEqual(build_info["card_writes"], "disabled")
        self.assertIn("SAVE:OFF", build_info["card_writes_note"])

        diskboot_info = artifacts["DISKBOOT.BIN"]
        self.assertEqual(diskboot_info["sha256"], BASE_PORT51_RESTORE2_SHA256)
        self.assertEqual(diskboot_info["size"], BASE_PORT51_RESTORE2_SIZE)

        diskboot_bin = self.build_p51 / "DISKBOOT.BIN"
        self.assertTrue(diskboot_bin.is_file())
        self.assertEqual(sha256_file(diskboot_bin), BASE_PORT51_RESTORE2_SHA256)
        self.assertEqual(diskboot_bin.stat().st_size, BASE_PORT51_RESTORE2_SIZE)

    def test_timer_source_citation_in_headers(self):
        diag_text = DIAG_HEADER.read_text(encoding="utf-8")
        sync_text = SYNC_HEADER.read_text(encoding="utf-8")

        for text in (diag_text, sync_text):
            self.assertIn("reference/finsig_gm110c/stubs_entry.S:239", text)
            self.assertIn("NHSTUB(GetSystemTime, 0xfc60243d)", text)
            self.assertIn("get_tick_count() calls _GetSystemTime", text)
            self.assertIn("chdk-port/platform/generic/wrappers.c:345", text)
            self.assertIn("DryOS GetSystemTime provides 1 ms resolution", text)


if __name__ == "__main__":
    unittest.main()
