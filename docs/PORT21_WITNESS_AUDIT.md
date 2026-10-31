# PORT-21 Witness Audit: Writer vs Inspector Roundtrip Verification (Hypothesis H4)

## 1. Executive Summary & Evaluation of Hypothesis H4

### 1.1 Objective & Context
During the physical camera execution trial for CHDK-PORT-2A (PowerShot G3 X GM1.10C), observation **O6** was recorded: the Canon Basic Witness Inspector reported `WITNESS_INVALID` on Line 1 (`h_title`) and `INVALID / CORRUPT` on Line 2 (`h_status`), returning sentinel `0x574954EE` (`docs/PORT18_OWNER_TRIAL_PLAN.md:267, 288`).

Hypothesis **H4** posits:
> *"The LOADER witness record at 0x0035F7A0 was malformed, given the code exactly as built."*

This audit conducts a host-based, field-by-field verification comparing the witness writer routines in the loader (`chdk-port/loader/g3x/main_prototype.c:42-56`) and core (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:26-56`) against the witness inspector parser executed by the owner (`firmware/tools/witness_inspector_gm110c.m`, `firmware/tools/witness_inspector_payload.S`, and host reference `tools/validate_witness_inspector.py`).

### 1.2 Epistemic Scope and Status of Hypothesis H4
- **Loader Code as Built is Valid (`[VERIFIED]`)**:
  A host C probe compiling the real boot witness header (`chdk-port/platform/g3x/sub/110c/boot_witness.h`) and replicating field-by-field the loader's assignments (`main_prototype.c:42-56`) generates a 32-byte record with `magic=0x5749544E`, `version=0x00010001`, `session_nonce=0x32A80001`, `stage_state=0x01`, `loader_sp=0x00007FF8`, `core_entry_pc=0`, `cont_tick=0`, and `checksum=0x3028882D`.
  When parsed by the real inspector code (`vwi.emulate_inspector_parse`), this exact loader-only record produces:
  - Title: `LOADER_REACHED`
  - Status: `FRESHNESS_UNVERIFIED`
  - Color indices: Title Color 1 (White), Status Color 4 (Yellow)
  - Return Sentinel: `0x57495401` (`SENTINEL_LOADER`)
  - **Verdict: VALID (`[VERIFIED]`)**.
  The loader-only record as designed and built is **never** reported as `WITNESS_INVALID` / `INVALID / CORRUPT` `[VERIFIED]`.
- **Writer/Parser Compatibility (`[VERIFIED]`)**:
  Struct layout, member offsets, 32-byte size, little-endian byte ordering, and polynomial checksum coverage match bit-for-bit between the loader writer and the inspector parser `[VERIFIED]`.
- **Actual Hardware State during Trial O6 (`[UNKNOWN]`)**:
  - The actual physical RAM contents at `0x0035F7A0` when the inspector executed during the O6 session are **`UNKNOWN`** (no raw memory dump was captured) `[UNKNOWN]`.
  - Whether the loader witness writer routine ever executed on the physical camera during the trial is **`UNKNOWN`** `[UNKNOWN]`.
- **Hypotheses H1–H4 Cannot Be Ruled Out by O6 Alone (`[VERIFIED]`)**:
  The inspector returns `WITNESS_INVALID / INVALID / CORRUPT` (`0x574954EE`) for multiple distinct raw memory state classes (including uninitialized all-zeros, stock OS heap overwrites, partial/aborted writes, and checksum/bit-level corruption). Because multiple physical failure mechanisms produce the exact same visual and sentinel output, **observation O6 alone does not rule out any of H1–H4** `[VERIFIED]`.

---

## 2. Artifact Identification & Code Flow

### 2.1 The Witness Writers
1. **Loader Writer**:
   - Source: `chdk-port/loader/g3x/main_prototype.c:42-56` `[VERIFIED]`.
   - Invocation: `my_restart()` in `candidate_loader.elf`, executed immediately after `core_copy()` and prior to cache synchronization and the branch to `0x003489B5` `[VERIFIED]`.
   - Target Address: Linker-resolved `BOOT_WITNESS_ADDR` (`0x0035F7A0`), passed via `-DBOOT_WITNESS_ADDR=0x0035f7a0` in `tools/build_candidate_port2a.py:506` `[VERIFIED]`.
   - Stack Pointer Provenance:
     - `chdk-port/loader/g3x/entry.S:7`: `LDR SP, =MEMBASEADDR` initializes SP to `0x00008000` `[VERIFIED]`.
     - `candidate_manifest.json:16`: `loader_entry` is pinned at `0x00008000` `[VERIFIED]`.
     - `candidate_loader.elf` disassembly at `0x000081D8` (`my_restart` entry): prologue instruction `push {r3, lr}` consumes 2 32-bit registers (8 bytes) on the stack `[VERIFIED]`.
     - At line 51-52 of `main_prototype.c`, `register uint32_t current_sp asm("sp"); w->loader_sp = current_sp;` evaluates SP as `0x00008000 - 0x08 = 0x00007FF8` `[VERIFIED]`.
2. **Core Writer**:
   - Source: `chdk-port/platform/g3x/sub/110c/boot_prototype.c:26-56` `[VERIFIED]`.
   - Structure Instance: `volatile boot_witness_t boot_witness __attribute__((aligned(16), section(".data")))` placed at `0x0035F7A0` in `candidate_port2a/candidate_main.elf` `[VERIFIED]`.
   - Transitions:
     - `witness_record_core()` (`boot_prototype.c:32-43`): Transitions `stage_state` from `0x01` (`STAGE_LOADER`) to `0x03` (`STAGE_LOADER | STAGE_CORE`), sets `core_entry_pc = 0x003489B5`, and updates the polynomial checksum `[VERIFIED]`.
     - `witness_record_continuation()` (`boot_prototype.c:45-56`): Transitions `stage_state` from `0x03` to `0x07` (`STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION`), sets `cont_tick = 0x0014F200`, and updates the polynomial checksum `[VERIFIED]`.

### 2.2 The Witness Inspector
1. **Canon Basic Script**:
   - Source: `firmware/tools/witness_inspector_gm110c.m` (packaged into `candidate_port2a/witness_inspector_gm110c.m` by `tools/build_candidate_port2a.py:792-860`) `[VERIFIED]`.
   - Allocates 448 bytes, reads `A/WITNESS.BIN` (444 bytes payload), flushes L1 Harvard caches (`0xFC127A85`, `0xFC127B2B`), and calls `buf + 1` (Thumb-2 vector) via `ExecuteEventProcedure("exec", ...)` passing `h_title`, `h_status`, and `expected_nonce = 0` (`lines 127-136`) `[VERIFIED]`.
2. **Native Assembly Payload**:
   - Source: `firmware/tools/witness_inspector_payload.S:1-265` (assembled into `candidate_port2a/witness_inspector_payload.bin`) `[VERIFIED]`.
   - Target Address: Hardcoded at compile time via `movw r7, #:lower16:BOOT_WITNESS_ADDR` and `movt r7, #:upper16:BOOT_WITNESS_ADDR` (`0x0035F7A0`) `[VERIFIED]`.
   - Reads 8 32-bit words from `0x0035F7A0`, verifies magic, version, checksum, and stage mask, and updates LCDMsg text and colors `[VERIFIED]`.
3. **Reference Host Validator & Emulation**:
   - Source: `tools/validate_witness_inspector.py:85-106, 242-274` (`emulate_inspector_parse`) and `tools/validate_boot_witness.py:45-138` (`inspect_witness`) `[VERIFIED]`.

---

## 3. Field-by-Field Writer vs Inspector Parser Comparison

| Field | Byte Offset | Loader Writer (`main_prototype.c`) | Core Writer (`boot_prototype.c`) | Inspector Parser (`payload.S` & `vwi.py`) | Status | Citation |
|---|---|---|---|---|---|---|
| **`magic`** | `0x00` (Word 0) | Writes `BOOT_WITNESS_MAGIC` (`0x5749544E`, `"WITN"`) | Checked unchanged at transitions (`lines 34, 47`) | `ldr r0, [r7, #0]`; compares to `0x5749544E`; branches to `.Lstate_invalid` if mismatch | **MATCH (`[VERIFIED]`)** | `main_prototype.c:43`; `boot_witness.h:8`; `payload.S:61-65`; `vwi.py:85, 250` |
| **`version`** | `0x04` (Word 1) | Writes `BOOT_WITNESS_VERSION` (`0x00010001`, v1.1) | Checked unchanged at transitions (`lines 35, 48`) | `ldr r0, [r7, #4]`; compares to `0x00010001`; branches to `.Lstate_invalid` if mismatch | **MATCH (`[VERIFIED]`)** | `main_prototype.c:44`; `boot_witness.h:9`; `payload.S:67-71`; `vwi.py:86, 250` |
| **`session_nonce`** | `0x08` (Word 2) | Writes `0x32A80001` (GM1.10C challenge nonce) | Unchanged across core transitions | Passed `expected_nonce = 0` by script; if `expected_nonce == 0` or `0x32A80001`, skips challenge check | **MATCH (`[VERIFIED]`)** | `main_prototype.c:48`; `inspector_gm110c.m:28`; `payload.S:101-108`; `vwi.py:259` |
| **`stage_state`** | `0x0C` (Word 3) | Writes `STAGE_LOADER` (`0x01`) | Core writes `0x03` (`STAGE_LOADER \| STAGE_CORE`); Continuation writes `0x07` (`0x01 \| 0x02 \| 0x04`) | Evaluates `stage_state`: `1 -> .Lstate_loader`, `3 -> .Lstate_core`, `7 -> .Lstate_continuation`, else `.Lstate_invalid` | **MATCH (`[VERIFIED]`)** | `main_prototype.c:50`; `boot_prototype.c:39, 52`; `payload.S:117-129`; `vwi.py:264-273` |
| **`loader_sp`** | `0x10` (Word 4) | Writes current `sp` (`asm("sp")`), initial stack at `0x00007FF8` | Unchanged by core | Not checked at Stage 1 or 2; at Stage 3, requires 8-byte alignment (`loader_sp % 8 == 0`) | **MATCH (`[VERIFIED]`)** | `main_prototype.c:51-52`; `entry.S:7`; `payload.S:161-163`; `vwi.py:269` |
| **`core_entry_pc`** | `0x14` (Word 5) | Writes `0` | Core writes `0x003489B5` (Thumb bit set for `MEMISOSTART`) | Not checked at Stage 1 or 2; at Stage 3, requires exact match `core_entry_pc == 0x003489B5` | **MATCH (`[VERIFIED]`)** | `main_prototype.c:53`; `boot_prototype.c:40`; `payload.S:154-159`; `vwi.py:269` |
| **`cont_tick`** | `0x18` (Word 6) | Writes `0` | Continuation writes `0x0014F200` | Checked only as part of polynomial checksum computation | **MATCH (`[VERIFIED]`)** | `main_prototype.c:54`; `boot_prototype.c:53`; `boot_witness.h:41`; `payload.S:80-87` |
| **`checksum`** | `0x1C` (Word 7) | `compute_witness_checksum()` over first 7 words | Recomputed at each core transition | Loops 7 words (offsets `0x00..0x18`), accumulates `c = (c * 31) ^ w`, compares with offset `0x1C` | **MATCH (`[VERIFIED]`)** | `boot_witness.h:33-43`; `payload.S:75-92`; `vwi.py:96-100, 254-256` |
| **Record Size** | N/A | `sizeof(boot_witness_t) == 32` (8 x 4B words) | 32 bytes (`aligned(16)`) | Reads 8 32-bit words (32 bytes) at `BOOT_WITNESS_ADDR` (`payload.S:57-90`); reference emulator unpacks 32 bytes (`<IIIIIIII`) with host-API `len(buf) >= 32` check (`vwi.py:244-247`) | **MATCH (`[VERIFIED]`)** | `boot_witness.h:30`; `payload.S:57-90`; `vwi.py:244-247` |
| **Alignment** | N/A | Placed at `0x0035F7A0` (16-byte aligned) | `boot_witness` in `.data` at `0x0035F7A0` | `BOOT_WITNESS_ADDR = 0x0035F7A0` (16-byte aligned) | **MATCH (`[VERIFIED]`)** | `build_candidate_port2a.py:54, 506`; `validate_candidate_port2a.py:48` |
| **Endianness** | N/A | ARMv7-R Cortex-R4 Little-Endian | ARMv7-R Cortex-R4 Little-Endian | Little-Endian struct read / unpack (`<IIIIIIII`) | **MATCH (`[VERIFIED]`)** | `entry.S`; `main_prototype.c`; `payload.S:39-41`; `vwi.py:247` |

### 3.1 Checksum Algorithm and Coverage Verification
- **Formula**:
  $$\text{checksum} = c_7, \quad \text{where } c_0 = \text{0x55AA55AA}, \quad c_{k+1} = (c_k \times 31) \oplus w_k \quad (k \in 0..6)$$
- **Coverage**: Exactly the 7 32-bit words: `magic`, `version`, `session_nonce`, `stage_state`, `loader_sp`, `core_entry_pc`, and `cont_tick` `[VERIFIED]`.
- **Loader Compilation**: In `candidate_port2a/candidate_loader.elf`, GCC optimizes `c_0 * 31` to literal `0x5FA05F96`, evaluating `(((0x5FA05F96 ^ magic) * 31) ^ version) * 31 ... ^ cont_tick`. Disassembly of `candidate_loader.elf:8008-8040` matches the loop in `firmware/tools/witness_inspector_payload.S:75-87` bit-for-bit `[VERIFIED]`.
- For the loader-only record with `loader_sp = 0x00007FF8`, the exact checksum is **`0x3028882D`** `[VERIFIED]`.
- **Writer / Parser Mismatch**: **None**. There is zero structural, sizing, offset, or algorithmic mismatch between the writer and parser `[VERIFIED]`.

---

## 4. Failure Mapping to `WITNESS_INVALID` / `INVALID / CORRUPT`

In `firmware/tools/witness_inspector_payload.S:190-198` and `tools/validate_witness_inspector.py:244-273`, any structural violation routes unconditionally to the failure terminal `.Lstate_invalid`:

```text
.Lstate_invalid:
    Title String:     "WITNESS_INVALID"
    Status String:    "INVALID / CORRUPT"
    Title Color:      3
    Status Color:     3
    Return Sentinel:  0x574954EE (SENTINEL_INVALID)
```

### 4.1 Native Payload vs Reference Emulator Behavior
- **Native Assembly Inspector (`firmware/tools/witness_inspector_payload.S:57-90`)**:
  The native assembly inspector executes directly on ARM hardware in the camera's execution context. It does **not** receive a buffer pointer or buffer length argument. Instead, it hardcodes `BOOT_WITNESS_ADDR` (`0x0035F7A0`) into register `r7` via `movw`/`movt` (`payload.S:57-58`) and performs direct 32-bit memory loads (`ldr r0, [r7, #offset]`) across the 8 consecutive 32-bit words (32 bytes). Physical memory at `0x0035F7A0` is always present and addressable; the native inspector has no concept of buffer length, cannot detect truncation, and never returns `INVALID` due to buffer length `[VERIFIED: firmware/tools/witness_inspector_payload.S:57-90]`.
- **Python Reference Emulator (`tools/validate_witness_inspector.py:244-245`)**:
  The host Python reference emulator takes an arbitrary Python byte sequence `buf` and executes `if len(buf) < 32: return SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3`. This check is strictly a **host-API safety guard** to prevent `struct.unpack` indexing exceptions on short buffers during host test execution. It is **not** a native-parser outcome or a physical on-camera memory state `[VERIFIED: tools/validate_witness_inspector.py:244-245]`.

### 4.2 Failure Conditions Reaching `.Lstate_invalid`
On-camera physical memory states route to `.Lstate_invalid` (`0x574954EE`) based on the structural checks implemented in `firmware/tools/witness_inspector_payload.S:61-163` and replicated in `tools/validate_witness_inspector.py:250-273`. Both the native payload and the reference emulator evaluate these physical memory states identically:
1. **Corrupted Magic**: `magic != 0x5749544E` (e.g. all-zeros `0x00000000`, stock pointers, uninitialized RAM) `[VERIFIED: payload.S:61-65; vwi.py:250]`.
2. **Unsupported Version**: `version != 0x00010001` `[VERIFIED: payload.S:67-71; vwi.py:250]`.
3. **Checksum Mismatch**: Any single bit flip or modification in any field without recalculating `checksum` `[VERIFIED: payload.S:78-92; vwi.py:254-256]`.
4. **Illegal Stage Mask**: `stage_state` not in `{1, 3, 7}` (e.g. `0x00` empty, `0x02` core-only, `0x04` continuation-only, `0x05` core-skipped) `[VERIFIED: payload.S:117-129; vwi.py:264-273]`.
5. **Continuation Core Entry Mismatch**: At Stage 3 (`stage_state == 7`), `core_entry_pc != 0x003489B5` `[VERIFIED: payload.S:154-159; vwi.py:269-270]`.
6. **Continuation Stack Misalignment**: At Stage 3 (`stage_state == 7`), `loader_sp % 8 != 0` `[VERIFIED: payload.S:161-163; vwi.py:269-270]`.

*(Host-API only)*: In the host reference emulator only, `len(buf) < 32` returns `SENTINEL_INVALID` (`vwi.py:244-245`), but this cannot occur on hardware (`payload.S:57-90`).

---

## 5. Raw Memory State Classes and Consistency with Hypotheses H1–H4

The owner observed trial result O6:
`Present: WITNESS_INVALID / INVALID / CORRUPT (Red/Red)`, Sentinel `0x574954EE` `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:267]`.

### 5.1 Tested Input-to-Status Classifications (`[VERIFIED]`)
The real inspector parsing code (`vwi.emulate_inspector_parse`) produces the following deterministic classifications:

| Memory Input at `0x0035F7A0` | Description | Inspector Output String 1 (`h_title`) | Inspector Output String 2 (`h_status`) | Color Indices (`tc, sc`) | Return Sentinel | Matches O6 Reading? |
|---|---|---|---|---|---|---|
| **Loader-only record** | Exact bytes written by `main_prototype.c:42-56` | `LOADER_REACHED` | `FRESHNESS_UNVERIFIED` | `1, 4` (White/Yellow) | `0x57495401` | **NO (`[VERIFIED]`)** |
| **All-zero DRAM** | `bytes(32)` (power-on uninitialized or cleared DRAM) | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Stock-boot DRAM overwrite** | Canon OS heap, stack, or MMU descriptors at `0x0035F7A0` | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Garbage / Uninitialized RAM** | Non-zero uninitialized pattern (e.g. `0xFF*32`, `0xAA*32`) | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Partial / Aborted Write** | Magic written, but version/state/checksum uninitialized | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Corrupted Checksum / Bit Flips** | Valid record with single bit flipped in data or checksum | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Illegal Stage Mask** | `stage_state` not in `{1, 3, 7}` (e.g. `0x00`, `0x02`, `0x05`) | `WITNESS_INVALID` | `INVALID / CORRUPT` | `3, 3` | `0x574954EE` | **YES (`[VERIFIED]`)** |
| **Core-reached record** | Valid Stage 2 record (`stage_state = 0x03`) | `CORE_REACHED` | `FRESHNESS_UNVERIFIED` | `1, 4` (White/Yellow) | `0x57495402` | **NO (`[VERIFIED]`)** |
| **Continuation-attempted** | Valid Stage 3 record (`stage_state = 0x07`) | `CONT_ATTEMPTED` | `FRESHNESS_UNVERIFIED` | `4, 4` (Yellow/Yellow) | `0x57495404` | **NO (`[VERIFIED]`)** |

### 5.2 Exhaustive Raw Memory State Classes Yielding Exactly `WITNESS_INVALID / INVALID / CORRUPT`
Every memory state on the physical camera that produces `0x574954EE` falls into one of the following 8 distinct physical classes. For each class, both the native payload and the reference emulator evaluate to `WITNESS_INVALID / INVALID / CORRUPT`:

1. **Class 1: Power-on uninitialized or cleared DRAM (all zeros `0x00*32`)**:
   - Failure point: Word 0 (`magic = 0x00000000`) fails magic check `0x5749544E`.
   - Parser evaluation: **Both** native payload (`firmware/tools/witness_inspector_payload.S:61-65`) and reference emulator (`tools/validate_witness_inspector.py:250-251`) reach `SENTINEL_INVALID` `[VERIFIED]`.
2. **Class 2: Stock Canon OS heap / task data overwrite**:
   - Failure point: Word 0 is a stock ROM/RAM pointer or DryOS data structure (failing magic `0x5749544E`), or subsequent words fail version (`0x00010001`) or polynomial checksum.
   - Parser evaluation: **Both** native payload (`payload.S:61-65, 67-71, 89-92`) and reference emulator (`vwi.py:250, 256`) reach `SENTINEL_INVALID` `[VERIFIED]`.
3. **Class 3: Uniform or floating DRAM patterns (`0xFF*32`, `0xAA*32`, random noise)**:
   - Failure point: Word 0 does not match `0x5749544E`.
   - Parser evaluation: **Both** native payload (`payload.S:61-65`) and reference emulator (`vwi.py:250`) reach `SENTINEL_INVALID` `[VERIFIED]`.
4. **Class 4: Partial or aborted witness writes**:
   - Failure point: The loader began executing `my_restart()`, but an exception, watchdog reset, or interrupt intervened before all 8 words and checksum were committed to DRAM; fails magic, version, or checksum.
   - Parser evaluation: **Both** native payload (`payload.S:61-92`) and reference emulator (`vwi.py:250-256`) reach `SENTINEL_INVALID` `[VERIFIED]`.
5. **Class 5: Checksum corruption / single-bit errors**:
   - Failure point: All 8 fields were populated, but memory decay, background DMA collision, or cache flush failure corrupted one or more bits before the inspector read DRAM.
   - Parser evaluation: **Both** native payload (`payload.S:89-92`) and reference emulator (`vwi.py:254-256`) reach `SENTINEL_INVALID` `[VERIFIED]`.
6. **Class 6: Invalid / illegal stage bitmask**:
   - Failure point: Word 3 contains an unsupported stage value (`0x00`, `0x02`, `0x04`, `0x05`, `0x06`, etc.).
   - Parser evaluation: **Both** native payload (`payload.S:117-129`) and reference emulator (`vwi.py:264-273`) reach `SENTINEL_INVALID` `[VERIFIED]`.
7. **Class 7: Incompatible version field**:
   - Failure point: Word 1 contains a version other than `0x00010001`.
   - Parser evaluation: **Both** native payload (`payload.S:67-71`) and reference emulator (`vwi.py:250`) reach `SENTINEL_INVALID` `[VERIFIED]`.
8. **Class 8: Stage 3 validation failure**:
   - Failure point: Word 3 indicates Stage 3 (`0x07`), but `core_entry_pc != 0x003489B5` or `loader_sp` is not 8-byte aligned.
   - Parser evaluation: **Both** native payload (`payload.S:154-163`) and reference emulator (`vwi.py:269-270`) reach `SENTINEL_INVALID` `[VERIFIED]`.

> [!NOTE]
> **Separation of Native Payload vs Reference Emulator Behavior**:
> Buffer truncation (`len(buf) < 32`) is **omitted** from the physical memory state classes above because it is physically impossible on the camera. The native inspector takes no buffer length argument and directly reads the 8 consecutive words at `BOOT_WITNESS_ADDR = 0x0035F7A0` (`firmware/tools/witness_inspector_payload.S:57-90`). The `< 32` bytes check exists solely in `tools/validate_witness_inspector.py:244-245` as a host Python reference emulator API safety check. Thus, truncation is strictly a host-API rejection outcome and cannot explain the on-camera O6 trial observation `[VERIFIED: tools/validate_witness_inspector.py:244-245; firmware/tools/witness_inspector_payload.S:57-90]`.

### 5.3 Consistency of Memory State Classes with Hypotheses H1–H4
We evaluate how each memory state class stays consistent with hypotheses H1–H4, and emphasize that **no single hypothesis is ruled out by observation O6 alone**:

| Hypothesis | Description | Consistent Raw Memory State Classes Producing O6 Reading | Why O6 Remains Consistent with this Hypothesis |
|---|---|---|---|
| **H1** | `StartDiskboot` never reached loader (file rejected, marker missing, gate blocked). | **Class 1 (All zeros)**<br>**Class 2 (Stock heap)**<br>**Class 3 (Garbage RAM)** | If `StartDiskboot` skipped or rejected the file, stock boot proceeded normally. DRAM at `0x0035F7A0` either remained uninitialized/cleared (Class 1/3) or was actively allocated and overwritten by stock DryOS heap (Class 2). |
| **H2** | Loader ran, but `check_compat` failed or loader stopped before writing witness. | **Class 1 (All zeros)**<br>**Class 3 (Garbage RAM)**<br>**Class 4 (Partial write)** | If the loader stopped before reaching `main_prototype.c:42` (or faulted during the write sequence), `0x0035F7A0` remained unwritten (Class 1/3) or partially written (Class 4), both evaluating to `SENTINEL_INVALID`. |
| **H3** | Loader wrote witness, but stock boot later overwrote `0x0035F7A0` (core region not reserved). | **Class 2 (Stock heap)**<br>**Class 5 (Checksum / bit corruption)** | If the loader ran and wrote the witness, but early core execution faulted and triggered a soft reset into stock ROM, stock DryOS heap initialized at `0x003489B4` and dynamically overran `0x0035F7A0`, producing Class 2 or Class 5. |
| **H4** | Witness was written but is malformed (checksum / stage / layout bug). | **Class 4 (Aborted write)**<br>**Class 5 (Checksum bug / cache writeback)**<br>**Class 6 (Illegal stage)** | Although the host C probe proves the loader code *as compiled* produces a valid record, on-camera execution could still suffer from uncommitted D-cache writeback, compiler optimization bugs in ARM mode, or runtime pipeline corruption. |

### 5.4 Summary of Hardware Conclusions
1. The loader witness record as compiled in `candidate_loader.elf` is **not malformed**: when executed to completion, its output is parsed by the inspector as valid `LOADER_REACHED` (`0x57495401`) `[VERIFIED]`.
2. The actual RAM contents at `0x0035F7A0` during the O6 trial session and whether the loader writer ever executed on hardware remain **`UNKNOWN`** `[UNKNOWN]`.
3. Because multiple physical classes of memory states evaluate identically to `WITNESS_INVALID / INVALID / CORRUPT` (specifically, 8 distinct physical raw memory state classes on hardware), **observation O6 alone does not single out or rule out any of H1, H2, H3, or H4** `[VERIFIED]`.

---

## 6. Display Color Analysis: Colour Index 3 and Rendering Context

### 6.1 Inspector Failure Color Index Selection (`[VERIFIED]`)
- In `firmware/tools/witness_inspector_payload.S:193-194`, the `.Lstate_invalid` failure path explicitly selects **Color Index 3** for both Title and Status:
  ```assembly
  .Lstate_invalid:
      movs    r6, #3          /* Title Color Index 3 */
      movs    r7, #3          /* Status Color Index 3 */
      movw    r8, #0x54EE     /* SENTINEL_INVALID (0x574954EE) */
  ```
- In `tools/validate_witness_inspector.py:251, 256, 260, 273`, all failure outcomes return `(SENTINEL_INVALID, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3)` `[VERIFIED]`.
- Thus, it is **`VERIFIED`** that the inspector payload selects **Color Index 3** whenever an invalid witness state is encountered.

### 6.2 Hardware Palette Format and Rendering Independence
- **Palette Format (`AYCrCb`, NOT RGB)**:
  In GM1.10C ROM, display hardware palette entries are 32-bit `AYCrCb` values (`docs/HDMI001_OVERLAY_PIPELINE.md:98`), where bits 25:24 encode 2-bit alpha (`0x00` transparent, `0x40`, `0x80`, `0xFF` opaque) and the lower bytes encode Y, Cr, and Cb chroma/luma components `[VERIFIED: docs/HDMI001_OVERLAY_PIPELINE.md:98]`. They are **NOT** standard RGB/ARGB values.
- **Rendering Context Dependence (`[INFERRED / UNKNOWN]`)**:
  The physical on-screen color rendered for Color Index 3 depends on:
  1. The active palette buffer slot (`0x00015DB4`, `SCM.c`).
  2. The display device lookup table and video output mode (LCD vs HDMI).
  3. Whether the SCM dirty bit was pushed to the Zico co-processor (`docs/HDMI001_OVERLAY_PIPELINE.md:76, 97`).
  Therefore, the visual appearance of Color Index 3 on the physical LCD (whether perceived as Light Blue, Red, or another hue) is **`INFERRED / UNKNOWN`** without empirical colorimeter or frame capture evidence.
- **Significance for the Inspector's Display**:
  - **For Inspector Logic and Data Validation**: **Means Nothing (`[VERIFIED]`)**.
    The inspector's branch logic, string pointers (`"WITNESS_INVALID"`, `"INVALID / CORRUPT"`), memory checks, and return sentinel (`0x574954EE`) are completely invariant to the visual display color.
  - **For Visual Telemetry Interpretation**:
    Historical documentation labeled Color Index 3 as `"(Red/Red)"` (`docs/PORT18_OWNER_TRIAL_PLAN.md:267`). If the physical camera LCD showed light blue text during trial execution, this visual appearance does not indicate a parser malfunction; it simply reflects the camera's active `AYCrCb` palette rendering for Color Index 3 `[INFERRED / UNKNOWN]`.

---

## 7. Host Test Suite Summary (`tests/test_port21_witness_roundtrip.py`)

A comprehensive unit test suite has been implemented in `tests/test_port21_witness_roundtrip.py`:
- `test_real_c_writer_bytes_roundtrip`: Compiles a host C probe including `boot_witness.h` and the loader's exact field assignments (`main_prototype.c:42-56`). Asserts GCC compiler presence (skips if absent, fails loudly with stderr on compile error), verifies `sizeof(boot_witness_t) == 32` and `offsetof` for all 8 members against the parser's expected offsets (`<IIIIIIII`), and feeds the serialized hex bytes directly to `vwi.emulate_inspector_parse()`. Asserts `LOADER_REACHED` / `FRESHNESS_UNVERIFIED` (Sentinel `0x57495401`, Colors `1, 4`).
- `test_disassembly_coherence_and_sp_provenance`: Directly inspects the disassembly and machine code of `candidate_port2a/candidate_loader.elf` and `candidate_loader.bin`. Verifies entry SP initialization (`mov.w sp, #32768`), prologue stack adjustment (`push {r3, lr}` consuming 8 bytes to yield `0x00007FF8`), store of SP to `[r1, #16]`, reference to target address `0x0035F7A0`, and polynomial checksum store to `[r1, #28]`.
- `test_all_zero_region_yields_witness_invalid`: Confirms 32 bytes of zeros yields `WITNESS_INVALID` / `INVALID / CORRUPT` (Sentinel `0x574954EE`, Colors `3, 3`).
- `test_overwritten_stock_boot_data_yields_witness_invalid`: Evaluates 5 patterns of stock-boot and uninitialized memory, proving all yield `WITNESS_INVALID`.
- `test_valid_records_across_all_stages`: Tests Stage 1, Stage 2, and Stage 3 valid records.
- `test_exhaustive_rejection_modes_mapping_to_witness_invalid`: Exhaustively tests invalid magic, invalid version, bit flips, illegal stage progressions, invalid core entry PC, and misaligned loader stack across physical memory states, as well as the host-API short buffer rejection in the Python reference emulator.
- `test_color_index_3_selection_and_rendering_invariance`: Verifies that the INVALID outcome selects Color Index 3 in both `vwi.emulate_inspector_parse` and `witness_inspector_payload.S:193-194`, and proves inspector parsing is independent of rendering context.

All tests execute offline and pass cleanly without requiring ROM reads or camera hardware.
Candidate builder (`candidate_build`) and candidate validator (`candidate_validate`) remain invariant and passing.
