// G3X display, video, and runtime library implementation (Full Build)
//
// PORT-41: Standard CHDK build adapted from sibling g7x and g5x
// Sibling citations:
// - chdk-port/platform/g7x/lib.c:136-145, 171-225, 289-296, 303-358
// - chdk-port/platform/g5x/lib.c:21-33, 162-204

#include "platform.h"
#include "lolevel.h"
#include "live_view.h"
#include "camera_info.h"

extern int active_bitmap_buffer;
extern char* bitmap_buffer[];

// GM1.10C Mode 12 LCD opacity buffers in DRAM
static void *opacity_buffers[2] = { (void*)0x5FC40000, (void*)0x5FB80000 };

void vid_bitmap_refresh()
{
    extern void _transfer_src_overlay(int);
    _transfer_src_overlay(0);
}

void *vid_get_bitmap_fb()
{
    return bitmap_buffer[active_bitmap_buffer & 1];
}

void *vid_get_opacity_active_buffer()
{
    return opacity_buffers[active_bitmap_buffer & 1];
}

/*
 * PORT-40 / PORT-41 GUI5 layout for Mode 12 900x600 LCD:
 * - displaytype 12 (or default on G3 X): 900x600, buffer stride 928
 * - Outer menu box: 880x576 px at (10, 12)-(889, 587)
 * - Margins: 10 px horizontal, 12 px vertical
 * - 18 rows @ 32 px pitch (1 header + 17 menu items)
 * [docs/PORT40_GUI_LAYOUT.md:10-29; chdk-port/platform/g7x/lib.c:303-358; chdk-port/platform/g5x/lib.c:162-204]
 */
void update_screen_dimensions()
{
    extern int displaytype;
    static int old_displaytype = -1;

    if (old_displaytype == displaytype) {
        return;
    }
    old_displaytype = displaytype;

    switch (displaytype) {
        case 12: // LCD Mode 12 (900x600, buffer stride 928)
        default:
            camera_screen.width = 900;
            camera_screen.height = 600;
            camera_screen.buffer_width = 928;
            camera_screen.buffer_height = 600;
            break;
    }

    // Reset OSD display margins per GUI5 layout (880x576 box with 10-px horiz margins)
    camera_screen.disp_left = 0;
    camera_screen.disp_width = 900;
    camera_screen.disp_right = camera_screen.width - 1;
    camera_screen.menu_border_width = 10;
    camera_screen.ts_menu_border = 0;

    camera_screen.physical_width = camera_screen.buffer_width;
    camera_screen.size = camera_screen.width * camera_screen.height;
    camera_screen.buffer_size = camera_screen.buffer_width * camera_screen.buffer_height;
}

/*
 * Compile-time card write disable wrappers for full build
 * Ensures no conf save, parameter save, or raw file writes to SD card.
 * Intercepts directory creation, file deletion, and file renaming.
 * Consumed by linker --wrap options in Makefile.
 */
void __wrap_conf_save(void) { }
void __wrap_save_params_values(int enforce) { (void)enforce; }
void __wrap_save_int_value_file(const char *fn, int v) { (void)fn; (void)v; }
int __wrap_write(int fd, const void *buf, int n) { (void)fd; (void)buf; return n; }
int __wrap_fwrite(const void *ptr, int size, int n, void *stream) { (void)ptr; (void)size; (void)stream; return n; }

// Real DryOS symbols resolved via linker --wrap
extern int __real_open(const char *name, int flags, int mode);
extern void *__real_fopen(const char *filename, const char *mode);

int __wrap_creat(const char *pathname, int mode)
{
    (void)pathname;
    (void)mode;
    return -1;
}

int __wrap_open(const char *name, int flags, int mode)
{
    // Block write/create/append/truncate access:
    // O_WRONLY(1), O_RDWR(2), O_APPEND(8), O_CREAT(0x100 or 0x200), O_TRUNC(0x200 or 0x400)
    if ((flags & 3) != 0 || (flags & (0x08 | 0x0100 | 0x0200 | 0x0400 | 0x0800))) {
        return -1;
    }
    return __real_open(name, flags, mode);
}

void *__wrap_fopen(const char *filename, const char *mode)
{
    if (!mode) return 0;
    // Pass read-only modes ("r", "rb") through to __real_fopen; reject write, append, create, truncate ('w', 'a', '+')
    const char *p;
    for (p = mode; *p; ++p) {
        if (*p == 'w' || *p == 'a' || *p == '+') {
            return 0;
        }
    }
    return __real_fopen(filename, mode);
}

// Wrappers blocking filesystem mutation (mkdir, remove/DeleteFile, rename)
long __wrap_mkdir(const char *dirname) { (void)dirname; return 0; }
long __wrap_MakeDirectory_Fut(const char *dirname, int unk) { (void)dirname; (void)unk; return 0; }
long __wrap__MakeDirectory_Fut(const char *dirname, int unk) { (void)dirname; (void)unk; return 0; }

int __wrap_remove(const char *name) { (void)name; return 0; }
int __wrap_DeleteFile_Fut(const char *name) { (void)name; return 0; }
int __wrap__DeleteFile_Fut(const char *name) { (void)name; return 0; }
int __wrap_DeleteDirectory_Fut(const char *name) { (void)name; return 0; }
int __wrap__DeleteDirectory_Fut(const char *name) { (void)name; return 0; }

int __wrap_rename(const char *oldname, const char *newname) { (void)oldname; (void)newname; return 0; }
int __wrap_RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return 0; }
int __wrap__RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return 0; }

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
