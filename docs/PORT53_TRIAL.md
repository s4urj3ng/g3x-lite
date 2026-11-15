# PORT-53 Owner Trial Plan (`G3X_PLAYBACK_MENU=1`, Playback ALT Menu Adaptation)

Short hardware trial protocol for the PORT-53 candidate build with playback-mode CHDK ALT menu support, navigation, in-session item editing, and card-write safety (`manifests/port53_playback_menu_manifest.json`, output directory `out/port53-playback-menu/`).

## 1. Safety & Card Writes Policy

- **Card writes disabled**: Compiled with `G3X_DISABLE_CARD_WRITES=1` and `OPT_DISABLE_FILE_WRITES=1`.
- **Physical write protect**: SD card write-protect switch remains **LOCKED** at all times.
- **Config save gated**: Displays `SAVE:OFF` on the menu diagnostic line. Config save attempts are intercepted and skipped; physical SD card writes are blocked.
- **In-session persistence**: Setting changes persist across menu close/re-open within the active session, but do not touch the SD card.

## 2. Pre-Trial Manifest Verification

Before inserting the SD card into the camera, verify the candidate artifacts against `manifests/port53_playback_menu_manifest.json`:

1. **Build command** (strictly **WITHOUT** `FULL_HOOKS`):
   ```sh
   python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --out-dir out/port53-playback-menu
   ```
   *Confirmation*: Config (c) build command contains NO `--full-hooks` flag and operates strictly without `FULL_HOOKS=1`.
2. **DISKBOOT.BIN SHA-256**: `620f39ccae74eceae96f9e4b6c41c77f3ed5e5219c42a013067b36241d6bf759` (confirmed matching fresh rebuild)
3. **DISKBOOT.BIN Size**: `132,209` bytes
4. **Core `_end`**: `0x0036aa40` (confirmed matching fresh rebuild)
5. **CHDK Files Count**: `34` modules in `CHDK/MODULES/`, plus `FONTS` and `LANG` distributions matching manifest.

Verify on host:
```sh
sha256sum out/port53-playback-menu/DISKBOOT.BIN
# Must match: 620f39ccae74eceae96f9e4b6c41c77f3ed5e5219c42a013067b36241d6bf759
```

## 3. Boot Method

- Insert write-protect LOCKED SD card into PowerShot G3 X.
- **Short press**: Tap `POWER` briefly (`< 500 ms`), per PORT-52 short-press boot mechanism.
- Camera powers on and enters normal live view or playback mode cleanly.

## 4. Numbered Playback Checklist

Execute the following 10 steps sequentially:

| Step # | Action | Details & Controls | Expected Outcome | What to Record |
|---|---|---|---|---|
| **1** | Enter Playback | Press `PLAYBACK` button (or power on directly into playback). | Camera switches to Canon image playback mode; last captured frame displays cleanly without freeze or lockup. | Pass / Fail; Canon playback active |
| **2** | Enter `<ALT>` | Press `WIFI` button (`KEY_WIFI`). | `<ALT>` indicator appears at bottom of screen. Diag line 1 and line 2 become visible. | Pass / Fail; Diag line 1 & 2 readings |
| **3** | Open Menu | Press `MENU` button (`KEY_MENU`). | Standard CHDK root menu opens overlaying the playback image. `MENU:0001` increments. No overlay tearing or freeze. | Pass / Fail; Diag line 2 (`MENU:0001`) |
| **4** | Up / Down Nav | Press `UP` (`KEY_UP`) and `DOWN` (`KEY_DOWN`) d-pad buttons. | Highlight cursor moves smoothly through menu items. No ghosting or lingering highlight artifacts. | Pass / Fail; cursor response |
| **5** | Enter & Leave Submenu | Press `SET` (`KEY_SET`) or `RIGHT` (`KEY_RIGHT`) to enter a submenu (e.g., *OSD Parameters*). Return to parent menu using `DISPLAY` (`KEY_DISPLAY`), pressing `SET` / `LEFT` on the submenu's `[Back]` item, or pressing `LEFT` (`KEY_LEFT`). | Submenu opens cleanly showing sub-items; pressing `DISPLAY`, `LEFT`, or selecting `[Back]` returns to parent root menu with previous item selected.<br>*Note*: Pressing `MENU` (`KEY_MENU`) closes the menu back to `<ALT>` mode directly per `gui_menu_kbd_process_menu_btn()`. | Pass / Fail; submenu enter & back; confirm parent return and MENU closing to ALT |
| **6** | Change Bool Item | Navigate to a boolean item (e.g., *Show OSD*), press `SET` (`KEY_SET`) or `LEFT`/`RIGHT`. | Checkbox state toggles immediately on screen (`[ ]` <-> `[*]`). Value changes in memory. | Pass / Fail; bool toggle observed |
| **7** | Change Enum Item | Navigate to an enum item (e.g., *Language* or mode selection), press `LEFT` / `RIGHT`. | Enum option cycles through available choices immediately on screen. | Pass / Fail; enum cycle observed |
| **8** | Change Int Item | Navigate to an integer item (e.g., numeric threshold or delay), press `LEFT` / `RIGHT`. | Integer numeric value increments or decrements immediately on screen. | Pass / Fail; int adjust observed |
| **9** | Close & Re-open Menu | Press `MENU` (`KEY_MENU`) to close menu, then press `MENU` again to re-open. | Menu closes cleanly. Upon re-opening (`MENU:0002`), the edited bool, enum, and int values remain at their changed values. | Pass / Fail; Diag line (`MENU:0002`), changed values confirmed |
| **10** | Save Attempt & SAVE:OFF | Navigate to *Save Options* / trigger conf save, or exit ALT mode. | Save attempt is safely skipped. Diagnostic lines display `SAVE:OFF` (Line 2: `MENU:xxxx SAVE:OFF Rs:xxxx Rp:xxxx B:x/xms` and Line 3: `MENU:xxxx SAVE:OFF ED:xxxx`). No disk I/O attempted, no camera hang. | Pass / Fail; `SAVE:OFF` confirmed on diag lines (Line 2: `SAVE:OFF` and Line 3: `MENU:xxxx SAVE:OFF ED:xxxx`) |

> [!NOTE]
> **Submenu parent-return vs MENU key**: In CHDK menus (`gui_menu.c`), `KEY_DISPLAY`, `KEY_LEFT`, or activating the submenu's `[Back]` (`...`) entry invokes `gui_menu_back()` to return from a child submenu to its parent. Pressing `MENU` (`KEY_MENU`) executes `gui_menu_kbd_process_menu_btn()` (`chdk-port/platform/g3x/gui_menu.c:1407`), which closes the menu entirely back to `<ALT>` mode instead of returning to the parent submenu.

## 5. Checklist Step-to-Code Mapping

| Checklist Step | Code Handler & Location | Coverage Status |
|---|---|---|
| Step 1 (Enter Playback) | `core/shooting.c:1687-1715` (`mode_get()` sets `camera_info.state.mode_play = 1`) | Covered by Canon firmware & core `mode_get()` |
| Step 2 (Enter ALT) | `core/kbd.c` via `KEY_WIFI` mapped in `platform/g3x/kbd.c:40` and `platform_camera.h:20-22` | Covered by existing PORT-46 ALT handling |
| Step 3 (Open Menu) | `core/gui.c:3134` (`gui_set_mode(&menuGuiHandler)`); open counted by `g3x_playback_menu_record_open()` (`scripts/build_port43_dbuf.py:1787`) | Covered by existing PORT-50 menu handler; open count tracked by PORT-53 hook |
| Step 4 (Navigate Up/Down) | `platform/g3x/gui_menu.c:658-672` (`gui_menu_kbd_process()`), using `KEY_UP` (`0x20`) and `KEY_DOWN` (`0x40`) from `platform/g3x/kbd.c:35-36` | Covered by existing PORT-50 navigation code |
| Step 5 (Enter & Leave Submenu) | `platform/g3x/gui_menu.c:535,683,739` (`select_sub_menu()`, `KEY_RIGHT`, `KEY_SET`); parent return via `gui_menu_back()` (`gui_menu.c:351,658,679,743,793`) via `KEY_DISPLAY`, `KEY_LEFT`, or `[Back]` item; `gui_menu_kbd_process_menu_btn()` (`gui_menu.c:1407`) on `KEY_MENU` exits directly to `altGuiHandler` (`<ALT>` mode) | Covered by existing PORT-50 submenu code |
| Step 6-8 (Change Bool/Enum/Int Items) | `platform/g3x/gui_menu.c:368-490` (`update_int/bool/enum_value`); edits tracked by `g3x_playback_menu_record_item_edit()` (`gui_menu.c:438,454,480`). Mutates in-RAM `conf` struct (`core/conf.c:20`) | Covered by existing PORT-50 item update routines; edit count tracked by PORT-53 hook |
| Step 9 (Close & Re-open Menu) | `gui_set_mode(&altGuiHandler)`. In-RAM `conf` struct (`core/conf.c:20`) retains mutated values. Re-opening re-reads `conf` | Covered by existing PORT-50 / CHDK core RAM state |
| Step 10 (Save Attempt & SAVE:OFF) | `gui_menu.c:1388` calls `conf_save()`. Intercepted by write-protect guard staged at `core/conf.c:1828` in config (c) and `__wrap_conf_save` in config (b), calling `g3x_conf_record_save_result(G3X_CONF_SAVE_OFF)` and returning. Diagnostic banner displays `"SAVE:OFF"` on Line 2 (`MENU:xxxx SAVE:OFF Rs:xxxx Rp:xxxx B:x/xms`) and Line 3 (`MENU:xxxx SAVE:OFF ED:xxxx`), and config (b) renders `MENU:xxxx SAVE:OFF ED:xxxx` via `g3x_playback_menu_diag_draw()`. | Covered by existing PORT-50 write-protect skip, diagnostic line, and PORT-53 standalone rendering path |

## 6. What to Record for Each Step

For every numbered step above, record:
1. **Pass / Fail status**.
2. **Diagnostic lines text**:
   - **Line 1**: `H:1/xxxx S:OK/<mode> L:xxxx R:xxxx F:xxxx M:xxxx Y:xxxx`
   - **Line 2**: `MENU:xxxx SAVE:OFF Rs:xxxx Rp:xxxx B:x/xms`
   - **Line 3**: `MENU:xxxx SAVE:OFF ED:xxxx`
3. Any unexpected display artifacts, flicker, or key response delays.
4. Record whether playback mode eliminated the Face+Tracking AF overlay flicker observed in record mode (see `chdk-port/platform/g3x/notes.txt`).

## 7. Emergency Recovery & Rollback

- **Battery-pull recovery**: If the camera locks up, fails to respond to key presses, or exhibits display distortion, immediately open the battery door and remove the battery. Wait at least 10 seconds. Note that pulling the battery only stops the current session: because the SD card holds the candidate `DISKBOOT.BIN` and is write-protect locked, the candidate loads again on the next boot until the card holds the baseline files or no `DISKBOOT.BIN`.
- **Card rollback to baseline files**: Remove SD card, place in host card reader, and replace `DISKBOOT.BIN` and `CHDK/` with the verified PORT-51 RESTORE2 no-FULL_HOOKS baseline files (`manifests/port51_restore2_nofullhooks_manifest.json`, `DISKBOOT.BIN` SHA-256 `f8df17f182289b4a100e8c348ecdca1ea7f2e9a8c1613058d9777dd832fed3cf`, `131,865` bytes, `_end` `0x0036a8e0`) or the earlier candidate manifest (`manifests/port51_restore2_manifest.json`, `DISKBOOT.BIN` SHA-256 `4fad35b503be9f0a0ed799cf4cd62721db61e8dc6fa0ba348a507e52937d622a`, `131,929` bytes, `_end` `0x0036a920`), or remove `DISKBOOT.BIN` entirely to boot stock Canon firmware. Ensure SD card physical lock switch is engaged before returning card to camera.
