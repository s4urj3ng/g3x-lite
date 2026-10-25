# PORT-5C — GM1.10C early boot consistency audit

Date: **2026-10-25 (Asia/Seoul)**. Analyst: Claude Code. Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port4-documentation-consolidation`, HEAD `57968eb` (dirty/untracked work preserved).
Scope: existing evidence and documentation only.
- No ROM disassembly or binary read. The `PRIMARY.BIN` copies in the tree were not opened.
- No patch application, builds, code or test changes, or camera/SD/hardware actions.
- No classifier-closed path was touched.

**Verdicts**
- **A — check words: CONTRADICTED at document level.**
  - **The prototype's pair** `[0x80F0]` vs `[0x8078]` is not supported by any GM1.10C document.
  - **The pair the documents support** is the GM1.10E pair, `[0x80EC]` vs `[0x8074]`. GM1.10C documents show both of those words being written before the comparison, with values that make the check meaningful.
  - **Supporting signal:** the same prototype function also contradicts the existing audit's quoted ROM for the `"/_term"` string address.
  - **Resolved by PORT-5D / PORT-5E (ROM VERIFIED):** Bounded ROM read of `0xFC05B558–0xFC05B67F` confirmed `[0x80EC]` vs `[0x8074] + 0x10` and all 8 string references +4 in the prototype; corrected in PORT-5E isolated prototype (`boot_prototype.c`).
- **B — power-on check: UNRESOLVED.** Retaining the stock path is a defensible *default*, but existing evidence does not justify it as safe after restart. The halt/shutdown branch is statically reachable, and the return value of `sub_fc1284ac` in the restart context is undocumented.
- **Hardware: STRICT NO-GO** (unchanged; reinforced).

## 1. Classification

- **VERIFIED:** stated by the cited document/source text, or by arithmetic on values quoted there. "VERIFIED (doc)" means the project document records it as ROM-derived. It was not re-derived here.
- **PLAUSIBLE:** follows from verified facts plus a stated premise.
- **UNKNOWN:** not established by existing evidence.

Patch references "P:n" are `g3x_110e.patch` lines. "C:n" are `chdk-port/platform/g3x/sub/110c/boot_prototype.c` lines.

## 2. Evidence register

| ID | Source | What it records (GM1.10C unless stated) |
|---|---|---|
| E1 | [CHDK_PORT1B_HEAP_PROOF.md](CHDK_PORT1B_HEAP_PROOF.md) §2 (L41–51, L109–113) | Stage 3 (`0xFC05B3DA..EC`) writes `*(0x8074)=0x00080000`, `*(0x8078)=0x42281000`, `*(0x807C)=0x42283000`. Literals at `0xFC05B45C/64/6C`. |
| E2 | PORT-1B §3.3 (L166–175); [CHDK_PORT1A_STARTUP_TRACE.md](CHDK_PORT1A_STARTUP_TRACE.md) Stage 11 (L318–330) | The kernel unpacker `0xBFE11EB0` writes descriptor words to `0x80E0`: `+0x00=0x0060E000`, `+0x04=0x000C0000`, `+0x08=heap base`, **`+0x0C` = `0x00600014 − base` (heap size)**. `sp[0x10]`/`sp[0x14]` feed Table 2 at `0x000403C8`. No write to `0x80E0+0x10` (`0x80F0`) is documented. |
| E3 | PORT-1A Stage 11–12 (L318–337) | Order: kernel table unpack (E2) → scheduler → initial task `0xFC05B559` runs. |
| E4 | [CHDK_PORT1C1_CRITICAL_AUDIT.md](CHDK_PORT1C1_CRITICAL_AUDIT.md) §4.1 (L173–184) | Quoted stock stage 4: `0xFC05B558 push {r4,lr}`, **`0xFC05B55A adr r4, #0xa4 @ "/_term"`**, `0xFC05B55C bl 0xfc05c5bc`, then `...` (body elided), ending `0xFC05B5E2 pop.w`, `0xFC05B5E6 b.w 0xfc05b962`. It claims the prototype replicates all stages "with identical ROM constants". |
| E5 | PORT-1C1 §4.1 (L185–208) | Quoted stock stage 5: `0xFC05B964 bl fc05ba68`, `B968 bl fc079404`, `B96C bl fc1284ac`, `B970 cbnz r0, B978`, `B972 bl fc05ba56`, **`B976 b B976` ("Halt if power-off requested")**, then `CreateTask("Startup")`. |
| E6 | PORT-1A Stage 12 (L341–347) | `0xFC05B98E adr r0, #0x10` → `"Startup"`. Prototype literal `0xfc05b9a0` (C:364). |
| E7 | `chdk-port/platform/g3x/sub/110c/funcs_by_address.csv` (existing sigfinder output) | `0xfc079405,IsNormalCameraMode_FW`. No name for `fc1284ac`, `fc05ba56` or `fc05b5ea`. |
| E8 | [CHDK_PORT1C_IMPLEMENTATION_REPORT.md](CHDK_PORT1C_IMPLEMENTATION_REPORT.md) L82–84; [CHDK_PORT1C_BOOT_CONTROL_FLOW.md](CHDK_PORT1C_BOOT_CONTROL_FLOW.md) L185 | Describes the retained check as "Uses Canon's unmodified ROM handler. If shutdown requested, halts safely via `bl sub_fc05ba56`." |
| E9 | Prototype C:264–278, 342–350 | Stage 4 checks `[0x80F0] ≥ [0x8078]+0x10`; failure → `sub_fc05b5ea("USER_MEM…" @ 0xfc05b614)`. Stage 5 retains `fc079404`, `fc1284ac`, `cbnz`, `fc05ba56`, halt. Strings in stage 4 at `0xfc05b604…0xfc05b678`. |
| E10 | ranma GM1.10E, P:1612–1622, 1662–1668, 1681–1703, 680–686, 701 (historical; not 1.10C evidence) | E checks `[0x80EC] ≥ [0x8074]+0x10`; strings `0xfc05b600…0xfc05b674`. Power check commented out: "TODO: Find out why the default handler in sub_fc1284ac is broken". Notes: `sub_fc1284ac` "reads GPIOs to determine startup cause"; `sub_fc05ba56` "sets GPIO 0x67 (0xD20B019C, maybe power-off?)". |
| E11 | Candidate manifest `candidate_port2a/candidate_manifest.json` | `dryos_heap_base 0x00366C90`, `dryos_heap_upper 0x00600014`. |

No project test asserts the stage-4 check-word or string constants: a grep of `tests/` finds no `80f0`, `8078`, `fc05b604` or `fc1284ac`.

## 3. Task 1–3: check-word pairs

### 3.1 Documented origins

| Pair | Where it appears | Documented derivation | Status |
|---|---|---|---|
| `[0x80EC]` vs `[0x8074]` | ranma GM1.10E source only (P:1614–1617) | capdis of the 1.10E ROM (P:1610) | VERIFIED as historical source; not 1.10C evidence |
| `[0x80F0]` vs `[0x8078]` | Our prototype (C:270–273) | **No document records its derivation.** PORT-1C1 E4 elides the instructions (`...`) and asserts "identical ROM constants" without listing them. | **UNKNOWN origin** |

### 3.2 Which addresses are initialised before the comparison (GM1.10C documents)

| Word | Writer before stage 4 | Value | Status |
|---|---|---|---|
| `0x8074` | Stage 3, `0xFC05B3DA..E0` (E1) | `0x00080000` | VERIFIED (doc) |
| `0x8078` | Stage 3, `0xFC05B3E2..E6` (E1) | `0x42281000` (PORT-1B labels it a "hardware register pointer") | VERIFIED (doc) |
| `0x80EC` | Kernel unpacker `0xBFE11EB0` (E2), before the initial task (E3) | Heap size = `0x00600014 − base` | VERIFIED (doc) |
| `0x80F0` | **None documented.** E2 lists only `0x80E0..0x80EC`, and routes `sp[0x10]` to Table 2 at `0x403C8`. It holds whatever the low-RAM copy or kernel left there. | Unknown | **UNKNOWN** |

### 3.3 Consistency evaluation (documented values only; no runtime claim)

- **E-style pair on 1.10C documents:** compares heap size against `0x80000+0x10`.
  - That is a coherent "USER_MEM size" check: the heap must exceed 512 KiB plus 16 bytes.
  - With our shifted base `0x00366C90` (E11), heap size = `0x00299384` ≥ `0x00080010`.
  - **PLAUSIBLE** that this pair is the GM1.10C semantics, because every operand is documented and the meaning matches the error string.
- **Prototype pair:** compares an undocumented word against `0x42281000+0x10`.
  - A pointer-like value plus 16 has no documented meaning as a size bound.
  - No document supports it.
  - **This report does not infer what happens at runtime.** `[0x80F0]` is unknown, and the behavior of `sub_fc05b5ea` is undocumented (E7 has no name for it).

### 3.4 Corroborating contradiction in the same function

- **Arithmetic on E4:** Thumb `ADR` resolves to `Align(PC+4, 4) + imm`. `0xFC05B55A + 4 = 0xFC05B55E`, which aligns to `0xFC05B55C`; adding `0xA4` gives **`0xFC05B600`**.
- **Method check:** the same arithmetic on E6 (`0xFC05B98E adr r0, #0x10`) gives `0xFC05B9A0`, which **matches** prototype C:364.
- **Mismatch:** the prototype loads `"/_term"` from **`0xfc05b604`** (C:268). That contradicts the PORT-1C1 audit's own quoted ROM. **VERIFIED (doc-arithmetic contradiction).**
- **The +4 is systematic:** all eight stage-4 string literals in the prototype (`…604, 614, 634, 63c, 64c, 660, 66c, 678`) are exactly +4 from ranma's E values (`…600, 610, 630, 638, 648, 65c, 668, 674`). The one value independently checkable from GM1.10C documents (E4) equals the E value, not the prototype value.
- **Implication:** the prototype's stage-4 constants plausibly carry a **systematic +4 transcription error**, which would also explain `0x80F0/0x8078` against `0x80EC/0x8074`. **PLAUSIBLE.** The cause is UNKNOWN; the PORT-1C1 claim of "identical ROM constants" is contradicted for at least one constant.

**Answer A: CONTRADICTED & RESOLVED** (the prototype pair was contradicted; resolved by PORT-5D via ROM verification of `[0x80EC]` vs `[0x8074]+0x10`; literals corrected in PORT-5E).

## 4. Task 4: power-on check reachability

| Question | Evidence | Status |
|---|---|---|
| Is a halt/shutdown branch statically reachable? | E5: if `sub_fc1284ac` returns 0 → `bl sub_fc05ba56` → `b .` (infinite loop). The prototype keeps this exactly (C:346–350). | **VERIFIED (doc)**: reachable on the zero-return path |
| What does `sub_fc1284ac` return after a DISKBOOT restart? | No GM1.10C document describes its inputs or logic. E7 gives no name. Ranma's E note says it reads GPIOs for the startup cause (E10). | **UNKNOWN** |
| What does `sub_fc05ba56` do? | No GM1.10C document. E10 (E only): "sets GPIO 0x67 … maybe power-off?" | **UNKNOWN** for 1.10C; "maybe power-off" is HISTORICAL only |
| Role of `IsNormalCameraMode_FW` (`fc079404`) | E7 names it. In E5 its return is not tested (the `cbnz` follows `fc1284ac`). Side effects undocumented. | Name VERIFIED (sigfinder); effect UNKNOWN |
| Was this path ever exercised after restart on 1.10C? | No: the prototype was never run on hardware (manifest `hardware_readiness: NO-GO`). | VERIFIED (absence) |
| Ranma's "broken" report | E10, a TODO on GM1.10E; no description of the symptom | HISTORICAL; not transferable |

**E8 overstates the evidence.** Calling it "halts safely" is unsupported, because an infinite loop after an unknown GPIO action is a hang, not a documented safe state. That wording should not be read as a safety property.

**Answer B: retaining the stock check is not justified by evidence; it is merely unrefuted.** As an engineering default it has one merit: it avoids inventing a start cause, and ranma's workaround is explicitly not to be copied. Whether it returns non-zero in the restart context is the open question.

## 5. Task 5: source-proven differences vs version assumptions

| Item | Source-proven (texts differ) | Depends on an assumption |
|---|---|---|
| Check words `0x80EC/0x8074` (E) vs `0x80F0/0x8078` (C prototype) | VERIFIED difference | That 1.10C equals 1.10E here: **not assumed**. The 1.10C documents independently favour the E pair (§3). |
| Stage-4 strings: E `…600` vs prototype `…604` | VERIFIED difference | The 1.10C value `0xFC05B600` comes from E4 arithmetic, not from E |
| Stage-5 call sites `fc079404`, `fc1284ac`, `fc05ba56`: identical in E (commented) and C | VERIFIED same text | Same function and behavior in both builds: UNKNOWN (§4.4 of PORT-5B shows irregular build differences) |
| Power-check omission (E) vs retention (C) | VERIFIED design difference | That E's "broken" applies to 1.10C: **not assumed** |

## 6. Task 6: contradictions

| # | Contradiction | Between | Status |
|---|---|---|---|
| X1 | `"/_term"` at `0xFC05B600` (from quoted ROM) vs `0xFC05B604` (prototype) | PORT-1C1 E4 ↔ prototype C:268 | **VERIFIED contradiction** |
| X2 | "All 7 stages replicated with identical ROM constants" vs X1 | PORT-1C1 L183 ↔ PORT-1C1 L177 (internal) | **VERIFIED contradiction**; the PORT-1C1 Issue 3 PASS is weakened for stage 4 |
| X3 | Check pair `0x80F0/0x8078` vs documented writers of `0x80EC`/`0x8074` and an undocumented `0x80F0` | Prototype ↔ PORT-1B/PORT-1A | **Unsupported** (PLAUSIBLE error) |
| X4 | "halts safely" vs an infinite loop after an undocumented call | PORT-1C impl. report ↔ PORT-1C1 E5 | Wording overstates; no safety evidence |
| X5 | Historical source says the stock power check is broken (E); the prototype treats it as correct (C) | ranma ↔ prototype | Not a contradiction about 1.10C; an open question |

## 7. Remaining evidence gaps, and ROM ranges requiring separate authorisation

Existing evidence is **insufficient** to close A or B. Per the task's stop rule, these are the exact read-only ranges that would settle the gaps. **Not read here.**

| Gap | ROM range (GM1.10C `PRIMARY.BIN`, VMA) | What it would settle |
|---|---|---|
| G-A1 | **`0xFC05B558–0xFC05B5E9`**: stage-4 code | The actual check-word loads and compare (`0x80EC/0x8074` vs `0x80F0/0x8078`) |
| G-A2 | **`0xFC05B5EA–0xFC05B67F`**: the following routine (`sub_fc05b5ea`), stage-4 literal pool and string table | The literal values feeding G-A1, the string addresses (X1) and what the error routine does |
| G-B1 | **`0xFC05B962–0xFC05B9A7`**: stage-5 code and `"Startup"` | Already quoted in E5. A re-read would confirm only exact bytes (optional). |
| G-B2 | **`sub_fc1284ac` entry through its return** (start `0xFC1284AC`; extent unknown, so bound the read at `0xFC1284AC–0xFC1285FF` and stop at the first return) | The inputs to the startup-cause decision and when it returns 0 |
| G-B3 | **`0xFC05BA56–0xFC05BA67`** (`sub_fc05ba56`, up to `sub_fc05ba68`) | Whether the failure branch drives a power-off GPIO before the hang |

Gaps that **no ROM read can close**: the restart-time hardware state that `sub_fc1284ac` samples (button and GPIO levels after DISKBOOT). That requires hardware observation, which is **STRICT NO-GO** in the current phase.

G-B2/G-B3 may touch GPIO or MMIO reads. They are listed only as **candidates for owner decision** and must be checked against the classifier-closed scope (IRQ caller enumeration, SD write sites, script teardown) before any authorisation. They are not those paths, but MMIO-adjacent reading is the owner's call.

## 8. Smallest next investigation

**PORT-5D (owner authorisation required): read-only confirmation of G-A1 + G-A2 only** (`0xFC05B558–0xFC05B67F`, 296 bytes). It needs no MMIO and no task or SD paths. Output: a correction note listing the verified stage-4 constants, and a reviewed proposal (not an edit) for `boot_prototype.c`.

G-B2/G-B3 should follow only if the owner wants the power-path question answered statically. Even then, B stays UNKNOWN until the restart-time GPIO state can be observed.

Documentation-only follow-ups that need no ROM access:
- Annotate PORT-1C1 Issue 3 as **PASS → CONTESTED (stage 4 constants)**.
- Replace "halts safely" in the PORT-1C implementation report with "enters an infinite loop after `sub_fc05ba56` (behavior undocumented)".

Neither is done here, because both documents are earlier audit records. Owner approval is needed to amend them.

## 9. Hardware readiness

**STRICT NO-GO.** This audit adds two reasons to the existing PORT-3C/PORT-4B blockers:
1. A documented, unresolved inconsistency in a pre-kernel-continuation stage of the prototype (A).
2. An unproven halt/shutdown branch on the startup path (B).

## 10. Boundary record

- **Done:**
  - Read the listed documents, the prototype source, the historical patch text and the existing 1.10C sigfinder CSV.
  - Arithmetic on quoted instruction values.
- **Not done:**
  - ROM or binary reads, or disassembly.
  - Applying the patch, or substituting E addresses into the prototype.
  - Code, test or document amendments outside this report and the PROJECT_STATE/HANDOFF summaries.
  - Builds, camera, SD or hardware actions; commits, pushes or merges.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md
```
