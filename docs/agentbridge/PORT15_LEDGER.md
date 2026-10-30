# PORT-15 — Git-Evidenced Milestone & PR Ledger (`PORT-5E`..`PORT-14-OFFLINE`)

- **Task**: `p15-ledger` (`PORT-15 ledger: git-evidenced milestone status PORT-5E..PORT-14-OFFLINE`) `[VERIFIED]`
- **Evidence Source Policy**: All facts in this ledger are gathered exclusively via `git fetch`, `git rev-parse`, `git log`, `git ls-files`, `git show`, `git merge-base`, and `git branch -r` `[VERIFIED]`. No untracked or local-only sources are cited `[VERIFIED]`.
- **Hardware Status**: **STRICT NO-GO** (Phase 0 read-only regarding firmware and camera hardware) `[VERIFIED: docs/SAFETY.md:1-8]`.

---

## 1. Repository Base, `origin/main`, and Merge-Base Header

- **Claim**: After `git fetch`, the worktree base (`HEAD`) is `db115c6dd3f7ad69fbd839447df8a3ff68f79822`, `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251`, and the merge-base of `HEAD` and `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (`origin/main` is a direct ancestor of `HEAD`) `[VERIFIED]`.

### Verbatim Command Output

```text
$ git fetch
$ git rev-parse HEAD
db115c6dd3f7ad69fbd839447df8a3ff68f79822
$ git rev-parse origin/main
581b1a4bb30456bf18c46dc4bcf61b0375aee251
$ git merge-base HEAD origin/main
581b1a4bb30456bf18c46dc4bcf61b0375aee251
```

---

## 2. Milestone Deliverable Ledger (`PORT-5E`..`PORT-14-OFFLINE`)

> **Methodology Note (`[VERIFIED]`)**:
> - For each deliverable file claimed in `docs/PROJECT_STATE.md` or `docs/HANDOFF.md`, we record:
>   1. Both `git ls-files --with-tree=origin/main -- <path>` and `git show origin/main:<path> | head -1` (with stderr captured verbatim when absent from `origin/main`), because `git ls-files --with-tree=origin/main` unions the current worktree index (`HEAD`) with `origin/main`, whereas `git show origin/main:<path> | head -1` inspects the `origin/main` tree in isolation `[VERIFIED]`.
>   2. `git ls-files -- <path>` for presence at the worktree base (`HEAD`) `[VERIFIED]`.
>   3. `git log origin/main --diff-filter=A --format='%H %s' -- <path>` for the commit that first added `<path>` to `origin/main` (or `none` if never added to `origin/main`) `[VERIFIED]`.
>   4. Status classification: `MERGED` (present in `origin/main` tree), `PRESENT_ONLY_ON_BRANCH` (present in worktree base `HEAD` index but not in `origin/main` tree), or `ABSENT` (present in neither `origin/main` nor `HEAD`) `[VERIFIED]`.

---

### 2.1 `PORT-5E` — ROM-Verified Early Boot Literal Correction

- **Doc Mentions**: `docs/PROJECT_STATE.md:35, 51-62`; `docs/HANDOFF.md:44, 67, 93-106` `[VERIFIED]`.
- **Milestone Summary Claim**: All 6 files claimed as `PORT-5E` deliverables/modified docs in `docs/PROJECT_STATE.md` and `docs/HANDOFF.md` are present at both `origin/main` and the worktree base (`HEAD`), with status **`MERGED`** (`f8cc7a9743a768351c6e95e80d956f3ee52dbd09` on `origin/main`) `[VERIFIED]`.
- **Doc Staleness Note**: `docs/HANDOFF.md:104` still describes `PORT-5E` as `"Dedicated branch fix/port5e-early-boot-literals created from main, pushed to origin, and Draft PR opened targeting main"`, which is superseded on `origin/main` by commit `f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | `docs/PROJECT_STATE.md:35, 51`; `docs/HANDOFF.md:67, 95` | `e418ccfeb7dab8c0dd2db6b3b8d988beec2b5e60 fix(sd-restart): track prototype sources, add patch artifact, and reconcile MMIO bit semantics` *(modified in `PORT-5E` commit `f8cc7a9743a768351c6e95e80d956f3ee52dbd09`)* | `MERGED` | `VERIFIED` |
| `tests/test_early_boot_literals.py` | `docs/PROJECT_STATE.md:51, 54, 62`; `docs/HANDOFF.md:95, 101, 106` | `f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` | `MERGED` | `VERIFIED` |
| `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md` | `docs/PROJECT_STATE.md:56`; `docs/HANDOFF.md:95` | `f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` | `MERGED` | `VERIFIED` |
| `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | `docs/PROJECT_STATE.md:57`; `docs/HANDOFF.md:95` | `f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` | `MERGED` | `VERIFIED` |
| `docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md` | `docs/PROJECT_STATE.md:58`; `docs/HANDOFF.md:95` | `f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` | `MERGED` | `VERIFIED` |
| `docs/REPRODUCIBILITY_MANIFEST.md` | `docs/PROJECT_STATE.md:59`; `docs/HANDOFF.md:95` | `a9ead89aa735845cee66e2ed270e33c7688c5b71 docs(audit): add reproducibility manifest and separate clean-checkout vs offline tests` *(modified in `PORT-5E` commit `f8cc7a9743a768351c6e95e80d956f3ee52dbd09`)* | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-5E`)

```text
$ git ls-files --with-tree=origin/main -- chdk-port/platform/g3x/sub/110c/boot_prototype.c
chdk-port/platform/g3x/sub/110c/boot_prototype.c
$ git show origin/main:chdk-port/platform/g3x/sub/110c/boot_prototype.c | head -1
// =============================================================================
$ git ls-files -- chdk-port/platform/g3x/sub/110c/boot_prototype.c
chdk-port/platform/g3x/sub/110c/boot_prototype.c
$ git log origin/main --diff-filter=A --format='%H %s' -- chdk-port/platform/g3x/sub/110c/boot_prototype.c
e418ccfeb7dab8c0dd2db6b3b8d988beec2b5e60 fix(sd-restart): track prototype sources, add patch artifact, and reconcile MMIO bit semantics

$ git ls-files --with-tree=origin/main -- tests/test_early_boot_literals.py
tests/test_early_boot_literals.py
$ git show origin/main:tests/test_early_boot_literals.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tests/test_early_boot_literals.py
tests/test_early_boot_literals.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_early_boot_literals.py
f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)

$ git ls-files --with-tree=origin/main -- docs/CHDK_PORT1C1_CRITICAL_AUDIT.md
docs/CHDK_PORT1C1_CRITICAL_AUDIT.md
$ git show origin/main:docs/CHDK_PORT1C1_CRITICAL_AUDIT.md | head -1
# CHDK-PORT-1C.1: Critical Boot Control-Flow Audit Report
$ git ls-files -- docs/CHDK_PORT1C1_CRITICAL_AUDIT.md
docs/CHDK_PORT1C1_CRITICAL_AUDIT.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/CHDK_PORT1C1_CRITICAL_AUDIT.md
f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)

$ git ls-files --with-tree=origin/main -- docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
$ git show origin/main:docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md | head -1
# PORT-5B — Ranma G3 X historical boot comparison
$ git ls-files -- docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)

$ git ls-files --with-tree=origin/main -- docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
$ git show origin/main:docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md | head -1
# PORT-5C — GM1.10C early boot consistency audit
$ git ls-files -- docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
f8cc7a9743a768351c6e95e80d956f3ee52dbd09 fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)

$ git ls-files --with-tree=origin/main -- docs/REPRODUCIBILITY_MANIFEST.md
docs/REPRODUCIBILITY_MANIFEST.md
$ git show origin/main:docs/REPRODUCIBILITY_MANIFEST.md | head -1
# Reproducibility Manifest: G3 X CHDK Restart & SD1stInit Prototype
$ git ls-files -- docs/REPRODUCIBILITY_MANIFEST.md
docs/REPRODUCIBILITY_MANIFEST.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/REPRODUCIBILITY_MANIFEST.md
a9ead89aa735845cee66e2ed270e33c7688c5b71 docs(audit): add reproducibility manifest and separate clean-checkout vs offline tests
```

---

### 2.2 `PORT-7A` & `PORT-7B` — Platform Configuration & Playback ALT Override Mask Correction

- **Doc Mentions**: `docs/PROJECT_STATE.md:27, 487-488`; `docs/HANDOFF.md:44, 46-48` (`PORT-7A` is cited inside the `PORT-7B` ledger entry and status summary) `[VERIFIED]`.
- **Milestone Summary Claim**: All 8 files explicitly claimed for `PORT-7A` / `PORT-7B` in `docs/PROJECT_STATE.md:27` and `docs/HANDOFF.md:47` (plus companion doc `docs/PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md` added in the same commit) are present at both `origin/main` and the worktree base (`HEAD`), with status **`MERGED`** (`a0a33a4323b6ae65801f593cd44636f7b5629ac6` on `origin/main`) `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT7B_PLAYBACK_MASK_CORRECTION.md` | `docs/PROJECT_STATE.md:27`; `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `patches/0002-port7b-keys-mask0.patch` | `docs/PROJECT_STATE.md:27`; `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/test_port7b_reproducibility.py` | `docs/PROJECT_STATE.md:27`; `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/test_port7a_platform_configuration.py` | `docs/PROJECT_STATE.md:27`; `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port7b/kbd.c` | `docs/PROJECT_STATE.md:27` (`tests/fixtures/port7b/*`); `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port7b/platform_camera.h` | `docs/PROJECT_STATE.md:27` (`tests/fixtures/port7b/*`); `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port7b/platform_kbd.h.preimage` | `docs/PROJECT_STATE.md:27` (`tests/fixtures/port7b/*`); `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port7b/shooting.c` | `docs/PROJECT_STATE.md:27` (`tests/fixtures/port7b/*`); `docs/HANDOFF.md:47` | `a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-7A` / `PORT-7B`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT7B_PLAYBACK_MASK_CORRECTION.md
docs/PORT7B_PLAYBACK_MASK_CORRECTION.md
$ git show origin/main:docs/PORT7B_PLAYBACK_MASK_CORRECTION.md | head -1
# PORT-7B — Playback ALT override mask correction
$ git ls-files -- docs/PORT7B_PLAYBACK_MASK_CORRECTION.md
docs/PORT7B_PLAYBACK_MASK_CORRECTION.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT7B_PLAYBACK_MASK_CORRECTION.md
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- patches/0002-port7b-keys-mask0.patch
patches/0002-port7b-keys-mask0.patch
$ git show origin/main:patches/0002-port7b-keys-mask0.patch | head -1
# Patch: G3 X GM1.10C CHDK port - PORT-7B Playback ALT override mask correction
$ git ls-files -- patches/0002-port7b-keys-mask0.patch
patches/0002-port7b-keys-mask0.patch
$ git log origin/main --diff-filter=A --format='%H %s' -- patches/0002-port7b-keys-mask0.patch
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/test_port7b_reproducibility.py
tests/test_port7b_reproducibility.py
$ git show origin/main:tests/test_port7b_reproducibility.py | head -1
"""PORT-7B: clean-checkout reproducibility of the Playback KEYS_MASK0 correction.
$ git ls-files -- tests/test_port7b_reproducibility.py
tests/test_port7b_reproducibility.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port7b_reproducibility.py
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/test_port7a_platform_configuration.py
tests/test_port7a_platform_configuration.py
$ git show origin/main:tests/test_port7a_platform_configuration.py | head -1
"""PORT-7A: source-only GM1.10C configuration regression checks.
$ git ls-files -- tests/test_port7a_platform_configuration.py
tests/test_port7a_platform_configuration.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port7a_platform_configuration.py
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port7b/kbd.c
tests/fixtures/port7b/kbd.c
$ git show origin/main:tests/fixtures/port7b/kbd.c | head -1
KeyMap keymap[] = {
$ git ls-files -- tests/fixtures/port7b/kbd.c
tests/fixtures/port7b/kbd.c
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port7b/kbd.c
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port7b/platform_camera.h
tests/fixtures/port7b/platform_camera.h
$ git show origin/main:tests/fixtures/port7b/platform_camera.h | head -1
    #define CAM_ADJUSTABLE_ALT_BUTTON           1
$ git ls-files -- tests/fixtures/port7b/platform_camera.h
tests/fixtures/port7b/platform_camera.h
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port7b/platform_camera.h
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port7b/platform_kbd.h.preimage
tests/fixtures/port7b/platform_kbd.h.preimage
$ git show origin/main:tests/fixtures/port7b/platform_kbd.h.preimage | head -1
#ifndef PLATFORM_KBD_H
$ git ls-files -- tests/fixtures/port7b/platform_kbd.h.preimage
tests/fixtures/port7b/platform_kbd.h.preimage
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port7b/platform_kbd.h.preimage
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port7b/shooting.c
tests/fixtures/port7b/shooting.c
$ git show origin/main:tests/fixtures/port7b/shooting.c | head -1
// canon_mode_list 0xfca90f10 (found @0xfc07317c)
$ git ls-files -- tests/fixtures/port7b/shooting.c
tests/fixtures/port7b/shooting.c
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port7b/shooting.c
a0a33a4323b6ae65801f593cd44636f7b5629ac6 PORT-7B: Playback ALT override mask correction (KEYS_MASK0 0x000533F9) via patch + clean-clone fixtures (#6)
```

---

### 2.3 `PORT-7C` — CHDK Platform Offline Validation Framework

- **Doc Mentions**: `docs/PROJECT_STATE.md:29, 44, 487-488, 552`; `docs/HANDOFF.md:44, 52-54, 87` `[VERIFIED]`.
- **Milestone Summary Claim**: Both deliverables claimed for `PORT-7C` are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`16b954a1537e7d516d64deba54b21d7ca26d78cb` on `origin/main`) `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md` | `docs/PROJECT_STATE.md:29`; `docs/HANDOFF.md:53` | `16b954a1537e7d516d64deba54b21d7ca26d78cb PORT-7C: CHDK platform offline validation framework and comparative analysis (#8)` | `MERGED` | `VERIFIED` |
| `tests/test_port7c_platform_validation.py` | `docs/PROJECT_STATE.md:29`; `docs/HANDOFF.md:53` | `16b954a1537e7d516d64deba54b21d7ca26d78cb PORT-7C: CHDK platform offline validation framework and comparative analysis (#8)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-7C`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md
docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md
$ git show origin/main:docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md | head -1
# PORT-7C — CHDK Platform Offline Validation Framework
$ git ls-files -- docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md
docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md
16b954a1537e7d516d64deba54b21d7ca26d78cb PORT-7C: CHDK platform offline validation framework and comparative analysis (#8)

$ git ls-files --with-tree=origin/main -- tests/test_port7c_platform_validation.py
tests/test_port7c_platform_validation.py
$ git show origin/main:tests/test_port7c_platform_validation.py | head -1
"""PORT-7C: CHDK Platform Offline Validation Framework.
$ git ls-files -- tests/test_port7c_platform_validation.py
tests/test_port7c_platform_validation.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port7c_platform_validation.py
16b954a1537e7d516d64deba54b21d7ca26d78cb PORT-7C: CHDK platform offline validation framework and comparative analysis (#8)
```

---

### 2.4 `PORT-8A` — Reproducible G3 X Platform Bootstrap

- **Doc Mentions**: `docs/PROJECT_STATE.md:28, 32, 487-488`; `docs/HANDOFF.md:44, 49-51, 62` `[VERIFIED]`.
- **Milestone Summary Claim**: All 9 deliverables claimed for `PORT-8A` are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`84573f6cd036dfc716963e698ae00160514c9cd9` on `origin/main`) `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT8A_PLATFORM_BOOTSTRAP.md` | `docs/PROJECT_STATE.md:28`; `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/MANIFEST.json` | `docs/PROJECT_STATE.md:28`; `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/kbd.c` | `docs/PROJECT_STATE.md:28` (`vendor/g3x-platform/platform/g3x/*`, `kbd.c`); `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/lib.c` | `docs/PROJECT_STATE.md:28` (`vendor/g3x-platform/platform/g3x/*`, `lib.c`); `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/platform_camera.h` | `docs/PROJECT_STATE.md:28` (`vendor/g3x-platform/platform/g3x/*`, `platform_camera.h`); `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/platform_kbd.h` | `docs/PROJECT_STATE.md:28` (`vendor/g3x-platform/platform/g3x/*`, `platform_kbd.h`); `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/shooting.c` | `docs/PROJECT_STATE.md:28` (`vendor/g3x-platform/platform/g3x/*`, `shooting.c`); `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `tools/bootstrap_chdk_platform.py` | `docs/PROJECT_STATE.md:28, 48, 555`; `docs/HANDOFF.md:50, 90` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |
| `tests/test_port8a_platform_bootstrap.py` | `docs/PROJECT_STATE.md:28`; `docs/HANDOFF.md:50` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-8A`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT8A_PLATFORM_BOOTSTRAP.md
docs/PORT8A_PLATFORM_BOOTSTRAP.md
$ git show origin/main:docs/PORT8A_PLATFORM_BOOTSTRAP.md | head -1
# PORT-8A — Reproducible G3 X platform source bootstrap
$ git ls-files -- docs/PORT8A_PLATFORM_BOOTSTRAP.md
docs/PORT8A_PLATFORM_BOOTSTRAP.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT8A_PLATFORM_BOOTSTRAP.md
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/MANIFEST.json
vendor/g3x-platform/MANIFEST.json
$ git show origin/main:vendor/g3x-platform/MANIFEST.json | head -1
{
$ git ls-files -- vendor/g3x-platform/MANIFEST.json
vendor/g3x-platform/MANIFEST.json
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/MANIFEST.json
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/platform/g3x/kbd.c
vendor/g3x-platform/platform/g3x/kbd.c
$ git show origin/main:vendor/g3x-platform/platform/g3x/kbd.c | head -1
// G3X keyboard mapping foundation
$ git ls-files -- vendor/g3x-platform/platform/g3x/kbd.c
vendor/g3x-platform/platform/g3x/kbd.c
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/platform/g3x/kbd.c
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/platform/g3x/lib.c
vendor/g3x-platform/platform/g3x/lib.c
$ git show origin/main:vendor/g3x-platform/platform/g3x/lib.c | head -1
#include "platform.h"
$ git ls-files -- vendor/g3x-platform/platform/g3x/lib.c
vendor/g3x-platform/platform/g3x/lib.c
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/platform/g3x/lib.c
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/platform/g3x/platform_camera.h
vendor/g3x-platform/platform/g3x/platform_camera.h
$ git show origin/main:vendor/g3x-platform/platform/g3x/platform_camera.h | head -1
// Camera - g3x - platform_camera.h
$ git ls-files -- vendor/g3x-platform/platform/g3x/platform_camera.h
vendor/g3x-platform/platform/g3x/platform_camera.h
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/platform/g3x/platform_camera.h
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/platform/g3x/platform_kbd.h
vendor/g3x-platform/platform/g3x/platform_kbd.h
$ git show origin/main:vendor/g3x-platform/platform/g3x/platform_kbd.h | head -1
#ifndef PLATFORM_KBD_H
$ git ls-files -- vendor/g3x-platform/platform/g3x/platform_kbd.h
vendor/g3x-platform/platform/g3x/platform_kbd.h
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/platform/g3x/platform_kbd.h
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- vendor/g3x-platform/platform/g3x/shooting.c
vendor/g3x-platform/platform/g3x/shooting.c
$ git show origin/main:vendor/g3x-platform/platform/g3x/shooting.c | head -1
#include "platform.h"
$ git ls-files -- vendor/g3x-platform/platform/g3x/shooting.c
vendor/g3x-platform/platform/g3x/shooting.c
$ git log origin/main --diff-filter=A --format='%H %s' -- vendor/g3x-platform/platform/g3x/shooting.c
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- tools/bootstrap_chdk_platform.py
tools/bootstrap_chdk_platform.py
$ git show origin/main:tools/bootstrap_chdk_platform.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tools/bootstrap_chdk_platform.py
tools/bootstrap_chdk_platform.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/bootstrap_chdk_platform.py
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)

$ git ls-files --with-tree=origin/main -- tests/test_port8a_platform_bootstrap.py
tests/test_port8a_platform_bootstrap.py
$ git show origin/main:tests/test_port8a_platform_bootstrap.py | head -1
"""PORT-8A: clean-checkout regression tests for tools/bootstrap_chdk_platform.py.
$ git ls-files -- tests/test_port8a_platform_bootstrap.py
tests/test_port8a_platform_bootstrap.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port8a_platform_bootstrap.py
84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)
```

---

### 2.5 `PORT-9A` — Offline CHDK Runtime Integration Foundation

- **Doc Mentions**: `docs/PROJECT_STATE.md:30, 32, 487-488`; `docs/HANDOFF.md:44, 55-57, 62` `[VERIFIED]`.
- **Milestone Summary Claim**: All 3 deliverables claimed for `PORT-9A` are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c` on `origin/main`) `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md` | `docs/PROJECT_STATE.md:30`; `docs/HANDOFF.md:56` | `7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)` | `MERGED` | `VERIFIED` |
| `tools/port9a_runtime_lifecycle.py` | `docs/PROJECT_STATE.md:30, 543`; `docs/HANDOFF.md:56` | `7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)` | `MERGED` | `VERIFIED` |
| `tests/test_port9a_runtime_lifecycle.py` | `docs/PROJECT_STATE.md:30`; `docs/HANDOFF.md:56` | `7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-9A`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT9A_RUNTIME_INTEGRATION_MAP.md
docs/PORT9A_RUNTIME_INTEGRATION_MAP.md
$ git show origin/main:docs/PORT9A_RUNTIME_INTEGRATION_MAP.md | head -1
# PORT-9A — CHDK runtime integration map (GM1.10C)
$ git ls-files -- docs/PORT9A_RUNTIME_INTEGRATION_MAP.md
docs/PORT9A_RUNTIME_INTEGRATION_MAP.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT9A_RUNTIME_INTEGRATION_MAP.md
7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)

$ git ls-files --with-tree=origin/main -- tools/port9a_runtime_lifecycle.py
tools/port9a_runtime_lifecycle.py
$ git show origin/main:tools/port9a_runtime_lifecycle.py | head -1
"""PORT-9A / PORT-11B: offline lifecycle and safety model for CHDK runtime integration.
$ git ls-files -- tools/port9a_runtime_lifecycle.py
tools/port9a_runtime_lifecycle.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port9a_runtime_lifecycle.py
7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)

$ git ls-files --with-tree=origin/main -- tests/test_port9a_runtime_lifecycle.py
tests/test_port9a_runtime_lifecycle.py
$ git show origin/main:tests/test_port9a_runtime_lifecycle.py | head -1
"""PORT-9A / PORT-11B: offline tests for tools/port9a_runtime_lifecycle.py.
$ git ls-files -- tests/test_port9a_runtime_lifecycle.py
tests/test_port9a_runtime_lifecycle.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port9a_runtime_lifecycle.py
7663d01baf4c67c0f5c55d4acd9ba43ca1a8536c feat(port9a): offline CHDK runtime lifecycle model, tests and GM1.10C integration map (#9)
```

---

### 2.6 `PORT-9B` — Offline Runtime Integration Contract

- **Doc Mentions**: `docs/PROJECT_STATE.md:32, 48, 487-488, 543, 555, 562, 573`; `docs/HANDOFF.md:34, 44, 60-62, 90, 2031, 2041` `[VERIFIED]`.
- **Milestone Summary Claim**: All 3 deliverables claimed for `PORT-9B` (`docs/PORT9B_RUNTIME_CONTRACT.md`, `tools/port9b_runtime_contract.py`, `tests/test_port9b_runtime_contract.py`) are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`4206ec573c951ebd460d2041ed081c39f11aa020` on `origin/main`) `[VERIFIED]`. See **Section 3** below for the dedicated `PORT-9B` and `4206ec5` verification and contradiction analysis `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT9B_RUNTIME_CONTRACT.md` | `docs/PROJECT_STATE.md:32`; `docs/HANDOFF.md:61` | `4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)` | `MERGED` | `VERIFIED` |
| `tools/port9b_runtime_contract.py` | `docs/PROJECT_STATE.md:32, 48, 543, 555`; `docs/HANDOFF.md:34, 61, 90` | `4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)` | `MERGED` | `VERIFIED` |
| `tests/test_port9b_runtime_contract.py` | `docs/PROJECT_STATE.md:32`; `docs/HANDOFF.md:61` | `4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-9B`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT9B_RUNTIME_CONTRACT.md
docs/PORT9B_RUNTIME_CONTRACT.md
$ git show origin/main:docs/PORT9B_RUNTIME_CONTRACT.md | head -1
# PORT-9B — Runtime integration contract (PORT-8A sources ↔ PORT-9A model)
$ git ls-files -- docs/PORT9B_RUNTIME_CONTRACT.md
docs/PORT9B_RUNTIME_CONTRACT.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT9B_RUNTIME_CONTRACT.md
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)

$ git ls-files --with-tree=origin/main -- tools/port9b_runtime_contract.py
tools/port9b_runtime_contract.py
$ git show origin/main:tools/port9b_runtime_contract.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tools/port9b_runtime_contract.py
tools/port9b_runtime_contract.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port9b_runtime_contract.py
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)

$ git ls-files --with-tree=origin/main -- tests/test_port9b_runtime_contract.py
tests/test_port9b_runtime_contract.py
$ git show origin/main:tests/test_port9b_runtime_contract.py | head -1
"""PORT-9B: tests for tools/port9b_runtime_contract.py.
$ git ls-files -- tests/test_port9b_runtime_contract.py
tests/test_port9b_runtime_contract.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port9b_runtime_contract.py
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)
```

---

### 2.7 `PORT-9C` — Milestone Consolidation & Integration Status Synchronization

- **Doc Mentions**: `docs/PROJECT_STATE.md:25-49, 487`; `docs/HANDOFF.md:41-91` `[VERIFIED]`.
- **Milestone Summary Claim**: Both deliverables claimed for `PORT-9C` (`docs/PROJECT_STATE.md` and `docs/HANDOFF.md`, plus `AGENTS.md` cited under PR #10 at `docs/PROJECT_STATE.md:31` and `docs/HANDOFF.md:58-59`) are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`cbe74cf53097386139410da00cdb6c277d40a1a0 PORT-9C: milestone consolidation in PROJECT_STATE and HANDOFF (PRs #6–#11) (#12)` on `origin/main`) `[VERIFIED]`.
- **Doc Staleness Note**: `docs/PROJECT_STATE.md:25, 487` and `docs/HANDOFF.md:43` still label `PORT-9C` as `DRAFT_PR_OPEN / PENDING_MERGE` (PR #12), which is superseded on `origin/main` by commit `cbe74cf53097386139410da00cdb6c277d40a1a0` `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PROJECT_STATE.md` | `docs/PROJECT_STATE.md:25`; `docs/HANDOFF.md:43, 44` | `ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite` *(updated for `PORT-9C` on `origin/main` in `cbe74cf53097386139410da00cdb6c277d40a1a0`)* | `MERGED` | `VERIFIED` |
| `docs/HANDOFF.md` | `docs/PROJECT_STATE.md:25`; `docs/HANDOFF.md:43, 44` | `ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite` *(updated for `PORT-9C` on `origin/main` in `cbe74cf53097386139410da00cdb6c277d40a1a0`)* | `MERGED` | `VERIFIED` |
| `AGENTS.md` *(cited in `PORT-9C` ledger for PR #10)* | `docs/PROJECT_STATE.md:31`; `docs/HANDOFF.md:58-59` | `ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite` *(updated in `52a361c198d8bfab5738e7ec31753682e26a115f` / merged in `ddcdfdc0a87e1ee78d5155d944966790e26e116a`)* | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-9C`)

```text
$ git ls-files --with-tree=origin/main -- docs/PROJECT_STATE.md
docs/PROJECT_STATE.md
$ git show origin/main:docs/PROJECT_STATE.md | head -1
# Project state
$ git ls-files -- docs/PROJECT_STATE.md
docs/PROJECT_STATE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PROJECT_STATE.md
ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite

$ git ls-files --with-tree=origin/main -- docs/HANDOFF.md
docs/HANDOFF.md
$ git show origin/main:docs/HANDOFF.md | head -1
# Agent handoff
$ git ls-files -- docs/HANDOFF.md
docs/HANDOFF.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/HANDOFF.md
ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite

$ git ls-files --with-tree=origin/main -- AGENTS.md
AGENTS.md
$ git show origin/main:AGENTS.md | head -1
# Agent contract — Codex / Claude Code / Gemini CLI
$ git ls-files -- AGENTS.md
AGENTS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- AGENTS.md
ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite
```

---

### 2.8 `PORT-10A` (and `PORT-10B` Zero-ROM Alternative Mentioned in `PORT-9C`)

- **Doc Mentions**: `docs/PROJECT_STATE.md:44, 552`; `docs/HANDOFF.md:83-87` `[VERIFIED]`.
- **Milestone Summary Claim**:
  - In `docs/PROJECT_STATE.md:44, 552` and `docs/HANDOFF.md:83-87`, `PORT-10A` is listed only as a recommended next investigation referencing ignored local dump `firmware/dumps/GM1.10C/PRIMARY.BIN` (**`ABSENT`** from git by policy) and alternative zero-ROM targets `vendor/g3x-platform/platform/g3x/kbd.c` and `vendor/g3x-platform/MANIFEST.json` (**`MERGED`**) `[VERIFIED]`.
  - On `origin/main`, commit `bf698c1dcd0470f778aa9e5d36099459753bd4de` (`PORT-10A: deep runtime preconditions evidence consolidation and contradiction audit (#13)`) subsequently added `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md` (**`MERGED`**), and commit `7cf565e1eff188f4c2b342108eafe5ee688f4f8c` (`fix(port10b): correct stale physw_event_table index comments in kbd.c (#14)`) updated `vendor/g3x-platform/platform/g3x/kbd.c`, `vendor/g3x-platform/MANIFEST.json`, and `tests/fixtures/port7b/kbd.c` (`MERGED`), even though `docs/PROJECT_STATE.md` and `docs/HANDOFF.md` were not updated for `#13` or `#14` `[VERIFIED]`.

| File Mentioned / Added on `origin/main` | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `firmware/dumps/GM1.10C/PRIMARY.BIN` *(referenced as local-only ROM input, never committed)* | `docs/PROJECT_STATE.md:44, 552`; `docs/HANDOFF.md:83` | `none` | `ABSENT` | `VERIFIED` |
| `vendor/g3x-platform/platform/g3x/kbd.c` *(referenced as zero-ROM alternative target)* | `docs/PROJECT_STATE.md:44, 552`; `docs/HANDOFF.md:87` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` *(modified in `7cf565e1eff188f4c2b342108eafe5ee688f4f8c fix(port10b): correct stale physw_event_table index comments in kbd.c (#14)`)* | `MERGED` | `VERIFIED` |
| `vendor/g3x-platform/MANIFEST.json` *(referenced as zero-ROM alternative target)* | `docs/HANDOFF.md:87` | `84573f6cd036dfc716963e698ae00160514c9cd9 PORT-8A: reproducible G3 X platform bootstrap (restacked on merged PORT-7B) (#7)` *(modified in `7cf565e1eff188f4c2b342108eafe5ee688f4f8c fix(port10b): correct stale physw_event_table index comments in kbd.c (#14)`)* | `MERGED` | `VERIFIED` |
| `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md` *(not claimed in `PROJECT_STATE.md`/`HANDOFF.md`, but added by `PORT-10A` commit `bf698c1` on `origin/main`)* | *Not cited in `docs/PROJECT_STATE.md` or `docs/HANDOFF.md`* | `bf698c1dcd0470f778aa9e5d36099459753bd4de PORT-10A: deep runtime preconditions evidence consolidation and contradiction audit (#13)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-10A` / `PORT-10B`)

```text
$ git ls-files --with-tree=origin/main -- firmware/dumps/GM1.10C/PRIMARY.BIN
$ git show origin/main:firmware/dumps/GM1.10C/PRIMARY.BIN 2>&1 | head -1
fatal: path 'firmware/dumps/GM1.10C/PRIMARY.BIN' does not exist in 'origin/main'
$ git ls-files -- firmware/dumps/GM1.10C/PRIMARY.BIN
$ git log origin/main --diff-filter=A --format='%H %s' -- firmware/dumps/GM1.10C/PRIMARY.BIN
none

$ git ls-files --with-tree=origin/main -- docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md
docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md
$ git show origin/main:docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md | head -1
# PORT-10A — Deep Runtime Preconditions Research: Evidence Consolidation & Contradiction Audit (GM1.10C)
$ git ls-files -- docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md
docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md
bf698c1dcd0470f778aa9e5d36099459753bd4de PORT-10A: deep runtime preconditions evidence consolidation and contradiction audit (#13)
```

---

### 2.9 `PORT-11A` (and `PORT-11B` / PR #16 Baseline Mentioned in `PORT-11C`)

- **Doc Mentions**:
  - `PORT-11A`: `docs/PROJECT_STATE.md:10, 581, 582`; `docs/HANDOFF.md:7, 21, 2049, 2050` `[VERIFIED]`.
  - `PR #16` (`PORT-11B` baseline): `docs/PROJECT_STATE.md:5`; `docs/HANDOFF.md:6` (`from origin/main 7f39946 (merged PR #16 baseline)`) `[VERIFIED]`.
- **Milestone Summary Claim**: `docs/PORT11A_GM110C_ROM_EVIDENCE.md` (cited at `docs/PROJECT_STATE.md:581, 582` and `docs/HANDOFF.md:2049, 2050`) and the `PORT-11A` fixtures `tests/fixtures/port11a_manifest.json` and `tests/fixtures/port11a_trusted_scopes.json` (cited at `docs/PROJECT_STATE.md:4, 10, 22` and `docs/HANDOFF.md:6, 21, 33, 38`), as well as `docs/PORT11B_RUNTIME_SAFETY_MODEL.md` from `7f39946` (`#16`), are all present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT11A_GM110C_ROM_EVIDENCE.md` | `docs/PROJECT_STATE.md:581, 582`; `docs/HANDOFF.md:2049, 2050` | `9c1c544db5421527ccd933407f957ff3266b19d1 docs(port11a): verify U1/U2/U3 runtime prerequisites from GM1.10C ROM (#15)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port11a_manifest.json` | `docs/PROJECT_STATE.md:4, 10, 22`; `docs/HANDOFF.md:6, 21, 33, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port11a_trusted_scopes.json` | `docs/PROJECT_STATE.md:4, 10, 22`; `docs/HANDOFF.md:6, 21, 33, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `docs/PORT11B_RUNTIME_SAFETY_MODEL.md` *(from `7f39946` merged PR #16 baseline cited at `docs/PROJECT_STATE.md:5`; `docs/HANDOFF.md:6`)* | `docs/PROJECT_STATE.md:5`; `docs/HANDOFF.md:6` *(by commit `7f39946` / PR #16)* | `7f39946010b802a4440b92f20e0cfd8fb9eb8916 feat(port11b): refine offline runtime safety model and contract with PORT-11A static evidence (#16)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-11A` / `PORT-11B`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT11A_GM110C_ROM_EVIDENCE.md
docs/PORT11A_GM110C_ROM_EVIDENCE.md
$ git show origin/main:docs/PORT11A_GM110C_ROM_EVIDENCE.md | head -1
# PORT-11A — GM1.10C ROM Evidence Verification for Runtime Prerequisites (U1, U2, U3)
$ git ls-files -- docs/PORT11A_GM110C_ROM_EVIDENCE.md
docs/PORT11A_GM110C_ROM_EVIDENCE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT11A_GM110C_ROM_EVIDENCE.md
9c1c544db5421527ccd933407f957ff3266b19d1 docs(port11a): verify U1/U2/U3 runtime prerequisites from GM1.10C ROM (#15)

$ git ls-files --with-tree=origin/main -- docs/PORT11B_RUNTIME_SAFETY_MODEL.md
docs/PORT11B_RUNTIME_SAFETY_MODEL.md
$ git show origin/main:docs/PORT11B_RUNTIME_SAFETY_MODEL.md | head -1
# PORT-11B — Runtime Integration Safety Model (GM1.10C)
$ git ls-files -- docs/PORT11B_RUNTIME_SAFETY_MODEL.md
docs/PORT11B_RUNTIME_SAFETY_MODEL.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT11B_RUNTIME_SAFETY_MODEL.md
7f39946010b802a4440b92f20e0cfd8fb9eb8916 feat(port11b): refine offline runtime safety model and contract with PORT-11A static evidence (#16)
```

---

### 2.10 `PORT-11C` — Offline Evidence Validation Harness

- **Doc Mentions**: `docs/PROJECT_STATE.md:4-23`; `docs/HANDOFF.md:4-39` `[VERIFIED]`.
- **Milestone Summary Claim**: All 5 deliverables claimed for `PORT-11C` are present at `origin/main` and at the worktree base (`HEAD`), with status **`MERGED`** (`a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` on `origin/main`) `[VERIFIED]`.
- **Doc Staleness Note**: `docs/PROJECT_STATE.md:5` and `docs/HANDOFF.md:6` still state `DRAFT_PR_OPEN / PENDING_TECH_LEAD_REVIEW (PR #17)` and `NOT merged`, which is superseded on `origin/main` by commit `a028ef981542eeaddd3a317d9cdb8e908601724e` `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `tools/port11c_evidence_validator.py` | `docs/PROJECT_STATE.md:4, 8, 22`; `docs/HANDOFF.md:6, 9, 33, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `tests/test_port11c_evidence_validator.py` | `docs/PROJECT_STATE.md:4, 9, 22`; `docs/HANDOFF.md:6, 20, 32, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port11a_manifest.json` | `docs/PROJECT_STATE.md:4, 10, 22`; `docs/HANDOFF.md:6, 21, 33, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `tests/fixtures/port11a_trusted_scopes.json` | `docs/PROJECT_STATE.md:4, 10, 22`; `docs/HANDOFF.md:6, 21, 33, 38` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |
| `docs/PORT11C_EVIDENCE_HARNESS.md` | `docs/PROJECT_STATE.md:4, 11`; `docs/HANDOFF.md:6, 22` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-11C`)

```text
$ git ls-files --with-tree=origin/main -- tools/port11c_evidence_validator.py
tools/port11c_evidence_validator.py
$ git show origin/main:tools/port11c_evidence_validator.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tools/port11c_evidence_validator.py
tools/port11c_evidence_validator.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port11c_evidence_validator.py
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)

$ git ls-files --with-tree=origin/main -- tests/test_port11c_evidence_validator.py
tests/test_port11c_evidence_validator.py
$ git show origin/main:tests/test_port11c_evidence_validator.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tests/test_port11c_evidence_validator.py
tests/test_port11c_evidence_validator.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port11c_evidence_validator.py
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port11a_manifest.json
tests/fixtures/port11a_manifest.json
$ git show origin/main:tests/fixtures/port11a_manifest.json | head -1
{
$ git ls-files -- tests/fixtures/port11a_manifest.json
tests/fixtures/port11a_manifest.json
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port11a_manifest.json
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)

$ git ls-files --with-tree=origin/main -- tests/fixtures/port11a_trusted_scopes.json
tests/fixtures/port11a_trusted_scopes.json
$ git show origin/main:tests/fixtures/port11a_trusted_scopes.json | head -1
{
$ git ls-files -- tests/fixtures/port11a_trusted_scopes.json
tests/fixtures/port11a_trusted_scopes.json
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/fixtures/port11a_trusted_scopes.json
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)

$ git ls-files --with-tree=origin/main -- docs/PORT11C_EVIDENCE_HARNESS.md
docs/PORT11C_EVIDENCE_HARNESS.md
$ git show origin/main:docs/PORT11C_EVIDENCE_HARNESS.md | head -1
# PORT-11C — Offline Evidence Validation Harness
$ git ls-files -- docs/PORT11C_EVIDENCE_HARNESS.md
docs/PORT11C_EVIDENCE_HARNESS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT11C_EVIDENCE_HARNESS.md
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)
```

---

### 2.11 `PORT-12A`, `PORT-12B`, `PORT-12C` — Unmerged Remote Branches Referenced in `PORT-13-OFFLINE`

- **Doc Mentions**: `docs/PROJECT_STATE.md:562, 565, 573`; `docs/HANDOFF.md:2031, 2034, 2041` (referenced as unmerged Draft PRs `#23` `origin/research/port12a-memory-ownership` @ `3e1e369`, `#24` `origin/research/port12b-filesystem-u2` @ `6fb7622`, and `#25` `origin/research/port12c-spytask-u4` @ `de792bd`) `[VERIFIED]`.
- **Milestone Summary Claim**: `docs/PROJECT_STATE.md` and `docs/HANDOFF.md` explicitly state that Draft PRs `#23`–`#25` remain unmerged (`docs/PROJECT_STATE.md:562, 573`; `docs/HANDOFF.md:2031, 2041`); all 6 files on those remote branches (`3e1e369`, `6fb7622`, `de792bd`) are absent from both `origin/main` and the worktree base (`HEAD`), with status **`ABSENT`** `[VERIFIED]`.

| Branch File (`3e1e369` / `6fb7622` / `de792bd`) | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md` *(on `origin/research/port12a-memory-ownership` `3e1e369`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |
| `tests/test_port12a_memory_ownership.py` *(on `origin/research/port12a-memory-ownership` `3e1e369`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |
| `docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md` *(on `origin/research/port12b-filesystem-u2` `6fb7622`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |
| `tests/test_port12b_filesystem_u2.py` *(on `origin/research/port12b-filesystem-u2` `6fb7622`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |
| `docs/PORT12C_SPYTASK_U4_CONTRACT.md` *(on `origin/research/port12c-spytask-u4` `de792bd`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |
| `tests/test_port12c_spytask_u4.py` *(on `origin/research/port12c-spytask-u4` `de792bd`)* | `docs/PROJECT_STATE.md:565`; `docs/HANDOFF.md:2034` *(via branch ref)* | `none` | `ABSENT` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-12A` / `PORT-12B` / `PORT-12C`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md
$ git show origin/main:docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md 2>&1 | head -1
fatal: path 'docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md' does not exist in 'origin/main'
$ git ls-files -- docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md
none

$ git ls-files --with-tree=origin/main -- tests/test_port12a_memory_ownership.py
$ git show origin/main:tests/test_port12a_memory_ownership.py 2>&1 | head -1
fatal: path 'tests/test_port12a_memory_ownership.py' does not exist in 'origin/main'
$ git ls-files -- tests/test_port12a_memory_ownership.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port12a_memory_ownership.py
none

$ git ls-files --with-tree=origin/main -- docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md
$ git show origin/main:docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md 2>&1 | head -1
fatal: path 'docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md' does not exist in 'origin/main'
$ git ls-files -- docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md
none

$ git ls-files --with-tree=origin/main -- tests/test_port12b_filesystem_u2.py
$ git show origin/main:tests/test_port12b_filesystem_u2.py 2>&1 | head -1
fatal: path 'tests/test_port12b_filesystem_u2.py' does not exist in 'origin/main'
$ git ls-files -- tests/test_port12b_filesystem_u2.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port12b_filesystem_u2.py
none

$ git ls-files --with-tree=origin/main -- docs/PORT12C_SPYTASK_U4_CONTRACT.md
$ git show origin/main:docs/PORT12C_SPYTASK_U4_CONTRACT.md 2>&1 | head -1
fatal: path 'docs/PORT12C_SPYTASK_U4_CONTRACT.md' does not exist in 'origin/main'
$ git ls-files -- docs/PORT12C_SPYTASK_U4_CONTRACT.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT12C_SPYTASK_U4_CONTRACT.md
none

$ git ls-files --with-tree=origin/main -- tests/test_port12c_spytask_u4.py
$ git show origin/main:tests/test_port12c_spytask_u4.py 2>&1 | head -1
fatal: path 'tests/test_port12c_spytask_u4.py' does not exist in 'origin/main'
$ git ls-files -- tests/test_port12c_spytask_u4.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port12c_spytask_u4.py
none
```

---

### 2.12 `PORT-13-OFFLINE` — Read-Only Reviews of Draft PRs #23–#25, Fail-Closed Proof Obligations & Next Questions

- **Doc Mentions**: `docs/PROJECT_STATE.md:559-569`; `docs/HANDOFF.md:2028-2036` `[VERIFIED]`.
- **Milestone Summary Claim**: All 14 deliverables (10 primary + 4 companion) claimed for `PORT-13-OFFLINE` in `docs/PROJECT_STATE.md:563-567` and `docs/HANDOFF.md:2032-2036` are present at the worktree base (`HEAD` = `db115c6dd3f7ad69fbd839447df8a3ff68f79822`) and absent from `origin/main` (`581b1a4bb30456bf18c46dc4bcf61b0375aee251`), with status **`PRESENT_ONLY_ON_BRANCH`** and `origin/main` add commit `none` `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/PORT13_NEXT_QUESTIONS.md` | `docs/PROJECT_STATE.md:564, 568, 581`; `docs/HANDOFF.md:2033, 2049` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_REVIEW_PR23.md` | `docs/PROJECT_STATE.md:562, 565, 582`; `docs/HANDOFF.md:2031, 2034, 2050` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_REVIEW_U2.md` | `docs/PROJECT_STATE.md:562, 565`; `docs/HANDOFF.md:2031, 2034` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_REVIEW_U4.md` | `docs/PROJECT_STATE.md:562, 565`; `docs/HANDOFF.md:2031, 2034` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tools/port13_memory_obligations.py` | `docs/PROJECT_STATE.md:566, 577, 578, 582`; `docs/HANDOFF.md:2035, 2045, 2046, 2050` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tests/test_port13_memory_obligations.py` | `docs/PROJECT_STATE.md:566, 578`; `docs/HANDOFF.md:2035, 2046` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tools/port13_u2_obligations.py` | `docs/PROJECT_STATE.md:566`; `docs/HANDOFF.md:2035` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tests/test_port13_u2_obligations.py` | `docs/PROJECT_STATE.md:566`; `docs/HANDOFF.md:2035` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tools/port13_oblig_u4.py` | `docs/PROJECT_STATE.md:566, 576, 578, 581`; `docs/HANDOFF.md:2035, 2044, 2046, 2049` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tests/test_port13_oblig_u4.py` | `docs/PROJECT_STATE.md:566`; `docs/HANDOFF.md:2035` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_MEMORY_OBLIGATIONS.md` | `docs/PROJECT_STATE.md:567`; `docs/HANDOFF.md:2036` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_U2_OBLIGATIONS.md` | `docs/PROJECT_STATE.md:567`; `docs/HANDOFF.md:2036` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT13_OBLIG_U4.md` | `docs/PROJECT_STATE.md:567`; `docs/HANDOFF.md:2036` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/agentbridge/PORT13_BASELINE.md` | `docs/PROJECT_STATE.md:567`; `docs/HANDOFF.md:2036` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-13-OFFLINE`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT13_NEXT_QUESTIONS.md
docs/PORT13_NEXT_QUESTIONS.md
$ git show origin/main:docs/PORT13_NEXT_QUESTIONS.md 2>&1 | head -1
fatal: path 'docs/PORT13_NEXT_QUESTIONS.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_NEXT_QUESTIONS.md
docs/PORT13_NEXT_QUESTIONS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_NEXT_QUESTIONS.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_REVIEW_PR23.md
docs/PORT13_REVIEW_PR23.md
$ git show origin/main:docs/PORT13_REVIEW_PR23.md 2>&1 | head -1
fatal: path 'docs/PORT13_REVIEW_PR23.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_REVIEW_PR23.md
docs/PORT13_REVIEW_PR23.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_REVIEW_PR23.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_REVIEW_U2.md
docs/PORT13_REVIEW_U2.md
$ git show origin/main:docs/PORT13_REVIEW_U2.md 2>&1 | head -1
fatal: path 'docs/PORT13_REVIEW_U2.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_REVIEW_U2.md
docs/PORT13_REVIEW_U2.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_REVIEW_U2.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_REVIEW_U4.md
docs/PORT13_REVIEW_U4.md
$ git show origin/main:docs/PORT13_REVIEW_U4.md 2>&1 | head -1
fatal: path 'docs/PORT13_REVIEW_U4.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_REVIEW_U4.md
docs/PORT13_REVIEW_U4.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_REVIEW_U4.md
none

$ git ls-files --with-tree=origin/main -- tools/port13_memory_obligations.py
tools/port13_memory_obligations.py
$ git show origin/main:tools/port13_memory_obligations.py 2>&1 | head -1
fatal: path 'tools/port13_memory_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tools/port13_memory_obligations.py
tools/port13_memory_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port13_memory_obligations.py
none

$ git ls-files --with-tree=origin/main -- tests/test_port13_memory_obligations.py
tests/test_port13_memory_obligations.py
$ git show origin/main:tests/test_port13_memory_obligations.py 2>&1 | head -1
fatal: path 'tests/test_port13_memory_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tests/test_port13_memory_obligations.py
tests/test_port13_memory_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port13_memory_obligations.py
none

$ git ls-files --with-tree=origin/main -- tools/port13_u2_obligations.py
tools/port13_u2_obligations.py
$ git show origin/main:tools/port13_u2_obligations.py 2>&1 | head -1
fatal: path 'tools/port13_u2_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tools/port13_u2_obligations.py
tools/port13_u2_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port13_u2_obligations.py
none

$ git ls-files --with-tree=origin/main -- tests/test_port13_u2_obligations.py
tests/test_port13_u2_obligations.py
$ git show origin/main:tests/test_port13_u2_obligations.py 2>&1 | head -1
fatal: path 'tests/test_port13_u2_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tests/test_port13_u2_obligations.py
tests/test_port13_u2_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port13_u2_obligations.py
none

$ git ls-files --with-tree=origin/main -- tools/port13_oblig_u4.py
tools/port13_oblig_u4.py
$ git show origin/main:tools/port13_oblig_u4.py 2>&1 | head -1
fatal: path 'tools/port13_oblig_u4.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tools/port13_oblig_u4.py
tools/port13_oblig_u4.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port13_oblig_u4.py
none

$ git ls-files --with-tree=origin/main -- tests/test_port13_oblig_u4.py
tests/test_port13_oblig_u4.py
$ git show origin/main:tests/test_port13_oblig_u4.py 2>&1 | head -1
fatal: path 'tests/test_port13_oblig_u4.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tests/test_port13_oblig_u4.py
tests/test_port13_oblig_u4.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port13_oblig_u4.py
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_MEMORY_OBLIGATIONS.md
docs/PORT13_MEMORY_OBLIGATIONS.md
$ git show origin/main:docs/PORT13_MEMORY_OBLIGATIONS.md 2>&1 | head -1
fatal: path 'docs/PORT13_MEMORY_OBLIGATIONS.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_MEMORY_OBLIGATIONS.md
docs/PORT13_MEMORY_OBLIGATIONS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_MEMORY_OBLIGATIONS.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_U2_OBLIGATIONS.md
docs/PORT13_U2_OBLIGATIONS.md
$ git show origin/main:docs/PORT13_U2_OBLIGATIONS.md 2>&1 | head -1
fatal: path 'docs/PORT13_U2_OBLIGATIONS.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_U2_OBLIGATIONS.md
docs/PORT13_U2_OBLIGATIONS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_U2_OBLIGATIONS.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT13_OBLIG_U4.md
docs/PORT13_OBLIG_U4.md
$ git show origin/main:docs/PORT13_OBLIG_U4.md 2>&1 | head -1
fatal: path 'docs/PORT13_OBLIG_U4.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT13_OBLIG_U4.md
docs/PORT13_OBLIG_U4.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT13_OBLIG_U4.md
none

$ git ls-files --with-tree=origin/main -- docs/agentbridge/PORT13_BASELINE.md
docs/agentbridge/PORT13_BASELINE.md
$ git show origin/main:docs/agentbridge/PORT13_BASELINE.md 2>&1 | head -1
fatal: path 'docs/agentbridge/PORT13_BASELINE.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/agentbridge/PORT13_BASELINE.md
docs/agentbridge/PORT13_BASELINE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/agentbridge/PORT13_BASELINE.md
none
```

---

### 2.13 `PORT-14-OFFLINE` — Tracked-Artifact Evaluation of `OBLIG-U4-08` & `OBLIG-MEM-03` and State Synchronization

- **Doc Mentions**: `docs/PROJECT_STATE.md:570-583`; `docs/HANDOFF.md:2038-2050` `[VERIFIED]`.
- **Milestone Summary Claim**:
  - The 3 new documentation deliverables created in `PORT-14-OFFLINE` (`docs/agentbridge/PORT14_BASE.md`, `docs/PORT14_Q_U4_08.md`, `docs/PORT14_Q_MEM03_BSS.md`) and the 2 modified `PORT-13-OFFLINE` files (`tools/port13_memory_obligations.py`, `tests/test_port13_memory_obligations.py`) are present at the worktree base (`HEAD`) and absent from `origin/main`, with status **`PRESENT_ONLY_ON_BRANCH`** and `origin/main` add commit `none` `[VERIFIED]`.
  - The 2 repository-wide state files modified in `PORT-14-OFFLINE` (`docs/PROJECT_STATE.md` and `docs/HANDOFF.md`) exist as file paths on `origin/main` (**`MERGED`** as paths, first added in `ec971142db1f3d99f30cee1e13a15466ccd740f6`), while the `PORT-14-OFFLINE` edits (`5c92cbc768266ad4a859b220d736d71cc0672052` / `db115c6dd3f7ad69fbd839447df8a3ff68f79822`) exist only on the branch (`origin/main..HEAD`) `[VERIFIED]`.

| Claimed Deliverable File | Doc Citations (`file:line`) | First Add Commit on `origin/main` (`--diff-filter=A`) | Status | Label |
|---|---|---|---|---|
| `docs/agentbridge/PORT14_BASE.md` | `docs/PROJECT_STATE.md:561, 563, 572, 575`; `docs/HANDOFF.md:2030, 2032, 2040, 2043` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT14_Q_U4_08.md` | `docs/PROJECT_STATE.md:572, 573, 576, 581`; `docs/HANDOFF.md:2040, 2041, 2044, 2049` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PORT14_Q_MEM03_BSS.md` | `docs/PROJECT_STATE.md:572, 573, 577, 578, 582`; `docs/HANDOFF.md:2040, 2041, 2045, 2046, 2050` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tools/port13_memory_obligations.py` | `docs/PROJECT_STATE.md:578`; `docs/HANDOFF.md:2046` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `tests/test_port13_memory_obligations.py` | `docs/PROJECT_STATE.md:578`; `docs/HANDOFF.md:2046` | `none` | `PRESENT_ONLY_ON_BRANCH` | `VERIFIED` |
| `docs/PROJECT_STATE.md` | `docs/PROJECT_STATE.md:578, 579`; `docs/HANDOFF.md:2046, 2047` | `ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite` *(path is `MERGED` on `origin/main`; `PORT-14-OFFLINE` synchronization commit `5c92cbc768266ad4a859b220d736d71cc0672052` is on `HEAD` branch only)* | `MERGED` | `VERIFIED` |
| `docs/HANDOFF.md` | `docs/PROJECT_STATE.md:578, 579`; `docs/HANDOFF.md:2046, 2047` | `ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite` *(path is `MERGED` on `origin/main`; `PORT-14-OFFLINE` synchronization commit `5c92cbc768266ad4a859b220d736d71cc0672052` is on `HEAD` branch only)* | `MERGED` | `VERIFIED` |

#### Verbatim Git Evidence (`PORT-14-OFFLINE`)

```text
$ git ls-files --with-tree=origin/main -- docs/agentbridge/PORT14_BASE.md
docs/agentbridge/PORT14_BASE.md
$ git show origin/main:docs/agentbridge/PORT14_BASE.md 2>&1 | head -1
fatal: path 'docs/agentbridge/PORT14_BASE.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/agentbridge/PORT14_BASE.md
docs/agentbridge/PORT14_BASE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/agentbridge/PORT14_BASE.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT14_Q_U4_08.md
docs/PORT14_Q_U4_08.md
$ git show origin/main:docs/PORT14_Q_U4_08.md 2>&1 | head -1
fatal: path 'docs/PORT14_Q_U4_08.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT14_Q_U4_08.md
docs/PORT14_Q_U4_08.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT14_Q_U4_08.md
none

$ git ls-files --with-tree=origin/main -- docs/PORT14_Q_MEM03_BSS.md
docs/PORT14_Q_MEM03_BSS.md
$ git show origin/main:docs/PORT14_Q_MEM03_BSS.md 2>&1 | head -1
fatal: path 'docs/PORT14_Q_MEM03_BSS.md' exists on disk, but not in 'origin/main'
$ git ls-files -- docs/PORT14_Q_MEM03_BSS.md
docs/PORT14_Q_MEM03_BSS.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT14_Q_MEM03_BSS.md
none

$ git ls-files --with-tree=origin/main -- tools/port13_memory_obligations.py
tools/port13_memory_obligations.py
$ git show origin/main:tools/port13_memory_obligations.py 2>&1 | head -1
fatal: path 'tools/port13_memory_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tools/port13_memory_obligations.py
tools/port13_memory_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port13_memory_obligations.py
none

$ git ls-files --with-tree=origin/main -- tests/test_port13_memory_obligations.py
tests/test_port13_memory_obligations.py
$ git show origin/main:tests/test_port13_memory_obligations.py 2>&1 | head -1
fatal: path 'tests/test_port13_memory_obligations.py' exists on disk, but not in 'origin/main'
$ git ls-files -- tests/test_port13_memory_obligations.py
tests/test_port13_memory_obligations.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port13_memory_obligations.py
none

$ git ls-files --with-tree=origin/main -- docs/PROJECT_STATE.md
docs/PROJECT_STATE.md
$ git show origin/main:docs/PROJECT_STATE.md | head -1
# Project state
$ git ls-files -- docs/PROJECT_STATE.md
docs/PROJECT_STATE.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PROJECT_STATE.md
ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite

$ git ls-files --with-tree=origin/main -- docs/HANDOFF.md
docs/HANDOFF.md
$ git show origin/main:docs/HANDOFF.md | head -1
# Agent handoff
$ git ls-files -- docs/HANDOFF.md
docs/HANDOFF.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/HANDOFF.md
ec971142db1f3d99f30cee1e13a15466ccd740f6 chore: initialize G3X Lite
```

---

## 3. Dedicated `PORT-9B` Verification (`4206ec5` & Three `PORT-9B` Files)

- **Claim 3.1 (Existence of Three `PORT-9B` Files)**: `docs/PORT9B_RUNTIME_CONTRACT.md`, `tools/port9b_runtime_contract.py`, and `tests/test_port9b_runtime_contract.py` all exist at `origin/main` (`581b1a4bb30456bf18c46dc4bcf61b0375aee251`) and at the worktree base (`HEAD` = `db115c6dd3f7ad69fbd839447df8a3ff68f79822`), and all three have status **`MERGED`** `[VERIFIED]`.
- **Claim 3.2 (Existence of Commit `4206ec5`)**: Commit `4206ec5` (`4206ec573c951ebd460d2041ed081c39f11aa020`, `PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)`) exists in the repository and is the commit that first added all three `PORT-9B` files to `origin/main` `[VERIFIED]`.
- **Claim 3.3 (`origin/main` Containment of `4206ec5`)**: `git merge-base --is-ancestor 4206ec5 origin/main` exits with code **`0`**, proving that `origin/main` contains commit `4206ec5` `[VERIFIED]`.
- **Claim 3.4 (Resolution of `PROJECT_STATE.md` / `HANDOFF.md` Self-Contradiction)**: `docs/PROJECT_STATE.md:32, 487-488` and `docs/HANDOFF.md:44, 60-62` accurately record `PORT-9B` as merged on `origin/main` (`4206ec5`, PR #11), whereas `docs/PROJECT_STATE.md:562, 573` and `docs/HANDOFF.md:2031, 2041` erroneously state `"and PORT-9B is not started"` — a claim contradicted by `git show -s 4206ec5` and `git merge-base --is-ancestor 4206ec5 origin/main` (exit code `0`) `[VERIFIED]`.

### Verbatim Command Output (`PORT-9B`)

```text
$ git ls-files --with-tree=origin/main -- docs/PORT9B_RUNTIME_CONTRACT.md
docs/PORT9B_RUNTIME_CONTRACT.md
$ git show origin/main:docs/PORT9B_RUNTIME_CONTRACT.md | head -1
# PORT-9B — Runtime integration contract (PORT-8A sources ↔ PORT-9A model)
$ git ls-files -- docs/PORT9B_RUNTIME_CONTRACT.md
docs/PORT9B_RUNTIME_CONTRACT.md
$ git log origin/main --diff-filter=A --format='%H %s' -- docs/PORT9B_RUNTIME_CONTRACT.md
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)

$ git ls-files --with-tree=origin/main -- tools/port9b_runtime_contract.py
tools/port9b_runtime_contract.py
$ git show origin/main:tools/port9b_runtime_contract.py | head -1
#!/usr/bin/env python3
$ git ls-files -- tools/port9b_runtime_contract.py
tools/port9b_runtime_contract.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tools/port9b_runtime_contract.py
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)

$ git ls-files --with-tree=origin/main -- tests/test_port9b_runtime_contract.py
tests/test_port9b_runtime_contract.py
$ git show origin/main:tests/test_port9b_runtime_contract.py | head -1
"""PORT-9B: tests for tools/port9b_runtime_contract.py.
$ git ls-files -- tests/test_port9b_runtime_contract.py
tests/test_port9b_runtime_contract.py
$ git log origin/main --diff-filter=A --format='%H %s' -- tests/test_port9b_runtime_contract.py
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)

$ git show -s 4206ec5
commit 4206ec573c951ebd460d2041ed081c39f11aa020
Author: PHAM VAN AN <125888490+s4urj3ng@users.noreply.github.com>
Date:   Wed Oct 28 00:39:03 2026 +0900

    PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)
    
    * feat(port9b): offline integration contract for PORT-8A sources and PORT-9A model
    
    Adds tools/port9b_runtime_contract.py, a standard-library validator, and 42
    tests. The validator reads the five PORT-8A platform sources (integrity checked
    through bootstrap_chdk_platform.build_expected / classify) and the tracked
    boot_prototype.c, then checks:
    C1 sources present and at final hash; C2 platform/DryOS config, ALT options
    inside KEYS_MASK0, Power excluded; C3 no runtime interface (CreateTask hook,
    mykbd_task, readiness signal, SpyTask creation) active in source beyond what
    the PORT-9A model allows; C4 non-default preconditions refused unless
    explicitly allowed, then labelled HYPOTHETICAL; C5 an address-free registry of
    unverified runtime facts (U1-U4) covering every PORT-9A precondition flag.
    
    It never writes. Without --target it rebuilds sources in memory; with --target
    it only reads. PORT-8A and PORT-9A code unchanged.
    
    Evidence: VERIFIED (source) that the current GM1.10C sources activate no
    interface and match PORT-9A GM110C_PRECONDITIONS; firmware runtime facts U1-U4
    remain UNKNOWN. No GM1.10E value or new firmware address introduced. Seven
    hand mutations of the validator all killed. Hardware: STRICT NO-GO.
    
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    
    * docs(port9b): runtime integration contract report
    
    Records the C1-C5 contract, clean-clone results (commit 2219f79: 9B 42 OK
    before bootstrap; 7A/7B/7C/8A/9A/9B 18/19/23/34/32/42 OK after), the seven
    killed mutations and the unresolved requirements U1-U4 (UNKNOWN, no addresses).
    Notes PROJECT_STATE.md/HANDOFF.md are stale (2026-10-25, no PORT-8A/9A) and
    were deliberately not modified. Hardware: STRICT NO-GO.
    
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    
    * fix(port9b): remediate B1/B2/N1 review findings in runtime contract
    
    - B1: broaden SpyTask activation marker detection across inline asm
      (instruction width suffixes .w/.n, multiple ;/\n-separated statements,
      labels, literal pool/symbol references) and active C calls outside dormant
      prototype wrapper definitions; reword C3 findings to 'recognized activation
      markers absent' and explicitly document regex source-scanning limits.
    - B2: pin SHA-256 of tracked platform/g3x/sub/110c/boot_prototype.c
      (f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68),
      check all path components for symlinks, enforce C1.prototype_sha256,
      correct source-loading description, and add regression tests for
      StartDiskboot (bl sub_fc05bbea) and BSS-bound (0x00400000) mutations.
    - N1: derive C4.model_trace label and C4.defaults_inert emission from
      effective preconditions rather than refused input; add regression test.
    
    Evidence: VERIFIED_SOURCE via 51/51 PORT-9B unit tests and 7A/7B/7C/8A/9A/9B
    regression suites on clean clone. Firmware runtime facts U1-U4 remain
    UNVERIFIED_RUNTIME. Hardware remains STRICT NO-GO.
    
    ---------
    
    Co-authored-by: avp <avp@mac-buc.local>
    Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>

$ git merge-base --is-ancestor 4206ec5 origin/main
exit_code: 0
```

---

## 4. Pull Request Ledger (`#11`, `#12`, `#17`, `#19`, `#23`–`#25`)

- **Claim 4.1 (`--merges` Commits on `origin/main`)**: `git log origin/main --merges --grep="#<N>"` returns **empty (none)** for all seven PRs (`#11`, `#12`, `#17`, `#19`, `#23`, `#24`, `#25`) because `origin/main` has no 2-parent merge commits matching those PR numbers `[VERIFIED]`.
- **Claim 4.2 (Non-Merge / Squash Commits on `origin/main` Mentioning `(#<N>)`)**: `git log origin/main --format='%H %s' --grep="(#<N>)"` shows single-parent commits on `origin/main` whose subjects reference `#11` (`4206ec573c951ebd460d2041ed081c39f11aa020`), `#12` (`cbe74cf53097386139410da00cdb6c277d40a1a0`), `#17` (`a028ef981542eeaddd3a317d9cdb8e908601724e`), and `#19` (`581b1a4bb30456bf18c46dc4bcf61b0375aee251`), and **none** for `#23`, `#24`, `#25` `[VERIFIED]`.
- **Claim 4.3 (Remote Branch Heads via `git branch -r` and `git rev-parse`)**: All seven associated remote-tracking branches still exist in `git branch -r` (`origin/feat/port9b-runtime-contracts`, `origin/docs/port9c-milestone-sync`, `origin/research/port11c-evidence-harness`, `origin/research/historical-symbol-reconciliation`, `origin/research/port12a-memory-ownership`, `origin/research/port12b-filesystem-u2`, `origin/research/port12c-spytask-u4`), and none of those branch tip commits is a 2-parent ancestor of `origin/main` (`git merge-base --is-ancestor <branch> origin/main` exits `1` for each) `[VERIFIED]`.
- **Claim 4.4 (GitHub UI Open/Closed/Merged State)**: Git alone does not store GitHub pull-request metadata (`refs/pull/*` or GitHub API state); therefore, the GitHub open/closed/merged state for every PR is labelled **`UNKNOWN`** `[UNKNOWN]`.

| PR | `git log origin/main --merges --grep="#<N>"` (2-parent merge commits) | `git log origin/main --format='%H %s' --grep="(#<N>)"` (all commits on `origin/main`) | Remote Branch in `git branch -r` & Head SHA (`git rev-parse`) | Remote Branch Tip Subject (`git log -1`) | GitHub PR State (open / closed / merged) | Evidence Labels |
|---|---|---|---|---|---|---|
| **#11** | `none` `[VERIFIED]` | `4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)` `[VERIFIED]` | `origin/feat/port9b-runtime-contracts` @ `c127c4cf5d919676daefeca16d251095ea79f8b2` `[VERIFIED]` | `fix(port9b): remediate B1/B2/N1 review findings in runtime contract` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; squash-style commit `4206ec5` with `(#11)` in subject is on `origin/main`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#12** | `none` `[VERIFIED]` | `cbe74cf53097386139410da00cdb6c277d40a1a0 PORT-9C: milestone consolidation in PROJECT_STATE and HANDOFF (PRs #6–#11) (#12)` `[VERIFIED]` | `origin/docs/port9c-milestone-sync` @ `eff5d539eb0a1f15378226c980b77cbc7b7113f6` `[VERIFIED]` | `docs(port9c): change status to DRAFT_PR_OPEN / PENDING_MERGE per review` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; squash-style commit `cbe74cf` with `(#12)` in subject is on `origin/main`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#17** | `none` `[VERIFIED]` | `a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)` `[VERIFIED]` | `origin/research/port11c-evidence-harness` @ `791be0a1dbb3abe9beac60ea3fa16ef253bf4b88` `[VERIFIED]` | `fix(port11c): address Tech Lead review on trust boundaries and baseline` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; squash-style commit `a028ef9` with `(#17)` in subject is on `origin/main`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#19** | `none` `[VERIFIED]` | `581b1a4bb30456bf18c46dc4bcf61b0375aee251 docs(historical): reconcile G7/G8 symbols and three-version comparison (#19)` `[VERIFIED]` | `origin/research/historical-symbol-reconciliation` @ `50c7c807f4a9a4d08b1d58cb6c9729a348e7ef72` `[VERIFIED]` | `docs(historical): normalize hex addresses, correct ATCM span, and verify GetKbdState evidence` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; squash-style commit `581b1a4` with `(#19)` in subject is on `origin/main`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#23** | `none` `[VERIFIED]` | `none` `[VERIFIED]` | `origin/research/port12a-memory-ownership` @ `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4` `[VERIFIED]` *(branch association cited in `docs/PROJECT_STATE.md:565`)* | `docs(port12a): memory ownership matrix, headroom arithmetic, and non-overlap tests (#20)` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; no commit on `origin/main` mentions `#23`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#24** | `none` `[VERIFIED]` | `none` `[VERIFIED]` | `origin/research/port12b-filesystem-u2` @ `6fb7622aee7915ff2d3d39563a45ef3310ae31b3` `[VERIFIED]` *(branch association cited in `docs/PROJECT_STATE.md:565`)* | `docs(port12b): U2 filesystem readiness proof obligations and negative tests (#21)` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; no commit on `origin/main` mentions `#24`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |
| **#25** | `none` `[VERIFIED]` | `none` `[VERIFIED]` | `origin/research/port12c-spytask-u4` @ `de792bd73b643e778dea3f3a80c53c8f2fdb0ead` `[VERIFIED]` *(branch association cited in `docs/PROJECT_STATE.md:565`)* | `docs(port12c): U4 SpyTask scheduling contract and gating failure traces (#22)` `[VERIFIED]` | `UNKNOWN` (git cannot show GitHub PR state; no commit on `origin/main` mentions `#25`) | Git facts: `VERIFIED`; GitHub PR state: `UNKNOWN` |

### Verbatim Command Output (`git log --merges --grep`, `git log --grep`, and `git branch -r`)

```text
$ git log origin/main --merges --format='%H %s' --grep='#11'
$ git log origin/main --merges --format='%H %s' --grep='#12'
$ git log origin/main --merges --format='%H %s' --grep='#17'
$ git log origin/main --merges --format='%H %s' --grep='#19'
$ git log origin/main --merges --format='%H %s' --grep='#23'
$ git log origin/main --merges --format='%H %s' --grep='#24'
$ git log origin/main --merges --format='%H %s' --grep='#25'

$ git log origin/main --format='%H %s' --grep='(#11)'
4206ec573c951ebd460d2041ed081c39f11aa020 PORT-9B: offline runtime integration contract (PORT-8A sources ↔ PORT-9A model) (#11)
$ git log origin/main --format='%H %s' --grep='(#12)'
cbe74cf53097386139410da00cdb6c277d40a1a0 PORT-9C: milestone consolidation in PROJECT_STATE and HANDOFF (PRs #6–#11) (#12)
$ git log origin/main --format='%H %s' --grep='(#17)'
a028ef981542eeaddd3a317d9cdb8e908601724e feat(port11c): offline evidence harness, manifest validator, and trust boundary audit (#17)
$ git log origin/main --format='%H %s' --grep='(#19)'
581b1a4bb30456bf18c46dc4bcf61b0375aee251 docs(historical): reconcile G7/G8 symbols and three-version comparison (#19)
$ git log origin/main --format='%H %s' --grep='(#23)'
$ git log origin/main --format='%H %s' --grep='(#24)'
$ git log origin/main --format='%H %s' --grep='(#25)'

$ git branch -r
  origin/HEAD -> origin/main
  origin/agentbridge/g3x-lite/port-13-offline/integration
  origin/agentbridge/g3x-lite/port-13-offline/p13-next-questions-r3
  origin/agentbridge/g3x-lite/port-14-offline/integration
  origin/agentbridge/g3x-lite/port-14-offline/p14-base
  origin/agentbridge/g3x-lite/port-14-offline/p14-oblig-update
  origin/agentbridge/g3x-lite/port-14-offline/p14-q-mem03
  origin/agentbridge/g3x-lite/port-14-offline/p14-q-u4-08
  origin/agentbridge/g3x-lite/port-14-offline/p14-state-sync-r2
  origin/docs/agentbridge-mode
  origin/docs/g10-uart-hardware-correction
  origin/docs/port3-restart-readiness-audit
  origin/docs/port4-documentation-consolidation
  origin/docs/port9c-milestone-sync
  origin/feat/dynamic-witness-address
  origin/feat/port7c-platform-validation
  origin/feat/port8a-platform-bootstrap
  origin/feat/port9a-runtime-integration
  origin/feat/port9b-runtime-contracts
  origin/feat/restart-sd1stinit-prototype
  origin/fix/port10b-keyboard-switch-indices
  origin/fix/port5e-early-boot-literals
  origin/fix/port7b-playback-mask
  origin/main
  origin/research/g9-ranma-source-archaeology
  origin/research/historical-symbol-reconciliation
  origin/research/port10a-runtime-preconditions
  origin/research/port11a-gm110c-rom-evidence
  origin/research/port11b-runtime-safety-model
  origin/research/port11c-evidence-harness
  origin/research/port12a-memory-ownership
  origin/research/port12b-filesystem-u2
  origin/research/port12c-spytask-u4
  origin/test/port11b-adversarial-qa

$ git log -1 --format='%H %s' origin/feat/port9b-runtime-contracts
c127c4cf5d919676daefeca16d251095ea79f8b2 fix(port9b): remediate B1/B2/N1 review findings in runtime contract
$ git log -1 --format='%H %s' origin/docs/port9c-milestone-sync
eff5d539eb0a1f15378226c980b77cbc7b7113f6 docs(port9c): change status to DRAFT_PR_OPEN / PENDING_MERGE per review
$ git log -1 --format='%H %s' origin/research/port11c-evidence-harness
791be0a1dbb3abe9beac60ea3fa16ef253bf4b88 fix(port11c): address Tech Lead review on trust boundaries and baseline
$ git log -1 --format='%H %s' origin/research/historical-symbol-reconciliation
50c7c807f4a9a4d08b1d58cb6c9729a348e7ef72 docs(historical): normalize hex addresses, correct ATCM span, and verify GetKbdState evidence
$ git log -1 --format='%H %s' origin/research/port12a-memory-ownership
3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4 docs(port12a): memory ownership matrix, headroom arithmetic, and non-overlap tests (#20)
$ git log -1 --format='%H %s' origin/research/port12b-filesystem-u2
6fb7622aee7915ff2d3d39563a45ef3310ae31b3 docs(port12b): U2 filesystem readiness proof obligations and negative tests (#21)
$ git log -1 --format='%H %s' origin/research/port12c-spytask-u4
de792bd73b643e778dea3f3a80c53c8f2fdb0ead docs(port12c): U4 SpyTask scheduling contract and gating failure traces (#22)
```

---

## Static test counts (p15-test-count)
