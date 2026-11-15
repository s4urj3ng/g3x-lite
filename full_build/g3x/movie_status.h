#ifndef G3X_MOVIE_STATUS_H
#define G3X_MOVIE_STATUS_H

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
 * Strictly read-only; performs no stores and no firmware writes.
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

#endif /* G3X_MOVIE_STATUS == 1 */

#endif /* G3X_MOVIE_STATUS_H */
