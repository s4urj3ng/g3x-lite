# PORT-40: Opt-In G3X_GUI5=1 Candidate Menu Box Geometry, Edge Leaks, and Row Count

## Overview
The `G3X_GUI5=1` opt-in candidate builds upon `G3X_GUI4=1` (preserving 2x font scaling, high-contrast title bar, zero-flicker kbd driver, and Step 8/9 sentinel guards) to resolve all four symptoms observed in the PORT-38 owner trial. It aligns the menu background fill rectangle and the painted menu rectangle at `(10, 12)-(889, 587)` (880x576 px) with even 10-px horizontal and 12-px vertical margins on the 900x600 LCD, eliminates edge leaks via UYVY 2-pixel word packing, and fills unpainted rows down to the bottom with solid opaque black.

Both scrolling menus (e.g. Visual Settings with 31 items > 17 visible rows) and non-scrolling menus (e.g. `root_menu` with 10 items <= 17) are explicitly covered. In both cases, the outer box remains strictly `(10, 12)-(889, 587)` (880x576 px) with even 10-px left/right margins and 12-px top/bottom margins. Under GUI5, the scrollbar width (`wplus = 8`) is reserved inside the 880-px box by shrinking the item text area (`w = 880 - 8 = 872 px`), keeping 2-pixel word alignment for DIGIC 6 UYVY overlay packing.

---

## Changed Values Table

| Symbol / Parameter | Old Value (GUI4) | New Value (GUI5) | Source Path:Line | Label | Evidence & Rationale |
|---|---|---|---|---|---|
| `CAM_BITMAP_WIDTH` | `736` | `928` | `scripts/build_candidate_gui3.py:1706` (injected GUI5 override in `camera_info.c`) | `VERIFIED` | Mode 12 LCD buffer stride in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV` jump table at `0xFC1834F8`, SHA-256 `d0827e15c2deb8c1eace949c85c395bb0c75455f7e88ce3c1a0f9b3477b78647`). |
| `CAM_BITMAP_HEIGHT` | `480` | `600` | `scripts/build_candidate_gui3.py:1707` (injected GUI5 override in `camera_info.c`) | `VERIFIED` | Mode 12 LCD buffer height in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV` jump table at `0xFC1834F8`). |
| `CAM_SCREEN_WIDTH` | `720` | `900` | `scripts/build_candidate_gui3.py:1708` (injected GUI5 override in `camera_info.c`) | `VERIFIED` | Mode 12 LCD visible pixel width in GM1.10C `BmpDDev.c`; verified by PORT-36 1-px frame test at `(0,0)-(899,599)`. |
| `CAM_SCREEN_HEIGHT` | `480` | `600` | `scripts/build_candidate_gui3.py:1709` (injected GUI5 override in `camera_info.c`) | `VERIFIED` | Mode 12 LCD visible pixel height in GM1.10C `BmpDDev.c`; verified by PORT-36 1-px frame test at `(0,0)-(899,599)`. |
| `G3X_OSD2_DEFAULT_WIDTH` | `720` | `900` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:54` | `VERIFIED` | Default OSD2 screen width matching Mode 12 LCD resolution. |
| `G3X_OSD2_DEFAULT_HEIGHT` | `480` | `600` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:55` | `VERIFIED` | Default OSD2 screen height matching Mode 12 LCD resolution. |
| `G3X_OSD2_DEFAULT_BUFFER_WIDTH` | `736` | `928` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:56` | `VERIFIED` | Default OSD2 buffer stride matching Mode 12 LCD buffer stride (`PORT35-ROM-BMPDDEV`). |
| `G3X_OSD2_DEFAULT_BUFFER_HEIGHT` | `480` | `600` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:57` | `VERIFIED` | Default OSD2 buffer height matching Mode 12 LCD buffer height. |
| `G3X_OSD2_DEFAULT_SIZE` | `345600` | `540000` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:58` | `VERIFIED` | 900 * 600 visible pixels. |
| `G3X_OSD2_DEFAULT_BUFFER_SIZE` | `353280` | `556800` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:59` | `VERIFIED` | 928 * 600 buffer pixels (`PORT35-ROM-BMPDDEV` `0x87F00`). |
| GUI5 Scrollbar Layout & Width Reservation | `wplus = 8` outside `w` (box widened to 890, 10/0 margins) | `wplus = 8` reserved inside 880 box (`w -= wplus` -> `872`, scrollbar `882..889`, 8 px even) | `scripts/build_candidate_gui3.py:81-112, 1718-1725` | `VERIFIED` | Embedded transform applied to `gui_menu.c` copy during candidate build; keeps worktree `chdk-port/core/gui_menu.c` pristine. Reserves 8-px scrollbar inside 880 box, aligns fill rect and menu rect at `(10,12,880,576)` with even margins in both scrolling and non-scrolling menus. |
| `conf.menu_color` default background | `IDX_COLOR_GREY_DK` | `IDX_COLOR_BLACK` | `scripts/build_candidate_gui3.py:1685-1692` (injected GUI5 override in `conf_candidate.c`) | `HISTORICAL_CHDK` | Overrides default menu background from dark grey to solid black so text padding and scrollbar use black, keeping `chdk-port/core/conf.c` pristine. |
| Scrollbar background color | `conf.menu_color` | `COLOR_BLACK` | `scripts/build_candidate_gui3.py:91, 1718-1725` | `HISTORICAL_CHDK` | Explicitly draws scrollbar background rectangle using `MAKE_COLOR(COLOR_BLACK, COLOR_BLACK)`. |
| `conf.menu_center` vertical offset | centered count | fixed y=44 (num_lines) | `scripts/build_candidate_gui3.py:82-96, 1718-1725` | `INFERRED` | Bypasses `conf.menu_center` under GUI5 so header is anchored at y=12, perfectly matching `g3x_get_menu_layout`. |
| Unpainted rows fill | unpainted (exposed) | solid opaque black | `scripts/build_candidate_gui3.py:116-125, 1718-1725` | `HISTORICAL_CHDK` | Loop `for (; i < num_lines; ++i, yy += fh)` draws filled black rectangles down to `y=587`. |
| UYVY even-word alignment | unaligned | 2-pixel word aligned | `scripts/build_candidate_gui3.py:768-771, 790-791, 822-824` | `INFERRED` | Enforces `x &= ~1; w &= ~1; bw = (bw + 1) & ~1;` and writes 32-bit `0x00800080` (Y=0, U=128, V=128). Adapts `gui_draw.c:79-93, 134-142`. |
| String padding background | `BG_COLOR(cl)` | `COLOR_BLACK` | `scripts/build_candidate_gui3.py:1079, 1094` | `INFERRED` | In `rbf_draw_string_len` / `right_len`, pad rectangle filled with solid black instead of theme color. |

---

## Root Cause Analysis for PORT-38 Symptoms

1. **Symptom 1 (Box covers only ~80% width, ~85% height; left uncovered, right ~1/10 width, photo shows at top)**:
   - *Root cause*: `CAM_SCREEN_WIDTH` was 720 (80.0% of 900) and `CAM_SCREEN_HEIGHT` was 480 (80.0% of 600) in `platform_camera.h:73-83` and static `camera_info.thm.o`. In Mode 12 (900x600), `disp_width=720` produced `w = 700 px`. Centering left `(900 - 720) / 2 = 90 px` margins on both sides (exactly 1/10 LCD width), and photo show-through above `y = 12`. Furthermore, in scrolling menus like Visual Settings (`count = 31 > 17`), standard CHDK placed `wplus = 8` outside `w`, which widened the box and destroyed margin symmetry (giving 10 px left and 0 px right margin when clamped/widened).
   - *Code fix*: Candidate build glue in `scripts/build_candidate_gui3.py` (`CAM_SCREEN_WIDTH: 720 -> 900`, `CAM_SCREEN_HEIGHT: 480 -> 600`, `CAM_BITMAP_WIDTH: 736 -> 928`, `CAM_BITMAP_HEIGHT: 480 -> 600`) and `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:51-68` (`G3X_OSD2_DEFAULT_WIDTH: 720 -> 900`, etc.), setting `disp_width = 900` and outer `w = 880 px` centered with even 10 px margins. In `scripts/build_candidate_gui3.py:81-112, 1718-1725` (embedded menu transform applied during build to candidate copy of `gui_menu.c`), scrollbar width (`wplus = 8`) is reserved inside the 880-px box by reducing `w` from 880 to 872 px when `count > num_lines`, keeping the outer box strictly at `880x576` at `(10,12)-(889,587)` with even 10-px margins in both scrolling and non-scrolling cases.
2. **Symptom 2 (Thin bright strip along top edge, thin green line along right edge; fill rect and painted area out of line)**:
   - *Root cause*:
     - Top bright strip: `conf.menu_center = 1` shifted `gui_menu_draw()` `y` to 96 (header to 64) when `count=10`, while `g3x_fill_menu_opaque_black()` filled from `header_y = 12`, creating a vertical mismatch.
     - Right green line: In DIGIC 6 16-bpp UYVY (`chdk-port/core/gui_draw.c:79-93`), each 32-bit word packs 2 horizontal pixels `[U0, Y0, V0, Y1]`. An odd width or unaligned boundary leaves chroma `U=0, V=0` with `opacity=255`, decoding in YUV to pure bright green (`G = Y + 135`, `R = 0`, `B = 0`).
   - *Code fix*:
     - `scripts/build_candidate_gui3.py:82-96, 1718-1725`: Bypasses `conf.menu_center` under GUI5 so `y` is unconditionally 44 and header is at `y = 12`, exactly matching `g3x_get_menu_layout: header_y = 12` and eliminating the top strip.
     - `scripts/build_candidate_gui3.py:768-771, 780-791, 822-824` and `scripts/build_candidate_gui3.py:81-112`: Enforces 2-pixel even word alignment (`bx &= ~1; bw = (bw + 1) & ~1; total_w = w; w = 872; scrollbar = 8 px [882..889]`) and writes 32-bit `0x00800080` (`Y0=0, U=128, Y1=0, V=128`), adapting `chdk-port/core/gui_draw.c:79-93, 134-142` and eliminating chroma leaks.
3. **Symptom 3 (Area below last item is dark grey, not black)**:
   - *Root cause*:
     - `chdk-port/core/conf.c:201-205`: `conf.menu_color` default background was `IDX_COLOR_GREY_DK` (dark grey).
     - `chdk-port/core/gui_menu.c:743`: Scrollbar background was drawn with `conf.menu_color` (`IDX_COLOR_GREY_DK`).
     - `scripts/build_candidate_gui3.py:1079, 1094`: String padding rectangles were drawn with `BG_COLOR(cl)` (`IDX_COLOR_GREY_DK`).
     - `chdk-port/core/gui_menu.c:1005-1084`: `gui_menu_draw()` stopped at `i == count` (10 items), leaving rows 10..16 unpainted and exposing the underlying Canon UI buffer.
   - *Code fix*:
     - `scripts/build_candidate_gui3.py:1685-1692`: Overrides `conf.menu_color` default background to `IDX_COLOR_BLACK` in generated `conf_candidate.c`.
     - `scripts/build_candidate_gui3.py:91, 1718-1725`: Scrollbar background drawn with `MAKE_COLOR(COLOR_BLACK, COLOR_BLACK)`.
     - `scripts/build_candidate_gui3.py:1079, 1094`: String padding drawn with `MAKE_COLOR(COLOR_BLACK, COLOR_BLACK)`.
     - `scripts/build_candidate_gui3.py:116-125, 1718-1725`: Adds loop `for (; i < num_lines; ++i, yy += rbf_font_height()) draw_rectangle(x, yy, x + w - 1, yy + rbf_font_height() - 1, MAKE_COLOR(COLOR_BLACK, COLOR_BLACK), RECT_BORDER0 | DRAW_FILLED);` to paint rows 10..16 solid opaque black.
4. **Symptom 4 (Items use only upper half of box)**:
   - *Root cause*: Menu row capacity is calculated as `num_lines = (camera_screen.height - camera_screen.ts_menu_border*2)/rbf_font_height()-1` (`chdk-port/core/gui_menu.c:226`). Under GUI5 with `camera_screen.height = 600`, `num_lines = (600 - 0)/32 - 1 = 17` visible rows. For submenus with >= 17 items, all 17 visible rows are filled (544 px + 32 px title = 576 px box). For shorter menus like `root_menu` (`count = 10`), items occupy rows 0..9 (320 px), leaving rows 10..16 unpainted in GUI4.
   - *Code fix*: `chdk-port/core/gui_menu.c:1086-1094` fills remaining rows 10..16 with solid black down to `y = 587`, so the entire 576-px box is solid black, filling the full box height.

---

## DIGIC 6 Sibling Handling Citations

1. **PowerShot G7 X (`chdk-port/platform/g7x/`)**:
   - `platform_camera.h:61-65`: `CAM_BITMAP_WIDTH 736`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 720`, `CAM_SCREEN_HEIGHT 480`. (G7 X built-in LCD is standard 720x480).
   - `lib.c:289-296`: `vid_get_opacity_active_buffer` indexes `opacity_buffer[active_bitmap_buffer & 1]`.
   - `lib.c:303-358`: `update_screen_dimensions()` switches on `displaytype`; for LCD (cases 1, 2, 8, 9, 10), sets `width=720, buffer_width=736, height=480`. Case 12 sets `900x600`, stride `928`.
   - *Scrollbar handling in core*: G7 X relies on common `chdk-port/core/gui_menu.c:36, 736-745, 757, 1096-1107`. In standard 720x480 CHDK, `wplus = 8` extends beyond `w`, expanding the menu box when scrolling. On G3 X's 900x600 panel, expanding beyond `w = 880` encroaches on the 10-px border, so `G3X_GUI5=1` reserves `wplus = 8` inside the 880 box (`w = 872`), keeping even margins and 2-pixel word alignment.
2. **PowerShot G5 X (`chdk-port/platform/g5x/`)**:
   - `platform_camera.h:88-94`: `CAM_BITMAP_WIDTH 736`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 720`, `CAM_SCREEN_HEIGHT 480`.
   - `lib.c:21-33`: active buffer indexing with `& 1`.
   - `lib.c:162-204`: `update_screen_dimensions()` handles displaytype switching; lines 194-197 reset `camera_screen.disp_right = camera_screen.width - 1; camera_screen.disp_width = camera_screen.width;`. Case 12 sets `900x600`, stride `928`.
3. **PowerShot SX60 HS (`chdk-port/platform/sx60hs/`)**:
   - `platform_camera.h:127-133`: `CAM_BITMAP_WIDTH 640`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 640`, `CAM_SCREEN_HEIGHT 480`.
   - `lib.c:289-332`: `update_screen_dimensions()` for 640x480 LCD.

*G3 X distinction*: Unlike its 720x480 and 640x480 siblings, the G3 X features a 3.2" 1.62M-dot panel operating in Mode 12 (`900x600`, buffer stride `928`). The buffer dimensions `buffer_width 928` / `buffer_size 556800` are sourced directly from GM1.10C ROM slice `PORT35-ROM-BMPDDEV` (`0xFC18347E..0xFC18381F`, SHA-256 `d0827e15c2deb8c1eace949c85c395bb0c75455f7e88ce3c1a0f9b3477b78647` in `evidence/port35_manifest.json`), `BmpDDev.c` `sub_fc18347e` jump table at `0xFC1834F8` displaytype 12 (labeled `VERIFIED`).

---

## DISKBOOT Artifacts and Reproducibility

| Build Target | Build Flags | DISKBOOT SHA-256 | Size (Bytes) | Boot Witness Addr | Linked `_end` | Heap Clearance |
|---|---|---|---|---|---|---|
| Default Baseline | (no flags) | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | `118001` (118,001) | `0x0035F7A0` | `0x00366CB0` | 7,120 B |
| `G3X_GUI4=1` Trial Baseline | `-DG3X_GUI4=1` | `14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd` | `102241` (102,241) | `0x0035C9A0` | `0x003629D0` | 24,240 B |
| `G3X_GUI5=1` Plain | `-DG3X_GUI5=1` | `aff912e317c007208d00dc78dca966aada10256dcf5ecb734c1b6b610a7e91fa` | `102161` (102,161) | `0x0035C950` | `0x00362980` | 24,320 B |
| `G3X_GUI5=1` Combined | `-DG3X_GUI5=1 -DG3X_SHORTPRESS=1` | `5c5d4ef4bbecd09b31a73cb461c80674fef268fc5c5993f38f18e91231860ed4` | `102321` (102,321) | `0x0035C9F0` | `0x00362A30` | 24,144 B |

---

## Untouched GUI4 Behaviors Under GUI5

All GUI4 behaviors that passed the owner trial remain completely untouched in the GUI5 build:
- **F1 2x Font Scaling (`g3x_draw_char_16x32`)**: Native integer scaling from 8x16 font data to 16x32 glyphs with 16-px advance (`scripts/build_candidate_gui3.py:917-995`).
- **High-Contrast Title Bar**: Crisp white text on solid black background (`MAKE_COLOR(COLOR_BLACK, COLOR_WHITE)`) in `rbf_draw_menu_header` (`scripts/build_candidate_gui3.py:1120-1145`).
- **Zero-Flicker Kbd Driver**: Repaint only on ALT entry, buffer toggle (`check_gui_needs_redraw()`), or sentinel guard overwrite (`!draw_test_guard()`). No periodic timer force redraw (`scripts/build_candidate_gui3.py:730-746`).
- **Step 8 Sentinel Recovery**: Re-arm sentinel via `draw_set_guard()` and immediate refill with `g3x_fill_menu_opaque_black()` upon stock Canon overwrite while in menu mode (`scripts/build_candidate_gui3.py:738-742`).
- **Step 9 Clean ALT Exit**: `gui_set_need_restore()` followed by `gui_redraw(1)` on `left_alt` to clear CHDK overlay and return full control to stock Canon UI without lingering background redraws (`scripts/build_candidate_gui3.py:723-728`).
- **disp_left Reset**: `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:224` retains `#if (defined(G3X_GUI2) && (G3X_GUI2 == 1)) || (defined(G3X_GUI3) && (G3X_GUI3 == 1))`. Because GUI4 and GUI5 always define `G3X_GUI3=1`, the reset applies identically to GUI4 and GUI5 without needing redundant macro terms.
