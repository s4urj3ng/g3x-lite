# PORT-34: Owner Trial Plan — Opt-In `G3X_KBD=1` Keyboard Candidate (GM1.10C)

**Target**: Canon PowerShot G3 X (`GM1.10C`, Platform ID `0x32A8`). Phase 0 safety rules apply (`docs/SAFETY.md`): agents build on the host only; the owner executes the hardware trial by hand. Candidate runs strictly from RAM (`DISKBOOT.BIN`), with zero firmware flashing. No classifier or decoder tools are used for this trial.

## 1. Candidate Build & Artifact Pins (`docs/PORT34_KBD_ADDRESSES.md` §1)

| Field | Value |
|:---|:---|
| **Pinned Toolchain** | `toolchains/gcc-arm-none-eabi-5_4-2016q3` (`arm-none-eabi-gcc` 5.4.1 20160919) |
| **G3X_KBD=1 Build Command** | `G3X_KBD=1 python3 -B tools/build_candidate_port25_ladder_fix.py --kbd --out-dir <dir>` |
| **G3X_KBD=1 `DISKBOOT.BIN` SHA-256** | `a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33` |
| **G3X_KBD=1 Sizes & Clearance** | `DISKBOOT.BIN`: `124,801` B; loaded `candidate_main.bin`: `123,360` B; linked `_end`: `0x00368640` $\le$ heap `0x00368880` (`576` B clearance) |
| **G3X_KBD=1 G3X_OSD=1 Build Command** | `G3X_KBD=1 G3X_OSD=1 python3 -B tools/build_candidate_port25_ladder_fix.py --kbd --osd --out-dir <dir>` |
| **G3X_KBD=1 G3X_OSD=1 `DISKBOOT.BIN` SHA-256** | `686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8` |
| **G3X_KBD=1 G3X_OSD=1 Sizes & Clearance** | `DISKBOOT.BIN`: `125,121` B; loaded `candidate_main.bin`: `123,680` B; linked `_end`: `0x00368780` $\le$ heap `0x00368880` (`256` B clearance) |
| **Expected Heartbeat (Rear Green LED `0xD20B0884`)** | - **ALT OFF**: ~1.0 Hz single blink (`100 ms ON -> 900 ms OFF`)<br>- **ALT ON**: ~1.0 Hz double blink (`100 ms ON -> 100 ms OFF -> 100 ms ON -> 700 ms OFF`) |
| **Expected Test Overlay (OSD Variant)** | 120x40 px rectangle near `(16, 16)`: 2px white border, checkerboard tiles, "CHDK" text; displays bright white "ALT" marker when ALT is ON |

## 2. Step-by-Step Trial Checklist & Procedure

- **Pre-Trial Card Prep & Hard Gate**:
  - [ ] Format SD card as FAT32 `BOOTDISK` (`0x1E0` marker present).
  - [ ] Copy candidate `DISKBOOT.BIN` to SD card root (`A/DISKBOOT.BIN`).
  - [ ] Verify `sha256sum <card>/DISKBOOT.BIN` equals expected SHA-256 (STOP if mismatch).
  - [ ] Unmount card and slide write-protect switch to **LOCKED**.
  - [ ] Insert fully charged NB-10L battery.
  - [ ] Hard limit: maximum 2 power-ons per candidate variant.

- **Step 1: Boot with Held Press & Verify Heartbeat Runs (`G3X_KBD=1` candidate)**
  - [ ] Press and **hold Power button continuously** through the PORT-25 ladder (`1..7`, `11..44`).
  - [ ] Release Power button after `Code 44` completes and stock GM1.10C UI appears on LCD.
  - [ ] Observe rear green LED (`0xD20B0884`): verify heartbeat runs at **~1.0 Hz single blink** (`100 ms ON -> 900 ms OFF`), indicating ALT mode is OFF.
  - [ ] Verify stock UI is fully responsive and camera does not crash or freeze.

- **Step 2: Toggle ALT on Standard ALT Key (`G3X_KBD=1` candidate)**
  - [ ] Press the standard ALT key: **Playback button** (`KEY_PLAYBACK` = `0x00010000`, bit 16).
  - [ ] Observe rear green LED: verify pattern switches from single blink to **~1.0 Hz double blink** (`100 ms ON -> 100 ms OFF -> 100 ms ON -> 700 ms OFF`), confirming ALT mode is ON.
  - [ ] Press Playback button a second time.
  - [ ] Observe rear green LED: verify pattern switches back to **~1.0 Hz single blink** (`100 ms ON -> 900 ms OFF`), confirming ALT mode toggled back OFF.

- **Step 3: OSD Variant ALT Marker Check (`G3X_KBD=1 G3X_OSD=1` candidate)**
  - [ ] Deploy `G3X_KBD=1 G3X_OSD=1` candidate (`DISKBOOT.BIN` SHA-256: `686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8`).
  - [ ] Boot via held press; confirm PORT-25 ladder completes, stock UI loads, and 120x40 test overlay box appears near `(16, 16)` displaying "CHDK".
  - [ ] Press Playback button (ALT toggle): verify bright white **"ALT"** marker appears inside the overlay box next to "CHDK", and rear LED double-blinks.
  - [ ] Press Playback button again: verify **"ALT"** marker disappears from the overlay box, and rear LED returns to single blink.

- **Step 4: Boot with Short Press & Check Camera Stays On (`G3X_KBD=1` candidate)**
  - [ ] Power down camera (or perform clean battery pull).
  - [ ] Power on with a **short tap** on the Power button (< 0.5 s; do NOT hold).
  - [ ] Observe: camera completes loader/ladder and **stays powered ON** past `Code 43` without cutting power (short-press cutoff fixed by `my_kbd_read_keys_candidate` holding `KEY_POWER` bit 17 for 100 polls).
  - [ ] Verify stock UI loads and rear green LED runs single-blink heartbeat.

- **Step 5: Check Normal Stock Button Behaviour with ALT OFF (`G3X_KBD=1` candidate)**
  - [ ] Verify ALT mode is OFF (single blink on rear LED; no "ALT" marker on OSD).
  - [ ] Test stock controls: Shutter button (half-press focus / full-press), Func/Set, Menu, Disp, 4-way D-pad (Up/Down/Left/Right), Zoom lever, Control dial / lens ring (`handle_jogdial`).
  - [ ] Verify all stock controls operate normally without lag, freeze, or unhandled exception.
  - [ ] Toggle ALT ON (double blink): confirm stock functions are blocked/suppressed by CHDK key handler.
  - [ ] Toggle ALT OFF (single blink): confirm stock functions immediately resume normal operation.

## 3. Observation Table Mapped to `docs/PORT34_KBD_ADDRESSES.md` INFERRED Rows

| Symbol / Name | Inferred Value | Sibling Source | Confirmed By Trial Observation | Refuted By Trial Observation | Relevant Step(s) |
|:---|:---:|:---|:---|:---|:---:|
| `mykbd_task` | CHDK symbol | `g7x/kbd.c:70-82` | Dedicated CHDK keyboard loop polls keys continuously; ALT mode toggles without halting DryOS. | Physical buttons unresponsive, task exits immediately, or camera locks up. | Steps 1, 2 |
| `sub_fc1283d2_my` | CHDK symbol | `g7x sub/100d/boot.c:382-407`<br>`g5x sub/100c/boot.c:479-506` | `task_Startup_my` spawns `mykbd_task` with stack 0x2000 and priority 0x17 via `j_CreateTaskStrictly`; boot succeeds to stock UI. | Kernel panic or hang during task creation; `task_PhySw` not scheduled. | Step 1 |
| `wrap_kbd_p1_f_candidate` | CHDK symbol | `g7x/kbd.c:57-67` | Wrapper invokes `my_kbd_read_keys_candidate` and smoothly jumps to `_kbd_p1_f_cont` at `0xFC128695` without fault. | Crash or illegal instruction exception when button scanning runs or returns to Canon ROM. | Steps 1, 2, 5 |
| `my_kbd_read_keys_candidate` | CHDK symbol | `g7x/kbd.c:44-55`<br>`sx60hs/kbd.c:41` | Updates CHDK key state (enabling ALT toggle) and holds power bit for 100 polls (preventing short-press shutdown). | Short-press shutdown recurs at Code 43, or physical key presses fail to update internal state. | Steps 2, 4 |
| `kbd_fetch_data` | CHDK symbol | `g7x/kbd.c:135-139`<br>`sx60hs/kbd.c:140-144` | Hardware GPIO button inputs successfully fetched into destination buffers via `GetKbdState` and `kbd_read_keys_r2`. | Button registers remain unpopulated (zeroed/stale); button presses never register. | Steps 2, 5 |
| `KEY_PLAYBACK` | `0x00010000` | `g7x/kbd.c:48`<br>`sx60hs/kbd.c:46` | Pressing Playback toggles ALT mode (LED switches between single and double blink; "ALT" appears/disappears on OSD). | Pressing Playback enters stock playback mode without ALT intercept, or does not toggle LED/OSD. | Steps 2, 3 |
| `G3X_KBD_TASK_STACK_SIZE` | `0x2000` | `g5x sub/100c/boot.c:500`<br>`g7x sub/100d/boot.c:401` | Repeated button presses, rapid ALT toggling, and stock operations remain stable over >60 s without stack overflow. | Task stack corruption halts system, causes memory faults, or corrupts adjacent DRAM heap. | Steps 2, 5 |
| `G3X_POWERON_HOLD_POLLS` | `100` | `g7x/kbd.c:70-82`<br>`kbd_common.c:169-179` | Camera remains powered on after a short button tap (<0.5 s); held-press boot also succeeds. | Camera shuts down immediately upon early button release during short press (Code 43 / outcome O10 recurs). | Steps 1, 4 |
| `handle_jogdial` | stubbed (`return 1`) | `g7x/kbd.c:115` | Rotating control dial and lens ring does not crash camera, lock event queue, or trigger unhandled interrupt. | Turning control dial causes immediate camera lockup, exception, or UI freeze. | Step 5 |
| `jogdial_control` | stubbed (`noop`) | `g7x/kbd.c:135` | Symbol links cleanly without runtime side effects; dial behavior remains stable. | Link failure or crash / hang if invoked by firmware subsystems. | Steps 1, 5 |

## 4. Owner Results Table

| Step # | Test Description | Variant Tested | Expected Outcome | Observed Behaviour | Result |
|:---:|:---|:---|:---|:---|:---:|
| **1** | Held-press boot & heartbeat | `G3X_KBD=1` | Ladder finishes, stock UI loads, rear green LED single-blinks at ~1.0 Hz | | [ ] PASS<br>[ ] FAIL |
| **2a** | ALT toggle ON (Playback) | `G3X_KBD=1` | Rear green LED switches from single blink to double blink at ~1.0 Hz | | [ ] PASS<br>[ ] FAIL |
| **2b** | ALT toggle OFF (Playback) | `G3X_KBD=1` | Rear green LED switches from double blink back to single blink at ~1.0 Hz | | [ ] PASS<br>[ ] FAIL |
| **3a** | OSD overlay boot | `G3X_KBD=1 G3X_OSD=1` | Test box at `(16, 16)` displays "CHDK"; single-blink heartbeat runs | | [ ] PASS<br>[ ] FAIL |
| **3b** | OSD "ALT" marker toggle | `G3X_KBD=1 G3X_OSD=1` | Press Playback: "ALT" appears and LED double-blinks; press again: "ALT" disappears | | [ ] PASS<br>[ ] FAIL |
| **4** | Short-press boot | `G3X_KBD=1` | Tap Power (<0.5 s); camera stays ON past ladder; stock UI runs; no Code 43 shutdown | | [ ] PASS<br>[ ] FAIL |
| **5a** | Stock controls (ALT OFF) | `G3X_KBD=1` | Shutter, dials, D-pad, Menu, Func/Set operate normally without freeze | | [ ] PASS<br>[ ] FAIL |
| **5b** | Stock controls (ALT ON) | `G3X_KBD=1` | Stock key events suppressed/intercepted by CHDK while double blink active | | [ ] PASS<br>[ ] FAIL |

## 5. Recovery Procedure & Fallback Candidates

- **Strict RAM-Only Execution Guarantee**:
  - The candidate binary (`DISKBOOT.BIN`) executes strictly in camera DRAM (`0x003489B4`).
  - No flash ROM sectors, bootloaders, or NVRAM are modified.
  - A battery pull completely clears camera DRAM and resets hardware to stock state.
- **Battery-Pull Recovery Steps**:
  1. **Pull Battery**: Open battery latch and remove the NB-10L battery pack immediately.
  2. **Eject SD Card**: Remove SD card; slide write-protect switch to **UNLOCKED** (or delete `A/DISKBOOT.BIN`).
  3. **Wait 30 Seconds**: Allow all power rail capacitors to completely discharge.
  4. **Stock Verification Boot**: Reinsert battery, close door, and power on normally **without candidate** to confirm clean stock GM1.10C UI operation, then power off via Power button.
- **Fallback Candidates Table**:
  | Fallback Level | Candidate Variant | Build Command | `DISKBOOT.BIN` SHA-256 | Fallback Purpose / Role |
  |:---:|:---|:---|:---:|:---|
  | **Fallback 1** | PORT-33 Overlay Only | `G3X_OSD=1 python3 -B tools/build_candidate_port25_ladder_fix.py --osd --out-dir <dir>` | `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` | Isolates display pipeline if keyboard task causes boot failure. |
  | **Fallback 2** | PORT-32 Resident Only | `G3X_RESIDENT=1 python3 -B tools/build_candidate_port25_ladder_fix.py --resident --out-dir <dir>` | `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` | Isolates resident task & SleepTask yield if overlay or kbd fails. |
  | **Fallback 3** | Default Flag-Off Build | `python3 -B tools/build_candidate_port25_ladder_fix.py --out-dir <dir>` | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | Baseline PORT-25 ladder fix without resident multitasking. |
