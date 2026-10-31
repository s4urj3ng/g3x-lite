# PORT-20 T1: Evidence for a Visible LED Signal from Loader Context (GM1.10C)

**Milestone**: PORT-20: Visible Boot Signal (PowerShot G3 X GM1.10C)  
**Deliverable**: Task P20-T1-led-evidence (`docs/PORT20_LED_EVIDENCE.md`)  
**Firmware Target**: Canon PowerShot G3 X **GM1.10C** (`PRIMARY.BIN`, 33,554,432 bytes, SHA-256 `d8ad5039...`)  
**Evidence Manifest**: `docs/agentbridge/PORT20_EVIDENCE_MANIFEST.json`  
**Evidence Validator**: `tools/port11c_evidence_validator.py`  
**Verification Standard**: Evidence is classified strictly under project protocol:
- **`VERIFIED`**: GM1.10C ROM code (`PRIMARY.BIN`), read in an anchored range, writes the exact value to the exact address for that LED descriptor; or a tracked file:line states exactly the cited fact.
- **`INFERRED`**: Follows from reference DIGIC 6 CHDK ports, forum reports, ARM architecture documents, or an unanchored ROM read (see §7). Not proven directly by anchored GM1.10C ROM code.
- **`UNKNOWN`**: No primary evidence in tracked artifacts or anchored ROM ranges.

---

## 1. Executive Summary & Verification Outcome

The GM1.10C firmware was examined offline with bounded static disassembly (8 recorded ROM ranges, 2,336 bytes in total). The goal was an MMIO register that can drive a visible G3 X LED from loader context (`0x8000` / `0x40008000`), before DryOS or its drivers are set up.

### Key Technical Findings:
1. **Primary MMIO LED Register**:
   - Register address: **`0xD20B0884`** `[VERIFIED: PRIMARY.BIN 0xFC075DC4..0xFC075DE4, 0xFC075D98..0xFC075DC2, 0xFC0D73C4..0xFC0D73CE]`
   - Value written by the action-0 path: **`0x004d0002`** `[VERIFIED: PRIMARY.BIN 0xFC075DA0, literal 0xFC075E00]`
   - Value written by the action-1 path: **`0x004c0003`** `[VERIFIED: PRIMARY.BIN 0xFC075DB6, literal 0xFC075E04]`
   - Read-modify-write requirement: **None**. The stock code does a direct 32-bit store, `str.w r1, [r0, #2048]` `[VERIFIED: PRIMARY.BIN 0xFC0D73CA]`
   - Target: **Logical LED descriptor 0 of the stock `LEDDrv` (GPIO pin 33)** `[VERIFIED: PRIMARY.BIN 0xFC12D6DC, 0xFC075DC4]`
   - Physical LED: **rear green status / power-button LED** `[INFERRED: docs/RESEARCH_LOG.md:38 (E025, forum post 149971); chdk-port/loader/g16/main.c:7 (G16 uses 0xd20b0884 for its "green LED on power button")]`
   - Polarity (`0x4d0002` = lit, `0x4c0003` = dark): **`INFERRED`** from reference DIGIC 6 loaders `chdk-port/loader/g7x/main.c:16-17, 28` and `chdk-port/loader/g5x/main.c:16-17, 28` (see §3.5).
2. **Rejection of the copied G5 X / G7 X address (`0xD20B0994`)**: `vendor/g3x-platform/platform/g3x/lib.c:45-46` warns against copying it `[VERIFIED: tracked file]`. In GM1.10C, `0xD20B0800 + pin*4` is the store target of the GPIO primitive, so `0xD20B0994` is pin 101, not the LED-0 pin 33 `[VERIFIED: PRIMARY.BIN 0xFC075DC8, 0xFC0D73C4..0xFC0D73CA]`.
3. **Rejection of stock driver calls**: the `LEDDrv.c` routines `0xFC12D750` / `0xFC12D7A4` check `*0x00009BA4 == 1` and call the assert/panic routine `0xfc31bff4` otherwise `[VERIFIED: PRIMARY.BIN 0xFC12D75C, 0xFC12D7B0]`. The candidate `LEDDrive` entry `0xFC5572B9` was seen only in an unanchored read `[INFERRED (unanchored read, §7)]`.
4. **Loader context** (details in §4):
   - MPU Region 2 (`0x80000000..0xFFFFFFFF`) is programmed with `DRACR = 0x1105` (privileged RW only, Shareable Device, non-cacheable, XN) `[VERIFIED: PRIMARY.BIN 0xFC0045BE..0xFC0045D6]`. That no higher-numbered region overrides it at `0xD20B0884` is `[INFERRED: docs/PROJECT_STATE.md:254]`.
   - Privileged (PL1) execution at loader entry: `[INFERRED]`. The exact CPU mode at entry: `[UNKNOWN]`. FIQ state at entry: `[UNKNOWN]`.
   - No cache maintenance is needed for the LED store, but a `DSB` is needed after it before any busy-wait, because Device writes can sit in the Cortex-R4 store buffer `[INFERRED: ARM DDI 0406C; ARM DDI 0363]`.

---

## 2. Candidate LED Registers Table

The table lists every candidate evaluated from GM1.10C ROM analysis, tracked platform sources and reference CHDK ports:

| Candidate Address | ON Value | OFF Value | RMW Mask | Target Hardware LED | Verification Classification | Tracked Citation / Primary Disassembly |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **`0xD20B0884`** | `0x004d0002` | `0x004c0003` | None (Direct 32-bit `str.w`) | Logical LED descriptor 0 (GPIO pin 33) `[VERIFIED]`; physically inferred as rear green status / power-button LED `[INFERRED: docs/RESEARCH_LOG.md:38]` | **`VERIFIED`** (address & operational values) / **`INFERRED`** (physical location & polarity) | `PRIMARY.BIN` `0xFC075DC4` (pin 33), `0xFC075D98` (`0x4d0002`), `0xFC075DAE` (`0x4c0003`), `0xFC0D73C4` (MMIO store); physical location and polarity inferred from `docs/RESEARCH_LOG.md:38` (E025), `chdk-port/loader/g16/main.c:7`, `chdk-port/loader/g7x/main.c:17, 28` |
| **`0xD20B0994`** | `0x004d0002` | `0x004c0003` | None | G5 X / SX710 / M10 Green LED (pin 101); wrong pin on G3 X | **`INFERRED`** (ref ports) / **`REJECTED (CONTRADICTED FOR G3 X)`** | Reference ports `chdk-port/loader/g7x/main.c:17, 28` and `chdk-port/loader/g5x/main.c:17, 28`; explicitly rejected for G3 X in `vendor/g3x-platform/platform/g3x/lib.c:45-46` |
| **`0xD20B0810`** | `0x004d0002` | `0x004c0003` | None | Front AF Assist Lamp (pin 4) | **`INFERRED`** (unverified direct store in ROM) | Forum post 149971 cited in `docs/RESEARCH_LOG.md:38` (E025); calculated as GPIO pin 4 (`0xD20B0800 + 4*4`), but no direct store verified in GM1.10C ROM |
| **`0xD20B0888`** | `0x004d0002` | `0x004c0003` | None | OVF Bezel Orange LED on G16 (pin 34) | **`INFERRED`** (ref port) / **`REJECTED (ABSENT ON G3 X)`** | Reference port `chdk-port/loader/g16/main.c:8`; no evidence of OVF bezel orange LED on G3 X hardware |
| **`LEDDrive (0xFC5572B9)`** | N/A (`action=0`) | N/A (`action=1`) | N/A | High-level firmware function forwarding to `LEDDrv.c` | **`INFERRED`** (unanchored read, §7) / **`REJECTED (FATAL PRE-KERNEL)`** | Entry and branch to `0xFC12D838` seen only in unanchored range `PORT20-ROM-LEDDRIVE` (§7); the panic path it reaches is `0xFC12D75C` / `0xFC12D7B0` in anchored range `PORT20-ROM-LEDDRV-INIT` |
| **`LEDDrv.c (0xFC12D724)`** | N/A | N/A | N/A | Stock DryOS LED task & driver | **`VERIFIED`** (ROM driver) / **`REJECTED (FATAL PRE-KERNEL)`** | Anchored by `docs/PORT17_TRACE_EVIDENCE.md:410` and `docs/PROJECT_STATE.md:223`; panics at `0xFC12D75C` / `0xFC12D7B0` unless `*0x9BA4 == 1` |

---

## 3. Disassembly Evidence & Derivation of `0xD20B0884`

The register and its two values follow from five linked routines in the GM1.10C ROM. All of them lie in anchored ranges (see §6); none comes from `PORT20-ROM-LEDDRIVE`.

### 3.1 Step 1: Registration of LED 0 with GPIO Pin 33 (`0x21`)
In `LEDDrv_Init` (`0xFC12D624`, range `PORT20-ROM-LEDDRV-INIT`) the firmware allocates 14 LED descriptors (36 bytes each, array pointer at `[r7, #12]`), fills in defaults, then calls `0xFC075DC4` for element 0:

```arm
; --- GM1.10C ROM 0xFC12D6DA..0xFC12D6E0 (Range PORT20-ROM-LEDDRV-INIT) ---
fc12d6da: 68f8      ldr     r0, [r7, #12]          ; r0 = pointer to LED array element 0 (LED 0)
fc12d6dc: f748 fb72 bl      0xfc075dc4             ; configure LED 0 descriptor
```

At `0xFC075DC4` (range `PORT20-ROM-SS-LED-CONTROL`) descriptor 0 gets GPIO pin `33` (`0x21`):

```arm
; --- GM1.10C ROM 0xFC075DC4..0xFC075DE4 (Range PORT20-ROM-SS-LED-CONTROL) ---
fc075dc4: 2100      movs    r1, #0
fc075dc6: 7101      strb    r1, [r0, #4]           ; [r0, #4] = 0 (GPIO mode flag: 0 = direct GPIO)
fc075dc8: 2221      movs    r2, #33                ; r2 = 33 (0x21, GPIO pin identifier)
fc075dca: 6082      str     r2, [r0, #8]           ; [r0, #8] = 33 (pin index)
fc075dcc: f880 1094 strb.w  r1, [r0, #148]         ; aux fields
fc075dd0: 2204      movs    r2, #4
fc075dd2: f8c0 2098 str.w   r2, [r0, #152]
fc075dd6: f880 10b8 strb.w  r1, [r0, #184]
fc075dda: f880 10dc strb.w  r1, [r0, #220]
fc075dde: 2101      movs    r1, #1
fc075de0: f8c0 10ac str.w   r1, [r0, #172]
fc075de4: 4770      bx      lr
```

### 3.2 Step 2: Dispatching Action 0 and Action 1 in `task_LEDCon`
`task_LEDCon` (`0xFC12D3E0`, range `PORT20-ROM-TASK-LEDCON-ENTRY`) dequeues LED messages and branches at `0xFC12D4EE` (`beq.n 0xFC12D506`) into its state loop (`PORT20-ROM-TASK-LEDCON-LOOP`). At `0xFC12D510` the action in `r6` goes through a `tbb` jump table:
- `r6 = 0` (action 0) branches to `0xFC12D550`, which calls `0xFC075D98`.
- `r6 = 1` (action 1) branches to `0xFC12D548`, which calls `0xFC075DAE`.

```arm
; --- GM1.10C ROM 0xFC12D510..0xFC12D558 (Range PORT20-ROM-TASK-LEDCON-LOOP) ---
fc12d510: e8df f006 tbb     [pc, r6]               ; base is 0xFC12D514
; Table entries: [0] = 0x1E (offset 0x3C -> 0xFC12D550); [1] = 0x1A (offset 0x34 -> 0xFC12D548)

fc12d548: 4620      mov     r0, r4                 ; r0 = LED descriptor pointer
fc12d54a: f748 fc30 bl      0xfc075dae             ; action 1
fc12d54e: e059      b.n     0xfc12d604

fc12d550: 7e21      ldrb    r1, [r4, #24]
fc12d552: 4620      mov     r0, r4                 ; r0 = LED descriptor pointer
fc12d554: f748 fc20 bl      0xfc075d98             ; action 0
fc12d558: e054      b.n     0xfc12d604
```

### 3.3 Step 3: Loading Constants and Calling the MMIO Primitive
`0xFC075D98` and `0xFC075DAE` (range `PORT20-ROM-SS-LED-CONTROL`) load the pin from `[r4, #8]`, load the command word from a literal pool, and call the GPIO primitive `0xFC0D73C4`:

```arm
; --- GM1.10C ROM 0xFC075D98..0xFC075DC2 (Range PORT20-ROM-SS-LED-CONTROL) ---
fc075d98: b510      push    {r4, lr}
fc075d9a: 4604      mov     r4, r0                 ; r4 = LED descriptor
fc075d9c: 7900      ldrb    r0, [r0, #4]           ; check GPIO flag
fc075d9e: b918      cbnz    r0, 0xfc075da8         ; skip if not direct GPIO
fc075da0: 4917      ldr     r1, [pc, #92]          ; [0xFC075E00] -> 0x004d0002
fc075da2: 68a0      ldr     r0, [r4, #8]           ; [r4, #8] -> pin 33
fc075da4: f061 fb0e bl      0xfc0d73c4             ; write to hardware GPIO
fc075da8: 2000      movs    r0, #0
fc075daa: 6020      str     r0, [r4, #0]           ; record state = 0
fc075dac: bd10      pop     {r4, pc}

fc075dae: b510      push    {r4, lr}
fc075db0: 4604      mov     r4, r0                 ; r4 = LED descriptor
fc075db2: 7900      ldrb    r0, [r0, #4]           ; check GPIO flag
fc075db4: b918      cbnz    r0, 0xfc075dbe         ; skip if not direct GPIO
fc075db6: 4913      ldr     r1, [pc, #76]          ; [0xFC075E04] -> 0x004c0003
fc075db8: 68a0      ldr     r0, [r4, #8]           ; [r4, #8] -> pin 33
fc075dba: f061 fb03 bl      0xfc0d73c4             ; write to hardware GPIO
fc075dbe: 2001      movs    r0, #1
fc075dc0: 6020      str     r0, [r4, #0]           ; record state = 1
fc075dc2: bd10      pop     {r4, pc}

; Literal pool:
fc075e00: 004d0002  .word   0x004d0002             ; action 0 value
fc075e04: 004c0003  .word   0x004c0003             ; action 1 value
```

### 3.4 Step 4: MMIO Address Computation and Store Primitive
At `0xFC0D73C4` (range `PORT20-ROM-GPIO-WRITE-MMIO`) the pin is in `r0` and the command word in `r1`:

```arm
; --- GM1.10C ROM 0xFC0D73C4..0xFC0D73CE (Range PORT20-ROM-GPIO-WRITE-MMIO) ---
fc0d73c4: 4a07      ldr     r2, [pc, #28]          ; [0xFC0D73E4] -> 0xd20b0000
fc0d73c6: eb02 0080 add.w   r0, r2, r0, lsl #2     ; r0 = 0xd20b0000 + (pin << 2)
fc0d73ca: f8c0 1800 str.w   r1, [r0, #2048]        ; *(r0 + 0x800) = r1
fc0d73ce: 4770      bx      lr                     ; no DSB / read-back after the store

; Literal pool:
fc0d73e4: d20b0000  .word   0xd20b0000             ; GPIO MMIO base
```

For LED 0: `0xD20B0000 + 33*4 + 0x800 = 0xD20B0884`. The stock firmware therefore stores `0x4d0002` to `0xD20B0884` for action 0 and `0x4c0003` for action 1 `[VERIFIED]`. The primitive has no barrier or read-back after the store `[VERIFIED: PRIMARY.BIN 0xFC0D73CA..0xFC0D73CE]`.

### 3.5 Step 5: Polarity Analysis & Uncertainty
1. **Reference DIGIC 6 loaders**: `chdk-port/loader/g7x/main.c:16-17` and `chdk-port/loader/g5x/main.c:16-17` write `0x4d0002` under the comment `// light up green LED`, and their blinker writes `0x4c0003` for the dark phase (`:28`) `[VERIFIED: tracked files]`. Applying this to G3 X pin 33 is `[INFERRED]`.
2. **G3 X platform source**: `vendor/g3x-platform/platform/g3x/lib.c:52-58` maps CHDK `state = 1` to `_LEDDrive(led, 0)` and `state = 0` to `_LEDDrive(led, 1)` `[VERIFIED: tracked file]`. That `_LEDDrive` reaches `task_LEDCon` with the same action number is not shown in anchored ranges: the link from the candidate `LEDDrive` entry to `0xFC12D838` comes only from the unanchored read (§7). This strand is therefore `[INFERRED (unanchored read)]`, and it agrees with item 1 (action 0 = `0x4d0002` = lit).
3. **Classification**: the wiring (active high or low) cannot be checked offline. Polarity is **`INFERRED`**. The register `0xD20B0884` and the two values are **`VERIFIED`** from anchored GM1.10C ROM ranges.

---

## 4. Loader Context Writability Analysis

The question is whether the loader can write `0xD20B0884` before kernel start, in terms of CPU mode, interrupt state, MPU permissions and cache/write-buffer behaviour. State is split into (1) loader entry, before any loader instruction runs, and (2) after the explicit `cpsid if` in the loader.

### 4.1 CPU Execution Mode and Interrupt State

#### (1) At loader entry (before the first loader instruction at `0x8001`)

| Item | State | Label | Citation |
|---|---|---|---|
| Instruction set | Thumb, entered by `bx ip` with `ip = 0x8001` | **VERIFIED** | `docs/PORT19_DISKBOOT_ENCODING.md:323`; `chdk-port/loader/g3x/entry.S:2,4` |
| Privilege level | PL1 (privileged) | **INFERRED** | The handoff path that branches to the loader first does cache maintenance (`docs/PORT19_DISKBOOT_ENCODING.md:302`) and programs MPU Region 7 through CP15 (`docs/PORT19_DISKBOOT_ENCODING.md:303`). CP15 MPU and cache operations are UNDEFINED at PL0 (ARM DDI 0406C, Part B, PMSA system control registers), so that context should be PL1. The handoff steps listed in `docs/PORT19_DISKBOOT_ENCODING.md:304-323` contain no mode change, but the callees `0xFC41870C` / `0xFC135284` are not traced instruction by instruction in tracked evidence. |
| Exact CPU mode (SVC, System, ...) | Not shown | **UNKNOWN** | No tracked artifact records `CPSR.M` at the `StartDiskboot` handoff. |
| IRQ | Masked | **INFERRED** | `docs/PORT19_DISKBOOT_ENCODING.md:301`: `0xFC0D9CA2` calls `0xFC31BEFC` (`cpsr_fsxc \|= 0x80`, the I bit). The masking only takes effect at PL1, and the later callees are not shown not to re-enable IRQs. |
| FIQ | Not shown | **UNKNOWN** | `0x80` is the I bit only; no tracked evidence sets the F bit (`0x40`) before entry. |
| MPU Region 2 attributes | `0x80000000..0xFFFFFFFF`, `DRACR = 0x1105` | **VERIFIED** | `PRIMARY.BIN 0xFC0045BE..0xFC0045D6` (range `PORT20-ROM-MPU-REGION2-SETUP`) |
| Region 2 still in force at entry, not overridden at `0xD20B0884` | Unchanged | **INFERRED** | `docs/PROJECT_STATE.md:254` states the MPU configuration is phase-invariant across boot and loader execution and that Regions 1-5 cover addresses `>= 0x40000000`, without listing their attributes at `0xD20B0884`; the handoff only reprograms Region 7 (`docs/PORT19_DISKBOOT_ENCODING.md:303`, low memory). Higher-numbered regions take priority under PMSAv7, and their attributes at `0xD20B0884` were not re-examined in this task. |
| Caches | D/I cache maintained for the payload at `0x8000` | **VERIFIED** (tracked statement) | `docs/PORT19_DISKBOOT_ENCODING.md:302`. Whether the D-cache is enabled is not needed for the LED store (Region 2 is non-cacheable). |

The loader entry code itself does not change mode or interrupt state: `chdk-port/loader/g3x/entry.S:7-8` only loads `SP` and branches to `my_restart` `[VERIFIED: tracked file]`. `chdk-port/loader/g3x/main.c` contains no inline `asm`, `cps` or `msr` `[VERIFIED: tracked file]`.

#### (2) After `cpsid if` at `chdk-port/loader/g3x/main_prototype.c:86`

| Item | State | Label | Citation |
|---|---|---|---|
| Instruction present | `cpsid if` is the last step before the terminal handoff `bx r0` | **VERIFIED** | `chdk-port/loader/g3x/main_prototype.c:85-91` |
| IRQ and FIQ | Masked | **INFERRED** | `cpsid if` sets I and F only when executed at PL1; at PL0 a CPS instruction is a NOP (ARM DDI 0406C, CPS instruction description). Privilege itself is INFERRED (table 1). |
| CPU mode | Unchanged from entry | **UNKNOWN** | `cpsid if` has no mode operand and does not change mode, so the mode stays whatever it was at entry, which is UNKNOWN. |
| MPU / caches | Same as entry, plus the loader's own D-cache clean and I-cache invalidate for the core image | **INFERRED** | `chdk-port/loader/g3x/main_prototype.c:70-83`; the loader does not reprogram the MPU. |

`cpsid if` runs only at the very end of the prototype loader. All loader code before line 86 runs with the entry state (IRQ masked INFERRED, FIQ UNKNOWN, mode UNKNOWN).

#### Requirements for the T2 prologue
- The LED store needs PL1. Region 2 has `AP = 0b001` (privileged RW, no unprivileged access), so a PL0 store would take a permission fault `[INFERRED: VERIFIED DRACR value + ARM DDI 0406C PMSAv7 access permissions]`.
- T2 must not assume a specific mode, because the entry mode is UNKNOWN. The prologue should read `CPSR` (`mrs r0, cpsr`), and only do the LED store if `CPSR.M[4:0] != 0x10` (not User). Otherwise it skips the LED write (no signal, no fault). This makes the privilege requirement explicit and checked instead of assumed.
- T2 should not switch modes with `cps #mode`: that would bank a different `SP`/`LR` from the one `entry.S:7` set up.
- A `cpsid if` before the LED sequence is harmless (a NOP at PL0, masks both at PL1), so FIQ state does not have to be assumed.
- The LED write should come after `entry.S:7` has set up `SP` and before the cache/handoff steps of `main_prototype.c:70-91`.

### 4.2 MPU Memory Region Protection: Privileged Read/Write `[VERIFIED attributes]`
- DIGIC 6 uses an ARM Cortex-R4 with a PMSAv7 MPU, not an MMU `[VERIFIED: docs/PROJECT_STATE.md:254; docs/HANDOFF.md:628]`.
- ROM routine `0xFC0045BE..0xFC0045D6` (range `PORT20-ROM-MPU-REGION2-SETUP`) programs MPU Region 2:
  - `DRBAR`: `0x80000000`
  - `DRSR`: `0x3D` (2 GiB: `0x80000000..0xFFFFFFFF`)
  - `DRACR`: `0x1105`
    - Bits `[10:8]` (`AP`) = `0b001`: privileged read/write, no unprivileged access
    - Bits `[5:3]` (`TEX`) = `0b000`, bit `[2]` (`S`) = `1`, bit `[1]` (`C`) = `0`, bit `[0]` (`B`) = `1`: Shareable Device Memory, Non-cacheable
    - Bit `[12]` (`XN`) = `1`: execute never
- `0xD20B0884` lies inside `0x80000000..0xFFFFFFFF`. A PL1 store is permitted by Region 2 `[VERIFIED attributes]`. That Region 2 is the effective region at that address is `[INFERRED]` (see §4.1).

### 4.3 Cache Maintenance and Write Completion `[INFERRED]`
- **Cache maintenance is not needed.** Region 2 is Device memory (`TEX=000, C=0, B=1`), Non-cacheable and XN, so the LED store does not allocate in the D-cache. No `DCCMVAC` / `DCCISW` is needed for it `[INFERRED: VERIFIED DRACR + ARM DDI 0406C, memory types and attributes]`.
- **Non-cacheable does not mean unbuffered or complete.** Device writes can be held in the Cortex-R4 store buffer `[INFERRED: ARM DDI 0363, Cortex-R4 TRM, Level One Memory System / store buffer]`. ARMv7 Device memory only guarantees ordering against other Device accesses, not that the write has reached the peripheral before later non-memory instructions run. Completion is guaranteed only by `DSB` `[INFERRED: ARM DDI 0406C, A3.8.3 Memory barriers]`.
- **Recommendation for T2**: `str` the value to `0xD20B0884`, then `dsb sy`, then optionally read back `0xD20B0884` with `ldr`, and only then start the busy-wait. Without the `DSB`, the LED change could be delayed by an unknown amount behind the delay loop. What the read-back returns (latch value or something else) is `[UNKNOWN]`, so T2 must not use it as proof of success.
- **ROM comparison**: the stock primitive does not show this pattern. It returns straight after the store (`str.w` then `bx lr`) `[VERIFIED: PRIMARY.BIN 0xFC0D73CA..0xFC0D73CE]`, and the reference loaders do a plain volatile store (`chdk-port/loader/g7x/main.c:17`). The DSB recommendation therefore stays `[INFERRED]`.

### 4.4 Read-Modify-Write Requirements: None `[VERIFIED]`
- The stock routine at `0xFC0D73CA` does an unconditional word store, `str.w r1, [r0, #2048]`, with no read-modify-write masking.
- The meaning of the halfwords (upper `0x004d` / `0x004c`, lower `0x0002` / `0x0003`) is `[UNKNOWN]`. T2 writes the full 32-bit words exactly as the stock code does.

---

## 5. Audit of Alternative Candidate Indicators

### 5.1 Route 1: Stock Firmware `LEDDrive` (`0xFC5572B9`) — REJECTED (FATAL PRE-KERNEL)
- Entry `0xFC5572B9` (Thumb) and its branch to `0xFC12D838` come only from the unanchored range `PORT20-ROM-LEDDRIVE` `[INFERRED (unanchored read, §7)]`. No tracked artifact gives this address.
- Independent of that range: `0xFC12D838` (range `PORT20-ROM-LEDDRV-DISPATCH`) forwards to `0xFC12D750` / `0xFC12D7A4`, which check `*0x00009BA4 == 1` and otherwise call `0xfc31bff4` `[VERIFIED: PRIMARY.BIN 0xFC12D75C, 0xFC12D7B0]`. `*0x9BA4` is set late in DryOS boot `[VERIFIED tracked statement: docs/HANDOFF.md:543]`. Calling the stock driver from the loader is rejected.

### 5.2 Route 2: Front AF Assist Lamp (`0xD20B0810`) — INFERRED
- Suggested in forum post 149971 for G3 X (`docs/RESEARCH_LOG.md:38`, E025); it equals GPIO pin 4 under `0xD20B0800 + pin*4`.
- LED 4 has special handling at `0xFC12D83E` (`cmp r0, #4`), but no anchored GM1.10C code path was found storing `0x4d0002` to `0xD20B0810`. It stays `INFERRED` and is not recommended.

### 5.3 Route 3: Copied G5 X Address (`0xD20B0994`) — CONTRADICTED
- Reference DIGIC 6 loaders use `0xD20B0994` (`chdk-port/loader/g7x/main.c:17`). On G3 X this is GPIO pin 101, not the LED-0 pin 33.
- `vendor/g3x-platform/platform/g3x/lib.c:45-46`: `// NOTE: G3X GPIO LED MMIO address is UNVERIFIED. // DO NOT copy G5X MMIO (0xd20b0994). Left inert.` `[VERIFIED: tracked file]`.

### 5.4 Relation to Earlier Tracked Claims
- `docs/PROJECT_STATE.md:223, 231` state that the `0xD20B0884` / `0xD20B0810` writes are "absent in ROM" (no such literal). That fits this task: the ROM computes `0xD20B0884` from base `0xD20B0000`, pin 33 and offset `0x800`, and never holds it as a literal (`PRIMARY.BIN 0xFC0D73C4..0xFC0D73E4`).
- The same lines call these writes dangerous (motor coils, power rails). For `0xD20B0884`, the anchored ROM chain shows Canon's own `LEDDrv` uses it as LED descriptor 0 `[VERIFIED]`. The physical wiring of pin 33 is still `[INFERRED]`. The owner should weigh this before any T2 hardware trial. This task does not settle the danger claim for `0xD20B0810`.

---

## 6. ROM Range Ancestry & Evidence Manifest Accounting

Eight ranges were read. Seven are anchored. Each is either the root of a chain (a tracked file:line whose content contains an address inside the range, or an address span that covers its start) or is reached by a `bl`/branch/literal inside another anchored range that points into it. One range, `PORT20-ROM-LEDDRIVE`, has no anchor and is disclosed as a scope deviation in §7. Each manifest entry carries its anchors as `ANCHOR:` clauses in `notes`, which `tests/test_port20_led_evidence.py` checks against the actual line content and the recorded ranges.

| Range ID | Start Address | End Address | Length (Bytes) | SHA-256 Digest | Anchor Citation / Parent Range | Anchor Type | Claims Supported & Classification |
|---|:---:|:---:|:---:|---|---|---|---|
| `PORT20-ROM-MPU-REGION2-SETUP` | `0xFC0045B0` | `0xFC0046AF` | 256 | `8768fa98243fd4899d01ede804bec51b43b0fe1bcb098152fbaaafdbbbe53140` | `docs/PROJECT_STATE.md:254` and `docs/HANDOFF.md:628` cite `0xFC00457A..0xFC004652`, which covers the start `0xFC0045B0` | Tracked repo artifact (`path:line`, root) | MPU Region 2 setup (`0x80000000..0xFFFFFFFF`, DRACR `0x1105`) `[VERIFIED]` |
| `PORT20-ROM-SS-LED-CONTROL` | `0xFC075D80` | `0xFC075E7F` | 256 | `70af2f448bb0a351e0bede3ea045ff2b273bb3071ccff887a54406f15431fb6c` | `PORT20-ROM-LEDDRV-INIT` `0xFC12D6DC` (`bl 0xFC075DC4`) | Instruction `bl` in recorded range | Pin 33 for LED 0, `0x4d0002` / `0x4c0003` loads `[VERIFIED]` |
| `PORT20-ROM-GPIO-WRITE-MMIO` | `0xFC0D73C0` | `0xFC0D74BF` | 256 | `0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b` | `PORT20-ROM-SS-LED-CONTROL` `0xFC075DA4`, `0xFC075DBA` (`bl 0xFC0D73C4`) | Instruction `bl` in recorded range | `0xD20B0000 + pin*4 + 0x800 = 0xD20B0884` and `str.w` store `[VERIFIED]` |
| `PORT20-ROM-TASK-LEDCON-ENTRY` | `0xFC12D3E0` | `0xFC12D4FF` | 288 | `fd8cc7ffbfadcc303eebdc96a72be278eaee89816762b1253f56a8e27e58c754` | `PORT20-ROM-LEDDRV-DISPATCH` literal `0xFC12D8D0` (holds `0xFC12D3E1`) | Literal pointer in recorded range | `task_LEDCon` entry and branch `0xFC12D4EE` to loop `[VERIFIED]` |
| `PORT20-ROM-TASK-LEDCON-LOOP` | `0xFC12D500` | `0xFC12D5FF` | 256 | `6e7abdb12c6e80115aa951f0b356732f7d3691a02b18817183a7e0675f89a791` | `PORT20-ROM-TASK-LEDCON-ENTRY` `0xFC12D4EE` (`beq.n 0xFC12D506`) | Instruction branch in recorded range | `tbb [pc, r6]` dispatch of action 0 to `0xFC075D98` and action 1 to `0xFC075DAE` `[VERIFIED]` |
| `PORT20-ROM-LEDDRV-INIT` | `0xFC12D620` | `0xFC12D81F` | 512 | `f905d002702bf182a2a92762fa50295e1cbb696d704c5b69690afac28de665c3` | `docs/PORT17_TRACE_EVIDENCE.md:410` and `docs/PROJECT_STATE.md:223` cite `0xFC12D724`, inside the range (start + `0x104`) | Tracked repo artifact (`path:line`, root) | 14 LED descriptors and registration of LED 0 via `bl 0xFC075DC4`; pre-kernel asserts `[VERIFIED]` |
| `PORT20-ROM-LEDDRV-DISPATCH` | `0xFC12D820` | `0xFC12D91F` | 256 | `c6f3aa05396d8ff9cff0b0bd954191f03706ef932ca8aac3bfacf0c7db7c9b8b` | `PORT20-ROM-LEDDRV-INIT` `0xFC12D658` (`bl 0xFC12D8B6`) | Instruction `bl` in recorded range | Dispatcher, IPC sender, `task_LEDCon` pointer literal `0xFC12D8D0` `[VERIFIED]` |
| `PORT20-ROM-LEDDRIVE` | `0xFC5572B8` | `0xFC5573B7` | 256 | `9a23088b4d321bd65e1728451354023c7814d0915c3ad9e4d6ce74af56208399` | None: no tracked file:line and no recorded-range instruction or literal references `0xFC5572B8` / `0xFC5572B9` | SCOPE DEVIATION (unanchored read, §7) | Candidate `LEDDrive` entry `0xFC5572B9` `[INFERRED (unanchored read) / REJECTED PRE-KERNEL]` |

- Total ranges read: **8** (limit: at most 8)
- Largest range: **512 bytes** (limit: at most 4096 bytes)
- Total bytes read: **2,336 bytes** (limit: at most 32,768 bytes)
- No new ROM ranges were read in revision 3. Only the manifest `notes` fields changed. Addresses, lengths and SHA-256 digests are unchanged.
- Validator: `python3 tools/port11c_evidence_validator.py --manifest docs/agentbridge/PORT20_EVIDENCE_MANIFEST.json` must report `Result: VALID` with 0 errors. The expected single WARNING is the self-declared-scope trust notice (`tools/port11c_evidence_validator.py:606`). `tests/test_port20_led_evidence.py` enforces this.

---

## 7. Scope Deviations

- `PORT20-ROM-LEDDRIVE` (`0xFC5572B8..0xFC5573B7`, 256 bytes, SHA-256 `9a23088b4d321bd65e1728451354023c7814d0915c3ad9e4d6ce74af56208399`): **this read had no tracked anchor and breaks the T1 ROM-read rule** (each range must be justified by a tracked artifact or by an address inside an already recorded range).
  - No tracked file:line contains `0xFC5572B8` or `0xFC5572B9`. `vendor/g3x-platform/platform/g3x/lib.c:55` only declares `extern int _LEDDrive(int, int);` with no address. `docs/PORT17_TRACE_EVIDENCE.md:389` only points at that source. Neither is an anchor, and earlier revisions were wrong to call them one.
  - No instruction or literal inside the other seven recorded ranges branches to or points at `0xFC5572B8` / `0xFC5572B9`.
  - The entry stays in the manifest only so that the read accounting (start, length, SHA-256) is complete.
  - Claims drawn only from this range (the `LEDDrive` entry at `0xFC5572B9`, its `r1 < 8` check, and its branch to `0xFC12D838`) are labelled at most **INFERRED (unanchored read)**.
- **The T2 GO/STOP conclusion does not depend on this range.** The chain behind the conclusion uses only anchored ranges: `PORT20-ROM-LEDDRV-INIT` (tracked root `0xFC12D724`) → `0xFC12D6DC` → `PORT20-ROM-SS-LED-CONTROL` (`0xFC075DC4` pin 33; `0xFC075D98` / `0xFC075DAE` with literals `0xFC075E00` / `0xFC075E04`) → `PORT20-ROM-GPIO-WRITE-MMIO` (`0xFC0D73C4`, store to `0xD20B0884`). The `task_LEDCon` dispatch (`PORT20-ROM-LEDDRV-DISPATCH` → `PORT20-ROM-TASK-LEDCON-ENTRY` → `PORT20-ROM-TASK-LEDCON-LOOP` → `0xFC075D98` / `0xFC075DAE`) also descends from `PORT20-ROM-LEDDRV-INIT`. The MPU attributes come from `PORT20-ROM-MPU-REGION2-SETUP` (tracked root). The only strand that touches the unanchored range is the `_LEDDrive` → `task_LEDCon` action mapping in §3.5 item 2. Polarity is INFERRED anyway, and the reference loaders support it independently (§3.5 item 1).

---

## 8. Conclusion

Anchored GM1.10C ROM code shows the stock `LEDDrv` storing `0x004d0002` (action 0) and `0x004c0003` (action 1) to MMIO address `0xD20B0884` for LED descriptor 0 (GPIO pin 33) `[VERIFIED]`. That this is the rear green status / power LED, and that `0x4d0002` lights it, is `[INFERRED]`. The loader can write the register only at PL1 (`[INFERRED]`; entry mode `[UNKNOWN]`), so T2 must check `CPSR.M` before the store rather than assume a mode. No cache maintenance is needed, but T2 must issue a `DSB` after the store before any busy-wait. Otherwise the change may appear later than intended, and even with it the visible effect is not guaranteed while the physical LED and polarity are only INFERRED.

T2 GO: 0xD20B0884 on=0x004d0002 off=0x004c0003 (address/value VERIFIED, polarity INFERRED)
