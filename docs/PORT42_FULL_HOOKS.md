# PORT-42: FULL_HOOKS=1 Full CHDK Build with FINSIG-Confirmed Hooks

## 1. Overview

The `FULL_HOOKS=1` opt-in switch enables CHDK task hooks for the standard full CHDK build (`PLATFORM=g3x PLATFORMSUB=110c`, toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3`) where target task addresses are confirmed in `reference/finsig_gm110c/stubs_entry.S` (with zero uncertainty) or established in existing `VERIFIED` records.

- **Stock / Disabled Hooks**: Hooks requiring unverified internal addresses (`INFERRED-only`) remain stock and on the TODO list.
- **Card-Write Invariants**: CHDK runtime card writes remain strictly suppressed (`-DG3X_DISABLE_CARD_WRITES=1`, `-DOPT_DISABLE_FILE_WRITES=1`, linker `--wrap` options unchanged from PORT-41).
- **Candidate Invariance**: All candidate builds (PORT-24..40) remain bit-identical.
- **Switch Off Invariance**: Without `FULL_HOOKS=1`, the full build produces the standard PORT-41 distribution.
- **ROM Slices**: Zero ROM slices were read (`0` bytes) as all hook addresses are confirmed in `reference/finsig_gm110c/stubs_entry.S`.

---

## 2. Hook Evaluation Table

| Hook | Address(es) | Label | Sibling Citation | Enabled (yes/no) | Notes / Reason Left Disabled |
|---|---|---|---|---|---|
| `task_PhySw` | `0xFC1283AD` | `FINSIG` / `VERIFIED` | `chdk-port/platform/g7x/sub/100d/boot.c:16-25, 400` | yes | Intercepted in `CreateTask_my`; expands stack to 0x2000 and branches to `mykbd_task`. |
| `task_InitFileModules` | `0xFC0BD071` | `FINSIG` / `VERIFIED` | `chdk-port/platform/g7x/sub/100d/boot.c:140-144, 410-434` | yes | Intercepted in `CreateTask_my`; signals `core_spytask_can_start()` with `r1=1` completion argument. |
| `task_CaptSeq` | `0xFC06A001` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:103-108`<br>`chdk-port/platform/g7x/sub/100d/capt_seq.c:63-65` | yes | Intercepted in `CreateTask_my` via `capt_seq_task`; safe pass-through trampoline to stock DryOS entry (internal raw develop hooks unverified/INFERRED-only). |
| `task_FileWrite` | `0xFC25F3A7` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:126-131`<br>`chdk-port/platform/g7x/sub/100d/filewrite.c:110-115` | yes | Intercepted in `CreateTask_my` via `filewritetask`; safe pass-through trampoline to stock DryOS entry (async card write hooks suppressed and unverified/INFERRED-only). |
| `task_MovieRecord` | `0xFC09AC19` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:134-138`<br>`chdk-port/platform/g5x/sub/100c/boot.c:139-144` | no | Disabled across sibling DIGIC 6 ports; movie recording task hooks and video bitrate tables are unverified (INFERRED-only). |
| `task_ExpDrv` | `0xFC2C136F` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:111-116`<br>`chdk-port/platform/g5x/sub/100c/boot.c:121-125` | no | Disabled in sibling g7x; internal exposure control state machine and calibration tables are unverified (INFERRED-only). |
| `task_DvlpSeqTask` | `0xFC07B637` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:118-123`<br>`chdk-port/platform/g5x/sub/100c/boot.c:127-132` | no | Disabled across DIGIC 6 siblings; raw develop sequence internal addresses are unverified (INFERRED-only). |
| `task_TricInitTask` | `0xFC4E4B19` | `FINSIG` | `chdk-port/platform/g5x/sub/100c/boot.c:145-149` | no | FI2-specific boot initialization task not applicable to standard DISKBOOT builds. |
| `task_TouchPanel` | `0xFC12E74F` | `FINSIG` | `reference/finsig_gm110c/stubs_entry.S:341` | no | Touch panel events are handled directly by Canon firmware UI; not hooked in sibling ports. |

---

## 3. Output Artifacts Manifest

The FULL_HOOKS=1 variant full build emits the following complete runtime distribution artifacts under `out/port41-full/` and recorded in `manifests/port42_full_hooks_manifest.json` (mirrored in `docs/manifests/`):

| Artifact | Type | Size (Bytes) | SHA-256 Checksum | Description |
|---|---|---|---|---|
| `DISKBOOT.BIN` (Variant) | Encoded Bootloader | `124,153` | `20871cbad4d7f04b621f8d5cad39feeb0ac8f994b266788f900745a22bdf509d` | FULL_HOOKS=1 bootloader with FINSIG hooks, dancingbits format row 13. |
| `CHDK/MODULES/` | Directory (34 modules) | — | (See `port42_full_hooks_manifest.json`) | Dynamic runtime modules (`.flt` format): `calend.flt`, `mdetect.flt`, `cpuinfo.flt`, `mpopup.flt`, `tetris.flt`, `fshelter.flt`, `exmemins.flt`, `sudoku.flt`, `_osd_le.flt`, `curves.flt`, `reversi.flt`, `memview.flt`, `palette.flt`, `_hexbox.flt`, `_rawop.flt`, `ubasic.flt`, `eyefi.flt`, `shothist.flt`, `modinsp.flt`, `lua.flt`, `_tbox.flt`, `zebra.flt`, `snake.flt`, `benchm.flt`, `txtread.flt`, `edgeovr.flt`, `grids.flt`, `useredit.flt`, `4wins.flt`, `fselect.flt`, `histo.flt`, `_dng.flt`, `sokoban.flt`, `mastmind.flt`. |
| `CHDK/FONTS/` | Directory (74 fonts) | — | (See manifest) | Standard CHDK RBF raster fonts (`.rbf` format) for 16x32 and alternate UI scales. |
| `CHDK/LANG/` | Directory (20 languages) | — | (See manifest) | Localization language definition files (`.lng` format). |
| `CHDK/` (Total Files) | Full Distribution (242 files) | — | (See manifest) | Complete CHDK distribution hierarchy including `LUALIB/`, `SCRIPTS/`, `SYMBOLS/`, and `logo.dat`. |
| `port42_full_hooks_manifest.json` | JSON Manifest | — | — | Full cryptographic integrity manifest for the variant (`manifests/port42_full_hooks_manifest.json`). |

*Comparison with PORT-41 Default Build (`manifests/port41_manifest.json`)*:
- Default `DISKBOOT.BIN`: `124,097` bytes, SHA-256 `8b20175ad4d082cb3008398bdab3ab56c7331555eba30a1242ccb30c789c70e3`.
- Delta: +56 bytes in `DISKBOOT.BIN` due to `capt_seq_task` and `filewritetask` trampolines and `CreateTask_my` interception logic.

---

## 4. Owner Trial Plan

### 4.1 Strict Protocol & Safety Constraints
1. **Order of Trials**: The PORT-41 default build must be trialed **FIRST**. The FULL_HOOKS=1 variant may only be trialed **AFTER** the PORT-41 default build passes all trial checks.
2. **DISKBOOT SHA-256 Verification**: Before copying any binary to the SD card, verify the SHA-256 checksum against the manifest:
   - PORT-41 Default: `8b20175ad4d082cb3008398bdab3ab56c7331555eba30a1242ccb30c789c70e3`
   - FULL_HOOKS=1 Variant: `20871cbad4d7f04b621f8d5cad39feeb0ac8f994b266788f900745a22bdf509d`
3. **Power-On Budget**: At most **2 power-ons** permitted during the entire trial session (Power-on 1: PORT-41 default trial; Power-on 2: FULL_HOOKS variant trial).
4. **Boot Method**: Use a **held press** (hold Power button for >= 1.5 seconds) on each power-on to observe loader LED diagnostic pulses and initiate CHDK boot sequence.

### 4.2 Trial Steps Table

| Step | Target Build | Action | Checks Per Enabled Hook / Subsystem | Expected Result | What to Note (PASS / FAIL) |
|---|---|---|---|---|---|
| **Step 1** | **PORT-41 Default Build** | 1. Check SHA-256 (`8b20175a...`).<br>2. Copy to SD card.<br>3. Held press (>= 1.5s) on Power button. | Baseline keyboard & init file hooks: `task_PhySw` and `task_InitFileModules`. | 1. Green power LED ladder pulses.<br>2. Stock Canon UI loads.<br>3. WiFi button toggles `<ALT>` mode.<br>4. Menu button opens standard CHDK menu.<br>5. Power press shuts down camera cleanly. | **PASS**: Clean menu display, no crash, clean shutdown.<br>**FAIL**: Hang, black screen, watchdog blink pattern.<br>*(If FAIL: abort trial; do NOT proceed to Step 2).* |
| **Step 2** | **FULL_HOOKS=1 Variant** | 1. Check SHA-256 (`20871cba...`).<br>2. Copy to SD card.<br>3. Held press (>= 1.5s) on Power button. | Check every enabled hook: | 1. Green power LED ladder completes.<br>2. Stock live view display initializes cleanly.<br>3. `task_PhySw`: WiFi toggles `<ALT>`, Menu key opens 900x600 menu.<br>4. `task_InitFileModules`: Spytask signaled (`r1=1`), CHDK core running.<br>5. `task_CaptSeq`: Half-press shutter focuses; full press passes to stock task without hang.<br>6. `task_FileWrite`: Card writes suppressed; stock file write calls complete without timeout.<br>7. Power press shuts camera off cleanly. | **PASS**: All 4 enabled hooks execute without lockup or crash; ALT menu and shooting pass-through functional; clean power off.<br>**FAIL**: Lockup on shutter press (`task_CaptSeq` failure), hang during write (`task_FileWrite` failure), or watchdog reset. |

### 4.3 Recovery Path (RAM-Only & Battery Pull)
Execution is strictly RAM-only (`MEMISOSTART` at `0x003489B4`). Runtime card writes and flash writes are suppressed by compile directives (`-DG3X_DISABLE_CARD_WRITES=1`, `-DOPT_DISABLE_FILE_WRITES=1`) and linker symbol wraps. No persistent state is written to flash or SD card.

**Battery-Pull Recovery Procedure**:
1. Open camera battery door and remove the Canon NB-10L battery.
2. Remove the SD card (or unlock write-protect switch to disable autoboot).
3. Wait at least **10 seconds** (or 30 seconds for full capacitor discharge) to clear volatile SDRAM retention.
4. Re-insert the battery.
5. Turn on camera normally: camera boots pristine stock Canon factory firmware.
