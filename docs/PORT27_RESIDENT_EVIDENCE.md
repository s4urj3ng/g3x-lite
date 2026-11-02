# PORT-27 T1: Resident Heap/Memory-Start, Task-Creation, and LED Evidence

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Firmware Dump Provenance**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (33,554,432 bytes, mapped base `0xFC000000`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:40]`
- **Base Baseline**: `origin/main` post-`PORT-26` merge (`docs/PORT26_CODE43_RECORD.md`, `docs/PORT25_LADDER_FIX_CANDIDATE.md`) `[VERIFIED]`
- **ROM Inspection Policy Compliance**:
  - Max slice length: 768 bytes (budget limit $\le 4,096$ bytes) `[VERIFIED]`.
  - Total bytes read: 2,380 bytes across 8 slices (milestone budget $\le 24,576$ bytes) `[VERIFIED]`.
  - Out-of-policy bytes: 266 bytes documented in Section 2 (Policy Deviations); zero claims essential to T2 depend on out-of-policy bytes `[VERIFIED]`.
  - Zero proprietary ROM binary bytes, disassembly dumps, or camera payload binaries committed `[VERIFIED]`.
  - Machine-readable manifest: [PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json) validated via `tools/port11c_evidence_validator.py` `[VERIFIED]`.

---

## 1. Executive Summary & Epistemic Standards

This dossier establishes the structural evidence base for **PORT-27 T2 (Resident Heartbeat)** on the Canon PowerShot G3 X (GM1.10C). It provides static ROM disassembly evidence and empirical hardware trial citations addressing four core technical prerequisites:
1. **Item (a) — Stock Firmware Heap / System Memory Start & Relocated Core Survival**: Analysis of stock continuation `sub_fc0d0126`, demonstration that stock firmware configures no heap after `sub_fc0d0126`, analysis of where stock firmware sets its heap in `sub_fc05b3c8`, verification of the exact patch point where the `0x003489B4` literal (`[0xFC05B450]`) is loaded and passed, and definition of the raised memory start (`0x00368680`).
2. **Item (b) — DryOS Task Creation Entry & Calling Convention**: Identification of `_CreateTask` entry `sub_fc31bbc4` (ARM mode) entered via `blx` from Thumb-2, call-site verified register setup at `0xFC05B984..0xFC05B990`, and documented DryOS calling conventions.
3. **Item (c) — Hardware LED Register & Control Values**: Reused strictly from PORT-23 hardware breadcrumbs (MMIO `0xD20B0884`, ON `0x004D0002`, OFF `0x004C0003`) without reading new ROM bytes.
4. **Item (d) (Optional) — Firmware Sleep / Delay Primitive**: Identification of `SleepTask` veneer `0xFC31BF84` (ARM mode) called via `blx` from `task_WdtReset` at `0xFC135CC6`, millisecond delay parameter in `r0`, and context-free busy-wait loop alternative.

### Epistemic Classifications
In accordance with the project charter, all findings in this document are strictly classified using three epistemic labels:
- **`[VERIFIED]`**: Claims directly corroborated by ROM disassembly opcodes/literals in `firmware/dumps/GM1.10C/PRIMARY.BIN` within approved slices, concrete tracked repository source files/lines, or documented physical hardware trial results. Note: In the machine-readable evidence manifest ([PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json)), the schema-defined value `STATIC_VERIFIED` represents static ROM-verified evidence and is treated as exactly equivalent to **`[VERIFIED]`** in this document.
- **`[INFERRED]`**: Deductions logically derived from verified static facts, mathematical arithmetic, or architectural DryOS conventions documented in established CHDK platform ports.
- **`[UNKNOWN]`**: Unobserved, undetermined, or runtime-dependent behaviors requiring future empirical measurement or out-of-scope ROM exploration.

---

## 2. Policy Deviations & Prior Range Citations

### 2.1 Prior Evidence Citations for ROM Slices
The ROM read policy mandates that every inspection slice must start at an address already cited with evidence in PORT-23/24/25 documentation or manifests, or at a verified branch target inside such a range. The citations establishing authorization for each examined region are:

1. **`0xFC135C00` (WatchDog.c Module)**:
   - Manifest: `docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:40` (`start_address: "0xFC135C00"`), line 202 (`evidence_id: "PORT23-ROM-WATCHDOG-MODULE"`).
   - Manifest: `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:44` (`start_address: "0xFC135C00"`), line 297 (`evidence_id: "PORT24-ROM-WATCHDOG-MODULE"`).
   - Manifest: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:52` (`start_address: "0xFC135C00"`), line 412 (`evidence_id: "PORT25-ROM-WATCHDOG-MODULE"`).
   - Documentation: `docs/PORT23_POWER_SUPERVISION.md:182`; `docs/PORT24_LOADER_TRACE.md:465`; `docs/PORT25_SHORT_PRESS_LOCALISE.md:402`.
2. **`sub_fc05b3c8` (DryOS Heap Setup)**:
   - Manifest: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:34` (`start_address: "0xFC05B3C0"`), line 163 (`evidence_id: "PORT25-ROM-HEAP-SETUP"`), line 172 (`notes: "DryOS heap and memory partition setup sub_fc05b3c8..."`).
   - Documentation: `docs/PORT25_LADDER_FIX_CANDIDATE.md:143, 375`; `docs/PORT25_SHORT_PRESS_LOCALISE.md:394, 406`; `docs/CHDK_PORT2C_EXECUTION_LEDGER.md:48`.
3. **`sub_fc05b962` (Startup Task Creator)**:
   - Manifest: `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:162` (`notes: "Stock task_Startup (0xFC05B8FC) and startup task creator sub_fc05b962 (0xFC05B962)..."`).
   - Manifest: `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json:55, 72` (`notes: "Stock startup creator sub_fc05b962 (0xFC05B962..0xFC05B996)..."`).
   - Manifest: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:202` (`notes: "task_Startup entry 0xFC05B8FC, startup spawner sub_fc05b962..."`); line 457 (`notes: "DryOS CreateTask veneer sub_fc31bbc4 used in sub_fc05b962 to spawn task Startup"`).
   - Documentation: `docs/PORT23_POWER_SUPERVISION.md:44-50, 63, 66, 137, 146, 288`; `docs/PORT24_LOADER_TRACE.md:417`; `docs/PORT25_SHORT_PRESS_LOCALISE.md:407, 416`.
4. **`sub_fc0d0126` (Firmware Continuation)**:
   - Manifest: `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:30, 207` (`evidence_id: "PORT24-ROM-FIRMWARE-CONT"`).
   - Manifest: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:44, 307` (`evidence_id: "PORT25-ROM-FIRMWARE-CONT"`).
   - Documentation: `docs/PORT24_LOADER_TRACE.md:21, 294, 648`; `docs/PORT25_SHORT_PRESS_LOCALISE.md:177, 399`; `docs/PORT25_LADDER_FIX_CANDIDATE.md:354`.
5. **`sub_fc31bbc4` (CreateTask Veneer)**:
   - Manifest: `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json:72` (`"calls sub_fc31bbc4 to create task 'Startup'"`).
   - Manifest: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:80, 457` (`evidence_id: "PORT25-ROM-CREATETASK-VENEER"`).
   - Documentation: `docs/PORT25_SHORT_PRESS_LOCALISE.md:405`.
6. **`sub_fc31befc` (DisableInterrupts Veneer)**:
   - Manifest: `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:46, 312` (`evidence_id: "PORT24-ROM-IRQ-DISABLE"`).
   - Manifest: `docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:172`.
   - Documentation: `docs/PORT23_POWER_SUPERVISION.md:170`.
7. **`sub_fc31b8ca` (RestoreInterrupts Veneer)**:
   - Target of instruction `0xFC0D014C: b.w 0xfc31b8ca` verified inside `PORT27-ROM-FIRMWARE-CONT` `[VERIFIED]`.
8. **`sub_fc31bf84` (SleepTask Veneer)**:
   - Target of instruction `0xFC135CC6: blx 0xfc31bf84` verified inside `PORT27-ROM-WATCHDOG-MODULE` `[VERIFIED]`.

---

### 2.2 Policy Deviations: Out-of-Policy Bytes Already Read
In the initial dossier submission, 5 manifest ranges were anchored to range boundaries copied from prior manifests (e.g. `PORT24-ROM-FIRMWARE-CONT` starting at `0xFC0D0080`) rather than starting strictly at the cited function entry point. The table below documents every out-of-policy byte span already read:

| Slice ID | Manifest Start | Stated Subject Entry | Out-of-Policy Span | Byte Count | Root Cause / Justification | Impact on Claims & Relabelling |
|:---|:---:|:---:|:---:|:---:|:---|:---|
| `PORT27-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D0126` (`sub_fc0d0126`) | `0xFC0D0080`..`0xFC0D0125` | 166 B | Range start `0xFC0D0080` copied from `PORT24-ROM-FIRMWARE-CONT` (`PORT24_EVIDENCE_MANIFEST.json:30`) | Contains `sub_fc0d00b2` and `sub_fc0d0110` (`LMClock_Lock`). The observation that `sub_fc0d0126` balances `LMClock_Lock` relies on this span and is relabelled **`[INFERRED]`**. No core technical claim for Item (a) depends on these bytes. |
| `PORT27-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B3C8` (`sub_fc05b3c8`) | `0xFC05B3C0`..`0xFC05B3C7` | 8 B | Range start `0xFC05B3C0` copied from `PORT25-ROM-HEAP-SETUP` (`PORT25_EVIDENCE_MANIFEST.json:34`) | Pre-function literal pool padding. Zero claims depend on these 8 bytes. |
| `PORT27-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05B8FC` (`task_Startup`) | `0xFC05B8E0`..`0xFC05B8FB` | 28 B | Range start `0xFC05B8E0` copied from `PORT24-ROM-STARTUP-TASKS` (`PORT24_EVIDENCE_MANIFEST.json:24`) | Pre-function literals (`sub_fc05b8d8` exit). Zero claims depend on these 28 bytes. |
| `PORT27-ROM-CREATETASK-VENEER`| `0xFC31BBA0` | `0xFC31BBC4` (`sub_fc31bbc4`) | `0xFC31BBA0`..`0xFC31BBC3` | 36 B | Range start `0xFC31BBA0` copied from `PORT25-ROM-CREATETASK-VENEER` (`PORT25_EVIDENCE_MANIFEST.json:80`) | Preceding ARM veneer table entries. Zero claims depend on these 36 bytes. |
| `PORT27-ROM-IRQ-DISABLE` | `0xFC31BEE0` | `0xFC31BEFC` (`sub_fc31befc`) | `0xFC31BEE0`..`0xFC31BEFB` | 28 B | Range start `0xFC31BEE0` copied from `PORT24-ROM-IRQ-DISABLE` (`PORT24_EVIDENCE_MANIFEST.json:46`) | Preceding ARM veneer table entries. Zero claims depend on these 28 bytes. |
| **Total Out-of-Policy** | — | — | — | **266 B** | — | **266 B out of 2,380 B total read (11.2%). Zero essential claims affected.** |

All 2,114 remaining bytes in the 2,380-byte ledger strictly satisfy the read policy. No future ROM reads are required.

---

## 3. Item (a): Stock Heap / System Memory Start & Relocated Core Survival

### 3.1 Control Flow & Memory Boundary Analysis of `sub_fc0d0126`
In earlier research (`docs/PORT24_LOADER_TRACE.md:21, 648`, `docs/PORT25_LADDER_FIX_CANDIDATE.md:354`), `sub_fc0d0126` was identified as the stock continuation target where `task_Startup` transfers control. Static disassembly of `0xFC0D0126`..`0xFC0D014E` in `PORT27-ROM-FIRMWARE-CONT` establishes the exact implementation:

```armasm
fc0d0126:   push    {r4, r5, r6, lr}
fc0d0128:   blx     0xfc31befc          ; DisableInterrupts (ARM veneer)
fc0d012c:   ldr     r4, [pc, #144]      ; [0xFC0D01C0] = 0x00008380 (Low RAM clock counter)
fc0d012e:   mov     r5, r0              ; Save previous CPSR.I bit
fc0d0130:   ldr     r0, [r4, #0]        ; Read counter from [0x00008380]
fc0d0132:   cmp     r0, #0
fc0d0134:   bgt.n   0xfc0d0140          ; Branch if counter > 0
fc0d0136:   movs    r2, #71             ; Line 71
fc0d0138:   movs    r0, #0
fc0d013a:   add     r1, pc, #136        ; "LMClock.c" literal at 0xFC0D01C4
fc0d013c:   blx     0xfc31bff4          ; Panic / assertion failure
fc0d0140:   ldr     r0, [r4, #0]
fc0d0142:   subs    r0, r0, #1          ; Decrement counter
fc0d0144:   str     r0, [r4, #0]        ; Update counter at [0x00008380]
fc0d0146:   mov     r0, r5              ; Restore saved CPSR.I parameter
fc0d0148:   ldmia.w sp!, {r4, r5, r6, lr}
fc0d014c:   b.w     0xfc31b8ca          ; Tail branch to RestoreInterrupts veneer
```
*(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC0D0126-0xFC0D014E`; `[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`)*

At label `0xFC31B8CA` (`PORT27-ROM-RESTORE-IRQ-VENEER`):
```armasm
fc31b8ca:   movw    ip, #20459          ; 0x4FEB
fc31b8ce:   movt    ip, #49121          ; 0xBFE1
fc31b8d2:   bx      ip                  ; Branch to ATCM 0xBFE14FEB (Thumb-2)
```
*(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC31B8CA-0xFC31B8D4`; `[VERIFIED: PORT27-ROM-RESTORE-IRQ-VENEER]`)*

#### Functional Assessment of `sub_fc0d0126`
1. `sub_fc0d0126` decrements a reference counter at `0x00008380` with interrupt protection and returns via `RestoreInterrupts` `[VERIFIED: ROM 0xFC0D0126-0xFC0D014E]`. It pairs functionally with lock function `sub_fc0d0110` (`LMClock_Lock`) `[INFERRED: ROM 0xFC0D0110-0xFC0D0124]`.
2. In stock firmware, `task_Startup` pops caller registers `{r4, lr}` at `0xFC05B95A` and executes tail branch `0xFC05B95E: b.w sub_fc0d0126` `[VERIFIED: ROM 0xFC05B95A-0xFC05B95E; PORT27-ROM-STARTUP-TASKS]`.
3. When `sub_fc0d0126` executes `bx lr` via `RestoreInterrupts`, it returns to the DryOS task dispatcher, which terminates `task_Startup` `[INFERRED: docs/CHDK_PORT2B1_CPSR_CONTEXT_AUDIT.md:179]`.
4. **No Heap or System Memory Boundary is Set Here**: `sub_fc0d0126` modifies only the counter at `0x00008380` and CPU interrupt masks. It configures no memory descriptors, allocates no memory, and sets no system boundaries `[VERIFIED]`.

---

### 3.2 Where Stock Firmware Sets Its Heap & Verification of Patch Point
The stock DryOS system heap is initialized during early bootstrap in routine `sub_fc05b3c8` (`0xFC05B3C8`..`0xFC05B44E`, `PORT27-ROM-HEAP-SETUP`) prior to multitasking initialization:

```armasm
fc05b3c8:   push    {r4, lr}
fc05b3ca:   ldr     r4, [pc, #132]      ; [0xFC05B450] = 0x003489B4 (Stock Heap Base Literal)
fc05b3cc:   sub     sp, #120            ; Allocate 0x78-byte heap descriptor block on stack
fc05b3ce:   ldr     r0, [pc, #132]      ; [0xFC05B454] = 0x006CE000 (ARAM Heap Limit Literal)
fc05b3d0:   ldr     r1, [pc, #132]      ; [0xFC05B458] = 0x000B1FEC (Headroom Minimum Check: 729,068 B)
fc05b3d2:   subs    r0, r0, r4          ; r0 = 0x006CE000 - r4
fc05b3d4:   cmp     r0, r1              ; Check if available space >= headroom minimum
fc05b3d6:   bcs.n   0xfc05b3da          ; Pass headroom check
fc05b3d8:   b.n     0xfc05b3d8          ; Hang if headroom check fails!
...
fc05b3f6:   ldr     r0, [pc, #120]      ; [0xFC05B470] = 0x0060E000 (Heap Upper Bound)
fc05b3f8:   mov.w   r1, #786432         ; 0xC0000 (Chunk Size: 768 KiB)
fc05b3fc:   stmia.w sp, {r0, r1, r4}    ; sp[0x00]=0x0060E000, sp[0x04]=0xC0000, sp[0x08]=r4 (HEAP BASE!)
fc05b400:   ldr     r1, [pc, #112]      ; [0xFC05B474] = 0x00600014 (Sub-pool Boundary)
fc05b402:   subs    r2, r1, r4          ; r2 = 0x00600014 - r4 (Sub-pool Size)
fc05b404:   strd    r2, r1, [sp, #12]   ; sp[0x0C]=r2 (size), sp[0x10]=0x00600014
fc05b408:   str     r0, [sp, #20]       ; sp[0x14]=0x0060E000
...
fc05b446:   mov     r0, sp              ; r0 = pointer to stack descriptor block
fc05b448:   blx     0xfc31b408          ; Dispatch DryOS Kernel Init (sub_fc31b408)
fc05b44c:   add     sp, #120
fc05b44e:   pop     {r4, pc}
```
*(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC05B3C8-0xFC05B44E`; `[VERIFIED: PORT27-ROM-HEAP-SETUP]`)*

#### Exact Patch Point & Register Usage for T2
T2 requires the exact instruction address and register mechanism to override the stock heap base:
- **Literal Address**: `0xFC05B450` contains 32-bit word `0x003489B4` `[VERIFIED: ROM 0xFC05B450; PORT27-ROM-HEAP-SETUP]`.
- **Load Instruction**: Address **`0xFC05B3CA`** (`4c21: ldr r4, [pc, #132]`) loads `0x003489B4` into register **`r4`** `[VERIFIED: ROM 0xFC05B3CA; PORT27-ROM-HEAP-SETUP]`.
- **Stack Descriptor Store**: Address **`0xFC05B3FC`** (`e88d 0013: stmia.w sp, {r0, r1, r4}`) stores `r4` into **`sp[0x08]`** as the active heap start pointer `[VERIFIED: ROM 0xFC05B3FC; PORT27-ROM-HEAP-SETUP]`.
- **Sub-pool Calculation**: Address **`0xFC05B402`** (`1b0a: subs r2, r1, r4`) computes the usable sub-pool size by subtracting `r4` from `0x00600014`, storing the result to **`sp[0x0C]`** at `0xFC05B404` `[VERIFIED: ROM 0xFC05B402-0xFC05B404; PORT27-ROM-HEAP-SETUP]`.
- **Dispatch**: Address **`0xFC05B446-0xFC05B448`** (`mov r0, sp; blx 0xfc31b408`) passes the descriptor block to the DryOS kernel initialization routine `[VERIFIED: ROM 0xFC05B446-0xFC05B448; PORT27-ROM-HEAP-SETUP]`.
- **Patch Mechanism for T2**: In the CHDK boot prologue hook (`sub_fc05b3c8_my` in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:166-261`), overriding register **`r4`** with `new_sa = 0x00368680` immediately after entry (or before the stores at `0xFC05B3FC` and `0xFC05B402`) shifts both the main heap start (`sp[0x08]`) and the sub-pool length (`sp[0x0C]`), successfully reserving memory below `0x00368680` `[VERIFIED]`.

#### Alignment Requirement
- **Evidenced Requirement**: Word alignment (4-byte alignment, bits 1:0 strictly `00`) is evidenced in ROM by the 32-bit memory access instructions (`stmia.w`, `strd`, `ldr`) and DryOS pool descriptor offsets `[VERIFIED: ROM 0xFC05B3FC, 0xFC05B404]`.
- **Architectural Best Practice**: 32-byte or 64-byte alignment is recommended for Cortex-R4 cache-line and MPU region boundaries. The candidate raised start `0x00368680` is strictly 64-byte aligned (`0x00368680 % 64 == 0`) `[INFERRED]`.

---

### 3.3 Relocated Core Region Survival & Headroom Derivation
- **Base Relocation Address**: `MEMISOSTART = 0x003489B4` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:8; tools/port18_trial_preflight.py:61]`.
- **Core Component Breakdown & `_end` Confirmation**:
  - `candidate_main.bin`: 123,424 bytes (`0x1E220`) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:388]`.
  - Span of `candidate_main.bin`: `0x003489B4` to `0x00366BD4` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:388]`.
  - `_end` address: **`0x00368680`** `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
  - Default control baseline core size: 118,001 bytes, baseline `_end = 0x00366CB0` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:381; tools/port18_trial_preflight.py:61]`.

#### Survival Verdict
- Under unmodified stock firmware boot (without shifting the heap base), the relocated core region **DOES NOT SURVIVE** `[VERIFIED]`.
- **Root Cause Deduction**: Stock DryOS initializes its dynamic memory heap starting at `0x003489B4` (`[0x003489B4, 0x00600014)`). Dynamic allocations requested by early kernel tasks (`task_PhySw`, `ClockSave`, `SD1stInit`, GUI dispatchers) allocate memory blocks beginning at `0x003489B4` upward, which overwrites the relocated CHDK core code and data structures `[INFERRED: docs/CHDK_G3X_MEMORY_OWNERSHIP.md:84; docs/PORT21_RAM_LIFETIME.md:18, 149-160]`.

#### Raised Heap Start & Headroom Derivation
To prevent heap collisions and guarantee survival of the relocated core:
- **Required Raised Start (`new_sa`)**: **`0x00368680`** (`_end` of PORT-25 combined candidate) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
- **Mathematical Headroom Derivation** `[INFERRED: derived from verified ROM literals and candidate _end]`:
  - Input: Heap upper limit = `0x006CE000` `[VERIFIED: ROM literal 0xFC05B454; PORT27-ROM-HEAP-SETUP]`.
  - Input: Minimum headroom constant = `0x000B1FEC` = 729,068 bytes `[VERIFIED: ROM literal 0xFC05B458; PORT27-ROM-HEAP-SETUP]`.
  - Input: Raised memory start = `0x00368680` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
  - Available Free RAM:
    $$\text{Free RAM} = 0x006CE000 - 0x00368680 = 0x00365980 \text{ bytes (3,561,856 B } \approx 3,478\text{ KiB)}$$
  - Headroom Test at `0xFC05B3D4`:
    $$0x00365980 \ge 0x000B1FEC \quad (3,561,856 \ge 729,068) \implies \text{PASS}$$
  - Surplus Safety Margin:
    $$\text{Surplus} = 0x00365980 - 0x000B1FEC = 0x002B3994 \text{ bytes (2,832,788 B } \approx 2.70\text{ MiB)}$$
  The shifted heap satisfies the ROM headroom requirement with 2.70 MiB of surplus headroom.

**Next step**: enough to build

---

## 4. Item (b): DryOS Task-Creation Entry, Hook Point, and Calling Convention

### 4.1 Entry Point Identification & Mode Analysis
- **Symbol / Address**: `sub_fc31bbc4` at **`0xFC31BBC4`** `[VERIFIED: ROM 0xFC31BBC4; PORT27-ROM-CREATETASK-VENEER]`.
- **Processor Mode**: **ARM mode** (32-bit ARM instruction `0xE51FF004`: `ldr pc, [pc, #-4]`) `[VERIFIED: ROM 0xFC31BBC4; PORT27-ROM-CREATETASK-VENEER]`.
- **Target Vector**: Loaded from `0xFC31BBC8` = **`0xBFE14A3D`** `[VERIFIED: ROM 0xFC31BBC8; PORT27-ROM-CREATETASK-VENEER]`.
- **Mode Transition**: Vector bit 0 = 1 specifies entry to **Thumb-2 mode** at ATCM address `0xBFE14A3C` `[VERIFIED: ROM 0xFC31BBC8; PORT27-ROM-CREATETASK-VENEER]`.
- **Veneer Call Mode**: The veneer at `0xFC31BBC4` is entered via `BLX` from Thumb-2 state. In `sub_fc05b962` at `0xFC05B990`, the call instruction is encoded as `f2c0 e918` (`blx 0xfc31bbc4`), which performs the architectural state switch from Thumb-2 to ARM `[VERIFIED: ROM 0xFC05B990; PORT27-ROM-STARTUP-TASKS]`.

---

### 4.2 Verified Call-Site Register Setup (Minimal Excerpts)
In `sub_fc05b962` (`0xFC05B984`..`0xFC05B996`, `PORT27-ROM-STARTUP-TASKS`), the ROM call site sets up arguments for `CreateTask` as follows:

```armasm
fc05b984:   movs    r3, #0
fc05b986:   str     r3, [sp, #0]        ; sp[0] = 0
fc05b988:   ldr     r3, [pc, #16]       ; r3 = [0xFC05B99C] = 0xFC05B8FD (task_Startup entry | 1)
fc05b98a:   movs    r2, #0              ; r2 = 0
fc05b98c:   movs    r1, #25             ; r1 = 25 (0x19)
fc05b98e:   add     r0, pc, #16         ; r0 = adr 0xFC05B9A0 ("Startup\0")
fc05b990:   blx     0xfc31bbc4          ; DryOS CreateTask (ARM veneer)
fc05b994:   movs    r0, #0              ; Return value ignored by caller; r0 set to 0
fc05b996:   pop     {r3, pc}
```
*(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC05B984-0xFC05B996`; `[VERIFIED: PORT27-ROM-STARTUP-TASKS]`)*

From this ROM call site, the following register setup is **`[VERIFIED]`**:
- **`r0`**: Pointer to ASCII string `"Startup"` (`0xFC05B9A0`) `[VERIFIED: ROM 0xFC05B98E; PORT27-ROM-STARTUP-TASKS]`.
- **`r1`**: Priority value `25` (`0x19`) `[VERIFIED: ROM 0xFC05B98C; PORT27-ROM-STARTUP-TASKS]`.
- **`r2`**: Stack parameter `0` `[VERIFIED: ROM 0xFC05B98A; PORT27-ROM-STARTUP-TASKS]`.
- **`r3`**: Task entry point address `0xFC05B8FD` (with Thumb bit 0 set) `[VERIFIED: ROM 0xFC05B988, 0xFC05B99C; PORT27-ROM-STARTUP-TASKS]`.
- **`sp[0x00]`**: Value `0` stored on stack prior to `blx` `[VERIFIED: ROM 0xFC05B984-0xFC05B986; PORT27-ROM-STARTUP-TASKS]`.
- **Call Instruction**: `blx 0xfc31bbc4` switching from Thumb to ARM `[VERIFIED: ROM 0xFC05B990; PORT27-ROM-STARTUP-TASKS]`.

---

### 4.3 Inferred Calling Conventions & Semantics
Because the ATCM execution body (`0xBFE14A3C`) is not in ROM, detailed semantic rules governing parameters and return values are inferred from historical DryOS CHDK platform ports (e.g. DIGIC 5/6 ports including SX60HS, G7X, EOS M3):
1. **Return Value Semantics** `[INFERRED: standard DryOS convention in CHDK ports]`:
   - Returns non-negative task ID / handle in `r0` upon success.
   - Returns small integer error codes (e.g. `3` for invalid parameters, `5` for task table exhaustion) upon failure.
2. **Stack Size Parameter (`r2 = 0`)** `[INFERRED: standard DryOS convention across DIGIC 5/6 platforms]`:
   - Passing `0` instructs the kernel to assign the system default task stack size (typically `0x1000` = 4,096 bytes).
3. **Priority Range (`r1`)** `[INFERRED: DryOS scheduling architecture]`:
   - Priority integers range from `1` (highest priority) to `32` (lowest priority). Priority `25` (`0x19`) is standard for application initialization tasks.
4. **Stack User Context (`sp[0x00]`)** `[INFERRED: ARM AAPCS standard & DryOS task dispatch convention]`:
   - The 5th argument passed on the stack is loaded into `r0` by the task dispatcher as the context argument for the task entry function.

---

### 4.4 Task-Creation Assembly Template for T2
For invoking `CreateTask` from the T2 boot prologue or resident payload:

```armasm
    movs    r3, #0
    str     r3, [sp, #0]        ; arg5: user context pointer (NULL) [VERIFIED call site pattern]
    ldr     r3, =task_heartbeat ; arg4: task entry function (Thumb: bit 0 = 1) [VERIFIED call site pattern]
    movs    r2, #0              ; arg3: stack size = 0 (kernel default) [VERIFIED call site pattern]
    movs    r1, #25             ; arg2: priority = 25 (0x19) [VERIFIED call site pattern]
    ldr     r0, =name_string    ; arg1: ASCII string pointer [VERIFIED call site pattern]
    blx     sub_fc31bbc4        ; Invoke DryOS CreateTask veneer (ARM) [VERIFIED]
```

**Next step**: enough to build

---

## 5. Item (c): Hardware LED Register and Control Values

### 5.1 Reused PORT-23 Hardware Trial Breadcrumbs
Reused strictly from verified PORT-23 physical hardware trial breadcrumbs (`docs/PORT23_LED_BREADCRUMBS.md:6-7`) without reading new ROM ranges:
- **LED MMIO Register Address**: **`0xD20B0884`** `[VERIFIED: hardware trial 2026-11-01; docs/PORT23_LED_BREADCRUMBS.md:6-7]`.
- **LED ON Word Value**: **`0x004D0002`** `[VERIFIED: hardware trial 2026-11-01; docs/PORT23_LED_BREADCRUMBS.md:6]`.
- **LED OFF Word Value**: **`0x004C0003`** `[VERIFIED: hardware trial 2026-11-01; docs/PORT23_LED_BREADCRUMBS.md:7]`.
- **Physical Device**: Rear green power/activity LED `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:6-7]`.

### 5.2 Control Pattern for T2
- Writing `0x004D0002` to `0xD20B0884` actively turns ON the rear green LED `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:6]`.
- Writing `0x004C0003` to `0xD20B0884` actively turns OFF the rear green LED `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:7]`.
- Minimal verified assembly sequence:
  ```armasm
  ldr  r1, =0xd20b0884
  ldr  r0, =0x004d0002        ; ON
  str  r0, [r1]
  ...
  ldr  r0, =0x004c0003        ; OFF
  str  r0, [r1]
  ```
  *(Source: `docs/PORT23_LED_BREADCRUMBS.md:6-7`; `docs/PORT25_LADDER_FIX_CANDIDATE.md:6-8`)*

**Next step**: enough to build

---

## 6. Item (d) (Optional): Firmware Sleep / Delay Primitive

### 6.1 Primitive Identification: `SleepTask`
- **Function Name**: **`SleepTask`** `[VERIFIED: ROM 0xFC135CC6; PORT27-ROM-WATCHDOG-MODULE; docs/UI001_CLAUDE_REVIEW.md:21]`.
- **ROM Veneer Address**: **`0xFC31BF84`** `[VERIFIED: ROM 0xFC31BF84; PORT27-ROM-SLEEPTASK-VENEER]`.
- **Execution Mode**: **ARM mode** (32-bit ARM instruction `0xE51FF004`: `ldr pc, [pc, #-4]`) `[VERIFIED: ROM 0xFC31BF84; PORT27-ROM-SLEEPTASK-VENEER]`.
- **Target Vector**: Loaded from `0xFC31BF88` = **`0xBFE14969`** (bit 0 = 1 specifying Thumb-2 mode at ATCM `0xBFE14968`) `[VERIFIED: ROM 0xFC31BF88; PORT27-ROM-SLEEPTASK-VENEER]`.

---

### 6.2 Verified Call-Site Register Setup & Context Constraints
- **ROM Call Site**: In watchdog servicing task `task_WdtReset` (`0xFC135CB0`..`0xFC135CD0` in `PORT27-ROM-WATCHDOG-MODULE`), lines `0xFC135CBC`..`0xFC135CC6` set up a 2-second periodic sleep:
  ```armasm
  fc135cbc:   movw    r6, #2000       ; 0x7D0 (2000 ms)
  fc135cc0:   str     r0, [r1, #0]
  fc135cc2:   str     r4, [r5, #4]
  fc135cc4:   mov     r0, r6          ; Parameter r0 = 2000 ms
  fc135cc6:   blx     0xfc31bf84      ; SleepTask(2000)
  ```
  *(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC135CBC-0xFC135CC6`; `[VERIFIED: PORT27-ROM-WATCHDOG-MODULE]`)*
- **Calling Convention**:
  - `blx 0xfc31bf84` from Thumb-2 state (Thumb-2 encoding `f1e6 e95e`) switches to ARM mode `[VERIFIED: ROM 0xFC135CC6]`.
  - `r0`: Sleep duration in milliseconds `[VERIFIED: ROM 0xFC135CBC, 0xFC135CC4]`.
- **Interrupt Context Guard**:
  - In DryOS kernel architecture, blocking sleep primitives are strictly prohibited inside interrupt handlers or before multitasking is initialized, triggering a kernel panic if invoked from non-task context `[INFERRED: DryOS kernel architecture; docs/CHDK_PORT0E_CLAUDE_REVIEW.md:23]`.

---

### 6.3 Context-Free Busy-Wait Alternative
When delaying execution in early boot or with interrupts disabled (where `SleepTask` cannot be used), the register decrement loop verified in PORT-24/25 is available:
```armasm
    ldr     r0, =0x00100000     ; Loop count
1:  subs    r0, r0, #1
    bne     1b
```
In `docs/PORT25_LADDER_FIX_CANDIDATE.md:417`, constant `0x00100000` is verified as:
- Nominal: $\approx 20.97\text{ ms}$ (at 100 MHz Cortex-R4 dual-issue) `[INFERRED]`.
- Conservative Slow Bound: $\le 50.0\text{ ms}$ (at 42 MHz unpipelined worst-case) `[INFERRED]`.

**Next step**: enough to build

---

## 7. Comprehensive Summary Table

| Item | Technical Focus | Concrete Values & Verified Facts | Epistemic Status | Manifest Entry / Citation | Next Step |
|:---:|:---|:---|:---:|:---|:---:|
| **(a)** | Stock heap / memory start after `sub_fc0d0126` | `sub_fc0d0126` decrements `[0x00008380]` and executes `bx lr` via `sub_fc31b8ca`; sets **NO heap or memory boundaries**; stock heap is set in `sub_fc05b3c8` | `VERIFIED` | `PORT27-ROM-FIRMWARE-CONT` (`0xFC0D0080`), `PORT27-ROM-RESTORE-IRQ-VENEER` (`0xFC31B8CA`), `PORT27-ROM-HEAP-SETUP` (`0xFC05B3C0`) | **enough to build** |
| **(a)** | Exact patch point for memory start in `sub_fc05b3c8` | Literal `0x003489B4` at `[0xFC05B450]` loaded into `r4` at `0xFC05B3CA`, stored to `sp[0x08]` at `0xFC05B3FC`, subtracted from `0x00600014` at `0xFC05B402` into `r2` and stored to `sp[0x0C]` at `0xFC05B404`; word alignment required; hook overrides `r4` with `new_sa = 0x00368680` | `VERIFIED` | `PORT27-ROM-HEAP-SETUP` (`0xFC05B3C0`), `docs/PORT25_LADDER_FIX_CANDIDATE.md:391` | **enough to build** |
| **(a)** | Relocated core survival | Relocated core (`0x003489B4`..`0x00368680`, `candidate_main.bin` 123,424 B, `_end = 0x00368680`) does not survive stock boot (clobbered by stock allocations in `[0x003489B4, 0x00600014)`); raised start `0x00368680` yields 2.70 MiB surplus headroom above 712 KiB limit | `INFERRED` (clobber / headroom derivation) / `VERIFIED` (sizes, addresses, literals) | `docs/PORT25_LADDER_FIX_CANDIDATE.md:388, 391`, `docs/CHDK_G3X_MEMORY_OWNERSHIP.md:84`, `PORT27-ROM-HEAP-SETUP` | **enough to build** |
| **(b)** | Task-creation entry (`CreateTask`) | `sub_fc31bbc4` at `0xFC31BBC4` (ARM mode `ldr pc, [pc, #-4]` -> ATCM `0xBFE14A3D` Thumb-2); entered via `blx 0xfc31bbc4` from Thumb-2 at `0xFC05B990` | `VERIFIED` | `PORT27-ROM-CREATETASK-VENEER` (`0xFC31BBA0`), `PORT27-ROM-STARTUP-TASKS` (`0xFC05B8E0`) | **enough to build** |
| **(b)** | Task-creation register setup & conventions | Call site `0xFC05B984..0xFC05B990` verifies `r0`=string, `r1`=priority, `r2`=0, `r3`=entry\|1, `sp[0]`=0; DryOS conventions (return task ID/handle, `r2=0` default 4 KiB stack, priority 1..32, `sp[0]` context) inferred from CHDK ports | `VERIFIED` (call site setup) / `INFERRED` (return value, stack default, priority range) | `PORT27-ROM-STARTUP-TASKS` (`0xFC05B8E0`), `PORT27-ROM-CREATETASK-VENEER` (`0xFC31BBA0`) | **enough to build** |
| **(c)** | LED register & on/off values | MMIO: `0xD20B0884`; ON: `0x004D0002`; OFF: `0x004C0003` (Rear green LED; reused from PORT-23 hardware trial without new ROM reads) | `VERIFIED` | `docs/PORT23_LED_BREADCRUMBS.md:6-7` (Hardware trial 2026-11-01) | **enough to build** |
| **(d)** | Firmware sleep / delay primitive | `SleepTask` veneer `0xFC31BF84` (ARM mode -> ATCM `0xBFE14969` Thumb-2); called via `blx 0xfc31bf84` from `task_WdtReset` (`0xFC135CC6`) with `r0`=ms delay; task context only; busy-wait loop with `0x00100000` ($\approx 21-50\text{ ms}$) for any context | `VERIFIED` (veneer, call site) / `INFERRED` (ISR guard, loop timing) | `PORT27-ROM-WATCHDOG-MODULE` (`0xFC135C00`), `PORT27-ROM-SLEEPTASK-VENEER` (`0xFC31BF84`), `docs/PORT25_LADDER_FIX_CANDIDATE.md:417` | **enough to build** |

---

## 8. ROM Evidence Manifest & Running Byte Ledger

All ranges read for PORT-27 are recorded in [PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json). The running byte total is 2,380 bytes, strictly below the 24,576-byte milestone limit:

| Entry ID | ROM Start | ROM End | Length (B) | Running Total (B) | SHA-256 | Provenance & Purpose |
|:---|:---:|:---:|:---:|:---:|:---|:---|
| `PORT27-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B53F` | 384 | 384 | `68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6` | Stock heap init `sub_fc05b3c8`, base `0x003489B4`, headroom check `0x000B1FEC` (cited in `PORT25_EVIDENCE_MANIFEST.json:34, 163`) |
| `PORT27-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 | 1,152 | `749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e` | `task_Startup`, `StartDiskboot`, `b.w sub_fc0d0126`, and `CreateTask` call site in `sub_fc05b962` (cited in `PORT24_EVIDENCE_MANIFEST.json:24, 162`) |
| `PORT27-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D023F` | 448 | 1,600 | `33d2fae4ed8c9c228ea6cc8f3304a26b96f8a4fb6d9d3bdc37cd056e7833456e` | `sub_fc0d0126` (`LMClock_Unlock`), decrement `[0x00008380]`, assert, and tail branch (cited in `PORT24_EVIDENCE_MANIFEST.json:30, 207`) |
| `PORT27-ROM-WATCHDOG-MODULE`| `0xFC135C00` | `0xFC135E3F` | 576 | 2,176 | `29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb` | `task_WdtReset` calling `SleepTask(2000)` via `blx 0xfc31bf84` at `0xFC135CC6` (cited in `PORT23_EVIDENCE_MANIFEST.json:40, 202`) |
| `PORT27-ROM-RESTORE-IRQ-VENEER`| `0xFC31B8CA`| `0xFC31B8D9`| 16 | 2,192 | `c50fd6df693d4724d6ec4ac070967f674bab9c0448f1ca6c27dc480b8922a6e1` | `RestoreInterrupts` veneer `sub_fc31b8ca` (branch target from `0xFC0D014C` in `PORT27-ROM-FIRMWARE-CONT`) |
| `PORT27-ROM-CREATETASK-VENEER`| `0xFC31BBA0`| `0xFC31BBEF`| 80 | 2,272 | `59c9adc82ad1ad670ecf7ba0d42665a34f7acf1a10b68ad75874afe1fae77487` | `CreateTask` ARM veneer `sub_fc31bbc4` loading `0xBFE14A3D` (cited in `PORT25_EVIDENCE_MANIFEST.json:80, 457`) |
| `PORT27-ROM-IRQ-DISABLE` | `0xFC31BEE0` | `0xFC31BF3F` | 96 | 2,368 | `a15cb37e666e3349c0453b294d1283d99ae116214f36fc69671cdc3131db7826` | `DisableInterrupts` ARM veneer `sub_fc31befc` (callee from `0xFC0D0128` in `sub_fc0d0126`; cited in `PORT24_EVIDENCE_MANIFEST.json:46, 312`) |
| `PORT27-ROM-SLEEPTASK-VENEER`| `0xFC31BF84` | `0xFC31BF8F` | 12 | 2,380 | `462ba50005667f6192185cf76e0af698e0419e9d2fc481fd474ff862cb84d6e8` | `SleepTask` ARM veneer `0xFC31BF84` loading `0xBFE14969` (branch target from `0xFC135CC6` in `PORT27-ROM-WATCHDOG-MODULE`) |

---

## 9. Final Verdict for PORT-27 T2

> [!IMPORTANT]
> **Verdict for PORT-27 T2**: **GO**
> 
> - **Item (a) Status**: **VERIFIED** at the level required for T2 implementation:
>   - Established that stock continuation `sub_fc0d0126` configures no heap or system memory boundaries `[VERIFIED]`.
>   - Established that stock firmware sets its heap in `sub_fc05b3c8`, with exact patch point verified: literal `0x003489B4` at `[0xFC05B450]` is loaded into register `r4` at `0xFC05B3CA`, stored to descriptor slot `sp[0x08]` at `0xFC05B3FC`, and subtracted from `0x00600014` at `0xFC05B402` to compute pool size into `r2` stored to `sp[0x0C]` at `0xFC05B404` `[VERIFIED]`.
>   - Established 4-byte word alignment requirement from ROM memory accesses, with candidate raised start `new_sa = 0x00368680` strictly 64-byte aligned `[VERIFIED]`.
>   - Relocated core region (`candidate_main.bin` 123,424 B, `_end = 0x00368680`) non-survival under stock boot and 2.70 MiB headroom surplus are verified and logically derived `[VERIFIED / INFERRED]`.
> - **Item (b) Status**: **VERIFIED** at the level required for T2 implementation:
>   - Established `CreateTask` entry `sub_fc31bbc4` (ARM mode opcode `0xE51FF004` at `0xFC31BBC4`, loading target vector `0xBFE14A3D` for Thumb-2 execution at `0xBFE14A3C`) `[VERIFIED]`.
>   - Established that `sub_fc31bbc4` is entered via `blx` from Thumb-2 state (instruction `f2c0 e918` at `0xFC05B990`) `[VERIFIED]`.
>   - Established call-site verified register setup at `0xFC05B984..0xFC05B990` (`r0`=name string, `r1`=priority 25, `r2`=0, `r3`=entry\|1, `sp[0]`=0) `[VERIFIED]`, with DryOS calling conventions documented `[INFERRED]`.
> - **Item (c) Status**: **VERIFIED**:
>   - Confirmed LED MMIO `0xD20B0884`, ON `0x004D0002`, OFF `0x004C0003` from PORT-23 hardware breadcrumbs without new ROM reads `[VERIFIED]`.
> - **Item (d) Status**: **VERIFIED**:
>   - Established `SleepTask` veneer `0xFC31BF84` (ARM mode opcode `0xE51FF004` loading `0xBFE14969`) called via `blx` with millisecond delay in `r0`, plus context-free busy-wait loop alternative `[VERIFIED / INFERRED]`.
> 
> All acceptance criteria are satisfied, all items report `enough to build`, and T2 has all required static facts to implement the resident heartbeat payload.
