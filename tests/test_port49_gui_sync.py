"""Offline unit and integration tests for PORT-49 (G3X_GUI_SYNC=1)."""

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
SYNC_HEADER = ROOT / "chdk-port/platform/g3x/sub/110c/gui_sync.h"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
DOC_SYNC = ROOT / "docs/PORT49_GUI_SYNC.md"
DOC_TRIAL = ROOT / "docs/PORT49_TRIAL.md"
EVIDENCE_MANIFEST = ROOT / "manifests/port49_gui_sync_evidence.json"
MANIFEST = ROOT / "manifests/port49_gui_sync_manifest.json"
PORT41_MANIFEST = ROOT / "manifests/port41_manifest.json"
PORT48_MANIFEST = ROOT / "manifests/port48_shadow_alloc_manifest.json"
PRIMARY_ROM = ROOT / "firmware/dumps/GM1.10C/PRIMARY.BIN"
OUT = ROOT / "out/port49-test"
TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_CANONICAL_DISKBOOT_SHA256 = "3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72"
BASE_CANONICAL_DISKBOOT_SIZE = 116073
BASE_PORT41_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_PORT41_DEFAULT_SIZE = 124097
BASE_PORT48_SHA256 = "9ac53c2720f96e40b6ff95e64ed069139c80c170d521a0e4fc01dd9c03ad4db1"


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


class TestPort49FlagPlumbingAndRomEvidence(unittest.TestCase):
    def test_flag_plumbing_rejects_missing_prerequisites_and_accepts_full_stack(self):
        required = [
            "G3X_GUI_DBUF",
            "G3X_GUI_NOOVERDRAW",
            "G3X_KBD_CHECK",
            "G3X_GUI_DIAG",
            "G3X_GUI_SHADOW2",
        ]
        for missing in required:
            with self.subTest(missing=missing):
                c_flags = ["-DG3X_GUI_SYNC=1"] + [
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
                        "G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

                make_args = ["G3X_GUI_SYNC=1"] + [
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
                        "G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1",
                        res.stderr,
                    )

        full_c_flags = ["-DG3X_GUI_SYNC=1"] + [f"-D{f}=1" for f in required]
        for hdr in (DIAG_HEADER, SYNC_HEADER):
            res = subprocess.run(
                ["cc", "-E", *full_c_flags, "-I", str(DIAG_HEADER.parent), "-x", "c", str(hdr)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_hook_address_and_rom_bytes_match_recorded_evidence_and_doc_answer_c(self):
        self.assertTrue(DOC_SYNC.is_file(), f"Missing {DOC_SYNC}")
        self.assertTrue(EVIDENCE_MANIFEST.is_file(), f"Missing {EVIDENCE_MANIFEST}")
        self.assertTrue(SYNC_HEADER.is_file(), f"Missing {SYNC_HEADER}")

        doc_text = DOC_SYNC.read_text(encoding="utf-8")
        sync_text = SYNC_HEADER.read_text(encoding="utf-8")
        evidence = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))

        # Verify answer (c) in docs/PORT49_GUI_SYNC.md selects 0x0000E26C, 0xFC143493, 0xFC380675, sp_entry[23] (#92)
        self.assertIn("### (c) Which hook method fits best, and what is the exact hook point?", doc_text)
        self.assertIn("`0x0000E26C`", doc_text)
        self.assertIn("`0xFC143493`", doc_text)
        self.assertIn("0xFC380675", doc_text)
        self.assertIn("`sp_entry[23]` (`[sp_entry, #92]`", doc_text)

        # Verify constants in chdk-port/platform/g3x/sub/110c/gui_sync.h match answer (c)
        parsed_macros = {
            name: int(val.rstrip("uU"), 0)
            for name, val in re.findall(
                r"^#define\s+(G3X_GUI_SYNC_\w+)\s+(0x[0-9a-fA-F]+u?|\d+u?)\s*$",
                sync_text,
                re.M,
            )
        }
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_CALLBACK_PTR_ADDR"], 0x0000E26C)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_HELPER_ADDR"], 0xFC143493)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_SETTER_ADDR"], 0xFC143481)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_TRANSFER_ADDR"], 0xFC380635)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_CALLER_LR"], 0xFC380675)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_VTM_CALLER_LR"], 0xFC3809DF)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_MAKE_OSD_CALL_ADDR"], 0xFC3806F2)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_FLIP_COMMIT_ADDR"], 0xFC38090B)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_ACTIVE_BM_ADDR"], 0x0000D2A4)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_HELPER_LR_WORD_IDX"], 1)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_HELPER_LR_BYTE_OFF"], 4)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_RET_LR_WORD_IDX"], 23)
        self.assertEqual(parsed_macros["G3X_GUI_SYNC_RET_LR_BYTE_OFF"], 92)
        self.assertEqual(8 + 60 + 6 * 4, parsed_macros["G3X_GUI_SYNC_RET_LR_BYTE_OFF"])
        self.assertEqual(
            parsed_macros["G3X_GUI_SYNC_RET_LR_WORD_IDX"] * 4,
            parsed_macros["G3X_GUI_SYNC_RET_LR_BYTE_OFF"],
        )

        # Check ROM evidence slices in manifests/port49_gui_sync_evidence.json and PRIMARY.BIN
        self.assertTrue(PRIMARY_ROM.is_file(), f"Missing {PRIMARY_ROM}")
        rom_bytes = PRIMARY_ROM.read_bytes()

        # Verify all 24 bounded slices in manifests/port49_gui_sync_evidence.json match PRIMARY.BIN
        ranges = evidence["rom_ranges_read"]
        self.assertEqual(len(ranges), 24)
        for r in ranges:
            start_addr = int(r["start"], 16)
            off = start_addr - 0xFC000000
            length = r["length"]
            chunk = rom_bytes[off : off + length]
            self.assertEqual(hashlib.sha256(chunk).hexdigest(), r["sha256"])

        def get_rom_bytes(addr: int, length: int) -> bytes:
            matching = [
                r for r in ranges
                if int(r["start"], 16) <= addr and (addr + length - 1) <= int(r["end"], 16)
            ]
            self.assertTrue(
                matching,
                f"Requested ROM range {hex(addr)}..{hex(addr + length - 1)} not covered by evidence manifest",
            )
            off = addr - 0xFC000000
            return rom_bytes[off : off + length]

        # 1. GraphicSystemCoreFinish_helper (0xFC143492..0xFC1434A7)
        # 0xFC143492: push {r4, lr} (10 b5)
        # 0xFC143494: movs r4, #0 (00 24)
        # 0xFC143496: bl 0xFC20C5BE (c9 f0 92 f8)
        # 0xFC14349A: ldr r0, [pc, #12] (03 48 -> literal pool at 0xFC1434A8)
        # 0xFC14349C: ldr r0, [r0, #0] (00 68)
        # 0xFC14349E: cbz r0, 0xFC1434A4 (08 b1)
        # 0xFC1434A0: blx r0 (80 47)
        # 0xFC1434A2: mov r4, r0 (04 46)
        # 0xFC1434A4: mov r0, r4 (20 46)
        # 0xFC1434A6: pop {r4, pc} (10 bd)
        self.assertEqual(
            get_rom_bytes(0xFC143492, 22),
            bytes.fromhex("10b50024c9f092f80348006808b180470446204610bd"),
        )
        # Literal pool at 0xFC1434A8 holds 0x0000E26C (little-endian: 6c e2 00 00)
        self.assertEqual(
            int.from_bytes(get_rom_bytes(0xFC1434A8, 4), "little"),
            0x0000E26C,
        )
        # ROM data copy initial value at 0xFCE972C4 for RAM 0x0000E26C is 0x00000000
        self.assertEqual(
            int.from_bytes(get_rom_bytes(0xFCE972C4, 4), "little"),
            0x00000000,
        )

        # 2. transfer_src_overlay (0xFC380634..0xFC3806FB)
        # 0xFC380634: stmdb sp!, {r4-r9, lr} (2d e9 f0 43)
        # 0xFC380638: sub sp, #60 (8f b0)
        # 0xFC38063A: mov r9, r0 (81 46)
        self.assertEqual(
            get_rom_bytes(0xFC380634, 8),
            bytes.fromhex("2de9f0438fb08146"),
        )
        # 0xFC380670: bl 0xFC143492 (c2 f5 0f ff) -> next instruction at 0xFC380674 (Thumb lr = 0xFC380675)
        self.assertEqual(
            get_rom_bytes(0xFC380670, 4),
            bytes.fromhex("c2f50fff"),
        )
        # 0xFC3806F2: bl 0xFC183A12 (MakeOsdVram, 03 f6 8e f9)
        # 0xFC3806F6: add sp, #60 (0f b0)
        # 0xFC3806F8: ldmia.w sp!, {r4-r9, pc} (bd e8 f0 83)
        self.assertEqual(
            get_rom_bytes(0xFC3806F2, 10),
            bytes.fromhex("03f68ef90fb0bde8f083"),
        )

        # 3. VTM_FlipAndCommit (0xFC38090A..0xFC380C4F)
        # 0xFC38091E: str r0, [r5, #64] (28 64) where literal pool 0xFC380C4C = 0x0000D2B8 (-0x54 + 0x40 = 0x0000D2A4)
        self.assertEqual(
            get_rom_bytes(0xFC38091E, 2),
            bytes.fromhex("2864"),
        )
        self.assertEqual(
            int.from_bytes(get_rom_bytes(0xFC380C4C, 4), "little") - 0x54 + 0x40,
            0x0000D2A4,
        )

        # 4. Verify INFERRED citations in gui_sync.h
        self.assertIn("INFERRED", sync_text)
        self.assertIn("docs/PORT49_GUI_SYNC.md", sync_text)
        self.assertIn("manifests/port49_gui_sync_evidence.json", sync_text)


class TestPort49HostSyncBehavior(unittest.TestCase):
    def test_sync_hook_blits_target_buffer_only_and_preserves_poll_fallback(self):
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define G3X_GUI_DBUF 1
#define G3X_GUI_NOOVERDRAW 1
#define G3X_KBD_CHECK 1
#define G3X_GUI_DIAG 1
#define G3X_GUI_SHADOW2 1
#define G3X_GUI_SYNC 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1

#define FONT_WIDTH 16
#define FONT_HEIGHT 32
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define MAKE_COLOR(bg, fg) (((bg) << 8) | (fg))
#define MEMINFO_H 1

typedef short coord;
typedef unsigned short color;
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
    int size;
    int disp_left;
    int disp_width;
} camera_screen = {900, 600, 928, 928 * 600, 0, 900};

int active_bitmap_buffer = 0;

static unsigned char bm0[928 * 600 * 2];
static unsigned char bm1[928 * 600 * 2];
static unsigned char op0[928 * 600];
static unsigned char op1[928 * 600];
char *bitmap_buffer[2] = { (char *)bm0, (char *)bm1 };
volatile char *opacity_buffer[2] = { (volatile char *)op0, (volatile char *)op1 };

static unsigned char backing_exmem[928 * 600 * 3];
static unsigned char backing_rect[880 * 576 * 3];
static unsigned char backing_idx[880 * 576];

static int allow_exmem = 1;
static int allow_rect = 0;
static int allow_idx = 0;
static int exmem_calls = 0;
static int malloc_calls = 0;
static int umalloc_calls = 0;
static int redraw_calls = 0;

void *exmem_alloc_cached(unsigned int pool_id, unsigned int size, int unk, int unk2)
{
    (void)pool_id; (void)unk; (void)unk2;
    ++exmem_calls;
    if (allow_exmem && size == sizeof(backing_exmem))
        return backing_exmem;
    return 0;
}

static void *test_malloc(size_t size)
{
    ++malloc_calls;
    if (allow_rect && size == sizeof(backing_rect))
        return backing_rect;
    if (allow_idx && size == sizeof(backing_idx))
        return backing_idx;
    return 0;
}

static void *test_umalloc(size_t size)
{
    ++umalloc_calls;
    if (allow_rect && size == sizeof(backing_rect))
        return backing_rect;
    if (allow_idx && size == sizeof(backing_idx))
        return backing_idx;
    return 0;
}

#define malloc test_malloc
#define umalloc test_umalloc

void GetMemInfo(cam_meminfo *info)
{
    memset(info, 0, sizeof(*info));
    info->free_block_max_size = 360448;
}

static unsigned char *sh_bm = 0;
static unsigned char *sh_op = 0;
static int sh_valid = 0;
static int sh_attempted = 0;

int g3x_dbuf_shadow_is_allocated(void)
{
    return (sh_bm != 0 && sh_op != 0) ? 1 : 0;
}

void draw_set_guard(void);
int draw_test_guard(void);
void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl)
{
    (void)x1; (void)y1; (void)x2; (void)y2; (void)cl;
}

static char last_diag_line[128];
static int last_draw_x = -1, last_draw_y = -1;
static void draw_string(int x, int y, const char *s, int c)
{
    (void)c;
    last_draw_x = x;
    last_draw_y = y;
    strcpy(last_diag_line, s);
}

#include "gui_diag.h"

void draw_set_guard(void)
{
    g3x_sync_set_guard_target(0u);
    g3x_sync_set_guard_target(1u);
}

int draw_test_guard(void)
{
    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42)
        return 0;
    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated())
    {
        int buf_w = camera_screen.buffer_width;
        unsigned int offs[4] = {
            (unsigned int)(10 * buf_w + 8),
            (unsigned int)(10 * buf_w + 891),
            (unsigned int)(589 * buf_w + 8),
            (unsigned int)(589 * buf_w + 891),
        };
        for (int i = 0; i < 4; ++i)
        {
            if ((unsigned char)opacity_buffer[0][offs[i]] != 0x42 ||
                (unsigned char)opacity_buffer[1][offs[i]] != 0x42)
                return 0;
        }
    }
    return 1;
}

void g3x_dbuf_shadow_ensure_allocated(void)
{
    g3x_diag_shadow_ensure_allocated(&sh_bm, &sh_op, &sh_valid, &sh_attempted);
}

int g3x_dbuf_shadow_restore(void)
{
    if (!g3x_dbuf_shadow_is_allocated() || camera_info.state.gui_mode_none)
        return 0;
    if (!g3x_shadow2_blit_restore(sh_bm, sh_op, camera_screen.buffer_width))
        return 0;
    draw_set_guard();
    g3x_diag_record_shadow_restore();
    return 1;
}

int g3x_dbuf_shadow_sync_restore(unsigned int target_idx)
{
    if (!g3x_dbuf_shadow_is_allocated() || camera_info.state.gui_mode_none)
        return 0;
    if (!g3x_shadow2_blit_restore_target(sh_bm, sh_op, camera_screen.buffer_width, target_idx))
        return 0;
    g3x_sync_set_guard_target(target_idx);
    g3x_diag_record_shadow_restore();
    return 1;
}

void gui_redraw(int enforce)
{
    (void)enforce;
    ++redraw_calls;
}

int main(void)
{
    camera_info.state.gui_mode_none = 1;
    camera_info.state.gui_mode_alt = 0;

    /* 1. Install hook at 0x0000E26C (host backing ptr) */
    g3x_gui_sync_install_hook();
    assert(g3x_gui_sync_is_hook_installed() == 1);
    assert(g3x_diag_hook_installed == 1u);

    /* 2. Non-transfer_src_overlay caller (e.g. VTMUnLock_flush 0xFC3809DF) is ignored */
    unsigned int sp_frame[24];
    memset(sp_frame, 0, sizeof(sp_frame));
    sp_frame[G3X_GUI_SYNC_HELPER_LR_WORD_IDX] = G3X_GUI_SYNC_VTM_CALLER_LR;
    sp_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] = 0xFC380A0Du;
    assert(g3x_gui_sync_pre_frame_check(sp_frame, 1u) == 0);
    assert(sp_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] == 0xFC380A0Du);
    assert(g3x_gui_sync_in_flight == 0u);

    /* 3. transfer_src_overlay caller (0xFC380675) with ALT off intercepts lr, increments Y, does no blit/alloc */
    sp_frame[G3X_GUI_SYNC_HELPER_LR_WORD_IDX] = G3X_GUI_SYNC_CALLER_LR;
    sp_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] = 0xFC380723u;
    assert(g3x_gui_sync_pre_frame_check(sp_frame, 1u) == 1);
    assert(g3x_gui_sync_in_flight == 1u);
    assert(g3x_gui_sync_saved_lr == 0xFC380723u);
    assert(g3x_gui_sync_target_buf == 1u);
    assert(sp_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] == (((unsigned int)(unsigned long)&g3x_gui_sync_post_trampoline) | 1u));

    /* Re-entrancy guard rejects nested call while in flight */
    unsigned int nested_frame[24];
    memset(nested_frame, 0, sizeof(nested_frame));
    nested_frame[G3X_GUI_SYNC_HELPER_LR_WORD_IDX] = G3X_GUI_SYNC_CALLER_LR;
    nested_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] = 0xFC381179u;
    assert(g3x_gui_sync_pre_frame_check(nested_frame, 0u) == 0);
    assert(nested_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] == 0xFC381179u);

    unsigned int ret_lr = g3x_gui_sync_post_c();
    assert(ret_lr == 0xFC380723u);
    assert(g3x_gui_sync_in_flight == 0u);
    assert(g3x_diag_get_sync_hits() == 1u);
    assert(g3x_diag_shadow_restore_count == 0u);
    assert(exmem_calls == 0 && malloc_calls == 0 && umalloc_calls == 0);

    /* 4. Enter ALT: allocates exmem shadow and re-verifies hook */
    camera_info.state.gui_mode_none = 0;
    camera_info.state.gui_mode_alt = 1;
    g3x_diag_on_alt_enter();
    assert(g3x_shadow2_mode == G3X_SHADOW_MODE_EXMEM);
    assert(exmem_calls == 1);
    draw_set_guard();

    /* Write test pixels into shadow at (100, 100) */
    g3x_shadow2_write_pixel(sh_bm, sh_op, 100, 100, 0xAA, 0xFF, 0x55, 0x66, 0, 1);
    unsigned int test_off_op = 100u * 928u + 100u;
    unsigned int test_off_bm = test_off_op * 2u;

    /* Simulate MakeOsdVram DMA wiping ONLY inactive buffer 1 while buffer 0 keeps distinct marker */
    memset(op1, 0, sizeof(op1));
    memset(bm1, 0, sizeof(bm1));
    op0[test_off_op] = 0x11;
    bm0[test_off_bm + 1] = 0x22;

    int prev_exmem = exmem_calls, prev_malloc = malloc_calls, prev_umalloc = umalloc_calls;
    sp_frame[G3X_GUI_SYNC_HELPER_LR_WORD_IDX] = G3X_GUI_SYNC_CALLER_LR;
    sp_frame[G3X_GUI_SYNC_RET_LR_WORD_IDX] = 0xFC380723u;
    assert(g3x_gui_sync_pre_frame_check(sp_frame, 1u) == 1);
    ret_lr = g3x_gui_sync_post_c();
    assert(ret_lr == 0xFC380723u);

    /* Target buffer 1 was restored synchronously from shadow, while buffer 0 was untouched! */
    assert(op1[test_off_op] == 0xFF);
    assert(bm1[test_off_bm + 0] == 0x55);
    assert(bm1[test_off_bm + 1] == 0xAA);
    assert(bm1[test_off_bm + 2] == 0x66);
    assert(op0[test_off_op] == 0x11);
    assert(bm0[test_off_bm + 1] == 0x22);

    /* Zero allocations occurred in the sync hook path */
    assert(exmem_calls == prev_exmem && malloc_calls == prev_malloc && umalloc_calls == prev_umalloc);
    assert(g3x_diag_get_sync_hits() == 2u);
    assert(g3x_diag_shadow_restore_count == 1u);

    /* Sentinels on buffer 1 were restored by sync hook, so draw_test_guard() is 1 and poll is a no-op */
    assert(draw_test_guard() == 1);
    assert(g3x_diag_restore_overlay(0) == 0);
    assert(g3x_diag_sentinel_loss_count == 0u);
    assert(g3x_diag_shadow_restore_count == 1u);

    /* 5. Poll fallback: if buffer 0 loses its sentinel outside transfer_src_overlay, poll restores both */
    opacity_buffer[0][0] = 0x00;
    assert(draw_test_guard() == 0);
    assert(g3x_diag_restore_overlay(0) == 0);
    assert(g3x_diag_sentinel_loss_count == 1u);
    assert(g3x_diag_shadow_restore_count == 2u);
    assert(draw_test_guard() == 1);
    assert(op0[test_off_op] == 0xFF);

    /* 6. Verify DIAG line format includes H, S, L, R, F, M, and Y within <= 55 chars */
    gui_diag_draw();
    assert(strlen(last_diag_line) <= G3X_DIAG_LINE_MAX_CHARS);
    assert(last_draw_x >= 10 && (last_draw_x + (int)strlen(last_diag_line) * FONT_WIDTH) <= 890);
    assert(last_draw_y == 600 - 2 * FONT_HEIGHT);
    assert(strstr(last_diag_line, "H:1/0003") != 0);
    assert(strstr(last_diag_line, "S:OK/exmem") != 0);
    assert(strstr(last_diag_line, "L:0001") != 0);
    assert(strstr(last_diag_line, "R:0002") != 0);
    assert(strstr(last_diag_line, "F:0000") != 0);
    assert(strstr(last_diag_line, "M:0000") != 0);
    assert(strstr(last_diag_line, "Y:0002") != 0);

    /* 7. Also verify RECT and IDX modes in g3x_shadow2_blit_restore_target */
    sh_bm = sh_op = 0; sh_valid = sh_attempted = 0;
    allow_exmem = 0; allow_rect = 1; allow_idx = 0;
    g3x_diag_on_alt_enter();
    assert(g3x_shadow2_mode == G3X_SHADOW_MODE_RECT);
    g3x_shadow2_write_pixel(sh_bm, sh_op, 50, 50, 0x77, 0xEE, 0x33, 0x44, 0, 2);
    memset(op0, 0, sizeof(op0));
    memset(bm0, 0, sizeof(bm0));
    assert(g3x_dbuf_shadow_sync_restore(0u) == 1);
    unsigned int off50 = 50u * 928u + 50u;
    assert(op0[off50] == 0xEE);
    assert(bm0[off50 * 2u + 1] == 0x77);

    sh_bm = sh_op = 0; sh_valid = sh_attempted = 0;
    allow_exmem = 0; allow_rect = 0; allow_idx = 1;
    g3x_diag_on_alt_enter();
    assert(g3x_shadow2_mode == G3X_SHADOW_MODE_IDX);
    g3x_shadow2_write_pair(sh_bm, sh_op, 60, 60, 0, 0, 1, 1);
    memset(op1, 0, sizeof(op1));
    memset(bm1, 0, sizeof(bm1));
    assert(g3x_dbuf_shadow_sync_restore(1u) == 1);
    unsigned int off60 = 60u * 928u + 60u;
    assert(op1[off60] == 255);
    assert(op1[off60 + 1] == 255);

    return 0;
}
'''
        OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUT) as td:
            cfile = Path(td) / "test_sync.c"
            exe = Path(td) / "test_sync"
            cfile.write_text(source, encoding="utf-8")
            res = subprocess.run(
                [
                    "cc",
                    "-std=c99",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(DIAG_HEADER.parent),
                    str(cfile),
                    "-o",
                    str(exe),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            subprocess.run([str(exe)], check=True)


class TestPort49BuildsAndTrialDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.build_a = OUT / "build-a"
        cls.build_b = OUT / "build-b"
        cls.build_default = OUT / "build-default"
        cls.build_port48 = OUT / "build-port48"

        env = os.environ.copy()
        for k in [
            "G3X_GUI_FIX",
            "G3X_GUI_DBUF",
            "G3X_GUI_NOOVERDRAW",
            "G3X_KBD_CHECK",
            "G3X_GUI_DIAG",
            "G3X_GUI_SHADOW2",
            "G3X_GUI_SYNC",
            "FULL_HOOKS",
            "MAKEFLAGS",
        ]:
            env.pop(k, None)

        for target, extra in ((cls.build_a, []), (cls.build_b, ["--discard-stage"])):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--gui-sync",
                    *extra,
                    "--out-dir",
                    str(target),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
            )

        # Build default full build (no flags) to verify byte-identity with base
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

        # Build PORT-48 (--shadow2 without --gui-sync) to verify byte-identity with PORT-48 manifest
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/build_port43_dbuf.py"),
                "--shadow2",
                "--discard-stage",
                "--out-dir",
                str(cls.build_port48),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_clean_gui_sync_builds_are_byte_identical_and_match_manifest(self):
        self.assertTrue(MANIFEST.is_file(), f"Missing {MANIFEST}")
        pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))
        gen_a = json.loads((self.build_a / "port49_gui_sync_manifest.json").read_text(encoding="utf-8"))
        gen_b = json.loads((self.build_b / "port49_gui_sync_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(pinned, gen_a)
        self.assertEqual(pinned, gen_b)

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
        ]
        self.assertEqual(pinned["build"]["flags"], expected_flags)
        self.assertEqual(pinned["core_end"], pinned["artifacts"]["core_end"])
        self.assertRegex(pinned["core_end"], r"^0x003[0-9a-f]{5}$")

        snap_a = distribution_snapshot(self.build_a)
        snap_b = distribution_snapshot(self.build_b)
        self.assertEqual(snap_a, snap_b)

        expected = dict(pinned["artifacts"]["chdk_files"])
        expected["DISKBOOT.BIN"] = {
            k: pinned["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")
        }
        self.assertEqual(snap_a, expected)
        self.assertEqual(pinned["artifacts"]["chdk_files_count"], len(snap_a) - 1)

    def test_default_and_port48_builds_are_byte_identical_to_base(self):
        # Canonical in-tree chdk-port/bin/DISKBOOT.BIN is untouched and byte-identical to base
        canonical_diskboot = ROOT / "chdk-port/bin/DISKBOOT.BIN"
        self.assertEqual(canonical_diskboot.stat().st_size, BASE_CANONICAL_DISKBOOT_SIZE)
        self.assertEqual(sha256_file(canonical_diskboot), BASE_CANONICAL_DISKBOOT_SHA256)

        # Default full build (no opt-in flags) matches base PORT-41 manifest byte-for-byte
        default_diskboot = self.build_default / "DISKBOOT.BIN"
        self.assertEqual(default_diskboot.stat().st_size, BASE_PORT41_DEFAULT_SIZE)
        self.assertEqual(sha256_file(default_diskboot), BASE_PORT41_DEFAULT_SHA256)
        port41_pinned = json.loads(PORT41_MANIFEST.read_text(encoding="utf-8"))
        default_snap = distribution_snapshot(self.build_default)
        expected_p41 = dict(port41_pinned["artifacts"]["chdk_files"])
        expected_p41["DISKBOOT.BIN"] = {
            k: port41_pinned["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")
        }
        self.assertEqual(default_snap, expected_p41)

        # PORT-48 build (--shadow2 without --gui-sync) matches PORT-48 manifest
        port48_pinned = json.loads(PORT48_MANIFEST.read_text(encoding="utf-8"))
        port48_snap = distribution_snapshot(self.build_port48)
        expected_p48 = dict(port48_pinned["artifacts"]["chdk_files"])
        expected_p48["DISKBOOT.BIN"] = {
            k: port48_pinned["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")
        }
        self.assertEqual(port48_snap, expected_p48)
        self.assertEqual(
            sha256_file(self.build_port48 / "DISKBOOT.BIN"),
            BASE_PORT48_SHA256,
        )

    def test_elf_disassembly_verifies_hook_install_and_bounded_trampoline(self):
        elf = self.build_a / "stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(elf.is_file(), f"Missing {elf}")

        nm_out = subprocess.check_output([str(NM), "-S", str(elf)], text=True)
        end_match = re.search(r"^([0-9a-f]+) B _end$", nm_out, re.M)
        self.assertIsNotNone(end_match)
        end_addr = int(end_match.group(1), 16)
        self.assertLessEqual(end_addr, 0x003687B0 + 65536)

        for sym in (
            "g3x_gui_sync_install_hook",
            "g3x_gui_sync_pre_cb",
            "g3x_gui_sync_post_trampoline",
            "g3x_gui_sync_post_c",
            "g3x_dbuf_shadow_sync_restore",
            "g3x_shadow2_blit_restore_target",
        ):
            self.assertRegex(nm_out, rf"\bT {sym}\b")

        disasm = subprocess.check_output([str(OBJDUMP), "-d", str(elf)], text=True)

        def func_body(name: str) -> str:
            m = re.search(rf"^[0-9a-f]+ <{name}>:\n(.*?)(?:\n\n|\Z)", disasm, re.M | re.S)
            self.assertIsNotNone(m, f"Function {name} not found in disassembly")
            return m.group(1)

        # boot() calls g3x_gui_sync_install_hook
        boot_body = func_body("boot")
        self.assertIn("<g3x_gui_sync_install_hook>", boot_body)

        # g3x_gui_sync_install_hook writes g3x_gui_sync_pre_cb | 1 to 0x0000E26C
        install_body = func_body("g3x_gui_sync_install_hook")
        self.assertIn("0xe26c", install_body)

        # g3x_gui_sync_pre_cb checks [sp, #4] == 0xFC380675, reads/writes [sp, #92] (0x5c), reads r9
        pre_body = func_body("g3x_gui_sync_pre_cb")
        self.assertIn("[sp, #4]", pre_body)
        self.assertIn("fc380675", pre_body)
        self.assertIn("[sp, #92]", pre_body)
        self.assertRegex(pre_body, r"mov\s+r3,\s*r9")

        # g3x_gui_sync_post_trampoline preserves registers, calls g3x_gui_sync_post_c, branches via bx ip
        tramp_body = func_body("g3x_gui_sync_post_trampoline")
        self.assertIn("<g3x_gui_sync_post_c>", tramp_body)
        self.assertIn("bx\tip", tramp_body)

        # Hook execution path has no allocator, sleep, task creation, or full gui_redraw calls
        for fn in (
            "g3x_gui_sync_pre_cb",
            "g3x_gui_sync_post_trampoline",
            "g3x_gui_sync_post_c",
            "g3x_dbuf_shadow_sync_restore",
            "g3x_shadow2_blit_restore_target",
        ):
            body = func_body(fn)
            for forbidden in (
                "<malloc>",
                "<umalloc>",
                "<exmem_alloc_cached>",
                "<_exmem_alloc>",
                "<msleep>",
                "<_SleepTask>",
                "<CreateTask",
                "<gui_redraw>",
            ):
                self.assertNotIn(forbidden, body, f"Forbidden call {forbidden} in {fn}")

    def test_trial_doc_contains_required_steps_criteria_and_rollback(self):
        self.assertTrue(DOC_TRIAL.is_file(), f"Missing {DOC_TRIAL}")
        text = DOC_TRIAL.read_text(encoding="utf-8")
        pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))
        diskboot_sha = pinned["artifacts"]["DISKBOOT.BIN"]["sha256"]

        self.assertIn(diskboot_sha, text)
        self.assertIn(pinned["core_end"], text)
        self.assertIn("Held press", text)
        self.assertIn("Short press", text)
        self.assertIn("<ALT>", text)
        self.assertIn("Pan and trigger AF", text)
        for tok in ("H:", "S:OK/exmem", "L:", "R:", "F:", "M:", "Y:"):
            self.assertIn(tok, text)
        self.assertIn("CONFIRMED", text)
        self.assertIn("REFUTED", text)
        self.assertIn("pull the battery", text)
        self.assertIn("9ac53c27", text)


if __name__ == "__main__":
    unittest.main()
