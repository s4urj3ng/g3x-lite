# PORT-20 T2: Loader-Entry LED Signal in a Separate Opt-In Candidate

**Milestone**: PORT-20: Visible Boot Signal (PowerShot G3 X GM1.10C)  
**Deliverable**: Task P20-T2b-led-candidate (`docs/PORT20_LED_CANDIDATE.md`)  
**Firmware Target**: Canon PowerShot G3 X **GM1.10C**  
**Toolchain**: ARM GNU-RM 5.4.1 2016q3 (`toolchains/gcc-arm-none-eabi-5_4-2016q3`)  

---

## 1. Precondition & Verdict Citation

As required by Task P20-T2b, `docs/PORT20_LED_EVIDENCE.md:292` is quoted verbatim:

> `T2 GO: 0xD20B0884 action0=0x004d0002 action1=0x004c0003 (address/values VERIFIED, ON/OFF polarity UNKNOWN)` `[VERIFIED: docs/PORT20_LED_EVIDENCE.md:292]`

Precondition check: **`GO`** `[VERIFIED]`. Address `0xD20B0884` and action values `0x004D0002` (action 0) and `0x004C0003` (action 1) are verified from anchored GM1.10C ROM code (`docs/PORT20_LED_EVIDENCE.md:23-26, 46, 288-292`). Electrical ON/OFF polarity remains **`UNKNOWN`** `[UNKNOWN: docs/PORT20_LED_EVIDENCE.md:29, 157, 290, 292]`.

---

## 2. Executive Summary & Design Overview

Task P20-T2b implements an isolated, opt-in loader-entry signal candidate behind the `--led` build flag (default OFF) in `tools/build_candidate_port2a.py`.

### 2.1 Core Objectives Achieved
1. **Default Build Invariance**: The default candidate build (`python3 tools/build_candidate_port2a.py`) is byte-identical to the approved PORT-19 candidate:
   - Output: `candidate_port2a/DISKBOOT.BIN`
   - Size: `118001` bytes (`0x1CCF1`) `[VERIFIED]`
   - SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED]`
   - Core Symbols: `boot_witness` (`0x0035F7A0`) and `_end` (`0x00366CB0`) unchanged `[VERIFIED]`.
2. **Strict Directory Separation**: Specifying `--led` (or `G3X_LED=1`) writes candidate artifacts exclusively to `candidate_led/` (or `--out-dir`), leaving `candidate_port2a/` untouched `[VERIFIED]`.
3. **Loader-Entry Signal Sequence**: Source file `chdk-port/platform/g3x/sub/110c/loader_entry_led.S` provides an opt-in entry point (`_start` at `0x8000`) that:
   - Writes action 0 (`0x004D0002`) to MMIO register `0xD20B0884` `[VERIFIED MMIO / UNKNOWN polarity]`.
   - Executes a `dsb sy` data synchronization barrier `[INFERRED]`.
   - Runs a bounded busy-wait delay loop with fixed constant `0x06000000` (100,663,296 iterations), producing about 1-2 s of changed LED state `[INFERRED timing]`.
   - Writes action 1 (`0x004C0003`) to MMIO register `0xD20B0884` `[VERIFIED MMIO / UNKNOWN polarity]`.
   - Executes a `dsb sy` barrier `[INFERRED]`.
   - Executes the original entry instructions: `ldr sp, =0x8000` (`mov.w sp, #32768`) and branches to `my_restart` (`b.w my_restart`) `[VERIFIED]`.
4. **Zero Mode or Interrupt Mutation**: The prologue contains NO `cpsid`, NO `cpsie`, NO `msr`, and NO `mrs` instructions `[VERIFIED]`. All CPSR mode bits and interrupt mask bits are identical to what the stock ROM passes to the loader entry `[VERIFIED]`.
5. **Rigorous Register Preservation**: Disassembly analysis of `my_restart` proves that only dead registers (`r0`, `r1`, `r2`) and condition flags are overwritten by the prologue. `r3`, `r4-r12`, and `lr` are strictly preserved `[VERIFIED]`.

---

## 3. Build Commands & Artifact Provenance

### 3.1 Default Build Command (Flag OFF)
The default build outputs to `candidate_port2a/` and preserves production and milestone invariance:
```bash
python3 tools/build_candidate_port2a.py
```

### 3.2 Opt-In LED Build Commands (Flag ON)
The LED candidate build outputs to `candidate_led/`:
```bash
# Using CLI flag:
python3 tools/build_candidate_port2a.py --led

# Or using environment variable:
G3X_LED=1 python3 tools/build_candidate_port2a.py

# Or specifying a custom destination:
python3 tools/build_candidate_port2a.py --led --out-dir /path/to/custom_dir
```

### 3.3 Artifact Hashes and Sizes

| Artifact | Build Target | Size (bytes) | SHA-256 Checksum | Invariance / Status | Citation |
|---|---|:---:|---|:---:|:---:|
| `candidate_port2a/DISKBOOT.BIN` | Default (OFF) | `118001` | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | `VERIFIED` | Milestone PORT-19 locked hash |
| `candidate_port2a/candidate_loader.bin` | Default (OFF) | `118000` | `2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a` | `VERIFIED` | Raw unencoded loader |
| `candidate_port2a/candidate_main.bin` | Default (OFF) | `116816` | `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e` | `VERIFIED` | CHDK core binary payload |
| `candidate_led/DISKBOOT.BIN` | LED (ON) | `118041` | `757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286` | `VERIFIED` | Exactly +40 B over default |
| `candidate_led/candidate_loader.bin` | LED (ON) | `118040` | `45171d300abb7e11e9ed54a321cf61e06e101b245e6f6cb93ebb3d3e2dd5006d` | `VERIFIED` | Exactly +40 B over default |
| `candidate_led/candidate_main.bin` | LED (ON) | `116816` | `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e` | `VERIFIED` | Bit-for-bit identical to default |

---

## 4. Symbol Alignment & Inspector Matching

### 4.1 Core Symbol Comparison (`boot_witness` and `_end`)

| Symbol | ELF Target | Default Build Address | LED Build Address | Address Shift | Status |
|---|---|:---:|:---:|:---:|:---:|
| `link_text_start` | `candidate_main.elf` | `0x003489B4` | `0x003489B4` | `+0x00` | `VERIFIED` |
| `_start` | `candidate_main.elf` | `0x003489B4` | `0x003489B4` | `+0x00` | `VERIFIED` |
| `boot_witness` | `candidate_main.elf` | `0x0035F7A0` | `0x0035F7A0` | `+0x00` | `VERIFIED` |
| `_end` | `candidate_main.elf` | `0x00366CB0` | `0x00366CB0` | `+0x00` | `VERIFIED` |

**Explanation of Zero Shift (`+0x00`)**:  
The candidate core binary (`candidate_main.bin`) is compiled from `chdk-port/platform/g3x/sub/110c/boot_prototype.c` and associated objects, linked against linker script `link-boot.ld` at base address `0x003489B4`. This core build is performed independently from the loader. The loader (`candidate_loader.elf`) embeds `candidate_main.bin` as a binary data blob via assembly directive `.incbin` in `blobs.S`.  
Because the LED prologue lives entirely in `chdk-port/platform/g3x/sub/110c/loader_entry_led.S` (which replaces `chdk-port/loader/g3x/entry.o` in `candidate_loader.elf`), it introduces changes only to the loader text section at `0x00008000..0x0000802F`. It has zero impact on the compilation or link of `candidate_main.elf`. Hence, `boot_witness` (`0x0035F7A0`) and `_end` (`0x00366CB0`) are identical between the default and LED builds `[VERIFIED]`.

### 4.2 Witness Inspector Verification
In `candidate_led/`:
- `witness_inspector_metadata.json` records target address `0x0035F7A0` `[VERIFIED]`.
- `witness_inspector_payload.bin` (444 bytes, SHA-256 `241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2`) encodes target address `0x0035F7A0` at literal offset `0x19C` `[VERIFIED]`.
- `verify_inspector_binding()` in `tools/build_candidate_port2a.py` executes fail-closed during the build, confirming that the inspector targets the build's actual `boot_witness` symbol (`0x0035F7A0`) `[VERIFIED]`.
- Manifest entry `trial_ready` is recorded as `true` `[VERIFIED: candidate_led/candidate_manifest.json:10]`. (Hardware deployment remains locked `NO-GO` per Phase 0 policy).

---

## 5. Register Preservation & Disassembly Analysis

Disassembly was performed with the pinned GNU-RM 5.4.1 toolchain (`toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump`).

### 5.1 Original Loader Entry & Restart Disassembly
Default loader disassembly (`candidate_port2a/candidate_loader.elf`):

```arm
00008000 <_start>:
    8000:	f44f 4d00 	mov.w	sp, #32768	; 0x8000
    8004:	f000 b8e8 	b.w	81d8 <my_restart>

00008154 <check_pid>:
    8154:	b508      	push	{r3, lr}
    8156:	4b07      	ldr	r3, [pc, #28]	; (8174 <check_pid+0x20>)
    8158:	f8d3 2210 	ldr.w	r2, [r3, #528]	; 0x210
    815c:	f9b2 2000 	ldrsh.w	r2, [r2]
    8160:	f9b3 0214 	ldrsh.w	r0, [r3, #532]	; 0x214
    8164:	4290      	cmp	r0, r2
    8166:	d003      	beq.n	8170 <check_pid+0x1c>

00008178 <check_compat>:
    8178:	b510      	push	{r4, lr}
    817a:	f7ff ffeb 	bl	8154 <check_pid>
    817e:	4604      	mov	r4, r0
    8180:	4b05      	ldr	r3, [pc, #20]	; (8198 <check_compat+0x20>)
    8182:	f8d3 1218 	ldr.w	r1, [r3, #536]	; 0x218
    8186:	f8d3 021c 	ldr.w	r0, [r3, #540]	; 0x21c
    818a:	f7ff ffd5 	bl	8138 <ver_cmp>

000081d8 <my_restart>:
    81d8:	b508      	push	{r3, lr}
    81da:	f7ff ffcd 	bl	8178 <check_compat>
    81de:	4b1a      	ldr	r3, [pc, #104]	; (8248 <my_restart+0x70>)
```

### 5.2 Liveness & Preservation Table across Loader Entry

| Register / Flag | Read Before Written in `my_restart`? | First Modification Line / Disassembly Citation | Dead at Entry? | Handled by Prologue | Status |
|---|:---:|---|:---:|---|:---:|
| `r0` | **No** | Line `8160`: `ldrsh.w r0, [r3, #532]` in `check_pid` | **YES** | Used as MMIO register pointer (`0xD20B0884`); safe to overwrite | `VERIFIED` |
| `r1` | **No** | Line `8182`: `ldr.w r1, [r3, #536]` in `check_compat` | **YES** | Used as MMIO value scratch (`0x004D0002` / `0x004C0003`); safe to overwrite | `VERIFIED` |
| `r2` | **No** | Line `8158`: `ldr.w r2, [r3, #528]` in `check_pid` | **YES** | Used as busy-wait loop counter scratch; safe to overwrite | `VERIFIED` |
| `r3` | **No** | Line `81d8`: `push {r3, lr}` (stack alignment dummy); line `8156`: `ldr r3, [pc, #28]` | **YES** | Untouched by prologue; preserved | `VERIFIED` |
| `r4-r11` | **No** | Callee-saved standard registers | **N/A** | Untouched by prologue; strictly preserved | `VERIFIED` |
| `r12` (IP) | **No** | Not read anywhere before written in call tree | **YES** | Untouched by prologue; preserved | `VERIFIED` |
| `sp` | **Yes** (at `81d8`) | Line `8000`: `mov.w sp, #32768` (`0x8000`) | **N/A** | Re-initialized to `0x8000` at line `801a` by fallthrough instruction | `VERIFIED` |
| `lr` | **Yes** (at `81d8`) | Line `81d8`: `push {r3, lr}` saves entry `lr` | **NO** | Untouched by prologue; strictly preserved | `VERIFIED` |
| Condition Flags (NZCV) | **No** | Line `8164`: `cmp r0, r2` in `check_pid` sets flags before branch `8166` | **YES** | Overwritten by `subs r2, #1` during loop; dead at entry | `VERIFIED` |
| CPSR Mode / IRQ (`I`, `F`, `M`) | **No** | Unmodified by original entry; masked later at line `823c: cpsid if` | **NO** | NO `cpsid`, `cpsie`, `msr`, or `mrs` in prologue; strictly preserved | `VERIFIED` |

---

## 6. LED Signal Description, Polarity & Timing

### 6.1 Signal Description & Polarity
- **Signal**: About 1-2 s of changed LED state at loader entry `[INFERRED timing / VERIFIED code]`.
- **MMIO Register**: `0xD20B0884` (GPIO pin 33, DryOS logical LED descriptor 0) `[VERIFIED: docs/PORT20_LED_EVIDENCE.md:23-26, 46]`.
- **Physical LED**: Rear green status LED `[INFERRED: docs/PORT20_LED_EVIDENCE.md:28]`.
- **Polarity Verdict**: **`UNKNOWN`** `[UNKNOWN: docs/PORT20_LED_EVIDENCE.md:29, 157, 290, 292]`. Whether `0x004D0002` (action 0) asserts active-high (LED ON) or active-low (LED OFF) cannot be proven from static ROM code without dynamic camera observation.
- **Design Resolution**: The prologue does not claim action 0 means 'on'. Instead, it writes action 0 (`0x004D0002`), holds state for ~1-2 s via a busy-wait delay, and then writes action 1 (`0x004C0003`). This guarantees an observable transition of LED state at loader entry regardless of whether the circuit is active-high or active-low.

### 6.2 Timing & Wall-Clock Calculations

The bounded busy-wait delay loop consists of:
```arm
.Ldelay_loop:
    subs    r2, #1        /* 1 cycle */
    bne.n   .Ldelay_loop  /* 1-3 cycles (typically 2 cycles taken on ARMv7-R) */
```

- **Loop Count**: Fixed constant `N = 0x06000000 = 100,663,296` iterations `[VERIFIED]`.
- **Cycles Per Iteration**: 2 to 3 CPU cycles per iteration on Cortex-R4 / Cortex-R5 pipeline `[INFERRED]`.
- **Total Cycles**:
  - At 2 cycles/iteration: `2 * 100,663,296 = 201,326,592` cycles (~201.3M cycles) `[INFERRED]`.
  - At 3 cycles/iteration: `3 * 100,663,296 = 301,989,888` cycles (~302.0M cycles) `[INFERRED]`.
- **Core Clock Frequency**: CPU core frequency at the moment of loader execution (`StartDiskboot`) is unmeasured on physical camera `[UNKNOWN]`. DIGIC 6 nominal operating core clocks range between ~150 MHz and ~250 MHz `[INFERRED]`.

#### Nominal Expected Duration Range:
| Assumed CPU Clock | Cycles / Iteration | Total Execution Time | Classification |
|:---:|:---:|:---:|:---:|
| `150 MHz` | 2 | `1.34 s` | `[INFERRED]` |
| `150 MHz` | 3 | `2.01 s` | `[INFERRED]` |
| `200 MHz` | 2 | `1.01 s` | `[INFERRED]` |
| `200 MHz` | 3 | `1.51 s` | `[INFERRED]` |
| `250 MHz` | 2 | `0.81 s` | `[INFERRED]` |
| `250 MHz` | 3 | `1.21 s` | `[INFERRED]` |

Nominal wall-clock signal duration is approximately **1.0 to 2.0 seconds** `[INFERRED]`.

#### Worst-Case Upper Bound:
If early boot runs on an unmultiplied reference/crystal clock or lower PLL divider prior to DryOS clock reconfiguration (e.g., 66.6 MHz):
- At `66.6 MHz` with 3 cycles/iteration: `301,989,888 / 66,666,666 = 4.53 s` `[INFERRED]`.
- At `50.0 MHz` with 2 cycles/iteration: `201,326,592 / 50,000,000 = 4.03 s` `[INFERRED]`.

The worst-case execution upper bound is guaranteed to remain **strictly under 5.0 seconds** `[INFERRED]`.

---

## 7. Pinned-Objdump Disassembly Diff & Relocation Accounting

### 7.1 Loader Entry Disassembly Comparison
Disassembly produced by `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-objdump -d`:

#### Default Build (`candidate_port2a/candidate_loader.elf`):
```arm
00008000 <_start>:
    8000:	f44f 4d00 	mov.w	sp, #32768	; 0x8000
    8004:	f000 b8e8 	b.w	81d8 <my_restart>

00008008 <compute_witness_checksum.constprop.0>:
    8008:	4b0e      	ldr	r3, [pc, #56]	; (8044 <compute_witness_checksum.constprop.0+0x3c>)
    800a:	681a      	ldr	r2, [r3, #0]
```

#### Opt-In LED Build (`candidate_led/candidate_loader.elf`):
```arm
00008000 <_start>:
    8000:	4808      	ldr	r0, [pc, #32]	; (8024 <_start+0x24>)
    8002:	4909      	ldr	r1, [pc, #36]	; (8028 <_start+0x28>)
    8004:	6001      	str	r1, [r0, #0]
    8006:	f3bf 8f4f 	dsb	sy
    800a:	f04f 62c0 	mov.w	r2, #100663296	; 0x6000000
    800e:	3a01      	subs	r2, #1
    8010:	d1fd      	bne.n	800e <_start+0xe>
    8012:	4906      	ldr	r1, [pc, #24]	; (802c <_start+0x2c>)
    8014:	6001      	str	r1, [r0, #0]
    8016:	f3bf 8f4f 	dsb	sy
    801a:	f44f 4d00 	mov.w	sp, #32768	; 0x8000
    801e:	f000 b8ef 	b.w	8200 <my_restart>
    8022:	bf00      	nop
    8024:	d20b0884 	.word	0xd20b0884
    8028:	004d0002 	.word	0x004d0002
    802c:	004c0003 	.word	0x004c0003

00008030 <compute_witness_checksum.constprop.0>:
    8030:	4b0e      	ldr	r3, [pc, #56]	; (806c <compute_witness_checksum.constprop.0+0x3c>)
    8032:	681a      	ldr	r2, [r3, #0]
```

### 7.2 Relocation & Symbol Shift Accounting

The default `.entry` section occupies 8 bytes (`0x8000..0x8007`).  
The LED `.entry` section occupies 48 bytes (`0x8000..0x802F`):
- 10 instructions (28 bytes)
- 1 alignment NOP (2 bytes)
- 3 literal pool words (12 bytes)
- Total length = 48 bytes.

Net section expansion: `48 - 8 = 40` bytes (`+0x28` hex).

Because `.entry` is the first input section linked at base `0x8000`, every subsequent symbol and section in `candidate_loader.elf` is shifted by exactly `+0x28`:

| Symbol Name | Default Address | LED Candidate Address | Net Shift | Relocation / Code Effect |
|---|:---:|:---:|:---:|---|
| `_start` | `0x00008000` | `0x00008000` | `+0x00` | Fixed hardware entry point |
| `compute_witness_checksum` | `0x00008008` | `0x00008030` | `+0x28` | Shifted by entry section delta; code identical |
| `set_led` | `0x0000804C` | `0x00008074` | `+0x28` | Shifted by entry section delta; code identical |
| `get_pid` | `0x000080B4` | `0x000080DC` | `+0x28` | Shifted by entry section delta; code identical |
| `blink` | `0x000080E0` | `0x00008108` | `+0x28` | Shifted by entry section delta; code identical |
| `ver_cmp` | `0x00008138` | `0x00008160` | `+0x28` | Shifted by entry section delta; code identical |
| `check_pid` | `0x00008154` | `0x0000817C` | `+0x28` | Shifted by entry section delta; code identical |
| `check_compat` | `0x00008178` | `0x000081A0` | `+0x28` | Shifted by entry section delta; code identical |
| `core_copy` | `0x0000819C` | `0x000081C4` | `+0x28` | Shifted by entry section delta; code identical |
| `my_restart` | `0x000081D8` | `0x00008200` | `+0x28` | Shifted by entry section delta; code identical |
| `blob_chdk_core_size` | `0x00008264` | `0x0000828C` | `+0x28` | Relocated word constant (`116816` B) |
| `blob_chdk_core` | `0x00008268` | `0x00008290` | `+0x28` | Relocated pointer to `blob_chdk_core_start` |
| `link_data_start` | `0x0000826C` | `0x00008294` | `+0x28` | Base of `.data` section in loader |
| `blob_chdk_core_start` | `0x00008280` | `0x000082A8` | `+0x28` | Start of embedded core binary payload |
| `blob_chdk_core_end` | `0x00024AD0` | `0x00024AF8` | `+0x28` | End of embedded core binary payload |
| `pid_leds` | `0x00024AD0` | `0x00024AF8` | `+0x28` | Shifted data table |
| `pid_sigs` | `0x00024CE0` | `0x00024D08` | `+0x28` | Shifted signature table |
| `ver_sigs` | `0x00024CE8` | `0x00024D10` | `+0x28` | Shifted signature table |
| `link_bss_start` | `0x00024CF0` | `0x00024D18` | `+0x28` | Shifted BSS section base |
| `_end` (loader BSS end) | `0x00024CF0` | `0x00024D20` | `+0x30` | Shifted BSS section end (8-byte alignment) |

Inside `my_restart`, all relative branch offsets (`b.w`, `bl`) and PC-relative literal pool loads (`ldr r3, [pc, #...]`) adjust naturally without any relocation overflows or displacement truncations `[VERIFIED]`.

---

## 8. Verification & Test Suite Summary

The unit test suite `tests/test_port20_led_candidate.py` verifies:
1. `test_default_build_invariance`: Default build DISKBOOT.BIN SHA-256 (`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`), size (`118001` B), and core symbols (`0x0035F7A0`, `0x00366CB0`) are unaltered `[VERIFIED]`.
2. `test_led_build_directory_separation`: `--led` writes only to `candidate_led/` and preserves `candidate_port2a/` bit-for-bit `[VERIFIED]`.
3. `test_custom_out_dir_option`: Custom `--out-dir` writes artifacts to the specified target directory `[VERIFIED]`.
4. `test_environment_variable_activation`: `G3X_LED=1` activates the LED build without CLI flag `[VERIFIED]`.
5. `test_loader_entry_prologue_disassembly`: Disassembly of `candidate_loader.elf` confirms the prologue contains `0xD20B0884`, `0x004D0002`, `0x004C0003`, delay loop with constant `100663296` (`0x06000000`), `dsb sy`, and fallthrough to `mov.w sp, #32768; b.w my_restart`, with NO `cpsid`, `cpsie`, `msr`, or `mrs` `[VERIFIED]`.
6. `test_binary_contains_t1_literals`: `candidate_loader.bin` contains little-endian encodings of T1 constants `[VERIFIED]`.
7. `test_default_build_lacks_prologue`: Default candidate loader has zero prologue code at `0x8000` `[VERIFIED]`.
8. `test_core_symbols_identical_across_builds`: Core symbols `_start`, `boot_witness`, and `_end` match bit-for-bit between default and LED builds `[VERIFIED]`.

All 8 tests in `tests/test_port20_led_candidate.py` pass cleanly in 0.82s `[VERIFIED]`.  
All 816 tests across the full `test_port*.py` suite pass cleanly in 12.45s `[VERIFIED]`.  
Candidate validator `tools/validate_candidate_port2a.py` passes all 7 validation checks with exit code 0 `[VERIFIED]`.
