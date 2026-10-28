# Ranma GM1.10E Patch Engineering Gap Analysis

**Worker**: G9 (Ranma Source Engineering Analysis)  
**Coordinator**: Gemini Coordinator  
**Tech Lead**: ChatGPT  
**Date**: 2026-10-28  
**Status**: **`RESEARCH_COMPLETE / FOR_REVIEW`**  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Read-Only Investigation)

---

## 1. Executive Summary & Provenance Baseline

This report supersedes repetitive forum retrieval archaeology and addresses concrete engineering gaps between Ranma's historical `g3x_110e.patch` and our current GM1.10C prototype.

### Provenance & Prior Knowledge Context
- **Prior Recovery**: The patch `g3x_110e.patch` (336,714 B; CRLF/LF mixed unified diff; SVN base r5480) was originally retrieved, verified against post 143437 of CHDK forum thread 12600, and documented on **2026-10-25** in `docs/PORT5A_RANMA_PORT_RECOVERY.md` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`.
- **Integrity Notice**: The SHA-256 digest (`55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba`) is an empirical local file checksum; the CHDK forum software does not provide cryptographic digests.
- **Scope Mandate**: Phase 0 read-only. Zero boot code modification; zero firmware builds or execution.

---

## 2. Concrete Engineering Gaps Not Covered by PORT-5B

### 2.1 Memory Placement & Heap Relocation (`MEMISOSTART`)
*Source References*: `platform/g3x/makefile.inc:25–38`, `platform/g3x/notes.txt:39–65`.

1. **Rejection of Automatic Sigfinder ARAM Address**:  
   The CHDK `finsig_thumb2` signature finder identified an apparent ARAM heap start at `0x006CE000` (size `0x22000`, 136 KiB, from `0xFC55888E`). Ranma **explicitly rejected** this automatic value:
   ```makefile
   ## values from sig finder
   #ARAM_HEAP_START = 0x006ce000 # Found @0xfc5588b4
   #ARAM_HEAP_SIZE  = 0x00022000 # Found @0xfc55888e

   ARAM_HEAP_START = 0x00c80000
   ARAM_HEAP_SIZE  = 0x00180000
   override OPT_ARAM_MALLOC=1
   override OPT_CHDK_IN_ARAM=1
   MEMISOSTART = $(ARAM_HEAP_START) # 0x00C80000
   ```
2. **Engineering Rationale**:  
   - 136 KiB at `0x006CE000` was marginal for the CHDK core binary.
   - Crucially, `AdditionAgent.c` actively reads up to `0x22000` bytes from storage into `0x006CE000`, causing memory corruption.
   - Ranma relocated `MEMISOSTART` to high DRAM at **`0x00C80000`** (12.5 MiB into DRAM), carving out a 1.5 MiB (`0x00180000`) isolated heap.
3. **Relevance to GM1.10C**:  
   Our GM1.10C prototype must not rely on `0x006CE000`. High DRAM placement (`0x00C80000` or above) provides safe isolation from stock DMA regions and heap allocators.

---

### 2.2 Task Hook Mechanics & Filtering Set
*Source References*: `platform/g3x/sub/110e/boot.c:130–248`, `platform/g3x/sub/110e/stubs_entry.S`.

1. **RAM Trampoline Installation**:  
   Ranma installed a direct Thumb-2 jump patch into firmware RAM at `hook_CreateTask` (`0xBFE14A40` / `0xBFE14A3C` area):
   ```armasm
   patch_CreateTask:
       ldr.w   pc, [pc, #0]
       .long   CreateTask_my + 1  ; Thumb entry
   ```
2. **Hook Filtering Logic (`CreateTask_my`)**:  
   `CreateTask_my` intercepted calls to `CreateTask` and checked the function pointer in `r0`:
   - `task_PhySw` (`0xFC1283AD`): Substituted with `mykbd_task` (defined in `platform/g3x/kbd.c`).
   - `task_InitFileModules` (`0xFC0BD071`): Substituted with `init_file_modules_task_my`.
   - `task_FileWrite` (`0xFC25F3CF`): Substituted with `task_FileWrite_my` (`platform/g3x/sub/110e/filewrite.c`) for remote PTP capture.
   - `task_TricInitTask` (`0xFC4E4B41`): Substituted with `task_TricInitTask_my` (required for FI2 boot to avoid video core collisions).
   - *Commented Out / Deferred*: `task_CaptSeq`, `task_ExpDrv`, `task_DvlpSeq`, `task_MovieRecord`, `task_TskCocoa0` were left stock.
3. **Continuation**:  
   Non-intercepted tasks continue execution by jumping to `hook_CreateTask + 8 + 1` in firmware.

---

### 2.3 Startup Ordering & SpyTask Insertion Point
*Source References*: `platform/g3x/sub/110e/boot.c:403–490`.

1. **Startup Task Replacement (`task_Startup_my`)**:  
   Ranma intercepted `taskcreate_startup` (`sub_fc05b963_my`) to redirect `task_Startup` to `task_Startup_my`.
2. **Omission of Stock DISKBOOT Loader**:  
   In `task_Startup_my`, Ranma commented out `bl sub_fc05bbea` (`startdiskboot`). This prevented the camera from attempting a secondary diskboot cycle during warm startup.
3. **Exact SpyTask Insertion Timing**:  
   Rather than launching `SpyTask` immediately, Ranma permitted 19 stock subroutines to run (initializing clock, GPIOs, HWIC/OC, ADC, error logging, UI memory, `taskcreate_physw`, and battery monitoring).  
   `CreateTask_spytask` was invoked at line 484:
   ```c
   CreateTask_spytask(); // _CreateTask("SpyTask", 0x19, 0x2000, spytask, 0);
   ```
   Immediately following `CreateTask_spytask`, `task_Startup_my` tail-branched to stock `sub_fc0d0126` (`MLHClock`).

---

### 2.4 Power-On Handler Failure & Workaround
*Source References*: `platform/g3x/sub/110e/boot.c:406–428`, `platform/g3x/notes.txt:18–35`.

1. **Breakage of Stock `sub_fc1284ac`**:  
   Ranma's developer notes record:
   ```text
   // TODO: Find out why the default handler in sub_fc1284ac is broken.
   // See sub_fc08ecbc
   ```
   In stock firmware, `sub_fc1284ac` reads GPIO registers to determine why the camera turned on (power button, playback button, USB insertion, or error condition). Ranma observed that calling this handler under custom boot triggered immediate shutdown or bootlooping.
2. **Applied Workaround**:  
   Ranma completely commented out three stock calls in `sub_fc05b963_my`:
   - `// bl sub_fc079404` (`IsNormalCameraMode_FW`)
   - `// bl sub_fc1284ac` (GPIO power-on cause evaluator)
   - `// bl sub_fc05ba56` (sets GPIO `0x67` / `0xD20B019C`, error power-off trigger)
3. **Invalidation of Legacy CHDK Magic Word**:  
   Ranma explicitly noted: `"0x12345678 @ 0x4ffc trick doesn't seem to help with this model for power-on handling."` The standard DIGIC 4/5 method of setting `*(0x4FFC) = 0x12345678` to force Playback mode is ineffective on DIGIC 6 G3 X.
4. **Documented Power GPIOs**:  
   - `0x02` (`0xD20B0008`): Mystery power-up status register.
   - `0x67` (`0xD20B019C`): Cleared on power-up error condition.
   - `0x88` (`0xD20B0220`): Wi-Fi button.
   - `0x97` (`0xD20B025C`): Power button.
   - `0x98` (`0xD20B0260`): Play button.

---

### 2.5 Filesystem Readiness Handshake (`spytask_can_start`)
*Source References*: `platform/g3x/sub/110e/boot.c:493–515`.

1. **Stock Task Replacement**:  
   `task_InitFileModules` (`0xFC0BD071`) executes a tight sequence of two initialization functions:
   - `sub_fc0d9ccc` (lower-level storage/host driver init)
   - `sub_fc0d9cf6` (filesystem mount completion and event dispatcher)
2. **Synchronization Handshake**:  
   Ranma's cloned `init_file_modules_task_my` inserted `bl core_spytask_can_start` immediately after `sub_fc0d9cf6`:
   ```armasm
   bl      sub_fc0d9ccc
   bl      sub_fc0d9cf6
   bl      core_spytask_can_start   ; Sets spytask_can_start = 1
   ```
3. **SpyTask Release**:  
   `SpyTask` is created early in `task_Startup_my`, but spins waiting on `spytask_can_start`. Once `init_file_modules_task_my` reaches `core_spytask_can_start`, `SpyTask` exits its spin-wait and begins loading fonts, configs, and scripts from the SD card.

---

## 3. Comparative Gap Matrix: Ranma 1.10E vs GM1.10C Prototype

| Domain | Ranma GM1.10E Approach | Current GM1.10C Prototype State | Engineering Action for GM1.10C |
|---|---|---|---|
| **Memory Placement** | Relocated to high DRAM `0x00C80000` (1.5 MiB heap); bypassed `0x006CE000` | Prototype BSS/Data currently linked in low memory; high DRAM unreserved | Adopt high DRAM placement (`0x00C80000`+) to prevent `AdditionAgent` / DMA stomping. |
| **Power-On GPIOs** | Bypassed `sub_fc1284ac` and `sub_fc05ba56` to prevent shutdown loop | Prototype mirrors stock boot calls; GPIO error handling unmapped | Audit `sub_fc1284ac` on GM1.10C to evaluate whether power-on bypass is required. |
| **Startup Ordering** | Disabled `startdiskboot` (`sub_fc05bbea`); deferred `SpyTask` to end of `task_Startup` | Prototype comments out `CreateTask_spytask` in `task_Startup_my` | Maintain `SpyTask` disabled until display and file modules are verified. |
| **Filesystem Readiness** | Cloned `task_InitFileModules` inserting `core_spytask_can_start` after `sub_fc0d9cf6` | U2 entry verified (`0xFC0BD071`); completion semantics still marked `UNKNOWN` | Verify whether `sub_fc0d9cf6` return guarantees FAT32 mount readiness before signaling. |
| **Task Interception** | Patched RAM `hook_CreateTask` with Thumb-2 `ldr.w pc, [pc, #0]` | Offline contract model verifies `check_trace()` and single-hook rules | Enforce fail-closed model; do not install RAM patches until all preconditions pass. |

---

## 4. Conclusion & Strict Safety Compliance

- Zero code was modified in `chdk-port/platform/g3x/`.
- No raw ROM scans were performed.
- All findings are referenced directly to lines of `g3x_110e.patch` and existing tracked documentation.
