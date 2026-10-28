# PORT-11B — Runtime Integration Safety Model (GM1.10C)

**Date**: 2026-10-28  
**Role**: Gemini — Primary Engineer  
**Tech Lead**: ChatGPT  
**Independent Reviewer**: Claude  
**Repository Baseline**: `s4urj3ng/g3x-lite` @ `origin/main` commit `9c1c544db5421527ccd933407f957ff3266b19d1` (PORT-11A merged)  
**Feature Branch**: `research/port11b-runtime-safety-model` (PR #16)  
**Hardware Status**: **STRICT NO-GO** (Offline pure-Python model and contract validation only; zero ROM reads, zero firmware/runtime executable changes, zero camera or SD-card operations)

---

## 1. Summary of Changes & PR #16 Remediation (B1–B4)

PORT-11B refines the existing offline runtime lifecycle model ([`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py)) and source/model contract validator ([`tools/port9b_runtime_contract.py`](../tools/port9b_runtime_contract.py)) to incorporate the static ROM evidence verified in [PORT-11A](PORT11A_GM110C_ROM_EVIDENCE.md) while enforcing a strict fail-closed boundary between **static ROM verification** and **runtime activation authorization**.

### Changed Files

| File | Summary of Improvements |
|---|---|
| [`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py) | Added `EvidenceStatus`, `StaticEvidenceProfile` (`GM110C_STATIC_EVIDENCE`), `HookSafetyContract` (`GM110C_HOOK_CONTRACT`), `CreatorCallContext` (`is_synthetic_witness_only=True`), `CreationMechanism`, `EXPECTED_CREATION_MECHANISMS`, `Action.REJECT_DUPLICATE`, `FilesystemStage`, `FilesystemReadinessState`, `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS`, 6-stage filesystem readiness transition methods, strict fail-closed `file_modules_finished(success)` (zero automatic promotion of Stages 2–6), strict fail-closed `_u4_permitted()` and `install_intercept()` (zero legacy bypasses when `U4` or `hook_contract` is `UNKNOWN`/`None`), unambiguous duplicate rejection (`Action.REJECT_DUPLICATE`), stock pass-through isolation from candidate context faults, and stage-ordering invariants in `check_trace`. |
| [`tools/port9b_runtime_contract.py`](../tools/port9b_runtime_contract.py) | Updated `UNVERIFIED_RUNTIME_FACTS` descriptions to reflect PORT-11A static vs runtime splits (remaining address-free), added `C4.static_vs_runtime_auth` (`STATIC_VERIFIED` never authorizes runtime activation), and added `C6.hook_safety_contract` and `C6.fs_readiness_contract` (explicitly scoped as offline contract structure/default invariant checks that do **not** prove hardware readiness). |
| [`tests/test_port9a_runtime_lifecycle.py`](../tests/test_port9a_runtime_lifecycle.py) | Migrated legacy tests to explicit test-only helper `advance_all_fs_stages_for_test(m)` and explicit synthetic contracts; added `Port11bSafetyScenarios` (18 deterministic regression tests covering all Phase 2–5 requirements and B1–B4 fixes; 51 tests total in file). |
| [`tests/test_port9b_runtime_contract.py`](../tests/test_port9b_runtime_contract.py) | Added 3 contract tests (`test_port11b_static_vs_runtime_contract_checks_present`, `test_port11b_prematurely_claiming_hook_runtime_satisfied_fails_c6`, `test_port11b_prematurely_claiming_u2_or_u4_verified_fails_c6`; 54 tests total in file). |
| [`docs/PORT11B_RUNTIME_SAFETY_MODEL.md`](PORT11B_RUNTIME_SAFETY_MODEL.md) | This technical documentation report. |

---

## 2. Static Evidence vs Runtime Authorization (Phase 2)

`StaticEvidenceProfile` (`GM110C_STATIC_EVIDENCE`) models the PORT-11A static ROM findings separately from `Preconditions` (`GM110C_PRECONDITIONS`):

| Prerequisite | Static Evidence Field (`GM110C_STATIC_EVIDENCE`) | Status | Runtime Authorization Flag (`GM110C_PRECONDITIONS`) | Value |
|---|---|:---:|---|:---:|
| **U1** | `u1_create_task_prologue_and_continuation` | **`STATIC_VERIFIED`** | `create_task_prologue_verified` | **`False`** |
| **U2 (Entry)** | `u2_init_file_modules_entry` | **`STATIC_VERIFIED`** | `init_file_modules_entry_verified` | **`False`** |
| **U2 (Mount)** | `u2_sd_fat_mount_readiness` | **`UNKNOWN`** | *(Governed by 6-stage FS contract)* | **`False`** |
| **U3** | `u3_physw_creator_entry_and_strictly_chain` | **`STATIC_VERIFIED`** | `physw_entry_verified` | **`False`** |
| **U4** | `u4_spytask_creation_priority_and_dependencies` | **`UNKNOWN`** | *(Governed by `_u4_permitted()` gate)* | **`False`** |

**Invariants Enforced (Including Blocker B2 Remediation)**:
1. `GM110C_PRECONDITIONS` remains `Preconditions(False, False, False)`.
2. `StaticEvidenceProfile.authorizes_runtime_activation` and `RuntimeLifecycle.hardware_execution_authorized` are unconditionally `False`.
3. `RuntimeLifecycle.__init__` defaults to `static_evidence=GM110C_STATIC_EVIDENCE` and `hook_contract=GM110C_HOOK_CONTRACT`.
4. `install_intercept()` refuses installation fail-closed if `hook_contract is None` or `not hook_contract.all_satisfied` (no legacy hypothetical bypass).
5. `_u4_permitted()` returns `True` **only** when `static_evidence.u4_spytask_creation_priority_and_dependencies is EvidenceStatus.STATIC_VERIFIED` (no legacy hypothetical bypass).

---

## 3. Six-Stage Filesystem Readiness Contract (Phase 3 & Blocker B1 Remediation)

PORT-11A proved that the first callee of `task_InitFileModules` (`sub_fc0d9ccc`) has zero conditional branches of its own and always returns `r0 = 0` (`r4 == 0`) on normal return. Therefore, `r4 == 0` and the subsequent UI event `0x5006` cannot prove dynamic SD/FAT mount readiness.

`FilesystemReadinessState` and `FilesystemStage` enforce six sequential, fail-closed stages bound to `boot_generation`:

| Stage # | `FilesystemStage` | Transition Method | Model Invariant & Evidence Needed for Future Promotion |
|:---:|---|---|---|
| **1** | `TASK_CREATED` | `on_firmware_create_task("InitFileModules")` | Arms gate (`GateState.ARMED`), sets `task_created=True`. Does **not** mark task started or gate `READY`. Promotion requires runtime proof that `CreateTask` was invoked for `"InitFileModules"` in the current boot generation. |
| **2** | `TASK_STARTED` | `init_file_modules_started()` | Requires `TASK_CREATED` and matching `boot_generation`. Promotion requires execution witness confirming `task_InitFileModules` entry executed after scheduler dispatch. |
| **3** | `INIT_RETURNED_NORMALLY` | `init_file_modules_returned(return_code=0, event_5006_posted=...)` | Requires `TASK_STARTED`, `status == "ok"`, and `return_code == 0`. Explicitly logs `r0=0_constant_not_mount_proof` (and `event_5006_not_sufficient` if `event_5006_posted=True`). Does **not** advance `GateState` to `READY`. |
| **4** | `MOUNT_OBSERVED` | `record_mount_observation(observed=True)` | Requires `INIT_RETURNED_NORMALLY`, `observed is True`, `status == "ok"`, matching `boot_generation`, and `u2_sd_fat_mount_readiness == STATIC_VERIFIED`. Promotion requires independent kernel/storage state proof that FAT volume mount succeeded. |
| **5** | `FS_IO_READY` | `record_filesystem_io_readiness(ready=True)` | Requires `MOUNT_OBSERVED`, `ready is True`, `status == "ok"`, and matching `boot_generation`. Promotion requires verified non-destructive file open/read capability on the mounted volume without contention or timeout. |
| **6** | `WARM_RESTART_SAFE` | `record_warm_restart_storage_safety(safe=True)` | Requires `FS_IO_READY`, `safe is True`, `status == "ok"`, and matching `boot_generation`. Only when Stage 6 succeeds does `GateState` transition to `READY`. Promotion requires resolving warm-restart SD host/card preconditions (`P11`, `P12`, `P13`, `P15`). |

**Strict `file_modules_finished(success)` Behavior (Blocker B1 Remediation)**:
- `file_modules_finished(True)` **never** auto-promotes or synthesizes Stages 2–6.
- Calling `file_modules_finished(True)` on an armed gate when `not self.fs.is_ready` immediately fails closed (`FilesystemStage.FAILED`, `GateState.FAILED`, and `SpyTask` `TaskState.FAILED`).
- Legacy unit tests that exercise downstream ordering use the explicit test-only helper `advance_all_fs_stages_for_test(m)` in `tests/test_port9a_runtime_lifecycle.py`.

---

## 4. Runtime Hook Safety Contract & Task Creation Semantics (Phase 4 & Blockers B3–B4)

### 4.1 `HookSafetyContract` (`GM110C_HOOK_CONTRACT`)

| Prerequisite Field | Default in `GM110C_HOOK_CONTRACT` | Basis |
|---|:---:|---|
| `static_prologue_and_boundaries` | **`STATIC_VERIFIED`** | PORT-11A Slice `S1C` (`push.w {r1-r9, lr}; mov r4, r0; ldr r0, [pc, #0x214]` = 8 B, boundary `0xBFE14A44`). |
| `replay_semantics` | **`STATIC_VERIFIED`** | PORT-11A Slice `S1C` (literal `0x00008160` at `0xBFE14C58`). |
| `patch_execution_context_safe` | **`UNKNOWN`** | Runtime CPU mode / ATCM write timing during hook installation not verified. |
| `interrupt_masking_and_concurrency_safe` | **`UNKNOWN`** | IRQ masking (`P15`) and scheduler concurrency during ATCM write not verified. |
| `icache_and_branch_predictor_coherent` | **`UNKNOWN`** | Cortex-R4 I-cache / branch predictor maintenance for ATCM self-modifying code not verified. |
| `continuation_behavior_safe` | **`UNKNOWN`** | Live execution of Thumb interworking continuation target not verified on hardware. |
| `no_duplicate_task_creation_verified` | **`STATIC_VERIFIED`** | Enforced by singleton guard in ROM creators and `Action.REJECT_DUPLICATE`. |
| `creator_predecessors_and_guards_preserved` | **`STATIC_VERIFIED`** | Enforced via synthetic witness assertions in `CreatorCallContext`. |
| `create_task_strictly_forwarding_safe` | **`STATIC_VERIFIED`** | PORT-11A Slices `S1D`/`S1E` (`CreateTaskStrictly` preserves `r0–r3` and `[sp]`, forwarding to `CreateTask`). |

### 4.2 Unambiguous Duplicate Task Creation & Creator Context Semantics (Blockers B3 & B4)

1. **Three Explicit `Action` Outcomes in `on_firmware_create_task`**:
   - `Action.PASS_THROUGH` (`entry="stock"`): Stock firmware task is created unmodified. Used for unlisted tasks, or when the intercept is not installed, a fault is latched, the task entry is unverified, or candidate creator validation failed.
   - `Action.REPLACE` (`entry=REPLACEMENTS[task_name]`): First creation of a listed task under an installed intercept and valid creator context is routed to the CHDK replacement task.
   - `Action.REJECT_DUPLICATE` (`entry="duplicate_blocked"`): Any second creation request for a listed singleton task (`InitFileModules` or `PhySw`) is blocked (`duplicate_task_creation_blocked`); neither a second replacement task nor a second stock task is created.
2. **Stock Pass-Through Isolation**:
   - `_validate_creator_context` is evaluated **only** when `task_name in REPLACEMENTS`, the task has not yet been created, `self.intercept is InterceptState.INSTALLED`, `self.fault is None`, and `self._entry_verified(task_name)` is `True`. Unlisted tasks and unintercepted stock pass-through paths never latch creator-context faults.
3. **Mandatory Creation Mechanism & Synthetic Witness Framing (`EXPECTED_CREATION_MECHANISMS`)**:
   - `CreatorCallContext` is explicitly documented and marked (`is_synthetic_witness_only = True`) as a synthetic witness assertion for offline scenario testing, never physical runtime proof.
   - `EXPECTED_CREATION_MECHANISMS` requires `CreationMechanism.CREATE_TASK` for `"InitFileModules"` and `CreationMechanism.CREATE_TASK_STRICTLY` for `"PhySw"`. Supplying `CREATE_TASK` for `"PhySw"` (which would otherwise skip the `CreateTaskStrictly` forwarding check) is rejected fail-closed with a fault.

### 4.3 Scope of `C6` in `tools/port9b_runtime_contract.py`

`C6.hook_safety_contract` and `C6.fs_readiness_contract` verify the **offline contract structure and selected default fail-closed invariants** (that `GM110C_HOOK_CONTRACT` leaves runtime prerequisites `UNKNOWN`, `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` defines all 6 stages, and `GM110C_STATIC_EVIDENCE` leaves `U2` mount readiness and `U4` `UNKNOWN`). They do **not** prove physical hardware readiness or replace the state-machine transition tests in `tests/test_port9a_runtime_lifecycle.py`.

---

## 5. Offline Test Scenarios & What They Prove (Phase 5 & B1–B4 Regressions)

All scenarios are deterministically verified in `Port11bSafetyScenarios` ([`tests/test_port9a_runtime_lifecycle.py`](../tests/test_port9a_runtime_lifecycle.py)) and `RegistryViolations` ([`tests/test_port9b_runtime_contract.py`](../tests/test_port9b_runtime_contract.py)):

1. **Static evidence present, runtime authorization absent** (`test_static_evidence_present_but_runtime_authorization_absent`)
2. **B1 — `file_modules_finished(True)` never auto-promotes Stages 2–6** (`test_b1_file_modules_finished_true_never_auto_promotes_stages`, `test_b1_file_modules_finished_true_at_any_partial_stage_fails_closed`)
3. **B2 — Default or `None` `hook_contract` and `U4` `UNKNOWN` always fail closed without legacy hypothetical bypasses** (`test_b2_missing_or_default_hook_contract_refuses_intercept_even_with_hypothetical_preconditions`, `test_b2_u4_unknown_always_blocks_spytask_without_legacy_bypass`)
4. **`InitFileModules` created but not started** (`test_init_file_modules_created_but_not_started_blocks_spytask`)
5. **Initialization returns zero (`r0 == 0`) + event `0x5006` while mount readiness is `UNKNOWN`** (`test_init_returns_zero_and_event_5006_do_not_prove_mount_readiness`)
6. **Mount observed without proven filesystem I/O readiness** (`test_mount_observed_without_fs_io_readiness_blocks_spytask`)
7. **Filesystem I/O ready without warm-restart storage safety** (`test_filesystem_ready_without_warm_restart_safety_blocks_spytask`)
8. **Stale readiness evidence from an earlier boot generation** (`test_stale_boot_generation_readiness_evidence_rejected`)
9. **Explicit failure or ambiguous status** (`test_explicit_failure_or_ambiguous_status_blocks_spytask`)
10. **B3 — Duplicate `InitFileModules` / `PhySw` creation returns `Action.REJECT_DUPLICATE` and invalid context does not fault stock pass-through** (`test_b3_duplicate_init_file_modules_creation_returns_reject_duplicate`, `test_b3_invalid_context_does_not_fault_stock_pass_through_paths`, `test_second_creation_of_same_task_is_rejected_not_recreated`)
11. **B4 — `PhySw` enforces `CREATE_TASK_STRICTLY` mechanism and rejects wrong mechanism** (`test_b4_physw_creation_enforces_create_task_strictly_mechanism`)
12. **Missing or invalid creator guard / predecessor calls** (`test_missing_or_invalid_creator_guard_or_predecessors_rejected`)
13. **Unknown interrupt or cache safety** (`test_unknown_interrupt_or_cache_safety_blocks_hook_install`)
14. **`SpyTask` blocked by `U4`** (`test_spytask_blocked_by_u4_when_u4_remains_unknown`)
15. **Complete synthetic readiness scenario passing logical model while refusing hardware authorization** (`test_complete_synthetic_readiness_passes_model_but_never_authorizes_hardware`)

---

## 6. What Remains `UNKNOWN` & Why Hardware Remains Blocked

1. **`U2` Dynamic SD/FAT Mount Readiness & Warm-Restart Storage Safety (`UNKNOWN`)**:
   - Nested callees of `sub_fc0d9ccc` and `sub_fc0d9cf6` (and RAM pointer `[0xFC0D9D54]`) have not been verified to establish when FAT mount completes.
   - Warm-restart SD controller/card hazards (`BLK-16`: `P11` `SD1stInit` skip predicate, `P12` controller reset, `P13` card state, `P15` IRQ state) remain unresolved.
2. **`U4` `SpyTask` Creation Point, Priority, and Heap Headroom (`UNKNOWN`)**:
   - Exact placement of `CreateTask_spytask` in `task_Startup_my`, priority interaction, and DryOS heap headroom (`P07`) remain unverified on GM1.10C.
3. **Runtime Hook Execution Safety (`UNKNOWN`)**:
   - Patch installation context, interrupt masking, ATCM I-cache/branch-predictor coherence, `mykbd_task` stack adequacy (`0x800` vs `0x2000`), and live continuation behavior remain unverified.
4. **Why Hardware Is Still Blocked (`STRICT NO-GO`)**:
   - Passing an offline Python state model does not establish physical-device safety (`docs/SAFETY.md`). All three `GM110C_PRECONDITIONS` flags remain `False`, all runtime hooks in `boot_prototype.c` and `vendor/g3x-platform/` remain absent/dormant, and hardware testing requires explicit human authorization after all runtime blockers are resolved.

---

## 7. Recommended Next Milestone

- **PORT-11C — Bounded Offline Analysis of Filesystem Mount Indicator & `SpyTask` Startup Placement (`U2` Dynamic Mount State & `U4`)**:
  1. Formulate a strictly bounded, read-only offline inspection plan (requiring explicit owner approval before any ROM read) to identify the underlying kernel/FileSem/mount state variable set by the `sub_fc0d9ccc` / `sub_fc0d9cf6` call tree and the exact `task_Startup` call sequence around `sub_fc0bb6fe` for `U4`.
  2. Keep all runtime hooks disabled (`GM110C_PRECONDITIONS` all `False`) and maintain **Hardware STRICT NO-GO**.
