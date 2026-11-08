# PORT-37: CHDK GUI Flicker, Redraw Mechanism, Large-Screen Font, and Opacity Survey

## Overview
Evidence survey for candidate `G3X_GUI3=1` analyzing flicker root causes in `G3X_GUI2=1`, comparing CHDK core and sibling redraw/buffer architectures (`g7x`, then `g5x`, then `sx60hs`), tracing menu background opacity, specifying large-screen font scaling, and recording verified display geometry.

## Evidence & Decision Table

| Item | G3X Current (path:line) | Sibling / Core Reference (path:line) | Label | Decision for GUI3 |
|---|---|---|---|---|
| B1: `gui_redraw` flags | `tools/build_candidate_port25_ladder_fix.py:432-455` | `chdk-port/core/gui.c:2966-3012`; `chdk-port/core/gui_menu.c:952-965` | HISTORICAL_CHDK | Drop periodic force_redraw; call `gui_redraw(0)` and rely on core `gui_menu_redraw` flags |
| B1: Guard pixel functions | absent (uncalled in `g3x_gui_kbd_redraw`) | `chdk-port/core/gui_draw.c:380-389`; `chdk-port/core/gui_draw.h:104-105`; `chdk-port/core/gui.c:2968` | HISTORICAL_CHDK | `draw_set_guard` / `draw_test_guard` present (`draw_guard_pixel` absent); use sentinel `0x42` on `opacity_buffer[active][0]` |
| B1: `draw_restore` & refresh | `tools/build_candidate_port25_ladder_fix.py:425-427`; `sub/110c/osd2_test_overlay.h:147-151` | `chdk-port/core/gui_draw.c:420-431`; `chdk-port/platform/g7x/lib.c:7-20`; `g5x/lib.c:9-19`; `sx60hs/lib.c:14-20` | HISTORICAL_CHDK | Retain `draw_restore()` on ALT exit; invokes `vid_bitmap_refresh()` calling `_transfer_src_overlay` |
| B1: Opacity byte check in draw proc | absent (`core/gui_draw.c:78` writes opacity unconditionally) | absent in `chdk-port/core/gui_draw.c:72-94`; `chdk-port/platform/g5x/lib.c:211-224` (`check_gui_needs_redraw`) | HISTORICAL_CHDK | No per-pixel opacity check; use sentinel byte check in `draw_test_guard()` to detect Canon redraws |
| B1: Buffer target (active vs inactive) | active buffer `[active_bitmap_buffer & 1]` (`core/gui_draw.c:72-74`) | `chdk-port/platform/g7x/platform_camera.h:143`; `g5x/platform_camera.h:83`; `sx60hs/platform_camera.h:122` | HISTORICAL_CHDK | Draw into ACTIVE buffer; `DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY 1` is mandatory on DIGIC 6 (`core/gui_draw.c:68-70`) |
| B1: Recommended repaint mechanism | periodic forced redraw `(tick_cnt & 3) == 0` (`build_candidate_port25_ladder_fix.py:436`) | `chdk-port/core/gui.c:2968-2975`; `chdk-port/core/gui_draw.c:380-389`; `chdk-port/core/gui_menu.c:952-965` | INFERRED | Recommend guard/sentinel pixel (`draw_test_guard`); draws only on key events or when Canon wipes sentinel |
| B2: `g3x_gui_kbd_redraw()` hook | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:287,294`; `kbd_candidate.h:110` | `chdk-port/platform/g7x/kbd.c:70-82`; `chdk-port/core/main.c:289-324` | INFERRED | Retain kbd-task driver; remove per-tick drawing and unconditional force_redraw |
| B2: `(tick_cnt & 3) == 0` force_redraw | `tools/build_candidate_port25_ladder_fix.py:436` (via `osd2_test_overlay.h:294`) | `chdk-port/core/main.c:322-325` (passes 0 / `gui_force_redraw`, not 1) | INFERRED | Remove `(tick_cnt & 3) == 0` force_redraw completely; menu stays static until user navigation or erase |
| B2: Per-key force_redraw | `tools/build_candidate_port25_ladder_fix.py:434-435` (via `osd2_test_overlay.h:294`) | `chdk-port/core/gui_menu.c:366,379,402,520` (sets `gui_menu_redraw = 1` for row updates) | INFERRED | Remove per-key `force_redraw = 1`; let `gui_menu_kbd_process` trigger incremental row updates (`gui_menu_redraw = 1`) |
| B2: Black filled box clear | `tools/build_candidate_port25_ladder_fix.py:444-453` (`draw_rectangle` with `COLOR_BLACK`) | `chdk-port/core/gui_menu.c:740` (scrollbar only); `core/gui_menu.c:967-1077` (per-row text background) | INFERRED | Remove periodic `draw_rectangle` clear from `g3x_gui_kbd_redraw`; paint full box once upon `gui_menu_draw_initial` |
| B2: Per-tick diag frame / marker | `tools/build_candidate_port25_ladder_fix.py:457-471` (4 border lines + `draw_string` every tick) | absent in siblings / core | INFERRED | Remove diagnostic border lines and string from GUI3; PORT-36 geometry trial completed |
| F1: Built-in font dimensions | 8x16 glyphs scaled to 14x32 in `draw_char` (`core/gui_draw.c:701-784`) | `chdk-port/core/gui_draw.h:56-69`; `chdk-port/lib/font/rbf_font.c:251-260` | HISTORICAL_CHDK | Replace 14x32 lookup scaling with integer 2x scaling (16x32) of built-in 8x16 font for menu path (INFERRED) |
| F1: `CAM_*` font / menu scale defines | absent (`vendor/g3x-platform/platform/g3x/platform_camera.h:1-40`) | absent in `chdk-port/include/camera.h:70-125`; `g7x`; `g5x`; `sx60hs` | HISTORICAL_CHDK | No sibling scale defines exist; implement 2x integer scaling in menu draw path without external files |
| F1: Layout geometry in `gui_menu.c` | `disp_width = 900`, `height = 600` (`sub/110c/osd2_test_overlay.h:216-218`) | `chdk-port/core/gui_menu.c:226-228`; `chdk-port/platform/g5x/lib.c:195-196` | HISTORICAL_CHDK | Dynamic layout (`w = disp_width - 20`, `num_lines = (height/rbf_font_height)-1`); 900x600 yields 17 lines, w=880 px |
| F1: SD card RBF font loading | disabled (`tools/build_candidate_port25_ladder_fix.py:399-400`) | `chdk-port/core/conf.c:236,352`; `chdk-port/core/gui.c:1989-2007`; `chdk-port/lib/font/rbf_font.c:248-262` | HISTORICAL_CHDK | Exclude card RBF loading under Phase 0; use integer 2x font scaling (16x32) for menu draw path (INFERRED) |
| F3: Menu color index & palette map | `conf.menu_color.bg.col = 1` (`tools/build_candidate_port25_ladder_fix.py:1153`) | `chdk-port/core/conf.c:201` (`IDX_COLOR_GREY_DK = 13`); `platform/generic/palette.c:14,26` (`0xFF`/`0xb4`) | HISTORICAL_CHDK | Keep `conf.menu_color.bg.col = 1` (`COLOR_BLACK`) in `conf_restore()` so text row background is solid black (luma 0) |
| F3: YUV conversion & opacity write | `core/gui_draw.c:15-19, 72-94` (`obu[offset] = o`) | `chdk-port/core/gui_draw.c:15-19, 72-94`; `chdk-port/platform/g7x/lib.c:289-296` | HISTORICAL_CHDK | `CALC_YUV_LUMA_OPACITY_FOR_COLOR` yields opacity 255 for non-zero nibble; `draw_pixel_std` writes `obu[offset] = 255` |
| F3: Translucency cause & fix | `tools/build_candidate_port25_ladder_fix.py:444-453` (cleared box per force_redraw) | `chdk-port/core/gui_menu.c:731-752, 967-1077` (rows 9..13 unpainted; opacity not written) | INFERRED | Cause: **opacity not written** on rows 9..13 & margins + grey default; Fix: paint full opaque box once on init |
| Geometry: LCD displaytype & dimensions | `dt=12`, `width=900`, `height=600`, `buffer_width=928` (`docs/PORT36_GUI_GEOMETRY.md:4,10`) | `chdk-port/platform/g7x/lib.c:328-333`; `chdk-port/platform/g5x/lib.c:188-192` (720x480, stride 736) | VERIFIED | Record `dt=12 900x600 bw=928` as VERIFIED (owner trial PORT-36); mark 720/736/480 LCD assumption dropped |
| Geometry: `displaytype` address | `0x00009740` (`tools/build_candidate_port25_ladder_fix.py:876`) | `reference/finsig_gm110c/stubs_entry.S:187` | FINSIG | Use FINSIG address `0x00009740` for `displaytype` (`reference/finsig_gm110c/stubs_entry.S:187`) |
| Geometry: `active_bitmap_buffer` address | `0x0000d2a4` (`tools/build_candidate_port25_ladder_fix.py:875`) | `reference/finsig_gm110c/stubs_entry.S:186` | FINSIG | Use FINSIG address `0x0000d2a4` for `active_bitmap_buffer` (`reference/finsig_gm110c/stubs_entry.S:186`) |
| Geometry: `bitmap_buffer` address | `0x0000d2a8` (`tools/build_candidate_port25_ladder_fix.py:877`) | `reference/finsig_gm110c/stubs_entry.S:188` | FINSIG | Use FINSIG address `0x0000d2a8` for `bitmap_buffer` (`reference/finsig_gm110c/stubs_entry.S:188`) |
| Geometry: `transfer_src_overlay` stub | `0xfc380635` (`tools/build_candidate_port25_ladder_fix.py:947`) | `reference/finsig_gm110c/stubs_entry.S:352`; `g7x/lib.c:15`; `g5x/lib.c:11`; `sx60hs/lib.c:17` | FINSIG | Use FINSIG stub `0xfc380635` for `_transfer_src_overlay` in `vid_bitmap_refresh` (`reference/finsig_gm110c/stubs_entry.S:352`) |
| Geometry: `opacity_buffer` addresses | `0x5FC40000` / `0x5FB80000` (`docs/PORT35_GUI_ADDRESSES.md:38-39`) | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV` @ `0xFC183800, 0xFC183804`) | VERIFIED | Hardware addresses `0x5FC40000` / `0x5FB80000` established from ROM slice `PORT35-ROM-BMPDDEV` |

## Key Findings & Decisions

### (B1) Repaint Decision & Buffer Handling
- **Core Redraw Flags**: `gui_redraw(flag_gui_enforce_redraw)` (`core/gui.c:2966-3012`) evaluates `draw_test_guard()`, `gui_osd_need_restore`, and `gui_mode_need_redraw`. For the menu (`core/gui_menu.c:952-965`), `enforce_redraw` sets `gui_menu_redraw = 2` (full initial draw); cursor/item updates set `gui_menu_redraw = 1` (row-only draw); if `gui_menu_redraw == 0` and `enforce_redraw == 0`, nothing is drawn.
- **Guard-Pixel Functions**: In `core/gui_draw.c:380-389`, exact names are `draw_set_guard()` and `draw_test_guard()` (`draw_guard_pixel` is absent). On DIGIC 6, `draw_set_guard()` writes sentinel byte `0x42` to `opacity_buffer[active_bitmap_buffer][0]`; `draw_test_guard()` returns 0 if byte 0 is not `0x42`, detecting when Canon firmware has erased or rewritten the overlay.
- **Opacity Byte Check in DIGIC 6 Draw Proc**: Absent in `draw_pixel_std` (`core/gui_draw.c:56-95`), which writes `obu[offset] = o` unconditionally. In siblings, `g5x/lib.c:211-224` implements `check_gui_needs_redraw()` by checking if `active_bitmap_buffer` toggled.
- **Active vs Inactive Buffer**: Siblings and core draw strictly into the ACTIVE buffer (`bitmap_buffer[active_bitmap_buffer & 1]` and `opacity_buffer[active_bitmap_buffer & 1]`). `DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY 1` is mandatory on DIGIC 6 (`core/gui_draw.c:68-70`; `g7x/platform_camera.h:143`; `g5x/platform_camera.h:83`; `sx60hs/platform_camera.h:122`).
- **Recommendation for G3X**: Guard/sentinel pixel mechanism (`draw_test_guard()` / `draw_set_guard()` in `core/gui_draw.c:380-389` & `core/gui.c:2968-2975`). Rationale: DIGIC 6 enforces active-buffer drawing; the sentinel pixel automatically detects Canon overlay refreshes and requests repaints only when the buffer is wiped, avoiding periodic clearing and eliminating flicker.

### (B2) Current G3X Flicker Root Causes
Driven from `mykbd_task()` (`chdk-port/platform/g3x/sub/110c/kbd_candidate.h:110`) via `g3x_osd2_kbd_redraw` -> `g3x_gui_kbd_redraw(alt_active)` (`chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:287,294`), implemented in `tools/build_candidate_port25_ladder_fix.py:383-473` (`generate_gui_candidate_c`):
1. `(tick_cnt & 3u) == 0u` (`build_candidate_port25_ladder_fix.py:436`): Unconditionally forces `force_redraw = 1` every 4 keyboard ticks (~40-80 ms), even without UI state changes.
2. Per-key force_redraw (`build_candidate_port25_ladder_fix.py:434-435`): Forces `gui_redraw(1)` on every clicked or pressed key tick, causing `gui_menu_redraw = 2` (full rebuild) instead of incremental row navigation (`gui_menu_redraw = 1`).
3. Clear with black `draw_rectangle` (`build_candidate_port25_ladder_fix.py:444-453`): Whenever `force_redraw` is true (every 4 ticks and every key tick), blanks the 14-line menu rectangle with filled black directly in the visible active buffer right before redrawing menu text.
4. Per-tick diag frame/marker (`build_candidate_port25_ladder_fix.py:457-471`): Calls 4x `draw_line` and `draw_string` unconditionally every keyboard tick directly to the active visible buffer.

### (F1) Large-Screen Handling & Font Scaling
- Core built-in font is 8x16 (`gui_draw.h:56-57`). Under `THUMB_FW` (DIGIC 6), `core/gui_draw.c:701-784` horizontally upscales 8 px to 14 px via bit arithmetic and 2x vertically to 32 px (`FONT_WIDTH 14`, `FONT_HEIGHT 32` in `gui_draw.h:68-69`).
- No `CAM_*` font or menu scale defines exist in `camera.h` or any sibling platform (`g7x`, `g5x`, `sx60hs`).
- `gui_menu.c:226-228` does not use `CAM_SCREEN_WIDTH`/`BUFFER_WIDTH`; layout is calculated at runtime from `camera_screen` (`w = disp_width - 20`, `num_lines = (height/rbf_font_height)-1`).
- Sibling ports (`g7x/lib.c:303-358`, `g5x/lib.c:162-204`) update `camera_screen` dimensions but leave built-in font size unchanged; large screens rely on SD card RBF files (`conf.menu_rbf_file`), which is excluded under Phase 0.
- **Decision for GUI3 [INFERRED]**: Specify an integer 2x scaling of the built-in 8x16 font for the menu draw path only (`16x32` pixels, expanding each font bit to a 2x2 pixel block). On the 900x600 display, `num_lines = (600/32)-1 = 17` lines and `w = 880` px (fitting ~53 characters across), cleanly filling the screen without SD card dependencies.

### (F3) Menu Background Colour and Opacity Trace
1. `conf.menu_color.bg` (`core/conf.c:201`) defaulted to `IDX_COLOR_GREY_DK = 13` (`gui_draw.h:24`).
2. `core/gui_menu.c:969` passes `conf.menu_color` to `user_color()`, which calls `chdkColorToCanonColor` (`gui_draw.c:1406`).
3. `platform/generic/palette.c:26` maps index 13 to `0xb4` (luma 64, opacity 255); index 1 (`COLOR_BLACK`) maps to `0xFF` (`palette.c:14`, luma 0, opacity 255).
4. `core/gui_draw.c:15-19` macro `CALC_YUV_LUMA_OPACITY_FOR_COLOR` calculates `luma` and `opacity = (color & 0xf) ? 255 : color`. For `0xb4` and `0xFF`, opacity evaluates to 255.
5. `core/gui_draw.c:78` writes opacity `o` directly to `obu[offset]`.
- **Actual Root Cause**: **Opacity not written** (`core/gui_menu.c:731-752, 967-1077`). `gui_menu_draw_initial()` draws no outer menu box; `gui_menu_draw()` only writes opacity for active item rows (rows 0..8). Unpainted lines 9..13 and margins remained at opacity 0 (fully transparent), revealing the underlying stock Canon UI. The dark grey luma (64) on active rows compounded the translucent appearance.
- **Fix for GUI3**: Retain `conf.menu_color.bg.col = 1` (`COLOR_BLACK`) in `conf_restore()` so text backgrounds are solid black (luma 0). Paint the full opaque menu rectangle once on menu initialization (`gui_menu_draw_initial` / `entered_alt`), eliminating per-tick clears.

### Geometry Decision
- **Display Geometry**: `dt=12`, `900x600`, `buffer_width 928` recorded as **`VERIFIED`** based on owner trial PORT-36 video evidence (`docs/PORT36_GUI_GEOMETRY.md:4,10,82`).
- **Dropped Assumption**: The historical G7X/G5X assumption of `displaytype 1,2,8,9,10` (`720x480`, `buffer_width 736`) is formally **DROPPED** for the G3X LCD panel.
- **Firmware Addresses**: All hardware symbols verified from `reference/finsig_gm110c/stubs_entry.S` (`displaytype` line 187, `active_bitmap_buffer` line 186, `bitmap_buffer` line 188, `transfer_src_overlay` line 352 `[FINSIG]`). No new ROM ranges read.

## Adapted-Address Table (PORT-37)

The candidate `G3X_GUI3=1` implementation reuses existing verified and FINSIG addresses from PORT-35 and PORT-36. Zero new ROM ranges were read.

| Address | Name | Source FINSIG / Sibling path:line | Label | Purpose in GUI3 |
|---|---|---|---|---|
| `0x00009740` | `displaytype` | `reference/finsig_gm110c/stubs_entry.S:187` | FINSIG | Queried in Mode 12 resolution detection and diagnostic overlay |
| `0x0000D2A4` | `active_bitmap_buffer` | `reference/finsig_gm110c/stubs_entry.S:186` | FINSIG | Active buffer index tracking in `check_gui_needs_redraw` & guard pixel |
| `0x0000D2A8` | `bitmap_buffer` | `reference/finsig_gm110c/stubs_entry.S:188` | FINSIG | Base pointer array for bitmap overlay drawing buffers |
| `0xFC380635` | `_transfer_src_overlay` | `reference/finsig_gm110c/stubs_entry.S:352`; `g7x/lib.c:15` | FINSIG | Refresh trigger called during `draw_restore()` on ALT exit |
| `0x5FC40000` | `opacity_buffer[0]` | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | Target for guard sentinel `0x42` at offset 0; hardware opacity buffer 0 |
| `0x5FB80000` | `opacity_buffer[1]` | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | Hardware opacity buffer 1 |
| `0x5FE80000` | `bitmap_buffer[0]` | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | Hardware UYVY bitmap overlay buffer 0 |
| `0x5FD00000` | `bitmap_buffer[1]` | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | Hardware UYVY bitmap overlay buffer 1 |
| `0x00368880` | `G3X_GUI_HEAP_START` | `docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD` | VERIFIED | Raised DryOS heap base providing >22 KB clearance for linked `_end` |
| `0xD20B0884` | GPIO LED MMIO | `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` | VERIFIED | Power / card-access LED MMIO register for resident heartbeat |
| `0xBFE14A3D` | `CreateTask` | `reference/finsig_gm110c/stubs_entry.S:200` | FINSIG | Firmware task creation veneer for resident heartbeat task |
| `0xFC0D0126` | `sub_fc0d0126` | `docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json` | VERIFIED | Handoff point where heartbeat task is spawned |
| `0xFC31BF84` | `SleepTask` | `reference/finsig_gm110c/stubs_entry.S:307` | FINSIG | Heartbeat task cadence delay veneer |
| `0xFC1283D2` | `taskcreate_physw` | `reference/finsig_gm110c/stubs_entry.S:335` | FINSIG | Keyboard PhySw replacement entry point |

## Candidate Build Artifacts (PORT-37)

Built with pinned toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3` via `scripts/build_candidate_gui3.py`:

| Candidate Flag | DISKBOOT Size | DISKBOOT SHA-256 | Witness Addr | Linked `_end` | Heap Clearance |
|---|---|---|---|---|---|
| `G3X_GUI3=1` (plain) | 103,569 B | `4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638` | `0x0035CED0` | `0x00362F10` | 22,896 B |
| `G3X_GUI3=1` + `G3X_GUI_DIAG=1` | 103,745 B | `de066f7198ed8f56e055807eb25880c394386eaeab5aac6384cb1fa607308ed4` | `0x0035CF80` | `0x00362FC0` | 22,720 B |

### Invariance of Prior Builds
- **Default**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (118,001 B) — **BYTE-IDENTICAL**
- **RESIDENT**: `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` (124,561 B) — **BYTE-IDENTICAL**
- **OSD**: `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` (124,833 B) — **BYTE-IDENTICAL**
- **KBD**: `a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33` (124,801 B) — **BYTE-IDENTICAL**
- **OSD2**: `20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57` (125,329 B) — **BYTE-IDENTICAL**
- **GUI**: `1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272` (103,057 B) — **BYTE-IDENTICAL**
- **GUI2**: `4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071` (103,345 B) — **BYTE-IDENTICAL**

## Evidence Manifest Check
- **New ROM Ranges Read**: `0`
- No new firmware ROM ranges or slices were read for PORT-37. All symbol addresses are derived from existing FINSIG exports (`reference/finsig_gm110c/stubs_entry.S`) or verified evidence manifests (`port34_evidence_manifest.json`, `port35_manifest.json`).

## Owner Trial and Recovery Plan (G3X_GUI3 Candidate)

**Safety & Scope**: Canon PowerShot G3 X (`GM1.10C`, PID `0x32A8`). Phase 0 read-only rules apply (`docs/SAFETY.md`): offline host builds only, owner executes trial by hand. Binary execution is strictly RAM-only (`DISKBOOT.BIN` in DRAM; zero flash ROM/NVRAM writes; default build unchanged: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`, 118,001 B). Recovery: battery pull (remove NB-10L battery $\ge 10\text{ s}$ to clear DRAM; short tap $<0.5\text{ s}$ boots stock Canon firmware). Boot method: held press (press & hold Power ~1–2 s through ladder until stock UI loads; $\le 2$ power-ons/session).

### Candidate Binaries (Sources at Commit `4a06f75`)
Built via `scripts/build_candidate_gui3.py` with pinned toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3`:
- **`G3X_GUI3=1` (plain candidate)**: Commit `4a06f75`, 103,569 B, SHA-256 `4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638` (witness `0x0035CED0`, clearance `22,896` B, build: `python3 -B scripts/build_candidate_gui3.py --gui3 --out-dir candidate_port37_gui3`)
- **`G3X_GUI3=1` + `G3X_GUI_DIAG=1` (DIAG variant)**: Commit `4a06f75`, 103,745 B, SHA-256 `de066f7198ed8f56e055807eb25880c394386eaeab5aac6384cb1fa607308ed4` (witness `0x0035CF80`, clearance `22,720` B, build: `python3 -B scripts/build_candidate_gui3.py --gui3 --gui-diag --out-dir candidate_port37_gui3_diag`)

### Numbered Trial Checklist
1. `[ ] PASS  [ ] FAIL` **Heartbeat as in PORT-36**: Release Power after held press; rear green LED blinks ~1.0 Hz single blink (`100 ms ON / 900 ms OFF`), stock Canon UI loads. Expected: steady heartbeat, stock UI operational.
2. `[ ] PASS  [ ] FAIL` **ALT on/off**: Press Playback (`KEY_PLAYBACK`); rear LED switches to ~1.0 Hz double blink (ALT on). Press again; returns to single blink. Expected: ALT toggles reliably.
3. `[ ] PASS  [ ] FAIL` **Open the menu**: In ALT mode, press Menu (`KEY_MENU`); CHDK Main Menu opens. Expected: menu displays promptly on LCD.
4. `[ ] PASS  [ ] FAIL` **No flicker (idle & nav)**: Menu holds still for $\ge 10\text{ s}$ with no key pressed; repaints only on navigation. Expected: zero periodic flicker/tearing at idle; smooth redraw on D-pad Up/Down.
5. `[ ] PASS  [ ] FAIL` **F1 (large font & dimensions)**: Menu fills most of 900x600 LCD (~880x576 px, 17 rows); 16x32 text is readable at arm's length. Expected: large crisp font filling panel without margin clipping.
6. `[ ] PASS  [ ] FAIL` **F3 (opaque black background)**: Menu background is solid black (`COLOR_BLACK`); zero stock Canon UI showing through text or unpainted rows. Expected: 100% opaque black background.
7. `[ ] PASS  [ ] FAIL` **F2 (box covers all items)**: Outer box completely encloses all items, including bottom entries (*Script*, *CHDK Settings*, *Miscellaneous Stuff*). Expected: zero items clipped outside box.
8. `[ ] PASS  [ ] FAIL` **Redraw recovery after stock overwrite**: After stock Canon UI redraws (toggle DISP button or half-press shutter), menu comes back promptly. Expected: prompt menu restore via sentinel check.
9. `[ ] PASS  [ ] FAIL` **Close menu and leave ALT**: Press Menu to close CHDK menu, press Playback to leave ALT. Expected: clean OSD erase, full stock Canon controls restore.
10. `[ ] PASS  [ ] FAIL` **DIAG variant only**: Outer frame sits precisely on LCD physical edges; marker reads `dt=12 w=900 bw=928 h=600`; neither frame nor text flickers. Expected: perimeter aligned, marker static.

### INFERRED Assumptions Mapping & Owner Observation Notes
- **B1/B2 (Sentinel repaint & idle stability)**: Confirmed by Step 4 (static idle $\ge 10\text{ s}$) and Step 8 (prompt redraw on stock overwrite); refuted if idle flicker persists or menu fails to recover.
- **F1 (Integer 2x font scaling 16x32)**: Confirmed by Step 5 (fills 900x600, readable at arm's length); refuted if text is tiny/illegible or clipped.
- **F3 (Opacity not written root cause & solid black)**: Confirmed by Step 6 (opaque black background, zero stock UI show-through); refuted if menu remains translucent.
- **F2 (Full bounding box coverage)**: Confirmed by Step 7 (all 17 items inside box); refuted if bottom items escape.
- **B2 (DIAG edge alignment & static marker)**: Confirmed by Step 10 (frame at LCD boundary, marker readable, no flicker); refuted if offset or blinking.
- **Owner Notes**: Record PASS/FAIL for each step. Note text legibility at arm's length, background opacity, navigation responsiveness, and redraw speed after DISP toggle. A short phone video (~10–20 s) capturing idle stillness, navigation, and DISP toggle is preferred.

