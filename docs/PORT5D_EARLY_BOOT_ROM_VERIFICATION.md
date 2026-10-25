# PORT-5D — GM1.10C early boot check-word ROM verification

Date: **2026-10-25 (Asia/Seoul)**. Analyst: Claude Code. Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port4-documentation-consolidation`, HEAD `57968eb` (dirty/untracked work preserved).
Authorisation: owner-approved, read-only inspection of GM1.10C ROM **`0xFC05B558–0xFC05B67F` inclusive** only.

**Verdict: the prototype is CONTRADICTED by ROM.**
- **Check words:** the GM1.10C initial task compares **`[0x80EC]` against `[0x8074] + 0x10`**, not `[0x80F0]`/`[0x8078]`.
- **Strings:** all eight stage-4 string references resolve to addresses **4 bytes lower** than the ones `boot_prototype.c` uses.
- **PORT-5C:** its inference is confirmed.

A source correction is proposed in §7. It has **not** been applied.

## 1. Method and boundary

| Item | Value |
|---|---|
| ROM | `firmware/dumps/GM1.10C/PRIMARY.BIN`, SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` (re-verified) |
| Bytes read | File offsets `0x5B558–0x5B67F` (VMA = offset + `0xFC000000`), **296 bytes**, extracted with `dd` into the session scratchpad. Extract SHA-256 `3266baee803e10a8db949f25994c424e1bb692d0f7e0104e6e6065a82fadcbc2`. |
| Tool | `arm-none-eabi-objdump -D -b binary -m arm -M force-thumb --adjust-vma=0xFC05B558`, on the 296-byte extract only. Literal and string bytes were decoded from the same extract. |
| Not read | Any byte outside the range. Branch and call targets were **not** followed. In particular these were not examined: `sub_fc05b5ea`'s callees, `0xFC05B684`, the init callees, and `0xFC05B962`. |
| Range-edge note | `"extlib_setup"` occupies `0xFC05B674–0xFC05B67F`. Its NUL terminator at `0xFC05B680` is outside the range and **not read**. |
| Classifier | No step was blocked. No IRQ, SD, memory-controller or power-on routine was inspected. |

Classifications:
- **ROM VERIFIED:** read from the 296-byte extract in this session.
- **SOURCE VERIFIED:** read from the cited project or patch text.
- **INFERRED:** follows from the above with a stated premise.
- **UNKNOWN:** not established.

## 2. Comparison operands (Questions 1–3)

| Address | Encoding | Instruction | Effect | Status |
|---|---|---|---|---|
| `0xFC05B560` | `4829` | `ldr r0, [pc, #0xA4]` → literal **`0xFC05B608`** | `r0 = 0x000080EC` | ROM VERIFIED |
| `0xFC05B562` | `6801` | `ldr r1, [r0]` | `r1 = [0x80EC]` | ROM VERIFIED |
| `0xFC05B564` | `4829` | `ldr r0, [pc, #0xA4]` → literal **`0xFC05B60C`** | `r0 = 0x00008074` | ROM VERIFIED |
| `0xFC05B566` | `6800` | `ldr r0, [r0]` | `r0 = [0x8074]` | ROM VERIFIED |
| `0xFC05B568` | `3010` | `adds r0, #16` | `r0 = [0x8074] + 0x10` | ROM VERIFIED |
| `0xFC05B56A` | `4281` | `cmp r1, r0` | | ROM VERIFIED |
| `0xFC05B56C` | `d202` | `bcs 0xFC05B574` | Skip the error when `[0x80EC] ≥ [0x8074] + 0x10` (**unsigned**, HS/CS) | ROM VERIFIED |
| `0xFC05B56E` | `a028` | `adr r0, 0xFC05B610` (`"USER_MEM size checking"`) | Error-path argument | ROM VERIFIED |
| `0xFC05B570` | `f000 f83b` | `bl 0xFC05B5EA` | Error routine | ROM VERIFIED (call); routine semantics UNKNOWN |

Literal-pool bytes: `0xFC05B608: ec 80 00 00` and `0xFC05B60C: 74 80 00 00` (ROM VERIFIED).

PC-relative arithmetic. Thumb `LDR (literal)`: `Align(PC+4, 4) + imm8×4`.
- `0xFC05B560`: `Align(0xFC05B564, 4) = 0xFC05B564`, plus `0x29×4 = 0xA4`, gives `0xFC05B608`. ✓
- `0xFC05B564`: `0xFC05B568 + 0xA4 = 0xFC05B60C`. ✓

**Answer 2: the ROM uses `[0x80EC]` and `[0x8074]`.**
- Condition: proceed if `[0x80EC] ≥ [0x8074] + 16` (unsigned). Otherwise call `sub_fc05b5ea("USER_MEM size checking")` and then continue at `0xFC05B574`, because the `bl` returns into the next instruction.
- Whether `sub_fc05b5ea` returns at all is **UNKNOWN**. Its body (below) ends in a tail branch outside the range.

Rest of the function in range, for completeness (ROM VERIFIED). None of it was traced further:
- TCM fill `0xBFE10000..0xBFE10800` with `0xEEEEEEEE`, using literals `0xFC05B628 = 0xBFE10000` and `0xFC05B62C = 0xBFE10800`.
- Calls `0xFC05C5BC`, `0xFC127B3C`, `0xFC127B4E`, `0xFC418738`, `0xFC05C7D4`, `0xFC05C862`, `0xFC05B794`, `0xFC05B8D8` and `0xFC05E910`, each failure taking the `bge`-guarded error call.
- `pop.w {r4, lr}` and `b.w 0xFC05B962` at `0xFC05B5E2/E6`.

`sub_fc05b5ea` (`0xFC05B5EA–0xFC05B5FF`):
```
mov r1, r0
adr r0, 0xFC05B684        ; outside range, not read
push {r4, lr}
blx 0xFC31BF04
movs r1, #1
pop {r4, lr}
movs r0, #0x40
b.w 0xFC084BA4
```
Targets not followed.

## 3. ADR at 0xFC05B55A (Question 4)

`0xFC05B55A: a429` is `ADR r4, #0xA4` (imm8 `0x29` × 4).
- `Align(0xFC05B55A + 4, 4) = Align(0xFC05B55E, 4) = 0xFC05B55C`.
- `0xFC05B55C + 0xA4 = **0xFC05B600**`.

Bytes at `0xFC05B600`: `2f 5f 74 65 72 6d 00`, which is **`"/_term"`**. **ROM VERIFIED.** This matches the PORT-5C arithmetic exactly.

## 4. Eight string references (Question 5)

| # | Instruction | Calculation | Resolved | Content | Prototype uses | Content at prototype address |
|---|---|---|---|---|---|---|
| 1 | `0xFC05B55A a429` (`r4`, passed to `0xFC05C5BC`, `0xFC05C862`, `0xFC05B794`) | `0xFC05B55C + 0xA4` | **`0xFC05B600`** | `"/_term"` | `0xfc05b604` (C:268) | `"rm"` |
| 2 | `0xFC05B56E a028` | `0xFC05B570 + 0xA0` | **`0xFC05B610`** | `"USER_MEM size checking"` | `0xfc05b614` (C:277) | `"_MEM size checking"` |
| 3 | `0xFC05B592 a027` | `0xFC05B594 + 0x9C` | **`0xFC05B630`** | `"dmSetup"` | `0xfc05b634` (C:292) | `"tup"` |
| 4 | `0xFC05B5A0 a025` | `0xFC05B5A4 + 0x94` | **`0xFC05B638`** | `"termDriverInit"` | `0xfc05b63c` (C:298) | `"DriverInit"` |
| 5 | `0xFC05B5B0 a025` | `0xFC05B5B4 + 0x94` | **`0xFC05B648`** | `"termDeviceCreate"` | `0xfc05b64c` (C:305) | `"DeviceCreate"` |
| 6 | `0xFC05B5C0 a026` | `0xFC05B5C4 + 0x98` | **`0xFC05B65C`** | `"stdioSetup"` | `0xfc05b660` (C:312) | `"oSetup"` |
| 7 | `0xFC05B5CE a026` | `0xFC05B5D0 + 0x98` | **`0xFC05B668`** | `"stdlibSetup"` | `0xfc05b66c` (C:318) | `"ibSetup"` |
| 8 | `0xFC05B5DC a025` | `0xFC05B5E0 + 0x94` | **`0xFC05B674`** | `"extlib_setup"` (12 bytes to the range end; NUL beyond range) | `0xfc05b678` (C:324) | `"ib_setup"` (to range end) |

All eight calculations are **ROM VERIFIED**. Every prototype string address is exactly **+4** from the ROM value.

String #1 matters beyond diagnostics: the ROM passes `r4` (`"/_term"`) as the device name to `0xFC05C862` (termDeviceCreate) and `0xFC05B794` (stdioSetup), and the prototype passes a pointer to `"rm"` instead. **INFERRED** effect: a different device-name string is registered or opened than the one stock firmware uses. This report does not predict runtime behavior; the callees were not examined.

Strings #2–#8 are used only on the error path.

## 5. Comparison with existing documents and source (Question 6)

| Source | Claim | ROM result | Status |
|---|---|---|---|
| `boot_prototype.c` C:268–324 | `"/_term"` @ `0xfc05b604`; check `[0x80F0] ≥ [0x8078]+0x10`; seven error strings at `…614/634/63c/64c/660/66c/678` | ROM: `…600`; `[0x80EC]`/`[0x8074]`; strings at `…610/630/638/648/65c/668/674` | **CONTRADICTED** (10 constants, all +4) |
| `boot_prototype.c` other stage-4 content | Call targets, TCM fill bounds/pattern, `bhs`, tail `b.w sub_fc05b962_my` | Same targets; `0xBFE10000/0xBFE10800`; `0xEEEEEEEE`; HS condition | **Consistent** (ROM VERIFIED) |
| [PORT-5C](PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md) §3 | E-style pair PLAUSIBLE; `"/_term"` = `0xFC05B600`; systematic +4 error PLAUSIBLE | All confirmed | **Confirmed** (upgrade PLAUSIBLE → ROM VERIFIED) |
| [PORT-1C1](CHDK_PORT1C1_CRITICAL_AUDIT.md) §4.1, L177 | `0xFC05B55A: adr r4, #0xa4 @ "/_term"` | Matches the ROM | **Correct** |
| PORT-1C1 L183 / Issue 3 | "All 7 initialization stages … replicated with identical ROM constants"; PASS | Ten constants differ | **Incorrect** |
| [PORT-1A](CHDK_PORT1A_STARTUP_TRACE.md) Stage 12, L337 | Lists the stage-4 callees `0xFC05C5BC`, `0xFC418738`, `0xFC05C7D4`, `0xFC05C862`, `0xFC05B794`, `0xFC05B8D8`, `0xFC05E910` and the tail `b.w 0xFC05B962` | Matches; it omits `0xFC127B3C`/`0xFC127B4E` (the TCM fill brackets), which is an omission, not an error | **Consistent** |
| [PORT-1B](CHDK_PORT1B_HEAP_PROOF.md) §2 / §3.3 | `0x8074 = 0x80000` written in stage 3; `0x80E0+0x0C` = heap size written by the kernel unpacker | Not re-checked here (outside range). Now consistent with the ROM-verified operands. | Consistent (SOURCE VERIFIED, not re-derived) |
| ranma `g3x_110e.patch` P:1612–1668 (GM1.10E) | `"/_term"` `0xfc05b600`; `[0x80ec]`/`[0x8074]`; strings `…610/630/638/648/65c/668/674` | **Identical values** to the GM1.10C ROM for this function | SOURCE VERIFIED equality. The E value of `dmSetup`, `fc418760`, differs from the C ROM's `0xFC418738`, consistent with PORT-5B F9. This equality was established from the C ROM, not assumed from E. |

## 6. Contradictions and proposed documentation corrections (Question 7)

| # | Contradiction | Proposed documentation correction (not applied) |
|---|---|---|
| D1 | The prototype's stage-4 constants are all +4 from ROM | Record in PROJECT_STATE/HANDOFF (done in summary form). Track the §7 source correction as a pending review item. |
| D2 | PORT-1C1 L183 and the Issue 3 verdict claim "identical ROM constants" | Annotate PORT-1C1 Issue 3: **"PASS → CONTESTED by PORT-5D: stage-4 literals and check words are +4 from ROM `0xFC05B558–0xFC05B67F`; see PORT5D §5."** Owner approval needed to amend that record. |
| D3 | PORT-5C §3 classed the E-style pair and the +4 hypothesis as PLAUSIBLE | Add a forward note: **"Resolved by PORT-5D: ROM VERIFIED `[0x80EC]` vs `[0x8074]+0x10`; all eight string references +4 in prototype."** |
| D4 | PORT-5B F3 listed the correct 1.10C pair as UNKNOWN | Add a forward note: **"F3 resolved by PORT-5D (ROM VERIFIED)."** |
| D5 | PORT-1A Stage 12 omits `0xFC127B3C`/`0xFC127B4E` and the TCM `0xEEEEEEEE` fill | Optional completeness note; no correctness impact |

## 7. Proposed source correction (not applied; `boot_prototype.c` not edited)

Justified: every changed value is ROM VERIFIED in §2–§4. Ten literal replacements in `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, function `sub_fc05b558_my`. No other change.

```diff
-        "    ldr     r4, =0xfc05b604\n"        // ROM literal string "/_term"
+        "    ldr     r4, =0xfc05b600\n"        // ROM literal string "/_term" (adr @0xFC05B55A, PORT-5D)
         "    bl      sub_fc05c5bc\n"
-        "    ldr     r0, =0x000080f0\n"
+        "    ldr     r0, =0x000080ec\n"        // literal @0xFC05B608
         "    ldr     r1, [r0]\n"
-        "    ldr     r0, =0x00008078\n"
+        "    ldr     r0, =0x00008074\n"        // literal @0xFC05B60C
         "    ldr     r0, [r0]\n"
         "    adds    r0, #0x10\n"
         "    cmp     r1, r0\n"
         "    bhs     loc_fc05b574\n"
-        "    ldr     r0, =0xfc05b614\n"        // ROM literal string "USER_MEM size checking"
+        "    ldr     r0, =0xfc05b610\n"        // ROM literal string "USER_MEM size checking"
 ...
-        "    ldr     r0, =0xfc05b634\n"        // ROM literal string "dmSetup"
+        "    ldr     r0, =0xfc05b630\n"        // ROM literal string "dmSetup"
 ...
-        "    ldr     r0, =0xfc05b63c\n"        // ROM literal string "termDriverInit"
+        "    ldr     r0, =0xfc05b638\n"        // ROM literal string "termDriverInit"
 ...
-        "    ldr     r0, =0xfc05b64c\n"        // ROM literal string "termDeviceCreate"
+        "    ldr     r0, =0xfc05b648\n"        // ROM literal string "termDeviceCreate"
 ...
-        "    ldr     r0, =0xfc05b660\n"        // ROM literal string "stdioSetup"
+        "    ldr     r0, =0xfc05b65c\n"        // ROM literal string "stdioSetup"
 ...
-        "    ldr     r0, =0xfc05b66c\n"        // ROM literal string "stdlibSetup"
+        "    ldr     r0, =0xfc05b668\n"        // ROM literal string "stdlibSetup"
 ...
-        "    ldr     r0, =0xfc05b678\n"        // ROM literal string "extlib_setup"
+        "    ldr     r0, =0xfc05b674\n"        // ROM literal string "extlib_setup"
```

Review notes for whoever applies it later, under separate approval:
- The candidate binaries in `candidate_port2a/` and the recorded hashes in `candidate_manifest.json` were built from the uncorrected source. They would be stale.
- Any test that pins the prototype's hash or symbols would need updating. No existing test pins these constants (PORT-5C §2).
- This correction does **not** change the hardware verdict.

## 8. Remaining unknowns

1. **`sub_fc05b5ea`:** whether it returns, logs, asserts or halts. Its callees `0xFC31BF04` and `0xFC084BA4`, and its format string at `0xFC05B684`, are outside the approved range.
2. **Callee semantics** of `0xFC05C862`/`0xFC05B794` with the wrong `"rm"` pointer. Not examined, and no runtime claim is made.
3. **The origin of the systematic +4** in the prototype's transcription. UNKNOWN.
4. **The remainder of `boot_prototype.c`:** its other stages were not ROM-verified here. Stage 3 was cross-checked against PORT-1B only. A +4 class of error elsewhere cannot be excluded.
5. **Power-on path** (PORT-5C B): out of scope here, still UNRESOLVED.
6. **The NUL terminator of `"extlib_setup"`** at `0xFC05B680`: outside range, not read.

## 9. Hardware readiness

**STRICT NO-GO.** The prototype is now ROM-contradicted in a pre-continuation stage. Even with §7 applied, the PORT-3C/PORT-4B restart blockers, the PORT-5C power-on question and the unknowns above remain. No phase transition is implied.

## 10. Boundary record

- **Done:**
  - Read 296 ROM bytes inside the approved range.
  - Thumb disassembly and literal/string decoding of that extract only.
  - Text comparison with project documents and the historical patch.
- **Not done:**
  - Reads outside `0xFC05B558–0xFC05B67F`, or call-tree expansion.
  - Power-on, IRQ, SD or memory-controller inspection.
  - Edits to `boot_prototype.c` or any executable, test or firmware file.
  - Builds, hardware, SD, flashing or deployment; commits or pushes.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md
```
