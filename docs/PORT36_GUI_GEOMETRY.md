# PORT-36: CHDK Menu Geometry and Opacity Corrections (G3X_GUI2=1)

## Overview
This document records the constants, addresses, sibling adaptations, and root causes for candidate `G3X_GUI2=1`, resolving display faults F1, F2, and F3 observed during the owner's PORT-35 hardware trial (2026-11-08, main commit `16bec70`).

## Evidence & ROM Reads
All GM1.10C display dimensions and hardware framebuffer addresses were established by the bounded ROM slice `PORT35-ROM-BMPDDEV` (`0xFC18347E..0xFC18381F`, SHA-256 `5b04719fde94ae9a967beb93e1f64836fd417de35d0cc613536c3c79b07fcadf`) in `evidence/port35_manifest.json`. Reference `reference/finsig_gm110c` (FINSIG) symbols were verified for `displaytype`. **No ROM was read for PORT-36; all values are from PORT35-ROM-BMPDDEV or sibling headers.**

## Constant and Address Adaptation Table

| Name | Old Value | New GM1.10C Value | Label | Sibling Path:Line | Takes Effect in GUI2 Build (File:Line) | Fault Addressed | Owner Observation (Confirm / Refute) |
|---|---|---|---|---|---|---|---|
| `CAM_SCREEN_WIDTH` | 720 | 900 | ROM | `evidence/port35_manifest.json:PORT35-ROM-BMPDDEV:0xFC18352A; chdk-port/platform/g5x/platform_camera.h:93; lib.c:162-204` | `chdk-port/core/camera_info.c:97` (static compile-time init; updated at runtime by `g3x_osd2_update_screen_dimensions`) | F1 | Confirm: Mode 12 LCD panel width is 900 px. Refute: Menu clipped horizontally. |
| `CAM_SCREEN_HEIGHT` | 480 | 600 | ROM | `evidence/port35_manifest.json:PORT35-ROM-BMPDDEV:0xFC18352A; chdk-port/platform/g5x/platform_camera.h:94; lib.c:162-204` | `chdk-port/core/camera_info.c:97` (static compile-time init; updated at runtime by `g3x_osd2_update_screen_dimensions`) | F1, F2 | Confirm: Mode 12 LCD panel height is 600 px. Refute: Menu clipped vertically. |
| `CAM_BITMAP_WIDTH` | 736 | 928 | ROM | `evidence/port35_manifest.json:PORT35-ROM-BMPDDEV:0xFC18352A; chdk-port/platform/g5x/platform_camera.h:91; lib.c:162-204` | `chdk-port/core/camera_info.c:99` (static compile-time init; updated at runtime by `g3x_osd2_update_screen_dimensions`) | F1 | Confirm: Framebuffer stride matches 928 words in Mode 12. Refute: Diagonal shearing. |
| `CAM_BITMAP_HEIGHT` | 480 | 600 | ROM | `evidence/port35_manifest.json:PORT35-ROM-BMPDDEV:0xFC18352A; chdk-port/platform/g5x/platform_camera.h:92; lib.c:162-204` | `chdk-port/core/camera_info.c:99` (static compile-time init; updated at runtime by `g3x_osd2_update_screen_dimensions`) | F1, F2 | Confirm: Framebuffer height matches 600 rows in Mode 12. Refute: Buffer overrun. |
| `camera_screen.disp_left` | 0 | 0 | INFERRED | `chdk-port/platform/g5x/lib.c:195` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:216; chdk-port/core/gui_menu.c:227` | F1 | Confirm: Left margin stays at 0 (CAM_TS_BUTTON_BORDER=0). Refute: Left edge offset. |
| `camera_screen.disp_right` | 719 | 899 | INFERRED | `chdk-port/platform/g5x/lib.c:195` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:217` | F1 | Confirm: Extends right margin to column width - 1 (899 in Mode 12). Refute: Right edge clipped early. |
| `camera_screen.disp_width` | 720 | 900 | INFERRED | `chdk-port/platform/g5x/lib.c:196` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:218; chdk-port/core/gui_menu.c:228` | F1 | Confirm: Effective change 720->900 expands menu width w = disp_width - 20 to 880 px in Mode 12. Refute: Menu clamped to 700 px. |
| `update_screen_dimensions` | unexported | REMOVED | INFERRED | `chdk-port/platform/g7x/lib.c:303-358; chdk-port/platform/g5x/lib.c:162-204` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h` | None (uncalled) | Core code never calls update_screen_dimensions; g3x_gui_kbd_redraw runs g3x_osd2_update_screen_dimensions per tick. Removed no-op wrapper. |
| `CALC_YUV_LUMA_OPACITY_FOR_COLOR` | `(color&0xf)?255:color` | `(color==0)?0:255` | INFERRED | None (siblings use stock `core/gui_draw.c:15-19`) | `chdk-port/core/gui_draw.c:77,125,202,205` (via `generate_gui_draw_candidate_c`) | F3 | Changes opacity of index 18 (0xb0, IDX_COLOR_GREY_DK_TRANS) from 176 to 255 (opaque). Confirm: Menu background solid black/dark grey. Refute: Translucency persists. |

*Notes on font and geometry*: Built-in font height of 32 is cited from `chdk-port/core/gui_draw.h:68-69` (`#define FONT_HEIGHT 32`, `#define FONT_WIDTH 14` under `THUMB_FW`) and `chdk-port/lib/font/rbf_font.c:251-252` (`rbf_font->hdr.height = FONT_HEIGHT`). Old `disp_left`/`disp_right`/`disp_width` values were 0/719/720 (`CAM_TS_BUTTON_BORDER` defaults to 0 in `include/camera.h:88`; 10 is `CAM_MENU_BORDERWIDTH` in `include/camera.h:83`). Citation `chdk-port/platform/g5x/lib.c:195-196` is confirmed. PORT-35's values were wrong because `g3x_osd2_update_screen_dimensions()` updated `camera_screen.width` but omitted resetting `disp_left`/`disp_right`/`disp_width`, leaving `disp_width` clamped to 720 px. Default-case stride remains 736 words; no 928 default override exists.

## Tracing Menu Background Opacity (Fault F3)
1. Conf / Menu defaults: `core/conf.c:201` defines `conf.menu_color`: `CONF_INFOC(55, conf.menu_color, CONF_DEF_VALUE, IDX_COLOR_GREY_DK, IDX_COLOR_WHITE, 1, 1)` with `IDX_COLOR_GREY_DK = 13` (`core/gui_draw.h:24`). OSD/override colors in `conf.c:198-200,207` use `IDX_COLOR_GREY_DK_TRANS = 18` (`core/gui_draw.h:29`).
2. Menu color conversion: `core/gui_menu.c:969` evaluates `cl = user_color((gui_menu_curr_item==imenu) ? conf.menu_cursor_color : conf.menu_color)`.
3. Canon color lookup: `core/gui_draw.c:1412-1418` (`user_color`) converts `cc.bg` via `chdkColorToCanonColor` (lines 1406-1410), indexing `chdk_colors` which points to `ply_colors` (`core/gui_draw.c:1384`).
4. Palette mapping: `platform/generic/palette.c:30,35` maps index 13 (`IDX_COLOR_GREY_DK`) to byte `0xb4`, index 18 (`IDX_COLOR_GREY_DK_TRANS`) to byte `0xb0`, and index 1 (`COLOR_BLACK`) to `0xFF` (`include/palette.h:15`).
5. Opacity computation: `core/gui_draw.c:15-19` macro `CALC_YUV_LUMA_OPACITY_FOR_COLOR(color, luma, opacity)` tests `(color & 0xf) ? 255 : color`.
   - For `0xb4` (index 13): `(0xb4 & 0xf) == 4 != 0`, yielding opacity 255.
   - For `0xb0` (index 18): `(0xb0 & 0xf) == 0`, yielding opacity `0xb0` = 176 (~69% alpha, translucent).
6. Opacity write: `core/gui_draw.c:78,126,140,202` writes opacity `o` directly to hardware opacity buffer (`obu[offset] = o;`).
7. Why the owner saw translucency despite index 13 evaluating to 255:
   - CHDK draws NO outer solid background box before drawing menu text (`core/gui_menu.c:731-752`, `gui_menu_draw_initial`).
   - CHDK renders PER-ROW backgrounds strictly behind text and padding (`core/gui_menu.c:967-1077`, `lib/font/rbf_font.c:428-436`).
   - Any elements using index 18 (`IDX_COLOR_GREY_DK_TRANS`), including `conf.space_color` (`core/conf.c:207`) and OSD overlays (`core/conf.c:198-200`), had opacity 176 (translucent).
   - On the physical camera during ALT mode entry, the underlying Canon live viewfinder overlay was active underneath CHDK's transparent OSD2 layer. The Canon UI elements showing through unpainted gaps and translucent elements produced the visual impression of a translucent menu background.
8. GUI2 fix: `generate_gui_draw_candidate_c` overrides `CALC_YUV_LUMA_OPACITY_FOR_COLOR` to `opacity = (color == COLOR_TRANSPARENT) ? 0 : 255;`.
   - In `ply_colors[]` [0..19], exactly index 18 (`0xb0`, `IDX_COLOR_GREY_DK_TRANS`) changes from opacity 176 to 255; index 0 (`COLOR_TRANSPARENT`) remains 0, and indices 1..17, 19 remain 255.
   - Solid 255 opacity across all non-transparent rows completely occludes the underlying Canon UI.

## Menu Box Drawing and Structure (Fault F2)
- In `core/gui_menu.c:731-752` (`gui_menu_draw_initial`), CHDK only draws the menu title header (line 751) and scrollbar background if `count > num_lines` (line 740). CHDK draws NO outer menu box.
- In `core/gui_menu.c:967-1077` (`gui_menu_draw`), CHDK renders PER-ROW backgrounds in a loop `for (imenu=gui_menu_top_item, i=0, yy=y; curr_menu->menu[imenu].text && i<num_lines; ++imenu, ++i, yy+=rbf_font_height())` via `rbf_draw_string_len` (`lib/font/rbf_font.c:428-436`), `gui_menu_draw_symbol` (lines 761-775), etc.
- In PORT-35, screen height was 480 px and font height 32 px (`core/gui_draw.h:68-69`), so `num_lines = (480-0)/32 - 1 = 14` (`core/gui_menu.c:226`). Root menu has 9 rows (`core/gui.c:2209-2223`, user menu disabled by default); `num_lines = 14 >= 9`, so CHDK rendered all 9 rows without any height mismatch.
- The apparent "short grey box" was NOT a box-height mismatch; it was translucent rows allowing an underlying stock Canon UI box (a grey quick-control box spanning rows 0..5) to show through, while rows 6..8 (Script, CHDK Settings, Misc Stuff) drew over the dark camera preview background below Canon's box.
- The fix follows from the F3 opacity change: forcing solid opacity 255 across all rows occludes the underlying Canon box, eliminating the apparent boundary.

## Menu Width and Sizing (Fault F1)
- Formula at `core/gui_menu.c:226-228`:
  - Line 226: `num_lines = (camera_screen.height - camera_screen.ts_menu_border*2)/rbf_font_height()-1;`
  - Line 227: `x = camera_screen.disp_left  + camera_screen.menu_border_width;`
  - Line 228: `w = camera_screen.disp_width - camera_screen.menu_border_width*2;`
- Font size:
  - `core/gui_draw.h:68-69`: `#define FONT_WIDTH 14`, `#define FONT_HEIGHT 32` (under `THUMB_FW`)
  - `lib/font/rbf_font.c:251-252`: `rbf_font->hdr.height = FONT_HEIGHT;`, `rbf_font->width = FONT_WIDTH;`
- Why disp_* reset alone is expected to widen the menu:
  - In PORT-35, `g3x_osd2_update_screen_dimensions()` (`osd2_test_overlay.h:201-215`) updated `camera_screen.width` but omitted resetting `disp_left`/`disp_right`/`disp_width`, leaving `disp_width` clamped to 720 px (`w = 720 - 20 = 700 px`). On the 900x600 Mode 12 LCD panel, this left a ~200 px margin on the right (77.8% width).
  - In GUI2, `osd2_test_overlay.h:216-218` adds `camera_screen.disp_left = 0; camera_screen.disp_right = camera_screen.width - 1; camera_screen.disp_width = camera_screen.width;` (adapting `chdk-port/platform/g5x/lib.c:195-196`).
  - In Mode 12, `disp_width` resets to 900 px, expanding `w = 900 - 20 = 880 px` (97.8% width). In 720x480 mode, `disp_width` resets to 720 px, keeping `w = 700 px` at unsheared stride 736.
- Refuting owner observation: Menu remaining restricted to 700 px width (with a blank right margin) when displaytype is Mode 12 would refute this cause.

## Root-Cause Notes

### Fault F1: Menu uses only a small part of the LCD [INFERRED]
In gui_menu.c:227-228, menu width is screen-relative (`w = disp_width - 20`), and font is 14x32 (gui_draw.h:69-70). PORT-35 clamped disp_width to 720 px, so 9 root items covered only 700x288 px on the 900x600 3.2-inch panel.
Refutation observation: Menu remaining restricted to 700x288 px when displaytype is Mode 12 refutes this cause.

### Fault F2: Grey box is shorter than item list [INFERRED]
In gui_menu.c:967-1077, CHDK draws no outer box; each row renders its own background, and num_lines=14 (at 480 px) fully covers all 9 root items (gui_menu.c:226). The "grey box" was a stock Canon UI element showing through translucent rows.
Refutation observation: A visible boundary between rows 5 and 6 persisting despite opaque background rendering refutes this cause.

### Fault F3: Background is translucent [INFERRED]
In core/conf.c:198-201 and platform/generic/palette.c:35, transparent dark grey is index 18 (byte 0xb0); stock gui_draw.c:18 gives opacity 0xb0 (176 = ~69% alpha) because (0xb0 & 0xf) == 0. GUI2 forces opacity 255 for non-transparent colors.
Refutation observation: Translucency persisting on hardware despite the opacity 255 override refutes this cause.

## Trial Diagnostic
The 1-px border and `dt=%d w=%d bw=%d h=%d` string rendered by `g3x_gui_kbd_redraw` in GUI2 is a TRIAL DIAGNOSTIC to inspect the live hardware displaytype and screen geometry; it is NOT a fix for F1-F3.

## Candidate Artifacts and Build Command

- **Build command**:
  ```bash
  G3X_GUI2=1 python3 -B tools/build_candidate_port25_ladder_fix.py --gui2 --out-dir candidate_port36_gui2
  ```
- **Candidate DISKBOOT.BIN SHA-256**:
  `2f9d51dabf435997dbc5005dd60b71bc07758d6598175377fc74669fb42263ae`
- **Candidate DISKBOOT.BIN size**: 103,249 bytes
- **Witness address**: `0x0035CD90`
- **Linked `_end`**: `0x00362DD0`
- **DryOS heap start**: `0x00368880` (clearance: 23,216 bytes)
