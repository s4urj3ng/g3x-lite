# PORT-19 T3: Inspector Witness Address Resolution (P6 Resolution)

**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C)  
**Task ID**: `p19-witness-address-r2` (PORT-19 T3 redo)  
**Host Platform**: AgentBridge isolated worktree (`/var/lib/agentbridge/worktrees/g3x-lite/port-19-trial-blockers-p19-witness-address-r2`)  
**Evaluation Mode**: Phase 0 Read-Only / Host-Side Preflight & Inspector Witness Address Resolution (Zero ROM reads)  
**Date**: 2026-10-31  

---

## 1. Executive Summary & Trial Conflict P6 Resolution

In the owner trial plan (`docs/PORT18_OWNER_TRIAL_PLAN.md:128`), blocking precondition **P6** recorded an unresolved conflict between the tracked witness inspector metadata (`0x0035F780` in `firmware/tools/witness_inspector_metadata.json:4`) and the candidate symbol `boot_witness` pinned in PORT-16 (`0x0035F7A0` in `docs/PORT16_WITNESS_ADDRESS.md:15` and `docs/PORT16_CANDIDATE_BUILD.md:21-24`).

This task resolves conflict P6 host-side with zero ROM reads:
1. **Root Cause Confirmed**: In CHDK-PORT-1G, the witness inspector was developed against the initial pre-correction prototype (`boot_witness` at `0x0035F780`). In PR #2 (`SD1stInit`), Thumb-2 instructions were added to `boot_prototype.c` and stubs to `stubs_prototype.S`, expanding `.text` and pushing `.data` forward by exactly 32 bytes (`+0x20`), relocating `boot_witness` to `0x0035F7A0`. In PORT-16, candidate build tooling was updated to emit aligned artifacts directly to `candidate_port2a/` with `0x0035F7A0`, while historical artifacts under `firmware/tools/` were left at `0x0035F780`.
2. **VERIFIED Candidate Address**: Directly queried from the candidate built by `tools/build_candidate_port2a.py` using `arm-none-eabi-nm` and `arm-none-eabi-readelf`:
   - `candidate_port2a/candidate_main.elf`: `0035f7a0 D boot_witness` (Section 3 `.data`, Type `D`, Size 32 B / `0x20`, 16-byte aligned).
   - `candidate_port2a/witness_inspector_metadata.json`: `"witness_address": "0x0035F7A0"`, `"witness_address_int": 3536800`.
   - `candidate_port2a/witness_inspector_payload.bin`: MOVW/MOVT opcodes decode to `0x0035F7A0`.
3. **Inspector Tooling Fixes (`tools/build_witness_inspector.py`, `tools/validate_witness_inspector.py`)**:
   - `tools/build_witness_inspector.py`: Pinned `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`. Enforces `witness_addr == expected_addr`, raising `ValueError` on any mismatch (hard error, never silently accepted). Output defaults to `candidate_port2a/` to protect `firmware/tools/` from being overwritten.
   - `tools/validate_witness_inspector.py`: Pinned `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`. Resolves candidate inspector artifacts from `candidate_port2a/` by default. Strictly checks that payload binary MOVW/MOVT, ELF symbol, and address metadata all equal `0x0035F7A0`, raising `AssertionError` if `0x0035F780` or any other mismatched address is encountered.
4. **Preflight Tool Integration (`tools/port18_trial_preflight.py`)**:
   - `EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0` was already pinned (line 49).
   - Added optional `--inspector-metadata` / `--metadata` and `--inspector-bin` checks to verify candidate inspector alignment against the pinned witness address `0x0035F7A0`, failing closed with exit code 1 if mismatched (e.g. `0x0035F780`).
   - Fix (b): When `witness_address` is missing in inspector metadata, reports a clean `FAIL` without crashing (safe f-string formatting).
   - Fix (c): In inspector payload check, uses `payload_addr is not None` rather than truthiness when selecting the reason text.
5. **Regression & Coherence Test Suites**:
   - `tests/test_port19_witness_address.py`: 8 unit tests asserting tripartite agreement across the candidate build, inspector, and preflight tool on `boot_witness = 0x0035F7A0`, and verifying hard-error rejection if `0x0035F780` is reintroduced.
   - Fix (a): `tests/test_validate_witness_inspector.py::test_simulated_symbol_address_change_and_linker_output` asserts that the pinned default `EXPECTED_BOOT_WITNESS_ADDR` rejects a simulated ELF with `boot_witness` at `0x00358B10` (`ValueError`), and then verifies dynamic address resolution by passing `expected_witness_addr=sim_witness_addr` explicitly.
   - `tests/test_port18_trial_preflight.py`: Added comprehensive unit tests for `--inspector-metadata` and `--inspector-bin`, verifying clean FAIL on missing fields or corrupted opcodes.

---

## 2. Comprehensive Inventory of Former `0x0035F780` Uses

The address `0x0035F780` appears across 18 files in the repository. The complete file:line inventory and context for each occurrence is detailed below.

### 2.1 Witness Inspector Tooling and Inspector Tests

| File Path | Line(s) | Exact Text / Context | Nature of Use & Resolution |
|:---|:---:|:---|:---|
| `firmware/tools/witness_inspector_metadata.json` | 4–5 | `"witness_address": "0x0035F780",\n  "witness_address_int": 3536768` | **Historical pre-correction metadata** generated in CHDK-PORT-1G.2. Preserved as historical baseline under `firmware/tools/`. Candidate builds regenerate aligned metadata in `candidate_port2a/` @ `0x0035F7A0`. `validate_witness_inspector.py` and preflight tool reject this file fail-closed with exit code 1. |
| `firmware/tools/witness_inspector_payload.bin` | 0x0A..0x11 | MOVW `0xF780`, MOVT `0x0035` | **Historical pre-correction payload binary**. Preserved as historical baseline. Candidate builds regenerate aligned payload in `candidate_port2a/` @ `0x0035F7A0`. Rejected fail-closed by validator and preflight tool. |
| `tests/test_validate_witness_inspector.py` | 54 | `# Dynamically check the derived symbol address rather than historical pre-correction 0x0035F780` | **Documentation comment** explaining removal of hardcoded address in dynamic inspector test. |
| `tests/test_port16_validator_witness.py` | 9, 19, 53, 268, 273, 370, 378, 383, 391, 571, 575, 581, 605, 606, 615, 633, 635, 642 | MOCK_NM_HISTORICAL_WITNESS_0035F780 and assertions verifying rejection of 0x0035F780 in candidate symbols, manifest, and payload | **Negative test suite**: tests fail-closed rejection of stale `0x0035F780` artifacts. |
| `tests/test_port16_pipeline_witness.py` | 159, 359, 365, 380, 384, 392, 405, 490, 499, 507, 520, 548, 560 | Negative test assertions verifying candidate builder and validator reject stale 0x0035F780 in symbols, metadata, and inspector payload | **Negative test suite**: tests that candidate builder rejects stale 0x0035F780. |

### 2.2 Preflight Tool and Preflight Tests

| File Path | Line(s) | Exact Text / Context | Nature of Use & Resolution |
|:---|:---:|:---|:---|
| `tools/port18_trial_preflight.py` | 46 | `# - Historical pre-correction candidate: 0x0035F780` | **Documentation comment** contrasting historical pre-correction address against pinned `EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0` (line 49). |
| `tests/fixtures/port18/preflight/wrong_witness.map` | 1–2 | `.data          0x0035f780       0x20 /path/to/boot_prototype.o\n                0x0035f780                boot_witness` | **Negative test fixture**: linker map fixture used by preflight tests to verify that `0x0035F780` fails. |
| `tests/test_port18_trial_preflight.py` | 133, 149 | `"""Linker map with stale/wrong boot_witness (0x0035F780) fails with exit code 1."""\n...\nself.assertEqual(bw_check["actual"], "0x0035F780")` | **Negative test definition & assertion**: preflight tool rejects `wrong_witness.map`. |
| `tests/test_port18_trial_preflight.py` | 576, 583, 598, 600 | `"""nm with conflicting boot_witness (global wrong 0x0035F780, local right 0x0035F7A0) fails."""\n...\n"0035f780 D boot_witness\n"\n...\nself.assertEqual(bw_check["actual"], ["0x0035F780", "0x0035F7A0"])` | **Negative test definition & assertion**: conflicting symbols. |
| `tests/test_port18_trial_preflight.py` | 608, 616, 630, 633 | `"""nm with conflicting boot_witness in reverse order (global right 0x0035F7A0, local wrong 0x0035F780) fails."""\n...\n"0035f780 d boot_witness\n"\n...\nself.assertEqual(bw_check["actual"], ["0x0035F7A0", "0x0035F780"])` | **Negative test definition & assertion**: conflicting symbols. |

### 2.3 Documentation Files

| File Path | Line(s) | Context / Citation |
|:---|:---:|:---|
| `docs/PORT18_OWNER_TRIAL_PLAN.md` | 128 | **Precondition P6**: Records blocking conflict between tracked inspector metadata (`0x0035F780`) and pinned candidate witness (`0x0035F7A0`). |
| `docs/PORT18_OWNER_TRIAL_PLAN.md` | 169 | `(historical note: docs/CHDK_PORT2A_CANDIDATE_INTEGRATION.md:58-69 recorded the pre-PORT-16 historical address 0x0035F780)` |
| `docs/PORT16_WITNESS_ADDRESS.md` | 13, 17, 31, 40-75, 105, 111, etc. | Comprehensive root cause analysis of `boot_witness` relocation from `0x0035F780` to `0x0035F7A0` caused by PR #2 (+32 bytes in `.text`). |
| `docs/PORT16_CANDIDATE_BUILD.md` | 23, 126, 164, 248 | Documents discrepancy between tracked metadata (`firmware/tools/`) and rebuilt candidate metadata (`candidate_port2a/`). |
| `docs/PORT16_OWNER_TRIAL_PLAN.md` | 158 | Historical note on `0x0035F780` baseline. |
| `docs/PORT16_PIPELINE_FIX.md` | 10, 48, 120 | Documents migration from `0x0035F780` to `0x0035F7A0`. |
| `docs/PORT16_VALIDATOR_FIX.md` | 12, 45 | Documents validator update enforcing `0x0035F7A0`. |
| `docs/PORT3C_RESTART_READINESS_MATRIX.md` | 231 | Historical audit matrix noting prototype ELF @ `0x0035F7A0` vs preserved pre-correction candidate @ `0x0035F780`. |
| `docs/CHDK_PORT1G_INSPECTOR_IMPLEMENTATION.md` | 39, 55 | Initial witness inspector design targeting `0x0035F780`. |
| `docs/CHDK_PORT1G_FINAL_REVIEW_BUNDLE.md` | 17 | Review bundle citing `0x0035F780` target. |
| `docs/CHDK_PORT1G_CACHE_READOUT.md` | 15, 17, 61, 62, 66, 67 | Cache analysis citing `0x0035F780`. |
| `docs/CHDK_PORT1F1_REVIEW_BUNDLE.md` | 10, 18 | Placement proof for initial `0x0035F780`. |
| `docs/CHDK_PORT1F2_FINAL_EVIDENCE.md` | 12, 27, 31, 38 | Final evidence citing `0x0035F780`. |
| `docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md` | 103, 125, 127 | MPU region mapping for `0x0035F780`. |
| `docs/CHDK_PORT1F2_REMEDIATION.md` | 19 | Remediation audit for `0x0035F780`. |
| `docs/CHDK_PORT2A_CANDIDATE_INTEGRATION.md` | 62, 70, 155, 235 | Historical candidate integration referencing `0x0035F780`. |

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
4. **Output Directory Isolation**: Default output paths now target `candidate_port2a/` (`PAYLOAD_O`, `PAYLOAD_BIN`, `LOADER_SCRIPT`, `METADATA_JSON`). This guarantees that running `build_witness_inspector.py` does not modify tracked historical files under `firmware/tools/`.
5. **CLI Support**: Added `--expected-addr` option defaulting to `0x0035F7A0`.

### 4.2 Inspector Validator (`tools/validate_witness_inspector.py`)
1. **Pinned Constant**: Defined `EXPECTED_BOOT_WITNESS_ADDR = 0x0035F7A0`.
2. **Candidate Artifact Resolution**: Defined `CANDIDATE_DIR = candidate_port2a`. Defaults to candidate inspector payload, object, and metadata in `candidate_port2a/` when available.
3. **Hard-Error Address Invariants**: In `validate_payload_binary`:
   - Rejects binary payload if decoded address does not equal `expected_witness_addr` (`AssertionError`).
   - Rejects candidate ELF if symbol does not equal `expected_witness_addr` (`AssertionError`).
   - Rejects address metadata if target does not equal `expected_witness_addr` (`AssertionError`).
   - Enforces default `expected_witness_addr = EXPECTED_BOOT_WITNESS_ADDR` (`0x0035F7A0`).
4. **CLI Option**: Added `--expected-addr` defaulting to `0x0035F7A0`.

### 4.3 Preflight Verification Tool (`tools/port18_trial_preflight.py`)
1. **Existing Verification**: `EXPECTED_BOOT_WITNESS_ADDR: int = 0x0035F7A0` was already pinned (line 49), and linker map / symbol parsing already rejected `0x0035F780` with status `FAIL` and exit code 1.
2. **Inspector Alignment Verification**: Added optional CLI flags `--inspector-metadata` (or `--metadata`) and `--inspector-bin`:
   - Decodes and validates that the inspector metadata JSON and/or payload binary target `0x0035F7A0`.
   - Any mismatch (such as historical `firmware/tools/witness_inspector_metadata.json` pointing to `0x0035F780`) records a check status `FAIL` and causes preflight to exit non-zero (exit code 1).
3. **Fix (b) - Clean FAIL on Missing Metadata Field**: If `witness_address` is missing in metadata JSON, `meta_addr` is `None` and `meta_err` notes the missing field. The tool reports a clean `FAIL` without evaluating `0x{meta_addr:08X}` on `None`, preventing `TypeError` formatting exceptions.
4. **Fix (c) - Explicit None-Check on Payload Address**: The payload decoder check uses `elif payload_addr is not None:` rather than truthiness when selecting the diagnostic reason text.

### 4.4 Dynamic Inspector Resolution Test Fix (a)
In `tests/test_validate_witness_inspector.py::test_simulated_symbol_address_change_and_linker_output`:
- The test proves dynamic symbol address resolution by compiling a simulated ELF (`elf_sim`) with `boot_witness` at `0x00358B10`.
- Calling `bwi.build_witness_inspector` with the default pinned expectation (`0x0035F7A0`) now asserts that a `ValueError` is raised (`address mismatch`).
- The test then explicitly passes `expected_witness_addr=sim_witness_addr` to build and validate the inspector dynamically, preserving the test's purpose while maintaining strict pinned defaults in production tooling.

---

## 5. Verification Test Suite Results

All unit and integration test suites pass with exit code 0:

### 5.1 `tests/test_port19_witness_address.py`
Command:
```bash
python3 -B -m unittest tests/test_port19_witness_address.py -v
```
Verbatim Output:
```text
test_built_candidate_manifest (tests.test_port19_witness_address.TestPort19WitnessAddress.test_built_candidate_manifest)
candidate_manifest.json specifies boot_witness_addr = 0x0035F7A0. ... ok
test_built_candidate_symbol_table (tests.test_port19_witness_address.TestPort19WitnessAddress.test_built_candidate_symbol_table)
Built candidate ELF symbol table defines boot_witness = 0x0035F7A0. ... ok
test_candidate_inspector_artifacts (tests.test_port19_witness_address.TestPort19WitnessAddress.test_candidate_inspector_artifacts)
candidate_port2a inspector metadata and binary target 0x0035F7A0. ... ok
test_inspector_builder_rejects_0035f780_symbol_table (tests.test_port19_witness_address.TestPort19WitnessAddress.test_inspector_builder_rejects_0035f780_symbol_table)
Inspector builder extract_witness_addr_from_elf rejects 0x0035F780 with ValueError. ... ok
test_inspector_validator_rejects_0035f780 (tests.test_port19_witness_address.TestPort19WitnessAddress.test_inspector_validator_rejects_0035f780)
Inspector validator fails closed when encountering 0x0035F780 in metadata or payload. ... ok
test_pinned_constants_coherence (tests.test_port19_witness_address.TestPort19WitnessAddress.test_pinned_constants_coherence)
All tools define EXPECTED_BOOT_WITNESS_ADDR as 0x0035F7A0, never 0x0035F780. ... ok
test_preflight_tool_passes_candidate_and_rejects_0035f780 (tests.test_port19_witness_address.TestPort19WitnessAddress.test_preflight_tool_passes_candidate_and_rejects_0035f780)
Preflight tool accepts 0x0035F7A0 candidate symbols and rejects 0x0035F780 with exit 1. ... ok
test_tripartite_witness_address_agreement (tests.test_port19_witness_address.TestPort19WitnessAddress.test_tripartite_witness_address_agreement)
Inspector, preflight tool, and built candidate strictly agree on 0x0035F7A0. ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.053s

OK
```
`[VERIFIED: test execution]`

### 5.2 Witness Tests (`witness_tests`)
Command:
```bash
python3 -B -m unittest discover -s tests -p "test_validate_witness*.py"
```
Ran 13 tests: all 13 passed cleanly (`OK`).
`[VERIFIED: test execution]`

### 5.3 Candidate Validator (`candidate_validate`)
Command:
```bash
python3 -B tools/validate_candidate_port2a.py
```
All 7 validation suites passed cleanly (`OK`).
`[VERIFIED: test execution]`

### 5.4 Preflight Tests (`test_port18_trial_preflight.py`)
Command:
```bash
python3 -B -m unittest tests/test_port18_trial_preflight.py
```
Ran 38 tests: all 38 passed cleanly (`OK`).
`[VERIFIED: test execution]`

---

## 6. Integration Invariance & Safety Compliance

- **Candidate Source & Builder Invariance**: Neither `chdk-port/platform/g3x/sub/110c/boot_prototype.c` nor `tools/build_candidate_port2a.py` was altered.
- **Allowed Scope Conformance**: Only permitted paths were modified or added:
  - `docs/PORT19_WITNESS_ADDRESS.md`
  - `tests/test_port19_witness_address.py`
  - `tests/test_validate_witness_inspector.py`
  - `tests/test_port18_trial_preflight.py`
  - `tools/build_witness_inspector.py`
  - `tools/validate_witness_inspector.py`
  - `tools/port18_trial_preflight.py`
- **Zero ROM Reads**: The resolution was completed entirely host-side using the local toolchain and candidate build artifacts. No firmware ROM files were read or probed.
- **Git Hygiene**: No binaries or build outputs (`candidate_port2a/`) are tracked or committed. Working tree is clean.
- **Trial Plan Status**: Precondition P6 is fully resolved. The inspector, preflight tool, and candidate build agree on `boot_witness = 0x0035F7A0`.
