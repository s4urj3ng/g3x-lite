// G3X keyboard mapping foundation (Full Build)
// Supported by UI-001B-1 physical hardware verification (docs/UI001B1_HARDWARE_RESULT.md)
// and ROM physw_event_table at 0xFC66C948.
//
// PORT-41: Standard CHDK build adapted from sibling g7x (sub/100d) and g5x
// Sibling citations:
// - chdk-port/platform/g7x/kbd.c:26-38, 57-82, 115-139
// - chdk-port/platform/g5x/kbd.c:28-86

#include "lolevel.h"
#include "platform.h"
#include "keyboard.h"
#include "kbd_common.h"
#include "camera_info.h"

long kbd_new_state[3] = { 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF };
long kbd_prev_state[3] = { 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF };
long kbd_mod_state[3] = { 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF };

extern void _GetKbdState(long*);

int get_usb_bit()
{
    long usb_physw[3];
    usb_physw[USB_IDX] = 0;
    _kbd_read_keys_r2(usb_physw);
    return ((usb_physw[USB_IDX] & USB_MASK) == USB_MASK);
}

// KeyMap table
// Hardware verification classifications:
//   PROVISIONALLY VERIFIED: KEY_UP (2 test runs + negative control D0=0)
//   HARDWARE OBSERVED: KEY_DOWN, KEY_RIGHT, KEY_LEFT, KEY_MENU, KEY_DISPLAY, KEY_WIFI, KEY_VIDEO
//   HYPOTHESIZED (NOT YET HARDWARE VERIFIED): KEY_SET (table index 9, bit 9), KEY_SHOOT_HALF, KEY_SHOOT_FULL
KeyMap keymap[] = {
    { 0, KEY_SHOOT_FULL      ,0x00040001 }, // ROM table 0xFC66C948 idx 0/16, levent 0x01
    { 0, KEY_SHOOT_HALF      ,0x00040000 }, // ROM table 0xFC66C948 idx 16, levent 0x00
    { 0, KEY_SHOOT_FULL_ONLY ,0x00000001 }, // ROM table 0xFC66C948 idx 0, levent 0x01
    { 0, KEY_VIDEO           ,0x00000008 }, // HW Observed: D0=0x00000008, table idx 3, levent 0x02
    { 0, KEY_MENU            ,0x00000010 }, // HW Observed: D0=0x00000010, table idx 4, levent 0x14
    { 0, KEY_UP              ,0x00000020 }, // HW Verified: D0=0x00000020, table idx 5, levent 0x06
    { 0, KEY_DOWN            ,0x00000040 }, // HW Observed: D0=0x00000040, table idx 6, levent 0x07
    { 0, KEY_RIGHT           ,0x00000080 }, // HW Observed: D0=0x00000080, table idx 7, levent 0x09
    { 0, KEY_LEFT            ,0x00000100 }, // HW Observed: D0=0x00000100, table idx 8, levent 0x08
    { 0, KEY_SET             ,0x00000200 }, // ROM table idx 9, levent 0x0a (unverified on HW due to script trigger)
    { 0, KEY_DISPLAY         ,0x00001000 }, // HW Observed: D0=0x00001000, table idx 11, levent 0x0d
    { 0, KEY_WIFI            ,0x00002000 }, // HW Observed: D0=0x00002000, table idx 12, levent 0x103 (Phone Connect)
    { 0, KEY_PLAYBACK        ,0x00010000 }, // ROM table idx 14, levent 0x101
    { 0, KEY_POWER           ,0x00020000 }, // ROM table idx 15, levent 0x100
    { 0, 0, 0 }
};

extern void _kbd_p1_f_cont(void);

long __attribute__((naked,noinline)) wrap_kbd_p1_f()
{
    asm volatile (
        "push    {r1-r7, lr}\n"
        "movs    r4, #0\n"
        "bl      my_kbd_read_keys\n"
        "b       _kbd_p1_f_cont\n"
    );
    return 0;
}

int get_dial_hw_position(int dial)
{
    extern int _get_dial_hw_position(int dial);
    return _get_dial_hw_position(dial) & ~3;
}

int get_jogdial_counter()
{
    return get_dial_hw_position(4);
}

long get_jogdial_direction(void)
{
    static int new_jogdial = 0, old_jogdial = 0;
    old_jogdial = new_jogdial;
    new_jogdial = get_jogdial_counter();
    if (old_jogdial > new_jogdial) return JOGDIAL_LEFT;
    else if (old_jogdial < new_jogdial) return JOGDIAL_RIGHT;
    else return 0;
}

/*
 * PORT-41 Short-Press Power-On Fix:
 * - physw_status 0x40DAC (0x00040DAC)
 * - Power bit 17 (0x00020000), Playback bit 16 (0x00010000)
 * - physw_sleep_delay: 10 ms
 * - Start cause at 0x9BD0 (0x00009BD0)
 * - Power-cut bypass at sub_fc05b962 (sub_fc05b962_my in boot.c)
 * - On Power start (bit 19 0x00080000 set, 0, or default), restore 0x00080000
 *   so camera boots in shooting mode rather than Playback.
 * - Fake only Power bit 17 (0x00020000) in physw_status[0] (0x00040DAC).
 * - After 200 polls (~2 seconds at 10 ms/poll), release override.
 * - Pressing Power button later turns camera off normally.
 * - ALT is off at boot (camera_info.state.gui_mode = 0).
 * - Namespaced symbols (g3x_full_*) prevent collisions with candidate builders.
 */
#define G3X_ADDR_STARTCAUSE             0x00009BD0
#define G3X_STARTCAUSE_POWER            0x00080000  // (1u << 19)
#define G3X_STARTCAUSE_PLAYBACK         0x00100000  // (1u << 20)
#define G3X_KEY_POWER_BIT               0x00020000  // Bit 17
#define G3X_KEY_PLAYBACK_BIT            0x00010000  // Bit 16
#define G3X_SHORTPRESS_MARGIN_POLLS     200         // 200 polls @ 10 ms = 2.0 s

volatile unsigned int g3x_full_saved_start_cause = 0;
volatile int g3x_full_shortpress_active = 0;
volatile int g3x_full_shortpress_margin_polls = 0;
volatile unsigned int g3x_full_selected_button_bit = 0;

int physw0_override;

void my_kbd_read_keys()
{
    if (kbd_update_key_state())
        physw0_override = physw_status[0];
    else
        physw0_override = -1;
    kbd_update_physw_bits();

    if (g3x_full_shortpress_active) {
        if (g3x_full_shortpress_margin_polls > 0) {
            g3x_full_shortpress_margin_polls--;
            extern long physw_status[3];
            physw_status[0] &= ~g3x_full_selected_button_bit;
            *(volatile unsigned int *)G3X_ADDR_STARTCAUSE = g3x_full_saved_start_cause;
        } else {
            g3x_full_shortpress_active = 0;
        }
    }
}

void kbd_fetch_data(long *dst)
{
    _GetKbdState(dst);
    _kbd_read_keys_r2(dst);
}

void g3x_full_shortpress_boot_entry_hook(void)
{
    volatile unsigned int * const raw_cause = (volatile unsigned int *)G3X_ADDR_STARTCAUSE;
    g3x_full_saved_start_cause = *raw_cause;

    if (g3x_full_saved_start_cause & G3X_STARTCAUSE_PLAYBACK) {
        g3x_full_selected_button_bit = G3X_KEY_PLAYBACK_BIT;
    } else {
        // Power start, 0, or unknown -> restore shooting mode start cause 0x00080000 and fake only Power bit 17
        g3x_full_saved_start_cause = G3X_STARTCAUSE_POWER;
        g3x_full_selected_button_bit = G3X_KEY_POWER_BIT;
    }
    g3x_full_shortpress_active = 1;
    g3x_full_shortpress_margin_polls = G3X_SHORTPRESS_MARGIN_POLLS;
}

void g3x_full_shortpress_post_bss_hook(void)
{
    *(volatile unsigned int *)G3X_ADDR_STARTCAUSE = g3x_full_saved_start_cause;
    extern long physw_status[3];
    physw_status[0] &= ~g3x_full_selected_button_bit;
}

void __attribute__((noinline)) mykbd_task()
{
    extern long physw_run;
    extern long physw_sleep_delay;
    extern void _SleepTask(long);
    extern void _ExitTask(void);
    extern void _kbd_p2_f(void);

    // ALT is off at boot
    camera_info.state.gui_mode = 0;

    while (physw_run) {
        _SleepTask(physw_sleep_delay);

        if (wrap_kbd_p1_f() == 1) {
            _kbd_p2_f();
        }
    }

    _ExitTask();
}
