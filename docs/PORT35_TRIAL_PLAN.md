# PORT-35: Owner Trial and Recovery Plan — Opt-In `G3X_GUI=1` Candidate (GM1.10C)

**Target**: Canon PowerShot G3 X (`GM1.10C`, Platform ID `0x32A8`).  
**Safety Protocol**: Phase 0 rules apply (`docs/SAFETY.md`). Host builds offline only; owner executes hardware trials by hand. Binary is strictly RAM-only (`DISKBOOT.BIN` in DRAM), with zero flash ROM or NVRAM modification. No classifier or decoder tools are used.

---

## 1. Candidate Build & Artifact Pins (`docs/PORT35_GUI_ADDRESSES.md` §1)

| Parameter | Value / Specification |
| :--- | :--- |
| **Target Firmware / Platform** | Canon PowerShot G3 X (`GM1.10C`, PID `0x32A8`) |
| **Pinned Toolchain** | `toolchains/gcc-arm-none-eabi-5_4-2016q3` (`arm-none-eabi-gcc` 5.4.1 20160919) |
| **Build Flags** | `G3X_GUI=1` (`--gui`, implies `G3X_OSD2=1`, `G3X_KBD=1`, `G3X_RESIDENT=1`, `G3X_POWERON_FIX=1`, `LED_LADDER=1`) |
| **Build Command** | `G3X_GUI=1 python3 -B tools/build_candidate_port25_ladder_fix.py --gui --out-dir <dir>` |
| **Expected `DISKBOOT.BIN` SHA-256** | `1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272` |
| **Binary Sizes & Bounds** | `DISKBOOT.BIN`: `103,057` B; loaded `candidate_main.bin`: `101,616` B |
| **Memory Clearance** | `boot_witness`: `0x0035CCD0`; `_end`: `0x00362D10` $\le$ DryOS heap `0x00368880` (`23,408` B clearance) |
| **Execution Mode** | Strictly RAM-only; SD card writes, config saves, scripts, and module loaders compiled out |

---

## 2. Pre-Trial Prep & Boot Procedure

| Stage | Procedure | Expected State / Safety Gate |
| :--- | :--- | :--- |
| **Card Prep** | Format SD card as FAT32 `BOOTDISK` (`0x1E0` signature present). | SD card partitioned and bootable. |
| **Staging** | Copy candidate `DISKBOOT.BIN` to root (`A/DISKBOOT.BIN`). | Target binary placed at card root. |
| **Integrity Gate** | Run `sha256sum <card>/DISKBOOT.BIN` on host. | Must equal `1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272`. **STOP if mismatch**. |
| **Write Protect** | Slide SD card lock switch to **LOCKED** position. | Physical hardware write protect engaged. |
| **Battery Check** | Insert fully charged Canon NB-10L battery pack. | Full voltage to prevent brownout during boot. |
| **Held-Press Boot** | Press and **hold Power button continuously** through the ladder until stock UI appears (~1-2 s). | Breadcrumb ladder (`1..7`, `11..44`) runs; release button once stock UI loads. |
| **Trial Budget** | Hard limit: **Maximum 2 power-ons** per candidate run. | Limit physical battery cycles and ensure safety. |

---

## 3. Step-by-Step Trial Checks & Expected Observations

| Check # | Target Action | Input / Trigger | Expected Observation | Result |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Heartbeat LED Pattern** | Release Power after ladder boot | Rear green LED (`0xD20B0884`) runs steady **~1.0 Hz single blink** (`100 ms ON -> 900 ms OFF`), identical to PORT-34 baseline. Stock Canon UI is active and responsive. | [ ] PASS<br>[ ] FAIL |
| **2** | **ALT Key Toggle** | Press Playback button (`KEY_PLAYBACK`) | Rear green LED switches from single blink to **~1.0 Hz double blink** (`100 ms ON -> 100 ms OFF -> 100 ms ON -> 700 ms OFF`), confirming ALT mode entry. | [ ] PASS<br>[ ] FAIL |
| **3** | **Menu Open & OSD Drawing** | In ALT mode (from Check 2) | CHDK Main Menu (`gui_menu`) opens automatically on OSD. Text is sharp and crisp white; background is solid opaque black; edges are straight; no upper-screen stripes; no 30 Hz frame flickering. | [ ] PASS<br>[ ] FAIL |
| **4** | **D-Pad Navigation & SET Selection** | Press D-pad Up / Down / Left / Right, then press SET | D-pad Up/Down moves highlight cursor smoothly across menu items. Left/Right or SET enters submenus or toggles an option value (e.g. OSD layout or display toggle). | [ ] PASS<br>[ ] FAIL |
| **5** | **Menu Close** | Press Menu button (`KEY_MENU`) | CHDK menu closes. OSD overlay box is erased cleanly from both screen buffers; no residual ghost graphics or artifacts linger. | [ ] PASS<br>[ ] FAIL |
| **6** | **ALT Exit to Stock UI** | Press Playback button (`KEY_PLAYBACK`) | ALT mode exits. Rear green LED returns to **~1.0 Hz single blink**. Full control returns immediately to stock Canon UI (shutter, zoom, dials, stock menus all function normally). | [ ] PASS<br>[ ] FAIL |
| **7** | **Short-Press Boot Unchanged** | Power off; short tap Power button (<0.5 s) | Camera boots cleanly past Code 43 without shutting down (power hold fix active). Stock UI loads and single-blink heartbeat starts. | [ ] PASS<br>[ ] FAIL |
| **8** | **RAM-Only Setting Volatility** | Change a menu item in Check 4, power off, power on | Power off completely. Power on again, re-enter ALT menu. The setting changed previously has **reverted to default** (proves zero persistence to card or NVRAM). | [ ] PASS<br>[ ] FAIL |

---

## 4. Mapping of `docs/PORT35_GUI_ADDRESSES.md` INFERRED Rows to Observations

| Row Name / Symbol | GM1.10C Value | Sibling Source | Confirming Observation | Refuting Observation | Relevant Check(s) |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `h1` (pixel format & stride) | `16-bpp UYVY (stride 1472 B) + 8-bpp opacity (stride 736 B)` | `g7x lib.c:291`<br>`gui_draw.c:72` | Menu box and text draw without horizontal or vertical stripes; raster is solid. | Upper-screen stripes recur as seen in PORT-34 OSD v1 trial. | Checks 3, 4 |
| `h2` (active buffer sync) | `bitmap_buffer[active & 1]`, `opacity_buffer[active & 1]` | `g7x lib.c:279`<br>`gui_draw.c:48` | Menu and cursor remain rock-solid across Canon buffer flips without 30 Hz flicker or tearing. | Overlay flickers between alternate frames or displays torn partial frames. | Checks 3, 4 |
| `h3` (keyboard loop redraw) | `g3x_osd2_kbd_redraw` in `mykbd_task` (no `vid_bitmap_refresh`) | `g7x lib.c:7`<br>`gui_draw.c:420` | Menu stays visible continuously in ALT mode without being erased by stock UI compositor. | Menu disappears immediately after opening while LED still double-blinks. | Checks 3, 4 |
| `G3X_OSD2_UNCACHED_BIT` | `0x40000000` | `g7x makefile.inc:20` | Uncached framebuffer writes show immediately on LCD without missing tiles or delay. | Display writes corrupt DRAM or do not update until external cache eviction. | Checks 3, 4, 5 |
| `G3X_OSD2_UYVY_WHITE` | `0xFF80` | `gui_draw.c:15`<br>`g7x platform_camera.h:47` | Menu text, border, and cursor render pure neutral white (`Y=0xFF, U/V=0x80`). | Text or border appears discolored (green, magenta, or yellow cast). | Checks 3, 4 |
| `G3X_OSD2_UYVY_BLACK` | `0x0080` | `gui_draw.c:15`<br>`g7x platform_camera.h:47` | Menu box background renders pure neutral black (`Y=0x00, U/V=0x80`). | Menu box background appears tinted green or purple. | Checks 3, 4 |
| `G3X_OSD2_OPACITY_OPAQUE` | `0xFF` | `gui_draw.c:18,78` | Menu background is completely opaque; live view behind menu is fully obscured. | Menu background is translucent or completely transparent over live view. | Checks 3, 4 |
| `G3X_OSD2_OPACITY_TRANSPARENT` | `0x00` | `gui_draw.c:18,115` | Closing menu or exiting ALT clears opacity to 0; live view is fully restored. | Dark ghost rectangles or leftover menu pixels persist on live view. | Checks 5, 6 |
| `G3X_OSD2_BOX_X` / `BOX_Y` | `16, 16` | `osd_test_overlay.h:41` | Test banner / overlay anchor renders near top-left offset `(16, 16)`. | Overlay renders shifted off-screen or overlaps screen edges. | Check 3 |
| `G3X_OSD2_BOX_W` | `120` | `osd_test_overlay.h:43` | Test banner spans exactly 120 pixels wide without horizontal distortion. | Banner is horizontally compressed or stretched across LCD. | Check 3 |
| `G3X_OSD2_BOX_H` | `40` | `osd_test_overlay.h:44` | Test banner spans exactly 40 pixels tall without vertical clipping. | Banner is vertically clipped or stretched. | Check 3 |
| `G3X_OSD2_BORDER` | `2` | `osd_test_overlay.h:111` | White border around overlay elements is uniform 2 pixels wide. | Border is missing, uneven, or single-pixel wide. | Check 3 |
| `g3x_osd2_chdk_glyph_rows` | `0x7565, 0x4555, 0x4756` | `osd_test_overlay.h:67` | "CHDK" banner text is legible and properly proportioned. | Banner text renders as illegible dots or corrupted patterns. | Check 3 |
| `g3x_osd2_alt_glyph_rows` | `0xE8E0, 0xA840, 0xE840, 0xAE40` | `osd_test_overlay.h:79` | "ALT" indicator glyph renders cleanly when ALT mode is active. | "ALT" glyph is missing, garbled, or remains visible when ALT is off. | Checks 2, 3, 6 |
| `G3X_GUI_HEAP_START` | `0x00368880` | `g7x makefile.inc:24` | System boots and executes GUI heap allocations cleanly; `_end` (`0x00362D10`) clears heap. | Memory fault or crash occurs during heap allocations in `malloc`/`gui_init`. | Checks 1, 3, 4 |
| `G3X_GUI_INIT_FILE_MODULES_SUB` | `0xFC0BB6FE` | `g7x boot.c:410`<br>`g5x boot.c:524` | `core_spytask_can_start()` gates startup until file modules init; boot is smooth. | Task startup races DryOS initialization; camera freezes before stock UI loads. | Check 1 |
| `kbd_driven_gui_redraw` | `1` | `g7x kbd.c:70`<br>`core/main.c:218` | Menu responds to key inputs and redraws on tick count; smooth ALT transitions. | Menu fails to redraw on keypress or freezes the keyboard task. | Checks 2, 3, 4, 6 |
| `focus_len_table` | `0xFDF317D8` | `g7x main.c:11`<br>`stubs_entry.S:179` | Focal length / zoom queries in Miscellaneous Values display valid numbers. | Focal length reads zero, negative, or causes an exception when queried. | Check 4 |
| `levent_table` | `0xFC7714F8` | `g7x stubs_entry.S:174`<br>`stubs_min.S:3` | Menu navigation and key handling run without event-table lookup faults. | Crash or panic when processing key events or dialog triggers. | Checks 4, 5, 6 |
| `recreview_hold` | `0x000095F0` | `g7x stubs_min.S:7`<br>`stubs_min.S:5` | State queries in `camera_info` evaluate review hold safely without crash. | System freeze when switching modes or querying shooting state. | Checks 4, 6 |
| `zoom_status` | `0x00010D74` | `g7x stubs_min.S:15`<br>`stubs_min.S:6` | Zoom status queries execute safely during menu display and live view. | Zoom lever operation while menu is active panics kernel. | Checks 4, 6 |
| `simple_movie_status` | `0x0000C170` | `g7x stubs_entry.S:185`<br>`stubs_min.S:7` | Movie recording state query in `camera_info` executes cleanly. | Memory fault when reading video recording flags. | Checks 3, 4 |
| `canon_shoot_menu_active` | `1` (FAKEDEF) | `g7x stubs_min.S:10`<br>`stubs_min.S:10` | GUI mode dispatcher initializes and manages menu state transitions smoothly. | Mode dispatcher aborts or fails to transition between stock and ALT modes. | Checks 2, 3, 6 |

---

## 5. Failure Symptoms & Diagnostic Guide

| Failure Symptom | Likely Cause (Implicated INFERRED Row) | What to Note & Inspect |
| :--- | :--- | :--- |
| **Upper-screen stripes or garbled raster across menu** | `h1` (`G3X_OSD2_UYVY_*` pixel format or stride 1472 vs 736 mismatch) | Note stripe direction, width, colors, and whether menu text is readable beneath stripes. |
| **Menu or cursor rapidly flickers between frames (~30 Hz)** | `h2` (Active buffer ping-pong tracking out of phase with hardware) | Note if flicker is continuous or only occurs when moving the selection cursor. |
| **Menu flashes briefly then disappears completely** | `h3` / `kbd_driven_gui_redraw` (Stock UI wipes OSD without CHDK redraw) | Check rear LED: note if LED double-blink continues while screen is blank. |
| **Menu text or background has green / magenta tint** | `G3X_OSD2_UYVY_WHITE` (`0xFF80`) / `G3X_OSD2_UYVY_BLACK` (`0x0080`) | Note exact color cast on text, cursor box, and menu background rectangle. |
| **Live view shows through menu box (translucent or invisible)** | `G3X_OSD2_OPACITY_OPAQUE` (`0xFF` opacity byte not written) | Note whether menu text appears floating directly over live view without black backdrop. |
| **Dark rectangle or ghost pixels persist after exiting ALT** | `G3X_OSD2_OPACITY_TRANSPARENT` (`0x00` opacity clearing failure) | Note whether ghost disappears after pressing stock DISP/MENU or persists permanently. |
| **Camera freezes during early boot before stock UI appears** | `G3X_GUI_INIT_FILE_MODULES_SUB` (`0xFC0BB6FE`) or `G3X_GUI_HEAP_START` (`0x00368880`) | Note ladder code reached on power LED, whether lens extends, and card access LED state. |
| **Camera panics / freezes when pressing Playback (ALT entry)** | `kbd_driven_gui_redraw` / `canon_shoot_menu_active` / `G3X_GUI_HEAP_START` | Note if LED begins double-blinking before freeze, or if camera locks immediately. |
| **Camera crashes when navigating D-pad or entering submenu** | `focus_len_table` / `zoom_status` / `levent_table` / `_qsort` / `_malloc` | Note exact menu entry or submenu highlighted when freeze occurred. |
| **Camera shuts down immediately upon releasing Power button** | `G3X_POWERON_HOLD_POLLS` (held power bit logic in `mykbd_task`) | Note if held-press boot still succeeds; record button press duration. |
| **Changed menu settings persist after a complete power cycle** | Config save stub failure (disk write executed instead of RAM-only no-op) | Note which setting persisted and inspect SD card root for newly written `.cfg` files. |

---

## 6. Recovery Procedure & Fallback Candidates

### Strict RAM-Only Guarantee
- The candidate binary (`DISKBOOT.BIN`) is loaded strictly into camera DRAM (`0x003489B4`).
- No flash ROM sectors, bootloaders, or NVRAM parameters are written or altered.
- All persistent configuration writes and file loaders are disabled / stubbed in `G3X_GUI=1`.
- A battery pull completely drains DRAM, returning hardware to its unmodified factory state.
- The default baseline build remains 100% untouched.

### Step-by-Step Battery-Pull Recovery
1. **Pull Battery**: Open the battery door and remove the Canon NB-10L battery pack immediately.
2. **Eject SD Card**: Remove the SD card; unlock the write-protect switch on host to remove or replace `DISKBOOT.BIN`.
3. **Discharge (30 Seconds)**: Leave battery out for at least 30 seconds to allow all power rail capacitors to fully drain.
4. **Stock Verification Boot**: Reinsert battery (with unmodified or blank SD card) and power on normally to verify factory Canon GM1.10C operation.

### Fallback Candidate Hierarchy

| Fallback Level | Candidate Variant | Build Command | Expected `DISKBOOT.BIN` SHA-256 | Fallback Role / Purpose |
| :---: | :--- | :--- | :---: | :--- |
| **Baseline** | Default Flag-Off Build | `python3 -B tools/build_candidate_port25_ladder_fix.py --default --out-dir <dir>` | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | Baseline reference without resident multitasking. |
| **Fallback 1** | PORT-35 Part A (OSD2 Only) | `G3X_OSD2=1 python3 -B tools/build_candidate_port25_ladder_fix.py --osd2 --out-dir <dir>` | `20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57` | Isolates OSD2 double-buffered overlay without core GUI/menu. |
| **Fallback 2** | PORT-34 (KBD + ALT Toggle) | `G3X_KBD=1 python3 -B tools/build_candidate_port25_ladder_fix.py --kbd --out-dir <dir>` | `a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33` | Verifies keyboard hook and ALT LED toggle without OSD drawing. |
| **Fallback 3** | PORT-32 (Resident Heartbeat) | `G3X_RESIDENT=1 python3 -B tools/build_candidate_port25_ladder_fix.py --resident --out-dir <dir>` | `63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a` | Verifies resident task multitasking and power-on ladder fix. |

---

## 7. Owner-Notes Template for Tech Lead

```markdown
# PORT-35 Hardware Trial Owner Notes

- **Date / Time**: YYYY-MM-DD HH:MM UTC
- **Camera Body**: Canon PowerShot G3 X (GM1.10C, Platform ID 0x32A8)
- **Candidate Tested**: G3X_GUI=1 (PORT-35 Part B)
- **Card SHA-256**: 1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272
- **SHA-256 Match Verified**: [ ] YES  [ ] NO (Trial stopped if NO)
- **Total Power-Ons Executed**: [ ] 1  [ ] 2 (Hard limit: max 2)

### Step-by-Step Trial Results
| Check # | Test Description | Expected Result | Observed Result | Pass / Fail |
|:---:|:---|:---|:---|:---:|
| 1 | Held-press boot & heartbeat | Steady ~1.0 Hz single blink; stock UI active | | [ ] PASS  [ ] FAIL |
| 2 | ALT toggle (Playback button) | LED switches to ~1.0 Hz double blink | | [ ] PASS  [ ] FAIL |
| 3 | Menu open & OSD drawing | CHDK Main Menu opens; solid, crisp, no stripes | | [ ] PASS  [ ] FAIL |
| 4 | D-pad nav & SET selection | D-pad moves cursor; SET toggles/enters | | [ ] PASS  [ ] FAIL |
| 5 | Menu close (MENU button) | Menu closes; overlay erased cleanly | | [ ] PASS  [ ] FAIL |
| 6 | ALT exit to stock UI | LED returns to single blink; stock UI active | | [ ] PASS  [ ] FAIL |
| 7 | Short-press boot unchanged | Powers on past ladder on tap (<0.5 s); no cutoff | | [ ] PASS  [ ] FAIL |
| 8 | RAM-only volatility check | Changed setting reverts after power cycle | | [ ] PASS  [ ] FAIL |

### Inferred Address Hypotheses Confirmation
- [ ] `h1` confirmed: Upper-screen stripes eliminated; solid background rendered.
- [ ] `h2` confirmed: Menu remains visible across frames without 30 Hz flicker.
- [ ] `h3` confirmed: Menu persists continuously in ALT mode without stock UI wipe.
- [ ] Color / Opacity confirmed: Neutral white text, neutral black opaque box.
- [ ] RAM-only confirmed: No SD card configuration file written; settings volatile.

### Observations, Glitches, or Anomalies
- Visual quality of menu font and alignment:
- Menu navigation responsiveness:
- Stock UI behavior after exiting ALT:
- Any unhandled exceptions or watchdog resets:

### Overall Verdict & Sign-Off
- [ ] **PASS**: Candidate meets all acceptance criteria. Proceed to PORT-36.
- [ ] **FAIL**: Issues observed (see details above). Revert to fallback.
- **Tech Lead Sign-Off**: ____________________  **Date**: ______________
```
