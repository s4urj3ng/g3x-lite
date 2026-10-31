/*
 * PORT-20 T2: Loader-entry LED signal prologue for Canon PowerShot G3 X (GM1.10C).
 *
 * Signal sequence (about 1-2 s of changed LED state at loader entry):
 * 1. Write action-0 value (0x004d0002) to MMIO 0xD20B0884 (GPIO pin 33, LED descriptor 0).
 *    (MMIO address and action values VERIFIED; ON/OFF polarity UNKNOWN).
 * 2. Issue DSB (sy) to ensure store reaches peripheral.
 * 3. Bounded busy-wait loop with fixed constant 0x06000000 (~1-2 s for ~150-200 MHz clock).
 * 4. Write action-1 value (0x004c0003) to MMIO 0xD20B0884.
 * 5. Issue DSB (sy) to ensure store completes.
 * 6. Fall through to unchanged original loader entry sequence:
 *    ldr sp, =0x8000
 *    b.w my_restart
 *
 * Register / state invariants:
 * - No changes to CPSR, interrupts, or execution mode (no cpsid/cpsie/msr).
 * - Registers overwritten (r0, r1, r2, condition flags) are dead at my_restart entry.
 * - r3, r4-r12, lr are preserved.
 * - sp is initialized to 0x8000 by the original entry instruction.
 */

.section .entry, "ax", %progbits
.code 16
.align 2
.syntax unified

.global _start
.thumb_func
_start:
    /* 1. Write action-0 value 0x004d0002 to MMIO address 0xD20B0884 */
    ldr     r0, =0xd20b0884
    ldr     r1, =0x004d0002
    str     r1, [r0]
    dsb     sy

    /* 2. Bounded busy-wait delay loop: fixed constant 0x06000000 (~1-2 s) */
    ldr     r2, =0x06000000
.Ldelay_loop:
    subs    r2, r2, #1
    bne     .Ldelay_loop

    /* 3. Write action-1 value 0x004c0003 to MMIO address 0xD20B0884 */
    ldr     r1, =0x004c0003
    str     r1, [r0]
    dsb     sy

    /* 4. Original entry sequence: set sp = 0x8000 and branch to my_restart */
    ldr     sp, =0x8000
    b.w     my_restart

    .align  2
    .ltorg
