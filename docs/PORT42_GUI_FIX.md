# PORT42-GUI-FIX: Full Build Overlay Flicker, UYVY Colours, and Opacity/2x Font

## Summary of Fixes

The PORT-41 default full CHDK build succeeded in booting and launching ALT mode, but exhibited three issues on hardware:
1. **Flicker**: The ALT panel alternated between drawn and mostly erased every couple of frames due to periodic forced redraws `(((cnt++) & 3) == 0)` and lack of sentinel overwrite detection.
2. **Colours**: Large pink blocks appeared in the panel and title areas due to incorrect default color indexes, missing DIGIC 6 palette type 3 registration, and misrouted opacity buffer stubs.
3. **Opacity/Size**: The stock 8x16 font was used (tiny on 900x600 Mode 12 LCD), and live view showed through the menu panel due to non-opaque background filling.

The fixes confirmed on physical camera hardware during PORT-35..40 are ported into the full build under the compile-time opt-in switch `G3X_GUI_FIX=1`. When `G3X_GUI_FIX` is off, the build reproduces `manifests/port41_manifest.json` byte-for-byte.

---

## Fix Mapping Table

| Fix | File:Line Changed | Source Citation | Label |
|---|---|---|---|
| **Zero-Flicker Redraw**: Eliminate periodic forced redraw `(((cnt++) & 3) == 0)`. Repaint only when GUI state changes (`gui_check_state_changed()`), stock UI overwrites the layer (`!draw_test_guard()`), or buffer toggles (`check_bitmap_buffer_changed()`). Timer and state maintenance (`gui_maintenance_tick()`) runs unconditionally each tick. | `full_build/g3x/lib.c:289-315`<br>`full_build/g3x/gui_menu.c:34-40`<br>`stage_chdk/core/main.c:316-335`<br>`stage_chdk/core/gui.c:2387-2405,2960-3020`<br>`tools/build_port41_full.py:215-245,310-485` | `chdk-port/platform/g5x/lib.c:211-224`<br>`scripts/build_candidate_gui3.py:730-746,812-828`<br>`docs/PORT37_GUI_FLICKER.md:17,46`<br>`docs/PORT38_GUI4_TRIAL.md:123` | VERIFIED by owner trial |
| **Active-Buffer Drawing**: Index opacity and bitmap buffers strictly with `active_bitmap_buffer & 1` across `draw_set_guard`, `draw_test_guard`, `vid_get_bitmap_fb`, `vid_get_opacity_active_buffer`, and `g3x_fill_menu_opaque_black`. | `full_build/g3x/lib.c:27-35`<br>`stage_chdk/core/gui_draw.c:380-389`<br>`tools/build_port41_full.py:338-360` | `chdk-port/platform/g7x/lib.c:289-296`<br>`chdk-port/core/gui_draw.c:72-94,135`<br>`scripts/build_candidate_gui3.py:739,835,959` | VERIFIED by owner trial |
| **UYVY Neutral Black/White**: Use DIGIC 6 UYVY word values `0x00800080` (black, Y=0, U=128, V=128) and `0xFF80FF80` / `0xFF80` (white, Y=255, U=128, V=128), eliminating pink/magenta chroma offsets. | `full_build/g3x/gui_menu.c:1235-1240`<br>`stage_chdk/core/conf.c:201-202`<br>`tools/build_port41_full.py:245-263` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:24-27,100-106`<br>`scripts/build_candidate_gui3.py:739,906,977`<br>`docs/PORT35_TRIAL_PLAN.md:58` | VERIFIED by owner trial |
| **DIGIC 6 Palette Registration**: Provide `vid_get_bitmap_active_palette()` returning `palette_buffer_ptr[active_palette_buffer] + 1`, `vid_get_palette_type() = 3` (256x4 AYUV), and `vid_get_palette_size() = 1024` so CHDK color conversion accurately tracks hardware palette. | `full_build/g3x/lib.c:37-62` | `reference/finsig_gm110c/stubs_entry.S:195,196`<br>`scripts/build_candidate_gui3.py:1223-1249`<br>`chdk-port/platform/g7x/lib.c:338-358` | VERIFIED by owner trial |
| **Real Opacity Buffer Array**: Provide real `opacity_buffer[2] = {0x5FC40000, 0x5FB80000}` in DRAM and write opacity byte `0xFF` where drawn, avoiding misdirected pointer to `0xFC1837FC`. | `full_build/g3x/lib.c:18`<br>`full_build/g3x/sub/110c/stubs_min.S:3-5` | `chdk-port/platform/g3x/sub/110c/osd2_test_overlay.h:18-27,131-134`<br>`scripts/build_candidate_gui3.py:739,901`<br>`docs/PORT38_TRACE.md:10` | VERIFIED by owner trial |
| **Menu Contrast Defaults**: Default `conf.menu_color` and `conf.menu_title_color` to `IDX_COLOR_BLACK` background and `IDX_COLOR_WHITE` foreground, and `conf.menu_center` to 0. | `stage_chdk/core/conf.c:201-202,254`<br>`tools/build_port41_full.py:245-263` | `scripts/build_candidate_gui3.py:1685-1698`<br>`docs/PORT40_GUI_LAYOUT.md:23-25` | VERIFIED by owner trial |
| **880x576 Opaque Black Background**: Fill complete 880x576 menu rectangle (x:10..889, y:12..587) with solid UYVY black (`0x00800080`) and opacity `0xFF` on menu initial draw and ALT helper entry, preventing live view show-through. | `full_build/g3x/gui_menu.c:984-993,1210-1241`<br>`stage_chdk/core/gui.c:2573-2578`<br>`tools/build_port41_full.py:269-278` | `scripts/build_candidate_gui3.py:820-826,885-909`<br>`docs/PORT38_GUI4_TRIAL.md:123`<br>`docs/PORT40_GUI_LAYOUT.md:14-28` | VERIFIED by owner trial |
| **2x Integer Font Scaling (16x32)**: Direct 16x32 font rasterizer doubling each 8x16 bit into a 2x2 square, `rbf_*` interface overrides in `gui_menu.c`, and `FONT_WIDTH=16`, `FONT_HEIGHT=32` in `gui_draw.h`/`gui_draw.c`. | `full_build/g3x/gui_menu.c:1157-1208,1243-1447`<br>`stage_chdk/core/gui_draw.h:68-70`<br>`stage_chdk/core/gui_draw.c:307-335`<br>`tools/build_port41_full.py:284-335` | `scripts/build_candidate_gui3.py:840-909,984-1221`<br>`docs/PORT40_GUI_LAYOUT.md:14-28`<br>`chdk-port/platform/g5x/lib.c:27-33` | VERIFIED by owner trial |
| **Timed GUI State Change Detection**: Detect visible-state signature changes (GUI mode handler pointer, timed ALT helper expiry `get_tick_count() >= gui_helper_displayat`, timed splash countdown / expiry, current menu item, and all 16 helper/menu conf fields) to trigger repaints without periodic polling or forced per-tick redraws. | `full_build/g3x/gui_menu.c:39-44`<br>`stage_chdk/core/gui.c:2387-2405,2553-2700,2960-3020`<br>`tools/build_port41_full.py:340-485` | `chdk-port/core/gui.c:2387-2405,2553-2700` | INFERRED (owner trial to confirm) |
 
---

## Output Manifests & Verified Hashes

Toolchain: `gcc-arm-none-eabi-5_4-2016q3` (deterministic wrapper: `scripts/gcc_deterministic_wrapper.sh`)

| Variant | Switch | DISKBOOT.BIN Size | DISKBOOT.BIN SHA-256 | Manifest File |
|---|---|---|---|---|
| PORT-41 Default | (none) | 124,097 B | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | `manifests/port41_manifest.json` |
| PORT-42 FULL_HOOKS | `FULL_HOOKS=1` | 124,153 B | `eb46aa339bb6557f27d992691f83ceb14cc73962625a44e0f146edde9b886dce` | `manifests/port42_full_hooks_manifest.json` |
| PORT-42 GUI Fix | `G3X_GUI_FIX=1` | 123,913 B | `1b3d1a036530a54783696be08207081bc5da08ece5677fb6d1fc4142518a5be4` | `manifests/port42_gui_fix_manifest.json` |
| PORT-42 GUI Fix + FULL_HOOKS | `G3X_GUI_FIX=1 FULL_HOOKS=1` | 123,977 B | `d96aed5ac212e9e1582bd7364a594df79976ac56090d579edb09223fdb6d6ff0` | `manifests/port42_gui_fix_full_hooks_manifest.json` |

All candidate builds (`candidate_port2a`, `gui4`, `gui5`, `shortpress`) remain bit-for-bit invariant. Bootstrap pins (`platform/g3x/libplatform.a`, `platform_camera.h`) remain unaltered.
