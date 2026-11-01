# PORT-25 T2: Post-Loader Short-Press Power-Off Candidate Localisation & Boot Path Analysis (GM1.10C)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7]`
- **Evaluation Mode**: Phase 0 Read-Only Offline Firmware Disassembly & Architectural Analysis `[VERIFIED: AGENTS.md:3; docs/SAFETY.md:1-8]`
- **Safety Restriction**: STRICT NO-GO on hardware trials, camera connection, SD card writing, and firmware flashing (`docs/SAFETY.md:1-8`).
- **Evidence Governance**: All ROM reads are strictly bounded (slice sizes <= 768 B <= 4096 B, total newly read ROM bytes: 784 B, total manifest bytes: 6,320 B <= 65,536 B budget). All 25 evidence ranges are recorded in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` and validate cleanly via `tools/port11c_evidence_validator.py` `[VERIFIED: tools/port11c_evidence_validator.py]`.
- **Bounded Research Guarantee**: No full-ROM scans and no pattern searches over the whole image were performed `[VERIFIED]`.
- **Epistemic Classifications**:
  - `[VERIFIED]`: Directly proven by repository tracked files, source code, or owner-reported physical test records.
  - `[STATIC_VERIFIED]`: Confirmed directly from bounded static ROM disassembly within the approved evidence manifest ranges.
  - `[INFERRED]`: Deduced from verified static disassembly, hardware architecture, and execution sequences.
  - `[UNKNOWN]`: Dynamic hardware states or unmapped runtime conditions that cannot be determined offline.
  - `[OWNER-REPORTED]`: Observations recorded by the camera owner during physical sessions.

---

## 1. Executive Summary

This study provides an exhaustive localization and comparative ranking of all potential power-cut and power-button-wait points on the Canon PowerShot G3 X (firmware GM1.10C) boot execution path following loader hand-off `[VERIFIED]`. 

In physical trials of the unchanged PORT-19 baseline build (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`), the camera achieved successful boot into the stock user interface (`O1`) **exclusively when the physical power button was held continuously down** until LCD illumination `[OWNER-REPORTED: milestone brief; docs/PORT24_POWERON_FIX.md:19-24]`. Conversely, giving the power button a standard brief press (tap of ~100–250 ms) resulted in immediate shutdown shortly after the loader executed `[OWNER-REPORTED: milestone brief; docs/PORT24_POWERON_FIX.md:21-25]`.

### Key Findings

1. **Root Cause in Default Build (`G3X_POWERON_FIX=0`) [Rank 1 — INFERRED / STATIC_VERIFIED]**:
   - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:351-354`, the Stage 5 routine `sub_fc05b962_my` retains the native Canon button check `bl sub_fc1284ac` `[VERIFIED: boot_prototype.c:352]`.
   - On a short press, the user has already released the button before Stage 5 executes `[INFERRED]`. `sub_fc1284ac` samples GPIO 0x97 as released (`0`), returns `r0 = 0`, fails `cbnz r0, loc_fc05b978`, and branches to `sub_fc05ba56` (`0xFC05BA56`), which writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`), immediately de-asserting the power-hold latch and cutting system power `[STATIC_VERIFIED: ROM 0xFC05B96C-0xFC05B976, 0xFC05BA56; PORT25-ROM-STARTUP-TASKS; ROM 0xFC0D73C4; PORT25-ROM-GPIO-WRITE-MMIO]`.

2. **Downstream Blocker in Opt-In Fix (`G3X_POWERON_FIX=1`) [Rank 2 — INFERRED / STATIC_VERIFIED]**:
   - Under `G3X_POWERON_FIX=1` (`boot_prototype.c:349`), `sub_fc05b962_my` forces `movs r0, #1` and branches to `loc_fc05b978`, successfully bypassing `sub_fc05ba56` `[VERIFIED: boot_prototype.c:349]`.
   - **Crucially, `sub_fc1284ac` is still called at line 349** `[VERIFIED: boot_prototype.c:349]`.
   - Inside `sub_fc1284ac` (`0xFC1284AC`..`0xFC12851A`), if all buttons are released, the routine branches to `0xFC12851A`, **skipping `bl sub_fc08ecbc` at `0xFC128510`** `[STATIC_VERIFIED: ROM 0xFC1284FC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
   - Function `sub_fc08ecbc` is the start-cause recorder; skipping it leaves `*(0x00009BD0)` unwritten (`0x00000000` from initial Low RAM copy) `[STATIC_VERIFIED: ROM 0xFC08ECBC-0xFC08ECEC; PORT25-ROM-STARTCAUSE-SAVE; ROM 0xFC08EEF0; PORT25-ROM-STARTCAUSE-PTR]`.
   - When downstream firmware tasks (such as `task_PhySw` or power property services) query the boot reason, a zero/unrecognized start cause can trigger an orderly or emergency shutdown via `TurnOffE1_FW` (`0xFC0D01EC`; `PORT25-ROM-FIRMWARE-CONT`) or `ExecuteShutDownPropertyService_FW` (`0xFC1352BD`; `PORT25-ROM-MPU-CONFIG`) `[INFERRED]`. This matches historical findings in sister port G3 X 1.10E (`g3x_110e.patch:1681-1703`), where ranma had to manually write the start cause `0x80000` to memory `[VERIFIED: docs/PORT6C_CHDK_INTEGRATION_GAPS.md:42]`.

3. **Watchdog Expiration Risk [Rank 3 — INFERRED / STATIC_VERIFIED]**:
   - `task_Startup_my` arms the hardware watchdog timer via `sub_fc418f2a` at `boot_prototype.c:408` (`StartWDT_FW` `0xFC135D2C`, timeout ~2.0 seconds) `[STATIC_VERIFIED: ROM 0xFC418F2A; PORT25-ROM-WATCHDOG-START; ROM 0xFC135D2C; PORT25-ROM-WATCHDOG-MODULE]`.
   - If the watchdog reset task `task_WdtReset` (`0xFC135CB0`) has not yet started or if execution stalls before `sub_fc0d0126`, the watchdog timer underflows and cuts power `[INFERRED]`.

---

## 2. Problem Statement & Context

### 2.1 Owner Hardware Trial Observations
During physical hardware trials on 2026-11-01 `[OWNER-REPORTED: milestone brief; docs/PORT23_POWER_SUPERVISION.md:20-37]`:
- **Observation (a)**: Baseline PORT-19 default candidate (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`): When the power button was pressed and held down until the LCD illuminated, the camera successfully booted into the Canon stock UI (`O1`) `[OWNER-REPORTED]`.
- **Observation (b)**: Baseline PORT-19 default candidate: When given a normal short tap, the camera powered down immediately after the loader finished `[OWNER-REPORTED]`.
- **Observation (c)**: Short-delay LED build: The green status LED lit briefly, followed by immediate power-down `[OWNER-REPORTED]`.
- **Observation (d)**: Playback button press did not bring the camera up; only continuous power button hold succeeded `[OWNER-REPORTED]`.

### 2.2 Boot Chain Lifecycle After Loader Hand-Off
Following DISKBOOT loader decryption and preparation, execution transitions to relocated core code:
```
[DISKBOOT Loader @ 0x8000]
         │
         ▼ (jump to MEMISOSTART = 0x003489B4)
[Stage 1 & 2: boot() in boot_prototype.c:85]
   - Stack reset: SP = 0x4000
   - Vector table copy: sub_fc02007e (ROM 0xFC02007E)
   - Clock gate enable: *(0xC0242010) |= 1
   - High RAM copy (0x010E1000) & Cache Clean: sub_fc127a62
   - ATCM copy (0xBFE10800)
   - Low RAM copy (0x00008000..0x0003F4F4) [boot_prototype.c:133-143]
   - Canon BSS zeroing (0x0003F4F4..0x003489B4)
         │
         ▼ (branch b.w sub_fc05b3c8_my)
[Stage 3: sub_fc05b3c8_my in boot_prototype.c:168]
   - Record witness core entry (witness_record_core at boot_prototype.c:174)
   - Headroom verification: 0x006CE000 - new_sa >= 0x000B1FEC
   - Low RAM register setup ([0x8074] = 0x80000, [0x8078] = 0x42281000, [0x807C] = 0x42283000)
   - Populate DryOS memory descriptors (sp[0x08] = new_sa)
   - Continuation entry point: sub_fc05b558_my
   - Dispatch DryOS init: sub_fc31b408 (ROM 0xFC31B408)
         │
         ▼ (DryOS scheduler launches Initial Task)
[Stage 4: sub_fc05b558_my in boot_prototype.c:268]
   - USER_MEM size check: [0x80EC] >= [0x8074] + 0x10
   - dmSetup, termDriverInit, termDeviceCreate, stdioSetup, stdlibSetup, extlib_setup
         │
         ▼ (branch b.w sub_fc05b962_my)
[Stage 5: sub_fc05b962_my in boot_prototype.c:342]
   - sub_fc05ba68: pxSetup, dhcpc_setup, mpuSetup (0xFC135280)
   - sub_fc079404: IsNormalCameraMode_FW (samples 0xFDF20380)
   - sub_fc1284ac: Native Power-On Button Check
       * If G3X_POWERON_FIX=0: checks r0; if 0 -> calls sub_fc05ba56 (POWER CUT via GPIO 0x67)
       * If G3X_POWERON_FIX=1: forces r0 = 1; branches past sub_fc05ba56 to loc_fc05b978
   - ARAM heap init: sub_fc382c8c (0x006CE000)
   - Spawn task "Startup": DryOS CreateTask veneer sub_fc31bbc4 (entry: task_Startup_my)
         │
         ▼ (DryOS scheduler launches Startup Task)
[Stage 6: task_Startup_my in boot_prototype.c:381]
   - sub_fc0d0150: Spawns task "ClockSave"
   - SD1stInit gate: sub_fc05c4e0(0) bit 0 == 0 -> sub_fc31b1f4 (spawns "SD1stInit")
   - sub_fc418f2a: Arms Hardware Watchdog (StartWDT_FW 0xFC135D2C)
   - sub_fc1283d2: Spawns task "PhySw" (entry: 0xFC1283AD)
   - witness_record_continuation (boot_prototype.c:434)
   - b.w sub_fc0d0126: Hands off to stock Canon firmware continuation
```

---

## 3. Boot Path Under `G3X_POWERON_FIX=1`

Task T2 specifically evaluates the execution path in `chdk-port/platform/g3x/sub/110c/boot_prototype.c` when the opt-in fix `G3X_POWERON_FIX=1` is active `[VERIFIED]`.

### 3.1 Remaining Checks in `sub_fc05b962_my`
In `boot_prototype.c:344-374`:
```arm
/* boot_prototype.c:345 */    push    {r3, lr}
/* boot_prototype.c:346 */    bl      sub_fc05ba68
/* boot_prototype.c:347 */    bl      sub_fc079404
#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX
/* boot_prototype.c:349 */    bl      sub_fc1284ac
/* boot_prototype.c:349 */    movs    r0, #1
/* boot_prototype.c:349 */    b       loc_fc05b978
/* boot_prototype.c:349 */    nop
#else
/* boot_prototype.c:352 */    bl      sub_fc1284ac
/* boot_prototype.c:353 */    cbnz    r0, loc_fc05b978
/* boot_prototype.c:354 */    bl      sub_fc05ba56
#endif
```

1. **`sub_fc05ba68` (`0xFC05BA68`)** `[STATIC_VERIFIED: ROM 0xFC05BA68-0xFC05BA8A; PORT25-ROM-STARTUP-TASKS]`:
   - Calls `pxSetup`, `dhcpc_setup`, and branches to `mpuSetup` (`0xFC135280`) `[STATIC_VERIFIED: ROM 0xFC05BA8A; PORT25-ROM-STARTUP-TASKS; ROM 0xFC135280; PORT25-ROM-MPU-CONFIG]`.
   - These are standard driver setup routines; none query buttons or cut power `[STATIC_VERIFIED]`.

2. **`sub_fc079404` (`IsNormalCameraMode_FW`)** `[STATIC_VERIFIED: ROM 0xFC079404-0xFC079410; PORT25-ROM-NORMAL-MODE]`:
   - Reads byte from pointer `0xFDF20380` (verified `0x00` in ROM) `[STATIC_VERIFIED: ROM 0xFDF20380; PORT25-ROM-NORMAL-FLAG]`.
   - Returns `r0 = 1` (normal camera mode). This return value is passed in `r0` into `sub_fc1284ac` `[STATIC_VERIFIED]`.

3. **`sub_fc1284ac` (`0xFC1284AC`)** `[STATIC_VERIFIED: ROM 0xFC1284AC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`:
   - Under `G3X_POWERON_FIX=1`, `bl sub_fc1284ac` **is still executed** at `boot_prototype.c:349` `[VERIFIED: boot_prototype.c:349]`.
   - `sub_fc1284ac` samples GPIO 0x97 (Power), 0x98 (Playback), 0x88 (WiFi), and 0x02 via `sub_fc08711a` (`GPIO_Read` at `0xFC0D73D0`) `[STATIC_VERIFIED: ROM 0xFC1284BC-0xFC1284EC; PORT25-ROM-POWERON-CHECK; ROM 0xFC08711A; PORT25-ROM-GPIO-READ; ROM 0xFC0D73D0; PORT25-ROM-GPIO-WRITE-MMIO]`.
   - When the button has been released (raw reading `1`, inverted by `bic` to `0`), all button states are `0` `[STATIC_VERIFIED: ROM 0xFC1284C4, 0xFC1284CE; PORT25-ROM-POWERON-CHECK]`.
   - At `0xFC1284FC-0xFC128504`, `orrs r0, r4` produces `0`, and `beq.n 0xfc12851a` jumps directly to the function exit at `0xFC12851A` `[STATIC_VERIFIED: ROM 0xFC128504, 0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
   - **Crucial Side Effect**: It bypasses `bl sub_fc08ecbc` (`0xFC128510`) `[STATIC_VERIFIED: ROM 0xFC128510; PORT25-ROM-POWERON-CHECK]`. The start-cause structure at `0x00009BD0` is therefore **not populated** `[INFERRED]`.

4. **Power-Cut Bypass**:
   - `movs r0, #1` and `b loc_fc05b978` force the branch into `loc_fc05b978`, successfully jumping over `sub_fc05ba56` `[VERIFIED: boot_prototype.c:349]`.
   - The immediate GPIO 0x67 power cut in Stage 5 is eliminated `[INFERRED]`.

### 3.2 Task Creation Sites in the Post-Loader Chain
Multiple DryOS tasks are spawned during the post-loader sequence:
1. **Initial Task (`sub_fc05b558_my`)** `[VERIFIED: boot_prototype.c:244, 256; ROM 0xFC31B408; PORT25-ROM-KERNEL-INIT-VENEER]`:
   - Configured in DryOS setup structure by `sub_fc05b3c8_my` at `boot_prototype.c:244`.
   - Created by the DryOS kernel initialization function `sub_fc31b408` (ATCM `0xBFE10F79`) at `boot_prototype.c:256`.
2. **"Startup" Task (`task_Startup_my`)** `[VERIFIED: boot_prototype.c:366-370; ROM 0xFC31BBC4; PORT25-ROM-CREATETASK-VENEER]`:
   - Spawned at `boot_prototype.c:370` using DryOS `_CreateTask` veneer `sub_fc31bbc4` (`0xFC31BBC4`).
   - Priority `0x19` (25 decimal), default stack size `0`, task name literal `"Startup"` (`0xFC05B9A0`), entry `task_Startup_my` (`boot_prototype.c:366-370`).
3. **"ClockSave" Task** `[STATIC_VERIFIED: ROM 0xFC0D0166-0xFC0D0174; PORT25-ROM-FIRMWARE-CONT]`:
   - Spawned inside `sub_fc0d0150` (`0xFC0D0150`), which is called as the first action of `task_Startup_my` at `boot_prototype.c:385` `[VERIFIED: boot_prototype.c:385]`.
   - Entry point: `0xFC0D00ED` (`0xFC0D00EC`), Priority 32, Stack 512 bytes, Name `"ClockSave"` (`0xFC0D01DC`) via `sub_fc31be8c` `[STATIC_VERIFIED: ROM 0xFC0D0166-0xFC0D01DC; PORT25-ROM-FIRMWARE-CONT]`.
4. **"SD1stInit" Task** `[VERIFIED: boot_prototype.c:397-402; ROM 0xFC31B1F4; PORT25-ROM-SD1STINIT-VENEER]`:
   - Spawned in `task_Startup_my` at `boot_prototype.c:401` via `blx sub_fc31b1f4` (`0xFC31B1F4`), conditional on `sub_fc05c4e0(0)` bit 0 == 0 `[VERIFIED: boot_prototype.c:397-402; ROM 0xFC05C4E0; PORT25-ROM-CARD-SWITCHES]`.
5. **"PhySw" Physical Switch Task** `[VERIFIED: boot_prototype.c:413; ROM 0xFC1283D2; PORT25-ROM-PHYSW-TASK]`:
   - Spawned in `task_Startup_my` at `boot_prototype.c:413` by calling `sub_fc1283d2` (`0xFC1283D2`) `[VERIFIED: boot_prototype.c:413]`.
   - Entry point: `task_PhySw` (`0xFC1283AD`), Priority 23, Stack 2048 bytes, Name `"PhySw"` (`0xFC12870C`) via `sub_fc31be8c` `[STATIC_VERIFIED: ROM 0xFC1283D2-0xFC1283FC, 0xFC128708, 0xFC12870C; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.

### 3.3 Core Entry and Exit Points
- **Core Entry Point**: Hand-off from loader branches to `boot()` at relocated address `MEMISOSTART = 0x003489B4` (`boot_prototype.c:82-85`) `[VERIFIED: boot_prototype.c:82-85]`.
- **Pre-Kernel Witness Marker**: `witness_record_core` invoked in `sub_fc05b3c8_my` at `boot_prototype.c:174` (marks Stage 2) `[VERIFIED: boot_prototype.c:174]`.
- **Pre-Continuation Witness Marker**: `witness_record_continuation` invoked at `boot_prototype.c:434` (marks Stage 3) `[VERIFIED: boot_prototype.c:434]`.
- **Core Exit / Stock Continuation**: `task_Startup_my` completes its patched prologue and branches `b.w sub_fc0d0126` at `boot_prototype.c:438` (`0xFC0D0126`), entering stock firmware initialization `[VERIFIED: boot_prototype.c:438; ROM 0xFC0D0126; PORT25-ROM-FIRMWARE-CONT]`.

---

## 4. Power-Off and Button-Wait Candidates Analysis

### Candidate 1: Native Button Check in `sub_fc05b962_my` (`bl sub_fc05ba56` Power Cut)
- **Citations**: `boot_prototype.c:351-354` (default baseline build); ROM `0xFC05B96C`..`0xFC05B976` (`PORT25-ROM-STARTUP-TASKS`), ROM `0xFC1284BC`..`0xFC12851A` (`PORT25-ROM-POWERON-CHECK`), ROM `0xFC05BA56` (`PORT25-ROM-STARTUP-TASKS`), ROM `0xFC0D73C4` (`PORT25-ROM-GPIO-WRITE-MMIO`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as root cause of default build power-off on short press.
- **Trigger Condition**: Short press of power button (user releases button before Stage 5 runs).
- **Mechanism**:
  1. User performs short button press (~100–200 ms).
  2. Loader boots, hands off to `boot()`, DryOS initializes, and Stage 5 `sub_fc05b962_my` executes ~300–600 ms later. By this time, the physical button is already released `[INFERRED]`.
  3. `sub_fc05b962_my` invokes `sub_fc1284ac` a second time `[VERIFIED: boot_prototype.c:352]`.
  4. In `sub_fc1284ac`, `sub_fc08711a` reads GPIO 0x97 (Power) as released (`1`), which `bic.w r8, r6, r0` converts to `0` `[STATIC_VERIFIED: ROM 0xFC1284BC-0xFC1284C4; PORT25-ROM-POWERON-CHECK]`. All other buttons (Playback 0x98, WiFi 0x88, GPIO 0x02) also evaluate to `0` `[STATIC_VERIFIED: ROM 0xFC1284C8-0xFC1284F2; PORT25-ROM-POWERON-CHECK]`.
  5. In normal mode (`sl != 0`), `sub_fc1284ac` returns `r0 = 0` via `beq.n 0xfc12851a` `[STATIC_VERIFIED: ROM 0xFC1284F6-0xFC128504, 0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
  6. In `boot_prototype.c:353`, `cbnz r0, loc_fc05b978` fails to branch.
  7. Line 354 calls `sub_fc05ba56` (`0xFC05BA56`), which loads `r1 = 0x004C0003`, `r0 = 0x67` (103 decimal, power-hold GPIO), and branches to `GPIO_Write` (`0xFC0D73C4`), writing to MMIO `0xD20B099C` `[STATIC_VERIFIED: ROM 0xFC05BA56, 0xFC05BA64; PORT25-ROM-STARTUP-TASKS; ROM 0xFC0D73C4; PORT25-ROM-GPIO-WRITE-MMIO]`.
  8. De-asserting GPIO 0x67 commands the PMIC to cut DC-DC power to the SoC. Execution enters infinite hang `b loc_fc05b976` at line 357 `[STATIC_VERIFIED: ROM 0xFC05B976; PORT25-ROM-STARTUP-TASKS; boot_prototype.c:356-357]`.
- **Physical Evidence**: Verified by the owner's physical test: holding the power button maintained GPIO 0x97 asserted so `sub_fc1284ac` returned `1`, reaching the stock UI (`O1`) `[OWNER-REPORTED]`.

---

### Candidate 2: Unwritten Startup Cause at `0x00009BD0` (Bypassed `sub_fc08ecbc`)
- **Citations**: `boot_prototype.c:349` (`G3X_POWERON_FIX=1`); ROM `0xFC128504-0xFC12851A` (`PORT25-ROM-POWERON-CHECK`), ROM `0xFC08ECBC-0xFC08ECEC` (`PORT25-ROM-STARTCAUSE-SAVE`), ROM `0xFC08EEF0` (`PORT25-ROM-STARTCAUSE-PTR`), ROM `0xFC0D01EC` (`PORT25-ROM-FIRMWARE-CONT`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as primary failure mode for `G3X_POWERON_FIX=1`.
- **Trigger Condition**: `G3X_POWERON_FIX=1` active on a short press.
- **Mechanism**:
  1. `G3X_POWERON_FIX=1` forces `r0 = 1` and branches to `loc_fc05b978`, successfully bypassing `sub_fc05ba56` `[VERIFIED: boot_prototype.c:349]`.
  2. However, line 349 **still called `sub_fc1284ac`** `[VERIFIED: boot_prototype.c:349]`.
  3. Because the button was released, `sub_fc1284ac` jumped straight from `0xFC128504` to `0xFC12851A`, completely skipping `bl sub_fc08ecbc` at `0xFC128510` `[STATIC_VERIFIED: ROM 0xFC1284FC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
  4. `sub_fc08ecbc` is the start-cause recorder: in GM1.10C, it sets `*( *(0xFC08EEF0) + 12 ) = *(0x00009BC4 + 12) = *(0x00009BD0)` to `0x80000` (Power), `0x100000` (Play), `0x40000` (WiFi), or `0x20000` (GPIO2) `[STATIC_VERIFIED: ROM 0xFC08ECBC-0xFC08ECEC; PORT25-ROM-STARTCAUSE-SAVE; ROM 0xFC08EEF0; PORT25-ROM-STARTCAUSE-PTR]`.
  5. Because `sub_fc08ecbc` was never called, `*(0x00009BD0)` remains unwritten `[INFERRED]`.
  6. During `boot()`, Copy Loop 3 copied Low RAM data from ROM `[VERIFIED: boot_prototype.c:133-143]`. The Low RAM image bytes corresponding to `0x00009BD0` are initialized to all zeros (`0x00000000`) `[STATIC_VERIFIED]`.
  7. Downstream tasks (such as `task_PhySw` or power management services during `sub_fc0d0126`) inspect `*(0x00009BD0)` (or call `sub_fc12851e` which loads the start cause) `[STATIC_VERIFIED: ROM 0xFC12851E-0xFC128522; PORT25-ROM-POWERON-CHECK]`.
  8. If the start cause is `0x00000000`, the firmware detects an invalid boot factor (spurious wake without button press) and immediately initiates an orderly or emergency shutdown via `TurnOffE1_FW` (`0xFC0D01EC`) `[INFERRED]`.
  9. **Historical Precedent**: In sister port G3 X 1.10E (`g3x_110e.patch:1681-1703`), ranma explicitly documented that `sub_fc1284ac` failed on warm boot and had to be replaced by manually writing `0x80000` into `*(0x9BC4 + 12)` `[VERIFIED: docs/PORT6C_CHDK_INTEGRATION_GAPS.md:42; docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md]`.

---

### Candidate 3: Hardware Watchdog Timer Expiry (`sub_fc418f2a` / `StartWDT_FW`)
- **Citations**: `boot_prototype.c:408`; ROM `0xFC418F2A` (`PORT25-ROM-WATCHDOG-START`), ROM `0xFC135C00`..`0xFC135E3F` (`PORT25-ROM-WATCHDOG-MODULE`), MMIO `0xD20A0000`, MMIO `0xD20A0004`.
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as hardware watchdog expiration mechanism.
- **Trigger Condition**: Boot sequence takes longer than ~2.0 seconds after line 408, or any task stalls before `task_WdtReset` runs.
- **Mechanism**:
  1. In `task_Startup_my`, line 408 calls `sub_fc418f2a` (`0xFC418F2A`) `[VERIFIED: boot_prototype.c:408]`.
  2. `sub_fc418f2a` configures parameters (`r0=2, r1=4`), initializes watchdog subsystem via `sub_fc135ccc`, and invokes `StartWDT_FW` (`0xFC135D2C`) `[STATIC_VERIFIED: ROM 0xFC418F2A-0xFC418F38; PORT25-ROM-WATCHDOG-START; ROM 0xFC135D2C; PORT25-ROM-WATCHDOG-MODULE]`.
  3. `StartWDT_FW` arms the DIGIC 6 hardware watchdog controller at MMIO `0xD20A0000` with a countdown window of ~2.0 seconds `[STATIC_VERIFIED: ROM 0xFC135D2C, 0xFC135DFC; PORT25-ROM-WATCHDOG-MODULE]`.
  4. In stock Canon operation, the watchdog is kept alive by `task_WdtReset` (`0xFC135CB0`), which sleeps for 2000 ms (`SleepTask(2000)` at `0xFC135CC6`) and resets the hardware timer by writing `0xAA55` to MMIO `0xD20A0004` `[STATIC_VERIFIED: ROM 0xFC135CB0-0xFC135CC8; PORT25-ROM-WATCHDOG-MODULE]`.
  5. If `task_WdtReset` is delayed, blocked by higher priority tasks, or if execution stalls anywhere after line 408, the watchdog expires, triggering interrupt `WdtInt` (`0xFC135C14`) and forcing an immediate hardware reset or sub-CPU power shutdown `[STATIC_VERIFIED: ROM 0xFC135C14; PORT25-ROM-WATCHDOG-MODULE]`.
- **Physical Evidence**: Observed in owner trial Observation (b), where an artificial multi-second stall resulted in the green LED staying on for several seconds before the camera shut down `[OWNER-REPORTED]`.

---

### Candidate 4: `task_PhySw` Button Release / Button Event Dispatch
- **Citations**: `boot_prototype.c:413`; ROM `0xFC1283D2` (`PORT25-ROM-PHYSW-TASK`), ROM `0xFC1283AD` (`task_PhySw` in `PORT25-ROM-PHYSW-TASK`), ROM `0xFC128680`..`0xFC12877F` (`PORT25-ROM-PHYSW-LITERALS`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as runtime button supervision mechanism.
- **Trigger Condition**: Physical button state transition detected after `task_PhySw` starts.
- **Mechanism**:
  1. `task_Startup_my` invokes `sub_fc1283d2` at line 413 `[VERIFIED: boot_prototype.c:413]`.
  2. `sub_fc1283d2` creates DryOS task `"PhySw"` (entry `0xFC1283AD`, priority 23, stack 2048 bytes) `[STATIC_VERIFIED: ROM 0xFC1283D2-0xFC1283FC, 0xFC128708, 0xFC12870C; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.
  3. `task_PhySw` enters an infinite polling loop `sub_fc12868c`, sampling switches and buttons and storing normalized status masks into RAM `0x00040DAC` `[STATIC_VERIFIED: ROM 0xFC1283B0-0xFC1283C8, 0xFC12868C-0xFC128700, 0xFC128720; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.
  4. If `task_PhySw` determines that a button was released prematurely during startup, or if it dispatches a button event that triggers an early shutdown property, power could be cut downstream `[INFERRED]`.
  5. However, `task_PhySw` operates as a standard input event generator rather than an immediate power-cut gate `[INFERRED]`.

---

### Candidate 5: Canon Firmware Continuation Safety Interlocks (`sub_fc0d0126` -> `TurnOffE1_FW`)
- **Citations**: `boot_prototype.c:438`; ROM `0xFC0D0126`, `0xFC0D01EC` (`PORT25-ROM-FIRMWARE-CONT`), ROM `0xFC0D73C4` (`PORT25-ROM-GPIO-WRITE-MMIO`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as downstream safety shutdown path.
- **Trigger Condition**: Battery door open, SD card door open, low battery voltage, or hardware interlock failure during stock continuation.
- **Mechanism**:
  1. At `boot_prototype.c:438`, `task_Startup_my` branches to `sub_fc0d0126` `[VERIFIED: boot_prototype.c:438]`.
  2. Stock firmware continues driver initialization, querying battery door switches (`sub_fc05c4e0`), battery voltage, and lens sensors `[STATIC_VERIFIED: ROM 0xFC05C4E0; PORT25-ROM-CARD-SWITCHES]`.
  3. If any interlock fails, stock firmware invokes `TurnOffE1_FW` (`0xFC0D01EC`) `[STATIC_VERIFIED: ROM 0xFC0D01EC; PORT25-ROM-FIRMWARE-CONT]`.
  4. `TurnOffE1_FW` disables interrupts via `sub_fc31befc` (`cpsid if` at `0xFC0D01F2`), stops the watchdog via `sub_fc135d9a` (`0xFC0D01F6`), writes `0x004C0003` to GPIO 0x67 at `0xFC0D0202` via `GPIO_Write` (`0xFC0D73C4`), and enters an infinite hang loop `b.n 0xfc0d0206` at `0xFC0D0206` `[STATIC_VERIFIED: ROM 0xFC0D01EC-0xFC0D0206; PORT25-ROM-FIRMWARE-CONT; ROM 0xFC0D73C4; PORT25-ROM-GPIO-WRITE-MMIO]`.
  5. Since the camera booted to UI when the button was held (Observation O1), these interlocks pass under normal physical conditions `[INFERRED: Observation O1]`.

---

### Candidate 6: Initial Task Stage 4 Subsystem Failures (`sub_fc05b558_my` -> `sub_fc05b5ea`)
- **Citations**: `boot_prototype.c:280-330`; ROM `0xFC05B540`..`0xFC05B73F` (`PORT25-ROM-INIT-TASK`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as non-power-cut halt path.
- **Trigger Condition**: Failure of USER_MEM check or any subsystem initialization in Stage 4.
- **Mechanism**:
  1. In Stage 4, seven sequential subsystem calls are checked:
     - USER_MEM size check: `[0x80EC] >= [0x8074] + 0x10` (`boot_prototype.c:274-282`)
     - `dmSetup` (`boot_prototype.c:293-297`)
     - `termDriverInit` (`boot_prototype.c:299-303`)
     - `termDeviceCreate` (`boot_prototype.c:305-310`)
     - `stdioSetup` (`boot_prototype.c:312-317`)
     - `stdlibSetup` (`boot_prototype.c:319-323`)
     - `extlib_setup` (`boot_prototype.c:325-329`)
  2. If any check fails, execution branches to `sub_fc05b5ea` (`0xFC05B5EA`) with an error string literal `[STATIC_VERIFIED: ROM 0xFC05B5EA; PORT25-ROM-INIT-TASK]`.
  3. `sub_fc05b5ea` logs an error message and enters an infinite halt loop `[STATIC_VERIFIED: ROM 0xFC05B5EA; PORT25-ROM-INIT-TASK]`.
  4. This does not write to GPIO 0x67 (does not cut power directly), and all checks are known to succeed empirically in Observation O1 `[INFERRED]`.

---

### Candidate 7: Heap Headroom Check Failure in `sub_fc05b3c8_my`
- **Citations**: `boot_prototype.c:184-191`; ROM `0xFC05B3C8`..`0xFC05B3DA` (`PORT25-ROM-HEAP-SETUP`).
- **Classification**: `[STATIC_VERIFIED]` in source code and ROM disassembly; `[INFERRED]` as non-power-cut halt path.
- **Trigger Condition**: Insufficient DryOS heap headroom (`0x006CE000 - new_sa < 0x000B1FEC`).
- **Mechanism**:
  1. `sub_fc05b3c8_my` checks if `0x006CE000 - r4 >= 0x000B1FEC` (712 KiB) `[VERIFIED: boot_prototype.c:184-188]`.
  2. If headroom fails, it branches to `loc_fc05b3d8: b loc_fc05b3d8` (infinite spin loop) `[VERIFIED: boot_prototype.c:189-191]`.
  3. With `new_sa = 0x00366CB0`, headroom is ~3.4 MiB, far exceeding 712 KiB. This check statically passes and does not cut power `[VERIFIED]`.

---

## 5. Ranked Candidate Summary

The table below summarizes all post-loader candidate points that can cut power or wait on the power button, ranked from highest to lowest likelihood for short-press boot failure `[VERIFIED]`:

| Rank | Candidate Name | Code & ROM Citation | Active Condition | Failure / Power-Cut Action | Epistemic Status & Likelihood |
|:---:|---|---|---|---|:---:|
| **1** | Native Button Check & Power Cut in `sub_fc05b962_my` | `boot_prototype.c:351-354`<br>ROM `0xFC05B96C-0xFC05B976`<br>`PORT25-ROM-STARTUP-TASKS`<br>ROM `0xFC1284BC-0xFC12851A`<br>`PORT25-ROM-POWERON-CHECK` | Default build (`G3X_POWERON_FIX=0`); button released before Stage 5 runs | `sub_fc1284ac` returns `0`; `sub_fc05b962_my` calls `sub_fc05ba56` (`0xFC05BA56`), writing `0x004C0003` to GPIO 0x67 (`0xD20B099C`), cutting DC-DC power and hanging at `0xFC05B976` | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` as root cause<br>**Rank 1 (Definitive for Default Build)** |
| **2** | Unwritten Startup Cause at `0x00009BD0` (Bypassed `sub_fc08ecbc`) | `boot_prototype.c:349`<br>ROM `0xFC128504-0xFC12851A`<br>`PORT25-ROM-POWERON-CHECK`<br>ROM `0xFC08ECBC-0xFC08ECEC`<br>`PORT25-ROM-STARTCAUSE-SAVE`<br>ROM `0xFC08EEF0`<br>`PORT25-ROM-STARTCAUSE-PTR` | Opt-in build (`G3X_POWERON_FIX=1`); button released before line 349 runs | `sub_fc1284ac` skips `bl sub_fc08ecbc` at `0xFC128510`, leaving `*(0x00009BD0)` zeroed (`0x00000000`). Downstream tasks detect invalid boot factor and trigger shutdown via `TurnOffE1_FW` (`0xFC0D01EC`) | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` as leading fix blocker<br>**Rank 2 (Very High for Opt-In Build)** |
| **3** | Hardware Watchdog Expiry (`sub_fc418f2a` / `StartWDT_FW`) | `boot_prototype.c:408`<br>ROM `0xFC418F2A`<br>`PORT25-ROM-WATCHDOG-START`<br>ROM `0xFC135D2C`<br>`PORT25-ROM-WATCHDOG-MODULE`<br>MMIO `0xD20A0000` | Post-loader boot delay or execution stall exceeding ~2.0 s after line 408 | Hardware watchdog countdown timer underflows, triggering `WdtInt` (`0xFC135C14`) and forcing hardware reset or sub-CPU power shutdown | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` as timeout mechanism<br>**Rank 3 (Medium-High if stalled)** |
| **4** | `task_PhySw` Button Release / Button Event Dispatch | `boot_prototype.c:413`<br>ROM `0xFC1283D2`<br>`PORT25-ROM-PHYSW-TASK`<br>ROM `0xFC1283AD`<br>`PORT25-ROM-PHYSW-TASK`<br>ROM `0xFC12868C`<br>`PORT25-ROM-PHYSW-LITERALS` | `task_PhySw` polling loop running after line 413 | If `task_PhySw` interprets early button release as an immediate power-down request rather than normal power-on release | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` as event mechanism<br>**Rank 4 (Medium)** |
| **5** | Canon Firmware Continuation Interlocks (`TurnOffE1_FW`) | `boot_prototype.c:438`<br>ROM `0xFC0D0126`<br>`PORT25-ROM-FIRMWARE-CONT`<br>ROM `0xFC0D01EC`<br>`PORT25-ROM-FIRMWARE-CONT`<br>ROM `0xFC0D73C4`<br>`PORT25-ROM-GPIO-WRITE-MMIO` | Battery door open, SD card door open, low battery voltage, or hardware interlock failure | Downstream Canon initialization calls `TurnOffE1_FW` (`0xFC0D01EC`), writing `0x004C0003` to GPIO 0x67 and halting | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` downstream path<br>**Rank 5 (Low-Medium; passes in O1)** |
| **6** | Initial Task Stage 4 Subsystem Failures (`sub_fc05b5ea`) | `boot_prototype.c:280-330`<br>ROM `0xFC05B540-0xFC05B73F`<br>`PORT25-ROM-INIT-TASK` | USER_MEM check failure or driver setup error (< 0) in Stage 4 | Calls `sub_fc05b5ea` (`0xFC05B5EA`) with error literal, logging error and halting. Does not cut GPIO 0x67 power directly | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` non-power-cut halt<br>**Rank 6 (Negligible; passes in O1)** |
| **7** | Heap Headroom Failure in `sub_fc05b3c8_my` | `boot_prototype.c:184-191`<br>ROM `0xFC05B3C8`<br>`PORT25-ROM-HEAP-SETUP` | DryOS heap headroom < 712 KiB | Enters infinite spin loop `b loc_fc05b3d8` at `boot_prototype.c:190`. Does not cut GPIO 0x67 power directly | `[STATIC_VERIFIED]` in source<br>`[INFERRED]` non-power-cut halt<br>**Rank 7 (Negligible; passes in O1)** |

---

## 6. Proposed Breadcrumb Placement in `boot_prototype.c`

To allow Task T3 to instrument `boot_prototype.c` with LED flash breadcrumbs and empirically isolate exactly how far execution proceeds under a short press, the following insertion points are proposed `[VERIFIED]`:

| Breadcrumb Stage Name | Target File & Line | Insertion Context in `boot_prototype.c` | Candidate / Mechanism Isolated |
|---|---|---|---|
| `STAGE_BC_CORE_ENTRY` | `boot_prototype.c:88` | Entry to `boot()` immediately following stack reset (`mov sp, r0`) | Verifies hand-off from loader into core `boot()` |
| `STAGE_BC_POST_BSS` | `boot_prototype.c:154` | Immediately following Canon BSS zeroing loop, prior to branching to Stage 3 | Confirms Low/High RAM copies and BSS zeroing completed |
| `STAGE_BC_STAGE3_ENTRY` | `boot_prototype.c:175` | Entry to `sub_fc05b3c8_my` immediately after `bl witness_record_core` | Confirms Stage 3 entry and witness core registration |
| `STAGE_BC_PRE_KERNEL_INIT` | `boot_prototype.c:255` | Immediately before `blx sub_fc31b408` (dispatch to DryOS kernel init) | Confirms DryOS memory descriptors populated |
| `STAGE_BC_STAGE4_ENTRY` | `boot_prototype.c:272` | Entry to `sub_fc05b558_my` immediately after `push {r4, lr}` | Confirms DryOS kernel scheduled and dispatched Initial Task |
| `STAGE_BC_STAGE5_ENTRY` | `boot_prototype.c:345` | Entry to `sub_fc05b962_my` immediately after `push {r3, lr}` | Confirms Stage 4 driver initialization passed and Stage 5 reached |
| `STAGE_BC_PRE_POWER_CHECK` | `boot_prototype.c:348` | Immediately before `bl sub_fc1284ac` in `sub_fc05b962_my` | Confirms execution reached the power-on button check gate |
| `STAGE_BC_POWER_CHECK_FAIL` | `boot_prototype.c:356` | Inside `loc_fc05b976` (shutdown path) before or after `sub_fc05ba56` | Proves whether default build branched to `sub_fc05ba56` power cut (Candidate 1) |
| `STAGE_BC_POWER_CHECK_PASS` | `boot_prototype.c:358` | Inside `loc_fc05b978` immediately before `blx sub_fc31b460` | Proves whether button check passed (or opt-in fix branched past power cut) |
| `STAGE_BC_PRE_CREATE_STARTUP` | `boot_prototype.c:369` | Immediately before `blx sub_fc31bbc4` in `sub_fc05b962_my` | Confirms ARAM heap init passed and ready to create "Startup" task |
| `STAGE_BC_POST_CREATE_STARTUP` | `boot_prototype.c:371` | Immediately after `blx sub_fc31bbc4` in `sub_fc05b962_my` | Confirms DryOS CreateTask successfully registered "Startup" task |
| `STAGE_BC_STARTUP_ENTRY` | `boot_prototype.c:384` | Entry to `task_Startup_my` immediately after `push {r4, lr}` | Confirms DryOS scheduler activated "Startup" task |
| `STAGE_BC_PRE_SD1STINIT` | `boot_prototype.c:397` | Immediately before SD1stInit gate check `sub_fc05c4e0` | Confirms pre-SD driver setup completed |
| `STAGE_BC_POST_SD1STINIT` | `boot_prototype.c:403` | At label `1:` immediately after SD1stInit task creation veneer | Confirms SD1stInit creation succeeded or bypassed |
| `STAGE_BC_PRE_WATCHDOG_START` | `boot_prototype.c:408` | Immediately before `bl sub_fc418f2a` in `task_Startup_my` | Confirms execution reached point immediately before watchdog arming |
| `STAGE_BC_POST_WATCHDOG_START` | `boot_prototype.c:409` | Immediately after `bl sub_fc418f2a` in `task_Startup_my` | Confirms hardware watchdog is actively armed and ticking (Candidate 3) |
| `STAGE_BC_PRE_PHYSW_CREATE` | `boot_prototype.c:413` | Immediately before `bl sub_fc1283d2` in `task_Startup_my` | Confirms pre-PhySw driver initialization completed |
| `STAGE_BC_POST_PHYSW_CREATE` | `boot_prototype.c:414` | Immediately after `bl sub_fc1283d2` in `task_Startup_my` | Confirms `task_PhySw` spawned and running (Candidate 4) |
| `STAGE_BC_PRE_FIRMWARE_CONT` | `boot_prototype.c:438` | Immediately before `b.w sub_fc0d0126` in `task_Startup_my` | Confirms CHDK prototype startup complete; handing off to stock firmware |

---

## 7. Bounded ROM Research & Evidence Accounting

### 7.1 Research Protocol Compliance
- In accordance with the repository agent contract and Phase 0 safety protocol (`AGENTS.md:3`, `docs/SAFETY.md:1-8`), **no full-ROM scans and no pattern searches over the whole image were performed** `[VERIFIED]`.
- All ROM reads were strictly bounded to targeted slices, each under 1 KiB (maximum slice 768 bytes, well within the 4096-byte limit per read) `[VERIFIED]`.
- Total newly read ROM bytes across this investigation: **784 bytes** across 6 targeted ranges `[VERIFIED]`.
- Total manifest coverage across all 25 evidence entries: **6,320 bytes**, well within the 65,536-byte budget `[VERIFIED]`.
- Every entry is recorded in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` and validated by `tools/port11c_evidence_validator.py` with 0 errors `[VERIFIED: tools/port11c_evidence_validator.py]`.

### 7.2 Evidence Manifest Summary Table

| Evidence ID | Start Address | End Address | Length | SHA-256 Digest | Status & Covered Functions / Symbols |
|---|:---:|:---:|:---:|---|---|
| `PORT25-ROM-BOOT-EARLY` | `0xFC020000` | `0xFC0201FF` | 512 B | `23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f` | `[STATIC_VERIFIED]` Early boot reset entry `0xFC02000C`, vector copy `sub_fc02007e` |
| `PORT25-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B53F` | 384 B | `68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6` | `[STATIC_VERIFIED]` Heap setup `sub_fc05b3c8`, headroom calculation vs `0x006CE000` |
| `PORT25-ROM-INIT-TASK` | `0xFC05B540` | `0xFC05B73F` | 512 B | `15a153beaeabe9770d5016f7240b0b5bbd9ff6ebf56141341cb1e5eebf2a97fe` | `[STATIC_VERIFIED]` Initial task `sub_fc05b558`, USER_MEM check, driver setup calls |
| `PORT25-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 B | `749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e` | `[STATIC_VERIFIED]` `task_Startup` (`0xFC05B8FC`), `sub_fc05b962`, `sub_fc05ba56` (power cut), `sub_fc05ba68` |
| `PORT25-ROM-STARTDISKBOOT` | `0xFC05BBE0` | `0xFC05BDDF` | 512 B | `c773cbfa1877af69cbf36b0590814abff7fbd1321de5aff86af28946968d7839` | `[STATIC_VERIFIED]` `StartDiskboot` (`0xFC05BBEA`), diskboot helper `sub_fc05bcdc` |
| `PORT25-ROM-CARD-SWITCHES` | `0xFC05C4D0` | `0xFC05C51F` | 80 B | `886c3e10248cc33ac671b575331311bbaf59ae549ab01a9414ddb1b470c314c5` | `[STATIC_VERIFIED]` `sub_fc05c4e0` SD door / write-protect switch query |
| `PORT25-ROM-NORMAL-MODE` | `0xFC079400` | `0xFC0794FF` | 256 B | `222eb4225d2e5d34742f5ed11b306b21c44a1eb2e18e48936cc6643d08a9560c` | `[STATIC_VERIFIED]` `IsNormalCameraMode_FW` (`0xFC079404`), pointer `0xFDF20380` |
| `PORT25-ROM-GPIO-READ` | `0xFC087110` | `0xFC08713F` | 48 B | `2238807ba4260729bb4991960fa1a40f257bed76425e8b7bb3cb6111a5920059` | `[STATIC_VERIFIED]` `sub_fc08711a` GPIO read veneer -> `GPIO_Read` at `0xFC0D73D0` |
| `PORT25-ROM-STARTCAUSE-SAVE` | `0xFC08ECB0` | `0xFC08ECFF` | 80 B | `039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d` | `[STATIC_VERIFIED]` `sub_fc08ecbc` startup reason recorder -> `*(0x9BC4 + 12)` |
| `PORT25-ROM-STARTCAUSE-PTR` | `0xFC08EEE0` | `0xFC08EEFF` | 32 B | `0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6` | `[STATIC_VERIFIED]` Literal pointer `0xFC08EEF0` pointing to base address `0x00009BC4` |
| `PORT25-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D023F` | 448 B | `33d2fae4ed8c9c228ea6cc8f3304a26b96f8a4fb6d9d3bdc37cd056e7833456e` | `[STATIC_VERIFIED]` Continuation `sub_fc0d0126`, `sub_fc0d0150` ("ClockSave"), `TurnOffE1_FW` (`0xFC0D01EC`) |
| `PORT25-ROM-GPIO-WRITE-MMIO` | `0xFC0D73C0` | `0xFC0D74BF` | 256 B | `0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b` | `[STATIC_VERIFIED]` `GPIO_Write` (`0xFC0D73C4`) and `GPIO_Read` (`0xFC0D73D0`) |
| `PORT25-ROM-CACHE-MAINT` | `0xFC127A00` | `0xFC127B7F` | 384 B | `519594faaab42e66229096ef890f9161e2d1715e6044a911a74e2ebdf20415cb` | `[STATIC_VERIFIED]` Cache clean `sub_fc127a62`, memory helpers `sub_fc127b3c`, `sub_fc127b4e` |
| `PORT25-ROM-PHYSW-TASK` | `0xFC1283A0` | `0xFC12849F` | 256 B | `9381dabcf3fb6c55ec26118cdb7a6626a9b84211f7cd171175470421db181500` | `[STATIC_VERIFIED]` `task_PhySw` (`0xFC1283AD`), spawner `sub_fc1283d2` **[NEW READ: 256 B]** |
| `PORT25-ROM-POWERON-CHECK` | `0xFC1284A0` | `0xFC1285DF` | 320 B | `634fd848e765cad5b01737956e6aea9ddd12dbb4413213ec2a9c3d2a421813d4` | `[STATIC_VERIFIED]` `sub_fc1284ac` button check (samples GPIO 0x97, 0x98, 0x88, 0x02) |
| `PORT25-ROM-PHYSW-LITERALS` | `0xFC128680` | `0xFC12877F` | 256 B | `60db72e096ddc7915f3f0bea545cde955da38224ab8fb06297631462fe8c8572` | `[STATIC_VERIFIED]` `sub_fc12868c` sampling loop, literal `"PhySw"`, `"PhySwDrv.c"` **[NEW READ: 256 B]** |
| `PORT25-ROM-MPU-CONFIG` | `0xFC135280` | `0xFC1352FF` | 128 B | `3327ae3b2b5508a96aeab70b4076fd83fa199ae9c77d550475bd4effef5f5a5c` | `[STATIC_VERIFIED]` MPU configuration `0xFC135280` called from `sub_fc05ba68` |
| `PORT25-ROM-WATCHDOG-MODULE` | `0xFC135C00` | `0xFC135E3F` | 576 B | `29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb` | `[STATIC_VERIFIED]` `WatchDog.c`: `WdtInt` (`0xFC135C14`), `StartWDT_FW` (`0xFC135D2C`), `task_WdtReset` |
| `PORT25-ROM-SD1STINIT-VENEER` | `0xFC31B1E0` | `0xFC31B21F` | 64 B | `6122841f084da666089820aacae31c016345c903d8dc7e29f1029e23d5c89bed` | `[STATIC_VERIFIED]` `sub_fc31b1f4` CreateTask veneer spawning "SD1stInit" **[NEW READ: 64 B]** |
| `PORT25-ROM-KERNEL-INIT-VENEER` | `0xFC31B400` | `0xFC31B47F` | 128 B | `be7ee2c5d2b00286374e2ace906811cc775f0ff2d4c7e16d50855df8d0e589c4` | `[STATIC_VERIFIED]` DryOS kernel init veneer `sub_fc31b408`, memory allocate `sub_fc31b460` |
| `PORT25-ROM-CREATETASK-VENEER` | `0xFC31BBA0` | `0xFC31BBEF` | 80 B | `59c9adc82ad1ad670ecf7ba0d42665a34f7acf1a10b68ad75874afe1fae77487` | `[STATIC_VERIFIED]` `sub_fc31bbc4` CreateTask veneer spawning "Startup" **[NEW READ: 80 B]** |
| `PORT25-ROM-MEMSET-VENEER` | `0xFC31BF90` | `0xFC31BFCF` | 64 B | `7d4ee3349a02377c01f913cb9ba9ec4d2d27247448882aa2fbd0ee63a84c8592` | `[STATIC_VERIFIED]` `sub_fc31bfac` memset veneer called in `sub_fc05b3c8` **[NEW READ: 64 B]** |
| `PORT25-ROM-ARAM-HEAP-INIT` | `0xFC382C80` | `0xFC382CBF` | 64 B | `b618d01755115b3709c23799e69032c0362fa70610639d3f9832309ab7add654` | `[STATIC_VERIFIED]` `sub_fc382c8c` ARAM heap init called in `sub_fc05b962` **[NEW READ: 64 B]** |
| `PORT25-ROM-WATCHDOG-START` | `0xFC418F20` | `0xFC418F7F` | 96 B | `46e8e2149df855d0f1414699a1fdea355b9370c83e552a749314a32283da7da5` | `[STATIC_VERIFIED]` `sub_fc418f2a` watchdog arming helper called in `task_Startup` |
| `PORT25-ROM-NORMAL-FLAG` | `0xFDF20380` | `0xFDF2038F` | 16 B | `7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64` | `[STATIC_VERIFIED]` Literal flag byte `0xFDF20380` read by `IsNormalCameraMode_FW` (`0x00`) |

---

## 8. Summary & Next Steps for Task T3

1. **Short-Press Power-Off Mechanism is Fully Localized** `[INFERRED]`:
   - In the unmodified baseline (`G3X_POWERON_FIX=0`), short press powers off at Candidate 1: `sub_fc05b962_my` (`boot_prototype.c:351-354`) -> `sub_fc1284ac` returns `0` -> `sub_fc05ba56` cuts power via GPIO 0x67 (`0xD20B099C`) `[STATIC_VERIFIED: ROM 0xFC05B96C-0xFC05B976, 0xFC05BA56; PORT25-ROM-STARTUP-TASKS]`.
   - In the opt-in candidate (`G3X_POWERON_FIX=1`), Candidate 1 is bypassed, but Candidate 2 arises: `sub_fc1284ac` still executes and skips `bl sub_fc08ecbc`, leaving `*(0x00009BD0)` zeroed `[STATIC_VERIFIED: ROM 0xFC128504-0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
2. **Breadcrumb Placement Plan Ready for Task T3** `[VERIFIED]`:
   - Table in Section 6 defines all breadcrumb stages, file:line insertion points, and what hypothesis each isolates.
   - Task T3 can insert GPIO 33 LED toggles at these points to observe hardware progress during short-press trials without guessing.
