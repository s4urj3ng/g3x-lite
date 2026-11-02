# PORT-29 T1: CreateTask Calling Convention, Parameter Roles & Stack Allocation Evidence

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-29 T1 (`p29-t1-createtask-evidence`)
- **Primary Source**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (offline host analysis; 33,554,432 bytes; base `0xFC000000`) `[VERIFIED]`
- **Baseline Context**: `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` (Section 3 UNKNOWN list), `docs/PORT28_PORT27_OUTCOME.md:143-176` (Sections 4.1–4.3), `docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`, `docs/PORT21_RAM_LIFETIME.md:33, 210, 307`
- **Output Artifacts**:
  - `evidence/port29_manifest.json` `[VERIFIED]`
  - `evidence/port29_trusted_scopes.json` `[VERIFIED]`
  - `tests/test_port29_evidence.py` `[VERIFIED]`
- **Verdict**: **NO-GO** (Parameter semantic roles and stack allocator are `[INFERRED]`; stack alignment, runtime default stack size value, and downstream descriptor consumption in unread activation callees remain `[UNKNOWN]`)

---

## 1. Executive Summary & Epistemic Standards

This dossier resolves **PORT-27 Item (b)** for Canon PowerShot G3 X firmware **GM1.10C**. All research, disassemblies, instruction traces, and cryptographic hashes in this report were performed strictly on the host workstation and offline from `firmware/dumps/GM1.10C/PRIMARY.BIN`.

### 1.1 Scope Authorization & Offline Policy Compliance
1. **Strict Read Scope Compliance**: The candidate authorized range list from `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3 and `docs/PORT28_PORT27_OUTCOME.md:143-176` Sections 4.1–4.3 comprises Slices N3–N7, the `CreateTask` body (`0xFCEF3488..0xFCEF34F9`, 114 bytes), and the two additional UNKNOWN entries (Slice N1 / `sub_fc31b408` and Item 8 non-heap RAM users), totaling 1,894 bytes (~1.9 KiB).
2. **Exclusion and Reconciliation of Unclear, Disputed, or Oversized Ranges**: In strict accordance with the task read policy ("If a range's bounds are unclear, the two docs disagree about it, or it is longer than 4 KiB, do not read it. Record it as UNKNOWN with the reason"):
   - **Slice N4** (`0xFCEEF760..0xFCEEF9C3`, 612 B): Reconciled strictly against `docs/PORT27_RESIDENT_CANDIDATE.md:59` Section 3 and `docs/PORT28_PORT27_OUTCOME.md:154, 168` (excluding `docs/PORT27_OWNER_TRIAL_PLAN.md`). Both authoritative sources agree on entry/start address `0xFCEEF760` with proposed inspection window $\le 1\text{ KiB}$. Slice N3 (`0xFCEEF5C0..0xFCEEF7BF`, 512 B) and Slice N4 (`0xFCEEF760..0xFCEEF9C3`, 612 B) share 96 bytes on `0xFCEEF760..0xFCEEF7BF`. To eliminate overlapping slices in the evidence manifest without widening any range or reading new ROM bytes, the N3 manifest entry is retained at `0xFCEEF5C0..0xFCEEF7BF` (512 B, SHA-256 `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2`), covering the 96 overlapping prefix bytes. The N4 manifest entry and its authorization scope are narrowed to the non-overlapping remainder `0xFCEEF7C0..0xFCEEF9C3` (516 B, SHA-256 `c4603dc40c67f2f563a0e41efddd4f5ac50fbaf64b5c2272263622b424eedabc`). These bytes fall strictly inside the authorized N4 window, requiring zero new reads, introducing zero slice overlaps, and requiring no bypass flags during validation.
   - **Slice N7** (`0xFCEF33A0..0xFCEF33EF`, 80 B) was **not read** due to a direct documentation disagreement on window size: `docs/PORT27_RESIDENT_CANDIDATE.md:66` strictly caps the proposed inspection window at $\le 64$ B at entry `0xFCEF33B4`, whereas `docs/PORT28_PORT27_OUTCOME.md:161, 171` defines an 80-byte range starting at `0xFCEF33A0` (exceeding the 64-byte boundary).
   - **Item 8** (Relocated Core Non-Heap RAM Users) was **not read** because its bounds are unclear (no bounded ROM address), the two documents disagree (entire 32 MiB ROM in PORT27 vs no bounded ROM location in PORT28), and the span exceeds 4 KiB (130,252 B RAM / 32 MiB ROM).
3. **Manifest and Trusted Scopes**: All 6 read slices (totaling 1,718 bytes, well within the 4,096-byte scope budget) are declared in `evidence/port29_manifest.json` and authorized under `evidence/port29_trusted_scopes.json`. Earlier port manifests were kept in `docs/agentbridge/` (e.g. `docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json`) or `tests/fixtures/` (`port11a_manifest.json`), while PORT-29 places `port29_manifest.json` and `port29_trusted_scopes.json` under `evidence/` as mandated by the task specification.
4. **No Firmware Flashing or Hardware Access**: No physical camera hardware was connected, no SD card was modified, no binary payloads or build outputs were created, and zero ROM bytes were committed `[VERIFIED: docs/SAFETY.md:3-8; AGENTS.md:18-24]`.

### 1.2 Evidence Validator Execution & Output
The machine-readable evidence manifest was verified using `tools/port11c_evidence_validator.py` with no extra flags:

```bash
python3 -B tools/port11c_evidence_validator.py --manifest evidence/port29_manifest.json --trusted-scopes evidence/port29_trusted_scopes.json
```

**Exact Quoted Validator Output**:
```
Evidence Manifest Validation: 6 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED
----------------------------------------------------------------------
----------------------------------------------------------------------
Result: VALID (0 errors, 0 warnings)
```

### 1.3 Instruction Word Notation Convention
All ARM Thumb and Thumb-2 instructions cited throughout this document use explicit 16-bit Thumb halfwords in `0xHHHH` form (hexadecimal, 4 uppercase hex digits preceded by `0x`). 32-bit Thumb-2 instructions are written as two 16-bit halfwords in execution order (first halfword followed by second halfword, e.g. `0xF7FF 0xEA02` for `blx 0xBFE13E78` at `0xFCEF34BE`, or `0xE92D 0x43FE` for `push.w {r1-r8, sb, lr}` at `0xFCEF3488`). All cited instruction words are re-derived directly from the bytes read inside the authorized ROM ranges.

---

## 2. Authorized ROM Ranges Evaluation Table

The table below catalogs every range in the candidate authorized range list from `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3 and `docs/PORT28_PORT27_OUTCOME.md:143-176` Sections 4.1–4.3, detailing source doc citations, start and end addresses, byte spans, SHA-256 cryptographic hashes, and read status (`READ` or `UNKNOWN-not-read`).

In `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3, nine entries are enumerated:
- Rows 1, 2, 3, 5/6, 9 correspond to Slices N3, N4, N5, N6, N7.
- Row 4 is the `CreateTask` body `0xFCEF3488..0xFCEF34F9` (114 B).
- The two other UNKNOWN entries listed there are Row 7 (Heap alignment `sub_fc31b408` / Slice N1 at `0xFC31B408..0xFC31B507`, 256 B) and Row 8 (Relocated Core Non-Heap RAM users, 130,252 B RAM, unread due to >4 KiB size and lack of a bounded ROM address).

| Range ID | Target Routine / Subsystem | Source Citation (Doc:Line) | Start Address | End Address | Length (Bytes) | SHA-256 Digest | Status | Policy Compliance & Epistemic Reasoning |
|---|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **PORT29-ROM-N1** | `sub_fc31b408` Heap Init & Veneer Table | `docs/PORT27_RESIDENT_CANDIDATE.md:64`; `docs/PORT28_PORT27_OUTCOME.md:159, 165` | `0xFC31B408` | `0xFC31B507` | 256 B | `b93e3f48ab31f467e9ee3f4ba907ea3032a3a81cac4fe1ff18a2c0ba138181ce` | **`READ`** | Bounded ($\le 4\text{ KiB}$), both docs agree on start `0xFC31B408` and length 256 B; non-overlapping. Authorized under Item (a) kernel init. Provides zero calling convention evidence for Item (b); no CreateTask claim relies on it. |
| **PORT29-ROM-N3** | `alloc_task_stack_tcb` Task Allocator Body | `docs/PORT27_RESIDENT_CANDIDATE.md:58`; `docs/PORT28_PORT27_OUTCOME.md:153, 167` | `0xFCEEF5C0` | `0xFCEEF7BF` | 512 B | `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2` | **`READ`** | Bounded ($\le 4\text{ KiB}$); captures `0xBFE10B88` body (160 B) and task parameter setup; also covers the 96 overlapping prefix bytes (`0xFCEEF760..0xFCEEF7BF`) containing the `activate_task` body. |
| **PORT29-ROM-N4** | `activate_task` Task Activation Remainder | `docs/PORT27_RESIDENT_CANDIDATE.md:59`; `docs/PORT28_PORT27_OUTCOME.md:154, 168` | `0xFCEEF7C0` | `0xFCEEF9C3` | 516 B | `c4603dc40c67f2f563a0e41efddd4f5ac50fbaf64b5c2272263622b424eedabc` | **`READ`** | Bounded ($\le 4\text{ KiB}$); authorized start is `0xFCEEF760` (full authorized window `0xFCEEF760..0xFCEEF9C3`, 612 B). The 96 overlapping prefix bytes (`0xFCEEF760..0xFCEEF7BF`) are covered by the N3 manifest entry's hash (`PORT29-ROM-N3`). To eliminate overlap in the manifest, the N4 manifest entry is narrowed to the remainder `0xFCEEF7C0..0xFCEEF9C3` (516 B). Any N4 instruction cited below `0xFCEEF7C0` (e.g. `0xFCEEF764`, `0xFCEEF76C`, `0xFCEEF77C`, `0xFCEEF79A`) cites the N3 manifest entry as its hash coverage. |
| **PORT29-ROM-N5** | `DebugAssert` Kernel Panic Handler Veneer Table | `docs/PORT27_RESIDENT_CANDIDATE.md:60`; `docs/PORT28_PORT27_OUTCOME.md:155, 169` | `0xFCEF28B0` | `0xFCEF29AF` | 256 B | `93c956e9d994888fc228997a65d0785901a4c23e0921c5e3cf6befa450fb2142` | **`READ`** | Bounded ($\le 4\text{ KiB}$); covers `0xBFE13E78` veneer target vector; both docs agree on $\le 256$ B window. |
| **PORT29-ROM-CREATETASK** | `CreateTask` Body & Calling Convention | `docs/PORT27_RESIDENT_CANDIDATE.md:61`; `docs/PORT28_PORT27_OUTCOME.md:147` | `0xFCEF3488` | `0xFCEF34F9` | 114 B | `6d7fbecb5f9589cc34994a63ac6cf7e2def132a7c355a789a29ea3cae8c50ddf` | **`READ`** | Bounded ($\le 4\text{ KiB}$); exact 114-byte extent confirmed by terminating epilogue branch; both docs agree. |
| **PORT29-ROM-N6** | ATCM Interrupt Disable & Restore Veneers | `docs/PORT27_RESIDENT_CANDIDATE.md:62-63`; `docs/PORT28_PORT27_OUTCOME.md:157-158, 170` | `0xFCEF3A20` | `0xFCEF3A5F` | 64 B | `3bf663507211b96500c59647e3f065cff96d111421ee5a2c867c022536c45969` | **`READ`** | Bounded ($\le 4\text{ KiB}$); covers `0xBFE14FE6` and `0xBFE14FEA` branch trampolines; both docs agree on 64 B. |
| **PORT29-ROM-N7** | `SleepTask` Body & Millisecond Scaling | `docs/PORT27_RESIDENT_CANDIDATE.md:66`; `docs/PORT28_PORT27_OUTCOME.md:161, 171` | `0xFCEF33A0` | `0xFCEF33EF` | 80 B | N/A | **`UNKNOWN-not-read`** | Disagreement between source docs on bounds: `docs/PORT27_RESIDENT_CANDIDATE.md:66` specifies window $\le 64$ B at `0xFCEF33B4`, whereas `docs/PORT28_PORT27_OUTCOME.md:161` specifies 80 B at `0xFCEF33A0` ($80 > 64$). |
| **PORT29-ROM-RAMUSERS** | Relocated Core Non-Heap RAM Users | `docs/PORT27_RESIDENT_CANDIDATE.md:65`; `docs/PORT28_PORT27_OUTCOME.md:160, 176` | `0x003489B4` (RAM) / `0xFC000000` (ROM) | `0x00368680` (RAM) / `0xFDFFFFFF` (ROM) | 130,252 B (RAM) / 32 MiB (ROM) | N/A | **`UNKNOWN-not-read`** | Exceeds 4 KiB limit (130,252 B RAM / 32 MiB ROM); bounds unclear; docs disagree (entire 32 MiB ROM in PORT27 vs no bounded ROM location in PORT28). |

---

## 3. Disassembly & Calling Convention: Roles of `r0`, `r1`, `r2`, and `sp[0]`

The primary entry point for DryOS task creation in stock firmware GM1.10C is `_CreateTask`, invoked by callers through the ARM kernel veneer `sub_fc31bbc4` at `0xFC31BBC4` (`ldr pc, [pc, #-4]` -> `.word 0xBFE14A3D`). Bit 0 of the target vector selects **Thumb execution** at ATCM RAM instruction address `0xBFE14A3C`, which maps to ROM source range `0xFCEF3488..0xFCEF34F9` via the early boot copy loop at `0xFC020040..0xFC020052` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`):
$$\text{ROM} = 0\text{xFCEEF24C} + (\text{ATCM} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + (0\text{xBFE14A3C} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF3488}}$$

The complete function body spans exactly **114 bytes** (`0x72` B), from `0xFCEF3488` to `0xFCEF34F9`.

```
========================================================================================
CreateTask Entry Frame & Argument Register State at 0xFCEF3488 (ATCM 0xBFE14A3C):
----------------------------------------------------------------------------------------
Register  Incoming Value at Entry           Literally Verified Action & Semantic Role
----------------------------------------------------------------------------------------
r0        First Argument (Candidate Name)   Moved to r4; if r0 == 0, loads fallback *(r1);
                                            stored to stack-frame offset [sp, #24] /
                                            descriptor offset [desc, #20] (desc = sp + 4) [VERIFIED].
                                            Semantic role as name string pointer [INFERRED].
r1        Second Argument (INFERRED: prio)  Moved to r6; checked (r1 - 1) < 0x20 else error branch;
                                            byte stored at stack-frame offset [sp, #29] /
                                            descriptor offset [desc, #25] (desc = sp + 4;
                                            INFERRED: priority) [VERIFIED].
                                            Semantic role as scheduling priority [INFERRED].
r2        Third Argument (Candidate Stack)  Moved to r5; if r2 == 0, loads fallback *(r1 + 4);
                                            forwarded as parameter to 0xBFE10B88; stored to
                                            stack-frame offset [sp, #20] / descriptor offset
                                            [desc, #16] (desc = sp + 4) [VERIFIED].
                                            Literal pool address 0xFCEF36A0 unread [INFERRED: PORT11A].
                                            Semantic role as stack size in bytes [INFERRED].
r3        Fourth Argument (INFERRED: entry) Checked r3 != 0 else error branch; stored to
                                            stack-frame offset [sp, #8] / descriptor offset
                                            [desc, #4] (desc = sp + 4) [VERIFIED].
                                            Semantic role as entry point [INFERRED].
sp[0]     Fifth Argument (Candidate Context)Loaded from caller stack [sp, #0x28]; forwarded
                                            to stack-frame offset [sp, #12] / descriptor offset
                                            [desc, #8] (desc = sp + 4) [VERIFIED].
                                            Semantic delivery to spawned task [INFERRED].
========================================================================================
```

### 3.1 Role of `r0`: Forwarding and Descriptor Storage `[VERIFIED]` / Name String Interpretation `[INFERRED]`
- **ROM Address**: `0xFCEF348C` (File Offset `0x00EF348C`, ATCM VMA `0xBFE14A40`)
- **Instruction Word**: `0x4604` (16-bit Thumb)
- **Disassembly**: `mov r4, r0`
- **Technical Reasoning**:
  1. At entry, `CreateTask` executes `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` at `0xFCEF3488` (`0xE92D 0x43FE`), allocating 40 bytes (`0x28` B) on the stack and preserving caller registers `[VERIFIED]`.
  2. At `0xFCEF348C`, `mov r4, r0` (instruction word `0x4604`) moves incoming `r0` into callee-saved register `r4` `[VERIFIED]`.
  3. At `0xFCEF34AA` (`0x497D`), `ldr r1, [pc, #0x1f4]` executes PC-relative load. The target literal word is located at $\text{Align}(0\text{xFCEF34AA} + 4, 4) + 0\text{x1f4} = 0\text{xFCEF34AC} + 0\text{x1f4} = 0\text{xFCEF36A0}$ (ATCM `0xBFE14C54`). Because `0xFCEF36A0` lies outside all manifest read ranges, the literal value `0x000081CC` cannot be verified from read slices; it is **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144]`**.
  4. At `0xFCEF34AC` (`0xB904`), `cbnz r4, 0xbfe14a64` inspects `r4`. If `r4 != 0`, caller value is preserved. If `r4 == 0`, instruction `0xFCEF34AE` (`0x680C`) executes `ldr r4, [r1]`, substituting the default pointer stored at `*(uint32_t *)r1` `[VERIFIED]`.
  5. At `0xFCEF34D4` (`0x9402`), `str r4, [sp, #8]` passes `r4` on the stack to internal routine `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` (`0xFCEEF5D4` / `0xBFE10B88`), after allocating a 56-byte stack frame (`stmdb sp!` 24 B + `sub sp, #32`), instruction `0xBFE10B8E` (ROM `0xFCEEF5DA`, `0xE9DD 0x780F`) executes `ldrd r7, r8, [sp, #60]`, retrieving `r8` from stack-frame offset `sp + 64` (corresponding to caller's `sp + 8`).
  - At `0xBFE10BF4` (ROM `0xFCEEF640`, `0xA801`: `add r0, sp, #4`), `alloc_task_stack_tcb` sets up the descriptor pointer passed in `r0` to `0xBFE11746`, defining descriptor base `desc = sp + 4`. At `0xBFE10BF6` (ROM `0xFCEEF642`, `0xF8CD 0x8018`: `str.w r8, [sp, #24]`), it stores this pointer into stack-frame offset `sp + 24`, corresponding to descriptor offset `desc + 20` (`desc = sp + 4`) `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B984`: `ldr r0, [pc, #0x18]` loads `r0 = 0xFC05B9A0`, pointing to literal string `"init_task\0"` `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:144-155 / docs/PORT11A_GM110C_ROM_EVIDENCE.md:104-108]`.
- **Status Summary**:
  - Register forwarding, null check, fallback dereference, and descriptor store at stack-frame offset `sp + 24` / descriptor offset `desc + 20`: **`[VERIFIED]`**.
  - Semantic interpretation as null-terminated ASCII task name string: **`[INFERRED]`** (consumer at `0xBFE11746` unread).

### 3.2 Role of `r1`: Range Check and Descriptor Storage `[VERIFIED]` / Priority Interpretation `[INFERRED]`
- **ROM Address**: `0xFCEF3490` (File Offset `0x00EF3490`, ATCM VMA `0xBFE14A44`)
- **Instruction Word**: `0x460E` (16-bit Thumb)
- **Disassembly**: `mov r6, r1`
- **Technical Reasoning**:
  1. At `0xFCEF3490`, `mov r6, r1` (instruction word `0x460E`) transfers incoming `r1` into callee-saved register `r6` `[VERIFIED]`.
  2. At `0xFCEF34B0` (`0x1E70`), `subs r0, r6, #1` decrements `r6` by 1 into `r0` `[VERIFIED]`.
  3. At `0xFCEF34B2` (`0x2820`), `cmp r0, #0x20` compares `r6 - 1` against unsigned integer `32` (`0x20`) `[VERIFIED]`.
  4. At `0xFCEF34B4` (`0xD200`), `bhs 0xbfe14a6c` takes an error branch if `r0 >= 32` (unsigned), strictly enforcing that incoming `r1` must satisfy $0 \le (r1 - 1) < 32$, which is mathematically equivalent to:
     $$1 \le r1 \le 32$$
  5. If `r1` is outside $1..32$, execution branches to `0xFCEF34B8`:
     - `0xFCEF34B8` (`0x22A0`): `movs r2, #0xa0` (loads integer literal 160) `[VERIFIED]`.
     - `0xFCEF34BA` (`0x2000`): `movs r0, #0` `[VERIFIED]`.
     - `0xFCEF34BC` (`0xA17A`): `adr r1, #0x1e8`.
       The ADR instruction word `0xA17A` computes:
       $$\text{Target ROM} = \text{Align}(0\text{xFCEF34BC} + 4, 4) + 0\text{x1E8} = 0\text{xFCEF34C0} + 0\text{x1E8} = \mathbf{0\text{xFCEF36A8}}$$
       In ATCM VMA space (where `0xFCEF34BC` maps to ATCM `0xBFE14A70`):
       $$\text{Target ATCM} = \text{Align}(0\text{xBFE14A70} + 4, 4) + 0\text{x1E8} = 0\text{xBFE14A74} + 0\text{x1E8} = \mathbf{0\text{xBFE14C5C}}$$
       The address computation $\text{ROM } 0\text{xFCEF36A8} \iff \text{ATCM } 0\text{xBFE14C5C}$ is **`[VERIFIED]`**.
     - `0xFCEF34BE..0xFCEF34C1` (`0xF7FF 0xEA02`): `blx 0xBFE13E78` branches to error handler veneer in Slice N5 `[VERIFIED]`.
     - `0xFCEF34C2` (`0x2003`): `movs r0, #3`, returning error code 3 `[VERIFIED: instructions, branch conditions, register arguments, and control flow]`.
     - Because address `0xFCEF36A8` (ATCM `0xBFE14C5C`) lies outside authorized read ranges, what is stored at `0xFCEF36A8` was not read; any meaning taken from it as an assertion source file string (such as `"KerTask.c"` known from `docs/PORT11A_GM110C_ROM_EVIDENCE.md:147, 187`) or interpretation of literal `160` as a source line number is **`[INFERRED]`**, and the semantic identification of handler `0xBFE13E78` as `DebugAssert` is **`[INFERRED]`**.
  6. If valid, at `0xFCEF34D6` (`0xE9CD 0x6200`), `strd r6, r2, [sp]` stores `r6` at `[sp]` and `r2` (`0`) at `[sp, #4]` for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10B92` (ROM `0xFCEEF5DE`, `0x9C0E`), `ldr r4, [sp, #56]` loads `r4` from caller's `[sp]` (retrieving `r6`).
  - At `0xBFE10BA6` (ROM `0xFCEEF5F2`, `0x2C00`), `cmp r4, #0`; at `0xBFE10BA8` (ROM `0xFCEEF5F4`, `0xDB3A`), `blt 0xbfe10c20` verifies value is non-negative `[VERIFIED]`.
  - At `0xBFE10BAA` (ROM `0xFCEEF5F6`, `0x4DF0`: `ldr r5, [pc, #960]`), `0xBFE10BAC` (ROM `0xFCEEF5F8`, `0x682D`: `ldr r5, [r5]`), `0xBFE10BAE` (ROM `0xFCEEF5FA`, `0x42AC`: `cmp r4, r5`), and `0xBFE10BB0` (ROM `0xFCEEF5FC`, `0xDA36`: `bge 0xbfe10c20`), execution compares `r4` against the value loaded through pointer `[pc, #960]`, branching to error block `0xBFE10C20` if `r4 >= r5` `[VERIFIED: compare instruction, branch condition, and control flow]`. The target literal is located at $\text{Align}(0\text{xBFE10BAA} + 4, 4) + 960 = 0\text{xBFE10BAC} + 0\text{x3C0} = 0\text{xBFE10F6C}$, which maps in ROM via the early boot copy loop formula to $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE10F6C} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEEF9B8}}$. This literal pool word lies inside the read and hash-verified Slice N4 range (`0xFCEEF7C0..0xFCEEF9C3`, covered by manifest entry `PORT29-ROM-N4`) and holds the 32-bit literal pointer value `0x000080F0` (halfwords `0x80F0 0x0000`) `[VERIFIED]`. The runtime RAM contents at Low RAM address `0x000080F0` are `[UNKNOWN]`. Its semantic role (as pointing to an active task limit or system configuration variable) is `[INFERRED]`.
  - At `0xBFE10BEC` (ROM `0xFCEEF638`, `0xF88D 0x401D`), `strb.w r4, [sp, #29]` writes the byte stored at `desc + 25` (`sp + 29`, with `desc = sp + 4`; INFERRED: priority) of the task control block descriptor `[VERIFIED: byte store at desc+25; semantic role as task priority is INFERRED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B98A`: `movs r1, #25` (passes 25, within verified $1..32$ bounds) `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:147]`.
- **Status Summary**:
  - Range check `(r1 - 1) < 0x20` ($1 \le r1 \le 32$) else error branch, register forwarding, and byte stored at `desc + 25` (`sp + 29`, with `desc = sp + 4`; INFERRED: priority): **`[VERIFIED: instructions and data flow]`**; semantic role of target routine as `DebugAssert` and byte role as scheduling priority: **`[INFERRED]`**.
  - Semantic interpretation as task scheduling priority: **`[INFERRED]`** (consumer at `0xBFE11746` and scheduler unread).

### 3.3 Role of `r2`: Argument Forwarding and Default Load `[VERIFIED]` / Stack Size Interpretation `[INFERRED]`
- **ROM Address**: `0xFCEF3492` (File Offset `0x00EF3492`, ATCM VMA `0xBFE14A46`)
- **Instruction Word**: `0x4615` (16-bit Thumb)
- **Disassembly**: `mov r5, r2`
- **Technical Reasoning**:
  1. At `0xFCEF3492`, `mov r5, r2` (instruction word `0x4615`) preserves incoming `r2` in callee-saved register `r5` `[VERIFIED]`.
  2. At `0xFCEF34C8` (`0xB905`), `cbnz r5, 0xbfe14a80` evaluates `r5`. If `r5 != 0`, execution branches directly to `0xBFE14A80`, preserving the explicit value passed by caller `[VERIFIED]`.
  3. At `0xFCEF34CA` (`0x684D`), `ldr r5, [r1, #4]` executes if `r5 == 0`. Register `r1` holds the base pointer loaded at `0xFCEF34AA`. In historical documentation `docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164`, literal pool entry `0xFCEF36A0` was documented as `0x000081CC`, making `[r1, #4]` access `0x000081CC + 4 = 0x000081D0`. Because literal `0xFCEF36A0` is unread in PORT-29, the literal value `0x000081CC` and default address `0x000081D0` are **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164]`**.
  4. At `0xFCEF34D2` (`0x462B`), `mov r3, r5` moves the resolved value into register `r3` as parameter 4 for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10B94` (ROM `0xFCEEF5E0`, `0xB90B`), `cbnz r3, 0xbfe10b9a` verifies that `r3` is non-zero `[VERIFIED]`.
  - At `0xBFE10B96` (ROM `0xFCEEF5E2`, `0x4BF3`: `ldr r3, [pc, #972]`) and `0xBFE10B98` (ROM `0xFCEEF5E4`, `0x681B`: `ldr r3, [r3]`), secondary fallback is provided if `r3 == 0` `[VERIFIED]`.
  - At `0xBFE10BD6` (ROM `0xFCEEF622`, `0xA803`: `add r0, sp, #12`), `alloc_task_stack_tcb` sets `r0 = sp + 12`; then at `0xBFE10BD8` (ROM `0xFCEEF624`, `0xC00E`: `stmia r0!, {r1, r2, r3}`), it writes `{r1, r2, r3}` sequentially into stack-frame offsets `sp + 12`, `sp + 16`, and `sp + 20`. Parameter `r3` (forwarded from `r2` / default load; INFERRED: default stack size) is thus written into stack-frame offset `sp + 20`, corresponding to descriptor offset `desc + 16` (`desc = sp + 4`) of the task creation parameter block passed to internal kernel allocator `0xBFE11746` `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B988`: `movs r2, #0` (passes 0 to trigger default load) `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:146]`.
  - In `task_InitFileModules` creator `sub_fc0bd0b4` (`PORT11A-S2A`) at `0xFC0BD0CC`: `mov.w r2, #0x1000` (passes explicit non-zero value 4,096) `[INFERRED: historical corroboration, citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:158]`.
- **Status Summary**:
  - Argument forwarding, non-zero bypass, `r2 == 0` fallback load from `[r1, #4]`, and store to stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`desc = sp + 4`): **`[VERIFIED]`**.
  - Literal pool word `0x000081CC` at `0xFCEF36A0` and default address `0x000081D0`: **`[INFERRED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164]`**.
  - Semantic interpretation as stack size in bytes: **`[INFERRED]`** (consumer at `0xBFE11746` unread).
  - Runtime numeric integer value at `*(0x000081D0)`: **`[UNKNOWN]`**.

### 3.4 Role of `sp[0]`: Stack Parameter Retrieval and Forwarding `[VERIFIED]` / Task Context Delivery `[INFERRED]`
- **ROM Address**: `0xFCEF3494` (File Offset `0x00EF3494`, ATCM VMA `0xBFE14A48`)
- **Instruction Word**: `0xF8DD 0x8028` (32-bit Thumb-2)
- **Disassembly**: `ldr.w r8, [sp, #0x28]`
- **Technical Reasoning**:
  1. At entry `0xFCEF3488`, `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` decrements the stack pointer by exactly 40 bytes (`0x28` B) `[VERIFIED]`.
  2. Under AAPCS conventions, arguments beyond the fourth (`r0`–`r3`) are placed by the caller on the stack starting at `sp[0]`.
  3. At `0xFCEF3494`, `ldr.w r8, [sp, #0x28]` (instruction word `0xF8DD 0x8028`) reads 32 bits from `sp_current + 0x28`, corresponding precisely to `sp_entry + 0x00` (caller's 5th argument passed on stack). The word is loaded into callee-saved register `r8` `[VERIFIED]`.
  4. At `0xFCEF34CE` (`0x4641`), `mov r1, r8` transfers `r8` into `r1` as argument 2 for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10BD6` (ROM `0xFCEEF622`, `0xA803`: `add r0, sp, #12`) and `0xBFE10BD8` (ROM `0xFCEEF624`, `0xC00E`: `stmia r0!, {r1, r2, r3}`), incoming `r1` (caller's `sp[0]`) is written into stack-frame offset `sp + 12`, corresponding to descriptor offset `desc + 8` (`desc = sp + 4`) of the parameter block passed to `0xBFE11746` `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B980..0xFC05B982`: `movs r3, #0`; `str r3, [sp, #0]` (places 0 at `sp[0]`) `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:145]`.
- **Status Summary**:
  - Retrieval of 5th parameter from caller stack `sp[0]` and forwarding into stack-frame offset `sp + 12` / descriptor offset `desc + 8` (`desc = sp + 4`): **`[VERIFIED]`**.
  - Semantic delivery to spawned task function as user context argument: **`[INFERRED]`** (consumer at `0xBFE11746` and task dispatcher unread).

### 3.5 Corroborating Role of `r3`: Non-Null Check and Entry Forwarding `[VERIFIED]` / Execution Role `[INFERRED]`
- **ROM Address**: `0xFCEF3498` (File Offset `0x00EF3498`, ATCM VMA `0xBFE14A4C`)
- **Instruction Word**: `0x461F` (16-bit Thumb)
- **Disassembly**: `mov r7, r3`
- **Technical Reasoning**:
  1. At `0xFCEF3498`, `mov r7, r3` (instruction word `0x461F`) preserves incoming `r3` in callee-saved register `r7` `[VERIFIED]`.
  2. At `0xFCEF34B6` (`0xB93F`), `cbnz r7, 0xbfe14a7c` checks whether `r7` is non-zero. If `r7 == 0`, execution falls through to error path `0xFCEF34B8`: `movs r2, #0xa0` (`0x22A0`), `movs r0, #0` (`0x2000`), `adr r1, #0x1e8` (instruction word `0xA17A` at `0xFCEF34BC`, computing $\text{Align}(0\text{xFCEF34BC} + 4, 4) + 0\text{x1E8} = 0\text{xFCEF36A8}$, ATCM `0xBFE14C5C`), and `blx 0xBFE13E78` (`0xF7FF 0xEA02`), returning error code 3 at `0xFCEF34C2` (`0x2003`) `[VERIFIED: branch condition and instructions; address computation 0xFCEF36A8 / ATCM 0xBFE14C5C is VERIFIED; contents at 0xFCEF36A8 and semantic role of 0xBFE13E78 as DebugAssert and literal 0xa0 as source line 160 are INFERRED]`.
  3. At `0xFCEF34D0` (`0x4638`), `mov r0, r7` passes the function pointer in `r0` to `0xBFE10B88` `[VERIFIED]`.
  4. In `alloc_task_stack_tcb` at `0xBFE10BD2` (ROM `0xFCEEF61E`, `0xE9CD 0x6001`), `strd r6, r0, [sp, #4]` writes `r0` (task entry function pointer) into stack-frame offset `sp + 8`, corresponding to descriptor offset `desc + 4` (`desc = sp + 4`) of the task descriptor `[VERIFIED]`.
- **Status Summary**:
  - Check `r3 != 0` else error branch, register forwarding, and descriptor store at stack-frame offset `sp + 8` / descriptor offset `desc + 4`: **`[VERIFIED: instructions and flow; semantic role as task entry point and callee role as DebugAssert are INFERRED]`**.
  - Execution as spawned task main entry point: **`[INFERRED]`** (consumer at `0xBFE11746` and task dispatcher unread).

### 3.6 Role of Task Activation Helper `activate_task` (`0xBFE10D14` / `0xFCEEF760`, Slice N4)
- **ROM Address Range**: Authorized window `0xFCEEF760..0xFCEEF9C3` (612 B; ATCM VMA `0xBFE10D14..0xBFE10F77`). The function body spans `0xFCEEF760..0xFCEEF7A2` (68 B), which falls in the 96-byte prefix `0xFCEEF760..0xFCEEF7BF` covered by manifest entry `PORT29-ROM-N3` (`0xFCEEF5C0..0xFCEEF7BF`, SHA-256 `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2`). The literal pool spans `0xFCEEF9B8..0xFCEEF9C3`, covered by manifest entry `PORT29-ROM-N4` (`0xFCEEF7C0..0xFCEEF9C3`, SHA-256 `c4603dc40c67f2f563a0e41efddd4f5ac50fbaf64b5c2272263622b424eedabc`).
- **Key Instruction Words & Manifest Hash Coverage**:
  - `0xFCEEF760`: `0xB538` (`push {r3, r4, r5, lr}`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF762`: `0x4605` (`mov r5, r0`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF764`: `0xF04F 0x34FF` (`mov.w r4, #0xFFFFFFFF`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF768`: `0x1C40` (`adds r0, r0, #1`); `0xFCEEF76A: 0xD101` (`bne 0xFCEEF770`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF76C`: `0x4620` (`mov r0, r4`); `0xFCEEF76E: 0xBD38` (`pop {r3, r4, r5, pc}`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF770`: `0x4668` (`mov r0, sp`); `0xFCEEF772..775: 0xF003 0xE8C4` (`blx 0xFCEF28FC`, callee in Slice N5; INFERRED: take kernel lock) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF776`: `0x4628` (`mov r0, r5`); `0xFCEEF778..77B: 0xF000 0xFC81` (`bl 0xFCEF007E`, callee outside slices; INFERRED: TCB pointer lookup) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF77C`: `0xB170` (`cbz r0, 0xFCEEF79C`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF77E`: `0x4990` (`ldr r1, [pc, #0x240]`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF780`: `0x6809` (`ldr r1, [r1, #0]`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF782`: `0xB939` (`cbnz r1, 0xFCEEF794`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF784`: `0x498D` (`ldr r1, [pc, #0x234]`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF786`: `0x6809` (`ldr r1, [r1, #0]`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF788`: `0xF991 0x104B` (`ldrsb.w r1, [r1, #0x4b]`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF78C`: `0x2900` (`cmp r1, #0`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF78E`: `0xDC01` (`bgt 0xFCEEF794`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF790`: `0x2101` (`movs r1, #1`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF792`: `0xE000` (`b 0xFCEEF796`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF794`: `0x2100` (`movs r1, #0`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF796`: `0xF7FF 0xFE4F` (`bl 0xFCEEF438`, callee outside slices; INFERRED: enqueue / activate task) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF79A`: `0x2400` (`movs r4, #0`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF79C`: `0x9800` (`ldr r0, [sp, #0]`); `0xFCEEF79E..7A1: 0xF003 0xE8B2` (`blx 0xFCEF2904`, callee in Slice N5; INFERRED: release kernel lock) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF7A2`: `0xE7E3` (`b 0xFCEEF76C` -> `mov r0, r4`; `pop {r3, r4, r5, pc}`) `[Hash coverage: PORT29-ROM-N3]`
  - `0xFCEEF9B8..0xFCEEF9C3`: Literal pool holding Low RAM pointer literals `0x000080F0` (at `0xFCEEF9B8`, words `0x80F0 0x0000`), `0x0000803C` (at `0xFCEEF9BC`, words `0x803C 0x0000`), and `0x00008040` (at `0xFCEEF9C0`, words `0x8040 0x0000`) `[Hash coverage: PORT29-ROM-N4]`. The literal values stored in ROM are `[VERIFIED]`; the runtime RAM contents at these Low RAM addresses are `[UNKNOWN]`; their semantic roles are `[INFERRED]`.
- **Technical Reasoning & Observed Return Outcomes**:
  1. `CreateTask` invokes `activate_task` at `0xFCEF34F2` (`0xF7FC 0xF935`: `bl 0xBFE10D14`, ATCM `0xBFE14AA6`) immediately after `alloc_task_stack_tcb` returns `[VERIFIED]`.
  2. The only argument passed to `activate_task` in `r0` is the task ID/handle returned by `alloc_task_stack_tcb` `[VERIFIED]`.
  3. Every observed return outcome is documented and labeled separately with exact citations:
     - **Default error register setup**: At `0xFCEEF764`, `0xF04F 0x34FF` executes `mov.w r4, #0xFFFFFFFF`, initializing `r4 = -1` `[VERIFIED: covered by manifest entry PORT29-ROM-N3]`.
     - **Input of -1 return outcome (Returns -1)**: If caller passes invalid task handle `r0 = -1` (`0xFFFFFFFF`), instruction `0xFCEEF768` (`0x1C40`: `adds r0, r0, #1`) evaluates to 0 and sets the Z flag. Consequently, conditional branch `0xFCEEF76A` (`0xD101`: `bne 0xFCEEF770`) is not taken. Execution falls through directly to `0xFCEEF76C` (`0x4620`: `mov r0, r4`), which moves `r4` (`-1`) into return register `r0`, and `0xFCEEF76E` (`0xBD38`: `pop {r3, r4, r5, pc}`) returns `-1` to caller `[VERIFIED: branch condition, register values, and return path; covered by manifest entry PORT29-ROM-N3]`.
     - **Null-result return outcome (Returns -1)**: If input `r0 != -1`, branch `bne 0xFCEEF770` is taken, acquiring the kernel lock at `0xFCEEF772` (`0xF003 0xE8C4`: `blx 0xFCEF28FC`), restoring `r0 = r5` (input handle) at `0xFCEEF776` (`0x4628`: `mov r0, r5`), and calling routine `0xFCEF007E` at `0xFCEEF778` (`0xF000 0xFC81`: `bl 0xFCEF007E`, unread callee; INFERRED: TCB pointer lookup). If `0xFCEF007E` returns `r0 == 0` (null result), instruction `0xFCEEF77C` (`0xB170`: `cbz r0, 0xFCEEF79C`) branches to `0xFCEEF79C` to release the lock (`0xF003 0xE8B2`: `blx 0xFCEF2904`) and branches at `0xFCEEF7A2` (`0xE7E3`: `b 0xFCEEF76C`) to `0xFCEEF76C`. At `0xFCEEF76C`, `0x4620`: `mov r0, r4` executes with `r4` still holding `-1` (unmodified since `0xFCEEF764`), returning `-1` to caller `[VERIFIED: branch conditions, register preservation, and return value -1; covered by manifest entry PORT29-ROM-N3; callee semantic roles INFERRED]`.
     - **Success return outcome (Returns 0)**: If `0xFCEF007E` returns a non-null pointer (`r0 != 0`), execution proceeds past `0xFCEEF77C` to `0xFCEEF796` (`0xF7FF 0xFE4F`: `bl 0xFCEEF438`, unread callee; INFERRED: enqueue / activate task). Execution then reaches `0xFCEEF79A` (`0x2400`: `movs r4, #0`), which explicitly sets `r4 = 0`. At `0xFCEEF79C`, it releases the lock (`0xF003 0xE8B2`: `blx 0xFCEF2904`) and branches at `0xFCEEF7A2` (`0xE7E3`: `b 0xFCEEF76C`) to `0xFCEEF76C`, executing `0x4620`: `mov r0, r4` to return status code `0` to caller `[VERIFIED: instruction sequence, register assignments, and return value 0; covered by manifest entry PORT29-ROM-N3; callee semantic roles INFERRED]`.
  4. **Data-Flow Analysis across `0xFCEEF77E..0xFCEEF79C`**:
     The table below details every instruction in the sequence `0xFCEEF77E..0xFCEEF79C` (covered by manifest entry `PORT29-ROM-N3`), showing the local manipulation of `r1` and stack slot `sp[0]`:

     | ROM Address | Instruction Word(s) | Disassembly | Architectural & Data-Flow Effect | Epistemic Status |
     |:---:|:---:|---|---|:---:|
     | `0xFCEEF77E` | `0x4990` | `ldr r1, [pc, #0x240]` | PC-relative literal load from $\text{Align}(0\text{xFCEEF77E}+4, 4) + 0\text{x240} = 0\text{xFCEEF9C0}$, loading Low RAM address `0x00008040` into `r1`. Overwrites any prior content in register `r1`. | `[VERIFIED: instruction in Slice N3, literal word in N4]` |
     | `0xFCEEF780` | `0x6809` | `ldr r1, [r1, #0]` | Dereferences `r1`, loading 32-bit word from Low RAM address `0x00008040` into `r1`. | `[VERIFIED]` |
     | `0xFCEEF782` | `0xB939` | `cbnz r1, 0xFCEEF794` | Evaluates `r1`; if non-zero (`r1 != 0`), branches to `0xFCEEF794` (bypassing secondary check and setting local `r1 = 0`). | `[VERIFIED]` |
     | `0xFCEEF784` | `0x498D` | `ldr r1, [pc, #0x234]` | PC-relative literal load from $\text{Align}(0\text{xFCEEF784}+4, 4) + 0\text{x234} = 0\text{xFCEEF9BC}$, loading Low RAM address `0x0000803C` into `r1`. | `[VERIFIED: instruction in Slice N3, literal word in N4]` |
     | `0xFCEEF786` | `0x6809` | `ldr r1, [r1, #0]` | Dereferences `r1`, loading 32-bit word from Low RAM address `0x0000803C` into `r1`. | `[VERIFIED]` |
     | `0xFCEEF788` | `0xF991 0x104B` | `ldrsb.w r1, [r1, #0x4B]` | Loads signed byte from structure offset `[r1, #0x4B]` into `r1` (sign-extended to 32 bits). | `[VERIFIED]` |
     | `0xFCEEF78C` | `0x2900` | `cmp r1, #0` | Compares signed byte in `r1` against immediate `0`. | `[VERIFIED]` |
     | `0xFCEEF78E` | `0xDC01` | `bgt 0xFCEEF794` | Conditional branch if signed `r1 > 0` to `0xFCEEF794` (setting local `r1 = 0`). | `[VERIFIED]` |
     | `0xFCEEF790` | `0x2101` | `movs r1, #1` | Sets local flag `r1 = 1` (path taken when signed byte $\le 0$). | `[VERIFIED]` |
     | `0xFCEEF792` | `0xE000` | `b 0xFCEEF796` | Unconditional branch jumping over `0xFCEEF794` directly to call site at `0xFCEEF796`. | `[VERIFIED]` |
     | `0xFCEEF794` | `0x2100` | `movs r1, #0` | Sets local flag `r1 = 0` (path taken when `*(0x8040) != 0` or signed byte at `*(0x803C)+0x4B > 0`). | `[VERIFIED]` |
     | `0xFCEEF796` | `0xF7FF 0xFE4F` | `bl 0xFCEEF438` | Branch with link to unread activation callee `0xFCEEF438` (ATCM `0xBFE109EC`), passing `r0` (task pointer from `0xFCEF007E`) and `r1` (local flag, `0` or `1`). | `[VERIFIED: branch and register args; callee semantic role is INFERRED]` |
     | `0xFCEEF79A` | `0x2400` | `movs r4, #0` | Sets `r4 = 0` (success return code). | `[VERIFIED]` |
     | `0xFCEEF79C` | `0x9800` | `ldr r0, [sp, #0]` | Reads 32-bit word from local stack frame slot `sp[0]` into `r0`, passed as lock context argument to unlock helper `0xFCEF2904` (`blx 0xFCEF2904` at `0xFCEEF79E`). | `[VERIFIED: stack load; unlock handler semantic role is INFERRED]` |

  5. **Distinction Between Local `activate_task` Variables and `CreateTask` Arguments**:
     - **`r1` and `sp[0]` in `activate_task` are Strictly Local**:
       The `r1` and `sp[0]` values manipulated across `0xFCEEF77E..0xFCEEF79C` are strictly local to `activate_task` and are **not** the original `CreateTask` `r1` or `sp[0]` arguments:
       - In `CreateTask`, `r1` was the incoming priority argument, validated against $1 \le r1 \le 32$ and stored into descriptor offset `desc + 25` in `alloc_task_stack_tcb`. In `activate_task`, `r1` is generated entirely anew via literal pool loads (`0xFCEEF77E: ldr r1, [pc, #0x240]` and `0xFCEEF784: ldr r1, [pc, #0x234]`) and explicit immediate writes (`movs r1, #1` or `movs r1, #0`). It has no data-flow connection to `CreateTask`'s `r1`.
       - In `CreateTask`, `sp[0]` was the caller's 5th argument passed on the caller's stack frame at `sp_entry + 0x00`, retrieved via `ldr.w r8, [sp, #0x28]` and stored into descriptor offset `desc + 8` in `alloc_task_stack_tcb`. In `activate_task`, `sp[0]` reads from `activate_task`'s own local 16-byte stack frame allocated at `0xFCEEF760` (`push {r3, r4, r5, lr}`). This local stack slot was passed to kernel lock helper `0xFCEF28FC` (`mov r0, sp; blx 0xFCEF28FC`) at `0xFCEEF770..0xFCEEF775`, and is retrieved at `0xFCEEF79C` (`ldr r0, [sp, #0]`) to pass to unlock helper `0xFCEF2904`. It has no data-flow connection to `CreateTask`'s `sp[0]`.
     - **Epistemic Relationship to `CreateTask` Arguments `[UNKNOWN / INFERRED]`**:
       - Whether the local flag placed in `r1` (`0` or `1`) passed to `bl 0xFCEEF438` at `0xFCEEF796` relates semantically to the task priority or scheduling state configured by `CreateTask` is **`[UNKNOWN]`**; callee `0xFCEEF438` (ATCM `0xBFE109EC`) lies outside authorized read slices. Any interpretation of this parameter as an activation flag or scheduling mode is **`[INFERRED]`**.
       - Whether the local lock slot `sp[0]` or the lock/unlock routines (`0xFCEF28FC`, `0xFCEF2904`) interact with or affect the user context stored in the TCB descriptor at `desc + 8` is **`[UNKNOWN]`**.
       - Whether downstream activation callees (`0xFCEF007E`, `0xFCEEF438`) consume or rely on any of the stored descriptor parameters (`r0` name, `r1` priority, `r2` stack size, `sp[0]` context) cannot be determined from authorized ranges and remains **`[UNKNOWN]`**.
     - **`r2` is Untouched in `activate_task`**:
       Across all instructions of `activate_task` (`0xFCEEF760..0xFCEEF7A2`), register `r2` is neither read nor modified `[VERIFIED: limited strictly to instructions inside the authorized slice]`. The incoming `CreateTask` `r2` argument (candidate stack size) was forwarded to `alloc_task_stack_tcb` and stored into descriptor offset `desc + 16` (`desc = sp + 4`).
     - To investigate whether downstream activation code accesses the stored descriptor parameters, bounded proposed inspection ranges ($\le 4\text{ KiB}$ each) are defined as proposals for a future milestone:
       - Proposed ROM slice for `0xFCEF007E` (ATCM `0xBFE11632`): `0xFCEF0070..0xFCEF00EF` (128 B, $\le 4\text{ KiB}$, proposal for a future milestone).
       - Proposed ROM slice for `0xFCEEF438` (ATCM `0xBFE109EC`): `0xFCEEF430..0xFCEEF4AF` (128 B, $\le 4\text{ KiB}$, proposal for a future milestone).
- **Status Summary**:
  - Task handle check, register preservation, return value outcomes (-1 on invalid input, -1 on null result, 0 on success): **`[VERIFIED: covered by manifest entry PORT29-ROM-N3]`**; semantic locking and activation mechanisms in unread callees: **`[INFERRED]`**.
  - Local data flow in `activate_task` (`0xFCEEF77E..0xFCEEF79C`): `r1` literal loads, dereferences, conditional branches, immediate flag assignments (`0` or `1`), and local stack load `ldr r0, [sp, #0]`: **`[VERIFIED: covered by manifest entry PORT29-ROM-N3]`**.
  - Differentiation of local variables vs `CreateTask` arguments: `r1` and `sp[0]` in `activate_task` are strictly local to `activate_task` and are not the original `CreateTask` `r1` / `sp[0]` arguments: **`[VERIFIED]`**.
  - Epistemic relationship between local activation parameters and original `CreateTask` arguments: **`[UNKNOWN: callee 0xFCEEF438 unread]`**; semantic interpretations: **`[INFERRED]`**.
  - Absence of instructions accessing `r2` within `activate_task` body: **`[VERIFIED: limited strictly to accesses seen inside authorized slice]`**.
  - Claim that later code does not use stored descriptor parameters (`r0`/`r1`/`r2`/`sp[0]`): **`[UNKNOWN: call targets 0xFCEF007E and 0xFCEEF438 unread; proposed as bounded slices <= 4 KiB for a future milestone]`**.

---

## 4. The `r2` Stack Allocation: Allocator, Size, and Alignment

The table below synthesizes the verified findings and epistemic boundaries governing stack buffer allocation for tasks created via `CreateTask`.

```
========================================================================================
Summary of Task Stack Allocation Properties:
----------------------------------------------------------------------------------------
Property            Finding / Specification                  Epistemic Status & Citation
----------------------------------------------------------------------------------------
Argument Forwarding Forwarding of r2 to 0xBFE10B88; store    [VERIFIED: 0xFCEF3488..4F9; 0xFCEF3492;
                    to stack-frame offset [sp, #20] /         0xFCEF34D2; 0xFCEF34DA; 0xBFE10BD8]
                    descriptor offset [desc, #16] (desc=sp+4)
Fallback Load       Fallback load from *(r1 + 4) if r2 == 0  [VERIFIED: 0xFCEF34CA]
Allocated By        Allocator identity (caller vs kernel);   [INFERRED: consumer 0xBFE11746 unread;
                    forwarding does not rule out r2 as       forwarding instructions do not rule
                    a caller-provided buffer pointer          out reading r2 as buffer]
                    Stack allocation mechanism in kernel     [INFERRED: consumer 0xBFE11746 unread]
----------------------------------------------------------------------------------------
Stack Size (r2!=0)  Explicit caller integer forwarded        [VERIFIED: 0xFCEF34C8; 0xFCEF34D2]
                    Interpretation as byte size              [INFERRED: consumer 0xBFE11746 unread]
Stack Size (r2==0)  Fallback load from *(r1 + 4)             [VERIFIED: 0xFCEF34CA]
                    Address 0x000081D0 via literal 0x81CC    [INFERRED: docs/PORT11A:144, 162-164]
Initial Boot Value  ROM initializer at 0xFCE91228            [UNKNOWN: unread in ROM; <= 32 B proposed]
Runtime Value       Dynamic RAM value at *(0x000081D0)       [UNKNOWN: writers before CreateTask unread;
                                                              UNKNOWN-location]
----------------------------------------------------------------------------------------
Alignment Rule      ARM AAPCS 8-byte stack alignment         [INFERRED: DryOS / ARM standard]
Enforcement Site    Not in CreateTask (0xFCEF3488)           [VERIFIED: no bic/and in slice]
                    Not in alloc_task_stack_tcb (0xBFE10B88) [VERIFIED: no bic/and in slice]
                    Downstream in 0xBFE11746                 [UNKNOWN: 0xBFE11746 outside slice]
========================================================================================
```

### 4.1 Who Allocates the Stack: Caller vs. Callee/Kernel `[VERIFIED / INFERRED / UNKNOWN]`
- **Analysis**:
  1. Under the calling convention evidenced at `CreateTask` entry (`0xFCEF3488..0xFCEF3494`), five arguments are passed (`r0`–`r3` and `sp[0]`).
  2. Inside `CreateTask`, `r2` is preserved in `r5` (`0xFCEF3492`, `0x4615`) and forwarded as argument `r3` to `alloc_task_stack_tcb` (`0xBFE10B88`) at `0xFCEF34D2` (`0x462B`) and `0xFCEF34DA` (`0xF7FC 0xF87B`: `bl 0xBFE10B88`), with an `r2 == 0` fallback load from `*(r1 + 4)` at `0xFCEF34CA` (`0x684D`) `[VERIFIED]`.
  3. In Slice N3 (`0xFCEEF5C0..0xFCEEF7BF`), `alloc_task_stack_tcb` builds a task descriptor on its stack frame (`desc = sp + 4`, set up at `0xBFE10BF4`: `add r0, sp, #4`), writes `r3` into stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`0xBFE10BD8`, `0xC00E`), and executes `bl 0xBFE11746` at `0xBFE10BFA` (ROM `0xFCEEF646`, `0xF000 0xFDA4`), transferring the descriptor pointer `r0` to the internal kernel routine `[VERIFIED]`.
  4. The claim that "the caller never allocates or provides a stack buffer pointer" cannot be certified as verified from the observed forwarding instructions alone: `CreateTask` does not inspect or dereference `r2`, and the forwarding instructions do not rule out the consumer `0xBFE11746` interpreting `r2` as a caller-supplied buffer or structure pointer. The function body of `0xBFE11746` (ROM `0xFCEF0192`) was not read under PORT-29 policy.
  5. Therefore, the allocator identity (that the DryOS kernel allocates the task stack rather than the caller providing a buffer), the interpretation of `r2` as a byte size, and the downstream stack allocation mechanism are **`[INFERRED: consumer 0xBFE11746 unread]`**.
- **Verdict**: Register forwarding and `r2 == 0` fallback load are **`[VERIFIED]`**; allocator identity (caller vs kernel) and size semantics are **`[INFERRED]`**; exact kernel allocator mechanism is **`[UNKNOWN]`**.

### 4.2 Stack Size Determination `[VERIFIED / INFERRED / UNKNOWN]`
- **Explicit Size (`r2 != 0`)**:
  - Instruction `0xFCEF34C8` (`0xB905`: `cbnz r5, 0xbfe14a80`) bypasses default loading. The value passed in `r3` is exactly the caller's value `r2` `[VERIFIED]`.
  - Semantic interpretation as stack buffer byte count is **`[INFERRED]`** (consumer `0xBFE11746` unread).
- **Default Size (`r2 == 0`)**:
  - Instruction `0xFCEF34CA` (`0x684D`: `ldr r5, [r1, #4]`) loads `r5 = *(uint32_t *)(r1 + 4)`. The fallback substitution mechanism is strictly **`[VERIFIED]`**.
  - Derivation of `r1 = 0x000081CC` and `r1 + 4 = 0x000081D0` depends on unread literal pool entry `0xFCEF36A0` and is **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164]`**.
  - Address `0x000081D0` resides in system Low RAM (`0x00008000..0x0003F4F4`). As established in `docs/PORT21_RAM_LIFETIME.md:33, 210, 307` and `docs/CHDK_PORT1A_STARTUP_TRACE.md:213`, early boot Copy Loop 3 (`0xFC020054..0xFC020066`) copies Low RAM variables from ROM source `0xFCE91058`. The ROM source word corresponding to `0x000081D0` resides at $0\text{xFCE91058} + (0\text{x81D0} - 0\text{x8000}) = \mathbf{0\text{xFCE91228}}$, which was not read in PORT-29.
  - A future read of ROM `0xFCE91228` can establish only the INITIAL value written to RAM `0x81D0` during early boot, not its runtime value.
  - The runtime numeric integer value at `*(0x000081D0)` remains **`[UNKNOWN]`**. Settling the runtime value requires inspecting the code that writes `0x81D0` during initialization or establishing proof that no other writer modifies `0x81D0` before `CreateTask` callers run; because no verified ROM address is currently evidenced for such writers, this writer inspection is marked `UNKNOWN-location`.

### 4.3 Stack Memory Alignment `[VERIFIED / UNKNOWN]`
- **Absence of Masking in `CreateTask` and `alloc_task_stack_tcb`**:
  - A static audit of all 114 bytes in `CreateTask` (`0xFCEF3488..0xFCEF34F9`) confirms there are zero bitwise masking instructions (`bic`, `and`) or alignment tests applied to `r2` or `r5` `[VERIFIED]`.
  - A static audit of the 160-byte function body of `alloc_task_stack_tcb` (`0xBFE10B88..0xBFE10C26`, ROM `0xFCEEF5D4..0xFCEEF672`) confirms there are likewise zero alignment masking instructions applied to `r3` before storing it into stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`desc = sp + 4`) `[VERIFIED]`.
- **Downstream Kernel Alignment**:
  - Downstream routine `0xBFE11746` (ROM `0xFCEF0192`) allocates the stack buffer and sets up the initial Task Control Block (TCB). Whether `0xBFE11746` aligns the stack pointer to 4-byte or 8-byte boundaries (AAPCS compliant) cannot be observed within read slices.
  - Therefore, the exact stack alignment enforced by the DryOS kernel allocator remains **`[UNKNOWN]`**.

---

## 5. Prerequisite Item (b) Evaluation Matrix

| Prerequisite Element | Evidenced Property & ROM Instruction | Epistemic Status & Citations |
|---|---|:---:|
| **`r0` Role** | Moved to `r4`; if 0, fallback `ldr r4, [r1]`; stored to stack-frame offset `sp + 24` / descriptor offset `desc + 20` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF348C: mov r4, r0; 0xFCEF34AC: cbnz r4; 0xFCEF34AE: ldr r4, [r1]; 0xBFE10BF6: str.w r8, [sp, #24]]`**<br>**Semantic role as name string pointer: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **`r1` Role** | Moved to `r6`; checked `(r1 - 1) < 0x20` ($1 \le r1 \le 32$) else error branch; byte stored at desc+25 (`sp + 29`, with `desc = sp + 4`; INFERRED: priority) | **`[VERIFIED: 0xFCEF3490: mov r6, r1; 0xFCEF34B0: subs r0, r6, #1; 0xFCEF34B2: cmp r0, #0x20; 0xBFE10BEC: strb.w r4, [sp, #29]]`**<br>**Semantic role as scheduling priority: `[INFERRED: consumer 0xBFE11746 unread]`**; **error handler role as DebugAssert: `[INFERRED]`** |
| **`r2` Role** | Moved to `r5`; if 0, fallback `ldr r5, [r1, #4]`; forwarded to stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF3492: mov r5, r2; 0xFCEF34C8: cbnz r5; 0xFCEF34CA: ldr r5, [r1, #4]; 0xBFE10BD8: stmia]`**<br>**Literal 0x81CC at 0xFCEF36A0 and 0x81D0: `[INFERRED: docs/PORT11A:144, 162-164]`**<br>**Semantic role as stack size in bytes: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **`sp[0]` Role** | Loaded from caller stack `[sp, #0x28]`; forwarded to stack-frame offset `sp + 12` / descriptor offset `desc + 8` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF3494: ldr.w r8, [sp, #0x28]; 0xFCEF34CE: mov r1, r8; 0xBFE10BD8: stmia]`**<br>**Semantic delivery to task as user context: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **Stack Allocator** | Forwarding of `r2` to `0xBFE10B88` and descriptor offset `desc + 16` (`desc = sp + 4`); fallback load from `*(r1 + 4)` when `r2 == 0` | **`[VERIFIED: 0xFCEF3492: mov r5, r2; 0xFCEF34CA: ldr r5, [r1, #4]; 0xFCEF34D2: mov r3, r5; 0xFCEF34DA: bl 0xBFE10B88; 0xBFE10BD8: stmia]`**<br>**Allocator identity (caller vs kernel) & size semantics: `[INFERRED: consumer 0xBFE11746 unread; forwarding instructions do not rule out reading r2 as a buffer]`** |
| **Default Stack Size** | Runtime numeric integer value at `*(0x000081D0)` | **`[UNKNOWN: ROM initializer word 0xFCE91228 establishes only initial boot value; runtime value and writers modifying 0x81D0 before CreateTask remain UNKNOWN-location]`** |
| **Stack Alignment** | Alignment rule enforced by kernel allocator `0xBFE11746` | **`[UNKNOWN: 0xBFE11746 resides outside authorized slices]`** |
| **Later Parameter Use in Activation** | Usage of stored descriptor parameters in activation callees (`0xFCEF007E`, `0xFCEEF438`); local `r1` (flag 0/1) and local stack slot `sp[0]` in `activate_task` do not derive from `CreateTask` `r1`/`sp[0]` | **`[UNKNOWN: call targets 0xFCEF007E and 0xFCEEF438 unread; proposed as bounded slices <= 4 KiB for a future milestone]`** |

---

## 6. Final Verdict & Bounded Next-Milestone Proposals

### 6.1 Verdict: NO-GO
Under the reviewer directive in `docs/PORT27_RESIDENT_EVIDENCE.md:578-579` and the task specification:
> *"A final GO or NO-GO verdict. GO only if every element of item (b) is VERIFIED (all four argument roles plus the stack allocator, size and alignment). If NO-GO, give the exact remaining UNKNOWN list, each with a proposed bounded range (start, length of 4 KiB or less) for a future milestone."*

> [!WARNING]
> **Final Verdict for PORT-29 T1**: **`NO-GO`**
>
> Under strict project epistemic policy, a **GO** verdict requires every element of Item (b) to be certified as **`VERIFIED`**. While register moves, argument checks (`1 <= r1 <= 32` else error branch; INFERRED: DebugAssert), descriptor stores, argument forwarding, and `r2 == 0` fallback load were strictly observed in ROM, the high-level semantic roles (`r0` as name string, `r1` as scheduling priority, `r2` as stack size in bytes, `sp[0]` as task argument delivered to the spawned task, and stack allocator identity) are **`[INFERRED]`** because consumer `0xBFE11746` was not read. Furthermore, **stack alignment**, the **runtime default stack size literal** at `0x000081D0`, and **downstream descriptor parameter consumption** in activation callees remain **`[UNKNOWN]`**. These gaps compel an explicit **`NO-GO`** verdict.

### 6.2 The Exact Remaining UNKNOWN List & Proposed Bounded Ranges ($\le 4\text{ KiB}$)

To fully resolve the remaining uncertainties in a subsequent milestone, the following bounded read ranges ($\le 4\text{ KiB}$ each) are proposed for owner authorization:

| # | Item | Target Routine / Data Structure | Target VMA | Proposed ROM Range | Slice Size | Technical Objective & Justification |
|:---:|:---:|---|:---:|:---:|:---:|---|
| **1** | **(b)** | Kernel Task Allocator & Stack Alignment Routine (`0xBFE11746`) | `0xBFE11746` (ATCM Thumb-2) | `0xFCEF0180..0xFCEF037F` | 512 B | Called via `bl 0xbfe11746` at `0xBFE10BFA` in `alloc_task_stack_tcb`. Mapped via formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11746} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF0192}}$. Reading this 512-byte slice verifies the exact stack buffer allocation, stack alignment (4-byte vs 8-byte), TCB descriptor layout, and proves whether `r2` is consumed as stack byte count and `sp[0]` is delivered to the task function. |
| **2** | **(b)** | `CreateTask` Literal Pool Entry (Pointer at `0xFCEF36A0`) | `0xBFE14C54` (ATCM) | `0xFCEF36A0..0xFCEF36A3` | 4 B | Read by `0xFCEF34AA: ldr r1, [pc, #0x1f4]`. Verifies the 32-bit literal word (`0x000081CC`) currently known only from historical documentation `docs/PORT11A_GM110C_ROM_EVIDENCE.md:144`. |
| **3** | **(b)** | ROM Initializer Word for Default Stack Size (`*(0x000081D0)`) | `0x000081D0` (Low RAM destination) | `0xFCE91220..0xFCE9123F` | 32 B | Derived via early boot Copy Loop 3 (`0xFC020054..0xFC020066`, `docs/PORT21_RAM_LIFETIME.md:33, 210, 307`) copying ROM `0xFCE91058` to Low RAM `0x00008000..0x0003F4F4`. ROM source address: $0\text{xFCE91058} + (0\text{x81D0} - 0\text{x8000}) = \mathbf{0\text{xFCE91228}}$. Reading this bounded 32-byte ROM slice ($\le 4\text{ KiB}$) establishes only the INITIAL value written to RAM `0x81D0` during early boot, not its runtime value. The runtime value at `*(0x000081D0)` remains **UNKNOWN**. Settling the runtime value at `0x000081D0` requires extra evidence: the code that writes `0x81D0` during init, or proof that no other writer modifies `0x81D0` before `CreateTask` callers run. Because no bounded range ($\le 4\text{ KiB}$) is currently known for such writers, this extra writer evidence is marked `UNKNOWN-location`. |
| **4** | **(d)** | Reconciled `SleepTask` Body | `0xBFE14968` (ATCM Thumb-2) | `0xFCEF33A0..0xFCEF33DF` | 64 B | Truncates Slice N7 to exactly 64 bytes (`0xFCEF33A0..0xFCEF33DF`), eliminating the size disagreement with PORT27's $\le 64$ B constraint and verifying millisecond tick scaling. |
| **5** | **(b)** | Task Dispatcher / Context Delivery Consumer Investigation (`0xBFE11746`) | `0xBFE11746` (ATCM Thumb-2) | `0xFCEF0180..0xFCEF037F` | 512 B | Start address `0xFCEF0192` (VMA `0xBFE11746`) is evidenced by `bl 0xbfe11746` at `0xBFE10BFA` in Slice N3, mapped to ROM via early boot Copy Loop 1 formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11746} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF0192}}$ (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`). Length is 512 B (window `0xFCEF0180..0xFCEF037F`, sharing the read window of Row 1). Proves descriptor offset `desc + 8` (`sp[0]` context) delivery to task function and byte stored at `desc + 25` (`r1` parameter; INFERRED: priority) handling. Any address further downstream (such as a separate scheduler or context-switch dispatcher) remains **UNKNOWN** until this initial consumer window is read. |
| **6** | **(b)** | Activation Helper Downstream Callee: TCB Descriptor Lookup (`0xFCEF007E`) | `0xBFE11632` (ATCM Thumb-2) | `0xFCEF0070..0xFCEF00EF` | 128 B | Called by `activate_task` at `0xFCEEF778` (`bl 0xFCEF007E`). Bounded slice $\le 4\text{ KiB}$ proposed for a future milestone to inspect whether routine accesses stored descriptor parameters (`r0`/`r1`/`r2`/`sp[0]`). |
| **7** | **(b)** | Activation Helper Downstream Callee: Task Enqueue / Activation (`0xFCEEF438`) | `0xBFE109EC` (ATCM Thumb-2) | `0xFCEEF430..0xFCEEF4AF` | 128 B | Called by `activate_task` at `0xFCEEF796` (`bl 0xFCEEF438`). Bounded slice $\le 4\text{ KiB}$ proposed for a future milestone to inspect whether routine accesses stored descriptor parameters (`r0`/`r1`/`r2`/`sp[0]`). |

---

## 7. Acceptance Criteria Verification Checklist

- [x] **`python3 -B tools/port11c_evidence_validator.py --manifest evidence/port29_manifest.json --trusted-scopes evidence/port29_trusted_scopes.json` reports VALID with 0 errors**: Confirmed. Exact quoted output provided in §1.2.
- [x] **Every manifest range is one of the authorized ranges from `docs/PORT27_RESIDENT_CANDIDATE.md` Section 3 / `docs/PORT28_PORT27_OUTCOME.md`, is $\le 4\text{ KiB}$, and has start, length and SHA-256**: Confirmed. All 6 read slices in §2 are authorized ranges $\le 516$ B.
- [x] **Unclear or oversized ranges are listed as UNKNOWN and were not read**: Confirmed. Slice N4 was narrowed to non-overlapping remainder `0xFCEEF7C0..0xFCEEF9C3` with prefix hashed under N3; Slice N7 (bounds disagreement) and Item 8 (oversized > 4 KiB / unclear bounds) are cataloged as `UNKNOWN-not-read` in §2.
- [x] **`docs/PORT29_CREATETASK_EVIDENCE.md` states the roles of `r0`, `r1`, `r2` and `sp[0]` at `CreateTask` entry, and the `r2` stack allocator, size and alignment**: Confirmed in §3 and §4 with exact assembly words, VMA addresses, and reasoning.
- [x] **Every claim has a VERIFIED / INFERRED / UNKNOWN label**: Confirmed throughout document.
- [x] **The doc ends with an explicit GO/NO-GO verdict that matches the labels**: Confirmed in §6.1 with an explicit `NO-GO` verdict and remaining UNKNOWN list with bounded proposed ranges in §6.2.
- [x] **No ROM bytes, binaries or build outputs are committed; only allowed paths changed**: Confirmed. Worktree contains only the 4 allowed paths.
- [x] **Existing tests still pass**: Confirmed. Unit test suite passes without regressions.
