# PORT-16: Boot Witness Symbol Address Verification & Derivation

**Task ID**: `p16-witness-addr`  
**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C)  
**Host Platform**: AgentBridge isolated worktree (`/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr`)  
**Evaluation Mode**: Phase 0 Read-Only / Offline Link Output Derivation  
**Date**: 2026-10-30  

---

## 1. Executive Summary & Core Findings

This document records the exact derivation and verification of the `boot_witness` symbol RAM address by building the boot prototype directly from the corrected source in `chdk-port/platform/g3x/sub/110c/` using the pinned ARM GNU toolchain (`gcc-arm-none-eabi-5_4-2016q3`).

- **Derived `boot_witness` Symbol Address**: **`0x0035F7A0`** `[VERIFIED: prototype_main.elf nm / prototype_main.map]`
- **Symbol Properties**: Section `.data`, Type `D`, Size `0x20` (32 bytes), Alignment 16-byte boundary `[VERIFIED: boot_prototype.c:27; prototype_main.map:1431-1432]`
- **Comparison with Candidate Assertion (`0x0035F780`)**:
  - `tools/build_candidate_port2a.py:223` asserts `witness_addr == 0x0035F780` `[VERIFIED: tools/build_candidate_port2a.py:223]`.
  - The derived prototype address `0x0035F7A0` differs by exactly **`+0x20` (+32 bytes)** from `0x0035F780` `[VERIFIED]`.
  - **Stale Builder Assertion vs. Preserved Historical Artifacts**:
    - The candidate build script `tools/build_candidate_port2a.py` compiles the **CURRENT** working-tree source files `boot_prototype.c` and `stubs_prototype.S` (`tools/build_candidate_port2a.py:70-71, 127-144`), overwriting the candidate core outputs (`candidate_main.elf`, `candidate_main.bin`), and asserts the old address `assert witness_addr == 0x0035F780` at line 223 `[VERIFIED: tools/build_candidate_port2a.py:70-71, 127-144, 223]`. Because the builder compiles the current corrected source (which yields `boot_witness` at `0x0035F7A0`), the `0x0035F780` assertion is **STALE against the corrected source** and would fail or mismatch if executed `[VERIFIED: tools/build_candidate_port2a.py:216-224]`.
    - Separately, preserved historical candidate artifacts (e.g. pinned candidate hashes in `docs/REPRODUCIBILITY_MANIFEST.md:71-78` and tracked documentation in `docs/PROJECT_STATE.md:60`) preserve the original pre-correction candidate baseline (116,784-byte core, witness at `0x0035F780`) from the original build prior to PR #2 `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:71-78; docs/PROJECT_STATE.md:60]`.
- **Comparison with Tracked Prototype Documentation (`0x0035F7A0`)**:
  - `docs/RESTART_SD_HOST_AUDIT.md:248` records: `boot_witness relocated from 0x0035F780 to 0x0035F7A0 (16-byte aligned, type D)` `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:248]`.
  - `docs/REPRODUCIBILITY_MANIFEST.md:80` records: `boot_witness @ 0x0035F7A0` `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:80]`.
  - `docs/PROJECT_STATE.md:133` and `docs/HANDOFF.md:228` record: `boot_witness moved from 0x0035F780 to 0x0035F7A0 (type D)` `[VERIFIED: docs/PROJECT_STATE.md:133; docs/HANDOFF.md:228]`.
  - `docs/PORT3C_RESTART_READINESS_MATRIX.md:231` records: `prototype ELF places witness at 0x0035F7A0; preserved candidate ELF places it at 0x0035F780` `[VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:231]`.
  - `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66` records: `SD audit §8.2 describes a prototype witness at 0x0035F7A0; current inspector metadata targets the candidate at 0x0035F780` `[VERIFIED: docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66]`.
  - The derived address matches tracked prototype documentation with 100% precision `[VERIFIED]`.
- **Root Cause of Symbol Relocation**:
  - **PR #2 (`SD1stInit` addition)**: Added Thumb-2 instructions in `boot_prototype.c` (`task_Startup_my`) and stub routines in `stubs_prototype.S` (`sub_fc05c4e0` and `sub_fc31b1f4`) `[VERIFIED: git show 2590036; patches/0001-sd1stinit-restart-prototype.patch:22-58]`. In the current build, `link_text_end` and `link_data_start` are placed at `0x0035AEC0` and `boot_witness` is placed at `0x0035F7A0` in `.data` `[VERIFIED: prototype_main.map:1312-1315, 1431-1432; link-boot.ld:14-26]`. The causal claim that these source additions expanded `.text` and shifted `link_text_end`/`link_data_start` forward by `+0x20` (32 bytes) to relocate `boot_witness` from `0x0035F780` to `0x0035F7A0`, along with the specific byte accounting breakdown of $14 + 16 + 2 = 32$ bytes, is inferred from source and patch analysis without a comparative pre-PR#2 linker map in the repository `[INFERRED]`.
  - **PR #5 (`PORT-5E` early boot literal corrections)**: Corrected ten 32-bit literals in `sub_fc05b558_my` `[VERIFIED: git show f8cc7a9; tests/test_early_boot_literals.py]`. Comparative scratch builds of the prototype at the pre-PORT-5E commit (`fa2a094`) and at the PORT-5E commit (`f8cc7a9`) verify that assembled section sizes remained identical ($\Delta = 0$ bytes) and `boot_witness` remained unchanged at `0x0035F7A0` `[VERIFIED: comparative build link outputs §6.4; prototype_main.map:1431-1432]`.

---

## 2. Build Environment, Toolchain, and Git Baseline

### 2.1 Git Repository & HEAD Identification
- **Active Worktree**: `/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr`
- **Git Branch**: `agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-witness-addr`
- **Base Commit SHA (`origin/main`)**: `3d8794e136ecc03919f2da5bb3f5d034eae500e5` `[VERIFIED: git rev-parse origin/main]`
  - Commit message: `Merge pull request #39 from s4urj3ng/agentbridge/g3x-lite/port-15-offline/integration`
- **Git HEAD SHA**: `3d8794e136ecc03919f2da5bb3f5d034eae500e5` `[VERIFIED: git rev-parse HEAD]`

### 2.2 Pinned ARM GNU Toolchain
- **Toolchain Path**: `toolchains/gcc-arm-none-eabi-5_4-2016q3` `[VERIFIED]`
- **Compiler Binary**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc` `[VERIFIED]`
- **Symbol Utility Binary**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm` `[VERIFIED]`
- **Archive Utility Binary**: `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-ar` `[VERIFIED]`
- **Verbatim Toolchain Version Output (`arm-none-eabi-gcc --version`)**:
  ```text
  arm-none-eabi-gcc (GNU Tools for ARM Embedded Processors) 5.4.1 20160919 (release) [ARM/embedded-5-branch revision 240496]
  Copyright (C) 2015 Free Software Foundation, Inc.
  This is free software; see the source for copying conditions.  There is NO
  warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
  ```
  `[VERIFIED: toolchain command execution]`
- **Verbatim NM Utility Version Output (`arm-none-eabi-nm --version`)**:
  ```text
  GNU nm (GNU Tools for ARM Embedded Processors) 2.26.2.20160923
  Copyright (C) 2015 Free Software Foundation, Inc.
  This program is free software; you may redistribute it under the terms of
  the GNU General Public License version 3 or (at your option) any later version.
  This program has absolutely no warranty.
  ```
  `[VERIFIED: toolchain command execution]`

---

## 3. Build Procedure and Exact Commands

### 3.1 Step 1: Platform Source Bootstrap (PR #7 / PORT-8A)
The camera-level platform headers and sources (`kbd.c`, `lib.c`, `platform_camera.h`, `platform_kbd.h`, `shooting.c`) are deterministically reconstructed into `chdk-port/platform/g3x/` from hash-pinned baseline files via `tools/bootstrap_chdk_platform.py`:
```bash
python3 -B tools/bootstrap_chdk_platform.py
```
**Verbatim Output**:
```text
OK       platform/g3x/kbd.c (final hash)
OK       platform/g3x/lib.c (final hash)
OK       platform/g3x/platform_camera.h (final hash)
OK       platform/g3x/platform_kbd.h (final hash)
OK       platform/g3x/shooting.c (final hash)
RESULT ok: all files at final hash
```
`[VERIFIED: tools/bootstrap_chdk_platform.py execution]`

### 3.2 Step 2: Prototype Compilation and Link
The prototype build compiles `chdk-port/platform/g3x/sub/110c/boot_prototype.c` and `stubs_prototype.S`, archives them into `libplatformsub_prototype.a`, and links `prototype_main.elf` at origin `0x003489B4`:
```bash
python3 -B tools/build_prototype.py
```
**Verbatim Build Output**:
```text
Successfully built /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/prototype_main.elf:
   text	   data	    bss	    dec	    hex	filename
  75020	  41796	   6828	 123644	  1e2fc	/var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/prototype_main.elf

Generated /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/prototype_main.bin (116816 bytes)
```
`[VERIFIED: tools/build_prototype.py execution]`

### 3.3 Step 3: Exact Linker Invocation and Map Generation
The prototype link step executed by the build script (with `-Wl,-Map,platform/g3x/sub/110c/prototype_main.map` added to generate the linker map) is:
```bash
cd chdk-port && /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc \
    -nostdlib \
    -Wl,--allow-shlib-undefined \
    -Wl,-T,tools/link-boot.ld \
    -Wl,-N,-Ttext,0x3489b4 \
    -Wl,-Map,platform/g3x/sub/110c/prototype_main.map \
    -o /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/prototype_main.elf \
    -Wl,--start-group \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/entry.o \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/libplatform.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/lib/font/.o2/libfont.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/lib/math/.o2/libmath.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/lib/lang/.o2/liblang.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/lib/armutil/.o2/libarmutil.a \
    /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/lib/core/.o2/libcore.a \
    -lgcc \
    -Wl,--end-group
```
`[VERIFIED: linker execution log]`

---

## 4. Derived `boot_witness` Symbol Address from Link Outputs

### 4.1 Exact `arm-none-eabi-nm` Command and Verbatim Output
Command executed on the built prototype ELF:
```bash
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm -n chdk-port/platform/g3x/sub/110c/prototype_main.elf | grep -C 5 boot_witness
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
`[VERIFIED: arm-none-eabi-nm output]`

The symbol `boot_witness` appears at address **`0x0035F7A0`**, with symbol type `D` (initialized data section).

### 4.2 Exact Linker Map Command and Verbatim Output
Command executed to extract the symbol and neighbouring section placements from the map file:
```bash
grep -C 10 "boot_witness" chdk-port/platform/g3x/sub/110c/prototype_main.map
```
**Verbatim Linker Map Output (`prototype_main.map:1422-1442`)**:
```text
 *(.rdata)
                0x0035f798                . = ALIGN (0x4)
 *(.blob*)
 *(.data)
 .data          0x0035f798        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/entry.o
 .data          0x0035f798        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/libplatform.a(main.o)
 .data          0x0035f798        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/libplatform.a(lib.o)
 .data          0x0035f798        0x4 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/libplatform.a(wrappers.o)
 *fill*         0x0035f79c        0x4 
 .data          0x0035f7a0       0x20 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(boot_prototype.o)
                0x0035f7a0                boot_witness
 .data          0x0035f7c0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(stubs_prototype.o)
 .data          0x0035f7c0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(stubs_min.o)
 .data          0x0035f7c0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(stubs_entry.o)
 .data          0x0035f7c0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(stubs_entry_2.o)
 .data          0x0035f7c0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(capt_seq.o)
 .data          0x0035f7c0        0x4 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(main.thm.o)
 .data          0x0035f7c4        0x4 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(gui_draw.thm.o)
                0x0035f7c4                chdk_colors
 .data          0x0035f7c8        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(memmgmt.thm.o)
 .data          0x0035f7c8     0x1b4c /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/libplatformsub_prototype.a(gui.thm.o)
```
`[VERIFIED: prototype_main.map:1422-1442]`

The map confirms:
- Preceding symbol contribution: `wrappers.o` contributes 4 bytes (`0x0035f798..0x0035f79c`)
- Alignment fill: 4 bytes padding (`*fill* 0x0035f79c 0x4`) to reach the 16-byte boundary `0x0035F7A0`
- Target symbol: `boot_witness` is placed at `0x0035f7a0` with length `0x20` (32 bytes)
- Following symbol contribution: `main.thm.o` begins at `0x0035f7c0`

---

## 5. Address Comparisons

### 5.1 Comparison with `0x0035F780` Assertion in `tools/build_candidate_port2a.py`
In `tools/build_candidate_port2a.py:223`, the candidate builder script asserts:
```python
assert witness_addr == 0x0035F780, f"Expected boot_witness at 0x0035F780, got {witness_addr}"
```
`[VERIFIED: tools/build_candidate_port2a.py:223]`

Additionally, `tools/validate_candidate_port2a.py:112` asserts:
```python
assert syms.get("boot_witness") == 0x0035F780, f"boot_witness must be 0x0035F780, got {hex(syms.get('boot_witness', 0))}"
```
`[VERIFIED: tools/validate_candidate_port2a.py:112]`

| Metric | Preserved Historical Candidate Baseline | Corrected Prototype Build (`sub/110c/`) | Delta |
|---|---|---|---|
| Target Core ELF | `candidate_port2a/candidate_main.elf` | `chdk-port/platform/g3x/sub/110c/prototype_main.elf` | — |
| `boot_witness` Address | `0x0035F780` `[VERIFIED: tools/build_candidate_port2a.py:223]` | **`0x0035F7A0`** `[VERIFIED: prototype_main.elf nm]` | **`+0x20` (+32 B)** |
| Core Binary Size | 116,784 B `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:77]` | 116,816 B `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:80]` | **+32 B** |
| Core ELF Size | 211,416 B `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:78]` | 211,608 B `[VERIFIED: prototype build size]` | **+192 B** |
| Section Bounds (`link_data_start`) | `0x0035AEA0` `[INFERRED]` | `0x0035AEC0` `[VERIFIED: prototype_main.map:1315]` | **`+0x20` (+32 B)** |
| Section Bounds (`link_data_end` / `link_bss_start`) | `0x003651E4` `[VERIFIED: docs/PROJECT_STATE.md:178]` | `0x00365204` `[VERIFIED: prototype_main.map:1488]` | **`+0x20` (+32 B)** |
| Section Bounds (`_end`) | `0x00366C90` `[VERIFIED: docs/PROJECT_STATE.md:178]` | `0x00366CB0` `[VERIFIED: prototype_main.map:1506]` | **`+0x20` (+32 B)** |

**Analysis of Builder Behavior vs. Preserved Historical Artifacts**:
1. **The `0x0035F780` Assertion is Stale Against Corrected Source**:
   The script `tools/build_candidate_port2a.py` does not compile a separate frozen snapshot of old source; it compiles the **CURRENT** working-tree source files:
   - `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (`tools/build_candidate_port2a.py:70, 78-126`)
   - `chdk-port/platform/g3x/sub/110c/stubs_prototype.S` (`tools/build_candidate_port2a.py:71, 129-144`)
   It archives these into `candidate_port2a/libplatformsub_candidate.a` (line 173), links `candidate_port2a/candidate_main.elf` (lines 176-196), and writes `candidate_port2a/candidate_main.bin` (line 199), overwriting the candidate core outputs.
   At lines 216-224, it inspects the newly linked core ELF using `arm-none-eabi-nm -n` and executes:
   ```python
   assert witness_addr == 0x0035F780, f"Expected boot_witness at 0x0035F780, got {witness_addr}"
   ```
   (`tools/build_candidate_port2a.py:223`).
   Because the builder compiles the current corrected source (which contains the PR #2 additions), linking places `boot_witness` at `0x0035F7A0`. Consequently, the builder's own assertion at line 223 is **STALE against the corrected source**: executing `tools/build_candidate_port2a.py` today would fail with an assertion mismatch (`AssertionError: Expected boot_witness at 0x0035F780, got 3536800`) `[VERIFIED: tools/build_candidate_port2a.py:70-71, 127-144, 216-224]`.

2. **Distinct Preserved Historical Artifacts and Documentation**:
   The `0x0035F780` address originated from the pre-correction candidate baseline built prior to PR #2. The repository separately tracks and protects those historical artifacts:
   - Preserved Candidate Core Binary: `candidate_port2a/candidate_main.bin` (116,784 B, SHA-256 `e6f823d1c4e40ff03bc923d423946f6da4bd412b18ae1ac68d0553a5055d7fd5`) `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:77]`.
   - Preserved Candidate ELF: `candidate_port2a/candidate_main.elf` (211,416 B, SHA-256 `973678ed662ba0add199697e2529024d6b6d98e9582cb3d4e233d2d333b8c645`) `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:78]`.
   - Historical Documentation: `docs/REPRODUCIBILITY_MANIFEST.md:71-78`, `docs/PROJECT_STATE.md:60, 178`, and `docs/PORT3C_RESTART_READINESS_MATRIX.md:231` document that the historical candidate baseline core placed `boot_witness` at `0x0035F780` and `_end` at `0x00366C90`.
   - Validator Script: `tools/validate_candidate_port2a.py:112` tests the preserved ELF with `assert syms.get("boot_witness") == 0x0035F780`.
   Under Phase 0 safety invariants (`docs/REPRODUCIBILITY_MANIFEST.md:71-73`), those historical candidate artifacts remain frozen. They must not be conflated with the execution of `tools/build_candidate_port2a.py`, which targets current source.

### 5.2 Comparison with Tracked `0x0035F7A0` Documentation Claims
Multiple tracked documents in the repository explicitly state that the prototype witness resides at `0x0035F7A0`:

1. `docs/RESTART_SD_HOST_AUDIT.md:248`:
   > `- boot_witness relocated from 0x0035F780 to 0x0035F7A0 (16-byte aligned, type D).`  
   `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:248]`
2. `docs/REPRODUCIBILITY_MANIFEST.md:80`:
   > `| **Prototype Core Binary** | chdk-port/platform/g3x/sub/110c/prototype_main.bin | 116,816 | 49a2fde902c9e86b49a0533256a174d791f1bdced26c8521ea7dd6f945fb16ad | Remediated SD1stInit prototype (+32 bytes; boot_witness @ 0x0035F7A0). |`  
   `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:80]`
3. `docs/PROJECT_STATE.md:133`:
   > `- Adding 14 bytes to prototype .text moved prototype_main.elf .data by +32 bytes (16-byte aligned): boot_witness moved from 0x0035F780 to 0x0035F7A0 (type D).`  
   `[VERIFIED: docs/PROJECT_STATE.md:133]`
4. `docs/HANDOFF.md:228`:
   > `- Adding 14 bytes to prototype .text moved prototype_main.elf .data by +32 bytes (16-byte aligned): boot_witness moved from 0x0035F780 to 0x0035F7A0 (type D).`  
   `[VERIFIED: docs/HANDOFF.md:228]`
5. `docs/PORT3C_RESTART_READINESS_MATRIX.md:231`:
   > `SD audit describes witness at 0x0035F7A0; inspector metadata targets 0x0035F780. | Different targets: prototype ELF places witness at 0x0035F7A0; preserved candidate ELF places it at 0x0035F780.`  
   `[VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:231]`
6. `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`:
   > `SD audit §8.2 describes a prototype witness at 0x0035F7A0; current inspector metadata targets the candidate at 0x0035F780.`  
   `[VERIFIED: docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66]`

**Result**:
The derived address `0x0035F7A0` is a 100% exact numerical match with all tracked prototype documentation `[VERIFIED]`.

---

## 6. Root Cause Analysis of Symbol Relocation

### 6.1 Linker Section Placement in `link-boot.ld`
The linker script `chdk-port/tools/link-boot.ld:14-26` places the `.data` section contiguously immediately following the `.text` section:

```ld
    . = ALIGN(4);
    link_text_end = .;


    .data : {
	link_data_start = .;
    *(.rodata*)
    *(.rdata)
    . = ALIGN(4);
    *(.blob*)
	*(.data)
	. = ALIGN(4);
    }
```
`[VERIFIED: chdk-port/tools/link-boot.ld:14-26]`

Because the prototype is linked with flags `-N -Ttext 0x3489b4`, `.data` begins immediately at `link_text_end`. Therefore:
$$\text{link\_data\_start} = \text{ALIGN\_UP}(\text{link\_text\_end}, 4)$$
Any byte-growth in `.text` directly advances `link_data_start` and shifts all contents of `.rodata` and `.data` downstream `[VERIFIED]`.

### 6.2 Verbatim Map Evidence for Section Boundaries
In `chdk-port/platform/g3x/sub/110c/prototype_main.map:1309-1318`, the exact boundary between `.text` and `.data` is recorded as:

```text
.rel.dyn        0x0035aec0        0x0
 .rel.iplt      0x0035aec0        0x0 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/sub/110c/entry.o
                0x0035aec0                . = ALIGN (0x4)
                0x0035aec0                link_text_end = .

.data           0x0035aec0     0xa344
                0x0035aec0                link_data_start = .
 *(.rodata*)
 .rodata        0x0035aec0        0x4 /var/lib/agentbridge/worktrees/g3x-lite/port-16-firstboot-pipeline-p16-witness-addr/chdk-port/platform/g3x/libplatform.a(main.o)
                0x0035aec0                zoom_points
```
`[VERIFIED: prototype_main.map:1309-1318]`

This confirms:
- `link_text_end = 0x0035aec0`
- `link_data_start = 0x0035aec0`
- `.data` starts at `0x0035aec0` with total length `0xa344` (41,796 bytes)

### 6.3 Source Change That Moved the Symbol: PR #2 (`SD1stInit` Addition)
In PR #2, the SD card startup task initialization was added to the prototype.

#### Git Commits:
- **PR #2 Merge Commit**: `25900369763851bbe3ede321f8395854a5dc9b4c`
  - `Merge pull request #2 from s4urj3ng/feat/restart-sd1stinit-prototype`
- **Feature Commit**: `860d873c130f063ab75b69985ea096c21d6ed0b9`
  - `feat(sd-restart): investigate SD1stInit omission and implement isolated prototype call`
- **Fix Commit**: `e418ccfeb7dab8c0dd2db6b3b8d988beec2b5e60`
  - `fix(sd-restart): track prototype sources, add patch artifact, and reconcile MMIO bit semantics`

#### `git show --stat 2590036` Summary:
```text
 .gitignore                                        |  14 +
 chdk-port/platform/g3x/sub/110c/boot_prototype.c  | 436 ++++++++++++++++++++++
 chdk-port/platform/g3x/sub/110c/boot_witness.h    |  45 +++
 chdk-port/platform/g3x/sub/110c/stubs_prototype.S |  56 +++
 docs/HANDOFF.md                                   |  43 ++-
 docs/PROJECT_STATE.md                             |  41 +-
 docs/REPRODUCIBILITY_MANIFEST.md                  | 200 ++++++++++
 docs/RESTART_SD_HOST_AUDIT.md                     | 302 +++++++++++++++
 patches/0001-sd1stinit-restart-prototype.patch    |  58 +++
 tests/test_restart_sd_audit.py                    | 370 ++++++++++++++++++
 10 files changed, 1554 insertions(+), 11 deletions(-)
```
`[VERIFIED: git show --stat 2590036]`

#### Verbatim Diff Hunks from `patches/0001-sd1stinit-restart-prototype.patch:22-58`:
```diff
--- a/platform/g3x/sub/110c/stubs_prototype.S
+++ b/platform/g3x/sub/110c/stubs_prototype.S
@@ -46,6 +46,7 @@
 STUB(fc33319a)
 STUB(fc0bb6fe)
+STUB(fc05c4e0)
 STUB(fc0d0126)
 
 // ARM Vector Routines (called via blx from Thumb-2)
@@ -53,3 +54,4 @@
 STUB2(fc31b408)
 STUB2(fc31b460)
 STUB2(fc31bbc4)
+STUB2(fc31b1f4)
--- a/platform/g3x/sub/110c/boot_prototype.c
+++ b/platform/g3x/sub/110c/boot_prototype.c
@@ -385,8 +385,16 @@
         "    bl      sub_fc418eec\n"
 
         // ---------------------------------------------------------------------
-        // CRITICAL OMISSION:
-        // Stock firmware executes: bl sub_fc05bbea (StartDiskboot)
-        // In CHDK, this call is omitted to prevent an infinite reload loop.
+        // RESTART-SD-1: SD1stInit Task Creation (replicates StartDiskboot gate)
+        // Stock StartDiskboot (0xFC05BBEA) spawns "SD1stInit" via veneer 0xFC31B1F4
+        // before loading DISKBOOT.BIN. Omitting StartDiskboot prevents reload loop,
+        // but previously left SD1stInit unspawned.
+        // Replicate stock gate (sub_fc05c4e0(0) bit 0 == 0) and call creator veneer.
         // ---------------------------------------------------------------------
+        "    movs    r0, #0\n"
+        "    bl      sub_fc05c4e0\n"
+        "    lsls    r0, r0, #31\n"
+        "    bne     1f\n"
+        "    blx     sub_fc31b1f4\n"
+        "1:\n"
 
         "    bl      sub_fc0bba02\n"
```
`[VERIFIED: patches/0001-sd1stinit-restart-prototype.patch:22-58]`

#### Inferred Byte Accounting:
- **`boot_prototype.c` Thumb-2 instructions**:
  - `movs r0, #0` (2 bytes)
  - `bl sub_fc05c4e0` (4 bytes)
  - `lsls r0, r0, #31` (2 bytes)
  - `bne 1f` (2 bytes)
  - `blx sub_fc31b1f4` (4 bytes)
  - Subtotal in `boot_prototype.c`: 14 bytes `[INFERRED]`
- **`stubs_prototype.S` additions**:
  - `STUB(fc05c4e0)`: `ldr.w pc, [pc, #0]` (4 B) + `.long 0xFC05C4E0 | 1` (4 B) = 8 bytes `[INFERRED]`
  - `STUB2(fc31b1f4)`: `ldr pc, [pc, #-4]` (4 B) + `.long 0xFC31B1F4` (4 B) = 8 bytes `[INFERRED]`
  - Subtotal in `stubs_prototype.S`: 16 bytes `[INFERRED]`
- **Section alignment padding**:
  - Total added code bytes = $14 + 16 = 30$ bytes.
  - Adding 2 bytes alignment padding yields 32 bytes (`+0x20`) `[INFERRED]`.
- **Shift of `.data` and `boot_witness`**:
  - `link_text_end` and `link_data_start` shifted by `+0x20` (from `0x0035AEA0` to `0x0035AEC0`) `[INFERRED]`.
  - The preceding symbols in `.data` shifted by 32 bytes `[INFERRED]`.
  - Because `boot_witness` requires 16-byte alignment (`__attribute__((aligned(16), section(".data")))` in `boot_prototype.c:27`), the downstream location aligned to the next 16-byte boundary at `0x0035F7A0` (with 4 bytes padding after `mz_speed`) `[VERIFIED: prototype_main.map:1430-1432]`.
  - Result: The claim that `boot_witness` shifted by exactly `+0x20` from `0x0035F780` to **`0x0035F7A0`** due to these PR #2 source additions is `[INFERRED]`.

*(Note: Because a side-by-side pre-change vs post-change linker map comparison is not checked into the repository, the causal claim that the PR #2 source additions shifted the section boundary by +0x20 and the exact internal byte accounting of $14 + 16 + 2 = 32$ bytes are classified as `INFERRED`. The verified facts are: (1) PR #2 added source in `boot_prototype.c` and `stubs_prototype.S` [VERIFIED: git show 2590036; patches/0001-sd1stinit-restart-prototype.patch:22-58]; (2) the current build places `link_text_end`/`link_data_start` at `0x0035AEC0` and `boot_witness` at `0x0035F7A0` [VERIFIED: prototype_main.map:1312-1315, 1431-1432]; and (3) historical candidate documentation and artifacts recorded `boot_witness` at `0x0035F780` [VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:77-78; docs/PROJECT_STATE.md:60]).*

### 6.4 Why PORT-5E (PR #5) Did Not Move the Symbol
Commit `f8cc7a9743a768351c6e95e80d956f3ee52dbd09` (`fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)`) corrected ten stage-4 literals in `sub_fc05b558_my`:
- String address: `0xfc05b604` $\to$ `0xfc05b600` (`"/_term"`)
- DryOS heap check words: `0x000080f0` $\to$ `0x000080ec`, `0x00008078` $\to$ `0x00008074`
- Seven diagnostic string pointers (`0xfc05b610`..`0xfc05b674`)

#### `git show --stat f8cc7a9` Summary:
```text
 chdk-port/platform/g3x/sub/110c/boot_prototype.c |  20 +-
 docs/CHDK_PORT1C1_CRITICAL_AUDIT.md              | 337 +++++++++++++++++++++++
 docs/HANDOFF.md                                  |  49 ++++
 docs/PORT5A_RANMA_PORT_RECOVERY.md               | 147 ++++++++++
 docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md        | 279 +++++++++++++++++++
 docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md      | 166 +++++++++++
 docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md       | 195 +++++++++++++
 docs/PROJECT_STATE.md                            |  21 ++
 docs/REPRODUCIBILITY_MANIFEST.md                 |   4 +
 tests/test_early_boot_literals.py                | 328 ++++++++++++++++++++++
 10 files changed, 1536 insertions(+), 10 deletions(-)
```
`[VERIFIED: git show --stat f8cc7a9]`

#### Verbatim Diff Hunk from `git show f8cc7a9 -- chdk-port/platform/g3x/sub/110c/boot_prototype.c`:
```diff
--- a/chdk-port/platform/g3x/sub/110c/boot_prototype.c
+++ b/chdk-port/platform/g3x/sub/110c/boot_prototype.c
@@ -265,16 +265,16 @@ void __attribute__((naked,noinline)) sub_fc05b558_my(void)
 {
     asm volatile (
         "    push    {r4, lr}\n"
-        "    ldr     r4, =0xfc05b604\n"        // ROM literal string "/_term"
+        "    ldr     r4, =0xfc05b600\n"        // ROM literal string "/_term" (adr @0xFC05B55A, PORT-5D)
         "    bl      sub_fc05c5bc\n"
-        "    ldr     r0, =0x000080f0\n"
+        "    ldr     r0, =0x000080ec\n"        // literal @0xFC05B608: [0x80ec] heap size
         "    ldr     r1, [r0]\n"
-        "    ldr     r0, =0x00008078\n"
+        "    ldr     r0, =0x00008074\n"        // literal @0xFC05B60C: [0x8074] 0x80000 bound
         "    ldr     r0, [r0]\n"
         "    adds    r0, #0x10\n"
         "    cmp     r1, r0\n"
         "    bhs     loc_fc05b574\n"
-        "    ldr     r0, =0xfc05b614\n"        // ROM literal string "USER_MEM size checking"
+        "    ldr     r0, =0xfc05b610\n"        // ROM literal string "USER_MEM size checking" (adr @0xFC05B56E)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b574:\n"
         "    bl      sub_fc127b3c\n"
@@ -289,39 +289,39 @@ void __attribute__((naked,noinline)) sub_fc05b558_my(void)
         "    bl      sub_fc418738\n"           // dmSetup
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b598\n"
-        "    ldr     r0, =0xfc05b634\n"        // ROM literal string "dmSetup"
+        "    ldr     r0, =0xfc05b630\n"        // ROM literal string "dmSetup" (adr @0xFC05B592)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b598:\n"
         "    bl      sub_fc05c7d4\n"           // termDriverInit
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b5a6\n"
-        "    ldr     r0, =0xfc05b63c\n"        // ROM literal string "termDriverInit"
+        "    ldr     r0, =0xfc05b638\n"        // ROM literal string "termDriverInit" (adr @0xFC05B5A0)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b5a6:\n"
         "    mov     r0, r4\n"
         "    bl      sub_fc05c862\n"           // termDeviceCreate
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b5b6\n"
-        "    ldr     r0, =0xfc05b64c\n"        // ROM literal string "termDeviceCreate"
+        "    ldr     r0, =0xfc05b648\n"        // ROM literal string "termDeviceCreate" (adr @0xFC05B5B0)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b5b6:\n"
         "    mov     r0, r4\n"
         "    bl      sub_fc05b794\n"           // stdioSetup
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b5c6\n"
-        "    ldr     r0, =0xfc05b660\n"        // ROM literal string "stdioSetup"
+        "    ldr     r0, =0xfc05b65c\n"        // ROM literal string "stdioSetup" (adr @0xFC05B5C0)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b5c6:\n"
         "    bl      sub_fc05b8d8\n"           // stdlibSetup
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b5d4\n"
-        "    ldr     r0, =0xfc05b66c\n"        // ROM literal string "stdlibSetup"
+        "    ldr     r0, =0xfc05b668\n"        // ROM literal string "stdlibSetup" (adr @0xFC05B5CE)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b5d4:\n"
         "    bl      sub_fc05e910\n"           // extlib_setup
         "    cmp     r0, #0\n"
         "    bge     loc_fc05b5e2\n"
-        "    ldr     r0, =0xfc05b678\n"        // ROM literal string "extlib_setup"
+        "    ldr     r0, =0xfc05b674\n"        // ROM literal string "extlib_setup" (adr @0xFC05B5DC)
         "    bl      sub_fc05b5ea\n"
         "loc_fc05b5e2:\n"
         "    pop.w   {r4, lr}\n"
```
`[VERIFIED: git show f8cc7a9 -- chdk-port/platform/g3x/sub/110c/boot_prototype.c]`

#### 6.4.1 Assembly Analysis: Pseudo-Instructions and Immediate Encoding
In GNU ARM/Thumb-2 assembly, `ldr rX, =constant` is an assembler pseudo-instruction rather than a single fixed opcode:
- When the constant can be encoded as an immediate (such as a 16-bit unsigned immediate for the ARMv7-R `movw` opcode, or a modified 12-bit Thumb-2 immediate for `mov`/`mvn`), GNU `as` emits an immediate move instruction directly, generating no entry in the literal pool.
- When the constant cannot be encoded as an immediate, GNU `as` allocates a 32-bit word in a literal pool (placed at the next `.ltorg` directive or the end of the section) and emits a PC-relative `ldr rX, [pc, #offset]` instruction.

In `sub_fc05b558_my`, ten `ldr rX, =constant` pseudo-instructions were modified by PORT-5E:

1. **Two 16-bit DryOS heap bound addresses** (`0x000080f0` $\to$ `0x000080ec`, and `0x00008078` $\to$ `0x00008074`):
   Because both the original and corrected constants fit into a 16-bit unsigned integer ($0 \le c \le 0\text{xFFFF}$), GNU `as` assembles both into 4-byte Thumb-2 `movw` instructions in `.text`, without allocating any words in the literal pool.
   
   Disassembly comparison via `arm-none-eabi-objdump -d` on `boot_prototype.o`:
   - *Pre-PORT-5E (`fa2a094`)*:
     ```text
      1fc:	f248 00f0 	movw	r0, #33008	; 0x80f0
      200:	6801      	ldr	r1, [r0, #0]
      202:	f248 0078 	movw	r0, #32888	; 0x8078
     ```
   - *Post-PORT-5E (`f8cc7a9`)*:
     ```text
      1fc:	f248 00ec 	movw	r0, #33004	; 0x80ec
      200:	6801      	ldr	r1, [r0, #0]
      202:	f248 0074 	movw	r0, #32884	; 0x8074
     ```
   Each `movw` instruction occupies exactly 4 bytes in both versions ($\Delta = 0$ bytes) `[VERIFIED: objdump disassembly]`.

2. **Eight 32-bit ROM string addresses** (`0xfc05b604` $\to$ `0xfc05b600`, `0xfc05b614` $\to$ `0xfc05b610`, `0xfc05b634` $\to$ `0xfc05b630`, `0xfc05b63c` $\to$ `0xfc05b638`, `0xfc05b64c` $\to$ `0xfc05b648`, `0xfc05b660` $\to$ `0xfc05b65c`, `0xfc05b66c` $\to$ `0xfc05b668`, `0xfc05b678` $\to$ `0xfc05b674`):
   These ROM addresses exceed 16 bits and cannot be represented as modified Thumb-2 immediates. GNU `as` emits 2-byte PC-relative load instructions (`ldr rX, [pc, #offset]`) referencing 8 words allocated in the function's trailing literal pool.
   
   Disassembly comparison of the trailing literal pool in `boot_prototype.o`:
   - *Pre-PORT-5E (`fa2a094`)*:
     ```text
      380:	fc05b604 	.word	0xfc05b604
      384:	fc05b614 	.word	0xfc05b614
      388:	bfe10000 	.word	0xbfe10000
      38c:	fc05b634 	.word	0xfc05b634
      390:	fc05b63c 	.word	0xfc05b63c
      394:	fc05b64c 	.word	0xfc05b64c
      398:	fc05b660 	.word	0xfc05b660
      39c:	fc05b66c 	.word	0xfc05b66c
      3a0:	fc05b678 	.word	0xfc05b678
     ```
   - *Post-PORT-5E (`f8cc7a9`)*:
     ```text
      380:	fc05b600 	.word	0xfc05b600
      384:	fc05b610 	.word	0xfc05b610
      388:	bfe10000 	.word	0xbfe10000
      38c:	fc05b630 	.word	0xfc05b630
      390:	fc05b638 	.word	0xfc05b638
      394:	fc05b648 	.word	0xfc05b648
      398:	fc05b65c 	.word	0xfc05b65c
      39c:	fc05b668 	.word	0xfc05b668
      3a0:	fc05b674 	.word	0xfc05b674
     ```
   Updating these 8 addresses altered the 32-bit values stored in the pool in-place; it did not change the number of pool entries (8 words = 32 bytes in both versions, $\Delta = 0$ bytes) `[VERIFIED: objdump disassembly]`.

#### 6.4.2 Comparative Before/After Link Evidence
To establish empirical link evidence verifying section-size invariance across PORT-5E (Option a), the boot prototype was built at both the commit immediately preceding PORT-5E (`fa2a09420aba025654d55138a7752eca89322fd7`, parent of PR #5) and at the PORT-5E commit (`f8cc7a9743a768351c6e95e80d956f3ee52dbd09`) in isolated scratch worktrees using the pinned toolchain (`toolchains/gcc-arm-none-eabi-5_4-2016q3`) and the local build script (`tools/build_prototype.py`).

##### 1. Pre-PORT-5E Build Evidence
- **Git Commit SHA**: `fa2a09420aba025654d55138a7752eca89322fd7`
- **Build Command**:
  ```bash
  python3 -B tools/build_prototype.py
  ```
- **Section Size Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-size chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
  ```text
     text	   data	    bss	    dec	    hex	filename
    75020	  41796	   6828	 123644	  1e2fc	chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
- **Section Headers Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump -h chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
  ```text
  Sections:
  Idx Name          Size      VMA       LMA       File off  Algn
    0 .text         00012428  003489b4  003489b4  00000054  2**3
                    CONTENTS, ALLOC, LOAD, CODE
    1 .text.unlikely 000000e4  0035addc  0035addc  0001247c  2**2
                    CONTENTS, ALLOC, LOAD, READONLY, CODE
    2 .data         0000a344  0035aec0  0035aec0  00012560  2**4
                    CONTENTS, ALLOC, LOAD, DATA
    3 .bss          00001aac  00365204  00365204  0001c8a4  2**2
                    ALLOC
    4 .ARM.attributes 0000002b  00000000  00000000  0001c8a4  2**0
                    CONTENTS, READONLY
    5 .comment      0000006e  00000000  00000000  0001c8cf  2**0
                    CONTENTS, READONLY
    6 .debug_frame  00000060  00000000  00000000  0001c940  2**2
                    CONTENTS, READONLY, DEBUGGING
  ```
- **Symbol Address Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm chdk-port/platform/g3x/sub/110c/prototype_main.elf | grep boot_witness
  ```
  ```text
  0035f7a0 D boot_witness
  ```
  `[VERIFIED: pre-PORT-5E link output at commit fa2a094]`

##### 2. Post-PORT-5E Build Evidence
- **Git Commit SHA**: `f8cc7a9743a768351c6e95e80d956f3ee52dbd09`
- **Build Command**:
  ```bash
  python3 -B tools/build_prototype.py
  ```
- **Section Size Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-size chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
  ```text
     text	   data	    bss	    dec	    hex	filename
    75020	  41796	   6828	 123644	  1e2fc	chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
- **Section Headers Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump -h chdk-port/platform/g3x/sub/110c/prototype_main.elf
  ```
  ```text
  Sections:
  Idx Name          Size      VMA       LMA       File off  Algn
    0 .text         00012428  003489b4  003489b4  00000054  2**3
                    CONTENTS, ALLOC, LOAD, CODE
    1 .text.unlikely 000000e4  0035addc  0035addc  0001247c  2**2
                    CONTENTS, ALLOC, LOAD, READONLY, CODE
    2 .data         0000a344  0035aec0  0035aec0  00012560  2**4
                    CONTENTS, ALLOC, LOAD, DATA
    3 .bss          00001aac  00365204  00365204  0001c8a4  2**2
                    ALLOC
    4 .ARM.attributes 0000002b  00000000  00000000  0001c8a4  2**0
                    CONTENTS, READONLY
    5 .comment      0000006e  00000000  00000000  0001c8cf  2**0
                    CONTENTS, READONLY
    6 .debug_frame  00000060  00000000  00000000  0001c940  2**2
                    CONTENTS, READONLY, DEBUGGING
  ```
- **Symbol Address Command & Verbatim Output**:
  ```bash
  toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm chdk-port/platform/g3x/sub/110c/prototype_main.elf | grep boot_witness
  ```
  ```text
  0035f7a0 D boot_witness
  ```
  `[VERIFIED: post-PORT-5E link output at commit f8cc7a9]`

##### 3. Empirical Conclusion on Size Invariance
The side-by-side link outputs prove that:
1. `.text` size (`0x00012428` = 74,792 B), `.text.unlikely` size (`0x000000e4` = 228 B), total text segment (`75020` B), `.data` size (`0x0000a344` = 41,796 B), and `.bss` size (`0x00001aac` = 6,828 B) remained byte-for-byte identical ($\Delta = 0$ bytes) across PORT-5E `[VERIFIED: comparative build link outputs]`.
2. The section boundary between `.text` and `.data` remained at `0x0035AEC0` `[VERIFIED: comparative objdump -h]`.
3. Consequently, `boot_witness` remained completely undisturbed at `0x0035F7A0` before and after PORT-5E `[VERIFIED: comparative nm outputs]`.

---

## 7. Evidence and Claim Classification Ledger

| # | Topic / Claim | Value / Citation | Classification |
|---|---|---|---|
| 1 | Git Base Commit SHA (`origin/main`) | `3d8794e136ecc03919f2da5bb3f5d034eae500e5` (`git rev-parse origin/main`) | `VERIFIED` |
| 2 | Git HEAD SHA | `3d8794e136ecc03919f2da5bb3f5d034eae500e5` (`git rev-parse HEAD`) | `VERIFIED` |
| 3 | ARM Toolchain Version | GCC 5.4.1 20160919 (release) [ARM/embedded-5-branch revision 240496] | `VERIFIED` |
| 4 | Build Command | `python3 -B tools/bootstrap_chdk_platform.py && python3 -B tools/build_prototype.py` | `VERIFIED` |
| 5 | Derived `boot_witness` Address | `0x0035F7A0` (type `D`, size 32 B, 16-byte aligned in `.data`) | `VERIFIED` |
| 6 | Candidate Builder Assertion | `assert witness_addr == 0x0035F780` (`tools/build_candidate_port2a.py:223`) | `VERIFIED` |
| 7 | Candidate Validator Assertion | `assert syms.get("boot_witness") == 0x0035F780` (`tools/validate_candidate_port2a.py:112`) | `VERIFIED` |
| 8 | Numerical Address Divergence | Current prototype witness (`0x0035F7A0`) differs by `+0x20` (+32 B) from historical candidate assertion (`0x0035F780`) | `VERIFIED` |
| 8b | Stale Builder Assertion | `tools/build_candidate_port2a.py:223` asserts `0x0035F780` but compiles current source (`lines 70-71, 127-144`), causing an assertion mismatch against current source | `VERIFIED` |
| 9 | Tracked SD Audit Claim | `boot_witness relocated from 0x0035F780 to 0x0035F7A0` (`docs/RESTART_SD_HOST_AUDIT.md:248`) | `VERIFIED` |
| 10 | Tracked Manifest Claim | `boot_witness @ 0x0035F7A0` (`docs/REPRODUCIBILITY_MANIFEST.md:80`) | `VERIFIED` |
| 11 | Tracked State & Handoff Claim | `boot_witness moved from 0x0035F780 to 0x0035F7A0` (`docs/PROJECT_STATE.md:133`, `docs/HANDOFF.md:228`) | `VERIFIED` |
| 12 | Tracked Matrix Claim | Prototype ELF places witness at `0x0035F7A0` (`docs/PORT3C_RESTART_READINESS_MATRIX.md:231`) | `VERIFIED` |
| 13 | Tracked Codex Review Claim | SD audit describes witness at `0x0035F7A0` (`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`) | `VERIFIED` |
| 14 | Linker Placement of `.data` | Contiguous layout starting at `link_text_end` (`chdk-port/tools/link-boot.ld:14-26`) | `VERIFIED` |
| 15 | Map Boundaries for Corrected Build | `link_text_end = 0x0035aec0`, `link_data_start = 0x0035aec0` (`prototype_main.map:1312-1315`) | `VERIFIED` |
| 16 | PR #2 Source Additions | PR #2 added instructions to `boot_prototype.c` and stubs to `stubs_prototype.S` (`git show 2590036; patches/0001-sd1stinit-restart-prototype.patch:22-58`) | `VERIFIED` |
| 16b | Causal Shift Attribution (+0x20 to `0x0035F7A0`) | Claim that PR #2 additions shifted `link_text_end`/`link_data_start` by `+0x20`, moving `boot_witness` from `0x0035F780` to `0x0035F7A0` | `INFERRED` |
| 17 | Byte Accounting Breakdown for PR #2 | 14 B (`boot_prototype.c`) + 16 B (`stubs_prototype.S`) + 2 B alignment = 32 B | `INFERRED` |
| 18 | Cause: PORT-5E in PR #5 | Literal corrections in sub_fc05b558_my; comparative link outputs at fa2a094 vs f8cc7a9 verify zero section delta ($\Delta = 0$ B) and identical witness at 0x0035F7A0 (§6.4) | `VERIFIED` |
| 19 | Preserved Historical Candidate `.text` End Bound | `link_text_end = 0x0035AEA0` calculated from candidate section delta | `INFERRED` |

---

## 8. Safety and Governance Audit

- **Phase 0 Compliance**: This task operated exclusively on source files, local build tooling, and compiler link outputs. Strictly zero ROM reads, zero firmware modifications, and zero camera operations occurred `[VERIFIED]`.
- **Artifact Hygiene**: No binaries (`.bin`), object files (`.o`, `.a`), ELF executables (`.elf`), or linker map files (`.map`) are committed to Git. Only documentation (`docs/PORT16_WITNESS_ADDRESS.md`) is tracked `[VERIFIED]`.
- **Hardware Status**: **STRICT NO-GO**.

---

## 9. Conclusion

1. **Derived Address**: Direct build of the corrected boot prototype from `chdk-port/platform/g3x/sub/110c/` using the pinned toolchain (`gcc-arm-none-eabi-5_4-2016q3`) verifies `boot_witness` at **`0x0035F7A0`** (`.data` section, 16-byte aligned) `[VERIFIED: prototype_main.elf nm; prototype_main.map:1431-1432]`.
2. **Comparison with Candidate Assertion (`0x0035F780`)**:
   - The assertion `witness_addr == 0x0035F780` in `tools/build_candidate_port2a.py:223` is **stale against the corrected source**. The builder compiles the current working-tree source files (`tools/build_candidate_port2a.py:70-71, 127-144`), which produces `0x0035F7A0`, so its own assertion would fail or mismatch if run `[VERIFIED: tools/build_candidate_port2a.py:70-71, 127-144, 216-224]`.
   - Distinct from the builder's current compilation behavior, preserved historical candidate artifacts (`candidate_port2a/candidate_main.elf`, `candidate_port2a/candidate_main.bin`, `docs/REPRODUCIBILITY_MANIFEST.md:71-78`, `docs/PROJECT_STATE.md:60`) preserve the original pre-correction baseline (`0x0035F780`) from prior to PR #2 `[VERIFIED]`.
3. **Comparison with Tracked Documentation (`0x0035F7A0`)**: The derived address matches all tracked prototype documentation with 100% precision (`docs/RESTART_SD_HOST_AUDIT.md:248`, `docs/REPRODUCIBILITY_MANIFEST.md:80`, `docs/PROJECT_STATE.md:133`, `docs/HANDOFF.md:228`, `docs/PORT3C_RESTART_READINESS_MATRIX.md:231`, `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`) `[VERIFIED]`.
4. **Relocation Attribution**: PR #2 added Thumb-2 instructions in `boot_prototype.c` and stubs in `stubs_prototype.S` (`VERIFIED: git show 2590036`). The causal attribution that these additions expanded `.text` and shifted `link_text_end`/`link_data_start` forward by `+0x20` (moving `boot_witness` from `0x0035F780` to `0x0035F7A0`), together with the internal byte accounting breakdown ($14 + 16 + 2 = 32$ B), is `INFERRED`. In PORT-5E (PR #5), comparative prototype builds at the pre-PORT-5E commit (`fa2a094`) and PORT-5E commit (`f8cc7a9`) verify that assembled section sizes were byte-for-byte identical ($\Delta = 0$ B) and `boot_witness` remained at `0x0035F7A0` (`VERIFIED: comparative build link outputs §6.4`).
