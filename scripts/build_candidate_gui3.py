#!/usr/bin/env python3
"""PORT-37: Opt-in G3X_GUI3=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C).

Builds an opt-in diagnostic candidate DISKBOOT.BIN combining:
1. G3X_GUI3=1: CHDK GUI candidate fixing flicker (B), menu size (F1: 2x integer font scaling / 900x600 layout),
   and background opacity (F3: solid opaque black background).
   Implies G3X_GUI2=1, G3X_GUI=1, G3X_OSD2=1, G3X_KBD=1, G3X_RESIDENT=1, G3X_POWERON_FIX=1, LED_LADDER=1.
2. G3X_GUI_DIAG=1: Valid only with G3X_GUI3=1; keeps 1-px border (0,0)-(899,599) and 'dt= w= bw= h=' marker,
   drawn only as part of full menu repaints, never per tick.

Design & Constraints:
- Default build (flags omitted / --default) remains byte-identical to locked baseline:
  DISKBOOT.BIN SHA-256: 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B).
- All prior builds (RESIDENT, OSD, OSD2, KBD, GUI, GUI2) remain strictly byte-identical.
- When GUI3 is not selected, delegates directly to tools/build_candidate_port25_ladder_fix.py.
- Retains all PORT-35 card-write exclusions (RAM-only menu, no card file access or writing).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
LOADER_DIR = CHDK_PORT / "loader" / "g3x"
BUILD_DIR = REPO_ROOT / "build"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import build_candidate_port25_ladder_fix as legacy_builder
from build_candidate_port2a import (
    CC,
    AR,
    OBJCOPY,
    NM,
    EXPECTED_BOOT_WITNESS_ADDR,
    build_candidate_loader as build_default_loader,
    encode_candidate_diskboot,
    generate_candidate_inspector,
    generate_manifest,
    extract_symbol_addr_from_nm,
    sha256_file,
    run_cmd,
)

CANDIDATE_PORT37_GUI3_DIR = str(BUILD_DIR / "candidate_port37_gui3")
CANDIDATE_PORT37_GUI3_DIAG_DIR = str(BUILD_DIR / "candidate_port37_gui3_diag")
CANDIDATE_PORT38_GUI4_DIR = str(BUILD_DIR / "candidate_port38_gui4")
CANDIDATE_PORT38_GUI4_DIAG_DIR = str(BUILD_DIR / "candidate_port38_gui4_diag")
CANDIDATE_PORT39_SHORTPRESS_GUI4_DIR = str(BUILD_DIR / "candidate_port39_shortpress_gui4")
CANDIDATE_PORT40_GUI5_DIR = str(BUILD_DIR / "candidate_port40_gui5")
CANDIDATE_PORT40_GUI5_SHORTPRESS_DIR = str(BUILD_DIR / "candidate_port40_gui5_shortpress")

G3X_GUI3_HEAP_START = legacy_builder.G3X_GUI_HEAP_START
G3X_GUI4_HEAP_START = legacy_builder.G3X_GUI_HEAP_START
G3X_GUI5_HEAP_START = legacy_builder.G3X_GUI_HEAP_START


def generate_gui3_candidate_c(gui_diag: bool = False) -> str:
    """Generate kbd-task-driven CHDK GUI driver and RAM-only/no-op stubs for G3X_GUI3=1."""
    diag_code = ""
    if gui_diag:
        diag_code = r'''
    /* PORT-37 Trial Diagnostic: 1-px border and displaytype marker drawn ONLY on menu repaint */
    extern int displaytype;
    char diag[64];
    int w1 = camera_screen.width - 1;
    int h1 = camera_screen.height - 1;
    draw_line(0, 0, w1, 0, COLOR_WHITE);
    draw_line(0, h1, w1, h1, COLOR_WHITE);
    draw_line(0, 0, 0, h1, COLOR_WHITE);
    draw_line(w1, 0, w1, h1, COLOR_WHITE);

    sprintf(diag, "dt=%d w=%d bw=%d h=%d", displaytype, camera_screen.width, camera_screen.buffer_width, camera_screen.height);
    draw_string(2, 2, diag, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
'''

    return r'''#include "platform.h"
#include "core.h"
#include "conf.h"
#include "keyboard.h"
#include "gui.h"
#include "gui_draw.h"
#include "gui_menu.h"
#include "gui_lang.h"
#include "gui_osd.h"
#include "camera_info.h"
#include "font.h"

/* =============================================================================
 * PORT-37: G3X_GUI3=1 CHDK core GUI candidate on OSD2 path.
 *
 * Implements:
 * (B)  Zero-flicker redraw: timer force_redraw (tick_cnt & 3) and per-key
 *      force_redraw are eliminated. Redraw occurs only on ALT mode transitions,
 *      active buffer toggle (check_gui_needs_redraw), guard pixel overwrite
 *      (!draw_test_guard), or GUI-consumed key events (gui_menu_kbd_process).
 *      No clearing or blanking of the visible buffer occurs when state is unchanged.
 * (F1) 2x integer font scaling (16x32) of built-in 8x16 font for the 900x600 LCD.
 * (F3) Full opaque black menu background box filled once upon menu initial draw.
 * ============================================================================= */

extern void g3x_osd2_update_screen_dimensions(void);
extern void gui_init(void);

volatile long spytask_can_start = 0;
int chdk_started_flag = 0;
int no_modules_flag = 0;
int memdmp_delay = 0;
int raw_need_postprocess = 0;
char *current_raw_addr = 0;

void core_spytask_can_start(void)
{
    spytask_can_start = 1;
}

void core_spytask(void)
{
    /* Replaced by kbd-task-driven g3x_gui_kbd_redraw() */
}

/* Driven from mykbd_task -> g3x_osd2_kbd_redraw on every keyboard tick */
void g3x_gui_kbd_redraw(int alt_active)
{
    static int gui_initialized = 0;
    static int prev_alt_active = 0;

    if (!spytask_can_start) {
        return;
    }

    if (!gui_initialized) {
        gui_initialized = 1;
        g3x_osd2_update_screen_dimensions();
        camera_info_init();
        conf_restore();
        /* Ensure built-in fonts are initialized in RAM before gui_init() */
        rbf_load_from_file("", FONT_CP_WIN);
        rbf_load_symbol("");
        gui_init();
        chdk_started_flag = 1;
    }

    int entered_alt = (alt_active != 0) && (prev_alt_active == 0);
    int left_alt = (alt_active == 0) && (prev_alt_active != 0);
    prev_alt_active = (alt_active != 0);

    g3x_osd2_update_screen_dimensions();

    /* Process pending ALT mode transition (ALT_MODE_ENTER / ALT_MODE_LEAVE) */
    gui_activate_alt_mode();

    if (entered_alt) {
        /* Open CHDK Main Menu immediately on ALT entry */
        gui_menu_init(&root_menu);
        gui_set_mode(&menuGuiHandler);
    }

    if (left_alt) {
        /* Erase CHDK menu from both OSD2 buffers and return control to stock UI */
        gui_set_need_restore();
        gui_redraw(1);
        return;
    }

    if (alt_active) {
        /* PORT-37 (B): Repaint only when entered ALT, buffer toggled, or guard pixel overwritten.
         * Timer force_redraw (tick_cnt & 3) and per-key force_redraw are removed.
         * Navigation redraw is handled incrementally by gui_menu_kbd_process without clearing. */
        extern int check_gui_needs_redraw(void);
        extern int draw_test_guard(void);
        extern void draw_set_guard(void);
        int force_redraw = entered_alt || check_gui_needs_redraw() || (!draw_test_guard());
        if (force_redraw) {
            draw_set_guard();
        }
        gui_redraw(force_redraw);
    }
}

/* Wrap gui_menu_draw_initial to fill full opaque black background once on initial draw */
void __wrap_gui_menu_draw_initial(void)
{
    extern void __real_gui_menu_draw_initial(void);
    /* PORT-37 F3: Fill full menu rectangle with solid opaque black (color 1 -> 0xFF, luma 0, opacity 255) */
    int bx = camera_screen.disp_left + camera_screen.menu_border_width;
    int bw = camera_screen.disp_width - camera_screen.menu_border_width * 2;
    int num_l = (camera_screen.height - camera_screen.ts_menu_border * 2) / rbf_font_height() - 1;
    int by = (camera_screen.height - ((num_l - 1) * rbf_font_height())) >> 1;
    int header_y = by - rbf_font_height();
    int total_h = (num_l + 1) * rbf_font_height();
    draw_rectangle(bx, header_y, bx + bw - 1, header_y + total_h - 1, MAKE_COLOR(COLOR_BLACK, COLOR_BLACK), RECT_BORDER0 | DRAW_FILLED);

    __real_gui_menu_draw_initial();
''' + diag_code + r'''
}

/* =============================================================================
 * PORT-37 (F1): 2x Integer Font Scaling (16x32) of built-in 8x16 font.
 * Expands each bit into a 2x2 pixel square without card-loaded RBF fonts.
 * ============================================================================= */

#pragma pack(1)
typedef struct {
    unsigned char skips;
} FontData;
#pragma pack()

static unsigned char* g3x_get_cdata(unsigned int *offset, unsigned int *size, const char ch)
{
    extern unsigned char *get_current_font_data(unsigned char ch);
    FontData *f = (FontData*)get_current_font_data((unsigned char)ch);
    *offset = f->skips >> 4;
    *size = 16 - (f->skips & 0xF);
    if (*size == *offset)
        (*offset)++;
    return (unsigned char*)f + sizeof(FontData) - *offset;
}

void __wrap_draw_char(coord x, coord y, const char ch, twoColors cl)
{
    unsigned int offset, size;
    unsigned char *sym = g3x_get_cdata(&offset, &size, ch);
    color fg = FG_COLOR(cl);
    color bg = BG_COLOR(cl);
    unsigned int i, j;

    /* Blank lines at top (each blank row is 2 vertical lines of width 16) */
    for (i = 0; i < offset; i++) {
        draw_hline(x, y + (i << 1), 16, bg);
        draw_hline(x, y + (i << 1) + 1, 16, bg);
    }

    /* Glyph data rows */
    for (j = i; i < size; ) {
        extern unsigned char fontdata_lookup[];
        unsigned int dsym = fontdata_lookup[sym[j] & 0x7f];
        int rep = sym[j] & 0x80;

        while (rep >= 0) {
            int yt = y + (i << 1);
            int b;
            for (b = 7; b >= 0; b--) {
                color c = (dsym & (1u << b)) ? fg : bg;
                int px = x + ((7 - b) << 1);
                /* 2x2 pixel block */
                draw_pixel(px, yt, c);
                draw_pixel(px + 1, yt, c);
                draw_pixel(px, yt + 1, c);
                draw_pixel(px + 1, yt + 1, c);
            }
            rep -= 0x80;
            i++;
        }
        j++;
    }

    /* Blank lines at bottom */
    for (; i < 16; i++) {
        draw_hline(x, y + (i << 1), 16, bg);
        draw_hline(x, y + (i << 1) + 1, 16, bg);
    }
}

int __wrap_rbf_char_width(int ch)
{
    (void)ch;
    return 16;
}

int __wrap_rbf_draw_char(int x, int y, int ch, twoColors cl)
{
    __wrap_draw_char(x, y, (char)ch, cl);
    return 16;
}

int __wrap_draw_string_clipped(coord x, coord y, const char *s, twoColors cl, int max_width)
{
    while (*s && (*s != '\n') && (max_width >= 16)) {
        __wrap_draw_char(x, y, *s, cl);
        s++;
        max_width -= 16;
        x += 16;
        if ((x >= camera_screen.width) && (*s)) {
            __wrap_draw_char(x - 16, y, '>', cl);
            break;
        }
    }
    return x;
}

/* FINSIG palette pointers */
extern int active_palette_buffer;
extern int **palette_buffer_ptr;

void *vid_get_bitmap_active_palette(void)
{
    unsigned int idx = (unsigned int)active_palette_buffer;
    if (palette_buffer_ptr == 0 || idx > 7u) {
        return 0;
    }
    int *pal = palette_buffer_ptr[idx];
    if (pal == 0) {
        return 0;
    }
    return pal + 1;
}

int vid_get_palette_type(void)
{
    return 3;
}

int vid_get_palette_size(void)
{
    return 256 * 4;
}

/* Outside ALT mode, pass all keys to stock Canon UI without CHDK interception */
int __wrap_gui_kbd_process(void)
{
    extern int kbd_is_blocked(void);
    extern int __real_gui_kbd_process(void);
    if (!kbd_is_blocked()) {
        return 0;
    }
    return __real_gui_kbd_process();
}

/* Keep non-menu OSD drawing off so closing the menu leaves a clean screen */
void __wrap_gui_draw_osd(void)
{
}

const char *__wrap_gui_alt_mode_button_enum(int change, int arg)
{
    (void)change;
    (void)arg;
    conf.alt_mode_button = KEY_PLAYBACK;
    return "Playback";
}

/* Add a selectable "Back" item (MENUITEM_UP) at the bottom of root_menu */
void __wrap_set_usermenu_state(void)
{
    extern void __real_set_usermenu_state(void);
    __real_set_usermenu_state();
    if (!conf.user_menu_enable && root_menu.menu != 0) {
        CMenuItem *items = (CMenuItem *)root_menu.menu;
        items[9].symbol = 0x51;
        items[9].opt_len = 0;
        items[9].type = MENUITEM_UP;
        items[9].text = LANG_MENU_BACK;
        items[9].value = 0;
        items[9].arg = 0;
    }
}

int core_get_free_memory(void)
{
    cam_meminfo meminfo;
    GetMemInfo(&meminfo);
    return meminfo.free_size;
}

/* Compile out / stub script loading and execution (RAM-only menu) */
char script_title[36] = "";
_chdk_version_t script_version = { 0 };
sc_param *script_params = 0;

static CMenuItem g3x_script_submenu_items[] = {
    { 0x51, 0, MENUITEM_UP, LANG_MENU_BACK, 0, 0 },
    { 0 }
};
CMenu script_submenu = { 0x27, LANG_MENU_SCRIPT_TITLE, g3x_script_submenu_items };

extern void gui_chdk_draw(int force_redraw);
gui_handler scriptGuiHandler = { GUI_MODE_SCRIPT, gui_chdk_draw, 0, 0, 0, 0 };

void script_load(const char *fn) { (void)fn; }
void __wrap_script_load(const char *fn) { (void)fn; }
long script_start_gui(int autostart) { (void)autostart; return 0; }
long __wrap_script_start_gui(int autostart) { (void)autostart; return 0; }
void save_params_values(int unconditional) { (void)unconditional; }
void __wrap_save_params_values(int unconditional) { (void)unconditional; }
void script_reset_to_default_params_values(void) {}
void script_check_terminate(void) {}
void script_console_add_line(long str_id) { (void)str_id; }
void script_console_add_error(long str_id) { (void)str_id; }
void script_end(void) {}
int script_is_running(void) { return 0; }
long script_stack_start(void) { return 0; }
void script_wait_terminate(void) {}
void script_print_screen_statement(int val) { (void)val; }
void script_set_terminate_key(int key, const char *key_name) { (void)key; (void)key_name; }

void script_get_alt_text(char *buf)
{
    if (buf) {
        buf[0] = '<';
        buf[1] = 'A';
        buf[2] = 'L';
        buf[3] = 'T';
        buf[4] = '>';
        buf[5] = '\0';
    }
}

/* Compile out / stub fileutil, raw, ptp, remotecap, and card-write hooks */
void make_pixel_list(char *ptr, int size) { (void)ptr; (void)size; }
void patch_bad_pixel(unsigned int x, unsigned int y) { (void)x; (void)y; }
void raw_prepare_develop(const char *filename, int prompt) { (void)filename; (void)prompt; }
int raw_savefile(void) { return 0; }
void raw_postprocess(void) {}
void start_ptp_script(void) {}
void __wrap_mark_filesystem_bootable(void) {}
void schedule_memdump(void) {}

char *load_file(const char *name, int *size, int add0)
{
    (void)name;
    if (size) *size = 0;
    (void)add0;
    return 0;
}
char *__wrap_load_file(const char *name, int *size, int add0) { return load_file(name, size, add0); }

char *load_file_to_length(const char *name, int *size, int add0, int length)
{
    (void)name;
    if (size) *size = 0;
    (void)add0;
    (void)length;
    return 0;
}
char *__wrap_load_file_to_length(const char *name, int *size, int add0, int length) { return load_file_to_length(name, size, add0, length); }

int process_file(const char *name, void *callback, int add0)
{
    (void)name;
    (void)callback;
    (void)add0;
    return 0;
}
int __wrap_process_file(const char *name, void *callback, int add0) { return process_file(name, callback, add0); }

int load_int_value_file(const char *name, int *value_p)
{
    (void)name;
    (void)value_p;
    return 0;
}
int __wrap_load_int_value_file(const char *name, int *value_p) { return load_int_value_file(name, value_p); }

int save_int_value_file(const char *name, int value)
{
    (void)name;
    (void)value;
    return 0;
}
int __wrap_save_int_value_file(const char *name, int value) { return save_int_value_file(name, value); }

/* Safe C replacements for stubs_entry_2.S */
int _GetFocusLensSubjectDistanceFromLens(void)
{
    extern int _GetFocusLensSubjectDistance(void);
    return _GetFocusLensSubjectDistance();
}
int _GetDrive_TotalClusters(int drive) { (void)drive; return 0; }
int _Feof_Fut(int fd) { (void)fd; return 1; }
int _Fflush_Fut(int fd) { (void)fd; return 0; }
int _PostLogicalEventToUI(int id, int x) { (void)id; (void)x; return 0; }
int _PostLogicalEventForNotPowerType(int id, int x) { (void)id; (void)x; return 0; }
void _LockMainPower(void) {}
void _UnlockMainPower(void) {}
void _SetAutoShutdownTime_FW(int t, void *cb) { (void)t; (void)cb; }
void _EnterToCompensationEVF(void) {}
void _ExitFromCompensationEVF(void) {}
void _ExpCtrlTool_StartContiAE(int a, int b) { (void)a; (void)b; }
void _ExpCtrlTool_StopContiAE(int a, int b) { (void)a; (void)b; }
int _RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
void _Restart(unsigned int opt) { (void)opt; }
int _SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int _SetFileTimeStamp(const char *fn, int t1, int t2) { (void)fn; (void)t1; (void)t2; return 0; }
int _SetParameterData(int id, void *buf, int size) { (void)id; (void)buf; (void)size; return 0; }
int _WriteSDCard(unsigned int d, unsigned int s, unsigned int n, void *b) { (void)d; (void)s; (void)n; (void)b; return 0; }
int _apex2us(int apex_val) { (void)apex_val; return 0; }
int _reboot_fw_update(const char *fw_update) { (void)fw_update; return 0; }
int _CancelHPTimer(int h) { (void)h; return 0; }
void _UnsetZoomForMovie(void) {}
void _VTMLock(void) {}
void _VTMUnlock(void) {}
void _MakeSDCardBootable(int d) { (void)d; }
int _GetImageFolder(void *a, int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; return 0; }
void _captseq_raw_addr_init(void) {}
void _PutInNdFilter_FW(void) {}
void _PutOutNdFilter_FW(void) {}
void _MoveFocusLensToDistance_FW(short *d) { (void)d; }

int _Close(int fd) { (void)fd; return -1; }
int _close(int fd) { (void)fd; return -1; }
int _closedir(void *d) { (void)d; return -1; }
int _CreateBinarySemaphore(char *n, int v) { (void)n; (void)v; return 0; }
int _CreateTask(const char *n, int p, int s, void *e, long a) { (void)n; (void)p; (void)s; (void)e; (void)a; return 0; }
int _DeleteDirectory_Fut(const char *n) { (void)n; return -1; }
int _DeleteFile_Fut(const char *n) { (void)n; return -1; }
void _DoAELock(void) {}
void _DoAFLock(void) {}
int _ExecuteEventProcedure(const char *n, ...) { (void)n; return -1; }
void _ExitTask(void) {}
int _Fclose_Fut(void *f) { (void)f; return -1; }
char *_Fgets_Fut(char *s, int n, void *f) { (void)s; (void)n; (void)f; return 0; }
void *_Fopen_Fut(const char *n, const char *m) { (void)n; (void)m; return 0; }
unsigned int _Fread_Fut(void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _Fseek_Fut(void *f, long o, int w) { (void)f; (void)o; (void)w; return -1; }
unsigned int _Fwrite_Fut(const void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _GetAdChValue(int c) { (void)c; return 0; }
unsigned int _GetDrive_ClusterSize(int d) { (void)d; return 0; }
unsigned int _GetDrive_FreeClusters(int d) { (void)d; return 0; }
void _LEDDrive(int l, int a) { (void)l; (void)a; }
int _MakeDirectory_Fut(const char *n, int u) { (void)n; (void)u; return -1; }
int _MoveOpticalZoomAt(int p) { (void)p; return 0; }
int _Open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
int _open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
void *_OpenFastDir(const char *n) { (void)n; return 0; }
void _PB2Rec(void) {}
void _Rec2PB(void) {}
int _PT_MFOff(void) { return 0; }
int _PT_MFOn(void) { return 0; }
int _PT_MoveDigitalZoomToWide(void) { return 0; }
void _PT_PlaySound(short s, void *c, int u) { (void)s; (void)c; (void)u; }
int _Read(int fd, void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _ReadFastDir(void *d, void *b) { (void)d; (void)b; return 0; }
void _SetCurrentCaptureModeType(void) {}
int _SetHPTimerAfterNow(int d, void *g, void *b, int p) { (void)d; (void)g; (void)b; (void)p; return 0; }
void _SetLogicalEventActive(unsigned int id, unsigned int s) { (void)id; (void)s; }
void _SetScriptMode(unsigned int m) { (void)m; }
void _TurnOffBackLight(void) {}
void _TurnOnBackLight(void) {}
void _TurnOffDisplay(void) {}
void _TurnOnDisplay(void) {}
void _UnlockAE(void) {}
void _UnlockAF(void) {}
int _Write(int fd, const void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _add_ptp_handler(int o, void *h, int u) { (void)o; (void)h; (void)u; return 0; }
void *_exmem_ualloc(unsigned int t, unsigned int s, void *a) { (void)t; (void)s; (void)a; return 0; }
void _exmem_ufree(unsigned int t) { (void)t; }
int _get_fstype(int d) { (void)d; return 0; }
int _lseek(int fd, int o, int w) { (void)fd; (void)o; (void)w; return -1; }
void _set_control_event(int e) { (void)e; }
int _stat(const char *n, void *p) { (void)n; (void)p; return -1; }

void __wrap_play_sound(unsigned int sound) { (void)sound; }
void __wrap_camera_set_led(int led, int state, int bright) { (void)led; (void)state; (void)bright; }
void __wrap_debug_led(int state) { (void)state; }

/* Linker wrappers blocking all file open, write, directory, and SD card paths */
int __wrap_write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
unsigned int __wrap_fwrite(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
unsigned int __wrap__Fwrite_Fut(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
int __wrap_open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
int __wrap__open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
int __wrap__Open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
void *__wrap_fopen(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
void *__wrap__Fopen_Fut(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
int __wrap_mkdir(const char *name) { (void)name; return -1; }
int __wrap_mkdir_if_not_exist(const char *dirname) { (void)dirname; return -1; }
int __wrap__MakeDirectory_Fut(const char *name, int unk) { (void)name; (void)unk; return -1; }
int __wrap_remove(const char *name) { (void)name; return -1; }
int __wrap__DeleteFile_Fut(const char *name) { (void)name; return -1; }
int __wrap__DeleteDirectory_Fut(const char *name) { (void)name; return -1; }
int __wrap_rename(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap__RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap_utime(const char *file, void *newTimes) { (void)file; (void)newTimes; return -1; }
int __wrap_stat(const char *name, void *pStat) { (void)name; (void)pStat; return -1; }
void *__wrap_opendir(const char *name) { (void)name; return 0; }
void *__wrap_opendir_chdk(const char *name, unsigned int flags) { (void)name; (void)flags; return 0; }
void *__wrap_readdir(void *d) { (void)d; return 0; }
int __wrap_closedir(void *d) { (void)d; return 0; }
int __wrap__WriteSDCard(unsigned int drive, unsigned int start_sect, unsigned int num_sect, void *buf) { (void)drive; (void)start_sect; (void)num_sect; (void)buf; return 0; }
void __wrap__MakeSDCardBootable(int drive) { (void)drive; }
int __wrap__SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int __wrap__SetFileTimeStamp(const char *fn, int time1, int time2) { (void)fn; (void)time1; (void)time2; return 0; }
int __wrap__ExecuteEventProcedure(const char *name, ...) { (void)name; return -1; }
void __wrap_rbf_load_from_file(char *file, int codepage)
{
    (void)file;
    extern void __real_rbf_load_from_file(char *f, int cp);
    __real_rbf_load_from_file("", codepage);
}
int __wrap_rbf_load_symbol(char *file)
{
    (void)file;
    extern int __real_rbf_load_symbol(char *f);
    return __real_rbf_load_symbol("");
}
void __wrap_lang_load_from_file(const char *file) { (void)file; }
int __wrap_read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap_lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap__lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap_close(int fd) { (void)fd; return -1; }
int __wrap__close(int fd) { (void)fd; return -1; }
int __wrap__Close(int fd) { (void)fd; return -1; }
'''


def generate_gui4_candidate_c(gui_diag: bool = False) -> str:
    """Generate kbd-task-driven CHDK GUI driver and direct font routines for G3X_GUI4=1."""
    diag_code = ""
    if gui_diag:
        diag_code = r'''
    /* PORT-38 Trial Diagnostic: 1-px border and displaytype marker drawn ONLY on menu repaint */
    extern int displaytype;
    char diag[64];
    int w1 = camera_screen.width - 1;
    int h1 = camera_screen.height - 1;
    draw_line(0, 0, w1, 0, COLOR_WHITE);
    draw_line(0, h1, w1, h1, COLOR_WHITE);
    draw_line(0, 0, 0, h1, COLOR_WHITE);
    draw_line(w1, 0, w1, h1, COLOR_WHITE);

    sprintf(diag, "dt=%d w=%d bw=%d h=%d", displaytype, camera_screen.width, camera_screen.buffer_width, camera_screen.height);
    draw_string(2, 2, diag, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
'''

    return r'''#include "platform.h"
#include "core.h"
#include "conf.h"
#include "keyboard.h"
#include "gui.h"
#include "gui_draw.h"
#include "gui_menu.h"
#include "gui_lang.h"
#include "gui_osd.h"
#include "camera_info.h"
#include "font.h"

/* =============================================================================
 * PORT-38: G3X_GUI4=1 CHDK core GUI candidate on OSD2 path.
 *
 * Implements:
 * (F1) Real 2x integer font scaling (16x32 raster, 16 px advance, 32 px row pitch)
 *      via direct G3X font driver in candidate code (no cross-object ld --wrap).
 * (F3) Full opaque black menu background box filled across the exact menu
 *      rectangle (x: 10..889, y: 12..587, width 880, height 576), writing
 *      UYVY black to bitmap_buffer and opacity 255 to opacity_buffer[active_bitmap_buffer & 1]
 *      (citing g7x/g5x lib.c: chdk-port/platform/g7x/lib.c:289-296, g5x/lib.c:27-33).
 * (Title) Contrasting title bar (white text on black background, conf.menu_title_color).
 * (Redraw) Zero-flicker redraw (no periodic timer force_redraw), preserving PORT-37
 *          Steps 8 (sentinel recovery) and 9 (clean ALT exit).
 * ============================================================================= */

extern void g3x_osd2_update_screen_dimensions(void);
extern void gui_init(void);

volatile long spytask_can_start = 0;
int chdk_started_flag = 0;
int no_modules_flag = 0;
int memdmp_delay = 0;
int raw_need_postprocess = 0;
char *current_raw_addr = 0;

void core_spytask_can_start(void)
{
    spytask_can_start = 1;
}

void core_spytask(void)
{
    /* Replaced by kbd-task-driven g3x_gui_kbd_redraw() */
}

static void g3x_fill_menu_opaque_black(void);
void g3x_draw_char_16x32(coord x, coord y, const char ch, twoColors cl);
int gui_get_mode(void);
void g3x_get_menu_layout(int *out_x, int *out_y, int *out_w, int *out_h);

int gui_get_mode(void)
{
    return camera_info.state.gui_mode;
}

/* Driven from mykbd_task -> g3x_osd2_kbd_redraw on every keyboard tick */
void g3x_gui_kbd_redraw(int alt_active)
{
    static int gui_initialized = 0;
    static int prev_alt_active = 0;

    if (!gui_initialized) {
        gui_initialized = 1;
        camera_info_init();
        conf_restore();
        gui_init();
        chdk_started_flag = 1;
    }

    int entered_alt = (alt_active != 0) && (prev_alt_active == 0);
    int left_alt = (alt_active == 0) && (prev_alt_active != 0);
    prev_alt_active = (alt_active != 0);

    g3x_osd2_update_screen_dimensions();

    /* Process pending ALT mode transition (ALT_MODE_ENTER / ALT_MODE_LEAVE) */
    gui_activate_alt_mode();

    if (entered_alt) {
        /* Open CHDK Main Menu immediately on ALT entry */
        gui_menu_init(&root_menu);
        gui_set_mode(&menuGuiHandler);
    }

    if (left_alt) {
        /* Erase CHDK menu from both OSD2 buffers and return control to stock UI */
        gui_set_need_restore();
        gui_redraw(1);
        return;
    }

    if (alt_active) {
        /* PORT-37 (B): Repaint only when entered ALT, buffer toggled, or guard pixel overwritten.
         * Timer force_redraw (tick_cnt & 3) and per-key force_redraw are removed.
         * Navigation redraw is handled incrementally by gui_menu_kbd_process without clearing. */
        extern int check_gui_needs_redraw(void);
        extern int draw_test_guard(void);
        extern void draw_set_guard(void);
        int force_redraw = entered_alt || check_gui_needs_redraw() || (!draw_test_guard());
        if (force_redraw) {
            draw_set_guard();
            if (gui_get_mode() == GUI_MODE_MENU) {
                g3x_fill_menu_opaque_black();
            }
        }
        gui_redraw(force_redraw);
    }
}

/* =============================================================================
 * PORT-38 (F3): Opaque Black Menu Background Fill
 *
 * Cites g7x/g5x lib.c (chdk-port/platform/g7x/lib.c:289-296, chdk-port/platform/g5x/lib.c:27-33):
 * Opacity buffer defines per-pixel opacity (255 = fully opaque) for the bitmap overlay.
 * Both bitmap_buffer and opacity_buffer are indexed by (active_bitmap_buffer & 1).
 * Mode 12 (900x600, buffer_width 928):
 * Menu rectangle computed from shared layout matching chdk-port/core/gui_menu.c.
 * ============================================================================= */

#if defined(G3X_GUI5) && (G3X_GUI5 == 1)
void g3x_get_menu_layout(int *out_x, int *out_y, int *out_w, int *out_h)
{
    int fh = rbf_font_height();
    int num_l = (camera_screen.height - camera_screen.ts_menu_border * 2) / fh - 1;
    int x = camera_screen.disp_left + camera_screen.menu_border_width;
    int w = camera_screen.disp_width - camera_screen.menu_border_width * 2;

    /* Enforce 2-pixel even alignment for UYVY word packing (adapting chdk-port/core/gui_draw.c:79-84) */
    x &= ~1;
    w &= ~1;

    /* Check current menu row count to determine scrollbar presence (wplus) */
    CMenu *cm = get_curr_menu();
    int count = 0;
    if (cm && cm->menu) {
        while (cm->menu[count].text) count++;
    }

    int wplus = (count > num_l) ? 8 : 0;

    int by = (camera_screen.height - ((num_l - 1) * fh)) >> 1;
    int header_y = by - fh;
    int total_h = (num_l + 1) * fh;

    /* When scrollbar is present, scrollbar draws to (x + w) + wplus inclusive.
     * When scrollbar is absent, list and header draw to x + w - 1 (x=889),
     * so total width from x is w (880 px). */
    int total_w = w + wplus + (wplus ? 1 : 0);
    /* Enforce even width for UYVY 2-pixel word packing */
    total_w = (total_w + 1) & ~1;

    /* Clamp to display dimensions (900x600) */
    if (x < 0) x = 0;
    if (header_y < 0) header_y = 0;
    if (x + total_w > camera_screen.disp_width) {
        total_w = camera_screen.disp_width - x;
    }
    if (header_y + total_h > camera_screen.height) {
        total_h = camera_screen.height - header_y;
    }

    if (out_x) *out_x = x;
    if (out_y) *out_y = header_y;
    if (out_w) *out_w = total_w;
    if (out_h) *out_h = total_h;
}

static void g3x_fill_menu_opaque_black(void)
{
    extern volatile char *opacity_buffer[];
    extern char *bitmap_buffer[];
    extern int active_bitmap_buffer;

    int active = active_bitmap_buffer & 1;
    volatile unsigned char *obu = (volatile unsigned char *)opacity_buffer[active];
    volatile unsigned char *bbu = (volatile unsigned char *)bitmap_buffer[active];
    if (!obu || !bbu) return;

    int bx, by, bw, bh;
    g3x_get_menu_layout(&bx, &by, &bw, &bh);

    /* Enforce 2-pixel even word alignment for DIGIC 6 UYVY overlay (chdk-port/core/gui_draw.c:79-93, 134-142) */
    bx &= ~1;
    bw = (bw + 1) & ~1;
    int count_pairs = bw >> 1;

    int y;
    for (y = by; y < by + bh; y++) {
        unsigned int offset = y * camera_screen.buffer_width + bx;
        unsigned char *o_ptr = (unsigned char *)&obu[offset];
        memset(o_ptr, 0xFF, bw);

        unsigned int *b_ptr = (unsigned int *)&bbu[(offset >> 1) << 2];
        int i;
        for (i = 0; i < count_pairs; i++) {
            b_ptr[i] = 0x00800080;
        }
    }
}
#else
void g3x_get_menu_layout(int *out_x, int *out_y, int *out_w, int *out_h)
{
    int fh = rbf_font_height();
    int num_l = (camera_screen.height - camera_screen.ts_menu_border * 2) / fh - 1;
    int x = camera_screen.disp_left + camera_screen.menu_border_width;
    int w = camera_screen.disp_width - camera_screen.menu_border_width * 2;

    /* Check current menu row count to determine scrollbar presence (wplus) */
    CMenu *cm = get_curr_menu();
    int count = 0;
    if (cm && cm->menu) {
        while (cm->menu[count].text) count++;
    }

    int wplus = (count > num_l) ? 8 : 0;

    int by = (camera_screen.height - ((num_l - 1) * fh)) >> 1;
    int header_y = by - fh;
    int total_h = (num_l + 1) * fh;

    /* When scrollbar is present, scrollbar draws to (x + w) + wplus inclusive (x=898),
     * so total width from x is w + wplus + 1 (880 + 8 + 1 = 889 px).
     * When scrollbar is absent, list and header draw to x + w - 1 (x=889),
     * so total width from x is w (880 px). */
    int total_w = w + wplus + (wplus ? 1 : 0);

    /* Clamp to display dimensions (900x600) */
    if (x < 0) x = 0;
    if (header_y < 0) header_y = 0;
    if (x + total_w > camera_screen.disp_width) {
        total_w = camera_screen.disp_width - x;
    }
    if (header_y + total_h > camera_screen.height) {
        total_h = camera_screen.height - header_y;
    }

    if (out_x) *out_x = x;
    if (out_y) *out_y = header_y;
    if (out_w) *out_w = total_w;
    if (out_h) *out_h = total_h;
}

static void g3x_fill_menu_opaque_black(void)
{
    extern volatile char *opacity_buffer[];
    extern char *bitmap_buffer[];
    extern int active_bitmap_buffer;

    int active = active_bitmap_buffer & 1;
    volatile unsigned char *obu = (volatile unsigned char *)opacity_buffer[active];
    volatile unsigned char *bbu = (volatile unsigned char *)bitmap_buffer[active];
    if (!obu || !bbu) return;

    int bx, by, bw, bh;
    g3x_get_menu_layout(&bx, &by, &bw, &bh);

    int y;
    for (y = by; y < by + bh; y++) {
        unsigned int offset = y * camera_screen.buffer_width + bx;
        unsigned char *o_ptr = (unsigned char *)&obu[offset];
        memset(o_ptr, 0xFF, bw);

        unsigned int *b_ptr = (unsigned int *)&bbu[(offset >> 1) << 2];
        int count_pairs = (bw + 1) >> 1;
        int i;
        for (i = 0; i < count_pairs; i++) {
            b_ptr[i] = 0x00800080;
        }
    }
}
#endif

/* =============================================================================
 * PORT-38 (F1): Direct 2x Integer Font Scaling (16x32) Driver
 *
 * Implements native 16x32 glyph rasterization from 8x16 font data without ld --wrap.
 * ============================================================================= */

#pragma pack(1)
typedef struct {
    unsigned char skips;
} FontData;
#pragma pack()

static unsigned char* g3x_get_cdata(unsigned int *offset, unsigned int *size, const char ch)
{
    extern unsigned char *get_current_font_data(unsigned char ch);
    FontData *f = (FontData*)get_current_font_data((unsigned char)ch);
    *offset = f->skips >> 4;
    *size = 16 - (f->skips & 0xF);
    if (*size == *offset)
        (*offset)++;
    return (unsigned char*)f + sizeof(FontData) - *offset;
}

void g3x_draw_char_16x32(coord x, coord y, const char ch, twoColors cl)
{
    unsigned int offset, size;
    unsigned char *sym = g3x_get_cdata(&offset, &size, ch);
    color fg = FG_COLOR(cl);
    color bg = BG_COLOR(cl);
    unsigned int i, j;

    /* Blank lines at top (each blank row is 2 horizontal lines of width 16) */
    for (i = 0; i < offset; i++) {
        draw_hline(x, y + (i << 1), 16, bg);
        draw_hline(x, y + (i << 1) + 1, 16, bg);
    }

    /* Glyph data rows */
    for (j = i; i < size; ) {
        extern unsigned char fontdata_lookup[];
        unsigned int dsym = fontdata_lookup[sym[j] & 0x7f];
        int rep = sym[j] & 0x80;

        while (rep >= 0) {
            int yt = y + (i << 1);
            int b;
            for (b = 7; b >= 0; b--) {
                color c = (dsym & (1u << b)) ? fg : bg;
                int px = x + ((7 - b) << 1);
                /* 2x2 pixel block */
                draw_pixel(px, yt, c);
                draw_pixel(px + 1, yt, c);
                draw_pixel(px, yt + 1, c);
                draw_pixel(px + 1, yt + 1, c);
            }
            rep -= 0x80;
            i++;
        }
        j++;
    }

    /* Blank lines at bottom */
    for (; i < 16; i++) {
        draw_hline(x, y + (i << 1), 16, bg);
        draw_hline(x, y + (i << 1) + 1, 16, bg);
    }
}

/* RBF interface implementation resolving all core references directly */

int rbf_font_height(void)
{
    return 32;
}

int rbf_char_width(int ch)
{
    (void)ch;
    return 16;
}

int rbf_str_width(const char *str)
{
    if (!str) return 0;
    return strlen(str) * 16;
}

int rbf_str_clipped_width(const char *str, int l, int maxlen)
{
    if (!str) return l;
    while (*str && (l + 16 <= maxlen)) {
        l += 16;
        str++;
    }
    return l;
}

int rbf_draw_char(int x, int y, int ch, twoColors cl)
{
    g3x_draw_char_16x32(x, y, (char)ch, cl);
    return 16;
}

int rbf_draw_symbol(int x, int y, int ch, twoColors cl)
{
    (void)x; (void)y; (void)ch; (void)cl;
    return 0;
}

int rbf_symbol_height(void)
{
    return 32;
}

int rbf_symbol_width(int ch)
{
    (void)ch;
    return 0;
}

static int g3x_cursor_on = 0;
static int g3x_cursor_start = 0;
static int g3x_cursor_end = 0;

void rbf_enable_cursor(int s, int e)
{
    g3x_cursor_on = 1;
    g3x_cursor_start = s;
    g3x_cursor_end = e;
}

void rbf_disable_cursor(void)
{
    g3x_cursor_on = 0;
}

int rbf_draw_clipped_string(int x, int y, const char *str, twoColors cl, int l, int maxlen)
{
    if (!str) return l;
    int i = 0;
    twoColors inv_cl = MAKE_COLOR(FG_COLOR(cl), BG_COLOR(cl));
    while (*str && (l + 16 <= maxlen)) {
        twoColors c = (g3x_cursor_on && (g3x_cursor_start <= i) && (i <= g3x_cursor_end)) ? inv_cl : cl;
        g3x_draw_char_16x32(x + l, y, *str++, c);
        l += 16;
        i++;
    }
    return l;
}

int rbf_draw_string(int x, int y, const char *str, twoColors cl)
{
    if (!str) return 0;
    int start_x = x;
    while (*str) {
        g3x_draw_char_16x32(x, y, *str++, cl);
        x += 16;
    }
    return x - start_x;
}

int rbf_draw_string_len(int x, int y, int len, const char *str, twoColors cl)
{
    int l = rbf_draw_clipped_string(x, y, str, cl, 0, len);
    if (l < len) {
#if defined(G3X_GUI5) && (G3X_GUI5 == 1)
        draw_rectangle(x + l, y, x + len - 1, y + 31, MAKE_COLOR(COLOR_BLACK, COLOR_BLACK), RECT_BORDER0 | DRAW_FILLED);
#else
        draw_rectangle(x + l, y, x + len - 1, y + 31, MAKE_COLOR(BG_COLOR(cl), BG_COLOR(cl)), RECT_BORDER0 | DRAW_FILLED);
#endif
    }
    return len;
}

int rbf_draw_string_right_len(int x, int y, int len, const char *str, twoColors cl)
{
    int str_w = str ? (strlen(str) * 16) : 0;
    int pad = len - str_w;
    if (pad < 0) pad = 0;
    if (pad > 0) {
#if defined(G3X_GUI5) && (G3X_GUI5 == 1)
        draw_rectangle(x, y, x + pad - 1, y + 31, MAKE_COLOR(COLOR_BLACK, COLOR_BLACK), RECT_BORDER0 | DRAW_FILLED);
#else
        draw_rectangle(x, y, x + pad - 1, y + 31, MAKE_COLOR(BG_COLOR(cl), BG_COLOR(cl)), RECT_BORDER0 | DRAW_FILLED);
#endif
    }
    rbf_draw_clipped_string(x, y, str, cl, pad, len);
    return len;
}

void rbf_load_from_file(char *file, int codepage)
{
    (void)file; (void)codepage;
}

int rbf_load_symbol(char *file)
{
    (void)file;
    return 1;
}

void rbf_set_codepage(int codepage)
{
    (void)codepage;
}

void init_fonts(void)
{
}

int rbf_draw_menu_header(int x, int y, int len, char symbol, const char *str, twoColors cl)
{
    (void)symbol;
    /* Fill full menu box with solid opaque black background */
    g3x_fill_menu_opaque_black();

    int h = rbf_font_height(); // 32
    color bg = BG_COLOR(cl);
    color fg = FG_COLOR(cl);

    int bw = 0;
    g3x_get_menu_layout(0, 0, &bw, 0);
    int header_w = (len > (camera_screen.disp_width - camera_screen.menu_border_width * 2)) ? bw : len;

    /* Fill header bar with solid background color (black) */
    draw_rectangle(x, y, x + header_w - 1, y + h - 1, MAKE_COLOR(bg, bg), RECT_BORDER0 | DRAW_FILLED);

    /* Draw title text in contrasting foreground color (white on black) */
    if (str && *str) {
        int title_x = x + 16;
        int max_x = x + header_w - 16;
        while (*str && (title_x + 16 <= max_x)) {
            g3x_draw_char_16x32(title_x, y, *str++, MAKE_COLOR(bg, fg));
            title_x += 16;
        }
    }
''' + diag_code + r'''
    return len;
}

/* FINSIG palette pointers */
extern int active_palette_buffer;
extern int **palette_buffer_ptr;

void *vid_get_bitmap_active_palette(void)
{
    unsigned int idx = (unsigned int)active_palette_buffer;
    if (palette_buffer_ptr == 0 || idx > 7u) {
        return 0;
    }
    int *pal = palette_buffer_ptr[idx];
    if (pal == 0) {
        return 0;
    }
    return pal + 1;
}

int vid_get_palette_type(void)
{
    return 3;
}

int vid_get_palette_size(void)
{
    return 256 * 4;
}

/* Outside ALT mode, pass all keys to stock Canon UI without CHDK interception */
int __wrap_gui_kbd_process(void)
{
    extern int kbd_is_blocked(void);
    extern int __real_gui_kbd_process(void);
    if (!kbd_is_blocked()) {
        return 0;
    }
    return __real_gui_kbd_process();
}

/* Keep non-menu OSD drawing off so closing the menu leaves a clean screen */
void __wrap_gui_draw_osd(void)
{
}

const char *__wrap_gui_alt_mode_button_enum(int change, int arg)
{
    (void)change;
    (void)arg;
    conf.alt_mode_button = KEY_PLAYBACK;
    return "Playback";
}

/* Add a selectable "Back" item (MENUITEM_UP) at the bottom of root_menu */
void __wrap_set_usermenu_state(void)
{
    extern void __real_set_usermenu_state(void);
    __real_set_usermenu_state();
    if (!conf.user_menu_enable && root_menu.menu != 0) {
        CMenuItem *items = (CMenuItem *)root_menu.menu;
        items[9].symbol = 0x51;
        items[9].opt_len = 0;
        items[9].type = MENUITEM_UP;
        items[9].text = LANG_MENU_BACK;
        items[9].value = 0;
        items[9].arg = 0;
    }
}

int core_get_free_memory(void)
{
    cam_meminfo meminfo;
    GetMemInfo(&meminfo);
    return meminfo.free_size;
}

/* Compile out / stub script loading and execution (RAM-only menu) */
char script_title[36] = "";
_chdk_version_t script_version = { 0 };
sc_param *script_params = 0;

static CMenuItem g3x_script_submenu_items[] = {
    { 0x51, 0, MENUITEM_UP, LANG_MENU_BACK, 0, 0 },
    { 0 }
};
CMenu script_submenu = { 0x27, LANG_MENU_SCRIPT_TITLE, g3x_script_submenu_items };

extern void gui_chdk_draw(int force_redraw);
gui_handler scriptGuiHandler = { GUI_MODE_SCRIPT, gui_chdk_draw, 0, 0, 0, 0 };

void script_load(const char *fn) { (void)fn; }
void __wrap_script_load(const char *fn) { (void)fn; }
long script_start_gui(int autostart) { (void)autostart; return 0; }
long __wrap_script_start_gui(int autostart) { (void)autostart; return 0; }
void save_params_values(int unconditional) { (void)unconditional; }
void __wrap_save_params_values(int unconditional) { (void)unconditional; }
void script_reset_to_default_params_values(void) {}
void script_check_terminate(void) {}
void script_console_add_line(long str_id) { (void)str_id; }
void script_console_add_error(long str_id) { (void)str_id; }
void script_end(void) {}
int script_is_running(void) { return 0; }
long script_stack_start(void) { return 0; }
void script_wait_terminate(void) {}
void script_print_screen_statement(int val) { (void)val; }
void script_set_terminate_key(int key, const char *key_name) { (void)key; (void)key_name; }

void script_get_alt_text(char *buf)
{
    if (buf) {
        buf[0] = '<';
        buf[1] = 'A';
        buf[2] = 'L';
        buf[3] = 'T';
        buf[4] = '>';
        buf[5] = '\0';
    }
}

/* Compile out / stub fileutil, raw, ptp, remotecap, and card-write hooks */
void make_pixel_list(char *ptr, int size) { (void)ptr; (void)size; }
void patch_bad_pixel(unsigned int x, unsigned int y) { (void)x; (void)y; }
void raw_prepare_develop(const char *filename, int prompt) { (void)filename; (void)prompt; }
int raw_savefile(void) { return 0; }
void raw_postprocess(void) {}
void start_ptp_script(void) {}
void __wrap_mark_filesystem_bootable(void) {}
void schedule_memdump(void) {}

char *load_file(const char *name, int *size, int add0)
{
    (void)name;
    if (size) *size = 0;
    (void)add0;
    return 0;
}
char *__wrap_load_file(const char *name, int *size, int add0) { return load_file(name, size, add0); }
char *load_file_to_length(const char *name, int *size, int add0, int length)
{
    (void)name;
    if (size) *size = 0;
    (void)add0;
    (void)length;
    return 0;
}
char *__wrap_load_file_to_length(const char *name, int *size, int add0, int length) { return load_file_to_length(name, size, add0, length); }

int process_file(const char *name, void *callback, int add0)
{
    (void)name;
    (void)callback;
    (void)add0;
    return 0;
}
int __wrap_process_file(const char *name, void *callback, int add0) { return process_file(name, callback, add0); }

int load_int_value_file(const char *name, int *value_p)
{
    (void)name;
    (void)value_p;
    return 0;
}
int __wrap_load_int_value_file(const char *name, int *value_p) { return load_int_value_file(name, value_p); }

int save_int_value_file(const char *name, int value)
{
    (void)name;
    (void)value;
    return 0;
}
int __wrap_save_int_value_file(const char *name, int value) { return save_int_value_file(name, value); }

/* Safe C replacements for stubs_entry_2.S */
int _GetFocusLensSubjectDistanceFromLens(void)
{
    extern int _GetFocusLensSubjectDistance(void);
    return _GetFocusLensSubjectDistance();
}
int _GetDrive_TotalClusters(int drive) { (void)drive; return 0; }
int _Feof_Fut(int fd) { (void)fd; return 1; }
int _Fflush_Fut(int fd) { (void)fd; return 0; }
int _PostLogicalEventToUI(int id, int x) { (void)id; (void)x; return 0; }
int _PostLogicalEventForNotPowerType(int id, int x) { (void)id; (void)x; return 0; }
void _LockMainPower(void) {}
void _UnlockMainPower(void) {}
void _SetAutoShutdownTime_FW(int t, void *cb) { (void)t; (void)cb; }
void _EnterToCompensationEVF(void) {}
void _ExitFromCompensationEVF(void) {}
void _ExpCtrlTool_StartContiAE(int a, int b) { (void)a; (void)b; }
void _ExpCtrlTool_StopContiAE(int a, int b) { (void)a; (void)b; }
int _RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
void _Restart(unsigned int opt) { (void)opt; }
int _SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int _SetFileTimeStamp(const char *fn, int t1, int t2) { (void)fn; (void)t1; (void)t2; return 0; }
int _SetParameterData(int id, void *buf, int size) { (void)id; (void)buf; (void)size; return 0; }
int _WriteSDCard(unsigned int d, unsigned int s, unsigned int n, void *b) { (void)d; (void)s; (void)n; (void)b; return 0; }
int _apex2us(int apex_val) { (void)apex_val; return 0; }
int _reboot_fw_update(const char *fw_update) { (void)fw_update; return 0; }
int _CancelHPTimer(int h) { (void)h; return 0; }
void _UnsetZoomForMovie(void) {}
void _VTMLock(void) {}
void _VTMUnlock(void) {}
void _MakeSDCardBootable(int d) { (void)d; }
int _GetImageFolder(void *a, int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; return 0; }
void _captseq_raw_addr_init(void) {}
void _PutInNdFilter_FW(void) {}
void _PutOutNdFilter_FW(void) {}
void _MoveFocusLensToDistance_FW(short *d) { (void)d; }

int _Close(int fd) { (void)fd; return -1; }
int _close(int fd) { (void)fd; return -1; }
int _closedir(void *d) { (void)d; return -1; }
int _CreateBinarySemaphore(char *n, int v) { (void)n; (void)v; return 0; }
int _CreateTask(const char *n, int p, int s, void *e, long a) { (void)n; (void)p; (void)s; (void)e; (void)a; return 0; }
int _DeleteDirectory_Fut(const char *n) { (void)n; return -1; }
int _DeleteFile_Fut(const char *n) { (void)n; return -1; }
void _DoAELock(void) {}
void _DoAFLock(void) {}
int _ExecuteEventProcedure(const char *n, ...) { (void)n; return -1; }
void _ExitTask(void) {}
int _Fclose_Fut(void *f) { (void)f; return -1; }
char *_Fgets_Fut(char *s, int n, void *f) { (void)s; (void)n; (void)f; return 0; }
void *_Fopen_Fut(const char *n, const char *m) { (void)n; (void)m; return 0; }
unsigned int _Fread_Fut(void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _Fseek_Fut(void *f, long o, int w) { (void)f; (void)o; (void)w; return -1; }
unsigned int _Fwrite_Fut(const void *b, unsigned int s, unsigned int n, void *f) { (void)b; (void)s; (void)n; (void)f; return 0; }
int _GetAdChValue(int c) { (void)c; return 0; }
unsigned int _GetDrive_ClusterSize(int d) { (void)d; return 0; }
unsigned int _GetDrive_FreeClusters(int d) { (void)d; return 0; }
void _LEDDrive(int l, int a) { (void)l; (void)a; }
int _MakeDirectory_Fut(const char *n, int u) { (void)n; (void)u; return -1; }
int _MoveOpticalZoomAt(int p) { (void)p; return 0; }
int _Open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
int _open(const char *n, int f, int m) { (void)n; (void)f; (void)m; return -1; }
void *_OpenFastDir(const char *n) { (void)n; return 0; }
void _PB2Rec(void) {}
void _Rec2PB(void) {}
int _PT_MFOff(void) { return 0; }
int _PT_MFOn(void) { return 0; }
int _PT_MoveDigitalZoomToWide(void) { return 0; }
void _PT_PlaySound(short s, void *c, int u) { (void)s; (void)c; (void)u; }
int _Read(int fd, void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _ReadFastDir(void *d, void *b) { (void)d; (void)b; return 0; }
void _SetCurrentCaptureModeType(void) {}
int _SetHPTimerAfterNow(int d, void *g, void *b, int p) { (void)d; (void)g; (void)b; (void)p; return 0; }
void _SetLogicalEventActive(unsigned int id, unsigned int s) { (void)id; (void)s; }
void _SetScriptMode(unsigned int m) { (void)m; }
void _TurnOffBackLight(void) {}
void _TurnOnBackLight(void) {}
void _TurnOffDisplay(void) {}
void _TurnOnDisplay(void) {}
void _UnlockAE(void) {}
void _UnlockAF(void) {}
int _Write(int fd, const void *b, unsigned int c) { (void)fd; (void)b; (void)c; return -1; }
int _add_ptp_handler(int o, void *h, int u) { (void)o; (void)h; (void)u; return 0; }
void *_exmem_ualloc(unsigned int t, unsigned int s, void *a) { (void)t; (void)s; (void)a; return 0; }
void _exmem_ufree(unsigned int t) { (void)t; }
int _get_fstype(int d) { (void)d; return 0; }
int _lseek(int fd, int o, int w) { (void)fd; (void)o; (void)w; return -1; }
void _set_control_event(int e) { (void)e; }
int _stat(const char *n, void *p) { (void)n; (void)p; return -1; }

void __wrap_play_sound(unsigned int sound) { (void)sound; }
void __wrap_camera_set_led(int led, int state, int bright) { (void)led; (void)state; (void)bright; }
void __wrap_debug_led(int state) { (void)state; }

/* Linker wrappers blocking all file open, write, directory, and SD card paths */
int __wrap_write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Write(int fd, const void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
unsigned int __wrap_fwrite(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
unsigned int __wrap__Fwrite_Fut(const void *ptr, unsigned int size, unsigned int nmemb, void *stream) { (void)ptr; (void)size; (void)nmemb; (void)stream; return 0; }
int __wrap_open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
int __wrap__open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
int __wrap__Open(const char *name, int flags, int mode) { (void)name; (flags); (mode); return -1; }
void *__wrap_fopen(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
void *__wrap__Fopen_Fut(const char *filename, const char *mode) { (void)filename; (void)mode; return 0; }
int __wrap_mkdir(const char *name) { (void)name; return -1; }
int __wrap_mkdir_if_not_exist(const char *dirname) { (void)dirname; return -1; }
int __wrap__MakeDirectory_Fut(const char *name, int unk) { (void)name; (void)unk; return -1; }
int __wrap_remove(const char *name) { (void)name; return -1; }
int __wrap__DeleteFile_Fut(const char *name) { (void)name; return -1; }
int __wrap__DeleteDirectory_Fut(const char *name) { (void)name; return -1; }
int __wrap_rename(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap__RenameFile_Fut(const char *oldname, const char *newname) { (void)oldname; (void)newname; return -1; }
int __wrap_utime(const char *file, void *newTimes) { (void)file; (void)newTimes; return -1; }
int __wrap_stat(const char *name, void *pStat) { (void)name; (void)pStat; return -1; }
void *__wrap_opendir(const char *name) { (void)name; return 0; }
void *__wrap_opendir_chdk(const char *name, unsigned int flags) { (void)name; (void)flags; return 0; }
void *__wrap_readdir(void *d) { (void)d; return 0; }
int __wrap_closedir(void *d) { (void)d; return 0; }
int __wrap__WriteSDCard(unsigned int drive, unsigned int start_sect, unsigned int num_sect, void *buf) { (void)drive; (void)start_sect; (void)num_sect; (void)buf; return 0; }
void __wrap__MakeSDCardBootable(int drive) { (void)drive; }
int __wrap__SetFileAttributes(const char *fn, int attr) { (void)fn; (void)attr; return 0; }
int __wrap__SetFileTimeStamp(const char *fn, int time1, int time2) { (void)fn; (void)time1; (void)time2; return 0; }
int __wrap__ExecuteEventProcedure(const char *name, ...) { (void)name; return -1; }
void __wrap_lang_load_from_file(const char *file) { (void)file; }
int __wrap_read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap__Read(int fd, void *buf, unsigned int count) { (void)fd; (void)buf; (void)count; return -1; }
int __wrap_lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap__lseek(int fd, int offset, int whence) { (void)fd; (void)offset; (void)whence; return -1; }
int __wrap_close(int fd) { (void)fd; return -1; }
int __wrap__close(int fd) { (void)fd; return -1; }
int __wrap__Close(int fd) { (void)fd; return -1; }
'''


def build_candidate_gui3_core(
    candidate_dir: str,
    gui_diag: bool = False,
    gui4: bool = False,
    gui5: bool = False,
    shortpress: bool = False,
) -> tuple[str, str, int, int]:
    """Compile and link candidate core for G3X_GUI3=1, G3X_GUI4=1, or G3X_GUI5=1."""
    if gui5:
        gui4 = True
    legacy_builder.ensure_bootstrap()
    os.makedirs(candidate_dir, exist_ok=True)

    boot_proto_c = os.path.join(candidate_dir, "boot_prototype_resident.c")
    boot_proto_o = os.path.join(candidate_dir, "boot_prototype.o")
    stubs_proto_s = os.path.join(candidate_dir, "stubs_prototype.S")
    stubs_proto_o = os.path.join(candidate_dir, "stubs_prototype.o")
    lib_proto_a = os.path.join(candidate_dir, "libplatformsub_candidate.a")
    core_elf = os.path.join(candidate_dir, "candidate_main.elf")
    core_bin = os.path.join(candidate_dir, "candidate_main.bin")

    # 1. Generate and compile boot_prototype.c
    with open(boot_proto_c, "w", encoding="utf-8") as f:
        f.write(legacy_builder.BOOT_PROTOTYPE_RESIDENT_C)

    base_cflags = [
        CC,
        "-fno-inline",
        "-Os",
        "-fno-strict-aliasing",
        "-fno-schedule-insns2",
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Imodules",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-DMEMBASEADDR=0x8000",
        "-DMEMISOSTART=0x3489b4",
        "-DMEMISOSIZE=(&_end-&_start)",
        "-DCAM_DIGIC=60",
        "-DMAXRAMADDR=0x0fffffff",
        "-DROMBASEADDR=0xFC000000",
        "-DVER_CHDK",
        '-DHDK_VERSION="CHDK"',
        '-DBUILD_NUMBER="1.5.0"',
        '-DBUILD_SVNREV="0"',
        "-Wall",
        "-Wno-unused",
        "-Wno-format",
        "-DOPT_CURVES",
        "-DOPT_DEBUGGING",
        "-DOPT_PTP",
        "-DOPT_ARAM_MALLOC",
        "-DARAM_HEAP_START=0x006ce000",
        "-DARAM_HEAP_SIZE=0x00022000",
        "-DOPT_DISABLE_CAM_ERROR=0",
        "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
        "-mthumb-interwork",
        "-DLOW_LEVEL",
        '-DPLATFORM="g3x"',
        '-DPLATFORMSUB="110c"',
        "-DPLATFORMID=12968",
        "-DCAMERA_g3x=1",
        "-DCAM_DRYOS_REL=57",
        "-nostdinc",
        "-DG3X_POWERON_FIX=1",
        "-DLED_LADDER=1",
        "-DG3X_RESIDENT=1",
        "-DG3X_KBD=1",
        "-DG3X_OSD2=1",
        "-DG3X_GUI=1",
        "-DG3X_GUI2=1",
        "-DG3X_GUI3=1",
    ]
    if gui4:
        base_cflags.append("-DG3X_GUI4=1")
    if gui5:
        base_cflags.append("-DG3X_GUI5=1")
        base_cflags.append("-Wno-builtin-macro-redefined")
        base_cflags.append('-D__DATE__="Nov  9 2026"')
        base_cflags.append('-D__TIME__="12:00:00"')
    if shortpress:
        base_cflags.append("-DG3X_SHORTPRESS=1")
    if gui_diag:
        base_cflags.append("-DG3X_GUI_DIAG=1")

    cflags = list(base_cflags) + ["-c", "-o", boot_proto_o, boot_proto_c]
    run_cmd(cflags, cwd=str(CHDK_PORT))

    stubs_proto_s = str(SUB_DIR / "stubs_prototype.S")
    sflags = [
        CC,
        "-march=armv7-r",
        "-mthumb",
        "-DTHUMB_FW",
        "-Iinclude",
        "-Icore",
        "-Iplatform/g3x",
        "-Iplatform/g3x/sub/110c",
        "-c",
        "-o",
        stubs_proto_o,
        stubs_proto_s,
    ]
    run_cmd(sflags, cwd=str(CHDK_PORT))

    # 3. Create candidate libplatformsub archive
    if os.path.exists(lib_proto_a):
        os.remove(lib_proto_a)

    stubs_min_obj = str(SUB_DIR / "stubs_min.o")
    stubs_min_osd2_o = os.path.join(candidate_dir, "stubs_min_osd2.o")
    run_cmd([OBJCOPY, "--strip-symbol=opacity_buffer", stubs_min_obj, stubs_min_osd2_o], cwd=str(CHDK_PORT))
    stubs_min_obj = stubs_min_osd2_o

    stubs_entry_gui_s = os.path.join(candidate_dir, "stubs_entry_gui.S")
    stubs_entry_gui_o = os.path.join(candidate_dir, "stubs_entry_gui.o")
    with open(stubs_entry_gui_s, "w", encoding="utf-8") as f:
        f.write(legacy_builder.generate_stubs_entry_gui_s())
    run_cmd(
        [
            CC,
            "-march=armv7-r",
            "-mthumb",
            "-DTHUMB_FW",
            "-Iinclude",
            "-Icore",
            "-Iplatform/g3x",
            "-Iplatform/g3x/sub/110c",
            "-c",
            "-o",
            stubs_entry_gui_o,
            stubs_entry_gui_s,
        ],
        cwd=str(CHDK_PORT),
    )

    gui_cand_c = os.path.join(candidate_dir, "gui_candidate.c")
    gui_cand_o = os.path.join(candidate_dir, "gui_candidate.o")
    with open(gui_cand_c, "w", encoding="utf-8") as f:
        if gui4:
            f.write(generate_gui4_candidate_c(gui_diag=gui_diag))
        else:
            f.write(generate_gui3_candidate_c(gui_diag=gui_diag))
    run_cmd(list(base_cflags) + ["-c", "-o", gui_cand_o, gui_cand_c], cwd=str(CHDK_PORT))

    mod_cand_c = os.path.join(candidate_dir, "module_candidate.c")
    mod_cand_o = os.path.join(candidate_dir, "module_candidate.o")
    with open(mod_cand_c, "w", encoding="utf-8") as f:
        f.write(legacy_builder.generate_module_candidate_c())
    run_cmd(list(base_cflags) + ["-c", "-o", mod_cand_o, mod_cand_c], cwd=str(CHDK_PORT))

    conf_cand_c = os.path.join(candidate_dir, "conf_candidate.c")
    conf_cand_o = os.path.join(candidate_dir, "conf_candidate.o")
    with open(conf_cand_c, "w", encoding="utf-8") as f:
        f.write(legacy_builder.generate_conf_candidate_c())
    run_cmd(list(base_cflags) + ["-c", "-o", conf_cand_o, conf_cand_c], cwd=str(CHDK_PORT))

    gui_draw_obj = str(SUB_DIR / "gui_draw.thm.o")
    if gui5:
        camera_info_cand_c = os.path.join(candidate_dir, "camera_info.c")
        camera_info_cand_o = os.path.join(candidate_dir, "camera_info.o")
        with open(str(CHDK_PORT / "core" / "camera_info.c"), "r", encoding="utf-8") as f:
            cam_src = f.read()
        cam_override = """
#if defined(G3X_GUI5) && (G3X_GUI5 == 1)
#undef CAM_BITMAP_WIDTH
#undef CAM_BITMAP_HEIGHT
#undef CAM_SCREEN_WIDTH
#undef CAM_SCREEN_HEIGHT
#define CAM_BITMAP_WIDTH 928
#define CAM_BITMAP_HEIGHT 600
#define CAM_SCREEN_WIDTH 900
#define CAM_SCREEN_HEIGHT 600
#endif
"""
        cam_src = cam_src.replace('#include "platform.h"', '#include "platform.h"\n' + cam_override)
        with open(camera_info_cand_c, "w", encoding="utf-8") as f:
            f.write(cam_src)
        run_cmd(list(base_cflags) + ["-c", "-o", camera_info_cand_o, camera_info_cand_c], cwd=str(CHDK_PORT))
        camera_info_obj = camera_info_cand_o

        gui_menu_cand_o = os.path.join(candidate_dir, "gui_menu.o")
        run_cmd(list(base_cflags) + ["-c", "-o", gui_menu_cand_o, str(CHDK_PORT / "core" / "gui_menu.c")], cwd=str(CHDK_PORT))
    else:
        camera_info_obj = str(SUB_DIR / "camera_info.thm.o")

    obj_files = [
        boot_proto_o,
        stubs_proto_o,
        stubs_min_obj,
        stubs_entry_gui_o,
        gui_cand_o,
        mod_cand_o,
        conf_cand_o,
        gui_draw_obj,
        str(SUB_DIR / "memmgmt.thm.o"),
        str(SUB_DIR / "gui.thm.o"),
        str(SUB_DIR / "kbd_process.thm.o"),
        str(SUB_DIR / "kbd_common.thm.o"),
        str(SUB_DIR / "gui_osd.thm.o"),
        str(SUB_DIR / "usb_sync.thm.o"),
        str(SUB_DIR / "shooting.thm.o"),
        camera_info_obj,
        str(SUB_DIR / "lib_thumb.thm.o"),
        str(SUB_DIR / "lang_str.thm.o"),
    ]
    if gui5:
        obj_files.append(gui_menu_cand_o)
    run_cmd([AR, "cr", lib_proto_a] + obj_files, cwd=str(CHDK_PORT))

    # 4. Link candidate_main.elf
    libplatform_a = str(CHDK_PORT / "platform" / "g3x" / "libplatform.a")
    libplatform_cand_a = os.path.join(candidate_dir, "libplatform_candidate.a")
    shutil.copyfile(libplatform_a, libplatform_cand_a)
    lib_osd2_o = os.path.join(candidate_dir, "lib.o")
    run_cmd([AR, "x", libplatform_cand_a, "lib.o"], cwd=candidate_dir)
    run_cmd(
        [
            OBJCOPY,
            "--weaken-symbol=vid_get_bitmap_fb",
            "--weaken-symbol=vid_get_opacity_active_buffer",
            "--weaken-symbol=vid_bitmap_refresh",
            lib_osd2_o,
        ],
        cwd=candidate_dir,
    )
    run_cmd([AR, "r", libplatform_cand_a, lib_osd2_o], cwd=candidate_dir)
    libplatform_a = libplatform_cand_a

    liblang_cand_a = os.path.join(candidate_dir, "liblang_candidate.a")
    shutil.copyfile(str(CHDK_PORT / "lib" / "lang" / ".o2" / "liblang.a"), liblang_cand_a)
    run_cmd([AR, "d", liblang_cand_a, "fileutil.o"], cwd=candidate_dir)
    liblang_a = liblang_cand_a

    libcore_cand_a = os.path.join(candidate_dir, "libcore_candidate.a")
    shutil.copyfile(str(CHDK_PORT / "lib" / "core" / ".o2" / "libcore.a"), libcore_cand_a)
    run_cmd(
        [
            AR,
            "d",
            libcore_cand_a,
            "modules.o",
            "module_load.o",
            "module_hashlist.o",
            "gui_script.o",
            "script.o",
            "gps.o",
        ],
        cwd=candidate_dir,
    )
    if gui5:
        run_cmd([AR, "d", libcore_cand_a, "gui_menu.o"], cwd=candidate_dir)
    libcore_a = libcore_cand_a

    ld_script = "tools/link-boot.ld"
    ld_cmd = [
        CC,
        "-nostdlib",
        "-Wl,--allow-shlib-undefined",
        f"-Wl,-T,{ld_script}",
        "-Wl,-N,-Ttext,0x3489b4",
        "-o",
        core_elf,
    ]

    gui_wraps = [
        "gui_menu_draw_initial",
        "draw_char",
        "rbf_char_width",
        "rbf_draw_char",
        "draw_string_clipped",
        "gui_kbd_process",
        "gui_draw_osd",
        "gui_alt_mode_button_enum",
        "set_usermenu_state",
        "conf_save",
        "conf_restore",
        "script_load",
        "script_start_gui",
        "save_params_values",
        "load_file",
        "load_file_to_length",
        "process_file",
        "load_int_value_file",
        "save_int_value_file",
        "play_sound",
        "camera_set_led",
        "debug_led",
        "mark_filesystem_bootable",
        "write",
        "_Write",
        "fwrite",
        "_Fwrite_Fut",
        "open",
        "_open",
        "_Open",
        "fopen",
        "_Fopen_Fut",
        "mkdir",
        "mkdir_if_not_exist",
        "_MakeDirectory_Fut",
        "remove",
        "_DeleteFile_Fut",
        "_DeleteDirectory_Fut",
        "rename",
        "_RenameFile_Fut",
        "utime",
        "stat",
        "opendir",
        "opendir_chdk",
        "readdir",
        "closedir",
        "_WriteSDCard",
        "_MakeSDCardBootable",
        "_SetFileAttributes",
        "_SetFileTimeStamp",
        "_ExecuteEventProcedure",
        "rbf_load_from_file",
        "rbf_load_symbol",
        "lang_load_from_file",
        "read",
        "_Read",
        "lseek",
        "_lseek",
        "close",
        "_close",
        "_Close",
    ]
    if gui4:
        # In GUI4, direct font driver provides rbf_* and scaled glyph drawing.
        # ld --wrap for these symbols is eliminated.
        for sym in [
            "gui_menu_draw_initial",
            "draw_char",
            "rbf_char_width",
            "rbf_draw_char",
            "draw_string_clipped",
            "rbf_load_from_file",
            "rbf_load_symbol",
        ]:
            if sym in gui_wraps:
                gui_wraps.remove(sym)
    for sym in gui_wraps:
        ld_cmd.append(f"-Wl,--wrap={sym}")

    ld_cmd.extend(
        [
            "-Wl,--start-group",
            str(SUB_DIR / "entry.o"),
            libplatform_a,
            lib_proto_a,
            str(CHDK_PORT / "lib" / "font" / ".o2" / "libfont.a"),
            str(CHDK_PORT / "lib" / "math" / ".o2" / "libmath.a"),
            liblang_a,
            str(CHDK_PORT / "lib" / "armutil" / ".o2" / "libarmutil.a"),
            libcore_a,
            "-lgcc",
            "-Wl,--end-group",
        ]
    )
    run_cmd(ld_cmd, cwd=str(CHDK_PORT))

    # 5. Extract binary
    run_cmd([OBJCOPY, "-O", "binary", core_elf, core_bin], cwd=str(CHDK_PORT))
    core_bin_size = os.path.getsize(core_bin)
    print(f"  [OK] candidate_main.bin generated ({core_bin_size} B)")

    # 6. Extract witness and end symbols
    proc = subprocess.run([NM, "-n", core_elf], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    boot_witness_addr = extract_symbol_addr_from_nm(proc.stdout, "boot_witness")
    end_addr = extract_symbol_addr_from_nm(proc.stdout, "_end")
    heap_start = G3X_GUI4_HEAP_START if gui4 else G3X_GUI3_HEAP_START
    if end_addr > heap_start:
        raise ValueError(
            f"Linked _end (0x{end_addr:08X}) overlaps heap start (0x{heap_start:08X})"
        )
    print(f"  [OK] boot_witness discovered at 0x{boot_witness_addr:08X}, _end at 0x{end_addr:08X}")

    return core_elf, core_bin, boot_witness_addr, end_addr


def build_candidate(
    ladder: bool = True,
    poweron_fix: bool = True,
    out_dir: str | None = None,
    resident: bool | None = None,
    osd: bool | None = None,
    kbd: bool | None = None,
    osd2: bool | None = None,
    gui: bool | None = None,
    gui2: bool | None = None,
    gui3: bool | None = None,
    gui4: bool | None = None,
    gui5: bool | None = None,
    gui_diag: bool | None = None,
    shortpress: bool | None = None,
) -> dict:
    """Execute candidate build pipeline supporting G3X_GUI5=1, G3X_GUI4=1, G3X_GUI3=1 and prior flags."""
    if shortpress is None:
        shortpress = os.environ.get("G3X_SHORTPRESS", "0") == "1"

    if gui5 is None:
        gui5 = os.environ.get("G3X_GUI5", "0") == "1"

    if gui4 is None:
        gui4 = os.environ.get("G3X_GUI4", "0") == "1"

    if gui3 is None:
        gui3 = os.environ.get("G3X_GUI3", "0") == "1"

    if gui5:
        gui4 = True
        gui3 = True
    elif gui4:
        gui3 = True

    if gui_diag is None:
        gui_diag = os.environ.get("G3X_GUI_DIAG", "0") == "1"

    if not gui3 and not gui4 and not gui5:
        # Prior builds delegate to legacy builder ensuring byte identity
        return legacy_builder.build_candidate(
            ladder=ladder,
            poweron_fix=poweron_fix,
            out_dir=out_dir,
            resident=resident,
            osd=osd,
            kbd=kbd,
            osd2=osd2,
            gui=gui,
            gui2=gui2,
            shortpress=shortpress,
        )

    # G3X_GUI5=1, G3X_GUI4=1 and G3X_GUI3=1 imply GUI2, GUI, OSD2, KBD, RESIDENT, POWERON_FIX, LED_LADDER
    gui2 = True
    gui = True
    osd2 = True
    kbd = True
    resident = True
    poweron_fix = True
    ladder = True

    if out_dir:
        candidate_dir = os.path.abspath(out_dir)
    elif gui5 and shortpress:
        candidate_dir = CANDIDATE_PORT40_GUI5_SHORTPRESS_DIR
    elif gui5:
        candidate_dir = CANDIDATE_PORT40_GUI5_DIR
    elif gui4 and shortpress:
        candidate_dir = CANDIDATE_PORT39_SHORTPRESS_GUI4_DIR
    elif gui4:
        candidate_dir = CANDIDATE_PORT38_GUI4_DIAG_DIR if gui_diag else CANDIDATE_PORT38_GUI4_DIR
    elif gui_diag:
        candidate_dir = CANDIDATE_PORT37_GUI3_DIAG_DIR
    else:
        candidate_dir = CANDIDATE_PORT37_GUI3_DIR

    legacy_builder._check_not_tracked_dir(candidate_dir)
    os.makedirs(candidate_dir, exist_ok=True)
    if gui5:
        tag = "G3X_GUI5=1"
    elif gui4:
        tag = "G3X_GUI4=1"
    else:
        tag = "G3X_GUI3=1"
    print(f"\n--- Building Candidate Core ({tag}, diag={gui_diag}) (@ 0x003489B4) ---")

    core_elf, core_bin, boot_witness_addr, end_addr = build_candidate_gui3_core(
        candidate_dir=candidate_dir,
        gui_diag=gui_diag,
        gui4=gui4,
        gui5=gui5,
        shortpress=shortpress,
    )

    core_bin_size = os.path.getsize(core_bin)

    print("\n--- Building Candidate Loader (ladder=True) (@ 0x00008000) ---")
    loader_elf, loader_bin = legacy_builder.build_candidate_loader_ladder_fix(
        core_elf=core_elf,
        core_bin=core_bin,
        witness_addr=boot_witness_addr,
        ladder=True,
        candidate_dir=candidate_dir,
    )
    loader_bin_size = os.path.getsize(loader_bin)

    print("\n--- Encoding Candidate DISKBOOT.BIN (dancingbits row 13) ---")
    diskboot_bin = legacy_builder.encode_candidate_diskboot(loader_bin, candidate_dir=candidate_dir)
    diskboot_size = os.path.getsize(diskboot_bin)
    diskboot_sha256 = sha256_file(diskboot_bin)
    print(f"  [OK] {os.path.basename(candidate_dir)}/DISKBOOT.BIN successfully encoded ({diskboot_size} B)")

    print(f"\n--- Associating Canon Basic Witness Inspector (@ 0x{boot_witness_addr:08X}) ---")
    insp_m, insp_bin = legacy_builder.generate_candidate_inspector(
        witness_addr=boot_witness_addr,
        candidate_dir=candidate_dir,
    )

    print("\n--- Generating Locked Candidate Manifest ---")
    artifacts = {
        "candidate_main.elf": core_elf,
        "candidate_main.bin": core_bin,
        "candidate_loader.elf": loader_elf,
        "candidate_loader.bin": loader_bin,
        "DISKBOOT.BIN": diskboot_bin,
        "witness_inspector_gm110c.m": insp_m,
        "witness_inspector_payload.bin": insp_bin,
    }

    manifest_path = legacy_builder.generate_manifest(
        artifacts,
        witness_addr=boot_witness_addr,
        core_end_addr=end_addr,
        candidate_dir=candidate_dir,
        inspector_verified=True,
    )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest_data["architectural_invariants"]["core_end_symbol"] = f"0x{end_addr:08X}"
    manifest_data["architectural_invariants"]["dryos_heap_base"] = f"0x{G3X_GUI3_HEAP_START:08X}"
    manifest_data["architectural_invariants"]["gui3_active"] = True
    manifest_data["architectural_invariants"]["gui4_active"] = gui4
    manifest_data["architectural_invariants"]["gui5_active"] = gui5
    manifest_data["architectural_invariants"]["gui_diag_active"] = gui_diag
    manifest_data["architectural_invariants"]["shortpress_active"] = shortpress
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    heap_start = G3X_GUI5_HEAP_START if gui5 else (G3X_GUI4_HEAP_START if gui4 else G3X_GUI3_HEAP_START)
    clearance = heap_start - end_addr

    print("\nCANDIDATE BUILD COMPLETE (OFFLINE ONLY).")
    print(f"DISKBOOT.BIN SHA-256: {diskboot_sha256}")
    print(f"DISKBOOT.BIN Size:    {diskboot_size} bytes")
    print(f"Boot Witness Addr:    0x{boot_witness_addr:08X}")
    print(f"Linked _end:          0x{end_addr:08X}")
    print(f"Heap start:           0x{heap_start:08X} (clearance: {clearance} B)")

    return {
        "core_bin": core_bin,
        "core_bin_size": core_bin_size,
        "core_elf": core_elf,
        "loader_bin": loader_bin,
        "loader_bin_size": loader_bin_size,
        "diskboot_bin": diskboot_bin,
        "diskboot_size": diskboot_size,
        "diskboot_sha256": diskboot_sha256,
        "manifest": manifest_path,
        "shortpress": shortpress,
        "boot_witness": boot_witness_addr,
        "end_addr": end_addr,
        "ladder": ladder,
        "poweron_fix": poweron_fix,
        "resident": resident,
        "osd": False,
        "kbd": kbd,
        "osd2": osd2,
        "gui": gui,
        "gui2": gui2,
        "gui3": gui3,
        "gui4": gui4,
        "gui5": gui5,
        "gui_diag": gui_diag,
        "dancingbits_row": 13,
        "clearance_bytes": clearance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-40 / PORT-38 / PORT-37: Opt-in G3X_GUI5=1 / G3X_GUI4=1 / G3X_GUI3=1 Candidate Builder for Canon PowerShot G3 X (GM1.10C)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui5", action="store_true", help="Build opt-in G3X_GUI5=1 candidate")
    group.add_argument("--gui4", action="store_true", help="Build opt-in G3X_GUI4=1 candidate")
    group.add_argument("--gui3", action="store_true", help="Build opt-in G3X_GUI3=1 candidate")
    group.add_argument("--gui2", action="store_true", help="Build opt-in G3X_GUI2=1 candidate")
    group.add_argument("--gui", action="store_true", help="Build opt-in G3X_GUI=1 candidate")
    group.add_argument("--osd2", action="store_true", help="Build opt-in G3X_OSD2=1 candidate")
    group.add_argument("--kbd", action="store_true", help="Build opt-in G3X_KBD=1 candidate")
    group.add_argument("--osd", action="store_true", help="Build opt-in G3X_OSD=1 candidate")
    group.add_argument("--resident", action="store_true", help="Build opt-in G3X_RESIDENT=1 candidate")
    group.add_argument("--combined", action="store_true", help="Build opt-in ladder + poweron fix candidate")
    group.add_argument("--default", action="store_true", help="Build default baseline candidate")
    parser.add_argument("--gui-diag", action="store_true", help="Include 1-px frame and marker under GUI3/GUI4")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    if args.default:
        res = build_candidate(ladder=False, poweron_fix=False, resident=False, out_dir=args.out_dir)
    elif args.gui5:
        res = build_candidate(gui5=True, out_dir=args.out_dir)
    elif args.gui4:
        gui_diag = bool(args.gui_diag or os.environ.get("G3X_GUI_DIAG", "0") == "1")
        res = build_candidate(gui4=True, gui_diag=gui_diag, out_dir=args.out_dir)
    elif args.gui3:
        gui_diag = bool(args.gui_diag or os.environ.get("G3X_GUI_DIAG", "0") == "1")
        res = build_candidate(gui3=True, gui_diag=gui_diag, out_dir=args.out_dir)
    elif args.gui2:
        res = build_candidate(gui2=True, out_dir=args.out_dir)
    elif args.gui:
        res = build_candidate(gui=True, out_dir=args.out_dir)
    elif args.osd2:
        res = build_candidate(osd2=True, out_dir=args.out_dir)
    elif args.kbd:
        res = build_candidate(kbd=True, out_dir=args.out_dir)
    elif args.osd:
        res = build_candidate(osd=True, out_dir=args.out_dir)
    elif args.resident:
        res = build_candidate(resident=True, out_dir=args.out_dir)
    elif args.combined:
        res = build_candidate(ladder=True, poweron_fix=True, out_dir=args.out_dir)
    else:
        # Default action: check G3X_GUI5 first, then G3X_GUI4, then G3X_GUI3
        gui_diag = bool(args.gui_diag or os.environ.get("G3X_GUI_DIAG", "0") == "1")
        if os.environ.get("G3X_GUI5", "0") == "1":
            res = build_candidate(gui5=True, out_dir=args.out_dir)
        elif os.environ.get("G3X_GUI4", "0") == "1":
            res = build_candidate(gui4=True, gui_diag=gui_diag, out_dir=args.out_dir)
        else:
            res = build_candidate(gui3=True, gui_diag=gui_diag, out_dir=args.out_dir)

    print(f"\nFinal DISKBOOT: {res['diskboot_bin']}")
    print(f"SHA-256:        {res['diskboot_sha256']}")
    print(f"Size:           {res['diskboot_size']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
