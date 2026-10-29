# PORT-13 — Fail-Closed Proof Obligations: U2 InitFileModules Filesystem Readiness

**Milestone**: PORT-13 / Task `p13-oblig-u2-r2` (Replacement for task 10 `p13-oblig-u2`)  
**Target Subsystem**: Prerequisite **U2** (`init_file_modules_entry_verified`) / Interface **I2** (`InitFileModules` readiness gate)  
**Camera Firmware**: Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8`, DryOS on ARM Cortex-R4)  
**Reference Document**: [`docs/PORT13_REVIEW_U2.md`](PORT13_REVIEW_U2.md) (Independent Read-Only Review of Draft PR #24)  
**Supporting Evidence**: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md`](PORT11A_GM110C_ROM_EVIDENCE.md), [`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py), [`tools/port9b_runtime_contract.py`](../tools/port9b_runtime_contract.py), [`docs/RESTART_SD_HOST_AUDIT.md`](RESTART_SD_HOST_AUDIT.md), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`](PORT5B_HISTORICAL_BOOT_COMPARISON.md), [`docs/PORT5A_RANMA_PORT_RECOVERY.md`](PORT5A_RANMA_PORT_RECOVERY.md)  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Offline Read-Only Investigation)  

---

## 1. Executive Summary & Epistemic Separation

This document formalizes the mathematical and architectural proof obligations required before any implementation may claim that the DryOS filesystem is initialized and ready for file I/O operations following `InitFileModules` on Canon PowerShot G3 X **GM1.10C**.

This specification directly incorporates the findings, corrections, and remediation requirements established in [`docs/PORT13_REVIEW_U2.md`](PORT13_REVIEW_U2.md), replacing the unmerged proposals of Draft PR #24.

### 1.1 Core Epistemic Invariant: Static Entry vs. Dynamic Filesystem Readiness
The foundational requirement of Prerequisite U2 is the strict separation between:
1. **Static ROM Evidence** (`STATIC_VERIFIED`):
   - Task creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`), task name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack size `0x1000`, and Thumb entry pointer **`0xFC0BD071`** (instruction address **`0xFC0BD070`**) are verified in GM1.10C ROM slice `S2A` ([`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 220–228, 235, 251, 389, 402`](PORT11A_GM110C_ROM_EVIDENCE.md#L21)).
   - This static evidence proves **only** the existence, allocation parameters, and initial instruction address of the task.
2. **Dynamic Runtime Readiness** (`UNKNOWN / NOT ESTABLISHED`):
   - Static entry evidence proves **zero** dynamic properties: it does not prove that the DryOS task scheduler ever dispatched `task_InitFileModules`, that the physical SD card controller is powered, that card host negotiation succeeded, that a valid FAT32 partition exists, or that directory structures are readable without bus timeout.
   - Callee 1 `sub_fc0d9ccc` contains **zero conditional branches of its own** and concludes with `movs r0, #0; pop {r4, pc}`; thus **`r0 = 0` is an unconditional constant on normal return** ([`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284, 390`](PORT11A_GM110C_ROM_EVIDENCE.md#L21)). Observing `r0 == 0` provides zero discrimination regarding physical media state ([`docs/PORT13_REVIEW_U2.md:25, 100, 142–144`](PORT13_REVIEW_U2.md#L25)).
   - DryOS event `0x5006` is insufficient to establish filesystem readiness: $\text{Event}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$ ([`tools/port9a_runtime_lifecycle.py:301, 678–679`](../tools/port9a_runtime_lifecycle.py#L301), [`docs/PORT13_REVIEW_U2.md:26, 108, 145–147`](PORT13_REVIEW_U2.md#L26)).

### 1.2 Remediation of PR #24 Flaws from `docs/PORT13_REVIEW_U2.md`
This document remedies all eight evidentiary and technical defects identified in [`docs/PORT13_REVIEW_U2.md:237–262`](PORT13_REVIEW_U2.md#L237-L262):
1. **Corrected Instruction Addresses** ([`PORT13_REVIEW_U2.md:32–34, 101–103, 238–241`](PORT13_REVIEW_U2.md#L32-L34)):
   - Call to Callee 1 (`sub_fc0d9ccc`): Corrected from PR #24's erroneous `0xFC0BD074` to **`0xFC0BD072`** (`bl 0xFC0D9CCC`, raw bytes `1c f0 2b fe`; [`PORT11A:252`](PORT11A_GM110C_ROM_EVIDENCE.md#L252)).
   - Call to Callee 2 (`sub_fc0d9cf6`): Corrected from PR #24's erroneous `0xFC0BD078` to **`0xFC0BD086`** (`bl 0xFC0D9CF6`, raw bytes `1c f0 36 fe`; [`PORT11A:259`](PORT11A_GM110C_ROM_EVIDENCE.md#L259)). At `0xFC0BD078`, the actual instruction is `movw r5, #0x5006` (`45 f2 06 05`; [`PORT11A:254`](PORT11A_GM110C_ROM_EVIDENCE.md#L254)).
   - Task Epilogue/Exit: Corrected from PR #24's erroneous `0xFC0BD07C` (which is `beq 0xFC0BD086`; [`PORT11A:255`](PORT11A_GM110C_ROM_EVIDENCE.md#L255)) to tail branch **`0xFC0BD096: b.w 0xFC35B93C`** and epilogue **`0xFC0BD09A: pop {r4, r5, r6, pc}`** ([`PORT11A:265–266`](PORT11A_GM110C_ROM_EVIDENCE.md#L265-L266)).
2. **De-escalated Event `0x5006` Dispatch Mechanism** ([`PORT13_REVIEW_U2.md:43–44, 109, 242–245`](PORT13_REVIEW_U2.md#L43-L44)):
   - PR #24's assertion that event `0x5006` is dispatched via asynchronous message queues is removed. The target subroutine `0xFC35B93C` lies outside slice `S2A` and its internal mechanism is strictly **`UNKNOWN`** ([`PORT11A:258, 265`](PORT11A_GM110C_ROM_EVIDENCE.md#L258)). The obligation is grounded strictly in what is verified: event `0x5006` is insufficient for filesystem readiness ([`port9a_runtime_lifecycle.py:301, 678–679`](../tools/port9a_runtime_lifecycle.py#L301)).
3. **Aligned Lifecycle Promotion & Added Non-Destructive Open/Read** ([`PORT13_REVIEW_U2.md:45–47, 112, 161–167, 246–248`](PORT13_REVIEW_U2.md#L45-L47)):
   - PR #24's uncodified driver internals (idle DMA, BPB parsing, descriptor allocation) are labeled as proposed extensions. This document explicitly includes the tracked requirement from [`tools/port9a_runtime_lifecycle.py:302–303`](../tools/port9a_runtime_lifecycle.py#L302): **verified non-destructive file open/read capability on mounted volume without contention or timeout** for `fs_io_ready`.
4. **Contextualized Historical Citation** ([`PORT13_REVIEW_U2.md:48–49, 110, 249–250`](PORT13_REVIEW_U2.md#L48-L49)):
   - Untracked citation `platform/g3x/sub/110e/boot.c` is replaced with tracked secondary evidence in [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190`](PORT5B_HISTORICAL_BOOT_COMPARISON.md#L190) (`P:1769–1795`) and [`docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`](PORT5A_RANMA_PORT_RECOVERY.md#L93-L94).
5. **De-escalated Callee 2 (`sub_fc0d9cf6`) Semantics** ([`PORT13_REVIEW_U2.md:50–51, 107, 251–253`](PORT13_REVIEW_U2.md#L50-L51)):
   - Unverified claims that `sub_fc0d9cf6` performs "Mount completion / event dispatch" are removed. Visible event `0x5006` calls reside directly in `task_InitFileModules` ([`PORT11A:254–265`](PORT11A_GM110C_ROM_EVIDENCE.md#L254-L265)), while the internal behavior of `sub_fc0d9cf6`'s nested callees remains strictly **`UNKNOWN`** ([`PORT11A:286, 289`](PORT11A_GM110C_ROM_EVIDENCE.md#L286)).
6. **Qualified Warm-Restart State & Decoupled Reset Ownership** ([`PORT13_REVIEW_U2.md:52–53, 114–116, 254–256`](PORT13_REVIEW_U2.md#L52-L53)):
   - SD hardware bus/card-host state persistence across warm restart is classified as **`INFERRED / PLAUSIBLE`** per [`docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29`](RESTART_SD_HOST_AUDIT.md#L11-L18). The lifecycle requirement is decoupled from unverified reset ownership assignment to `InitFileModules` (**`UNKNOWN / NOT ESTABLISHED`** per [`RESTART_SD_HOST_AUDIT.md:54–68`](RESTART_SD_HOST_AUDIT.md#L54-L68)).
7. **Removed Callee 1 Storage Init Semantics** ([`PORT13_REVIEW_U2.md:35–38, 104, 257–259`](PORT13_REVIEW_U2.md#L35-L38)):
   - Description asserting Callee 1 performs "Lower-level storage/host controller init" is marked strictly **`UNKNOWN / UNSUPPORTED`** per [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:289, 406`](PORT11A_GM110C_ROM_EVIDENCE.md#L289).
8. **Removed `task_Startup` Invocation Edge** ([`PORT13_REVIEW_U2.md:39–42, 105, 260–262`](PORT13_REVIEW_U2.md#L39-L42)):
   - Graph edge asserting `task_Startup` creates `sub_fc0bd0b4` is marked strictly **`UNKNOWN / UNSUPPORTED`** per [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:81, 407`](PORT11A_GM110C_ROM_EVIDENCE.md#L81).

---

## 2. Canonical Call Sequence and Epistemic Observation Limits

### 2.1 Verified Disassembly of `task_InitFileModules` (ROM Slice S2A)
The execution flow within `task_InitFileModules` (`0xFC0BD070..0xFC0BD09B`) is verified in GM1.10C ROM slice `S2A` ([`docs/PORT11A_GM110C_ROM_EVIDENCE.md:247–267`](PORT11A_GM110C_ROM_EVIDENCE.md#L247-L267)):

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Architectural Effect & Role | Epistemic Status |
|---|---:|---|---|---|:---:|
| **`0xFC0BD070`** | `0x0BD070` | `70 b5` | `push {r4, r5, r6, lr}` | Function entry (Thumb entry pointer `0xFC0BD071`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD072`** | `0x0BD072` | `1c f0 2b fe` | `bl 0xFC0D9CCC` | Call Callee 1 (`sub_fc0d9ccc`, Slice `S2B`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD076`** | `0x0BD076` | `04 00` | `movs r4, r0` | Save return value in `r4`; flags updated (`Z=1` if `r0==0`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD078`** | `0x0BD078` | `45 f2 06 05` | `movw r5, #0x5006` | Load constant `r5 = 0x5006` (Event ID `[INFERRED]`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD07C`** | `0x0BD07C` | `03 d0` | `beq 0xFC0BD086` | Branch to `0xFC0BD086` if `r0 == 0` | **`STATIC_VERIFIED`** |
| `0xFC0BD07E` | `0x0BD07E` | `00 21` | `movs r1, #0` | Set `r1 = 0` (argument 2) | **`STATIC_VERIFIED`** |
| `0xFC0BD080` | `0x0BD080` | `28 46` | `mov r0, r5` | Set `r0 = 0x5006` (argument 1) | **`STATIC_VERIFIED`** |
| `0xFC0BD082` | `0x0BD082` | `9e f2 5b fc` | `bl 0xFC35B93C` | Call `0xFC35B93C(0x5006, 0)` (target outside `S2A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD086`** | `0x0BD086` | `1c f0 36 fe` | `bl 0xFC0D9CF6` | Call Callee 2 (`sub_fc0d9cf6`, Slice `S2B`) | **`STATIC_VERIFIED`** |
| `0xFC0BD08A` | `0x0BD08A` | `00 2c` | `cmp r4, #0` | Compare saved `r4` against 0 | **`STATIC_VERIFIED`** |
| `0xFC0BD08C` | `0x0BD08C` | `05 d1` | `bne 0xFC0BD09A` | If `r4 != 0`, branch to epilogue `0xFC0BD09A` | **`STATIC_VERIFIED`** |
| `0xFC0BD08E` | `0x0BD08E` | `28 46` | `mov r0, r5` | Set `r0 = 0x5006` (argument 1) | **`STATIC_VERIFIED`** |
| `0xFC0BD090` | `0x0BD090` | `bd e8 70 40` | `pop.w {r4, r5, r6, lr}` | Restore registers before tail call | **`STATIC_VERIFIED`** |
| `0xFC0BD094` | `0x0BD094` | `01 21` | `movs r1, #1` | Set `r1 = 1` (argument 2) | **`STATIC_VERIFIED`** |
| **`0xFC0BD096`** | `0x0BD096` | `9e f2 51 bc` | `b.w 0xFC35B93C` | Tail-branch `0xFC35B93C(0x5006, 1)` (outside `S2A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| **`0xFC0BD09A`** | `0x0BD09A` | `70 bd` | `pop {r4, r5, r6, pc}` | Function epilogue return | **`STATIC_VERIFIED`** |

### 2.2 Epistemic Observation Limits Matrix

| Observation Target | Tracked Evidence | What It PROVES | What It CANNOT Prove |
|---|---|---|---|
| **Creator `sub_fc0bd0b4`** | Loads `"InitFileModules"`, prio `0x19`, stack `0x1000`, entry `0xFC0BD071` ([`PORT11A:220–228`](PORT11A_GM110C_ROM_EVIDENCE.md#L220-L228)). | Static task identity, creation parameters, and initial execution vector. | Whether `sub_fc0bd0b4` was invoked during boot (`UNKNOWN` caller graph; [`PORT11A:81, 407`](PORT11A_GM110C_ROM_EVIDENCE.md#L81)). |
| **Thumb Entry `0xFC0BD071`** | Slice `S2A` instruction bytes at `0xFC0BD070` ([`PORT11A:251`](PORT11A_GM110C_ROM_EVIDENCE.md#L251)). | Statically verified entry point of `task_InitFileModules`. | Does **not** prove scheduler dispatch, CPU execution, or host controller power/clocking. |
| **Callee 1 `sub_fc0d9ccc` Return** | Slice `S2B`: zero conditional branches, ends with `movs r0, #0; pop {r4, pc}` ([`PORT11A:281–284`](PORT11A_GM110C_ROM_EVIDENCE.md#L281-L284)). | Static return sequence: normal return yields constant `r0 = 0` (`movs r0, #0; pop {r4, pc}` at `0xFC0D9CF2..0xFC0D9CF5`). Actual runtime completion and absence of CPU faults remains **`UNKNOWN`**. | **Cannot prove storage mount readiness**: `r0 = 0` is unconditionally hardcoded; provides zero dynamic media discrimination. Does not prove the epilogue was reached at runtime without a CPU fault. |
| **Callee 2 `sub_fc0d9cf6` Call** | Invoked sequentially at `0xFC0BD086` ([`PORT11A:259`](PORT11A_GM110C_ROM_EVIDENCE.md#L259)). | Static sequential invocation in task body. | Does not prove FAT partition mounted, cluster tables valid, or file handles writable. Nested callees are `UNKNOWN` ([`PORT11A:286, 289`](PORT11A_GM110C_ROM_EVIDENCE.md#L286)). |
| **Event `0x5006` Call** | Target routine `0xFC35B93C` called with `0x5006` ([`PORT11A:258, 265`](PORT11A_GM110C_ROM_EVIDENCE.md#L258)). | Instruction call to routine `0xFC35B93C`. | Does not prove filesystem readiness: event `0x5006` is insufficient for filesystem I/O ([`port9a:301, 678–679`](../tools/port9a_runtime_lifecycle.py#L301)). Queuing mechanism is `UNKNOWN`. |

---

## 3. Formal U2 Proof Obligations Catalog

The following eight proof obligations are codified in [`tools/port13_u2_obligations.py`](../tools/port13_u2_obligations.py). Every obligation carries an ID, an epistemic status, an architectural kind (static vs runtime), required evidence specifications, and citations strictly to Git-tracked files.

### 3.1 Obligation OBLIG-U2-01: Static Task Entry Vector
- **ID**: `OBLIG-U2-01`
- **Kind**: **`STATIC`**
- **Current Status**: **`VERIFIED`**
- **Statement**: `task_InitFileModules` static task parameters and Thumb entry pointer `0xFC0BD071` (instruction address `0xFC0BD070`) are statically verified in GM1.10C ROM slice `S2A`.
- **Required Evidence**:
  - *Artifact Type*: `STATIC_ROM_SLICE`
  - *What It Must Show*: Static creator `sub_fc0bd0b4` passing task name `"InitFileModules"`, priority `0x19`, stack size `0x1000`, and Thumb entry pointer `0xFC0BD071` (loaded from literal pool `[0xFC0BD1A8]`) to `j_CreateTask` (`0xFC31BBC4`), with entry instruction `push {r4, r5, r6, lr}` at `0xFC0BD070`.
- **Tracked Citations**:
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21`](PORT11A_GM110C_ROM_EVIDENCE.md#L21) (Executive summary table U2: task identity and entry `0xFC0BD071` `STATIC_VERIFIED`).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:223`](PORT11A_GM110C_ROM_EVIDENCE.md#L223) (`sub_fc0bd0b4` loads `r3 = [0xFC0BD1A8] = 0xFC0BD071`).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:235`](PORT11A_GM110C_ROM_EVIDENCE.md#L235) (Literal pool entry `0xFC0BD1A8` holding `0xFC0BD071`).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:251`](PORT11A_GM110C_ROM_EVIDENCE.md#L251) (`task_InitFileModules` entry instruction at `0xFC0BD070`).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:389`](PORT11A_GM110C_ROM_EVIDENCE.md#L389) (`C-07`: Entry `0xFC0BD071` `STATIC_VERIFIED`).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:402`](PORT11A_GM110C_ROM_EVIDENCE.md#L402) (`InitFileModules` creator `sub_fc0bd0b4` details).
- **Epistemic Invariant**: This obligation is the **sole** obligation satisfied by static ROM evidence. It proves the entry vector only; it does not satisfy any runtime obligation.

### 3.2 Obligation OBLIG-U2-02: Runtime Task Creation and Dispatch Witness
- **ID**: `OBLIG-U2-02`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Dynamic execution witness confirming `task_InitFileModules` ran in the current boot generation after DryOS scheduler dispatch.
- **Required Evidence**:
  - *Artifact Type*: `EXECUTION_WITNESS`
  - *What It Must Show*: Dynamic execution trace confirming `task_InitFileModules` entry ran after DryOS scheduler dispatch in the active `boot_generation` context.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:296–297`](../tools/port9a_runtime_lifecycle.py#L296-L297) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `task_started`).
  - [`tools/port9a_runtime_lifecycle.py:661–668`](../tools/port9a_runtime_lifecycle.py#L661-L668) (`RuntimeLifecycle.init_file_modules_started()` requires generation match).
  - [`docs/PORT13_REVIEW_U2.md:24–25`](PORT13_REVIEW_U2.md#L24-L25) (Observing entry vector `0xFC0BD071` does not prove dynamic dispatch).
- **Epistemic Invariant**: Static entry evidence `0xFC0BD071` cannot discharge this obligation.

### 3.3 Obligation OBLIG-U2-03: Runtime Normal Completion Witness
- **ID**: `OBLIG-U2-03`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Current-generation normal completion witness confirming both `sub_fc0d9ccc` and `sub_fc0d9cf6` return normally in current boot generation (note: `sub_fc0d9ccc` `r0==0` is constant on normal return and does NOT prove mount).
- **Required Evidence**:
  - *Artifact Type*: `COMPLETION_WITNESS`
  - *What It Must Show*: Dynamic completion witness verifying both `sub_fc0d9ccc` and `sub_fc0d9cf6` returned in current boot generation without latched fault (noting that `sub_fc0d9ccc` `r0==0` is constant on normal return and does NOT prove mount).
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:298–299`](../tools/port9a_runtime_lifecycle.py#L298-L299) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `init_returned_normally`).
  - [`tools/port9a_runtime_lifecycle.py:670–706`](../tools/port9a_runtime_lifecycle.py#L670-L706) (`RuntimeLifecycle.init_file_modules_returned()` requires current generation and no latched fault).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284, 390`](PORT11A_GM110C_ROM_EVIDENCE.md#L21) (`sub_fc0d9ccc` contains zero conditional branches, returns `r0=0` constant on normal return).
  - [`docs/PORT13_REVIEW_U2.md:25, 100, 142–144`](PORT13_REVIEW_U2.md#L25) (Epilogue `r0=0` is unconditional constant on normal return; does not prove mount).
- **Notes**: Requires dynamic completion witness for `sub_fc0d9ccc` and `sub_fc0d9cf6` in active boot generation; `r0==0` is constant on normal return and does not prove mount.

### 3.4 Obligation OBLIG-U2-04: Event `0x5006` Decoupling from Filesystem Gate
- **ID**: `OBLIG-U2-04`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Event `0x5006` decoupling from filesystem I/O gate: $\text{Event}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$; independent kernel/storage state proof required.
- **Required Evidence**:
  - *Artifact Type*: `STORAGE_MOUNT_PROOF`
  - *What It Must Show*: Independent kernel storage state proof that FAT volume mount succeeded without relying on event `0x5006`.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:300–301`](../tools/port9a_runtime_lifecycle.py#L300-L301) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `mount_observed`: event `0x5006` alone is insufficient).
  - [`tools/port9a_runtime_lifecycle.py:678–679`](../tools/port9a_runtime_lifecycle.py#L678-L679) (Posting event `0x5006` does not advance to `mount_observed` or `fs_io_ready`).
  - [`tools/port9a_runtime_lifecycle.py:708–737`](../tools/port9a_runtime_lifecycle.py#L708-L737) (`RuntimeLifecycle.record_mount_observation()` requires independent mount observation).
  - [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265`](PORT11A_GM110C_ROM_EVIDENCE.md#L258) (`0xFC35B93C` target outside `S2A` / `UNKNOWN`).
  - [`docs/PORT13_REVIEW_U2.md:26, 43–44, 108–109, 145–147`](PORT13_REVIEW_U2.md#L26) (Event `0x5006` alone is insufficient for filesystem readiness).

### 3.5 Obligation OBLIG-U2-05: Causal Ordering Relative to First CHDK File Access
- **ID**: `OBLIG-U2-05`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Strict causal ordering of filesystem readiness signal prior to first CHDK file access with verified non-destructive open/read capability on mounted volume without contention or timeout.
- **Required Evidence**:
  - *Artifact Type*: `CAUSAL_ORDERING_TRACE`
  - *What It Must Show*: Verified non-destructive file open/read capability on mounted volume without contention or timeout, causally preceding any CHDK file access (`Fopen_Fut`, `Fread_Fut`, `Fwrite_Fut`, diskboot, or SpyTask file I/O):
    $$\text{InitFileModules complete} \prec \text{Mount Verified} \prec \text{fs\_io\_ready} \prec \text{First CHDK File Access}$$
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:302–303`](../tools/port9a_runtime_lifecycle.py#L302-L303) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `fs_io_ready`: non-destructive file open/read capability).
  - [`tools/port9a_runtime_lifecycle.py:739–765`](../tools/port9a_runtime_lifecycle.py#L739-L765) (`RuntimeLifecycle.record_filesystem_io_readiness()`).
  - [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190`](PORT5B_HISTORICAL_BOOT_COMPARISON.md#L190) (Historical defect: `core_spytask_can_start` called without checking mount/return status; patch lines `P:1769–1795`).
  - [`docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`](PORT5A_RANMA_PORT_RECOVERY.md#L93-L94) (Historical port recovery notes on `core_spytask_can_start`).
  - [`docs/PORT13_REVIEW_U2.md:45–47, 49, 110, 112, 161–167`](PORT13_REVIEW_U2.md#L45-L47) (Tracked obligation for verified non-destructive open/read capability).

### 3.6 Obligation OBLIG-U2-06: Fail-Closed Fault, Error, and Timeout Handling
- **ID**: `OBLIG-U2-06`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Fail-closed fault, error, timeout, and out-of-order execution handling: any violation immediately transitions filesystem state to `FAILED` and permanently blocks the gate.
- **Required Evidence**:
  - *Artifact Type*: `FAULT_HANDLING_WITNESS`
  - *What It Must Show*: Verification that errors, timeouts, out-of-order calls, or latched CPU faults halt progression and permanently fail the filesystem gate.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:262–263`](../tools/port9a_runtime_lifecycle.py#L262-L263) (`FilesystemReadinessState.stage` returns `FAILED` if `self.failed`).
  - [`tools/port9a_runtime_lifecycle.py:686–694`](../tools/port9a_runtime_lifecycle.py#L686-L694) (`init_file_modules_returned` before `task_started` or with latched fault fails filesystem).
  - [`docs/PORT13_REVIEW_U2.md:27, 159, 212, 215`](PORT13_REVIEW_U2.md#L27) (Fail-closed invariant: latched CPU faults halt progression).

### 3.7 Obligation OBLIG-U2-07: Monotonic Generation Token Invalidation Across Warm Restart
- **ID**: `OBLIG-U2-07`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Monotonic `boot_generation` token binding: filesystem readiness latch $\langle \text{Ready}, \text{GenerationID} \rangle$ invalidated across soft reboot or warm restart.
- **Required Evidence**:
  - *Artifact Type*: `GENERATION_BINDING_PROOF`
  - *What It Must Show*: Monotonic generation token check rejecting stale tokens from prior generations across warm restart and resetting filesystem stages to `NOT_CREATED`.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:250`](../tools/port9a_runtime_lifecycle.py#L250) (`boot_generation` field in `FilesystemReadinessState`).
  - [`tools/port9a_runtime_lifecycle.py:343–366`](../tools/port9a_runtime_lifecycle.py#L343-L366) (`RuntimeLifecycle.reset()` increments `boot_generation` and resets fs state).
  - [`tools/port9a_runtime_lifecycle.py:394–400`](../tools/port9a_runtime_lifecycle.py#L394-L400) (`RuntimeLifecycle._check_generation()` validates active `boot_generation`).
  - [`docs/PORT13_REVIEW_U2.md:113, 213`](PORT13_REVIEW_U2.md#L113) (Latch state must be monotonically bound to `boot_generation` token).

### 3.8 Obligation OBLIG-U2-08: Warm-Restart Storage Preconditions Resolution
- **ID**: `OBLIG-U2-08`
- **Kind**: **`RUNTIME`**
- **Current Status**: **`UNKNOWN`**
- **Statement**: Resolution of warm-restart SD host/card preconditions (P11, P12, P13, P15) with host retention qualified as plausible and reset ownership decoupled from `InitFileModules`.
- **Required Evidence**:
  - *Artifact Type*: `WARM_RESTART_AUDIT_WITNESS`
  - *What It Must Show*: Precondition resolution for SD host and card state across warm restart confirming re-enumeration safety without bus lockup.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:304–306`](../tools/port9a_runtime_lifecycle.py#L304-L306) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `warm_restart_safe`).
  - [`tools/port9a_runtime_lifecycle.py:767–805`](../tools/port9a_runtime_lifecycle.py#L767-L805) (`RuntimeLifecycle.record_warm_restart_storage_safety()`).
  - [`tools/port9b_runtime_contract.py:79–80`](../tools/port9b_runtime_contract.py#L79-L80) (Fact U2 encompasses warm-restart storage safety).
  - [`docs/RESTART_SD_HOST_AUDIT.md:16`](RESTART_SD_HOST_AUDIT.md#L16) (Host state retention is plausible `[P]`; intervening routines `0xFC41870C` and `[0x4000]` `UNKNOWN`).
  - [`docs/RESTART_SD_HOST_AUDIT.md:56`](RESTART_SD_HOST_AUDIT.md#L56) (`SD1stInit` task entry `0x010E17A5`; reset ownership decoupled from `InitFileModules`).
  - [`docs/PORT13_REVIEW_U2.md:52–53, 114–116, 254–256`](PORT13_REVIEW_U2.md#L52-L53) (Decouple lifecycle requirement from unverified reset ownership assignment).

---

## 4. Consistency with Runtime Lifecycle and Offline Contracts

### 4.1 Consistency with `tools/port9a_runtime_lifecycle.py`
The obligations model codified in `tools/port13_u2_obligations.py` strictly adheres to `tools/port9a_runtime_lifecycle.py`:
1. **Preconditions Invariant**: `GM110C_PRECONDITIONS.init_file_modules_entry_verified` is strictly `False` ([`port9a:100, 105`](../tools/port9a_runtime_lifecycle.py#L100)).
2. **Static Evidence Separation**: `GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry` is `STATIC_VERIFIED`, while `GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness` is strictly `UNKNOWN` ([`port9a:119–120`](../tools/port9a_runtime_lifecycle.py#L119-L120)).
3. **Six-Stage Promotion Requirements Completeness**: All six stages of `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` ([`port9a:293–306`](../tools/port9a_runtime_lifecycle.py#L293-L306)) are mapped directly to tracked line numbers in `port9a` and canonical proof obligations:
   - Stage 1: `task_created` ([`port9a:294`](../tools/port9a_runtime_lifecycle.py#L294)) $\to$ `OBLIG-U2-01` (static creator vector) & `OBLIG-U2-02` (task creation witness).
   - Stage 2: `task_started` ([`port9a:296`](../tools/port9a_runtime_lifecycle.py#L296)) $\to$ `OBLIG-U2-02` (execution witness after scheduler dispatch).
   - Stage 3: `init_returned_normally` ([`port9a:298`](../tools/port9a_runtime_lifecycle.py#L298)) $\to$ `OBLIG-U2-03` (normal completion witness for both `sub_fc0d9ccc` and `sub_fc0d9cf6`).
   - Stage 4: `mount_observed` ([`port9a:300`](../tools/port9a_runtime_lifecycle.py#L300)) $\to$ `OBLIG-U2-04` (independent kernel storage mount proof decoupled from event `0x5006`).
   - Stage 5: `fs_io_ready` ([`port9a:302`](../tools/port9a_runtime_lifecycle.py#L302)) $\to$ `OBLIG-U2-05` (verified non-destructive open/read capability prior to CHDK file access).
   - Stage 6: `warm_restart_safe` ([`port9a:304`](../tools/port9a_runtime_lifecycle.py#L304)) $\to$ `OBLIG-U2-08` (warm-restart SD host/card state preconditions resolution).

### 4.2 Consistency with `tools/port9b_runtime_contract.py`
The obligations model aligns with `tools/port9b_runtime_contract.py`:
1. **Fact U2 in Registry**: Fact U2 registers `init_file_modules_entry_verified` as: *"InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety"* ([`port9b:79–80`](../tools/port9b_runtime_contract.py#L79-L80)). Fact U2 remains address-free and unverified in Phase 0.
2. **Contract C3.gate**: Ensures that activation markers (`REPLACEMENTS["InitFileModules"]` or bare `core_spytask_can_start`) are absent in default platform sources ([`port9b:455–456`](../tools/port9b_runtime_contract.py#L455-L456)).
3. **Contract C6.fs_readiness_contract**: Verifies the 6-stage filesystem promotion structure and default fail-closed invariants ([`port9b:529–564`](../tools/port9b_runtime_contract.py#L529-L564)).

---

## 5. Implementation Architecture & Negative Tests

### 5.1 Fail-Closed Evaluator Implementation
The evaluator in [`tools/port13_u2_obligations.py`](../tools/port13_u2_obligations.py) implements the following fail-closed rules:
- `evaluate()` evaluates aggregate filesystem readiness, which strictly requires the **complete canonical obligation set** (`OBLIG-U2-01` through `OBLIG-U2-08`). Any strict subset, missing obligation, extra obligation, or substituted obligation causes aggregate evaluation to fail closed (`is_ready = False`, `status = "not-ready"`, `RULE_INCOMPLETE_OBLIGATION_SET`).
- Per-obligation satisfaction in isolation is evaluated via `evaluate_obligation()`, and queried on `EvaluationResult` via `obligation_evaluations` or `is_obligation_satisfied(obligation_id)`. Satisfying an individual obligation in isolation (including `OBLIG-U2-01`) does not confer aggregate readiness.
- Submitted evidence artifacts are strictly validated before discharging any obligation:
  - The artifact's citation must be present and non-empty (`RULE_MISSING_CITATIONS`).
  - The citation must point to a Git-tracked file on `origin/main` (`RULE_UNTRACKED_PATH`).
  - The citation must not reference forbidden local-only paths (`firmware/`, `PORT-9A L1/L2`) (`RULE_FORBIDDEN_LOCAL_PATH`).
  - The artifact's `artifact_type` must match the obligation's required artifact type (`RULE_ARTIFACT_TYPE_MISMATCH`).
  - The artifact's status must be `VERIFIED` (`RULE_EVIDENCE_STATUS_NOT_VERIFIED`).
  - For runtime obligations, static evidence (including ROM slices, `0xFC0BD071`, or citations to `docs/PORT11A_GM110C_ROM_EVIDENCE.md` even with empty addresses) is strictly rejected with `RULE_STATIC_CANNOT_DISCHARGE_RUNTIME`.
- Address provenance verification guarantees that every firmware address referenced in the module is cited to a Git-tracked document at the exact line number.

### 5.2 Test Suite Verification
The offline test suite in [`tests/test_port13_u2_obligations.py`](../tests/test_port13_u2_obligations.py) validates the entire contract:
- `test_evaluate_returns_not_ready_for_shipped_data`: Confirms `is_ready == False`, `status == "not-ready"`, and 7 of 8 obligations are `UNKNOWN`.
- `test_there_is_no_path_to_ready_from_shipped_data`: Proves no path to ready from shipped data and asserts each single obligation evaluated alone fails aggregate readiness.
- `test_every_strict_subset_of_canonical_set_returns_not_ready`: Verifies every strict subset (length 1 through 7, including evaluating just `OBLIG-U2-01` with static evidence) returns `not-ready`.
- `test_static_entry_evidence_satisfies_static_entry_obligation`: Confirms static entry evidence satisfies `OBLIG-U2-01` in isolation while aggregate readiness remains `not-ready`.
- `test_static_entry_evidence_cannot_discharge_any_runtime_obligation`: Proves static entry evidence `0xFC0BD071` cannot discharge any of the 7 runtime obligations.
- `test_execution_witness_citing_only_port11a_static_evidence_fails`: Negative test confirming an `EXECUTION_WITNESS` citing PORT11A static ROM evidence with empty addresses is rejected with `RULE_STATIC_CANNOT_DISCHARGE_RUNTIME`.
- `test_runtime_obligations_with_missing_citations_fail`: Negative test confirming `VERIFIED/RUNTIME` artifacts with missing citations fail across all 7 runtime obligations.
- `test_runtime_obligations_with_untracked_citations_fail`: Negative test confirming `VERIFIED/RUNTIME` artifacts with untracked citations fail across all 7 runtime obligations.
- `test_runtime_obligations_with_forbidden_firmware_citations_fail`: Negative test confirming `VERIFIED/RUNTIME` artifacts citing `firmware/` dumps fail across all 7 runtime obligations.
- `test_artifact_type_mismatch_fails`: Negative test confirming an artifact with mismatched `artifact_type` fails closed.
- `test_missing_citations_cause_failure`: Proves empty citations or blank paths fail closed.
- `test_untracked_citations_cause_failure`: Proves citations to untracked files (`sub/110e/boot.c`) fail closed.
- `test_local_only_citations_cause_failure`: Proves citations to local dumps (`firmware/dumps/...`) or `PORT-9A L1/L2` fail closed.
- `test_port9a_six_stage_promotion_contract_completeness`: Verifies the 6-stage filesystem promotion structure, line citations in `port9a`, and mapping to `OBLIG-U2-03` and `OBLIG-U2-04`.
- `test_verify_i2_contract_consistency_helper`: Asserts agreement with PORT-9A model and PORT-9B I2 contract.
- `test_all_addresses_cited_in_tracked_docs`: Verifies address provenance and ensures zero new firmware addresses.
- `test_no_subprocess_imported`: Enforces standard library only and zero subprocess calls.

---

## 6. Concise Evidence-Request Checklist for Future Separately Authorized Research

The following bounded checklist defines the exact dynamic evidence required from future authorized research before U2 filesystem readiness can be promoted:
- [ ] **E-01**: Execution witness confirming `task_InitFileModules` was created and entered after scheduler dispatch in current boot generation.
- [ ] **E-02**: Dynamic media inspection witness confirming physical card presence and partition table validity, independent of `r0 == 0` from `sub_fc0d9ccc`.
- [ ] **E-03**: Storage mount completion proof from DryOS kernel, decoupled from UI event `0x5006`.
- [ ] **E-04**: Verified non-destructive file open/read capability on the mounted volume without contention or timeout prior to any CHDK file access.
- [ ] **E-05**: Dynamic warm-restart telemetry confirming SD host controller re-enumeration safety without bus lockup or drive corruption.

---

## 7. Safety Compliance & Invariants

- **Zero firmware modifications or flashing**.
- **Zero camera operations, SD card writes, or boot manipulation**.
- **Phase 0 read-only status strictly preserved**.
- **Preconditions invariant**: `GM110C_PRECONDITIONS.init_file_modules_entry_verified = False` remains strictly unchanged.
- **Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`**.
