// =============================================================================
// CHDK-PORT-23 T2b: Breadcrumb Loader for Canon PowerShot G3 X (GM1.10C)
//
// Opt-in diagnostic loader supporting LED breadcrumb checkpoints:
// Stage 1: loader_entry  (loader_entry_breadcrumb.S @ 0x8000)
// Stage 2: before_copy   (my_restart before core_copy)
// Stage 3: after_copy    (my_restart after core_copy)
// Stage 4: witness_entry (my_restart at boot_witness entry)
// Stage 5: witness_write (my_restart right after witness store)
// Stage 6: pre_jump      (my_restart immediately before jump to payload)
// =============================================================================

#include "../generic/check_compat.c"
#include "../../platform/g3x/sub/110c/boot_witness.h"
#include "../../platform/g3x/sub/110c/led_breadcrumb.h"

#define __STR(x) #x
#define _STR(x) __STR(x)

extern long *blob_chdk_core;
extern long blob_chdk_core_size;

// Decoupled native cache maintenance routines in GM1.10C ROM:
// Inverted order in 0xFC418722 remediated per PORT-1D.1:
// 1. 0xFC127AB1: D-cache clean & invalidate (DCCISW all sets/ways) + DSB
// 2. 0xFC127B09: I-cache invalidate (ICIALLU) + branch predictor invalidate (BPIALL) + ISB
#define ROM_DCACHE_CLEAN_INV 0xFC127AB1
#define ROM_ICACHE_INV_BP    0xFC127B09

void __attribute__((noreturn, noinline)) my_restart()
{
    // 1. Validate platform compatibility
    check_compat();

    // 2. Setup relocation parameters
    long *dst = (long*)MEMISOSTART;                 // 0x003489B4
    const long *src = blob_chdk_core;              // Loader-embedded core image
    long byte_size = ((blob_chdk_core_size + 3) >> 2) << 2;
    long word_len = byte_size >> 2;

#if defined(LED_BREADCRUMB_BEFORE_COPY)
    g3x_breadcrumb_led_on();
#elif defined(LED_BREADCRUMB_LOADER_ENTRY) && defined(LED_BREADCRUMB_OFF_NEXT)
    g3x_breadcrumb_led_off();
#endif

    // 3. Relocate CHDK core from loader RAM to DRAM MEMISOSTART
    core_copy(src, dst, word_len);

#if defined(LED_BREADCRUMB_AFTER_COPY)
    g3x_breadcrumb_led_on();
#elif defined(LED_BREADCRUMB_BEFORE_COPY) && defined(LED_BREADCRUMB_OFF_NEXT)
    g3x_breadcrumb_led_off();
#endif

#ifdef BOOT_WITNESS_ADDR
#if defined(LED_BREADCRUMB_WITNESS_ENTRY)
    g3x_breadcrumb_led_on();
#elif defined(LED_BREADCRUMB_AFTER_COPY) && defined(LED_BREADCRUMB_OFF_NEXT)
    g3x_breadcrumb_led_off();
#endif
    // Record Stage 1 (LOADER_REACHED) in Boot Witness
    volatile boot_witness_t *w = (volatile boot_witness_t*)BOOT_WITNESS_ADDR;
    w->magic = BOOT_WITNESS_MAGIC;
    w->version = BOOT_WITNESS_VERSION;
#ifdef WITNESS_SESSION_NONCE
    w->session_nonce = WITNESS_SESSION_NONCE;
#else
    w->session_nonce = 0x32A80001; // Default challenge nonce for prototype
#endif
    w->stage_state = STAGE_LOADER;
    register uint32_t current_sp asm("sp");
    w->loader_sp = current_sp;
    w->core_entry_pc = 0;
    w->cont_tick = 0;
    w->checksum = compute_witness_checksum((const boot_witness_t*)w);
#if defined(LED_BREADCRUMB_WITNESS_WRITE)
    g3x_breadcrumb_led_on();
#elif defined(LED_BREADCRUMB_WITNESS_ENTRY) && defined(LED_BREADCRUMB_OFF_NEXT)
    g3x_breadcrumb_led_off();
#endif
#endif

    // 4. Execute decoupled cache synchronization in canonical ARMv7-A/R order (§B2.2.5.2):
    //    Step 1: Clean and invalidate D-cache to PoC (DCCISW all sets/ways)
    //    Step 2: Invalidate I-cache and branch predictors (ICIALLU/BPIALL) + ISB
    //    Step 3: Enforce disabled interrupt state (cpsid if)
    //    Step 4: One-way terminal branch to relocated core entry (0x003489B4)
    //
    // ABI Hardening (PORT-1D.2):
    // - Call targets are freshly loaded into r2 immediately before each BLX call,
    //   preventing caller-saved r12/ip clobber across the first ROM subroutine.
    // - Operand registers %0 and %1 are held in callee-saved registers (r4-r11).
    // - Full AAPCS scratch register clobber list declared: r0-r3, r12, lr, cc, memory.
    asm volatile (
        // Step 1: Clean and invalidate Data Cache to PoC (DCCISW all sets/ways)
        "    mov     r0, %0\n"                      // r0 = start address (0x003489B4)
        "    mov     r1, %1\n"                      // r1 = size in bytes
        "    ldr     r2, =%2\n"                     // Freshly load ROM_DCACHE_CLEAN_INV
        "    blx     r2\n"                          // Calls ROM_DCACHE_CLEAN_INV (0xFC127AB1)
        "    dsb     sy\n"                          // Ensure data writebacks complete

        // Step 2: Invalidate Instruction Cache (ICIALLU) and Branch Predictor (BPIALL)
        "    mov     r0, %0\n"                      // r0 = start address
        "    mov     r1, %1\n"                      // r1 = size in bytes
        "    ldr     r2, =%3\n"                     // Freshly load ROM_ICACHE_INV_BP (eliminates caller-saved r12)
        "    blx     r2\n"                          // Calls ROM_ICACHE_INV_BP (0xFC127B09)
        "    dsb     sy\n"                          // Ensure invalidation completion
        "    isb     sy\n"                          // Flush instruction pipeline

        // Step 3: Enforce disabled interrupt state prior to handoff
        "    cpsid   if\n"                          // Guarantee IRQ & FIQ disabled

        // Step 4: One-way terminal handoff to relocated core entry (0x003489B4)
#if defined(LED_BREADCRUMB_PRE_JUMP)
        "    ldr     r0, =0xD20B0884\n"
        "    ldr     r1, =0x004D0002\n"
        "    str     r1, [r0]\n"
        "    dsb     sy\n"
#if defined(LED_BREADCRUMB_DELAY) && (LED_BREADCRUMB_DELAY > 0)
        "    ldr     r2, =" _STR(LED_BREADCRUMB_DELAY) "\n"
        "1:\n"
        "    subs    r2, r2, #1\n"
        "    bne     1b\n"
#endif
#elif defined(LED_BREADCRUMB_WITNESS_WRITE) && defined(LED_BREADCRUMB_OFF_NEXT)
        "    ldr     r0, =0xD20B0884\n"
        "    ldr     r1, =0x004C0003\n"
        "    str     r1, [r0]\n"
        "    dsb     sy\n"
#endif
        "    mov     r0, %0\n"
        "    add     r0, r0, #1\n"                  // Set Thumb bit (0x003489B5)
        "    bx      r0\n"                          // Branch into relocated core
        :
        : "r"(MEMISOSTART), "r"(byte_size),
          "i"(ROM_DCACHE_CLEAN_INV), "i"(ROM_ICACHE_INV_BP)
        : "r0", "r1", "r2", "r3", "r12", "lr", "cc", "memory"
    );

    // Unreachable fallback
    while (1)
        ;
}
