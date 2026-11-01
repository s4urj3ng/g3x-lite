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
// (c) Non-loop overhead bound: ~9 instructions + 2 memory barriers (ldr, str, dsb, mov) execute in < 200 cycles (< 0.01 ms).
//     A conservative overhead bound of 1.0 ms is allocated.
// (d) Full-step requirement: Full modelled step (loops + overhead) must be strictly < 200 ms at slow bound.
// Maximized OFF gap: OFF = 0x002AC000 (2,801,664 iterations, Thumb-2 modified immediate encodable by mov.w r2, #0x002AC000):
// ON delay:  0x00134000 (1,261,568 iterations) -> ~20.05 ms (fast 100ms) / ~25.07 ms (nom 125ms) / ~60.16 ms (slow 300ms) [INFERRED]
// OFF delay: 0x002AC000 (2,801,664 iterations) -> ~44.53 ms (fast 100ms) / ~55.66 ms (nom 125ms) / ~133.59 ms (slow 300ms) [INFERRED]
// Total loop: 0x003E0000 (4,063,232 iterations) -> ~64.58 ms (fast) / ~80.73 ms (nom) / 193.75 ms (slow) [INFERRED]
// Full step (loops + 1.0 ms overhead): 193.75 ms + 1.0 ms = 194.75 ms (< 200.0 ms strictly) [INFERRED]
#define G3X_LADDER_ON_DELAY    0x00134000
#define G3X_LADDER_OFF_DELAY   0x002AC000

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
    "    mov.w   r2, #0x002AC000\n" \
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
