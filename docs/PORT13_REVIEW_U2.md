# PORT-13 — Read-Only Review of Draft PR #24 (PORT-12B U2 Filesystem Readiness)

**Review Date**: 2026-10-28  
**Reviewer**: Antigravity (Independent Firmware Reviewer, AgentBridge worker `p13-review-u2`)  
**Target Pull Request**: Draft PR #24 (milestone **PORT-12B / Issue #21**)  
**Target Branch**: `origin/research/port12b-filesystem-u2`  
**Target Commit SHA**: [`6fb7622aee7915ff2d3d39563a45ef3310ae31b3`](https://github.com/s4urj3ng/g3x-lite/commit/6fb7622aee7915ff2d3d39563a45ef3310ae31b3)  
**Base Commit SHA**: [`581b1a4bb30456bf18c46dc4bcf61b0375aee251`](https://github.com/s4urj3ng/g3x-lite/commit/581b1a4bb30456bf18c46dc4bcf61b0375aee251) (`origin/main`)  
**Merge-Base**: `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (Clean ancestor; 1 commit ahead: `+302` lines across 2 files)  
**Reviewed Artifacts**:
- `docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md` (148 lines added)
- `tests/test_port12b_filesystem_u2.py` (154 lines added)  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Read-Only Investigation)  
**Overall Recommendation**: **`needs-changes`** (Do not merge in current form; factual, evidentiary, and contract remediation required)

---

## 1. Executive Summary

This document provides a formal, independent, read-only review of Draft PR #24 (milestone **PORT-12B / Issue #21**). The stated objective of PR #24 is to translate the **U2 prerequisite** (`InitFileModules` entry vs. actual filesystem mount readiness) into formal static evidence requirements, mathematical obligations, and robust offline negative tests.

### High-Level Assessment
1. **Architectural & Epistemic Direction (Sound Foundation)**:
   - PR #24 rigorously enforces the epistemic separation between static ROM entry-point evidence and dynamic runtime filesystem readiness. It explicitly warns that observing the task entry vector `0xFC0BD071` does **not** prove filesystem mount readiness.
   - It correctly incorporates the ROM slice `S2B` evidence from `docs/PORT11A_GM110C_ROM_EVIDENCE.md`: `sub_fc0d9ccc` contains zero conditional branches of its own and concludes with `movs r0, #0; pop {r4, pc}`; therefore, **`r0 = 0` is an unconditional constant on normal return**, providing zero evidence of physical SD card presence, FAT32 partition validity, or cluster availability.
   - It correctly emphasizes that observing event `0x5006` is insufficient to establish filesystem readiness ($\text{Event}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$), adhering to `tools/port9a_runtime_lifecycle.py:301, 678–679`.
   - It strictly maintains the fail-closed governance invariant: `GM110C_PRECONDITIONS.init_file_modules_entry_verified = False` is left unchanged, and no camera hooks are introduced.
2. **Consistency with Core Runtime Models**:
   - The document and tests align with `tools/port9a_runtime_lifecycle.py` (fail-closed generation binding, constant-zero suppression, and fault handling), `tools/port9b_runtime_contract.py` (I2 contract and `C3.gate` / `C5.U2` constraints), and `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md` (prerequisite U2).
3. **Identified Inaccuracies & Evidentiary Flaws Requiring Remediation**:
   - **Instruction Address Inaccuracies in Section 2.1 Call Sequence Diagram**:
     - PR #24 states: `0xFC0BD074: bl 0xFC0D9CCC`. In GM1.10C ROM slice `S2A` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:252`), this 32-bit Thumb-2 `BL` instruction begins at **`0xFC0BD072`** (raw bytes `1c f0 2b fe`), not `0xFC0BD074`.
     - PR #24 states: `0xFC0BD078: bl 0xFC0D9CF6`. In GM1.10C ROM slice `S2A` (`PORT11A:254, 259`), address **`0xFC0BD078`** holds `movw r5, #0x5006` (`45 f2 06 05`). The actual subroutine call `bl 0xFC0D9CF6` is located at **`0xFC0BD086`** (`1c f0 36 fe`).
     - PR #24 states: `0xFC0BD07C: ... Task completion / exit`. Address **`0xFC0BD07C`** is `beq 0xFC0BD086` (`03 d0`), while task completion/epilogue occurs at **`0xFC0BD096`** (`b.w 0xFC35B93C`) and **`0xFC0BD09A`** (`pop {r4, r5, r6, pc}`).
   - **Unsupported Callee 1 Storage Init Semantics in Section 2.1 Call Sequence Diagram**:
     - PR #24's diagram asserts that Callee 1 (`sub_fc0d9ccc`) performs *"Lower-level storage/host controller init"*.
     - Label: **`UNKNOWN / UNSUPPORTED`**; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289` leaves what the nested callees of `sub_fc0d9ccc` initialize strictly **`UNKNOWN`** (all nested callees lie outside slice `S2B`).
     - **Remediation**: PR #24 must remove this description or mark it **`UNKNOWN`**.
   - **Unsupported `task_Startup` Invocation Edge in Section 2.1 Call Sequence Diagram**:
     - PR #24's diagram depicts `task_Startup` calling/creating the `InitFileModules` creator (`sub_fc0bd0b4`).
     - Label: **`UNKNOWN / UNSUPPORTED`**; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:407` leaves startup reachability and the caller of `sub_fc0bd0b4` strictly **`UNKNOWN`**.
     - **Remediation**: PR #24 must remove the edge or mark it **`UNKNOWN`**.
   - **Overstated Dispatch Semantics for Event `0x5006`**:
     - PR #24 claims that event `0x5006` is proven to be "dispatched asynchronously via message queues". This overstates the reverse-engineering evidence. In verified GM1.10C ROM (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265`), calls to `0xFC35B93C` with argument `0x5006` lie outside slice `S2A` and are explicitly classified as **`UNKNOWN`**. The tracked evidence supports only the narrower claim that event `0x5006` is **insufficient** to establish filesystem readiness; whether DryOS dispatches `0x5006` via an asynchronous queue or synchronous handler is unverified in Phase 0.
   - **Promotion Requirements Gap & Untracked Internal Specifications**:
     - In Section 3 (Obligation 3), PR #24 specifies four low-level storage driver preconditions (idle DMA, FAT32 BPB parsing, root-cluster verification, and descriptor allocation). These four items are **proposed additional requirements** from PR #24, not existing tracked requirements in `tools/port9a_runtime_lifecycle.py:300–303`.
     - Furthermore, PR #24 **lacks** an explicit obligation for verified non-destructive file open/read capability without contention or timeout, which is the actual requirement codified in `port9a_runtime_lifecycle.py:302–303` for the `fs_io_ready` stage.
   - **Citing Untracked Historical File Without Context**:
     - Section 3 (Obligation 1) cites `platform/g3x/sub/110e/boot.c:493–515` as evidence of Ranma's historical port behavior. This file path does not exist on `origin/main` or anywhere in git history (it was an untracked file from Ranma's GM1.10E patch). The citation must reference tracked secondary evidence in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` (patch lines `P:1769–1795`) and `docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`.
   - **Overstated Callee 2 (`sub_fc0d9cf6`) Functional Semantics**:
     - In §2.1 and §2.2, PR #24 characterizes `sub_fc0d9cf6` as performing "Mount completion / event dispatch" and asserts it "Dispatches mount sequence and notifies system". Tracked ROM evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:247–267, 285–289` (§4.3) leaves nested-callee behavior strictly **`UNKNOWN`** (all seven callees lie outside slice `S2B`) and places the visible `0x5006` event dispatch calls (`0xFC35B93C`) within `task_InitFileModules` itself (`PORT11A:254–265`), not inside `sub_fc0d9cf6`. These functional claims are **`UNKNOWN / OVERSTATED`**; PR #24 must qualify or correct them.
   - **Unqualified Warm-Restart Hardware State & Reset Ownership Attributions**:
     - In Section 3 (Obligation 5), PR #24 asserts as fact that SD hardware retains bus/card-host configuration across warm restart and claims `InitFileModules` is the mandatory routine to reset the SD host controller. Tracked evidence in `docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29` (§1) classifies host configuration retention as at most plausible (**P** / **`INFERRED`**), leaving the SD effects of intervening routines (`0xFC41870C` and `[0x4000]`) **`UNKNOWN`** (`docs/RESTART_SD_HOST_AUDIT.md:16, 45`). Furthermore, while the lifecycle contract (`tools/port9a_runtime_lifecycle.py:304–306`) requires warm-restart storage/SD-host preconditions to be resolved prior to promotion, it does not specify who performs the reset (`UNKNOWN / NOT ESTABLISHED`). PR #24 must qualify the hardware retention claim as plausible/inferred and decouple the lifecycle requirement from the unverified assignment of reset ownership to `InitFileModules`.
4. **Test Suite Status**:
   - The PR's test suite `tests/test_port12b_filesystem_u2.py` was executed completely unmodified in an isolated scratch checkout pinned directly to PR head commit `6fb7622aee7915ff2d3d39563a45ef3310ae31b3`, and passed completely (**8/8 PASS**, 0.001s).

---

## 2. PR Identification & Search Methodology

To locate the open PORT-12 Draft PR covering U2 (InitFileModules filesystem readiness), the following systematic read-only git queries were conducted:

1. **Remote Research Ref Enumeration**:
   - Query: `git for-each-ref refs/remotes/origin/research/`
   - Result:
     - `refs/remotes/origin/research/port12a-memory-ownership` (`3e1e3690...`) -> PR #23 (Issue #20)
     - `refs/remotes/origin/research/port12b-filesystem-u2` (`6fb7622a...`) -> PR #24 (Issue #21)
     - `refs/remotes/origin/research/port12c-spytask-u4` (`de792bd7...`) -> PR #25 (Issue #22)
2. **Cross-Reference with Tracked Baseline Documentation**:
   - Inspected `docs/agentbridge/PORT13_BASELINE.md:131–169` (Section 4.2: *PR #24: origin/research/port12b-filesystem-u2*).
   - Confirmed that GitHub Draft PR #24 implements Issue #21 / milestone PORT-12B on branch `origin/research/port12b-filesystem-u2`.
3. **Target Head SHA & Commit Verification**:
   - Query: `git rev-parse origin/research/port12b-filesystem-u2`
     - Output: `6fb7622aee7915ff2d3d39563a45ef3310ae31b3`
   - Query: `git log -1 origin/research/port12b-filesystem-u2`
     - Output:
       ```text
       commit 6fb7622aee7915ff2d3d39563a45ef3310ae31b3 (origin/research/port12b-filesystem-u2)
       Author: avp <avp@mac-buc.local>
       Date:   Wed Oct 28 23:21:11 2026 +0900

           docs(port12b): U2 filesystem readiness proof obligations and negative tests (#21)
       ```
4. **Merge-Base & Lineage Verification**:
   - Query: `git merge-base origin/main origin/research/port12b-filesystem-u2`
     - Output: `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (Matches `origin/main` HEAD).
   - Query: `git merge-base --is-ancestor origin/main origin/research/port12b-filesystem-u2`
     - Exit code: `0` (`origin/main` is a clean direct ancestor; exactly 1 commit ahead, zero conflicts).

---

## 3. Per-Claim Evaluation Table

The following table evaluates every technical claim, address, instruction, and proof obligation presented in `docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md` against tracked repository evidence on `origin/main`.

| Claim ID | Section / Subject | Claimed Statement in PR #24 | PR Claimed Status | Citations supplied by PR | Reviewer-added citations | Tracked on `origin/main`? | Reviewer Verdict | Reviewer Finding & Epistemic Analysis |
|---|---|---|:---:|---|---|:---:|:---:|---|
| **CLM-01** | §1, §2.1<br>Creator `sub_fc0bd0b4` | Creator `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`) loads name `"InitFileModules"`, prio `0x19`, stack `0x1000`, entry `0xFC0BD071`, calls `0xFC31BBC4` | `STATIC_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:220–228, 402` | **YES** | **`VERIFIED`** | Matches GM1.10C ROM slice `S2A` verbatim (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 220–228, 402`).<br>**Citation support assessment**: Supported by PR-supplied citations (`PORT11A:21, 402` directly establish creator `sub_fc0bd0b4`, task name, priority, stack size, entry pointer, and call; lines `454–456` verify Slice `S2A` bounds). Reviewer-added lines `220–228` confirm specific instruction disassembly. |
| **CLM-02** | §1, §2.1<br>Task Entry Pointer | `task_InitFileModules` Thumb entry pointer is `0xFC0BD071` (instruction address `0xFC0BD070`, loaded from literal pool `[0xFC0BD1A8]`) | `STATIC_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:223, 235, 251, 389` | **YES** | **`VERIFIED`** | Grounded in ROM slice `S2A` (`PORT11A:223, 235, 251, 389`). Entry vector is verified.<br>**Citation support assessment**: Supported by PR-supplied citations (`PORT11A:21`, `:389` [C-07], `:402` directly confirm Thumb entry pointer `0xFC0BD071` and instruction address `0xFC0BD070`; lines `454–456` verify Slice `S2A`). Reviewer-added lines `223, 235, 251` confirm literal pool load and entry instruction. |
| **CLM-04** | §1, §2.1, §2.2<br>Callee 1 Return | Callee 1 `sub_fc0d9ccc` (`0xFC0D9CCC..0xFC0D9CF5`) contains zero conditional branches and returns hardcoded `r0 = 0`; normal return does not prove mount readiness | `STATIC_VERIFIED` (bytes) / `UNKNOWN` (mount) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 284, 390` | **YES** | **`VERIFIED`** | Verbatim match for slice `S2B` epilogue (`0xFC0D9CF2: movs r0, #0; pop {r4, pc}`). `r0 = 0` provides zero dynamic discrimination.<br>**Citation support assessment**: Supported by PR-supplied citations (`PORT11A:21`, `:390` [C-08], and `:458–459` directly prove `sub_fc0d9ccc` contains zero conditional branches, returns constant `r0 = 0`, and cannot establish mount readiness). Reviewer-added line `284` provides exact disassembly. |
| **CLM-05** | §2.1<br>Call Site 1 Address | `task_InitFileModules` calls `sub_fc0d9ccc` at address `0xFC0BD074` | Unlabeled diagram | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:252` | **YES** | **`CONTRADICTED (ADDRESS DISCREPANCY)`** | **Factual error in diagram**: `PORT11A:252` establishes instruction `bl 0xFC0D9CCC` begins at `0xFC0BD072` (`1c f0 2b fe`). Address `0xFC0BD074` is the second halfword of the 32-bit Thumb instruction.<br>**Citation support assessment**: Not supported by PR-supplied citations; `PORT11A:21, 388–390, 402, 454–459` provides no evidence for `0xFC0BD074`, and underlying slice `S2A` ROM evidence (`PORT11A:252`, within lines `454–456`) contradicts `0xFC0BD074`.<br>**Remediation**: PR #24 must correct the call address to `0xFC0BD072`. |
| **CLM-06** | §2.1<br>Call Site 2 Address | `task_InitFileModules` calls `sub_fc0d9cf6` at address `0xFC0BD078` | Unlabeled diagram | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:254, 259` | **YES** | **`CONTRADICTED (ADDRESS DISCREPANCY)`** | **Factual error in diagram**: Address `0xFC0BD078` holds `movw r5, #0x5006` (`PORT11A:254`). Callee 2 `bl 0xFC0D9CF6` is actually invoked at `0xFC0BD086` (`PORT11A:259`).<br>**Citation support assessment**: Not supported by PR-supplied citations; `PORT11A:21, 388–390, 402, 454–459` provides no evidence for `0xFC0BD078`, and underlying slice `S2A` ROM evidence (`PORT11A:254, 259`, within lines `454–456`) contradicts `0xFC0BD078`.<br>**Remediation**: PR #24 must correct the call address to `0xFC0BD086`. |
| **CLM-07** | §2.1<br>Task Completion Address | `task_InitFileModules` completion/exit occurs at address `0xFC0BD07C` | Unlabeled diagram | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:255, 265` | **YES** | **`CONTRADICTED (ADDRESS DISCREPANCY)`** | **Factual error in diagram**: Address `0xFC0BD07C` is `beq 0xFC0BD086` (`PORT11A:255`). Function epilogue/tail branch occurs at `0xFC0BD096` (`b.w 0xFC35B93C`) and `0xFC0BD09A` (`pop {r4, r5, r6, pc}`).<br>**Citation support assessment**: Not supported by PR-supplied citations; `PORT11A:21, 388–390, 402, 454–459` provides no evidence for `0xFC0BD07C`, and underlying slice `S2A` ROM evidence (`PORT11A:255, 265`, within lines `454–456`) contradicts `0xFC0BD07C`.<br>**Remediation**: PR #24 must correct the completion address to `0xFC0BD096` / `0xFC0BD09A`. |
| **CLM-07A** | §2.1<br>Diagram: Callee 1 Storage Init Role | Diagram asserts Callee 1 (`sub_fc0d9ccc`) performs "Lower-level storage/host controller init" | Unlabeled diagram / stated as fact | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289, 406` | **NO** | **`UNKNOWN / UNSUPPORTED`** | **PR #24 overstates Callee 1 functionality**: Tracked ROM evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289, 406` leaves what the nested callees initialize strictly `UNKNOWN` (all nested callees lie outside slice `S2B`). Asserting that Callee 1 performs storage or host controller initialization is unestablished in Phase 0.<br>**Citation support assessment**: Not supported by PR-supplied citations; `PORT11A:21, 388–390, 402, 454–459` establishes only subroutine bounds and constant `r0 = 0` return, not storage or host controller initialization semantics.<br>**Remediation**: PR #24 must remove this or mark it UNKNOWN. |
| **CLM-07B** | §2.1<br>Diagram: `task_Startup` Invocation Edge | Diagram shows `task_Startup` calling/creating the `InitFileModules` creator (`sub_fc0bd0b4`) | Unlabeled diagram / stated as fact | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:81, 407` | **NO** | **`UNKNOWN / UNSUPPORTED`** | **PR #24 asserts unverified task creation edge**: Tracked evidence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:81, 407` leaves startup reachability strictly `UNKNOWN`. Whether `task_Startup` creates `sub_fc0bd0b4` directly or through intervening task dispatchers is unproven in Phase 0.<br>**Citation support assessment**: Not supported by PR-supplied citations; none of `PORT11A:21, 388–390, 402, 454–459` demonstrates startup reachability, and line `407` explicitly leaves the caller graph of `sub_fc0bd0b4` as `UNKNOWN`.<br>**Remediation**: PR #24 must remove the edge or mark it UNKNOWN. |
| **CLM-08A** | §2.1, §2.2<br>Callee 2 Call Order | Callee 2 `sub_fc0d9cf6` is invoked sequentially after `sub_fc0d9ccc`; cannot prove FAT volume mounted or handles writable | `STATIC_VERIFIED` (call) / `UNKNOWN` (mount) | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:252, 259, 285–289` | **YES** | **`VERIFIED`** | Sound architectural distinction; callee 2 invocation at `0xFC0BD086` following `sub_fc0d9ccc` is verified in ROM slice `S2A` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:252, 259`).<br>**Citation support assessment**: Supported by PR-supplied citations (`PORT11A:402` and `:454–459` document direct callees `sub_fc0d9ccc` and `sub_fc0d9cf6` in task body); reviewer-added lines `252, 259` confirm sequential invocation. |
| **CLM-08B** | §2.1, §2.2<br>Callee 2 Functional Role | Callee 2 `sub_fc0d9cf6` performs "Mount completion / event dispatch" and "Dispatches mount sequence and notifies system" | `STATIC_VERIFIED` / stated as fact | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388–390, 402, 454–459` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:247–267, 285–289` | **NO** | **`UNKNOWN / OVERSTATED`** | **PR #24 overstates callee functionality**: In GM1.10C ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:247–267, 285–289` §4.3), the visible `0x5006` event dispatch calls (`bl 0xFC35B93C` at `0xFC0BD082` and `b.w 0xFC35B93C` at `0xFC0BD096`) are located within `task_InitFileModules` itself (`PORT11A:254–265`), not inside `sub_fc0d9cf6`. Furthermore, all nested callees of `sub_fc0d9cf6` (`0xFC37AD52`, `0xFC0F9BA4`, `0xFC35FAAC`, `0xFC2DD73A`, `0xFC3138CC`, `0xFC35F9A8`, `0xFC2DD7A4`) lie outside slice `S2B` and their behavior remains explicitly classified as **`UNKNOWN`** (`PORT11A:286, 289`). Asserting that `sub_fc0d9cf6` dispatches events or the mount sequence is unestablished in Phase 0.<br>**Citation support assessment**: Not supported by PR-supplied citations; `PORT11A:21, 388–390, 402, 454–459` lists `sub_fc0d9cf6` as a callee but does not support that it dispatches events or mount sequences.<br>**Remediation**: PR #24 must qualify or correct these functional statements. |
| **CLM-09A** | §1, §2.2, §3 (Obl. 2)<br>Event `0x5006` Insufficiency | Event `0x5006` alone is insufficient to establish filesystem mount readiness or authorize synchronous file I/O | `INSUFFICIENT` | none | `tools/port9a_runtime_lifecycle.py:301, 678–679, 703–705` | **YES** | **`VERIFIED`** | Explicitly codified in `tools/port9a_runtime_lifecycle.py:301` and lines 678–679: posting UI event `0x5006` does not advance state to `mount_observed` or `fs_io_ready`. |
| **CLM-09B** | §1, §2.2, §3 (Obl. 2)<br>Event `0x5006` Dispatch Semantics | Event `0x5006` is an asynchronous UI notification message dispatched via DryOS message queues | `INFERRED` / stated as fact | none | `docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265` | **NO** | **`UNKNOWN / OVERSTATED`** | **PR #24 overstates dispatch mechanism**: In `docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265`, the target subroutine `0xFC35B93C` at `0xFC0BD082` and `0xFC0BD096` lies outside slice `S2A` and is explicitly classified as **`UNKNOWN`**. Whether `0xFC35B93C` enqueues to an asynchronous message queue, executes synchronously, or accesses hardware registers is unproven in Phase 0.<br>**Remediation**: PR #24 must de-escalate claims of asynchronous message queuing to unverified hypothesis. |
| **CLM-10** | §3 (Obl. 1)<br>Historical Deficiency | Ranma inserted `bl core_spytask_can_start` after `sub_fc0d9cf6` without evaluating return registers | `HISTORICALLY REPORTED` | `platform/g3x/sub/110e/boot.c:493–515` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` (`P:1769–1795`), `docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94` | **NO (UNTRACKED)** | **`VERIFIED (WITH UNTRACKED CITATION)`** | Statement is technically accurate per `PORT5B:190` (`P:1769–1795`), but cited path `sub/110e/boot.c` is untracked on `origin/main`.<br>**Remediation**: PR #24 must update citation to reference tracked secondary evidence in `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` and `docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`. |
| **CLM-11** | §3 (Obl. 2)<br>Event Decoupling Bound | Formal bound: $\text{PostEvent}(0x5006) \not\implies \text{FilesystemReady}(\text{SD0})$ | `FORMAL OBLIGATION` | none | `tools/port9a_runtime_lifecycle.py:301` | **YES** | **`VERIFIED (INSUFFICIENCY) / UNKNOWN (DISPATCH MECHANISM)`** | The negative implication is verified: event observation does not prove filesystem readiness (`port9a:301`). However, naming the mechanism `PostEvent` assumes eventproc/queue dispatch semantics that remain `UNKNOWN`. |
| **CLM-12** | §3 (Obl. 3)<br>Mount-Readiness Storage Verification | Mount readiness requires idle DMA, parsed FAT32 BPB, verified root cluster, and allocatable file descriptor from pool | `FORMAL OBLIGATION` | none | `tools/port9a_runtime_lifecycle.py:300–303` | **NO (PROPOSED NOVEL SPECIFICATION)** | **`PROPOSED (UNTRACKED EXTENSION) / GAP NOTED`** | **Untracked criteria & missing obligation**: These four items are proposed technical criteria introduced by PR #24; they do not match `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` (`tools/port9a_runtime_lifecycle.py:300–303`). Furthermore, PR #24 **lacks** an explicit obligation for verified non-destructive open/read capability on the mounted volume matching `port9a_runtime_lifecycle.py:302–303`.<br>**Remediation**: PR #24 must qualify these criteria as novel proposals and add the missing open/read capability obligation. |
| **CLM-13** | §3 (Obl. 4)<br>Generation Invalidation | Latch state must be monotonically bound to `boot_generation` token: $\langle \text{Ready}, \text{GenerationID} \rangle$ | `ARCHITECTURAL INVARIANT` | none | `tools/port9a_runtime_lifecycle.py:343–366, 394–400` | **YES** | **`VERIFIED`** | Directly aligns with `RuntimeLifecycle` generation invalidation and reset logic (`reset` at `tools/port9a_runtime_lifecycle.py:343–366` and `_check_generation` at `tools/port9a_runtime_lifecycle.py:394–400`). |
| **CLM-14A** | §3 (Obl. 5)<br>Warm-Restart Precondition Proof Obligation | Storage and SD-host preconditions must be resolved before filesystem readiness can be promoted (`warm_restart_safe`) | `FORMAL OBLIGATION` | none | `tools/port9a_runtime_lifecycle.py:256, 274–276, 287, 304–306, 767–805`, `tools/port9b_runtime_contract.py:79–80` | **YES** | **`VERIFIED`** | Explicitly codified in `tools/port9a_runtime_lifecycle.py:256, 274–276, 287, 304–306, 767–805` (the 6th promotion stage `warm_restart_safe` requiring resolution of SD host/card state preconditions P11, P12, P13, P15) and `tools/port9b_runtime_contract.py:79–80` (Fact U2 defining `init_file_modules_entry_verified` as encompassing warm-restart storage safety). |
| **CLM-14B** | §3 (Obl. 5)<br>Hardware Bus State Persistence | SD card hardware retains its bus/card-host configuration across warm restart unless explicitly power-cycled | Stated as fact | none | `docs/PORT3C_SD_DRIVE_STATE.md`, `docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29` (§1) | **PARTIAL (INFERRED)** | **`INFERRED / PLAUSIBLE (NOT VERIFIED)`** | In `docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29` (§1.3–1.4, §2), the audit confirms that drive A remains mounted at loader entry and hardware state is not reset by RAM copies, but host configuration persistence is explicitly classified as plausible (**P**) rather than verified (**V**), and the SD effects of intervening routines (`0xFC41870C` and `[0x4000]`) remain strictly **`UNKNOWN`** (`docs/RESTART_SD_HOST_AUDIT.md:16, 45`).<br>**Remediation**: PR #24 must qualify this claim as inferred/plausible rather than verified fact. |
| **CLM-14C** | §3 (Obl. 5)<br>Reset Ownership Attribution | `InitFileModules` is the mandatory routine that must reset or re-initialize the SD host controller without bus lockup | `FORMAL OBLIGATION` / asserted role | none | `docs/RESTART_SD_HOST_AUDIT.md:54–68` (§6), `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289` | **NO** | **`UNKNOWN / NOT ESTABLISHED`** | While the lifecycle contract (`tools/port9a_runtime_lifecycle.py:304–306`) mandates resolution of SD host/card preconditions, the contract does not designate `InitFileModules` as the reset owner. In fact, `docs/RESTART_SD_HOST_AUDIT.md:54–68` (§6) identifies `SD1stInit` (`0x010E17A5`) created by `StartDiskboot` as issuing CMD0 (`0x010EE7D2`), while `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289` leaves the actual role of `InitFileModules` callees regarding SD reset as **`UNKNOWN`**.<br>**Remediation**: PR #24 must qualify or decouple this ownership attribution. |
| **CLM-15** | §1, §6<br>Governance Invariant | `GM110C_PRECONDITIONS.init_file_modules_entry_verified = False` remains strictly unchanged; zero hooks added | `VERIFIED` | none | `tools/port9a_runtime_lifecycle.py:99–105`, `tools/port9b_runtime_contract.py:79` | **YES** | **`VERIFIED`** | Invariant confirmed in default `GM110C_PRECONDITIONS` (`tools/port9a_runtime_lifecycle.py:99–105`), runtime contract (`tools/port9b_runtime_contract.py:79`), and test suite. |
| **CLM-16** | §5<br>Evidence Checklist | Checklists E-01..E-05 define bounded research requirements for future authorized investigation | `FORMAL SPECIFICATION` | none | none (Proposal for future research) | **YES** | **`VERIFIED`** | Appropriately scopes future work to non-destructive static disassembly and data structure identification. |

### 3.1 Reviewer Background Evidence (Not Claimed by PR #24)

The following finding was audited during review but is **not** claimed or discussed in PR #24 (`docs/PORT12B_FILESYSTEM_U2_OBLIGATIONS.md`):

- **Refutation of Historical Entry Address `0xFC0BD049`**:
  - **Finding**: Competing historical entry address `0xFC0BD049` (Ranma `-0x28` offset relative to `0xFC0BD071`) is refuted by literal word `0xFC66BBB0` at `0xFC0BD048` logged outside slice `S2A` in Step 204 (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:65, 87, 388` §2.4, §4.2; `S2A` is defined at line 65 as `0xFC0BD070..0xFC0BD1BB`), with creator `sub_fc0bd0b4` passing `0xFC0BD071` (`PORT11A:21, 389, 402`).
  - **Provenance**: This refutation and the `CONTRADICTED` status derive strictly from `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 65, 87, 388` (logged outside `S2A` in Step 204). PR #24 does not make this claim, does not contain the `0xFC0BD049` refutation, does not use the `CONTRADICTED` label for this address, and contains no section §4.2. This evidence is recorded here solely as reviewer background context explaining why creator `sub_fc0bd0b4` passes `0xFC0BD071` as the task entry pointer.

---

## 4. Audit on Separation of Static Entry vs. Runtime Filesystem Readiness

A core mandate of this review is to verify that Draft PR #24 strictly separates:
- **(a) Static ROM evidence** for the `InitFileModules` task Thumb entry `0xFC0BD071`, and
- **(b) Runtime filesystem readiness**, which that static evidence does not establish.

### 4.1 Detailed Evaluation
Draft PR #24 demonstrates compliance with this separation in its core architecture. It does **not** treat static entry-point evidence as proof of runtime readiness:

1. **Explicit Conceptual Decoupling**:
   - In Section 1, PR #24 explicitly labels entry `0xFC0BD071` as `STATIC_VERIFIED`, while labeling dynamic mount readiness as `UNKNOWN / NOT ESTABLISHED`.
   - In Section 2.2, PR #24 builds a comparative matrix showing that observing `0xFC0BD071` only proves the initial execution vector of the task, but *"Does not prove that hardware SD controller is powered, clocked, or initialized."*
2. **Analysis of Callee Epilogue (`sub_fc0d9ccc`)**:
   - PR #24 incorporates the static finding from ROM slice `S2B` that `sub_fc0d9ccc` contains no conditional branches and always exits via `movs r0, #0; pop {r4, pc}`.
   - PR #24 correctly identifies that because `r0 = 0` is hardcoded on normal return, checking `r4 == 0` after `sub_fc0d9ccc` yields a constant `0` regardless of whether an SD card is present, formatted, or corrupted.
3. **Decoupling of Event `0x5006` Insufficiency vs. Overstated Dispatch Semantics**:
   - PR #24 correctly identifies that observing or posting event `0x5006` cannot serve as a gate for filesystem I/O operations (`Fopen_Fut`, `Fread_Fut`, `Fwrite_Fut`), adhering to `tools/port9a_runtime_lifecycle.py:301, 678–679`.
   - **Reviewer Finding on Overstated Dispatch Semantics**: However, PR #24 overstates the reverse-engineering evidence by repeatedly asserting that event `0x5006` is dispatched asynchronously via DryOS message queues. In verified GM1.10C ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265`), calls to `0xFC35B93C` with parameter `0x5006` lie outside slice `S2A` and are explicitly classified as `UNKNOWN`. Whether DryOS dispatches `0x5006` via an asynchronous task queue or a synchronous handler table is unproven in Phase 0. While the *insufficiency* of event `0x5006` for filesystem readiness is verified, PR #24's claims regarding its *internal queuing semantics* are unverified.
4. **Offline Contract Enforcement**:
   - PR #24 provides test `test_constant_zero_return_cannot_grant_fs_io_readiness` and test `test_event_5006_alone_does_not_open_fs_io_gate`, verifying that neither a zero return code nor an event flag can advance the state machine to `FS_IO_READY`.

---

## 5. Consistency Check with Core Runtime Lifecycle & Contracts

### 5.1 Consistency with `tools/port9a_runtime_lifecycle.py`
PR #24 aligns with the runtime lifecycle model implemented in `tools/port9a_runtime_lifecycle.py` in several key areas:
- **Preconditions**: It preserves `GM110C_PRECONDITIONS.init_file_modules_entry_verified = False` (tested in `test_gm110c_preconditions_invariant`).
- **Static Evidence Profile**: It verifies that `GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry` is `STATIC_VERIFIED`, while `u2_sd_fat_mount_readiness` remains strictly `UNKNOWN` (tested in `test_static_evidence_profile_separation`).
- **State Transition Guardrails**: It models adversarial sequences showing that out-of-order returns, stale `boot_generation` tokens, and latched CPU faults immediately halt progression and fail closed.

**Promotion Requirements Discrepancy & Gap**:
- `tools/port9a_runtime_lifecycle.py:293–306` defines `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` across six formal stages:
  - `mount_observed` (line 300–301): *"Independent kernel/storage state proof that FAT volume mount succeeded (event 0x5006 alone is insufficient)"*
  - `fs_io_ready` (line 302–303): *"Verified non-destructive file open/read capability on mounted volume without contention or timeout"*
- In Section 3 (Obligation 3), PR #24 proposes four low-level hardware/kernel internals: idle DMA, FAT32 BPB parsing, root-cluster verification, and descriptor allocation. These four items do **not** match the tracked wording of `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS`; they represent proposed additional requirements from PR #24.
- Crucially, PR #24 **lacks** an explicit obligation for verified non-destructive file open/read capability on the mounted volume matching `tools/port9a_runtime_lifecycle.py:302–303`. While PR #24 mentions `Fopen_Fut`, `Fread_Fut`, and `Fwrite_Fut` parenthetically, its formal Obligation 3 omits this required functional capability check.

### 5.2 Consistency with `tools/port9b_runtime_contract.py` (I2 Contract)
PR #24 adheres strictly to the offline runtime contract:
- **`UNVERIFIED_RUNTIME_FACTS` (Fact U2)**: `port9b_runtime_contract.py:79–80` registers U2 as `init_file_modules_entry_verified` with the description: *"InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety"*. PR #24 respects this exact definition.
- **Contract `C3.gate`**: Verifies that activation markers for `InitFileModules` (`REPLACEMENTS["InitFileModules"]` or `core_spytask_can_start`) are absent in source unless explicitly allowed by the model. PR #24 introduces zero activation markers.
- **Contract `C5.U2`**: Ensures runtime facts remain unverified and address-free. PR #24 leaves the registry clean and introduces no addresses into runtime contracts.

### 5.3 Consistency with `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md` (U2)
In `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md`:
- Interface I2 (*InitFileModules readiness gate*) was originally characterized as *"Modelled: latched, needs explicit success, fails closed; Name string only; task entry UNKNOWN"*.
- In PORT-11A, static ROM inspection resolved the entry address to `0xFC0BD071`, but confirmed mount readiness remained unestablished.
- PR #24 operationalizes the findings of PORT-11A into the formal obligations necessary to eventually resolve U2 without violating the Phase 0 safety boundary.

---

## 6. Test Suite Execution & Analysis

### 6.1 Execution Environment & Harness Details
- **Test File**: `tests/test_port12b_filesystem_u2.py` (pinned to target commit `6fb7622aee7915ff2d3d39563a45ef3310ae31b3`)
- **Execution Workspace**: Materialized scratch checkout outside task worktree: `/tmp/scratch_pr24_head`
- **Target SHA Materialization**: Extracted directly from git archive of `6fb7622aee7915ff2d3d39563a45ef3310ae31b3`
- **Tree Verification**:
  - `tests/test_port12b_filesystem_u2.py` SHA256: `df044ee73b94393c7c0abfa11513176baf90a6121ac663de9e5634448d53d82a` (matches git blob `8cdb9afa1b43f6f5f4fa423056b31bd014233c61`)
  - `tools/port9a_runtime_lifecycle.py` SHA256: `77da2bfa5fb018590ec60215afc440b48d2fe1d618e6ce121f4253d21b667d93` (matches git blob `d95c67aeadf77f0b9385ab690a8e579e4c4f1cd3`)
  - The test file was completely unmodified and imported `tools.port9a_runtime_lifecycle` directly from the pinned checkout at `/tmp/scratch_pr24_head`.
- **Execution Command**:
  ```sh
  cd /tmp/scratch_pr24_head && python3 -B -m unittest -v tests/test_port12b_filesystem_u2.py
  ```
- **Execution Date**: 2026-10-28
- **Runner**: Python 3.14.4 standard library `unittest`
- **Execution Counts**:
  - **Ran**: 8 tests
  - **Passed**: 8 tests
  - **Failed**: 0
  - **Errors**: 0
  - **Skipped**: 0
- **Validation**: Verified in pinned scratch environment (8 ran, 8 passed) and confirmed by AgentBridge automated test validation.

### 6.2 Test Results Ledger

| Test Case Name | Target Behavior / Invariant Tested | Result | Execution Time |
|---|---|:---:|---:|
| `test_constant_zero_return_cannot_grant_fs_io_readiness` | Asserts normal return ($r_0=0$) of `sub_fc0d9ccc` advances only to `INIT_RETURNED_NORMALLY`, never to `FS_IO_READY` or `WARM_RESTART_SAFE` | **PASS** | <0.001s |
| `test_event_5006_alone_does_not_open_fs_io_gate` | Asserts UI notification event `0x5006` cannot open `fs_io_ready` without independent dynamic storage proof | **PASS** | <0.001s |
| `test_fault_latched_blocks_subsequent_stages` | Asserts that a latched CPU fault causes immediate transition to `FAILED` and blocks gate progression | **PASS** | <0.001s |
| `test_generation_mismatch_fails_closed` | Asserts that a stale `boot_generation` token (e.g. from prior warm restart) is rejected and cannot advance stage | **PASS** | <0.001s |
| `test_gm110c_preconditions_invariant` | Asserts `GM110C_PRECONDITIONS.init_file_modules_entry_verified` remains strictly `False` in Phase 0 | **PASS** | <0.001s |
| `test_out_of_order_init_returned_fails_closed` | Asserts that invoking `init_file_modules_returned` before `task_started` fails the filesystem | **PASS** | <0.001s |
| `test_six_stage_promotion_contract_completeness` | Asserts all six formal promotion stages are explicitly defined in `FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS` | **PASS** | <0.001s |
| `test_static_evidence_profile_separation` | Asserts static entry is `STATIC_VERIFIED` while dynamic mount readiness is strictly `UNKNOWN` | **PASS** | <0.001s |
| **Total Suite Metrics** | **8 tests executed** | **8 PASS, 0 FAIL, 0 ERR, 0 SKIP** | **0.001s** |

### 6.3 Test Rigor & Epistemic Evaluation
In contrast to PR #23 (where tests asserted synthetic mock strings and circular address contiguity), PR #24's test suite exhibits solid engineering rigor:
1. It validates genuine adversarial state sequences against the live state machine `tools.port9a_runtime_lifecycle.RuntimeLifecycle`.
2. It tests negative failure paths: out-of-order execution, generation token mismatch, latched fault propagation, and constant-zero return suppression.
3. It guarantees that no future developer can casually flip `init_file_modules_entry_verified` or assume that a successful return from `sub_fc0d9ccc` authorizes filesystem I/O.
4. **Test Provenance Note**: The test suite was executed unmodified against a pristine tree pinned to PR head SHA `6fb7622aee7915ff2d3d39563a45ef3310ae31b3` in `/tmp/scratch_pr24_head` (8 ran, 8 passed; also confirmed by AgentBridge automated test validation). The earlier preliminary run (which modified `REPO_ROOT` to run from the local worktree) is superseded by this verified pinned execution.

---

## 7. Synthesis & Final Recommendation

### Formal Recommendation: **`needs-changes`**

Draft PR #24 represents methodologically sound engineering work that significantly advances the project's safety posture. It properly formalizes the limits of static ROM analysis and creates robust negative tests against premature filesystem authorization. 

However, because project standards require absolute accuracy in ROM instruction transcriptions, strict citation integrity, and precise alignment with tracked lifecycle contracts, the PR **cannot be merged in its current state** until the following remediation items are addressed.

### Required Remediation Items for PR Author
1. **Correct Instruction Addresses in Section 2.1 Call Tree Diagram**:
   - Update `0xFC0BD074: bl 0xFC0D9CCC` to **`0xFC0BD072: bl 0xFC0D9CCC`** (instruction start address in ROM slice `S2A`; `PORT11A:252`).
   - Update `0xFC0BD078: bl 0xFC0D9CF6` to **`0xFC0BD086: bl 0xFC0D9CF6`** (at `0xFC0BD078`, the instruction is `movw r5, #0x5006`; `PORT11A:254, 259`).
   - Update `0xFC0BD07C: ... Task completion / exit` to clarify that `0xFC0BD07C` is `beq 0xFC0BD086`, and function completion/epilogue occurs at **`0xFC0BD096`** (`b.w 0xFC35B93C`) and **`0xFC0BD09A`** (`pop {r4, r5, r6, pc}`).
2. **De-escalate Overstated Event `0x5006` Dispatch Semantics**:
   - In §1, §2.2, and §3 (Obligation 2), remove claims asserting as fact that event `0x5006` is dispatched asynchronously via DryOS message queues.
   - Ground the obligation strictly in what is verified: posting or observing event `0x5006` is **insufficient** to establish filesystem readiness (`tools/port9a_runtime_lifecycle.py:301, 678–679`).
   - Acknowledge that the target function `0xFC35B93C` at `0xFC0BD082` and `0xFC0BD096` lies outside verified slice `S2A` and remains **`UNKNOWN`** per `docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265`.
3. **Align Obligation 3 with Tracked Lifecycle Requirements & Add Non-Destructive Open/Read**:
   - In §3 (Obligation 3), clearly distinguish the four proposed internal storage driver criteria (idle DMA, BPB parsing, root-cluster verification, descriptor pool allocation) as **proposed novel extensions** from PR #24 rather than existing tracked project requirements.
   - Explicitly add the missing tracked requirement from `tools/port9a_runtime_lifecycle.py:302–303`: **verified non-destructive file open/read capability on the mounted volume without contention or timeout** for the `fs_io_ready` condition.
4. **Contextualize Untracked Historical Citation**:
   - In Section 3 (Obligation 1), replace or qualify the citation to `platform/g3x/sub/110e/boot.c:493–515` by citing tracked repository evidence: `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:190` (patch lines `P:1769–1795`) and `docs/PORT5A_RANMA_PORT_RECOVERY.md:93–94`.
5. **De-escalate Callee 2 (`sub_fc0d9cf6`) Functional Assertions**:
   - In §2.1 and §2.2, correct or qualify functional claims asserting that `sub_fc0d9cf6` performs "Mount completion / event dispatch" or "Dispatches mount sequence and notifies system".
   - Ground the description strictly in tracked ROM evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:247–267, 285–289` §4.3): visible `0x5006` event dispatch calls reside directly within `task_InitFileModules` (`PORT11A:254–265`), while the internal behavior of `sub_fc0d9cf6`'s nested callees remains explicitly **`UNKNOWN`**.
6. **Qualify Warm-Restart Host State Persistence and Decouple Reset Ownership**:
   - In §3 (Obligation 5), qualify hardware bus/card-host configuration retention across warm restart as **`INFERRED / PLAUSIBLE`** rather than verified fact, citing `docs/RESTART_SD_HOST_AUDIT.md:11–18, 28–29` (§1).
   - Maintain the verified proof obligation that storage/SD-host preconditions must be resolved prior to promoting filesystem readiness (`tools/port9a_runtime_lifecycle.py:256, 304–306, 767–805`, `tools/port9b_runtime_contract.py:79–80`), but decouple it from the unverified assertion that `InitFileModules` is the mandatory reset owner (`UNKNOWN / NOT ESTABLISHED`).
7. **Remove or Mark UNKNOWN Callee 1 Storage Init Semantics in Diagram**:
   - In Section 2.1 call sequence diagram, the diagram asserts that Callee 1 (`sub_fc0d9ccc`) performs "Lower-level storage/host controller init". Label: **`UNKNOWN / UNSUPPORTED`**; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:289` leaves what the nested callees initialize strictly **`UNKNOWN`**.
   - **Remediation**: PR #24 must remove this description or mark it **`UNKNOWN`**.
8. **Remove or Mark UNKNOWN `task_Startup` Invocation Edge in Diagram**:
   - In Section 2.1 call sequence diagram, the diagram depicts `task_Startup` calling/creating the `InitFileModules` creator (`sub_fc0bd0b4`). Label: **`UNKNOWN / UNSUPPORTED`**; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:407` leaves startup reachability strictly **`UNKNOWN`**.
   - **Remediation**: PR #24 must remove the edge or mark it **`UNKNOWN`**.
