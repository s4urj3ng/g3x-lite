// =============================================================================
// Functional Loader for Canon PowerShot G3 X (GM1.10C) Full Build
// Adapted from chdk-port/loader/g7x/main.c:1-57 and chdk-port/loader/g3x/main_prototype.c:19-95 (PORT-1F2 / PORT-1D2 / PORT-24..39)
// =============================================================================

#include "../generic/check_compat.c"

extern long *blob_chdk_core;
extern long blob_chdk_core_size;

// Decoupled native cache maintenance routines in GM1.10C ROM:
// Inverted order in 0xFC418722 remediated per PORT-1D.1 / PORT-1F2
// (VERIFIED: docs/CHDK_PORT1D1_MPU_CACHE_VERIFICATION.md:124-134 and docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119):
// 1. 0xFC127AB1: D-cache clean & invalidate (DCCISW all sets/ways) + DSB
// 2. 0xFC127B09: I-cache invalidate (ICIALLU) + branch predictor invalidate (BPIALL) + ISB
#define ROM_DCACHE_CLEAN_INV 0xFC127AB1
#define ROM_ICACHE_INV_BP    0xFC127B09

void __attribute__((noreturn)) my_restart()
{
    // Adapted from chdk-port/loader/g7x/main.c:8 and g5x/main.c:8
    check_compat();

    // Adapted from chdk-port/loader/g7x/main.c:10-14 and g5x/main.c:10-14
    long *dst = (long*)MEMISOSTART;
    const long *src = blob_chdk_core;
    long byte_size = ((blob_chdk_core_size + 3) >> 2) << 2;
    long length = byte_size >> 2;

    core_copy(src, dst, length);

    // Light up Power LED 0xD20B0884 (adapted from g7x/main.c:17 green LED 0xd20b0994)
    *(volatile int*)0xd20b0884 = 0x4d0002;

    // Decoupled cache synchronization in canonical ARM order (clean D-cache before invalidating I-cache):
    // Reused from chdk-port/loader/g3x/main_prototype.c:69-95 (PORT-1F2 / PORT-1D2 / PORT-24..39)
    asm volatile (
        // Step 1: Clean and invalidate Data Cache to PoC (DCCISW all sets/ways)
        "    mov     r0, %0\n"                      // r0 = start address (0x003489B4)
        "    mov     r1, %1\n"                      // r1 = size in bytes
        "    ldr     r2, =%2\n"                     // Freshly load ROM_DCACHE_CLEAN_INV (0xFC127AB1)
        "    blx     r2\n"                          // Calls ROM_DCACHE_CLEAN_INV (0xFC127AB1)
        "    dsb     sy\n"                          // Ensure data writebacks complete

        // Step 2: Invalidate Instruction Cache (ICIALLU) and Branch Predictor (BPIALL)
        "    mov     r0, %0\n"                      // r0 = start address
        "    mov     r1, %1\n"                      // r1 = size in bytes
        "    ldr     r2, =%3\n"                     // Freshly load ROM_ICACHE_INV_BP (0xFC127B09)
        "    blx     r2\n"                          // Calls ROM_ICACHE_INV_BP (0xFC127B09)
        "    dsb     sy\n"                          // Ensure invalidation completion
        "    isb     sy\n"                          // Flush instruction pipeline

        // Step 3: Enforce disabled interrupt state prior to handoff
        "    cpsid   if\n"                          // Guarantee IRQ & FIQ disabled

        // Step 4: One-way terminal handoff to relocated core entry (0x003489B4)
        "    mov     r0, %0\n"
        "    add     r0, r0, #1\n"                  // Set Thumb bit (0x003489B5)
        "    bx      r0\n"                          // Branch into relocated core
        :
        : "r"(MEMISOSTART), "r"(byte_size),
          "i"(ROM_DCACHE_CLEAN_INV), "i"(ROM_ICACHE_INV_BP)
        : "r0", "r1", "r2", "r3", "r12", "lr", "cc", "memory"
    );

    while (1)
        ;
}
