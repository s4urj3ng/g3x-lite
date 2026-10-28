# PORT-11A — GM1.10C ROM Evidence Verification for Runtime Prerequisites (U1, U2, U3)

**Date**: 2026-10-28  
**Author**: Gemini (Primary Research Engineer)  
**Tech Lead**: ChatGPT  
**Independent Reviewer**: Claude  
**Repository Baseline**: `https://github.com/s4urj3ng/g3x-lite` @ `origin/main` commit `7cf565e1eff188f4c2b342108eafe5ee688f4f8c` (merged PR #14)  
**Research Worktree**: `/Users/avp/Project/g3x-lite-port11a` (`research/port11a-gm110c-rom-evidence`)  
**Authorization Scope**: Owner-approved, bounded, read-only offline inspection of the local-only GM1.10C `PRIMARY.BIN` firmware dump for U1, U2, and U3 only (see §2.3–§2.4 for pinned slices and process-deviation disclosure).  
**Hardware Status**: **STRICT NO-GO** (Read-only offline firmware inspection only; zero firmware modification, zero hook installation, zero compilation, zero SD-card or camera operations).

---

## 1. Executive Summary & Prerequisite Verdicts

Using read-only offline inspection of the local-only Canon PowerShot G3 X **GM1.10C** firmware image (`PRIMARY.BIN`, SHA-256 `99118557...2578`), cross-checked by one agent using two decoding representations (Capstone 5.0.6 disassembly and manual ARMv7-R bitfield/PC-relative arithmetic decoding) and subsequently reviewed by Claude against the nine pinned ROM slices (`S1A`–`S3B`), this milestone establishes the static ROM evidence for **U1**, **U2**, and **U3**:

| Prerequisite | PORT-10A Status | PORT-11A Static ROM Verdict | Summary of Direct GM1.10C ROM Proof & Remaining Boundaries |
|---|:---:|:---:|---|
| **U1 (`create_task_prologue_verified`)** | `UNKNOWN / CONTRADICTED` | **`STATIC_VERIFIED` (Static ROM / ATCM Copy Source Only; Runtime Hook Safety `UNKNOWN`)** | `boot()` (`0xFC020040..0xFC020052`) copies `6,919` 32-bit words (`27,676` B) from ROM `0xFCEEF24C..0xFCEF5E67` to Cortex-R4 ATCM `0xBFE10800..0xBFE1741B` (loop limit literal `[0xFC0200CC] = 0xBFE17419`). ARM veneer at `0xFC31BBC4` (`j_CreateTask` `[INFERRED]`) jumps to `0xBFE14A3D` (Thumb instruction address `0xBFE14A3C`, ROM source `0xFCEF3488`, file offset `0xEF3488`). The 8-byte prologue at `0xBFE14A3C..0xBFE14A43` is **`2d e9 fe 43` (`push.w {r1-r9, lr}`), `04 46` (`mov r4, r0`), `85 48` (`ldr r0, [pc, #0x214]`)** loading literal **`0x00008160`** from `0xBFE14C58` (ROM `0xFCEF36A4`). The next instruction (`0e 46` = `mov r6, r1`) is at instruction address **`0xBFE14A44`** (Thumb interworking continuation pointer **`0xBFE14A45`**). The competing `push {r4, r5, r6, lr}` claim at `0xBFE14A3C` is **CONTRADICTED**. |
| **U2 (`init_file_modules_entry_verified`)** | `UNKNOWN / CONTRADICTED` | **PARTIAL: Task Identity & Entry `0xFC0BD071` `STATIC_VERIFIED`; Filesystem Mount Readiness `UNKNOWN / NOT ESTABLISHED`** | Creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`) invokes `0xFC31BBC4` (`j_CreateTask` `[INFERRED]`) with ASCII name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack `0x1000`, and Thumb entry pointer **`0xFC0BD071`** (instruction address `0xFC0BD070`, loaded from `[0xFC0BD1A8]`). The competing `0xFC0BD049` address is **CONTRADICTED** (`0xFC0BD048` holds literal word `0xFC66BBB0`, logged outside `S2A`). First callee `sub_fc0d9ccc` (`0xFC0D9CCC..0xFC0D9CF5`) contains zero conditional branches of its own and ends with `movs r0, #0; pop {r4, pc}`; thus **`r0 = 0` (`r4 == 0`) is constant on normal return** of `sub_fc0d9ccc` and cannot establish dynamic SD/FAT mount readiness (`UNKNOWN`). |
| **U3 (`physw_entry_verified`)** | `INFERRED (creator) / UNKNOWN (entry)` | **`STATIC_VERIFIED` (Static Creator `0xFC1283D2`, Entry `0xFC1283AD`, and `CreateTaskStrictly` Call Chain; Runtime Hook Safety `UNKNOWN`)** | Stock `task_Startup` calls `bl 0xFC1283D2` at `0xFC05B92E` (logged outside `S3A`). `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`) passes `"PhySw"` (`0xFC12870C`), priority `0x17`, stack `0x800`, `arg = 0`, and Thumb entry pointer **`0xFC1283AD`** (instruction address `0xFC1283AC`, loaded from `[0xFC128708]`) to ARM veneer `0xFC31BE8C` (`j_CreateTaskStrictly` `[INFERRED]` $\to$ `0xBFE154E9`), which preserves `r0–r3` and forwards `[sp]` to `0xBFE14A3C` (`CreateTask` `[INFERRED]`) via `0xBFE154F2: bl 0xBFE14A3C`. The loop body at `0xFC1283AC..0xFC1283D1` is `STATIC_VERIFIED` in GM1.10C ROM. |

> [!IMPORTANT]
> **Governance & Precondition Flag Boundary**:
> 1. `STATIC_VERIFIED` in this report applies **strictly to static ROM bytes, instruction encodings, register/stack effects, and literal pool values**. Symbolic/semantic labels (`CreateTask`, `CreateTaskStrictly`, `task_InitFileModules`, `task_PhySw`, `SleepTask`, `kbd_p1_f`, `kbd_p2_f`, etc.) are classified as **`INFERRED`**, and uninspected callee bodies or runtime properties remain **`UNKNOWN`**.
> 2. Per PORT-11A scope instructions, `GM110C_PRECONDITIONS` in [`tools/port9a_runtime_lifecycle.py`](../tools/port9a_runtime_lifecycle.py) is **not modified** (all four flags remain `False`). Runtime hook activation and hardware execution remain **STRICT NO-GO**.

---

## 2. Firmware Identity, Methodology, Pinned Slices, and Process Deviation Disclosure

### 2.1 Firmware Identity & Local-Only Artifact Provenance

| Parameter | Verified Value & Provenance |
|---|---|
| **Firmware Image Path** | `/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN` (**local-only, git-ignored/untracked proprietary artifact**; never committed to git and absent in clean checkouts/CI) |
| **Camera / Firmware Revision** | Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8` = 12968, DryOS on **ARM Cortex-R4** / ARMv7-R) |
| **File Size** | `33,554,432` bytes (`0x02000000`, 32 MiB) |
| **Mapped ROM Base VMA** | `0xFC000000` ($\text{VMA} = 0\text{xFC000000} + \text{file\_offset}$) |
| **Verified SHA-256** | `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` |
| **Git Base Commit** | `7cf565e1eff188f4c2b342108eafe5ee688f4f8c` (`origin/main`, merged PR #14) |

### 2.2 Single-Agent Cross-Checking Using Two Decoding Representations

Every instruction sequence, literal pool load, and branch target inside the pinned slices was **cross-checked by one agent (Gemini)** using two decoding representations on the same raw file offsets (and subsequently verified by Claude during independent review):
1. **Representation A (Disassembler Engine)**: Capstone 5.0.6 (`capstone.Cs(CS_ARCH_ARM, CS_MODE_THUMB)` for Thumb/Thumb-2 code and `CS_MODE_ARM` for 32-bit ARM kernel veneers).
2. **Representation B (Manual ARMv7-R Bitfield & Architectural Formula Decoding)**: Direct little-endian halfword/word unpacking (`struct.unpack_from("<HH", ...)` / `"<I"`) checked against the ARMv7-R Architecture Reference Manual (DDI 0406C) bitfield encodings:
   - 16-bit `LDR (literal)` (`01001 Rt[10:8] imm8[7:0]`): $\text{Target} = \text{Align}(\text{PC}, 4) + (\text{imm8} \ll 2)$, where $\text{PC} = \text{InstrAddr} + 4$.
   - 16-bit `ADR` (`10100 Rd[10:8] imm8[7:0]`): $\text{Target} = \text{Align}(\text{PC}, 4) + (\text{imm8} \ll 2)$.
   - 32-bit Thumb-2 `PUSH.W` / `STMDB SP!, {...}` (`0xE92D` followed by register mask halfword `0x43FE`).
   - 32-bit Thumb-2 `BL` / `BLX (immediate)` (`11110 S imm10` / `11 J1 L J2 imm11`): $I_1 = \neg(J_1 \oplus S)$, $I_2 = \neg(J_2 \oplus S)$, signed 25-bit displacement added to $\text{InstrAddr} + 4$ (or $\text{Align}(\text{InstrAddr} + 4, 4)$ for `BLX`).

### 2.3 Nine Canonical Pinned Evidence Slices (`1,284` Bytes Total)

The following **nine pinned ROM slices** (`S1A`–`S3B`, totaling **1,284 bytes**) constitute the primary reproducible evidence excerpts for U1, U2, and U3. Note that these 1,284 bytes are the **pinned evidence excerpts**, not the entirety of ROM bytes accessed during the research session (see §2.4 for full disclosure of broader context reads and the out-of-scope caller scan).

| Slice ID | Purpose | ROM VMA Range (Inclusive) | File Offset Range | Size | Slice SHA-256 |
|---|---|---|---:|---:|---|
| **S1A** | Early boot ATCM copy loop & literal pool | `0xFC020040..0xFC0200CF` | `0x020040..0x0200CF` | 144 B | `a8bea578f65643701322d3ce2fc500d04485323dbb28bfab6e89a51a6344c54b` |
| **S1B** | `0xFC31BBC4` ARM veneer (`j_CreateTask` `[INFERRED]`) | `0xFC31BBC4..0xFC31BBCB` | `0x31BBC4..0x31BBCB` | 8 B | `e7f6fb4484c3a010e0db4a97edd252a10e92c529f0e75190a0cf98a479fa566d` |
| **S1C** | `CreateTask` `[INFERRED]` (`0xBFE14A3C..0xBFE14AAD`), adjacent code, & literal pool (`0xBFE14A3C..0xBFE14C67`) | `0xFCEF3488..0xFCEF36B3` | `0xEF3488..0xEF36B3` | 556 B | `409dcaec41a0e5aeba37110254919995f018aae13fcc942b832ffc244c223b36` |
| **S1D** | `0xFC31BE8C` ARM veneer (`j_CreateTaskStrictly` `[INFERRED]`) | `0xFC31BE8C..0xFC31BE93` | `0x31BE8C..0x31BE93` | 8 B | `f4a9356c75017083e2dbabbc309815595ae745a3787bbb5128e1e823601079b3` |
| **S1E** | `CreateTaskStrictly` `[INFERRED]` body in ATCM ROM source (`0xBFE154E8..0xBFE15509`) | `0xFCEF3F34..0xFCEF3F55` | `0xEF3F34..0xEF3F55` | 34 B | `ce4d1016656cd6053e9808a6cf718d18e885948f0b7102a15cef88bcaacad612` |
| **S2A** | `task_InitFileModules` `[INFERRED]`, creator `sub_fc0bd0b4`, and literal/string pool | `0xFC0BD070..0xFC0BD1BB` | `0x0BD070..0x0BD1BB` | 332 B | `2c939717866f0a5c4c8df88e8f75942890347cdd7453fbe54bdcc33125020c94` |
| **S2B** | `task_InitFileModules` callees (`sub_fc0d9ccc`, `sub_fc0d9cf6`) | `0xFC0D9CCC..0xFC0D9D25` | `0x0D9CCC..0x0D9D25` | 90 B | `4e3f0f99e5605d08d6ba093146e86f009b28121220c632dae05f0a479e218ee8` |
| **S3A** | `task_PhySw` `[INFERRED]` (`0xFC1283AC`) & creator `sub_fc1283d2` (`0xFC1283D2`) | `0xFC1283AC..0xFC1283FF` | `0x1283AC..0x1283FF` | 84 B | `8d38c2112b67283d302f77bd881ab9ccf4b2f7f1b4bfffc51bb531fd2151385a` |
| **S3B** | `PhySw` literal and string pool | `0xFC128704..0xFC12871F` | `0x128704..0x12871F` | 28 B | `fdace2c951b23e71497dab6d9e160a439a72f20f24fbcb362bbd014d3714b376` |

### 2.4 Process Deviation Disclosure & Out-of-Slice Provenance Accounting

> [!WARNING]
> **Read-Only Process Deviation Disclosure (Out-of-Scope Full-ROM Caller Scans)**:
> Although the PORT-11A authorization permitted only bounded region inspection of `PRIMARY.BIN` for U1, U2, and U3, the worker executed three read-only Python search commands across broader spans of `PRIMARY.BIN` while attempting to locate callers of `sub_fc0bd0b4` (`0xFC0BD0B4`) after checking five `0xFC0BBxxx` subroutines called from `task_Startup`:
> 1. **Step 217 (Pointer + $\pm 4\text{ MiB}$ Branch Scan)**: Ran a full-ROM (`0x000000..0x02000000`, `33,554,432` B) `bytes.find` for little-endian 32-bit word `0xFC0BD0B5`, and a halfword-aligned (`step = 2`) loop over file offsets `0x000000..0x4BD0B4` (`4,968,628` B) checking 32-bit Thumb-2 `BL`/`B.W` (`(hw1 & 0xF800) == 0xF000`, `(hw2 & 0xC000) == 0x8000`, `(hw2 & 0xD000) in (0xD000, 0x9000)`). Due to missing parentheses in `I1 = ~(J1 ^ S) & 1` inside `(S << 24) | (I1 << 23)`, the branch scan returned no matches.
> 2. **Step 221 (Full-ROM 32-Bit Word Search)**: Ran a full-ROM (`0x000000..0x02000000`, `33,554,432` B) `bytes.find` for little-endian 32-bit words `0xFC0BD0B4`, `0xFC0BD0B5`, `0xFC0BD166`, `0xFC0BD167` and their file-offset equivalents (`target - 0xFC000000`), returning zero matches.
> 3. **Step 223 (Full-ROM Halfword-Aligned Thumb-2 `BL`/`B.W` Scan)**: Ran a full-ROM halfword-aligned (`range(0, len(rom) - 4, 2)`, file offsets `0x000000..0x1FFFFFC`, `33,554,428` B) scan for 32-bit Thumb-2 unconditional `BL` (`(hw1 & 0xF800) == 0xF000`, `(hw2 & 0xD000) == 0xD000`) and unconditional `B.W` (`(hw1 & 0xF800) == 0xF000`, `(hw2 & 0xD000) == 0x9000`) with target `0xFC0BD0B4`. This scan returned four matches (`0xFC079130`, `0xFC324A04`, `0xFC324A20`, `0xFC324C00`), followed by a Step 225 context read of `0xFC079118..0xFC079147` (`48` B) and `0xFC3249F8..0xFC324A2F` (`56` B).
>
> **Governance & Methodological Consequences**:
> - Executing global `bytes.find` and full-ROM halfword scans exceeded the bounded-slice inspection scope and is recorded here as a **read-only process deviation**. Any future investigation requiring scans outside pre-approved bounded regions must obtain explicit prior re-scoping authorization before execution.
> - **Non-Exhaustiveness of the Caller Scan**: The Step 223 scan checked **only** halfword-aligned 32-bit Thumb-2 unconditional `BL` and `B.W` instructions targeting `0xFC0BD0B4` assuming base `0xFC000000`. It did **not** check indirect calls (`BLX Rm`, `BX Rm`, `LDR PC`), table/relative-offset dispatch, conditional `B<cc>.W`, 16-bit Thumb `B`, ARM-state `BL`/`BLX`, or relocated RAM/ATCM copies. Furthermore, the surrounding function context of `0xFC324C00` was never read (`UNKNOWN`). Therefore, the four matched addresses are **not an exhaustive caller list**, and whether `task_Startup` reaches `sub_fc0bd0b4` indirectly remains **`UNKNOWN`**.

In addition to the nine pinned slices (`S1A`–`S3B`), initial bounded context reads in Steps 199–220 accessed slightly wider windows around those slices (`0xFC02000C..0xFC0200E7`, `0xFC31BBC0..0xFC31BBD3`, `0xFCEF3488..0xFCEF352F`, `0xFCEF369C..0xFCEF36C3`, `0xFC0BD000..0xFC0BD2BF`, `0xFC0D9CCC..0xFC0D9D4F`, `0xFC05B8FC..0xFC05B957`, `0xFC1283AC..0xFC12847F`, `0xFC128700..0xFC128727`, `0xFC31BE88..0xFC31BE97`, `0xFCEF3F34..0xFCEF3FB3`, `0xFC0BB6FE..0xFC0BB79D`, `0xFC0BB9CC..0xFC0BBA21`). Every reference in this document to an address outside `S1A`–`S3B` is accounted for in the table below using **only** already-collected session logs (zero additional ROM reads):

| Out-of-Slice Address / Range | File Offset | Size | Logged Bytes & SHA-256 (from Session Log) | Provenance & Evidentiary Disposition |
|---|---:|---:|---|---|
| **`0xFC0BD02E..0xFC0BD04B`** (and word **`0xFC0BD048..0xFC0BD04B`**) | `0x0BD02E..0x0BD04B` (`0x0BD048..0x0BD04B`) | 30 B (4 B) | `30 B` hex: `5ef2a7bc000080850000c8160400ebc30bfce9c30bfc59c70bfcb0bb66fc` (`sha256: 2e21bd3131bf10ea0d55ea61feffb9fd230ab68855d931998a49da9868eac841`); `4 B` at `0xFC0BD048`: `b0bb66fc` = `0xFC66BBB0` (`sha256: 17b9f5ee26e9c90d82b748a3c4422fe0d87a8153c93cf0d2f82acb50e7435a4d`) | **`STATIC_VERIFIED (Logged in Step 204 Outside S2A)`**: Shows `0xFC0BD02E` (`b.w 0xFC31B980`) followed by literal words including `[0xFC0BD048] = 0xFC66BBB0`. |
| **`0xFCEF36B4..0xFCEF36BB`** (ATCM `0xBFE14C68..0xBFE14C6F`) | `0xEF36B4..0xEF36BB` | 8 B | `0484000070b50446` (`[0xFCEF36B4] = 0x00008404`; `0xFCEF36B8`: `70 b5 04 46` = `push {r4, r5, r6, lr}; mov r4, r0`; `sha256: c73ff76163ef3343859a9993d775f023ccda2bc4fffc86e0ddde82f2b2d70dc9`) | **`STATIC_VERIFIED (Logged in Step 202 Outside S1C; Non-Essential Context)`**: Explanatory context only; `S1C` (`0xFCEF3488`) already disproves `push {r4, r5, r6, lr}` at `CreateTask`. |
| **`0xFC05B92E..0xFC05B931`** (in `task_Startup`) | `0x05B92E..0x05B931` | 4 B | `ccf050fd` (`bl 0xFC1283D2`; `sha256: 31dd3c875a79885b4c75d424b2d90e9d7ca3ad950fae49418f250b9d4e71fa73`) | **`STATIC_VERIFIED (Logged in Step 212 Outside S3A; Also in Tracked PORT-5D / boot_prototype.c:170)`**: Confirms `task_Startup` calls `0xFC1283D2`. |
| **`[0xFC0D9D54]`** (target of `0xFC0D9D02: ldr r4, [pc, #0x50]`) | `0x0D9D54..0x0D9D57` | 4 B | *Not read* (Step 208 read ended at `0xFC0D9D50`; `S2B` ends at `0xFC0D9D25`) | **`UNKNOWN` (Outside Pinned Slice `S2B`)**: PC-relative target address `0xFC0D9D54` is arithmetic-verified from `0xFC0D9D02` (`14 4c` in `S2B`), but the 32-bit word stored at `0xFC0D9D54` was not read and is `UNKNOWN`. |
| **`0xBFE15634`** / ROM **`0xFCEF4080`** (target of `0xBFE15500: adr r1, #0x130`) | `0xEF4080..` | — | *Not read* (Step 214 read ended at `0xFCEF3FB3`; `S1E` ends at `0xFCEF3F55`) | **`UNKNOWN` (Outside Pinned Slice `S1E`)**: Target address `0xBFE15634` is arithmetic-verified from `0xBFE15500` (`4c a1` in `S1E`), but the bytes at `0xBFE15634` (`0xFCEF4080`) were not read; any `"KerTask.c"` string content at `0xBFE15634` is **`INFERRED / UNKNOWN`**. |

---

## 3. Phase 2 — U1: `CreateTask` Prologue and Continuation Evidence

### 3.1 ATCM Copy Loop Verification (Slice S1A)

During early boot (`0xFC020040..0xFC020052`), stock GM1.10C firmware populates the **ARM Cortex-R4** ATCM region from ROM:

| ROM Address | File Offset | Raw Bytes | Instruction | Resolved Operand / Direct Effect | Status |
|---|---:|---|---|---|---|
| `0xFC020040` | `0x020040` | `20 48` | `ldr r0, [pc, #0x80]` | `[0xFC0200C4] = 0xFCEEF24C` (ROM source start) | **`STATIC_VERIFIED`** |
| `0xFC020042` | `0x020042` | `21 49` | `ldr r1, [pc, #0x84]` | `[0xFC0200C8] = 0xBFE10800` (ATCM destination start) | **`STATIC_VERIFIED`** |
| `0xFC020044` | `0x020044` | `21 4b` | `ldr r3, [pc, #0x84]` | `[0xFC0200CC] = 0xBFE17419` (ATCM loop comparison limit) | **`STATIC_VERIFIED`** |
| `0xFC020046` | `0x020046` | `99 42` | `cmp r1, r3` | Compares current destination `r1` against `0xBFE17419` | **`STATIC_VERIFIED`** |
| `0xFC020048` | `0x020048` | `3c bf` | `itt lo` | Conditional block while unsigned `r1 < 0xBFE17419` | **`STATIC_VERIFIED`** |
| `0xFC02004A` | `0x02004A` | `50 f8 04 2b` | `ldrlo r2, [r0], #4` | Reads 32-bit word from ROM `r0`, post-increments `r0 += 4` | **`STATIC_VERIFIED`** |
| `0xFC02004E` | `0x02004E` | `41 f8 04 2b` | `strlo r2, [r1], #4` | Writes 32-bit word to ATCM `r1`, post-increments `r1 += 4` | **`STATIC_VERIFIED`** |
| `0xFC020052` | `0x020052` | `f8 d3` | `blo 0xFC020046` | Loops while `r1 < 0xBFE17419` | **`STATIC_VERIFIED`** |

**Exact Copy Span & Mapping Formula**:
- Because `r1` starts at `0xBFE10800` (4-byte aligned) and increments by `4` on each iteration, the final iteration where `r1 < 0xBFE17419` occurs at `r1 = 0xBFE17418` (writing the 4-byte word at `0xBFE17418..0xBFE1741B` and advancing `r1` to `0xBFE1741C`, which terminates the loop since `0xBFE1741C >= 0xBFE17419`).
- Thus, the loop copies **`6,919` words (`27,676` bytes = `0x6C1C` B)** from ROM **`0xFCEEF24C..0xFCEF5E67`** to ATCM **`0xBFE10800..0xBFE1741B`** (`[0xBFE10800, 0xBFE1741C)`).
- For any runtime address $\text{VMA} \in [0\text{xBFE10800}, 0\text{xBFE1741C})$:
  $$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (\text{VMA} - 0\text{xBFE10800}), \qquad \text{File\_Offset} = \text{ROM\_VMA} - 0\text{xFC000000}$$
- Applying this formula to the `CreateTask` `[INFERRED]` entry at ATCM instruction address `0xBFE14A3C`:
  $$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (0\text{xBFE14A3C} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x423C} = \mathbf{0\text{xFCEF3488}} \quad (\text{File Offset } \mathbf{0\text{x00EF3488}})$$

### 3.2 Kernel Veneer at `0xFC31BBC4` (`j_CreateTask` `[INFERRED]`, Slice S1B)

Callers in ROM invoke `0xFC31BBC4` via `blx 0xFC31BBC4` (switching from Thumb to ARM state at `0xFC31BBC4`):

| ROM Address | File Offset | Raw Bytes | 32-bit LE Word | ARM Instruction / Data | Direct Architectural Effect | Status |
|---|---:|---|---|---|---|---|
| `0xFC31BBC4` | `0x31BBC4` | `04 f0 1f e5` | `0xE51FF004` | `ldr pc, [pc, #-4]` | In ARM state (`PC = 0xFC31BBC4 + 8`), loads `PC` from `0xFC31BBC8` | **`STATIC_VERIFIED`** |
| `0xFC31BBC8` | `0x31BBC8` | `3d 4a e1 bf` | `0xBFE14A3D` | `.word 0xBFE14A3D` | Branches to instruction address `0xBFE14A3C` in **Thumb state** (bit 0 = 1) | **`STATIC_VERIFIED`** |

### 3.3 `CreateTask` `[INFERRED]` Body (`0xBFE14A3C..0xBFE14AAD`, `114` Bytes) and Literal Pool (Slice S1C)

Complete instruction-by-instruction disassembly of the `CreateTask` `[INFERRED]` function body (`0xBFE14A3C..0xBFE14AAD` inclusive, ROM source `0xFCEF3488..0xFCEF34F9` inclusive, file offset `0x00EF3488..0x00EF34F9`, totaling **`114` bytes** = `0x72` B; note that `0xBFE14AAE` / ROM `0xFCEF34FA` is `10 b5` = `push {r4, lr}`, the entry of the subsequent function):

| ATCM VMA | ROM Source VMA | File Offset | Raw Bytes | Size | Thumb/Thumb-2 Instruction | Direct Architectural Effect (and `[INFERRED]` Role) | Status |
|---|---|---:|---|---:|---|---|---|
| **`0xBFE14A3C`** | **`0xFCEF3488`** | **`0xEF3488`** | **`2d e9 fe 43`** | **4 B** | **`push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}`** | **Pushes 10 registers (`40` bytes = `0x28` B) onto stack (`stmdb sp!, {r1-r9, lr}`)** | **`STATIC_VERIFIED`** |
| **`0xBFE14A40`** | **`0xFCEF348C`** | **`0xEF348C`** | **`04 46`** | **2 B** | **`mov r4, r0`** | **Copies `r0` into `r4` (`name` pointer `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| **`0xBFE14A42`** | **`0xFCEF348E`** | **`0xEF348E`** | **`85 48`** | **2 B** | **`ldr r0, [pc, #0x214]`** | **Loads `r0 = [0xBFE14C58] = 0x00008160` (ROM `0xFCEF36A4`)** | **`STATIC_VERIFIED`** |
| **`0xBFE14A44`** | **`0xFCEF3490`** | **`0xEF3490`** | **`0e 46`** | **2 B** | **`mov r6, r1`** | **Next instruction at even address `0xBFE14A44` (Thumb continuation target pointer `0xBFE14A45`); copies `r1` to `r6` (`priority` `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| `0xBFE14A46` | `0xFCEF3492` | `0xEF3492` | `15 46` | 2 B | `mov r5, r2` | Copies `r2` to `r5` (`stack_size` `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14A48` | `0xFCEF3494` | `0xEF3494` | `dd f8 28 80` | 4 B | `ldr.w r8, [sp, #0x28]` | Loads caller's stacked 5th argument (`[sp_entry + 0]`) across 40-byte (`0x28`) `push.w` frame into `r8` | **`STATIC_VERIFIED`** |
| `0xBFE14A4C` | `0xFCEF3498` | `0xEF3498` | `1f 46` | 2 B | `mov r7, r3` | Copies `r3` to `r7` (`entry` function pointer `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14A4E` | `0xFCEF349A` | `0xEF349A` | `00 68` | 2 B | `ldr r0, [r0]` | Dereferences `*(uint32_t *)0x00008160` (context/ISR state word `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14A50` | `0xFCEF349C` | `0xEF349C` | `00 28` | 2 B | `cmp r0, #0` | Compares `*(0x00008160)` against `0` | **`STATIC_VERIFIED`** |
| `0xBFE14A52` | `0xFCEF349E` | `0xEF349E` | `04 dd` | 2 B | `ble 0xBFE14A5E` | Signed branch to `0xBFE14A5E` if `<= 0` | **`STATIC_VERIFIED`** |
| `0xBFE14A54` | `0xFCEF34A0` | `0xEF34A0` | `98 22` | 2 B | `movs r2, #0x98` | Sets `r2 = 0x98` (152, source line number `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14A56` | `0xFCEF34A2` | `0xEF34A2` | `00 20` | 2 B | `movs r0, #0` | Sets `r0 = 0` | **`STATIC_VERIFIED`** |
| `0xBFE14A58` | `0xFCEF34A4` | `0xEF34A4` | `80 a1` | 2 B | `adr r1, #0x200` | Sets `r1 = 0xBFE14C5C` (`"KerTask.c"`, ROM `0xFCEF36A8`) | **`STATIC_VERIFIED`** |
| `0xBFE14A5A` | `0xFCEF34A6` | `0xEF34A6` | `ff f7 0e ea` | 4 B | `blx 0xBFE13E78` | Calls `0xBFE13E78` (`DebugAssert` `[INFERRED]`, body outside `S1C` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xBFE14A5E` | `0xFCEF34AA` | `0xEF34AA` | `7d 49` | 2 B | `ldr r1, [pc, #0x1f4]` | Loads `r1 = [0xBFE14C54] = 0x000081CC` (ROM `0xFCEF36A0`) | **`STATIC_VERIFIED`** |
| `0xBFE14A60` | `0xFCEF34AC` | `0xEF34AC` | `04 b9` | 2 B | `cbnz r4, 0xBFE14A64` | If `r4 != 0`, keep `r4`; else load default at `0xBFE14A62` | **`STATIC_VERIFIED`** |
| `0xBFE14A62` | `0xFCEF34AE` | `0xEF34AE` | `0c 68` | 2 B | `ldr r4, [r1]` | Loads `r4 = *(uint32_t *)0x000081CC` | **`STATIC_VERIFIED`** |
| `0xBFE14A64` | `0xFCEF34B0` | `0xEF34B0` | `70 1e` | 2 B | `subs r0, r6, #1` | Computes `r0 = r6 - 1` | **`STATIC_VERIFIED`** |
| `0xBFE14A66` | `0xFCEF34B2` | `0xEF34B2` | `20 28` | 2 B | `cmp r0, #0x20` | Unsigned range check `r6 - 1 < 0x20` (`1 <= r6 <= 0x20`) | **`STATIC_VERIFIED`** |
| `0xBFE14A68` | `0xFCEF34B4` | `0xEF34B4` | `00 d2` | 2 B | `bhs 0xBFE14A6C` | Branch if out of range | **`STATIC_VERIFIED`** |
| `0xBFE14A6A` | `0xFCEF34B6` | `0xEF34B6` | `3f b9` | 2 B | `cbnz r7, 0xBFE14A7C` | Branch to `0xBFE14A7C` if `r7 != 0` | **`STATIC_VERIFIED`** |
| `0xBFE14A6C` | `0xFCEF34B8` | `0xEF34B8` | `a0 22` | 2 B | `movs r2, #0xa0` | Sets `r2 = 0xa0` (160) | **`STATIC_VERIFIED`** |
| `0xBFE14A6E` | `0xFCEF34BA` | `0xEF34BA` | `00 20` | 2 B | `movs r0, #0` | Sets `r0 = 0` | **`STATIC_VERIFIED`** |
| `0xBFE14A70` | `0xFCEF34BC` | `0xEF34BC` | `7a a1` | 2 B | `adr r1, #0x1e8` | Sets `r1 = 0xBFE14C5C` (`"KerTask.c"`) | **`STATIC_VERIFIED`** |
| `0xBFE14A72` | `0xFCEF34BE` | `0xEF34BE` | `ff f7 02 ea` | 4 B | `blx 0xBFE13E78` | Calls `0xBFE13E78` (`DebugAssert` `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14A76` | `0xFCEF34C2` | `0xEF34C2` | `03 20` | 2 B | `movs r0, #3` | Error return code `3` | **`STATIC_VERIFIED`** |
| `0xBFE14A78` | `0xFCEF34C4` | `0xEF34C4` | `bd e8 fe 83` | 4 B | `pop.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, pc}` | Common epilogue: restores `r1–r9` and returns | **`STATIC_VERIFIED`** |
| `0xBFE14A7C` | `0xFCEF34C8` | `0xEF34C8` | `05 b9` | 2 B | `cbnz r5, 0xBFE14A80` | If `r5 != 0`, keep `r5`; else load default `[r1, #4]` | **`STATIC_VERIFIED`** |
| `0xBFE14A7E` | `0xFCEF34CA` | `0xEF34CA` | `4d 68` | 2 B | `ldr r5, [r1, #4]` | Loads `r5 = *(uint32_t *)0x000081D0` | **`STATIC_VERIFIED`** |
| `0xBFE14A80` | `0xFCEF34CC` | `0xEF34CC` | `00 22` | 2 B | `movs r2, #0` | Sets `r2 = 0` | **`STATIC_VERIFIED`** |
| `0xBFE14A82` | `0xFCEF34CE` | `0xEF34CE` | `41 46` | 2 B | `mov r1, r8` | Passes 5th arg (`r8`) in `r1` | **`STATIC_VERIFIED`** |
| `0xBFE14A84` | `0xFCEF34D0` | `0xEF34D0` | `38 46` | 2 B | `mov r0, r7` | Passes `entry` (`r7`) in `r0` | **`STATIC_VERIFIED`** |
| `0xBFE14A86` | `0xFCEF34D2` | `0xEF34D2` | `2b 46` | 2 B | `mov r3, r5` | Passes `stack_size` (`r5`) in `r3` | **`STATIC_VERIFIED`** |
| `0xBFE14A88` | `0xFCEF34D4` | `0xEF34D4` | `02 94` | 2 B | `str r4, [sp, #8]` | Stores `name` (`r4`) at `[sp, #8]` | **`STATIC_VERIFIED`** |
| `0xBFE14A8A` | `0xFCEF34D6` | `0xEF34D6` | `cd e9 00 62` | 4 B | `strd r6, r2, [sp]` | Stores `r6` (`priority`) at `[sp]` and `r2` (`0`) at `[sp, #4]` | **`STATIC_VERIFIED`** |
| `0xBFE14A8E` | `0xFCEF34DA` | `0xEF34DA` | `fc f7 7b f8` | 4 B | `bl 0xBFE10B88` | Calls internal allocator/initializer `0xBFE10B88` (outside `S1C` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xBFE14A92` | `0xFCEF34DE` | `0xEF34DE` | `04 46` | 2 B | `mov r4, r0` | Saves return value in `r4` | **`STATIC_VERIFIED`** |
| `0xBFE14A94` | `0xFCEF34E0` | `0xEF34E0` | `40 1c` | 2 B | `adds r0, r0, #1` | Checks if `r0 == -1` (`0xFFFFFFFF`) | **`STATIC_VERIFIED`** |
| `0xBFE14A96` | `0xFCEF34E2` | `0xEF34E2` | `05 d1` | 2 B | `bne 0xBFE14AA4` | If not `-1`, branch to `0xBFE14AA4` | **`STATIC_VERIFIED`** |
| `0xBFE14A98` | `0xFCEF34E4` | `0xEF34E4` | `b2 22` | 2 B | `movs r2, #0xb2` | Sets `r2 = 0xb2` (178) | **`STATIC_VERIFIED`** |
| `0xBFE14A9A` | `0xFCEF34E6` | `0xEF34E6` | `70 a1` | 2 B | `adr r1, #0x1c0` | Sets `r1 = 0xBFE14C5C` (`"KerTask.c"`) | **`STATIC_VERIFIED`** |
| `0xBFE14A9C` | `0xFCEF34E8` | `0xEF34E8` | `ff f7 ec e9` | 4 B | `blx 0xBFE13E78` | Calls `0xBFE13E78` (`DebugAssert` `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xBFE14AA0` | `0xFCEF34EC` | `0xEF34EC` | `05 20` | 2 B | `movs r0, #5` | Returns error code `5` | **`STATIC_VERIFIED`** |
| `0xBFE14AA2` | `0xFCEF34EE` | `0xEF34EE` | `e9 e7` | 2 B | `b 0xBFE14A78` | Jumps to common epilogue `0xBFE14A78` | **`STATIC_VERIFIED`** |
| `0xBFE14AA4` | `0xFCEF34F0` | `0xEF34F0` | `20 46` | 2 B | `mov r0, r4` | Passes `r4` in `r0` | **`STATIC_VERIFIED`** |
| `0xBFE14AA6` | `0xFCEF34F2` | `0xEF34F2` | `fc f7 35 f9` | 4 B | `bl 0xBFE10D14` | Calls internal activation helper `0xBFE10D14` (outside `S1C` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xBFE14AAA` | `0xFCEF34F6` | `0xEF34F6` | `60 00` | 2 B | `lsls r0, r4, #1` | Sets `r0 = r4 << 1` | **`STATIC_VERIFIED`** |
| **`0xBFE14AAC`** | **`0xFCEF34F8`** | **`0xEF34F8`** | **`e4 e7`** | **2 B** | **`b 0xBFE14A78`** | **Final bytes of `CreateTask` (`0xBFE14AAC..0xBFE14AAD`); branches to epilogue `0xBFE14A78` (`36 B + 78 B = 114 B` total)** | **`STATIC_VERIFIED`** |

**Referenced Literal Pool in ATCM Copy Source (`0xBFE14C54..0xBFE14C67`, ROM `0xFCEF36A0..0xFCEF36B3`, inside Slice S1C)**:
- `0xBFE14C54` (ROM `0xFCEF36A0`, off `0xEF36A0`): `cc 81 00 00` $\to$ `0x000081CC` (`STATIC_VERIFIED`; default task attribute block pointer `[INFERRED]`).
- `0xBFE14C58` (ROM `0xFCEF36A4`, off `0xEF36A4`): `60 81 00 00` $\to$ **`0x00008160`** (`STATIC_VERIFIED`; loaded by `0xBFE14A42: ldr r0, [pc, #0x214]`: $\text{Align}(0\text{xBFE14A42}+4, 4) + 0\text{x214} = 0\text{xBFE14A44} + 0\text{x214} = 0\text{xBFE14C58}$).
- `0xBFE14C5C..0xBFE14C65` (ROM `0xFCEF36A8..0xFCEF36B1`, off `0xEF36A8`): `4b 65 72 54 61 73 6b 2e 63 00` $\to$ ASCII `"KerTask.c\0"` (`STATIC_VERIFIED`).

### 3.4 Resolution of the PORT-10A U1 Contradiction

1. **Why `CHDK_PORT0B_STUBS_AUDIT.md:33` Was Contradicted**:
   - At `0xBFE14A3C` (ROM `0xFCEF3488`, inside `S1C`), the actual instruction is `2d e9 fe 43` = **`push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}`** (4 bytes), matching the epilogue `pop.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, pc}` (`bd e8 fe 83`) at `0xBFE14A78` and the 40-byte stack offset `ldr.w r8, [sp, #0x28]` at `0xBFE14A48`.
   - Therefore, the `push {r4, r5, r6, lr}` (`70 b5`) entry in `CHDK_PORT0B_STUBS_AUDIT.md:33` is **CONTRADICTED** by primary ROM bytes in `S1C` (as non-essential context, `70 b5` appears at `task_InitFileModules` `0xFC0BD070` in `S2A` and at `0xBFE14C6C` / ROM `0xFCEF36B8` logged outside `S1C` in §2.4).
2. **Exact 8-Byte Instruction Boundary (`0xBFE14A44`) vs Thumb Interworking Target (`0xBFE14A45`)**:
   - The first three instructions at `0xBFE14A3C` occupy **exactly 8 bytes** (`4 + 2 + 2 = 8` bytes, `0xBFE14A3C..0xBFE14A43`), ending cleanly on the **even instruction boundary `0xBFE14A44`** (`0e 46` = `mov r6, r1`, ROM `0xFCEF3490`).
   - Any future 8-byte trampoline at `0xBFE14A3C` (`ldr.w pc, [pc, #0]` + target word) would overwrite:
     1. `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` (`0xBFE14A3C`, 4 B)
     2. `mov r4, r0` (`0xBFE14A40`, 2 B)
     3. `ldr r0, [pc, #0x214]` (`0xBFE14A42`, 2 B — PC-relative load of literal `0x00008160`)
   - And would have to replay those three operations (setting `r0 = 0x00008160`) before branching to the **Thumb-state interworking continuation pointer `0xBFE14A45`** (`0xBFE14A44 | 1`, which resumes execution at instruction address `0xBFE14A44` in Thumb state).

---

## 4. Phase 3 — U2: `InitFileModules` Task Identity and Completion Semantics

### 4.1 Task Creation Site: `sub_fc0bd0b4` (Slice S2A)

Inspection of `0xFC0BD070..0xFC0BD1BB` (file offset `0x000BD070..0x000BD1BB`, Slice `S2A`) identifies both the creator function (`sub_fc0bd0b4` at `0xFC0BD0B4..0xFC0BD0DB`) and the task entry (`0xFC0BD070..0xFC0BD09B`, `task_InitFileModules` `[INFERRED]`):

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Architectural Effect (and `[INFERRED]` Role) | Status |
|---|---:|---|---|---|---|
| `0xFC0BD0B4` | `0x0BD0B4` | `3a 48` | `ldr r0, [pc, #0xe8]` | Loads `r0 = [0xFC0BD1A0] = 0x00008BB8` (RAM state base `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC0BD0B6` | `0x0BD0B6` | `08 b5` | `push {r3, lr}` | Saves `lr` and allocates 4-byte stack slot `[sp]` | **`STATIC_VERIFIED`** |
| `0xFC0BD0B8` | `0x0BD0B8` | `41 68` | `ldr r1, [r0, #4]` | Reads `*(uint32_t *)0x00008BBC` (singleton guard flag `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC0BD0BA` | `0x0BD0BA` | `00 29` | `cmp r1, #0` | Compares `*(0x00008BBC)` with `0` | **`STATIC_VERIFIED`** |
| `0xFC0BD0BC` | `0x0BD0BC` | `0d d1` | `bne 0xFC0BD0DA` | If `*(0x00008BBC) != 0`, branch to `0xFC0BD0DA` (`pop {r3, pc}`) | **`STATIC_VERIFIED`** |
| `0xFC0BD0BE` | `0x0BD0BE` | `01 21` | `movs r1, #1` | Sets `r1 = 1` | **`STATIC_VERIFIED`** |
| `0xFC0BD0C0` | `0x0BD0C0` | `41 60` | `str r1, [r0, #4]` | Stores `*(0x00008BBC) = 1` | **`STATIC_VERIFIED`** |
| `0xFC0BD0C2` | `0x0BD0C2` | `38 48` | `ldr r0, [pc, #0xe0]` | Loads `r0 = [0xFC0BD1A4] = 0xFC0BD0B1` (`0xFC0BD0B0: b.w 0xFC31B280`) | **`STATIC_VERIFIED`** |
| `0xFC0BD0C4` | `0x0BD0C4` | `5e f2 d8 e8` | `blx 0xFC31B278` | Calls `0xFC31B278(0xFC0BD0B1)` (body outside `S2A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC0BD0C8` | `0x0BD0C8` | `00 23` | `movs r3, #0` | Sets `r3 = 0` | **`STATIC_VERIFIED`** |
| `0xFC0BD0CA` | `0x0BD0CA` | `00 93` | `str r3, [sp]` | Stores 5th argument `[sp] = 0` | **`STATIC_VERIFIED`** |
| **`0xFC0BD0CC`** | **`0x0BD0CC`** | **`36 4b`** | **`ldr r3, [pc, #0xd8]`** | **Loads `r3 = [0xFC0BD1A8] = 0xFC0BD071` (Thumb entry pointer for `0xFC0BD070`)** | **`STATIC_VERIFIED`** |
| **`0xFC0BD0CE`** | **`0x0BD0CE`** | **`19 21`** | **`movs r1, #0x19`** | **Sets `r1 = 0x19` (`25`, task priority `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| **`0xFC0BD0D0`** | **`0x0BD0D0`** | **`36 a0`** | **`adr r0, #0xd8`** | **Sets `r0 = 0xFC0BD1AC` (`"InitFileModules"`)** | **`STATIC_VERIFIED`** |
| **`0xFC0BD0D2`** | **`0x0BD0D2`** | **`41 f2 00 02`** | **`movw r2, #0x1000`** | **Sets `r2 = 0x1000` (`4096`, stack size `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| **`0xFC0BD0D6`** | **`0x0BD0D6`** | **`5e f2 76 ed`** | **`blx 0xFC31BBC4`** | **Calls ARM veneer `0xFC31BBC4` (`-> 0xBFE14A3D`, `j_CreateTask` `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| `0xFC0BD0DA` | `0x0BD0DA` | `08 bd` | `pop {r3, pc}` | Returns | **`STATIC_VERIFIED`** |

*(Note on Predecessor Actions in `sub_fc0bd0b4`: Before calling `0xFC31BBC4`, `sub_fc0bd0b4` checks/sets the `*(0x00008BBC)` guard and calls `0xFC31B278(0xFC0BD0B1)`. Any future interception design must preserve `sub_fc0bd0b4` execution rather than bypassing those predecessor operations.)*

**Literal & String Pool (`0xFC0BD1A0..0xFC0BD1BB`, file offset `0x000BD1A0..0x000BD1BB`, Slice S2A)**:
- `0xFC0BD1A0`: `b8 8b 00 00` (`0x00008BB8`, `STATIC_VERIFIED`)
- `0xFC0BD1A4`: `b1 d0 0b fc` (`0xFC0BD0B1`, `STATIC_VERIFIED`)
- `0xFC0BD1A8`: `71 d0 0b fc` (**`0xFC0BD071`**, `STATIC_VERIFIED` — Thumb entry pointer for instruction address `0xFC0BD070`)
- `0xFC0BD1AC..0xFC0BD1BB`: `49 6e 69 74 46 69 6c 65 4d 6f 64 75 6c 65 73 00` (**`"InitFileModules\0"`**, `STATIC_VERIFIED`)

**Call Sites Reaching `sub_fc0bd0b4` (`0xFC0BD0B4`) — Qualified per §2.4**:
- In `task_Startup` (`0xFC05B8FC..0xFC05B957`, logged in Step 212), there is no direct `bl 0xFC0BD0B4` instruction; whether `task_Startup` reaches `sub_fc0bd0b4` indirectly is **`UNKNOWN`**.
- The out-of-scope halfword-aligned Thumb-2 `BL`/`B.W` scan disclosed in §2.4 (Step 223) found four direct `bl 0xFC0BD0B4` instructions at `0xFC079130`, `0xFC324A04`, `0xFC324A20`, and `0xFC324C00` (outside `S1A`–`S3B`; non-exhaustive because indirect calls, jump tables, or other encodings were not scanned, and `0xFC324C00` context was not read).

### 4.2 Contradiction Resolution: `0xFC0BD071` vs `0xFC0BD049`

- **`0xFC0BD071` (`0xFC0BD070 | 1`) is `STATIC_VERIFIED` in GM1.10C**: Both the literal word at `0xFC0BD1A8` (`0xFC0BD071`) loaded into `r3` at `0xFC0BD0CC` and the function body starting at `0xFC0BD070` inside Slice `S2A` directly establish that the `"InitFileModules"` task entry in GM1.10C is **`0xFC0BD071`** (instruction address `0xFC0BD070`).
- **`0xFC0BD049` (`0xFC0BD048 | 1`) is `CONTRADICTED`**: As logged in Step 204 outside `S2A` (see §2.4, `0xFC0BD02E..0xFC0BD04B`, `sha256: 2e21bd31...c841`), `0xFC0BD048` lies inside a literal pool following `0xFC0BD02E: b.w 0xFC31B980` and contains the 32-bit word `0xFC66BBB0` (`b0 bb 66 fc`), not a function prologue.

### 4.3 `task_InitFileModules` `[INFERRED]` Control Flow (`0xFC0BD070..0xFC0BD09B`) and Callee Semantics (Slices S2A & S2B)

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Architectural Effect (and `[INFERRED]` Role) | Status |
|---|---:|---|---|---|---|
| **`0xFC0BD070`** | **`0x0BD070`** | `70 b5` | `push {r4, r5, r6, lr}` | Function entry at `0xFC0BD070` (Thumb entry pointer `0xFC0BD071`) | **`STATIC_VERIFIED`** |
| `0xFC0BD072` | `0x0BD072` | `1c f0 2b fe` | `bl 0xFC0D9CCC` | Calls `sub_fc0d9ccc` (Slice `S2B`) | **`STATIC_VERIFIED`** |
| `0xFC0BD076` | `0x0BD076` | `04 00` | `movs r4, r0` | Copies `r0` to `r4` and updates APSR flags (`Z=1` if `r0 == 0`) | **`STATIC_VERIFIED`** |
| `0xFC0BD078` | `0x0BD078` | `45 f2 06 05` | `movw r5, #0x5006` | Loads constant `r5 = 0x5006` (event ID `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC0BD07C` | `0x0BD07C` | `03 d0` | `beq 0xFC0BD086` | Branches to `0xFC0BD086` if `r0 == 0` | **`STATIC_VERIFIED`** |
| `0xFC0BD07E` | `0x0BD07E` | `00 21` | `movs r1, #0` | Sets `r1 = 0` | **`STATIC_VERIFIED`** |
| `0xFC0BD080` | `0x0BD080` | `28 46` | `mov r0, r5` | Sets `r0 = 0x5006` | **`STATIC_VERIFIED`** |
| `0xFC0BD082` | `0x0BD082` | `9e f2 5b fc` | `bl 0xFC35B93C` | Calls `0xFC35B93C(0x5006, 0)` (outside `S2A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC0BD086` | `0x0BD086` | `1c f0 36 fe` | `bl 0xFC0D9CF6` | Calls `sub_fc0d9cf6` (Slice `S2B`) | **`STATIC_VERIFIED`** |
| `0xFC0BD08A` | `0x0BD08A` | `00 2c` | `cmp r4, #0` | Compares saved `r4` against `0` | **`STATIC_VERIFIED`** |
| `0xFC0BD08C` | `0x0BD08C` | `05 d1` | `bne 0xFC0BD09A` | If `r4 != 0`, branch to `0xFC0BD09A` | **`STATIC_VERIFIED`** |
| `0xFC0BD08E` | `0x0BD08E` | `28 46` | `mov r0, r5` | Sets `r0 = 0x5006` | **`STATIC_VERIFIED`** |
| `0xFC0BD090` | `0x0BD090` | `bd e8 70 40` | `pop.w {r4, r5, r6, lr}` | Restores `r4–r6, lr` before tail branch | **`STATIC_VERIFIED`** |
| `0xFC0BD094` | `0x0BD094` | `01 21` | `movs r1, #1` | Sets `r1 = 1` | **`STATIC_VERIFIED`** |
| `0xFC0BD096` | `0x0BD096` | `9e f2 51 bc` | `b.w 0xFC35B93C` | Tail-branches to `0xFC35B93C(0x5006, 1)` (outside `S2A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC0BD09A` | `0x0BD09A` | `70 bd` | `pop {r4, r5, r6, pc}` | Returns when `r4 != 0` | **`STATIC_VERIFIED`** |

**Inspection of Callees `sub_fc0d9ccc` and `sub_fc0d9cf6` (Slice S2B, `0xFC0D9CCC..0xFC0D9D25`)**:
1. **`sub_fc0d9ccc` (`0xFC0D9CCC..0xFC0D9CF5`, file offset `0x0D9CCC`, 42 B)**:
   ```arm
   0xFC0D9CCC: push  {r4, lr}            ; 10 b5
   0xFC0D9CCE: bl    0xFC18C13C          ; b2 f0 35 fa (target outside S2B / UNKNOWN)
   0xFC0D9CD2: bl    0xFC2DD6D4          ; 03 f2 ff fc (target outside S2B / UNKNOWN)
   0xFC0D9CD6: bl    0xFC18C564          ; b2 f0 45 fc (target outside S2B / UNKNOWN)
   0xFC0D9CDA: bl    0xFC31375E          ; 39 f2 40 fd (target outside S2B / UNKNOWN)
   0xFC0D9CDE: bl    0xFC0727D4          ; 98 f7 79 fd (target outside S2B / UNKNOWN)
   0xFC0D9CE2: mov.w r1, #0x40000        ; 4f f4 80 21
   0xFC0D9CE6: mov.w r0, #0x10A0000      ; 4f f0 85 70
   0xFC0D9CEA: bl    0xFC18EE9C          ; b5 f0 d7 f8 (target outside S2B / UNKNOWN)
   0xFC0D9CEE: bl    0xFC18D596          ; b3 f0 52 fc (target outside S2B / UNKNOWN)
   0xFC0D9CF2: movs  r0, #0              ; 00 20  <-- sets r0 = 0 on normal return
   0xFC0D9CF4: pop   {r4, pc}            ; 10 bd
   ```
   - **Critical Finding (Qualified for Normal Return)**: `sub_fc0d9ccc` contains **zero conditional branches of its own** and ends with `0xFC0D9CF2: movs r0, #0; pop {r4, pc}`. While any of its seven nested callees (`0xFC18C13C`..`0xFC18D596`, whose bodies lie outside `S2B` and are **`UNKNOWN`**) could theoretically block, assert, or fail to return, **whenever `sub_fc0d9ccc` returns normally to `0xFC0BD076`, `r0` (and therefore `r4`) is always `0`**. The `r4 != 0` path (`0xFC0BD07E..0xFC0BD082` and `0xFC0BD09A`) is dead code with respect to any normal return of `sub_fc0d9ccc`.
2. **`sub_fc0d9cf6` (`0xFC0D9CF6..0xFC0D9D25`, file offset `0x0D9CF6`, 48 B)**:
   - Begins with `0xFC0D9CF6: movs r0, #3` followed by `0xFC0D9CF8: push {r4, lr}`, calls `0xFC37AD52` and `0xFC0F9BA4`, loads `r4` via `0xFC0D9D02: ldr r4, [pc, #0x50]` (targeting address `0xFC0D9D54`, whose 32-bit word is **outside `S2B` and `UNKNOWN`**), checks `ldr r0, [r4, #4]; cbnz r0, 0xFC0D9D20`, conditionally invokes `0xFC35FAAC`, `0xFC2DD73A`, `0xFC35FAAC`, `0xFC3138CC`, `0xFC35F9A8`, `0xFC2DD7A4` (all outside `S2B` / **`UNKNOWN`**), stores `1` to `[r4]`, and returns `r0 = 1` at `0xFC0D9D20..0xFC0D9D24` (which `0xFC0BD08A` ignores).
3. **Why Filesystem / SD Mount Readiness Remains `UNKNOWN` / `NOT ESTABLISHED`**:
   - Because `r4 == 0` in `task_InitFileModules` is a constant post-condition of `sub_fc0d9ccc` returning normally, testing `r4 == 0` after `sub_fc0d9cf6` provides **zero dynamic discrimination** between a mounted and an unmounted SD card.
   - Because the nested callees of `sub_fc0d9ccc` and `sub_fc0d9cf6` lie outside `S2B` (`UNKNOWN`), PORT-11A does **not** infer what those callees initialize or whether SD/FAT mount readiness has completed when `sub_fc0d9cf6` returns. Filesystem readiness across warm restart remains **`UNKNOWN`**.

---

## 5. Phase 4 — U3: `PhySw` Creator and Task-Entry Evidence

### 5.1 Startup Call Site (`0xFC05B92E`) and Creator Function `sub_fc1283d2` (Slices S3A & S3B)

In stock `task_Startup`, instruction `0xFC05B92E` (file offset `0x05B92E`, logged in Step 212 outside `S3A`; see §2.4, `sha256: 31dd3c87...fa73`) is `cc f0 50 fd` = **`bl 0xFC1283D2`** (`STATIC_VERIFIED`).

Disassembly of `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`, file offset `0x001283D2..0x001283FF`, inside Slice `S3A`):

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Architectural Effect (and `[INFERRED]` Role) | Status |
|---|---:|---|---|---|---|
| **`0xFC1283D2`** | **`0x1283D2`** | `38 b5` | `push {r3, r4, r5, lr}` | Function entry (`sub_fc1283d2`), allocates `[sp]` slot | **`STATIC_VERIFIED`** |
| `0xFC1283D4` | `0x1283D4` | `5f f7 58 fd` | `bl 0xFC087E88` | Calls `0xFC087E88` (predecessor init helper `[INFERRED]`, body `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC1283D8` | `0x1283D8` | `50 f7 d3 ff` | `bl 0xFC079382` | Calls `0xFC079382` (predecessor state check `[INFERRED]`, body `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC1283DC` | `0x1283DC` | `08 b9` | `cbnz r0, 0xFC1283E2` | If `r0 != 0`, skip `0xFC087E2C` | **`STATIC_VERIFIED`** |
| `0xFC1283DE` | `0x1283DE` | `5f f7 25 fd` | `bl 0xFC087E2C` | Conditional call to `0xFC087E2C` (body `UNKNOWN`) | **`STATIC_VERIFIED`** |
| **`0xFC1283E2`** | **`0x1283E2`** | **`c8 4c`** | **`ldr r4, [pc, #0x320]`** | **Loads `r4 = [0xFC128704] = 0x000082BC` (Slice `S3B`)** | **`STATIC_VERIFIED`** |
| `0xFC1283E4` | `0x1283E4` | `60 68` | `ldr r0, [r4, #4]` | Reads `*(uint32_t *)0x000082C0` (task handle / guard `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC1283E6` | `0x1283E6` | `00 28` | `cmp r0, #0` | Compares `*(0x000082C0)` against `0` | **`STATIC_VERIFIED`** |
| `0xFC1283E8` | `0x1283E8` | `09 d1` | `bne 0xFC1283FE` | If `*(0x000082C0) != 0`, branch to return at `0xFC1283FE` | **`STATIC_VERIFIED`** |
| `0xFC1283EA` | `0x1283EA` | `00 23` | `movs r3, #0` | Sets `r3 = 0` | **`STATIC_VERIFIED`** |
| `0xFC1283EC` | `0x1283EC` | `00 93` | `str r3, [sp]` | Stores 5th argument `[sp] = 0` | **`STATIC_VERIFIED`** |
| **`0xFC1283EE`** | **`0x1283EE`** | **`c6 4b`** | **`ldr r3, [pc, #0x318]`** | **Loads `r3 = [0xFC128708] = 0xFC1283AD` (Thumb entry pointer for `0xFC1283AC`)** | **`STATIC_VERIFIED`** |
| **`0xFC1283F0`** | **`0x1283F0`** | **`17 21`** | **`movs r1, #0x17`** | **Sets `r1 = 0x17` (`23`, task priority `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| **`0xFC1283F2`** | **`0x1283F2`** | **`c6 a0`** | **`adr r0, #0x318`** | **Sets `r0 = 0xFC12870C` (`"PhySw"`, Slice `S3B`)** | **`STATIC_VERIFIED`** |
| **`0xFC1283F4`** | **`0x1283F4`** | **`40 f6 00 02`** | **`movw r2, #0x800`** | **Sets `r2 = 0x800` (`2048`, stack size `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| **`0xFC1283F8`** | **`0x1283F8`** | **`f3 f1 48 ed`** | **`blx 0xFC31BE8C`** | **Calls ARM veneer `0xFC31BE8C` (`-> 0xBFE154E9`, `j_CreateTaskStrictly` `[INFERRED]`)** | **`STATIC_VERIFIED`** |
| `0xFC1283FC` | `0x1283FC` | `60 60` | `str r0, [r4, #4]` | Stores returned value `r0` at `0x000082C0` | **`STATIC_VERIFIED`** |
| `0xFC1283FE` | `0x1283FE` | `38 bd` | `pop {r3, r4, r5, pc}` | Returns | **`STATIC_VERIFIED`** |

**Literal & String Pool (`0xFC128704..0xFC12871F`, file offset `0x00128704..0x0012871F`, Slice S3B)**:
- `0xFC128704`: `bc 82 00 00` (`0x000082BC`, `STATIC_VERIFIED` — `PhySw` state block in Low RAM `[INFERRED]`)
- `0xFC128708`: `ad 83 12 fc` (**`0xFC1283AD`**, `STATIC_VERIFIED` — `0xFC1283AC | 1`, Thumb entry pointer for instruction address `0xFC1283AC`)
- `0xFC12870C..0xFC128711`: `50 68 79 53 77 00` (**`"PhySw\0"`**, `STATIC_VERIFIED`)
- `0xFC128714..0xFC12871E`: `50 68 79 53 77 44 72 76 2e 63 00` (**`"PhySwDrv.c\0"`**, `STATIC_VERIFIED`)

### 5.2 Key Architectural Finding: `CreateTaskStrictly` `[INFERRED]` Veneer (`0xFC31BE8C` $\to$ `0xBFE154E8`, Slices S1D & S1E)

Unlike `sub_fc0bd0b4` (which calls `blx 0xFC31BBC4`), `sub_fc1283d2` at `0xFC1283F8` calls **`blx 0xFC31BE8C`**.

Inspection of veneer `0xFC31BE8C` (Slice `S1D`) and its ATCM target `0xBFE154E8` (ROM source `0xFCEF3F34`, file offset `0x00EF3F34`, Slice `S1E`) establishes the exact call and argument-forwarding chain:
- **`0xFC31BE8C`** (`0x31BE8C`, Slice `S1D`): `04 f0 1f e5` (`ldr pc, [pc, #-4]`) + `e9 54 e1 bf` (`.word 0xBFE154E9`), branching to instruction address `0xBFE154E8` in Thumb state (`STATIC_VERIFIED`).
- **`0xBFE154E8..0xBFE15509`** (ROM `0xFCEF3F34..0xFCEF3F55`, `34` B, Slice `S1E`, `CreateTaskStrictly` `[INFERRED]`):
  ```arm
  0xBFE154E8: push  {r3, r4, r5, lr}    ; 38 b5 (decrements sp by 16 B = 0x10; r0, r1, r2 unchanged)
  0xBFE154EA: mov   r4, r3              ; 1c 46 (saves 4th arg r3 = 0xFC1283AD in r4)
  0xBFE154EC: ldr   r3, [sp, #0x10]     ; 04 9b (loads caller's 5th arg [sp_caller + 0] across 0x10 frame)
  0xBFE154EE: str   r3, [sp]            ; 00 93 (writes 5th arg into outgoing [sp] slot)
  0xBFE154F0: mov   r3, r4              ; 23 46 (restores 4th arg r3 = 0xFC1283AD)
  0xBFE154F2: bl    0xBFE14A3C          ; ff f7 a3 fa -> CALLS CreateTask (0xBFE14A3C)
  0xBFE154F6: cmp   r0, #5              ; 05 28 (checks if CreateTask returned error code 5)
  0xBFE154F8: mov   r4, r0              ; 04 46
  0xBFE154FA: bne   0xBFE15506          ; 04 d1
  0xBFE154FC: movs  r2, #0x22           ; 22 22 (0x22 = 34)
  0xBFE154FE: movs  r0, #0              ; 00 20
  0xBFE15500: adr   r1, #0x130          ; 4c a1 (computes r1 = 0xBFE15634; target bytes outside S1E / UNKNOWN)
  0xBFE15502: blx   0xBFE13E78          ; fe f7 ba ec (DebugAssert [INFERRED], body UNKNOWN)
  0xBFE15506: mov   r0, r4              ; 20 46
  0xBFE15508: pop   {r3, r4, r5, pc}    ; 38 bd
  ```
- **Architectural & Redesign Implications**:
  1. `0xBFE154E8` leaves `r0`, `r1`, and `r2` unmodified, preserves `r3` via `r4`, copies the caller's stacked 5th argument (`[sp + 0x10]`) into `[sp]`, and calls `0xBFE14A3C` (`CreateTask` `[INFERRED]`) at `0xBFE154F2` with identical `(r0, r1, r2, r3, [sp])` arguments (`r3 = 0xFC1283AD`).
  2. **Requirement to Preserve Predecessor Calls and Guard**: `sub_fc1283d2` executes three predecessor calls (`0xFC087E88`, `0xFC079382`, and conditional `0xFC087E2C`), checks the `*(0x000082C0) == 0` creation guard, and stores the returned task handle into `*(0x000082C0)` (`str r0, [r4, #4]` at `0xFC1283FC`). Any future CHDK `PhySw` hook or `taskcreate_physw_my` redesign **must preserve** those predecessor calls, the `*(0x000082C0)` guard, and the `*(0x000082C0)` handle store.

### 5.3 Periodic Task Entry `task_PhySw` `[INFERRED]` (`0xFC1283AC..0xFC1283D1`, Slice S3A)

| ROM Address | File Offset | Raw Bytes | Instruction | Direct Architectural Effect (and `[INFERRED]` Role) | Status |
|---|---:|---|---|---|---|
| **`0xFC1283AC`** | **`0x1283AC`** | `10 b5` | `push {r4, lr}` | **Function entry at `0xFC1283AC` (Thumb entry pointer `0xFC1283AD`)** | **`STATIC_VERIFIED`** |
| `0xFC1283AE` | `0x1283AE` | `d5 4c` | `ldr r4, [pc, #0x354]` | Loads `r4 = [0xFC128704] = 0x000082BC` (Slice `S3B`) | **`STATIC_VERIFIED`** |
| `0xFC1283B0` | `0x1283B0` | `08 e0` | `b 0xFC1283C4` | Unconditional branch to loop test `0xFC1283C4` on initial entry | **`STATIC_VERIFIED`** |
| `0xFC1283B2` | `0x1283B2` | `a0 68` | `ldr r0, [r4, #8]` | Loads `r0 = *(uint32_t *)0x000082C4` (sleep interval `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC1283B4` | `0x1283B4` | `f3 f1 e6 ed` | `blx 0xFC31BF84` | Calls `0xFC31BF84` (`j_SleepTask` `[INFERRED]`, body outside `S3A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC1283B8` | `0x1283B8` | `00 f0 68 f9` | `bl 0xFC12868C` | Calls `0xFC12868C` (`kbd_p1_f` `[INFERRED]`, body outside `S3A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC1283BC` | `0x1283BC` | `01 28` | `cmp r0, #1` | Compares return value `r0` against `1` | **`STATIC_VERIFIED`** |
| `0xFC1283BE` | `0x1283BE` | `01 d1` | `bne 0xFC1283C4` | If `r0 != 1`, skip `0xFC1283C0` | **`STATIC_VERIFIED`** |
| `0xFC1283C0` | `0x1283C0` | `ff f7 ad fe` | `bl 0xFC12811E` | Calls `0xFC12811E` (`kbd_p2_f` `[INFERRED]`, body outside `S3A` / `UNKNOWN`) | **`STATIC_VERIFIED`** |
| `0xFC1283C4` | `0x1283C4` | `20 68` | `ldr r0, [r4]` | Reads `*(uint32_t *)0x000082BC` (loop active flag `[INFERRED]`) | **`STATIC_VERIFIED`** |
| `0xFC1283C6` | `0x1283C6` | `00 28` | `cmp r0, #0` | Compares `*(0x000082BC)` against `0` | **`STATIC_VERIFIED`** |
| `0xFC1283C8` | `0x1283C8` | `f3 d1` | `bne 0xFC1283B2` | Loops to `0xFC1283B2` while `*(0x000082BC) != 0` | **`STATIC_VERIFIED`** |
| `0xFC1283CA` | `0x1283CA` | `bd e8 10 40` | `pop.w {r4, lr}` | Restores `r4, lr` | **`STATIC_VERIFIED`** |
| `0xFC1283CE` | `0x1283CE` | `f3 f1 95 ba` | `b.w 0xFC31B8FC` | Tail-branches to `0xFC31B8FC` (`j_ExitTask` `[INFERRED]`, body `UNKNOWN`) | **`STATIC_VERIFIED`** |

*(Provenance Note: The local-only, untracked file `/Users/avp/Project/g3x-lite/docs/UI001_ROM_RESEARCH.md` in the primary workspace—which is not tracked in git or present in clean checkouts—omitted instruction `0xFC1283B0: b 0xFC1283C4` (`08 e0`) in its transcription. Slice `S3A` establishes the exact ROM bytes at `0xFC1283AC..0xFC1283D1` without relying on any untracked notes.)*

---

## 6. Consolidated Cross-Check Against PORT-10A Claims

| ID | Claim / Hypothesis from PORT-10A | GM1.10C ROM Location | Observed ROM Evidence | PORT-11A Classification |
|---|---|---|---|---|
| **C-01** | `boot()` copies ROM `0xFCEEF24C` to Cortex-R4 ATCM `0xBFE10800..0xBFE1741B` (limit literal `0xBFE17419`) | `0xFC020040..0xFC020052` (off `0x020040`, Slice `S1A`) | Literals `0xFCEEF24C` (`0xFC0200C4`), `0xBFE10800` (`0xFC0200C8`), `0xBFE17419` (`0xFC0200CC`) copied word-by-word (`6,919` words = `27,676` B). | **`STATIC_VERIFIED`** |
| **C-02** | ARM veneer at `0xFC31BBC4` (`j_CreateTask` `[INFERRED]`) branches to `0xBFE14A3D` | `0xFC31BBC4..0xFC31BBCB` (off `0x31BBC4`, Slice `S1B`) | `04 f0 1f e5` (`ldr pc, [pc, #-4]`) + `3d 4a e1 bf` (`0xBFE14A3D`, Thumb state at `0xBFE14A3C`). | **`STATIC_VERIFIED`** |
| **C-03** | `CreateTask` prologue is `push {r4, r5, r6, lr}` (`CHDK_PORT0B_STUBS_AUDIT.md:33`) | `0xBFE14A3C` / ROM `0xFCEF3488` (off `0xEF3488`, Slice `S1C`) | Bytes at `0xFCEF3488` are `2d e9 fe 43` (`push.w {r1-r9, lr}`), NOT `70 b5`. | **`CONTRADICTED`** |
| **C-04** | `CreateTask` prologue is `push.w {r1-r9, lr}` (`2d e9 fe 43`) | `0xBFE14A3C` / ROM `0xFCEF3488` (off `0xEF3488`, Slice `S1C`) | Bytes `2d e9 fe 43 04 46 85 48` (`push.w {r1-r9, lr}; mov r4, r0; ldr r0, [pc, #0x214]`). | **`STATIC_VERIFIED`** |
| **C-05** | `CreateTask` opening load fetches literal `0x00008160` and next instruction is at `0xBFE14A44` (Thumb pointer `0xBFE14A45`) | `0xBFE14A42` / `0xBFE14C58` (ROM `0xFCEF36A4`, Slice `S1C`) | `ldr r0, [pc, #0x214]` loads `[0xBFE14C58] = 0x00008160`; next instruction (`mov r6, r1`) is at even address `0xBFE14A44` (Thumb target pointer `0xBFE14A45`). | **`STATIC_VERIFIED`** |
| **C-06** | `task_InitFileModules` entry is `0xFC0BD049` (`PORT-6C` `-0x28` shift) | `0xFC0BD048` (off `0x0BD048`, logged in Step 204 outside `S2A`) | `0xFC0BD048` contains literal word `0xFC66BBB0` (`b0 bb 66 fc`, `sha256: 17b9f5ee...5a4d`) following `0xFC0BD02E: b.w 0xFC31B980`. | **`CONTRADICTED` (Logged Outside `S2A`)** |
| **C-07** | `task_InitFileModules` entry is `0xFC0BD071` (instruction address `0xFC0BD070`) | `0xFC0BD070..0xFC0BD09B` & `0xFC0BD1A8` (Slice `S2A`) | Creator `0xFC0BD0B4` loads `r3 = [0xFC0BD1A8] = 0xFC0BD071` and `r0 = 0xFC0BD1AC` (`"InitFileModules"`). | **`STATIC_VERIFIED`** |
| **C-08** | `task_InitFileModules` `r4 == 0` check proves filesystem mount success | `0xFC0D9CCC..0xFC0D9CF5` (off `0x0D9CCC`, Slice `S2B`) | `sub_fc0d9ccc` has zero conditional branches of its own and ends with `movs r0, #0; pop {r4, pc}` (`r0 = 0` on normal return); mount readiness is not established. | **`CONTRADICTED` (as a mount-readiness proof); Mount Readiness `UNKNOWN`** |
| **C-09** | `sub_fc1283d2` is the `"PhySw"` creator function | `0xFC1283D2..0xFC1283FF` (off `0x1283D2`, Slices `S3A`/`S3B`/`S1D`/`S1E`) | Loads `"PhySw"` (`0xFC12870C`), prio `0x17`, stack `0x800`, entry `0xFC1283AD` (`0xFC128708`), calls `0xFC31BE8C` (`0xBFE154E8` $\to$ `0xBFE14A3C`). | **`STATIC_VERIFIED`** |
| **C-10** | `task_PhySw` entry is `0xFC1283AD` (instruction address `0xFC1283AC`) | `0xFC1283AC..0xFC1283D1` & `0xFC128708` (Slices `S3A`/`S3B`) | Literal at `0xFC128708` is `0xFC1283AD`; loop at `0xFC1283AC..0xFC1283D1` calls `0xFC31BF84`, `0xFC12868C`, and `0xFC12811E`. | **`STATIC_VERIFIED`** |

---

## 7. Remaining Uncertainties & Implications for PORT-9A / PORT-9B

### 7.1 What Is Statically Verified vs What Remains `UNKNOWN`

1. **`STATIC_VERIFIED` ROM Facts**:
   - **U1 Static Prologue & Continuation**: ATCM copy loop (`0xFC020040..0xFC020052`), `0xFC31BBC4` veneer (`-> 0xBFE14A3D`), `0xBFE14A3C..0xBFE14AAD` (`114` B) function body, 8-byte prologue (`2d e9 fe 43 04 46 85 48`), literal `0x00008160` at `0xBFE14C58`, next instruction address `0xBFE14A44`, and Thumb continuation pointer `0xBFE14A45`.
   - **U2 Static Task Identity**: Creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`), task name `"InitFileModules"` (`0xFC0BD1AC`), priority `0x19`, stack `0x1000`, Thumb entry pointer `0xFC0BD071` (instruction address `0xFC0BD070`), task body `0xFC0BD070..0xFC0BD09B`, and direct callees `sub_fc0d9ccc` / `sub_fc0d9cf6`.
   - **U3 Static Creator, Entry, & Call Chain**: Creator `sub_fc1283d2` (`0xFC1283D2..0xFC1283FF`), task name `"PhySw"` (`0xFC12870C`), priority `0x17`, stack `0x800`, Thumb entry pointer `0xFC1283AD` (instruction address `0xFC1283AC`), task body `0xFC1283AC..0xFC1283D1`, and the `0xFC31BE8C` $\to$ `0xBFE154E8` $\to$ `0xBFE14A3C` call chain.

2. **Remaining Uncertainties (Still `UNKNOWN` / Open Blockers)**:
   - **U2 Filesystem Mount Readiness Semantics (`UNKNOWN`)**: Because `sub_fc0d9ccc` (`0xFC0D9CCC`) always returns `0` on normal return and the nested callees of `sub_fc0d9ccc` / `sub_fc0d9cf6` (as well as `[0xFC0D9D54]`) were not inspected (`UNKNOWN`), executing `task_InitFileModules` does **not** establish when or how the SD card FAT filesystem becomes ready for CHDK file I/O across a warm restart.
   - **Exhaustive Caller Graph of `sub_fc0bd0b4` (`UNKNOWN`)**: Whether `task_Startup` or warm-restart initialization reaches `sub_fc0bd0b4` via indirect calls or uninspected dispatchers remains `UNKNOWN`.
   - **U4 (`SpyTask` Creation Point, Priority, and Heap Headroom Interaction)**: Remains **`UNKNOWN / UNVERIFIED`**.
   - **Runtime Hook Safety, Stack Adequacy, & Callee Bodies (`UNKNOWN`)**: Callee bodies outside `S1A`–`S3B` (`0xFC12868C`, `0xFC12811E`, `0xFC31BF84`, `0xFC31B8FC`, `0xFC087E88`, `0xFC079382`, `0xFC087E2C`, `0xFC31B278`, `0xFC35B93C`, `0xBFE10B88`, `0xBFE10D14`, `0xBFE13E78`), ATCM I-cache/BPU coherence at patch time, `mykbd_task` stack adequacy (`0x800` vs `0x2000`), and warm-restart hardware safety (`BLK-16` P11–P13/P15) remain **`UNKNOWN`**.

### 7.2 Implications for the PORT-9A / PORT-9B Offline Model

- **PORT-9A (`tools/port9a_runtime_lifecycle.py`)**:
  - Per task constraints, `GM110C_PRECONDITIONS` remains all `False` in this milestone.
  - Any future `PhySw` hook design must account for two static facts proven in §5.1–§5.2:
    1. `sub_fc1283d2` calls `0xFC31BE8C` (`CreateTaskStrictly` `[INFERRED]`) with `r2 = 0x800`, which delegates to `0xBFE14A3C` (`CreateTask` `[INFERRED]`).
    2. `sub_fc1283d2` performs predecessor calls (`0xFC087E88`, `0xFC079382`, conditional `0xFC087E2C`), checks the `*(0x000082C0) == 0` guard, and stores the created task handle into `*(0x000082C0)`. Any future redesign (whether intercepting inside `CreateTask_my` or replacing `bl sub_fc1283d2` with a wrapper) must preserve those predecessor calls, guard, and handle store.
- **PORT-9B (`tools/port9b_runtime_contract.py`)**:
  - Remains 100% valid (`RESULT ok`; all 51 unit tests pass). Keeping `GM110C_PRECONDITIONS` all `False` ensures `C3` continues to forbid premature activation of `I1–I4` in tracked sources.

---

## 8. Reproducibility Commands (All Nine Pinned Slices `S1A`–`S3B`)

Anyone with access to the local-only `PRIMARY.BIN` (`SHA-256 = 99118557...2578`) can verify the firmware image and all **nine pinned slices (`S1A`–`S3B`, 1,284 bytes)** using standard POSIX commands:

```sh
ROM=/Users/avp/Project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN

# 0. Verify full firmware image SHA-256 (33,554,432 bytes)
shasum -a 256 "$ROM"
# Expected: 9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578

# 1. Slice S1A — Early boot ATCM copy loop & literal pool (0xFC020040..0xFC0200CF, offset 0x020040, 144 B)
dd if="$ROM" bs=1 skip=$((0x020040)) count=144 2>/dev/null | shasum -a 256
# Expected: a8bea578f65643701322d3ce2fc500d04485323dbb28bfab6e89a51a6344c54b

# 2. Slice S1B — 0xFC31BBC4 ARM veneer (0xFC31BBC4..0xFC31BBCB, offset 0x31BBC4, 8 B)
dd if="$ROM" bs=1 skip=$((0x31BBC4)) count=8 2>/dev/null | shasum -a 256
# Expected: e7f6fb4484c3a010e0db4a97edd252a10e92c529f0e75190a0cf98a479fa566d

# 3. Slice S1C — CreateTask body & literals in ATCM ROM source (0xFCEF3488..0xFCEF36B3, offset 0xEF3488, 556 B)
dd if="$ROM" bs=1 skip=$((0xEF3488)) count=556 2>/dev/null | shasum -a 256
# Expected: 409dcaec41a0e5aeba37110254919995f018aae13fcc942b832ffc244c223b36

# 4. Slice S1D — 0xFC31BE8C ARM veneer (0xFC31BE8C..0xFC31BE93, offset 0x31BE8C, 8 B)
dd if="$ROM" bs=1 skip=$((0x31BE8C)) count=8 2>/dev/null | shasum -a 256
# Expected: f4a9356c75017083e2dbabbc309815595ae745a3787bbb5128e1e823601079b3

# 5. Slice S1E — CreateTaskStrictly body in ATCM ROM source (0xFCEF3F34..0xFCEF3F55, offset 0xEF3F34, 34 B)
dd if="$ROM" bs=1 skip=$((0xEF3F34)) count=34 2>/dev/null | shasum -a 256
# Expected: ce4d1016656cd6053e9808a6cf718d18e885948f0b7102a15cef88bcaacad612

# 6. Slice S2A — task_InitFileModules, creator sub_fc0bd0b4, & literals (0xFC0BD070..0xFC0BD1BB, offset 0x0BD070, 332 B)
dd if="$ROM" bs=1 skip=$((0x0BD070)) count=332 2>/dev/null | shasum -a 256
# Expected: 2c939717866f0a5c4c8df88e8f75942890347cdd7453fbe54bdcc33125020c94

# 7. Slice S2B — sub_fc0d9ccc and sub_fc0d9cf6 (0xFC0D9CCC..0xFC0D9D25, offset 0x0D9CCC, 90 B)
dd if="$ROM" bs=1 skip=$((0x0D9CCC)) count=90 2>/dev/null | shasum -a 256
# Expected: 4e3f0f99e5605d08d6ba093146e86f009b28121220c632dae05f0a479e218ee8

# 8. Slice S3A — task_PhySw and creator sub_fc1283d2 (0xFC1283AC..0xFC1283FF, offset 0x1283AC, 84 B)
dd if="$ROM" bs=1 skip=$((0x1283AC)) count=84 2>/dev/null | shasum -a 256
# Expected: 8d38c2112b67283d302f77bd881ab9ccf4b2f7f1b4bfffc51bb531fd2151385a

# 9. Slice S3B — PhySw literal and string pool (0xFC128704..0xFC12871F, offset 0x128704, 28 B)
dd if="$ROM" bs=1 skip=$((0x128704)) count=28 2>/dev/null | shasum -a 256
# Expected: fdace2c951b23e71497dab6d9e160a439a72f20f24fbcb362bbd014d3714b376
```

---

## 9. Recommended Next Engineering Milestone

- **Recommended Next Milestone — PORT-11B (Offline Runtime Contract & Precondition Refinement Without Further ROM Scans)**:
  1. Using **only** the `STATIC_VERIFIED` facts already established in PORT-11A (zero new ROM reads or scans), refine the offline runtime precondition model (`PORT-9A` / `PORT-9B`) to separate **static ROM address/instruction verification** (`U1` prologue/literal, `U2` task entry `0xFC0BD071`, `U3` creator `0xFC1283D2` + entry `0xFC1283AD`) from **unverified dynamic runtime/mount safety preconditions** (`U2` filesystem mount readiness, `U4` `SpyTask` gate, and runtime hook safety), ensuring fail-closed enforcement (`C3` continues to forbid active hooks in source while any runtime precondition remains `False`).
  2. Record the `sub_fc1283d2` predecessor-call/guard preservation requirement and the `0xFC31BE8C` $\to$ `0xBFE154E8` $\to$ `0xBFE14A3C` (`CreateTaskStrictly` $\to$ `CreateTask`) call path in the offline contract model.
  3. Treat all unspecified firmware details as `UNKNOWN`, keep all runtime hooks disabled in source, and maintain **Hardware STRICT NO-GO**.
