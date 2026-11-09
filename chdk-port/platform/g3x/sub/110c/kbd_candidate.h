/*
 * PORT-34: Opt-in G3X_KBD=1 candidate (task_PhySw hook, ALT toggle, short-press fix)
 * Target: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
 *
 * Sibling sources:
 * - chdk-port/platform/g7x/sub/100d/boot.c:382-407 (taskcreate_physw replacement)
 * - chdk-port/platform/g7x/kbd.c:57-82, 115-139 (mykbd_task, wrap_kbd_p1_f, jogdial stubs)
 * - chdk-port/platform/g5x/sub/100c/boot.c:479-506 (CreateTask strictly, stack 0x2000)
 */

#ifndef KBD_CANDIDATE_H
#define KBD_CANDIDATE_H

#if (defined(G3X_KBD) && (G3X_KBD == 1)) || (defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1))

#include "lolevel.h"
#include "platform.h"
#include "keyboard.h"
#include "kbd_common.h"
#include "conf.h"

/* Task parameters */
#define G3X_KBD_HEAP_START          0x00368880  /* Raised heap start for G3X_KBD=1 */
#define G3X_KBD_TASK_PRIORITY       0x17    /* Stock PhySw priority 23 */
#define G3X_KBD_TASK_STACK_SIZE     0x2000  /* Adjusted 0x800 -> 0x2000 (8192 bytes) */
#define G3X_POWERON_HOLD_POLLS      100     /* ~1-2 s button state hold during boot */

/* Citable address literals for verification */
#define G3X_ADDR_PHYSW_RUN          0x000082BC
#define G3X_ADDR_PHYSW_SLEEP_DELAY  0x000082C4
#define G3X_ADDR_PHYSW_STATUS       0x00040DAC
#define G3X_ADDR_TASKCREATE_PHYSW   0xFC1283D2
#define G3X_ADDR_TASK_PHYSW         0xFC1283AD
#define G3X_ADDR_PHYSW_NAME         0xFC12870C
#define G3X_ADDR_CREATETASK_STRICTLY 0xFC31BE8C
#define G3X_ADDR_SUB_FC087E88       0xFC087E88
#define G3X_ADDR_IS_FACTORY_MODE    0xFC079382
#define G3X_ADDR_OPLOG_START        0xFC087E2C
#define G3X_ADDR_KBD_P1_F           0xFC12868D
#define G3X_ADDR_KBD_P1_F_CONT      0xFC128695
#define G3X_ADDR_KBD_P2_F           0xFC12811F
#define G3X_ADDR_GETKBDSTATE        0xFC08EF67
#define G3X_ADDR_KBD_READ_KEYS_R2   0xFC08EE0D
#define G3X_ADDR_EXITTASK           0xBFE14C1F

/* Key bits */
#define G3X_KEY_PLAYBACK_BIT        0x00010000  /* Word 0, bit 16: Playback button */
#define G3X_KEY_POWER_BIT           0x00020000  /* Word 0, bit 17: Power button */

extern long physw_run;
extern long physw_sleep_delay;
extern long physw_status[3];
extern void _SleepTask(long msec);
extern void _ExitTask(void);
extern void _kbd_p2_f(void);
extern int kbd_is_blocked(void);

/*
 * PORT-39: Opt-in G3X_SHORTPRESS=1 candidate
 * Adapted DIGIC 6 Sibling Short-Press Power-On Handling:
 * - g7x: chdk-port/platform/g7x/kbd.c:48, 50 (Playback / Power physw bits);
 *        chdk-port/platform/g7x/kbd.c:70-82 (PhySw polling task loop)
 * - g5x: chdk-port/platform/g5x/kbd.c:118-126 (physw override);
 *        chdk-port/platform/g5x/sub/100c/boot.c:172-182 (start-mode write);
 *        chdk-port/platform/g5x/sub/100c/boot.c:411-420 (power-cut bypass sub_fc0ecf20_my);
 *        chdk-port/platform/g5x/sub/100c/boot.c:479-506 (taskcreate_physw stack 0x2000)
 *
 * Timing reference & time base:
 * - What starts the timer: early boot entry hook g3x_shortpress_boot_entry_hook()
 *   placed before the first ladder stage (CORE_LADDER_PULSE_11) at boot entry (t = 0).
 * - Pre-task window: early boot sequence and complete LED ladder run synchronously
 *   from boot entry to mykbd_task creation (~5.0 s / 5000 ms), verified on physical
 *   camera (owner trial observation, PORT-38, 2026-11: holding Power for ~5 s until
 *   LED ladder finishes powers on into CHDK candidate). [VERIFIED]
 * - Post-task margin: in mykbd_task, polling delay is paced by physw_sleep_delay loaded
 *   from 0x000082C4, where ROM literal 0xFC1283B2 initializes sleep time to 10 ms.
 *   [FINSIG/VERIFIED] Thus 1 poll in mykbd_task = 10 ms.
 * - Margin duration: 200 polls @ 10 ms/poll = 2000 ms (2.0 s, 40%) safety margin beyond the
 *   ~5 s LED ladder window, yielding total hold coverage of ~7000 ms (~7.0 s) from boot entry. [INFERRED]
 * - Release: once margin polls reach 0, g3x_shortpress_active is cleared (0) and override is
 *   released so subsequent button presses (e.g. normal Power button press to shut down) work natively. [VERIFIED]
 */
#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)

#define G3X_SHORTPRESS_LADDER_TIME_MS   5000    /* ~5 s LED ladder duration from boot entry [VERIFIED] */
#define G3X_SHORTPRESS_MARGIN_MS        2000    /* 2.0 s safety margin beyond ladder [INFERRED] */
#define G3X_SHORTPRESS_POLL_INTERVAL_MS 10      /* physw_sleep_delay = 10 ms [FINSIG/VERIFIED] */
#define G3X_SHORTPRESS_MARGIN_POLLS     (G3X_SHORTPRESS_MARGIN_MS / G3X_SHORTPRESS_POLL_INTERVAL_MS) /* 200 polls [INFERRED] */
#define G3X_SHORTPRESS_HOLD_POLLS       G3X_SHORTPRESS_MARGIN_POLLS

/*
 * Addresses and bit constants for shortpress candidate:
 * - G3X_ADDR_STARTCAUSE: 0x00009BD0 = *(0x9BC4 + 12) startup cause word [VERIFIED]
 * - G3X_STARTCAUSE_POWER: 0x00080000 = (1u << 19) Power button start cause [VERIFIED]
 * - G3X_STARTCAUSE_PLAYBACK: 0x00100000 = (1u << 20) Playback button start cause [VERIFIED]
 */
#define G3X_ADDR_STARTCAUSE             0x00009BD0
#define G3X_STARTCAUSE_POWER            (1u << 19)
#define G3X_STARTCAUSE_PLAYBACK         (1u << 20)

/* CHDK-owned state variables in .data section to survive low-RAM reinit and BSS zeroing */
volatile unsigned int g3x_saved_start_cause = 0;
volatile int g3x_shortpress_active = 0;
volatile int g3x_shortpress_margin_polls = 0;
volatile unsigned int g3x_selected_button_bit = 0;

/*
 * Discrimination function:
 * Evaluates start cause captured before low-RAM reinitialization:
 * - If Playback button bit 20 (0x00100000) is set: returns G3X_KEY_PLAYBACK_BIT (0x00010000, bit 16).
 * - Otherwise (Power button bit 19 0x00080000 set, 0, or default): returns G3X_KEY_POWER_BIT (0x00020000, bit 17).
 */
unsigned int g3x_shortpress_discriminate(unsigned int raw_cause)
{
    if (raw_cause & G3X_STARTCAUSE_PLAYBACK) {
        return G3X_KEY_PLAYBACK_BIT;
    } else {
        return G3X_KEY_POWER_BIT;
    }
}

/*
 * Early boot hook executed at boot entry before first ladder stage (CORE_LADDER_PULSE_11):
 * 1. Captures original start-cause word from 0x00009BD0 before Copy Loop 3 overwrites low RAM.
 * 2. Discriminates start cause into Playback vs Power button.
 * 3. Starts coverage window: active flag = 1, margin polls = 200.
 */
void __attribute__((noinline)) g3x_shortpress_boot_entry_hook(void)
{
    volatile unsigned int * const raw_cause = (volatile unsigned int *)G3X_ADDR_STARTCAUSE;
    g3x_saved_start_cause = *raw_cause;

    /* If neither button was recorded (e.g. 0), default to Power start */
    if ((g3x_saved_start_cause & (G3X_STARTCAUSE_PLAYBACK | G3X_STARTCAUSE_POWER)) == 0) {
        g3x_saved_start_cause = G3X_STARTCAUSE_POWER;
    }

    g3x_selected_button_bit = g3x_shortpress_discriminate(g3x_saved_start_cause);
    g3x_shortpress_active = 1;
    g3x_shortpress_margin_polls = G3X_SHORTPRESS_MARGIN_POLLS;
}

/*
 * Post-BSS hook executed right after Canon BSS is zeroed:
 * Restores saved start cause into low RAM 0x00009BD0 and clears active-low button bit in physw_status[0].
 */
void __attribute__((noinline)) g3x_shortpress_post_bss_hook(void)
{
    *(volatile unsigned int *)G3X_ADDR_STARTCAUSE = g3x_saved_start_cause;
    physw_status[0] &= ~g3x_selected_button_bit;
}

static inline void g3x_shortpress_read_keys(void)
{
    kbd_update_key_state();
    kbd_update_physw_bits();

    if (g3x_shortpress_active) {
        if (g3x_shortpress_margin_polls > 0) {
            g3x_shortpress_margin_polls--;
            /* Active-low key logic: clear bit (&= ~mask) to fake button held */
            physw_status[0] &= ~g3x_selected_button_bit;
            /* Keep start cause word populated */
            *(volatile unsigned int *)G3X_ADDR_STARTCAUSE = g3x_saved_start_cause;
        } else {
            /* Hold window expired: release override so normal Power button press turns off camera */
            g3x_shortpress_active = 0;
        }
    }
}

#endif /* G3X_SHORTPRESS */

/*
 * Short-press shutdown fix: hold power button state (bit 17 = 0x00020000)
 * in physw_status[0] during initial startup polls so Canon firmware completes
 * power-on initialization without cutting power. Held press continues to work.
 */
void __attribute__((noinline)) my_kbd_read_keys_candidate(void)
{
#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)
    g3x_shortpress_read_keys();
#else
    static int pwr_hold_count = G3X_POWERON_HOLD_POLLS;

    kbd_update_key_state();
    kbd_update_physw_bits();

    if (pwr_hold_count > 0) {
        pwr_hold_count--;
        physw_status[0] |= G3X_KEY_POWER_BIT;
    }
#endif
}

/*
 * Intercept kbd_p1_f: run CHDK key processing and jump to Canon continuation in ROM.
 * Adapted from g7x/kbd.c:57-67.
 */
long __attribute__((naked,noinline)) wrap_kbd_p1_f_candidate(void)
{
    asm volatile (
        "push    {r1-r7, lr}\n"
        "movs    r4, #0\n"
        "bl      my_kbd_read_keys_candidate\n"
        "ldr     pc, =0xFC128695\n" /* _kbd_p1_f_cont */
        ".ltorg\n"
    );
    return 0;
}

/*
 * Replacement keyboard task.
 * Adapted from g7x/kbd.c:70-82.
 */
void __attribute__((noinline)) mykbd_task(void)
{
    /* Set default ALT mode button to KEY_PLAYBACK (Playback button) if uninitialized */
    if (conf.alt_mode_button == 0) {
        conf.alt_mode_button = KEY_PLAYBACK;
    }

    while (physw_run) {
        _SleepTask(physw_sleep_delay);

        if (wrap_kbd_p1_f_candidate() == 1) {
            _kbd_p2_f();
        }
#if defined(G3X_OSD2) && (G3X_OSD2 == 1)
        g3x_osd2_kbd_redraw(kbd_is_blocked());
#endif
    }

    _ExitTask();
}

/*
 * Replacement taskcreate_physw helper.
 * Adapted from g7x sub/100d/boot.c:382-407 and g5x sub/100c/boot.c:479-506.
 */
void __attribute__((naked,noinline)) sub_fc1283d2_my(void)
{
    asm volatile (
        "push    {r3, r4, r5, lr}\n"
        "ldr     r3, =0xFC087E89\n"     /* sub_fc087e88 (Thumb) */
        "blx     r3\n"
        "ldr     r3, =0xFC079383\n"     /* sub_fc079382 IsFactoryMode_FW (Thumb) */
        "blx     r3\n"
        "cbnz    r0, 1f\n"
        "ldr     r3, =0xFC087E2D\n"     /* sub_fc087e2c OpLog.Start_FW (Thumb) */
        "blx     r3\n"
    "1:\n"
        "ldr     r4, =0x000082BC\n"     /* physw_run */
        "ldr     r0, [r4, #4]\n"        /* task handle */
        "cmp     r0, #0\n"
        "bne     2f\n"
        "movs    r3, #0\n"
        "str     r3, [sp, #0]\n"
        "ldr     r3, =mykbd_task\n"
        "movs    r1, #0x17\n"           /* priority 23 */
        "ldr     r0, =0xFC12870C\n"     /* *"PhySw" */
        "movw    r2, #0x2000\n"         /* stack size 0x2000 (8192 bytes) */
        "ldr     r5, =0xFC31BE8C\n"     /* j_CreateTaskStrictly (ARM veneer) */
        "blx     r5\n"
        "str     r0, [r4, #4]\n"
    "2:\n"
        "pop     {r3, r4, r5, pc}\n"
        ".ltorg\n"
    );
}

/* Jogdial stubs: G3X jogdial hardware addresses not in FINSIG, stubbed to pass-through */
int handle_jogdial(void)
{
    return 1;
}

void jogdial_control(int c)
{
    (void)c;
}

#endif /* G3X_KBD */

#endif /* KBD_CANDIDATE_H */
