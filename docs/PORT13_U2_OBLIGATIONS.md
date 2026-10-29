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
   - `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 220–228, 235, 251, 389, 402]` Task creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`), task name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack size `0x1000`, and Thumb entry pointer **`0xFC0BD071`** (instruction address **`0xFC0BD070`**) are verified in GM1.10C ROM slice `S2A`.
   - `[VERIFIED: docs/PORT13_REVIEW_U2.md:24–25; tools/port9a_runtime_lifecycle.py:119–120]` This static evidence proves **only** the existence, allocation parameters, and initial instruction address of the task. It does NOT satisfy any runtime obligation.
2. **Dynamic Runtime Readiness** (`UNKNOWN / NOT ESTABLISHED`):
   - `[UNKNOWN: tools/port9a_runtime_lifecycle.py:100, 105, 120; docs/PORT13_REVIEW_U2.md:24–25]` Static entry evidence proves **zero** dynamic properties: it does not prove that the DryOS task scheduler ever dispatched `task_InitFileModules`, that the physical SD card controller is powered, that card host negotiation succeeded, that a valid FAT32 partition exists, or that directory structures are readable without bus timeout.
   - `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284, 390; docs/PORT13_REVIEW_U2.md:25, 100, 142–144]` Callee 1 `sub_fc0d9ccc` contains **zero conditional branches of its own** and concludes with `movs r0, #0; pop {r4, pc}`; thus **`r0 = 0` is an unconditional constant on normal return**. Observing `r0 == 0` provides zero discrimination regarding physical media state.
   - `[VERIFIED: tools/port9a_runtime_lifecycle.py:301, 678–679; docs/PORT13_REVIEW_U2.md:26, 108, 145–147]` DryOS event `0x5006` is insufficient to establish filesystem readiness: $\text{Event}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$.

### 1.2 Remediation of PR #24 Flaws from `docs/PORT13_REVIEW_U2.md`
This document remedies all eight evidentiary and technical defects identified in [`docs/PORT13_REVIEW_U2.md:237–262`](PORT13_REVIEW_U2.md#L237-L262):
1. **Corrected Instruction Addresses** `[VERIFIED: docs/PORT13_REVIEW_U2.md:32–34, 101–103, 238–241; docs/PORT11A_GM110C_ROM_EVIDENCE.md:252, 254, 255, 259, 265–266]`:
   - Call to Callee 1 (`sub_fc0d9ccc`): Corrected from PR #24's erroneous `0xFC0BD074` to **`0xFC0BD072`** (`bl 0xFC0D9CCC`, raw bytes `1c f0 2b fe`; [`PORT11A:252`](PORT11A_GM110C_ROM_EVIDENCE.md#L252)).
   - Call to Callee 2 (`sub_fc0d9cf6`): Corrected from PR #24's erroneous `0xFC0BD078` to **`0xFC0BD086`** (`bl 0xFC0D9CF6`, raw bytes `1c f0 36 fe`; [`PORT11A:259`](PORT11A_GM110C_ROM_EVIDENCE.md#L259)). At `0xFC0BD078`, the actual instruction is `movw r5, #0x5006` (`45 f2 06 05`; [`PORT11A:254`](PORT11A_GM110C_ROM_EVIDENCE.md#L254)).
   - Task Epilogue/Exit: Corrected from PR #24's erroneous `0xFC0BD07C` (which is `beq 0xFC0BD086`; [`PORT11A:255`](PORT11A_GM110C_ROM_EVIDENCE.md#L255)) to tail branch **`0xFC0BD096: b.w 0xFC35B93C`** and epilogue **`0xFC0BD09A: pop {r4, r5, r6, pc}`** ([`PORT11A:265–266`](PORT11A_GM110C_ROM_EVIDENCE.md#L265-L266)).
2. **De-escalated Event `0x5006` Dispatch Mechanism** `[VERIFIED: docs/PORT13_REVIEW_U2.md:43–44, 109, 242–245; docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265; tools/port9a_runtime_lifecycle.py:301, 678–679]`:
   - PR #24's assertion that event `0x5006` is dispatched via asynchronous message queues is removed. The target subroutine `0xFC35B93C` lies outside slice `S2A` and its internal mechanism is strictly **`UNKNOWN`** ([`PORT11A:258, 265`](PORT11A_GM110C_ROM_EVIDENCE.md#L258)). The obligation is grounded strictly in what is verified: event `0x5006` is insufficient for filesystem readiness ([`port9a_runtime_lifecycle.py:301, 678–679`](../tools/port9a_runtime_lifecycle.py#L301)).
3. **Aligned Lifecycle Promotion & Added Non-Destructive Open/Read** `[VERIFIED: docs/PORT13_REVIEW_U2.md:45–47, 112, 161–167, 246–248; tools/port9a_runtime_lifecycle.py:302–303]`:
   - PR #24's uncodified driver internals (idle DMA, BPB parsing, descriptor allocation) are labeled as proposed extensions. This document explicitly includes the tracked requirement from [`tools/port9a_runtime_lifecycle.py:302–303`](../tools/port9a_runtime_lifecycle.py#L302): **verified non-destructive file open/read capability on mounted volume without contention or timeout** for `fs_io_ready`.
4. **Contextualized Historical Citation** `[VERIFIED: docs/PORT13_REVIEW_U2.md:48–49, 110, 249–250; docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190; docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94]`:
   - Untracked citation `platform/g3x/sub/110e/boot.c` is replaced with tracked secondary evidence in [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190`](PORT5B_HISTORICAL_BOOT_COMPARISON.md#L190) (`P:1769–1795`) and [`docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`](PORT5A_RANMA_PORT_RECOVERY.md#L93-L94).
5. **De-escalated Callee 2 (`sub_fc0d9cf6`) Semantics** `[VERIFIED: docs/PORT13_REVIEW_U2.md:50–51, 107, 251–253; docs/PORT11A_GM110C_ROM_EVIDENCE.md:254–265, 286, 289]`:
   - Unverified claims that `sub_fc0d9cf6` performs "Mount completion / event dispatch" are removed. Visible event `0x5006` calls reside directly in `task_InitFileModules` ([`PORT11A:254–265`](PORT11A_GM110C_ROM_EVIDENCE.md#L254-L265)), while the internal behavior of `sub_fc0d9cf6`'s nested callees remains strictly **`UNKNOWN`** ([`PORT11A:286, 289`](PORT11A_GM110C_ROM_EVIDENCE.md#L286)).
6. **Qualified Warm-Restart State & Decoupled Reset Ownership** `[INFERRED / VERIFIED: docs/PORT13_REVIEW_U2.md:52–53, 114–116, 254–256; docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29, 54–68]`:
   - SD hardware bus/card-host state persistence across warm restart is classified as **`INFERRED / PLAUSIBLE`** per [`docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29`](RESTART_SD_HOST_AUDIT.md#L11-L18). The lifecycle requirement is decoupled from unverified reset ownership assignment to `InitFileModules` (**`UNKNOWN / NOT ESTABLISHED`** per [`RESTART_SD_HOST_AUDIT.md:54–68`](RESTART_SD_HOST_AUDIT.md#L54-L68)).
7. **Removed Callee 1 Storage Init Semantics** `[VERIFIED: docs/PORT13_REVIEW_U2.md:35–38, 104, 257–259; docs/PORT11A_GM110C_ROM_EVIDENCE.md:289, 406]`:
   - Description asserting Callee 1 performs "Lower-level storage/host controller init" is marked strictly **`UNKNOWN / UNSUPPORTED`** per [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:289, 406`](PORT11A_GM110C_ROM_EVIDENCE.md#L289).
8. **Removed `task_Startup` Invocation Edge** `[VERIFIED: docs/PORT13_REVIEW_U2.md:39–42, 105, 260–262; docs/PORT11A_GM110C_ROM_EVIDENCE.md:81, 407]`:
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
| **Creator `sub_fc0bd0b4`** | Loads `"InitFileModules"`, prio `0x19`, stack `0x1000`, entry `0xFC0BD071` ([`PORT11A:220–228`](PORT11A_GM110C_ROM_EVIDENCE.md#L220-L228)). | `[STATIC_VERIFIED: PORT11A:220–228]` Static task identity, creation parameters, and initial execution vector. | `[UNKNOWN: PORT11A:81, 407]` Whether `sub_fc0bd0b4` was invoked during boot (`UNKNOWN` caller graph). |
| **Thumb Entry `0xFC0BD071`** | Slice `S2A` instruction bytes at `0xFC0BD070` ([`PORT11A:251`](PORT11A_GM110C_ROM_EVIDENCE.md#L251)). | `[STATIC_VERIFIED: PORT11A:251]` Statically verified entry point of `task_InitFileModules`. | `[UNKNOWN: PORT13_REVIEW_U2.md:24–25]` Does **not** prove scheduler dispatch, CPU execution, or host controller power/clocking. |
| **Callee 1 `sub_fc0d9ccc` Return** | Slice `S2B`: zero conditional branches, ends with `movs r0, #0; pop {r4, pc}` ([`PORT11A:281–284`](PORT11A_GM110C_ROM_EVIDENCE.md#L281-L284)). | `[STATIC_VERIFIED: PORT11A:281–284]` Static return sequence: normal return yields constant `r0 = 0` (`movs r0, #0; pop {r4, pc}` at `0xFC0D9CF2..0xFC0D9CF5`). Actual runtime completion and absence of CPU faults remains **`UNKNOWN`**. | `[UNKNOWN: PORT13_REVIEW_U2.md:25, 100, 142–144]` **Cannot prove storage mount readiness**: `r0 = 0` is unconditionally hardcoded; provides zero dynamic media discrimination. Does not prove the epilogue was reached at runtime without a CPU fault. |
| **Callee 2 `sub_fc0d9cf6` Call** | Invoked sequentially at `0xFC0BD086` ([`PORT11A:259`](PORT11A_GM110C_ROM_EVIDENCE.md#L259)). | `[STATIC_VERIFIED: PORT11A:259]` Static sequential invocation in task body. | `[UNKNOWN: PORT11A:286, 289]` Does not prove FAT partition mounted, cluster tables valid, or file handles writable. Nested callees are `UNKNOWN`. |
| **Event `0x5006` Call** | Target routine `0xFC35B93C` called with `0x5006` ([`PORT11A:258, 265`](PORT11A_GM110C_ROM_EVIDENCE.md#L258)). | `[STATIC_VERIFIED: PORT11A:258, 265]` Instruction call to routine `0xFC35B93C`. | `[UNKNOWN: tools/port9a_runtime_lifecycle.py:301, 678–679; PORT13_REVIEW_U2.md:26]` Does not prove filesystem readiness: event `0x5006` is insufficient for filesystem I/O. Queuing mechanism is `UNKNOWN`. |

---

## 3. Formal U2 Proof Obligations Catalog

The following eight proof obligations are codified in [`tools/port13_u2_obligations.py`](../tools/port13_u2_obligations.py). Every obligation carries an ID, an epistemic status, an architectural kind (static vs runtime), required evidence specifications, and citations strictly to Git-tracked files.

### 3.1 Obligation OBLIG-U2-01: Static Task Entry Vector
- **ID**: `OBLIG-U2-01`
- **Kind**: **`STATIC`**
- **Current Status**: **`VERIFIED`** `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21; tools/port9a_runtime_lifecycle.py:119; tools/port9b_runtime_contract.py:79]`
- **Requirement Source**: Established requirement in PORT-9A (`tools/port9a_runtime_lifecycle.py:119`) and PORT-9B (`tools/port9b_runtime_contract.py:79`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:296–297; docs/PORT13_REVIEW_U2.md:24–25]`
- **Requirement Source**: Established requirement in PORT-9A stage `task_started` (`tools/port9a_runtime_lifecycle.py:296–297, 661–668`). Epistemic separation reinforced in review (`docs/PORT13_REVIEW_U2.md:24–25`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:298–299; docs/PORT13_REVIEW_U2.md:25, 100, 142–144]`
- **Requirement Source**: Established requirement in PORT-9A stage `init_returned_normally` (`tools/port9a_runtime_lifecycle.py:298–299, 670–706`), refined by Slice S2B evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:300–301; docs/PORT13_REVIEW_U2.md:26, 43–44, 108–109]`
- **Requirement Source**: Established requirement in PORT-9A stage `mount_observed` (`tools/port9a_runtime_lifecycle.py:300–301, 678–679, 708–737`), reinforced by decoupling analysis in review (`docs/PORT13_REVIEW_U2.md:26, 43–44`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:302–303; docs/PORT13_REVIEW_U2.md:45–47, 161–167]`
- **Requirement Source**: Established requirement in PORT-9A stage `fs_io_ready` (`tools/port9a_runtime_lifecycle.py:302–303, 739–765`), grounded in historical port defect analysis (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190; docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`). Mathematical causal sequencing formalized in this task `[PROPOSED (this document)]`.
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:262–263, 686–694; docs/PORT13_REVIEW_U2.md:27, 159, 212]`
- **Requirement Source**: Established requirement in PORT-9A (`tools/port9a_runtime_lifecycle.py:262–263, 686–694`). Fail-closed state machine halting verified in review (`docs/PORT13_REVIEW_U2.md:27, 159, 212`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:250, 343–366, 394–400; docs/PORT13_REVIEW_U2.md:113, 213]`
- **Requirement Source**: Established requirement in PORT-9A (`tools/port9a_runtime_lifecycle.py:250, 343–366, 394–400`). Monotonic binding formalization in review (`docs/PORT13_REVIEW_U2.md:113, 213`).
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
- **Current Status**: **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:304–306; tools/port9b_runtime_contract.py:79–80; docs/PORT13_REVIEW_U2.md:52–53, 114–116]`
- **Requirement Source**: Established requirement in PORT-9A stage `warm_restart_safe` (`tools/port9a_runtime_lifecycle.py:304–306, 767–805`) and PORT-9B Fact U2 (`tools/port9b_runtime_contract.py:79–80`). Qualified retention (`[INFERRED]`) and decoupled reset ownership (`[VERIFIED]`) from restart SD host audit (`docs/RESTART_SD_HOST_AUDIT.md:16, 56`).
- **Statement**: Resolution of warm-restart SD host/card preconditions (P11, P12, P13, P15) with host retention qualified as plausible and reset ownership decoupled from `InitFileModules`.
- **Required Evidence**:
  - *Artifact Type*: `WARM_RESTART_AUDIT_WITNESS`
  - *What It Must Show*: Precondition resolution for SD host and card state across warm restart confirming re-enumeration safety without bus lockup.
- **Tracked Citations**:
  - [`tools/port9a_runtime_lifecycle.py:304–306`](../tools/port9a_runtime_lifecycle.py#L304-L306) (`FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` stage `warm_restart_safe`).
  - [`tools/port9a_runtime_lifecycle.py:767–805`](../tools/port9a_runtime_lifecycle.py#L767-L805) (`RuntimeLifecycle.record_warm_restart_storage_safety()`).
  - [`tools/port9b_runtime_contract.py:79–80`](../tools/port9b_runtime_contract.py#L79-L80) (Fact U2 encompasses warm-restart storage safety).
  - [`docs/RESTART_SD_HOST_AUDIT.md:16`](RESTART_SD_HOST_AUDIT.md#L16) (Host state retention is plausible `[INFERRED]`; intervening routines `0xFC41870C` and `[0x4000]` `UNKNOWN`).
  - [`docs/RESTART_SD_HOST_AUDIT.md:56`](RESTART_SD_HOST_AUDIT.md#L56) (`SD1stInit` task entry `0x010E17A5`; reset ownership decoupled from `InitFileModules`).
  - [`docs/PORT13_REVIEW_U2.md:52–53, 114–116, 254–256`](PORT13_REVIEW_U2.md#L52-L53) (Decouple lifecycle requirement from unverified reset ownership assignment).

---

## 4. Consistency with Runtime Lifecycle and Offline Contracts

### 4.1 Consistency with `tools/port9a_runtime_lifecycle.py`
The obligations model codified in `tools/port13_u2_obligations.py` strictly adheres to `tools/port9a_runtime_lifecycle.py`:
1. **Preconditions Invariant** `[VERIFIED: established in tools/port9a_runtime_lifecycle.py:100, 105; verified by test_port9a_preconditions_invariant (tests/test_port13_u2_obligations.py:481–486)]`:
   - `GM110C_PRECONDITIONS.init_file_modules_entry_verified` is strictly `False`.
2. **Static Evidence Separation** `[VERIFIED: established in tools/port9a_runtime_lifecycle.py:119–120; verified by test_port9a_static_evidence_profile (tests/test_port13_u2_obligations.py:488–499)]`:
   - `GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry` is `STATIC_VERIFIED`, while `GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness` is strictly `UNKNOWN`.
3. **Six-Stage Promotion Requirements Completeness** `[VERIFIED: established in tools/port9a_runtime_lifecycle.py:293–306; verified by test_port9a_six_stage_promotion_contract_completeness (tests/test_port13_u2_obligations.py:509–549)]`:
   - All six stages of `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` are mapped directly to tracked line numbers in `port9a` and canonical proof obligations:
     - Stage 1: `task_created` `[VERIFIED: tools/port9a_runtime_lifecycle.py:294]` $\to$ `OBLIG-U2-01` (static creator vector) & `OBLIG-U2-02` (task creation witness).
     - Stage 2: `task_started` `[VERIFIED: tools/port9a_runtime_lifecycle.py:296]` $\to$ `OBLIG-U2-02` (execution witness after scheduler dispatch).
     - Stage 3: `init_returned_normally` `[VERIFIED: tools/port9a_runtime_lifecycle.py:298]` $\to$ `OBLIG-U2-03` (normal completion witness for both `sub_fc0d9ccc` and `sub_fc0d9cf6`).
     - Stage 4: `mount_observed` `[VERIFIED: tools/port9a_runtime_lifecycle.py:300]` $\to$ `OBLIG-U2-04` (independent kernel storage mount proof decoupled from event `0x5006`).
     - Stage 5: `fs_io_ready` `[VERIFIED: tools/port9a_runtime_lifecycle.py:302]` $\to$ `OBLIG-U2-05` (verified non-destructive open/read capability prior to CHDK file access).
     - Stage 6: `warm_restart_safe` `[VERIFIED: tools/port9a_runtime_lifecycle.py:304]` $\to$ `OBLIG-U2-08` (warm-restart SD host/card state preconditions resolution).
4. **Programmatic Stage Correspondence Mapping** `[PROPOSED (this document): implemented in tools/port13_u2_obligations.py:814–844; verified by test_port9a_six_stage_promotion_contract_completeness (tests/test_port13_u2_obligations.py:509–549)]`:
   - The dictionary `PORT9A_SIX_STAGE_CORRESPONDENCE` formalizes the exact line citations in `port9a` for automated regression testing.

### 4.2 Consistency with `tools/port9b_runtime_contract.py`
The obligations model aligns with `tools/port9b_runtime_contract.py`:
1. **Fact U2 in Registry** `[VERIFIED: established in tools/port9b_runtime_contract.py:79–80; verified by test_port9b_fact_u2_consistency (tests/test_port13_u2_obligations.py:501–507)]`:
   - Fact U2 registers `init_file_modules_entry_verified` as: *"InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety"*. Fact U2 remains address-free and unverified in Phase 0.
2. **Contract C3.gate** `[VERIFIED: established in tools/port9b_runtime_contract.py:455–456; verified by tests/test_port9b_runtime_contract.py:126–145]`:
   - Ensures that activation markers (`REPLACEMENTS["InitFileModules"]` or bare `core_spytask_can_start`) are absent in default platform sources.
3. **Contract C6.fs_readiness_contract** `[VERIFIED: established in tools/port9b_runtime_contract.py:529–564; verified by tests/test_port9b_runtime_contract.py:240–280]`:
   - Verifies the 6-stage filesystem promotion structure and default fail-closed invariants.
4. **Automated Cross-Module Contract Verification** `[PROPOSED (this document): implemented in tools/port13_u2_obligations.py:898–934; verified by test_verify_i2_contract_consistency_helper (tests/test_port13_u2_obligations.py:551–555)]`:
   - The helper `verify_i2_contract_consistency()` programmatically verifies that `GM110C_PRECONDITIONS.init_file_modules_entry_verified is False`, static evidence profiles match, Fact U2 is defined, and the 6 filesystem promotion stages match without modifying `port9a` or `port9b`.

---

## 5. Implementation Architecture & Negative Tests

### 5.1 Fail-Closed Evaluator Implementation Architecture
The evaluator in [`tools/port13_u2_obligations.py`](../tools/port13_u2_obligations.py) implements the following structural fail-closed guarantees:

1. **Full Value Equality Canonical Set Enforcement** `[VERIFIED: implemented in tools/port13_u2_obligations.py:972–984, 1328–1375; verified by tests/test_port13_u2_obligations.py:611–659]`:
   - `evaluate()` evaluates aggregate filesystem readiness, which strictly requires the **complete canonical obligation set** (`OBLIG-U2-01` through `OBLIG-U2-08`) compared by **full value equality** against `DEFAULT_U2_OBLIGATIONS` (`target_obligations == DEFAULT_U2_OBLIGATIONS`).
   - If any obligation is missing, extra, or if IDs do not match, aggregate evaluation fails with `RULE_INCOMPLETE_OBLIGATION_SET`.
   - If IDs match but any obligation field (`id`, `statement`, `kind`, `status`, `required_evidence`, `citations`, `notes`) differs from the canonical definition (such as the reviewer's substitution exploit or flipping `kind` from RUNTIME to STATIC), aggregate evaluation fails with `RULE_NONCANONICAL_OBLIGATION`.
   - In isolation, `evaluate_obligation()` also verifies that any obligation claiming a canonical ID matches `CANONICAL_OBLIGATIONS_MAP[obligation.id]` by full value equality (`tools/port13_u2_obligations.py:972–984`), failing with `RULE_NONCANONICAL_OBLIGATION` if modified.

2. **Positive Runtime Witness Allowlist (`TRUSTED_RUNTIME_WITNESSES`)** `[VERIFIED: implemented in tools/port13_u2_obligations.py:286, 1200–1229; verified by tests/test_port13_u2_obligations.py:661–745]`:
   - Existing tracked documentation (`docs/`), source files (`chdk-port/`, `vendor/`), reviews (`docs/PORT13_REVIEW_U2.md`), or Python tools (`tools/`) on `origin/main` are static offline materials and must NEVER discharge any runtime obligation, regardless of caller-supplied labels (`kind=RUNTIME`, `status=VERIFIED`, matching `artifact_type`).
   - This invariant is enforced as a **positive allowlist**, not a denylist: `tools/port13_u2_obligations.py:286` defines the module-level registry `TRUSTED_RUNTIME_WITNESSES: frozenset[str] = frozenset()`.
   - In `evaluate_obligation()` (`tools/port13_u2_obligations.py:1200–1229`), any artifact submitted for a runtime obligation (`obligation.is_runtime`) whose `artifact_id` and citation path are not in `TRUSTED_RUNTIME_WITNESSES` is rejected with `RULE_UNTRUSTED_RUNTIME_PROVENANCE`.
   - Because `TRUSTED_RUNTIME_WITNESSES` is strictly empty in shipped code, **aggregate ready (`is_ready = True`) is structurally unreachable** from shipped data or from any caller-supplied artifacts citing repository files. Populating any entry in this registry requires physical hardware execution, dynamic telemetry capture, and an authorized, human-reviewed PR following phase transition.

3. **Static Evidence Rejection for Runtime Obligations** `[VERIFIED: implemented in tools/port13_u2_obligations.py:427–474, 1188–1199; verified by tests/test_port13_u2_obligations.py:216–287]`:
   - The statically evidenced Thumb entry pointer `0xFC0BD071` (instruction address `0xFC0BD070`, ROM slice `S2A`) may satisfy ONLY `OBLIG-U2-01`.
   - `is_static_evidence()` (`tools/port13_u2_obligations.py:427–474`) detects static ROM artifacts, ROM slices, disassembly descriptions, ROM address references, and PORT11A citations.
   - Any static evidence submitted for a runtime obligation is rejected with `RULE_STATIC_CANNOT_DISCHARGE_RUNTIME` (`tools/port13_u2_obligations.py:1188–1199`).

4. **Citation Authenticity, Path Restrictions, and Content Integrity** `[VERIFIED: implemented in tools/port13_u2_obligations.py:989–1060, 1073–1141; verified by tests/test_port13_u2_obligations.py:297–471]`:
   - Supporting citations on obligations and submitted evidence artifacts must be non-empty (`RULE_MISSING_CITATIONS`).
   - Citations must point to files tracked in `ORIGIN_MAIN_TRACKED_FILES` (`RULE_UNTRACKED_PATH`).
   - Citations referencing forbidden local-only paths (`firmware/`, `PORT-9A L1/L2`) are rejected with `RULE_FORBIDDEN_LOCAL_PATH`.
   - Pinned files (`PINNED_FILE_HASHES`, `tools/port13_u2_obligations.py:150–159`) are validated against SHA-256 digests; tampering triggers `RULE_CONTENT_HASH_MISMATCH`. Missing files on disk trigger `RULE_MISSING_CITED_PATH`.
   - Evidence artifact types must match `obligation.required_evidence.artifact_type` exactly; mismatches trigger `RULE_ARTIFACT_TYPE_MISMATCH`.

5. **Strict Address Provenance Verification** `[VERIFIED: implemented in tools/port13_u2_obligations.py:294–334, 853–896; verified by tests/test_port13_u2_obligations.py:577–599]`:
   - Zero new firmware addresses: every firmware address referenced in the module is registered in `TRACKED_ADDRESS_CITATIONS` (`tools/port13_u2_obligations.py:294–334`) and verified against exact document line references on disk.

### 5.2 Test Suite Verification Catalog
The offline test suite in [`tests/test_port13_u2_obligations.py`](../tests/test_port13_u2_obligations.py) comprises 33 unit tests validating the entire contract:

1. `test_evaluate_returns_not_ready_for_shipped_data` `[VERIFIED: tests/test_port13_u2_obligations.py:79–94]`: Confirms `is_ready == False`, `status == "not-ready"`, 7 unknown runtime obligations, 1 static verified obligation, and `is_fail_closed == True`.
2. `test_there_is_no_path_to_ready_from_shipped_data` `[VERIFIED: tests/test_port13_u2_obligations.py:96–118]`: Proves no path to ready from shipped data; each single obligation evaluated alone fails aggregate readiness with `RULE_INCOMPLETE_OBLIGATION_SET`.
3. `test_every_strict_subset_of_canonical_set_returns_not_ready` `[VERIFIED: tests/test_port13_u2_obligations.py:120–169]`: Verifies every strict subset (length 1 through 7, including evaluating just `OBLIG-U2-01` with static evidence) and extra-obligation sets return `not-ready`.
4. `test_get_obligation_lookup` `[VERIFIED: tests/test_port13_u2_obligations.py:171–179]`: Verifies canonical obligation lookup by ID and returns `None` for nonexistent IDs.
5. `test_static_entry_evidence_satisfies_static_entry_obligation` `[VERIFIED: tests/test_port13_u2_obligations.py:198–214]`: Confirms static entry evidence satisfies `OBLIG-U2-01` in isolation while aggregate readiness remains `not-ready`.
6. `test_execution_witness_citing_only_port11a_static_evidence_fails` `[VERIFIED: tests/test_port13_u2_obligations.py:216–237]`: Negative test confirming an `EXECUTION_WITNESS` citing PORT11A static ROM evidence with empty addresses is rejected with `RULE_STATIC_CANNOT_DISCHARGE_RUNTIME`.
7. `test_static_entry_evidence_cannot_discharge_any_runtime_obligation` `[VERIFIED: tests/test_port13_u2_obligations.py:239–251]`: Proves static entry evidence `0xFC0BD071` cannot discharge any of the 7 runtime obligations.
8. `test_static_evidence_detection_variants` `[VERIFIED: tests/test_port13_u2_obligations.py:253–287]`: Confirms diverse static artifact representations (mislabeled kind, static artifact type, static entry address, offline disassembly description) are rejected for runtime obligations.
9. `test_missing_citations_cause_failure` `[VERIFIED: tests/test_port13_u2_obligations.py:297–323]`: Proves empty citations tuple or blank paths fail closed with `RULE_MISSING_CITATIONS`.
10. `test_untracked_citations_cause_failure` `[VERIFIED: tests/test_port13_u2_obligations.py:325–338]`: Proves citations to untracked files (`platform/g3x/sub/110e/boot.c`) fail closed with `RULE_UNTRACKED_PATH`.
11. `test_local_only_citations_cause_failure` `[VERIFIED: tests/test_port13_u2_obligations.py:340–366]`: Proves citations to local dumps (`firmware/dumps/...`) or `PORT-9A L1/L2` fail closed with `RULE_FORBIDDEN_LOCAL_PATH`.
12. `test_runtime_obligations_with_missing_citations_fail` `[VERIFIED: tests/test_port13_u2_obligations.py:368–388]`: Negative test confirming `VERIFIED/RUNTIME` artifacts with missing citations fail across all 7 runtime obligations.
13. `test_runtime_obligations_with_untracked_citations_fail` `[VERIFIED: tests/test_port13_u2_obligations.py:390–410]`: Negative test confirming `VERIFIED/RUNTIME` artifacts with untracked citations fail across all 7 runtime obligations.
14. `test_runtime_obligations_with_forbidden_firmware_citations_fail` `[VERIFIED: tests/test_port13_u2_obligations.py:412–432]`: Negative test confirming `VERIFIED/RUNTIME` artifacts citing `firmware/` dumps fail across all 7 runtime obligations.
15. `test_artifact_type_mismatch_fails` `[VERIFIED: tests/test_port13_u2_obligations.py:434–453]`: Negative test confirming an artifact with mismatched `artifact_type` fails closed with `RULE_ARTIFACT_TYPE_MISMATCH`.
16. `test_missing_file_on_disk_fails_closed` `[VERIFIED: tests/test_port13_u2_obligations.py:455–463]`: Proves cited files missing on disk fail closed with `RULE_MISSING_CITED_PATH`.
17. `test_tampered_content_hash_fails_closed` `[VERIFIED: tests/test_port13_u2_obligations.py:465–475]`: Proves content hash tampering at pinned paths fails with `RULE_CONTENT_HASH_MISMATCH`.
18. `test_port9a_preconditions_invariant` `[VERIFIED: tests/test_port13_u2_obligations.py:481–486]`: Asserts `GM110C_PRECONDITIONS.init_file_modules_entry_verified is False`.
19. `test_port9a_static_evidence_profile` `[VERIFIED: tests/test_port13_u2_obligations.py:488–499]`: Asserts static entry is `STATIC_VERIFIED` while SD/FAT mount readiness is `UNKNOWN` in PORT-9A.
20. `test_port9b_fact_u2_consistency` `[VERIFIED: tests/test_port13_u2_obligations.py:501–507]`: Asserts PORT-9B Fact U2 is defined and maps to `init_file_modules_entry_verified`.
21. `test_port9a_six_stage_promotion_contract_completeness` `[VERIFIED: tests/test_port13_u2_obligations.py:509–549]`: Verifies all 6 promotion stages, exact line numbers in `port9a`, and mapping to `OBLIG-U2-03` and `OBLIG-U2-04`.
22. `test_verify_i2_contract_consistency_helper` `[VERIFIED: tests/test_port13_u2_obligations.py:551–555]`: Asserts `verify_i2_contract_consistency()` passes against tracked repository code.
23. `test_tools_port9a_and_port9b_are_unmodified` `[VERIFIED: tests/test_port13_u2_obligations.py:557–571]`: Cryptographically asserts `port9a_runtime_lifecycle.py` and `port9b_runtime_contract.py` match pinned SHA-256 digests.
24. `test_all_addresses_cited_in_tracked_docs` `[VERIFIED: tests/test_port13_u2_obligations.py:577–581]`: Asserts `verify_address_provenance()` passes without error.
25. `test_address_registration_completeness` `[VERIFIED: tests/test_port13_u2_obligations.py:583–599]`: Asserts critical U2 firmware addresses are registered in `TRACKED_ADDRESS_CITATIONS`.
26. `test_canonical_obligation_substitution_exploit_fails` `[VERIFIED: tests/test_port13_u2_obligations.py:611–640]`: Proves that substituting canonical obligations with 8 copies of `OBLIG-U2-01` fails aggregate readiness with `RULE_NONCANONICAL_OBLIGATION` and sets `status = "not-ready"`.
27. `test_single_obligation_kind_flipped_fails` `[VERIFIED: tests/test_port13_u2_obligations.py:642–659]`: Proves that flipping `kind` from RUNTIME to STATIC on a single obligation fails aggregate readiness with `RULE_NONCANONICAL_OBLIGATION`.
28. `test_relabelled_runtime_artifacts_exploit_fails` `[VERIFIED: tests/test_port13_u2_obligations.py:661–702]`: Proves that 7 relabeled `VERIFIED/RUNTIME` artifacts citing `docs/PORT13_REVIEW_U2.md:24` fail with `RULE_UNTRUSTED_RUNTIME_PROVENANCE` and evaluate to `not-ready`.
29. `test_sample_of_tracked_docs_and_tools_rejected_as_runtime_citations` `[VERIFIED: tests/test_port13_u2_obligations.py:704–740]`: Loops over a representative sample of 10 tracked docs/tools (`docs/PORT13_REVIEW_U2.md`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, `tools/port9a_runtime_lifecycle.py`, `tools/port9b_runtime_contract.py`, `README.md`, `docs/SAFETY.md`, `docs/RESTART_SD_HOST_AUDIT.md`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `tools/port13_u2_obligations.py`, `AGENTS.md`) and asserts that every one is rejected with `RULE_UNTRUSTED_RUNTIME_PROVENANCE`.
30. `test_trusted_runtime_witnesses_is_empty_in_shipped_code` `[VERIFIED: tests/test_port13_u2_obligations.py:742–745]`: Asserts that `TRUSTED_RUNTIME_WITNESSES` is strictly empty `frozenset()`.
31. `test_no_subprocess_imported` `[VERIFIED: tests/test_port13_u2_obligations.py:751–753]`: Enforces zero subprocess imports in `tools/port13_u2_obligations.py`.
32. `test_standard_library_only` `[VERIFIED: tests/test_port13_u2_obligations.py:755–759]`: Enforces standard library only (no pytest, requests, capstone, ghidra, keystone, or numpy).
33. `test_all_obligations_serialize_to_dict_and_json` `[VERIFIED: tests/test_port13_u2_obligations.py:761–769]`: Asserts all obligations and results serialize cleanly to JSON.

---

## 6. Concise Evidence-Request Checklist for Future Separately Authorized Research

The following bounded checklist defines the exact dynamic evidence required from future authorized research before U2 filesystem readiness can be promoted. Each item clearly distinguishes established requirements from newly proposed requirements and carries exact Git-tracked citations:

- [ ] **E-01**: `[UNKNOWN / PROPOSED (this document)]` **Scheduler Dispatch Execution Witness**:
  - *Requirement Status*: Extending established stage `task_started` requirement ([`tools/port9a_runtime_lifecycle.py:296–297, 661–668`](../tools/port9a_runtime_lifecycle.py#L296)).
  - *Description*: Dynamic execution witness confirming `task_InitFileModules` was created by `sub_fc0bd0b4` and entered at `0xFC0BD070` (`0xFC0BD071`) after DryOS scheduler dispatch in the current `boot_generation` context.
  - *Supporting Citations*: [`tools/port9a_runtime_lifecycle.py:296–297`](../tools/port9a_runtime_lifecycle.py#L296), [`docs/PORT13_REVIEW_U2.md:24–25`](PORT13_REVIEW_U2.md#L24-L25).

- [ ] **E-02**: `[UNKNOWN / PROPOSED (this document)]` **Independent Storage Media Inspection Witness**:
  - *Requirement Status*: Proposed requirement to resolve Callee 1 return indeterminacy established in [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284, 390`](PORT11A_GM110C_ROM_EVIDENCE.md#L21) and [`docs/PORT13_REVIEW_U2.md:25, 100, 142–144`](PORT13_REVIEW_U2.md#L25).
  - *Description*: Dynamic media inspection witness confirming physical card insertion detection, card controller clocking, and partition table / BPB validity, completely independent of `sub_fc0d9ccc`'s return value (since `sub_fc0d9ccc` concludes with `movs r0, #0; pop {r4, pc}` unconditionally on normal return and provides zero discrimination regarding card state).
  - *Supporting Citations*: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281–284, 390`](PORT11A_GM110C_ROM_EVIDENCE.md#L21), [`docs/PORT13_REVIEW_U2.md:25, 100, 142–144`](PORT13_REVIEW_U2.md#L25).

- [ ] **E-03**: `[UNKNOWN / PROPOSED (this document)]` **Storage Mount Completion Proof (Decoupled from Event 0x5006)**:
  - *Requirement Status*: Extending established stage `mount_observed` requirement ([`tools/port9a_runtime_lifecycle.py:300–301, 678–679, 708–737`](../tools/port9a_runtime_lifecycle.py#L300)).
  - *Description*: Kernel/storage driver state proof confirming DryOS FAT volume mount completion, decoupled from DryOS UI event `0x5006` (since $\text{Event}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$).
  - *Supporting Citations*: [`tools/port9a_runtime_lifecycle.py:300–301, 678–679`](../tools/port9a_runtime_lifecycle.py#L300), [`docs/PORT13_REVIEW_U2.md:26, 43–44, 108–109`](PORT13_REVIEW_U2.md#L26).

- [ ] **E-04**: `[UNKNOWN / established requirement in tools/port9a_runtime_lifecycle.py:302–303, 739–765]` **Verified Non-Destructive File Open/Read Capability**:
  - *Requirement Status*: Established requirement in PORT-9A stage `fs_io_ready` ([`tools/port9a_runtime_lifecycle.py:302–303, 739–765`](../tools/port9a_runtime_lifecycle.py#L302)), resolving historical CHDK boot defects documented in [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190`](PORT5B_HISTORICAL_BOOT_COMPARISON.md#L190) and [`docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`](PORT5A_RANMA_PORT_RECOVERY.md#L93-L94).
  - *Description*: Verified non-destructive file open/read test capability on the mounted volume without bus contention, error latching, or timeout, causally preceding any CHDK file access (`Fopen_Fut`, `Fread_Fut`, `Fwrite_Fut`, diskboot, or SpyTask file I/O):
    $$\text{InitFileModules complete} \prec \text{Mount Verified} \prec \text{fs\_io\_ready} \prec \text{First CHDK File Access}$$
  - *Supporting Citations*: [`tools/port9a_runtime_lifecycle.py:302–303, 739–765`](../tools/port9a_runtime_lifecycle.py#L302), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190`](PORT5B_HISTORICAL_BOOT_COMPARISON.md#L190), [`docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`](PORT5A_RANMA_PORT_RECOVERY.md#L93-L94), [`docs/PORT13_REVIEW_U2.md:45–47, 112, 161–167`](PORT13_REVIEW_U2.md#L45-L47).

- [ ] **E-05**: `[UNKNOWN / PROPOSED (this document)]` **Warm-Restart SD Host Re-Enumeration Telemetry**:
  - *Requirement Status*: Extending established stage `warm_restart_safe` requirement ([`tools/port9a_runtime_lifecycle.py:304–306, 767–805`](../tools/port9a_runtime_lifecycle.py#L304)) and Fact U2 ([`tools/port9b_runtime_contract.py:79–80`](../tools/port9b_runtime_contract.py#L79)). Grounded in SD host retention audit ([`docs/RESTART_SD_HOST_AUDIT.md:16, 56`](RESTART_SD_HOST_AUDIT.md#L16)).
  - *Description*: Dynamic telemetry confirming SD host controller and card state re-enumeration safety across warm restart without bus lockup or filesystem corruption, with controller retention qualified as plausible (`[INFERRED]`) and reset ownership decoupled from `InitFileModules` (`[VERIFIED]`).
  - *Supporting Citations*: [`tools/port9a_runtime_lifecycle.py:304–306`](../tools/port9a_runtime_lifecycle.py#L304), [`tools/port9b_runtime_contract.py:79–80`](../tools/port9b_runtime_contract.py#L79), [`docs/RESTART_SD_HOST_AUDIT.md:16, 56`](RESTART_SD_HOST_AUDIT.md#L16), [`docs/PORT13_REVIEW_U2.md:52–53, 114–116`](PORT13_REVIEW_U2.md#L52-L53).

---

## 7. Safety Compliance & Invariants

- `[VERIFIED: AGENTS.md:19–27; docs/SAFETY.md:1–20]` **Zero firmware modifications or flashing**: strictly read-only offline analysis.
- `[VERIFIED: AGENTS.md:19–27; docs/SAFETY.md:1–20]` **Zero camera operations, SD card writes, or boot manipulation**: no physical hardware trials.
- `[VERIFIED: AGENTS.md:19–27; docs/SAFETY.md:1–20]` **Phase 0 read-only status strictly preserved**: all verification is mathematical and structural.
- `[VERIFIED: tools/port9a_runtime_lifecycle.py:100, 105; tests/test_port13_u2_obligations.py:481–486]` **Preconditions invariant preserved**: `GM110C_PRECONDITIONS.init_file_modules_entry_verified = False` remains strictly unchanged.
- `[VERIFIED: docs/SAFETY.md:1–10; AGENTS.md:19–27]` **Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`**.
