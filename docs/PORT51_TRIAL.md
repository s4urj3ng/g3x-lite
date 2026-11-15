# PORT-51 Owner Trial Plan (`G3X_GUI_RESTORE2=1`, Both-Buffer Sync Restore)

Short hardware trial protocol for the candidate with both-buffer synchronous display-flip restore and bounded dirty-rect timing (`out/port51-restore2-core/`, pinned in `manifests/port51_restore2_manifest.json`).

## 1. Safety & Card Writes Policy

- **Card writes disabled**: Built with `G3X_DISABLE_CARD_WRITES=1` and `OPT_DISABLE_FILE_WRITES=1`.
- **Physical write protect**: SD card write-protect switch remains **LOCKED** at all times.
- **Config save gated**: Displays `SAVE:OFF` on the menu diagnostic line. Changes are in-session only; persistence across reboot is deferred.

## 2. Pre-Trial Candidate Artifacts

- **Candidate build command**:
  ```sh
  python3 -B scripts/build_port43_dbuf.py --full-hooks --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --out-dir out/port51-restore2-core
  ```
- **Candidate manifest**: `manifests/port51_restore2_manifest.json` (and `out/port51-restore2-core/manifest.json`)
- **DISKBOOT.BIN SHA-256**: `4fad35b503be9f0a0ed799cf4cd62721db61e8dc6fa0ba348a507e52937d622a` (`131,929` bytes)
- **Core `_end`**: `0x0036a920`
- **Build flags**: `G3X_FULL_BUILD=1 FULL_HOOKS=1 G3X_DISABLE_CARD_WRITES=1 CAM_SUPPORT_BITMAP_RES_CHANGE=1 OPT_DISABLE_FILE_WRITES=1 G3X_GUI5=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1 G3X_GUI_SYNC=1 G3X_GUI_MENU=1 G3X_GUI_RESTORE2=1`

## 3. Trial (A) Protocol

1. **Boot**: Insert the write-protect LOCKED SD card. Test both power-on modes:
   - **Held press**: Hold `POWER` (`~1 s`) to boot directly into live view.
   - **Short press**: Tap `POWER` briefly to boot into live view.
2. **Enter `<ALT>`**: Press `WIFI` (`KEY_WIFI`) to engage `<ALT>` mode. Verify the two bottom diagnostic lines:
   - Line 1: `H:1/xxxx S:OK/<mode> L:xxxx R:xxxx F:xxxx M:xxxx Y:xxxx`
   - Line 2: `MENU:0000 SAVE:OFF Rs:0000 Rp:0000 B:0/0ms`
3. **Open Menu**: Press `MENU` (`KEY_MENU`) to display the CHDK menu. Verify `MENU:0001` and `SAVE:OFF`.
4. **Pan and Trigger AF**:
   - Pan camera rapidly across high-contrast scenes.
   - Half-press shutter (`KEY_SHOOT_HALF`) repeatedly to trigger autofocus and exposure metering updates (`transfer_src_overlay` at `0xFC380635`).
5. **Record Observations**:
   - **Flicker**: `yes` / `no` (confirm whether both-buffer restore eliminates overlay flicker during AF/panning).
   - **Line 1 Counters**:
     * `H`: Hook installed flag (`1`) / total hook hit count.
     * `S`: Shadow tier (`OK/rect`, `OK/exmem`, `OK/idx`).
     * `L`: Sentinel loss count (expected `0000` under clean both-buffer sync restore).
     * `R`: Total shadow restore count (`Rs + Rp`).
     * `F`: Full redraw count.
     * `M`: Overdraw suppression hit count.
     * `Y`: Sync hook callback hits at `*(0x0000E26C)`.
   - **Line 2 Counters**:
     * `MENU`: Menu open count.
     * `SAVE`: Configuration save status (`OFF`).
     * `Rs`: Synchronous restore count via `transfer_src_overlay` hook.
     * `Rp`: Asynchronous 20 ms poll-loop fallback restore count.
     * `B`: Blit duration last / max (`B:last/max ms`; 1 ms resolution via DryOS `GetSystemTime`).

## 4. Emergency Recovery and Rollback

- **Battery-pull recovery**: If the camera freezes, exhibits display artifacts, or fails to respond to button input, immediately open the battery door and pull the battery. Remove or unlock the SD card, reinsert battery, and power on to boot stock Canon firmware from read-only internal ROM. No permanent flash or NVRAM writes occur.
- **Rollback to PORT-50**: Replace `DISKBOOT.BIN` and `CHDK/` on the SD card with the PORT-50 candidate (`manifests/port50_gui_menu_manifest.json`, DISKBOOT `c5cd59f05c026e540681039a8184bcedb5718030d4d108db8e6e7c5cefcf4480`, `130,745` bytes).
