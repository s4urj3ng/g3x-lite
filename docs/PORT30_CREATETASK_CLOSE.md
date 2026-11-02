# PORT-30 T1: Bounded CreateTask Evidence Read, Manifest & GO/NO-GO Verdict

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-30 T1 (`p30-t1-createtask-close-evidence`)
- **Primary Source**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (offline host analysis; 33,554,432 bytes; base `0xFC000000`) `[VERIFIED]`
- **Baseline Context**: `docs/PORT29_CREATETASK_EVIDENCE.md:408-420` (§6.2 Remaining UNKNOWN List), `docs/HANDOFF.md:2418-2431`, `evidence/port29_manifest.json`, `evidence/port29_trusted_scopes.json`, `AGENTS.md`, `docs/SAFETY.md`
- **Output Artifacts**:
  - `docs/PORT30_CREATETASK_CLOSE.md`
  - `evidence/port30_manifest.json`
  - `evidence/port30_trusted_scopes.json`
- **Verdict**: **`NO-GO`** (Parameter roles `r0`, `r1`, `r2`, and storage of `sp[0]` into `[TCB + 0x10]` are `[VERIFIED]`; stack allocator internal identity, buffer alignment, runtime default stack size values on both fallback paths, task-argument delivery to spawned task, and `SleepTask` tick scaling remain `[UNKNOWN]`)

---

## 1. Executive Summary & Epistemic Standards

This dossier closes the `CreateTask` UNKNOWN items left open by milestone **PORT-29** for Canon PowerShot G3 X firmware **GM1.10C**. All disassemblies, instruction traces, and cryptographic hashes were conducted strictly on the offline workstation from `firmware/dumps/GM1.10C/PRIMARY.BIN`.

### 1.1 ROM Read Policy Compliance
1. **Strict Read Scope Compliance**: Only ranges explicitly enumerated with an exact start address and length in the PORT-29 remaining-UNKNOWN list (`docs/PORT29_CREATETASK_EVIDENCE.md:411-420` §6.2 and `docs/HANDOFF.md:2421-2430`) were read.
2. **Quota and Range Bounds**:
   - Each individual new range is at most 512 bytes (well within the 4,096-byte per-range ceiling).
   - Exactly 7 new ranges were read, totaling **900 new bytes** (well within the authorized 8,192 new-byte budget).
   - The 6 ranges previously read and validated in PORT-29 are re-cited with identical bounds and SHA-256 digests; zero PORT-29 manifest ranges were widened.
   - Total bytes declared across all 13 entries in `evidence/port30_manifest.json` is **2,618 bytes** (under the 4,096-byte scope maximum quota).
3. **Traceability of New Ranges**: Every newly read range traces directly to an exact row and citation in `docs/PORT29_CREATETASK_EVIDENCE.md` §6.2 and `docs/HANDOFF.md` lines 2421–2430.
4. **No Out-of-Bounds Reads or Scans**: No full-ROM scans, heuristic searches, or caller sweeps outside the authorized ranges were performed.
5. **No Firmware Flashing or Hardware Access**: No camera hardware was connected, no SD card was modified, no binaries or ROM payloads were built, and zero binary blobs or raw ROM bytes were committed `[VERIFIED: docs/SAFETY.md:3-8; AGENTS.md:18-24]`.

### 1.2 Evidence Validator Execution & Output
The machine-readable evidence manifest was verified using `tools/port11c_evidence_validator.py` with zero extra flags:

```bash
python3 -B tools/port11c_evidence_validator.py --manifest evidence/port30_manifest.json --trusted-scopes evidence/port30_trusted_scopes.json
```

**Exact Quoted Validator Output**:
```
Evidence Manifest Validation: 13 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED
----------------------------------------------------------------------
----------------------------------------------------------------------
Result: VALID (0 errors, 0 warnings)
```

### 1.3 Instruction Word Notation Convention
All ARM Thumb and Thumb-2 instructions cited throughout this document use explicit 16-bit Thumb halfwords in `0xHHHH` form (hexadecimal, 4 uppercase hex digits preceded by `0x`). 32-bit Thumb-2 instructions are written as two 16-bit halfwords in execution order (first halfword followed by second halfword, e.g. `0xE92D 0x41FC` for `push.w {r2-r8, lr}` at `0xFCEF0192`, `0xF000 0xFB65` for `bl 0xBFE11E62` at `0xFCEF01E0`, or `0xF000 0xFB24` for `bl 0xBFE11E04` at `0xFCEF0204`). All instruction words and offsets are re-derived directly from the bytes read inside the authorized ROM ranges.

---

## 2. Table of Every Range Read (Section a)

The table below catalogs every ROM range read for PORT-30, including re-cited PORT-29 ranges and newly authorized PORT-30 ranges, in ROM start address order. For each range, the file offset in `PRIMARY.BIN` ($\text{Offset} = \text{Address} - 0\text{xFC000000}$), byte length, SHA-256 cryptographic hash, read status (`New` or `Re-cited`), running total of new bytes, and exact listing source in `docs/PORT29_CREATETASK_EVIDENCE.md` / `docs/HANDOFF.md` are documented.

| Range ID | Target Routine / Subsystem | ROM Start | ROM End | File Offset | Length | Status | Running New | SHA-256 Digest | Listing Source in PORT-29 Evidence / HANDOFF |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|---|
| **PORT29-ROM-N1** | `sub_fc31b408` heap init veneer table | `0xFC31B408` | `0xFC31B507` | `0x0031B408` | 256 B | Re-cited | 0 B | `b93e3f48ab31f467e9ee3f4ba907ea3032a3a81cac4fe1ff18a2c0ba138181ce` | `docs/PORT29_CREATETASK_EVIDENCE.md:54` §2 (Re-cited PORT-29 manifest range) |
| **PORT30-ROM-INIT-811C** | Secondary default stack size ROM initializer | `0xFCE91170` | `0xFCE9118F` | `0x00E91170` | 32 B | **New** | 32 B | `66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925` | `docs/PORT29_CREATETASK_EVIDENCE.md:415` (§6.2, Row 4); `docs/HANDOFF.md:2426` (Row 4) |
| **PORT30-ROM-INIT-81D0** | Primary default stack size ROM initializer | `0xFCE91220` | `0xFCE9123F` | `0x00E91220` | 32 B | **New** | 64 B | `e63a1b3b97dd2950c54eae572c9e857e6246e251814c11802a9c687f670eaf6c` | `docs/PORT29_CREATETASK_EVIDENCE.md:414` (§6.2, Row 3); `docs/HANDOFF.md:2425` (Row 3) |
| **PORT30-ROM-ACTIVATE-CALLEE2** | Activation callee 2: task enqueue (`0xFCEEF438`) | `0xFCEEF430` | `0xFCEEF4AF` | `0x00EEF430` | 128 B | **New** | 192 B | `0c2fee6daa607075ee78299c3b6005bd021bb46b32a08e9e3f9d8ef38147d386` | `docs/PORT29_CREATETASK_EVIDENCE.md:419` (§6.2, Row 8); `docs/HANDOFF.md:2430` (Row 8) |
| **PORT29-ROM-N3** | `alloc_task_stack_tcb` body (`0xBFE10B88`) | `0xFCEEF5C0` | `0xFCEEF7BF` | `0x00EEF5C0` | 512 B | Re-cited | 192 B | `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2` | `docs/PORT29_CREATETASK_EVIDENCE.md:58` §2 (Re-cited PORT-29 manifest range) |
| **PORT29-ROM-N4** | `activate_task` helper remainder | `0xFCEEF7C0` | `0xFCEEF9C3` | `0x00EEF7C0` | 516 B | Re-cited | 192 B | `c4603dc40c67f2f563a0e41efddd4f5ac50fbaf64b5c2272263622b424eedabc` | `docs/PORT29_CREATETASK_EVIDENCE.md:59` §2 (Re-cited PORT-29 manifest range) |
| **PORT30-ROM-ACTIVATE-CALLEE1** | Activation callee 1: TCB lookup (`0xFCEF007E`) | `0xFCEF0070` | `0xFCEF00EF` | `0x00EF0070` | 128 B | **New** | 320 B | `efb95b96c288b0cb1e153cfba32a660e2dd2bdeac20223bb22eb4a3722cbc7ac` | `docs/PORT29_CREATETASK_EVIDENCE.md:418` (§6.2, Row 7); `docs/HANDOFF.md:2429` (Row 7) |
| **PORT30-ROM-ALLOC-TASK** | Kernel task allocator (`0xBFE11746`) | `0xFCEF0180` | `0xFCEF037F` | `0x00EF0180` | 512 B | **New** | 832 B | `504cc373cf058c055fa66ae38bd8ad9aa6ccd7c85d31d01e3e33f273692f6405` | `docs/PORT29_CREATETASK_EVIDENCE.md:412, 417` (§6.2, Rows 1 & 6); `docs/HANDOFF.md:2423, 2428` (Rows 1 & 6) |
| **PORT29-ROM-N5** | `DebugAssert` entry veneer table (`0xBFE13E78`) | `0xFCEF28B0` | `0xFCEF29AF` | `0x00EF28B0` | 256 B | Re-cited | 832 B | `93c956e9d994888fc228997a65d0785901a4c23e0921c5e3cf6befa450fb2142` | `docs/PORT29_CREATETASK_EVIDENCE.md:62` §2 (Re-cited PORT-29 manifest range) |
| **PORT30-ROM-SLEEPTASK** | Reconciled `SleepTask` body (`0xBFE14968`) | `0xFCEF33A0` | `0xFCEF33DF` | `0x00EF33A0` | 64 B | **New** | 896 B | `ee0ef02f81b7f50a81c60d40a752542ff09be03a185eb3d5d69119c4cf0f3c61` | `docs/PORT29_CREATETASK_EVIDENCE.md:416` (§6.2, Row 5); `docs/HANDOFF.md:2427` (Row 5) |
| **PORT29-ROM-CREATETASK** | `CreateTask` body & calling convention | `0xFCEF3488` | `0xFCEF34F9` | `0x00EF3488` | 114 B | Re-cited | 896 B | `6d7fbecb5f9589cc34994a63ac6cf7e2def132a7c355a789a29ea3cae8c50ddf` | `docs/PORT29_CREATETASK_EVIDENCE.md:63` §2 (Re-cited PORT-29 manifest range) |
| **PORT30-ROM-CREATETASK-LIT** | `CreateTask` literal pool entry (`0xFCEF36A0`) | `0xFCEF36A0` | `0xFCEF36A3` | `0x00EF36A0` | 4 B | **New** | **900 B** | `4a9f5cbccf8b59d7df28cb6af0bd9d7373f1209b30fcfe86786a37ab7f88e1a2` | `docs/PORT29_CREATETASK_EVIDENCE.md:413` (§6.2, Row 2); `docs/HANDOFF.md:2424` (Row 2) |
| **PORT29-ROM-N6** | ATCM interrupt disable & restore routines | `0xFCEF3A20` | `0xFCEF3A5F` | `0x00EF3A20` | 64 B | Re-cited | 900 B | `3bf663507211b96500c59647e3f065cff96d111421ee5a2c867c022536c45969` | `docs/PORT29_CREATETASK_EVIDENCE.md:64` §2 (Re-cited PORT-29 manifest range) |

- **Total New Bytes Read in PORT-30**: **900 bytes** ($\le 8,192\text{ bytes}$ limit).
- **Total Combined Bytes in Manifest**: **2,618 bytes** ($\le 4,096\text{ bytes}$ scope budget).
- **Widened Ranges**: **None** (zero PORT-29 ranges widened; all 6 PORT-29 entries are re-cited exactly).

---

## 3. Evaluation of Each PORT-29 UNKNOWN Item (Section b)

This section evaluates each item left open or classified as `[INFERRED]` / `[UNKNOWN]` in `docs/PORT29_CREATETASK_EVIDENCE.md:382-392` (§5) and `docs/HANDOFF.md:2398-2406`.

### 3.1 Role of `r0`: Task Name String Pointer `[VERIFIED]`
- **Citations & Disassembly Reasoning**:
  - `0xFCEF348C` (`0x4604`): `mov r4, r0` preserves incoming `r0` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34AC` (`0xB904`): `cbnz r4, 0xbfe14a64` checks if caller passed non-zero pointer `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34AA` (`0x497D`): `ldr r1, [pc, #0x1f4]` loads literal pointer from $\text{Align}(0\text{xFCEF34AA}+4, 4) + 0\text{x1F4} = \mathbf{0\text{xFCEF36A0}}$. Inside newly read range `PORT30-ROM-CREATETASK-LIT` (`0xFCEF36A0..0xFCEF36A3`), the 32-bit literal word is verified as **`0x000081CC`** (little-endian bytes `cc 81 00 00`, SHA-256 `4a9f5cbccf8b59d7df28cb6af0bd9d7373f1209b30fcfe86786a37ab7f88e1a2`) `[VERIFIED]`.
  - `0xFCEF34AE` (`0x680C`): `ldr r4, [r1]` executes if `r0 == 0`, loading default name pointer `*(0x000081CC)` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF640` (`0xA801`): `add r0, sp, #4` computes descriptor base pointer `desc = sp + 4` in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEEF642` (`0xF8CD 0x8018`): `str.w r8, [sp, #24]` stores the task name pointer into descriptor offset `desc + 20` (`sp + 24`, with `desc = sp + 4`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF0272` (`0x6968`): `ldr r0, [r5, #0x14]` loads `[desc + 20]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0274` (`0x6260`): `str r0, [r4, #0x24]` stores the loaded name pointer directly into `[TCB + 0x24]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - Corroborated by stock startup call site `0xFC05B98E` (`docs/PORT27_RESIDENT_EVIDENCE.md:268, 278`) passing pointer to ASCII string `"Startup\0"` into `r0`.
- **Verdict**: **`[VERIFIED]`**. Argument forwarding, null-check fallback, storage into descriptor `desc + 20`, and direct storage into `[TCB + 0x24]` are all verified in ROM.

### 3.2 Role of `r1`: Task Scheduling Priority `[VERIFIED]`
- **Citations & Disassembly Reasoning**:
  - `0xFCEF3490` (`0x460E`): `mov r6, r1` preserves incoming `r1` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B0` (`0x1E70`): `subs r0, r6, #1` decrements by 1 `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B2` (`0x2820`): `cmp r0, #0x20` compares `r1 - 1` against 32 `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B4` (`0xD200`): `bhs 0xbfe14a6c` branches to assertion error path if $r1 < 1$ or $r1 > 32$, strictly enforcing $1 \le r1 \le 32$ `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF638` (`0xF88D 0x401D`): `strb.w r4, [sp, #29]` stores the validated priority byte into descriptor offset `desc + 25` (`desc = sp + 4`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF022E` (`0x7E68`): `ldrb r0, [r5, #0x19]` loads `[desc + 25]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0230` (`0x60A0`): `str r0, [r4, #0x8]` stores priority into `[TCB + 0x8]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0234` (`0xF8A4 0x0046`): `strh.w r0, [r4, #0x46]` stores priority halfword into `[TCB + 0x46]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEEF458` (`0x68A8`): `ldr r0, [r5, #0x8]` reads `[TCB + 0x8]` in downstream activation callee `0xBFE109EC` (`PORT30-ROM-ACTIVATE-CALLEE2`), using it to index the scheduling ready-queue array and calling enqueue routine `0xFCEEF464: bl 0xBFE126C4` `[VERIFIED]`.
- **Verdict**: **`[VERIFIED]`**. The range check ($1 \le r1 \le 32$), storage into descriptor `desc + 25`, placement into TCB priority fields `[TCB + 0x8]` and `[TCB + 0x46]`, and consumption by the scheduler ready queue are verified in ROM.

### 3.3 Role of `r2`: Task Stack Size in Bytes `[VERIFIED]`
- **Citations & Disassembly Reasoning**:
  - `0xFCEF3492` (`0x4615`): `mov r5, r2` preserves incoming `r2` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34C8` (`0xB905`): `cbnz r5, 0xbfe14a80` preserves caller's explicit value if `r2 != 0` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34CA` (`0x684D`): `ldr r5, [r1, #4]` executes if `r2 == 0`. Register `r1` holds `0x000081CC` (verified from `0xFCEF36A0`), accessing primary default address `0x000081CC + 4 = 0x000081D0` `[VERIFIED: PORT29-ROM-CREATETASK, PORT30-ROM-CREATETASK-LIT]`.
  - `0xFCEEF5E0` (`0xB90B`): `cbnz r3, 0xbfe10b9a` in `alloc_task_stack_tcb` verifies parameter `r3`. If primary fallback `*(0x81D0)` yields zero, instruction `0xFCEEF5E2` (`0x4BF3`: `ldr r3, [pc, #972]`) loads literal `0x0000811C` at `0xFCEEF9B0` and `0xFCEEF5E4` (`0x681B`: `ldr r3, [r3]`) loads secondary fallback `*(0x811C)` `[VERIFIED: PORT29-ROM-N3, PORT29-ROM-N4]`.
  - `0xFCEEF624` (`0xC00E`): `stmia r0!, {r1, r2, r3}` stores the resolved value into stack-frame offset `sp + 20` / descriptor offset `desc + 16` (`desc = sp + 4`) `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF01DE` (`0x6929`): `ldr r1, [r5, #0x10]` loads `[desc + 16]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`), passing it directly in `r1` to dynamic allocator callee `0xBFE11E62` (`0xFCEF01E0: bl 0xBFE11E62`) `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0202` (`0x6929`): `ldr r1, [r5, #0x10]` loads `[desc + 16]` and passes it in `r1` to stack framing helper `0xBFE11E04` (`0xFCEF0204: bl 0xBFE11E04`) `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0246` (`0x6928`): `ldr r0, [r5, #0x10]` loads `[desc + 16]` and `0xFCEF0248` (`0x6220`: `str r0, [r4, #0x20]`) stores it directly into `[TCB + 0x20]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
- **Verdict**: **`[VERIFIED]`**. Argument forwarding, primary and secondary fallback loads, forwarding to dynamic allocator `0xBFE11E62` and framing routine `0xBFE11E04`, and storage in `[TCB + 0x20]` are verified in ROM.

### 3.4 Role of `sp[0]`: Task Entry Context Argument Storage `[VERIFIED]` / Task-Argument Delivery `[UNKNOWN]`
- **Citations & Disassembly Reasoning**:
  - `0xFCEF3494` (`0xF8DD 0x8028`): `ldr.w r8, [sp, #0x28]` loads caller's 5th argument passed on stack (`sp_entry + 0x00` after 40-byte push) into `r8` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34CE` (`0x4641`): `mov r1, r8` forwards `r8` into `r1` for callee `0xBFE10B88` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF624` (`0xC00E`): `stmia r0!, {r1, r2, r3}` writes incoming `r1` into descriptor offset `desc + 8` (`sp + 12`, with `desc = sp + 4`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF0240` (`0x68A8`): `ldr r0, [r5, #0x8]` loads `[desc + 8]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0244` (`0x6120`): `str r0, [r4, #0x10]` stores the context argument directly into `[TCB + 0x10]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - **Stock Call Site Context**: Corroborated by stock startup call site `0xFC05B984..0xFC05B986` (`docs/PORT27_RESIDENT_EVIDENCE.md:263-264, 282`) storing `0` at `sp[0]`. While consistent with passing a null/zero argument, a zero argument at a single call site proves nothing about delivery mechanism.
  - **Consumer / Dispatcher Gap**: No downstream task dispatcher, scheduler context restorer, or execution switch routine has been shown in the read slices delivering the value in `[TCB + 0x10]` into `r0` (or another parameter register) when the newly spawned task executes.
- **Verdict**:
  - Retrieval of 5th parameter from caller stack `sp[0]`, forwarding through descriptor `desc + 8`, and storage into `[TCB + 0x10]`: **`[VERIFIED]`**.
  - Delivery of this argument to the task entry function by the task dispatcher / scheduler: **`[UNKNOWN]`** (remains open due to consumer/dispatcher gap).

### 3.5 Corroborating Role of `r3`: Task Entry Point `[VERIFIED]`
- **Citations & Disassembly Reasoning**:
  - `0xFCEF3498` (`0x461F`): `mov r7, r3` preserves incoming `r3` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B6` (`0xB93F`): `cbnz r7, 0xbfe14a7c` checks $r3 \ne 0$ else branches to panic handler `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF61E` (`0xE9CD 0x6001`): `strd r6, r0, [sp, #4]` stores entry pointer into descriptor offset `desc + 4` (`sp + 8`, with `desc = sp + 4`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF023C` (`0x6868`): `ldr r0, [r5, #0x4]` loads `[desc + 4]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF023E` (`0x60E0`): `str r0, [r4, #0xC]` stores entry function pointer directly into `[TCB + 0xC]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
- **Verdict**: **`[VERIFIED]`**. Non-null check, forwarding through descriptor `desc + 4`, and storage in `[TCB + 0xC]` are verified in ROM.

### 3.6 The `r2` Stack Allocator: Dynamic Allocation Delegation `[VERIFIED]` / Allocator Implementation `[UNKNOWN]`
- **Citations & Disassembly Reasoning**:
  - In `alloc_task_stack_tcb` (`0xBFE10B88`), instruction `0xFCEEF61C..0xFCEEF624` writes a hardcoded `0` into descriptor offset `desc + 12` (`[sp, #16]`, with `desc = sp + 4`) via `stmia r0!, {r1, r2, r3}` (`r2` was cleared to 0) `[VERIFIED: PORT29-ROM-N3]`.
  - In `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`):
    - `0xFCEF01D6` (`0x68EE`): `ldr r6, [r5, #0xC]` loads caller stack buffer pointer `[desc + 12]` into `r6` `[VERIFIED]`.
    - `0xFCEF01D8` (`0x2000`): `movs r0, #0` clears `r0` `[VERIFIED]`.
    - `0xFCEF01DA` (`0x4607`): `mov r7, r0` sets `r7 = 0` `[VERIFIED]`.
    - `0xFCEF01DC` (`0xB976`): `cbnz r6, 0xFCEF01FC` tests `r6`.
      - When `r6 != 0` (indicating a caller-supplied static buffer), `cbnz r6` branches to `0xFCEF01FC`. At `0xFCEF01FC` (`0xF884 0x704A`: `strb.w r7, [r4, #0x4A]`), flag `0` is stored in `[TCB + 0x4A]` (marking a non-dynamic buffer), followed by `0xFCEF0200` (`0x4630`: `mov r0, r6`), loading `[desc + 16]` into `r1` at `0xFCEF0202`, and invoking stack setup helper `0xBFE11E04` (`0xFCEF0204: bl 0xBFE11E04`).
      - However, for all tasks created via `CreateTask`, `desc + 12` is unconditionally 0 (`r6 == 0`). Thus, `cbnz r6` is **not taken**, and execution falls through to `0xFCEF01DE`!
    - When `r6 == 0` (the `CreateTask` execution path):
      - `0xFCEF01DE` (`0x6929`): `ldr r1, [r5, #0x10]` loads the requested stack byte count from `desc + 16` into `r1` `[VERIFIED]`.
      - `0xFCEF01E0` (`0xF000 0xFB65`): `bl 0xBFE11E62` (ROM target `0xFCEF08AE`) calls the dynamic memory allocator `0xBFE11E62` with `r1 = stack_size` `[VERIFIED]`.
      - `0xFCEF01E4` (`0x0006`): `movs r6, r0` preserves the returned buffer pointer in `r6` `[VERIFIED]`.
      - `0xFCEF01E6` (`0xD105`): `bne 0xFCEF01F4` checks allocation success; if `r6 == 0` (allocation failed), execution falls through to error / panic at `0xFCEF01E8..0xFCEF01F2` `[VERIFIED]`.
      - `0xFCEF01F4` (`0x2080`): `movs r0, #0x80` `[VERIFIED]`.
      - `0xFCEF01F6` (`0xF884 0x004A`): `strb.w r0, [r4, #0x4A]` records dynamic allocation flag `0x80` in `[TCB + 0x4A]` `[VERIFIED]`.
      - `0xFCEF01FA` (`0xE001`): `b 0xFCEF0200` branches to common stack framing `[VERIFIED]`.
    - Downstream common stack framing:
      - `0xFCEF0200` (`0x4630`): `mov r0, r6` places the buffer pointer (returned by `0xBFE11E62`) into `r0` `[VERIFIED]`.
      - `0xFCEF0202` (`0x6929`): `ldr r1, [r5, #0x10]` loads stack size into `r1` `[VERIFIED]`.
      - `0xFCEF0204` (`0xF000 0xFB24`): `bl 0xBFE11E04` (ROM target `0xFCEF0850`) invokes the stack framing / initialization routine with `r0 = stack_buffer` and `r1 = stack_size` `[VERIFIED]`.
  - Control-Flow & Allocator Delegation Findings:
    1. `CreateTask` callers **never provide a stack buffer pointer** (`desc + 12 == 0`).
    2. Dynamic stack allocation is delegated by `0xBFE11746` to routine `0xBFE11E62` (`ROM 0xFCEF08AE`) with `r1 = stack_size`.
    3. The subsequent call to `0xBFE11E04` (`ROM 0xFCEF0850`) at `0xFCEF0204` is NOT the dynamic memory allocator; it receives the already allocated buffer (`r0 = r6`) and formats the initial stack frame.
    4. Routine `0xBFE11E62` (ROM `0xFCEF08AE`) lies outside the read slices, so its internal heap pool, sub-allocator identity, and alignment behavior are unread.
- **Verdict**:
  - Delegation to dynamic allocator `0xBFE11E62` (ROM `0xFCEF08AE`) with `r1 = stack_size` and dynamic flag `0x80` recorded in `[TCB + 0x4A]`: **`[VERIFIED]`**.
  - Internal identity and heap mechanism of allocator `0xBFE11E62`: **`[UNKNOWN]`**.

### 3.7 The `r2` Stack Size: Explicit Size `[VERIFIED]` / Runtime Default Size `[UNKNOWN]`
- **Explicit Size (`r2 != 0`)**:
  - The caller-supplied positive integer is preserved in `r5` (`0xFCEF3492: mov r5, r2`), bypassed past fallback logic (`0xFCEF34C8: cbnz r5`), forwarded to `alloc_task_stack_tcb` and stored in `desc + 16`, passed in `r1` to dynamic allocator `0xBFE11E62` (`0xFCEF01DE..0xFCEF01E0`) and framing routine `0xBFE11E04` (`0xFCEF0202..0xFCEF0204`), and recorded in `[TCB + 0x20]` (`0xFCEF0248: str r0, [r4, #0x20]`).
  - Status: **`[VERIFIED]`**.
- **Default Size (`r2 == 0`)**:
  - **Primary Fallback (`*(0x000081D0)`)**:
    - Instruction `0xFCEF34CA` (`0x684D`: `ldr r5, [r1, #4]`) dereferences `*(0x000081D0)` (where `r1 = 0x000081CC` is verified in `PORT30-ROM-CREATETASK-LIT`) `[VERIFIED]`.
    - Range `PORT30-ROM-INIT-81D0` (`0xFCE91220..0xFCE9123F`, 32 B) contains the ROM source word copied to RAM `0x000081D0` via early boot Copy Loop 3 (`0xFC020054..0xFC020066`, `docs/PORT21_RAM_LIFETIME.md:33, 210, 307`). ROM address $0\text{xFCE91058} + (0\text{x81D0} - 0\text{x8000}) = \mathbf{0\text{xFCE91228}}$ holds 32-bit word **`0x00000000`** (SHA-256 `e63a1b3b97dd2950c54eae572c9e857e6246e251814c11802a9c687f670eaf6c`) `[VERIFIED]`.
    - Because the initial boot value is `0x00000000`, the runtime value at `*(0x000081D0)` depends entirely on runtime writers that modify `0x81D0` after Copy Loop 3 and before `CreateTask` callers execute.
    - Those runtime writers are unread in ROM and their addresses are not evidenced in any committed doc (`UNKNOWN-location`).
    - Status: **`[UNKNOWN]`**.
  - **Secondary Fallback (`*(0x0000811C)`)**:
    - In `alloc_task_stack_tcb`, when `r3 == 0` (due to primary default yielding zero), instruction `0xFCEEF5E2` (`0x4BF3`: `ldr r3, [pc, #972]`) loads literal `0x0000811C` at `0xFCEEF9B0` and `0xFCEEF5E4` (`0x681B`: `ldr r3, [r3]`) dereferences `*(0x0000811C)` `[VERIFIED]`.
    - Range `PORT30-ROM-INIT-811C` (`0xFCE91170..0xFCE9118F`, 32 B) contains the ROM source word copied to RAM `0x0000811C` via early boot Copy Loop 3. ROM address $0\text{xFCE91058} + (0\text{x811C} - 0\text{x8000}) = \mathbf{0\text{xFCE91174}}$ holds 32-bit word **`0x00000000`** (SHA-256 `66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925`) `[VERIFIED]`.
    - Because the initial boot value is `0x00000000`, the runtime value at `*(0x0000811C)` depends entirely on runtime writers modifying `0x811C`.
    - Those runtime writers are unread in ROM and unlocalised (`UNKNOWN-location`).
    - Status: **`[UNKNOWN]`**.
- **Verdict**: Explicit stack size is **`[VERIFIED]`**; runtime default stack size on both fallback paths is **`[UNKNOWN]`**.

### 3.8 The `r2` Stack Alignment `[UNKNOWN]`
- **Audit of Read Routines**:
  - `CreateTask` (`0xFCEF3488..0xFCEF34F9`): Static audit confirms zero bitwise masking instructions (`bic`, `and`) or alignment tests applied to `r2` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `alloc_task_stack_tcb` (`0xBFE10B88..0xBFE10C26` / ROM `0xFCEEF5D4..0xFCEEF672`): Static audit confirms zero alignment masking instructions applied to `r3` before storing into `desc + 16` `[VERIFIED: PORT29-ROM-N3]`.
  - `alloc_task` (`0xBFE11746` / ROM `0xFCEF0180..0xFCEF037F`): Static audit of all 512 bytes confirms zero alignment masking instructions applied to `r1` (loaded from `desc + 16` at `0xFCEF01DE` and `0xFCEF0202`) before invoking dynamic allocator `0xBFE11E62` (`0xFCEF01E0`) or stack framing helper `0xBFE11E04` (`0xFCEF0204`), and zero alignment masking applied before storing size into `[TCB + 0x20]` at `0xFCEF0248` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
- **Downstream Allocator & Framing Routines**:
  - The actual memory buffer allocation is performed by `0xBFE11E62` (`ROM 0xFCEF08AE`), and stack frame setup is performed by `0xBFE11E04` (`ROM 0xFCEF0850`).
  - Both routines lie outside authorized read slices. Whether dynamic allocator `0xBFE11E62` or framing helper `0xBFE11E04` enforces 4-byte or 8-byte stack pointer alignment (AAPCS compliance) cannot be verified from read slices.
- **Verdict**: **`[UNKNOWN]`**. Absence of alignment masking in `CreateTask`, `alloc_task_stack_tcb`, and `0xBFE11746` is `[VERIFIED]`; downstream buffer alignment enforced by allocator `0xBFE11E62` and framing routine `0xBFE11E04` remains `[UNKNOWN]`.

### 3.9 Additional PORT-29 UNKNOWN Items
- **Item 2: `CreateTask` Literal Pool Entry (`0xFCEF36A0`)**:
  - Range `PORT30-ROM-CREATETASK-LIT` (`0xFCEF36A0..0xFCEF36A3`, 4 B, SHA-256 `4a9f5cbccf8b59d7df28cb6af0bd9d7373f1209b30fcfe86786a37ab7f88e1a2`) contains 32-bit literal pointer **`0x000081CC`** (`0xCC 0x81 0x00 0x00`).
  - Status: **`[VERIFIED]`**.
- **Item 5: Reconciled `SleepTask` Body (`0xFCEF33A0..0xFCEF33DF`)**:
  - Range `PORT30-ROM-SLEEPTASK` (`0xFCEF33A0..0xFCEF33DF`, 64 B, SHA-256 `ee0ef02f81b7f50a81c60d40a752542ff09be03a185eb3d5d69119c4cf0f3c61`).
  - Entry point is `0xFCEF33B4` (VMA `0xBFE14968`): `push {r2, r3, r4, lr}` (`0xB51C`), `mov r4, r0` (`0x4604`), preserving incoming delay argument in `r4`. Preceding bytes `0xFCEF33A0..0xFCEF33B2` are the epilogue of the previous function (`bx lr` at `0xFCEF33B2: 0x4770`) `[VERIFIED]`.
  - Instruction sequence inside read slice:
    - `0xFCEF33B8..0xFCEF33BC`: `ldr r0, [pc, #0xA4]`, `ldr r0, [r0]`, `cmp r0, #0` tests kernel state variable.
    - `0xFCEF33BE`: `ble 0xBFE1498C` branches to panic `DebugAssert` (`0xFCEF33C8: bl ...`).
    - `0xFCEF33CC..0xFCEF33D0`: `ldr r0, [pc, #0xA0]`, `ldr r0, [r0]`, `cmp r0, #0` tests second kernel state variable.
    - `0xFCEF33D2`: `ble 0xBFE149A0` branches to panic `DebugAssert` (`0xFCEF33DC: bl ...`).
  - The authorized 64-byte slice ends at `0xFCEF33DF`, which is still inside these initial precondition checks. It does not contain the timer programming, delay calculation, tick conversion, or sleep dispatch logic.
  - Status: Routine entry and argument preservation in `r4` are **`[VERIFIED]`**; delay units and millisecond tick scaling remain **`[UNKNOWN]`** (requires reading beyond `0xFCEF33DF`).
- **Item 7: Downstream Activation Callee 1: TCB Lookup (`0xFCEF007E`)**:
  - Range `PORT30-ROM-ACTIVATE-CALLEE1` (`0xFCEF0070..0xFCEF00EF`, 128 B, SHA-256 `efb95b96c288b0cb1e153cfba32a660e2dd2bdeac20223bb22eb4a3722cbc7ac`).
  - Target `0xFCEF007E` (VMA `0xBFE11632`): takes task ID in `r0`, validates index range, indexes TCB table, checks handle matching (`cmp r2, r1` at `0xFCEF00AC`), and returns TCB pointer in `r0` (or 0 if invalid).
  - Confirmed: routine does **not** read or consume any descriptor parameters (`r0` name, `r1` priority, `r2` stack size, `sp[0]` context).
  - Status: **`[VERIFIED]`**.
- **Item 8: Downstream Activation Callee 2: Task Enqueue (`0xFCEEF438`)**:
  - Range `PORT30-ROM-ACTIVATE-CALLEE2` (`0xFCEEF430..0xFCEEF4AF`, 128 B, SHA-256 `0c2fee6daa607075ee78299c3b6005bd021bb46b32a08e9e3f9d8ef38147d386`).
  - Target `0xFCEEF438` (VMA `0xBFE109EC`): takes TCB in `r0` and activation flag in `r1`. Reads task priority `[TCB + 0x8]` (`0xFCEEF458: ldr r0, [r5, #0x8]`) and enqueues TCB into the priority-ordered ready queue (`0xFCEEF464: bl 0xBFE126C4`).
  - Confirmed: routine reads only priority `[TCB + 0x8]`; it does **not** read `sp[0]` context (`[TCB + 0x10]`), stack size (`[TCB + 0x20]`), or task name (`[TCB + 0x24]`).
  - Status: **`[VERIFIED]`**.

---

## 4. Listed Ranges Not Read (Section c)

In accordance with strict ROM read policy ("If a listed range is unclear, has no exact start and length, or exceeds 4 KiB, do not read it. Record it as UNKNOWN in the doc, giving the reason"):

| Listed Item | Proposed / Nominal Range | Span | Reason Not Read & Epistemic Justification |
|---|:---:|:---:|---|
| **Runtime Writer for `0x000081D0`** (Row 3 extra evidence) | `UNKNOWN-location` in ROM | Unbounded | The PORT-29 remaining-UNKNOWN list explicitly notes: *"Because no bounded range ($\le 4\text{ KiB}$) is currently known for such writers, this extra writer evidence is marked UNKNOWN-location."* No bounded ROM address is evidenced in any committed doc. |
| **Runtime Writer for `0x0000811C`** (Row 4 extra evidence) | `UNKNOWN-location` in ROM | Unbounded | The PORT-29 remaining-UNKNOWN list explicitly notes: *"No committed doc gives evidence for a writer location of 0x811C; UNKNOWN: writer of 0x811C not localised; requires owner-authorised bounded search in a future milestone."* No bounded ROM address is evidenced. |
| **Downstream Dispatcher / Context-Switch Code** (Row 6 extra evidence) | Downstream from `0xBFE11746` | Unbounded | The PORT-29 remaining-UNKNOWN list notes: *"Any address further downstream (such as a separate scheduler or context-switch dispatcher) remains UNKNOWN until this initial consumer window is read."* |
| **Relocated Core Non-Heap RAM Users** (PORT-29 §2 Item 8) | `0x003489B4` (RAM) / `0xFC000000` (ROM) | 130,252 B RAM / 32 MiB ROM | Exceeds 4 KiB limit; bounds unclear; lacks a bounded ROM address. |

---

## 5. Synthesis & Comparison with PORT-29 Baseline

```
========================================================================================================
CreateTask Calling Convention & Task Stack Parameter Resolution (PORT-29 vs PORT-30):
--------------------------------------------------------------------------------------------------------
Parameter / Property     PORT-29 Baseline Status      PORT-30 Result & Exact Citation
--------------------------------------------------------------------------------------------------------
r0 (Task Name Pointer)   [INFERRED]                   [VERIFIED] Loaded from desc+20 and stored to
                                                      [TCB, #0x24] at 0xFCEF0272..0xFCEF0274; literal
                                                      pool 0xFCEF36A0 = 0x000081CC verified.
r1 (Scheduling Priority) [INFERRED]                   [VERIFIED] Range check (1 <= r1 <= 32); stored
                                                      to [TCB, #0x8] and [TCB, #0x46] at 0xFCEF022E..
                                                      0xFCEF0234; consumed by scheduler at 0xFCEEF458.
r2 (Task Stack Size)     [INFERRED]                   [VERIFIED] Forwarded as r1 to dynamic allocator
                                                      0xBFE11E62 at 0xFCEF01DE..0xFCEF01E0 and framing
                                                      routine 0xBFE11E04 at 0xFCEF0202..0xFCEF0204;
                                                      stored to [TCB, #0x20] at 0xFCEF0246..0xFCEF0248.
r3 (Task Entry Point)    [INFERRED]                   [VERIFIED] Check r3 != 0; stored to [TCB, #0xC]
                                                      at 0xFCEF023C..0xFCEF023E.
sp[0] (Context Storage)  [INFERRED]                   [VERIFIED] Loaded from caller stack [sp, #0x28];
                                                      stored to [TCB, #0x10] at 0xFCEF0240..0xFCEF0244.
sp[0] (Task Delivery)    [UNKNOWN]                    [UNKNOWN] No dispatcher/scheduler read proving
                                                      delivery of [TCB + 0x10] to spawned task entry.
Stack Allocator Identity [INFERRED]                   [UNKNOWN] desc+12 is hardcoded to 0; 0xBFE11746
                                                      delegates dynamic allocation to 0xBFE11E62
                                                      (ROM 0xFCEF08AE); internal allocator unread.
Stack Size (Explicit)    [VERIFIED]                   [VERIFIED] Preserved and passed to allocator.
Stack Size (Default)     [UNKNOWN]                    [UNKNOWN] ROM initializers at 0xFCE91228 (81D0)
                                                      and 0xFCE91174 (811C) verified as 0x00000000;
                                                      runtime values depend on unlocalised writers.
Stack Alignment          [UNKNOWN]                    [UNKNOWN] No alignment masking in CreateTask,
                                                      alloc_task_stack_tcb, or 0xBFE11746; alignment
                                                      enforced downstream by 0xBFE11E62/0xBFE11E04 unread.
SleepTask Tick Scaling   [UNKNOWN]                    [UNKNOWN] Range ends at 0xFCEF33DF inside
                                                      precondition checks; tick scaling unread.
========================================================================================================
```

---

## 6. Final GO/NO-GO Verdict & Narrower UNKNOWN List (Section d)

### 6.1 Verdict: NO-GO

Under the strict project decision rule mandated by the task specification:
> *"The verdict is GO only if the r0, r1, r2 and sp[0] roles and the r2 stack allocation (allocator, size, alignment) are ALL VERIFIED. Otherwise it is NO-GO with an exact, narrower UNKNOWN list (each item with the bounded range that would resolve it, if known)."*

> [!WARNING]
> **Final Verdict for PORT-30 T1**: **`NO-GO`**
>
> While incoming parameter extraction for `r0` (name string pointer), `r1` (scheduling priority), `r2` (stack size in bytes), and `sp[0]` (storage into `[TCB + 0x10]`), as well as task entry point `r3`, are certified as **`[VERIFIED]`**, the remaining elements required for GO are not fully verified:
> 1. **Stack Allocator Internal Identity & Alignment**: `CreateTask` callers unconditionally pass `desc + 12 == 0`, causing `0xBFE11746` to fall through `cbnz r6` (`0xFCEF01DC`) and invoke dynamic allocator `0xBFE11E62` (`ROM 0xFCEF08AE`). However, routine `0xBFE11E62` and downstream framing helper `0xBFE11E04` (`ROM 0xFCEF0850`) lie outside the read slices. Their heap mechanism, allocation pool, and buffer alignment enforcement (4-byte vs 8-byte) remain **`[UNKNOWN]`**.
> 2. **Runtime Default Stack Size**: The ROM initializers for both fallback paths (`*(0x000081D0)` and `*(0x0000811C)`) were read and verified as `0x00000000` (zero). Their runtime values depend on initialization writers whose ROM locations are unevidenced and remain **`[UNKNOWN]`**.
> 3. **Task-Argument Delivery to Spawned Task**: Storage of `sp[0]` into `[TCB + 0x10]` is verified, but no execution-time dispatcher or context-switch consumer has been read delivering that value to the spawned task function, leaving delivery **`[UNKNOWN]`**.
> 4. **`SleepTask` Tick Scaling**: Read slice `0xFCEF33A0..0xFCEF33DF` ends inside precondition checks, leaving delay units and millisecond tick scaling **`[UNKNOWN]`**.
>
> Under the fail-closed project gate rule, these remaining UNKNOWNs compel an explicit **`NO-GO`** verdict.

### 6.2 Exact Narrower UNKNOWN List & Bounded Proposals ($\le 4\text{ KiB}$)

The remaining uncertainties are now narrowed to the following concrete items:

| # | Item | Target Routine / Variable | Target VMA | Proposed ROM Range | Slice Size | Technical Objective & Justification |
|:---:|:---:|---|:---:|:---:|:---:|---|
| **1** | **(b)** | Dynamic Stack Allocator Callee Entry (`0xBFE11E62`) | `0xBFE11E62` (ATCM Thumb-2) | `0xFCEF0880..0xFCEF097F` | 256 B | Invoked by `0xBFE11746` at `0xFCEF01E0` (`bl 0xBFE11E62`) with `r1 = stack_size` when `desc + 12 == 0`. Mapped via Copy Loop 1 formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11E62} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF08AE}}$ (entry veneer at `0xFCEF089C..0xFCEF08AF`). Reading this 256-byte slice ($\le 4\text{ KiB}$) inspects the dynamic allocator entry, verifies how `stack_size` is handled, and determines whether buffer alignment is enforced or delegated to a secondary sub-allocator (e.g. `0xFCEF2F7A` / `0xBFE1452E`). Note: bounds of any downstream sub-allocator body remain UNKNOWN until this entry is inspected. |
| **2** | **(b)** | Task Stack Frame Setup & Initialization Routine (`0xBFE11E04`) | `0xBFE11E04` (ATCM Thumb-2) | `0xFCEF0850..0xFCEF088F` | 64 B | Invoked by `0xBFE11746` at `0xFCEF0204` (`bl 0xBFE11E04`) with `r0 = stack_buffer` (returned from `0xBFE11E62`) and `r1 = stack_size`. Mapped via formula $\text{ROM} = 0\text{xFCEEF24C} + (0\text{xBFE11E04} - 0\text{xBFE10800}) = \mathbf{0\text{xFCEF0850}}$. Reading this bounded 64-byte slice inspects initial stack framing, verifying whether the initial stack pointer is adjusted or aligned (4-byte vs 8-byte) within the allocated buffer. |
| **3** | **(b)** | Task Dispatcher / Context Delivery Consumer (`sp[0]` Delivery) | Downstream scheduler / dispatcher | `UNKNOWN-location` | Unbounded | Storage into `[TCB + 0x10]` is verified, but downstream task dispatcher that activates the task and proves delivery of `[TCB + 0x10]` to `r0` at task entry point is not localized in read slices. Requires an owner-authorized bounded search. |
| **4** | **(b)** | Runtime Writer for Primary Default Stack Size (`*(0x000081D0)`) | `0x000081D0` (Low RAM destination) | `UNKNOWN-location` | Unbounded | ROM initializer at `0xFCE91228` is verified as `0x00000000`. Resolving the runtime default stack size requires locating the routine that stores the default stack size into `0x000081D0` during kernel startup. Unevidenced in committed documentation; requires an owner-authorized bounded search in a future milestone. |
| **5** | **(b)** | Runtime Writer for Secondary Default Stack Size (`*(0x0000811C)`) | `0x0000811C` (Low RAM destination) | `UNKNOWN-location` | Unbounded | ROM initializer at `0xFCE91174` is verified as `0x00000000`. Resolving the secondary default stack size requires locating the routine that stores into `0x0000811C`. Unevidenced in committed documentation; requires an owner-authorized bounded search in a future milestone. |
| **6** | **(d)** | `SleepTask` Delay Units & Millisecond Tick Scaling Body | `0xBFE14994` (ATCM Thumb-2) | `0xFCEF33E0..0xFCEF345F` | 128 B | Continuation of `SleepTask` (`0xBFE14968`) immediately following slice `0xFCEF33A0..0xFCEF33DF`. Reading this 128-byte slice inspects the routine body beyond initial precondition checks, verifying delay calculation, tick conversion formula, and timer dispatch. |

---

## 7. Acceptance Criteria Verification Checklist

- [x] **`docs/PORT30_CREATETASK_CLOSE.md` exists and has a range table with start, length, SHA-256 and new/re-cited status for every range read, plus the total of new bytes**: Confirmed in §2.
- [x] **Every range read is listed (with an exact start and length) in the PORT-29 remaining-UNKNOWN list in `docs/PORT29_CREATETASK_EVIDENCE.md` or `docs/HANDOFF.md` PORT-29 section. No range exceeds 4096 bytes, total new bytes are at most 8192, and no PORT-29 manifest range is widened**: Confirmed. Exactly 7 new ranges read (900 bytes total, well under 8,192 byte limit); all 7 new ranges trace to exact rows in `docs/PORT29_CREATETASK_EVIDENCE.md` §6.2 and `docs/HANDOFF.md:2421-2430`; all 6 PORT-29 ranges re-cited with identical bounds and SHA-256 digests; max individual range size is 516 B ($\le 4,096$ B).
- [x] **Listed ranges that were unclear, had no exact bounds or exceeded 4 KiB are recorded as UNKNOWN with a reason and were not read**: Confirmed in §4 (writers of `0x81D0` and `0x811C` marked `UNKNOWN-location`; downstream dispatcher marked `UNKNOWN-location`; RAM users item marked unread due to >4 KiB size and unbounded ROM location).
- [x] **The PORT-30 manifest and trusted-scopes files exist, and `python3 -B tools/port11c_evidence_validator.py` on them reports VALID with 0 errors. The command and output are quoted in the doc**: Confirmed in §1.2.
- [x] **Each PORT-29 UNKNOWN item (`r0`, `r1`, `r2`, `sp[0]` roles; `r2` stack allocator, size, alignment; any others listed) has a VERIFIED/INFERRED/UNKNOWN label with an exact address plus instruction words or disassembly reasoning**: Confirmed in §3.1–§3.9.
- [x] **The doc ends with an explicit GO or NO-GO verdict. GO only if all of the `r0`/`r1`/`r2`/`sp[0]` roles and the `r2` stack allocator/size/alignment are VERIFIED. On NO-GO, an exact narrower UNKNOWN list is given**: Confirmed in §6.1 (`NO-GO`) and §6.2 (narrower UNKNOWN list covering dynamic allocator callee `0xBFE11E62`, framing routine `0xBFE11E04`, dispatcher gap, unlocalised default stack size writers, and `SleepTask` tick scaling).
- [x] **No ROM bytes, binaries or build outputs are committed, and no files outside the allowed paths are changed**: Confirmed. Only allowed files modified/created.
