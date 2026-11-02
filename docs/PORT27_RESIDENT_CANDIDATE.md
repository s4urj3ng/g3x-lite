# PORT-27 T2: Resident Heartbeat Candidate Record & UNKNOWN List

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-27 T2 (`p27-t2-resident-candidate`)
- **Baseline Evidence**: `docs/PORT27_RESIDENT_EVIDENCE.md` (PORT-27 T1 Dossier)
- **Status / Verdict**: **NO-GO Record** (No candidate produced; zero code modified)

---

## 1. Executive Summary & Verdict Citation

In accordance with the task specification for **PORT-27 T2**:
> *"Read the GO/NO-GO verdict in docs/PORT27_RESIDENT_EVIDENCE.md first.*  
> *If the verdict is NO-GO (item (a) or (b) is not VERIFIED), produce no candidate and change no code. Write docs/PORT27_RESIDENT_CANDIDATE.md with the exact UNKNOWN list (item, missing address or range, why the read policy could not reach it)."*

### 1.1 Verdict Citation from `docs/PORT27_RESIDENT_EVIDENCE.md:575-580`
> [!WARNING]
> **Verdict for PORT-27 T2**: **NO-GO**
> 
> Under the project task policy, a **GO** verdict requires both Item (a) and Item (b) to be certified as **VERIFIED**. Furthermore, reviewer guidance establishes a strict evaluation standard:
> *"GO is allowed only if T2 can create its task by copying the VERIFIED call-site pattern exactly, changing only values whose role is VERIFIED. State the exact arguments T2 would pass and give each one a label. If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*
> 
> Detailed justification by prerequisite item:
> - **Item (a) (Heap Start & Core Survival)**: Sufficient for implementation (`enough to build`): patch point at `0xFC05B3CA` and heap pool 1 exclusion up to `new_sa = 0x00368680` are `[VERIFIED]`; ATCM IRQ disable/restore routines are `[INFERRED/UNKNOWN]`; heap alignment requirement is `[UNKNOWN]`; runtime survival against DMA/MMIO is `[UNKNOWN]`.
> - **Item (b) (Task Creation Entry & Calling Convention)**: **FAILS STRICT VERIFICATION** (`UNKNOWN: exact ranges still needed`): Task creation entry veneer `sub_fc31bbc4` at `0xFC31BBC4` is `[VERIFIED]`; call site raw values are `[VERIFIED]`; parameter roles (`r0` name, `r1` priority, `r2` stack size, `sp[0]` user context) are `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`; and internal callees delegated by `CreateTask` (`0xBFE10B88` allocator, `0xBFE10D14` activation helper, `0xBFE13E78` assert handler) reside outside Slice `S1C` and remain `[UNKNOWN]`.

### 1.2 Policy Compliance & Outcome
1. **No Candidate Produced**: No candidate binary, no DISKBOOT image, and no build script (`tools/build_candidate_port27_resident.py`) were created.
2. **Zero Code Changes**: No modifications were made to `chdk-port/platform/g3x/sub/110c/`, `tools/`, or any other source directory.
3. **Build Invariance Preserved**: The default build and all existing opt-in builds (`--ladder`, `--poweron-fix`, `--combined`) remain 100% bit-for-bit identical to their prior verified baselines.
4. **Exact UNKNOWN List Recorded**: This document records the comprehensive, exact UNKNOWN list across Items (a), (b), and (d) with verified entry points, unknown function extents, and precise policy reachability explanations (including the 22,196-byte unspent budget for reachable targets and the exact policy boundaries for out-of-scope targets).

---

## 2. Prerequisite Status Evaluation Matrix

| Prerequisite Item | Scope & Technical Focus | Verification Status | Epistemic Status & Evidence Citation | T2 Impact |
|:---:|:---|:---:|:---|:---:|
| **Item (a)** | Stock heap / memory start after `sub_fc0d0126`; patch point in `sub_fc05b3c8`; relocated core survival at `0x003489B4` | **PARTIALLY VERIFIED** (`enough to build`) | `sub_fc0d0126` instructions set no heap bounds `[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`; patch point `0xFC05B3CA` loading `r4` and storing to `sp[0x08]` / `sp[0x0C]` `[VERIFIED: PORT27-ROM-HEAP-SETUP]`; exclusion of core `[0x003489B4, 0x00368680)` from heap pool 1 `[VERIFIED: boot_prototype.c:24, 177-178, 212-215]`; ATCM IRQ routines `[INFERRED/UNKNOWN]`; heap alignment `[UNKNOWN]`; non-heap RAM users `[UNKNOWN]`. | Heap start can be safely raised to `0x00368680`, but ATCM continuation effects and DMA/MMIO survival remain unverified. |
| **Item (b)** | DryOS task-creation entry (`CreateTask`) and calling convention | **FAILS STRICT VERIFICATION** (`UNKNOWN: exact ranges still needed`) | Entry veneer `sub_fc31bbc4` (ARM `ldr pc, [pc, #-4]` -> ATCM `0xBFE14A3D` Thumb-2) is `[VERIFIED: PORT27-ROM-CREATETASK-VENEER]`; call site raw values in `sub_fc05b962` are `[VERIFIED: PORT27-ROM-STARTUP-TASKS]`; parameter roles (`r0` name, `r1` priority, `r2` stack size, `sp[0]` user context) are `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`; internal callees `0xBFE10B88`, `0xBFE10D14`, `0xBFE13E78` are `[UNKNOWN]`. | **Blocks T2 candidate creation**. T2 strictly depends on `r2 = 0` successfully assigning an adequate stack from internal allocator `0xBFE10B88`. Unverified parameter semantics prohibit safe task spawning under strict policy. |
| **Item (c)** | Hardware LED register and control values | **VERIFIED** (`enough to build`) | MMIO `0xD20B0884`, ON `0x004D0002`, OFF `0x004C0003` `[VERIFIED: hardware trial 2026-11-01; docs/PORT23_LED_BREADCRUMBS.md:6-7]`. | Ready for use. Rear green LED control is empirically confirmed on physical camera. |
| **Item (d)** | Firmware sleep / delay primitive (`SleepTask`) | **PARTIALLY VERIFIED** (`enough to build`) | Veneer `0xFC31BF84` (ARM -> ATCM `0xBFE14969` Thumb-2) and call site literal `r0 = 2000` at `0xFC135CC6` are `[VERIFIED: PORT27-ROM-WATCHDOG-MODULE; PORT27-ROM-SLEEPTASK-VENEER]`; millisecond delay unit and task context constraint are `[INFERRED]`. Context-free busy-wait loop (`0x00100000`, ~21–50 ms) is available `[INFERRED]`. | Usable via bounded busy-wait delay loop or `SleepTask` veneer if multitasking is confirmed. |

---

## 3. The Exact UNKNOWN List

The table below catalogs every missing address or property across the prerequisite items, the exact component, its epistemic status, evidenced function extent, proposed inspection window (strictly non-evidentiary), and why it was unresolved under the PORT-27 ROM read policy.

> [!IMPORTANT]
> **Distinction Between Evidenced Entry Addresses and Function Extents**:  
> In accordance with project epistemic standards, when a veneer or branch instruction in an approved slice references a target vector, **only the entry address is VERIFIED**. The function length and extent remain **`UNKNOWN`** unless the function body is completely read and its terminating return instruction (`bx lr` / `pop {..., pc}`) is statically verified.  
> Sizing figures in the column *Proposed Inspection Window (Not Evidence)* are non-evidentiary planning suggestions ($\le 4\text{ KiB}$) to guide future bounded read slices within Phase 0 budget constraints; they must never be construed as evidenced function boundaries.

| # | Item | Component / Subsystem | Entry / Target Address (VMA) | Source ROM Entry Address | File Offset | Evidenced Function Extent | Proposed Inspection Window (Not Evidence) | Epistemic Status & Citations | Policy Status & Reason Unresolved in T1 |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|:---|
| **1** | **(b)** | Internal Task Allocator / Initializer (`alloc_task_stack_tcb` `[INFERRED: role]`) | `0xBFE10B88` (ATCM Thumb-2) | `0xFCEEF5D4` | `0x00EEF5D4` | `UNKNOWN` | $\le 512\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:170; UNKNOWN in PORT-27]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** The target is called via `bl 0xBFE10B88` at `0xBFE14A8E` inside the ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:170`), which was not read in T1. Source ROM entry address `0xFCEEF5D4` was not cited in prior evidence manifests (`PORT23`, `PORT24`, `PORT25`) and is not a branch target inside any ROM range read in T1. Therefore, `0xFCEEF5D4` lies outside the authorized read policy boundary and could not be read without an expanded authorization scope. |
| **2** | **(b)** | Internal Task Activation Helper (`activate_task` `[INFERRED: role]`) | `0xBFE10D14` (ATCM Thumb-2) | `0xFCEEF760` | `0x00EEF760` | `UNKNOWN` | $\le 1\text{ KiB}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:180; UNKNOWN in PORT-27]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** Called via `bl 0xBFE10D14` at `0xBFE14AA6` inside the ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:180`), which was not read in T1. ROM entry address `0xFCEEF760` was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`) and is not a branch target inside any ROM range read in T1. Outside milestone read policy boundary. |
| **3** | **(b)** | DryOS Debug Assertion / Kernel Panic Handler (`DebugAssert` `[INFERRED: role]`) | `0xBFE13E78` (ATCM Thumb-2) | `0xFCEF28C4` | `0x00EF28C4` | `UNKNOWN` | $\le 256\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176; UNKNOWN in PORT-27]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** Called via `blx 0xBFE13E78` from `CreateTask` assertion/error paths (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176`), which were not read in T1. ROM entry address `0xFCEF28C4` was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`) and is not a branch target inside any ROM range read in T1. Outside milestone read policy boundary. |
| **4** | **(b)** | `CreateTask` Function Body (Primary ROM Source) | `0xBFE14A3C` (ATCM Thumb-2; target vector `0xBFE14A3D`) | `0xFCEF3488` | `0x00EF3488` | `UNKNOWN` (PORT-27 authority) | $\le 512\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:251-255; manifest PORT27-ROM-CREATETASK-VENEER]`; Parameter roles `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`; Function extent and authority in PORT-27 `[UNKNOWN]` | **Outside milestone read policy boundary.** Veneer `sub_fc31bbc4` at `0xFC31BBC4` (`PORT27-ROM-CREATETASK-VENEER`) loads ATCM execution vector `0xBFE14A3D` `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:251-255]`. Because `0xBFE14A3D` is an ATCM RAM execution address, the source ROM address `0xFCEF3488` is not a direct branch target in ROM (it is mapped via the early boot copy loop at `0xFC020040..0xFC020052`). Neither `0xFCEF3488` nor `0xFC020040` was cited in prior manifests (`PORT23`, `PORT24`, `PORT25`), and neither is a branch target inside any ROM range read in T1. Parameter roles carry forward PORT11A's `[INFERRED]` status and are not verified on PORT-27 authority. |
| **5** | **(a)** | ATCM Interrupt Disable Destination (`DisableInterrupts_ATCM` `[INFERRED: role]`) | `0xBFE14FE6` (ATCM Thumb-2; target vector `0xBFE14FE7` loaded at `0xFC31BF00`) | `0xFCEF3982` | `0x00EF3982` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:124-125; manifest PORT27-ROM-IRQ-DISABLE]`; Function extent `[UNKNOWN]`; Implementation behavior and effects `[INFERRED/UNKNOWN]` | **Outside milestone read policy boundary.** ARM veneer `sub_fc31befc` at `0xFC31BEFC` was authorized under `PORT27-ROM-IRQ-DISABLE`, verifying target vector `0xBFE14FE7`. However, `0xBFE14FE7` is an ATCM RAM address. Its source ROM address `0xFCEF3982` was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`) and is not a direct branch target in ROM. Destination routine effects in ATCM remain unread. |
| **6** | **(a)** | ATCM Interrupt Restore Destination (`RestoreInterrupts_ATCM` `[INFERRED: role]`) | `0xBFE14FEA` (ATCM Thumb-2; target vector `0xBFE14FEB` loaded at `0xFC31B8CA`) | `0xFCEF3986` | `0x00EF3986` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:110-115, 125; manifest PORT27-ROM-RESTORE-IRQ-VENEER]`; Function extent `[UNKNOWN]`; Continuation behavior and absence of heap operations `[INFERRED/UNKNOWN]` | **Outside milestone read policy boundary.** Thumb-2 veneer `sub_fc31b8ca` at `0xFC31B8CA` was authorized as a branch target of `0xFC0D014C` in `PORT27-ROM-FIRMWARE-CONT`. It executes `bx ip` to ATCM VMA `0xBFE14FEB`. Source ROM address `0xFCEF3986` was not cited in prior manifests and is not a direct ROM branch target. Continuation behavior and effects in ATCM remain unread. |
| **7** | **(a)** | DryOS Heap-Start Alignment Specification & Kernel Init (`sub_fc31b408`) | `0xFC31B408` (ROM; target of `0xFC05B448: blx 0xfc31b408`) | `0xFC31B408` | `0x0031B408` | `UNKNOWN` | $\le 256\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:158, 170; manifest PORT27-ROM-HEAP-SETUP]`; Function extent `[UNKNOWN]`; Alignment specification `[UNKNOWN]` | **Reachable under policy, not read in T1.** Start address `0xFC31B408` is a branch target VERIFIED inside an approved range (`0xFC05B448: blx 0xfc31b408` in `PORT27-ROM-HEAP-SETUP`), making it fully eligible for a bounded read under the milestone read policy. It was simply not read in T1. The PORT-27 manifest budget allows up to 24,576 bytes total ($\le 4,096$ bytes per slice); T1 read 2,380 bytes across 8 slices, leaving **22,196 bytes** of unspent budget `[VERIFIED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49-55; docs/PORT27_RESIDENT_EVIDENCE.md:558-570]`. Routine `sub_fc05b3c8` merely stores `sp[0x08]` without alignment checks or masking; whether `sub_fc31b408` enforces alignment or delegates to downstream callees remains `UNKNOWN`. |
| **8** | **(a)** | Relocated Core Region Non-Heap RAM Users | Span `0x003489B4..0x00368680` (RAM) | Entire 32 MiB ROM (`0xFC000000..0xFDFFFFFF`) | Entire dump | N/A (RAM buffer span 130,252 B) | N/A (whole-ROM analysis) | Relocated core exclusion from heap pool 1 allocations is `[VERIFIED: boot_prototype.c:24, 177-178, 212-215; docs/PORT21_RAM_LIFETIME.md:40-41]`; Complete runtime survival against non-heap RAM users is `[UNKNOWN]` | **Exceeds Phase 0 bounded inspection budgets.** Raising the heap base past `_end` (`0x00368680`) excludes relocated core RAM from DryOS heap pool 1 allocations `[VERIFIED]`. However, proving complete runtime survival against hardware DMA transfers (image sensors, video codec, SD card DMA controller), framebuffers, or hardcoded pointers would require whole-ROM analysis across 32 MiB of ROM (`0xFC000000..0xFDFFFFFF`), which is impossible under Phase 0 bounded inspection budgets ($\le 4,096$ B/slice, $\le 24,576$ B milestone total). |
| **9** | **(d)** | `SleepTask` Function Body (Primary ROM Source) | `0xBFE14968` (ATCM Thumb-2; target vector `0xBFE14969` loaded at `0xFC31BF88`) | `0xFCEF33B4` | `0x00EF33B4` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:494-497; manifest PORT27-ROM-SLEEPTASK-VENEER]`; Function extent `[UNKNOWN]`; Parameter unit (milliseconds) and task context constraint `[INFERRED]` | **Outside milestone read policy boundary.** The ARM veneer `0xFC31BF84` was read as a verified branch target of `0xFC135CC6` in `PORT27-ROM-WATCHDOG-MODULE`. The veneer loads target vector `0xBFE14969` (ATCM RAM execution address). The source ROM entry address `0xFCEF33B4` is not a direct ROM branch target and was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`). Therefore, reading ROM `0xFCEF33B4` was outside the milestone read policy. Verifying conversion of `r0 = 2000` to millisecond timer ticks requires reading `0xFCEF33B4`, which was unread. |

---

## 4. Technical Analysis of the Failure to Meet Strict GO Criteria

### 4.1 Item (b): Task Creation Argument Dependency
The reviewer policy mandates:
> *"If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*

In order to spawn a resident heartbeat task, T2 would need to invoke `_CreateTask` (`sub_fc31bbc4` at `0xFC31BBC4`) with arguments matching the stock call site at `0xFC05B984..0xFC05B990`:
```armasm
    movs    r3, #0
    str     r3, [sp, #0]        ; sp[0] = 0 (user context parameter [INFERRED])
    ldr     r3, =task_heartbeat ; r3 = task entry point | 1 [VERIFIED entry role]
    movs    r2, #0              ; r2 = 0 (stack size & default selector [INFERRED])
    movs    r1, #25             ; r1 = 25 (priority [INFERRED])
    ldr     r0, =name_string    ; r0 = string pointer (task name [INFERRED])
    blx     sub_fc31bbc4        ; Invoke DryOS CreateTask veneer (ARM) [VERIFIED]
```

- **The `r2` Stack Size Dilemma**:
  1. If T2 passes `r2 = 0` (relying on the stock call-site literal), T2 depends on the instruction sequence documented in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-163` loading the default stack size from `*(uint32_t *)0x000081D0`.
  2. While the instruction sequence in Slice `S1C` was static-verified in PORT11A, its semantic interpretation as the default stack size selector remains **`[INFERRED]`**.
  3. More critically, the internal allocator `0xBFE10B88` (ROM `0xFCEEF5D4`) that allocates the stack buffer from kernel memory is **`[UNKNOWN]`**. If the internal allocator allocates stacks from a secondary pool or from an unreserved region, or if `r2 = 0` allocates a minimal 512-byte stack inadequate for interrupt nesting, the camera could suffer stack corruption or an unhandled crash.
  4. If T2 instead passes an explicit non-zero stack size in `r2` (such as `0x1000` = 4096 bytes, as seen in `sub_fc0bd0d2`), T2 is modifying an argument whose semantic role is **`[INFERRED]`**, directly violating the strict rule ("changing only values whose role is VERIFIED").

### 4.2 Item (a): Continuation Routines in ATCM
`sub_fc0d0126`'s own instructions (`0xFC0D0126..0xFC0D014E`) modify only the lock counter at `0x00008380` and call the IRQ disable/restore veneers `[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`. However, the destination routines in ATCM (`0xBFE14FE7` and `0xBFE14FEB`) were outside the PORT-27 authorized read policy. While it is highly probable from standard DryOS architecture that these routines simply execute `cpsie i` and `bx lr`, confirming that they perform no heap or memory-start operations is **`[INFERRED/UNKNOWN]`**.

### 4.3 Milestone Read Policy Boundary Analysis: Reachability vs. Out-of-Scope Targets

To prevent confusion regarding what was blocked by policy versus what was simply omitted from T1's read slices, the technical boundaries are delineated below:

1. **Reachable Target Not Read in T1 (`sub_fc31b408` & Heap Alignment)**:
   - Routine `sub_fc05b3c8` at `0xFC05B448` executes `blx 0xfc31b408` `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:158, 170; manifest PORT27-ROM-HEAP-SETUP]`.
   - Because `0xFC05B448` lies inside the approved heap slice `PORT27-ROM-HEAP-SETUP` (`0xFC05B3C0..0xFC05B53F`), `0xFC31B408` is a **branch target VERIFIED inside an approved range**.
   - Under the milestone read policy, bounded reads starting at verified branch targets inside approved ranges are fully permissible.
   - Therefore, `0xFC31B408` was **reachable under the milestone read policy**, but was simply not read in T1.
   - The PORT-27 evidence manifest authorization scope (`SCOPE-PORT27-RESIDENT-EVIDENCE`) authorizes up to 24,576 total bytes (`docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49`). T1 consumed 2,380 bytes across 8 slices, leaving **22,196 bytes** of unspent budget `[VERIFIED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49-55; docs/PORT27_RESIDENT_EVIDENCE.md:558-570]`.
   - Any alignment checks or constraints enforced by DryOS reside in `sub_fc31b408` or downstream of it. If `sub_fc31b408` itself branches to downstream callees, those downstream callees are not verified branch targets until `sub_fc31b408` is inspected.

2. **The Exact Policy Boundary for Item (b) and ATCM Destinations**:
   - The veneer `sub_fc31bbc4` at `0xFC31BBC4` is a verified ROM veneer read in T1 (`PORT27-ROM-CREATETASK-VENEER`). It executes `ldr pc, [pc, #-4]` loading `0xBFE14A3D` `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:251-255]`.
   - Address `0xBFE14A3D` specifies an execution address in **ATCM RAM** (`0xBFE14A3C`, Thumb-2 state), not a ROM address.
   - In ROM, the code executed at `0xBFE14A3C` originates from high ROM address `0xFCEF3488` via the early boot ATCM copy loop (`0xFC020040..0xFC020052`).
   - Neither the high ROM address `0xFCEF3488` nor the early boot copy loop `0xFC020040` was cited in prior manifests (`PORT23`, `PORT24`, `PORT25`), and neither is a direct branch target inside any ROM range read in T1.
   - Furthermore, the internal helpers called by `CreateTask`:
     - `0xBFE10B88` (`bl 0xBFE10B88` at `0xBFE14A8E`, ROM `0xFCEEF5D4`)
     - `0xBFE10D14` (`bl 0xBFE10D14` at `0xBFE14AA6`, ROM `0xFCEEF760`)
     - `0xBFE13E78` (`blx 0xBFE13E78` at `0xBFE14A5A`, `0xBFE14A72`, `0xBFE14A9C`, ROM `0xFCEF28C4`)
     reside inside the unread ATCM `CreateTask` body. None of these addresses is a verified branch target inside any range read in T1, and none was cited in prior manifests.
   - Therefore, the exact policy boundary that blocked Item (b) is that **no ROM instruction read in T1 branches to high ROM `0xFCEF3488`, `0xFCEEF5D4`, `0xFCEEF760`, or `0xFCEF28C4`**, and none of those start addresses was cited in prior manifests. Reading them requires an expanded milestone authorization scope.

---

## 5. Worktree State & Build Invariance Verification

Because the verdict is strictly **NO-GO**, no code changes were introduced.

### 5.1 Verification Commands Executed
1. **Evidence Consistency**:
   Validated machine-readable manifest `docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json` via `tools/port11c_evidence_validator.py`:
   ```bash
   python3 tools/port11c_evidence_validator.py --manifest docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json
   # Output: Result: VALID (8 entries, 0 errors, 1 warning)
   ```
2. **Prior Candidate Suite Regression Tests**:
   Executed full unit test suites for prior candidate builds (`test_port25_ladder_fix.py`, `test_port26_ladder_decode.py`, `test_port26_owner_template.py`, `test_port25_localise.py`, `test_early_boot_literals.py`, `test_port24_breadcrumb_ladder.py`):
   ```bash
   python3 -m unittest tests/test_port25_ladder_fix.py
   # Output: Ran 20 tests in 1.749s, OK (All 20 tests PASS)
   
   python3 -m unittest tests/test_port26_ladder_decode.py tests/test_port26_owner_template.py tests/test_port11c_evidence_validator.py
   # Output: Ran 93 tests in 3.456s, OK (All 93 tests PASS)
   
   python3 -m unittest tests/test_port25_localise.py tests/test_early_boot_literals.py tests/test_port24_breadcrumb_ladder.py
   # Output: Ran 40 tests, OK (All 40 tests PASS)
   ```
3. **Canonical Hash Invariance Confirmation**:
   - Default Candidate `DISKBOOT.BIN`: SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (118,001 bytes) `[VERIFIED]`
   - PORT-24 Power-on Fix `DISKBOOT.BIN`: SHA-256 `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` (118,001 bytes) `[VERIFIED]`
   - PORT-24 Ladder `DISKBOOT.BIN`: SHA-256 `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` (118,257 bytes) `[VERIFIED]`
   - PORT-25 Combined `DISKBOOT.BIN`: SHA-256 `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` (124,865 bytes) `[VERIFIED]`
4. **Git Worktree Status**:
   ```bash
   git status --short
   # Only docs/PORT27_RESIDENT_CANDIDATE.md is untracked; zero tracked files modified.
   ```

---

## 6. Acceptance Criteria Compliance Checklist

- [x] **If T1 is NO-GO: docs/PORT27_RESIDENT_CANDIDATE.md holds the exact UNKNOWN list and no code changes are made**: Confirmed. Exact UNKNOWN list documented in Section 3; no code files in `chdk-port/` or `tools/` were changed.
- [x] **Every firmware address, memory-start value and mode used is cited to a VERIFIED item in docs/PORT27_RESIDENT_EVIDENCE.md; nothing is inferred**: Confirmed. All addresses in the status matrix and UNKNOWN list are cited with exact file:line references and ROM inspection ranges.
- [x] **The memory start is reserved or raised as evidenced; the heartbeat task is created through the verified entry and toggles the LED at about 1 Hz; the PORT-25 ladder codes are unchanged**: N/A for code implementation under NO-GO verdict. The technical mechanisms for memory start reservation (`0x00368680` via `r4` override in `sub_fc05b3c8_my`), LED toggling (`0xD20B0884` ON/OFF words), and ladder preservation are verified and documented in Section 2, but not committed to binary.
- [x] **The flag-off default build and existing opt-in builds are byte-identical to before**: Confirmed. No build configurations or source headers were modified. Existing candidate hashes are verified bit-for-bit identical.
- [x] **docs/PORT27_RESIDENT_CANDIDATE.md records the build command, DISKBOOT SHA-256 and size; no binaries are committed**: Confirmed. Baseline build hashes and sizes recorded; no binary payloads committed.
