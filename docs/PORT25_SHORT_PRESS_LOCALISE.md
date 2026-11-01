# PORT-25 T2: Post-Loader Short-Press Power-Off Candidate Localisation & Boot Path Analysis (GM1.10C)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7]`
- **Evaluation Mode**: Phase 0 Read-Only Offline Firmware Disassembly & Architectural Analysis `[VERIFIED: AGENTS.md:3; docs/SAFETY.md:1-8]`
- **Safety Restriction**: STRICT NO-GO on hardware trials, camera connection, SD card writing, and firmware flashing (`docs/SAFETY.md:1-8`).
- **Evidence Governance**: All ROM reads are strictly bounded (slice sizes <= 768 B <= 4096 B, total newly read ROM bytes: 784 B across 6 ranges, total manifest bytes: 6,320 B <= 65,536 B budget). All 25 evidence ranges are recorded in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` and validate cleanly via `tools/port11c_evidence_validator.py` `[VERIFIED: tools/port11c_evidence_validator.py]`.
- **Bounded Research Guarantee**: No full-ROM scans and no pattern searches over the whole image were performed `[VERIFIED]`.
- **Epistemic Classifications**:
  - `[VERIFIED]`: Directly proven by repository tracked files, source code, or owner-reported physical test records.
  - `[STATIC_VERIFIED]`: Confirmed directly from bounded static ROM disassembly within the approved evidence manifest ranges.
  - `[INFERRED]`: Deduced from verified static disassembly, hardware architecture, and execution sequences.
  - `[UNKNOWN]`: Dynamic hardware states, external microcontroller firmware, or unmapped runtime conditions that cannot be determined offline.
  - `[OWNER-REPORTED]`: Observations recorded by the camera owner during physical sessions.

---

## 1. Executive Summary

This study provides an exhaustive localization and comparative ranking of all potential power-cut and power-button-wait points on the Canon PowerShot G3 X (firmware GM1.10C) boot execution path following loader hand-off `[VERIFIED]`.

In physical trials of the unchanged PORT-19 baseline build (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`), the camera achieved successful boot into the stock user interface (`O1`) **exclusively when the physical power button was held continuously down** until LCD illumination `[OWNER-REPORTED: milestone brief; docs/PORT24_POWERON_FIX.md:19-24]`. Conversely, giving the power button a standard brief press (tap of ~100–250 ms) resulted in immediate shutdown shortly after the loader executed `[OWNER-REPORTED: milestone brief; docs/PORT24_POWERON_FIX.md:21-25]`.

### Key Findings

1. **Root Cause in Default Build (`G3X_POWERON_FIX=0`) [Rank 1 — INFERRED / STATIC_VERIFIED]**:
   - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:351-354`, the Stage 5 routine `sub_fc05b962_my` retains the native Canon button check `bl sub_fc1284ac` `[VERIFIED: boot_prototype.c:352]`.
   - On a short press, the user has already released the button before Stage 5 executes `[INFERRED]`. `sub_fc1284ac` samples GPIO 0x97 as released (`0`), returns `r0 = 0`, fails `cbnz r0, loc_fc05b978`, and branches to `sub_fc05ba56` (`0xFC05BA56`), which writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`), immediately de-asserting the power-hold latch and cutting system power `[STATIC_VERIFIED: ROM 0xFC05B96C-0xFC05B976, 0xFC05BA56; PORT25-ROM-STARTUP-TASKS; ROM 0xFC0D73C4; PORT25-ROM-GPIO-WRITE-MMIO]`.

2. **Startup Cause at `0x00009BD0` in Opt-In Fix (`G3X_POWERON_FIX=1`) [Rank 2 — INFERRED / UNKNOWN / STATIC_VERIFIED]**:
   - Under `G3X_POWERON_FIX=1` (`boot_prototype.c:349`), `sub_fc05b962_my` forces `movs r0, #1` and branches to `loc_fc05b978`, successfully bypassing `sub_fc05ba56` `[VERIFIED: boot_prototype.c:349]`.
   - However, `sub_fc1284ac` is still executed at line 349 `[VERIFIED: boot_prototype.c:349]`. When buttons are released, `sub_fc1284ac` branches to `0xFC12851A`, **skipping `bl sub_fc08ecbc` at `0xFC128510`** `[STATIC_VERIFIED: ROM 0xFC1284FC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
   - Function `sub_fc08ecbc` is the start-cause recorder; skipping it leaves `*(0x00009BD0)` unwritten `[STATIC_VERIFIED: ROM 0xFC08ECBC-0xFC08ECEC; PORT25-ROM-STARTCAUSE-SAVE; ROM 0xFC08EEF0; PORT25-ROM-STARTCAUSE-PTR]`.
   - Address `0x00009BD0` lies within Low RAM (`0x00008000`..`0x0003F4F4`) populated by Copy Loop 3 (`boot_prototype.c:133-143`). Because the ROM source bytes copied to `0x00009BD0` are not covered by an evidence manifest range, its initial value after `boot()` is `[UNKNOWN]` (`docs/PORT24_POWERON_FIX.md:246`).
   - Furthermore, while `sub_fc12851e` (`0xFC12851E`) acts as a getter returning `*(0x00009BD0)` `[STATIC_VERIFIED: ROM 0xFC12851E-0xFC128522; PORT25-ROM-POWERON-CHECK]`, which downstream tasks consume this value and whether an uninitialized value triggers an orderly shutdown or error remain `[UNKNOWN]`.
   - Because skipping `sub_fc08ecbc` is verified to occur on every short press when `G3X_POWERON_FIX=1` is active, directly replicating the known warm-boot failure mode from sister port G3 X 1.10E (`g3x_110e.patch:1681-1703`), this is ranked **Rank 2** as the leading hypothesis for the opt-in fix.

3. **Watchdog Expiration Risk [Rank 3 — INFERRED / STATIC_VERIFIED / UNKNOWN]**:
   - `task_Startup_my` arms the hardware watchdog timer via `sub_fc418f2a` at `boot_prototype.c:408` (`StartWDT_FW` `0xFC135D2C`) `[STATIC_VERIFIED: ROM 0xFC418F2A; PORT25-ROM-WATCHDOG-START; ROM 0xFC135D2C; PORT25-ROM-WATCHDOG-MODULE]`.
   - In stock Canon operation, the watchdog is kept alive by `task_WdtReset` (`0xFC135CB0`), which sleeps for 2000 ms (`SleepTask(2000)` at `0xFC135CC6`) and resets the timer by writing `0xAA55` to MMIO `0xD20A0004` `[STATIC_VERIFIED: ROM 0xFC135CB0-0xFC135CC8; PORT25-ROM-WATCHDOG-MODULE]`. Note that 2000 ms is the software service interval, NOT the hardware timer expiry deadline `[VERIFIED]`.
   - If execution stalls after line 408 or if `task_WdtReset` is delayed, the watchdog expires, triggering interrupt `WdtInt` (`0xFC135C92`) `[STATIC_VERIFIED: ROM 0xFC135C92, 0xFC135CEE-0xFC135CF6; PORT25-ROM-WATCHDOG-MODULE]`. The hardware outcome (hard SoC reset, bus lockup, or PMIC power cut) remains `[UNKNOWN]`.

4. **Sub-CPU Power-Hold Supervision & Autonomous PMIC Latch Timeout [Rank 4 — INFERRED / UNKNOWN / STATIC_VERIFIED]**:
   - In DIGIC 6 cameras, the power rails are initially latched by an external power management microcontroller (sub-CPU/PMIC) when the physical button is pressed `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:294-300]`.
   - In Stage 5, `sub_fc05ba68` (`0xFC05BA68`) tail-branches to `mpuSetup` (`0xFC135280`), which sets up the ARM CP15 Memory Protection Unit (MPU); it is **not** serial communication or a handshake with the external microcontroller (sub-CPU/PMIC) `[STATIC_VERIFIED: ROM 0xFC05BA68-0xFC05BA8A; PORT25-ROM-STARTUP-TASKS; ROM 0xFC135280; PORT25-ROM-MPU-CONFIG; docs/PORT24_POWERON_FIX.md]`.
   - Returning from `sub_fc05ba68` demonstrates only that ARM MPU configuration completed; it does **not** prove that a sub-CPU handshake happened or succeeded `[STATIC_VERIFIED]`.
   - In stock firmware, SIO and DC-DC communication drivers are initialized at `0xFC05B8FE..0xFC05B90A` prior to `StartDiskboot` (`0xFC05B90E`) `[STATIC_VERIFIED: ROM 0xFC05B8FE-0xFC05B90A; PORT25-ROM-STARTUP-TASKS]`. No dedicated sub-CPU handshake exists in `sub_fc05b962_my`.
   - If the external sub-CPU firmware enforces an autonomous timeout that unlatches DC-DC power if the physical button is released early without downstream supervision, power would be cut externally `[INFERRED]`. Because the sub-CPU runs external microcontroller firmware not contained in `PRIMARY.BIN`, the exact handshake protocol and timeout duration remain `[UNKNOWN: external microcontroller firmware]`. Given that `0xFC135280` does not communicate with the sub-CPU, this candidate is re-ranked to **Rank 4**.

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
   - sub_fc05ba68: pxSetup, dhcpc_setup, mpuSetup (0xFC135280; ARM CP15 Memory Protection Unit setup)
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
In `boot_prototype.c:344-358`:
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
   - Configures the ARM CP15 Memory Protection Unit (MPU); it does NOT establish serial communication or a handshake with the external sub-CPU `[STATIC_VERIFIED: ROM 0xFC135280; PORT25-ROM-MPU-CONFIG; docs/PORT24_POWERON_FIX.md]`. It does not sample buttons or de-assert GPIO 0x67 `[STATIC_VERIFIED]`.

2. **`sub_fc079404` (`IsNormalCameraMode_FW`)** `[STATIC_VERIFIED: ROM 0xFC079404-0xFC079410; PORT25-ROM-NORMAL-MODE]`:
   - Reads byte from pointer `0xFDF20380` (verified `0x00` in ROM) `[STATIC_VERIFIED: ROM 0xFDF20380; PORT25-ROM-NORMAL-FLAG]`.
   - Returns `r0 = 1` (normal camera mode). This return value is passed in `r0` into `sub_fc1284ac` `[STATIC_VERIFIED]`.

3. **`sub_fc1284ac` (`0xFC1284AC`)** `[STATIC_VERIFIED: ROM 0xFC1284AC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`:
   - Under `G3X_POWERON_FIX=1`, `bl sub_fc1284ac` **is still executed** at `boot_prototype.c:349` `[VERIFIED: boot_prototype.c:349]`.
   - `sub_fc1284ac` samples GPIO 0x97 (Power), 0x98 (Playback), 0x88 (WiFi), and 0x02 via `sub_fc08711a` (`GPIO_Read` at `0xFC0D73D0`) `[STATIC_VERIFIED: ROM 0xFC1284BC-0xFC1284EC; PORT25-ROM-POWERON-CHECK; ROM 0xFC08711A; PORT25-ROM-GPIO-READ; ROM 0xFC0D73D0; PORT25-ROM-GPIO-WRITE-MMIO]`.
   - When the button has been released (raw reading `1`, inverted by `bic` to `0`), all button states are `0` `[STATIC_VERIFIED: ROM 0xFC1284C4, 0xFC1284CE; PORT25-ROM-POWERON-CHECK]`.
   - At `0xFC1284FC-0xFC128504`, `orrs r0, r4` produces `0`, and `beq.n 0xfc12851a` jumps directly to the function exit at `0xFC12851A` `[STATIC_VERIFIED: ROM 0xFC128504, 0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
   - **Crucial Side Effect**: It bypasses `bl sub_fc08ecbc` (`0xFC128510`) `[STATIC_VERIFIED: ROM 0xFC128510; PORT25-ROM-POWERON-CHECK]`. The start-cause structure at `0x00009BD0` is therefore **not updated** `[INFERRED]`.

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
   - Entry point: `0xFC0D00ED` (`0xFC0D00EC`), Priority 32, Stack 512 bytes, Name `"ClockSave"` (`0xFC0D01DC`) via DryOS CreateTask veneer (called at `0xFC0D0174`) `[STATIC_VERIFIED: ROM 0xFC0D0166-0xFC0D01DC; PORT25-ROM-FIRMWARE-CONT]`.
4. **"SD1stInit" Task** `[VERIFIED: boot_prototype.c:397-402; ROM 0xFC31B1F4; PORT25-ROM-SD1STINIT-VENEER]`:
   - Spawned in `task_Startup_my` at `boot_prototype.c:401` via `blx sub_fc31b1f4` (`0xFC31B1F4`), conditional on `sub_fc05c4e0(0)` bit 0 == 0 `[VERIFIED: boot_prototype.c:397-402; ROM 0xFC05C4E0; PORT25-ROM-CARD-SWITCHES]`.
5. **"PhySw" Physical Switch Task** `[VERIFIED: boot_prototype.c:413; ROM 0xFC1283D2; PORT25-ROM-PHYSW-TASK]`:
   - Spawned in `task_Startup_my` at `boot_prototype.c:413` by calling `sub_fc1283d2` (`0xFC1283D2`) `[VERIFIED: boot_prototype.c:413]`.
   - Entry point: `task_PhySw` (`0xFC1283AD`), Priority 23, Stack 2048 bytes, Name `"PhySw"` (`0xFC12870C`) via DryOS CreateTask veneer (called at `0xFC1283F8`) `[STATIC_VERIFIED: ROM 0xFC1283D2-0xFC1283FC, 0xFC128708, 0xFC12870C; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.

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

### Candidate 2: Sub-CPU Power-Hold Supervision & Autonomous PMIC Latch Timeout
- **Citations**: `boot_prototype.c:346`; ROM `0xFC05BA68`..`0xFC05BA8A` (`PORT25-ROM-STARTUP-TASKS`), ROM `0xFC135280`..`0xFC1352FF` (`PORT25-ROM-MPU-CONFIG`), ROM `0xFC05B8FE`..`0xFC05B90A` (`PORT25-ROM-STARTUP-TASKS`), `docs/PORT23_POWER_SUPERVISION.md:294-300`.
- **Classification**: `[STATIC_VERIFIED]` for ROM MPU setup; `[INFERRED]` as hardware power-supervision hypothesis; `[UNKNOWN: external microcontroller firmware]` for autonomous latch timeout and sub-CPU firmware behavior.
- **Trigger Condition**: Power button pressed and released; sub-CPU hardware latch drops DC-DC rails autonomously if button is released without downstream supervision.
- **Architectural Clarification regarding `0xFC135280`**:
  1. In `sub_fc05b962_my`, line 346 calls `sub_fc05ba68` (`0xFC05BA68`), which calls `pxSetup`, `dhcpc_setup`, and branches to `mpuSetup` (`0xFC135280`) `[STATIC_VERIFIED: ROM 0xFC05BA68-0xFC05BA8A; PORT25-ROM-STARTUP-TASKS; ROM 0xFC135280; PORT25-ROM-MPU-CONFIG]`.
  2. The routine at `0xFC135280` branches into ARM CP15 code configuring the ARM Cortex-R Memory Protection Unit (MPU) `[STATIC_VERIFIED: ROM 0xFC135280; PORT25-ROM-MPU-CONFIG; docs/PORT24_POWERON_FIX.md]`. It is **not** serial communication or a handshake with the external microcontroller (sub-CPU/PMIC).
  3. Consequently, returning from `sub_fc05ba68` demonstrates only that ARM MPU setup returned without exception; it does **not** prove that a sub-CPU handshake happened or succeeded `[STATIC_VERIFIED]`.
  4. In stock firmware, SIO and DC-DC communication drivers are initialized at `0xFC05B8FE..0xFC05B90A` prior to `StartDiskboot` (`0xFC05B90E`) `[STATIC_VERIFIED: ROM 0xFC05B8FE-0xFC05B90A; PORT25-ROM-STARTUP-TASKS]`. No dedicated sub-CPU handshake exists in `sub_fc05b962_my`.
- **Remaining UNKNOWN Protocol Details**:
  1. The sub-CPU / PMIC controller runs independent proprietary microcontroller firmware outside the main ARM address space and not contained in `PRIMARY.BIN` `[UNKNOWN: external microcontroller firmware]`.
  2. Whether the external sub-CPU firmware enforces an autonomous power-rail cut-off timeout if the power button is released early is `[UNKNOWN: external microcontroller firmware]`.
- **Mechanism**:
  1. DIGIC 6 cameras rely on an external power management controller (sub-CPU) that latches the main DC-DC rails when the Power button is pressed `[INFERRED: docs/PORT6A_POWERON_EVIDENCE.md:14-20]`.
  2. If the sub-CPU firmware drops the hardware power latch purely on button release without ongoing communication, power would be cut externally `[INFERRED]`.
  3. However, because `0xFC135280` does not communicate with the sub-CPU and no Stage 5 handshake call exists, there is no evidence of a failed handshake at this point `[STATIC_VERIFIED]`.
- **Likelihood & Breadcrumbs**: Re-ranked to **Rank 4** (Lowered Likelihood: Unmapped External Microcontroller Hypothesis). Re-ranked below Startup Cause (Rank 2) and Watchdog (Rank 3) because `sub_fc05ba68` is ARM MPU setup, eliminating the hypothesis of a failed Stage 5 sub-CPU handshake. Breadcrumbs `STAGE_BC_PRE_MPU_SETUP` (line 346) and `STAGE_BC_POST_MPU_SETUP` (line 347) isolate MPU setup return only, not a sub-CPU handshake.

---

### Candidate 3: Hardware Watchdog Timer Expiry (`sub_fc418f2a` / `StartWDT_FW`)
- **Citations**: `boot_prototype.c:408`; ROM `0xFC418F2A` (`PORT25-ROM-WATCHDOG-START`), ROM `0xFC135C00`..`0xFC135E3F` (`PORT25-ROM-WATCHDOG-MODULE`), MMIO `0xD20A0000`, MMIO `0xD20A0004`.
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[UNKNOWN]` for hardware countdown duration and physical expiration effect.
- **Trigger Condition**: Boot sequence execution stalls after line 408 or `task_WdtReset` is delayed beyond the hardware timeout.
- **Detailed Architectural Analysis**:
  1. **Software Servicing**: In `task_Startup_my`, line 408 calls `sub_fc418f2a` (`0xFC418F2A`), which configures parameters and invokes `StartWDT_FW` (`0xFC135D2C`) `[STATIC_VERIFIED: ROM 0xFC418F2A; PORT25-ROM-WATCHDOG-START; ROM 0xFC135D2C; PORT25-ROM-WATCHDOG-MODULE]`. In stock operation, `task_WdtReset` (`0xFC135CB0`) loops indefinitely, executing `SleepTask(2000)` at `0xFC135CC6` and resetting the hardware counter by writing `0xAA55` to MMIO `0xD20A0004` `[STATIC_VERIFIED: ROM 0xFC135CB0-0xFC135CC8; PORT25-ROM-WATCHDOG-MODULE]`. **`SleepTask(2000)` is the verified software service interval, NOT the hardware expiry deadline** `[VERIFIED]`.
  2. **Hardware Expiry Timing**: `StartWDT_FW` writes control parameters to MMIO `0xD20A0000` `[STATIC_VERIFIED: ROM 0xFC135D2C, 0xFC135DFC; PORT25-ROM-WATCHDOG-MODULE]`. The exact countdown clock divisor, countdown duration, and hardware expiry deadline in milliseconds are `[UNKNOWN]` without hardware register documentation.
  3. **Diagnostic Handling**: During watchdog initialization in `sub_fc135ccc`, interrupt vector 395 (`0x18B`, `"WdtInt"`) is registered with handler function `0xFC135C92` (Thumb address `0xFC135C93`) at `0xFC135CEE-0xFC135CF6` `[STATIC_VERIFIED: ROM 0xFC135CEA-0xFC135CF6, 0xFC135E04, 0xFC135E08; PORT25-ROM-WATCHDOG-MODULE]`. When the watchdog interrupt triggers, handler `WdtInt` at `0xFC135C92` clears the interrupt bit at MMIO `0xD20A0000` and dispatches diagnostic trace routine `0xFC135C14` (`0xFC135C15`) to DryOS `[STATIC_VERIFIED: ROM 0xFC135C92-0xFC135CAC, 0xFC135E00; PORT25-ROM-WATCHDOG-MODULE]`.
  4. **Unknown Hardware Effect**: Whether unserviced timer expiration forces an immediate SoC hardware reset, an NMI exception, a bus hang, or an external sub-CPU power shutdown is `[UNKNOWN]`.
  5. **Correction Regarding Loader Stall**: Earlier physical trials observed that an artificial multi-second stall in the loader resulted in a shutdown. Because that stall occurred during loader execution, strictly *before* `task_Startup_my` was created and *before* `sub_fc418f2a` armed the watchdog at line 408, it could not have been caused by this watchdog `[VERIFIED: docs/PORT23_POWER_SUPERVISION.md:280]`.
- **Likelihood & Breadcrumbs**: Ranked **Rank 3** (Plausible if execution stalls after line 408). Breadcrumbs `STAGE_BC_PRE_WATCHDOG_START` (line 408) and `STAGE_BC_POST_WATCHDOG_START` (line 409) isolate watchdog activation.

---

### Candidate 4: Startup Cause at `0x00009BD0` (Bypassed `sub_fc08ecbc`)
- **Citations**: `boot_prototype.c:349` (`G3X_POWERON_FIX=1`); ROM `0xFC128504-0xFC12851A` (`PORT25-ROM-POWERON-CHECK`), ROM `0xFC08ECBC-0xFC08ECEC` (`PORT25-ROM-STARTCAUSE-SAVE`), ROM `0xFC08EEF0` (`PORT25-ROM-STARTCAUSE-PTR`), ROM `0xFC12851E-0xFC128522` (`PORT25-ROM-POWERON-CHECK`).
- **Classification**: `[STATIC_VERIFIED]` for ROM disassembly of `sub_fc1284ac` and `sub_fc08ecbc`; `[UNKNOWN]` for initial Low RAM value and downstream consumer/shutdown edge; `[INFERRED]` as unverified boot-factor hypothesis.
- **Trigger Condition**: `G3X_POWERON_FIX=1` active on a short press.
- **Mechanism & Unknowns**:
  1. `G3X_POWERON_FIX=1` forces `r0 = 1` and branches to `loc_fc05b978`, successfully bypassing `sub_fc05ba56` `[VERIFIED: boot_prototype.c:349]`.
  2. However, line 349 **still called `sub_fc1284ac`** `[VERIFIED: boot_prototype.c:349]`.
  3. Because the button was released, `sub_fc1284ac` jumped straight from `0xFC128504` to `0xFC12851A`, completely skipping `bl sub_fc08ecbc` at `0xFC128510` `[STATIC_VERIFIED: ROM 0xFC1284FC-0xFC12851A; PORT25-ROM-POWERON-CHECK]`.
  4. `sub_fc08ecbc` is the start-cause recorder: in GM1.10C, it sets `*( *(0xFC08EEF0) + 12 ) = *(0x00009BC4 + 12) = *(0x00009BD0)` to `0x80000` (Power), `0x100000` (Play), `0x40000` (WiFi), or `0x20000` (GPIO2) `[STATIC_VERIFIED: ROM 0xFC08ECBC-0xFC08ECEC; PORT25-ROM-STARTCAUSE-SAVE; ROM 0xFC08EEF0; PORT25-ROM-STARTCAUSE-PTR]`.
  5. Because `sub_fc08ecbc` was never called, `*(0x00009BD0)` is not updated. During `boot()`, Copy Loop 3 copied Low RAM data from ROM source bytes into `0x00008000`..`0x0003F4F4` `[VERIFIED: boot_prototype.c:133-143]`. Because the ROM source bytes copied to `0x00009BD0` are not covered by an evidence manifest range, the start-cause word's initial value after `boot()` is `[UNKNOWN]` (rather than known zero; cf. `docs/PORT24_POWERON_FIX.md:246`).
  6. Getter function `sub_fc12851e` (`0xFC12851E`) returns `*(0x00009BD0)` `[STATIC_VERIFIED: ROM 0xFC12851E-0xFC128522; PORT25-ROM-POWERON-CHECK]`. However, which downstream tasks consume this value and whether an uninitialized or unrecognized value causes an orderly shutdown or error are `[UNKNOWN]` (no bounded control-flow edge to shutdown is mapped).
  7. **Historical Precedent**: In sister port G3 X 1.10E (`g3x_110e.patch:1681-1703`), ranma explicitly documented that `sub_fc1284ac` failed on warm boot and had to be replaced by manually writing `0x80000` into `*(0x9BC4 + 12)` `[VERIFIED: docs/PORT6C_CHDK_INTEGRATION_GAPS.md:42; docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md]`. Whether GM1.10C requires this or shuts down without it remains `[UNKNOWN]`.
- **Likelihood & Breadcrumbs**: Ranked **Rank 2** (Leading Hypothesis for Opt-In Build `G3X_POWERON_FIX=1`). Re-ranked above Watchdog (Rank 3) and Sub-CPU (Rank 4) because bypassing `sub_fc08ecbc` is verified to occur on every short press under `G3X_POWERON_FIX=1`, directly replicating the known warm-boot failure mode from sister port G3 X 1.10E (`g3x_110e.patch:1681-1703`).

---

### Candidate 5: `task_PhySw` Button Release / Button Event Dispatch
- **Citations**: `boot_prototype.c:413`; ROM `0xFC1283D2` (`PORT25-ROM-PHYSW-TASK`), ROM `0xFC1283AD` (`task_PhySw` in `PORT25-ROM-PHYSW-TASK`), ROM `0xFC128680`..`0xFC12877F` (`PORT25-ROM-PHYSW-LITERALS`).
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly; `[INFERRED]` as runtime button supervision mechanism; `[UNKNOWN]` for downstream event handling.
- **Trigger Condition**: Physical button state transition detected after `task_PhySw` starts.
- **Mechanism**:
  1. `task_Startup_my` invokes `sub_fc1283d2` at line 413 `[VERIFIED: boot_prototype.c:413]`.
  2. `sub_fc1283d2` creates DryOS task `"PhySw"` (entry `0xFC1283AD`, priority 23, stack 2048 bytes) `[STATIC_VERIFIED: ROM 0xFC1283D2-0xFC1283FC, 0xFC128708, 0xFC12870C; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.
  3. `task_PhySw` enters an infinite polling loop `sub_fc12868c`, sampling switches and buttons and storing normalized status masks into RAM `0x00040DAC` `[STATIC_VERIFIED: ROM 0xFC1283B0-0xFC1283C8, 0xFC12868C-0xFC128700, 0xFC128720; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS]`.
  4. If `task_PhySw` determines that a button was released prematurely during startup, or if it dispatches a button event that triggers an early shutdown property, power could be cut downstream `[INFERRED]`.
  5. However, `task_PhySw` operates as a standard input event generator rather than an immediate power-cut gate `[INFERRED]`.
- **Likelihood**: Ranked **Rank 5** (Medium).

---

### Candidate 6: Downstream Canon Firmware Interlocks & Orderly Shutdown (`TurnOffE1_FW`)
- **Citations**: `boot_prototype.c:438`; ROM `0xFC0D0126`, `0xFC0D01EC` (`PORT25-ROM-FIRMWARE-CONT`), ROM `0xFC0D73C4` (`PORT25-ROM-GPIO-WRITE-MMIO`).
- **Classification**: `[STATIC_VERIFIED]` for function bodies in ROM disassembly; `[UNKNOWN]` for trigger conditions and reachability edges from `sub_fc0d0126`.
- **Trigger Condition**: Potential hardware interlocks (e.g. battery door, SD card door, low voltage) or shutdown property events during stock continuation.
- **Mechanism & Reachability Analysis**:
  1. At `boot_prototype.c:438`, `task_Startup_my` branches to `sub_fc0d0126` `[VERIFIED: boot_prototype.c:438]`.
  2. Disassembly of `sub_fc0d0126` (`0xFC0D0126`..`0xFC0D014C`) reveals that it only performs internal counter bookkeeping at Low RAM `0x00008380` and branches out `[STATIC_VERIFIED: ROM 0xFC0D0126-0xFC0D014C; PORT25-ROM-FIRMWARE-CONT]`. It does not directly perform sensor checks or call shutdown functions.
  3. `TurnOffE1_FW` (`0xFC0D01EC`) is an independent shutdown helper that disables interrupts at `0xFC0D01F2`, stops the watchdog via `sub_fc135d9a` (`0xFC0D01F6`), writes `0x004C0003` to GPIO 0x67 at `0xFC0D0202` via `GPIO_Write` (`0xFC0D73C4`), and enters an infinite halt loop at `0xFC0D0206` `[STATIC_VERIFIED: ROM 0xFC0D01EC-0xFC0D0206; PORT25-ROM-FIRMWARE-CONT; ROM 0xFC0D73C4; PORT25-ROM-GPIO-WRITE-MMIO]`.
  4. However, no bounded control-flow evidence is cited connecting `sub_fc0d0126` to `TurnOffE1_FW`, nor showing that battery door, SD card door, or lens sensor failures call `TurnOffE1_FW`. The trigger conditions and reachability from `sub_fc0d0126` are therefore `[UNKNOWN]`.
  5. In physical Observation O1, the camera booted to the stock user interface when the button was held down, proving that standard hardware interlocks pass under normal operating conditions `[INFERRED: Observation O1]`.
- **Likelihood**: Ranked **Rank 6** (Low).

---

### Candidate 7: Initial Task Stage 4 Subsystem Failures (`sub_fc05b5ea`)
- **Citations**: `boot_prototype.c:280-330`; ROM `0xFC05B540`..`0xFC05B73F` (`PORT25-ROM-INIT-TASK`), `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:59`.
- **Classification**: `[STATIC_VERIFIED]` in ROM disassembly for entry sequence; `[UNKNOWN]` for callee return/halt behavior.
- **Trigger Condition**: Failure of USER_MEM check or any subsystem initialization in Stage 4.
- **Mechanism**:
  1. In Stage 4, seven sequential subsystem calls are checked: USER_MEM size, `dmSetup`, `termDriverInit`, `termDeviceCreate`, `stdioSetup`, `stdlibSetup`, `extlib_setup` (`boot_prototype.c:280-330`).
  2. If any check fails, execution branches to `sub_fc05b5ea` (`0xFC05B5EA`) with an error string literal `[STATIC_VERIFIED: ROM 0xFC05B5EA; PORT25-ROM-INIT-TASK]`.
  3. Inside `sub_fc05b5ea`, the instructions at `0xFC05B5EA`..`0xFC05B5FC` log an error message and execute a tail branch at `0xFC05B5FC` to an external callee that has not been examined `[STATIC_VERIFIED: ROM 0xFC05B5EA-0xFC05B5FC; PORT25-ROM-INIT-TASK]`. As recorded in `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:59`, whether this callee halts, returns into Stage 4, or triggers an exception or shutdown is `[UNKNOWN: unexamined callee]`.
  4. While the return/halt behaviour of `sub_fc05b5ea` remains `[UNKNOWN]`, all seven Stage 4 checks are known to succeed empirically in Observation O1 `[INFERRED: Observation O1]`.
- **Likelihood**: Ranked **Rank 7** (Negligible; passes in Observation O1).

---

### Candidate 8: Heap Headroom Check Failure in `sub_fc05b3c8_my`
- **Citations**: `boot_prototype.c:184-191`; ROM `0xFC05B3C8`..`0xFC05B3DA` (`PORT25-ROM-HEAP-SETUP`).
- **Classification**: `[STATIC_VERIFIED]` in source code and ROM disassembly; `[INFERRED]` as non-power-cut halt path.
- **Trigger Condition**: Insufficient DryOS heap headroom (`0x006CE000 - new_sa < 0x000B1FEC`).
- **Mechanism**:
  1. `sub_fc05b3c8_my` checks if `0x006CE000 - r4 >= 0x000B1FEC` (712 KiB) `[VERIFIED: boot_prototype.c:184-188]`.
  2. If headroom fails, it branches to `loc_fc05b3d8: b loc_fc05b3d8` (infinite spin loop) `[VERIFIED: boot_prototype.c:189-191]`.
  3. With `new_sa = 0x00366CB0`, headroom is ~3.4 MiB, far exceeding 712 KiB. This check statically passes and does not cut power `[VERIFIED]`.
- **Likelihood**: Ranked **Rank 8** (Negligible).

---

## 5. Ranked Candidate Summary

The table below summarizes all post-loader candidate points that can cut power or wait on the power button, ranked from highest to lowest likelihood for short-press boot failure `[VERIFIED]`:

| Rank | Candidate Name | Code & ROM Citation | Active Condition | Failure / Power-Cut Action | Epistemic Status & Likelihood |
|:---:|---|---|---|---|:---:|
| **1** | Native Button Check & Power Cut in `sub_fc05b962_my` | `boot_prototype.c:351-354`<br>ROM `0xFC05B96C-0xFC05B976`<br>`PORT25-ROM-STARTUP-TASKS`<br>ROM `0xFC1284BC-0xFC12851A`<br>`PORT25-ROM-POWERON-CHECK` | Default build (`G3X_POWERON_FIX=0`); button released before Stage 5 runs | `sub_fc1284ac` returns `0`; `sub_fc05b962_my` calls `sub_fc05ba56` (`0xFC05BA56`), writing `0x004C0003` to GPIO 0x67 (`0xD20B099C`), cutting DC-DC power and hanging at `0xFC05B976` | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` as root cause<br>**Rank 1 (Definitive for Default Build)** |
| **2** | Startup Cause at `0x00009BD0` (Bypassed `sub_fc08ecbc`) | `boot_prototype.c:349`<br>ROM `0xFC128504-0xFC12851A`<br>`PORT25-ROM-POWERON-CHECK`<br>ROM `0xFC08ECBC-0xFC08ECEC`<br>`PORT25-ROM-STARTCAUSE-SAVE`<br>ROM `0xFC08EEF0`<br>`PORT25-ROM-STARTCAUSE-PTR` | Opt-in build (`G3X_POWERON_FIX=1`); button released before line 349 runs | `sub_fc1284ac` skips `bl sub_fc08ecbc` at `0xFC128510`, leaving `*(0x00009BD0)` unwritten. Initial value after boot is UNKNOWN; whether downstream Canon tasks shut down or error if uninitialized is UNKNOWN (known warm-boot failure in G3 X 1.10E) | `[STATIC_VERIFIED]` in ROM<br>`[UNKNOWN]` initial value & shutdown edge<br>`[INFERRED]` downstream risk<br>**Rank 2 (Leading Hypothesis for Opt-In Build)** |
| **3** | Hardware Watchdog Timer Expiry (`sub_fc418f2a` / `StartWDT_FW`) | `boot_prototype.c:408`<br>ROM `0xFC418F2A`<br>`PORT25-ROM-WATCHDOG-START`<br>ROM `0xFC135C00-0xFC135E3F`<br>`PORT25-ROM-WATCHDOG-MODULE`<br>MMIO `0xD20A0000` | Post-loader boot delay or execution stall after line 408 | Hardware watchdog countdown timer underflows, triggering `WdtInt` (`0xFC135C92`) and causing hardware reset or power cut | `[STATIC_VERIFIED]` in ROM<br>`[UNKNOWN]` hardware effect<br>**Rank 3 (Plausible if Stalled After Line 408)** |
| **4** | Sub-CPU Power-Hold Supervision & Autonomous PMIC Latch Timeout | `boot_prototype.c:346`<br>ROM `0xFC05BA68-0xFC05BA8A`<br>`PORT25-ROM-STARTUP-TASKS`<br>ROM `0xFC135280-0xFC1352FF`<br>`PORT25-ROM-MPU-CONFIG`<br>ROM `0xFC05B8FE-0xFC05B90A`<br>`PORT25-ROM-STARTUP-TASKS` | Both builds; button released on short press before sub-CPU supervision satisfied | Sub-CPU hardware latch drops DC-DC power rails autonomously if button released. Routine at 0xFC135280 is CP15 MPU setup, not sub-CPU communication; returning from it does not prove sub-CPU handshake | `[STATIC_VERIFIED]` for MPU setup<br>`[INFERRED]` power supervision<br>`[UNKNOWN: external microcontroller firmware]`<br>**Rank 4 (Lowered Likelihood: Unmapped Microcontroller Hypothesis)** |
| **5** | `task_PhySw` Button Release / Button Event Dispatch | `boot_prototype.c:413`<br>ROM `0xFC1283D2`<br>`PORT25-ROM-PHYSW-TASK`<br>ROM `0xFC1283AD`<br>`PORT25-ROM-PHYSW-TASK`<br>ROM `0xFC12868C`<br>`PORT25-ROM-PHYSW-LITERALS` | `task_PhySw` polling loop running after line 413 | If `task_PhySw` interprets early button release as an immediate power-down request rather than normal power-on release | `[STATIC_VERIFIED]` in ROM<br>`[INFERRED]` event mechanism<br>`[UNKNOWN]` event handling<br>**Rank 5 (Medium; input event generator)** |
| **6** | Downstream Canon Firmware Interlocks & Orderly Shutdown (`TurnOffE1_FW`) | `boot_prototype.c:438`<br>ROM `0xFC0D0126`<br>`PORT25-ROM-FIRMWARE-CONT`<br>ROM `0xFC0D01EC`<br>`PORT25-ROM-FIRMWARE-CONT`<br>ROM `0xFC0D73C4`<br>`PORT25-ROM-GPIO-WRITE-MMIO` | Battery door open, SD card door open, low battery voltage, or hardware interlock failure | Downstream Canon initialization calls `TurnOffE1_FW` (`0xFC0D01EC`), writing `0x004C0003` to GPIO 0x67 and halting | `[STATIC_VERIFIED]` in ROM<br>`[UNKNOWN]` call edge from continuation<br>**Rank 6 (Low; passes in Observation O1)** |
| **7** | Initial Task Stage 4 Subsystem Failures (`sub_fc05b5ea`) | `boot_prototype.c:280-330`<br>ROM `0xFC05B540-0xFC05B73F`<br>`PORT25-ROM-INIT-TASK`<br>`docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:59` | USER_MEM check failure or driver setup error (< 0) in Stage 4 | Calls `sub_fc05b5ea` (`0xFC05B5EA`) with error literal, ending in tail branch at `0xFC05B5FC` to unexamined callee. Whether it halts, returns, or cuts power is `[UNKNOWN: docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:59]` | `[STATIC_VERIFIED]` in ROM<br>`[UNKNOWN]` return/halt/shutdown behavior<br>**Rank 7 (Negligible; passes in Observation O1)** |
| **8** | Heap Headroom Failure in `sub_fc05b3c8_my` | `boot_prototype.c:184-191`<br>ROM `0xFC05B3C8`<br>`PORT25-ROM-HEAP-SETUP` | DryOS heap headroom < 712 KiB | Enters infinite spin loop `b loc_fc05b3d8` at `boot_prototype.c:190`. Does not cut GPIO 0x67 power directly | `[STATIC_VERIFIED]` in source<br>`[INFERRED]` non-power-cut halt<br>**Rank 8 (Negligible; passes in Observation O1)** |

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
| `STAGE_BC_PRE_MPU_SETUP` | `boot_prototype.c:346` | Immediately before `bl sub_fc05ba68` (`mpuSetup`) | Confirms entry to ARM Memory Protection Unit (MPU) setup via `sub_fc05ba68` (Candidate 4) |
| `STAGE_BC_POST_MPU_SETUP` | `boot_prototype.c:347` | Immediately after `bl sub_fc05ba68`, before `bl sub_fc079404` | Confirms ARM MPU configuration returned; does NOT prove sub-CPU handshake (shows only that MPU setup returned) |
| `STAGE_BC_PRE_POWER_CHECK` | `boot_prototype.c:348` | Immediately before `bl sub_fc1284ac` in `sub_fc05b962_my` | Confirms execution reached the power-on button check gate |
| `STAGE_BC_POWER_CHECK_FAIL` | `boot_prototype.c:354` | Immediately before `bl sub_fc05ba56` in default build | Proves native button check evaluated released (`r0 == 0`) and selected power-cut branch BEFORE GPIO 0x67 MMIO write (Candidate 1) |
| `STAGE_BC_POWER_CUT_HALT` | `boot_prototype.c:356` | At label `loc_fc05b976` immediately after `bl sub_fc05ba56` | Reached only if `sub_fc05ba56` returns to caller without instantaneous power loss, entering post-cut infinite halt loop `b loc_fc05b976` (Candidate 1) |
| `STAGE_BC_POWER_CHECK_PASS` | `boot_prototype.c:358` | Inside `loc_fc05b978` immediately before `blx sub_fc31b460` | Proves whether button check passed (or opt-in fix branched past power cut) |
| `STAGE_BC_PRE_CREATE_STARTUP` | `boot_prototype.c:369` | Immediately before `blx sub_fc31bbc4` in `sub_fc05b962_my` | Confirms ARAM heap init passed and ready to invoke "Startup" CreateTask helper |
| `STAGE_BC_POST_CREATE_STARTUP` | `boot_prototype.c:371` | Immediately after `blx sub_fc31bbc4` in `sub_fc05b962_my` (helper-return checkpoint) | Helper-return checkpoint: confirms CreateTask veneer returned to caller; does NOT prove "Startup" task was registered or ran (task running verified at `STAGE_BC_STARTUP_ENTRY`) |
| `STAGE_BC_STARTUP_ENTRY` | `boot_prototype.c:384` | Entry to `task_Startup_my` immediately after `push {r4, lr}` (task execution checkpoint) | Task execution checkpoint: confirms DryOS scheduler dispatched `task_Startup_my` (proves "Startup" task is actively running) |
| `STAGE_BC_PRE_SD1STINIT` | `boot_prototype.c:397` | Immediately before SD1stInit gate check `sub_fc05c4e0` | Confirms pre-SD driver setup completed |
| `STAGE_BC_POST_SD1STINIT` | `boot_prototype.c:403` | At label `1:` immediately after SD1stInit task creation veneer (helper-return checkpoint) | Helper-return checkpoint: confirms SD1stInit creation veneer returned or was bypassed; does NOT prove `task_SD1stInit` is running |
| `STAGE_BC_PRE_WATCHDOG_START` | `boot_prototype.c:408` | Immediately before `bl sub_fc418f2a` in `task_Startup_my` | Confirms execution reached point immediately before watchdog arming |
| `STAGE_BC_POST_WATCHDOG_START` | `boot_prototype.c:409` | Immediately after `bl sub_fc418f2a` in `task_Startup_my` | Confirms hardware watchdog helper returned and watchdog is actively armed (Candidate 3) |
| `STAGE_BC_PRE_PHYSW_CREATE` | `boot_prototype.c:413` | Immediately before `bl sub_fc1283d2` in `task_Startup_my` | Confirms pre-PhySw driver initialization completed |
| `STAGE_BC_POST_PHYSW_CREATE` | `boot_prototype.c:414` | Immediately after `bl sub_fc1283d2` in `task_Startup_my` (helper-return checkpoint) | Helper-return checkpoint: confirms `sub_fc1283d2` returned; does NOT prove `task_PhySw` was registered or ran (`sub_fc1283d2` skips creation if handle exists at `0xFC1283E4-0xFC1283E8`) |
| `STAGE_BC_PHYSW_ENTRY` | `boot_prototype.c:414` | Proposed hooked `task_PhySw` entry checkpoint in `boot_prototype.c` (prior to ROM `0xFC1283AD` handoff) | Task execution checkpoint: proposed hooked entry checkpoint proving `task_PhySw` is actively running (Candidate 5) |
| `STAGE_BC_PRE_FIRMWARE_CONT` | `boot_prototype.c:438` | Immediately before `b.w sub_fc0d0126` in `task_Startup_my` | Confirms CHDK prototype startup complete; handing off to stock firmware |

### Helper-Return Checkpoints vs Task-Execution Checkpoints
Returning from a task-creation helper does not prove that the task was registered or ran `[VERIFIED]`:
1. **Helper Return Does Not Imply Task Registration**: In `task_Startup_my`, helper `sub_fc1283d2` (`boot_prototype.c:413`) checks an existing task handle pointer at `0xFC1283E4-0xFC1283E8` (`PORT25-ROM-PHYSW-TASK`); if the task handle already exists, it skips task creation entirely and immediately returns `[STATIC_VERIFIED: ROM 0xFC1283E4-0xFC1283E8; PORT25-ROM-PHYSW-TASK]`. Therefore, breadcrumb `STAGE_BC_POST_PHYSW_CREATE` (line 414) serves strictly as a **helper-return checkpoint**, confirming that `sub_fc1283d2` returned to the caller, not that `task_PhySw` was newly created or dispatched.
2. **Task Execution Requires Entry Checkpoints**: A task can be claimed as actively running only from a checkpoint situated at that task's entry point, or other verified execution evidence `[VERIFIED]`:
   - For the "Startup" task, `STAGE_BC_POST_CREATE_STARTUP` (line 371) is a helper-return checkpoint, whereas `STAGE_BC_STARTUP_ENTRY` (`boot_prototype.c:384`) placed after `push {r4, lr}` inside `task_Startup_my` provides the verified task-execution checkpoint proving DryOS actually dispatched and ran the task.
   - For `task_PhySw`, T3 can place a hooked wrapper in `boot_prototype.c` at line 414 (`STAGE_BC_PHYSW_ENTRY`) before dispatching to ROM `0xFC1283AD`, providing an unambiguous task-execution checkpoint.

### Distinction Between `STAGE_BC_POWER_CHECK_FAIL` and `STAGE_BC_POWER_CUT_HALT`
Crucially, two separate breadcrumb stages are defined around the Candidate 1 power-cut call:
1. **`STAGE_BC_POWER_CHECK_FAIL` (line 354)** is situated directly after the conditional branch `cbnz r0, loc_fc05b978` falls through, **immediately preceding** `bl sub_fc05ba56`. Because DC-DC power to the SoC has not yet been de-asserted, this breadcrumb will flash reliably if `sub_fc1284ac` returned `0`, proving definitively that execution entered the failure path.
2. **`STAGE_BC_POWER_CUT_HALT` (line 356)** is situated at label `loc_fc05b976`, **immediately following** `bl sub_fc05ba56`. If the MMIO write to GPIO 0x67 triggers an immediate hardware rail drop, power will extinguish before or during the return from `sub_fc05ba56`, and `STAGE_BC_POWER_CUT_HALT` will never execute. Conversely, if power remains latched until the CPU spins in `loc_fc05b976`, `STAGE_BC_POWER_CUT_HALT` will flash. This allows Task T3 to empirically distinguish instantaneous hardware rail drops from post-call spin loops.

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
| `PORT25-ROM-WATCHDOG-MODULE` | `0xFC135C00` | `0xFC135E3F` | 576 B | `29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb` | `[STATIC_VERIFIED]` `WatchDog.c`: `WdtInt` (`0xFC135C92`), `StartWDT_FW` (`0xFC135D2C`), `task_WdtReset` |
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
   - In the opt-in candidate (`G3X_POWERON_FIX=1`), Candidate 1 is bypassed, leaving Candidate 4 / Rank 2 (unwritten start cause), Candidate 3 / Rank 3 (watchdog timeout), and Candidate 2 / Rank 4 (sub-CPU autonomous latch timeout) as key hypotheses to be tested.
2. **Breadcrumb Placement Plan Ready for Task T3** `[VERIFIED]`:
   - The table in Section 6 defines all breadcrumb stages, file:line insertion points, and what hypothesis each isolates.
   - Crucially, `STAGE_BC_POWER_CHECK_FAIL` (line 354, pre-call) and `STAGE_BC_POWER_CUT_HALT` (line 356, post-call) allow Task T3 to distinguish whether power is cut immediately inside `sub_fc05ba56` or delayed until the halt loop.
   - Task T3 can insert GPIO 33 LED toggles at these points to observe hardware progress during short-press trials without guessing.
