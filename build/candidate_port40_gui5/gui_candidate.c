#include "platform.h"
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
