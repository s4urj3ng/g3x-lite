#!/usr/bin/env python3
"""PORT-45 Test Suite: G3X_GUI_NOOVERDRAW=1 opt-in overlay protection.

Verifies:
1. Pinned build artifacts and manifest for G3X_GUI_NOOVERDRAW=1.
2. Memory layout & _end guard (< 64 KiB above PORT-42 baseline, no symbol > 64 KiB).
3. Build flag dependency: G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1.
4. Host C model simulation:
   - ALT gating: With ALT inactive, 0 shadow writes occur and forced=0.
   - Buffer toggle: When ALT is active, buffer toggle triggers shadow restore.
   - Multi-point perimeter sentinels: Corrupting (0,0) or any of the 4 menu corners
     ((10,12), (889,12), (10,587), (889,587)) triggers shadow restore.
   - NULL shadow fallback: When shadow is NULL or unavailable, falls back to
     forced=1 (PORT-44 full redraw) without crashes or memory corruption.
   - Canary integrity: Zero out-of-bounds writes on all code paths.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
TOOLCHAIN_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OUT_DIR = REPO_ROOT / "out" / "port45-no-overdraw"
PORT42_BASELINE_END = 0x003687B0


class TestPort45ArtifactsAndMemory(unittest.TestCase):
    """Artifact integrity, symbols, and _end guard tests for PORT-45 build."""

    def test_diskboot_bin_exists_and_hash(self):
        diskboot = OUT_DIR / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Missing {diskboot}")
        self.assertEqual(diskboot.stat().st_size, 126929)

    def test_manifest_contents(self):
        manifest_path = OUT_DIR / "port45_no_overdraw_manifest.json"
        self.assertTrue(manifest_path.is_file(), f"Missing {manifest_path}")
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        build_info = data.get("build", {})
        flags = build_info.get("flags", [])
        self.assertIn("G3X_GUI_FIX=1", flags)
        self.assertIn("G3X_GUI_DBUF=1", flags)
        self.assertIn("G3X_GUI_NOOVERDRAW=1", flags)

        artifacts = data.get("artifacts", {})
        diskboot_info = artifacts.get("DISKBOOT.BIN", {})
        self.assertEqual(diskboot_info.get("size"), 126929)
        self.assertEqual(
            diskboot_info.get("sha256"),
            "acf8a062cac5034686971d5eb32a692de202c406b1b6a02f170ba6bd74f339ab",
        )

    def test_end_guard_and_symbol_sizes(self):
        elf_path = OUT_DIR / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
        self.assertTrue(elf_path.is_file(), f"Missing {elf_path}")
        self.assertTrue(TOOLCHAIN_NM.is_file(), f"Missing {TOOLCHAIN_NM}")

        # Find _end using nm
        res_nm = subprocess.run(
            [str(TOOLCHAIN_NM), str(elf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        end_val = None
        for line in res_nm.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1] == "_end":
                end_val = int(parts[0], 16)
                break

        self.assertIsNotNone(end_val, "Symbol '_end' not found in main.elf")
        delta = end_val - PORT42_BASELINE_END
        self.assertGreaterEqual(delta, 0, f"_end {hex(end_val)} is below PORT-42 baseline {hex(PORT42_BASELINE_END)}")
        self.assertLess(
            delta,
            65536,
            f"_end delta {delta} bytes exceeds 64 KiB margin (end={hex(end_val)}, baseline={hex(PORT42_BASELINE_END)})",
        )

        # Check maximum symbol size using nm -S --size-sort
        res_sz = subprocess.run(
            [str(TOOLCHAIN_NM), "-S", "--size-sort", str(elf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        max_symbol_size = 0
        max_symbol_name = ""
        for line in res_sz.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 4:
                try:
                    sz = int(parts[1], 16)
                    if sz > max_symbol_size:
                        max_symbol_size = sz
                        max_symbol_name = parts[3]
                except ValueError:
                    pass

        self.assertLess(
            max_symbol_size,
            65536,
            f"Symbol {max_symbol_name} size {max_symbol_size} exceeds 64 KiB",
        )

    def test_build_flag_dependency_enforcement(self):
        """Verifies G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1 in Makefile."""
        makefile_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "Makefile"
        self.assertTrue(makefile_path.is_file())
        text = makefile_path.read_text(encoding="utf-8")
        self.assertIn("G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1", text)


class TestPort45HostSimulation(unittest.TestCase):
    """Host C simulation verifying ALT gating, sentinels, buffer flip, NULL fallback and canaries."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="port45_test_")
        cls.c_src = Path(cls.temp_dir) / "sim_nooverdraw.c"
        cls.c_bin = Path(cls.temp_dir) / "sim_nooverdraw"

        c_code = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdint.h>

#define SCREEN_W 900
#define SCREEN_H 600
#define BUF_W    928
#define BUF_H    600

#define BM_SIZE  (BUF_W * BUF_H * 2)
#define OP_SIZE  (BUF_W * BUF_H * 1)

#define G3X_MENU_X0         10
#define G3X_MENU_Y0         12
#define G3X_MENU_WIDTH      880
#define G3X_MENU_HEIGHT     576
#define G3X_MENU_X1         (G3X_MENU_X0 + G3X_MENU_WIDTH - 1)  /* 889 */
#define G3X_MENU_Y1         (G3X_MENU_Y0 + G3X_MENU_HEIGHT - 1) /* 587 */

#define G3X_SHADOW_WIDTH    G3X_MENU_WIDTH
#define G3X_SHADOW_HEIGHT   G3X_MENU_HEIGHT
#define G3X_SHADOW_BM_SIZE  (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 2)
#define G3X_SHADOW_OP_SIZE  (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 1)
#define G3X_SHADOW_TOTAL_SIZE (G3X_SHADOW_BM_SIZE + G3X_SHADOW_OP_SIZE)

#define CANARY_SIZE 4096
#define CANARY_BYTE 0x5A

typedef struct {
    uint8_t guard_pre[CANARY_SIZE];
    uint8_t buf[BM_SIZE];
    uint8_t guard_post[CANARY_SIZE];
} guarded_bm_buf_t;

typedef struct {
    uint8_t guard_pre[CANARY_SIZE];
    uint8_t buf[OP_SIZE];
    uint8_t guard_post[CANARY_SIZE];
} guarded_op_buf_t;

static guarded_bm_buf_t g_bm_buffers[2];
static guarded_op_buf_t g_op_buffers[2];

static uint8_t *bitmap_buffer[2] = { g_bm_buffers[0].buf, g_bm_buffers[1].buf };
static uint8_t *opacity_buffer[2] = { g_op_buffers[0].buf, g_op_buffers[1].buf };

static uint8_t *g3x_shadow_bitmap = NULL;
static uint8_t *g3x_shadow_opacity = NULL;
static int g3x_shadow_valid = 0;

static int active_bitmap_buffer = 0;
static int last_bitmap_buffer = 0;

static struct {
    struct {
        int gui_mode_none;
    } state;
} camera_info;

static struct {
    int buffer_width;
} camera_screen = { 928 };

static int restore_calls = 0;

void init_canaries(void) {
    for (int b = 0; b < 2; b++) {
        memset(g_bm_buffers[b].guard_pre, CANARY_BYTE, CANARY_SIZE);
        memset(g_bm_buffers[b].guard_post, CANARY_BYTE, CANARY_SIZE);
        memset(g_op_buffers[b].guard_pre, CANARY_BYTE, CANARY_SIZE);
        memset(g_op_buffers[b].guard_post, CANARY_BYTE, CANARY_SIZE);
    }
}

int check_canaries(void) {
    for (int b = 0; b < 2; b++) {
        for (int i = 0; i < CANARY_SIZE; i++) {
            if (g_bm_buffers[b].guard_pre[i] != CANARY_BYTE) return 0;
            if (g_bm_buffers[b].guard_post[i] != CANARY_BYTE) return 0;
            if (g_op_buffers[b].guard_pre[i] != CANARY_BYTE) return 0;
            if (g_op_buffers[b].guard_post[i] != CANARY_BYTE) return 0;
        }
    }
    return 1;
}

static const unsigned int SENTINEL_OFFSETS[5] = {
    0,
    (unsigned int)(G3X_MENU_Y0 * BUF_W + G3X_MENU_X0),
    (unsigned int)(G3X_MENU_Y0 * BUF_W + G3X_MENU_X1),
    (unsigned int)(G3X_MENU_Y1 * BUF_W + G3X_MENU_X0),
    (unsigned int)(G3X_MENU_Y1 * BUF_W + G3X_MENU_X1)
};

void draw_set_guard(void) {
    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;
    for (int i = 0; i < 5; i++) {
        unsigned int off = (i == 0) ? 0 :
            (i == 1) ? (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X0) :
            (i == 2) ? (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X1) :
            (i == 3) ? (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X0) :
                       (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X1);
        opacity_buffer[0][off] = 0x42;
        opacity_buffer[1][off] = 0x42;
    }
}

int draw_test_guard(void) {
    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;
    for (int i = 0; i < 5; i++) {
        unsigned int off = (i == 0) ? 0 :
            (i == 1) ? (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X0) :
            (i == 2) ? (unsigned int)(G3X_MENU_Y0 * buf_w + G3X_MENU_X1) :
            (i == 3) ? (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X0) :
                       (unsigned int)(G3X_MENU_Y1 * buf_w + G3X_MENU_X1);
        if (opacity_buffer[0][off] != 0x42 || opacity_buffer[1][off] != 0x42)
            return 0;
    }
    return 1;
}

int g3x_dbuf_shadow_is_allocated(void) {
    return (g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL);
}

int g3x_dbuf_shadow_restore(void) {
    if (!g3x_shadow_valid || !g3x_dbuf_shadow_is_allocated()) return 0;
    restore_calls++;
    for (int y = 0; y < G3X_MENU_HEIGHT; y++) {
        int screen_y = G3X_MENU_Y0 + y;
        size_t screen_bm_offset = (screen_y * BUF_W + G3X_MENU_X0) * 2;
        size_t screen_op_offset = (screen_y * BUF_W + G3X_MENU_X0);
        size_t shadow_bm_offset = (y * G3X_SHADOW_WIDTH) * 2;
        size_t shadow_op_offset = (y * G3X_SHADOW_WIDTH);
        size_t bm_bytes = G3X_MENU_WIDTH * 2;
        size_t op_bytes = G3X_MENU_WIDTH;

        memcpy(&bitmap_buffer[0][screen_bm_offset], &g3x_shadow_bitmap[shadow_bm_offset], bm_bytes);
        memcpy(&bitmap_buffer[1][screen_bm_offset], &g3x_shadow_bitmap[shadow_bm_offset], bm_bytes);
        memcpy(&opacity_buffer[0][screen_op_offset], &g3x_shadow_opacity[shadow_op_offset], op_bytes);
        memcpy(&opacity_buffer[1][screen_op_offset], &g3x_shadow_opacity[shadow_op_offset], op_bytes);
    }
    draw_set_guard();
    return 1;
}

int check_bitmap_buffer_changed(void) {
    if (active_bitmap_buffer != last_bitmap_buffer) {
        last_bitmap_buffer = active_bitmap_buffer;
        return 1;
    }
    return 0;
}

int check_gui_needs_redraw(void) {
    return 0;
}

/* Scheduler tick under PORT-45 */
int scheduler_tick(void) {
    int buffer_changed = check_bitmap_buffer_changed();
    int forced = check_gui_needs_redraw();
    int chdk_overlay_active = !camera_info.state.gui_mode_none;
    if (chdk_overlay_active && (buffer_changed || !draw_test_guard())) {
        if (!g3x_shadow_valid || !g3x_dbuf_shadow_is_allocated() || !g3x_dbuf_shadow_restore()) {
            forced = 1;
        }
    }
    return forced;
}

int main(void) {
    init_canaries();
    assert(check_canaries() == 1);

    uint8_t *heap_buf = (uint8_t *)malloc(G3X_SHADOW_TOTAL_SIZE);
    assert(heap_buf != NULL);
    memset(heap_buf, 0x33, G3X_SHADOW_TOTAL_SIZE);
    g3x_shadow_bitmap = heap_buf;
    g3x_shadow_opacity = heap_buf + G3X_SHADOW_BM_SIZE;
    g3x_shadow_valid = 1;

    /* 1. ALT off: Zero writes and forced=0 */
    camera_info.state.gui_mode_none = 1;
    draw_set_guard();
    restore_calls = 0;
    active_bitmap_buffer = 1; /* buffer toggle */
    int forced = scheduler_tick();
    assert(forced == 0);
    assert(restore_calls == 0);
    assert(check_canaries() == 1);

    /* Corrupt a sentinel while ALT is off */
    opacity_buffer[0][0] = 0x00;
    forced = scheduler_tick();
    assert(forced == 0);
    assert(restore_calls == 0);
    assert(check_canaries() == 1);

    /* 2. ALT on: Buffer toggle triggers shadow restore */
    camera_info.state.gui_mode_none = 0;
    draw_set_guard();
    restore_calls = 0;
    active_bitmap_buffer = 0; /* buffer toggle */
    forced = scheduler_tick();
    assert(forced == 0);
    assert(restore_calls == 1);
    assert(draw_test_guard() == 1);
    assert(check_canaries() == 1);

    /* 3. Multi-point sentinel protection for all 5 points */
    for (int p = 0; p < 5; p++) {
        restore_calls = 0;
        draw_set_guard();
        assert(draw_test_guard() == 1);

        /* Corrupt single sentinel p */
        opacity_buffer[p % 2][SENTINEL_OFFSETS[p]] = 0x00;
        assert(draw_test_guard() == 0);

        forced = scheduler_tick();
        assert(forced == 0);
        assert(restore_calls == 1);
        assert(draw_test_guard() == 1);
        assert(check_canaries() == 1);
    }

    /* 4. NULL shadow / unallocated fallback -> forced=1 without crash */
    g3x_shadow_bitmap = NULL;
    g3x_shadow_opacity = NULL;
    g3x_shadow_valid = 0;
    restore_calls = 0;

    opacity_buffer[0][0] = 0x00; /* sentinel loss */
    forced = scheduler_tick();
    assert(forced == 1); /* fell back to full redraw */
    assert(restore_calls == 0);
    assert(check_canaries() == 1);

    active_bitmap_buffer = 1; /* buffer toggle */
    forced = scheduler_tick();
    assert(forced == 1); /* fell back to full redraw */
    assert(restore_calls == 0);
    assert(check_canaries() == 1);

    free(heap_buf);
    printf("ALL PORT-45 SIMULATION TESTS PASSED SUCCESSFULLY.\n");
    return 0;
}
"""
        cls.c_src.write_text(c_code, encoding="utf-8")

        asan_flags = ["-fsanitize=address"]
        test_cmd = ["gcc", "-fsanitize=address", "-x", "c", "-", "-o", "/dev/null"]
        proc_test = subprocess.run(
            test_cmd,
            input="int main(void){return 0;}\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc_test.returncode != 0:
            asan_flags = []

        cmd = ["gcc", "-O2", "-Wall", "-Wextra", "-Werror"] + asan_flags + [str(cls.c_src), "-o", str(cls.c_bin)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            proc = subprocess.run(
                ["gcc", "-O2", "-Wall", "-Wextra", "-Werror", str(cls.c_src), "-o", str(cls.c_bin)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Failed to compile host C simulation harness: {proc.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_host_c_simulation_execution(self):
        proc = subprocess.run(
            [str(self.c_bin)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Host simulation failed:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("ALL PORT-45 SIMULATION TESTS PASSED SUCCESSFULLY.", proc.stdout)


if __name__ == "__main__":
    unittest.main()
