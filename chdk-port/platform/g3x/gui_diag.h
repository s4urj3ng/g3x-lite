/* PORT-47 / PORT-48: Opt-in G3X_GUI_DIAG=1 and G3X_GUI_SHADOW2=1 overdraw/restore counters,
 * ordered shadow allocation fallback chain (exmem -> rect -> idx), shadow-blit restore,
 * GetMemInfo largest-free-block readout, and adapted G5X check_gui_needs_redraw suppression.
 *
 * Layered on: G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1
 * (and G3X_GUI_DIAG=1 when G3X_GUI_SHADOW2=1 is enabled)
 *
 * Sibling & FINSIG citations:
 * - chdk-port/platform/g5x/lib.c:206 (check_gui_needs_redraw)
 * - chdk-port/platform/g5x/platform_camera.h:85 (CAM_DETECT_BITMAP_UPDATE)
 * - chdk-port/platform/generic/wrappers.c:1003 (exmem_alloc_cached -> _exmem_alloc)
 * - chdk-port/platform/generic/wrappers.c:1020,1045,1090 (canon_malloc, umalloc, GetMemInfo)
 * - chdk-port/core/memmgmt.c:180-186 (exmem_alloc_cached pool 0 = EXMEM_RAMDISK)
 * - chdk-port/core/main.c:316 (caller)
 * - reference/finsig_gm110c/stubs_entry.S:186 (active_bitmap_buffer = 0x0000D2A4; platform stubs_entry.S:190)
 * - reference/finsig_gm110c/stubs_entry.S:188 (bitmap_buffer = 0x0000D2A8; platform stubs_entry.S:192)
 * - reference/finsig_gm110c/stubs_entry.S:197 (AllocateUncacheableMemory = 0xFC144471; platform stubs_entry.S:201)
 * - reference/finsig_gm110c/stubs_entry.S:235 (GetMemInfo = 0xFC610AB9; platform stubs_entry.S:239)
 * - reference/finsig_gm110c/stubs_entry.S:298 (exmem_alloc = 0xFC092537; platform stubs_entry.S:302)
 * - reference/finsig_gm110c/stubs_entry.S:308 (malloc = 0xFC381525; platform stubs_entry.S:312)
 */
#ifndef G3X_GUI_DIAG_H
#define G3X_GUI_DIAG_H

#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
#if !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1) || \
    !defined(G3X_GUI_SHADOW2) || (G3X_GUI_SHADOW2 != 1)
#error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
#endif
#endif

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
#if !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1)
#error G3X_GUI_SHADOW2=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1
#endif
#endif

#if defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)
#if !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1)
#error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1
#endif

#ifndef G3X_MENU_X0
#define G3X_MENU_X0           10
#define G3X_MENU_Y0           12
#define G3X_MENU_WIDTH        880
#define G3X_MENU_HEIGHT       576
#define G3X_MENU_X1           (G3X_MENU_X0 + G3X_MENU_WIDTH - 1)  /* 889 */
#define G3X_MENU_Y1           (G3X_MENU_Y0 + G3X_MENU_HEIGHT - 1) /* 587 */
#endif

#ifndef G3X_SHADOW_WIDTH
#define G3X_SHADOW_WIDTH      G3X_MENU_WIDTH
#define G3X_SHADOW_HEIGHT     G3X_MENU_HEIGHT
#define G3X_SHADOW_BM_SIZE    (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 2) /* 1,013,760 B */
#define G3X_SHADOW_OP_SIZE    (G3X_SHADOW_WIDTH * G3X_SHADOW_HEIGHT * 1) /*   506,880 B */
#define G3X_SHADOW_TOTAL_SIZE (G3X_SHADOW_BM_SIZE + G3X_SHADOW_OP_SIZE)  /* 1,520,640 B */
#endif

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
/* PORT-48 Step 1: Full-screen shadow in exmem (EXMEM_RAMDISK pool 0) */
#define G3X_SHADOW_FULL_X0         0
#define G3X_SHADOW_FULL_Y0         0
#define G3X_SHADOW_FULL_WIDTH      928
#define G3X_SHADOW_FULL_HEIGHT     600
#define G3X_SHADOW_FULL_BM_SIZE    (G3X_SHADOW_FULL_WIDTH * G3X_SHADOW_FULL_HEIGHT * 2) /* 1,113,600 B */
#define G3X_SHADOW_FULL_OP_SIZE    (G3X_SHADOW_FULL_WIDTH * G3X_SHADOW_FULL_HEIGHT * 1) /*   556,800 B */
#define G3X_SHADOW_FULL_TOTAL_SIZE (G3X_SHADOW_FULL_BM_SIZE + G3X_SHADOW_FULL_OP_SIZE)  /* 1,670,400 B */

/* PORT-48 Step 2: Reduced ALT/menu rectangle at full depth (16bpp UYVY + 8bpp opacity) */
#define G3X_SHADOW_RECT_X0         G3X_MENU_X0
#define G3X_SHADOW_RECT_Y0         G3X_MENU_Y0
#define G3X_SHADOW_RECT_WIDTH      G3X_MENU_WIDTH
#define G3X_SHADOW_RECT_HEIGHT     G3X_MENU_HEIGHT
#define G3X_SHADOW_RECT_BM_SIZE    (G3X_SHADOW_RECT_WIDTH * G3X_SHADOW_RECT_HEIGHT * 2) /* 1,013,760 B */
#define G3X_SHADOW_RECT_OP_SIZE    (G3X_SHADOW_RECT_WIDTH * G3X_SHADOW_RECT_HEIGHT * 1) /*   506,880 B */
#define G3X_SHADOW_RECT_TOTAL_SIZE (G3X_SHADOW_RECT_BM_SIZE + G3X_SHADOW_RECT_OP_SIZE)  /* 1,520,640 B */

/* PORT-48 Step 3: Reduced ALT/menu rectangle at 1 byte per pixel (palette index) */
#define G3X_SHADOW_IDX_X0          G3X_MENU_X0
#define G3X_SHADOW_IDX_Y0          G3X_MENU_Y0
#define G3X_SHADOW_IDX_WIDTH       G3X_MENU_WIDTH
#define G3X_SHADOW_IDX_HEIGHT      G3X_MENU_HEIGHT
#define G3X_SHADOW_IDX_TOTAL_SIZE  (G3X_SHADOW_IDX_WIDTH * G3X_SHADOW_IDX_HEIGHT * 1)   /*   506,880 B */

#define G3X_SHADOW_MODE_NONE       0
#define G3X_SHADOW_MODE_EXMEM      1
#define G3X_SHADOW_MODE_HEAP       2
#define G3X_SHADOW_MODE_RECT       3
#define G3X_SHADOW_MODE_IDX        4

#define G3X_DIAG_LINE_MAX_CHARS    55
#endif

#define G3X_DIAG_LINE_CHARS   51

extern unsigned int g3x_diag_hook_installed;
extern unsigned int g3x_diag_hook_hits;
extern unsigned int g3x_diag_sentinel_loss_count;
extern unsigned int g3x_diag_shadow_restore_count;
extern unsigned int g3x_diag_full_redraw_count;
extern unsigned int g3x_diag_suppress_hit_count;
extern int g3x_diag_suppress_engaged;
extern int g3x_diag_last_bitmap_buffer;

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
extern int g3x_shadow2_mode;
extern unsigned int g3x_shadow2_bytes;
extern int g3x_shadow2_x0;
extern int g3x_shadow2_y0;
extern int g3x_shadow2_w;
extern int g3x_shadow2_h;
extern int g3x_shadow2_largest_free;
extern int g3x_shadow2_ov_valid;
extern int g3x_shadow2_ov_x0;
extern int g3x_shadow2_ov_y0;
extern int g3x_shadow2_ov_x1;
extern int g3x_shadow2_ov_y1;
extern int g3x_shadow2_in_fallback_redraw;

const char *g3x_shadow2_mode_tag(int mode);
void g3x_shadow2_reset_overlay_bounds(void);
void g3x_shadow2_record_overlay_rect(int x0, int y0, int x1, int y1);
void g3x_shadow2_get_overlay_rect(int *out_x0, int *out_y0, int *out_x1, int *out_y1);
void g3x_shadow2_reset_buffer(unsigned char *bm, unsigned char *op);
void g3x_shadow2_expand_pair(unsigned char c0, unsigned char c1,
                             unsigned int *out_uyvy, unsigned short *out_op);
void g3x_shadow2_write_pixel(unsigned char *bm, unsigned char *op,
                             int screen_x, int screen_y,
                             unsigned char y_luma, unsigned char o_val,
                             unsigned char u_val, unsigned char v_val,
                             int is_odd, unsigned char cl);
void g3x_shadow2_write_pair(unsigned char *bm, unsigned char *op,
                            int screen_x, int screen_y,
                            unsigned int yuv, unsigned short co,
                            unsigned char c0, unsigned char c1);
void g3x_shadow2_fill_span(unsigned char *bm, unsigned char *op,
                           int screen_x_start, int screen_x_end, int screen_y,
                           unsigned int uyvy_word, unsigned char op_byte,
                           unsigned char cl);
int g3x_shadow2_blit_restore(unsigned char *bm, unsigned char *op, int buf_w);
int g3x_shadow2_intersects_rect(int x0, int y0, int x1, int y1);
int g3x_shadow2_covers_rect(int x0, int y0, int x1, int y1);
int g3x_shadow2_covers_active_overlay(void);
int g3x_shadow2_restore_rect(int x0, int y0, int x1, int y1);
int g3x_shadow2_handle_gui_redraw_sentinel(int *flag_gui_enforce_redraw);
int g3x_shadow2_query_largest_free(void);
void g3x_diag_format_line(char *line);
#endif

void g3x_diag_set_hook_installed(int installed);
void g3x_diag_record_hook_hit(void);
void g3x_diag_record_sentinel_loss(void);
void g3x_diag_record_shadow_restore(void);
void g3x_diag_record_full_redraw(void);
void g3x_diag_shadow_ensure_allocated(unsigned char **bm_ptr,
                                      unsigned char **op_ptr,
                                      int *valid_ptr,
                                      int *attempted_ptr);
void g3x_diag_on_alt_enter(void);
void g3x_diag_on_alt_leave(void);
int g3x_diag_check_suppress(void);
int g3x_diag_restore_overlay(int trigger);
void gui_diag_draw(void);

#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
#if defined(G3X_GUI_DIAG_IMPLEMENTATION)
#undef G3X_GUI_DIAG_IMPLEMENTATION
#include "sub/110c/gui_sync.h"
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#else
#include "sub/110c/gui_sync.h"
#endif
#endif

#if defined(G3X_GUI_DIAG_IMPLEMENTATION) && (G3X_GUI_DIAG_IMPLEMENTATION == 1)

extern int active_bitmap_buffer;
extern int draw_test_guard(void);
extern int g3x_dbuf_shadow_is_allocated(void);
extern void g3x_dbuf_shadow_ensure_allocated(void);
extern int g3x_dbuf_shadow_restore(void);
extern void gui_redraw(int flag_gui_enforce_redraw);

unsigned int g3x_diag_hook_installed = 1u;
unsigned int g3x_diag_hook_hits = 0u;
unsigned int g3x_diag_sentinel_loss_count = 0u;
unsigned int g3x_diag_shadow_restore_count = 0u;
unsigned int g3x_diag_full_redraw_count = 0u;
unsigned int g3x_diag_suppress_hit_count = 0u;
int g3x_diag_suppress_engaged = 0;
int g3x_diag_last_bitmap_buffer = -1;

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
#ifndef MEMINFO_H
#include "meminfo.h"
#endif

extern void *exmem_alloc_cached(unsigned int pool_id, unsigned int size, int unk, int unk2);
extern char *bitmap_buffer[];
extern volatile char *opacity_buffer[];
extern void g3x_dbuf_fast_fill_rect(coord x1, coord y1, coord x2, coord y2, color cl);
extern void draw_set_guard(void);

int g3x_shadow2_mode = G3X_SHADOW_MODE_NONE;
unsigned int g3x_shadow2_bytes = 0u;
int g3x_shadow2_x0 = 0;
int g3x_shadow2_y0 = 0;
int g3x_shadow2_w = 0;
int g3x_shadow2_h = 0;
int g3x_shadow2_largest_free = -1;
int g3x_shadow2_ov_valid = 0;
int g3x_shadow2_ov_x0 = G3X_MENU_X0;
int g3x_shadow2_ov_y0 = G3X_MENU_Y0;
int g3x_shadow2_ov_x1 = G3X_MENU_X1;
int g3x_shadow2_ov_y1 = G3X_MENU_Y1;
int g3x_shadow2_in_fallback_redraw = 0;

const char *g3x_shadow2_mode_tag(int mode)
{
    switch (mode)
    {
    case G3X_SHADOW_MODE_EXMEM:
        return "exmem";
    case G3X_SHADOW_MODE_HEAP:
        return "heap";
    case G3X_SHADOW_MODE_RECT:
        return "rect";
    case G3X_SHADOW_MODE_IDX:
        return "idx";
    default:
        return "NULL";
    }
}

void g3x_shadow2_reset_overlay_bounds(void)
{
    g3x_shadow2_ov_valid = 0;
    g3x_shadow2_ov_x0 = G3X_MENU_X0;
    g3x_shadow2_ov_y0 = G3X_MENU_Y0;
    g3x_shadow2_ov_x1 = G3X_MENU_X1;
    g3x_shadow2_ov_y1 = G3X_MENU_Y1;
}

void g3x_shadow2_record_overlay_rect(int x0, int y0, int x1, int y1)
{
    if (x0 > x1) { int t = x0; x0 = x1; x1 = t; }
    if (y0 > y1) { int t = y0; y0 = y1; y1 = t; }
    if (x1 < 0 || y1 < 0 || x0 >= G3X_SHADOW_FULL_WIDTH || y0 >= G3X_SHADOW_FULL_HEIGHT)
        return;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= G3X_SHADOW_FULL_WIDTH) x1 = G3X_SHADOW_FULL_WIDTH - 1;
    if (y1 >= G3X_SHADOW_FULL_HEIGHT) y1 = G3X_SHADOW_FULL_HEIGHT - 1;
    if (!g3x_shadow2_ov_valid)
    {
        g3x_shadow2_ov_x0 = x0;
        g3x_shadow2_ov_y0 = y0;
        g3x_shadow2_ov_x1 = x1;
        g3x_shadow2_ov_y1 = y1;
        g3x_shadow2_ov_valid = 1;
    }
    else
    {
        if (x0 < g3x_shadow2_ov_x0) g3x_shadow2_ov_x0 = x0;
        if (y0 < g3x_shadow2_ov_y0) g3x_shadow2_ov_y0 = y0;
        if (x1 > g3x_shadow2_ov_x1) g3x_shadow2_ov_x1 = x1;
        if (y1 > g3x_shadow2_ov_y1) g3x_shadow2_ov_y1 = y1;
    }
}

void g3x_shadow2_get_overlay_rect(int *out_x0, int *out_y0, int *out_x1, int *out_y1)
{
    int x0 = g3x_shadow2_ov_valid ? g3x_shadow2_ov_x0 : G3X_MENU_X0;
    int y0 = g3x_shadow2_ov_valid ? g3x_shadow2_ov_y0 : G3X_MENU_Y0;
    int x1 = g3x_shadow2_ov_valid ? g3x_shadow2_ov_x1 : G3X_MENU_X1;
    int y1 = g3x_shadow2_ov_valid ? g3x_shadow2_ov_y1 : G3X_MENU_Y1;

    if (camera_info.state.osd_title_line)
    {
        int scr_h = camera_screen.height ? camera_screen.height : G3X_SHADOW_FULL_HEIGHT;
        int disp_w = camera_screen.disp_width ? camera_screen.disp_width : G3X_SHADOW_FULL_WIDTH;
        int tx0 = camera_screen.disp_left;
        int ty0 = scr_h - FONT_HEIGHT;
        int tx1 = tx0 + disp_w - 1;
        int ty1 = scr_h - 1;
        if (tx0 < 0) tx0 = 0;
        if (ty0 < 0) ty0 = 0;
        if (tx1 >= G3X_SHADOW_FULL_WIDTH) tx1 = G3X_SHADOW_FULL_WIDTH - 1;
        if (ty1 >= G3X_SHADOW_FULL_HEIGHT) ty1 = G3X_SHADOW_FULL_HEIGHT - 1;
        if (tx0 < x0) x0 = tx0;
        if (ty0 < y0) y0 = ty0;
        if (tx1 > x1) x1 = tx1;
        if (ty1 > y1) y1 = ty1;
    }

    if (out_x0) *out_x0 = x0;
    if (out_y0) *out_y0 = y0;
    if (out_x1) *out_x1 = x1;
    if (out_y1) *out_y1 = y1;
}

int g3x_shadow2_query_largest_free(void)
{
    cam_meminfo meminfo;
    memset(&meminfo, 0, sizeof(meminfo));
    GetMemInfo(&meminfo);
    g3x_shadow2_largest_free = meminfo.free_block_max_size;
    return g3x_shadow2_largest_free;
}

void g3x_shadow2_reset_buffer(unsigned char *bm, unsigned char *op)
{
    (void)op;
    g3x_shadow2_reset_overlay_bounds();
    if (bm != 0 && g3x_shadow2_bytes > 0u)
    {
        memset(bm, 0, g3x_shadow2_bytes);
    }
}

void g3x_shadow2_expand_pair(unsigned char c0, unsigned char c1,
                             unsigned int *out_uyvy, unsigned short *out_op)
{
    unsigned int y0 = (((unsigned int)c0 - 1u) ^ 0xffffffffu) & 0xf0u;
    unsigned int o0 = (c0 & 0x0fu) ? 255u : (unsigned int)c0;
    unsigned int v0 = (unsigned int)c0;
    unsigned int u0 = v0 + 1u;
    if (!(u0 & 2u))
    {
        u0 = 128u;
        v0 = 128u;
    }
    else
    {
        u0 *= 3u;
        v0 <<= 3u;
    }

    unsigned int y1 = (((unsigned int)c1 - 1u) ^ 0xffffffffu) & 0xf0u;
    unsigned int o1 = (c1 & 0x0fu) ? 255u : (unsigned int)c1;

    if (out_uyvy)
    {
        *out_uyvy = (u0 & 0xffu) | ((y0 & 0xffu) << 8) | ((v0 & 0xffu) << 16) | ((y1 & 0xffu) << 24);
    }
    if (out_op)
    {
        *out_op = (unsigned short)((o0 & 0xffu) | ((o1 & 0xffu) << 8));
    }
}

void g3x_shadow2_write_pixel(unsigned char *bm, unsigned char *op,
                             int screen_x, int screen_y,
                             unsigned char y_luma, unsigned char o_val,
                             unsigned char u_val, unsigned char v_val,
                             int is_odd, unsigned char cl)
{
    g3x_shadow2_record_overlay_rect(screen_x, screen_y, screen_x, screen_y);

    if (!bm || !op || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE)
        return;

    if (screen_x < g3x_shadow2_x0 || screen_x >= (g3x_shadow2_x0 + g3x_shadow2_w) ||
        screen_y < g3x_shadow2_y0 || screen_y >= (g3x_shadow2_y0 + g3x_shadow2_h))
        return;

    int rx = screen_x - g3x_shadow2_x0;
    int ry = screen_y - g3x_shadow2_y0;
    unsigned int sh_offset = (unsigned int)(ry * g3x_shadow2_w + rx);
    unsigned int max_pixels = (unsigned int)(g3x_shadow2_w * g3x_shadow2_h);
    if (sh_offset >= max_pixels)
        return;

    if (g3x_shadow2_mode == G3X_SHADOW_MODE_IDX)
    {
        bm[sh_offset] = cl;
    }
    else
    {
        unsigned int sh_offs2 = (sh_offset >> 1) << 2;
        op[sh_offset] = o_val;
        if (is_odd)
        {
            bm[sh_offs2 + 3] = y_luma;
        }
        else
        {
            bm[sh_offs2 + 0] = u_val;
            bm[sh_offs2 + 1] = y_luma;
            bm[sh_offs2 + 2] = v_val;
        }
    }
}

void g3x_shadow2_write_pair(unsigned char *bm, unsigned char *op,
                            int screen_x, int screen_y,
                            unsigned int yuv, unsigned short co,
                            unsigned char c0, unsigned char c1)
{
    g3x_shadow2_record_overlay_rect(screen_x, screen_y, screen_x + 1, screen_y);

    if (!bm || !op || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE)
        return;

    if (screen_x < g3x_shadow2_x0 || (screen_x + 1) >= (g3x_shadow2_x0 + g3x_shadow2_w) ||
        screen_y < g3x_shadow2_y0 || screen_y >= (g3x_shadow2_y0 + g3x_shadow2_h))
        return;

    int rx = screen_x - g3x_shadow2_x0;
    int ry = screen_y - g3x_shadow2_y0;
    unsigned int sh_offset = (unsigned int)(ry * g3x_shadow2_w + rx);
    unsigned int max_pixels = (unsigned int)(g3x_shadow2_w * g3x_shadow2_h);
    if ((sh_offset + 1u) >= max_pixels)
        return;

    if (g3x_shadow2_mode == G3X_SHADOW_MODE_IDX)
    {
        bm[sh_offset] = c0;
        bm[sh_offset + 1u] = c1;
    }
    else
    {
        unsigned int sh_pair = sh_offset >> 1;
        ((unsigned short *)op)[sh_pair] = co;
        ((unsigned int *)bm)[sh_pair] = yuv;
    }
}

void g3x_shadow2_fill_span(unsigned char *bm, unsigned char *op,
                           int screen_x_start, int screen_x_end, int screen_y,
                           unsigned int uyvy_word, unsigned char op_byte,
                           unsigned char cl)
{
    g3x_shadow2_record_overlay_rect(screen_x_start, screen_y, screen_x_end, screen_y);

    if (!bm || !op || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE)
        return;

    int sh_x0 = g3x_shadow2_x0;
    int sh_y0 = g3x_shadow2_y0;
    int sh_x1 = sh_x0 + g3x_shadow2_w - 1;
    int sh_y1 = sh_y0 + g3x_shadow2_h - 1;

    if (screen_y < sh_y0 || screen_y > sh_y1)
        return;

    int x_start = (screen_x_start > sh_x0) ? screen_x_start : sh_x0;
    int x_end = (screen_x_end < sh_x1) ? screen_x_end : sh_x1;
    if (x_start > x_end)
        return;

    int ry = screen_y - sh_y0;
    int rx_start = x_start - sh_x0;
    int sh_pixels = x_end - x_start + 1;
    unsigned int sh_op_off = (unsigned int)(ry * g3x_shadow2_w + rx_start);
    unsigned int max_pixels = (unsigned int)(g3x_shadow2_w * g3x_shadow2_h);
    if ((sh_op_off + (unsigned int)sh_pixels) > max_pixels)
        return;

    if (g3x_shadow2_mode == G3X_SHADOW_MODE_IDX)
    {
        memset(&bm[sh_op_off], cl, sh_pixels);
    }
    else
    {
        unsigned int sh_bm_off = sh_op_off * 2u;
        memset(&op[sh_op_off], op_byte, sh_pixels);
        int sh_pairs = sh_pixels / 2;
        unsigned int *sp = (unsigned int *)(&bm[sh_bm_off]);
        for (int sw = 0; sw < sh_pairs; ++sw)
        {
            sp[sw] = uyvy_word;
        }
    }
}

int g3x_shadow2_blit_restore(unsigned char *bm, unsigned char *op, int buf_w)
{
    if (!bm || !op || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE ||
        g3x_shadow2_w <= 0 || g3x_shadow2_h <= 0)
    {
        return 0;
    }

    if (g3x_shadow2_mode == G3X_SHADOW_MODE_IDX)
    {
        for (int ry = 0; ry < g3x_shadow2_h; ++ry)
        {
            int screen_y = g3x_shadow2_y0 + ry;
            unsigned int dst_pair_base = (unsigned int)((screen_y * buf_w + g3x_shadow2_x0) >> 1);
            const unsigned char *src_idx = bm + (ry * g3x_shadow2_w);
            unsigned short *dst_op0 = (unsigned short *)(opacity_buffer[0]) + dst_pair_base;
            unsigned short *dst_op1 = (unsigned short *)(opacity_buffer[1]) + dst_pair_base;
            unsigned int *dst_bm0 = (unsigned int *)(bitmap_buffer[0]) + dst_pair_base;
            unsigned int *dst_bm1 = (unsigned int *)(bitmap_buffer[1]) + dst_pair_base;
            int pairs = g3x_shadow2_w >> 1;
            for (int p = 0; p < pairs; ++p)
            {
                unsigned int uyvy = 0u;
                unsigned short op16 = 0u;
                g3x_shadow2_expand_pair(src_idx[p * 2], src_idx[p * 2 + 1], &uyvy, &op16);
                dst_op0[p] = op16;
                dst_op1[p] = op16;
                dst_bm0[p] = uyvy;
                dst_bm1[p] = uyvy;
            }
        }
        return 1;
    }

    for (int ry = 0; ry < g3x_shadow2_h; ++ry)
    {
        int screen_y = g3x_shadow2_y0 + ry;
        unsigned int offset_op = (unsigned int)(screen_y * buf_w + g3x_shadow2_x0);
        unsigned int offset_bm = offset_op * 2u;

        unsigned char *src_op = op + ry * g3x_shadow2_w;
        unsigned char *src_bm = bm + (ry * g3x_shadow2_w) * 2;

        memcpy((void *)&opacity_buffer[0][offset_op], src_op, g3x_shadow2_w);
        memcpy((void *)&opacity_buffer[1][offset_op], src_op, g3x_shadow2_w);

        memcpy((void *)&bitmap_buffer[0][offset_bm], src_bm, g3x_shadow2_w * 2);
        memcpy((void *)&bitmap_buffer[1][offset_bm], src_bm, g3x_shadow2_w * 2);
    }
    return 1;
}

int g3x_shadow2_intersects_rect(int x0, int y0, int x1, int y1)
{
    if (!g3x_dbuf_shadow_is_allocated() || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE ||
        g3x_shadow2_w <= 0 || g3x_shadow2_h <= 0)
    {
        return 0;
    }
    if (x0 > x1) { int t = x0; x0 = x1; x1 = t; }
    if (y0 > y1) { int t = y0; y0 = y1; y1 = t; }
    int sh_x1 = g3x_shadow2_x0 + g3x_shadow2_w - 1;
    int sh_y1 = g3x_shadow2_y0 + g3x_shadow2_h - 1;
    return (x1 >= g3x_shadow2_x0 && x0 <= sh_x1 &&
            y1 >= g3x_shadow2_y0 && y0 <= sh_y1) ? 1 : 0;
}

int g3x_shadow2_covers_rect(int x0, int y0, int x1, int y1)
{
    if (!g3x_dbuf_shadow_is_allocated() || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE ||
        g3x_shadow2_w <= 0 || g3x_shadow2_h <= 0)
    {
        return 0;
    }
    if (x0 > x1) { int t = x0; x0 = x1; x1 = t; }
    if (y0 > y1) { int t = y0; y0 = y1; y1 = t; }
    int sh_x1 = g3x_shadow2_x0 + g3x_shadow2_w - 1;
    int sh_y1 = g3x_shadow2_y0 + g3x_shadow2_h - 1;
    return (x0 >= g3x_shadow2_x0 && y0 >= g3x_shadow2_y0 &&
            x1 <= sh_x1 && y1 <= sh_y1) ? 1 : 0;
}

int g3x_shadow2_covers_active_overlay(void)
{
    int ov_x0 = G3X_MENU_X0;
    int ov_y0 = G3X_MENU_Y0;
    int ov_x1 = G3X_MENU_X1;
    int ov_y1 = G3X_MENU_Y1;
    g3x_shadow2_get_overlay_rect(&ov_x0, &ov_y0, &ov_x1, &ov_y1);
    return g3x_shadow2_covers_rect(ov_x0, ov_y0, ov_x1, ov_y1);
}

int g3x_shadow2_restore_rect(int x0, int y0, int x1, int y1)
{
    if (g3x_shadow2_intersects_rect(x0, y0, x1, y1))
    {
        (void)g3x_dbuf_shadow_restore();
    }
    if (g3x_shadow2_covers_rect(x0, y0, x1, y1))
    {
        return 0;
    }
    draw_set_guard();
    g3x_diag_record_full_redraw();
    g3x_shadow2_in_fallback_redraw = 1;
    gui_redraw(1);
    g3x_shadow2_in_fallback_redraw = 0;
    return 1;
}

int g3x_shadow2_handle_gui_redraw_sentinel(int *flag_gui_enforce_redraw)
{
    if (g3x_shadow2_in_fallback_redraw)
    {
        if (flag_gui_enforce_redraw)
        {
            *flag_gui_enforce_redraw = 1;
        }
        return 0;
    }

    int ov_x0 = G3X_MENU_X0;
    int ov_y0 = G3X_MENU_Y0;
    int ov_x1 = G3X_MENU_X1;
    int ov_y1 = G3X_MENU_Y1;
    g3x_shadow2_get_overlay_rect(&ov_x0, &ov_y0, &ov_x1, &ov_y1);

    g3x_diag_record_sentinel_loss();
    if (g3x_shadow2_intersects_rect(ov_x0, ov_y0, ov_x1, ov_y1))
    {
        (void)g3x_dbuf_shadow_restore();
    }
    if (g3x_shadow2_covers_rect(ov_x0, ov_y0, ov_x1, ov_y1))
    {
        return 1;
    }
    g3x_diag_record_full_redraw();
    draw_set_guard();
    if (flag_gui_enforce_redraw)
    {
        *flag_gui_enforce_redraw = 1;
    }
    return 0;
}
#endif /* G3X_GUI_SHADOW2 == 1 */

static unsigned int g3x_diag_clamp9999(unsigned int val)
{
    return (val > 9999u) ? 9999u : val;
}

void g3x_diag_set_hook_installed(int installed)
{
    g3x_diag_hook_installed = installed ? 1u : 0u;
}

void g3x_diag_record_hook_hit(void)
{
    if (g3x_diag_hook_installed)
        g3x_diag_hook_hits++;
}

void g3x_diag_record_sentinel_loss(void)
{
    g3x_diag_sentinel_loss_count++;
}

void g3x_diag_record_shadow_restore(void)
{
    g3x_diag_shadow_restore_count++;
}

void g3x_diag_record_full_redraw(void)
{
    g3x_diag_full_redraw_count++;
}

#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
#include "sub/110c/gui_sync.h"
#endif

/* Requirement (a)/(b): Allocate the shadow on ALT entry only (nothing at boot).
 * Under G3X_GUI_SHADOW2=1, try ordered fallback chain:
 *   1. exmem_alloc_cached(0, 1670400, 0, 0) -> full-screen 928x600 shadow ("exmem")
 *   2. malloc/umalloc(1520640) -> 880x576 ALT/menu rect at full depth ("rect")
 *   3. malloc/umalloc(506880) -> 880x576 ALT/menu rect at 1B/px palette index ("idx")
 * Every step is NULL-checked. While NULL, retry on each ALT entry. */
void g3x_diag_shadow_ensure_allocated(unsigned char **bm_ptr,
                                      unsigned char **op_ptr,
                                      int *valid_ptr,
                                      int *attempted_ptr)
{
    if (!bm_ptr || !op_ptr || !valid_ptr || !attempted_ptr)
        return;

    if (*bm_ptr != 0 && *op_ptr != 0)
        return;

    *attempted_ptr = 1;

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
    /* Step 1: Chosen large-block allocator (exmem_alloc, pool 0 = EXMEM_RAMDISK), full-screen shadow */
    void *buf = exmem_alloc_cached(0u, G3X_SHADOW_FULL_TOTAL_SIZE, 0, 0);
    if (buf != 0)
    {
        *bm_ptr = (unsigned char *)buf;
        *op_ptr = (unsigned char *)buf + G3X_SHADOW_FULL_BM_SIZE;
        memset(buf, 0, G3X_SHADOW_FULL_TOTAL_SIZE);
        g3x_shadow2_mode = G3X_SHADOW_MODE_EXMEM;
        g3x_shadow2_bytes = (unsigned int)G3X_SHADOW_FULL_TOTAL_SIZE;
        g3x_shadow2_x0 = G3X_SHADOW_FULL_X0;
        g3x_shadow2_y0 = G3X_SHADOW_FULL_Y0;
        g3x_shadow2_w = G3X_SHADOW_FULL_WIDTH;
        g3x_shadow2_h = G3X_SHADOW_FULL_HEIGHT;
        *valid_ptr = 1;
        (void)g3x_shadow2_query_largest_free();
        return;
    }

    /* Step 2: Heap malloc/umalloc of reduced shadow covering drawn ALT/menu rectangle at full depth */
    buf = malloc(G3X_SHADOW_RECT_TOTAL_SIZE);
    if (buf == 0)
    {
        buf = umalloc(G3X_SHADOW_RECT_TOTAL_SIZE);
    }
    if (buf != 0)
    {
        *bm_ptr = (unsigned char *)buf;
        *op_ptr = (unsigned char *)buf + G3X_SHADOW_RECT_BM_SIZE;
        memset(buf, 0, G3X_SHADOW_RECT_TOTAL_SIZE);
        g3x_shadow2_mode = G3X_SHADOW_MODE_RECT;
        g3x_shadow2_bytes = (unsigned int)G3X_SHADOW_RECT_TOTAL_SIZE;
        g3x_shadow2_x0 = G3X_SHADOW_RECT_X0;
        g3x_shadow2_y0 = G3X_SHADOW_RECT_Y0;
        g3x_shadow2_w = G3X_SHADOW_RECT_WIDTH;
        g3x_shadow2_h = G3X_SHADOW_RECT_HEIGHT;
        *valid_ptr = 1;
        (void)g3x_shadow2_query_largest_free();
        return;
    }

    /* Step 3: Heap malloc/umalloc of reduced shadow storing 1 byte per pixel (palette index), expanded on blit */
    buf = malloc(G3X_SHADOW_IDX_TOTAL_SIZE);
    if (buf == 0)
    {
        buf = umalloc(G3X_SHADOW_IDX_TOTAL_SIZE);
    }
    if (buf != 0)
    {
        *bm_ptr = (unsigned char *)buf;
        *op_ptr = (unsigned char *)buf;
        memset(buf, 0, G3X_SHADOW_IDX_TOTAL_SIZE);
        g3x_shadow2_mode = G3X_SHADOW_MODE_IDX;
        g3x_shadow2_bytes = (unsigned int)G3X_SHADOW_IDX_TOTAL_SIZE;
        g3x_shadow2_x0 = G3X_SHADOW_IDX_X0;
        g3x_shadow2_y0 = G3X_SHADOW_IDX_Y0;
        g3x_shadow2_w = G3X_SHADOW_IDX_WIDTH;
        g3x_shadow2_h = G3X_SHADOW_IDX_HEIGHT;
        *valid_ptr = 1;
        (void)g3x_shadow2_query_largest_free();
        return;
    }

    /* All fallback steps returned NULL: keep pointers NULL and retry on next ALT entry. */
    *bm_ptr = 0;
    *op_ptr = 0;
    *valid_ptr = 0;
    *attempted_ptr = 0;
    g3x_shadow2_mode = G3X_SHADOW_MODE_NONE;
    g3x_shadow2_bytes = 0u;
    g3x_shadow2_x0 = 0;
    g3x_shadow2_y0 = 0;
    g3x_shadow2_w = 0;
    g3x_shadow2_h = 0;
    (void)g3x_shadow2_query_largest_free();
#else
    void *buf = malloc(G3X_SHADOW_TOTAL_SIZE);
    if (buf == 0)
    {
        buf = umalloc(G3X_SHADOW_TOTAL_SIZE);
    }

    if (buf != 0)
    {
        *bm_ptr = (unsigned char *)buf;
        *op_ptr = (unsigned char *)buf + G3X_SHADOW_BM_SIZE;
        memset(buf, 0, G3X_SHADOW_TOTAL_SIZE);
        *valid_ptr = 1;
    }
    else
    {
        /* Allocation returned NULL: keep pointers NULL and allow retry on next ALT entry. */
        *bm_ptr = 0;
        *op_ptr = 0;
        *valid_ptr = 0;
        *attempted_ptr = 0;
    }
#endif
}

/* Engage adapted G5X check_gui_needs_redraw mechanism on ALT entry,
 * retry shadow allocation if still NULL, and cache GetMemInfo once on ALT entry. */
void g3x_diag_on_alt_enter(void)
{
#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
    g3x_shadow2_reset_overlay_bounds();
    int was_allocated = g3x_dbuf_shadow_is_allocated();
    g3x_dbuf_shadow_ensure_allocated();
    if (was_allocated)
    {
        (void)g3x_shadow2_query_largest_free();
    }
#else
    g3x_dbuf_shadow_ensure_allocated();
#endif
#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
    g3x_gui_sync_install_hook();
#endif
    g3x_diag_suppress_engaged = 1;
    g3x_diag_last_bitmap_buffer = active_bitmap_buffer;
}

/* Release suppression mechanism cleanly on ALT exit. */
void g3x_diag_on_alt_leave(void)
{
#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
    g3x_shadow2_reset_overlay_bounds();
#endif
    g3x_diag_suppress_engaged = 0;
    g3x_diag_last_bitmap_buffer = -1;
}

/* Adapted from chdk-port/platform/g5x/lib.c:206 (check_gui_needs_redraw)
 * and chdk-port/platform/g5x/platform_camera.h:85 (CAM_DETECT_BITMAP_UPDATE).
 * Active ONLY while ALT is engaged; reads active_bitmap_buffer (0x0000D2A4, FINSIG). */
int g3x_diag_check_suppress(void)
{
    if (!g3x_diag_suppress_engaged || camera_info.state.gui_mode_none)
        return 0;

    if (active_bitmap_buffer != g3x_diag_last_bitmap_buffer)
    {
        g3x_diag_last_bitmap_buffer = active_bitmap_buffer;
        g3x_diag_suppress_hit_count++;
        return 1;
    }
    return 0;
}

/* Restore overlay from shadow for the region it holds; anything outside or NULL shadow
 * falls back to gui_redraw(1) and increments F. */
int g3x_diag_restore_overlay(int trigger)
{
    if (camera_info.state.gui_mode_none)
        return 0;

    int sentinel_lost = !draw_test_guard();
    if (sentinel_lost)
    {
        g3x_diag_record_sentinel_loss();
    }

    if (!trigger && !sentinel_lost)
        return 0;

    g3x_diag_record_hook_hit();

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
    int ov_x0 = G3X_MENU_X0;
    int ov_y0 = G3X_MENU_Y0;
    int ov_x1 = G3X_MENU_X1;
    int ov_y1 = G3X_MENU_Y1;
    g3x_shadow2_get_overlay_rect(&ov_x0, &ov_y0, &ov_x1, &ov_y1);
    return g3x_shadow2_restore_rect(ov_x0, ov_y0, ov_x1, ov_y1);
#else
    if (g3x_dbuf_shadow_is_allocated())
    {
        /* Shadow is non-NULL: single fast blit ONLY; gui_redraw is unreachable. */
        (void)g3x_dbuf_shadow_restore();
        return 0;
    }

    /* Shadow is NULL: fall back to full gui_redraw and increment full-redraw counter. */
    g3x_diag_record_full_redraw();
    gui_redraw(1);
    return 1;
#endif
}

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
void g3x_diag_format_line(char *line)
{
    char shadow_tok[24];
#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
    if (g3x_dbuf_shadow_is_allocated() && g3x_shadow2_mode != G3X_SHADOW_MODE_NONE && g3x_shadow2_bytes > 0u)
    {
        sprintf(shadow_tok, "S:OK/%s",
                g3x_shadow2_mode_tag(g3x_shadow2_mode));
    }
    else
    {
        sprintf(shadow_tok, "S:NULL");
    }

    sprintf(line, "H:%u/%04u %s L:%04u R:%04u F:%04u M:%04u Y:%04u",
            g3x_diag_hook_installed ? 1u : 0u,
            g3x_diag_clamp9999(g3x_diag_hook_hits),
            shadow_tok,
            g3x_diag_clamp9999(g3x_diag_sentinel_loss_count),
            g3x_diag_clamp9999(g3x_diag_shadow_restore_count),
            g3x_diag_clamp9999(g3x_diag_full_redraw_count),
            g3x_diag_clamp9999(g3x_diag_suppress_hit_count),
            g3x_diag_clamp9999(g3x_diag_get_sync_hits()));
#else
    if (g3x_dbuf_shadow_is_allocated() && g3x_shadow2_mode != G3X_SHADOW_MODE_NONE && g3x_shadow2_bytes > 0u)
    {
        sprintf(shadow_tok, "S:OK/%u/%s",
                g3x_shadow2_bytes,
                g3x_shadow2_mode_tag(g3x_shadow2_mode));
    }
    else
    {
        sprintf(shadow_tok, "S:NULL");
    }

    char free_tok[16];
    if (g3x_shadow2_largest_free > 0)
    {
        unsigned int free_kb = ((unsigned int)g3x_shadow2_largest_free) >> 10;
        if (free_kb > 99999u)
            free_kb = 99999u;
        sprintf(free_tok, "%uK", free_kb);
    }
    else
    {
        sprintf(free_tok, "-");
    }

    sprintf(line, "H:%u/%04u %s %s L:%04u R:%04u F:%04u",
            g3x_diag_hook_installed ? 1u : 0u,
            g3x_diag_clamp9999(g3x_diag_hook_hits),
            shadow_tok,
            free_tok,
            g3x_diag_clamp9999(g3x_diag_sentinel_loss_count),
            g3x_diag_clamp9999(g3x_diag_shadow_restore_count),
            g3x_diag_clamp9999(g3x_diag_full_redraw_count));
#endif
}
#endif

/* Second ALT diagnostic line drawn with existing draw_string path
 * and 2x font (16x32) inside the 880x576 layout ([10, 889] x [12, 587]).
 */
void gui_diag_draw(void)
{
    if (!camera_info.state.gui_mode_alt)
        return;

#if defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)
    char line[64];
    g3x_diag_format_line(line);
    int y = camera_screen.height - 2 * FONT_HEIGHT;
    int len = (int)strlen(line);
    if (len > G3X_DIAG_LINE_MAX_CHARS)
        len = G3X_DIAG_LINE_MAX_CHARS;
    g3x_dbuf_fast_fill_rect(G3X_MENU_X0, y, G3X_MENU_X1, y + FONT_HEIGHT - 1, COLOR_BLACK);
    draw_string((camera_screen.width - len * FONT_WIDTH) / 2,
                y,
                line, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
#else
    int shadow_ok = g3x_dbuf_shadow_is_allocated();
    const char *shadow_tag = shadow_ok ? "OK" : "NULL";
    const char *shadow_pad = shadow_ok ? "  " : "";
    char line[G3X_DIAG_LINE_CHARS + 1];
    sprintf(line, "H:%u/%04u S:%s/%u%s L:%04u R:%04u F:%04u M:%04u",
            g3x_diag_hook_installed ? 1u : 0u,
            g3x_diag_clamp9999(g3x_diag_hook_hits),
            shadow_tag,
            (unsigned int)G3X_SHADOW_TOTAL_SIZE,
            shadow_pad,
            g3x_diag_clamp9999(g3x_diag_sentinel_loss_count),
            g3x_diag_clamp9999(g3x_diag_shadow_restore_count),
            g3x_diag_clamp9999(g3x_diag_full_redraw_count),
            g3x_diag_clamp9999(g3x_diag_suppress_hit_count));
    draw_string((camera_screen.width - G3X_DIAG_LINE_CHARS * FONT_WIDTH) / 2,
                camera_screen.height - 2 * FONT_HEIGHT,
                line, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
#endif
}

#endif /* G3X_GUI_DIAG_IMPLEMENTATION */
#endif /* G3X_GUI_DIAG == 1 */
#endif /* G3X_GUI_DIAG_H */
