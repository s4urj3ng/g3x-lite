#include "platform.h"
#include "lolevel.h"
#include "live_view.h"

extern int active_bitmap_buffer;
extern char* bitmap_buffer[];

void vid_bitmap_refresh()
{
    extern void _transfer_src_overlay(int);
    extern void _VTMLock();
    extern void _VTMUnlock();
    _VTMLock();
    int n = active_bitmap_buffer;
    _transfer_src_overlay(n ^ 1);
    _transfer_src_overlay(n);
    _VTMUnlock();
}

void *vid_get_bitmap_fb()
{
    return bitmap_buffer[active_bitmap_buffer];
}

extern void *opacity_buffer[];

void *vid_get_opacity_active_buffer()
{
    return opacity_buffer[active_bitmap_buffer];
}

char *camera_jpeg_count_str()
{
    extern char jpeg_count_str[];
    return jpeg_count_str;
}

void shutdown()
{
    // UNKNOWN: G3X power-off primitive not yet established
    while (1)
        ;
}

// NOTE: G3X GPIO LED MMIO address is UNVERIFIED.
// DO NOT copy G5X MMIO (0xd20b0994). Left inert.
void debug_led(int state)
{
    (void)state;
}

void camera_set_led(int led, int state, int bright)
{
    (void)bright;
    extern int _LEDDrive(int, int);
    static char led_table[2] = { 0, 4 };
    _LEDDrive(led_table[led % sizeof(led_table)], state <= 1 ? !state : state);
}

void shutdown_soft()
{
    _PostLogicalEventForNotPowerType(0x1005, 0);
}

// Exactly 229 parameters in FlashParamsTable @ 0xFCA9129C
int get_flash_params_count(void)
{
    return 229;
}

void JogDial_CW(void)
{
    _PostLogicalEventToUI(0x872, 1);    // RotateJogDialRight
}

void JogDial_CCW(void)
{
    _PostLogicalEventToUI(0x873, 1);    // RotateJogDialLeft
}

extern char* current_raw_addr;

char *hook_raw_image_addr()
{
    return current_raw_addr;
}

void *vid_get_viewport_fb_d()
{
    return 0;
}

void *vid_get_viewport_fb()
{
    return 0;
}

void *vid_get_viewport_live_fb()
{
    return 0;
}

int vid_get_viewport_width()
{
    extern int _GetVRAMHPixelsSize();
    if (camera_info.state.mode_play)
    {
        return 720;
    }
    return _GetVRAMHPixelsSize();
}

long vid_get_viewport_height()
{
    extern int _GetVRAMVPixelsSize();
    if (camera_info.state.mode_play)
    {
        return 480;
    }
    return _GetVRAMVPixelsSize();
}

int vid_get_viewport_byte_width()
{
    return 736 * 2;     // buffer is 736 wide (720 image pixels) UYVY
}

int vid_get_viewport_display_xoffset_proper()   { return vid_get_viewport_display_xoffset(); }
int vid_get_viewport_display_yoffset_proper()   { return vid_get_viewport_display_yoffset(); }
int vid_get_viewport_fullscreen_width()         { return 720; }
int vid_get_viewport_fullscreen_height()        { return 480; }
int vid_get_viewport_buffer_width_proper()      { return 736; }
int vid_get_viewport_type()                     { return LV_FB_YUV8B; }
int vid_get_aspect_ratio()                      { return LV_ASPECT_3_2; }

int check_gui_needs_redraw()
{
    static int last_bitmap_buffer = 0;
    if (active_bitmap_buffer != last_bitmap_buffer)
    {
        last_bitmap_buffer = active_bitmap_buffer;
        return 1;
    }
    return 0;
}
