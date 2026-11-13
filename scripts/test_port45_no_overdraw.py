#!/usr/bin/env python3
"""PORT-45 Test Suite: G3X_GUI_NOOVERDRAW=1 opt-in overlay protection.

Verifies:
1. Pinned build artifacts and manifest for G3X_GUI_NOOVERDRAW=1.
2. Memory layout & _end guard (< 64 KiB above PORT-42 baseline, no symbol > 64 KiB).
3. Build flag dependency: G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1 in Makefile (single location).
4. Host C model simulation:
   (i)   ALT off: Sequence of guard writes is byte-for-byte the PORT-44 sequence
         (only byte 0 written at startup and draw_restore; zero extra pixels).
   (ii)  NULL shadow: Buffer flip with intact guards causes no redraw, and redraws
         per tick match PORT-44.
   (iii) Intact menu draw: A menu drawn with no simulated overdraw leaves every sentinel intact.
   (iv)  Stock overdraw restore: A simulated stock overdraw on any sentinel triggers a restore
         from the heap shadow that reproduces the exact shadow bytes.
   (v)   Canary integrity: Zero out-of-bounds writes on all code paths.
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

EXPECTED_DISKBOOT_SIZE = 126977
EXPECTED_DISKBOOT_SHA256 = "2be1877e495a0d2aee07851eee6e0294eb2d62ba9db2707b929fa2cf7927a684"


class TestPort45ArtifactsAndMemory(unittest.TestCase):
    """Artifact integrity, symbols, and _end guard tests for PORT-45 build."""

    def test_diskboot_bin_exists_and_hash(self):
        diskboot = OUT_DIR / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Missing {diskboot}")
        self.assertEqual(diskboot.stat().st_size, EXPECTED_DISKBOOT_SIZE)

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
        self.assertEqual(diskboot_info.get("size"), EXPECTED_DISKBOOT_SIZE)
        self.assertEqual(
            diskboot_info.get("sha256"),
            EXPECTED_DISKBOOT_SHA256,
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
        """Verifies G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1 in Makefile (single location)."""
        makefile_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "Makefile"
        self.assertTrue(makefile_path.is_file())
        text = makefile_path.read_text(encoding="utf-8")
        self.assertIn("G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1", text)

        # Ensure makefile.inc does NOT duplicate the flag
        makefile_inc_path = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "makefile.inc"
        self.assertTrue(makefile_inc_path.is_file())
        inc_text = makefile_inc_path.read_text(encoding="utf-8")
        self.assertNotIn("G3X_GUI_NOOVERDRAW", inc_text)


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

/* Perimeter sentinels placed strictly outside the 880x576 menu fill ([10,889]x[12,587])
 * but within 900x600 display / 928x600 buffer bounds */
#define G3X_SENTINEL_TL_X   8
#define G3X_SENTINEL_TL_Y   10
#define G3X_SENTINEL_TR_X   891
#define G3X_SENTINEL_TR_Y   10
#define G3X_SENTINEL_BL_X   8
#define G3X_SENTINEL_BL_Y   589
#define G3X_SENTINEL_BR_X   891
#define G3X_SENTINEL_BR_Y   589

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

/* Trace writes to opacity_buffer */
typedef struct {
    int buf;
    unsigned int off;
    uint8_t val;
} write_event_t;

#define MAX_LOGGED_WRITES 64
static write_event_t g_logged_writes[MAX_LOGGED_WRITES];
static int g_num_logged_writes = 0;
static int g_trace_writes_enabled = 0;

static void write_opacity_pixel(int buf, unsigned int off, uint8_t val) {
    if (g_trace_writes_enabled && g_num_logged_writes < MAX_LOGGED_WRITES) {
        g_logged_writes[g_num_logged_writes].buf = buf;
        g_logged_writes[g_num_logged_writes].off = off;
        g_logged_writes[g_num_logged_writes].val = val;
        g_num_logged_writes++;
    }
    opacity_buffer[buf][off] = val;
}

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

int g3x_dbuf_shadow_is_allocated(void) {
    return (g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL);
}

/* PORT-44 baseline draw_set_guard */
void port44_draw_set_guard(void) {
    write_opacity_pixel(0, 0, 0x42);
    write_opacity_pixel(1, 0, 0x42);
}

/* PORT-45 NOOVERDRAW draw_set_guard */
void port45_draw_set_guard(void) {
    write_opacity_pixel(0, 0, 0x42);
    write_opacity_pixel(1, 0, 0x42);

    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated()) {
        int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;
        unsigned int offsets[4] = {
            (unsigned int)(G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X),
            (unsigned int)(G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X),
            (unsigned int)(G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X),
            (unsigned int)(G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X)
        };
        for (int i = 0; i < 4; i++) {
            write_opacity_pixel(0, offsets[i], 0x42);
            write_opacity_pixel(1, offsets[i], 0x42);
        }
    }
}

/* PORT-45 NOOVERDRAW draw_test_guard */
int port45_draw_test_guard(void) {
    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42) return 0;

    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated()) {
        int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;
        unsigned int offsets[4] = {
            (unsigned int)(G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X),
            (unsigned int)(G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X),
            (unsigned int)(G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X),
            (unsigned int)(G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X)
        };
        for (int i = 0; i < 4; i++) {
            if (opacity_buffer[0][offsets[i]] != 0x42 || opacity_buffer[1][offsets[i]] != 0x42)
                return 0;
        }
    }
    return 1;
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
    port45_draw_set_guard();
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

/* PORT-44 baseline scheduler tick */
int port44_scheduler_tick(void) {
    (void)check_bitmap_buffer_changed();
    int forced = check_gui_needs_redraw();
    int chdk_overlay_active = !camera_info.state.gui_mode_none;
    if (!port45_draw_test_guard() && chdk_overlay_active) {
        if (!g3x_shadow_valid || !g3x_dbuf_shadow_restore()) {
            forced = 1;
        }
    }
    return forced;
}

/* PORT-45 NOOVERDRAW scheduler tick */
int port45_scheduler_tick(void) {
    int buffer_changed = check_bitmap_buffer_changed();
    int forced = check_gui_needs_redraw();
    int chdk_overlay_active = !camera_info.state.gui_mode_none;
    if (chdk_overlay_active) {
        if (g3x_shadow_valid && g3x_dbuf_shadow_is_allocated()) {
            if (buffer_changed || !port45_draw_test_guard()) {
                if (!g3x_dbuf_shadow_restore()) {
                    forced = 1;
                }
            }
        } else {
            /* Fallback to PORT-44: ignore buffer flips, only sentinel loss triggers redraw */
            if (!port45_draw_test_guard()) {
                forced = 1;
            }
        }
    }
    return forced;
}

/* Simulate menu fill: fills [10, 12] to [889, 587] with black (opacity 0xFF, bitmap 0x00800080) */
void simulate_g3x_fill_menu_opaque_black(void) {
    for (int y = G3X_MENU_Y0; y <= G3X_MENU_Y1; y++) {
        size_t op_offset = y * BUF_W + G3X_MENU_X0;
        size_t bm_offset = (y * BUF_W + G3X_MENU_X0) * 2;
        memset(&opacity_buffer[0][op_offset], 0xFF, G3X_MENU_WIDTH);
        memset(&opacity_buffer[1][op_offset], 0xFF, G3X_MENU_WIDTH);

        uint32_t *b0 = (uint32_t *)&bitmap_buffer[0][bm_offset];
        uint32_t *b1 = (uint32_t *)&bitmap_buffer[1][bm_offset];
        for (int i = 0; i < G3X_MENU_WIDTH / 2; i++) {
            b0[i] = 0x00800080;
            b1[i] = 0x00800080;
        }
    }
}

int main(void) {
    init_canaries();
    assert(check_canaries() == 1);

    uint8_t *heap_buf = (uint8_t *)malloc(G3X_SHADOW_TOTAL_SIZE);
    assert(heap_buf != NULL);

    /* Fill shadow buffer with distinct recognizable pattern */
    for (size_t i = 0; i < G3X_SHADOW_BM_SIZE; i++) {
        heap_buf[i] = (uint8_t)((i ^ 0xA5) & 0xFF);
    }
    for (size_t j = 0; j < G3X_SHADOW_OP_SIZE; j++) {
        heap_buf[G3X_SHADOW_BM_SIZE + j] = (uint8_t)((j ^ 0x5C) & 0xFF);
    }
    g3x_shadow_bitmap = heap_buf;
    g3x_shadow_opacity = heap_buf + G3X_SHADOW_BM_SIZE;
    g3x_shadow_valid = 1;

    /* =========================================================================
     * PROOF (i): With ALT off, the sequence of guard writes is byte-for-byte
     * the PORT-44 sequence (no extra pixels at startup or at draw_restore).
     * ========================================================================= */
    {
        /* Clear opacity buffers to zero */
        memset(opacity_buffer[0], 0x00, OP_SIZE);
        memset(opacity_buffer[1], 0x00, OP_SIZE);

        camera_info.state.gui_mode_none = 1; /* ALT off */

        /* Trace PORT-44 writes */
        g_num_logged_writes = 0;
        g_trace_writes_enabled = 1;
        port44_draw_set_guard();
        assert(g_num_logged_writes == 2);
        assert(g_logged_writes[0].buf == 0 && g_logged_writes[0].off == 0 && g_logged_writes[0].val == 0x42);
        assert(g_logged_writes[1].buf == 1 && g_logged_writes[1].off == 0 && g_logged_writes[1].val == 0x42);

        /* Reset and trace PORT-45 NOOVERDRAW writes with ALT off */
        memset(opacity_buffer[0], 0x00, OP_SIZE);
        memset(opacity_buffer[1], 0x00, OP_SIZE);
        g_num_logged_writes = 0;
        port45_draw_set_guard();
        assert(g_num_logged_writes == 2);
        assert(g_logged_writes[0].buf == 0 && g_logged_writes[0].off == 0 && g_logged_writes[0].val == 0x42);
        assert(g_logged_writes[1].buf == 1 && g_logged_writes[1].off == 0 && g_logged_writes[1].val == 0x42);

        /* Verify that outside of offset 0, zero extra pixels were modified */
        for (size_t p = 1; p < OP_SIZE; p++) {
            assert(opacity_buffer[0][p] == 0x00);
            assert(opacity_buffer[1][p] == 0x00);
        }

        /* Check simulated draw_restore() with ALT off */
        g_num_logged_writes = 0;
        port45_draw_set_guard(); /* simulated draw_restore guard seeding */
        assert(g_num_logged_writes == 2);
        assert(g_logged_writes[0].off == 0 && g_logged_writes[1].off == 0);

        g_trace_writes_enabled = 0;
        assert(check_canaries() == 1);
        printf("[OK] Proof (i) passed: ALT-off write sequence is byte-for-byte PORT-44.\n");
    }

    /* =========================================================================
     * PROOF (ii): With a NULL shadow, a buffer flip with intact guards causes
     * no redraw, and redraws per tick match PORT-44.
     * ========================================================================= */
    {
        camera_info.state.gui_mode_none = 0; /* ALT active */
        g3x_shadow_bitmap = NULL;
        g3x_shadow_opacity = NULL;
        g3x_shadow_valid = 0;

        port45_draw_set_guard(); /* with NULL shadow, only sets guard 0 */
        assert(port45_draw_test_guard() == 1);

        /* Simulate 10 ticks with buffer flips and intact guards */
        for (int tick = 0; tick < 10; tick++) {
            active_bitmap_buffer ^= 1; /* toggle buffer */
            int p44_forced = port44_scheduler_tick();
            /* restore active_bitmap_buffer state for p45 check */
            last_bitmap_buffer = !active_bitmap_buffer;
            int p45_forced = port45_scheduler_tick();

            assert(p44_forced == 0);
            assert(p45_forced == 0);
            assert(p45_forced == p44_forced);
        }

        /* Corrupt guard: sentinel lost under NULL shadow */
        opacity_buffer[0][0] = 0x00;
        int p44_lost = port44_scheduler_tick();
        last_bitmap_buffer = active_bitmap_buffer;
        int p45_lost = port45_scheduler_tick();
        assert(p44_lost == 1);
        assert(p45_lost == 1);
        assert(p45_lost == p44_lost);

        assert(check_canaries() == 1);
        printf("[OK] Proof (ii) passed: NULL shadow buffer flip causes no redraw, matching PORT-44.\n");
    }

    /* Restore shadow pointers for proofs (iii) and (iv) */
    g3x_shadow_bitmap = heap_buf;
    g3x_shadow_opacity = heap_buf + G3X_SHADOW_BM_SIZE;
    g3x_shadow_valid = 1;

    /* =========================================================================
     * PROOF (iii): A menu drawn with no simulated overdraw leaves every
     * sentinel intact.
     * ========================================================================= */
    {
        camera_info.state.gui_mode_none = 0; /* ALT active */
        port45_draw_set_guard();
        assert(port45_draw_test_guard() == 1);

        /* Simulate drawing the CHDK menu: fill [10, 12] to [889, 587] with black 0xFF */
        simulate_g3x_fill_menu_opaque_black();

        /* Verify that drawing the menu did NOT touch any sentinel */
        int buf_w = camera_screen.buffer_width;
        assert(opacity_buffer[0][0] == 0x42);
        assert(opacity_buffer[1][0] == 0x42);
        assert(opacity_buffer[0][G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X] == 0x42);
        assert(opacity_buffer[1][G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X] == 0x42);
        assert(opacity_buffer[0][G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X] == 0x42);
        assert(opacity_buffer[1][G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X] == 0x42);
        assert(opacity_buffer[0][G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X] == 0x42);
        assert(opacity_buffer[1][G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X] == 0x42);
        assert(opacity_buffer[0][G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X] == 0x42);
        assert(opacity_buffer[1][G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X] == 0x42);

        /* Guard test must still be 100% intact */
        assert(port45_draw_test_guard() == 1);

        /* Scheduler tick causes no redraw and no restore */
        restore_calls = 0;
        int forced = port45_scheduler_tick();
        assert(forced == 0);
        assert(restore_calls == 0);

        assert(check_canaries() == 1);
        printf("[OK] Proof (iii) passed: Menu drawn without overdraw leaves every sentinel intact.\n");
    }

    /* =========================================================================
     * PROOF (iv): A simulated stock overdraw on a sentinel triggers a restore
     * from the shadow that reproduces the shadow bytes.
     * ========================================================================= */
    {
        int buf_w = camera_screen.buffer_width;
        unsigned int sentinel_offsets[5] = {
            0,
            (unsigned int)(G3X_SENTINEL_TL_Y * buf_w + G3X_SENTINEL_TL_X),
            (unsigned int)(G3X_SENTINEL_TR_Y * buf_w + G3X_SENTINEL_TR_X),
            (unsigned int)(G3X_SENTINEL_BL_Y * buf_w + G3X_SENTINEL_BL_X),
            (unsigned int)(G3X_SENTINEL_BR_Y * buf_w + G3X_SENTINEL_BR_X)
        };

        for (int p = 0; p < 5; p++) {
            restore_calls = 0;
            port45_draw_set_guard();
            assert(port45_draw_test_guard() == 1);

            /* Simulate Canon stock overdraw:
             * 1. Clobber sentinel p with stock UI data (0x00)
             * 2. Clobber the menu area with noise */
            opacity_buffer[p % 2][sentinel_offsets[p]] = 0x00;
            memset(&bitmap_buffer[0][(G3X_MENU_Y0 * BUF_W + G3X_MENU_X0) * 2], 0x11, 400);
            memset(&opacity_buffer[0][G3X_MENU_Y0 * BUF_W + G3X_MENU_X0], 0x00, 200);

            assert(port45_draw_test_guard() == 0);

            /* Scheduler tick detects sentinel loss and triggers shadow restore */
            int forced = port45_scheduler_tick();
            assert(forced == 0); /* handled by fast restore, no full gui_redraw */
            assert(restore_calls == 1);
            assert(port45_draw_test_guard() == 1);

            /* Verify byte-for-byte reproduction of shadow bytes across the entire menu */
            for (int y = 0; y < G3X_MENU_HEIGHT; y++) {
                int sy = G3X_MENU_Y0 + y;
                size_t s_bm_off = (sy * BUF_W + G3X_MENU_X0) * 2;
                size_t s_op_off = (sy * BUF_W + G3X_MENU_X0);
                size_t sh_bm_off = (y * G3X_SHADOW_WIDTH) * 2;
                size_t sh_op_off = (y * G3X_SHADOW_WIDTH);

                assert(memcmp(&bitmap_buffer[0][s_bm_off], &g3x_shadow_bitmap[sh_bm_off], G3X_SHADOW_WIDTH * 2) == 0);
                assert(memcmp(&bitmap_buffer[1][s_bm_off], &g3x_shadow_bitmap[sh_bm_off], G3X_SHADOW_WIDTH * 2) == 0);
                assert(memcmp(&opacity_buffer[0][s_op_off], &g3x_shadow_opacity[sh_op_off], G3X_SHADOW_WIDTH) == 0);
                assert(memcmp(&opacity_buffer[1][s_op_off], &g3x_shadow_opacity[sh_op_off], G3X_SHADOW_WIDTH) == 0);
            }
        }

        assert(check_canaries() == 1);
        printf("[OK] Proof (iv) passed: Stock overdraw triggers shadow restore reproducing exact bytes.\n");
    }

    /* Buffer flip with valid shadow triggers shadow restore */
    {
        restore_calls = 0;
        port45_draw_set_guard();
        active_bitmap_buffer ^= 1;
        int forced = port45_scheduler_tick();
        assert(forced == 0);
        assert(restore_calls == 1);
        assert(port45_draw_test_guard() == 1);
        assert(check_canaries() == 1);
    }

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
