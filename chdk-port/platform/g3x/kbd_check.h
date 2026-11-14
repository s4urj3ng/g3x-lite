/* PORT-46: included only by the opt-in DBUF GUI staging patch. */
#ifndef G3X_KBD_CHECK_H
#define G3X_KBD_CHECK_H

#if defined(G3X_KBD_CHECK) && (G3X_KBD_CHECK == 1)
#if !defined(G3X_GUI_DBUF) || (G3X_GUI_DBUF != 1)
#error G3X_KBD_CHECK=1 requires G3X_GUI_DBUF=1
#endif

void gui_kbd_check_draw(void)
{
    /* No sampling, formatting or drawing outside the ALT handler. */
    if (!camera_info.state.gui_mode_alt)
        return;

    extern volatile long physw_status[3];
    unsigned int w0 = (unsigned int)physw_status[0];
    unsigned int w1 = (unsigned int)physw_status[1];
    unsigned int w2 = (unsigned int)physw_status[2];
    const char *name = "none";
    switch (kbd_get_pressed_key())
    {
#define G3X_KEY_NAME(key) case key: name = #key; break
        G3X_KEY_NAME(KEY_SHOOT_FULL);
        G3X_KEY_NAME(KEY_SHOOT_HALF);
        G3X_KEY_NAME(KEY_SHOOT_FULL_ONLY);
        G3X_KEY_NAME(KEY_VIDEO);
        G3X_KEY_NAME(KEY_MENU);
        G3X_KEY_NAME(KEY_UP);
        G3X_KEY_NAME(KEY_DOWN);
        G3X_KEY_NAME(KEY_RIGHT);
        G3X_KEY_NAME(KEY_LEFT);
        G3X_KEY_NAME(KEY_SET);
        G3X_KEY_NAME(KEY_DISPLAY);
        G3X_KEY_NAME(KEY_WIFI);
        G3X_KEY_NAME(KEY_PLAYBACK);
        G3X_KEY_NAME(KEY_POWER);
#undef G3X_KEY_NAME
    }

    /* 19 name cells + 3 * (space + 8 hex cells) + NUL = 47 bytes.
     * Fixed width overwrites the previous name, including a longer shutter name.
     * draw_string uses the existing DBUF 16x32 (2x) font and shadow path. */
    char line[47];
    sprintf(line, "%-19s %08x %08x %08x", name, w0, w1, w2);
    draw_string((camera_screen.width - 46 * FONT_WIDTH) / 2,
                camera_screen.height - 3 * FONT_HEIGHT,
                line, MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
}
#endif
#endif
