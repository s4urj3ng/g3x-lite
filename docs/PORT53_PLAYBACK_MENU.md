# PORT-53 — Playback-mode CHDK ALT menu adaptation table

| item | sibling path:line | G3X current state (path:line in chdk-port/platform/g3x/ or 'missing') | GM1.10C address or value | label (FINSIG / INFERRED / HISTORICAL_CHDK / ROM_VERIFIED) | change needed |
|---|---|---|---|---|---|
| **1. Menu navigation keys (UP / DOWN / LEFT / RIGHT / SET / MENU)** | `chdk-port/platform/g7x/kbd.c:41-46` (G7X: MENU:41, UP:42, DOWN:43, RIGHT:44, LEFT:45, SET:46; G5X: `chdk-port/platform/g5x/kbd.c:26-31`; SX60HS: `chdk-port/platform/sx60hs/kbd.c:34-39`) | `chdk-port/platform/g3x/kbd.c:34-39` (MENU:34, UP:35, DOWN:36, RIGHT:37, LEFT:38, SET:39); `chdk-port/platform/g3x/platform_kbd.h:10` (`KEYS_MASK0 = 0x000533F9`) | UP: w0.b5 `0x00000020` (event 0x06 @ `0xFC66C970`); DOWN: w0.b6 `0x00000040` (event 0x07 @ `0xFC66C978`); LEFT: w0.b8 `0x00000100` (event 0x08 @ `0xFC66C988`); RIGHT: w0.b7 `0x00000080` (event 0x09 @ `0xFC66C980`); SET: w0.b9 `0x00000200` (event 0x0a @ `0xFC66C990`); MENU: w0.b4 `0x00000010` (event 0x14 @ `0xFC66C968`); MASK0: `0x000533F9` | FINSIG | Existing G3X code already covers this row (none; 100% consistent with `reference/finsig_gm110c/physw_bits.txt:7-12` and `docs/PORT46_KEYMAP.md:17-22`; no nav key mismatch; historical zoom event mismatch 0x16/0x12 vs 0x04/0x03 does not affect menu nav) |
| **2. Submenu enter and back** | `chdk-port/core/gui_menu.c:489,656,696` (enter: `select_sub_menu()`, `KEY_RIGHT`:656, `KEY_SET`:696; `select_proc()`:653,693); `chdk-port/core/gui_menu.c:316,614,635,699,749,1340` (back: `gui_menu_back()`, `KEY_LEFT`:614,635, `KEY_SET` on `MENUITEM_UP`:699, `KEY_DISPLAY`:749; `gui_menu_kbd_process_menu_btn()` on `KEY_MENU`:1340 exits to ALT) | `chdk-port/platform/g3x/gui_menu.c:510,677,717` (enter: `select_sub_menu()`, `KEY_RIGHT`:677, `KEY_SET`:717); `chdk-port/platform/g3x/gui_menu.c:337,635,656,720,770,1384` (back: `gui_menu_back()`, `KEY_LEFT`:635,656, `KEY_SET`:720, `KEY_DISPLAY`:770, `KEY_MENU`:1384); keys mapped in `chdk-port/platform/g3x/kbd.c:34,37-40` | Values: `KEY_RIGHT` = `0x00000080` (w0.b7), `KEY_SET` = `0x00000200` (w0.b9), `KEY_LEFT` = `0x00000100` (w0.b8), `KEY_DISPLAY` = `0x00001000` (w0.b12), `KEY_MENU` = `0x00000010` (w0.b4) | HISTORICAL_CHDK / FINSIG | Existing G3X code already covers this row (none; `gui_menu.c` and `kbd.c` handle submenu enter and back via d-pad, SET, DISP, and MENU identical to siblings) |
| **3. In-session item edits (bool / enum / int)** | `chdk-port/core/gui_menu.c:347,405,418,603-612,642-651,681-725` (`update_int_value`:347, `update_bool_value`:405, `update_enum_value`:418 mutate `*(mi->value)` or call enum callbacks like `chdk-port/core/gui.c:2080-2104`); `chdk-port/core/conf.c:20` (`Conf conf;` in RAM) | `chdk-port/platform/g3x/gui_menu.c:368,426,439,624-633,663-672,702-748` (same `update_int/bool/enum_value` modifying `*(mi->value)` in `conf`); `chdk-port/core/conf.c:20` | In-RAM mutation: `conf` struct in RAM (BSS symbol `conf` in `chdk-port/core/conf.c:20`); direct memory write to `conf.<var>`; no ROM stub address required | HISTORICAL_CHDK | Existing G3X code already covers this row (none; item edits directly mutate global `conf` struct in RAM, persisting across menu close/re-open within session without card writes) |
| **4. Conf save path, write-disabled skip point, and SAVE:OFF marker** | `chdk-port/core/conf.c:1159-1175` (`conf_save()`); callers: `chdk-port/core/gui_menu.c:1344` (menu exit), `chdk-port/core/gui.c:2029,3140` (GUI init & ALT exit), `chdk-port/core/main.c:218` (power-off hook), `chdk-port/core/conf.c:1554` (restore); siblings execute native card writes | Caller: `chdk-port/platform/g3x/gui_menu.c:1388`; Linker wrap: `chdk-port/platform/g3x/sub/110c/Makefile:15` & `chdk-port/platform/g3x/lib.c:130` (`-Wl,--wrap=conf_save`); Skip guard: `scripts/build_port43_dbuf.py:1821-1841` (staged `core/conf.c:1159`); Marker: `chdk-port/platform/g3x/gui_diag.h:268,275-290,975-977,1317-1319` | Value: `G3X_CONF_SAVE_OFF = 3` (`g3x_conf_save_status`); displayed as `"SAVE:OFF"` banner string @ `(82, 504)` on OSD | INFERRED | Existing G3X code already covers this row (none; under `G3X_GUI_MENU=1` + `G3X_DISABLE_CARD_WRITES=1` / `OPT_DISABLE_FILE_WRITES=1`, `conf_save()` entry is intercepted before `config_save()`/`save_params_values()`, calls `g3x_conf_record_save_result(3)` and immediately returns, setting `SAVE:OFF`) |
| **5. Playback-specific mode checks (mode_play, playrec mode, get_movie_status)** | Mode check: `chdk-port/core/shooting.c:1678-1716` (`rec_mode_active()`:1678 weak check of `playrec_mode == 2 \|\| 4 \|\| 5`, `mode_get()`:1687-1715 sets `camera_info.state.mode_play = 1`); Movie status: `chdk-port/core/shooting.c:1619-1627` (`get_movie_status()`); Viewport: `chdk-port/platform/g7x/lib.c:198,209,226,242` (`vid_get_viewport_width/height/offsets`); Title/OSD: `chdk-port/core/gui.c:2696` (`mode_rec \|\| mode_play`); ALT/kbd: `chdk-port/core/kbd_process.c:156,171-176` (ungated); sibling stubs: `chdk-port/platform/g7x/sub/100c/stubs_entry.S:143` (`playrec_mode`), `chdk-port/platform/g7x/sub/100c/stubs_min.S:16` (`simple_movie_status`) | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:181` (`playrec_mode`); `chdk-port/platform/g3x/sub/110c/stubs_entry.S:343` (`task_MovieRecord`); `chdk-port/platform/g3x/sub/110c/stubs_min.S:7` (`simple_movie_status`); `chdk-port/platform/g3x/lib.c:106,116` (`vid_get_viewport_width/height`); `chdk-port/platform/g3x/wrappers.c:15,24` (`DoMFLock`, `UnlockMF`); `chdk-port/platform/g3x/platform_kbd.h:10` (`KEYS_MASK0` covering `KEY_PLAYBACK`) | `playrec_mode` = `0x0000C4D4` (`reference/finsig_gm110c/stubs_entry.S:177`, found @ `0xFC2D7296`; playback value = 0 or 1); `get_playrec_mode` = `0xFC2D7297` (`reference/finsig_gm110c/funcs_by_name.csv:493`); `task_MovieRecord` entry = `0xFC09AC19` (`reference/finsig_gm110c/stubs_entry.S:339`); `simple_movie_status` = `0x0000C170` (`chdk-port/platform/g3x/sub/110c/stubs_min.S:7`, identified via internal store instruction @ `0xFC09BD60` inside `task_MovieRecord`; playback value = 0); `KEY_PLAYBACK` = w0.b16 (`0x00010000`, event 0x101 @ `0xFC66C9B8` in `reference/finsig_gm110c/physw_bits.txt:17`); `KEYS_MASK0 = 0x000533F9` | FINSIG (`playrec_mode` @ `0x0000C4D4`, `get_playrec_mode` @ `0xFC2D7297`, `task_MovieRecord` @ `0xFC09AC19`) / HISTORICAL_CHDK (`simple_movie_status` @ `0x0000C170` identified via store @ `0xFC09BD60`) / ROM_VERIFIED (`KEY_PLAYBACK` @ `0xFC66C9B8`) | Existing G3X code already covers this row (none; playback mode correctly evaluates `mode_play=1`, `mode_rec=0`; ALT and menu kbd paths are ungated in playback mode; `KEY_PLAYBACK` is covered by `KEYS_MASK0`). No missing FINSIG stubs required; proposed ROM read is not needed for build task |
| **6. Redraw trigger after an edit and integration with PORT-51 RESTORE2** | `chdk-port/core/gui_menu.c:401,414,437,1095-1132` (`gui_menu_redraw = 1` set upon item update; consumed in `gui_menu_draw()` to trigger partial row redraw; siblings lack double-buffering and sync restore) | `chdk-port/platform/g3x/gui_menu.c:54,422,435,458,1133-1176` (`gui_menu_redraw = 1` triggers DBUF shadow redraw of modified row & updates dirty rect); `chdk-port/platform/g3x/sub/110c/gui_sync.h:115-116,238-348` (CHDK function `g3x_shadow2_blit_restore_target` restores dirty rect to BOTH buffers under `G3X_GUI_RESTORE2=1`); `scripts/build_port43_dbuf.py:1650-1655` | `transfer_src_overlay` entry: `0xFC380635` (`gui_sync.h:82`); return-address comparison value: `0xFC380675` (`gui_sync.h:83,170-171,180,470-471`); epilogue hook site: `0xFC3806F8` (`gui_sync.h:498`); RAM callback pointer: `0x0000E26C` (`gui_sync.h:75,129,461`); `g3x_shadow2_blit_restore_target` is a CHDK function (`chdk-port/platform/g3x/sub/110c/gui_sync.h:115,238-348`); display buffers: `bitmap_buffer[0..1]` = `0x5FE80000`, `0x5FD00000`; `opacity_buffer[0..1]` = `0x5FC40000`, `0x5FB80000` | FINSIG (`transfer_src_overlay` entry @ `0xFC380635`) / ROM_VERIFIED (RAM callback pointer @ `0x0000E26C`, comparison lr @ `0xFC380675`, epilogue hook site @ `0xFC3806F8`) / INFERRED (runtime behavior in playback) | Existing G3X code already covers this row (none; restore mechanism is present in code: `gui_menu_draw` writes item edits into DBUF shadow buffer, and `g3x_shadow2_blit_restore_target` restores dirty rect into BOTH bitmap and opacity buffers on display sync; runtime behaviour in playback after edits is INFERRED, to be confirmed by owner trial) |

## Notes

1. **Navigation key cross-check**: `KEY_UP` (w0.b5, `0x20`), `KEY_DOWN` (w0.b6, `0x40`), `KEY_LEFT` (w0.b8, `0x100`), `KEY_RIGHT` (w0.b7, `0x80`), `KEY_SET` (w0.b9, `0x200`), and `KEY_MENU` (w0.b4, `0x10`) match `reference/finsig_gm110c/physw_bits.txt:7-12` and `docs/PORT46_KEYMAP.md:17-22` 100% with zero mismatches. All are covered by `KEYS_MASK0 = 0x000533F9`. Historical zoom candidate mismatch (GM1.10C events 0x16/0x12 vs CHDK 0x04/0x03 in `docs/PORT46_KEYMAP.md:40`) does not affect menu navigation.
2. **In-session persistence & save skip**: Item edits directly mutate the `conf` struct in RAM (`chdk-port/core/conf.c:20`). Values persist across menu close and re-open within session without card writes. Under `G3X_GUI_MENU=1` and `G3X_DISABLE_CARD_WRITES=1` / `OPT_DISABLE_FILE_WRITES=1`, `conf_save()` entry is intercepted at `core/conf.c:1159`, calls `g3x_conf_record_save_result(3)` (`G3X_CONF_SAVE_OFF`), and immediately returns, safely displaying `"SAVE:OFF"` on the OSD banner (`chdk-port/platform/g3x/gui_diag.h:975,1317`).
3. **Playback mode & FINSIG stubs**: In playback mode, `playrec_mode` (`0x0000C4D4`) evaluates to 0 or 1, causing `rec_mode_active()` to return 0 and `mode_get()` to assign `camera_info.state.mode_play = 1`, `mode_rec = 0`. Neither ALT mode entry nor the menu keyboard handler is gated off in playback mode. `task_MovieRecord` entry is `0xFC09AC19` (`reference/finsig_gm110c/stubs_entry.S:339`), while `0xFC09BD60` is the internal store instruction within `task_MovieRecord` used to identify `simple_movie_status` (`0x0000C170` in `chdk-port/platform/g3x/sub/110c/stubs_min.S:7`). All required stubs exist in FINSIG or `stubs_min.S`; proposed ROM read is not needed for the build task.
4. **PORT-51 RESTORE2 integration**: Item edits set `gui_menu_redraw = 1`, updating the modified row in the DBUF shadow layer (`g3x_shadow_bitmap`/`opacity`) and marking the dirty rectangle (`chdk-port/platform/g3x/gui_menu.c:422,435,458,1133-1176`). The CHDK restore function `g3x_shadow2_blit_restore_target` (`chdk-port/platform/g3x/sub/110c/gui_sync.h:115,238-348`) is executed via the PORT-49/PORT-51 sync hook: the RAM callback pointer at `0x0000E26C` (`gui_sync.h:75,129,461`) invokes `g3x_gui_sync_pre_cb`, which checks the saved caller lr against return-address comparison value `0xFC380675` (`gui_sync.h:83,170-171,180,470-471`) inside `transfer_src_overlay` (entry `0xFC380635`, `gui_sync.h:82`) and redirects the `transfer_src_overlay` epilogue pop at `0xFC3806F8` (`gui_sync.h:498`) to `g3x_gui_sync_post_trampoline` (`gui_sync.h:502-511`). Under `G3X_GUI_RESTORE2=1`, this restores the shadow dirty rectangle into BOTH `bitmap_buffer[0..1]` (`0x5FE80000`, `0x5FD00000`) and `opacity_buffer[0..1]` (`0x5FC40000`, `0x5FB80000`). The restore mechanism is present in code; runtime behaviour in playback after edits is INFERRED, to be confirmed by the owner trial.

## 5. Playback Logic: Function Definitions and Trial Checklist Code Mapping

### (a) Definitions and Staging Locations of Playback Helper Functions

All playback functions sit strictly behind `#if defined(G3X_PLAYBACK_MENU) && (G3X_PLAYBACK_MENU == 1)`:

1. **`g3x_playback_menu_is_active(void)`**:
   - **Staged by**: `scripts/build_port43_dbuf.py:2053-2056` into `stage_chdk/platform/g3x/kbd.c`.
   - **Definition**: Returns `camera_info.state.mode_play && !camera_info.state.gui_mode_none`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:73`.
   - **Called by**: `g3x_playback_menu_kbd_process()`.

2. **`g3x_playback_menu_kbd_process(void)`**:
   - **Staged by**: `scripts/build_port43_dbuf.py:2058-2066` into `stage_chdk/platform/g3x/kbd.c`.
   - **Definition**: Returns `g3x_playback_menu_is_active() ? 1 : 0`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:74`.
   - **Called by**: `my_kbd_read_keys()` in `stage_chdk/platform/g3x/kbd.c` (staged by `scripts/build_port43_dbuf.py:2070-2076`).

3. **`g3x_playback_menu_gui_mode_active(void)`**:
   - **Staged by**: `scripts/build_port43_dbuf.py:2088-2092` into `stage_chdk/platform/g3x/lib.c`.
   - **Definition**: Returns `camera_info.state.mode_play && (camera_info.state.gui_mode_alt || !camera_info.state.gui_mode_none)`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:75`.
   - **Called by**: `check_gui_needs_redraw()` in `stage_chdk/platform/g3x/lib.c` (staged by `scripts/build_port43_dbuf.py:2112-2118`) and `g3x_playback_menu_mode_check()` in `chdk-port/platform/g3x/main.c:75-76`.

4. **`g3x_playback_menu_get_viewport_mode(void)`**:
   - **Staged by**: `scripts/build_port43_dbuf.py:2094-2098` into `stage_chdk/platform/g3x/lib.c`.
   - **Definition**: Returns `camera_info.state.mode_play ? 1 : 0`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:76`.
   - **Called by**: `vid_get_viewport_width()` in `stage_chdk/platform/g3x/lib.c` (staged by `scripts/build_port43_dbuf.py:2102-2105`).

5. **`g3x_playback_menu_mode_check(void)`**:
   - **Defined in**: `chdk-port/platform/g3x/main.c:73-77` (and staged by `scripts/build_port43_dbuf.py:2150-2158`).
   - **Definition**: Calls `g3x_playback_menu_gui_mode_active()`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:77`.
   - **Called by**: `screen_rotated()` in `chdk-port/platform/g3x/main.c:66-68`.

6. **`g3x_playback_menu_record_item_edit(int type)`**:
   - **Defined in**: `chdk-port/platform/g3x/gui_menu.c:69-74`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:78`.
   - **Called by**: `update_int_value()` (`gui_menu.c:438`), `update_bool_value()` (`gui_menu.c:454`), `update_enum_value()` (`gui_menu.c:480`).

7. **`g3x_playback_menu_redraw_needed(void)`**:
   - **Defined in**: `chdk-port/platform/g3x/gui_menu.c:76-81`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:79`.
   - **Called by**: `check_gui_needs_redraw()` in staged `stage_chdk/platform/g3x/lib.c`.

8. **`g3x_playback_menu_record_open(void)`**:
   - **Defined in**: `chdk-port/platform/g3x/gui_diag.h:349-352`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:71`.
   - **Called by**: Staged `core/gui.c` (`scripts/build_port43_dbuf.py:1787`).

9. **`g3x_playback_menu_diag_format(char *buf, unsigned int max_len)`**:
   - **Defined in**: `chdk-port/platform/g3x/gui_diag.h:354-365`.
   - **Declared in**: `chdk-port/platform/g3x/gui_diag.h:72`.
   - **Called by**: `g3x_diag_format_line2()` in `chdk-port/platform/g3x/gui_diag.h:982-985`.

### (b) Mapping of Trial Checklist Steps to Code

| Step | Action | Code Handler | Status / Coverage |
|---|---|---|---|
| 1 | Enter Playback | `chdk-port/core/shooting.c:1687-1715` (`mode_get()` sets `camera_info.state.mode_play = 1`) | Covered by Canon firmware & core `mode_get()` |
| 2 | Enter ALT | `chdk-port/core/kbd.c` via `KEY_WIFI` mapped in `chdk-port/platform/g3x/kbd.c:40` and `platform_camera.h:20-22` | Covered by existing PORT-46 ALT handling |
| 3 | Open Menu | `chdk-port/core/gui.c:3134` (`gui_set_mode(&menuGuiHandler)`); open counted by `g3x_playback_menu_record_open()` (`scripts/build_port43_dbuf.py:1787`) | Covered by existing PORT-50 menu handler; open count tracked by PORT-53 hook |
| 4 | Navigate Up/Down | `chdk-port/platform/g3x/gui_menu.c:658-672` (`gui_menu_kbd_process()`), using `KEY_UP` (`0x00000020`, w0.b5) and `KEY_DOWN` (`0x00000040`, w0.b6) from `chdk-port/platform/g3x/kbd.c:35-36` | Covered by existing PORT-50 navigation code |
| 5 | Enter & Leave Submenus | `chdk-port/platform/g3x/gui_menu.c:510,677,717` (`select_sub_menu()`, `KEY_RIGHT`, `KEY_SET`) and `gui_menu.c:337,635,656,720,770,1384` (`gui_menu_back()`, `KEY_LEFT`, `KEY_DISPLAY`, `KEY_MENU`) | Covered by existing PORT-50 submenu code |
| 6 | Change Bool/Enum/Int Items | `chdk-port/platform/g3x/gui_menu.c:368-490` (`update_int_value`, `update_bool_value`, `update_enum_value`); edits tracked by `g3x_playback_menu_record_item_edit()` (`gui_menu.c:438,454,480`). Mutates in-RAM `conf` struct (`core/conf.c:20`) | Covered by existing PORT-50 item update routines; edit count tracked by PORT-53 hook |
| 7 | Close & Re-open Menu | `gui_set_mode(&altGuiHandler)`. In-RAM `conf` struct (`chdk-port/core/conf.c:20`) persists values. Re-opening re-reads `conf` | Covered by existing PORT-50 / CHDK core RAM state |
| 8 | Try Save & Confirm SAVE:OFF | `gui_menu.c:1388` calls `conf_save()`. Intercepted by write-protect guard staged at `core/conf.c:1159` (`scripts/build_port43_dbuf.py:1828`), which calls `g3x_conf_record_save_result(G3X_CONF_SAVE_OFF)` and returns. `gui_diag_draw()` displays `"SAVE:OFF"` banner (`gui_diag.h:1317`) | Covered by existing PORT-50 write-protect skip and diagnostic line |
