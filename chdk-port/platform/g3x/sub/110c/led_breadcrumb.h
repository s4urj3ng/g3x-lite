/*
 * PORT-23 T2b: LED breadcrumb helpers for Canon PowerShot G3 X (GM1.10C).
 *
 * Hardware facts VERIFIED on camera (owner, 2026-11-01):
 * - MMIO 0xD20B0884 is the green LED register.
 * - Writing 0x004D0002 turns the green LED ON.
 * - Writing 0x004C0003 turns the green LED OFF.
 * - Loader entry prologue at 0x8000 runs.
 * - A 0x06000000 stall and a 0x00600000 stall both ended with the camera dark.
 *
 * Design constraints:
 * - This header defines NO symbols unless LED_BREADCRUMB is defined.
 * - In documented stage builds, delay is 0 (LED turns ON and stays ON).
 * - Optional busy-wait delay is capped at 0x00600000.
 */

#ifndef LED_BREADCRUMB_H
#define LED_BREADCRUMB_H

#if defined(LED_BREADCRUMB)

#define G3X_LED_MMIO_ADDR   0xD20B0884
#define G3X_LED_ON_VAL      0x004D0002
#define G3X_LED_OFF_VAL     0x004C0003

#define G3X_LED_MAX_DELAY   0x00600000

#if defined(LED_BREADCRUMB_DELAY) && (LED_BREADCRUMB_DELAY > 0)
#if (LED_BREADCRUMB_DELAY > G3X_LED_MAX_DELAY)
#error "LED_BREADCRUMB_DELAY exceeds maximum safety cap of 0x00600000"
#endif
#endif

#ifndef _STR
#define __STR(x) #x
#define _STR(x) __STR(x)
#endif

static inline __attribute__((always_inline)) void g3x_breadcrumb_led_on(void)
{
    asm volatile (
        "    ldr     r2, =0xD20B0884\n"
        "    ldr     r3, =0x004D0002\n"
        "    str     r3, [r2]\n"
        "    dsb     sy\n"
#if defined(LED_BREADCRUMB_DELAY) && (LED_BREADCRUMB_DELAY > 0)
        "    ldr     r2, =" _STR(LED_BREADCRUMB_DELAY) "\n"
        "1:\n"
        "    subs    r2, r2, #1\n"
        "    bne     1b\n"
#endif
        :
        :
        : "r2", "r3", "memory"
    );
}

static inline __attribute__((always_inline)) void g3x_breadcrumb_led_off(void)
{
    asm volatile (
        "    ldr     r2, =0xD20B0884\n"
        "    ldr     r3, =0x004C0003\n"
        "    str     r3, [r2]\n"
        "    dsb     sy\n"
        :
        :
        : "r2", "r3", "memory"
    );
}

#endif /* LED_BREADCRUMB */

#if defined(LED_LADDER)

#define G3X_LADDER_MMIO_ADDR   0xD20B0884
#define G3X_LADDER_ON_VAL      0x004D0002
#define G3X_LADDER_OFF_VAL     0x004C0003

// Timing calibration derived from PORT-23 0x00600000 short-delay loop:
// Reference: 0x00600000 (6,291,456 iterations) ~ 100-150 ms (nominal 125 ms) [PORT23_POWER_SUPERVISION.md:245]
//            and ~300 ms conservative upper bound [PORT24_LOADER_TRACE.md:761].
// Loop body: 'subs r2, r2, #1; bne' (identical to PORT-23 stall loop).
// Timing constraints & justified compromise:
// (a) Fast-bound 40 ms ON + 60 ms OFF = 100 ms, which scales 3x to 300 ms at the slow bound (> 200 ms cap).
//     Both targets are mathematically impossible simultaneously under the 200 ms cap.
// (b) Minimum-ON assumption: ON = 0x00134000 (1,261,568 iterations, ~20.05 ms at fast 100ms bound).
//     Perceptual noticeability / human countability on physical camera is UNKNOWN (no optical trials in repo).
// (c) Non-loop overhead [UNKNOWN: no latency evidence in the repo]:
//     The 1.0 ms figure is an ASSUMPTION (~9 instructions + 2 memory barriers: ldr, str, dsb, mov).
// (d) Cap compliance: Loop-only duration at the slow bound is 198.44 ms [INFERRED].
//     Full step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN).
// Maximized OFF gap: OFF = 0x002C4000 (2,899,968 iterations, Thumb-2 modified immediate encodable by mov.w r2, #0x002C4000):
// ON delay:  0x00134000 (1,261,568 iterations) -> ~20.05 ms (fast 100ms) / ~25.07 ms (nom 125ms) / ~60.16 ms (slow 300ms) [INFERRED]
// OFF delay: 0x002C4000 (2,899,968 iterations) -> ~46.09 ms (fast 100ms) / ~57.62 ms (nom 125ms) / ~138.28 ms (slow 300ms) [INFERRED]
// Total loop: 0x003F8000 (4,161,536 iterations) -> ~66.15 ms (fast) / ~82.68 ms (nom) / 198.44 ms (slow) [INFERRED]
// Under the 1.0 ms overhead ASSUMPTION: 198.44 ms + 1.0 ms = 199.44 ms (step < 200 ms at the slow bound IF non-loop overhead < 1.56 ms (UNKNOWN))
#define G3X_LADDER_ON_DELAY    0x00134000
#define G3X_LADDER_OFF_DELAY   0x002C4000

#define LADDER_ASM_PULSE \
    "    ldr     r0, =0xD20B0884\n" \
    "    ldr     r1, =0x004D0002\n" \
    "    str     r1, [r0]\n" \
    "    dsb     sy\n" \
    "    mov.w   r2, #0x00134000\n" \
    "1:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     1b\n" \
    "    ldr     r1, =0x004C0003\n" \
    "    str     r1, [r0]\n" \
    "    dsb     sy\n" \
    "    mov.w   r2, #0x002C4000\n" \
    "2:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     2b\n"

static inline __attribute__((always_inline)) void g3x_ladder_pulse_c(void)
{
    asm volatile (
        LADDER_ASM_PULSE
        :
        :
        : "r0", "r1", "r2", "r3", "cc", "memory"
    );
}

#endif /* LED_LADDER */

#endif /* LED_BREADCRUMB_H */
