# PORT-9B — Runtime integration contract (PORT-8A sources ↔ PORT-9A model)

Date: 2026-10-28. Implementer: Claude Code, under the ChatGPT Tech Lead.
- **Branch:** `feat/port9b-runtime-contracts`, cut from `origin/main` `ddcdfdc`.
- **Scope:** an offline validator, its tests and this report.
- **Hardware:** **STRICT NO-GO**.

Labels used in this report:
- **VERIFIED**: checked here by execution, or by reading tracked source.
- **UNKNOWN**: not established.

## 1. Deliverables

| File | Purpose |
|---|---|
| `tools/port9b_runtime_contract.py` | Contract validator. Standard library only. It never writes. |
| `tests/test_port9b_runtime_contract.py` | 42 tests: positive cases, negative cases and static offline guards. |
| `docs/PORT9B_RUNTIME_CONTRACT.md` | This report. |

The validator imports `tools/bootstrap_chdk_platform.py` (PORT-8A) and `tools/port9a_runtime_lifecycle.py` (PORT-9A). Neither of those files is modified.

## 2. How sources are obtained

- **Default (no `--target`):** the validator calls PORT-8A `load_manifest` and `build_expected`. These check the vendored baselines, the patch 0002 header hashes, the preimage, the postimage and the final hashes. The five final files are then rebuilt in memory, so no bootstrap or write is needed.
- **`--target DIR`:** each manifest file must classify as PORT-8A `OK` (at its final hash). `CREATE`, `ADVANCE` or `CONFLICT` is an integrity error, so a tree that still has the unpatched `platform_kbd.h` is rejected.
- **In both modes:** the validator also reads the tracked `platform/g3x/sub/110c/boot_prototype.c`. It must be a regular file, not a symlink.

Exit codes: `0` = contract holds, `1` = violation, `3` = integrity error.

## 3. Contract

| ID | Check | Label |
|---|---|---|
| C1 | All five platform sources plus the prototype are present | VERIFIED source |
| C2 | `PLATFORM "g3x"` and `PLATFORMSUB "110c"` match the manifest firmware GM1.10C. `CAM_DRYOS 1` | VERIFIED source |
| C2 | Every `CAM_ALT_BUTTON_OPTIONS` key is in `keymap[]`, is in word 0 and is covered by `KEYS_MASK0` (`0x000533F9`). Power (bit 17) is excluded. `KEYS_MASK1` and `KEYS_MASK2` are 0 | VERIFIED source |
| C3 | No runtime interface is active in source unless the PORT-9A model, run under the accepted preconditions, allows it. The four interfaces and their source markers are listed below | VERIFIED source |
| C3 | The prototype still calls the stock PhySw creator (`bl sub_fc1283d2`) | VERIFIED source |
| C4 | Preconditions must be `GM110C_PRECONDITIONS` (all False). Any True flag is **refused** unless `allow_hypothetical=True`. A refused set does not relax C3. An allowed set labels the model results and the affected facts **HYPOTHETICAL** | policy |
| C4 | Under the defaults, the PORT-9A reference boot activates nothing, and its trace passes `check_trace` | VERIFIED (model) |
| C5 | Registry of unverified runtime facts U1–U4. Entries must contain no address, and every PORT-9A precondition flag must be covered | UNVERIFIED_RUNTIME |

C3 interfaces and the source markers that count as "active":
- **Intercept:** `CreateTask_my` or `hook_CreateTask` appears.
- **Keyboard task:** `mykbd_task` has a definition.
- **Readiness gate:** `init_file_modules_task` has a definition, or `core_spytask_can_start` appears.
- **SpyTask:** active inline asm contains `bl` or `blx` `CreateTask_spytask`.

Comment-only mentions do not count as active (tested).

The `allow_hypothetical` opt-in exists only in the Python API. The command line has no option to enable it.

## 4. Results (VERIFIED by execution)

Commit `2219f79`, fresh `git clone` into a temporary directory, Python 3, no ROM and no toolchain.

| Step | Result |
|---|---|
| Before bootstrap: `test_port9b_*.py` | 42 tests OK |
| Before bootstrap: validator, in-memory mode | `RESULT ok` (exit 0) |
| Before bootstrap: validator `--target chdk-port` | `ERROR integrity: platform/g3x/kbd.c: CREATE (missing)` (exit 3, fails closed) |
| `tools/bootstrap_chdk_platform.py` | wrote 5 files, all at their final hash |
| After bootstrap: validator `--target chdk-port` | `RESULT ok` |
| After bootstrap: PORT-7A / 7B / 7C / 8A / 9A / 9B | 18 / 19 / 23 / 34 / 32 / 42 tests, all OK |
| `git status --short` after the run | clean |

Hand mutation check (not committed). Seven single-point mutations of the validator, each killed by the suite:
- C3 always passes.
- The precondition refusal is removed.
- Refused flags leak into C3.
- The asm matcher ignores comments.
- Runtime facts are labelled VERIFIED.
- The Power bit is not checked.
- A pending patch is accepted.

The negative tests cover:
- enabled SpyTask creation, through both `bl` and `blx`;
- a `mykbd_task` definition;
- a `core_spytask_can_start` call;
- an added `CreateTask_my`;
- the stock PhySw call removed;
- `PLATFORMSUB "110e"`;
- `CAM_DRYOS 0`;
- the PORT-7B preimage mask `0x000433F9`, which leaves Playback (an ALT option) uncovered;
- Power added to the mask;
- a nonzero `KEYS_MASK1`;
- an ALT key missing from the keymap;
- a missing source;
- a duplicate `#define`;
- registry entries that carry an address, omit a flag or use an unknown flag;
- partial or full preconditions without opt-in;
- a pending patch, a modified source, a missing source, a missing or symlinked prototype, or a tampered vendor manifest in a target tree.

## 5. Unresolved integration requirements (UNKNOWN; no addresses recorded)

These are unchanged from the PORT-9A map §5. PORT-9B adds no evidence for any of them.

| ID | Requirement | Blocks |
|---|---|---|
| U1 | GM1.10C CreateTask prologue bytes and the literal replayed after them. The local stubs audit contradicts itself on these | Intercept (I1), and therefore everything below |
| U2 | `task_InitFileModules` entry and its success/failure semantics | Readiness gate (I2), SpyTask (I3) |
| U3 | `task_PhySw` entry, established independently of GM1.10E. Role of the PhySw creator call | `mykbd_task` (I4) |
| U4 | SpyTask creation point and priority on GM1.10C | SpyTask (I3) |

Additional requirements:
- **Human approval:** task and CreateTask hook work is outside Phase 0 scope. Any of it needs explicit human approval.
- **Lifting a precondition:** flipping a flag in `GM110C_PRECONDITIONS` requires all three of:
  - a ROM-verified, tracked GM1.10C record;
  - a matching registry update;
  - review.

  Until then, C4 refuses the flag.

## 6. Boundaries kept

- No CreateTask hook, bootloader, IRQ or SD change.
- No firmware build, ROM read, camera or SD operation.
- No GM1.10E value is used. The only firmware symbol the validator names is `sub_fc1283d2`, which already appears in tracked source, and a test enforces that.
- `boot_prototype.c`, `chdk-port/`, PORT-8A and PORT-9A code, `vendor/`, `patches/` and the protected candidate artifacts are untouched.

## 7. Milestone records (not modified)

Updating `docs/PROJECT_STATE.md` and `docs/HANDOFF.md` was not explicitly assigned, and the AgentBridge rules say not to edit them. They were left as they are. Both are **stale**: on `origin/main` `ddcdfdc`, `PROJECT_STATE.md` is headed "Updated: 2026-10-25" (as is `HANDOFF.md`) and leads with PORT-5E. Neither file mentions PORT-7B, 7C, 8A, 9A (all merged) or 9B. The milestone's final task should update both files.

## 8. Run

```
python3 -B -m unittest discover -s tests -p 'test_port9b_*.py' -v
python3 -B tools/port9b_runtime_contract.py                     # in-memory
python3 -B tools/bootstrap_chdk_platform.py && \
python3 -B tools/port9b_runtime_contract.py --target chdk-port  # bootstrapped tree
```
