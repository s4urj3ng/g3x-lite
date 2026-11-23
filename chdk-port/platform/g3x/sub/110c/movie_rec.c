#include "conf.h"
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

/* PORT-57: Gated Movie Automatic Continuation (G3X_MOVIE_AUTOCONT=1).
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

/* Nonblocking session state machine variables */
static volatile int g3x_autocont_state = G3X_AUTOCONT_DISARMED;
static volatile unsigned int g3x_autocont_timer_polls = 0U;
static volatile int g3x_autocont_prev_rec_state = -1;
static volatile int g3x_autocont_saw_boot_idle = 0;
static volatile int g3x_autocont_idle_start_press_seen = 0;
static volatile int g3x_autocont_cancel_latched = 0;
static volatile int g3x_autocont_held_from_idle = 0;
static volatile unsigned int g3x_autocont_start_hold_polls = 0U;
static volatile int g3x_autocont_saw_frames_in_bounds = 0;
static volatile int g3x_autocont_saw_size_in_bounds = 0;
static volatile int g3x_autocont_synth_owned = 0;
static volatile unsigned int g3x_autocont_last_stop_reason = 0U;
static volatile unsigned int g3x_autocont_restart_count = 0U;

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

static void g3x_autocont_disarm(int latch_cancel)
{
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_timer_polls = 0U;
    g3x_autocont_state = G3X_AUTOCONT_DISARMED;
    if (latch_cancel)
    {
        g3x_autocont_cancel_latched = 1;
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
    g3x_autocont_state = G3X_AUTOCONT_RECORDING;
    g3x_autocont_restart_count++;
    g3x_autocont_sample_recording_metrics();
}

void __attribute__((used)) g3x_movie_autocont_reset(void)
{
    g3x_autocont_release_synth_input();
    g3x_autocont_reset_session_metrics();
    g3x_autocont_state = G3X_AUTOCONT_DISARMED;
    g3x_autocont_timer_polls = 0U;
    g3x_autocont_prev_rec_state = -1;
    g3x_autocont_saw_boot_idle = 0;
    g3x_autocont_idle_start_press_seen = 0;
    g3x_autocont_cancel_latched = 0;
    g3x_autocont_last_stop_reason = 0U;
    g3x_autocont_restart_count = 0U;
    g3x_autocont_last_stop_cur_frames = 0U;
    g3x_autocont_last_stop_stream_bytes = 0ULL;
    g3x_autocont_last_stop_proj_total = 0ULL;
}

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

void __attribute__((used)) g3x_movie_autocont_poll(void)
{
    int cur_state = g3x_get_movie_status();
    int prev_state = g3x_autocont_prev_rec_state;
    int phys_video_pressed = (((unsigned int)kbd_new_state[0] & G3X_KEY_VIDEO_BIT) == 0U) ? 1 : 0;

    /* Disarm and release any synthetic key immediately in playback mode or on unsupported movie state */
    if (camera_info.state.mode_play != 0 ||
        cur_state < G3X_MOVIE_STATE_IDLE ||
        cur_state > G3X_MOVIE_STATE_SEGMENT_SPLIT)
    {
        g3x_autocont_disarm(phys_video_pressed);
        g3x_autocont_prev_rec_state = cur_state;
        return;
    }

    switch (g3x_autocont_state)
    {
        case G3X_AUTOCONT_DISARMED:
        {
            g3x_autocont_release_synth_input();
            if (cur_state == G3X_MOVIE_STATE_IDLE)
            {
                g3x_autocont_saw_boot_idle = 1;
                if (phys_video_pressed)
                {
                    if (!g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_idle_start_press_seen = 1;
                    }
                }
                else
                {
                    if (g3x_autocont_cancel_latched)
                    {
                        g3x_autocont_cancel_latched = 0;
                    }
                }
            }
            else if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                /* Arm only on an observed IDLE (0) -> RECORDING (1) start during this boot when not cancelled */
                if (g3x_autocont_saw_boot_idle &&
                    prev_state == G3X_MOVIE_STATE_IDLE &&
                    !g3x_autocont_cancel_latched &&
                    (!phys_video_pressed || g3x_autocont_idle_start_press_seen))
                {
                    g3x_autocont_reset_session_metrics();
                    g3x_autocont_state = G3X_AUTOCONT_RECORDING;
                    g3x_autocont_held_from_idle = (phys_video_pressed && g3x_autocont_idle_start_press_seen) ? 1 : 0;
                    g3x_autocont_start_hold_polls = g3x_autocont_held_from_idle ? G3X_AUTOCONT_START_HOLD_POLLS : 0U;
                    g3x_autocont_idle_start_press_seen = 0;
                    g3x_autocont_sample_recording_metrics();
                }
                else
                {
                    g3x_autocont_idle_start_press_seen = 0;
                    if (phys_video_pressed)
                    {
                        g3x_autocont_cancel_latched = 1;
                    }
                }
            }
            else
            {
                g3x_autocont_idle_start_press_seen = 0;
                if (phys_video_pressed)
                {
                    g3x_autocont_cancel_latched = 1;
                }
            }
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
                    g3x_autocont_disarm(1);
                    break;
                }
                g3x_autocont_start_hold_polls--;
            }

            if (cur_state == G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_sample_recording_metrics();
            }
            else
            {
                unsigned int attributed_reason = 0U;
                int eligible = g3x_autocont_check_eligible_stop(&attributed_reason);
                g3x_autocont_snapshot_stop_counters();
                if (!eligible)
                {
                    g3x_autocont_disarm(0);
                    break;
                }
                g3x_autocont_last_stop_reason = attributed_reason;
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
                g3x_autocont_disarm(1);
                break;
            }
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
            }
            g3x_autocont_disarm(0);
            break;
        }

        case G3X_AUTOCONT_SETTLE:
        {
            if (phys_video_pressed)
            {
                g3x_autocont_disarm(1);
                break;
            }
            if (cur_state != G3X_MOVIE_STATE_IDLE)
            {
                g3x_autocont_disarm(0);
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
                g3x_autocont_disarm(1);
                break;
            }
            if (cur_state != G3X_MOVIE_STATE_IDLE && cur_state != G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_disarm(0);
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
                g3x_autocont_disarm(1);
                break;
            }
            if (cur_state != G3X_MOVIE_STATE_IDLE && cur_state != G3X_MOVIE_STATE_RECORDING)
            {
                g3x_autocont_disarm(0);
                break;
            }
            kbd_key_release(KEY_VIDEO);
            physw_status[0] |= (long)G3X_KEY_VIDEO_BIT;
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
                g3x_autocont_disarm(1);
                break;
            }
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
            }
            /* Confirmation timeout or unexpected non-IDLE/non-RECORDING state: disarm without retry */
            g3x_autocont_disarm(0);
            break;
        }

        default:
        {
            g3x_autocont_disarm(0);
            break;
        }
    }

    g3x_autocont_prev_rec_state = cur_state;
}

#endif /* G3X_MOVIE_AUTOCONT == 1 */
