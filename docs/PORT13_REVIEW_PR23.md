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
   - The core conceptual thesis of PR #23 is well-reasoned: rejecting the unsafe heuristic that uninspected DRAM is "free space", distinguishing `PROVEN_NO_OVERLAP` from `MERELY_NO_KNOWN_OVERLAP`, and identifying severe hazards with Ranma's high-DRAM placement (`0x00C80000`) on GM1.10C (such as sensor RAW circular DMA buffers, audio/video co-processor firmware blob loads, and lack of verified top-of-DRAM bounds).
   - The mathematical model of DryOS heap headroom (`0x006CE000 - r4 >= 0x000B1FEC`) matches prototype code in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:179` and tracked analysis in `docs/PROJECT_STATE.md:294`.
2. **Evidentiary Rigor & Citation Compliance (Critical Failures)**:
   - **Citing Untracked Documents as Checkable Evidence**: PR #23 extensively cites local, untracked files that do not exist on `origin/main` or in git history, specifically: `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B:26`, `CHDK_PORT1B:32`, `CHDK_PORT1B:47`, `CHDK_PORT1B:92`, and `docs/RANMA_SOURCE_ARCHAEOLOGY.md:46` (the latter exists only on an unmerged research branch `origin/research/g9-ranma-source-archaeology`).
   - **Over-Promotion to `VERIFIED_IN_EXISTING_DOCS`**: Out of 17 memory regions cataloged, 9 regions are labeled `VERIFIED_IN_EXISTING_DOCS`. However, only **one single aspect of one region (R-16a: ATCM relocated span bounds)** is backed by tracked primary GM1.10C ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`). The remaining regions rely on untracked notes or secondary tables in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, where line 72 explicitly notes: *"No ROM was read, and every C value is only as good as the existing document it comes from."*
   - **Conflation of Region Bounds with Subsystem Ownership**: PR #23 assigns definitive subsystem owners and bus masters (e.g. DryOS kernel object tables, scheduler ownership, CPU-1 IPC, DMA controllers) without tracked primary proof. Verified bounds do not verify ownership: per `docs/PORT11A_GM110C_ROM_EVIDENCE.md:26`, `STATIC_VERIFIED` applies strictly to static instruction effects and register/stack encodings, while semantic names and functional ownership remain `INFERRED`.
   - **Erroneous Sensor RAW Frame Size Arithmetic**: PR #23 endorses $5472 \times 3648 \times 14 / 8$, yielding 34,933,248 bytes (~33.315 MiB). $5472 \times 3648$ are the JPEG dimensions (`CAM_JPEG_WIDTH` L47, `CAM_JPEG_HEIGHT` L48 in `chdk-port/platform/g3x/platform_camera.h`), NOT the RAW sensor dimensions. The tracked RAW frame dimensions in `chdk-port/platform/g3x/platform_camera.h:44-56` are $5632 \times 3710$ at 14 bpp, yielding $36,565,760\text{ bytes} \approx 34.872\text{ MiB}$. Furthermore, frame-size arithmetic is strictly theoretical geometry and provides zero evidence of DMA buffer allocation, placement, or heap isolation.
   - **Inaccurate Line Citations & Transcriptions**: Citations to `PORT5B:78` do not contain `MEMBASEADDR=0x8000` (which is at line 101, referencing Ranma's GM1.10E `entry.S`) or BSS zeroing loops; citation to `PORT5B:48` for DMA address `0x43DBFCA0` references a line-count table row for `notes.txt`.
   - **Unsupported Span Expansions and Fencepost Errors**:
     - Region `R-09` (`AdditionAgent`): Declared as inclusive `0x006CE000..0x006FFFFF` (196 KiB claimed / 200 KiB inclusive). Tracked documentation confirms `AdditionAgent` reads up to `0x22000` bytes (136 KiB), ending inclusively at `0x006EFFFF` (half-open: `[0x006CE000, 0x006F0000)`). Expanding this region to `0x006FFFFF` arbitrarily subsumes a 64 KiB uninspected gap (`0x006F0000..0x006FFFFF`, `UNKNOWN`).
     - Region `R-10` (`OMAR`): Upper bound is given as `0x00760000` (384 KiB + 1 byte), whereas historical note `PORT5B:172` records `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB).
     - Region `R-14` (`Firmware Executable RAM Mirror`): Declared as inclusive `0x010E1000..0x01107D00`. Auditing tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115` proves the copy loop uses a strictly-less-than (`blo`) condition against limit `0x01107d00`, stopping strictly before `0x01107D00` (last word written to `0x01107CFC..0x01107CFF`, total size `0x26D00` = 155.25 KiB, confirmed by cache flush size at line 120 and `PORT5B:178`). PR #23's inclusive upper bound of `0x01107D00` adds 1 extra byte and causes Region `R-15` to begin at `0x01107D01`, stranding `0x01107D00`.
   - **Categorical Safety Assertions Lacking Primary Proof**: PR #23 presents categorical assertions—declaring low-heap placement "proven safe", claiming DryOS allocator exclusion proof, asserting "zero collision risk", and assuming camera architecture guarantees capture DMA never overwrites DryOS heap space—without primary disassembly of GM1.10C allocator routines or DMA controllers.
3. **Test Suite Status & Epistemic Grounding**:
   - The PR's test suite `tests/test_port12a_memory_ownership.py` was executed using standard library `unittest` and passed completely (**10/10 PASS**, 0.001s).
   - In PR #23's narrative, test margins were improperly claimed as `>2.43 MiB` and `>2.96 MiB` (confusing decimal megabytes with binary mebibytes). The exact byte margins recomputed from tracked constants are `2,438,752 B` (≈2.326 MiB) and `2,963,040 B` (≈2.826 MiB).
   - The test assertions verify internal arithmetic consistency but hardcode `VERIFIED_IN_EXISTING_DOCS` strings and assert contiguous partitioning across unverified boundaries, creating circular validation.

### Notation and Interval Conventions
Throughout this review report:
- Interval notation `[start, end]` denotes **inclusive (closed)** endpoints: both `start` and `end` are contained within the span (size = `end - start + 1`).
- Interval notation `[start, end)` denotes **half-open** endpoints: `start` is included, and `end` is excluded (size = `end - start`).
- In table entries, `start..end` denotes inclusive bounds `[start, end]`. When discussing copy limits, half-open notation is explicitly marked.

---

## 2. Per-Claim Evaluation Table

The following table evaluates all claims extracted from PR #23:
1. Cataloged memory region bounds and spatial allocations (`CLM-01a`..`CLM-17a`).
2. Primary owner, allocator, CPU, and bus-master assertions for each cataloged region (`CLM-01b`..`CLM-17b`, plus R-16 performance profile `CLM-16c`).
3. Quantitative headroom, arithmetic, and frame-size claims (`CLM-18`..`CLM-22`).
4. Categorical safety and architectural exclusion assertions (`CLM-23`..`CLM-26`).

> [!IMPORTANT]
> **Epistemic Principle on Ownership**: Verified memory bounds do not verify subsystem ownership. In accordance with `docs/PORT11A_GM110C_ROM_EVIDENCE.md:26`, static byte copy verification is restricted to instruction effects; functional ownership and semantic names remain `INFERRED`, and unverified hardware assertions remain `UNKNOWN`.

| Claim ID | Region / Subject | Address Range / Scope | PR Claimed Classification | Cited Source in PR #23 | Tracked on `origin/main`? | Reviewer Verdict | Reviewer Finding & Flag Notes |
|---|---|---|:---:|---|:---:|:---:|---|
| **CLM-01a (R-01 Bounds)** | Low Vector & Hardware Scratch (Bounds) | `0x00000000..0x00007FFF` (32 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78 (MEMBASEADDR=0x8000)` | Partial (`PORT5B` tracked; line 78 wrong; `MEMBASEADDR` is L101) | **`INFERRED / MISLABELED`** | **FLAGGED (Historical / Inaccurate Citation)**. Line 78 in `PORT5B` describes copy ranges, not `MEMBASEADDR`. `MEMBASEADDR=0x8000` appears at L101 as Ranma's loader stack setup in GM1.10E `entry.S`. Exception vector layout in `0x00000000..0x00007FFF` on GM1.10C is inferred from historical platforms, not ROM-verified. |
| **CLM-01b (R-01 Owner/Master)** | Low Vector & Hardware Scratch (Owner & Master) | Hardware Exception Vectors & System Scratch; Cortex-R4 (CPU 0) / Boot ROM | `VERIFIED_IN_EXISTING_DOCS` | `PORT5B:78` | Partial (`PORT5B:101` historical) | **`INFERRED`** | **FLAGGED (Unverified Ownership & Master)**. Exception vector table assignment and CPU 0 boot ROM control are architectural inferences from ARMv7-R and historical ports, not tracked GM1.10C ROM vector table disassembly. |
| **CLM-02a (R-02 Bounds)** | Low-RAM Data Section (Bounds) | `0x00008000..0x0003F4F3` (~221 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCE91058 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked local file `CHDK_PORT1B:26`. In `PORT5B`, Low-RAM data copy source `0xFCE91058` is at L77 (citing prototype `C:134`) and destinations at L78 and L167, with explicit caveat at L72 that no ROM was read. Copy source `0xFCE91058` is outside approved ROM inspection scopes. |
| **CLM-02b (R-02 Owner/Master)** | Low-RAM Data Section (Owner & Master) | DryOS Kernel Data & Globals; Cortex-R4 (CPU 0) | `VERIFIED_IN_EXISTING_DOCS` | `PORT5B:78, CHDK_PORT1B:26` | Partial | **`INFERRED`** | **FLAGGED (Unverified Ownership)**. Attribution of this span to DryOS kernel data (interrupt vectors, task control blocks, timer tables) is inferred from historical DryOS conventions; no tracked GM1.10C disassembly proves TCB structure layouts or kernel ownership. |
| **CLM-03a (R-03 Bounds)** | Canon Firmware BSS (Bounds) | `0x0003F4F4..0x003489B3` (~3.036 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Zeroed at boot 0xFC020070..0xFC020078 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked; `0xFC020070` inside S1A range in `PORT11A:60`) | **`INFERRED / UNTRACKED_CITATION / MISSING_PRIMARY_PROOF`** | **FLAGGED (Untracked Citation / Missing Primary Disassembly)**. Cites untracked `CHDK_PORT1B:26`. `PORT5B:78` lists BSS end `0x3489b4` from prototype `C:144-153`, but has no BSS zeroing loop instructions. While address `0xFC020070` falls inside the read range of pinned ROM Slice `S1A` (`0xFC020040..0xFC0200CF`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:60`), `PORT11A` only analyzed the ATCM copy loop (`0xFC020040..0xFC020052`) and literals; no tracked analysis of `0xFC020070..0xFC020078` supports the BSS zeroing claim (Case b). BSS end `0x003489B4` is modeled in prototype, but ROM loop is unanalyzed. |
| **CLM-03b (R-03 Owner/Master)** | Canon Firmware BSS (Owner & Master) | Canon Firmware Static BSS; Cortex-R4 (CPU 0) | `VERIFIED_IN_EXISTING_DOCS` | `PORT5B:78, CHDK_PORT1B:26` | Partial | **`INFERRED`** | **FLAGGED (Unverified Ownership)**. Static BSS designation and CPU 0 access are modeled from prototype comments; zeroing loop instructions and variable layout have zero tracked primary proof. |
| **CLM-04a (R-04 Bounds)** | Low-Heap Prototype Target (Bounds) | `0x003489B4..0x003C89B3` (512 KiB) | `INFERRED (Design Candidate)` | `Linker script & docs/CHDK_PORT1B_HEAP_PROOF.md:92` | No (both untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification as `INFERRED` design candidate is epistemically sound, but citations ("Linker script" and `CHDK_PORT1B_HEAP_PROOF.md:92`) refer to untracked local files not present in the repository. |
| **CLM-04b (R-04 Owner/Master)** | Low-Heap Prototype Target (Owner & Master) | CHDK Core Prototype (Shifted Heap Base); Cortex-R4 (CPU 0) | `INFERRED (Design Candidate)` | `Linker script & docs/CHDK_PORT1B_HEAP_PROOF.md:92` | No | **`INFERRED (Design Candidate)`** | Proposed software payload allocation. Valid candidate design model, but cites untracked files. |
| **CLM-05a (R-05 Bounds)** | DryOS Main Heap Pool 0 (Bounds) | `0x003C89B4..0x00600013` (~2.216 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474 (0x00600014), CHDK_PORT1B:47` | Partial (`0x00600014` in `boot_prototype.c:209-211` and `PORT5B:169, 205`; literal `0xFC05B474` and `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal address `0xFC05B474` has no tracked reference anywhere in the repo (Case c). Sub-pool limit `0x00600014` is in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-211` and `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169, 205` (where descriptor semantics are explicitly marked `INFERRED`). |
| **CLM-05b (R-05 Owner/Master)** | DryOS Main Heap Pool 0 (Owner & Master) | DryOS Dynamic System Heap (`AllocateMemory`); Cortex-R4 / System Tasks | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:47` | No | **`INFERRED`** | **FLAGGED (Unverified Allocator & Ownership)**. Allocator identity (`AllocateMemory`) and system task authority are inferred from DryOS conventions; ROM allocator routines are uninspected in GM1.10C. |
| **CLM-06a (R-06 Bounds)** | DryOS Sub-pool & Kernel Descriptors (Bounds) | `0x00600014..0x0060DFFF` (56 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474, CHDK_PORT1B:47` | No | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal `0xFC05B474` has no tracked reference anywhere in the repo (Case c). `PORT5B:169, 205` classifies descriptor parameters as `INFERRED`. |
| **CLM-06b (R-06 Owner/Master)** | DryOS Sub-pool & Kernel Descriptors (Owner & Master) | DryOS Kernel Object Tables (tasks, semaphores, message queues, condvars); DryOS Kernel | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:47` | No | **`INFERRED`** | **FLAGGED (Unverified Object Table Semantics)**. Descriptor slot semantics are classified as `INFERRED` in `PORT5B:169, 205`; assigning specific OS object tables (semaphores, queues) has zero tracked primary evidence. |
| **CLM-07a (R-07 Bounds)** | DryOS Heap Upper Chunk Block (Bounds) | `0x0060E000..0x006CDFFF` (768 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B470, chunk size 0x000C0000, CHDK_PORT1B:47` | Partial (`0x0060E000` in `PORT5B:170, 205` and `boot_prototype.c:206, 212`; literal `0xFC05B470` & `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Missing Literal)**. Cites untracked `CHDK_PORT1B:47`. Literal `0xFC05B470` has no tracked reference anywhere in the repository (Case c). Chunk size `0x000C0000` and descriptor slot `sp[0x14] = 0x0060E000` appear in `boot_prototype.c:206, 212` and `PORT5B:170, 205` (marked `INFERRED`). |
| **CLM-07b (R-07 Owner/Master)** | DryOS Heap Upper Chunk Block (Owner & Master) | DryOS Fixed Chunk Allocator; DryOS Kernel | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:47` | No | **`INFERRED`** | **FLAGGED (Unverified Allocator Role)**. Fixed chunk allocator mechanism is an inference from stack descriptor slot values; uninspected in ROM. |
| **CLM-08a (R-08 Bounds)** | DryOS System Limit & Headroom Assert (Anchor) | `0x006CE000` (Anchor) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B454 (0x006CE000), CHDK_PORT1B:32` | Partial (`0x006CE000` in `PROJECT_STATE.md:294` & `HANDOFF.md:793`; `0xFC05B454` in `PORT5A:108`; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Non-Primary Reference)**. Cites untracked `CHDK_PORT1B:32`. Literal address `0xFC05B454` appears in `docs/PORT5A_RANMA_PORT_RECOVERY.md:108` only as a secondary comparison table entry, not reproducible primary ROM proof (Case a). The headroom limit `0x006CE000` is documented in `docs/PROJECT_STATE.md:294` and `boot_prototype.c:179`, but derives from unpinned early research traces. |
| **CLM-08b (R-08 Owner/Master)** | DryOS System Limit & Headroom Assert (Owner & Master) | Kernel Headroom Comparator Limit; DryOS Kernel Init | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:32` | Partial | **`INFERRED`** | **FLAGGED (Uninspected Kernel Function)**. Comparator check role is inferred from prototype math; kernel init routine `0xFC05B3C8` is uninspected in GM1.10C ROM. |
| **CLM-09a (R-09 Bounds)** | AdditionAgent Conflict Zone (Bounds) | `0x006CE000..0x006FFFFF` (196 KiB claimed / 200 KiB inclusive) | `VERIFIED_IN_EXISTING_DOCS` | `0xFC55888C..0xFC5588C0 (docs/RANMA_SOURCE_ARCHAEOLOGY.md:46)` | Partial (ROM routine in `HANDOFF.md:830` & `PROJECT_STATE.md:308`; `PORT5B:171`; `docs/RANMA_SOURCE_ARCHAEOLOGY.md` untracked on `main`) | **`INFERRED / UNTRACKED_CITATION / CONTRADICTED_BOUNDS`** | **FLAGGED (Untracked Citation / Unsupported Span Extension / Fencepost Error)**. Cites unmerged branch artifact `docs/RANMA_SOURCE_ARCHAEOLOGY.md`. Tracked docs (`PORT5B:171`, `HANDOFF.md:830`, `PROJECT_STATE.md:308`) specify `AdditionAgent` reads up to `0x22000` bytes (136 KiB), spanning inclusively `0x006CE000..0x006EFFFF` (half-open: `[0x006CE000, 0x006F0000)`). Expanding this region to `0x006FFFFF` arbitrarily absorbs the subsequent 64 KiB uninspected gap `0x006F0000..0x006FFFFF` (`UNKNOWN`). |
| **CLM-09b (R-09 Owner/Master)** | AdditionAgent Conflict Zone (Owner & Master) | `AdditionAgent.c` Storage Direct Buffer; Storage DMA / `Fread_Fut` | `VERIFIED_IN_EXISTING_DOCS` | `docs/RANMA_SOURCE_ARCHAEOLOGY.md:46` | Partial | **`INFERRED`** | **FLAGGED (Unverified DMA Master & Subsystem)**. Attribution to storage direct buffer and `Fread_Fut` DMA is inferred from Ranma's archaeology notes and debug strings; no tracked GM1.10C storage DMA controller disassembly. |
| **CLM-10a (R-10 Bounds)** | OMAR Secondary Core Staging RAM (Bounds) | `0x00700000..0x00760000` (384 KiB + 1 byte) | `HISTORICAL_CANDIDATE` | `Ranma platform/g3x/notes.txt:45–46, PORT5B` | Partial (`PORT5B:172` tracked; `notes.txt` untracked) | **`HISTORICAL_CANDIDATE / OFF_BY_ONE`** | **FLAGGED (Historical / Untracked Citation / Fencepost Error)**. Cites untracked `notes.txt`. In tracked `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`, Ranma's GM1.10E range is recorded as `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB) and explicitly classified as *"Not documented"* on GM1.10C (`HISTORICALLY REPORTED`). PR #23's upper bound `0x00760000` adds 1 extra byte (`0x60001` = 393,217 B). |
| **CLM-10b (R-10 Owner/Master)** | OMAR Secondary Core Staging RAM (Owner & Master) | Secondary Core (*Omar*) IPC & Staging; Cortex-R4 (CPU 1) / IPC DMA | `HISTORICAL_CANDIDATE` | `Ranma platform/g3x/notes.txt:45–46, PORT5B` | Partial (`PORT5B:172` tracked) | **`INFERRED / UNKNOWN`** | **FLAGGED (Unverified CPU-1 / IPC Master Attribution)**. Ranma's GM1.10E note called this "OMAR ram area", but attribution to Cortex-R4 CPU 1, inter-core mailbox IPC, and IPC DMA is entirely unverified on GM1.10C. `PORT5B:172` explicitly marks this region *"Not documented"* on GM1.10C and strictly `HISTORICALLY REPORTED`. No tracked primary evidence exists for CPU 1 ownership or IPC bus-mastering. |
| **CLM-11 (R-11 Bounds & Owner)** | Mid DRAM Uninspected Gap | `0x00760001..0x00C7FFFF` (~5.12 MiB); Owner: Unknown | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly classifies uninspected DRAM and unassigned bus mastering as `UNKNOWN` and rejects treating it as empty memory. |
| **CLM-12 (R-12 Bounds & Owner)** | Ranma High-DRAM CHDK Placement | `0x00C80000..0x00DFFFFF` (1.5 MiB); Owner: Ranma CHDK Core / CPU 0 | `HISTORICAL_DESIGN_CANDIDATE` | `platform/g3x/makefile.inc:29–37, g3x_110e.patch:580` | Partial (`PORT5B:175` documents values; local patch files untracked) | **`HISTORICAL_CANDIDATE / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification as historical candidate unproven on GM1.10C is sound (`PORT5B:175`), but citations to `platform/g3x/makefile.inc` and `g3x_110e.patch` are to untracked local files. |
| **CLM-13 (R-13 Bounds & Owner)** | High DRAM Uninspected Gap | `0x00E00000..0x010E0FFF` (~2.88 MiB); Owner: Unknown | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly flags uninspected DRAM gap and unknown bus master as `UNKNOWN`. |
| **CLM-14a (R-14 Bounds)** | Firmware Executable RAM Mirror (Bounds) | `0x010E1000..0x01107D00` (155.25 KiB claimed / 158,977 B inclusive) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEC854C (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B:75, 78, 177` and `boot_prototype.c:108-115` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION / FENCEPOST_ERROR`** | **FLAGGED (Untracked Citation / Fencepost Error)**. Cites untracked `CHDK_PORT1B:26`. In `PORT5B`, source `0xFCEC854C` is at L75 and copy ranges at L78 (citing prototype `C:107`, `C:108-147`), with memory map row at L177 giving `0x010E1000–0x01107CFF`. Auditing tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c:108-115` reveals the copy loop uses a strictly-less-than (`blo`) condition against upper limit `0x01107d00`, stopping strictly before `0x01107D00` (last word written to `0x01107CFC..0x01107CFF`, total size `0x26D00` = 158,976 B = 155.25 KiB, matching cache clean size at line 120). Stating inclusive range as `0x010E1000..0x01107D00` is a 1-byte fencepost error that causes `R-15` to start at `0x01107D01`, stranding `0x01107D00`. |
| **CLM-14b (R-14 Owner/Master)** | Firmware Executable RAM Mirror (Owner & Master) | Canon ROM Routines Copied to Executable RAM; Cortex-R4 (CPU 0) Code Bus | `VERIFIED_IN_EXISTING_DOCS` | `PORT5B:78, CHDK_PORT1B:26` | Partial | **`INFERRED`** | **FLAGGED (Unverified Code Identity)**. While the copy loop in `boot_prototype.c:108-115` copies words, the specific routine identity and instruction contents are uninspected in tracked GM1.10C ROM disassemblies. |
| **CLM-15a (R-15 Bounds)** | Upper DRAM & DMA Capture Buffers (Bounds) | `0x01107D01..0x3FFFFFFF` (~1006 MiB) | `UNKNOWN` | `Dynamic heap / peripheral DMA (0x43DBFCA0, PORT5B:48)` | Partial (`PORT5B` tracked; L48 irrelevant; `0x43DBFCA0` in `HANDOFF.md:830` & `PROJECT_STATE.md:308`) | **`UNKNOWN / INACCURATE_CITATION`** | **FLAGGED (Inaccurate Line Citation / Inferred Bound / Fencepost Offset)**. `PORT5B:48` is a table line count for `notes.txt`. `0x43DBFCA0` is in `docs/HANDOFF.md:830` and `docs/PROJECT_STATE.md:308`. Lower bound should start at `0x01107D00` rather than `0x01107D01` (due to R-14's true endpoint `0x01107CFF`). Upper bound `0x3FFFFFFF` is inferred without physical DRAM size register evidence. Classification `UNKNOWN` is correct. |
| **CLM-15b (R-15 Owner/Master)** | Upper DRAM & DMA Capture Buffers (Owner & Master) | Sensor RAW, JPEG encoder, Video Buffers; Video DMA, Sensor ISP | `UNKNOWN` | `PORT5B:48` | Partial | **`UNKNOWN / UNVERIFIED HEURISTIC`** | **FLAGGED (Unverified Bus Master Heuristic)**. Dynamic peripheral allocation and DMA bus master attribution are plausible inferences from camera architecture, but completely unproven by tracked primary evidence. |
| **CLM-16a (R-16 Bounds)** | Cortex-R4 ATCM Relocated Span (Bounds) | `0xBFE10800..0xBFE1741B` (27,676 B) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEEF24C..0xFCEF5E67 (PORT11A:20, PR #19)` | Yes (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`) | **`STATIC_VERIFIED`** | **VERIFIED BOUNDS**. Accurately cites tracked `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20` and approved ROM slice `S1A` (`0xFC020040..0xFC0200CF`, L60). Proves copy of 6,919 words (27,676 B) to `0xBFE10800..0xBFE1741B`. Sole genuinely verified address bound in PR #23. |
| **CLM-16b (R-16 Scheduler Claim)** | Cortex-R4 ATCM Relocated Span (Scheduler Ownership) | Cortex-R4 Tightly Coupled Memory containing critical OS routines (`CreateTask`, `CreateTaskStrictly`, scheduler) | `VERIFIED_IN_EXISTING_DOCS` | `PORT11A:20, PR #19` | Yes (`PORT11A`) | **`INFERRED`** | **FLAGGED (Over-Promoted Ownership Claim)**. `docs/PORT11A_GM110C_ROM_EVIDENCE.md:26` explicitly limits verification to static instruction encodings and register/stack effects, marking all semantic names (`CreateTask`, `CreateTaskStrictly`, scheduler) as `INFERRED`. Static copy loop bytes do not verify functional scheduler ownership. |
| **CLM-16c (R-16 Timing Claim)** | Cortex-R4 ATCM Relocated Span (Performance Profile) | "Fast zero-wait-state RAM" | `VERIFIED_IN_EXISTING_DOCS` | None cited in PR #23 | No | **`UNKNOWN / UNVERIFIED HARDWARE HEURISTIC`** | **FLAGGED (Unverified Hardware Timing Heuristic)**. Cortex-R4 TCM wait states, memory controller bus arbitration, and timing registers are uninspected in GM1.10C ROM/hardware. Stating that ATCM is "zero-wait-state" is an architectural heuristic, not a verified property. |
| **CLM-17a (R-17 Bounds)** | Uncached Peripheral Memory Mappings (Bounds) | `0x40000000..0x5FFFFFFF` (512 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `0x42281000, 0x42283000, 0x406CE000 (CHDK_PORT1B:47)` | Partial (`CAM_UNCACHED_BIT 0x40000000` tracked in `chdk-port/platform/g3x/platform_camera.h:38`; `PORT5B:179`; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:47`. `PORT5B:179` classifies `0x20000000`/`0x40000000` as `HISTORICALLY REPORTED` (`P:699, 711`). Range `0x40000000..0x5FFFFFFF` (512 MiB) is an architectural inference without MPU or peripheral aperture proof. |
| **CLM-17b (R-17 Owner/Master)** | Uncached Peripheral Memory Mappings (Owner & Master) | Uncached Aliases of DRAM & DMA Apertures; Peripheral DMA Controllers | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:47` | No | **`INFERRED / UNKNOWN`** | **FLAGGED (Unverified Master)**. Physical peripheral aperture and DMA master mapping are inferred without MPU or peripheral controller proof. |
| **CLM-18 (AR-1)** | DryOS Stock Headroom Check | `0x006CE000 - 0x003489B4 = 3,692,108 B >= 729,068 B` (Margin: 2,963,040 B ≈ 2.826 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:32` | Partial (formula in `boot_prototype.c:179` & `PROJECT_STATE.md:294`; `CHDK_PORT1B` untracked) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic matches prototype model in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:179` and `docs/PROJECT_STATE.md:294`, but cites untracked `CHDK_PORT1B`. Kernel init routine `0xFC05B3C8` is uninspected in GM1.10C ROM. |
| **CLM-19 (AR-2)** | DryOS Shifted 512 KiB Headroom Check | `0x006CE000 - 0x003C89B4 = 3,167,820 B >= 729,068 B` (Margin: 2,438,752 B ≈ 2.326 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B_HEAP_PROOF.md` | No (untracked file) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic is mathematically sound for shifted heap base, but cites untracked document. |
| **CLM-20 (AR-3)** | Low-Heap Isolation from AdditionAgent | `0x006CE000 - 0x003C89B4 = 3.02 MiB > 3 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming `AdditionAgent` base is `0x006CE000` and heap shift is `0x003C89B4`. |
| **CLM-21 (AR-4)** | Low-Heap Isolation from OMAR | `0x00700000 - 0x003C89B4 = 3.21 MiB > 3.2 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming OMAR base is `0x00700000`. |
| **CLM-22 (AR-5)** | Ranma High-DRAM Sensor RAW Hazard & Frame Size Arithmetic | Uncompressed raw frame size claims (~35 MiB / $5472 \times 3648 \times 14$ bits) | `UNKNOWN` (Hazard Analysis) | PR #23 §1, §2 (R-15), §4 (Decision Memo) | Yes (`chdk-port/platform/g3x/platform_camera.h:44-56`) | **`ERRONEOUS_CALCULATION / UNVERIFIED_ALLOCATION`** | **FLAGGED (Wrong Dimensions, Erroneous Arithmetic, Unverified Heap Isolation)**.<br>1. PR #23 endorses $5472 \times 3648 \times 14 / 8$, yielding 34,933,248 bytes (~33.315 MiB). $5472 \times 3648$ are the JPEG dimensions (`CAM_JPEG_WIDTH` L47, `CAM_JPEG_HEIGHT` L48 in `chdk-port/platform/g3x/platform_camera.h`), NOT the RAW sensor dimensions.<br>2. Tracked `chdk-port/platform/g3x/platform_camera.h:44-56` gives RAW $5632 \times 3710$ at 14 bpp: `CAM_RAW_ROWPIX = 5632` (L44), `CAM_RAW_ROWS = 3710` (L45), `CAM_SENSOR_BITS_PER_PIXEL = 14` (L56).<br>3. True uncompressed 14 bpp RAW frame product: $5632 \times 3710 \times 14 / 8 = 36,565,760\text{ bytes} \approx 34.872\text{ MiB}$. PR #23's figure is wrong.<br>4. Crucial Epistemic Boundary: Frame-size arithmetic is strictly theoretical sensor geometry and does NOT provide evidence of DMA buffer allocation, physical placement, or isolation from the heap on GM1.10C. |
| **CLM-23 (SA-1)** | §1 Categorical Assertion: "Proven safe" Low-Heap Placement | `0x003489B4..0x003C89B3` (512 KiB) vs BSS & Low-RAM | `VERIFIED_IN_EXISTING_DOCS` | PR #23 §1 Key Findings (cites `0xFC05B3C8` & headroom formula) | Partial (math in `boot_prototype.c:179`; routine `0xFC05B3C8` uninspected) | **`INFERRED / OVERSTATED_SAFETY_CLAIM`** | **FLAGGED (Categorical Safety Assertion / Uninspected Preconditions)**. PR #23 asserts placement is categorically *"Proven safe from collision with BSS and low-RAM hardware structures"*. While arithmetic headroom is consistent with the prototype model, BSS bounds and Low-RAM data structures derive from historical notes (`PORT5B:78, 167, 168`) and prototype comments, not verified GM1.10C ROM disassembly. Runtime bootloader safety and hardware exception behavior remain uninspected. Must be qualified as `INFERRED (Design Candidate)` or backed by tracked primary evidence. |
| **CLM-24 (SA-2)** | §3 Categorical Assertion: DryOS Allocator Exclusion Proof | `0x003489B4..0x003C89B3` (512 KiB exclusion zone) | `PROVEN_NO_OVERLAP` | PR #23 §3 (anchored to BSS `_end` via literal `0xFC05B450` and heap descriptor `sp[0x08] = r4`) | Partial (`0xFC05B450` in `PROJECT_STATE.md:295`; descriptor in `boot_prototype.c:206-212`; allocator logic untracked) | **`INFERRED / UNVERIFIED_ALLOCATOR_MODEL`** | **FLAGGED (Categorical Safety Assertion / Missing Primary Allocator Proof)**. PR #23 claims formal exclusion proof based on the premise that DryOS `AllocateMemory` only issues pointers $\ge r_4$. However, no tracked GM1.10C ROM disassembly of DryOS heap allocator routines (`AllocateMemory`, sub-pool managers, compaction) exists in the repo. While setting `sp[0x08] = r4` sets the lower bound in the prototype descriptor model (`boot_prototype.c:210`), proving zero runtime allocation below `r_4` requires disassembly of the allocator implementation. Must be qualified as `INFERRED (Design Model)` or backed by tracked primary ROM disassembly. |
| **CLM-25 (SA-3)** | §4 Categorical Assertion: "Zero" Collision Risk with AdditionAgent and OMAR | Margins: $3.02$ MiB to `0x006CE000`; $3.21$ MiB to `0x00700000` | "Zero" Risk | PR #23 §4 Decision Memo table (arithmetic distance from `0x003C89B4` to `0x006CE000` and `0x00700000`) | Partial (arithmetic correct; base bounds of AdditionAgent and OMAR unverified) | **`INFERRED / OVERSTATED_RISK_CLAIM`** | **FLAGGED (Categorical Safety Assertion)**. PR #23 claims "Zero" collision risk with `AdditionAgent` and OMAR. While static arithmetic distance ($>3$ MiB) from assumed anchors is correct, neither anchor is primary-verified on GM1.10C: `AdditionAgent` ROM read routines (`0xFC55888C..0xFC5588C0`) are uninspected in ROM, and OMAR is explicitly classified as `HISTORICALLY REPORTED` and *"Not documented"* on GM1.10C (`PORT5B:172`). Asserting absolute "Zero risk" without verified GM1.10C IPC memory maps is an overstatement; must be qualified as `INFERRED (Design Margin Estimate)` rather than categorical zero risk. |
| **CLM-26 (SA-4)** | §4 Categorical Assertion: Capture DMA Never Overwrites DryOS Heap Space | DryOS Heap Space (`0x003489B4..0x006CDFFF`) vs DMA Framebuffers | "High" Safety / Architectural Fact | PR #23 §4 Decision Memo table ("(Canon camera architecture isolates heap from framebuffers)") | No (Untracked architectural generalization) | **`UNKNOWN / UNVERIFIED_HEURISTIC`** | **FLAGGED (Categorical Safety Assertion / Unverified Heuristic)**. PR #23 asserts that DryOS heap space is never overwritten by raw image capture DMA because Canon camera architecture supposedly isolates heap from framebuffers. This architectural generalization is not backed by any tracked primary evidence on GM1.10C. In fact, PR #23's own Section 6 explicitly acknowledges that sensor RAW DMA lower bounds (E-01) and peak continuous shooting heap allocations (E-05) remain unverified. Heuristic assumptions of architectural isolation cannot be treated as verified safety facts; verdict must be qualified as `UNKNOWN / UNVERIFIED HEURISTIC` or backed by tracked primary evidence. |

---

## 3. Explicit Inventory of Flagged Claims

Per the acceptance criteria and reviewer guidelines, the following subsections catalog every claim that violates evidentiary standards:

### 3.1 Claims Relying on Historical Firmware (GM1.00C / GM1.10E / `g3x_110e.patch`) as GM1.10C Proof
1. **Claim CLM-01a / CLM-01b (Region R-01: `0x00000000..0x00007FFF`)**:
   - Relies on `MEMBASEADDR=0x8000`, which originates from Ranma's `entry.S` (`P:28–36` in `g3x_110e.patch` for GM1.10E, documented in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:101`). Treated as proving a 32 KiB "Low Vector & Hardware Scratch" allocation and CPU-0 ownership on GM1.10C.
2. **Claim CLM-10a / CLM-10b (Region R-10: `0x00700000..0x00760000`)**:
   - Derives from Ranma's GM1.10E comment "OMAR ram area" (`P:693–694` in `g3x_110e.patch`, recorded in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`). `PORT5B` explicitly states that this region is **`Not documented`** in GM1.10C and is strictly **`HISTORICALLY REPORTED`**. Attributing this region to Cortex-R4 CPU 1, inter-core mailbox IPC, and IPC DMA lacks any tracked GM1.10C primary evidence.
3. **Claim CLM-12 (Region R-12: `0x00C80000..0x00DFFFFF`)**:
   - Derives from Ranma's GM1.10E `MEMISOSTART = 0x00C80000` (`g3x_110e.patch:580`, recorded in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`). While PR #23 correctly warns that this is unproven on GM1.10C, it cites untracked historical patch lines as evidence sources.
4. **Claim CLM-17a / CLM-17b (Region R-17: `0x40000000..0x5FFFFFFF`)**:
   - Derives from Ranma's GM1.10E patch definitions (`P:699, 711`), classified in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179` as **`HISTORICALLY REPORTED`**.

### 3.2 Claims Citing Untracked / Local-Only L1/L2 Sources as Checkable Evidence
1. **`docs/PORT1B_HEAP_PROOF.md` / `CHDK_PORT1B_HEAP_PROOF.md`**:
   - Cited in Section 2 introductory text, Section 4 Decision Memo, and CLM-04a (R-04: `docs/CHDK_PORT1B_HEAP_PROOF.md:92`), CLM-19 (AR-2).
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

### 3.5 Ownership, Bus-Master, and Hardware Performance Attributions Lacking Primary Proof
A central defect in PR #23 is the conflation of physical/copied address bounds with functional subsystem ownership:
1. **Region R-16 ATCM Ownership and Performance Profile (CLM-16b, CLM-16c)**:
   - PR #23 attributes `0xBFE10800..0xBFE1741B` to "Cortex-R4 Tightly Coupled Memory" containing "critical OS routines (`CreateTask`, `CreateTaskStrictly`, scheduler)" and describes it as "Fast zero-wait-state RAM".
   - `docs/PORT11A_GM110C_ROM_EVIDENCE.md:26` explicitly governs verification status: `STATIC_VERIFIED` applies strictly to static instruction bytes and register/stack effects. Semantic identifiers (`CreateTask`, `CreateTaskStrictly`, scheduler) are classified as `INFERRED`. Static copy loop bytes do not verify functional scheduler ownership.
   - Furthermore, asserting zero wait states is an unverified hardware heuristic. Bus interface wait states and TCM configuration registers in the Cortex-R4 core have not been inspected in GM1.10C ROM or hardware (`UNKNOWN`).
2. **Region R-10 OMAR Secondary Core & IPC DMA Attribution (CLM-10b)**:
   - PR #23 attributes `0x00700000..0x00760000` to "Secondary Core (*Omar*) IPC & Staging" and names the bus master as "Cortex-R4 (CPU 1) / IPC DMA".
   - This claim relies exclusively on Ranma's historical note in GM1.10E `notes.txt`. In tracked `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`, this region is classified as `HISTORICALLY REPORTED` and explicitly marked *"Not documented"* on GM1.10C.
   - There is zero tracked primary evidence in the repository verifying that CPU 1 or an IPC DMA controller owns or accesses this range on GM1.10C. The ownership verdict must be `INFERRED / UNKNOWN`.
3. **Low-RAM Kernel Data, BSS, and OS Object Tables (CLM-01b, CLM-02b, CLM-03b, CLM-05b, CLM-06b, CLM-07b)**:
   - PR #23 labels ownership of `R-01` through `R-07` as `VERIFIED_IN_EXISTING_DOCS`.
   - In reality, attributing `R-02` to task control blocks and timer tables, `R-05` to `AllocateMemory` dynamic tasks, `R-06` to semaphores and message queues, and `R-07` to a fixed chunk allocator represents software modeling and architectural inferences from generic DryOS conventions, not verified GM1.10C disassembly.

### 3.6 Erroneous Sensor RAW Frame Calculation and Heap Isolation Claims (CLM-22 / AR-5)
PR #23 relies on the hazard of sensor RAW circular DMA buffers in High DRAM to justify rejecting Ranma's `0x00C80000` placement. However, the quantitative calculation in PR #23 is erroneous:
1. **Wrong Dimension Inputs**: PR #23 endorses $5472 \times 3648 \times 14\text{ bits} / 8 = 34,933,248\text{ bytes} \approx 33.315\text{ MiB}$. The dimensions $5472 \times 3648$ are the JPEG output dimensions defined in tracked `chdk-port/platform/g3x/platform_camera.h`:
   - Line 47: `#define CAM_JPEG_WIDTH 5472`
   - Line 48: `#define CAM_JPEG_HEIGHT 3648`
   They do not represent the raw Bayer sensor dimensions.
2. **Tracked Primary RAW Parameters**: Tracked `chdk-port/platform/g3x/platform_camera.h:44-56` defines the true sensor geometry:
   - Line 44: `#define CAM_RAW_ROWPIX 5632`
   - Line 45: `#define CAM_RAW_ROWS 3710`
   - Line 56: `#define CAM_SENSOR_BITS_PER_PIXEL 14`
3. **Correct RAW Frame Arithmetic**:
   $$\text{Pixels} = 5632 \times 3710 = 20,894,720\text{ pixels}$$
   $$\text{Frame Size (Bytes)} = \frac{20,894,720 \times 14\text{ bits}}{8\text{ bits/byte}} = 36,565,760\text{ bytes}$$
   $$\text{Frame Size (MiB)} = \frac{36,565,760\text{ bytes}}{1,048,576\text{ bytes/MiB}} \approx 34.8718\text{ MiB} \approx 34.872\text{ MiB}$$
   (or ~36.57 MB in decimal units).
   PR #23's claimed figure is wrong.
4. **Epistemic Limitation on DMA Allocation**:
   Frame-size arithmetic is strictly a geometric calculation based on header macro definitions. It does **NOT** constitute evidence of:
   - Whether DMA buffers are allocated statically or dynamically;
   - Where capture buffers are physically placed in DRAM;
   - How many circular ringbuffers are instantiated at runtime;
   - Whether camera hardware architecture isolates capture buffers from the DryOS heap.

### 3.7 Categorical Safety & Exclusion Inferences Lacking Primary Proof
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

### 4.1 Execution Details & Sandbox Whitelist Compliance
To evaluate PR #23, testing was executed against the exact target branch `origin/research/port12a-memory-ownership` at commit `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`:

1. **Branch Fetching & Target Commit Verification**:
   - `git fetch origin research/port12a-memory-ownership` fetched the branch read-only.
   - Verified commit SHA: `git rev-parse FETCH_HEAD` = `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`.
2. **Scratch Worktree Command Attempt & Shell Whitelist Refusal**:
   - *Attempted Command*: `git worktree add --detach /tmp/scratch-port12a-worktree 3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`
   - *Refusal & Constraint Disclosure*: The AgentBridge execution environment enforces strict headless sandboxing. The command whitelist explicitly permits `git worktree list`, but excludes `git worktree add` and `git worktree remove` (and repository governance rules strictly prohibit modifying `.git` or creating external worktrees outside the assigned worktree). Attempting to execute `git worktree add` is refused by the shell whitelist enforcer.
3. **Deterministic Fallback Extraction & Blob Hash Verification**:
   - *Fallback Procedure*: Per instructions, the PR's test module was extracted from git object storage using tracked read-only commands:
     - `git rev-parse 3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4:tests/test_port12a_memory_ownership.py` $\to$ blob SHA **`e1df1a24d22fc18045ce9a64a17c0542f3c538af`** (8,492 bytes).
     - File extracted via `git show 3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4:tests/test_port12a_memory_ownership.py` into persistent scratch location `/var/lib/agentbridge/.gemini/antigravity-cli/brain/39f8b0e9-1f1d-437c-a28d-5ad59a52ff6e/scratch/test_port12a_memory_ownership.py`.
     - The extracted file's git object SHA-1 was computed in Python: `hashlib.sha1(b"blob 8492\0" + content).hexdigest()`.
     - *Result*: Computed hash exactly matched `e1df1a24d22fc18045ce9a64a17c0542f3c538af`.
4. **Execution Command**:
   ```sh
   cd /var/lib/agentbridge/.gemini/antigravity-cli/brain/39f8b0e9-1f1d-437c-a28d-5ad59a52ff6e/scratch && python3 -B -m unittest -v test_port12a_memory_ownership
   ```
   - **Execution Environment**: Python 3.10 standard library `unittest` (no pytest, no pip).
   - **Exit Status**: `0`
   - **Execution Summary**: **10 tests run, 10 passed, 0 failed, 0 skipped** (Execution time: 0.001s).
   - **Process Label**: Formally documented deviation from the scratch worktree requirement due to shell whitelist policy restrictions.

### 4.2 Test Results Ledger & Headroom Margin Recomputations

The following table records the execution results for all 10 tests, detailing the exact tracked constants, recomputed byte margins, and what each test strictly asserts:

| Test Case Name | Tracked Constants & Exact Arithmetic | What Passing Test Strictly Asserts | Result | Time |
|---|---|---|:---:|---:|
| `test_addition_agent_isolation` | `AdditionAgent` start: `0x006CE000`; shifted core end: `0x003C89B3`.<br>Distance: `0x006CE000 - 0x003C89B3 - 1 = 3,167,820 B` (≈3.021 MiB). | Asserts distance exceeds $3 \times 1024 \times 1024 = 3,145,728\text{ B}$ (3 MiB). | **PASS** | <0.001s |
| `test_adversarial_overlap_detection` | Injects synthetic rogue span `0x005F0000..0x00610000` overlapping Pool 0. | Asserts that `check_disjoint()` flags synthetic collision. | **PASS** | <0.001s |
| `test_canonical_known_regions_are_strictly_disjoint` | Checks intervals for 11 entries in `CANONICAL_REGIONS`. | Asserts zero overlapping intervals among the mock array entries. | **PASS** | <0.001s |
| `test_contiguous_low_ram_partitioning` | Compares end/start boundaries: `R-01.end+1 == R-02.start`, `R-02.end+1 == R-03.start`, `R-03.end+1 == R-04.start`, `R-04.end+1 == R-05.start`. | Asserts contiguity among mock intervals. Does NOT prove hardware memory contiguity. | **PASS** | <0.001s |
| `test_dryos_heap_headroom_512k_shift` | Shifted heap base `r4 = 0x003C89B4` (3,967,412 B); limit `0x006CE000` (7,135,232 B); minimum threshold `0x000B1FEC` (729,068 B).<br>Available Headroom: `7,135,232 - 3,967,412 = 3,167,820 B` (`0x0030564C`).<br>Exact Margin: `3,167,820 - 729,068 = 2,438,752 B` (`0x00253660`, ≈ **2.326 MiB**). | Asserts `passed == True`, `headroom == 3,167,820`, `margin == 2,438,752 B`, and `margin > 3 * 729,068 B` (2,187,204 B).<br>*Note*: Does NOT assert `>2.43 MiB` (2,438,752 B is 2.326 MiB, not >2.43 MiB). | **PASS** | <0.001s |
| `test_dryos_heap_headroom_critical_limit` | Max allowable `r4 = 0x006CE000 - 0x000B1FEC = 0x0061C014`. | Asserts `verify_headroom(0x0061C014)` has `margin == 0`, and `0x0061C015` returns `passed == False`, `margin == -1`. | **PASS** | <0.001s |
| `test_dryos_heap_headroom_stock` | Stock heap base `r4 = 0x003489B4` (3,443,124 B); limit `0x006CE000` (7,135,232 B); minimum threshold `0x000B1FEC` (729,068 B).<br>Available Headroom: `7,135,232 - 3,443,124 = 3,692,108 B` (`0x0038564C`).<br>Exact Margin: `3,692,108 - 729,068 = 2,963,040 B` (`0x002D3660`, ≈ **2.826 MiB**). | Asserts `passed == True`, `headroom == 3,692,108`, and `margin == 2,963,040 B`.<br>*Note*: Does NOT assert `>2.96 MiB` (2,963,040 B is 2.826 MiB, not >2.96 MiB). | **PASS** | <0.001s |
| `test_historical_high_dram_cannot_be_verified` | Inspects mock `MemoryRegion` instantiated with `0x00C80000..0x00DFFFFF`. | Asserts mock region classification equals `HISTORICAL_DESIGN_CANDIDATE`. | **PASS** | <0.001s |
| `test_omar_secondary_core_isolation` | OMAR start: `0x00700000`; shifted core end: `0x003C89B3`.<br>Distance: `0x00700000 - 0x003C89B3 - 1 = 3,372,620 B` (≈3.216 MiB). | Asserts distance exceeds $3.2 \times 1024 \times 1024 = 3,355,443\text{ B}$ (3.2 MiB). | **PASS** | <0.001s |
| `test_unknown_gaps_are_not_treated_as_empty` | Inspects synthetic `gap_mid` (`0x00760001..0x00C7FFFF`) and `gap_high` (`0x00E00000..0x010E0FFF`). | Asserts both synthetic regions are labeled `UNKNOWN`. | **PASS** | <0.001s |
| **Total Suite Metrics** | **Deterministic unit testing of PR #23 logic** | **10 executed, 10 PASS, 0 FAIL, 0 ERR** | **0.001s** |

### 4.3 Test Rigor & Epistemic Limitations
While all 10 tests pass, the passing status must not be interpreted as proving hardware safety:
1. `CANONICAL_REGIONS` hardcodes the classification `"VERIFIED_IN_EXISTING_DOCS"` for regions whose primary sources are untracked local documents (`CHDK_PORT1B`) or unverified historical notes.
2. `test_contiguous_low_ram_partitioning` enforces that `R-01` (`0x00000000..0x00007FFF`), `R-02` (`0x00008000..0x0003F4F3`), and `R-03` (`0x0003F4F4..0x003489B3`) form an exact, contiguous block. This assumes what has not been proven: that GM1.10C hardware has contiguous RAM from `0x00000000` to `0x0003F4F4` without hardware holes, MPU faults, or remapped memory.
3. `test_historical_high_dram_cannot_be_verified` only checks a locally instantiated mock `MemoryRegion` string, which does not validate any repository data or prevent promotion in documentation.

---

## 5. Synthesis & Final Recommendation

### Formal Recommendation: **`needs-changes`**

Draft PR #23 contains valuable architectural analysis regarding the hazards of Ranma's GM1.10E high-DRAM placement and provides correct mathematical modeling of DryOS heap headroom. However, it cannot be merged in its current form due to extensive citations to untracked local files, over-promotion of unverified historical notes to verified status, conflation of bounds with subsystem ownership, inaccurate sensor RAW frame arithmetic, inaccurate line numbers, unsupported address range expansions, and unbacked categorical safety assertions.

### Required Remediation Items for PR Author
1. **Purge Untracked Citations**:
   - Replace or contextualize all citations to `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B`, `docs/RANMA_SOURCE_ARCHAEOLOGY.md`, `g3x_110e.patch`, `platform/g3x/notes.txt`, and `platform/g3x/makefile.inc`.
   - If an engineering assumption relies on prototype source code, cite tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c` or tracked historical comparisons in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`.
2. **Reclassify Over-Promoted Regions & Qualify Categorical Safety Claims**:
   - Reserve `STATIC_VERIFIED` strictly for the byte copy bounds of Region `R-16a` (ATCM relocated span), which is verified by tracked GM1.10C ROM evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`.
   - Separate bounds from ownership and bus mastering across all regions:
     - Mark R-16 scheduler ownership as `INFERRED` (per `PORT11A:26`);
     - Mark R-16 zero-wait-state performance claims as `UNKNOWN / UNVERIFIED HARDWARE HEURISTIC`;
     - Mark R-10 CPU-1 / IPC DMA attribution as `INFERRED / UNKNOWN` (not documented on GM1.10C);
     - Reclassify Regions `R-01`, `R-02`, `R-03`, `R-05`, `R-06`, `R-07`, `R-08`, `R-09`, `R-14`, and `R-17` to `INFERRED (Historical / Prototype Model)` or `HISTORICAL_CANDIDATE`, explicitly noting that their underlying ROM literals remain uninspected under authorized Phase 0 scopes.
   - Qualify categorical assertions:
     - Replace §1 "proven safe" assertions with `INFERRED (Design Candidate)`;
     - Replace §3 "allocator exclusion proof" with `INFERRED (Design Model)` noting that primary GM1.10C allocator disassembly is uninspected;
     - Replace §4 "zero collision risk" with `INFERRED (Design Margin Estimate)` noting unverified IPC bounds;
     - Reclassify §4 claim of capture DMA isolation from heap to `UNKNOWN / UNVERIFIED HEURISTIC`.
3. **Correct Sensor RAW Frame Size Arithmetic & State Epistemic Boundaries**:
   - In §1 Key Finding 2, §2 R-15, and §4 Decision Memo, correct the raw frame size calculation:
     - State explicitly that $5472 \times 3648$ are the JPEG output dimensions (`chdk-port/platform/g3x/platform_camera.h:47-48`), yielding 34,933,248 bytes (~33.315 MiB).
     - Recompute uncompressed 14 bpp RAW frame size using tracked macro parameters from `chdk-port/platform/g3x/platform_camera.h:44-56`: `CAM_RAW_ROWPIX = 5632` (L44), `CAM_RAW_ROWS = 3710` (L45), `CAM_SENSOR_BITS_PER_PIXEL = 14` (L56):
       $$5632 \times 3710 \times 14 / 8 = 36,565,760\text{ bytes} \approx 34.872\text{ MiB}$$
     - State explicitly that frame-size arithmetic is strictly theoretical sensor geometry and does NOT constitute evidence of DMA buffer allocation, placement, or heap isolation.
4. **Correct Citation Line Numbers**:
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
5. **Correct Address Boundaries and Eliminate Fencepost Errors**:
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
6. **Update Test Suite & Narrative Headroom Margins**:
   - In PR #23 narrative, replace `>2.43 MiB` and `>2.96 MiB` with exact byte margins: `2,438,752 B` (≈2.326 MiB) and `2,963,040 B` (≈2.826 MiB).
   - Adjust `CANONICAL_REGIONS` classifications and boundaries in `tests/test_port12a_memory_ownership.py` to match the corrected epistemic taxonomy and fencepost corrections (`R-09` ending at `0x006EFFFF`, `R-10` ending at `0x0075FFFF`, `R-14` ending at `0x01107CFF`).
   - Refactor `test_contiguous_low_ram_partitioning` to document that contiguity between `0x0` and `0x8000` is an architectural design assumption, not a verified hardware fact.
