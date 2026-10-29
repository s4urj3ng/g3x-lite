# PORT-13 — Fail-Closed Proof Obligations: U4 SpyTask Launch Dependencies

- **Date:** 2026-10-29
- **Author:** AgentBridge Worker (`port-13-offline-p13-oblig-u4-r2`)
- **Target Platform:** PowerShot G3 X GM1.10C (DIGIC 6)
- **Status:** **`FAIL_CLOSED_OBLIGATIONS_CODIFIED`**
- **Safety Gate:** **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Offline Read-Only Investigation)
- **Referenced Documents:**
  - `docs/PORT13_REVIEW_U4.md` (Approved read-only review of PR #25 / Issue #22)
  - `tools/port9b_runtime_contract.py` (Contracts I1, I3, C3.spytask, C5.U4)
  - `tools/port9a_runtime_lifecycle.py` (Lifecycle state machine, preconditions, evidence status)
  - `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md` (Contract I3 and U4 registration)
  - `docs/PORT11A_GM110C_ROM_EVIDENCE.md` (Slices S1B, S1C, S2A, S2B, S3A, S3B)
  - `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (Dormant prototype wrappers)

---

## 1. Executive Summary & Context

Milestone **PORT-13 U4** translates the **U4 prerequisite** (*SpyTask creation point, priority, and readiness dependencies on GM1.10C*) into reproducible, deterministic, fail-closed offline proof obligations.

In earlier research drafts (PR #25 / Issue #22), offline lifecycle models successfully codified fail-closed gating logic, but narrative claims and architectural diagrams introduced critical conflations between static ROM disassembly and dynamic runtime feasibility. Furthermore, unsupported causal claims regarding legacy timeout behaviors were introduced.

This document establishes the canonical repository proof obligations for U4, codified programmatically in `tools/port13_oblig_u4.py` and validated by unit tests in `tests/test_port13_oblig_u4.py`.

### 1.1 Core Governance Invariants
1. **Decoupling of Static Evidence from Runtime Hook Placement & Launch Ordering:**
   Static ROM disassembly—specifically the CreateTask ARM veneer (`0xFC31BBC4 -> relocated ATCM instruction 0xBFE14A3C`) and the PhySw Thumb entry point (`0xFC1283AD`)—establishes **strictly** the static presence and relocation destination of firmware code. It does **NOT** prove runtime hook placement, ATCM instruction cache / branch predictor coherence, IRQ safety, or task launch ordering. Static evidence can **never** satisfy runtime obligations.
2. **Isolation of the Legacy Timeout-Bypass Causal Link (Finding C06b):**
   Upstream CHDK (`core/main.c:136, 156`) implemented a 10-second timeout bypass that permitted SpyTask to execute without verified filesystem readiness. While the bypass behavior is verified, asserting that this bypass *caused* storage corruption and kernel panics is an untested inference (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` [F5]). This causal relationship must strictly remain **`UNKNOWN`**.
3. **Fail-Closed Evaluator Model:**
   Any proof obligation lacking `VERIFIED` evidence evaluates as **`NOT_SATISFIED`**. If even a single obligation is `NOT_SATISFIED`, the overall U4 verdict evaluates as **`NOT_SATISFIED`**. For GM1.10C today, all runtime obligations are `UNKNOWN`, ensuring that the overall U4 evaluation verdict is strictly **`NOT_SATISFIED`**.

---

## 2. Master Catalog of U4 Proof Obligations

The table below defines the 9 canonical U4 proof obligations, their required evidence specifications, baseline GM1.10C statuses, and tracked repository citations:

| ID | Title / Domain | Statement | Required Evidence (Artifact Type & Specification) | Status (GM1.10C) | Tracked Citation | Contract / Review Link |
|---|---|---|---|---|---|---|
| **OBLIG-U4-01** | SpyTask Launch Ordering (`LAUNCH_ORDERING`) | Identification and verification of safe execution point and caller dispatch ordering in GM1.10C startup sequence. | `STARTUP_DISPATCH_TRACE`: Dynamic execution trace or caller graph from `sub_fc05b558` / `task_Startup` (`0xFC05B8FC`) proving safe reachability and execution sequence without destabilizing concurrent tasks. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:50-55, 85-90, 167, 176, 277, 296-298` | Contract I3; Findings C01, C02, C08, C12; Remediation #6 |
| **OBLIG-U4-02** | Hook Placement & Interception Authorization (`RUNTIME_HOOK_PLACEMENT`) | Runtime hook installation and `CreateTask` interception authorization on GM1.10C. | `HOOK_SAFETY_EVIDENCE`: Proof of safe runtime patch context, Cortex-R4 ATCM I-cache/BPU coherence at patch time, IRQ safety, and execution authorization. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:41-46, 86, 141-144, 177, 258, 297` | Contract I1 (`C3.intercept`); Findings C08, C09; Remediation #6 |
| **OBLIG-U4-03** | RTOS Priority & Scheduler Policy (`SCHEDULER_POLICY`) | Scheduling priority assignment and DryOS kernel scheduler policy validation on DIGIC 6. | `RTOS_SCHEDULER_SPEC`: Disassembly or kernel specification proving numerical priority direction, preemption/round-robin/FIFO rules for equal priority tasks (`0x19 == 0x19`), and task table survey proving candidate priority avoids starvation. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:60-61, 103-112, 168-170, 275-276, 293-294` | Findings C03a, C03b, C03c; Remediation #4, #5 |
| **OBLIG-U4-04** | Stack Sizing & Dynamic Memory Ownership (`MEMORY_OWNERSHIP`) | Task stack sizing (`0x2000` bytes) and DryOS dynamic memory pool ownership validation. | `KERNEL_HEAP_SPEC`: Heap allocator disassembly proving `CreateTask` dynamically allocates `0x2000` bytes from a verified heap pool without buffer exhaustion or collision with camera buffers or executable RAM. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:98-101, 121-125, 171, 184, 274, 279, 292, 300` | Findings C04, C16; Remediation #3, #8 |
| **OBLIG-U4-05** | Filesystem Readiness Gating (`FS_GATING`) | Filesystem readiness gating and monotonic latch synchronization (Contract I3). | `LIFECYCLE_STATE_TRACE`: SpyTask is created in `WAITING_GATE` and moves to `RUNNING` strictly after all 6 filesystem stages are satisfied (`GateState.READY`) with no latched fault; while U4 is UNKNOWN, SpyTask remains blocked in `WAITING_GATE`. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:63-64, 92-96, 145-152, 172, 175, 179, 215-216, 273, 291` | Contract I3; Findings C05, C07, C11, C14; Remediation #2 |
| **OBLIG-U4-06** | Fail-Closed Gate Timeout (`FAILCLOSED_TIMEOUT`) | Fail-closed gate timeout enforcement eliminating upstream CHDK legacy bypass. | `TIMEOUT_GATING_SPEC`: Deterministic transition of SpyTask to `FAILED` upon gate timeout (`spytask_gate_timeout`), never allowing the task to bypass the gate or launch into unmapped routines. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:63-64, 145-152, 173, 209-210` | Contract I3; Finding C06; Remediation #2 |
| **OBLIG-U4-07** | Timeout-Bypass Causal Link Isolation (`CAUSAL_ANALYSIS`) | Empirical verification or isolation of the causal link between legacy timeout bypass and storage corruption / kernel panic. | `STORAGE_CORRUPTION_TRACE`: Hardware crash log or empirical trace demonstrating whether un-gated SpyTask execution directly induced storage media corruption and kernel panic, or whether the claim is unproven correlation. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:71-74, 174, 272, 290` | Finding C06b; Remediation #1; `PORT5B:204` (F5) |
| **OBLIG-U4-08** | CPU Execution Context (`EXECUTION_CONTEXT`) | Task execution CPU mode and interrupt mask conformance (Privileged Supervisor Mode). | `TASK_CONTEXT_EVIDENCE`: Proof that SpyTask executes in Privileged Supervisor Mode (`M = 0x13`) with initial CPSR `0x000000F3`, unmasked to IRQ enabled and FIQ disabled (`CPSR[7:6] = 0b01`), never assuming System Mode or unmasked FIQ. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:113-120, 183, 278, 299` | Finding C15; Remediation #7 |
| **OBLIG-U4-09** | Continuation Branch Safety (`CONTINUATION`) | Continuation branch runtime safety (tail branch `b.w sub_fc0d0126`). | `CONTINUATION_TRACE`: Runtime proof that executing the tail branch `b.w sub_fc0d0126` (`boot_prototype.c:434`) successfully resumes startup without stack corruption, CPU exception, or hang. | **`UNKNOWN`** | `docs/PORT13_REVIEW_U4.md:126-129, 181, 281, 302` | Findings C12, C13; Remediation #10 |

---

## 3. Detailed Obligation Analysis & Evidence Gaps

### 3.1 OBLIG-U4-01: SpyTask Launch Site and Caller Execution Ordering
- **Problem Statement:** In PR #25 §2, the startup sequence diagram asserted that `task_Startup` directly dispatched `sub_fc0bd0b4` (`InitFileModules`) and assumed that CHDK hook placement could occur after power evaluation (`S3`).
- **Evidence Gap:** Tracked primary evidence proves:
  1. `0xFC05B558` is the initial bootstrap task (`sub_fc05b558`), which spawns `task_Startup` at entry `0xFC05B8FC` (`docs/PORT3C_RESTART_READINESS_MATRIX.md:224`).
  2. ROM evidence proves there is no direct call to `sub_fc0bd0b4` in `task_Startup`; whether `task_Startup` reaches `sub_fc0bd0b4` via indirect dispatch is strictly `UNKNOWN` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407`).
  3. The disabled prototype call site in `boot_prototype.c:409-416` is mid-startup (post-PhySw), distinct from Ranma's candidate placement (post-initialization subroutines).
- **Static Evidence Boundary:** Statically identifying the entry of `task_Startup` (`0xFC05B8FC`) or PhySw (`0xFC1283AD`) does **not** prove caller ordering or thread launch progression.
- **Contract Link:** Contract I3 (`tools/port9b_runtime_contract.py:223-251`).

### 3.2 OBLIG-U4-02: Runtime Hook Placement & Interception Authorization
- **Problem Statement:** PR #25 §2 depicted a runtime hook placement edge at `S3`.
- **Evidence Gap:** Slices `S1A`–`S1C` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 61-62` statically verify the CreateTask veneer `0xFC31BBC4 -> ATCM 0xBFE14A3C`. However, modifying instructions in ATCM or vector tables at runtime requires:
  1. Synchronization of Cortex-R4 Harvard architecture (flushing/invalidating I-cache and Branch Target Buffer / BPU).
  2. Ensuring interrupt handlers or concurrent RTOS tasks are not executing within the patched region.
  3. Precondition verification (`create_task_prologue_verified = False` in `GM110C_PRECONDITIONS`).
- **Static Evidence Boundary:** Static ROM discovery does not authorize runtime memory patching. Static veneer evidence cannot satisfy runtime hook placement.
- **Contract Link:** Contract I1 (`tools/port9b_runtime_contract.py:451-470`; check `C3.intercept`).

### 3.3 OBLIG-U4-03: RTOS Priority Allocation & Scheduler Policy
- **Problem Statement:** PR #25 §1.1 and §3 noted parameter equality between Ranma's candidate priority `0x19` and stock `InitFileModules` (`0x19`), but asserted that this risks starving filesystem flushes and claimed priorities `0x1E` or `0x20` would be "safer".
- **Evidence Gap:**
  1. While parameter equality (`0x19 == 0x19`) is statically verified in Slice `S2A` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 224`), DryOS scheduler policy on DIGIC 6 is unknown. Whether equal-priority tasks time-slice, yield cooperatively, or execute FIFO is unverified.
  2. Claiming priorities `0x1E` or `0x20` are "safer" is unsupported conjecture: numerical priority polarity (whether higher numbers mean higher or lower priority) and unallocated task priority bands have not been reverse engineered.
- **Required Artifact:** `RTOS_SCHEDULER_SPEC` detailing kernel scheduler queue mechanics and priority assignment rules.

### 3.4 OBLIG-U4-04: Stack Sizing & Dynamic Memory Ownership
- **Problem Statement:** PR #25 §1.1 misstated `InitFileModules` stack size as 1,024 B, and §4.2 claimed `SpyTask` stack (`0x2000` bytes) is allocated from "DryOS Pool 0" (`0x003C89B4..0x00600013`).
- **Evidence Gap:**
  1. Slice `S2A` (`0xFC0BD0D2: movw r2, #0x1000`) conclusively proves `InitFileModules` stack is `0x1000` (4,096 B / 4 KiB), directly contradicting PR #25.
  2. On baseline `origin/main`, `0x00600013` is a derived inclusive arithmetic bound (`boot_prototype.c:209-211`), but dynamic allocator ownership by DryOS `CreateTask` and candidate base `0x003C89B4` remain unverified (`UNKNOWN`).
- **Required Artifact:** `KERNEL_HEAP_SPEC` proving dynamic stack allocation bounds from DryOS memory pools.

### 3.5 OBLIG-U4-05: Filesystem Readiness Gating & Monotonic Latch Synchronization
- **Problem Statement:** PR #25 §2 diagram routed `SP2 -- "Timeout or U4 UNKNOWN" --> SP4 (TaskState.FAILED)`.
- **Evidence Gap:** In the lifecycle contract (`tools/port9a_runtime_lifecycle.py:869-878`) and unit test Trace 3, when U4 is `UNKNOWN`, `SpyTask` remains indefinitely blocked in `TaskState.WAITING_GATE`. It does **not** transition to `FAILED`. Grouping U4 UNKNOWN into FAILED contradicted the lifecycle model.
- **Status:** In the offline model, this is verified; on GM1.10C firmware target, no hook calls `core_spytask_can_start` today (`docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:259-260`), so target runtime synchronization remains `UNKNOWN`.
- **Contract Link:** Contract I3 (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:91-106`).

### 3.6 OBLIG-U4-06: Fail-Closed Gate Timeout Enforcement
- **Problem Statement:** Upstream CHDK (`core/main.c:136, 156`) waited 10 seconds and launched anyway, bypassing filesystem readiness checks.
- **Contract Requirement:** The G3X Lite runtime lifecycle model enforces `spytask_gate_timeout() -> TaskState.FAILED`, ensuring that if filesystem readiness does not occur, SpyTask is permanently latched as failed without execution.
- **Status:** Offline model contract is verified (`tests/test_port9a_runtime_lifecycle.py:84-93`); firmware-side implementation remains `UNKNOWN` (U5).

### 3.7 OBLIG-U4-07: Legacy Timeout-Bypass Causal Link Isolation (C06b)
- **Problem Statement:** PR #25 §1.2 asserted that the upstream 10-second timeout bypass "caused storage corruptions and kernel panics".
- **Evidence Audit:** Tracked sources (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:95-99` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` [F5]) establish the bypass code structure, but explicitly label the causal connection to crashes/panics as **`INFERRED`** and **"not tested"**.
- **Governance Mandate:** The causal claim is unproven correlation. It must remain strictly **`UNKNOWN`** unless verified by empirical crash dumps.

### 3.8 OBLIG-U4-08: CPU Execution Context & Privileged Mode Conformance
- **Problem Statement:** PR #25 §4.1 asserted DryOS user tasks execute in ARM System Mode with IRQ and FIQ enabled (`CPSR[7:6] = 0b00`).
- **Evidence Audit:** Contradicted by tracked primary evidence:
  1. DryOS task context creation in ROM (`0xFC05C5A8`) initializes CPSR to `0x000000F3`: **Privileged Supervisor Mode** (`M = 0x13`), Thumb-2 (`T = 1`), IRQ masked (`I = 1`), FIQ masked (`F = 1`) (`docs/PROJECT_STATE.md:168`; `docs/HANDOFF.md:306-309`).
  2. The unmasking helper entered at `0xFC267BE6` clears IRQ via BIC (`0xFC267BEA`) and MSR (`0xFC267BF2`), resulting in `CPSR[7:6] = 0b01` (IRQ enabled, FIQ masked). Zero transitions to System Mode occur.
- **Required Artifact:** `TASK_CONTEXT_EVIDENCE` demonstrating task execution under Supervisor Mode without FIQ unmasking.

### 3.9 OBLIG-U4-09: Continuation Branch Runtime Safety
- **Problem Statement:** PR #25 §3 labeled tail continuation branch `b.w sub_fc0d0126` (`boot_prototype.c:434`) as `VERIFIED_IN_EXISTING_DOCS` for "semantic continuation".
- **Evidence Audit:** While matching opcode bytes are verified in source, whether branching to `sub_fc0d0126` achieves successful runtime continuation without crash or hang is `UNKNOWN` (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:114`).
- **Required Artifact:** `CONTINUATION_TRACE` demonstrating clean execution resumption across the continuation branch.

---

## 4. Mathematical Bounds and Fail-Closed Evaluation Model

The U4 proof evaluator implements a strict mathematical conjunction across all obligations:

$$\text{Verdict}(O_i) = \begin{cases} 
\text{SATISFIED} & \text{if } \text{Status}(E(O_i)) = \text{VERIFIED} \land \neg \text{IsStaticBypass}(O_i, E) \\ 
\text{NOT\_SATISFIED} & \text{otherwise} 
\end{cases}$$

$$\text{OverallVerdict}(\text{U4}) = \bigwedge_{i=1}^{9} \text{Verdict}(O_i)$$

### 4.1 Boundary Guard: Static Evidence Exclusion
For obligations concerning runtime hook placement or task launch ordering ($O_1, O_2 \in \{\text{LAUNCH\_ORDERING}, \text{RUNTIME\_HOOK\_PLACEMENT}\}$):

$$\text{StaticROM}(0\text{xFC31BBC4} \to 0\text{xBFE14A3C}) \not\implies \text{RuntimeHookPlacementAuthorized}$$
$$\text{StaticROM}(0\text{xFC1283AD}) \not\implies \text{TaskStartOrderingProven}$$

If evidence artifact $E$ consists of static veneer or entry pointers, $\text{IsStaticBypass}(O_i, E) = \text{True}$, forcing $\text{Verdict}(O_i) = \text{NOT\_SATISFIED}$.

### 4.2 Baseline Evaluation Outcome
Because all 9 obligations in the GM1.10C baseline catalog currently possess `current_status = UNKNOWN`:

$$\forall i \in \{1, \dots, 9\}, \quad \text{Verdict}(O_i) = \text{NOT\_SATISFIED}$$
$$\text{OverallVerdict}(\text{U4}) = \text{NOT\_SATISFIED}$$

The offline model fails closed by design.

---

## 5. Verification Harness and Traceability

The proof obligations and boundary guards are implemented and verified via:
1. `tools/port13_oblig_u4.py`: Canonical Python standard library module implementing:
   - Data structures: `U4Obligation`, `RequiredEvidence`, `EvidenceArtifact`, `ObligationResult`, `U4EvaluationReport`.
   - The 9 canonical obligations `OBLIG-U4-01` through `OBLIG-U4-09`.
   - Fail-closed evaluation function `evaluate_u4_obligations()`.
   - Static evidence exclusion logic `is_static_veneer_or_entry_evidence()`.
2. `tests/test_port13_oblig_u4.py`: Deterministic unit test suite validating:
   - Schema and repository citation integrity (`test_u4_obligations_catalog_structure_and_citations`).
   - Fail-closed baseline evaluation (`test_baseline_evaluator_fails_closed`).
   - Static CreateTask veneer rejection for hook placement (`test_static_veneer_evidence_cannot_satisfy_runtime_hook_placement`).
   - Static PhySw entry rejection for launch ordering (`test_static_physw_entry_evidence_cannot_satisfy_launch_ordering`).
   - Isolation of the C06b causal claim as UNKNOWN (`test_timeout_bypass_causal_link_remains_unknown`).
   - Negative controls on unverified evidence, mismatched artifact types, and partial satisfaction.
   - Positive synthetic path when all obligations receive valid runtime artifacts.
   - Address containment proving zero new firmware addresses are introduced.

---

## 6. Safety Compliance and Policy Adherence

- **Phase 0 Compliance:** Read-only analysis. Zero ROM scans, zero camera operations, zero firmware flashing, zero binary execution.
- **Contract Integrity:** Fully preserves Contracts I1 and I3; respects address-free rules of `tools/port9b_runtime_contract.py`.
- **Hardware Gate:** Hardware execution remains **`STRICT NO-GO`**.
