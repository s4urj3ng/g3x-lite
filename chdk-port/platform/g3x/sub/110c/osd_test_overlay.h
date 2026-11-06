/*
 * PORT-33: Opt-in G3X_OSD=1 test overlay candidate for Canon PowerShot G3 X (GM1.10C).
 *
 * Adapted from sibling DIGIC 6 ports (chdk-port/platform/g7x and g5x lib.c / stubs):
 * - vid_get_bitmap_fb / vid_get_bitmap_active_buffer
 * - vid_get_opacity_active_buffer
 * - vid_bitmap_refresh
 * - screen width/height/pitch (PORT-7C geometry: 720x480 visible in 736x480 buffer)
 *
 * Hardware facts & firmware addresses:
 * - active_bitmap_buffer: 0x0000D2A4 [FINSIG reference/finsig_gm110c/stubs_entry.S:186]
 * - bitmap_buffer:        0x0000D2A8 [FINSIG reference/finsig_gm110c/stubs_entry.S:188]
 * - opacity_buffer:       0xFC1837FC [ROM_VERIFIED PORT33-ROM-OPACITY-BUFFER; stubs_min.S:4]
 * - transfer_src_overlay: 0xFC380635 [FINSIG reference/finsig_gm110c/stubs_entry.S:352]
 * - CreateTask:           0xBFE14A3D [FINSIG reference/finsig_gm110c/stubs_entry.S:200]
 * - SleepTask veneer:     0xFC31BF84 [ROM_VERIFIED PORT27-ROM-SLEEPTASK-VENEER]
 * - Raised heap start:    0x00368680 [ROM_VERIFIED PORT27-ROM-HEAP-SETUP]
 *
 * Design constraints:
 * - This header defines NO symbols unless G3X_OSD is defined and == 1.
 * - Draws a filled, opaque 120x40 rectangle near top-left (16, 16) with 2px border,
 *   subtle checkerboard background, and "CHDK" text pattern.
 * - Spawns via _CreateTask per include/lolevel.h:54 once heartbeat runs.
 * - Redraws every ~1 s for >= 30 s using g3x_resident_sleep_inferred_ms(1000).
 */

#ifndef OSD_TEST_OVERLAY_H
#define OSD_TEST_OVERLAY_H

#if defined(G3X_OSD) && (G3X_OSD == 1)

#include "lolevel.h"

/* Screen geometry from PORT-7C */
#define G3X_OSD_SCREEN_WIDTH        720
#define G3X_OSD_SCREEN_HEIGHT       480
#define G3X_OSD_BUFFER_WIDTH        736
#define G3X_OSD_BUFFER_HEIGHT       480

/* Test overlay box: 120 x 40 px near top-left corner */
#define G3X_OSD_RECT_X              16
#define G3X_OSD_RECT_Y              16
#define G3X_OSD_RECT_W              120
#define G3X_OSD_RECT_H              40

/* Firmware address literals cited in docs/PORT33_OSD_ADDRESSES.md */
#define G3X_ADDR_ACTIVE_BITMAP_BUFFER 0x0000D2A4
#define G3X_ADDR_BITMAP_BUFFER        0x0000D2A8
#define G3X_ADDR_OPACITY_BUFFER       0xFC1837FC
#define G3X_ADDR_TRANSFER_OVERLAY     0xFC380635

/* DIGIC 6 UYVY color words (Byte 0: U, Byte 1: Y0, Byte 2: V, Byte 3: Y1) */
#define G3X_UYVY_WHITE              0xEB80EB80  /* Y=0xEB, U=0x80, V=0x80 */
#define G3X_UYVY_DARK               0x18801880  /* Y=0x18, U=0x80, V=0x80 */
#define G3X_UYVY_MEDIUM             0x38803880  /* Y=0x38, U=0x80, V=0x80 */

#define G3X_OPACITY_OPAQUE          0xFF

/* External framebuffer and compositor routines from platform lib.c / wrappers */
extern void *vid_get_bitmap_fb(void);
extern void *vid_get_bitmap_active_buffer(void);
extern void *vid_get_opacity_active_buffer(void);
extern void vid_bitmap_refresh(void);

/* Fixed "CHDK" text bitmap rows: 5 rows x 15 columns (1 = pixel on, 0 = off)
 * Glyphs: 'C' (3 cols), gap (1), 'H' (3 cols), gap (1), 'D' (3 cols), gap (1), 'K' (3 cols) */
static const unsigned short g3x_chdk_glyph_rows[5] = {
    0x7565, /* 0b0111_0101_0110_0101:  ***  * *  **   * * */
    0x4555, /* 0b0100_0101_0101_0101:  *    * *  * *  * * */
    0x4756, /* 0b0100_0111_0101_0110:  *    ***  * *  **  */
    0x4555, /* 0b0100_0101_0101_0101:  *    * *  * *  * * */
    0x7565  /* 0b0111_0101_0110_0101:  ***  * *  **   * * */
};

static inline __attribute__((always_inline)) void g3x_osd_draw_test_overlay(void)
{
    unsigned char *op_buf = (unsigned char *)vid_get_opacity_active_buffer();
    unsigned char *bm_buf = (unsigned char *)vid_get_bitmap_fb();

    if (!op_buf || !bm_buf) {
        return;
    }

    for (int y = 0; y < G3X_OSD_RECT_H; y++) {
        int py = G3X_OSD_RECT_Y + y;
        unsigned char *op = op_buf + (py * G3X_OSD_BUFFER_WIDTH + G3X_OSD_RECT_X);
        unsigned int *bm = (unsigned int *)(bm_buf + (py * G3X_OSD_BUFFER_WIDTH + G3X_OSD_RECT_X) * 2);

        /* Set 120 pixels in opacity buffer to 0xFF (opaque) */
        for (int x = 0; x < G3X_OSD_RECT_W; x++) {
            op[x] = G3X_OPACITY_OPAQUE;
        }

        int border_y = (y < 2 || y >= G3X_OSD_RECT_H - 2);
        int text_row = (y - 10) >> 2; /* 5 font rows scaled 4x vertically (y in 10..29) */
        int in_text_y = (y >= 10 && y < 30);
        unsigned short row_mask = in_text_y ? g3x_chdk_glyph_rows[text_row] : 0;

        for (int p = 0; p < (G3X_OSD_RECT_W / 2); p++) {
            if (border_y || p < 1 || p >= (G3X_OSD_RECT_W / 2) - 1) {
                bm[p] = G3X_UYVY_WHITE; /* Contrasting white 2px border */
                continue;
            }

            /* "CHDK" text centered horizontally at p in [15..44] (30 pixel pairs = 60 px) */
            int bit_idx = (p - 15) >> 1; /* Each glyph bit is 4 px wide = 2 pairs */
            if (in_text_y && p >= 15 && p < 45 && (row_mask & (1 << (14 - bit_idx)))) {
                bm[p] = G3X_UYVY_WHITE; /* Bright white text "CHDK" */
            } else {
                /* Checkerboard background in 8x8 blocks */
                int cb = ((p >> 2) ^ (y >> 3)) & 1;
                bm[p] = cb ? G3X_UYVY_MEDIUM : G3X_UYVY_DARK;
            }
        }
    }

    vid_bitmap_refresh();
}

void __attribute__((noinline)) g3x_resident_osd_task(void)
{
    /* Redraw test overlay every ~1 s for at least 30 s */
    for (;;) {
        g3x_osd_draw_test_overlay();
        g3x_resident_sleep_inferred_ms(1000);
    }
}

static inline __attribute__((always_inline)) void g3x_spawn_osd_task(void)
{
    /* Create second CHDK task to draw OSD overlay per include/lolevel.h:54
     * r0 = "OSDOverlay" [INFERRED task name string]
     * r1 = 0x19 (25)    [VERIFIED priority, equal to heartbeat / startup tasks]
     * r2 = 0x2000       [VERIFIED explicit stack size, 8192 bytes]
     * r3 = g3x_resident_osd_task
     * parm = 0
     * Callee: CreateTask via _CreateTask at 0xBFE14A3D */
    _CreateTask("OSDOverlay", G3X_RESIDENT_PRIORITY, G3X_RESIDENT_STACK_SIZE, g3x_resident_osd_task, 0);
}

#endif /* G3X_OSD */

#endif /* OSD_TEST_OVERLAY_H */
