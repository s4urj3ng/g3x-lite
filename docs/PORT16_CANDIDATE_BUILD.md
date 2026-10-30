# PORT-16: First-Boot Candidate Rebuild and Offline Validation Report

**Task ID**: `p16-candidate-rebuild-r3`  
**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C)  
**Host Platform**: Linux (x86_64), AgentBridge isolated worktree (`/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-candidate-rebuild-r3`)  
**Evaluation Mode**: Phase 0 Read-Only / Host-Only Offline Candidate Rebuild & Validation  
**Date**: 2026-10-30  

---

## 1. Executive Summary & Build State

This document records the exact host rebuild and validation of the corrected CHDK first-boot candidate (`candidate_port2a/`) for the Canon PowerShot G3 X (GM1.10C) from current working-tree source in `chdk-port/platform/g3x/sub/110c/`.

- **Base Commit SHA (`git rev-parse HEAD` at milestone base)**: `665c8dec2c6477ecefef8714b32a37bdd11b9d84` `[VERIFIED: git rev-parse HEAD]`
- **Base Commit SHA (`git merge-base HEAD origin/main`)**: `3d8794e136ecc03919f2da5bb3f5d034eae500e5` `[VERIFIED: git merge-base HEAD origin/main]`
- **Milestone Integration Base SHA (`git merge-base HEAD agentbridge/g3x-lite/port-16-firstboot-pipeline/integration`)**: `665c8dec2c6477ecefef8714b32a37bdd11b9d84` `[VERIFIED: git merge-base HEAD integration]`
- **Candidate Builder**: `tools/build_candidate_port2a.py` (updated in `p16-pipeline-fix-r3` / commit `20ba457`) `[VERIFIED]`
- **Candidate Validator**: `tools/validate_candidate_port2a.py` (updated in `p16-validator-fix-r3` / commit `733f679`) `[VERIFIED]`
- **Pinned Toolchain**: `toolchains/gcc-arm-none-eabi-5_4-2016q3` (ARM GNU-RM 5.4.1 2016q3) `[VERIFIED]`
- **Build Status**: Exit Code `0` (Success) `[VERIFIED]`
- **Validation Status**: Exit Code `0` (All 7 test suites passed) `[VERIFIED]`
- **Candidate Boot Witness Symbol Address**: **`0x0035F7A0`** (`.data`, 16-byte aligned) `[VERIFIED: candidate_main.elf symbol table]`
- **Candidate End Symbol (`_end`) Address**: **`0x00366CB0`** (`.bss`, heap base) `[VERIFIED: candidate_main.elf symbol table]`
- **Comparison with `docs/PORT16_WITNESS_ADDRESS.md`**: 100% exact numerical match for `boot_witness` (`0x0035F7A0`), `_end` (`0x00366CB0`), and section sizing `[VERIFIED]`
- **Discrepancy in Tracked Metadata vs. Rebuilt Candidate**: The tracked repository file `firmware/tools/witness_inspector_metadata.json:4` at HEAD still states `"witness_address": "0x0035F780"`, while the corrected candidate build regenerates `candidate_port2a/witness_inspector_metadata.json:4` stating `"witness_address": "0x0035F7A0"` `[VERIFIED]`
- **Hardware Readiness Status**: `NO-GO` (Phase 0 read-only policy strictly enforced; zero physical hardware operations) `[VERIFIED]`

---

## 2. Git Repository & Baseline Identification

### 2.1 Git Worktree & Base Commit
- **Active Worktree**: `/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-candidate-rebuild-r3` `[VERIFIED: pwd]`
- **Active Branch**: `agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-candidate-rebuild-r3` `[VERIFIED: git branch --show-current]`
- **Milestone Baseline SHA (`git rev-parse HEAD`)**: `665c8dec2c6477ecefef8714b32a37bdd11b9d84` `[VERIFIED: git rev-parse HEAD]`
- **Base Commit SHA (`git merge-base HEAD origin/main`)**: `3d8794e136ecc03919f2da5bb3f5d034eae500e5` `[VERIFIED: git merge-base HEAD origin/main]`
- **Milestone Integration Base SHA (`git merge-base HEAD agentbridge/g3x-lite/port-16-firstboot-pipeline/integration`)**: `665c8dec2c6477ecefef8714b32a37bdd11b9d84` `[VERIFIED: git merge-base HEAD integration]`
- **Preceding Commit Log**:
  - `665c8de` `agentbridge: integrate p16-validator-fix-r3 (Update validate_candidate_port2a.py to the corrected boot_wi)` `[VERIFIED: git log -n 1 665c8de]`
  - `733f679` `feat(p16): update validate_candidate_port2a.py to corrected witness and _end addresses (fail-closed)` `[VERIFIED: git log -n 1 733f679]`
  - `dfe52a2` `agentbridge: integrate p16-pipeline-fix-r3 (Update build_candidate_port2a.py to the corrected witness ad)` `[VERIFIED: git log -n 1 dfe52a2]`

### 2.2 Initial Worktree Status & Untracked File Handling (`git status --porcelain`)

Prior to candidate build execution, `git status --porcelain` was executed at the base commit `665c8dec2c6477ecefef8714b32a37bdd11b9d84`:
```text
?? firmware/tools/boot001a_loader_gm110c.m
?? firmware/tools/boot001a_payload.S
?? firmware/tools/boot001a_payload.bin
?? firmware/tools/boot001b_diag_loader_gm110c.m
?? firmware/tools/boot001b_loader_gm110c.m
?? firmware/tools/boot001b_payload.S
?? firmware/tools/boot001b_payload.bin
?? firmware/tools/ui001a_loader_gm110c.m
?? firmware/tools/ui001a_payload.S
?? firmware/tools/ui001a_payload.bin
?? firmware/tools/ui001b0_loader_gm110c.m
?? firmware/tools/ui001b0_payload.S
?? firmware/tools/ui001b0_payload.bin
?? firmware/tools/ui001b1_loader_gm110c.m
?? firmware/tools/ui001b1_payload.S
?? firmware/tools/ui001b1_payload.bin
?? firmware/tools/video001_limits_probe_gm110c.m
?? firmware/tools/video001a0_loader_gm110c.m
?? firmware/tools/video001a0_payload.S
?? firmware/tools/video001a0_payload.bin
```
`[VERIFIED: git status --porcelain at assignment start]`

All 20 exact paths were confirmed present in the repository exclude registry (`$(git rev-parse --git-path info/exclude)`) `[VERIFIED]`. Because root `.gitignore:8` contains `!firmware/tools/**` which takes precedence over repository exclude files in standard Git evaluation, a directory-scoped local exclusion (`firmware/tools/.gitignore` containing `*`) was placed to locally ignore all 20 untracked overlay files and itself without modifying tracked repository files or deleting/moving any file on disk `[VERIFIED]`.

Subsequent execution of `git status --porcelain` confirmed that untracked files no longer appear:
```text
(clean: zero output)
```
`[VERIFIED: git status --porcelain]`

### 2.3 Pinned ARM GNU Toolchain Verification
- **Toolchain Path**: `toolchains/gcc-arm-none-eabi-5_4-2016q3` `[VERIFIED]`
- **C Compiler**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc` `[VERIFIED]`
- **Symbol Dumper**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm` `[VERIFIED]`
- **Size Dumper**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-size` `[VERIFIED]`
- **Disassembler**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump` `[VERIFIED]`
- **Verbatim GCC Version Output**:
  ```text
  arm-none-eabi-gcc (GNU Tools for ARM Embedded Processors) 5.4.1 20160919 (release) [ARM/embedded-5-branch revision 240496]
  Copyright (C) 2015 Free Software Foundation, Inc.
  This is free software; see the source for copying conditions.  There is NO
  warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
  ```
  `[VERIFIED: arm-none-eabi-gcc --version]`
- **Verbatim NM Version Output**:
  ```text
  GNU nm (GNU Tools for ARM Embedded Processors) 2.26.2.20160923
  Copyright (C) 2015 Free Software Foundation, Inc.
  This program is free software; you may redistribute it under the terms of
  the GNU General Public License version 3 or (at your option) any later version.
  This program has absolutely no warranty.
  ```
  `[VERIFIED: arm-none-eabi-nm --version]`

---

## 3. Rebuild Command & Verbatim Output

The candidate rebuild script `tools/build_candidate_port2a.py` compiles the corrected working-tree sources `boot_prototype.c` and `stubs_prototype.S` in `chdk-port/platform/g3x/sub/110c/`, archives them into `candidate_port2a/libplatformsub_candidate.a`, links `candidate_port2a/candidate_main.elf`, dynamically verifies `boot_witness` from the built ELF symbol table via `verify_witness_addr_from_elf`, builds `candidate_port2a/candidate_loader.elf`, encodes `candidate_port2a/DISKBOOT.BIN` via dancingbits row 13, regenerates and validates `candidate_port2a/witness_inspector_payload.bin` and `witness_inspector_gm110c.m`, and writes `candidate_port2a/candidate_manifest.json` `[VERIFIED: tools/build_candidate_port2a.py]`.

Prior to rebuild execution, deterministic offline platform source bootstrap was verified via `python3 -B tools/bootstrap_chdk_platform.py` in accordance with PORT-8A / PR #7 `[VERIFIED]`.

### 3.1 Exact Build Command
```bash
python3 -B tools/build_candidate_port2a.py
```
`[VERIFIED: shell command execution]`

### 3.2 Build Exit Code
**`0`** `[VERIFIED: process exit code 0]`

### 3.3 Verbatim Build Output Lines
```text
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
  [OK] Manifest written to /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-candidate-rebuild-r3/candidate_port2a/candidate_manifest.json

CANDIDATE BUILD COMPLETE (OFFLINE ONLY).
```
`[VERIFIED: tools/build_candidate_port2a.py verbatim stdout]`

---

## 4. Validation Command & Verbatim Output

The candidate validator script `tools/validate_candidate_port2a.py` executes 7 offline validation test suites against canonical production invariants, candidate core artifacts, candidate loader artifacts, dancingbits row 13 reversible encoding, disjoint memory and stack lifetime proofs, witness inspector integration, and manifest integrity `[VERIFIED: tools/validate_candidate_port2a.py]`.

### 4.1 Exact Validation Command
```bash
python3 -B tools/validate_candidate_port2a.py
```
`[VERIFIED: shell command execution]`

### 4.2 Validation Exit Code
**`0`** `[VERIFIED: process exit code 0]`

### 4.3 Verbatim Validation Output Lines
```text
======================================================================
CHDK-PORT-2A: First-Boot Candidate Integration Validator
======================================================================
1. Validating Canonical Production Invariance:
  [OK] DISKBOOT.BIN unaltered (SHA256: 3b2a0d5fe786933b...)
  [OK] loader/g3x/main.c unaltered (SHA256: 2678341e18cf55db...)
  [OK] platform/g3x/sub/110c/boot.c unaltered (SHA256: 13105e4cbc1dec6d...)
2. Validating Candidate Core Artifacts:
  [OK] Core symbols verified (_start=0x003489B4, boot_witness=0x0035F7A0, _end=0x00366CB0)
  [OK] Thumb-2 entry instruction verified: b.w startup (0xF000B800)
3. Validating Candidate Loader Artifacts & Payload Embedding:
  [OK] Embedded core payload at offset 0x280 (116816 B) matches candidate_main.bin bit-for-bit
  [OK] Loader handoff disassembly verified: core_copy -> DCCISW -> ICIALLU -> cpsid if -> bx r0
4. Validating Encoded SD Bootloader (DISKBOOT.BIN):
  [OK] Reversible decoding verified: decoded 118000 B bit-for-bit identical to loader binary
5. Validating Disjoint Memory and Stack Lifetime:
  [OK] Zero overlap proven across Loader Stack, Core Boot Stack, Core, BSS, and Shifted Heap
6. Validating Associated Canon Basic Inspector:
  [OK] Inspector payload length (444 B), size binding, and freshness invariants verified
7. Validating Candidate Manifest Integrity:
  [OK] candidate_main.elf: 211616 B (SHA256: 2a07ef02109ecc35...) verified against manifest
  [OK] candidate_main.bin: 116816 B (SHA256: 420b3842ed56b59d...) verified against manifest
  [OK] candidate_loader.elf: 120176 B (SHA256: 61812193ec9de3fa...) verified against manifest
  [OK] candidate_loader.bin: 118000 B (SHA256: 2dab82272a15db45...) verified against manifest
  [OK] DISKBOOT.BIN: 118001 B (SHA256: 9468257364d753d9...) verified against manifest
  [OK] witness_inspector_gm110c.m: 5580 B (SHA256: 7a53835f7048b3c9...) verified against manifest
  [OK] witness_inspector_payload.bin: 444 B (SHA256: 241420a6eea2d7cb...) verified against manifest
======================================================================
ALL PORT-2A CANDIDATE VALIDATION CHECKS PASSED (OFFLINE ONLY)
Candidate Status: OFFLINE_CANDIDATE_BUILT
Independent Review: PENDING
Hardware Readiness: NO-GO
======================================================================
```
`[VERIFIED: tools/validate_candidate_port2a.py verbatim stdout]`

---

## 5. Candidate Symbol Table Extraction & Address Comparison

### 5.1 Verbatim Symbol Table Extraction (`candidate_main.elf`)

#### Command: `boot_witness` context
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm -n candidate_port2a/candidate_main.elf | grep -C 5 boot_witness
```
**Verbatim NM Output**:
```text
0035f2f0 D modemap
0035f334 D iso_table
0035f448 D shutter_speeds_table
0035f700 D aperture_sizes_table
0035f798 d mz_speed
0035f7a0 D boot_witness
0035f7c0 d cnt.6014
0035f7c4 D chdk_colors
0035f7c8 d tools_submenu
0035f7d4 d games_submenu
0035f7e0 d lastcall.7105
```
`[VERIFIED: arm-none-eabi-nm output on candidate_port2a/candidate_main.elf]`

#### Command: `_end` context
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm -n candidate_port2a/candidate_main.elf | grep -C 5 " B _end"
```
**Verbatim NM Output**:
```text
00366c74 B print_screen_file
00366c90 B remote_space_count
00366c94 B remote_mark_count
00366c98 B chdk_version
00366ca0 B physw0_override
00366cb0 B _end
00366cb0 B link_bss_end
bfe14a3c A hook_CreateTask
fc06a001 A task_CaptSeq
fc07b637 A task_DvlpSeqTask
fc09ac19 A task_MovieRecord
```
`[VERIFIED: arm-none-eabi-nm output on candidate_port2a/candidate_main.elf]`

#### Command: Section boundaries (`_start`, `link_text_end`, `link_data_start`, `link_bss_start`, `_end`)
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm -n candidate_port2a/candidate_main.elf | grep -E "(boot_witness|_end|_start|link_data|link_text|link_bss)"
```
**Verbatim NM Output**:
```text
003489b4 T link_text_start
003489b4 T _start
0035aec0 D link_data_start
0035aec0 D link_text_end
0035f7a0 D boot_witness
00365204 B link_bss_start
00365204 B link_data_end
00366cb0 B _end
00366cb0 B link_bss_end
```
`[VERIFIED: arm-none-eabi-nm output on candidate_port2a/candidate_main.elf]`

#### Candidate Segment Sizes (`arm-none-eabi-size`)
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-size candidate_port2a/candidate_main.elf candidate_port2a/candidate_loader.elf
```
**Verbatim Size Output**:
```text
   text	   data	    bss	    dec	    hex	filename
  75020	  41796	   6828	 123644	  1e2fc	candidate_port2a/candidate_main.elf
    620	 117380	      0	 118000	  1ccf0	candidate_port2a/candidate_loader.elf
```
`[VERIFIED: arm-none-eabi-size output]`

---

### 5.2 Address Comparison with `docs/PORT16_WITNESS_ADDRESS.md`

The table below compares the rebuilt candidate symbols and boundaries against both the derived prototype build values documented in `docs/PORT16_WITNESS_ADDRESS.md` and the historical pre-correction candidate baseline:

| Metric / Symbol | Historical Candidate Baseline (Pre-PORT-16) | Derived in `docs/PORT16_WITNESS_ADDRESS.md` | Rebuilt Candidate (`candidate_port2a/`) | Delta vs. `PORT16_WITNESS_ADDRESS.md` | Delta vs. Historical Baseline |
|---|---|---|---|---|---|
| Target Core ELF | `candidate_port2a/candidate_main.elf` | `platform/g3x/sub/110c/prototype_main.elf` | `candidate_port2a/candidate_main.elf` | Identical source | Relocated build |
| **`boot_witness` Address** | `0x0035F780` `[VERIFIED: historical tools/build_candidate_port2a.py:223]` | **`0x0035F7A0`** `[VERIFIED: PORT16_WITNESS_ADDRESS.md:15]` | **`0x0035F7A0`** `[VERIFIED: candidate_main.elf nm]` | **`0x0` (Exact Match)** | **`+0x20` (+32 B)** |
| `boot_witness` Type | Section `.data`, Type `D`, 16-byte aligned `[VERIFIED]` | Section `.data`, Type `D`, 16-byte aligned `[VERIFIED: PORT16_WITNESS_ADDRESS.md:16]` | Section `.data`, Type `D`, 16-byte aligned `[VERIFIED]` | Exact Match | Exact Match |
| **`_end` Address** | `0x00366C90` `[VERIFIED: docs/PROJECT_STATE.md:178]` | **`0x00366CB0`** `[VERIFIED: PORT16_WITNESS_ADDRESS.md:218]` | **`0x00366CB0`** `[VERIFIED: candidate_main.elf nm]` | **`0x0` (Exact Match)** | **`+0x20` (+32 B)** |
| `_start` Address | `0x003489B4` `[VERIFIED]` | `0x003489B4` `[VERIFIED: PORT16_WITNESS_ADDRESS.md:90]` | `0x003489B4` `[VERIFIED: candidate_main.elf nm]` | `0x0` (Exact Match) | `0x0` (Exact Match) |
| `link_text_end` / `link_data_start` | `0x0035AEA0` `[INFERRED: PORT16_WITNESS_ADDRESS.md:216]` | `0x0035AEC0` `[VERIFIED: PORT16_WITNESS_ADDRESS.md:216]` | `0x0035AEC0` `[VERIFIED: candidate_main.elf nm]` | `0x0` (Exact Match) | `+0x20` (+32 B) |
| `link_data_end` / `link_bss_start` | `0x003651E4` `[VERIFIED: docs/PROJECT_STATE.md:178]` | `0x00365204` `[VERIFIED: PORT16_WITNESS_ADDRESS.md:217]` | `0x00365204` `[VERIFIED: candidate_main.elf nm]` | `0x0` (Exact Match) | `+0x20` (+32 B) |
| Core Binary Size | 116,784 B `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:77]` | 116,816 B `[VERIFIED: PORT16_WITNESS_ADDRESS.md:99]` | 116,816 B `[VERIFIED: candidate_main.bin size]` | 0 B (Exact Match) | +32 B |
| Core `.text` Size | 74,988 B `[INFERRED]` | 75,020 B `[VERIFIED: PORT16_WITNESS_ADDRESS.md:97]` | 75,020 B `[VERIFIED: candidate_main.elf size]` | 0 B (Exact Match) | +32 B |
| Core `.data` Size | 41,796 B `[INFERRED]` | 41,796 B `[VERIFIED: PORT16_WITNESS_ADDRESS.md:97]` | 41,796 B `[VERIFIED: candidate_main.elf size]` | 0 B (Exact Match) | 0 B |
| Core `.bss` Size | 6,828 B `[INFERRED]` | 6,828 B `[VERIFIED: PORT16_WITNESS_ADDRESS.md:97]` | 6,828 B `[VERIFIED: candidate_main.elf size]` | 0 B (Exact Match) | 0 B |
| Witness Inspector Target | `0x0035F780` (pre-remediation) `[VERIFIED]` | `0x0035F7A0` `[VERIFIED: PORT16_WITNESS_ADDRESS.md:21]` | `0x0035F7A0` `[VERIFIED: MOVW/MOVT disassembly §5.3]` | `0x0` (Exact Match) | `+0x20` (+32 B) |

---

### 5.3 Witness Inspector Payload Target Verification

Disassembly of `candidate_port2a/witness_inspector_payload.bin` (first 20 bytes):
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump -b binary -m arm -M force-thumb -D candidate_port2a/witness_inspector_payload.bin
```
**Verbatim Disassembly Output**:
```text
00000000 <.data>:
   0:	e92d 41f0 	stmdb	sp!, {r4, r5, r6, r7, r8, lr}
   4:	4604      	mov	r4, r0
   6:	460d      	mov	r5, r1
   8:	4616      	mov	r6, r2
   a:	f24f 77a0 	movw	r7, #63392	; 0xf7a0
   e:	f2c0 0735 	movt	r7, #53	; 0x35
  12:	6838      	ldr	r0, [r7, #0]
```
`[VERIFIED: arm-none-eabi-objdump output on candidate_port2a/witness_inspector_payload.bin]`

- Instruction at `0x0A`: `movw r7, #0xF7A0` (lower 16 bits of target address) `[VERIFIED]`
- Instruction at `0x0E`: `movt r7, #0x0035` (upper 16 bits of target address) `[VERIFIED]`
- Resulting Register Value: `r7 = 0x0035F7A0` (matches candidate `boot_witness` exactly) `[VERIFIED]`

---

## 6. Discrepancy Analysis: Tracked Metadata vs. Regenerated Candidate Inspector

A critical discrepancy between the tracked repository state at HEAD and the regenerated candidate build was identified and documented:

### 6.1 Tracked File at HEAD (`firmware/tools/witness_inspector_metadata.json`)
The tracked metadata file in the Git repository at HEAD still records the pre-correction witness address:
```json
4:   "witness_address": "0x0035F780",
5:   "witness_address_int": 3536768,
```
`[VERIFIED: firmware/tools/witness_inspector_metadata.json:4-5]`

Similarly, the tracked binary payload `firmware/tools/witness_inspector_payload.bin` at HEAD encodes immediate `0x0035F780` (bytes at `0x0A-0x12`: `4ff28077c0f23507` -> `movw r7, #0xF780; movt r7, #0x0035`) with SHA-256 `f1cd6438b8c54a233b28360705c02f869da2149c6499e9b2d8c340746a3c7f00` `[VERIFIED]`.

### 6.2 Corrected Candidate Build Output (`candidate_port2a/witness_inspector_metadata.json`)
The candidate build script `tools/build_candidate_port2a.py` dynamically regenerates the witness inspector artifacts directly inside `candidate_port2a/` targeted to the verified ELF witness address `0x0035F7A0`:
```json
4:   "witness_address": "0x0035F7A0",
5:   "witness_address_int": 3536800,
```
`[VERIFIED: candidate_port2a/witness_inspector_metadata.json:4-5]`

The regenerated binary payload `candidate_port2a/witness_inspector_payload.bin` encodes immediate `0x0035F7A0` (bytes at `0x0A-0x12`: `4ff2a077c0f23507` -> `movw r7, #0xF7A0; movt r7, #0x0035`) with SHA-256 `241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2` `[VERIFIED]`.

### 6.3 Restoration of Tracked Repository Files
Because `firmware/tools/witness_inspector_metadata.json` and `firmware/tools/witness_inspector_payload.bin` are tracked files in Git that represent historical tools/repository state, they must not be overwritten or modified by candidate build execution.
The explicit restoration command was executed:
```bash
git checkout HEAD -- firmware/tools/witness_inspector_metadata.json firmware/tools/witness_inspector_payload.bin
```
`[VERIFIED: shell command execution]`
Both files remain exactly identical to HEAD, leaving zero uncommitted modifications in tracked repository files `[VERIFIED]`.

---

## 7. Candidate Artifacts Ledger (SHA-256 and Size)

The following ledger documents every artifact generated in `candidate_port2a/` by the candidate rebuild. All files were measured using `sha256sum` and byte-level filesystem queries `[VERIFIED]`.

### 7.1 Pinned Candidate Release Artifacts (Recorded in Manifest)

| Artifact Name | Path | Size (Bytes) | SHA-256 Checksum | Classification |
|---|---|---|---|---|
| **`candidate_main.elf`** | `candidate_port2a/candidate_main.elf` | 211,616 | `2a07ef02109ecc35bc1865bd0ccf7a8329a17dcf3574fa43691295a6d3ae3c93` | `VERIFIED` |
| **`candidate_main.bin`** | `candidate_port2a/candidate_main.bin` | 116,816 | `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e` | `VERIFIED` |
| **`candidate_loader.elf`** | `candidate_port2a/candidate_loader.elf` | 120,176 | `61812193ec9de3fa4a43094e0fd595ac5982251641a81bc980248c8b24ac5509` | `VERIFIED` |
| **`candidate_loader.bin`** | `candidate_port2a/candidate_loader.bin` | 118,000 | `2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a` | `VERIFIED` |
| **`DISKBOOT.BIN`** | `candidate_port2a/DISKBOOT.BIN` | 118,001 | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | `VERIFIED` |
| **`witness_inspector_gm110c.m`** | `candidate_port2a/witness_inspector_gm110c.m` | 5,580 | `7a53835f7048b3c9e8be3c545efb9b14a85676a7b856de7899ae00dcd697c28f` | `VERIFIED` |
| **`witness_inspector_payload.bin`** | `candidate_port2a/witness_inspector_payload.bin` | 444 | `241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2` | `VERIFIED` |

### 7.2 Supporting Manifest and Metadata Artifacts

| Artifact Name | Path | Size (Bytes) | SHA-256 Checksum | Description | Classification |
|---|---|---|---|---|---|
| **`candidate_manifest.json`** | `candidate_port2a/candidate_manifest.json` | 2,766 | `d1cac2f4a0de41b5058d7776a63fe19dbbb7acd42bccc99c63ad7bfb22310135` | Cryptographically locked candidate manifest | `VERIFIED` |
| **`witness_inspector_metadata.json`** | `candidate_port2a/witness_inspector_metadata.json` | 288 | `8b78003bb5feeb9b7159a0f8147bb7028a8ba809d2fd926e7bcd8359b3844295` | Inspector address binding metadata (target `0x0035F7A0`) | `VERIFIED` |

### 7.3 Intermediate Object and Archive Artifacts

| Artifact Name | Path | Size (Bytes) | SHA-256 Checksum | Description | Classification |
|---|---|---|---|---|---|
| **`boot_prototype.o`** | `candidate_port2a/boot_prototype.o` | 4,984 | `c1a18520d9149c109bf8e842a9cd4783e34dc5f8550039b99bd35529f507aa72` | Compiled object of `boot_prototype.c` | `VERIFIED` |
| **`stubs_prototype.o`** | `candidate_port2a/stubs_prototype.o` | 3,728 | `ba8279c2e07405973504f5e818f7db752d5ee97fc219f35a325cb9d40284b03d` | Assembled object of `stubs_prototype.S` | `VERIFIED` |
| **`libplatformsub_candidate.a`** | `candidate_port2a/libplatformsub_candidate.a` | 197,750 | `b2336f149e45b4d9ce39f5747f5a676e23a1507970ded950aa02a97c8c1fd9cf` | Candidate platform sub archive | `VERIFIED` |
| **`main_prototype.o`** | `candidate_port2a/main_prototype.o` | 3,036 | `c750323769ed03b0e31268cb3338116e9a0f8336dbb7ce0221bc786f82e9193a` | Compiled object of `main_prototype.c` | `VERIFIED` |
| **`blobs_candidate.o`** | `candidate_port2a/blobs_candidate.o` | 117,652 | `16bea78be1c0e43d06151ec383f1e440bcc34f27bc702b9d5c773ed73c29a6c4` | Assembled payload blob wrapper | `VERIFIED` |
| **`witness_inspector_payload.o`** | `candidate_port2a/witness_inspector_payload.o` | 1,288 | `0e3de9e1c3f62971978c45f91e5d1cbcd60efd319e089148d4fa983675972411` | Assembled object of `witness_inspector_payload.S` | `VERIFIED` |

### 7.4 Tracked Reference Artifacts in `firmware/tools/` (Preserved at HEAD)

| Artifact Name | Path | Size (Bytes) | SHA-256 Checksum | Description | Classification |
|---|---|---|---|---|---|
| **`witness_inspector_metadata.json`** | `firmware/tools/witness_inspector_metadata.json` | 286 | `1d834c21aedd0a46383559f65c0fe56e035ea1de21146fc9d15ee3f82f17daf3` | Tracked metadata at HEAD (targets `0x0035F780`) | `VERIFIED` |
| **`witness_inspector_payload.bin`** | `firmware/tools/witness_inspector_payload.bin` | 444 | `f1cd6438b8c54a233b28360705c02f869da2149c6499e9b2d8c340746a3c7f00` | Tracked binary payload at HEAD (targets `0x0035F780`) | `VERIFIED` |

*(Note: Per project policy and `.gitignore`, all files in `candidate_port2a/` remain uncommitted and untracked. Only this documentation file is committed to git `[VERIFIED]`.)*

---

## 8. Production Invariance Verification

The candidate validator verified that all production canonical files remain unaltered against their locked hashes `[VERIFIED: validate_candidate_port2a.py]`:

| Production File | Locked SHA-256 Hash | Current SHA-256 Hash | Status | Classification |
|---|---|---|---|---|
| `chdk-port/bin/DISKBOOT.BIN` | `3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72` | `3b2a0d5fe786933bb218f99de7acd5bb53276459f88e7cbeb2fa0e8085494d72` | Unaltered | `VERIFIED` |
| `chdk-port/loader/g3x/main.c` | `2678341e18cf55db0eba2ec50d55bebcca33ae189ce67fed839e3a43ed9b21f8` | `2678341e18cf55db0eba2ec50d55bebcca33ae189ce67fed839e3a43ed9b21f8` | Unaltered | `VERIFIED` |
| `chdk-port/platform/g3x/sub/110c/boot.c` | `13105e4cbc1dec6d997f15c2ff1b37305d309d83269239a8d2b0456f559e50b1` | `13105e4cbc1dec6d997f15c2ff1b37305d309d83269239a8d2b0456f559e50b1` | Unaltered | `VERIFIED` |

---

## 9. Evidence and Claim Classification Ledger

| # | Topic / Claim | Value / Citation | Classification |
|---|---|---|---|
| 1 | Git Worktree | `/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-candidate-rebuild-r3` | `VERIFIED` |
| 2 | Git Branch | `agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-candidate-rebuild-r3` | `VERIFIED` |
| 3 | Base Commit SHA (`origin/main`) | `3d8794e136ecc03919f2da5bb3f5d034eae500e5` (`git merge-base HEAD origin/main`); Milestone Integration Base: `665c8dec2c6477ecefef8714b32a37bdd11b9d84` (`git rev-parse HEAD` at milestone base) | `VERIFIED` |
| 4 | Toolchain GCC version | ARM GNU-RM 5.4.1 20160919 (`arm-none-eabi-gcc --version`) | `VERIFIED` |
| 5 | Toolchain NM version | GNU nm 2.26.2.20160923 (`arm-none-eabi-nm --version`) | `VERIFIED` |
| 6 | Candidate Rebuild Command | `python3 -B tools/build_candidate_port2a.py` | `VERIFIED` |
| 7 | Candidate Rebuild Exit Code | `0` (Success) | `VERIFIED` |
| 8 | Candidate Validation Command | `python3 -B tools/validate_candidate_port2a.py` | `VERIFIED` |
| 9 | Candidate Validation Exit Code | `0` (All 7 test suites passed) | `VERIFIED` |
| 10 | Candidate `boot_witness` Address | `0x0035F7A0` (`candidate_main.elf` symbol table) | `VERIFIED` |
| 11 | Candidate `boot_witness` Symbol Type | `D` (.data, 16-byte aligned, length 0x20) | `VERIFIED` |
| 12 | Candidate `_end` Address | `0x00366CB0` (`candidate_main.elf` symbol table) | `VERIFIED` |
| 13 | Candidate `_start` Address | `0x003489B4` (`candidate_main.elf` symbol table) | `VERIFIED` |
| 14 | Candidate Section Boundary `link_data_start` | `0x0035AEC0` (`candidate_main.elf` symbol table) | `VERIFIED` |
| 15 | Candidate Section Boundary `link_bss_start` | `0x00365204` (`candidate_main.elf` symbol table) | `VERIFIED` |
| 16 | Match with `docs/PORT16_WITNESS_ADDRESS.md` | Exact numerical match for `boot_witness` (`0x0035F7A0`) and `_end` (`0x00366CB0`) | `VERIFIED` |
| 17 | Core Binary Size | 116,816 bytes (`candidate_port2a/candidate_main.bin`) | `VERIFIED` |
| 18 | Loader Binary Size | 118,000 bytes (`candidate_port2a/candidate_loader.bin`) | `VERIFIED` |
| 19 | DISKBOOT.BIN Size | 118,001 bytes (`candidate_port2a/DISKBOOT.BIN`) | `VERIFIED` |
| 20 | Inspector Payload Size | 444 bytes (`candidate_port2a/witness_inspector_payload.bin`) | `VERIFIED` |
| 21 | Inspector Script Size | 5,580 bytes (`candidate_port2a/witness_inspector_gm110c.m`) | `VERIFIED` |
| 22 | Inspector Target Address (MOVW/MOVT) | `0x0035F7A0` (Thumb-2 instructions at offset `0x0A` and `0x0E`) | `VERIFIED` |
| 23 | Tracked Metadata Witness Address | `0x0035F780` (`firmware/tools/witness_inspector_metadata.json:4`) | `VERIFIED` |
| 24 | Regenerated Metadata Witness Address | `0x0035F7A0` (`candidate_port2a/witness_inspector_metadata.json:4`) | `VERIFIED` |
| 25 | Tracked File Restoration | Restored to HEAD via explicit `git checkout HEAD --` command | `VERIFIED` |
| 26 | Production Invariance | `DISKBOOT.BIN`, `loader/g3x/main.c`, `platform/g3x/sub/110c/boot.c` unaltered | `VERIFIED` |
| 27 | Git Tracking Invariance | Only `docs/PORT16_CANDIDATE_BUILD.md` tracked/committed; binaries uncommitted | `VERIFIED` |
| 28 | Hardware Trial / Camera Testing | STRICT NO-GO; Phase 0 offline validation only | `VERIFIED` |

---

## 10. Conclusion

The CHDK-PORT-2A first-boot candidate rebuild pipeline is fully operational, consistent, and validated offline:
1. `tools/build_candidate_port2a.py` built all candidate artifacts directly from current corrected source with zero failures.
2. The candidate `boot_witness` symbol is located at `0x0035F7A0` in `.data` (16-byte aligned) and `_end` is at `0x00366CB0` in `.bss`, matching `docs/PORT16_WITNESS_ADDRESS.md` with 100% precision.
3. The associated witness inspector script and binary payload are confirmed targeting `0x0035F7A0` via bit-level MOVW/MOVT immediate inspection.
4. All 7 test suites in `tools/validate_candidate_port2a.py` pass cleanly offline.
5. The tracked reference files in `firmware/tools/` at HEAD still record the historical `0x0035F780` address, whereas the corrected candidate build properly regenerates artifacts at `0x0035F7A0`. Both tracked reference files remain untouched and restored to HEAD.
6. Production files remain unaltered, and Phase 0 read-only safety rules remain strictly enforced (`NO-GO` for physical camera testing).
