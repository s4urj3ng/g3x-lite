// PORT-41: movie_rec.c adapted from sibling g7x (sub/100d: movie_rec.c)
// Sibling citation: chdk-port/platform/g7x/sub/100d/movie_rec.c:1-20
// Task hook address task_MovieRecord cannot be confirmed from FINSIG (reference/finsig_gm110c/stubs_entry.S,
// funcs_by_name.csv) or existing VERIFIED records for GM1.10C.
// Hook remains disabled (task left stock). TODO: Establish GM1.10C task_MovieRecord entry.

#include "conf.h"

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

#if defined(__arm__) || defined(__thumb__)

/* PORT56-ROM-CHECK-FRAME-LIMIT / PORT56-ROM-SETUP-MAX-FRAMES-STORE:
 * mr_max_frames @ 0x0000C274 (ROM_VERIFIED, read-only accessor)
 */
unsigned int __attribute__((used)) g3x_get_movie_max_frames(void)
{
    return *(volatile const unsigned int *)0x0000C274;
}

/* PORT56-ROM-CHECK-FRAME-LIMIT:
 * mr_cur_frames @ 0x0000C278 (ROM_VERIFIED, strictly read-only)
 */
unsigned int __attribute__((used)) g3x_get_movie_cur_frames(void)
{
    return *(volatile const unsigned int *)0x0000C278;
}

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
