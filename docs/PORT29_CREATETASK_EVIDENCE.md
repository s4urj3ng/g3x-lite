# PORT-29 T1: CreateTask Calling Convention, Parameter Roles & Stack Allocation Evidence

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-29 T1 (`p29-t1-createtask-evidence`)
- **Primary Source**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (offline host analysis; 33,554,432 bytes; base `0xFC000000`) `[VERIFIED]`
- **Baseline Context**: `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` (Section 3 UNKNOWN list), `docs/PORT28_PORT27_OUTCOME.md:143-176` (Sections 4.1–4.3), `docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`, `docs/PORT21_RAM_LIFETIME.md:33, 210, 307`
- **Output Artifacts**:
  - `evidence/port29_manifest.json` `[VERIFIED]`
  - `evidence/port29_trusted_scopes.json` `[VERIFIED]`
  - `tests/test_port29_evidence.py` `[VERIFIED]`
- **Verdict**: **NO-GO** (Parameter semantic roles and stack allocator are `[INFERRED]`; stack alignment and runtime default stack size value remain `[UNKNOWN]`)

---

## 1. Executive Summary & Epistemic Standards

This dossier resolves **PORT-27 Item (b)** for Canon PowerShot G3 X firmware **GM1.10C**. All research, disassemblies, instruction traces, and cryptographic hashes in this report were performed strictly on the host workstation and offline from `firmware/dumps/GM1.10C/PRIMARY.BIN`.

### 1.1 Scope Authorization & Offline Policy Compliance
1. **Strict Read Scope Compliance**: The candidate authorized range list from `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3 and `docs/PORT28_PORT27_OUTCOME.md:143-176` Sections 4.1–4.3 comprises Slices N3–N7, the `CreateTask` body (`0xFCEF3488..0xFCEF34F9`, 114 bytes), and the two additional UNKNOWN entries (Slice N1 / `sub_fc31b408` and Item 8 non-heap RAM users), totaling 1,894 bytes (~1.9 KiB).
2. **Exclusion and Reconciliation of Unclear, Disputed, or Oversized Ranges**: In strict accordance with the task read policy ("If a range's bounds are unclear, the two docs disagree about it, or it is longer than 4 KiB, do not read it. Record it as UNKNOWN with the reason"):
   - **Slice N4** (`0xFCEEF760..0xFCEEF9C3`, 612 B): The 96-byte prefix `0xFCEEF760..0xFCEEF7BF` was **already read** as part of Slice N3 (`0xFCEEF5C0..0xFCEEF7BF`). This read prefix fully contains the `activate_task` helper body (`0xBFE10D14..0xBFE10D56`, ROM `0xFCEEF760..0xFCEEF7A2`, 68 B). The remainder of Slice N4 (`0xFCEEF7C0..0xFCEEF9C3`) was **not read** and remains `UNKNOWN-not-read` due to an extent disagreement between `docs/PORT27_OWNER_TRIAL_PLAN.md:71` (608 B) and `docs/PORT28_PORT27_OUTCOME.md:154` (612 B).
   - **Slice N7** (`0xFCEF33A0..0xFCEF33EF`, 80 B) was **not read** due to a direct documentation disagreement on window size: `docs/PORT27_RESIDENT_CANDIDATE.md:66` strictly caps the proposed inspection window at $\le 64$ B at entry `0xFCEF33B4`, whereas `docs/PORT28_PORT27_OUTCOME.md:161, 171` defines an 80-byte range starting at `0xFCEF33A0` (exceeding the 64-byte boundary).
   - **Item 8** (Relocated Core Non-Heap RAM Users) was **not read** because its bounds are unclear (no bounded ROM address), the two documents disagree (entire 32 MiB ROM in PORT27 vs no bounded ROM location in PORT28), and the span exceeds 4 KiB (130,252 B RAM / 32 MiB ROM).
3. **Manifest and Trusted Scopes**: All 5 read slices (totaling 1,202 bytes, well within the 4,096-byte scope budget) are declared in `evidence/port29_manifest.json` and authorized under `evidence/port29_trusted_scopes.json`. Earlier port manifests were kept in `docs/agentbridge/` (e.g. `docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json`) or `tests/fixtures/` (`port11a_manifest.json`), while PORT-29 places `port29_manifest.json` and `port29_trusted_scopes.json` under `evidence/` as mandated by the task specification.
4. **No Firmware Flashing or Hardware Access**: No physical camera hardware was connected, no SD card was modified, no binary payloads or build outputs were created, and zero ROM bytes were committed `[VERIFIED: docs/SAFETY.md:3-8; AGENTS.md:18-24]`.

### 1.2 Evidence Validator Execution & Output
The machine-readable evidence manifest was verified using `tools/port11c_evidence_validator.py`:

```bash
python3 -B tools/port11c_evidence_validator.py --manifest evidence/port29_manifest.json --trusted-scopes evidence/port29_trusted_scopes.json
```

**Exact Quoted Validator Output**:
```
Evidence Manifest Validation: 5 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED
----------------------------------------------------------------------
----------------------------------------------------------------------
Result: VALID (0 errors, 0 warnings)
```

---

## 2. Authorized ROM Ranges Evaluation Table

The table below catalogs every range in the candidate authorized range list from `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3 and `docs/PORT28_PORT27_OUTCOME.md:143-176` Sections 4.1–4.3, detailing source doc citations, start and end addresses, byte spans, SHA-256 cryptographic hashes, and read status (`READ`, `PARTIALLY READ VIA N3`, or `UNKNOWN-not-read`).

In `docs/PORT27_RESIDENT_CANDIDATE.md:56-67` Section 3, nine entries are enumerated:
- Rows 1, 2, 3, 5/6, 9 correspond to Slices N3, N4, N5, N6, N7.
- Row 4 is the `CreateTask` body `0xFCEF3488..0xFCEF34F9` (114 B).
- The two other UNKNOWN entries listed there are Row 7 (Heap alignment `sub_fc31b408` / Slice N1 at `0xFC31B408..0xFC31B507`, 256 B) and Row 8 (Relocated Core Non-Heap RAM users, 130,252 B RAM, unread due to >4 KiB size and lack of a bounded ROM address).

| Range ID | Target Routine / Subsystem | Source Citation (Doc:Line) | Start Address | End Address | Length (Bytes) | SHA-256 Digest | Status | Policy Compliance & Epistemic Reasoning |
|---|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **PORT29-ROM-N1** | `sub_fc31b408` Heap Init & Veneer Table | `docs/PORT27_RESIDENT_CANDIDATE.md:64`; `docs/PORT28_PORT27_OUTCOME.md:159, 165` | `0xFC31B408` | `0xFC31B507` | 256 B | `b93e3f48ab31f467e9ee3f4ba907ea3032a3a81cac4fe1ff18a2c0ba138181ce` | **`READ`** | Bounded ($\le 4\text{ KiB}$), both docs agree on start `0xFC31B408` and length 256 B; non-overlapping. Authorized under Item (a) kernel init. Provides zero calling convention evidence for Item (b); no CreateTask claim relies on it. |
| **PORT29-ROM-N3** | `alloc_task_stack_tcb` Task Allocator Body | `docs/PORT27_RESIDENT_CANDIDATE.md:58`; `docs/PORT28_PORT27_OUTCOME.md:153, 167` | `0xFCEEF5C0` | `0xFCEEF7BF` | 512 B | `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2` | **`READ`** | Bounded ($\le 4\text{ KiB}$); captures `0xBFE10B88` body (160 B) and task parameter setup; also covers the N4 prefix containing `activate_task` (`0xBFE10D14..0xBFE10D56`). |
| **PORT29-ROM-N5** | `DebugAssert` Kernel Panic Handler Veneer Table | `docs/PORT27_RESIDENT_CANDIDATE.md:60`; `docs/PORT28_PORT27_OUTCOME.md:155, 169` | `0xFCEF28B0` | `0xFCEF29AF` | 256 B | `93c956e9d994888fc228997a65d0785901a4c23e0921c5e3cf6befa450fb2142` | **`READ`** | Bounded ($\le 4\text{ KiB}$); covers `0xBFE13E78` veneer target vector; both docs agree on $\le 256$ B window. |
| **PORT29-ROM-CREATETASK** | `CreateTask` Body & Calling Convention | `docs/PORT27_RESIDENT_CANDIDATE.md:61`; `docs/PORT28_PORT27_OUTCOME.md:147` | `0xFCEF3488` | `0xFCEF34F9` | 114 B | `6d7fbecb5f9589cc34994a63ac6cf7e2def132a7c355a789a29ea3cae8c50ddf` | **`READ`** | Bounded ($\le 4\text{ KiB}$); exact 114-byte extent confirmed by terminating epilogue branch; both docs agree. |
| **PORT29-ROM-N6** | ATCM Interrupt Disable & Restore Veneers | `docs/PORT27_RESIDENT_CANDIDATE.md:62-63`; `docs/PORT28_PORT27_OUTCOME.md:157-158, 170` | `0xFCEF3A20` | `0xFCEF3A5F` | 64 B | `3bf663507211b96500c59647e3f065cff96d111421ee5a2c867c022536c45969` | **`READ`** | Bounded ($\le 4\text{ KiB}$); covers `0xBFE14FE6` and `0xBFE14FEA` branch trampolines; both docs agree on 64 B. |
| **PORT29-ROM-N4** | `activate_task` Task Activation Helper | `docs/PORT27_RESIDENT_CANDIDATE.md:59`; `docs/PORT28_PORT27_OUTCOME.md:154, 168` | `0xFCEEF760` | `0xFCEEF9C3` | 612 B | N/A | **`PARTIALLY READ VIA N3 / UNKNOWN-not-read for remainder`** | Prefix `0xFCEEF760..0xFCEEF7BF` (96 B) is read inside Slice N3, covering `activate_task` (`0xBFE10D14..0xBFE10D56`, ROM `0xFCEEF760..0xFCEEF7A2`). Remainder `0xFCEEF7C0..0xFCEEF9C3` is unread due to 608 vs 612 B doc conflict. |
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
r0        Task Name Pointer                 Moved to r4; if r0 == 0, loads fallback *(r1);
                                            stored to stack-frame offset [sp, #24] /
                                            descriptor offset [desc, #20] (desc = sp + 4) [VERIFIED].
                                            Semantic role as name string pointer [INFERRED].
r1        Task Execution Priority           Moved to r6; checked (r1 - 1) < 0x20 else asserts;
                                            stored to stack-frame offset [sp, #29] /
                                            descriptor offset [desc, #25] (desc = sp + 4) [VERIFIED].
                                            Semantic role as scheduling priority [INFERRED].
r2        Task Stack Size (Bytes)           Moved to r5; if r2 == 0, loads fallback *(r1 + 4);
                                            forwarded as parameter to 0xBFE10B88; stored to
                                            stack-frame offset [sp, #20] / descriptor offset
                                            [desc, #16] (desc = sp + 4) [VERIFIED].
                                            Literal pool address 0xFCEF36A0 unread [INFERRED: PORT11A].
                                            Semantic role as stack size in bytes [INFERRED].
r3        Task Entry Function Pointer       Checked r3 != 0 else asserts; stored to
                                            stack-frame offset [sp, #8] / descriptor offset
                                            [desc, #4] (desc = sp + 4) [VERIFIED].
                                            Semantic role as entry point [INFERRED].
sp[0]     User Context Parameter            Loaded from caller stack [sp, #0x28]; forwarded
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
  1. At entry, `CreateTask` executes `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` at `0xFCEF3488` (`2d e9 fe 43`), allocating 40 bytes (`0x28` B) on the stack and preserving caller registers `[VERIFIED]`.
  2. At `0xFCEF348C`, `mov r4, r0` moves incoming `r0` into callee-saved register `r4` `[VERIFIED]`.
  3. At `0xFCEF34AA` (`7d 49`), `ldr r1, [pc, #0x1f4]` executes PC-relative load. The target literal word is located at $\text{Align}(0\text{xFCEF34AA} + 4, 4) + 0\text{x1f4} = 0\text{xFCEF34AC} + 0\text{x1f4} = 0\text{xFCEF36A0}$ (ATCM `0xBFE14C54`). Because `0xFCEF36A0` lies outside all manifest read ranges, the literal value `0x000081CC` cannot be verified from read slices; it is **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144]`**.
  4. At `0xFCEF34AC` (`04 b9`), `cbnz r4, 0xbfe14a64` inspects `r4`. If `r4 != 0`, caller value is preserved. If `r4 == 0`, instruction `0xFCEF34AE` (`0c 68`) executes `ldr r4, [r1]`, substituting the default pointer stored at `*(uint32_t *)r1` `[VERIFIED]`.
  5. At `0xFCEF34D4` (`02 94`), `str r4, [sp, #8]` passes `r4` on the stack to internal routine `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` (`0xFCEEF5D4` / `0xBFE10B88`), after allocating a 56-byte stack frame (`stmdb sp!` 24 B + `sub sp, #32`), instruction `0xBFE10B8E` (`e9dd 780f`) executes `ldrd r7, r8, [sp, #60]`, retrieving `r8` from stack-frame offset `sp + 64` (corresponding to caller's `sp + 8`).
  - At `0xBFE10BF4` (word `0xA801`, `add r0, sp, #4`), `alloc_task_stack_tcb` sets up the descriptor pointer passed in `r0` to `0xBFE11746`, defining descriptor base `desc = sp + 4`. At `0xBFE10BF6` (`f8cd 8018`), `str.w r8, [sp, #24]` stores this pointer into stack-frame offset `sp + 24`, corresponding to descriptor offset `desc + 20` (`desc = sp + 4`) `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B984`: `ldr r0, [pc, #0x18]` loads `r0 = 0xFC05B9A0`, pointing to literal string `"init_task\0"` `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:144-155 / docs/PORT11A_GM110C_ROM_EVIDENCE.md:104-108]`.
- **Status Summary**:
  - Register forwarding, null check, fallback dereference, and descriptor store at stack-frame offset `sp + 24` / descriptor offset `desc + 20`: **`[VERIFIED]`**.
  - Semantic interpretation as null-terminated ASCII task name string: **`[INFERRED]`** (consumer at `0xBFE11746` unread).

### 3.2 Role of `r1`: Range Check and Descriptor Storage `[VERIFIED]` / Priority Interpretation `[INFERRED]`
- **ROM Address**: `0xFCEF3490` (File Offset `0x00EF3490`, ATCM VMA `0xBFE14A44`)
- **Instruction Word**: `0x460e` (16-bit Thumb)
- **Disassembly**: `mov r6, r1`
- **Technical Reasoning**:
  1. At `0xFCEF3490`, `mov r6, r1` transfers incoming `r1` into callee-saved register `r6` `[VERIFIED]`.
  2. At `0xFCEF34B0` (`70 1e`), `subs r0, r6, #1` decrements `r6` by 1 into `r0` `[VERIFIED]`.
  3. At `0xFCEF34B2` (`20 28`), `cmp r0, #0x20` compares `r6 - 1` against unsigned integer `32` (`0x20`) `[VERIFIED]`.
  4. At `0xFCEF34B4` (`00 d2`), `bhs 0xbfe14a6c` takes an error branch if `r0 >= 32` (unsigned), strictly enforcing that incoming `r1` must satisfy $0 \le (r1 - 1) < 32$, which is mathematically equivalent to:
     $$1 \le r1 \le 32$$
  5. If `r1` is outside $1..32$, execution branches to `0xFCEF34B8`: `movs r2, #0xa0` (source line 160), `adr r1, #0x1e8` (`"KerTask.c"`), and `blx 0xBFE13E78` (invoking `DebugAssert` in Slice N5), returning error code 3 at `0xFCEF34C2` (`movs r0, #3`) `[VERIFIED]`.
  6. If valid, at `0xFCEF34D6` (`cd e9 00 62`), `strd r6, r2, [sp]` stores `r6` at `[sp]` and `r2` (`0`) at `[sp, #4]` for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10B92` (`9c0e`), `ldr r4, [sp, #56]` loads `r4` from caller's `[sp]` (retrieving `r6`).
  - At `0xBFE10BA6` (`2c00`), `cmp r4, #0`; `db3a: blt 0xbfe10c20` verifies value is non-negative `[VERIFIED]`.
  - At `0xBFE10BAA` (`4df0`), `ldr r5, [pc, #960]`; `682d: ldr r5, [r5]`; `42ac: cmp r4, r5`; `da36: bge 0xbfe10c20` compares against active task limit `[VERIFIED]`.
  - At `0xBFE10BEC` (`f88d 401d`), `strb.w r4, [sp, #29]` writes the priority byte into stack-frame offset `sp + 29`, corresponding to descriptor offset `desc + 25` (`desc = sp + 4`) of the task control block descriptor `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B98A`: `movs r1, #25` (passes 25, within verified $1..32$ bounds) `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:147]`.
- **Status Summary**:
  - Range check `(r1 - 1) < 0x20` ($1 \le r1 \le 32$) else `DebugAssert`, register forwarding, and descriptor store at stack-frame offset `sp + 29` / descriptor offset `desc + 25`: **`[VERIFIED]`**.
  - Semantic interpretation as task scheduling priority: **`[INFERRED]`** (consumer at `0xBFE11746` and scheduler unread).

### 3.3 Role of `r2`: Argument Forwarding and Default Load `[VERIFIED]` / Stack Size Interpretation `[INFERRED]`
- **ROM Address**: `0xFCEF3492` (File Offset `0x00EF3492`, ATCM VMA `0xBFE14A46`)
- **Instruction Word**: `0x4615` (16-bit Thumb)
- **Disassembly**: `mov r5, r2`
- **Technical Reasoning**:
  1. At `0xFCEF3492`, `mov r5, r2` preserves incoming `r2` in callee-saved register `r5` `[VERIFIED]`.
  2. At `0xFCEF34C8` (`05 b9`), `cbnz r5, 0xbfe14a80` evaluates `r5`. If `r5 != 0`, execution branches directly to `0xBFE14A80`, preserving the explicit value passed by caller `[VERIFIED]`.
  3. At `0xFCEF34CA` (`4d 68`), `ldr r5, [r1, #4]` executes if `r5 == 0`. Register `r1` holds the base pointer loaded at `0xFCEF34AA`. In historical documentation `docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164`, literal pool entry `0xFCEF36A0` was documented as `0x000081CC`, making `[r1, #4]` access `0x000081CC + 4 = 0x000081D0`. Because literal `0xFCEF36A0` is unread in PORT-29, the literal value `0x000081CC` and default address `0x000081D0` are **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164]`**.
  4. At `0xFCEF34D2` (`2b 46`), `mov r3, r5` moves the resolved value into register `r3` as parameter 4 for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10B94` (`b90b`), `cbnz r3, 0xbfe10b9a` verifies that `r3` is non-zero `[VERIFIED]`.
  - At `0xBFE10B96` (`4bf3`) and `0xBFE10B98` (`681b`), `ldr r3, [pc, #972]` (`0xBFE10F64`); `ldr r3, [r3]` provides secondary fallback if `r3 == 0` `[VERIFIED]`.
  - At `0xBFE10BD6` (word `0xA803`, `add r0, sp, #12`), `alloc_task_stack_tcb` sets `r0 = sp + 12`; then at `0xBFE10BD8` (`c00e`), `stmia r0!, {r1, r2, r3}` writes `{r1, r2, r3}` sequentially into stack-frame offsets `sp + 12`, `sp + 16`, and `sp + 20`. Parameter `r3` (forwarded from `r2` / default stack size) is thus written into stack-frame offset `sp + 20`, corresponding to descriptor offset `desc + 16` (`desc = sp + 4`) of the task creation parameter block passed to internal kernel allocator `0xBFE11746` `[VERIFIED]`.
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
- **Instruction Word**: `0x8028f8dd` (32-bit Thumb-2: `dd f8 28 80`)
- **Disassembly**: `ldr.w r8, [sp, #0x28]`
- **Technical Reasoning**:
  1. At entry `0xFCEF3488`, `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` decrements the stack pointer by exactly 40 bytes (`0x28` B) `[VERIFIED]`.
  2. Under AAPCS conventions, arguments beyond the fourth (`r0`–`r3`) are placed by the caller on the stack starting at `sp[0]`.
  3. At `0xFCEF3494`, `ldr.w r8, [sp, #0x28]` reads 32 bits from `sp_current + 0x28`, corresponding precisely to `sp_entry + 0x00` (caller's 5th argument passed on stack). The word is loaded into callee-saved register `r8` `[VERIFIED]`.
  4. At `0xFCEF34CE` (`41 46`), `mov r1, r8` transfers `r8` into `r1` as argument 2 for callee `0xBFE10B88` `[VERIFIED]`.
- **Call-Site Corroboration in Slice N3 (`0xBFE10B88` / `0xFCEEF5D4`)**:
  - In `alloc_task_stack_tcb` at `0xBFE10BD6` (`add r0, sp, #12`) and `0xBFE10BD8` (`c00e`, `stmia r0!, {r1, r2, r3}`), incoming `r1` (caller's `sp[0]`) is written into stack-frame offset `sp + 12`, corresponding to descriptor offset `desc + 8` (`desc = sp + 4`) of the parameter block passed to `0xBFE11746` `[VERIFIED]`.
- **Stock Caller Call-Site Evidence**:
  - In `sub_fc05b962` (`PORT27-ROM-STARTUP-TASKS`) at `0xFC05B980..0xFC05B982`: `movs r3, #0`; `str r3, [sp, #0]` (places 0 at `sp[0]`) `[INFERRED: historical corroboration, citing docs/PORT27_RESIDENT_EVIDENCE.md:145]`.
- **Status Summary**:
  - Retrieval of 5th parameter from caller stack `sp[0]` and forwarding into stack-frame offset `sp + 12` / descriptor offset `desc + 8` (`desc = sp + 4`): **`[VERIFIED]`**.
  - Semantic delivery to spawned task function as user context argument: **`[INFERRED]`** (consumer at `0xBFE11746` and task dispatcher unread).

### 3.5 Corroborating Role of `r3`: Non-Null Check and Entry Forwarding `[VERIFIED]` / Execution Role `[INFERRED]`
- **ROM Address**: `0xFCEF3498` (File Offset `0x00EF3498`, ATCM VMA `0xBFE14A4C`)
- **Instruction Word**: `0x461f` (16-bit Thumb)
- **Disassembly**: `mov r7, r3`
- **Technical Reasoning**:
  1. At `0xFCEF3498`, `mov r7, r3` preserves incoming `r3` in callee-saved register `r7` `[VERIFIED]`.
  2. At `0xFCEF34B6` (`3f b9`), `cbnz r7, 0xbfe14a7c` checks whether `r7` is non-zero. If `r7 == 0`, execution falls through to `0xFCEF34B8`, calling `DebugAssert` with source line 160 (`movs r2, #0xa0`) and aborting task creation `[VERIFIED]`.
  3. At `0xFCEF34D0` (`38 46`), `mov r0, r7` passes the function pointer in `r0` to `0xBFE10B88` `[VERIFIED]`.
  4. In `alloc_task_stack_tcb` at `0xBFE10BD2` (`e9cd 6001`), `strd r6, r0, [sp, #4]` writes `r0` (task entry function pointer) into stack-frame offset `sp + 8`, corresponding to descriptor offset `desc + 4` (`desc = sp + 4`) of the task descriptor `[VERIFIED]`.
- **Status Summary**:
  - Check `r3 != 0` else `DebugAssert`, register forwarding, and descriptor store at stack-frame offset `sp + 8` / descriptor offset `desc + 4`: **`[VERIFIED]`**.
  - Execution as spawned task main entry point: **`[INFERRED]`** (consumer at `0xBFE11746` and task dispatcher unread).

---

## 4. The `r2` Stack Allocation: Allocator, Size, and Alignment

The table below synthesizes the verified findings and epistemic boundaries governing stack buffer allocation for tasks created via `CreateTask`.

```
========================================================================================
Summary of Task Stack Allocation Properties:
----------------------------------------------------------------------------------------
Property            Finding / Specification                  Epistemic Status & Citation
----------------------------------------------------------------------------------------
Argument Forwarding Forwarding of r2 to 0xBFE10B88; store    [VERIFIED: 0xFCEF3492; 0xFCEF34D2;
                    to stack-frame offset [sp, #20] /         0xFCEF34DA; 0xBFE10BD8]
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
Dynamic Value       RAM literal at 0x000081D0                [UNKNOWN: unread in ROM]
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
  2. Inside `CreateTask`, `r2` is preserved in `r5` (`0xFCEF3492`) and forwarded as argument `r3` to `alloc_task_stack_tcb` (`0xBFE10B88`) at `0xFCEF34D2` and `0xFCEF34DA` (`bl 0xBFE10B88`), with an `r2 == 0` fallback load from `*(r1 + 4)` at `0xFCEF34CA` `[VERIFIED]`.
  3. In Slice N3 (`0xFCEEF5C0..0xFCEEF7BF`), `alloc_task_stack_tcb` builds a task descriptor on its stack frame (`desc = sp + 4`, set up at `0xBFE10BF4: add r0, sp, #4`), writes `r3` into stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`0xBFE10BD8`), and executes `bl 0xBFE11746` at `0xBFE10BFA`, transferring the descriptor pointer `r0` to the internal kernel routine `[VERIFIED]`.
  4. The claim that "the caller never allocates or provides a stack buffer pointer" cannot be certified as verified from the observed forwarding instructions alone: `CreateTask` does not inspect or dereference `r2`, and the forwarding instructions do not rule out the consumer `0xBFE11746` interpreting `r2` as a caller-supplied buffer or structure pointer. The function body of `0xBFE11746` (ROM `0xFCEF0192`) was not read under PORT-29 policy.
  5. Therefore, the allocator identity (that the DryOS kernel allocates the task stack rather than the caller providing a buffer), the interpretation of `r2` as a byte size, and the downstream stack allocation mechanism are **`[INFERRED: consumer 0xBFE11746 unread]`**.
- **Verdict**: Register forwarding and `r2 == 0` fallback load are **`[VERIFIED]`**; allocator identity (caller vs kernel) and size semantics are **`[INFERRED]`**; exact kernel allocator mechanism is **`[UNKNOWN]`**.

### 4.2 Stack Size Determination `[VERIFIED / INFERRED / UNKNOWN]`
- **Explicit Size (`r2 != 0`)**:
  - Instruction `0xFCEF34C8` (`cbnz r5, 0xbfe14a80`) bypasses default loading. The value passed in `r3` is exactly the caller's value `r2` `[VERIFIED]`.
  - Semantic interpretation as stack buffer byte count is **`[INFERRED]`** (consumer `0xBFE11746` unread).
- **Default Size (`r2 == 0`)**:
  - Instruction `0xFCEF34CA` (`ldr r5, [r1, #4]`) loads `r5 = *(uint32_t *)(r1 + 4)`. The fallback substitution mechanism is strictly **`[VERIFIED]`**.
  - Derivation of `r1 = 0x000081CC` and `r1 + 4 = 0x000081D0` depends on unread literal pool entry `0xFCEF36A0` and is **`[INFERRED: citing docs/PORT11A_GM110C_ROM_EVIDENCE.md:144, 162-164]`**.
  - Address `0x000081D0` resides in system Low RAM (`0x00008000..0x0003F4F4`). As established in `docs/PORT21_RAM_LIFETIME.md:33, 210, 307` and `docs/CHDK_PORT1A_STARTUP_TRACE.md:213`, early boot Copy Loop 3 (`0xFC020054..0xFC020066`) copies Low RAM variables from ROM source `0xFCE91058`. The ROM source word corresponding to `0x000081D0` resides at $0\text{xFCE91058} + (0\text{x81D0} - 0\text{x8000}) = \mathbf{0\text{xFCE91228}}$, which was not read in PORT-29.
  - The runtime numeric integer value at `*(0x000081D0)` remains **`[UNKNOWN]`**.

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
| **`r1` Role** | Moved to `r6`; checked `(r1 - 1) < 0x20` ($1 \le r1 \le 32$) else `DebugAssert`; stored to stack-frame offset `sp + 29` / descriptor offset `desc + 25` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF3490: mov r6, r1; 0xFCEF34B0: subs r0, r6, #1; 0xFCEF34B2: cmp r0, #0x20; 0xBFE10BEC: strb.w r4, [sp, #29]]`**<br>**Semantic role as scheduling priority: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **`r2` Role** | Moved to `r5`; if 0, fallback `ldr r5, [r1, #4]`; forwarded to stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF3492: mov r5, r2; 0xFCEF34C8: cbnz r5; 0xFCEF34CA: ldr r5, [r1, #4]; 0xBFE10BD8: stmia]`**<br>**Literal 0x81CC at 0xFCEF36A0 and 0x81D0: `[INFERRED: docs/PORT11A:144, 162-164]`**<br>**Semantic role as stack size in bytes: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **`sp[0]` Role** | Loaded from caller stack `[sp, #0x28]`; forwarded to stack-frame offset `sp + 12` / descriptor offset `desc + 8` (`desc = sp + 4`) | **`[VERIFIED: 0xFCEF3494: ldr.w r8, [sp, #0x28]; 0xFCEF34CE: mov r1, r8; 0xBFE10BD8: stmia]`**<br>**Semantic delivery to task as user context: `[INFERRED: consumer 0xBFE11746 unread]`** |
| **Stack Allocator** | Forwarding of `r2` to `0xBFE10B88` and descriptor offset `desc + 16` (`desc = sp + 4`); fallback load from `*(r1 + 4)` when `r2 == 0` | **`[VERIFIED: 0xFCEF3492: mov r5, r2; 0xFCEF34CA: ldr r5, [r1, #4]; 0xFCEF34D2: mov r3, r5; 0xFCEF34DA: bl 0xBFE10B88; 0xBFE10BD8: stmia]`**<br>**Allocator identity (caller vs kernel) & size semantics: `[INFERRED: consumer 0xBFE11746 unread; forwarding instructions do not rule out reading r2 as a buffer]`** |
| **Default Stack Size** | Numeric integer value at `*(0x000081D0)` at runtime | **`[UNKNOWN: ROM source word 0xFCE91228 unread]`** |
| **Stack Alignment** | Alignment rule enforced by kernel allocator `0xBFE11746` | **`[UNKNOWN: 0xBFE11746 resides outside authorized slices]`** |

---

## 6. Final Verdict & Bounded Next-Milestone Proposals

### 6.1 Verdict: NO-GO
Under the reviewer directive in `docs/PORT27_RESIDENT_EVIDENCE.md:578-579` and the task specification:
> *"A final GO or NO-GO verdict. GO only if every element of item (b) is VERIFIED (all four argument roles plus the stack allocator, size and alignment). If NO-GO, give the exact remaining UNKNOWN list, each with a proposed bounded range (start, length of 4 KiB or less) for a future milestone."*

> [!WARNING]
> **Final Verdict for PORT-29 T1**: **`NO-GO`**
>
> Under strict project epistemic policy, a **GO** verdict requires every element of Item (b) to be certified as **`VERIFIED`**. While register moves, argument checks (`1 <= r1 <= 32` else `DebugAssert`), descriptor stores, argument forwarding, and `r2 == 0` fallback load were strictly observed in ROM, the high-level semantic roles (`r0` as name string, `r1` as scheduling priority, `r2` as stack size in bytes, `sp[0]` as task argument delivered to the spawned task, and stack allocator identity) are **`[INFERRED]`** because consumer `0xBFE11746` was not read. Furthermore, **stack alignment** and the **runtime default stack size literal** at `0x000081D0` remain **`[UNKNOWN]`**. These gaps compel an explicit **`NO-GO`** verdict.

### 6.2 The Exact Remaining UNKNOWN List & Proposed Bounded Ranges ($\le 4\text{ KiB}$)

To fully resolve the remaining uncertainties in a subsequent milestone, the following bounded read ranges ($\le 4\text{ KiB}$ each) are proposed for owner authorization:

| # | Item | Target Routine / Data Structure | Target VMA | Proposed ROM Range | Slice Size | Technical Objective & Justification |
|:---:|:---:|---|:---:|:---:|:---:|---|
| **1** | **(b)** | Kernel Task Allocator & Stack Alignment Routine (`0xBFE11746`) | `0xBFE11746` (ATCM Thumb-2) | `0xFCEF0180..0xFCEF037F` | 512 B | Called via `bl 0xbfe11746` at `0xBFE10BFA` in `alloc_task_stack_tcb`. Mapped via formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11746} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF0192}}$. Reading this 512-byte slice verifies the exact stack buffer allocation, stack alignment (4-byte vs 8-byte), TCB descriptor layout, and proves whether `r2` is consumed as stack byte count and `sp[0]` is delivered to the task function. |
| **2** | **(b)** | `CreateTask` Literal Pool Entry (Pointer at `0xFCEF36A0`) | `0xBFE14C54` (ATCM) | `0xFCEF36A0..0xFCEF36A3` | 4 B | Read by `0xFCEF34AA: ldr r1, [pc, #0x1f4]`. Verifies the 32-bit literal word (`0x000081CC`) currently known only from historical documentation `docs/PORT11A_GM110C_ROM_EVIDENCE.md:144`. |
| **3** | **(b)** | ROM Source Word for Default Stack Size Literal (`*(0x000081D0)`) | `0x000081D0` (Low RAM destination) | `0xFCE91220..0xFCE9123F` | 32 B | Derived via early boot Copy Loop 3 (`0xFC020054..0xFC020066`, `docs/PORT21_RAM_LIFETIME.md:33, 210, 307`) copying ROM `0xFCE91058` to Low RAM `0x00008000..0x0003F4F4`. ROM source address: $0\text{xFCE91058} + (0\text{x81D0} - 0\text{x8000}) = \mathbf{0\text{xFCE91228}}$. Verifies the default stack size integer. |
| **4** | **(b)** | Unread Remainder of Slice N4 (`activate_task` downstream routines) | `0xBFE10D74` (ATCM Thumb-2) | `0xFCEEF7C0..0xFCEEF9C3` | 516 B | The `activate_task` body (`0xBFE10D14..0xBFE10D56`, ROM `0xFCEEF760..0xFCEEF7A2`) is already read inside Slice N3. This slice covers downstream helpers following `0xFCEEF7BF`, resolving the 608 vs 612 B doc conflict. |
| **5** | **(d)** | Reconciled `SleepTask` Body | `0xBFE14968` (ATCM Thumb-2) | `0xFCEF33A0..0xFCEF33DF` | 64 B | Truncates Slice N7 to exactly 64 bytes (`0xFCEF33A0..0xFCEF33DF`), eliminating the size disagreement with PORT27's $\le 64$ B constraint and verifying millisecond tick scaling. |
| **6** | **(b)** | Task Dispatcher / Context Delivery Consumer Investigation (`0xBFE11746`) | `0xBFE11746` (ATCM Thumb-2) | `0xFCEF0180..0xFCEF037F` | 512 B | Start address `0xFCEF0192` (VMA `0xBFE11746`) is evidenced by `bl 0xbfe11746` at `0xBFE10BFA` in Slice N3, mapped to ROM via early boot Copy Loop 1 formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11746} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF0192}}$ (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:112-118`). Length is 512 B (window `0xFCEF0180..0xFCEF037F`, sharing the read window of Row 1). Proves descriptor offset `desc + 8` (`sp[0]` context) delivery to task function and `desc + 25` (`r1` priority) handling. Any address further downstream (such as a separate scheduler or context-switch dispatcher) remains **UNKNOWN** until this initial consumer window is read. |

---

## 7. Acceptance Criteria Verification Checklist

- [x] **`python3 -B tools/port11c_evidence_validator.py --manifest evidence/port29_manifest.json --trusted-scopes evidence/port29_trusted_scopes.json` reports VALID with 0 errors**: Confirmed. Exact quoted output provided in §1.2.
- [x] **Every manifest range is one of the authorized ranges from `docs/PORT27_RESIDENT_CANDIDATE.md` Section 3 / `docs/PORT28_PORT27_OUTCOME.md`, is $\le 4\text{ KiB}$, and has start, length and SHA-256**: Confirmed. All 5 read slices in §2 are authorized ranges $\le 512$ B.
- [x] **Unclear or oversized ranges are listed as UNKNOWN and were not read**: Confirmed. Slice N4 prefix is read in N3, remainder is unread; Slice N7 (bounds disagreement) and Item 8 (oversized > 4 KiB / unclear bounds) are cataloged as `UNKNOWN-not-read` in §2.
- [x] **`docs/PORT29_CREATETASK_EVIDENCE.md` states the roles of `r0`, `r1`, `r2` and `sp[0]` at `CreateTask` entry, and the `r2` stack allocator, size and alignment**: Confirmed in §3 and §4 with exact assembly words, VMA addresses, and reasoning.
- [x] **Every claim has a VERIFIED / INFERRED / UNKNOWN label**: Confirmed throughout document.
- [x] **The doc ends with an explicit GO/NO-GO verdict that matches the labels**: Confirmed in §6.1 with an explicit `NO-GO` verdict and remaining UNKNOWN list with bounded proposed ranges in §6.2.
- [x] **No ROM bytes, binaries or build outputs are committed; only allowed paths changed**: Confirmed. Worktree contains only the 4 allowed paths.
- [x] **Existing tests still pass**: Confirmed. Unit test suite passes without regressions.
