# PORT-10A — Deep Runtime Preconditions Research: Evidence Consolidation & Contradiction Audit (GM1.10C)

**Date**: 2026-10-28  
**Author**: Gemini (Primary Research Engineer)  
**Tech Lead**: ChatGPT  
**Independent Reviewer**: Claude (post-completion)  
**Repository Baseline**: `https://github.com/s4urj3ng/g3x-lite` @ `origin/main` commit `cbe74cf` (includes merged PRs #1–#12)  
**Research Worktree**: `/Users/avp/Project/g3x-lite-port10a` (`research/port10a-runtime-preconditions`)  
**Hardware Status**: **STRICT NO-GO** (Read-only repository evidence consolidation; zero ROM disassembly expansion; zero firmware flashing; zero camera operation).

---

## 1. Executive Technical Conclusion

A review of the listed available repository evidence (tracked, local-only, and historical records) establishes that **none of the three unresolved runtime prerequisites (U1, U2, U3) can be legitimately promoted to `VERIFIED` using currently permitted repository evidence**.

1. **U1 (`create_task_prologue_verified`) remains UNKNOWN and CONTRADICTED**:
   - While the kernel veneer `0xFC31BBC4` targeting `CreateTask` @ `0xBFE14A3D` is directly supported by ROM disassembly traces (`RESTART_SD_HOST_AUDIT.md:64`), the prologue instruction sequence at `hook_CreateTask` (`0xBFE14A3C`) is internally inconsistent within a single untracked local document (`push.w {r1-r9, lr}` vs `push {r4, r5, r6, lr}`), leaving both claims unresolved until independent GM1.10C evidence is obtained.
   - The stored word `0x2de9fe43` has disputed independent provenance (matching GM1.10E), and the replayed literal (`0x8160` in GM1.10E vs `0x00008164` in G5X) has zero verified evidence for GM1.10C.
   - The underlying ATCM copy source in ROM (`0xFCEEF24C..`) has not been inspected. No specific instruction replay can be assumed safe without primary GM1.10C ROM verification.

2. **U2 (`init_file_modules_entry_verified`) remains UNKNOWN and CONTRADICTED**:
   - The ASCII string `"InitFileModules"` is verified in GM1.10C ROM at `0xFC0BD1AC`, but the task entry function address is contradicted between `0xFC0BD071` (untracked local record, copied verbatim from GM1.10E) and `0xFC0BD049` (an inferred `-0x28` shift).
   - Stock task body disassembly, error branches, and successful filesystem completion conditions on GM1.10C are entirely unrecorded.
   - Furthermore, reference CHDK ports signal readiness unconditionally, whereas physical SD card readiness across warm restart remains blocked by unresolved hardware states (P11, P12, P13).

3. **U3 (`physw_entry_verified`) — creator interpretation is strongly INFERRED; task-entry identity still UNKNOWN**:
   - Stock `task_Startup` (and `task_Startup_my`) calls `0xFC05B92E: bl sub_fc1283d2`. That `sub_fc1283d2` acts as the `PhySw` creator function (by analogy with G5 X `taskcreate_physw`) is **strongly INFERRED** rather than independently verified from the GM1.10C body of `sub_fc1283d2`, and the `task_PhySw` task-entry identity remains **UNKNOWN** in tracked evidence.
   - The entry address `0xFC1283AD` recorded in local notes is inherited from GM1.10E (or lacks provenance independent of GM1.10E) without tracked GM1.10C ROM proof.
   - Empirical hardware observations from `UI-001B-1` verify only the physical switch bitmasks in `GetKbdState dest[0]`; they provide **zero** evidence of task replacement, stack sizing (`0x2000` vs `0x800`), key suppression, or `mykbd_task` execution.

**Practical Verdict**: All four runtime interfaces (I1 `CreateTask_my`, I2 `InitFileModules` gate, I3 `SpyTask`, I4 `mykbd_task`) must remain strictly dormant. The PORT-9A fail-closed default configuration (`GM110C_PRECONDITIONS` all `False`) accurately reflects the state of evidence. Any promotion of U1–U3 requires separate owner authorization for read-only inspection of the relevant ROM regions in `firmware/dumps/GM1.10C/PRIMARY.BIN`.

---

## 2. Repository Baseline and Source Inventory

### 2.1 Repository & Worktree Baseline

- **Baseline Commit**: `cbe74cf30b5327b9ec3de53a79f1ec5d8487b41e` (`origin/main`, PR #12).
- **Active Research Worktree**: `/Users/avp/Project/g3x-lite-port10a` on branch `research/port10a-runtime-preconditions`.
- **Primary Worktree State**: `/Users/avp/Project/g3x-lite` contains uncommitted work from previous milestones. In accordance with AGENTS.md §24 and task directives, this primary worktree was untouched and preserved.

### 2.2 Source Material Categorization

To guarantee transparency and reproducibility across agents, all cited materials are partitioned into four strict provenance categories:

```
+---------------------------------------------------------------------------------------------------+
|                                  SOURCE MATERIAL INVENTORY                                        |
+---------------------------------------------------------------------------------------------------+
| 1. TRACKED REPOSITORY EVIDENCE (Available on clean clone of origin/main @ cbe74cf):               |
|    - docs/PROJECT_STATE.md, docs/HANDOFF.md, docs/SAFETY.md, AGENTS.md                            |
|    - docs/PORT9A_RUNTIME_INTEGRATION_MAP.md, tools/port9a_runtime_lifecycle.py                    |
|    - docs/PORT9B_RUNTIME_CONTRACT.md, tools/port9b_runtime_contract.py                            |
|    - docs/PORT3C_RESTART_READINESS_MATRIX.md, docs/PORT3A_RESTART_IRQ_AUDIT.md                    |
|    - docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md, docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md       |
|    - docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md, docs/PORT8A_PLATFORM_BOOTSTRAP.md              |
|    - docs/GM110C_FUNCTION_MAP.md, docs/RESTART_SD_HOST_AUDIT.md, docs/RESEARCH_LOG.md            |
|    - vendor/g3x-platform/*, tools/bootstrap_chdk_platform.py, patches/0002-port7b-keys-mask0.patch|
|    - chdk-port/platform/g3x/sub/110c/boot_prototype.c (SHA-256 f7884eb2...232e68)                |
+---------------------------------------------------------------------------------------------------+
| 2. LOCAL-ONLY / UNTRACKED ARTIFACTS (Present only in /Users/avp/Project/g3x-lite/):               |
|    - docs/CHDK_PORT0B_STUBS_AUDIT.md (L1: internal stub tables, contradictions)                   |
|    - docs/UI001_ROM_RESEARCH.md (L3: detailed function disassemblies, PhySw loop)                |
|    - docs/CHDK_PORT1C1_CRITICAL_AUDIT.md, docs/CHDK_PORT2C_EXECUTION_LEDGER.md                    |
|    - docs/PORT6C_CHDK_INTEGRATION_GAPS.md, docs/PORT_READINESS.md                                 |
|    - candidate_port2a/ (Pre-correction candidate binaries, FROZEN)                                |
+---------------------------------------------------------------------------------------------------+
| 3. HISTORICAL / EXTERNAL COMPARISON MATERIALS (Not GM1.10C facts):                               |
|    - g3x_110e.patch (Untracked, 336,714 B, SHA-256 55927968..., ranma CHDK r5480 port)            |
|    - Upstream CHDK r5491 (Git-ignored chdk-port/core/main.c, platform/g5x/sub/100c/boot.c)        |
+---------------------------------------------------------------------------------------------------+
| 4. RESTRICTED FIRMWARE DUMP (Read-Restricted under Phase 0 Safety Gate):                          |
|    - firmware/dumps/GM1.10C/PRIMARY.BIN (32 MiB, SHA-256 99118557...2578)                         |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. U1 — CreateTask Prerequisite

### 3.1 Interface Context & Architectural Role

In upstream DIGIC 6 CHDK ports (G5 X, SX710, M10), task redirection does not rely on compile-time linker overrides because core Canon firmware routines are linked to absolute addresses in ROM and TCM. Instead, CHDK installs an in-memory hook into the RAM-resident `CreateTask` entry point during early boot (`fw_boot` / `boot()`).

When Canon firmware tasks (such as `task_PhySw` or `task_InitFileModules`) are subsequently spawned by `task_Startup`, the hook intercepts the task entry pointer in register `r3`, redirects it to a CHDK replacement, replays the overwritten native prologue instructions, and branches back to the remainder of Canon's `CreateTask`.

### 3.2 Evidence Audit: Veneer, Entry, and ATCM Copy Source

1. **Kernel Veneer (`0xFC31BBC4`)**:
   - `docs/RESTART_SD_HOST_AUDIT.md:64` records that kernel veneer `j_CreateTask` at `0xFC31BBC4` branches directly to `0xBFE14A3D` (Thumb mode).
   - `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:81` also cites `0xFC31BBC4` (noting a `-0x28` offset relative to GM1.10E's veneer `0xFC31BBEC`), though both documents share provenance from the same original ROM trace rather than constituting two independent primary extractions.
   - **Classification**: **VERIFIED** for the existence and target of veneer `0xFC31BBC4` (single primary trace, shared provenance across docs).

2. **Hook Location (`0xBFE14A3C`)**:
   - The address `hook_CreateTask = 0xBFE14A3C` resides in the ARM Cortex-R4 ATCM address space (`0xBFE10000..0xBFE1FFFF`).
   - This address is identical to GM1.10E (`g3x_110e.patch:9045`) and is recorded in local file `docs/CHDK_PORT0B_STUBS_AUDIT.md:234`.
   - **Classification**: **INFERRED / HISTORICAL_REFERENCE_ONLY**. The TCM target address is plausible given ARM memory mapping, but its contents derive from early boot memory copies, not static ROM mapping.

3. **Origin in ROM (`0xFCEEF24C..`)**:
   - The ATCM is populated during early boot by an explicit copy loop (`loc_fc020046`). The ROM source backing `0xBFE10000` is located in high ROM (`0xFCEEF24C..`).
   - Under current Phase 0 rules, this ROM region has never been disassembled or verified.
   - **Classification**: **BLOCKED — REQUIRES SEPARATE APPROVAL**.

### 3.3 Prologue Description Contradictions

The untracked local stubs audit (`docs/CHDK_PORT0B_STUBS_AUDIT.md`) contains two conflicting descriptions of the first instruction of `CreateTask`:

```arm
; Conflict within untracked docs/CHDK_PORT0B_STUBS_AUDIT.md:
; Line 33:
CreateTask  @ 0xBFE14A3D  ->  push {r4, r5, r6, lr}                                 ; 16-bit Thumb (0xB570)

; Line 112 & Line 234:
CreateTask  @ 0xBFE14A3D  ->  push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}       ; 32-bit Thumb-2 (0x2DE9FE43 / stmdb)
hook_CreateTask @ 0xBFE14A3C -> val = 0x2de9fe43                                   ; Matches g3x_110e.patch
```

- **Analysis**: Line 33 describes a 4-register 16-bit Thumb push (`0xB570`), whereas lines 112 and 234 describe a 10-register 32-bit Thumb-2 `stmdb sp!, {r1-r9, lr}` (`0xE92D 0x43FE`, stored little-endian as `0x2DE9FE43`). Because both assertions appear within the same untracked local document and `0x2de9fe43` also matches `g3x_110e.patch` (disputed independent provenance), neither claim logically refutes the other; both remain unresolved until checked against primary GM1.10C evidence.
- **Hazard**: These two encodings have different lengths (2 bytes vs 4 bytes) and alter the stack pointer differently (16 bytes vs 40 bytes). Neither instruction replay may be assumed or used until the actual GM1.10C ATCM copy source is verified.

### 3.4 Replayed Literal & Patch Size

- In historical GM1.10E (`g3x_110e.patch:1521`), the hook replays `ldr r0, =0x8160`.
- In reference G5 X (`chdk-port/platform/g5x/sub/100c/boot.c:164`), the hook replays `ldr r0, =0x00008164`.
- **Finding for GM1.10C**: The literal (or instruction sequence) following the initial push is **UNKNOWN**. Reusing `0x8160` on GM1.10C is unjustified without GM1.10C ROM proof.

### 3.5 Contradiction Matrix for U1

| Claim | Source | Firmware Rev | Evidence Type | Confidence | Independently Corroborated? | Remaining Gap |
|---|---|:---:|---|:---:|:---:|---|
| Kernel veneer `0xFC31BBC4` branches to `0xBFE14A3D` | `RESTART_SD_HOST_AUDIT.md:64`, `PORT5B:81` | GM1.10C | Static ROM trace | **HIGH** | Shared provenance (`PORT5B` cites same trace) | None on veneer itself. |
| `hook_CreateTask` resides at `0xBFE14A3C` | `CHDK_PORT0B_STUBS_AUDIT.md:234`, `g3x_110e.patch:9045` | GM1.10C / GM1.10E | Local table & patch | **PLAUSIBLE** | NO (Local record matches E) | ATCM copy source in ROM unread. |
| Prologue is `push {r4, r5, r6, lr}` | `CHDK_PORT0B_STUBS_AUDIT.md:33` | GM1.10C | Untracked local table | **CONTRADICTED** | NO (Inconsistent with line 112/234) | Inconsistent with another local claim; unresolved until independent evidence. |
| Prologue is `push.w {r1-r9, lr}` (`0x2de9fe43`) | `CHDK_PORT0B_STUBS_AUDIT.md:112, 234` | GM1.10C | Untracked local table | **CONTRADICTED / UNVERIFIED** | NO (Inconsistent with line 33; matches E) | Disputed provenance; unresolved until independent evidence. |
| Replayed literal is `0x8160` | `g3x_110e.patch:1521` | GM1.10E | Historical patch | **HISTORICAL_ONLY** | NO (G5X uses `0x8164`) | Exact GM1.10C literal unknown. |
| Overwrite length is 8 bytes | `g3x_110e.patch:1434`, `g5x boot.c:101` | Reference / GM1.10E | Upstream C pattern | **PLAUSIBLE** | NO (Upstream reference pattern only) | Instruction boundaries on GM1.10C unverified. |

---

## 4. U2 — InitFileModules Prerequisite

### 4.1 String Attribution vs Task Entry

1. **String Literal**:
   - The string `"InitFileModules"` is verified in GM1.10C ROM at address `0xFC0BD1AC` (`docs/GM110C_FUNCTION_MAP.md:90`, `docs/RESEARCH_LOG.md:70` E057).
   - **Classification**: **VERIFIED**.

2. **Task Entry Address Contradiction**:
   - `docs/GM110C_FUNCTION_MAP.md:90` explicitly marks the task entry as **`UNKNOWN`**.
   - `docs/CHDK_PORT0B_STUBS_AUDIT.md:229` claims `task_InitFileModules = 0xFC0BD071` (`CONFIRMED`). However, `0xFC0BD071` is identical to Ranma's address in `g3x_110e.patch:9040` for GM1.10E.
   - `docs/PORT6C_CHDK_INTEGRATION_GAPS.md:46` claims `0xFC0BD049` (`0xFC0BD048 | 1`), which represents an inferred `-0x28` shift from `0xFC0BD071`.
   - **Analysis**: The repository contains two competing entry addresses (`0xFC0BD071` vs `0xFC0BD049`) alongside an explicit `UNKNOWN` marker. Neither address has traceable primary ROM disassembly evidence.
   - **Classification**: **UNKNOWN / CONTRADICTED**.

### 4.2 Documented Filesystem Readiness & Upstream Timing Hazards

In upstream CHDK reference ports and Ranma's GM1.10E patch, the `init_file_modules_task` hook functions as follows:

```arm
; Historical g3x_110e.patch:1768-1795:
init_file_modules_task:
    push    {r4, r5, r6, lr}
    bl      sub_fc0d9ccc            ; Initialize filesystem structures
    movs    r4, r0                  ; Save return code
    movw    r5, #0x5006
    beq     loc_fc0bd086
    movs    r1, #0
    mov     r0, r5
    bl      _PostLogicalEventToUI   ; Error notification to UI
loc_fc0bd086:
    bl      sub_fc0d9cf6            ; Secondary file module init
    bl      core_spytask_can_start  ; <-- CHDK GATE: spytask_can_start = 1
    cmp     r4, #0
    bne     loc_fc0bd09a            ; Return without UI event if error
    ...
```

**Critical Timing & Semantic Flaws in Upstream CHDK**:
1. **Unconditional Signaling**: Ranma's hook calls `core_spytask_can_start` *regardless* of whether `sub_fc0d9ccc` returned an error (`r4 != 0`). Upstream G5 X (`boot.c:524-526`) also places the signal before the error branch.
2. **Race Condition in `core_spytask`**: In upstream CHDK (`core/main.c:136, 156`), `core_spytask` explicitly clears `spytask_can_start = 0` at startup, and then waits up to 10 seconds for it to become 1. If `InitFileModules` finishes *before* `core_spytask` reaches line 136, the signal is wiped out.
3. **Timeout Fall-Through**: If the 10-second timeout expires, upstream `core_spytask` logs a warning and **continues executing anyway**, attempting to access fonts, scripts, and configuration on an unmounted filesystem.

### 4.3 Stricter PORT-9A Lifecycle Contract

PORT-9A (`tools/port9a_runtime_lifecycle.py`) rejected upstream's permissive behavior and modeled a strictly fail-closed gate:
- Readiness requires explicit `success=True`.
- Early readiness signals are latched and never cleared by SpyTask.
- Timeout or fault transitions SpyTask permanently to `FAILED`, never executing uninitialized code.

### 4.4 Disconnect from Physical Storage Mounting

Even if `InitFileModules` executes its stock code, this does **not** prove that the SD card is mounted or accessible:
- In `PORT3C_RESTART_READINESS_MATRIX.md` (P11, P12, P13), `SD1stInit` contains a conditional predicate check (`0x010E1774() == 1`) that can skip `CMD0_Initialize` entirely.
- The storage mounter waiter (`0x010E181E`) has its own 10-second timeout on event flag `[0x0000AC98]`.
- Therefore, task identity and completion of `InitFileModules` cannot be inferred to guarantee safe file I/O across warm restart.

---

## 5. U3 — PhySw Prerequisite

### 5.1 Creator Function vs Task Entry Point (Strongly Inferred Creator; Task Entry Still Unknown)

A persistent source of confusion in early project documentation was the relationship between the stock call in `task_Startup` and the periodic `task_PhySw` task entry:

1. **Stock Call (`sub_fc1283d2` @ `0xFC1283D2`) — Creator Interpretation Strongly Inferred**:
   - Stock `task_Startup` calls `0xFC05B92E: bl sub_fc1283d2` (`CHDK_PORT1C1_CRITICAL_AUDIT.md:222`).
   - In `CHDK_PORT2C_EXECUTION_LEDGER.md`, this call was verified to occur **after** `StartDiskboot` (`0xFC05B90E`), confirming that `sub_fc1283d2` is reached for the first time during `task_Startup_my`.
   - As recorded in `PORT9A_RUNTIME_INTEGRATION_MAP.md:113`, the call instruction `bl sub_fc1283d2` is **VERIFIED**, whereas the interpretation that `sub_fc1283d2` is the `PhySw` *creator function* (analogous to G5 X `taskcreate_physw`, which invokes `CreateTask` for `"PhySw"`) is **strongly INFERRED** from the startup call structure and upstream reference ports; the body of `sub_fc1283d2` and the exact arguments it passes to `CreateTask` have not been independently verified from GM1.10C ROM in tracked records.

2. **Candidate Periodic Task Entry (`0xFC1283AC` / `0xFC1283AD`) — Identity Still Unknown**:
   - Untracked local notes (`docs/CHDK_PORT0B_STUBS_AUDIT.md:231` and `docs/UI001_ROM_RESEARCH.md` §4) list `0xFC1283AC` (Thumb address `0xFC1283AD`) as `task_PhySw`:
     ```arm
     loc_fc1283ac:
         push    {r4, lr}
         ldr     r4, =0x000082BC     ; candidate state block
     loc_fc1283b2:
         ldr     r0, [r4, #8]        ; sleep duration
         blx     0xFC31BF84          ; SleepTask
         bl      0xFC12868C          ; switch scan helper
         cmp     r0, #1
         bne     loc_fc1283c4
         bl      0xFC12811E          ; change notification helper
     loc_fc1283c4:
         ldr     r0, [r4]            ; termination flag
         cmp     r0, #0
         bne     loc_fc1283b2
         pop.w   {r4, lr}
         b.w     0xFC31B8FC          ; ExitTask
     ```
   - However, `0xFC1283AD` is identical to the GM1.10E address in `g3x_110e.patch:9042`, and (`PORT9A_RUNTIME_INTEGRATION_MAP.md:114`) whether the local record was derived independently of GM1.10E is **UNKNOWN**. Consequently, `task_PhySw` task-entry identity remains **UNKNOWN** until independently verified from GM1.10C ROM.

### 5.2 Contradiction & Provenance Summary for U3

| Claim | Source | Firmware Rev | Evidence Type | Confidence | Independently Corroborated? | Remaining Gap |
|---|---|:---:|---|:---:|:---:|---|
| `task_Startup` calls `bl sub_fc1283d2` at `0xFC05B92E` | `boot_prototype.c:409`, `PORT9A:113` | GM1.10C | Tracked source / ROM trace | **VERIFIED (call)** | Shared provenance across startup audits | Target body of `sub_fc1283d2` not verified in tracked docs. |
| `sub_fc1283d2` is the `PhySw` creator (`taskcreate_physw`) | `PORT9A:113`, G5X `boot.c:485-500` | GM1.10C / Ref | Structural analogy | **STRONGLY INFERRED** | NO (GM1.10C body of `0xFC1283D2` unread in tracked records) | Creator body and exact `CreateTask` arguments unverified on GM1.10C. |
| `task_PhySw` task entry is `0xFC1283AD` | `CHDK_PORT0B_STUBS_AUDIT.md:231`, `UI001_ROM_RESEARCH.md` | GM1.10C / GM1.10E | Untracked local notes & E patch | **UNKNOWN** | NO (Matches `g3x_110e.patch:9042`; independent provenance unproven) | Task-entry identity still UNKNOWN without independent GM1.10C ROM check. |

### 5.3 What Empirical Keyboard Observations Actually Prove

Empirical hardware verification in milestone `UI-001B-1` (`docs/UI001B1_HARDWARE_RESULT.md`, `PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md`) confirmed the active-low bitmasks for 8 physical buttons:
- `KEY_VIDEO` (`0x08`), `KEY_MENU` (`0x10`), `KEY_UP` (`0x20`), `KEY_DOWN` (`0x40`), `KEY_RIGHT` (`0x80`), `KEY_LEFT` (`0x100`), `KEY_DISPLAY` (`0x1000`), `KEY_WIFI` (`0x2000`).

**Boundary of Proof**:
- **PROVEN**: The bit positions within `GetKbdState dest[0]` and ROM physical switch table `0xFC66C948` corresponding to button presses.
- **NOT PROVEN**:
  1. `task_PhySw` task-entry identity or replacement.
  2. `mykbd_task` execution or stack enlargement (`0x800` -> `0x2000`).
  3. Hooking `kbd_p1_f` / `kbd_p2_f` (`0xFC12811E`).
  4. Interception or suppression of `PostLogicalEventToUI` (`0xFC354494`).
  5. The runtime validity of `KEYS_MASK0` overrides.

`UI-001B-1` was a read-only sampler executed via Canon Basic inside stock `task_Script`, with stock `task_PhySw` running unmodified. It provides zero runtime validation of CHDK task interception.

---

## 6. Cross-Interface Dependency Matrix (I1–I4)

Using PORT-9A (`tools/port9a_runtime_lifecycle.py`) and PORT-9B (`tools/port9b_runtime_contract.py`) as the architectural foundation, the four runtime interfaces depend on each other and on unresolved firmware/hardware preconditions as follows:

```
+---------------------------------------------------------------------------------------------------------+
|                                    RUNTIME INTERFACE DEPENDENCY GRAPH                                   |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|   [ U1: CreateTask Prologue & Literal ] ---> [ I1: CreateTask Interception ]                            |
|                                                          |                                              |
|                               +--------------------------+-------------------------+                    |
|                               |                                                    |                    |
|                               v                                                    v                    |
|   [ U2: InitFileModules Entry & Semantics ]                [ U3: PhySw Entry & Stack Sizing ]           |
|                               |                                                    |                    |
|                               v                                                    v                    |
|   [ I2: InitFileModules Readiness Gate ]                   [ I4: Keyboard Task (mykbd_task) ]           |
|                               |                                                    |                    |
|                               v                                                    | (Gated on SpyTask) |
|   [ U4: SpyTask Placement & P07 Heap ]                                             |                    |
|                               |                                                    |                    |
|                               v                                                    |                    |
|   [ I3: SpyTask Execution (spytask) ] --------------------------------------------+                    |
|                                                                                    v                    |
|                                                                    [ CHDK ALT-Mode Key Handling ]       |
+---------------------------------------------------------------------------------------------------------+
```

### Detailed Dependency Table

| Interface | Primary Role | Direct Preconditions Required | Current Repository Status | Warm Restart Blocker Dependencies | Implementation Gate |
|---|---|---|:---:|---|---|
| **I1: Task Interception** (`CreateTask_my`) | Intercepts task creation in TCM; routes `InitFileModules` and `PhySw` to CHDK wrappers. | **U1**: Prologue instructions at `0xBFE14A3C` and replayed literal/instructions. | **UNKNOWN / CONTRADICTED** (Local claims inconsistent; literal unverified). | CPU mode Privileged SVC (P01) and pre-unmask IRQ disabled (P15). | BLOCKED on U1 ROM verification. |
| **I2: Readiness Gate** (`init_file_modules_task`) | Runs file module init; latches `fs_ready` to release SpyTask. | **I1** functional + **U2**: `task_InitFileModules` entry (`0xFC0BD071` vs `0xFC0BD049`) and success semantics. | **UNKNOWN / CONTRADICTED** (Entry contradicted; body disassembly absent). | SD host controller reset (P12), card `TRAN` response (P13), `SD1stInit` predicate (P11). | BLOCKED on I1 + U2 ROM verification. |
| **I3: Core SpyTask** (`spytask`) | Initializes CHDK core, scripts, GUI, and console. | **I2** `fs_ready` + **U4**: SpyTask placement & priority in `task_Startup_my` + DryOS heap shift (P07). | **UNKNOWN** (Commented out in prototype; placement unverified). | Heap collision safety (P07), task table reset (P08), SD filesystem mount completion. | BLOCKED on I2 + U4 + warm restart storage safety. |
| **I4: Keyboard Task** (`mykbd_task`) | Replaces `task_PhySw`; intercepts ALT key and suppresses Canon UI event dispatch. | **I1** functional + **U3**: `task_PhySw` entry identity, creator relationship, stack sizing. | **UNKNOWN / INFERRED** (Creator strongly INFERRED; task-entry identity UNKNOWN). | UI event queue stability (`PostLogicalEventToUI`), physical switch debouncing. | BLOCKED on I1 + U3 ROM verification. |

### Downstream Prerequisite U4 (Treated Separately)

- **Definition**: The placement, stack size, and priority of `CreateTask_spytask` in `task_Startup_my`.
- **Historical Reference**: Ranma placed `CreateTask_spytask("SpyTask", 0x19, 0x2000, spytask, 0)` at the end of `task_Startup_my` after `sub_fc0bb6fe`.
- **Current Prototype**: Commented out at lines 412–416 of `boot_prototype.c` to prevent the 10-second watchdog timeout crash.
- **Status**: **UNKNOWN / UNVERIFIED**. It cannot be resolved until I1 and I2 provide a functional readiness gate.

---

## 7. Explicit Unresolved Facts

The following facts are formally recorded as unresolved:

1. **ATCM `CreateTask` Prologue Instructions**: The machine code residing at `0xBFE14A3C` (and its backing ROM copy source `0xFCEEF24C..`) is unverified, and local notes contain conflicting descriptions (`push {r4, r5, r6, lr}` vs `push.w {r1-r9, lr}`).
2. **Replayed Literal / Sequence**: The constant or instruction sequence following the `CreateTask` prologue is unrecorded for GM1.10C.
3. **`task_InitFileModules` Entry Address**: The function pointer passed in `r3` when creating `InitFileModules` is contradicted between `0xFC0BD071` and `0xFC0BD049`.
4. **`task_InitFileModules` Body & Semantics**: The internal call graph, return register semantics, and error branches of `task_InitFileModules` on GM1.10C are unrecorded.
5. **`sub_fc1283d2` Body & `task_PhySw` Entry Identity**: That `sub_fc1283d2` is the `PhySw` creator is strongly inferred, while its GM1.10C body and the `task_PhySw` entry address (`0xFC1283AD` in local notes and GM1.10E) have not been independently verified from GM1.10C ROM.
6. **Stack Sizing for `mykbd_task`**: Whether `0x800` causes stack overflow during CHDK ALT-mode processing on GM1.10C, necessitating `0x2000`, is unmeasured.
7. **Filesystem Mount Guarantee**: Whether `InitFileModules` execution guarantees that the SD card is ready for standard file I/O across a warm restart without power-cycling the card is unproven.

---

## 8. Recommended Next Permitted Engineering Action

### 8.1 Zero-ROM Offline Maintenance (Immediately Permitted)

In accordance with Phase 0 rules and the recommendations of PORT-7C (§4, Rank 1):
- **Action**: Correct the stale switch-table index comments in `vendor/g3x-platform/platform/g3x/kbd.c` (e.g. updating `KEY_PLAYBACK` comment from index 10 to index 14, matching `physw_event_table` `0xFC66C9B8` / `physw_bits.txt`), update `vendor/g3x-platform/MANIFEST.json`, and re-run bootstrap/contract validation.
- **Scope**: Documentation/comment-only fix within tracked vendor files. Zero ROM access required.

### 8.2 Proposed Future Evidence Targets: Bounded Read-Only ROM Inspection (Separately Unauthorized)

Any direct inspection of `firmware/dumps/GM1.10C/PRIMARY.BIN` remains **separately unauthorized** under current rules, and neither the exact byte extent required nor the sufficiency of a fixed-size slice can be guaranteed in advance. If the owner later authorizes bounded read-only ROM inspection, the proposed initial evidence targets (not guaranteed resolutions) are:

1. **Proposed Target 1 (U1 — CreateTask in ATCM Copy Source)**:
   - Inspect the ATCM copy source region in ROM (`0xFCEEF24C..`) corresponding to runtime address `0xBFE14A3C` (and any referenced literal pool) to check the actual GM1.10C prologue instructions, instruction boundaries, and any literal loaded in the opening sequence.
2. **Proposed Target 2 (U2 — InitFileModules Creator & Entry)**:
   - Inspect code cross-references in ROM to the string `"InitFileModules"` (`0xFC0BD1AC`) to identify the task creation site, candidate `r3` entry pointer, and initial task body structure.
3. **Proposed Target 3 (U3 — `sub_fc1283d2` & PhySw Entry)**:
   - Inspect `sub_fc1283d2` (`0xFC1283D2..`) to test the strongly inferred creator interpretation and check what entry address and stack size it passes to `CreateTask`.

*Until explicit human authorization is granted, all ROM reads remain STRICTLY BLOCKED.*

---

## 9. Evidence Classification & Source Reference Index

| ID | Subject | Cited Location | Classification | Notes / Justification |
|---|---|---|:---:|---|
| **E-01** | `j_CreateTask` veneer target | `RESTART_SD_HOST_AUDIT.md:64`, `PORT5B:81` | **VERIFIED** | Direct ROM disassembly: `0xFC31BBC4` $\to$ `0xBFE14A3D` (shared provenance across docs). |
| **E-02** | `hook_CreateTask` address | `CHDK_PORT0B_STUBS_AUDIT.md:234` | **HISTORICAL_ONLY** | Untracked local note; matches `g3x_110e.patch:9045`. |
| **E-03** | Prologue: `push {r4-r6, lr}` | `CHDK_PORT0B_STUBS_AUDIT.md:33` | **CONTRADICTED** | Inconsistent with lines 112 & 234 of the same local document; unresolved until independent evidence. |
| **E-04** | Prologue: `push.w {r1-r9, lr}` | `CHDK_PORT0B_STUBS_AUDIT.md:112` | **CONTRADICTED / UNVERIFIED** | Inconsistent with line 33; `0x2de9fe43` matches GM1.10E with disputed independent provenance. |
| **E-05** | Replayed literal `0x8160` | `g3x_110e.patch:1521` | **HISTORICAL_ONLY** | Established for GM1.10E only; G5 X uses `0x8164`. |
| **E-06** | `"InitFileModules"` string | `GM110C_FUNCTION_MAP.md:90` | **VERIFIED** | Verified at `0xFC0BD1AC` in GM1.10C ROM. |
| **E-07** | `task_InitFileModules` entry | `GM110C_FUNCTION_MAP.md:90` | **UNKNOWN** | Explicitly marked UNKNOWN; local claims conflict (`0xFC0BD071` vs `0xFC0BD049`). |
| **E-08** | Stock `bl sub_fc1283d2` call & role | `boot_prototype.c:409`, `PORT9A:113` | **VERIFIED (call) / STRONGLY INFERRED (creator)** | Call at `0xFC05B92E` is VERIFIED; creator role is strongly INFERRED; `task_PhySw` entry identity still UNKNOWN. |
| **E-09** | `task_PhySw` loop disassembly | `UI001_ROM_RESEARCH.md:147`, `PORT9A:114` | **UNKNOWN / UNVERIFIED (LOCAL)** | Untracked local note (`0xFC1283AD` matches GM1.10E; independent GM1.10C provenance unproven). |
| **E-10** | Physical button bitmasks | `PORT7C:47-56`, `UI001B1_HARDWARE_RESULT.md` | **VERIFIED (OBSERVED)** | 8 Port 0 button bits verified empirically on camera hardware. |
| **E-11** | Keyboard task replacement | `vendor/.../kbd.c:47-49` | **NOT IMPLEMENTED** | `mykbd_task` deliberately omitted; stock call `sub_fc1283d2` runs unmodified. |
| **E-12** | Model preconditions inert | `PORT9A:34`, `PORT9B:39` | **VERIFIED (MODEL)** | `GM110C_PRECONDITIONS` all False; verified by 32 + 51 unit tests. |

---

**Hardware deployment status remains STRICT NO-GO.**
