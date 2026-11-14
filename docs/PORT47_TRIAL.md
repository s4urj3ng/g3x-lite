# PORT-47 Owner Trial Plan (`G3X_GUI_DIAG=1`)

**Scope:** **VERIFIED** host build and manifest hashes; **UNKNOWN** on-camera counter dynamics and visual overdraw behavior until owner trial.

## Candidate & Rollback Hashes

| Build | Flags | `DISKBOOT.BIN` Size | `DISKBOOT.BIN` SHA-256 | Core `_end` | Manifest |
|---|---|---|---|---|---|
| **PORT-47 Candidate** | `G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1` | `128,057 B` | `9b6d9ad95b2512e487f9d7d6ae694ab9fddbaee731339570240f77bbcfc7e5f7` | `0x003699b0` | [port47_gui_diag_manifest.json](../manifests/port47_gui_diag_manifest.json) |
| **Rollback (PORT-45+46)** | `G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1` | `127,449 B` | `7c91eaa622ff0ca44b8d60219da1418ca34dc4a837a6112c39b6bbd31e285798` | `0x00369730` | [port46_kbd_check_manifest.json](../manifests/port46_kbd_check_manifest.json) (`variants.no-overdraw`) |

## Counter Line Legend (`y = 536`, 2x Font `16x32`, below `kbd_check` line at `y = 504`)

Format: `H:<0/1>/<hits> S:<NULL/OK>/1520640 L:<loss> R:<restore> F:<full> M:<suppress>`

| Field | Meaning |
|---|---|
| `H:<0/1>/<hits>` | `G3X_GUI_NOOVERDRAW` hook installed (`0`/`1`) and hook hit count |
| `S:<NULL/OK>/1520640` | Heap shadow pointer status (`NULL` or `OK`) and shadow size in bytes (`1,520,640`) |
| `L:<loss>` | Opacity sentinel-loss count (`!draw_test_guard()`) |
| `R:<restore>` | Single-blit shadow-restore count (`g3x_dbuf_shadow_restore()`) |
| `F:<full>` | Full-redraw count (`gui_redraw(1)`, reachable only when `S:NULL`) |
| `M:<suppress>` | Hit count for adapted G5X `check_gui_needs_redraw` (`active_bitmap_buffer` at `0x0000D2A4`) |

## Trial Steps & Observation Table

| Step | Action | Expected / What to Record | Observed Counter Line (`H: ... M:`) | Overlay Disappears? (`yes`/`no`) | Redraws in Bands? (`yes`/`no`) |
|---|---|---|---|---|---|
| 1 | **Verify hashes** on host before SD copy (`DISKBOOT.BIN` + `CHDK/`) | `DISKBOOT.BIN` SHA-256 = `9b6d9ad95b2512e487f9d7d6ae694ab9fddbaee731339570240f77bbcfc7e5f7` (`128,057 B`) | N/A | N/A | N/A |
| 2 | **Boot with held press** (`PLAY` or `ON/OFF` held $\ge 1\text{ s}$) | Camera boots cleanly with SD write-protect `LOCK` engaged | N/A (ALT off) | N/A | N/A |
| 3 | Power off, then **boot with short press** ($\approx 0.2\text{ s}$) | Camera boots cleanly into Play/Rec without hang or shutdown | N/A (ALT off) | N/A | N/A |
| 4 | **Enter `<ALT>`** (short press `WIFI`) and **record at rest** (5 s) | Both 2x diagnostic lines visible inside `880x576`; record `H:`, `S:`, `L:`, `R:`, `F:`, `M:` | `H:_/____ S:____/1520640 L:____ R:____ F:____ M:____` | | |
| 5 | **Record while panning** camera across scene in `<ALT>` (5 s) | Record counter deltas (`L:`, `R:`, `F:`, `M:`) and whether overlay stays solid | `H:_/____ S:____/1520640 L:____ R:____ F:____ M:____` | | |
| 6 | **Record while AF / half-press (`KEY_SHOOT_HALF`) runs** in `<ALT>` | Key line shows `KEY_SHOOT_HALF`; record counter line and overlay behavior | `H:_/____ S:____/1520640 L:____ R:____ F:____ M:____` | | |
| 7 | **Exit `<ALT>`** (`WIFI`), re-enter `<ALT>`, and open `MENU` | Verify clean suppression release on exit and shadow state on re-entry | `H:_/____ S:____/1520640 L:____ R:____ F:____ M:____` | | |

## Owner Checklist, Recovery & Rollback

- [ ] **Hash check:** Verified `DISKBOOT.BIN` (`9b6d9ad9...`, `128,057 B`) and all 242 `CHDK/` files match `manifests/port47_gui_diag_manifest.json`; SD card switch set to `LOCK`.
- [ ] **Held-press boot:** Confirmed clean boot with held press.
- [ ] **Short-press boot:** Confirmed clean boot with short press.
- [ ] **ALT at rest:** Recorded counter line (`H:`, `S:OK/1520640` vs `S:NULL/1520640`, `L:`, `R:`, `F:`, `M:`) and noted whether overlay disappears or redraws in bands.
- [ ] **ALT while panning:** Recorded counter line while panning and noted whether overlay disappears or redraws in bands.
- [ ] **ALT during AF / half-press:** Recorded counter line during `KEY_SHOOT_HALF` / AF and noted whether overlay disappears or redraws in bands.
- [ ] **Recovery (if camera hangs or screen locks):** Open battery door, pull battery for $\ge 10\text{ s}$, slide SD card switch to unlock or remove SD card, reinsert battery, and verify stock GM1.10C boots normally.
- [ ] **Rollback:** Restore the PORT-45+46 build (`G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1`, `DISKBOOT.BIN` SHA-256 `7c91eaa622ff0ca44b8d60219da1418ca34dc4a837a6112c39b6bbd31e285798`, `127,449 B`) from `manifests/port46_kbd_check_manifest.json` (`variants.no-overdraw`).
