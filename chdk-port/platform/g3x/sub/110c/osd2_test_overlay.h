#ifndef G3X_OSD2_TEST_OVERLAY_H
#define G3X_OSD2_TEST_OVERLAY_H

/* =============================================================================
 * PORT-35 Part A: Opt-in OSD2 Test Overlay (G3X_OSD2=1)
 *
 * Adapted from DIGIC 6 siblings:
 * - chdk-port/platform/g7x/lib.c:5-20,261-358
 * - chdk-port/platform/g5x/lib.c:6-34,162-204
 * - chdk-port/platform/g7x/platform_camera.h:47-65
 * - chdk-port/core/gui_draw.c:13-38,71-95,120-141,420-425
 *
 * Fixes the three root causes of the PORT-34 G3X_KBD=1 G3X_OSD=1 failure
 * (where power / card-access LED 0xD20B0884 heartbeat passed, but the screen
 * showed fast-moving stripes in the upper half and no CHDK box or ALT marker):
 *
 * - h1 (INFERRED): Wrong pixel format/stride and wrong opacity_buffer stub.
 *   PORT-33/34 stubs_min.S pointed opacity_buffer at 0xFC1837FC (0x5FE80000,
 *   which is bitmap_buffer[0] in BmpDDev.c) and wrote 8-bit indexed bytes at
 *   stride 736 into the 16-bpp UYVY bitmap_buffer[0] (stride 1472 bytes),
 *   creating stripes across the upper half while leaving the real opacity
 *   buffers at 0xFC183800..0xFC183807 (0x5FC40000, 0x5FB80000) transparent.
 *   OSD2 uses the ROM-verified opacity_buffer[2] = {0x5FC40000, 0x5FB80000}
 *   [evidence/port35_manifest.json: PORT35-ROM-BMPDDEV] and writes 16-bpp
 *   UYVY words (0xFF80 white, 0x0080 black) at buffer_width (736 words =
 *   1472 bytes/row) plus 8-bpp opacity bytes (0xFF opaque) at buffer_width
 *   (736 bytes/row).
 *
 * - h2 (INFERRED): Drawing to a fixed buffer instead of the active one.
 *   PORT-33/34 drew to vid_get_bitmap_fb() (bitmap_buffer[0]) and did not mask
 *   active_bitmap_buffer & 1. OSD2 adapts vid_get_bitmap_active_buffer() and
 *   vid_get_opacity_active_buffer() from chdk-port/platform/g7x/lib.c:279-296
 *   and chdk-port/platform/g5x/lib.c:21-33 using (active_bitmap_buffer & 1).
 *
 * - h3 (INFERRED): No redraw from the kbd loop and post-draw refresh wipe.
 *   PORT-33/34 redrew only every 1000 ms from a separate task and called
 *   vid_bitmap_refresh() (_transfer_src_overlay(0/1)) after drawing, which
 *   is CHDK draw_restore() and overwrites the overlay with Canon UI buffers.
 *   OSD2 redraws the test box plus the ALT marker on every kbd tick while ALT
 *   is on without calling vid_bitmap_refresh() after drawing.
 * ============================================================================= */

#if defined(G3X_OSD2) && (G3X_OSD2 == 1)

#include "lolevel.h"
#include "platform.h"

/* Uncached RAM alias bit [chdk-port/platform/g3x/sub/110c/makefile.inc:20, INFERRED] */
#define G3X_OSD2_UNCACHED_BIT 0x40000000u

/* Default LCD screen dimensions (displaytype 1, 2, 8, 9, 10)
 * [evidence/port35_manifest.json: PORT35-ROM-BMPDDEV (jump table at 0xFC1834F8);
 *  chdk-port/platform/g7x/platform_camera.h:61-65; chdk-port/platform/g7x/lib.c:323-332] */
#if defined(G3X_GUI5) && (G3X_GUI5 == 1)
#define G3X_OSD2_DEFAULT_WIDTH         900
#define G3X_OSD2_DEFAULT_HEIGHT        600
#define G3X_OSD2_DEFAULT_BUFFER_WIDTH  928
#define G3X_OSD2_DEFAULT_BUFFER_HEIGHT 600
#define G3X_OSD2_DEFAULT_SIZE          540000
#define G3X_OSD2_DEFAULT_BUFFER_SIZE   556800
#else
#define G3X_OSD2_DEFAULT_WIDTH         720
#define G3X_OSD2_DEFAULT_HEIGHT        480
#define G3X_OSD2_DEFAULT_BUFFER_WIDTH  736
#define G3X_OSD2_DEFAULT_BUFFER_HEIGHT 480
#define G3X_OSD2_DEFAULT_SIZE          345600
#define G3X_OSD2_DEFAULT_BUFFER_SIZE   353280
#endif

/* Alternate displaytype dimensions in GM1.10C BmpDDev.c sub_fc18347e (jump table at 0xFC1834F8)
 * [evidence/port35_manifest.json: PORT35-ROM-BMPDDEV;
 *  chdk-port/platform/g7x/lib.c:313-347; chdk-port/platform/g5x/lib.c:171-203] */
#define G3X_OSD2_VGA_WIDTH             640
#define G3X_OSD2_VGA_HEIGHT            480
#define G3X_OSD2_VGA_BUFFER_WIDTH      640
#define G3X_OSD2_VGA_BUFFER_SIZE       307200

#define G3X_OSD2_HDMI_WIDTH            960
#define G3X_OSD2_HDMI_HEIGHT           540
#define G3X_OSD2_HDMI_BUFFER_WIDTH     960
#define G3X_OSD2_HDMI_BUFFER_SIZE      518400

#define G3X_OSD2_EVF_WIDTH             1024
#define G3X_OSD2_EVF_HEIGHT            768
#define G3X_OSD2_EVF_BUFFER_WIDTH      1024
#define G3X_OSD2_EVF_BUFFER_SIZE       786432

#define G3X_OSD2_MODE12_WIDTH          900
#define G3X_OSD2_MODE12_HEIGHT         600
#define G3X_OSD2_MODE12_BUFFER_WIDTH   928
#define G3X_OSD2_MODE12_SIZE           540000
#define G3X_OSD2_MODE12_BUFFER_SIZE    556800

/* Test box geometry (INFERRED) [chdk-port/platform/g3x/sub/110c/osd_test_overlay.h:40-45] */
#define G3X_OSD2_BOX_X                 16
#define G3X_OSD2_BOX_Y                 16
#define G3X_OSD2_BOX_W                 120
#define G3X_OSD2_BOX_H                 40
#define G3X_OSD2_BORDER                2

/* DIGIC 6 16-bpp UYVY pixel words and 8-bpp opacity values (INFERRED)
 * [chdk-port/core/gui_draw.c:15-35,72-94,110,127; chdk-port/platform/g7x/platform_camera.h:47] */
#define G3X_OSD2_UYVY_WHITE          0xFF80u
#define G3X_OSD2_UYVY_BLACK          0x0080u
#define G3X_OSD2_OPACITY_OPAQUE      0xFFu
#define G3X_OSD2_OPACITY_TRANSPARENT 0x00u

/* Firmware display variables and stubs (FINSIG)
 * - bitmap_buffer         = 0x0000D2A8 [reference/finsig_gm110c/stubs_entry.S:188]
 * - active_bitmap_buffer  = 0x0000D2A4 [reference/finsig_gm110c/stubs_entry.S:186]
 * - displaytype           = 0x00009740 [reference/finsig_gm110c/stubs_entry.S:187]
 * - _transfer_src_overlay = 0xFC380635 [reference/finsig_gm110c/stubs_entry.S:352] */
#define G3X_OSD2_ACTIVE_BITMAP_BUFFER_ADDR 0x0000D2A4u
#define G3X_OSD2_BITMAP_BUFFER_ADDR        0x0000D2A8u
#define G3X_OSD2_DISPLAYTYPE_ADDR          0x00009740u
#define G3X_OSD2_TRANSFER_SRC_OVERLAY_ADDR 0xFC380635u

extern char *bitmap_buffer[];
extern int active_bitmap_buffer;
extern int displaytype;
extern void _transfer_src_overlay(int);

/* GM1.10C bitmap_buffer and opacity_buffer pointers from BmpDDev.c sub_fc183608 literal pool
 * at 0xFC1837FC (0x5FE80000), 0xFC183800 (0x5FC40000), 0xFC183804 (0x5FB80000), and
 * 0xFC183818 (0x5FD00000) [evidence/port35_manifest.json: PORT35-ROM-BMPDDEV;
 * adapted from chdk-port/platform/g7x/lib.c:263-265,279-281,291 and chdk-port/platform/g5x/lib.c:21-33] */
#define G3X_OSD2_BITMAP_BUF0_ADDR  0x5FE80000u
#define G3X_OSD2_BITMAP_BUF1_ADDR  0x5FD00000u
#define G3X_OSD2_OPACITY_BUF0_ADDR 0x5FC40000u
#define G3X_OSD2_OPACITY_BUF1_ADDR 0x5FB80000u

volatile char *opacity_buffer[2] = {
    (char *)G3X_OSD2_OPACITY_BUF0_ADDR,
    (void *)G3X_OSD2_OPACITY_BUF1_ADDR,
};

/* Adapted from chdk-port/platform/g7x/lib.c:263-265 and chdk-port/platform/g5x/lib.c:21-25 */
void *vid_get_bitmap_fb(void)
{
    return (void *)bitmap_buffer[0];
}

/* Adapted from chdk-port/platform/g7x/lib.c:279-281 and chdk-port/platform/g5x/lib.c:21-25 */
void *vid_get_bitmap_active_buffer(void)
{
    return bitmap_buffer[active_bitmap_buffer & 1];
}

/* Adapted from chdk-port/platform/g7x/lib.c:294-296 and chdk-port/platform/g5x/lib.c:30-33 */
void *vid_get_opacity_active_buffer(void)
{
    return (void *)opacity_buffer[active_bitmap_buffer & 1];
}

/* Adapted from chdk-port/platform/g7x/lib.c:7-20 and chdk-port/platform/g5x/lib.c:9-19 */
void vid_bitmap_refresh(void)
{
    _transfer_src_overlay(0);
    _transfer_src_overlay(1);
}

/* Update camera_screen width/height/buffer_width/size/buffer_size from displaytype
 * Adapted from chdk-port/platform/g7x/lib.c:303-358 (LCD case 1,2,8,9,10 at lines 323-332),
 * chdk-port/platform/g5x/lib.c:162-204, and GM1.10C BmpDDev.c sub_fc18347e jump table at
 * 0xFC1834F8 (0xFC18347E..0xFC18381F) [evidence/port35_manifest.json: PORT35-ROM-BMPDDEV] */
void g3x_osd2_update_screen_dimensions(void)
{
    static int old_displaytype = -1;
    int dt = displaytype;

    if (old_displaytype == dt) {
        return;
    }
    old_displaytype = dt;

    int w = G3X_OSD2_DEFAULT_WIDTH;
    int bw = G3X_OSD2_DEFAULT_BUFFER_WIDTH;
    int h = G3X_OSD2_DEFAULT_HEIGHT;

    switch (dt) {
        case 0:
        case 3:
        case 4:
        case 5:
            w = G3X_OSD2_VGA_WIDTH;
            bw = G3X_OSD2_VGA_BUFFER_WIDTH;
            h = G3X_OSD2_VGA_HEIGHT;
            break;
        case 1:
        case 2:
        case 8:
        case 9:
        case 10:
            w = G3X_OSD2_DEFAULT_WIDTH;
            bw = G3X_OSD2_DEFAULT_BUFFER_WIDTH;
            h = G3X_OSD2_DEFAULT_HEIGHT;
            break;
        case 6:
        case 7:
            w = G3X_OSD2_HDMI_WIDTH;
            bw = G3X_OSD2_HDMI_BUFFER_WIDTH;
            h = G3X_OSD2_HDMI_HEIGHT;
            break;
        case 11:
            w = G3X_OSD2_EVF_WIDTH;
            bw = G3X_OSD2_EVF_BUFFER_WIDTH;
            h = G3X_OSD2_EVF_HEIGHT;
            break;
        case 12:
            w = G3X_OSD2_MODE12_WIDTH;
            bw = G3X_OSD2_MODE12_BUFFER_WIDTH;
            h = G3X_OSD2_MODE12_HEIGHT;
            break;
        default:
            break;
    }

    camera_screen.width = camera_screen.physical_width = w;
    camera_screen.buffer_width = bw;
    camera_screen.height = camera_screen.buffer_height = h;
    camera_screen.size = w * h;
    camera_screen.buffer_size = bw * h;

#if (defined(G3X_GUI2) && (G3X_GUI2 == 1)) || (defined(G3X_GUI3) && (G3X_GUI3 == 1))
    /* Reset OSD offset and width for active resolution (adapting chdk-port/platform/g5x/lib.c:195-196).
     * Note: G3X_GUI4 and G3X_GUI5 inherit -DG3X_GUI3=1, so disp_left/right/width resets apply to all. */
    camera_screen.disp_left = 0;
    camera_screen.disp_right = camera_screen.width - 1;
    camera_screen.disp_width = camera_screen.width;
#endif
}

/* Fixed "CHDK" text bitmap rows: 5 rows x 15 columns (1 = pixel on, 0 = off) */
static const unsigned short g3x_osd2_chdk_glyph_rows[5] = {
    0x7565, /* 0b0111_0101_0110_0101:  ***  * *  **   * * */
    0x4555, /* 0b0100_0101_0101_0101:  *    * *  * *  * * */
    0x4756, /* 0b0100_0111_0101_0110:  *    ***  * *  **  */
    0x4555, /* 0b0100_0101_0101_0101:  *    * *  * *  * * */
    0x7565  /* 0b0111_0101_0110_0101:  ***  * *  **   * * */
};

/* Fixed "ALT" text bitmap rows: 5 rows x 11 columns (1 = pixel on, 0 = off) */
static const unsigned short g3x_osd2_alt_glyph_rows[5] = {
    0xE8E0, /* 0b1110_1000_1110_0000:  ***  *    *** */
    0xA840, /* 0b1010_1000_0100_0000:  * *  *     *  */
    0xE840, /* 0b1110_1000_0100_0000:  ***  *     *  */
    0xA840, /* 0b1010_1000_0100_0000:  * *  *     *  */
    0xAE40  /* 0b1010_1110_0100_0000:  * *  ***   *  */
};

/* Draw the "CHDK" test box and (while ALT is on) the "ALT" marker into the
 * active bitmap buffer (16-bpp UYVY, stride buffer_width * 2 bytes) and
 * active opacity buffer (8-bpp alpha, stride buffer_width bytes).
 * Does NOT call vid_bitmap_refresh() after drawing (fixes h3). */
void __attribute__((noinline)) g3x_osd2_draw_test_overlay(int alt_active)
{
    g3x_osd2_update_screen_dimensions();

    volatile unsigned short *bmp_buf = (volatile unsigned short *)((unsigned int)vid_get_bitmap_active_buffer() | G3X_OSD2_UNCACHED_BIT);
    volatile unsigned char *op_buf = (volatile unsigned char *)((unsigned int)vid_get_opacity_active_buffer() | G3X_OSD2_UNCACHED_BIT);
    if (!bmp_buf || !op_buf) {
        return;
    }

    int buf_w = camera_screen.buffer_width;
    if (buf_w <= 0) {
        buf_w = G3X_OSD2_DEFAULT_BUFFER_WIDTH;
    }

    for (int y = 0; y < G3X_OSD2_BOX_H; y++) {
        int py = G3X_OSD2_BOX_Y + y;
        int row_off = py * buf_w + G3X_OSD2_BOX_X;
        int border_y = (y < G3X_OSD2_BORDER || y >= G3X_OSD2_BOX_H - G3X_OSD2_BORDER);
        int text_row = (y - 10) >> 2;
        int in_text_y = (y >= 10 && y < 30);
        unsigned short chdk_mask = in_text_y ? g3x_osd2_chdk_glyph_rows[text_row] : 0;
        unsigned short alt_mask = (in_text_y && alt_active) ? g3x_osd2_alt_glyph_rows[text_row] : 0;

        for (int x = 0; x < G3X_OSD2_BOX_W; x++) {
            int p = x >> 1;
            int is_white = border_y || (x < G3X_OSD2_BORDER) || (x >= G3X_OSD2_BOX_W - G3X_OSD2_BORDER);
            if (!is_white && in_text_y) {
                int bit_idx = (p - 15) >> 1;
                if (p >= 15 && p < 45 && (chdk_mask & (1u << (14 - bit_idx)))) {
                    is_white = 1;
                } else if (alt_active && p >= 46 && p < 57 && (alt_mask & (1u << (15 - (p - 46))))) {
                    is_white = 1;
                }
            }
            bmp_buf[row_off + x] = is_white ? (unsigned short)G3X_OSD2_UYVY_WHITE : (unsigned short)G3X_OSD2_UYVY_BLACK;
            op_buf[row_off + x] = (unsigned char)G3X_OSD2_OPACITY_OPAQUE;
        }
    }
}

#if defined(G3X_GUI) && (G3X_GUI == 1)
extern void g3x_gui_kbd_redraw(int alt_active);
#endif

/* Called from mykbd_task() on every keyboard tick */
static inline __attribute__((always_inline)) void g3x_osd2_kbd_redraw(int alt_active)
{
#if defined(G3X_GUI) && (G3X_GUI == 1)
    g3x_gui_kbd_redraw(alt_active);
#else
    g3x_osd2_draw_test_overlay(alt_active);
#endif
}

#endif /* defined(G3X_OSD2) && (G3X_OSD2 == 1) */

#endif /* G3X_OSD2_TEST_OVERLAY_H */
