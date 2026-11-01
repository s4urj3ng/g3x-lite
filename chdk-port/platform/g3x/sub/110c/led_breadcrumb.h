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

static inline __attribute__((always_inline)) void g3x_breadcrumb_led_on(void)
{
    *(volatile unsigned int *)G3X_LED_MMIO_ADDR = G3X_LED_ON_VAL;
    asm volatile("dsb sy" ::: "memory");
#if defined(LED_BREADCRUMB_DELAY) && (LED_BREADCRUMB_DELAY > 0)
    register unsigned int count = LED_BREADCRUMB_DELAY;
    asm volatile(
        "1:\n"
        "    subs %0, %0, #1\n"
        "    bne  1b\n"
        : "+r"(count)
        :
        : "cc"
    );
#endif
}

static inline __attribute__((always_inline)) void g3x_breadcrumb_led_off(void)
{
    *(volatile unsigned int *)G3X_LED_MMIO_ADDR = G3X_LED_OFF_VAL;
    asm volatile("dsb sy" ::: "memory");
}

#endif /* LED_BREADCRUMB */

#endif /* LED_BREADCRUMB_H */
