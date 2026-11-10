#include "lolevel.h"
#include "platform.h"
#include "core.h"
#include "keyboard.h"

extern long link_bss_start;
extern long link_bss_end;
extern void boot();

void startup() {
    long *bss = &link_bss_start;
    // sanity check
    if ((long)&link_bss_end > (MEMISOSTART + MEMISOSIZE)) {
        started();
        shutdown();
    }
    // initialize .bss segment
    while (bss < &link_bss_end)
        *bss++ = 0;
    boot();
}

#define NUM_FL      201
#define NUM_DATA    1   // 1 word each entry (zoom focus length in um)
extern int focus_len_table[NUM_FL * NUM_DATA];

// Conversion factor lens FL --> 35mm equiv
// lens      35mm     CF
// ----      ----     --
// 8.8       24       (24.0/8.8  ) * 100 = 273  (min FL)
// 220.0     600      (600.0/220.0) * 100 = 273  (max FL)
#define CF_EFL      273
#define CF_EFL_DIV  100

const int zoom_points = NUM_FL;

int get_effective_focal_length(int zp) {
    return (CF_EFL * get_focal_length(zp)) / CF_EFL_DIV;
}

int get_focal_length(int zp) {
    if (zp < 0) zp = 0;
    else if (zp >= NUM_FL) zp = NUM_FL - 1;
    return focus_len_table[zp * NUM_DATA];
}

int get_zoom_x(int zp) {
    return get_focal_length(zp) * 10 / focus_len_table[0];
}

long get_vbatt_min()
{
    return 6800; // NB-10L 7.4V pack nominal, min ~6.8V
}

long get_vbatt_max()
{
    return 8400; // NB-10L 7.4V pack fully charged ~8.4V
}

int screen_opened(void) {
    return (physw_status[0] & 0x00002000);
}

int screen_rotated(void) {
    return !(physw_status[0] & 0x10000000);
}
