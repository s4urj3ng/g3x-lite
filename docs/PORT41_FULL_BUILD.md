# PORT-41: Standard CHDK Full Build for PowerShot G3 X (GM1.10C)

## 1. Overview & Architecture

The PORT-41 full build produces the standard CHDK firmware artifacts for the Canon PowerShot G3 X (firmware GM1.10C) in a completely separate, out-of-tree staging pipeline. This architecture ensures strict decoupling from the candidate builder pipeline (PORT-24..40) and preserves bit-identical reproducibility across all existing candidate outputs.

### Key Architectural Invariants
- **Isolated Source Tree**: Full-build source files are tracked under `full_build/g3x/` (platform-level files) and `full_build/g3x/sub/110c/` (firmware-specific sub-platform files).
- **Zero Pollution of Canonical Platform**: The canonical `chdk-port/platform/g3x/` tree is never modified; its files and hashes remain 100% identical to the base branch.
- **Out-of-Tree Staging**: Staging occurs under `out/port41-full/stage_chdk` (gitignored). The build tool copies `chdk-port`, cleans host/target object artifacts, overlays `full_build/g3x` onto `platform/g3x` in staging only, and invokes the standard CHDK build system with pinned cross-compiler `toolchains/gcc-arm-none-eabi-5_4-2016q3`.
- **Output Artifacts**:
  - `out/port41-full/DISKBOOT.BIN` (encoded standard CHDK bootloader, dancingbits format row 13).
  - `out/port41-full/CHDK/` (distribution folder containing `MODULES/` with 34 compiled `.flt` modules, `FONTS/`, and `LANG/`).
  - `out/port41-full/port41_manifest.json` (SHA-256 manifest verifying output integrity).
- **Symbol Namespacing**: All global symbols that could collide with candidate boot/keyboard symbols (e.g. `g3x_saved_start_cause`, `g3x_shortpress_active`) are namespaced (`g3x_full_saved_start_cause`, `g3x_full_shortpress_active`) to prevent duplicate definition collisions.

---

## 2. Table of Adapted Addresses

| Subsystem / Feature | Address / Value | Evidence Label | Provenance / Citation | Description |
|---|---|---|---|---|
| `CreateTask` runtime entry | `0xBFE14A3D` | `VERIFIED` | ROM disassembly / DryOS ATCM | DryOS `CreateTask` entry address in ATCM (Thumb mode). |
| `hook_CreateTask` patch site | `0xBFE14A3C` | `VERIFIED` | ROM disassembly / DryOS ATCM | 8-byte patch site replaced with trampoline to `CreateTask_my`. |
| Post-bootloader ROM handoff | `0xFC0D0126` | `VERIFIED` | ROM disassembly / PORT-24..39 | Subroutine `sub_fc0d0126` handling terminal OS init sequence. |
| Status LED MMIO | `0xD20B0884` | `VERIFIED` | Hardware MMIO / PORT-20,24 | Green power LED register used for diagnostic ladder pulses. |
| Held-press ladder timing | `0x00100000` | `VERIFIED` | PORT-24 ladder timing | Calibrated loop delay count for power button hold detection. |
| Power-cut bypass subroutine | `0xFC05B962` | `VERIFIED` | ROM disassembly / PORT-24,39 | Subroutine `sub_fc05b962` hooked to bypass shutdown `sub_fc05ba56`. |
| Start cause register | `0x00009BD0` | `VERIFIED` | DryOS RAM / PORT-24,39 | Memory location storing DryOS startup reason flags. |
| Shooting mode start cause | `0x00080000` | `VERIFIED` | DryOS RAM / PORT-24,39 | Start cause value restored on Power press to enforce shooting mode. |
| `physw_status` array | `0x00040DAC` | `VERIFIED` | DryOS RAM / FINSIG / PORT-34 | Physical switch status word array read by `my_kbd_read_keys()`. |
| Power key bit | Bit 17 (`0x00020000`) | `VERIFIED` | PORT-34,39 | Bit index in `physw_status[0]`. |
| Playback key bit | Bit 16 (`0x00010000`) | `VERIFIED` | PORT-34,39 | Bit index in `physw_status[0]`. |
| Physw sleep delay | `10` ms | `VERIFIED` | Sibling `g7x`/`g5x` baseline | Sleep duration per iteration of `mykbd_task`. |
| Display Type | Mode `12` | `VERIFIED` | PORT-33,35,40 | DryOS Mode 12 (900x600 UYVY panel). |
| Screen dimensions | 900 x 600 | `VERIFIED` | PORT-33,35,40 | Physical panel resolution. |
| Bitmap buffer width | 928 | `VERIFIED` | PORT-33,35,40 | Bitmap buffer pitch / stride. |
| Active bitmap buffer pointer | `0x0000D2A4` | `VERIFIED` | DryOS RAM / FINSIG (stubs_entry.S:190) | Pointer holding active bitmap index (`active_bitmap_buffer & 1`). |
| Opacity buffers | `{0x5FC40000, 0x5FB80000}` | `VERIFIED` | MMIO / PORT-33,35,40 | Dual opacity buffer memory addresses. |
| GUI5 OSD geometry | `(10, 12, 880, 576)` | `VERIFIED` | `docs/PORT40_GUI_LAYOUT.md` | Centered 880x576 OSD box with 10/12 px margins and 32 px rows. |
| Loader D-cache clean & invalidate | `0xFC127AB1` | `VERIFIED` | ROM disassembly / PORT-1F2 / PORT-24..39 / `docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119` | Cleans & invalidates L1 Data Cache (DCCISW all sets/ways) to PoC after core relocation. Replaces monolithic `0xFC418723`. |
| Loader I-cache / BP invalidate | `0xFC127B09` | `VERIFIED` | ROM disassembly / PORT-1F2 / PORT-24..39 / `docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119` | Invalidates entire L1 Instruction Cache (ICIALLU) and branch predictors (BPIALL) followed by `dsb sy` and `isb sy`. |
| Loader handoff sequence | `0xFC127AB1` -> `dsb` -> `0xFC127B09` -> `dsb` -> `isb` -> `cpsid if` -> `bx r0` | `VERIFIED` | `chdk-port/loader/g3x/main_prototype.c:19-95` (PORT-1F2 / PORT-24..39) | Decoupled cache maintenance sequence in canonical ARMv7 order. `0xFC418723` is NOT called in loader. |
| CHDK heap allocator / ARAM exclusion | Canon heap (`canon_malloc`) | `VERIFIED` | ROM disassembly / `docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78` | AdditionAgent reserves `0x006CE000..0x006F0000` for file-read scratch. `OPT_ARAM_MALLOC` unset; CHDK delegates to Canon allocator. |

---

## 2.1 Remediations & Architectural Decisions (P1 Reviews)

### 1. Loader Cache-Maintenance Sequence Remediated (P1 Fix 1)
- **Problem**: Monolithic ROM subroutine `0xFC418723` (`0xFC418722`) was originally derived from sibling loaders (`g7x` / `g5x`). However, disassembly shows that `0xFC418722` invalidates the instruction cache (`0xFC127B08`) *before* cleaning the data cache (`0xFC127AB0`), as verified in `docs/CHDK_PORT1D1_MPU_CACHE_VERIFICATION.md:124-134`. Relocating executable code requires the reverse order (`docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119`).
- **Remediation**: Replaced `0xFC418723` with the established decoupled handoff sequence from `chdk-port/loader/g3x/main_prototype.c:69-95` (PORT-1F2 / PORT-24..39):
  1. `core_copy(src, dst, length)`: relocates core to `MEMISOSTART` (`0x003489B4`).
  2. Call `0xFC127AB1` (`blx r2`): DCCISW (clean and invalidate D-cache to PoC).
  3. `dsb sy`: serialize memory completion.
  4. Call `0xFC127B09` (`blx r2`): ICIALLU + BPIALL (invalidate I-cache and branch predictor).
  5. `dsb sy; isb sy`: synchronize pipeline.
  6. `cpsid if`: enforce disabled interrupt state.
  7. `bx r0`: branch to Thumb core entry (`0x003489B5`).
- `0xFC418723` is **not** called in the loader, verified by static checks and ELF disassembly tests in `tests/test_port41_full_build.py`.

### 2. ARAM Pool Collision Avoidance (P1 Fix 2)
- **Problem**: `full_build/g3x/sub/110c/makefile.inc` previously defined `ARAM_HEAP_START=0x006ce000` and `ARAM_HEAP_SIZE=0x00022000` with `OPT_ARAM_MALLOC=1`. As proven in `docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78`, `0x006CE000..0x006F0000` is actively owned by Canon's `AdditionAgent.c` (`0xFC558866..0xFC5588C0`) as a file I/O scratch buffer. Allocating CHDK's heap there would result in memory corruption during `AdditionAgent` file reads.
- **Remediation**:
  1. Removed `OPT_ARAM_MALLOC`, `ARAM_HEAP_START`, and `ARAM_HEAP_SIZE` from `full_build/g3x/sub/110c/makefile.inc`.
  2. Explicitly unset `override OPT_ARAM_MALLOC=` and `override OPT_CHDK_IN_ARAM=` so CHDK core delegates all dynamic memory allocations to Canon's allocator (`canon_malloc` via DryOS).
  3. Staged build configuration and core binary analysis verify that no CHDK heap falls in `0x006CE000..0x006F0000`.

---

## 3. Disabled-Hook TODOs

Per safety policy and Phase 0 guidelines, hooks that are not verified by FINSIG or proven by disassembly records are left stock (delegating directly to DryOS tasks) with clear TODO markers:

1. **`task_CaptSeq`** (`full_build/g3x/sub/110c/capt_seq.c`):
   - *Status*: Disabled (bypassed). Directly branches to stock DryOS `task_CaptSeq`.
   - *TODO*: Reverse and confirm GM1.10C raw develop and capture sequence hook points (`capt_seq_hook_raw_here`, `exp_drv_task`) before enabling CHDK raw capture overrides.
2. **`task_MovieRecord`** (`full_build/g3x/sub/110c/movie_rec.c`):
   - *Status*: Disabled (bypassed). Directly branches to stock DryOS `task_MovieRecord`.
   - *TODO*: Reverse and confirm movie recording task hooks and video bitrate tables before enabling CHDK video parameter overrides.
3. **`task_FileWrite`** (`full_build/g3x/sub/110c/filewrite.c`):
   - *Status*: Disabled (bypassed). Directly branches to stock DryOS `task_FileWrite`.
   - *TODO*: Reverse and confirm asynchronous file write hooks before enabling CHDK background file shelter or DNG write tasks.

---

## 4. Card-Write Suppression Switches

Phase 0 strictly forbids modifying camera flash or writing files to SD storage at runtime. To ensure safety, all card write paths are suppressed using compile-time flags and linker symbol wrapping:

### Linker `--wrap` Directives (`full_build/g3x/sub/110c/Makefile`)
- File creation & write: `-Wl,--wrap=open -Wl,--wrap=fopen -Wl,--wrap=creat -Wl,--wrap=write -Wl,--wrap=fwrite`
- Directory management: `-Wl,--wrap=mkdir -Wl,--wrap=MakeDirectory_Fut -Wl,--wrap=_MakeDirectory_Fut`
- File deletion & rename: `-Wl,--wrap=remove -Wl,--wrap=DeleteFile_Fut -Wl,--wrap=_DeleteFile_Fut -Wl,--wrap=DeleteDirectory_Fut -Wl,--wrap=_DeleteDirectory_Fut -Wl,--wrap=rename -Wl,--wrap=RenameFile_Fut -Wl,--wrap=_RenameFile_Fut`
- CHDK configuration & parameters: `-Wl,--wrap=conf_save -Wl,--wrap=save_params_values -Wl,--wrap=save_int_value_file`

### Compile Preprocessor Flags
- `-DG3X_DISABLE_CARD_WRITES=1`: Disables internal CHDK disk writing functions.
- `-DOPT_DISABLE_FILE_WRITES=1`: Suppresses file write operations across core modules.
- `-UOPT_FILEIO_STATS`: Disables file I/O statistics recording.

### Wrapper Behavior (`full_build/g3x/lib.c`)
- Calls to `__wrap_open()` and `__wrap_fopen()` check requested flags and access modes. Read-only modes (`O_RDONLY`, `"r"`, `"rb"`) pass through to `__real_open()` and `__real_fopen()`, enabling CHDK to read scripts, modules, fonts, and language files.
- Any write, append, truncate, or create flag (`O_WRONLY`, `O_RDWR`, `O_CREAT`, `O_APPEND`, `"w"`, `"a"`, `"+"`) immediately returns an error (`-1` or `NULL`) without invoking the underlying OS file write routines.
- Mutation functions (`mkdir`, `remove`, `rename`) immediately return success/no-op without performing any I/O.

---

## 5. How to Run the Build

### Standard CHDK Full Build
Run the Python build entry point:
```bash
python3 -B tools/build_port41_full.py
```
Or use the shell wrapper:
```bash
./tools/build_port41_full.sh
```

### Verification & Automated Tests
Execute the comprehensive PORT-41 test suite:
```bash
python3 -B -m unittest tests/test_port41_full_build.py
```

### Clean Verification Suite Run
Ensure all existing validation suites pass:
```bash
python3 -B tools/bootstrap_chdk_platform.py --verify-only
python3 -B tools/build_candidate_port2a.py
python3 -B tools/validate_candidate_port2a.py
python3 -B -m unittest discover -s tests -p "test_port*.py"
```

---

## 6. Output Artifacts Manifest & Owner Trial Plan

### 6.1 Output Artifacts Manifest

The standard CHDK full build emits the following complete runtime distribution artifacts under `out/port41-full/`:

| Artifact | Type | Size (Bytes) | SHA-256 Checksum | Description |
|---|---|---|---|---|
| `DISKBOOT.BIN` | Encoded Bootloader | `124,097` | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | Full CHDK executable binary, encoded with dancingbits row 13. |
| `CHDK/MODULES/` | Directory (34 modules) | — | (See `port41_manifest.json`) | Dynamic runtime modules (`.flt` format): `calend.flt`, `mdetect.flt`, `cpuinfo.flt`, `mpopup.flt`, `tetris.flt`, `fshelter.flt`, `exmemins.flt`, `sudoku.flt`, `_osd_le.flt`, `curves.flt`, `reversi.flt`, `memview.flt`, `palette.flt`, `_hexbox.flt`, `_rawop.flt`, `ubasic.flt`, `eyefi.flt`, `shothist.flt`, `modinsp.flt`, `lua.flt`, `_tbox.flt`, `zebra.flt`, `snake.flt`, `benchm.flt`, `txtread.flt`, `edgeovr.flt`, `grids.flt`, `useredit.flt`, `4wins.flt`, `fselect.flt`, `histo.flt`, `_dng.flt`, `sokoban.flt`, `mastmind.flt`. |
| `CHDK/FONTS/` | Directory (74 fonts) | — | — | Standard CHDK RBF raster fonts (`.rbf` format) for 16x32 and alternate UI scales. |
| `CHDK/LANG/` | Directory (20 languages) | — | — | Localization language definition files (`.lng` format). |
| `CHDK/SCRIPTS/` | Directory | — | — | Default CHDK Lua and uBasic script suite (`shoot.lua`, `interval.lua`, `default.lua`, etc.). |
| `port41_manifest.json` | JSON Manifest | — | — | Cryptographic integrity manifest verifying all output files and hashes. |

### 6.2 Owner Trial Steps Table

The owner trial validates the full build on physical camera hardware in two consecutive steps: **held press first**, followed by **short press**.

| Step | Action | Expected Result | What to Note |
|---|---|---|---|
| **Step 1: Held Press** | Insert SD card with `DISKBOOT.BIN` and `CHDK/`. Press and **hold** the Power button for >= 1.5 seconds until LED activity completes. | 1. **LED ladder**: Diagnostic LED ladder flashes on green power LED (`0xD20B0884`).<br>2. **Stock UI**: Firmware enters normal DryOS initialization and renders the stock Canon display.<br>3. **CHDK resident**: CHDK background keyboard task (`mykbd_task`) is resident in memory without crashes or watchdogs.<br>4. **ALT toggle opens standard CHDK menu**: Pressing the WiFi button (default ALT key on fresh config from `CAM_ALT_BUTTON_OPTIONS`; Playback can be selected in CHDK Settings -> Miscellaneous -> ALT Button) toggles ALT mode; pressing Menu opens the full 900x600 CHDK menu cleanly without edge leaks or visual artifacts. | - Observe green LED pulse sequence during loader handoff.<br>- Verify LCD display boots to stock live view.<br>- Confirm WiFi key enters `<ALT>` mode cleanly (WiFi is the fresh-config ALT default; Playback can be configured in CHDK Settings).<br>- Confirm Menu key displays standard CHDK menu centered in 880x576 box with 10 px horizontal and 12 px vertical margins.<br>- Pressing WiFi exits `<ALT>` mode and returns to normal operation. |
| **Step 2: Short Press** | With camera powered off, perform a normal **short press** (< 0.5 s) of the Power button. | 1. **Shooting mode on short press**: The camera powers up directly into shooting mode (lens extends, sensor activates, live view starts) because start cause `0x00080000` is restored and the power-cut shutdown in `sub_fc05b962` is bypassed.<br>2. **CHDK resident**: Background kbd driver and CHDK core remain fully resident.<br>3. **Normal power-off**: A later Power press turns it off cleanly. | - Note that the short press does not drop power or shut down prematurely.<br>- Observe lens extension and live viewfinder display.<br>- Verify ALT mode toggle (WiFi button, or Playback if selected) remains functional.<br>- Press Power button to verify that a later Power press turns it off cleanly. |

### 6.3 Recovery Path (RAM-Only & Battery Pull)

The PORT-41 full build strictly follows Phase 0 safety invariants:
- **Suppressed Card / File Writes**: Linker `--wrap` flags (`--wrap=open`, `--wrap=fopen`, `--wrap=creat`, `--wrap=write`, `--wrap=fwrite`) and compile directives (`-DG3X_DISABLE_CARD_WRITES=1`, `-DOPT_DISABLE_FILE_WRITES=1`) suppress SD card writes, configuration file saves, and filesystem modifications.
- **RAM-Only Execution**: The entire CHDK core and heap reside strictly in volatile SDRAM (`MEMISOSTART` at `0x003489B4`). Execution is RAM-only and does not persist across reboots or modify camera flash ROM.
- **Recovery Procedure (Battery Pull & Card Removal)**:
  1. Open the battery compartment door and remove the Canon NB-10L battery.
  2. Remove the CHDK SD card (or make it non-bootable by sliding the SD write-protect switch to UNLOCKED or removing `DISKBOOT.BIN`) before restarting, preventing `DISKBOOT.BIN` from reloading automatically.
  3. Leave the battery out for >= 10 seconds (or 30 seconds for complete capacitor discharge) to ensure complete discharge of all power supply rail capacitors and volatile SDRAM retention.
  4. Re-insert the battery.
  5. Turn on the camera normally: the camera boots stock Canon factory firmware.

