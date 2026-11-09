/*
 * PORT-39: Opt-in G3X_SHORTPRESS=1 candidate
 * Target: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
 *
 * Adapted DIGIC 6 Sibling Short-Press Power-On Handling:
 * - g7x: chdk-port/platform/g7x/kbd.c:48, 50 (Playback / Power physw bits);
 *        chdk-port/platform/g7x/kbd.c:70-82 (PhySw polling task loop)
 * - g5x: chdk-port/platform/g5x/kbd.c:118-126 (physw override);
 *        chdk-port/platform/g5x/sub/100c/boot.c:172-182 (start-mode write);
 *        chdk-port/platform/g5x/sub/100c/boot.c:411-420 (power-cut bypass sub_fc0ecf20_my);
 *        chdk-port/platform/g5x/sub/100c/boot.c:479-506 (taskcreate_physw stack 0x2000)
 *
 * Timing reference:
 * - Owner trial observation (PORT-38, 2026-11): held press of ~5 s (until LED ladder
 *   blinks finish) is sufficient for camera to power on into the CHDK candidate.
 * - At physw_sleep_delay = 10 ms (0x000082C4), 700 polls = 7000 ms (7.0 s),
 *   covering the ~5 s LED ladder window with 2.0 s (40%) safety margin before releasing
 *   the override so a normal Power button press can turn off the camera.
 */

#ifndef SHORTPRESS_CANDIDATE_H
#define SHORTPRESS_CANDIDATE_H

#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)

#include "lolevel.h"
#include "platform.h"
#include "keyboard.h"
#include "kbd_common.h"
#include "conf.h"

/* Enforce architectural invariant: G3X_SHORTPRESS implies G3X_RESIDENT=1 */
#if !defined(G3X_RESIDENT) || (G3X_RESIDENT != 1)
#error "G3X_SHORTPRESS=1 requires G3X_RESIDENT=1"
#endif

/* Override duration covering ~5 s ladder window with 2 s margin [INFERRED] */
#define G3X_SHORTPRESS_HOLD_POLLS   700     /* 700 polls @ 10 ms = 7.0 s (~5 s ladder + 2.0 s margin) */

/* Addresses and bit constants */
#define G3X_ADDR_STARTCAUSE         0x00009BD0  /* *(0x9BC4 + 12): startup cause word [VERIFIED] */
#define G3X_STARTCAUSE_POWER        0x00080000  /* Power button start cause [VERIFIED] */
#define G3X_STARTCAUSE_PLAYBACK     0x00100000  /* Playback button start cause [VERIFIED] */

#define G3X_KEY_PLAYBACK_BIT        0x00010000  /* Word 0, bit 16: Playback button [FINSIG] */
#define G3X_KEY_POWER_BIT           0x00020000  /* Word 0, bit 17: Power button [FINSIG] */

extern long physw_status[3];

static inline void g3x_shortpress_read_keys(void)
{
    static int pwr_hold_count = G3X_SHORTPRESS_HOLD_POLLS;

    kbd_update_key_state();
    kbd_update_physw_bits();

    if (pwr_hold_count > 0) {
        pwr_hold_count--;

        /* Active-low key logic: clear bit (&= ~mask) to fake button held.
         * Distinguish Playback start vs Power start using start-cause word at 0x00009BD0:
         * If Playback start was recorded (0x00100000), fake Playback held (bit 16).
         * Otherwise (Power start 0x00080000, unrecorded 0, or default), fake Power held (bit 17)
         * and ensure start-cause is populated with Power start cause.
         */
        volatile unsigned int *start_cause = (volatile unsigned int *)G3X_ADDR_STARTCAUSE;
        if (*start_cause & G3X_STARTCAUSE_PLAYBACK) {
            physw_status[0] &= ~G3X_KEY_PLAYBACK_BIT;
        } else {
            if (*start_cause == 0) {
                *start_cause = G3X_STARTCAUSE_POWER;
            }
            physw_status[0] &= ~G3X_KEY_POWER_BIT;
        }
    }
}

#endif /* G3X_SHORTPRESS */

#endif /* SHORTPRESS_CANDIDATE_H */
