/* PORT-49: Opt-in G3X_GUI_SYNC=1 synchronous overlay restore hook.
 *
 * Layered on: G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
 *
 * Chosen hook method and address from docs/PORT49_GUI_SYNC.md answer (c):
 * - Hook pointer: *(volatile unsigned int *)0x0000E26C
 *   [ROM_VERIFIED: docs/PORT49_GUI_SYNC.md answer (c); manifests/port49_gui_sync_evidence.json
 *    ROM 0xFC143480..0xFC14353F literal pool at 0xFC1434A8 = 0x0000E26C; setter at 0xFC143481
 *    has 0 callers in ROM; ROM data copy initial value at 0xFCE972C4 is 0x00000000].
 * - Dispatcher: GraphicSystemCoreFinish_helper at 0xFC143493
 *   [FINSIG: reference/finsig_gm110c/funcs_by_name.csv:935; ROM_VERIFIED:
 *    0xFC143492 push {r4, lr} (8 B), 0xFC143494 bl 0xFC20C5BE (GraphicSystemCoreFinish),
 *    0xFC14349A ldr r0, [pc, #12] (0x0000E26C), 0xFC14349C ldr r0, [r0],
 *    0xFC14349E cbz r0, 0xFC1434A2, 0xFC1434A0 blx r0, 0xFC1434A2 pop {r4, pc}].
 * - Caller: transfer_src_overlay at 0xFC380635
 *   [FINSIG: reference/finsig_gm110c/stubs_entry.S:352; ROM_VERIFIED:
 *    0xFC380634 push.w {r4-r9, lr} (28 B), 0xFC380638 sub sp, #60 (60 B),
 *    0xFC38063A mov r9, r0 (saves target buffer index 0 or 1 in r9),
 *    0xFC380670 bl 0xFC143492 (return lr = 0xFC380675 at sp_entry[1] / [sp_entry, #4]),
 *    0xFC3806F2 bl 0xFC183A12 (MakeOsdVram hardware Ximr/T2D DMA composition),
 *    0xFC3806F6 add sp, #60, 0xFC3806F8 pop.w {r4-r9, pc}].
 * - Post-transfer return interception:
 *   [INFERRED runtime behaviour: docs/PORT49_GUI_SYNC.md answers (a), (b), (c);
 *    manifests/port49_gui_sync_evidence.json ROM 0xFC380634..0xFC380A33]:
 *   When g3x_gui_sync_pre_cb is entered via blx r0 at 0xFC1434A0 with
 *   sp_entry[1] ([sp_entry, #4]) == 0xFC380675, transfer_src_overlay's saved
 *   return lr sits at sp_entry[23] ([sp_entry, #92], offset 8 + 60 + 6*4 = 92)
 *   and r9 holds the live target buffer index (0 or 1). Patching sp_entry[23]
 *   to g3x_gui_sync_post_trampoline | 1 causes transfer_src_overlay's
 *   pop.w {r4-r9, pc} epilogue at 0xFC3806F8 to run a bounded fast blit from
 *   the PORT-48 shadow into bitmap_buffer[r9 & 1] and opacity_buffer[r9 & 1]
 *   after MakeOsdVram (0xFC3806F2) finishes overwriting the inactive buffer
 *   and before VTM_FlipAndCommit (0xFC38090B at 0xFC380A1C) writes
 *   active_bitmap_buffer (0x0000D2A4 at 0xFC38091E) and calls disp_commit
 *   (0xFC183690 at 0xFC38093E).
 */
#ifndef G3X_GUI_SYNC_H
#define G3X_GUI_SYNC_H

#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
#if !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1) || \
    !defined(G3X_GUI_SHADOW2) || (G3X_GUI_SHADOW2 != 1)
#error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
#endif

/* ROM_VERIFIED: RAM callback pointer read by GraphicSystemCoreFinish_helper
 * (0xFC143493) via literal pool at 0xFC1434A8 (docs/PORT49_GUI_SYNC.md (c);
 * manifests/port49_gui_sync_evidence.json). */
#define G3X_GUI_SYNC_CALLBACK_PTR_ADDR   0x0000e26cu
#define G3X_GUI_SYNC_HELPER_ADDR         0xfc143493u
#define G3X_GUI_SYNC_SETTER_ADDR         0xfc143481u

/* FINSIG + ROM_VERIFIED: transfer_src_overlay (0xFC380635) and VTM flip chain
 * addresses (docs/PORT49_GUI_SYNC.md (a), (b), (c);
 * reference/finsig_gm110c/stubs_entry.S:28-30,352). */
#define G3X_GUI_SYNC_TRANSFER_ADDR       0xfc380635u
#define G3X_GUI_SYNC_CALLER_LR           0xfc380675u
#define G3X_GUI_SYNC_VTM_CALLER_LR       0xfc3809dfu
#define G3X_GUI_SYNC_MAKE_OSD_CALL_ADDR  0xfc3806f2u
#define G3X_GUI_SYNC_FLIP_COMMIT_ADDR    0xfc38090bu
#define G3X_GUI_SYNC_ACTIVE_BM_ADDR      0x0000d2a4u

/* ROM_VERIFIED stack displacements + INFERRED runtime frame invariance
 * (docs/PORT49_GUI_SYNC.md answer (c); manifests/port49_gui_sync_evidence.json
 * ROM 0xFC143492..0xFC1434A3 and ROM 0xFC380634..0xFC3806FB):
 * - sp_entry[1]  ([sp_entry, #4])  = GraphicSystemCoreFinish_helper saved lr
 * - sp_entry[23] ([sp_entry, #92]) = transfer_src_overlay saved lr (8 + 60 + 6*4 = 92) */
#define G3X_GUI_SYNC_HELPER_LR_WORD_IDX  1u
#define G3X_GUI_SYNC_HELPER_LR_BYTE_OFF  4u
#define G3X_GUI_SYNC_RET_LR_WORD_IDX     23u
#define G3X_GUI_SYNC_RET_LR_BYTE_OFF     92u

extern volatile unsigned int g3x_diag_sync_hits;
extern volatile unsigned int g3x_gui_sync_saved_lr;
extern volatile unsigned int g3x_gui_sync_target_buf;
extern volatile unsigned int g3x_gui_sync_in_flight;

extern char *bitmap_buffer[];
extern volatile char *opacity_buffer[];

void g3x_gui_sync_install_hook(void);
int g3x_gui_sync_is_hook_installed(void);
void g3x_gui_sync_pre_cb(void);
void g3x_gui_sync_post_trampoline(void);
unsigned int g3x_gui_sync_post_c(void);
int g3x_gui_sync_pre_frame_check(unsigned int *sp_entry, unsigned int r9_val);
void g3x_diag_record_sync_hit(void);
unsigned int g3x_diag_get_sync_hits(void);
int g3x_shadow2_blit_restore_target(unsigned char *bm, unsigned char *op,
                                    int buf_w, unsigned int target_idx);
void g3x_sync_set_guard_target(unsigned int target_idx);
int g3x_dbuf_shadow_sync_restore(unsigned int target_idx);

#endif /* G3X_GUI_SYNC == 1 */
#endif /* G3X_GUI_SYNC_H */

#if defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)
#if defined(G3X_GUI_DIAG_IMPLEMENTATION) && (G3X_GUI_DIAG_IMPLEMENTATION == 1)
#ifndef G3X_GUI_SYNC_IMPL_H
#define G3X_GUI_SYNC_IMPL_H

#if defined(__arm__) || defined(__thumb__)
#define G3X_GUI_SYNC_HOOK_PTR() (*(volatile unsigned int *)G3X_GUI_SYNC_CALLBACK_PTR_ADDR)
#else
static volatile unsigned int g3x_host_sync_callback_ptr = 0u;
#define G3X_GUI_SYNC_HOOK_PTR() (g3x_host_sync_callback_ptr)
#endif

volatile unsigned int g3x_diag_sync_hits = 0u;
volatile unsigned int g3x_gui_sync_saved_lr = 0u;
volatile unsigned int g3x_gui_sync_target_buf = 0u;
volatile unsigned int g3x_gui_sync_in_flight = 0u;

void g3x_diag_record_sync_hit(void)
{
    g3x_diag_sync_hits++;
}

unsigned int g3x_diag_get_sync_hits(void)
{
    return g3x_diag_sync_hits;
}

/* INFERRED runtime hook installation (docs/PORT49_GUI_SYNC.md answer (c);
 * manifests/port49_gui_sync_evidence.json): writes the Thumb entry address of
 * g3x_gui_sync_pre_cb to *(volatile unsigned int *)0x0000E26C so
 * GraphicSystemCoreFinish_helper (0xFC143493) dispatches to g3x_gui_sync_pre_cb
 * at 0xFC1434A0. */
void g3x_gui_sync_install_hook(void)
{
    unsigned int cb_addr = ((unsigned int)(unsigned long)&g3x_gui_sync_pre_cb) | 1u;
    G3X_GUI_SYNC_HOOK_PTR() = cb_addr;
    g3x_diag_set_hook_installed(1);
}

int g3x_gui_sync_is_hook_installed(void)
{
    unsigned int cb_addr = ((unsigned int)(unsigned long)&g3x_gui_sync_pre_cb) | 1u;
    return (G3X_GUI_SYNC_HOOK_PTR() == cb_addr) ? 1 : 0;
}

/* INFERRED stack-frame return-address interception (docs/PORT49_GUI_SYNC.md
 * answer (c); manifests/port49_gui_sync_evidence.json):
 * Verifies GraphicSystemCoreFinish_helper's saved lr at sp_entry[1] ([sp, #4])
 * is 0xFC380675 (the call inside transfer_src_overlay at 0xFC380670, not the
 * call inside VTMUnLock_flush at 0xFC3809DA with lr = 0xFC3809DF), captures
 * live r9 (next_buf index 0 or 1), saves transfer_src_overlay's return lr at
 * sp_entry[23] ([sp, #92]), and replaces sp_entry[23] with
 * g3x_gui_sync_post_trampoline | 1. */
int g3x_gui_sync_pre_frame_check(unsigned int *sp_entry, unsigned int r9_val)
{
    if (!sp_entry)
        return 0;
    if (sp_entry[G3X_GUI_SYNC_HELPER_LR_WORD_IDX] != G3X_GUI_SYNC_CALLER_LR)
        return 0;
    if (g3x_gui_sync_in_flight != 0u)
        return 0;
    unsigned int orig_lr = sp_entry[G3X_GUI_SYNC_RET_LR_WORD_IDX];
    unsigned int tramp_addr = ((unsigned int)(unsigned long)&g3x_gui_sync_post_trampoline) | 1u;
    if (orig_lr == tramp_addr)
        return 0;
    g3x_gui_sync_in_flight = 1u;
    g3x_gui_sync_saved_lr = orig_lr;
    g3x_gui_sync_target_buf = r9_val & 1u;
    sp_entry[G3X_GUI_SYNC_RET_LR_WORD_IDX] = tramp_addr;
    return 1;
}

/* Restore PORT-45/PORT-48 opacity sentinel guards on the single target buffer
 * that was just blitted synchronously, leaving the other buffer's sentinels
 * untouched so the 20 ms poll loop remains an accurate fallback for both buffers. */
void g3x_sync_set_guard_target(unsigned int target_idx)
{
    unsigned int idx = target_idx & 1u;
    if (!opacity_buffer[idx])
        return;
    opacity_buffer[idx][0] = 0x42;
    if (!camera_info.state.gui_mode_none && g3x_dbuf_shadow_is_allocated())
    {
        int buf_w = camera_screen.buffer_width ? camera_screen.buffer_width : G3X_SHADOW_FULL_WIDTH;
        opacity_buffer[idx][10 * buf_w + 8] = 0x42;
        opacity_buffer[idx][10 * buf_w + 891] = 0x42;
        opacity_buffer[idx][589 * buf_w + 8] = 0x42;
        opacity_buffer[idx][589 * buf_w + 891] = 0x42;
    }
}

/* Bounded fast shadow blit into ONLY the buffer about to be shown (target_idx & 1).
 * No allocation, no blocking calls, no new tasks. Supports all 3 PORT-48 shadow
 * tiers (exmem 928x600, rect 880x576, idx 880x576 palette index). */
int g3x_shadow2_blit_restore_target(unsigned char *bm, unsigned char *op,
                                    int buf_w, unsigned int target_idx)
{
    if (!bm || !op || g3x_shadow2_mode == G3X_SHADOW_MODE_NONE ||
        g3x_shadow2_w <= 0 || g3x_shadow2_h <= 0 || buf_w <= 0 ||
        g3x_shadow2_x0 < 0 || g3x_shadow2_y0 < 0 ||
        (g3x_shadow2_x0 + g3x_shadow2_w) > G3X_SHADOW_FULL_WIDTH ||
        (g3x_shadow2_y0 + g3x_shadow2_h) > G3X_SHADOW_FULL_HEIGHT)
    {
        return 0;
    }

    unsigned int idx = target_idx & 1u;
    if (!bitmap_buffer[idx] || !opacity_buffer[idx])
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
            unsigned short *dst_op = (unsigned short *)(opacity_buffer[idx]) + dst_pair_base;
            unsigned int *dst_bm = (unsigned int *)(bitmap_buffer[idx]) + dst_pair_base;
            int pairs = g3x_shadow2_w >> 1;
            for (int p = 0; p < pairs; ++p)
            {
                unsigned int uyvy = 0u;
                unsigned short op16 = 0u;
                g3x_shadow2_expand_pair(src_idx[p * 2], src_idx[p * 2 + 1], &uyvy, &op16);
                dst_op[p] = op16;
                dst_bm[p] = uyvy;
            }
        }
        return 1;
    }

    if (g3x_shadow2_mode == G3X_SHADOW_MODE_EXMEM &&
        g3x_shadow2_x0 == 0 && g3x_shadow2_y0 == 0 &&
        g3x_shadow2_w == G3X_SHADOW_FULL_WIDTH &&
        g3x_shadow2_h == G3X_SHADOW_FULL_HEIGHT &&
        buf_w == G3X_SHADOW_FULL_WIDTH)
    {
        memcpy((void *)opacity_buffer[idx], op, G3X_SHADOW_FULL_OP_SIZE);
        memcpy((void *)bitmap_buffer[idx], bm, G3X_SHADOW_FULL_BM_SIZE);
        return 1;
    }

    for (int ry = 0; ry < g3x_shadow2_h; ++ry)
    {
        int screen_y = g3x_shadow2_y0 + ry;
        unsigned int offset_op = (unsigned int)(screen_y * buf_w + g3x_shadow2_x0);
        unsigned int offset_bm = offset_op * 2u;

        unsigned char *src_op = op + ry * g3x_shadow2_w;
        unsigned char *src_bm = bm + (ry * g3x_shadow2_w) * 2;

        memcpy((void *)&opacity_buffer[idx][offset_op], src_op, (unsigned int)g3x_shadow2_w);
        memcpy((void *)&bitmap_buffer[idx][offset_bm], src_bm, (unsigned int)(g3x_shadow2_w * 2));
    }
    return 1;
}

/* INFERRED post-transfer handler (docs/PORT49_GUI_SYNC.md answer (c);
 * manifests/port49_gui_sync_evidence.json):
 * Runs immediately after MakeOsdVram (0xFC183A13 at 0xFC3806F2) finishes
 * overwriting bitmap_buffer[target_idx] and opacity_buffer[target_idx], and
 * immediately before VTM_FlipAndCommit (0xFC38090B at 0xFC380A1C) writes
 * active_bitmap_buffer (0x0000D2A4 at 0xFC38091E) and commits the flip. */
unsigned int g3x_gui_sync_post_c(void)
{
    unsigned int saved_lr = g3x_gui_sync_saved_lr;
    unsigned int target_idx = g3x_gui_sync_target_buf & 1u;
    g3x_gui_sync_in_flight = 0u;
    g3x_diag_record_sync_hit();
    g3x_diag_record_hook_hit();

    if (!camera_info.state.gui_mode_none &&
        g3x_dbuf_shadow_is_allocated() &&
        g3x_shadow2_mode != G3X_SHADOW_MODE_NONE)
    {
        (void)g3x_dbuf_shadow_sync_restore(target_idx);
    }
    return saved_lr;
}

#if defined(__arm__) || defined(__thumb__)
/* INFERRED Thumb-2 callback installed at *(volatile unsigned int *)0x0000E26C
 * (docs/PORT49_GUI_SYNC.md answer (c); manifests/port49_gui_sync_evidence.json
 * ROM 0xFC143492..0xFC1434A3 and ROM 0xFC380634..0xFC3806FB).
 * Reuses the naked inline-asm hooking style of CreateTask / NOOVERDRAW. */
void __attribute__((naked, noinline)) g3x_gui_sync_pre_cb(void)
{
    asm volatile (
        ".syntax unified\n"
        "ldr     r0, [sp, #4]\n"
        "ldr     r1, =0xFC380675\n"
        "cmp     r0, r1\n"
        "bne     1f\n"
        "ldr     r2, =g3x_gui_sync_in_flight\n"
        "ldr     r0, [r2]\n"
        "cbnz    r0, 1f\n"
        "ldr     r0, [sp, #92]\n"
        "ldr     r1, =g3x_gui_sync_post_trampoline\n"
        "orr     r1, r1, #1\n"
        "cmp     r0, r1\n"
        "beq     1f\n"
        "movs    r3, #1\n"
        "str     r3, [r2]\n"
        "ldr     r2, =g3x_gui_sync_saved_lr\n"
        "str     r0, [r2]\n"
        "mov     r3, r9\n"
        "and     r3, r3, #1\n"
        "ldr     r2, =g3x_gui_sync_target_buf\n"
        "str     r3, [r2]\n"
        "str     r1, [sp, #92]\n"
        "1:\n"
        "movs    r0, #0\n"
        "bx      lr\n"
        ".ltorg\n"
    );
}

/* INFERRED post-transfer return trampoline entered from transfer_src_overlay's
 * epilogue pop.w {r4-r9, pc} at 0xFC3806F8 (docs/PORT49_GUI_SYNC.md answer (c);
 * manifests/port49_gui_sync_evidence.json ROM 0xFC3806F2..0xFC3806FB).
 * Preserves r0-r3, r4, lr (24 B = 8-byte aligned SP; AAPCS preserves r4-r11
 * across g3x_gui_sync_post_c), then branches to the original saved lr. */
void __attribute__((naked, noinline)) g3x_gui_sync_post_trampoline(void)
{
    asm volatile (
        ".syntax unified\n"
        "push    {r0-r3, r4, lr}\n"
        "bl      g3x_gui_sync_post_c\n"
        "mov     r12, r0\n"
        "pop     {r0-r3, r4, lr}\n"
        "bx      r12\n"
    );
}
#else
void g3x_gui_sync_pre_cb(void)
{
}

void g3x_gui_sync_post_trampoline(void)
{
    (void)g3x_gui_sync_post_c();
}
#endif

#endif /* G3X_GUI_SYNC_IMPL_H */
#endif /* G3X_GUI_DIAG_IMPLEMENTATION == 1 */
#endif /* G3X_GUI_SYNC == 1 */
