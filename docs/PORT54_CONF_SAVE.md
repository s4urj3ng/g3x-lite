# PORT-54 — Conf Save/Load File-Call Adaptation & Safety Table

| item | sibling path:line | G3X current state | GM1.10C address or value | label (FINSIG/INFERRED/HISTORICAL_CHDK/ROM_VERIFIED) | change needed |
|---|---|---|---|---|---|
| **1a. Open (`_Open`) [reached: conf save & conf load]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:233`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:239`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:237` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:257`; wrapper: `chdk-port/platform/generic/wrappers.c:451-478`; linker wrap in `chdk-port/platform/g3x/sub/110c/Makefile:16` & `full_build/g3x/lib.c:147-155` rejecting write flags `(flags & 3) != 0 \|\| (flags & 0xF08)` | `0xfc37b3b5` (`reference/finsig_gm110c/stubs_entry.S:253`) | FINSIG | Existing code covers stub address; for PORT-54, update `__wrap_open` to permit write modes ONLY when file path begins with `"A/CHDK/"` (see item 4) |
| **1b. Close (`_Close`) [reached: conf save & conf load]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:182`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:192`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:190` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:202`; called via `chdk-port/platform/generic/wrappers.c:480-506` | `0xfc37b439` (`reference/finsig_gm110c/stubs_entry.S:198`) | FINSIG | Existing G3X code already covers this row (none; `Close` stub is verified and operational for both save and load) |
| **1c. Read (`_Read`) [reached: conf load]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:243`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:248`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:246` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:267`; called via `chdk-port/platform/generic/wrappers.c:529-532` in `lib/lang/fileutil.c:53` | `0xfc418d61` (`reference/finsig_gm110c/stubs_entry.S:263`) | FINSIG | Existing G3X code already covers this row (none; `Read` stub is verified and operational for `conf_restore` / `load_file`) |
| **1d. Write (`_Write`) [reached: conf save]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:267`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:270`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:268` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:293`; wrapper: `chdk-port/platform/generic/wrappers.c:508-527`; linker wrap in `chdk-port/platform/g3x/sub/110c/Makefile:16` & `full_build/g3x/lib.c:133` returning `n` without write | `0xfc37b471` (`reference/finsig_gm110c/stubs_entry.S:289`) | FINSIG | Existing code covers stub address; for PORT-54, remove `-Wl,--wrap=write` from `Makefile:16` (or route to `__real_write`) once `__wrap_open` path sandboxing is verified |
| **1e. stat (`_stat`) [reached: conf load]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:299`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:299`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:297` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:326`; called via `chdk-port/platform/generic/wrappers.c:754-778` in `core/conf.c:1331` and `lib/lang/fileutil.c:25` | `0xfc37b5cd` (`reference/finsig_gm110c/stubs_entry.S:322`) | FINSIG | Existing G3X code already covers this row (none; `stat` stub is verified and operational for checking file existence/size) |
| **1f. TakeSemaphore / GiveSemaphore / fileio_semaphore [reached: wrapper file I/O]** | `chdk-port/platform/g7x/sub/100c/stubs_entry.S:140,224,257`; `chdk-port/platform/g5x/sub/100c/stubs_entry.S:165,230,262`; `chdk-port/platform/sx60hs/sub/100f/stubs_entry.S:163,228,260` | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:174,248,284`; called in `chdk-port/platform/generic/wrappers.c:436,470,472,498,500,523,525` | `fileio_semaphore` = `0x000149c0` (`stubs_entry.S:174`); `TakeSemaphore` = `0xbfe153e1` (`stubs_entry.S:280`); `GiveSemaphore` = `0xbfe15459` (`stubs_entry.S:244`) | FINSIG | Existing G3X code already covers this row (none; semaphore synchronization primitives are verified and match siblings) |
| **1g. Candidate file calls NOT reached by conf save/load (`lseek`, `Fopen_Fut`, `Fwrite_Fut`, `Fclose_Fut`, `MakeDirectory_Fut`, `DeleteFile_Fut`, `RenameFile_Fut`)** | G7X `stubs_entry.S:284` (`lseek`), `:198` (`Fopen_Fut`), `:202` (`Fwrite_Fut`), `:196` (`Fclose_Fut`), `:229` (`MakeDirectory_Fut`), `:187` (`DeleteFile_Fut`); `stubs_entry_2.S:15` (`RenameFile_Fut`: `0xfc325ad1`) | `chdk-port/platform/g3x/sub/110c/stubs_entry.S:311` (`lseek`), `:220` (`Fopen_Fut`), `:224` (`Fwrite_Fut`), `:216` (`Fclose_Fut`), `:253` (`MakeDirectory_Fut`), `:207` (`DeleteFile_Fut`); `stubs_entry_2.S:28` (`RenameFile_Fut`: `NULL_SUB`); wrapped in `full_build/g3x/lib.c:134,157,171-183` via `Makefile:16-20` | `lseek`: `0xfc37b595`; `Fopen_Fut`: `0xfc37efa7`; `Fwrite_Fut`: `0xfc37f077`; `Fclose_Fut`: `0xfc37efcf`; `MakeDirectory_Fut`: `0xfc37b723`; `DeleteFile_Fut`: `0xfc37ef23`; `RenameFile_Fut`: MISSING in FINSIG (`stubs_entry.S:266`), mapped to `NULL_SUB` (`0xFC000011`), proposed bounded ROM range `0xFC37B000..0xFC37F500` (len `0x4500` / 17664 B) | FINSIG (`lseek`, `Fopen_Fut`, `Fwrite_Fut`, `Fclose_Fut`, `MakeDirectory_Fut`, `DeleteFile_Fut`) / HISTORICAL_CHDK (`RenameFile_Fut` `NULL_SUB`) / INFERRED (proposed bounded range) | Existing code covers these calls (none; none are reached by `conf_save` or `conf_restore`, and all remain defensively wrapped in `lib.c:134,157,171-183`) |
| **2. Card write blocking (`G3X_DISABLE_CARD_WRITES` / `OPT_DISABLE_FILE_WRITES`) and SAVE:OFF marker in PORT-53** | `chdk-port/core/conf.c:1159-1175` (siblings execute unblocked writes); `chdk-port/platform/g7x/lib.c` (no wrap) | `chdk-port/platform/g3x/sub/110c/Makefile:10,15-20` (`-DG3X_DISABLE_CARD_WRITES=1 -DOPT_DISABLE_FILE_WRITES=1`, `-Wl,--wrap=conf_save ...`); `scripts/build_port43_dbuf.py:1673-1765, 1910-1951` (staged `conf_save`, `config_save`, `save_config_file`, `do_save_param_file`, `save_params_values` call `g3x_conf_record_save_result(3)` and return early); `chdk-port/platform/g3x/gui_diag.h:1001,1343,1445` (formats `"SAVE:OFF"` banner) | `G3X_CONF_SAVE_OFF = 3` (`g3x_conf_save_status`); OSD string `"SAVE:OFF"` | INFERRED | For PORT-54 save build, remove `G3X_DISABLE_CARD_WRITES=1` / `OPT_DISABLE_FILE_WRITES=1` from staging build, remove `-Wl,--wrap=conf_save` from `Makefile:15`, and allow `config_save()` to run while retaining safety wrappers on non-conf file mutation |
| **3. Filesystem-ready gate (`task_InitFileModules` / `core_spytask_can_start`) and conf load/save ordering** | `chdk-port/platform/g7x/sub/100d/boot.c:140-144, 410-434` (intercepts `task_InitFileModules`, calls `core_spytask_can_start()`); `chdk-port/core/main.c:156,166,218` | `full_build/g3x/sub/110c/boot.c:176-182, 203-227` (`CreateTask_my` intercepts `task_InitFileModules` @ `0xFC0BD071` -> `init_file_modules_task`, calls `sub_fc0d9ccc` / `sub_fc0d9cf6`, then `core_spytask_can_start()`); `chdk-port/core/main.c:156,166` (`core_spytask()` polls `spytask_can_start`, then calls `conf_restore()`); `chdk-port/platform/g3x/gui_menu.c:1388` (`conf_save()` called only upon ALT menu exit) | `task_InitFileModules` = `0xFC0BD071` (`reference/finsig_gm110c/stubs_entry.S:342`); mount routines `0xFC0D9CCC`, `0xFC0D9CF6`; `spytask_can_start` flag in RAM (`chdk-port/core/main.c:31`) | FINSIG (`task_InitFileModules` @ `0xFC0BD071`) / ROM_VERIFIED (`sub_fc0d9ccc`, `sub_fc0d9cf6`, UI event 0x5006 with r1=1 in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:263-264`) / HISTORICAL_CHDK (`core_spytask_can_start` ordering) | Existing code already covers this row (none; boot sequence guarantees SD card filesystem is fully initialized before `conf_restore()` loads settings at boot, and long before `conf_save()` executes at menu exit) |
| **4. Central `A/CHDK/` path sandboxing check for enabled writes** | `chdk-port/platform/generic/wrappers.c:461-463` (generic CHDK only checks `if(!name \|\| name[0]!='A') return -1;`; no `A/CHDK/` prefix sandbox) | `full_build/g3x/lib.c:147-155` (`__wrap_open()` currently denies all write flags unconditionally: `(flags & 3) != 0 \|\| (flags & 0xF08)`) | Sandboxed path prefix: `"A/CHDK/"` (case-insensitive string prefix length 7, e.g. `"A/CHDK/"` or `"A/chdk/"`) | INFERRED | In `full_build/g3x/lib.c:147` (`__wrap_open`), replace blanket write rejection with central sandbox check: if write/create/truncate flags are present, verify `(name[0]=='A' \|\| name[0]=='a') && strncmp(name+1, "/CHDK/", 6) == 0` (or `strncasecmp(name, "A/CHDK/", 7) == 0`); if matched, allow call to `__real_open()`; if not matched (e.g. attempting to touch `A/DCIM/` or root `A/`), reject with `-1` (`errno = EACCES`) |
| **5. Diagnostic marker transition from SAVE:OFF to SAVE:OK / SAVE:FAIL** | `chdk-port/platform/g7x/lib.c` (siblings do not implement save result OSD diagnostic tracking) | `chdk-port/platform/g3x/gui_diag.h:45-48, 306-316, 1001-1004, 1343-1346, 1445-1448` (`g3x_conf_save_status`: `G3X_CONF_SAVE_OFF=3` -> `"OFF"`, `G3X_CONF_SAVE_OK=1` -> `"OK"`, `G3X_CONF_SAVE_ERR=2` -> `"ERR"`) | `g3x_conf_save_status`: `G3X_CONF_SAVE_NONE = 0`, `G3X_CONF_SAVE_OK = 1` (`"SAVE:OK"`), `G3X_CONF_SAVE_FAIL = 2` (`"SAVE:FAIL"`), `G3X_CONF_SAVE_OFF = 3` (`"SAVE:OFF"`) | INFERRED | In `chdk-port/platform/g3x/gui_diag.h:1003,1345,1447`, change formatted label for error status 2 from `"ERR"` to `"FAIL"` (rendering `"SAVE:FAIL"` on failure and `"SAVE:OK"` on success); in `core/conf.c:config_save()`, check `fd >= 0` and bytes written `wb == (p - buf)` to invoke `g3x_conf_record_save_result(1)` on success or `g3x_conf_record_save_result(0)` on error |
| **6. Confirmation of disabled filewrite raw/jpeg hooks, scripting, and logging** | `chdk-port/platform/g7x/sub/100c/filewrite.c:1-500` (hooks `task_FileWrite` for raw/jpeg writes); `chdk-port/core/script.c` (active scripting); `chdk-port/platform/generic/wrappers.c:482` (`OPT_FILEIO_STATS`) | `chdk-port/platform/g3x/sub/110c/filewrite.c:1-5` (inert 5-line stub; no `task_FileWrite` hooks); `chdk-port/platform/g3x/sub/110c/Makefile:10` (`-UOPT_FILEIO_STATS`, no `OPT_LUA`/`OPT_UBASIC`); `full_build/g3x/lib.c:131-132` (`__wrap_save_params_values`, `__wrap_save_int_value_file` inert empty stubs); `chdk-port/platform/g3x/notes.txt:34` | `task_FileWrite` = `0xFC25F3A7` (`reference/finsig_gm110c/stubs_entry.S:337`, unhooked/stock pass-through); `OPT_LUA=0`, `OPT_UBASIC=0`, `OPT_FILEIO_STATS=0`, `CAM_CONSOLE_LOG_ENABLED=0` | FINSIG (`task_FileWrite` @ `0xFC25F3A7`) / HISTORICAL_CHDK (`filewrite.c` stub, disabled script/log flags) | Existing code already covers this row (none; keep `filewrite.c` raw/jpeg hooks, Lua/uBasic scripting engines, and disk logging disabled in PORT-54) |

## Notes

1. **Firmware file calls reached**: CHDK `conf_save` (`core/conf.c:1159`) reaches `open` (`O_WRONLY|O_CREAT|O_TRUNC`), `write`, and `close`. CHDK `conf_restore` (`core/conf.c:1319`) reaches `stat`, `open` (`O_RDONLY`), `read`, and `close` via `load_file` (`lib/lang/fileutil.c:14`). All wrapper file operations serialize through `takeFileIOSemaphore()` (`TakeSemaphore` / `GiveSemaphore` / `fileio_semaphore`). Other candidate calls (`lseek`, `Fopen_Fut`, `Fwrite_Fut`, `Fclose_Fut`, `MakeDirectory_Fut`, `DeleteFile_Fut`, `RenameFile_Fut`) are NOT reached by conf save or load.
2. **Missing FINSIG stub analysis (`RenameFile_Fut`)**: `RenameFile_Fut` is marked missing in `reference/finsig_gm110c/stubs_entry.S:266` (`ERROR: RenameFile_Fut is not found`). It is safely mapped to `NULL_SUB` (`0xFC000011`) in `chdk-port/platform/g3x/sub/110c/stubs_entry_2.S:28` and blocked by linker wrap in `Makefile:20` and `full_build/g3x/lib.c:182`. If ever required for non-conf tasks, its bounded ROM search range is proposed as `0xFC37B000..0xFC37F500` (length `0x4500` / 17,664 bytes) within the GM1.10C DryOS filesystem cluster. Because `RenameFile_Fut` is not reached by conf save/load, zero ROM reads were executed.
3. **Central write sandbox**: Placing the `A/CHDK/` path check in `__wrap_open` (`full_build/g3x/lib.c:147`) ensures that every file write opened via POSIX flags is gated through a single choke point. Any write attempt targeting outside `A/CHDK/` (such as `A/DCIM/`, `A/MISC/`, or root `A/`) is immediately refused with `errno = EACCES` (`-1`).
4. **Diagnostic marker update**: Setting `g3x_conf_save_status = 1` yields `"SAVE:OK"`, while status `2` (updated from `"ERR"` to `"FAIL"`) yields `"SAVE:FAIL"` on the OSD banner (`chdk-port/platform/g3x/gui_diag.h`), providing immediate visual confirmation on camera without reading back the card.

## Adapted GM1.10C Stubs and Symbols Table

| Symbol | Address / Value | FINSIG line (`reference/finsig_gm110c/stubs_entry.S`) | Type / Role | Conf Path | Status |
|---|---|---|---|---|---|
| `Open` (`_Open`) | `0xfc37b3b5` | Line 253 | NHSTUB | Save (`O_WRONLY\|O_CREAT\|O_TRUNC`) & Load (`O_RDONLY`) | Gated by `g3x_is_safe_chdk_write_path` & `spytask_can_start` |
| `Close` (`_Close`) | `0xfc37b439` | Line 198 | NHSTUB | Save & Load | Active / Unwrapped |
| `Read` (`_Read`) | `0xfc418d61` | Line 263 | NHSTUB | Load (`conf_restore`) | Active / Unwrapped |
| `Write` (`_Write`) | `0xfc37b471` | Line 289 | NHSTUB | Save (`conf_save`) | Gated by `spytask_can_start`; routes to `__real_write` |
| `stat` (`_stat`) | `0xfc37b5cd` | Line 322 | NHSTUB | Load (`conf_restore` file check) | Active / Unwrapped |
| `fileio_semaphore` | `0x000149c0` | Line 174 | DEF | File I/O semaphore mutex | Active / Wrappers serialize |
| `TakeSemaphore` | `0xbfe153e1` | Line 280 | NHSTUB | Semaphore acquire | Active / Wrappers serialize |
| `GiveSemaphore` | `0xbfe15459` | Line 244 | NHSTUB | Semaphore release | Active / Wrappers serialize |
| `task_InitFileModules` | `0xfc0bd071` | Line 338 | DEF | Filesystem init task hook | Signals `core_spytask_can_start()` |
| `task_FileWrite` | `0xfc25f3a7` | Line 337 | DEF | Raw/JPEG image writer task | Stock pass-through (unhooked / disabled) |

## PORT-54 Build Artifacts and Hashes

| Configuration | Output Path | Size (bytes) | SHA-256 | Description |
|---|---|---|---|---|
| Default | `out/build-default/DISKBOOT.BIN` | 124097 | `24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9` | Byte-identical to PORT-53 default (`SAVE:OFF`, all card writes disabled) |
| G3X_CONF_SAVE=1 alone | `out/build-conf-alone/DISKBOOT.BIN` | 124737 | `8f3f3d4c21a0942420c8ea2894578a13d6f655bb5029da6321dfd480d397942e` | Opt-in standalone settings save with central `A/CHDK/` path check |
| Full Candidate (G3X_CONF_SAVE=1 + G3X_PLAYBACK_MENU=1 + PORT-50 menu + PORT-51 RESTORE2) | `out/port54-conf-save/DISKBOOT.BIN` | 133265 | `452d942c586044e59c20ccc89dfd977c863c34c2ac33b8c103157cbd208f6be4` | Opt-in candidate with sandboxed conf save, playback ALT menu, and DBUF restore |

## Owner Trial Plan and Recovery (PORT-54 Candidate)

### 1. Candidate Build and Artifact Hashes

- **Exact build command**:
  ```sh
  python3 -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --conf-save --out-dir out/port54-conf-save
  ```

| File Path | Size (bytes) | SHA-256 |
|---|---|---|
| `DISKBOOT.BIN` | 133265 | `452d942c586044e59c20ccc89dfd977c863c34c2ac33b8c103157cbd208f6be4` |
| `CHDK/BOOKS/readme.txt` | 90 | `e6140b50ed5f6c1d0e8c0af0bbc52f91355faa8c34f7941c7ff5282637981f17` |
| `CHDK/CURVES/readme.txt` | 20 | `ea09d83b939d563351d0a18782cf134c96cf025977d6d7a5816e1579102ea431` |
| `CHDK/DATA/GPS_Kreis.txt` | 10974 | `706bcca98d2a73f379fc2b2b447098db96da3e2e3b990d29b8c018af26463aac` |
| `CHDK/DATA/GPS_Sat.txt` | 899 | `090434eb05bd981f81bf2fc21c96069fe942b86f0d3375512cc25e417a8bc7c7` |
| `CHDK/DATA/GPS_Track_1.txt` | 986 | `483db9d438e667ec48383ddf6d481a724b1167155684919ea0c961ec7648d8aa` |
| `CHDK/DATA/GPS_Track_2.txt` | 986 | `95aa7bb685c23ef1af776a87d2973856493a2a4bcb36e4283cd982317c8ba3ae` |
| `CHDK/DATA/GPS_Track_3.txt` | 986 | `b6b8c81d93e30e669d6fb84c359e63474432a9347f5bdc4533f54b02ba7e9028` |
| `CHDK/DATA/GPS_compass.txt` | 10974 | `4b15877296cae8ea5f112be2520c0cfcb59e221d47e55d936b76904de7f3c40f` |
| `CHDK/DATA/GPS_needle.txt` | 3843 | `bf9c935310c283838e09f628e447d685873019386d6d4f37f922975c61e83713` |
| `CHDK/DATA/geo_data.txt` | 833 | `513ec9e91f95b17f17a5597181f42b7157d4fd80ea987713c67c50b9ac6a237e` |
| `CHDK/DATA/logo.dat` | 2458 | `4c57c6c5fe2c5a0829517c793f50cf30fcecbabbe946a37a0a8cccf8c288a7ad` |
| `CHDK/FONTS/AriUni14.rbf` | 13108 | `520c3383c5decc7846fdeebbd2722c405cf17898a926b9a1a11cb76014864a15` |
| `CHDK/FONTS/Arial14.rbf` | 11092 | `88be440feefc755e31b5e70943e309a67064291e37c5841010dff828a1fa4df2` |
| `CHDK/FONTS/Arial14b.rbf` | 11092 | `2c8ae8858cf7bcf8bd512b6e1d6355005f24d94145a96d703a421f151de5adb3` |
| `CHDK/FONTS/Arial16.rbf` | 12436 | `cf361df080b2d98edf889ca6baba14e70e8d73544e95651acb06b5375ae2bfb2` |
| `CHDK/FONTS/Arial16b.rbf` | 12436 | `92efcf8ef9b3e918882340f5df674d284acc3f148d4a159200a235086dcbcc95` |
| `CHDK/FONTS/Arial18.rbf` | 14452 | `f1c48cf99ba83edf13e24e848013c2bb2b6d99a95f8a97f8e2bedbf0c0f58e13` |
| `CHDK/FONTS/Arial18b.rbf` | 14452 | `735b83bf431e66cc829cc43efe717208727868963fe09e42d7319c2a93a6a70d` |
| `CHDK/FONTS/Arial20.rbf` | 15796 | `06f0b27ab297da8570aef08f84e5131c2cf9a887afb1de1ec5390014bbf2ca53` |
| `CHDK/FONTS/Arial20b.rbf` | 15796 | `8e5bc147e14676dc1ac5fe23ceae4950d07b422fb9c87b7ecc9ff2fd016bc6e3` |
| `CHDK/FONTS/ArilGR14.rbf` | 11092 | `8b68587a215b2e36fa2878084d1329b92209e31b054fb77b02ae04f4507236a5` |
| `CHDK/FONTS/BookAn14.rbf` | 7956 | `a00834b4e0dc2301e3154f0dcfa24bcb0159f772a0749fbf3fd5799992365749` |
| `CHDK/FONTS/Cour14B.rbf` | 11092 | `cd9fed795f575fca9cb322522d3a933534d545ada7845a94951529fe1d9c8ff7` |
| `CHDK/FONTS/Cour14BI.rbf` | 11092 | `18a965c64bb54ddfb2251cf19b5b587a979cc12e79b68869e74f3bb194de4be3` |
| `CHDK/FONTS/Cour16B.rbf` | 12436 | `fc734b54ac4197930997d35eb001fe6b847c7cc30b867cdbfec8322470f4d671` |
| `CHDK/FONTS/Courier14.rbf` | 7508 | `97456fd3d040685d9c510308af152b8094f99a97854feae04c8fb6b120bf64c0` |
| `CHDK/FONTS/Courier14b.rbf` | 11092 | `b3840d81b5d8d30174b7f34402faaab1c47159e1408ce5b0ab8336e2a483daf1` |
| `CHDK/FONTS/Courier16.rbf` | 8404 | `fbc4a83541a98f6ec5ad12cc6f7a02877d1e3967755d93a214d7656436dafdcd` |
| `CHDK/FONTS/Courier16b.rbf` | 12436 | `fc86a302ee67f2a23dd83dc4541e3071fa65df71e6196ccb092ceaee1d1a07c4` |
| `CHDK/FONTS/Courier18.rbf` | 9300 | `8bb0ef741c23400895a7ef870c58ffc5b6d52e221262fe5eaa5a1a13b09a3476` |
| `CHDK/FONTS/Courier18b.rbf` | 13780 | `af74ce791d1d658f404d190ec4ca9b21dfcb4782e9e71a0a03ba329eda5793b9` |
| `CHDK/FONTS/Courier20.rbf` | 10644 | `73a76a423ef03b8e50da18b4901db55188a5102727b0d3f2339d7f6934afe07d` |
| `CHDK/FONTS/Courier20b.rbf` | 20948 | `e44fcd87accb44855d57c327836bcd7f3cecaf44d2efceba2225a5dd5aff2b0b` |
| `CHDK/FONTS/Garam14B.rbf` | 11092 | `77aaaff70e64276bad465734f01e406095051693d150409234dde19f3f08404c` |
| `CHDK/FONTS/Garam16B.rbf` | 12436 | `baca8676ef2b4181d60bc3b238639ca9533661e3880aa54e3df81c19e6ec66d3` |
| `CHDK/FONTS/Geor14B.rbf` | 11092 | `173afe1fd13f1aecddef04dea5126440c0603ac53e18cf38ef5d34188461d44b` |
| `CHDK/FONTS/Geor16B.rbf` | 12436 | `708293ab37e7a5a14f4e5eec1f0b12da3394c48f272b1ccd0c447b222cb726a9` |
| `CHDK/FONTS/Gill14.rbf` | 11092 | `43065dd58bdf9d669c0b7949b83509b289d970b96e9f96a7617bc61de5161137` |
| `CHDK/FONTS/Gill14B.rbf` | 7508 | `c6e4f72c7ad93f5aeeb5b1233e5fa96877795dd45b8ce3e710193eb83123d370` |
| `CHDK/FONTS/LucSC14.rbf` | 10196 | `d59dfd1fd7de50fc9f5b9be4a67d9372d776d50ff5e42dc178a425c9da724b8a` |
| `CHDK/FONTS/Lucida14.rbf` | 10196 | `78e3c72433d41d3c65331de45f690ddd75bbfd9ac36741ed03104b04d7076582` |
| `CHDK/FONTS/Lucida16.rbf` | 11540 | `cde18e45792d1fadfa9d3451d24f81b870b9ca062a2205ab3c1596f6ff8f913c` |
| `CHDK/FONTS/Lucida18.rbf` | 19156 | `5104050496006e01b8f988a590e72c5253a4accda596311cbfaaff70e2a95563` |
| `CHDK/FONTS/Lucida20.rbf` | 21172 | `a5797eb04010ee061337f541d4d41821601f717de67ef3615d9c0d19801c0820` |
| `CHDK/FONTS/Menu-A16b.rbf` | 12436 | `242247f1765e4c1e57c4b98ea073a68956772728e19032b75a6fe95bfc71f0e5` |
| `CHDK/FONTS/Menu-A20.rbf` | 14452 | `6a5d8d57a02c5af24d3e12fb50251ad30656ffddc85b30e132779d3970f861ee` |
| `CHDK/FONTS/Menu-AN18b.rbf` | 8852 | `7f57843b10111e8b31ab1c65605d5a62894f3fa9ca82565100c544f9fc9ba780` |
| `CHDK/FONTS/Menu-AN20b.rbf` | 14452 | `ec4ffaae2659ecf123127c67da57d06ed8e6e8469622d46f733edade393f96fb` |
| `CHDK/FONTS/Tahoma14.rbf` | 11764 | `149c76605d9acc94c896fc3d24a5cfb6f6163ce951dbd9e0e827d64d1b11b4eb` |
| `CHDK/FONTS/Tahoma14b.rbf` | 11764 | `85afdfc8293d8f2fc764d1da11aeda9a4e69747c1b9c85c25a2574f54310337b` |
| `CHDK/FONTS/Tahoma16.rbf` | 13108 | `41a54bfa780f1a26444ccbc42fd1753aec980d133afdcbaca9213be03343ea55` |
| `CHDK/FONTS/Tahoma16b.rbf` | 17364 | `2abbee454f67a2aca31a10c41e8a6e95e1387ef848615f3f76cff613e98c8f8b` |
| `CHDK/FONTS/Tahoma18.rbf` | 20052 | `f41c1a0144e39238095406dcf87027da76f33cc088a20ceec84fcf48b9236e45` |
| `CHDK/FONTS/Tahoma18b.rbf` | 20052 | `b3cdc4a3887ec7b4f923ddb175e6da9264b959f42392926bd8c7c56374da8ad3` |
| `CHDK/FONTS/Tahoma20.rbf` | 21844 | `8f4c94070e5f44145879ae33041ef15e9d4baad7705eecaf14650b9ac8e675c9` |
| `CHDK/FONTS/Tahoma20b.rbf` | 27220 | `4985549d65238ef56f60606b558fdd34256173d5e810e289250a95d88267d488` |
| `CHDK/FONTS/TimNR14.rbf` | 11092 | `4d3ad46aab13ac311d3f387c3a0a1055d48c58ff5fc2bb0dc3971de438422d92` |
| `CHDK/FONTS/TimNR14B.rbf` | 11092 | `6a15818306400b67dcea2385f3029070288dd13494a75677a2b1742397321fe4` |
| `CHDK/FONTS/TimNR14BI.rbf` | 11092 | `7db513287304189b5d17fcb172205b71b67271ff1ace4042cfae189fa633478c` |
| `CHDK/FONTS/TimNR16B.rbf` | 12436 | `6a3fae3a9d251c18502620001ed101de4df1f6430be906bd9441c7bee1cc52cd` |
| `CHDK/FONTS/TimNR16BI.rbf` | 12436 | `d6afca36718cb5dbd0c5bdab900859394dba2a40e2a124c9b876564792d445c5` |
| `CHDK/FONTS/Times14.rbf` | 11092 | `b99966a397536a4b6b84b69c0a587c4fbb51c63c4b8af03e60968e5c0d7fdcde` |
| `CHDK/FONTS/Times14b.rbf` | 7508 | `2de65b8437fd0ae8b70d49623b1897a8fd2e8e977e45fc37433adbaf95ae6cb3` |
| `CHDK/FONTS/Times16.rbf` | 12436 | `fe16af85cf7906c0da144eb6095f77f751bc382cf09584bcaeb41872c670b622` |
| `CHDK/FONTS/Times16b.rbf` | 12436 | `14c336a674d57a142dc54d4a8fbb37924595d49005e40cab32586be44811b0f0` |
| `CHDK/FONTS/Times18.rbf` | 14452 | `500f4c445f7e6c5b9edd6dfe33fc64cb6674a1491a4a61f2ac3737548f2048e6` |
| `CHDK/FONTS/Times18b.rbf` | 14452 | `00b5ca94a2161dc6ee48ea2bae138fd922946aba9a49dd76eaa7f9c6ffa5a74f` |
| `CHDK/FONTS/Times20.rbf` | 15796 | `5ab722b531712ee8d88f738bf94413e8327628a2b1b9d0c7984668a38c82e8c8` |
| `CHDK/FONTS/Times20b.rbf` | 15796 | `c89b46661efdcea364030081ef2218dabb5ff7f7d09bf5bef6770d15bb9dc4cb` |
| `CHDK/FONTS/Verd14.rbf` | 11764 | `7c3b99df289a625d91929b9b3f4daa77287f52db7a7575c11db058cf06639fbb` |
| `CHDK/FONTS/Verd14B.rbf` | 15572 | `6d53d98bfb6b21ae74541cb8eee4f9c91dc1c0295f9d847854663bfcae979f48` |
| `CHDK/FONTS/Verd14BI.rbf` | 15572 | `bbca87e86827cb27a23992e31504115efd86c56256b8b8ab2c315180053c5cea` |
| `CHDK/FONTS/Verd16.rbf` | 13108 | `5d7557b6b5d7b2fe9a9f7c7383684eb89dd7d5f9bf179ccaccc02d67b6c39375` |
| `CHDK/FONTS/Verd16B.rbf` | 17364 | `4a860706360046094ad3dae5594ca9994c03f6a455b40591c4101f6569713a52` |
| `CHDK/FONTS/Verd16BI.rbf` | 17364 | `d58a66e93a27925e59bbacfb26479333e167f30adb045d5ee661a47469f8fb69` |
| `CHDK/FONTS/Verdana14.rbf` | 11764 | `239e024d0724acc4c41bc412c72805b080e22a9d3ed6638525fa101affb67678` |
| `CHDK/FONTS/Verdana14b.rbf` | 15572 | `070c391e11d13f64675628209f32b4667263ea70b2dec8eee60f99c51f2eb09c` |
| `CHDK/FONTS/Verdana16.rbf` | 13108 | `6fce0e9d39f24e8c3edfd16a46a46b36548dd359dce80acb85d4a3222e39184c` |
| `CHDK/FONTS/Verdana16b.rbf` | 17364 | `789e1dbf20f13b6b9f3b901007c3b86880d06b7b8e3b6e6a0c9fbd9795b97cf8` |
| `CHDK/FONTS/Verdana18.rbf` | 20052 | `4b0a81f4b5dbaaa1981d0f3fa831bd7b927bbdcf41fe64bd903f5ed2b7117de8` |
| `CHDK/FONTS/Verdana18b.rbf` | 20052 | `f3aa1f52d50046d9cd7bffdb4ba2431202f8bfd51694dcc01f0936e2f4c54d3f` |
| `CHDK/FONTS/Verdana20.rbf` | 21844 | `d40c4a16e98ebee34c68eca0e2bf89a5faf99238ed7b088ca9494a6e18b945a7` |
| `CHDK/FONTS/Verdana20b.rbf` | 27220 | `f5d291854ef1c7c673e77ccd7b06a4bd9ea7af1bef5ce2cb409aaadb8386c767` |
| `CHDK/FONTS/arialround16.rbf` | 13108 | `af8eef6189c2e9ebe2736d5048ec3b3143c9914d3aaea96c4f1d6dd8ffcef0e6` |
| `CHDK/FONTS/arialround18.rbf` | 14452 | `3ffbe9b6390041f1ed9da96b6b0d43e1c43fb2ca2cb31d92d8970174d985a2f3` |
| `CHDK/GAMES/SOKOBAN.LEV` | 12365 | `579780550fcb84117272370113a9d94407b0be21763a40f1347d1785c89f2407` |
| `CHDK/GRIDS/16to9grid.grd` | 71 | `b2e27742f8e1652d3362d11855481a19a6b89091dfb80f11cd9659fb37c38c3d` |
| `CHDK/GRIDS/3to2grid.grd` | 70 | `d0f29fe88de1c409092a069ef75118ff9a90f220749b967aa087189aec14d15d` |
| `CHDK/GRIDS/3to8grid.grd` | 132 | `9f729315678a20cc002a72498433e93034a78cfd6ef2916584498008616ea4f7` |
| `CHDK/GRIDS/golden1.grd` | 70 | `5e05c9dcac7caf39d1e76d48648713876dba3d78d418cdb1fa49dd8b2a7529fa` |
| `CHDK/GRIDS/golden2.grd` | 70 | `48d09e98c8192d55f01a93cc76cd04e7f511082eb5f7294dbba030b82f27d112` |
| `CHDK/GRIDS/id.grd` | 515 | `d18ed4f4b847e75593b67a43213eef56c9135d5b2966c727b1db461d0c43a3a1` |
| `CHDK/GRIDS/readme.txt` | 8263 | `6403ee7e39dbc5d364d9d8a094ab1875dd0a5d8844e843a2a131e15aded38340` |
| `CHDK/GRIDS/rulecross.grd` | 3620 | `d5d906636cd1a1b2dfcabe087337dda3ac35fa4ae8113f5a4d2bbc610fd39d11` |
| `CHDK/GRIDS/rulers.grd` | 2255 | `52b7cd4fb479bae542f170ecc5ec6e360aefa6f10f2e2e799a346ff02a7b94bd` |
| `CHDK/GRIDS/sports.grd` | 176 | `abc2831f64da8042e96b85e23134da9bd6188d6a6795456f6b5901c109361d30` |
| `CHDK/GRIDS/stolen.grd` | 2352 | `bc82854a6af604231aa1bebfd68145c9dff774c051e30415bd2288360bfa9705` |
| `CHDK/GRIDS/third_h.grd` | 76 | `499d013a28717b39923bea9ef38259d2ac5775f066cfb2620dd8df72f8d6f5f6` |
| `CHDK/GRIDS/third_v.grd` | 74 | `17ee2d9824d9362b2a2434580713eb9bb6c16b49fbc055134f15e9a996f1d601` |
| `CHDK/HELP/CZECH.hlp` | 1017 | `cb2beddcda86eeac52b98fa3489e7ee828ee56e1ecf4d239f6639b1824824a17` |
| `CHDK/HELP/ENGLISH.HLP` | 855 | `b0ce655a218e4f0ae4246fd5744c2ad8bc85028e107874c70f74a11b96492633` |
| `CHDK/HELP/german.HLP` | 1055 | `bcda6df6e1d6f64694a1f5895152f3d4cb29f918c764d75096787600cd7ad3da` |
| `CHDK/HELP/russian.hlp` | 1184 | `f43860e23ac04398bf0e80ef23579714352aa22be4c52a6bbcb4e0043fe64658` |
| `CHDK/LANG/croatian.lng` | 17661 | `74ed22c8b53bb8869a549a030ed55bce5c394e5dedc9999b7ad69f9de4137dc2` |
| `CHDK/LANG/czech.lng` | 17896 | `2973c3ca0d2e5431a0aec1eeaf62c2bc29a2695d756f254e11dfe607490f9ad4` |
| `CHDK/LANG/dutch.lng` | 11448 | `6e89a8ec057f0e5f07617d95ef6be97c2a0d9040942559037a078ce933239e47` |
| `CHDK/LANG/english.lng` | 17983 | `298b8d4b3489e8cf0ac62212483aa709532dddeac8b53ee4025242823fd5b257` |
| `CHDK/LANG/estonian.lng` | 12161 | `2a49e41fae7ba4ae9419092da097b9cf3a62ee10df012cf2322099ddd1287867` |
| `CHDK/LANG/finnish.lng` | 12260 | `8c539baac54a82c268f37a52aec67e7f7930e204c4dc6e062bb60b2164d853c5` |
| `CHDK/LANG/french.lng` | 12261 | `bf282a61df3af2e4f9fb85098e957feefffa1fbc90d28bc25dc14bf22a9b2420` |
| `CHDK/LANG/german.lng` | 19419 | `b7e74bd7b81f397a0ebd0aa8d9ada0f52cb8812641dab35ee870f72b4cdb7ece` |
| `CHDK/LANG/greek.lng` | 13137 | `909c275d9d7554c9936e0de88e00d99dcf7df6cd5bd2a70345d49bd4d0583e25` |
| `CHDK/LANG/hungarian.lng` | 18474 | `f25c923db59686adb439b0636f43dc1e7cd3041f917ae01be7563540d53c42ec` |
| `CHDK/LANG/indonesian.lng` | 17902 | `217174268f492bb1a30cc529110a7cff948a288fe3427e57fce92b81ce737a2f` |
| `CHDK/LANG/italian.lng` | 19937 | `f22331f5783687328c0775211072a5a41b988c7b9ac6447a370609752724fd16` |
| `CHDK/LANG/polish.lng` | 20647 | `20683ab741871b6ede74aa65bff4102df55804be32f1d11605cf55d8cbf9cfeb` |
| `CHDK/LANG/portuguese.lng` | 12532 | `a90682ee1e8dfc3d9980bb1c830f5cb6d16bafc693c6c2e02ed98e7933f1407b` |
| `CHDK/LANG/romanian.lng` | 13199 | `1769d79afc93c8f445d2adc4c0edcec6283c7be7266c511dcd12f3ad38e60270` |
| `CHDK/LANG/russian.lng` | 18761 | `d84f5b47a95e7f92812c1a569e98b6e02093633c4ebb9a279fcc8a657a536172` |
| `CHDK/LANG/slovak.lng` | 10783 | `d7ea01d04ff2a83fb74739a02b978cdf70621fcf4a9d6033d3b2f21392c8dbca` |
| `CHDK/LANG/spanish.lng` | 19026 | `8a30f05f4909ca1c5fa6ee75fdbe3e1e3d28fdb6dc24dd6bd2ea6d4c28192d25` |
| `CHDK/LANG/turkish.lng` | 12768 | `ebc34839917eb2c5da818362c31f29c8d949e35493d005ec1ced5b656ba4b38b` |
| `CHDK/LANG/ukrainian.lng` | 11837 | `434ace867ce934d55531dfce4bf81380d0f3dc2d11d051e29b42a972660a3590` |
| `CHDK/LUALIB/GEN/README.TXT` | 416 | `c39e6ad701e39b9f10f3afee848695cdaf8795fd214173ffc6ac7951b37243ca` |
| `CHDK/LUALIB/GEN/cnf_core.lua` | 3252 | `01a8ce1a89b8794c870da2ffb19b7e620a535be92c73f4efab79a4637341544a` |
| `CHDK/LUALIB/GEN/cnf_gps.lua` | 847 | `52fa36073a05e2c07ee39706d50e8c60f15d49f11b1436555cb76f40f9d722b9` |
| `CHDK/LUALIB/GEN/cnf_osd.lua` | 3185 | `467954bbb3cd8801f14b97c5534d9aba007de2ff76895412bba9bdbe2f98be78` |
| `CHDK/LUALIB/GEN/cnf_user.lua` | 184 | `8994af48094ed7f284875f8a5b93eda0b1b59db3df769bf511d0923e1645a260` |
| `CHDK/LUALIB/GEN/modelist.lua` | 2867 | `84beb439a1e1b1bf25fb07bbe81735b65a05da1967b8f474ea629eb848e09723` |
| `CHDK/LUALIB/GEN/propset1.lua` | 3023 | `2571a32e0d21c8e7e659206db0fa388906f84aaf058574f4392035ee703d5152` |
| `CHDK/LUALIB/GEN/propset10.lua` | 6435 | `72b6f9b1f277b1a12619ab2688dc82849fee631a4af0514e5d1088514f15b058` |
| `CHDK/LUALIB/GEN/propset11.lua` | 6564 | `c0c0f8bed6bd6d0075e065b9c3850ce941c3e225e25e68b1875b7ccf998cc5e0` |
| `CHDK/LUALIB/GEN/propset12.lua` | 4030 | `c5c0ed016c6c4d157c3fc843966c1c1be3e5814d3cd23b225ca32c4f7281ef36` |
| `CHDK/LUALIB/GEN/propset13.lua` | 4915 | `0334b958821e7e7f3fa23cdb9df7810d1f0a57385c50752d06749885e96804c5` |
| `CHDK/LUALIB/GEN/propset2.lua` | 3773 | `bd36b03048389f2b221a9877879ce1423ba61cf4e89d5cc7d0e6e01e2ff621a0` |
| `CHDK/LUALIB/GEN/propset3.lua` | 2696 | `57f95d3f0486fc49657bb6250a0c98e4f8aae59da3699e96c25fb8ef87c87f06` |
| `CHDK/LUALIB/GEN/propset4.lua` | 5519 | `36bfdded75cf036cdc0b9a6cbff02a40c72506adafbc0d6685855380ff06e4fa` |
| `CHDK/LUALIB/GEN/propset5.lua` | 5768 | `acbcc5ae6275cdd5bc5f32c777a4411249eb5235a3e7d43520a02e73eb736191` |
| `CHDK/LUALIB/GEN/propset6.lua` | 5770 | `3693b855687ec1f6a2e7447f5a6fc7aa387b2f181de5bd8595f46c5730add791` |
| `CHDK/LUALIB/GEN/propset7.lua` | 6001 | `a06abbe308fdcaa96bf876a4fff3b46237fddacea6960c41dc5bd2050a7d027d` |
| `CHDK/LUALIB/GEN/propset8.lua` | 6856 | `7518c69f5cf2c9a1cff10ed3532dcac059dbc00be8672823ea4b2ac590e46f99` |
| `CHDK/LUALIB/GEN/propset9.lua` | 6046 | `4c8b3afe1db430d69b8c68f80d64b9e1eeb184689f9d497fd615f15e52e6f7c4` |
| `CHDK/LUALIB/binstr.lua` | 1846 | `884aa59f87691835cabecff5fc1b8d7e17a56ee383ee4c37e1c86e389148dfe4` |
| `CHDK/LUALIB/capmode.lua` | 2517 | `b8068fdf110469714ddd547e74964b83caeb38f399d6b3d6b302d839ea09befc` |
| `CHDK/LUALIB/drawings.lua` | 7015 | `060d760b94f19043379d0628a74f4967a9042ce2de351a1ef045bf9683672da7` |
| `CHDK/LUALIB/gpsLib.lua` | 4697 | `a5f4fc54581154756191a3c169f56defde82b6a59ce6b9e3fdc0e07ef15adba5` |
| `CHDK/LUALIB/hookutil.lua` | 2144 | `34804ce92e3b762678f19b8d95a791f4bdc97505fd4397a219d3d01aaf89f35d` |
| `CHDK/LUALIB/iniLib.lua` | 4284 | `da83172024c417bb89f57b8ea07e2ad4fbadc3dfb0e353897875da4080453f8f` |
| `CHDK/LUALIB/propcase.lua` | 1118 | `a4704ed5241b2da7461f525eba15a746a82906c82757b2cbebe7e9a90a6a7b11` |
| `CHDK/LUALIB/rawoplib.lua` | 3156 | `b41fe918c93f9dd4e2a260dec48b874a178923bafc910360122a100c14375036` |
| `CHDK/LUALIB/readme.txt` | 150 | `b6ab5048e5c9d730189af98e32f4c0e0a88d807a497f635cee6499a6b645f806` |
| `CHDK/LUALIB/uartr.lua` | 1845 | `50a42748614d6e289e6e400836d7ada61dcaa9e60c130fac5eb9d4e17161f548` |
| `CHDK/LUALIB/wrap13.lua` | 393 | `434537bf17a9e78c8eca8b7e49f5df0e3b64258605e285a0088cf10b3c5ceb99` |
| `CHDK/MODULES/4wins.flt` | 4756 | `ca79f48d7ea501f7040116fa55cca42504edf02d4fc9bda9e6adde17fe140d21` |
| `CHDK/MODULES/_dng.flt` | 8584 | `1e9fb1726d03964153d3298007f7f34febcd3d69d14b9e0d799abc3f029a6d8d` |
| `CHDK/MODULES/_hexbox.flt` | 1568 | `3abc35baa26a5587a62b0901c33daebb3df76e58a11dacbbb43e4f4bab3a9277` |
| `CHDK/MODULES/_osd_le.flt` | 1840 | `35acb014b51ab24287ca67a122ff40c24500196c70d3ba781c660397c8ff4aa3` |
| `CHDK/MODULES/_rawop.flt` | 5516 | `c6ea2442c11bbedaf405942fd7732561bf21747dbd4a2b8c7aeff2bd72fa43f6` |
| `CHDK/MODULES/_tbox.flt` | 4252 | `a166078bf5889876c6a4c8b236f78e87214fb58172664a9786835392e98125fc` |
| `CHDK/MODULES/benchm.flt` | 4880 | `5996d525e0f35567cf37b580c546ac2de2f3f2cc1e205da9d4b0d1722ab26211` |
| `CHDK/MODULES/calend.flt` | 1816 | `b4e0a1d2f45f987b62f4a807f372154c76a1ab57df1387bdf4cef949f6c22e17` |
| `CHDK/MODULES/cpuinfo.flt` | 11452 | `315870f3c78e933c43a182b9ab2a85ce402fd397e1e86671048b5b5dfe157546` |
| `CHDK/MODULES/curves.flt` | 2676 | `2814c0bbe49e754db511514226dd4c2806d5c747582187352b1012691ea11c52` |
| `CHDK/MODULES/edgeovr.flt` | 3852 | `0e97b90fa2543d608b5e221c77ee7e5a87159e11b32c8ba7f136e918f5d9f518` |
| `CHDK/MODULES/exmemins.flt` | 2616 | `09e92a1d6c4b2eab789a96da690357f34f19b23bbccf16fb72764141e6a35ccc` |
| `CHDK/MODULES/eyefi.flt` | 10944 | `748c9dd42b8467ad7b893c56f794d7f63929026bff0bd8d27d5da0b48059bf16` |
| `CHDK/MODULES/fselect.flt` | 9032 | `16c7963abc0f25d87c2b40743f235114b6caec2fbee77b4359f926f62e4756e9` |
| `CHDK/MODULES/fshelter.flt` | 7816 | `3eaf2c95d381cdd0ee759e308cbba996a06e2505754fd3f41672632986f807e8` |
| `CHDK/MODULES/grids.flt` | 1340 | `3ceb32bd271ee35df1759846193cf1582672f86323353e22b435b6ce6d97ff1a` |
| `CHDK/MODULES/histo.flt` | 3044 | `dd59f9e7e1a921437a1f4781ecbef00761daaa74860ffa715b2d314591b87cbc` |
| `CHDK/MODULES/lua.flt` | 99732 | `0e54001ab304beb390aec40f5fe373da9e1d1268cf3c0195f3d6e0b51149a473` |
| `CHDK/MODULES/mastmind.flt` | 2444 | `a707f074b383db0e28751c91586f2ea6fa7243fbeb9bb8ba433100eed176fc73` |
| `CHDK/MODULES/mdetect.flt` | 3060 | `c59ade2b1447ecdf548e84b42bdd95bd7a526605164d04609d1c0b25d0806e5d` |
| `CHDK/MODULES/memview.flt` | 1616 | `bcdbed5b807c9f101de6ec41d552fe51da3e96992cc6ffa86c421bc54d106761` |
| `CHDK/MODULES/modinsp.flt` | 1480 | `a05133a3252ce4d485a7cd6ac01b7289e5b3b6a4a96d0ba6d97d1287605e9514` |
| `CHDK/MODULES/mpopup.flt` | 1120 | `2b1fb1b83930c5d7bf977ed3172457d593f10665a0d9b9a33b981b80bd9f4a90` |
| `CHDK/MODULES/palette.flt` | 3284 | `5fb5c141367a2671467b91f89ddbf4e9666ad3893db1b6ef9df7c1c4e525ff80` |
| `CHDK/MODULES/reversi.flt` | 3368 | `122ea749cd8656cc359ef688e54371de4585cda21acf7a269f75806a39b3d388` |
| `CHDK/MODULES/shothist.flt` | 776 | `814e0177d2d6d5b5e2cdc8b1cbabcd93798781869a70e143c55853a20b1336e7` |
| `CHDK/MODULES/snake.flt` | 6980 | `9bd75c134665fa8e1bf8013ed7feba033256937b51dc043fac0f4e328f108064` |
| `CHDK/MODULES/sokoban.flt` | 3596 | `86a6046263ba0179387af5bf8cacfb61ca6ef5f8a5b5f5fe9e0b8a678bfa9359` |
| `CHDK/MODULES/sudoku.flt` | 7384 | `b77fa489877f0619460239f5b433a62a08065eaf0c0b5935d9c7b65c87b2966c` |
| `CHDK/MODULES/tetris.flt` | 3680 | `562c13e88377090a26e0bb7396f30774de6f0e64199d41052a6cf900f9dfeb80` |
| `CHDK/MODULES/txtread.flt` | 2660 | `e912d066b2892718677b4ad129e967ddfe8846d15e397046d05e8dbf565ad146` |
| `CHDK/MODULES/ubasic.flt` | 20040 | `917498e5dc5d6059fc95d6721703ce32648bfc93d7132fd259b658989e25d480` |
| `CHDK/MODULES/useredit.flt` | 5384 | `bf7fa89b8dc9128ca6fbf3feada5a5c4f9a8dffb50b259b0731d9d1f7a9ee7f2` |
| `CHDK/MODULES/zebra.flt` | 1452 | `d18b65e339d1069d4d4fdc9ac123006f15c65a9cc4e019ddf42006ab056c26a1` |
| `CHDK/Makefile` | 2011 | `6bc345c9d1e9ff0c3900be71e535b761b5998f47e160272708d1e22869904a50` |
| `CHDK/SCRIPTS/EDITOR/EDI.lua` | 21965 | `d1e836fb4f4ca2d019df02c48acdb567f3a77ab481ced4079366c771fb047d7a` |
| `CHDK/SCRIPTS/EDITOR/README.TXT` | 10169 | `d97003f153040cee2c3898f049421ee5b20594bef56669e9d91be0dc7860ad46` |
| `CHDK/SCRIPTS/EXAM/countdown.lua` | 969 | `103ef095f0a8932f6e849a2e73bac858f281d2d00f272247bd72457e093f14bb` |
| `CHDK/SCRIPTS/EXAM/eggtimer.bas` | 2949 | `1db9a68c8ecc322a4814ea12ba636b474ae9b4fb7d266897535f0cc738552ab9` |
| `CHDK/SCRIPTS/EXAM/lotto.lua` | 3255 | `9fee28f134e980be1d0538042d9da7b036b17c84b67df53c31cb39d7aa43fdf2` |
| `CHDK/SCRIPTS/EXAM/metronome.lua` | 964 | `6a65b07ae4b6843c9bbda841f50da782e93c98d895f91ffe536f420c8365c973` |
| `CHDK/SCRIPTS/EXAM/remote.bas` | 272 | `b7883c3135f12cf3bc874239a3ddeb7cdfbaa9d047f67c652e507e3476085f46` |
| `CHDK/SCRIPTS/EXAM/stopwatch.lua` | 1210 | `4e88e3a42c7059c598bba772081354928ea0bbace58255e8e6a27bee35c008ac` |
| `CHDK/SCRIPTS/TEST/MD_Tune.bas` | 2054 | `8585fb6845d22c870cd0cba0838ac6a776d6783d1ae951d39d5515d3a03dc132` |
| `CHDK/SCRIPTS/TEST/compat13.lua` | 634 | `c1b9e04dc08ef28884af5ac3c6c83c8e1d2df15a2239eb96151992325a6aed5a` |
| `CHDK/SCRIPTS/TEST/drawtest.lua` | 3059 | `cc47231bb918e1fa935cf3ca932fd9f1a56e8e82d23605e9e030fd705acaf6ad` |
| `CHDK/SCRIPTS/TEST/drtest.lua` | 13931 | `f0d4d849b7c33f1d5366dde7116023e9c721f7eef46084c69e0c28ed71cae0f3` |
| `CHDK/SCRIPTS/TEST/filetest.lua` | 105 | `5b472900942406eb18616a93165b3e9865150c4ce122308db49c293a0ba59abb` |
| `CHDK/SCRIPTS/TEST/gps_test.lua` | 1162 | `12dcfb89b51e77a0d2c4d21b7868fb48eb9293eacb8e8c790c731f413cb692d3` |
| `CHDK/SCRIPTS/TEST/hooktest.lua` | 11147 | `0bab92e9d5da990ea7242d02a3825a9de507d958df4e181b856e9da05c34fe79` |
| `CHDK/SCRIPTS/TEST/imath.lua` | 5546 | `4ea953add9fa0e04e144a18017f6b7e5f86a1b8c8fec5ec728a083ed2f1a8952` |
| `CHDK/SCRIPTS/TEST/ini_test.lua` | 1798 | `507e5be205dc2400e0204dade458dbe9db7df29d9d6a8b32f0180abd974878a6` |
| `CHDK/SCRIPTS/TEST/isobase.lua` | 1033 | `d5cbc4d9e0257c6fb4ef8bc9c68f1ba6b242aa1046dd5c51924a265194719345` |
| `CHDK/SCRIPTS/TEST/isoinc.lua` | 9918 | `657540cf7ac82b26fecbc7b103bf9c6245359facd2a6d65c27ad54b15a1728c6` |
| `CHDK/SCRIPTS/TEST/isoovr.lua` | 3341 | `1331dcc8fffddd086fa5ae248539533b2c186687f9f44963e50de569917a263e` |
| `CHDK/SCRIPTS/TEST/isorm.lua` | 2719 | `8b81a95b5a63ab059f4eed2d468507bc9dfaa921e38fbc2e855ae1d59b834767` |
| `CHDK/SCRIPTS/TEST/llibtst.lua` | 12862 | `1048ca588512687769041c1016ece3ac8158bdc81448002e6fee5ea715dfbcf2` |
| `CHDK/SCRIPTS/TEST/mftest.lua` | 7589 | `a7418e3de9052d83eaf1a079a2f256eac1061c0217845bcd81109f9aed08a2ad` |
| `CHDK/SCRIPTS/TEST/ndtest.lua` | 28646 | `6aab431f3f2daefc8e2ac614e59b7bf9abf47f63f72777a3301f7deca30c559f` |
| `CHDK/SCRIPTS/TEST/paramdmp.lua` | 1147 | `c9319b2d0de508289b9005055cd2bf20cbb99795aa3b1241701f876caefd8e15` |
| `CHDK/SCRIPTS/TEST/parmtest.lua` | 485 | `f3c91eeacffcc9e623af1f195e970bb59e6d3734a7b07f7a018788bb14317edb` |
| `CHDK/SCRIPTS/TEST/rawdraw.lua` | 3583 | `380465e0dccd3264ca1d48df80aa28a7e3a315fe26887c8d47fef22173fba381` |
| `CHDK/SCRIPTS/TEST/romlog.lua` | 1543 | `39d41dc399cf0b07dee1120d861a112a84c57f6112def38c3cc89b6918a2b5e0` |
| `CHDK/SCRIPTS/TEST/setmode.bas` | 963 | `c4433164e5545c71d58ced65c64e75e526ac7f685553382705a80901e32f3abd` |
| `CHDK/SCRIPTS/TEST/setmode.lua` | 5779 | `cfa0fdf839d17d3defad33327e0eb0ed718167f07d939bd2d5162f9340f24e2b` |
| `CHDK/SCRIPTS/TEST/setrec.bas` | 338 | `e7f574f0bb2e3a1dcef2a679ea40f008c89afebf79258a01911f1ca5c6e01bbb` |
| `CHDK/SCRIPTS/TEST/setrec.lua` | 321 | `12774a6c4cb3e8ee5766140c68a692819ba9e3477a4e29eb1d5fc8fb65f8edb6` |
| `CHDK/SCRIPTS/TEST/shothist.lua` | 556 | `2a94e57b1dc9691f7fc7c925b18ec4c1eb970c8fe8e665bc93dda1e6182eddf6` |
| `CHDK/SCRIPTS/TEST/tboxtest.lua` | 344 | `a92f86c6e11d2b5b8dd69b1ef4d4221519057403030f28738a1022ca2b87cd69` |
| `CHDK/SCRIPTS/TEST/tstcallf.lua` | 3610 | `a7280f4e56457211672464501c2167864936851dea87828921db9f9f6234db37` |
| `CHDK/SCRIPTS/TEST/twilight_e.lua` | 9474 | `bcb486a35e7aab61a85a9120cbae45fda6f5066957310bbf8eb55407155efcb0` |
| `CHDK/SCRIPTS/TEST/uartrtst.lua` | 751 | `b43fdf1f7dbe62049bc59d37b7d8480a99ce22d3287795c288c1e4b93702063d` |
| `CHDK/SCRIPTS/TEST/ubtest.bas` | 4221 | `689a8b93f7eb26696f03c7e0ca1360eb3093e448b3c349647afcb83b5771a288` |
| `CHDK/SCRIPTS/TEST/vidtest.lua` | 4794 | `b93c666d3501f72d579af66744f9bc9ec29a8f0de48a30ed8283b8ee4024ec90` |
| `CHDK/SCRIPTS/default.lua` | 6673 | `5f5b8b5bb23f87f6cb4a030b06d482f82bc1d2b92bbc4ac58186322833fbbc2f` |
| `CHDK/SCRIPTS/hdr.bas` | 357 | `ca94701f932754f4b4d7e44183c8676490d7de005d5353864d6ca863b4882c29` |
| `CHDK/SCRIPTS/hdr.lua` | 414 | `87ef37ab19cafd0f6736bca92688d8aa7335c28360ce4fa124bcf93e1bfffdbc` |
| `CHDK/SCRIPTS/interval.bas` | 181 | `b2bb46d21902d6d2f72cc5688e687b76524af0559bcbe8013c7d888a4cd578b2` |
| `CHDK/SCRIPTS/interval.lua` | 213 | `c9e596bb2494e39d8993355c54cc18de85a457fe691b005412920ead0fab703e` |
| `CHDK/SCRIPTS/motion.bas` | 351 | `e5954d8f3ec6cdc9f086042a0d97af407c6c91fb1f8f9ff3436e3d192911258a` |
| `CHDK/SCRIPTS/motion.lua` | 1097 | `a036edee5c6b688a0574dd7a80794d5ea191d712959fcca129f13087de154f9c` |
| `CHDK/SCRIPTS/readme.txt` | 1011 | `f439729831a5bcb71f8d00e1b3f56feec44cc988ad020aa8b4379053cb23ecbc` |
| `CHDK/SCRIPTS/shoot.bas` | 295 | `c6c5c9a22634de4181f2c74bff4b59cc5b4ae6095b57bc1e09e676e035e774ae` |
| `CHDK/SCRIPTS/shoot.lua` | 323 | `d50f36c22628d1bf27b5d0306ae8f0ef39f828cfbda6f957687f50bc3897e144` |
| `CHDK/SYMBOLS/icon_10.rbf` | 7060 | `9ca9aa19f0b9af01d6d9f1ac07c17987fbb759dbc1bdf771475830878820dddc` |
| `CHDK/SYMBOLS/icon_16.rbf` | 12436 | `a7dd6b1d6674e39e05f65225b35952796a38eabdfa158a83ca7eef3375f86960` |
| `CHDK/logo.dat` | 2458 | `4c57c6c5fe2c5a0829517c793f50cf30fcecbabbe946a37a0a8cccf8c288a7ad` |
| `CHDK/logo_de.dat` | 2404 | `dcdeeffc0ec624d277c53b5b79fa4a597a9aab934921f8bbefcf652420fb517b` |
| `CHDK/syscurves.CVF` | 8192 | `bc10cc014cbc7bfb72cea9ee1f66057edf543b97e9c9087368870aefde8023a6` |

### 2. Pre-Trial SD Card Preparation and Backup Checklist

- [ ] **Backup existing `A/CHDK/` folder**: In the PC card reader, copy the entire existing `CHDK/` directory on the SD card to a host backup location before copying any new files:
  ```sh
  cp -a /Volumes/CANON_SD/CHDK /path/to/host/backup/CHDK_pre_port54
  ```
- [ ] **Record baseline SD card file tree**: Record a recursive file listing of all files on the SD card to compare against post-trial file creation:
  ```sh
  cd /Volumes/CANON_SD && find . -type f | sort > /path/to/host/pre_trial_files.txt
  ```
- [ ] **Deploy candidate artifacts**: Copy `DISKBOOT.BIN` and `CHDK/` from `out/port54-conf-save/` onto the SD card root.
- [ ] **Card lock state**: Keep SD card write-protect switch **LOCKED** for camera insertion and trial boot. (Autoboot requires a locked card per `docs/PORT41_FULL_BUILD.md:169`. CHDK clears the software read-only flag itself in `chdk-port/core/kbd_common.c:246`, so configuration writes still work on a locked card. Unlock the card only in the PC card reader, and only if the reader needs that for the backup or restore copy).

### 3. Step-by-Step Trial Protocol

| Step # | Action | Details & Controls | Expected Outcome | What to Record |
|---|---|---|---|---|
| **1** | Short-press boot | Tap `POWER` briefly (< 500 ms) with card locked. | Camera powers on cleanly into live view or playback; stock Canon firmware initializes normally. | Pass / Fail; boot mode (Rec / Play) |
| **2** | Check diag line | Press `WIFI` (`KEY_WIFI`) to enter `<ALT>` mode. | `<ALT>` indicator appears; diagnostic Line 2/3 displays `SAVE:FAIL` or `SAVE:OK` (confirms `SAVE:OFF` inactive). | Pass / Fail; initial `SAVE` marker text |
| **3** | Change ALT-menu setting | Press `MENU` (`KEY_MENU`) to open CHDK menu. Navigate to a visible setting, e.g., *OSD Parameters -> Show OSD* boolean toggle `[ ]` <-> `[*]`, and toggle it. (Note: OSD settings land in `CHDK/OSD__4.CFG`; core settings land in `CHDK/CCHDK4.CFG`). | Highlight moves cleanly; setting updates visibly on screen and in memory (`conf` struct). | Pass / Fail; setting name (*Show OSD*), old value, new value |
| **4** | Save configuration | Press `MENU` (`KEY_MENU`) to exit menu (invoking `conf_save()`), or select *Save Settings Now*. | Menu closes cleanly; diagnostic line immediately displays `SAVE:OK` (or `SAVE:FAIL` if write failed). No freeze or lockup. | Pass / Fail; post-save `SAVE` marker (`SAVE:OK` / `SAVE:FAIL`) |
| **5** | Power off camera | Press `POWER` button to shut down camera. | Camera executes clean shutdown: lens retracts and power LED extinguishes. Wait >= 5 seconds. | Pass / Fail; shutdown clean |
| **6** | Reboot & confirm load | Power on via short-press (< 500 ms) with card locked. Press `WIFI` to enter `<ALT>`, press `MENU` to inspect setting. | Modified setting retains the value set in Step 3 across cold power-cycle, confirming `conf_restore()` successfully loaded `CHDK/OSD__4.CFG`. | Pass / Fail; persisted value confirmed |
| **7** | Check files outside `A/CHDK/` | Power off, remove SD card, insert into host PC (unlock switch only if reader requires it), and generate post-trial file list to compare with baseline: `diff -u pre_trial_files.txt post_trial_files.txt`. | Only `CHDK/OSD__4.CFG` (and standard CHDK internal logs) modified or added. Confirmed strictly zero new or modified files outside `A/CHDK/` (e.g., `DCIM/`, `MISC/`, or root). | Pass / Fail; full file diff |

### 4. What to Record (Trial Observation Table)

| Item | Recorded Observation | Target Verification |
|---|---|---|
| **SAVE marker (initial)** | `SAVE:____` | Diagnostic line shows `SAVE:FAIL` or `SAVE:OK` (verifies `SAVE:OFF` inactive) |
| **Edited setting** | Name: `____`, Old: `____`, New: `____` | Confirms in-RAM setting mutation via menu (e.g., *Show OSD*, lands in `CHDK/OSD__4.CFG`) |
| **SAVE marker (post-save)** | `SAVE:____` | Diagnostic line confirms `SAVE:OK` upon menu exit save |
| **Setting persisted after reboot** | `Yes / No` (Observed value: `____`) | Confirms `conf_restore()` successfully read back saved setting from `CHDK/OSD__4.CFG` |
| **File list differences** | Exact file diff: `____` | Confirms file creation strictly confined to `A/CHDK/` (`CHDK/OSD__4.CFG`); zero files outside `A/CHDK/` |
| **Display / key artifacts** | `None / Describe` | Confirms normal operation without freeze, lag, or graphical anomalies |

### 5. Recovery Procedures

| Scenario | Action | Procedure |
|---|---|---|
| **Camera freeze / hang** | Battery pull | Open battery compartment door, remove battery, wait >= 10 seconds before reinserting. Safely halts CPU and clears volatile SDRAM. |
| **Misbehavior / invalid config** | Conf file removal | In PC card reader (unlock switch only if reader requires it for write access), delete all configuration files written by CHDK (`chdk-port/core/conf.c:632-652`): `A/CHDK/CCHDK4.CFG` (core), `A/CHDK/OSD__4.CFG` (OSD, including *Show OSD*), `A/CHDK/UMENU4.CFG` (user menu), and `A/CHDK/GPS__4.CFG` (GPS). Deleting all of them returns CHDK to default settings. |
| **Corrupted `CHDK/` folder** | Restore backup folder | In PC card reader: delete `A/CHDK/`, then copy the backup folder back and rename it to `A/CHDK/` (or copy the backup's contents into a fresh `A/CHDK/`). Do not leave it as `CHDK_pre_port54/`. |
| **Bypass CHDK autoboot** | Unlock SD card switch | Slide the SD card write-protect switch to **UNLOCKED** (or delete `DISKBOOT.BIN`). An unlocked card bypasses DISKBOOT autoboot and boots factory Canon firmware directly; a locked card is required for autoboot. (Note: unlock the card only in the PC card reader, and only if the reader needs that for the backup or restore copy). |
