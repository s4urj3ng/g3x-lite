# PORT-24 T3 (r3): Opt-in Breadcrumb Ladder DISKBOOT Candidate

## 1. Executive Summary & Epistemic Classifications

This document establishes the technical design, hardware calibration, architectural verification, and failure triage matrix for the **PORT-24 T3 (r3) Breadcrumb Ladder Candidate Build** on the Canon PowerShot G3 X (firmware GM1.10C).

The breadcrumb ladder is an opt-in diagnostic bootloader candidate (`DISKBOOT.BIN`) that emits progressive, visually distinct optical flashes on the camera's rear green LED (`0xD20B0884`) across the sequential post-loader execution path identified in `docs/PORT24_LOADER_TRACE.md`. Unlike single-stage breadcrumb builds (which require flashing and testing multiple separate binaries across separate power cycles), the ladder executes sequentially in a single boot cycle. The camera owner simply counts the **total number of flashes** observed before the camera powers off or goes dark. That total count directly identifies the exact execution checkpoint reached before failure.

### Epistemic Status
- `[VERIFIED: hardware trial 2026-11-01]`: Green LED MMIO address `0xD20B0884` controls the rear green LED on Canon PowerShot G3 X GM1.10C. Writing `0x004D0002` turns the LED ON; writing `0x004C0003` turns the LED OFF.
- `[VERIFIED: hardware trial 2026-11-01]`: Loader entry prologue at `0x00008000` executes on camera power-on with an encoded boot disk.
- `[VERIFIED: host build & test]`: Scope compliance: No new files are created under `chdk-port/platform/g3x/sub/110c/`. Only already-tracked files (`led_breadcrumb.h` and `loader_main_breadcrumb.c`) are edited, and all ladder additions sit strictly inside `#if defined(LED_LADDER)` guards.
- `[VERIFIED: host build & test]`: Default build invariance: When building without `--ladder` (or with `--flag-off`), the DISKBOOT.BIN output is byte-identical to the locked baseline SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (118,001 bytes).
- `[VERIFIED: host build & test]`: Ladder candidate build output is deterministic across multiple independent builds (DISKBOOT.BIN SHA-256 `530aee849f69b0c8a02c2b51803ef2988e12eeb2e86e79d444f93877f2781abe`, 118,257 bytes; candidate_loader.bin SHA-256 `649fdff6ce3469824890a5e59d0461c993b08a28f21188b5bfdfbc0db8e0f03b`, 118,256 bytes).
- `[VERIFIED: host build & test]`: The ladder candidate passes all 7 validation checks of `tools/validate_candidate_port2a.py`.
- `[INFERRED: docs/PORT23_POWER_SUPERVISION.md:245; docs/PORT24_LOADER_TRACE.md:761]`: Timing calibration is derived from the PORT-23 `0x00600000` short-delay build using the exact same loop body (`subs r2, r2, #1; bne`). Total step duration at the slowest bound (300 ms) is ~187.5 ms, strictly below the 200 ms upper bound.
- `[INFERRED: human visual physiology; Bloch's law]`: Single pulse per step with maximized dark gap (~52.1 ms nominal, ~125.0 ms slowest bound, ~41.7 ms fastest bound) prevents flicker-fusion blurring and enables clear human counting of separate flashes.
- `[UNKNOWN: codebase analysis]`: The CHDK core entry point `_start` (`0x003489B4`) is defined in `chdk-port/core/entry.S:1-11`, which resides outside `chdk-port/platform/g3x/sub/110c/`. Per the task brief and repository scope rules, files outside the allowed paths are not edited. The final loader breadcrumb is therefore accurately designated `before_bx`, and core entry itself is NOT instrumented.
- `[UNKNOWN: hardware trial 2026-11-01]`: Root cause of the shutdown after loader handoff (whether power supervision hold timeout, MMU/cache exception, or unhandled interrupt). The ladder candidate is designed to resolve this question.

---

## 2. Progressive Flash Ladder Scheme & Visibility Rationale (Problem 1 Remediation)

### 2.1 The Visibility Problem in Task 117
Task 117 configured an ON delay of $0x00240000$ and an OFF delay of $0x00140000$. Under nominal calibration (125 ms for reference $0x00600000$), this produced:
- ON duration: ~46.9 ms
- OFF duration: ~26.0 ms (dropping to as low as ~17–20 ms at faster loop execution speeds)

Under human visual physiology, retinal persistence lasts approximately 30–50 ms. When an intense light source (such as the camera rear green LED) is extinguished for only ~17–26 ms between pulses, the eye does not perceive the LED going dark; retinal after-images bridge the short gap, causing adjacent flashes to blend together into a single blurred pulse (flicker fusion). To be clearly counted by eye as separate flashes, the dark gap (OFF duration) must be substantially lengthened.

### 2.2 Mathematical Impossibility Analysis of Simultaneous Fast-Bound Goals
The task requirements state:
> "Choose iteration counts so that, at the FASTEST calibration bound, ON >= 40 ms and OFF >= 60 ms, and at the SLOWEST bound the step total stays < 200 ms. If the calibration range makes both impossible, say so explicitly in the doc and choose the counts that maximise the OFF gap under the 200 ms cap."

Let us analyze the mathematical envelope of the calibration sources:
- Reference loop count: $N_{ref} = 0x00600000 = 6,291,456$ iterations.
- Fastest calibration bound: $T_{fast}(N_{ref}) = 100$ ms (`docs/PORT23_POWER_SUPERVISION.md:245` range min).
- Slowest calibration bound: $T_{slow}(N_{ref}) = 300$ ms (`docs/PORT24_LOADER_TRACE.md:761` upper bound).

#### Step 1: Constraint at the Slowest Bound
To keep the step total strictly under 200 ms at the slowest bound ($T_{slow} = 300$ ms per $N_{ref}$):
$$T_{step, slow} < 200\text{ ms} \implies \frac{N_{step}}{N_{ref}} \times 300\text{ ms} < 200\text{ ms} \implies \frac{N_{step}}{N_{ref}} < \frac{2}{3} \approx 0.6667$$
$$N_{step} < \frac{2}{3} \times 0x00600000 = 0x00400000 = 4,194,304\text{ iterations}$$

#### Step 2: Maximum Available Duration at the Fastest Bound
For any iteration count $N_{step} < 0x00400000$, the maximum possible step duration at the fastest bound ($T_{fast} = 100$ ms per $N_{ref}$) is:
$$T_{step, fast} = \frac{N_{step}}{N_{ref}} \times 100\text{ ms} < \frac{2}{3} \times 100\text{ ms} \approx 66.67\text{ ms}$$

#### Step 3: Impossibility Proof
The step duration at the fastest bound is the sum of the ON duration and the OFF duration:
$$T_{step, fast} = T_{ON, fast} + T_{OFF, fast} < 66.67\text{ ms}$$
However, the simultaneous requirement of $T_{ON, fast} \ge 40$ ms and $T_{OFF, fast} \ge 60$ ms requires:
$$T_{step, fast} = T_{ON, fast} + T_{OFF, fast} \ge 40\text{ ms} + 60\text{ ms} = 100\text{ ms}$$
Because $100\text{ ms} > 66.67\text{ ms}$, **it is mathematically impossible to simultaneously achieve $T_{ON} \ge 40$ ms and $T_{OFF} \ge 60$ ms at the fastest calibration bound while keeping the total step duration under 200 ms at the slowest calibration bound**.

### 2.3 Justified Compromise: Maximizing the OFF Gap Under the 200 ms Cap
Per the task brief's instruction for this scenario ("choose the counts that maximise the OFF gap under the 200 ms cap"):
1. The 200 ms cap at the slowest bound (300 ms) limits $N_{step} < 0x00400000$. We select $N_{step} = 0x003C0000$ (3,932,160 iterations, ratio $0.625$), which ensures $T_{step, slow} = 187.5$ ms, safely leaving a 12.5 ms margin below the 200 ms limit.
2. In optical signaling, high-intensity LEDs (such as the G3 X rear green LED) deliver saturation brightness to human retinal cones in ~20–25 ms (Bloch's law of visual temporal summation). Conversely, human temporal resolution requires a large dark interval to register distinct flash boundaries.
3. Therefore, under the $N_{step} = 0x003C0000$ budget, we configure a **1:2 ON:OFF duty cycle** by inverting and expanding the iteration split:
   - $N_{ON} = 0x00140000$ (1,310,720 iterations, ratio $1.25 / 6 \approx 0.2083$)
   - $N_{OFF} = 0x00280000$ (2,621,440 iterations, ratio $2.5 / 6 \approx 0.4167$)
4. This doubles the OFF gap compared to Task 117 ($0x00280000$ vs $0x00140000$):
   - At the nominal bound (125 ms): OFF is **52.08 ms** (vs 26.0 ms in Task 117), providing a distinct dark gap.
   - At the range max bound (150 ms): OFF is **62.50 ms** (satisfying $\ge 60$ ms).
   - At the slowest bound (300 ms): OFF is **125.00 ms** (satisfying $\ge 60$ ms), ON is **62.50 ms** (satisfying $\ge 40$ ms), and step total is **187.50 ms** (satisfying $< 200$ ms).
   - At the fastest bound (100 ms): OFF is **41.67 ms** and ON is **20.83 ms**, which provides twice the dark separation of Task 117.

---

## 3. Hardware Calibration & Timing Arithmetic (Problem 2 Remediation)

### 3.1 Quotations from Calibration Sources
The timing calibration is anchored in physical hardware trials reported by the camera owner on 2026-11-01:

1. **Source A** (`docs/PORT23_POWER_SUPERVISION.md:245`):
   > "2. *Independence from stall duration* `[INFERRED]`: Despite reducing the loop duration by 16x (to ~100–150 ms `[INFERRED]`), the camera still powered off cleanly `[OWNER-REPORTED]`."
   - For $0x00600000$ iterations, this provides an estimated duration range of **100 ms to 150 ms**, with a nominal midpoint of **125 ms**.

2. **Source B** (`docs/PORT24_LOADER_TRACE.md:761`):
   > "Physical trial evidence: Candidate DISKBOOT runs the loader prologue (green LED turns ON at `0x8000`), but after a short stall (`0x00600000`, ~0.3 s) or long stall (`0x06000000`, ~3.3 s), the camera **powers completely off with the LCD backlight dark** `[VERIFIED: owner report; docs/PORT23_POWER_SUPERVISION.md:20-22]`."
   - For $0x00600000$ iterations, this provides an upper-bound estimate of **~0.3 s (300 ms)**.

### 3.2 Min/Max Calibration Envelope
Combining both citations gives the complete calibration envelope for $N_{ref} = 0x00600000$ (6,291,456 iterations):
- **Fastest Bound**: $100.0$ ms ($15.89$ ns per iteration) `[INFERRED]`
- **Nominal Model**: $125.0$ ms ($19.87$ ns per iteration) `[INFERRED]`
- **Range Max**: $150.0$ ms ($23.84$ ns per iteration) `[INFERRED]`
- **Slowest Bound**: $300.0$ ms ($47.68$ ns per iteration) `[INFERRED]`

### 3.3 Confirmation of Identical Loop Body in Objdump
The ladder build's busy-wait loop body was compared against the PORT-23 reference stall loop in `chdk-port/platform/g3x/sub/110c/loader_entry_led.S:36-39`:
```assembly
.Ldelay_loop:
    subs    r2, r2, #1
    bne     .Ldelay_loop
```
In `candidate_loader.elf`, disassembly of the ladder pulse loops confirms bit-for-bit instruction matching:
```assembly
    81ec:	3a01      	subs	r2, #1
    81ee:	d1fd      	bne.n	81ec <my_restart+0x14>
```
Both loops execute exactly **2 Thumb instructions per iteration** (`subs` and `bne.n`), confirming that execution timing per iteration is identical to the physical reference trials `[INFERRED]`.

### 3.4 Timing Arithmetic Across All Envelope Bounds `[INFERRED]`

Iteration parameter ratios:
$$\text{Ratio}_{ON} = \frac{0x00140000}{0x00600000} = \frac{1,310,720}{6,291,456} = \frac{1.25}{6} \approx 0.20833$$
$$\text{Ratio}_{OFF} = \frac{0x00280000}{0x00600000} = \frac{2,621,440}{6,291,456} = \frac{2.50}{6} \approx 0.41667$$
$$\text{Ratio}_{step} = \frac{0x003C0000}{0x00600000} = \frac{3,932,160}{6,291,456} = \frac{3.75}{6} = 0.62500$$

| Calibration Model | Reference Duration (0x00600000) | ON Duration ($N_{ON}$) | OFF Duration ($N_{OFF}$) | Total Step Duration ($N_{step}$) | Safety Cap (< 200 ms) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Fastest Bound** (`PORT23_POWER_SUPERVISION.md:245`) | 100.0 ms | 20.83 ms | 41.67 ms | 62.50 ms | **PASS** (< 200 ms) |
| **Nominal Model** (`PORT23_POWER_SUPERVISION.md:245`) | 125.0 ms | 26.04 ms | 52.08 ms | 78.13 ms | **PASS** (< 200 ms) |
| **Range Max** (`PORT23_POWER_SUPERVISION.md:245`) | 150.0 ms | 31.25 ms | 62.50 ms | 93.75 ms | **PASS** (< 200 ms) |
| **Slowest Bound** (`PORT24_LOADER_TRACE.md:761`) | 300.0 ms | 62.50 ms | 125.00 ms | 187.50 ms | **PASS** (< 200 ms) |

---

## 4. Repo Evidence for Alignment Pad `_ladder_align_pad` (Problem 3 Remediation)

### 4.1 Evidence Citations from the Repository
The 4-byte padding object `static const uint32_t _ladder_align_pad = 0;` is maintained in `loader_main_breadcrumb.c` behind `#if defined(LED_LADDER)`. The repository evidence requiring 8-byte alignment for the loader image is:

1. **`chdk-port/tools/dancingbits.c:60-68`**:
   ```c
   	int phox = fread(ewavr, 1, GHOST, jeff666);
   	while (phox > 0) {
   		for (grand=0; grand<phox; grand+=8) {
   			unsigned char fe50[8];
   			for (hacki=0; hacki<8; hacki++) {
   				fe50[_chr_[oldgit][hacki]] = dance(ewavr[grand + hacki], grand+hacki);
   			}
   			fwrite(fe50, 1, 8, jucifer);
   		}
   		phox = fread(ewavr, 1, GHOST, jeff666);
   	}
   ```
   The dancingbits encoder reads and permutes data in 8-byte blocks (`grand += 8; fwrite(fe50, 1, 8, jucifer)`). If the input loader binary is not an exact multiple of 8 bytes, `dancingbits.c` reads past the end of the input buffer and pads the output binary to an 8-byte boundary.

2. **`tools/validate_candidate_port2a.py:86-93` and `:458-462`**:
   ```python
   def decode_dancingbits_row13(encoded_bytes):
       ...
       for grand in range(0, len(payload), 8):
           block = payload[grand:grand+8]
           if len(block) < 8:
               break
           ...
       return bytes(out)
   ```
   ```python
   assert len(diskboot_bytes) == len(loader_bytes) + 1, "DISKBOOT.BIN length mismatch"
   decoded_loader = decode_dancingbits_row13(diskboot_bytes)
   assert decoded_loader == loader_bytes, "Decoded DISKBOOT.BIN does not match candidate_loader.bin bit-for-bit!"
   ```
   The validator strictly requires `len(diskboot_bytes) == len(loader_bytes) + 1` and reversibly decodes the payload in 8-byte blocks. Any leftover bytes (`len(block) < 8`) break the decoding loop and leave trailing zeros, causing `assert decoded_loader == loader_bytes` to fail.

3. **Size Arithmetic**:
   - Locked default loader: `118,000` bytes ($118,000 \pmod 8 = 0$, exactly 14,750 8-byte blocks).
   - Ladder loader without pad: `118,252` bytes ($118,252 \pmod 8 = 4$). Encoding causes dancingbits to write 118,257 bytes while the raw loader is 118,252 bytes, causing validator failure.
   - Ladder loader with 4-byte pad: `118,256` bytes ($118,256 \pmod 8 = 0$, exactly 14,782 8-byte blocks). `DISKBOOT.BIN` is $118,256 + 1 = 118,257$ bytes, and reversible decoding succeeds bit-for-bit.

### 4.2 Verification that Default Build is Unaffected
Unit test `test_default_build_unaffected_by_ladder_align_pad` in `tests/test_port24_breadcrumb_ladder.py` confirms:
1. When compiling without `--ladder` (or with `--flag-off`), `_ladder_align_pad` is not compiled into `candidate_loader.elf` (`arm-none-eabi-nm` confirms symbol is absent).
2. The default loader binary size is exactly 118,000 bytes ($118,000 \pmod 8 = 0$) and its SHA-256 matches the locked baseline `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`.

---

## 5. Architectural State Preservation & Literal Pool Verification (Problem 4 Remediation)

To ensure that the breadcrumb ladder causes zero state disruption to loader relocation, cache maintenance, or CHDK core handoff, disassembly of `candidate_loader.elf` was audited across all execution paths.

### 5.1 Preservation Invariants
1. **Stack Pointer (`sp = 0x7FF8`)**:
   - `docs/PORT24_LOADER_TRACE.md:312`: "Stack Pointer: `my_restart` pushes `{r3, lr}`, setting `sp = 0x7FF8` `[VERIFIED: candidate_loader.elf:0x81D8]`".
   - `docs/PORT24_LOADER_TRACE.md:389`: "Inherits `sp = 0x7FF8` from loader `[VERIFIED: candidate_loader.elf:0x8244]`".
   - Disassembly confirms that zero `push` or `pop` instructions exist in any breadcrumb routine. `sp` remains strictly `0x7FF8` throughout all 7 checkpoints.
2. **Registers & Callee-Saved Operands**:
   - GCC allocates callee-saved `r4` for `%1` (`byte_size` = 116,816) and `r5` for `%0` (`MEMISOSTART` = `0x003489B4`).
   - Breadcrumbs write exclusively to scratch registers `r0`, `r1`, `r2`.
   - Callee-saved `r4` and `r5` are never modified by any breadcrumb. Prior to each ROM call (`blx r2`), parameters in `r0`, `r1`, and `r2` are freshly loaded from `r5`, `r4`, and the literal pool.
3. **CPSR Mask State**:
   - Step 7 executes after `0x8308: cpsid if`.
   - Step 7 executes only `ldr`, `str`, `dsb sy`, `mov.w`, `subs`, and `bne.n`. It never executes `cpsie`, `cpsid`, or `msr CPSR`.
   - Both IRQ and FIQ remain strictly disabled (`I=1`, `F=1`) at terminal handoff `bx r0`.
4. **Thumb Execution Mode**:
   - All instructions are 16-bit or 32-bit Thumb-2 instructions.
   - Handoff executes `0x832c: mov r0, r5; 0x832e: add.w r0, r0, #1; 0x8332: bx r0`.
   - Setting bit 0 (`r0 = 0x003489B5`) guarantees entry into the CHDK core `_start` in Thumb mode.
5. **Final LED State**:
   - The final action of Step 7 (and every preceding pulse) writes `0x004C0003` to `0xD20B0884` and executes `dsb sy`.
   - The final optical state before handoff is **LED OFF**.

### 5.2 Literal Pool Placement Outside Execution Path
In `candidate_loader.elf`, the assembler placed the literal pool constants for `ldr r0, =0xD20B0884`, `ldr r1, =0x004D0002`, `ldr r1, =0x004C0003`, `ROM_DCACHE_CLEAN_INV`, and `ROM_ICACHE_INV_BP` at addresses `0x00008338..0x0000835F`:
```assembly
    8332:	4700      	bx	r0              ; Terminal handoff to core _start (0x003489B5)
    8334:	e7fe      	b.n	8334            ; Unreachable fallback infinite loop
    8336:	bf00      	nop                     ; Alignment padding
    ; --- LITERAL POOL (OUTSIDE EXECUTION PATH) ---
    8338:	00008360 	.word	0x00008360      ; &blob_chdk_core_size
    833c:	003489b4 	.word	0x003489b4      ; MEMISOSTART
    8340:	00008364 	.word	0x00008364      ; &blob_chdk_core
    8344:	0035f7a0 	.word	0x0035f7a0      ; BOOT_WITNESS_ADDR
    8348:	5749544e 	.word	0x5749544e      ; BOOT_WITNESS_MAGIC ('WITN')
    834c:	d20b0884 	.word	0xd20b0884      ; G3X_LED_MMIO_ADDR
    8350:	004d0002 	.word	0x004d0002      ; G3X_LED_ON_VAL
    8354:	004c0003 	.word	0x004c0003      ; G3X_LED_OFF_VAL
    8358:	fc127ab1 	.word	0xfc127ab1      ; ROM_DCACHE_CLEAN_INV
    835c:	fc127b09 	.word	0xfc127b09      ; ROM_ICACHE_INV_BP
```
Because the literal pool is positioned after the terminal `bx r0` and the infinite loop `b.n 8334`, **the literal pool is completely outside the linear execution path and can never be executed as instructions**.

### 5.3 Local Label Resolution
Each breadcrumb pulse defines local labels `1:` (ON loop) and `2:` (OFF loop) in inline assembly. In `candidate_loader.elf`, disassembly confirms that GNU `as` resolves each backward branch `bne 1b` and `bne 2b` to the nearest preceding label within that exact pulse:
- All 14 branch instructions (7 ON loops + 7 OFF loops) have opcode `d1fd` (Thumb `bne.n` with displacement `-3` halfwords = `-6` bytes).
- At address `0x81ee`, `bne.n 81ec` targets `0x81ec` (`subs r2, #1`).
- At address `0x81fe`, `bne.n 81fc` targets `0x81fc` (`subs r2, #1`).
- This exact pattern repeats identically for all 7 breadcrumbs. There is zero cross-pulse label collision or branching outside the immediate loop body.

---

## 6. Disassembly Excerpts of All 7 Breadcrumb Checkpoints

The following excerpts from `arm-none-eabi-objdump -d candidate_loader.elf` confirm the exact instructions, addresses, and opcodes for each breadcrumb checkpoint in `my_restart`.

### Step 1: `after_prologue` (`0x000081DE..0x000081FE`)
Positioned immediately after `check_compat()` returns (`0x81da: bl 8178`) and before `core_copy` parameter setup (`0x8200`):
```assembly
    81d8:	b508      	push	{r3, lr}
    81da:	f7ff ffcd 	bl	8178 <check_compat>
    ; --- BREADCRUMB STEP 1: after_prologue ---
    81de:	485b      	ldr	r0, [pc, #364]	; (834c: 0xD20B0884)
    81e0:	495b      	ldr	r1, [pc, #364]	; (8350: 0x004D0002)
    81e2:	6001      	str	r1, [r0, #0]
    81e4:	f3bf 8f4f 	dsb	sy
    81e8:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    81ec:	3a01      	subs	r2, #1
    81ee:	d1fd      	bne.n	81ec <my_restart+0x14>
    81f0:	4958      	ldr	r1, [pc, #352]	; (8354: 0x004C0003)
    81f2:	6001      	str	r1, [r0, #0]
    81f4:	f3bf 8f4f 	dsb	sy
    81f8:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    81fc:	3a01      	subs	r2, #1
    81fe:	d1fd      	bne.n	81fc <my_restart+0x24>
    ; --- SETUP FOR core_copy ---
    8200:	4b4d      	ldr	r3, [pc, #308]	; (8338: blob_chdk_core_size)
    8202:	681c      	ldr	r4, [r3, #0]
    8204:	3403      	adds	r4, #3
    8206:	f024 0403 	bic.w	r4, r4, #3
    820a:	4d4c      	ldr	r5, [pc, #304]	; (833c: 0x003489B4)
    820c:	10a2      	asrs	r2, r4, #2
    820e:	4629      	mov	r1, r5
    8210:	4b4b      	ldr	r3, [pc, #300]	; (8340: blob_chdk_core)
    8212:	6818      	ldr	r0, [r3, #0]
    8214:	f7ff ffc2 	bl	819c <core_copy>
```

### Step 2: `after_copy` (`0x00008242..0x00008262`)
Positioned immediately after Boot Witness Stage 1 checksum calculation and store (`0x8240: str r0, [r1, #28]`):
```assembly
    823c:	f7ff fee4 	bl	8008 <compute_witness_checksum.constprop.0>
    8240:	61c8      	str	r0, [r1, #28]
    ; --- BREADCRUMB STEP 2: after_copy ---
    8242:	4842      	ldr	r0, [pc, #264]	; (834c: 0xD20B0884)
    8244:	4942      	ldr	r1, [pc, #264]	; (8350: 0x004D0002)
    8246:	6001      	str	r1, [r0, #0]
    8248:	f3bf 8f4f 	dsb	sy
    824c:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    8250:	3a01      	subs	r2, #1
    8252:	d1fd      	bne.n	8250 <my_restart+0x78>
    8254:	493f      	ldr	r1, [pc, #252]	; (8354: 0x004C0003)
    8256:	6001      	str	r1, [r0, #0]
    8258:	f3bf 8f4f 	dsb	sy
    825c:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    8260:	3a01      	subs	r2, #1
    8262:	d1fd      	bne.n	8260 <my_restart+0x88>
```

### Step 3: `before_dcache` (`0x00008264..0x00008284`)
Positioned inside the cache synchronization assembly block immediately before loading parameters for `ROM_DCACHE_CLEAN_INV` (`0x8286: mov r0, r5`):
```assembly
    ; --- BREADCRUMB STEP 3: before_dcache ---
    8264:	4839      	ldr	r0, [pc, #228]	; (834c: 0xD20B0884)
    8266:	493a      	ldr	r1, [pc, #232]	; (8350: 0x004D0002)
    8268:	6001      	str	r1, [r0, #0]
    826a:	f3bf 8f4f 	dsb	sy
    826e:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    8272:	3a01      	subs	r2, #1
    8274:	d1fd      	bne.n	8272 <my_restart+0x9a>
    8276:	4937      	ldr	r1, [pc, #220]	; (8354: 0x004C0003)
    8278:	6001      	str	r1, [r0, #0]
    827a:	f3bf 8f4f 	dsb	sy
    827e:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    8282:	3a01      	subs	r2, #1
    8284:	d1fd      	bne.n	8282 <my_restart+0xaa>
    ; --- INVOKE ROM_DCACHE_CLEAN_INV ---
    8286:	4628      	mov	r0, r5          ; r0 = 0x003489B4 (from r5)
    8288:	4621      	mov	r1, r4          ; r1 = size in bytes (from r4)
    828a:	4a33      	ldr	r2, [pc, #204]	; (8358: 0xFC127AB1)
    828c:	4790      	blx	r2
    828e:	f3bf 8f4f 	dsb	sy
```

### Step 4: `after_dcache` (`0x00008292..0x000082B2`)
Positioned immediately after D-cache clean completion and `dsb sy` (`0x828e`), before I-cache invalidation:
```assembly
    828e:	f3bf 8f4f 	dsb	sy
    ; --- BREADCRUMB STEP 4: after_dcache ---
    8292:	482e      	ldr	r0, [pc, #184]	; (834c: 0xD20B0884)
    8294:	492e      	ldr	r1, [pc, #184]	; (8350: 0x004D0002)
    8296:	6001      	str	r1, [r0, #0]
    8298:	f3bf 8f4f 	dsb	sy
    829c:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    82a0:	3a01      	subs	r2, #1
    82a2:	d1fd      	bne.n	82a0 <my_restart+0xc8>
    82a4:	492b      	ldr	r1, [pc, #172]	; (8354: 0x004C0003)
    82a6:	6001      	str	r1, [r0, #0]
    82a8:	f3bf 8f4f 	dsb	sy
    82ac:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    82b0:	3a01      	subs	r2, #1
    82b2:	d1fd      	bne.n	82b0 <my_restart+0xd8>
```

### Step 5: `before_icache` (`0x000082B4..0x000082D4`)
Positioned immediately before loading parameters for `ROM_ICACHE_INV_BP` (`0x82d6: mov r0, r5`):
```assembly
    ; --- BREADCRUMB STEP 5: before_icache ---
    82b4:	4825      	ldr	r0, [pc, #148]	; (834c: 0xD20B0884)
    82b6:	4926      	ldr	r1, [pc, #152]	; (8350: 0x004D0002)
    82b8:	6001      	str	r1, [r0, #0]
    82ba:	f3bf 8f4f 	dsb	sy
    82be:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    82c2:	3a01      	subs	r2, #1
    82c4:	d1fd      	bne.n	82c2 <my_restart+0xea>
    82c6:	4923      	ldr	r1, [pc, #140]	; (8354: 0x004C0003)
    82c8:	6001      	str	r1, [r0, #0]
    82ca:	f3bf 8f4f 	dsb	sy
    82ce:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    82d2:	3a01      	subs	r2, #1
    82d4:	d1fd      	bne.n	82d2 <my_restart+0xfa>
    ; --- INVOKE ROM_ICACHE_INV_BP ---
    82d6:	4628      	mov	r0, r5          ; r0 = 0x003489B4 (from r5)
    82d8:	4621      	mov	r1, r4          ; r1 = size in bytes (from r4)
    82da:	4a20      	ldr	r2, [pc, #128]	; (835c: 0xFC127B09)
    82dc:	4790      	blx	r2
    82de:	f3bf 8f4f 	dsb	sy
    82e2:	f3bf 8f6f 	isb	sy
```

### Step 6: `after_icache` (`0x000082E6..0x00008306`)
Positioned immediately after `isb sy` (`0x82e2`), before interrupt masking (`0x8308: cpsid if`):
```assembly
    82e2:	f3bf 8f6f 	isb	sy
    ; --- BREADCRUMB STEP 6: after_icache ---
    82e6:	4819      	ldr	r0, [pc, #100]	; (834c: 0xD20B0884)
    82e8:	4919      	ldr	r1, [pc, #100]	; (8350: 0x004D0002)
    82ea:	6001      	str	r1, [r0, #0]
    82ec:	f3bf 8f4f 	dsb	sy
    82f0:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    82f4:	3a01      	subs	r2, #1
    82f6:	d1fd      	bne.n	82f4 <my_restart+0x11c>
    82f8:	4916      	ldr	r1, [pc, #88]	; (8354: 0x004C0003)
    82fa:	6001      	str	r1, [r0, #0]
    82fc:	f3bf 8f4f 	dsb	sy
    8300:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    8304:	3a01      	subs	r2, #1
    8306:	d1fd      	bne.n	8304 <my_restart+0x12c>
    ; --- DISABLE INTERRUPTS ---
    8308:	b673      	cpsid	if
```

### Step 7: `before_bx` (`0x0000830A..0x0000832A`)
Positioned after `cpsid if` (`0x8308`) and immediately before handoff address setup and `bx r0` (`0x832c..0x8332`):
```assembly
    8308:	b673      	cpsid	if
    ; --- BREADCRUMB STEP 7: before_bx ---
    830a:	4810      	ldr	r0, [pc, #64]	; (834c: 0xD20B0884)
    830c:	4910      	ldr	r1, [pc, #64]	; (8350: 0x004D0002)
    830e:	6001      	str	r1, [r0, #0]
    8310:	f3bf 8f4f 	dsb	sy
    8314:	f44f 12a0 	mov.w	r2, #1310720	; 0x140000 (ON loop)
    8318:	3a01      	subs	r2, #1
    831a:	d1fd      	bne.n	8318 <my_restart+0x140>
    831c:	490d      	ldr	r1, [pc, #52]	; (8354: 0x004C0003)
    831e:	6001      	str	r1, [r0, #0]
    8320:	f3bf 8f4f 	dsb	sy
    8324:	f44f 1220 	mov.w	r2, #2621440	; 0x280000 (OFF loop)
    8328:	3a01      	subs	r2, #1
    832a:	d1fd      	bne.n	8328 <my_restart+0x150>
    ; --- TERMINAL HANDOFF TO CHDK CORE ---
    832c:	4628      	mov	r0, r5          ; r0 = 0x003489B4 (from r5)
    832e:	f100 0001 	add.w	r0, r0, #1      ; r0 = 0x003489B5 (Thumb bit set)
    8332:	4700      	bx	r0              ; Terminal branch into core _start
```

---

## 7. Step-to-Code Reference Table & Triage Matrix

### 7.1 Generated Reference Table
Generated by `python3 tools/port24_ladder_table.py --markdown`:

| Step # | Step ID | T1 Step | Signal | Cumulative Flashes | Step Iterations | Nominal ms | Max ms (<200ms) | Disassembly Addr | Preserved State |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `after_prologue` | Step 1/2 | **Flash 1** | 1 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x000081E2` | r0-r3 clobbered per AAPCS; r4-r11, sp (0x7FF8), CPSR preserved |
| 2 | `after_copy` | Step 3/4 | **Flash 2** | 2 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x00008246` | r0-r3 clobbered per AAPCS; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved |
| 3 | `before_dcache` | Step 5 | **Flash 3** | 3 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x00008268` | r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved |
| 4 | `after_dcache` | Step 5 | **Flash 4** | 4 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x00008296` | r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved |
| 5 | `before_icache` | Step 6 | **Flash 5** | 5 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x000082B8` | r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved |
| 6 | `after_icache` | Step 6 | **Flash 6** | 6 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x000082EA` | r0-r3 clobbered; r4 (%0), r5 (%1), sp (0x7FF8), CPSR preserved |
| 7 | `before_bx` | Step 7 | **Flash 7** | 7 | 3,932,160 | 78.12 ms | 187.5 ms (YES) | `0x0000830E` | r4 (%0), sp (0x7FF8), CPSR.I/F=1 (disabled), Thumb mode (0x003489B5) |

### 7.2 Failure Point Triage Matrix for Camera Owner Observation

| Observed Signal | Total Flashes | Failure Checkpoint | Subsystem / Mechanism Implicated | Next Action / Triage |
| :--- | :---: | :--- | :--- | :--- |
| **No light (camera stays dark)** | **0** | Before Step 1 (`check_compat` or entry `0x8000`) | Card MBR, dancingbits decryption, or PID/version mismatch | Verify SD card format, dancingbits encoding row 13, or `check_compat` PID `0x32A8` |
| **1 flash**, then dark | **1** | Between Step 1 and Step 2 (`core_copy` or Boot Witness Stage 1 store) | DRAM write fault during payload relocation to `0x003489B4`, or alignment fault during witness store at `0x0035F7A0` | Inspect memory region permissions at `0x003489B4`; check witness struct alignment |
| **2 flashes**, then dark | **2** | Between Step 2 and Step 3 (preparation for D-cache clean) | Register setup or argument loading prior to `ROM_DCACHE_CLEAN_INV` | Inspect register allocation `%0` and `%1` |
| **3 flashes**, then dark | **3** | Inside `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1`) | D-cache DCCISW subroutine fault, invalid address/size argument, or cache lockup | Check parameters `r0 = 0x003489B4`, `r1 = 116816`; inspect ROM `0xFC127AB0` disassembly |
| **4 flashes**, then dark | **4** | Between Step 4 and Step 5 (between D-cache clean and I-cache invalidation) | Bus hang on `dsb sy` or argument setup for I-cache | Verify bus quiescence after cache clean |
| **5 flashes**, then dark | **5** | Inside `ROM_ICACHE_INV_BP` (`0xFC127B09`) | I-cache ICIALLU / BPIALL subroutine fault or invalid parameter | Check parameters `r0 = 0x003489B4`, `r1 = 116816`; inspect ROM `0xFC127B08` disassembly |
| **6 flashes**, then dark | **6** | Between Step 6 and Step 7 (pipeline flush `isb sy` or interrupt mask `cpsid if`) | Pipeline sync exception or mode trap on `cpsid if` | Inspect CPU mode at handoff (must be privileged) |
| **7 flashes**, then dark | **7** | After Step 7 (`before_bx`) **inside CHDK core execution** | **LOADER EXONERATED 100%**. Handoff to core `_start` (`0x003489B5`) succeeded. Crash occurs inside CHDK core (`startup`, BSS init, or `boot()`) | Localize fault to CHDK core startup or early DryOS reinit |

---

## 8. Candidate Artifact Digests & Manifest

### 8.1 Default Control Output (`--flag-off`)
When `--flag-off` is specified (or when building default candidate without ladder), the build pipeline produces an output that is **byte-for-byte identical** to the PORT-19 locked baseline:
- **`DISKBOOT.BIN` SHA-256**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED]`
- **`DISKBOOT.BIN` Size**: `118,001` bytes `[VERIFIED]`
- **`candidate_loader.bin` SHA-256**: `2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a` `[VERIFIED]`
- **`candidate_loader.bin` Size**: `118,000` bytes `[VERIFIED]`
- **`candidate_main.bin` SHA-256**: `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e` `[VERIFIED]`
- **`candidate_main.bin` Size**: `116,816` bytes `[VERIFIED]`

### 8.2 Opt-in Ladder Candidate Artifacts (`--ladder`)
When built with `--ladder`, the deterministic candidate artifacts are:

| Artifact | Size (bytes) | SHA-256 Digest | Status |
| :--- | :---: | :--- | :---: |
| **`DISKBOOT.BIN`** | `118,257` | `530aee849f69b0c8a02c2b51803ef2988e12eeb2e86e79d444f93877f2781abe` | `[VERIFIED: deterministic host build]` |
| **`candidate_loader.bin`** | `118,256` | `649fdff6ce3469824890a5e59d0461c993b08a28f21188b5bfdfbc0db8e0f03b` | `[VERIFIED: deterministic host build]` |
| **`candidate_loader.elf`** | `120,488` | (ELF symbols at `0x8000`) | `[VERIFIED]` |
| **`candidate_main.bin`** | `116,816` | `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e` | `[VERIFIED: bit-for-bit identical to default]` |
| **`candidate_main.elf`** | `211,620` | `8685c90b5e3cf2da33d062828b86e0fc2521cf9c98bc01d1c313a48e718ba7c2` | `[VERIFIED]` |
| **`witness_inspector_gm110c.m`** | `5,580` | `7a53835f7048b3c9e8be3c545efb9b14a85676a7b856de7899ae00dcd697c28f` | `[VERIFIED]` |
| **`witness_inspector_payload.bin`** | `444` | `241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2` | `[VERIFIED]` |

### 8.3 Candidate Validation Results
All 7 validation stages of `tools/validate_candidate_port2a.py` passed cleanly:
1. Canonical Production Invariance: PASS
2. Candidate Core Artifacts: PASS (`_start=0x003489B4`, `boot_witness=0x0035F7A0`, `_end=0x00366CB0`, `b.w startup (0xF000B800)`)
3. Candidate Loader Artifacts & Payload Embedding: PASS (`core_copy -> DCCISW -> ICIALLU -> cpsid if -> bx r0`)
4. Encoded SD Bootloader (DISKBOOT.BIN): PASS (reversible dancingbits decoding)
5. Disjoint Memory and Stack Lifetime: PASS
6. Associated Canon Basic Inspector: PASS
7. Candidate Manifest Integrity: PASS

---

## 9. Safety Invariants & Scope Compliance
- **Phase 0 Read-Only**: Strictly no camera hardware flashing, no firmware modification, and no camera operations performed.
- **Hardware Readiness**: Marked strictly `NO-GO` in manifest; binary execution on physical hardware requires explicit owner approval.
- **Repository Hygiene**: Zero binary files or build outputs are committed to the git repository.
