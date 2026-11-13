#include "platform.h"
#include "stdlib.h"
#include "touchscreen.h"
#include "conf.h"
#include "font.h"
#include "lang.h"
#include "gui_draw.h"

#define GET_FONT_COMPRESSION_MODE 1
#include "../lib/font/font_8x16_uni_packed.h"
#undef  GET_FONT_COMPRESSION_MODE

#ifdef THUMB_FW
// macros for computing palette from a single byte color value
#define CALC_YUV_LUMA_OPACITY_FOR_COLOR(color,luma,opacity) \
    { \
        luma = ((color-1)^0xffffffff)&0xf0; \
        opacity = (color&0xf)?255:color; \
    }

#define CALC_YUV_CHROMA_FOR_COLOR(color,u,v) \
    { \
        v = color; \
        u = (v+1); \
        if (!(u&2)) \
        { \
            u = 128; \
            v = 128; \
        } \
        else \
        { \
            u *= 3; \
            v <<= 3; \
        } \
    }

extern volatile char *opacity_buffer[];

#endif
//-------------------------------------------------------------------
// used to prevent draw_restore from being called until tick reached
// to avoid crashes on video out change
int draw_restore_suspend_tick;

void            (*draw_pixel_proc)(unsigned int offset, color cl);
void            (*draw_pixel_proc_norm)(unsigned int offset, color cl);

#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
extern char* bitmap_buffer[];
extern int active_bitmap_buffer;
#else
static char* frame_buffer[2];
#endif
//-------------------------------------------------------------------

#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
/*
 * PORT-44: Runtime heap-allocated shadow buffer sized to the drawn menu rectangle (880x576).
 *
 * Background & Hypothesis (PORT-44 task):
 * In PORT-43, static g3x_shadow (928x600 bitmap + opacity, 1,670,400 bytes) in BSS moved core _end
 * from 0x003687b0 (PORT-42) to 0x00500fd0 (+1,673,248 bytes).
 * The PORT-27 heap-start raise sets the firmware heap at _end (new_sa = &_end).
 * Raising the heap base past 0x00500fd0 deprived DryOS of ~1.67 MB of heap RAM,
 * causing firmware startup allocations to fail and preventing camera boot.
 *
 * PORT-44 Fix:
 * 1. Remove static g3x_shadow from BSS entirely. No large static arrays in BSS.
 * 2. Size shadow strictly to the drawn menu rectangle:
 *    Width:  880 (stride = 880 pixels, even)
 *    Height: 576 rows
 *    Origin: (G3X_MENU_X0 = 10, G3X_MENU_Y0 = 12)
 *    Bitmap:  880 * 576 * 2 = 1,013,760 bytes (UYVY 16bpp)
 *    Opacity: 880 * 576 * 1 =   506,880 bytes (8bpp)
 *    Total:   1,520,640 bytes (~1.45 MiB)
 * 3. Allocate lazily on the first GUI/ALT entry from the firmware heap:
 *    - First try CHDK malloc(G3X_SHADOW_TOTAL_SIZE) -> delegates to canon_malloc / DryOS _malloc
 *    - If NULL, fallback to umalloc(G3X_SHADOW_TOTAL_SIZE) -> delegates to _AllocateUncacheableMemory
 *    - Allocate once and reuse; never free and reallocate on every entry.
 *    - Never allocate during boot or from startup / CreateTask hook path.
 * 4. Fallback on NULL:
 *    - If allocation returns NULL, run with dual-buffer writes only (no shadow).
 *    - Do not retry every frame (g3x_shadow_alloc_attempted flag).
 *    - Every shadow access checks for NULL, with zero out-of-bounds writes and no crash.
 *
 * Citations:
 * - reference/finsig_gm110c/stubs_entry.S:308: NHSTUB(malloc, 0xfc381525) [FINSIG]
 * - reference/finsig_gm110c/stubs_entry.S:197: NHSTUB(AllocateUncacheableMemory, 0xfc144471) [FINSIG]
 * - chdk-port/core/memmgmt.c:284-297 (malloc delegates to canon_malloc)
 * - chdk-port/platform/generic/wrappers.c:1020-1031 (canon_malloc calls _malloc)
 * - chdk-port/platform/generic/wrappers.c:1045-1057 (umalloc calls _AllocateUncacheableMemory)
 * - chdk-port/platform/g7x/sub/100c/stubs_entry.S:285: NHSTUB(malloc, 0xfc3623b9)
 * - chdk-port/platform/g5x/sub/100c/stubs_entry.S:286: NHSTUB(malloc, 0xfc3bf235)
 * - chdk-port/platform/g7x/sub/100c/stubs_entry.S:181: NHSTUB(AllocateUncacheableMemory, 0xfc0ef0cd)
 * - chdk-port/platform/g5x/sub/100c/stubs_entry.S:191: NHSTUB(AllocateUncacheableMemory, 0xfc16f5f1)
 */
#define G3X_MENU_X0         10
#define G3X_MENU_Y0         12
#define G3X_MENU_WIDTH      880
#define G3X_MENU_HEIGHT     576
#define G3X_MENU_X1         (G3X_MENU_X0 + G3X_MENU_WIDTH - 1)  /* 889 */
#define G3X_MENU_Y1         (G3X_MENU_Y0 + G3X_MENU_HEIGHT - 1) /* 587 */

#define G3X_SHADOW_WIDTH    G3X_MENU_WIDTH
#define G3X_SHADOW_HEIGHT   G3X_MENU_HEIGHT
#define G3X_SHADOW_BM_SIZE  (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 2) /* 1,013,760 B */
#define G3X_SHADOW_OP_SIZE  (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 1) /*   506,880 B */
#define G3X_SHADOW_TOTAL_SIZE (G3X_SHADOW_BM_SIZE + G3X_SHADOW_OP_SIZE) /* 1,520,640 B */

static unsigned char *g3x_shadow_bitmap = 0;
static unsigned char *g3x_shadow_opacity = 0;
static int g3x_shadow_alloc_attempted = 0;

int g3x_shadow_valid = 0;

int g3x_dbuf_shadow_is_allocated(void)
{
    return (g3x_shadow_bitmap != 0 && g3x_shadow_opacity != 0);
}

void g3x_dbuf_shadow_ensure_allocated(void)
{
    if (g3x_shadow_alloc_attempted)
        return;
    g3x_shadow_alloc_attempted = 1;

    void *buf = malloc(G3X_SHADOW_TOTAL_SIZE);
    if (!buf)
    {
        buf = umalloc(G3X_SHADOW_TOTAL_SIZE);
    }
    if (buf)
    {
        g3x_shadow_bitmap = (unsigned char *)buf;
        g3x_shadow_opacity = (unsigned char *)buf + G3X_SHADOW_BM_SIZE;
        memset(buf, 0, G3X_SHADOW_TOTAL_SIZE);
    }
    else
    {
        g3x_shadow_bitmap = 0;
        g3x_shadow_opacity = 0;
        g3x_shadow_valid = 0;
    }
}

void g3x_dbuf_shadow_reset(void)
{
    g3x_shadow_valid = 0;
    if (g3x_shadow_bitmap && g3x_shadow_opacity)
    {
        memset(g3x_shadow_bitmap, 0, G3X_SHADOW_BM_SIZE);
        memset(g3x_shadow_opacity, 0, G3X_SHADOW_OP_SIZE);
    }
}

void g3x_dbuf_shadow_init(void)
{
    /* Invalidation: DBUF startup / shadow init - clear shadow valid.
     * Never allocate here (boot / spytask start). */
    g3x_shadow_valid = 0;
}

void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd)
{
    (void)offs2;
    if (!g3x_shadow_bitmap || !g3x_shadow_opacity)
        return;

    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;
    int screen_y = (int)(offset / buf_w);
    int screen_x = (int)(offset % buf_w);

    if (screen_x >= G3X_MENU_X0 && screen_x <= G3X_MENU_X1 &&
        screen_y >= G3X_MENU_Y0 && screen_y <= G3X_MENU_Y1)
    {
        int rx = screen_x - G3X_MENU_X0;
        int ry = screen_y - G3X_MENU_Y0;
        unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);
        unsigned int sh_offs2 = (sh_offset >> 1) << 2;

        if (sh_offset < G3X_SHADOW_OP_SIZE)
        {
            g3x_shadow_opacity[sh_offset] = (unsigned char)o;
            if (is_odd)
            {
                g3x_shadow_bitmap[sh_offs2 + 3] = (unsigned char)y;
            }
            else
            {
                g3x_shadow_bitmap[sh_offs2 + 0] = (unsigned char)u;
                g3x_shadow_bitmap[sh_offs2 + 1] = (unsigned char)y;
                g3x_shadow_bitmap[sh_offs2 + 2] = (unsigned char)v;
            }
        }
    }
}

/*
 * Fast fills: 32-bit word writes (UYVY pairs plus opacity bytes, memset/memcpy style).
 * ZERO per-pixel draw_pixel calls.
 * Citing chdk-port/core/gui_draw.c:138-146; scripts/build_candidate_gui3.py:885-896.
 * Label: VERIFIED.
 */
void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl)
{
    if (x1 > x2) { coord t = x1; x1 = x2; x2 = t; }
    if (y1 > y2) { coord t = y1; y1 = y2; y2 = t; }

    int screen_w = camera_screen.width ? camera_screen.width : 900;
    int screen_h = camera_screen.height ? camera_screen.height : 600;
    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;

    if (x1 < 0) x1 = 0;
    if (y1 < 0) y1 = 0;
    if (x2 >= screen_w) x2 = screen_w - 1;
    if (y2 >= screen_h) y2 = screen_h - 1;
    if (x1 > x2 || y1 > y2) return;

    unsigned int op;
    unsigned int uyvy_word = color_to_rawpx(cl, &op);
    unsigned char op_byte = (unsigned char)(op & 0xFF);

    unsigned int y_luma, o_val;
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl, y_luma, o_val);
    unsigned int u_val = 128, v_val = 128;
    CALC_YUV_CHROMA_FOR_COLOR(cl, u_val, v_val);

    for (coord y = y1; y <= y2; ++y)
    {
        coord cur_x = x1;
        // Leading odd pixel if x1 is odd
        if (cur_x & 1)
        {
            unsigned int offset = y * buf_w + cur_x;
            unsigned int offs2 = (offset >> 1) << 2;
            for (int b = 0; b < 2; b++)
            {
                opacity_buffer[b][offset] = op_byte;
                ((unsigned char*)bitmap_buffer[b])[offs2 + 3] = (unsigned char)y_luma;
            }
            if (g3x_shadow_opacity && g3x_shadow_bitmap &&
                cur_x >= G3X_MENU_X0 && cur_x <= G3X_MENU_X1 &&
                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)
            {
                int rx = cur_x - G3X_MENU_X0;
                int ry = y - G3X_MENU_Y0;
                unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);
                unsigned int sh_offs2 = (sh_offset >> 1) << 2;
                if (sh_offset < G3X_SHADOW_OP_SIZE)
                {
                    g3x_shadow_opacity[sh_offset] = op_byte;
                    g3x_shadow_bitmap[sh_offs2 + 3] = (unsigned char)y_luma;
                }
            }
            cur_x++;
        }

        int pairs = (x2 - cur_x + 1) / 2;
        if (pairs > 0)
        {
            int n_pixels = pairs * 2;
            unsigned int offset_fb = (y * buf_w + cur_x) * 2;
            unsigned int offset_op = y * buf_w + cur_x;

            memset((void*)&opacity_buffer[0][offset_op], op_byte, n_pixels);
            memset((void*)&opacity_buffer[1][offset_op], op_byte, n_pixels);

            unsigned int *p0 = (unsigned int *)(&bitmap_buffer[0][offset_fb]);
            unsigned int *p1 = (unsigned int *)(&bitmap_buffer[1][offset_fb]);
            for (int w = 0; w < pairs; ++w)
            {
                p0[w] = uyvy_word;
                p1[w] = uyvy_word;
            }

            if (g3x_shadow_opacity && g3x_shadow_bitmap &&
                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)
            {
                int sh_x_start = cur_x > G3X_MENU_X0 ? cur_x : G3X_MENU_X0;
                int sh_x_end = (cur_x + n_pixels - 1) < G3X_MENU_X1 ? (cur_x + n_pixels - 1) : G3X_MENU_X1;
                if (sh_x_start <= sh_x_end)
                {
                    int ry = y - G3X_MENU_Y0;
                    int rx_start = sh_x_start - G3X_MENU_X0;
                    int sh_pixels = sh_x_end - sh_x_start + 1;
                    unsigned int sh_op_off = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx_start);
                    unsigned int sh_bm_off = sh_op_off * 2;

                    if ((sh_op_off + sh_pixels) <= G3X_SHADOW_OP_SIZE)
                    {
                        memset(&g3x_shadow_opacity[sh_op_off], op_byte, sh_pixels);
                        int sh_pairs = sh_pixels / 2;
                        unsigned int *sp = (unsigned int *)(&g3x_shadow_bitmap[sh_bm_off]);
                        for (int sw = 0; sw < sh_pairs; ++sw)
                        {
                            sp[sw] = uyvy_word;
                        }
                    }
                }
            }
            cur_x += n_pixels;
        }

        // Trailing odd pixel if x2 was even
        if (cur_x <= x2)
        {
            unsigned int offset = y * buf_w + cur_x;
            unsigned int offs2 = (offset >> 1) << 2;
            for (int b = 0; b < 2; b++)
            {
                opacity_buffer[b][offset] = op_byte;
                ((unsigned char*)bitmap_buffer[b])[offs2 + 0] = (unsigned char)u_val;
                ((unsigned char*)bitmap_buffer[b])[offs2 + 1] = (unsigned char)y_luma;
                ((unsigned char*)bitmap_buffer[b])[offs2 + 2] = (unsigned char)v_val;
            }
            if (g3x_shadow_opacity && g3x_shadow_bitmap &&
                cur_x >= G3X_MENU_X0 && cur_x <= G3X_MENU_X1 &&
                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)
            {
                int rx = cur_x - G3X_MENU_X0;
                int ry = y - G3X_MENU_Y0;
                unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);
                unsigned int sh_offs2 = (sh_offset >> 1) << 2;
                if (sh_offset < G3X_SHADOW_OP_SIZE)
                {
                    g3x_shadow_opacity[sh_offset] = op_byte;
                    g3x_shadow_bitmap[sh_offs2 + 0] = (unsigned char)u_val;
                    g3x_shadow_bitmap[sh_offs2 + 1] = (unsigned char)y_luma;
                    g3x_shadow_bitmap[sh_offs2 + 2] = (unsigned char)v_val;
                }
            }
        }
    }
}

void g3x_dbuf_fill_menu_opaque_black(void)
{
    g3x_dbuf_fast_fill_rect(10, 12, 889, 587, COLOR_BLACK);
}

int g3x_dbuf_shadow_restore(void)
{
    /* Restore only when shadow is valid, buffer allocated, AND CHDK overlay layer is active (not in defaultGuiHandler/live view) */
    if (!g3x_shadow_valid || !g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)
    {
        return 0;
    }
    int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : 928;

    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry)
    {
        int screen_y = G3X_MENU_Y0 + ry;
        unsigned int offset_op = (unsigned int)(screen_y * buf_w + G3X_MENU_X0);
        unsigned int offset_bm = offset_op * 2;

        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;
        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;

        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);
        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);

        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);
        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);
    }

    draw_set_guard();
    /* NOTE: No vid_bitmap_refresh() here! On G3X (DIGIC 6), vid_bitmap_refresh calls _transfer_src_overlay,
     * which wipes the overlay plane back to stock Canon UI (docs/PORT35_GUI_ADDRESSES.md:35).
     * The synchronous blit into both bitmap buffers and both opacity buffers stands on its own. */
    return 1;
}

int g3x_dbuf_restore_if_sentinel_lost(void)
{
    if (!g3x_shadow_valid || !g3x_shadow_bitmap || !g3x_shadow_opacity || camera_info.state.gui_mode_none)
    {
        return 0;
    }
    if (!draw_test_guard())
    {
        return g3x_dbuf_shadow_restore();
    }
    return 0;
}
#endif

static void draw_pixel_std(unsigned int offset, color cl)
{
#ifndef THUMB_FW
    // drawing on 8bpp paletted overlay
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
	bitmap_buffer[active_bitmap_buffer][offset] = cl;
#else
	frame_buffer[0][offset] = frame_buffer[1][offset] = cl;
#endif
#else
    // DIGIC 6, drawing on 16bpp YUV overlay

#ifndef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
#error DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY is required for DIGIC 6 ports
#endif

#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    unsigned int y;
    unsigned int o;
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl, y, o);
    unsigned int u = 128, v = 128;
    int is_odd = (offset & 1);
    if (!is_odd)
    {
        CALC_YUV_CHROMA_FOR_COLOR(cl, u, v);
    }
    register unsigned int offs2 = (offset >> 1) << 2;

    for (int buf_idx = 0; buf_idx < 2; buf_idx++)
    {
        unsigned char *obu = (unsigned char *)(&opacity_buffer[buf_idx][0]);
        unsigned char *bbu = (unsigned char *)(&bitmap_buffer[buf_idx][0]);
        obu[offset] = o;
        if (is_odd)
        {
            bbu[offs2 + 3] = y;
        }
        else
        {
            bbu[offs2 + 0] = u;
            bbu[offs2 + 1] = y;
            bbu[offs2 + 2] = v;
        }
    }
    g3x_dbuf_shadow_draw_pixel(offset, offs2, y, o, u, v, is_odd);
#else
    int active_buffer_index =  active_bitmap_buffer & 1;
    unsigned char *obu = (unsigned char *)(&opacity_buffer[active_buffer_index][0]);
    unsigned char *bbu = (unsigned char *)(&bitmap_buffer[active_buffer_index][0]);
    unsigned int y;
    unsigned int o;
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl,y,o);
    obu[offset] = o;
    register unsigned int offs2 = (offset>>1)<<2;
    if (offset&1) // x is odd
    {
        bbu[offs2+3] = y; // Y
    }
    else // x is even
    {
        unsigned int u;
        unsigned int v;
        CALC_YUV_CHROMA_FOR_COLOR(cl,u,v);
        bbu[offs2+1] = y; // Y
        bbu[offs2+0] = u; // U?
        bbu[offs2+2] = v; // V?

    }
#endif
#endif
}
//-------------------------------------------------------------------
#ifdef THUMB_FW
// direct drawing functions for YUV overlay, currently used by the zebra module
// ATTENTION: these functions do not support guard pixels or rotation

// function for setting part of the overlay transparent (DIGIC 6 only), used in zebra module
// n_pixel is the number of pixels to set
// offst is the byte offset in bitmap_buffer, 2 bytes per pixel
void set_transparent(unsigned int offst, int n_pixel)
{
    extern void _bzero(char *s, int n);
    extern void _memset32(char *s, int n, unsigned int pattern);
    //offset is the byte (same as pixel) offset in the opacity buffer
    unsigned int offset = offst>>2;
    unsigned int w_pattern = 0x00800080;

#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    for (int b = 0; b < 2; b++)
    {
        _memset32(&bitmap_buffer[b][offst], n_pixel<<1, w_pattern);
        _bzero((char*)&opacity_buffer[b][offset], n_pixel);
    }
#else
    int active_buffer_index = active_bitmap_buffer & 1;

    _memset32(&bitmap_buffer[active_buffer_index][offst], n_pixel<<1, w_pattern);
    _bzero((char*)&opacity_buffer[active_buffer_index][offset], n_pixel);
#endif
}

// translate single byte CHDK color to a whole yuv unit (2 pixels)
// opacity is returned via the second argument
unsigned int color_to_rawpx(color cl, unsigned int *op)
{
    unsigned int y,u,v,o;
    CALC_YUV_CHROMA_FOR_COLOR(cl,u,v);
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl,y,o);
    if (op) *op = o;
    return (u&255)+((y&255)<<8)+((v&255)<<16)+(y<<24);
}

// function for drawing a whole yuv unit (2 pixels, aligned)
// opacity is a single byte, used for both pixels
// drawing offset is pixel offset, calculated by caller
void draw_dblpixel_raw(unsigned int offset, unsigned int px, unsigned int op)
{
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    offset >>= 2;
    for (int b = 0; b < 2; b++)
    {
        unsigned short * opbuf = (unsigned short*)(opacity_buffer[b]);
        unsigned int * bmbuf = (unsigned int*)(bitmap_buffer[b]);
        bmbuf[offset] = px;
        opbuf[offset] = op | (op<<8);
    }
#else
    int active_buffer_index =  active_bitmap_buffer & 1;
    offset >>= 2;
    unsigned short * opbuf = (unsigned short*)(opacity_buffer[active_buffer_index]);
    unsigned int * bmbuf = (unsigned int*)(bitmap_buffer[active_buffer_index]);
    bmbuf[offset] = px;
    opbuf[offset] = op | (op<<8);
#endif
}

#else // !THUMB_FW
// not implemented for earlier DIGICs
unsigned int color_to_rawpx(color cl, unsigned int *op)
{
    return 0;
}
void draw_dblpixel_raw(unsigned int offset, unsigned int px, unsigned int op)
{
}
void set_transparent(unsigned int offst, int n_pixel)
{
}
#endif // THUMB_FW

//-------------------------------------------------------------------
unsigned int rotate_base;

void draw_pixel_proc_rotated(unsigned int offset, color cl)
{
    draw_pixel_proc_norm(rotate_base - offset, cl);
}

void draw_set_draw_proc(void (*pixel_proc)(unsigned int offset, color cl))
{
    draw_pixel_proc_norm = (pixel_proc)?pixel_proc:draw_pixel_std;
    if (conf.rotate_osd)
    {
        rotate_base = (camera_screen.height - 1) * camera_screen.buffer_width + ASPECT_XCORRECTION(camera_screen.width) - 1;
        draw_pixel_proc = draw_pixel_proc_rotated;
    }
    else
    {
        draw_pixel_proc = draw_pixel_proc_norm;
    }
}

void update_draw_proc()
{
    draw_set_draw_proc(draw_pixel_proc_norm);
}

//-------------------------------------------------------------------
#ifdef THUMB_FW
// pixel drawing functions for YUV, meant to be optimized for greater speed
// drawing is done directly, drawing function replacement is not supported
// OSD rotation is respected

static unsigned char *current_opacity_buf;
static unsigned char *current_bitmap_buf;
static unsigned char yuvclr[8]; // order of bytes: background u,y,v,opacity; foreground u,y,v,opacity

// sets up decoded colors and buffer addresses for the following drawing operation
static void draw_pixel_simple_start(twoColors tc)
{
    color cl;
    int active_buffer_index =  active_bitmap_buffer & 1;
    current_opacity_buf = (unsigned char *)(&opacity_buffer[active_buffer_index][0]);
    current_bitmap_buf = (unsigned char *)(&bitmap_buffer[active_buffer_index][0]);
    cl = BG_COLOR(tc);
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl,yuvclr[1],yuvclr[3]);
    CALC_YUV_CHROMA_FOR_COLOR(cl,yuvclr[0],yuvclr[2]);
    cl = FG_COLOR(tc);
    CALC_YUV_LUMA_OPACITY_FOR_COLOR(cl,yuvclr[5],yuvclr[7]);
    CALC_YUV_CHROMA_FOR_COLOR(cl,yuvclr[4],yuvclr[6]);
}

// px: bit0 unset for background, set for foreground
static void draw_1pixel_simple(coord x, coord y, int px, int vrepeat)
{
    if ((x < 0) || (y < 0) || (x >= camera_screen.width) || (y+vrepeat >= camera_screen.height)/* || ((x == 0) && (y == 0))*/) return;
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    unsigned int offset = y * camera_screen.buffer_width + x;
    int plus = camera_screen.buffer_width;
    if (conf.rotate_osd)
    {
        offset = rotate_base - offset;
        plus = -plus;
        g3x_shadow_valid = 0;
    }

    if (!offset) return; // skip guard pixel

    int fg = px<<2;
    register unsigned int offs2 = (offset>>1)<<2;
    unsigned char op = yuvclr[fg+3];
    unsigned char y_luma = yuvclr[fg+1];
    unsigned char u_val = yuvclr[fg];
    unsigned char v_val = yuvclr[fg+2];

    if (offset&1) // x is odd
    {
        while (1)
        {
            opacity_buffer[0][offset] = op;
            opacity_buffer[1][offset] = op;
            ((unsigned char *)bitmap_buffer[0])[offs2+3] = y_luma;
            ((unsigned char *)bitmap_buffer[1])[offs2+3] = y_luma;
            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, 1);
            if (!vrepeat) return;
            vrepeat--;
            offset += plus;
            offs2 += (plus<<1);
        }
    }
    else // x is even
    {
        while (1)
        {
            opacity_buffer[0][offset] = op;
            opacity_buffer[1][offset] = op;
            ((unsigned char *)bitmap_buffer[0])[offs2+0] = u_val;
            ((unsigned char *)bitmap_buffer[0])[offs2+1] = y_luma;
            ((unsigned char *)bitmap_buffer[0])[offs2+2] = v_val;
            ((unsigned char *)bitmap_buffer[1])[offs2+0] = u_val;
            ((unsigned char *)bitmap_buffer[1])[offs2+1] = y_luma;
            ((unsigned char *)bitmap_buffer[1])[offs2+2] = v_val;
            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, 0);
            if (!vrepeat) return;
            vrepeat--;
            offset += plus;
            offs2 += (plus<<1);
        }
    }
#else
    unsigned char *obu = current_opacity_buf;
    unsigned char *bbu = current_bitmap_buf;
    unsigned int offset = y * camera_screen.buffer_width + x;
    int plus = camera_screen.buffer_width;
    if (conf.rotate_osd)
    {
        offset = rotate_base - offset;
        plus = -plus;
    }

    if (!offset) return; // skip guard pixel

    int fg = px<<2;
    register unsigned int offs2 = (offset>>1)<<2;
    
    if (offset&1) // x is odd
    {
        while (1)
        {
            obu[offset] = yuvclr[fg+3];
            bbu[offs2+3] = yuvclr[fg+1]; // Y
            if (!vrepeat) return;
            vrepeat--;
            offset += plus;
            offs2 += (plus<<1);
        }
    }
    else // x is even
    {
        while (1)
        {
            obu[offset] = yuvclr[fg+3];
            bbu[offs2+1] = yuvclr[fg+1]; // Y
            bbu[offs2+0] = yuvclr[fg]; // U
            bbu[offs2+2] = yuvclr[fg+2]; // V
            if (!vrepeat) return;
            vrepeat--;
            offset += plus;
            offs2 += (plus<<1);
        }
    }
#endif
}

// px: 2 bits, describing 2 pixels (foreground when set, background when not), LSB is the second pixel
// first pixel specifies chroma
static void draw_2pixels_simple(coord x, coord y, int px, int vrepeat)
{
    if ((x < 0) || (y < 0) || (x+1 >= camera_screen.width) || (y+vrepeat >= camera_screen.height)/* || ((x == 0) && (y == 0))*/) return;
    unsigned int y1, y2;
    unsigned int offset = (y * camera_screen.buffer_width + x)>>1;
    int plus;
    unsigned short co;
    unsigned int yuv;
    if (conf.rotate_osd)
    {
        offset = (rotate_base>>1) - offset;
        plus = -(camera_screen.buffer_width>>1);
        y1 = px&1?4:0;
        y2 = px&2?4+1:0+1;
    }
    else
    {
        plus = camera_screen.buffer_width>>1;
        y1 = px&2?4:0;
        y2 = px&1?4+1:0+1;
    }

    if (!offset) return; // skip guard pixel

    co = yuvclr[y1+3]+(yuvclr[y1+3]<<8);
    yuv = (*(unsigned int*)(&yuvclr[y1]) & 0xffffff) + (yuvclr[y2]<<24);
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    unsigned short *obu0 = (unsigned short *)opacity_buffer[0];
    unsigned short *obu1 = (unsigned short *)opacity_buffer[1];
    unsigned int *bbu0 = (unsigned int *)bitmap_buffer[0];
    unsigned int *bbu1 = (unsigned int *)bitmap_buffer[1];
    coord cur_y = y;
    while (1)
    {
        obu0[offset] = co;
        obu1[offset] = co;
        bbu0[offset] = yuv;
        bbu1[offset] = yuv;

        // Shadow copy update (16-bit opacity word, 32-bit UYVY bitmap word)
        if (!conf.rotate_osd && g3x_shadow_opacity && g3x_shadow_bitmap)
        {
            if (x >= G3X_MENU_X0 && (x + 1) <= G3X_MENU_X1 &&
                cur_y >= G3X_MENU_Y0 && cur_y <= G3X_MENU_Y1)
            {
                int rx = x - G3X_MENU_X0;
                int ry = cur_y - G3X_MENU_Y0;
                unsigned int sh_pair = (unsigned int)((ry * G3X_SHADOW_WIDTH + rx) >> 1);
                if (sh_pair < (G3X_SHADOW_OP_SIZE / 2))
                {
                    ((unsigned short *)g3x_shadow_opacity)[sh_pair] = co;
                    ((unsigned int *)g3x_shadow_bitmap)[sh_pair] = yuv;
                }
            }
        }

        if (!vrepeat) return;
        vrepeat--;
        cur_y++;
        offset += plus;
    }
#else
    unsigned short *obu = (unsigned short *)current_opacity_buf;
    unsigned int *bbu = (unsigned int *)current_bitmap_buf;
    while (1)
    {
        obu[offset] = co;
        bbu[offset] = yuv;
        if (!vrepeat) return;
        vrepeat--;
        offset += plus;
    }
#endif
}

void draw_hline_simple(coord x, coord y, int len, int px)
{
    if ((y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height)) return;
    if (x < 0) { len += x; x = 0; }
    if ((x + len) > camera_screen.width) len = camera_screen.width - x;
    /*if ((x == 0) && (y == 0)) { x++; len--; }   // Skip guard pixel*/

    register unsigned int offset = y * camera_screen.buffer_width + (x);
    if (conf.rotate_osd)
    {
        offset = rotate_base - offset - len;
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
        g3x_shadow_valid = 0;
#endif
    }

    // Skip guard pixel
    if (!offset)
    {
        offset++;
        len--;
    }

    int fg = px<<2;
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    unsigned char op = yuvclr[fg+3];
    unsigned char y_luma = yuvclr[fg+1];
    unsigned char u_val = yuvclr[fg];
    unsigned char v_val = yuvclr[fg+2];

    if (offset & 1)
    {
        register unsigned int offs2 = (offset>>1)<<2;
        opacity_buffer[0][offset] = op;
        opacity_buffer[1][offset] = op;
        ((unsigned char *)bitmap_buffer[0])[offs2+3] = y_luma;
        ((unsigned char *)bitmap_buffer[1])[offs2+3] = y_luma;
        g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, 1);
        offset++;
        len--;
    }
    unsigned short co = op + (op << 8);
    unsigned int yuv = (*(unsigned int*)(&yuvclr[fg]) & 0xffffff) + (y_luma << 24);
    unsigned short *obu0 = (unsigned short *)opacity_buffer[0];
    unsigned short *obu1 = (unsigned short *)opacity_buffer[1];
    unsigned int *bbu0 = (unsigned int *)bitmap_buffer[0];
    unsigned int *bbu1 = (unsigned int *)bitmap_buffer[1];

    int cur_x = (x & 1) ? (x + 1) : x;
    for (; len>0; len-=2, offset+=2, cur_x+=2)
    {
        unsigned int pair_idx = offset >> 1;
        obu0[pair_idx] = co;
        obu1[pair_idx] = co;
        bbu0[pair_idx] = yuv;
        bbu1[pair_idx] = yuv;

        if (!conf.rotate_osd && g3x_shadow_opacity && g3x_shadow_bitmap)
        {
            if (cur_x >= G3X_MENU_X0 && (cur_x + 1) <= G3X_MENU_X1 &&
                y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1)
            {
                int rx = cur_x - G3X_MENU_X0;
                int ry = y - G3X_MENU_Y0;
                unsigned int sh_pair = (unsigned int)((ry * G3X_SHADOW_WIDTH + rx) >> 1);
                if (sh_pair < (G3X_SHADOW_OP_SIZE / 2))
                {
                    ((unsigned short *)g3x_shadow_opacity)[sh_pair] = co;
                    ((unsigned int *)g3x_shadow_bitmap)[sh_pair] = yuv;
                }
            }
        }
    }
    if (len == -1)
    {
        offset--;
        register unsigned int offs2 = (offset>>1)<<2;
        opacity_buffer[0][offset] = op;
        opacity_buffer[1][offset] = op;
        ((unsigned char *)bitmap_buffer[0])[offs2+3] = y_luma;
        ((unsigned char *)bitmap_buffer[1])[offs2+3] = y_luma;
        g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op, u_val, v_val, 1);
    }
#else
    if (offset & 1)
    {
        unsigned char *obu = current_opacity_buf;
        unsigned char *bbu = current_bitmap_buf;
        register unsigned int offs2 = (offset>>1)<<2;
        obu[offset] = yuvclr[fg+3];
        bbu[offs2+3] = yuvclr[fg+1]; // Y
        offset++;
        len--;
    }
    unsigned short co = yuvclr[fg+3]+(yuvclr[fg+3]<<8);
    unsigned int yuv = (*(unsigned int*)(&yuvclr[fg]) & 0xffffff) + (yuvclr[fg+1]<<24);
    unsigned short *obud = (unsigned short *)current_opacity_buf;
    unsigned int *bbud = (unsigned int *)current_bitmap_buf;
    for (; len>0; len-=2, offset+=2)
    {
        obud[offset>>1] = co;
        bbud[offset>>1] = yuv;
    }
    if (len == -1)
    {
        offset--;
        unsigned char *obu = current_opacity_buf;
        unsigned char *bbu = current_bitmap_buf;
        register unsigned int offs2 = (offset>>1)<<2;
        obu[offset] = yuvclr[fg+3];
        bbu[offs2+3] = yuvclr[fg+1]; // Y
    }
#endif
}


#endif // THUMB_FW
//-------------------------------------------------------------------
#ifndef THUMB_FW

#define GUARD_VAL   COLOR_GREY_DK

void draw_set_guard()
{
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
    *((unsigned char*)(bitmap_buffer[0])) = GUARD_VAL;
    *((unsigned char*)(bitmap_buffer[1])) = GUARD_VAL;
#else
    *((unsigned char*)(frame_buffer[0])) = GUARD_VAL;
    *((unsigned char*)(frame_buffer[1])) = GUARD_VAL;
#endif
}

int draw_test_guard()
{
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
    if (*((unsigned char*)(bitmap_buffer[active_bitmap_buffer])) != GUARD_VAL) return 0;
#else
    if (*((unsigned char*)(frame_buffer[0])) != GUARD_VAL) return 0;
    if (*((unsigned char*)(frame_buffer[1])) != GUARD_VAL) return 0;
#endif
    return 1;
}

#else // DIGIC 6

#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
void draw_set_guard(void)
{
    opacity_buffer[0][0] = 0x42;
    opacity_buffer[1][0] = 0x42;
}

int draw_test_guard(void)
{
    if (opacity_buffer[0][0] != 0x42 || opacity_buffer[1][0] != 0x42) return 0;
    return 1;
}
#else
void draw_set_guard()
{
    opacity_buffer[active_bitmap_buffer][0] = 0x42;
}

int draw_test_guard()
{
    if (opacity_buffer[active_bitmap_buffer][0] != 0x42) return 0;
    return 1;
}
#endif

#endif
//-------------------------------------------------------------------
void draw_init()
{
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    /* DBUF startup: initialize and invalidate shadow buffer */
    g3x_dbuf_shadow_init();
#endif
#ifndef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
    frame_buffer[0] = vid_get_bitmap_fb();
    frame_buffer[1] = frame_buffer[0] + camera_screen.buffer_size;
#endif
    draw_set_draw_proc(NULL);

    draw_set_guard();
}

// disable draw_restore for the ms milliseconds
void draw_suspend(int ms)
{
    int t=get_tick_count() + ms;
    // only change if not already suspended to a later time
    if(t > draw_restore_suspend_tick) {
        draw_restore_suspend_tick = t;
    }
}
// disable draw_restore for the ms milliseconds
int draw_is_suspended(void)
{
    return (draw_restore_suspend_tick > get_tick_count());
}
// Restore CANON_OSD
//-------------------------------------------------------------------
void draw_restore()
{
    if(draw_is_suspended()) {
        return;
    }
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    /* Invalidation: full erase via draw_restore - reset shadow */
    g3x_dbuf_shadow_reset();
#endif
    vid_bitmap_refresh();

    draw_set_guard();
#ifdef CAM_TOUCHSCREEN_UI
    redraw_buttons = 1;
#endif
}

//-------------------------------------------------------------------
void draw_pixel(coord x, coord y, color cl)
{
    // Make sure pixel is on screen. Skip top left pixel if screen erase detection is on to avoid triggering the detector.
    if ((x < 0) || (y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height) || ((x == 0) && (y == 0))) return;
    else
    {
        register unsigned int offset = y * camera_screen.buffer_width + ASPECT_XCORRECTION(x);
        draw_pixel_proc(offset,   cl);
#if CAM_USES_ASPECT_CORRECTION
        draw_pixel_proc(offset+1, cl);  // Draw second pixel if screen scaling is needed
#endif
   }
}

void draw_pixel_unrotated(coord x, coord y, color cl)
{
    // Make sure pixel is on screen. Skip top left pixel if screen erase detection is on to avoid triggering the detector.
    if ((x < 0) || (y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height) || ((x == 0) && (y == 0))) return;
    else
    {
        register unsigned int offset = y * camera_screen.buffer_width + ASPECT_XCORRECTION(x);
        draw_pixel_proc_norm(offset,   cl);
#if CAM_USES_ASPECT_CORRECTION
        draw_pixel_proc_norm(offset+1, cl);  // Draw second pixel if screen scaling is needed
#endif
   }
}

//-------------------------------------------------------------------
color draw_get_pixel(coord x, coord y)
{
#ifndef THUMB_FW
    if ((x < 0) || (y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height)) return 0;
    if (conf.rotate_osd)
    {
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
        return bitmap_buffer[0][rotate_base - (y * camera_screen.buffer_width + ASPECT_XCORRECTION(x))];
#else
        return frame_buffer[0][rotate_base - (y * camera_screen.buffer_width + ASPECT_XCORRECTION(x))];
#endif
    }
    else
    {
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
        return bitmap_buffer[0][y * camera_screen.buffer_width + ASPECT_XCORRECTION(x)];
#else
        return frame_buffer[0][y * camera_screen.buffer_width + ASPECT_XCORRECTION(x)];
#endif
    }
#else
    // DIGIC 6 not supported
    return 0;
#endif
}

color draw_get_pixel_unrotated(coord x, coord y)
{
#ifndef THUMB_FW
    if ((x < 0) || (y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height)) return 0;
#ifdef DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY
    return bitmap_buffer[0][y * camera_screen.buffer_width + ASPECT_XCORRECTION(x)];
#else
    return frame_buffer[0][y * camera_screen.buffer_width + ASPECT_XCORRECTION(x)];
#endif
#else
    // DIGIC 6 not supported
    return 0;
#endif
}

//-------------------------------------------------------------------
#define swap(v1, v2)   {v1^=v2; v2^=v1; v1^=v2;}
//-------------------------------------------------------------------
void draw_line(coord x1, coord y1, coord x2, coord y2, color cl)
{
     unsigned char steep = abs(y2 - y1) > abs(x2 - x1);
     if (steep)
     {
         swap(x1, y1);
         swap(x2, y2);
     }
     if (x1 > x2)
     {
         swap(x1, x2);
         swap(y1, y2);
     }
     int deltax = x2 - x1;
     int deltay = abs(y2 - y1);
     int error = 0;
     int y = y1;
     int ystep = (y1 < y2)?1:-1;
     int x;
     for (x=x1; x<=x2; ++x)
     {
         if (steep) draw_pixel(y, x, cl);
         else draw_pixel(x, y, cl);
         error += deltay;
         if ((error<<1) >= deltax)
         {
             y += ystep;
             error -= deltax;
         }
     }
}

//-------------------------------------------------------------------
void draw_hline(coord x, coord y, int len, color cl)
{
    if ((y < 0) || (x >= camera_screen.width) || (y >= camera_screen.height)) return;
    if (x < 0) { len += x; x = 0; }
    if ((x + len) > camera_screen.width) len = camera_screen.width - x;
    if (conf.rotate_osd)
    {
        if ((y == camera_screen.height-1) && ((x+len) >= camera_screen.width-1)) { x--; len--; }   // Skip guard pixel
    }
    else
    {
        if ((y == 0) && (x == 0)) { x++; len--; }   // Skip guard pixel
    }
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    if (len <= 0) return;
    g3x_dbuf_fast_fill_rect(x, y, x + len - 1, y, cl);
#else
    register unsigned int offset = y * camera_screen.buffer_width + ASPECT_XCORRECTION(x);
    len = ASPECT_XCORRECTION(len);      // Scale the line length if needed
    for (; len>0; len--, offset++)
        draw_pixel_proc(offset, cl);
#endif
}

void draw_vline(coord x, coord y, int len, color cl)
{
    if ((x < 0) || (x >= camera_screen.width) || (y >= camera_screen.height)) return;
    if (y < 0) { len += y; y = 0; }
    if ((y + len) > camera_screen.height) len = camera_screen.height - y;
#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
    if (len <= 0) return;
    g3x_dbuf_fast_fill_rect(x, y, x, y + len - 1, cl);
#else
    for (; len>0; len--, y++)
        draw_pixel(x, y, cl);
#endif
}

//-------------------------------------------------------------------
// Generic rectangle
// 'flags' defines type - filled, round corners, shadow and border thickness
void draw_rectangle(coord x1, coord y1, coord x2, coord y2, twoColors cl, int flags)
{
    // Normalise values
    if (x1 > x2)
        swap(x1, x2);
    if (y1 > y2)
        swap(y1, y2);

    // Check if completely off screen
    if ((x2 < 0) || (y2 < 0) || (x1 >= camera_screen.width) || (y1 >= camera_screen.height))
        return;

    int round = (flags & RECT_ROUND_CORNERS) ? 1 : 0;
    int thickness;
    int i;

    // Shadow (do this first, as edge draw shrinks rectangle for fill)
    if (flags & RECT_SHADOW_MASK)
    {
        thickness = ((flags & RECT_SHADOW_MASK) >> 4);
        for (i=1; i<=thickness; i++)
        {
            draw_vline(x2+i, y1+1, y2 - y1, COLOR_BLACK);
            draw_hline(x1+1, y2+i, x2 - x1 + thickness, COLOR_BLACK);
        }
    }

    // Edge
    thickness = flags & RECT_BORDER_MASK;
    for (i=0; i<thickness; i++)
    {
        // Clipping done in draw_hline and draw_vline
        draw_vline(x1, y1 + round * 2, y2 - y1 - round * 4 + 1, FG_COLOR(cl));
        draw_vline(x2, y1 + round * 2, y2 - y1 - round * 4 + 1, FG_COLOR(cl));
        draw_hline(x1 + 1 + round, y1, x2 - x1 - round * 2 - 1, FG_COLOR(cl));
        draw_hline(x1 + 1 + round, y2, x2 - x1 - round * 2 - 1, FG_COLOR(cl));

        x1++; x2--;
        y1++; y2--;

        round = 0;
    }

    // Fill
    if (flags & DRAW_FILLED)
    {
        // Clip values
        if (x1 < 0) x1 = 0;
        if (y1 < 0) y1 = 0;
        if (x2 >= camera_screen.width)  x2 = camera_screen.width - 1;
        if (y2 >= camera_screen.height) y2 = camera_screen.height - 1;

#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)
        g3x_dbuf_fast_fill_rect(x1, y1, x2, y2, BG_COLOR(cl));
#else
        coord y;
        for (y = y1; y <= y2; ++y)
            draw_hline(x1, y, x2 - x1 + 1, BG_COLOR(cl));
#endif
    }
}

//-------------------------------------------------------------------
#pragma pack(1)
// Format of header block for each character in the 'font_data' array
// This is immediately followed by '16 - top - bottom' bytes of character data.
typedef struct {
    unsigned char skips;    // Top and Bottom skip counts for blank rows (4 bits each - ((top << 4) | bottom))
} FontData;
#pragma pack()

static unsigned char* get_cdata(unsigned int *offset, unsigned int *size, const char ch)
{
    FontData *f = (FontData*)get_current_font_data(ch);

    *offset = f->skips >> 4;            // # of blank lines at top
    *size = 16 - (f->skips & 0xF);      // last line of non-blank data
    if (*size == *offset)               // special case for blank char (top == 15 && bottom == 1)
        *offset++;

    return (unsigned char*)f + sizeof(FontData) - *offset;
}

#ifndef THUMB_FW
// DIGIC II...5
void draw_char(coord x, coord y, const char ch, twoColors cl)
{
    int i, ii;

    unsigned int offset, size;
    unsigned char *sym = get_cdata(&offset, &size, ch);

    // First draw blank lines at top
    for (i=0; i<offset; i++)
        draw_hline(x, y+i, FONT_WIDTH, BG_COLOR(cl));

    // Now draw character data

    int j;
    for (j=i; i<size;)
    {
        unsigned int dsym;
        int rep;
#ifdef BUILTIN_FONT_RLE_COMPRESSED
        dsym = fontdata_lookup[sym[j] & 0x7f];
        rep = sym[j] & 0x80;
#else
        dsym = sym[j];
        rep = 0;
#endif
        for (ii=0; ii<FONT_WIDTH; ii++)
        {
            draw_pixel(x+ii, y+i, (dsym & (0x80>>ii))? FG_COLOR(cl) : BG_COLOR(cl));
        }
        if (rep)
        {
            i++;
            for (ii=0; ii<FONT_WIDTH; ii++)
            {
                draw_pixel(x+ii, y+i, (dsym & (0x80>>ii))? FG_COLOR(cl) : BG_COLOR(cl));
            }
        }
        i++;
        j++;
    }

    // Last draw blank lines at bottom
    for (; i<FONT_HEIGHT; i++)
        draw_hline(x, y+i, FONT_WIDTH, BG_COLOR(cl));
}
#endif

#ifdef THUMB_FW
// DIGIC 6: "optimizations" to improve speed
void draw_char(coord x, coord y, const char ch, twoColors cl)
{
    int i, ii;

    unsigned int offset, size;
    unsigned char *sym = get_cdata(&offset, &size, ch);
    color fg = FG_COLOR(cl);
    color bg = BG_COLOR(cl);
    unsigned int fw = FONT_WIDTH;

    draw_pixel_simple_start(cl);

    // First draw blank lines at top
    for (i=0; i<offset; i++)
    {
        int j;
        j = i<<1;
        draw_hline_simple(x, y+j, fw, 0);
        draw_hline_simple(x, y+j+1, fw, 0);
    }

    // Now draw character data

    int j;
    for (j=i; i<size;)
    {
        unsigned int dsym;
        int rep;
#ifdef BUILTIN_FONT_RLE_COMPRESSED
        dsym = fontdata_lookup[sym[j] & 0x7f];
        rep = sym[j] & 0x80;
#else
        dsym = sym[j];
        rep = 0;
#endif
        {
            // upscaling 8 pixels to 14
            ii = 0;
            ii += (dsym&1)?3:0;
            ii += (dsym&2)?4:0;
            ii += (dsym&4)?0x18:0;
            ii += (dsym&8)?0x60:0;
            ii += (dsym&16)?0x180:0;
            ii += (dsym&32)?0x600:0;
            ii += (dsym&64)?0x1800:0;
            ii += (dsym&128)?0x2000:0;
            dsym = ii;
        }

        while (rep >= 0)
        {
            unsigned int px;
            unsigned int yt = y+(i<<1);
            ii = 0;
            if (x&1)
            {
                draw_1pixel_simple(x+ii, yt, dsym>>(fw-1), 1);
                ii++;
            }
            for (; ii<fw; ii+=2)
            {
                px = (dsym & ((3<<(fw-2))>>ii))>>(fw-2-ii);
                draw_2pixels_simple(x+ii, yt, px, 1);
            }
            if (x&1)
            {
                draw_1pixel_simple(x+ii-1, yt, dsym&1, 1);
            }
            rep -= 0x80;
            i++;
        }

        j++;
    }

    // Last draw blank lines at bottom
    for (; i<FONT_REAL_HEIGHT; i++)
    {
        int j;
        j = i<<1;
        draw_hline_simple(x, y+j, fw, 0);
        draw_hline_simple(x, y+j+1, fw, 0);
    }
}

void draw_char_unscaled(coord x, coord y, const char ch, twoColors cl)
{
    int i, ii;

    unsigned int offset, size;
    unsigned char *sym = get_cdata(&offset, &size, ch);
    color fg = FG_COLOR(cl);
    color bg = BG_COLOR(cl);
    unsigned int fw = FONT_REAL_WIDTH;

    draw_pixel_simple_start(cl);

    // First draw blank lines at top
    for (i=0; i<offset; i++)
    {
        draw_hline_simple(x, y+i, fw, 0);
    }

    // Now draw character data

    int j;
    for (j=i; i<size;)
    {
        unsigned int dsym;
        int rep;
#ifdef BUILTIN_FONT_RLE_COMPRESSED
        dsym = fontdata_lookup[sym[j] & 0x7f];
        rep = sym[j] & 0x80;
#else
        dsym = sym[j];
        rep = 0;
#endif

        while (rep >= 0)
        {
            unsigned int px;
            unsigned int yt = y+(i);
            ii = 0;
            if (x&1)
            {
                draw_1pixel_simple(x+ii, yt, dsym>>(fw-1), 0);
                ii++;
            }
            for (; ii<fw; ii+=2)
            {
                px = (dsym & ((3<<(fw-2))>>ii))>>(fw-2-ii);
                draw_2pixels_simple(x+ii, yt, px, 0);
            }
            if (x&1)
            {
                draw_1pixel_simple(x+ii-1, yt, dsym&1, 0);
            }
            rep -= 0x80;
            i++;
        }

        j++;
    }

    // Last draw blank lines at bottom
    for (; i<FONT_REAL_HEIGHT; i++)
    {
        draw_hline_simple(x, y+i, fw, 0);
    }
}

#endif // THUMB_FW

#ifndef THUMB_FW
void draw_char_scaled(coord x, coord y, const char ch, twoColors cl, int xsize, int ysize)
{
    int i, ii;

    twoColors clf = MAKE_COLOR(FG_COLOR(cl),FG_COLOR(cl));
    twoColors clb = MAKE_COLOR(BG_COLOR(cl),BG_COLOR(cl));

    unsigned int offset, size;
    unsigned char *sym = get_cdata(&offset, &size, ch);

    // First draw blank lines at top
    if (offset > 0)
        draw_rectangle(x,y,x+FONT_WIDTH*xsize-1,y+offset*ysize+ysize-1,clb,RECT_BORDER0|DRAW_FILLED);

    // Now draw character data
    int j;
    for (j=i=offset; i<size;)
    {
        unsigned int dsym;
        int rep;
        unsigned int last;
        int len;
#ifdef BUILTIN_FONT_RLE_COMPRESSED
        dsym = fontdata_lookup[sym[j] & 0x7f];
        rep = sym[j] & 0x80;
#else
        dsym = sym[j];
        rep = 0;
#endif
        while (rep >= 0)
        {
            last = dsym & 0x80;
            len = 1;
            for (ii=1; ii<FONT_WIDTH; ii++)
            {
                if (((dsym << ii) & 0x80) != last)
                {
                    draw_rectangle(x+(ii-len)*xsize,y+i*ysize,x+ii*xsize-1,y+i*ysize+ysize-1,(last)?clf:clb,RECT_BORDER0|DRAW_FILLED);
                    last = (dsym << ii) & 0x80;
                    len = 1;
                }
                else
                {
                    len++;
                }
            }
            draw_rectangle(x+(ii-len)*xsize,y+i*ysize,x+ii*xsize-1,y+i*ysize+ysize-1,(last)?clf:clb,RECT_BORDER0|DRAW_FILLED);
            i++;
            rep -= 0x80;
        }
        j++;
    }

    // Last draw blank lines at bottom
    if (i < FONT_HEIGHT)
        draw_rectangle(x,y+i*ysize,x+FONT_WIDTH*xsize-1,y+FONT_HEIGHT*ysize+ysize-1,clb,RECT_BORDER0|DRAW_FILLED);
}
#endif // !THUMB_FW

#ifdef THUMB_FW
void draw_char_scaled(coord x, coord y, const char ch, twoColors cl, int xsize, int ysize)
{
    int i, ii;

    twoColors clf = MAKE_COLOR(FG_COLOR(cl),FG_COLOR(cl));
    twoColors clb = MAKE_COLOR(BG_COLOR(cl),BG_COLOR(cl));

    unsigned int offset, size;
    unsigned char *sym = get_cdata(&offset, &size, ch);

    ysize <<= 1;

    // First draw blank lines at top
    if (offset > 0)
        draw_rectangle(x,y,x+FONT_WIDTH*xsize-1,y+offset*ysize+ysize-1,clb,RECT_BORDER0|DRAW_FILLED);

    // Now draw character data
    int j;
    for (j=i=offset; i<size;)
    {
        unsigned int dsym;
        int rep;
        unsigned int last;
        int len;
        unsigned int lastmask = 1 << (FONT_WIDTH-1);
#ifdef BUILTIN_FONT_RLE_COMPRESSED
        dsym = fontdata_lookup[sym[j] & 0x7f];
        rep = sym[j] & 0x80;
#else
        dsym = sym[j];
        rep = 0;
#endif
        {
            // upscaling 8 pixels to 14
            ii = 0;
            ii += (dsym&1)?3:0;
            ii += (dsym&2)?4:0;
            ii += (dsym&4)?0x18:0;
            ii += (dsym&8)?0x60:0;
            ii += (dsym&16)?0x180:0;
            ii += (dsym&32)?0x600:0;
            ii += (dsym&64)?0x1800:0;
            ii += (dsym&128)?0x2000:0;
            dsym = ii;
        }
        while (rep >= 0)
        {
            last = dsym & lastmask;
            len = 1;
            for (ii=1; ii<FONT_WIDTH; ii++)
            {
                if (((dsym << ii) & lastmask) != last)
                {
                    draw_rectangle(x+(ii-len)*xsize,y+i*ysize,x+ii*xsize-1,y+i*ysize+ysize-1,(last)?clf:clb,RECT_BORDER0|DRAW_FILLED);
                    last = (dsym << ii) & lastmask;
                    len = 1;
                }
                else
                {
                    len++;
                }
            }
            draw_rectangle(x+(ii-len)*xsize,y+i*ysize,x+ii*xsize-1,y+i*ysize+ysize-1,(last)?clf:clb,RECT_BORDER0|DRAW_FILLED);
            i++;
            rep -= 0x80;
        }
        j++;
    }

    // Last draw blank lines at bottom
    if (i < FONT_REAL_HEIGHT)
        draw_rectangle(x,y+i*ysize,x+FONT_WIDTH*xsize-1,y+FONT_REAL_HEIGHT*ysize+ysize-1,clb,RECT_BORDER0|DRAW_FILLED);
}
#endif // THUMB_FW
//-------------------------------------------------------------------
// String & text functions

// Draw a single line string up to a maximum pixel width
int draw_string_clipped(coord x, coord y, const char *s, twoColors cl, int max_width)
{
    while (*s && (*s != '\n') && (max_width >= FONT_WIDTH))
    {
	    draw_char(x, y, *s, cl);
	    s++;
        max_width -= FONT_WIDTH;
	    x += FONT_WIDTH;
	    if ((x>=camera_screen.width) && (*s))
        {
	        draw_char(x-FONT_WIDTH,y, '>', cl);
	        break;
	    }
    }
    return x;
}

// Draw a single line string
int draw_string(coord x, coord y, const char *s, twoColors cl)
{
    return draw_string_clipped(x, y, s, cl, camera_screen.width);
}

// Draw a single line string:
//      - xo = left offset to start text (only applies to left justified text)
//      - max_width = maximum pixel width to use (staring from x)
//      - justification = left, center or right justified, also controls if unused area to be filled with background color
// Returns x position of first character drawn
int draw_string_justified(coord x, coord y, const char *s, twoColors cl, int xo, int max_width, int justification)
{
    // Get length in pixels
    const char *e = strchr(s, '\n');
    int l;
    if (e)
        l = (e - s) * FONT_WIDTH;
    else
        l = strlen(s) * FONT_WIDTH;
    if (l > max_width) l = max_width;

    // Calculate justification offset
    switch (justification & 0xF)
    {
    case TEXT_RIGHT:
        xo = (max_width - l);
        break;
    case TEXT_CENTER:
        xo = ((max_width - l) >> 1);
        break;
    }

    // Fill left side
    if ((justification & TEXT_FILL) && (xo > 0))
        draw_rectangle(x, y, x+xo-1, y+FONT_HEIGHT-1, cl, RECT_BORDER0|DRAW_FILLED);

    // Draw string (get length drawn in pixels)
    l = draw_string_clipped(x+xo, y, s, cl, max_width - xo) - x;

    // Fill right side
    if ((justification & TEXT_FILL) && (l < max_width))
        draw_rectangle(x+l, y, x+max_width-1, y+FONT_HEIGHT-1, cl, RECT_BORDER0|DRAW_FILLED);

    // Return start of first character
    return x+xo;
}

// Calculate the max line length and number of lines of a multi line string
// Lines are separated by newline '\n' characters
// Returns:
//      - max line length (return value)
//      - number of lines (in *max_lines)
int text_dimensions(const char *s, int width, int max_chars, int *max_lines)
{
    int l = 0, n;
    while (s && *s && (l < *max_lines))
    {
        const char *e = strchr(s, '\n');
        if (e)
        {
            n = e - s;
            e++;
        }
        else
        {
            n = strlen(s);
        }

        if (n > width) width = n;

        s = e;
        l++;
    }
    *max_lines = l;
    if (width > max_chars) width = max_chars;
    return width;
}

// Draw multi-line text string:
//      - max_chars = max # of chars to draw
//      - max_lines = max # of lines to draw
//      - justification = left, center or right justified, with optional fill of unused space
// Returns x position of first character on last line
int draw_text_justified(coord x, coord y, const char *s, twoColors cl, int max_chars, int max_lines, int justification)
{
    int rx = 0;
    while (s && *s && (max_lines > 0))
    {
        const char *e = strchr(s, '\n');
        if (e) e++;

        rx = draw_string_justified(x, y, s, cl, 0, max_chars*FONT_WIDTH, justification);

        s = e;
        y += FONT_HEIGHT;
        max_lines--;
    }
    return rx;
}

// Draw single line string, with optiona X and Y scaling
#ifndef THUMB_FW
void draw_string_scaled(coord x, coord y, const char *s, twoColors cl, int xsize, int ysize)
{
    while (*s && (*s != '\n'))
    {
        draw_char_scaled(x, y, *s, cl, xsize, ysize);
        s++;
        x+=FONT_WIDTH*xsize;
        if ((x>=camera_screen.width) && (*s))
        {
            draw_char_scaled(x-FONT_WIDTH*xsize,y, '>', cl, xsize, ysize);
            break;
        }
    }
}
#endif

#ifdef THUMB_FW
void draw_string_scaled(coord x, coord y, const char *s, twoColors cl, int xsize, int ysize)
{
    if ((xsize==0) || (ysize==0))
    {
        while (*s && (*s != '\n'))
        {
            draw_char_unscaled(x, y, *s, cl);
            s++;
            x+=FONT_REAL_WIDTH;
            if ((x>=camera_screen.width) && (*s))
            {
                draw_char_unscaled(x-FONT_REAL_WIDTH,y, '>', cl);
                break;
            }
        }
    }
    else
    {
        while (*s && (*s != '\n'))
        {
            draw_char_scaled(x, y, *s, cl, xsize, ysize);
            s++;
            x+=FONT_WIDTH*xsize;
            if ((x>=camera_screen.width) && (*s))
            {
                draw_char_scaled(x-FONT_WIDTH*xsize,y, '>', cl, xsize, ysize);
                break;
            }
        }
    }
}
#endif

// Draw CHDK OSD string at user defined position and scale
#ifndef THUMB_FW
void draw_osd_string(OSD_pos pos, int xo, int yo, char *s, twoColors c, OSD_scale scale)
{
    if ((scale.x == 0) || (scale.y == 0) || ((scale.x == 1) && (scale.y == 1)))
        draw_string(pos.x+xo, pos.y+yo, s, c);
    else
        draw_string_scaled(pos.x+(xo*scale.x), pos.y+(yo*scale.y), s, c, scale.x, scale.y);
}
#endif

#ifdef THUMB_FW
void draw_osd_string(OSD_pos pos, int xo, int yo, char *s, twoColors c, OSD_scale scale)
{
    if ((scale.x == 1) && (scale.y == 1))
    {
        draw_string(pos.x+xo, pos.y+yo, s, c);
    }
    else if ((scale.x == 0) || (scale.y == 0))
    {
        draw_string_scaled(pos.x+(xo>>1), pos.y+(yo>>1), s, c, scale.x, scale.y);
    }
    else
    {
        draw_string_scaled(pos.x+(xo*scale.x), pos.y+(yo*scale.y), s, c, scale.x, scale.y);
    }
}
#endif

//-------------------------------------------------------------------
// Draw single line string at 'character' screen position (row, col)
// Pixel co-ordinate conversion --> x = col * FONT_WIDTH, y = row * FONT_HEIGHT
void draw_txt_string(coord col, coord row, const char *str, twoColors cl)
{
    draw_string(col*FONT_WIDTH, row*FONT_HEIGHT, str, cl);
}

//-------------------------------------------------------------------
// *** Not used ***
//void draw_circle(coord x, coord y, const unsigned int r, color cl)
//{
//    int dx = 0;
//    int dy = r;
//    int p=(3-(r<<1));
//
//    do {
//        draw_pixel((x+dx),(y+dy),cl);
//        draw_pixel((x+dy),(y+dx),cl);
//        draw_pixel((x+dy),(y-dx),cl);
//        draw_pixel((x+dx),(y-dy),cl);
//        draw_pixel((x-dx),(y-dy),cl);
//        draw_pixel((x-dy),(y-dx),cl);
//        draw_pixel((x-dy),(y+dx),cl);
//        draw_pixel((x-dx),(y+dy),cl);
//
//        ++dx;
//
//        if (p<0)
//            p += ((dx<<2)+6);
//        else {
//            --dy;
//            p += (((dx-dy)<<2)+10);
//        }
//    } while (dx<=dy);
//}

//-------------------------------------------------------------------
void draw_ellipse(coord CX, coord CY, unsigned int XRadius, unsigned int YRadius, color cl, int flags)
{
    // Bresenham fast ellipse algorithm - http://homepage.smc.edu/kennedy_john/BELIPSE.PDF
    int X, Y;
    int XChange, YChange;
    int EllipseError;
    int TwoASquare, TwoBSquare;
    int StoppingX, StoppingY;
    TwoASquare = 2*XRadius*XRadius;
    TwoBSquare = 2*YRadius*YRadius;
    X = XRadius;
    Y = 0;
    XChange = YRadius*YRadius*(1-2*XRadius);
    YChange = XRadius*XRadius;
    EllipseError = 0;
    StoppingX = TwoBSquare*XRadius;
    StoppingY = 0;
    while ( StoppingX >= StoppingY ) 
    {
        if (flags & DRAW_FILLED)
        {
            draw_hline(CX-X,CY-Y,X*2+1,cl);
            draw_hline(CX-X,CY+Y,X*2+1,cl);
        }
        else
        {
            draw_pixel(CX-X,CY-Y,cl);
            draw_pixel(CX-X,CY+Y,cl);
            draw_pixel(CX+X,CY-Y,cl);
            draw_pixel(CX+X,CY+Y,cl);
        }
        Y++;
        StoppingY += TwoASquare;
        EllipseError += YChange;
        YChange += TwoASquare;
        if ((2*EllipseError + XChange) > 0 )
        {
            X--;
            StoppingX -= TwoBSquare;
            EllipseError += XChange;
            XChange += TwoBSquare;
        }
    }
    X = 0;
    Y = YRadius;
    XChange = YRadius*YRadius;
    YChange = XRadius*XRadius*(1-2*YRadius);
    EllipseError = 0;
    StoppingX = 0;
    StoppingY = TwoASquare*YRadius;
    int lastY = Y + 1;
    while ( StoppingX <= StoppingY )
    {
        if (flags & DRAW_FILLED)
        {
            // Only draw lines if Y has changed
            if (lastY != Y)
            {
                draw_hline(CX-X,CY-Y,X*2+1,cl);
                draw_hline(CX-X,CY+Y,X*2+1,cl);
                lastY = Y;
            }
        }
        else
        {
            draw_pixel(CX-X,CY-Y,cl);
            draw_pixel(CX-X,CY+Y,cl);
            draw_pixel(CX+X,CY-Y,cl);
            draw_pixel(CX+X,CY+Y,cl);
        }
        X++;
        StoppingX += TwoBSquare;
        EllipseError += XChange;
        XChange += TwoBSquare;
        if ((2*EllipseError + YChange) > 0 )
        {
            Y--;
            StoppingY -= TwoASquare;
            EllipseError += YChange;
            YChange += TwoASquare;
        }
    }
}

//-------------------------------------------------------------------
// Draw a button
void draw_button(int x, int y, int w, int str_id, int active)
{
    twoColors cl = MAKE_COLOR((active) ? COLOR_RED : COLOR_BLACK, COLOR_WHITE);
    w = w * FONT_WIDTH;

    draw_rectangle(x-2, y-2, x+w+2, y+FONT_HEIGHT+2, cl, RECT_BORDER1|DRAW_FILLED|RECT_SHADOW1);     // main box
    draw_string(x+((w-(strlen(lang_str(str_id))*FONT_WIDTH))>>1), y, lang_str(str_id), cl);
}

//-------------------------------------------------------------------
// Draw an OSD icon from an array of actions
void draw_icon_cmds(coord x, coord y, icon_cmd *cmds)
{
    int x1, y1, x2, y2;
    while (1)
    {
        if (FONT_HEIGHT > 16)
        {
            x1 = cmds->x1<<1;
            y1 = cmds->y1<<1;
            x2 = cmds->x2<<1;
            y2 = cmds->y2<<1;
        }
        else
        {
            x1 = cmds->x1;
            y1 = cmds->y1;
            x2 = cmds->x2;
            y2 = cmds->y2;
        }
        color cf = chdk_colors[cmds->cf];       // Convert color indexes to actual colors
        color cb = chdk_colors[cmds->cb];
        switch (cmds->action)
        {
        default:
        case IA_END:
            return;
        case IA_HLINE:
            draw_hline(x+x1, y+y1, x2, cb);
            break;
        case IA_VLINE:
            draw_vline(x+x1, y+y1, y2, cb);
            break;
        case IA_LINE:
            draw_line(x+x1, y+y1, x+x2, y+y2, cb);
            break;
        case IA_RECT:
            draw_rectangle(x+x1, y+y1, x+x2, y+y2, MAKE_COLOR(cb,cf), RECT_BORDER1);
            break;
        case IA_FILLED_RECT:
            draw_rectangle(x+x1, y+y1, x+x2, y+y2, MAKE_COLOR(cb,cf), RECT_BORDER1|DRAW_FILLED);
            break;
        case IA_ROUND_RECT:
            draw_rectangle(x+x1, y+y1, x+x2, y+y2, MAKE_COLOR(cb,cf), RECT_BORDER1|RECT_ROUND_CORNERS);
            break;
        case IA_FILLED_ROUND_RECT:
            draw_rectangle(x+x1, y+y1, x+x2, y+y2, MAKE_COLOR(cb,cf), RECT_BORDER1|DRAW_FILLED|RECT_ROUND_CORNERS);
            break;
        }
        cmds++;
    }
}

//-------------------------------------------------------------------

extern unsigned char ply_colors[];
extern unsigned char rec_colors[];

unsigned char *chdk_colors = ply_colors;

void set_palette()
{
#ifndef THUMB_FW
    if (camera_info.state.mode_rec)
        chdk_colors = rec_colors;
    else
        chdk_colors = ply_colors;
#endif
}

color get_script_color(int cl)
{
    if (cl < 256)
        return cl;
    else
        return chdk_colors[cl-256];
}

// Convert user adjustable color (from conf struct) to Canon colors
color chdkColorToCanonColor(chdkColor col)
{
    if (col.type)
        return chdk_colors[col.col];
    return col.col;
}

twoColors user_color(confColor cc)
{
    color fg = chdkColorToCanonColor(cc.fg);
    color bg = chdkColorToCanonColor(cc.bg);

    return MAKE_COLOR(bg,fg);
}

//-------------------------------------------------------------------
