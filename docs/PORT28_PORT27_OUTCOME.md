# PORT-28 T1: Audit of PORT-27-RESIDENT-HEARTBEAT Outcome

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-28 T1 (`p28-t1-port27-outcome`)
- **Audit Subject**: PORT-27-RESIDENT-HEARTBEAT (Pull Request #111, merge head `5a0b74b46c81138c25e50be7cc0c5c09faea8607`) `[VERIFIED: git log 5a0b74b46c]`
- **Primary Sources**:
  - `docs/PORT27_RESIDENT_EVIDENCE.md` (PORT-27 T1 Dossier) `[VERIFIED]`
  - `docs/PORT27_RESIDENT_CANDIDATE.md` (PORT-27 T2 Candidate Record) `[VERIFIED]`
  - `tests/test_port27_resident.py` (PORT-27 T3 Test Suite) `[VERIFIED]`
  - `docs/PORT27_OWNER_TRIAL_PLAN.md` & `docs/PORT27_RECOVERY_PLAN.md` (PORT-27 T4 Plans) `[VERIFIED]`
  - `docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json` (PORT-27 Evidence Manifest) `[VERIFIED]`
  - `docs/PORT23_LED_BREADCRUMBS.md`, `docs/PORT24_POWERON_FIX.md`, `docs/PORT24_BREADCRUMB_LADDER.md`, `docs/PORT25_LADDER_FIX_CANDIDATE.md`, `docs/PORT26_CODE43_RECORD.md` `[VERIFIED]`
  - Existing local build scripts: `tools/build_candidate_port25_ladder_fix.py`, `tools/build_candidate_port2a.py` `[VERIFIED]`
- **Policy Compliance**: Phase 0 read-only regarding firmware and camera hardware; no new ROM ranges read; `firmware/dumps/` not accessed; no binaries or build outputs committed `[VERIFIED: docs/SAFETY.md:3-8; AGENTS.md:18-24; docs/RESEARCH_PLAN.md:3-19]`.

---

## 1. Executive Summary & Epistemic Standards

This document establishes the official outcome audit of **PORT-27-RESIDENT-HEARTBEAT** (PR #111, merge head `5a0b74b46c`) for milestone **PORT-28**.

### Epistemic Classifications
Every finding and claim in this document is labeled strictly according to repository epistemic standards:
- **`[VERIFIED]`**: Directly corroborated by static ROM disassembly opcodes/literals in `firmware/dumps/GM1.10C/PRIMARY.BIN` within approved slices, concrete tracked repository files and line citations, verified local build executions, or documented physical hardware trial results.
- **`[INFERRED]`**: Logically deduced from verified static facts, mathematical arithmetic, or architectural DryOS conventions documented in established CHDK platform ports.
- **`[UNKNOWN]`**: Unobserved, undetermined, or runtime-dependent behaviors requiring future authorized ROM slices or empirical hardware measurement.

---

## 2. PORT-27 T2 Outcome: Candidate vs. UNKNOWN Record

### 2.1 Verdict & Record Type
Task **p27-t2** produced an **UNKNOWN record** (a strict **NO-GO record**). It did **NOT** produce a `G3X_RESIDENT=1` candidate binary, and made **zero code changes** to the repository `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6, 28-31; tests/test_port27_resident.py:141-162, 294-299; docs/PROJECT_STATE.md:859; docs/HANDOFF.md:2333]`.

### 2.2 Exact File and Line Citations
1. **`docs/PORT27_RESIDENT_CANDIDATE.md:6`**:
   > `- **Status / Verdict**: **NO-GO Record** (No candidate produced; zero code modified)` `[VERIFIED]`
2. **`docs/PORT27_RESIDENT_CANDIDATE.md:28-31`** (§1.2 Policy Compliance & Outcome):
   > `1. **No Candidate Produced**: No candidate binary, no DISKBOOT image, and no build script (`tools/build_candidate_port27_resident.py`) were created.`  
   > `2. **Zero Code Changes**: No modifications were made to `chdk-port/platform/g3x/sub/110c/`, `tools/`, or any other source directory.`  
   > `3. **Build Invariance Preserved**: The default build and all existing opt-in builds (`--ladder`, `--poweron-fix`, `--combined`) remain 100% bit-for-bit identical to their prior verified baselines.`  
   > `4. **Exact UNKNOWN List Recorded**: This document records the comprehensive, exact UNKNOWN list across Items (a), (b), and (d) with verified entry points, unknown function extents, and precise policy reachability explanations (including the 22,196-byte unspent budget for reachable targets and the exact policy boundaries for out-of-scope targets).` `[VERIFIED]`
3. **`docs/PORT27_RESIDENT_EVIDENCE.md:576-579`** (§7 Verdict for PORT-27 T2):
   > `**Verdict for PORT-27 T2**: **NO-GO**`  
   > `Under the project task policy, a **GO** verdict requires both Item (a) and Item (b) to be certified as **VERIFIED**. Furthermore, reviewer guidance establishes a strict evaluation standard:`  
   > `*"GO is allowed only if T2 can create its task by copying the VERIFIED call-site pattern exactly, changing only values whose role is VERIFIED. State the exact arguments T2 would pass and give each one a label. If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*` `[VERIFIED]`
4. **`tests/test_port27_resident.py:141-162, 294-299, 400-441`**:
   The automated test suite enforces that `t2_produced_candidate()` evaluates to `False` (lines 141-162, 294-299), asserts that `docs/PORT27_RESIDENT_CANDIDATE.md` contains the NO-GO verdict (lines 301-309), asserts that no candidate builder `tools/build_candidate_port27_resident.py` exists (lines 435-441), and asserts that no `G3X_RESIDENT` macro or code path exists in `chdk-port/` (lines 400-418) or `tools/` (lines 420-433) `[VERIFIED]`.
5. **`docs/PROJECT_STATE.md:859`** (§PORT-27 Milestone Close-Out):
   > `- **Milestone Outcome & T2 Verdict**: **NO-GO Record** (No candidate produced; zero code modified) \`[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6-32; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]\`:` `[VERIFIED]`
6. **`docs/HANDOFF.md:2333`** (§PORT-27 Milestone Close-Out):
   > `- **Milestone Outcome & T2 Verdict**: **NO-GO Record** (No candidate produced; zero code modified) \`[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6-32; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]\`:` `[VERIFIED]`

### 2.3 Rationale for NO-GO Verdict
Under the reviewer directive in `docs/PORT27_RESIDENT_EVIDENCE.md:578-579`, a GO verdict required both Item (a) and Item (b) to be certified as `VERIFIED`.
- **Item (a) (Heap Start & Relocated Core Survival)**: Achieved `enough to build` status `[VERIFIED]`. The patch point at `0xFC05B3CA` and heap pool 1 exclusion up to `new_sa = 0x00368680` are `[VERIFIED: PORT27-ROM-HEAP-SETUP; boot_prototype.c:24, 177-178, 212-215]`. However, ATCM IRQ disable/restore routines behaviour is `[INFERRED/UNKNOWN: not read; outside PORT-27 policy]`, heap alignment requirement is `[UNKNOWN]`, and runtime survival against non-heap RAM users (DMA/MMIO) is `[UNKNOWN]`.
- **Item (b) (Task Creation Entry & Calling Convention)**: **Failed strict verification** (`UNKNOWN: exact ranges still needed`) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:589-601]`. Although the task creation veneer `sub_fc31bbc4` at `0xFC31BBC4` is `[VERIFIED]` and the call-site literal values at `0xFC05B984..0xFC05B990` are `[VERIFIED]`, parameter semantic roles (`r0` name, `r1` priority, `r2` stack size, `sp[0]` user context) remain `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`. Crucially, `CreateTask` delegates execution to internal callees located in unread ATCM/high-ROM slices: internal allocator `0xBFE10B88` at ROM `0xFCEEF5D4` (`UNKNOWN`), activation helper `0xBFE10D14` at ROM `0xFCEEF760` (`UNKNOWN`), and assertion handler `0xBFE13E78` at ROM `0xFCEF28C4` (`UNKNOWN`). Because a candidate resident heartbeat task depends on `r2 = 0` successfully assigning an adequate stack via `0xBFE10B88`, T2 depended on unverified prerequisites, compelling the strict NO-GO verdict `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:594-595]`.

---

## 3. Candidate Audit, Evidence Status & Flag-Off Hash Invariance

### 3.1 Candidate Status & Zero Code Modifications
- **G3X_RESIDENT=1 Candidate**: Does **not** exist `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-31; tests/test_port27_resident.py:400-441]`.
- **Source Invariance**: Zero files under `chdk-port/platform/g3x/` or `tools/` were modified in PORT-27 `[VERIFIED: git diff a1ba9a8..5a0b74b -- chdk-port/ tools/ shows 0 changes]`.
- **Build Script**: No resident candidate builder script (`tools/build_candidate_port27_resident.py`) was created `[VERIFIED: tests/test_port27_resident.py:435-441]`.

### 3.2 Evidence Status for Items (a), (b), and (c) in `docs/PORT27_RESIDENT_EVIDENCE.md`

| Item | Prerequisite Scope | Technical Details & Verified Facts | Epistemic Status & Citations |
|:---:|:---|:---|:---|
| **Item (a)** | Stock heap / memory start after `sub_fc0d0126`; patch point in `sub_fc05b3c8`; relocated core survival at `0x003489B4` | - `sub_fc0d0126` instructions set no heap bounds `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:85-132; manifest PORT27-ROM-FIRMWARE-CONT]`.<br>- Stock heap setup in `sub_fc05b3c8`: literal `0x003489B4` at `[0xFC05B450]` loaded into `r4` at `0xFC05B3CA`, stored to descriptor `sp[0x08]` at `0xFC05B3FC`, subtracted from `0x00600014` at `0xFC05B402`, stored to `sp[0x0C]` at `0xFC05B404` `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:135-178; manifest PORT27-ROM-HEAP-SETUP]`.<br>- Relocated core region (`candidate_main.bin` 123,424 B, `_end = 0x00368680`) strictly excluded from stock heap pool 1 allocations by overriding `r4` with `new_sa = 0x00368680` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 177-178, 212-215; docs/PORT21_RAM_LIFETIME.md:40-41]`.<br>- ATCM IRQ disable (`0xBFE14FE7`) and restore (`0xBFE14FEB`) routines behaviour is `[INFERRED/UNKNOWN: not read; outside PORT-27 policy: docs/PORT27_RESIDENT_EVIDENCE.md:126-132, 584]`.<br>- Heap-start alignment requirement in ROM is `[UNKNOWN: docs/PORT27_RESIDENT_EVIDENCE.md:173-175, 586]`.<br>- Relocated core runtime survival against non-heap users (DMA/MMIO) is `[UNKNOWN: docs/PORT27_RESIDENT_EVIDENCE.md:218-221, 587]`. | **PARTIALLY VERIFIED** (`enough to build` for heap override, but contains `UNKNOWN` items regarding ATCM routines, alignment, and DMA/MMIO survival) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:583-588]` |
| **Item (b)** | DryOS task-creation entry (`CreateTask`) and calling convention | - Entry veneer `sub_fc31bbc4` (ARM `ldr pc, [pc, #-4]` at `0xFC31BBC4` targeting vector `0xBFE14A3D` for Thumb-2 execution at `0xBFE14A3C`) is `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:250-258; manifest PORT27-ROM-CREATETASK-VENEER]`.<br>- Call-site register setup at `0xFC05B984..0xFC05B990` (`r0=0xFC05B9A0`, `r1=25`, `r2=0`, `r3=0xFC05B8FD`, `sp[0]=0`) is `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:259-291; manifest PORT27-ROM-STARTUP-TASKS]`.<br>- Parameter semantic roles (`r0` name pointer, `r1` priority, `r2` stack size, `sp[0]` user context) are `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165; docs/PORT27_RESIDENT_EVIDENCE.md:356-384, 593]`.<br>- Internal callees in ATCM: internal allocator `0xBFE10B88` (ROM `0xFCEEF5D4`), activation helper `0xBFE10D14` (ROM `0xFCEEF760`), assertion handler `0xBFE13E78` (ROM `0xFCEF28C4`) are outside Slice S1C and remain `[UNKNOWN: docs/PORT27_RESIDENT_EVIDENCE.md:382-384, 406-417, 594, 597-599]`.<br>- `CreateTask` body decode under PORT-27 authority remains `[UNKNOWN: docs/PORT27_RESIDENT_EVIDENCE.md:592, 600]`. | **FAILS STRICT VERIFICATION** (`UNKNOWN: exact ranges still needed`) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:589-601]` |
| **Item (c)** | Hardware LED register and control values | - MMIO register: `0xD20B0884` `[VERIFIED]`.<br>- Turn ON word: `0x004D0002` `[VERIFIED]`.<br>- Turn OFF word: `0x004C0003` `[VERIFIED]`.<br>- Reused strictly from PORT-23 physical hardware trial breadcrumbs without reading new ROM bytes `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:6-7; docs/PORT20_LED_CANDIDATE.md:32, 35; docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:157; docs/PORT27_RESIDENT_EVIDENCE.md:465-485, 602-604]`. | **VERIFIED** (`enough to build`) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:602-604]` |

### 3.3 Pinned Flag-Off Baseline Checksums & Citations
The flag-off builds (where `G3X_RESIDENT` is unset or 0) are pinned to two established canonical baselines:

1. **Default Control Baseline `DISKBOOT.BIN`**:
   - **SHA-256**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED]`
   - **Byte Size**: `118,001` bytes `[VERIFIED]`
   - **Pinned Citations (file:line)**:
     - `tests/test_port27_resident.py:15, 74-77` `[VERIFIED]`
     - `docs/PORT27_RESIDENT_CANDIDATE.md:151` `[VERIFIED]`
     - `docs/PROJECT_STATE.md:848, 885` `[VERIFIED]`
     - `docs/PORT25_LADDER_FIX_CANDIDATE.md:50, 381` `[VERIFIED]`
     - `docs/PORT24_POWERON_FIX.md:7, 249, 275` `[VERIFIED]`
     - `docs/PORT20_LED_CANDIDATE.md:28, 68` `[VERIFIED]`
     - `docs/PORT19_GO_NOGO.md:31, 50` `[VERIFIED]`

2. **PORT-25 Combined Baseline `DISKBOOT.BIN`** (carrying the held-press boot method and ladder fix):
   - **SHA-256**: `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` `[VERIFIED]`
   - **Byte Size**: `124,865` bytes `[VERIFIED]`
   - **Pinned Citations (file:line)**:
     - `tests/test_port27_resident.py:19, 87-90` `[VERIFIED]`
     - `docs/PORT27_RESIDENT_CANDIDATE.md:154` `[VERIFIED]`
     - `docs/PROJECT_STATE.md:800, 853, 890` `[VERIFIED]`
     - `docs/PORT25_LADDER_FIX_CANDIDATE.md:385, 402` `[VERIFIED]`
     - `docs/PORT26_CODE43_RECORD.md:13` `[VERIFIED]`
     - `docs/PORT26_TRIAL_2026-11-02.md:21, 24` `[VERIFIED]`
     - `docs/HANDOFF.md:2263, 2327, 2364` `[VERIFIED]`

### 3.4 Local Build Reproduction & Verification Audit
All builds were executed using the repository's pinned GCC toolchain:
`toolchains/gcc-arm-none-eabi-5_4-2016q3` (`arm-none-eabi-gcc` 5.4.1 20160919) `[VERIFIED: toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc -v]`.

#### Build Commands Executed
To verify byte-identity without contaminating the workspace, outputs were directed to isolated temporary directories and deleted immediately after hashing:

1. **Default Control Baseline Build Command**:
   ```bash
   python3 tools/build_candidate_port25_ladder_fix.py --default --out-dir /tmp/test_build_default
   ```
   *(Alternative equivalent default builder: `python3 tools/build_candidate_port2a.py --out-dir /tmp/test_build_port2a`)*

2. **Combined Baseline Build Command**:
   ```bash
   python3 tools/build_candidate_port25_ladder_fix.py --combined --out-dir /tmp/test_build_combined
   ```

#### Reproduction Results Across Two Independent Local Builds

| Baseline Target | Build Run | Output `DISKBOOT.BIN` SHA-256 | Size (Bytes) | Verification vs. Pinned Hash |
|---|:---:|:---:|:---:|:---:|
| **Default Control Baseline** | Run 1 | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | 118,001 | Exact Match `[VERIFIED]` |
| **Default Control Baseline** | Run 2 | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | 118,001 | 100% Reproducible `[VERIFIED]` |
| **PORT-25 Combined Baseline** | Run 1 | `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` | 124,865 | Exact Match `[VERIFIED]` |
| **PORT-25 Combined Baseline** | Run 2 | `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` | 124,865 | 100% Reproducible `[VERIFIED]` |

**Confirmation**: Both flag-off builds match their respective pinned baseline hashes 100% bit-for-bit `[VERIFIED]`. Zero binaries or build outputs were retained or committed `[VERIFIED]`.

---

## 4. Exact UNKNOWN List & Proposed ROM Ranges for Future Milestones

In accordance with task specification item 3, because p27-t2 produced no candidate, the exact UNKNOWN list is copied here from `docs/PORT27_RESIDENT_EVIDENCE.md` (§7 table, lines 584-601), cross-referenced with `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` and `docs/PORT27_OWNER_TRIAL_PLAN.md:20-54`.

> [!IMPORTANT]
> **Proposals Only — No New ROM Ranges Read**:  
> The ROM inspection windows listed below are non-evidentiary planning proposals ($\le 4\text{ KiB}$) for authorization in a future milestone. In strict compliance with Phase 0 policy, **NO new ROM ranges have been read** and `firmware/dumps/` was not accessed during this audit `[VERIFIED]`.

### 4.1 Comprehensive UNKNOWN List and Proposed Bounded Slices

| # | Item | Component / Subsystem | Target VMA | Source ROM Entry | File Offset | Evidenced Extent | Proposed ROM Range ($\le 4\text{ KiB}$) | Proposed Slice Size | Citation-Based Justification & Policy Status |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | **(b)** | Internal Task Allocator / Initializer (`alloc_task_stack_tcb`) | `0xBFE10B88` (ATCM Thumb-2 `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:170]`) | `0xFCEEF5D4` | `0x00EEF5D4` | `UNKNOWN` (span up to 396 B in T1: `docs/PORT27_RESIDENT_EVIDENCE.md:597`) | `0xFCEEF5C0..0xFCEEF7BF` (ATCM `0xBFE10B74..0xBFE10D73`) | 512 B | Target called via `bl 0xBFE10B88` at `0xBFE14A8E` in ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:170; docs/PORT27_RESIDENT_EVIDENCE.md:382, 406-407, 597`). Mapped via PORT11A §3.1 formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE10B88} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEEF5D4}}$. **Outside PORT-27 read policy boundary**: not a branch target inside read ROM slices, and not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`). `[UNKNOWN]` |
| **2** | **(b)** | Internal Task Activation Helper (`activate_task`) | `0xBFE10D14` (ATCM Thumb-2 `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:180]`) | `0xFCEEF760` | `0x00EEF760` | `UNKNOWN` (span up to 612 B in T1: `docs/PORT27_RESIDENT_EVIDENCE.md:598`) | `0xFCEEF760..0xFCEEF9BF` (ATCM `0xBFE10D14..0xBFE10F73`) | 608 B | Target called via `bl 0xBFE10D14` at `0xBFE14AA6` in ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:180; docs/PORT27_RESIDENT_EVIDENCE.md:383, 411-412, 598`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE10D14} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEEF760}}$. **Outside PORT-27 read policy boundary**. `[UNKNOWN]` |
| **3** | **(b)** | DryOS Debug Assertion / Kernel Panic Handler (`DebugAssert`) | `0xBFE13E78` (ATCM ARM state `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176]`) | `0xFCEF28C4` | `0x00EF28C4` | `UNKNOWN` | `0xFCEF28B0..0xFCEF29AF` (ATCM `0xBFE13E64..0xBFE13F63`) | 256 B | Target called via `blx 0xBFE13E78` from `CreateTask` error branches (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176; docs/PORT27_RESIDENT_EVIDENCE.md:382, 391, 416-417, 599`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE13E78} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF28C4}}$. **Outside PORT-27 read policy boundary**. `[UNKNOWN]` |
| **4** | **(b)** | `CreateTask` Body & Calling Convention Semantics | `0xBFE14A3C..0xBFE14AAD` (ATCM Thumb-2; target vector `0xBFE14A3D`) | `0xFCEF3488..0xFCEF34F9` | `0x00EF3488..0x00EF34F9` | 114 B (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:131-133, 182; docs/PORT27_RESIDENT_EVIDENCE.md:592, 600`) | `0xFCEF3480..0xFCEF350F` (ATCM `0xBFE14A34..0xBFE14AC3`) | 144 B | Target vector `0xBFE14A3D` loaded by veneer `sub_fc31bbc4` at `0xFC31BBC4` (`docs/PORT27_RESIDENT_EVIDENCE.md:251-255`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE14A3C} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF3488}}$. The 114-byte extent is identified, but direct body decode and parameter semantics under current milestone authority remain **outside PORT-27 read policy boundary**. `[UNKNOWN]` |
| **5** | **(a)** | ATCM Interrupt Disable Destination (`DisableInterrupts_ATCM`) | `0xBFE14FE6` (ATCM Thumb-2; target vector `0xBFE14FE7` loaded at `0xFC31BEFC`) | `0xFCEF3A32` | `0x00EF3A32` | `UNKNOWN` | `0xFCEF3A20..0xFCEF3A5F` (Slice N6; ATCM `0xBFE14FD4..0xBFE15013`) | 64 B (paired with #6) | Target vector `0xBFE14FE7` loaded by ARM veneer at `0xFC31BEFC` (`docs/PORT27_RESIDENT_EVIDENCE.md:124; manifest PORT27-ROM-IRQ-DISABLE`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE14FE6} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF3A32}}$. **Outside PORT-27 read policy boundary**. `[INFERRED/UNKNOWN]` |
| **6** | **(a)** | ATCM Interrupt Restore Destination (`RestoreInterrupts_ATCM`) | `0xBFE14FEA` (ATCM Thumb-2; target vector `0xBFE14FEB` branched at `0xFC31B8CA`) | `0xFCEF3A36` | `0x00EF3A36` | `UNKNOWN` | `0xFCEF3A20..0xFCEF3A5F` (Slice N6; ATCM `0xBFE14FD4..0xBFE15013`) | 64 B (paired with #5) | Target vector `0xBFE14FEB` branched by Thumb-2 veneer at `0xFC31B8CA` (`docs/PORT27_RESIDENT_EVIDENCE.md:109-115, 125; manifest PORT27-ROM-RESTORE-IRQ-VENEER`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE14FEA} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF3A36}}$. **Outside PORT-27 read policy boundary**. `[INFERRED/UNKNOWN]` |
| **7** | **(a)** | DryOS Heap-Start Alignment Specification & Kernel Init (`sub_fc31b408`) | `0xFC31B408` (ROM ARM state) | `0xFC31B408` | `0x0031B408` | `UNKNOWN` | `0xFC31B408..0xFC31B507` (Slice N1) | 256 B | Target called via `0xFC05B448: blx 0xfc31b408` in `sub_fc05b3c8` (`docs/PORT27_RESIDENT_EVIDENCE.md:158, 170; manifest PORT27-ROM-HEAP-SETUP`). **Reachable under policy**: verified branch target in approved range, 22,196 bytes unspent budget in T1, but not read in T1. Alignment rules enforced downstream remain `[UNKNOWN]`. |
| **8** | **(a)** | Relocated Core Region Non-Heap RAM Users | Span `0x003489B4..0x00368680` (RAM) | **UNRESOLVED: no evidence-backed bounded range available** | UNRESOLVED | `RAM span 130,252 B` (`0x003489B4..0x00368680`) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:548, 587]` | **UNRESOLVED: no evidence-backed bounded range available** | UNRESOLVED | Relocated core exclusion from stock DryOS heap pool 1 allocations is `[VERIFIED: boot_prototype.c:24, 177-178, 212-215; docs/PORT21_RAM_LIFETIME.md:40-41]`. However, proving complete runtime survival against non-heap RAM users (such as hardware DMA transfers, image sensor or video codec buffers, SD card host controller DMA, or hardcoded MMIO buffers) requires whole-ROM analysis across 32 MiB (`0xFC000000..0xFDFFFFFF`), which exceeds Phase 0 single-milestone bounded inspection budgets ($\le 4\text{ KiB}$ per slice, $\le 24,576$ B total) `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:65; docs/PORT27_OWNER_TRIAL_PLAN.md:52]`. No existing citation in the PORT-23..PORT-27 documentation or committed manifests under `docs/agentbridge/` identifies a specific peripheral driver initialization routine, DMA channel configuration table, or MMIO buffer setup with an evidenced ROM start address targeting this RAM window. (Note: `0xFC05B458` is the heap-headroom literal `0x000B1FEC` in `sub_fc05b3c8` `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:143; docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:72]`, not a routine or peripheral DMA table). In accordance with policy, because no existing citation supports any ROM start address, none is invented. Item 8 is explicitly designated as `UNRESOLVED: no evidence-backed bounded range available`. `[UNKNOWN]` |
| **9** | **(d)** | `SleepTask` Function Body (Primary ROM Source) | `0xBFE14968` (ATCM Thumb-2; target vector `0xBFE14969` loaded at `0xFC31BF88`) | `0xFCEF33B4` | `0x00EF33B4` | `UNKNOWN` | `0xFCEF33A0..0xFCEF33EF` (Slice N7; ATCM `0xBFE14954..0xBFE149A3`) | 80 B | Target vector `0xBFE14969` loaded by ARM veneer `sub_fc31bf84` at `0xFC31BF84` (`docs/PORT27_RESIDENT_EVIDENCE.md:494-497, 606; manifest PORT27-ROM-SLEEPTASK-VENEER`). Mapped via formula: $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE14968} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF33B4}}$. Parameter units (ms) and task-only execution context are `[INFERRED]`. **Outside PORT-27 read policy boundary**. `[UNKNOWN]` |

### 4.2 Summary of Proposed Read Expansion Slices N1–N7
As documented in `docs/PORT27_OWNER_TRIAL_PLAN.md:57-76`, resolving Items 1–7 and 9 in a future milestone requires authorizing 7 bounded slices (N1 through N7) totaling **1,920 bytes**:
- **Slice N1** (`0xFC31B408..0xFC31B507`, 256 B): Heap alignment & init callee `sub_fc31b408`
- **Slice N2** (`0xFCEF3480..0xFCEF350F`, 144 B): `CreateTask` body & parameter roles
- **Slice N3** (`0xFCEEF5C0..0xFCEEF7BF`, 512 B): Task stack allocator `alloc_task_stack_tcb`
- **Slice N4** (`0xFCEEF760..0xFCEEF9BF`, 608 B): Task activation helper `activate_task`
- **Slice N5** (`0xFCEF28B0..0xFCEF29AF`, 256 B): Panic/assertion handler `DebugAssert`
- **Slice N6** (`0xFCEF3A20..0xFCEF3A5F`, 64 B): ATCM interrupt disable & restore routines
- **Slice N7** (`0xFCEF33A0..0xFCEF33EF`, 80 B): `SleepTask` body & millisecond tick scaling

Total proposed inspection size is 1,920 bytes, consuming less than 10% of the single-milestone budget limit of 24,576 bytes `[INFERRED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49; docs/PORT27_OWNER_TRIAL_PLAN.md:76]`.

> [!NOTE]
> **Status of Item 8**: As noted in §4.1, Item 8 (non-heap RAM users) is not covered by proposed slices N1–N7 because no evidence-backed bounded ROM start address exists in tracked project documents, and whole-ROM analysis across 32 MiB is outside Phase 0 bounded inspection budgets (`docs/PORT27_OWNER_TRIAL_PLAN.md:52`).

---

## 5. Machine-Readable Summary Block

The following machine-readable block provides structured key-value pairs summarizing the PORT-27 outcome and flag-off baseline verification for consumption by subsequent tasks:

```yaml
candidate_exists: false
build_command: null
diskboot_sha256: null
diskboot_size: null
flag_off_sha256: "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
default_control_sha256: "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
default_control_size: 118001
default_control_pin_citation: "docs/PROJECT_STATE.md:848, 885; tests/test_port27_resident.py:15, 74-77"
port25_combined_sha256: "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
port25_combined_size: 124865
port25_combined_pin_citation: "docs/PROJECT_STATE.md:853, 890; tests/test_port27_resident.py:19, 87-90; docs/HANDOFF.md:2327, 2364"
flag_off_build_command: "python3 tools/build_candidate_port25_ladder_fix.py --default --out-dir <out_dir>"
port25_combined_build_command: "python3 tools/build_candidate_port25_ladder_fix.py --combined --out-dir <out_dir>"
verdict: "NO-GO"
t2_outcome: "UNKNOWN_RECORD"
toolchain: "toolchains/gcc-arm-none-eabi-5_4-2016q3"
pr111_merge_head: "5a0b74b46c81138c25e50be7cc0c5c09faea8607"
target_platform_id: "0x32A8"
target_firmware: "GM1.10C"
```

---

## 6. Acceptance Criteria Compliance Checklist

- [x] **`docs/PORT28_PORT27_OUTCOME.md` exists and states, with file/line citations, whether p27-t2 produced a G3X_RESIDENT=1 candidate or an UNKNOWN record**: Confirmed in §2.1 and §2.2 with exact citations to `docs/PORT27_RESIDENT_CANDIDATE.md:6, 28-31`, `docs/PORT27_RESIDENT_EVIDENCE.md:576-579`, `tests/test_port27_resident.py:141-162, 294-299`, `docs/PROJECT_STATE.md:859`, and `docs/HANDOFF.md:2333`.
- [x] **If a candidate exists: exact build command, DISKBOOT SHA-256 and size reproduced by two local builds, evidence for items (a)/(b)/(c), and pinned flag-off SHA-256 with citation plus confirmation that current flag-off build matches**: Confirmed in §3.1–§3.4. (Candidate does not exist; exact build commands for flag-off baselines given; two local builds executed for each baseline confirming SHA-256 and byte sizes are 100% reproducible bit-for-bit; evidence status for (a)/(b)/(c) documented; pinned citations for flag-off hashes provided).
- [ ] **If no candidate: exact UNKNOWN list from `PORT27_RESIDENT_EVIDENCE.md`, each with a proposed ROM range (start, length $\le 4\text{ KiB}$) and citation-based justification**: Criterion partially met. In §4.1, Items 1–7 and 9 have evidence-backed proposed bounded slices N1–N7 ($\le 4\text{ KiB}$ each, totaling 1,920 B). For Item 8 (non-heap RAM users), no evidence-backed bounded range exists in prior project records or manifests, as proving complete absence of non-heap RAM users across 32 MiB would require unbounded whole-ROM analysis; Item 8 is therefore explicitly documented as `UNRESOLVED: no evidence-backed bounded range available` rather than inventing an unbacked address.
- [x] **Contains a machine-readable summary block (`candidate_exists`, `build_command`, `diskboot_sha256`, `diskboot_size`, `flag_off_sha256`)**: Confirmed in §5 (with explicit null values for candidate attributes under the no-candidate outcome, and separate verified keys and pin citations for default and combined baselines).
- [x] **Every claim is labelled VERIFIED / INFERRED / UNKNOWN with exact citations**: Confirmed throughout document.
- [x] **No ROM bytes, binaries or build outputs committed; no new ROM ranges read**: Confirmed. Only `docs/PORT28_PORT27_OUTCOME.md` is modified; zero binary outputs tracked.
