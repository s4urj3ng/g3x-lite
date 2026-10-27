# PORT-9B — Runtime integration contract (PORT-8A sources ↔ PORT-9A model)

Date: 2026-10-28. Implementer: Gemini (review remediation) / Claude Code (initial), under the ChatGPT Tech Lead.
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
| `tests/test_port9b_runtime_contract.py` | 51 tests: positive cases, negative cases (including review counterexamples) and static offline guards. |
| `docs/PORT9B_RUNTIME_CONTRACT.md` | This report. |

The validator imports `tools/bootstrap_chdk_platform.py` (PORT-8A) and `tools/port9a_runtime_lifecycle.py` (PORT-9A). Neither of those files is modified.

## 2. How sources are obtained

- **Default (no `--target`):** the validator calls PORT-8A `load_manifest` and `build_expected`. These check the vendored baselines, the patch 0002 header hashes, the preimage, the postimage and the final hashes. The five platform files are rebuilt in memory from `vendor/` + `patches/` (so no bootstrap or write is needed), and the tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c` is read from the repository tree.
- **`--target DIR`:** each manifest file must classify as PORT-8A `OK` (at its final hash). `CREATE`, `ADVANCE` or `CONFLICT` is an integrity error, so a tree that still has the unpatched `platform_kbd.h` is rejected.
- **In both modes (`boot_prototype.c` integrity):** `platform/g3x/sub/110c/boot_prototype.c` is read from disk (either the repository's `chdk-port/` or `--target DIR`). Every path component is checked to ensure it is not a symlink, the file must be a regular file, and its SHA-256 must match the pinned digest `f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68` (enforced both during `load_sources` and in `check_contract` via `C1.prototype_sha256`). Any missing, symlinked or modified prototype is rejected fail-closed.

Exit codes: `0` = contract holds, `1` = violation, `3` = integrity error.

## 3. Contract

| ID | Check | Label |
|---|---|---|
| C1 | All five platform sources plus the prototype are present (`C1.sources`), and `boot_prototype.c` matches its pinned SHA-256 digest `f7884eb2...232e68` (`C1.prototype_sha256`) | VERIFIED source |
| C2 | `PLATFORM "g3x"` and `PLATFORMSUB "110c"` match the manifest firmware GM1.10C. `CAM_DRYOS 1` | VERIFIED source |
| C2 | Every `CAM_ALT_BUTTON_OPTIONS` key is in `keymap[]`, is in word 0 and is covered by `KEYS_MASK0` (`0x000533F9`). Power (bit 17) is excluded. `KEYS_MASK1` and `KEYS_MASK2` are 0 | VERIFIED source |
| C3 | Recognized activation markers for the four runtime interfaces are absent in source unless the PORT-9A model, run under the effective preconditions, allows them | VERIFIED source |
| C3 | The prototype still calls the stock PhySw creator (`bl sub_fc1283d2`) | VERIFIED source |
| C4 | Preconditions must be `GM110C_PRECONDITIONS` (all False). Any True flag is **refused** unless `allow_hypothetical=True`. A refused set falls back to `GM110C_PRECONDITIONS` as the effective preconditions, does not relax C3, labels `C4.model_trace` by the effective preconditions (`VERIFIED_SOURCE`), and preserves `C4.defaults_inert`. An explicitly allowed hypothetical set labels `C4.preconditions`, `C4.model_trace` and the affected C5 facts **HYPOTHETICAL** | policy |
| C4 | Under effective default preconditions, the PORT-9A reference boot activates nothing (`C4.defaults_inert`), and its trace passes `check_trace` (`C4.model_trace`) | VERIFIED (model) |
| C5 | Registry of unverified runtime facts U1–U4. Entries must contain no address, and every PORT-9A precondition flag must be covered | UNVERIFIED_RUNTIME |

### C3 recognized activation markers and detection limits

C3 interfaces and the recognized source markers that count as present:
- **Intercept (`C3.intercept`):** `CreateTask_my` or `hook_CreateTask` appears in active code.
- **Keyboard task (`C3.kbd`):** `mykbd_task` has a function definition in active code.
- **Readiness gate (`C3.gate`):** `init_file_modules_task` has a function definition, or `core_spytask_can_start` appears in active code.
- **SpyTask (`C3.spytask`):**
  - Active inline assembly in any checked source invokes or references `CreateTask_spytask`, `spytask` or `core_spytask` — including direct branches (`b`, `bl`, `bx`, `blx` with optional `.w`/`.n` width suffixes), multiple `;`- or `\n`-separated instructions per string literal, instructions preceded by labels, and symbol references / literal-pool loads (`=CreateTask_spytask` or bare symbol references in asm statements).
  - Active C code outside the prototype's dormant `spytask()` and `CreateTask_spytask()` wrapper definitions calls or references `CreateTask_spytask`, `core_spytask`, `spytask`, `_CreateTask`, `CreateTask`, or `"SpyTask"`.

Comment-only mentions (`// ...` and `/* ... */`) do not count as active (tested).

**Explicit detection limits:** Regex and source-text scanning only detects known, recognized activation markers. It is **not** a C or ARM assembly parser and **cannot prove the absence of arbitrary runtime hooks** (for example: raw numeric function-pointer casts `(void(*)(void))0x...`, preprocessor token-pasting `##` obfuscation, inline `.word`/`.byte` machine-code emission, or calls to uncrecognized ROM addresses). Source-marker absence must never be interpreted as general runtime safety.

The `allow_hypothetical` opt-in exists only in the Python API. The command line has no option to enable it.

## 4. Results (VERIFIED by execution)

Fresh checkout / clean worktree verification, Python 3, no ROM and no toolchain:

| Step | Result |
|---|---|
| Before bootstrap: `test_port9b_*.py` | 51 tests OK |
| Before bootstrap: validator, default mode (platform sources in-memory + tracked `boot_prototype.c`) | `RESULT ok` (exit 0) |
| Before bootstrap: validator `--target chdk-port` | `ERROR integrity: platform/g3x/kbd.c: CREATE (missing)` (exit 3, fails closed) |
| `tools/bootstrap_chdk_platform.py` | wrote 5 files, all at their final hash |
| After bootstrap: validator `--target chdk-port` | `RESULT ok` (exit 0) |
| After bootstrap: PORT-7A / 7B / 7C / 8A / 9A / 9B | 18 / 19 / 23 / 34 / 32 / 51 tests, all OK |
| `git status --short` after cleaning bootstrapped untracked files | clean |

The negative and regression tests cover:
- enabled SpyTask creation in `boot_prototype.c` (fails both `C1.prototype_sha256` and `C3.spytask`, and exits 3 in `--target` mode);
- all Reviewer (Claude) B1 SpyTask activation counterexamples in both `kbd.c` (`C3.spytask`) and `boot_prototype.c` (`C1.prototype_sha256` + `C3.spytask`):
  - `b.w CreateTask_spytask`, `bl.w CreateTask_spytask`, `b CreateTask_spytask`, `bx CreateTask_spytask`;
  - `ldr r3, =CreateTask_spytask; blx r3` (symbol literal load + indirect branch);
  - second instruction in multi-line (`\n`) or semicolon-separated (`;`) asm strings;
  - local/named label before branch instruction (`1: bl CreateTask_spytask`);
  - inline asm calls to `core_spytask` or `spytask`;
  - active C calls to `CreateTask_spytask()`, `core_spytask()`, `spytask(...)`, or `_CreateTask("SpyTask", ...)`;
- Reviewer (Claude) B2 prototype integrity mutations (both in `check_contract` via `C1.prototype_sha256` and in `load_sources` / `run` with exit 3):
  - reintroducing `bl sub_fc05bbea` (StartDiskboot reload loop);
  - mutating the Canon BSS zeroing upper bound from `0x003489b4` to `0x00400000`;
- Reviewer (Claude) N1 precondition refusal labeling:
  - supplying unapproved hypothetical preconditions without `allow_hypothetical=True` fails `C4.preconditions`, keeps `C4.model_trace` labelled `VERIFIED_SOURCE` (reflecting effective `GM110C_PRECONDITIONS`), and preserves `C4.defaults_inert`;
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
- a pending patch, a modified source, a missing source, a missing or symlinked prototype (or symlinked parent directory), or a tampered vendor manifest in a target tree.

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
python3 -B tools/port9b_runtime_contract.py                     # platform sources in-memory + tracked boot_prototype.c
python3 -B tools/bootstrap_chdk_platform.py && \
python3 -B tools/port9b_runtime_contract.py --target chdk-port  # bootstrapped tree
```
