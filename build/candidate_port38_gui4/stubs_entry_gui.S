/* =============================================================================
 * PORT-35 Part B: G3X_GUI=1 minimal FINSIG stubs_entry table
 * Every entry below is from reference/finsig_gm110c/stubs_entry.S (label FINSIG)
 * or chdk-port/platform/g3x/sub/110c/stubs_entry.S.
 * File-write, file-open, file-delete, and directory firmware veneers are omitted.
 * ============================================================================= */
#include "stubs_asm.h"

DEF(ctypes                            ,0xfc616f54) // reference/finsig_gm110c/stubs_entry.S:170
DEF(physw_run                         ,0x000082bc) // reference/finsig_gm110c/stubs_entry.S:171
DEF(physw_sleep_delay                 ,0x000082c4) // reference/finsig_gm110c/stubs_entry.S:172
DEF(physw_status                      ,0x00040dac) // reference/finsig_gm110c/stubs_entry.S:173
DEF(fileio_semaphore                  ,0x000149c0) // reference/finsig_gm110c/stubs_entry.S:174
DEF(focus_len_table                   ,0xfdf317d8) // chdk-port/platform/g3x/sub/110c/stubs_entry.S:179
DEF(FlashParamsTable                  ,0xfca9129c) // reference/finsig_gm110c/stubs_entry.S:176
DEF(playrec_mode                      ,0x0000c4d4) // reference/finsig_gm110c/stubs_entry.S:177
DEF(jpeg_count_str                    ,0x0012c39c) // reference/finsig_gm110c/stubs_entry.S:178
DEF(zoom_busy                         ,0x0000bef8) // reference/finsig_gm110c/stubs_entry.S:179
DEF(focus_busy                        ,0x00014bc0) // reference/finsig_gm110c/stubs_entry.S:180
DEF(imager_active                     ,0x000086bc) // reference/finsig_gm110c/stubs_entry.S:181
DEF(canon_menu_active                 ,0x0000d2e8) // reference/finsig_gm110c/stubs_entry.S:182
DEF(file_counter_var                  ,0x00014864) // reference/finsig_gm110c/stubs_entry.S:183
DEF(active_bitmap_buffer              ,0x0000d2a4) // reference/finsig_gm110c/stubs_entry.S:186
DEF(displaytype                       ,0x00009740) // reference/finsig_gm110c/stubs_entry.S:187
DEF(bitmap_buffer                     ,0x0000d2a8) // reference/finsig_gm110c/stubs_entry.S:188
DEF(palette_control                   ,0x00015da4) // reference/finsig_gm110c/stubs_entry.S:189
DEF(palette_buffer_ptr                ,0x00015dbc) // reference/finsig_gm110c/stubs_entry.S:190
DEF(active_palette_buffer             ,0x00015db4) // reference/finsig_gm110c/stubs_entry.S:191
DEF_CONST(uiprop_count                ,0x000000d1) // reference/finsig_gm110c/stubs_entry.S:192
DEF(exmem_alloc_table                 ,0x00049040) // reference/finsig_gm110c/stubs_entry.S:193
DEF(exmem_types_table                 ,0xfce955fc) // reference/finsig_gm110c/stubs_entry.S:194
DEF_CONST(exmem_type_count            ,0x00000024) // reference/finsig_gm110c/stubs_entry.S:195

NHSTUB(AllocateUncacheableMemory              ,0xfc144471) // reference/finsig_gm110c/stubs_entry.S:197
NHSTUB(DebugAssert                            ,0x010e1001) // reference/finsig_gm110c/stubs_entry.S:201
NHSTUB(FreeUncacheableMemory                  ,0xfc14449d) // reference/finsig_gm110c/stubs_entry.S:218
NHSTUB(GetBatteryTemperature                  ,0xfc12da91) // reference/finsig_gm110c/stubs_entry.S:221
NHSTUB(GetCCDTemperature                      ,0xfc12da35) // reference/finsig_gm110c/stubs_entry.S:222
NHSTUB(GetCurrentAvValue                      ,0xfc0d8e55) // reference/finsig_gm110c/stubs_entry.S:223
NHSTUB(GetCurrentShutterSpeed                 ,0xfc144dd3) // reference/finsig_gm110c/stubs_entry.S:224
NHSTUB(GetUsableMaxAv                         ,0xfc555d21) // reference/finsig_gm110c/stubs_entry.S:225
NHSTUB(GetUsableMinAv                         ,0xfc555d0f) // reference/finsig_gm110c/stubs_entry.S:226
NHSTUB(get_nd_value                           ,0xfc493a51) // reference/finsig_gm110c/stubs_entry.S:227
NHSTUB(get_current_nd_value                   ,0xfc493a2b) // reference/finsig_gm110c/stubs_entry.S:228
NHSTUB(GetFocusLensSubjectDistance            ,0xfc3821af) // reference/finsig_gm110c/stubs_entry.S:232
NHSTUB(GetKbdState                            ,0xfc08ef67) // reference/finsig_gm110c/stubs_entry.S:234
NHSTUB(GetMemInfo                             ,0xfc610ab9) // reference/finsig_gm110c/stubs_entry.S:235
NHSTUB(GetOpticalTemperature                  ,0xfc12daeb) // reference/finsig_gm110c/stubs_entry.S:236
NHSTUB(GetParameterData                       ,0xfc275feb) // reference/finsig_gm110c/stubs_entry.S:237
NHSTUB(GetPropertyCase                        ,0xfc362f91) // reference/finsig_gm110c/stubs_entry.S:238
NHSTUB(GetSystemTime                          ,0xfc60243d) // reference/finsig_gm110c/stubs_entry.S:239
NHSTUB(GetVRAMHPixelsSize                     ,0xfc0d360b) // reference/finsig_gm110c/stubs_entry.S:240
NHSTUB(GetVRAMVPixelsSize                     ,0xfc0d3613) // reference/finsig_gm110c/stubs_entry.S:241
NHSTUB(GetZoomLensCurrentPoint                ,0xfc37deeb) // reference/finsig_gm110c/stubs_entry.S:242
NHSTUB(GetZoomLensCurrentPosition             ,0xfc37decb) // reference/finsig_gm110c/stubs_entry.S:243
NHSTUB(GiveSemaphore                          ,0xbfe15459) // reference/finsig_gm110c/stubs_entry.S:244
NHSTUB(IsStrobeChargeCompleted                ,0xfc0bcaaf) // reference/finsig_gm110c/stubs_entry.S:245
NHSTUB(LocalTime                              ,0x010e1581) // reference/finsig_gm110c/stubs_entry.S:247
NHSTUB(SetPropertyCase                        ,0xfc362e5d) // reference/finsig_gm110c/stubs_entry.S:277
NHSTUB(SleepTask                              ,0xbfe14969) // reference/finsig_gm110c/stubs_entry.S:279
NHSTUB(TakeSemaphore                          ,0xbfe153e1) // reference/finsig_gm110c/stubs_entry.S:280
NHSTUB(VbattGet                               ,0xfc0bb591) // reference/finsig_gm110c/stubs_entry.S:288
NHSTUB(_log                                   ,0x011032f8) // reference/finsig_gm110c/stubs_entry.S:291
NHSTUB(_log10                                 ,0x01103818) // reference/finsig_gm110c/stubs_entry.S:292
NHSTUB(_pow                                   ,0x01103980) // reference/finsig_gm110c/stubs_entry.S:293
NHSTUB(_sqrt                                  ,0x01105a00) // reference/finsig_gm110c/stubs_entry.S:294
NHSTUB(free                                   ,0xfc38155b) // reference/finsig_gm110c/stubs_entry.S:301
NHSTUB(kbd_p1_f                               ,0xfc12868d) // reference/finsig_gm110c/stubs_entry.S:302
NHSTUB(kbd_p1_f_cont                          ,0xfc128695) // reference/finsig_gm110c/stubs_entry.S:303
NHSTUB(kbd_p2_f                               ,0xfc12811f) // reference/finsig_gm110c/stubs_entry.S:304
NHSTUB(kbd_read_keys_r2                       ,0xfc08ee0d) // reference/finsig_gm110c/stubs_entry.S:306
NHSTUB(malloc                                 ,0xfc381525) // reference/finsig_gm110c/stubs_entry.S:308
NHSTUB(memcmp                                 ,0xfc382c01) // reference/finsig_gm110c/stubs_entry.S:309
NHSTUB(memcpy                                 ,0xfc13d68d) // reference/finsig_gm110c/stubs_entry.S:310
NHSTUB(memset                                 ,0xfc5591c9) // reference/finsig_gm110c/stubs_entry.S:311
NHSTUB(mktime_ext                             ,0xfc420545) // reference/finsig_gm110c/stubs_entry.S:312
NHSTUB(qsort                                  ,0xfc468519) // reference/finsig_gm110c/stubs_entry.S:317
NHSTUB(rand                                   ,0xfc42094f) // reference/finsig_gm110c/stubs_entry.S:318
NHSTUB(srand                                  ,0xfc420949) // reference/finsig_gm110c/stubs_entry.S:321
NHSTUB(strcat                                 ,0xfc381489) // reference/finsig_gm110c/stubs_entry.S:323
NHSTUB(strchr                                 ,0xfc13d721) // reference/finsig_gm110c/stubs_entry.S:324
NHSTUB(strcmp                                 ,0xfc382a2d) // reference/finsig_gm110c/stubs_entry.S:325
NHSTUB(strcpy                                 ,0xfc382a09) // reference/finsig_gm110c/stubs_entry.S:326
NHSTUB(strftime                               ,0x010e1689) // reference/finsig_gm110c/stubs_entry.S:327
NHSTUB(strlen                                 ,0xfc382aed) // reference/finsig_gm110c/stubs_entry.S:328
NHSTUB(strncmp                                ,0xfc420997) // reference/finsig_gm110c/stubs_entry.S:329
NHSTUB(strncpy                                ,0xfc381465) // reference/finsig_gm110c/stubs_entry.S:330
NHSTUB(strrchr                                ,0xfc13d733) // reference/finsig_gm110c/stubs_entry.S:331
NHSTUB(strtol                                 ,0xfc13d67f) // reference/finsig_gm110c/stubs_entry.S:332
NHSTUB(strtolx                                ,0xfc13d53d) // reference/finsig_gm110c/stubs_entry.S:333
NHSTUB(time                                   ,0x010e11e3) // reference/finsig_gm110c/stubs_entry.S:344
NHSTUB(vsprintf                               ,0xfc0dcc67) // reference/finsig_gm110c/stubs_entry.S:345
NHSTUB(EngDrvRead                             ,0xfc382b41) // reference/finsig_gm110c/stubs_entry.S:346
NHSTUB(PTM_GetCurrentItem                     ,0xfc35f5cb) // reference/finsig_gm110c/stubs_entry.S:347
NHSTUB(transfer_src_overlay                   ,0xfc380635) // reference/finsig_gm110c/stubs_entry.S:352
NHSTUB(bzero                                  ,0x01100b40) // reference/finsig_gm110c/stubs_entry.S:353
NHSTUB(memset32                               ,0x01100b44) // reference/finsig_gm110c/stubs_entry.S:354
NHSTUB(get_dial_hw_position                   ,0xfc118149) // reference/finsig_gm110c/stubs_entry.S:355
