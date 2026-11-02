# PORT-27: Resident Heartbeat Recovery Plan & Safety Stop Conditions

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-27 T4 (`p27-t4-trial-recovery-plan`)
- **Baseline Candidate Document**: `docs/PORT27_RESIDENT_CANDIDATE.md`
- **Canonical Baseline Recovery Reference**: `docs/PORT25_OWNER_TRIAL_PLAN.md:334-369` (Section 5: Recovery Procedures) `[VERIFIED]`
- **Milestone Status / Verdict**: **NO-GO Record** (No candidate produced; zero code modified; no physical hardware trial conducted in PORT-27) `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6-32; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]`

---

## 1. Context, Reference to PORT-25 Recovery Plan & Scope

### 1.1 Milestone Context & NO-GO Record Reference
In milestone PORT-27, task T2 concluded with a strict **NO-GO record** because Item (b) DryOS `CreateTask` calling convention parameter semantics are `[INFERRED]` rather than `[VERIFIED]`, and internal callees (`0xBFE10B88`, `0xBFE10D14`, `0xBFE13E78`) lie outside the authorized read policy boundary `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:20-26; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]`.

In accordance with milestone instructions:
> *"If T2 was NO-GO, write the trial plan as a 'no trial this milestone' note that carries the UNKNOWN list and the proposed next ROM ranges, and skip the recovery plan beyond a reference to the PORT-25 recovery plan."*

Therefore, for this milestone, the authoritative recovery procedures are defined by reference to the established, verified recovery procedures in **`docs/PORT25_OWNER_TRIAL_PLAN.md:334-369` (Section 5: Recovery Procedures)** `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md:334-369; docs/PORT18_OWNER_TRIAL_PLAN.md:318-355]`. Because zero code changes were made to the codebase and no resident candidate was produced, there is zero physical hardware risk in PORT-27 `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`.

### 1.2 Boot Method & Scope Restrictions
1. **Held-Press Boot Method**: The only authorized boot method for resident heartbeat evaluation is the **Held-Press Boot Method** (pressing and holding the Power button down continuously until all 7 loader blinks, transition gap, and core ladder codes 11–44 have finished and the LCD displays the Canon stock UI) `[VERIFIED: docs/PORT24_SESSION_PLAN.md:92-96; docs/PORT26_CODE43_RECORD.md:40-44]`.
2. **Short-Press Shutdown is Explicitly Out of Scope**: Short-press shutdown was localized in PORT-26 to **Code 43** (`task_Startup_my` helper-return checkpoint) `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:63-65; docs/PORT26_CODE43_RECORD.md:12-38]`. By owner priority direction on 2026-11-02, short-press shutdown is deferred to Step 3 (`task_PhySw` hook / keyboard polling) `[VERIFIED: docs/PORT26_CODE43_RECORD.md:59-62; docs/PROJECT_STATE.md:839-847]`. Short-press trials are NOT to be conducted for resident heartbeat testing, and any shutdown observed on short press is expected behaviour under the known Code 43 mechanism.

---

## 2. Reversible Boot Architecture & Non-Destructive Invariants

Any hardware execution on the PowerShot G3 X is governed by the reversible boot mechanisms established across project safety documentation `[VERIFIED: docs/SAFETY.md:7; docs/PORT25_OWNER_TRIAL_PLAN.md:338-344]`:

- **R-a. SD Card Write-Protect Tab Unlock**: Hardware-level SD boot requires the card's physical write-protect switch to be in the **LOCKED** position `[VERIFIED: docs/HANDOFF.md:923; docs/PROJECT_STATE.md:333]`. Sliding the switch to UNLOCKED, or removing the SD card completely, bypasses `DISKBOOT.BIN` execution entirely and leads directly to a normal factory firmware start `[INFERRED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:230-242; docs/PORT25_OWNER_TRIAL_PLAN.md:340]`.
- **R-b. Plain Card Without `"BOOTDISK"` Marker**: SD boot requires the 8-byte ASCII marker `"BOOTDISK"` at offset `0x1E0` in the Volume Boot Record (VBR) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:20-25]`. An SD card lacking this signature executes standard stock firmware without loading `DISKBOOT.BIN` `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:341]`.
- **R-c. Clean Return on Unloaded Diskboot**: If `StartDiskboot` loads nothing or encounters an invalid image, it executes `bx lr` returning through `0xFC05BC38` → `0xFC05C4DE`, allowing `task_Startup` to continue normal boot at `0xFC05B912` `[VERIFIED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:230-239; docs/PORT25_OWNER_TRIAL_PLAN.md:342]`.
- **R-d. Volatile RAM Execution**: All candidate loader code executes at `0x8000` `[VERIFIED: tools/build_candidate_port2a.py:536]` and core code executes in relocated DRAM at `0x003489B4..0x00368680` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:390-391]`. The candidate contains zero flash-write routines, zero EEPROM write calls, and zero `SetParameterData` invocations `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-487; docs/PORT25_OWNER_TRIAL_PLAN.md:343]`. Completely powering off the camera drains volatile DRAM and completely removes candidate code from the camera `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:343]`.

---

## 3. Concrete Recovery Procedures by Failure Mode

When candidate trials are conducted in future milestones, the owner must apply the specific recovery action sequences below:

### 3.1 Failure Mode 1: Camera Hangs or Freezes (Outcome `O8`, `O9`)
*Symptoms*: The optical ladder stops at an intermediate stage code, the rear green LED stays dark without booting stock UI, or the camera becomes unresponsive while powered on `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:347-355]`.

1. **Do not press buttons repeatedly** `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:348]`.
2. **Remove the battery immediately**: Open the battery/card door and remove the battery pack `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:349]`. (Do not merely eject the card, as the PMIC and CPU remain powered in a hung state `[INFERRED: docs/PORT24_SESSION_PLAN.md:1347-1351]`.)
3. **Remove the SD card**: Eject the candidate SD card `[INFERRED: R-a]`.
4. **Capacitor Discharge Interval**: Leave the camera unpowered without a battery for at least **30 seconds** to allow power rail capacitors to fully drain and reset the PMIC supervision microcontroller `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:351; docs/PORT24_SESSION_PLAN.md:1347-1351]`.
5. **Stock Restart Verification**: Insert a fully charged battery with **NO SD card**. Power on by pressing the **Playback** button `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:352]`.
6. **Confirm Normal Stock Operation**: Verify that the LCD displays the normal playback screen, menus respond cleanly, and switching to Shooting mode extends the lens properly `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:353]`.
7. **Host Card Sanitization**: On the host workstation, slide the write-protect tab to UNLOCKED or rename `DISKBOOT.BIN` to prevent boot execution before inserting the card back into the camera `[INFERRED: R-a, R-b; docs/PORT25_OWNER_TRIAL_PLAN.md:354]`.

### 3.2 Failure Mode 2: Rear Green LED Stays Solid ON (Outcome `O8`)
*Symptoms*: The rear green LED turns ON and remains solid ON indefinitely without toggling or progressing to stock UI, indicating a crash or hang inside the ladder, heap setup, or task initialization while the LED GPIO MMIO is asserted `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:347, 388]`.

1. **Remove the battery immediately**: Continuous solid ON draws battery current through the LED drive circuit and may indicate an unhandled assertion or infinite loop in early boot. Pull the battery immediately `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:349]`.
2. **Remove the SD card**: Eject the SD card to prevent rebooting into the candidate.
3. **Wait 30 seconds**: Allow complete capacitor discharge `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:351]`.
4. **Revert SD Card on Host**:
   - Unlock the card slider tab (write-protect UP) `[VERIFIED: R-a]`.
   - Rename `DISKBOOT.BIN` to `DISKBOOT.OFF` or replace with a clean stock SD card lacking `"BOOTDISK"` `[VERIFIED: R-b]`.
5. **Verify Stock Recovery**: Insert charged battery with no card (or stock card) and verify normal boot in Playback mode `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:352-353]`.

### 3.3 Failure Mode 3: No UI / LCD Dark / No Power-On (Outcome `O10`, `O15`)
*Symptoms*: The Power button is pressed, but the camera exhibits no LED flash, no LCD backlight, no lens extension, and powers down completely `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:356-362]`.

1. **Verify Held-Press Boot Method**: Confirm that the Power button was held continuously down until all ladder blinks finished. (Remember: short-press shutdown is out of scope; releasing the button prematurely will cause a clean shutdown at Code 43 `[VERIFIED: docs/PORT26_CODE43_RECORD.md:40-44]`).
2. **If Held Press Produces No Response**:
   - Open door, remove battery and SD card `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:357]`.
   - Place battery in external Canon charger and confirm full charge `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:358]`.
   - Inspect the battery/card door latch to ensure the hardware interlock microswitch closes firmly `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:359]`.
   - Insert charged battery with **no card**, latch door, and press Playback `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:360]`.
   - If still unresponsive: leave battery out for 60 seconds, then retry once `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:361]`.

### 3.4 Failure Mode 4: Heartbeat Missing (Stock UI Boots, but No ~1 Hz Heartbeat)
*Symptoms*: The optical ladder codes 11–44 play, the camera boots smoothly into the Canon stock UI (LCD on, lens extends, shooting screen active), but the rear green LED does not toggle at ~1 Hz (remains dark or solid) `[INFERRED: prompt p27-t4]`.

1. **Do NOT force an abnormal shutdown**: The camera is executing normal Canon stock firmware safely `[INFERRED]`.
2. **Power Off Normally**: Power off the camera cleanly using the camera's Power button or Playback toggle `[INFERRED]`.
3. **SD Card Log Triage**: Remove the SD card and mount on the host workstation. Check for the presence of `TRACE.LOG` or crash dumps `[INFERRED: tools/port18_trial_report.py:238-246]`.
4. **Outcome Classification**: Record the trial report with `camera_behaviour: normal_stock_boot`, `outcome_id: O4` (or `O5` if `TRACE.LOG` is present), and note that the heartbeat task failed to toggle `[VERIFIED: tools/port18_trial_report.py:1029-1038]`.

---

## 4. Safety Stop Conditions (Abort Rules)

Per project safety policy (`docs/SAFETY.md:7` `[VERIFIED]`), testing must halt immediately under any of the following mandatory stop conditions:

> [!CAUTION]
> **Mandatory Abort Conditions**:
>
> 1. **Failure to Return to Stock Behaviour**: If stock camera operation (normal Playback mode, responsive menus, clean lens extension) does NOT return after battery removal and restarting with NO card: **STOP IMMEDIATELY, DO NOT RETRY** `[INFERRED: docs/SAFETY.md:7; docs/PORT25_OWNER_TRIAL_PLAN.md:367]`.
> 2. **Continuous Reboot Loop**: If the camera begins power cycling or rebooting repeatedly without user intervention: remove battery immediately and do not reinstall until host-side review is complete `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md:364]`.
> 3. **Display Error Codes or ROM Asserts (Outcome `O11`, `O12`)**: If the camera LCD displays an abnormal Canon error code (e.g. `Err 20`, `Err 70`) or DryOS assertion text: pull battery immediately, preserve SD card contents unmodified, and file an `O11`/`O12` report `[VERIFIED: tools/port18_trial_report.py:1023-1025; docs/PORT25_OWNER_TRIAL_PLAN.md:364-367]`.
> 4. **Acoustic or Mechanical Anomaly**: If the camera emits grinding, clicking, or abnormal shutter/lens mechanism sounds: pull battery immediately.
> 5. **Thermal Anomaly**: If the camera body or battery door exhibits excessive heat: pull battery immediately and allow camera to cool.
