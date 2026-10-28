# PORT-11A — GM1.10C ROM Evidence Verification for Runtime Prerequisites (U1, U2, U3)

**Date**: 2026-10-28  
**Author**: Gemini (Primary Research Engineer)  
**Tech Lead**: ChatGPT  
**Independent Reviewer**: Claude  
**Repository Baseline**: `https://github.com/s4urj3ng/g3x-lite` @ `origin/main` commit `7cf565e1eff188f4c2b342108eafe5ee688f4f8c` (merged PR #14)  
**Research Worktree**: `/Users/avp/Project/g3x-lite-port11a` (`research/port11a-gm110c-rom-evidence`)  
**Authorization Scope**: Owner-approved, bounded, read-only offline inspection of the verified GM1.10C `PRIMARY.BIN` firmware dump for U1, U2, and U3 only.  
**Hardware Status**: **STRICT NO-GO** (Read-only offline firmware inspection only; zero firmware modification, zero hook installation, zero compilation, zero SD-card or camera operations).

---

## 1. Executive Summary & Prerequisite Verdicts

Using bounded, read-only inspection of the verified Canon PowerShot G3 X **GM1.10C** firmware image (`PRIMARY.BIN`, SHA-256 `99118557...2578`) and two independent instruction-decoding methods (Capstone 5.0.6 disassembly and standalone ARMv7-A/R bitfield/PC-relative arithmetic verification), this milestone resolves the static ROM evidence for **U1**, **U2**, and **U3**:

| Prerequisite | PORT-10A Status | PORT-11A ROM Evidence Verdict | Summary of Direct GM1.10C ROM Proof |
|---|:---:|:---:|---|
| **U1 (`create_task_prologue_verified`)** | `UNKNOWN / CONTRADICTED` | **VERIFIED (Static ROM / ATCM Copy Source)** | `boot()` (`0xFC020040..0xFC020052`) copies ROM `0xFCEEF24C` to ATCM `0xBFE10800..0xBFE17419`. Veneer `0xFC31BBC4` jumps to `0xBFE14A3D` (ROM source `0xFCEF3488`, file offset `0xEF3488`). The 8-byte prologue at `0xBFE14A3C..0xBFE14A43` is **`2d e9 fe 43` (`push.w {r1-r9, lr}`), `04 46` (`mov r4, r0`), `85 48` (`ldr r0, [pc, #0x214]`)** loading literal **`0x00008160`** from `0xBFE14C58` (ROM `0xFCEF36A4`), with continuation at **`0xBFE14A45`**. The competing `push {r4, r5, r6, lr}` claim is **CONTRADICTED**. |
| **U2 (`init_file_modules_entry_verified`)** | `UNKNOWN / CONTRADICTED` | **PARTIALLY VERIFIED (Task Identity & Entry `0xFC0BD071` VERIFIED; Mount Readiness Semantics NOT ESTABLISHED)** | Creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`) calls `j_CreateTask` (`0xFC31BBC4`) with name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack `0x1000`, and entry **`0xFC0BD071`** (loaded from `0xFC0BD1A8`). The competing `0xFC0BD049` address is **CONTRADICTED** (points to data word `0xFC66BBB0` at `0xFC0BD048`). However, first callee `sub_fc0d9ccc` (`0xFC0D9CCC..0xFC0D9CF5`) contains zero conditional branches and **unconditionally returns `r0 = 0`**, proving that `r4 == 0` in `task_InitFileModules` does **not** verify dynamic SD card mount readiness. |
| **U3 (`physw_entry_verified`)** | `INFERRED (creator) / UNKNOWN (entry)` | **VERIFIED (Static Creator, Task Entry `0xFC1283AD`, and Call Path)** | Stock `task_Startup` calls `bl 0xFC1283D2` at `0xFC05B92E`. `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`) is **VERIFIED** as the `PhySw` creator: it passes `"PhySw"` (`0xFC12870C`), priority `0x17`, stack `0x800`, and task entry **`0xFC1283AD`** (loaded from `0xFC128708`) to veneer `0xFC31BE8C` (`CreateTaskStrictly` @ `0xBFE154E8`), which in turn calls `CreateTask` (`0xBFE14A3C`) at `0xBFE154F2`. The periodic loop at `0xFC1283AC..0xFC1283D1` is **VERIFIED** in GM1.10C ROM. |

> [!IMPORTANT]
> **Governance & Precondition Flag Boundary**: Per PORT-11A scope instructions, `GM110C_PRECONDITIONS` in [`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py) is **not modified** in this research milestone. Furthermore, because `task_InitFileModules` completion does not establish physical SD card mount readiness across warm restart (and warm restart blockers `BLK-16` P11–P13/P15 remain open), runtime hook activation and hardware execution remain **STRICT NO-GO**.

---

## 2. Firmware Identity, Methodology, and Bounded Slices

### 2.1 Firmware Identity & Baseline Verification

| Parameter | Verified Value |
|---|---|
| **Firmware Image Path** | `/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN` (untracked/git-ignored) |
| **Camera / Firmware Revision** | Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8` = 12968) |
| **File Size** | `33,554,432` bytes (`0x02000000`, 32 MiB) |
| **Mapped ROM Base VMA** | `0xFC000000` ($\text{VMA} = 0\text{xFC000000} + \text{file\_offset}$) |
| **Verified SHA-256** | `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` |
| **Git Base Commit** | `7cf565e1eff188f4c2b342108eafe5ee688f4f8c` (`origin/main`, merged PR #14) |

### 2.2 Dual Independent Verification Methods

Every instruction sequence, literal pool load, and branch target reported in this document was verified using two independent technical methods on the same raw file offsets:
1. **Method A (Disassembler Engine)**: Capstone 5.0.6 (`capstone.Cs(CS_ARCH_ARM, CS_MODE_THUMB)` for Thumb/Thumb-2 code and `CS_MODE_ARM` for 32-bit ARM kernel veneers).
2. **Method B (Manual / Bitfield & Architectural Formula Decoder)**: Direct little-endian halfword/word unpacking (`struct.unpack_from("<HH", ...)` / `"<I"`) checked against the ARMv7-A/R Architecture Reference Manual (DDI 0406C) bitfield encodings:
   - 16-bit `LDR (literal)` (`01001 Rt[10:8] imm8[7:0]`): $\text{Target} = \text{Align}(\text{PC}, 4) + (\text{imm8} \ll 2)$, where $\text{PC} = \text{InstrAddr} + 4$.
   - 16-bit `ADR` (`10100 Rd[10:8] imm8[7:0]`): $\text{Target} = \text{Align}(\text{PC}, 4) + (\text{imm8} \ll 2)$.
   - 32-bit Thumb-2 `PUSH.W` / `STMDB SP!, {...}` (`0xE92D` followed by register mask halfword `0x43FE`).
   - 32-bit Thumb-2 `BL` / `BLX (immediate)` (`11110 S imm10` / `11 J1 L J2 imm11`): $I_1 = \neg(J_1 \oplus S)$, $I_2 = \neg(J_2 \oplus S)$, signed 25-bit displacement added to $\text{InstrAddr} + 4$ (or $\text{Align}(\text{InstrAddr} + 4, 4)$ for `BLX`).

### 2.3 Bounded ROM Slices Inspected

No unrestricted ROM-wide exploration was performed. The investigation was bounded to the following specific slices (totaling **1,284 bytes** of primary target regions), each pinned by SHA-256 for deterministic reproduction:

| Slice ID | Purpose | ROM VMA Range (Inclusive) | File Offset Range | Size | Slice SHA-256 |
|---|---|---|---:|---:|---|
| **S1A** | Early boot ATCM copy loop & literal pool | `0xFC020040..0xFC0200CF` | `0x020040..0x0200CF` | 144 B | `a8bea578f65643701322d3ce2fc500d04485323dbb28bfab6e89a51a6344c54b` |
| **S1B** | `j_CreateTask` kernel veneer | `0xFC31BBC4..0xFC31BBCB` | `0x31BBC4..0x31BBCB` | 8 B | `e7f6fb4484c3a010e0db4a97edd252a10e92c529f0e75190a0cf98a479fa566d` |
| **S1C** | `CreateTask` body & literals in ATCM ROM source (`0xBFE14A3C..0xBFE14C67`) | `0xFCEF3488..0xFCEF36B3` | `0xEF3488..0xEF36B3` | 556 B | `409dcaec41a0e5aeba37110254919995f018aae13fcc942b832ffc244c223b36` |
| **S1D** | `j_CreateTaskStrictly` kernel veneer | `0xFC31BE8C..0xFC31BE93` | `0x31BE8C..0x31BE93` | 8 B | `f4a9356c75017083e2dbabbc309815595ae745a3787bbb5128e1e823601079b3` |
| **S1E** | `CreateTaskStrictly` body in ATCM ROM source (`0xBFE154E8..0xBFE15509`) | `0xFCEF3F34..0xFCEF3F55` | `0xEF3F34..0xEF3F55` | 34 B | `ce4d1016656cd6053e9808a6cf718d18e885948f0b7102a15cef88bcaacad612` |
| **S2A** | `task_InitFileModules`, creator `sub_fc0bd0b4`, and literal/string pool | `0xFC0BD070..0xFC0BD1BB` | `0x0BD070..0x0BD1BB` | 332 B | `2c939717866f0a5c4c8df88e8f75942890347cdd7453fbe54bdcc33125020c94` |
| **S2B** | `task_InitFileModules` callees (`sub_fc0d9ccc`, `sub_fc0d9cf6`) | `0xFC0D9CCC..0xFC0D9D25` | `0x0D9CCC..0x0D9D25` | 90 B | `4e3f0f99e5605d08d6ba093146e86f009b28121220c632dae05f0a479e218ee8` |
| **S3A** | `task_PhySw` (`0xFC1283AC`) & creator `sub_fc1283d2` (`0xFC1283D2`) | `0xFC1283AC..0xFC1283FF` | `0x1283AC..0x1283FF` | 84 B | `8d38c2112b67283d302f77bd881ab9ccf4b2f7f1b4bfffc51bb531fd2151385a` |
| **S3B** | `PhySw` literal and string pool | `0xFC128704..0xFC12871F` | `0x128704..0x12871F` | 28 B | `fdace2c951b23e71497dab6d9e160a439a72f20f24fbcb362bbd014d3714b376` |

---

## 3. Phase 2 — U1: `CreateTask` Prologue and Continuation Evidence

### 3.1 ATCM Copy Loop Verification (Slice S1A)

During early boot (`0xFC020040..0xFC020052`), stock GM1.10C firmware populates the ARM Cortex-R4/A9 ATCM region (`0xBFE10800..0xBFE17419`) from ROM:

| ROM Address | File Offset | Raw Bytes | Instruction | Resolved Operand / Literal | Status |
|---|---:|---|---|---|---|
| `0xFC020040` | `0x020040` | `20 48` | `ldr r0, [pc, #0x80]` | `[0xFC0200C4] = 0xFCEEF24C` (ROM source start) | **VERIFIED** |
| `0xFC020042` | `0x020042` | `21 49` | `ldr r1, [pc, #0x84]` | `[0xFC0200C8] = 0xBFE10800` (ATCM dest start) | **VERIFIED** |
| `0xFC020044` | `0x020044` | `21 4b` | `ldr r3, [pc, #0x84]` | `[0xFC0200CC] = 0xBFE17419` (ATCM dest limit) | **VERIFIED** |
| `0xFC020046` | `0x020046` | `99 42` | `cmp r1, r3` | Loop while `r1 < 0xBFE17419` | **VERIFIED** |
| `0xFC020048` | `0x020048` | `3c bf` | `itt lo` | Conditional block | **VERIFIED** |
| `0xFC02004A` | `0x02004A` | `50 f8 04 2b` | `ldrlo r2, [r0], #4` | Read 32-bit word from ROM `r0`, post-increment | **VERIFIED** |
| `0xFC02004E` | `0x02004E` | `41 f8 04 2b` | `strlo r2, [r1], #4` | Write 32-bit word to ATCM `r1`, post-increment | **VERIFIED** |
| `0xFC020052` | `0x020052` | `f8 d3` | `blo 0xFC020046` | Repeat until `r1 == 0xBFE1741C` | **VERIFIED** |

**Exact Mapping Formula**:
For any runtime address $\text{VMA} \in [0\text{xBFE10800}, 0\text{xBFE1741C})$:
$$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (\text{VMA} - 0\text{xBFE10800}), \qquad \text{File\_Offset} = \text{ROM\_VMA} - 0\text{xFC000000}$$

Applying this formula to `CreateTask` at runtime address `0xBFE14A3C`:
$$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (0\text{xBFE14A3C} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x423C} = \mathbf{0\text{xFCEF3488}} \quad (\text{File Offset } \mathbf{0\text{x00EF3488}})$$

### 3.2 Kernel Veneer `j_CreateTask` at `0xFC31BBC4` (Slice S1B)

Callers in ROM invoke `CreateTask` via `blx 0xFC31BBC4` (switching from Thumb to ARM state at `0xFC31BBC4`):

| ROM Address | File Offset | Raw Bytes | 32-bit LE Word | ARM Instruction / Data | Effect | Status |
|---|---:|---|---|---|---|---|
| `0xFC31BBC4` | `0x31BBC4` | `04 f0 1f e5` | `0xE51FF004` | `ldr pc, [pc, #-4]` | Loads `pc` from `0xFC31BBC4 + 8 - 4 = 0xFC31BBC8` | **VERIFIED** |
| `0xFC31BBC8` | `0x31BBC8` | `3d 4a e1 bf` | `0xBFE14A3D` | `.word 0xBFE14A3D` | Branches to `0xBFE14A3C` in **Thumb state** (bit 0 = 1) | **VERIFIED** |

### 3.3 `CreateTask` Body and Literal Pool in ATCM Copy Source (Slice S1C)

Disassembly and manual bitfield decoding of `CreateTask` (`0xBFE14A3C..0xBFE14AAE`, ROM source `0xFCEF3488..0xFCEF34FA`, file offset `0x00EF3488..0x00EF34FA`):

| ATCM VMA | ROM Source VMA | File Offset | Raw Bytes | Size | Thumb/Thumb-2 Instruction | Direct Effect / Resolved Target | Status |
|---|---|---:|---|---:|---|---|---|
| **`0xBFE14A3C`** | **`0xFCEF3488`** | **`0xEF3488`** | **`2d e9 fe 43`** | **4 B** | **`push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}`** | **Pushes 10 registers (40 bytes) onto stack (`stmdb sp!, {r1-r9, lr}`)** | **VERIFIED** |
| **`0xBFE14A40`** | **`0xFCEF348C`** | **`0xEF348C`** | **`04 46`** | **2 B** | **`mov r4, r0`** | **Saves `r0` (`name` pointer) into `r4`** | **VERIFIED** |
| **`0xBFE14A42`** | **`0xFCEF348E`** | **`0xEF348E`** | **`85 48`** | **2 B** | **`ldr r0, [pc, #0x214]`** | **Loads `r0 = [0xBFE14C58] = 0x00008160` (ROM `0xFCEF36A4`)** | **VERIFIED** |
| **`0xBFE14A44`** | **`0xFCEF3490`** | **`0xEF3490`** | `0e 46` | 2 B | `mov r6, r1` | **Continuation instruction (`0xBFE14A45`)**; saves `priority` (`r1`) in `r6` | **VERIFIED** |
| `0xBFE14A46` | `0xFCEF3492` | `0xEF3492` | `15 46` | 2 B | `mov r5, r2` | Saves `stack_size` (`r2`) in `r5` | **VERIFIED** |
| `0xBFE14A48` | `0xFCEF3494` | `0xEF3494` | `dd f8 28 80` | 4 B | `ldr.w r8, [sp, #0x28]` | Loads 5th argument (`arg`) across 40-byte (`0x28`) `push.w` stack frame | **VERIFIED** |
| `0xBFE14A4C` | `0xFCEF3498` | `0xEF3498` | `1f 46` | 2 B | `mov r7, r3` | Saves `entry` function pointer (`r3`) in `r7` | **VERIFIED** |
| `0xBFE14A4E` | `0xFCEF349A` | `0xEF349A` | `00 68` | 2 B | `ldr r0, [r0]` | Reads `*(uint32_t *)0x00008160` (ISR nesting / context counter) | **VERIFIED** |
| `0xBFE14A50` | `0xFCEF349C` | `0xEF349C` | `00 28` | 2 B | `cmp r0, #0` | Checks whether `[0x00008160] <= 0` | **VERIFIED** |
| `0xBFE14A52` | `0xFCEF349E` | `0xEF349E` | `04 dd` | 2 B | `ble 0xBFE14A5E` | Normal path if not in interrupt context | **VERIFIED** |
| `0xBFE14A54` | `0xFCEF34A0` | `0xEF34A0` | `98 22` | 2 B | `movs r2, #0x98` | Line 152 (`0x98`) for `DebugAssert` | **VERIFIED** |
| `0xBFE14A56` | `0xFCEF34A2` | `0xEF34A2` | `00 20` | 2 B | `movs r0, #0` | Assert condition `0` | **VERIFIED** |
| `0xBFE14A58` | `0xFCEF34A4` | `0xEF34A4` | `80 a1` | 2 B | `adr r1, #0x200` | Resolves to `0xBFE14C5C` (`"KerTask.c"`, ROM `0xFCEF36A8`) | **VERIFIED** |
| `0xBFE14A5A` | `0xFCEF34A6` | `0xEF34A6` | `ff f7 0e ea` | 4 B | `blx 0xBFE13E78` | Calls `DebugAssert(0, "KerTask.c", 0x98)` | **VERIFIED** |
| `0xBFE14A5E` | `0xFCEF34AA` | `0xEF34AA` | `7d 49` | 2 B | `ldr r1, [pc, #0x1f4]` | Loads `r1 = [0xBFE14C54] = 0x000081CC` (ROM `0xFCEF36A0`) | **VERIFIED** |
| `0xBFE14A60..` | `0xFCEF34AC..` | `0xEF34AC..` | `...` | 46 B | Validates priority/entry, calls `0xBFE10B88` & `0xBFE10D14` | Epilogue at `0xBFE14A78`: `bd e8 fe 83` (`pop.w {r1-r9, pc}`) | **VERIFIED** |

**Referenced Literal Pool in ATCM Copy Source (`0xBFE14C54..0xBFE14C67`, ROM `0xFCEF36A0..0xFCEF36B3`)**:
- `0xBFE14C54` (ROM `0xFCEF36A0`, off `0xEF36A0`): `cc 81 00 00` $\to$ `0x000081CC` (default task attribute block).
- `0xBFE14C58` (ROM `0xFCEF36A4`, off `0xEF36A4`): `60 81 00 00` $\to$ **`0x00008160`** (loaded by `0xBFE14A42: ldr r0, [pc, #0x214]`: $\text{Align}(0\text{xBFE14A42}+4, 4) + 0\text{x214} = 0\text{xBFE14A44} + 0\text{x214} = 0\text{xBFE14C58}$).
- `0xBFE14C5C..0xBFE14C65` (ROM `0xFCEF36A8..0xFCEF36B1`, off `0xEF36A8`): `4b 65 72 54 61 73 6b 2e 63 00` $\to$ ASCII `"KerTask.c\0"`.

### 3.4 Resolution of the PORT-10A U1 Contradiction

1. **Why `CHDK_PORT0B_STUBS_AUDIT.md` Contained Conflicting Prologues**:
   - At `0xBFE14A3C` (ROM `0xFCEF3488`), the actual instruction is `2d e9 fe 43` = **`push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}`** (4 bytes), matching the matching `pop.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, pc}` (`bd e8 fe 83`) at `0xBFE14A78` and the 40-byte stack offset `ldr.w r8, [sp, #0x28]` at `0xBFE14A48`.
   - Immediately after `"KerTask.c\0"` and literal `0x00008404` (`0xBFE14C68`), the next function in ATCM (`0xBFE14C6C`, ROM `0xFCEF36B8`) begins with `70 b5 04 46` (`push {r4, r5, r6, lr}; mov r4, r0`), and `task_InitFileModules` (`0xFC0BD070`) also begins with `70 b5` (`push {r4, r5, r6, lr}`).
   - Therefore, the `push {r4, r5, r6, lr}` entry in `CHDK_PORT0B_STUBS_AUDIT.md:33` is **CONTRADICTED** by primary ROM bytes, while `push.w {r1-r9, lr}` (`2d e9 fe 43`) is **VERIFIED**.
2. **Exact 8-Byte Patch Boundary and Continuation Requirements**:
   - The first three instructions at `0xBFE14A3C` occupy **exactly 8 bytes** (`4 + 2 + 2 = 8` bytes, `0xBFE14A3C..0xBFE14A43`), ending cleanly on the instruction boundary `0xBFE14A44` (`mov r6, r1`).
   - Any future 8-byte trampoline installed at `0xBFE14A3C` (`ldr.w pc, [pc, #0]` + target address) overwrites:
     1. `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` (`0xBFE14A3C`, 4 B)
     2. `mov r4, r0` (`0xBFE14A40`, 2 B)
     3. `ldr r0, [pc, #0x214]` (`0xBFE14A42`, 2 B — PC-relative load of `0x00008160`)
   - And must replay those three operations (loading `r0 = 0x00008160`) before branching to **`0xBFE14A45`** (`0xBFE14A44 | 1`).

---

## 4. Phase 3 — U2: `InitFileModules` Task Identity and Completion Semantics

### 4.1 Task Creation Site: `sub_fc0bd0b4` (Slice S2A)

Inspection of `0xFC0BD070..0xFC0BD1BB` (file offset `0x000BD070..0x000BD1BB`) identifies both the creator function (`sub_fc0bd0b4` at `0xFC0BD0B4..0xFC0BD0DB`) and the task entry (`task_InitFileModules` at `0xFC0BD070..0xFC0BD09B`):

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Effect / Resolved Target | Status |
|---|---:|---|---|---|---|
| `0xFC0BD0B4` | `0x0BD0B4` | `3a 48` | `ldr r0, [pc, #0xe8]` | Loads `r0 = [0xFC0BD1A0] = 0x00008BB8` (state struct) | **VERIFIED** |
| `0xFC0BD0B6` | `0x0BD0B6` | `08 b5` | `push {r3, lr}` | Saves `lr` and allocates 4-byte stack slot `[sp]` | **VERIFIED** |
| `0xFC0BD0B8` | `0x0BD0B8` | `41 68` | `ldr r1, [r0, #4]` | Reads `*(uint32_t *)0x00008BBC` (created guard flag) | **VERIFIED** |
| `0xFC0BD0BA` | `0x0BD0BA` | `00 29` | `cmp r1, #0` | Checks if already created | **VERIFIED** |
| `0xFC0BD0BC` | `0x0BD0BC` | `0d d1` | `bne 0xFC0BD0DA` | If `*(0x00008BBC) != 0`, return immediately | **VERIFIED** |
| `0xFC0BD0BE` | `0x0BD0BE` | `01 21` | `movs r1, #1` | | **VERIFIED** |
| `0xFC0BD0C0` | `0x0BD0C0` | `41 60` | `str r1, [r0, #4]` | Sets `*(0x00008BBC) = 1` | **VERIFIED** |
| `0xFC0BD0C2` | `0x0BD0C2` | `38 48` | `ldr r0, [pc, #0xe0]` | Loads `r0 = [0xFC0BD1A4] = 0xFC0BD0B1` | **VERIFIED** |
| `0xFC0BD0C4` | `0x0BD0C4` | `5e f2 d8 e8` | `blx 0xFC31B278` | Registers callback `0xFC0BD0B1` (`0xFC0BD0B0: b.w 0xFC31B280`) | **VERIFIED** |
| `0xFC0BD0C8` | `0x0BD0C8` | `00 23` | `movs r3, #0` | | **VERIFIED** |
| `0xFC0BD0CA` | `0x0BD0CA` | `00 93` | `str r3, [sp]` | 5th argument to `CreateTask`: `arg = 0` | **VERIFIED** |
| **`0xFC0BD0CC`** | **`0x0BD0CC`** | **`36 4b`** | **`ldr r3, [pc, #0xd8]`** | **Loads `r3 = [0xFC0BD1A8] = 0xFC0BD071` (`task_InitFileModules`)** | **VERIFIED** |
| **`0xFC0BD0CE`** | **`0x0BD0CE`** | **`19 21`** | **`movs r1, #0x19`** | **`priority = 0x19` (25)** | **VERIFIED** |
| **`0xFC0BD0D0`** | **`0x0BD0D0`** | **`36 a0`** | **`adr r0, #0xd8`** | **`name = 0xFC0BD1AC` (`"InitFileModules"`)** | **VERIFIED** |
| **`0xFC0BD0D2`** | **`0x0BD0D2`** | **`41 f2 00 02`** | **`movw r2, #0x1000`** | **`stack_size = 0x1000` (4096 bytes)** | **VERIFIED** |
| **`0xFC0BD0D6`** | **`0x0BD0D6`** | **`5e f2 76 ed`** | **`blx 0xFC31BBC4`** | **Calls `j_CreateTask` veneer (`-> 0xBFE14A3D`)** | **VERIFIED** |
| `0xFC0BD0DA` | `0x0BD0DA` | `08 bd` | `pop {r3, pc}` | Returns | **VERIFIED** |

**Literal & String Pool (`0xFC0BD1A0..0xFC0BD1BB`, file offset `0x000BD1A0..0x000BD1BB`)**:
- `0xFC0BD1A0`: `b8 8b 00 00` (`0x00008BB8`)
- `0xFC0BD1A4`: `b1 d0 0b fc` (`0xFC0BD0B1`)
- `0xFC0BD1A8`: `71 d0 0b fc` (**`0xFC0BD071`** — exact Thumb entry pointer for `task_InitFileModules`)
- `0xFC0BD1AC..0xFC0BD1BB`: `49 6e 69 74 46 69 6c 65 4d 6f 64 75 6c 65 73 00` (**`"InitFileModules\0"`**)

**Callers of `sub_fc0bd0b4` (`0xFC0BD0B4`)**:
`sub_fc0bd0b4` is called via `bl 0xFC0BD0B4` from `0xFC079130` (file offset `0x079130`), `0xFC324A04` (`0x324A04`), `0xFC324A20` (`0x324A20`), and `0xFC324C00` (`0x324C00`)—not directly inside `task_Startup` (`0xFC05B8FC`). Consequently, intercepting `task_InitFileModules` requires `CreateTask` interception (`I1`) rather than a direct call replacement in `task_Startup_my`.

### 4.2 Contradiction Resolution: `0xFC0BD071` vs `0xFC0BD049`

- **`0xFC0BD071` (`0xFC0BD070 | 1`) is VERIFIED**: Both the literal word at `0xFC0BD1A8` (`0xFC0BD071`) loaded into `r3` at `0xFC0BD0CC` and the function body starting at `0xFC0BD070` confirm that `task_InitFileModules` is at `0xFC0BD071` in GM1.10C. In this lower ROM segment (`0xFC0BD000..`), GM1.10C and GM1.10E have a `0x0` address offset, whereas the `-0x28` shift between GM1.10E and GM1.10C occurs in higher ROM segments (e.g., `0xFC35B93C` in GM1.10C vs `0xFC35B964` in GM1.10E).
- **`0xFC0BD049` (`0xFC0BD048 | 1`) is CONTRADICTED**: The `-0x28` shifted address `0xFC0BD048` proposed in `PORT-6C` lies inside a literal pool (`0xFC0BD034..0xFC0BD050`) following `0xFC0BD02E: b.w 0xFC31B980`, where word `0xFC0BD048` holds the data pointer `0xFC66BBB0`. Executing `0xFC0BD049` as code would execute data bytes and fault.

### 4.3 `task_InitFileModules` Control Flow (`0xFC0BD070..0xFC0BD09B`) and Callee Semantics (Slices S2A & S2B)

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Effect / Resolved Target | Status |
|---|---:|---|---|---|---|
| **`0xFC0BD070`** | **`0x0BD070`** | `70 b5` | `push {r4, r5, r6, lr}` | Function entry (`0xFC0BD071` Thumb) | **VERIFIED** |
| `0xFC0BD072` | `0x0BD072` | `1c f0 2b fe` | `bl 0xFC0D9CCC` | Calls `sub_fc0d9ccc` | **VERIFIED** |
| `0xFC0BD076` | `0x0BD076` | `04 00` | `movs r4, r0` | Copies `r0` to `r4` and sets flags (`Z=1` if `r0 == 0`) | **VERIFIED** |
| `0xFC0BD078` | `0x0BD078` | `45 f2 06 05` | `movw r5, #0x5006` | Logical event ID `0x5006` | **VERIFIED** |
| `0xFC0BD07C` | `0x0BD07C` | `03 d0` | `beq 0xFC0BD086` | Branches to `0xFC0BD086` if `r0 == 0` | **VERIFIED** |
| `0xFC0BD07E` | `0x0BD07E` | `00 21` | `movs r1, #0` | Error event argument `0` | **VERIFIED** |
| `0xFC0BD080` | `0x0BD080` | `28 46` | `mov r0, r5` | Event `0x5006` | **VERIFIED** |
| `0xFC0BD082` | `0x0BD082` | `9e f2 5b fc` | `bl 0xFC35B93C` | Calls `sub_fc35b93c(0x5006, 0)` | **VERIFIED** |
| `0xFC0BD086` | `0x0BD086` | `1c f0 36 fe` | `bl 0xFC0D9CF6` | Calls `sub_fc0d9cf6` | **VERIFIED** |
| `0xFC0BD08A` | `0x0BD08A` | `00 2c` | `cmp r4, #0` | Re-tests `r4` (return value of `sub_fc0d9ccc`) | **VERIFIED** |
| `0xFC0BD08C` | `0x0BD08C` | `05 d1` | `bne 0xFC0BD09A` | If `r4 != 0`, skip `0x5006` arg `1` notification | **VERIFIED** |
| `0xFC0BD08E` | `0x0BD08E` | `28 46` | `mov r0, r5` | Event `0x5006` | **VERIFIED** |
| `0xFC0BD090` | `0x0BD090` | `bd e8 70 40` | `pop.w {r4, r5, r6, lr}` | Restores registers before tail call | **VERIFIED** |
| `0xFC0BD094` | `0x0BD094` | `01 21` | `movs r1, #1` | Event argument `1` | **VERIFIED** |
| `0xFC0BD096` | `0x0BD096` | `9e f2 51 bc` | `b.w 0xFC35B93C` | Tail-calls `sub_fc35b93c(0x5006, 1)` | **VERIFIED** |
| `0xFC0BD09A` | `0x0BD09A` | `70 bd` | `pop {r4, r5, r6, pc}` | Returns when `r4 != 0` | **VERIFIED** |

**Inspection of Callees `sub_fc0d9ccc` and `sub_fc0d9cf6` (Slice S2B, `0xFC0D9CCC..0xFC0D9D25`)**:
1. **`sub_fc0d9ccc` (`0xFC0D9CCC..0xFC0D9CF5`, file offset `0x0D9CCC`)**:
   ```arm
   0xFC0D9CCC: push  {r4, lr}
   0xFC0D9CCE: bl    0xFC18C13C
   0xFC0D9CD2: bl    0xFC2DD6D4
   0xFC0D9CD6: bl    0xFC18C564
   0xFC0D9CDA: bl    0xFC31375E
   0xFC0D9CDE: bl    0xFC0727D4
   0xFC0D9CE2: mov.w r1, #0x40000
   0xFC0D9CE6: mov.w r0, #0x10A0000
   0xFC0D9CEA: bl    0xFC18EE9C
   0xFC0D9CEE: bl    0xFC18D596
   0xFC0D9CF2: movs  r0, #0          ; <-- UNCONDITIONAL 0 RETURN
   0xFC0D9CF4: pop   {r4, pc}
   ```
   - **Critical Finding**: `sub_fc0d9ccc` contains **zero conditional branches** and unconditionally executes `movs r0, #0; pop {r4, pc}` at `0xFC0D9CF2..0xFC0D9CF4`. Therefore, whenever `sub_fc0d9ccc` returns to `task_InitFileModules` (`0xFC0BD076`), **`r0` (and `r4`) is always `0`**. The `r4 != 0` branch in `task_InitFileModules` is never taken on normal return.
2. **`sub_fc0d9cf6` (`0xFC0D9CF6..0xFC0D9D25`, file offset `0x0D9CF6`)**:
   - Calls `0xFC37AD52(3)` and `0xFC0F9BA4`, checks `*(r4 + 4)` (where `r4 = [0xFC0D9D54]`), optionally runs module callbacks (`0xFC35FAAC`, `0xFC2DD73A`, `0xFC3138CC`, `0xFC35F9A8`, `0xFC2DD7A4`), stores `1` to `[r4]`, and returns `r0 = 1` at `0xFC0D9D20..0xFC0D9D24` (whose return value `task_InitFileModules` ignores).
3. **Why Readiness Semantics Are Not Established by `task_InitFileModules` Alone**:
   - Even if a CHDK hook gates `core_spytask_can_start()` on `r4 == 0` after `sub_fc0d9cf6()`, `r4 == 0` is structurally constant upon return from `sub_fc0d9ccc()`.
   - Neither `sub_fc0d9ccc()` nor `sub_fc0d9cf6()` verifies that the physical SD card has been re-initialized or that the FAT filesystem is mounted (which depends on the separate `SD1stInit` task and storage mounter waiter at `0x010E181E`, `PORT-3C` P11–P13).

---

## 5. Phase 4 — U3: `PhySw` Creator and Task-Entry Evidence

### 5.1 Startup Call Site (`0xFC05B92E`) and Creator Function `sub_fc1283d2` (Slice S3A & S3B)

In stock `task_Startup` (`0xFC05B8FC..0xFC05B958`), instruction `0xFC05B92E` (file offset `0x05B92E`) is `cc f0 50 fd` = **`bl 0xFC1283D2`** (**VERIFIED**).

Disassembly of `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`, file offset `0x001283D2..0x001283FF`):

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Effect / Resolved Target | Status |
|---|---:|---|---|---|---|
| **`0xFC1283D2`** | **`0x1283D2`** | `38 b5` | `push {r3, r4, r5, lr}` | Function entry (`sub_fc1283d2`) | **VERIFIED** |
| `0xFC1283D4` | `0x1283D4` | `5f f7 58 fd` | `bl 0xFC087E88` | Pre-task hardware/switch init helper | **VERIFIED** |
| `0xFC1283D8` | `0x1283D8` | `50 f7 d3 ff` | `bl 0xFC079382` | Mode/state check helper | **VERIFIED** |
| `0xFC1283DC` | `0x1283DC` | `08 b9` | `cbnz r0, 0xFC1283E2` | If non-zero, skip `0xFC087E2C` | **VERIFIED** |
| `0xFC1283DE` | `0x1283DE` | `5f f7 25 fd` | `bl 0xFC087E2C` | Conditional switch helper | **VERIFIED** |
| **`0xFC1283E2`** | **`0x1283E2`** | **`c8 4c`** | **`ldr r4, [pc, #0x320]`** | **Loads `r4 = [0xFC128704] = 0x000082BC`** | **VERIFIED** |
| `0xFC1283E4` | `0x1283E4` | `60 68` | `ldr r0, [r4, #4]` | Reads `*(uint32_t *)0x000082C0` (task handle / created guard) | **VERIFIED** |
| `0xFC1283E6` | `0x1283E6` | `00 28` | `cmp r0, #0` | Checks if `PhySw` task already exists | **VERIFIED** |
| `0xFC1283E8` | `0x1283E8` | `09 d1` | `bne 0xFC1283FE` | If already created, return | **VERIFIED** |
| `0xFC1283EA` | `0x1283EA` | `00 23` | `movs r3, #0` | | **VERIFIED** |
| `0xFC1283EC` | `0x1283EC` | `00 93` | `str r3, [sp]` | 5th argument: `arg = 0` | **VERIFIED** |
| **`0xFC1283EE`** | **`0x1283EE`** | **`c6 4b`** | **`ldr r3, [pc, #0x318]`** | **Loads `r3 = [0xFC128708] = 0xFC1283AD` (`task_PhySw` entry)** | **VERIFIED** |
| **`0xFC1283F0`** | **`0x1283F0`** | **`17 21`** | **`movs r1, #0x17`** | **`priority = 0x17` (23)** | **VERIFIED** |
| **`0xFC1283F2`** | **`0x1283F2`** | **`c6 a0`** | **`adr r0, #0x318`** | **`name = 0xFC12870C` (`"PhySw"`)** | **VERIFIED** |
| **`0xFC1283F4`** | **`0x1283F4`** | **`40 f6 00 02`** | **`movw r2, #0x800`** | **`stack_size = 0x800` (2048 bytes)** | **VERIFIED** |
| **`0xFC1283F8`** | **`0x1283F8`** | **`f3 f1 48 ed`** | **`blx 0xFC31BE8C`** | **Calls `j_CreateTaskStrictly` veneer (`-> 0xBFE154E9`)** | **VERIFIED** |
| `0xFC1283FC` | `0x1283FC` | `60 60` | `str r0, [r4, #4]` | Stores created task handle at `0x000082C0` | **VERIFIED** |
| `0xFC1283FE` | `0x1283FE` | `38 bd` | `pop {r3, r4, r5, pc}` | Returns | **VERIFIED** |

**Literal & String Pool (`0xFC128704..0xFC12871F`, file offset `0x00128704..0x0012871F`)**:
- `0xFC128704`: `bc 82 00 00` (`0x000082BC` — `PhySw` state block in Low RAM)
- `0xFC128708`: `ad 83 12 fc` (**`0xFC1283AD`** — `0xFC1283AC | 1`, exact Thumb entry pointer for `task_PhySw`)
- `0xFC12870C..0xFC128711`: `50 68 79 53 77 00` (**`"PhySw\0"`**)
- `0xFC128714..0xFC12871E`: `50 68 79 53 77 44 72 76 2e 63 00` (**`"PhySwDrv.c\0"`**)

### 5.2 Key Architectural Finding: `CreateTaskStrictly` Veneer (`0xFC31BE8C` $\to$ `0xBFE154E8`, Slices S1D & S1E)

Unlike `sub_fc0bd0b4` (which calls `blx 0xFC31BBC4` $\to$ `CreateTask`), `sub_fc1283d2` at `0xFC1283F8` calls **`blx 0xFC31BE8C`**.

Inspection of veneer `0xFC31BE8C` (Slice S1D) and its ATCM target `0xBFE154E8` (ROM source `0xFCEF3F34`, file offset `0x00EF3F34`, Slice S1E) establishes the exact call chain:
- **`0xFC31BE8C`** (`0x31BE8C`): `04 f0 1f e5` (`ldr pc, [pc, #-4]`) + `e9 54 e1 bf` (`.word 0xBFE154E9`).
- **`0xBFE154E8..0xBFE15509`** (ROM `0xFCEF3F34..0xFCEF3F55`, `CreateTaskStrictly`):
  ```arm
  0xBFE154E8: push  {r3, r4, r5, lr}    ; 38 b5
  0xBFE154EA: mov   r4, r3              ; 1c 46
  0xBFE154EC: ldr   r3, [sp, #0x10]     ; 04 9b (loads caller's 5th arg [sp])
  0xBFE154EE: str   r3, [sp]            ; 00 93 (places 5th arg at [sp])
  0xBFE154F0: mov   r3, r4              ; 23 46 (restores r3 = task entry)
  0xBFE154F2: bl    0xBFE14A3C          ; ff f7 a3 fa -> CALLS CreateTask (0xBFE14A3C)!
  0xBFE154F6: cmp   r0, #5              ; 05 28
  0xBFE154F8: mov   r4, r0              ; 04 46
  0xBFE154FA: bne   0xBFE15506          ; 04 d1
  0xBFE154FC: movs  r2, #0x22           ; 22 22 (line 34 of "KerTask.c")
  0xBFE154FE: movs  r0, #0              ; 00 20
  0xBFE15500: adr   r1, #0x130          ; 4c a1 (0xBFE15634 -> "KerTask.c")
  0xBFE15502: blx   0xBFE13E78          ; fe f7 ba ec (DebugAssert)
  0xBFE15506: mov   r0, r4              ; 20 46
  0xBFE15508: pop   {r3, r4, r5, pc}    ; 38 bd
  ```
- **Architectural Implication**:
  1. `sub_fc1283d2` (`0xFC1283D2`) calls `j_CreateTaskStrictly` (`0xFC31BE8C` $\to$ `0xBFE154E8`), which immediately calls `CreateTask` (`0xBFE14A3C`) at `0xBFE154F2` with the exact same `(r0, r1, r2, r3, [sp])` registers (`r3 = 0xFC1283AD`).
  2. Therefore, `sub_fc1283d2` is **definitively VERIFIED** as the `PhySw` creator function, and a hook at `CreateTask` (`0xBFE14A3C`) intercepts `PhySw` task creation via `CreateTaskStrictly` (while upstream reference ports like G5 X instead replace `bl sub_fc1283d2` in `task_Startup_my` directly so they can also enlarge `r2` from `0x800` to `0x2000`).

### 5.3 Periodic Task Entry `task_PhySw` (`0xFC1283AC..0xFC1283D1`, Slice S3A)

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Effect / Resolved Target | Status |
|---|---:|---|---|---|---|
| **`0xFC1283AC`** | **`0x1283AC`** | `10 b5` | `push {r4, lr}` | **`task_PhySw` entry (`0xFC1283AD` Thumb)** | **VERIFIED** |
| `0xFC1283AE` | `0x1283AE` | `d5 4c` | `ldr r4, [pc, #0x354]` | Loads `r4 = [0xFC128704] = 0x000082BC` | **VERIFIED** |
| `0xFC1283B0` | `0x1283B0` | `08 e0` | `b 0xFC1283C4` | Jumps to loop condition check on initial entry | **VERIFIED** |
| `0xFC1283B2` | `0x1283B2` | `a0 68` | `ldr r0, [r4, #8]` | Loads sleep interval `*(uint32_t *)0x000082C4` | **VERIFIED** |
| `0xFC1283B4` | `0x1283B4` | `f3 f1 e6 ed` | `blx 0xFC31BF84` | Calls `j_SleepTask` veneer | **VERIFIED** |
| `0xFC1283B8` | `0x1283B8` | `00 f0 68 f9` | `bl 0xFC12868C` | Polls physical switch state (`kbd_p1_f` poll stage) | **VERIFIED** |
| `0xFC1283BC` | `0x1283BC` | `01 28` | `cmp r0, #1` | Checks if switch state changed | **VERIFIED** |
| `0xFC1283BE` | `0x1283BE` | `01 d1` | `bne 0xFC1283C4` | Skip dispatch if unchanged | **VERIFIED** |
| `0xFC1283C0` | `0x1283C0` | `ff f7 ad fe` | `bl 0xFC12811E` | Calls switch event dispatch (`kbd_p2_f`) | **VERIFIED** |
| `0xFC1283C4` | `0x1283C4` | `20 68` | `ldr r0, [r4]` | Reads loop active flag `*(uint32_t *)0x000082BC` | **VERIFIED** |
| `0xFC1283C6` | `0x1283C6` | `00 28` | `cmp r0, #0` | Checks termination condition | **VERIFIED** |
| `0xFC1283C8` | `0x1283C8` | `f3 d1` | `bne 0xFC1283B2` | Repeat polling loop while `*(0x000082BC) != 0` | **VERIFIED** |
| `0xFC1283CA` | `0x1283CA` | `bd e8 10 40` | `pop.w {r4, lr}` | Restores `r4, lr` | **VERIFIED** |
| `0xFC1283CE` | `0x1283CE` | `f3 f1 95 ba` | `b.w 0xFC31B8FC` | Tail-calls `j_ExitTask` veneer | **VERIFIED** |

*(Note: The untracked local note `docs/UI001_ROM_RESEARCH.md` omitted instruction `0xFC1283B0: b 0xFC1283C4` in its transcription; the actual ROM bytes at `0xFC1283B0` are `08 e0` = `b 0xFC1283C4`, jumping to the loop condition before the first sleep.)*

---

## 6. Consolidated Cross-Check Against PORT-10A Claims

| ID | Claim / Hypothesis from PORT-10A | GM1.10C ROM Location | Observed ROM Evidence | PORT-11A Classification |
|---|---|---|---|---|
| **C-01** | `boot()` copies ROM `0xFCEEF24C` to ATCM `0xBFE10800..0xBFE17419` | `0xFC020040..0xFC020052` (off `0x020040`) | Literals `0xFCEEF24C` (`0xFC0200C4`), `0xBFE10800` (`0xFC0200C8`), `0xBFE17419` (`0xFC0200CC`) copied word-by-word. | **VERIFIED** |
| **C-02** | `j_CreateTask` veneer at `0xFC31BBC4` branches to `0xBFE14A3D` | `0xFC31BBC4..0xFC31BBCB` (off `0x31BBC4`) | `04 f0 1f e5` (`ldr pc, [pc, #-4]`) + `3d 4a e1 bf` (`0xBFE14A3D`). | **VERIFIED** |
| **C-03** | `CreateTask` prologue is `push {r4, r5, r6, lr}` (`CHDK_PORT0B_STUBS_AUDIT.md:33`) | `0xBFE14A3C` / ROM `0xFCEF3488` (off `0xEF3488`) | Bytes at `0xFCEF3488` are `2d e9 fe 43` (`push.w {r1-r9, lr}`), NOT `70 b5`. | **CONTRADICTED** |
| **C-04** | `CreateTask` prologue is `push.w {r1-r9, lr}` (`2d e9 fe 43`) | `0xBFE14A3C` / ROM `0xFCEF3488` (off `0xEF3488`) | Bytes `2d e9 fe 43 04 46 85 48` (`push.w {r1-r9, lr}; mov r4, r0; ldr r0, [pc, #0x214]`). | **VERIFIED** |
| **C-05** | `CreateTask` opening load fetches literal `0x00008160` and continues at `0xBFE14A45` | `0xBFE14A42` / `0xBFE14C58` (ROM `0xFCEF36A4`) | `ldr r0, [pc, #0x214]` loads `[0xBFE14C58] = 0x00008160`; next instruction at `0xBFE14A44` (`mov r6, r1`). | **VERIFIED** |
| **C-06** | `task_InitFileModules` entry is `0xFC0BD049` (`PORT-6C` `-0x28` shift) | `0xFC0BD048` (off `0x0BD048`) | `0xFC0BD048` contains data pointer `0xFC66BBB0` inside a literal pool. | **CONTRADICTED** |
| **C-07** | `task_InitFileModules` entry is `0xFC0BD071` | `0xFC0BD070..0xFC0BD09B` & `0xFC0BD1A8` | Creator `0xFC0BD0B4` loads `r3 = [0xFC0BD1A8] = 0xFC0BD071` and `r0 = 0xFC0BD1AC` (`"InitFileModules"`). | **VERIFIED** |
| **C-08** | `task_InitFileModules` `r4 == 0` check proves filesystem mount success | `0xFC0D9CCC..0xFC0D9CF5` (off `0x0D9CCC`) | `sub_fc0d9ccc` has zero conditional branches and unconditionally returns `movs r0, #0`. | **CONTRADICTED (for mount readiness proof)** |
| **C-09** | `sub_fc1283d2` is the `PhySw` creator function | `0xFC1283D2..0xFC1283FF` (off `0x1283D2`) | Loads `"PhySw"` (`0xFC12870C`), prio `0x17`, stack `0x800`, entry `0xFC1283AD` (`0xFC128708`), calls `0xFC31BE8C` (`CreateTaskStrictly` $\to$ `CreateTask`). | **VERIFIED** |
| **C-10** | `task_PhySw` entry is `0xFC1283AD` (`0xFC1283AC`) | `0xFC1283AC..0xFC1283D1` & `0xFC128708` | Literal at `0xFC128708` is `0xFC1283AD`; loop at `0xFC1283AC..0xFC1283D1` polls `0xFC12868C` and dispatches `0xFC12811E`. | **VERIFIED** |

---

## 7. Remaining Uncertainties & Implications for PORT-9A / PORT-9B

### 7.1 What Is Now Resolved vs What Remains Unknown

1. **Sufficiently Verified Static Prerequisites**:
   - **U1 (`create_task_prologue_verified`)**: Fully verified at the static ROM/ATCM level (`0xBFE14A3C` entry, 8-byte instruction sequence `2d e9 fe 43 04 46 85 48`, literal `0x00008160` at `0xBFE14C58`, continuation `0xBFE14A45`).
   - **U3 (`physw_entry_verified`)**: Fully verified at the static ROM level (creator `0xFC1283D2`, task entry `0xFC1283AD`, stock priority `0x17`, stock stack `0x800`, and `CreateTaskStrictly` $\to$ `CreateTask` call chain).
   - **U2 Static Task Identity**: Creator `0xFC0BD0B4`, task name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack `0x1000`, task entry `0xFC0BD071`, and task body `0xFC0BD070..0xFC0BD09B` are fully verified.

2. **Remaining Uncertainties (Still `UNKNOWN` / Open Blockers)**:
   - **U2 Filesystem Mount Readiness Semantics**: Because `sub_fc0d9ccc` (`0xFC0D9CCC`) unconditionally returns `0` and `task_InitFileModules` does not wait on the SD card mounter event flag (`[0x0000AC98]`, `PORT-3C` P11–P13), executing `task_InitFileModules` does **not** by itself guarantee that the SD card FAT filesystem is ready for CHDK file I/O across a warm restart.
   - **U4 (`SpyTask` Creation Point, Priority, and Heap Headroom Interaction)**: Remains **UNKNOWN / UNVERIFIED** until a safe readiness signal and DryOS heap reservation (`P07`) are integrated.
   - **Runtime Stack Adequacy & Key Suppression (`I4`)**: Whether `mykbd_task` requires stack enlargement from `0x800` to `0x2000` (which requires replacing `bl sub_fc1283d2` in `task_Startup_my` or overriding `r2` inside `CreateTask_my` when `r3 == 0xFC1283AD`) and how `PostLogicalEventToUI` behaves at runtime remain runtime properties (**UNKNOWN** offline).
   - **Warm Restart Hardware Safety (`BLK-16`)**: Pre-unmask interrupt controller state (`P15`) and SD host/card warm-restart state (`P11–P13`) remain open blockers.

### 7.2 Implications for the PORT-9A / PORT-9B Offline Model

- **PORT-9A (`tools/port9a_runtime_lifecycle.py`)**:
  - In accordance with task instructions, `GM110C_PRECONDITIONS` remains all `False` in this milestone.
  - Furthermore, PORT-11A discovers an important architectural nuance for `U3` / `I4`: in stock GM1.10C, `sub_fc1283d2` passes `r2 = 0x800` to `CreateTaskStrictly` (`0xFC31BE8C`), which forwards `r2 = 0x800` to `CreateTask` (`0xBFE14A3C`). If CHDK redirects `task_PhySw` (`0xFC1283AD`) inside `CreateTask_my` (`I1`) *without* either modifying `r2` (`0x800` $\to$ `0x2000`) in `CreateTask_my` or replacing `bl sub_fc1283d2` with `bl taskcreate_physw_my` in `task_Startup_my`, `mykbd_task` would run on a `0x800`-byte stack instead of `0x2000`.
- **PORT-9B (`tools/port9b_runtime_contract.py`)**:
  - Remains 100% valid (`RESULT ok`; all 51 unit tests pass). Keeping `GM110C_PRECONDITIONS` all `False` ensures `C3` continues to forbid premature activation of `I1–I4` in tracked sources.

---

## 8. Reproducibility Commands

Anyone with access to the local `PRIMARY.BIN` (`SHA-256 = 99118557...2578`) can reproduce the exact slice hashes and disassemblies using standard POSIX tools:

```sh
# 1. Verify firmware image SHA-256
shasum -a 256 /Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN
# Expected: 9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578

# 2. Verify Slice S1C (CreateTask in ATCM ROM copy source: offset 0xEF3488, 556 bytes)
dd if=/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN bs=1 skip=$((0xEF3488)) count=556 2>/dev/null | shasum -a 256
# Expected: 409dcaec41a0e5aeba37110254919995f018aae13fcc942b832ffc244c223b36

# 3. Verify Slice S2A (InitFileModules task, creator, and literals: offset 0x0BD070, 332 bytes)
dd if=/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN bs=1 skip=$((0x0BD070)) count=332 2>/dev/null | shasum -a 256
# Expected: 2c939717866f0a5c4c8df88e8f75942890347cdd7453fbe54bdcc33125020c94

# 4. Verify Slice S3A (task_PhySw and creator sub_fc1283d2: offset 0x1283AC, 84 bytes)
dd if=/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN bs=1 skip=$((0x1283AC)) count=84 2>/dev/null | shasum -a 256
# Expected: 8d38c2112b67283d302f77bd881ab9ccf4b2f7f1b4bfffc51bb531fd2151385a
```

---

## 9. Recommended Next Engineering Milestone

- **Recommended Next Milestone — PORT-11B (Offline Runtime Contract & Precondition Refinement for Verified U1/U3 and Split U2 Semantics)**:
  1. Refine the offline runtime precondition model (`PORT-9A` / `PORT-9B`) to distinguish **static ROM address/instruction verification** (`U1` prologue/literal verified, `U2` entry `0xFC0BD071` verified, `U3` creator `0xFC1283D2` + entry `0xFC1283AD` verified) from **dynamic runtime/mount safety preconditions** (`U2_mount_ready` and `U4_spytask_gate`), so that recording verified ROM facts in the model does **not** weaken fail-closed enforcement (`C3` must still forbid active hooks in source while `U2_mount_ready` and `U4` remain `False`).
  2. Model the newly discovered `CreateTaskStrictly` (`0xFC31BE8C` $\to$ `0xBFE154E8` $\to$ `0xBFE14A3C`) call path and stack-size (`0x800` vs `0x2000`) invariant for `PhySw` in the offline contract.
  3. Keep all runtime hooks disabled in source and maintain **Hardware STRICT NO-GO**.
