# PORT-40: Opt-In G3X_GUI5=1 Candidate Menu Box Geometry, Edge Leaks, and Row Count

## Overview
The `G3X_GUI5=1` opt-in candidate builds upon `G3X_GUI4=1` (preserving 2x font scaling, high-contrast title bar, zero-flicker kbd driver, and Step 8/9 sentinel guards) to resolve all four symptoms observed in the PORT-38 owner trial. It aligns the menu background fill rectangle and the painted menu rectangle at `(10, 12)-(889, 587)` (880x576 px) with even 10-px horizontal and 12-px vertical margins on the 900x600 LCD, eliminates edge leaks, and fills all unpainted rows down to the bottom with solid opaque black.

---

## Changed Values Table

| Symbol / Parameter | Old Value (GUI4) | New Value (GUI5) | Source Path:Line | Label | Evidence & Rationale |
|---|---|---|---|---|---|
| `CAM_BITMAP_WIDTH` | `736` | `928` | `scripts/build_candidate_gui3.py:1532-1540` | `VERIFIED` | Mode 12 LCD buffer stride in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV` `0xFC18347E..0xFC18381F`). |
| `CAM_BITMAP_HEIGHT` | `480` | `600` | `scripts/build_candidate_gui3.py:1532-1540` | `VERIFIED` | Mode 12 LCD buffer height in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV`). |
| `CAM_SCREEN_WIDTH` | `720` | `900` | `scripts/build_candidate_gui3.py:1532-1540` | `VERIFIED` | Mode 12 LCD visible pixel width in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV`); confirmed PORT-36. |
| `CAM_SCREEN_HEIGHT` | `480` | `600` | `scripts/build_candidate_gui3.py:1532-1540` | `VERIFIED` | Mode 12 LCD visible pixel height in GM1.10C `BmpDDev.c` (`PORT35-ROM-BMPDDEV`); confirmed PORT-36. |
| `G3X_OSD2_DEFAULT_WIDTH` | `720` | `900` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:54` | `VERIFIED` | Default OSD2 screen width matching Mode 12 LCD resolution. |
| `G3X_OSD2_DEFAULT_HEIGHT` | `480` | `600` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:55` | `VERIFIED` | Default OSD2 screen height matching Mode 12 LCD resolution. |
| `G3X_OSD2_DEFAULT_BUFFER_WIDTH` | `736` | `928` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:56` | `VERIFIED` | Default OSD2 buffer stride matching Mode 12 LCD buffer stride. |
| `G3X_OSD2_DEFAULT_BUFFER_HEIGHT` | `480` | `600` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:57` | `VERIFIED` | Default OSD2 buffer height matching Mode 12 LCD buffer height. |
| `G3X_OSD2_DEFAULT_SIZE` | `345600` | `540000` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:58` | `VERIFIED` | 900 * 600 visible pixels. |
| `G3X_OSD2_DEFAULT_BUFFER_SIZE` | `353280` | `556800` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:59` | `VERIFIED` | 928 * 600 buffer pixels. |
| `camera_screen.disp_width` reset | unreset in GUI4 | `camera_screen.width` (900) | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:224` | `INFERRED` | Adapts `chdk-port/platform/g5x/lib.c:195-196`; gates reset under `G3X_GUI4` and `G3X_GUI5`. |
| `camera_screen` static .data | 720x480 stride 736 | 900x600 stride 928 | `chdk-port/core/camera_info.c:95-100` | `VERIFIED` | Statically recompiled in GUI5 with `CAM_SCREEN_WIDTH=900` / `CAM_BITMAP_WIDTH=928`. |
| Unpainted rows fill | unpainted (exposed) | solid opaque black | `chdk-port/core/gui_menu.c:1080-1087` | `HISTORICAL_CHDK` | Rows `i < num_lines` filled with `draw_rectangle` using `MAKE_COLOR(COLOR_BLACK, COLOR_BLACK)`. |

---

## Root Cause Analysis for PORT-38 Symptoms

1. **Symptom 1 (Box covers ~80% width, ~85% height; left margin uncovered, right margin ~1/10 width, photo shows at top)**:
   - *Root cause*: `platform_camera.h:73-77` defined `CAM_SCREEN_WIDTH=720` (80.0% of 900) and `CAM_SCREEN_HEIGHT=480` (80.0% of 600), and `camera_info.thm.o` was bundled from stock precompiled objects with static 720x480 dimensions. In Mode 12 (900x600), a 720-wide box with `disp_width=720` resulted in `w = 700` px. When centered, it left `(900 - 720) / 2 = 90` px margins on both left and right (exactly 1/10 of LCD width), and photo show-through above `y = 12`.
2. **Symptom 2 (Thin bright strip along top edge, thin green line along right edge; fill rect and painted area out of line)**:
   - *Root cause*: Discrepancies between compile-time 720x480 and runtime 900x600 caused fill and paint boundaries to diverge. In addition, DIGIC 6 16-bpp UYVY packs 2 horizontal pixels per word (`chdk-port/core/gui_draw.c:79-93`); any odd width or unwritten odd pixel leaves chroma `U=0, V=0` with `opacity=255`, which decodes in YUV to pure green (`G = Y + 135`, `R = 0`, `B = 0`). In GUI5, starting at even `x=10` with even `w=880` guarantees complete 2-pixel UYVY word pairs (`440` words = `880` px) with `U=128, V=128`, eliminating chroma leaks.
3. **Symptom 3 (Area below last item is dark grey, not black)**:
   - *Root cause*: `core/gui_menu.c:967` only looped over `curr_menu->menu[imenu].text` (10 items in `root_menu`), terminating at `i = 10`. Rows 10..16 were never drawn by `gui_menu.c`, leaving the underlying Canon UI buffer (default dark grey `IDX_COLOR_GREY_DK`) exposed. In GUI5, rows `i < num_lines` (10..16) are explicitly filled with `draw_rectangle(..., MAKE_COLOR(COLOR_BLACK, COLOR_BLACK), RECT_BORDER0 | DRAW_FILLED)`.
4. **Symptom 4 (Items use only upper half of box)**:
   - *Root cause*: `root_menu` has only 10 items (`count = 10`), while a 900x600 screen at a 32-px font pitch allocates `num_lines = (600 / 32) - 1 = 17` rows. In GUI4, `conf.menu_center = 0` anchored items at `y = 44..363` (`10 * 32 = 320` px), using only 55.6% of the 576-px box height. In GUI5, the remaining 7 rows (224 px) are filled with opaque black down to `y = 587`, perfectly completing the 576-px box.

---

## DIGIC 6 Sibling Handling Citations

1. **PowerShot G7 X (`chdk-port/platform/g7x/`)**:
   - `platform_camera.h:61-65`: `CAM_BITMAP_WIDTH 736`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 720`, `CAM_SCREEN_HEIGHT 480`. (G7 X built-in LCD is standard 720x480).
   - `lib.c:289-296`: `vid_get_opacity_active_buffer` indexes `opacity_buffer[active_bitmap_buffer & 1]`.
   - `lib.c:303-358`: `update_screen_dimensions()` switches on `displaytype`; for LCD (cases 1, 2, 8, 9, 10), sets `width=720, buffer_width=736, height=480`.
2. **PowerShot G5 X (`chdk-port/platform/g5x/`)**:
   - `platform_camera.h:88-94`: `CAM_BITMAP_WIDTH 736`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 720`, `CAM_SCREEN_HEIGHT 480`.
   - `lib.c:21-33`: active buffer indexing with `& 1`.
   - `lib.c:162-204`: `update_screen_dimensions()` handles displaytype switching; lines 194-197 reset `camera_screen.disp_right = camera_screen.width - 1; camera_screen.disp_width = camera_screen.width;`.
3. **PowerShot SX60 HS (`chdk-port/platform/sx60hs/`)**:
   - `platform_camera.h:127-133`: `CAM_BITMAP_WIDTH 640`, `CAM_BITMAP_HEIGHT 480`, `CAM_SCREEN_WIDTH 640`, `CAM_SCREEN_HEIGHT 480`.
   - `lib.c:289-332`: `update_screen_dimensions()` for 640x480 LCD.

*G3 X distinction*: Unlike its 720x480 and 640x480 siblings, the G3 X features a 3.2" 1.62M-dot panel operating in Mode 12 (`900x600`, buffer stride `928`). GUI5 is the first build to supply these true panel dimensions at both compile time and runtime.

---

## DISKBOOT Artifacts and Reproducibility

| Build Target | Build Flags | DISKBOOT SHA-256 | Size (Bytes) | Boot Witness Addr | Linked `_end` | Heap Clearance |
|---|---|---|---|---|---|---|
| Default Baseline | (no flags) | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | `118001` (118,001) | `0x0035F7A0` | `0x00366CB0` | 7,120 B |
| `G3X_GUI5=1` Plain | `-DG3X_GUI5=1` | `b88855c138cc4992a85aded8c7f91b2bacf7001b6d0d9ac89345d9e596251f08` | `102257` (102,257) | `0x0035C9B0` | `0x003629E0` | 24,224 B |
| `G3X_GUI5=1` Combined | `-DG3X_GUI5=1 -DG3X_SHORTPRESS=1` | `7ed211105640ff429269825ccdab079e1fd92089ce88e8a49a3eb915b1f891ec` | `102417` (102,417) | `0x0035CA50` | `0x00362A90` | 24,048 B |

---

## Untouched GUI4 Behaviors Under GUI5

All GUI4 behaviors that passed the owner trial remain completely untouched in the GUI5 build:
- **F1 2x Font Scaling (`g3x_draw_char_16x32`)**: Native integer scaling from 8x16 font data to 16x32 glyphs with 16-px advance (`scripts/build_candidate_gui3.py:835-980`).
- **High-Contrast Title Bar**: Crisp white text on solid black background (`MAKE_COLOR(COLOR_BLACK, COLOR_WHITE)`) in `rbf_draw_menu_header` (`scripts/build_candidate_gui3.py:1031-1059`).
- **Zero-Flicker Kbd Driver**: Repaint only on ALT entry, buffer toggle (`check_gui_needs_redraw()`), or sentinel guard overwrite (`!draw_test_guard()`). No periodic timer force redraw (`scripts/build_candidate_gui3.py:730-746`).
- **Step 8 Sentinel Recovery**: Re-arm sentinel via `draw_set_guard()` and immediate refill with `g3x_fill_menu_opaque_black()` upon stock Canon overwrite while in menu mode (`scripts/build_candidate_gui3.py:738-742`).
- **Step 9 Clean ALT Exit**: `gui_set_need_restore()` followed by `gui_redraw(1)` on `left_alt` to clear CHDK overlay and return full control to stock Canon UI without lingering background redraws (`scripts/build_candidate_gui3.py:723-728`).
