# PORT-27: Owner Trial Plan & NO-GO Record (2026-11-02)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-27 T4 (`p27-t4-trial-recovery-plan`)
- **Baseline Candidate Document**: `docs/PORT27_RESIDENT_CANDIDATE.md`
- **Baseline Evidence Dossier**: `docs/PORT27_RESIDENT_EVIDENCE.md`
- **Milestone Status / Verdict**: **NO TRIAL THIS MILESTONE (NO-GO RECORD)** `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6-32; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]`
- **Candidate Production Status**: **No candidate produced**; zero code modified; build invariance preserved `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`

---

## 1. Executive Summary & 'No Trial This Milestone' Declaration

In accordance with the task specification for **PORT-27 T4**:
> *"If T2 was NO-GO, write the trial plan as a 'no trial this milestone' note that carries the UNKNOWN list and the proposed next ROM ranges, and skip the recovery plan beyond a reference to the PORT-25 recovery plan."*

### 1.1 Trial Verdict & Technical Justification
**No hardware trial is conducted in milestone PORT-27** `[VERIFIED]`.

In milestone PORT-27, task T2 (`p27-t2-resident-candidate`) evaluated the evidence dossier compiled in T1 (`docs/PORT27_RESIDENT_EVIDENCE.md`) against strict project safety and verification standards:
1. **Item (a) (Stock Heap Relocation & Memory Start)**: Evaluated as partially verified (`enough to build`). The patch point at `0xFC05B3CA` and heap pool 1 exclusion up to `new_sa = 0x00368680` are verified `[VERIFIED: boot_prototype.c:24, 177-178, 212-215; docs/PORT27_RESIDENT_EVIDENCE.md:150-170]`. However, ATCM IRQ disable/restore effects (`0xBFE14FE6` / `0xBFE14FEA`) are `[INFERRED/UNKNOWN]`, DryOS heap alignment in `sub_fc31b408` is `[UNKNOWN]`, and runtime core survival against non-heap RAM users (DMA, framebuffers) is `[UNKNOWN]` `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:39]`.
2. **Item (b) (DryOS Task Creation & Calling Convention)**: **Fails strict verification** (`UNKNOWN: exact ranges still needed`). The ARM entry veneer `sub_fc31bbc4` at `0xFC31BBC4` is verified `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:251-255]`. However, the calling convention parameter semantics (`r0` name string, `r1` priority, `r2` stack size, `sp[0]` user context) remain strictly `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`. Crucially, the internal callees invoked by `CreateTask` (`0xBFE10B88` stack allocator, `0xBFE10D14` activation helper, `0xBFE13E78` assert handler) reside outside the authorized milestone read policy boundary and remain completely `[UNKNOWN]` `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:40, 58-61]`.

Under project policy:
> *"If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*

Because T2 returned a strict **NO-GO** verdict:
- **Zero code changes** were committed to `chdk-port/` or `tools/` `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`.
- **No resident candidate binary** (`candidate_port27_resident`) was produced `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`.
- **No physical hardware trial** can or should be run by the owner in this milestone `[VERIFIED: docs/SAFETY.md:7]`.
- Existing candidate builds (`default`, `--poweron-fix`, `--ladder`, `--combined`) remain 100% bit-for-bit identical to prior baselines `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:150-155]`.

---

## 2. The Exact UNKNOWN List

The table below reproduces the comprehensive catalog of every missing firmware address, internal function extent, and epistemic boundary established in `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` `[VERIFIED]`.

> [!IMPORTANT]
> **Evidenced Entry Addresses vs. Evidenced Function Extents**:  
> Per project epistemic rules, when a veneer or branch vector is identified, **only the entry address is VERIFIED**. The function length and extent remain **`UNKNOWN`** until the complete function body is decoded and its terminating instruction (`bx lr` / `pop {..., pc}`) verified. Sizing values under *Proposed Inspection Window* are non-evidentiary planning suggestions ($\le 4\text{ KiB}$) to guide future slice authorizations.

| # | Item | Component / Subsystem | Entry / Target Address (VMA) | Source ROM Entry Address | File Offset | Evidenced Function Extent | Proposed Inspection Window (Not Evidence) | Epistemic Status & Citations | Policy Status & Reason Unresolved in T1 |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|:---|
| **1** | **(b)** | Internal Task Allocator / Initializer (`alloc_task_stack_tcb` `[INFERRED: role]`) | `0xBFE10B88` (ATCM Thumb-2 `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:170]`) | `0xFCEEF5D4` | `0x00EEF5D4` | `UNKNOWN` (span up to 396 B in T1: `docs/PORT27_RESIDENT_EVIDENCE.md:597`) | $\le 512\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:170; UNKNOWN in PORT-27]`; Execution mode Thumb-2 `[VERIFIED by BL-immediate encoding at docs/PORT11A_GM110C_ROM_EVIDENCE.md:170]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** The target is called via `bl 0xBFE10B88` at `0xBFE14A8E` inside the ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:170`), which was not read in T1. Mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE10B88} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x0388} = \mathbf{0\text{xFCEEF5D4}}$, file offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEEF5D4} - 0\text{xFC000000} = \mathbf{0\text{x00EEF5D4}}$. Source ROM entry address `0xFCEEF5D4` was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`) and is not a branch target inside any ROM range read in T1. Outside milestone read policy boundary. |
| **2** | **(b)** | Internal Task Activation Helper (`activate_task` `[INFERRED: role]`) | `0xBFE10D14` (ATCM Thumb-2 `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:180]`) | `0xFCEEF760` | `0x00EEF760` | `UNKNOWN` (span up to 612 B in T1: `docs/PORT27_RESIDENT_EVIDENCE.md:598`) | $\le 1\text{ KiB}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:180; UNKNOWN in PORT-27]`; Execution mode Thumb-2 `[VERIFIED by BL-immediate encoding at docs/PORT11A_GM110C_ROM_EVIDENCE.md:180]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** Called via `bl 0xBFE10D14` at `0xBFE14AA6` inside the ATCM `CreateTask` body (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:180`), which was not read in T1. Mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE10D14} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x0514} = \mathbf{0\text{xFCEEF760}}$, file offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEEF760} - 0\text{xFC000000} = \mathbf{0\text{x00EEF760}}$. Outside milestone read policy boundary. |
| **3** | **(b)** | DryOS Debug Assertion / Kernel Panic Handler (`DebugAssert` `[INFERRED: role]`) | `0xBFE13E78` (ATCM ARM state `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176]`) | `0xFCEF28C4` | `0x00EF28C4` | `UNKNOWN` | $\le 256\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176; UNKNOWN in PORT-27]`; Execution mode ARM `[VERIFIED by BLX-immediate encoding at docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176]`; Function extent `[UNKNOWN]` | **Outside milestone read policy boundary.** Target is called via immediate `blx 0xBFE13E78` from `CreateTask` assertion/error paths in Thumb state (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176`), which switches processor execution state from Thumb to ARM. ROM source address mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE13E78} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x3678} = \mathbf{0\text{xFCEF28C4}}$, file offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEF28C4} - 0\text{xFC000000} = \mathbf{0\text{x00EF28C4}}$. Outside milestone read policy boundary. |
| **4** | **(b)** | `CreateTask` Function Body & Calling Convention (Primary ROM Source) | `0xBFE14A3C..0xBFE14AAD` (ATCM Thumb-2; target vector `0xBFE14A3D`) | `0xFCEF3488..0xFCEF34F9` | `0x00EF3488..0x00EF34F9` | `114 bytes` (`0x72` B) `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:592, 600; docs/PORT11A_GM110C_ROM_EVIDENCE.md:131-133, 182]` | N/A (exact 114 B extent known from T1 / PORT11A) | Entry address vector `0xBFE14A3D` is `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:251-255; manifest PORT27-ROM-CREATETASK-VENEER]`. The exact ROM source range `0xFCEF3488..0xFCEF34F9` (114 bytes), corresponding to ATCM RAM `0xBFE14A3C..0xBFE14AAD`, and its complete instruction extent are known and verified from T1 / PORT11A (`docs/PORT27_RESIDENT_EVIDENCE.md:592, 600`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`). Calling convention parameter semantics (`r0` name, `r1` priority, `r2` stack size, `sp[0]` user context) remain `[INFERRED per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]`; direct body decode and authority under PORT-27 are missing (`[UNKNOWN]`). | **Outside milestone read policy boundary.** The ROM range `0xFCEF3488..0xFCEF34F9` corresponds to ATCM `0xBFE14A3C..0xBFE14AAD` via the early boot copy loop at `0xFC020040..0xFC020052` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118, 131-133`). However, ROM control flow reaches the veneer `sub_fc31bbc4` at `0xFC31BBC4`, which executes ARM `ldr pc, [pc, #-4]` branching to ATCM RAM (`0xBFE14A3D`), not to high ROM. Range `0xFCEF3488..0xFCEF34F9` is not a verified branch target from any ROM range read in T1. Because reading it was unauthorized under policy, PORT-27 could not perform an authorized body decode, leaving calling convention parameter semantics strictly `[INFERRED]`. |
| **5** | **(a)** | ATCM Interrupt Disable Destination (`DisableInterrupts_ATCM` `[INFERRED: role]`) | `0xBFE14FE6` (ATCM Thumb-2; target vector `0xBFE14FE7` loaded at `0xFC31BF00`) | `0xFCEF3A32` | `0x00EF3A32` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:124-125; manifest PORT27-ROM-IRQ-DISABLE]`; Execution mode Thumb-2 `[VERIFIED by target vector bit 0 = 1 loaded via ldr pc at docs/PORT27_RESIDENT_EVIDENCE.md:124-125]`; Function extent `[UNKNOWN]`; Implementation behavior and effects `[INFERRED/UNKNOWN]` | **Outside milestone read policy boundary.** ARM veneer `sub_fc31befc` at `0xFC31BEFC` loads target vector `0xBFE14FE7` (instruction address `0xBFE14FE6`). Mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (\text{ATCM} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x47E6} = \mathbf{0\text{xFCEF3A32}}$. File offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEF3A32} - 0\text{xFC000000} = \mathbf{0\text{x00EF3A32}}$. Source ROM address `0xFCEF3A32` was not cited in prior manifests and is not a direct ROM branch target. Outside milestone read policy boundary. |
| **6** | **(a)** | ATCM Interrupt Restore Destination (`RestoreInterrupts_ATCM` `[INFERRED: role]`) | `0xBFE14FEA` (ATCM Thumb-2; target vector `0xBFE14FEB` loaded at `0xFC31B8CA`) | `0xFCEF3A36` | `0x00EF3A36` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:110-115, 125; manifest PORT27-ROM-RESTORE-IRQ-VENEER]`; Execution mode Thumb-2 `[VERIFIED by target vector bit 0 = 1 branched via bx ip at docs/PORT27_RESIDENT_EVIDENCE.md:110-115, 125]`; Function extent `[UNKNOWN]`; Continuation behavior and absence of heap operations `[INFERRED/UNKNOWN]` | **Outside milestone read policy boundary.** Thumb-2 veneer `sub_fc31b8ca` at `0xFC31B8CA` executes `bx ip` to ATCM VMA `0xBFE14FEB` (instruction address `0xBFE14FEA`). Mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (\text{ATCM} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x47EA} = \mathbf{0\text{xFCEF3A36}}$. File offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEF3A36} - 0\text{xFC000000} = \mathbf{0\text{x00EF3A36}}$. Outside milestone read policy boundary. |
| **7** | **(a)** | DryOS Heap-Start Alignment Specification & Kernel Init (`sub_fc31b408`) | `0xFC31B408` (ROM ARM state; target of `0xFC05B448: blx 0xfc31b408`) | `0xFC31B408` | `0x0031B408` | `UNKNOWN` | $\le 256\text{ B}$ ($\le 4\text{ KiB}$) | Entry address `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:158, 170; manifest PORT27-ROM-HEAP-SETUP]`; Execution mode ARM `[VERIFIED by BLX-immediate encoding at docs/PORT27_RESIDENT_EVIDENCE.md:158, 170]`; Function extent `[UNKNOWN]`; Alignment specification `[UNKNOWN]` | **Reachable under policy, not read in T1.** Start address `0xFC31B408` is a branch target verified inside an approved range (`0xFC05B448: blx 0xfc31b408` in `PORT27-ROM-HEAP-SETUP`), making it eligible for a bounded read under milestone policy. It was not read in T1. The PORT-27 manifest budget authorizes up to 24,576 bytes total ($\le 4,096$ bytes per slice); T1 read 2,380 bytes across 8 slices, leaving **22,196 bytes** of unspent budget `[VERIFIED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49-55; docs/PORT27_RESIDENT_EVIDENCE.md:558-570]`. Alignment checks enforced by DryOS downstream of `sub_fc31b408` remain `UNKNOWN`. |
| **8** | **(a)** | Relocated Core Region Non-Heap RAM Users | Span `0x003489B4..0x00368680` (RAM) | Entire 32 MiB ROM (`0xFC000000..0xFDFFFFFF`) | Entire dump | N/A (RAM buffer span 130,252 B) | N/A (whole-ROM analysis) | Relocated core exclusion from heap pool 1 allocations is `[VERIFIED: boot_prototype.c:24, 177-178, 212-215; docs/PORT21_RAM_LIFETIME.md:40-41]`; Complete runtime survival against non-heap RAM users is `[UNKNOWN]` | **Exceeds Phase 0 bounded inspection budgets.** Raising the heap base past `_end` (`0x00368680`) excludes relocated core RAM from DryOS heap pool 1 allocations `[VERIFIED]`. Proving complete runtime survival against hardware DMA transfers (image sensor, video codec, SD card DMA controller), framebuffers, or hardcoded pointers requires whole-ROM analysis across 32 MiB of ROM (`0xFC000000..0xFDFFFFFF`), impossible under Phase 0 bounded inspection budgets ($\le 4,096$ B/slice, $\le 24,576$ B milestone total). |
| **9** | **(d)** | `SleepTask` Function Body (Primary ROM Source) | `0xBFE14968` (ATCM Thumb-2; target vector `0xBFE14969` loaded at `0xFC31BF88`) | `0xFCEF33B4` | `0x00EF33B4` | `UNKNOWN` | $\le 64\text{ B}$ ($\le 4\text{ KiB}$) | Entry address vector `[VERIFIED: docs/PORT27_RESIDENT_EVIDENCE.md:494-497; manifest PORT27-ROM-SLEEPTASK-VENEER]`; Execution mode Thumb-2 `[VERIFIED by target vector bit 0 = 1 loaded via ldr pc at docs/PORT27_RESIDENT_EVIDENCE.md:494-497]`; Function extent `[UNKNOWN]`; Parameter unit (milliseconds) and task context constraint `[INFERRED]` | **Outside milestone read policy boundary.** The ARM veneer `0xFC31BF84` loads target vector `0xBFE14969` (ATCM RAM execution address `0xBFE14968`). Mapped via PORT11A §3.1 formula (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`): $\text{ROM} = 0\text{xFCEEF24C} + (\text{ATCM} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x4168} = \mathbf{0\text{xFCEF33B4}}$, file offset from `PRIMARY.BIN` base `0xFC000000`: $\text{File\_Offset} = 0\text{xFCEF33B4} - 0\text{xFC000000} = \mathbf{0\text{x00EF33B4}}$. The source ROM entry address `0xFCEF33B4` is not a direct ROM branch target and was not cited in prior manifests (`PORT23`, `PORT24`, `PORT25`). Outside milestone read policy boundary. |

---

## 3. Proposed Next ROM Ranges for Milestone Read Policy Expansion

To resolve the strict NO-GO verdict and enable a verified resident candidate in a future milestone, the read policy must authorize specific bounded slices covering the missing ATCM early-boot routines in high ROM and the heap alignment callee in primary ROM.

All proposed slices comply strictly with Phase 0 bounds ($\le 4\text{ KiB}$ per slice). The table below lists routine entry addresses separately from the mapped inspection windows (start/length in ROM and ATCM), calculated using the verified PORT11A §3.1 mapping formula:
$$\text{ROM} = 0\text{xFCEEF24C} + (\text{ATCM} - 0\text{xBFE10800})$$
$$\text{ATCM} = 0\text{xBFE10800} + (\text{ROM} - 0\text{xFCEEF24C})$$
$$\text{File\_Offset} = \text{ROM} - 0\text{xFC000000}$$

| Slice ID | Target Routine | Routine Entry Address | Proposed ROM Window | Slice Size | File Offset Range | Mapped ATCM / VMA Window | Prerequisite Item Resolved |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **N1** | DryOS Heap Alignment & Init (`sub_fc31b408`) | `0xFC31B408` (ROM ARM) | `0xFC31B408..0xFC31B507` | 256 B | `0x0031B408..0x0031B507` | `0xFC31B408..0xFC31B507` (ROM ARM) | Item (a): Heap start alignment requirements |
| **N2** | `CreateTask` Body & Calling Convention | `0xBFE14A3C` (Thumb-2 vector `0xBFE14A3D`; ROM `0xFCEF3488`) | `0xFCEF3480..0xFCEF350F` | 144 B | `0x00EF3480..0x00EF350F` | `0xBFE14A34..0xBFE14AC3` (ATCM Thumb-2) | Item (b): Static decode of parameter roles (`r0`–`r2`, `sp[0]`) |
| **N3** | Task Stack Allocator (`alloc_task_stack_tcb`) | `0xBFE10B88` (Thumb-2; ROM `0xFCEEF5D4`) | `0xFCEEF5C0..0xFCEEF7BF` | 512 B | `0x00EEF5C0..0x00EEF7BF` | `0xBFE10B74..0xBFE10D73` (ATCM Thumb-2) | Item (b): Verification of `r2 = 0` default stack allocation |
| **N4** | Task Activation Helper (`activate_task`) | `0xBFE10D14` (Thumb-2; ROM `0xFCEEF760`) | `0xFCEEF760..0xFCEEF9BF` | 608 B | `0x00EEF760..0x00EEF9BF` | `0xBFE10D14..0xBFE10F73` (ATCM Thumb-2) | Item (b): Verification of task activation & dispatch logic |
| **N5** | Panic / Assert Handler (`DebugAssert`) | `0xBFE13E78` (ARM; ROM `0xFCEF28C4`) | `0xFCEF28B0..0xFCEF29AF` | 256 B | `0x00EF28B0..0x00EF29AF` | `0xBFE13E64..0xBFE13F63` (ATCM ARM) | Item (b): Parameter assert conditions in `CreateTask` |
| **N6** | ATCM Interrupt Disable & Restore Routines | `0xBFE14FE6` (Disable; ROM `0xFCEF3A32`), `0xBFE14FEA` (Restore; ROM `0xFCEF3A36`) | `0xFCEF3A20..0xFCEF3A5F` | 64 B | `0x00EF3A20..0x00EF3A5F` | `0xBFE14FD4..0xBFE15013` (ATCM Thumb-2) | Item (a): ATCM interrupt management & non-heap safety |
| **N7** | `SleepTask` Body & Delay Tick Scaling | `0xBFE14968` (Thumb-2 vector `0xBFE14969`; ROM `0xFCEF33B4`) | `0xFCEF33A0..0xFCEF33EF` | 80 B | `0x00EF33A0..0x00EF33EF` | `0xBFE14954..0xBFE149A3` (ATCM Thumb-2) | Item (d): Millisecond scaling factor and task-context safety |

**Total Proposed Slices Size**: **1,920 bytes** across 7 bounded slices (well within the single-milestone budget limit of 24,576 bytes, consuming less than 10% of allowable inspection bandwidth) `[INFERRED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49]`.

---

## 4. Candidate Trial Protocol (Specifications for Future Candidate Trials)

Although no trial is conducted in PORT-27, this section establishes the technical protocol, boot method, and verification commands required when a candidate is evaluated in a future milestone.

### 4.1 Host-Side Checksum and Size Verification
Before copying any candidate payload to an SD card, the owner MUST verify the cryptographic integrity and byte size directly on the host workstation `[INFERRED: docs/SAFETY.md:7-8]`:

```bash
# 1. Verify candidate SHA-256 checksum against pinned candidate hash
sha256sum <candidate_output_dir>/DISKBOOT.BIN

# 2. Verify candidate decimal byte size
stat -c %s <candidate_output_dir>/DISKBOOT.BIN
```

#### Reference Baseline Checksums & Sizes (Flag-Off Invariance Baselines)
- **Default Baseline `DISKBOOT.BIN`**:
  - SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED: docs/PORT19_GO_NOGO.md:31; docs/PORT25_LADDER_FIX_CANDIDATE.md:381; docs/PORT27_RESIDENT_CANDIDATE.md:151]`
  - Decimal Size: `118,001` bytes `[VERIFIED]`
- **PORT-25 Combined Baseline `DISKBOOT.BIN`**:
  - SHA-256: `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:385, 402; docs/PORT27_RESIDENT_CANDIDATE.md:154]`
  - Decimal Size: `124,865` bytes `[VERIFIED]`

### 4.2 Boot Method: The Held-Press Boot Method
The authorized boot method for resident heartbeat candidate trials is the **Held-Press Boot Method** `[VERIFIED: docs/PORT24_SESSION_PLAN.md:92-96; docs/PORT26_CODE43_RECORD.md:40-44]`.

1. **Button Action**: The owner powers on the camera by pressing and **holding the Power button down continuously** `[VERIFIED: docs/PORT26_CODE43_RECORD.md:40-44]`.
2. **Hold Duration**: The button MUST remain held until:
   - All 7 loader pulses have played.
   - The dark transition gap has passed.
   - Core ladder groups 11–15, 21–26, 31–35, and 41–44 have finished.
   - The rear LCD illuminates and the Canon stock user interface is fully visible `[VERIFIED: docs/PORT26_CODE43_RECORD.md:40-44]`.
3. **Held-Press vs. Short-Press Behavior & Scope**:
   - Holding the Power button continuously until Canon stock UI boots reliably reaches the stock UI `[VERIFIED: docs/PORT26_CODE43_RECORD.md:40-44; docs/PORT26_TRIAL_2026-11-02.md:92-96; docs/PORT24_POWERON_FIX.md:19-24]`.
   - On short press, high-speed optical timing capture verified that the camera cleanly shuts down at **Code 43** (inside `task_Startup_my`, after helper `sub_fc1283d2` returns and before Code 44) `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:63-65; docs/PORT26_CODE43_RECORD.md:12-38]`.
   - The earlier hypothesis attributing short-press shutdown to early power-check re-entry into `sub_fc1284ac` / `sub_fc05ba56` is `[INFERRED / SUPERSEDED: docs/PORT23_POWER_SUPERVISION.md:43-50, 285-294; docs/PORT26_CODE43_RECORD.md:28-38]` because PORT-26 proved that execution proceeds past Stage 5 all the way to Code 43 on short press, and the PORT-24 `--poweron-fix` bypass was verified insufficient `[VERIFIED: docs/PORT23_POWER_SUPERVISION.md:50, 294; docs/PORT26_CODE43_RECORD.md:28-38]`.
   - The remaining physical mechanism that triggers power-off at Code 43 on short press is `[UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:50, 294; docs/PORT26_CODE43_RECORD.md:38]` and is explicitly out of scope for resident heartbeat, deferred to Step 3 per owner directive `[VERIFIED: docs/PORT26_CODE43_RECORD.md:59-62]`.

### 4.3 Short-Press Shutdown is Explicitly Out of Scope
> [!IMPORTANT]
> **Short-press shutdown is EXPLICITLY OUT OF SCOPE for resident heartbeat trials.**  
>
> On 2026-11-02, the owner established a binding priority directive:
> *"The owner-directed sequence prioritizes the CHDK GUI track ahead of the short-press fix: Step 1: resident CHDK task after the sub_fc0d0126 handoff, with an LED heartbeat checked with a held press... Step 3: keyboard/task_PhySw hook and ALT toggle, with the short-press fix folded in."* `[VERIFIED: docs/PORT26_CODE43_RECORD.md:59-62; docs/PROJECT_STATE.md:839-847]`.
>
> Therefore:
> - Short-press power-on trials are **NOT performed** for resident heartbeat evaluation.
> - Any shutdown observed on a short press is expected behaviour under the known Code 43 mechanism and is deferred to Step 3.

### 4.4 Expected Physical Observations for a Resident Heartbeat Candidate
When a valid resident candidate is tested with the held-press boot method in a future milestone, the expected sequential observations are:
1. **Loader Phase**: Exactly **7 single green LED blinks** (~25 ms ON / ~58 ms OFF) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:328-334]`.
2. **Transition Gap**: A distinct dark pause (~58–138 ms) separating the loader from core execution `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:228-232]`.
3. **Core Ladder Groups**:
   - Group 1 (11, 12, 13, 14, 15): Core entry, BSS clear, witness setup, kernel init entry `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:336-340]`.
   - Group 2 (21, 22, 23, 24, 25, 26): Stage 5 entry, MPU config, power check bypass pass, `CreateTask("Startup")` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:342-347]`.
   - Group 3 (31, 32, 33, 34, 35): `task_Startup_my` entry, driver init, SD init return, watchdog arming `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:348-352]`.
   - Group 4 (41, 42, 43, 44): Post-watchdog, `task_PhySw` create, helper return, pre-firmware continuation `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:353-354]`.
4. **Stock Firmware Startup**: LCD backlight illuminates, Canon splash logo displays, shooting/playback UI renders on screen `[INFERRED: docs/PORT24_SESSION_PLAN.md:92-96; docs/PORT26_CODE43_RECORD.md:40-44]`.
5. **Resident LED Heartbeat**: Once the stock UI is operating, the rear green LED toggles continuously at **roughly 1 Hz** (~500 ms ON, ~500 ms OFF) `[INFERRED: prompt p27-t4; docs/PORT27_RESIDENT_EVIDENCE.md:460-463]`. Observing a visible LED heartbeat alongside the stock UI suggests that a resident background task is executing its toggle loop `[INFERRED: docs/PORT27_RESIDENT_EVIDENCE.md:244-248, 460-463]`. However, this visible toggle does NOT establish non-destructive coexistence or memory safety, which remain strictly `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:24, 65, 87-92]`. Specifically, relocated core RAM (`0x003489B4..0x00368680`) is excluded from DryOS heap pool 1 allocations `[VERIFIED: boot_prototype.c:24, 177-178, 212-215]`, but whether unmanaged non-heap RAM users (such as hardware DMA transfers, image buffers, or video pipelines) overwrite resident code or stack memory remains `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:24, 65]`.

---

## 5. Optical Ladder Decoding with `tools/port26_ladder_decode.py` (Deferred for NO-GO)

Because milestone PORT-27 concluded with a strict NO-GO verdict and produced no candidate binary, no physical hardware trial was conducted, and the empirical physical outcome table and optical ladder decoding are deferred to the future milestone that produces a candidate binary.

When candidate trials are conducted in a future milestone, optical ladder captures and classifications will follow the technical protocols below:

1. **Decoder Operation & Digest Override**:
   Optical pulse sequences captured from the rear green LED are decoded using `tools/port26_ladder_decode.py` `[VERIFIED: tools/port26_ladder_decode.py:1-40]`.
   By default, `tools/port26_ladder_decode.py` pins the expected candidate SHA-256 to the PORT-25 combined digest (`9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15`) `[VERIFIED: tools/port26_ladder_decode.py:149-151, 1888-1898]`.
   The command-line interface (`main()`, `tools/port26_ladder_decode.py:2394-2420`) accepts only positional `input`, `--json`, and `--report` flags, and contains no command-line option to override the candidate SHA-256. At the Python API level, `classify_owner_report` (`tools/port26_ladder_decode.py:1831-1835`) and `decode_ladder_report` (`tools/port26_ladder_decode.py:2383-2387`) accept an optional parameter `expected_sha256: str = EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256`. When evaluating a new candidate binary digest in a future milestone, overriding the expected hash requires either passing `expected_sha256` via the Python API or updating the module constant `EXPECTED_PORT25_COMBINED_DISKBOOT_SHA256` (`tools/port26_ladder_decode.py:149-151`); invoking the existing CLI directly against a different candidate hash will trigger an `INVALID_CANDIDATE` classification `[VERIFIED: tools/port26_ladder_decode.py:1888-1898, 2394-2420]`.

2. **Decoder Output Classes**:
   The decoder evaluates input trial parameters and emits exact classification classes `[VERIFIED: tools/port26_ladder_decode.py:1901-2020]`:
   - `CONTROL_HELD_O1`: Emitted when `press: held` and `lcd: stock_ui`, confirming the held-press control trial successfully reached the stock user interface `[VERIFIED: tools/port26_ladder_decode.py:1901-1918]`.
   - `NO_PULSES`: Emitted when `pulses: none` (case-insensitive), indicating no optical activity was detected (e.g. unpowered or battery depleted) `[VERIFIED: tools/port26_ladder_decode.py:1921]`.
   - Stage Codes `CODE_11` through `CODE_44`: Emitted when decoded pulse sequences match specific stage definitions `[VERIFIED: tools/port26_ladder_decode.py:1980-2020]`. For example, `CODE_43` indicates execution reached the helper-return checkpoint in `task_Startup_my`, while `CODE_44` indicates full completion of the early boot ladder.
   - `UNKNOWN_CODE`: Emitted when pulse counts or sequence timings cannot be matched to a defined checkpoint `[VERIFIED: tools/port26_ladder_decode.py:1930]`.

3. **Resident Heartbeat Verification & Outcome Interpretation**:
   In a candidate resident heartbeat trial, completion of the early boot ladder through `CODE_44` (`STAGE_BC_PRE_FIRMWARE_CONT`, immediately preceding the stock firmware continuation branch `sub_fc0d0126` `[VERIFIED: tools/port26_ladder_decode.py:504-515]`) is an expected observation `[INFERRED: prompt p27-t4; docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55; tools/port26_ladder_decode.py:504-515]`, followed by the appearance of the Canon stock UI. Note that `CONTROL_HELD_O1` is a classification of held press and stock UI (`press: held` and `lcd: stock_ui`) that is returned before examining any pulses (`tools/port26_ladder_decode.py:1905-1918`), so it does not depend on pulses and is not evidence that the ladder completed `[VERIFIED: tools/port26_ladder_decode.py:1905-1918]`. The recorded held-run optical codes were not captured and remain strictly `[UNKNOWN: docs/PORT26_CODE43_RECORD.md:43]`.
   - **Heartbeat Visible (~1 Hz Toggle)**: If the rear green LED toggles continuously at roughly 1 Hz while the stock UI is operating, the interpretation that the resident heartbeat task is actively executing is `[INFERRED: prompt p27-t4; docs/PORT27_RESIDENT_EVIDENCE.md:244-248, 460-463]`. However, observing an ongoing optical blink does NOT establish non-destructive coexistence or long-term memory safety, both of which remain strictly `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:24, 65, 87-92]`. Heap pool 1 exclusion up to `0x00368680` protects relocated core RAM only against standard DryOS heap allocations `[VERIFIED: boot_prototype.c:24, 177-178, 212-215]`; survival against non-heap RAM users (DMA transfers, video codec buffers, framebuffers) and stack preservation under unread kernel allocation routines remain `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:24, 65, 87-92]`.
   - **LED Dark or Solid ON**: If the stock UI boots cleanly but the rear green LED remains dark or solid ON, the interpretation that the resident task failed to spawn or hung during execution is `[INFERRED: docs/PORT27_RESIDENT_CANDIDATE.md:87-92]`. Plausible alternative root causes remain `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:24, 65, 87-92]`, including:
     1. The task was created but never scheduled by the DryOS scheduler `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:25, 61, 87-92]`.
     2. LED MMIO register writes (`0xD20B0884`) were overridden or reconfigured by stock firmware background tasks or GPIO controllers `[UNKNOWN: docs/PORT23_LED_BREADCRUMBS.md:6-7; docs/PORT27_RESIDENT_CANDIDATE.md:24]`.
     3. The sleep/delay primitive stalled or deadlocked due to unverified tick scaling or non-task execution context `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:66, 94]`.
     4. The task crashed silently due to stack overflow, kernel assert, or memory corruption elsewhere in the system `[UNKNOWN: docs/PORT27_RESIDENT_CANDIDATE.md:60, 90-91]`.

---

## 6. Result Recording for `tools/port18_trial_report.py`

### 6.1 Status for PORT-27
Because milestone PORT-27 concluded with a strict NO-GO verdict and produced no candidate binary, no physical trial was run, and no trial report is ingested for PORT-27 `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`.

### 6.2 Invariants for Future Candidate Trials
When candidate trials are conducted in future milestones, the owner records the observed results in a structured report parsed and validated by `tools/port18_trial_report.py` `[VERIFIED: tools/port18_trial_report.py:8-22]`:
1. **Single Fenced Block Requirement**: The ingest parser extracts report content via regex `fence_pattern = re.compile(r"^```port18-report\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)` and processes **only the first fenced block in the file** `[VERIFIED: tools/port18_trial_report.py:461-465]`. Appending a second block causes it to be silently ignored.
2. **Dedicated Report Path**: Each power-on attempt must be recorded in its own dedicated file under `private/` (e.g. `private/port27/trial_report_held.md`), which is git-ignored via `.gitignore:34` `[VERIFIED: .gitignore:34]`.
3. **Classification Invariants**: To classify cleanly under `tools/port18_trial_report.py --strict`:
   - The candidate SHA-256 and byte size must match the actual candidate binary under test.
   - When testing without witness readout tools, a held-press run reaching the stock UI must specify `witness_observed: no` (or `unknown`) and `trace_log_present: no` to classify as Outcome `O4` `[VERIFIED: tools/port18_trial_report.py:1035-1038]`.
   - If specifying `witness_observed: yes` (with `trace_log_present: no`), either a verified witness dump path or enough readout detail (recognized readout text in `notes`) must be supplied to classify the trial `[VERIFIED: tools/port18_trial_report.py:958-989]`. A readout in `notes` is recognizable when `extract_readout_indicators_from_notes` yields `notes_status == "exact"`, meaning exactly one unambiguous uncancelled indicator token (`CONT_ATTEMPTED`, `CORE_REACHED`, `LOADER_REACHED`, `WITNESS_INVALID`, `STALE / REPLAY`, or `SCRIPT_ERROR`) is present in a clause and not cancelled by a leading or trailing negation word (e.g. `not`, `no`, `never`, `none`, `without`, `absent`, `unobserved`, `missing`) `[VERIFIED: tools/port18_trial_report.py:834-873, 913-941, 979-981]`. If neither a challenge-checked witness dump path nor recognizable readout text in `notes` is supplied (e.g. notes lack indicators or contain conflicting or cancelled tokens), `derive_implied_outcome` cannot distinguish between candidate outcomes, producing `classification_status = "insufficient_evidence"` and failing strict validation `[VERIFIED: tools/port18_trial_report.py:982-989, 1040-1048]`.
