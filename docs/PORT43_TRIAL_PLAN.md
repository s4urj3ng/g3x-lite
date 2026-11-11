# PORT-43: Owner Trial and Recovery Plan (Double-Buffered GUI)

## 1. Overview & Safety Rules

Trial protocol for the double-buffered GUI build (`G3X_GUI_FIX=1 G3X_GUI_DBUF=1`) on Canon PowerShot G3 X (GM1.10C, DIGIC 6).

- **Strict Limits**: At most **2 power-ons** during this trial session.
- **Card-Write Safety**: SD card writes are strictly disabled at compile time (`G3X_DISABLE_CARD_WRITES=1`, `OPT_DISABLE_FILE_WRITES=1`). The physical SD card write-protect switch must remain locked (**LOCK** position).
- **RAM Execution**: Code executes strictly from DRAM (`DISKBOOT.BIN`). Camera flash ROM is never modified.
- **Recovery & Fallback**:
  - **Battery Pull**: To recover from any hang, remove the NB-10L battery for $\ge 10\text{ s}$ to fully discharge DRAM.
  - **Revert to PORT-42**: If any regression occurs, copy the known-good PORT-42 GUI DISKBOOT.BIN (`760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738`, 124,257 B) onto the SD card.

---

## 2. Preflight Checksum

Before inserting the SD card into the camera, verify the host checksum of `DISKBOOT.BIN`:

- **Path**: `out/port43-dbuf/DISKBOOT.BIN` (or `DISKBOOT.BIN` from `manifests/port43_gui_dbuf_manifest.json`)
- **Expected Size**: `126,329` bytes
- **Expected SHA-256**: `8d5509e597a598e8bb023adae46d4caa2c7ee1e2b763e4ff292f0aef21f9b140`

---

## 3. Trial Protocol Table

| Step | Action | Expected Behavior | Observation / Result |
| :--- | :--- | :--- | :--- |
| **1. Preflight** | Verify `DISKBOOT.BIN` SHA-256 on host; ensure SD card physical switch is set to **LOCK**. | SHA-256: `8d5509e597a598e8bb023adae46d4caa2c7ee1e2b763e4ff292f0aef21f9b140`<br>Size: 126,329 B. | `[ ] PASS  [ ] FAIL` |
| **2. Power-On 1** | Boot camera via **held press** (hold Power or Playback button for 1–2 s). Record startup method. | Camera boots with CHDK resident in DRAM without cutting power. | Boot method used:<br>`[ ] Held press`<br>`[ ] Short press` |
| **3. ALT Idle Video** | Press ALT key (Play/Shortcut) to display ALT key-help panel. **Record video for $\ge 10\text{ s}$ at idle.** | Overlay is stable; **no vanish-to-live-view cycle** (display flip no longer hides CHDK overlay). | `[ ] Stable (no vanish)`<br>`[ ] Vanished / cycled` |
| **4. Menu & Navigation** | Press Menu key in ALT mode to enter CHDK Menu. Navigate up/down through menu items for $\ge 10\text{ s}$. | **Repaint speed**: whole-box fast fill; does **NOT** grow in bands from the top. Cursor move touches only changed rows. | `[ ] Instant / fast repaint`<br>`[ ] Still grows in bands` |
| **5. Appearance Check** | Inspect colours, opacity, 2x font and layout on LCD screen. | Colours (neutral UYVY black/white), 100% opacity, crisp 2x font (16x32), and centered 880x576 layout **match PORT-42**. | `[ ] Matches PORT-42`<br>`[ ] Mismatch (record):` |
| **6. Regression Check** | Observe overall screen display during idle and navigation. | **No new regressions**: no pink blocks, no edge leaks, no lockups / freezes. | `[ ] Clean (no regressions)`<br>`[ ] Regression observed` |
| **7. Power-Off / Recov.** | Power off camera, or perform **battery pull** ($\ge 10\text{ s}$). If testing a second time, power on once more (maximum 2 power-ons total). | Clean shutdown or clean DRAM discharge. | `[ ] Clean shutdown`<br>`[ ] Battery pull required` |

---

## 4. Owner Recording Checklist

Please record and report the following observations:
1. **Video**: Record at least 10 seconds of video covering ALT/Menu at idle plus key navigation.
2. **Overlay Stability**: Is the overlay rock-solid, or does it exhibit the vanish-to-live-view cycle?
3. **Repaint Speed**: Does the menu repaint instantly, or does it still grow in bands from the top?
4. **Boot Method**: Was the camera started via held press (1–2 s) or short press (<0.5 s)?
5. **PORT-42 Parity**: Do colours (neutral black/white), opacity (solid opaque background), 2x integer font (16x32), and centered layout match PORT-42?
6. **New Regressions**: Were there any pink blocks, edge leaks, crashes, or lockups?

---

## 5. Rollback Procedure

If any blocking issue or regression is encountered:
1. Remove battery for $\ge 10\text{ s}$.
2. Insert SD card into card reader on PC.
3. Replace `DISKBOOT.BIN` with the PORT-42 build:
   - SHA-256: `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738`
   - Size: `124,257` bytes
4. Lock card and re-insert into camera to return to PORT-42 baseline.
