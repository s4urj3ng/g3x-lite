# PORT-15 — First-Boot Inventory of Tracked Sources for `boot_witness` Address Discrepancy

- **Task**: `p15-firstboot-inventory` (`PORT-15 inventory of tracked sources for the boot_witness address discrepancy (prep for first-boot milestone)`) `[VERIFIED]`
- **Hardware Status**: **STRICT NO-GO** (Phase 0 read-only investigation regarding firmware and camera hardware; zero ROM reads, zero builds, zero hardware operations) `[VERIFIED: docs/SAFETY.md:1-8]`.
- **Evidence Source Policy**: All facts in this inventory are gathered strictly from Git-tracked repository files using read-only git operations (`git ls-files`, `git grep`, `git show`, `git log`) and Python 3 standard library scripts inspecting tracked text files `[VERIFIED]`. No proprietary ROM bytes or `firmware/dumps/` files have been accessed or cited `[VERIFIED]`.
- **Epistemic Classification Policy**: Every statement, table row, and conclusion is explicitly classified as `VERIFIED`, `INFERRED`, or `UNKNOWN` per repository contract `[VERIFIED: AGENTS.md:15-18]`. No firmware address is inferred unless quoted directly from a tracked repository source `[VERIFIED]`.

---

## Executive Summary & Discrepancy Architecture

The Canon PowerShot G3 X (`GM1.10C`) CHDK first-boot candidate codebase exhibits an address divergence for the non-persistent RAM witness structure `boot_witness`:

1. **Candidate Target Address (`0x0035F780`)**: Preserved first-boot candidate documentation and inspector metadata target `boot_witness` at `0x0035F780` `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:76-77; docs/PROJECT_STATE.md:93, 135; docs/HANDOFF.md:186, 340; firmware/tools/witness_inspector_metadata.json:4]`.
2. **Remediated Prototype Target Address (`0x0035F7A0`)**: Adding 14 bytes of Thumb-2 instructions for `SD1stInit` task creation (`sub_fc05c4e0` gate check + `sub_fc31b1f4` ARM veneer invocation) in `chdk-port/platform/g3x/sub/110c/boot_prototype.c` and `stubs_prototype.S` expanded the `.text` segment, shifting the 16-byte-aligned `.data` section forward by +32 bytes (`+0x20`), which relocated `boot_witness` from `0x0035F780` to `0x0035F7A0` in `prototype_main.elf` `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:247-250; docs/PROJECT_STATE.md:133-134; docs/HANDOFF.md:228-229]`.
3. **Pre-Correction Invariance**: `candidate_port2a/` artifacts were generated during milestone `CHDK-PORT-2A` (2026-10-24) prior to `SD1stInit` remediation (PR #2) and prior to `PORT-5E` early boot literal corrections (PR #5). Under strict Phase 0 invariants, these candidate artifacts remain frozen **PRE-CORRECTION** artifacts and must not be mutated or claimed to represent the remediated prototype source `[VERIFIED: docs/REPRODUCIBILITY_MANIFEST.md:71-74; docs/PROJECT_STATE.md:60; docs/HANDOFF.md:67]`.
4. **Dynamic Address Decoupling**: In commit `5d644cbd` (PR #1), the hardcoded address dependency was eliminated from offline tooling: `tools/build_witness_inspector.py` and `tools/validate_witness_inspector.py` resolve the witness address dynamically from the active target ELF (`arm-none-eabi-nm`) and enforce 3-way consistency across the ELF symbol, metadata JSON, and inspector binary opcodes `[VERIFIED: docs/PROJECT_STATE.md:93; docs/HANDOFF.md:186-192; tools/build_witness_inspector.py:39-76; tools/validate_witness_inspector.py:89-108]`.

---

## 1. Tracked Locations Stating, Asserting, or Deriving `boot_witness` Address and Offsets

Across all Git-tracked files in the repository, exactly **26** line occurrences reference `0x0035F780` and **9** line occurrences reference `0x0035F7A0` (with 5 lines referencing both, yielding 30 distinct lines) `[VERIFIED: git grep -n]`.

### 1.1 Complete Census of Tracked References to `0x0035F780`

| Tracked File | Line | Exact Quoted Text | Value Stated | Classification |
|---|---|---|---|---|
| `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md` | 66 | `\| C09 \| SD audit §8.2 describes a prototype witness at `0x0035F7A0`; current inspector metadata targets the candidate at `0x0035F780`. \| Different target artifacts, not automatically a validator defect. Candidate/prototype evidence is not interchangeable. Any future observation must identify exact loaded loader/core and matching inspector target. Existing metadata and the manifest document which target is intended. \|` | `0x0035F780` (candidate) & `0x0035F7A0` (prototype) | `VERIFIED` |
| `docs/HANDOFF.md` | 186 | `- **Objective**: Eliminate hardcoded `0x0035F780` witness address dependency from offline build system, automatically resolve symbol address from `candidate_main.elf`, generate inspector payload and metadata, enforce 3-way consistency rejection, and test with simulated symbol address changes and linker output verification.` | `0x0035F780` (candidate baseline) | `VERIFIED` |
| `docs/HANDOFF.md` | 188 | `  1. **Dynamic Symbol Extraction**: `extract_witness_addr_from_elf` parses `candidate_main.elf` symbol table via `arm-none-eabi-nm`, confirming `boot_witness` address (`0x0035F780`), type (`D`), and 4-byte/16-byte alignment. Fails closed without silent fallback.` | `0x0035F780` (extracted from ELF) | `VERIFIED` |
| `docs/HANDOFF.md` | 189 | `  2. **Dynamic Assembly Injection**: `witness_inspector_payload.S` uses `movw r7, #:lower16:BOOT_WITNESS_ADDR` and `movt r7, #:upper16:BOOT_WITNESS_ADDR`. `build_witness_inspector.py` supplies `-DBOOT_WITNESS_ADDR=0x...` at assembly time. When pointing to `0x0035F780`, generated binary is 100% bit-for-bit identical (444 bytes).` | `0x0035F780` (injected assembly macro) | `VERIFIED` |
| `docs/HANDOFF.md` | 192 | `  5. **Elimination of Address Pinning in Tests (Review Finding 3)**: General test assertions and mismatch tests dynamically derive expected and mismatched addresses from active candidate ELF or simulated ELFs rather than hardcoding `0x0035F780` or arbitrary literals.` | `0x0035F780` (removed hardcoding) | `VERIFIED` |
| `docs/HANDOFF.md` | 228 | `  - Adding 14 bytes to prototype `.text` moved `prototype_main.elf` `.data` by +32 bytes (16-byte aligned): `boot_witness` moved from `0x0035F780` to `0x0035F7A0` (type `D`).` | `0x0035F780` (initial) & `0x0035F7A0` (remediated) | `VERIFIED` |
| `docs/HANDOFF.md` | 340 | `     - Associated Canon Basic inspector (444 B binary) with candidate metadata, binding to `boot_witness` @ `0x0035F780`.` | `0x0035F780` (inspector binding) | `VERIFIED` |
| `docs/HANDOFF.md` | 388 | `     - Implemented `firmware/tools/witness_inspector_payload.S` (assembled into 364 B binary) reading `boot_witness_t` at physical address `0x0035F780`.` | `0x0035F780` (early inspector prototype) | `VERIFIED` |
| `docs/HANDOFF.md` | 398 | `     - Witness address `0x0035F780` resides in MPU Region 0 (`DRACR = 0x0121`, Inner Write-Back, Write-Allocate Cacheable).` | `0x0035F780` (MPU attribute audit) | `VERIFIED` |
| `docs/HANDOFF.md` | 426 | `  1. **Q1 Witness Placement & Memory Lifetime (ACCEPTED / PASS)**: Linker ownership at `0x0035F780` in `.data` accepted by Codex.` | `0x0035F780` (accepted linker ownership) | `VERIFIED` |
| `docs/HANDOFF.md` | 455 | `     - Implemented `boot_witness` with dedicated linker ownership via `__attribute__((aligned(16), section(".data")))` in `boot_prototype.c` at `0x0035F780`.` | `0x0035F780` (linker placement) | `VERIFIED` |
| `docs/PORT14_Q_MEM03_BSS.md` | 124 | `\| `docs/PROJECT_STATE.md:206` \| `0x3F4F4..0x3489B4` (start-to-limit range) \| `1. **Dedicated Linker Ownership & Placement Invariants (PROVEN)**: Audited proposed region `0x0035ADE0..0x003650F8` and proved it is active CHDK `.data` containing `sounds` (`0x0035ADE0`) and `new_sa` (`0x0035AE00`). Writing arbitrarily corrupts `new_sa` and crashes the DryOS allocator. Instantiated `boot_witness` with dedicated linker ownership via `__attribute__((aligned(16), section(".data")))` at `0x0035F780`. Proved absolute immunity from Canon low-RAM copy (`0x8000..0x3F4F4`), Canon BSS zeroing (`0x3F4F4..0x3489B4`), CHDK BSS zeroing (`0x003651E4..0x00366C90`), and shifted DryOS heap (`>= 0x00366C90`).` \|` | `0x0035F780` (memory safety proof) | `VERIFIED` |
| `docs/PORT3C_RESTART_READINESS_MATRIX.md` | 231 | `\| **C09** \| Witness Address Target Divergence \| SD audit describes witness at `0x0035F7A0`; inspector metadata targets `0x0035F780`. \| Different targets: prototype ELF places witness at `0x0035F7A0`; preserved candidate ELF places it at `0x0035F780`. \| **RESOLVED**. Dynamic witness tooling extracts address from active target ELF; candidate and prototype targets must not be conflated. \|` | `0x0035F780` (candidate) & `0x0035F7A0` (prototype) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 93 | `- **Dynamic Address Extraction**: Removed hardcoded `0x0035F780` dependency from offline build tooling. Symbol address for `boot_witness` is resolved dynamically from `candidate_main.elf` (or configured ELF) using the ARM toolchain (`arm-none-eabi-nm`).` | `0x0035F780` (toolchain decoupling) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 133 | `  - Adding 14 bytes to prototype `.text` moved `prototype_main.elf` `.data` by +32 bytes (16-byte aligned): `boot_witness` moved from `0x0035F780` to `0x0035F7A0` (type `D`).` | `0x0035F780` (initial) & `0x0035F7A0` (remediated) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 135 | `  - Production files (`chdk-port/platform/g3x/sub/110c/boot.c`, `loader/g3x/main.c`, `bin/DISKBOOT.BIN`) and candidate artifacts in `candidate_port2a/` remain 100% byte-identical skeletons (`boot_witness` @ `0x0035F780`).` | `0x0035F780` (preserved candidate skeleton) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 179 | `5. **Inspector Association (PASS)**: Bound Canon Basic inspector (444 B binary) to `boot_witness` @ `0x0035F780`. Classified as `CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED` in Yellow (`Color 4`). Zero Green (`Color 2`).` | `0x0035F780` (inspector association) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 191 | `1. **Isolated Inspector Prototype (PASS)**: Built `witness_inspector_payload.S` (assembled to 364 B binary) reading `boot_witness_t` at physical address `0x0035F780`. Validates header magic (`0x5749544E`), version (`0x00010001`), stage monotonic progression, and cascaded checksum. Never outputs `BOOT_SUCCESS` or `CONTINUATION_CONFIRMED` from witness data alone.` | `0x0035F780` (early inspector binary) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 199 | `1. **Q1 Witness Placement & Lifetime (ACCEPTED / PASS)**: Linker ownership at `0x0035F780` in `.data` accepted by Codex.` | `0x0035F780` (accepted linker ownership) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 206 | `1. **Dedicated Linker Ownership & Placement Invariants (PROVEN)**: Audited proposed region `0x0035ADE0..0x003650F8` and proved it is active CHDK `.data` containing `sounds` (`0x0035ADE0`) and `new_sa` (`0x0035AE00`). Writing arbitrarily corrupts `new_sa` and crashes the DryOS allocator. Instantiated `boot_witness` with dedicated linker ownership via `__attribute__((aligned(16), section(".data")))` at `0x0035F780`. Proved absolute immunity from Canon low-RAM copy (`0x8000..0x3F4F4`), Canon BSS zeroing (`0x3F4F4..0x3489B4`), CHDK BSS zeroing (`0x003651E4..0x00366C90`), and shifted DryOS heap (`>= 0x00366C90`).` | `0x0035F780` (memory safety proof) | `VERIFIED` |
| `docs/REPRODUCIBILITY_MANIFEST.md` | 76 | `\| **Candidate Loader Binary** \| `candidate_port2a/candidate_loader.bin` \| 117,968 \| `bac0431c2e896cb5e9a761f66d4aaaad0676af11a28335c602367539574c72bf` \| Unmodified first-boot candidate loader (`boot_witness` @ `0x0035F780`). Protected artifact. \|` | `0x0035F780` (candidate loader manifest) | `VERIFIED` |
| `docs/REPRODUCIBILITY_MANIFEST.md` | 77 | `\| **Candidate Core Binary** \| `candidate_port2a/candidate_main.bin` \| 116,784 \| `e6f823d1c4e40ff03bc923d423946f6da4bd412b18ae1ac68d0553a5055d7fd5` \| Unmodified first-boot candidate core (`boot_witness` @ `0x0035F780`). Protected artifact. \|` | `0x0035F780` (candidate core manifest) | `VERIFIED` |
| `docs/RESTART_SD_HOST_AUDIT.md` | 248 | `  - `boot_witness` relocated from `0x0035F780` to `0x0035F7A0` (16-byte aligned, type `D`).` | `0x0035F780` (pre-remediation baseline) | `VERIFIED` |
| `docs/RESTART_SD_HOST_AUDIT.md` | 253 | `  - `candidate_port2a/` witness address remains pinned at `0x0035F780` and passes candidate validation.` | `0x0035F780` (frozen candidate artifact) | `VERIFIED` |
| `firmware/tools/witness_inspector_metadata.json` | 4 | `  "witness_address": "0x0035F780",` | `0x0035F780` (inspector address metadata) | `VERIFIED` |
| `tests/test_validate_witness_inspector.py` | 54 | `        # Dynamically check the derived symbol address rather than hardcoded 0x0035F780` | `0x0035F780` (test code comment) | `VERIFIED` |

### 1.2 Complete Census of Tracked References to `0x0035F7A0`

| Tracked File | Line | Exact Quoted Text | Value Stated | Classification |
|---|---|---|---|---|
| `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md` | 66 | `\| C09 \| SD audit §8.2 describes a prototype witness at `0x0035F7A0`; current inspector metadata targets the candidate at `0x0035F780`. \| Different target artifacts, not automatically a validator defect. Candidate/prototype evidence is not interchangeable. Any future observation must identify exact loaded loader/core and matching inspector target. Existing metadata and the manifest document which target is intended. \|` | `0x0035F7A0` (prototype target) | `VERIFIED` |
| `docs/HANDOFF.md` | 228 | `  - Adding 14 bytes to prototype `.text` moved `prototype_main.elf` `.data` by +32 bytes (16-byte aligned): `boot_witness` moved from `0x0035F780` to `0x0035F7A0` (type `D`).` | `0x0035F7A0` (remediated prototype) | `VERIFIED` |
| `docs/HANDOFF.md` | 229 | `  - Dynamic witness inspector (`build_witness_inspector.py` / `validate_witness_inspector.py`) automatically extracted, assembled, and verified 3-way consistency for `prototype_main.elf` @ `0x0035F7A0`.` | `0x0035F7A0` (dynamic validation target) | `VERIFIED` |
| `docs/PORT3C_RESTART_READINESS_MATRIX.md` | 231 | `\| **C09** \| Witness Address Target Divergence \| SD audit describes witness at `0x0035F7A0`; inspector metadata targets `0x0035F780`. \| Different targets: prototype ELF places witness at `0x0035F7A0`; preserved candidate ELF places it at `0x0035F780`. \| **RESOLVED**. Dynamic witness tooling extracts address from active target ELF; candidate and prototype targets must not be conflated. \|` | `0x0035F7A0` (prototype target) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 133 | `  - Adding 14 bytes to prototype `.text` moved `prototype_main.elf` `.data` by +32 bytes (16-byte aligned): `boot_witness` moved from `0x0035F780` to `0x0035F7A0` (type `D`).` | `0x0035F7A0` (remediated prototype) | `VERIFIED` |
| `docs/PROJECT_STATE.md` | 134 | `  - Dynamic witness inspector (`build_witness_inspector.py` / `validate_witness_inspector.py`) automatically extracted, assembled, and verified 3-way consistency for `prototype_main.elf` @ `0x0035F7A0`.` | `0x0035F7A0` (dynamic validation target) | `VERIFIED` |
| `docs/REPRODUCIBILITY_MANIFEST.md` | 80 | `\| **Prototype Core Binary** \| `chdk-port/platform/g3x/sub/110c/prototype_main.bin` \| 116,816 \| `49a2fde902c9e86b49a0533256a174d791f1bdced26c8521ea7dd6f945fb16ad` \| Remediated `SD1stInit` prototype (+32 bytes; `boot_witness` @ `0x0035F7A0`). \|` | `0x0035F7A0` (prototype manifest entry) | `VERIFIED` |
| `docs/RESTART_SD_HOST_AUDIT.md` | 248 | `  - `boot_witness` relocated from `0x0035F780` to `0x0035F7A0` (16-byte aligned, type `D`).` | `0x0035F7A0` (remediated prototype ELF) | `VERIFIED` |
| `docs/RESTART_SD_HOST_AUDIT.md` | 251 | `  - `tools/build_witness_inspector.py` automatically resolves `0x0035F7A0` from `prototype_main.elf` and generates bit-for-bit matching MOVW/MOVT opcodes.` | `0x0035F7A0` (automatic toolchain resolution) | `VERIFIED` |

### 1.3 Tracked Locations Stating or Deriving SD1stInit-Related Offsets

1. **Addition of 14 Bytes of Code**:
   - `docs/RESTART_SD_HOST_AUDIT.md:247`: `- Adding 14 bytes of code and stubs to the prototype shifts .data in prototype_main.elf by +32 bytes (16-byte aligned):` `[VERIFIED]`.
   - `docs/HANDOFF.md:228` and `docs/PROJECT_STATE.md:133`: `- Adding 14 bytes to prototype .text moved prototype_main.elf .data by +32 bytes (16-byte aligned): boot_witness moved from 0x0035F780 to 0x0035F7A0 (type D).` `[VERIFIED]`.
   - `patches/0001-sd1stinit-restart-prototype.patch:49-56` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:392-398`:
     ```arm
     "    movs    r0, #0\n"        // 2 bytes: Thumb-2 16-bit movs
     "    bl      sub_fc05c4e0\n"  // 4 bytes: Thumb-2 32-bit bl
     "    lsls    r0, r0, #31\n"   // 2 bytes: Thumb-2 16-bit lsls
     "    bne     1f\n"            // 2 bytes: Thumb-2 16-bit bne
     "    blx     sub_fc31b1f4\n"  // 4 bytes: Thumb-2 32-bit blx (ARM veneer)
     "1:\n"
     ```
     Total inline assembly instructions added: 2 + 4 + 2 + 2 + 4 = **14 bytes** `[VERIFIED]`.
   - `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:65`: `STUB2(fc31b1f4)` registers the ARM veneer call `[VERIFIED]`.

2. **Shift of `.data` by +32 Bytes (`+0x20`)**:
   - Because `boot_witness` is declared with `__attribute__((aligned(16), section(".data")))` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:27`), and because `.data` is linked after `.text`, expanding `.text` by 14 bytes crossed a 16-byte alignment boundary, advancing the start of `.data` and all symbols within it by +32 bytes (`0x20` bytes) `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:247-250]`.
   - Section bounds shift recorded in `docs/RESTART_SD_HOST_AUDIT.md:250`:
     - `link_data_start = 0x0035AEC0`
     - `link_bss_start = 0x00365204`
     - `_end = 0x00366CB0` (shifted from candidate `0x00366C90` by exactly +32 bytes) `[VERIFIED]`.
   - Binary size shift recorded in `docs/REPRODUCIBILITY_MANIFEST.md:77, 80`:
     - Candidate core (`candidate_main.bin`): `116,784` bytes (`boot_witness` @ `0x0035F780`) `[VERIFIED]`.
     - Prototype core (`prototype_main.bin`): `116,816` bytes (`boot_witness` @ `0x0035F7A0`) `[VERIFIED]`.
     - Exact difference: `116,816 - 116,784 = 32` bytes (`+0x20` bytes) `[VERIFIED]`.

---

## 2. Tracked Docs and Commits Establishing the Corrected Value

The corrected address (`0x0035F7A0`) and its underlying early boot literal corrections (`PORT-5E`) were established through the following Git commits on `origin/main` `[VERIFIED: git log]`:

### 2.1 Git Commit Provenance Log

| Milestone / PR | Commit SHA | Date | Author / Description | Tracked Deliverables / Citations |
|---|---|---|---|---|
| **PR #1 (Dynamic Witness Tooling)** | `5d644cbd1915a47cb12c257f032df436867043a5` | 2026-10-25 | avp: `feat(build): dynamic RAM witness address resolution and 3-way consistency validator` | `tools/build_witness_inspector.py`, `tools/validate_witness_inspector.py`, `tests/test_validate_witness_inspector.py`, `firmware/tools/witness_inspector_metadata.json`, `firmware/tools/witness_inspector_payload.S`, `firmware/tools/witness_inspector_payload.bin`; `docs/PROJECT_STATE.md:93`; `docs/HANDOFF.md:186-192` `[VERIFIED]` |
| **PR #2 (SD1stInit Investigation)** | `860d873c130f063ab75b69985ea096c21d6ed0b9` | 2026-10-25 | avp: `feat(sd-restart): investigate SD1stInit omission and implement isolated prototype call` | `docs/RESTART_SD_HOST_AUDIT.md` (lines 247-253 record `0x0035F780` -> `0x0035F7A0`), `tests/test_restart_sd_audit.py` `[VERIFIED]` |
| **PR #2 (Prototype Tracking)** | `e418ccfeb7dab8c0dd2db6b3b8d988beec2b5e60` | 2026-10-25 | avp: `fix(sd-restart): track prototype sources, add patch artifact, and reconcile MMIO bit semantics` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `stubs_prototype.S`, `boot_witness.h`, `patches/0001-sd1stinit-restart-prototype.patch` `[VERIFIED]` |
| **PR #2 Merge** | `25900369763851bbe3ede321f8395854a5dc9b4c` | 2026-10-25 | PHAM VAN AN: `Merge pull request #2 from s4urj3ng/feat/restart-sd1stinit-prototype` | Merged `feat/restart-sd1stinit-prototype` into `main` `[VERIFIED]` |
| **Audit Reproducibility** | `a9ead89aa735845cee66e2ed270e33c7688c5b71` | 2026-10-25 | avp: `docs(audit): add reproducibility manifest and separate clean-checkout vs offline tests` | `docs/REPRODUCIBILITY_MANIFEST.md` (lines 71-80 record candidate pre-correction status vs prototype @ `0x0035F7A0`) `[VERIFIED]` |
| **PORT-5E (PR #5)** | `f8cc7a9743a768351c6e95e80d956f3ee52dbd09` | 2026-10-25 | PHAM VAN AN: `fix(boot): ROM-verified early boot literal corrections in sub_fc05b558_my (#5)` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:268-288`, `tests/test_early_boot_literals.py`, `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md`, `docs/PORT5A_RANMA_PORT_RECOVERY.md`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md`, `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md`, `docs/PROJECT_STATE.md:51-62`, `docs/HANDOFF.md:93-106` `[VERIFIED]` |

### 2.2 Mechanism and Documented History of the Correction

1. **`SD1stInit` Task Creation Addition (PR #2)**:
   - In stock firmware, `StartDiskboot` (`0xFC05BBEA`) spawns `"SD1stInit"` via veneer `0xFC31B1F4` before loading `DISKBOOT.BIN` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:387-390; tests/test_restart_sd_audit.py:77]`.
   - The initial CHDK port prototype (`boot.c`) omitted `StartDiskboot` to bypass reloading the bootloader, leaving `SD1stInit` unspawned on the restart path `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:68]`. The consequence that the SD controller is left un-reinitialized is `UNKNOWN`, as `docs/RESTART_SD_HOST_AUDIT.md:71-73` itself leaves compensating initialisation (`0xFC07564E` → `0x010E1A92`) and the actual runtime effect of the omission unverified `[UNKNOWN]`.
   - PR #2 added the gated call to `sub_fc31b1f4` in `boot_prototype.c:392-398` and stub `STUB2(fc31b1f4)` in `stubs_prototype.S:65` (14 bytes added to `.text`) `[VERIFIED]`.
   - This 14-byte code growth pushed `.data` across a 16-byte alignment boundary by +32 bytes (`+0x20`), shifting `boot_witness` from `0x0035F780` to `0x0035F7A0` in `prototype_main.elf` `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:247-250]`.

2. **PORT-5E Early Boot Literal Corrections (PR #5)**:
   - Corrected 10 literals in `sub_fc05b558_my` in `boot_prototype.c:268-288` (check words `0x80EC` / `0x8074` and strings `0xFC05B600..0xFC05B674`), eliminating a systematic +4 transcription offset from earlier drafts `[VERIFIED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:185, 244; tests/test_early_boot_literals.py:47-60]`.
   - These literal changes were value corrections in-place within the existing literal pool in `boot_prototype.c:268-288` without adding or removing instructions; `.text` size is therefore `INFERRED` to remain unchanged based on instruction count invariance. However, because no tracked post-PORT-5E ELF or symbol map exists in the repository for that exact revision (`docs/agentbridge/PORT15_LEDGER.md:60-65` shows only merge and file provenance), the post-correction `boot_witness` placement remains `UNKNOWN` until a rebuild confirms it `[INFERRED / UNKNOWN]`.
   - `docs/REPRODUCIBILITY_MANIFEST.md:71-74` explicitly classified `candidate_port2a/` artifacts as **PRE-CORRECTION** artifacts built prior to both PR #2 and PR #5, freezing them at `0x0035F780` to preserve build reproducibility `[VERIFIED]`.

---

## 3. Tools and Tests Consuming or Validating the Candidate

### 3.1 Untracked Candidate Build and Validation Scripts

The candidate builder script `tools/build_candidate_port2a.py` and validator script `tools/validate_candidate_port2a.py` are untracked and git-ignored working-tree files:

1. **Untracked Status (`git ls-files --error-unmatch`)**:
   ```bash
   $ git ls-files --error-unmatch tools/build_candidate_port2a.py
   error: pathspec 'tools/build_candidate_port2a.py' did not match any file(s) known to git
   Did you forget to 'git add'?
   [exit code: 1]

   $ git ls-files --error-unmatch tools/validate_candidate_port2a.py
   error: pathspec 'tools/validate_candidate_port2a.py' did not match any file(s) known to git
   Did you forget to 'git add'?
   [exit code: 1]
   ```
   `[VERIFIED]`

2. **Git-Ignored Status (`git check-ignore -v`)**:
   ```bash
   $ git check-ignore -v tools/build_candidate_port2a.py
   /srv/agentbridge/repos/g3x-lite/.git/info/exclude:1954:/tools/build_candidate_port2a.py	tools/build_candidate_port2a.py

   $ git check-ignore -v tools/validate_candidate_port2a.py
   /srv/agentbridge/repos/g3x-lite/.git/info/exclude:1965:/tools/validate_candidate_port2a.py	tools/validate_candidate_port2a.py
   ```
   `[VERIFIED]`

3. **Status of Script Contents, Hard-Coded Addresses, and Build Inputs**:
   Because `tools/build_candidate_port2a.py` and `tools/validate_candidate_port2a.py` are untracked and git-ignored, their file contents, any addresses they hard-code, and the build inputs they select are `UNKNOWN` for this tracked-only inventory and are deferred to the first-boot milestone `[UNKNOWN]`.

### 3.2 Tracked Tools and Tests Consuming or Validating the Candidate

The following table lists all Git-tracked tools, tests, and data files in the repository that consume, validate, or reference the candidate or prototype witness, noting the exact lines hard-coding any address `[VERIFIED: git ls-files]`:

| Tool / Test Path | Tracked in Git? | Role Regarding Candidate / Prototype | Hard-Coded Lines (`file:line`) & Quoted Text | Dynamic vs Hardcoded Behavior | Classification |
|---|---|---|---|---|---|
| `tools/build_witness_inspector.py` | **Yes** (`git ls-files`) | Assembles Canon Basic witness inspector payload with dynamic address injection | **None**: Line 180 supplies `-DBOOT_WITNESS_ADDR=0x{witness_addr:08X}` from dynamic ELF resolution | **Dynamic**: extracts `boot_witness` from ELF via `arm-none-eabi-nm` (lines 39-76, 172); does NOT hardcode `0x0035F780` or `0x0035F7A0`. | `VERIFIED` |
| `tools/validate_witness_inspector.py` | **Yes** (`git ls-files`) | Validates 3-way consistency across ELF symbol, inspector `.bin` opcodes, and metadata JSON | **None**: Line 554 provides CLI option `--expected-addr` (default `None`) | **Dynamic**: extracts address from binary MOVW/MOVT opcodes (lines 111-155), ELF symbol (lines 89-108), and metadata JSON (lines 204-215); verifies 3-way equality. | `VERIFIED` |
| `tests/test_validate_witness_inspector.py` | **Yes** (`git ls-files`) | Unit test suite (8 tests) validating witness inspector tooling | - Line 54 (comment only): `# Dynamically check the derived symbol address rather than hardcoded 0x0035F780` | **Dynamic**: extracts `expected_addr` dynamically from `CANDIDATE_MAIN_ELF` (lines 47, 65, 152, 183, 246, 267, 290, 325); tests mutation detection using dynamic offsets (`+0x1000`). | `VERIFIED` |
| `firmware/tools/witness_inspector_metadata.json` | **Yes** (`git ls-files`) | Metadata file accompanying candidate inspector binary | - Line 4: `"witness_address": "0x0035F780",`<br>- Line 5: `"witness_address_int": 3536768,` | **Hardcoded (Data)**: records address `0x0035F780` matching candidate core ELF. | `VERIFIED` |
| `firmware/tools/witness_inspector_payload.bin` | **Yes** (`git ls-files`) | Pre-assembled 444-byte inspector binary payload | Byte offsets `0x0A..0x0D` (MOVW) and `0x0E..0x11` (MOVT) encode `0x0035F780` | **Hardcoded (Binary)**: assembled with `-DBOOT_WITNESS_ADDR=0x0035F780`. | `VERIFIED` |
| `firmware/tools/witness_inspector_payload.S` | **Yes** (`git ls-files`) | Assembly source for witness inspector | Lines 57-58: `movw r7, #:lower16:BOOT_WITNESS_ADDR` / `movt r7, #:upper16:BOOT_WITNESS_ADDR` | **Dynamic Macro**: requires `-DBOOT_WITNESS_ADDR` from builder; no literal address in source. | `VERIFIED` |
| `tests/test_restart_sd_audit.py` | **Yes** (`git ls-files`) | Unit tests for SD1stInit audit and prototype source presence | Lines 44, 121: references `chdk-port/platform/g3x/sub/110c/boot_witness.h` | **Indirect**: asserts presence of `boot_witness.h` header; does not pin address. | `VERIFIED` |

---

## 4. Files Under `chdk-port/platform/g3x/sub/110c/` Used by Candidate Build

- **Status**: `UNKNOWN` `[UNKNOWN]`.
- **Reasoning**: The candidate builder script `tools/build_candidate_port2a.py` is an untracked, git-ignored file. No tracked makefile, build script, or configuration file in the Git repository specifies which files under `chdk-port/platform/g3x/sub/110c/` the candidate build consumes `[VERIFIED: git ls-files tools/ chdk-port/]`.
- **Tracked Files Under `sub/110c`**:
  While the repository tracks three files under `chdk-port/platform/g3x/sub/110c/`:
  1. `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (`git ls-files`)
  2. `chdk-port/platform/g3x/sub/110c/boot_witness.h` (`git ls-files`)
  3. `chdk-port/platform/g3x/sub/110c/stubs_prototype.S` (`git ls-files`)
  whether the candidate build compiles these files, links pre-compiled object files, or references canonical `boot.c` cannot be proven from tracked files or historical commits alone.
- **Milestone Deferral**: The exact selection of `sub/110c` files used by the candidate build is therefore reported as `UNKNOWN` for this tracked-only inventory and is deferred to the first-boot milestone `[UNKNOWN]`.

---

## 5. Open U1–U4 Obligation IDs Connected to First Boot

Across the tracked obligation modules (`tools/port13_u2_obligations.py`, `tools/port13_oblig_u4.py`, and runtime lifecycle modules `tools/port9a_runtime_lifecycle.py` and `tools/port9b_runtime_contract.py`), the following **open** obligation IDs are connected by tracked repository documentation to first boot. Per task instructions, they are listed and categorized without resolution `[VERIFIED]`.

### 5.1 Open U2 Obligations (`tools/port13_u2_obligations.py`)

In `tools/port13_u2_obligations.py:597-809`, exactly one obligation (`OBLIG-U2-01`, static task entry pointer `0xFC0BD071`) is `VERIFIED`. The remaining **7** obligations are open (`UNKNOWN`), belonging to Category (c) (unadvanceable from tracked offline artifacts alone) `[VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:21, 144-153]`:

| Obligation ID | Status | Module Definition (`file:line`) | Obligation Statement / First-Boot Connection | Tracked First-Boot Doc Citations | Classification |
|---|---|---|---|---|---|
| **`OBLIG-U2-02`** | `UNKNOWN` | `tools/port13_u2_obligations.py:628-649` | Dynamic task creation and scheduler dispatch execution witness confirming `task_InitFileModules` ran in current boot generation. Observing static entry vector `0xFC0BD071` does not prove scheduler dispatch on first boot. | `docs/PORT13_NEXT_QUESTIONS.md:147`; `docs/PORT13_REVIEW_U2.md:24`; `tools/port9a_runtime_lifecycle.py:296, 661` | `VERIFIED` |
| **`OBLIG-U2-03`** | `UNKNOWN` | `tools/port13_u2_obligations.py:652-677` | Current-generation normal completion witness confirming both `sub_fc0d9ccc` and `sub_fc0d9cf6` return normally in current boot generation without latched fault (`r0==0` is constant and does not prove mount). | `docs/PORT13_NEXT_QUESTIONS.md:148`; `docs/PORT13_REVIEW_U2.md:25`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 281` | `VERIFIED` |
| **`OBLIG-U2-04`** | `UNKNOWN` | `tools/port13_u2_obligations.py:680-703` | Event 0x5006 decoupling from filesystem I/O gate: `Event(0x5006)` does not imply `FilesystemReady(SD0)`; independent kernel storage mount proof required before first boot file access. | `docs/PORT13_NEXT_QUESTIONS.md:149`; `docs/PORT13_REVIEW_U2.md:26`; `tools/port9a_runtime_lifecycle.py:300, 678, 708` | `VERIFIED` |
| **`OBLIG-U2-05`** | `UNKNOWN` | `tools/port13_u2_obligations.py:706-729` | Strict causal ordering of filesystem readiness signal prior to first CHDK file access with verified non-destructive open/read capability on mounted volume without contention or timeout. | `docs/PORT13_NEXT_QUESTIONS.md:150`; `docs/PORT13_REVIEW_U2.md:46`; `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` | `VERIFIED` |
| **`OBLIG-U2-06`** | `UNKNOWN` | `tools/port13_u2_obligations.py:732-754` | Fail-closed fault, error, timeout, and out-of-order execution handling: any violation immediately transitions filesystem state to `FAILED` and blocks first-boot progression. | `docs/PORT13_NEXT_QUESTIONS.md:151`; `docs/PORT13_REVIEW_U2.md:27`; `tools/port9a_runtime_lifecycle.py:262, 686-692` | `VERIFIED` |
| **`OBLIG-U2-07`** | `UNKNOWN` | `tools/port13_u2_obligations.py:757-779` | Monotonic `boot_generation` binding: filesystem readiness latch `<Ready, GenerationID>` invalidated across soft reboot or warm restart to prevent stale token reuse. | `docs/PORT13_NEXT_QUESTIONS.md:152`; `docs/PORT13_REVIEW_U2.md:113`; `tools/port9a_runtime_lifecycle.py:250, 343, 394` | `VERIFIED` |
| **`OBLIG-U2-08`** | `UNKNOWN` | `tools/port13_u2_obligations.py:782-806` | Resolution of warm-restart SD host/card preconditions (P11 `SD1stInit` predicate `0x010E1774()==1`, P12 controller reset, P13 card state, P15 IRQ state) with host retention qualified as plausible and reset ownership decoupled. | `docs/PORT13_NEXT_QUESTIONS.md:153`; `docs/PORT13_REVIEW_U2.md:52-53, 114`; `docs/RESTART_SD_HOST_AUDIT.md:26, 56, 301` | `VERIFIED` |

### 5.2 Open U4 Obligations (`tools/port13_oblig_u4.py`)

In `tools/port13_oblig_u4.py:167-342`, all **11** obligations are open (`UNKNOWN`), connecting `SpyTask` startup ordering, hook interception, priority, stack safety, and timeout semantics to first boot `[VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:22, 155-168]`:

| Obligation ID | Status | Module Definition (`file:line`) | Obligation Statement / First-Boot Connection | Tracked First-Boot Doc Citations | Classification |
|---|---|---|---|---|---|
| **`OBLIG-U4-01`** | `UNKNOWN` | `tools/port13_oblig_u4.py:168-183` | `SpyTask` launch site and caller execution ordering in `GM1.10C` startup sequence. In tracked source, `CreateTask_spytask` is commented out (`boot_prototype.c:416`) for first-boot hardening. | `docs/PORT13_NEXT_QUESTIONS.md:159`; `docs/PORT14_Q_U4_08.md:23, 181`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:409-416` | `VERIFIED` |
| **`OBLIG-U4-02`** | `UNKNOWN` | `tools/port13_oblig_u4.py:184-198` | Runtime hook placement and `CreateTask` interception authorization (Contract I1). Proving static prologue `0xBFE14A3C` does not prove ATCM runtime hook safety on first boot. | `docs/PORT13_NEXT_QUESTIONS.md:160`; `docs/PORT13_OBLIG_U4.md:48-50, 78-82`; `tools/port9b_runtime_contract.py:382-405` | `VERIFIED` |
| **`OBLIG-U4-03`** | `UNKNOWN` | `tools/port13_oblig_u4.py:199-215` | RTOS scheduling priority assignment (`0x19`) and kernel scheduler policy validation to prevent starvation or priority inversion against `task_InitFileModules`. | `docs/PORT13_NEXT_QUESTIONS.md:161`; `docs/PORT13_OBLIG_U4.md:52, 84-89`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 144-161` | `VERIFIED` |
| **`OBLIG-U4-04`** | `UNKNOWN` | `tools/port13_oblig_u4.py:216-231` | Task stack sizing (`0x2000`) and DryOS dynamic memory pool ownership validation ensuring stack allocation does not collide with camera buffers or shifted heap (`0x00366C90`). | `docs/PORT13_NEXT_QUESTIONS.md:162`; `docs/PORT13_OBLIG_U4.md:53, 91-96`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-170` | `VERIFIED` |
| **`OBLIG-U4-05`** | `UNKNOWN` | `tools/port13_oblig_u4.py:232-247` | Filesystem readiness gating and monotonic latch synchronization (Contract I3): `SpyTask` must wait for all 6 filesystem stages without latched fault before I/O. | `docs/PORT13_NEXT_QUESTIONS.md:163`; `docs/PORT13_OBLIG_U4.md:54, 98-102`; `tools/port9a_runtime_lifecycle.py:841-860` | `VERIFIED` |
| **`OBLIG-U4-06`** | `UNKNOWN` | `tools/port13_oblig_u4.py:248-262` | Fail-closed gate timeout enforcement eliminating upstream CHDK legacy bypass (which launched `SpyTask` on 10s timeout even when filesystem mount failed). | `docs/PORT13_NEXT_QUESTIONS.md:164`; `docs/PORT13_OBLIG_U4.md:55, 104-107`; `tools/port9a_runtime_lifecycle.py:863-875` | `VERIFIED` |
| **`OBLIG-U4-07`** | `UNKNOWN` | `tools/port13_oblig_u4.py:263-278` | Isolation of legacy timeout-bypass causal claim: evaluates whether timeout bypass caused storage media corruption or kernel panics vs unsupported correlation. | `docs/PORT13_NEXT_QUESTIONS.md:165`; `docs/PORT13_OBLIG_U4.md:56, 109-114`; `docs/PORT13_REVIEW_U4.md:71-74` | `VERIFIED` |
| **`OBLIG-U4-08`** | `UNKNOWN` | `tools/port13_oblig_u4.py:280-294` | Task execution CPU mode and interrupt mask conformance: proof that `SpyTask` executes in Privileged Supervisor Mode (`M = 0x13`) with initial CPSR `0x000000F3`. | `docs/PORT13_NEXT_QUESTIONS.md:11, 22, 60-84`; `docs/PORT14_Q_U4_08.md:1-260`; `docs/PORT13_OBLIG_U4.md:57, 116-124` | `VERIFIED` |
| **`OBLIG-U4-09`** | `UNKNOWN` | `tools/port13_oblig_u4.py:296-309` | Continuation branch runtime safety: verifying tail branch `b.w sub_fc0d0126` in `task_Startup_my` continues camera initialization without stack corruption. | `docs/PORT13_NEXT_QUESTIONS.md:166`; `docs/PORT13_OBLIG_U4.md:58, 126-129`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434` | `VERIFIED` |
| **`OBLIG-U4-10`** | `UNKNOWN` | `tools/port13_oblig_u4.py:311-325` | `SpyTask` cooperative yield behavior and global-interrupt disable constraints: ensuring `SpyTask` does not monopolize CPU or execute prolonged interrupt-disabled sections. | `docs/PORT13_NEXT_QUESTIONS.md:167`; `docs/PORT13_OBLIG_U4.md:59, 131-134`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:48-52` | `VERIFIED` |
| **`OBLIG-U4-11`** | `UNKNOWN` | `tools/port13_oblig_u4.py:327-341` | Isolation of warm-restart semaphore-freeze hypothesis: verifying whether semaphores allocated prior to DISKBOOT persist across soft reboot and cause scheduler deadlock. | `docs/PORT13_NEXT_QUESTIONS.md:168`; `docs/PORT13_OBLIG_U4.md:60, 136-140`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:80` | `VERIFIED` |

### 5.3 Open Runtime Facts for U1 and U3 (`tools/port9b_runtime_contract.py`)

While dedicated numbered modules exist for U2 (`port13_u2_obligations.py`) and U4 (`port13_oblig_u4.py`), U1 and U3 are tracked as foundational architectural facts in `tools/port9b_runtime_contract.py` and `tools/port9a_runtime_lifecycle.py` `[VERIFIED: docs/PORT15_PORT9B_GAP.md:32-47, 85-118]`:

1. **Fact U1 (`create_task_prologue_verified`)**:
   - Registered at `tools/port9b_runtime_contract.py:77-78`: `"CreateTask prologue and continuation are STATIC_VERIFIED; runtime hook patch context and cache/IRQ safety: UNKNOWN"` `[VERIFIED]`.
   - Contract prerequisite `C6.hook_safety_contract` (`tools/port9b_runtime_contract.py:505-528`) leaves all 4 runtime prerequisites (`patch_execution_context_safe`, `interrupt_masking_and_concurrency_safe`, `icache_and_branch_predictor_coherent`, `continuation_behavior_safe`) as `UNKNOWN` `[VERIFIED]`.
   - Connected to first boot: any premature runtime patching of `CreateTask` without verifying I-cache invalidation or IRQ masking risks crashing early DryOS initialization before the witness is recorded `[VERIFIED: docs/PORT11B_RUNTIME_SAFETY_MODEL.md:22-25; docs/PORT15_PORT9B_GAP.md:93-118]`.
2. **Fact U3 (`physw_entry_verified`)**:
   - Registered at `tools/port9b_runtime_contract.py:81-82`: `"PhySw creator, entry and CreateTaskStrictly chain are STATIC_VERIFIED; runtime replacement and stack safety: UNKNOWN"` `[VERIFIED]`.
   - Connected to first boot: in `boot_prototype.c:405-409`, `task_Startup_my` deliberately calls the stock `PhySw` creator (`sub_fc1283d2`) rather than attempting runtime replacement, because `kbd_task` stack sizing and replacement execution safety are unverified (`UNKNOWN`) `[VERIFIED: docs/PROJECT_STATE.md:35, 159; docs/PORT15_PORT9B_GAP.md:85-88]`.

### 5.4 First-Boot Hardening Integration Invariant

The tracked documentation across `docs/PROJECT_STATE.md:35`, `docs/HANDOFF.md:67`, `docs/PORT14_Q_U4_08.md:23, 135, 181`, and `docs/PORT13_REVIEW_U4.md:133` establishes the first-boot hardening state:

> **First-Boot Hardening State**: In the first-boot prototype source (`boot_prototype.c`), CHDK task and hook activation is disabled `[VERIFIED: docs/PROJECT_STATE.md:35; docs/HANDOFF.md:67]`:
> - `CreateTask_spytask` invocation is commented out (`boot_prototype.c:416`) `[VERIFIED]`.
> - Stock `PhySw` creator `sub_fc1283d2` is called directly without interception (`boot_prototype.c:409`) `[VERIFIED]`.
>
> **Unresolved Active Obligations**: While CHDK background tasks and hooks are disabled, active execution paths in `boot_prototype.c` still execute code associated with open obligations:
> 1. **`OBLIG-U4-09`**: The continuation tail branch `b.w sub_fc0d0126` at `boot_prototype.c:434` is on the active execution path of `task_Startup_my`, so continuation branch runtime safety remains applicable and unresolved `[UNKNOWN: tools/port13_oblig_u4.py:296-309; boot_prototype.c:434]`.
> 2. **`OBLIG-U2-08`**: The warm-restart SD host/card preconditions on the active `SD1stInit` call path (`boot_prototype.c:392-398`, invoking `sub_fc31b1f4` when `sub_fc05c4e0` gate passes) remain applicable and unresolved `[UNKNOWN: tools/port13_u2_obligations.py:782-806; boot_prototype.c:392-398]`.

---

## 6. Summary Matrix of Findings

| Item | Subject | Verified Finding | Key Citations (`file:line`) |
|---|---|---|---|
| **1** | Tracked `0x0035F780` Occurrences | Exactly 26 lines across 7 tracked files | `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`; `docs/HANDOFF.md:186, 188, 189, 192, 228, 340, 388, 398, 426, 455`; `docs/PORT14_Q_MEM03_BSS.md:124`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:231`; `docs/PROJECT_STATE.md:93, 133, 135, 179, 191, 199, 206`; `docs/REPRODUCIBILITY_MANIFEST.md:76, 77`; `docs/RESTART_SD_HOST_AUDIT.md:248, 253`; `firmware/tools/witness_inspector_metadata.json:4`; `tests/test_validate_witness_inspector.py:54` |
| **1** | Tracked `0x0035F7A0` Occurrences | Exactly 9 lines across 6 tracked files | `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`; `docs/HANDOFF.md:228, 229`; `docs/PORT3C_RESTART_READINESS_MATRIX.md:231`; `docs/PROJECT_STATE.md:133, 134`; `docs/REPRODUCIBILITY_MANIFEST.md:80`; `docs/RESTART_SD_HOST_AUDIT.md:248, 251` |
| **1** | `SD1stInit` Offsets | +14 bytes Thumb-2 code added in `.text` shifts 16-byte-aligned `.data` by +32 bytes (`+0x20`) | `docs/RESTART_SD_HOST_AUDIT.md:247-250`; `docs/HANDOFF.md:228`; `docs/PROJECT_STATE.md:133`; `patches/0001-sd1stinit-restart-prototype.patch:49-56`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:392-398` |
| **2** | Corrected Provenance Commits | `860d873c` (investigation), `e418ccfe` (prototype), `25900369` (PR #2 merge), `5d644cbd` (dynamic tooling), `f8cc7a97` (PORT-5E PR #5) | Git log commits on `origin/main`; `docs/REPRODUCIBILITY_MANIFEST.md:71-74` |
| **3** | Candidate Build & Validation Tools | Builder script `build_candidate_port2a.py` and validator script `validate_candidate_port2a.py` are untracked (`git ls-files --error-unmatch` exits 1) and git-ignored (`.git/info/exclude`), so their hardcoded addresses and contents are `UNKNOWN` for tracked inventory. Tracked tooling: `build_witness_inspector.py` (dynamic NM symbol resolution), `validate_witness_inspector.py` (dynamic 3-way check), `test_validate_witness_inspector.py` (dynamic tests; comment line 54), `witness_inspector_metadata.json` (hardcoded 0x0035F780 at line 4), `witness_inspector_payload.bin` (hardcoded 0x0035F780 in MOVW/MOVT opcodes). | `tools/build_witness_inspector.py:39-76`; `tools/validate_witness_inspector.py:89-108, 359-434`; `tests/test_validate_witness_inspector.py:47-68`; `firmware/tools/witness_inspector_metadata.json:4-5`; `firmware/tools/witness_inspector_payload.bin:0x0A..0x11` |
| **4** | Platform Sub Files Used by Candidate | Reported `UNKNOWN`. `tools/build_candidate_port2a.py` is untracked and git-ignored; no tracked build script or configuration specifies which `sub/110c` files the candidate build uses. Deferred to first-boot milestone. | `git ls-files tools/ chdk-port/`; `chdk-port/platform/g3x/sub/110c/` |
| **5** | Open U1–U4 Obligations | 7 open U2 obligations (`OBLIG-U2-02..08`); 11 open U4 obligations (`OBLIG-U4-01..11`); 2 open runtime facts (U1 hook safety, U3 PhySw replacement). All left unresolved (`UNKNOWN`). Active path obligations `OBLIG-U4-09` (continuation branch at `boot_prototype.c:434`) and `OBLIG-U2-08` (SD1stInit restart conditions at `boot_prototype.c:392-398`) remain applicable and unresolved. | `tools/port13_u2_obligations.py:628-806`; `tools/port13_oblig_u4.py:168-341`; `tools/port9b_runtime_contract.py:77-84`; `docs/PORT13_NEXT_QUESTIONS.md:21-23, 144-168`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:392-398, 434` |
