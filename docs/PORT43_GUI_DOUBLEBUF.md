# PORT-43: Double-Buffered Overlay, Fast Fills, Partial Redraw, and Shadow Restore

This document records the implementation of `G3X_GUI_DBUF=1` (opt-in compile-time switch for PowerShot G3 X GM1.10C) designed to eliminate the overlay flicker observed in the PORT-42 owner trial (menu repainting as black bands growing down over 5-8 frames, followed by disappearance to live view).

All changes are gated behind `#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)`. When the switch is disabled, all builds produce 100% byte-identical outputs to their existing manifests.

## Technical Architecture & Changes

| Change | File:Line | Sibling Citation | Label | Expected Visible Effect |
| :--- | :--- | :--- | :--- | :--- |
| **Dual-Buffer Drawing & Opacity Fill**<br>Draw and opacity write paths write synchronously into both bitmap buffers (`bitmap_buffer[0]`, `bitmap_buffer[1]`) and both opacity buffers (`opacity_buffer[0]`, `opacity_buffer[1]`), including glyph/text rows (`draw_1pixel_simple`, `draw_2pixels_simple`, `draw_hline_simple`). | `chdk-port/core/gui_draw.c:305-336`<br>`chdk-port/core/gui_draw.c:377-383`<br>`chdk-port/core/gui_draw.c:407-416`<br>`chdk-port/core/gui_draw.c:494-750` | `chdk-port/platform/g7x/lib.c:18-19, 291-292`; `chdk-port/platform/g5x/lib.c:21-33` | INFERRED | Eliminates frame-flip flicker where display page swap hides CHDK overlay; overlay persists across all hardware display flips. Text rendering (including ALT helpers) routes to both buffers and shadow copy. |
| **Dual-Buffer Sentinel Guard & Flip Bypass**<br>`draw_set_guard` and `draw_test_guard` verify sentinel bytes in both opacity buffers simultaneously. Under DBUF, a buffer flip with intact sentinels causes no redraw. Only a lost sentinel triggers restoration via single shadow blit. | `chdk-port/core/gui_draw.c:808-824`<br>`scripts/build_port43_dbuf.py:88-112` | `tools/build_port41_full.py:228-245`; `scripts/build_candidate_gui3.py:840-850`; `chdk-port/platform/g5x/lib.c:211-224` | INFERRED | Instant detection if stock camera UI wipes overlay planes. A hardware buffer flip with intact sentinels causes no repaint; lost sentinel triggers single fast shadow blit instead of gui_redraw. |
| **Fast Fills (32-bit Word Writes)**<br>`g3x_dbuf_fast_fill_rect` hooked into `draw_hline`, `draw_vline`, `draw_rectangle(DRAW_FILLED)`, and `g3x_fill_menu_opaque_black`. Uses 32-bit UYVY word pairs (`0x00800080` for black) and `memset` opacity blocks with zero per-pixel `draw_pixel` calls. | `chdk-port/core/gui_draw.c:112-234`<br>`chdk-port/core/gui_draw.c:1003-1006`<br>`chdk-port/core/gui_draw.c:1019-1022`<br>`chdk-port/core/gui_draw.c:1083-1085`<br>`chdk-port/platform/g3x/gui_menu.c:1278-1282` | `chdk-port/core/gui_draw.c:138-146`; `scripts/build_candidate_gui3.py:885-896` | INFERRED | Eliminates the 200-300 ms "growing black bands" top-to-bottom paint artifact observed in PORT-42; whole-box clear occurs in sub-millisecond time. |
| **Partial Redraw for Navigation**<br>In `gui_menu_draw`, when `gui_menu_redraw == 1`, `g3x_shadow_valid` is set, and `gui_menu_top_item == dbuf_last_drawn_top_item`, unchanged lines and padding rows are skipped and only the previous and current cursor items (and scrollbar) are redrawn. Navigation never triggers a full clear-and-repaint. | `chdk-port/platform/g3x/gui_menu.c:1007-1040`<br>`chdk-port/platform/g3x/gui_menu.c:1152-1155`<br>`chdk-port/platform/g3x/gui_menu.c:1177-1185`<br>`chdk-port/core/gui_menu.c:978-1005`<br>`chdk-port/core/gui_menu.c:1117-1120`<br>`chdk-port/core/gui_menu.c:1142-1148` | `chdk-port/core/gui_menu.c:995-1030` | INFERRED | Cursor navigation (up/down/scroll wheel) updates only the affected 32 px rows; padding rows are skipped on partial redraw; no visual glitching, jumping, or full-menu blinking while navigating. |
| **Fast Shadow Buffer Restore & Lifecycle Invalidation**<br>Off-screen shadow buffer sized for 880x576 at `(10, 12)` (1,013,760 bytes bitmap + 506,880 bytes opacity). Placement in static CHDK BSS guarded behind `G3X_GUI_DBUF=1`. Shadow validity lifecycle:<br>(1) Initialized/invalidated at DBUF startup (`draw_init`, `gui_init`).<br>(2) Invalidated (`g3x_shadow_valid=0`) on ALT exit, GUI handler/layer transitions, menu/submenu changes, and full erase (`draw_restore`).<br>(3) Validated (`g3x_shadow_valid=1`) strictly after complete redraw of active CHDK layer (menu or ALT overlay).<br>(4) Sentinel loss restores layer in single fast row `memcpy` without `vid_bitmap_refresh` ONLY when shadow is valid AND a CHDK overlay layer is active (never in live view). | `chdk-port/core/gui_draw.c:56-110`<br>`chdk-port/core/gui_draw.c:244-272`<br>`chdk-port/core/gui_draw.c:837-841`<br>`chdk-port/core/gui_draw.c:868-874`<br>`chdk-port/core/gui.c:2440-2443`<br>`chdk-port/core/gui.c:2469-2472`<br>`chdk-port/core/gui.c:2704-2708`<br>`chdk-port/core/gui.c:2980-3000`<br>`chdk-port/core/gui.c:3125-3129`<br>`scripts/build_port43_dbuf.py:88-112` | `docs/PORT40_GUI_LAYOUT.md:14-28`; `scripts/build_candidate_gui3.py:820-826` | INFERRED | Layer restoration after stock UI wipe occurs in ~1-2 ms without noticeable flicker or dropped frames. Wiping overlay after draw is eliminated by omitting `vid_bitmap_refresh`. Stale shadow restoration over live view is prevented by lifecycle invalidation. |
| **Dual-Plane Hardware Refresh Hook (Erase-Only)**<br>`vid_bitmap_refresh` calls DryOS `_transfer_src_overlay` for both buffer 0 and buffer 1. As established in `docs/PORT35_GUI_ADDRESSES.md:35`, `_transfer_src_overlay` wipes CHDK overlay back to stock Canon graphics; thus `vid_bitmap_refresh` is erase-only (used solely by `draw_restore()`) and is never called after drawing or during shadow restore. | `chdk-port/platform/g3x/lib.c:8-18` | `reference/finsig_gm110c/stubs_entry.S:352`; `docs/PORT35_GUI_ADDRESSES.md:35` | FINSIG | Used exclusively during `draw_restore()` to erase CHDK overlay; intentionally omitted from shadow restore and all drawing paths to prevent overlay erasure. |

## Switch-Off Invariance Verification

When `G3X_GUI_DBUF` is disabled, the build produces byte-identical binaries to previously established baselines:

| Build Target | Flags | Expected SHA-256 | Actual SHA-256 | Invariance |
| :--- | :--- | :--- | :--- | :--- |
| PORT-41 Full | None | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | 100% IDENTICAL |
| PORT-42 GUI Fix | `G3X_GUI_FIX=1` | `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738` | `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738` | 100% IDENTICAL |
| PORT-42 Full Hooks | `G3X_GUI_FIX=1 FULL_HOOKS=1` | `d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb` | `d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb` | 100% IDENTICAL |

## Deliverable Binary Manifest (G3X_GUI_DBUF=1)

- Build Command: `python3 scripts/build_port43_dbuf.py`
- Toolchain: `toolchains/gcc-arm-none-eabi-5_4-2016q3` (pinned GCC 5.4.1)
- Flags: `PLATFORM=g3x PLATFORMSUB=110c G3X_FULL_BUILD=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 OPT_CAPSTONE_TOOLS=0`
- Output: `out/port43-dbuf/DISKBOOT.BIN`
  - Size: 126,073 bytes
  - SHA-256: `c6edf82d4f48aa5f13b0377d32c11d2c77e81b7d239e2e0ca47d806ea8765492`
- Modules: 34 loadable modules in `out/port43-dbuf/CHDK/MODULES/`
- Runtime Card Writes: Disabled (compile-time wrappers active)
- Fonts & Layout: 2x integer font (16x32) with 880x576 box at `(10, 12)` unchanged from PORT-42
