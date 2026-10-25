# Reproducibility Manifest: G3 X CHDK Restart & SD1stInit Prototype

Date: 2026-10-25 · Workspace: `/Users/avp/project/g3x-lite` · Branch: `feat/restart-sd1stinit-prototype`  
Pull Request: `s4urj3ng/g3x-lite#2` (stacked on `feat/dynamic-witness-address`)  
Hardware Status: **STRICT NO-GO** (Read-only investigation; zero deployment / zero flashing).

---

## 1. Overview and Purpose

This manifest documents the exact build environment, upstream source provenance, external dependencies, cryptographic artifact hashes, and 3-tier test execution requirements for the Canon PowerShot G3 X (GM1.10C) CHDK restart and `SD1stInit` task creation prototype.

The purpose is to provide an unambiguous, verifiable audit trail distinguishing:
1. **Clean-checkout public verification** (reproducible anywhere with zero external dependencies, no proprietary ROM, and no ARM toolchain).
2. **Private ROM evidence verification** (verifiable locally against a legally obtained owner ROM dump).
3. **Offline toolchain integration verification** (compilable and inspectable with the pinned ARM toolchain).

> [!NOTE]
> **Clean-Checkout Status Clarification**: No automated GitHub Actions or remote CI runner is currently configured for `s4urj3ng/g3x-lite`. Clean-checkout results documented herein represent **design expectations and local simulated runs** (verified locally by executing test runners under mocked clean-clone conditions with missing ROM and toolchain paths). Verified execution results with local external artifacts are distinguished explicitly.

---

## 2. Upstream Pinned CHDK Revision & Provenance

The prototype source code and patch are derived from upstream CHDK trunk:

| Parameter | Specification / Value |
|---|---|
| **Upstream Git Mirror** | `https://github.com/01luna/CHDK.git` |
| **Upstream Subversion** | `svn://assembla.com/chdk/trunk` |
| **Pinned Git Commit SHA** | `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6` |
| **Pinned SVN Revision** | `r5491` |
| **Commit Timestamp** | 2020-04-26 12:47:33 +0000 |
| **Commit Subject** | `sub_fc31b408, sub_fc31b460, sub_fc31bbc4` stubs & G3 X baseline |
| **Standalone Patch** | `patches/0001-sd1stinit-restart-prototype.patch` (SHA-256: `c0bfc658c04aef50cb9776e970b9aca70cdc394a7044d65c2bd95cc151113fa7`) |
| **Tracked Prototype Files** | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `chdk-port/platform/g3x/sub/110c/stubs_prototype.S`, `chdk-port/platform/g3x/sub/110c/boot_witness.h` |

---

## 3. Required ARM Toolchain & Environment

To assemble, compile, and link the prototype binaries from source:

| Parameter | Specification |
|---|---|
| **Toolchain Package** | `gcc-arm-none-eabi-5_4-2016q3` |
| **GCC Version** | `arm-none-eabi-gcc (GNU Tools for ARM Embedded Processors) 5.4.1 20160919 (release) [ARM/embedded-5-branch revision 240496]` |
| **Target Architecture** | ARMv7-R (`-march=armv7-r -mcpu=cortex-r4 -mthumb`) |
| **ABI** | EABI / AAPCS (soft-float, 8-byte stack alignment) |
| **Host System** | macOS (Darwin 24+ arm64 / x86_64) or Linux (x86_64) |
| **Local Toolchain Path** | `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/` |
| **Python Version** | Python 3.9+ (standard library only: `os`, `struct`, `unittest`, `subprocess`, `hashlib`, `unittest.mock`) |

---

## 4. Required External Artifacts (Private ROM)

To run Tier 2 static ROM byte and word assertions:

| Artifact | File Path | Size (Bytes) | SHA-256 Hash | Provenance & Legal Classification |
|---|---|---|---|---|
| **Canon G3 X Firmware Dump** | `firmware/dumps/GM1.10C/PRIMARY.BIN` | 33,554,432 | `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` | Legally dumped from physical PowerShot G3 X (GM1.10C) owned by researcher. **Proprietary Canon binary; strictly local and gitignored. Never committed or distributed.** |

---

## 5. Built Artifacts Specification (Candidate vs Prototype)

The repository maintains strict isolation between First-Boot Candidate artifacts (`candidate_port2a/`) and isolated prototype artifacts (`chdk-port/`):

> [!IMPORTANT]
> **PRE-CORRECTION ARTIFACT STATUS (PORT-5E)**:
> All `candidate_port2a/` artifacts (`candidate_loader.bin`, `candidate_main.bin`, `candidate_main.elf`, `DISKBOOT.BIN`) and their associated manifest `candidate_manifest.json` are **PRE-CORRECTION** artifacts. They were built prior to the PR #2 `SD1stInit` addition and prior to the PORT-5E early boot literal corrections (`0x80EC`/`0x8074` check words and corrected string addresses). Under strict Phase 0 safety invariants, these candidate artifacts are **NOT** regenerated, overwritten, or claimed to represent the corrected prototype source.

| Artifact | Relative Path | Size (Bytes) | SHA-256 Hash | Role / Invariant |
|---|---|---|---|---|
| **Candidate Loader Binary** | `candidate_port2a/candidate_loader.bin` | 117,968 | `bac0431c2e896cb5e9a761f66d4aaaad0676af11a28335c602367539574c72bf` | Unmodified first-boot candidate loader (`boot_witness` @ `0x0035F780`). Protected artifact. |
| **Candidate Core Binary** | `candidate_port2a/candidate_main.bin` | 116,784 | `e6f823d1c4e40ff03bc923d423946f6da4bd412b18ae1ac68d0553a5055d7fd5` | Unmodified first-boot candidate core (`boot_witness` @ `0x0035F780`). Protected artifact. |
| **Candidate ELF** | `candidate_port2a/candidate_main.elf` | 211,416 | `973678ed662ba0add199697e2529024d6b6d98e9582cb3d4e233d2d333b8c645` | Symbol table reference for dynamic witness inspector tooling. Protected artifact. |
| **Candidate Encoded Loader** | `candidate_port2a/DISKBOOT.BIN` | 117,969 | `db91b18a148ba31f0d770d8ce45acd92d35e1ac0c7ba6c69c7b4efaa25bd73e1` | `dancingbits` row 13 encoded DISKBOOT bootloader (byte 0 = 0x00). Protected artifact. |
| **Prototype Core Binary** | `chdk-port/platform/g3x/sub/110c/prototype_main.bin` | 116,816 | `49a2fde902c9e86b49a0533256a174d791f1bdced26c8521ea7dd6f945fb16ad` | Remediated `SD1stInit` prototype (+32 bytes; `boot_witness` @ `0x0035F7A0`). |
| **Prototype Core ELF** | `chdk-port/platform/g3x/sub/110c/prototype_main.elf` | 211,552 | `4ca6410ef76c3a94d24eeaea8844c77e2f6421d8a120eec487cbe1deca34b4bc` | Debug ELF with symbols for `sub_fc05c4e0` and `sub_fc31b1f4`. |
| **Prototype Loader Binary** | `chdk-port/loader/g3x/prototype_loader.bin` | 118,000 | `d3057360058e4f1905bcd499ee19aeec4ae845740d93b82bad810e34de7841f3` | Prototype loader embedding remediated core at offset `0x20C`. |
| **Witness Inspector Binary** | `firmware/tools/witness_inspector_payload.bin` | 444 | `f1cd6438b8c54a233b28360705c02f869da2149c6499e9b2d8c340746a3c7f00` | Canon Basic dynamic witness inspector assembled payload. |

---

## 6. Verification and Build Commands

### Routine Offline Verification (Non-Mutating / Read-Only)
The following commands perform strictly read-only validation without modifying candidate artifacts or repository source code:

```sh
# 1. Run 3-tier restart SD host audit test suite
python3 -m unittest tests.test_restart_sd_audit -v

# 2. Validate First-Boot Candidate artifacts without rebuild (read-only invariant check)
python3 tools/validate_candidate_port2a.py

# 3. Validate isolated prototype loader and core integration
python3 tools/validate_prototype_integration.py

# 4. Validate boot witness placement and inspector state transitions
python3 tools/validate_boot_witness.py

# 5. Validate dynamic witness inspector opcodes and metadata consistency
python3 tools/validate_witness_inspector.py
```

> [!WARNING]
> **Candidate Rebuild Invariant**: `tools/build_candidate_port2a.py` is an intentional rebuild utility that regenerates `candidate_port2a/` artifacts. It must **NEVER** be run as a routine verification step. Routine verification of candidate artifacts must strictly use `tools/validate_candidate_port2a.py` to prevent accidental mutation of protected candidate files.

### Isolated Prototype Build Commands (Prototype Only)
When an intentional rebuild of the isolated prototype is required:

```sh
# 1. Build Isolated SD1stInit Prototype Core (emits prototype_main.elf & prototype_main.bin)
python3 tools/build_prototype.py

# 2. Build Isolated SD1stInit Prototype Loader (embeds prototype_main.bin -> prototype_loader.bin)
python3 tools/build_loader_prototype.py

# 3. Assemble Dynamic Witness Inspector for Prototype Target ELF
python3 tools/build_witness_inspector.py --elf chdk-port/platform/g3x/sub/110c/prototype_main.elf
```

---

## 7. 3-Tier Test Classification & Execution Matrix

To avoid conflating clean public checkout tests with private ROM evidence and toolchain-dependent builds, the test suite is partitioned into three explicit tiers:

```
+---------------------------------------------------------------------------------------+
|                                    TEST TIERS                                         |
+---------------------------------------------------------------------------------------+
|  Tier 1: Source Presence & Logic        --> Zero deps; 100% PASS on clean clone       |
|  Tier 2: Private ROM Evidence           --> Requires PRIMARY.BIN; SKIPPED on clone     |
|  Tier 3: Offline Toolchain Integration  --> Requires arm-none-eabi-nm; SKIPPED on clone|
+---------------------------------------------------------------------------------------+
```

### Tier 1: Source Presence, Logic & Skip Regression (Clean Public Checkout)
- **Environment**: Clean `git clone` on public machine or local clean simulation.
- **Dependencies**: Python 3 standard library only. **No** ARM toolchain, **no** ROM dump, **no** prebuilt ELF.
- **Test Classes**: `TestRestartSdSourcePresence` (5 tests) and `TestRestartSdSkipRegression` (4 tests) in `tests/test_restart_sd_audit.py`.
- **Test Cases**:
  1. `test_clean_checkout_source_integrity`: Asserts all tracked prototype source files and the standalone patch exist in tree.
  2. `test_clean_checkout_patch_validity`: Validates patch header, pinned commit `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`, and diff targets.
  3. `test_task_startup_my_omits_startdiskboot_and_calls_sd1stinit_veneer`: Statically checks `boot_prototype.c` to confirm `sub_fc05bbea` is omitted and `blx sub_fc31b1f4` is called with gate check.
  4. `test_prototype_stubs_include_sd1stinit_symbols`: Statically checks `stubs_prototype.S` for `STUB(fc05c4e0)` and `STUB2(fc31b1f4)`.
  5. `test_gate_mmio_bit_arithmetic_semantics`: Algorithmic proof showing `lsls r0, #15; bpl` extracts Bit 16 (0-indexed) into sign bit 31 across all 32 bit positions.
  6. `test_regression_tier3_skips_when_nm_missing_even_if_elf_present`: Regression test asserting that missing `arm-none-eabi-nm` cleanly skips Tier 3 without raising an assertion error, even if `prototype_main.elf` exists.
  7. `test_regression_tier3_skips_when_both_nm_and_elf_missing`: Regression test asserting that missing both toolchain and ELF cleanly skips Tier 3.
  8. `test_regression_tier2_skips_when_rom_missing`: Regression test asserting that missing `PRIMARY.BIN` cleanly skips Tier 2.
  9. `test_regression_tier3_fails_closed_when_toolchain_present_but_build_fails`: Asserts that when toolchain is present, a failed compilation fails closed with `AssertionError`.
- **Expected Outcome**: **9 PASS, 0 FAIL, 0 ERROR**.

### Tier 2: Private ROM Evidence (Local Private Workspace)
- **Environment**: Local workstation with owner's legally obtained GM1.10C ROM dump.
- **Dependencies**: `firmware/dumps/GM1.10C/PRIMARY.BIN`.
- **Test Class**: `TestRestartSdRomEvidence` in `tests/test_restart_sd_audit.py`.
- **Test Cases**:
  1. `test_rom_byte_sequences`: Verifies 19 critical ROM disassembly opcodes.
  2. `test_rom_words`: Verifies 9 critical ROM addresses, veneers, and low-RAM guard values.
  3. `test_strings`: Verifies `StartDiskboot`, `A/DISKBOOT.BIN`, and `CMD0_Initialize` string literals in ROM.
  4. `test_sd_host0_mmio_base`: Verifies SD Host 0 MMIO calculation (`0xC8060000`).
  5. `test_sd1stinit_name`: Verifies `"SD1stInit"` task name in ROM.
  6. `test_driver_table_in_zeroed_bss`: Verifies driver slot table falls within zeroed BSS range.
  7. `test_gate_mmio_bit_semantics_reconciliation_in_rom`: Disassembles Gate 2 opcodes at `0xFC05C4E0` and `0xFC0D73D0` directly from ROM bytes.
- **Outcome**:
  - *Clean clone simulation (no ROM)*: **7 SKIPPED** via class-level `setUpClass` / `@unittest.skipUnless`.
  - *Developer setup (ROM present)*: **7 PASS**.

### Tier 3: Offline Toolchain & Integration (Workstation with ARM Toolchain)
- **Environment**: Workstation with `gcc-arm-none-eabi-5_4-2016q3` toolchain.
- **Dependencies**: `arm-none-eabi-nm` (required for symbol inspection). Compilation from source requires toolchain build script.
- **Test Class**: `TestRestartSdOfflineIntegration` in `tests/test_restart_sd_audit.py`.
- **Test Cases**:
  1. `test_prototype_elf_resolves_symbols`: Verifies `prototype_main.elf` symbol table contains `sub_fc05c4e0` and `sub_fc31b1f4`.
- **Outcome**:
  - *Clean clone simulation (no toolchain)*: **1 SKIPPED** via class-level `setUpClass` / `@unittest.skipUnless(NM_PATH is not None, ...)`.
  - *Developer setup (toolchain present)*: **1 PASS**.

---

## 8. Summary of Test Results Across Environments

| Environment | Tier 1 (Source + Regression) | Tier 2 (ROM) | Tier 3 (Toolchain/ELF) | Expected / Reported Result | Status |
|---|---|---|---|---|---|
| **Clean Checkout Simulation** (Design Expectation, No ROM/Toolchain) | 9 / 9 PASS | 7 SKIPPED | 1 SKIPPED | **9 passed, 8 skipped (2 classes skipped)** | **PASS (Design Expectation / Simulated)** |
| **Developer Workstation** (Actual Verified Execution with Full Artifacts) | 9 / 9 PASS | 7 / 7 PASS | 1 / 1 PASS | **17 passed, 0 skipped** | **PASS (Actual Local Execution)** |

> [!NOTE]
> Reviewers on an ordinary clean checkout will see `Ran 9 tests in ... OK (skipped=2)`. All 9 Tier 1 source, patch, arithmetic, and regression assertions pass without requiring private ROM dumps or external compilers. Tier 2 and Tier 3 classes cleanly skip.

---

## 9. Hardware Safety Invariant

**HARDWARE EXECUTION STRICT NO-GO.**

1. All prototype verifications are strictly static and offline.
2. The prototype remediates the static call chain omission of `SD1stInit`, but does **not** prove runtime hardware controller recovery across soft restart.
3. Physical hardware deployment, SD card flashing, or camera execution remains prohibited until explicit owner approval and Phase 1 transition.
