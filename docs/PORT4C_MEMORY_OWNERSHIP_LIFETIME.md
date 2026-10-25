# PORT-4C — Native integration memory ownership & lifetime review

Date/retrieval date: **2026-10-25 (Asia/Seoul)**. Reviewer: Claude Code (independent architecture / memory-safety analyst).
Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port3-restart-readiness-audit`. Review-start HEAD: `4577fb6ae74057571da923b51f61fbe0724a1595`, with existing dirty/untracked material preserved. §10 lists the exact inputs and their hashes.

**Final verdict: C RESIDENCY UNKNOWN — STOP.** The existing evidence does not establish safe memory ownership for persistent native code/data, or a persistent task lifetime, inside the running GM1.10C DryOS environment. No implementation, task creation, address choice or hardware step follows from this report.

**Strongest verified finding.** Five owner-reported, same-model hardware results show native code running from DryOS-heap DRAM and returning cleanly. In **every one** of those packages, the code buffer is released with `FreeMemory(buf)` right after the synchronous `exec` returns, while still inside `task_Script` (E1–E5, E9). So native **code** residency has been shown only for the length of one borrowed, synchronous call. It has never been shown after `exec` returned, after `task_Script` ended, across a mode transition, or in a task the payload owns. What did survive script exit and one Playback→Shooting transition was **Canon-allocated** `LCDMsg` descriptors (E2/E3). Those are Canon-owned data in a Canon list, not native code or native-owned memory.

## 1. Scope, question and classification

Bounded question (from [PORT-4B §7](PORT4B_BOOT_ARCHITECTURE_DECISION.md)): *Does existing documentation establish memory ownership and lifetime sufficient for architecture C's residency, from entry until its last task/callback use has ended?*

What was done: only existing repository documents were read, plus the already-reviewed Canon Basic loader scripts that the hardware-result documents cite (to confirm what each tested package did with its buffers). No ROM/firmware bytes were opened. There was no disassembly, tracing, IRQ-caller or SD-write enumeration, memory probing, build, test, emulator, camera/SD operation, deployment, commit or push. The outputs are this report and short PROJECT_STATE/HANDOFF additions.

Labels, applied per proposition:

- **VERIFIED (doc)**: the cited document records the stated static finding or owner-reported observation. This review did not independently re-derive ROM facts or witness hardware events.
- **PLAUSIBLE**: supported by some evidence or architectural reasoning; a required premise is unproven.
- **UNKNOWN**: no evidence establishes it.
- **CONTRADICTED**: inconsistent with other identified evidence, or the documents disagree with each other.

Terminology used throughout:

| Term | Meaning here |
|---|---|
| **Allocated** | Obtained from an allocator that has a documented release contract (e.g. `AllocateMemory`/`FreeMemory`). |
| **Reserved** | Excluded from every competing owner for a documented lifetime (e.g. the restart path's heap shift). |
| **Copied** | Written by a boot copy/zero loop. That shows initialization, not current ownership. |
| **Observed** | An address seen in disassembly, a symbol or a hardware report. That shows neither ownership nor freedom. |
| **Function return** | A synchronous call returned to its caller with registers restored. |
| **Task survival** | Code continues to be scheduled, and its code/data/stack stay valid, after the creating context has ended. |

## 2. Evidence register

| ID | Source | What it supports | What it does **not** support |
|---|---|---|---|
| E1 | [BOOT001A_HARDWARE_RESULT.md](BOOT001A_HARDWARE_RESULT.md) §§1–4; loader [`boot001a_loader_gm110c.m`](../firmware/tools/boot001a_loader_gm110c.m) lines 86–99 | Owner-reported execution of a 12-byte Thumb-2 leaf from `AllocateMemory(12)` DRAM, with sentinel return. The loader calls `FreeMemory(buf)` after `exec` returns. | Any lifetime beyond the call. Any API use. Any task. |
| E2 | [BOOT001B_DIAG_HARDWARE_RESULT.md](BOOT001B_DIAG_HARDWARE_RESULT.md) §§1–4; loader [`boot001b_diag_loader_gm110c.m`](../firmware/tools/boot001b_diag_loader_gm110c.m) lines 124–127 | 52-byte non-leaf payload called `LCDMsg_SetStr_native` on a pre-existing handle and returned. The loader frees the buffer straight away ("string was copied into message object"). Two Canon-allocated descriptors persisted into Shooting Live View. | Arbitrary APIs, task creation, long sessions, recovery guarantees (all expressly excluded in its §4). |
| E3 | [UI001A_HARDWARE_RESULT.md](UI001A_HARDWARE_RESULT.md) (incl. line 79, 102, 115); loader [`ui001a_loader_gm110c.m`](../firmware/tools/ui001a_loader_gm110c.m) line 181 | Native multi-line OSD. Payload freed straight away. Three descriptors (168 B) survived **one** Playback→Shooting transition. | Persistence across other modes (MENU, sleep, video), which that document lists as unverified. |
| E4 | [UI001B0_HARDWARE_RESULT.md](UI001B0_HARDWARE_RESULT.md) lines 64–81, 131 | Payload (420 B) plus a result buffer (24 B) passed to native code, both freed straight away. Handles retained across one transition. | Native-owned data surviving the call. |
| E5 | [UI001B1_HARDWARE_RESULT.md](UI001B1_HARDWARE_RESULT.md) §1; loader [`ui001b1_loader_gm110c.m`](../firmware/tools/ui001b1_loader_gm110c.m) lines 23, 148–169 | 676-byte payload ran a bounded loop (~1.8 s) **inside `task_Script`**, yielding with `SleepTask(30)` and resuming correctly. Canaries were intact. Buffers freed after return. | Survival outside `task_Script`. Concurrent mode transitions (the script holds the interpreter semaphore, so mode switches are deferred). |
| E6 | [BOOT001_NATIVE_ENTRY_VERIFICATION.md](BOOT001_NATIVE_ENTRY_VERIFICATION.md) §5 lines 223–230, §6.1 | Static: `AllocateMemory` → system heap, 8-byte aligned, "lifetime extends until explicitly freed via `FreeMemory`". DRAM is `XN=0`. | Whether the allocator, the interpreter or task teardown ties a block to its requesting task or script. Runtime free capacity. |
| E7 | [CHDK_G3X_MEMORY_OWNERSHIP.md](CHDK_G3X_MEMORY_OWNERSHIP.md) §§1–3 | Static map of low RAM, BSS and the DryOS system pool, with a placement verdict of `UNVERIFIED / BLOCKED`. | Free or safe regions. Runtime heap occupancy. The "available safety margin" is a boot-time configuration check, not runtime free memory. |
| E8 | [CHDK_PORT1C_MEMORY_VALIDATION.md](CHDK_PORT1C_MEMORY_VALIDATION.md) line 61–65; [PORT-4B §2](PORT4B_BOOT_ARCHITECTURE_DECISION.md) | A pool/sub-boundary of `0x00600014` is used in the restart prototype, which conflicts with E7's `0x0060E000`. PORT-4B left this unresolved. | Which boundary is authoritative. |
| E9 | [UI001C_DESIGN_REVIEW.md](UI001C_DESIGN_REVIEW.md) §§3.1–3.3 (Codex) | Static `CreateTask` prologue/ABI notes (5th arg on stack, priority 1..32, TCM entry vs ARM thunk). An **execution-after-free** hazard if the payload is freed while a task runs. `ExitTask` does not return. | That `CreateTask` works from the `exec` context, that the payload survives once left unfreed, or the review's statement that session-scoped pinning "is safe". That statement is an assertion, not evidence. |
| E10 | [UI001C_ARCHITECTURE.md](UI001C_ARCHITECTURE.md) line 88; [UI001C_RISK_REGISTER.md](UI001C_RISK_REGISTER.md) RSK-01/RSK-05, lines 125–126, 199–200 | Design claims (Gemini): `ExitTask` reclaims the stack and TCB; a 4 KiB stack is adequate; an unclosed task has "zero persistent effect". | None of these were tested. E9 already rejects the related "free after `ExitTask`" claim. Not adopted. |
| E11 | [VIDEO001A_EXECUTION_CONTEXT_MATRIX.md](VIDEO001A_EXECUTION_CONTEXT_MATRIX.md) Approach 3 | The task approach is listed as "currently unproven on live hardware". Memory pinning, stack alignment and safe exit are listed as open blockers. A task cannot free its own code. | Any task result. |
| E12 | [PHASE4_NATIVE_RUNTIME_FEASIBILITY.md](PHASE4_NATIVE_RUNTIME_FEASIBILITY.md) §2.2–2.3, §4.2 | Static MPU decode (DRAM `XN=0`). Allocator inventory. Custom-task persistence labelled **INFERRED**. | Its "FEASIBLE" verdict, its persistence conclusion, and the absolutes "zero D-cache incoherency risk" and "100% volatile / zero risk". All are rejected as guarantees, consistent with PORT-4B E7. |
| E13 | [CHDK_G3X_STUBS_INVENTORY.md](CHDK_G3X_STUBS_INVENTORY.md) lines 28–29; [CHDK_PORT0B_STUBS_AUDIT.md](CHDK_PORT0B_STUBS_AUDIT.md) lines 33–35 | `CreateTask` `0xBFE14A3D` (CONFIRMED there). `ExitTask` given as `0xBFE14C1F` (PROBABLE) in one document and `0xBFE14A19` in the other. | Which `ExitTask` entry is correct. **CONTRADICTED** between documents. |
| E14 | [PORT3C_RESTART_READINESS_MATRIX.md](PORT3C_RESTART_READINESS_MATRIX.md) §§1–3; [PORT4A](PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md) §§4–5 | Restart-specific IRQ/SD blockers (P11–P13, P16–P18, P20). The ID register is documented. Reset semantics are UNKNOWN. ARMv7-R is documented, against the Cortex-A9 annotation. | Any ordinary (non-restart) IRQ or storage safety property. |
| E15 | [CHDK_PORT2C_ARCHITECTURE_DECISION.md](CHDK_PORT2C_ARCHITECTURE_DECISION.md) §2.2; [PORT-4B E3/E4](PORT4B_BOOT_ARCHITECTURE_DECISION.md) | The fixed CHDK core at `0x003489B4` overlaps the unshifted stock heap. The DISKBOOT load base `0x8000` lies in Canon low RAM. | That every non-restart placement is impossible (PORT-4B corrected that over-generalization). |

## 3. RAM ownership matrix

The addresses come from the cited documents only. **No row identifies free or safe RAM.** "Unused-looking" is never treated as ownable.

| Region (as documented) | Documented owner / mechanism | Kind | Lifetime / release | Collision risk for a resident native component | Status |
|---|---|---|---|---|---|
| `0x00000000..0x00003FFF` vectors + early scratch/stack | ROM boot (E7) | Copied / observed | Boot-time; current use after boot is not established | Exception vectors and early stacks. Not usable. | VERIFIED (doc) owner; current runtime use UNKNOWN |
| `0x00004000..0x00007FFF` | "Kernel low vectors & OS scratch" (E7) | Observed, **[INFERRED]** in E7 | UNKNOWN | Unknown live use. Absence of a model is not freedom. | UNKNOWN |
| `0x00008000..0x0003F4F3` low-RAM data | Canon initialized globals, copied from ROM (E7). Contains e.g. LCDMsg pool `0x0001BC60` (E2) and the interpreter semaphore `0x00015AC0` (E9) | Copied; Canon-owned | Whole session | Overwriting corrupts live Canon state. The current DISKBOOT load base `0x8000` is inside it (E15). | VERIFIED (doc): 100% Canon-owned |
| `0x0003F4F4..0x003489B3` BSS | Canon zero-initialized statics, incl. IRQ handler table at `0x0003F4F4` (E7, E14) | Copied (zeroed); Canon-owned | Whole session | Same. Zeroed at boot does not mean unused at runtime. | VERIFIED (doc): 100% Canon-owned |
| DryOS system pool `0x003489B4..0x0060E000` **or** `..0x00600014` | DryOS allocator: task stacks, queues, application buffers (E7). Source of every `AllocateMemory` block in E1–E5 | **Allocated** per block | Per block: until `FreeMemory` (E6, static). Whether blocks are tied to the requesting task or script: UNKNOWN | Only a block returned by the allocator, and not yet freed, is native-owned. A fixed address in the pool (e.g. the CHDK core base) is owned by the allocator, not by native code (E15). Runtime free capacity under shooting/movie load: UNKNOWN. | Owner VERIFIED (doc); upper boundary **CONTRADICTED** between E7/E8; capacity UNKNOWN |
| `0x0060E000..0x006CE000` "headroom" | Described as a reserved margin checked at boot (E7) | Observed / boot-time check | UNKNOWN at runtime | Calling it padding does not make it ownable. Its runtime use is not established. | UNKNOWN |
| `0x006CE000..0x006F0000` ARAM heap | Separate allocator (E7) | Allocated (Canon) | UNKNOWN | Canon-owned allocator. No native contract. | Owner VERIFIED (doc); contract UNKNOWN |
| `exmem` uncacheable pool (table `0x00049040`) | `exmem_ualloc` (E12) | Allocated (Canon) | UNKNOWN | Shared with Canon image/movie pipelines (plausibly). No release/ownership contract is documented for native use. | UNKNOWN |
| Uncached mirror `0x40000000+` | Alias of the same DRAM (E7, E12) | Alias, not separate memory | Same as the aliased block | Ownership follows the underlying block. A different alias is not a different owner. Coherency between aliases: see F6. | VERIFIED (doc) as alias |
| `0x010E1000..0x01107CFF` high RAM code/data | ROM-copied Canon code/thunks (E7) | Copied; Canon-owned | Whole session | Live Canon code. Not usable. | VERIFIED (doc) |
| TCM `0xBFE10000..0xBFE1741B` | Kernel code (`CreateTask`, scheduler), copied from ROM (E7) | Copied; Canon-owned | Whole session | Patching = hooking (E12 "Rank 2"), which is out of scope and unreviewed. | VERIFIED (doc) |
| Display memory `0x5FA00000..` / VRAM `0x5FD00000`, `0x5FE80000` | Display drivers (E7, E12) | Observed / Canon-owned | Whole session | Canon framebuffers. Not storage for native data. | VERIFIED (doc) owner |
| Restart path's reserved core `0x003489B4..new_sa` | Reserved **only if** the warm-restart heap shift is executed (PORT-3C P07) | Reserved (conditional on A) | Session, under A | Without restart this reservation does not exist and the range belongs to the allocator (E15). | VERIFIED (doc) conditional on A; **not available to C** |
| `task_Script` stack (borrowed by `exec`) | Canon interpreter task (E5, E9) | Canon-owned task stack | Ends when the script/task ends | Usable only for the duration of a synchronous call. Its size and the headroom for native frames are UNKNOWN. | Owner PLAUSIBLE (documented assertion); size UNKNOWN |
| `LCDMsg` 20-slot pool / descriptors | Canon UI; handles created through `LCDMsg_Create` (E2, E3) | Canon-allocated objects | Shown to outlive script exit across **one** transition (E2–E4). Global delete is owner-blind (E2 design notes). | Canon may also use slots. Retention ≠ native ownership. | VERIFIED (doc) for one transition; beyond that UNKNOWN |

**Ownership conclusion.** The only native-ownable memory with documented evidence is an allocator block (`AllocateMemory`) while it remains un-freed, and that has been exercised only during a synchronous call. No document establishes:

- whether an un-freed block survives `task_Script` termination without being reclaimed, or
- how much heap a resident component could hold without starving Canon allocations under real load.

**Heap / BSS / stack / temporary-buffer collision risks:**

- Using a heap address without allocating it is an allocator collision (E15).
- Using low RAM or BSS corrupts Canon globals (E7).
- Native frames on the borrowed `task_Script` stack have unknown headroom.
- Freeing the payload buffer while anything can still execute or reference it is execution-after-free (E9).
- Every Canon Basic temporary buffer in E1–E5 is freed at script level, so none of them is evidence of residency.

## 4. Execution lifetime

### 4.1 What the evidence actually demonstrates

```
 time ──────────────────────────────────────────────────────────────────────────────────────►

 task_Script (Canon-owned, holds interpreter semaphore 0x00015AC0)
 ├─ AllocateMemory(n) ── buf ─┐                                       [ALLOCATED, native-owned block]
 ├─ Fread payload → buf       │
 ├─ cache clean/invalidate    │
 ├─ exec(buf+1, …) ═══════════╪══► native code on task_Script's stack
 │                            │      ├─ optional Canon API call (LCDMsg_SetStr_native)   E2–E4
 │                            │      ├─ optional SleepTask yield/resume ≤ ~1.8 s        E5
 │                            │      └─ return r0 (sentinel)                    ◄── FUNCTION RETURN: VERIFIED (doc)
 ├─ FreeMemory(buf) ──────────┘  ◄── native code residency ENDS here in ALL five packages (E1–E5)
 ├─ script exits; semaphore released
 │
 ▼  mode transition (Playback → Shooting)
    Canon-owned LCDMsg descriptors still rendered        ◄── CANON DATA retention, one transition: VERIFIED (doc)
    native code / native-owned memory present?           ◄── NONE EXISTS (already freed)

 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
 What architecture C would require (NONE of this is evidenced):

 task_Script ── exec ──► CreateTask(entry∈buf, stack, prio, arg) ──? dispatch           UNKNOWN
          └─ buf NOT freed ──? survives script teardown                                UNKNOWN
 own task  ──► runs after script exit ──? across mode / sleep / movie / power-off       UNKNOWN
          ──► stack + TCB owned by whom; overflow detection                            UNKNOWN
          ──► ExitTask (entry address CONTRADICTED, E13) ──? who frees code buf          UNKNOWN
```

### 4.2 Function return vs task survival

| Property | Evidence | Status |
|---|---|---|
| DRAM allocated by `AllocateMemory` can be executed after cache maintenance | E1–E5 | VERIFIED (doc), owner-reported |
| AAPCS call/return through `exec` restores the caller's state well enough for the script to continue | E1–E5 | VERIFIED (doc) for those packages |
| One Canon API (`LCDMsg_SetStr_native`) is callable from native code in the `task_Script` context | E2 (and E3/E4 for the same API family) | VERIFIED (doc), for that API and context only |
| Native code can block/yield (`SleepTask`) and be rescheduled inside a borrowed Canon task | E5 | VERIFIED (doc), ≤ ~1.8 s, bounded, inside `task_Script` |
| Native code remains valid after `exec` returns | None: every package frees the buffer | **UNKNOWN (never exercised)** |
| An un-freed `AllocateMemory` block survives `task_Script` termination | None | **UNKNOWN** |
| Native code survives a mode transition | None. E5's loop was serialized against mode switches by the semaphore (E9). | **UNKNOWN** |
| Native code runs in a task it owns | None. E2 §4 expressly excludes task creation. | **UNKNOWN** |
| A task persists independently of UI mode | E12 §4.2: **INFERRED** only | **UNKNOWN** (not adopted) |

### 4.3 Limits of the temporary execution context

- **Borrowed stack.** `exec` runs native code on `task_Script`'s stack (documented assertion, E9). Its size, and the headroom for native frames or deeper API call chains, are not documented.
- **Serialization.** While `exec` is running, the interpreter semaphore blocks mode transitions (E5, E9). A temporary context therefore cannot observe or survive a transition while it is running.
- **Lifetime coupling.** Everything the script owns ends when the script exits. The evidence covers the script freeing its own blocks. It does not cover what interpreter teardown does with blocks the script did *not* free.
- **No callback registration.** No package registered a callback, handler or hook. So no native entry point was ever reachable by Canon after `exec` returned.

### 4.4 Requirements for persistent code and data residency

All of these are unsatisfied today:

1. A native-owned code/data block whose owner and release condition are documented and outlive every possible execution or reference (task, callback, pending message).
2. Proof that the block is not reclaimed by script/interpreter teardown, a mode change or a low-memory path.
3. A documented size and heap-headroom budget that does not starve Canon allocations under shooting/movie load.
4. Cache-coherency rules for code that stays resident while Canon code performs its own cache maintenance or uses uncached aliases. Note: E12 and PORT-3C P05 describe the Region 0 cacheability attributes differently. Both agree on `XN=0`.
5. A teardown order (stop execution → drain references → release objects → release memory) that does not depend on a task freeing its own code (E11).

## 5. Task integration precondition matrix

| ID | Precondition | Current evidence | Status |
|---|---|---|---|
| T1 | Task-creation entry point and ABI | `CreateTask` TCM entry `0xBFE14A3D`, ARM thunk `0xFC31BBC4`, 5th arg on stack, priority 1..32 (E9, E13), all static | PLAUSIBLE (static only); never called |
| T2 | Creation is legal from the `exec` / `task_Script` context | None | UNKNOWN |
| T3 | Created task actually dispatches | None | UNKNOWN |
| T4 | Stack ownership: who allocates it, from which pool, adequate size, overflow detection | E10 design claims only (4 KiB, "from DryOS heap") | UNKNOWN |
| T5 | TCB/name/arg lifetime (e.g. is the name pointer or arg copied, or referenced later?) | None | UNKNOWN |
| T6 | Code residency outlives the task's last instruction (no execution-after-free) | Hazard identified (E9). No proven pinning mechanism. | UNKNOWN |
| T7 | Data/context residency, and ownership of Canon objects (LCD handles) the task uses | Handles survive one transition (E2–E4). Shared 20-slot pool. Global delete is owner-blind. | PARTIAL: one transition only; beyond that UNKNOWN |
| T8 | Scheduler impact: priority relative to `task_Script` / `task_UI` / `task_MovieRecord`; starvation; latency | Priority values documented statically (E9, E11). No runtime evidence. | UNKNOWN |
| T9 | API context validity: which Canon APIs may be called from a non-Canon task | Only `LCDMsg_SetStr_native` from `task_Script` (E2) | UNKNOWN for any own task |
| T10 | Synchronization with Canon tasks; shared-variable races; multi-core affinity | Core topology not established for G3 X (PORT-4A §5; E12 "dual-core" claim not adopted) | UNKNOWN |
| T11 | Behavior across mode changes, sleep/power-save, movie recording and shutdown (killed, waited on, or blocks shutdown?) | None. E12 §4.2 is inference only. | UNKNOWN |
| T12 | Termination: correct `ExitTask` entry; who reclaims stack/TCB; how the code buffer is released | Entry address **CONTRADICTED** (`0xBFE14C1F` vs `0xBFE14A19`, E13). A task cannot free its own code (E11). Reclamation claims untested (E10). | CONTRADICTED / UNKNOWN |
| T13 | Observability that separates "`exec` returned" from "task dispatched and is still running" | No such instrument designed or evidenced. Output left on screen after return is not proof (PORT-4B). | UNKNOWN |
| T14 | Fault containment and recovery for a resident task | Power-off recovery reported only for the E1–E5 packages; E2 §4.5 expressly denies a guarantee | UNKNOWN |

No task-creation path is claimed to work.

## 6. Dependency comparison: restart-specific vs still applicable

| Hazard | Specific to warm restart (A)? | Still applies to native task integration (C)? |
|---|---|---|
| Handler table at `0x0003F4F4` zeroed while inherited lines stay enabled; earliest unmask `0xFC267BF2` (P16/P17) | **Yes.** It comes from recreating DryOS over live hardware. | Not this transition, provided C never re-initializes the kernel or touches the controller. **Still applies:** native code must not mask IRQs for long, must not touch `0xD401xxxx`, and must not register handlers. Ordinary interrupt latency and preemption of native code remain. |
| Interrupt-controller reset semantics UNKNOWN (PORT-4A) | **Yes** (A relies on a reset guarantee). | Not relied on, as long as C performs no controller operations. The semantics are still unknown, so any later C design that touches IRQs would reopen this. |
| SD host/card state across restart; conditional CMD0; mount (P11–P13) | **Yes.** | The reinitialization problem does not apply. **Still applies:** storage-API context and locking (e.g. `fileio_semaphore` exists, E7), I/O during recording, and card removal while a task holds handles. None of this is evidenced for native tasks. |
| Pre-restart peripheral quiesce (P18) | **Yes.** | No. |
| Witness freshness / continuation proof (P20) | **Yes**, in its form (stale DRAM across restart). | The equivalent need remains: proving a task is running *now*, not inferring it from earlier output (T13). |
| Heap reservation via shift (P07) | Its **solution** is restart-specific. | The **problem** remains and gets harder: C has no reservation mechanism, so it needs live allocator ownership plus a runtime budget (§3, §4.4). |
| Fixed CHDK core overlapping the stock heap (E15) | Solved only by A's shift. | Applies if C reused that layout. Avoided only by allocator-backed memory, whose survival is UNKNOWN. |
| Cache coherency of loaded code (P06) | Present in A's loader. | Applies at load time (handled for short payloads, E1–E5). Long-term coherency for resident code is UNKNOWN (F6). |
| CPU architecture (ARMv7-R vs Cortex-A9 annotation) | Affects A's model. | Affects C as well: multi-core/affinity and synchronization assumptions (T10). |
| Mode/power transitions, Canon resource contention, recovery | Applies to A after continuation. | **Applies fully to C** (T8, T11, T14). |

Avoiding a restart removes A's specific hardware-convergence obligations. It does **not** remove memory ownership, scheduling, concurrency, storage-context, transition or recovery hazards.

## 7. Failure modes (resident native integration)

| ID | Failure mode | Mechanism | Evidence status |
|---|---|---|---|
| F1 | Execution-after-free | Payload freed (or reclaimed by teardown) while a task, callback or return path can still reach it; the heap reuses the bytes | Mechanism VERIFIED (doc) in design review (E9); occurrence avoided so far only by never running past the free |
| F2 | Silent reclamation on script teardown | Interpreter/task teardown releases blocks it attributes to `task_Script` | UNKNOWN whether this mechanism exists |
| F3 | Heap starvation | A resident block or stack reduces headroom; Canon allocation fails during shooting/movie | UNKNOWN (no runtime capacity evidence) |
| F4 | Stack overflow | Undersized task stack, or borrowed-stack overflow in `exec`, corrupts adjacent heap/TCBs | UNKNOWN (sizes undocumented; E10 is a design claim) |
| F5 | Dangling Canon object references | Task uses LCD handles or other objects that Canon or a global delete has released; shared slot exhaustion | Partially characterized (owner-blind delete, E2 design notes); runtime UNKNOWN |
| F6 | Stale instructions/data | Resident code modified or relocated without coherent maintenance; cacheable vs uncached alias mismatch | UNKNOWN for residency; MPU attribute descriptions inconsistent (E12 vs PORT-3C P05) |
| F7 | Priority inversion / starvation of Canon tasks | Native task priority or busy loop delays `task_UI` / `task_MovieRecord` | UNKNOWN |
| F8 | Illegal API context | Calling a Canon API that assumes a particular task, lock or mode | UNKNOWN beyond E2's single API/context |
| F9 | Wrong termination primitive | `ExitTask` entry ambiguity (E13) leads to calling the wrong routine | CONTRADICTED source data |
| F10 | Transition / shutdown interaction | Task killed mid-operation, blocks shutdown, or survives into a state where its references are invalid | UNKNOWN |
| F11 | Race on shared state | Concurrent access to Canon globals without Canon's locks; affinity unknown | UNKNOWN |
| F12 | Unrecoverable fault | Fault in a resident task with no containment; recovery by power-off not guaranteed (E2 §4.5) | UNKNOWN |

## 8. Feasibility gates

Evidence that must exist **before implementation is even considered**:

| Gate | Required evidence | Status |
|---|---|---|
| G1 | DRAM executability of allocator-backed memory | **SATISFIED** (VERIFIED doc: E1–E5) |
| G2 | Load-time cache maintenance sufficient for short payloads | **SATISFIED** for the tested packages (E1–E5) |
| G3 | Synchronous native call/return without restart | **SATISFIED** (E1–E5) |
| G4 | At least one Canon API callable from native code in a Canon task context | **SATISFIED** narrowly (E2: one API, `task_Script` only) |
| G5 | Native code can yield/block and resume inside a borrowed Canon task | **SATISFIED** narrowly (E5: ≤ ~1.8 s, bounded) |
| G6 | **A native-owned block survives `task_Script` termination unreclaimed** (documented allocator/teardown contract) | **UNKNOWN**: first gate on the critical path |
| G7 | Runtime heap headroom and a resident budget under shooting/movie load | UNKNOWN |
| G8 | Authoritative pool boundaries (`0x0060E000` vs `0x00600014`) | CONTRADICTED / unresolved |
| G9 | Task-creation legality from the `exec` context, plus a dispatch observation | UNKNOWN |
| G10 | Stack/TCB/name/arg ownership and reclamation contract | UNKNOWN |
| G11 | Correct, single-sourced `ExitTask` entry and termination contract, plus a code-release owner other than the exiting task | CONTRADICTED / UNKNOWN |
| G12 | Behavior across mode, sleep, movie and shutdown transitions | UNKNOWN |
| G13 | Synchronization/affinity model for G3 X | UNKNOWN |
| G14 | Observability that distinguishes return from live task, and recovery evidence | UNKNOWN |

G1–G5 are the only satisfied gates. They establish a **call primitive**, not residency. G6 must be resolved before G9–G12 are meaningful: without a block that outlives its creator, a task would have nowhere valid to run.

## 9. Final verdict, critical gaps and recommendation

**Final feasibility verdict: C RESIDENCY UNKNOWN — STOP.**

- **VERIFIED (doc):** a no-restart native call primitive, including one Canon API call and a bounded yield inside `task_Script`, with code lifetime strictly bounded by the call. Canon-owned descriptors survive one Playback→Shooting transition.
- **PLAUSIBLE:** the static `CreateTask` ABI description. Allocator-backed memory as the only ownership path consistent with a live heap.
- **UNKNOWN:** persistence of native-owned memory past script exit, runtime heap budget, task creation/dispatch/context, stack ownership, transitions, synchronization, termination and recovery.
- **CONTRADICTED:** `ExitTask` entry address between documents; DryOS pool upper boundary between documents; PHASE4's task-persistence and "zero risk" conclusions as guarantees.

This does not show C to be impossible. It shows that C has no documented residency contract. It neither revives nor rejects A or B, and PORT-4B's NOT READY classification for all complete architectures stands.

**Critical missing evidence (highest leverage first):**

1. **G6:** whether an `AllocateMemory` block that the script does not free survives `task_Script` termination and interpreter teardown, and who owns it afterwards.
2. **G11/T12:** a single verified `ExitTask` entry, and a termination order that releases code without the task freeing itself.
3. **G7:** runtime heap headroom under real load.
4. **G9/T2–T3:** legality and dispatch of `CreateTask` from the `exec` context.

**Recommended next action (one bounded, offline-only question).** Stop here for owner review. If the owner wants to continue, the smallest next investigation is:

> **G6 only:** *Does the Canon Basic interpreter/task teardown, or the DryOS allocator, attribute `AllocateMemory` blocks to the requesting task/script and release them on script exit?*

Existing documents cannot answer this. It would need a **separately authorized, read-only static ROM review** limited to the `AllocateMemory`/`FreeMemory` event procedures (`0xFC60241A`/`0xFC602414` → `0xFC382C90`/`0xFC382C94`, per E6) and script-termination cleanup. Constraints for that review:

- no call-tree enumeration beyond those routines;
- no task creation;
- no hardware.

A documented "no attribution, no reclamation" result would satisfy only G6. It would not satisfy any task gate.

If ROM review is not authorized, the documentation-only fallback is to reconcile the `ExitTask`/`CreateTask` entry and stack-ownership claims across E9/E10/E13 into a single contradiction list. That clarifies G11 without new tracing.

This report authorizes no phase transition, implementation, address selection or experiment.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT4C_MEMORY_OWNERSHIP_LIFETIME.md
```

## 10. Source register

All inputs were read locally on 2026-10-25. No external source was retrieved. Hardware results are owner reports attributed to their documents; this review did not reproduce them. For untracked or modified files, the local hash is authoritative and no matching public revision is asserted. The PROJECT_STATE/HANDOFF hashes were taken before this review's additions.

| Local source | SHA-256 |
|---|---|
| `docs/PORT4B_BOOT_ARCHITECTURE_DECISION.md` | `a4203885636d8d5b6fda210b6ef6888f7704d4e8a029caa60e5747a276b56654` |
| `docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md` | `20c4f9c17abe9866909700edb6f5061ccc1ca3c26a4e8886704a8656c17a83e3` |
| `docs/PORT3C_RESTART_READINESS_MATRIX.md` | `5f7961e98b637896b5f3f6d9b26e4fe7a3c63030a9d757022e6a21d81c35b9ec` |
| `docs/CHDK_PORT2C_ARCHITECTURE_DECISION.md` | `9c6d83b88ef73f477d6abb7b5c9909bb40f46a9991ae67a337fdeeee983b4c0c` |
| `docs/PROJECT_STATE.md` (pre-edit) | `324c59b699ee5bdd5eeb81d245cdf91783bbda00e0d24ac6665f1f02fb3c0a28` |
| `docs/HANDOFF.md` (pre-edit) | `52c4b5636f3d6d60b26ece66e7aca388b6de34029dd049d637d88a7e5b592175` |
| `docs/BOOT001A_HARDWARE_RESULT.md` | `9f804b7a59ee3b1e61894b14ade8bce57fbbcfed612124d2df84b6fed8c4c99c` |
| `docs/BOOT001B_DIAG_HARDWARE_RESULT.md` | `738fcde1e502261fb6578a36657f48026b2ccff22d3aa6c8dc856e2e99062bcc` |
| `docs/BOOT001B_FIRST_HARDWARE_DIAGNOSIS.md` | `df2ceac089882b0fe4488ea3a931e393f4093df4a886dc802838908f864467f4` |
| `docs/BOOT001_NATIVE_ENTRY_VERIFICATION.md` | `f261f6bedeeb2c83d13ab8ddd8df9f58606420b741504025d56e0b509d63bd8a` |
| `docs/UI001A_HARDWARE_RESULT.md` | `40b606fc32426995835c269a11e7ffa7e81fb8404ff20d79e7db0e767ba965f7` |
| `docs/UI001B0_HARDWARE_RESULT.md` | `2734da34b08625e189e3c576957606cd0470d81f78bb3ffecffb34250088ebab` |
| `docs/UI001B1_HARDWARE_RESULT.md` | `8359dd1ecfff480660b71dafec1a7a19c7920e261ac19062a2601bad8ac47cb3` |
| `docs/UI001C_DESIGN_REVIEW.md` | `2543bd2f01b9993f3e10bbd6ab7d2ea10ceea297acca33a29b450fc133d382a0` |
| `docs/UI001C_RISK_REGISTER.md` | `2ff2cf64ac11267f16cb396190840ddc372ddc57ee0cdc29491bb84ba7d7c0fc` |
| `docs/VIDEO001A_EXECUTION_CONTEXT_MATRIX.md` | `1fd757eecd19456bb057a38ecae9eb15bf62df4bd8ccdebc8623f52d3e50e860` |
| `docs/CHDK_G3X_MEMORY_OWNERSHIP.md` | `9c9e5f34b40498182a16eae3ae7aed7a247d7654029ba7abf9ba011d760d2a7c` |
| `docs/CHDK_PORT1C_MEMORY_VALIDATION.md` | `d6d9081186fab337943f4f0846e5705ae2631bfa68c35a381147f5b882aefdb9` |
| `docs/CHDK_PORT1F1_MEMORY_LIFETIME.md` | `52169e0aababd6af3299f2e73785767a748d338beb037dc9fe4472a23aeab53f` |
| `docs/PHASE4_NATIVE_RUNTIME_FEASIBILITY.md` | `645bf80f152d98682b5e0fe6d1751ead3e1f355e8d0b172fbada3fea7a44ef85` |
| `firmware/tools/boot001a_loader_gm110c.m` | `03adb1f4e5fe77059b8828a8fd64654f54ef833c40e06f49218a7d0b56d7e69f` |
| `firmware/tools/boot001b_diag_loader_gm110c.m` | `1b5b03760bf376d50479dbb6caf7c362a5f88db051cc2fa61a5c45ed23313485` |
| `firmware/tools/ui001a_loader_gm110c.m` | `633d0b67267fb4bff9508f9a357414717f0610bfdf5715b86c90524efeedcd58` |
| `firmware/tools/ui001b1_loader_gm110c.m` | `f89ebf9a3f90912d4a74065afdee6bbe8351640f0c63e69dfcaf943650087046` |

`docs/CHDK_G3X_STUBS_INVENTORY.md` and `docs/CHDK_PORT0B_STUBS_AUDIT.md` were consulted only for the `CreateTask`/`ExitTask` rows cited in E13.

Worktree boundary: this report plus short PROJECT_STATE/HANDOFF entries are the only changes. All pre-existing dirty/untracked work is preserved. Nothing was committed or pushed.
