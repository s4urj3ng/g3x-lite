# PORT-27 T1: Resident Heap/Memory-Start, Task-Creation, and LED Evidence

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Firmware Dump Provenance**: `firmware/dumps/GM1.10C/PRIMARY.BIN` (33,554,432 bytes, mapped base `0xFC000000`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:40]`
- **Base Baseline**: `origin/main` post-`PORT-26` merge (`docs/PORT26_CODE43_RECORD.md`, `docs/PORT25_LADDER_FIX_CANDIDATE.md`) `[VERIFIED]`
- **ROM Inspection Policy Compliance**:
  - Max slice length: 768 bytes (budget limit $\le 4,096$ bytes) `[VERIFIED]`.
  - Total bytes read: 2,380 bytes across 8 slices (milestone budget $\le 24,576$ bytes) `[VERIFIED]`.
  - Zero out-of-policy bytes read: all 8 slices start at addresses cited with evidence in PORT-23/24/25 manifests or are branch targets verified inside approved ranges `[VERIFIED]`.
  - Zero proprietary ROM binary bytes, disassembly dumps, or camera payload binaries committed `[VERIFIED]`.
  - Machine-readable manifest: [PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json) validated via `tools/port11c_evidence_validator.py` `[VERIFIED]`.

---

## 1. Executive Summary & Epistemic Standards

This dossier establishes the structural evidence base for **PORT-27 T2 (Resident Heartbeat)** on the Canon PowerShot G3 X (GM1.10C). It provides static ROM disassembly evidence and empirical hardware trial citations addressing four core technical prerequisites:
1. **Item (a) — Stock Firmware Heap / System Memory Start & Relocated Core Survival**: Analysis of stock continuation `sub_fc0d0126` establishing that `sub_fc0d0126`'s own instructions set no heap bounds (`[VERIFIED]`) while the behaviour of the ATCM IRQ disable/restore routines is `[INFERRED/UNKNOWN]` (not read; outside PORT-27 policy), analysis of where stock firmware sets its heap in `sub_fc05b3c8`, verification of the exact patch point where the `0x003489B4` literal (`[0xFC05B450]`) is loaded and passed, and definition of the raised memory start (`0x00368680`).
2. **Item (b) — DryOS Task Creation Entry & Calling Convention**: Identification of `_CreateTask` entry `sub_fc31bbc4` (ARM mode) entered via `blx` from Thumb-2, call-site verified register values at `0xFC05B984..0xFC05B990`, and determination that parameter semantics (specifically stack size parameter `r2`) remain unproven in ROM and reside in ATCM (`0xBFE14A3C`, out of policy), yielding a strict NO-GO verdict for T2.
3. **Item (c) — Hardware LED Register & Control Values**: Reused strictly from PORT-23 hardware breadcrumbs (MMIO `0xD20B0884`, ON `0x004D0002`, OFF `0x004C0003`) without reading new ROM bytes.
4. **Item (d) (Optional) — Firmware Sleep / Delay Primitive**: Identification of `SleepTask` veneer `0xFC31BF84` (ARM mode) called via `blx` from `task_WdtReset` at `0xFC135CC6`, millisecond delay parameter in `r0`, and context-free busy-wait loop alternative.

### Epistemic Classifications
In accordance with the project charter, all findings in this document are strictly classified using three epistemic labels:
- **`[VERIFIED]`**: Claims directly corroborated by ROM disassembly opcodes/literals in `firmware/dumps/GM1.10C/PRIMARY.BIN` within approved slices, concrete tracked repository source files/lines, or documented physical hardware trial results. Note: In the machine-readable evidence manifest ([PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json)), the schema-defined value `STATIC_VERIFIED` represents static ROM-verified evidence and is treated as exactly equivalent to **`[VERIFIED]`** in this document.
- **`[INFERRED]`**: Deductions logically derived from verified static facts, mathematical arithmetic, or architectural DryOS conventions documented in established CHDK platform ports.
- **`[UNKNOWN]`**: Unobserved, undetermined, or runtime-dependent behaviors requiring future empirical measurement or out-of-scope ROM exploration.

---

## 2. ROM Read Policy Authorization & Prior Range Citations

### 2.1 Prior Evidence Citations for ROM Slices
The ROM read policy mandates that every inspection slice must start at an address already cited with evidence in PORT-23/24/25 documentation or manifests, or at a verified branch target inside such a range. All eight examined ranges strictly satisfy this policy.

#### Authorization Matrix: Range Start $\to$ Authorizing File:Line $\to$ Literal Text
| Range Start Address | Evidence ID | Authorizing File:Line | Literal Text Found on Cited Line |
|:---:|:---|:---|:---|
| `0xFC05B3C0` | `PORT27-ROM-HEAP-SETUP` | `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:14`<br>`docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:162` | `"start_address": "0xFC05B3C0",`<br>`"start_address": "0xFC05B3C0",` |
| `0xFC05B8E0` | `PORT27-ROM-STARTUP-TASKS` | `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:14`<br>`docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:152` | `"start_address": "0xFC05B8E0",`<br>`"start_address": "0xFC05B8E0",` |
| `0xFC0D0080` | `PORT27-ROM-FIRMWARE-CONT` | `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:29`<br>`docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:197` | `"start_address": "0xFC0D0080",`<br>`"start_address": "0xFC0D0080",` |
| `0xFC135C00` | `PORT27-ROM-WATCHDOG-MODULE`| `docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:49`<br>`docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:192` | `"start_address": "0xFC135C00",`<br>`"start_address": "0xFC135C00",` |
| `0xFC31B8CA` | `PORT27-ROM-RESTORE-IRQ-VENEER` | `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC0D014C`<br>(branch target in `PORT27-ROM-FIRMWARE-CONT`) | `fc0d014c:   b.w     0xfc31b8ca          ; Tail branch to RestoreInterrupts veneer` |
| `0xFC31BBA0` | `PORT27-ROM-CREATETASK-VENEER` | `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:109`<br>`docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:447` | `"start_address": "0xFC31BBA0",`<br>`"start_address": "0xFC31BBA0",` |
| `0xFC31BEE0` | `PORT27-ROM-IRQ-DISABLE` | `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:64`<br>`docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:303` | `"start_address": "0xFC31BEE0",`<br>`"start_address": "0xFC31BEE0",` |
| `0xFC31BF84` | `PORT27-ROM-SLEEPTASK-VENEER` | `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC135CC6`<br>(branch target in `PORT27-ROM-WATCHDOG-MODULE`) | `fc135cc6:   blx     0xfc31bf84      ; SleepTask(2000)` |

#### Detailed Evidence Citations per Range:
1. **`0xFC05B3C0` (`PORT27-ROM-HEAP-SETUP`, 384 B)**:
   - Allowed Start Address: `0xFC05B3C0` cited in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:14` (`"start_address": "0xFC05B3C0",`), line 160 (`"evidence_id": "PORT25-ROM-HEAP-SETUP",`), and line 162 (`"start_address": "0xFC05B3C0",`).
   - Documentation Citations: `docs/PORT25_SHORT_PRESS_LOCALISE.md:386` (`| `PORT25-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B53F` | 384 B |`); `docs/PORT21_RAM_LIFETIME.md:308` (`| `PORT21-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B53F` | 384 |`); `docs/CHDK_PORT2C_EXECUTION_LEDGER.md:48` (cites routine `sub_fc05b3c8` at `0xFC05B3C8`).
2. **`0xFC05B8E0` (`PORT27-ROM-STARTUP-TASKS`, 768 B)**:
   - Allowed Start Address: `0xFC05B8E0` cited in `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:14` (`"start_address": "0xFC05B8E0",`), line 150 (`"evidence_id": "PORT24-ROM-STARTUP-TASKS",`), and line 152 (`"start_address": "0xFC05B8E0",`).
   - Additional Citations: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:24` (`"start_address": "0xFC05B8E0",`), line 191 (`"evidence_id": "PORT25-ROM-STARTUP-TASKS",`), line 192 (`"start_address": "0xFC05B8E0",`); `docs/PORT24_LOADER_TRACE.md:803` (`| `PORT24-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 B |`); `docs/PORT25_SHORT_PRESS_LOCALISE.md:388` (`| `PORT25-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 B |`); `docs/PORT23_POWER_SUPERVISION.md:44, 361` (`| `PORT23-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 B |`).
3. **`0xFC0D0080` (`PORT27-ROM-FIRMWARE-CONT`, 448 B)**:
   - Allowed Start Address: `0xFC0D0080` cited in `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:29` (`"start_address": "0xFC0D0080",`), line 196 (`"evidence_id": "PORT24-ROM-FIRMWARE-CONT",`), and line 197 (`"start_address": "0xFC0D0080",`).
   - Additional Citations: `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:59` (`"start_address": "0xFC0D0080",`), line 296 (`"evidence_id": "PORT25-ROM-FIRMWARE-CONT",`), line 297 (`"start_address": "0xFC0D0080",`); `docs/PORT24_LOADER_TRACE.md:21, 294, 648, 806` (`| `PORT24-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D023F` | 448 B |`); `docs/PORT25_SHORT_PRESS_LOCALISE.md:177, 395` (`| `PORT25-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D023F` | 448 B |`).
4. **`0xFC135C00` (`PORT27-ROM-WATCHDOG-MODULE`, 576 B)**:
   - Allowed Start Address: `0xFC135C00` cited in `docs/agentbridge/PORT23_EVIDENCE_MANIFEST.json:49` (`"start_address": "0xFC135C00",`), line 191 (`"evidence_id": "PORT23-ROM-WATCHDOG-MODULE",`), and line 192 (`"start_address": "0xFC135C00",`).
   - Additional Citations: `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:59` (`"start_address": "0xFC135C00",`), line 286 (`"evidence_id": "PORT24-ROM-WATCHDOG-MODULE",`), line 287 (`"start_address": "0xFC135C00",`); `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:94` (`"start_address": "0xFC135C00",`), line 401 (`"evidence_id": "PORT25-ROM-WATCHDOG-MODULE",`), line 402 (`"start_address": "0xFC135C00",`); `docs/PORT23_POWER_SUPERVISION.md:182, 368` (`| `PORT23-ROM-WATCHDOG-MODULE` | `0xFC135C00` | `0xFC135E3F` | 576 B |`); `docs/PORT24_LOADER_TRACE.md:812` (`| `PORT24-ROM-WATCHDOG-MODULE` | `0xFC135C00` | `0xFC135E3F` | 576 B |`); `docs/PORT25_SHORT_PRESS_LOCALISE.md:402` (`| `PORT25-ROM-WATCHDOG-MODULE` | `0xFC135C00` | `0xFC135E3F` | 576 B |`).
5. **`0xFC31B8CA` (`PORT27-ROM-RESTORE-IRQ-VENEER`, 16 B)**:
   - Branch target of instruction `0xFC0D014C: b.w 0xfc31b8ca` verified inside `PORT27-ROM-FIRMWARE-CONT` (`0xFC0D0080..0xFC0D023F`) `[VERIFIED]`.
6. **`0xFC31BBA0` (`PORT27-ROM-CREATETASK-VENEER`, 80 B)**:
   - Allowed Start Address: `0xFC31BBA0` cited in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:109` (`"start_address": "0xFC31BBA0",`), line 445 (`"evidence_id": "PORT25-ROM-CREATETASK-VENEER",`), and line 447 (`"start_address": "0xFC31BBA0",`).
   - Additional Citations: `docs/PORT25_SHORT_PRESS_LOCALISE.md:405` (`| `PORT25-ROM-CREATETASK-VENEER` | `0xFC31BBA0` | `0xFC31BBEF` | 80 B |`).
7. **`0xFC31BEE0` (`PORT27-ROM-IRQ-DISABLE`, 96 B)**:
   - Allowed Start Address: `0xFC31BEE0` cited in `docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:64` (`"start_address": "0xFC31BEE0",`), line 301 (`"evidence_id": "PORT24-ROM-IRQ-DISABLE",`), and line 303 (`"start_address": "0xFC31BEE0",`).
   - Additional Citations: `docs/PORT24_LOADER_TRACE.md:813` (`| `PORT24-ROM-IRQ-DISABLE` | `0xFC31BEE0` | `0xFC31BF3F` | 96 B |`).
8. **`0xFC31BF84` (`PORT27-ROM-SLEEPTASK-VENEER`, 12 B)**:
   - Branch target of instruction `0xFC135CC6: blx 0xfc31bf84` verified inside `PORT27-ROM-WATCHDOG-MODULE` (`0xFC135C00..0xFC135E3F`) `[VERIFIED]`.

### 2.2 Policy Accounting & Ledger Invariance
All 5 range start addresses (`0xFC05B3C0`, `0xFC05B8E0`, `0xFC0D0080`, `0xFC31BBA0`, `0xFC31BEE0`) are directly cited in PORT-23/24/25 manifests, the two branch targets (`0xFC31B8CA`, `0xFC31BF84`) are verified inside cited ranges, and `0xFC135C00` is cited across all three prior manifests.

Consequently, exactly zero out-of-policy bytes were read. All 2,380 bytes across the 8 slices are strictly authorized and within the 24,576-byte milestone budget:
- Total slices read: 8
- Maximum slice length: 768 bytes ($\le 4,096$ B)
- Total milestone ROM bytes read: 2,380 bytes ($\le 24,576$ B)
- Out-of-policy bytes: 0 bytes (0.0%) `[VERIFIED]`

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
1. **Inspected Instructions in `sub_fc0d0126`**: Within approved slice `PORT27-ROM-FIRMWARE-CONT`, `sub_fc0d0126`'s own instructions (`0xFC0D0126`..`0xFC0D014E`) execute:
   - `0xFC0D0128: blx 0xfc31befc` calling the ARM interrupt disable veneer `sub_fc31befc` (`[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`).
   - Decrement of the clock lock counter at `0x00008380` (`[VERIFIED: ROM 0xFC0D012C-0xFC0D0144; PORT27-ROM-FIRMWARE-CONT]`). It pairs functionally with lock function `sub_fc0d0110` (`LMClock_Lock`) `[INFERRED: ROM 0xFC0D0110-0xFC0D0124]`.
   - Register restore `{r4, r5, r6, lr}` via `ldmia.w sp!, ...` at `0xFC0D0148` (`[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`).
   - `0xFC0D014C: b.w 0xfc31b8ca` tail branch to RestoreInterrupts veneer `sub_fc31b8ca` (`[VERIFIED: PORT27-ROM-FIRMWARE-CONT]`).
2. **Inspected Veneers**:
   - The veneer at `0xFC31BEFC` loads `pc` with target vector `0xBFE14FE7` via ARM instruction `ldr pc, [pc, #-4]` (`[VERIFIED: ROM 0xFC31BEFC; PORT27-ROM-IRQ-DISABLE]`).
   - The veneer at `0xFC31B8CA` loads `ip` with `0xBFE14FEB` and executes `bx ip` (`[VERIFIED: ROM 0xFC31B8CA-0xFC31B8D2; PORT27-ROM-RESTORE-IRQ-VENEER]`).
3. **ATCM Destination Routines (Unread / Outside Policy)**:
   - Slices read in PORT-27 contain only the veneers, not the ATCM implementations.
   - The full behaviour of the ATCM IRQ disable and restore routines (`0xBFE14FE7` and `0xBFE14FEB`)—including their full effects, whether they return via `bx lr` to the DryOS task dispatcher to terminate `task_Startup`, and confirming whether the path through them performs any heap or memory-start operations—is **`[INFERRED/UNKNOWN: not read; outside PORT-27 policy]`**.
4. **Item (a) Boundary Assessment**:
   - **`sub_fc0d0126`'s own instructions set no heap bounds (VERIFIED); the behaviour of the ATCM IRQ disable/restore routines is INFERRED/UNKNOWN (not read; outside PORT-27 policy)**.
   - Specifically, `sub_fc0d0126`'s own instruction stream modifies only the reference counter at `0x00008380` and calls the veneers; it configures no memory descriptors, allocates no memory, and sets no system boundaries `[VERIFIED]`.

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
- **Heap-Start Alignment Requirement**: **`[UNKNOWN]`**. The cited instructions (`0xFC05B3FC: stmia.w sp, {r0, r1, r4}` and `0xFC05B402: subs r2, r1, r4`) store the heap address value into the stack descriptor block as data and perform arithmetic subtraction. Neither routine `sub_fc05b3c8` nor the descriptor stores prove any alignment requirement on the heap start address itself.
- **Arithmetic Alignment Fact**: The candidate raised start `0x00368680` is strictly 64-byte aligned as a mathematical fact (`0x00368680 % 64 == 0` and `0x00368680 % 4 == 0`).

---

### 3.3 Relocated Core Region Survival & Headroom Derivation
- **Base Relocation Address**: `MEMISOSTART = 0x003489B4` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:8; tools/port18_trial_preflight.py:61]`.
- **Component Breakdown & `_end` Confirmation**:
  - **PORT-25 Combined Candidate** (`docs/PORT25_LADDER_FIX_CANDIDATE.md:387-393`):
    - Relocated Core Binary (`candidate_main.bin`): `123,424` bytes (`0x1E220`) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:388]`.
    - Span of `candidate_main.bin`: `0x003489B4` to `0x00366BD4` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:388]`.
    - Witness Symbol (`boot_witness`): `0x00361170` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:390]`.
    - Reservation End Symbol (`_end`): **`0x00368680`** `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
    - Loader Binary (`candidate_loader.bin`): `124,864` bytes `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:389]`.
    - Encoded DISKBOOT Image (`DISKBOOT.BIN`): `124,865` bytes `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:385, 392]`.
  - **Default Control Baseline** (`docs/PORT23_LED_BREADCRUMBS.md:21-26; docs/PORT25_LADDER_FIX_CANDIDATE.md:381`):
    - Baseline Core Binary (`candidate_main.bin`): `116,816` bytes (SHA-256 `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e`) `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:25]`.
    - Witness Symbol (`boot_witness`): `0x0035F7A0` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:26]`.
    - Baseline End Symbol (`_end`): **`0x00366CB0`** `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:26; tools/validate_candidate_port2a.py:51]`.
    - Baseline Loader Binary (`candidate_loader.bin`): `118,000` bytes `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:24]`.
    - Baseline Encoded DISKBOOT Image (`DISKBOOT.BIN`): `118,001` bytes `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:22; docs/PORT25_LADDER_FIX_CANDIDATE.md:381]`.

#### Survival Analysis: Stock Initialization vs Candidate Shifted Memory Start
- **Under Stock Boot (Unshifted Heap Initialization)**:
  - Stock DryOS initializes its dynamic memory heap starting at literal `0x003489B4` (`[0xFC05B450]`) up to `0x00600014` (`[0xFC05B474]`) `[VERIFIED: ROM 0xFC05B450, 0xFC05B474; PORT27-ROM-HEAP-SETUP]`.
  - The unshifted stock heap span `[0x003489B4, 0x00600014)` encompasses the relocated core region (`0x003489B4`..`0x00368680`).
  - As analyzed in `docs/PORT21_RAM_LIFETIME.md:44-47`, dynamic memory allocations requested by early firmware tasks *may* allocate blocks starting from `0x003489B4` upward and overwrite the relocated core.
  - However, no specific overwrite instruction, store sequence, or allocation trace covering that exact address range has been cited from the approved ROM slices.
  - Therefore, non-survival of the relocated core under unmodified stock boot is **`[INFERRED]`**, NOT `[VERIFIED]`.
- **Under Actual PORT-25 Combined Candidate (Shifted Memory Start)**:
  - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:24`, the dynamic reservation boundary is defined as `const char * const new_sa = &_end;`, pointing to `0x00368680` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24]`.
  - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:177-178`, the candidate boot hook `sub_fc05b3c8_my` loads `new_sa` into register `r4`:
    ```c
    "    ldr     r4, =new_sa\n"
    "    ldr     r4, [r4]\n"
    ```
  - In `chdk-port/platform/g3x/sub/110c/boot_prototype.c:212-215`, `r4` is stored to stack descriptor slot `sp[0x08]` and the sub-pool length `sp[0x0C]` is adjusted accordingly:
    ```c
    "    stm.w   sp, {r0, r1, r4}\n"       // sp[0x08] = new_sa (SHIFTED HEAP BASE!)
    "    ldr     r1, =0x00600014\n"        // Sub-pool 1 boundary
    "    subs    r2, r1, r4\n"             // sp[0x0C] = 0x00600014 - new_sa (HEAP SIZE!)
    "    strd    r2, r1, [sp, #0xc]\n"
    ```
  - **VERIFIED Exclusion**: Overriding `r4` with `new_sa = 0x00368680` sets the DryOS heap base strictly past `_end`. This strictly excludes the relocated core region `[0x003489B4, 0x00368680)` from stock DryOS heap pool 1 allocations `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 177-178, 212-215; docs/PORT21_RAM_LIFETIME.md:40-41]`.
  - **INFERRED Runtime Survival**: That the relocated core region survives during runtime under this shifted configuration is **`[INFERRED]`** `[docs/PORT21_RAM_LIFETIME.md:42]`.
  - **Scope of Protection (What It Does and Does Not Rule Out)**:
    - *What it rules out*: Raising the heap start strictly rules out overwrites by stock DryOS dynamic heap allocations servicing firmware tasks out of heap pool 1 `[VERIFIED exclusion]`.
    - *What it does NOT rule out*: Raising the heap start does *not* guarantee survival against all memory corrupters. It does not rule out other users of that RAM region, such as direct physical DMA transfers (e.g., sensor, image processing, or SD controller DMA buffers), memory-mapped hardware buffers / framebuffers, unmanaged kernel stack overflows, secondary memory pools, or hardcoded pointer stores elsewhere in stock firmware `[UNKNOWN; docs/PORT21_RAM_LIFETIME.md:43]`.

#### Raised Heap Start & Headroom Derivation
To prevent heap collisions and guarantee survival of the relocated core against heap allocations:
- **Required Raised Start (`new_sa`)**: **`0x00368680`** (`_end` of PORT-25 combined candidate) `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
- **Mathematical Headroom Derivation for PORT-25 Candidate** `[INFERRED: derived from verified ROM literals and candidate _end]`:
  - Input: Heap upper limit = `0x006CE000` `[VERIFIED: ROM literal 0xFC05B454; PORT27-ROM-HEAP-SETUP]`.
  - Input: Minimum headroom constant = `0x000B1FEC` = 729,068 bytes `[VERIFIED: ROM literal 0xFC05B458; PORT27-ROM-HEAP-SETUP]`.
  - Input: Raised memory start = `0x00368680` `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:391]`.
  - Available Free RAM:
    $$\text{Free RAM} = 0x006CE000 - 0x00368680 = 0x00365980 \text{ bytes (3,561,856 B } \approx 3,478\text{ KiB)}$$
  - Headroom Test at `0xFC05B3D4`:
    $$0x00365980 \ge 0x000B1FEC \quad (3,561,856 \ge 729,068) \implies \text{PASS}$$
  - Surplus Safety Margin:
    $$\text{Surplus} = 0x00365980 - 0x000B1FEC = 0x002B3994 \text{ bytes (2,832,788 B } \approx 2.70\text{ MiB)}$$
- **Mathematical Headroom Derivation for Baseline Core** `[INFERRED: derived from verified ROM literals and baseline _end]`:
  - Input: Baseline memory start = `0x00366CB0` `[VERIFIED: docs/PORT23_LED_BREADCRUMBS.md:26]`.
  - Available Free RAM:
    $$\text{Free RAM} = 0x006CE000 - 0x00366CB0 = 0x00367350 \text{ bytes (3,568,464 B } \approx 3,485\text{ KiB)}$$
  - Surplus Safety Margin:
    $$\text{Surplus} = 0x00367350 - 0x000B1FEC = 0x002B5364 \text{ bytes (2,839,396 B } \approx 2.71\text{ MiB)}$$
  Both candidate and baseline shifted heaps satisfy the ROM headroom requirement with $\ge 2.70$ MiB of surplus headroom.

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

#### Strict Epistemic Classification of Call-Site Facts
The **ONLY** facts strictly proven by this ROM call site and its veneer target are:
1. **Values and Register Setup Passed to the Veneer** `[VERIFIED: ROM 0xFC05B984-0xFC05B98E]`:
   - `r0`: address `0xFC05B9A0` (points to ASCII string `"Startup\0"`).
   - `r1`: integer literal `25` (`0x19`).
   - `r2`: integer literal `0`.
   - `r3`: address `0xFC05B8FD` (entry address of `task_Startup` with Thumb bit 0 set).
   - `sp[0x00]`: integer literal `0` stored on stack before the call.
2. **Branch Instruction** `[VERIFIED: ROM 0xFC05B990]`:
   - `blx 0xfc31bbc4` branches from Thumb-2 state into the ARM-mode veneer `sub_fc31bbc4`.
3. **Veneer Target** `[VERIFIED: ROM 0xFC31BBC8]`:
   - Veneer vector loaded from `0xFC31BBC8` is `0xBFE14A3D`, branching to Thumb-2 code at ATCM address `0xBFE14A3C`.
4. **Task Entry Point Role of `r3`** `[VERIFIED]`:
   - That `r3` serves as the task entry point function address is directly verified because `0xFC05B8FC` is the verified entry point of `task_Startup` executed by the spawned task `[VERIFIED: PORT27-ROM-STARTUP-TASKS]`.

---

### 4.3 Re-labelling What the Call Site Does NOT Prove

Everything beyond the raw register values and entry address `r3` is **not proven** by the call site. In accordance with strict epistemic standards, each aspect is classified below:

1. **`r0` Parameter Role (Task Name Pointer)**:
   - *What the call site proves*: `r0` is passed the address `0xFC05B9A0` pointing to `"Startup\0"` `[VERIFIED]`.
   - *What the call site does NOT prove*: That `r0` is strictly required to be a valid name string, whether the string is copied or referenced by pointer, or whether a NULL pointer is tolerated.
   - *Classification*: **`[INFERRED: DryOS CHDK platform convention; e.g. chdk-port/platform/g3x/sub/110c/boot_prototype.c:369]`**.
2. **`r1` Parameter Meaning (Task Priority)**:
   - *What the call site proves*: Value `25` (`0x19`) is passed in `r1` `[VERIFIED]`.
   - *What the call site does NOT prove*: That `r1` represents scheduling priority, the valid priority integer range (e.g., 1..32 vs 0..255), or whether lower numbers indicate higher priority.
   - *Classification*: **`[INFERRED: standard DryOS priority conventions documented across CHDK ports (e.g. SX60HS, G7X)]`**.
3. **`r2` Parameter Meaning (Stack Size & Default Stack Selection)**:
   - *What the call site proves*: Value `0` is passed in `r2` `[VERIFIED]`.
   - *What the call site does NOT prove*: What parameter `r2` actually controls. Specifically, whether `r2` represents a byte stack size, whether passing `0` instructs the kernel to allocate a default stack (e.g. 4 KiB), or whether `task_Startup` operates with no stack or an externally allocated stack.
   - *Classification*: **`[UNKNOWN: not proven by ROM call site]`** (historically **`[INFERRED: CHDK DryOS platform conventions]`**, but completely unverified on GM1.10C).
4. **`sp[0x00]` Parameter Meaning (Fifth Argument / User Context)**:
   - *What the call site proves*: Value `0` is pushed to `sp[0]` `[VERIFIED]`.
   - *What the call site does NOT prove*: What the fifth argument represents (e.g. user argument passed to the task entry function in `r0`, creation flags, or task attributes block).
   - *Classification*: **`[UNKNOWN: not proven by ROM call site]`** (historically **`[INFERRED: AAPCS calling standard & DryOS task dispatcher convention]`**).
5. **Return-Value & Error Semantics**:
   - *What the call site proves*: Address `0xFC05B994` executes `movs r0, #0` immediately upon return, unconditionally discarding any return value produced by `sub_fc31bbc4` `[VERIFIED: ROM 0xFC05B994]`.
   - *What the call site does NOT prove*: What `CreateTask` returns on success (task ID handle vs status code) or failure (error code vs null), or whether task creation failures trigger an internal kernel panic.
   - *Classification*: **`[UNKNOWN: requires inspecting function implementation at 0xBFE14A3C]`**.
6. **ISR and Execution Context Constraints**:
   - *What the call site proves*: `sub_fc05b962` executes from a normal thread context during boot with interrupts enabled `[VERIFIED]`.
   - *What the call site does NOT prove*: Whether `CreateTask` can be called from interrupt handlers, before scheduler initialization, or with interrupts disabled.
   - *Classification*: **`[UNKNOWN: not proven by ROM call site alone]`**.

---

### 4.4 Reconciliation with Existing Tracked Repository Evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`)

While the call site in `sub_fc05b962` does not prove argument semantics on its own authority, the codebase already tracks comprehensive primary evidence in [`docs/PORT11A_GM110C_ROM_EVIDENCE.md`](PORT11A_GM110C_ROM_EVIDENCE.md). That document establishes the exact ROM-to-ATCM mapping and provides an instruction-by-instruction disassembly of the complete `CreateTask` function body.

#### 4.4.1 ATCM-to-ROM Copy Loop and Relocation Formula
During early boot (`0xFC020040..0xFC020052`), stock GM1.10C firmware executes an explicit copy loop that populates the ARM Cortex-R4 ATCM from high ROM (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-118`, Slice `S1A`):
- **Source ROM Span**: `0xFCEEF24C..0xFCEF5E67` (`6,919` 32-bit words = `27,676` bytes, file offset `0x00EEF24C..0x00EF5E67`).
- **Destination ATCM Span**: `0xBFE10800..0xBFE1741B` (`[0xBFE10800, 0xBFE1741C)`).
- **Exact Linear Mapping Formula**:
  $$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (\text{VMA} - 0\text{xBFE10800}), \qquad \text{File\_Offset} = \text{ROM\_VMA} - 0\text{xFC000000}$$
- Applying this formula to the `CreateTask` instruction address `0xBFE14A3C`:
  $$\text{ROM\_VMA} = 0\text{xFCEEF24C} + (0\text{xBFE14A3C} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x423C} = \mathbf{0\text{xFCEF3488}} \quad (\text{File Offset } \mathbf{0\text{x00EF3488}})$$
  (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:118`).

#### 4.4.2 Reconciled `CreateTask` Parameter Properties and Epistemic Labels
In `docs/PORT11A_GM110C_ROM_EVIDENCE.md:129-188` (Slice `S1C`, `556` bytes at ROM `0xFCEF3488..0xFCEF36B3`), the full `CreateTask` body (`0xBFE14A3C..0xBFE14AAD`, `114` bytes, ROM `0xFCEF3488..0xFCEF34F9`) and its literal pool (`0xBFE14C54..0xBFE14C67`, ROM `0xFCEF36A0..0xFCEF36B3`) are verified instruction-by-instruction. Each property is reconciled below, strictly maintaining PORT11A's epistemic classifications without upgrading to `VERIFIED` on PORT-27's own authority:

1. **`r0` (Task Name Pointer)**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A40` (ROM `0xFCEF348C`): `mov r4, r0` saves the pointer passed in `r0` into `r4` (`STATIC_VERIFIED` instruction in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:136`; role `name pointer [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136]`).
     - `0xBFE14A60` (ROM `0xFCEF34AC`): `cbnz r4, 0xBFE14A64` tests if `r4 != 0`.
     - `0xBFE14A62` (ROM `0xFCEF34AE`): `ldr r4, [r1]` substitutes the default name pointer from `*(uint32_t *)0x000081CC` (`[r1]`, where `r1 = [0xBFE14C54] = 0x000081CC` loaded at `0xBFE14A5E`) if `r4 == 0` (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:150-151`).
     - `0xBFE14A88` (ROM `0xFCEF34D4`): `str r4, [sp, #8]` forwards the resolved name pointer to the internal task allocator.
   - *Status*: **`[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136]`**.

2. **`r1` (Task Priority)**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A44` (ROM `0xFCEF3490`): `mov r6, r1` copies `r1` to `r6` (`STATIC_VERIFIED` instruction in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:138`; role `priority [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:138]`).
     - `0xBFE14A64..0xBFE14A68` (ROM `0xFCEF34B0..0xFCEF34B4`): `subs r0, r6, #1`; `cmp r0, #0x20`; `bhs 0xBFE14A6C` enforces the valid priority range $1 \le r6 \le 32$ (`0x20`) (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:152-154`). If `r6 == 0` or `r6 > 32`, execution branches to assertion setup (`0xBFE14A6C: movs r2, #0xa0`) and returns error code `3` (`0xBFE14A76: movs r0, #3`).
     - `0xBFE14A8A` (ROM `0xFCEF34D6`): `strd r6, r2, [sp]` passes `r6` (priority) at `[sp]` and `0` at `[sp, #4]` to the internal task allocator.
   - *Status*: **`[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:138, 152-154]`**.

3. **`r2` (Stack Size & Default Substitution when `r2 == 0`)**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A46` (ROM `0xFCEF3492`): `mov r5, r2` copies `r2` to `r5` (`STATIC_VERIFIED` instruction in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:139`; role `stack_size [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:139]`).
     - `0xBFE14A7C` (ROM `0xFCEF34C8`): `cbnz r5, 0xBFE14A80` tests if `r5 != 0`. If non-zero, the caller-specified stack size in `r5` is preserved.
     - `0xBFE14A7E` (ROM `0xFCEF34CA`): `ldr r5, [r1, #4]` loads `r5 = *(uint32_t *)0x000081D0` (`[r1, #4]`, where `r1 = 0x000081CC` loaded at `0xBFE14A5E`) (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-163`). This explicitly establishes the default stack size substitution when `r2 == 0`.
     - `0xBFE14A86` (ROM `0xFCEF34D2`): `mov r3, r5` passes the resolved stack size in `r3` to the internal allocator.
   - *Status*: Parameter role is `stack_size [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:139]`. The default stack size substitution logic when `r2 == 0` is a `STATIC_VERIFIED` instruction sequence in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-163`, with its role as `default stack size [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-163]`.

4. **`r3` (Entry Function Pointer & Thumb Bit)**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A4C` (ROM `0xFCEF3498`): `mov r7, r3` copies `r3` to `r7` (`STATIC_VERIFIED` instruction in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:141`; role `entry [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:141]`).
     - `0xBFE14A6A` (ROM `0xFCEF34B6`): `cbnz r7, 0xBFE14A7C` checks that `r7` is non-null (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:155`). If NULL (`0`), it falls through to assertion setup and returns error code `3`.
     - `0xBFE14A84` (ROM `0xFCEF34D0`): `mov r0, r7` passes the entry pointer in `r0` to the internal allocator.
     - *Thumb Interworking Requirement*: Both stock call sites pass Thumb entry function pointers with bit 0 set (`r3 = 0xFC0BD071` for `task_InitFileModules` at `0xFC0BD070` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:223-224`; `r3 = 0xFC05B8FD` for `task_Startup` at `0xFC05B8FC` in `PORT27-ROM-STARTUP-TASKS`).
   - *Status*: Parameter role is `entry [INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:141, 155]`. The entry point function address and Thumb bit 0 = 1 requirement are `STATIC_VERIFIED` across all stock call sites.

5. **`sp[0x00]` (Caller's Fifth Stacked Argument)**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A3C` (ROM `0xFCEF3488`): `push.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, lr}` pushes 10 32-bit registers (`40` bytes = `0x28` B) onto the stack (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:135`).
     - `0xBFE14A48` (ROM `0xFCEF3494`): `ldr.w r8, [sp, #0x28]` loads the caller's stacked 5th argument (`sp_entry + 0x00`) across the 40-byte stack frame into `r8` (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:140`).
     - `0xBFE14A82` (ROM `0xFCEF34CE`): `mov r1, r8` forwards the 5th argument in `r1` to the internal allocator.
   - *Status*: Instruction sequence loading the stacked 5th argument is `STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:140`; role as user context parameter is `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:140, 165]`.

6. **Return Value & Error Transformation**:
   - *Tracked Body Disassembly*:
     - Epilogue at `0xBFE14A78` (ROM `0xFCEF34C4`): `pop.w {r1, r2, r3, r4, r5, r6, r7, r8, sb, pc}` restores saved registers and returns (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:161`).
     - Parameter validation error: If priority is out of range or entry is NULL, returns `r0 = 3` (`0xBFE14A76: movs r0, #3`) (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:160`).
     - Internal allocator failure: At `0xBFE14A8E`, `bl 0xBFE10B88` invokes the internal allocator; at `0xBFE14A92..0xBFE14A96`, `mov r4, r0; adds r0, r0, #1; bne 0xBFE14AA4` tests if `r0 == -1` (`0xFFFFFFFF`). If `-1`, triggers `blx 0xBFE13E78` (`DebugAssert`) at `0xBFE14A9C` and returns error code `5` (`0xBFE14AA0: movs r0, #5`) (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:170-177`).
     - Success transformation: If `r0 != -1`, calls activation helper `bl 0xBFE10D14` at `0xBFE14AA6`, executes `lsls r0, r4, #1` at `0xBFE14AAA` (transforming the allocator handle to `handle << 1`), and branches to the epilogue at `0xBFE14AAC: b 0xBFE14A78` (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:180-182`).
   - *Status*: Instruction sequence is `STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:160-182`; return value transformation semantics are `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:171-182]`.

7. **Calling Context & ISR Execution Constraints**:
   - *Tracked Body Disassembly*:
     - `0xBFE14A42` (ROM `0xFCEF348E`): `ldr r0, [pc, #0x214]` loads literal pointer `[0xBFE14C58] = 0x00008160` (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:137`).
     - `0xBFE14A4E` (ROM `0xFCEF349A`): `ldr r0, [r0]` dereferences `*(uint32_t *)0x00008160` (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:142`).
     - `0xBFE14A50..0xBFE14A52` (ROM `0xFCEF349C..0xFCEF349E`): `cmp r0, #0; ble 0xBFE14A5E` checks if the context word is $\le 0$ (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:143-144`).
     - If $> 0$ (indicating ISR or forbidden execution context), lines `0xBFE14A54..0xBFE14A5A` load line number `0x98` (152), filename `"KerTask.c"` (`0xBFE14C5C`), and call `blx 0xBFE13E78` (`DebugAssert`) (`STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:145-148`).
   - *Status*: The context guard instruction sequence is `STATIC_VERIFIED` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:142-148`; interpretation of `0x00008160` as the context/ISR state word is `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:142-144]`.

---

### 4.5 Separation of Tracked Documentation vs. Milestone ROM Policy Bounds

In accordance with AgentBridge review protocol, two distinct categories of evidence must be kept strictly separated:
1. **Facts Reused from Existing Tracked Repository Documentation**:
   The facts documented in [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`](PORT11A_GM110C_ROM_EVIDENCE.md#L98-L186) are already tracked in the repository and require **no new ROM reads**. They carry forward PORT11A's epistemic classifications (`STATIC_VERIFIED` instruction bodies, `INFERRED` parameter roles and semantic interpretations).
2. **Facts Requiring New ROM Reads & Unverified Helpers**:
   The start address of the `CreateTask` body (`ROM 0xFCEF3488`) was not cited in PORT-23, PORT-24, or PORT-25 documentation or evidence manifests. Under the PORT-27 milestone read policy, reading `0xFCEF3488` or any uncited address is strictly prohibited. Therefore, no ROM read at `0xFCEF3488` is conducted in this milestone.

#### Unverified Internal Helpers Inside the `CreateTask` Body
`CreateTask` delegates core operating system functionality to three internal callees whose function bodies reside outside Slice `S1C` and are left unverified by PORT11A (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 170, 180, 409`; `docs/PORT14_Q_U4_08.md:183-185, 210-211`):
1. **Internal Task Allocator / Initializer (`0xBFE10B88`)**:
   - *ATCM Target*: `0xBFE10B88` (invoked via `bl 0xBFE10B88` at `0xBFE14A8E`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:170`).
   - *Exact ROM Start Address*: **`0xFCEEF5D4`** (file offset `0x00EEF5D4`, derived via linear formula: $0\text{xFCEEF24C} + (0\text{xBFE10B88} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x388} = 0\text{xFCEEF5D4}$).
   - *Length*: Span in ATCM up to the subsequent helper `0xBFE10D14` is 396 bytes (`0x18C` B); exact function length is unverified.
   - *Status*: **`UNKNOWN: needs authorised read (outside PORT-27 policy)`** (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:170`; `docs/PORT13_NEXT_QUESTIONS.md:162`; `docs/PORT14_Q_U4_08.md:183, 210`).
2. **Internal Activation Helper (`0xBFE10D14`)**:
   - *ATCM Target*: `0xBFE10D14` (invoked via `bl 0xBFE10D14` at `0xBFE14AA6`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:180`).
   - *Exact ROM Start Address*: **`0xFCEEF760`** (file offset `0x00EEF760`, derived via linear formula: $0\text{xFCEEF24C} + (0\text{xBFE10D14} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x514} = 0\text{xFCEEF760}$).
   - *Length*: Span in ATCM up to kernel initialization at `0xBFE10F78` is 612 bytes (`0x264` B); exact function length is unverified.
   - *Status*: **`UNKNOWN: needs authorised read (outside PORT-27 policy)`** (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:180`; `docs/PORT14_Q_U4_08.md:184, 211`).
3. **Debug Assertion / Panic Handler (`0xBFE13E78`, `DebugAssert [INFERRED]`)**:
   - *ATCM Target*: `0xBFE13E78` (invoked via `blx 0xBFE13E78` at `0xBFE14A5A`, `0xBFE14A72`, `0xBFE14A9C`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 159, 176`).
   - *Exact ROM Start Address*: **`0xFCEF28C4`** (file offset `0x00EF28C4`, derived via linear formula: $0\text{xFCEEF24C} + (0\text{xBFE13E78} - 0\text{xBFE10800}) = 0\text{xFCEEF24C} + 0\text{x3678} = 0\text{xFCEF28C4}$).
   - *Length*: Exact function length is unverified.
   - *Status*: **`UNKNOWN: needs authorised read (outside PORT-27 policy)`** (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:148, 409`).

#### Clarification on ROM Policy Boundaries
No full-ROM scan or pattern search is required to locate the ATCM copy loop or `CreateTask` implementation in ROM. The ATCM copy loop in early boot (`0xFC020040..0xFC020052`) and the high ROM source span (`0xFCEEF24C..0xFCEF5E67`) are already verified and tracked in [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-118`](PORT11A_GM110C_ROM_EVIDENCE.md#L98-L118). The restriction preventing inspection of these helpers in PORT-27 is strictly a milestone policy boundary: start addresses `0xFCEEF5D4`, `0xFCEEF760`, and `0xFCEF28C4` were not cited in the PORT-23/24/25 evidence baselines and therefore cannot be read without owner authorization in an expanded milestone policy.

---

### 4.6 Task-Creation Template for T2 & Strict GO / NO-GO Dependency Evaluation

If T2 attempts to spawn a resident heartbeat task by copying the verified call site pattern:

```armasm
    movs    r3, #0
    str     r3, [sp, #0]        ; arg5: passed value 0 [STATIC_VERIFIED call-site literal; INFERRED user context per PORT11A:140]
    ldr     r3, =task_heartbeat ; arg4: task entry function (Thumb bit 0 = 1) [VERIFIED call-site role; INFERRED per PORT11A:141]
    movs    r2, #0              ; arg3: passed value 0 [STATIC_VERIFIED call-site literal; INFERRED default stack per PORT11A:139, 162-163]
    movs    r1, #25             ; arg2: passed value 25 (0x19) [STATIC_VERIFIED call-site literal; INFERRED priority per PORT11A:138]
    ldr     r0, =name_string    ; arg1: string pointer [STATIC_VERIFIED call-site literal type; INFERRED name per PORT11A:136]
    blx     sub_fc31bbc4        ; Invoke DryOS CreateTask veneer (ARM) [VERIFIED: ROM 0xFC31BBC4]
```

#### Exact Arguments T2 Would Pass and Their Epistemic Labels:
1. `r0`: Pointer to ASCII name string (e.g. `0xFC05B9A0` `"Startup\0"` or a static buffer `"Heartbeat\0"`) — `[VERIFIED call-site literal type; INFERRED role as task name per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136]`.
2. `r1`: `25` (`0x19`) — `[VERIFIED call-site literal value; INFERRED role as priority per docs/PORT11A_GM110C_ROM_EVIDENCE.md:138, 152-154]`.
3. `r2`: `0` — `[VERIFIED call-site literal value; INFERRED role as stack size and default stack size selector per docs/PORT11A_GM110C_ROM_EVIDENCE.md:139, 162-163]`.
4. `r3`: `task_heartbeat | 1` — `[VERIFIED call-site role as task entry point with Thumb bit set; INFERRED parameter role per docs/PORT11A_GM110C_ROM_EVIDENCE.md:141, 155]`.
5. `sp[0x00]`: `0` — `[VERIFIED call-site literal value; INFERRED role as user context parameter per docs/PORT11A_GM110C_ROM_EVIDENCE.md:140, 165]`.

#### Application of the Strict GO Rule:
The reviewer policy states:
> *"GO is allowed only if T2 can create its task by copying the VERIFIED call-site pattern exactly, changing only values whose role is VERIFIED. State the exact arguments T2 would pass and give each one a label. If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*

- **Evaluation**:
  - In the template above, T2 changes `r3` (whose role is `[VERIFIED]` as the task entry point) and `r0` (whose role is `[INFERRED]`).
  - However, in order for `task_heartbeat` to run safely without corrupting memory or triggering a kernel panic, T2 strictly depends on `r2 = 0` successfully assigning an adequate execution stack from the internal allocator `0xBFE10B88`.
  - While `docs/PORT11A_GM110C_ROM_EVIDENCE.md:162-163` proves the instruction sequence substituting `*(0x000081D0)` when `r2 == 0`, its semantic role remains **`[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:139, 162-163]`** and cannot be upgraded to `VERIFIED` on PORT-27's own authority.
  - Crucially, the internal allocator `0xBFE10B88` at ROM `0xFCEEF5D4` that actually handles stack and TCB allocation remains **`[UNKNOWN: needs authorised read (outside PORT-27 policy)]`**.
  - Therefore, because T2 depends on the `INFERRED` parameter role of `r2` and the unverified allocator `0xBFE10B88`, the task creation prerequisite cannot be certified as fully VERIFIED under the strict rule.

**Next step**: UNKNOWN: exact ranges still needed (`0xFCEEF5D4`, `0xFCEEF760`, `0xFCEF28C4` for internal helpers, and authorized read of `0xFCEF3488..0xFCEF34F9` for CreateTask body)

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
  fc135cbc:   movw    r6, #2000       ; 0x7D0 (passed literal value 2000)
  fc135cc0:   str     r0, [r1, #0]
  fc135cc2:   str     r4, [r5, #4]
  fc135cc4:   mov     r0, r6          ; Parameter r0 = 2000
  fc135cc6:   blx     0xfc31bf84      ; SleepTask(2000)
  ```
  *(Source: `firmware/dumps/GM1.10C/PRIMARY.BIN:0xFC135CBC-0xFC135CC6`; `[VERIFIED: PORT27-ROM-WATCHDOG-MODULE]`)*
- **Calling Convention & Verification Status**:
  - `blx 0xfc31bf84` from Thumb-2 state (Thumb-2 encoding `f1e6 e95e`) switches to ARM mode `[VERIFIED: ROM 0xFC135CC6]`.
  - `r0`: Literal integer `2000` (`0x7D0`) is passed in `r0` `[VERIFIED: ROM 0xFC135CBC, 0xFC135CC4]`.
  - Argument Semantics & Units: That `2000` denotes a sleep duration in milliseconds is `[INFERRED: standard DryOS watchdog reset interval conventions; docs/UI001_CLAUDE_REVIEW.md:21]`, as the ROM call site instructions prove only the literal value 2000.
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
In `docs/PORT25_LADDER_FIX_CANDIDATE.md:144-154`, the timing model reproduces the following assumptions and calibration bounds:
- **Clock Assumptions**:
  - DIGIC 6 Cortex-R4 CPU core clock running at nominal ~150–250 MHz (`[INFERRED: docs/PORT20_LED_CANDIDATE.md:177]`).
  - Loop body `subs r0, r0, #1; bne` executes in 2–3 CPU cycles per iteration on ARMv7-R pipeline (`[INFERRED]`).
  - Slow conservative calibration bound is modeled at 66.6 MHz unmultiplied PLL reference clock (`[INFERRED: docs/PORT25_LADDER_FIX_CANDIDATE.md:149]`).
- **Loop Constant `0x00100000` (1,048,576 iterations)**:
  - Fast bound estimate (200 MHz, 3 cycles): ~15.73 ms `[INFERRED: docs/PORT25_LADDER_FIX_CANDIDATE.md:152]`.
  - Nominal bound estimate (150 MHz, 3 cycles): **20.97 ms** `[INFERRED: docs/PORT25_LADDER_FIX_CANDIDATE.md:153]`.
  - Slow bound estimate (66.6 MHz reference clock): **50.0 ms** `[INFERRED: docs/PORT25_LADDER_FIX_CANDIDATE.md:154]`.
- **Timing Model Qualification**:
  - The 50.0 ms figure is a nominal / slow-bound model estimate under uninterrupted CPU execution; it is **NOT** an upper bound or worst-case elapsed wall-clock time, because hardware interrupts, cache effects, and RTOS task preemption can stretch elapsed loop execution time without limit `[INFERRED]`.

**Next step**: enough to build

---

## 7. Comprehensive Summary Table

| Item | Technical Focus | Concrete Values & Verified Facts | Epistemic Status | Manifest Entry / Citation | Next Step |
|:---:|:---|:---|:---:|:---|:---:|
| **(a)** | Stock heap / memory start after `sub_fc0d0126` | `sub_fc0d0126`'s own instructions set no heap bounds (VERIFIED); the behaviour of the ATCM IRQ disable/restore routines is INFERRED/UNKNOWN (not read; outside PORT-27 policy); stock heap is set in `sub_fc05b3c8` | `VERIFIED` (sub_fc0d0126 instructions, veneer encodings, heap setup) / `INFERRED/UNKNOWN` (ATCM routines behaviour) | `PORT27-ROM-FIRMWARE-CONT` (`0xFC0D0080`), `PORT27-ROM-RESTORE-IRQ-VENEER` (`0xFC31B8CA`), `PORT27-ROM-HEAP-SETUP` (`0xFC05B3C0`) | **enough to build** |
| **(a)** | Exact patch point for memory start in `sub_fc05b3c8` | Literal `0x003489B4` at `[0xFC05B450]` loaded into `r4` at `0xFC05B3CA`, stored to `sp[0x08]` at `0xFC05B3FC`, subtracted from `0x00600014` at `0xFC05B402` into `r2` and stored to `sp[0x0C]` at `0xFC05B404`; heap-start alignment requirement is unproven; hook in `boot_prototype.c:24, 177-178, 212-215` overrides `r4` with `new_sa = 0x00368680` (arithmetically 64-byte aligned) | `VERIFIED` (patch point, descriptor stores, `new_sa`) / `UNKNOWN` (heap-start alignment requirement) | `PORT27-ROM-HEAP-SETUP` (`0xFC05B3C0`), `chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 177-178, 212-215`, `docs/PORT25_LADDER_FIX_CANDIDATE.md:391` | **enough to build** |
| **(a)** | Relocated core survival | Relocated core (`0x003489B4`..`0x00368680`, candidate `candidate_main.bin` 123,424 B, `_end = 0x00368680`; baseline `candidate_main.bin` 116,816 B, `_end = 0x00366CB0`). Stock non-survival is unconfirmed by specific overwrite; exclusion by shifting heap start past `_end` to `0x00368680` is verified; runtime survival is inferred (rules out heap pool 1 allocations, does not rule out DMA/MMIO); raised start yields 2.70 MiB surplus headroom above 712 KiB limit | `VERIFIED` (exclusion boundary, sizes, literals) / `INFERRED` (stock non-survival, runtime survival, headroom derivation) / `UNKNOWN` (other RAM users) | `docs/PORT25_LADDER_FIX_CANDIDATE.md:388, 391`, `docs/PORT23_LED_BREADCRUMBS.md:25-26`, `docs/PORT21_RAM_LIFETIME.md:37-47`, `PORT27-ROM-HEAP-SETUP` | **enough to build** |
| **(b)** | Task-creation entry (`CreateTask`) | `sub_fc31bbc4` at `0xFC31BBC4` (ARM mode `ldr pc, [pc, #-4]` -> ATCM `0xBFE14A3D` Thumb-2); entered via `blx 0xfc31bbc4` from Thumb-2 at `0xFC05B990` | `VERIFIED` | `PORT27-ROM-CREATETASK-VENEER` (`0xFC31BBA0`), `PORT27-ROM-STARTUP-TASKS` (`0xFC05B8E0`) | **enough to build** (entry point only) |
| **(b)** | Task-creation calling convention & argument meanings | Call site `0xFC05B984..0xFC05B990` proves passed values (`r0=0xFC05B9A0`, `r1=25`, `r2=0`, `r3=0xFC05B8FD`, `sp[0]=0`); PORT11A documents body at ATCM `0xBFE14A3C..0xBFE14AAD` (ROM `0xFCEF3488..0xFCEF34F9`) including default stack size substitution from `*(0x000081D0)` when `r2=0`, priority range check $1 \le r6 \le 32$, and return value `handle << 1`; parameter roles remain `INFERRED` per `docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165`; internal callees `0xBFE10B88` (`0xFCEEF5D4`), `0xBFE10D14` (`0xFCEEF760`), and `0xBFE13E78` (`0xFCEF28C4`) are outside PORT-27 read policy and remain `UNKNOWN` | `VERIFIED` (call site values, entry `r3`, veneer) / `INFERRED` (`r0` name, `r1` priority, `r2` stack size & default substitution, `sp[0]` 5th arg, return value semantics per PORT11A) / `UNKNOWN` (internal callees `0xFCEEF5D4`, `0xFCEEF760`, `0xFCEF28C4`) | `PORT27-ROM-STARTUP-TASKS` (`0xFC05B8E0`), `PORT27-ROM-CREATETASK-VENEER` (`0xFC31BBA0`), `docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186` | **UNKNOWN: exact ranges still needed** (`0xFCEEF5D4`, `0xFCEEF760`, `0xFCEF28C4` for internal helpers, and authorized read of `0xFCEF3488..0xFCEF34F9` for CreateTask body) |
| **(c)** | LED register & on/off values | MMIO: `0xD20B0884`; ON: `0x004D0002`; OFF: `0x004C0003` (Rear green LED; reused from PORT-23 hardware trial without new ROM reads) | `VERIFIED` | `docs/PORT23_LED_BREADCRUMBS.md:6-7` (Hardware trial 2026-11-01) | **enough to build** |
| **(d)** | Firmware sleep / delay primitive | `SleepTask` veneer `0xFC31BF84` (ARM mode -> ATCM `0xBFE14969` Thumb-2); called via `blx 0xfc31bf84` from `task_WdtReset` (`0xFC135CC6`) with literal `r0=2000` (`[VERIFIED]`; role as ms delay `[INFERRED]`); task context only `[INFERRED]`; busy-wait loop with `0x00100000` (nominal ~21 ms, slow bound ~50 ms under uninterrupted timing model at `docs/PORT25_LADDER_FIX_CANDIDATE.md:144-154`; interrupts/preemption can stretch elapsed time without limit) `[INFERRED]` | `VERIFIED` (veneer, call site `r0=2000`) / `INFERRED` (delay units/semantics, ISR guard, loop timing model) | `PORT27-ROM-WATCHDOG-MODULE` (`0xFC135C00`), `PORT27-ROM-SLEEPTASK-VENEER` (`0xFC31BF84`), `docs/PORT25_LADDER_FIX_CANDIDATE.md:144-154` | **enough to build** |

---

## 8. ROM Evidence Manifest & Running Byte Ledger

All ranges read for PORT-27 are recorded in [PORT27_EVIDENCE_MANIFEST.json](file:///var/lib/agentbridge/worktrees/g3x-lite/port-27-resident-heartbeat-p27-t1-resident-evidence/docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json). The running byte total is 2,380 bytes, strictly below the 24,576-byte milestone limit:

| Entry ID | ROM Start | ROM End | Length (B) | Running Total (B) | SHA-256 | Provenance & Purpose |
|:---|:---:|:---:|:---:|:---:|:---|:---|
| `PORT27-ROM-HEAP-SETUP` | `0xFC05B3C0` | `0xFC05B53F` | 384 | 384 | `68e60a1c4ffdf3ce29c97120aac275f1758df3726f8f5829a23e33b73c6908d6` | Stock heap init `sub_fc05b3c8`, base `0x003489B4`, headroom check `0x000B1FEC` (allowed start address `0xFC05B3C0` cited in `PORT25_EVIDENCE_MANIFEST.json:14, 162`) |
| `PORT27-ROM-STARTUP-TASKS` | `0xFC05B8E0` | `0xFC05BBDF` | 768 | 1,152 | `749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e` | `task_Startup`, `StartDiskboot`, `b.w sub_fc0d0126`, and `CreateTask` call site in `sub_fc05b962` (allowed start address `0xFC05B8E0` cited in `PORT24_EVIDENCE_MANIFEST.json:14, 152`) |
| `PORT27-ROM-FIRMWARE-CONT` | `0xFC0D0080` | `0xFC0D023F` | 448 | 1,600 | `33d2fae4ed8c9c228ea6cc8f3304a26b96f8a4fb6d9d3bdc37cd056e7833456e` | `sub_fc0d0126`'s own instructions set no heap bounds; decrement `[0x00008380]`, assert, and tail branch (allowed start address `0xFC0D0080` cited in `PORT24_EVIDENCE_MANIFEST.json:29, 197`) |
| `PORT27-ROM-WATCHDOG-MODULE`| `0xFC135C00` | `0xFC135E3F` | 576 | 2,176 | `29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb` | `task_WdtReset` calling `SleepTask(2000)` via `blx 0xfc31bf84` at `0xFC135CC6` (allowed start address `0xFC135C00` cited in `PORT23_EVIDENCE_MANIFEST.json:49, 192`) |
| `PORT27-ROM-RESTORE-IRQ-VENEER`| `0xFC31B8CA`| `0xFC31B8D9`| 16 | 2,192 | `c50fd6df693d4724d6ec4ac070967f674bab9c0448f1ca6c27dc480b8922a6e1` | `RestoreInterrupts` veneer `sub_fc31b8ca` (branch target verified from `0xFC0D014C` in `PORT27-ROM-FIRMWARE-CONT`) |
| `PORT27-ROM-CREATETASK-VENEER`| `0xFC31BBA0`| `0xFC31BBEF`| 80 | 2,272 | `59c9adc82ad1ad670ecf7ba0d42665a34f7acf1a10b68ad75874afe1fae77487` | `CreateTask` ARM veneer `sub_fc31bbc4` loading `0xBFE14A3D` (allowed start address `0xFC31BBA0` cited in `PORT25_EVIDENCE_MANIFEST.json:109, 447`) |
| `PORT27-ROM-IRQ-DISABLE` | `0xFC31BEE0` | `0xFC31BF3F` | 96 | 2,368 | `a15cb37e666e3349c0453b294d1283d99ae116214f36fc69671cdc3131db7826` | `DisableInterrupts` ARM veneer `sub_fc31befc` (allowed start address `0xFC31BEE0` cited in `PORT24_EVIDENCE_MANIFEST.json:64, 303`) |
| `PORT27-ROM-SLEEPTASK-VENEER`| `0xFC31BF84` | `0xFC31BF8F` | 12 | 2,380 | `462ba50005667f6192185cf76e0af698e0419e9d2fc481fd474ff862cb84d6e8` | `SleepTask` ARM veneer `0xFC31BF84` loading `0xBFE14969` (branch target verified from `0xFC135CC6` in `PORT27-ROM-WATCHDOG-MODULE`) |

---

## 9. Final Verdict for PORT-27 T2

> [!WARNING]
> **Verdict for PORT-27 T2**: **NO-GO**
> 
> Under the project task policy, a **GO** verdict requires both Item (a) and Item (b) to be certified as **VERIFIED**. Furthermore, reviewer guidance establishes a strict evaluation standard:
> *"GO is allowed only if T2 can create its task by copying the VERIFIED call-site pattern exactly, changing only values whose role is VERIFIED. State the exact arguments T2 would pass and give each one a label. If any argument T2 depends on (for example the stack size or the meaning of r2) is only INFERRED, the verdict is NO-GO, and the summary must list the exact UNKNOWN ranges."*
> 
> Detailed justification by prerequisite item:
> 
> - **Item (a) (Heap Start & Core Survival)**: Sufficient for implementation (`enough to build`):
>   - `sub_fc0d0126`'s own instructions set no heap bounds (`[VERIFIED]`); the behaviour of the ATCM IRQ disable/restore routines is `[INFERRED/UNKNOWN]` (not read; outside PORT-27 policy).
>   - Verified that stock firmware sets its heap in `sub_fc05b3c8`, with exact patch point verified: literal `0x003489B4` at `[0xFC05B450]` is loaded into register `r4` at `0xFC05B3CA`, stored to descriptor slot `sp[0x08]` at `0xFC05B3FC`, and subtracted from `0x00600014` at `0xFC05B402` to compute pool size into `r2` stored to `sp[0x0C]` at `0xFC05B404` `[VERIFIED]`.
>   - Heap-start alignment requirement is unproven in ROM `[UNKNOWN]`, though candidate raised start `new_sa = 0x00368680` is strictly 64-byte aligned as an arithmetic fact.
>   - Relocated core region (`candidate_main.bin` 123,424 B, `_end = 0x00368680`) is strictly excluded from stock DryOS heap allocations by overriding `r4` with `new_sa = 0x00368680` `[VERIFIED exclusion: boot_prototype.c:24, 177-178, 212-215; PORT21_RAM_LIFETIME.md:40-41]`, with 2.70 MiB of surplus headroom above the ROM limit. Runtime survival is `[INFERRED]` (protects against heap allocations; does not rule out unverified physical DMA buffers or hardware MMIO).
> 
> - **Item (b) (Task Creation Entry & Calling Convention)**: **FAILS STRICT VERIFICATION** (`UNKNOWN: exact ranges still needed`):
>   - The task creation entry veneer `sub_fc31bbc4` (ARM mode `0xE51FF004` at `0xFC31BBC4`, loading target vector `0xBFE14A3D` for Thumb-2 execution at `0xBFE14A3C`) is `[VERIFIED]`.
>   - The call site values at `0xFC05B984..0xFC05B990` (`r0=0xFC05B9A0`, `r1=25`, `r2=0`, `r3=0xFC05B8FD`, `sp[0]=0`) and the entry point role of `r3` are `[VERIFIED]`.
>   - When reconciled with tracked repository evidence (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:98-186`), the complete `CreateTask` body at ATCM `0xBFE14A3C..0xBFE14AAD` (ROM `0xFCEF3488..0xFCEF34F9`) verifies the instruction logic substituting `*(0x000081D0)` when `r2 == 0`, priority range check $1 \le r6 \le 32$, and return value `handle << 1`.
>   - However, parameter roles (`r0` name pointer, `r1` priority, `r2` stack size, `sp[0]` user context) carry forward PORT11A's epistemic status as `[INFERRED: per docs/PORT11A_GM110C_ROM_EVIDENCE.md:136-165]` and cannot be upgraded to `VERIFIED` on PORT-27's own authority.
>   - Furthermore, `CreateTask` delegates execution to internal callees whose bodies are outside Slice `S1C` and remain unverified: internal allocator `0xBFE10B88` at ROM `0xFCEEF5D4` (`UNKNOWN`), activation helper `0xBFE10D14` at ROM `0xFCEEF760` (`UNKNOWN`), and assertion handler `0xBFE13E78` at ROM `0xFCEF28C4` (`UNKNOWN`).
>   - If T2 creates a resident heartbeat task using the verified call-site template (`r0`=name string, `r1=25`, `r2=0`, `r3=task_heartbeat|1`, `sp[0]=0`), T2 strictly depends on `r2 = 0` successfully assigning a valid, adequate execution stack from internal allocator `0xBFE10B88`. Because the role of `r2` is `[INFERRED]` and `0xBFE10B88` is `[UNKNOWN]`, T2 depends on unverified prerequisites.
>   - The exact ranges required to resolve these uncertainties are:
>     1. ROM `0xFCEEF5D4` (ATCM `0xBFE10B88`, internal allocator, span up to 396 B) — `UNKNOWN: needs authorised read (outside PORT-27 policy)`
>     2. ROM `0xFCEEF760` (ATCM `0xBFE10D14`, internal activation helper, span up to 612 B) — `UNKNOWN: needs authorised read (outside PORT-27 policy)`
>     3. ROM `0xFCEF28C4` (ATCM `0xBFE13E78`, assertion handler) — `UNKNOWN: needs authorised read (outside PORT-27 policy)`
>     4. ROM `0xFCEF3488..0xFCEF34F9` (114 B, `CreateTask` body in Slice `S1C`) — requires authorized read under an updated milestone read policy
> 
> - **Item (c) (Hardware LED)**: **VERIFIED** (`enough to build`):
>   - MMIO `0xD20B0884`, ON `0x004D0002`, OFF `0x004C0003` reused from PORT-23 hardware trial breadcrumbs `[VERIFIED]`.
> 
> - **Item (d) (Firmware Sleep)**: **VERIFIED** entry / call site (`enough to build`):
>   - Veneer `0xFC31BF84` loading `0xBFE14969` and call site literal `r0 = 2000` (`0xFC135CC6`) are `[VERIFIED: PORT27-ROM-WATCHDOG-MODULE; PORT27-ROM-SLEEPTASK-VENEER]`. Parameter semantics (millisecond delay unit) and task-only execution constraints are `[INFERRED]`. Context-free busy-wait loop (`0x00100000` yielding nominal ~20.97 ms, slow bound ~50.0 ms under the uninterrupted timing model in `docs/PORT25_LADDER_FIX_CANDIDATE.md:144-154`, where interrupts or preemption can stretch duration) provides a robust alternative `[INFERRED]`.
> 
> Because Item (b) calling convention semantics cannot be certified as VERIFIED within the milestone ROM read policy, the final verdict for PORT-27 T2 is strictly **NO-GO**.
