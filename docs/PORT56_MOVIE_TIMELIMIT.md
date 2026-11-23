# PORT-56 — Movie Time-Limit Evidence Table & Mechanism Analysis

**Verdict**:
- (a) Every sibling (g7x, g5x, sx60hs, sx280hs) defeats the limit through a movie_rec task replacement or has movie hooks disabled (`g7x`: `chdk-port/platform/g7x/sub/100d/boot.c:134-138`; `g5x`: `chdk-port/platform/g5x/sub/100c/boot.c:139-144`; `sx60hs`: `chdk-port/platform/sx60hs/sub/100h/boot.c:165-171`; `sx280hs`: `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:10-12,548-550` and `chdk-port/platform/sx280hs/sub/102b/boot.c:147-152`).
- (b) Under the scope amendment in the PORT56-LIMIT-RESEARCH2 task description (Tech Lead, owner-delegated, 2026-11-15), a FULL_HOOKS-free mechanism exists: rewrite mr_max_frames at 0x0000C274 (ROM_VERIFIED address, INFERRED mechanism) from the GUI/kbd loop while g3x_get_movie_status()==1. SetupModeAndLimits (0xFC097D72, called at 0xFC09A97C) resets this variable on every recording start, so the write must be repeated after each start.
- (c) The milestone therefore continues to PORT56-LIMIT-BUILD2.

**Recommended Mechanism**:
- **Write rule**: While `MOV:REC` holds (`g3x_get_movie_status() == 1`), check `mr_max_frames` (`0x0000C274`) on every GUI/kbd loop tick and overwrite it with `0xFFFFFFFF` whenever the value is nonzero and not already `0xFFFFFFFF`. Do NOT treat `MOV:REC` as proof that setup has finished (`docs/VIDEO001_RECORDING_LIMITS.md:183`). Never rely on a single write. Never write while not recording. Diag marker: `LIM:OFF` when the patched value (`0xFFFFFFFF`) is in place while recording (limit defeated); `LIM:ON` when the stock value is seen while recording (limit active); `LIM:?` otherwise. Re-enforced on each recording start because `SetupModeAndLimits` runs on each recording start (manifest `PORT56-ROM-CMD0-SETUP-CALL`).
- **Target**: Write only `0x0000C274` (`mr_max_frames = 0xFFFFFFFF`). Do NOT write `0x0000C0E4` (UI warning only) or `0x0000C0C0` (stop reason).
- **Cap**: Note that the 4 GiB size stop (reason 3, `0xFC098C5C`) stays active and is the real cap.

> [!NOTE]
> Function names used herein (`MovieRecorder_SetupModeAndLimits` @ `0xFC097D72`, `MovieRecorder_CheckFrameCountLimit` @ `0xFC098AE0`, `MovieRecorder_CheckSizeAndSpaceLimits` @ `0xFC098BAA`, `MovieRecorder_CmdStartPipeline` @ `0xFC09A956`, `MovieRecorder_ProcessEncodedFrame` @ `0xFC098E9E`) are reverse-engineering descriptive labels from project Ghidra analysis, not official Canon symbols or FINSIG names.
> In `reference/finsig_gm110c/funcs_by_name.csv` and `stubs_entry.S`, internal MovieRecorder helpers are not extracted; the nearest preceding FINSIG entry is `task_DevelopJpeg` (`0xFC09333D`), and the nearest succeeding entry is `task_MovieRecord` (`0xFC09AC19` / `stubs_entry.S:339`).

---

## 1. Evidence Table

| item | sibling path:line | GM1.10C address/value | label (FINSIG/INFERRED/HISTORICAL_CHDK/ROM_VERIFIED) | change needed |
|---|---|---|---|---|
| **1. Sibling time-limit defeat mechanism (`set_movie_time_limit`)** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:10-12,548-550`; `chdk-port/platform/sx280hs/sub/102c/movie_rec.c:10-12,550-552`; `chdk-port/platform/generic/movie_rec.c:72-80` | N/A (CHDK core helper in `generic/movie_rec.c:72-80`; not in Canon firmware; called exclusively within replaced `movie_record_task`) | HISTORICAL_CHDK | None; requires `CAM_MOVIEREC_NEWSTYLE` and full `task_MovieRecord` task replacement. |
| **2. Sibling `task_MovieRecord` boot hook (`task_create_hook`)** | `chdk-port/platform/sx280hs/sub/102b/boot.c:150-155`; `chdk-port/platform/g7x/sub/100d/boot.c:134-138` (commented out); `chdk-port/platform/g5x/sub/100c/boot.c:139-144` (commented out); `chdk-port/platform/sx60hs/sub/100h/boot.c:165-171` (commented out) | `task_MovieRecord = 0xFC09AC19` (`reference/finsig_gm110c/stubs_entry.S:339`, `funcs_by_name.csv:2459`) | FINSIG | None; intercepting `CreateTask` requires `FULL_HOOKS`. Kept unhooked / commented out in G3X Lite as on all modern DIGIC 6 siblings. |
| **3. Sibling platform definitions (`CAM_CHDK_HAS_EXT_VIDEO_MENU` / `CAM_VIDEO_CONTROL` / `CAM_MOVIEREC_NEWSTYLE`)** | `chdk-port/platform/g7x/platform_camera.h:65-66`; `chdk-port/platform/g5x/platform_camera.h:42-43`; `chdk-port/platform/sx60hs/platform_camera.h:20-21`; `chdk-port/platform/sx280hs/platform_camera.h:14,17` (`#define CAM_MOVIEREC_NEWSTYLE 1`) | `#undef CAM_CHDK_HAS_EXT_VIDEO_MENU`, `#undef CAM_VIDEO_CONTROL`, `CAM_MOVIEREC_NEWSTYLE` undefined (`chdk-port/platform/g3x/platform_camera.h:28-29`) | INFERRED | None; remain undefined in `platform_camera.h` to prevent invoking unimplemented movie_rec hooks. |
| **4. Sibling stubs in `movie_rec.c`** | `chdk-port/platform/g5x/sub/100c/movie_rec.c:6-11`; `chdk-port/platform/sx60hs/sub/100f/movie_rec.c:6-11`; `chdk-port/platform/g7x/` (no `movie_rec.c`) | `chdk-port/platform/g3x/sub/110c/movie_rec.c:1-12` (`change_video_tables`, `set_quality` empty stubs) | HISTORICAL_CHDK | None; G5X/SX60HS `set_quality` is not empty (contains a conditional quality write), but their movie task hooks are disabled; G3X keeps empty stubs. |
| **5. GM1.10C stock duration limit constants (`1799` s FHD/HD, `3599` s VGA)** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:10-12,543-544` (`FW_SHORT_TIME_LIMIT 30`, `SHORT_TIME_LIMIT 300`, `LONG_TIME_LIMIT 10800`) | `0xFC09853E`: `movw r0, #0x707` (1799 s = 29:59 FHD/HD); `0xFC09859A`: `movw r0, #0xE0F` (3599 s = 59:59 VGA) in `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`) | ROM_VERIFIED | None; hardcoded in ROM flash. |
| **6. Setup function execution timing & reinitialization** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:540-565` (runs on startup of replaced movie task) | `0xFC09A97C`: `BL 0xFC097D72` (`MovieRecorder_SetupModeAndLimits`) called unconditionally inside `MovieRecorder_CmdStartPipeline` (`0xFC09A956`) during Command 0 dispatch upon recording start. Does not run at idle mode switch. | ROM_VERIFIED | Writes must occur **after** record start. Any pre-recording write (boot/mode switch) is overwritten on record start. Timing correction (`docs/VIDEO001_RECORDING_LIMITS.md:183`): `MOV:REC` does NOT mean limit setup has finished; recording state becomes 1 before limits are initialised, and setup runs again on every record start (`BL 0xFC09A97C`). On every loop tick while recording (`g3x_get_movie_status() == 1`), if the value at `0x0000C274` is nonzero and not already `0xFFFFFFFF`, overwrite it with `0xFFFFFFFF` (`blo` at `0xFC098B22`); do nothing when not recording. Late setup stores are overwritten on the next tick, long before the 1799 s limit. |
| **7. GM1.10C max frames variable (`mr_max_frames`) store** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:565` (`str r0, [r1, #0x6c]`) | `0x0000C274` (`mr_max_frames`, stored at `0xFC098692`: `str r1, [r0, #0x7C]` with `r0 = 0x0000C1F8`, `r1 = (max_sec * fps_num) / fps_den`) | ROM_VERIFIED | Opt-in runtime write `*(volatile uint32_t *)0x0000C274 = 0xFFFFFFFF` (or `0x7FFFFFFF`) from kbd/GUI loop while recording (`mr_rec_state == 1`). |
| **8. Frame limit check & branch signedness (`MovieRecorder_CheckFrameCountLimit`)** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:548-550` (defeated by overriding `r6` before frame calculation) | `0xFC098B10..38`: `0xFC098B22` `cmp r0, r1` (`cur_frames` @ `0x0000C278` vs `max_frames` @ `0x0000C274`) followed by `0xFC098B24: 04 d3` (`blo 0xFC098B30`). **Unsigned** lower branch. Falls through to stop reason `*(0x0000C0C0) = 4` at `0xFC098B28` only when `cur_frames >= max_frames`. | ROM_VERIFIED | Disabling value is `0xFFFFFFFF` (or `0x7FFFFFFF`). Setting `0x0000C274` to `0xFFFFFFFF` makes `cur_frames < max_frames` permanently True, bypassing Reason 4 stop. |
| **9. UI warning threshold variable (`mr_warn_sec`) & effect if unchanged** | `chdk-port/platform/sx280hs/sub/102b/movie_rec.c:568` (`str.w r0, [sb, #0x50]`) | `0x0000C0E4` (`mr_warn_sec`, stored at `0xFC09869C`: `max_sec - 10`). Evaluated at `0xFC0992FE`: `cmp r1, r0` -> posts UI warning event `0x3149` (bit 1 of `0x0000C0C4`) at 29:49. | ROM_VERIFIED | Optional. Does **not** terminate recording. If left untouched, camera displays stock 10s warning at 29:49 while recording continues. Writing `0xFFFFFFFF` suppresses the warning icon. |
| **10. GM1.10C 4 GiB file size policy check (`MovieRecorder_CheckSizeAndSpaceLimits`)** | Not addressed in siblings (`chdk-port/platform/sx280hs/sub/102b/movie_rec.c` halts at 4 GiB) | `0xFC098C40..70`: `0xFC098C48..58` 64-bit comparison against `segment * 0xFFFFFFFF`. Halts recording with stop reason `*(0x0000C0C0) = 3` at `0xFC098C5C`. Stock GM1.10C **stops** at 4 GiB; it does **not** start a new file. | ROM_VERIFIED | None (don't defeat). Limits FHD 60p to ~16m20s and FHD 30p to ~23m50s. For HD 720p, the ~8 Mbps video figure is an estimate; with audio at ~192 kbps AAC (`docs/VIDEO001_RECORDING_LIMITS.md:101`), 60 min is about 3.7 GB, below the 4 GiB stop. The minute at which the 4 GiB stop (Reason 3, `0xFC098C5C`) is reached depends on the real bitrate. |
| **11. FULL_HOOKS-free execution context (kbd/GUI loop)** | `chdk-port/platform/g7x/lib.c:231,247`; `chdk-port/platform/g3x/gui_diag.h:18-24`; `chdk-port/core/gui.c` | Non-invasive polling in `mykbd_task` / `gui_sync` reading `mr_rec_state` (`0x0000C0C8`, PORT-55). SetupModeAndLimits (`0xFC097D72`) rewrites `mr_max_frames` on every recording start (called from `0xFC09A97C`). The candidate must therefore rewrite `*(volatile uint32_t *)0x0000C274 = 0xFFFFFFFF;` repeatedly from the GUI/kbd loop while `g3x_get_movie_status() == 1`, not just once. | INFERRED | Future milestone implementation (e.g. PORT-57) in CHDK core / kbd loop without `FULL_HOOKS`. |

---

## 2. RAM Address ROM Derivation Table

Every RAM address referenced in the evidence table is derived from bounded reads covering literal pools and base-register setup instructions in `firmware/dumps/GM1.10C/PRIMARY.BIN`. All four addresses (`0x0000C274`, `0x0000C278`, `0x0000C0E4`, `0x0000C0C0`) are fully derived and confirmed across all cited use sites, qualifying each as `ROM_VERIFIED`.

> [!NOTE]
> If any RAM address could not be derived from bounded reads, it would remain labelled `INFERRED`, and the build would be forbidden from writing it. Because each derivation below is complete and verified against literal pool words in ROM, the target addresses are verified.

| RAM address | use site | load insn @addr | pool addr -> word | base+offset | manifest read id |
|---|---|---|---|---|---|
| `0x0000C274` (`mr_max_frames`) | `0xFC098692`: `str r1, [r0, #124]` (`r0 = sl` @ `0xFC098690`) in `SetupModeAndLimits` | `0xFC098286`: `ldr.w sl, [pc, #556]` | `Align(0xFC098286+4, 4) + 0x22C = 0xFC0984B4` -> `0x0000C1F8` | `sl (0x0000C1F8) + 0x7C (124) = 0x0000C274` | `PORT56-ROM-SETUP-MAXFRAMES-BASE-LOAD`, `PORT56-ROM-POOL-SETUP-MAXFRAMES-BASE`, `PORT56-ROM-SETUP-MAX-FRAMES-STORE` |
| `0x0000C0E4` (`mr_warn_sec`) | `0xFC09869C`: `str r0, [r7, #108]` (`r0 = max_sec - 10`) in `SetupModeAndLimits` | `0xFC097DA4`: `ldr r7, [pc, #744]` | `Align(0xFC097DA4+4, 4) + 0x2E8 = 0xFC098090` -> `0x0000C078` | `r7 (0x0000C078) + 0x6C (108) = 0x0000C0E4` | `PORT56-ROM-SETUP-WARNSEC-BASE-LOAD`, `PORT56-ROM-POOL-SETUP-WARNSEC-BASE`, `PORT56-ROM-SETUP-MAX-FRAMES-STORE` |
| `0x0000C274` (`mr_max_frames`) | `0xFC098B18`: `ldr r5, [pc, #620]`; `0xFC098B20`: `ldr r1, [r5, #124]` in `CheckFrameCountLimit` | `0xFC098B18`: `ldr r5, [pc, #620]` | `Align(0xFC098B18+4, 4) + 0x26C = 0xFC098D88` -> `0x0000C278` | `r5 (0x0000C278 - 0x80 = 0x0000C1F8) + 0x7C (124) = 0x0000C274` (`subs r5, #128` @ `0xFC098B1C`) | `PORT56-ROM-CHECK-FRAME-LIMIT`, `PORT56-ROM-POOL-CHECK-LIMITS-BASES` |
| `0x0000C278` (`mr_cur_frames`) | `0xFC098B1A`: `ldr r0, [pc, #620]`; `0xFC098B1E`: `ldr r0, [r0, #0]` in `CheckFrameCountLimit` | `0xFC098B1A`: `ldr r0, [pc, #620]` | `Align(0xFC098B1A+4, 4) + 0x26C = 0xFC098D88` -> `0x0000C278` | `r0 (0x0000C278) + 0x0 (0) = 0x0000C278` | `PORT56-ROM-CHECK-FRAME-LIMIT`, `PORT56-ROM-POOL-CHECK-LIMITS-BASES` |
| `0x0000C0C0` (stop reason) | `0xFC098B28`: `str.w r1, [r8, #72]` (`r1 = 4`, reason 4) in `CheckFrameCountLimit` | `0xFC098AE4`: `ldr.w r8, [pc, #668]` | `Align(0xFC098AE4+4, 4) + 0x29C = 0xFC098D84` -> `0x0000C078` | `r8 (0x0000C078) + 0x48 (72) = 0x0000C0C0` | `PORT56-ROM-CHECK-FRAMELIMIT-BASE-LOAD`, `PORT56-ROM-CHECK-FRAME-LIMIT`, `PORT56-ROM-POOL-CHECK-LIMITS-BASES` |
| `0x0000C0C0` (stop reason) | `0xFC098C5C`: `str r0, [r7, #72]` (`r0 = 3`, reason 3) in `CheckSizeAndSpaceLimits` | `0xFC098BB4`: `ldr r7, [pc, #460]` | `Align(0xFC098BB4+4, 4) + 0x1CC = 0xFC098D84` -> `0x0000C078` | `r7 (0x0000C078) + 0x48 (72) = 0x0000C0C0` | `PORT56-ROM-CHECK-SIZELIMIT-BASE-LOAD`, `PORT56-ROM-CHECK-SIZE-LIMIT`, `PORT56-ROM-POOL-CHECK-LIMITS-BASES` |
| `0x0000C0E4` (`mr_warn_sec`) | `0xFC0992FA`: `ldr.w r0, [fp, #108]` in `ProcessEncodedFrame` | `0xFC09906C`: `ldr.w fp, [pc, #312]` | `Align(0xFC09906C+4, 4) + 0x138 = 0xFC0991A8` -> `0x0000C078` | `fp (0x0000C078) + 0x6C (108) = 0x0000C0E4` | `PORT56-ROM-WARN-SEC-BASE-LOAD`, `PORT56-ROM-POOL-WARN-SEC-BASE`, `PORT56-ROM-WARN-SEC-CHECK` |

---

## 3. Stock Limit Applicability by Video Resolution & Mode

In stock Canon firmware, recording halts on whichever limit is encountered first:

| Video Mode | Resolution & Framerate | Target Bitrate | Factory Limiting Factor | Limit Boundary | 4 GiB vs Duration: What Hits First? | Visible With Duration Unlock? |
|---|---|---|---|---|---|---|
| **FHD 60p / 50p** | 1920x1080 @ 59.94 / 50.00 fps | ~35 Mbps | 4 GiB Size Policy (Reason 3) | ~16 min 20 sec | **4 GiB hit first** (~16m 20s < 29:59) | No (stops at 4 GiB before 29:59) |
| **FHD 30p / 25p / 24p** | 1920x1080 @ 29.97 / 25.00 / 23.98 fps | ~24 Mbps | 4 GiB Size Policy (Reason 3) | ~23 min 50 sec | **4 GiB hit first** (~23m 50s < 29:59) | No (stops at 4 GiB before 29:59) |
| **HD 720p 30p / 25p** | 1280x720 @ 29.97 / 25.00 fps | ~8 Mbps (estimate) | 29:59 Duration Limit (Reason 4) | 29 min 59 sec | **Duration hit first** (~1.93 GiB at 29:59 << 4 GiB; `docs/VIDEO001_RECORDING_LIMITS.md:97`) | **YES** (bypasses 29:59; 4 GiB size stop reached later depending on real VBR bitrate; INFERRED) |
| **VGA 30p / 25p** | 640x480 @ 29.97 / 25.00 fps | ~3 Mbps | 59:59 Duration Limit (Reason 4) | 59 min 59 sec | **Duration hit first** (file is ~1.45 GiB << 4 GiB) | **YES** (reaches >60m without hitting 4 GiB) |

- **Stock Behavior on 4 GiB**: Stock GM1.10C halts recording with Reason 3 (`0xFC098C5C`); it does **not** seamlessly split or start a new file.
- **Recommended Trial Mode**: **HD 720p 30p/25p**. For HD 720p, the audio bitrate is ~192 kbps AAC (`docs/VIDEO001_RECORDING_LIMITS.md:101`). With the 8 Mbps video figure, 60 min is about 3.7 GB, below the 4 GiB stop. The video bitrate is an estimate, and the minute at which the 4 GiB stop (Reason 3, `0xFC098C5C`) is reached depends on the real bitrate. Because at 35 minutes the file size is ~2.15 GB (safely below the 4 GiB ceiling), defeating the duration limit allows a continuous recording trial (e.g. 35 minutes) to clearly prove that the 29:59 limit has been bypassed.

---

## 4. Safe Write Timing and Recommended Mechanism Without FULL_HOOKS

1. **Reinitialization Timing**: `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`) is called at `0xFC09A97C` inside Command 0 dispatch (`0xFC09A956`). It runs strictly upon recording start, unconditionally recalculating and writing `mr_max_frames` into `0x0000C274` and `mr_warn_sec` into `0x0000C0E4`. It does **not** run at idle mode switch. Note that `SetupModeAndLimits` runs on each recording start (manifest `PORT56-ROM-CMD0-SETUP-CALL`), so the value must be enforced again for every recording.
2. **Safe Write Rule & Timing**:
   - Do NOT treat `MOV:REC` as proof that setup has finished. As cited in `docs/VIDEO001_RECORDING_LIMITS.md:183`: recording state becomes 1 before the limit setup finishes.
   - **Required rule for the build**: While `MOV:REC` holds (`g3x_get_movie_status() == 1`), check `mr_max_frames` (`0x0000C274`) on every GUI/kbd loop tick and rewrite it whenever it is nonzero and not already `0xFFFFFFFF`. Never rely on a single write. Never write while not recording.
   - Status reporting: `LIM:OFF` when the patched value (`0xFFFFFFFF`) is in place while recording (limit defeated); `LIM:ON` when the stock value is seen while recording (limit active); `LIM:?` otherwise (not recording or initial 0).
   - Note that `SetupModeAndLimits` runs on each recording start (manifest `PORT56-ROM-CMD0-SETUP-CALL`), so the value must be enforced again for every recording.
   - Target: Write only `0x0000C274` (`mr_max_frames = 0xFFFFFFFF`). Do NOT write `0x0000C0E4` (UI warning only) or `0x0000C0C0` (stop reason).
   - Cap: Note that the 4 GiB size stop (reason 3, `0xFC098C5C`) stays active and is the real cap.
   - The claim that this write is safe and takes effect is **INFERRED**; runtime safety is verified in owner trial.
3. **Execution Context**: The existing non-invasive CHDK loop (`mykbd_task` / `gui_sync`) queries `g3x_get_movie_status()` (`mr_rec_state` @ `0x0000C0C8`, verified in PORT-55). Note that `is_video_recording()` (`chdk-port/core/shooting.c:1651`) is true for every non-zero state, including stopping states, so it must not gate the write. While active recording holds (`g3x_get_movie_status() == 1`), CHDK executes:
   ```c
   if (g3x_get_movie_status() == 1) { // mr_rec_state == 1 (MOV:REC)
       uint32_t val = *(volatile uint32_t *)0x0000C274;
       if (val != 0 && val != 0xFFFFFFFFU) {
           *(volatile uint32_t *)0x0000C274 = 0xFFFFFFFFU; // mr_max_frames (write only this address)
       }
   }
   ```
   - While recording, if the readback value equals `0xFFFFFFFF`, the status is `LIM:OFF` (limit defeated / off).
   - While recording, if the readback value is nonzero and not `0xFFFFFFFF`, the status is `LIM:ON` (stock limit active / on).
   - When not recording or value is 0, status is `LIM:?` and never write.
4. **Evaluation Logic**: At `0xFC098B22`, `cmp r0, r1` compares `mr_cur_frames` against `mr_max_frames`. The subsequent instruction `04 d3` is `blo 0xFC098B30` (unsigned lower). With `mr_max_frames = 0xFFFFFFFF`, `cur_frames < max_frames` is always True, permanently bypassing the Reason 4 stop sequence.

---

## 5. Evidence Manifest Summary

Bounded ROM reads recorded in `manifests/evidence/port56_evidence_manifest.json` (15 ranges, 464 bytes total):

| Range ID | Start Address | End Address | ROM Offset | Length (B) | SHA-256 | Target Function / Purpose |
|---|---|---|---|---|---|---|
| `PORT56-ROM-SETUP-WARNSEC-BASE-LOAD` | `0xFC097DA0` | `0xFC097DB0` | `0x00097DA0` | 16 | `0fd46b0cb1932d5267c2266513fe8f0e2dac93d8fa57c541731c103700a8ec03` | `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`): confirms `ldr r7, [pc, #744]` at `0xFC097DA4` targeting pool `0xFC098090`. |
| `PORT56-ROM-POOL-SETUP-WARNSEC-BASE` | `0xFC098090` | `0xFC0980A0` | `0x00098090` | 16 | `184e1814b6440be66ba0760c0445ccf21d78a15f889970cb6d9f29e9fa7e7ce6` | Literal pool at `0xFC098090`: confirms base word `0x0000C078` for `mr_warn_sec` store (`+0x6C` = `0x0000C0E4`). |
| `PORT56-ROM-SETUP-MAXFRAMES-BASE-LOAD` | `0xFC098280` | `0xFC098290` | `0x00098280` | 16 | `d5102bae0b5adc5508a064984120e191eb8d9abc04324e7482178a17b9addd55` | `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`): confirms `ldr.w sl, [pc, #556]` at `0xFC098286` targeting pool `0xFC0984B4`. |
| `PORT56-ROM-POOL-SETUP-MAXFRAMES-BASE` | `0xFC0984B0` | `0xFC0984C0` | `0x000984B0` | 16 | `43ddd0793a2dbd86b03c191b1985141c43c7db54bc2bc84ea20be77618eac60f` | Literal pool at `0xFC0984B4`: confirms base word `0x0000C1F8` for `mr_max_frames` store (`+0x7C` = `0x0000C274`). |
| `PORT56-ROM-SETUP-DURATION-LIMITS` | `0xFC098530` | `0xFC0985B0` | `0x00098530` | 128 | `37300b420dfee7fb5d914bd218054fee9b1cf3e6b63150aa1be219e4b912d533` | `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`): confirms `movw r0, #0x707` (`1799` s FHD/HD) at `0xFC09853E` and `movw r0, #0xE0F` (`3599` s VGA) at `0xFC09859A`. |
| `PORT56-ROM-SETUP-MAX-FRAMES-STORE` | `0xFC098688` | `0xFC0986B0` | `0x00098688` | 40 | `c5bd8f9f22319a041c89fac44d2a6fa3bcdec09fe49368ecbbe0c1285e806e00` | `MovieRecorder_SetupModeAndLimits` (`0xFC097D72`): confirms store of `max_frames` to `0x0000C274` at `0xFC098692` and `warn_sec` to `0x0000C0E4` at `0xFC09869C`. |
| `PORT56-ROM-CHECK-FRAMELIMIT-BASE-LOAD` | `0xFC098AE0` | `0xFC098AF0` | `0x00098AE0` | 16 | `ecbb4e9224366a90c4d66f99dd75b5440ffc788dac1e737bc5482c4eddf96c5d` | `MovieRecorder_CheckFrameCountLimit` (`0xFC098AE0`): confirms `ldr.w r8, [pc, #668]` at `0xFC098AE4` targeting pool `0xFC098D84`. |
| `PORT56-ROM-CHECK-FRAME-LIMIT` | `0xFC098B10` | `0xFC098B38` | `0x00098B10` | 40 | `3ecb33c05ba76b458c8f1f99374fe844d78db763d30086cc614d84c787d07a9a` | `MovieRecorder_CheckFrameCountLimit` (`0xFC098AE0`): confirms unsigned comparison `cmp r0, r1` at `0xFC098B22` followed by `blo 0xFC098B30`, storing stop reason `*(0x0000C0C0) = 4` at `0xFC098B28`. |
| `PORT56-ROM-CHECK-SIZELIMIT-BASE-LOAD` | `0xFC098BB0` | `0xFC098BC0` | `0x00098BB0` | 16 | `fe76c98d15a010a9ff0ae4942cdea3b5afbc6df05e70d2e37eb1f1fc280b55a3` | `MovieRecorder_CheckSizeAndSpaceLimits` (`0xFC098BAA`): confirms `ldr r7, [pc, #460]` at `0xFC098BB4` targeting pool `0xFC098D84`. |
| `PORT56-ROM-CHECK-SIZE-LIMIT` | `0xFC098C40` | `0xFC098C70` | `0x00098C40` | 48 | `2ea7dfc06e0c7804cff20565e5048b4312a53e6a269866af417a873b0e53db4e` | `MovieRecorder_CheckSizeAndSpaceLimits` (`0xFC098BAA`): confirms 64-bit comparison against 4 GiB (`segment * 0xFFFFFFFF`) at `0xFC098C46..58`, storing size stop reason `*(0x0000C0C0) = 3` at `0xFC098C5C`. |
| `PORT56-ROM-POOL-CHECK-LIMITS-BASES` | `0xFC098D80` | `0xFC098D90` | `0x00098D80` | 16 | `29f5a7657870a618761710dc8c33d03e28c39f58f19f390c7242b23ad5338e0a` | Literal pools at `0xFC098D84` (base `0x0000C078` for stop reason `0x0000C0C0`) and `0xFC098D88` (base `0x0000C278` for `mr_cur_frames` and `mr_max_frames`). |
| `PORT56-ROM-WARN-SEC-BASE-LOAD` | `0xFC099068` | `0xFC099078` | `0x00099068` | 16 | `369203e95037706c657e6dea1a40a1561fb82a83736a677fb28815cbe5b1f6bc` | `MovieRecorder_ProcessEncodedFrame` (`0xFC098E9E`): confirms `ldr.w fp, [pc, #312]` at `0xFC09906C` targeting pool `0xFC0991A8`. |
| `PORT56-ROM-POOL-WARN-SEC-BASE` | `0xFC0991A0` | `0xFC0991B0` | `0x000991A0` | 16 | `597fc12fec4f5720e51a19bae5ef43d9bd51f9533a826bd26a4c9b0741fb95a9` | Literal pool at `0xFC0991A8`: confirms base word `0x0000C078` for `mr_warn_sec` load (`+0x6C` = `0x0000C0E4`). |
| `PORT56-ROM-WARN-SEC-CHECK` | `0xFC0992F0` | `0xFC099310` | `0x000992F0` | 32 | `1f7597700d045a3e15d5d536971ce18ebc21ac9fbb2ce684a1a1b6b1b79b7597` | `MovieRecorder_ProcessEncodedFrame` (`0xFC098E9E`): confirms `warn_sec` loaded from `0x0000C0E4` at `0xFC0992FA` triggers UI warning event `0x3149` (10s warning), not recording termination. |
| `PORT56-ROM-CMD0-SETUP-CALL` | `0xFC09A968` | `0xFC09A988` | `0x0009A968` | 32 | `172905742f575ad2286fb1fd6ac6006d42edb47b07ac23581f29fac00f84094c` | `MovieRecorder_CmdStartPipeline` (`0xFC09A956`): confirms `BL 0xFC097D72` at `0xFC09A97C` executes during Command 0 dispatch upon recording start, proving setup runs on every recording start. |

---

## 6. Candidate Build Configurations & Artifacts

All three configurations built deterministically with pinned toolchain (`toolchains/gcc-arm-none-eabi-5_4-2016q3`):

| Configuration | Flags | Output DISKBOOT.BIN | Size (B) | SHA-256 | `_end` | Diag Marker | Status |
|---|---|---|---|---|---|---|---|
| **(a) Default** | None (stock flags) | `out/build-default/DISKBOOT.BIN` | 124,097 | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | `0x003686b0` | `LIM:?` | Byte-identical to baseline default |
| **(b) Nolimit alone** | `G3X_MOVIE_STATUS=1` `G3X_MOVIE_NOLIMIT=1` | `out/build-nolimit-alone/DISKBOOT.BIN` | 124,145 | `12c0635ffd11d2c6a1d158aaac436885a4a3b9b7830841a8c65410c193439b33` | `0x003686e0` | `LIM:OFF` / `LIM:ON` / `LIM:?` | Single-feature opt-in candidate |
| **(c) Full combination** | `G3X_GUI_FIX=1` `G3X_GUI_DBUF=1` `G3X_GUI_NOOVERDRAW=1` `G3X_KBD_CHECK=1` `G3X_GUI_DIAG=1` `G3X_GUI_SHADOW2=1` `G3X_GUI_SYNC=1` `G3X_GUI_MENU=1` `G3X_GUI_RESTORE2=1` `G3X_PLAYBACK_MENU=1` `G3X_MOVIE_STATUS=1` `G3X_MOVIE_NOLIMIT=1` | `out/port56-movie-nolimit/DISKBOOT.BIN` | 132,385 | `c8709189c4508fd96f89aebed58641fbbc1e60b258699be642686e6387c58352` | `0x0036aaf0` | `LIM:OFF` / `LIM:ON` / `LIM:?` | Full interactive candidate without FULL_HOOKS |

