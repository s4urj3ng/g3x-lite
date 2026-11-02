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

All proposed slices comply strictly with Phase 0 bounds ($\le 4\text{ KiB}$ per slice):

| Slice ID | Target Routine / Purpose | Proposed ROM Range | Size (Bytes) | File Offset Range | Target ATCM / VMA | Prerequisite Item Resolved |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| **N1** | DryOS Heap Alignment & Init (`sub_fc31b408`) | `0xFC31B408..0xFC31B507` | 256 B | `0x0031B408..0x0031B507` | `0xFC31B408` (ROM ARM) | Item (a): Heap start alignment requirements |
| **N2** | `CreateTask` Body & Calling Convention | `0xFCEF3480..0xFCEF350F` | 144 B | `0x00EF3480..0x00EF350F` | `0xBFE14A3C..0xBFE14AAF` (ATCM Thumb-2) | Item (b): Static decode of parameter roles (`r0`–`r2`, `sp[0]`) |
| **N3** | Task Stack Allocator (`alloc_task_stack_tcb`) | `0xFCEEF5C0..0xFCEEF7BF` | 512 B | `0x00EEF5C0..0x00EEF7BF` | `0xBFE10B88..0xBFE10D87` (ATCM Thumb-2) | Item (b): Verification of `r2 = 0` default stack allocation |
| **N4** | Task Activation Helper (`activate_task`) | `0xFCEEF760..0xFCEEF9BF` | 608 B | `0x00EEF760..0x00EEF9BF` | `0xBFE10D14..0xBFE10F73` (ATCM Thumb-2) | Item (b): Verification of task activation & dispatch logic |
| **N5** | Panic / Assert Handler (`DebugAssert`) | `0xFCEF28B0..0xFCEF29AF` | 256 B | `0x00EF28B0..0x00EF29AF` | `0xBFE13E78..0xBFE13F77` (ATCM ARM) | Item (b): Parameter assert conditions in `CreateTask` |
| **N6** | ATCM Interrupt Disable & Restore Routines | `0xFCEF3A20..0xFCEF3A5F` | 64 B | `0x00EF3A20..0x00EF3A5F` | `0xBFE14FE0..0xBFE1501F` (ATCM Thumb-2) | Item (a): ATCM interrupt management & non-heap safety |
| **N7** | `SleepTask` Body & Delay Tick Scaling | `0xFCEF33A0..0xFCEF33EF` | 80 B | `0x00EF33A0..0x00EF33EF` | `0xBFE14950..0xBFE1499F` (ATCM Thumb-2) | Item (d): Millisecond scaling factor and task-context safety |

**Total Proposed Slices Size**: **1,920 bytes** across 7 bounded slices (well within the single-milestone budget limit of 24,576 bytes, consuming less than 10% of allowable inspection bandwidth) `[INFERRED: docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json:49]`.

---

## 4. Candidate Trial Protocol (Specifications for Future Candidate Trials)

Although no trial is conducted in PORT-27, this section establishes the complete technical protocol, boot method, and verification commands required when a candidate is evaluated in a future milestone.

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
3. **Physical Hardware Mechanism**: Holding the button maintains physical assertion of GPIO 0x97 (`0xD20B09EC`), ensuring native supervisor routine `sub_fc1284ac` returns 1, which bypasses the native Canon power-cut routine `sub_fc05ba56` `[VERIFIED: docs/PORT23_POWER_SUPERVISION.md:43-50, 284-293]`.

### 4.3 Short-Press Shutdown is Explicitly Out of Scope
> [!IMPORTANT]
> **Short-press shutdown is EXPLICITLY OUT OF SCOPE for resident heartbeat trials.**  
>
> In the 2026-11-02 owner trial of the PORT-25 combined candidate, high-speed optical capture (240 fps) verified that a short press cleanly shuts down at **Code 43** (helper-return checkpoint in `task_Startup_my`, after `sub_fc1283d2` returns and before Code 44) `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:63-65; docs/PORT26_CODE43_RECORD.md:12-38]`.
>
> On 2026-11-02, the owner established a binding priority directive:
> *"The owner-directed sequence prioritizes the CHDK GUI track ahead of the short-press fix: Step 1: resident CHDK task after the sub_fc0d0126 handoff, with an LED heartbeat checked with a held press... Step 3: keyboard/task_PhySw hook and ALT toggle, with the short-press fix folded in."* `[VERIFIED: docs/PORT26_CODE43_RECORD.md:59-62; docs/PROJECT_STATE.md:839-847]`.
>
> Therefore:
> - Short-press power-on trials are **NOT performed** for resident heartbeat evaluation.
> - Any shutdown observed on a short press is expected behaviour under the known Code 43 mechanism and is deferred to Step 3.

### 4.4 Expected Physical Observations for a Resident Heartbeat Candidate
When a valid resident candidate is tested with the held-press boot method, the expected sequential observations are:
1. **Loader Phase**: Exactly **7 single green LED blinks** (~25 ms ON / ~58 ms OFF) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:328-334]`.
2. **Transition Gap**: A distinct dark pause (~58–138 ms) separating the loader from core execution `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:228-232]`.
3. **Core Ladder Groups**:
   - Group 1 (11, 12, 13, 14, 15): Core entry, BSS clear, witness setup, kernel init entry `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:336-340]`.
   - Group 2 (21, 22, 23, 24, 25, 26): Stage 5 entry, MPU config, power check bypass pass, `CreateTask("Startup")` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:342-347]`.
   - Group 3 (31, 32, 33, 34, 35): `task_Startup_my` entry, driver init, SD init return, watchdog arming `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:348-352]`.
   - Group 4 (41, 42, 43, 44): Post-watchdog, `task_PhySw` create, helper return, pre-firmware continuation `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:353-354]`.
4. **Stock Firmware Startup**: LCD backlight illuminates, Canon splash logo displays, shooting/playback UI renders on screen `[INFERRED]`.
5. **Resident LED Heartbeat**: Once the stock UI is operating, the rear green LED toggles continuously at **roughly 1 Hz** (~500 ms ON, ~500 ms OFF) `[INFERRED: prompt p27-t4]`. The heartbeat runs as an independent DryOS background task, confirming non-destructive coexistence with stock camera operations.

---

## 5. Comprehensive Physical Outcome Table & Decoding

The outcome table below maps every possible physical observation during a held-press candidate trial to its technical diagnosis, next action, ladder decoding class via `tools/port26_ladder_decode.py`, and `tools/port18_trial_report.py` outcome class.

| Physical Observation | `tools/port26_ladder_decode.py` Output Class | Technical Meaning & Diagnosis | `tools/port18_trial_report.py` Classification | Next Action & Protocol |
|:---|:---:|:---|:---:|:---|
| **7 loader blinks, core codes 11-44 play, LCD illuminates to stock UI, rear green LED blinks at ~1 Hz continuously** | `CODE_44` (or `SUCCESS`) | **Candidate Full Success**: Ladder finished, handoff to firmware completed, resident task successfully spawned, DryOS multitasking active, and LED heartbeat running concurrently with stock UI. | `outcome_id: O4` (or `O6` if inspector run) `[VERIFIED: tools/port18_trial_report.py:1036-1042]` | Candidate validated. Maintain camera on for 60 seconds to confirm stability, record video, power off normally, file trial report. |
| **7 loader blinks, core codes 11-44 play, LCD illuminates to stock UI, but rear green LED remains dark (NO heartbeat)** | `CODE_44` | **Heartbeat Task Failure**: Early boot ladder and stock firmware boot succeeded, but resident task was not created or hung before LED toggle loop. DryOS heap or task creation parameter failure. | `outcome_id: O4` `[VERIFIED: tools/port18_trial_report.py:1036]` | Camera is running stock UI safely. Do not force crash. Power off normally. Inspect SD card for `TRACE.LOG`, file trial report. |
| **7 loader blinks, core codes 11-44 play, LCD illuminates to stock UI, but rear green LED stays SOLID ON** | `CODE_44` | **Heartbeat Task Hang / Crash**: Resident task asserted MMIO ON word (`0x004D0002`) but hung in delay primitive (`SleepTask` veneer `0xFC31BF84` or tick scaling) without toggling OFF. | `outcome_id: O4` (or `O8` if UI freezes) `[VERIFIED: tools/port18_trial_report.py:1016, 1036]` | Power off normally or perform § 5.2.1 battery pull if UI freezes. Triage `SleepTask` calling convention. |
| **7 loader blinks, core codes play through Code 43, then LED darkens and camera shuts down or hangs without Code 44** | `CODE_43` `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:83-89]` | **Code 43 / Premature Release**: The Power button was released prematurely before Code 44 finished, or native supervisor shut down before handoff. | `outcome_id: O10` (if unpowered) or `O8` (if hung) `[VERIFIED: tools/port18_trial_report.py:1016, 1020]` | Verify that the Power button was held firmly and continuously until LCD illuminated. If button was held, triage Code 43 window (`boot_prototype_ladder.c:418-442`). |
| **Ladder halts at any earlier code (e.g. Code 15, 26, 35) or LED stays solid ON during ladder** | Decode via `tools/port26_ladder_decode.py` (e.g. `CODE_15`, `CODE_26`, `CODE_35`) | **Boot Stage Hang**: Execution failed at the identified checkpoint. | `outcome_id: O8` (if hung) or `O10` (if shut down) `[VERIFIED: tools/port18_trial_report.py:1016, 1020]` | Execute battery pull recovery (`docs/PORT25_OWNER_TRIAL_PLAN.md:347-355`). Note exact last code observed and file report. |
| **Ladder plays, but camera enters reboot loop, displays Canon error code / ROM assert, or abnormal lens movement** | Indeterminate / `abnormal_state` | **Kernel Assert / Abnormal State**: Memory corruption, invalid heap pointer, or DryOS panic assert triggered downstream. | `outcome_id: O11` (no log) or `O12` (`TRACE.LOG` present) `[VERIFIED: tools/port18_trial_report.py:1023-1025]` | **Immediate Abort**: Pull battery immediately. Do NOT permit reboot loop. Remove card and file report. |
| **Camera fails to power on at all (no LED, no lens, no LCD)** | `no_power_on` | **Power-On Interlock / Battery Depleted**: Battery door open, battery depleted, or hardware interlock fault. | `outcome_id: O10` `[VERIFIED: tools/port18_trial_report.py:1020]` | Verify battery charge in external charger and ensure door latch is fully closed. Test with no card in Playback mode. |

---

## 6. Result Recording for `tools/port18_trial_report.py`

Following any candidate execution, the owner records the observed results in a structured report parsed by `tools/port18_trial_report.py` `[VERIFIED: tools/port18_trial_report.py:8-22]`.

### 6.1 Report Ingest Invariants
1. **Single Fenced Block Requirement**: The ingest parser extracts report content via regex `fence_pattern = re.compile(r"^```port18-report\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)` and processes **only the first fenced block in the file** `[VERIFIED: tools/port18_trial_report.py:461-465]`. Appending a second block causes it to be silently ignored.
2. **Dedicated Report Path**: Each power-on attempt must be recorded in its own dedicated file under `private/` (e.g. `private/port27/trial_report_held.md`), which is git-ignored via `.gitignore:34` `[VERIFIED: .gitignore:34]`.

### 6.2 Representative Template: Held-Press Resident Trial

Save to `private/port27/trial_report_held.md`:

```port18-report
candidate_sha256: 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
candidate_size: 124865
trial_date: 2026-11-02
card_prepared: yes
camera_behaviour: normal_stock_boot
witness_observed: yes
trace_log_present: no
trace_log_path: none
witness_dump_path: none
outcome_id: O4
notes: Held-press candidate trial: Held Power button until Canon stock UI booted; observed 7 loader blinks, transition gap, then core ladder codes 11-15, 21-26, 31-35, 41-44; LCD illuminated to stock shooting UI; rear green LED toggled at ~1 Hz continuously; short-press shutdown was not tested (out of scope per PORT-27 plan).
```

### 6.3 Host Report Ingestion Commands
To validate the report on the host:

```bash
# Validate trial report with strict schema checking
python3 -B tools/port18_trial_report.py private/port27/trial_report_held.md --strict
```
