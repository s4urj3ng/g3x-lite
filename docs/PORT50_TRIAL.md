# PORT-50 Owner Trial Plan (`G3X_GUI_MENU=1`)

Short hardware trial protocol for the opt-in `G3X_GUI_MENU=1` candidate with standard CHDK menu navigation and FINSIG configuration save/load (`out/port50-gui-menu/`, pinned in `manifests/port50_gui_menu_manifest.json`).

## 1. Assumptions Table

| Address / Value | Label / Symbol | Source | Confidence / Status |
|---|---|---|---|
| `0x00000010` (w0.b4) | `KEY_MENU` (event `0x14`) | `physw_bits.txt:7`, `PORT46_KEYMAP.md:17` | FINSIG (HW verified UI-001B-1) |
| `0x00000020` (w0.b5) | `KEY_UP` (event `0x06`) | `physw_bits.txt:8`, `PORT46_KEYMAP.md:18` | FINSIG (HW verified UI-001B-1) |
| `0x00000040` (w0.b6) | `KEY_DOWN` (event `0x07`) | `physw_bits.txt:9`, `PORT46_KEYMAP.md:19` | FINSIG (HW observed UI-001B-1) |
| `0x00000100` (w0.b8) | `KEY_LEFT` (event `0x08`) | `physw_bits.txt:11`, `PORT46_KEYMAP.md:21` | FINSIG (HW observed UI-001B-1) |
| `0x00000080` (w0.b7) | `KEY_RIGHT` (event `0x09`) | `physw_bits.txt:10`, `PORT46_KEYMAP.md:20` | FINSIG (HW observed UI-001B-1) |
| `0x00000200` (w0.b9) | `KEY_SET` (event `0x0a`) | `physw_bits.txt:12`, `PORT46_KEYMAP.md:22` | FINSIG |
| `0x00001000` (w0.b12) | `KEY_DISPLAY` (event `0x0d`) | `physw_bits.txt:14`, `PORT46_KEYMAP.md:24` | FINSIG |
| `0x00002000` (w0.b13) | `KEY_WIFI` (ALT key, event `0x103`) | `physw_bits.txt:17`, `platform_camera.h:20` | FINSIG |
| `0x000533F9` | `KEYS_MASK0` (button override mask) | `platform_kbd.h:8`, `PORT46_KEYMAP.md:28` | INFERRED (covers 12 keys, preserves Power) |
| `0xFC37B3B5` | `Open` (FatFs file open) | `reference/finsig_gm110c/stubs_entry.S:253` | FINSIG |
| `0xFC37B471` | `Write` (FatFs file write) | `reference/finsig_gm110c/stubs_entry.S:289` | FINSIG |
| `0xFC37B439` | `Close` (FatFs file close) | `reference/finsig_gm110c/stubs_entry.S:198` | FINSIG |
| `0xFC418D61` | `Read` (FatFs file read) | `reference/finsig_gm110c/stubs_entry.S:263` | FINSIG |
| `0xFC37B595` | `lseek` (FatFs seek) | `reference/finsig_gm110c/stubs_entry.S:307` | FINSIG |
| `0xFC37B5CD` | `stat` (FatFs file stat) | `reference/finsig_gm110c/stubs_entry.S:322` | FINSIG |
| `0x0000E26C` | `G3X_GUI_SYNC_CALLBACK_PTR_ADDR` | `docs/PORT49_GUI_SYNC.md` (c), `manifests/port49_gui_sync_evidence.json` | ROM_VERIFIED |

## 2. Pre-Trial Candidate Artifacts

- **Candidate build command**:
  ```sh
  python3 scripts/build_port43_dbuf.py --gui-menu
  ```
- **Manifest**: `manifests/port50_gui_menu_manifest.json`
- **DISKBOOT.BIN SHA-256**: `7fa091329c0d3d43e531004bcd135ab4f452e2a574aad4949888445720d6fca8` (`131,321` bytes)
- **Core `_end`**: `0x0036a6b0`
- **Flags**: `G3X_FULL_BUILD=1 G3X_DISABLE_CARD_WRITES=1 CAM_SUPPORT_BITMAP_RES_CHANGE=1 OPT_DISABLE_FILE_WRITES=1 G3X_GUI5=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1 G3X_GUI_SYNC=1 G3X_GUI_MENU=1`

## 3. Trial Protocol

### Trial (A): PORT-49 Baseline Verification
1. Copy the PORT-49 candidate (`manifests/port49_gui_sync_manifest.json`, DISKBOOT `e31e97a1...`, `131,185` bytes) to FAT32 SD card.
2. Power on with held `POWER` button (`~1 s`) to boot into live view.
3. Press `WIFI` (`KEY_WIFI`) to enter `<ALT>` mode.
4. Pan the camera across scenes and trigger autofocus half-presses (`KEY_SHOOT_HALF`).
5. **Record**:
   - Overlay flicker: `yes` / `no`.
   - Counter line readings: `H` (installed/hits), `S` (shadow alloc), `R` (shadow blits), `F` (forced redraws), `L` (sentinel losses), `M` (free memory), and sync counter `Y`.

### Trial (B): PORT-50 Menu & Configuration Persistence
1. Copy the PORT-50 candidate (`manifests/port50_gui_menu_manifest.json`, DISKBOOT `7fa09132...`, `131,321` bytes) to FAT32 SD card (card write-protect tab **UNLOCKED** so FAT32 config write succeeds).
2. Power on with held `POWER` button (`~1 s`) to boot into live view.
3. Press `WIFI` (`KEY_WIFI`) to enter `<ALT>` mode.
   - Verify bottom lines: `<ALT>`, counter line, and diagnostic line: `MENU:0000 CONF:-`.
4. Press `MENU` (`KEY_MENU`):
   - Verify CHDK Main Menu opens in double-buffered display.
   - Verify menu-open counter increments: `MENU:0001`.
5. Navigate with d-pad (`UP` / `DOWN` / `LEFT` / `RIGHT`):
   - Move selection cursor across menu items.
6. Open one submenu (e.g., `OSD Settings` or `GUI Settings`) using `SET` (`KEY_SET`) or `RIGHT`.
7. Toggle one harmless setting (e.g., toggle an OSD display item or change a numeric value by `1`).
8. Press `MENU` or navigate to `Back` to exit the menu:
   - Verify config autosave triggers through FINSIG stubs (`Open` -> `Write` -> `Close`).
   - Verify diagnostic line updates: `CONF:OK` (or `CONF:ERR` if write failed).
9. Exit `<ALT>` mode by pressing `WIFI`.
10. Power off camera, wait `5 s`, then power on again.
11. Enter `<ALT>` mode (`WIFI`), press `MENU`, navigate to the altered setting, and **verify that the changed setting persisted across reboot**.

## 4. Recovery and Rollback

- **Battery-pull recovery**: If camera hangs, displays a blank or frozen screen, or fails to respond to power button, immediately open the battery compartment door and pull the battery. Reinsert battery with SD card removed or unlocked to boot stock Canon firmware from internal ROM (no flash or permanent firmware modifications occur).
- **Rollback to PORT-49**: Replace `DISKBOOT.BIN` and `CHDK/` on the SD card with the PORT-49 candidate (`out/port49-gui-sync/DISKBOOT.BIN`, SHA-256 `e31e97a1b4e700aaff36e1da80ffff8e335fd162d29be2e6b3400afe8aa5a2a1`, `131,185` bytes, pinned in `manifests/port49_gui_sync_manifest.json`).
