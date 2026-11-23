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

