# PORT-9A — CHDK runtime integration map (GM1.10C)

Date: 2026-10-26. Analyst: Claude Code. Branch `feat/port9a-runtime-integration`, cut from `origin/main` `84573f6`.
Scope: an offline lifecycle model, its tests and this map. Nothing in this work is a firmware hook, patch or build.
- No ROM, dump or binary was read. No subprocess, compiler or toolchain was run.
- `boot_prototype.c`, loader code and everything under `chdk-port/` are unchanged.
- No `g3x_110e.patch` (GM1.10E) value is used as a GM1.10C fact. E values are quoted only as historical context, labelled as such.
- Hardware: **STRICT NO-GO**.

Deliverables:
- `tools/port9a_runtime_lifecycle.py`: the state model. It uses only the standard library, contains no addresses and has no I/O.
- `tests/test_port9a_runtime_lifecycle.py`: 32 tests.
- This document.

## 1. Labels and sources

- **VERIFIED**: stated directly by the cited repo document from a GM1.10C ROM or source read, or by the cited CHDK r5491 source line.
- **INFERRED**: follows from verified facts plus a stated premise.
- **UNKNOWN**: not established. Do not build on it.

"Tracked" means the source is in `origin/main`. **Local-only** means it exists only in the shared checkout `/Users/avp/Project/g3x-lite` (untracked or Git-ignored), so a clean clone cannot check it. Local-only sources used here:
- L1: `docs/CHDK_PORT0B_STUBS_AUDIT.md` (untracked).
- L2: `chdk-port/core/main.c` and `chdk-port/platform/g5x/sub/100c/boot.c`. These are upstream CHDK r5491 files in the Git-ignored `chdk-port/` checkout. They are also cited publicly via the `01luna/CHDK` mirror at `21b9a14e` in `docs/RESEARCH_LOG.md` E018/E027/E058.

## 2. Summary

| Interface | Model status | GM1.10C evidence | GM1.10C implementation |
|---|---|---|---|
| I1 Task-creation interception (`CreateTask_my`) | Modelled: idempotent install, pass-through by default | Partial: CreateTask entry VERIFIED; prologue to replay and literal UNKNOWN | **Not implemented**; not verified |
| I2 `InitFileModules` readiness gate | Modelled: latched, needs explicit success, fails closed | Name string only; task entry UNKNOWN | **Not implemented**; not verified |
| I3 SpyTask startup ordering | Modelled: runs only after READY; a timeout is a failure | Prototype creator exists but is disabled (VERIFIED) | **Disabled**; ordering unverified |
| I4 Keyboard task lifecycle (`mykbd_task` replacing PhySw) | Modelled: starts only via a routed PhySw creation; CHDK key handling needs SpyTask | PhySw entry and creator labels conflict or are local-only | **Not implemented** (stock PhySw runs) |

By default the model uses `GM110C_PRECONDITIONS`, in which every precondition is False. Under that setting it refuses the intercept, replaces no task and starts neither SpyTask nor the keyboard task (test `Gm110cDefaults`). This is how the model encodes the current evidence state.

## 3. Interfaces

### I1 — Task-creation interception

**Reference pattern** (VERIFIED, upstream source):
- `boot.c` overwrites the RAM-resident `hook_CreateTask` with an absolute jump to `CreateTask_my`.
- `CreateTask_my` compares the entry pointer in `r3` with known firmware tasks and swaps in CHDK replacements.
- It then replays the overwritten firmware prologue and jumps back to `hook_CreateTask + 9`.

Sources: `docs/RESEARCH_LOG.md` E027 (line 40) and E058 (line 71); `docs/GM110C_FUNCTION_MAP.md:176-182`; L2 `platform/g5x/sub/100c/boot.c:76-103, 109-165`.

| Claim | Label | Evidence |
|---|---|---|
| GM1.10C kernel CreateTask veneer `0xFC31BBC4` resolves to `0xBFE14A3D` (Thumb) | VERIFIED | `docs/RESTART_SD_HOST_AUDIT.md:64` (tracked, "direct") |
| `hook_CreateTask` = `0xbfe14a3c`, stored word `0x2de9fe43` | VERIFIED (local-only) | L1 line 234. Also quoted in tracked `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:87` |
| Prologue at CreateTask is `push.w {r1-r9, lr}` | **UNKNOWN** (contradicted within L1) | L1 line 112 gives `push.w {r1…r9, lr}`; L1 line 33 gives `push {r4, r5, r6, lr}` for the same address |
| The literal replayed after the prologue (E: `0x8160`; G5X: `0x00008164`) | **UNKNOWN** for GM1.10C | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:112`, F4 (line 203). The E value must not be reused |
| Our prototype has no CreateTask interception | VERIFIED | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:105, 112` |
| A RAM-copied CreateTask hook is the right integration point for GM1.10C | INFERRED | Same TCM address recorded in E and C (PORT5B F4). Not validated for C |

Model rules (`install_intercept`, `on_firmware_create_task`):
- Install requires an initialized core, no latched fault and `create_task_prologue_verified`. Without that flag the install is REFUSED, and REFUSED is permanent.
- A repeated install is a no-op. This models the hazard of a double patch replaying into itself.
- Only tasks listed in `REPLACEMENTS` are replaced (`InitFileModules`, `PhySw`). Each needs its own entry flag, and each is replaced at most once.
- Once a fault is latched, every creation passes through to the stock entry, so the firmware falls back to stock behaviour.
- The model matches by task name. The real hook matches by entry pointer. This is a deliberate simplification.

**Remaining before any implementation:**
- Resolve the L1 prologue contradiction from ROM.
- Establish the replayed literal for GM1.10C.
- Track L1 or an equivalent ROM-verified record.
- Get scoped human approval, because task/CreateTask work is outside current scope (PORT5B F4; PORT-4D boundary).

### I2 — `InitFileModules` readiness gate

**Reference pattern** (VERIFIED, upstream source):
- The replacement `init_file_modules_task` is a copy of the stock task with `core_spytask_can_start()` inserted after the file modules are up.
- That call sets `spytask_can_start = 1`.

Sources: L2 `g5x/sub/100c/boot.c:508-530`; L2 `core/main.c:101-103`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` (E, historical).

| Claim | Label | Evidence |
|---|---|---|
| GM1.10C contains the string `InitFileModules` at `0xFC0BD1AC` | VERIFIED | `docs/GM110C_FUNCTION_MAP.md:90`; `docs/RESEARCH_LOG.md` E057 (line 70) |
| GM1.10C `task_InitFileModules` entry address | **UNKNOWN** | `docs/GM110C_FUNCTION_MAP.md:90` ("entry UNKNOWN") |
| The stock task's body and its success/failure semantics on GM1.10C | **UNKNOWN** | No GM1.10C disassembly in the repo. In G5X the signal is placed before the `r4` result branch (L2 `boot.c:524-526`), so upstream signals readiness even on that path |
| ranma's port hooked InitFileModules to signal "CHDK can start" | VERIFIED as historical report (E only) | `docs/PORT5A_RANMA_PORT_RECOVERY.md:93-94`; `docs/RESEARCH_LOG.md` E012 (line 25) |
| No GM1.10C hook calls `core_spytask_can_start` today | VERIFIED | `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:259-260` |

Model rules (`file_modules_finished`):
- The gate is ARMED only when `InitFileModules` creation was routed to the replacement. That needs the intercept and `init_file_modules_entry_verified`.
- READY requires an explicit `success=True` with no latched fault.
- READY and FAILED are both latched. A signal on an unarmed gate is ignored.
- Upstream signals readiness unconditionally after the stock work, and the model does not. This is a design requirement inferred from the unknown stock semantics (INFERRED).

### I3 — SpyTask startup ordering

| Claim | Label | Evidence |
|---|---|---|
| Upstream `core_spytask` clears `spytask_can_start` itself, then waits at most 1000 × 10 ms and **continues regardless** | VERIFIED | L2 `core/main.c:136, 156` |
| Therefore, upstream loses a readiness signal sent before `core_spytask` reaches line 136, and a timeout lets SpyTask run without readiness | INFERRED | Follows from the two lines above |
| The prototype defines `CreateTask_spytask` (`"SpyTask", 0x19, 0x2000`) but its call in `task_Startup_my` is commented out | VERIFIED | Tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:75-78, 412-416`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:71` (P09) |
| SpyTask was deferred because nothing signals the gate, so it would time out after 10 s and enter unmapped routines | VERIFIED as audit conclusion | `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:23, 248-283` |
| The prototype's "10-second timeout" symptom is consistent with SpyTask running without the InitFileModules gate | INFERRED | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:204` (F5) |
| The correct GM1.10C creation point and priority for SpyTask | **UNKNOWN** | ranma's E placement after `sub_fc0bb6fe` is historical only (`PORT5B:113`) |

Model rules (`create_spytask`, `spytask_gate_timeout`):
- SpyTask is created in WAITING_GATE and moves to RUNNING only when the gate is READY and no fault is latched.
- An early readiness signal is retained. A timeout or a fault moves SpyTask to FAILED, never to RUNNING. Both rules deliberately differ from upstream (see the INFERRED row above).
- A negative-control test, `test_upstream_timeout_semantics_would_be_rejected`, shows that the upstream timeout behaviour violates the trace invariant.

### I4 — Keyboard task lifecycle

| Claim | Label | Evidence |
|---|---|---|
| Keyboard interception (`mykbd_task` / `wrap_kbd_p1_f`) is intentionally not implemented | VERIFIED | Tracked `vendor/g3x-platform/platform/g3x/kbd.c:47-49`; `docs/PORT7B_PLAYBACK_MASK_CORRECTION.md:122` |
| The prototype starts stock PhySw unmodified | VERIFIED | `boot_prototype.c:408-409`; `docs/RESTART_SD_HOST_AUDIT.md:96`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:112` |
| Stock `task_Startup` calls `0xFC1283D2`, labelled `task_PhySw` | VERIFIED call; label **UNKNOWN** | `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:222`. The call target differs from the L1 entry below. INFERRED: `0xFC1283D2` is the PhySw *creator* (G5X equivalent: the `taskcreate_physw` copy, L2 `boot.c:485-500`), not the task entry |
| GM1.10C `task_PhySw` entry `0xfc1283ad` | VERIFIED (local-only), with a provenance caveat | L1 line 231 (CONFIRMED). The E patch records the same value (`PORT5B:189`, P:9042). Whether L1 was derived independently of E is **UNKNOWN**, so treat it as unverified for GM1.10C until it is re-checked from ROM |
| Upstream G5X replaces PhySw with `mykbd_task` and enlarges its stack from 0x800 to 0x2000 | VERIFIED | L2 `g5x/sub/100c/boot.c:495-498`; E equivalent in `PORT5B:189` |
| KEYS_MASK0 includes Playback (bit 16) | VERIFIED (static), with no runtime effect yet | `docs/PORT7B_PLAYBACK_MASK_CORRECTION.md:23, 122` |
| CHDK ALT-mode key handling should only act once SpyTask runs; before that, `mykbd_task` must pass keys through | INFERRED | A model design rule (`chdk_key_handling`). Not established from GM1.10C or upstream lifecycle evidence |

Model rules:
- The keyboard task starts only when `PhySw` creation is routed by an installed intercept, with `physw_entry_verified` and no latched fault. It starts at most once.
- `chdk_key_handling` is True only when the keyboard task and SpyTask are both RUNNING and there is no fault.

## 4. Invariants tested

`check_trace` and the 32 tests cover:
1. SpyTask never runs before `fs_ready` or before the core is initialized.
2. The keyboard task never runs without an installed intercept.
3. Repeated `init_core`, `install_intercept`, `create_spytask`, `file_modules_finished` and repeated task creation change nothing.
4. After a fault, nothing downstream activates: no intercept, replacement, readiness, SpyTask or keyboard task.
5. With GM1.10C defaults, nothing activates.
6. Negative controls: hand-built bad traces must be rejected; unlisted tasks are never replaced; upstream timeout semantics are rejected.
7. Static guards on the model source: imports limited to `dataclasses` and `enum`; no `open`, `exec`, `eval`, `compile` or `__import__` calls; no integer constant ≥ `0x10000` and no 5+-digit hex literal in strings.

Mutation check, run by hand and not committed: each of four single-line mutations was killed by the suite. The mutations were removing the READY condition, ignoring `success`, allowing repeated replacement and making `init_core` non-idempotent.

## 5. Unimplemented or unverified for GM1.10C

| # | Item | Status |
|---|---|---|
| U1 | CreateTask prologue bytes and replayed literal | UNKNOWN; L1 contradicts itself |
| U2 | `task_InitFileModules` entry and body | UNKNOWN |
| U3 | `task_PhySw` entry independently of E; meaning of `0xFC1283D2` | UNKNOWN / INFERRED |
| U4 | SpyTask creation point and priority on GM1.10C | UNKNOWN |
| U5 | Any firmware-side implementation of I1–I4 | Not implemented (by design in Phase 0) |
| U6 | `task_FileWrite`, `task_TricInitTask`, CaptSeq, ExpDrv hooks | Out of scope; not modelled, and the model never replaces them |
| U7 | L1 is untracked; L2 is Git-ignored | Clean clones cannot re-check these citations |

## 6. Run

```
python3 -B -m unittest discover -s tests -p 'test_port9a_*.py' -v
```

Result on this branch: 32 tests, OK, in about 0.02 s.
