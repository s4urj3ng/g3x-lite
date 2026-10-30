// =============================================================================
// CHDK-PORT-1C: Offline Boot Trampoline Prototype for Canon PowerShot G3 X (GM1.10C)
//
// ISOLATED EXPERIMENTAL PROTOTYPE - NOT FOR PRODUCTION PACKAGING OR DEPLOYMENT
//
// Architecture: DIGIC 6 (Cortex-A9), DryOS 57
// Target Firmware: GM1.10C (Platform ID 0x32A8 = 12968 decimal)
// Reference Architecture: PowerShot G5 X GM1.00C (DryOS 57 sister port)
//
// Safety Restrictions:
// - Hardware execution is STRICTLY PROHIBITED (Hardware readiness: NO-GO).
// - This prototype MUST NOT replace production boot.c or be packaged into canonical DISKBOOT.BIN.
// - Keyboard, display, capture, and movie task hooks remain strictly disabled.
// =============================================================================

#include "lolevel.h"
#include "platform.h"
#include "core.h"
#include "dryos31.h"
#include "camera_info.h"
#include "boot_witness.h"

// Dynamic reservation boundary: points to the 16-byte aligned end of CHDK BSS
const char * const new_sa = &_end;

// Dedicated, aligned witness region with explicit linker ownership in .data
volatile boot_witness_t boot_witness __attribute__((aligned(16), section(".data"))) = {
    0, 0, 0, 0, 0, 0, 0, 0
};

// Witness state transition functions
void witness_record_core(void)
{
    if (boot_witness.magic == BOOT_WITNESS_MAGIC &&
        boot_witness.version == BOOT_WITNESS_VERSION &&
        boot_witness.stage_state == STAGE_LOADER &&
        boot_witness.checksum == compute_witness_checksum((const boot_witness_t*)&boot_witness))
    {
        boot_witness.stage_state = (STAGE_LOADER | STAGE_CORE);
        boot_witness.core_entry_pc = 0x003489B5;
        boot_witness.checksum = compute_witness_checksum((const boot_witness_t*)&boot_witness);
    }
}

void witness_record_continuation(void)
{
    if (boot_witness.magic == BOOT_WITNESS_MAGIC &&
        boot_witness.version == BOOT_WITNESS_VERSION &&
        boot_witness.stage_state == (STAGE_LOADER | STAGE_CORE) &&
        boot_witness.checksum == compute_witness_checksum((const boot_witness_t*)&boot_witness))
    {
        boot_witness.stage_state = (STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION);
        boot_witness.cont_tick = 0x0014F200; // Deterministic hardware tick sentinel in prototype
        boot_witness.checksum = compute_witness_checksum((const boot_witness_t*)&boot_witness);
    }
}

// Forward declarations for prototype routines
void spytask(long ua, long ub, long uc, long ud, long ue, long uf);
void CreateTask_spytask(void);
void boot(void);
void sub_fc05b3c8_my(void);
void sub_fc05b558_my(void);
void sub_fc05b962_my(void);
void task_Startup_my(void);

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
    _CreateTask("SpyTask", 0x19, 0x2000, spytask, 0);
}

// -----------------------------------------------------------------------------
// Stage 1 & 2: Main Entry Point (relocated core execution @ MEMISOSTART = 0x003489B4)
// Replicates stock Canon startup sequence from 0xFC02000C in GM1.10C ROM
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) boot(void)
{
    asm volatile (
        // Reset stack pointer to initial stack boundary (0x4000)
        "    movw    r0, #0x4000\n"
        "    movt    r0, #0\n"
        "    mov     sp, r0\n"

        // Copy Thumb exception vector table ROM 0xFC05B47C..0xFC05B4B4 -> 0x00000000
        // (IRQ vector -> 0xFC05B6A9). No clock/power/interrupt-controller access.
        // IRQ/FIQ must already be masked by the loader (cpsid if): the IRQ path's
        // low-RAM state and handler table (0x0003F4F4) are rewritten below.
        // See docs/RESTART_IRQ_PENDING_AUDIT.md.
        "    bl      sub_fc02007e\n"

        // Peripheral bus clock gate enable (0xC0242010 |= 1)
        "    ldr     r2, =0xc0242010\n"
        "    ldr     r1, [r2]\n"
        "    orr     r1, r1, #1\n"
        "    str     r1, [r2]\n"

        // Copy Loop 1: High RAM (0x010E1000..0x01107D00) from ROM 0xFCEC854C
        "    ldr     r0, =0xfcec854c\n"
        "    ldr     r1, =0x010e1000\n"
        "    ldr     r3, =0x01107d00\n"
        "loc_copy_highram:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     loc_copy_highram\n"

        // Clean & invalidate cache for High RAM (0x010E1000, size 0x00026D00)
        "    ldr     r0, =0x010e1000\n"
        "    ldr     r1, =0x00026d00\n"
        "    bl      sub_fc127a62\n"

        // Copy Loop 2: ATCM (0xBFE10800..0xBFE17419) from ROM 0xFCEEF24C
        "    ldr     r0, =0xfceef24c\n"
        "    ldr     r1, =0xbfe10800\n"
        "    ldr     r3, =0xbfe17419\n"
        "loc_copy_atcm:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     loc_copy_atcm\n"

        // Copy Loop 3: Low RAM (0x00008000..0x0003F4F4) from ROM 0xFCE91058
        "    ldr     r0, =0xfce91058\n"
        "    ldr     r1, =0x00008000\n"
        "    ldr     r3, =0x0003f4f4\n"
        "loc_copy_lowram:\n"
        "    cmp     r1, r3\n"
        "    itt     lo\n"
        "    ldrlo   r2, [r0], #4\n"
        "    strlo   r2, [r1], #4\n"
        "    blo     loc_copy_lowram\n"

        // Zero Canon BSS (0x0003F4F4..0x003489B4)
        // CRITICAL: Terminates strictly at 0x003489B4 (MEMISOSTART), preserving CHDK core!
        "    ldr     r3, =0x0003f4f4\n"
        "    ldr     r1, =0x003489b4\n"
        "    mov.w   r2, #0\n"
        "loc_zero_bss:\n"
        "    cmp     r3, r1\n"
        "    it      lo\n"
        "    strlo   r2, [r3], #4\n"
        "    blo     loc_zero_bss\n"

        // Branch to DryOS Kernel Heap Reservation Trampoline
#if defined(G3X_TRACE) && G3X_TRACE
        "    b.w     g3x_trace_boot_post_bss\n"   // PORT-17 ENTRY/RELOC markers, see end of file
#else
        "    b.w     sub_fc05b3c8_my\n"
#endif
    );
}

// -----------------------------------------------------------------------------
// Stage 3: DryOS Kernel Heap Reservation Trampoline (replaces 0xFC05B3C8)
// Adjusts r4 = new_sa before constructing the 0x78-byte DryOS setup structure
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b3c8_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"

        // Record Stage 2 (Core Pre-Kernel Trampoline) in Boot Witness
        "    bl      witness_record_core\n"

        // Load shifted heap base from new_sa (&_end)
        "    ldr     r4, =new_sa\n"
        "    ldr     r4, [r4]\n"

        // Allocate 120-byte (0x78) setup structure on stack
        "    sub     sp, #0x78\n"

        // Headroom verification: 0x006CE000 - r4 >= 0x000B1FEC (712 KiB)
        "    ldr     r0, =0x006ce000\n"
        "    ldr     r1, =0x000b1fec\n"
        "    subs    r0, r0, r4\n"
        "    cmp     r0, r1\n"
        "    bhs     loc_fc05b3da\n"
        "loc_fc05b3d8:\n"
        "    b       loc_fc05b3d8\n"          // Safe halt if headroom check fails

        // Configure system registers in Low RAM
        "loc_fc05b3da:\n"
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
        "    ldr     r0, =0x0060e000\n"        // sp[0x00] = Heap Pool 0 Upper Limit
        "    mov.w   r1, #0xc0000\n"           // sp[0x04] = Chunk Size (768 KiB)
        "    stm.w   sp, {r0, r1, r4}\n"       // sp[0x08] = new_sa (SHIFTED HEAP BASE!)
        "    ldr     r1, =0x00600014\n"        // Sub-pool 1 boundary
        "    subs    r2, r1, r4\n"             // sp[0x0C] = 0x00600014 - new_sa (HEAP SIZE!)
        "    strd    r2, r1, [sp, #0xc]\n"     // sp[0x10] = 0x00600014
        "    str     r0, [sp, #0x14]\n"        // sp[0x14] = 0x0060E000

        // DryOS OS Entity Limits (matching GM1.10C ROM)
        "    movs    r0, #0x22\n"              // sp[0x18] = 34 max tasks
        "    str     r0, [sp, #0x18]\n"
        "    movs    r0, #0xca\n"              // sp[0x1C] = 202 max semaphores
        "    str     r0, [sp, #0x1c]\n"
        "    movw    r0, #0x2b0\n"             // sp[0x20] = 688 max message queues / event flags
        "    str     r0, [sp, #0x20]\n"
        "    movs    r0, #0xfa\n"              // sp[0x24] = 250 timer descriptors
        "    str     r0, [sp, #0x24]\n"
        "    movw    r0, #0x11a\n"             // sp[0x28] = 282 mutex descriptors
        "    str     r0, [sp, #0x28]\n"
        "    movs    r0, #0x85\n"              // sp[0x2C] = 133 condvar descriptors
        "    str     r0, [sp, #0x2c]\n"
        "    movs    r0, #0x40\n"              // sp[0x30] = 64 event descriptors
        "    str     r0, [sp, #0x30]\n"
        "    movs    r0, #4\n"                 // sp[0x34] = 4 system resources
        "    str     r0, [sp, #0x34]\n"
        "    movs    r0, #0\n"                 // sp[0x38] = 0
        "    str     r0, [sp, #0x38]\n"
        "    movs    r0, #0x10\n"              // sp[0x5C] = 16 priority levels
        "    str     r0, [sp, #0x5c]\n"
        "    movs    r2, #0\n"
        "    lsls    r0, r0, #8\n"             // r0 = 0x1000 (4096 bytes)
        "    str     r0, [sp, #0x60]\n"        // sp[0x60] = initial task stack size

        // Continuation entry point: sub_fc05b558_my (replaces stock 0xFC05B559)
        "    ldr     r1, =sub_fc05b558_my\n"

        "    asrs    r0, r0, #4\n"             // r0 = 0x100 (256 bytes)
        "    str     r0, [sp, #0x64]\n"        // sp[0x64] = minimum task stack size
        "    lsls    r0, r0, #5\n"             // r0 = 0x2000 (8192 bytes)
        "    str     r0, [sp, #0x68]\n"        // sp[0x68] = interrupt stack size

        // Dispatch into DryOS Kernel Initialization (ATCM 0xBFE10F79).
        // Its first call (0xBFE10F80 -> 0xFC05C570 -> 0xFC05E500(0x1B0)) re-runs
        // the Canon interrupt-controller init; it does NOT prove per-line enables
        // set before the restart are cleared (docs/RESTART_IRQ_PENDING_AUDIT.md).
        "    mov     r0, sp\n"
        "    blx     sub_fc31b408\n"

        // Clean up stack frame and return
        "    add     sp, #0x78\n"
        "    pop     {r4, pc}\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 4: Initial Task Hook (replaces 0xFC05B558)
// Replicates stock initial task initialization, then hooks startup task creator
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b558_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        "    ldr     r4, =0xfc05b600\n"        // ROM literal string "/_term" (adr @0xFC05B55A, PORT-5D)
        "    bl      sub_fc05c5bc\n"
        "    ldr     r0, =0x000080ec\n"        // literal @0xFC05B608: [0x80ec] heap size
        "    ldr     r1, [r0]\n"
        "    ldr     r0, =0x00008074\n"        // literal @0xFC05B60C: [0x8074] 0x80000 bound
        "    ldr     r0, [r0]\n"
        "    adds    r0, #0x10\n"
        "    cmp     r1, r0\n"
        "    bhs     loc_fc05b574\n"
        "    ldr     r0, =0xfc05b610\n"        // ROM literal string "USER_MEM size checking" (adr @0xFC05B56E)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b574:\n"
        "    bl      sub_fc127b3c\n"
        "    ldr     r1, =0xbfe10000\n"
        "    mov.w   r2, #-0x11111112\n"
        "    ldr     r3, =0xbfe10800\n"
        "loc_fc05b580:\n"
        "    stm     r1!, {r2}\n"
        "    cmp     r1, r3\n"
        "    blo     loc_fc05b580\n"
        "    bl      sub_fc127b4e\n"
        "    bl      sub_fc418738\n"           // dmSetup
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b598\n"
        "    ldr     r0, =0xfc05b630\n"        // ROM literal string "dmSetup" (adr @0xFC05B592)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b598:\n"
        "    bl      sub_fc05c7d4\n"           // termDriverInit
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b5a6\n"
        "    ldr     r0, =0xfc05b638\n"        // ROM literal string "termDriverInit" (adr @0xFC05B5A0)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b5a6:\n"
        "    mov     r0, r4\n"
        "    bl      sub_fc05c862\n"           // termDeviceCreate
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b5b6\n"
        "    ldr     r0, =0xfc05b648\n"        // ROM literal string "termDeviceCreate" (adr @0xFC05B5B0)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b5b6:\n"
        "    mov     r0, r4\n"
        "    bl      sub_fc05b794\n"           // stdioSetup
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b5c6\n"
        "    ldr     r0, =0xfc05b65c\n"        // ROM literal string "stdioSetup" (adr @0xFC05B5C0)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b5c6:\n"
        "    bl      sub_fc05b8d8\n"           // stdlibSetup
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b5d4\n"
        "    ldr     r0, =0xfc05b668\n"        // ROM literal string "stdlibSetup" (adr @0xFC05B5CE)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b5d4:\n"
        "    bl      sub_fc05e910\n"           // extlib_setup
        "    cmp     r0, #0\n"
        "    bge     loc_fc05b5e2\n"
        "    ldr     r0, =0xfc05b674\n"        // ROM literal string "extlib_setup" (adr @0xFC05B5DC)
        "    bl      sub_fc05b5ea\n"
        "loc_fc05b5e2:\n"
        "    pop.w   {r4, lr}\n"

        // Continue into Startup Task Creator
        "    b.w     sub_fc05b962_my\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 5: Startup Task Spawner Hook (replaces 0xFC05B962)
// Launches hooked task_Startup_my instead of stock task_Startup
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) sub_fc05b962_my(void)
{
    asm volatile (
        "    push    {r3, lr}\n"
        "    bl      sub_fc05ba68\n"
        "    bl      sub_fc079404\n"

        // Native Canon power-on button check (unmodified stock ROM handler)
        "    bl      sub_fc1284ac\n"
        "    cbnz    r0, loc_fc05b978\n"
        "    bl      sub_fc05ba56\n"
        "loc_fc05b976:\n"
        "    b       loc_fc05b976\n"          // Safe halt if shutdown requested

        "loc_fc05b978:\n"
        "    blx     sub_fc31b460\n"
        "    ldr     r1, =0x006ce000\n"
        "    movs    r0, #0\n"
        "    bl      sub_fc382c8c\n"

        // Spawn hooked task_Startup_my
        "    movs    r3, #0\n"
        "    str     r3, [sp]\n"
        "    ldr     r3, =task_Startup_my\n"   // Entry point of hooked task_Startup
        "    movs    r2, #0\n"                 // Default stack size
        "    movs    r1, #0x19\n"              // Task priority 25
        "    ldr     r0, =0xfc05b9a0\n"        // ROM literal string "Startup"
        "    blx     sub_fc31bbc4\n"           // DryOS CreateTask

        "    movs    r0, #0\n"
        "    pop     {r3, pc}\n"
    );
}

// -----------------------------------------------------------------------------
// Stage 6: Patched task_Startup (replaces 0xFC05B8FC)
// CRITICAL: Omits StartDiskboot (0xFC05BBEA) to prevent infinite reload loop!
// Spawns CHDK SpyTask after Canon driver setup, then continues in stock firmware
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline)) task_Startup_my(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        "    bl      sub_fc0d0150\n"
        "    bl      sub_fc05ba34\n"
        "    bl      sub_fc05bb94\n"
        "    bl      sub_fc418eec\n"

        // ---------------------------------------------------------------------
        // RESTART-SD-1: SD1stInit Task Creation (replicates StartDiskboot gate)
        // Stock StartDiskboot (0xFC05BBEA) spawns "SD1stInit" via veneer 0xFC31B1F4
        // before loading DISKBOOT.BIN. Omitting StartDiskboot prevents reload loop,
        // but previously left SD1stInit unspawned.
        // Replicate stock gate (sub_fc05c4e0(0) bit 0 == 0) and call creator veneer.
        // ---------------------------------------------------------------------
        "    movs    r0, #0\n"
        "    bl      sub_fc05c4e0\n"
        "    lsls    r0, r0, #31\n"
        "    bne     1f\n"
        "    blx     sub_fc31b1f4\n"
        "1:\n"

        "    bl      sub_fc0bba02\n"
        "    bl      sub_fc0d046c\n"
        "    bl      sub_fc05bcdc\n"
        "    bl      sub_fc05bb24\n"
        "    bl      sub_fc418f2a\n"
        "    bl      sub_fc090674\n"
        "    bl      sub_fc0d0472\n"

        // Launch unmodified stock task_PhySw (keyboard task hook remains disabled)
        "    bl      sub_fc1283d2\n"

        // ---------------------------------------------------------------------
        // CHDK SpyTask Completely Disabled for First-Boot Hardening (PORT-1C.2)
        // Prevents premature thread execution and 10-second timeout unhooked crash.
        // No CHDK keyboard, GUI, filesystem, or capture tasks are spawned.
        // ---------------------------------------------------------------------
        // "    bl      CreateTask_spytask\n"

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

        // Record Stage 3 (Startup Continuation) in Boot Witness
        "    bl      witness_record_continuation\n"

        // Restore registers and continue in stock Canon firmware
        "    pop.w   {r4, lr}\n"
        "    b.w     sub_fc0d0126\n"
    );
}
#if defined(G3X_TRACE) && G3X_TRACE

// -----------------------------------------------------------------------------
// PORT-17 stage markers (trace build only; this whole block and the branch in
// boot() at boot_prototype.c:155-160 are compiled out when G3X_TRACE is 0 or
// undefined, so the tracing-off preprocessed source is unchanged).
//
// RELOC (G3X_STAGE_RELOC): boot() branches here instead of sub_fc05b3c8_my
// right after the Canon BSS zeroing loop completes (boot_prototype.c:144-153;
// docs/PORT17_TRACE_EVIDENCE.md:205-251, 256).
//
// ENTRY (G3X_STAGE_ENTRY): ENTRY timing is post-BSS, emitted as the first record
// at the same post-BSS point, not boot() entry (boot_prototype.c:89-91).
// Reason: boot() reaches sub_fc02007e (boot_prototype.c:98) with r0-r3 still
// holding the sp setup and startup() values, and the register-input contract of
// sub_fc02007e is not recorded here or in docs/PORT16_FIRSTBOOT_U_TRIAGE.md:53;
// an AAPCS C call before it would clobber r0-r3, r12 and lr.
// At the post-BSS point the next routine, sub_fc05b3c8_my, saves lr and calls C
// (witness_record_core, boot_prototype.c:171-174) before it reads any argument
// register, so a C call here leaves its inputs unchanged. Ring survival: the
// ring is in CHDK .bss, which startup() zeroes before it calls boot()
// (chdk-port/platform/g3x/main.c:17-20), and the Canon BSS loop stops at
// 0x003489B4 = MEMISOSTART (boot_prototype.c:144-147), below the CHDK image.
// An earlier ENTRY marker stays open under Q-P17-01.
//
// TASK_HOOK (G3X_STAGE_TASK_HOOK): TODO (Q-P17-01, Q-P17-04), no call site.
// CHDK SpyTask is disabled for first-boot hardening (boot_prototype.c:415-420).
// KBD (G3X_STAGE_KBD): TODO (Q-P17-01), no call site. The keyboard hook is
// disabled; stock task_PhySw runs unhooked (boot_prototype.c:13, 412-413).
// DISPLAY (G3X_STAGE_DISPLAY): TODO (Q-P17-01), no call site. The display hook
// is disabled (boot_prototype.c:13); no framebuffer hook exists in this file.
//
// Placed in section .g3x_trace_text (trace text section), which the trace
// link script puts after .data, so boot_witness keeps its PORT-16 address in
// the trace build too.
// -----------------------------------------------------------------------------
void __attribute__((naked,noinline,section(".g3x_trace_text"))) g3x_trace_boot_post_bss(void)
{
    asm volatile (
        "    push    {r4, lr}\n"
        "    bl      g3x_trace_mark_entry\n"
        "    bl      g3x_trace_mark_reloc\n"
        "    pop.w   {r4, lr}\n"
        "    b.w     sub_fc05b3c8_my\n"
    );
}
#endif
