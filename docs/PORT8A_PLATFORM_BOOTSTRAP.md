# PORT-8A — Reproducible G3 X platform source bootstrap

Local date: **2026-10-26**. Author: Claude (repository architecture / reproducibility) under ChatGPT Tech Lead.

**Status:**
- **PR:** Draft [PR #7](https://github.com/s4urj3ng/g3x-lite/pull/7) on branch `feat/port8a-platform-bootstrap`. It is stacked on PORT-7B, Draft [PR #6](https://github.com/s4urj3ng/g3x-lite/pull/6) on branch `fix/port7b-playback-mask`.
- **History:** first committed as `8c5f1a2`, then rebased to `5a08a92` onto `42cf957`, the PR #6 docs fix that makes the manual patch command forward-only. The Tech Lead review of `5a08a92` was addressed in the follow-up commit (§5.1). The PR page shows the current head.
- **Not merged.**

**Result:**
- **Baseline:** a tracked, hash-pinned baseline of the five GM1.10C platform sources that PORT-7A and PORT-7C read.
- **Bootstrap:** a deterministic, fail-closed tool that recreates those sources in `chdk-port/`, applying PORT-7B patch 0002 on the way.
- **Tests:** a regression suite that runs on a clean clone.

On a fresh temporary clone, after bootstrap, PORT-7A, PORT-7B, PORT-7C and PORT-8A all pass. No firmware behavior, boot/loader code, `.gitignore`, mask value or protected artifact was changed. **Hardware: STRICT NO-GO.**

Labels: **VERIFIED** = checked here against recorded evidence or by execution; **INFERRED** = reasoned but not directly recorded; **UNKNOWN** = not established.

## 1. Problem (VERIFIED)

- **The tree is ignored:** `.gitignore` L39–50 ignores everything under `chdk-port/` except three tracked prototype files in `platform/g3x/sub/110c/`.
- **Upstream has no G3 X platform:** `chdk-port/.git_upstream` is CHDK r5491, commit `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`. There, `ls-tree 21b9a14 platform/g3x` is empty, and upstream status shows `?? platform/g3x/`. The G3 X platform tree was written locally in CHDK-PORT-0. No upstream checkout or bootstrap can produce it.
- **Consequence:** on a clean clone (`b6c74e6`), PORT-7A gives `FAILED (errors=1)` and PORT-7C gives `FAILED (errors=4)`, both from missing sources, before bootstrap.

## 2. Source inventory of `chdk-port/platform/g3x` (local workspace)

| Group | Files | Disposition |
|---|---|---|
| Camera-level sources read by PORT-7A/7C | `kbd.c`, `lib.c`, `platform_camera.h`, `platform_kbd.h`, `shooting.c` | **Vendored** (§3) |
| Other camera-level build sources | `Makefile`, `makefile.inc`, `main.c`, `wrappers.c` | Not vendored: no test reads them. `makefile.inc` changed after the PORT-0C freeze; its current hash `7b6969f2…` is the one recorded by PORT-0E. |
| `sub/110c` boot, hook and stub sources | `boot.c`, `capt_seq.c`, `filewrite.c`, `movie_rec.c`, `bin_compat.h`, `stubs_auto.S`, `stubs_min.S`, `stubs_entry_2.S`, `Makefile`, `makefile.inc` | Not vendored: these are boot/task-hook code and firmware-specific stub tables, outside this task's scope |
| Already tracked | `sub/110c/boot_prototype.c`, `stubs_prototype.S`, `boot_witness.h` | Unchanged |
| Generated from the ROM | `sub/110c/stubs_entry.S`, `funcs_by_address.csv`, `funcs_by_name.csv`, `physw_bits.txt` | Not vendored: generated artifacts |
| Build outputs | `*.o`, `*.a`, `main.bin`, `main.bin.dump`, `main.elf`, `main.elf.syms`, `prototype_main.{bin,elf}`, `PRIMARY.BIN` (0-byte placeholder) | Not vendored: binaries |

**Firmware-specific constants in the vendored files.** All of these are ROM addresses or values written as text in comments or `#define`s. None is a firmware byte sequence. VERIFIED by inspection.

| File | Constants |
|---|---|
| `kbd.c` | table address `0xFC66C948` and the key masks |
| `platform_kbd.h` | `0xFC66C948`, `0xfc66ca30`, `0xfc66ca58`, `0xfc66cab0`, `0xfc66cab8` and the masks |
| `shooting.c` | `0xfca90f10`, `0xfc07317c` |
| `lib.c` | `0xFCA9129C`, the levent IDs, and the G5 X LED MMIO address `0xd20b0994`, which the comment says *not* to use |
| `platform_camera.h` | `0x02010100`, `0x40000000` |

No paths, credentials or secrets were found.

## 3. Provenance and SHA-256 of the vendored inputs

| File | Bytes | Baseline SHA-256 | Independent records of the same hash | Local modification |
|---|---|---|---|---|
| `kbd.c` | 3750 | `ff4d62afd1d98cd22b6369eac0dde539b19a2dec2a44a255c9251c4272eed0ce` | PORT-0C frozen-source table (Codex, 2026-10-24); PORT-0F (Gemini); PORT-7A E9 | none since freeze |
| `lib.c` | 2997 | `1036e3452e66274010b5da755b2740f0b01b80f918009abf82e52045a0f8a1da` | PORT-0C; PORT-0F | none since freeze |
| `platform_camera.h` | 3885 | `0fed491abe86c069166c4aadc50eceec81dd0da835943049e03b370fede9f6ac` | PORT-0C; PORT-7A E7 | none since freeze |
| `platform_kbd.h` | 872 | `4d2594313c304ffb6598d47cfc9cd4bbffd0f3b1b64d35e734df8e8218d459b0` | PORT-0C; PORT-7A E8; PORT-7B fixture (byte-identical) | PORT-7B patch 0002 → final `4c9fd8b4…9b24` |
| `shooting.c` | 4581 | `005eecdb840eeab16b16ef251fa8428653eabf34c8ee29a20cccb03f48af9b96` | PORT-0C; PORT-7A E10 | none since freeze |

- **VERIFIED:** each vendored file is byte-identical to the live workspace file, or, for `platform_kbd.h`, to the PORT-7B preimage. Each hash equals the PORT-0C frozen-source record and at least one other record. These are the GM1.10C CHDK-PORT-0 sources.
- **Nothing historical was substituted:** no file comes from `g3x_110e.patch` (GM1.10E). PORT-7A had already shown that the current sources differ from that patch (14 keys against 19, 17 modes against 32).
- **Caveat:** PORT-0C and PORT-0F are untracked local documents. On a public clone only PORT-7A (tracked in PR #6) records four of the five hashes; `lib.c`'s provenance record is local-only (§7).

**Patch relationship (VERIFIED):**
- The manifest records patch 0002 with preimage `4d259431…` and postimage `4c9fd8b4…`. These equal the `# Preimage/Postimage SHA-256` lines in the patch header and the PORT-7B test constants.
- Applying the patch strictly to the vendored preimage gives the postimage, which is byte-identical to the live corrected header.
- The bootstrapped `KEYS_MASK0` is `0x000533F9`; the PORT-7B value is unchanged.

## 4. Files added by PR #7

| File | Purpose |
|---|---|
| `vendor/g3x-platform/MANIFEST.json` | Schema 1. Lists the five files with size, baseline and final SHA-256 and provenance pointers. Also records the upstream commit, firmware `GM1.10C`, target root `chdk-port`, and the patch 0002 pre/post hashes. |
| `vendor/g3x-platform/platform/g3x/{kbd.c, lib.c, platform_camera.h, platform_kbd.h, shooting.c}` | Exact baseline bytes; `platform_kbd.h` is the preimage. 16,085 bytes in total. |
| `tools/bootstrap_chdk_platform.py` | The bootstrap (§5). Standard library only. |
| `tests/test_port8a_platform_bootstrap.py` | 34 tests: 33 run on a clean clone, 1 runs only in the local workspace. Before the review fixes there were 29. |
| `docs/PORT8A_PLATFORM_BOOTSTRAP.md` | This report. |

None of these paths is matched by `.gitignore` (`git check-ignore` rc=1). PORT-7B's patch, fixtures and tests are unchanged.

## 5. Bootstrap design

```sh
python3 -B tools/bootstrap_chdk_platform.py --verify-only   # report only, never writes
python3 -B tools/bootstrap_chdk_platform.py                 # create/advance into chdk-port/
python3 -B tools/bootstrap_chdk_platform.py --target DIR    # alternative CHDK tree root
```

Steps 1–3 run before anything is written; a failure there means nothing is written. Step 4 re-validates each write as it happens (§5.1). If it stops on a conflict, files written earlier in that run are already at their final hash, and no modified file has been overwritten.

1. **Integrity:** the manifest schema and paths are checked; absolute paths, `..`, backslashes and duplicates are rejected. Every vendored file must match its recorded size and baseline hash. Each patch header's Preimage/Postimage lines must equal the manifest. The current content must equal the patch preimage; applying the patch with no fuzz must give the postimage; every final hash must match. Otherwise exit **3**.
2. **Plan:** each target file is classified as follows. If any file is a `CONFLICT`, nothing is written and the exit code is **2**.

   | Current state of the target file | Classification |
   |---|---|
   | missing | `CREATE` |
   | final hash | `OK` |
   | exact recorded baseline, e.g. an unpatched `platform_kbd.h` | `ADVANCE` |
   | any other hash, a symlink anywhere in the path, or not a regular file | `CONFLICT` |

3. **Verify-only:** exit **0** if every file is `OK`, otherwise **1**. Never writes and takes no lock.
4. **Write:** the run first takes the lock on the target root (§5.1). Each file is then written to a scratch file in its own directory and fsynced, and moved into place by `CREATE` or `ADVANCE` (§5.1). Afterwards every file is re-verified, exit **0**. A conflict found at this stage gives exit **2**.

Repeat runs do not write; output is sorted by path.

### 5.1 Changes between planning and writing (Tech Lead review of `5a08a92`)

**What the review found:** `5a08a92` checked the destination's hash for `ADVANCE` and then called `os.replace`. A write landing between the two would have been overwritten. Its symlink checks also ran only at planning time. So the earlier claim that the tool "never overwrites a modified file" held only if nothing else wrote to the files during a run.

The tool now applies these defences:

| Defence | What it covers |
|---|---|
| **Single writer:** an exclusive, non-blocking `flock` on the target root directory, held for the whole run | A second write-mode bootstrap exits **2** with nothing written. The lock is advisory: other programs ignore it. |
| **No symlink traversal at write time:** each path component is opened with `O_DIRECTORY \| O_NOFOLLOW`, starting from the target-root descriptor. All later operations (`openat`, `linkat`, `renameat`, `unlinkat`) use those descriptors. | A directory replaced by a symlink at any point fails closed. Nothing is written outside the tree. |
| **`CREATE`:** the new file is linked in with `linkat()`, which never replaces an existing entry | A file that appears after planning is kept, and the run stops with a conflict. |
| **`ADVANCE`:** the destination is first renamed aside, which is atomic. The inode that was moved is hashed. The final file is then linked in, only if that inode is the exact recorded baseline and the name is still free. | Content changed after planning is restored to the destination unchanged. If the name was taken in the meantime, the earlier content is kept beside it as `.bootstrap-*.pre`. A file saved over the name (save-by-rename) or newly created during the run is kept. Each case stops with a conflict. |

- **Scratch files:** created with `O_EXCL | O_NOFOLLOW` and mode `0644`, and removed on every path.
- **Guarantee, narrowed:** no file is overwritten unless its content is the exact recorded baseline at the moment it is moved aside. Changes made by path (a new file, save-by-rename, swapping in a symlink, another bootstrap run) are never overwritten.
- **Precondition the tool cannot enforce:** no other process may write these files *in place*, through a descriptor it opened before the run, while a write-mode run is in progress. A write of that kind landing after the `ADVANCE` hash check and before the moved-aside copy is removed would be lost. Also, during `ADVANCE` the destination name is briefly absent.
- **How to run it:** use write mode only when nothing else is editing `chdk-port/platform/g3x`. `--verify-only` is always safe.
- **Tests:** these paths are covered by `TestConcurrentChangeDefences` (§6). A mutation check confirmed the tests catch the old behaviour: with the old `os.replace` overwrite and no hash check restored, the edit-after-planning and save-by-rename tests fail.

## 6. Validation

**Initial validation, before the first commit:** a fresh temporary clone of `fix/port7b-playback-mask` at `b6c74e6`. The PORT-8A files, not yet committed, were copied in, plus the untracked PORT-7C test only so it could be run. The review-fix validation is at the end of this section.

| Step | Result |
|---|---|
| PORT-8A suite before bootstrap | `Ran 29 … OK (skipped=1)`; only the local-workspace check was skipped |
| PORT-7A / PORT-7C before bootstrap | `FAILED (errors=1)` / `FAILED (errors=4)` (missing sources) |
| `--verify-only` on the clean tree | 5 × `CREATE`, exit 1, nothing written |
| Bootstrap | 5 files written, all at final hash, exit 0. Only those five files were created under `platform/g3x/`. `git status` stays clean because they are ignored, and the tracked `sub/110c` files are unchanged. |
| PORT-7A after bootstrap | `Ran 18 … OK` |
| PORT-7C after bootstrap | `Ran 23 … OK` |
| PORT-7B after bootstrap | `Ran 19 … OK`; its local-workspace checks now run and pass |
| PORT-8A after bootstrap | `Ran 29 … OK`; nothing skipped |
| Repeat bootstrap | all `OK`, exit 0; hashes and mtimes of all files identical before and after |
| Modified `lib.c` with `kbd.c` deleted | `CONFLICT lib.c`, `RESULT conflict: nothing written`, exit 2. `lib.c` was left unchanged, and `kbd.c` was not recreated because the run stops before any write. |

**Local workspace:**
- `--verify-only` reports all five files `OK` at their final hashes, exit 0.
- PORT-8A runs 29 tests, all OK.
- The bootstrap was never run in write mode against the live tree.

**Safety:**
- 786 pre-existing files under `candidate_port2a/`, `firmware/`, `chdk-port/platform/g3x/`, `chdk-port/loader/`, `patches/` and `tests/fixtures/` have identical SHA-256 before and after.
- The six modified files from other agents are unchanged.
- The only new untracked paths are `vendor/`, `tools/bootstrap_chdk_platform.py` and `tests/test_port8a_platform_bootstrap.py`, plus this doc.
- No build, ROM read, subprocess or hardware action.

**Tests that run on a clean clone:**
- vendor-tree contents and integrity;
- the vendored preimage equals the PORT-7B fixture, and the PORT-7B excerpts are line ranges of the vendored sources;
- the bootstrapped mask is `0x000533F9`;
- create, idempotence and verify-only behaviour;
- advancing a file from the recorded preimage;
- a modified file blocks every write, in both modes;
- a symlink is a conflict and the file outside the tree is untouched;
- a missing target root is an error;
- a tampered vendor file, an unexpected patch preimage, a vendored postimage, and unsafe manifest paths are all rejected with nothing written;
- all PORT-7A constant checks on a bootstrapped tree;
- changes between planning and writing:
  - an edit to the baseline file is restored, not overwritten;
  - a save-by-rename during `ADVANCE` is kept (exit 2);
  - a file created after planning is kept;
  - a directory swapped for a symlink leads to nothing written outside the tree;
  - a second writer is locked out, while verify-only still works.

**Review-fix validation:** a fresh clone of `5a08a92`, with only the three review-fix files changed. `vendor/`, `MANIFEST.json` and `patches/` were byte-unchanged.

| Step | Result |
|---|---|
| PORT-8A before bootstrap | `Ran 34 … OK (skipped=1)` |
| `--verify-only` | 5 files pending, nothing written |
| Bootstrap | wrote 5 files; a second run reported all `OK` and wrote nothing |
| PORT-7A after bootstrap | 18 OK |
| PORT-7B after bootstrap | 19 OK |
| PORT-7C after bootstrap | 23 OK (untracked test, copied in unmodified) |
| PORT-8A after bootstrap | 34 OK |

No `.bootstrap-*` scratch files were left, and `git status` showed only the three changed files.

## 7. Remaining blockers and limits

1. **Depends on PR #6.** The patch, the PORT-7A test and the PORT-7B fixtures exist only on `fix/port7b-playback-mask`. PR #7 targets that branch. Once #6 merges, retarget #7 to `main`.
2. **Single-writer precondition** (§5.1): the tool cannot guard against in-place writes through descriptors opened before the run. The `flock` excludes only other bootstrap runs.
3. **The PORT-7C test is untracked** (`tests/test_port7c_platform_validation.py`, another agent's work). It passes after bootstrap, but a public clean clone can only run it once its owner commits it. PORT-8A does not import it.
4. **Public provenance.** PORT-0C and PORT-0F are untracked. Until they are committed, `lib.c`'s hash has no tracked record outside this manifest.
5. **Drift.** The vendored files duplicate ignored live files. Any approved edit to a live source needs a matching vendor and manifest update; otherwise the local-workspace checks (PORT-7B excerpts, PORT-8A verify-only) fail. INFERRED as the intended way to detect drift.
6. **Not a build set.** The baseline is limited to the five files the tests read. It does not make `chdk-port` buildable, and the bootstrap prepares no firmware, boot, loader or hook code. The physical Playback bit and runtime override behaviour remain UNKNOWN, exactly as in PORT-7B.

**Hardware readiness: STRICT NO-GO.**
