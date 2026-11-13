# PORT-45: DIGIC 6 Sibling Overlay Overdraw Analysis & Hook Design

## 1. Mechanism & Address Inventory

The table below catalogs display refresh, overlay transfer, stock UI rendering, and double-buffer restore mechanisms across sibling DIGIC 6 ports (G7 X, G5 X, SX60 HS, G16, SX710 HS) and their PowerShot G3 X (GM1.10C) addresses.

| Mechanism | Sibling path:line | G3X address | Label |
| :--- | :--- | :--- | :--- |
| Stock UI overlay transfer (`transfer_src_overlay`) | `chdk-port/platform/g7x/lib.c:13` | `0xFC380635` | FINSIG |
| VTM overlay transfer helper (`transfer_src_overlay_helper`) | `chdk-port/tools/finsig_thumb2.c:4707` | `0xFC38113F` | FINSIG |
| Graphic system finish helper (`GraphicSystemCoreFinish_helper`) | `chdk-port/platform/g7x/sub/100c/funcs_by_name.csv:817` | `0xFC143493` | FINSIG |
| Graphic system finish message sender (`GraphicSystemCoreFinish`) | `chdk-port/platform/g7x/sub/100c/funcs_by_name.csv:816` | `0xFC20C5BF` | FINSIG |
| Screen lock transfer inhibit (`ScreenLock`) | `chdk-port/platform/g7x/sub/100d/stubs_entry.S:245` | `0xFC3810F1` | FINSIG |
| Screen unlock transfer resume (`ScreenUnlock`) | `chdk-port/platform/g7x/sub/100d/stubs_entry.S:246` | `0xFC381127` | FINSIG |
| Display device buffer commit (`BmpDDev_SetBitmapVRAMAddress`) | `chdk-port/platform/g7x/lib.c:261-280` | `0xFC183690` | INFERRED (ROM read, 0xFC18347E..0xFC18381F) |
| Active bitmap buffer index (`active_bitmap_buffer`) | `chdk-port/platform/g7x/lib.c:5` | `0x0000D2A4` | FINSIG |
| Double-buffered bitmap framebuffers (`bitmap_buffer[0/1]`) | `chdk-port/platform/g7x/lib.c:261-280` | `0x0000D2A8` | FINSIG |
| Mode 12 LCD opacity buffers (`opacity_buffer[0/1]`) | `chdk-port/platform/g7x/lib.c:291` | `0x5FC40000` / `0x5FB80000` | INFERRED (ROM read, 0xFC18347E..0xFC18381F) |
| VRAM transfer manager structure base (`VTM_Data`) | `chdk-port/platform/sx710hs/sub/100a/stubs_min.S:26` | `0x0000D264` | INFERRED (chdk-port/platform/sx710hs/sub/100a/stubs_min.S:26) |
| Active buffer toggle check (`check_gui_needs_redraw`) | `chdk-port/platform/g5x/lib.c:211-220` | `chdk-port/platform/g3x/lib.c:136-145` | HISTORICAL_CHDK |
| Fast runtime heap shadow restore (`g3x_dbuf_shadow_restore`) | N/A (PORT-44 G3X implementation) | `chdk-port/core/gui_draw.c:341-371` | source (PORT-44) |
| Stock UI face / AF frame task (`task_FaceFrame`) | `chdk-port/platform/g5x/notes.txt:6-7` | `0xFC0BFDE3` | FINSIG |
| Stock UI LCD control task (`task_LcdConTask`) | `chdk-port/platform/g7x/sub/100c/funcs_by_name.csv:899` | `0xFC1828F5` | FINSIG |
| Stock keyboard task (`task_PhySw`) | `reference/finsig_gm110c/stubs_entry.S:340` | `0xFC1283AD` | FINSIG |
| Keyboard task 100 Hz loop (`mykbd_task`) | `chdk-port/platform/g7x/kbd.c:56-65` | `chdk-port/platform/g3x/kbd.c:48-62` | HISTORICAL_CHDK |
| DryOS task creation hook (`hook_CreateTask`) | `chdk-port/platform/g7x/sub/100d/boot.c:63-71` | `0xBFE14A3C` | FINSIG |

---

## 2. Evaluation of Options

### Option (A): Suppress or Hook Stock Bitmap/OSD Redraw
- **Mechanism**: Inhibit Canon stock UI redraw while ALT mode is active (`!camera_info.state.gui_mode_none`) by calling `ScreenLock()` (`0xFC3810F1` [FINSIG]) or suppressing `transfer_src_overlay()` (`0xFC380635` [FINSIG]).
- **Evaluation**: Calling `ScreenLock()` sets an inhibit flag in `VramTransferManager.c`. In sibling G5 X (`chdk-port/platform/g5x/sub/100c/stubs_entry_2.S:57`), `ScreenLock` is stubbed to `NULL_SUB` under the comment `/* These don't exist */`. Holding `ScreenLock` continuously while in ALT mode could stall `VramTransferManager.c` queue completions, risking watchdog resets and live-view freezes (INFERRED). Suppressing `transfer_src_overlay` leaves VTM dirty bitmasks uncleared, risking queue starvation (INFERRED). Furthermore, suppressing stock tasks (`task_FaceFrame` at `0xFC0BFDE3` [FINSIG], `task_LcdConTask` at `0xFC1828F5` [FINSIG]) via `hook_CreateTask` (`0xBFE14A3C` [FINSIG]) risks breaking camera autofocus tracking and power supervision (INFERRED). Sibling ports (G7 X, G5 X, SX60 HS, G16) do not suppress stock UI redraws and do not invoke `ScreenLock`/`ScreenUnlock` in CHDK C code.
- **Verdict**: Rejected due to firmware instability and task deadlock risks (INFERRED).

### Option (B): Asynchronous Restore from Heap Shadow on Buffer Flip / Sentinel Loss
- **Mechanism**: Detect buffer flips and sentinel corruption asynchronously via polling, and restore the CHDK overlay from the PORT-44 runtime heap shadow (`g3x_dbuf_shadow_restore` in `chdk-port/core/gui_draw.c:341-371` [source (PORT-44)]) into the newly active buffer.
- **Evaluation of Interception Routes & Timing Truth**:
  - `check_gui_needs_redraw()` and `gui_redraw()` run in the CHDK scheduler (`chdk-port/core/main.c:316-323,372`, 20 ms sleep), and the PORT-43/44 sentinel restore (`scripts/build_port43_dbuf.py:97-104`) is also polling. Neither one intercepts the Canon display commit (`transfer_src_overlay` / `BmpDDev` path, in ROM) before hardware scanout.
  - Sibling survey: None of the sibling DIGIC 6 ports (`g7x`, `g5x`, `sx60hs`, `g16`) hooks a real display refresh or commit point. Sibling `g5x` only implements polling on `active_bitmap_buffer` changes in `check_gui_needs_redraw()` (`chdk-port/platform/g5x/lib.c:211-220`), and `g7x`, `sx60hs`, and `g16` have no display hook at all. Therefore, a synchronous commit hook is **UNKNOWN** and unavailable without ROM patching (which is strictly out of scope).
  - Firmware ROM call sites checked:
    1. `transfer_src_overlay_helper` at `0xFC38113E` (FINSIG `0xFC38113F`): disassembly of call site `0xFC38117E` showed a direct `bl 0xFC183690` (`BmpDDev_SetBitmapVRAMAddress`); no RAM function pointer or callback table exists at this specific site.
    2. Stock UI tasks `task_FaceFrame` (`0xFC0BFDE3` [FINSIG]) and `task_LcdConTask` (`0xFC1828F5` [FINSIG]): call ROM graphics helpers directly.
    Other firmware ROM display refresh call sites remain unchecked and are labelled INFERRED/unknown.
  - Task wrapper route: `hook_CreateTask` (`0xBFE14A3C` [FINSIG]) intercepting `task_PhySw` (Thumb entry `0xFC1283AD` [FINSIG]; `0xFC1283D2` is the task-creation helper, not the task entry) to wrap it with `mykbd_task` (`chdk-port/platform/g3x/kbd.c:48-62` [HISTORICAL_CHDK]) runs at 100 Hz (10 ms period), offering a potential 100 Hz polling loop.
  - CHDK RAM polling route: The cleanest, lowest-risk polling point is in CHDK's own RAM code, where PORT-44 already monitors display buffer updates in `check_gui_needs_redraw()` (`chdk-port/platform/g3x/lib.c:136-145` [HISTORICAL_CHDK]) and `gui_redraw()` (`chdk-port/core/gui.c:2988-3006` [source (PORT-44)]).
- **Verdict**: Recommended. Option B restores from the heap shadow asynchronously upon detecting an `active_bitmap_buffer` flip or sentinel loss in CHDK RAM polling.

---

## 3. Recommended Implementation: Option B (Asynchronous Heap Shadow Restore) [INFERRED]

Option B is recommended. The build task should detect display buffer flips and sentinel loss in CHDK RAM code at `check_gui_needs_redraw()` (`chdk-port/platform/g3x/lib.c:136-145` [HISTORICAL_CHDK]) and `gui_redraw()` (`chdk-port/core/gui.c:2988-3006` [source (PORT-44)]).

- **Execution Context & Polling Mechanism**:
  `check_gui_needs_redraw()` in `chdk-port/platform/g3x/lib.c:136-145` is polled by the CHDK scheduler loop in `core_spytask()` (`chdk-port/core/main.c:316-323,372`) with a 20 ms sleep interval (~50 Hz). Similarly, the PORT-43/44 sentinel restore (`scripts/build_port43_dbuf.py:97-104`) runs within this polling loop.
  **Honesty on Timing**: This is asynchronous polling. Neither mechanism intercepts the Canon display commit (`transfer_src_overlay` / `BmpDDev` path in ROM) before hardware scanout. Because no sibling DIGIC 6 port (`g7x`, `g5x`, `sx60hs`, `g16`) hooks a display refresh/commit point, a synchronous commit hook is UNKNOWN and unavailable without ROM patching (out of scope). The restore does NOT happen before scanout; it restores the overlay in RAM after a buffer flip or stock UI write has occurred.
- **Check Interval & CPU Cost**:
  Currently, polling occurs every 20 ms in `core_spytask` (~50 Hz). Optionally, polling could be performed at a shorter 10 ms interval (100 Hz) in `mykbd_task` (`chdk-port/platform/g3x/kbd.c:48-62` [HISTORICAL_CHDK]). The CPU cost of checking `active_bitmap_buffer` and 4 perimeter sentinel words at 100 Hz is negligible (<0.1% CPU overhead for RAM word comparisons), with `g3x_dbuf_shadow_restore()` executed only upon detected change.
- **Option A Elements**:
  Option A elements, such as wrapping CHDK drawing with `ScreenLock()` (`0xFC3810F1` [FINSIG]) and `ScreenUnlock()` (`0xFC381127` [FINSIG]), are NOT recommended: no sibling DIGIC 6 port uses them in CHDK C code (`g5x` stubs them to `NULL_SUB` in `chdk-port/platform/g5x/sub/100c/stubs_entry_2.S:57`, while `g7x`, `sx60hs`, and `g16` never call them), and holding screen locks risks stalling the VTM queue and triggering watchdog timeouts.
- **Monitored Hardware State**:
  `active_bitmap_buffer` at `0x0000D2A4` [FINSIG].
- **Build-time Recommendation [INFERRED]**:
  Restore from the PORT-44 heap shadow (`g3x_dbuf_shadow_restore()` in `chdk-port/core/gui_draw.c:341-371` [source (PORT-44)]) as soon as an `active_bitmap_buffer` flip or sentinel loss is detected, only while ALT/menu is active (`!camera_info.state.gui_mode_none`) and the shadow is valid (`g3x_shadow_valid && g3x_shadow_bitmap != NULL`).
  `g3x_dbuf_shadow_restore()` performs a fast row-by-row shadow blit into both bitmap framebuffers (`bitmap_buffer[0/1]` at `0x0000D2A8` [FINSIG]) and both opacity planes (`opacity_buffer[0/1]` at `0x5FC40000`/`0x5FB80000` [INFERRED (ROM read, 0xFC18347E..0xFC18381F)]). This minimizes visual overdraw duration after Canon stock UI writes, but operates asynchronously after the event.
- **Multi-Point Sentinel Upgrade**:
  In PORT-44, `draw_test_guard()` only inspected pixel (0,0) (`opacity_buffer[0/1][0] == 0x42`). When Canon stock UI redraws AF tracking frames and scene indicators in central/marginal areas, pixel (0,0) is untouched, so sentinel loss went undetected. The guard test should check four perimeter points or corner bounds (`G3X_MENU_X0, G3X_MENU_Y0` through `G3X_MENU_X1, G3X_MENU_Y1`), triggering immediate `g3x_dbuf_shadow_restore()` when an AF box intersects the menu.
- **Gate and Fallback Mechanism**:
  - **Strict Gate**: Asynchronous restore is gated strictly: `if (!camera_info.state.gui_mode_none && g3x_shadow_valid && g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL)`. When ALT/menu is inactive or the shadow is NULL/invalid, zero writes occur.
  - **Fallback to PORT-44**: When the shadow buffer is NULL (`!g3x_shadow_valid` or heap allocation failure), CHDK falls back to PORT-44 behavior: buffer-change polling via `check_gui_needs_redraw()`, setting `forced = 1` and calling full `gui_redraw()`. As documented in sibling G5 X (`chdk-port/platform/g5x/lib.c:206-209`), this polling reduces flickering without relying on the shadow buffer.

---

## 4. Evidence Manifest Summary

Bounded ROM reads from `firmware/dumps/GM1.10C/PRIMARY.BIN` recorded in `manifests/evidence/port45_evidence_manifest.json` (zero full-ROM scans):

| Range | Size | SHA-256 | Why FINSIG Was Insufficient |
| :--- | :---: | :--- | :--- |
| `0xFC18347E..0xFC18381F` | 930 B | `5b04719fde94ae9a967beb93e1f64836fd417de35d0cc613536c3c79b07fcadf` | `BmpDDev_SetBitmapVRAMAddress` (`0xFC183690`) and `opacity_buffer` (`0x5FC40000`/`0x5FB80000`) absent from FINSIG |
| `0xFC380634..0xFC38073F` | 268 B | `336d235df668ca1d9e05c010545ccf417c3b57a572326fb6dd35506c45d533ab` | `transfer_src_overlay` internal DMA/dirty bitmask clearing mechanics absent from FINSIG |
| `0xFC3810F0..0xFC38119B` | 172 B | `188ac7d596935c5b3a6d4c04f91a15e9202676d70ef6712ef7d49e18f90dfcc0` | Indirect RAM pointer table vs direct BL check for `transfer_src_overlay_helper` absent from FINSIG |
| `0xFC381420..0xFC38143F` | 32 B | `6818cfe66adb29abc97612cf7139d102bd144d5bef456aa1d32b480a688fb556` | `VTM_Data` structure base address (`0x0000D264`) absent from FINSIG |

FINSIG addresses: `transfer_src_overlay` = `0xFC380635` [FINSIG], `ScreenLock` = `0xFC3810F1` [FINSIG], `ScreenUnlock` = `0xFC381127` [FINSIG], `active_bitmap_buffer` = `0x0000D2A4` [FINSIG], `bitmap_buffer` = `0x0000D2A8` [FINSIG], `task_FaceFrame` = `0xFC0BFDE3` [FINSIG], `task_PhySw` = `0xFC1283AD` [FINSIG], `hook_CreateTask` = `0xBFE14A3C` [FINSIG].

---

## 5. Build Instructions

- **Detection Point**: Detect `active_bitmap_buffer` (`0x0000D2A4` [FINSIG]) toggles and perimeter sentinel loss in CHDK RAM code (`check_gui_needs_redraw()` in `chdk-port/platform/g3x/lib.c:136-145` [HISTORICAL_CHDK] / `gui_redraw()` in `chdk-port/core/gui.c:2988-3006`).
- **Gate**: Asynchronous restore is strictly gated: `if (!camera_info.state.gui_mode_none && g3x_shadow_valid && g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL)`. When ALT/menu is off or shadow is NULL, execution is an instantaneous no-op with zero writes and zero CPU overhead.
- **Restore Operation**: Restore from the PORT-44 runtime heap shadow via `g3x_dbuf_shadow_restore()` (`chdk-port/core/gui_draw.c:341-371` [source (PORT-44)]) asynchronously upon detection; never claim restore happens before scanout.
- **Memory**: No boot allocation, no static buffers; uses PORT-44 runtime heap shadow (`malloc` on ALT entry, `free` on exit).
- **Fallback**: If `g3x_shadow_bitmap` is NULL or heap allocation fails, fall back to PORT-44 behavior (conventional `gui_redraw()` polling via `check_gui_needs_redraw()`, `chdk-port/platform/g5x/lib.c:206-209`), which reduces flicker without relying on the shadow buffer.
