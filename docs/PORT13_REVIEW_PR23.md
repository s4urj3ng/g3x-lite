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
   - The mathematical model of DryOS heap headroom (`0x006CE000 - r4 >= 0x000B1FEC`) matches prototype code in `boot_prototype.c`.
2. **Evidentiary Rigor & Citation Compliance (Critical Failures)**:
   - **Citing Untracked Documents as Checkable Evidence**: PR #23 extensively cites local, untracked files that do not exist on `origin/main` or in git history, specifically: `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B:26`, `CHDK_PORT1B:32`, `CHDK_PORT1B:47`, `CHDK_PORT1B:92`, and `docs/RANMA_SOURCE_ARCHAEOLOGY.md:46` (the latter exists only on an unmerged research branch `origin/research/g9-ranma-source-archaeology`).
   - **Over-Promotion to `VERIFIED_IN_EXISTING_DOCS`**: Out of 17 memory regions cataloged, 9 regions are labeled `VERIFIED_IN_EXISTING_DOCS`. However, only **one single region (R-16: ATCM relocated span)** is backed by tracked primary GM1.10C ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`). The remaining 8 regions rely on untracked notes or secondary tables in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, where line 72 explicitly notes: *"No ROM was read, and every C value is only as good as the existing document it comes from."*
   - **Inaccurate Line Citations & Transcriptions**: Citations to `PORT5B:78` do not contain `MEMBASEADDR=0x8000` (which is at line 101, referencing Ranma's GM1.10E `entry.S`) or BSS zeroing loops; citation to `PORT5B:48` for DMA address `0x43DBFCA0` references a line-count row for `notes.txt`.
   - **Unsupported Span Expansions and Off-by-One Boundaries**:
     - Region `R-09` (`AdditionAgent`): Declared as `0x006CE000..0x006FFFFF` (196 KiB / 200 KiB). Tracked documentation confirms `AdditionAgent` reads up to `0x22000` bytes (`0x006CE000..0x006F0000`, 136 KiB). Expanding this region to `0x006FFFFF` is an unverified inference.
     - Region `R-10` (`OMAR`): Upper bound is given as `0x00760000` (384 KiB + 1 byte), whereas historical note `PORT5B:116` records `0x00700000..0x0075FFFF` (`0x60000` = exactly 384 KiB).
3. **Test Suite Status**:
   - The PR's test suite `tests/test_port12a_memory_ownership.py` was executed in a scratch environment and passed completely (**10/10 PASS**, 0.001s).
   - However, the tests hardcode `VERIFIED_IN_EXISTING_DOCS` strings and assert strict contiguous partitioning across unverified address boundaries (`R-01 -> R-02 -> R-03 -> R-04 -> R-05`), creating circular validation of unverified assumptions.

---

## 2. Per-Claim Evaluation Table

The following table evaluates every claim about GM1.10C memory ownership, address range, size, owner, and classification in PR #23 against tracked repository evidence on `origin/main`.

| Claim ID | Region / Subject | Address Range & Size | PR Claimed Classification | Cited Source in PR #23 | Tracked on `origin/main`? | Reviewer Verdict | Reviewer Finding & Flag Notes |
|---|---|---|:---:|---|:---:|:---:|---|
| **CLM-01 (R-01)** | Low Vector & Hardware Scratch | `0x00000000..0x00007FFF` (32 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78 (MEMBASEADDR=0x8000)` | Partial (`PORT5B` tracked; line 78 wrong; `MEMBASEADDR` is L101) | **`INFERRED / MISLABELED`** | **FLAGGED (Historical / Inaccurate Citation)**. Line 78 in `PORT5B` describes Low-RAM data copy source, not `MEMBASEADDR`. `MEMBASEADDR=0x8000` appears at L101 as Ranma's loader stack setup in GM1.10E `entry.S`. Vector layout in `0x0..0x7FFF` on GM1.10C is inferred, not ROM-verified. |
| **CLM-02 (R-02)** | Low-RAM Data Section | `0x00008000..0x0003F4F3` (~221 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCE91058 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked local file `CHDK_PORT1B:26`. `PORT5B:78` cites `C:134` (prototype comment), with caveat at L72 that no ROM was read. Copy source `0xFCE91058` is outside approved ROM scopes. |
| **CLM-03 (R-03)** | Canon Firmware BSS | `0x0003F4F4..0x003489B3` (~3.036 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Zeroed at boot 0xFC020070..0xFC020078 (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Inaccurate Address)**. Address range `0xFC020070..0xFC020078` does not exist in any tracked file in the repo. L78 of `PORT5B` has no BSS loop. Cites untracked `CHDK_PORT1B:26`. BSS end `0x003489B4` is tracked in prototype, but ROM loop is uninspected. |
| **CLM-04 (R-04)** | Low-Heap Prototype Target | `0x003489B4..0x003C89B3` (512 KiB) | `INFERRED (Design Candidate)` | `Linker script & docs/CHDK_PORT1B_HEAP_PROOF.md:92` | No (both untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification `INFERRED` is acceptable, but citations ("Linker script" and `CHDK_PORT1B_HEAP_PROOF.md`) do not exist anywhere in the tracked repository. |
| **CLM-05 (R-05)** | DryOS Main Heap Pool 0 | `0x003C89B4..0x00600013` (~2.216 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474 (0x00600014), CHDK_PORT1B:47` | Partial (`0x00600014` in `boot_prototype.c`; literal `0xFC05B474` and `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. `CHDK_PORT1B:47` is untracked. Literal address `0xFC05B474` is in zero tracked files and uninspected in ROM. Sub-pool limit `0x00600014` is in `boot_prototype.c` and `PORT5B:125` (where it is explicitly marked `INFERRED`). |
| **CLM-06 (R-06)** | DryOS Sub-pool & Kernel Descriptors | `0x00600014..0x0060DFFF` (56 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B474, CHDK_PORT1B:47` | No | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:47` and uninspected literal `0xFC05B474`. `PORT5B:125` classifies descriptor parameters as `INFERRED`. |
| **CLM-07 (R-07)** | DryOS Heap Upper Chunk Block | `0x0060E000..0x006CDFFF` (768 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B470, chunk size 0x000C0000, CHDK_PORT1B:47` | Partial (`0x0060E000` in `PORT5B:125`; literal `0xFC05B470` & `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:47`. Literal `0xFC05B470` is not in tracked files. `PORT5B:125` marks chunk semantics as `INFERRED`. |
| **CLM-08 (R-08)** | DryOS System Limit & Headroom Assert | `0x006CE000` (Anchor) | `VERIFIED_IN_EXISTING_DOCS` | `Literal 0xFC05B454 (0x006CE000), CHDK_PORT1B:32` | Partial (`0x006CE000` in `PROJECT_STATE.md`; literal `0xFC05B454` & `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:32`. Literal address `0xFC05B454` is not in tracked files. The limit `0x006CE000` is documented in `PROJECT_STATE.md:161`, but derives from untracked early traces. |
| **CLM-09 (R-09)** | AdditionAgent Conflict Zone | `0x006CE000..0x006FFFFF` (196 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `0xFC55888C..0xFC5588C0 (docs/RANMA_SOURCE_ARCHAEOLOGY.md:46)` | No (`docs/RANMA_SOURCE_ARCHAEOLOGY.md` is on unmerged branch) | **`INFERRED / UNTRACKED_CITATION / CONTRADICTED_BOUNDS`** | **FLAGGED (Untracked Citation / Unsupported Span Extension)**. Cites unmerged branch artifact `docs/RANMA_SOURCE_ARCHAEOLOGY.md`. Tracked docs (`HANDOFF.md`, `PROJECT_STATE.md`) specify `AdditionAgent` reads up to `0x22000` bytes (`0x006CE000..0x006F0000`, 136 KiB). Expanding to `0x006FFFFF` is an arbitrary, unverified inference. |
| **CLM-10 (R-10)** | OMAR Secondary Core Staging RAM | `0x00700000..0x00760000` (384 KiB) | `HISTORICAL_CANDIDATE` | `Ranma platform/g3x/notes.txt:45–46, PORT5B` | Partial (`PORT5B` tracked; `notes.txt` untracked) | **`HISTORICAL_CANDIDATE / OFF_BY_ONE`** | **FLAGGED (Historical / Untracked Citation / Fencepost Error)**. Cites untracked `notes.txt`. `PORT5B:116` records Ranma GM1.10E range as `0x00700000..0x0075FFFF` (`0x60000` = 384 KiB) and marks it `Not documented` on GM1.10C. Upper bound `0x00760000` adds 1 byte (`0x60001` = 393,217 B). |
| **CLM-11 (R-11)** | Mid DRAM Uninspected Gap | `0x00760001..0x00C7FFFF` (~5.12 MiB) | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly classifies uninspected DRAM as `UNKNOWN` and rejects treating it as empty memory. |
| **CLM-12 (R-12)** | Ranma High-DRAM CHDK Placement | `0x00C80000..0x00DFFFFF` (1.5 MiB) | `HISTORICAL_DESIGN_CANDIDATE` | `platform/g3x/makefile.inc:29–37, g3x_110e.patch:580` | No (`makefile.inc` & `patch` untracked) | **`HISTORICAL_CANDIDATE / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citations)**. Classification as historical candidate unproven on GM1.10C is sound, but citations to `platform/g3x/makefile.inc` and `g3x_110e.patch` are to untracked local files. |
| **CLM-13 (R-13)** | High DRAM Uninspected Gap | `0x00E00000..0x010E0FFF` (~2.88 MiB) | `UNKNOWN` | `No tracked GM1.10C evidence` | Yes | **`UNKNOWN`** | **VERIFIED CLASSIFICATION**. Correctly flags uninspected DRAM gap as `UNKNOWN`. |
| **CLM-14 (R-14)** | Firmware Executable RAM Mirror | `0x010E1000..0x01107D00` (155.25 KiB) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEC854C (PORT5B:78, CHDK_PORT1B:26)` | Partial (`PORT5B` tracked; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Inaccurate Line)**. Cites untracked `CHDK_PORT1B:26`. In `PORT5B`, source `0xFCEC854C` is at L76 and range at L79 (citing prototype `C:107`, `C:108-147`). Uninspected in GM1.10C ROM. |
| **CLM-15 (R-15)** | Upper DRAM & DMA Capture Buffers | `0x01107D01..0x3FFFFFFF` (~1006 MiB) | `UNKNOWN` | `Dynamic heap / peripheral DMA (0x43DBFCA0, PORT5B:48)` | Partial (`PORT5B` tracked; L48 irrelevant; `0x43DBFCA0` in `HANDOFF.md`) | **`UNKNOWN / INACCURATE_CITATION`** | **FLAGGED (Inaccurate Line Citation / Inferred Bound)**. `PORT5B:48` is a table line count for `notes.txt`. `0x43DBFCA0` is in `HANDOFF.md` from legacy notes. Upper bound `0x3FFFFFFF` is inferred without physical DRAM size proof (noted in E-04). Classification `UNKNOWN` is correct. |
| **CLM-16 (R-16)** | Cortex-R4 ATCM Relocated Span | `0xBFE10800..0xBFE1741B` (27,676 B) | `VERIFIED_IN_EXISTING_DOCS` | `Copied from ROM 0xFCEEF24C..0xFCEF5E67 (PORT11A:20, PR #19)` | Yes (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20` tracked) | **`STATIC_VERIFIED`** | **VERIFIED**. Accurately cites tracked `PORT11A:20` and approved ROM slice `PORT11A-S1A` (`0xFC020040..0xFC0200CF`). Proves copy of 6,919 words (27,676 B) to `0xBFE10800..0xBFE1741B`. Only genuinely verified region. |
| **CLM-17 (R-17)** | Uncached Peripheral Memory Mappings | `0x40000000..0x5FFFFFFF` (512 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `0x42281000, 0x42283000, 0x406CE000 (CHDK_PORT1B:47)` | Partial (`CAM_UNCACHED_BIT 0x40000000` tracked in `platform_camera.h`; `CHDK_PORT1B` untracked) | **`INFERRED / UNTRACKED_CITATION`** | **FLAGGED (Untracked Citation / Mislabeled)**. Cites untracked `CHDK_PORT1B:47`. `PORT5B:120` marks `0x40000000` as `HISTORICALLY REPORTED` (`P:699, 711`). Range `0x40000000..0x5FFFFFFF` (512 MiB) is an architectural inference. |
| **CLM-18 (AR-1)** | DryOS Stock Headroom Check | `0x006CE000 - 0x003489B4 = 3,692,108 B >= 729,068 B` (Margin: 2.82 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B:32` | No (untracked `CHDK_PORT1B`) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic formula matches prototype model in `boot_prototype.c` and `PROJECT_STATE.md`, but cites untracked `CHDK_PORT1B`. Kernel init routine `0xFC05B3C8` is uninspected in GM1.10C ROM. |
| **CLM-19 (AR-2)** | DryOS Shifted 512 KiB Headroom Check | `0x006CE000 - 0x003C89B4 = 3,167,820 B >= 729,068 B` (Margin: 2.32 MiB) | `VERIFIED_IN_EXISTING_DOCS` | `CHDK_PORT1B_HEAP_PROOF.md` | No (untracked file) | **`INFERRED (Formula Consistent)`** | **FLAGGED (Untracked Citation)**. Arithmetic is mathematically sound for shifted heap base, but cites untracked document. |
| **CLM-20 (AR-3)** | Low-Heap Isolation from AdditionAgent | `0x006CE000 - 0x003C89B4 = 3.02 MiB > 3 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming `AdditionAgent` base is `0x006CE000` and heap shift is `0x003C89B4`. |
| **CLM-21 (AR-4)** | Low-Heap Isolation from OMAR | `0x00700000 - 0x003C89B4 = 3.21 MiB > 3.2 MiB` | `VERIFIED_IN_EXISTING_DOCS` | Arithmetic deduction | N/A | **`INFERRED`** | Distance calculation is mathematically correct assuming OMAR base is `0x00700000`. |
| **CLM-22 (AR-5)** | Ranma High-DRAM Sensor RAW Hazard | Uncompressed 20.2 MP raw frame: $5472 \times 3648 \times 14\text{ bits} \approx 34.9\text{ MiB}$ in High DRAM | `UNKNOWN` (Hazard Analysis) | Sensor specification deduction | N/A | **`PLAUSIBLE / UNKNOWN`** | Sensor arithmetic is sound ($5472 \times 3648 \times 14 / 8 = 34,924,032\text{ B} \approx 34.9\text{ MiB}$). Circular capture buffers in upper DRAM present genuine collision risk. |

---

## 3. Explicit Inventory of Flagged Claims

Per the acceptance criteria, the following subsections catalog every claim that violates evidentiary standards:

### 3.1 Claims Relying on Historical Firmware (GM1.00C / GM1.10E / `g3x_110e.patch`) as GM1.10C Proof
1. **Claim CLM-01 (Region R-01: `0x00000000..0x00007FFF`)**:
   - Relies on `MEMBASEADDR=0x8000`, which originates from Ranma's `entry.S` (`P:28–36` in `g3x_110e.patch` for GM1.10E, documented in `PORT5B:101`). Treated as proving a 32 KiB "Low Vector & Hardware Scratch" allocation on GM1.10C.
2. **Claim CLM-10 (Region R-10: `0x00700000..0x00760000`)**:
   - Derives from Ranma's GM1.10E comment "OMAR ram area" (`P:693–694` in `g3x_110e.patch`, recorded in `PORT5B:116`). `PORT5B` explicitly states that this region is **`Not documented`** in GM1.10C and is strictly **`HISTORICALLY REPORTED`**.
3. **Claim CLM-12 (Region R-12: `0x00C80000..0x00DFFFFF`)**:
   - Derives from Ranma's GM1.10E `MEMISOSTART = 0x00C80000` (`g3x_110e.patch:580`). While PR #23 correctly warns that this is unproven on GM1.10C, it cites untracked historical patch lines as evidence sources.
4. **Claim CLM-17 (Region R-17: `0x40000000..0x5FFFFFFF`)**:
   - Derives from Ranma's GM1.10E patch definitions (`P:699, 711`), classified in `PORT5B:120` as **`HISTORICALLY REPORTED`**.

### 3.2 Claims Citing Untracked / Local-Only L1/L2 Sources as Checkable Evidence
1. **`docs/PORT1B_HEAP_PROOF.md` / `CHDK_PORT1B_HEAP_PROOF.md`**:
   - Cited in Section 2 introductory text, Section 4 Decision Memo, and CLM-04 (R-04: `docs/CHDK_PORT1B_HEAP_PROOF.md:92`).
   - **Status**: **UNTRACKED**. This file was a local document from 2026-10-24 that was never committed to git.
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

### 3.3 Claims Inferring Addresses, Offsets, Hardware Bounds, or CPU Mode Without Evidence
1. **Claim CLM-03 (BSS Zeroing Bounds `0xFC020070..0xFC020078`)**:
   - Address literal `0xFC020070` does not exist in any tracked file in the repository. The instructions at this address are uninspected in GM1.10C ROM.
2. **Claims CLM-05, CLM-06, CLM-07, CLM-08 (ROM Literals `0xFC05B474`, `0xFC05B470`, `0xFC05B454`, `0xFC05B450`)**:
   - None of these literal addresses exist in tracked files or approved ROM inspection scopes. The ROM range `0xFC05B450..0xFC05B480` has never been inspected under owner authorization.
3. **Claim CLM-09 (R-09: `AdditionAgent` Upper Bound `0x006FFFFF`)**:
   - Arbitrarily expands the `AdditionAgent` zone from `0x006CE000..0x006F0000` (`0x22000` bytes, documented in `HANDOFF.md` and `PROJECT_STATE.md`) up to `0x006FFFFF` (200 KiB) to make it contiguous with OMAR at `0x00700000`.
4. **Claim CLM-10 (R-10: OMAR Upper Bound `0x00760000`)**:
   - Introduces an off-by-one fencepost error. Ranma's note in `PORT5B:116` gives `0x00700000..0x0075FFFF` (`0x60000` = 384 KiB). `0x00760000` is 384 KiB + 1 byte.
5. **Claim CLM-14 (R-14: ROM Copy Source `0xFCEC854C`)**:
   - Derived from unverified prototype comment `C:107` in `PORT5B:76`. Has never been inspected in GM1.10C ROM.
6. **Claim CLM-15 (R-15: Upper DRAM Limit `0x3FFFFFFF`)**:
   - Infers a 1 GiB physical DRAM boundary without register verification or memory controller inspection.
7. **Claim CLM-17 (R-17: Uncached Aperture Span `0x40000000..0x5FFFFFFF`)**:
   - Infers a 512 MiB uncached mapping range without MPU or bus controller evidence.

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

Draft PR #23 contains valuable architectural analysis regarding the hazards of Ranma's GM1.10E high-DRAM placement and provides correct mathematical modeling of DryOS heap headroom. However, it cannot be merged in its current form due to extensive citations to untracked local files, over-promotion of unverified historical notes to verified status, inaccurate line numbers, and unsupported address range expansions.

### Required Remediation Items for PR Author
1. **Purge Untracked Citations**:
   - Replace or contextualize all citations to `docs/PORT1B_HEAP_PROOF.md`, `CHDK_PORT1B`, `docs/RANMA_SOURCE_ARCHAEOLOGY.md`, `g3x_110e.patch`, `platform/g3x/notes.txt`, and `platform/g3x/makefile.inc`.
   - If an engineering assumption relies on prototype source code, cite tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c` or tracked historical comparisons in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`.
2. **Reclassify Over-Promoted Regions**:
   - Reserve `STATIC_VERIFIED` strictly for Region `R-16` (ATCM relocated span), which is verified by tracked GM1.10C ROM evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`.
   - Reclassify Regions `R-01`, `R-02`, `R-03`, `R-05`, `R-06`, `R-07`, `R-08`, `R-09`, `R-14`, and `R-17` to `INFERRED (Historical / Prototype Model)` or `HISTORICAL_CANDIDATE`, explicitly noting that their underlying ROM literals remain uninspected under authorized Phase 0 scopes.
3. **Correct Citation Line Numbers**:
   - In `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, update references to point to actual lines (e.g., L101 for `MEMBASEADDR`, L76 for RAM-code source, L79 for destination ranges, L116 for OMAR, L120 for `0x40000000`).
4. **Correct Address Boundaries**:
   - `R-09` (`AdditionAgent`): Restore documented range `0x006CE000..0x006F0000` (`0x22000` bytes / 136 KiB), and mark the span `0x006F0001..0x006FFFFF` as `UNKNOWN` gap rather than part of `AdditionAgent`.
   - `R-10` (`OMAR`): Correct upper bound to `0x0075FFFF` (`0x60000` = exactly 384 KiB) to fix the off-by-one fencepost error.
5. **Update Test Suite**:
   - Adjust `CANONICAL_REGIONS` classifications in `tests/test_port12a_memory_ownership.py` to match the corrected epistemic taxonomy.
   - Refactor `test_contiguous_low_ram_partitioning` to document that contiguity between `0x0` and `0x8000` is an architectural design assumption, not a verified hardware fact.
