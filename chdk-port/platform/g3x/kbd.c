// G3X keyboard mapping foundation
// Supported by UI-001B-1 physical hardware verification (docs/UI001B1_HARDWARE_RESULT.md)
// and ROM physw_event_table at 0xFC66C948.

#include "lolevel.h"
#include "platform.h"
#include "keyboard.h"
#include "kbd_common.h"

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

// NOTE: Active keyboard task interception (mykbd_task / wrap_kbd_p1_f) is
// INTENTIONALLY NOT IMPLEMENTED for CHDK-PORT-0 in accordance with review rules.
// Active task replacement requires independent review of task_PhySw lifecycle.
long __attribute__((naked,noinline)) wrap_kbd_p1_f()
{
    asm volatile (
        "push    {r1-r7, lr}\n"
        "movs    r4, #0\n"
        "bl      my_kbd_read_keys\n"
        "b       kbd_p1_f_cont_my\n"
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

int physw0_override;

void my_kbd_read_keys()
{
    if (kbd_update_key_state())
        physw0_override = physw_status[0];
    else
        physw0_override = -1;
    kbd_update_physw_bits();
}

void __attribute__((naked,noinline)) kbd_p1_f_cont_my()
{
    asm volatile (
        "pop     {r1-r7, pc}\n"
    );
}

void kbd_fetch_data(long *dst)
{
    _GetKbdState(dst);
    _kbd_read_keys_r2(dst);
}
