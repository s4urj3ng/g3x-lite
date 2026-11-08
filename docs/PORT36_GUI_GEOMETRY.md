# PORT-36: CHDK Menu Geometry and Opacity Corrections (G3X_GUI2=1)

## Overview
This document records the constants, addresses, sibling adaptations, and root causes for candidate `G3X_GUI2=1`, resolving display faults F1, F2, and F3 observed during the owner's PORT-35 hardware trial (2026-11-08, main commit `16bec70`).

## Evidence & ROM Reads
All GM1.10C display dimensions and hardware framebuffer addresses were established by the bounded ROM slice `PORT35-ROM-BMPDDEV` (`0xFC18347E..0xFC18381F`, SHA-256 `5b04719fde94ae9a967beb93e1f64836fd417de35d0cc613536c3c79b07fcadf`) in `evidence/port35_manifest.json`. Reference `reference/finsig_gm110c` (FINSIG) symbols were verified for `displaytype`. **No ROM was read for PORT-36; all values are from PORT35-ROM-BMPDDEV or sibling headers.**

## Compile-Time Framebuffer and Screen Geometry
Compile-time constants `CAM_BITMAP_WIDTH` (736), `CAM_BITMAP_HEIGHT` (480), `CAM_SCREEN_WIDTH` (720), and `CAM_SCREEN_HEIGHT` (480) in `chdk-port/platform/g3x/platform_camera.h:89-94` remain strictly stock compile-time values. No compile-time 928 or 900x600 overrides exist in the GUI2 build. All Mode 12 geometry adjustments (900x600, stride 928) are activated strictly at runtime by `g3x_osd2_update_screen_dimensions()` (`chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:177-220`) when `displaytype == 12`.

## Constant and Address Adaptation Table

| Name | Old Value | New GM1.10C Value | Label | Sibling Path:Line | Takes Effect in GUI2 Build (File:Line) | Fault Addressed | Owner Observation (Confirm / Refute) |
|---|---|---|---|---|---|---|---|
| `camera_screen.disp_left` | 0 | 0 | INFERRED | `chdk-port/platform/g5x/lib.c:195` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:216; chdk-port/core/gui_menu.c:227` | F1 | Confirm: Left margin stays at 0 (CAM_TS_BUTTON_BORDER=0). Refute: Left edge offset. |
| `camera_screen.disp_right` | 719 | width - 1 | INFERRED | `chdk-port/platform/g5x/lib.c:195` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:217` | F1 | Confirm: Extends right margin to active screen width - 1 (899 in Mode 12; 719 on LCD). Refute: Right edge clipped early. |
| `camera_screen.disp_width` | 720 | width | INFERRED | `chdk-port/platform/g5x/lib.c:196` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:218; chdk-port/core/gui_menu.c:228` | F1 | Confirm: In Mode 12, disp_width becomes 900 expanding menu width w to 880 px; on 720x480 LCD, resets to 720 (w = 700 px). Refute: Menu width unchanged in Mode 12. |
| `update_screen_dimensions` | unexported | REMOVED | INFERRED | `chdk-port/platform/g7x/lib.c:303-358; chdk-port/platform/g5x/lib.c:162-204` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h` | None (uncalled) | Core code never calls update_screen_dimensions; g3x_gui_kbd_redraw runs g3x_osd2_update_screen_dimensions per tick. Removed no-op wrapper. |
| `conf.menu_color.bg.col` | 13 (IDX_COLOR_GREY_DK) | 1 (COLOR_BLACK) | INFERRED | None (RAM-only conf default) | `tools/build_candidate_port25_ladder_fix.py:generate_conf_candidate_c` (`conf_restore`) | F3 | Changes menu text row background default from dark grey (0xb4, luma 64) to solid black (0xff, luma 0, opacity 255). Confirm: Menu rows solid black. Refute: Translucent rows persist. |
| Menu box background (`draw_rectangle`) | absent (unpainted rows 9..13) | full 14-line filled box (lines 0..14) | INFERRED | `chdk-port/core/gui_menu.c:740` (draw_rectangle pattern) | `tools/build_candidate_port25_ladder_fix.py:generate_gui_candidate_c` (`g3x_gui_kbd_redraw`) | F2, F3 | Fills lines 0..14 with COLOR_BLACK (opacity 255) before gui_redraw, occluding underlying Canon UI. Confirm: Solid background across full menu height. Refute: Canon UI visible below row 8. |

*Notes on font and geometry*: Built-in font height of 32 is cited from `chdk-port/core/gui_draw.h:68-69` (`#define FONT_HEIGHT 32`, `#define FONT_WIDTH 14` under `THUMB_FW`) and `chdk-port/lib/font/rbf_font.c:251-252` (`rbf_font->hdr.height = FONT_HEIGHT`). Old `disp_left`/`disp_right`/`disp_width` values were 0/719/720 (`CAM_TS_BUTTON_BORDER` defaults to 0 in `include/camera.h:88`; 10 is `CAM_MENU_BORDERWIDTH` in `include/camera.h:83`). Citation `chdk-port/platform/g5x/lib.c:195-196` is confirmed. PORT-35's values were wrong because `g3x_osd2_update_screen_dimensions()` updated `camera_screen.width` but omitted resetting `disp_left`/`disp_right`/`disp_width`, leaving `disp_width` clamped to 720 px. Default-case stride remains 736 words; no 928 default override exists.

## Tracing Menu Background Opacity (Fault F3)
1. Conf / Menu defaults: `core/conf.c:201` defines `conf.menu_color`: `CONF_INFOC(55, conf.menu_color, CONF_DEF_VALUE, IDX_COLOR_GREY_DK, IDX_COLOR_WHITE, 1, 1)` with `IDX_COLOR_GREY_DK = 13` (`core/gui_draw.h:24`). OSD/override colors in `conf.c:198-200,207` use `IDX_COLOR_GREY_DK_TRANS = 18` (`core/gui_draw.h:29`).
2. Menu color conversion: `core/gui_menu.c:969` evaluates `cl = user_color((gui_menu_curr_item==imenu) ? conf.menu_cursor_color : conf.menu_color)`.
3. Canon color lookup: `core/gui_draw.c:1412-1418` (`user_color`) converts `cc.bg` via `chdkColorToCanonColor` (lines 1406-1410), indexing `chdk_colors` which points to `ply_colors` (`core/gui_draw.c:1384`).
4. Palette mapping: `platform/generic/palette.c:26` maps index 13 (`IDX_COLOR_GREY_DK`) to byte `0xb4`; index 1 (`COLOR_BLACK`) maps to byte `0xFF` (`platform/generic/palette.c:14`; `include/palette.h:15`).
5. Opacity computation: `core/gui_draw.c:15-19` macro `CALC_YUV_LUMA_OPACITY_FOR_COLOR(color, luma, opacity)` tests `(color & 0xf) ? 255 : color`.
   - For `0xb4` (index 13): `(0xb4 & 0xf) == 4 != 0`, yielding opacity 255 and luma `0x40` (64, dark grey).
   - For `0xFF` (index 1, `COLOR_BLACK`): `(0xff & 0xf) == 0xf != 0`, yielding opacity 255 and luma `0x00` (0, solid black).
6. Opacity write: `core/gui_draw.c:78` writes opacity `o` directly to hardware opacity buffer (`obu[offset] = o;`).
7. Why the owner saw translucency despite index 13 evaluating to 255:
   - `core/gui_menu.c:731-752` (`gui_menu_draw_initial`) draws NO outer solid background box before drawing menu text.
   - `core/gui_menu.c:967-1077` renders PER-ROW backgrounds strictly behind text and padding for the 9 active items (rows 0..8).
   - Lines 9..13 of the 14-line screen area were NEVER written by `gui_menu_draw`, leaving opacity buffer value 0 (completely transparent).
   - Underneath rows 0..8, dark grey (luma 64) over live viewfinder combined with transparent rows 9..13 produced the visual impression of a translucent background.
8. GUI2 fix:
   - In `conf_restore()` (`generate_conf_candidate_c()`), set RAM default `conf.menu_color.bg.col = 1` (`COLOR_BLACK`) and `conf.menu_color.bg.type = 1`.
   - In `g3x_gui_kbd_redraw` (`generate_gui_candidate_c()`), draw an opaque menu background box across lines 0..14 using `draw_rectangle` with `MAKE_COLOR(COLOR_BLACK, COLOR_BLACK)`, `RECT_BORDER0 | DRAW_FILLED`, writing opacity 255 and luma 0 across all 14 lines.

## Menu Box Drawing and Structure (Fault F2)
- In `core/gui_menu.c:731-752` (`gui_menu_draw_initial`), CHDK only draws the menu title header (line 751) and scrollbar background if `count > num_lines` (line 740). CHDK draws NO outer menu box.
- In `core/gui_menu.c:967-1077` (`gui_menu_draw`), CHDK renders PER-ROW backgrounds in a loop `for (imenu=gui_menu_top_item, i=0, yy=y; curr_menu->menu[imenu].text && i<num_lines; ++imenu, ++i, yy+=rbf_font_height())` via `rbf_draw_string_len` (`lib/font/rbf_font.c:428-436`), `gui_menu_draw_symbol` (lines 761-775), etc.
- In PORT-35, screen height was 480 px and font height 32 px (`core/gui_draw.h:68-69`), so `num_lines = (480-0)/32 - 1 = 14` (`core/gui_menu.c:226`). Root menu has 9 rows (`core/gui.c:2209-2223`, user menu disabled by default); `num_lines = 14 >= 9`, so CHDK rendered all 9 rows without any height mismatch.
- The apparent "short grey box" was NOT a box-height mismatch; it was unpainted transparent rows 9..13 allowing an underlying stock Canon UI box (a grey quick-control box spanning rows 0..5) to show through, while rows 6..8 (Script, CHDK Settings, Misc Stuff) drew over the dark camera preview background below Canon's box.
- The GUI2 fix follows directly from this cause: drawing a filled rectangle in `g3x_gui_kbd_redraw` across lines 0..14 with `COLOR_BLACK` (opacity 255) ensures solid coverage across all lines.

## Menu Width and Sizing (Fault F1)
- Formula at `core/gui_menu.c:226-228`:
  - Line 226: `num_lines = (camera_screen.height - camera_screen.ts_menu_border*2)/rbf_font_height()-1;`
  - Line 227: `x = camera_screen.disp_left  + camera_screen.menu_border_width;`
  - Line 228: `w = camera_screen.disp_width - camera_screen.menu_border_width*2;`
- Font size:
  - `core/gui_draw.h:68-69`: `#define FONT_WIDTH 14`, `#define FONT_HEIGHT 32` (under `THUMB_FW`)
  - `lib/font/rbf_font.c:251-252`: `rbf_font->hdr.height = FONT_HEIGHT;`, `rbf_font->width = FONT_WIDTH;`
- Why disp_* reset widens the menu in Mode 12, but leaves 720x480 LCD path unchanged:
  - In PORT-35, `g3x_osd2_update_screen_dimensions()` (`osd2_test_overlay.h:201-215`) updated `camera_screen.width` but omitted resetting `disp_left`/`disp_right`/`disp_width`, leaving `disp_width` clamped to 720 px (`w = 720 - 20 = 700 px`). On the 900x600 Mode 12 LCD panel, this left a ~200 px margin on the right.
  - In GUI2, `osd2_test_overlay.h:216-218` adds `camera_screen.disp_left = 0; camera_screen.disp_right = camera_screen.width - 1; camera_screen.disp_width = camera_screen.width;` (adapting `chdk-port/platform/g5x/lib.c:195-196`).
  - In Mode 12, `disp_width` resets to 900 px, expanding `w = 900 - 20 = 880 px`.
  - On the 720x480 LCD path, `disp_width` resets to 720 px (`w = 700 px`), so F1 is NOT widened on the 720x480 LCD path in this candidate without changing stride/buffer width or font scale (INFERRED).

## Root-Cause Notes

### Fault F1: Menu uses only a small part of the LCD [INFERRED]
gui_menu.c:226-228 sets w = disp_width - 20 (700 px at 720; 880 px at 900) with 14x32 font (gui_draw.h/rbf_font.c); disp_* reset widens menu in Mode 12.
On the 720x480 LCD path (disp_width 720->720), F1 is not fixed in this candidate without changing stride/buffer width or font scale (INFERRED).
Refutation observation: Live display shows dt=12 w=900 with menu spanning 880 px (confirms F1 fixed in Mode 12) vs dt=0 w=720 with 700 px menu (confirms F1 unfixed on LCD).

### Fault F2: Grey box is shorter than item list [INFERRED]
gui_menu.c:731-752 draws no outer box; lines 967-1077 draw per-row backgrounds for 9 items, leaving lines 9..13 unpainted at opacity 0 over Canon's UI (num_lines=14 >= 9 fits all items).
Fix fills the 14-line rectangle in g3x_gui_kbd_redraw with COLOR_BLACK (opacity 255) before gui_redraw.
Refutation observation: Menu shows only 5-6 rows of text with remaining items missing, indicating a font-height or num_lines calculation mismatch rather than unpainted rows.

### Fault F3: Background is translucent [INFERRED]
conf.c:201 sets IDX_COLOR_GREY_DK=13 -> palette.c:26 (0xb4, luma 64, opacity 255); translucent appearance was caused by luma 64 grey over unpainted opacity 0 rows 9..13.
Fix sets RAM default conf.menu_color.bg to COLOR_BLACK (0xff, luma 0, opacity 255) and paints full 14-line box opaque.
Refutation observation: Menu text remains visible over live-view video stream with opacity < 255 on rows 0..8 despite COLOR_BLACK.

## Trial Diagnostic
The 1-px border and `dt=%d w=%d bw=%d h=%d` string rendered by `g3x_gui_kbd_redraw` in GUI2 is a TRIAL DIAGNOSTIC to inspect the live hardware displaytype and screen geometry; it is NOT a fix for F1-F3.

## Candidate Artifacts and Build Command

- **Build command**:
  ```bash
  python3 -B tools/build_candidate_port25_ladder_fix.py --gui2 --out-dir candidate_port36_gui2
  ```
- **Candidate DISKBOOT.BIN SHA-256**:
  `4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071`
- **Candidate DISKBOOT.BIN size**: 103,345 bytes
- **Witness address**: `0x0035CDF0`
- **Linked `_end`**: `0x00362E30`
- **DryOS heap start**: `0x00368880` (clearance: 23,120 bytes)
