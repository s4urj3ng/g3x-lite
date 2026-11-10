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
| Active bitmap buffer pointer | `0x0002A548` | `VERIFIED` | DryOS RAM / FINSIG | Pointer holding active bitmap index (`active_bitmap_buffer & 1`). |
| Opacity buffers | `{0x5FC40000, 0x5FB80000}` | `VERIFIED` | MMIO / PORT-33,35,40 | Dual opacity buffer memory addresses. |
| GUI5 OSD geometry | `(10, 12, 880, 576)` | `VERIFIED` | `docs/PORT40_GUI_LAYOUT.md` | Centered 880x576 OSD box with 10/12 px margins and 32 px rows. |

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
