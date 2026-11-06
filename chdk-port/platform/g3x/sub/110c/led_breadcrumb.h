/*
 * PORT-23 T2b / PORT-25 T3: LED breadcrumb helpers for Canon PowerShot G3 X (GM1.10C).
 *
 * Hardware facts VERIFIED on camera (owner, 2026-11-01):
 * - MMIO 0xD20B0884 is the green LED register.
 * - Writing 0x004D0002 turns the green LED ON.
 * - Writing 0x004C0003 turns the green LED OFF.
 * - Loader entry prologue at 0x8000 runs.
 * - A 0x06000000 stall and a 0x00600000 stall both ended with the camera dark.
 *
 * Design constraints:
 * - This header defines NO symbols unless LED_BREADCRUMB or LED_LADDER is defined.
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

// PORT-25 Frame Timing Configuration (under 1000 ms whole-frame post-arming):
// Clock assumption: DIGIC 6 Cortex-R4 CPU core clock running at nominal ~150-250 MHz
// (2-3 CPU cycles per iteration for 'subs r2, #1; bne').
// At 200 MHz, 3 cycles/iteration: 6,291,456 iterations ~ 94.4 ms (~100 ms fast bound).
// At 150 MHz, 3 cycles/iteration: 6,291,456 iterations ~ 125.8 ms (nominal bound).
// At 66.6 MHz reference clock: 6,291,456 iterations ~ 283 ms (~300 ms slow conservative bound).
//
// Frame Timing Configuration with Preemption Tolerance (>= 50 ms difference at slow bound):
// ON pulse delay:       0x00100000 (1,048,576 iterations) -> 50.0 ms slow / 20.97 ms nom / 15.73 ms fast
// Pulse OFF gap:        0x00050000 (  327,680 iterations) -> 15.625 ms slow / 6.55 ms nom / 4.91 ms fast
// Inter-digit gap:      0x00200000 (2,097,152 iterations) -> 100.0 ms slow / 41.94 ms nom / 31.46 ms fast
// Frame-end gap:        0x00400000 (4,194,304 iterations) -> 200.0 ms slow / 83.89 ms nom / 62.91 ms fast
//
// Separator differences at slow bound:
//   Digit gap - Pulse gap = 100.0 ms - 15.625 ms = 84.375 ms >= 50 ms preemption tolerance.
//   Frame gap - Digit gap = 200.0 ms - 100.0 ms = 100.0 ms >= 50 ms preemption tolerance.
// Every single LED-ON pulse is strictly <= 150 ms (50.0 ms at slow bound, 150 ms headroom below 200 ms cap).
// Whole-frame duration for post-arming stages (Codes 41..44) is strictly < 1000 ms at slow bound:
// Code 41: 712.50 ms slow / 298.80 ms nom / 224.12 ms fast
// Code 42: 778.125 ms slow / 326.32 ms nom / 244.75 ms fast
// Code 43: 843.75 ms slow / 353.84 ms nom / 265.39 ms fast
// Code 44: 909.375 ms slow / 381.36 ms nom / 286.02 ms fast

#define G3X_FRAME_ON_DELAY     0x00100000
#define G3X_FRAME_OFF_DELAY    0x00050000
#define G3X_FRAME_DIGIT_GAP    0x00200000
#define G3X_FRAME_END_GAP      0x00400000

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

// Single pulse within a framed stage code:
// Turns LED ON (0x004D0002), waits G3X_FRAME_ON_DELAY (0x00100000 = 50 ms slow bound <= 150 ms),
// turns LED OFF (0x004C0003), waits G3X_FRAME_OFF_DELAY (0x00050000 = 15.625 ms slow bound).
// IRQ is masked (cpsid i) strictly between the LED-ON store and the LED-OFF store,
// restoring saved CPSR immediately after the OFF store. OFF gaps remain unmasked.
#define LADDER_PULSE_ON_OFF \
    "    movw    r1, #0x0002\n" \
    "    movt    r1, #0x004d\n" \
    "    mrs     r3, cpsr\n" \
    "    cpsid   i\n" \
    "    str     r1, [r0]\n" \
    "    dsb     sy\n" \
    "    mov.w   r2, #0x00100000\n" \
    "1:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     1b\n" \
    "    movw    r1, #0x0003\n" \
    "    movt    r1, #0x004c\n" \
    "    str     r1, [r0]\n" \
    "    dsb     sy\n" \
    "    msr     cpsr_cxsf, r3\n" \
    "    mov.w   r2, #0x00050000\n" \
    "2:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     2b\n"

#define LADDER_DIGIT_GAP \
    "    mov.w   r2, #0x00200000\n" \
    "3:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     3b\n"

#define LADDER_FRAME_END \
    "    mov.w   r2, #0x00400000\n" \
    "4:\n" \
    "    subs    r2, r2, #1\n" \
    "    bne     4b\n"

#define LADDER_PULSES_1 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_2 LADDER_PULSES_1 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_3 LADDER_PULSES_2 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_4 LADDER_PULSES_3 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_5 LADDER_PULSES_4 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_6 LADDER_PULSES_5 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_7 LADDER_PULSES_6 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_8 LADDER_PULSES_7 LADDER_PULSE_ON_OFF
#define LADDER_PULSES_9 LADDER_PULSES_8 LADDER_PULSE_ON_OFF

#define CORE_LADDER_FRAME(tens, units) \
    "    b.w     98f\n" \
    "    .ltorg\n" \
    "98:\n" \
    "    push    {r0, r1, r2, r3, r12, lr}\n" \
    "    movw    r0, #0x0884\n" \
    "    movt    r0, #0xd20b\n" \
    LADDER_PULSES_##tens \
    LADDER_DIGIT_GAP \
    LADDER_PULSES_##units \
    LADDER_FRAME_END \
    "    pop     {r0, r1, r2, r3, r12, lr}\n"

#define CORE_LADDER_PULSE_11 CORE_LADDER_FRAME(1, 1)
#define CORE_LADDER_PULSE_12 CORE_LADDER_FRAME(1, 2)
#define CORE_LADDER_PULSE_13 CORE_LADDER_FRAME(1, 3)
#define CORE_LADDER_PULSE_14 CORE_LADDER_FRAME(1, 4)
#define CORE_LADDER_PULSE_15 CORE_LADDER_FRAME(1, 5)

#define CORE_LADDER_PULSE_21 CORE_LADDER_FRAME(2, 1)
#define CORE_LADDER_PULSE_22 CORE_LADDER_FRAME(2, 2)
#define CORE_LADDER_PULSE_23 CORE_LADDER_FRAME(2, 3)
#define CORE_LADDER_PULSE_24 CORE_LADDER_FRAME(2, 4)
#define CORE_LADDER_PULSE_25 CORE_LADDER_FRAME(2, 5)
#define CORE_LADDER_PULSE_26 CORE_LADDER_FRAME(2, 6)
#define CORE_LADDER_PULSE_27 CORE_LADDER_FRAME(2, 7)
#define CORE_LADDER_PULSE_28 CORE_LADDER_FRAME(2, 8)
#define CORE_LADDER_PULSE_29 CORE_LADDER_FRAME(2, 9)

// Under the Single-Emitter Rule, at any moment only one execution context emits
// LED frames. The parent Initial Task finishes emitting before CreateTask is called.
// The child Startup Task is the sole emitter once created and emits directly.
// No cross-context flags, replay queues, or bitmasks are used.
#define CHILD_LADDER_FRAME(tens, units) CORE_LADDER_FRAME(tens, units)

#define CHILD_LADDER_PULSE_31 CORE_LADDER_FRAME(3, 1)
#define CHILD_LADDER_PULSE_32 CORE_LADDER_FRAME(3, 2)
#define CHILD_LADDER_PULSE_33 CORE_LADDER_FRAME(3, 3)
#define CHILD_LADDER_PULSE_34 CORE_LADDER_FRAME(3, 4)
#define CHILD_LADDER_PULSE_35 CORE_LADDER_FRAME(3, 5)

#define CHILD_LADDER_PULSE_41 CORE_LADDER_FRAME(4, 1)
#define CHILD_LADDER_PULSE_42 CORE_LADDER_FRAME(4, 2)
#define CHILD_LADDER_PULSE_43 CORE_LADDER_FRAME(4, 3)
#define CHILD_LADDER_PULSE_44 CORE_LADDER_FRAME(4, 4)

#define CHILD_LADDER_PULSE_FAIL CORE_LADDER_PULSE_28
#define CHILD_LADDER_PULSE_HALT CORE_LADDER_PULSE_29

#define CORE_LADDER_PULSE_31 CHILD_LADDER_PULSE_31
#define CORE_LADDER_PULSE_32 CHILD_LADDER_PULSE_32
#define CORE_LADDER_PULSE_33 CHILD_LADDER_PULSE_33
#define CORE_LADDER_PULSE_34 CHILD_LADDER_PULSE_34
#define CORE_LADDER_PULSE_35 CHILD_LADDER_PULSE_35

#define CORE_LADDER_PULSE_41 CHILD_LADDER_PULSE_41
#define CORE_LADDER_PULSE_42 CHILD_LADDER_PULSE_42
#define CORE_LADDER_PULSE_43 CHILD_LADDER_PULSE_43
#define CORE_LADDER_PULSE_44 CHILD_LADDER_PULSE_44

#define CORE_LADDER_PULSE_FAIL CORE_LADDER_PULSE_28
#define CORE_LADDER_PULSE_HALT CORE_LADDER_PULSE_29

#else

#define CHILD_LADDER_FRAME(tens, units) ""
#define CHILD_LADDER_PULSE_31 ""
#define CHILD_LADDER_PULSE_32 ""
#define CHILD_LADDER_PULSE_33 ""
#define CHILD_LADDER_PULSE_34 ""
#define CHILD_LADDER_PULSE_35 ""
#define CHILD_LADDER_PULSE_41 ""
#define CHILD_LADDER_PULSE_42 ""
#define CHILD_LADDER_PULSE_43 ""
#define CHILD_LADDER_PULSE_44 ""
#define CHILD_LADDER_PULSE_FAIL ""
#define CHILD_LADDER_PULSE_HALT ""

#define CORE_LADDER_PULSE_11 ""
#define CORE_LADDER_PULSE_12 ""
#define CORE_LADDER_PULSE_13 ""
#define CORE_LADDER_PULSE_14 ""
#define CORE_LADDER_PULSE_15 ""
#define CORE_LADDER_PULSE_21 ""
#define CORE_LADDER_PULSE_22 ""
#define CORE_LADDER_PULSE_23 ""
#define CORE_LADDER_PULSE_24 ""
#define CORE_LADDER_PULSE_25 ""
#define CORE_LADDER_PULSE_26 ""
#define CORE_LADDER_PULSE_27 ""
#define CORE_LADDER_PULSE_28 ""
#define CORE_LADDER_PULSE_29 ""
#define CORE_LADDER_PULSE_31 ""
#define CORE_LADDER_PULSE_32 ""
#define CORE_LADDER_PULSE_33 ""
#define CORE_LADDER_PULSE_34 ""
#define CORE_LADDER_PULSE_35 ""
#define CORE_LADDER_PULSE_41 ""
#define CORE_LADDER_PULSE_42 ""
#define CORE_LADDER_PULSE_43 ""
#define CORE_LADDER_PULSE_44 ""
#define CORE_LADDER_PULSE_FAIL ""
#define CORE_LADDER_PULSE_HALT ""

#endif /* LED_LADDER */

#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)

/* ============================================================================
 * PORT-32 Opt-In Resident Heartbeat Candidate (G3X_RESIDENT=1)
 *
 * Every firmware address is cited to a validated PORT-24/25/27/29/30/31 manifest:
 * - 0x00368680: Raised DryOS heap start (new_sa)
 *   Manifest: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json (PORT27-ROM-HEAP-SETUP)
 * - 0xFCEF3488: DryOS CreateTask ROM entry (Thumb-2, 0xFCEF3488..0xFCEF34F9)
 *   Manifest: evidence/port31_manifest.json (PORT29-ROM-CREATETASK)
 *             evidence/port29_manifest.json (PORT29-ROM-CREATETASK)
 *             evidence/port30_manifest.json (PORT29-ROM-CREATETASK)
 * - 0xFC0D0126: Stock task_Startup continuation handoff (sub_fc0d0126)
 *   Manifest: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json (PORT27-ROM-FIRMWARE-CONT)
 *             docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json (PORT25-ROM-FIRMWARE-CONT)
 * - 0xFC31BF84: DryOS SleepTask ARM veneer (0xFC31BF84..0xFC31BF8F -> ATCM 0xBFE14969)
 *   Manifest: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json (PORT27-ROM-SLEEPTASK-VENEER,
 *             PORT27-ROM-WATCHDOG-MODULE)
 * - 0xFCEF33B4: DryOS SleepTask Thumb-2 ROM entry (0xFCEF33A0..0xFCEF345F)
 *   Manifest: evidence/port31_manifest.json (PORT30-ROM-SLEEPTASK, PORT31-ROM-SLEEPTASK-BODY)
 * - 0xD20B0884: Rear green LED MMIO register (ON 0x004D0002, OFF 0x004C0003)
 *   Manifest: docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json (PORT25-ROM-GPIO-WRITE-MMIO)
 *             docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json (PORT24-ROM-GPIO-WRITE-MMIO)
 * ============================================================================ */

/* Raised heap base under G3X_RESIDENT=1 only
 * [VERIFIED exclusion / INFERRED runtime survival:
 *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-HEAP-SETUP] */
#define G3X_RESIDENT_HEAP_START          0x00368680

/* DryOS CreateTask ROM entry
 * [VERIFIED instruction body:
 *  evidence/port31_manifest.json: PORT29-ROM-CREATETASK] */
#define G3X_RESIDENT_CREATETASK_ADDR     0xFCEF3488

/* Stock task_Startup handoff target sub_fc0d0126
 * [VERIFIED instruction body:
 *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-FIRMWARE-CONT;
 *  docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json: PORT25-ROM-FIRMWARE-CONT] */
#define G3X_RESIDENT_HANDOFF_ADDR        0xFC0D0126

/* DryOS SleepTask veneer & ROM entry
 * [VERIFIED veneer & body; delay unit (ms) is INFERRED:
 *  docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json: PORT27-ROM-SLEEPTASK-VENEER;
 *  evidence/port31_manifest.json: PORT30-ROM-SLEEPTASK, PORT31-ROM-SLEEPTASK-BODY] */
#define G3X_RESIDENT_SLEEPTASK_VENEER    0xFC31BF84
#define G3X_RESIDENT_SLEEPTASK_ADDR      0xFCEF33B4

/* Explicit stack size copied from DIGIC 6 ports (never r2=0).
 * Stack alignment at task entry is INFERRED (no inline sp write in C task body).
 * [VERIFIED byte-count forwarding in PORT31-ROM-STACK-CALLEES;
 *  INFERRED adequacy & entry stack alignment from chdk-port/platform/g3x/sub/110c/boot.c:21-24,
 *  chdk-port/platform/g3x/sub/110c/boot_prototype.c:75-79,
 *  docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:97,115,
 *  docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:189] */
#define G3X_RESIDENT_STACK_SIZE          0x2000

/* Task priority numerically no higher-urgency than startup tasks (25 >= 25, 25 > 23)
 * [VERIFIED range check 1..32 in PORT29-ROM-CREATETASK;
 *  cited to task_Startup=25 in PORT27-ROM-STARTUP-TASKS,
 *  task_PhySw=23 in PORT25-ROM-PHYSW-TASK,
 *  chdk-port/platform/g3x/sub/110c/boot.c:21-24,
 *  chdk-port/platform/g3x/sub/110c/boot_prototype.c:75-79, 368] */
#define G3X_RESIDENT_PRIORITY            0x19

/* ~1 Hz double-short-blink heartbeat timing (delay unit: milliseconds, INFERRED)
 * Pattern: 100 ms ON, 100 ms OFF, 100 ms ON, 700 ms OFF = 1000 ms (1.0 Hz) period.
 * Distinct from PORT-25 count-coded ladder (1..7, 11..44) and stock LED behaviour. */
#define G3X_HEARTBEAT_ON_MS              100   /* INFERRED delay unit: milliseconds */
#define G3X_HEARTBEAT_GAP_MS             100   /* INFERRED delay unit: milliseconds */
#define G3X_HEARTBEAT_PAUSE_MS           700   /* INFERRED delay unit: milliseconds */

#ifndef G3X_LADDER_MMIO_ADDR
#define G3X_LADDER_MMIO_ADDR             0xD20B0884
#endif
#ifndef G3X_LADDER_ON_VAL
#define G3X_LADDER_ON_VAL                0x004D0002
#endif
#ifndef G3X_LADDER_OFF_VAL
#define G3X_LADDER_OFF_VAL               0x004C0003
#endif

static inline __attribute__((always_inline)) void g3x_resident_led_write(unsigned int val)
{
    /* Same LED MMIO register (0xD20B0884) and barrier routine as PORT-25 ladder
     * [docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json: PORT25-ROM-GPIO-WRITE-MMIO] */
    asm volatile (
        "    str     %1, [%0]\n"
        "    dsb     sy\n"
        :
        : "r" (G3X_LADDER_MMIO_ADDR), "r" (val)
        : "memory"
    );
}

static inline __attribute__((always_inline)) void g3x_resident_sleep_inferred_ms(unsigned int delay_ms)
{
    /* Calls manifest-cited SleepTask veneer 0xFC31BF84 (PORT27-ROM-SLEEPTASK-VENEER)
     * targeting SleepTask body 0xFCEF33B4 / ATCM 0xBFE14968 (PORT30-ROM-SLEEPTASK,
     * PORT31-ROM-SLEEPTASK-BODY). Delay unit (milliseconds) is INFERRED. */
    void (*sleep_fn)(unsigned int) = (void (*)(unsigned int))G3X_RESIDENT_SLEEPTASK_VENEER;
    sleep_fn(delay_ms);
}

/* Spawned after CORE_LADDER_PULSE_44 at the sub_fc0d0126 handoff point:
 * r0 = "Heartbeat" (INFERRED task name C-string role; VERIFIED TCB+0x24 store)
 * r1 = 0x19 (25)   (VERIFIED priority role; INFERRED scheduling compatibility)
 * r2 = 0x2000      (VERIFIED explicit stack byte count, never 0; INFERRED adequacy)
 * r3 = g3x_resident_heartbeat_task | 1 (VERIFIED entry store; INFERRED dispatcher call)
 * sp[0] = 0        (VERIFIED TCB+0x10 store; UNKNOWN delivery role to task entry)
 * Callee: CreateTask at 0xFCEF3488 (evidence/port31_manifest.json: PORT29-ROM-CREATETASK)
 * Register & stack preservation: saves and restores r0-r3 (push/pop {r0, r1, r2, r3})
 * and balances sp (sub/add sp, #8) before pop.w {r4, lr}; b.w sub_fc0d0126
 * (moreover sub_fc0d0126 takes no register arguments: PORT27-ROM-FIRMWARE-CONT). */
#define G3X_SPAWN_RESIDENT_HEARTBEAT \
    "    push    {r0, r1, r2, r3}\n" \
    "    sub     sp, #8\n" \
    "    movs    r3, #0\n" \
    "    str     r3, [sp, #0]\n" \
    "    ldr     r3, =g3x_resident_heartbeat_task\n" \
    "    orr     r3, r3, #1\n" \
    "    mov.w   r2, #0x2000\n" \
    "    movs    r1, #0x19\n" \
    "    adr     r0, 99f\n" \
    "    ldr     r4, =0xFCEF3488\n" \
    "    orr     r4, r4, #1\n" \
    "    blx     r4\n" \
    "    add     sp, #8\n" \
    "    pop     {r0, r1, r2, r3}\n" \
    "    b       97f\n" \
    "    .align  2\n" \
    "99:\n" \
    "    .asciz  \"Heartbeat\"\n" \
    "    .align  2\n" \
    "97:\n"

#endif /* G3X_RESIDENT */

#endif /* LED_BREADCRUMB_H */
