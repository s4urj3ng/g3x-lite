// !!! THIS FILE IS GENERATED. DO NOT EDIT. !!!
#include "stubs_asm.h"

// Camera info:
//   Main firmware start: 0xfc020000
//   DRYOS R57 (DRYOS version 2.3, release #0057) @ 0xfc616ea0 ref @ 0xfc0359c8
//   Firmware Ver GM1.10C   // Found @ 0xfc54e080, "GM1.10C" @ 0xfc54e08d

// Values for makefile.inc
//   PLATFORMOSVER = 57
//   DIGIC = 60
//   MEMISOSTART = 0x3489b4
//   MEMBASEADDR = 0x8000
//   ARAM_HEAP_START = 0x006ce000#  Found @0xfc55888c
//   ARAM_HEAP_SIZE = 0x00022000#  Found @0xfc558866

// Detected address ranges:
// ROM      0xfc000000 - 0xfe000000 (33554432 bytes)
// RAM code 0x010e1000 - 0x01107d00 copied from 0xfcec854c ( 158976 bytes)
// TCM code 0xbfe10800 - 0xbfe17419 copied from 0xfceef24c (  27673 bytes)
// RAM data 0x00008000 - 0x0003f4f4 copied from 0xfce91058 ( 226548 bytes)
// EVEC     0x00000000 - 0x00000038 copied from 0xfc05b47c (     56 bytes)

// Zico Xtensa blobs:
// zico_0 0xbff20000 - 0xbff27938 copied from 0xfcc90278 (  31032 bytes)
// zico_1 0xbff00000 - 0xbff04b30 copied from 0xfcc97bb8 (  19248 bytes)
// zico_2 0x80a00000 - 0x80b14df0 copied from 0xfcc9c6f0 (1134064 bytes)

// Found DryOS versions:
// 0xfc616ea0 main  "DRYOS version 2.3, release #0057"
// 0xfc62cad8 other "DRYOS version 2.3, release #0057"
// 0xfcc9d8a0 other "DRYOS version 2.3, release #0057"

// Values below go in 'platform_camera.h':
//#define CAM_DRYOS         1
//#define CAM_DRYOS_2_3_R39 1 // Defined for cameras with DryOS version R39 or higher
//#define CAM_DRYOS_2_3_R47 1 // Defined for cameras with DryOS version R47 or higher
//#undef  CAM_UNCACHED_BIT
//#define CAM_UNCACHED_BIT  0x40000000 // Found @0xfc1444a0
//#define CAM_HAS_ND_FILTER 1 // Camera has ND filter
// Camera has an iris (CAM_HAS_IRIS_DIAPHRAGM default)

// physw_event_table 0xfc66c948 Found @0xfc08ee10
// Values below go in 'platform_kbd.h':
//#define SD_READONLY_FLAG    0x20000000 // Found @0xfc66ca58, levent 0x20a
//#define SD_READONLY_IDX     1
//#define USB_MASK            0x00800000 // Found @0xfc66cab8, levent 0x202
//#define USB_IDX             2
//#define BATTCOVER_FLAG      0x00400000 // Found @0xfc66cab0, levent 0x205
//#define BATTCOVER_IDX       2
//#define HOTSHOE_FLAG        0x00001000 // Found @0xfc66ca30, levent 0x204
//#define HOTSHOE_IDX         1

// Keymap values for kbd.c. Additional keys may be present, only common values included here.
// WARNING: Key name / function may vary! Values for unknown DryOS versions should not be trusted!
//KeyMap keymap[] = {
//    { 0, KEY_SHOOT_FULL      ,0x00040001 }, // Found @0xfc66c948, levent 0x01
//    { 0, KEY_SHOOT_HALF      ,0x00040000 }, // Found @0xfc66c9c8, levent 0x00
//    { 0, KEY_SHOOT_FULL_ONLY ,0x00000001 }, // Found @0xfc66c948, levent 0x01
//    { 0, KEY_VIDEO           ,0x00000008 }, // Found @0xfc66c960, levent 0x02
//    { 0, KEY_MENU            ,0x00000010 }, // Found @0xfc66c968, levent 0x14
//    { 0, KEY_UP              ,0x00000020 }, // Found @0xfc66c970, levent 0x06
//    { 0, KEY_DOWN            ,0x00000040 }, // Found @0xfc66c978, levent 0x07
//    { 0, KEY_RIGHT           ,0x00000080 }, // Found @0xfc66c980, levent 0x09
//    { 0, KEY_LEFT            ,0x00000100 }, // Found @0xfc66c988, levent 0x08
//    { 0, KEY_SET             ,0x00000200 }, // Found @0xfc66c990, levent 0x0a
//    { 0, KEY_DISPLAY         ,0x00001000 }, // Found @0xfc66c9a0, levent 0x0d
//    { 0, KEY_WIFI            ,0x00002000 }, // Found @0xfc66c9a8, levent 0x103
//    { 0, KEY_PLAYBACK        ,0x00010000 }, // Found @0xfc66c9b8, levent 0x101
//    { 0, KEY_POWER           ,0x00020000 }, // Found @0xfc66c9c0, levent 0x100
//    { 0, 0, 0 }
//};

// canon_mode_list 0xfca90f10 Found @0xfc07317c
// Check modemap values from 'platform/CAMERA/shooting.c':
// 32770  0x8002 In firmware but not in current modemap
// 32772  0x8004 In firmware but not in current modemap
// 32771  0x8003 In firmware but not in current modemap
// 32773  0x8005 In firmware but not in current modemap
//  8760  0x2238 In firmware but not in current modemap
//  8759  0x2237 In firmware but not in current modemap
//  8763  0x223b In firmware but not in current modemap
//  8764  0x223c In firmware but not in current modemap
//  8765  0x223d In firmware but not in current modemap
//  8767  0x223f In firmware but not in current modemap
//  8754  0x2232 In firmware but not in current modemap
//  8755  0x2233 In firmware but not in current modemap
//  8775  0x2247 In firmware but not in current modemap
//  8753  0x2231 In firmware but not in current modemap
// 16414  0x401e In firmware but not in current modemap
// 16416  0x4020 In firmware but not in current modemap
// 16406  0x4016 In firmware but not in current modemap
// 16953  0x4239 In firmware but not in current modemap
// 16948  0x4234 In firmware but not in current modemap
// 16950  0x4236 In firmware but not in current modemap
// 16949  0x4235 In firmware but not in current modemap
// 16453  0x4045 In firmware but not in current modemap
// 16454  0x4046 In firmware but not in current modemap
// 16459  0x404b In firmware but not in current modemap
// 33288  0x8208 In firmware but not in current modemap
// 32768  0x8000 In firmware but not in current modemap
// 33298  0x8212 In firmware but not in current modemap
// 33299  0x8213 In firmware but not in current modemap
//  2643  0x0a53 In firmware but not in current modemap
//  2652  0x0a5c In firmware but not in current modemap
//  2651  0x0a5b In firmware but not in current modemap
//  2650  0x0a5a In firmware but not in current modemap
// 33297  0x8211 In firmware but not in current modemap
//  4173  0x104d In firmware but not in current modemap
//  4174  0x104e In firmware but not in current modemap

// Known propcases
// //      PROPCASE_AFSTEP 13
// #define PROPCASE_FOCUS_STATE 18
// #define PROPCASE_AV 23
// #define PROPCASE_BV 40
// //      PROPCASE_DELTA_DIGITALGAIN 84
// #define PROPCASE_DELTA_SV 86
// //      PROPCASE_DELTA_ND 87
// //      PROPCASE_FELOCK 122
// #define PROPCASE_FLASH_ADJUST_MODE 129
// #define PROPCASE_FLASH_FIRE 130
// //      PROPCASE_HSCAPTURE 146
// #define PROPCASE_EV_CORRECTION_2 218
// #define PROPCASE_ORIENTATION_SENSOR 230
// #define PROPCASE_SV_MARKET 257
// //      PROPCASE_SVFIX 258
// #define PROPCASE_TV 274
// Guessed propset: 10

// EXMEM types:
// EXMEM_RAMDISK        0
// EXMEM_COM            1
// EXMEM_FORMATTER      2
// EXMEM_SHADING        3
// EXMEM_FAMODE         4
// EXMEM_FIRMUP         5
// EXMEM_FIRMUP_VRAM    6
// EXMEM_FIRMUP_INFLATE 7
// EXMEM_FIRMUP_PICTURESTYLE 8
// EXMEM_DVLPWORK       9
// EXMEM_EVF            10
// EXMEM_SCRIPT         11
// EXMEM_GPS            12
// EXMEM_FACEAUTH       13
// EXMEM_OHYEARLOG      14
// EXMEM_WIFI           15
// EXMEM_MULTI_PLY      16
// EXMEM_FEP            17
// EXMEM_LENS_FIRMUP    18
// EXMEM_LENS_COMPENSATION 19
// EXMEM_FILESTORE      20
// EXMEM_MOVIE_REC      21
// EXMEM_MOVIE_PLY      22
// EXMEM_WIFI_RESIZE    23
// EXMEM_PCEVF          24
// EXMEM_WIDE           25
// EXMEM_NARROW         26
// EXMEM_AUTO_GIS_MODE  27
// EXMEM_NP_GIS_MODE    28
// EXMEM_TRIPODHDR_MODE 29
// EXMEM_HSHQ_MODE      30
// EXMEM_CRAW_REC       31
// EXMEM_CREATIVE_SHOT  32
// EXMEM_BACKBLUR       33
// EXMEM_ASTRO          34
// EXMEM_PHOTO_IN_MOVIE 35

// Values below can be overridden in 'stubs_min.S':
DEF(ctypes                            ,0xfc616f54) // Found @0xfc034d14
DEF(physw_run                         ,0x000082bc) // Found @0xfc1283ae
DEF(physw_sleep_delay                 ,0x000082c4) // (0x82bc+0x8) Found @0xfc1283b2
DEF(physw_status                      ,0x00040dac) // Found @0xfc128694
DEF(fileio_semaphore                  ,0x000149c0) // Found @0xfc072842
// levent_table not found
// focus_len_table contains zoom focus lengths for use in 'get_focal_length' (main.c).
// each entry contains 1 int value, which is the zoom focus length.
// there are 201 entries in the table - set NUM_FL to 201, NUM_DATA to 1
DEF(focus_len_table                   ,0xfdf317d8) // Found via finsig_thumb2 @0xfdf317d8 (min 8800, max 220000)
DEF(FlashParamsTable                  ,0xfca9129c) // Found @0xfc073190
DEF(playrec_mode                      ,0x0000c4d4) // (0xc4d0+0x4) Found @0xfc2d7296
DEF(jpeg_count_str                    ,0x0012c39c) // Found @0xfc1f2156
DEF(zoom_busy                         ,0x0000bef8) // (0xbedc+0x1c) Found @0xfc37dca2
DEF(focus_busy                        ,0x00014bc0) // (0x14bb8+0x8) Found @0xfc3816c6
DEF(imager_active                     ,0x000086bc) // (0x86b8+0x4) Found @0xfc128be0
DEF(canon_menu_active                 ,0x0000d2e8) // (0xd2e4+0x4) Found @0xfc325012
DEF(file_counter_var                  ,0x00014864) // Found @0xfc18c13c
DEF(_nrflag                           ,0x00024a68) // (0x24a64+0x4) Found @0xfc09c6ba
DEF(av_override_semaphore             ,0x000298e4) // Found @0xfc5ff2dc
DEF(active_bitmap_buffer              ,0x0000d2a4) // (0xd264+0x40) Found @0xfc38116e
DEF(displaytype                       ,0x00009740) // (0x9700+0x40) Found @0xfc37b9c2
DEF(bitmap_buffer                     ,0x0000d2a8) // (0xd264+0x44) Found @0xfc381174
DEF(palette_control                   ,0x00015da4) // Found @0xfc33d12e
DEF(palette_buffer_ptr                ,0x00015dbc) // (0x15da4+0x18) Found @0xfc33d14a
DEF(active_palette_buffer             ,0x00015db4) // (0x15da4+0x10) Found @0xfc33d132
DEF_CONST(uiprop_count                      ,0x000000d1) // Found @0xfc2755fa
DEF(exmem_alloc_table                 ,0x00049040) // Found @0xfc091ffe
DEF(exmem_types_table                 ,0xfce955fc) // Found @0xfc092002
DEF_CONST(exmem_type_count                  ,0x00000024) // Found @0xfce955fc

NHSTUB(AllocateUncacheableMemory              ,0xfc144471) //  0
NHSTUB(Close                                  ,0xfc37b439) //  0
NHSTUB(CreateBinarySemaphore                  ,0xbfe152ed) //  0
NHSTUB(CreateTask                             ,0xbfe14a3d) //  0
NHSTUB(DebugAssert                            ,0x010e1001) //  0
NHSTUB(DeleteDirectory_Fut                    ,0xfc37ef6d) //  0
NHSTUB(DeleteFile_Fut                         ,0xfc37ef23) //  0
NHSTUB(DoAELock                               ,0xfc2a85d7) //  0
NHSTUB(DoAFLock                               ,0xfc2a8207) //  0
// ERROR: EnterToCompensationEVF is not found.             //--- ---
NHSTUB2(ExecuteEventProcedure                  ,0xfc37d5c1) //  0
// ERROR: ExitFromCompensationEVF is not found.            //--- ---
NHSTUB(ExitTask                               ,0xbfe14c1f) //  0
// ERROR: ExpCtrlTool_StartContiAE is not found.           //--- ---
// ERROR: ExpCtrlTool_StopContiAE is not found.            //--- ---
NHSTUB(Fclose_Fut                             ,0xfc37efcf) //  0
// ERROR: Feof_Fut is not found.                           //--- ---
// ERROR: Fflush_Fut is not found.                         //--- ---
NHSTUB(Fgets_Fut                              ,0xfc37f0ad) //  0
NHSTUB(Fopen_Fut                              ,0xfc37efa7) //  0
NHSTUB(Fread_Fut                              ,0xfc37f041) //  0
NHSTUB(FreeUncacheableMemory                  ,0xfc14449d) //  0
NHSTUB(Fseek_Fut                              ,0xfc37f0df) //  0
NHSTUB(Fwrite_Fut                             ,0xfc37f077) //  0
NHSTUB(GetBatteryTemperature                  ,0xfc12da91) //  0
NHSTUB(GetCCDTemperature                      ,0xfc12da35) //  0
NHSTUB(GetCurrentAvValue                      ,0xfc0d8e55) //  0
NHSTUB(GetCurrentShutterSpeed                 ,0xfc144dd3) //  0
NHSTUB(GetUsableMaxAv                         ,0xfc555d21) //  0
NHSTUB(GetUsableMinAv                         ,0xfc555d0f) //  0
NHSTUB(get_nd_value                           ,0xfc493a51) //  0
NHSTUB(get_current_nd_value                   ,0xfc493a2b) //  0
NHSTUB(GetDrive_ClusterSize                   ,0xfc37aaab) //  0
NHSTUB(GetDrive_FreeClusters                  ,0xfc37afaf) //  0
// ERROR: GetDrive_TotalClusters is not found.             //--- ---
NHSTUB(GetFocusLensSubjectDistance            ,0xfc3821af) //  0
// ERROR: GetFocusLensSubjectDistanceFromLens is not found.  //--- ---
NHSTUB(GetKbdState                            ,0xfc08ef67) //  0
NHSTUB(GetMemInfo                             ,0xfc610ab9) //  0
NHSTUB(GetOpticalTemperature                  ,0xfc12daeb) //  0
NHSTUB(GetParameterData                       ,0xfc275feb) //  0
NHSTUB(GetPropertyCase                        ,0xfc362f91) //  0
NHSTUB(GetSystemTime                          ,0xfc60243d) //  0
NHSTUB(GetVRAMHPixelsSize                     ,0xfc0d360b) //  0
NHSTUB(GetVRAMVPixelsSize                     ,0xfc0d3613) //  0
NHSTUB(GetZoomLensCurrentPoint                ,0xfc37deeb) //  0
NHSTUB(GetZoomLensCurrentPosition             ,0xfc37decb) //  0
NHSTUB(GiveSemaphore                          ,0xbfe15459) //  0
NHSTUB(IsStrobeChargeCompleted                ,0xfc0bcaaf) //  0
NHSTUB(LEDDrive                               ,0xfc5572b9) //  0
NHSTUB(LocalTime                              ,0x010e1581) //  0
// ERROR: LockMainPower is not found.                      //--- ---
NHSTUB(MakeDirectory_Fut                      ,0xfc37b723) //  0
NHSTUB(MoveFocusLensToDistance                ,0xfc604b03) //  0
NHSTUB(MoveIrisWithAv                         ,0xfc5ff2c9) //  0
NHSTUB(MoveZoomLensWithPoint                  ,0xfc5ffcb9) //  0
NHSTUB(Open                                   ,0xfc37b3b5) //  0
NHSTUB(PB2Rec                                 ,0xfc32326d) //  0
NHSTUB(PT_MoveDigitalZoomToWide               ,0xfc2a7ac7) //  0
NHSTUB(PT_MoveOpticalZoomAt                   ,0xfc5581e9) //  0
NHSTUB(MoveOpticalZoomAt                      ,0xfc2a78fd) //  0
NHSTUB(PT_PlaySound                           ,0xfc35fc39) //  0
// ERROR: PostLogicalEventForNotPowerType is not found.    //--- ---
// ERROR: PostLogicalEventToUI is not found.               //--- ---
NHSTUB(PutInNdFilter                          ,0xfc605375) //  0
NHSTUB(PutOutNdFilter                         ,0xfc60539b) //  0
NHSTUB(Read                                   ,0xfc418d61) //  0
NHSTUB(ReadFastDir                            ,0xfc491eb5) //  0
NHSTUB(Rec2PB                                 ,0xfc3232ad) //  0
// ERROR: RenameFile_Fut is not found.                     //--- ---
// ERROR: Restart is not found.                            //--- ---
NHSTUB(ScreenLock                             ,0xfc3810f1) //  0
NHSTUB(ScreenUnlock                           ,0xfc381127) //  0
NHSTUB(SetAE_ShutterSpeed                     ,0xfc6123bd) //  0
// ERROR: SetAutoShutdownTime is not found.                //--- ---
NHSTUB(SetCurrentCaptureModeType              ,0xfc349a11) //  0
// ERROR: SetFileAttributes is not found.                  //--- ---
// ERROR: SetFileTimeStamp is not found.                   //--- ---
NHSTUB(SetLogicalEventActive                  ,0xfc354607) //  0
// ERROR: SetParameterData is not found.                   //--- ---
NHSTUB(SetPropertyCase                        ,0xfc362e5d) //  0
NHSTUB(SetScriptMode                          ,0xfc35463f) //  0
NHSTUB(SleepTask                              ,0xbfe14969) //  0
NHSTUB(TakeSemaphore                          ,0xbfe153e1) //  0
NHSTUB(TurnOffBackLight                       ,0xfc37c449) //  0
NHSTUB(TurnOnBackLight                        ,0xfc37c3ef) //  0
NHSTUB(TurnOnDisplay                          ,0xfc18317f) //  0
NHSTUB(TurnOffDisplay                         ,0xfc183191) //  0
NHSTUB(UnlockAE                               ,0xfc2a85f5) //  0
NHSTUB(UnlockAF                               ,0xfc2a8237) //  0
// ERROR: UnlockMainPower is not found.                    //--- ---
NHSTUB(VbattGet                               ,0xfc0bb591) //  0
NHSTUB(Write                                  ,0xfc37b471) //  0
// ERROR: WriteSDCard is not found.                        //--- ---
NHSTUB(_log                                   ,0x011032f8) //  0
NHSTUB(_log10                                 ,0x01103818) //  0
NHSTUB(_pow                                   ,0x01103980) //  0
NHSTUB(_sqrt                                  ,0x01105a00) //  0
NHSTUB(add_ptp_handler                        ,0xfc322953) //  0
// ERROR: apex2us is not found.                            //--- ---
NHSTUB(close                                  ,0xfc418c5b) //  0
NHSTUB(exmem_alloc                            ,0xfc092537) //  0
NHSTUB(exmem_ualloc                           ,0xfc092441) //  0
NHSTUB(exmem_ufree                            ,0xfc0924fb) //  0
NHSTUB(free                                   ,0xfc38155b) //  0
NHSTUB(kbd_p1_f                               ,0xfc12868d) //  0
NHSTUB(kbd_p1_f_cont                          ,0xfc128695) //  0
NHSTUB(kbd_p2_f                               ,0xfc12811f) //  0
NHSTUB(kbd_read_keys                          ,0xfc127f8d) //  0
NHSTUB(kbd_read_keys_r2                       ,0xfc08ee0d) //  0
NHSTUB(lseek                                  ,0xfc37b595) //  0
NHSTUB(malloc                                 ,0xfc381525) //  0
NHSTUB(memcmp                                 ,0xfc382c01) //  0
NHSTUB(memcpy                                 ,0xfc13d68d) //  0
NHSTUB(memset                                 ,0xfc5591c9) //  0
NHSTUB(mktime_ext                             ,0xfc420545) //  0
NHSTUB(open                                   ,0xfc418beb) //  0
NHSTUB(OpenFastDir                            ,0xfc491e15) //  0
NHSTUB(closedir                               ,0xfc491ddd) //  0
NHSTUB(get_fstype                             ,0xfc37aa45) //  0
NHSTUB(qsort                                  ,0xfc468519) //  0
NHSTUB(rand                                   ,0xfc42094f) //  0
// ERROR: reboot_fw_update is not found.                   //--- ---
NHSTUB(set_control_event                      ,0xfc354345) //  0
NHSTUB(srand                                  ,0xfc420949) //  0
NHSTUB(stat                                   ,0xfc37b5cd) //  0
NHSTUB(strcat                                 ,0xfc381489) //  0
NHSTUB(strchr                                 ,0xfc13d721) //  0
NHSTUB(strcmp                                 ,0xfc382a2d) //  0
NHSTUB(strcpy                                 ,0xfc382a09) //  0
NHSTUB(strftime                               ,0x010e1689) //  0
NHSTUB(strlen                                 ,0xfc382aed) //  0
NHSTUB(strncmp                                ,0xfc420997) //  0
NHSTUB(strncpy                                ,0xfc381465) //  0
NHSTUB(strrchr                                ,0xfc13d733) //  0
NHSTUB(strtol                                 ,0xfc13d67f) //  0
NHSTUB(strtolx                                ,0xfc13d53d) //  0
   DEF(task_CaptSeq                           ,0xfc06a001) //  0
   DEF(task_DvlpSeqTask                       ,0xfc07b637) //  0
   DEF(task_ExpDrv                            ,0xfc2c136f) //  0
   DEF(task_FileWrite                         ,0xfc25f3a7) //  0
   DEF(task_InitFileModules                   ,0xfc0bd071) //  0
   DEF(task_MovieRecord                       ,0xfc09ac19) //  0
   DEF(task_PhySw                             ,0xfc1283ad) //  0
   DEF(task_TouchPanel                        ,0xfc12e74f) //  0
   DEF(task_TricInitTask                      ,0xfc4e4b19) //  0
   DEF(hook_CreateTask                        ,0xbfe14a3c) //  0
NHSTUB(time                                   ,0x010e11e3) //  0
NHSTUB(vsprintf                               ,0xfc0dcc67) //  0
NHSTUB(EngDrvRead                             ,0xfc382b41) //  0
NHSTUB(PTM_GetCurrentItem                     ,0xfc35f5cb) //  0
NHSTUB(DisableISDriveError                    ,0xfc6012b9) //  0
// ERROR: CancelHPTimer is not found.                      //--- ---
NHSTUB(SetHPTimerAfterNow                     ,0xfc135abd) //  0
NHSTUB(SetEventFlag                           ,0xbfe14e4f) //  0
NHSTUB(transfer_src_overlay                   ,0xfc380635) //  0
NHSTUB(bzero                                  ,0x01100b40) //  0
NHSTUB(memset32                               ,0x01100b44) //  0
NHSTUB(get_dial_hw_position                   ,0xfc118149) //  0
NHSTUB(PT_MFOn                                ,0xfc2a96b5) //  0
NHSTUB(PT_MFOff                               ,0xfc2a96e9) //  0
NHSTUB(GetAdChValue                           ,0xfc41f643) //  0
NHSTUB(SetVideoOutType                        ,0xfc61294d) //  0
NHSTUB(GetVideoOutType                        ,0xfc6128b9) //  0
