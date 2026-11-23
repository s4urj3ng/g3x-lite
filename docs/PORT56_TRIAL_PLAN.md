# PORT-56 Owner Trial and Recovery Plan (`G3X_MOVIE_NOLIMIT=1`)

Hardware trial checklist and recovery protocol for the PORT-56 movie time-limit bypass candidate (`G3X_MOVIE_NOLIMIT=1` + `G3X_MOVIE_STATUS=1` + full interactive UI stack).

---

## 1. Candidate Artifacts & Preflight

The candidate binary is Configuration (c) from `docs/PORT56_MOVIE_TIMELIMIT.md` Section 6 ("Candidate Build Configurations & Artifacts").

| Property | Primary Candidate: Configuration (c) (Full Combination) | Recovery Build: Configuration (a) (Default Build) |
|---|---|---|
| **Build Type** | Full interactive candidate (`G3X_MOVIE_NOLIMIT=1` opt-in) | Default baseline build (stock flags) |
| **Output Path** | `out/port56-movie-nolimit/DISKBOOT.BIN` | `out/build-default/DISKBOOT.BIN` |
| **Manifest** | `manifests/port56_movie_nolimit_manifest.json` | — |
| **Size (bytes)** | `132,385` | `124,097` |
| **SHA-256** | `c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352` | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` |
| **Core `_end`** | `0x0036aaf0` | `0x003686b0` |
| **Build Flags** | `G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1 G3X_GUI_SYNC=1 G3X_GUI_MENU=1 G3X_GUI_RESTORE2=1 G3X_PLAYBACK_MENU=1 G3X_MOVIE_STATUS=1 G3X_MOVIE_NOLIMIT=1` | None (stock flags) |
| **Execution Safety** | Strictly volatile SDRAM execution; zero persistent ROM/flash modifications | Strictly volatile SDRAM execution |
| **SD Card Switch** | Set to **LOCK** (write-protect engaged) | Set to **LOCK** (write-protect engaged) |

> [!NOTE]
> Verify host SHA-256 of `DISKBOOT.BIN` before copying to SD card:
> ```sh
> sha256sum out/port56-movie-nolimit/DISKBOOT.BIN
> # Expected: c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352
> ```

---

## 2. Test Mode & Resolution Selection

Per `docs/PORT56_MOVIE_TIMELIMIT.md` Section 3 ("Stock Limit Applicability by Video Resolution & Mode"):

- **Named Test Mode**: **HD 720p 30p / 25p** (`1280x720`).
- **Why HD 720p**:
  - In **FHD 60p** (~35 Mbps) and **FHD 30p** (~24 Mbps), the stock 4 GiB file size policy (Reason 3, `0xFC098C5C`) stops recording early at ~16m 20s and ~23m 50s, before reaching 29:59.
  - In **HD 720p 30p/25p** (~8 Mbps video + ~192 kbps audio), 29:59 of video is only ~1.93 GiB. The 29:59 duration limit (Reason 4, `0xFC098B28`) is therefore the **first** limiting factor encountered.
  - At 35 minutes, file size is ~2.15 GiB, well below the 4 GiB size ceiling. Recording past 29:59 (e.g. 31 to 35 minutes) provides direct, definitive proof of time-limit defeat.

---

## 3. Step-by-Step Owner Checklist

| Step # | Action | Controls & Procedure | Expected Outcome |
|---|---|---|---|
| **1** | **Host Hash Check** | Verify host SHA-256 of `DISKBOOT.BIN` before copying to SD card. Slide SD card write-protect switch to **LOCK**. | Hash matches `c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352` (`132,385` B). |
| **2** | **Boot by Short Press** | Insert locked SD card; tap `POWER` button briefly (< 500 ms). | Camera boots cleanly into live view without holding the power button. |
| **3** | **Check Idle Markers on Diag Line** | Set camera to **HD 720p** movie resolution. Press `WIFI` (`KEY_WIFI`) to enter CHDK `<ALT>` mode. Inspect diagnostic Line 2. | Diag Line 2 displays: `MOV:IDLE` and `LIM:?`<br>(`MENU:xxxx SAVE:OFF MOV:IDLE LIM:? Rs:xxxx Rp:xxxx`). |
| **4** | **Start Movie Recording & Check Markers** | Press the red Canon Movie button to start recording. Observe the OSD diagnostic line and remaining-time display. | • `MOV:` changes from `IDLE` to `REC` (`MOV:REC`).<br>• `LIM:` changes from `?` to `OFF` (`LIM:OFF`), confirming `mr_max_frames` at `0x0000C274` was overwritten with `0xFFFFFFFF`.<br>• Check if remaining-time display changes or does not clamp to 29:59. |
| **5** | **Record Past Stock Limit Point** | Allow continuous recording to run past the stock 29:59 limit point (target: **31 to 35 minutes** at HD 720p). | Recording continues past `29:59` and `30:00` without halting or throwing error. |
| **6** | **Clean Stop by User Press** | At ~31–35 minutes, press the red Movie button to stop recording. | Movie stops cleanly; file container finalizes; camera returns to live view. Markers return to `MOV:IDLE` and `LIM:?`. |
| **7** | **Check File Playback** | Switch to playback mode (`PLAYBACK` button). Select the recorded video clip and press `SET` to play. | Video clip plays back smoothly from beginning to end on camera LCD with synchronized audio; recorded duration matches trial time (> 29:59). |
| **8** | **Check CHDK ALT Menu** | Press `WIFI` (`KEY_WIFI`) to enter `<ALT>`, then press `MENU` (`KEY_MENU`). Navigate using d-pad (`UP`/`DOWN`). Press `MENU` to close. | CHDK ALT menu opens cleanly, navigates without freeze or display corruption, and closes cleanly back to `<ALT>`. |

---

## 4. Results Table for Owner

Please fill in the observed values during and after the trial:

| Field | Parameter | Expected Value | Owner Observed Value | Pass / Fail |
|---|---|---|---|---|
| **1** | Host SHA-256 Check | `c8709189...` (`132,385` B) | | `[ ] PASS  [ ] FAIL` |
| **2** | Short-Press Boot (< 500 ms) | Clean boot to live view | | `[ ] PASS  [ ] FAIL` |
| **3** | **LIM: value (idle)** | `LIM:?` | `LIM:____` | `[ ] PASS  [ ] FAIL` |
| **4** | **MOV: value (idle)** | `MOV:IDLE` | `MOV:____` | `[ ] PASS  [ ] FAIL` |
| **5** | **LIM: value (recording)** | `LIM:OFF` | `LIM:____` | `[ ] PASS  [ ] FAIL` |
| **6** | **MOV: value (recording)** | `MOV:REC` | `MOV:____` | `[ ] PASS  [ ] FAIL` |
| **7** | Remaining-Time Display | Changed or > 29:59 | | `[ ] PASS  [ ] FAIL` |
| **8** | **Recorded length** | > 29:59 (e.g. 31m–35m) | `____ min ____ sec` | `[ ] PASS  [ ] FAIL` |
| **9** | **Clean stop** | Yes (clean return to live view) | `[ ] YES  [ ] NO` | `[ ] PASS  [ ] FAIL` |
| **10** | **LIM: value (post-stop)** | `LIM:?` | `LIM:____` | `[ ] PASS  [ ] FAIL` |
| **11** | **MOV: value (post-stop)** | `MOV:IDLE` | `MOV:____` | `[ ] PASS  [ ] FAIL` |
| **12** | File playback | Yes (plays cleanly with audio) | `[ ] YES  [ ] NO` | `[ ] PASS  [ ] FAIL` |
| **13** | **Menu OK** | Yes (opens, navs, closes) | `[ ] YES  [ ] NO` | `[ ] PASS  [ ] FAIL` |

---

## 5. Meaning of Each Outcome for Next Build

| Observed Outcome | Interpretation & Root Cause | Impact & Next Build Action |
|---|---|---|
| **Full Success**<br>(`LIM:OFF`, `MOV:REC`, length > 29:59, clean stop YES, menu OK YES) | Overwriting `mr_max_frames` at `0x0000C274` with `0xFFFFFFFF` in the kbd/GUI loop successfully and safely defeats the 29:59 limit without side effects or crashes. | **Promote feature**: Enable `G3X_MOVIE_NOLIMIT=1` by default in interactive builds or provide a toggle in the CHDK Video Settings menu. |
| **Limit Hit at 29:59**<br>(`LIM:ON` while recording, stops exactly at 29:59) | The RAM write to `0x0000C274` was either not executed or was overwritten back by Canon firmware before `MovieRecorder_CheckFrameCountLimit` ran. | **Adjust write timing**: Increase polling frequency in kbd loop or investigate whether `SetupModeAndLimits` is called cyclically during capture. |
| **Marker `LIM:?` While Recording**<br>(`MOV:REC` active, but `LIM:?` shown) | The value at `0x0000C274` was read as 0 or could not be verified; the safety guard skipped writing to avoid writing into uninitialized memory. | **Verify address offset**: Confirm whether base register `0x0000C1F8` offset varies under specific camera settings. |
| **Early Stop Before 29:59**<br>(Stops at ~16m 20s or ~23m 50s) | The 4 GiB file size policy (Reason 3, `0xFC098C5C`) halted capture because movie mode was set to FHD (1080p 60p/30p) rather than HD 720p. | **User configuration note**: The 4 GiB size limit remains active and working as intended. Ensure camera is set to HD 720p for testing duration bypass. |
| **Stop Press Hangs / Freeze**<br>(Clean stop NO; camera hangs on movie button stop) | Overwriting `mr_max_frames` with `0xFFFFFFFF` interfered with movie recorder container finalization or duration header calculation upon stop. | **Add stop-transition cleanup**: Restore original frame count or clamp to actual elapsed frames immediately when `g3x_get_movie_status()` signals stopping. |
| **Menu Freeze After Recording**<br>(Menu OK NO; ALT menu hangs after movie capture) | Interaction or memory contention between movie recorder thread cleanup and CHDK GUI double-buffer / keyboard task. | **Audit heap / buffer**: Audit memory allocation and display buffer ownership during video encode teardown. |

---

## 6. Recovery Plan

If the camera freezes, hangs, displays visual distortion, or fails to respond at any point during the trial, execute the following recovery protocol:

### Step 1: Battery Pull (Clean SDRAM Reset)
- CHDK executes exclusively from volatile SDRAM (`DISKBOOT.BIN`) and performs **zero** writes to onboard persistent flash ROM.
- Open the battery door and remove the Canon NB-10L battery.
- **Wait $\ge 10$ seconds** to ensure complete power rail decay and full DRAM state discharge.
- Reinserting the battery returns the camera hardware to a clean, unpowered factory state.

### Step 2: Revert to Default Build
- Remove the SD card and insert it into a host PC card reader.
- Replace `DISKBOOT.BIN` on the card with the verified default build:
  - **Path**: `out/build-default/DISKBOOT.BIN`
  - **Size**: `124,097` bytes
  - **SHA-256**: `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9`
- Ensure the physical SD card write-protect switch is set to **LOCK**.
- Reinsert SD card into camera and verify standard CHDK default operation.

### Step 3: Stock Canon Firmware (Optional Direct Bypass)
- To bypass CHDK entirely and boot 100% factory Canon ROM firmware, slide the physical SD card switch to **UNLOCKED** (or remove the SD card / delete `DISKBOOT.BIN`).
- An unlocked card bypasses bootdisk execution; the camera boots directly into stock Canon firmware.
