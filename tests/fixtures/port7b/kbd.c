KeyMap keymap[] = {
    { 0, KEY_SHOOT_FULL      ,0x00040001 }, // ROM table 0xFC66C948 idx 0, levent 0x01
    { 0, KEY_SHOOT_HALF      ,0x00040000 }, // ROM table 0xFC66C948 idx 8, levent 0x00
    { 0, KEY_SHOOT_FULL_ONLY ,0x00000001 }, // ROM table 0xFC66C948 idx 0, levent 0x01
    { 0, KEY_VIDEO           ,0x00000008 }, // HW Observed: D0=0x00000008, table idx 12, levent 0x02
    { 0, KEY_MENU            ,0x00000010 }, // HW Observed: D0=0x00000010, table idx 4, levent 0x14
    { 0, KEY_UP              ,0x00000020 }, // HW Verified: D0=0x00000020, table idx 0, levent 0x06
    { 0, KEY_DOWN            ,0x00000040 }, // HW Observed: D0=0x00000040, table idx 1, levent 0x07
    { 0, KEY_RIGHT           ,0x00000080 }, // HW Observed: D0=0x00000080, table idx 3, levent 0x09
    { 0, KEY_LEFT            ,0x00000100 }, // HW Observed: D0=0x00000100, table idx 2, levent 0x08
    { 0, KEY_SET             ,0x00000200 }, // ROM table idx 9, levent 0x0a (unverified on HW due to script trigger)
    { 0, KEY_DISPLAY         ,0x00001000 }, // HW Observed: D0=0x00001000, table idx 5, levent 0x0d
    { 0, KEY_WIFI            ,0x00002000 }, // HW Observed: D0=0x00002000, table idx 6, levent 0x103 (Phone Connect)
    { 0, KEY_PLAYBACK        ,0x00010000 }, // ROM table idx 10, levent 0x101
    { 0, KEY_POWER           ,0x00020000 }, // ROM table idx 11, levent 0x100
    { 0, 0, 0 }
};
