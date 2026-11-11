# PORT-43: Double-Buffered Overlay, Fast Fills, Partial Redraw, and Shadow Restore

This document records the implementation of `G3X_GUI_DBUF=1` (opt-in compile-time switch for PowerShot G3 X GM1.10C) designed to eliminate the overlay flicker observed in the PORT-42 owner trial (menu repainting as black bands growing down over 5-8 frames, followed by disappearance to live view).

All changes are gated behind `#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)`. When the switch is disabled, all builds produce 100% byte-identical outputs to their existing manifests.

## Technical Architecture & Changes

| Change | File:Line | Sibling Citation | Label | Expected Visible Effect |
| :--- | :--- | :--- | :--- | :--- |
| **Dual-Buffer Drawing & Opacity Fill**<br>Draw and opacity write paths write synchronously into both bitmap buffers (`bitmap_buffer[0]`, `bitmap_buffer[1]`) and both opacity buffers (`opacity_buffer[0]`, `opacity_buffer[1]`). | `chdk-port/core/gui_draw.c:289-325`<br>`chdk-port/core/gui_draw.c:375-408`<br>`chdk-port/core/gui_draw.c:500-535` | `chdk-port/platform/g7x/lib.c:18-19, 291-292`; `chdk-port/platform/g5x/lib.c:21-33` | VERIFIED | Eliminates frame-flip flicker where display page swap hides CHDK overlay; overlay persists across all hardware display flips. |
| **Dual-Buffer Sentinel Guard**<br>`draw_set_guard` and `draw_test_guard` verify sentinel bytes in both opacity buffers simultaneously. | `chdk-port/core/gui_draw.c:645-680` | `tools/build_port41_full.py:228-245`; `scripts/build_candidate_gui3.py:840-850` | VERIFIED | Instant detection if stock camera UI wipes either or both overlay planes. |
| **Fast Fills (32-bit Word Writes)**<br>`g3x_dbuf_fast_fill_rect` hooked into `draw_hline`, `draw_vline`, `draw_rectangle(DRAW_FILLED)`, and `g3x_fill_menu_opaque_black`. Uses 32-bit UYVY word pairs (`0x00800080` for black) and `memset` opacity blocks with zero per-pixel `draw_pixel` calls. | `chdk-port/core/gui_draw.c:117-237`<br>`chdk-port/core/gui_draw.c:685-710`<br>`chdk-port/core/gui_draw.c:720-745`<br>`chdk-port/core/gui_draw.c:860-890`<br>`chdk-port/platform/g3x/gui_menu.c:1235-1243` | `chdk-port/core/gui_draw.c:138-146`; `scripts/build_candidate_gui3.py:885-896` | VERIFIED | Eliminates the 200-300 ms "growing black bands" top-to-bottom paint artifact observed in PORT-42; whole-box clear occurs in sub-millisecond time. |
| **Partial Redraw for Navigation**<br>In `gui_menu_draw`, when `gui_menu_redraw == 1` and `gui_menu_top_item == dbuf_last_drawn_top_item`, unchanged lines are skipped and only the previous and current cursor items are redrawn. Navigation never triggers a full clear-and-repaint. | `chdk-port/platform/g3x/gui_menu.c:998-1025`<br>`chdk-port/platform/g3x/gui_menu.c:1159-1163` | `chdk-port/core/gui_menu.c:995-1030` | VERIFIED | Cursor navigation (up/down/scroll wheel) updates only the affected 32 px rows; no visual glitching, jumping, or full-menu blinking while navigating. |
| **Fast Shadow Buffer Restore**<br>Off-screen shadow buffer sized for 880x576 at `(10, 12)` (1,013,760 bytes bitmap + 506,880 bytes opacity). If sentinel loss occurs, `g3x_dbuf_restore_if_sentinel_lost()` restores both hardware buffers via fast row `memcpy` instead of re-evaluating the full widget tree from scratch. | `chdk-port/core/gui_draw.c:70-109`<br>`chdk-port/core/gui_draw.c:247-286`<br>`chdk-port/core/gui.c:45-56`<br>`chdk-port/core/gui.c:120-135` | `docs/PORT40_GUI_LAYOUT.md:14-28`; `scripts/build_candidate_gui3.py:820-826` | INFERRED | Layer restoration after stock UI wipe occurs in ~1-2 ms without noticeable flicker or dropped frames. Shadow buffer placement in static CHDK BSS is guarded behind `G3X_GUI_DBUF=1`. |
| **Dual-Plane Hardware Refresh Hook**<br>`vid_bitmap_refresh` calls DryOS `_transfer_src_overlay` for both buffer 0 and buffer 1. | `chdk-port/platform/g3x/lib.c:20-25` | `reference/finsig_gm110c/stubs_entry.S:352`; `chdk-port/platform/g7x/lib.c:18-19` | FINSIG | Ensures DryOS display controller commits both overlay planes to hardware VRAM simultaneously. |

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
  - Size: 125,329 bytes
  - SHA-256: `cfc147ad860b45584c60cdf752a4e2e9a0aab66b1e5cd71dccbed98feee7efa7`
- Modules: 34 loadable modules in `out/port43-dbuf/CHDK/MODULES/`
- Runtime Card Writes: Disabled (compile-time wrappers active)
- Fonts & Layout: 2x integer font (16x32) with 880x576 box at `(10, 12)` unchanged from PORT-42
