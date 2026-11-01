# PORT-23: Opt-In LED Breadcrumbs for GM1.10C Loader Verification

## 1. Overview & Objective

During the physical hardware trials of the Canon PowerShot G3 X (GM1.10C) on 2026-11-01, the camera owner verified:
1. Writing `0x004D0002` to MMIO `0xD20B0884` turns the rear green LED **ON** `[VERIFIED: hardware trial 2026-11-01]`.
2. Writing `0x004C0003` to MMIO `0xD20B0884` turns the rear green LED **OFF** `[VERIFIED: hardware trial 2026-11-01]`.
3. The loader-entry prologue at `0x8000` executes on camera power-on with an encoded boot disk `[VERIFIED: hardware trial 2026-11-01]`.
4. The `0x06000000` stall build, the `0x00600000` stall build, and the PORT-19 control re-run all ended with the camera off `[VERIFIED: owner report 2026-11-01]`.

Cause of the dark camera after loader entry: UNKNOWN (not established by this task; see PORT-23 T1).

The objective of **PORT-23** is to provide an opt-in set of diagnostic build candidates where exactly one checkpoint in the loader execution sequence turns the green LED **ON** and leaves it on (delay = 0, no busy-wait loop). Physical power-ons by the camera owner with these targeted builds are intended to show how far execution proceeds after loader entry `0x8000` `[INFERRED]`.

---

## 2. Default Build Invariance

The default production build produced by `tools/build_candidate_port2a.py` without flags is completely unaffected and remains byte-for-byte identical to the locked baseline:

- **Target Binary**: `candidate_port2a/DISKBOOT.BIN`
- **File Size**: `118,001` bytes `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:362; docs/PORT20_LED_CANDIDATE.md:68]`
- **SHA-256**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:362; docs/PORT20_LED_CANDIDATE.md:68]`
- **Candidate Loader Binary**: `candidate_port2a/candidate_loader.bin` (118,000 B, SHA-256 `2dab82272a15db45685f411926d6da32b54e158808a6ff3919b0c035c28a914a`) `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:361; docs/PORT20_LED_CANDIDATE.md:69; tests/test_port23_led_breadcrumbs.py:81-82]`
- **Candidate Core Binary**: `candidate_port2a/candidate_main.bin` (116,816 B, SHA-256 `420b3842ed56b59dc7cd24d0fb5e311fad1aec36ed38825b435d5030a314a56e`) `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:359; docs/PORT20_LED_CANDIDATE.md:70]`
- **Core Symbols**: `boot_witness` at `0x0035F7A0`, `_end` at `0x00366CB0` `[VERIFIED: tools/validate_candidate_port2a.py:48-52]`
- **Validator**: `python3 tools/validate_candidate_port2a.py` reports "ALL PORT-2A CANDIDATE VALIDATION CHECKS PASSED (OFFLINE ONLY)" (`tools/validate_candidate_port2a.py:586`); the default build is asserted by `tests/test_port23_led_breadcrumbs.py:test_default_build_invariance`

All breadcrumb helpers live in new files (`chdk-port/platform/g3x/sub/110c/led_breadcrumb.h`, `chdk-port/platform/g3x/sub/110c/loader_entry_breadcrumb.S`, `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c`) or inside `#if defined(LED_BREADCRUMB_<STAGE>)` guards. When `LED_BREADCRUMB` is undefined, `led_breadcrumb.h` defines zero symbols, and preprocessed loader source is token-identical to baseline.

### 2.1 Rationale for `loader_main_breadcrumb.c` and Citation Protection

Editing `chdk-port/loader/g3x/main_prototype.c` was intentionally avoided because tracked docs and tests cite `main_prototype.c` by exact line numbers (for example, `tests/test_port21_witness_roundtrip.py:103-125` and `docs/PORT21_WITNESS_AUDIT.md:13-123` cite lines 42–56), so editing `main_prototype.c` would break those citations. Note that scope-integrity tests do not protect `main_prototype.c` directly (`FORBIDDEN_PREFIXES` and `FORBIDDEN_FILES` in `tests/test_port21_ram_lifetime.py:71-72` do not include it). Rather, placing the breadcrumb-enabled loader in `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c` preserves citation stability in existing tests and documents.

To ensure `loader_main_breadcrumb.c` does not diverge from `main_prototype.c`, `tests/test_port23_led_breadcrumbs.py` includes `test_loader_drift_and_parity`, which compiles both `loader_main_breadcrumb.c` and `main_prototype.c` through `arm-none-eabi-gcc -E` without `LED_BREADCRUMB*` defines and asserts that the resulting preprocessed token streams are identical. Any future divergence will fail the test.

---

## 3. Stage Table

Each stage build activates the green LED at exactly one explicit source location. Delay is set to 0 in all documented builds (the LED turns on and stays on).

| Stage ID | Source Location | Macro Guard | Camera Verification / Inference | Host Deterministic Verification |
| :--- | :--- | :--- | :--- | :--- |
| **`loader_entry`** | `chdk-port/platform/g3x/sub/110c/loader_entry_breadcrumb.S:36` | `LED_BREADCRUMB_LOADER_ENTRY` | ROM loaded `DISKBOOT.BIN`, decrypted dancingbits, and reached `_start` at `0x8000`. `[VERIFIED: hardware trial 2026-11-01]` | Verified single write and instructions by `test_stage_differs_only_by_breadcrumb_instructions` and `test_exactly_one_on_write` `[VERIFIED]` |
| **`before_copy`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:37` | `LED_BREADCRUMB_BEFORE_COPY` | Loader initialized stack (`0x8000`), entered `my_restart()`, and passed `check_compat()` model ID check (`0x32A8`). `[INFERRED]` | Verified checkpoint between `check_compat` and `core_copy` by `test_exactly_one_on_write` `[VERIFIED]` |
| **`after_copy`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:52` | `LED_BREADCRUMB_AFTER_COPY` | `core_copy()` returned; 116,816 bytes relocated from loader to `0x003489B4`. `[INFERRED]` | Verified checkpoint between `core_copy` and witness store by `test_exactly_one_on_write` `[VERIFIED]` |
| **`witness_entry`** *(alias for `after_copy`)* | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:59` | `LED_BREADCRUMB_WITNESS_ENTRY` | Loader reached Boot Witness Stage 1 block prior to store sequence. Compiles to byte-identical image as `after_copy`. `[INFERRED]` | Verified checkpoint before witness store by `test_exactly_one_on_write` `[VERIFIED]` |
| **`witness_write`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:79` | `LED_BREADCRUMB_WITNESS_WRITE` | All 8 Boot Witness Stage 1 fields and checksum were stored to `0x0035F7A0`. `[INFERRED]` | Verified checkpoint after witness store by `test_exactly_one_on_write` `[VERIFIED]` |
| **`pre_jump`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:117` | `LED_BREADCRUMB_PRE_JUMP` | Cache maintenance (`0xFC127AB1`, `0xFC127B09`) returned, interrupts disabled (`cpsid if`), handoff via `bx r0` to `0x003489B5` imminent. `[INFERRED]` | Verified checkpoint after `cpsid if` and before `bx r0` by `test_pre_jump_stage_position` `[VERIFIED]` |

*Note on `after_copy` vs `witness_entry` (Duplicate / Alias Stage)*: Because no executable C statements intervene between `core_copy()` and the declaration of `volatile boot_witness_t *w`, both `after_copy` and `witness_entry` compile to 100% byte-identical binaries and share the exact same DISKBOOT.BIN SHA-256 (`0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df`). Stage `witness_entry` is an alias for `after_copy`. The camera owner should NOT spend a power-on trial on `witness_entry` once `after_copy` has been tested.

---

## 4. Host Build Commands & Expected Hashes

All builds are generated with the new standalone tool `tools/build_candidate_port23_breadcrumb.py`.

### 4.1 Stage 1: `loader_entry`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage loader_entry --out-dir candidate_breadcrumb/loader_entry
```
- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `0eb980aab0db7e968c33087568b6139103612e685d0544e9b3fcb443900376d5` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `60a78e40127d7aa2b05178a27d834545817ded7618fef9f26637b7789d92fe24` `[VERIFIED: host build]`

### 4.2 Stage 2: `before_copy`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage before_copy --out-dir candidate_breadcrumb/before_copy
```
- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `1ce8051834a6a1a9e778ae1d7433e0db4cc7169e92c9a6f594ba4c3d4598115c` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `b2a2d55e25cfd422895854d47f0d186874df9bb3450cfc46a5be045179466852` `[VERIFIED: host build]`

### 4.3 Stage 3: `after_copy`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage after_copy --out-dir candidate_breadcrumb/after_copy
```
- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `95e833aee0cd7a99cdb574315247efe69cb9c478a2c7333d3d9434f7af444ef4` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df` `[VERIFIED: host build]`

### 4.4 Stage 4: `witness_entry` (Alias for `after_copy`)
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage witness_entry --out-dir candidate_breadcrumb/witness_entry
```
> [!NOTE]
> `witness_entry` compiles to the exact same SHA-256 as `after_copy` (`0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df`). It is an alias of `after_copy`. The camera owner should NOT spend a physical power-on trial on `witness_entry` once `after_copy` has been tried.

- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `95e833aee0cd7a99cdb574315247efe69cb9c478a2c7333d3d9434f7af444ef4` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `0b02b408b8f4c3f8ddfd2d0b0e6726355aa4440cb5a40c659f1d8515651c43df` `[VERIFIED: host build]`

### 4.5 Stage 5: `witness_write`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage witness_write --out-dir candidate_breadcrumb/witness_write
```
- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `4a1de051f63822084d72b7bf300cf18bcb5e19ffc7345b0f57e773ffca550463` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `1fcad53e31f18c378b84918b65f9365e7400185423ad7dbeac62ac04555e3de8` `[VERIFIED: host build]`

### 4.6 Stage 6: `pre_jump`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage pre_jump --out-dir candidate_breadcrumb/pre_jump
```
- **`candidate_loader.bin` Size**: `118,020` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `c0c6bda42e9399212aec58f0bee2e42015b68d464dc9b5547a757c29e3ce182d` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,021` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75` `[VERIFIED: host build]`

---

## 5. Differential Turn-Off (`--off-next`)

The `--off-next` flag allows 2-checkpoint differential isolation:
- The selected stage writes `0x004D0002` (LED ON).
- The subsequent checkpoint writes `0x004C0003` (LED OFF).
- If the LED remains ON after camera boot, execution stopped between stage $S$ and stage $S+1$.
- If the LED remains dark, execution either stopped before stage $S$, or successfully reached stage $S+1$.

Example build:
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage loader_entry --off-next --out-dir candidate_breadcrumb/entry_off_next
```
- **`candidate_loader.bin` Size**: `118,040` bytes `[VERIFIED: host build]`
- **`candidate_loader.bin` SHA-256**: `95d5acfdf88294865a5feb564b1b7931e9577e83bfda20cc05c39ffa46b95c30` `[VERIFIED: host build]`
- **`DISKBOOT.BIN` Size**: `118,041` bytes `[VERIFIED: host build]`
- **`DISKBOOT.BIN` SHA-256**: `2021a873fa934e1fd144e868bb961ac313b25bd2d790102bfb31223836c8c765` `[VERIFIED: host build]`

---

## 6. Safety Enforcements

1. **No Delays in Documented Builds**: Delay iterations default to `0`. No busy-wait loop is executed; the LED turns ON and execution proceeds immediately `[VERIFIED: tests/test_port23_led_breadcrumbs.py:test_no_delay_loop_in_documented_builds]`.
2. **Strict Delay Cap**: If `--delay` is specified, it is capped at `0x00600000` (6,291,456 iterations). Any larger value fails closed both at build script argument parsing and via compile-time preprocessor check (`#error`) `[VERIFIED: tests/test_port23_led_breadcrumbs.py:test_no_delay_loop_in_documented_builds]`.
3. **Register / ABI Preservation**: Overwritten registers (`r2`, `r3`) are fully declared in AAPCS clobber lists. Interrupt state is preserved until `cpsid if` at step 4.
4. **Isolated Paths**: No PORT-20 files (`loader_entry_led.S`, `build_candidate_port2a.py`) are modified. Scope-integrity tests pass cleanly `[VERIFIED: tests/test_port23_led_breadcrumbs.py:test_scope_integrity_no_port20_files_modified]`.
