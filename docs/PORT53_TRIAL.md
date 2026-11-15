# PORT-53 Owner Trial Plan (`G3X_PLAYBACK_MENU=1`, Playback ALT Menu Adaptation)

Short hardware trial protocol for the PORT-53 candidate build with playback-mode CHDK ALT menu support, navigation, in-session item editing, and card-write safety (`manifests/port53_playback_menu_manifest.json`, output directory `out/port53-playback-menu/`).

## 1. Safety & Card Writes Policy

- **Card writes disabled**: Compiled with `G3X_DISABLE_CARD_WRITES=1` and `OPT_DISABLE_FILE_WRITES=1`.
- **Physical write protect**: SD card write-protect switch remains **LOCKED** at all times.
- **Config save gated**: Displays `SAVE:OFF` on the menu diagnostic line. Config save attempts are intercepted and skipped; physical SD card writes are blocked.
- **In-session persistence**: Setting changes persist across menu close/re-open within the active session, but do not touch the SD card.

## 2. Pre-Trial Manifest Verification

Before inserting the SD card into the camera, verify the candidate artifacts against `manifests/port53_playback_menu_manifest.json`:

1. **Build command**:
   ```sh
   python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --out-dir out/port53-playback-menu
   ```
2. **DISKBOOT.BIN SHA-256**: `b054f24264084bd51fd50d90dfa9af9e54c9bef1e8afb318aa1bc6a6f2185fe6`
3. **DISKBOOT.BIN Size**: `132,145` bytes
4. **Core `_end`**: `0x0036aa00`
5. **CHDK Files Count**: `34` modules in `CHDK/MODULES/`, plus `FONTS` and `LANG` distributions matching manifest.

Verify on host:
```sh
sha256sum out/port53-playback-menu/DISKBOOT.BIN
# Must match: b054f24264084bd51fd50d90dfa9af9e54c9bef1e8afb318aa1bc6a6f2185fe6
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
| **5** | Enter & Leave Submenu | Press `SET` (`KEY_SET`) or `RIGHT` (`KEY_RIGHT`) to enter a submenu (e.g., *OSD Parameters*), then `MENU` (`KEY_MENU`) to return. | Submenu opens cleanly showing sub-items; pressing `MENU` returns to parent root menu with previous item selected. | Pass / Fail; submenu enter & back |
| **6** | Change Bool Item | Navigate to a boolean item (e.g., *Show OSD*), press `SET` (`KEY_SET`) or `LEFT`/`RIGHT`. | Checkbox state toggles immediately on screen (`[ ]` <-> `[*]`). Value changes in memory. | Pass / Fail; bool toggle observed |
| **7** | Change Enum Item | Navigate to an enum item (e.g., *Language* or mode selection), press `LEFT` / `RIGHT`. | Enum option cycles through available choices immediately on screen. | Pass / Fail; enum cycle observed |
| **8** | Change Int Item | Navigate to an integer item (e.g., numeric threshold or delay), press `LEFT` / `RIGHT`. | Integer numeric value increments or decrements immediately on screen. | Pass / Fail; int adjust observed |
| **9** | Close & Re-open Menu | Press `MENU` (`KEY_MENU`) to close menu, then press `MENU` again to re-open. | Menu closes cleanly. Upon re-opening (`MENU:0002`), the edited bool, enum, and int values remain at their changed values. | Pass / Fail; Diag line (`MENU:0002`), changed values confirmed |
| **10** | Save Attempt & SAVE:OFF | Navigate to *Save Options* / trigger conf save, or exit ALT mode. | Save attempt is safely skipped. Diagnostic line displays `SAVE:OFF`. No disk I/O attempted, no camera hang. | Pass / Fail; `SAVE:OFF` confirmed on diag line |

## 5. What to Record for Each Step

For every numbered step above, record:
1. **Pass / Fail status**.
2. **Diagnostic lines text**:
   - **Line 1**: `H:1/xxxx S:OK/<mode> L:xxxx R:xxxx F:xxxx M:xxxx Y:xxxx`
   - **Line 2**: `MENU:xxxx SAVE:OFF Rs:xxxx Rp:xxxx B:x/xms`
3. Any unexpected display artifacts, flicker, or key response delays.
4. Record whether playback mode eliminated the Face+Tracking AF overlay flicker observed in record mode (see `chdk-port/platform/g3x/notes.txt`).

## 6. Emergency Recovery & Rollback

- **Battery-pull recovery**: If the camera locks up, fails to respond to key presses, or exhibits display distortion, immediately open the battery door and remove the battery. Wait at least 10 seconds. Close door, reinsert battery, and power on. Camera will boot cleanly into stock Canon firmware from read-only internal ROM.
- **Card rollback to PORT-52**: Remove SD card, place in host card reader, and replace `DISKBOOT.BIN` and `CHDK/` with the PORT-52 verified build (`manifests/port52_shortpress_manifest.json`, `DISKBOOT.BIN` SHA-256 `93f18eec00c2837bc2fd17b0d0dc08709cf906ee6225b68e9ee263b6b158fcda`, `131,985` bytes). Ensure SD card physical lock switch is engaged before returning card to camera.
