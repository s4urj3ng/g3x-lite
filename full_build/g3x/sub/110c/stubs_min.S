#include "stubs_asm.h"

DEF(levent_table, 0xFC7714F8)             // Found @0xFC0A9794 via ShowLogicalEventName_FW
DEF(opacity_buffer, 0xFC1837FC)
DEF(recreview_hold, 0x000095F0)        // Found @0xFC35251C via ShootCon_NotifyCompleteReviewHold (0x000095E0 + 0x10)
DEF(zoom_status, 0x00010D74)           // Found @0xFC0F01FC via UI ZoomCon (0x00010D64 + 0x10)
DEF(simple_movie_status, 0x0000C170)   // Found @0xFC09BD60 via task_MovieRecord (0x0000C078 + 0x80 + 0x78)

FAKEDEF(video_compression_rate, 1)
FAKEDEF(canon_shoot_menu_active, 1)
