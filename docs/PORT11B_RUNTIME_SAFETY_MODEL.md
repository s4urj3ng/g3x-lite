# PORT-11B — Runtime Integration Safety Model (GM1.10C)

**Date**: 2026-10-28  
**Role**: Gemini — Primary Engineer  
**Tech Lead**: ChatGPT  
**Independent Reviewer**: Claude  
**Repository Baseline**: `s4urj3ng/g3x-lite` @ `origin/main` commit `9c1c544db5421527ccd933407f957ff3266b19d1` (PORT-11A merged)  
**Feature Branch**: `research/port11b-runtime-safety-model`  
**Hardware Status**: **STRICT NO-GO** (Offline pure-Python model and contract validation only; zero ROM reads, zero firmware/runtime executable changes, zero camera or SD-card operations)

---

## 1. Summary of Changes

PORT-11B refines the existing offline runtime lifecycle model ([`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py)) and source/model contract validator ([`tools/port9b_runtime_contract.py`](../tools/port9b_runtime_contract.py)) to incorporate the static ROM evidence verified in [PORT-11A](PORT11A_GM110C_ROM_EVIDENCE.md) while enforcing a strict fail-closed boundary between **static ROM verification** and **runtime activation authorization**.

### Changed Files

| File | Summary of Improvements |
|---|---|
| [`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py) | Added `EvidenceStatus`, `StaticEvidenceProfile` (`GM110C_STATIC_EVIDENCE`), `HookSafetyContract` (`GM110C_HOOK_CONTRACT`), `CreatorCallContext`, `CreationMechanism`, `FilesystemStage`, `FilesystemReadinessState`, `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS`, 6-stage filesystem readiness transition methods, creator predecessor/guard checks, `CreateTaskStrictly` forwarding checks, `U4` SpyTask execution gate, and stage-ordering invariants in `check_trace`. Preserved `GM110C_PRECONDITIONS` all `False` and full backward compatibility with PORT-9A/9B callers. |
| [`tools/port9b_runtime_contract.py`](../tools/port9b_runtime_contract.py) | Updated `UNVERIFIED_RUNTIME_FACTS` descriptions to reflect PORT-11A static vs runtime splits (remaining address-free), added `C4.static_vs_runtime_auth` (`STATIC_VERIFIED` never authorizes runtime activation), `C6.hook_safety_contract`, and `C6.fs_readiness_contract`. |
| [`tests/test_port9a_runtime_lifecycle.py`](../tests/test_port9a_runtime_lifecycle.py) | Added `Port11bSafetyScenarios` (13 deterministic regression tests covering all Phase 2–5 requirements) and `test_checker_rejects_out_of_order_filesystem_stages` (46 tests total in file). |
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

**Invariants Enforced**:
1. `GM110C_PRECONDITIONS` remains `Preconditions(False, False, False)`.
2. `StaticEvidenceProfile.authorizes_runtime_activation` and `RuntimeLifecycle.hardware_execution_authorized` are unconditionally `False`.
3. Even when `GM110C_STATIC_EVIDENCE` is supplied, `install_intercept()` is `REFUSED` unless runtime authorization (`Preconditions`) is also explicitly granted in a hypothetical test context (`C4.static_vs_runtime_auth`).

---

## 3. Six-Stage Filesystem Readiness Contract (Phase 3)

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

Any out-of-order call, `False`/`None` observation, non-`"ok"` status, or mismatched `boot_generation` immediately latches `FilesystemStage.FAILED`, `GateState.FAILED`, and a lifecycle fault that transitions `SpyTask` to `TaskState.FAILED`.

---

## 4. Runtime Hook Safety Contract (Phase 4)

`HookSafetyContract` (`GM110C_HOOK_CONTRACT`) models the nine prerequisites for a future `CreateTask` hook:

| Prerequisite Field | Default in `GM110C_HOOK_CONTRACT` | Basis |
|---|:---:|---|
| `static_prologue_and_boundaries` | **`STATIC_VERIFIED`** | PORT-11A Slice `S1C` (`push.w {r1-r9, lr}; mov r4, r0; ldr r0, [pc, #0x214]` = 8 B, boundary `0xBFE14A44`). |
| `replay_semantics` | **`STATIC_VERIFIED`** | PORT-11A Slice `S1C` (literal `0x00008160` at `0xBFE14C58`). |
| `patch_execution_context_safe` | **`UNKNOWN`** | Runtime CPU mode / ATCM write timing during hook installation not verified. |
| `interrupt_masking_and_concurrency_safe` | **`UNKNOWN`** | IRQ masking (`P15`) and scheduler concurrency during ATCM write not verified. |
| `icache_and_branch_predictor_coherent` | **`UNKNOWN`** | Cortex-R4 I-cache / branch predictor maintenance for ATCM self-modifying code not verified. |
| `continuation_behavior_safe` | **`UNKNOWN`** | Live execution of Thumb interworking continuation target not verified on hardware. |
| `no_duplicate_task_creation_verified` | **`STATIC_VERIFIED`** | Enforced by singleton guard in ROM creators and `RuntimeLifecycle._created`. |
| `creator_predecessors_and_guards_preserved` | **`STATIC_VERIFIED`** | Enforced via `CreatorCallContext` (`predecessor_calls_preserved`, `singleton_guard_checked`, `singleton_guard_clear`, `handle_stored_on_return`). |
| `create_task_strictly_forwarding_safe` | **`STATIC_VERIFIED`** | PORT-11A Slices `S1D`/`S1E` (`CreateTaskStrictly` preserves `r0–r3` and `[sp]`, forwarding to `CreateTask`). |

---

## 5. Offline Test Scenarios & What They Prove (Phase 5)

All 13 required scenarios are deterministically verified in `Port11bSafetyScenarios` ([`tests/test_port9a_runtime_lifecycle.py`](../tests/test_port9a_runtime_lifecycle.py)) and `RegistryViolations` ([`tests/test_port9b_runtime_contract.py`](../tests/test_port9b_runtime_contract.py)):

1. **Static evidence present but runtime authorization absent** (`test_static_evidence_present_but_runtime_authorization_absent`): Proves `GM110C_STATIC_EVIDENCE` (`U1`/`U2` entry/`U3` `STATIC_VERIFIED`) with `GM110C_PRECONDITIONS` (`False`) refuses `install_intercept()` and leaves all tasks on stock pass-through.
2. **`InitFileModules` created but not started** (`test_init_file_modules_created_but_not_started_blocks_spytask`): Proves Stage 1 (`TASK_CREATED`) keeps `SpyTask` in `WAITING_GATE`, and calling `init_file_modules_returned` before `init_file_modules_started` fails closed.
3. **Initialization returns zero (`r0 == 0`) and posts `0x5006` while mount readiness is `UNKNOWN`** (`test_init_returns_zero_and_event_5006_do_not_prove_mount_readiness`): Proves Stage 3 (`return_code=0, event_5006_posted=True`) does not arm `READY`, and `record_mount_observation(True)` fails closed while `u2_sd_fat_mount_readiness` is `UNKNOWN`.
4. **Mount observed without proven filesystem I/O readiness** (`test_mount_observed_without_fs_io_readiness_blocks_spytask`): Proves Stage 4 (`MOUNT_OBSERVED`) alone does not release `SpyTask`, and skipping Stage 5 (`FS_IO_READY`) fails closed.
5. **Filesystem I/O ready without warm-restart storage safety** (`test_filesystem_ready_without_warm_restart_safety_blocks_spytask`): Proves Stage 5 (`FS_IO_READY`) alone keeps `SpyTask` waiting, and `record_warm_restart_storage_safety(False)` fails closed.
6. **Readiness evidence from an earlier boot generation** (`test_stale_boot_generation_readiness_evidence_rejected`): Proves passing `boot_generation=1` into a `boot_generation=2` lifecycle instance latches a fault and fails `SpyTask`.
7. **Explicit failure or ambiguous status** (`test_explicit_failure_or_ambiguous_status_blocks_spytask`): Proves non-zero return codes, `None` observations, or statuses `"ambiguous"`, `"stale"`, or `"unknown"` fail closed at every stage.
8. **Duplicate `InitFileModules` creation** (`test_duplicate_init_file_modules_creation_blocked`): Proves a second `on_firmware_create_task("InitFileModules")` logs `duplicate_task_creation_blocked` and returns `PASS_THROUGH` without re-arming the gate.
9. **`PhySw` creation through `CreateTaskStrictly`** (`test_physw_creation_through_create_task_strictly`): Proves `PhySw` defaults to `CreationMechanism.CREATE_TASK_STRICTLY`, logs `create_task_strictly_forwarded`, and fails closed if `create_task_strictly_forwarding_safe` is `UNKNOWN`.
10. **Missing or invalid creator guard / predecessor calls** (`test_missing_or_invalid_creator_guard_or_predecessors_rejected`): Proves bypassing predecessor calls, skipping the singleton guard, encountering a non-zero guard, or omitting the `PhySw` task handle store latches a fault and blocks replacement.
11. **Unknown interrupt or cache safety** (`test_unknown_interrupt_or_cache_safety_blocks_hook_install`): Proves `install_intercept()` is `REFUSED` whenever any of `patch_execution_context_safe`, `interrupt_masking_and_concurrency_safe`, `icache_and_branch_predictor_coherent`, or `continuation_behavior_safe` is `UNKNOWN`.
12. **`SpyTask` blocked by `U4`** (`test_spytask_blocked_by_u4_when_u4_remains_unknown`): Proves that even when all 6 filesystem readiness stages reach `GateState.READY`, `SpyTask` remains in `WAITING_GATE` (logging `spytask_blocked_u4`) while `u4_spytask_creation_priority_and_dependencies` is `UNKNOWN`.
13. **Complete synthetic readiness scenario** (`test_complete_synthetic_readiness_passes_model_but_never_authorizes_hardware`): Proves that a synthetic end-to-end run with all static and dynamic flags satisfied passes `check_trace`, but `hardware_execution_authorized` and `authorizes_runtime_activation` remain `False` and `GM110C_PRECONDITIONS` remains all `False`.

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
