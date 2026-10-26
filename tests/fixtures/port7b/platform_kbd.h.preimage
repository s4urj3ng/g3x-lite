#ifndef PLATFORM_KBD_H
#define PLATFORM_KBD_H

// G3X verified key masks based on UI-001B-1 hardware observations
// Port 0: bits 0 (Shoot Full), 3 (Video), 4 (Menu), 5 (Up), 6 (Down),
//         7 (Right), 8 (Left), 9 (Set), 12 (Disp), 13 (Phone), 18 (Shoot Half)
#define KEYS_MASK0 (0x000433F9)
#define KEYS_MASK1 (0x00000000)
#define KEYS_MASK2 (0x00000000)

// Physical switch flags extracted by finsig_thumb2 from physw_event_table 0xFC66C948
#define SD_READONLY_FLAG    0x20000000 // Found @0xfc66ca58, levent 0x20a
#define SD_READONLY_IDX     1
#define USB_MASK            0x00800000 // Found @0xfc66cab8, levent 0x202
#define USB_IDX             2
#define BATTCOVER_FLAG      0x00400000 // Found @0xfc66cab0, levent 0x205
#define BATTCOVER_IDX       2
#define HOTSHOE_FLAG        0x00001000 // Found @0xfc66ca30, levent 0x204
#define HOTSHOE_IDX         1

#endif
