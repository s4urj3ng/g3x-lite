#ifndef G3X_MOVIE_STATUS_H
#define G3X_MOVIE_STATUS_H

#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
#if !defined(G3X_MOVIE_RESTART_BUDGET) || (G3X_MOVIE_RESTART_BUDGET != 1) || \
    !defined(G3X_MOVIE_AUTOCONT_UI) || (G3X_MOVIE_AUTOCONT_UI != 1) || \
    !defined(G3X_MOVIE_AUTOCONT) || (G3X_MOVIE_AUTOCONT != 1) || \
    !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1) || \
    !defined(G3X_GUI_MENU) || (G3X_GUI_MENU != 1) || \
    !defined(G3X_GUI_SYNC) || (G3X_GUI_SYNC != 1) || \
    !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1) || \
    !defined(G3X_GUI_SHADOW2) || (G3X_GUI_SHADOW2 != 1)
#error G3X_MOVIE_SESSION_CANCEL=1 requires G3X_MOVIE_RESTART_BUDGET=1 G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_SESSION_CANCEL=1 is incompatible with G3X_CONF_SAVE=1
#endif
#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)
#error G3X_MOVIE_SESSION_CANCEL=1 is incompatible with FULL_HOOKS=1
#endif
#endif

#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
#if !defined(G3X_MOVIE_AUTOCONT_UI) || (G3X_MOVIE_AUTOCONT_UI != 1) || \
    !defined(G3X_MOVIE_AUTOCONT) || (G3X_MOVIE_AUTOCONT != 1) || \
    !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1) || \
    !defined(G3X_GUI_MENU) || (G3X_GUI_MENU != 1) || \
    !defined(G3X_GUI_SYNC) || (G3X_GUI_SYNC != 1) || \
    !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1) || \
    !defined(G3X_GUI_SHADOW2) || (G3X_GUI_SHADOW2 != 1)
#error G3X_MOVIE_RESTART_BUDGET=1 requires G3X_MOVIE_AUTOCONT_UI=1 G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_RESTART_BUDGET=1 is incompatible with G3X_CONF_SAVE=1
#endif
#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)
#error G3X_MOVIE_RESTART_BUDGET=1 is incompatible with FULL_HOOKS=1
#endif
#endif

#if defined(G3X_MOVIE_AUTOCONT_UI) && (G3X_MOVIE_AUTOCONT_UI == 1)
#if !defined(G3X_MOVIE_AUTOCONT) || (G3X_MOVIE_AUTOCONT != 1) || \
    !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1) || \
    !defined(G3X_GUI_MENU) || (G3X_GUI_MENU != 1) || \
    !defined(G3X_GUI_SYNC) || (G3X_GUI_SYNC != 1) || \
    !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1) || \
    !defined(G3X_GUI_NOOVERDRAW) || (G3X_GUI_NOOVERDRAW != 1) || \
    !defined(G3X_KBD_CHECK) || (G3X_KBD_CHECK != 1) || \
    !defined(G3X_GUI_DIAG) || (G3X_GUI_DIAG != 1) || \
    !defined(G3X_GUI_SHADOW2) || (G3X_GUI_SHADOW2 != 1)
#error G3X_MOVIE_AUTOCONT_UI=1 requires G3X_MOVIE_AUTOCONT=1 G3X_MOVIE_STATUS=1 G3X_GUI_MENU=1 G3X_GUI_SYNC=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_AUTOCONT_UI=1 is incompatible with G3X_CONF_SAVE=1
#endif
#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)
#error G3X_MOVIE_AUTOCONT_UI=1 is incompatible with FULL_HOOKS=1
#endif
#endif

#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)
#if !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1)
#error G3X_MOVIE_AUTOCONT=1 requires G3X_MOVIE_STATUS=1
#endif
#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)
#if !defined(G3X_MOVIE_AUTOCONT_UI) || (G3X_MOVIE_AUTOCONT_UI != 1)
#error Combining G3X_MOVIE_NOLIMIT=1 and G3X_MOVIE_AUTOCONT=1 requires G3X_MOVIE_AUTOCONT_UI=1
#endif
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_AUTOCONT=1 is incompatible with G3X_CONF_SAVE=1
#endif
#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)
#error G3X_MOVIE_AUTOCONT=1 is incompatible with FULL_HOOKS=1
#endif
#endif

#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)
#if !defined(G3X_MOVIE_STATUS) || (G3X_MOVIE_STATUS != 1)
#error G3X_MOVIE_NOLIMIT=1 requires G3X_MOVIE_STATUS=1
#endif
#if defined(G3X_CONF_SAVE) && (G3X_CONF_SAVE == 1)
#error G3X_MOVIE_NOLIMIT=1 is incompatible with G3X_CONF_SAVE=1
#endif
#if defined(FULL_HOOKS) && (FULL_HOOKS == 1)
#error Movie time-limit defeat is incompatible with FULL_HOOKS=1
#endif
#endif

#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)

/* Address of GM1.10C MovieRecorder recording state (mr_rec_state).
 * PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK: mr_rec_state @ 0x0000C0C8 (*(0x0000C078 + 0x50)), verified @ 0xFC09B416
 */
#define G3X_MOVIE_STATE_ADDR 0x0000C0C8

#define G3X_MOVIE_STATE_IDLE              0
#define G3X_MOVIE_STATE_RECORDING         1
#define G3X_MOVIE_STATE_STOPPING          2
#define G3X_MOVIE_STATE_STOPPING_PREREC   3
#define G3X_MOVIE_STATE_SEGMENT_SPLIT     4

/* Read-only accessor for the firmware movie-state variable (mr_rec_state).
 * Strictly read-only; performs no stores and no firmware modifications.
 */
int g3x_get_movie_status(void);

/* Diag line status marker helper:
 * Returns "IDLE" if state is 0 (idle)
 * Returns "REC"  if state is 1 (recording)
 * Returns "?"    if state is unavailable or unexpected (2, 3, 4, etc.)
 */
static inline const char *g3x_movie_status_str(void)
{
    int st = g3x_get_movie_status();
    if (st == G3X_MOVIE_STATE_IDLE)
        return "IDLE";
    if (st == G3X_MOVIE_STATE_RECORDING)
        return "REC";
    return "?";
}

#if defined(G3X_MOVIE_NOLIMIT) && (G3X_MOVIE_NOLIMIT == 1)

/* PORT-56: Movie Time-Limit RAM addresses & evidence classifications:
 * -------------------------------------------------------------------------------------------------------------------
 * Address    | Variable       | Evidence Classification | Manifest ID                             | Access Rule
 * -------------------------------------------------------------------------------------------------------------------
 * 0x0000C274 | mr_max_frames  | ROM_VERIFIED            | PORT56-ROM-SETUP-MAX-FRAMES-STORE,      | Write 0xFFFFFFFF
 *            |                |                         | PORT56-ROM-CHECK-FRAME-LIMIT            | ONLY while recording
 * 0x0000C278 | mr_cur_frames  | ROM_VERIFIED            | PORT56-ROM-CHECK-FRAME-LIMIT            | Strictly READ-ONLY
 * 0x0000C0E4 | mr_warn_sec    | ROM_VERIFIED            | PORT56-ROM-WARN-SEC-CHECK,              | DO NOT WRITE
 *            |                |                         | PORT56-ROM-SETUP-MAX-FRAMES-STORE       | (UI warning only)
 * 0x0000C0C0 | mr_stop_reason | ROM_VERIFIED            | PORT56-ROM-CHECK-FRAME-LIMIT,           | DO NOT WRITE
 *            |                |                         | PORT56-ROM-CHECK-SIZE-LIMIT             | (Stop reason code)
 * 0x0000C0C8 | mr_rec_state   | ROM_VERIFIED            | PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK| Strictly READ-ONLY
 * -------------------------------------------------------------------------------------------------------------------
 */
#define G3X_MR_MAX_FRAMES_ADDR  0x0000C274
#define G3X_MR_CUR_FRAMES_ADDR  0x0000C278
#define G3X_MR_WARN_SEC_ADDR    0x0000C0E4
#define G3X_MR_STOP_REASON_ADDR 0x0000C0C0

#define G3X_MOVIE_NOLIMIT_TARGET 0xFFFFFFFFU

/* Poll and enforce movie time limit defeat.
 * Timing rule: MOV:REC does NOT mean limit setup has finished (docs/VIDEO001_RECORDING_LIMITS.md:183).
 * Setup runs again on every record start (BL 0xFC09A97C).
 * On every loop tick while recording (g3x_get_movie_status() == 1), if the value at
 * 0x0000C274 is nonzero and not already 0xFFFFFFFF, overwrite it with 0xFFFFFFFF.
 * The check in ROM is an unsigned blo at 0xFC098B22.
 * Do nothing when not recording.
 */
void g3x_movie_nolimit_poll(void);

/* Read-only accessors for frame counters */
unsigned int g3x_get_movie_max_frames(void);
unsigned int g3x_get_movie_cur_frames(void);

/* Diag line status helper:
 * Returns "OFF" if patched value (0xFFFFFFFF) is in place while recording (LIM:OFF)
 * Returns "ON"  if stock value (nonzero != 0xFFFFFFFF) is seen while recording (LIM:ON)
 * Returns "?"   otherwise (LIM:?)
 */
static inline const char *g3x_movie_nolimit_status_str(void)
{
    if (g3x_get_movie_status() == G3X_MOVIE_STATE_RECORDING)
    {
        unsigned int val = g3x_get_movie_max_frames();
        if (val == G3X_MOVIE_NOLIMIT_TARGET)
            return "OFF";
        if (val != 0)
            return "ON";
    }
    return "?";
}

static inline const char *g3x_movie_nolimit_diag_str(void)
{
    if (g3x_get_movie_status() == G3X_MOVIE_STATE_RECORDING)
    {
        unsigned int val = g3x_get_movie_max_frames();
        if (val == G3X_MOVIE_NOLIMIT_TARGET)
            return "LIM:OFF";
        if (val != 0)
            return "LIM:ON";
    }
    return "LIM:?";
}

#endif /* G3X_MOVIE_NOLIMIT == 1 */

#if defined(G3X_MOVIE_AUTOCONT) && (G3X_MOVIE_AUTOCONT == 1)

/* PORT-57 / PORT-58: Movie Auto-Continuation RAM addresses & evidence classifications:
 * -------------------------------------------------------------------------------------------------------------------
 * Address    | Variable              | Width    | Evidence Classification | Manifest / Source ID            | Access
 * -------------------------------------------------------------------------------------------------------------------
 * 0x0000C0C8 | mr_rec_state          | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW, | Read-Only
 *            |                       |          |                         | PORT55-ROM-GET-ELAPSED-SECONDS  |
 * 0x0000C0C0 | mr_stop_reason        | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C278 | mr_cur_frames         | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C274 | mr_max_frames         | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C078 | mr_segment_index      | uint8_t  | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C0D4 | mr_fs_cluster_size    | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C0D8 | mr_fs_reserve_size    | uint32_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C290 | mr_avail_space_bytes  | uint64_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C298 | mr_stream_bytes       | uint64_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C2A0 | mr_projected_size     | uint64_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x0000C2A8 | mr_projected_base_off | uint64_t | ROM_VERIFIED            | PORT57-ROM-CHECK-LIMITS-WINDOW  | Read-Only
 * 0x00040DAC | physw_status[0]       | uint32_t | FINSIG / ROM_VERIFIED   | stubs_entry.S:173 / PORT34-ROM  | R/W bit 3
 * -------------------------------------------------------------------------------------------------------------------
 */
#ifndef G3X_MR_MAX_FRAMES_ADDR
#define G3X_MR_MAX_FRAMES_ADDR         0x0000C274
#define G3X_MR_CUR_FRAMES_ADDR         0x0000C278
#define G3X_MR_WARN_SEC_ADDR           0x0000C0E4
#define G3X_MR_STOP_REASON_ADDR        0x0000C0C0
#endif

#define G3X_MR_SEGMENT_INDEX_ADDR      0x0000C078
#define G3X_MR_FS_CLUSTER_SIZE_ADDR    0x0000C0D4
#define G3X_MR_FS_RESERVE_SIZE_ADDR    0x0000C0D8
#define G3X_MR_AVAIL_SPACE_ADDR        0x0000C290
#define G3X_MR_STREAM_BYTES_ADDR       0x0000C298
#define G3X_MR_PROJECTED_SIZE_ADDR     0x0000C2A0
#define G3X_MR_PROJECTED_BASE_OFF_ADDR 0x0000C2A8

/* Stop reason encodings at 0x0000C0C0 (PORT57-ROM-CHECK-LIMITS-WINDOW) */
#define G3X_MR_STOP_REASON_USER        0U
#define G3X_MR_STOP_REASON_OVERFLOW    1U
#define G3X_MR_STOP_REASON_SPACE_FULL  2U
#define G3X_MR_STOP_REASON_SIZE_LIMIT  3U
#define G3X_MR_STOP_REASON_FRAME_LIMIT 4U

/* KEY_VIDEO physical switch bit in word 0 (physw_status[0] / kbd_new_state[0] / kbd_mod_state[0]) */
#define G3X_KEY_VIDEO_BIT              0x00000008U

/* Timing bounds (1 poll = 10 ms at physw_sleep_delay @ 0x000082C4) */
#define G3X_AUTOCONT_POLL_MS           10U
#define G3X_AUTOCONT_MAX_STOP_POLLS    500U /* 5.0 s max wait for RECORDING -> STOPPING -> IDLE (0) */
#define G3X_AUTOCONT_SETTLE_POLLS      50U  /* 500 ms post-IDLE settle delay before synthetic KEY_VIDEO press */
#define G3X_AUTOCONT_PRESS_POLLS       6U   /* 60 ms simulated KEY_VIDEO hold (CAM_KEY_PRESS_DELAY = 60) */
#define G3X_AUTOCONT_RELEASE_POLLS     6U   /* 60 ms simulated KEY_VIDEO release cooldown (CAM_KEY_RELEASE_DELAY = 60) */
#define G3X_AUTOCONT_CONFIRM_POLLS     200U /* 2.0 s max wait for mr_rec_state == 1 confirmation after pulse */
#define G3X_AUTOCONT_START_HOLD_POLLS  50U  /* 500 ms max carry-over of initial start button press from IDLE */

/* Explicit nonblocking session state machine states */
typedef enum {
    G3X_AUTOCONT_DISARMED     = 0,
    G3X_AUTOCONT_RECORDING    = 1,
    G3X_AUTOCONT_WAIT_IDLE    = 2,
    G3X_AUTOCONT_SETTLE       = 3,
    G3X_AUTOCONT_PRESSING     = 4,
    G3X_AUTOCONT_RELEASING    = 5,
    G3X_AUTOCONT_WAIT_CONFIRM = 6
} g3x_movie_autocont_state_t;

/* Explicit disarm / status reason metadata (PORT-58) */
typedef enum {
    G3X_AUTOCONT_REASON_NONE          = 0, /* Default at boot or active/ready without disarm event */
    G3X_AUTOCONT_REASON_USER_OFF      = 1, /* Explicitly disabled by user */
    G3X_AUTOCONT_REASON_PHYS_STOP     = 2, /* Terminal session stop/cancel via physical KEY_VIDEO */
    G3X_AUTOCONT_REASON_PLAYBACK      = 3, /* Disarmed on entering playback mode (mode_play != 0) */
    G3X_AUTOCONT_REASON_INVALID_STATE = 4, /* Disarmed on invalid or unexpected mr_rec_state */
    G3X_AUTOCONT_REASON_STOP_FAULT    = 5, /* Disarmed on ineligible, stale, or error stop reason */
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
    G3X_AUTOCONT_REASON_TIMEOUT       = 6, /* Disarmed on WAIT_IDLE or WAIT_CONFIRM timeout */
    G3X_AUTOCONT_REASON_SESSION_CANCEL = 7 /* Active/pending session restarts cancelled via volatile GUI */
#endif
#if !defined(G3X_MOVIE_SESSION_CANCEL) || (G3X_MOVIE_SESSION_CANCEL != 1)
    G3X_AUTOCONT_REASON_TIMEOUT       = 6  /* Disarmed on WAIT_IDLE or WAIT_CONFIRM timeout */
#endif
} g3x_movie_autocont_reason_t;

/* Read-only accessors for MovieRecorder limit and stop attribution fields */
#if !defined(G3X_MOVIE_NOLIMIT) || (G3X_MOVIE_NOLIMIT != 1)
unsigned int g3x_get_movie_max_frames(void);
unsigned int g3x_get_movie_cur_frames(void);
#endif
unsigned int g3x_get_movie_stop_reason(void);
unsigned int g3x_get_movie_segment_index(void);
unsigned int g3x_get_movie_fs_reserve_size(void);
unsigned long long g3x_get_movie_avail_space(void);
unsigned long long g3x_get_movie_stream_bytes(void);
unsigned long long g3x_get_movie_projected_size(void);
unsigned long long g3x_get_movie_projected_base_offset(void);

/* Session state machine entry points & observability accessors */
void g3x_movie_autocont_poll(void);
void g3x_movie_autocont_reset(void);
int g3x_movie_autocont_get_state(void);
unsigned int g3x_movie_autocont_get_timer_polls(void);
int g3x_movie_autocont_is_synth_owned(void);
int g3x_movie_autocont_is_cancel_latched(void);
unsigned int g3x_movie_autocont_get_last_stop_reason(void);
unsigned int g3x_movie_autocont_get_restart_count(void);

/* Volatile user control & status projections (PORT-58) */
int g3x_movie_autocont_is_enabled(void);
int g3x_movie_autocont_can_enable(void);
int g3x_movie_autocont_set_enabled(int enable);
int g3x_movie_autocont_get_disarm_reason(void);
int g3x_movie_autocont_is_faulted(void);
const char *g3x_movie_autocont_reason_str(void);
const char *g3x_movie_autocont_ui_status_str(void);
const char *g3x_movie_autocont_menu_str(void);
const char *g3x_movie_autocont_menu_change(int change, int arg);
void g3x_movie_autocont_menu_cb(void);
int *g3x_movie_autocont_get_menu_bool_ptr(void);
#if defined(G3X_MOVIE_RESTART_BUDGET) && (G3X_MOVIE_RESTART_BUDGET == 1)
/* PORT-60: Opt-in volatile finite session restart budget (allowances 1, 2, or 3; default 1) */
#define G3X_AUTOCONT_BUDGET_MIN     1U
#define G3X_AUTOCONT_BUDGET_MAX     3U
#define G3X_AUTOCONT_BUDGET_DEFAULT 1U

unsigned int g3x_movie_autocont_get_restart_budget(void);
int g3x_movie_autocont_set_restart_budget(unsigned int budget);
unsigned int g3x_movie_autocont_get_restarts_remaining(void);
unsigned int g3x_movie_autocont_get_session_restarts_used(void);
int g3x_movie_autocont_is_attempt_admitted(void);
const char *g3x_movie_autocont_budget_menu_str(void);
const char *g3x_movie_autocont_budget_menu_change(int change, int arg);
#endif
#if defined(G3X_MOVIE_SESSION_CANCEL) && (G3X_MOVIE_SESSION_CANCEL == 1)
/* PORT-61: Opt-in volatile active-session cancellation ("Cancel further restarts") */
int g3x_movie_autocont_can_cancel_session(void);
int g3x_movie_autocont_cancel_session(void);
int g3x_movie_autocont_is_session_cancelled(void);
const char *g3x_movie_autocont_cancel_menu_str(void);
const char *g3x_movie_autocont_cancel_menu_change(int change, int arg);
#endif

static inline const char *g3x_movie_autocont_status_str(void)
{
    return g3x_movie_autocont_ui_status_str();
}

#endif /* G3X_MOVIE_AUTOCONT == 1 */

#endif /* G3X_MOVIE_STATUS == 1 */

#endif /* G3X_MOVIE_STATUS_H */
