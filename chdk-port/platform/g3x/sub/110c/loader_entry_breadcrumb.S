/*
 * PORT-23 T2b: Loader-entry LED breadcrumb for Canon PowerShot G3 X (GM1.10C).
 *
 * Hardware facts VERIFIED on camera (owner, 2026-11-01):
 * - Writing 0x004D0002 to MMIO 0xD20B0884 turns the green LED ON.
 * - Writing 0x004C0003 turns the green LED OFF.
 * - Loader entry prologue at 0x8000 runs.
 * - Stalls of 0x06000000 and 0x00600000 both resulted in a dark camera.
 *
 * Stage 1: loader_entry
 * If LED_BREADCRUMB_LOADER_ENTRY is defined:
 *   1. Write 0x004D0002 to MMIO 0xD20B0884.
 *   2. Issue DSB (sy) to ensure store reaches peripheral.
 *   3. If LED_BREADCRUMB_DELAY > 0 (capped at 0x00600000), optional bounded busy-wait.
 *   4. Set sp = 0x8000 and branch to my_restart.
 *
 * If LED_BREADCRUMB_LOADER_ENTRY is NOT defined:
 *   Standard loader entry:
 *     ldr sp, =0x8000
 *     b.w my_restart
 *
 * Invariants:
 * - No changes to CPSR, interrupts, or execution mode.
 * - Registers overwritten (r0, r1, r2, condition flags) are dead at my_restart entry.
 * - sp initialized to 0x8000.
 */

.section .entry, "ax", %progbits
.code 16
.align 2
.syntax unified

.global _start
.thumb_func
_start:
#if defined(LED_BREADCRUMB_LOADER_ENTRY)
    /* 1. Write action-0 value 0x004D0002 to MMIO address 0xD20B0884 (LED ON) */
    ldr     r0, =0xD20B0884
    ldr     r1, =0x004D0002
    str     r1, [r0]
    dsb     sy

#if defined(LED_BREADCRUMB_DELAY) && (LED_BREADCRUMB_DELAY > 0)
#if (LED_BREADCRUMB_DELAY > 0x00600000)
#error "LED_BREADCRUMB_DELAY exceeds maximum safety cap of 0x00600000"
#endif
    /* 2. Optional bounded busy-wait delay loop (capped at <= 0x00600000) */
    ldr     r2, =LED_BREADCRUMB_DELAY
.Lbreadcrumb_delay:
    subs    r2, r2, #1
    bne     .Lbreadcrumb_delay
#endif

#endif

    /* Standard loader entry sequence: set sp = 0x8000 and branch to my_restart */
    ldr     sp, =0x8000
    b.w     my_restart

    .align  2
    .ltorg
