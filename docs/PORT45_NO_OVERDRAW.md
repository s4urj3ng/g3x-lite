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
| Active buffer changed check (`check_bitmap_buffer_changed`) | `chdk-port/platform/g5x/lib.c:211-220` | `stage_chdk/platform/g3x/lib.c:290-300` (`full_build/g3x/lib.c:290-300`) | HISTORICAL_CHDK (PORT-42/45) |
| Multi-point perimeter sentinels (`draw_set_guard` / `draw_test_guard`) | `chdk-port/platform/g5x/lib.c:211-220` & `g7x/lib.c:303-358` | `stage_chdk/core/gui_draw.c:145-188` | source (PORT-45) |
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
  In PORT-44, `draw_test_guard()` only inspected pixel (0,0) (`opacity_buffer[0/1][0] == 0x42`). When Canon stock UI redraws AF tracking frames and scene indicators in central/marginal areas, pixel (0,0) is untouched, so sentinel loss went undetected. The implementation checks four margin points outside the menu, in addition to (0,0). A buffer flip or corruption of a monitored point triggers asynchronous `g3x_dbuf_shadow_restore()`. Overdraw confined to the menu interior with no buffer flip can remain undetected.
- **Gate and Fallback Mechanism**:
  - **Strict Gate**: Asynchronous restore is gated strictly: `if (!camera_info.state.gui_mode_none && g3x_shadow_valid && g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL)`. When ALT/menu is inactive, no extra restore occurs. With a NULL/invalid shadow, the scheduler uses the PORT-44 guard-loss fallback; the ordinary (0,0) guard remains in use.
  - **Fallback to PORT-44**: When the shadow buffer is NULL (`!g3x_shadow_valid` or heap allocation failure), CHDK falls back to PORT-44 behavior: ignore buffer flips while guards are intact; set `forced = 1` and call `gui_redraw(1)` on guard loss. The implemented scheduler is in `scripts/build_port43_dbuf.py:282-326`.

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
- **Gate**: Asynchronous restore is strictly gated: `if (!camera_info.state.gui_mode_none && g3x_shadow_valid && g3x_shadow_bitmap != NULL && g3x_shadow_opacity != NULL)`. With ALT/menu off, there is no extra restore or perimeter guard write. With a NULL shadow, the PORT-44 guard-loss fallback remains active. The scheduler still polls each tick.
- **Restore Operation**: Restore from the PORT-44 runtime heap shadow via `g3x_dbuf_shadow_restore()` (`chdk-port/core/gui_draw.c:341-371` [source (PORT-44)]) asynchronously upon detection; never claim restore happens before scanout.
- **Memory**: No boot allocation, no static buffers; uses the PORT-44 runtime heap shadow (one lazy allocation attempt on ALT/menu entry, retained and invalidated on exit).
- **Fallback**: If `g3x_shadow_bitmap` is NULL or heap allocation fails, fall back to PORT-44 behavior: ignore flips with intact guards and request `gui_redraw(1)` on guard loss.

---

## 6. Implementation & Build Verification (PORT45-NO-OVERDRAW-BUILD)

The Option B overlay protection design is implemented behind the opt-in build flag `G3X_GUI_NOOVERDRAW=1` (which requires and layers upon `G3X_GUI_DBUF=1`).

### Build Flags and Toolchain
- **Build Invocation**: `python3 scripts/build_port45_no_overdraw.py` (or `make port45_no_overdraw`).
- **Flags**: `G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1`.
- **Enforcement**: Build dependency is defined solely in `chdk-port/platform/g3x/Makefile` (and staged to `sub/110c/Makefile` by the build script), strictly enforcing that `G3X_GUI_NOOVERDRAW=1` requires `G3X_GUI_DBUF=1`. To avoid redundant flag definitions, `makefile.inc` is left unmodified.
- **Toolchain**: Pinned `toolchains/gcc-arm-none-eabi-5_4-2016q3`.

### Artifacts & Hashes
- **Output Directory**: `out/port45-no-overdraw/`
- **DISKBOOT.BIN Size**: 126,977 bytes
- **DISKBOOT.BIN SHA-256**: `2be1877e495a0d2aee07851eee6e0294eb2d62ba9db2707b929fa2cf7927a684`
- **Tracked manifest**: [`manifests/port45_gui_nooverdraw_manifest.json`](../manifests/port45_gui_nooverdraw_manifest.json); generated copy: `out/port45-no-overdraw/port45_no_overdraw_manifest.json`.

### Memory & Symbol Verification
- **_end Symbol**: `0x00369560` (link_bss_end).
- **Delta vs PORT-42 Baseline (`0x003687b0`)**: +3,504 bytes (~3.42 KiB), well within the 64 KiB margin (65,536 bytes).
- **Static Buffers Added**: 0 bytes (no static overlay or shadow buffers added).
- **Largest Symbol in BSS/Data**: `font_data` (3,473 bytes); no symbol approaches 64 KiB.
- **Boot Allocation**: 0 bytes allocated during boot. The shadow has one lazy heap allocation attempt upon ALT/menu entry and is retained and invalidated on exit; no new shadow allocation occurs during boot.

### Runtime Behavior & Acceptance Criteria
1. **ALT Gating**: Active only while CHDK ALT mode or CHDK menu is active (`!camera_info.state.gui_mode_none`). With ALT off, `draw_set_guard()` and `draw_test_guard()` write and test only sentinel (0, 0), matching PORT-44 byte-for-byte. Zero extra pixels are written at startup (`draw_init`) or at `draw_restore()`.
2. **Sentinel Protection**: 5-point perimeter sentinel monitoring: sentinel (0,0) and 4 margin corners placed outside the 880x576 menu fill (`[10,889] x [12,587]`) but inside the 928x600 bitmap buffer (display 900x600):
   - Top-Left: `(8, 10)`
   - Top-Right: `(891, 10)`
   - Bottom-Left: `(8, 589)`
   - Bottom-Right: `(891, 589)`
   Because these pixels lie outside the menu fill area, drawing the CHDK menu never trips a sentinel. Any stock UI overdraw (e.g. AF boxes, face detection frames) touching the perimeter immediately triggers asynchronous shadow restore.
3. **NULL Shadow Fallback**: If the shadow buffer is NULL or unavailable, buffer flips are ignored (causing zero redraws when guards are intact), and only sentinel corruption triggers `forced = 1` -> `gui_redraw(1)`, identically matching PORT-44 behavior with no crashes or tick-by-tick thrashing.
4. **Byte Identity**: Builds without `G3X_GUI_NOOVERDRAW=1` remain 100% byte-identical to existing baseline manifests (verified by 24 tests in `tests/test_port44_dbuf_heap.py`).

## 7. Owner trial plan (future owner execution only)

This task performed host builds and tests only. Hardware results remain **UNKNOWN**.

1. Before an independently authorized trial, verify the candidate against
   [`port45_gui_nooverdraw_manifest.json`](../manifests/port45_gui_nooverdraw_manifest.json):
   `DISKBOOT.BIN`, **126,977 bytes**, SHA-256
   `2be1877e495a0d2aee07851eee6e0294eb2d62ba9db2707b929fa2cf7927a684`.
2. Start with a **short press** of Power (less than 0.5 s). Observe normal boot,
   live view and controls before entering ALT. Stop on a failed boot or freeze.
3. Enter ALT and open the CHDK menu. Keep ALT/menu on for **at least 10 s**,
   moving the camera across a detailed scene and repeatedly half-pressing the
   shutter to trigger **AF**. Navigate several menu rows too.
4. Report whether the menu remains readable and opaque during motion/AF; note
   flicker, erased areas, stock AF-box show-through, colour/font/layout changes,
   freezes or resets. Exit ALT and compare live view, controls and normal power-off
   with PORT-44. A short video is useful. This asynchronous polling design cannot
   guarantee an undisturbed scanout or detect every interior-only stock write.
5. Stop and roll back on any regression. The known PORT-44 rollback DISKBOOT is
   **126,769 bytes**, SHA-256
   `2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382`
   ([manifest](../manifests/port44_dbuf_heap_manifest.json)). If the camera is
   unresponsive, use **battery-pull recovery**: remove the NB-10L battery, wait at
   least **10 s**, and leave power removed while the owner restores the known-good
   PORT-44 candidate using their established rollback procedure. Reinsert the
   battery and verify recovery; stop further trials if recovery fails.

## 8. Host evidence for PORT45-TESTS-TRIAL-R2

**VERIFIED**, retrieved 2026-11-13 against source commit
[`19fec9339f7a80c3c1f2a471dfcfc913b96f92e7`](https://github.com/s4urj3ng/g3x-lite/tree/19fec9339f7a80c3c1f2a471dfcfc913b96f92e7):
the pinned ARM toolchain completed two clean builds in separate staging trees.
All **243 distribution files** (DISKBOOT plus **242 CHDK files**, including 34
modules) have equal file sets, sizes, SHA-256 hashes and actual bytes. The tracked
manifest records the measured hash and size of every distribution file. Staging
objects and the manifest itself are build metadata, outside that distribution.

Reproduce the clean builds and PORT-45 checks from the repository root:

```sh
mkdir -p out/port45-validation/tmp
export TMPDIR="$PWD/out/port45-validation/tmp"
python3 -B scripts/build_port45_no_overdraw.py > out/port45-validation/build-first.log 2>&1
python3 -B scripts/build_port45_no_overdraw.py --out-dir out/port45-validation/second > out/port45-validation/build-second.log 2>&1
python3 -B scripts/test_port45_no_overdraw.py -v
python3 -B -m unittest tests.test_port44_dbuf_heap -v
```

The first two commands use the scripts' default clean staging behavior, without
`--no-clean`. [`scripts/test_port45_no_overdraw.py`](../scripts/test_port45_no_overdraw.py)
checks every distribution byte against the second build and every hash/size
against the tracked manifest. [`tests/test_port45_validation.py`](../tests/test_port45_validation.py)
exposes these checks to `port_tests` discovery. The test fixture also removes both
cached distribution trees and builds them again, so subsequent test runs exercise
clean builds of the current sources. The compiler reports GNU ARM Embedded
5.4.1 20160919, branch revision 240496.

**VERIFIED** memory results from pinned `arm-none-eabi-nm -S` on each staged
`platform/g3x/sub/110c/main.elf`. Fresh clean builds of the seven other variants
are recorded under `out/port45-validation/r2/baselines/`; each applicable existing
distribution manifest was checked without changing its expected hashes.
Measured summaries are in `out/port45-validation/r2/baseline-results.json` and
`out/port45-validation/r2/nooverdraw-results.json` (ignored host evidence):

| Full-build variant | `_end` | Difference from PORT-42 |
| --- | --- | ---: |
| Default PORT-41 | `0x003686b0` | -256 B |
| PORT-42 GUI_FIX | `0x003687b0` | 0 B |
| FULL_HOOKS | `0x003686f0` | -192 B |
| GUI_FIX + FULL_HOOKS | `0x003687f0` | +64 B |
| PORT-44 DBUF | `0x00369490` | +3,296 B |
| DBUF + FULL_HOOKS | `0x003694c0` | +3,344 B |
| NOOVERDRAW | `0x00369560` | +3,504 B |
| NOOVERDRAW + FULL_HOOKS | `0x003695a0` | +3,568 B |

NOOVERDRAW is **208 bytes above PORT-44's `0x00369490`**. Every variant is within
65,536 bytes of PORT-42, and **every sized core symbol**, including text, is at
most 65,536 bytes. The largest is `font_data`, 3,473 bytes, in all eight variants.

**VERIFIED**: all 24 PORT-44 regression tests pass, comparing full distributions
against the existing default, GUI_FIX, FULL_HOOKS, GUI_FIX + FULL_HOOKS and DBUF
manifests, and checking the pinned DISKBOOT hashes and sizes of all 19 PORT-24..40
candidates. This host initially contained a stale ignored `libplatform.a`: its
embedded `lib.o` had an extra `update_screen_dimensions` stub absent from the
baseline object/source. The exact local repair was:

```sh
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-ar r chdk-port/platform/g3x/libplatform.a chdk-port/platform/g3x/lib.o
```

No baseline hash was changed; the rebuilt candidates then matched their pinned
hashes. The archive and build outputs remain ignored and uncommitted.

The R2 discovery run additionally exposed nondeterministic timestamps/ownership
in that ignored archive. All six member names and object bytes compared equal
using pinned `ar t` / `ar p` against the deterministic output of
[`build_fallback_libplatform_a()`](../scripts/build_candidate_gui3.py#L1940).
The shared ignored archive was replaced with that output (SHA-256
`c8eba0e13f263cb1b884f6f53ef6e055fb48e57a60ca7637e442fec98210b035`),
preserving every member's contents. No tracked source or baseline manifest was
changed by either local archive repair.

To recreate the deterministic ignored archive from current sources, after
checking that the pinned candidate hashes still match:

```sh
TMPDIR="$PWD/out/port45-validation/tmp" python3 -B - <<'PY'
import sys
sys.path.insert(0, "scripts")
from build_candidate_gui3 import build_fallback_libplatform_a
build_fallback_libplatform_a("chdk-port/platform/g3x/libplatform.a")
PY
```

**VERIFIED**: all eight PORT-45 checks pass. The host model compiles the built
variant's actual C guard, restore, allocation/init and scheduler branch, with
mock framebuffers and camera state. It checks ALT-off equivalence, restores both
bitmap/opacity planes byte-for-byte after simulated overdraw, NULL and half-NULL
or invalid shadows, no shadow allocation during boot, one lazy allocation on
entry, and canaries. A NULL host restore-service pointer models an unavailable
hook and requests the ordinary guard-loss redraw without crashing. Production
calls the statically linked restore function; it has no optional firmware display
hook. Mutation checks reject removal of ALT gating, omission of an opacity-plane
restore and introduction of boot shadow allocation.

**VERIFIED**: `python3 -B tools/validate_candidate_port2a.py` passes all offline
candidate checks. The optional `--use-existing-inspector` build initially refused
the stale owner-local `0x0035f780` inspector metadata. The candidate instead uses
the already generated, verified inspector assets from the passing default
candidate under `out/port43-test/candidate_default/`, associated with
`copy_inspector_artifacts()` and recorded by `generate_manifest()` from
`tools/build_candidate_port2a.py`. The stale owner-local assets were left intact.

`port_tests` discovery uses `test_port*.py`, which excludes the forbidden
`tests/test_validate_witness_inspector.py`. It also explicitly skips
`TestPort19WitnessAddress.test_validator_rejects_self_consistent_0035f780_under_python_optimize`,
because that method invokes `tools/build_witness_inspector.py`'s payload builder.
The four pre-existing PORT-27 NO-GO skips remain in place. No repository test or
CI configuration was changed to apply this run-local safety exclusion.

**VERIFIED final R2 results (2026-11-13)**: discovery completed **1,428 tests in
529.316 s, OK (skipped=5)**, including all eight PORT-45 checks. The earlier sole
archive-metadata failure passed both its focused rerun and this full rerun.
`python3 -B tools/validate_candidate_port2a.py` then passed every offline check;
`git diff --check` passed. Exact final invocations and retained host logs:

```sh
TMPDIR="$PWD/out/port45-validation/tmp" python3 -B out/port45-validation/r2/run_port_tests.py > out/port45-validation/r2/port-tests-rerun.log 2>&1
python3 -B tools/validate_candidate_port2a.py > out/port45-validation/r2/candidate-validation-final.log 2>&1
```

The ignored run-local runner performs ordinary unittest `test_port*.py`
discovery and applies only the PORT-19 safety skip named above.

**INFERRED**: these results support the intended host control flow. **UNKNOWN**:
actual camera timing, visible flicker under AF/motion, allocator success on the
camera and physical-device safety. No new ROM inspection or hardware operation
was performed for this task.

