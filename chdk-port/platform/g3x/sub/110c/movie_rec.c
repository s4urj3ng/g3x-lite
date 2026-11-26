#include "conf.h"
#if defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
#if !defined(G3X_MOVIE_STANDALONE) || (G3X_MOVIE_STANDALONE != 1) || \
    !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1) || \
    !defined(G3X_MOVIE_RESTART_BUDGET) || (G3X_MOVIE_RESTART_BUDGET != 1) || \
    !defined(G3X_MOVIE_NOLIMIT) || (G3X_MOVIE_NOLIMIT != 1) || \
    !defined(G3X_MOVIE_AUTOCONT) || (G3X_MOVIE_AUTOCONT != 1) || \
    !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1)
#error G3X_MOVIE_SCREEN_OFF=1 requires G3X_MOVIE_STANDALONE=1 G3X_MOVIE_SESSION_CANCEL=1 G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_NOLIMIT=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1
#endif
#if defined(G3X_MOVIE_AUTOCONT_UI) && (G3X_MOVIE_AUTOCONT_UI == 1)
#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_MOVIE_AUTOCONT_UI=1
#endif
#if (defined(G3X_GUI5) && (G3X_GUI5 == 1)) || \
    (defined(G3X_GUI_FIX) && (G3X_GUI_FIX == 1)) || \
    (defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)) || \
    (defined(G3X_GUI_NOOVERDRAW) && (G3X_GUI_NOOVERDRAW == 1)) || \
    (defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)) || \
    (defined(G3X_GUI_DIAG) && (G3X_GUI_DIAG == 1)) || \
    (defined(G3X_GUI_SHADOW2) && (G3X_GUI_SHADOW2 == 1)) || \
    (defined(G3X_GUI_SYNC) && (G3X_GUI_SYNC == 1)) || \
    (defined(G3X_GUI_MENU) && (G3X_GUI_MENU == 1)) || \
    (defined(G3X_GUI_RESTORE2) && (G3X_GUI_RESTORE2 == 1)) || \
    (defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1))
#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with GUI/menu flags
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_SCREEN_OFF=1 is incompatible with G3X_CONF_SAVE=1
#endif
#endif
#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)
#include "keyboard.h"
#include "camera_info.h"
#include "../../movie_status.h"
#endif

void change_video_tables(int a, int b)
{
    (void)a;
    (void)b;
}

void set_quality(int *x)
{
    (void)x;
}

#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)
/* PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK: mr_rec_state @ 0x0000C0C8 (*(0x0000C078 + 0x50)), verified @ 0xFC09B416 */
#if defined(__arm__) || defined(__thumb__)
int __attribute__((used)) g3x_get_movie_status(void)
{
    /* Read-only access to mr_rec_state @ 0x0000C0C8. Performs strictly read access; no stores. */
    return *(volatile const int *)0x0000C0C8;
}
#else
volatile int g3x_host_movie_state = 0;
int __attribute__((used)) g3x_get_movie_status(void)
{
    return g3x_host_movie_state;
}
#endif
#endif

#if (defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)) || (defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1))

#if defined(__arm__) || defined(__thumb__)

/* PORT56-ROM-CHECK-FRAME-LIMIT / PORT56-ROM-SETUP-MAX-FRAMES-STORE / PORT57-ROM-CHECK-LIMITS-WINDOW:
 * mr_max_frames @ 0x0000C274 (ROM_VERIFIED, read-only accessor)
 */
unsigned int __attribute__((used)) g3x_get_movie_max_frames(void)
{
    return *(volatile const unsigned int *)0x0000C274;
}

/* PORT56-ROM-CHECK-FRAME-LIMIT / PORT57-ROM-CHECK-LIMITS-WINDOW:
 * mr_cur_frames @ 0x0000C278 (ROM_VERIFIED, strictly read-only)
 */
unsigned int __attribute__((used)) g3x_get_movie_cur_frames(void)
{
    return *(volatile const unsigned int *)0x0000C278;
}

#else

volatile unsigned int g3x_host_movie_max_frames = 0;
volatile unsigned int g3x_host_movie_cur_frames = 0;

unsigned int __attribute__((used)) g3x_get_movie_max_frames(void)
{
    return g3x_host_movie_max_frames;
}

unsigned int __attribute__((used)) g3x_get_movie_cur_frames(void)
{
    return g3x_host_movie_cur_frames;
}

#endif

#endif /* G3X_MOVIE_NOLIMIT == 1 || G3X_MOVIE_AUTOCONT == 1 */

#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)

/* PORT-56: Movie Time-Limit RAM addresses & evidence classifications:
 * -------------------------------------------------------------------------------------------------------------------
 * Address    | Variable       | Evidence Classification | Manifest ID                             | Access Rule
 * -------------------------------------------------------------------------------------------------------------------
 * 0x0000C274 | mr_max_frames  | ROM_VERIFIED            | PORT56-ROM-SETUP-MAX-FRAMES-STORE,      | Store 0xFFFFFFFF
 *            |                |                         | PORT56-ROM-CHECK-FRAME-LIMIT            | ONLY while recording
 * 0x0000C278 | mr_cur_frames  | ROM_VERIFIED            | PORT56-ROM-CHECK-FRAME-LIMIT            | Strictly READ-ONLY
 * 0x0000C0E4 | mr_warn_sec    | ROM_VERIFIED            | PORT56-ROM-WARN-SEC-CHECK,              | DO NOT STORE
 *            |                |                         | PORT56-ROM-SETUP-MAX-FRAMES-STORE       | (UI warning only)
 * 0x0000C0C0 | mr_stop_reason | ROM_VERIFIED            | PORT56-ROM-CHECK-FRAME-LIMIT,           | DO NOT STORE
 *            |                |                         | PORT56-ROM-CHECK-SIZE-LIMIT             | (Stop reason code)
 * 0x0000C0C8 | mr_rec_state   | ROM_VERIFIED            | PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK| Strictly READ-ONLY
 * -------------------------------------------------------------------------------------------------------------------
 */

#if defined(__arm__) || defined(__thumb__)

/* Patch mr_max_frames with 0xFFFFFFFF on every loop tick while recording.
 * RAM store location: only the existing CHDK GUI/kbd loop context.
 * Store only mr_max_frames at 0x0000C274. Read mr_cur_frames at 0x0000C278 only.
 * Do not store to mr_warn_sec 0x0000C0E4, stop-reason word 0x0000C0C0, or anything tied to 4 GiB size limit.
 *
 * Timing rule: MOV:REC does NOT mean limit setup has finished (docs/VIDEO001_RECORDING_LIMITS.md:183),
 * and setup runs again on every record start (BL 0xFC09A97C). So on every loop tick while recording
 * (MOV status), if the value at 0x0000C274 is nonzero and not already the patched value,
 * replace it with 0xFFFFFFFF. The check is an unsigned blo at 0xFC098B22. Do nothing when not recording.
 */
void __attribute__((used)) g3x_movie_nolimit_poll(void)
{
    if (g3x_get_movie_status() == 1) // mr_rec_state == 1 (G3X_MOVIE_STATE_RECORDING)
    {
        volatile unsigned int * const p_max_frames = (volatile unsigned int *)0x0000C274;
        unsigned int val = *p_max_frames;
        if (val != 0 && val != 0xFFFFFFFFU)
        {
            *p_max_frames = 0xFFFFFFFFU;
        }
    }
}

#else

void __attribute__((used)) g3x_movie_nolimit_poll(void)
{
    if (g3x_get_movie_status() == 1)
    {
        if (g3x_host_movie_max_frames != 0 && g3x_host_movie_max_frames != 0xFFFFFFFFU)
        {
            g3x_host_movie_max_frames = 0xFFFFFFFFU;
        }
    }
}

#endif

#endif /* G3X_MOVIE_NOLIMIT == 1 */

#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)

/* PORT-57 / PORT-58: Gated Movie Automatic Continuation & Volatile User Controls
 * (G3X_MOVIE_AUTOCONT=1 / G3X_MOVIE_AUTOCONT_UI=1).
 * All MovieRecorder RAM inspection addresses (0x0000C0C8, 0x0000C0C0, 0x0000C274, 0x0000C278,
 * 0x0000C078, 0x0000C0D4, 0x0000C0D8, 0x0000C290, 0x0000C298, 0x0000C2A0, 0x0000C2A8)
 * are strictly READ-ONLY (PORT57-ROM-CHECK-LIMITS-WINDOW).
 * Only owned synthetic KEY_VIDEO (bit 3 = 0x00000008) in kbd_mod_state[0] and physw_status[0]
 * (0x00040DAC) is toggled during a single bounded restart pulse after confirmed idle.
 */

extern long kbd_new_state[3];
extern long kbd_mod_state[3];
extern long physw_status[3];
extern void kbd_key_press(long key);
extern void kbd_key_release(long key);

#if defined(__arm__) || defined(__thumb__)

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_stop_reason @ 0x0000C0C0 (32-bit word, strictly read-only) */
unsigned int __attribute__((used)) g3x_get_movie_stop_reason(void)
{
    return *(volatile const unsigned int *)0x0000C0C0;
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_segment_index @ 0x0000C078 (8-bit byte, strictly read-only) */
unsigned int __attribute__((used)) g3x_get_movie_segment_index(void)
{
    return (unsigned int)(*(volatile const unsigned char *)0x0000C078);
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_fs_reserve_size @ 0x0000C0D8 (32-bit word, strictly read-only) */
unsigned int __attribute__((used)) g3x_get_movie_fs_reserve_size(void)
{
    return *(volatile const unsigned int *)0x0000C0D8;
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_avail_space_bytes @ 0x0000C290 (64-bit dword, strictly read-only) */
unsigned long long __attribute__((used)) g3x_get_movie_avail_space(void)
{
    return *(volatile const unsigned long long *)0x0000C290;
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_stream_bytes @ 0x0000C298 (64-bit dword, strictly read-only) */
unsigned long long __attribute__((used)) g3x_get_movie_stream_bytes(void)
{
    return *(volatile const unsigned long long *)0x0000C298;
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_projected_size @ 0x0000C2A0 (64-bit dword, strictly read-only) */
unsigned long long __attribute__((used)) g3x_get_movie_projected_size(void)
{
    return *(volatile const unsigned long long *)0x0000C2A0;
}

/* PORT57-ROM-CHECK-LIMITS-WINDOW: mr_projected_base_off @ 0x0000C2A8 (64-bit dword, strictly read-only) */
unsigned long long __attribute__((used)) g3x_get_movie_projected_base_offset(void)
{
    return *(volatile const unsigned long long *)0x0000C2A8;
}

#else

volatile unsigned int g3x_host_movie_stop_reason = 0;
volatile unsigned int g3x_host_movie_segment_index = 1;
volatile unsigned int g3x_host_movie_fs_reserve_size = 0;
volatile unsigned long long g3x_host_movie_avail_space = 0;
volatile unsigned long long g3x_host_movie_stream_bytes = 0;
volatile unsigned long long g3x_host_movie_projected_size = 0;
volatile unsigned long long g3x_host_movie_projected_base_offset = 0;

unsigned int __attribute__((used)) g3x_get_movie_stop_reason(void)
{
    return g3x_host_movie_stop_reason;
}

unsigned int __attribute__((used)) g3x_get_movie_segment_index(void)
{
    return g3x_host_movie_segment_index & 0xFFU;
}

unsigned int __attribute__((used)) g3x_get_movie_fs_reserve_size(void)
{
    return g3x_host_movie_fs_reserve_size;
}

unsigned long long __attribute__((used)) g3x_get_movie_avail_space(void)
{
    return g3x_host_movie_avail_space;
}

unsigned long long __attribute__((used)) g3x_get_movie_stream_bytes(void)
{
    return g3x_host_movie_stream_bytes;
}

unsigned long long __attribute__((used)) g3x_get_movie_projected_size(void)
{
    return g3x_host_movie_projected_size;
}

unsigned long long __attribute__((used)) g3x_get_movie_projected_base_offset(void)
{
    return g3x_host_movie_projected_base_offset;
}

#endif

/* Nonblocking session state machine & volatile user control variables */
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
#define G3X_AUTOCONT_BOOT_ENABLED_DEFAULT 1
#else
#define G3X_AUTOCONT_BOOT_ENABLED_DEFAULT 0
#endif
static volatile int g3x_autocont_enabled = G3X_AUTOCONT_BOOT_ENABLED_DEFAULT;
static int g3x_autocont_menu_bool_val = G3X_AUTOCONT_BOOT_ENABLED_DEFAULT;
static volatile int g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
static volatile int g3x_autocont_state = G3X_AUTOCONT_DISARMED;
static volatile unsigned int g3x_autocont_timer_polls = 0U;
static volatile int g3x_autocont_prev_rec_state = -1;
static volatile int g3x_autocont_saw_boot_idle = 0;
static volatile int g3x_autocont_idle_start_press_seen = 0;
static volatile unsigned int g3x_autocont_idle_press_age = 0U;
static volatile int g3x_autocont_cancel_latched = 0;
static volatile int g3x_autocont_held_from_idle = 0;
static volatile unsigned int g3x_autocont_start_hold_polls = 0U;
static volatile int g3x_autocont_saw_frames_in_bounds = 0;
static volatile int g3x_autocont_saw_size_in_bounds = 0;
static volatile int g3x_autocont_synth_owned = 0;
static volatile unsigned int g3x_autocont_last_stop_reason = 0U;
static volatile unsigned int g3x_autocont_restart_count = 0U;
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
static volatile unsigned int g3x_autocont_restart_budget = G3X_AUTOCONT_BUDGET_DEFAULT;
static volatile unsigned int g3x_autocont_restarts_remaining = 0U;
static volatile unsigned int g3x_autocont_session_restarts_used = 0U;
static volatile int g3x_autocont_attempt_admitted = 0;
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
static volatile int g3x_autocont_session_cancelled = 0;
#endif
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
/* PORT-64: Bounded screen-off & restoration policy and deliberate-start arming state
 * (scoped to G3X_MOVIE_STANDALONE=1 in the PORT-64 profile).
 * Firmware backlight routines (FINSIG + ROM_VERIFIED in PORT64-ROM-BACKLIGHT-CORE-WINDOW
 * 0xFC37C3E0..0xFC37C4FF and PORT64-ROM-DISPCON-BACKLIGHT-WINDOW 0xFC37CD20..0xFC37CE1F):
 * - TurnOffBackLight: 0xFC37C449 (_TurnOffBackLight, 0-arg void ABI, acquires DispCon semaphore
 *   [r4, #0x4C] with timeout 10000 via 0xFC31BEC4, idempotent on [r4, #0x10] == 1, sets
 *   [r4, #0x10] = 0 while leaving [r4, #0x14] == 1 intact, releases [r4, #0x4C] via 0xFC31B8E8).
 * - TurnOnBackLight:  0xFC37C3EF (_TurnOnBackLight, 0-arg void ABI, acquires DispCon semaphore
 *   [r4, #0x4C] with timeout 10000 via 0xFC31BEC4, idempotent on [r4, #0x10] == 1, checks display-active
 *   precondition [r4, #0x14] == 1, sets [r4, #0x10] = 1, releases [r4, #0x4C] via 0xFC31BECC).
 * - Task context: DryOS resident task context (mykbd_task 10 ms poll via my_kbd_read_keys ->
 *   g3x_movie_autocont_poll). Never called from an ISR.
 */
#define G3X_ADDR_TURNOFFBACKLIGHT                0xFC37C449U
#define G3X_ADDR_TURNONBACKLIGHT                 0xFC37C3EFU
#define G3X_KEY_DISPLAY_BIT                      0x00001000U
#define G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS      100U  /* 1.0 s post-start settle in confirmed RECORDING before TurnOffBackLight() */
#define G3X_AUTOCONT_SCREEN_REFRESH_POLLS        3000U /* 30.0 s bounded periodic idempotent re-assert interval while screen-off is active */
#define G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS    120U  /* Finite per-clip cap (120 * 30 s = 60 min) on periodic TurnOffBackLight() refreshes */

extern void TurnOffBackLight(void);
extern void TurnOnBackLight(void);
extern int rec_mode_active(void);

static volatile int g3x_autocont_confirmed_idle_ready = 0;
static volatile int g3x_autocont_screen_off_active = 0;
static volatile int g3x_autocont_screen_off_reassert_pending = 0;
static volatile int g3x_autocont_screen_user_woke = 0;
static volatile int g3x_autocont_prev_display_pressed = 0;
static volatile int g3x_autocont_display_consumed = 0;
static volatile unsigned int g3x_autocont_screen_off_delay_polls = 0U;
static volatile unsigned int g3x_autocont_screen_refresh_polls = 0U;
static volatile unsigned int g3x_autocont_screen_refresh_count = 0U;
static volatile unsigned int g3x_autocont_backlight_off_calls = 0U;
static volatile unsigned int g3x_autocont_backlight_on_calls = 0U;

static void g3x_autocont_sync_mode_play(void)
{
    camera_info.state.mode_play = rec_mode_active() ? 0 : 1;
}

static void g3x_autocont_engage_screen_off(void)
{
    TurnOffBackLight();
    g3x_autocont_backlight_off_calls++;
    g3x_autocont_screen_off_active = 1;
    g3x_autocont_screen_off_reassert_pending = 0;
    g3x_autocont_screen_off_delay_polls = 0U;
    g3x_autocont_screen_refresh_polls = G3X_AUTOCONT_SCREEN_REFRESH_POLLS;
}

static void g3x_autocont_restore_backlight(int clear_user_woke)
{
    g3x_autocont_screen_off_delay_polls = 0U;
    g3x_autocont_screen_refresh_polls = 0U;
    g3x_autocont_screen_refresh_count = 0U;
    g3x_autocont_screen_off_reassert_pending = 0;
    if (clear_user_woke)
    {
        g3x_autocont_screen_user_woke = 0;
        g3x_autocont_prev_display_pressed = 0;
        g3x_autocont_display_consumed = 0;
    }
    if (g3x_autocont_screen_off_active)
    {
        g3x_autocont_screen_off_active = 0;
        TurnOnBackLight();
        g3x_autocont_backlight_on_calls++;
    }
}

static void g3x_autocont_arm_screen_off_for_clip(int is_initial_clip)
{
    int phys_disp = (((unsigned int)kbd_new_state[0] & G3X_KEY_DISPLAY_BIT) == 0U) ? 1 : 0;
    g3x_autocont_prev_display_pressed = phys_disp;
    g3x_autocont_display_consumed = 0;
    g3x_autocont_screen_refresh_polls = 0U;
    g3x_autocont_screen_refresh_count = 0U;
    if (is_initial_clip)
    {
        g3x_autocont_screen_user_woke = 0;
        g3x_autocont_screen_off_active = 0;
        g3x_autocont_screen_off_reassert_pending = 0;
        g3x_autocont_screen_off_delay_polls = G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS;
    }
    else
    {
        if (!g3x_autocont_screen_user_woke)
        {
            g3x_autocont_screen_off_reassert_pending = 1;
            g3x_autocont_screen_off_delay_polls = G3X_AUTOCONT_SCREEN_OFF_DELAY_POLLS;
        }
        else
        {
            g3x_autocont_screen_off_reassert_pending = 0;
            g3x_autocont_screen_off_delay_polls = 0U;
        }
    }
}

static void g3x_autocont_poll_screen_off_in_recording(int cur_state, int phys_video_pressed)
{
    int phys_disp_pressed = (((unsigned int)kbd_new_state[0] & G3X_KEY_DISPLAY_BIT) == 0U) ? 1 : 0;
    if (cur_state != G3X_MOVIE_STATE_RECORDING ||
        g3x_autocont_state != G3X_AUTOCONT_RECORDING ||
        camera_info.state.mode_play != 0)
    {
        g3x_autocont_restore_backlight(1);
        return;
    }

    if (phys_video_pressed)
    {
        g3x_autocont_prev_display_pressed = phys_disp_pressed;
        g3x_autocont_display_consumed = 0;
        return;
    }

    if (phys_disp_pressed)
    {
        if (!g3x_autocont_prev_display_pressed)
        {
            g3x_autocont_prev_display_pressed = 1;
            g3x_autocont_display_consumed = 1;
            physw_status[0] |= (long)G3X_KEY_DISPLAY_BIT;
            if (g3x_autocont_screen_off_active && !g3x_autocont_screen_off_reassert_pending)
            {
                g3x_autocont_screen_user_woke = 1;
                g3x_autocont_restore_backlight(0);
            }
            else
            {
                g3x_autocont_screen_user_woke = 0;
                g3x_autocont_screen_refresh_count = 0U;
                g3x_autocont_engage_screen_off();
            }
            return;
        }
        if (g3x_autocont_display_consumed)
        {
            physw_status[0] |= (long)G3X_KEY_DISPLAY_BIT;
        }
    }
    else
    {
        g3x_autocont_prev_display_pressed = 0;
        g3x_autocont_display_consumed = 0;
    }

    if (g3x_autocont_screen_user_woke)
    {
        return;
    }

    if (!g3x_autocont_screen_off_active || g3x_autocont_screen_off_reassert_pending)
    {
        if (g3x_autocont_screen_off_delay_polls > 0U)
        {
            g3x_autocont_screen_off_delay_polls--;
            if (g3x_autocont_screen_off_delay_polls > 0U)
            {
                return;
            }
        }
        g3x_autocont_engage_screen_off();
        return;
    }

    if (g3x_autocont_screen_refresh_count < G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS)
    {
        if (g3x_autocont_screen_refresh_polls > 0U)
        {
            g3x_autocont_screen_refresh_polls--;
        }
        if (g3x_autocont_screen_refresh_polls == 0U)
        {
            TurnOffBackLight();
            g3x_autocont_backlight_off_calls++;
            g3x_autocont_screen_refresh_count++;
            if (g3x_autocont_screen_refresh_count < G3X_AUTOCONT_SCREEN_MAX_REFRESH_CALLS)
            {
                g3x_autocont_screen_refresh_polls = G3X_AUTOCONT_SCREEN_REFRESH_POLLS;
            }
        }
    }
}
#endif

/* Previous stop counter snapshots to reject unreset counters before SetupModeAndLimits completes */
static volatile unsigned int g3x_autocont_last_stop_cur_frames = 0U;
static volatile unsigned long long g3x_autocont_last_stop_stream_bytes = 0ULL;
static volatile unsigned long long g3x_autocont_last_stop_proj_total = 0ULL;
static volatile unsigned int g3x_autocont_session_prev_cur_frames = 0U;
static volatile unsigned long long g3x_autocont_session_prev_stream_bytes = 0ULL;

static unsigned long long g3x_autocont_compute_projected_total(void)
{
    /* PORT57-ROM-CHECK-LIMITS-WINDOW (0xFC098C0E..0xFC098C28):
     * *(uint64_t *)0x0000C2A0 = proj_total - *(uint64_t *)0x0000C2A8 + ((uint64_t)fs_reserve_size << 1)
     */
    unsigned long long proj_stored = g3x_get_movie_projected_size();
    unsigned long long base_off = g3x_get_movie_projected_base_offset();
    unsigned long long reserve2 = ((unsigned long long)g3x_get_movie_fs_reserve_size()) << 1;
    unsigned long long sum = proj_stored + base_off;
    if (sum >= reserve2)
    {
        return sum - reserve2;
    }
    return proj_stored;
}

static void g3x_autocont_assert_synth_press(void)
{
    g3x_autocont_synth_owned = 1;
    kbd_key_press(KEY_VIDEO);
    physw_status[0] &= ~((long)G3X_KEY_VIDEO_BIT);
}

static void g3x_autocont_release_synth_input(void)
{
    if (g3x_autocont_synth_owned)
    {
        kbd_key_release(KEY_VIDEO);
        if (((unsigned int)kbd_new_state[0] & G3X_KEY_VIDEO_BIT) != 0U)
        {
            physw_status[0] |= (long)G3X_KEY_VIDEO_BIT;
        }
        g3x_autocont_synth_owned = 0;
    }
}

static void g3x_autocont_reset_session_metrics(void)
{
    g3x_autocont_saw_frames_in_bounds = 0;
    g3x_autocont_saw_size_in_bounds = 0;
    g3x_autocont_held_from_idle = 0;
    g3x_autocont_start_hold_polls = 0U;
    g3x_autocont_session_prev_cur_frames = 0U;
    g3x_autocont_session_prev_stream_bytes = 0ULL;
}

static void g3x_autocont_disarm_with_reason(int latch_cancel, int reason, int disable_toggle)
{
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_idle_press_age = 0U;
    g3x_autocont_timer_polls = 0U;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_confirmed_idle_ready = 0;
    g3x_autocont_restore_backlight(1);
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
    g3x_autocont_attempt_admitted = 0;
#endif
    g3x_autocont_state = G3X_AUTOCONT_DISARMED;
    g3x_autocont_disarm_reason = reason;
    if (latch_cancel)
    {
        g3x_autocont_cancel_latched = 1;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
        g3x_autocont_session_cancelled = 1;
#endif
    }
    if (disable_toggle)
    {
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
        /* Standalone profile remains enabled across runtime disarms so only a new
         * deliberate physical start after confirmed idle rearms the next session.
         */
#elif defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
        if (!g3x_autocont_session_cancelled)
        {
            g3x_autocont_enabled = 0;
            g3x_autocont_menu_bool_val = 0;
        }
#else
        g3x_autocont_enabled = 0;
        g3x_autocont_menu_bool_val = 0;
#endif
    }
}

static void g3x_autocont_snapshot_stop_counters(void)
{
    g3x_autocont_last_stop_cur_frames = g3x_get_movie_cur_frames();
    g3x_autocont_last_stop_stream_bytes = g3x_get_movie_stream_bytes();
    g3x_autocont_last_stop_proj_total = g3x_autocont_compute_projected_total();
}

static void g3x_autocont_sample_recording_metrics(void)
{
    unsigned int cur_frames = g3x_get_movie_cur_frames();
    unsigned int max_frames = g3x_get_movie_max_frames();
    unsigned long long stream_bytes = g3x_get_movie_stream_bytes();
    unsigned long long avail_space = g3x_get_movie_avail_space();
    unsigned long long proj_total = g3x_autocont_compute_projected_total();
    unsigned long long size_cap = ((unsigned long long)g3x_get_movie_segment_index()) * 0xFFFFFFFFULL;

    /* Detect counter reset if SetupModeAndLimits finishes after mr_rec_state becomes 1 */
    if (cur_frames < g3x_autocont_session_prev_cur_frames)
    {
        g3x_autocont_saw_frames_in_bounds = 0;
    }
    if (stream_bytes < g3x_autocont_session_prev_stream_bytes)
    {
        g3x_autocont_saw_size_in_bounds = 0;
    }
    g3x_autocont_session_prev_cur_frames = cur_frames;
    g3x_autocont_session_prev_stream_bytes = stream_bytes;

    if (g3x_autocont_last_stop_cur_frames != 0U && cur_frames != g3x_autocont_last_stop_cur_frames)
    {
        g3x_autocont_last_stop_cur_frames = 0U;
    }
    if (g3x_autocont_last_stop_stream_bytes != 0ULL &&
        (stream_bytes != g3x_autocont_last_stop_stream_bytes || proj_total != g3x_autocont_last_stop_proj_total))
    {
        g3x_autocont_last_stop_stream_bytes = 0ULL;
        g3x_autocont_last_stop_proj_total = 0ULL;
    }

    if (g3x_autocont_last_stop_cur_frames == 0U &&
        cur_frames > 0U && max_frames > 0U && max_frames != 0xFFFFFFFFU && cur_frames < max_frames)
    {
        g3x_autocont_saw_frames_in_bounds = 1;
    }

    if (g3x_autocont_last_stop_stream_bytes == 0ULL &&
        cur_frames > 0U && stream_bytes > 0ULL && size_cap > 0ULL &&
        proj_total > 0ULL && proj_total <= size_cap && avail_space >= proj_total)
    {
        g3x_autocont_saw_size_in_bounds = 1;
    }
}

static int g3x_autocont_check_eligible_stop(unsigned int *out_reason)
{
    unsigned int reason = g3x_get_movie_stop_reason();
    if (reason == G3X_MR_STOP_REASON_FRAME_LIMIT)
    {
        /* Reason 4 (0xFC098B22..0xFC098B28): unsigned cmp cur_frames, max_frames; bcc (blo) */
        unsigned int cur_frames = g3x_get_movie_cur_frames();
        unsigned int max_frames = g3x_get_movie_max_frames();
        if (g3x_autocont_saw_frames_in_bounds &&
            max_frames > 0U && max_frames != 0xFFFFFFFFU && cur_frames >= max_frames)
        {
            if (out_reason)
            {
                *out_reason = G3X_MR_STOP_REASON_FRAME_LIMIT;
            }
            return 1;
        }
        return 0;
    }
    if (reason == G3X_MR_STOP_REASON_SIZE_LIMIT)
    {
        /* Reason 3 (0xFC098C2C..0xFC098C5C): avail_space >= proj_total && proj_total > segment_index * 0xFFFFFFFFULL */
        unsigned long long avail_space = g3x_get_movie_avail_space();
        unsigned long long proj_total = g3x_autocont_compute_projected_total();
        unsigned long long size_cap = ((unsigned long long)g3x_get_movie_segment_index()) * 0xFFFFFFFFULL;
        if (g3x_autocont_saw_size_in_bounds &&
            size_cap > 0ULL && avail_space >= proj_total && proj_total > size_cap)
        {
            if (out_reason)
            {
                *out_reason = G3X_MR_STOP_REASON_SIZE_LIMIT;
            }
            return 1;
        }
        return 0;
    }
    return 0;
}

static void g3x_autocont_enter_confirmed_recording(void)
{
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_timer_polls = 0U;
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    int was_admitted = g3x_autocont_attempt_admitted;
#endif
    g3x_autocont_attempt_admitted = 0;
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
    if (g3x_autocont_session_cancelled)
    {
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
        g3x_autocont_confirmed_idle_ready = 0;
        g3x_autocont_restore_backlight(1);
#endif
        g3x_autocont_state = G3X_AUTOCONT_DISARMED;
        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_SESSION_CANCEL;
        return;
    }
#endif
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    if (!was_admitted ||
        (g3x_autocont_state != G3X_AUTOCONT_RELEASING &&
         g3x_autocont_state != G3X_AUTOCONT_WAIT_CONFIRM))
    {
#if defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
        g3x_autocont_confirmed_idle_ready = 0;
        g3x_autocont_restore_backlight(1);
#endif
        g3x_autocont_state = G3X_AUTOCONT_DISARMED;
        return;
    }
#endif
    g3x_autocont_state = G3X_AUTOCONT_RECORDING;
    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
    g3x_autocont_restart_count++;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_confirmed_idle_ready = 0;
    g3x_autocont_arm_screen_off_for_clip(0);
#endif
    g3x_autocont_sample_recording_metrics();
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_poll_screen_off_in_recording(G3X_MOVIE_STATE_RECORDING, 0);
#endif
}

void __attribute__((used)) g3x_movie_autocont_reset(void)
{
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_enabled = G3X_AUTOCONT_BOOT_ENABLED_DEFAULT;
    g3x_autocont_menu_bool_val = G3X_AUTOCONT_BOOT_ENABLED_DEFAULT;
    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
    g3x_autocont_state = G3X_AUTOCONT_DISARMED;
    g3x_autocont_timer_polls = 0U;
    g3x_autocont_prev_rec_state = -1;
    g3x_autocont_saw_boot_idle = 0;
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_idle_press_age = 0U;
    g3x_autocont_cancel_latched = 0;
    g3x_autocont_last_stop_reason = 0U;
    g3x_autocont_restart_count = 0U;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_confirmed_idle_ready = 0;
    g3x_autocont_screen_off_active = 0;
    g3x_autocont_screen_off_reassert_pending = 0;
    g3x_autocont_screen_user_woke = 0;
    g3x_autocont_prev_display_pressed = 0;
    g3x_autocont_display_consumed = 0;
    g3x_autocont_screen_off_delay_polls = 0U;
    g3x_autocont_screen_refresh_polls = 0U;
    g3x_autocont_screen_refresh_count = 0U;
    g3x_autocont_backlight_off_calls = 0U;
    g3x_autocont_backlight_on_calls = 0U;
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
    g3x_autocont_restart_budget = G3X_AUTOCONT_BUDGET_DEFAULT;
    g3x_autocont_restarts_remaining = 0U;
    g3x_autocont_session_restarts_used = 0U;
    g3x_autocont_attempt_admitted = 0;
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
    g3x_autocont_session_cancelled = 0;
#endif
    g3x_autocont_last_stop_cur_frames = 0U;
    g3x_autocont_last_stop_stream_bytes = 0ULL;
    g3x_autocont_last_stop_proj_total = 0ULL;
}

int __attribute__((used)) g3x_movie_autocont_is_enabled(void)
{
    return g3x_autocont_enabled;
}

int __attribute__((used)) g3x_movie_autocont_can_enable(void)
{
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_sync_mode_play();
#endif
    int cur_state = g3x_get_movie_status();
    int phys_video_released = (((unsigned int)kbd_new_state[0] & G3X_KEY_VIDEO_BIT) != 0U) ? 1 : 0;
    if (camera_info.state.mode_play != 0)
    {
        return 0;
    }
    if (!g3x_autocont_saw_boot_idle)
    {
        return 0;
    }
    if (cur_state != G3X_MOVIE_STATE_IDLE || g3x_autocont_prev_rec_state != G3X_MOVIE_STATE_IDLE)
    {
        return 0;
    }
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    if (!g3x_autocont_confirmed_idle_ready)
    {
        return 0;
    }
#endif
    if (!phys_video_released || g3x_autocont_synth_owned != 0)
    {
        return 0;
    }
    if (g3x_autocont_state != G3X_AUTOCONT_DISARMED)
    {
        return 0;
    }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
    if (g3x_autocont_session_cancelled)
    {
        return 0;
    }
#endif
    return 1;
}

int __attribute__((used)) g3x_movie_autocont_set_enabled(int enable)
{
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
    if (g3x_autocont_session_cancelled)
    {
        g3x_autocont_menu_bool_val = g3x_autocont_enabled ? 1 : 0;
        return 0;
    }
#endif
    if (!enable)
    {
        /* Immediate user disable: never stops an active clip, cancels pending restarts,
         * releases only continuation-owned synthetic keys, and displays OFF.
         */
        g3x_autocont_enabled = 0;
        g3x_autocont_menu_bool_val = 0;
        g3x_autocont_release_synth_input();
        g3x_autocont_reset_session_metrics();
        g3x_autocont_idle_start_press_seen = 0;
        g3x_autocont_idle_press_age = 0U;
        g3x_autocont_timer_polls = 0U;
        g3x_autocont_cancel_latched = 0;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
        g3x_autocont_confirmed_idle_ready = 0;
        g3x_autocont_restore_backlight(1);
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
        g3x_autocont_attempt_admitted = 0;
#endif
        g3x_autocont_state = G3X_AUTOCONT_DISARMED;
        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_USER_OFF;
        return 0;
    }

#if !defined(G3X_MOVIE_RESTART_BUDGET) || (G3X_MOVIE_RESTART_BUDGET != 1)
    if (g3x_autocont_enabled)
    {
        g3x_autocont_menu_bool_val = 1;
        return 1;
    }
#endif

    if (!g3x_movie_autocont_can_enable())
    {
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
        g3x_autocont_menu_bool_val = g3x_autocont_enabled ? 1 : 0;
#endif
#if !defined(G3X_MOVIE_RESTART_BUDGET) || (G3X_MOVIE_RESTART_BUDGET != 1)
        g3x_autocont_menu_bool_val = 0;
#endif
        return 0;
    }

    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_idle_press_age = 0U;
    g3x_autocont_timer_polls = 0U;
    g3x_autocont_cancel_latched = 0;
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
    g3x_autocont_restarts_remaining = 0U;
    g3x_autocont_session_restarts_used = 0U;
    g3x_autocont_attempt_admitted = 0;
#endif
    g3x_autocont_state = G3X_AUTOCONT_DISARMED;
    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
    g3x_autocont_prev_rec_state = G3X_MOVIE_STATE_IDLE;
    g3x_autocont_enabled = 1;
    g3x_autocont_menu_bool_val = 1;
    return 1;
}

int __attribute__((used)) g3x_movie_autocont_get_disarm_reason(void)
{
    return g3x_autocont_disarm_reason;
}

int __attribute__((used)) g3x_movie_autocont_is_faulted(void)
{
    int r = g3x_autocont_disarm_reason;
    if (g3x_autocont_state == G3X_AUTOCONT_DISARMED &&
        (r == G3X_AUTOCONT_REASON_PLAYBACK ||
         r == G3X_AUTOCONT_REASON_INVALID_STATE ||
         r == G3X_AUTOCONT_REASON_STOP_FAULT ||
         r == G3X_AUTOCONT_REASON_TIMEOUT))
    {
        return 1;
    }
    return 0;
}

const char * __attribute__((used)) g3x_movie_autocont_reason_str(void)
{
    switch (g3x_autocont_disarm_reason)
    {
        case G3X_AUTOCONT_REASON_NONE:          return "NONE";
        case G3X_AUTOCONT_REASON_USER_OFF:      return "USER";
        case G3X_AUTOCONT_REASON_PHYS_STOP:     return "STOP";
        case G3X_AUTOCONT_REASON_PLAYBACK:      return "PLAY";
        case G3X_AUTOCONT_REASON_INVALID_STATE: return "STATE";
        case G3X_AUTOCONT_REASON_STOP_FAULT:    return "LIMIT";
        case G3X_AUTOCONT_REASON_TIMEOUT:       return "TMO";
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
        case G3X_AUTOCONT_REASON_SESSION_CANCEL: return "CANC";
#endif
        default:                                return "?";
    }
}

const char * __attribute__((used)) g3x_movie_autocont_ui_status_str(void)
{
    int st = g3x_autocont_state;
    switch (st)
    {
        case G3X_AUTOCONT_RECORDING:    return "ARM";
        case G3X_AUTOCONT_WAIT_IDLE:    return "WAIT";
        case G3X_AUTOCONT_SETTLE:       return "SETL";
        case G3X_AUTOCONT_PRESSING:     return "PRS";
        case G3X_AUTOCONT_RELEASING:    return "REL";
        case G3X_AUTOCONT_WAIT_CONFIRM: return "CONF";
        case G3X_AUTOCONT_DISARMED:
        {
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled)
            {
                return "CANC";
            }
#endif
            if (g3x_movie_autocont_is_faulted())
            {
                return "FLT";
            }
            if (g3x_autocont_enabled)
            {
                return "RDY";
            }
            return "OFF";
        }
        default:
            return "FLT";
    }
}

const char * __attribute__((used)) g3x_movie_autocont_menu_str(void)
{
    int st = g3x_autocont_state;
    switch (st)
    {
        case G3X_AUTOCONT_RECORDING:    return "Armed";
        case G3X_AUTOCONT_WAIT_IDLE:    return "Wait";
        case G3X_AUTOCONT_SETTLE:       return "Settle";
        case G3X_AUTOCONT_PRESSING:     return "Restart";
        case G3X_AUTOCONT_RELEASING:    return "Restart";
        case G3X_AUTOCONT_WAIT_CONFIRM: return "Confirm";
        case G3X_AUTOCONT_DISARMED:
        {
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled)
            {
                return "Cancel";
            }
#endif
            if (g3x_movie_autocont_is_faulted())
            {
                return "Fault";
            }
            if (g3x_autocont_enabled)
            {
                return "Ready";
            }
            return "Off";
        }
        default:
            return "Fault";
    }
}

const char * __attribute__((used)) g3x_movie_autocont_menu_change(int change, int arg)
{
    (void)arg;
    if (change != 0)
    {
        if (g3x_autocont_enabled)
        {
            (void)g3x_movie_autocont_set_enabled(0);
        }
        else if (change < 0 && g3x_movie_autocont_is_faulted())
        {
            (void)g3x_movie_autocont_set_enabled(0);
        }
        else
        {
            (void)g3x_movie_autocont_set_enabled(1);
        }
    }
    return g3x_movie_autocont_menu_str();
}

void __attribute__((used)) g3x_movie_autocont_menu_cb(void)
{
    (void)g3x_movie_autocont_set_enabled(g3x_autocont_menu_bool_val ? 1 : 0);
}

int * __attribute__((used)) g3x_movie_autocont_get_menu_bool_ptr(void)
{
    g3x_autocont_menu_bool_val = g3x_autocont_enabled ? 1 : 0;
    return &g3x_autocont_menu_bool_val;
}
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
unsigned int __attribute__((used)) g3x_movie_autocont_get_restart_budget(void)
{
    return g3x_autocont_restart_budget;
}

int __attribute__((used)) g3x_movie_autocont_set_restart_budget(unsigned int budget)
{
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    (void)budget;
    return 0;
#else
    if (budget < G3X_AUTOCONT_BUDGET_MIN || budget > G3X_AUTOCONT_BUDGET_MAX)
    {
        return 0;
    }
    if (!g3x_movie_autocont_can_enable())
    {
        return 0;
    }
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_idle_press_age = 0U;
    g3x_autocont_timer_polls = 0U;
    g3x_autocont_cancel_latched = 0;
    g3x_autocont_restarts_remaining = 0U;
    g3x_autocont_session_restarts_used = 0U;
    g3x_autocont_attempt_admitted = 0;
    g3x_autocont_restart_budget = budget;
    return 1;
#endif
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_restarts_remaining(void)
{
    return g3x_autocont_restarts_remaining;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_session_restarts_used(void)
{
    return g3x_autocont_session_restarts_used;
}

int __attribute__((used)) g3x_movie_autocont_is_attempt_admitted(void)
{
    return g3x_autocont_attempt_admitted;
}

const char * __attribute__((used)) g3x_movie_autocont_budget_menu_str(void)
{
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    return "50";
#else
    switch (g3x_autocont_restart_budget)
    {
        case 1U: return "1";
        case 2U: return "2";
        case 3U: return "3";
        default: return "1";
    }
#endif
}

const char * __attribute__((used)) g3x_movie_autocont_budget_menu_change(int change, int arg)
{
    (void)arg;
    if (change != 0 && g3x_movie_autocont_can_enable())
    {
        unsigned int cur = g3x_autocont_restart_budget;
        unsigned int next = cur;
        if (cur < G3X_AUTOCONT_BUDGET_MIN || cur > G3X_AUTOCONT_BUDGET_MAX)
        {
            cur = G3X_AUTOCONT_BUDGET_DEFAULT;
        }
        if (change > 0)
        {
            next = (cur >= G3X_AUTOCONT_BUDGET_MAX) ? G3X_AUTOCONT_BUDGET_MIN : (cur + 1U);
        }
        else
        {
            next = (cur <= G3X_AUTOCONT_BUDGET_MIN) ? G3X_AUTOCONT_BUDGET_MAX : (cur - 1U);
        }
        (void)g3x_movie_autocont_set_restart_budget(next);
    }
    return g3x_movie_autocont_budget_menu_str();
}
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
int __attribute__((used)) g3x_movie_autocont_is_session_cancelled(void)
{
    return g3x_autocont_session_cancelled;
}

int __attribute__((used)) g3x_movie_autocont_can_cancel_session(void)
{
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_sync_mode_play();
#endif
    int cur_state = g3x_get_movie_status();
    int phys_video_pressed = (((unsigned int)kbd_new_state[0] & G3X_KEY_VIDEO_BIT) == 0U) ? 1 : 0;
    if (camera_info.state.mode_play != 0)
    {
        return 0;
    }
    if (cur_state < G3X_MOVIE_STATE_IDLE || cur_state > G3X_MOVIE_STATE_SEGMENT_SPLIT)
    {
        return 0;
    }
    if (!g3x_autocont_enabled || g3x_autocont_session_cancelled)
    {
        return 0;
    }
    if (g3x_autocont_state < G3X_AUTOCONT_RECORDING ||
        g3x_autocont_state > G3X_AUTOCONT_WAIT_CONFIRM)
    {
        return 0;
    }
    if (phys_video_pressed)
    {
        if (g3x_autocont_state != G3X_AUTOCONT_RECORDING ||
            !g3x_autocont_held_from_idle ||
            cur_state != G3X_MOVIE_STATE_RECORDING ||
            g3x_autocont_start_hold_polls == 0U)
        {
            return 0;
        }
    }
    return 1;
}

int __attribute__((used)) g3x_movie_autocont_cancel_session(void)
{
    int cur_state;
    int pre_state;
    int keep_held = 0;
    unsigned int keep_hold_polls = 0U;
    if (!g3x_movie_autocont_can_cancel_session())
    {
        return 0;
    }
    cur_state = g3x_get_movie_status();
    pre_state = g3x_autocont_state;
    if (pre_state == G3X_AUTOCONT_RECORDING &&
        cur_state == G3X_MOVIE_STATE_RECORDING &&
        g3x_autocont_held_from_idle &&
        g3x_autocont_start_hold_polls > 0U)
    {
        keep_held = 1;
        keep_hold_polls = g3x_autocont_start_hold_polls;
    }
    if (cur_state != G3X_MOVIE_STATE_RECORDING)
    {
        g3x_autocont_snapshot_stop_counters();
    }
    g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
    g3x_autocont_held_from_idle = keep_held;
    g3x_autocont_start_hold_polls = keep_hold_polls;
    if (pre_state != G3X_AUTOCONT_RECORDING)
    {
        g3x_autocont_prev_rec_state = -1;
    }
    g3x_autocont_session_cancelled = 1;
    return 1;
}

const char * __attribute__((used)) g3x_movie_autocont_cancel_menu_str(void)
{
    if (g3x_autocont_session_cancelled)
    {
        return "Cancel";
    }
    if (g3x_autocont_enabled &&
        g3x_autocont_state >= G3X_AUTOCONT_RECORDING &&
        g3x_autocont_state <= G3X_AUTOCONT_WAIT_CONFIRM)
    {
        return "Active";
    }
    return "Idle";
}

const char * __attribute__((used)) g3x_movie_autocont_cancel_menu_change(int change, int arg)
{
    (void)arg;
    if (change != 0)
    {
        (void)g3x_movie_autocont_cancel_session();
    }
    return g3x_movie_autocont_cancel_menu_str();
}
#endif

int __attribute__((used)) g3x_movie_autocont_get_state(void)
{
    return g3x_autocont_state;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_timer_polls(void)
{
    return g3x_autocont_timer_polls;
}

int __attribute__((used)) g3x_movie_autocont_is_synth_owned(void)
{
    return g3x_autocont_synth_owned;
}

int __attribute__((used)) g3x_movie_autocont_is_cancel_latched(void)
{
    return g3x_autocont_cancel_latched;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_last_stop_reason(void)
{
    return g3x_autocont_last_stop_reason;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_restart_count(void)
{
    return g3x_autocont_restart_count;
}
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
int __attribute__((used)) g3x_movie_autocont_is_screen_off_active(void)
{
    return g3x_autocont_screen_off_active;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_screen_off_delay_polls(void)
{
    return g3x_autocont_screen_off_delay_polls;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_screen_refresh_polls(void)
{
    return g3x_autocont_screen_refresh_polls;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_backlight_off_count(void)
{
    return g3x_autocont_backlight_off_calls;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_backlight_on_count(void)
{
    return g3x_autocont_backlight_on_calls;
}

int __attribute__((used)) g3x_movie_autocont_is_confirmed_idle_ready(void)
{
    return g3x_autocont_confirmed_idle_ready;
}

int __attribute__((used)) g3x_movie_autocont_is_idle_start_press_seen(void)
{
    return g3x_autocont_idle_start_press_seen;
}

unsigned int __attribute__((used)) g3x_movie_autocont_get_idle_press_age(void)
{
    return g3x_autocont_idle_press_age;
}
#endif

void __attribute__((used)) g3x_movie_autocont_poll(void)
{
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
    g3x_autocont_sync_mode_play();
#endif
    int cur_state = g3x_get_movie_status();
    int prev_state = g3x_autocont_prev_rec_state;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    int pre_poll_state = g3x_autocont_state;
#endif
    int phys_video_pressed = (((unsigned int)kbd_new_state[0] & G3X_KEY_VIDEO_BIT) == 0U) ? 1 : 0;
    int in_playback = (camera_info.state.mode_play != 0) ? 1 : 0;
    int invalid_rec_state = (cur_state < G3X_MOVIE_STATE_IDLE ||
                             cur_state > G3X_MOVIE_STATE_SEGMENT_SPLIT) ? 1 : 0;

    /* Disarm and release any owned synthetic key immediately in playback mode or on invalid movie state.
     * Deliberate reason handling:
     * - If already disabled and disarmed, do not clobber g3x_autocont_disarm_reason on repeated polls.
     * - If enabled or active, preserve physical-stop precedence if physical KEY_VIDEO is pressed in an active
     *   non-hold state; otherwise latch G3X_AUTOCONT_REASON_PLAYBACK or G3X_AUTOCONT_REASON_INVALID_STATE
     *   and auto-disable continuation.
     */
    if (in_playback || invalid_rec_state)
    {
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
        int phys_stop_takes_precedence = 0;
        int should_disarm = (g3x_autocont_state != G3X_AUTOCONT_DISARMED || g3x_autocont_enabled != 0) ? 1 : 0;
        if (phys_video_pressed)
        {
            if (g3x_autocont_state != G3X_AUTOCONT_DISARMED)
            {
                if (g3x_autocont_state != G3X_AUTOCONT_RECORDING ||
                    !g3x_autocont_held_from_idle ||
                    g3x_autocont_start_hold_polls == 0U)
                {
                    phys_stop_takes_precedence = 1;
                }
            }
            else if (g3x_autocont_session_cancelled &&
                     cur_state != G3X_MOVIE_STATE_IDLE &&
                     (!g3x_autocont_held_from_idle ||
                      cur_state != G3X_MOVIE_STATE_RECORDING ||
                      g3x_autocont_start_hold_polls == 0U))
            {
                phys_stop_takes_precedence = 1;
            }
        }
        if (g3x_autocont_state == G3X_AUTOCONT_DISARMED &&
            g3x_autocont_session_cancelled &&
            !phys_stop_takes_precedence &&
            ((g3x_autocont_disarm_reason == G3X_AUTOCONT_REASON_PHYS_STOP && g3x_autocont_cancel_latched) ||
             g3x_autocont_disarm_reason == G3X_AUTOCONT_REASON_PLAYBACK ||
             g3x_autocont_disarm_reason == G3X_AUTOCONT_REASON_INVALID_STATE))
        {
            should_disarm = 0;
        }
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
        if (g3x_autocont_state == G3X_AUTOCONT_DISARMED &&
            !g3x_autocont_session_cancelled &&
            !phys_stop_takes_precedence &&
            g3x_autocont_disarm_reason != G3X_AUTOCONT_REASON_NONE)
        {
            should_disarm = 0;
        }
#endif
        if (should_disarm)
        {
            if (phys_stop_takes_precedence)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 1);
            }
            else if (in_playback)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_PLAYBACK, 1);
            }
            else
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
            }
        }
        else
        {
            g3x_autocont_release_synth_input();
            g3x_autocont_reset_session_metrics();
            g3x_autocont_idle_start_press_seen = 0;
            g3x_autocont_idle_press_age = 0U;
            g3x_autocont_timer_polls = 0U;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
            g3x_autocont_confirmed_idle_ready = 0;
            g3x_autocont_restore_backlight(1);
#endif
        }
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
        if (phys_video_pressed && !phys_stop_takes_precedence)
        {
            g3x_autocont_cancel_latched = 1;
        }
        g3x_autocont_prev_rec_state = -1;
        return;
#else
        g3x_autocont_prev_rec_state = g3x_autocont_session_cancelled ? -1 : cur_state;
        return;
#endif
#endif
#if !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1)
        if (g3x_autocont_state != G3X_AUTOCONT_DISARMED || g3x_autocont_enabled != 0)
        {
            int phys_stop_takes_precedence = 0;
            if (phys_video_pressed && g3x_autocont_state != G3X_AUTOCONT_DISARMED)
            {
                if (g3x_autocont_state != G3X_AUTOCONT_RECORDING ||
                    !g3x_autocont_held_from_idle ||
                    g3x_autocont_start_hold_polls == 0U)
                {
                    phys_stop_takes_precedence = 1;
                }
            }
            if (phys_stop_takes_precedence)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 1);
            }
            else if (in_playback)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_PLAYBACK, 1);
            }
            else
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
            }
        }
        else
        {
            g3x_autocont_release_synth_input();
            g3x_autocont_reset_session_metrics();
            g3x_autocont_idle_start_press_seen = 0;
            g3x_autocont_idle_press_age = 0U;
            g3x_autocont_timer_polls = 0U;
        }
        g3x_autocont_prev_rec_state = cur_state;
        return;
#endif
    }

    if (!g3x_autocont_enabled)
    {
        g3x_autocont_release_synth_input();
        g3x_autocont_reset_session_metrics();
        g3x_autocont_idle_start_press_seen = 0;
        g3x_autocont_idle_press_age = 0U;
        g3x_autocont_timer_polls = 0U;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
        g3x_autocont_confirmed_idle_ready = 0;
        g3x_autocont_restore_backlight(1);
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
        g3x_autocont_attempt_admitted = 0;
#endif
        g3x_autocont_state = G3X_AUTOCONT_DISARMED;
        if (cur_state == G3X_MOVIE_STATE_IDLE)
        {
            g3x_autocont_saw_boot_idle = 1;
            if (!phys_video_pressed && g3x_autocont_cancel_latched)
            {
                g3x_autocont_cancel_latched = 0;
            }
        }
        g3x_autocont_prev_rec_state = cur_state;
        return;
    }

    switch (g3x_autocont_state)
    {
        case G3X_AUTOCONT_DISARMED:
        {
            g3x_autocont_release_synth_input();
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
            g3x_autocont_restore_backlight(1);
            if (cur_state == G3X_MOVIE_STATE_IDLE)
            {
                if (!phys_video_pressed)
                {
                    g3x_autocont_held_from_idle = 0;
                    g3x_autocont_start_hold_polls = 0U;
                    g3x_autocont_saw_boot_idle = 1;
                    g3x_autocont_confirmed_idle_ready = 1;
                    if (g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_cancel_latched = 0;
                    }
                    if (g3x_autocont_idle_start_press_seen)
                    {
                        if (g3x_autocont_idle_press_age > 0U)
                        {
                            g3x_autocont_idle_press_age--;
                            if (g3x_autocont_idle_press_age == 0U)
                            {
                                g3x_autocont_idle_start_press_seen = 0;
                            }
                        }
                        else
                        {
                            g3x_autocont_idle_start_press_seen = 0;
                        }
                    }
                }
                else
                {
                    if (g3x_autocont_saw_boot_idle &&
                        g3x_autocont_confirmed_idle_ready &&
                        !g3x_autocont_cancel_latched &&
                        (prev_state == G3X_MOVIE_STATE_IDLE ||
                         (g3x_autocont_idle_start_press_seen &&
                          g3x_autocont_held_from_idle &&
                          g3x_autocont_start_hold_polls > 0U)))
                    {
                        if (prev_state == G3X_MOVIE_STATE_IDLE)
                        {
                            g3x_autocont_held_from_idle = 1;
                            g3x_autocont_start_hold_polls = G3X_AUTOCONT_START_HOLD_POLLS;
                        }
                        else
                        {
                            g3x_autocont_start_hold_polls--;
                        }
                        g3x_autocont_idle_start_press_seen = 1;
                        g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    }
                    else
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_confirmed_idle_ready = 0;
                        g3x_autocont_idle_start_press_seen = 0;
                        g3x_autocont_idle_press_age = 0U;
                        g3x_autocont_held_from_idle = 0;
                        g3x_autocont_start_hold_polls = 0U;
                    }
                }
            }
            else if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                int same_poll_idle_press = (g3x_autocont_saw_boot_idle &&
                                            g3x_autocont_confirmed_idle_ready &&
                                            prev_state == G3X_MOVIE_STATE_IDLE &&
                                            !g3x_autocont_cancel_latched &&
                                            phys_video_pressed) ? 1 : 0;
                int second_press_after_transitional_release = (prev_state != G3X_MOVIE_STATE_IDLE &&
                                                               phys_video_pressed &&
                                                               (!g3x_autocont_held_from_idle ||
                                                                g3x_autocont_start_hold_polls == 0U)) ? 1 : 0;
                if (same_poll_idle_press)
                {
                    g3x_autocont_idle_start_press_seen = 1;
                }
                if (second_press_after_transitional_release)
                {
                    g3x_autocont_idle_start_press_seen = 0;
                }
                if (g3x_autocont_saw_boot_idle &&
                    g3x_autocont_confirmed_idle_ready &&
                    prev_state != G3X_MOVIE_STATE_RECORDING &&
                    !g3x_autocont_cancel_latched &&
                    g3x_autocont_idle_start_press_seen)
                {
                    g3x_autocont_reset_session_metrics();
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
                    g3x_autocont_restarts_remaining = g3x_autocont_restart_budget;
                    g3x_autocont_session_restarts_used = 0U;
                    g3x_autocont_attempt_admitted = 0;
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                    g3x_autocont_session_cancelled = 0;
#endif
                    g3x_autocont_state = G3X_AUTOCONT_RECORDING;
                    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
                    g3x_autocont_confirmed_idle_ready = 0;
                    g3x_autocont_held_from_idle = phys_video_pressed ? 1 : 0;
                    g3x_autocont_start_hold_polls = g3x_autocont_held_from_idle ? G3X_AUTOCONT_START_HOLD_POLLS : 0U;
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_idle_press_age = 0U;
                    g3x_autocont_arm_screen_off_for_clip(1);
                    g3x_autocont_sample_recording_metrics();
                    g3x_autocont_poll_screen_off_in_recording(cur_state, phys_video_pressed);
                }
                else
                {
                    g3x_autocont_confirmed_idle_ready = 0;
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_idle_press_age = 0U;
                    if (!phys_video_pressed)
                    {
                        g3x_autocont_held_from_idle = 0;
                        g3x_autocont_start_hold_polls = 0U;
                    }
                    else if (g3x_autocont_held_from_idle && g3x_autocont_start_hold_polls > 0U)
                    {
                        g3x_autocont_start_hold_polls--;
                    }
                    else
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
                        g3x_autocont_session_cancelled = 1;
                    }
                }
            }
            else
            {
                if (!g3x_autocont_idle_start_press_seen &&
                    g3x_autocont_saw_boot_idle &&
                    g3x_autocont_confirmed_idle_ready &&
                    prev_state == G3X_MOVIE_STATE_IDLE &&
                    !g3x_autocont_cancel_latched &&
                    phys_video_pressed)
                {
                    g3x_autocont_idle_start_press_seen = 1;
                    g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    g3x_autocont_held_from_idle = 1;
                    g3x_autocont_start_hold_polls = G3X_AUTOCONT_START_HOLD_POLLS;
                }
                else if (g3x_autocont_idle_start_press_seen &&
                         g3x_autocont_saw_boot_idle &&
                         g3x_autocont_confirmed_idle_ready &&
                         !g3x_autocont_cancel_latched)
                {
                    if (!phys_video_pressed)
                    {
                        g3x_autocont_held_from_idle = 0;
                        g3x_autocont_start_hold_polls = 0U;
                        if (g3x_autocont_idle_press_age > 0U)
                        {
                            g3x_autocont_idle_press_age--;
                            if (g3x_autocont_idle_press_age == 0U)
                            {
                                g3x_autocont_idle_start_press_seen = 0;
                                g3x_autocont_confirmed_idle_ready = 0;
                            }
                        }
                        else
                        {
                            g3x_autocont_idle_start_press_seen = 0;
                            g3x_autocont_confirmed_idle_ready = 0;
                        }
                    }
                    else if (g3x_autocont_held_from_idle && g3x_autocont_start_hold_polls > 0U)
                    {
                        g3x_autocont_start_hold_polls--;
                        g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    }
                    else
                    {
                        g3x_autocont_idle_start_press_seen = 0;
                        g3x_autocont_idle_press_age = 0U;
                        g3x_autocont_confirmed_idle_ready = 0;
                        g3x_autocont_held_from_idle = 0;
                        g3x_autocont_start_hold_polls = 0U;
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
                        g3x_autocont_session_cancelled = 1;
                    }
                }
                else
                {
                    g3x_autocont_confirmed_idle_ready = 0;
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_idle_press_age = 0U;
                    g3x_autocont_held_from_idle = 0;
                    g3x_autocont_start_hold_polls = 0U;
                    if (phys_video_pressed)
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
                        g3x_autocont_session_cancelled = 1;
                    }
                }
            }
#else
            if (cur_state == G3X_MOVIE_STATE_IDLE)
            {
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                g3x_autocont_held_from_idle = 0;
                g3x_autocont_start_hold_polls = 0U;
#endif
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
                if (!phys_video_pressed)
                {
                    g3x_autocont_saw_boot_idle = 1;
                    if (g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_cancel_latched = 0;
                    }
                    if (g3x_autocont_idle_start_press_seen)
                    {
                        if (g3x_autocont_idle_press_age > 0U)
                        {
                            g3x_autocont_idle_press_age--;
                            if (g3x_autocont_idle_press_age == 0U)
                            {
                                g3x_autocont_idle_start_press_seen = 0;
                            }
                        }
                        else
                        {
                            g3x_autocont_idle_start_press_seen = 0;
                        }
                    }
                }
                else
                {
                    if (g3x_autocont_saw_boot_idle &&
                        prev_state == G3X_MOVIE_STATE_IDLE &&
                        !g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_idle_start_press_seen = 1;
                        g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    }
                    else
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_idle_start_press_seen = 0;
                        g3x_autocont_idle_press_age = 0U;
                    }
                }
#else
                g3x_autocont_saw_boot_idle = 1;
                if (phys_video_pressed)
                {
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                    if (!g3x_autocont_cancel_latched &&
                        (!g3x_autocont_session_cancelled || prev_state == G3X_MOVIE_STATE_IDLE))
                    {
                        g3x_autocont_idle_start_press_seen = 1;
                        g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    }
#endif
#if !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1)
                    if (!g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_idle_start_press_seen = 1;
                        g3x_autocont_idle_press_age = G3X_AUTOCONT_CONFIRM_POLLS;
                    }
#endif
                }
                else
                {
                    if (g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_cancel_latched = 0;
                    }
                    if (g3x_autocont_idle_start_press_seen)
                    {
                        if (g3x_autocont_idle_press_age > 0U)
                        {
                            g3x_autocont_idle_press_age--;
                            if (g3x_autocont_idle_press_age == 0U)
                            {
                                g3x_autocont_idle_start_press_seen = 0;
                            }
                        }
                        else
                        {
                            g3x_autocont_idle_start_press_seen = 0;
                        }
                    }
                }
#endif
            }
            else if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                /* Arm ONLY on an observed deliberate physical recording start:
                 * requires confirmed boot idle, IDLE (0) -> RECORDING (1) transition, not cancel-latched,
                 * and a physical KEY_VIDEO press observed in IDLE after enabling (g3x_autocont_idle_start_press_seen).
                 * A recording-state transition alone cannot arm continuation.
                 */
                if (g3x_autocont_saw_boot_idle &&
                    prev_state == G3X_MOVIE_STATE_IDLE &&
                    !g3x_autocont_cancel_latched &&
                    g3x_autocont_idle_start_press_seen)
                {
                    g3x_autocont_reset_session_metrics();
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
                    g3x_autocont_restarts_remaining = g3x_autocont_restart_budget;
                    g3x_autocont_session_restarts_used = 0U;
                    g3x_autocont_attempt_admitted = 0;
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                    g3x_autocont_session_cancelled = 0;
#endif
                    g3x_autocont_state = G3X_AUTOCONT_RECORDING;
                    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_NONE;
                    g3x_autocont_held_from_idle = phys_video_pressed ? 1 : 0;
                    g3x_autocont_start_hold_polls = g3x_autocont_held_from_idle ? G3X_AUTOCONT_START_HOLD_POLLS : 0U;
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_idle_press_age = 0U;
                    g3x_autocont_sample_recording_metrics();
                }
                else
                {
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_idle_press_age = 0U;
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                    if (!phys_video_pressed)
                    {
                        g3x_autocont_held_from_idle = 0;
                        g3x_autocont_start_hold_polls = 0U;
                    }
                    else if (g3x_autocont_held_from_idle && g3x_autocont_start_hold_polls > 0U)
                    {
                        g3x_autocont_start_hold_polls--;
                    }
                    else
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
                        g3x_autocont_session_cancelled = 1;
#endif
                    }
#endif
#if !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1)
                    if (phys_video_pressed)
                    {
                        g3x_autocont_cancel_latched = 1;
                        g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
                    }
#endif
                }
            }
            else
            {
                g3x_autocont_idle_start_press_seen = 0;
                g3x_autocont_idle_press_age = 0U;
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
                g3x_autocont_held_from_idle = 0;
                g3x_autocont_start_hold_polls = 0U;
#endif
                if (phys_video_pressed)
                {
                    g3x_autocont_cancel_latched = 1;
                    g3x_autocont_disarm_reason = G3X_AUTOCONT_REASON_PHYS_STOP;
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
                    g3x_autocont_session_cancelled = 1;
#endif
                }
            }
#endif
            break;
        }

        case G3X_AUTOCONT_RECORDING:
        {
            if (!phys_video_pressed)
            {
                g3x_autocont_held_from_idle = 0;
                g3x_autocont_start_hold_polls = 0U;
            }
            else
            {
                /* Physical movie-button cancellation wins races with automatic-stop detection */
                if (!g3x_autocont_held_from_idle ||
                    cur_state != G3X_MOVIE_STATE_RECORDING ||
                    g3x_autocont_start_hold_polls == 0U)
                {
                    if (cur_state != G3X_MOVIE_STATE_RECORDING)
                    {
                        g3x_autocont_snapshot_stop_counters();
                    }
                    g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                    break;
                }
                g3x_autocont_start_hold_polls--;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled)
            {
                if (cur_state != G3X_MOVIE_STATE_RECORDING)
                {
                    g3x_autocont_snapshot_stop_counters();
                }
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif

            if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_sample_recording_metrics();
#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1) && defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
                g3x_autocont_poll_screen_off_in_recording(cur_state, phys_video_pressed);
#endif
            }
            else
            {
                unsigned int attributed_reason = 0U;
                int eligible = g3x_autocont_check_eligible_stop(&attributed_reason);
                g3x_autocont_snapshot_stop_counters();
                if (!eligible)
                {
                    g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_STOP_FAULT, 1);
                    break;
                }
                g3x_autocont_last_stop_reason = attributed_reason;
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
                if (g3x_autocont_restarts_remaining == 0U ||
                    g3x_autocont_session_restarts_used >= g3x_autocont_restart_budget ||
                    g3x_autocont_attempt_admitted != 0)
                {
                    g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                    break;
                }
                g3x_autocont_restarts_remaining--;
                g3x_autocont_session_restarts_used++;
                g3x_autocont_attempt_admitted = 1;
#endif
                if (cur_state == G3X_MOVIE_STATE_IDLE)
                {
                    g3x_autocont_state = G3X_AUTOCONT_SETTLE;
                    g3x_autocont_timer_polls = G3X_AUTOCONT_SETTLE_POLLS;
                }
                else
                {
                    g3x_autocont_state = G3X_AUTOCONT_WAIT_IDLE;
                    g3x_autocont_timer_polls = G3X_AUTOCONT_MAX_STOP_POLLS;
                }
            }
            break;
        }

        case G3X_AUTOCONT_WAIT_IDLE:
        {
            if (phys_video_pressed)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                break;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled &&
                (cur_state == G3X_MOVIE_STATE_IDLE ||
                 (cur_state >= G3X_MOVIE_STATE_STOPPING &&
                  cur_state <= G3X_MOVIE_STATE_SEGMENT_SPLIT &&
                  g3x_autocont_timer_polls > 1U)))
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
            if (!g3x_autocont_attempt_admitted ||
                g3x_autocont_session_restarts_used == 0U ||
                g3x_autocont_session_restarts_used > g3x_autocont_restart_budget)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                break;
            }
#endif
            if (cur_state == G3X_MOVIE_STATE_IDLE)
            {
                g3x_autocont_state = G3X_AUTOCONT_SETTLE;
                g3x_autocont_timer_polls = G3X_AUTOCONT_SETTLE_POLLS;
                break;
            }
            if (cur_state >= G3X_MOVIE_STATE_STOPPING && cur_state <= G3X_MOVIE_STATE_SEGMENT_SPLIT)
            {
                if (g3x_autocont_timer_polls > 0U)
                {
                    g3x_autocont_timer_polls--;
                    if (g3x_autocont_timer_polls > 0U)
                    {
                        break;
                    }
                }
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_TIMEOUT, 1);
                break;
            }
            g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
            break;
        }

        case G3X_AUTOCONT_SETTLE:
        {
            if (phys_video_pressed)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                break;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled && cur_state == G3X_MOVIE_STATE_IDLE)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
            if (!g3x_autocont_attempt_admitted ||
                g3x_autocont_session_restarts_used == 0U ||
                g3x_autocont_session_restarts_used > g3x_autocont_restart_budget)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                break;
            }
#endif
            if (cur_state != G3X_MOVIE_STATE_IDLE)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
                break;
            }
            if (g3x_autocont_timer_polls > 0U)
            {
                g3x_autocont_timer_polls--;
                if (g3x_autocont_timer_polls > 0U)
                {
                    break;
                }
            }
            g3x_autocont_state = G3X_AUTOCONT_PRESSING;
            g3x_autocont_timer_polls = G3X_AUTOCONT_PRESS_POLLS;
            g3x_autocont_assert_synth_press();
            break;
        }

        case G3X_AUTOCONT_PRESSING:
        {
            /* Physical cancellation wins races with an in-progress synthetic pulse */
            if (phys_video_pressed)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                break;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled &&
                (cur_state == G3X_MOVIE_STATE_IDLE || cur_state == G3X_MOVIE_STATE_RECORDING))
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
            if (!g3x_autocont_attempt_admitted ||
                g3x_autocont_session_restarts_used == 0U ||
                g3x_autocont_session_restarts_used > g3x_autocont_restart_budget)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                break;
            }
#endif
            if (cur_state != G3X_MOVIE_STATE_IDLE && cur_state != G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
                break;
            }
            if (g3x_autocont_timer_polls > 0U)
            {
                g3x_autocont_timer_polls--;
                if (g3x_autocont_timer_polls > 0U)
                {
                    g3x_autocont_assert_synth_press();
                    break;
                }
            }
            g3x_autocont_release_synth_input();
            g3x_autocont_state = G3X_AUTOCONT_RELEASING;
            g3x_autocont_timer_polls = G3X_AUTOCONT_RELEASE_POLLS;
            break;
        }

        case G3X_AUTOCONT_RELEASING:
        {
            g3x_autocont_release_synth_input();
            if (phys_video_pressed)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                break;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled &&
                (cur_state == G3X_MOVIE_STATE_IDLE || cur_state == G3X_MOVIE_STATE_RECORDING))
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
            if (!g3x_autocont_attempt_admitted ||
                g3x_autocont_session_restarts_used == 0U ||
                g3x_autocont_session_restarts_used > g3x_autocont_restart_budget)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                break;
            }
#endif
            if (cur_state != G3X_MOVIE_STATE_IDLE && cur_state != G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
                break;
            }
            if (g3x_autocont_timer_polls > 0U)
            {
                g3x_autocont_timer_polls--;
                if (g3x_autocont_timer_polls > 0U)
                {
                    break;
                }
            }
            if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_enter_confirmed_recording();
            }
            else
            {
                g3x_autocont_state = G3X_AUTOCONT_WAIT_CONFIRM;
                g3x_autocont_timer_polls = G3X_AUTOCONT_CONFIRM_POLLS;
            }
            break;
        }

        case G3X_AUTOCONT_WAIT_CONFIRM:
        {
            g3x_autocont_release_synth_input();
            if (phys_video_pressed)
            {
                g3x_autocont_disarm_with_reason(1, G3X_AUTOCONT_REASON_PHYS_STOP, 0);
                break;
            }
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
            if (g3x_autocont_session_cancelled &&
                (cur_state == G3X_MOVIE_STATE_RECORDING ||
                 (cur_state == G3X_MOVIE_STATE_IDLE && g3x_autocont_timer_polls > 1U)))
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_SESSION_CANCEL, 0);
                break;
            }
#endif
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
            if (!g3x_autocont_attempt_admitted ||
                g3x_autocont_session_restarts_used == 0U ||
                g3x_autocont_session_restarts_used > g3x_autocont_restart_budget)
            {
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_NONE, 0);
                break;
            }
#endif
            if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_enter_confirmed_recording();
                break;
            }
            if (cur_state == G3X_MOVIE_STATE_IDLE)
            {
                if (g3x_autocont_timer_polls > 0U)
                {
                    g3x_autocont_timer_polls--;
                    if (g3x_autocont_timer_polls > 0U)
                    {
                        break;
                    }
                }
                /* Confirmation timeout: disarm with TIMEOUT without retry */
                g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_TIMEOUT, 1);
                break;
            }
            /* Unexpected non-IDLE/non-RECORDING state: disarm with INVALID_STATE without retry */
            g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
            break;
        }

        default:
        {
            g3x_autocont_disarm_with_reason(0, G3X_AUTOCONT_REASON_INVALID_STATE, 1);
            break;
        }
    }

#if defined(G3X_MOVIE_STANDALONE) && (G3X_MOVIE_STANDALONE == 1)
    if ((pre_poll_state != G3X_AUTOCONT_DISARMED &&
         g3x_autocont_state == G3X_AUTOCONT_DISARMED) ||
        g3x_autocont_cancel_latched)
    {
#if defined(G3X_MOVIE_SCREEN_OFF) && (G3X_MOVIE_SCREEN_OFF == 1)
        g3x_autocont_confirmed_idle_ready = 0;
        g3x_autocont_restore_backlight(1);
#endif
        g3x_autocont_prev_rec_state = -1;
    }
    else
    {
        g3x_autocont_prev_rec_state = cur_state;
    }
#else
    g3x_autocont_prev_rec_state = cur_state;
#endif
}

#endif /* G3X_MOVIE_AUTOCONT == 1 */
