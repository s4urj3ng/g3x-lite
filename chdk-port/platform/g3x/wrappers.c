#include "../generic/wrappers.c"

long lens_get_focus_pos()
{
    return _GetFocusLensSubjectDistance();
}

long lens_get_focus_pos_from_lens()
{
    return _GetFocusLensSubjectDistanceFromLens();
}

int DoMFLock(void)
{
    if (!camera_info.state.mode_play) {
        _PT_MFOn();
        return 1;
    }
    return 0;
}

int UnlockMF(void)
{
    if (!camera_info.state.mode_play) {
        _PT_MFOff();
        return 1;
    }
    return 0;
}

static void null_func() { }

void _PutInNdFilter()
{
    extern void _PutInNdFilter_FW(void*, int);
    _PutInNdFilter_FW(null_func, 0);
}

void _PutOutNdFilter()
{
    extern void _PutOutNdFilter_FW(void*, int);
    _PutOutNdFilter_FW(null_func, 0);
}

void _MoveFocusLensToDistance(short *dist)
{
    extern void _MoveFocusLensToDistance_FW(int, void*, int);
    _MoveFocusLensToDistance_FW(*(int*)dist, null_func, 0);
}

// SetAutoShutdownTime in ROM (0xFC136034) takes (int seconds, void (*callback)(void)).
// Upstream CHDK calls _SetAutoShutdownTime(int) with 1 argument.
// To satisfy the 2-argument AAPCS contract safely and prevent storing uninitialized
// caller register garbage into callback field [r4, #0x34], pass callback = 0 (NULL).
// ROM instruction 0xFC136086: cbz r5, #0xfc13608a skips callback registration when r1 == 0.
void _SetAutoShutdownTime(int t)
{
    extern void _SetAutoShutdownTime_FW(int, void*);
    _SetAutoShutdownTime_FW(t, 0);
}
