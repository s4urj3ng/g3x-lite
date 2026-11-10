#include "stubs_asm.h"

// BEWARE: thumb functions NEED the thumb bit in the below list

#define NULL_SUB 0xFC000011 // bx lr @ 0xFC000010

// Verified from ROM disassembly:
NHSTUB(GetDrive_TotalClusters                 ,0xFC37AF8B) // Function immediately preceding GetDrive_FreeClusters (0xFC37AFAF)
NHSTUB(Feof_Fut                               ,0xFC37F111) // In file wrapper cluster @ 0xFC37F110
NHSTUB(Fflush_Fut                             ,0xFC37F139) // In file wrapper cluster @ 0xFC37F138

// Verified DryOS Event Primitives (Registered eventproc wrappers):
NHSTUB(PostLogicalEventToUI                   ,0xFC35B93D) // Registered @ 0xFC35BA80, entry @ 0xFC35B93C (Thumb)
NHSTUB(PostLogicalEventForNotPowerType        ,0xFC35B909) // Registered @ 0xFC35BA8A, entry @ 0xFC35B908 (Thumb, prologue push)

// Verified DryOS Power Management Primitives (Registered eventproc wrappers):
NHSTUB(LockMainPower                          ,0xFC135FE5) // Registered @ 0xFC1360B0, entry @ 0xFC135FE4 (Thumb)
NHSTUB(UnlockMainPower                        ,0xFC135F81) // Registered @ 0xFC1360BA, entry @ 0xFC135F80 (Thumb)
IGNORE(SetAutoShutdownTime)                                // Custom 2-arg adapter supplied in wrappers.c
NHSTUB(SetAutoShutdownTime_FW                 ,0xFC136035) // Registered @ 0xFC1360A6, entry @ 0xFC136034 (Thumb)

// Stubs mapped to NULL_SUB for offline scaffolding:
NHSTUB(EnterToCompensationEVF                 ,NULL_SUB)
NHSTUB(ExitFromCompensationEVF                ,NULL_SUB)
NHSTUB(ExpCtrlTool_StartContiAE               ,NULL_SUB)
NHSTUB(ExpCtrlTool_StopContiAE                ,NULL_SUB)
NHSTUB(GetFocusLensSubjectDistanceFromLens    ,NULL_SUB)
NHSTUB(RenameFile_Fut                         ,NULL_SUB)
NHSTUB(Restart                                ,NULL_SUB)
NHSTUB(SetFileAttributes                      ,NULL_SUB)
NHSTUB(SetFileTimeStamp                       ,NULL_SUB)
NHSTUB(SetParameterData                       ,NULL_SUB)
NHSTUB(WriteSDCard                            ,NULL_SUB)
NHSTUB(apex2us                                ,NULL_SUB)
NHSTUB(reboot_fw_update                       ,NULL_SUB)
NHSTUB(CancelHPTimer                          ,NULL_SUB)
NHSTUB(UnsetZoomForMovie                      ,NULL_SUB)

// Additional required CHDK primitives:
NHSTUB(VTMLock                                ,NULL_SUB)
NHSTUB(VTMUnlock                              ,NULL_SUB)
NHSTUB(MakeSDCardBootable                     ,NULL_SUB)
NHSTUB(GetImageFolder                         ,NULL_SUB)
NHSTUB(captseq_raw_addr_init                  ,NULL_SUB)
NHSTUB(PutInNdFilter_FW                       ,NULL_SUB)
NHSTUB(PutOutNdFilter_FW                      ,NULL_SUB)
NHSTUB(MoveFocusLensToDistance_FW             ,NULL_SUB)
