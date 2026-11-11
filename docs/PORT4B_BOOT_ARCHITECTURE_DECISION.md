# PORT-4B — Independent boot architecture decision review

Date/retrieval date: **2026-10-25 (Asia/Seoul)**. Reviewer: Codex.
Repository: [s4urj3ng/g3x-lite](https://github.com/s4urj3ng/g3x-lite). Review-start HEAD: `4577fb6ae74057571da923b51f61fbe0724a1595`, with existing dirty/untracked material. The source register identifies the actual reviewed documents.

**Recommendation: preserve A as a blocked reference architecture; prioritize a bounded documentation review of C; retain B as an unproven alternative. No architecture is selected for implementation or hardware execution.**

Continuing A as the **only** plausible architecture is not justified by the current evidence. Its concrete prototype and documented heap reservation justify preserving it, but PORT-4A did not establish its critical interrupt-reset guarantee. C deserves further offline investigation because the project reports native execution and return inside the running GM1.10C environment. That evidence supports a primitive, not resident-task feasibility or a replacement for the full CHDK port.

**Overall feasibility/readiness: INSUFFICIENT EVIDENCE / NOT READY for all three complete architectures.**

## 1. Scope and comparison boundary

This is a documentation-only decision review. No ROM or executable artifacts were read for analysis; no new disassembly/tracing, IRQ caller enumeration, SD register-write enumeration, classifier retry, executable/test modification, build, test, emulator, camera/SD operation, MMIO probe, deployment, commit, push, or PR action occurred. Outputs are this report and the required state/handoff additions. Historical observations and test results are attributed to their documents, not reproduced here.

The options are distinguished by the integration boundary, not by an invented implementation:

| Option | Meaning in this review | What is not established by the name |
|---|---|---|
| **A — CHDK-style warm restart** | The existing documented path recopies OS state, clears Canon BSS, shifts the heap and restarts DryOS before attempting stock continuation. | Repeated initialization does not establish hardware normalization or successful continuation. |
| **B — Non-restart loader / RAM coexistence** | A loader and any resident native component would coexist with the original OS without recreating it. | No valid load location, reservation, relocation, handback convention or working loader is assumed. Removing the restart from the current loader does not define a valid B. |
| **C — Task-based integration without full DryOS restart** | Native integration would use the existing OS execution/task environment, with ownership and lifetime compatible with that OS. | No task-creation method, hook, scheduler parameters, resident location or persistence guarantee is assumed. Existing synchronous native calls are evidence relevant to C, not examples of a proved independent resident task. |

B and C overlap: a resident task still needs RAM coexistence, and a non-restart loader might eventually use tasks. They are not three mutually exclusive hardware platforms. Comparing them separately exposes B's loader/handoff obligations and C's task/lifetime obligations; it does not eliminate either set of obligations from a combined design.

The dossier contains goals ranging from limited native/UI functions to a full resident CHDK port. These are different capability requirements. No evidence establishes feature parity between C and A, and this recommendation does not silently reduce the project goal or claim that a small native payload replaces CHDK.

Classification:

- **VERIFIED (documented):** the inspected document records the stated static result or observation; this review does not thereby independently verify the underlying hardware event.
- **PLAUSIBLE:** an architectural direction has a relevant foothold, with important premises unproved.
- **UNKNOWN:** feasibility or a required premise is not established.
- **CONTRADICTED:** a particular claimed guarantee/layout is inconsistent with identified evidence. A rejected instance does not reject its entire architecture family.

## 2. Evidence that changes the decision

| ID | Exact source reference | What the evidence supports | What it does not establish |
|---|---|---|---|
| E1 | [PORT-3C §§1–2, especially P07/P11–P18/P20](/Users/avp/Project/g3x-lite/docs/PORT3C_RESTART_READINESS_MATRIX.md:18); [independent review §5](/Users/avp/Project/g3x-lite/docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:84). | A has a documented memory strategy and static prototype, but handler coverage, retained IRQ state, SD recovery and fresh downstream continuation remain unresolved. | A is neither proved safe nor proved inevitably failing. Static checks cannot discharge its hardware premises. |
| E2 | [PORT-4A §4](/Users/avp/Project/g3x-lite/docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md:90). | External documentation adds support for the current-ID read at `0xD4011000`. The bank and auxiliary-register initialization/reset guarantee remains UNKNOWN. | Identifying an interrupt ID register does not prove a safe restart transition. Missing documentation does not prove no safe transition exists. |
| E3 | [PORT-2C §2.2](/Users/avp/Project/g3x-lite/docs/CHDK_PORT2C_ARCHITECTURE_DECISION.md:43); [memory dossier §§2.3/3.2](/Users/avp/Project/g3x-lite/docs/CHDK_G3X_MEMORY_OWNERSHIP.md:56). | The documented fixed core beginning at `0x003489B4` overlaps the unshifted stock heap. An unreserved core there has no ownership exclusion from the allocator. | It does not prove all non-restart placements, allocation-backed lifetimes, or task-based integrations impossible. Exact first-allocation crash timing is not established by interval overlap alone. |
| E4 | [PORT-2C §2.2 loader entry](/Users/avp/Project/g3x-lite/docs/CHDK_PORT2C_ARCHITECTURE_DECISION.md:45); [memory dossier §2.1](/Users/avp/Project/g3x-lite/docs/CHDK_G3X_MEMORY_OWNERSHIP.md:36). | The documented load base `0x8000` lies in the region the dossier identifies as Canon-owned initialized low RAM. This creates an additional compatibility obligation for reusing the current loading path without restart. | The documents do not establish that a return is legal, which exact live data would be affected, or that every possible non-restart loader has this problem. No new live-memory/tracing claim is made. |
| E5 | [BOOT-001B-DIAG §§1–3.1](/Users/avp/Project/g3x-lite/docs/BOOT001B_DIAG_HARDWARE_RESULT.md:12), dated 2026-10-17. | Owner-reported GM1.10C execution of a 52-byte native payload from dynamically allocated DRAM, an LCD API result and return to the caller. The report identifies the package and records normal subsequent operation. | This review did not witness or reproduce the result; the report says there is no external photo/video. The result does not establish a persistent task, a large core, a DISKBOOT handback, or behavior under load. |
| E6 | [BOOT-001B-DIAG §4](/Users/avp/Project/g3x-lite/docs/BOOT001B_DIAG_HARDWARE_RESULT.md:101). | The same hardware-result report explicitly excludes arbitrary APIs, task creation, long-session stability and universal recovery guarantees. | E5 cannot be promoted into C being implemented, safe, or equivalent to A. |
| E7 | [native-runtime dossier §4.2](/Users/avp/Project/g3x-lite/docs/PHASE4_NATIVE_RUNTIME_FEASIBILITY.md:159), plus its [executive claims](/Users/avp/Project/g3x-lite/docs/PHASE4_NATIVE_RUNTIME_FEASIBILITY.md:15). | Independent custom-task persistence is labeled **INFERRED** in its table. The stronger following sentence that it will persist is a hypothesis requiring evidence. | The dossier's FEASIBLE label, cache-risk absolutes, topology claim and blanket power-cycle reversibility statement are not adopted as guarantees. Later evidence limits recovery and architecture assumptions. |
| E8 | [independent review E17–E19 and §4](/Users/avp/Project/g3x-lite/docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:50); [PORT-4A §5](/Users/avp/Project/g3x-lite/docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md:106). | A's stage 3 is pre-branch; its fixed sentinel does not prove fresh downstream continuation. PORT-4A documents an ARMv7-R profile inconsistent with the earlier Cortex-A9 annotation. | Neither a witness field, a generic Cortex-A/GIC assumption nor agreement among reports supplies missing runtime evidence. |

The memory documents use different upper boundaries for the system pool/subpool (`0x0060E000` versus `0x00600014`) and different candidate/prototype end addresses. This review does not resolve or combine these into a new memory map. The specific overlap finding in E3 holds under either recorded upper boundary; no free region or available capacity is inferred from it.

## 3. Comparative decision matrix

Entries for B/C describe **requirements and conditional architectural reasoning**, not demonstrated properties of an existing implementation. References E1–E8 above bound the claims.

| Criterion | A — Existing warm restart | B — Non-restart loader / RAM coexistence | C — Task-based integration without full restart |
|---|---|---|---|
| **Supporting feasibility evidence** | Most concrete static prototype and review history; documented shifted heap and loader/core separation. Sister-port precedent is suggestive, not G3 X validation. | The E3 rejection is specific to an unreserved fixed layout. E5 shows some native RAM execution alongside Canon is reported possible, but not from the DISKBOOT loader. | E5 is a same-model native-call-and-return foothold within the original OS. No documented resident-task result is supplied; E6 expressly limits the observation. |
| **Memory/heap compatibility** | Recorded heap shift excludes the core from the specified allocator region if the setup is executed as documented. This is not a claim that every writer/region is harmless. Candidate and prototype layouts must stay distinct. | Original heap and live OS allocations remain relevant. Needs documented ownership, executable/cache compatibility and lifetime for all resident components, plus a non-destructive loader path. E3/E4 defeat simply reusing current placements. | Needs owned code/data, stack and OS-resource lifetimes through the last task/callback use, with adequate capacity and failure handling. A short allocated payload proves no resident memory budget. Reusing the same unreserved CHDK base repeats B's overlap. |
| **Interrupt-controller dependency** | Must reconcile erased handlers with inherited hardware before earliest unmask (`0xFC267BF2` in the recorded path). Controller reset semantics remain UNKNOWN after PORT-4A. | If the original OS/table is preserved intact, the deliberate wipe/recreate transition would not be required. This is an inference, conditional on a valid loader handoff and preserved CPU/OS state. Current code cannot be assumed to provide it. | Preserving the running OS would avoid A's particular handler-table recreation step. Ordinary interrupt service, scheduling, API context and concurrency still matter. No direct controller changes or freedom from IRQ hazards is assumed. |
| **SD-host dependency** | Software init repeats against retained host/card state; SD1stInit execution/CMD0/recovery/mount remain UNKNOWN. | Would need to preserve valid storage-driver, transfer and file-service state through loading and handback. Avoiding reinitialization would remove A's specific recovery obligation only if this preservation is established. | Could rely on already running storage services if integration preserves their lifecycle. Loading, API synchronization, mode transitions and any later storage use remain obligations; no general SD safety is inferred. |
| **Observability** | Needs fresh, exact-artifact evidence after continuation and independent storage outcomes. Existing stage 3 does not supply it. | Needs evidence of correct OS continuation/handback, allocation ownership and absence of stale or invalid resident references. No B-specific observation is supplied. | Must distinguish synchronous entry/return from actual task dispatch, continuing execution, mode behavior and termination. Output remaining on screen after return is not proof code/task residency. |
| **Recovery/rollback** | Recreated software state means recovery is not an ordinary return to the old task environment. No guaranteed rollback from a panic or corrupted live state is established. | A handback and resident teardown contract is missing; returning through a presumed address is not rollback proof. Loader damage to live OS state cannot be assumed reversible by freeing a buffer. | Bounded native-return behavior was reported for E5's exact package. Resident task/callback/resource cleanup, cancellation and fault recovery remain UNKNOWN; freeing memory while references remain is not a demonstrated rollback. |
| **Unknowns needing runtime/hardware evidence** | IRQ delivery/handler coverage, host/card state convergence, actual continuation, mode stability and recovery. | Actual entry/exit CPU/OS state, memory-pressure coexistence, loader non-interference, storage continuity and recovery. | Actual creation/dispatch, allowed API context, scheduling impact, memory pressure/lifetime, mode/power transitions and reliable teardown. |
| **Full CHDK capability** | Intended architecture and artifact investment align with a CHDK port, but successful G3 X runtime is unproved. | No complete layout/handoff or feature mapping exists in the supplied evidence. | No evidence of full CHDK parity or that required early integration can be supplied later. Limited native integration and a full CHDK port are separate feasibility questions. |
| **Independent classification** | **PLAUSIBLE static approach; runtime feasibility UNKNOWN; NOT READY.** | **Current unreserved fixed-layout reuse is CONTRADICTED as memory-compatible. General B feasibility UNKNOWN; NOT READY.** | **PLAUSIBLE direction for further study, supported only at primitive level. Resident-task feasibility UNKNOWN; NOT READY.** |
| **Research disposition** | Preserve as blocked baseline. Reopen its critical semantics question only with new applicable evidence, not another prohibited enumeration. | Keep available; defer a general loader redesign until ownership and valid handoff have documentary support. | Highest priority for a small documentation-only feasibility milestone. This is not a recommendation to create a task or replace the candidate. |

## 4. Blockers by architecture

### A — Keep the static benefits, preserve the hardware blockers

1. **IRQ transition:** no applicable guarantee closes the mismatch between reset software handlers and inherited deliverable interrupts (E1/E2). The exact complete handler inventory is not independently established. Do not infer an actual inevitable panic.
2. **Storage transition:** task creation, task execution, the conditional CMD0 path, command completion and successful mount are separate unknowns (E1).
3. **Continuation/freshness:** no fresh, artifact-bound downstream observation establishes a complete warm restart (E8). Prototype remediation must not be attributed to the preserved older candidate.
4. **Inherited platform state and recovery:** skipped cold-only initialization and real CPU/bus state are not normalized by proof of RAM copying. The older Cortex-A9/GIC model cannot supply missing guarantees.

A has more implementation evidence than B/C; it also has unresolved hardware premises that the authorized documentation search did not close. That combination warrants retention, not automatic advancement or permanent abandonment.

### B — Reject the demonstrated conflict, not the whole family

1. **No established live memory ownership:** the current unreserved core overlaps the stock heap. Moving the name or calling it resident does not reserve it; no alternative safe region is identified here.
2. **No established non-destructive loader/return contract:** the recorded low-RAM loading address creates a live-state concern. The earlier `bx lr` return proposal is a proposal, not a demonstrated restoration of stack, mask, OS bookkeeping and continuation context.
3. **No resident lifetime/capability evidence:** code/data ownership, execution permissions/cache state, active references, available memory and feature coverage remain undocumented for a complete B.
4. **No demonstrated continuity/rollback:** storage and OS state must remain valid across load/handback and any subsequent removal. These outcomes cannot be inferred from avoiding a reboot.

Neither a new placement nor an in-flight allocator modification is proposed. General B remains UNKNOWN because its premises have not been established, not because E3 rules out every possible coexistence contract.

### C — The observed primitive is not a task architecture

1. **Task execution and API context:** a synchronous native call and return does not establish that creating a task is supported in that context, that it dispatches, or that every needed API is callable from it (E5/E6).
2. **Memory/resource lifetime:** resident code, data, stacks, callbacks and OS objects need a documented owner and a lifetime covering all uses. Existing short-payload allocation evidence does not establish these contracts or headroom.
3. **Persistence and scheduling:** survival through mode/power transitions, concurrency, blocking behavior and impact on Canon work are UNKNOWN. E7's inferred persistence is not a result.
4. **Feature reach and teardown:** the desired functions may require integration that a later task cannot supply; no parity is established. Stopping dispatch, outstanding work and live references must be accounted for before memory/resource release could be considered rollback.

If C were later found to require the same destructive restart or unreserved fixed layout, its claimed distinction would disappear and the corresponding A/B blockers would apply. The present recommendation assumes no such solution.

## 5. Corrections to the earlier decision rationale

| Earlier rationale in PORT-2C | Independent disposition |
|---|---|
| An overlapping fixed CHDK image makes every non-restart architecture mathematically impossible. | **Unsupported generalization.** The documented overlap invalidates ownership for that image/layout. It does not show that all native components must occupy those bytes or that no legitimate lifetime/ownership contract can exist. Conversely, this logical opening does not prove a large relocated/resident core feasible. |
| A's retained GIC/SD risks are mitigated by cold-boot restorations. | **Not established.** Later audits and PORT-4A leave Canon-controller semantics and SD recovery UNKNOWN. Repeating RAM/software initialization is not hardware reset proof. |
| Thousands of cameras / all released ports prove the selected approach. | **Insufficient applicability evidence.** The supplied record does not independently establish the universal inventory or transfer its results to G3 X GM1.10C. Precedent supports plausibility only. |
| Preserving candidate artifacts makes A superior on safety. | **Category error.** Preservation lowers rework and protects evidence; it does not satisfy a hardware precondition. Exploring B/C on paper requires discarding none of A's artifacts. |
| Native runtime FEASIBLE and task persistence inferred imply C is ready. | **Not established.** E6 excludes exactly the task and duration claims needed. Older unqualified reversibility/topology/cache statements cannot repair that gap. |

Normal power-off after E5's short test is useful evidence for that package and observation. It is not a guarantee for any future loader, resident task or failure mode. RAM residence alone does not exclude indirect persistent effects through Canon services; no option receives a zero-persistence-risk or guaranteed battery-pull recovery label.

## 6. Recommendation and explicit uncertainty

**Prioritize C for the next bounded documentation investigation, preserve A unchanged as the blocked reference, and retain B without accepting its rejected fixed layout.** This supersedes PORT-2C's argument that A is mandatory by elimination; it does not reverse the hardware NO-GO or establish a replacement design.

The strongest evidence is the combination of two independent limits in the project record:

- **A's missing premise remains missing:** PORT-4A found partial ID-register documentation, not a controller initialization/reset guarantee; the IRQ and SD blockers in the revised matrix remain open.
- **Native coexistence has a narrow reported foothold:** the same-model BOOT-001B-DIAG record documents bounded native execution and return within Canon's running environment, while explicitly excluding task creation and sustained operation.

That supports spending a small amount of documentation effort on C's missing ownership/lifetime premises. It does not support claiming that C is safer in practice, estimating its success probability, or abandoning the A prototype. B has both memory coexistence and loader/handoff uncertainties; C's existing-OS primitive makes a narrower evidence review possible first.

For a full CHDK port, there is **no justified final architecture selection yet**. If a required capability cannot be supported by C under a documented contract, that is a reason to reassess its applicability, not to invent a task hook or declare A safe. Additional controller documentation could improve A's case, but would still leave storage, observability and recovery obligations.

## 7. Smallest safe next research milestone

**One bounded question: does existing documentation establish memory ownership and lifetime sufficient for C's proposed residency, from entry until its last task/callback use has ended?**

Produce a short **C memory ownership and lifetime evidence table**, using existing written evidence only. The required result is a statement of what is supported versus missing, not a new memory map or implementation. Record:

1. The required lifetime being assessed, distinguishing a completed native call from a continuing task. State intended capability requirements; do not assume CHDK parity or change the product goal.
2. For code, data, task stack, callbacks and OS objects: documented ownership/allocation contract, lifetime, release condition, and exact source. Mark absent capacity, failure, cancellation or mode-lifecycle evidence UNKNOWN.
3. Whether the 52-byte call-and-return observation actually supports any continuing ownership claim. Do not infer a free address/pool, resident budget or task safety from it.

Completion criterion: a reviewable **SUPPORTED / MISSING evidence list** determining whether a later design discussion has enough premises. If required lifetime/ownership evidence is absent, conclude **C RESIDENCY UNKNOWN** and stop. A complete gap report is a valid milestone result; it is not permission to resolve the gaps through new firmware tracing, task creation or hardware testing.

Excluded from that milestone: new ROM analysis, IRQ caller searches, SD register-write searches, choosing addresses/patches/hooks, allocator rewrites, executable changes, builds/tests, payloads, probing and camera/SD operations. There is no speculative mitigation in this recommendation.

Questions ultimately requiring separately authorized runtime/hardware evidence remain distinct:

| Option | Runtime questions that documentation here does not answer |
|---|---|
| A | What IRQ is deliverable at unmask; whether handler coverage holds; actual SD/card recovery and fresh downstream continuation; failure recovery. |
| B | Whether a concrete loader preserves live OS/CPU/storage state, hands back correctly and coexists under real memory pressure; removal/fault recovery. |
| C | Whether a task actually runs in an allowed context, retains valid resources through mode/power transitions, avoids disrupting Canon work, and terminates without dangling uses. |

This table defines evidence gaps only. It is not an experiment plan or authorization for a phase transition.

Exact next command:

```sh
cat /Users/avp/Project/g3x-lite/docs/PORT4B_BOOT_ARCHITECTURE_DECISION.md
```

## 8. Source register and worktree boundary

All sources were read locally on **2026-10-25**. No external source was newly searched or revalidated in PORT-4B; PORT-4A's original URLs, versions and retrieval qualifications remain evidence attributed to that review. Prior physical results remain attributed reports. Addresses and memory ranges above come from the cited documents, with no new firmware verification.

The following hashes identify the actual local inputs, including untracked documents and pre-existing state/handoff edits. For clean tracked documents, repository links identify the same HEAD content; for modified/untracked inputs, the local file/hash is authoritative and a matching public version is not asserted. State/handoff hashes precede this review's additions.

| Exact local source | Revision boundary / public locator where applicable | Reviewed SHA-256 |
|---|---|---|
| [AGENTS.md](/Users/avp/Project/g3x-lite/AGENTS.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/AGENTS.md) | `175efb8c0313ef3055a0e987f72f7ffaa593270ffd0b20da5ec07d8b2f361a7d` |
| [README.md](/Users/avp/Project/g3x-lite/README.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/README.md) | `b26a04b134888ac4184485a6c7545c62913dc09eb320d82b887a1af29ebdb31d` |
| [docs/SAFETY.md](/Users/avp/Project/g3x-lite/docs/SAFETY.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/docs/SAFETY.md) | `c50f25b07500a844a374193b839028ca82de6007e6778eeb3a04049ffaaaa30d` |
| [docs/RESEARCH_PLAN.md](/Users/avp/Project/g3x-lite/docs/RESEARCH_PLAN.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/docs/RESEARCH_PLAN.md) | `9a06e7e4769d83aeea1d61749f324e29117b01894f303748c5b266c16a139097` |
| [docs/PROJECT_STATE.md](/Users/avp/Project/g3x-lite/docs/PROJECT_STATE.md) | Modified working-tree input; base HEAD above | `3ef890957dee5b513d75defce39daf1c5683cbc01a6fa498cd69461bd2537076` |
| [docs/HANDOFF.md](/Users/avp/Project/g3x-lite/docs/HANDOFF.md) | Modified working-tree input; base HEAD above | `96e5d33cbdae1c207c22a7467979b35503d2461c845a140a2841f3c177904172` |
| [docs/PORT3C_RESTART_READINESS_MATRIX.md](/Users/avp/Project/g3x-lite/docs/PORT3C_RESTART_READINESS_MATRIX.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/docs/PORT3C_RESTART_READINESS_MATRIX.md) | `5f7961e98b637896b5f3f6d9b26e4fe7a3c63030a9d757022e6a21d81c35b9ec` |
| [docs/CODEX_INDEPENDENT_RESTART_REVIEW.md](/Users/avp/Project/g3x-lite/docs/CODEX_INDEPENDENT_RESTART_REVIEW.md) | [HEAD source](https://github.com/s4urj3ng/g3x-lite/blob/4577fb6ae74057571da923b51f61fbe0724a1595/docs/CODEX_INDEPENDENT_RESTART_REVIEW.md) | `e540bad864e0d6eb4ead1fb5398922d70568a1864cf5a86e07ba7580e4e8ba60` |
| [docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md](/Users/avp/Project/g3x-lite/docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md) | Local/untracked; no matching public URL verified | `20c4f9c17abe9866909700edb6f5061ccc1ca3c26a4e8886704a8656c17a83e3` |
| [docs/CHDK_PORT2C_ARCHITECTURE_DECISION.md](/Users/avp/Project/g3x-lite/docs/CHDK_PORT2C_ARCHITECTURE_DECISION.md) | Local/untracked; no matching public URL verified | `9c6d83b88ef73f477d6abb7b5c9909bb40f46a9991ae67a337fdeeee983b4c0c` |
| [docs/BOOT001B_DIAG_HARDWARE_RESULT.md](/Users/avp/Project/g3x-lite/docs/BOOT001B_DIAG_HARDWARE_RESULT.md) | Local/untracked; no matching public URL verified | `738fcde1e502261fb6578a36657f48026b2ccff22d3aa6c8dc856e2e99062bcc` |
| [docs/PHASE4_NATIVE_RUNTIME_FEASIBILITY.md](/Users/avp/Project/g3x-lite/docs/PHASE4_NATIVE_RUNTIME_FEASIBILITY.md) | Local/untracked; no matching public URL verified | `645bf80f152d98682b5e0fe6d1751ead3e1f355e8d0b172fbada3fea7a44ef85` |
| [docs/CHDK_G3X_MEMORY_OWNERSHIP.md](/Users/avp/Project/g3x-lite/docs/CHDK_G3X_MEMORY_OWNERSHIP.md) | Local/untracked; no matching public URL verified | `9c9e5f34b40498182a16eae3ae7aed7a247d7654029ba7abf9ba011d760d2a7c` |

Only this decision document and brief PROJECT_STATE/HANDOFF additions are intended outputs. Existing source documents, candidate artifacts and other dirty/untracked work are preserved; no commit or push is made. **All complete architectures remain NOT READY.**
