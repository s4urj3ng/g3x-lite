// G3X GM1.10C INERT BOOT SKELETON
// NOTE: In accordance with CHDK-PORT-0 instructions and safety rules:
// - NO executable boot hooks are implemented
// - NO boot trampoline is implemented
// - NO task interception is performed
// This file serves as inert source scaffolding for offline verification.

#include "lolevel.h"
#include "platform.h"
#include "core.h"
#include "dryos31.h"
#include "camera_info.h"

const char * const new_sa = &_end;

void spytask(long ua, long ub, long uc, long ud, long ue, long uf)
{
    core_spytask();
}

void CreateTask_spytask()
{
    _CreateTask("SpyTask", 0x19, 0x2000, spytask, 0);
}

// INERT ENTRY POINT: Boot trampoline intentionally omitted.
void __attribute__((naked,noinline)) boot()
{
    while (1)
        ;
}
