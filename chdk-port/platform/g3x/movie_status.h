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

#endif /* G3X_MOVIE_STATUS == 1 */

#endif /* G3X_MOVIE_STATUS_H */
