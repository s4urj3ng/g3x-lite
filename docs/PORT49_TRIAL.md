# PORT-49 Owner Trial Plan (`G3X_GUI_SYNC=1`)

Short hardware trial checklist for the opt-in `G3X_GUI_SYNC=1` synchronous display-flip candidate (`out/port49-gui-sync/`, pinned in `manifests/port49_gui_sync_manifest.json`).

## 1. Pre-Trial Verification (`VERIFIED` Build Artifacts)

1. Build the candidate on the host:
   ```sh
   python3 -B scripts/build_port43_dbuf.py --gui-sync
   ```
2. Verify `DISKBOOT.BIN` and every `CHDK/` file SHA-256 against `manifests/port49_gui_sync_manifest.json` before copying to a FAT32 SD card:
   - `DISKBOOT.BIN`: `e31e97a1b4e700aaff36e1da80ffff8e335fd162d29be2e6b3400afe8aa5a2a1` (`131,185` bytes)
   - Core `_end`: `0x0036a620`
   - Flags: `G3X_FULL_BUILD=1 G3X_DISABLE_CARD_WRITES=1 CAM_SUPPORT_BITMAP_RES_CHANGE=1 OPT_DISABLE_FILE_WRITES=1 G3X_GUI5=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1 G3X_GUI_SYNC=1`

## 2. Camera Trial Steps

1. Insert the SD card (write-protect tab **LOCKED**) and test both power-on modes:
   - **Held press**: hold `POWER` (`~1 s`) to boot into live view, then power off.
   - **Short press**: tap `POWER` briefly to boot into live view.
2. Press the `<ALT>` button (`WIFI` / `KEY_WIFI`) once to enter `<ALT>` mode; press `MENU` to open the CHDK Main Menu.
3. Read the bottom two diagnostic lines (`<ALT>` key line + `G3X_GUI_SYNC=1` counter line):
   ```text
   H:1/xxxx S:OK/exmem L:xxxx R:xxxx F:xxxx M:xxxx Y:xxxx
   ```
4. **Pan and trigger AF**: pan the camera across high-contrast targets and half-press the shutter (`KEY_SHOOT_HALF`) several times to trigger Canon AF / exposure / OSD composition updates (`transfer_src_overlay` at `0xFC380635`), then record:
   - Whether the CHDK `<ALT>` / menu overlay still flickers during panning and AF.
   - The counter values `H`, `S`, `L`, `R`, `F`, `M`, and the new sync-hook counter `Y`.

## 3. Confirm / Refute Criteria for the `INFERRED` Hook (`0x0000E26C` -> `sp_entry[23]`)

The hook installs `g3x_gui_sync_pre_cb` at `*(volatile uint32_t *)0x0000E26C` (`ROM_VERIFIED`, `docs/PORT49_GUI_SYNC.md` (c); `manifests/port49_gui_sync_evidence.json`) so `GraphicSystemCoreFinish_helper` (`0xFC143493`) intercepts `transfer_src_overlay` (`0xFC380635`, call site `0xFC380670`, `lr = 0xFC380675`) and patches `sp_entry[23]` (`[sp_entry, #92]`) to `g3x_gui_sync_post_trampoline` (`INFERRED` runtime execution order before hardware trial):

- **Hook CONFIRMED**:
  - `H:1/xxxx` (`H` installed flag is `1` and hit count increments).
  - **`Y:` increments** (`Y > 0000`, climbing on live-view OSD flips, panning, and half-press AF).
  - **`R:` increments** synchronously (`R > 0000`) as the post-transfer hook blits `g3x_dbuf_shadow_*` into `bitmap_buffer[r9 & 1]` and `opacity_buffer[r9 & 1]` before `VTM_FlipAndCommit` (`0xFC38090B`) writes `active_bitmap_buffer` (`0x0000D2A4`).
  - **`L:` stays `0000` (or near `0000`)** and **`F:` stays `0001`**, because the sync hook restores the target buffer and its `0x42` sentinels before the 20 ms `core_spytask` poll sees a lost sentinel.
  - **Overlay flicker is eliminated** (or visibly reduced to zero) while panning and triggering AF in `<ALT>`.
- **Hook REFUTED**:
  - **`Y:0000`** while panning and triggering AF (confirming `GraphicSystemCoreFinish_helper` at `0xFC143493` / `transfer_src_overlay` at `0xFC380670` did not match `sp_entry[1] == 0xFC380675`), while `L:` and `R:` increment via the asynchronous 20 ms poll fallback; **or**
  - **`Y:` increments (`Y > 0000`)** and `R:` increments, but the `<ALT>` overlay **still visibly flickers** during panning/AF (indicating another composition/DMA path overwrites the active buffer after `transfer_src_overlay` returns).

## 4. Recovery and Rollback

- **Battery-pull recovery**: if the camera does not boot, hangs, or displays a corrupted screen, switch off or **open the battery door and pull the battery immediately**, unlock or remove the SD card, and reinsert the battery to boot stock Canon firmware from internal ROM (`no permanent flash or NVRAM writes occur`).
- **Rollback to PORT-48**: replace `DISKBOOT.BIN` and `CHDK/` on the SD card with the verified PORT-48 `G3X_GUI_SHADOW2=1` candidate (`out/port48-shadow-alloc/DISKBOOT.BIN`, SHA-256 `9ac53c2720f96e40b6ff95e64ed069139c80c170d521a0e4fc01dd9c03ad4db1`, `130,857` bytes, pinned in `manifests/port48_shadow_alloc_manifest.json`).
