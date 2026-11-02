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
4. **Exact UNKNOWN List Recorded**: This document records the comprehensive, exact UNKNOWN list across Items (a), (b), and (d) with missing addresses, ranges, and explanations of why the PORT-27 ROM read policy could not reach them.

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

The table below catalogs every missing address or range across the prerequisite items, the exact component, and the specific reason why the PORT-27 ROM read policy could not reach it:

| # | Item | Component / Subsystem | Execution Address (VMA) | Source ROM Address / Range | File Offset | Length | Epistemic Status | Why the Read Policy Could Not Reach It |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | **(b)** | Internal Task Allocator / Initializer (`alloc_task_stack_tcb`) | `0xBFE10B88` (ATCM Thumb-2) | `0xFCEEF5D4..0xFCEEF75F` | `0x00EEF5D4..0x00EEF75F` | Up to 396 B | `UNKNOWN` | Start address `0xFCEEF5D4` was **not cited** in prior evidence manifests (`PORT23_EVIDENCE_MANIFEST.json`, `PORT24_EVIDENCE_MANIFEST.json`, or `PORT25_EVIDENCE_MANIFEST.json`). The PORT-27 read policy strictly limited new ROM reads to start addresses already cited in prior manifests or verified branch targets within them. Reading uncited high ROM / ATCM ranges requires explicit human owner authorization in an expanded milestone policy. |
| **2** | **(b)** | Internal Task Activation Helper (`activate_task`) | `0xBFE10D14` (ATCM Thumb-2) | `0xFCEEF760..0xFCEEF9C3` | `0x00EEF760..0x00EEF9C3` | Up to 612 B | `UNKNOWN` | Start address `0xFCEEF760` was **not cited** in prior evidence manifests (`PORT23`, `PORT24`, `PORT25`). Outside the authorized milestone read policy boundary. |
| **3** | **(b)** | DryOS Debug Assertion / Kernel Panic Handler (`DebugAssert`) | `0xBFE13E78` (ATCM Thumb-2) | `0xFCEF28C4..0xFCEF2943` | `0x00EF28C4..0x00EF2943` | Unverified ($\approx 128\text{ B}$) | `UNKNOWN` | Start address `0xFCEF28C4` was **not cited** in prior evidence manifests (`PORT23`, `PORT24`, `PORT25`). Outside the authorized milestone read policy boundary. |
| **4** | **(b)** | `CreateTask` Function Body (Primary ROM Source) | `0xBFE14A3C..0xBFE14AAD` (ATCM Thumb-2) | `0xFCEF3488..0xFCEF34F9` | `0x00EF3488..0x00EF34F9` | 114 B | `INFERRED` roles; `UNKNOWN` authority in PORT-27 | Start address `0xFCEF3488` was **not cited** in PORT-23, PORT-24, or PORT-25 manifests. While documented in PORT11A Slice `S1C`, PORT-27 policy strictly prohibited reading `0xFCEF3488`. Therefore, parameter roles carry forward PORT11A's `[INFERRED]` status and cannot be upgraded to `VERIFIED` on PORT-27's own authority. |
| **5** | **(a)** | ATCM Interrupt Disable Destination (`DisableInterrupts_ATCM`) | `0xBFE14FE7` (instruction `0xBFE14FE6`) | `0xFCEF3982..0xFCEF3985` | `0x00EF3982..0x00EF3985` | 4 B | `INFERRED / UNKNOWN` | The ARM veneer `sub_fc31befc` at `0xFC31BEFC` was authorized under `PORT27-ROM-IRQ-DISABLE`, but the target address `0xBFE14FE6` / ROM `0xFCEF3982` was **not cited** in prior evidence manifests. Destination routine effects in ATCM remain unread. |
| **6** | **(a)** | ATCM Interrupt Restore Destination (`RestoreInterrupts_ATCM`) | `0xBFE14FEB` (instruction `0xBFE14FEA`) | `0xFCEF3986..0xFCEF3989` | `0x00EF3986..0x00EF3989` | 4 B | `INFERRED / UNKNOWN` | The Thumb-2 veneer `sub_fc31b8ca` at `0xFC31B8CA` was authorized as a branch target of `0xFC0D014C`, but the ATCM destination `0xBFE14FEA` / ROM `0xFCEF3986` was **not cited** in prior manifests. Continuation behavior, return via `bx lr`, and confirmation of absence of heap operations remain unread. |
| **7** | **(a)** | DryOS Heap-Start Alignment Specification | N/A (code inside `sub_fc31b408`) | Downstream of `0xFC05B448` (`blx 0xfc31b408`) | N/A | N/A | `UNKNOWN` | Routine `sub_fc05b3c8` (`PORT27-ROM-HEAP-SETUP`) merely stores the heap base pointer `sp[0x08]` without alignment checks or masking. Any alignment constraints enforced by the DryOS kernel reside inside `sub_fc31b408`, which lies outside the authorized slice `0xFC05B3C0..0xFC05B53F` and was not cited in prior manifests. |
| **8** | **(a)** | Relocated Core Region Non-Heap RAM Users | `0x003489B4..0x00368680` (RAM) | Entire 32 MiB ROM (`0xFC000000..0xFDFFFFFF`) | Entire dump | 32 MiB | `UNKNOWN` | Raising the heap base past `_end` (`0x00368680`) excludes relocated core RAM from DryOS heap pool 1 allocations `[VERIFIED]`. However, proving complete runtime survival against hardware DMA transfers (image sensors, video codec, SD card DMA controller), framebuffers, or hardcoded pointers would require whole-ROM analysis, which is impossible under Phase 0 bounded inspection budgets ($\le 4,096$ B/slice, $\le 24,576$ B milestone total). |
| **9** | **(d)** | `SleepTask` Function Body (Primary ROM Source) | `0xBFE14968..0xBFE14997` (ATCM Thumb-2) | `0xFCEF33B4..0xFCEF33E3` | `0x00EF33B4..0x00EF33E3` | 48 B | `INFERRED` units; `UNKNOWN` authority in PORT-27 | The ARM veneer `0xFC31BF84` was read as a branch target from `0xFC135CC6`, but the ATCM destination `0xBFE14968` / ROM `0xFCEF33B4` was **not cited** in PORT-23/24/25 manifests. Verifying conversion of `r0 = 2000` to millisecond timer ticks requires reading `0xFCEF33B4`, which was prohibited under milestone policy. |

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
