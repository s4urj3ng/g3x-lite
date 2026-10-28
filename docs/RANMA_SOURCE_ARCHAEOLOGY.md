# Ranma GM1.10E Patch Engineering Gap Analysis & Memory Architecture Comparison

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
- **Classification Mandate**: High DRAM placement (`0x00C80000`) is strictly categorized as a **`HISTORICAL_DESIGN_CANDIDATE`**. It is NOT proven safe for GM1.10C without dedicated memory collision analysis.
- **Runtime Precondition Invariant**: U2 (`init_file_modules_entry_verified` / filesystem mount completion) and U4 (`SpyTask` placement and priority) remain strictly **`UNKNOWN`** in the runtime safety model.
- **Scope Mandate**: Phase 0 read-only. Zero boot code modification; zero firmware builds or execution.

---

## 2. In-Depth Memory Architecture Comparison

### 2.1 Low-Heap Relocation (Our Prototype) vs. High-DRAM Relocation (Ranma)

| Dimension | Low-Heap Relocation (GM1.10C Prototype) | High-DRAM Relocation (Ranma GM1.10E) | Status / Evidence Basis |
|---|---|---|---|
| **Placement Target** | Pre-heap / low DRAM linked via `boot_prototype.c` | High DRAM `0x00C80000` (1.5 MiB heap, `MEMISOSTART = 0x00C80000`) | **`HISTORICAL_DESIGN_CANDIDATE`** (`platform/g3x/makefile.inc:29–37`) |
| **Sigfinder ARAM (`0x006CE000`)** | Disqualified: `AdditionAgent.c` reads up to `0x22000` B into `0x006CE000` | **Explicitly rejected by Ranma**: commented out auto-sigfinder values | **`VERIFIED_IN_EXISTING_DOCS`** (`docs/PROJECT_STATE.md`, `platform/g3x/makefile.inc:25–28`) |
| **Heap Interaction** | Directly truncates or pre-allocates before default DryOS heap (`0x003489B4`) | Relocates CHDK entirely outside stock DryOS main heap (`0x003489B4..0x006CDFFF`) | **`HISTORICAL_CANDIDATE`** (`platform/g3x/notes.txt:41–43`) |
| **Secondary Core Conflict** | Low RAM avoids secondary core range | Bypasses OMAR secondary core RAM area (`0x00700000..0x00760000`) | **`HISTORICAL_CANDIDATE`** (`platform/g3x/notes.txt:45–46`) |
| **Safety on GM1.10C** | Bounded offline; verified by contract tests | **UNPROVEN on GM1.10C**: potential DMA / sensor buffer collisions | **`UNKNOWN`** |

### 2.2 Known Source Evidence for Memory Ownership
From tracked repository documentation and Ranma's `notes.txt`:
1. **Default DryOS Heap Range**:
   - Heap Start: `0x003489B4`
   - Heap End: `0x006CDFFF` (approximately 3.5 MiB main system heap).
2. **`AdditionAgent` Conflict Area**:
   - `0x006CE000..0x006FFFFF`: Although flagged by signature finders as candidate ARAM, `AdditionAgent.c` (`0xFC55888C..0xFC5588C0`) actively performs file reads of up to `0x22000` bytes into `0x006CE000` / `0x406CE000` via `Fread_Fut`. Writing payload data here corrupts storage operations.
3. **OMAR Secondary Core DRAM Region**:
   - `0x00700000..0x00760000`: Dedicated communication and staging memory for the secondary Cortex-R4 / image processing core (*Omar*).
4. **Firmware RAM Code Mirror**:
   - `0x010E1000..0x01107D00`: Region where boot code copies Flash ROM routines into executable DRAM.
5. **Sensor Raw & Video DMA**:
   - Sensor raw DMA buffers dynamically map into upper DRAM (e.g. `0x43DBFCA0`).

### 2.3 Unknown Risks: DMA, Xtensa/Tric, Allocators, and Overlaps
While Ranma's choice of `0x00C80000` avoided the low `AdditionAgent` collision and OMAR core space, it introduces substantial **unverified risks on GM1.10C**:
1. **Sensor RAW / Live View Framebuffer Overlap**:
   Compact cameras with large 1-inch sensors require massive circular DMA buffers for 20.2 MP raw frames (~35 MiB per raw frame) and multi-frame noise reduction. Whether `0x00C80000..0x00DFFFFF` overlaps with raw capture buffers or video ringbuffers on GM1.10C is **`UNKNOWN`**.
2. **Xtensa / Tric Codec Core RAM Allocation**:
   The audio/video codec coprocessor (Tric / avcore) loads firmware blobs into uncached RAM. In `platform/g3x/notes.txt:77–88`, Ranma noted that on SX280 this area starts at `0x00E00000`. If the G3 X Tric core allocates starting near `0x00C00000..0x00E00000`, placing CHDK at `0x00C80000` risks silent memory stomping during video capture or audio playback.
3. **EXMEM Dynamic Allocator Collisions**:
   DryOS r57 features dynamic EXMEM chunk allocation. Whether DryOS pools claim high DRAM dynamically after boot remains unmapped.

### 2.4 Offline Verification vs. Future Authorized Scope

#### What CAN Be Checked Completely Offline (Existing Documents)
1. **DryOS Heap End Descriptors**: Inspecting tracked heap bounds (`0x003489B4` through `0x006CDFFF`) in `docs/PORT1B_HEAP_PROOF.md`.
2. **Linker Script Verification**: Verifying that our prototype linker script does not emit sections overlapping known ATCM (`0xBFE10000`), BTCM (`0x00000000`), or copied code (`0x010E1000`).
3. **Disassembly of `AdditionAgent.c`**: Reviewing existing documentation in `docs/HANDOFF.md` regarding `0x006CE000`.

#### What Requires Future Separately Authorized Verification (Phase 1+)
1. **Sensor DMA Buffer Table Inspection**: Bounded read-only inspection of GM1.10C capture buffer initialization tables to determine the true upper DRAM boundary.
2. **Tric / Avcore RAM Base Allocation**: Locating `sub_fc4e4b41` (`task_TricInitTask`) in GM1.10C ROM to establish the exact memory range used for audio/video codec firmware blobs.
3. **Dynamic Memory Allocation Tracing**: Evaluating runtime EXMEM pool bounds via non-invasive post-boot diagnostic tools (`witness_inspector_gm110c.m` or Canon Basic).

---

## 3. Concrete Engineering Gaps Not Covered by PORT-5B

### 3.1 Task Hook Mechanics & Filtering Set
*Source References*: `platform/g3x/sub/110e/boot.c:130–248`.

1. **RAM Trampoline Installation**:  
   Ranma installed a direct Thumb-2 jump patch into firmware RAM at `hook_CreateTask` (`0xBFE14A40` / `0xBFE14A3C` area):
   ```armasm
   patch_CreateTask:
       ldr.w   pc, [pc, #0]
       .long   CreateTask_my + 1  ; Thumb entry
   ```
2. **Hook Filtering Logic (`CreateTask_my`)**:  
   `CreateTask_my` intercepted calls to `CreateTask` and checked the function pointer in `r0`:
   - `task_PhySw` (`0xFC1283AD`): Substituted with `mykbd_task`.
   - `task_InitFileModules` (`0xFC0BD071`): Substituted with `init_file_modules_task_my`.
   - `task_FileWrite` (`0xFC25F3CF`): Substituted with `task_FileWrite_my` (`platform/g3x/sub/110e/filewrite.c`) for remote PTP capture.
   - `task_TricInitTask` (`0xFC4E4B41`): Substituted with `task_TricInitTask_my` (required for FI2 boot to avoid video core collisions).
   - *Commented Out / Deferred*: `task_CaptSeq`, `task_ExpDrv`, `task_DvlpSeq`, `task_MovieRecord`, `task_TskCocoa0` were left stock.

---

### 3.2 Startup Ordering & SpyTask Insertion Point
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
4. **Current Status on GM1.10C (U4)**:  
   On GM1.10C, the optimal insertion point, priority, and stack size for `SpyTask` remain **`UNKNOWN`**. Launching `SpyTask` prematurely before display and filesystem subsystems are online results in unhandled panics.

---

### 3.3 Power-On Handler Failure & Workaround
*Source References*: `platform/g3x/sub/110e/boot.c:406–428`, `platform/g3x/notes.txt:18–35`.

1. **Breakage of Stock `sub_fc1284ac`**:  
   In stock firmware, `sub_fc1284ac` reads GPIO registers to determine why the camera turned on (power button, playback button, USB insertion, or error condition). Ranma observed that calling this handler under custom boot triggered immediate shutdown or bootlooping.
2. **Applied Workaround**:  
   Ranma completely commented out three stock calls in `sub_fc05b963_my`:
   - `// bl sub_fc079404` (`IsNormalCameraMode_FW`)
   - `// bl sub_fc1284ac` (GPIO power-on cause evaluator)
   - `// bl sub_fc05ba56` (sets GPIO `0x67` / `0xD20B019C`, error power-off trigger)
3. **Invalidation of Legacy CHDK Magic Word**:  
   Ranma explicitly noted: `"0x12345678 @ 0x4ffc trick doesn't seem to help with this model for power-on handling."` Setting `*(0x4FFC) = 0x12345678` to force Playback mode is ineffective on DIGIC 6 G3 X.
4. **Documented Power GPIOs**:  
   - `0x02` (`0xD20B0008`): Mystery power-up status register.
   - `0x67` (`0xD20B019C`): Cleared on power-up error condition.
   - `0x88` (`0xD20B0220`): Wi-Fi button.
   - `0x97` (`0xD20B025C`): Power button.
   - `0x98` (`0xD20B0260`): Play button.

---

### 3.4 Filesystem Readiness Handshake (`spytask_can_start`)
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
3. **Current Status on GM1.10C (U2)**:  
   While the entry point `0xFC0BD071` is statically verified, whether the return of `sub_fc0d9cf6` guarantees complete FAT32 mount readiness without race conditions remains **`UNKNOWN`**. The readiness gate in our runtime model remains fail-closed.

---

## 4. Comparative Gap Matrix: Ranma 1.10E vs GM1.10C Prototype

| Domain | Ranma GM1.10E Approach | Current GM1.10C Prototype State | Evaluation & Future Verification Requirement |
|---|---|---|---|
| **Memory Placement** | Relocated to high DRAM `0x00C80000` (1.5 MiB heap); rejected `0x006CE000` | Prototype BSS/Data linked in low DRAM; high DRAM unreserved | **`HISTORICAL_DESIGN_CANDIDATE`**. Unproven safe on GM1.10C; requires bounded capture buffer mapping. |
| **Power-On GPIOs** | Bypassed `sub_fc1284ac` and `sub_fc05ba56` to prevent shutdown loop | Prototype mirrors stock boot calls; GPIO error handling unmapped | **`UNKNOWN`** on GM1.10C. Requires offline disassembly of `sub_fc1284ac`. |
| **Startup Ordering** | Disabled `startdiskboot` (`sub_fc05bbea`); deferred `SpyTask` to end of `task_Startup` | Prototype comments out `CreateTask_spytask` in `task_Startup_my` | **`UNKNOWN`** (U4). Defer `SpyTask` creation until display and filesystem are verified. |
| **Filesystem Readiness** | Cloned `task_InitFileModules` inserting `core_spytask_can_start` after `sub_fc0d9cf6` | U2 entry verified (`0xFC0BD071`); completion semantics marked `UNKNOWN` | **`UNKNOWN`** (U2). Requires proving mount completion before releasing latch. |
| **Task Interception** | Patched RAM `hook_CreateTask` with Thumb-2 `ldr.w pc, [pc, #0]` | Offline contract model verifies `check_trace()` and single-hook rules | Enforce fail-closed model; no RAM patching permitted in Phase 0. |

---

## 5. Conclusion & Strict Safety Compliance

- Zero code was modified in `chdk-port/platform/g3x/`.
- No raw ROM scans were performed.
- High DRAM placement is explicitly demoted to `HISTORICAL_DESIGN_CANDIDATE`.
- U2 and U4 runtime preconditions remain strictly `UNKNOWN`.
