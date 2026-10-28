# PORT-13 — Read-Only Review of Draft PR #23 (PORT-12A Memory Ownership)

**Review Date**: 2026-10-28  
**Reviewer**: Antigravity (Independent Firmware Reviewer, AgentBridge worker `p13-review-pr23`)  
**Target Branch**: `origin/research/port12a-memory-ownership`  
**Target Commit SHA**: [`3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`](https://github.com/s4urj3ng/g3x-lite/commit/3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4)  
**Base Commit SHA**: [`581b1a4bb30456bf18c46dc4bcf61b0375aee251`](https://github.com/s4urj3ng/g3x-lite/commit/581b1a4bb30456bf18c46dc4bcf61b0375aee251) (`origin/main`)  
**Merge-Base**: `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (Clean ancestor; 1 commit ahead: `+301` lines across 2 files)  
**Reviewed Artifacts**:
- `docs/PORT12A_MEMORY_OWNERSHIP_MATRIX.md` (143 lines added)
- `tests/test_port12a_memory_ownership.py` (158 lines added)  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Read-Only Investigation)  
**Overall Recommendation**: **`needs-changes`** (Do not merge or approve in current state)

---

## 1. Executive Summary

This document provides a formal, independent, read-only review of Draft PR #23 (milestone **PORT-12A / Issue #20**). The stated purpose of PR #23 is to establish an offline, source-grounded memory ownership matrix for the Canon PowerShot G3 X (Firmware **GM1.10C**, DIGIC 6, Cortex-R4 dual-core), comparing prototype low-heap core relocation (`0x003489B4 + new_sa`) against Ranma's historical GM1.10E high-DRAM placement (`0x00C80000`).

### High-Level Assessment
1. **Architectural Direction (Sound & Valuable)**:
   - The core conceptual thesis of PR #23 is well-reasoned: rejecting the unsafe heuristic that uninspected DRAM is "free space", distinguishing `PROVEN_NO_OVERLAP` from `MERELY_NO_KNOWN_OVERLAP`, and identifying severe hazards with Ranma's high-DRAM placement (`0x00C80000`) on GM1.10C (such as sensor RAW circular DMA buffers requiring ~35 MiB per frame, audio/video co-processor firmware blob loads, and lack of verified top-of-DRAM bounds).
   - The mathematical model of DryOS heap headroom (`0x006CE000 - r4 >= 0x000B1FEC`) matches prototype code in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:179` and tracked analysis in `docs/PROJECT_STATE.md:294`.
2. **Evidentiary Rigor & Citation Compliance (Critical Failures)**:
   - **Citing Untracked Documents as Checkable Evidence**: PR #23 extensively cites local, untracked files that do not exist on `origin/main` or in git history, specifically: `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B:26`, `CHDK_PORT1B:32`, `CHDK_PORT1B:47`, `CHDK_PORT1B:92`, and `docs/RANMA_SOURCE_ARCHAEOLOGY.md:46` (the latter exists only on an unmerged research branch `origin/research/g9-ranma-source-archaeology`).
   - **Over-Promotion to `VERIFIED_IN_EXISTING_DOCS`**: Out of 17 memory regions cataloged, 9 regions are labeled `VERIFIED_IN_EXISTING_DOCS`. However, only **one single region (R-16: ATCM relocated span)** is backed by tracked primary GM1.10C ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`). The remaining 8 regions rely on untracked notes or secondary tables in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, where line 72 explicitly notes: *"No ROM was read, and every C value is only as good as the existing document it comes from."*
   - **Inaccurate Line Citations & Transcriptions**: Citations to `PORT5B:78` do not contain `MEMBASEADDR=0x8000` (which is at line 101, referencing Ranma's GM1.10E `entry.S`) or BSS zeroing loops; citation to `PORT5B:48` for DMA address `0x43DBFCA0` references a line-count table row for `notes.txt`.
   - **Unsupported Span Expansions and Fencepost Errors**:
     - Region `R-09` (`AdditionAgent`): Declared as inclusive `0x006CE000..0x006FFFFF` (196 KiB claimed / 200 KiB inclusive). Tracked documentation confirms `AdditionAgent` reads up to `0x22000` bytes (136 KiB), ending inclusively at `0x006EFFFF` (half-open: `[0x006CE000, 0x006F0000)`). Expanding this region to `0x006FFFFF` arbitrarily subsumes a 64 KiB uninspected gap (`0x006F0000..0x006FFFFF`, `UNKNOWN`).
     - Region `R-10` (`OMAR`): Upper bound is given as `0x00760000` (384 KiB + 1 byte), whereas historical note `PORT5B:172` records `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB).
     - Region `R-14` (`Firmware Executable RAM Mirror`): Declared as inclusive `0x010E1000..0x01107D00`. Auditing tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115` proves the copy loop uses a strictly-less-than (`blo`) condition against limit `0x01107d00`, stopping strictly before `0x01107D00` (last word written to `0x01107CFC..0x01107CFF`, total size `0x26D00` = 155.25 KiB, confirmed by cache flush size at line 120 and `PORT5B:178`). PR #23's inclusive upper bound of `0x01107D00` adds 1 extra byte and causes Region `R-15` to begin at `0x01107D01`, stranding `0x01107D00`.
   - **Categorical Safety Assertions Lacking Primary Proof**: PR #23 presents categorical assertions—declaring low-heap placement "proven safe", claiming DryOS allocator exclusion proof, asserting "zero collision risk", and assuming camera architecture guarantees capture DMA never overwrites DryOS heap space—without primary disassembly of GM1.10C allocator routines or DMA controllers.
3. **Test Suite Status**:
   - The PR's test suite `tests/test_port12a_memory_ownership.py` was executed in a scratch environment and passed completely (**10/10 PASS**, 0.001s).
   - However, the tests hardcode `VERIFIED_IN_EXISTING_DOCS` strings and assert strict contiguous partitioning across unverified address boundaries (`R-01 -> R-02 -> R-03 -> R-04 -> R-05`), creating circular validation of unverified assumptions.

### Notation and Interval Conventions
Throughout this review report:
- Interval notation `[start, end]` denotes **inclusive (closed)** endpoints: both `start` and `end` are contained within the span (size = `end - start + 1`).
- Interval notation `[start, end)` denotes **half-open** endpoints: `start` is included, and `end` is excluded (size = `end - start`).
- In table entries, `start..end` denotes inclusive bounds `[start, end]`. When discussing copy limits, half-open notation is explicitly marked.

---

## 2. Per-Claim Evaluation Table

The following table evaluates the 17 cataloged memory regions (`R-01`..`R-17`), 5 quantitative headroom and arithmetic claims (`AR-1`..`AR-5`), and 4 categorical safety assertions (`SA-1`..`SA-4`) in PR #23 against tracked repository evidence on `origin/main`.

> [!NOTE]
> **Claim Coverage**: This table covers all cataloged memory regions, arithmetic deductions, and categorical safety assertions extracted from PR #23's matrix, diagrams, and decision memo. Because PR #23 also contains general narrative prose, this table is not described as an exhaustive extraction of every sentence in the document, but it explicitly captures all architectural, spatial, and safety claims made by the author.

| Claim ID | Region / Subject | Address Range & Size | PR Claimed Classification | Cited Source in PR #23 | Tracked on `origin/main`? | Reviewer Verdict | Reviewer Finding & Flag Notes |
|---|---|---|:---:|---|:---:|:---:|---|
| **CLM-01 (R-01)** | Low Vector & Hardware Scratch | `0x00000000..0x00007FFF` (32 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78 (MEMBASEADDR=0x8000)` | Partial (`PORT5B` tracked; line 78 wrong; `MEMBASEADDR` is L101) | **`INFERRED / MISLABELED`** | **FLAGGED (Historical / Inaccurate Citation)**. Line 78 in `PORT5B` describes copy ranges, not `MEMBASEADDR`. `MEMBASEADDR=0x8000` appears at L101 as Ranma's loader stack setup in GM1.10E `entry.S`. Exception vector layout in `0x00000000..0x00007FFF` on GM1.10C is inferred from historical platforms, not ROM-verified. |
| **CLM-02 (R-02)** | Low-RAM Data Section | `0x00008000..0x0003F4F3` (~221 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCE91058 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked local file `CHDK_PORT1B:26`. In `PORT5B`, Low-RAM data copy source `0xFCE91058` is at L77 (citing prototype `C:134`) and destinations at L78 and L167, with explicit caveat at L72 that no ROM was read. Copy source `0xFCE91058` is outside approved ROM inspection scopes. |
| **CLM-03 (R-03)** | Canon Firmware BSS | `0x0003F4F4..0x003489B3` (~3.036 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Zeroed at boot 0xFC020070..0xFC020078 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked; `0xFC020070` inside S1A range in `PORT11A:60`) | **`INFERRED / UNTRACKED_CITATION / MISSING_PRIMARY_PROOF`** | **FLAGGED (Untracked Citation / Missing Primary Disassembly)**. Cites untracked `CHDK_PORT1B:26`. `PORT5B:78` lists BSS end `0x3489b4` from prototype `C:144-153`, but has no BSS zeroing loop instructions. While address `0xFC020070` falls inside the read range of pinned ROM Slice `S1A` (`0xFC020040..0xFC0200CF`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:60`), `PORT11A` only analyzed the ATCM copy loop (`0xFC020040..0xFC020052`) and literals; no tracked analysis of `0xFC020070..0xFC020078` supports the BSS zeroing claim (Case b). BSS end `0x003489B4` is modeled in prototype, but ROM loop is unanalyzed. |
| **CLM-04 (R-04)** | Low-Heap Prototype Target | `0x003489B4..0x003C89B3` (512 KiB) | `INFERRED (Design Candidate)` | `Linker script & docs/CHDK_PORT1B_HEAP_PROOF.md:92` | No (both untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification as `INFERRED` design candidate is epistemically sound, but citations ("Linker script" and `CHDK_PORT1B_HEAP_PROOF.md:92`) refer to untracked local files not present in the repository. |
| **CLM-05 (R-05)** | DryOS Main Heap Pool 0 | `0x003C89B4..0x00600013` (~2.216 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474 (0x00600014), CHDK_PORT1B:47` | Partial (`0x00600014` in `boot_prototype.c:209-211` and `PORT5B:169, 205`; literal `0xFC05B474` and `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal address `0xFC05B474` has no tracked reference anywhere in the repo (Case c). Sub-pool limit `0x00600014` is in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-211` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169, 205` (where descriptor semantics are explicitly marked `INFERRED`). |
| **CLM-06 (R-06)** | DryOS Sub-pool & Kernel Descriptors | `0x00600014..0x0060DFFF` (56 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474, CHDK_PORT1B:47` | No | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal `0xFC05B474` has no tracked reference anywhere in the repo (Case c). `PORT5B:169, 205` classifies descriptor parameters as `INFERRED`. |
| **CLM-07 (R-07)** | DryOS Heap Upper Chunk Block | `0x0060E000..0x006CDFFF` (768 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B470, chunk size 0x000C0000, CHDK_PORT1B:47` | Partial (`0x0060E000` in `PORT5B:170, 205` and `boot_prototype.c:206, 212`; literal `0xFC05B470` & `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal `0xFC05B470` has no tracked reference anywhere in the repository (Case c). Chunk size `0x000C0000` and descriptor slot `sp[0x14] = 0x0060E000` appear in `boot_prototype.c:206, 212` and `PORT5B:170, 205` (marked `INFERRED`). |
| **CLM-08 (R-08)** | DryOS System Limit & Headroom Assert | `0x006CE000` (Anchor) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B454 (0x006CE000), CHDK_PORT1B:32` | Partial (`0x006CE000` in `PROJECT_STATE.md:294` & `HANDOFF.md:793`; `0xFC05B454` in `PORT5A:108`; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Non-Primary Reference)**. Cites untracked `CHDK_PORT1B:32`. Literal address `0xFC05B454` appears in `docs/PORT5A_RANMA_PORT_RECOVERY.md:108` only as a secondary comparison table entry, not reproducible primary ROM proof (Case a). The headroom limit `0x006CE000` is documented in `docs/PROJECT_STATE.md:294` and `boot_prototype.c:179`, but derives from unpinned early research traces. |
| **CLM-09 (R-09)** | AdditionAgent Conflict Zone | `0x006CE000..0x006FFFFF` (196 KiB claimed / 200 KiB inclusive) | `VERIFIED_IN_EXISTING_DOCS` | `0xFC55888C..0xFC5588C0 (docs/RANMA_SOURCE_ARCHAEOLOGY.md:46)` | Partial (ROM routine in `HANDOFF.md:830` & `PROJECT_STATE.md:308`; `PORT5B:171`; `docs/RANMA_SOURCE_ARCHAEOLOGY.md` untracked on `main`) | **`INFERRED / UNTRACKED_CITATION / CONTRADICTED_BOUNDS`** | **FLAGGED (Untracked Citation / Unsupported Span Extension / Fencepost Error)**. Cites unmerged branch artifact `docs/RANMA_SOURCE_ARCHAEOLOGY.md`. Tracked docs (`PORT5B:171`, `HANDOFF.md:830`, `PROJECT_STATE.md:308`) specify `AdditionAgent` reads up to `0x22000` bytes (136 KiB), spanning inclusively `0x006CE000..0x006EFFFF` (half-open: `[0x006CE000, 0x006F0000)`). Expanding this region to `0x006FFFFF` arbitrarily absorbs the subsequent 64 KiB uninspected gap `0x006F0000..0x006FFFFF` (`UNKNOWN`). |
| **CLM-10 (R-10)** | OMAR Secondary Core Staging RAM | `0x00700000..0x00760000` (384 KiB + 1 byte) | `HISTORICAL_CANDIDATE` | `Ranma platform/g3x/notes.txt:45–46, PORT5B` | Partial (`PORT5B:172` tracked; `notes.txt` untracked) | **`HISTORICAL_CANDIDATE / OFF_BY_ONE`** | **FLAGGED (Historical / Untracked Citation / Fencepost Error)**. Cites untracked `notes.txt`. In tracked `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`, Ranma's GM1.10E range is recorded as `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB) and explicitly classified as *"Not documented"* on GM1.10C (`HISTORICALLY REPORTED`). PR #23's upper bound `0x00760000` adds 1 extra byte (`0x60001` = 393,217 B). |
| **CLM-11 (R-11)** | Mid DRAM Uninspected Gap | `0x00760001..0x00C7FFFF` (~5.12 MiB) | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly classifies uninspected DRAM as `UNKNOWN` and rejects treating it as empty memory. |
| **CLM-12 (R-12)** | Ranma High-DRAM CHDK Placement | `0x00C80000..0x00DFFFFF` (1.5 MiB) | `HISTORICAL_DESIGN_CANDIDATE` | `platform/g3x/makefile.inc:29–37, g3x_110e.patch:580` | Partial (`PORT5B:175` documents values; local patch files untracked) | **`HISTORICAL_CANDIDATE / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification as historical candidate unproven on GM1.10C is sound (`PORT5B:175`), but citations to `platform/g3x/makefile.inc` and `g3x_110e.patch` are to untracked local files. |
| **CLM-13 (R-13)** | High DRAM Uninspected Gap | `0x00E00000..0x010E0FFF` (~2.88 MiB) | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly flags uninspected DRAM gap as `UNKNOWN`. |
| **CLM-14 (R-14)** | Firmware Executable RAM Mirror | `0x010E1000..0x01107D00` (155.25 KiB claimed / 158,977 B inclusive) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEC854C (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B:75, 78, 177` and `boot_prototype.c:108-115` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION / FENCEPOST_ERROR`** | **FLAGGED (Untracked Citation / Fencepost Error)**. Cites untracked `CHDK_PORT1B:26`. In `PORT5B`, source `0xFCEC854C` is at L75 and copy ranges at L78 (citing prototype `C:107`, `C:108-147`), with memory map row at L177 giving `0x010E1000–0x01107CFF`. Auditing tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115` reveals the copy loop uses a strictly-less-than (`blo`) condition against upper limit `0x01107d00`, stopping strictly before `0x01107D00` (last word written to `0x01107CFC..0x01107CFF`, total size `0x26D00` = 158,976 B = 155.25 KiB, matching cache clean size at line 120). Stating inclusive range as `0x010E1000..0x01107D00` is a 1-byte fencepost error that causes `R-15` to start at `0x01107D01`, stranding `0x01107D00`. |
| **CLM-15 (R-15)** | Upper DRAM & DMA Capture Buffers | `0x01107D01..0x3FFFFFFF` (~1006 MiB) | `UNKNOWN` | `Dynamic heap / peripheral DMA (0x43DBFCA0, PORT5B:48)` | Partial (`PORT5B` tracked; L48 irrelevant; `0x43DBFCA0` in `HANDOFF.md:830` & `PROJECT_STATE.md:308`) | **`UNKNOWN / INACCURATE_CITATION`** | **FLAGGED (Inaccurate Line Citation / Inferred Bound / Fencepost Offset)**. `PORT5B:48` is a table line count for `notes.txt`. `0x43DBFCA0` is in `docs/HANDOFF.md:830` and `docs/PROJECT_STATE.md:308`. Lower bound should start at `0x01107D00` rather than `0x01107D01` (due to R-14's true endpoint `0x01107CFF`). Upper bound `0x3FFFFFFF` is inferred without physical DRAM size register evidence. Classification `UNKNOWN` is correct. |
| **CLM-16 (R-16)** | Cortex-R4 ATCM Relocated Span | `0xBFE10800..0xBFE1741B` (27,676 B) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEEF24C..0xFCEF5E67 (PORT11A:20, PR #19)` | Yes (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`) | **`STATIC_VERIFIED`** | **VERIFIED**. Accurately cites tracked `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20` and approved ROM slice `S1A` (`0xFC020040..0xFC0200CF`, L60). Proves copy of 6,919 words (27,676 B) to `0xBFE10800..0xBFE1741B`. Sole genuinely verified region in PR #23. |
| **CLM-17 (R-17)** | Uncached Peripheral Memory Mappings | `0x40000000..0x5FFFFFFF` (512 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `0x42281000, 0x42283000, 0x406CE000 (CHDK_PORT1B:47)` | Partial (`CAM_UNCACHED_BIT 0x40000000` tracked in `vendor/g3x-platform/platform/g3x/platform_camera.h:38`; `PORT5B:179`; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:47`. `PORT5B:179` classifies `0x20000000`/`0x40000000` as `HISTORICALLY REPORTED` (`P:699, 711`). Range `0x40000000..0x5FFFFFFF` (512 MiB) is an architectural inference without MPU or peripheral aperture proof. |
| **CLM-18 (AR-1)** | DryOS Stock Headroom Check | `0x006CE000 - 0x003489B4 = 3,692,108 B >= 729,068 B` (Margin: 2.82 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:32` | Partial (formula in `boot_prototype.c:179` & `PROJECT_STATE.md:294`; `CHDK_PORT1B` untracked) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic matches prototype model in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:179` and `docs/PROJECT_STATE.md:294`, but cites untracked `CHDK_PORT1B`. Kernel init routine `0xFC05B3C8` is uninspected in GM1.10C ROM. |
| **CLM-19 (AR-2)** | DryOS Shifted 512 KiB Headroom Check | `0x006CE000 - 0x003C89B4 = 3,167,820 B >= 729,068 B` (Margin: 2.32 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B_HEAP_PROOF.md` | No (untracked file) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic is mathematically sound for shifted heap base, but cites untracked document. |
| **CLM-20 (AR-3)** | Low-Heap Isolation from AdditionAgent | `0x006CE000 - 0x003C89B4 = 3.02 MiB > 3 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming `AdditionAgent` base is `0x006CE000` and heap shift is `0x003C89B4`. |
| **CLM-21 (AR-4)** | Low-Heap Isolation from OMAR | `0x00700000 - 0x003C89B4 = 3.21 MiB > 3.2 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming OMAR base is `0x00700000`. |
| **CLM-22 (AR-5)** | Ranma High-DRAM Sensor RAW Hazard | Uncompressed 20.2 MP raw frame: $5472 \times 3648 \times 14\text{ bits} \approx 34.9\text{ MiB}$ in High DRAM | `UNKNOWN` (Hazard Analysis) | Sensor specification deduction | N/A | **`PLAUSIBLE / UNKNOWN`** | Sensor arithmetic is sound ($5472 \times 3648 \times 14 / 8 = 34,924,032\text{ B} \approx 34.9\text{ MiB}$). Circular capture buffers in upper DRAM present genuine collision risk. |
| **CLM-23 (SA-1)** | §1 Categorical Assertion: "Proven safe" Low-Heap Placement | `0x003489B4..0x003C89B3` (512 KiB) vs BSS & Low-RAM | `VERIFIED_IN_EXISTING_DOCS` | PR #23 §1 Key Findings (cites `0xFC05B3C8` & headroom formula) | Partial (math in `boot_prototype.c:179`; routine `0xFC05B3C8` uninspected) | **`INFERRED / OVERSTATED_SAFETY_CLAIM`** | **FLAGGED (Categorical Safety Assertion / Uninspected Preconditions)**. PR #23 asserts placement is categorically *"Proven safe from collision with BSS and low-RAM hardware structures"*. While arithmetic headroom is consistent with the prototype model, BSS bounds and Low-RAM data structures derive from historical notes (`PORT5B:78, 167, 168`) and prototype comments, not verified GM1.10C ROM disassembly. Runtime bootloader safety and hardware exception behavior remain uninspected. Must be qualified as `INFERRED (Design Candidate)` or backed by tracked primary evidence. |
| **CLM-24 (SA-2)** | §3 Categorical Assertion: DryOS Allocator Exclusion Proof | `0x003489B4..0x003C89B3` (512 KiB exclusion zone) | `PROVEN_NO_OVERLAP` | PR #23 §3 (anchored to BSS `_end` via literal `0xFC05B450` and heap descriptor `sp[0x08] = r4`) | Partial (`0xFC05B450` in `PROJECT_STATE.md:295`; descriptor in `boot_prototype.c:206-212`; allocator logic untracked) | **`INFERRED / UNVERIFIED_ALLOCATOR_MODEL`** | **FLAGGED (Categorical Safety Assertion / Missing Primary Allocator Proof)**. PR #23 claims formal exclusion proof based on the premise that DryOS `AllocateMemory` only issues pointers $\ge r_4$. However, no tracked GM1.10C ROM disassembly of DryOS heap allocator routines (`AllocateMemory`, sub-pool managers, compaction) exists in the repo. While setting `sp[0x08] = r4` sets the lower bound in the prototype descriptor model (`boot_prototype.c:210`), proving zero runtime allocation below `r_4` requires disassembly of the allocator implementation. Must be qualified as `INFERRED (Design Model)` or backed by tracked primary ROM disassembly. |
| **CLM-25 (SA-3)** | §4 Categorical Assertion: "Zero" Collision Risk with AdditionAgent and OMAR | Margins: $3.02$ MiB to `0x006CE000`; $3.21$ MiB to `0x00700000` | "Zero" Risk | PR #23 §4 Decision Memo table (arithmetic distance from `0x003C89B4` to `0x006CE000` and `0x00700000`) | Partial (arithmetic correct; base bounds of AdditionAgent and OMAR unverified) | **`INFERRED / OVERSTATED_RISK_CLAIM`** | **FLAGGED (Categorical Safety Assertion)**. PR #23 claims "Zero" collision risk with `AdditionAgent` and OMAR. While static arithmetic distance ($>3$ MiB) from assumed anchors is correct, neither anchor is primary-verified on GM1.10C: `AdditionAgent` ROM read routines (`0xFC55888C..0xFC5588C0`) are uninspected in ROM, and OMAR is explicitly classified as `HISTORICALLY REPORTED` and *"Not documented"* on GM1.10C (`PORT5B:172`). Asserting absolute "Zero risk" without verified GM1.10C IPC memory maps is an overstatement; must be qualified as `INFERRED (Design Margin Estimate)` rather than categorical zero risk. |
| **CLM-26 (SA-4)** | §4 Categorical Assertion: Capture DMA Never Overwrites DryOS Heap Space | DryOS Heap Space (`0x003489B4..0x006CDFFF`) vs DMA Framebuffers | "High" Safety / Architectural Fact | PR #23 §4 Decision Memo table ("(Canon camera architecture isolates heap from framebuffers)") | No (Untracked architectural generalization) | **`UNKNOWN / UNVERIFIED_HEURISTIC`** | **FLAGGED (Categorical Safety Assertion / Unverified Heuristic)**. PR #23 asserts that DryOS heap space is never overwritten by raw image capture DMA because Canon camera architecture supposedly isolates heap from framebuffers. This architectural generalization is not backed by any tracked primary evidence on GM1.10C. In fact, PR #23's own Section 6 explicitly acknowledges that sensor RAW DMA lower bounds (E-01) and peak continuous shooting heap allocations (E-05) remain unverified. Heuristic assumptions of architectural isolation cannot be treated as verified safety facts; verdict must be qualified as `UNKNOWN / UNVERIFIED HEURISTIC` or backed by tracked primary evidence. |

---

## 3. Explicit Inventory of Flagged Claims

Per the acceptance criteria, the following subsections catalog every claim that violates evidentiary standards:

### 3.1 Claims Relying on Historical Firmware (GM1.00C / GM1.10E / `g3x_110e.patch`) as GM1.10C Proof
1. **Claim CLM-01 (Region R-01: `0x00000000..0x00007FFF`)**:
   - Relies on `MEMBASEADDR=0x8000`, which originates from Ranma's `entry.S` (`P:28–36` in `g3x_110e.patch` for GM1.10E, documented in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:101`). Treated as proving a 32 KiB "Low Vector & Hardware Scratch" allocation on GM1.10C.
2. **Claim CLM-10 (Region R-10: `0x00700000..0x00760000`)**:
   - Derives from Ranma's GM1.10E comment "OMAR ram area" (`P:693–694` in `g3x_110e.patch`, recorded in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`). `PORT5B` explicitly states that this region is **`Not documented`** in GM1.10C and is strictly **`HISTORICALLY REPORTED`**.
3. **Claim CLM-12 (Region R-12: `0x00C80000..0x00DFFFFF`)**:
   - Derives from Ranma's GM1.10E `MEMISOSTART = 0x00C80000` (`g3x_110e.patch:580`, recorded in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`). While PR #23 correctly warns that this is unproven on GM1.10C, it cites untracked historical patch lines as evidence sources.
4. **Claim CLM-17 (Region R-17: `0x40000000..0x5FFFFFFF`)**:
   - Derives from Ranma's GM1.10E patch definitions (`P:699, 711`), classified in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179` as **`HISTORICALLY REPORTED`**.

### 3.2 Claims Citing Untracked / Local-Only L1/L2 Sources as Checkable Evidence
1. **`docs/PORT1B_HEAP_PROOF.md` / `CHDK_PORT1B_HEAP_PROOF.md`**:
   - Cited in Section 2 introductory text, Section 4 Decision Memo, and CLM-04 (R-04: `docs/CHDK_PORT1B_HEAP_PROOF.md:92`), CLM-19 (AR-2).
   - **Status**: **UNTRACKED**. This file was a local scratch document from early prototyping that was never committed to git.
2. **`CHDK_PORT1B:26`, `CHDK_PORT1B:32`, `CHDK_PORT1B:47`**:
   - Cited in CLM-02 (R-02), CLM-03 (R-03), CLM-05 (R-05), CLM-06 (R-06), CLM-07 (R-07), CLM-08 (R-08), CLM-14 (R-14), CLM-17 (R-17), and CLM-18 (AR-1).
   - **Status**: **UNTRACKED**. All citations to `CHDK_PORT1B` refer to local, uncommitted files.
3. **`docs/RANMA_SOURCE_ARCHAEOLOGY.md:46`**:
   - Cited in CLM-09 (R-09).
   - **Status**: **UNTRACKED ON `origin/main`**. Exists only on an unmerged research branch (`origin/research/g9-ranma-source-archaeology`).
4. **`g3x_110e.patch:580`**:
   - Cited in Section 2 intro and CLM-12 (R-12).
   - **Status**: **UNTRACKED**. `g3x_110e.patch` is an ignored, untracked local file.
5. **`platform/g3x/notes.txt:45–46` & `platform/g3x/makefile.inc:29–37`**:
   - Cited in CLM-10 (R-10) and CLM-12 (R-12).
   - **Status**: **UNTRACKED**. These paths refer to internal contents of the untracked patch, not tracked repository files.
6. **"Linker script"**:
   - Cited in CLM-04 (R-04).
   - **Status**: **UNTRACKED**. Zero linker scripts (`*.ld`) exist in the repository.

### 3.3 Evidence-Absence & ROM Address Provenance Accounting
PR #23 cites several specific ROM literal addresses (`0xFC05B450`, `0xFC05B454`, `0xFC020070`, `0xFC05B470`, `0xFC05B474`) as proof for its memory bounds and classifications. A rigorous audit against `origin/main` at base commit `581b1a4bb30456bf18c46dc4bcf61b0375aee251` separates these addresses into three distinct cases:

1. **Case (a): A tracked reference exists in repository documentation, but is not reproducible primary proof**:
   - **`0xFC05B450`** (cited in PR #23 §3 Definition 1 as ROM literal anchoring Canon BSS `_end` `0x003489B4`):
     - *Tracked Occurrences*: Appears in `docs/PROJECT_STATE.md:295, 304` and `docs/HANDOFF.md:795, 823`.
     - *Epistemic Finding*: These tracked occurrences are high-level narrative project summaries recording findings from an earlier unpinned session. Under Phase 0 evidentiary standards, narrative text in handoff files is secondary reporting, not reproducible primary ROM evidence (no pinned ROM slice, file offset, instruction disassembly, or SHA-256 excerpt exists in the repository for `0xFC05B450`). Thus, `0xFC05B450` cannot support a `VERIFIED` classification.
   - **`0xFC05B454`** (cited in CLM-08 / R-08 as ROM literal anchoring `0x006CE000`):
     - *Tracked Occurrences*: Appears in `docs/PORT5A_RANMA_PORT_RECOVERY.md:108`.
     - *Epistemic Finding*: In `PORT5A`, this address is mentioned strictly within a secondary comparison table contrasting historical candidate settings against Ranma's port notes. It is not reproducible primary proof of GM1.10C ROM contents (no pinned ROM slice or disassembly excerpt exists). Citing `0xFC05B454` does not make Region `R-08` `VERIFIED`.

2. **Case (b): The address is inside a documented read range, but no tracked analysis of those bytes supports the claim**:
   - **`0xFC020070`** (cited in CLM-03 / R-03 as BSS zeroing loop `0xFC020070..0xFC020078`):
     - *Tracked Occurrences*: The address `0xFC020070` lies within the address span of pinned ROM Slice `S1A` (`0xFC020040..0xFC0200CF`, documented in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:60`).
     - *Epistemic Finding*: In `PORT11A`, analysis of `S1A` was strictly limited to the early boot ATCM copy loop (`0xFC020040..0xFC020052`) and the literal pool at `0xFC0200C4..0xFC0200CC`. No tracked analysis, disassembly, or verification of the bytes at `0xFC020070..0xFC020078` exists anywhere in the repository. Simply falling inside a documented read range without tracked analysis of those specific instructions does not support the claim that this range constitutes a BSS zeroing loop, and cannot make `R-03` `VERIFIED`.

3. **Case (c): There is no tracked reference at all**:
   - **`0xFC05B470`** (cited in CLM-07 / R-07 as literal for chunk size `0x000C0000` / heap upper block) and **`0xFC05B474`** (cited in CLM-05 / R-05 and CLM-06 / R-06 as literal for `0x00600014` / sub-pool limit):
     - *Tracked Occurrences*: **Zero**. Neither address appears anywhere in any tracked file in the repository at base commit `581b1a4bb30456bf18c46dc4bcf61b0375aee251`.
     - *Epistemic Finding*: These addresses are entirely untracked and uninspected in ROM. Citing them as evidence for `VERIFIED_IN_EXISTING_DOCS` is an unsubstantiated assertion.

### 3.4 Spatial Inferences, Fencepost Errors, and Boundary Distortions
1. **Region R-09 (`AdditionAgent`) Span Expansion & Fencepost Error**:
   - PR #23 declares `R-09` as `0x006CE000..0x006FFFFF` (196 KiB claimed / 200 KiB inclusive).
   - Tracked documentation (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`, `docs/PROJECT_STATE.md:308`, `docs/HANDOFF.md:830`) confirms that `AdditionAgent` reads up to `0x22000` bytes (136 KiB).
   - In inclusive notation, `0x22000` bytes starting at `0x006CE000` end inclusively at `0x006EFFFF` (half-open: `[0x006CE000, 0x006F0000)`).
   - The subsequent gap begins at `0x006F0000` and runs to `0x006FFFFF` (64 KiB inclusive / `[0x006F0000, 0x00700000)`). Expanding `AdditionAgent` to `0x006FFFFF` arbitrarily subsumes this 64 KiB uninspected gap into `R-09`.
2. **Region R-10 (`OMAR`) Upper Bound Fencepost Error**:
   - PR #23 specifies `0x00700000..0x00760000` (384 KiB + 1 byte = 393,217 B).
   - Ranma's historical note recorded in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172` gives `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB = 393,216 B). `0x00760000` is an off-by-one fencepost error.
3. **Region R-14 (`Firmware Executable RAM Mirror`) Endpoint Fencepost Error**:
   - PR #23 specifies `0x010E1000..0x01107D00` as an inclusive range.
   - Auditing tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115` proves that the copy loop uses a strictly-less-than (`blo`) condition against upper limit literal `0x01107d00`:
     ```c
     ldr r0, =0xfcec854c
     ldr r1, =0x010e1000
     ldr r3, =0x01107d00
     loc_copy_highram:
         cmp r1, r3
         itt lo
         ldrlo r2, [r0], #4
         strlo r2, [r1], #4
         blo loc_copy_highram
     ```
   - The copy loop stops strictly before `0x01107D00`, writing its final 4-byte word to `0x01107CFC..0x01107CFF`.
   - In inclusive notation, the true copied range is `0x010E1000..0x01107CFF` (half-open: `[0x010E1000, 0x01107D00)`), with size `0x26D00` (158,976 bytes = 155.25 KiB, matching cache clean size at line 120 and `PORT5B:178`).
   - Declaring `R-14` as inclusive `0x010E1000..0x01107D00` adds 1 extra byte (`0x26D01` bytes) and causes `R-15` to begin at `0x01107D01`, stranding `0x01107D00`.
4. **Region R-15 (`Upper DRAM Limit 0x3FFFFFFF`)**:
   - Infers a 1 GiB physical DRAM boundary without memory controller register evidence.
5. **Region R-17 (`Uncached Aperture Span 0x40000000..0x5FFFFFFF`)**:
   - Infers a 512 MiB uncached mapping range without MPU or bus controller register evidence.

### 3.5 Categorical Safety & Exclusion Inferences Lacking Primary Proof
1. **§1 "Proven Safe" Low-Heap Core Placement (CLM-23 / SA-1)**:
   - PR #23 asserts placement is categorically *"Proven safe from collision with BSS and low-RAM hardware structures"*. While arithmetic headroom is consistent with the prototype model, BSS bounds and Low-RAM data structures derive from historical notes (`PORT5B:78, 167, 168`) and prototype comments, not verified GM1.10C ROM disassembly. Runtime bootloader safety and hardware exception behavior remain uninspected.
2. **§3 DryOS Allocator Exclusion Proof (CLM-24 / SA-2)**:
   - PR #23 claims formal exclusion proof based on the premise that DryOS `AllocateMemory` only issues pointers $\ge r_4$. However, no tracked GM1.10C ROM disassembly of the DryOS heap allocator routines (`AllocateMemory`, sub-pool managers, or compaction routines) exists in the repository. While passing `sp[0x08] = r4` sets the lower bound in the prototype descriptor model (`boot_prototype.c:210`), proving zero runtime allocation below `r_4` requires disassembly of the allocator implementation.
3. **§4 "Zero" Collision Risk with AdditionAgent and OMAR (CLM-25 / SA-3)**:
   - PR #23 claims "Zero" collision risk with `AdditionAgent` and OMAR. While static arithmetic distance ($>3$ MiB) from assumed anchors is correct, neither anchor is primary-verified on GM1.10C: `AdditionAgent` ROM read routines (`0xFC55888C..0xFC5588C0`) are uninspected in ROM, and OMAR is explicitly classified as `HISTORICALLY REPORTED` and *"Not documented"* on GM1.10C (`PORT5B:172`). Asserting absolute "Zero risk" without verified GM1.10C IPC memory maps is an overstatement.
4. **§4 Assertion that Capture DMA Never Overwrites DryOS Heap Space (CLM-26 / SA-4)**:
   - PR #23 asserts that DryOS heap space is never overwritten by raw image capture DMA because Canon camera architecture supposedly isolates heap from framebuffers. This architectural generalization is not backed by any tracked primary evidence on GM1.10C. In fact, PR #23's own Section 6 explicitly acknowledges that sensor RAW DMA lower bounds (E-01) and peak continuous shooting heap allocations (E-05) remain unverified. Heuristic assumptions of architectural isolation cannot be treated as verified safety facts.

---

## 4. Test Execution & Analysis

### 4.1 Execution Details
- **Test File**: `tests/test_port12a_memory_ownership.py` (commit `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`)
- **Execution Workspace**: Isolated scratch environment (`/var/lib/agentbridge/.gemini/antigravity-cli/brain/fd8607d3-34e8-4dac-b722-0548372b08c0/scratch/test_port12a_memory_ownership.py`)
- **Test Command**:
  ```sh
  python3 /var/lib/agentbridge/.gemini/antigravity-cli/brain/fd8607d3-34e8-4dac-b722-0548372b08c0/scratch/test_port12a_memory_ownership.py -v
  ```
- **Execution Date**: 2026-10-28
- **Runner**: Python 3.10 standard library `unittest`

### 4.2 Test Results Ledger

| Test Case Name | Target Behavior | Result | Execution Time |
|---|---|:---:|---:|
| `test_addition_agent_isolation` | Verifies low-heap placement maintains $>3$ MiB margin from `AdditionAgent` (`0x006CE000`) | **PASS** | <0.001s |
| `test_adversarial_overlap_detection` | Injects synthetic overlapping rogue allocation and asserts detection | **PASS** | <0.001s |
| `test_canonical_known_regions_are_strictly_disjoint` | Verifies all regions in `CANONICAL_REGIONS` are non-overlapping | **PASS** | <0.001s |
| `test_contiguous_low_ram_partitioning` | Asserts contiguous partitioning `R-01 -> R-02 -> R-03 -> R-04 -> R-05` | **PASS** | <0.001s |
| `test_dryos_heap_headroom_512k_shift` | Asserts 512 KiB shifted heap base `0x003C89B4` maintains $>2.43$ MiB margin above `0x000B1FEC` | **PASS** | <0.001s |
| `test_dryos_heap_headroom_critical_limit` | Asserts headroom limit at `0x0061C014` and failure at `0x0061C015` | **PASS** | <0.001s |
| `test_dryos_heap_headroom_stock` | Asserts stock heap base `0x003489B4` maintains $>2.96$ MiB margin above `0x000B1FEC` | **PASS** | <0.001s |
| `test_historical_high_dram_cannot_be_verified` | Asserts Ranma region classification is `HISTORICAL_DESIGN_CANDIDATE` | **PASS** | <0.001s |
| `test_omar_secondary_core_isolation` | Verifies low-heap placement maintains $>3.2$ MiB margin from OMAR (`0x00700000`) | **PASS** | <0.001s |
| `test_unknown_gaps_are_not_treated_as_empty` | Asserts mid-DRAM and high-DRAM gaps are classified as `UNKNOWN` | **PASS** | <0.001s |
| **Total Suite Metrics** | **10 tests executed** | **10 PASS, 0 FAIL, 0 ERR** | **0.001s** |

### 4.3 Test Rigor & Epistemic Limitations
While all 10 tests pass, the test suite exhibits significant circularity:
1. `CANONICAL_REGIONS` hardcodes the classification `"VERIFIED_IN_EXISTING_DOCS"` for regions whose primary sources are untracked local documents (`CHDK_PORT1B`) or unverified historical notes.
2. `test_contiguous_low_ram_partitioning` enforces that `R-01` (`0x00000000..0x00007FFF`), `R-02` (`0x00008000..0x0003F4F3`), and `R-03` (`0x0003F4F4..0x003489B3`) form an exact, contiguous block. This assumes what has not been proven: that GM1.10C hardware has contiguous RAM from `0x00000000` to `0x0003F4F4` without hardware holes or remapped memory.
3. `test_historical_high_dram_cannot_be_verified` only checks a locally instantiated mock `MemoryRegion` string, which does not validate any repository data or prevent promotion in documentation.

---

## 5. Synthesis & Final Recommendation

### Formal Recommendation: **`needs-changes`**

Draft PR #23 contains valuable architectural analysis regarding the hazards of Ranma's GM1.10E high-DRAM placement and provides correct mathematical modeling of DryOS heap headroom. However, it cannot be merged in its current form due to extensive citations to untracked local files, over-promotion of unverified historical notes to verified status, inaccurate line numbers, unsupported address range expansions, and unbacked categorical safety assertions.

### Required Remediation Items for PR Author
1. **Purge Untracked Citations**:
   - Replace or contextualize all citations to `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B`, `docs/RANMA_SOURCE_ARCHAEOLOGY.md`, `g3x_110e.patch`, `platform/g3x/notes.txt`, and `platform/g3x/makefile.inc`.
   - If an engineering assumption relies on prototype source code, cite tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c` or tracked historical comparisons in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`.
2. **Reclassify Over-Promoted Regions & Qualify Categorical Safety Claims**:
   - Reserve `STATIC_VERIFIED` strictly for Region `R-16` (ATCM relocated span), which is verified by tracked GM1.10C ROM evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`.
   - Reclassify Regions `R-01`, `R-02`, `R-03`, `R-05`, `R-06`, `R-07`, `R-08`, `R-09`, `R-14`, and `R-17` to `INFERRED (Historical / Prototype Model)` or `HISTORICAL_CANDIDATE`, explicitly noting that their underlying ROM literals remain uninspected under authorized Phase 0 scopes.
   - Qualify categorical assertions:
     - Replace §1 "proven safe" assertions with `INFERRED (Design Candidate)`;
     - Replace §3 "allocator exclusion proof" with `INFERRED (Design Model)` noting that primary GM1.10C allocator disassembly is uninspected;
     - Replace §4 "zero collision risk" with `INFERRED (Design Margin Estimate)` noting unverified IPC bounds;
     - Reclassify §4 claim of capture DMA isolation from heap to `UNKNOWN / UNVERIFIED HEURISTIC`.
3. **Correct Citation Line Numbers**:
   - In `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, update references to point to actual lines:
     - Line 75 for RAM-code copy source (`0xfcec854c`, C:107);
     - Line 77 for Low-RAM data copy source (`0xfce91058`, C:134);
     - Line 78 for copy destinations/ranges and BSS end (`0x010e1000–0x01107d00`, `0xbfe10800–0xbfe17419`, `0x8000–0x3f4f4`, BSS → `0x3489b4`);
     - Line 101 for loader entry and `MEMBASEADDR=0x8000` (`entry.S: sp = MEMBASEADDR (0x8000)`);
     - Lines 169, 170, and 205 (Finding F6) for heap descriptor parameters (`sp[0]`, `sp[0x10]`, `sp[0x14]`, `0x0060E000`, `0x00600014`);
     - Line 171 for Canon ARAM heap (`0x006CE000–0x006EFFFF`, `0x22000`);
     - Line 172 for OMAR ("OMAR ram area" `0x00700000–0x0075FFFF`);
     - Line 178 for RAM-copied code memory map entry (`0x010E1000–0x01107CFF`);
     - Line 179 for RAM mirror / uncached mirror definitions (`0x20000000`/`0x40000000`).
4. **Correct Address Boundaries and Eliminate Fencepost Errors**:
   - State and consistently apply interval notation:
     - Throughout the matrix, use inclusive interval notation `[start, end]` (closed bounds) or explicitly label half-open notation `[start, end)`.
   - `R-09` (`AdditionAgent`):
     - `0x22000` bytes starting at `0x006CE000` end inclusively at `0x006EFFFF`, or half-open at `0x006F0000` (`[0x006CE000, 0x006F0000)`).
     - Restore documented range `0x006CE000..0x006EFFFF` (136 KiB), and mark the subsequent 64 KiB span `0x006F0000..0x006FFFFF` as an `UNKNOWN` uninspected gap rather than part of `AdditionAgent`.
   - `R-10` (`OMAR`):
     - Correct upper bound to `0x0075FFFF` (`0x60000` = exactly 384 KiB = 393,216 B) to fix the off-by-one fencepost error.
   - `R-14` (`Firmware Executable RAM Mirror`) and `R-15`:
     - Audit against tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115`, where the copy loop compares `r1` with upper limit `0x01107d00` using `blo` (`cmp r1, r3; itt lo; ldrlo r2, [r0], #4; strlo r2, [r1], #4; blo loc_copy_highram`), stopping strictly before `0x01107D00`.
     - The true copied range is `0x010E1000..0x01107CFF` inclusive (half-open: `[0x010E1000, 0x01107D00)`), with size `0x26D00` (158,976 bytes = 155.25 KiB, matching cache clean size at line 120 and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:178`).
     - Correct `R-14` upper bound to `0x01107CFF` (inclusive), and align `R-15` lower bound to `0x01107D00` (inclusive `0x01107D00..0x3FFFFFFF`).
5. **Update Test Suite**:
   - Adjust `CANONICAL_REGIONS` classifications and boundaries in `tests/test_port12a_memory_ownership.py` to match the corrected epistemic taxonomy and fencepost corrections (`R-09` ending at `0x006EFFFF`, `R-10` ending at `0x0075FFFF`, `R-14` ending at `0x01107CFF`).
   - Refactor `test_contiguous_low_ram_partitioning` to document that contiguity between `0x0` and `0x8000` is an architectural design assumption, not a verified hardware fact.
