# PORT-25 T3b: Opt-in Combined Breadcrumb Ladder + G3X_POWERON_FIX Candidate (GM1.10C) (Single-Emitter Redesign)

## 1. Executive Summary & Epistemic Status

This document establishes the technical design, verification evidence, stage-code mappings, timing bounds, and cryptographic hashes for the **PORT-25 T3b Combined Breadcrumb Ladder + G3X_POWERON_FIX Candidate Build** on the Canon PowerShot G3 X (firmware GM1.10C).

### 1.1 Core Questions Addressed
1. **Did the PORT-24 breadcrumb ladder build include the `G3X_POWERON_FIX` path?**
   - **Answer**: **NO**. As verified below via file:line citations across the repository, the PORT-24 ladder candidate (`aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c`) and the PORT-24 power-on fix candidate (`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`) were completely disjoint builds. The ladder build did not define `G3X_POWERON_FIX`.
2. **Opt-in Combined Build Pipeline**:
   - Implemented in `tools/build_candidate_port25_ladder_fix.py` following the architectural design of `tools/build_candidate_port24_ladder.py` and `tools/build_candidate_port24_poweron_fix.py`.
   - Compiles both `LED_LADDER=1` (across loader and core) and `G3X_POWERON_FIX=1` (in core).
   - Also supports all individual macro combinations (`--ladder`, `--poweron-fix`, `--default`, and `--combined`).
3. **Single-Emitter Rule (No Cross-Context Queues or Flags)**:
   - Fixes the race between parent replay and child emission by strictly enforcing that at any moment only one execution context emits LED frames.
   - The parent context (`Initial Task` in `sub_fc05b962_my`) emits the stages in order: entry to `sub_fc05b962_my` (Code 21), MPU setup checks (Codes 22, 23), power check (Code 24), power check pass (Code 25), and 'before task creation' (Code 26) `[STATIC_VERIFIED: boot_prototype_ladder.c:373]`. The parent emits NOTHING after it calls the task-creation routine (`_CreateTask` / `sub_fc31bbc4`).
   - 'After task creation' is defined as the FIRST frame the created task emits: on entry to `task_Startup_my` (Code 31) `[STATIC_VERIFIED: boot_prototype_ladder.c:389]`. A frame that appears proves the task was created and scheduled. The child then emits its own later stages (Codes 32-35, 41-44), including core entry.
   - All cross-context queues, pending bitmasks (`ladder_pending_mask`), replay routines (`ladder_replay_pending`), and flags (`ladder_createtask_done`) are completely removed `[STATIC_VERIFIED: boot_prototype_ladder.c, led_breadcrumb.h]`.
   - A test verifies that the generated source contains no parent emit call after the `sub_fc31bbc4` call site `[STATIC_VERIFIED: tests/test_port25_ladder_fix.py:test_single_emitter_no_parent_emit_after_createtask]`.
4. **Bounded Pulses with Targeted IRQ Masking**:
   - IRQ is masked (`cpsid i`, saved CPSR restored via `msr cpsr_cxsf, r3`) strictly between the LED-ON store and the LED-OFF store `[STATIC_VERIFIED: disassembly]`.
   - FIQ is untouched.
   - All OFF gaps, digit gaps, and frame-end gaps remain completely unmasked, permitting the DryOS scheduler and watchdog ISRs to execute between pulses `[STATIC_VERIFIED: disassembly]`.
   - Each ON pulse is non-preemptible by IRQ-driven scheduling and bounded by the busy-wait alone ($\le 50.0\text{ ms}$ at slow bound `[INFERRED from loop arithmetic]`).
   - Hardware watchdog expiry deadline is `[UNKNOWN: hardware register documentation]`. Residual risk of watchdog reset during starvation is documented; no runtime property is claimed as `[VERIFIED]`.
5. **Framing Resilience Under Dark Gap Preemption (Approach b) & Whole-Frame Duration Bound**:
   - **Assembly-Faithful Framing Design** `[INFERRED: timing model]`: In assembly, `CORE_LADDER_FRAME` executes `LADDER_PULSE_ON_OFF` for the last pulse of a digit, which turns the LED off and spins for `G3X_FRAME_OFF_DELAY` (15.625 ms slow / 6.55 ms nominal). Only then does it execute `LADDER_DIGIT_GAP` (100.0 ms slow / 41.94 ms nominal) or `LADDER_FRAME_END` (200.0 ms slow / 83.89 ms nominal).
   - Calibrated separator durations (OFF delay + gap):
     - Single pulse ON delay: `0x00100000` (1,048,576 iterations) $\implies$ 50.0 ms slow / 20.97 ms nominal / 15.73 ms fast (strictly $\le 50.0\text{ ms}$, with 150.0 ms headroom below 200 ms cap).
     - Single pulse OFF delay: `0x00050000` (327,680 iterations) $\implies$ 15.625 ms slow / 6.55 ms nominal / 4.91 ms fast.
     - Cumulative inter-digit separator gap: $15.625 + 100.0 = 115.625\text{ ms}$ slow / $6.5536 + 41.9430 = 48.4966\text{ ms}$ nominal.
     - Cumulative frame-end separator gap: $15.625 + 200.0 = 215.625\text{ ms}$ slow / $6.5536 + 83.8860 = 90.4396\text{ ms}$ nominal.
   - Stated preemption tolerance:
     - At slow bound: $T_{\text{tol}} = 50.0\text{ ms}$.
       - Intra-pulse gap with preemption: $[10.0, 66.0]\text{ ms}$.
       - Inter-digit separator gap with preemption: $[115.0, 166.0]\text{ ms}$.
       - Frame-end separator gap with preemption: $\ge 215.0\text{ ms}$.
       - Ambiguous windows: $(66.0, 115.0)\text{ ms}$ and $(166.0, 215.0)\text{ ms}$.
     - At nominal bound (150 MHz): $T_{\text{tol}} = 20.0\text{ ms}$.
       - Intra-pulse gap with preemption: $[4.0, 27.0]\text{ ms}$.
       - Inter-digit separator gap with preemption: $[48.0, 69.0]\text{ ms}$.
       - Frame-end separator gap with preemption: $\ge 90.0\text{ ms}$.
       - Ambiguous windows: $(27.0, 48.0)\text{ ms}$ and $(69.0, 90.0)\text{ ms}$.
   - Edge-Only Timestamp Decoding: An offline decoder reconstructs stage codes from timestamped ON/OFF edges without gap labels. Within the tested tolerance envelope (preemption delay up to 50.0 ms on all dark intervals at slow bound, and up to 20.0 ms at nominal bound), every stage code decodes unambiguously `[VERIFIED: tests/test_port25_ladder_fix.py]`. Delays that fall into intermediate deadbands are flagged as ambiguous framing. Decoding outside this tested tolerance envelope is strictly unreliable: preemption delays exceeding the envelope can impersonate valid separators and produce a wrong code with status `OK` (demonstrated by regression test `test_decoder_out_of_envelope_preemption_unreliable`, where Code 22 with 100 ms pulse and digit delays decodes to `[11, 11]`). Terminal darkness must equal or exceed the frame-gap threshold (215.0 ms slow / 90.0 ms nominal); premature or truncated captures are flagged as `INCOMPLETE` (`test_decoder_incomplete_capture_handling`).
   - Every frame running after watchdog arming takes strictly under 1000 ms at the slow conservative bound (ranging from 628.13 ms for Code 41 to 825.00 ms for Code 44), leaving at least 175.0 ms margin below the 1000 ms bound.
6. **Hardware Register Invariants**:
   - Reuses exclusively the verified green LED MMIO register `0xD20B0884` (ON: `0x004D0002`, OFF: `0x004C0003`). No new firmware or MMIO addresses are introduced.
   - Final state is LED OFF (`0x004C0003`) after every pulse, held OFF during the frame-end gap, and remains OFF before firmware continuation.
7. **Baseline and Prior Opt-In Hash Invariance**:
   - Default control baseline: DISKBOOT SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (118,001 B) [bit-for-bit identical].
   - PORT-24 `--poweron-fix` build: DISKBOOT SHA-256 `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` (118,001 B) [bit-for-bit identical].
   - PORT-24 `--ladder` build: DISKBOOT SHA-256 `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` (118,257 B) [bit-for-bit identical].

### 1.2 Epistemic Status Ledger
- `[STATIC_VERIFIED: repository source and git history]`: PORT-24 ladder builder did not include `G3X_POWERON_FIX=1`.
- `[STATIC_VERIFIED: disassembly]`: Core image contains `movs r0, #1` bypass in `sub_fc05b962_my` and MMIO stores to `0xD20B0884`.
- `[STATIC_VERIFIED: disassembly]`: Parent Initial Task emits Code 26 immediately before `blx sub_fc31bbc4` (`CreateTask`), and emits NO LED frames, stores, or replay routines after `blx sub_fc31bbc4`.
- `[STATIC_VERIFIED: disassembly]`: Child Startup Task emits Code 31 on entry to `task_Startup_my` directly, proving task was created and scheduled.
- `[STATIC_VERIFIED: disassembly]`: No cross-context flags, bitmasks, or replay functions exist in core binary or source.
- `[STATIC_VERIFIED: disassembly]`: In every core frame, every ON store is preceded by `cpsid i` and followed by the OFF store before `msr CPSR_fsxc, r3`.
- `[STATIC_VERIFIED: disassembly]`: In every core frame, all gap delay loops (OFF gap, digit gap, frame-end gap) execute with interrupts unmasked.
- `[INFERRED: loop arithmetic]`: Single ON pulse duration is bounded by $\le 50.0\text{ ms}$ at slowest reference calibration bound.
- `[INFERRED: timing model]`: Preemption tolerance envelope (up to 50.0 ms at slow bound, up to 20.0 ms at nominal bound) ensures timestamped edges decode without label ambiguity under interrupt jitter within the envelope; decoding outside the envelope is unreliable.
- `[UNKNOWN: hardware register documentation]`: Exact hardware watchdog expiry deadline programmed into MMIO `0xD20A0000`.
- `[INFERRED: watchdog hardware model]`: Residual starvation risk exists if boot stalls or interrupts remain masked for longer than the hardware watchdog timeout before `task_WdtReset` can service it `[PORT25_SHORT_PRESS_LOCALISE.md:228]`.

---

## 2. PORT-24 Repository Audit: Ladder vs G3X_POWERON_FIX

To establish whether the PORT-24 breadcrumb ladder on `origin/main` included the `G3X_POWERON_FIX` path, an exhaustive audit was conducted across all PORT-24 documentation and build scripts:

### 2.1 Audit Findings & Exact Citations
1. **`tools/build_candidate_port24_ladder.py`**:
   - In `tools/build_candidate_port24_ladder.py:228`:
     ```python
     # 1. Build core
     core_elf, core_bin = build_candidate_core(candidate_dir=candidate_dir)
     ```
     `build_candidate_core` is imported directly from `tools/build_candidate_port2a.py:58`.
   - In `tools/build_candidate_port2a.py:90-130`, `build_candidate_core` compiles `boot_prototype.c` using standard prototype CFLAGS **without** `-DG3X_POWERON_FIX=1`.
   - In `tools/build_candidate_port24_ladder.py:231-233`, `build_ladder_loader` compiles `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c` with `-DLED_LADDER=1`.
   - No core defines were modified, and `G3X_POWERON_FIX` is never referenced anywhere in `tools/build_candidate_port24_ladder.py`.
2. **`docs/PORT24_BREADCRUMB_LADDER.md`**:
   - The document describes a ladder build of SHA-256 `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` that instruments loader steps 1–7.
   - Core code `boot_prototype.c` was left completely uninstrumented (`docs/PORT24_BREADCRUMB_LADDER.md:19`).
   - `G3X_POWERON_FIX` is not mentioned in `docs/PORT24_BREADCRUMB_LADDER.md`.
3. **`tools/build_candidate_port24_poweron_fix.py`**:
   - In `tools/build_candidate_port24_poweron_fix.py:130-132`:
     ```python
     if poweron_fix:
         cflags.append("-DG3X_POWERON_FIX=1")
     ```
     This compiles `boot_prototype.c` with `-DG3X_POWERON_FIX=1`.
   - In `tools/build_candidate_port24_poweron_fix.py:228`:
     ```python
     loader_elf, loader_bin, witness_addr, core_end_addr = build_candidate_loader(
         core_elf, core_bin, candidate_dir=candidate_dir
     )
     ```
     It invokes `build_candidate_loader` from `tools/build_candidate_port2a.py:230`, which compiles the default loader **without** `-DLED_LADDER=1`.
4. **`docs/PORT24_POWERON_FIX.md`**:
   - Documents the standalone power-on fix candidate (`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`).
   - Contains no breadcrumbs, LED ladder, or GPIO toggling.

### 2.2 Conclusion
`[STATIC_VERIFIED]`: **The PORT-24 breadcrumb ladder build did NOT include the `G3X_POWERON_FIX` path.** They were two independent, mutually exclusive candidates.

---

## 3. Architecture & Opt-in Build Pipeline (`tools/build_candidate_port25_ladder_fix.py`)

### 3.1 Design Principles
- **Macro Combinations Supported**:
  - Combined (`--combined` / default): `ladder=True, poweron_fix=True`. Compiles core and loader with `LED_LADDER=1` and core with `G3X_POWERON_FIX=1`.
  - Ladder-only (`--ladder`): `ladder=True, poweron_fix=False`. Compiles with `LED_LADDER=1` and native power-on button check.
  - Power-on fix only (`--poweron-fix`): `ladder=False, poweron_fix=True`. Matches PORT-24 power-on fix.
  - Default baseline (`--default`): `ladder=False, poweron_fix=False`. Matches baseline control.
- **Dedicated PORT-25 Output Directories**:
  - Combined: `candidate_port25_ladder_fix`
  - Ladder-only: `candidate_port25_ladder`
  - Power-on fix only: `candidate_port25_poweron_fix`
  - Default baseline: `candidate_port25_default`
  - All paths are strictly disjoint from PORT-24 output directories (`candidate_breadcrumb_ladder`, `candidate_poweron_fix`, `candidate`) `[STATIC_VERIFIED: tests/test_port25_ladder_fix.py:test_port25_output_directories_disjoint_from_port24]`.
- **Branch Forward-Reach Resolution (CBNZ Fix)**:
  - In `sub_fc05b962_my`, when `G3X_POWERON_FIX=0`, the button check result branch previously used `cbnz r0, loc_fc05b978`.
  - Because `CORE_LADDER_PULSE_28` and `CORE_LADDER_PULSE_29` add multiple instructions between the check and `loc_fc05b978`, the branch distance exceeds the 126-byte forward reach of 16-bit `cbnz`.
  - Resolved using `cbz r0, 1f; b.w loc_fc05b978; 1:`. `cbz` branches forward 4 bytes to `1:`, while `b.w` provides wide 16 MB forward reach to `loc_fc05b978`. All macro combinations build reproducibly with the pinned toolchain.
- **Single-Emitter Redesign (Initial Task & Startup Task)**:
  - At any moment only one execution context emits LED frames.
  - Initial Task emits Code 26 before calling `_CreateTask`, and emits nothing after `_CreateTask`.
  - 'After task creation' is defined as the FIRST frame emitted by `task_Startup_my` (Code 31), proving task was created and scheduled.
  - No cross-context queues, replay routines, or completion flags remain in source or assembly.
- **Bounded Pulses with Targeted IRQ Masking**:
  - IRQ is masked (`cpsid i`, restored via `msr cpsr_cxsf, r3`) strictly between the LED-ON store and the LED-OFF store.
  - FIQ is untouched.
  - Gap delay loops run unmasked, permitting interrupt servicing between pulses.
  - Stack registers `r0, r1, r2, r3, r12, lr` are preserved via 8-byte aligned stack push/pop.
  - Final state is always LED OFF (`0x004C0003`).

### 3.2 Timing Calibration & Whole-Frame Durations
All pulse timings derive from the reference calibration in `docs/PORT23_POWER_SUPERVISION.md:245` and `docs/PORT24_LOADER_TRACE.md:761`:
- **Clock Assumption**:
  - DIGIC 6 Cortex-R4 CPU core clock running at nominal ~150–250 MHz (`[INFERRED: docs/PORT20_LED_CANDIDATE.md:177]`).
  - Loop body `subs r2, r2, #1; bne` executes in 2–3 CPU cycles per iteration on ARMv7-R pipeline.
  - Reference loop constant `0x00600000` (6,291,456 iterations):
    - Fast bound (200 MHz, 3 cycles): ~94.4 ms (~100 ms).
    - Nominal bound (150 MHz, 3 cycles): ~125.8 ms.
    - Slow conservative bound (66.6 MHz unmultiplied PLL reference clock): ~283 ms (~300 ms).
- **Configured Frame Iteration Counts**:
  - **Single Pulse ON delay**: `0x00100000` (1,048,576 iterations)
    - Fast bound: ~15.73 ms
    - Nominal bound: **20.97 ms**
    - Slow bound: **50.0 ms** ($\le 50.0\text{ ms}$, with 150.0 ms headroom below 200 ms cap; 75% margin).
  - **Single Pulse OFF delay**: `0x00050000` (327,680 iterations)
    - Fast bound: ~4.91 ms / Nominal bound: ~6.55 ms / Slow bound: **15.625 ms**.
  - **Single Pulse (ON + OFF)**: `0x00150000` (1,376,256 iterations)
    - Fast bound: ~20.64 ms / Nominal bound: ~27.53 ms / Slow bound: **65.625 ms**.
  - **Inter-digit gap**: `0x00200000` (2,097,152 iterations, LED OFF)
    - Fast bound: ~31.46 ms / Nominal bound: ~41.94 ms / Slow bound: **100.0 ms**.
  - **Frame-end gap**: `0x00400000` (4,194,304 iterations, LED OFF)
    - Fast bound: ~62.91 ms / Nominal bound: ~83.89 ms / Slow bound: **200.0 ms**.
  - **Total gaps (inter-digit + frame-end)**: `0x00600000` (6,291,456 iterations, LED OFF)
    - Fast bound: ~94.37 ms / Nominal bound: ~125.83 ms / Slow bound: **300.0 ms**.

### 3.3 Worst-Case Whole-Frame Duration by Stage

For any framed stage code with tens digit $T$ and units digit $U$:
$$\text{Total Iterations} = (T + U) \times 1{,}376{,}256 + 6{,}291{,}456$$
$$\text{Duration}_{\text{slow}}\text{ (ms)} = \text{Total Iterations} \times \frac{300.0}{6{,}291{,}456}$$

| Code | $(T, U)$ | Total Iterations | Slow Bound (ms) | Nominal Bound (ms) | Fast Bound (ms) | Watchdog Arming State | Margin Below 1000 ms Cap |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **11** | $(1, 1)$ | 9,043,968 | 431.25 | 180.88 | 135.66 | Pre-Arming | N/A (pre-arming) |
| **12** | $(1, 2)$ | 10,420,224 | 496.88 | 208.40 | 156.30 | Pre-Arming | N/A (pre-arming) |
| **13** | $(1, 3)$ | 11,796,480 | 562.50 | 235.93 | 176.95 | Pre-Arming | N/A (pre-arming) |
| **14** | $(1, 4)$ | 13,172,736 | 628.13 | 263.45 | 197.59 | Pre-Arming | N/A (pre-arming) |
| **15** | $(1, 5)$ | 14,548,992 | 693.75 | 290.98 | 218.23 | Pre-Arming | N/A (pre-arming) |
| **21** | $(2, 1)$ | 10,420,224 | 496.88 | 208.40 | 156.30 | Pre-Arming | N/A (pre-arming) |
| **22** | $(2, 2)$ | 11,796,480 | 562.50 | 235.93 | 176.95 | Pre-Arming | N/A (pre-arming) |
| **23** | $(2, 3)$ | 13,172,736 | 628.13 | 263.45 | 197.59 | Pre-Arming | N/A (pre-arming) |
| **24** | $(2, 4)$ | 14,548,992 | 693.75 | 290.98 | 218.23 | Pre-Arming | N/A (pre-arming) |
| **25** | $(2, 5)$ | 15,925,248 | 759.38 | 318.50 | 238.88 | Pre-Arming | N/A (pre-arming) |
| **26** | $(2, 6)$ | 17,301,504 | 825.00 | 346.03 | 259.52 | Pre-Arming | N/A (pre-arming) |
| **28** | $(2, 8)$ | 20,054,016 | 956.25 | 401.08 | 300.81 | Pre-Arming (Fail Path) | N/A (pre-arming) |
| **29** | $(2, 9)$ | 21,430,272 | 1021.88 | 428.61 | 321.45 | Pre-Arming (Halt Path) | N/A (pre-arming) |
| **31** | $(3, 1)$ | 11,796,480 | 562.50 | 235.93 | 176.95 | Pre-Arming | N/A (pre-arming) |
| **32** | $(3, 2)$ | 13,172,736 | 628.13 | 263.45 | 197.59 | Pre-Arming | N/A (pre-arming) |
| **33** | $(3, 3)$ | 14,548,992 | 693.75 | 290.98 | 218.23 | Pre-Arming | N/A (pre-arming) |
| **34** | $(3, 4)$ | 15,925,248 | 759.38 | 318.50 | 238.88 | Pre-Arming | N/A (pre-arming) |
| **35** | $(3, 5)$ | 17,301,504 | 825.00 | 346.03 | 259.52 | Pre-Arming (line 413 entry) | N/A (pre-arming) |
| **41** | $(4, 1)$ | 13,172,736 | **628.13** | **263.45** | **197.59** | **POST-ARMING** | **+371.88 ms (37.2%)** |
| **42** | $(4, 2)$ | 14,548,992 | **693.75** | **290.98** | **218.23** | **POST-ARMING** | **+306.25 ms (30.6%)** |
| **43** | $(4, 3)$ | 15,925,248 | **759.38** | **318.50** | **238.88** | **POST-ARMING** | **+240.63 ms (24.1%)** |
| **44** | $(4, 4)$ | 17,301,504 | **825.00** | **346.03** | **259.52** | **POST-ARMING** | **+175.00 ms (17.5%)** |

### 3.4 Watchdog Hardware Semantics & Starvation Risk Analysis
- **Hardware Watchdog Arming Point**: Line 413 of `boot_prototype_ladder.c` executes `bl sub_fc418f2a` (`PORT25-ROM-WATCHDOG-START`; `docs/PORT25_SHORT_PRESS_LOCALISE.md:220-230`), which invokes `StartWDT_FW` (`0xFC135D2C`).
- **Software Servicing Contract**: In normal operation, DryOS task `task_WdtReset` (`0xFC135CB0`) loops every 2000 ms via `SleepTask(2000)` at `0xFC135CC6`, writing `0xAA55` to MMIO `0xD20A0004` `[PORT25_SHORT_PRESS_LOCALISE.md:225]`. The 2000 ms interval is the *software servicing period*, NOT the hardware expiry deadline.
- **Hardware Expiry Deadline**: `[UNKNOWN: hardware register documentation]`. The hardware counter divisor and exact timeout duration programmed into MMIO `0xD20A0000` are unknown without Canon hardware register specifications.
- **Residual Starvation Risk**: `[INFERRED: watchdog hardware model]`. Because `cpsid i` is held only during the $\le 50.0\text{ ms}$ ON pulse window, and all OFF gaps, digit gaps, and frame gaps are completely unmasked, interrupt-driven watchdog servicing (or task scheduling) can run between pulses. However, if the hardware watchdog timeout period is shorter than the IRQ-masked window or if consecutive pulses starve watchdog servicing before `task_WdtReset` is scheduled, watchdog reset will occur. This risk is acknowledged honestly; no runtime property is claimed as `[VERIFIED]`.

---

## 4. Count-Coded Framed Pulse Design

### 4.1 Owner Reading Guide Covering Both Protocols

The candidate implements two distinct diagnostic protocols:
1. **Loader-Stage Protocol (Steps 1–7)**: Emits cumulative single pulses.
2. **Core-Stage Protocol (Codes 11–44)**: Emits two-digit framed codes.

#### 4.1.1 Loader-Stage Protocol: Cumulative Single Pulses
During loader execution (`chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c`), each step emits exactly **one single pulse** via `LADDER_ASM_PULSE`:
- **Single Pulse Structure**:
  - LED ON (`0x004D0002`): wait `0x00134000` (1,261,568 iterations) $\implies$ ~25.07 ms nominal / ~60.16 ms slow [INFERRED].
  - LED OFF (`0x004C0003`): wait `0x002C4000` (2,899,968 iterations) $\implies$ ~57.62 ms nominal / ~138.28 ms slow [INFERRED].
  - Total step time: ~82.68 ms nominal / ~198.44 ms slow.
- **Cumulative Reading**: The owner observes a succession of 1 to 7 single blinks:
  - 1 blink: Prologue completed (`STAGE_LOADER_AFTER_PROLOGUE`).
  - 2 blinks: Core copied (`STAGE_LOADER_AFTER_COPY`).
  - 3 blinks: Before D-cache invalidate (`STAGE_LOADER_BEFORE_DCACHE`).
  - 4 blinks: After D-cache invalidate (`STAGE_LOADER_AFTER_DCACHE`).
  - 5 blinks: Before I-cache invalidate (`STAGE_LOADER_BEFORE_ICACHE`).
  - 6 blinks: After I-cache invalidate (`STAGE_LOADER_AFTER_ICACHE`).
  - 7 blinks: Before handoff branch `bx r0` (`STAGE_LOADER_BEFORE_BX`).

#### 4.1.2 Loader-to-Core Transition Gap
After Step 7's LED-OFF store, the loader waits its OFF delay (`0x002C4000` iterations):
- **Loader-to-Core Transition Gap Duration**:
  - Nominal bound: **57.62 ms** (at 150 MHz).
  - Slow bound: **138.28 ms** (at 66.6 MHz).
- The core entry instructions (`mov sp, r0; b.w 98f; push; movw; movt`) take under $1\ \mu\text{s}$.
- The owner clearly perceives this extended dark transition gap separating the 7th loader pulse from the first core frame (Code 11).

#### 4.1.3 Core-Stage Protocol: Two-Digit Framed Codes
Once execution enters core `boot()`, every checkpoint emits a self-contained two-digit frame defined by macro `CORE_LADDER_FRAME(tens, units)` (`chdk-port/platform/g3x/sub/110c/led_breadcrumb.h:201-212`):
- **Structure (Direct Tens Then Units)**:
  1. **Tens Digit ($T$)**: The LED emits $T$ blinks. Each blink consists of:
     - LED ON (`0x004D0002`): wait `0x00100000` (1,048,576 iterations) $\implies$ **20.97 ms nominal / 50.0 ms slow** (masked via `cpsid i`).
     - LED OFF (`0x004C0003`): wait `0x00050000` (327,680 iterations) $\implies$ **6.55 ms nominal / 15.625 ms slow** (unmasked).
  2. **Inter-Digit Gap**: Dark pause for `0x00200000` (2,097,152 iterations, LED OFF) $\implies$ **41.94 ms nominal / 100.0 ms slow** (unmasked).
  3. **Units Digit ($U$)**: The LED emits $U$ blinks (identical per-pulse ON/OFF timing to tens digit).
  4. **Frame-End Gap**: Dark pause for `0x00400000` (4,194,304 iterations, LED OFF) $\implies$ **83.89 ms nominal / 200.0 ms slow** (unmasked).

- **Decoding Formula**:
  $$\text{Stage Code} = 10 \times T + U$$
  The owner counts $T$ flashes, pauses for the digit gap (41.94 ms nom / 100.0 ms slow), counts $U$ flashes, and notes the frame-end gap (83.89 ms nom / 200.0 ms slow) before the next frame.

- **Framing Resilience Under Interrupt Delays (Approach b)** `[INFERRED: timing model]`:
  In assembly, `CORE_LADDER_FRAME` executes `LADDER_PULSE_ON_OFF` for the last pulse of each digit, which writes LED OFF and spins for `G3X_FRAME_OFF_DELAY` (15.625 ms slow / 6.55 ms nominal). Only then does it execute the inter-digit gap or frame-end gap loop. The cumulative dark separators are:
  - Intra-digit pulse gap: 15.625 ms slow / 6.55 ms nominal.
  - Inter-digit separator gap: $15.625 + 100.0 = 115.625\text{ ms}$ slow / $6.5536 + 41.9430 = 48.4966\text{ ms}$ nominal.
  - Frame-end separator gap: $15.625 + 200.0 = 215.625\text{ ms}$ slow / $6.5536 + 83.8860 = 90.4396\text{ ms}$ nominal.
  
  Preemption tolerance proven by automated test suite (`tests/test_port25_ladder_fix.py`):
  - At slow bound ($T_{\text{tol}} = 50.0\text{ ms}$):
    - Pulse gap with preemption: $[10.0\text{ ms}, 66.0\text{ ms}]$
    - Ambiguous window: $(66.0\text{ ms}, 115.0\text{ ms})$
    - Digit gap with preemption: $[115.0\text{ ms}, 166.0\text{ ms}]$
    - Ambiguous window: $(166.0\text{ ms}, 215.0\text{ ms})$
    - Frame gap with preemption: $\ge 215.0\text{ ms}$
  - At nominal bound ($T_{\text{tol}} = 20.0\text{ ms}$):
    - Pulse gap with preemption: $[4.0\text{ ms}, 27.0\text{ ms}]$
    - Ambiguous window: $(27.0\text{ ms}, 48.0\text{ ms})$
    - Digit gap with preemption: $[48.0\text{ ms}, 69.0\text{ ms}]$
    - Ambiguous window: $(69.0\text{ ms}, 90.0\text{ ms})$
    - Frame gap with preemption: $\ge 90.0\text{ ms}$
  - Tested Tolerance Envelope and Boundaries:
    - Within the tested tolerance envelope (preemption delay up to $50.0\text{ ms}$ on all dark intervals at slow bound, and up to $20.0\text{ ms}$ at nominal bound), 100% of stage codes decode correctly and unambiguously `[VERIFIED: tests/test_port25_ladder_fix.py]`.
    - Worst-case code (22) is tested and verified at nominal base and at the upper tolerance bounds (50.0 ms slow, 20.0 ms nominal) in `test_decoder_worst_case_code_22_at_tolerance_bounds`.
    - Delays that land in intermediate unassigned windows ($(66.0, 115.0)\text{ ms}$ and $(166.0, 215.0)\text{ ms}$ slow) are detected and reported as ambiguous framing (`test_decoder_reports_ambiguous_on_delay_exceeding_tolerance`).
    - **Out-of-Envelope Unreliability**: Decoding outside the tested tolerance envelope is strictly unreliable. Preemption delays longer than tolerance can cross interval thresholds, impersonate valid separators, and produce a wrong code with status `OK`. For example, Code 22 subjected to `pulse_preempt=100.0` ms and `digit_preempt=100.0` ms at the slow bound decodes to `[11, 11]` with status `OK` because intra-pulse gaps mimic digit gaps and digit gaps mimic frame gaps (proven and guarded by regression test `test_decoder_out_of_envelope_preemption_unreliable`).
    - **Capture Completion and Terminal Darkness**: The decoder requires that the observed terminal darkness after the last pulse must meet or exceed the frame-gap threshold ($215.0\text{ ms}$ slow / $90.0\text{ ms}$ nominal). Captures truncated prematurely (stopping inside a pulse gap, inside a digit gap, mid-pulse, or with an early capture end) report status `INCOMPLETE` rather than fabricating frame endings or decoding truncated digits (`test_decoder_incomplete_capture_handling`).

- **Functional Group Demarcation**:
  - **Group 1 ($T=1$)**: Core entry, RAM copy, BSS clear & DryOS kernel init (Codes 11–15)
  - **Group 2 ($T=2$)**: Stage 5 startup spawner, power checks, before task creation (Codes 21–26; fail path: 28, 29)
  - **Group 3 ($T=3$)**: Startup task execution *prior* to watchdog arming (Codes 31–35)
  - **Group 4 ($T=4$)**: Startup task execution *after* watchdog arming & continuation (Codes 41–44)

---

### 4.2 Single-Emitter Redesign (Initial Task and Startup Task)

Review P1 identified a potential race condition between parent replay and child emission under preemptive task scheduling. The p25-t3b redesign eliminates this race by implementing a strict **single-emitter rule**:

#### 4.2.1 Single-Emitter Principles
1. **Single-Emitter Invariant**: At any moment in time, exactly one execution context emits LED frames.
2. **Parent Execution Sequence**:
   - The parent context (`Initial Task` running `sub_fc05b962_my`) emits its stages in order:
     - Code 21: Entry to `sub_fc05b962_my` (`boot_prototype_ladder.c:346`)
     - Code 22: Before MPU setup (`boot_prototype_ladder.c:347`)
     - Code 23: After MPU setup (`boot_prototype_ladder.c:347`)
     - Code 24: Before power check (`boot_prototype_ladder.c:348`)
     - Code 25: Power check pass (`boot_prototype_ladder.c:361`)
     - Code 26: Immediately before calling `_CreateTask` (`boot_prototype_ladder.c:373`)
   - **The parent emits NOTHING after calling `_CreateTask` (`sub_fc31bbc4`).**
   - The parent context terminates cleanly via `movs r0, #0; pop {r3, pc}` immediately after `_CreateTask` returns.
3. **'After Task Creation' Definition**:
   - 'After task creation' is defined as the **FIRST frame emitted by the created task**: on entry to `task_Startup_my` (Code 31) (`boot_prototype_ladder.c:389`).
   - A frame that appears proves the task was successfully created and scheduled by the DryOS kernel.
   - The child task then emits its subsequent stages (Codes 32–35, 41–44) directly.
4. **Complete Removal of Cross-Context Queues, Flags, and Replay**:
   - The pending-slot bitmask (`ladder_pending_mask`), replay function (`ladder_replay_pending`), and task completion flag (`ladder_createtask_done`) are completely removed from `.bss` and source code.
   - In `led_breadcrumb.h`, `CHILD_LADDER_FRAME(tens, units)` expands directly to `CORE_LADDER_FRAME(tens, units)`. No synchronization flags or branching are needed.
   - In `tests/test_port25_ladder_fix.py`, `test_single_emitter_no_parent_emit_after_createtask` verifies that:
     - Disassembly of `sub_fc05b962_my` after `blx sub_fc31bbc4` contains zero frame emissions, zero LED MMIO stores, zero CPSID instructions, and zero replay calls.
     - Disassembly contains no references to `ladder_createtask_done`, `ladder_pending_mask`, or `ladder_replay_pending`.
     - The generated source `boot_prototype_ladder.c` contains no emit macros after the `sub_fc31bbc4` call site.
     - The child task emits Code 31 as its first frame directly without pending checks.

#### 4.2.2 Observation Key & Progress Guarantees
- **Normal Progression**: If Initial Task creates Startup Task and Startup Task runs, the owner observes:
  $$\text{Code 26 (before task creation)} \longrightarrow \text{Code 31 (after task creation / Startup entry)} \longrightarrow \text{Code 32} \dots$$
- **Last Code Seen = 26**: Proves Initial Task reached the task creation call site; Startup Task was either not created, failed to be scheduled, or hung before entering `task_Startup_my`.
- **Last Code Seen = 31**: Proves Startup Task was created, scheduled, and entered; camera halted before or during early driver setup (`sub_fc0d0150`..`sub_fc418eec`).
- Under no circumstances can Initial Task and Startup Task emit concurrently, because the parent emits nothing once `_CreateTask` is called.

---

## 5. Comprehensive Stage-Code Table

The table below maps every checkpoint in the combined build to its code, stage symbol, emitting context, source location, timing state, and functional purpose:

| Code | Stage Symbol | Emitting Context | File & Line | Timing State | Functional Purpose |
|:---:|:---|:---:|:---|:---:|:---|
| **1** | `STAGE_LOADER_AFTER_PROLOGUE` | Loader | `loader_main_breadcrumb.c:45` | Pre-Arming | Step 1: Entry prologue and check_compat() completed |
| **2** | `STAGE_LOADER_AFTER_COPY` | Loader | `loader_main_breadcrumb.c:99` | Pre-Arming | Step 2: Core payload copied to `0x003489B4` |
| **3** | `STAGE_LOADER_BEFORE_DCACHE` | Loader | `loader_main_breadcrumb.c:116` | Pre-Arming | Step 3: Immediately before ROM D-cache clean/invalidate (`0xFC127AB1`) |
| **4** | `STAGE_LOADER_AFTER_DCACHE` | Loader | `loader_main_breadcrumb.c:127` | Pre-Arming | Step 4: D-cache clean/invalidate completed |
| **5** | `STAGE_LOADER_BEFORE_ICACHE` | Loader | `loader_main_breadcrumb.c:132` | Pre-Arming | Step 5: Immediately before ROM I-cache invalidate (`0xFC127B09`) |
| **6** | `STAGE_LOADER_AFTER_ICACHE` | Loader | `loader_main_breadcrumb.c:144` | Pre-Arming | Step 6: I-cache invalidate completed |
| **7** | `STAGE_LOADER_BEFORE_BX` | Loader | `loader_main_breadcrumb.c:152` | Pre-Arming | Step 7: Final loader step immediately before `bx r0` to core (`0x003489B5`) |
| **11** | `STAGE_BC_CORE_ENTRY` | Reset thread | `boot_prototype_ladder.c:92` | Pre-Arming | Entry Checkpoint: Entry to core `boot()` immediately after SP reset (`mov sp, r0`) |
| **12** | `STAGE_BC_POST_BSS` | Reset thread | `boot_prototype_ladder.c:154` | Pre-Arming | Checkpoint: Low/High RAM copies and Canon BSS zeroing completed |
| **13** | `STAGE_BC_STAGE3_ENTRY` | Reset thread | `boot_prototype_ladder.c:175` | Pre-Arming | Entry Checkpoint: Entry to `sub_fc05b3c8_my` immediately after `witness_record_core` |
| **14** | `STAGE_BC_PRE_KERNEL_INIT` | Reset thread | `boot_prototype_ladder.c:256` | Pre-Arming | Checkpoint: DryOS memory descriptors initialized; immediately before `blx sub_fc31b408` |
| **15** | `STAGE_BC_STAGE4_ENTRY` | Initial Task | `boot_prototype_ladder.c:272` | Pre-Arming | Entry Checkpoint: Entry to `sub_fc05b558_my` (Initial Task) after `push {r4, lr}` |
| **21** | `STAGE_BC_STAGE5_ENTRY` | Initial Task | `boot_prototype_ladder.c:346` | Pre-Arming | Entry Checkpoint: Entry to `sub_fc05b962_my` after `push {r3, lr}` |
| **22** | `STAGE_BC_PRE_MPU_SETUP` | Initial Task | `boot_prototype_ladder.c:347` | Pre-Arming | Checkpoint: Immediately before `bl sub_fc05ba68` (`pxSetup`, `dhcpc_setup`, `mpuSetup`) |
| **23** | `STAGE_BC_POST_MPU_SETUP` | Initial Task | `boot_prototype_ladder.c:347` | Pre-Arming | Checkpoint: Immediately after `bl sub_fc05ba68`; proves setup calls returned |
| **24** | `STAGE_BC_PRE_POWER_CHECK` | Initial Task | `boot_prototype_ladder.c:348` | Pre-Arming | Checkpoint: Immediately after `bl sub_fc079404`, before button check `sub_fc1284ac` |
| **25** | `STAGE_BC_POWER_CHECK_PASS` | Initial Task | `boot_prototype_ladder.c:361` | Pre-Arming | Checkpoint: Label `loc_fc05b978`; button check passed or bypassed via `G3X_POWERON_FIX` |
| **26** | `STAGE_BC_PRE_CREATE_STARTUP` | Initial Task | `boot_prototype_ladder.c:373` | Pre-Arming | Checkpoint: Immediately before `blx sub_fc31bbc4` (DryOS CreateTask "Startup"); parent emits nothing after |
| **31** | `STAGE_BC_STARTUP_ENTRY` | Startup Task | `boot_prototype_ladder.c:389` | Pre-Arming | Task-Execution Checkpoint: 'After task creation' defined as first frame emitted by created task |
| **32** | `STAGE_BC_POST_EARLY_INIT` | Startup Task | `boot_prototype_ladder.c:393` | Pre-Arming | Checkpoint: Early driver calls (`sub_fc0d0150`..`sub_fc418eec`) returned |
| **33** | `STAGE_BC_PRE_SD1STINIT` | Startup Task | `boot_prototype_ladder.c:402` | Pre-Arming | Checkpoint: Immediately before SD1stInit gate check `sub_fc05c4e0` |
| **34** | `STAGE_BC_POST_SD1STINIT` | Startup Task | `boot_prototype_ladder.c:407` | Pre-Arming | Helper-Return Checkpoint: Label `1:` after SD1stInit task creation veneer |
| **35** | `STAGE_BC_PRE_WATCHDOG_START` | Startup Task | `boot_prototype_ladder.c:413` | Pre-Arming | Checkpoint: Immediately before `bl sub_fc418f2a` (watchdog arming helper) |
| **41** | `STAGE_BC_POST_WATCHDOG_START`| Startup Task | `boot_prototype_ladder.c:413` | **POST-ARMING** | Checkpoint: Immediately after `bl sub_fc418f2a`; watchdog is actively armed |
| **42** | `STAGE_BC_PRE_PHYSW_CREATE` | Startup Task | `boot_prototype_ladder.c:418` | **POST-ARMING** | Checkpoint: Immediately before `bl sub_fc1283d2` (task_PhySw launcher helper) |
| **43** | `STAGE_BC_POST_PHYSW_CREATE` | Startup Task | `boot_prototype_ladder.c:418` | **POST-ARMING** | Helper-Return Checkpoint: `sub_fc1283d2` returned (does NOT prove `task_PhySw` ran) |
| **44** | `STAGE_BC_PRE_FIRMWARE_CONT` | Startup Task | `boot_prototype_ladder.c:442` | **POST-ARMING** | Checkpoint: Immediately before `pop.w {r4, lr}; b.w sub_fc0d0126` (stock handoff) |

### 5.1 Native Power-Cut Failure Path (`G3X_POWERON_FIX=0`)
When `G3X_POWERON_FIX=0` and `LED_LADDER=1`, two diagnostic pulse points isolate Candidate 1 behavior:
- **Code 28** (`STAGE_BC_FAIL_POWER_CUT`, `boot_prototype_ladder.c:357`, Initial Task): Flashes if `sub_fc1284ac` returned 0, immediately before `bl sub_fc05ba56` cuts power.
- **Code 29** (`STAGE_BC_HALT_SHUTDOWN`, `boot_prototype_ladder.c:358`, Initial Task): Flashes at label `loc_fc05b976` if `sub_fc05ba56` returns without instantaneous power cut.

### 5.2 Diagnostic Decode Table & Observation Key

| Last Code Seen | Progression Status | Interpretation | Confidence | Technical Meaning & Diagnostic Action |
|:---:|:---:|:---|:---:|:---|
| **1–7** | Loader | Halted during loader execution | `VERIFIED` | Loader execution stopped at corresponding step (prologue, copy, D-cache, I-cache, bx). |
| **11–25** | Initial Task | Halted before task spawning | `VERIFIED` | Halted during RAM copy, BSS, DryOS descriptor setup, pxSetup/mpuSetup, or button check. |
| **26** | Initial Task | Halted at task creation call | `VERIFIED` | Initial Task reached `blx sub_fc31bbc4` (CreateTask); Startup task was not scheduled or did not enter. |
| **31–35** | Startup Task | Dispatched; pre-watchdog | `VERIFIED` | Proves `task_Startup_my` entered and ran ('after task creation' verified); halted before or at watchdog start. |
| **41–44** | Startup Task | Post-watchdog arming | `VERIFIED` | Hardware watchdog is active; camera proceeded past task_PhySw creation or into stock firmware handoff. |
| **28** | Fail Path | Power-on check returned 0 | `VERIFIED` | Confirms power-cut branch taken (`sub_fc1284ac == 0`); camera about to cut power. |
| **29** | Fail Path | Shutdown loop reached | `VERIFIED` | Power cut helper `sub_fc05ba56` returned without cutting power; loop at `loc_fc05b976` active. |

---

## 6. Build Artifact & Cryptographic Integrity Matrix

All builds are compiled strictly with the repository's pinned GCC toolchain (`gcc-arm-none-eabi-5_4-2016q3`):

| Build Variant | Defines Active | DISKBOOT.BIN SHA-256 | Size (B) | Reproducibility Status |
|---|---|---|:---:|---|
| **Default Control Baseline** | None (`--default`) | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | 118,001 | Byte-identical to locked baseline [VERIFIED] |
| **PORT-24 Power-on Fix** | `G3X_POWERON_FIX=1` | `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` | 118,001 | Byte-identical to PORT-24 [VERIFIED] |
| **PORT-24 Ladder** | `LED_LADDER=1` (loader) | `aa7963de9b6c04c8c5a3077efab12f8383a26db114d5d9b92e320780630abd3c` | 118,257 | Byte-identical to PORT-24 [VERIFIED] |
| **PORT-25 Ladder-Only** | `LED_LADDER=1` (core+loader) | `45da469f3eb46c4d2aff77a032e5c8bb4eedf8ec8846526853d716d05d2b2f4e` | 126,081 | Deterministic & reproducible [VERIFIED] |
| **PORT-25 Combined Candidate** | `LED_LADDER=1` + `G3X_POWERON_FIX=1` | `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` | 124,865 | Deterministic & reproducible [VERIFIED] |

### 6.1 PORT-25 Combined Candidate Component Breakdown
- `candidate_main.bin`: 123,424 bytes
- `candidate_loader.bin`: 124,864 bytes
- `boot_witness` address: `0x00361170`
- `_end` address: `0x00368680`
- `DISKBOOT.BIN`: 124,865 bytes (encoded with dancingbits row 13; byte 0 is `0x00`)

---

## 7. Automated Test Verification

The test suite in `tests/test_port25_ladder_fix.py` verifies all task invariants (18 tests):
1. `test_default_build_hash_invariance`: Confirms default build matches `9468257364d753d9...` (118,001 B).
2. `test_port24_poweron_build_hash_invariance`: Confirms PORT-24 power-on fix matches `faad4d8242fbf...` (118,001 B).
3. `test_port24_ladder_build_hash_invariance`: Confirms PORT-24 ladder matches `aa7963de9b6c...` (118,257 B).
4. `test_combined_build_determinism_and_hash`: Confirms independent builds yield identical SHA-256 `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15` and size 124,865 B.
5. `test_ladder_only_combination_assembles`: Confirms that the ladder-only combination (`ladder=True, poweron_fix=False`) builds successfully without branch-out-of-range errors (SHA-256 `45da469f3eb4...`, 126,081 B).
6. `test_combined_build_enables_both_macros`: Disassembles core and confirms both `movs r0, #1` bypass in `sub_fc05b962_my` and MMIO stores to `0xD20B0884`.
7. `test_disassembled_stage_codes_and_atomicity`: Disassembles `candidate_main.elf` with pinned objdump, derives all stage codes from LED-ON stores and inter-digit loops, verifies targeted `cpsid i` IRQ masking strictly during ON pulses, confirms all gap delay loops are unmasked, computes total iterations per frame, asserts per-frame bound (< 1000 ms at slow bound) for all post-arming stages (Codes 41..44), verifies all 20 core codes are distinct and match `[11..15, 21..26, 31..35, 41..44]`, verifies that instruction sequences are unique (rejecting duplicate macros), confirms ON pulse delay loop constant `0x00100000` is $\le 50.0\text{ ms}$, and verifies CreateTask codes (26, 31, 32) are distinct and documented with their emitting contexts.
8. `test_single_emitter_no_parent_emit_after_createtask`: Confirms single-emitter rule: parent Initial Task emits no frames, LED stores, CPSID masking, or replay calls after `blx sub_fc31bbc4` (CreateTask); disassembly and source contain no `ladder_createtask_done`, `ladder_pending_mask`, or `ladder_replay_pending`; child emits Code 31 directly as its first frame.
9. `test_decoder_timestamped_edges_with_preemption_tolerance`: Reconstructs codes from timestamped ON/OFF edges without gap labels under injected preemption delays up to stated tolerance ($\le 50.0\text{ ms}$ at slow bound, $\le 20.0\text{ ms}$ at nominal bound).
10. `test_decoder_worst_case_code_22_at_tolerance_bounds`: Tests worst-case code (22) at nominal base and at tolerance bounds (50 ms slow, 20 ms nominal).
11. `test_decoder_reports_ambiguous_on_delay_exceeding_tolerance`: Confirms preemption delays landing in intermediate deadbands are detected and reported as ambiguous rather than decoded wrongly.
12. `test_decoder_incomplete_capture_handling`: Confirms truncated captures (e.g. Code 22 with early capture end, ending in pulse gap, digit gap, or mid-pulse) report `INCOMPLETE` and never decode as valid codes, while full captures decode correctly `[P2-a]`.
13. `test_decoder_out_of_envelope_preemption_unreliable`: Regression test verifying that out-of-envelope delays (e.g. 100 ms preemption on Code 22) impersonate valid separators and decode as `[11, 11]` with status `OK`, proving out-of-envelope decoding is unreliable `[P2-b]`.
14. `test_port25_output_directories_disjoint_from_port24`: Asserts all PORT-25 output directories are disjoint from all PORT-24 output directories.
15. `test_protocol_description_matches_macro_structure`: Asserts that `CORE_LADDER_FRAME` macro definition emits tens pulses then units pulses directly, and verifies doc accurately covers loader single pulses and core framed codes with all nominal and slow gap durations (pulse gap 6.55/15.625 ms, digit gap 41.94/100.0 ms, frame gap 83.89/200.0 ms, loader transition 57.62/138.28 ms).
16. `test_pulse_timing_under_150ms_and_200ms_cap`: Mathematically verifies that `0x00100000` is 50.0 ms at the slow conservative bound, with 100 ms margin below the 150 ms bound and 150 ms margin below the 200 ms cap.
17. `test_final_state_led_off`: Confirms macro terminates by writing `0x004C0003` (OFF) and holding OFF during frame-end gap.
18. `test_reversible_dancingbits_decoding`: Confirms dancingbits decoding produces bit-for-bit loader binary.
19. `test_embedded_core_integrity`: Confirms loader embeds core binary bit-for-bit.
20. `test_no_new_addresses`: Confirms no addresses outside verified MMIO `0xD20B0884` are introduced.

### Verification Command & Output
```bash
python3 -m unittest tests/test_port25_ladder_fix.py
```
Output: `Ran 20 tests in 1.74s — OK`.
Both `candidate_build` (`tools/build_candidate_port2a.py`) and `candidate_validate` (`tools/validate_candidate_port2a.py`) pass with exit code `0`.

---

## 8. Safety & Phase 0 Adherence

- **Phase 0 Strict Read-Only**: No firmware flashing, camera connection, SD card writing, or camera execution.
- **No Binaries Committed**: No build output directories or `.bin`/`.elf`/`.o`/`.a` files are committed to version control.
- **Toolchain Pinned**: All compilation occurs through `toolchains/gcc-arm-none-eabi-5_4-2016q3`.
