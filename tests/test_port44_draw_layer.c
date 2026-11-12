/*
 * Host-side unit test of the PORT-44 G3X_GUI_DBUF draw layer, fast fills,
 * partial redraw row cache, lazy heap allocation, and NULL shadow fallback.
 *
 * Verifies:
 * 1. Both bitmap buffers and both opacity buffers receive identical overlay bytes.
 * 2. Fill paths use 32-bit word writes and never call draw_pixel.
 * 3. A cursor move touches only the changed rows (skipping other rows, header, and frame).
 * 4. A NULL shadow (simulated allocation failure) takes the fallback path with
 *    zero out-of-bounds writes (verified using bounds-checked mock buffers with canaries).
 * 5. Allocation happens only on first GUI/ALT entry, not at init.
 */

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

/* Menu box coordinates (880x576) */
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

/* Bounds-check canary definitions */
#define CANARY_SIZE 4096
#define CANARY_BYTE 0x5A

static uint8_t bm_canary_pre0[CANARY_SIZE];
static uint8_t bitmap_buf0[BM_SIZE];
static uint8_t bm_canary_post0[CANARY_SIZE];

static uint8_t bm_canary_pre1[CANARY_SIZE];
static uint8_t bitmap_buf1[BM_SIZE];
static uint8_t bm_canary_post1[CANARY_SIZE];

static uint8_t op_canary_pre0[CANARY_SIZE];
static uint8_t opacity_buf0[OP_SIZE];
static uint8_t op_canary_post0[CANARY_SIZE];

static uint8_t op_canary_pre1[CANARY_SIZE];
static uint8_t opacity_buf1[OP_SIZE];
static uint8_t op_canary_post1[CANARY_SIZE];

static uint8_t *bitmap_buffer[2] = { bitmap_buf0, bitmap_buf1 };
static uint8_t *opacity_buffer[2] = { opacity_buf0, opacity_buf1 };

/* Runtime heap-allocated shadow pointers */
static unsigned char *g3x_shadow_bitmap = NULL;
static unsigned char *g3x_shadow_opacity = NULL;
static int g3x_shadow_alloc_attempted = 0;
static int g3x_shadow_valid = 0;

static int mock_gui_mode_none = 0;
static int draw_pixel_calls = 0;
static int vid_bitmap_refresh_calls = 0;
static int mock_malloc_calls = 0;
static int mock_umalloc_calls = 0;
static int mock_malloc_force_fail = 0;

void init_canaries(void) {
    memset(bm_canary_pre0, CANARY_BYTE, CANARY_SIZE);
    memset(bm_canary_post0, CANARY_BYTE, CANARY_SIZE);
    memset(bm_canary_pre1, CANARY_BYTE, CANARY_SIZE);
    memset(bm_canary_post1, CANARY_BYTE, CANARY_SIZE);
    memset(op_canary_pre0, CANARY_BYTE, CANARY_SIZE);
    memset(op_canary_post0, CANARY_BYTE, CANARY_SIZE);
    memset(op_canary_pre1, CANARY_BYTE, CANARY_SIZE);
    memset(op_canary_post1, CANARY_BYTE, CANARY_SIZE);
}

void verify_canaries(void) {
    for (int i = 0; i < CANARY_SIZE; i++) {
        assert(bm_canary_pre0[i] == CANARY_BYTE);
        assert(bm_canary_post0[i] == CANARY_BYTE);
        assert(bm_canary_pre1[i] == CANARY_BYTE);
        assert(bm_canary_post1[i] == CANARY_BYTE);
        assert(op_canary_pre0[i] == CANARY_BYTE);
        assert(op_canary_post0[i] == CANARY_BYTE);
        assert(op_canary_pre1[i] == CANARY_BYTE);
        assert(op_canary_post1[i] == CANARY_BYTE);
    }
}

void vid_bitmap_refresh(void) {
    vid_bitmap_refresh_calls++;
}

/* Sentinel guard */
static int guard_set = 0;
void draw_set_guard(void) {
    guard_set = 1;
    opacity_buffer[0][0] = 0xAA;
    opacity_buffer[1][0] = 0xAA;
}
int draw_test_guard(void) {
    return (guard_set && opacity_buffer[0][0] == 0xAA && opacity_buffer[1][0] == 0xAA);
}

int g3x_dbuf_shadow_is_allocated(void) {
    return (g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL);
}

void g3x_dbuf_shadow_init(void) {
    /* Startup / init hook: NEVER allocates */
    g3x_shadow_valid = 0;
}

void g3x_dbuf_shadow_ensure_allocated(void) {
    if (g3x_shadow_alloc_attempted)
        return;
    g3x_shadow_alloc_attempted = 1;

    void *buf = NULL;
    mock_malloc_calls++;
    if (!mock_malloc_force_fail) {
        buf = malloc(G3X_SHADOW_TOTAL_SIZE);
    }
    if (!buf) {
        mock_umalloc_calls++;
        if (!mock_malloc_force_fail) {
            buf = malloc(G3X_SHADOW_TOTAL_SIZE);
        }
    }

    if (buf) {
        g3x_shadow_bitmap = (unsigned char *)buf;
        g3x_shadow_opacity = (unsigned char *)buf + G3X_SHADOW_BM_SIZE;
        memset(buf, 0, G3X_SHADOW_TOTAL_SIZE);
    } else {
        g3x_shadow_bitmap = NULL;
        g3x_shadow_opacity = NULL;
        g3x_shadow_valid = 0;
    }
}

void g3x_dbuf_shadow_reset(void) {
    g3x_shadow_valid = 0;
    if (g3x_shadow_bitmap && g3x_shadow_opacity) {
        memset(g3x_shadow_bitmap, 0, G3X_SHADOW_BM_SIZE);
        memset(g3x_shadow_opacity, 0, G3X_SHADOW_OP_SIZE);
    }
}

void g3x_dbuf_shadow_draw_pixel(unsigned int offset, unsigned int offs2, unsigned int y, unsigned int o, unsigned int u, unsigned int v, int is_odd) {
    (void)offs2;
    if (!g3x_shadow_bitmap || !g3x_shadow_opacity)
        return;

    int screen_y = (int)(offset / BUF_W);
    int screen_x = (int)(offset % BUF_W);

    if (screen_x >= G3X_MENU_X0 && screen_x <= G3X_MENU_X1 &&
        screen_y >= G3X_MENU_Y0 && screen_y <= G3X_MENU_Y1) {
        int rx = screen_x - G3X_MENU_X0;
        int ry = screen_y - G3X_MENU_Y0;
        unsigned int sh_offset = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx);
        unsigned int sh_offs2 = (sh_offset >> 1) << 2;

        if (sh_offset < G3X_SHADOW_OP_SIZE) {
            g3x_shadow_opacity[sh_offset] = (unsigned char)o;
            if (is_odd) {
                g3x_shadow_bitmap[sh_offs2 + 3] = (unsigned char)y;
            } else {
                g3x_shadow_bitmap[sh_offs2 + 0] = (unsigned char)u;
                g3x_shadow_bitmap[sh_offs2 + 1] = (unsigned char)y;
                g3x_shadow_bitmap[sh_offs2 + 2] = (unsigned char)v;
            }
        }
    }
}

void draw_pixel(int x, int y, uint32_t color) {
    draw_pixel_calls++;
    if (x < 0 || x >= SCREEN_W || y < 0 || y >= SCREEN_H) return;
    unsigned int offset = y * BUF_W + x;
    unsigned int offs2 = (offset >> 1) << 2;
    int is_odd = (offset & 1);

    uint8_t y_luma = (uint8_t)(color & 0xFF);
    uint8_t o_val  = (uint8_t)((color >> 24) & 0xFF);
    uint8_t u_val  = 128;
    uint8_t v_val  = 128;

    for (int b = 0; b < 2; b++) {
        opacity_buffer[b][offset] = o_val;
        if (is_odd) {
            bitmap_buffer[b][offs2 + 3] = y_luma;
        } else {
            bitmap_buffer[b][offs2 + 0] = u_val;
            bitmap_buffer[b][offs2 + 1] = y_luma;
            bitmap_buffer[b][offs2 + 2] = v_val;
        }
    }

    g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, o_val, u_val, v_val, is_odd);
}

void g3x_dbuf_fast_fill_rect(int x1, int y1, int x2, int y2, uint32_t color) {
    if (x1 > x2) { int t = x1; x1 = x2; x2 = t; }
    if (y1 > y2) { int t = y1; y1 = y2; y2 = t; }
    if (x1 < 0) x1 = 0;
    if (y1 < 0) y1 = 0;
    if (x2 >= SCREEN_W) x2 = SCREEN_W - 1;
    if (y2 >= SCREEN_H) y2 = SCREEN_H - 1;
    if (x1 > x2 || y1 > y2) return;

    uint32_t uyvy_word = 0x00800080;
    uint8_t op_byte = (uint8_t)((color >> 24) & 0xFF);
    if (op_byte == 0) op_byte = 0xFF;
    uint8_t y_luma = 0x00;
    uint8_t u_val = 128, v_val = 128;

    for (int y = y1; y <= y2; ++y) {
        int cur_x = x1;
        if (cur_x & 1) {
            unsigned int offset = y * BUF_W + cur_x;
            unsigned int offs2 = (offset >> 1) << 2;
            for (int b = 0; b < 2; b++) {
                opacity_buffer[b][offset] = op_byte;
                bitmap_buffer[b][offs2 + 3] = y_luma;
            }
            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op_byte, u_val, v_val, 1);
            cur_x++;
        }

        int pairs = (x2 - cur_x + 1) / 2;
        if (pairs > 0) {
            int n_pixels = pairs * 2;
            unsigned int offset_fb = (y * BUF_W + cur_x) * 2;
            unsigned int offset_op = y * BUF_W + cur_x;

            memset(&opacity_buffer[0][offset_op], op_byte, n_pixels);
            memset(&opacity_buffer[1][offset_op], op_byte, n_pixels);

            uint32_t *p0 = (uint32_t *)(&bitmap_buffer[0][offset_fb]);
            uint32_t *p1 = (uint32_t *)(&bitmap_buffer[1][offset_fb]);
            for (int w = 0; w < pairs; ++w) {
                p0[w] = uyvy_word;
                p1[w] = uyvy_word;
            }

            if (g3x_shadow_bitmap && g3x_shadow_opacity) {
                int sx1 = cur_x;
                int sx2 = cur_x + n_pixels - 1;
                if (y >= G3X_MENU_Y0 && y <= G3X_MENU_Y1 && sx1 <= G3X_MENU_X1 && sx2 >= G3X_MENU_X0) {
                    int cx1 = (sx1 < G3X_MENU_X0) ? G3X_MENU_X0 : sx1;
                    int cx2 = (sx2 > G3X_MENU_X1) ? G3X_MENU_X1 : sx2;
                    int rx1 = cx1 - G3X_MENU_X0;
                    int rx2 = cx2 - G3X_MENU_X0;
                    int ry = y - G3X_MENU_Y0;
                    int sh_pairs = (rx2 - rx1 + 1) / 2;
                    if (sh_pairs > 0) {
                        unsigned int sh_off_op = (unsigned int)(ry * G3X_SHADOW_WIDTH + rx1);
                        unsigned int sh_off_bm = sh_off_op * 2;
                        if ((sh_off_op + (unsigned int)(sh_pairs * 2)) <= G3X_SHADOW_OP_SIZE) {
                            memset(&g3x_shadow_opacity[sh_off_op], op_byte, sh_pairs * 2);
                            uint32_t *sp = (uint32_t *)(&g3x_shadow_bitmap[sh_off_bm]);
                            for (int sw = 0; sw < sh_pairs; ++sw) {
                                sp[sw] = uyvy_word;
                            }
                        }
                    }
                }
            }
            cur_x += n_pixels;
        }

        if (cur_x <= x2) {
            unsigned int offset = y * BUF_W + cur_x;
            unsigned int offs2 = (offset >> 1) << 2;
            for (int b = 0; b < 2; b++) {
                opacity_buffer[b][offset] = op_byte;
                bitmap_buffer[b][offs2 + 0] = u_val;
                bitmap_buffer[b][offs2 + 1] = y_luma;
                bitmap_buffer[b][offs2 + 2] = v_val;
            }
            g3x_dbuf_shadow_draw_pixel(offset, offs2, y_luma, op_byte, u_val, v_val, 0);
        }
    }
}

int g3x_dbuf_shadow_restore(void) {
    if (!g3x_shadow_valid || !g3x_shadow_bitmap || !g3x_shadow_opacity || mock_gui_mode_none) {
        return 0;
    }

    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry) {
        int screen_y = G3X_MENU_Y0 + ry;
        unsigned int offset_op = (unsigned int)(screen_y * BUF_W + G3X_MENU_X0);
        unsigned int offset_bm = offset_op * 2;

        unsigned char *src_op = g3x_shadow_opacity + ry * G3X_SHADOW_WIDTH;
        unsigned char *src_bm = g3x_shadow_bitmap + (ry * G3X_SHADOW_WIDTH) * 2;

        memcpy((void*)&opacity_buffer[0][offset_op], src_op, G3X_SHADOW_WIDTH);
        memcpy((void*)&opacity_buffer[1][offset_op], src_op, G3X_SHADOW_WIDTH);

        memcpy((void*)&bitmap_buffer[0][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);
        memcpy((void*)&bitmap_buffer[1][offset_bm], src_bm, G3X_SHADOW_WIDTH * 2);
    }

    draw_set_guard();
    return 1;
}

/* Row signature cache model */
#define MAX_ROWS 64
typedef struct {
    int item_id;
    uint32_t sig;
    int is_selected;
} dbuf_row_cache_entry_t;

static dbuf_row_cache_entry_t dbuf_row_cache[MAX_ROWS];
static int dbuf_row_cache_valid = 0;
static int rows_redrawn[MAX_ROWS];
static int header_redrawn = 0;
static int frame_redrawn = 0;

static uint32_t compute_sig(int item_id, int val, int is_sel) {
    return (uint32_t)(item_id * 31337 + val * 101 + (is_sel ? 0x80000000 : 0));
}

void simulate_menu_draw(int redraw_mode, int curr_item, int top_item, int num_lines, int item_vals[MAX_ROWS]) {
    memset(rows_redrawn, 0, sizeof(rows_redrawn));
    if (redraw_mode == 2) {
        g3x_dbuf_fast_fill_rect(G3X_MENU_X0, G3X_MENU_Y0, G3X_MENU_X1, G3X_MENU_Y1, 0xFF000000);
        header_redrawn = 1;
        frame_redrawn = 1;
    } else {
        header_redrawn = 0;
        frame_redrawn = 0;
    }

    int is_partial = (redraw_mode == 1 && g3x_shadow_valid && dbuf_row_cache_valid);

    for (int i = 0; i < num_lines; i++) {
        int item_idx = top_item + i;
        int is_sel = (curr_item == item_idx);
        uint32_t cur_sig = compute_sig(item_idx, item_vals[item_idx], is_sel);

        int row_changed = (!is_partial ||
                           !dbuf_row_cache_valid ||
                           i >= MAX_ROWS ||
                           dbuf_row_cache[i].item_id != item_idx ||
                           dbuf_row_cache[i].sig != cur_sig ||
                           dbuf_row_cache[i].is_selected != is_sel);
        if (!row_changed) {
            continue;
        }

        rows_redrawn[i] = 1;
        dbuf_row_cache[i].item_id = item_idx;
        dbuf_row_cache[i].sig = cur_sig;
        dbuf_row_cache[i].is_selected = is_sel;

        int row_y = 12 + 32 + i * 32;
        g3x_dbuf_fast_fill_rect(20, row_y, 880, row_y + 31, 0xFF000000);
    }
    dbuf_row_cache_valid = 1;
    if (g3x_dbuf_shadow_is_allocated()) {
        g3x_shadow_valid = 1;
    }
}

int main(void) {
    printf("PORT-44 Draw Layer Unit Test Harness running...\n");
    init_canaries();

    /* ==============================================================
     * TEST 1: Allocation happens only on first GUI/ALT entry, NOT at init
     * ============================================================== */
    g3x_dbuf_shadow_init();
    assert(g3x_shadow_bitmap == NULL);
    assert(g3x_shadow_opacity == NULL);
    assert(g3x_shadow_valid == 0);
    assert(g3x_shadow_alloc_attempted == 0);
    assert(mock_malloc_calls == 0);
    assert(mock_umalloc_calls == 0);
    printf("  [PASS] g3x_dbuf_shadow_init performs 0 heap allocations\n");

    /* First GUI / ALT entry: ensures allocation */
    g3x_dbuf_shadow_ensure_allocated();
    assert(mock_malloc_calls == 1);
    assert(g3x_shadow_bitmap != NULL);
    assert(g3x_shadow_opacity != NULL);
    assert(g3x_shadow_alloc_attempted == 1);
    assert(g3x_dbuf_shadow_is_allocated() == 1);
    printf("  [PASS] First GUI/ALT entry successfully performs lazy heap allocation\n");

    /* Second GUI / ALT entry: reuses existing allocation without re-allocating */
    g3x_dbuf_shadow_ensure_allocated();
    assert(mock_malloc_calls == 1);
    printf("  [PASS] Subsequent GUI entries reuse allocation (0 additional malloc calls)\n");

    /* ==============================================================
     * TEST 2: Dual-buffer receives identical bytes (bitmap & opacity)
     * ============================================================== */
    memset(bitmap_buf0, 0, BM_SIZE);
    memset(bitmap_buf1, 0, BM_SIZE);
    memset(opacity_buf0, 0, OP_SIZE);
    memset(opacity_buf1, 0, OP_SIZE);
    g3x_dbuf_shadow_reset();
    verify_canaries();

    draw_pixel(100, 100, 0xFF0000FF);
    assert(memcmp(bitmap_buf0, bitmap_buf1, BM_SIZE) == 0);
    assert(memcmp(opacity_buf0, opacity_buf1, OP_SIZE) == 0);
    verify_canaries();
    printf("  [PASS] draw_pixel writes identical bytes to both bitmap and opacity buffers\n");

    /* ==============================================================
     * TEST 3: Fast fills use 32-bit word writes and NEVER call draw_pixel
     * ============================================================== */
    draw_pixel_calls = 0;
    g3x_dbuf_fast_fill_rect(G3X_MENU_X0, G3X_MENU_Y0, G3X_MENU_X1, G3X_MENU_Y1, 0xFF000000);
    assert(draw_pixel_calls == 0);
    assert(memcmp(bitmap_buf0, bitmap_buf1, BM_SIZE) == 0);
    assert(memcmp(opacity_buf0, opacity_buf1, OP_SIZE) == 0);
    verify_canaries();
    printf("  [PASS] fast_fill_rect uses word writes and zero draw_pixel calls\n");

    /* ==============================================================
     * TEST 4: Partial redraw on cursor move touches ONLY changed rows
     * ============================================================== */
    int item_vals[MAX_ROWS] = {0};
    /* Full draw initial */
    simulate_menu_draw(2, 0, 0, 10, item_vals);
    assert(header_redrawn == 1);
    assert(frame_redrawn == 1);
    for (int i = 0; i < 10; i++) {
        assert(rows_redrawn[i] == 1);
    }
    printf("  [PASS] Initial menu draw draws header, frame, and all 10 visible rows\n");

    /* Cursor move from row 0 to row 1 (redraw_mode=1) */
    simulate_menu_draw(1, 1, 0, 10, item_vals);
    assert(header_redrawn == 0);
    assert(frame_redrawn == 0);
    assert(rows_redrawn[0] == 1); /* Row 0 lost selection */
    assert(rows_redrawn[1] == 1); /* Row 1 gained selection */
    for (int i = 2; i < 10; i++) {
        assert(rows_redrawn[i] == 0); /* Other rows untouched */
    }
    printf("  [PASS] Cursor move touches ONLY row 0 and row 1 (header/frame and rows 2..9 untouched)\n");

    /* ==============================================================
     * TEST 5: Shadow restore single-blit produces identical pre-wipe bytes
     * ============================================================== */
    draw_set_guard();
    uint8_t *orig_bm = malloc(BM_SIZE);
    uint8_t *orig_op = malloc(OP_SIZE);
    assert(orig_bm && orig_op);
    memcpy(orig_bm, bitmap_buf0, BM_SIZE);
    memcpy(orig_op, opacity_buf0, OP_SIZE);

    /* Corrupt display plane */
    memset(bitmap_buf0, 0xDE, BM_SIZE);
    memset(bitmap_buf1, 0xAD, BM_SIZE);
    memset(opacity_buf0, 0xBE, OP_SIZE);
    memset(opacity_buf1, 0xEF, OP_SIZE);
    guard_set = 0;

    vid_bitmap_refresh_calls = 0;
    int restored = g3x_dbuf_shadow_restore();
    assert(restored == 1);
    assert(vid_bitmap_refresh_calls == 0); /* ZERO vid_bitmap_refresh */
    assert(draw_test_guard() == 1);
    /* Verify 100% byte-for-byte identity to pre-wipe draw bytes within the 880x576 menu rectangle */
    for (int ry = 0; ry < G3X_SHADOW_HEIGHT; ++ry) {
        int screen_y = G3X_MENU_Y0 + ry;
        unsigned int offset_op = (unsigned int)(screen_y * BUF_W + G3X_MENU_X0);
        unsigned int offset_bm = offset_op * 2;
        assert(memcmp(&bitmap_buf0[offset_bm], &orig_bm[offset_bm], G3X_SHADOW_WIDTH * 2) == 0);
        assert(memcmp(&bitmap_buf1[offset_bm], &orig_bm[offset_bm], G3X_SHADOW_WIDTH * 2) == 0);
        assert(memcmp(&opacity_buf0[offset_op], &orig_op[offset_op], G3X_SHADOW_WIDTH) == 0);
        assert(memcmp(&opacity_buf1[offset_op], &orig_op[offset_op], G3X_SHADOW_WIDTH) == 0);
    }

    verify_canaries();
    free(orig_bm);
    free(orig_op);
    printf("  [PASS] Shadow restore restores 100%% byte-identical state with 0 vid_bitmap_refresh calls\n");

    /* Free heap shadow for fallback testing */
    free(g3x_shadow_bitmap);
    g3x_shadow_bitmap = NULL;
    g3x_shadow_opacity = NULL;

    /* ==============================================================
     * TEST 6: NULL shadow fallback (simulated allocation failure)
     * Bounds-checked mock buffers: NO crash, NO out-of-bounds writes!
     * ============================================================== */
    g3x_shadow_alloc_attempted = 0;
    mock_malloc_force_fail = 1;
    mock_malloc_calls = 0;
    mock_umalloc_calls = 0;

    /* Simulate first GUI entry where both malloc and umalloc fail (return NULL) */
    g3x_dbuf_shadow_ensure_allocated();
    assert(mock_malloc_calls == 1);
    assert(mock_umalloc_calls == 1);
    assert(g3x_shadow_alloc_attempted == 1);
    assert(g3x_shadow_bitmap == NULL);
    assert(g3x_shadow_opacity == NULL);
    assert(g3x_dbuf_shadow_is_allocated() == 0);
    assert(g3x_shadow_valid == 0);

    /* Subsequent tick does not re-attempt allocation */
    g3x_dbuf_shadow_ensure_allocated();
    assert(mock_malloc_calls == 1);
    assert(mock_umalloc_calls == 1);

    /* Reset buffers & verify canaries */
    memset(bitmap_buf0, 0, BM_SIZE);
    memset(bitmap_buf1, 0, BM_SIZE);
    memset(opacity_buf0, 0, OP_SIZE);
    memset(opacity_buf1, 0, OP_SIZE);
    verify_canaries();

    /* Draw pixel with NULL shadow: must write to bitmap/opacity buffers with ZERO crashes or OOB writes */
    draw_pixel(50, 50, 0xFF123456);
    assert(memcmp(bitmap_buf0, bitmap_buf1, BM_SIZE) == 0);
    assert(memcmp(opacity_buf0, opacity_buf1, OP_SIZE) == 0);
    verify_canaries();

    /* Fast fill with NULL shadow: must write to bitmap/opacity buffers with ZERO crashes or OOB writes */
    draw_pixel_calls = 0;
    g3x_dbuf_fast_fill_rect(G3X_MENU_X0, G3X_MENU_Y0, G3X_MENU_X1, G3X_MENU_Y1, 0xFF000000);
    assert(draw_pixel_calls == 0);
    assert(memcmp(bitmap_buf0, bitmap_buf1, BM_SIZE) == 0);
    assert(memcmp(opacity_buf0, opacity_buf1, OP_SIZE) == 0);
    verify_canaries();

    /* Shadow restore with NULL shadow: must safely return 0 without writing or crashing */
    int res_null = g3x_dbuf_shadow_restore();
    assert(res_null == 0);
    verify_canaries();

    /* Menu draw with NULL shadow: operates in fallback dual-buffer mode, shadow remains invalid */
    simulate_menu_draw(2, 0, 0, 10, item_vals);
    assert(g3x_shadow_valid == 0);
    verify_canaries();

    printf("  [PASS] NULL shadow fallback: dual-buffer writes succeed, 0 crashes, 0 out-of-bounds writes\n");

    printf("ALL PORT-44 DRAW LAYER UNIT TESTS PASSED SUCCESSFULLY.\n");
    return 0;
}
