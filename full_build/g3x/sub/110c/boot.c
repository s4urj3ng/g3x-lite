// G3X GM1.10C Boot implementation (Full Build)
//
// PORT-41: Standard CHDK build adapted from sibling g7x (sub/100d) and g5x
// Sibling citations:
// - chdk-port/platform/g7x/sub/100d/boot.c:20-95, 99-157, 159-250, 350-434
// - chdk-port/platform/g5x/sub/100c/boot.c:70-130, 411-420, 479-506, 524-535

#define LED_LADDER 1

// Diagnostic LED ladder timing: 0x00100000 loops per stage frame (led_breadcrumb.h)
#define G3X_LED_LADDER_TIMING 0x00100000

#include "lolevel.h"
#include "platform.h"
#include "core.h"
#include "dryos31.h"
#include "camera_info.h"
#include "led_breadcrumb.h"

// Forward declarations
void spytask(long ua, long ub, long uc, long ud, long ue, long uf);
void CreateTask_spytask(void);
void boot(void);
void CreateTask_my(void);
void init_file_modules_task(void);
void sub_fc05b3c8_my(void);
void sub_fc05b558_my(void);
void sub_fc05b962_my(void);
void task_Startup_my(void);

extern void g3x_full_shortpress_boot_entry_hook(void);
extern void g3x_full_shortpress_post_bss_hook(void);
extern void mykbd_task(void);
extern void core_spytask_can_start(void);

// Dynamic heap boundary: points to the 16-byte aligned end of CHDK BSS
const char * const new_sa = &_end;

// -----------------------------------------------------------------------------
// CHDK SpyTask Lifecycle
// -----------------------------------------------------------------------------
void spytask(long ua, long ub, long uc, long ud, long ue, long uf)
{
    core_spytask();
}

void CreateTask_spytask(void)
{
    // Task priority 0x19 (25 decimal), stack size 8192 bytes (0x2000)
    // Uses standard CHDK signature from include/lolevel.h:54
    _CreateTask("SpyTask", 0x19, 0x2000, spytask, 0);
}

// -----------------------------------------------------------------------------
// Stage 1 & 2: Main Entry Point (relocated core execution @ MEMISOSTART = 0x003489B4)
// Replicates stock Canon startup sequence from 0xFC02000C in GM1.10C ROM
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) boot(void)
{
    asm volatile (
        "    movw    r0, #0x4000\n"
        "    movt    r0, #0\n"
        "    mov     sp, r0\n"
        CORE_LADDER_PULSE_11

        // Early boot shortpress start-cause save hook
        "    push    {r0-r3, r12, lr}\n"
        "    bl      g3x_full_shortpress_boot_entry_hook\n"
        "    pop     {r0-r3, r12, lr}\n"

        // Vector table copy
        "    bl      sub_fc02007e\n"

        // Clock gate enable
        "    ldr     r2, =0xc0242010\n"
        "    ldr     r1, [r2]\n"
        "    orr     r1, r1, #1\n"
        "    str     r1, [r2]\n"

        // Copy Loop 1: High RAM (0xFCEC854C -> 0x010E1000..0x01107D00, 0x26D00 B)
        "    ldr     r0, =0xfcec854c\n"
        "    ldr     r1, =0x010e1000\n"
        "    ldr     r3, =0x01107d00\n"
        "1:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     1b\n"

        // Copy Loop 2: ATCM (0xFCEEF24C -> 0xBFE10800..0xBFE17419, 0x6C19 B)
        "    ldr     r0, =0xfceef24c\n"
        "    ldr     r1, =0xbfe10800\n"
        "    ldr     r3, =0xbfe17419\n"
        "2:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     2b\n"

        // Install hook_CreateTask patch at ATCM address 0xBFE14A3C (Thumb entry 0xBFE14A3D)
        // Replaces 8 bytes: stmdb sp!, {r1-r9, lr}; mov r4, r0; ldr r0, =0x8160
        // with jump to CreateTask_my
        "    adr     r0, patch_CreateTask\n"
        "    ldr     r1, =0xbfe14a3c\n"
        "    add     r2, r0, #8\n"
        "3:\n"
        "    ldrh    r3, [r0], #2\n"
        "    strh    r3, [r1], #2\n"
        "    cmp     r0, r2\n"
        "    blo     3b\n"

        // Cache clean routine
        "    ldr     r0, =0x010e1000\n"
        "    ldr     r1, =0x00026d00\n"
        "    bl      sub_fc127a62\n"

        // Copy Loop 3: Low RAM (0xFCE91058 -> 0x00008000..0x0003F4F4)
        "    ldr     r0, =0xfce91058\n"
        "    ldr     r1, =0x00008000\n"
        "    ldr     r3, =0x0003f4f4\n"
        "4:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     4b\n"

        // Zero Canon BSS (0x0003F4F4..0x003489B4) up to MEMISOSTART
        "    ldr     r3, =0x0003f4f4\n"
        "    ldr     r1, =0x003489b4\n"
        "    movs    r2, #0\n"
        "5:\n"
        "    cmp     r3, r1\n"
        "    it      lo\n"
        "    strlo   r2, [r3], #4\n"
        "    blo     5b\n"
        CORE_LADDER_PULSE_12

        // Post-BSS hook: restore start cause 0x00080000 and fake Power bit 17 in physw_status[0]
        "    push    {r0-r3, r12, lr}\n"
        "    bl      g3x_full_shortpress_post_bss_hook\n"
        "    pop     {r0-r3, r12, lr}\n"

        // Branch to DryOS Kernel Heap Reservation Trampoline
        "    b.w     sub_fc05b3c8_my\n"

        "patch_CreateTask:\n"
        "    ldr.w   pc, [pc, #0]\n"
        "    .long   CreateTask_my + 1\n"
    );
}

// -----------------------------------------------------------------------------
// CreateTask Interceptor: hooks task_PhySw and task_InitFileModules
// Sibling citations:
// - chdk-port/platform/g7x/sub/100d/boot.c:99-157
// - chdk-port/platform/g5x/sub/100c/boot.c:70-130
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) CreateTask_my(void)
{
    asm volatile (
        "    push    {r0}\n"

        // Intercept task_PhySw (0xFC1283AD) -> mykbd_task
        "    ldr     r0, =0xfc1283ad\n"
        "    cmp     r0, r3\n"
        "    bne     1f\n"
        "    ldr     r3, =mykbd_task\n"
        "    orr     r3, r3, #1\n"
        "    movw    r2, #0x2000\n" // Set kbd task stack to 0x2000 (cite chdk-port/platform/g7x/sub/100d/boot.c:400, g5x/sub/100c/boot.c:498)
        "    b       exitHook\n"
        "1:\n"

        // Intercept task_InitFileModules (0xFC0BD071) -> init_file_modules_task
        "    ldr     r0, =0xfc0bd071\n"
        "    cmp     r0, r3\n"
        "    itt     eq\n"
        "    ldreq   r3, =init_file_modules_task\n"
        "    orreq   r3, #1\n"
        "    beq     exitHook\n"

        // capt_seq, movie_rec, filewrite left stock (not in FINSIG / VERIFIED)
        // Listed as TODOs in documentation per specification

        "exitHook:\n"
        "    pop     {r0}\n"
        // Replaced original 8 bytes of CreateTask
        "    stmdb   sp!, {r1, r2, r3, r4, r5, r6, r7, r8, r9, lr}\n"
        "    mov     r4, r0\n"
        "    ldr     r0, =0x8160\n"
        "    ldr.w   pc, =(0xbfe14a3c + 8 + 1)\n"
        "    .ltorg\n"
    );
}

// -----------------------------------------------------------------------------
// task_InitFileModules hook: signals core_spytask_can_start() once file system is up
// Replicates stock GM1.10C ROM 0xFC0BD070..0xFC0BD0A0
// Sibling citation: chdk-port/platform/g7x/sub/100d/boot.c:410-434
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) init_file_modules_task(void)
{
    asm volatile (
        "    push    {r4, r5, r6, lr}\n"
        "    bl      sub_fc0d9ccc\n"
        "    movs    r4, r0\n"
        "    movw    r5, #0x5006\n"
        "    beq     1f\n"
        "    movs    r1, #0\n"
        "    mov     r0, r5\n"
        "    bl      _PostLogicalEventToUI\n"
        "1:\n"
        "    bl      sub_fc0d9cf6\n"
        "    bl      core_spytask_can_start\n"
        "    cmp     r4, #0\n"
        "    bne     2f\n"
        "    mov     r0, r5\n"
        "    pop.w   {r4, r5, r6, lr}\n"
        "    movs    r1, #1\n" // docs/PORT11A_GM110C_ROM_EVIDENCE.md:263-264: verified GM1.10C instruction at 0xFC0BD094 passes r1=1
        "    b.w     _PostLogicalEventToUI\n"
        "2:\n"
        "    pop     {r4, r5, r6, pc}\n"
        "    .ltorg\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 3: DryOS Kernel Heap Reservation Trampoline (replaces 0xFC05B3C8)
// Exact initialization contract matching boot_prototype.c:188-260
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b3c8_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        "    ldr     r4, =new_sa\n"
        "    ldr     r4, [r4]\n"
        "    sub     sp, #0x78\n"

        // Headroom verification: 0x006CE000 - r4 >= 0x000B1FEC (712 KiB)
        "    ldr     r0, =0x006ce000\n"
        "    ldr     r1, =0x000b1fec\n"
        "    subs    r0, r0, r4\n"
        "    cmp     r0, r1\n"
        "    bhs     1f\n"
        "2:\n"
        "    b       2b\n"
        "1:\n"

        // Configure system registers in Low RAM
        "    ldr     r1, =0x00008074\n"
        "    mov.w   r0, #0x80000\n"
        "    str     r0, [r1]\n"
        "    ldr     r1, =0x00008078\n"
        "    ldr     r0, =0x42281000\n"
        "    str     r0, [r1]\n"
        "    ldr     r1, =0x0000807c\n"
        "    ldr     r0, =0x42283000\n"
        "    str     r0, [r1]\n"

        // Zero the 0x78-byte structure via memset(sp, 0, 0x78)
        "    movs    r1, #0x78\n"
        "    mov     r0, sp\n"
        "    blx     sub_fc31bfac\n"

        // Populate DryOS Kernel Memory Descriptors
        "    ldr     r0, =0x0060e000\n"
        "    mov.w   r1, #0xc0000\n"
        "    stm.w   sp, {r0, r1, r4}\n"
        "    ldr     r1, =0x00600014\n"
        "    subs    r2, r1, r4\n"
        "    strd    r2, r1, [sp, #0xc]\n"
        "    str     r0, [sp, #0x14]\n"

        // DryOS OS Entity Limits (matching GM1.10C ROM)
        "    movs    r0, #0x22\n"
        "    str     r0, [sp, #0x18]\n"
        "    movs    r0, #0xca\n"
        "    str     r0, [sp, #0x1c]\n"
        "    movw    r0, #0x2b0\n"
        "    str     r0, [sp, #0x20]\n"
        "    movs    r0, #0xfa\n"
        "    str     r0, [sp, #0x24]\n"
        "    movw    r0, #0x11a\n"
        "    str     r0, [sp, #0x28]\n"
        "    movs    r0, #0x85\n"
        "    str     r0, [sp, #0x2c]\n"
        "    movs    r0, #0x40\n"
        "    str     r0, [sp, #0x30]\n"
        "    movs    r0, #4\n"
        "    str     r0, [sp, #0x34]\n"
        "    movs    r0, #0\n"
        "    str     r0, [sp, #0x38]\n"
        "    movs    r0, #0x10\n"
        "    str     r0, [sp, #0x5c]\n"
        "    movs    r2, #0\n"
        "    lsls    r0, r0, #8\n"
        "    str     r0, [sp, #0x60]\n"

        // Continuation entry point: sub_fc05b558_my
        "    ldr     r1, =sub_fc05b558_my\n"
        "    asrs    r0, r0, #4\n"
        "    str     r0, [sp, #0x64]\n"
        "    lsls    r0, r0, #5\n"
        "    str     r0, [sp, #0x68]\n"

        // Dispatch into DryOS Kernel Initialization (ATCM 0xBFE10F79)
        CORE_LADDER_PULSE_14
        "    mov     r0, sp\n"
        "    blx     sub_fc31b408\n"

        // Clean up stack frame and return
        "    add     sp, #0x78\n"
        "    pop     {r4, pc}\n"
        "    .ltorg\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 4: Subsystem Init Sequence Hook (replaces 0xFC05B558)
// Matches argument setup and call sequence from boot_prototype.c:270-335
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b558_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        CORE_LADDER_PULSE_15
        "    ldr     r4, =0xfc05b600\n"        // ROM literal string "/_term" (adr @0xFC05B55A, PORT-5D)
        "    bl      sub_fc05c5bc\n"
        "    ldr     r0, =0x000080ec\n"        // literal @0xFC05B608: [0x80ec] heap size
        "    ldr     r1, [r0]\n"
        "    ldr     r0, =0x00008074\n"        // literal @0xFC05B60C: [0x8074] 0x80000 bound
        "    ldr     r0, [r0]\n"
        "    adds    r0, #0x10\n"
        "    cmp     r1, r0\n"
        "    bhs     1f\n"
        "    ldr     r0, =0xfc05b610\n"        // ROM literal string "USER_MEM size checking" (adr @0xFC05B56E)
        "    bl      sub_fc05b5ea\n"
        "1:\n"
        "    bl      sub_fc127b3c\n"
        "    ldr     r1, =0xbfe10000\n"
        "    mov.w   r2, #-0x11111112\n"
        "    ldr     r3, =0xbfe10800\n"
        "2:\n"
        "    stm     r1!, {r2}\n"
        "    cmp     r1, r3\n"
        "    blo     2b\n"
        "    bl      sub_fc127b4e\n"
        "    bl      sub_fc418738\n"           // dmSetup
        "    cmp     r0, #0\n"
        "    bge     3f\n"
        "    ldr     r0, =0xfc05b630\n"        // ROM literal string "dmSetup" (adr @0xFC05B592)
        "    bl      sub_fc05b5ea\n"
        "3:\n"
        "    bl      sub_fc05c7d4\n"           // termDriverInit
        "    cmp     r0, #0\n"
        "    bge     4f\n"
        "    ldr     r0, =0xfc05b638\n"        // ROM literal string "termDriverInit" (adr @0xFC05B5A0)
        "    bl      sub_fc05b5ea\n"
        "4:\n"
        "    mov     r0, r4\n"
        "    bl      sub_fc05c862\n"           // termDeviceCreate
        "    cmp     r0, #0\n"
        "    bge     5f\n"
        "    ldr     r0, =0xfc05b648\n"        // ROM literal string "termDeviceCreate" (adr @0xFC05B5B0)
        "    bl      sub_fc05b5ea\n"
        "5:\n"
        "    mov     r0, r4\n"
        "    bl      sub_fc05b794\n"           // stdioSetup
        "    cmp     r0, #0\n"
        "    bge     6f\n"
        "    ldr     r0, =0xfc05b65c\n"        // ROM literal string "stdioSetup" (adr @0xFC05B5C0)
        "    bl      sub_fc05b5ea\n"
        "6:\n"
        "    bl      sub_fc05b8d8\n"           // stdlibSetup
        "    cmp     r0, #0\n"
        "    bge     7f\n"
        "    ldr     r0, =0xfc05b668\n"        // ROM literal string "stdlibSetup" (adr @0xFC05B5CE)
        "    bl      sub_fc05b5ea\n"
        "7:\n"
        "    bl      sub_fc05e910\n"           // extlib_setup
        "    cmp     r0, #0\n"
        "    bge     8f\n"
        "    ldr     r0, =0xfc05b674\n"        // ROM literal string "extlib_setup" (adr @0xFC05B5DC)
        "    bl      sub_fc05b5ea\n"
        "8:\n"
        "    pop.w   {r4, lr}\n"
        "    b.w     sub_fc05b962_my\n"
        "    .ltorg\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 5: Startup Task Spawner Hook (replaces 0xFC05B962)
// PORT-24/39 Power-cut bypass: skips sub_fc05ba56 shutdown
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b962_my(void)
{
    asm volatile (
        "    push    {r3, lr}\n"
        CORE_LADDER_PULSE_21
        CORE_LADDER_PULSE_22
        "    bl      sub_fc05ba68\n"
        CORE_LADDER_PULSE_23
        "    bl      sub_fc079404\n"
        CORE_LADDER_PULSE_24
        "    bl      sub_fc1284ac\n"
        "    movs    r0, #1\n"
        "    b       1f\n"
        "1:\n"
        CORE_LADDER_PULSE_25
        "    blx     sub_fc31b460\n"
        "    ldr     r1, =0x006ce000\n"
        "    movs    r0, #0\n"
        "    bl      sub_fc382c8c\n"
        "    movs    r3, #0\n"
        "    str     r3, [sp]\n"
        "    ldr     r3, =task_Startup_my\n"
        "    movs    r2, #0\n"
        "    movs    r1, #0x19\n"
        "    ldr     r0, =0xfc05b9a0\n"
        CORE_LADDER_PULSE_26
        "    blx     sub_fc31bbc4\n"
        "    movs    r0, #0\n"
        "    pop     {r3, pc}\n"
        "    .ltorg\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 6: Patched task_Startup (replaces 0xFC05B8FC)
// Creates PhySw, SpyTask, executes LED ladder, and hands off to sub_fc0d0126
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) task_Startup_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        CORE_LADDER_PULSE_31
        "    bl      sub_fc0d0150\n"
        "    bl      sub_fc05ba34\n"
        "    bl      sub_fc05bb94\n"
        "    bl      sub_fc418eec\n"
        CORE_LADDER_PULSE_32

        // SD1stInit gate (replicates StartDiskboot gate)
        CORE_LADDER_PULSE_33
        "    movs    r0, #0\n"
        "    bl      sub_fc05c4e0\n"
        "    lsls    r0, r0, #31\n"
        "    bne     1f\n"
        "    blx     sub_fc31b1f4\n"
        "1:\n"
        CORE_LADDER_PULSE_34

        "    bl      sub_fc0bba02\n"
        "    bl      sub_fc0d046c\n"
        "    bl      sub_fc05bcdc\n"
        "    bl      sub_fc05bb24\n"
        CORE_LADDER_PULSE_35
        "    bl      sub_fc418f2a\n"
        CORE_LADDER_PULSE_41
        "    bl      sub_fc090674\n"
        "    bl      sub_fc0d0472\n"

        // Launch task_PhySw / mykbd_task
        CORE_LADDER_PULSE_42
        "    bl      sub_fc1283d2\n"
        CORE_LADDER_PULSE_43

        // Spawn CHDK SpyTask
        "    bl      CreateTask_spytask\n"

        "    bl      sub_fc2a75f6\n"
        "    bl      sub_fc0d0488\n"
        "    bl      sub_fc127f24\n"
        "    bl      sub_fc0bb76e\n"
        "    bl      sub_fc0d02de\n"
        "    bl      sub_fc0bb9cc\n"
        "    bl      sub_fc0bb72a\n"
        "    bl      sub_fc05bce0\n"
        "    bl      sub_fc33319a\n"
        "    bl      sub_fc0bb6fe\n"

        // PORT-24..39 Held-Press Diagnostic Ladder Code 44 on LED 0xD20B0884
        CORE_LADDER_PULSE_44

        // Restore registers and terminal handoff to sub_fc0d0126
        "    pop.w   {r4, lr}\n"
        "    b.w     sub_fc0d0126\n"
        "    .ltorg\n"
    );
}
