/* PORT-47: Opt-in G3X_GUI_DIAG=1 overdraw/restore counters, shadow-blit-only restore,
 * and adapted G5X check_gui_needs_redraw sibling suppression mechanism.
 *
 * Layered on: G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1
 *
 * Sibling & FINSIG citations:
 * - chdk-port/platform/g5x/lib.c:206 (check_gui_needs_redraw)
 * - chdk-port/platform/g5x/platform_camera.h:85 (CAM_DETECT_BITMAP_UPDATE)
 * - chdk-port/core/main.c:316 (caller)
 * - reference/finsig_gm110c/stubs_entry.S:186 (active_bitmap_buffer = 0x0000D2A4)
 * - reference/finsig_gm110c/stubs_entry.S:188 (bitmap_buffer = 0x0000D2A8)
 * - reference/finsig_gm110c/stubs_entry.S:197 (AllocateUncacheableMemory = 0xFC144471)
 */
#ifndef G3X_GUI_DIAG_H
#define G3X_GUI_DIAG_H

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

#define G3X_DIAG_LINE_CHARS   51

extern unsigned int g3x_diag_hook_installed;
extern unsigned int g3x_diag_hook_hits;
extern unsigned int g3x_diag_sentinel_loss_count;
extern unsigned int g3x_diag_shadow_restore_count;
extern unsigned int g3x_diag_full_redraw_count;
extern unsigned int g3x_diag_suppress_hit_count;
extern int g3x_diag_suppress_engaged;
extern int g3x_diag_last_bitmap_buffer;

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

/* Requirement (b): Allocate the shadow reliably. Check the allocation result;
 * if it is NULL, retry on each ALT entry. Allocate nothing at boot. */
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
}

/* Requirement (d): Engage adapted G5X check_gui_needs_redraw mechanism on ALT entry,
 * and retry shadow allocation if still NULL. */
void g3x_diag_on_alt_enter(void)
{
    g3x_dbuf_shadow_ensure_allocated();
    g3x_diag_suppress_engaged = 1;
    g3x_diag_last_bitmap_buffer = active_bitmap_buffer;
}

/* Requirement (d): Release suppression mechanism cleanly on ALT exit. */
void g3x_diag_on_alt_leave(void)
{
    g3x_diag_suppress_engaged = 0;
    g3x_diag_last_bitmap_buffer = -1;
}

/* Requirement (d): Adapted from chdk-port/platform/g5x/lib.c:206 (check_gui_needs_redraw)
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

/* Requirement (c): While the shadow exists (non-NULL), restore ONLY by the single fast blit
 * (g3x_dbuf_shadow_restore) and never fall back to banded gui_redraw.
 * Full redraw (gui_redraw) is reachable ONLY when the shadow is NULL, and each one increments
 * the full-redraw counter. */
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
}

/* Requirement (a): Second ALT diagnostic line drawn with existing draw_string path
 * and 2x font (16x32) inside the 880x576 layout ([10, 889] x [12, 587]).
 * Shows:
 *   H:<0/1>/<hook_hits> S:<NULL/OK>/<size_bytes> L:<sentinel_loss> R:<shadow_restore> F:<full_redraw> M:<suppress_hits>
 */
void gui_diag_draw(void)
{
    if (!camera_info.state.gui_mode_alt)
        return;

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
}

#endif /* G3X_GUI_DIAG_IMPLEMENTATION */
#endif /* G3X_GUI_DIAG == 1 */
#endif /* G3X_GUI_DIAG_H */
