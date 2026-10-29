# PORT-14 Q-U4-08: Task Execution CPU Mode and Interrupt Mask Conformance (`OBLIG-U4-08`)

- **Milestone:** PORT-14
- **Task ID:** p14-q-u4-08
- **Target Obligation:** `OBLIG-U4-08` (Domain: `EXECUTION_CONTEXT`)
- **Baseline Git SHA:** `d1d5ce1347ee6084d5940e95060da7c08d0ff93a` [VERIFIED: docs/agentbridge/PORT14_BASE.md:18, 38]
- **Target Firmware:** Canon PowerShot G3 X `GM1.10C` [VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:3; docs/PORT11A_GM110C_ROM_EVIDENCE.md:1, 5]
- **Analysis Mode:** Read-only offline static artifact audit; zero hardware trials, zero binary modifications, zero new ROM dumps [VERIFIED: docs/SAFETY.md:1–8; docs/PORT13_NEXT_QUESTIONS.md:3]

---

## 1. Executive Summary

This document resolves the Rank 1 research question formulated in `docs/PORT13_NEXT_QUESTIONS.md:75–85` regarding proof obligation `OBLIG-U4-08` (`"Task Execution CPU Mode and Interrupt Mask Conformance"`), defined in `tools/port13_oblig_u4.py:279–294` [VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:75–85; tools/port13_oblig_u4.py:279–294].

At the baseline commit `d1d5ce1347ee6084d5940e95060da7c08d0ff93a`, all 14 PORT-13 deliverables and tests are tracked and present [VERIFIED: docs/agentbridge/PORT14_BASE.md:13–28, 131–154], and `p14-base` reported zero missing inputs [VERIFIED: docs/agentbridge/PORT14_BASE.md:25, 456–458]. In `tools/port13_oblig_u4.py:290`, `OBLIG-U4-08` was cataloged with baseline status `UNKNOWN` pending static evaluation of tracked context creation and wrapper disassembly [VERIFIED: tools/port13_oblig_u4.py:290; docs/PORT13_OBLIG_U4.md:57; docs/PORT13_NEXT_QUESTIONS.md:75–85].

Based exclusively on Git-tracked primary evidence on `origin/main`:
1. DryOS task context creation in ROM at `0xFC05C5A8` loads initial saved CPSR via `movs r0, #0xf3` into `[sp, #0x3C]`, setting saved CPSR to strictly `0x000000F3`: **Privileged Supervisor Mode** (`M = 0x13`), Thumb-2 (`T = 1`), IRQ masked (`I = 1`), and FIQ masked (`F = 1`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–306; docs/PORT13_REVIEW_U4.md:117; docs/PORT13_OBLIG_U4.md:118].
2. Context restore at `0xFC267B90..0xFC267B98` executes `rfeia sp!`, entering generic DryOS task wrapper `0xBFE11722` in Privileged Supervisor Mode (`0x13`) and Thumb state (`T = 1`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:307–308; docs/PORT3C_RESTART_READINESS_MATRIX.md:126].
3. The task wrapper unmask helper entered at `0xFC267BE6` clears only the IRQ mask bit (`bic r1, r1, #0x80` at `0xFC267BEA`) and writes CPSR via `msr cpsr_fsxc, r1` at `0xFC267BF2`, yielding `CPSR[7:6] = 0b01` (IRQ enabled `I = 0`, FIQ masked `F = 1`) while strictly preserving Privileged Supervisor Mode (`0x13`) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:126–128, 225; docs/PORT13_REVIEW_U4.md:118, 183, 278, 299; docs/PORT13_OBLIG_U4.md:119].
4. The historical PR #25 claim that DryOS user tasks execute in ARM System Mode (`0x1F`) with IRQ and FIQ enabled (`CPSR[7:6] = 0b00`) is refuted and contradicted by tracked ROM decodings [VERIFIED: docs/PORT13_REVIEW_U4.md:113–120, 183, 278, 299; docs/PORT13_OBLIG_U4.md:115–121].
5. Because `OBLIG-U4-08` explicitly requires static evidence (`requires_runtime_evidence=False` in `tools/port13_oblig_u4.py:293`), this tracked disassembly completely satisfies the required evidence artifact `TASK_CONTEXT_EVIDENCE` without needing physical execution or new ROM reads [VERIFIED: tools/port13_oblig_u4.py:282–293; docs/PORT13_NEXT_QUESTIONS.md:76, 84].

Consequently, the tracked evidence fully supports moving `OBLIG-U4-08` to **`VERIFIED`**, and a code change to update `tools/port13_oblig_u4.py` is justified in a subsequent task [VERIFIED: tools/port13_oblig_u4.py:279–294; docs/PORT13_NEXT_QUESTIONS.md:82].

---

## 2. Obligation Definition and Bounded Question Quotes

### 2.1 Verbatim Quote: `OBLIG-U4-08` Definition and Current Status in `tools/port13_oblig_u4.py`

From [`tools/port13_oblig_u4.py:279–294`](../tools/port13_oblig_u4.py#L279-L294):

```python
    U4Obligation(
        id="OBLIG-U4-08",
        statement="Task execution CPU mode and interrupt mask conformance (Privileged Supervisor Mode)",
        required_evidence=RequiredEvidence(
            artifact_type="TASK_CONTEXT_EVIDENCE",
            what_it_must_show=(
                "Proof that SpyTask executes in Privileged Supervisor Mode (M = 0x13) with initial "
                "CPSR 0x000000F3, unmasked to IRQ enabled and FIQ disabled (CPSR[7:6] = 0b01), "
                "never assuming System Mode or unmasked FIQ."
            ),
        ),
        current_status=ObligationStatus.UNKNOWN,
        citation="docs/PORT13_REVIEW_U4.md:113-120, 183, 278, 299",
        domain=Domain.EXECUTION_CONTEXT,
        requires_runtime_evidence=False,
    ),
```
[VERIFIED: tools/port13_oblig_u4.py:279–294]

- **Current Status in canonical module:** `ObligationStatus.UNKNOWN` [VERIFIED: tools/port13_oblig_u4.py:290].
- **Requires Runtime Evidence:** `False` [VERIFIED: tools/port13_oblig_u4.py:293].
- **Canonical Domain:** `Domain.EXECUTION_CONTEXT` [VERIFIED: tools/port13_oblig_u4.py:292].
- **Required Artifact Type:** `"TASK_CONTEXT_EVIDENCE"` [VERIFIED: tools/port13_oblig_u4.py:283].

### 2.2 Verbatim Quote: Question 1 (Rank 1) in `docs/PORT13_NEXT_QUESTIONS.md`

From [`docs/PORT13_NEXT_QUESTIONS.md:75–85`](PORT13_NEXT_QUESTIONS.md#L75-L85):

> **Question 1 (Rank 1): Task Execution CPU Mode and Interrupt Mask Conformance (`OBLIG-U4-08`)**
> - **Target obligation ID(s) and scope**: `OBLIG-U4-08` (full obligation: `"Task Execution CPU Mode and Interrupt Mask Conformance"`, requiring `TASK_CONTEXT_EVIDENCE` with `requires_runtime_evidence=False`) [VERIFIED: tools/port13_oblig_u4.py:279–294].
> - **Tracked files and line ranges to consult**:
>   - [`tools/port13_oblig_u4.py:279–294`](../tools/port13_oblig_u4.py#L279-L294) and [`docs/PORT13_OBLIG_U4.md:57, 117–121`](PORT13_OBLIG_U4.md#L57) [VERIFIED: tools/port13_oblig_u4.py:279–294; docs/PORT13_OBLIG_U4.md:57, 117–121].
>   - [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168) [VERIFIED: docs/PROJECT_STATE.md:168].
>   - [`docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125–128, 225`](PORT3C_RESTART_READINESS_MATRIX.md#L125-L128) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125–128, 225].
> - **Bounded question**: Do the decoded context-initialization (`0xFC05C5A8`) and task-wrapper unmasking (`0xFC267BE6` / `0xFC267BF2`) instructions already recorded in `docs/PROJECT_STATE.md:168` and `docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125–128, 225` satisfy `OBLIG-U4-08`'s static `TASK_CONTEXT_EVIDENCE` requirement that DryOS tasks on `GM1.10C` execute in privileged Supervisor Mode (`0x13`, Thumb `T=1`) with IRQ unmasked (`bic r1, r1, #0x80` -> `msr cpsr_fsxc, r1`) and FIQ remaining masked? [INFERRED: tools/port13_oblig_u4.py:279–294; docs/PROJECT_STATE.md:168; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128].
> - **Effect of a positive answer**: Moves `OBLIG-U4-08` from `UNKNOWN` to `VERIFIED` (once wired into the static evidence mapping) by confirming from tracked disassembly that task contexts initialize saved CPSR to `0x000000F3` (Supervisor mode `0x13`, Thumb `T=1`, `I=1`, `F=1`) and task wrapper unmasking (`0xFC267BE6`..`0xFC267BF2`) clears only the IRQ mask bit (`bic r1, r1, #0x80`) while preserving Supervisor mode and FIQ masking [VERIFIED: docs/PROJECT_STATE.md:168; docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125–128, 225; INFERRED: tools/port13_oblig_u4.py:279–294].
> - **Effect of a negative answer**: Leaves `OBLIG-U4-08` as `UNKNOWN` (fail-closed) if the tracked evidence is deemed specific to initial bootstrap task dispatch rather than general `CreateTask` context creation for `task_spytask`, or if DryOS tasks ran in System Mode or unmasked FIQ [INFERRED: tools/port13_oblig_u4.py:279–294; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128].
> - **Why no new ROM read is needed**: Both the task context initialization (`0xFC05C5A8` setting saved CPSR `0x000000F3`) and the wrapper unmask instruction sequence (`0xFC267BE6`: `mrs r1, apsr`; `0xFC267BEA`: `bic r1, r1, #0x80`; `...BEE`: `orr r1, r1, #0`; `0xFC267BF2`: `msr cpsr_fsxc, r1`) are already decoded and recorded in tracked baseline documentation on `origin/main` [VERIFIED: docs/PROJECT_STATE.md:168; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128, 225].
[VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:75–85]

---

## 3. Tracked Baseline Artifact Evidence Inventory

All evidence cited below derives exclusively from Git-tracked repository files at base commit `d1d5ce1347ee6084d5940e95060da7c08d0ff93a` [VERIFIED: docs/agentbridge/PORT14_BASE.md:18, 38]. Untracked and Git-ignored local files are strictly excluded [VERIFIED: docs/agentbridge/PORT14_BASE.md:441; docs/SAFETY.md:1–8].

### 3.1 Task Context Initialization at ROM `0xFC05C5A8`

The instruction sequence for DryOS task context initialization is decoded and recorded in tracked repository artifacts:

1. **Instruction disassembly:**
   At `0xFC05C5A8`, DryOS initializes new task execution contexts via:
   ```text
   subs r2, #0x40
   bic r2, r2, #7
   str r2, [r0]
   movs r0, #0xf3
   strd r1, r0, [r2, #0x38]
   ```
   [VERIFIED: docs/HANDOFF.md:305].
2. **Saved Context Layout:**
   - Saved PC is written to `[sp, #0x38]` (offset `#0x38`), initialized to `0xBFE11723` (Thumb interworking entry to generic task wrapper `0xBFE11722`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/PORT13_REVIEW_U4.md:117].
   - Saved CPSR is written to `[sp, #0x3C]` (offset `#0x3C`), initialized via `movs r0, #0xf3` to strictly `0x000000F3` [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–306; docs/PORT13_REVIEW_U4.md:117].
3. **Decoded Bitfield Semantics of `0x000000F3`:**
   - **Mode bits `M[4:0] = 0x13` (`0b10011`):** ARM Privileged Supervisor Mode (`SVC`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:63; docs/PORT13_REVIEW_U4.md:117].
   - **Bit 5 (`T = 1`):** Thumb execution state [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125].
   - **Bit 6 (`F = 1`):** FIQ masked / disabled [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:64, 125].
   - **Bit 7 (`I = 1`):** IRQ masked / disabled [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:64, 125].
   - **Condition flags `NZCVQ`:** Initialized to zero [VERIFIED: docs/PROJECT_STATE.md:162, 168].

### 3.2 Context Switch Restore at `0xFC267B90..0xFC267B98`

When DryOS dispatches a task context, context restoration occurs via:
```text
ldr.w sp, [r0]
pop.w {r0-r12, lr}
rfeia sp!
```
[VERIFIED: docs/HANDOFF.md:307].

- Instruction `rfeia sp!` at `0xFC267B98` atomically pops the saved PC (`0xBFE11723`) and saved CPSR (`0x000000F3`) from the task stack [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:307].
- Because saved CPSR is `0x000000F3`, the CPU hardware atomically enters Privileged Supervisor Mode (`M = 0x13`), Thumb-2 (`T = 1`), with IRQ masked (`I = 1`) and FIQ masked (`F = 1`) at address `0xBFE11722` [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:307–308; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–126].

### 3.3 Task Wrapper Unmask Sequence at `0xFC267BE6..0xFC267BF2`

Inside generic task wrapper `0xBFE11722`, the kernel passes `0` and branches to helper `0xFC267BE6` prior to executing the task body [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:126; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].

The helper instruction sequence is verified verbatim in tracked documentation:
1. `0xFC267BE6`: `mrs r1, apsr` (helper entry, reads current processor status) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225; docs/PORT13_NEXT_QUESTIONS.md:84; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].
2. `0xFC267BEA`: `bic r1, r1, #0x80` (clears bit 7, the IRQ mask bit `I`) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225; docs/PORT13_REVIEW_U4.md:118; docs/PORT13_NEXT_QUESTIONS.md:84].
3. `...BEE`: `orr r1, r1, #0` (preserves all other bits, including bit 6 `F=1` and mode `0x13`) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127; docs/PORT13_NEXT_QUESTIONS.md:84; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].
4. `0xFC267BF2`: `msr cpsr_fsxc, r1` (architectural mask write clearing `CPSR.I`) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 128, 225; docs/PORT13_REVIEW_U4.md:118; docs/PORT13_NEXT_QUESTIONS.md:84; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].
5. `0xFC267BF6`: `bx lr` (returns to wrapper) [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].

---

## 4. Claim-by-Claim Evidence Evaluation

### 4.1 Claim 1: Privileged Supervisor Mode (`M = 0x13`) Conformance

- **Claim Statement:** DryOS tasks execute in Privileged Supervisor Mode (`M = 0x13`), never assuming ARM System Mode (`0x1F`) or User Mode [VERIFIED: tools/port13_oblig_u4.py:285–287; docs/PORT13_OBLIG_U4.md:57].
- **Audit Findings:**
  1. The initial context generation at `0xFC05C5A8` writes `0x000000F3` (`movs r0, #0xf3`) to `[sp, #0x3C]` [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–306; docs/PORT13_REVIEW_U4.md:117]. The low five bits `0x13` (`0b10011`) encode ARM Supervisor Mode [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:63].
  2. The unmasking helper (`0xFC267BE6`..`0xFC267BF2`) modifies only bit 7 via `bic r1, r1, #0x80` [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225; docs/PORT13_REVIEW_U4.md:118]. Bits 4:0 (`0x13`) are not altered [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127; docs/PORT13_NEXT_QUESTIONS.md:84].
  3. Base task entry CPSR becomes `0x00000073` [VERIFIED: docs/PROJECT_STATE.md:162]. Mode bits remain strictly `0x13` [VERIFIED: docs/PROJECT_STATE.md:162, 168; docs/HANDOFF.md:309].
  4. Tracked analysis proves zero transitions to User Mode or System Mode (`0x1F`) occur during task dispatch or startup continuation [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:309; docs/PORT13_REVIEW_U4.md:119].
- **Status:** **`VERIFIED`** [docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306–309; docs/PORT13_REVIEW_U4.md:113–120].

### 4.2 Claim 2: Instruction Set Conformance (Thumb-2, `T = 1`)

- **Claim Statement:** DryOS tasks execute in Thumb-2 state (`T = 1`) [VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:81; docs/PORT13_OBLIG_U4.md:118].
- **Audit Findings:**
  1. Saved CPSR `0x000000F3` has bit 5 set (`T = 1`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125].
  2. Saved PC is initialized to `0xBFE11723` [VERIFIED: docs/PROJECT_STATE.md:168; docs/PORT13_REVIEW_U4.md:117]. The least significant bit (bit 0 = 1) is the standard ARM interworking indicator specifying Thumb execution state upon branch/return via `rfeia sp!` [VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:127; docs/PROJECT_STATE.md:168].
  3. The unmask helper at `0xFC267BE6` and task wrapper `0xBFE11722` execute entirely in Thumb state [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:23, 37].
- **Status:** **`VERIFIED`** [docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:63, 125].

### 4.3 Claim 3: Interrupt Mask State Conformance (`CPSR[7:6] = 0b01`)

- **Claim Statement:** Task execution unmasks IRQ (`I = 0`) while keeping FIQ masked (`F = 1`), establishing `CPSR[7:6] = 0b01`, and never unmasks FIQ [VERIFIED: tools/port13_oblig_u4.py:286–287; docs/PORT13_OBLIG_U4.md:57, 118–119].
- **Audit Findings:**
  1. The initial context at `0xFC05C5A8` sets both bit 7 (`I = 1`) and bit 6 (`F = 1`) [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:306; docs/PORT3C_RESTART_READINESS_MATRIX.md:64, 125].
  2. The unmask helper executes `bic r1, r1, #0x80` at `0xFC267BEA` [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225; docs/PORT13_REVIEW_U4.md:118]. Value `#0x80` corresponds strictly to bit 7 (`I`); bit 6 (`#0x40`, `F`) is untouched [VERIFIED: docs/PORT3C_RESTART_READINESS_MATRIX.md:127; docs/PORT13_REVIEW_U4.md:118].
  3. The resulting interrupt mask field in CPSR is `CPSR[7:6] = 0b01` (IRQ enabled, FIQ masked) [VERIFIED: docs/PORT13_REVIEW_U4.md:118, 183; docs/PORT13_OBLIG_U4.md:119].
  4. FIQ unmasking (`F = 0` / `CPSR[7:6] = 0b00`) is never executed by the task wrapper or context creation logic [VERIFIED: docs/PORT13_REVIEW_U4.md:118, 183; docs/PORT13_OBLIG_U4.md:119].
- **Status:** **`VERIFIED`** [docs/PORT13_REVIEW_U4.md:118, 183, 278, 299; docs/PORT3C_RESTART_READINESS_MATRIX.md:126–128, 225].

### 4.4 Claim 4: Universality Across DryOS Tasks vs Bootstrap Specificity

- **Claim Statement:** The context creation (`0xFC05C5A8`) and wrapper unmask sequence (`0xFC267BE6`..`0xFC267BF2`) apply generically to all DryOS tasks dispatched under the kernel framework (including candidate tasks created via `CreateTask`), rather than being unique to initial bootstrap execution [VERIFIED: docs/PORT13_REVIEW_U4.md:117–119; docs/PORT13_OBLIG_U4.md:118–119].
- **Audit Findings:**
  1. In `docs/PROJECT_STATE.md:168`, `docs/HANDOFF.md:305`, `docs/PORT13_REVIEW_U4.md:117`, and `docs/PORT13_OBLIG_U4.md:118`, routine `0xFC05C5A8` is identified without qualification as `"DryOS task context creation in ROM"` [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305; docs/PORT13_REVIEW_U4.md:117; docs/PORT13_OBLIG_U4.md:118].
  2. In `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37`, the task wrapper at `0xBFE11722` is identified as the generic entry wrapper that `"passes zero and calls the helper before invoking the task entry"` [VERIFIED: docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37].
  3. In `docs/PORT13_REVIEW_U4.md:113–120` (Finding C15) and `docs/PORT13_REVIEW_U4.md:299` (Remediation #7), the repository governance authoritative review rejected the notion of System Mode tasks and mandated that the general rule for DryOS user tasks on `GM1.10C` is Privileged Supervisor Mode (`M = 0x13`) with `CPSR[7:6] = 0b01` [VERIFIED: docs/PORT13_REVIEW_U4.md:113–120, 183, 278, 299].
  4. DryOS implements a single unified task scheduler on Cortex-R4; no separate "User mode scheduler" or "System mode task creator" exists in the tracked architecture [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–309; docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 131–180].
- **Status:** **`VERIFIED`** [docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–309; docs/PORT13_REVIEW_U4.md:113–120, 299].

---

## 5. Summary Reconciliation Table

| Evidence Element | Tracked Location & Exact Citation | Value / Opcode Sequence | Semantic Meaning | Status |
|---|---|---|---|:---:|
| **Context Init Entry** | [`docs/HANDOFF.md:305`](HANDOFF.md#L305); [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168) | `0xFC05C5A8` (`subs r2, #0x40; bic r2, r2, #7; str r2, [r0]; movs r0, #0xf3; strd r1, r0, [r2, #0x38]`) | Allocates task stack frame and stores initial PC and CPSR | **`VERIFIED`** |
| **Initial Saved PC** | [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168); [`docs/PORT13_REVIEW_U4.md:117`](PORT13_REVIEW_U4.md#L117) | `0xBFE11723` at `[sp, #0x38]` | Points to task wrapper `0xBFE11722` in Thumb state (bit 0 = 1) | **`VERIFIED`** |
| **Initial Saved CPSR** | [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168); [`docs/HANDOFF.md:306`](HANDOFF.md#L306) | `0x000000F3` at `[sp, #0x3C]` | Privileged Supervisor Mode (`0x13`), Thumb (`T=1`), `I=1`, `F=1` | **`VERIFIED`** |
| **Context Switch** | [`docs/HANDOFF.md:307`](HANDOFF.md#L307); [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168) | `0xFC267B90..0xFC267B98` (`ldr.w sp, [r0]; pop.w {r0-r12, lr}; rfeia sp!`) | Pops registers and restores PC/CPSR into CPU hardware | **`VERIFIED`** |
| **Task Wrapper Entry** | [`docs/PORT3C_RESTART_READINESS_MATRIX.md:126`](PORT3C_RESTART_READINESS_MATRIX.md#L126); [`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:37`](CODEX_INDEPENDENT_RESTART_REVIEW.md#L37) | `0xBFE11722` | Calls helper `0xFC267BE6` before invoking task body | **`VERIFIED`** |
| **Unmask Helper Entry** | [`docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225`](PORT3C_RESTART_READINESS_MATRIX.md#L225) | `0xFC267BE6` (`mrs r1, apsr`) | Reads status flags | **`VERIFIED`** |
| **IRQ Clear Bit** | [`docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225`](PORT3C_RESTART_READINESS_MATRIX.md#L225); [`docs/PORT13_REVIEW_U4.md:118`](PORT13_REVIEW_U4.md#L118) | `0xFC267BEA` (`bic r1, r1, #0x80`) | Clears bit 7 (`I=0`); leaves bit 6 (`F=1`) intact | **`VERIFIED`** |
| **Unchanged Flags** | [`docs/PORT3C_RESTART_READINESS_MATRIX.md:127`](PORT3C_RESTART_READINESS_MATRIX.md#L127); [`docs/PORT13_NEXT_QUESTIONS.md:84`](PORT13_NEXT_QUESTIONS.md#L84) | `...BEE` (`orr r1, r1, #0`) | NOP ORR preserving register state | **`VERIFIED`** |
| **Architectural Mask Write** | [`docs/PORT3C_RESTART_READINESS_MATRIX.md:127, 225`](PORT3C_RESTART_READINESS_MATRIX.md#L225); [`docs/PORT13_REVIEW_U4.md:118`](PORT13_REVIEW_U4.md#L118) | `0xFC267BF2` (`msr cpsr_fsxc, r1`) | Writes new mask to CPU hardware: `CPSR[7:6] = 0b01` | **`VERIFIED`** |
| **Mode Invariant** | [`docs/PROJECT_STATE.md:168`](PROJECT_STATE.md#L168); [`docs/HANDOFF.md:309`](HANDOFF.md#L309); [`docs/PORT13_REVIEW_U4.md:119`](PORT13_REVIEW_U4.md#L119) | Zero System Mode (`0x1F`) or User Mode transitions | Execution remains strictly in Privileged Supervisor Mode (`0x13`) | **`VERIFIED`** |

[VERIFIED: docs/PROJECT_STATE.md:162, 168; docs/HANDOFF.md:305–309; docs/PORT3C_RESTART_READINESS_MATRIX.md:63–64, 125–128, 225; docs/PORT13_REVIEW_U4.md:113–120, 183, 278, 299; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:23, 37]

---

## 6. Resulting Status and Canonical Module Recommendation

### 6.1 Resulting Status of OBLIG-U4-08

In the canonical module [`tools/port13_oblig_u4.py:290`](../tools/port13_oblig_u4.py#L290), `OBLIG-U4-08` was assigned baseline status `ObligationStatus.UNKNOWN` [VERIFIED: tools/port13_oblig_u4.py:290].

Because `OBLIG-U4-08` has `requires_runtime_evidence=False` (`tools/port13_oblig_u4.py:293`), its proof requirements are strictly static (`TASK_CONTEXT_EVIDENCE`) [VERIFIED: tools/port13_oblig_u4.py:282–293]. The decoded instruction sequences in tracked artifacts (`0xFC05C5A8`, `0xFC267B90..0xFC267B98`, `0xBFE11722`, and `0xFC267BE6..0xFC267BF2`) conclusively prove that tasks execute in Privileged Supervisor Mode (`0x13`, Thumb `T=1`) with IRQ unmasked (`I=0`) and FIQ masked (`F=1`), refuting PR #25's System Mode and FIQ-unmasked conjectures [VERIFIED: docs/PROJECT_STATE.md:168; docs/HANDOFF.md:305–309; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128, 225; docs/PORT13_REVIEW_U4.md:113–120, 183, 278, 299; docs/PORT13_NEXT_QUESTIONS.md:81–84].

Per `docs/PORT13_NEXT_QUESTIONS.md:82`, a positive answer moves the obligation to `VERIFIED` [VERIFIED: docs/PORT13_NEXT_QUESTIONS.md:82].

```text
Resulting status of OBLIG-U4-08: VERIFIED
```
[VERIFIED: tools/port13_oblig_u4.py:279–294; docs/PORT13_NEXT_QUESTIONS.md:81–84; docs/PROJECT_STATE.md:168; docs/PORT3C_RESTART_READINESS_MATRIX.md:125–128, 225; docs/PORT13_REVIEW_U4.md:113–120, 299]

### 6.2 Canonical Module Change Justification

- **Canonical module change justified:** **`YES`** [INFERRED: tools/port13_oblig_u4.py:279–294; docs/PORT13_NEXT_QUESTIONS.md:82].
- **Scope of justification:**
  A code change to `tools/port13_oblig_u4.py` is justified in a subsequent task to:
  1. Update `current_status = ObligationStatus.VERIFIED` for `OBLIG-U4-08` in `U4_OBLIGATIONS` (line `290`).
  2. Wire the verified static evidence artifact `TASK_CONTEXT_EVIDENCE` into the default evidence mapping or evaluation path.
  3. Update `tests/test_port13_oblig_u4.py` to assert that `OBLIG-U4-08` evaluates as `VERIFIED` / `SATISFIED`.
- **Enforcement of task constraint:**
  In accordance with the task instructions (`"Do not edit code in this task"`; `"Only docs/PORT14_Q_U4_08.md is changed"`), no code files or tests were modified during this task.
