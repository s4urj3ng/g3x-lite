# PORT-36: Owner Trial Plan — Candidate `G3X_GUI2=1` (GM1.10C)

**Target**: Canon PowerShot G3 X (`GM1.10C`, PID `0x32A8`). Phase 0 safety rules apply (`docs/SAFETY.md`): host builds offline only, owner executes hardware trials by hand. Binary is strictly RAM-only (`DISKBOOT.BIN` in DRAM), with zero flash ROM or NVRAM modification.

## 1. Candidate Build & Verification (`docs/PORT36_GUI_GEOMETRY.md`)

| Parameter | Specification / Pinned Value |
|:---|:---|
| **Build Command** | `python3 -B tools/build_candidate_port25_ladder_fix.py --gui2 --out-dir candidate_port36_gui2` |
| **Candidate `DISKBOOT.BIN` SHA-256** | `4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071` |
| **Candidate `DISKBOOT.BIN` Size** | `103,345 bytes` |
| **Binary Bounds & Clearance** | Witness address: `0x0035CDF0`; linked `_end`: `0x00362E30` $\le$ DryOS heap start: `0x00368880` (clearance: `23,120 bytes`) |

## 2. Boot Method & Budget

| Stage | Procedure & Safety Limits |
|:---|:---|
| **Card Staging** | Copy `DISKBOOT.BIN` to root of FAT32 `BOOTDISK` SD card (`0x1E0` marker). Verify SHA-256 matches. Lock write-protect switch. |
| **Boot Method** | **Held press**: press and hold Power button continuously (~1–2 s) through the ladder until stock UI loads. |
| **Trial Budget** | **At most 2 power-ons** per trial session (power-on 2 only if button was released early or to verify recovery). |

## 3. Observation Checklist & Geometry Refutations

| Check | Action & Expected Observation | Result | Refuted Row(s) on FAIL | Notes / Observations Blank |
|:---|:---|:---:|:---|:---|
| **Heartbeat present** | Release Power after ladder boot; rear green LED runs steady ~1.0 Hz single blink (`100 ms ON / 900 ms OFF`). Stock Canon UI loads. | [ ] PASS<br>[ ] FAIL | PORT-35 regression (no PORT-36 row) | Rear LED blink pattern / ladder stop code:<br>________________________________________ |
| **ALT toggles** | Press Playback (`KEY_PLAYBACK`); rear green LED switches to ~1.0 Hz double blink. | [ ] PASS<br>[ ] FAIL | PORT-35 regression (no PORT-36 row) | Rear LED double-blink transition:<br>________________________________________ |
| **F1: Menu fills LCD & readable** | In ALT mode, press Menu key (`KEY_MENU`); CHDK Main Menu opens. Menu width fills most of the LCD; text is readable. | [ ] PASS<br>[ ] FAIL | `camera_screen.disp_left`, `camera_screen.disp_right`, `camera_screen.disp_width` | Fraction of the screen used, text readability, margin clipping:<br>________________________________________ |
| **F2: Box covers every item** | Solid black box covers every item, including bottom 3: *Script*, *CHDK Settings*, and *Miscellaneous Stuff*. | [ ] PASS<br>[ ] FAIL | `Menu box background (draw_rectangle)` | Which items fall outside the box:<br>________________________________________ |
| **F3: Background opaque** | Solid black background is opaque; zero stock Canon UI showing through behind text or unpainted rows. | [ ] PASS<br>[ ] FAIL | `conf.menu_color.bg.col`, `Menu box background (draw_rectangle)` | Degree of translucency, underlying stock UI showing through:<br>________________________________________ |
| **D-pad / SET navigation** | D-pad Up/Down navigates items; Left/Right or SET toggles / enters submenu without freeze. | [ ] PASS<br>[ ] FAIL | PORT-35 regression (no PORT-36 row) | Cursor movement smoothness / freeze on entry:<br>________________________________________ |
| **Menu close** | Press Menu key (`KEY_MENU`); CHDK menu closes and OSD clears cleanly with no ghost artifacts. | [ ] PASS<br>[ ] FAIL | PORT-35 regression (no PORT-36 row) | Clean erase vs ghost artifacts on screen:<br>________________________________________ |
| **ALT exit** | Press Playback (`KEY_PLAYBACK`); rear green LED returns to single blink; full stock Canon controls restore. | [ ] PASS<br>[ ] FAIL | PORT-35 regression (no PORT-36 row) | Stock controls restored vs freeze:<br>________________________________________ |

## 4. Recovery Procedure

| Step | Action | Expected Result |
|:---:|:---|:---|
| **1. Battery Pull** | If camera hangs, freezes, or finishes trial, open battery door and remove NB-10L battery immediately. | Cuts power immediately; clears DRAM state. |
| **2. Stock Boot** | Reinsert battery, close door. Power on with normal short tap (<0.5 s) without holding Power button. | Bypasses `DISKBOOT.BIN`; returns cleanly to stock Canon firmware. |
