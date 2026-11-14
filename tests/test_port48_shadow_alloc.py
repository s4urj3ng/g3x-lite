#!/usr/bin/env python3
"""PORT-48 host unit and build verification tests for G3X_GUI_SHADOW2=1."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUI_DIAG_H = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "gui_diag.h"
PLATFORM_MAKEFILE = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "Makefile"
DOC_PATH = REPO_ROOT / "docs" / "PORT48_SHADOW_ALLOC.md"
MANIFEST_PATH = REPO_ROOT / "manifests" / "port48_shadow_alloc_manifest.json"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_port43_dbuf.py"

PORT47_CORE_END = 0x003699B0
MAX_CORE_END_GROWTH = 8 * 1024

EXPECTED_EARLIER_HASHES = {
    "port41": "06ce357ab59e3fc3c7aa58f3fd9cfbaaae3de3b13bb7dc71e09efacdc1b87d65",
    "port42": "0fb3ad38d1c8be7fb5df6f3d85b357900d88b17b7234766c9e594bc7bc8e5da0",
    "port44": "c86f6a64053a79928bf6c43e52f1caedfd45f2c2a753ef73dd392fd1fb17c090",
    "port45": "f22a406055317ce03ebaa7840207c92a49bf9811d8a328fa0676c14a4b3d4a2b",
    "port46": "02bc19468b44e0632afdf91e6e60c367c6550a8da4d734b19655b306c6e0425f",
    "port47": "9b6d9ad95b2512e487f9d7d6ae694ab9fddbaee731339570240f77bbcfc7e5f7",
}

HARNESS_C = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef short coord;
typedef unsigned short twoColors;
typedef unsigned char color;

#define MAKE_COLOR(bg, fg) ((twoColors)(((bg) << 8) | (fg)))
#define COLOR_BLACK 0xFF
#define COLOR_WHITE 0x01
#define FONT_WIDTH 16
#define FONT_HEIGHT 32

struct {
    struct {
        int gui_mode;
        int gui_mode_none;
        int gui_mode_alt;
    } state;
} camera_info;

struct {
    int width;
    int height;
    int buffer_width;
} camera_screen = { 900, 600, 928 };

int active_bitmap_buffer = 0;

static unsigned char host_bm0[928 * 600 * 2];
static unsigned char host_bm1[928 * 600 * 2];
static unsigned char host_op0[928 * 600];
static unsigned char host_op1[928 * 600];

char *bitmap_buffer[2] = { (char *)host_bm0, (char *)host_bm1 };
volatile char *opacity_buffer[2] = { (volatile char *)host_op0, (volatile char *)host_op1 };

static unsigned char *host_shadow_bm = NULL;
static unsigned char *host_shadow_op = NULL;
static int host_shadow_valid = 0;
static int host_shadow_attempted = 0;

static unsigned char host_pool_exmem[928 * 600 * 3];
static unsigned char host_pool_rect[880 * 576 * 3];
static unsigned char host_pool_idx[880 * 576 * 1];

static int mock_exmem_succeed = 0;
static int mock_malloc_rect_succeed = 0;
static int mock_umalloc_rect_succeed = 0;
static int mock_malloc_idx_succeed = 0;
static int mock_umalloc_idx_succeed = 0;

static int exmem_calls = 0;
static int malloc_calls = 0;
static int umalloc_calls = 0;
static unsigned int last_exmem_pool = 999u;
static unsigned int last_exmem_size = 0u;
static long last_malloc_size = 0;
static long last_umalloc_size = 0;

static int mock_free_block_max_size = 614400;
static int mock_sentinel_intact = 1;
static int draw_guard_calls = 0;
static int gui_redraw_calls = 0;
static int fill_rect_calls = 0;
static int draw_calls = 0;
static int last_draw_x = -1;
static int last_draw_y = -1;
static char last_drawn_line[128];

void *exmem_alloc_cached(unsigned int pool_id, unsigned int size, int unk, int unk2)
{
    (void)unk;
    (void)unk2;
    exmem_calls++;
    last_exmem_pool = pool_id;
    last_exmem_size = size;
    if (mock_exmem_succeed && size == (928u * 600u * 3u))
        return host_pool_exmem;
    return NULL;
}

static void *test_malloc(long size)
{
    malloc_calls++;
    last_malloc_size = size;
    if (size == (880 * 576 * 3) && mock_malloc_rect_succeed)
        return host_pool_rect;
    if (size == (880 * 576 * 1) && mock_malloc_idx_succeed)
        return host_pool_idx;
    return NULL;
}

static void *test_umalloc(long size)
{
    umalloc_calls++;
    last_umalloc_size = size;
    if (size == (880 * 576 * 3) && mock_umalloc_rect_succeed)
        return host_pool_rect;
    if (size == (880 * 576 * 1) && mock_umalloc_idx_succeed)
        return host_pool_idx;
    return NULL;
}

#define malloc test_malloc
#define umalloc test_umalloc

#define MEMINFO_H
typedef struct {
    int start_address;
    int end_address;
    int total_size;
    int allocated_size;
    int allocated_peak;
    int allocated_count;
    int free_size;
    int free_block_max_size;
    int free_block_count;
} cam_meminfo;

void GetMemInfo(cam_meminfo *camera_meminfo)
{
    memset(camera_meminfo, 0, sizeof(*camera_meminfo));
    camera_meminfo->free_block_max_size = mock_free_block_max_size;
}

int draw_test_guard(void)
{
    return mock_sentinel_intact;
}

void draw_set_guard(void)
{
    draw_guard_calls++;
    mock_sentinel_intact = 1;
}

int g3x_dbuf_shadow_is_allocated(void)
{
    return (host_shadow_bm != NULL && host_shadow_op != NULL) ? 1 : 0;
}

void g3x_diag_shadow_ensure_allocated(unsigned char **bm_ptr,
                                      unsigned char **op_ptr,
                                      int *valid_ptr,
                                      int *attempted_ptr);
void g3x_diag_record_shadow_restore(void);
int g3x_shadow2_blit_restore(unsigned char *bm, unsigned char *op, int buf_w);

void g3x_dbuf_shadow_ensure_allocated(void)
{
    g3x_diag_shadow_ensure_allocated(&host_shadow_bm, &host_shadow_op,
                                     &host_shadow_valid, &host_shadow_attempted);
}

int g3x_dbuf_shadow_restore(void)
{
    if (!host_shadow_bm || !host_shadow_op || camera_info.state.gui_mode_none)
        return 0;
    if (!g3x_shadow2_blit_restore(host_shadow_bm, host_shadow_op, camera_screen.buffer_width))
        return 0;
    draw_set_guard();
    g3x_diag_record_shadow_restore();
    return 1;
}

void gui_redraw(int flag_gui_enforce_redraw)
{
    (void)flag_gui_enforce_redraw;
    gui_redraw_calls++;
}

void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl)
{
    (void)x1; (void)y1; (void)x2; (void)y2; (void)cl;
    fill_rect_calls++;
}

int draw_string(coord x, coord y, const char *s, twoColors cl)
{
    (void)cl;
    draw_calls++;
    last_draw_x = x;
    last_draw_y = y;
    snprintf(last_drawn_line, sizeof(last_drawn_line), "%s", s);
    return x;
}

#define G3X_GUI_DBUF 1
#define G3X_GUI_NOOVERDRAW 1
#define G3X_KBD_CHECK 1
#define G3X_GUI_DIAG 1
#define G3X_GUI_SHADOW2 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#include "gui_diag.h"

void harness_reset(void)
{
    camera_info.state.gui_mode = 0;
    camera_info.state.gui_mode_none = 1;
    camera_info.state.gui_mode_alt = 0;
    active_bitmap_buffer = 0;

    memset(host_bm0, 0, sizeof(host_bm0));
    memset(host_bm1, 0, sizeof(host_bm1));
    memset(host_op0, 0, sizeof(host_op0));
    memset(host_op1, 0, sizeof(host_op1));

    host_shadow_bm = NULL;
    host_shadow_op = NULL;
    host_shadow_valid = 0;
    host_shadow_attempted = 0;

    mock_exmem_succeed = 0;
    mock_malloc_rect_succeed = 0;
    mock_umalloc_rect_succeed = 0;
    mock_malloc_idx_succeed = 0;
    mock_umalloc_idx_succeed = 0;

    exmem_calls = 0;
    malloc_calls = 0;
    umalloc_calls = 0;
    last_exmem_pool = 999u;
    last_exmem_size = 0u;
    last_malloc_size = 0;
    last_umalloc_size = 0;

    mock_free_block_max_size = 614400;
    mock_sentinel_intact = 1;
    draw_guard_calls = 0;
    gui_redraw_calls = 0;
    fill_rect_calls = 0;
    draw_calls = 0;
    last_draw_x = -1;
    last_draw_y = -1;
    last_drawn_line[0] = '\0';

    g3x_diag_hook_installed = 1u;
    g3x_diag_hook_hits = 0u;
    g3x_diag_sentinel_loss_count = 0u;
    g3x_diag_shadow_restore_count = 0u;
    g3x_diag_full_redraw_count = 0u;
    g3x_diag_suppress_hit_count = 0u;
    g3x_diag_suppress_engaged = 0;
    g3x_diag_last_bitmap_buffer = -1;

    g3x_shadow2_mode = G3X_SHADOW_MODE_NONE;
    g3x_shadow2_bytes = 0u;
    g3x_shadow2_x0 = 0;
    g3x_shadow2_y0 = 0;
    g3x_shadow2_w = 0;
    g3x_shadow2_h = 0;
    g3x_shadow2_largest_free = -1;
}

void harness_set_alloc_mocks(int exmem_ok, int malloc_rect_ok, int umalloc_rect_ok,
                             int malloc_idx_ok, int umalloc_idx_ok)
{
    mock_exmem_succeed = exmem_ok;
    mock_malloc_rect_succeed = malloc_rect_ok;
    mock_umalloc_rect_succeed = umalloc_rect_ok;
    mock_malloc_idx_succeed = malloc_idx_ok;
    mock_umalloc_idx_succeed = umalloc_idx_ok;
}

void harness_set_free_block_max_size(int val)
{
    mock_free_block_max_size = val;
    g3x_shadow2_largest_free = val;
}

void harness_set_mode_override(int mode, unsigned int bytes)
{
    g3x_shadow2_mode = mode;
    g3x_shadow2_bytes = bytes;
}

void harness_set_alt_mode(int is_alt)
{
    camera_info.state.gui_mode = is_alt ? 1 : 0;
    camera_info.state.gui_mode_none = is_alt ? 0 : 1;
    camera_info.state.gui_mode_alt = is_alt ? 1 : 0;
}

void harness_set_sentinel(int intact)
{
    mock_sentinel_intact = intact;
}

int harness_get_shadow_mode(void) { return g3x_shadow2_mode; }
unsigned int harness_get_shadow_bytes(void) { return g3x_shadow2_bytes; }
int harness_get_shadow_x0(void) { return g3x_shadow2_x0; }
int harness_get_shadow_y0(void) { return g3x_shadow2_y0; }
int harness_get_shadow_w(void) { return g3x_shadow2_w; }
int harness_get_shadow_h(void) { return g3x_shadow2_h; }
int harness_get_exmem_calls(void) { return exmem_calls; }
int harness_get_malloc_calls(void) { return malloc_calls; }
int harness_get_umalloc_calls(void) { return umalloc_calls; }
unsigned int harness_get_last_exmem_pool(void) { return last_exmem_pool; }
unsigned int harness_get_last_exmem_size(void) { return last_exmem_size; }
int harness_get_gui_redraw_calls(void) { return gui_redraw_calls; }
int harness_get_draw_calls(void) { return draw_calls; }
int harness_get_last_draw_x(void) { return last_draw_x; }
int harness_get_last_draw_y(void) { return last_draw_y; }
const char *harness_get_last_line(void) { return last_drawn_line; }

unsigned int harness_get_full_total_size(void) { return G3X_SHADOW_FULL_TOTAL_SIZE; }
unsigned int harness_get_rect_total_size(void) { return G3X_SHADOW_RECT_TOTAL_SIZE; }
unsigned int harness_get_idx_total_size(void) { return G3X_SHADOW_IDX_TOTAL_SIZE; }

void harness_set_counters(unsigned int installed, unsigned int hits,
                          unsigned int loss, unsigned int restore,
                          unsigned int full)
{
    g3x_diag_hook_installed = installed;
    g3x_diag_hook_hits = hits;
    g3x_diag_sentinel_loss_count = loss;
    g3x_diag_shadow_restore_count = restore;
    g3x_diag_full_redraw_count = full;
}

unsigned int harness_get_hook_hits(void) { return g3x_diag_hook_hits; }
unsigned int harness_get_loss_count(void) { return g3x_diag_sentinel_loss_count; }
unsigned int harness_get_restore_count(void) { return g3x_diag_shadow_restore_count; }
unsigned int harness_get_full_count(void) { return g3x_diag_full_redraw_count; }

void harness_write_shadow_pair(int x, int y, unsigned int yuv, unsigned short co,
                               unsigned char c0, unsigned char c1)
{
    g3x_shadow2_write_pair(host_shadow_bm, host_shadow_op, x, y, yuv, co, c0, c1);
}

unsigned int harness_read_bm_word(int buf_idx, int x, int y)
{
    unsigned int pair_idx = (unsigned int)((y * 928 + x) >> 1);
    unsigned int *bm = (unsigned int *)(buf_idx ? host_bm1 : host_bm0);
    return bm[pair_idx];
}

unsigned short harness_read_op_word(int buf_idx, int x, int y)
{
    unsigned int pair_idx = (unsigned int)((y * 928 + x) >> 1);
    unsigned short *op = (unsigned short *)(buf_idx ? host_op1 : host_op0);
    return op[pair_idx];
}
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPort48ShadowAlloc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        c_file = tmp / "harness.c"
        so_file = tmp / "harness.so"
        c_file.write_text(HARNESS_C, encoding="utf-8")
        subprocess.run(
            [
                "gcc",
                "-shared",
                "-fPIC",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                f"-I{GUI_DIAG_H.parent}",
                str(c_file),
                "-o",
                str(so_file),
            ],
            check=True,
        )
        cls.lib = ctypes.CDLL(str(so_file))
        cls.lib.harness_get_last_line.restype = ctypes.c_char_p
        cls.lib.harness_get_shadow_bytes.restype = ctypes.c_uint
        cls.lib.harness_get_last_exmem_pool.restype = ctypes.c_uint
        cls.lib.harness_get_last_exmem_size.restype = ctypes.c_uint
        cls.lib.harness_get_full_total_size.restype = ctypes.c_uint
        cls.lib.harness_get_rect_total_size.restype = ctypes.c_uint
        cls.lib.harness_get_idx_total_size.restype = ctypes.c_uint
        cls.lib.harness_get_hook_hits.restype = ctypes.c_uint
        cls.lib.harness_get_loss_count.restype = ctypes.c_uint
        cls.lib.harness_get_restore_count.restype = ctypes.c_uint
        cls.lib.harness_get_full_count.restype = ctypes.c_uint
        cls.lib.harness_read_bm_word.restype = ctypes.c_uint
        cls.lib.harness_read_op_word.restype = ctypes.c_ushort

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def setUp(self) -> None:
        self.lib.harness_reset()

    def test_header_and_makefile_require_all_layered_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "check.c"
            src.write_text('#include "gui_diag.h"\nint x;\n', encoding="utf-8")
            for missing_flag in [
                "G3X_GUI_DBUF",
                "G3X_GUI_NOOVERDRAW",
                "G3X_KBD_CHECK",
                "G3X_GUI_DIAG",
            ]:
                flags = [
                    "-DG3X_GUI_DBUF=1",
                    "-DG3X_GUI_NOOVERDRAW=1",
                    "-DG3X_KBD_CHECK=1",
                    "-DG3X_GUI_DIAG=1",
                    "-DG3X_GUI_SHADOW2=1",
                ]
                flags = [f for f in flags if not f.startswith(f"-D{missing_flag}=")]
                proc = subprocess.run(
                    ["gcc", "-fsyntax-only", *flags, f"-I{GUI_DIAG_H.parent}", str(src)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(
                    "G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1",
                    proc.stderr,
                )

            mk = Path(td) / "Makefile"
            mk_lines = [
                line
                for line in PLATFORM_MAKEFILE.read_text(encoding="utf-8").splitlines()
                if not line.startswith("include ")
            ]
            mk.write_text("\n".join(mk_lines) + "\nall:\n\t@true\n", encoding="utf-8")
            for missing in ["G3X_GUI_DBUF=0", "G3X_GUI_NOOVERDRAW=0", "G3X_KBD_CHECK=0", "G3X_GUI_DIAG=0"]:
                cmd = [
                    "make",
                    "-f",
                    str(mk),
                    "G3X_GUI_SHADOW2=1",
                    "G3X_GUI_DBUF=1",
                    "G3X_GUI_NOOVERDRAW=1",
                    "G3X_KBD_CHECK=1",
                    "G3X_GUI_DIAG=1",
                    missing,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(
                    "G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1",
                    proc.stderr,
                )

    def test_shadow_size_calculations(self) -> None:
        self.assertEqual(self.lib.harness_get_full_total_size(), 928 * 600 * 3)
        self.assertEqual(self.lib.harness_get_full_total_size(), 1670400)
        self.assertEqual(self.lib.harness_get_rect_total_size(), 880 * 576 * 3)
        self.assertEqual(self.lib.harness_get_rect_total_size(), 1520640)
        self.assertEqual(self.lib.harness_get_idx_total_size(), 880 * 576 * 1)
        self.assertEqual(self.lib.harness_get_idx_total_size(), 506880)

    def test_ordered_fallback_chain_and_retry_on_alt_entry(self) -> None:
        # 0. Nothing allocated at boot before ALT entry
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 0)
        self.assertEqual(self.lib.harness_get_exmem_calls(), 0)
        self.assertEqual(self.lib.harness_get_malloc_calls(), 0)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 0)

        # 1. All allocators return NULL -> shadow stays NULL, retried on next ALT entry
        self.lib.harness_set_alloc_mocks(0, 0, 0, 0, 0)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 0)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 0)
        self.assertEqual(self.lib.harness_get_exmem_calls(), 1)
        self.assertEqual(self.lib.harness_get_malloc_calls(), 2)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 2)

        # Retry on second ALT entry when Step 3 umalloc(506880) succeeds -> idx mode
        self.lib.harness_set_alloc_mocks(0, 0, 0, 0, 1)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 1)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 4)  # G3X_SHADOW_MODE_IDX
        self.assertEqual(self.lib.harness_get_shadow_bytes(), 506880)
        self.assertEqual(
            (
                self.lib.harness_get_shadow_x0(),
                self.lib.harness_get_shadow_y0(),
                self.lib.harness_get_shadow_w(),
                self.lib.harness_get_shadow_h(),
            ),
            (10, 12, 880, 576),
        )

        # Step 3 malloc(506880) succeeds -> idx mode without calling umalloc for Step 3
        self.lib.harness_reset()
        self.lib.harness_set_alloc_mocks(0, 0, 0, 1, 0)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 1)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 4)
        self.assertEqual(self.lib.harness_get_shadow_bytes(), 506880)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 1)

        # Step 2 umalloc(1520640) succeeds -> rect mode without attempting Step 3
        self.lib.harness_reset()
        self.lib.harness_set_alloc_mocks(0, 0, 1, 1, 1)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 1)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 3)  # G3X_SHADOW_MODE_RECT
        self.assertEqual(self.lib.harness_get_shadow_bytes(), 1520640)
        self.assertEqual(self.lib.harness_get_malloc_calls(), 1)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 1)

        # Step 2 malloc(1520640) succeeds -> rect mode without calling umalloc
        self.lib.harness_reset()
        self.lib.harness_set_alloc_mocks(0, 1, 0, 1, 1)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 1)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 3)
        self.assertEqual(self.lib.harness_get_shadow_bytes(), 1520640)
        self.assertEqual(self.lib.harness_get_malloc_calls(), 1)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 0)

        # Step 1 exmem_alloc_cached(0, 1670400, 0, 0) succeeds -> exmem mode without calling malloc/umalloc
        self.lib.harness_reset()
        self.lib.harness_set_alloc_mocks(1, 1, 1, 1, 1)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_dbuf_shadow_is_allocated(), 1)
        self.assertEqual(self.lib.harness_get_shadow_mode(), 1)  # G3X_SHADOW_MODE_EXMEM
        self.assertEqual(self.lib.harness_get_shadow_bytes(), 1670400)
        self.assertEqual(self.lib.harness_get_last_exmem_pool(), 0)
        self.assertEqual(self.lib.harness_get_last_exmem_size(), 1670400)
        self.assertEqual(self.lib.harness_get_malloc_calls(), 0)
        self.assertEqual(self.lib.harness_get_umalloc_calls(), 0)
        self.assertEqual(
            (
                self.lib.harness_get_shadow_x0(),
                self.lib.harness_get_shadow_y0(),
                self.lib.harness_get_shadow_w(),
                self.lib.harness_get_shadow_h(),
            ),
            (0, 0, 928, 600),
        )

        # Subsequent ALT entry reuses existing shadow without re-allocating
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.harness_get_exmem_calls(), 1)

    def test_diagnostic_string_format_and_largest_free_block(self) -> None:
        self.lib.harness_set_alt_mode(1)
        self.lib.harness_set_counters(1, 12, 3, 45, 0)

        # S:NULL with largest-free-block '-'
        self.lib.harness_set_free_block_max_size(0)
        self.lib.gui_diag_draw()
        line = self.lib.harness_get_last_line().decode("ascii")
        self.assertEqual(line, "H:1/0012 S:NULL - L:0003 R:0045 F:0000")
        self.assertLessEqual(len(line), 55)

        # S:OK/1670400/exmem with largest-free-block 614400
        self.lib.harness_set_alloc_mocks(1, 0, 0, 0, 0)
        self.lib.g3x_diag_on_alt_enter()
        self.lib.harness_set_free_block_max_size(614400)
        self.lib.gui_diag_draw()
        line = self.lib.harness_get_last_line().decode("ascii")
        self.assertEqual(line, "H:1/0012 S:OK/1670400/exmem 614400 L:0003 R:0045 F:0000")
        self.assertEqual(len(line), 55)
        self.assertEqual(self.lib.harness_get_last_draw_x(), 10)
        self.assertEqual(self.lib.harness_get_last_draw_y(), 600 - 2 * 32)

        # S:OK/1520640/heap
        self.lib.harness_set_mode_override(2, 1520640)
        self.lib.gui_diag_draw()
        line = self.lib.harness_get_last_line().decode("ascii")
        self.assertEqual(line, "H:1/0012 S:OK/1520640/heap 614400 L:0003 R:0045 F:0000")

        # S:OK/1520640/rect
        self.lib.harness_set_mode_override(3, 1520640)
        self.lib.gui_diag_draw()
        line = self.lib.harness_get_last_line().decode("ascii")
        self.assertEqual(line, "H:1/0012 S:OK/1520640/rect 614400 L:0003 R:0045 F:0000")

        # S:OK/506880/idx with '-'
        self.lib.harness_set_mode_override(4, 506880)
        self.lib.harness_set_free_block_max_size(-1)
        self.lib.harness_set_counters(1, 12345, 99999, 42, 7)
        self.lib.gui_diag_draw()
        line = self.lib.harness_get_last_line().decode("ascii")
        self.assertEqual(line, "H:1/9999 S:OK/506880/idx - L:9999 R:0042 F:0007")

    def test_palette_index_to_colour_expansion_and_blit(self) -> None:
        def ref_expand_pair(c0: int, c1: int) -> tuple[int, int]:
            y0 = (((c0 - 1) ^ 0xFFFFFFFF) & 0xF0) & 0xFF
            o0 = 255 if (c0 & 0x0F) else c0
            v0 = c0
            u0 = v0 + 1
            if not (u0 & 2):
                u0, v0 = 128, 128
            else:
                u0 = (u0 * 3) & 0xFF
                v0 = (v0 << 3) & 0xFF
            y1 = (((c1 - 1) ^ 0xFFFFFFFF) & 0xF0) & 0xFF
            o1 = 255 if (c1 & 0x0F) else c1
            uyvy = (u0 & 0xFF) | ((y0 & 0xFF) << 8) | ((v0 & 0xFF) << 16) | ((y1 & 0xFF) << 24)
            op16 = (o0 & 0xFF) | ((o1 & 0xFF) << 8)
            return uyvy, op16

        out_uyvy = ctypes.c_uint(0)
        out_op = ctypes.c_ushort(0)
        test_pairs = [
            (0x00, 0x00),  # COLOR_TRANSPARENT
            (0xFF, 0xFF),  # COLOR_BLACK
            (0x01, 0x01),  # COLOR_WHITE
            (0xFF, 0x01),  # Black + White mixed pair
            (0x22, 0x57),  # Chromatic palette indices
            (0x9F, 0x00),  # Opaque + Transparent pair
        ]
        for c0, c1 in test_pairs:
            self.lib.g3x_shadow2_expand_pair(
                c0, c1, ctypes.byref(out_uyvy), ctypes.byref(out_op)
            )
            exp_uyvy, exp_op = ref_expand_pair(c0, c1)
            self.assertEqual(out_uyvy.value, exp_uyvy)
            self.assertEqual(out_op.value, exp_op)

        # Verify idx shadow write + blit expansion into both bitmap_buffer[0..1] and opacity_buffer[0..1]
        self.lib.harness_set_alt_mode(1)
        self.lib.harness_set_alloc_mocks(0, 0, 0, 1, 0)  # idx mode
        self.lib.g3x_diag_on_alt_enter()
        self.lib.harness_write_shadow_pair(10, 12, 0, 0, 0xFF, 0x01)
        self.lib.harness_write_shadow_pair(888, 587, 0, 0, 0x22, 0x57)
        rc = self.lib.g3x_dbuf_shadow_restore()
        self.assertEqual(rc, 1)

        exp_uyvy1, exp_op1 = ref_expand_pair(0xFF, 0x01)
        exp_uyvy2, exp_op2 = ref_expand_pair(0x22, 0x57)
        for buf_idx in (0, 1):
            self.assertEqual(self.lib.harness_read_bm_word(buf_idx, 10, 12), exp_uyvy1)
            self.assertEqual(self.lib.harness_read_op_word(buf_idx, 10, 12), exp_op1)
            self.assertEqual(self.lib.harness_read_bm_word(buf_idx, 888, 587), exp_uyvy2)
            self.assertEqual(self.lib.harness_read_op_word(buf_idx, 888, 587), exp_op2)

    def test_region_scoped_restore_and_outside_fallback(self) -> None:
        self.lib.harness_set_alt_mode(1)

        # In rect mode ((10,12)..(889,587)), ALT/menu region restores from shadow; outside falls back to gui_redraw
        self.lib.harness_set_alloc_mocks(0, 1, 0, 0, 0)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_shadow2_covers_rect(10, 12, 889, 587), 1)
        self.assertEqual(self.lib.g3x_shadow2_covers_rect(0, 0, 899, 599), 0)

        rc_in = self.lib.g3x_diag_restore_overlay(1)
        self.assertEqual(rc_in, 0)
        self.assertEqual(self.lib.harness_get_restore_count(), 1)
        self.assertEqual(self.lib.harness_get_full_count(), 0)
        self.assertEqual(self.lib.harness_get_gui_redraw_calls(), 0)

        rc_out = self.lib.g3x_shadow2_restore_rect(0, 0, 899, 599)
        self.assertEqual(rc_out, 1)
        self.assertEqual(self.lib.harness_get_restore_count(), 1)
        self.assertEqual(self.lib.harness_get_full_count(), 1)
        self.assertEqual(self.lib.harness_get_gui_redraw_calls(), 1)

        # In exmem mode ((0,0)..(927,599)), full screen is covered by shadow
        self.lib.harness_reset()
        self.lib.harness_set_alt_mode(1)
        self.lib.harness_set_alloc_mocks(1, 0, 0, 0, 0)
        self.lib.g3x_diag_on_alt_enter()
        self.assertEqual(self.lib.g3x_shadow2_covers_rect(0, 0, 927, 599), 1)
        self.assertEqual(self.lib.g3x_shadow2_restore_rect(0, 0, 899, 599), 0)
        self.assertEqual(self.lib.harness_get_restore_count(), 1)
        self.assertEqual(self.lib.harness_get_full_count(), 0)

    def test_candidate_manifest_core_end_and_earlier_build_invariance(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        flags = manifest["build"]["flags"]
        for req_flag in [
            "G3X_GUI_DBUF=1",
            "G3X_GUI_NOOVERDRAW=1",
            "G3X_KBD_CHECK=1",
            "G3X_GUI_DIAG=1",
            "G3X_GUI_SHADOW2=1",
        ]:
            self.assertIn(req_flag, flags)

        core_end = int(manifest["core_end"], 16)
        self.assertEqual(manifest["core_end"], "0x00369ec0")
        self.assertLessEqual(core_end - PORT47_CORE_END, MAX_CORE_END_GROWTH)

        diskboot_entry = manifest["artifacts"]["DISKBOOT.BIN"]
        self.assertEqual(len(diskboot_entry["sha256"]), 64)
        self.assertEqual(manifest["artifacts"]["modules_count"], 34)
        self.assertEqual(manifest["artifacts"]["chdk_files_count"], 242)

        with tempfile.TemporaryDirectory() as td:
            out48 = Path(td) / "port48"
            out47 = Path(td) / "port47"
            subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--shadow2", "--discard-stage", "--out-dir", str(out48)],
                cwd=str(REPO_ROOT),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-diag", "--discard-stage", "--out-dir", str(out47)],
                cwd=str(REPO_ROOT),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.assertEqual(sha256_file(out48 / "DISKBOOT.BIN"), diskboot_entry["sha256"])
            self.assertEqual(sha256_file(out47 / "DISKBOOT.BIN"), EXPECTED_EARLIER_HASHES["port47"])

        doc_text = DOC_PATH.read_text(encoding="utf-8")
        for required_snippet in [
            "0xFC092537",
            "0xFC610AB9",
            "0xFC381525",
            "0xFC144471",
            "S:OK/",
            "S:NULL",
            "9b6d9ad9",
            "battery",
        ]:
            self.assertIn(required_snippet, doc_text)


if __name__ == "__main__":
    unittest.main()
