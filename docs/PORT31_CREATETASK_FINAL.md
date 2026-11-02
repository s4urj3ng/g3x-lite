# PORT-31 T1: Final Bounded CreateTask Evidence Read, Manifest & GO/NO-GO Verdict

## 1. Table of Every PORT-30 Remaining-UNKNOWN Item

The table below catalogs every item from the PORT-30 remaining-UNKNOWN list ([`docs/PORT30_CREATETASK_CLOSE.md:323-336`](PORT30_CREATETASK_CLOSE.md#62-exact-narrower-unknown-list--bounded-proposals-le-4text-kib) §6.2 and [`docs/HANDOFF.md:2506-2519`](HANDOFF.md#port-30-createtask-line-narrower-unknown-list)), its listed range (start and length), read status (`READ`, `RE-CITED`, or `SKIPPED` plus the reason), and the running total of newly read bytes.

| # | Item Description | Listed ROM Range | Listed Start | Listed Length | Status (READ / RE-CITED with source / SKIPPED with reason) | New Bytes Running Total |
|:---:|---|:---:|:---:|:---:|---|:---:|
| **1** | Dynamic Stack Allocator Callee Entry (`0xBFE11E62`) | `0xFCEF0880..0xFCEF097F` | `0xFCEF0880` | 256 B | **`READ`** (Encompassed within contiguous 304-byte slice `PORT31-ROM-STACK-CALLEES` `0xFCEF0850..0xFCEF097F`, which spans Items 1–3) | 304 B |
| **2** | Task Stack Frame Setup & Watermark Routine (`0xBFE11E04`) | `0xFCEF0850..0xFCEF088F` | `0xFCEF0850` | 64 B | **`READ`** (Encompassed within contiguous 304-byte slice `PORT31-ROM-STACK-CALLEES` `0xFCEF0850..0xFCEF097F`, which spans Items 1–3) | 304 B |
| **3** | `r2` Units/Semantics inside `0xFCEF08AE` / `0xFCEF0850` | `0xFCEF0850..0xFCEF097F` (spanned by items 1 & 2) | `0xFCEF0850` | 304 B | **`READ`** (`PORT31-ROM-STACK-CALLEES`, `0xFCEF0850..0xFCEF097F`, 304 B; SHA-256 `bca315b0b8b89f7bf2b82cd6847a0b45f640e5bd7bc041122021927359929f49`) | 304 B |
| **4** | Task Name String Consumer / TCB Layout (`r0` Name Semantics) | `range not yet identified` | Unbounded | Unbounded | **`SKIPPED`** (Unclear / no exact bounds; range not identified in any committed doc; item marked `UNKNOWN`) | 304 B |
| **5** | Task Dispatcher / Context Delivery Consumer (`sp[0]` Delivery) | `UNKNOWN-location` | Unbounded | Unbounded | **`SKIPPED`** (Unclear / no exact bounds; UNKNOWN-location; item marked `UNKNOWN`) | 304 B |
| **6** | Runtime Writer for Primary Default Stack Size (`*(0x000081D0)`) | `UNKNOWN-location` | Unbounded | Unbounded | **`SKIPPED`** (Unclear / no exact bounds; UNKNOWN-location; item marked `UNKNOWN`) | 304 B |
| **7** | Runtime Writer for Secondary Default Stack Size (`*(0x0000811C)`) | `UNKNOWN-location` | Unbounded | Unbounded | **`SKIPPED`** (Unclear / no exact bounds; UNKNOWN-location; item marked `UNKNOWN`) | 304 B |
| **8** | `SleepTask` Delay Units & Millisecond Tick Scaling Body | `0xFCEF33E0..0xFCEF345F` | `0xFCEF33E0` | 128 B | **`READ`** (`PORT31-ROM-SLEEPTASK-BODY`, `0xFCEF33E0..0xFCEF345F`, 128 B; SHA-256 `14f91ff60242c5d91e70bfe9ee0964c88f69a46909c6af124842c7f037a6e6c1`) | **432 B** |

- **Total New Bytes Read in PORT-31**: **432 bytes** ($\le 8,192\text{ bytes}$ limit).
- **Total Combined Bytes Declared in Manifest**: **3,050 bytes** ($\le 4,096\text{ bytes}$ scope budget).
- **Widened Ranges**: **None** (zero PORT-29/PORT-30 ranges widened; all 13 prior entries re-cited exactly).
- **Out-of-Bounds Reads or Scans**: **None** (zero sweeps, caller scans, or unlisted range reads).

---

### Metadata & Session Context
- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-31 T1 (`p31-t1-createtask-final-evidence`)
- **Primary Source**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (offline host analysis; 33,554,432 bytes; base `0xFC000000`) `[VERIFIED]`
- **Baseline Context**: [`docs/PORT30_CREATETASK_CLOSE.md:323-336`](PORT30_CREATETASK_CLOSE.md#62-exact-narrower-unknown-list--bounded-proposals-le-4text-kib) (§6.2 Remaining UNKNOWN List), [`docs/HANDOFF.md:2506-2519`](HANDOFF.md#port-30-createtask-line-narrower-unknown-list), [`evidence/port30_manifest.json`](../evidence/port30_manifest.json), [`evidence/port30_trusted_scopes.json`](../evidence/port30_trusted_scopes.json), [`AGENTS.md`](../AGENTS.md), [`docs/SAFETY.md`](SAFETY.md)
- **Output Artifacts**:
  - [`docs/PORT31_CREATETASK_FINAL.md`](PORT31_CREATETASK_FINAL.md)
  - [`evidence/port31_manifest.json`](../evidence/port31_manifest.json)
  - [`evidence/port31_trusted_scopes.json`](../evidence/port31_trusted_scopes.json)
  - [`docs/HANDOFF.md`](HANDOFF.md)
- **Verdict Summary**: **`NO-GO`** (Item (b) / resident candidate gate closed: `r1` priority role, `r2` forwarding/TCB storage, `r2` parameter role as byte count, `r0` forwarding/fallback/storage, `r3` entry point, `sp[0]` retrieval/storage, dynamic allocation flag `0x80` in `[TCB + 0x4A]`, and numeric argument forwarding in wrapper `0xBFE11E62` (loading `r0 = 0x000403A4`, `r1 = size`, and tail-calling `0xBFE1452E`) are `[VERIFIED]`; `r0` task name string semantics and interpretation of `0x000403A4` as identifying a heap pool descriptor are `[INFERRED]` (provenance: `HISTORICAL_CHDK`); `sp[0]` task-argument delivery to spawned task entry function, `r2` allocator pool-descriptor layout and callee `0xBFE1452E` internal implementation, `r2` runtime default stack size values, `r2` stack buffer and SP alignment, and `SleepTask` delay units and tick conversion remain `[UNKNOWN]`)

---

## 2. Evidence Manifest Catalog & Validator Verification

The machine-readable evidence manifest [`evidence/port31_manifest.json`](../evidence/port31_manifest.json) catalogs all 15 ranges (13 re-cited, 2 newly read) verified against [`evidence/port31_trusted_scopes.json`](../evidence/port31_trusted_scopes.json):

| Range ID | Target Routine / Subsystem | ROM Start | ROM End | File Offset | Length | Status | SHA-256 Digest |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **PORT29-ROM-N1** | `sub_fc31b408` heap init veneer table | `0xFC31B408` | `0xFC31B507` | `0x0031B408` | 256 B | Re-cited (PORT-29) | `b93e3f48ab31f467e9ee3f4ba907ea3032a3a81cac4fe1ff18a2c0ba138181ce` |
| **PORT30-ROM-INIT-811C** | Secondary default stack size ROM initializer | `0xFCE91170` | `0xFCE9118F` | `0x00E91170` | 32 B | Re-cited (PORT-30) | `66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925` |
| **PORT30-ROM-INIT-81D0** | Primary default stack size ROM initializer | `0xFCE91220` | `0xFCE9123F` | `0x00E91220` | 32 B | Re-cited (PORT-30) | `e63a1b3b97dd2950c54eae572c9e857e6246e251814c11802a9c687f670eaf6c` |
| **PORT30-ROM-ACTIVATE-CALLEE2** | Activation callee 2: task enqueue (`0xFCEEF438`) | `0xFCEEF430` | `0xFCEEF4AF` | `0x00EEF430` | 128 B | Re-cited (PORT-30) | `0c2fee6daa607075ee78299c3b6005bd021bb46b32a08e9e3f9d8ef38147d386` |
| **PORT29-ROM-N3** | `alloc_task_stack_tcb` body (`0xBFE10B88`) | `0xFCEEF5C0` | `0xFCEEF7BF` | `0x00EEF5C0` | 512 B | Re-cited (PORT-29) | `6d5869cf7e64256371fbe1ed693f64125dc0fbccd538ced877cfbb5cfe5fcdd2` |
| **PORT29-ROM-N4** | `activate_task` helper remainder | `0xFCEEF7C0` | `0xFCEEF9C3` | `0x00EEF7C0` | 516 B | Re-cited (PORT-29) | `c4603dc40c67f2f563a0e41efddd4f5ac50fbaf64b5c2272263622b424eedabc` |
| **PORT30-ROM-ACTIVATE-CALLEE1** | Activation callee 1: TCB lookup (`0xFCEF007E`) | `0xFCEF0070` | `0xFCEF00EF` | `0x00EF0070` | 128 B | Re-cited (PORT-30) | `efb95b96c288b0cb1e153cfba32a660e2dd2bdeac20223bb22eb4a3722cbc7ac` |
| **PORT30-ROM-ALLOC-TASK** | Kernel task allocator (`0xBFE11746`) | `0xFCEF0180` | `0xFCEF037F` | `0x00EF0180` | 512 B | Re-cited (PORT-30) | `504cc373cf058c055fa66ae38bd8ad9aa6ccd7c85d31d01e3e33f273692f6405` |
| **PORT31-ROM-STACK-CALLEES** | Task stack watermark (`0xBFE11E04`) & allocator wrapper (`0xBFE11E62`) | `0xFCEF0850` | `0xFCEF097F` | `0x00EF0850` | 304 B | **New (PORT-31)** | `bca315b0b8b89f7bf2b82cd6847a0b45f640e5bd7bc041122021927359929f49` |
| **PORT29-ROM-N5** | `DebugAssert` entry veneer table (`0xBFE13E78`) | `0xFCEF28B0` | `0xFCEF29AF` | `0x00EF28B0` | 256 B | Re-cited (PORT-29) | `93c956e9d994888fc228997a65d0785901a4c23e0921c5e3cf6befa450fb2142` |
| **PORT30-ROM-SLEEPTASK** | Reconciled `SleepTask` precondition checks | `0xFCEF33A0` | `0xFCEF33DF` | `0x00EF33A0` | 64 B | Re-cited (PORT-30) | `ee0ef02f81b7f50a81c60d40a752542ff09be03a185eb3d5d69119c4cf0f3c61` |
| **PORT31-ROM-SLEEPTASK-BODY** | `SleepTask` body, delay units & timer dispatch | `0xFCEF33E0` | `0xFCEF345F` | `0x00EF33E0` | 128 B | **New (PORT-31)** | `14f91ff60242c5d91e70bfe9ee0964c88f69a46909c6af124842c7f037a6e6c1` |
| **PORT29-ROM-CREATETASK** | `CreateTask` body & calling convention | `0xFCEF3488` | `0xFCEF34F9` | `0x00EF3488` | 114 B | Re-cited (PORT-29) | `6d7fbecb5f9589cc34994a63ac6cf7e2def132a7c355a789a29ea3cae8c50ddf` |
| **PORT30-ROM-CREATETASK-LIT** | `CreateTask` literal pool entry (`0xFCEF36A0`) | `0xFCEF36A0` | `0xFCEF36A3` | `0x00EF36A0` | 4 B | Re-cited (PORT-30) | `4a9f5cbccf8b59d7df28cb6af0bd9d7373f1209b30fcfe86786a37ab7f88e1a2` |
| **PORT29-ROM-N6** | ATCM interrupt disable & restore routines | `0xFCEF3A20` | `0xFCEF3A5F` | `0x00EF3A20` | 64 B | Re-cited (PORT-29) | `3bf663507211b96500c59647e3f065cff96d111421ee5a2c867c022536c45969` |

### 2.1 Evidence Validator Execution & Output
The machine-readable evidence manifest was verified using `tools/port11c_evidence_validator.py` with zero extra flags:

```bash
python3 -B tools/port11c_evidence_validator.py --manifest evidence/port31_manifest.json --trusted-scopes evidence/port31_trusted_scopes.json
```

**Exact Quoted Validator Output**:
```text
Evidence Manifest Validation: 15 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED
----------------------------------------------------------------------
----------------------------------------------------------------------
Result: VALID (0 errors, 0 warnings)
```

---

## 3. Evaluation of Each CreateTask Item (Sections 3.1–3.8)

This section evaluates the seven required items: the roles of `r0`, `r1`, `r2`, and `sp[0]`, followed by the `r2` stack allocator, size, and alignment, concluding with the evaluated `SleepTask` body item. All ARM Thumb and Thumb-2 instructions cite explicit 16-bit halfwords in `0xHHHH` notation.

### 3.1 Role of `r0` (Task Name Pointer)
- **Label**:
  - Argument forwarding, fallback when `r0 == 0`, and storage into `[TCB + 0x24]`: **`[VERIFIED]`**.
  - Semantic role of `r0` as a null-terminated C string task name: **`[INFERRED]`** (provenance: `HISTORICAL_CHDK`).
- **Citations & Step-by-Step Disassembly Reasoning**:
  - `0xFCEF348C` (`0x4604`): `mov r4, r0` preserves incoming `r0` parameter `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34AC` (`0xB904`): `cbnz r4, 0xbfe14a64` checks if caller passed non-zero pointer `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34AA` (`0x497D`): `ldr r1, [pc, #0x1f4]` loads literal pointer from $\text{Align}(0\text{xFCEF34AA}+4, 4) + 0\text{x1F4} = \mathbf{0\text{xFCEF36A0}}$, which contains literal `0x000081CC` `[VERIFIED: PORT30-ROM-CREATETASK-LIT]`.
  - `0xFCEF34AE` (`0x680C`): `ldr r4, [r1]` executes if `r0 == 0`, loading default pointer `*(0x000081CC)` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF640` (`0xA801`): `add r0, sp, #4` computes descriptor base pointer `desc = sp + 4` in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEEF642` (`0xF8CD 0x8018`): `str.w r8, [sp, #24]` stores resolved `r0` (preserved in `r8`) into descriptor offset `desc + 20` (`sp + 24`) `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF0272` (`0x6968`): `ldr r0, [r5, #0x14]` loads `[desc + 20]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0274` (`0x6260`): `str r0, [r4, #0x24]` stores the 32-bit value directly into `[TCB + 0x24]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
- **Epistemic Justification for `[INFERRED]`**:
  - The cited ROM instructions treat `r0` purely as an opaque 32-bit word, copying it from `desc + 20` into `[TCB + 0x24]`.
  - The stock startup call site at `0xFC05B98E` (`docs/PORT27_RESIDENT_EVIDENCE.md:268, 278`) passes a pointer to the ASCII string `"Startup\0"` in `r0`.
  - However, no consumer routine that reads `[TCB + 0x24]` as a null-terminated C string (e.g. logging, `DebugAssert`, task list formatting) was read in ROM (Row 4 was SKIPPED due to lack of an identified bounded range). Therefore, treating `r0` semantically as a string pointer remains `[INFERRED]` (provenance: `HISTORICAL_CHDK` and stock call-site data) and cannot be certified as `[VERIFIED]`.

### 3.2 Role of `r1` (Task Scheduling Priority)
- **Label**: **`[VERIFIED]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - `0xFCEF3490` (`0x460E`): `mov r6, r1` preserves incoming `r1` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B0` (`0x1E70`): `subs r0, r6, #1` decrements by 1 `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B2` (`0x2820`): `cmp r0, #0x20` compares `r1 - 1` against 32 `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34B4` (`0xD200`): `bhs 0xbfe14a6c` branches to panic handler if $r1 < 1$ or $r1 > 32$, strictly enforcing $1 \le r1 \le 32$ `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF638` (`0xF88D 0x401D`): `strb.w r4, [sp, #29]` stores validated priority byte into descriptor offset `desc + 25` (`sp + 29`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF022E` (`0x7E68`): `ldrb r0, [r5, #0x19]` loads `[desc + 25]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0230` (`0x60A0`): `str r0, [r4, #0x8]` stores priority into `[TCB + 0x8]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0234` (`0xF8A4 0x0046`): `strh.w r0, [r4, #0x46]` stores priority halfword into `[TCB + 0x46]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEEF458` (`0x68A8`): `ldr r0, [r5, #0x8]` reads `[TCB + 0x8]` in activation callee `0xBFE109EC` (`PORT30-ROM-ACTIVATE-CALLEE2`), using it to index the scheduling ready-queue array before enqueuing via `0xFCEEF464: bl 0xBFE126C4` `[VERIFIED]`.
- **Conclusion**: The parameter role of `r1` as task scheduling priority ($1 \le r1 \le 32$) is verified from range check, storage, and consumption by the ready-queue scheduler.

### 3.3 Role of `r2` (Task Stack Size)
- **Label**:
  - Argument forwarding, fallback when `r2 == 0`, and storage into `[TCB + 0x20]`: **`[VERIFIED]`**.
  - Parameter role as stack size in bytes: **`[VERIFIED]`**.
  - Callee units and arithmetic handling inside `0xBFE11E04` and `0xBFE11E62`: **`[VERIFIED]`**.
  - Runtime default stack size values on fallback paths: **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - `0xFCEF3492` (`0x4615`): `mov r5, r2` preserves incoming `r2` parameter `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34C8` (`0xB905`): `cbnz r5, 0xbfe14a80` preserves caller's explicit value if `r2 != 0` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34CA` (`0x684D`): `ldr r5, [r1, #4]` loads primary default `*(0x000081D0)` if `r2 == 0` `[VERIFIED: PORT29-ROM-CREATETASK, PORT30-ROM-CREATETASK-LIT]`.
  - `0xFCEEF5E4` (`0x681B`): `ldr r3, [r3]` loads secondary fallback `*(0x0000811C)` in `alloc_task_stack_tcb` if primary fallback yields zero `[VERIFIED: PORT29-ROM-N3, PORT29-ROM-N4]`.
  - `0xFCEEF624` (`0xC00E`): `stmia r0!, {r1, r2, r3}` writes resolved stack size into descriptor offset `desc + 16` (`sp + 20`) `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF01DE` (`0x6929`): `ldr r1, [r5, #0x10]` loads `[desc + 16]` in `0xBFE11746`, passing it in `r1` to dynamic allocator wrapper `0xBFE11E62` (`0xFCEF01E0: bl 0xBFE11E62`) `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0202` (`0x6929`): `ldr r1, [r5, #0x10]` loads `[desc + 16]`, passing it in `r1` to watermark fill routine `0xBFE11E04` (`0xFCEF0204: bl 0xBFE11E04`) `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xFCEF0246` (`0x6928`): `ldr r0, [r5, #0x10]` loads `[desc + 16]` and `0xFCEF0248` (`0x6220`: `str r0, [r4, #0x20]`) stores it directly into `[TCB + 0x20]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - **Newly Read Range `PORT31-ROM-STACK-CALLEES` (`0xFCEF0850..0xFCEF097F`) Resolution**:
    - **Routine `0xBFE11E04` (`ROM 0xFCEF0850`)**:
      - `0xFCEF0850` (`0x4A08`): `ldr r2, [pc, #32]` loads 32-bit watermark literal `0x19980218` from `0xFCEF0874` (`0xBFE11E28`) `[VERIFIED]`.
      - `0xFCEF0852` (`0x0889`): `lsrs r1, r1, #2` shifts the requested size right by 2 bits ($r1 = \text{stack\_size} / 4$) `[VERIFIED]`. This directly proves that `r1` represents a **byte count**, which is converted into a 32-bit word count.
      - `0xFCEF0854` (`0xE000`): `b 0xBFE11E0C` branches to loop termination check `[VERIFIED]`.
      - `0xFCEF0856` (`0xC004`): `stmia r0!, {r2}` writes canary word `0x19980218` into `[r0]`, incrementing buffer pointer `r0` by 4 `[VERIFIED]`.
      - `0xFCEF0858` (`0x1E49`): `subs r1, r1, #1` decrements word counter `[VERIFIED]`.
      - `0xFCEF085A` (`0xD2FC`): `bcs 0xBFE11E0A` loops while $r1 \ge 0$ `[VERIFIED]`.
      - `0xFCEF085C` (`0x4770`): `bx lr` returns `[VERIFIED]`.
    - **Routine `0xBFE11E62` (`ROM 0xFCEF08AE`)**:
      - `0xFCEF08AE` (`0xE7F5`): `b 0xBFE11E50` branches to ROM `0xFCEF089C` `[VERIFIED]`.
      - `0xFCEF089C` (`0x4816`): `ldr r0, [pc, #88]` loads 32-bit constant `0x000403A4` from literal pool at `0xFCEF08F8` `[VERIFIED]`.
      - `0xFCEF089E` (`0xF002 0xBB6C`): `b.w 0xBFE1452E` tail-calls callee `0xBFE1452E` with numeric arguments `r0 = 0x000403A4` and `r1 = stack_size` (byte count, preserved unmodified) `[VERIFIED]`.
      - *Heap pool descriptor interpretation*: The interpretation of `0x000403A4` as identifying a heap pool descriptor is `[INFERRED]` (provenance: `HISTORICAL_CHDK`). The callee body at `0xBFE1452E` was not read, and no descriptor layout was verified in ROM.
- **Conclusion**: `r2` parameter role as stack size in bytes is **`[VERIFIED]`**. Callee arithmetic converting bytes to 32-bit words via `lsrs r1, r1, #2` is **`[VERIFIED]`**. However, runtime values for default stack sizes (`*(0x81D0)` and `*(0x811C)`) remain **`[UNKNOWN]`** because ROM initializers are `0x00000000` and runtime initialization writers were SKIPPED.

### 3.4 Role of `sp[0]` (5th Parameter / Task Context Argument)
- **Label**:
  - Retrieval from caller stack, forwarding through descriptor, and storage into `[TCB + 0x10]`: **`[VERIFIED]`**.
  - Delivery to task entry function by task dispatcher: **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - `0xFCEF3494` (`0xF8DD 0x8028`): `ldr.w r8, [sp, #40]` retrieves caller's 5th parameter passed on stack (`sp_entry + 0x00` after 40-byte prologue push) `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEF34CE` (`0x4641`): `mov r1, r8` forwards `r8` into `r1` for callee `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `0xFCEEF624` (`0xC00E`): `stmia r0!, {r1, r2, r3}` writes incoming `r1` into descriptor offset `desc + 8` (`sp + 12`) in `alloc_task_stack_tcb` `[VERIFIED: PORT29-ROM-N3]`.
  - `0xFCEF0240` (`0x68A8`): `ldr r0, [r5, #0x8]` loads `[desc + 8]` in `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`) `[VERIFIED]`.
  - `0xFCEF0244` (`0x6120`): `str r0, [r4, #0x10]` stores context argument directly into `[TCB + 0x10]` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
- **Epistemic Justification for `[UNKNOWN]`**:
  - Forwarding through descriptor and storage into `[TCB + 0x10]` is verified in ROM.
  - However, the task dispatcher / context-switch code that launches the task and proves that `[TCB + 0x10]` is placed into `r0` (or another register) upon entry to `r3` was not read (Row 5 SKIPPED due to unlocalised ROM address). Therefore, delivery of this context argument to the task entry function remains **`[UNKNOWN]`**.

### 3.5 The `r2` Stack Allocator
- **Label**:
  - Numeric argument forwarding (wrapper `0xBFE11E62` loads `0x000403A4` into `r0`, forwards size in `r1`, and tail-calls `0xBFE1452E`): **`[VERIFIED]`**.
  - Dynamic allocation flag `0x80` recorded in `[TCB + 0x4A]`: **`[VERIFIED]`**.
  - Semantic interpretation of `0x000403A4` as identifying a heap pool descriptor: **`[INFERRED]`** (provenance: `HISTORICAL_CHDK`).
  - Heap pool descriptor layout at `0x000403A4` and internal implementation of allocator callee `0xBFE1452E`: **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - In `alloc_task_stack_tcb` (`0xBFE10B88`), instruction `0xFCEEF61C..0xFCEEF624` writes a hardcoded `0` into descriptor offset `desc + 12` (`sp + 16`) `[VERIFIED: PORT29-ROM-N3]`.
  - In `0xBFE11746` (`PORT30-ROM-ALLOC-TASK`):
    - `0xFCEF01D6` (`0x68EE`): `ldr r6, [r5, #0xC]` loads caller stack buffer pointer `[desc + 12]` into `r6` `[VERIFIED]`.
    - `0xFCEF01DC` (`0xB976`): `cbnz r6, 0xFCEF01FC` tests `r6`. For `CreateTask` callers, `desc + 12` is unconditionally 0 (`r6 == 0`), so branch is not taken and execution falls through to dynamic allocation `[VERIFIED]`.
    - `0xFCEF01DE` (`0x6929`): `ldr r1, [r5, #0x10]` loads stack size byte count `[VERIFIED]`.
    - `0xFCEF01E0` (`0xF000 0xFB65`): `bl 0xBFE11E62` calls allocator wrapper `[VERIFIED]`.
    - `0xFCEF01E4` (`0x0006`): `movs r6, r0` preserves returned buffer pointer `[VERIFIED]`.
    - `0xFCEF01E6` (`0xD105`): `bne 0xFCEF01F4` branches if buffer pointer is non-null; null falls through to assert panic `[VERIFIED]`.
    - `0xFCEF01F4` (`0x2080`): `movs r0, #0x80` `[VERIFIED]`.
    - `0xFCEF01F6` (`0xF884 0x004A`): `strb.w r0, [r4, #0x4A]` records dynamic allocation flag `0x80` in `[TCB + 0x4A]` `[VERIFIED]`.
  - In newly read slice `PORT31-ROM-STACK-CALLEES` (`0xFCEF0850..0xFCEF097F`):
    - `0xFCEF08AE` (`0xE7F5`): `b 0xBFE11E50` branches to ROM `0xFCEF089C` `[VERIFIED]`.
    - `0xFCEF089C` (`0x4816`): `ldr r0, [pc, #88]` loads 32-bit constant `0x000403A4` from literal pool at `0xFCEF08F8` `[VERIFIED]`.
    - `0xFCEF089E` (`0xF002 0xBB6C`): `b.w 0xBFE1452E` tail-calls callee `0xBFE1452E` with numeric arguments `r0 = 0x000403A4` and `r1 = stack_size` (byte count) `[VERIFIED]`.
    - Routine `0xBFE11E04` (`0xFCEF0850`) is confirmed as the stack watermark fill routine (`lsrs r1, r1, #2` / `stmia r0!, {r2}` with canary `0x19980218`), not a memory allocator.
- **Epistemic Justification for `[INFERRED]` and `[UNKNOWN]`**:
  - The cited instructions only prove numeric argument forwarding: wrapper `0xBFE11E62` loads literal `0x000403A4` into `r0`, preserves `stack_size` in `r1`, and tail-calls `0xBFE1452E`, while `alloc_task` records flag `0x80` into `[TCB + 0x4A]`. These mechanics are **`[VERIFIED]`**.
  - However, the cited instructions do NOT show that `0x000403A4` identifies a heap pool descriptor: the callee body at `0xBFE1452E` (ROM `0xFCEF2F7A`) was not read, and no descriptor-layout evidence is cited from verified ROM.
  - The interpretation that `0x000403A4` identifies a heap pool descriptor is **`[INFERRED]`** (provenance: `HISTORICAL_CHDK`, based on historical DryOS conventions where memory allocation routines take a pool descriptor address in `r0`).
  - Furthermore, because callee body `0xBFE1452E` lies outside authorized read slices, the internal heap allocation algorithm, descriptor layout, block headers, and fragmentation behavior remain **`[UNKNOWN]`**.

### 3.6 The `r2` Stack Size
- **Label**:
  - Explicit stack size forwarding and byte-count semantics: **`[VERIFIED]`**.
  - Runtime default stack sizes (`*(0x000081D0)` and `*(0x0000811C)`): **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - **Explicit Stack Size ($r2 \ne 0$)**:
    - Preserved in `r5` (`0xFCEF3492: mov r5, r2`), non-zero bypass (`0xFCEF34C8: cbnz r5`), forwarded through `desc + 16` (`0xFCEEF624: stmia r0!`), passed in `r1` to dynamic heap allocator `0xBFE11E62` (`0xFCEF01DE..0xFCEF01E0`), passed in `r1` to watermark fill routine `0xBFE11E04` (`0xFCEF0202..0xFCEF0204`), and stored into `[TCB + 0x20]` (`0xFCEF0248: str r0, [r4, #0x20]`).
    - Byte-count semantics is verified by `lsrs r1, r1, #2` at `0xFCEF0852` converting bytes to words for watermark filling.
    - Explicit stack size handling is **`[VERIFIED]`**.
  - **Default Stack Size ($r2 == 0$)**:
    - Primary fallback `*(0x000081D0)`: ROM initializer word at `0xFCE91228` holds `0x00000000` `[VERIFIED: PORT30-ROM-INIT-81D0]`.
    - Secondary fallback `*(0x0000811C)`: ROM initializer word at `0xFCE91174` holds `0x00000000` `[VERIFIED: PORT30-ROM-INIT-811C]`.
    - Because ROM initializers are zero, the runtime default stack sizes depend on runtime initialization writers. Those writers were listed as `UNKNOWN-location` (Rows 6 & 7) and were SKIPPED.
    - Runtime default stack size values remain **`[UNKNOWN]`**.

### 3.7 The `r2` Stack Alignment
- **Label**: **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - `CreateTask` (`0xFCEF3488..0xFCEF34F9`): Static audit confirms zero bitwise masking instructions (`bic`, `and`) applied to `r2` `[VERIFIED: PORT29-ROM-CREATETASK]`.
  - `alloc_task_stack_tcb` (`0xFCEEF5D4..0xFCEEF672`): Static audit confirms zero alignment masking instructions applied to requested size in `r3` `[VERIFIED: PORT29-ROM-N3]`.
  - `alloc_task` (`0xFCEF0180..0xFCEF037F`): Static audit confirms covered call-site instructions in `PORT30-ROM-ALLOC-TASK`—including `0xFCEF01E0` (`bl 0xBFE11E62`), `0xFCEF0204` (`bl 0xBFE11E04`), and subsequent task setup call sites `0xFCEF0210..0xFCEF0228` (such as `0xFCEF0220: bl 0xBFE13DDC` / ROM `0xFCEF2794`)—apply zero alignment masking or SP adjustment to size in `r1` or buffer pointer in `r6` `[VERIFIED: PORT30-ROM-ALLOC-TASK]`.
  - `0xBFE11E04` (`0xFCEF0850..0xFCEF0870`): Static audit confirms `lsrs r1, r1, #2` truncates the bottom 2 bits to enforce 4-byte word counting for watermark filling, but applies zero alignment adjustments to buffer pointer `r0` `[VERIFIED: PORT31-ROM-STACK-CALLEES]`.
  - **Separation of Covered Call-Site Instructions vs Unread Callee Bodies**:
    - The call-site instructions at `0xFCEF0210..0xFCEF0228` ARE covered within the re-cited range `PORT30-ROM-ALLOC-TASK` (`0xFCEF0180..0xFCEF037F`). Static audit confirms zero alignment masking instructions in this covered code.
    - However, the external *callee bodies* invoked from `alloc_task`—namely dynamic heap allocator `0xBFE1452E` (ROM `0xFCEF2F7A`) and downstream helper callees invoked from `0xFCEF0210..0xFCEF0228` (such as ROM `0xFCEF2794`)—were NOT read because they lie outside authorized read slices.
- **Epistemic Justification for `[UNKNOWN]`**:
  - Absence of alignment masking in covered instructions (`CreateTask`, `alloc_task_stack_tcb`, `alloc_task`, and `0xBFE11E04`) is verified.
  - However, whether dynamic heap allocator `0xBFE1452E` returns 4-byte or 8-byte aligned memory buffers, and whether downstream context setup callees enforce 8-byte initial stack pointer alignment (AAPCS compliance), cannot be verified without reading those external callee bodies. Therefore, stack alignment remains **`[UNKNOWN]`**.

### 3.8 Additional Evaluated Item: `SleepTask` Delay Units & Dispatch
- **Label**:
  - Routine entry, precondition checks, zero-delay bypass, unchanged delay forwarding (`mov r1, r4`), and timer dispatch call sites (`bl 0xBFE15014` / `0xFCEF3A60` and `bl 0xBFE10DA6` / `0xFCEEF7F2`): **`[VERIFIED]`**.
  - Delay units (milliseconds vs ticks) and any downstream tick conversion inside callee `0xFCEF3A60`: **`[UNKNOWN]`**.
- **Citations & Step-by-Step Disassembly Reasoning**:
  - Reconciled entry at `0xFCEF33B4` (`0xB51C: push {r2, r3, r4, lr}`, `0x4604: mov r4, r0`) preserves incoming delay in `r4` `[VERIFIED: PORT30-ROM-SLEEPTASK]`.
  - Precondition checks skip assertion panics to `0xFCEF33CC` and `0xFCEF33E0` `[VERIFIED: PORT30-ROM-SLEEPTASK]`.
  - In newly read slice `PORT31-ROM-SLEEPTASK-BODY` (`0xFCEF33E0..0xFCEF345F`):
    - `0xFCEF33E0` (`0xB90C`): `cbnz r4, 0xBFE1499A` (`0xFCEF33E6`) checks delay argument `[VERIFIED]`.
    - `0xFCEF33E2` (`0x2000`): `movs r0, #0` sets return value 0 if delay is 0 `[VERIFIED]`.
    - `0xFCEF33E4` (`0xBD1C`): `pop {r2, r3, r4, pc}` returns immediately if delay == 0 `[VERIFIED]`.
    - If delay $\ne 0$:
      - `0xFCEF33E6` (`0x4621`): `mov r1, r4` forwards delay argument directly into `r1` without multiplication, division, or tick-frequency scaling `[VERIFIED]`.
      - `0xFCEF33E8` (`0x4668`): `mov r0, sp` passes stack context buffer pointer in `r0` `[VERIFIED]`.
      - `0xFCEF33EA` (`0xF000 0xFB39`): `bl 0xBFE15014` (ROM `0xFCEF3A60`) invokes timer configuration routine `[VERIFIED]`.
      - `0xFCEF33EE` (`0xF7FC 0xFA00`): `bl 0xBFE10DA6` (ROM `0xFCEEF7F2`) invokes task sleep/yield routine `[VERIFIED]`.
      - `0xFCEF33F2` (`0xE7F6`): `b 0xBFE14996` branches to epilogue (`movs r0, #0`, `pop {r2, r3, r4, pc}`) `[VERIFIED]`.
  - Next function starts at `0xFCEF33F4` (`0x481A: ldr r0, [pc, #104]`, `0xB510: push {r4, lr}`).
- **Epistemic Justification for `[UNKNOWN]`**:
  - The evidence proves only that `SleepTask` forwards its delay parameter unchanged in `r1` (`mov r1, r4`).
  - Delay units (milliseconds vs ticks) and any downstream tick conversion formula are NOT established, because the timer configuration callee `0xBFE15014` at ROM `0xFCEF3A60` was not read (lies outside authorized read slices). Therefore, delay units and tick conversion remain **`[UNKNOWN]`**.

---

## CreateTask line: STOP RECORD

### Formal Closure Statement
> [!IMPORTANT]
> **The `CreateTask` / `G3X_RESIDENT` line is CLOSED for this firmware (PowerShot G3 X GM1.10C) unless the project owner explicitly opens it again.**
>
> Four consecutive research and evidence milestones (PORT-27, PORT-28, PORT-29, PORT-30, and PORT-31) have rigorously investigated stock GM1.10C firmware ROM. While incoming register forwarding and TCB storage are proven (`r0` forwarding/storage `[VERIFIED]`, `r0` task name string semantics `[INFERRED]`, `r1` priority $1 \le r1 \le 32$ `[VERIFIED]`, `r2` stack size in bytes `[VERIFIED]`, `r3` entry function `[VERIFIED]`, `sp[0]` retrieval/storage `[VERIFIED]`, dynamic allocation flag `0x80` in `[TCB + 0x4A]` `[VERIFIED]`, and numeric argument forwarding in wrapper `0xBFE11E62` with `r0 = 0x000403A4` and `r1 = size` `[VERIFIED]`), critical elements including `r0` C-string semantics `[INFERRED]`, `0x000403A4` heap pool descriptor interpretation `[INFERRED]`, `sp[0]` context delivery to the spawned task `[UNKNOWN]`, `r2` allocator pool-descriptor layout and callee `0xBFE1452E` internal implementation `[UNKNOWN]`, runtime default stack sizes `[UNKNOWN]`, stack/SP alignment `[UNKNOWN]`, and `SleepTask` delay units and tick conversion `[UNKNOWN]` cannot be closed within bounded ROM inspection quotas without unconstrained scans or owner-directed trial redesign. No resident candidate (`G3X_RESIDENT=1`) will be constructed.

### Final Exact UNKNOWN List
1. **`r0` Task Name String Semantics**:
   - *Reason it could not be closed*: The cited ROM instructions only store `r0` as an opaque 32-bit word into `[TCB + 0x24]`. Role as a C-string is inferred from the startup caller passing `"Startup\0"`. Proving string semantics requires verifying an established TCB layout or reading a consumer routine that reads `[TCB + 0x24]` as a C string.
   - *Range / evidence needed*: Range not yet identified in committed documentation (unbounded); requires locating and reading a consumer routine (logging, task list, or `DebugAssert` formatter) that reads `[TCB + 0x24]` as a null-terminated string.
2. **`sp[0]` Task-Argument Delivery to Spawned Task**:
   - *Reason it could not be closed*: Storage of `sp[0]` into `[TCB + 0x10]` is verified, but the downstream task dispatcher / context-switch code that restores `[TCB + 0x10]` into `r0` upon task launch is not localised in ROM (`UNKNOWN-location`).
   - *Range / evidence needed*: Unbounded / `UNKNOWN-location`; requires locating and reading the task context switch / dispatcher routine downstream of task scheduling.
3. **`r2` Stack Allocator Internal Implementation**:
   - *Reason it could not be closed*: Callee wrapper `0xBFE11E62` delegates dynamic allocation via tail-call to kernel routine `0xBFE1452E` (ROM `0xFCEF2F7A`), which lies outside authorized read slices.
   - *Range / evidence needed*: Reading kernel heap allocator routine `0xBFE1452E` (ROM `0xFCEF2F7A`, $\le 256$ B).
4. **`r2` Allocator Pool-Descriptor Role (`0x000403A4`)**:
   - *Reason it could not be closed*: Wrapper `0xBFE11E62` loads literal `0x000403A4` into `r0` and tail-calls `0xBFE1452E` with the size in `r1`. However, callee `0xBFE1452E` was not read, and no descriptor-layout evidence was verified in ROM. The interpretation that `0x000403A4` identifies a heap pool descriptor remains `[INFERRED]` (provenance: `HISTORICAL_CHDK`). Proving the pool-descriptor role and layout requires reading the callee and verifying the descriptor structure.
   - *Range / evidence needed*: Reading kernel heap allocator routine `0xBFE1452E` (ROM `0xFCEF2F7A`, $\le 256$ B) and inspecting descriptor memory at RAM `0x000403A4` (or its initialization routine in ROM) to verify whether `0x000403A4` is indeed a heap pool descriptor structure.
5. **`r2` Runtime Default Stack Size**:
   - *Reason it could not be closed*: ROM initializers for `*(0x000081D0)` and `*(0x0000811C)` are `0x00000000`, and runtime initialization writers are unlocalised in ROM (`UNKNOWN-location`).
   - *Range / evidence needed*: Unbounded / `UNKNOWN-location`; requires locating and reading the initialization routines that write default stack sizes into RAM addresses `0x000081D0` and `0x0000811C`.
6. **`r2` Stack Buffer & Initial Stack Pointer Alignment**:
   - *Reason it could not be closed*: Covered call-site instructions in `PORT30-ROM-ALLOC-TASK` (`0xFCEF0180..0xFCEF037F`, including call sites at `0xFCEF01E0`, `0xFCEF0204`, and `0xFCEF0210..0xFCEF0228`) contain no alignment masking or SP adjustment. However, external callee bodies—dynamic heap allocator `0xBFE1452E` (ROM `0xFCEF2F7A`) and downstream helper callees invoked from `0xFCEF0210..0xFCEF0228` (such as ROM `0xFCEF2794`)—were not read because they lie outside authorized read slices.
   - *Range / evidence needed*: Reading kernel heap allocator `0xBFE1452E` (ROM `0xFCEF2F7A`, $\le 256$ B) and downstream callee bodies (e.g. ROM `0xFCEF2794`, which has no exact bounds established in committed docs) to inspect buffer allocation alignment and initial SP framing.
7. **`SleepTask` Delay Units & Downstream Tick Conversion**:
   - *Reason it could not be closed*: The covered instructions in `PORT31-ROM-SLEEPTASK-BODY` (`0xFCEF33E0..0xFCEF345F`) prove only that `SleepTask` forwards its incoming delay argument unchanged (`mov r1, r4`) to timer configuration callee `0xBFE15014` at ROM `0xFCEF3A60`. Delay units (milliseconds vs ticks) and any downstream tick conversion formula are NOT established because callee `0xFCEF3A60` was not read.
   - *Range / evidence needed*: Reading timer configuration callee `0xBFE15014` at ROM `0xFCEF3A60`. The range start is `0xFCEF3A60`, but the routine body has no exact bounds established in committed documentation (length is unlocalised / unbounded without reading the callee epilogue).

---

## Verdict: NO-GO

Under the project decision rule mandated by the task specification:
> *"The document ends with a GO/NO-GO verdict. GO only if all seven items are VERIFIED. If the verdict is NO-GO, add a 'CreateTask line: STOP RECORD' section to docs/PORT31_CREATETASK_FINAL.md."*

> [!WARNING]
> **Final Verdict for PORT-31 T1**: **`NO-GO`**
>
> While incoming parameter forwarding and TCB storage of `r0` (into `[TCB + 0x24]`), parameter extraction, range checking, and ready-queue enqueuing of `r1` (scheduling priority), argument forwarding, TCB storage, and byte-count semantics of `r2` (stack size in bytes), task entry point `r3` (into `[TCB + 0xC]`), argument storage of `sp[0]` (into `[TCB + 0x10]`), dynamic allocation flag `0x80` in `[TCB + 0x4A]`, and numeric argument forwarding in wrapper `0xBFE11E62` (loading `r0 = 0x000403A4`, `r1 = size`, and tail-calling `0xBFE1452E`) are certified as **`[VERIFIED]`**, the required items cannot all be verified:
> 1. **`r0` Task Name String Semantics**: Cited ROM instructions treat `r0` purely as an opaque 32-bit word. That `r0` represents a null-terminated C string is **`[INFERRED]`** (provenance: `HISTORICAL_CHDK` and stock call-site data); no consumer reading `[TCB + 0x24]` as a C string was read in ROM.
> 2. **`sp[0]` Task-Argument Delivery**: Storage into `[TCB + 0x10]` is verified, but downstream task dispatcher delivery of this argument to the task entry function remains **`[UNKNOWN]`**.
> 3. **`r2` Stack Allocator Internal Implementation & Pool-Descriptor Role**: Wrapper `0xBFE11E62` loading numeric constant `0x000403A4` into `r0`, forwarding size in `r1`, and tail-calling `0xBFE1452E` is verified, but the interpretation that `0x000403A4` identifies a heap pool descriptor is **`[INFERRED]`** (provenance: `HISTORICAL_CHDK`); callee `0xBFE1452E` (ROM `0xFCEF2F7A`) was not read and no descriptor layout was verified, so internal heap allocator implementation and descriptor role remain **`[UNKNOWN]`**.
> 4. **`r2` Runtime Default Stack Size**: ROM initializers for `*(0x000081D0)` and `*(0x0000811C)` are `0x00000000` (zero). Runtime default values depend on unlocalised initialization writers and remain **`[UNKNOWN]`**.
> 5. **`r2` Stack Buffer & Initial SP Alignment**: Buffer alignment returned by allocator `0xBFE1452E` and initial stack pointer alignment in downstream context setup remain unverified because the external callee bodies lie outside authorized read slices and remain **`[UNKNOWN]`**.
>
> Additionally, unresolved PORT-30 item **`SleepTask` Delay Units & Downstream Tick Conversion** remains **`[UNKNOWN]`** because timer configuration callee `0xFCEF3A60` was not read.
>
> Under the fail-closed project gate rule, these remaining non-VERIFIED elements compel an explicit **`NO-GO`** verdict.
