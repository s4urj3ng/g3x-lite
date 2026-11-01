# PORT-24 T4 (r2): Owner Session Plan — Localizing Post-Loader Shutdown via Breadcrumb Ladder (GM1.10C)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) [VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/PORT21_RAM_LIFETIME.md:3]
- **Purpose**: Diagnostic execution plan for the camera owner to localise the post-loader shutdown in at most two physical power-ons using the opt-in Breadcrumb Ladder DISKBOOT candidate [INFERRED: § 2; docs/PORT24_BREADCRUMB_LADDER.md:7]
- **Evaluation Mode & Safety**: Phase 0 Read-Only regarding firmware and camera hardware (`docs/SAFETY.md:1-8`). STRICT NO-GO on firmware flashing, camera connection, binary modification, boot scripts, or unreviewed execution [VERIFIED: docs/SAFETY.md:1-8; AGENTS.md:19-25]
- **Base Document Dependencies** [VERIFIED: docs/PORT24_LOADER_TRACE.md:828-1029]:
  - `docs/PORT24_BREADCRUMB_LADDER.md` (T3: Opt-in Breadcrumb Ladder Candidate Build, DISKBOOT.BIN SHA-256 `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c`) [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:14, 517]
  - `docs/PORT24_LOADER_TRACE.md` (T2: Restart path findings, Section `## Restart path`, lines 828–1029) [VERIFIED: docs/PORT24_LOADER_TRACE.md:828-1029]
  - `docs/PORT24_LOADER_TRACE.md` (T1: 29-step post-prologue trace & Section 6 ranked failure table, lines 721–793) [VERIFIED: docs/PORT24_LOADER_TRACE.md:721-793]
  - `docs/PORT24_POWERON_FIX.md` (Analysis of second power-on check in `boot_prototype.c:350` and O1 trial result) [VERIFIED: docs/PORT24_POWERON_FIX.md:14-31]
  - Owner Physical Trial Results (2026-11-01) [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:20-23]
- **Epistemic Classifications** [VERIFIED: AGENTS.md:12-16]:
  - `[VERIFIED]`: Directly proven by tracked repository files, static ROM manifests, or recorded physical hardware trials [VERIFIED: AGENTS.md:1-16].
  - `[INFERRED]`: Logical deductions from verified ROM disassembly, architectural constraints, and hardware observations [INFERRED: AGENTS.md:1-16].
  - `[UNKNOWN]`: Unmeasured physical parameters, unread ROM routines outside approved slices, or uninstrumented hardware behaviors [UNKNOWN: AGENTS.md:1-16].

---

## 1. Exact SD Card Setup & Candidate Artifacts

The trial uses a single SD card configured identically to the owner's previous successful sessions [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:183-214; docs/PORT19_BOOTDISK_VBR.md:20-34].

### 1.1 Card Preparation Specifications

| Parameter | Required Value | Firmware Gating & Evidence Reference | Epistemic Status |
| :--- | :--- | :--- | :---: |
| **Filesystem** | **FAT32** (primary partition, $\le 32\text{ GB}$) | Supported by stock DryOS mounter; VBR checked by `sub_fc37aea6` (`0xFC05BC18`) [VERIFIED: docs/PORT19_BOOTDISK_VBR.md:20-34] | `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:20-34]` |
| **Write-Protect Tab** | **LOCKED** (slider in down position) | Checked by `StartDiskboot` via GPIO `0x14F` (`sub_fc05c4e0(1)` bit 0 == 1 at `0xFC05BC02..0xFC05BC0A`); if UNLOCKED, `StartDiskboot` exits cleanly at `0xFC05BC0A` to stock boot [VERIFIED: ROM 0xFC05BC02-0xFC05BC0A in docs/PORT24_LOADER_TRACE.md:948-951; INFERRED: docs/HANDOFF.md:923] | `[VERIFIED: docs/PORT24_LOADER_TRACE.md:948-951]` |
| **`BOOTDISK` Marker** | String `"BOOTDISK"` at VBR offset **`0x1E0`** (480 dec) | Required by `sub_fc37aea6` at `0xFC05BC18` for FAT32 media; if absent, `StartDiskboot` branches at `0xFC05BC1C` to clean return `0xFC05BC34` [VERIFIED: ROM 0xFC05BC18-0xFC05BC1C in docs/PORT24_LOADER_TRACE.md:956; docs/PORT19_BOOTDISK_VBR.md:12-25] | `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:12-25]` |
| **`SCRIPT` Marker** | String `"SCRIPT"` at VBR offset **`0x1F0`** (496 dec) | Read by filesystem mounter to set `is_scriptdisk` (enables Canon Basic script execution); does not gate `StartDiskboot` [VERIFIED: docs/PORT19_BOOTDISK_VBR.md:28-36; docs/PORT24_LOADER_TRACE.md:961-965] | `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:28-36]` |

### 1.2 Binary File Placement on Card Root (`A/`)

Copy the built ladder candidate artifact from `candidate_breadcrumb_ladder/` to the SD card root directory [INFERRED: § 1.1; docs/PORT24_BREADCRUMB_LADDER.md:34-38]:
- **Target File**: `A/DISKBOOT.BIN` on the card root filesystem [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:35]
- **Candidate Size**: `118,257` bytes [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:14, 517]
- **Exact Candidate SHA-256**: `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:14, 517]
- **Pre-Flight Hash Verification**: Before inserting the SD card into the camera, the owner must verify that running `sha256sum /<card-mount-point>/DISKBOOT.BIN` strictly matches `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c`; if it differs by even one byte, do not insert the card [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:517; docs/SAFETY.md:1-8].

---

## 2. Step-by-Step Execution Plan (At Most Two Power-Ons)

Unlike single-stage breadcrumbs (which required separate binaries and repeated card preparation), the PORT-24 T3 Breadcrumb Ladder Candidate executes sequentially through all 7 loader checkpoints in a single boot cycle [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:7]. The diagnostic session is structured for **one, at most two, power-ons** [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:7].

### 2.1 Accounting for the Owner O1 Trial Result & Known Power Cut

In physical hardware trials on 2026-11-01, the camera owner established a critical operational distinction on the PORT-19 default candidate build (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22]:
1. **Short Press (Brief Tap)**: The camera powered off immediately after loader execution with the LCD backlight dark [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22].
2. **Continuous Hold until LCD Came On**: The camera booted successfully into the stock Canon user interface (`O1` result) [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22].

#### The Candidate Power Cut Mechanism (INFERRED)
The failure mechanism on a short press is analyzed from static ROM disassembly and candidate ELF auditing [VERIFIED: candidate_main.elf:0x34976C-0x349776; chdk-port/platform/g3x/sub/110c/boot_prototype.c:350-356; ROM 0xFC05B970-0xFC05BA56; docs/PORT24_LOADER_TRACE.md:921-930; docs/PORT24_POWERON_FIX.md:20-29]:
- During native cold boot, `sub_fc1284ac` samples the power button BEFORE `task_Startup` is spawned [VERIFIED: ROM 0xFC05B96C in docs/PORT24_LOADER_TRACE.md:922].
- In `boot_prototype.c:350-352`, the candidate code replicates Stage 5 (`sub_fc05b962_my`) and invokes `sub_fc1284ac` a **second time** [VERIFIED: candidate_main.elf:0x34976C; chdk-port/platform/g3x/sub/110c/boot_prototype.c:352].
- On a short tap, the owner has already released the physical button by the time Step 25 runs; routine `sub_fc1284ac` samples GPIO 0x97 as released, returning `r0 = 0` [VERIFIED: ROM 0xFC1284BC-0xFC128504; INFERRED: docs/PORT24_LOADER_TRACE.md:927].
- At line 354, `boot_prototype.c` calls `sub_fc05ba56` (`0xFC05BA56`), which writes `0x004C0003` to GPIO 0x67 (MMIO `0xD20B099C`), terminating DC-DC power to the SoC and halting in `b .` [VERIFIED: ROM 0xFC05BA56; candidate_main.elf:0x349772-0x349776; chdk-port/platform/g3x/sub/110c/boot_prototype.c:354; INFERRED: docs/PORT24_LOADER_TRACE.md:928-929].
- Conversely, holding the power button continuously maintains GPIO 0x97 asserted (`1`), causing `sub_fc1284ac` to return `1`; execution branches to `loc_fc05b978` (`boot_prototype.c:358`), creating `task_Startup_my` and branching to `sub_fc0d0126` (`boot_prototype.c:438`), which presents the stock UI [INFERRED: docs/PORT24_LOADER_TRACE.md:932-934].

### 2.2 Execution Order, Timing Bounds, and Why Ladder Result is NOT Hidden

The execution sequence and timing bounds show why the breadcrumb ladder result is not masked by the short-press cut [INFERRED: § 2.2; docs/PORT24_LOADER_TRACE.md:725-731; docs/PORT24_BREADCRUMB_LADDER.md:87-91, 138-143]:

| Sequence Phase | Executed Function & Checkpoints | Nominal Loop Duration [INFERRED] | Envelope Bounds (Loop-Only) [INFERRED] | Latency & Non-Loop Overhead [UNKNOWN] | Epistemic Status & Evidence Citation |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Phase 1: Cold Boot & Loader Entry** | ROM cold boot -> `task_Startup` -> `StartDiskboot` -> `0x8000` | Uninstrumented | Uninstrumented | Pre-loader cold boot latency is unmeasured [UNKNOWN: docs/PORT24_LOADER_TRACE.md:927] | `[VERIFIED: docs/PORT24_LOADER_TRACE.md:922-924]` |
| **Phase 2: Ladder Steps 1 to 7** | `my_restart` (`0x8000..0x8332`), Flashes 1 to 7 | 578.76 ms (7 x 82.68 ms) | 463.05 ms (fastest bound) to 1389.08 ms (slowest bound) | Per-step non-loop MMIO store / DSB overhead is unmeasured [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:16, 143] | `[INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:88-91, 138-141]` |
| **Phase 3: Terminal Hand-off** | `0x8332: bx r0` into CHDK core `_start` (`0x003489B5`) | < 1 ms | Branch instruction | Handoff execution latency is unmeasured [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495] | `[VERIFIED: chdk-port/loader/g3x/entry.S:7-8; docs/PORT24_BREADCRUMB_LADDER.md:482]` |
| **Phase 4: Core Init to Stage 5 Check** | `startup()` -> Low RAM copy -> DryOS init -> Step 25 check (`boot_prototype.c:350`) | Uninstrumented | Uninstrumented | Core execution time prior to Step 25 is unmeasured [UNKNOWN: docs/PORT24_LOADER_TRACE.md:927] | `[VERIFIED: candidate_main.elf:0x34976C; chdk-port/platform/g3x/sub/110c/boot_prototype.c:350-352]` |
| **Phase 5a: Short Press Outcome** | Button released (`r0 == 0`) -> `sub_fc05ba56` cuts power via GPIO 0x67 | Immediate cut | GPIO 0x67 de-asserted | 7 complete flashes precede the power cut [INFERRED: § 2.2; docs/PORT24_LOADER_TRACE.md:928-929] | `[INFERRED: docs/PORT24_LOADER_TRACE.md:928-929]` |
| **Phase 5b: Held Press Outcome** | Button held (`r0 == 1`) -> `task_Startup_my` -> stock UI (`sub_fc0d0126`) | Continues | Continues to stock UI | 7 complete flashes precede stock UI illumination [INFERRED: § 2.2; docs/PORT24_LOADER_TRACE.md:932-934] | `[INFERRED: docs/PORT24_LOADER_TRACE.md:932-934]` |

- **Why the Ladder Result is NOT Hidden by the Short-Press Cut** [INFERRED: § 2.2; docs/PORT24_LOADER_TRACE.md:725-731, 751; docs/PORT24_BREADCRUMB_LADDER.md:295-463]:
  1. All 7 breadcrumb ladder steps reside entirely in `loader_main_breadcrumb.c` within `my_restart` (`0x8000..0x8332`), and terminal handoff occurs at Step 7 (`0x8332: bx r0`) [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:482]. The second button check (`sub_fc1284ac`) runs at Step 25 (`0x0034976C`) inside the CHDK core, strictly after the loader finishes [VERIFIED: candidate_main.elf:0x34976C; chdk-port/platform/g3x/sub/110c/boot_prototype.c:350-352].
  2. On a short tap (~100–200 ms), the physical button is released while the loader is executing its early steps, but DC-DC power remains asserted by hardware until Step 26 actively commands `0x004C0003` to GPIO 0x67 [INFERRED: docs/PORT24_LOADER_TRACE.md:927-929].
  3. Therefore, on a short press, all 7 loader steps execute and emit their optical flashes before the power cut occurs; the power cut terminates power only AFTER the loader has finished [INFERRED: § 2.2; docs/PORT24_LOADER_TRACE.md:928-929].
  4. Wall-clock boot latencies (from button click to `0x8000` and from `bx r0` to Step 25) are unmeasured and UNKNOWN [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:16, 143; docs/PORT24_LOADER_TRACE.md:927]. Only the loop duration bounds (fastest bound ~66.15 ms/step, nominal ~82.68 ms/step, slowest bound ~198.44 ms/step) are supported by calibration [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:88-91, 138-141].

### 2.3 Step-by-Step Session Protocol

- **Pulse Countability & Completeness Criteria** [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:17, 497]:
  - Human visual countability of the chosen ON/OFF durations on physical camera hardware is unmeasured and UNKNOWN [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:17].
  - An observed pulse count localises the failure checkpoint only when every pulse was seen complete (both the active ON flash and the subsequent dark gap finished before camera power off) [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:497].
  - A failure during an active pulse can make the count off-by-one ambiguous; an incomplete or truncated pulse indicates that the fault occurred during that step's execution [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:497].
  - When the observed sequence is uncertain, truncated, or merged (e.g. flicker fusion), the owner uses **Power-On 2** to repeat the observation under focused attention or video recording, maintaining the strict overall limit of **at most two power-ons in total** [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:497].

#### Step 1: Power-On 1 — Short Press (Primary Ladder Run)
- **Guidance & Evidence Level**: Normal short tap of Power button (~100–200 ms duration; release immediately upon tactile click) [INFERRED: protocol recommendation in docs/PORT24_LOADER_TRACE.md:996-999; button timing unmeasured UNKNOWN: docs/PORT24_LOADER_TRACE.md:927].
- **Purpose**: Observe the breadcrumb ladder flashes against a completely dark camera panel without LCD glow or lens motor distraction [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:998].
- **Owner Action** [INFERRED: protocol steps; docs/PORT24_BREADCRUMB_LADDER.md:10-14]:
  1. Insert charged battery and LOCKED SD card with `DISKBOOT.BIN` SHA-256 `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:14, 517].
  2. Dim room ambient lighting and focus gaze directly on the rear green status LED (`0xD20B0884`) [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:10].
  3. Give the Power button a firm, brief tap (~100–200 ms) and immediately release [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:996-999].
  4. Count every distinct flash of the green LED until the camera goes completely dark or completes the sequence [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:7].
- **Expected Observations & Immediate Triage** [INFERRED: triage protocol; docs/PORT24_BREADCRUMB_LADDER.md:488-497]:
  - **Count = 1 to 6 complete flashes, then dark**: The failure occurred INSIDE the loader between Step $k$ and Step $k+1$; the known cut at `boot_prototype.c:350` was never reached, and the failure is localized directly by the count (see Section 3 Decode Table) [INFERRED: § 3; docs/PORT24_BREADCRUMB_LADDER.md:489-494]. Power-On 2 is NOT needed.
  - **Count = 7 complete flashes, then dark**: Step 7 checkpoint `before_bx` was reached [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:482]. Terminal hand-off `bx r0` and core execution remain uninstrumented [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495]. The subsequent shutdown could be caused by the second button check in `boot_prototype.c:350` (T1 Rank 1 candidate) [INFERRED: docs/PORT24_LOADER_TRACE.md:782; docs/PORT24_POWERON_FIX.md:20-29], a failed terminal hand-off `bx r0` (T1 Loader Phase I: Low) [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495], or a failure inside the core (T1 Ranks 2-7) [INFERRED: docs/PORT24_LOADER_TRACE.md:783-789]. Proceed to **Power-On 2** (Held Press) to discriminate.
  - **Count is uncertain, truncated mid-pulse, or merged**: The observation was ambiguous or interrupted mid-pulse [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:497]. Proceed to **Power-On 2** to repeat the observation with closer attention or video recording [INFERRED: § 2.3].
  - **Count = 0 flashes (camera stays dark)**: Cold boot gate failed before Step 1, or StartDiskboot was skipped (see Section 4) [INFERRED: § 4; docs/PORT24_LOADER_TRACE.md:983-988]. Proceed to Power-On 2 [INFERRED: § 2.3].

#### Step 2: Power-On 2 — Continuous Held Press (Confirmation / Repeat Run)
- **Guidance & Evidence Level**: Continuous long press; maintain firm pressure on the Power button until the LCD illuminates (~1–2 s hold) [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; INFERRED: docs/PORT24_LOADER_TRACE.md:1000-1002].
- **Purpose** [INFERRED: protocol purpose; docs/PORT24_LOADER_TRACE.md:1000-1002]:
  1. If Power-On 1 saw 7 flashes and powered off: discriminate whether suppressing the second button check cut (`boot_prototype.c:350`) allows the ladder candidate to boot the stock UI (reproducing the O1 result on the ladder build) [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:1000-1002].
  2. If Power-On 1 saw an uncertain, truncated, or ambiguous count: repeat the observation to obtain a definitive count [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:497].
  3. Total power-ons for the entire diagnostic session remain strictly at most two [INFERRED: § 2; docs/PORT24_BREADCRUMB_LADDER.md:7].
- **Owner Action** [INFERRED: protocol steps; docs/PORT24_LOADER_TRACE.md:1000-1002]:
  1. If the camera powered off, wait at least 5 seconds [INFERRED: § 2.3; docs/PORT23_OWNER_SESSION_PLAN.md:240].
  2. Press and **HOLD the Power button continuously** without releasing upon tactile click [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; INFERRED: docs/PORT24_LOADER_TRACE.md:1000-1002].
  3. Watch the rear green LED during the first second of the hold (count flashes), then watch for the LCD display to illuminate [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:89].
  4. As soon as the LCD backlight turns on or stock UI appears, release the button [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:1000-1002].
- **Discrimination Criteria** [INFERRED: discrimination logic; docs/PORT24_LOADER_TRACE.md:1000-1002]:
  - *7 flashes observed, then LCD illuminates and stock Canon UI appears*: Reproduces the O1 outcome on the ladder build [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; INFERRED: docs/PORT24_LOADER_TRACE.md:1000-1002]. Holding the button kept GPIO 0x97 asserted, passing `sub_fc1284ac` at `boot_prototype.c:350` and reaching stock continuation `sub_fc0d0126` [INFERRED: docs/PORT24_LOADER_TRACE.md:932-934]. This strongly supports T1 Rank 1 (`boot_prototype.c:350` second button check) as the primary cause of the short-press shutdown, though core execution internals remain uninstrumented [INFERRED: docs/PORT24_POWERON_FIX.md:20-30; UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495].
  - *7 flashes observed, but camera still powers off despite continuous hold*: Exonerates the button-release cut as the primary cause [INFERRED: docs/PORT24_LOADER_TRACE.md:1002]. Implicates alternative mechanisms: a failed terminal hand-off `bx r0` (T1 Loader Phase I: Low) [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495], external sub-CPU hardware power supervision timeout (T1 Rank 2) [INFERRED: docs/PORT24_LOADER_TRACE.md:783], stray IRQ panic hang at Step 22b (T1 Rank 3) [INFERRED / UNKNOWN: docs/PORT24_LOADER_TRACE.md:784], or core heap/driver halt (T1 Ranks 4-7) [INFERRED: docs/PORT24_LOADER_TRACE.md:785-789].
  - *Definitive count 1 to 6 flashes observed on repeat*: Localises failure to loader Step $k$ [INFERRED: § 3; docs/PORT24_BREADCRUMB_LADDER.md:489-494].
  - *0 flashes observed, but camera boots directly to stock UI*: A clean bypass of DISKBOOT by `StartDiskboot` is an INFERRED possibility (Mechanism B: unlocked card, GPIO 0x14E non-zero, missing marker/file) [INFERRED: docs/PORT24_LOADER_TRACE.md:947-958, 986-988]. However, alternative explanations include missed optical flash, LED signalling failure, or battery transient; whether the payload actually ran in the current boot remains UNKNOWN [INFERRED: docs/PORT24_LOADER_TRACE.md:983-988; UNKNOWN: docs/PORT24_LOADER_TRACE.md:988].

#### Optional Single Power-On Alternative (Direct Continuous Hold)
- If the owner chooses to perform strictly **ONE power-on** to minimize cycles: the owner may perform the Continuous Held Press directly on the first attempt [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:1000-1002].
- The owner must watch the rear green LED intently for the first ~1.0 s after pressing the button, counting the optical flashes before looking at the LCD screen [INFERRED: § 2.3; docs/PORT24_BREADCRUMB_LADDER.md:89].
- If 7 flashes occur followed by stock UI illumination, the session diagnostic objective is fully achieved in a **single power-on** [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:1000-1002].

---

## 3. Comprehensive LED Sequence & Final State Decode Table (with T1 Rankings)

Every breadcrumb ladder pulse loop is identical (`subs r2, #1; bne.n`) and operates on GPIO MMIO `0xD20B0884` using `0x004D0002` (ON) and `0x004C0003` (OFF) [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:10, 122-127]. The total number of complete flashes observed before the camera powers off or goes dark directly decodes the execution milestone reached:

| Flash Count | Observed Signal & Final State | Loader Checkpoint Reached | Failing Execution Step & Mechanism | T1 Trace Step & Likelihood Ranking | Next Host Action |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **0** | No light seen; camera stays completely dark and unpowered | None (failed before Step 1 pulse) | Cold boot gate failed before Step 1, dancingbits decrypt error, PID mismatch in check_compat (`0x32A8`), early DC-DC collapse, or flat battery [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:488; docs/PORT24_LOADER_TRACE.md:839-840, 983-985]. Whether payload ran in current boot is [UNKNOWN: docs/PORT24_LOADER_TRACE.md:988] | Step 1 / Pre-loader Gates (T2 Restart Path Gating) [INFERRED: docs/PORT24_LOADER_TRACE.md:839-840] | Check SD card format, inspect write-protect switch, verify battery charge [INFERRED: § 1.1; docs/PORT24_SESSION_PLAN.md:27-31] |
| **1** | **1 complete flash**, then camera powers off (LCD dark) | `after_prologue` (`0x000081E2`) | Step 1 pulse completed. Fault between Step 1 and Step 2: DRAM payload relocation write fault in `core_copy` (`0x003489B4`), or alignment fault during witness store at `0x0035F7A0` [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:489] | Step 3 (`core_copy`) & Step 4 (Witness write); T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Audit DRAM memory mapping permissions at `0x003489B4`; check witness struct alignment [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:489] |
| **2** | **2 complete flashes**, then camera powers off (LCD dark) | `after_copy` (`0x00008246`) | Step 2 pulse completed. Fault between Step 2 and Step 3: transition into inline cache maintenance block (only adjacent breadcrumb pulse code runs here) [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:490] | Step 3/4 -> Step 5 transition; T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Audit instruction sequence between `core_copy` return and cache parameter setup [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:490] |
| **3** | **3 complete flashes**, then camera powers off (LCD dark) | `before_dcache` (`0x00008268`) | Step 3 pulse completed. Fault during D-cache clean & invalidate: argument setup, `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1` DCCISW subroutine) fault, or bus lockup on `dsb sy` [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:491] | Step 5 (`ROM_DCACHE_CLEAN_INV`); T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Verify DCCISW arguments (`r0 = 0x003489B4`, `r1 = 116816`); inspect ROM `0xFC127AB0` [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:491] |
| **4** | **4 complete flashes**, then camera powers off (LCD dark) | `after_dcache` (`0x00008296`) | Step 4 pulse completed. Fault between Step 4 and Step 5: transition from `after_dcache` into `before_icache` (only adjacent breadcrumb pulse code runs here) [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:492] | Step 5 -> Step 6 transition; T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Verify pulse execution timing and power hold rails [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:492] |
| **5** | **5 complete flashes**, then camera powers off (LCD dark) | `before_icache` (`0x000082B8`) | Step 5 pulse completed. Fault during I-cache & BP invalidation: argument setup, `ROM_ICACHE_INV_BP` (`0xFC127B09` ICIALLU/BPIALL subroutine), `dsb sy`, or pipeline sync (`isb sy`) [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:493] | Step 6 (`ROM_ICACHE_INV_BP`); T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Verify ICIALLU arguments (`r0 = 0x003489B4`, `r1 = 116816`); inspect ROM `0xFC127B08` [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:493] |
| **6** | **6 complete flashes**, then camera powers off (LCD dark) | `after_icache` (`0x000082EA`) | Step 6 pulse completed. Fault between Step 6 and Step 7: privilege fault or mode trap on interrupt disable instruction `cpsid if` (`0x8308`) [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:494] | Step 6 -> Step 7 transition (`cpsid if`); T1 Loader Phase I: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:725-731] | Audit CPU operating mode at loader hand-off (must be privileged System/Supervisor mode) [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:494] |
| **7** | **7 complete flashes**, then camera powers off (LCD dark) on short press | `before_bx` (`0x0000830E`) | Step 7 pulse completed; checkpoint `before_bx` reached [VERIFIED: docs/PORT24_BREADCRUMB_LADDER.md:482]. Terminal hand-off and core execution are uninstrumented [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495]. Fault mechanisms: (a) second button check in `boot_prototype.c:350` cut power on released button (T1 Rank 1 candidate) [INFERRED: docs/PORT24_LOADER_TRACE.md:782; docs/PORT24_POWERON_FIX.md:20-29]; (b) failed terminal hand-off `bx r0` (T1 Loader Phase I: Low) [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495]; (c) failure inside core: sub-CPU timeout (T1 Rank 2) [INFERRED: docs/PORT24_LOADER_TRACE.md:783], stray IRQ panic hang at Step 22b (T1 Rank 3) [INFERRED / UNKNOWN: docs/PORT24_LOADER_TRACE.md:784], or core driver halt (T1 Ranks 4-7) [INFERRED: docs/PORT24_LOADER_TRACE.md:785-789] | Step 25 & 26 (T1 Rank 1 candidate) vs Hand-off / Core Failure (T1 Ranks 2-7) [INFERRED: docs/PORT24_LOADER_TRACE.md:782-789] | Execute Power-On 2 (Held Press) to discriminate button cut from hand-off/core failure [INFERRED: § 2.3; docs/PORT24_LOADER_TRACE.md:1000-1002] |
| **7** | **7 complete flashes**, but camera powers off despite continuous hold | `before_bx` (`0x0000830E`) | Step 7 pulse completed. Button-release cut exonerated as primary obstacle. Fault occurred during terminal hand-off `bx r0` or inside CHDK core: sub-CPU power-hold supervision timeout (T1 Rank 2), stray IRQ panic hang at Step 22b (T1 Rank 3), or core heap/driver halt (T1 Ranks 4-7) [INFERRED: docs/PORT24_LOADER_TRACE.md:783-789; UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495] | Step 7 hand-off vs Steps 8-28 in core; T1 Rank 2 & Rank 3 [INFERRED: docs/PORT24_LOADER_TRACE.md:783-784] | Investigate sub-CPU serial protocol (`SioDrv`) or audit stray interrupt masking at Step 22b [INFERRED: docs/PORT24_LOADER_TRACE.md:783-784] |
| **7** | **7 complete flashes**, then LED remains solid ON, camera hangs with LCD glowing | `before_bx` (`0x0000830E`) | Step 7 pulse completed; terminal handoff succeeded. CHDK core reached display controller initialization but hung in `task_Startup_my` or stock continuation [INFERRED: docs/PORT23_OWNER_SESSION_PLAN.md:211; UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495] | Step 27/28 (Startup Task drivers); T1 Core Phase VII: Low [INFERRED: docs/PORT24_LOADER_TRACE.md:788-789] | Perform battery pull recovery; audit `task_Startup_my` driver calls [INFERRED: § 5.3; docs/PORT18_OWNER_TRIAL_PLAN.md:329-338] |
| **7** | **7 complete flashes**, then LCD turns on and **Stock Canon UI appears** | `before_bx` (`0x0000830E`) | **FULL BOOT SUCCESS.** Checkpoint `before_bx` reached, terminal hand-off succeeded, and CHDK core executed through to stock continuation `sub_fc0d0126` (O1 outcome reproduced on ladder build with held button) [INFERRED: docs/PORT24_LOADER_TRACE.md:932-934, 1000-1002; docs/PORT24_POWERON_FIX.md:16-18]. Core execution internals remain uninstrumented [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:495] | Step 29 (`sub_fc0d0126` Handoff); Execution Fully Successful [INFERRED: docs/PORT24_LOADER_TRACE.md:933-934] | Record verified O1 ladder outcome; finalize PORT-24 short-press fix [INFERRED: docs/PORT24_POWERON_FIX.md:30-31] |
| **Truncated** | Camera cuts power while LED is illuminated mid-pulse (incomplete flash) | Interrupted mid-step | Power loss occurred during the active LED ON pulse or dark gap of pulse $k$. Count is off-by-one ambiguous; fault occurred during that step's execution or early rail collapse [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:497] | Step $k$ execution / hardware power collapse [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:497] | Execute Power-On 2 (Held Press) to repeat observation with maintained power rail hold [INFERRED: § 2.3] |
| **Merged / Flicker** | Rapid optical pulses blend together without distinct dark gap (flicker fusion) | Sequence count unclear | Human eye failed to resolve rapid pulse train; retinal persistence exceeded dark gap [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:26-32]. Human countability limit reached [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:17] | Human visual physiological limit [UNKNOWN: docs/PORT24_BREADCRUMB_LADDER.md:17] | Execute Power-On 2 with video recording or repeat in dark room [INFERRED: § 2.3] |
| **Uncertain / Ambiguous** | Flash count uncertain or ambiguous; unable to confirm exact count | Ambiguous checkpoint | Visual pulse sequence not clearly enumerated. A count localises the failure only when every pulse was seen complete [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:497]. Failure cannot be isolated from this run alone [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:497] | Ambiguous step [INFERRED: docs/PORT24_BREADCRUMB_LADDER.md:497] | Execute Power-On 2 to repeat observation under focused gaze (at most two power-ons total) [INFERRED: § 2.3] |

---

## 4. How to Tell from Physical Cues Whether StartDiskboot Was Skipped

In physical trials, an owner observing the camera boot directly to the stock Canon UI must distinguish whether `StartDiskboot` actually executed `DISKBOOT.BIN` through to continuation, or whether `StartDiskboot` bypassed the candidate entirely [VERIFIED: docs/PORT24_LOADER_TRACE.md:970-988]. T2 established the physical cues that discriminate these paths:

### 4.1 Cue 1: Rear Green Status LED Activity (Ladder-Qualified)

- **Stock UI with 7 Distinct Flashes**: Proves that `StartDiskboot` executed `DISKBOOT.BIN` through the entire loader. The ladder ran, flashed all 7 checkpoints, jumped to core `_start`, and handed off to stock continuation `sub_fc0d0126` via the maintained button hold (Mechanism A) [INFERRED: docs/PORT24_LOADER_TRACE.md:979-981, 1000-1002].
- **Stock UI with ZERO Flashes Seen**: Suggests as an INFERRED possibility that `StartDiskboot` cleanly bypassed `DISKBOOT.BIN` (taking clean return sequence `0xFC05BC34` to `task_Startup` at `0xFC05B912` to boot pure factory firmware) [INFERRED: docs/PORT24_LOADER_TRACE.md:947-958, 986-988]. However, alternative explanations include the optical flash being missed by human visual observation, LED signalling failure, or battery voltage transients [INFERRED: docs/PORT24_LOADER_TRACE.md:983-988]. Whether the payload actually ran in the current boot remains UNKNOWN [UNKNOWN: docs/PORT24_LOADER_TRACE.md:988].
  - Clean Return Triggers in ROM [VERIFIED: ROM 0xFC05BBF4-0xFC05BC74 in docs/PORT24_LOADER_TRACE.md:947-958]:
    1. GPIO `0x14F` bit 0 == 0 (SD write-protect switch in UNLOCKED position at `0xFC05BC08..0xFC05BC0A`) [VERIFIED: ROM 0xFC05BC08-0xFC05BC0A in docs/PORT24_LOADER_TRACE.md:948-951].
    2. GPIO `0x14E` bit 16 non-zero (`sub_fc05c4e0(0) != 0` at `0xFC05BBF8..0xFC05BBFC`) [VERIFIED: ROM 0xFC05BBF8-0xFC05BBFC in docs/PORT24_LOADER_TRACE.md:952-955]. The physical meaning of GPIO 0x14E is unproven and UNKNOWN (do not identify as door or card switch) [UNKNOWN: docs/PORT24_LOADER_TRACE.md:954].
    3. Missing or corrupt `"BOOTDISK"` marker at VBR offset `0x1E0` (`sub_fc37aea6` returns 0 at `0xFC05BC18..0xFC05BC1C`) [VERIFIED: ROM 0xFC05BC18-0xFC05BC1C in docs/PORT24_LOADER_TRACE.md:956; docs/PORT19_BOOTDISK_VBR.md:12-25].
    4. Missing `A/DISKBOOT.BIN` file on SD card root or invalid executable format (`sub_fc05bc3c` returns via pop to `0xFC05BC2E` at `0xFC05BC5C`/`0xFC05BC74`) [VERIFIED: ROM 0xFC05BC2E-0xFC05BC74 in docs/PORT24_LOADER_TRACE.md:957].
- **Camera Stays Dark with ZERO Flashes Seen**: `StartDiskboot` was never even called! Pre-startup button check `sub_fc1284ac` at `0xFC05B96C` returned 0, so `sub_fc05ba56` cut power at `0xFC05B972` before `task_Startup` was created [VERIFIED: ROM 0xFC05B970-0xFC05B976 in docs/PORT24_LOADER_TRACE.md:942].

### 4.2 Cue 2: SD Card Lock Switch State

- If the card's physical write-protect tab is in the **UNLOCKED** (up) position: GPIO `0x14F` reads bit 0 = 0. In ROM, `0xFC05BC08: beq.n 0xfc05bc34` branches directly to clean return `0xFC05BC34` without initializing the SD bus or loading `DISKBOOT.BIN` [VERIFIED: ROM 0xFC05BC08-0xFC05BC0A in docs/PORT24_LOADER_TRACE.md:948-951, 1018-1020].

### 4.3 Cue 3: Canon Basic Witness Inspector Readout at `0x0035F7A0`

If the owner boots to the stock UI and runs the Canon Basic witness inspector (`extend.m` in Playback mode via `FUNC./SET`) [INFERRED: protocol step; docs/PORT18_OWNER_TRIAL_PLAN.md:262]:
- **`CONT_ATTEMPTED` (Yellow / Stage 0x07)**: Indicates that DISKBOOT executed `task_Startup_my` and attempted continuation `sub_fc0d0126` [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT18_OWNER_TRIAL_PLAN.md:262].
- **Stale-RAM Caveat & Attribution Uncertainty**: Because DRAM retains data across warm boots without session nonces, a static witness value cannot prove whether the current boot ran DISKBOOT or retained stale data from a previous attempt [INFERRED: docs/PORT24_LOADER_TRACE.md:935-937, 1024-1026; docs/PORT21_RAM_LIFETIME.md:44-48]. The optical LED flashes (7 flashes) provide the only real-time proof of current-boot execution [INFERRED: docs/PORT24_LOADER_TRACE.md:979-981].
- **`WITNESS_INVALID` (Light Blue / Colour Index 3)**: The witness structure failed checksum/magic validation or was overwritten by stock DryOS heap allocations [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:267; docs/PORT24_LOADER_TRACE.md:1027-1029].

---

## 5. Verified Recovery Procedures

If the camera powers off, hangs, or behaves abnormally, follow these recovery procedures to restore factory stock UI operation [INFERRED: recovery guidance; docs/PORT18_OWNER_TRIAL_PLAN.md:318-325]:

### 5.1 Owner-Observed Recovery Behaviors (2026-11-01 Physical Trials)

In physical hardware trials on 2026-11-01, the owner established the following verified recovery behaviors [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22]:
- **Continuous Hold Recovery**: Holding the Power button continuously until the LCD illuminates (~1–2 s) reached the stock UI (`O1` result) on physical hardware [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22]. Holding the button keeps GPIO 0x97 asserted, passing `sub_fc1284ac` at `boot_prototype.c:350` and handing off to stock continuation `sub_fc0d0126` [INFERRED: docs/PORT24_LOADER_TRACE.md:932-934].
- **Repeated-Press Recovery**: Repeated or long presses on a locked card sometimes reached the stock UI [VERIFIED: owner-reported in docs/PORT24_POWERON_FIX.md:16-18; docs/PORT23_POWER_SUPERVISION.md:22]. Repeated presses can coincidentally align with the sampling instant of `sub_fc1284ac` or cause transient SD bus desynchronization causing `StartDiskboot` to return cleanly to stock firmware [INFERRED: docs/PORT24_LOADER_TRACE.md:934, 959].

### 5.2 Recommended Procedure: Normal Stock Start (Card Removal or Unlock)

The following recommended recovery steps are derived from ROM branch analysis but remain physically untested on this camera [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:320-325]:
1. Turn off camera (or remove battery if unresponsive) [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:320-325].
2. Eject the SD card from the card compartment [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:324].
3. Either leave the SD card out of the camera, OR slide the write-protect tab to the **UNLOCKED** (up) position and re-insert [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:324; docs/PORT24_LOADER_TRACE.md:1018-1020].
4. Press the Power button [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:324].
5. Verification: The camera boots normally into the factory stock Canon UI, the lens extends, the LCD display activates, and full normal camera shooting operation is restored [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:324-325; docs/PORT24_LOADER_TRACE.md:1018-1020].

### 5.3 Recommended Procedure: Capacitor Discharge & PMIC Reset on Hang/Freeze

The following recommended procedure is for freeze recovery, derived from architectural guidelines but physically untested on this camera [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:320, 329-338]:
1. Immediately open the battery door and remove the rechargeable battery [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:332].
2. Eject the SD card from the compartment [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:333].
3. Leave the battery compartment open and unpowered (quiescent pause recommended; the exact duration required for complete capacitor discharge and PMIC reset is UNKNOWN, and no specific time interval guarantees it) [UNKNOWN: docs/PORT23_OWNER_SESSION_PLAN.md:238-240; INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:334].
4. Re-insert the fully charged battery with the SD card removed or unlocked [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:335].
5. Press the Power button to confirm normal factory boot [INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:336].

---

## 6. Machine-Readable Owner Report Template

The camera owner should fill out this structured report block and return it after completing the session [INFERRED: § 2.3; docs/PORT23_OWNER_SESSION_PLAN.md:250-255]:

```markdown
### PORT-24 Breadcrumb Ladder Trial Report

- **Date / Timestamp**: YYYY-MM-DD HH:MM UTC
- **Camera Model**: Canon PowerShot G3 X (Firmware GM1.10C)
- **Battery Status**: Freshly charged (voltage verified)
- **SD Card Format**: FAT32 primary partition, locked write-protect switch
- **VBR Marker Check**: BOOTDISK @ 0x1E0 confirmed, SCRIPT @ 0x1F0 confirmed
- **Binary Tested**: DISKBOOT.BIN
- **Measured SHA-256 on Card**: aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c

#### Power-On 1 (Short Press):
- **Button Action**: Short press / brief tap (~100–200 ms)
- **Flashes Observed**: [ 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Truncated mid-pulse | Merged / blended flicker | Uncertain / ambiguous ]
- **Pulse Completeness**: [ All seen pulses completed full OFF gap | Interrupted / cut short while LED was ON | Unclear ]
- **Flash Quality**: [ Distinct separate pulses | Blended / flicker fusion | Unsure ]
- **LCD Backlight State**: [ Completely dark / unpowered | Glowing blank screen | Stock UI ]
- **Final Outcome**: [ Powered off cleanly | Hung with solid LED | Booted stock UI ]
- **Estimated Time to Dark / Boot**: ~______ seconds

#### Power-On 2 (Held Press or Repeat Run, if run):
- **Run Reason**: [ Discriminator for 7 flashes | Repeat of uncertain/truncated count | Not needed / not run ]
- **Button Action**: Continuous hold until LCD illuminated (~1–2 s)
- **Flashes Observed during Hold**: [ 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Truncated | Merged | None seen ]
- **Pulse Completeness**: [ All seen pulses completed full OFF gap | Interrupted mid-pulse | Unclear ]
- **LCD Backlight State**: [ Illuminated with stock Canon UI | Dark / unpowered | Glowing blank ]
- **Stock UI Reached**: [ YES | NO ]
- **Inspector Overlay (if run)**: [ CONT_ATTEMPTED (Yellow) | WITNESS_INVALID (Blue) | None ]

#### Recovery & Operational Status:
- **Recovery Procedure Used**: [ None needed | Long-press / repeated press | Card unlocked | Card removed | Battery pull ]
- **Stock Camera Functionality Restored**: [ YES | NO ]
- **Owner Notes**: (Any unexpected lens motion, audible clicks, or visual timing observations)
```
