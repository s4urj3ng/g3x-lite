# PORT-32: Owner Trial Plan — Opt-In `G3X_RESIDENT=1` Heartbeat Candidate (GM1.10C)

**Target**: Canon PowerShot G3 X (`GM1.10C`, Platform ID `0x32A8`). Phase 0 safety rules apply (`docs/SAFETY.md`): agents build on the host only; the owner runs the hardware trial by hand. No classifier or decoder is used for this trial.

## 1. Candidate Build & Artifact Pin (`docs/PORT32_RESIDENT_CANDIDATE.md` §1)

| Field | Value |
|:---|:---|
| **Pinned Toolchain** | `toolchains/gcc-arm-none-eabi-5_4-2016q3` (`arm-none-eabi-gcc` 5.4.1 20160919) |
| **Build Command** | `G3X_RESIDENT=1 python3 -B tools/build_candidate_port25_ladder_fix.py --resident --out-dir <dir>` |
| **Candidate `DISKBOOT.BIN` SHA-256** | `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` |
| **Candidate Sizes & Bounds** | `DISKBOOT.BIN`: `124,561` B; loaded `candidate_main.bin`: `123,120` B; linked `_end`: `0x00368550` $\le$ heap start `0x00368680` (`304` B clearance) |
| **Expected Heartbeat Pattern** | Rear green LED (`0xD20B0884`) double short blink at **~1.0 Hz**: `100 ms ON -> 100 ms OFF -> 100 ms ON -> 700 ms OFF` (`1,000 ms` period) |

## 2. Held-Press Boot Procedure (At Most 2 Power-Ons)

- **Card Prep & Hard Gate**: Copy `DISKBOOT.BIN` to the root (`A/DISKBOOT.BIN`) of the FAT32 `BOOTDISK` SD card (`0x1E0` marker). Verify `sha256sum <card>/DISKBOOT.BIN` equals `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` (STOP if mismatch). Unmount and slide the card write-protect tab to **LOCKED**.
- **Power-On 1 (Primary Held-Press Boot)**: Insert a charged NB-10L battery and the LOCKED card. Press and **keep the Power button held down continuously** while the PORT-25 ladder plays (`1..7` single loader blinks, then two-digit core frames `11..15`, `21..26`, `31..35`, `41..44`). Keep the button held until the PORT-25 ladder finishes (`Code 44`) and the stock UI appears (or LED activity stops for $\ge 10\text{ s}$), then release and observe the rear green LED and LCD for 30–60 s. *(Short-press boot is out of scope and shuts down at `Code 43`.)*
- **Power-On 2 (Optional Repeat, Max 2 Total)**: Run a second held-press power-on **only** if Power-On 1 had an early button release or if confirming repeatability after a clean shutdown/recovery. Never exceed **2 power-ons** with the candidate installed.

## 3. Observation Table Mapped to `docs/PORT32_RESIDENT_CANDIDATE.md` §2 Assumptions

| Trial Outcome | Observed LED & Camera Behaviour | Meaning for `docs/PORT32_RESIDENT_CANDIDATE.md` §2 Assumptions Table Rows |
|:---|:---|:---|
| **1. Early stop at ladder code `N`** | Ladder stops at loader pulse `1..7` or core code `N` (`11..43`); `Code 44` and heartbeat are never reached. | - **`N < 13`**: Pre-heap early boot stopped; all resident assumptions remain **untested (`UNKNOWN`)**.<br>- **`N = 13` or `14`**: **Refutes/implicates** **Row 11 (Raised heap start `0x00368680`, `_end = 0x00368550`)** during `sub_fc05b3c8_my` / `sub_fc31b408` init.<br>- **`N = 43`**: Indicates accidental button release before `Code 44` (known short-press cutoff). Post-`Code 44` `CreateTask` rows (`1–10`, `12–13`) are **not reached**. |
| **2. Ladder completes (`Code 44`), no heartbeat** | Full ladder `1..7` and `11..44` finishes; no double-blink heartbeat appears on `0xD20B0884` (stock UI either boots or fails). | - **Confirms**: **Row 11 (Raised heap start `0x00368680` in early boot)**.<br>- **Refutes/implicates**: Post-`Code 44` spawn/handoff if crash before UI (**Row 1 `CreateTask` `0xBFE14A3D`**, **Row 2 `r0` `"Heartbeat"`**, **Row 3 `r1` priority check**, **Row 4 `r2` byte count / allocator `0xBFE1452E`**, **Row 13 `sub_fc0d0126` handoff**); or task dispatch/sleep/LED if stock UI runs without blinking (**Row 5 stack alignment**, **Row 6 `r3` entry dispatch**, **Row 7 `sp[0] = 0` delivery**, **Row 9 priority `0x19` starvation**, **Row 10 `SleepTask` `0xFC31BF84` stall**, **Row 12 `0xD20B0884` post-handoff GPIO override**). |
| **3. Heartbeat present** | Ladder `1..7`, `11..44` finishes; stock UI runs and rear green LED repeats the double-short-blink heartbeat continuously. | - **Confirms resident task & `CreateTask` calling convention**: **Row 1 (`CreateTask` `0xBFE14A3D` `FINSIG`)**, **Row 2 (`r0` `"Heartbeat"`)**, **Row 3 (`r1 = 0x19` priority)**, **Row 4 (`r2` byte count & `0xBFE1452E` stack alloc)**, **Row 5 (8-byte entry stack alignment)**, **Row 6 (`r3 = task \| 1` entry call)**, **Row 7 (`sp[0] = 0` safe)**, **Row 8 (`0x2000` stack headroom)**, **Row 9 (priority `0x19 = 25` coexists with stock UI)**, **Row 11 (raised heap `0x00368680` protects `0x003489B4..0x00368550`)**, **Row 12 (`0xD20B0884` MMIO active post-handoff)**, and **Row 13 (`sub_fc0d0126` handoff with `r0-r3`/`sp` preserved)**.<br>- **Row 10 (`SleepTask` `0xFC31BF84` & `ms` unit)**: ~1.0 Hz rate **confirms** `ms` delay unit; ~0.1 Hz or ~10 Hz **confirms** `SleepTask` yield but **refutes** `1 tick = 1 ms` in `0xFCEF3A60`. |
| **4. Heartbeat followed by freeze or shutdown** | Double-blink heartbeat appears after `Code 44` for one or more cycles, then LED/UI freezes or camera shuts down. | - **Confirms**: Initial spawn, `CreateTask` convention, and handoff (**Rows 1, 2, 3, 6, 12, 13**).<br>- **Refutes/implicates**: Runtime coexistence/survival: **Row 11 (non-heap DMA / live-view buffer overwriting resident RAM `0x003489B4..0x00368680`)**, **Row 4 & Row 8 (`0x2000` stack overflow or `0xBFE1452E` pool corruption under IRQ/preemption)**, **Row 5 (alignment fault on later context switch)**, **Row 9 (priority `0x19` watchdog timeout)**, or **Row 10 (`SleepTask` wakeup fault)**. |

## 4. Recovery Procedure (Battery Pull -> Normal Boot Without Candidate)

1. **Battery Pull**: If the camera freezes, shuts down abnormally, or finishes the trial, immediately open the battery door, **pull the NB-10L battery**, eject the SD card, and wait **30 seconds** for capacitor discharge.
2. **Remove Candidate**: Slide the SD card write-protect tab to **UNLOCKED** (or remove the SD card / delete `A/DISKBOOT.BIN`).
3. **Normal Stock Boot**: Reinsert the battery, close the door, and power on normally **without the candidate** to verify clean stock GM1.10C UI operation, then power off via the Power button.

## 5. What to Write in the Owner Report Note

Record a short plain-text note with these four items (plus confirmed card `DISKBOOT.BIN` SHA-256 and power-on count `1` or `2`):
- **Last ladder code seen**: Last loader blink (`1..7`) or two-digit core code (`11..44`) observed (e.g. `Code 44 completed`).
- **Whether a heartbeat appeared**: `yes` (continuous), `yes, then stopped after N blinks / T seconds`, or `no` (dark / solid ON).
- **Approximate heartbeat rate**: Observed period or frequency of the double-blink cycle (e.g. `~1 Hz` / `~1 s per double blink`, or other rate).
- **Stock UI state**: Rear LCD and camera behaviour (`stock UI normal and responsive`, `LCD dark/off`, `backlight only`, or `froze/shut down after T seconds`, plus clean post-recovery stock boot confirmation).
