# PORT-19 T3: Inspector Witness Address Resolution (P6 Resolution)

**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C)  
**Task ID**: `p19-witness-address-r2` (PORT-19 T3 redo)  
**Host Platform**: AgentBridge isolated worktree (`/var/lib/agentbridge/worktrees/g3x-lite/port-19-trial-blockers-p19-witness-address-r2`)  
**Evaluation Mode**: Phase 0 Read-Only / Host-Side Preflight & Inspector Witness Address Resolution (Zero ROM reads)  
**Date**: 2026-10-31  

---

## 1. Executive Summary & Trial Conflict P6 Resolution

In the owner trial plan (`docs/PORT18_OWNER_TRIAL_PLAN.md:26`), blocking precondition **P6** recorded an unresolved conflict between the tracked witness inspector metadata (`0x0035F780` in `firmware/tools/witness_inspector_metadata.json:4`) and the candidate symbol `boot_witness` pinned in PORT-16 (`0x0035F7A0` in `docs/PORT16_WITNESS_ADDRESS.md:15` and `docs/PORT16_CANDIDATE_BUILD.md:21-24`).

This task resolves conflict P6 host-side with zero ROM reads:
1. **Root Cause Confirmed**: In CHDK-PORT-1G, the witness inspector was developed against the initial pre-correction prototype (`boot_witness` at `0x0035F780`). In PR #2 (`SD1stInit`), Thumb-2 instructions were added to `boot_prototype.c` and stubs to `stubs_prototype.S`, expanding `.text` and pushing `.data` forward by exactly 32 bytes (`+0x20`), relocating `boot_witness` to `0x0035F7A0`. In PORT-16, candidate build tooling was updated to emit aligned artifacts directly to `candidate_port2a/` with `0x0035F7A0`, while historical artifacts under `firmware/tools/` were left at `0x0035F780`.
2. **VERIFIED Candidate Address**: Directly queried from the candidate built by `tools/build_candidate_port2a.py` using `arm-none-eabi-nm` and `arm-none-eabi-readelf`:
   - `candidate_port2a/candidate_main.elf`: `0035f7a0 D boot_witness` (Section 3 `.data`, Type `D`, Size 32 B / `0x20`, 16-byte aligned).
   - `candidate_port2a/witness_inspector_metadata.json`: `"witness_address": "0x0035F7A0"`, `"witness_address_int": 3536800`.
   - `candidate_port2a/witness_inspector_payload.bin`: MOVW/MOVT opcodes decode to `0x0035F7A0`.
3. **Inspector Tooling Fixes (`tools/build_witness_inspector.py`, `tools/validate_witness_inspector.py`)**:
   - `tools/build_witness_inspector.py`: Pinned `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`. Enforces `witness_addr == expected_addr`, raising `ValueError` on any mismatch (hard error, never silently accepted). Output defaults to `candidate_port2a/` to protect `firmware/tools/` from being overwritten.
   - `tools/validate_witness_inspector.py`: Pinned `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`. Resolves candidate inspector artifacts from `candidate_port2a/` by default. Strictly checks that payload binary MOVW/MOVT, ELF symbol, and address metadata all equal `0x0035F7A0`, raising `ValueError` if `0x0035F780` or any other mismatched address is encountered. Replaced all `assert` statements throughout the validator with explicit `if ...: raise ValueError(...)` so `python -O` / `PYTHONOPTIMIZE=1` cannot bypass validation. Enforces bit 15 of MOVW/MOVT second halfwords must be 0.
4. **Preflight Tool Integration (`tools/port18_trial_preflight.py`)**:
   - `EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0` is pinned in the preflight tool (line 50).
   - Added optional `--inspector-metadata` / `--metadata` and `--inspector-bin` checks to verify candidate inspector alignment against the pinned witness address `0x0035F7A0`, failing closed with exit code 1 if mismatched (e.g. `0x0035F780`).
   - Extended inspector metadata check to validate `witness_address_int`: whenever present, checks that it is an `int`, equals `witness_address`, and equals pinned `0x0035F7A0`. Disagreements or non-integer types return a clean `FAIL` with a clear reason (no crash).
   - Extended output collision protection: `--out` is checked against all inputs including `--inspector-metadata` and `--inspector-bin`. Direct equality, symlink aliases (`os.path.realpath`), and hardlink aliases (`st_dev`/`st_ino`) are rejected before any report is written, preserving input artifact bytes.
   - Fix (b): When `witness_address` is missing in inspector metadata, reports a clean `FAIL` without crashing (safe string formatting).
   - Fix (c): In inspector payload check, uses `payload_addr is not None` rather than truthiness when selecting the diagnostic reason text.
   - Full Thumb-2 MOVW/MOVT encoding validation: Validates opcode bits and requires bit 15 of each instruction's second halfword to be 0, returning clean FAIL for malformed variants (such as `0xF7A0` or `0x8735`), never crashing.
5. **Regression & Coherence Test Suites**:
   - `tests/test_port19_witness_address.py`: 22 unit tests asserting tripartite agreement across the candidate build, inspector, and preflight tool on `boot_witness = 0x0035F7A0`, and verifying hard-error rejection if `0x0035F780` is reintroduced. The forbidden address is written once, as the module constant `FORBIDDEN_WITNESS_ADDR` (`tests/test_port19_witness_address.py:44`). All fixtures and expected strings are derived from it (`FORBIDDEN_WITNESS_HEX = f"0x{FORBIDDEN_WITNESS_ADDR:08X}"`, `FORBIDDEN_WITNESS_NM = f"{FORBIDDEN_WITNESS_ADDR:08x}"`). Includes regression tests for `witness_address_int` validation, output collision protection across direct paths, symlinks, and hardlinks, validator execution under `python -O` / `PYTHONOPTIMIZE=1` against a self-consistent forbidden-address fixture, AST verification of 0 `assert` statements in the validator, and preflight rejection of `0xF7A0` and `0x8735` halfword variants.
   - Fix (a): `tests/test_validate_witness_inspector.py::test_simulated_symbol_address_change_and_linker_output` asserts that the pinned default `EXPECTED_BOOT_WITNESS_ADDR` rejects a simulated ELF with `boot_witness` at `0x00358B10` (`ValueError`), and then verifies dynamic address resolution by passing `expected_witness_addr=sim_witness_addr` explicitly.
   - `tests/test_port18_trial_preflight.py` (unchanged by this task): 35 unit tests verifying clean FAIL on missing fields, conflicting symbols, or corrupted opcodes.

---

## 2. Inventory of `0x0035F780` Occurrences

### 2.0 Method and Scope

Both parts use the same search patterns, the uppercase and lowercase spellings `0x0035F780` and `0x0035f780`. These are the only spellings `git grep` found. Identifiers without the `0x` prefix (for example the test name `test_inspector_validator_rejects_0035f780`) do not match and are not counted. The binary file `firmware/tools/witness_inspector_payload.bin` encodes the address as MOVW/MOVT immediates (`#0xF780`, `#0x0035` at offsets `0x0A..0x11`), not as text, so `git grep` does not match it either. It is covered under §2.1 with the metadata JSON.

| Part | Tree | Command | Total | Files |
|:---|:---|:---|:---:|:---:|
| (a) Former uses | base `f9c1bdc` (origin/main before this task) | `git grep -n -e 0x0035F780 -e 0x0035f780 f9c1bdc -- .` | 170 | 18 |
| (b) Remaining | final tree of this task | `git grep -n -e 0x0035F780 -e 0x0035f780 -- . ':!docs/PORT19_WITNESS_ADDRESS.md'` | 171 | 19 |

The difference of +1 is the single module constant `tests/test_port19_witness_address.py:44`, which is new in this task. Every other remaining occurrence is in a file this task did not change and sits at the same line as at base, with one exception: `tests/test_validate_witness_inspector.py:54` moved to line 75 because the fix (a) edits added lines above it.

**Key finding**: at base, `tools/` contained **zero** occurrences of `0x0035F780`. The inspector reached the stale address through its default artifact paths, not through a literal. At base, `tools/build_witness_inspector.py:29-34` and `tools/validate_witness_inspector.py:54-57` defaulted to `firmware/tools/witness_inspector_{metadata.json,payload.bin,payload.o}`, and neither tool pinned an expected address. `firmware/tools/witness_inspector_metadata.json:4` holds `0x0035F780`. `[VERIFIED: git show f9c1bdc:tools/build_witness_inspector.py; git show f9c1bdc:tools/validate_witness_inspector.py]`

### 2.1 (a) Former Uses at Base `f9c1bdc`

Command: `git grep -n -e 0x0035F780 -e 0x0035f780 f9c1bdc -- .` → 170 occurrences in 18 files.

| File | Count | Lines at `f9c1bdc` | Fixed to / why it remains |
|:---|:---:|:---|:---|
| `firmware/tools/witness_inspector_metadata.json` | 1 | 4 | **This is the P6 source.** Fixed at the consumer side. The inspector tools now default to `candidate_port2a/` (`tools/build_witness_inspector.py:30,37,39`; `tools/validate_witness_inspector.py:54,73,75`) and pin `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0` (`tools/build_witness_inspector.py:42`, `tools/validate_witness_inspector.py:78`, `tools/port18_trial_preflight.py:50`). If this file, or the matching `firmware/tools/witness_inspector_payload.bin`, is passed explicitly or used as the fallback, the validator raises `ValueError` and preflight reports `FAIL` with exit 1. The file itself remains unchanged because `firmware/tools/` is outside this task's allowed paths. It is the historical pre-correction baseline. |
| `tests/test_validate_witness_inspector.py` | 1 | 54 | A comment explaining that the test derives the address dynamically instead of using the historical value. It remains as a comment and is now at line 75 after the fix (a) edits. |
| `tests/fixtures/port18/preflight/wrong_witness.map` | 2 | 1, 2 | Negative fixture: a linker map with `boot_witness` at the stale address. It remains, because `tests/test_port18_trial_preflight.py:133-149` asserts that preflight rejects it. |
| `tests/test_port16_pipeline_witness.py` | 14 | 159, 359, 365, 380, 384, 392, 405, 489, 490, 499, 507, 520, 548, 560 | Negative fixtures, rejection assertions, and their docstrings. They show that the PORT-16 pipeline rejects stale metadata, payloads, and symbol tables. They remain as guards. |
| `tests/test_port16_validator_witness.py` | 17 | 9, 19, 273, 370, 378, 383, 391, 571, 581, 584, 605, 606, 615, 618, 633, 635, 642 | Negative fixtures, rejection assertions, and their docstrings (module docstring lines 9 and 19 describe the mismatch cases). They show that the candidate validator rejects the stale address. They remain as guards. |
| `tests/test_port18_trial_preflight.py` | 8 | 133, 149, 576, 598, 600, 608, 630, 633 | Negative fixtures and assertions: wrong-witness map and conflicting nm entries that must produce `FAIL`. They remain as guards. |
| `docs/PORT18_OWNER_TRIAL_PLAN.md` | 4 | 11, 26, 71, 98 | Records precondition P6. It remains because this task forbids editing this file. |
| `docs/HANDOFF.md` | 13 | 186, 188, 189, 192, 228, 340, 388, 398, 426, 455, 2078, 2080, 2113 | Historical milestone record. It remains because AGENTS.md (AgentBridge mode) reserves edits to this file for the milestone's final task. |
| `docs/PROJECT_STATE.md` | 10 | 93, 133, 135, 179, 191, 199, 206, 610, 612, 645 | Historical milestone record. It remains for the same AGENTS.md reason. |
| `docs/PORT16_WITNESS_ADDRESS.md` | 37 | 17, 18, 19, 21, 22, 24, 26, 27, 28, 31, 195, 198, 206, 213, 221, 228, 233, 236, 237, 244, 250, 253, 256, 259, 403, 405, 668, 669, 670, 671, 672, 674, 680, 698, 699, 700, 702 | Historical PORT-16 record of the relocation from `0x0035F780` to `0x0035F7A0`. It remains because it is outside this task's allowed paths. |
| `docs/PORT16_CANDIDATE_BUILD.md` | 9 | 26, 276, 286, 322, 327, 388, 389, 433, 449 | Historical PORT-16 build record, including the tracked-metadata discrepancy. It remains because it is outside the allowed paths. |
| `docs/PORT16_OWNER_TRIAL_PLAN.md` | 1 | 158 | Historical PORT-16 trial plan. It remains because it is outside the allowed paths. |
| `docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md` | 46 | 14, 15, 23, 25, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 60, 61, 63, 64, 67, 74, 94, 109, 121, 126, 169, 171, 172, 173, 259, 263 | Historical PORT-15 census of the pre-correction address. It remains because it is outside the allowed paths. |
| `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md` | 1 | 66 | Historical review finding C09. It remains because it is outside the allowed paths. |
| `docs/PORT14_Q_MEM03_BSS.md` | 1 | 124 | Historical audit citation. It remains because it is outside the allowed paths. |
| `docs/PORT3C_RESTART_READINESS_MATRIX.md` | 1 | 231 | Historical readiness matrix row C09. It remains because it is outside the allowed paths. |
| `docs/REPRODUCIBILITY_MANIFEST.md` | 2 | 76, 77 | Historical pre-correction artifact hashes. They remain because they are outside the allowed paths. |
| `docs/RESTART_SD_HOST_AUDIT.md` | 2 | 248, 253 | Historical SD audit record of the relocation. It remains because it is outside the allowed paths. |
| **Total** | **170** | 18 files | |

### 2.2 (b) Remaining Occurrences in the Final Tree

Command (regenerated as the last step, after all code and test edits):
```bash
git grep -n -e 0x0035F780 -e 0x0035f780 -- . ':!docs/PORT19_WITNESS_ADDRESS.md'
```

Per-file counts (`git grep -c` with the same patterns and pathspec):

| File | Count | Classification |
|:---|:---:|:---|
| `tests/test_port19_witness_address.py` | 1 | Guard: the single `FORBIDDEN_WITNESS_ADDR` constant (line 44), from which all PORT-19 negative fixtures are derived |
| `tests/test_validate_witness_inspector.py` | 1 | Guard comment in the dynamic-resolution test (line 75) |
| `tests/fixtures/port18/preflight/wrong_witness.map` | 2 | Negative fixture |
| `tests/test_port16_pipeline_witness.py` | 14 | Negative fixtures, assertions, and their docstrings |
| `tests/test_port16_validator_witness.py` | 17 | Negative fixtures, assertions, and their docstrings |
| `tests/test_port18_trial_preflight.py` | 8 | Negative fixtures and assertions |
| `firmware/tools/witness_inspector_metadata.json` | 1 | Historical baseline artifact. Not a guard. It is outside the allowed paths, and the tools reject it (§2.1) |
| `docs/` (12 files, listed below) | 127 | Historical records. Not guards. They are outside the allowed paths, or their editing is reserved (`HANDOFF.md`, `PROJECT_STATE.md`) or forbidden (`PORT18_OWNER_TRIAL_PLAN.md`) |
| **Total** | **171** | 19 files |

The 127 `docs/` occurrences break down as follows: `CODEX_INDEPENDENT_RESTART_REVIEW.md` 1, `HANDOFF.md` 13, `PORT14_Q_MEM03_BSS.md` 1, `PORT16_CANDIDATE_BUILD.md` 9, `PORT16_OWNER_TRIAL_PLAN.md` 1, `PORT16_WITNESS_ADDRESS.md` 37, `PORT18_OWNER_TRIAL_PLAN.md` 4, `PORT3C_RESTART_READINESS_MATRIX.md` 1, `PROJECT_STATE.md` 10, `REPRODUCIBILITY_MANIFEST.md` 2, `RESTART_SD_HOST_AUDIT.md` 2, `agentbridge/PORT15_FIRSTBOOT_INVENTORY.md` 46.

Not every remaining occurrence is a guard or a negative fixture. The 41 occurrences under `tests/` are. The 1 in `firmware/tools/` and the 127 in `docs/` are historical records that this task may not edit. Retiring them, if wanted, belongs to a task scoped to those paths (`HANDOFF.md`/`PROJECT_STATE.md`: the milestone's final task).

Full `file:line` list (command output, cut to `file:line`; 171 lines):
```text
docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66
docs/HANDOFF.md:186
docs/HANDOFF.md:188
docs/HANDOFF.md:189
docs/HANDOFF.md:192
docs/HANDOFF.md:228
docs/HANDOFF.md:340
docs/HANDOFF.md:388
docs/HANDOFF.md:398
docs/HANDOFF.md:426
docs/HANDOFF.md:455
docs/HANDOFF.md:2078
docs/HANDOFF.md:2080
docs/HANDOFF.md:2113
docs/PORT14_Q_MEM03_BSS.md:124
docs/PORT16_CANDIDATE_BUILD.md:26
docs/PORT16_CANDIDATE_BUILD.md:276
docs/PORT16_CANDIDATE_BUILD.md:286
docs/PORT16_CANDIDATE_BUILD.md:322
docs/PORT16_CANDIDATE_BUILD.md:327
docs/PORT16_CANDIDATE_BUILD.md:388
docs/PORT16_CANDIDATE_BUILD.md:389
docs/PORT16_CANDIDATE_BUILD.md:433
docs/PORT16_CANDIDATE_BUILD.md:449
docs/PORT16_OWNER_TRIAL_PLAN.md:158
docs/PORT16_WITNESS_ADDRESS.md:17
docs/PORT16_WITNESS_ADDRESS.md:18
docs/PORT16_WITNESS_ADDRESS.md:19
docs/PORT16_WITNESS_ADDRESS.md:21
docs/PORT16_WITNESS_ADDRESS.md:22
docs/PORT16_WITNESS_ADDRESS.md:24
docs/PORT16_WITNESS_ADDRESS.md:26
docs/PORT16_WITNESS_ADDRESS.md:27
docs/PORT16_WITNESS_ADDRESS.md:28
docs/PORT16_WITNESS_ADDRESS.md:31
docs/PORT16_WITNESS_ADDRESS.md:195
docs/PORT16_WITNESS_ADDRESS.md:198
docs/PORT16_WITNESS_ADDRESS.md:206
docs/PORT16_WITNESS_ADDRESS.md:213
docs/PORT16_WITNESS_ADDRESS.md:221
docs/PORT16_WITNESS_ADDRESS.md:228
docs/PORT16_WITNESS_ADDRESS.md:233
docs/PORT16_WITNESS_ADDRESS.md:236
docs/PORT16_WITNESS_ADDRESS.md:237
docs/PORT16_WITNESS_ADDRESS.md:244
docs/PORT16_WITNESS_ADDRESS.md:250
docs/PORT16_WITNESS_ADDRESS.md:253
docs/PORT16_WITNESS_ADDRESS.md:256
docs/PORT16_WITNESS_ADDRESS.md:259
docs/PORT16_WITNESS_ADDRESS.md:403
docs/PORT16_WITNESS_ADDRESS.md:405
docs/PORT16_WITNESS_ADDRESS.md:668
docs/PORT16_WITNESS_ADDRESS.md:669
docs/PORT16_WITNESS_ADDRESS.md:670
docs/PORT16_WITNESS_ADDRESS.md:671
docs/PORT16_WITNESS_ADDRESS.md:672
docs/PORT16_WITNESS_ADDRESS.md:674
docs/PORT16_WITNESS_ADDRESS.md:680
docs/PORT16_WITNESS_ADDRESS.md:698
docs/PORT16_WITNESS_ADDRESS.md:699
docs/PORT16_WITNESS_ADDRESS.md:700
docs/PORT16_WITNESS_ADDRESS.md:702
docs/PORT18_OWNER_TRIAL_PLAN.md:11
docs/PORT18_OWNER_TRIAL_PLAN.md:26
docs/PORT18_OWNER_TRIAL_PLAN.md:71
docs/PORT18_OWNER_TRIAL_PLAN.md:98
docs/PORT3C_RESTART_READINESS_MATRIX.md:231
docs/PROJECT_STATE.md:93
docs/PROJECT_STATE.md:133
docs/PROJECT_STATE.md:135
docs/PROJECT_STATE.md:179
docs/PROJECT_STATE.md:191
docs/PROJECT_STATE.md:199
docs/PROJECT_STATE.md:206
docs/PROJECT_STATE.md:610
docs/PROJECT_STATE.md:612
docs/PROJECT_STATE.md:645
docs/REPRODUCIBILITY_MANIFEST.md:76
docs/REPRODUCIBILITY_MANIFEST.md:77
docs/RESTART_SD_HOST_AUDIT.md:248
docs/RESTART_SD_HOST_AUDIT.md:253
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:14
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:15
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:23
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:25
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:29
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:30
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:31
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:32
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:33
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:34
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:35
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:36
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:37
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:38
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:39
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:40
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:41
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:42
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:43
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:44
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:45
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:46
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:47
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:48
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:49
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:50
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:51
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:52
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:53
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:54
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:60
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:61
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:63
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:64
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:67
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:74
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:94
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:109
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:121
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:126
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:169
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:171
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:172
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:173
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:259
docs/agentbridge/PORT15_FIRSTBOOT_INVENTORY.md:263
firmware/tools/witness_inspector_metadata.json:4
tests/fixtures/port18/preflight/wrong_witness.map:1
tests/fixtures/port18/preflight/wrong_witness.map:2
tests/test_port16_pipeline_witness.py:159
tests/test_port16_pipeline_witness.py:359
tests/test_port16_pipeline_witness.py:365
tests/test_port16_pipeline_witness.py:380
tests/test_port16_pipeline_witness.py:384
tests/test_port16_pipeline_witness.py:392
tests/test_port16_pipeline_witness.py:405
tests/test_port16_pipeline_witness.py:489
tests/test_port16_pipeline_witness.py:490
tests/test_port16_pipeline_witness.py:499
tests/test_port16_pipeline_witness.py:507
tests/test_port16_pipeline_witness.py:520
tests/test_port16_pipeline_witness.py:548
tests/test_port16_pipeline_witness.py:560
tests/test_port16_validator_witness.py:9
tests/test_port16_validator_witness.py:19
tests/test_port16_validator_witness.py:273
tests/test_port16_validator_witness.py:370
tests/test_port16_validator_witness.py:378
tests/test_port16_validator_witness.py:383
tests/test_port16_validator_witness.py:391
tests/test_port16_validator_witness.py:571
tests/test_port16_validator_witness.py:581
tests/test_port16_validator_witness.py:584
tests/test_port16_validator_witness.py:605
tests/test_port16_validator_witness.py:606
tests/test_port16_validator_witness.py:615
tests/test_port16_validator_witness.py:618
tests/test_port16_validator_witness.py:633
tests/test_port16_validator_witness.py:635
tests/test_port16_validator_witness.py:642
tests/test_port18_trial_preflight.py:133
tests/test_port18_trial_preflight.py:149
tests/test_port18_trial_preflight.py:576
tests/test_port18_trial_preflight.py:598
tests/test_port18_trial_preflight.py:600
tests/test_port18_trial_preflight.py:608
tests/test_port18_trial_preflight.py:630
tests/test_port18_trial_preflight.py:633
tests/test_port19_witness_address.py:44
tests/test_validate_witness_inspector.py:75
```
`[VERIFIED: git grep output on the final tree; this list is the command output and every listed line matches the pattern]`

---

## 3. Primary Evidence from Built Candidate Symbol Table & Map

To establish the address from primary source output rather than documentation alone, the candidate was compiled directly from working-tree sources using the pinned ARM toolchain (`gcc-arm-none-eabi-5_4-2016q3`).

### 3.1 Candidate Build Command and Output
```bash
python3 -B tools/bootstrap_chdk_platform.py
python3 -B tools/build_candidate_port2a.py
```

**Verbatim Output**:
```text
CREATE   platform/g3x/kbd.c (missing)
CREATE   platform/g3x/lib.c (missing)
CREATE   platform/g3x/platform_camera.h (missing)
CREATE   platform/g3x/platform_kbd.h (missing)
CREATE   platform/g3x/shooting.c (missing)
RESULT ok: wrote 5 file(s); all files at final hash
--- Building Candidate Core (@ 0x003489B4) ---
  [OK] candidate_main.bin generated (116816 B)
--- Building Candidate Loader (@ 0x00008000) ---
  [OK] boot_witness confirmed at 0x0035F7A0 (matches expected 0x0035F7A0)
  [OK] candidate_loader.bin generated (118000 B)
--- Encoding Candidate DISKBOOT.BIN (dancingbits row 13) ---
  [OK] candidate_port2a/DISKBOOT.BIN successfully encoded (118001 B)
--- Associating Canon Basic Witness Inspector (@ 0x0035F7A0) ---
  [OK] Inspector script and payload (444 B, target 0x0035F7A0) verified and associated in candidate_port2a/
--- Generating Locked Candidate Manifest ---
  [OK] Manifest written to /var/lib/agentbridge/worktrees/g3x-lite/port-19-trial-blockers-p19-witness-address-r2/candidate_port2a/candidate_manifest.json

CANDIDATE BUILD COMPLETE (OFFLINE ONLY).
```
`[VERIFIED: candidate build command execution]`

### 3.2 Symbol Table Resolution (`arm-none-eabi-nm`)
Command:
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm -n candidate_port2a/candidate_main.elf | grep boot_witness
```

**Verbatim Output**:
```text
0035f7a0 D boot_witness
```
`[VERIFIED: toolchain arm-none-eabi-nm stdout]`

Key symbols from `candidate_main.elf`:
- `_start`: `0x003489B4` (Section `.text`, Thumb-2 entry)
- `boot_witness`: `0x0035F7A0` (Section `.data`, Type `D`, 16-byte aligned)
- `_end`: `0x00366CB0` (Section `.bss`, end of loaded CHDK candidate)

### 3.3 Symbol Properties and Section Inspection (`arm-none-eabi-readelf`)
Command:
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-readelf -s candidate_port2a/candidate_main.elf | grep boot_witness
```

**Verbatim Output**:
```text
  3754: 0035f7a0    32 OBJECT  GLOBAL DEFAULT    3 boot_witness
```
`[VERIFIED: toolchain arm-none-eabi-readelf stdout]`

Section `3` is `.data` (`0x0035aec0..0x00365204`, flags `WA`, 16-byte aligned). `boot_witness` address is `0x0035F7A0`, size is 32 bytes (`0x20`), alignment boundary is 16 bytes ($0x0035F7A0 \pmod{16} = 0$).

### 3.4 Candidate Inspector Artifacts Verification
- **Inspector Metadata (`candidate_port2a/witness_inspector_metadata.json`)**:
  ```json
  {
    "target": "Canon PowerShot G3 X (GM1.10C)",
    "symbol": "boot_witness",
    "witness_address": "0x0035F7A0",
    "witness_address_int": 3536800,
    "elf_file": "candidate_port2a/candidate_main.elf",
    "payload_bin": "candidate_port2a/witness_inspector_payload.bin",
    "payload_size": 444
  }
  ```
  `[VERIFIED: candidate_port2a/witness_inspector_metadata.json]`
- **Decoded MOVW/MOVT Immediate Address from Payload Binary (`candidate_port2a/witness_inspector_payload.bin`)**:
  - Offset 0x0A: `0xF24F 0x77A0` $\rightarrow$ `movw r7, #0xF7A0`
  - Offset 0x0E: `0xF2C0 0x0735` $\rightarrow$ `movt r7, #0x0035`
  - Reconstructed address: `(0x0035 << 16) | 0xF7A0 = 0x0035F7A0`.
  `[VERIFIED: binary opcode decode]`

---

## 4. Architectural Fixes in Tooling

The inspector validation and build tools, as well as the preflight tool, were updated to strictly pin and enforce `0x0035F7A0`, ensuring that any reintroduction of `0x0035F780` or other mismatch causes a hard error and non-zero exit code.

### 4.1 Inspector Builder (`tools/build_witness_inspector.py`)
1. **Pinned Constant**: Defined `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`.
2. **Hard-Error Symbol Check**: Updated `extract_witness_addr_from_elf`:
   ```python
   if expected_addr is not None and witness_addr != expected_addr:
       raise ValueError(
           f"Symbol 'boot_witness' address mismatch in {elf_path}: "
           f"expected 0x{expected_addr:08X}, got 0x{witness_addr:08X}"
       )
   ```
3. **Build Binding**: `build_witness_inspector` takes `expected_witness_addr=EXPECTED_BOOT_WITNESS_ADDR` by default.
4. **Output Directory Isolation**: Default output paths target `candidate_port2a/` (`PAYLOAD_O`, `PAYLOAD_BIN`, `LOADER_SCRIPT`, `METADATA_JSON`). This guarantees that running `build_witness_inspector.py` does not modify tracked historical files under `firmware/tools/`.
5. **CLI Support**: Added `--expected-addr` option defaulting to `0x0035F7A0`.

### 4.2 Inspector Validator (`tools/validate_witness_inspector.py`)
1. **Pinned Constant**: Defined `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`.
2. **Candidate Artifact Resolution**: Defined `CANDIDATE_DIR = candidate_port2a`. Defaults to candidate inspector payload, object, and metadata in `candidate_port2a/` when available.
3. **Hard-Error Address Invariants & Python Optimization Resilience**: In `validate_payload_binary`:
   - Replaced every `assert` statement in the module with explicit `if ...: raise ValueError(...)`.
   - Guaranteed enforcement under `python -O` and `PYTHONOPTIMIZE=1` (where Python strips `assert` bytecode).
   - Rejects binary payload if decoded address does not equal `expected_witness_addr` (`ValueError`).
   - Rejects candidate ELF if symbol does not equal `expected_witness_addr` (`ValueError`).
   - Rejects address metadata if target does not equal `expected_witness_addr` (`ValueError`).
   - Enforces default `expected_witness_addr = EXPECTED_BOOT_WITNESS_ADDR` (`0x0035F7A0`).
   - Validates Thumb-2 MOVW/MOVT bit 15 in `extract_witness_addr_from_binary_bytes`: ensures bit 15 of both `hw2` and `hw4` is 0, raising `ValueError` on malformed encodings.
4. **CLI Option**: Added `--expected-addr` defaulting to `0x0035F7A0`.

### 4.3 Preflight Verification Tool (`tools/port18_trial_preflight.py`)
1. **Existing Verification**: `EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0` is pinned (line 50), and linker map / symbol parsing rejects `0x0035F780` with status `FAIL` and exit code 1.
2. **Inspector Alignment Verification**: Added optional CLI flags `--inspector-metadata` (or `--metadata`) and `--inspector-bin`:
   - Decodes and validates that the inspector metadata JSON and/or payload binary target `0x0035F7A0`.
   - Any mismatch (such as historical `firmware/tools/witness_inspector_metadata.json` pointing to `0x0035F780`) records a check status `FAIL` and causes preflight to exit non-zero (exit code 1).
3. **Inspector Metadata Integer Alignment (`witness_address_int`)**:
   - Preflight inspects `witness_address_int` when present in inspector metadata.
   - Strictly verifies that it is an integer (`type(meta_int) is int`), matches the parsed string `witness_address`, and matches the pinned constant `0x0035F7A0`.
   - Any disagreement or invalid type returns a clean `FAIL` status with a diagnostic reason (never crashing or returning a false-positive `PASS`).
4. **Comprehensive Output Collision Protection**:
   - `validate_output_target` was extended to guard `--inspector-metadata` and `--inspector-bin` in addition to candidate binary and symbols files.
   - Inspects direct path equality, symlink aliases (`os.path.realpath`), and hardlink aliases (`os.stat` `st_dev`/`st_ino`).
   - Rejects collisions before any file writes or mutations can occur, preserving the exact bytes of the input artifacts.
5. **Fix (b) - Clean FAIL on Missing Metadata Field**: If `witness_address` is missing in metadata JSON, `meta_addr` is `None` and `meta_err` notes the missing field. The tool reports a clean `FAIL` without evaluating `0x{meta_addr:08X}` on `None`, preventing `TypeError` formatting exceptions.
6. **Fix (c) - Explicit None-Check on Payload Address**: The payload decoder check uses `elif payload_addr is not None:` rather than truthiness when selecting the diagnostic reason text.
7. **Thumb-2 MOVW/MOVT Encoding & Bit 15 Validation**:
   - `decode_inspector_payload_witness_addr_details` validates Thumb-2 T3 MOVW first-halfword opcode bits (`hw1 & 0xFBF0 == 0xF240`) and T1 MOVT first-halfword opcode bits (`hw1 & 0xFBF0 == 0xF2C0`).
   - Enforces that bit 15 of each instruction's second halfword must be 0 (`(hw2 & 0x8000) == 0`).
   - Reports clean FAIL verdict on malformed variants (such as `0xF7A0` or `0x8735`), preventing false-positive PASS on corrupted halfwords, never crashing.

### 4.4 Dynamic Inspector Resolution Test Fix (a)
In `tests/test_validate_witness_inspector.py::test_simulated_symbol_address_change_and_linker_output`:
- The test proves dynamic symbol address resolution by compiling a simulated ELF (`elf_sim`) with `boot_witness` at `0x00358B10`.
- Calling `bwi.build_witness_inspector` with the default pinned expectation (`0x0035F7A0`) asserts that a `ValueError` is raised (`address mismatch`).
- The test then explicitly passes `expected_witness_addr=sim_witness_addr` to build and validate the inspector dynamically, preserving the test's purpose while maintaining strict pinned defaults in production tooling.

---

## 5. Verification Test Suite Results

### 5.1 `tests/test_port19_witness_address.py`
Command:
```bash
python3 -m unittest -v tests.test_port19_witness_address
```
Test names and docstrings from the verbose output (run after the `FORBIDDEN_WITNESS_ADDR` refactor; tool stdout interleaved with some results is omitted):
```text
test_built_candidate_manifest: candidate_manifest.json specifies boot_witness_addr = 0x0035F7A0. ... ok
test_built_candidate_symbol_table: Built candidate ELF symbol table defines boot_witness = 0x0035F7A0. ... ok
test_candidate_inspector_artifacts: candidate_port2a inspector metadata and binary target 0x0035F7A0. ... ok
test_inspector_builder_rejects_0035f780_symbol_table: Inspector builder extract_witness_addr_from_elf rejects FORBIDDEN_WITNESS_ADDR with ValueError. ... ok
test_inspector_metadata_both_fields_pinned_passes: Metadata with both witness_address and witness_address_int pinned to 0x0035F7A0 passes.
test_inspector_metadata_missing_field_reports_clean_fail: Inspector metadata missing 'witness_address' field reports clean FAIL without crashing (Fix b).
test_inspector_metadata_witness_address_int_disagreement_fails: Metadata with witness_address string OK but witness_address_int = FORBIDDEN_WITNESS_ADDR fails (non-zero exit).
test_inspector_metadata_witness_address_int_non_integer_fails: Metadata with witness_address_int not an integer fails with clean FAIL reason.
test_inspector_payload_binary_invalid_opcodes_reports_clean_fail: Inspector payload binary with non-MOVW/MOVT bytes reports clean FAIL (Fix c).
test_inspector_validator_rejects_0035f780: Inspector validator fails closed when encountering FORBIDDEN_WITNESS_ADDR in metadata or payload. ... ok
test_pinned_constants_coherence: All tools define EXPECTED_BOOT_WITNESS_ADDR as 0x0035F7A0, never FORBIDDEN_WITNESS_ADDR. ... ok
test_preflight_movw_movt_thumb2_opcode_and_bit15_validation: Decoder fully validates Thumb-2 T3 MOVW / T1 MOVT: opcode bits and second halfword bit 15 == 0.
test_preflight_tool_passes_candidate_and_rejects_0035f780: Preflight tool accepts 0x0035F7A0 candidate symbols and rejects FORBIDDEN_WITNESS_ADDR with exit 1.
test_refuse_out_as_hardlink_to_inspector_bin: --out given as hardlink alias to --inspector-bin is rejected, leaving file untouched. ... ok
test_refuse_out_as_hardlink_to_inspector_metadata: --out given as hardlink alias to --inspector-metadata is rejected, leaving file untouched. ... ok
test_refuse_out_as_symlink_to_inspector_bin: --out given as symlink alias to --inspector-bin is rejected, leaving file untouched. ... ok
test_refuse_out_as_symlink_to_inspector_metadata: --out given as symlink alias to --inspector-metadata is rejected, leaving file untouched. ... ok
test_refuse_out_equal_to_inspector_bin: --out pointing directly to --inspector-bin file is rejected, leaving file untouched. ... ok
test_refuse_out_equal_to_inspector_metadata: --out pointing directly to --inspector-metadata file is rejected, leaving file untouched. ... ok
test_tripartite_witness_address_agreement: Inspector, preflight tool, and built candidate strictly agree on 0x0035F7A0. ... ok
test_validator_contains_no_assert_statements: Inspector validator contains zero assert statements (enforces invariants under python -O). ... ok
test_validator_rejects_self_consistent_0035f780_under_python_optimize: Validator rejects a self-consistent FORBIDDEN_WITNESS_ADDR fixture when run under -O / PYTHONOPTIMIZE=1. ... ok

Ran 22 tests in 0.948s

OK
```
`[VERIFIED: test execution]`

### 5.2 Witness Tests (`witness_tests`)
`tests/test_validate_witness_inspector.py` was not run by the agent in this revision. AGENTS.md (AgentBridge mode) forbids agents from running it because it builds a camera payload binary. AgentBridge's `witness_tests` validation step covers it. `[UNKNOWN until AgentBridge validation]`

### 5.3 Candidate Validator (`candidate_validate`)
`tools/validate_candidate_port2a.py` was not re-run by the agent in this revision because the sandbox denied the command. This revision changes no tool or candidate source, so the validator's inputs are unchanged. AgentBridge's `candidate_validate` step covers it. `[UNKNOWN until AgentBridge validation]`

### 5.4 Preflight and PORT-16 Witness Tests
Commands:
```bash
python3 -m unittest tests.test_port18_trial_preflight
python3 -m unittest tests.test_port16_pipeline_witness tests.test_port16_validator_witness
```
`tests.test_port18_trial_preflight`: `Ran 35 tests ... OK`. The PORT-16 witness suites also passed when run alongside it: 91 tests in total, all OK. `[VERIFIED: test execution]`

---

## 6. Integration Invariance & Safety Compliance

- **Candidate Source & Builder Invariance**: Neither `chdk-port/` nor `tools/build_candidate_port2a.py` was altered.
- **Allowed Scope Conformance**: Relative to base `f9c1bdc`, only these permitted paths were modified or added:
  - `docs/PORT19_WITNESS_ADDRESS.md`
  - `tests/test_port19_witness_address.py`
  - `tests/test_validate_witness_inspector.py`
  - `tools/build_witness_inspector.py`
  - `tools/validate_witness_inspector.py`
  - `tools/port18_trial_preflight.py`
- **Zero ROM Reads**: The resolution was completed entirely host-side using the local toolchain and candidate build artifacts. No firmware ROM files were read or probed.
- **Git Hygiene**: No binaries or build outputs (`candidate_port2a/`) are tracked or committed.
- **Trial Plan Status**: Precondition P6 is resolved in tooling. The inspector, preflight tool, and candidate build agree on `boot_witness = 0x0035F7A0`, and the stale `firmware/tools/` inspector artifacts are rejected fail-closed. `docs/PORT18_OWNER_TRIAL_PLAN.md` is not edited by this task.
