# PORT-13 Review: PORT-12 Draft PR for U4 (SpyTask Launch Dependencies)

- **Date:** 2026-10-28 (Updated 2026-10-29)
- **Reviewer:** AgentBridge Worker (`port-13-offline-p13-review-u4-r2`)
- **Target PR:** PR #25 (Draft PR, tracking Issue #22 / PORT-12C)
- **Target Branch:** `research/port12c-spytask-u4` (`origin/research/port12c-spytask-u4`)
- **Target Head SHA:** `de792bd73b643e778dea3f3a80c53c8f2fdb0ead`
- **Base Branch:** `origin/main` (`581b1a4bb30456bf18c46dc4bcf61b0375aee251`)
- **Merge-Base:** `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (Branch is fast-forward compatible with `origin/main` HEAD)
- **Status:** **`READ_ONLY_REVIEW_COMPLETE`** (PR not modified, not merged)
- **Recommendation:** **`REVISE_BEFORE_MERGE`**

---

## 1. PR Identification and Scope

### 1.1 PR Metadata
- **Draft PR Number:** **#25** (identified via remote reference `refs/pull/25/head`)
- **Tracking Issue:** Issue #22 ("milestone PORT-12C (Issue #22)")
- **Branch:** `research/port12c-spytask-u4` (tracked at `origin/research/port12c-spytask-u4`)
- **Head Commit:** `de792bd73b643e778dea3f3a80c53c8f2fdb0ead`
- **Commit Message:** `docs(port12c): U4 SpyTask scheduling contract and gating failure traces (#22)`
- **Author:** `avp <avp@mac-buc.local>`
- **Date:** `Wed Oct 28 23:26:06 2026 +0900`
- **Ancestry Relation:** Fast-forward compatible with `origin/main` (`git merge-base --is-ancestor origin/main origin/research/port12c-spytask-u4` returned 0).

### 1.2 Delivered Files
The diff between `origin/main` and `origin/research/port12c-spytask-u4` consists strictly of two files:
1. `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd`: 159 lines defining the offline U4 lifecycle contract, parameter comparisons against Ranma's GM1.10E patch, dependency graph, execution context assumptions, synthetic failure traces, and ranked unknowns.
2. `tests/test_port12c_spytask_u4.py@de792bd`: 166 lines providing 9 deterministic offline unit tests validating GM1.10C baseline evidence invariants, synthetic failure traces 1–6, fail-closed timeout behavior, and positive path execution.

---

## 2. Separation of Static Evidence from Runtime Hook Placement and Start Ordering

A core requirement of the review is verifying whether PR #25 rigorously maintains the boundary between static ROM/ATCM disassembly evidence and unverified runtime hook placement or task launch ordering.

### 2.1 Static Evidence Audit: CreateTask Veneer and PhySw Entry vs Runtime Inferences
Tracked primary firmware evidence establishes two critical static anchor points in the GM1.10C ROM, both of which must be strictly isolated from dynamic runtime claims:

1. **CreateTask Veneer `0xFC31BBC4 -> relocated ATCM instruction 0xBFE14A3C`:**
   - **Tracked Evidence:** `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 61-62, 120-134, 384, 401`. Early boot `boot()` (`0xFC020040..0xFC020052`) copies 6,919 words (27,676 B) from ROM `0xFCEEF24C..0xFCEF5E67` to Cortex-R4 ATCM `0xBFE10800..0xBFE1741B`. The ARM veneer at `0xFC31BBC4` (Slice `S1B`) executes `ldr pc, [pc, #-4]` loading `0xBFE14A3D` from its literal pool (Thumb state at instruction address `0xBFE14A3C`, Slice `S1C`).
   - **Evidence Label:** **`STATIC_VERIFIED`**.
   - **Boundary Constraint:** This establishes **strictly** the static presence and relocation destination of the kernel task creator. It does **NOT** establish runtime hook placement, hook patch timing, ATCM I-cache/BPU coherence at patch time, or authorization to install a hook.
   - **PR #25 Audit:** PR #25 references ATCM kernel initialization in its overview diagram (`K3`), but correctly models U1 as unverified at runtime. It installs zero hooks and leaves `CreateTask_spytask` commented out in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:416`. PR #25 does not treat the static veneer as proof of runtime hook feasibility.

2. **PhySw Thumb Entry `0xFC1283AD`:**
   - **Tracked Evidence:** `docs/PORT11A_GM110C_ROM_EVIDENCE.md:22, 314, 324, 360, 391-392, 403`. Stock `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`) loads literal `[0xFC128708] = 0xFC1283AD` (Thumb entry pointer for `0xFC1283AC`, Slice `S3B`), passes `"PhySw"`, priority `0x17`, stack `0x800`, and invokes `blx 0xFC31BE8C` (`CreateTaskStrictly` veneer $\to$ `0xBFE154E8` $\to$ `0xBFE14A3C`).
   - **Evidence Label:** **`STATIC_VERIFIED`**.
   - **Boundary Constraint:** This establishes **strictly** the static entry pointer, task parameters, and creator subroutine for stock `PhySw`. It does **NOT** prove runtime task launch ordering, thread execution progression, or `SpyTask` start prerequisites.
   - **PR #25 Audit:** PR #25 cites `PhySw` priority `0x17` and stack `0x800` in its comparison table and diagrams (`S2`). It does not use the static entry pointer `0xFC1283AD` as proof of runtime execution. However, PR #25 assumes in its §2 diagram that `PhySw` executes strictly in a sequential startup chain preceding `InitFileModules`, which is an unverified caller ordering assumption (flagged in C08 below).

> [!IMPORTANT]
> **Static vs Runtime Boundary**: Neither static veneer `0xFC31BBC4 -> 0xBFE14A3C` nor PhySw entry `0xFC1283AD` establishes runtime hook placement or `SpyTask` start ordering. Both runtime hook installation and `SpyTask` scheduling dependencies remain strictly **`UNKNOWN` (U4)**.

### 2.2 Positive Decoupling Achievements in PR #25
1. **Explicit Identification of U4 as UNKNOWN:**
   - In `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd:23-25`, GM1.10C U4 parameterization (launch site, scheduling priority, stack size, and readiness dependencies) is explicitly marked **`UNKNOWN on GM1.10C (U4)`**.
   - In `tests/test_port12c_spytask_u4.py@de792bd:50-56`, `test_gm110c_baseline_evidence_u4_is_unknown` strictly asserts that `rt.GM110C_STATIC_EVIDENCE.u4_spytask_creation_priority_and_dependencies` is `EvidenceStatus.UNKNOWN`.
2. **Identification of Parameter Equality with Stock InitFileModules:**
   - PR #25 correctly notes that Ranma's candidate priority `0x19` matches stock `InitFileModules` (`0x19`, verified in Slice `S2A` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 224, 402`), raising awareness of potential concurrency and scheduling interactions.
3. **Fail-Closed Gating Without Legacy Bypass:**
   - In upstream CHDK (`core/main.c:136-156`), `SpyTask` waited up to 10 seconds for filesystem readiness and then started anyway. PR #25 explicitly enforces `spytask_gate_timeout() -> TaskState.FAILED`, ensuring no bypass occurs.
   - In Trace 3 (`test_trace3_gate_ready_but_u4_unknown_blocks_spytask`), PR #25 verifies that even if all 6 filesystem readiness stages are satisfied (`GateState.READY`), `SpyTask` is permanently blocked in `TaskState.WAITING_GATE` because U4 is `UNKNOWN`.
4. **Preservation of Dormant Prototype Code:**
   - PR #25 introduces zero code modifications to `boot_prototype.c` or runtime tooling. `CreateTask_spytask` remains commented out in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:416`.

### 2.3 Flagged Gaps and Conflations Requiring Remediation
Despite the strong fail-closed lifecycle model, several claims and diagrams in `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd` overstate or conflate static evidence with runtime launch ordering, or introduce unsupported assertions:

1. **Section 1.2: Unsupported Causal Claim on Legacy Timeout Bypass (C06b):**
   - In Section 1.2, PR #25 asserts:
     > "Unlike legacy CHDK ports (which timed out after 10 seconds and launched anyway, causing storage corruptions and kernel panics), our offline model enforces `spytask_gate_timeout() -> TaskState.FAILED`."
   - **Flagged Defect:** Asserting that the legacy timeout bypass *caused* storage corruptions and kernel panics is an unsupported causal claim (**`UNKNOWN` / `FAIL / UNSUPPORTED`**). While `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99` proves the upstream bypass behavior (`core/main.c:136, 156`), it explicitly labels the link between running without filesystem readiness and specific runtime symptoms as **`INFERRED`** (line 99: "The prototype's '10-second timeout' symptom is consistent with SpyTask running without the InitFileModules gate | INFERRED | docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204 (F5)"). Furthermore, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` (F5) explicitly documents that this causal link was **"not tested"**. Presenting this inference as established historical fact in PR #25 §1.2 violates repository grounding rules and must be removed or qualified.

2. **Section 2 Mermaid Diagram: Startup Sequence, Task Attribution, and Hook Placement (C08):**
   - In Section 2, the diagram groups the following under `subgraph Stock_Startup["task_Startup Dispatch (0xFC05B558)"]`:
     - `S1["Hardware Initialization"]`
     - `S2["sub_fc1283d2: CreateTask('PhySw')"]`
     - `S3["Battery & Power-on Evaluation"]`
     - `S4["sub_fc0bd0b4: CreateTask('InitFileModules')"]`
     with sequential flow `S1 --> S2 --> S3 --> S4`.
     Furthermore, line 73 places a dependency edge `S3 -.->|"CHDK Hook Placement"| SP1`.
   - **Flagged Defects:**
     - **Task Identity Misidentification (line 47):** The diagram label misidentifies `task_Startup` as `0xFC05B558`. Tracked primary evidence (`docs/PORT3C_RESTART_READINESS_MATRIX.md:224` [C02], `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38` [E05], and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:239-240, 358-366, 373`) proves that `0xFC05B558` is the initial bootstrap task (`sub_fc05b558`), which subsequently calls `CreateTask` to spawn `task_Startup` at entry `0xFC05B8FC`.
     - **Unsupported Runtime Hook Placement Edge (line 73):** Placing a 'CHDK Hook Placement' edge at `S3` is an unsupported runtime placement claim. As established in §2.1, static evidence for the CreateTask veneer (`0xFC31BBC4 -> 0xBFE14A3C`) and PhySw entry (`0xFC1283AD`) establishes static code presence only and does NOT establish runtime hook placement or authorization. This placement edge must be labelled **`UNKNOWN`**.
     - **Unverified Sequential Dispatch to `InitFileModules`:** The diagram implies that `task_Startup` directly calls `sub_fc0bd0b4` (`InitFileModules` creator). This is **unverified and contradicted** by `docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407`:
       > "In `task_Startup` (`0xFC05B8FC..0xFC05B957`), there is no direct `bl 0xFC0BD0B4` instruction; whether `task_Startup` reaches `sub_fc0bd0b4` indirectly is **`UNKNOWN`**."
       > "Exhaustive Caller Graph of `sub_fc0bd0b4` (`UNKNOWN`): Whether `task_Startup` or warm-restart initialization reaches `sub_fc0bd0b4` via indirect calls or uninspected dispatchers remains `UNKNOWN`."
       Placing `sub_fc0bd0b4` as `S4` inside `Stock_Startup` conflates the static discovery of `sub_fc0bd0b4` in Slice `S2A` with proof of startup ordering.

3. **Section 2 Mermaid Diagram: Contract Inconsistency Routing U4 UNKNOWN to FAILED (C11):**
   - Section 2 diagram specifies at line 77:
     `SP2 -- "Timeout or U4 UNKNOWN" --> SP4`
     where `SP4` is `TaskState.FAILED (Timeout / Fault Latch)`.
   - **Flagged Defect:** This contradicts the runtime contract implementation in `tools/port9a_runtime_lifecycle.py:869-878` and its Trace 3 test in `tests/test_port12c_spytask_u4.py@de792bd:102-103`. When U4 is `UNKNOWN`, `_try_run_spytask()` logs `spytask_blocked_u4` and returns, leaving `SpyTask` indefinitely in **`TaskState.WAITING_GATE`**. It does **not** transition to `TaskState.FAILED`. Transition to `FAILED` is reserved exclusively for explicit gate timeout (`spytask_gate_timeout()`, `tools/port9a_runtime_lifecycle.py:854-860`) or fault latches. Grouping "or U4 UNKNOWN" into `SP4` is a contract contradiction.

4. **Section 1.1: InitFileModules Stack Size Contradicted by ROM Slice S2A (C04):**
   - Section 1.1 states:
     > "In stock DryOS, normal tasks allocate between 1,024 B (`InitFileModules`) and 2,048 B (`PhySw`)."
   - **Flagged Defect:** This is **CONTRADICTED** by Slice `S2A` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 226, 402`. Disassembly of `sub_fc0bd0b4` at `0xFC0BD0D2` shows `41 f2 00 02` (`movw r2, #0x1000`), passing stack size **`0x1000` (4,096 B / 4 KiB)**, not 1,024 B.

5. **Section 3 Table: Unsupported Assertion of 'Safer' Priorities `0x1E` or `0x20` (C03c):**
   - Section 3 Table states:
     > "Priority `0x1E` or `0x20` is a safer candidate."
   - **Flagged Defect:** This claim is **UNKNOWN / UNSUPPORTED**. PR #25 presents no firmware disassembly or kernel analysis proving: (1) whether lower or higher numerical values represent higher scheduling priority in DryOS on DIGIC 6; (2) which priority levels are unallocated across the full Canon task table; or (3) what priority margins are required relative to UI, display, and storage tasks. This recommendation is unsupported conjecture.

6. **Section 1.1 & Section 3: Unverified Consequence of Priority Collision (C03b):**
   - Section 1.1 states:
     > "Under DryOS priority-based round-robin scheduling, running compute-heavy CHDK scripts at priority 25 risks starving filesystem write flushes and storage driver completion callbacks."
   - **Flagged Defect:** While parameter equality (`0x19 == 0x19`) is statically verified, the scheduling or starvation consequence is **`UNKNOWN`**. None of the cited sources establish DryOS kernel scheduling policy, time slicing, or preemption rules on DIGIC 6. Whether tasks of equal priority time-slice, run to completion/yield cooperatively, or follow strict FIFO ordering is unverified.

7. **Section 4: CPU Execution Context Contradicts Tracked ROM Decodings (C15):**
   - Section 4 Claim 1 states:
     > "Mode: DryOS user tasks execute in ARM **System Mode** (privileged, sharing User-mode register bank `r0–r14`) with **IRQ and FIQ enabled** (`CPSR[7:6] = 0b00`)."
   - **Flagged Defect:** This is **CONTRADICTED** by tracked primary evidence on `origin/main`:
     - `docs/PROJECT_STATE.md:168` and `docs/HANDOFF.md:306-309`: Traced DryOS task context creation in ROM (`0xFC05C5A8`) proves initial CPSR is loaded via `movs r0, #0xf3` and stored at `[sp, #0x3C]` with initial PC `0xBFE11723`. Initial CPSR is strictly `0x000000F3`: **Privileged Supervisor Mode** (`M = 0x13`), Thumb-2 (`T = 1`), IRQ masked (`I = 1`), FIQ masked (`F = 1`).
     - Task unmasking helper entered at `0xFC267BE6` (`mrs r1, apsr`) executes `bic r1, r1, #0x80` at `0xFC267BEA` and clears the IRQ mask via `msr cpsr_fsxc, r1` at `0xFC267BF2` (`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:225`), unmasking IRQ (`I = 0`) while keeping FIQ masked (`F = 1`). Thus `CPSR[7:6]` is `0b01`, NOT `0b00`.
     - Zero transitions to User or System mode occur (`docs/HANDOFF.md:309`). Tasks run in Supervisor Mode (`0x13`), not System Mode (`0x1F`).

8. **Section 4: Memory Pool Boundaries and Allocator Ownership Claims (C16):**
   - Section 4 Claim 2 states:
     > "The task stack (`0x2000` bytes) is dynamically allocated by the DryOS `CreateTask` kernel allocator from DryOS Pool 0 (`0x003C89B4..0x00600013`)."
   - **Flagged Defect:** On baseline `origin/main`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-211` already sets `size = 0x00600014 - base`, so `0x00600013` is the derived inclusive endpoint (label: **`VERIFIED` arithmetic**, cite `boot_prototype.c:209-211`). However, claiming dynamic allocator ownership by DryOS `CreateTask` for `SpyTask` stack (`0x2000` bytes) and designating this memory as "DryOS Pool 0" remain **`UNKNOWN`**. Furthermore, candidate fixed base `0x003C89B4` derives from `docs/HANDOFF.md:796` and parallel PR #23 (`origin/research/port12a-memory-ownership:docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md:43`, not line 52 which describes executable RAM). Claiming this heap pool dynamically allocates `SpyTask`'s stack conflates arithmetic bounds with unverified kernel allocator ownership.

9. **Section 3 Table: Continuation Branch Overstated as Verified Semantic Continuation (C13):**
   - Section 3 Table states:
     > "Continuation Branch: Tail branch `b.w sub_fc0d0126` (`P:1762`). `b.w sub_fc0d0126` (`C:434`). `VERIFIED_IN_EXISTING_DOCS` (Addresses match in both builds; semantic continuation)."
   - **Flagged Defect:** While the opcode `b.w sub_fc0d0126` is verified as present in prototype source at line 434, whether branching to `sub_fc0d0126` accomplishes successful continuation without crash or hang remains **`UNKNOWN`** (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:114`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:50`). Labeling it `VERIFIED_IN_EXISTING_DOCS` for "semantic continuation" conflates static instruction matching with verified runtime continuation.

10. **Section 3 Table: Prototype Launch Site Distinction (C12):**
    - Section 3 Table compares Ranma's GM1.10E launch site (end of `task_Startup_my`, line 484, after 19 subroutines including `sub_fc0bb6fe`) against `boot_prototype.c:411-416`.
    - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:409-416`, `CreateTask_spytask` is commented out immediately following `sub_fc1283d2` (`PhySw`), *before* the ten subroutines (`sub_fc2a75f6` through `sub_fc0bb6fe`).
    - The review table should explicitly note that the prototype's disabled site is mid-startup (post-PhySw), distinct from Ranma's post-initialization placement.

---

## 3. Consistency with I1/I3 Contracts and PORT-9A Integration Map (U4)

### 3.1 I1 Contract Consistency (`CreateTask_my` Interception)
- In `tools/port9b_runtime_contract.py:451-470`, check `C3.intercept` ensures that recognized activation markers for `CreateTask_my` or `hook_CreateTask` are absent from source unless authorized by verified preconditions.
- In `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:38-68`, I1 requires verified CreateTask prologue and literal before any intercept may be installed.
- **Evaluation:** PR #25 introduces no code hooks or intercept logic, leaving `C3.intercept` passing with no activation markers in source. It properly models I1 in its lifecycle tests.

### 3.2 I3 Contract Consistency (`SpyTask` Startup Ordering) — Qualified
- In `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:91-106`, I3 specifies that `SpyTask` is created in `WAITING_GATE` and advances to `RUNNING` only when `GateState` is `READY` with no latched fault. Timeout must transition `SpyTask` to `FAILED`, never to `RUNNING`.
- In `tools/port9b_runtime_contract.py:223-251`, `has_spytask_activation_marker` verifies that no active call to `CreateTask_spytask`, `spytask`, `core_spytask`, `_CreateTask`, or `"SpyTask"` exists outside dormant prototype wrappers (`C3.spytask`).
- In `tools/port9a_runtime_lifecycle.py:869-878`, when U4 is `UNKNOWN`, `_try_run_spytask()` logs `spytask_blocked_u4` and blocks progression, leaving `SpyTask` in `TaskState.WAITING_GATE`.
- **Evaluation (Qualified):**
  - **Unit Tests (`tests/test_port12c_spytask_u4.py@de792bd`):** Fully conform to I3. `test_trace3_gate_ready_but_u4_unknown_blocks_spytask` (lines 82-104) explicitly asserts `self.assertEqual(m.spytask, rt.TaskState.WAITING_GATE)` at line 102. `test_spytask_timeout_fails_instead_of_running` (lines 140-150) verifies that timeout induces `TaskState.FAILED`.
  - **Documentation Diagram Defect (`docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd:77`):** The Mermaid diagram routes `SP2 -- "Timeout or U4 UNKNOWN" --> SP4` (`TaskState.FAILED`). This contradicts both `tools/port9a_runtime_lifecycle.py:869-878` and the author's own Trace 3 unit test, which hold `SpyTask` in `WAITING_GATE` when U4 is `UNKNOWN`. The diagram must be corrected to decouple "Timeout" (which fails) from "U4 UNKNOWN" (which waits).

### 3.3 U4 Precondition Registration and Enforcement
- In `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:143`, U4 is registered as: "SpyTask creation point and priority on GM1.10C: UNKNOWN".
- In `tools/port9b_runtime_contract.py:83-85, 484-489, 547, 563`, U4 is address-free and strictly `UNKNOWN` in default validation.
- **Evaluation:** PR #25 respects this rule in its test suite and narrative. In `test_trace3_gate_ready_but_u4_unknown_blocks_spytask`, when all filesystem stages are simulated as ready but U4 remains `UNKNOWN`, `_try_run_spytask()` logs `spytask_blocked_u4` and blocks `SpyTask` execution.

---

## 4. Per-Claim Table with Labels, Tracked Citations, and Audit Verdicts

The following table reviews every distinct technical assertion made in `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd` and PR #25:

| # | Section | Claim / Assertion | PR #25 Label | Audit Label | Primary / Tracked Citation | Audit Verdict & Analysis |
|---|---|---|---|---|---|---|
| **C01** | §1.1 | Ranma created `SpyTask` at tail end of `task_Startup_my` with `CreateTask_spytask()` | `HISTORICAL_CANDIDATE` | `VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:113, 204` | **PASS**. Matches verified historical patch records (P:1759). Note: `docs/PATCH_AUDIT_110E.md:53-59` notes author's primary post claim regarding `InitFileModules` signaling CHDK start, but patch bytes are unrecovered; line 65 concerns unrecovered patch structure and does not establish `task_Startup_my`. |
| **C02** | §1.1 | U4 (launch point, priority, stack) is UNKNOWN on GM1.10C | `UNKNOWN` | `VERIFIED` | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:143`; `tools/port9b_runtime_contract.py:83-85` | **PASS**. Matches canonical registry of unverified runtime facts. |
| **C03a** | §1.1, §3 | Parameter equality: Stock `InitFileModules` priority is `0x19` (25), matching Ranma candidate priority `0x19` | `UNKNOWN` (Comparison) | `STATIC_VERIFIED` (Parameter Equality) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 224, 402` (Slice `S2A`); `tests/fixtures/port11a_manifest.json:42-46, 139-146`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:113` | **PASS**. Disassembly of stock `sub_fc0bd0b4` at `0xFC0BD0CE` (`movs r1, #0x19`) proves stock `InitFileModules` passes priority `0x19` (25), which matches Ranma's candidate value. |
| **C03b** | §1.1, §3 | Scheduling consequence: Priority collision under round-robin scheduling risks starving filesystem flushes | `UNKNOWN (Collision Risk)` | `UNKNOWN` (Scheduling Consequence) | None of the cited sources (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 208-226`; `tools/port9a_runtime_lifecycle.py:869-878`) establish DryOS kernel scheduling policy | **FLAGGED / UNVERIFIED_ASSUMPTION**. While parameter equality is verified, the scheduling or starvation consequence is unproven. None of the cited sources establish the DryOS scheduler policy (e.g. preemption vs cooperative FIFO within priority, round-robin time slicing, or completion callback mechanics). |
| **C03c** | §3 | Priorities `0x1E` (30) or `0x20` (32) are 'safer' candidates for `SpyTask` | `UNKNOWN (Collision Risk)` | `UNKNOWN / UNSUPPORTED` | `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd:88`; unsupported by tracked firmware evidence | **FLAGGED / DEFECT**. PR #25 claims "Priority 0x1E or 0x20 is a safer candidate" without evidence establishing: (1) whether lower or higher numerical values denote higher priority in DryOS on DIGIC 6; (2) which priorities are unallocated across stock tasks; or (3) what priority margins are required relative to display, filesystem, and keyboard tasks. Unsupported conjecture. |
| **C04** | §1.1 | Normal tasks allocate 1 KiB (`InitFileModules`) or 2 KiB (`PhySw`); 8 KiB stack impacts heap | `UNKNOWN` | **`CONTRADICTED`** (InitFileModules stack) / `STATIC_VERIFIED` (PhySw stack) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 226, 402` | **CONTRADICTED / DEFECT**. PR claims `InitFileModules` stack is 1,024 B (1 KiB). Disassembly of `sub_fc0bd0b4` in Slice `S2A` (`0xFC0BD0D2: movw r2, #0x1000`) conclusively proves the stack size is **`0x1000` (4,096 B / 4 KiB)**. |
| **C05** | §1.2 | `SpyTask` must remain in `WAITING_GATE` until all 6 FS stages and U4 are satisfied | *(Lifecycle Rule)* | `INFERRED` (Design Rule) | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:102-106`; `tools/port9a_runtime_lifecycle.py:270-285` | **PASS**. Consistent with PORT-9A lifecycle state model. |
| **C06** | §1.2 | Timeout enforces `spytask_gate_timeout() -> TaskState.FAILED` without legacy bypass | *(Lifecycle Rule)* | `INFERRED` (Design Rule) | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:104-105`; `tests/test_port9a_runtime_lifecycle.py:84-93` | **PASS**. Verified by `test_gate_timeout_fails_instead_of_running` (`tests/test_port9a_runtime_lifecycle.py:84-93`). Gating fail-closed without bypass is verified in the model. |
| **C06b** | §1.2 | Legacy timeout bypass caused storage corruptions and kernel panics | *(Causal Assertion)* | **`UNKNOWN`** | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` | **FAIL / UNSUPPORTED**. PR #25 §1.2 asserts that legacy timeout bypass "caused storage corruptions and kernel panics". While `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99` establishes upstream bypass behavior (`core/main.c:136, 156`), it labels the link to symptoms as `INFERRED` (line 99). Furthermore, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` (F5) explicitly notes that this causal relationship is "INFERRED; not tested". Asserting historical causality as established fact is unsupported. |
| **C07** | §1.3 | `u4_spytask_creation_priority_and_dependencies` is `UNKNOWN` in GM110C baseline | `UNKNOWN` | `VERIFIED` | `tools/port9a_runtime_lifecycle.py:112`; `tools/port9b_runtime_contract.py:547`; `tests/test_port12c_spytask_u4.py@de792bd:50-56` | **PASS**. Verified by `test_gm110c_baseline_evidence_u4_is_unknown`. |
| **C08** | §2 | Startup sequence, task attribution, and hook placement in §2 diagram | *(Diagram)* | **`UNKNOWN / CONTRADICTED`** | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:224`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:239-240, 358-366, 373` | **FLAGGED / DEFECTS**. (1) Line 47 misidentifies `task_Startup` as `0xFC05B558`: `0xFC05B558` is the initial bootstrap task (`sub_fc05b558`), which spawns `task_Startup` at `0xFC05B8FC`. (2) Line 73 places a 'CHDK Hook Placement' edge at `S3`, which is an unsupported runtime placement claim that must be labelled `UNKNOWN` (static veneer/PhySw evidence does not establish hook placement). (3) Sequential call from `task_Startup` to `sub_fc0bd0b4` (`InitFileModules`) is unverified and contradicted by `PORT11A:238-239` (no direct call; reachability `UNKNOWN`). |
| **C09** | §2 | CreateTask veneer `0xFC31BBC4 -> relocated ATCM instruction 0xBFE14A3C` | *(Static Setup)* | `STATIC_VERIFIED` (Veneer & ATCM) / `UNKNOWN` (Runtime Hook) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 61-62, 120-134, 384, 401` | **PASS**. Veneer and ATCM relocation verified in Slices `S1A`–`S1C`. PR #25 keeps hooks dormant and does not treat static veneer as runtime authorization. |
| **C10** | §2 | PhySw Thumb entry `0xFC1283AD` (instruction address `0xFC1283AC`) | *(Static Setup)* | `STATIC_VERIFIED` (Entry pointer) / `UNKNOWN` (Launch Ordering) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:22, 314, 324, 360, 391-392, 403` | **PASS WITH CAVEAT**. Static entry pointer verified in Slices `S3A`/`S3B`. PR #25 does not use entry pointer as runtime proof, though caller sequence in §2 diagram is over-assumed. |
| **C11** | §2 | Diagram transitions `SP2 -- "Timeout or U4 UNKNOWN" --> SP4` (`TaskState.FAILED`) | *(Diagram)* | **`CONTRADICTED`** | `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd:77` vs `tools/port9a_runtime_lifecycle.py:869-878`; `tests/test_port12c_spytask_u4.py@de792bd:102-103` | **FLAGGED / DEFECT**. In `tools/port9a_runtime_lifecycle.py:869-878` and Trace 3 test (line 102), U4 `UNKNOWN` leaves `SpyTask` blocked in `TaskState.WAITING_GATE`. It does NOT transition to `FAILED`. Grouping U4 UNKNOWN with timeout into `FAILED` at line 77 contradicts the lifecycle contract. |
| **C12** | §3 | Launch site in `task_Startup` requires verified subroutines | `HISTORICAL_CANDIDATE` | `INFERRED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:409-416`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:113` | **PASS WITH CAVEAT**. Correctly identifies as candidate; should clarify that prototype disabled site is mid-startup (post-PhySw), whereas Ranma was post-subroutines. |
| **C13** | §3 | Continuation branch `b.w sub_fc0d0126` (`P:1762`, `C:434`) is verified semantic continuation | `VERIFIED_IN_EXISTING_DOCS` | **`PARTIAL: VERIFIED (Source) / UNKNOWN (Continuation)`** | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:114`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:50` | **FLAGGED / OVERSTATED**. Matching opcode is verified in source; whether branching to `sub_fc0d0126` accomplishes successful continuation without crash or hang is `UNKNOWN`. |
| **C14** | §3 | Readiness synchronization gated by 6-stage lifecycle state machine | `INFERRED` | `INFERRED` | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:85-90`; `tools/port9a_runtime_lifecycle.py:228-270` | **PASS**. Accurately describes offline model design. |
| **C15** | §4.1 | DryOS user tasks execute in ARM **System Mode** with **IRQ and FIQ enabled** (`CPSR[7:6] = 0b00`) | *(Execution Rule)* | **`CONTRADICTED`** | `docs/PROJECT_STATE.md:168`; `docs/HANDOFF.md:306-309`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125, 225`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38` | **FLAGGED / CRITICAL DEFECT**. Tasks execute in **Privileged Supervisor Mode** (`M = 0x13`). Initial CPSR is `0x000000F3`. Task wrapper helper entry `0xFC267BE6` (`mrs`), BIC at `0xFC267BEA`, and mask-changing MSR at `0xFC267BF2` unmask IRQ only; FIQ remains disabled (`CPSR[7:6] = 0b01`). Zero System mode transitions occur. |
| **C16** | §4.2 | `SpyTask` stack (`0x2000`) allocated from DryOS Pool 0 (`0x003C89B4..0x00600013`) | *(Memory Rule)* | **`VERIFIED arithmetic (0x00600013) / UNVERIFIED_CANDIDATE (0x003C89B4) / UNKNOWN (Allocator Ownership)`** | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-211`; `docs/HANDOFF.md:796`; `origin/research/port12a-memory-ownership:docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md:43` | **FLAGGED / QUALIFIED**. On baseline `origin/main`, `boot_prototype.c:209-211` sets `size = 0x00600014 - base`, establishing `0x00600013` as the derived inclusive upper endpoint (`VERIFIED` arithmetic). However, designating this region as "DryOS Pool 0" and asserting that `SpyTask` stack is allocated from it by `CreateTask` is unproven (`UNKNOWN` allocator ownership). Candidate fixed base `0x003C89B4` derives from `docs/HANDOFF.md:796` and parallel PR #23 (`docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md:43`, not line 52 which describes executable RAM). |
| **C17** | §4.3 | `SpyTask` must yield via `SleepTask` or message queues; never disable interrupts globally | *(Concurrency Rule)* | **`UNKNOWN / UNVERIFIED_ASSUMPTION`** | `docs/PROJECT_STATE.md:456, 539` (UI-001 polling heuristic); no tracked kernel scheduling specification exists on `origin/main` | **FLAGGED / UNVERIFIED_ASSUMPTION**. Unsupported by `PROJECT_STATE.md:359` (stub extraction) or `port9a_runtime_lifecycle.py:276` (FS stage). While cooperative polling with `SleepTask` is standard practice, DryOS kernel scheduling constraints on GM1.10C are an unverified design assumption. |
| **C18** | §4.4 | Lingering semaphores across warm restart cause boot freeze | *(Lifecycle Rule)* | **`UNKNOWN / UNVERIFIED_ASSUMPTION`** | `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:100`; unsupported by `docs/PORT3C_RESTART_READINESS_MATRIX.md:154-159` | **FLAGGED / UNVERIFIED_ASSUMPTION**. Citing `PORT3C:154-159` is unsupported (that section addresses SD bus states and CMD0, not semaphores). Furthermore, `PORT1C1:100` establishes that kernel init re-initializes Low RAM OS structures and queues from ROM constants. The freeze claim is an unverified assumption. |
| **C19** | §5 | Traces 1–6 deterministically verify WAITING_GATE, FAILED, blocked U4, duplicate refusal, generation mismatch, fault containment | *(Test Verdicts)* | `VERIFIED` | `tests/test_port12c_spytask_u4.py@de792bd:58-164` | **PASS**. 9/9 unit tests pass deterministically as reported by independent test execution. |
| **C20** | §6 | Rank 1–4 unknowns: priority collision, stack sizing, display dependency, restart teardown | *(Research Tasks)* | `INFERRED` | `docs/PORT12C_SPYTASK_U4_CONTRACT.md@de792bd:144-152`; `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:143`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 224` | **PASS**. Sound prioritization of future research questions. |
| **C21** | §7 | Zero code hooks installed; zero ROM reads; hardware remains STRICT NO-GO | *(Safety Assertion)* | `VERIFIED` | `git diff origin/main...de792bd73b643e778dea3f3a80c53c8f2fdb0ead` | **PASS**. Zero code hooks, zero binary builds, read-only documentation/tests only. |

---

## 5. Offline Test Results and Validation Runner Verification

### 5.1 Test Provenance Separation and Protocol
Under Phase 0 read-only review rules and task instructions, tests are not re-executed during this review session. Results are recorded from earlier independent review execution and cited to the AgentBridge validation runner for this task (`p13-review-u4-r2`):
- **AgentBridge Worktree Test Suite:** The default AgentBridge test runner executes in the `origin/main`-based worktree (`python3 -B -m unittest discover -s tests`). Because `tests/test_port12c_spytask_u4.py` exists **strictly on the PR branch** and is not present on `origin/main`, the AgentBridge workspace validation tests validate baseline `origin/main` integrity and runtime contracts.
- **PR Dedicated Test Suite Execution:** Validated by the prior independent review of PR head `de792bd73b643e778dea3f3a80c53c8f2fdb0ead` in an isolated scratch directory without dirtying or modifying the active worktree.

### 5.2 PR #25 Dedicated Test Suite Execution (Recorded from Prior Independent Review)
- **Target PR Head SHA:** `de792bd73b643e778dea3f3a80c53c8f2fdb0ead`
- **Delivered Test Suite:** `tests/test_port12c_spytask_u4.py` (9 unit tests)
- **Results Reported by Prior Independent Review:**
  ```text
  test_gm110c_baseline_evidence_u4_is_unknown (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_gm110c_baseline_evidence_u4_is_unknown)
  Invariant: In GM1.10C baseline evidence, U4 must be strictly UNKNOWN. ... ok
  test_positive_path_when_all_conditions_satisfied (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_positive_path_when_all_conditions_satisfied)
  Positive verification: When ALL 6 FS stages AND U4 are verified, SpyTask runs. ... ok
  test_spytask_timeout_fails_instead_of_running (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_spytask_timeout_fails_instead_of_running)
  Unlike legacy CHDK, spytask_gate_timeout() transitions to FAILED (no bypass). ... ok
  test_trace1_early_start_remains_waiting_gate (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace1_early_start_remains_waiting_gate)
  Trace 1: Creating SpyTask early leaves it in WAITING_GATE until filesystem is ready. ... ok
  test_trace2_absent_u2_proof_blocks_spytask (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace2_absent_u2_proof_blocks_spytask)
  Trace 2: If U2 filesystem mount verification fails, gate and SpyTask fail closed. ... ok
  test_trace3_gate_ready_but_u4_unknown_blocks_spytask (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace3_gate_ready_but_u4_unknown_blocks_spytask)
  Trace 3: When gate is READY but U4 is UNKNOWN (GM1.10C profile), SpyTask cannot start. ... ok
  test_trace4_duplicate_spytask_creation_is_ignored (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace4_duplicate_spytask_creation_is_ignored)
  Trace 4: Duplicate create_spytask calls do not corrupt task state or re-spawn. ... ok
  test_trace5_generation_mismatch_blocks_spytask (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace5_generation_mismatch_blocks_spytask)
  Trace 5: Stale boot generation fails the filesystem and transitions SpyTask to FAILED. ... ok
  test_trace6_fault_after_replacement_contains_spytask (tests.test_port12c_spytask_u4.TestPort12cSpyTaskU4Contract.test_trace6_fault_after_replacement_contains_spytask)
  Trace 6: CPU fault during or after task replacement prevents SpyTask release. ... ok

  ----------------------------------------------------------------------
  Ran 9 tests in 0.001s

  OK
  ```
- **Result:** **`9/9 PASS`** (0 errors, 0 failures, 0 skips).

### 5.3 Baseline Runtime Contract Validator Execution (AgentBridge Validation Citation)
The repository runtime contract validator `tools/port9b_runtime_contract.py` was executed in the baseline AgentBridge environment to verify that baseline `origin/main` compliance with C1–C6 holds:

```text
SOURCES in-memory (vendor + patches) + tracked boot_prototype.c
PASS VERIFIED_SOURCE    C1.sources             all required sources present
PASS VERIFIED_SOURCE    C1.prototype_sha256    platform/g3x/sub/110c/boot_prototype.c matches pinned sha256=f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68
PASS VERIFIED_SOURCE    C2.platform            PLATFORM='g3x' PLATFORMSUB='110c', manifest GM1.10C
PASS VERIFIED_SOURCE    C2.dryos               CAM_DRYOS == 1
PASS VERIFIED_SOURCE    C2.alt_in_keymap       ALT options ['KEY_WIFI', 'KEY_VIDEO', 'KEY_DISPLAY', 'KEY_PLAYBACK'] in keymap
PASS VERIFIED_SOURCE    C2.alt_in_mask0        KEYS_MASK0=0x000533F9 covers every ALT option
PASS VERIFIED_SOURCE    C2.power_excluded      Power (bit 17) not in KEYS_MASK0
PASS VERIFIED_SOURCE    C2.mask12_zero         KEYS_MASK1/2 are zero (only word 0 is overridden)
PASS VERIFIED_SOURCE    C4.preconditions       GM1.10C defaults: no precondition verified
PASS STATIC_VERIFIED    C4.static_vs_runtime_auth STATIC_VERIFIED ROM evidence never authorizes runtime activation; GM110C_PRECONDITIONS remains all False
PASS VERIFIED_SOURCE    C4.model_trace         PORT-9A trace valid; allows nothing
PASS VERIFIED_SOURCE    C4.defaults_inert      PORT-9A GM1.10C defaults activate no interface
PASS VERIFIED_SOURCE    C3.intercept           intercept: recognized activation markers absent (regex scan only; not a proof against arbitrary hooks); model forbids it
PASS VERIFIED_SOURCE    C3.kbd                 kbd: recognized activation markers absent (regex scan only; not a proof against arbitrary hooks); model forbids it
PASS VERIFIED_SOURCE    C3.gate                gate: recognized activation markers absent (regex scan only; not a proof against arbitrary hooks); model forbids it
PASS VERIFIED_SOURCE    C3.spytask             spytask: recognized activation markers absent (regex scan only; not a proof against arbitrary hooks); model forbids it
PASS VERIFIED_SOURCE    C3.stock_physw         prototype task_Startup_my still calls the stock PhySw creator
PASS UNVERIFIED_RUNTIME C5.U1                  CreateTask prologue and continuation are STATIC_VERIFIED; runtime hook patch context and cache/IRQ safety: UNKNOWN
PASS UNVERIFIED_RUNTIME C5.U2                  InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety: UNKNOWN
PASS UNVERIFIED_RUNTIME C5.U3                  PhySw creator, entry and CreateTaskStrictly chain are STATIC_VERIFIED; runtime replacement and stack safety: UNKNOWN
PASS UNVERIFIED_RUNTIME C5.U4                  SpyTask creation point, priority and readiness dependencies on GM1.10C: UNKNOWN
PASS VERIFIED_SOURCE    C5.coverage            every PORT-9A precondition has a registry entry
PASS UNVERIFIED_RUNTIME C6.hook_safety_contract offline hook contract structure valid: static prerequisites STATIC_VERIFIED, all 4 runtime prerequisites UNKNOWN (does not prove hardware readiness)
PASS UNVERIFIED_RUNTIME C6.fs_readiness_contract offline 6-stage filesystem contract structure valid; U2 mount readiness and U4 SpyTask gate remain UNKNOWN (does not prove hardware readiness)
RESULT ok: contract holds; firmware runtime facts remain UNVERIFIED
```
- **Result:** **`24/24 PASS`** (0 contract violations, exit code 0). Verified by AgentBridge validation run for task `p13-review-u4-r2`.

---

## 6. Findings Summary and Recommendation

### 6.1 Findings Summary
1. **PR Structure and Safety:** PR #25 adheres strictly to Phase 0 offline constraints (zero ROM reads, zero firmware execution, zero camera operations, zero installed hooks). Its 9 offline unit tests in `tests/test_port12c_spytask_u4.py@de792bd` pass deterministically (9/9) as verified by prior independent test execution, and the baseline C1–C6 runtime contract suite passes completely (24/24).
2. **Decoupling Strengths:** PR #25 models U4 as strictly `UNKNOWN`, rejects blind adoption of Ranma's candidate parameters, notes parameter equality with stock `InitFileModules`, and introduces fail-closed timeout logic eliminating upstream CHDK's 10-second bypass.
3. **Identified Technical Defects Requiring Remediation:**
   - **Unsupported Causal Claim on Legacy Timeout Bypass (§1.2, C06b):** PR #25 §1.2 claims that the legacy 10-second timeout bypass "caused storage corruptions and kernel panics". Primary sources (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` [F5]) establish the bypass mechanism (`core/main.c:136, 156`), but explicitly label the causal connection to crash/panic symptoms as `INFERRED` and "not tested". Asserting this causal link as established fact is unsupported.
   - **Contract Inconsistency (C11):** The §2 Mermaid diagram specifies at line 77: `SP2 -- "Timeout or U4 UNKNOWN" --> SP4` (`TaskState.FAILED`). In `tools/port9a_runtime_lifecycle.py:869-878` and unit test Trace 3 (line 102), when U4 is `UNKNOWN`, `SpyTask` remains blocked in `TaskState.WAITING_GATE`. It only transitions to `FAILED` on explicit timeout (`spytask_gate_timeout()`) or latched fault.
   - **Contradicted Stack Size (C04):** Section 1.1 asserts `InitFileModules` allocates 1 KiB (1,024 B). Slice `S2A` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 226, 402` proves `sub_fc0bd0b4` passes `0x1000` (4,096 B / 4 KiB).
   - **Unsupported 'Safer' Priorities Assertion (C03c):** Section 3 asserts that priorities `0x1E` or `0x20` are 'safer' candidates for `SpyTask`. This is unsupported speculation: priority ordering semantics (higher vs lower numerical values), task table allocations, and safety margins are unverified on DIGIC 6.
   - **Unverified Scheduling Consequence (C03b):** Section 1.1 asserts that priority collision under round-robin scheduling risks starving filesystem write flushes. While parameter equality is verified, the RTOS scheduling policy is UNKNOWN.
   - **Unverified Sequential Startup Diagram, Task Identity, and Hook Placement (C08):** In §2, line 47 misidentifies `task_Startup` as `0xFC05B558` (which is the initial bootstrap task, distinct from `task_Startup` at `0xFC05B8FC`); line 73 places a 'CHDK Hook Placement' edge at S3 without runtime proof (`UNKNOWN`); and `sub_fc0bd0b4` is depicted as step `S4` inside `task_Startup` despite ROM evidence proving reachability is `UNKNOWN` (`PORT11A:238-239, 407`).
   - **Contradicted CPU Context (C15):** Section 4.1 asserts tasks run in ARM System Mode with IRQ and FIQ enabled (`CPSR[7:6] = 0b00`). Primary evidence proves DryOS tasks run in Privileged Supervisor Mode (`M = 0x13`, initial CPSR `0x000000F3`), and unmasking via helper entry `0xFC267BE6` / `0xFC267BEA` BIC / `0xFC267BF2` MSR clears IRQ only (`CPSR[7:6] = 0b01`) with zero System mode transitions (`docs/PROJECT_STATE.md:168`; `docs/HANDOFF.md:306-309`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:225`).
   - **Memory Bounds and Allocator Ownership (C16):** Section 4.2 claims `SpyTask` stack (`0x2000` bytes) is dynamically allocated by DryOS `CreateTask` from DryOS Pool 0 (`0x003C89B4..0x00600013`). While `0x00600013` is verified arithmetic on baseline `origin/main` (`boot_prototype.c:209-211`), allocator ownership is `UNKNOWN`, candidate base `0x003C89B4` derives from `docs/HANDOFF.md:796` and parallel PR #23 (`PORT12A_MEMORY_OWNERSHIP_MATRIX.md:43`, not line 52 which describes executable RAM), and "Pool 0" kernel ownership remains unestablished.
   - **Unverified Concurrency & Semaphore Assumptions (C17, C18):** Sections 4.3 and 4.4 cite references that do not support the claims made (`PROJECT_STATE.md:359` and `lifecycle:276` for scheduling; `PORT3C:154-159` for semaphores). `SpyTask` yield rules and the assertion that lingering semaphores freeze warm-restart boot are unverified assumptions.
   - **Overstated Continuation Branch & Launch Site Placement (C12, C13):** Section 3 labels `b.w sub_fc0d0126` as `VERIFIED_IN_EXISTING_DOCS` for semantic continuation, but runtime success remains `UNKNOWN`. The prototype's disabled call site is mid-startup (post-PhySw), distinct from Ranma's post-initialization placement.

Because of these identified defects—most notably the unsupported causal assertion in §1.2 (C06b), the CPU execution context error in §4.1 (C15), the contradicted stack size in §1.1 (C04), and diagram routing errors in §2 (C08, C11)—PR #25 is not fully aligned with repository ground truth and cannot be approved in its current form.

### 6.2 Single Recommendation
**`REVISE_BEFORE_MERGE`**

PR #25 should NOT be merged in its current state. The author must apply the following targeted remediations to `docs/PORT12C_SPYTASK_U4_CONTRACT.md`:

1. **Remove or Qualify Legacy Timeout-Bypass Causal Assertion (§1.2, C06b):** Remove the causal assertion that legacy timeout bypass "caused storage corruptions and kernel panics" from Section 1.2, or explicitly qualify it as `INFERRED / UNKNOWN` per `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` (F5, noting that the causal link was "not tested").
2. **Correct §2 Diagram Gating Logic (C11):** Update line 77 from `SP2 -- "Timeout or U4 UNKNOWN" --> SP4` to remove `or U4 UNKNOWN`. Clarify that when U4 is `UNKNOWN`, `SpyTask` remains blocked in `TaskState.WAITING_GATE` per `tools/port9a_runtime_lifecycle.py:869-878` and unit test Trace 3; only explicit timeout or fault latch transitions to `TaskState.FAILED`.
3. **Correct §1.1 Stack Sizing (C04):** Correct the `InitFileModules` stack size from 1,024 B (1 KiB) to `0x1000` (4,096 B / 4 KiB) per Slice `S2A` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 226, 402`.
4. **Remove or Relabel Unsupported Priority Recommendations (C03c):** Remove the claim that priorities `0x1E` or `0x20` would be 'safer' candidates, or explicitly label it as ungrounded speculation pending reverse engineering of the DryOS scheduler.
5. **Qualify Scheduling and Starvation Claims (C03b):** Clarify that while priority parameter equality (`0x19 == 0x19`) is statically verified, the scheduling or starvation consequence is `UNKNOWN` because DryOS scheduler policy on DIGIC 6 is not established by ROM evidence.
6. **Decouple §2 Startup Diagram Call Chain and Fix Task Identity (C08):**
   - **Correct Task Identity (line 47):** Correct line 47 which misidentifies `task_Startup` as `0xFC05B558`. Distinguish the initial bootstrap task (`0xFC05B558`, `sub_fc05b558`) from `task_Startup` at `0xFC05B8FC`, citing `docs/PORT3C_RESTART_READINESS_MATRIX.md:224` (C02), `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38` (E05), and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:239-240, 358-366, 373`.
   - **Remove Unsupported Hook Placement (line 73):** Flag the 'CHDK Hook Placement' edge at `S3` as an unsupported runtime placement claim; it must be labelled `UNKNOWN`, because static CreateTask veneer (`0xFC31BBC4 -> 0xBFE14A3C`) and PhySw entry (`0xFC1283AD`) evidence does not establish hook placement.
   - **Decouple Dispatch Chain:** Remove `sub_fc0bd0b4` from `Stock_Startup` or clearly annotate the edge from `task_Startup` to `sub_fc0bd0b4` as `UNKNOWN (Indirect Dispatch)` per `docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407`.
7. **Correct §4.1 CPU Execution Context (C15):** Change "System Mode (privileged, sharing User-mode register bank `r0–r14`) with IRQ and FIQ enabled (`CPSR[7:6] = 0b00`)" to "Privileged Supervisor Mode (`M = 0x13`) with IRQ enabled and FIQ disabled (`CPSR[7:6] = 0b01`)" per `docs/PROJECT_STATE.md:168` and `docs/HANDOFF.md:306-309`. In the prescribed replacement evidence, accurately attribute the helper instructions: `0xFC267BE6` is the helper entry/MRS (`mrs r1, apsr`), the BIC (`bic r1, r1, #0x80`) is at `0xFC267BEA`, and the mask-changing MSR (`msr cpsr_fsxc, r1`) is at `0xFC267BF2`, citing `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:38` and `docs/PORT3C_RESTART_READINESS_MATRIX.md:225`.
8. **Qualify §4.2 Memory Bounds and Allocator Ownership (C16):** Acknowledge that on baseline `origin/main`, `0x00600013` is the derived inclusive endpoint from `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-211` (`size = 0x00600014 - base`, label: `VERIFIED` arithmetic). Keep this arithmetic strictly separated from allocator ownership (`UNKNOWN`), as well as from candidate fixed base `0x003C89B4` (`docs/HANDOFF.md:796`; parallel PR #23 `docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md:43`, correcting the citation from line 52 which describes executable RAM).
9. **Qualify §4.3 & §4.4 Concurrency and Semaphore Assumptions (C17, C18):** Relabel `SpyTask` yield constraints and warm-restart semaphore freeze hypotheses as unverified RTOS design assumptions, removing unsupported citations (`PROJECT_STATE.md:359`, `lifecycle:276`, `PORT3C:154-159`). Note that `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:100` establishes that kernel initialization re-constructs Low RAM OS structures from initial ROM constants.
10. **Qualify §3 Continuation Branch & Launch Site (C12, C13):** Clarify that opcode `b.w sub_fc0d0126` matches historical patch text, while successful runtime continuation remains `UNKNOWN`. Note that the prototype's disabled call site is mid-startup (post-PhySw) rather than post-initialization.

PR #25 cannot be considered fully aligned with tracked repository ground truth, the I1/I3 contracts, and lifecycle invariants until all the above remediations—including removing or qualifying the unsupported C06b causal claim—are applied.
