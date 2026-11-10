// =============================================================================
// Functional Loader for Canon PowerShot G3 X (GM1.10C) Full Build
// Adapted from chdk-port/loader/g7x/main.c:1-57 and chdk-port/loader/g5x/main.c:1-49
// =============================================================================

#include "../generic/check_compat.c"

extern long *blob_chdk_core;
extern long blob_chdk_core_size;

void __attribute__((noreturn)) my_restart()
{
    // Adapted from chdk-port/loader/g7x/main.c:8 and g5x/main.c:8
    check_compat();

    // Adapted from chdk-port/loader/g7x/main.c:10-14 and g5x/main.c:10-14
    long *dst = (long*)MEMISOSTART;
    const long *src = blob_chdk_core;
    long length = (blob_chdk_core_size + 3) >> 2;

    core_copy(src, dst, length);

    // Light up Power LED 0xD20B0884 (adapted from g7x/main.c:17 green LED 0xd20b0994)
    *(volatile int*)0xd20b0884 = 0x4d0002;

    // Flush/clean cache and jump to core at MEMISOSTART in Thumb mode
    // Adapted from chdk-port/loader/g7x/main.c:43-54 and g5x/main.c:37-46
    asm volatile (
    "mov     r1, %1\n"
    "mov     r0, %0\n"
    "ldr     r2, =0xFC418723\n" // GM1.10C ROM caching subroutine (analogous to g7x 0xfc133daf:46, g5x 0xFC150D5B:40)
    "blx     r2\n"
    "dsb     sy\n"
    "isb     sy\n"
    "cpsid   if\n"
    // Start execution at MEMISOSTART in Thumb mode
    "mov     r0, %0\n"
    "add     r0, r0, #1\n"
    "bx      r0\n"
    : : "r"(MEMISOSTART), "r"(((blob_chdk_core_size+3)>>2)<<2)
    : "memory","r0","r1","r2","r3","r4"
    );

    while (1)
        ;
}
