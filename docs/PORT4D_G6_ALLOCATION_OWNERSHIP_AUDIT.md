# PORT-4D — G6 native allocation ownership & script teardown audit

Date: **2026-10-25 (Asia/Seoul)**. Analyst: Claude Code. Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port3-restart-readiness-audit`, HEAD `4577fb6ae74057571da923b51f61fbe0724a1595` (dirty/untracked work preserved).
ROM: `firmware/dumps/GM1.10C/PRIMARY.BIN`, 33,554,432 B, SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` (re-verified this session).
Authorization: owner-approved, read-only ROM analysis limited to G6 ([PORT-4C §8](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md)).
Tool: `arm-none-eabi-objdump` raw-binary disassembly, read-only. No ROM bytes were modified or copied into the repository.

**G6 verdict: UNKNOWN (partial evidence).**
- **Allocator half: resolved.** The `AllocateMemory` path records no task or owner. A block stays allocated until something calls `free` on its pointer.
- **Script-teardown half: not established.** That analysis was **stopped by a safety classifier** before any finding was recorded. Under the task's stop conditions it is not retried, reframed or bypassed.

Survival of a block after `task_Script` exits therefore remains **UNKNOWN**.

## 1. Classification

- **VERIFIED (ROM):** read directly from the disassembly in this session at the cited addresses.
- **VERIFIED (doc):** recorded in an existing project document; not re-derived here.
- **PLAUSIBLE:** follows from verified facts, but a premise is unexamined.
- **UNKNOWN:** not established.

## 2. Allocator call chain (exact ROM evidence)

TCM addresses map to ROM through the documented copy `0xFCEEF24C → 0xBFE10800` ([memory dossier §1](CHDK_G3X_MEMORY_OWNERSHIP.md)). The offset was checked against the documented `CreateTask` preimage pair (`0xBFE14A3C` ↔ `0xFCEF3488`), which matches exactly. No `CreateTask` behavior was examined.

| Step | Address | Instructions / behavior observed | Status |
|---|---|---|---|
| `AllocateMemory` event procedure | `0xFC60241A` | `ldr r0,[r0]` ; `b.w 0xFC382C90`. Loads the size argument and tail-branches. **No list insertion, no owner/task recording, no script bookkeeping.** | VERIFIED (ROM) |
| `FreeMemory` event procedure | `0xFC602414` | `ldr r0,[r0]` ; `b.w 0xFC382C94`. Same pattern, no bookkeeping. | VERIFIED (ROM) |
| Veneers | `0xFC382C90` / `0xFC382C94` | `b.w 0xFC381524` / `b.w 0xFC38155A` | VERIFIED (ROM) |
| `malloc` | `0xFC381524` | `size==0` → returns 0. Takes the semaphore at `[desc+0x24]` (thunk `0xFC31BF5C` → TCM `0xBFE120B3`). Calls the heap allocator (thunk `0xFC31BA2C` → `0xBFE1452F`) with `desc = 0x00040A94` (literal at `0xFC381580`). Gives the semaphore (thunk `0xFC31BF74` → `0xBFE1208B`). On success: `str r4,[r4]` writes a **self-pointer** header word, then returns `+8`. On failure: errno ← `12` (via `0xFC382AC8`), returns 0. | VERIFIED (ROM) |
| `free` | `0xFC38155A` | `ptr==0` → returns. Takes the same semaphore, loads `[ptr-8]` (the self-pointer), calls the heap free (thunk `0xFC31BA34` → `0xBFE145EF`), and tail-gives the semaphore (`0xFC31B8F2` → `0xBFE1208B`). | VERIFIED (ROM) |
| Heap allocate (TCM) | `0xBFE1452E` | First-fit walk of the free list at `desc+0x08/+0x0C`. Free block layout `{size@0, next@4}`. Rounds size up to 8 bytes plus overhead `desc+0x10`, splits or takes the whole block, writes `size` to `block[0]`, returns `block+8`. Optional statistics when `desc+0x14` bit 1 is set: bytes at `+0x1C`, count at `+0x20`, high-water at `+0x18`. **No owner field.** | VERIFIED (ROM) |
| Heap free (TCM) | `0xBFE145EE` → `0xBFE1459C` | Subtracts 8, decrements the optional statistics, inserts the block into the **address-ordered** free list and coalesces with adjacent neighbours. **No owner check.** | VERIFIED (ROM) |
| Heap creation | `0xFC3814DA` region | The `malloc` heap is created over `{base,size}` taken from the descriptor at `0x000403F0` (getters `0xFC05E5E8`/`0xFC05E5FE`) through thunk `0xFC31BA3C`. A `"malloc"`-named semaphore is created (`0xFC31BEA4`, string `0xFC381584`) and stored at `desc+0x24`. Whether that range is exactly the documented DryOS pool `0x003489B4..` was not resolved. | VERIFIED (ROM) for the mechanism; region identity PLAUSIBLE |

**Allocator-level ownership.** An `AllocateMemory` block belongs to a single global pool (`malloc` descriptor `0x00040A94`), serialized by one semaphore. Its header holds only a size word (heap layer) and a self-pointer (malloc layer). Nothing in the examined path ties a block to `task_Script`, to the calling task or to a script. Ownership is therefore a **caller convention**: whoever holds the pointer can free it, and the allocator alone never frees it.

## 3. Script teardown

| Question | Evidence | Status |
|---|---|---|
| Script entry identification | String `A/extend.m` at `0xFC311F1C` is referenced by ADR at `0xFC311F08`, which calls `0xFC0AC8F2`. Strings `LoadScript`/`UnLoadScript` (`0xFC557F70`/`0xFC557F80`) are registered at `0xFC557E3C`/`0xFC557E44`. | VERIFIED (ROM): locations only |
| Does `task_Script` exit or interpreter teardown free blocks the script obtained through `AllocateMemory`? | Analysis **stopped by a safety classifier** during script-module examination. No finding recorded. Not retried. | **UNKNOWN** |
| Does task termination in general free heap memory? | Not examined. Out of scope (scheduler/task investigation excluded). The allocator itself has no owner hook (§2), but a higher layer could still track and free blocks. | **UNKNOWN** |
| Existing evidence of script-owned allocations being invalidated | None. Every hardware-verified loader frees its own buffers explicitly ([PORT-4C E1–E5](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md)). No test ever left a block allocated. | No evidence either way |

## 4. G6 ownership / lifetime table

| G6 sub-question | Finding | Status |
|---|---|---|
| Allocation validity **after native `exec` returns** | `exec` returning frees nothing at allocator level: free happens only through an explicit `free` call. In the tested loaders the block stays valid until the script's `FreeMemory(buf)` line. | VERIFIED (ROM: allocator path) + VERIFIED (doc: loaders) |
| Allocation validity **after `task_Script` exits** | The allocator holds no owner. Survival depends on whether script teardown (or any other layer) explicitly frees tracked blocks, and that was not established. | **UNKNOWN** |
| **Ownership and authority to free** | No allocator-recorded owner, and `free` performs no owner check. Any code holding the pointer can release it. A double or foreign free is not prevented by the allocator. | VERIFIED (ROM) |
| Lifetime across Playback/Shooting transitions | Nothing in the allocator path is mode-dependent. Whether mode-change code resets or reinitializes this heap, or frees tracked blocks, was not examined. | **UNKNOWN** |

## 5. Contradictions relevant to G6

- The `AllocateMemory` target is consistent across sources: [BOOT001_NATIVE_ENTRY_VERIFICATION §5](BOOT001_NATIVE_ENTRY_VERIFICATION.md) gives `0xFC60241B → 0xFC382C90` and `loc_fc381524`, and this audit confirms it.
- [PHASE4 §2.3](PHASE4_NATIVE_RUNTIME_FEASIBILITY.md) lists `AllocateMemory` at `0xFC557D5C`. That is the registration-table area (`0xFC557D58` per [BOOT001B revised design §6](BOOT001B_DIAGNOSTIC_REVISED_DESIGN.md)), not the entry point.
- Two different `free` routines appear in project documents: `0xFC38155A` (this audit, reached from `FreeMemory`) and `0xFC35FDF6` (used by `LCDMsg_Delete`, BOOT001B docs). Whether `0xFC35FDF6` operates on the same pool was not examined. This matters only if LCD descriptors and `AllocateMemory` blocks are assumed to share lifetime rules.
- The pool upper bound (`0x0060E000` vs `0x00600014`) remains unresolved. This audit did not map the `0x000403F0` range to either value.

## 6. Remaining G6 blocker and smallest next evidence requirement

**Blocker:** it is unknown whether `task_Script` termination or Canon Basic interpreter teardown releases `AllocateMemory` blocks the script did not free. The allocator does not do so by itself.

**Smallest next evidence requirement:** one documented answer to that single question. The ROM path to it was halted by the safety classifier in this session. Under the task rules it is **not** retried, reframed or approached by another route here. Whether any further evidence path is appropriate (for example, an owner-supplied applicable external reference) is an **owner decision**. Until then, G6 stays UNKNOWN and C residency stays blocked (PORT-4C).

Implications that hold regardless:
- Even if survival were proven, a retained block would come out of the single global Canon pool, so PORT-4C G7 (heap budget) still applies.
- Ownership would be convention-only: nothing would stop Canon or other code from freeing a pointer it holds.

## 7. Boundary record

- **Done:** allocator disassembly at the listed addresses, ROM hash check, string/ADR location of script entry points.
- **Not done:** `CreateTask`/task analysis, IRQ or SD enumeration, any write or probe, builds, camera/SD operations, source/loader/test changes, commits or pushes. No retention was implemented and no `FreeMemory` was omitted anywhere.
- **Classifier stop:** recorded as a scope dependency, not a negative finding.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT4D_G6_ALLOCATION_OWNERSHIP_AUDIT.md
```
