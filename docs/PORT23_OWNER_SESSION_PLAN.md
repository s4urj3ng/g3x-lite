# PORT-23 T3: Owner Session Plan — Localizing Post-Loader Shutdown (GM1.10C)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/PORT21_RAM_LIFETIME.md:3]`
- **Purpose**: Diagnostic execution plan for the next camera owner session to localise the post-loader shutdown in at most two physical power-ons `[INFERRED]`
- **Evaluation Mode & Safety**: Phase 0 Read-Only regarding firmware and hardware (`docs/SAFETY.md:1-8`). STRICT NO-GO on firmware flashing, camera connection, unreviewed scripts, or execution without owner protocol `[VERIFIED: docs/SAFETY.md:1-8; AGENTS.md:19-25]`
- **Inputs & Citations**:
  - T1 Output: `docs/PORT23_POWER_SUPERVISION.md` and `docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json` (Commit `183dc7eaa9183889a6817f18eedd97e2a192d9e0`) `[VERIFIED: git commit 183dc7e]`
  - T2 Output: `docs/PORT23_LED_BREADCRUMBS.md`, `tools/build_candidate_port23_breadcrumb.py`, and breadcrumb platform files (Commit `59ca5f51226566c10607dbf0776980cdaebef25c`) `[VERIFIED: git commit 59ca5f5]`
  - Owner Physical Trial Results (2026-11-01) `[OWNER-REPORTED: milestone task brief; docs/PORT23_POWER_SUPERVISION.md:17-23]`
- **Epistemic Classifications** `[VERIFIED: AGENTS.md:3; docs/PORT23_POWER_SUPERVISION.md:6-11]`:
  - `[VERIFIED]`: Proven directly by tracked repository files, build outputs, or physical hardware trials.
  - `[STATIC_VERIFIED]`: Directly confirmed from static ROM disassembly within approved manifest slices (`docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json`).
  - `[INFERRED]`: Deductions from verified static code, hardware observations, and execution sequences.
  - `[UNKNOWN]`: Unobserved runtime state or unmapped hardware behavior.
  - `[OWNER-REPORTED]`: Observations reported directly by the camera owner during physical sessions.

---

## 1. Current Reading & Hardware Evidence

During the physical hardware trials conducted on 2026-11-01, the camera owner evaluated candidate builds on an SD card formatted as FAT32 with `BOOTDISK` at offset `0x1E0` and `SCRIPT` at offset `0x1F0`, with the SD card write-protect switch set to **LOCKED** `[OWNER-REPORTED: milestone task brief; docs/PORT19_BOOTDISK_VBR.md:17-22]`. Four primary results were established:

### 1.1 Owner Trial Results (2026-11-01)

1. **Owner Result (a) — PORT-20 LED Build (`0x06000000` Stall)** `[OWNER-REPORTED: milestone task brief; docs/PORT23_POWER_SUPERVISION.md:20]`:
   - **Target Binary**: `candidate_port2a/DISKBOOT.BIN` generated with `loader_entry_led.S` and loop constant `0x06000000` (100,663,296 busy-wait iterations) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:31-37]`.
   - **`DISKBOOT.BIN` SHA-256**: `757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286` `[VERIFIED: tests/test_port20_led_candidate.py:27; docs/PORT20_LED_CANDIDATE.md:71]`.
   - **Observation**: The rear green status LED lit for a few seconds, then went dark. The camera did not come up (LCD backlight completely off, no UI). A second power button press repeated the identical sequence `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:20]`.
2. **Owner Result (b) — Short-Delay LED Build (`0x00600000` Stall)** `[OWNER-REPORTED: milestone task brief; docs/PORT23_POWER_SUPERVISION.md:21]`:
   - **Target Binary**: Shortened delay variant with loop constant `0x00600000` (6,291,456 busy-wait iterations, 1/16th duration) `[VERIFIED: docs/PORT23_POWER_SUPERVISION.md:21]`.
   - **`DISKBOOT.BIN` SHA-256**: `3922ddbecab362e8e13dc76bedd1758828fc91a2934310d3abb7d7d70f4e44ac` `[VERIFIED: docs/PORT23_POWER_SUPERVISION.md:21]`.
   - **Observation**: The green status LED flashed briefly, then the camera stayed dark and did not come up. The LCD backlight was completely off, indicating an unpowered state rather than an active black screen `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:21]`.
3. **Owner Result (c) — Control: PORT-19 Default Build (No LED Prologue, Zero Delay)** `[OWNER-REPORTED: milestone task brief; docs/PORT23_POWER_SUPERVISION.md:22]`:
   - **Target Binary**: Unmodified baseline candidate produced by `tools/build_candidate_port2a.py` with zero LED code and zero delay `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:362; docs/PORT20_LED_CANDIDATE.md:68]`.
   - **`DISKBOOT.BIN` SHA-256**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:362; docs/PORT19_GO_NOGO.md:16; docs/PORT23_POWER_SUPERVISION.md:22]`.
   - **Observation**: Pressing the Playback button did not bring the camera up. Only repeated or long power-button presses sometimes brought up the stock UI `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:22]`.
4. **Owner Result (d) — LED Polarity Confirmed on Hardware** `[VERIFIED: hardware trial 2026-11-01; docs/PORT23_LED_BREADCRUMBS.md:6-7; docs/PORT23_POWER_SUPERVISION.md:33]`:
   - **GPIO MMIO Address**: `0xD20B0884` (pin 33, rear green status LED) `[STATIC_VERIFIED: ROM 0xFC0D73C0-0xFC0D74BF; PORT23-ROM-GPIO-WRITE-MMIO]`.
   - **LED ON Action**: Writing `0x004D0002` to `0xD20B0884` turns the rear green LED **ON** `[VERIFIED: hardware trial 2026-11-01]`.
   - **LED OFF Action**: Writing `0x004C0003` to `0xD20B0884` turns the rear green LED **OFF** `[VERIFIED: hardware trial 2026-11-01]`.

### 1.2 Core Deductions & Superseded Theories

1. **The Stall-Length Theory is SUPERSEDED** `[VERIFIED by owner results a-c; docs/PORT23_POWER_SUPERVISION.md:26-30]`:
   - Prior to physical testing, it was hypothesized that a multi-second busy wait in `loader_entry_led.S` (`0x06000000` cycles) exceeded a hardware power supervision timer during the stall itself `[INFERRED: docs/PORT20_LED_CANDIDATE.md:172-180]`.
   - However, reducing the delay 16-fold in Result (b) (`0x00600000` cycles, ~100–150 ms) still produced immediate power-off `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:27]`.
   - Furthermore, Result (c) (zero delay loop, zero LED code) also failed to boot on normal taps and failed on Playback presses `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:28]`.
   - Therefore, the stall length is NOT the cause of shutdown `[VERIFIED by owner results a-c]`. The stall-length theory is decisively superseded `[VERIFIED]`.
2. **DISKBOOT Execution is Conclusively Proven** `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:31-36]`:
   - In both Results (a) and (b), the rear green LED physically illuminated `[OWNER-REPORTED]`.
   - Stock GM1.10C ROM never writes `0x004D0002` to `0xD20B0884` during early boot `[STATIC_VERIFIED: ROM 0xFC0D73C0-0xFC0D74BF; PORT23-ROM-GPIO-WRITE-MMIO]`.
   - Therefore, `StartDiskboot` successfully validated `BOOTDISK`, loaded `A/DISKBOOT.BIN` from the locked SD card into RAM, descrambled DancingBits, and jumped to loader entry `0x8001` `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:35]`.
   - Early boot rejection (Hypothesis H1) is decisively refuted for initial entry `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:36]`.
3. **Failure Occurs Post-Loader-Entry** `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:29-30]`:
   - Both builds enter the loader, and the camera then ends up off `[VERIFIED by owner results a-c]`.
   - The earlier stock-UI start observed in PORT-19 Run 1 was most likely a retry or the result of a long button press, rather than an uninterrupted first-boot normal sequence `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:49, 224-227, 264-267]`.

---

## 2. Post-Loader Shutdown Hypotheses & Retry Behavior (from T1)

From the firmware disassembly analysis in `docs/PORT23_POWER_SUPERVISION.md:38-50, 271-314`, four candidate mechanisms explain why the camera powers off or resets after `StartDiskboot` transfers control to `0x8001`:

### 2.1 Ranked Post-Loader Failure Hypotheses

| Rank | Hypothesis | Mechanism & Impact | Disassembly & Firmware Proof | Epistemic Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Power-On Check (`sub_fc1284ac`) Re-entry Failure in Stage 5 (`sub_fc05b962_my`)** | In stock boot, `sub_fc1284ac` runs BEFORE `task_Startup` and before `StartDiskboot`. Candidate `boot_prototype.c` re-runs `sub_fc1284ac` a SECOND time. If the user performed a normal brief tap, the button is released when `sub_fc1284ac` runs, returning `0`. Function `sub_fc05ba56` writes `0x004C0003` to GPIO 0x67 (power-hold), cutting DC-DC rails and hanging in `b .` | ROM `0xFC1284AC-0xFC12851A` (samples GPIO 0x97, 0x98, 0x88, 0x02; returns 0 if released); ROM `0xFC05B970-0xFC05B976` (calls `sub_fc05ba56` if r0 == 0); ROM `0xFC05BA56` (writes `0x004C0003` to GPIO 0x67 / MMIO `0xD20B099C`); candidate `boot_prototype.c:334, 342-356` | `[STATIC_VERIFIED / INFERRED: docs/PORT23_POWER_SUPERVISION.md:43-50, 277, 284-293]` |
| **2** | **External Sub-CPU Power-Hold Supervision & Hardware Handshake Timeout** | Canon DIGIC 6 cameras rely on an external power management microcontroller (sub-CPU). If the sub-CPU requires continuous serial communication (SioDrv / DcdcDrv) or a maintained hardware button hold, dropping the button or resetting I/O controllers during soft restart could cause the sub-CPU to drop the DC-DC rails autonomously | ROM `0xFC05B8FE-0xFC05B90A` (SioDrv / DcdcDrv initialization); sub-CPU internal firmware resides outside `PRIMARY.BIN` | `[INFERRED / UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:278, 294-301]` |
| **3** | **SD Bus Desynchronization / Peripheral Re-init Error** | Abrupt power cuts during SD bus transactions desynchronize the SD host controller or card state machine | ROM `0xFC05BC04-0xFC05BC1C` (SD bus initialization and VBR check) | `[INFERRED / UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:279, 302-307]` |
| **4** | **Hardware Watchdog (`0xD20A0000`) Expiry** | Hardware watchdog timer expires during loader execution | ROM `0xFC05B90E, 0xFC05B922` (sub_fc418f2a starts watchdog strictly 18 instructions AFTER StartDiskboot returns). Watchdog is NOT running during StartDiskboot or loader | `[UNKNOWN: CONTRADICTED for Pre-StartDiskboot; docs/PORT23_POWER_SUPERVISION.md:38-41, 280, 308-314]` |

### 2.2 T1 Findings on Whether a Later Power-On Skips StartDiskboot

T1 analyzed two distinct mechanisms explaining why subsequent power-on attempts sometimes reached the stock UI `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:264-267]`:

1. **Mechanism A (User Button-Hold Duration)** `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:265]`:
   - On a retry, the owner presses the Power button longer or more firmly.
   - If the button is held continuously through handoff, loader, core boot, and initial task until `sub_fc1284ac` executes in Stage 5, GPIO 0x97 is sampled as held (`1`).
   - `sub_fc1284ac` returns `1`, allowing `sub_fc05b962_my` to branch to `loc_fc05b978` (`boot_prototype.c:356`), create `task_Startup_my`, and branch to `sub_fc0d0126` (`boot_prototype.c:438`), presenting the stock UI `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:49, 255-257]`.
   - Under Mechanism A, `StartDiskboot` is **NOT skipped**; rather, candidate execution completes through to stock continuation.
2. **Mechanism B (SD Bus Desynchronization Skips StartDiskboot on Retry)** `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:266]`:
   - If the previous attempt cut power abruptly while the SD controller was active, the card or host interface state machine can be left in an unclean or busy state.
   - On an immediate retry, `StartDiskboot`'s SD check (`sub_fc05c4e0` / `sub_fc37aea6` at `0xFC05BC18`) fails or times out `[STATIC_VERIFIED: ROM 0xFC05BC04-0xFC05BC1C; PORT23-ROM-STARTDISKBOOT]`.
   - On failure, `StartDiskboot` returns cleanly to `task_Startup` at `0xFC05BC34` -> `0xFC05B912`, skipping `DISKBOOT.BIN` entirely and booting pure stock firmware `[STATIC_VERIFIED: ROM 0xFC05BC34-0xFC05BC38; PORT23-ROM-STARTDISKBOOT] [STATIC_VERIFIED: ROM 0xFC05B912; PORT23-ROM-STARTUP-TASKS]`.
   - Under Mechanism B, `StartDiskboot` is **cleanly bypassed** due to transient SD failure.
3. Conclusively distinguishing Mechanism A from Mechanism B on a specific physical retry is `[UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:267]` without diagnostic instrumentation.

---

## 3. Session Protocol & Steps (At Most Two Power-Ons)

The objective of this session is to localise the failure point in at most two power-ons by first testing the **terminal loader boundary (`pre_jump`)** and then either discriminating the core root cause or bisecting the loader `[INFERRED]`.

### 3.1 Overview of Candidate Breadcrumb Checkpoints (from T2)

All breadcrumb candidate binaries are generated with `tools/build_candidate_port23_breadcrumb.py` and documented in `docs/PORT23_LED_BREADCRUMBS.md:39-116` `[VERIFIED]`:

| Stage Name | Opt-In Flag | Source Location | Execution Milestone | `DISKBOOT.BIN` SHA-256 |
| :--- | :--- | :--- | :--- | :---: |
| `loader_entry` | `--stage loader_entry` | `loader_entry_breadcrumb.S:36` | Entry `_start` at `0x8000` reached | `60a78e40127d7aa2b05178a27d834545817ded7618fef9f26637b7789d92fe24` `[VERIFIED]` |
| `before_copy` | `--stage before_copy` | `loader_main_breadcrumb.c:37` | `check_compat` passed (`0x32A8`), stack setup | `b2a2d55e25cfd422895854d47f0d186874df9bb3450cfc46a5be045179466852` `[VERIFIED]` |
| `after_copy` | `--stage after_copy` | `loader_main_breadcrumb.c:52` | `core_copy` complete (116,816 B relocated) | `0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df` `[VERIFIED]` |
| `witness_entry` | `--stage witness_entry` | `loader_main_breadcrumb.c:59` | Alias of `after_copy` (identical hash) | `0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df` `[VERIFIED]` |
| `witness_write` | `--stage witness_write` | `loader_main_breadcrumb.c:79` | Boot witness struct written to `0x0035F7A0` | `1fcad53e31f18c378b84918b65f9365e7400185423ad7dbeac62ac04555e3de8` `[VERIFIED]` |
| `pre_jump` | `--stage pre_jump` | `loader_main_breadcrumb.c:117` | Cache maintenance complete, `cpsid if` enforced, handoff via `bx r0` to `0x003489B5` imminent | `abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75` `[VERIFIED]` |

In all documented stage builds, delay is set to 0 (`LED_BREADCRUMB_DELAY` not defined): the LED writes `0x004D0002` to `0xD20B0884` and execution proceeds immediately without blocking `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:41, 140]`.

---

### 3.2 Power-On 1: Terminal Loader Checkpoint (`pre_jump`)

Power-On 1 tests whether execution successfully completes the entire loader sequence and reaches the handoff branch to relocated core code `0x003489B5` `[INFERRED]`.

- **Build Configuration**:
  - **Tool Command**: `python3 tools/build_candidate_port23_breadcrumb.py --stage pre_jump --out-dir candidate_breadcrumb/pre_jump` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:110]`
  - **Build Flag**: `--stage pre_jump` (defines macro `LED_BREADCRUMB_PRE_JUMP`) `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:50, 110]`
  - **`DISKBOOT.BIN` SHA-256**: `abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:115]`
  - **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:114]`
  - **Delay Iterations**: `0` (default; non-blocking) `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:41, 140]`
- **Card Setup**:
  - SD card formatted FAT32, `BOOTDISK` string at offset `0x1E0`, `SCRIPT` string at offset `0x1F0` `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:17-22]`.
  - Copy `candidate_breadcrumb/pre_jump/DISKBOOT.BIN` to SD card root directory `[VERIFIED: docs/PORT19_GO_NOGO.md:20]`.
  - Set SD card write-protect lock switch to **LOCKED** `[OWNER-REPORTED: milestone task brief]`.
- **Owner Action**:
  - Insert locked card and freshly charged battery.
  - Perform a **normal brief tap** of the Power button (~100–250 ms) `[INFERRED]`.
- **Expected Breadcrumb Sequence & Stage Mapping**:
  1. `0x8000`: Loader entry `_start` sets `sp = 0x8000` and branches to `my_restart` `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_entry_breadcrumb.S:57-58]`.
  2. `check_compat()` verifies GM1.10C model ID `0x32A8` `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:35]`.
  3. `core_copy()` copies 116,816 bytes from loader RAM to DRAM `0x003489B4` `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:50]`.
  4. Boot witness struct written to `0x0035F7A0` `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:65-78]`.
  5. Decoupled native cache maintenance executes: DCCISW (`0xFC127AB1`) + DSB, then ICIALLU/BPIALL (`0xFC127B09`) + ISB `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:98-111]`.
  6. `cpsid if` disables IRQ and FIQ `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:114]`.
  7. **CHECKPOINT FIRES**: `str r1, [r0]` writes `0x004D0002` to MMIO `0xD20B0884` (Green LED ON) `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:118-120]`.
  8. `bx r0` branches to relocated core entry `0x003489B5` `[VERIFIED: chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:136]`.
- **What to Watch**:
  - **LED Pattern**: Does the rear green LED light up?
    - *Brief Flash (~10–100 ms) then dark*: `pre_jump` was reached! Execution entered relocated core, where a subsequent power-cut killed power rails `[INFERRED]`.
    - *Solid Green*: Camera hung after `pre_jump` with power rails intact `[INFERRED]`.
    - *Stays Dark*: Execution halted inside the loader before `pre_jump` `[INFERRED]`.
  - **LCD Backlight**: Backlight completely unpowered/dark vs dimly glowing black screen.
  - **Time to Dark**: Time from button press until LED goes dark (estimated 50–150 ms if power cut).

---

### 3.3 Power-On 2: Conditional Discrimination Run

The selection of Power-On 2 depends strictly on the observation from Power-On 1:

#### Branch A: Power-On 1 Showed Green LED Flash at `pre_jump`
If the green LED flashed in Power-On 1, the entire loader is 100% verified. The failure is strictly post-loader in core execution. Power-On 2 immediately tests **Hypothesis Rank 1 (`sub_fc1284ac` Power-On Check Re-entry Failure)** `[INFERRED]`.

- **Power-On 2A — Long Power-Button Hold Trial**:
  - **Target Binary**: Use the exact same `pre_jump` build (`abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75`) or the default baseline build (`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) `[VERIFIED]`.
  - **Card Setup**: SD card locked, FAT32 `[OWNER-REPORTED]`.
  - **Owner Action**: Press and **HOLD the Power button continuously for 3.0 seconds** (do not release upon feeling tactile click; maintain firm pressure) `[INFERRED]`.
  - **Discrimination Criteria**:
    - *Camera stays powered on and boots to stock UI*: Conclusively PROVES **Rank 1 (`sub_fc1284ac` Power-On Check Re-entry Failure)** `[STATIC_VERIFIED / INFERRED: docs/PORT23_POWER_SUPERVISION.md:43-50, 255-257]`. Holding the button maintained GPIO 0x97 active (`1`), passing the second `sub_fc1284ac` check in `sub_fc05b962_my` and preventing `sub_fc05ba56` from cutting power `[INFERRED]`.
    - *Camera still cuts power and goes dark within ~100 ms despite holding button*: Conclusively points to **Rank 2 (External Sub-CPU Hardware Handshake Timeout)** `[INFERRED / UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:278, 294-301]`.

#### Branch B: Power-On 1 Showed NO Green LED (Stays Completely Dark)
If the LED never lit in Power-On 1, execution halted inside the loader before `pre_jump`. Power-On 2 performs a midpoint bisection of the loader at **Stage 3 (`after_copy`)** `[INFERRED]`.

- **Power-On 2B — Midpoint Loader Bisection (`after_copy`)**:
  - **Tool Command**: `python3 tools/build_candidate_port23_breadcrumb.py --stage after_copy --out-dir candidate_breadcrumb/after_copy` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:80]`
  - **Build Flag**: `--stage after_copy` (defines macro `LED_BREADCRUMB_AFTER_COPY`) `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:47, 80]`
  - **`DISKBOOT.BIN` SHA-256**: `0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:85]`
  - **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:84]`
  - **Card Setup**: SD card locked, FAT32 `[OWNER-REPORTED]`.
  - **Owner Action**: Normal brief tap of Power button `[INFERRED]`.
  - **Discrimination Criteria**:
    - *Green LED flashes*: `check_compat()` and `core_copy()` (116,816 B relocation) succeeded! The loader failure is strictly located between `after_copy` and `pre_jump` (in native cache routines `0xFC127AB1` / `0xFC127B09` or witness write) `[INFERRED]`.
    - *Green LED stays dark*: Failure occurs before `after_copy`. Since loader entry `0x8000` is proven to run, failure is strictly in `check_compat()` (model ID mismatch `0x32A8`) or in `core_copy()` `[INFERRED]`.

---

### 3.4 How to Distinguish Power-Off from a Hang or a Reset

| Characteristic | Clean Power-Off (DC-DC De-asserted) | System Hang / Freeze | Hardware or Software Reset |
| :--- | :--- | :--- | :--- |
| **LCD Backlight State** | Completely DARK and unpowered (no edge illumination or panel glow) `[OWNER-REPORTED: docs/PORT23_POWER_SUPERVISION.md:21]` | If hang is early: dark. If hang is after LCD init: backlight glows (black screen) `[INFERRED]` | Backlight flickers or remains uninitialized `[INFERRED]` |
| **LED Behavior** | Green LED flashes briefly (~20–100 ms) while rails are up, then turns OFF when rails collapse `[OWNER-REPORTED]` | If checkpoint passed: green LED remains **permanently illuminated** (solid green) `[INFERRED]` | Green LED or power LED cycles repeatedly (periodic blinks) `[INFERRED]` |
| **System Power Rails** | Main DC-DC converters shut down; GPIO 0x67 de-asserted via `0x004C0003` `[STATIC_VERIFIED: ROM 0xFC05BA56]` | Power rails remain energized; camera draws continuous battery current `[INFERRED]` | Rails toggle or CPU reboots into reset vector `0xFC02000C` `[STATIC_VERIFIED: ROM 0xFC02000C]` |
| **Recovery Requirement** | Camera responds to subsequent physical Power button press `[OWNER-REPORTED]` | Requires **physical battery pull** to recover `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:12]` | Continues boot cycling until battery is removed `[INFERRED]` |

---

## 4. Decision Table

| Last Breadcrumb Seen | Power-On 1 Result (`pre_jump`) | Power-On 2 Result | Failing Stage / Mechanism | Root Cause Classification | Next Host-Side Step |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pre_jump`** | Green LED flash (~50 ms), then power-off | **2A**: 3s hold boots to stock UI | Stage 5 startup check: `sub_fc1284ac` returns 0 on brief tap, calling `sub_fc05ba56` | **Rank 1**: Button release cuts power via GPIO 0x67 `[STATIC_VERIFIED / INFERRED]` | PORT-24 Remediation: Patch `sub_fc05b962_my` in `boot_prototype.c` to bypass `sub_fc1284ac` (force `r0 = 1`), matching sister port G3 X 1.10E `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:344-348]` |
| **`pre_jump`** | Green LED flash (~50 ms), then power-off | **2A**: 3s hold still powers off within ~100 ms | Sub-CPU PMIC hardware power supervision drops rails independently of button hold | **Rank 2**: Sub-CPU hardware handshake timeout `[INFERRED / UNKNOWN]` | Investigate sub-CPU SIO/DCDC communication sequence prior to `task_Startup` |
| **`pre_jump`** | Green LED remains **solid ON**, camera hung | *(Not needed)* | reloc core entry (`startup` at `0x003489B4`) hangs in vector copy or BSS zeroing | Core execution fault / infinite loop `[INFERRED]` | Audit core startup instructions and memory map (`candidate_main.map`) |
| **`after_copy`** | Dark in Power-On 1 | **2B**: Green LED flash | Cache sync (`0xFC127AB1` / `0xFC127B09`) or boot witness write at `0x0035F7A0` | Loader stage 4–6 fault `[INFERRED]` | Generate differential candidate (`--stage witness_write`) to isolate cache routine from witness store |
| **`before_copy`** | Dark in Power-On 1 | **2B**: Dark in Power-On 2B | `check_compat()` (`0x32A8`) or `core_copy()` inside `my_restart` | Loader stage 2–3 fault `[INFERRED]` | Generate `before_copy` candidate (`b2a2d55e...`) to test `check_compat` platform ID check |
| **None** | Dark in Power-On 1 | Dark across all candidates | ROM `StartDiskboot` fails to execute `DISKBOOT.BIN` | Transient SD bus desync (Mechanism B) or corrupted card file | Re-verify SD card VBR marker (`BOOTDISK`) and re-check file SHA-256 on host `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:17-22]` |

---

## 5. Stop Conditions & Recovery Plan

### 5.1 Immediate Stop Conditions

The trial must be immediately aborted if any of the following occur `[VERIFIED: docs/SAFETY.md:1-8]`:
1. The camera emits any abnormal heat, odor, or audible high-frequency noise.
2. The lens motor or shutter actuates unexpectedly or cycles erratically.
3. The rear green LED flickers continuously in an unmanaged rapid loop (potential boot loop).
4. Physical battery voltage drops below nominal threshold.

### 5.2 Verified Recovery Procedure

If the camera powers off, hangs, or fails to boot, execute the verified recovery sequence `[VERIFIED: hardware trial 2026-11-01; docs/PORT21_OWNER_SESSION_PLAN.md:12]`:

1. **Card Unlock or Removal** `[VERIFIED: hardware trial 2026-11-01]`:
   - Eject the SD card from the camera.
   - Slide the physical write-protect switch to the **UNLOCKED** (up) position.
2. **Capacitor Discharge / Quiescent Reset** `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:12]`:
   - Remove the rechargeable battery from the camera battery compartment.
   - Leave the battery compartment open and unpowered for at least **10 seconds** to allow decoupling capacitors to fully discharge and reset external PMIC / sub-CPU state registers.
3. **Battery Re-insertion**:
   - Re-insert the fully charged battery and securely close the battery door.
4. **Normal Stock Start Verification** `[VERIFIED: hardware trial 2026-11-01]`:
   - Insert the UNLOCKED SD card (or power on with no card inserted).
   - Press the Power button.
   - **Verification**: The camera boots normally into the stock Canon UI, lens extends, LCD backlight turns on, and full camera functionality is restored `[VERIFIED: hardware trial 2026-11-01]`.

---

## 6. Machine-Readable Report-Back Template

The owner copies and completes this template for each power-on trial, returning the filled block for automated processing.

### 6.1 YAML Format Template

```yaml
session_report:
  session_id: "PORT23-SESSION-20261101"
  camera_model: "Canon PowerShot G3 X"
  firmware_version: "GM1.10C"
  platform_id: "0x32A8"
  runs:
    - power_on_index: 1
      build_stage: "pre_jump"
      build_flag: "--stage pre_jump"
      diskboot_sha256: "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75"
      card_filesystem: "FAT32"
      card_lock_state: "LOCKED"
      bootdisk_vbr_present: true
      script_vbr_present: true
      button_pressed: "POWER"
      button_action: "brief_tap"
      button_hold_approx_ms: 200
      led_observed: "flash_brief"
      led_approx_duration_ms: 50
      lcd_backlight_state: "off_unpowered"
      time_to_dark_ms: 100
      outcome: "power_off"
      notes: "Green LED flashed once briefly, camera remained completely off with dark backlight"

    - power_on_index: 2
      build_stage: "pre_jump"
      build_flag: "--stage pre_jump"
      diskboot_sha256: "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75"
      card_filesystem: "FAT32"
      card_lock_state: "LOCKED"
      bootdisk_vbr_present: true
      script_vbr_present: true
      button_pressed: "POWER"
      button_action: "long_hold_3s"
      button_hold_approx_ms: 3000
      led_observed: "solid_on"
      led_approx_duration_ms: 3000
      lcd_backlight_state: "on_stock_ui"
      time_to_dark_ms: 0
      outcome: "stock_ui"
      notes: "Holding power button brought up stock UI, confirming sub_fc1284ac button hold requirement"
```

### 6.2 JSON Format Template

```json
{
  "session_report": {
    "session_id": "PORT23-SESSION-20261101",
    "camera_model": "Canon PowerShot G3 X",
    "firmware_version": "GM1.10C",
    "platform_id": "0x32A8",
    "runs": [
      {
        "power_on_index": 1,
        "build_stage": "pre_jump",
        "build_flag": "--stage pre_jump",
        "diskboot_sha256": "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75",
        "card_filesystem": "FAT32",
        "card_lock_state": "LOCKED",
        "bootdisk_vbr_present": true,
        "script_vbr_present": true,
        "button_pressed": "POWER",
        "button_action": "brief_tap",
        "button_hold_approx_ms": 200,
        "led_observed": "flash_brief",
        "led_approx_duration_ms": 50,
        "lcd_backlight_state": "off_unpowered",
        "time_to_dark_ms": 100,
        "outcome": "power_off",
        "notes": "Green LED flashed once briefly, camera remained completely off with dark backlight"
      },
      {
        "power_on_index": 2,
        "build_stage": "pre_jump",
        "build_flag": "--stage pre_jump",
        "diskboot_sha256": "abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75",
        "card_filesystem": "FAT32",
        "card_lock_state": "LOCKED",
        "bootdisk_vbr_present": true,
        "script_vbr_present": true,
        "button_pressed": "POWER",
        "button_action": "long_hold_3s",
        "button_hold_approx_ms": 3000,
        "led_observed": "solid_on",
        "led_approx_duration_ms": 3000,
        "lcd_backlight_state": "on_stock_ui",
        "time_to_dark_ms": 0,
        "outcome": "stock_ui",
        "notes": "Holding power button brought up stock UI, confirming sub_fc1284ac button hold requirement"
      }
    ]
  }
}
```
