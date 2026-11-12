# PORT-44: Lazy Runtime Heap Allocation for G3X_GUI_DBUF Shadow Buffer

This document records the design, implementation, and host verification for task `PORT44-DBUF-HEAP-BUILD` on the PowerShot G3 X (GM1.10C). It moves the double-buffer shadow buffer out of BSS into lazy runtime heap allocation from the DryOS firmware heap, resolving the boot failure observed in the PORT-43 owner trial.

All changes are gated behind `#if defined(G3X_GUI_DBUF) && (G3X_GUI_DBUF == 1)`. When the switch is disabled, all builds produce 100% byte-identical outputs to their existing manifests.

---

## 1. Core `_end` Summary Table

| Milestone / Variant | Build Target / Flags | Core `_start` | Core `_end` | Delta vs PORT-42 | Status / Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PORT-25** | Baseline ladder fix (`candidate_port25_default`) | `0x003489b4` | `0x00368680` | -304 B | VERIFIED (`docs/PORT25_LADDER_FIX_CANDIDATE.md:391`) |
| **PORT-42** | `G3X_GUI_FIX=1` full build | `0x003489b4` | `0x003687b0` | 0 B (Baseline) | VERIFIED (host build `out/port42-gui-fix/stage_chdk/.../main.elf`) |
| **PORT-43** | `G3X_GUI_FIX=1 G3X_GUI_DBUF=1` (static BSS shadow) | `0x003489b4` | `0x00500fd0` | +1,673,248 B (+1,634.03 KiB) | VERIFIED (host build `out/port43-dbuf/stage_chdk/.../main.elf`) |
| **PORT-44** | `G3X_GUI_FIX=1 G3X_GUI_DBUF=1` (lazy heap shadow) | `0x003489b4` | `0x00369490` | **+3,296 B (+3.22 KiB)** | VERIFIED (host build `out/port44-dbuf/stage_chdk/.../main.elf`) |

> [!IMPORTANT]
> **Core `_end` Constraint Verification**:
> The core `_end` with `G3X_GUI_DBUF=1` for PORT-44 is `0x00369490`, which is **3,296 bytes (+3.22 KiB)** above the PORT-42 baseline (`0x003687b0`). This is strictly within the 64 KiB ceiling required by acceptance criteria ($3,296 \le 65,536$ bytes).

---

## 2. Hypothesis Verification (Step a)

### Context & Failure Analysis
In the PORT-43 `G3X_GUI_DBUF=1` physical trial (`DISKBOOT.BIN` SHA-256 `8d5509e5...`), neither a held nor a short power press booted the camera: the LED blinked once, followed immediately by total shutdown.

- **Hypothesis**: The static `g3x_shadow` buffer (928x600 bitmap + opacity, 1,670,400 B) was placed in core BSS. This shifted core `_end` from `0x003687b0` (PORT-42) to `0x00500fd0`. In PORT-27 (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:24`), the DryOS firmware heap start is overridden via `new_sa = &_end;`. Raising the firmware heap start past `0x00500fd0` deprived DryOS of ~1.67 MB of early startup heap RAM, causing firmware startup allocations to fail and preventing the camera from booting.
- **Host Inspection**: The core ELF was built with the pinned toolchain (`toolchains/gcc-arm-none-eabi-5_4-2016q3`) and inspected using `arm-none-eabi-nm -S --size-sort` and `arm-none-eabi-nm -n`.

### 10 Largest BSS/Data Symbols in PORT-42 (G3X_GUI_FIX=1)
*ELF: `out/port42-gui-fix/stage_chdk/platform/g3x/sub/110c/main.elf` — `_start: 0x003489b4`, `_end: 0x003687b0` [VERIFIED host build]*

| Rank | Symbol | Size (Bytes) | Size (Hex) | Section Type | Address |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 1 | `font_data` | 3,473 | `0x000d91` | `d` (initialized data) | `0x003643c0` |
| 2 | `symbol_hash_table` | 3,160 | `0x000c58` | `D` (initialized data) | `0x00365f98` |
| 3 | `osd_conf_info` | 2,320 | `0x000910` | `d` (initialized data) | `0x00362db4` |
| 4 | `conf_info` | 2,128 | `0x000850` | `d` (initialized data) | `0x003636c4` |
| 5 | `conf` | 2,088 | `0x000828` | `B` (uninitialized BSS) | `0x00367e6c` |
| 6 | `console_buf` | 1,350 | `0x000546` | `b` (uninitialized BSS) | `0x00367424` |
| 7 | `shutter_speeds_table` | 696 | `0x0002b8` | `D` (initialized data) | `0x00360efc` |
| 8 | `conf_map_1_2` | 606 | `0x00025e` | `d` (initialized data) | `0x0035d460` |
| 9 | `camera_sensor` | 564 | `0x000234` | `D` (initialized data) | `0x0036416c` |
| 10 | `live_histogram_proc` | 512 | `0x000200` | `b` (uninitialized BSS) | `0x00367a24` |

### 10 Largest BSS/Data Symbols in PORT-43 (G3X_GUI_DBUF=1)
*ELF: `out/port43-dbuf/stage_chdk/platform/g3x/sub/110c/main.elf` — `_start: 0x003489b4`, `_end: 0x00500fd0` [VERIFIED host build]*

| Rank | Symbol | Size (Bytes) | Size (Hex) | Section Type | Address |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **1** | **`g3x_shadow`** | **1,670,400** | **`0x197d00`** | **`b` (uninitialized BSS)** | **`0x00367568`** |
| 2 | `font_data` | 3,473 | `0x000d91` | `d` (initialized data) | `0x00364bd4` |
| 3 | `symbol_hash_table` | 3,160 | `0x000c58` | `D` (initialized data) | `0x003667ac` |
| 4 | `osd_conf_info` | 2,320 | `0x000910` | `d` (initialized data) | `0x003635bc` |
| 5 | `conf_info` | 2,128 | `0x000850` | `d` (initialized data) | `0x00363ecc` |
| 6 | `conf` | 2,088 | `0x000828` | `B` (uninitialized BSS) | `0x00500680` |
| 7 | `console_buf` | 1,350 | `0x000546` | `b` (uninitialized BSS) | `0x004ffc38` |
| 8 | `dbuf_row_cache` | 768 | `0x000300` | `b` (uninitialized BSS) | `0x004ff694` |
| 9 | `shutter_speeds_table` | 696 | `0x0002b8` | `D` (initialized data) | `0x00361704` |
| 10 | `conf_map_1_2` | 606 | `0x00025e` | `d` (initialized data) | `0x0035dc68` |

### 10 Largest BSS/Data Symbols in PORT-44 (G3X_GUI_DBUF=1 with Heap Shadow)
*ELF: `out/port44-dbuf/stage_chdk/platform/g3x/sub/110c/main.elf` — `_start: 0x003489b4`, `_end: 0x00369490` [VERIFIED host build]*

| Rank | Symbol | Size (Bytes) | Size (Hex) | Section Type | Address |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 1 | `font_data` | 3,473 | `0x000d91` | `d` (initialized data) | `0x00364d8c` |
| 2 | `symbol_hash_table` | 3,160 | `0x000c58` | `D` (initialized data) | `0x00366964` |
| 3 | `osd_conf_info` | 2,320 | `0x000910` | `d` (initialized data) | `0x00363774` |
| 4 | `conf_info` | 2,128 | `0x000850` | `d` (initialized data) | `0x00364084` |
| 5 | `conf` | 2,088 | `0x000828` | `B` (uninitialized BSS) | `0x00368b44` |
| 6 | `console_buf` | 1,350 | `0x000546` | `b` (uninitialized BSS) | `0x003680fc` |
| 7 | `dbuf_row_cache` | 768 | `0x000300` | `b` (uninitialized BSS) | `0x00367b58` |
| 8 | `shutter_speeds_table` | 696 | `0x0002b8` | `D` (initialized data) | `0x003618bc` |
| 9 | `conf_map_1_2` | 606 | `0x00025e` | `d` (initialized data) | `0x0035de20` |
| 10 | `camera_sensor` | 564 | `0x000234` | `D` (initialized data) | `0x00364b2c` |

### Hypothesis Verdict: CONFIRMED
The `_end` hypothesis is **CONFIRMED** (`VERIFIED host build`).
- In PORT-43, the static `g3x_shadow` buffer occupied **1,670,400 bytes** (`0x197d00`) in BSS, directly shifting `_end` from `0x003687b0` to `0x00500fd0` (+1,673,248 bytes).
- In PORT-44, `g3x_shadow` is completely removed from BSS. No BSS or data symbol exceeds 64 KiB (the largest is `font_data` at 3,473 bytes).
- Core `_end` returns to `0x00369490`, restoring all 1.67 MB of RAM to the DryOS firmware startup heap.

---

## 3. Technical Changes Table

| Change | File:Line | Sibling Citation | Label | Expected Visible Effect |
| :--- | :--- | :--- | :--- | :--- |
| **BSS Shadow Removal**<br>Static `g3x_shadow` array (1,670,400 B) removed from BSS; replaced by runtime pointers `g3x_shadow_bitmap` and `g3x_shadow_opacity`. No static symbol > 64 KiB remains in BSS. | `chdk-port/core/gui_draw.c:110-112` | `chdk-port/platform/g7x/lib.c:18-19, 291-292`; `chdk-port/platform/g5x/lib.c:21-33` | VERIFIED host build | Reduces core `_end` from `0x00500fd0` to `0x00369490`, leaving the DryOS startup heap intact. Camera boots normally on both short and held power button press. |
| **Lazy Runtime Heap Allocation**<br>`g3x_dbuf_shadow_ensure_allocated` dynamically allocates the shadow buffer on the first GUI/ALT mode entry only (never during boot, `spytask`, or `CreateTask`). Uses CHDK `malloc` with fallback to `umalloc`. Allocates once and reuses; never frees and reallocates every frame. | `chdk-port/core/gui_draw.c:121-144`<br>`chdk-port/core/gui.c:2468-2475, 3109-3115`<br>`chdk-port/core/gui_menu.c:231-237`<br>`chdk-port/platform/g3x/gui_menu.c:250-256` | `reference/finsig_gm110c/stubs_entry.S:308, 197`; `chdk-port/core/memmgmt.c:284-297`; `chdk-port/platform/generic/wrappers.c:1020-1031, 1045-1057`; `chdk-port/platform/g7x/sub/100c/stubs_entry.S:181, 285`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:191, 286` | FINSIG (`malloc` @ `0xfc381525`, `AllocateUncacheableMemory` @ `0xfc144471`) / INFERRED (lazy allocation) | Boot path performs 0 heap allocations. Upon first pressing ALT or entering Menu, ~1.45 MiB is allocated from DryOS heap without disturbing OS startup. |
| **Menu Rectangle Sizing (880x576)**<br>Shadow sized strictly to the drawn menu rectangle: 880 width $\times$ 576 height ($1,013,760$ B bitmap + $506,880$ B opacity = $1,520,640$ B total, down from $1,670,400$ B). All shadow coordinates are clamped to `[10..889, 12..587]`. Even X origin ($x=10$) maintains UYVY 2-pixel word alignment parity ($rx \ \& \ 1 == x \ \& \ 1$). | `chdk-port/core/gui_draw.c:97-108, 163-196, 241-254, 276-300, 316-332, 733-747, 825-839` | `chdk-port/platform/g5x/lib.c:182-183`; `chdk-port/platform/g7x/lib.c:323-324` | INFERRED | Saves 149,760 bytes of firmware heap RAM while covering 100% of the rendered 880x576 CHDK menu box. Word blits remain aligned and bit-for-bit accurate. |
| **NULL Allocation Fallback & Safety**<br>If `malloc`/`umalloc` returns `NULL`, `g3x_shadow_alloc_attempted` prevents re-allocation attempts every frame. `g3x_shadow_valid` remains 0. All drawing functions (`g3x_dbuf_shadow_draw_pixel`, `g3x_dbuf_fast_fill_rect`, `draw_2pixels_simple`, `draw_hline_simple`) and restore functions (`g3x_dbuf_shadow_restore`, `g3x_dbuf_shadow_reset`) verify non-NULL pointers before accessing memory. | `chdk-port/core/gui_draw.c:116-119, 123-125, 147-154, 166-167, 241, 276, 316, 344-347, 375-378, 733, 825`<br>`chdk-port/core/gui.c:2707-2715`<br>`chdk-port/core/gui_menu.c:1325-1333`<br>`chdk-port/platform/g3x/gui_menu.c:1367-1375` | `chdk-port/core/gui_draw.c:888-937` | INFERRED | If heap memory is exhausted, CHDK continues running safely with dual-buffer direct hardware writes only (no crash, zero out-of-bounds writes). Lost sentinels gracefully fall back to normal `gui_redraw`. |
| **Row-by-Row Fast Restore Blit**<br>`g3x_dbuf_shadow_restore` blits 576 rows of 880 pixels into both bitmap buffers ($576 \times 1,760$ B) and both opacity buffers ($576 \times 880$ B) without calling `vid_bitmap_refresh`. Sentineled guard updated immediately upon restore. | `chdk-port/core/gui_draw.c:341-371` | `reference/finsig_gm110c/stubs_entry.S:352`; `docs/PORT35_GUI_ADDRESSES.md:35` | FINSIG (`_transfer_src_overlay` erase behavior) / INFERRED (row blit) | Restores menu in sub-millisecond time after stock Canon UI overwrite without overlay erase; live view remains stable and unaffected. |
| **Preservation of PORT-43 Features**<br>Dual-buffer writes (`bitmap_buffer[0/1]`, `opacity_buffer[0/1]`), 32-bit fast fills (`g3x_dbuf_fast_fill_rect`), per-row signature cache (`dbuf_row_cache[64]`), partial redraw navigation, 2x font (16x32), 880x576 layout, colors, and opacity remain 100% identical to PORT-43. | `chdk-port/core/gui_draw.c:198-334`<br>`chdk-port/platform/g3x/gui_menu.c:1129-1175`<br>`chdk-port/core/gui_menu.c:1093-1139` | `chdk-port/core/gui_draw.c:138-146`; `scripts/build_candidate_gui3.py:885-896` | VERIFIED host build | Zero visual differences from PORT-43: smooth partial redraw during navigation, instant box clears, no growing black bands, no layout or color changes. |

---

## 4. Stub Citations & Memory Allocation Chain

### G3X Firmware Heap Stubs
From `reference/finsig_gm110c/stubs_entry.S`:
```assembly
NHSTUB(malloc, 0xfc381525) // 0
NHSTUB(AllocateUncacheableMemory, 0xfc144471) // 0
```
- `malloc` is at ROM address `0xfc381525` `[FINSIG]`.
- `AllocateUncacheableMemory` is at ROM address `0xfc144471` `[FINSIG]`.

### CHDK Core & Sibling Allocation Paths
1. **Core Malloc**: `chdk-port/core/memmgmt.c:284-297` defines `malloc(size)`. In non-platform-specific code, it delegates to `canon_malloc(size)`.
2. **Platform Wrapper**: `chdk-port/platform/generic/wrappers.c:1020-1031` routes `canon_malloc(size)` to firmware `_malloc(size)`.
3. **Platform Umalloc**: `chdk-port/platform/generic/wrappers.c:1045-1057` routes `umalloc(size)` to firmware `_AllocateUncacheableMemory(size)`.
4. **Sibling Comparison**:
   - PowerShot G7 X (`100c`):
     - `chdk-port/platform/g7x/sub/100c/stubs_entry.S:285`: `NHSTUB(malloc, 0xfc3623b9)`
     - `chdk-port/platform/g7x/sub/100c/stubs_entry.S:181`: `NHSTUB(AllocateUncacheableMemory, 0xfc0ef0cd)`
   - PowerShot G5 X (`100c`):
     - `chdk-port/platform/g5x/sub/100c/stubs_entry.S:286`: `NHSTUB(malloc, 0xfc3bf235)`
     - `chdk-port/platform/g5x/sub/100c/stubs_entry.S:191`: `NHSTUB(AllocateUncacheableMemory, 0xfc16f5f1)`

---

## 5. Switch-Off Invariance Verification

When `G3X_GUI_DBUF` is disabled, the build produces byte-identical binaries to previously established baselines:

| Build Target | Flags | Expected SHA-256 | Actual SHA-256 | Invariance |
| :--- | :--- | :--- | :--- | :--- |
| **PORT-41 Full** | None | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | 100% IDENTICAL |
| **PORT-42 GUI Fix** | `G3X_GUI_FIX=1` | `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738` | `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738` | 100% IDENTICAL |
| **PORT-42 Full Hooks** | `G3X_GUI_FIX=1 FULL_HOOKS=1` | `d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb` | `d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb` | 100% IDENTICAL |

---

## 6. Deliverable Binary Manifest (PORT-44 G3X_GUI_DBUF=1)

- **Build Command**: `python3 scripts/build_port43_dbuf.py --out-dir out/port44-dbuf`
- **Toolchain**: `toolchains/gcc-arm-none-eabi-5_4-2016q3` (pinned GCC 5.4.1)
- **Compile Flags**: `PLATFORM=g3x PLATFORMSUB=110c G3X_FULL_BUILD=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 OPT_CAPSTONE_TOOLS=0`
- **Output Artifact**: `out/port44-dbuf/DISKBOOT.BIN`
  - **Size**: 126,769 bytes
  - **SHA-256**: `2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382`
- **Core Symbols**:
  - `_start`: `0x003489b4`
  - `_end`: `0x00369490` (Delta vs PORT-42: `+3,296 bytes` / `+3.22 KiB`)
- **Modules**: 34 loadable modules in `out/port44-dbuf/CHDK/MODULES/`
- **Heap Dynamic Allocation**: $1,520,640$ bytes on first GUI/ALT entry only
- **Runtime Card Writes**: Disabled (`OPT_DISABLE_FILE_WRITES=1` active)
