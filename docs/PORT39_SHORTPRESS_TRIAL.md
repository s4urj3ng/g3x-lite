# PORT-39: Short-Press Power-On Handling & Owner Trial Plan (With PORT-38 Timing & Baseline)

## 1. Overview & Sibling Adaptation Context

Milestone PORT-39 addresses the short-press power-off limitation on the PowerShot G3 X (GM1.10C, PID `0x32A8`, DIGIC 6). In prior milestones, booting the CHDK candidate required physically holding the Power button. Owner input from the PORT-38 trial (2026-11) refined this understanding: holding the Power button for approximately 5 seconds—specifically until the LED breadcrumb ladder blinks finish—is sufficient for the camera to remain powered on and load the candidate.

The short-press power-on mechanism adapts the closest DIGIC 6 sibling handling (PowerShot G7 X and G5 X) to GM1.10C:
1. **Early Boot Entry Hook & Saved-Cause Capture**: At boot entry (`boot()` in `boot_prototype.c`), before the first ladder stage (`CORE_LADDER_PULSE_11`) and before Copy Loop 3 overwrites low RAM (`0x00008000..0x0003F4F4`), `g3x_shortpress_boot_entry_hook()` samples the original startup cause from `*(0x9BC4 + 12)` (`0x00009BD0`) and preserves it in CHDK-owned variable `g3x_saved_start_cause`.
2. **Start-Cause Mode Discrimination**: Evaluates `g3x_saved_start_cause`: Playback start (`0x00100000`) selects Playback switch bit 16 (`0x00010000`), while Power start (`0x00080000`, 0, or default) selects Power switch bit 17 (`0x00020000`).
3. **Low-RAM Post-BSS Restoration**: After Copy Loop 3 and Canon BSS zeroing complete, `g3x_shortpress_post_bss_hook()` restores `0x00009BD0` from `g3x_saved_start_cause` and clears the active-low button bit in `physw_status[0]` (`0x00040DAC`). Stage 5 caller `sub_fc05b962_my` similarly maintains `0x00009BD0` after `sub_fc1284ac` returns 0.
4. **Override Duration Paced to LED Ladder Window**: The coverage window starts at boot entry ($t = 0$), spanning the synchronous execution of the LED ladder (~5.0 s / 5000 ms, `VERIFIED` by PORT-38 owner trial). When `mykbd_task` starts after ladder pulse 42, it continues the override for `G3X_SHORTPRESS_MARGIN_POLLS = 200` polls. At `physw_sleep_delay = 10` ms (`0x000082C4`, `FINSIG`/`VERIFIED`), 200 polls provide 2000 ms (2.0 s, 40%) safety margin beyond the ladder, for a total hold window of ~7000 ms (~7.0 s) from boot entry.
5. **Automatic Override Release**: Once the 200 margin polls complete, `g3x_shortpress_active` is cleared (0) and the override is released, allowing subsequent physical button presses (e.g. normal Power button press to shut down) to operate natively.
6. **Task Stack Allocation**: In `sub_fc1283d2_my` (`0xFC1283D2`), `mykbd_task` is created with a dedicated 0x2000 (8192 B) stack via `j_CreateTaskStrictly` (`0xFC31BE8C`), matching sibling G5 X `boot.c:479-506`.

All short-press code is strictly guarded behind `#if defined(G3X_SHORTPRESS) && (G3X_SHORTPRESS == 1)`. The default build and all prior candidate builds remain 100% byte-identical.

---

## 2. Adapted-Value Table

The table below lists every adapted address, bit, hook, and duration mapping sibling sources to GM1.10C:

| Item / Mechanism | Sibling Source path:line | GM1.10C Value (Address / Bit / Constant) | Label | Source Citation / Proof |
|:---|:---|:---|:---:|:---|
| **Boot entry hook** | `chdk-port/platform/g5x/sub/100c/boot.c:172-182` | `g3x_shortpress_boot_entry_hook` before `CORE_LADDER_PULSE_11` | `INFERRED` | Sibling G5 X samples button and writes start cause before task creation (`boot.c:172-182`); GM1.10C hooks `boot()` entry at `0x0034960E` before first ladder stage and before low-RAM copy. |
| **Saved-cause variable** | `chdk-port/platform/g5x/sub/100c/boot.c:172-182` | `g3x_saved_start_cause` capturing `*(0x9BC4 + 12)` (`0x00009BD0`) | `INFERRED` | `0x00009BD0` address/bit meaning is `VERIFIED` in ROM (`docs/PORT24_POWERON_FIX.md:172-198`). Retention across soft restart into CHDK `boot()` entry is `INFERRED` and tested in trial steps (b)/(c). |
| **Post-BSS restoration hook** | `chdk-port/platform/g5x/sub/100c/boot.c:172-182` | `g3x_shortpress_post_bss_hook` after `loc_zero_bss` | `INFERRED` | Restores `*(0x00009BD0) = g3x_saved_start_cause` and clears `physw_status[0]` bit after ROM-to-RAM copy loop overwrites low RAM. |
| **Power switch bit** | `chdk-port/platform/g7x/kbd.c:50`<br>`chdk-port/platform/g5x/sub/100c/physw_bits.txt:16` | Word 0, bit 17 (`0x00020000`, levent `0x100`) | `FINSIG` | `reference/finsig_gm110c/physw_bits.txt:18`; `chdk-port/platform/g3x/platform_kbd.h:26` |
| **Playback switch bit** | `chdk-port/platform/g7x/kbd.c:48`<br>`chdk-port/platform/g5x/sub/100c/physw_bits.txt:13` | Word 0, bit 16 (`0x00010000`, levent `0x101`) | `FINSIG` | `reference/finsig_gm110c/physw_bits.txt:17`; `chdk-port/platform/g3x/platform_kbd.h:25` |
| **Physical switch buffer** | `chdk-port/platform/g5x/kbd.c:118-126`<br>`chdk-port/platform/g7x/sub/100d/boot.c:382` | `physw_status[0]` at `0x00040DAC` | `VERIFIED` | `reference/finsig_gm110c/stubs_entry.S:173` (FINSIG); manifest `docs/port34_evidence_manifest.json` (`PORT34-ROM-KBD-P1-F-LITERALS`, start `0xFC12868C`, len 164 B, SHA-256 `bc6ca612429d161a14b2dee2d12599dbb8f9c824b4915ea8086371156f98aaee`) |
| **Key polling task loop** | `chdk-port/platform/g7x/kbd.c:70-82` | `task_PhySw` `0xFC1283AD`; `physw_run` `0x000082BC`; `physw_sleep_delay` `0x000082C4` (10 ms) | `VERIFIED` | Manifest `docs/port34_evidence_manifest.json` (`PORT34-ROM-PHYSW-TASKCREATE`, start `0xFC1283AC`, len 104 B, SHA-256 `ac7d16ad69045ff89d81c71fba9305614b8df87d55397fa5ac096eb43f02a01c`) |
| **Task creation hook** | `chdk-port/platform/g5x/sub/100c/boot.c:479-506`<br>`chdk-port/platform/g7x/sub/100d/boot.c:382-407` | `sub_fc1283d2` (`0xFC1283D2`); stack `0x2000`; priority `0x17`; entry `mykbd_task` via `j_CreateTaskStrictly` (`0xFC31BE8C`) | `VERIFIED` | Manifest `docs/port34_evidence_manifest.json` (`PORT34-ROM-PHYSW-TASKCREATE`) |
| **Active-low switch logic** | `chdk-port/core/kbd_common.c:297, 338` | `physw_status[0] &= ~mask` (0 = PRESSED, 1 = RELEASED) | `HISTORICAL_CHDK` | CHDK core keyboard implementation: `kbd_mod_state[grp] &= ~canonkey` on press; `physw_status[0] |= mask` marks button released. |
| **Start-cause structure** | `chdk-port/platform/g5x/sub/100c/boot.c:172-182`<br>`g3x_110e.patch:P1685-1691` | `*(volatile unsigned int *)(0x9BC4 + 12)` (`0x00009BD0`) | `VERIFIED` | Manifest `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json` (`PORT24-ROM-STARTCAUSE-SAVE`, start `0xFC08ECB0`, len 80 B, SHA-256 `039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d`; `PORT24-ROM-STARTCAUSE-PTR`, start `0xFC08EEE0`, len 32 B, SHA-256 `0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6`) |
| **Start-cause values** | `chdk-port/platform/g5x/sub/100c/boot.c:172-182`<br>`g3x_110e.patch:P1685-1691` | Power: `0x00080000`; Playback: `0x00100000` | `VERIFIED` | Written by `sub_fc08ecbc` in GM1.10C ROM (`docs/PORT24_POWERON_FIX.md:172-198`). Manifest: `PORT24-ROM-STARTCAUSE-SAVE`. |
| **Power-cut bypass** | `chdk-port/platform/g5x/sub/100c/boot.c:411-420` (`sub_fc0ecf20_my`) | `sub_fc05b962_my` (`0xFC05B962`) bypasses `sub_fc05ba56` (`0xFC05BA56`), forcing `r0 = 1` | `VERIFIED` | Manifest `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json` (`PORT24-ROM-CALLER-STARTUP`, start `0xFC05B960`, len 96 B; `PORT24-ROM-POWERCUT`, start `0xFC05BA50`, len 32 B) |
| **Hold duration & time base** | Owner observation (PORT-38 trial, 2026-11) (held press of ~5 s until LED ladder finishes) | Pre-task ladder (~5000 ms) + `G3X_SHORTPRESS_MARGIN_POLLS = 200` polls @ 10 ms = ~7000 ms (~7.0 s) from boot entry | `INFERRED` | Owner observation verified ~5 s LED ladder window (`VERIFIED`); `physw_sleep_delay = 10` ms (`0x000082C4`, `FINSIG`/`VERIFIED`). 200 polls provides ~2.0 s (40%) safety margin beyond ladder before releasing override (`INFERRED`). |

---

## 3. Override Duration Analysis & Time Base (PORT-38 Timing Reference)

In the PORT-38 owner trial (2026-11), the owner observed that holding the Power button does not need to last until the stock UI loads. Holding Power for about 5 seconds—until the LED breadcrumb ladder blinks finish—is sufficient for the camera to remain powered on into the CHDK candidate.

**Time Base & Hold Window Breakdown**:
1. **Timer Start**: The coverage timer begins at boot entry ($t = 0$) when `g3x_shortpress_boot_entry_hook()` runs immediately after `sp` initialization and before `CORE_LADDER_PULSE_11`.
2. **Pre-Task Window (LED Ladder Execution)**: Spans the synchronous execution of early boot and all 20 breadcrumb ladder stages from boot entry to `sub_fc1283d2_my` (pulse 42), lasting approximately 5000 ms (~5.0 s) on physical camera (`VERIFIED` by PORT-38 trial observation).
3. **Task Creation & Sleep Delay Mapping**: After pulse 42, `sub_fc1283d2_my` creates `mykbd_task`. In `mykbd_task`, the task loop executes `_SleepTask(physw_sleep_delay)`. `physw_sleep_delay` is loaded from `0x000082C4`, which is initialized to 10 in Low RAM (verified at ROM literal `0xFC1283B2` in `task_PhySw`, `reference/finsig_gm110c/stubs_entry.S:172`). Thus, each poll in `mykbd_task` maps to exactly 10 ms.
4. **Post-Task Margin**: In `mykbd_task`, `my_kbd_read_keys_candidate()` / `g3x_shortpress_read_keys()` maintains the override for `G3X_SHORTPRESS_MARGIN_POLLS = 200` polls ($200 \times 10\text{ ms} = 2000\text{ ms} = 2.0\text{ s}$), providing a 40% safety margin beyond the ladder.
5. **Total Coverage Window**: Spans $\sim 5000\text{ ms} + 2000\text{ ms} = \sim 7000\text{ ms}$ ($\sim 7.0\text{ s}$) measured from boot entry.
6. **Automatic Release**: When `g3x_shortpress_margin_polls` reaches 0, `g3x_shortpress_active` is cleared (0). Subsequent polls no longer clear button bits in `physw_status[0]`. When the user later presses the Power button, the press is detected normally by Canon firmware, initiating clean power-down.

---

## 4. Candidate Binaries

Built with pinned toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3`:

| Candidate Configuration | DISKBOOT Size | DISKBOOT SHA-256 | Boot Witness | Linked `_end` | Heap Clearance |
|---|---|---|---|---|---|
| **`G3X_SHORTPRESS=1` (Plain Candidate)** | 124,945 B | `6df54a905e36a6fe92b5a3a4ac4dd71086d3306fd0aaa31a1f1bc670f7e19461` | `0x003611C0` | `0x003686E0` | 416 B |
| **`G3X_SHORTPRESS=1` + `G3X_GUI4=1` (Combined)** | 102,401 B | `4859e0886a32665e5adbf65400121bb2a503b5827aa29aa69e35dc33a465db28` | `0x0035CA40` | `0x00362A80` | 24,064 B |

DryOS heap base is `0x00368880` (`docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD`), providing positive clearance above linked `_end` for both configurations.

---

## 5. Invariance of Prior Builds

Every prior build remains 100% byte-identical to its pinned baseline:

| Configuration | Output Size | SHA-256 Checksum | Invariance Status |
|---|---|---|---|
| **Default Build** | 118,001 B | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-38 GUI4** | 102,241 B | `14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-37 GUI3** | 103,569 B | `4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-36 GUI2** | 103,345 B | `4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-35 GUI** | 103,057 B | `1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-35 OSD2** | 125,329 B | `20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-34 KBD** | 124,801 B | `a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-33 OSD** | 124,833 B | `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-32 RESIDENT**| 124,561 B | `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` | **BYTE-IDENTICAL** [VERIFIED] |

---

## 6. Safety & Recovery Constraints

- **Phase 0 Compliance**: Strictly offline host builds. No physical camera hardware is connected. Binaries are copied to SD card manually by the owner (`docs/SAFETY.md`).
- **RAM Execution Only**: Candidate executes solely from camera DRAM. No flash ROM, bootloader block, NVRAM, or persistent camera firmware is modified.
- **Zero Card Writes**: `conf_save` and file logging stubs are no-ops. Zero write operations are issued to the SD card.
- **Battery-Pull Recovery**: If any unexpected halt occurs, open the battery door and remove the NB-10L battery for $\ge 10\text{ seconds}$ to fully discharge DRAM. Reinserting the battery and tapping Power powers on into unmodified factory Canon firmware.

---

## 7. Owner Trial Plan (Ordered Steps a–e)

Use the combined candidate `G3X_SHORTPRESS=1 G3X_GUI4=1` (`DISKBOOT.BIN` SHA-256 `4859e0886a32665e5adbf65400121bb2a503b5827aa29aa69e35dc33a465db28`, size `102,401` B).

### Step (a): Held Press Regression Check (PORT-38 GUI4 Baseline)
- **Action**: Insert SD card with combined build `DISKBOOT.BIN`. Press and hold Power button for ~5 seconds through the LED ladder until stock Playback UI loads. Press Playback button to enter ALT mode; press Menu button to open the CHDK menu.
- **Expected Result**:
  - **F1 2x Font**: Menu rows display in clear 16x32 font with 16 px advance and 32 px row pitch without character overlap (`PASS`).
  - **Title Bar**: "Main Menu" header displays crisp white text on solid black background anchored at top of menu (`PASS`).
  - **F3 Opacity**: Solid opaque black fill covers the menu area (`PASS`). Known thin leaks at the top and right edges are expected and do NOT constitute a failure.
  - **Known Geometry Gap**: The menu box occupies ~80% width $\times$ 85% height of the LCD screen (Mode 12, 900x600). This gap is scheduled for the next milestone and is explicitly **NOT a FAIL** for this trial.
  - **No Flicker**: Menu is completely static at idle (`PASS`).
  - **Step 8**: Sentinel byte `0x42` restores overlay after stock OSD toggle (`PASS`).
  - **Step 9**: Menu close and ALT exit cleanly erase CHDK overlay and restore stock controls (`PASS`).
- **What a FAIL looks like**: Overlapping or unreadable 8x16 font; unreadable header (black text on dark background); menu flickering or blinking at idle; crash on ALT toggle.
- **Item Confirmed/Refuted**: Confirms `INFERRED` that combining `G3X_SHORTPRESS=1` with `G3X_GUI4=1` introduces zero regression to font rendering, menu layout, opacity fill, or task coordination against the PORT-38 baseline.

### Step (b): Short Press into Playback Mode
- **Action**: From clean power-off state, perform a brief short tap ($<0.5\text{ s}$) on the **Playback** button.
  *(Note: Contrast with the reference held-press timing of ~5 s required in prior trials to bridge the LED ladder window).*
- **Expected Result**: Camera powers on, captures start cause `0x00100000` at boot entry, executes LED ladder (~5 s), restores `0x00009BD0 = 0x00100000`, overrides Playback switch state (`physw_status[0] &= ~0x00010000`) for 200 polls (~2.0 s post-ladder), bypasses shutdown, and successfully loads stock Playback UI with CHDK candidate resident (rear green LED blinks steady ~1.0 Hz single blink).
- **What a FAIL looks like**: Camera cuts power during or at the end of the LED ladder (Code 43 terminal shutdown; outcome O10), boots into shooting mode instead of Playback mode, or LCD remains off.
- **Item Confirmed/Refuted**: Confirms `INFERRED` item: start-cause discrimination via `g3x_saved_start_cause` captured before Low-RAM reinitialization correctly identifies Playback button start (`0x00100000`) and synthesizes Playback held (`physw_status[0] &= ~0x00010000`), keeping camera in Playback mode without cutting power. Refutes if camera boots into shooting mode or cuts power at Code 43.

### Step (c): Short Press into Shooting Mode
- **Action**: From clean power-off state, perform a brief short tap ($<0.5\text{ s}$) on the **Power** button.
- **Expected Result**: Camera powers on, captures start cause `0x00080000` at boot entry, executes LED ladder (~5 s), restores `0x00009BD0 = 0x00080000`, extends zoom lens, overrides Power switch state (`physw_status[0] &= ~0x00020000`) for 200 polls (~2.0 s post-ladder), bypasses shutdown, and reaches live shooting mode with CHDK candidate resident (heartbeat LED alive, live view display active on LCD).
- **What a FAIL looks like**: Camera cuts power during the ladder (Code 43), boots into Playback mode instead of shooting mode, or lens extends partially and power cuts off (outcome O10).
- **Item Confirmed/Refuted**: Confirms `INFERRED` item: start-cause discrimination via `g3x_saved_start_cause` captured before Low-RAM reinitialization correctly identifies Power button start (`0x00080000` / default) and synthesizes Power held (`physw_status[0] &= ~0x00020000`), booting camera into Shooting mode (extending lens) without cutting power. Refutes if camera boots into Playback mode or cuts power.

### Step (d): Heartbeat LED Alive After 30 Seconds
- **Action**: After short-press boot (either Step b or c), leave camera idle on a table for $\ge 30\text{ seconds}$ without touching any buttons. Observe rear green LED.
- **Expected Result**: Rear green LED continues steady ~1.0 Hz single blink (`100 ms ON / 900 ms OFF`). Camera remains fully stable and responsive; DryOS tasks continue executing normally after the ~7.0 s hold window has expired.
- **What a FAIL looks like**: Heartbeat LED freezes ON, freezes OFF, stops blinking, or camera spontaneously shuts down after 7 seconds.
- **Item Confirmed/Refuted**: Confirms `INFERRED` that the hold window (~5 s ladder + 200 polls @ 10 ms = ~7.0 s) safely expires and returns control to physical switches without task starvation, deadlock, or watchdog panic in `task_PhySw` or `mykbd_task`. Refutes if camera crashes upon override expiration.

### Step (e): Normal Power-Off With Power Button
- **Action**: With camera running past 30 s, press and release the physical **Power** button normally.
- **Expected Result**: Physical Power button press is detected by `my_kbd_read_keys_candidate` (override is inactive). Canon firmware executes clean shutdown: lens retracts smoothly (if in shooting mode), LCD turns off, power LED turns off, and PMIC power-hold line is released cleanly.
- **What a FAIL looks like**: Camera ignores the Power button press and remains ON (override failed to release / stuck in hold loop); or camera crashes with lens extended.
- **Item Confirmed/Refuted**: Confirms `INFERRED` that releasing the override after 200 margin polls restores normal physical Power button detection via Canon event dispatcher `_kbd_p2_f` (`0xFC12811F`), allowing clean user-directed power-down. Refutes if camera cannot be powered off with the button.
