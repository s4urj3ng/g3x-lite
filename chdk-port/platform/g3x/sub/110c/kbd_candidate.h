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

#if defined(G3X_KBD) && (G3X_KBD == 1)

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
 * Short-press shutdown fix: hold power button state (bit 17 = 0x00020000)
 * in physw_status[0] during initial startup polls so Canon firmware completes
 * power-on initialization without cutting power. Held press continues to work.
 */
void __attribute__((noinline)) my_kbd_read_keys_candidate(void)
{
    static int pwr_hold_count = G3X_POWERON_HOLD_POLLS;

    kbd_update_key_state();
    kbd_update_physw_bits();

    if (pwr_hold_count > 0) {
        pwr_hold_count--;
        physw_status[0] |= G3X_KEY_POWER_BIT;
    }
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
