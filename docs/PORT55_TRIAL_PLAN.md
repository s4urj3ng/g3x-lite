# PORT-55 Owner Trial and Recovery Plan (`G3X_MOVIE_STATUS=1`)

Hardware trial protocol and recovery plan for the PORT-55 combined candidate (configuration c) verifying non-invasive movie recording state telemetry (`mr_rec_state` @ `0x0000C0C8`, `MOV:IDLE` / `MOV:REC` / `MOV:?`).

## 1. Candidate Artifacts & Preflight

| Property | Configuration (c) — Primary Candidate | Configuration (b) — Standalone Reference (Optional) |
|---|---|---|
| **Build Type** | Full combined non-invasive feature stack | `G3X_MOVIE_STATUS=1` alone |
| **Output Path** | `out/port55-movie-status/DISKBOOT.BIN` | `out/build-movie-alone/DISKBOOT.BIN` |
| **Manifest** | `manifests/port55_movie_status_manifest.json` | — |
| **Size (bytes)** | `132,297` | `124,081` |
| **SHA-256** | `1f3d46569f95efa06a2acb0dabe0b11639bbcea6b147fd10e3ec31718944184f` | `be2a0839e4f74a78d4770c12d28ea3775229b88ad02801746908aa1a32787f9f` |
| **Core `_end`** | `0x0036aa90` | `0x003686a0` |
| **Card Writes** | Strictly disabled (`G3X_DISABLE_CARD_WRITES=1`, `OPT_DISABLE_FILE_WRITES=1`); switch **LOCKED** | Strictly disabled; switch **LOCKED** |

---

## 2. Step-by-Step Owner Checklist

| Step # | Action | Details & Controls | Expected Outcome | What to Record |
|---|---|---|---|---|
| **0** | **Hash Check** | Verify host SHA-256 of candidate `DISKBOOT.BIN` before copy to SD card. Ensure SD card switch is **LOCK**. | Hash matches `1f3d4656...` (`132,297` B) exactly. | `[ ] PASS  [ ] FAIL`<br>Recorded SHA-256 |
| **1** | **Short-Press Boot** | Insert locked SD card; tap `POWER` button briefly (< 500 ms). | Camera boots cleanly into live view without holding power button. | `[ ] PASS  [ ] FAIL`<br>Boot mode (Rec/Play) |
| **2** | **Diag Line Idle Check** | Press `WIFI` (`KEY_WIFI`) to enter `<ALT>`. Inspect diagnostic line in **shooting mode**, then switch to **playback mode** and inspect `<ALT>`. | Telemetry line displays `MOV:IDLE` in shooting mode and `MOV:IDLE` in playback mode (`st = 0`). | `[ ] PASS  [ ] FAIL`<br>Shooting marker: `MOV:____`<br>Playback marker: `MOV:____` |
| **3** | **Start Movie Recording** | In shooting mode, press Canon movie button to record a short stock video clip (~5 s). | Diag line changes from `MOV:IDLE` to `MOV:REC` (`st = 1`) while recording is active. | `[ ] PASS  [ ] FAIL`<br>Recording marker: `MOV:____` |
| **4** | **Stop Movie Recording** | Press movie button again to stop recording. Observe diag line as clip finalizes. | Diag line cleanly transitions back from `MOV:REC` to `MOV:IDLE` once recording stops. | `[ ] PASS  [ ] FAIL`<br>Post-stop marker: `MOV:____` |
| **5** | **Playback Menu Check** | Switch to playback mode, press `WIFI` (`KEY_WIFI`) for `<ALT>`, then press `MENU` (`KEY_MENU`). | CHDK ALT menu opens cleanly, navigates via d-pad (`UP`/`DOWN`), and closes cleanly with `MENU`. | `[ ] PASS  [ ] FAIL`<br>Menu open & nav verified |
| **6** | *(Optional) Repeat with (b)* | Copy standalone build (b) (`124,081` B, `be2a0839...`) to SD card; repeat Steps 0–4. | `MOV:IDLE` -> `MOV:REC` -> `MOV:IDLE` transitions identical to combined candidate. | `[ ] PASS  [ ] FAIL  [ ] SKIPPED` |

---

## 3. Outcome Analysis & Failure Mapping

| Observed Outcome | Meaning & Likely Cause | Next Diagnostic Step |
|---|---|---|
| **`MOV:IDLE` -> `MOV:REC` -> `MOV:IDLE`** | **SUCCESS**: Variable address (`0x0000C0C8`) and state encoding (`0`=idle, `1`=rec) are correct. | Proceed with full port integration. |
| **`MOV:?` throughout** | **Wrong Address or Invalid Encoding**: Address `0x0000C0C8` does not point to `mr_rec_state`, or reads unexpected state values ($> 1$). | Note raw value in memory; inspect ROM table structure or alternative candidates. |
| **`REC` never shows** (stuck on `MOV:IDLE`) | **Wrong Encoding**: Firmware active-recording value is not `1`, or reading wrong field offset within `MovieRecorder` struct. | Inspect raw value at `0x0000C0C8` during active recording to discover true active state bitmask/integer. |
| **Stuck `REC`** (`MOV:REC` persists after stop) | **Value Not Cleared**: Variable is a latch, teardown flag, or completion counter rather than active recording state. | Re-evaluate `0x0000C0C8` vs teardown store targets (`0x0000C1F0`); verify teardown handler flow. |

---

## 4. What the Owner Should Record

Please write down the following specific observations:
1. **Shooting Mode Idle Marker**: Exact token shown (`MOV:IDLE`, `MOV:REC`, or `MOV:?`).
2. **Active Recording Marker**: Exact token shown during movie capture (`MOV:REC`, `MOV:IDLE`, or `MOV:?`).
3. **Post-Stop Marker**: Exact token shown after stopping capture (`MOV:IDLE`, `MOV:REC`, or `MOV:?`).
4. **Playback Mode Marker**: Exact token shown in playback ALT mode (`MOV:IDLE` or other).
5. **Raw / Unexpected Value**: If `MOV:?` or unexpected marker appears, any raw value or string shown on LCD.
6. **CHDK Menu in Playback**: Whether ALT menu opens, navigates, and closes without freeze (`PASS / FAIL`).
7. **Boot Method**: Confirm short-press boot succeeded (`< 500 ms`).

---

## 5. Recovery Plan

1. **Battery Pull (Clean SDRAM Reset)**:
   - The candidate executes strictly from volatile SDRAM (`DISKBOOT.BIN`) and never modifies onboard flash ROM.
   - If the camera freezes, hangs, or fails to respond to button presses, open the battery compartment and remove the NB-10L battery.
   - Wait $\ge 10\text{ s}$ to ensure complete power rail collapse and DRAM state discharge.
   - Reinserting the battery returns the camera hardware to a clean, unpowered state.

2. **RAM-Only Execution Safety**:
   - Zero ROM writes or persistent flash modifications occur.
   - All CHDK code and variables reside entirely in volatile memory.

3. **Reverting to Default Build or Stock Firmware**:
   - **Default CHDK Build**: In PC card reader, replace `DISKBOOT.BIN` on the locked SD card with the known-good default build (`out/build-default/DISKBOOT.BIN`, SHA-256 `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9`, `124,097` bytes).
   - **Stock Canon Firmware**: Slide the SD card write-protect switch to **UNLOCKED** (or remove SD card / delete `DISKBOOT.BIN`). An unlocked card bypasses DISKBOOT autoboot, allowing the camera to boot 100% factory Canon ROM firmware immediately.
