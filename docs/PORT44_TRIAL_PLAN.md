# PORT-44: Owner Trial and Recovery Plan (Double-Buffered GUI with Runtime Heap Shadow)

## 1. Overview & Safety Rules

Trial protocol for the candidate build with lazy runtime heap shadow buffer (`G3X_GUI_FIX=1 G3X_GUI_DBUF=1`) on Canon PowerShot G3 X (GM1.10C, DIGIC 6). This build moves the double-buffer shadow out of core BSS into runtime heap allocation (`malloc`/`umalloc` on first GUI entry), restoring core `_end` to `0x00369490` (+3,296 B above PORT-42, well within the 64 KiB margin).

- **Strict Limits**: Test held press first, then short press (maximum 2 power-ons per trial cycle).
- **Card-Write Safety**: SD card writes are strictly disabled at compile time (`G3X_DISABLE_CARD_WRITES=1`, `OPT_DISABLE_FILE_WRITES=1`). The physical SD card write-protect switch must remain locked (**LOCK** position).
- **RAM Execution**: Code executes strictly from DRAM (`DISKBOOT.BIN`). Camera flash ROM is never modified.
- **Recovery & Fallback**:
  - **Battery Pull**: To recover from any unexpected shutdown or hang, remove the NB-10L battery for $\ge 10\text{ s}$ to fully discharge DRAM.
  - **Rollback to PORT-42**: If any regression occurs, copy the known-good PORT-42 GUI DISKBOOT.BIN (`760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738`, 124,257 B) onto the SD card.
- **Tooling Policy**: No automated report decoder or classifier tool is added or used. All observations are reported directly using the checklist below.

---

## 2. Preflight Checksum Verification

Before inserting the SD card into the camera, check the SHA-256 and size against the manifest (`manifests/port44_dbuf_heap_manifest.json`):

- **Target File**: `DISKBOOT.BIN`
- **Expected Size**: `126,769` bytes
- **Expected SHA-256**: `2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382`

---

## 3. Owner Trial Protocol Table

| Step | Action | Expected Behavior | Observation / Result |
| :--- | :--- | :--- | :--- |
| **1. Preflight** | Verify `DISKBOOT.BIN` SHA-256 against manifest; ensure physical SD switch is **LOCK**. | SHA-256: `2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382`<br>Size: 126,769 B. | `[ ] PASS  [ ] FAIL` |
| **2. Boot Trial 1 (Held Press)** | Start with a **held press** (hold Power or Playback button for 1–2 s). | Camera boots without cutting power (heap intact at `_end = 0x00369490`). | `[ ] Boots successfully`<br>`[ ] Cuts power / blinks` |
| **3. Boot Trial 2 (Short Press)** | Power off (or battery pull), then try a **short press** (<0.5 s tap). | Camera boots cleanly with short press. | `[ ] Boots successfully`<br>`[ ] Did not boot` |
| **4. ALT Mode Entry** | Press ALT key (Play/Shortcut) to display ALT overlay. | ALT overlay opens; lazy heap allocation succeeds; screen displays ALT prompt. | `[ ] ALT opens cleanly`<br>`[ ] Fails / crashes` |
| **5. CHDK Menu Entry** | Press Menu key in ALT mode to enter CHDK Menu. | CHDK Menu opens with 880x576 black box and 2x font. | `[ ] Menu opens cleanly`<br>`[ ] Fails to open` |
| **6. Overlay Stability (Idle)** | Keep ALT / Menu active at idle for $\ge 10\text{ s}$. | Overlay is rock-steady; **no flicker**; no vanish-to-live-view cycles. | `[ ] Steady (no flicker)`<br>`[ ] Flickers / vanishes` |
| **7. Navigation Stability** | Navigate up/down through menu items for $\ge 10\text{ s}$. | Cursor moves smoothly; repaints touch only changed rows; no flicker or band growth. | `[ ] Smooth partial redraw`<br>`[ ] Flickers / redraws bands` |
| **8. Visual Parity Check** | Inspect colours, opacity, 2x font, and 880x576 layout. | Neutral UYVY colours, solid black opacity, 2x font (16x32), and layout **match PORT-42**. | `[ ] Matches PORT-42`<br>`[ ] Mismatch observed` |
| **9. Regression Inspection** | Inspect LCD screen for any graphical anomalies or instability. | **No regressions**: zero pink blocks, zero edge leaks, zero lockups. | `[ ] Clean (no regressions)`<br>`[ ] Regression observed` |
| **10. Shutdown / Recov.** | Normal power-off, or **battery pull** ($\ge 10\text{ s}$). | Clean shutdown. If recovery needed, battery pull clears DRAM. | `[ ] Clean shutdown`<br>`[ ] Battery pull used` |

---

## 4. Owner Reporting Checklist

The owner reports back the following items (a video recording of at least 10 seconds is welcome):

- [ ] **Boot (Held Press)**: Does it boot with a held press (1–2 s)? (`Yes / No`)
- [ ] **Boot (Short Press)**: Does it boot with a short press (<0.5 s)? (`Yes / No`)
- [ ] **ALT / Menu Open**: Does the ALT overlay and CHDK Menu open normally? (`Yes / No`)
- [ ] **Overlay Steady (Idle)**: Is the overlay steady (no flicker / no vanish-to-live-view) at idle? (`Yes / No`)
- [ ] **Overlay Steady (Navigating)**: Is the overlay steady (no flicker / no growing bands) while navigating? (`Yes / No`)
- [ ] **Visual Parity**: Are colours, opacity, 2x font (16x32), and 880x576 layout identical to PORT-42? (`Yes / No`)
- [ ] **Regressions**: Any regressions observed (pink blocks, edge leaks, lockups)? (`None / Describe`)
- [ ] **Video**: Optional video of at least 10 seconds attached? (`Yes / No`)

---

## 5. Rollback Procedure (Known-Good PORT-42 Baseline)

If any hang, boot failure, or regression is encountered during testing:
1. Pull the camera battery and wait $\ge 10\text{ s}$ to fully discharge DRAM.
2. Remove SD card and insert into host card reader.
3. Replace `DISKBOOT.BIN` with the recorded PORT-42 candidate:
   - **File**: `DISKBOOT.BIN`
   - **Size**: `124,257` bytes
   - **SHA-256**: `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738`
4. Ensure the SD card lock switch is in **LOCK** position.
5. Reinsert battery and SD card to restore camera to the known-good PORT-42 baseline.
