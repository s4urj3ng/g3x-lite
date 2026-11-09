# PORT-38: CHDK GUI4 Candidate Build & Owner Trial Plan (Font 2x, Opaque Black, Readable Title)

## Overview
Owner trial and recovery plan for candidate `G3X_GUI4=1` (PowerShot G3 X `GM1.10C`, PID `0x32A8`).
`G3X_GUI4=1` implies `G3X_GUI3=1`, `G3X_GUI2=1`, `G3X_GUI=1`, `G3X_KBD=1`, `G3X_OSD2=1`, `G3X_RESIDENT=1`, `G3X_POWERON_FIX=1`, and `G3X_LED_LADDER=1`.
The default build and all prior candidate builds remain byte-identical.

Candidate fixes verified against owner trial PORT-37 findings:
1. **F1 Fix (Real 2x Menu Font & Advance)**: Native G3X font driver in `libplatformsub_candidate.a` directly providing `rbf_draw_char`, `rbf_char_width`, `rbf_font_height`, `rbf_str_width`, `rbf_draw_string_len`, and `rbf_draw_menu_header`. Renders true 16x32 pixel glyphs (2x2 pixel blocks from 8x16 font table), returns exact 16 px character advance width (`rbf_char_width = 16`, return `16`), and sets 32 px row pitch (`rbf_font_height = 32`). Completely eliminates ld `--wrap` font dependencies.
2. **F3 Fix (Solid Opaque Black Full-Box Fill)**: Replaces bypassed intra-unit `--wrap=gui_menu_draw_initial` by directly painting the full menu bounding box (`bx: 10..889, by: 12..587`, width 880 px, height 576 px) with opaque black (`COLOR_BLACK`, UYVY `0x00800080`) and opacity 255 written directly into `opacity_buffer[active_bitmap_buffer & 1]`. Zero photo show-through; completely eliminates green strips above the title and below the last item.
3. **Title Bar Fix (High-Contrast Legible Header)**: In `conf_restore()`, explicitly sets `conf.menu_title_color.bg.col = 1` (`COLOR_BLACK`), `conf.menu_title_color.bg.type = 1`, `conf.menu_title_color.fg.col = 2` (`COLOR_WHITE`), `conf.menu_title_color.fg.type = 1`, and `conf.menu_center = 0`. Title is painted as crisp white text on solid black background anchored at `y = 12` matching the top of the full menu box.
4. **PORT-37 Zero-Flicker & Steps 8/9 Preservation**: No periodic timer force redraw is present; menu remains completely static at idle. Sentinel byte `0x42` at `opacity_buffer[active_bitmap_buffer & 1][0]` restores menu overlay on stock Canon UI redraws (Step 8); closing menu and exiting ALT cleanly clears overlay and restores stock Canon controls (Step 9).

---

## Candidate Binaries

Built with pinned toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3` via `scripts/build_candidate_gui4.py`:

| Candidate Configuration | DISKBOOT Size | DISKBOOT SHA-256 | Boot Witness | Linked `_end` | Heap Clearance |
|---|---|---|---|---|---|
| **`G3X_GUI4=1` (Plain Candidate)** | 102,241 B | `14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd` | `0x0035C9A0` | `0x003629D0` | 24,240 B |
| **`G3X_GUI4=1` + `G3X_GUI_DIAG=1` (DIAG Variant)** | 102,417 B | `a4bfdeeae630e5fcac07e4b206ff2c64acea28e77f22bad49996bea460d35e1d` | `0x0035CA50` | `0x00362A80` | 24,064 B |

DryOS heap base is raised to `0x00368880` (`docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD`), providing $>24\text{ KB}$ clearance above linked `_end`.

---

## Invariance of Prior Builds

| Configuration | Output Size | SHA-256 Checksum | Invariance Status |
|---|---|---|---|
| **Default Build** | 118,001 B | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-37 GUI3** | 103,569 B | `4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-36 GUI2** | 103,345 B | `4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-35 GUI** | 103,057 B | `1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-35 OSD2** | 125,329 B | `20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-34 KBD** | 124,801 B | `a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-33 OSD** | 124,833 B | `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` | **BYTE-IDENTICAL** [VERIFIED] |
| **PORT-32 RESIDENT**| 124,561 B | `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` | **BYTE-IDENTICAL** [VERIFIED] |

---

## Safety & Scope Constraints
- **Hardware Target**: Canon PowerShot G3 X (`GM1.10C`, PID `0x32A8`, DIGIC 6).
- **Phase 0 Compliance**: Strictly offline host builds. The camera is not connected to host. Binary deployment and execution are performed manually by the owner (`docs/SAFETY.md`).
- **RAM Execution Only**: `DISKBOOT.BIN` executes solely in DRAM. No flash ROM, NVRAM, or persistent camera storage is modified.
- **Card-Write Exclusion**: `conf_save` and file logging are disabled (`conf_candidate.c:37-43`, `gui_candidate.c:83`). Zero SD card writes occur at runtime.
- **Boot Protocol**: Held-press boot (press and hold Power button for ~1–2 seconds through breadcrumb ladder until stock UI loads; $\le 2$ boots per session).
- **Run Mode**: Playback mode (boot directly in Playback mode or switch to Playback).
- **Recovery Protocol**: Battery pull (remove NB-10L battery $\ge 10\text{ s}$ to fully discharge DRAM; short tap $<0.5\text{ s}$ boots stock Canon firmware cleanly).

---

## Owner Trial Numbered Checklist (G3X_GUI4 Candidate)

Copy this checklist to record trial observations:

1. `[ ] PASS  [ ] FAIL` **Boot & Heartbeat (Held-press boot in Playback mode)**:
   - *Action*: Insert SD card containing `DISKBOOT.BIN` (SHA-256 `14456b08fca8...`), hold Power button ~1–2 seconds until stock Playback UI loads.
   - *Expected*: Rear green LED blinks steady ~1.0 Hz single blink (`100 ms ON / 900 ms OFF`). Stock Canon Playback photo displays cleanly.

2. `[ ] PASS  [ ] FAIL` **ALT Entry (Playback button)**:
   - *Action*: Press Playback button (`KEY_PLAYBACK`).
   - *Expected*: Rear LED cadence changes to ~1.0 Hz double blink (`100 ms ON / 100 ms OFF / 100 ms ON / 700 ms OFF`), confirming ALT mode active.

3. `[ ] PASS  [ ] FAIL` **Open CHDK Menu (Menu button)**:
   - *Action*: Press Menu button (`KEY_MENU`) while in ALT mode.
   - *Expected*: CHDK Main Menu opens promptly on the LCD screen.

4. `[ ] PASS  [ ] FAIL` **F1 Check: Text Visibly 2x (16x32 Glyph Raster & 16 px Advance)**:
   - *Action*: Observe menu item labels and text spacing.
   - *Expected*: Text glyphs are crisply rendered at true 16x32 pixel resolution (visibly twice the size of 8x16 font, easily legible at arm's length). Characters do NOT overlap or appear squished horizontally (full 16 px advance width).

5. `[ ] PASS  [ ] FAIL` **Layout Geometry: Menu Fills Most of Screen (880x576 px on 900x600 LCD)**:
   - *Action*: Observe menu box dimensions and margins.
   - *Expected*: Menu box spans from `x = 10` to `x = 889` (width 880 px, leaving 10 px margin on left/right) and `y = 12` to `y = 587` (height 576 px, leaving 12 px margin top/bottom), comfortably filling $\approx 94\%$ of the 900x600 display area without clipping.

6. `[ ] PASS  [ ] FAIL` **F3 Check: Solid Opaque Black Menu Box (Zero Photo Show-Through, No Green Strips)**:
   - *Action*: Inspect the background behind the menu items, header row, and outer box.
   - *Expected*: Background is solid opaque black across the entire 880x576 rectangle (`opacity = 255`). Zero photo show-through from Playback image. Specifically, the two green strips observed in PORT-37 above the title and below the last item are COMPLETELY GONE.

7. `[ ] PASS  [ ] FAIL` **Title Bar Check: High-Contrast White Text on Solid Black Header**:
   - *Action*: Inspect the title bar at the top of the menu (`CHDK Main Menu`).
   - *Expected*: Clean, legible white text on a solid black background (`conf.menu_title_color.bg = COLOR_BLACK`, `conf.menu_title_color.fg = COLOR_WHITE`). No garbled dark text or white bar artifact.

8. `[ ] PASS  [ ] FAIL` **Zero-Flicker at Idle**:
   - *Action*: Leave menu open with no buttons pressed for $\ge 10\text{ seconds}$.
   - *Expected*: Overlay remains completely motionless and rock-steady. Zero periodic tearing, blinking, or screen flicker (no periodic `force_redraw`).

9. `[ ] PASS  [ ] FAIL` **Menu Navigation & Submenus**:
   - *Action*: Press Up / Down on directional pad; press Right / SET to enter submenus; press Left / Menu to return.
   - *Expected*: Selection bar moves smoothly and responsively. Rows redraw cleanly without whole-screen flashing. Submenus open and display with the same 16x32 font, opaque black background, and legible header.

10. `[ ] PASS  [ ] FAIL` **Scrolling Submenu & Scrollbar (Scrollbar Inside Black Box)**:
    - *Action*: Navigate into a menu or submenu with $>17$ items (or scrollable list).
    - *Expected*: Scrollbar appears on the right (`x = 890..898`). The solid opaque black fill covers the entire layout including the scrollbar (`x = 10..898`, width 889 px, height 576 px). Scrollbar thumb and track remain entirely inside the opaque black background with zero photo show-through.

11. `[ ] PASS  [ ] FAIL` **Step 8: Redraw Recovery on Stock Canon Overwrite (DISP / Half-Press)**:
    - *Action*: While CHDK menu is open, toggle DISP button or lightly tap shutter half-press to trigger stock Canon OSD update.
    - *Expected*: CHDK menu restores promptly without freezing or leaving corrupt artifacts (detected via guard sentinel byte check).

12. `[ ] PASS  [ ] FAIL` **Step 9: Clean Menu Close & ALT Exit (Stock Controls Restored)**:
    - *Action*: Press Menu button to close menu; press Playback button to exit ALT mode.
    - *Expected*: CHDK menu and overlay are completely erased (`draw_restore()`). Rear LED returns to steady single blink. Full stock Canon camera controls and Playback review functions operate normally. No black box is redrawn on subsequent buffer toggles or guard updates while in ALT with menu closed.

13. `[ ] PASS  [ ] FAIL` **Battery-Pull Recovery Verification**:
    - *Action*: Open battery door and remove NB-10L battery for $\ge 10\text{ seconds}$; reinsert battery; short tap ($<0.5\text{ s}$) Power button.
    - *Expected*: Camera powers up directly into stock Canon firmware without executing CHDK.

---

## Code References and Evidence Manifest

All assumptions and implementations are mapped with exact citations:

| Item / Assumption | Citation (path:line) | Label | Runtime Verification / Effect |
|---|---|---|---|
| Native 16x32 font raster | `scripts/build_candidate_gui3.py:270-285` | VERIFIED | Doubles 8x16 font bits into 2x2 blocks: `px = x + ((7-b)<<1)`, `yt = y + (i<<1)` |
| Character advance width 16 px | `scripts/build_candidate_gui3.py:263,308` | VERIFIED | `rbf_char_width(int ch) { return 16; }`, `rbf_draw_char` returns `16` |
| Row pitch 32 px | `scripts/build_candidate_gui3.py:258,318` | VERIFIED | `rbf_font_height(void) { return 32; }` |
| Direct font routing (no `--wrap`) | `scripts/build_candidate_gui3.py:250-330,900-925` | VERIFIED | `rbf_*` defined in `libplatformsub_candidate.a`, bypassing `libfont.a:rbf_font.o` |
| Full menu bounding box dimensions | `scripts/build_candidate_gui3.py:202-230` | VERIFIED | `bx = 10`, `by = 12`, `bw = 880` (non-scrolling) / `889` (scrolling), `bh = 576` (`total_h = 18 * 32 = 576`) |
| Opacity 255 buffer write | `scripts/build_candidate_gui3.py:222-226` | VERIFIED | Writes `255` into `opacity_buffer[active_bitmap_buffer & 1]` for all menu pixels |
| UYVY Black buffer write | `scripts/build_candidate_gui3.py:215-220` | VERIFIED | Writes `0x00800080` (UYVY black) into `bitmap_buffer[active_bitmap_buffer & 1]` |
| Title bar color configuration | `tools/build_candidate_port25_ladder_fix.py:1145-1152` | VERIFIED | `conf.menu_title_color.bg.col = 1` (Black), `fg.col = 2` (White), `conf.menu_center = 0` |
| Sibling opacity buffer architecture | `chdk-port/platform/g7x/lib.c:289-296`; `g5x/lib.c:28-33` | HISTORICAL_CHDK | `vid_get_opacity_active_buffer() { return (void *)opacity_buffer[active_bitmap_buffer&1]; }` |
| DIGIC 6 active buffer requirement | `chdk-port/platform/g7x/platform_camera.h:143`; `g5x:83` | HISTORICAL_CHDK | `DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY 1` |
| Zero periodic force redraw | `scripts/build_candidate_gui3.py:170-195` | VERIFIED | `gui_redraw(0)` called on normal ticks; `gui_redraw(1)` only on ALT entry/exit |
| Sentinel byte overlay recovery | `scripts/build_candidate_gui3.py:180-185` | VERIFIED | Writes `0x42` to byte 0; triggers repaint on mismatch |
| Mode 12 900x600 display geometry | `docs/PORT36_GUI_GEOMETRY.md:4,10` | VERIFIED | `displaytype = 12`, `width = 900`, `height = 600`, `buffer_width = 928` |
| ROM Opacity buffer addresses | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | `0x5FC40000` (buffer 0), `0x5FB80000` (buffer 1) |
| ROM Bitmap overlay addresses | `evidence/port35_manifest.json` (`PORT35-ROM-BMPDDEV`) | VERIFIED | `0x5FE80000` (buffer 0), `0x5FD00000` (buffer 1) |
| Raised DryOS heap base | `docs/port34_evidence_manifest.json: PORT34-ROM-HEAP-KBD` | VERIFIED | `0x00368880` provides 24,240 B clearance above `_end` `0x003629D0` |
| Zero new ROM ranges read | Offline repository audit | VERIFIED | `0` new ROM slices read; all symbols from verified manifests |

---

## Build Verification Instructions (Offline Host)

To reproduce the candidate build and verify byte invariance of default and prior candidates:
```bash
# 1. Run PORT-38 geometry, font, opacity, and build invariance test suite:
python3 -m unittest tests/test_port38_gui_geometry.py

# 2. Run PORT-37 flicker regression test suite:
python3 -m unittest tests/test_port37_gui_flicker.py

# 3. Build candidate DISKBOOT.BIN:
python3 -B scripts/build_candidate_gui4.py --out-dir /tmp/candidate_port38_gui4

# 4. Verify SHA-256 and size:
sha256sum /tmp/candidate_port38_gui4/DISKBOOT.BIN
# Output: 14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd  102241 bytes
```
