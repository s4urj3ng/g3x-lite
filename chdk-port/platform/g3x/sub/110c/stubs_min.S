#include "stubs_asm.h"

DEF(levent_table, 0xFC7714F8)             // Found @0xFC0A9794 via ShowLogicalEventName_FW
#if !defined(G3X_GUI_FIX) || (G3X_GUI_FIX != 1)
DEF(opacity_buffer, 0xFC1837FC)
#endif
DEF(recreview_hold, 0x000095F0)        // Found @0xFC35251C via ShootCon_NotifyCompleteReviewHold (0x000095E0 + 0x10)
DEF(zoom_status, 0x00010D74)           // Found @0xFC0F01FC via UI ZoomCon (0x00010D64 + 0x10)
#if defined(G3X_MOVIE_STATUS) && (G3X_MOVIE_STATUS == 1)
DEF(simple_movie_status, 0x0000C0C8)   // PORT55-ROM-GET-ELAPSED-SECONDS-STATE-CHECK: mr_rec_state @ 0x0000C0C8 (*(0x0000C078 + 0x50)), verified @ 0xFC09B416
#else
DEF(simple_movie_status, 0x0000C170)   // Found @0xFC09BD60 via task_MovieRecord (0x0000C078 + 0x80 + 0x78)
#endif

FAKEDEF(video_compression_rate, 1)
FAKEDEF(canon_shoot_menu_active, 1)
