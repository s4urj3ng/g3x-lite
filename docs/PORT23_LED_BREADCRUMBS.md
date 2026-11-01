# PORT-23: Opt-In LED Breadcrumbs for GM1.10C Loader Verification

## 1. Overview & Objective

During the first physical hardware trial of the Canon PowerShot G3 X (GM1.10C) on 2026-11-01, the camera owner verified two crucial hardware facts:
1. Writing `0x004D0002` to MMIO `0xD20B0884` turns the rear green LED **ON** `[VERIFIED]`.
2. Writing `0x004C0003` to MMIO `0xD20B0884` turns the rear green LED **OFF** `[VERIFIED]`.
3. The loader-entry prologue at `0x8000` executes on camera power-on with an encoded boot disk `[VERIFIED]`.
4. Busy-wait stalls of `0x06000000` (~1–2 s) and `0x00600000` (~100–200 ms) both ended with the camera dark (shutdown or watchdog reset) `[VERIFIED]`.

The objective of **PORT-23** is to provide an opt-in set of diagnostic build candidates where exactly one checkpoint in the loader execution sequence turns the green LED **ON** and leaves it on (delay = 0). Physical power-ons by the camera owner with these targeted builds will isolate exactly how far execution proceeds after loader entry `0x8000` without triggering watchdog resets from long delay loops.

---

## 2. Default Build Invariance

The default production build produced by `tools/build_candidate_port2a.py` without flags is completely unaffected and remains byte-for-byte identical to the locked baseline:

- **Target Binary**: `candidate_port2a/DISKBOOT.BIN`
- **File Size**: `118,001` bytes `[VERIFIED]`
- **SHA-256**: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` `[VERIFIED]`
- **Candidate Loader Binary**: `candidate_port2a/candidate_loader.bin` (118,000 B, SHA-256 `2dab82272a15db45938561d56e72b4dbdaefdbe5da3a5ff79efdbd2d6f30df1b`)
- **Core Symbols**: `boot_witness` at `0x0035F7A0`, `_end` at `0x00366CB0` `[VERIFIED]`
- **Validator**: `python3 tools/validate_candidate_port2a.py` passes 7/7 checks `[VERIFIED]`

All breadcrumb helpers live in new files (`led_breadcrumb.h`, `loader_entry_breadcrumb.S`, `loader_main_breadcrumb.c`) or inside `#if defined(LED_BREADCRUMB_<STAGE>)` guards. When `LED_BREADCRUMB` is undefined, `led_breadcrumb.h` defines zero symbols and preprocessed loader source is byte-identical to baseline.

---

## 3. Stage Table

Each stage build activates the green LED at exactly one explicit source location. Delay is set to 0 in all documented builds (the LED turns on and stays on).

| Stage ID | Source Location | Macro Guard | What Reaching This Checkpoint Proves | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`loader_entry`** | `chdk-port/platform/g3x/sub/110c/loader_entry_breadcrumb.S:36` | `LED_BREADCRUMB_LOADER_ENTRY` | ROM loaded `DISKBOOT.BIN`, decrypted dancingbits, and reached `_start` at `0x8000`. | **VERIFIED** on hardware (2026-11-01) |
| **`before_copy`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:41` | `LED_BREADCRUMB_BEFORE_COPY` | Loader initialized stack (`0x8000`), entered `my_restart()`, and passed `check_compat()` model ID check (`0x32A8`). | **INFERRED** from `loader_main_breadcrumb.c:30-41` |
| **`after_copy`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:50` | `LED_BREADCRUMB_AFTER_COPY` | `core_copy()` returned; 116,816 bytes relocated from loader to `0x003489B4`. | **INFERRED** from `loader_main_breadcrumb.c:41-50` |
| **`witness_entry`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:57` | `LED_BREADCRUMB_WITNESS_ENTRY` | Loader reached Boot Witness Stage 1 block prior to store sequence. | **INFERRED** from `loader_main_breadcrumb.c:50-57` |
| **`witness_write`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:77` | `LED_BREADCRUMB_WITNESS_WRITE` | All 8 Boot Witness Stage 1 fields and checksum were stored to `0x0035F7A0`. | **INFERRED** from `loader_main_breadcrumb.c:57-77` |
| **`pre_jump`** | `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:115` | `LED_BREADCRUMB_PRE_JUMP` | Cache maintenance (`0xFC127AB1`, `0xFC127B09`) returned, interrupts disabled (`cpsid if`), handoff via `bx r0` to `0x003489B5` imminent. | **INFERRED** from `loader_main_breadcrumb.c:95-139` |

*Note on `after_copy` vs `witness_entry`*: Because no C statements intervene between `core_copy()` and the declaration of `volatile boot_witness_t *w`, both stages compile to the same assembly checkpoint when delay is 0 and `--off-next` is not set.

---

## 4. Host Build Commands & Expected Hashes

All builds are generated with the new standalone tool `tools/build_candidate_port23_breadcrumb.py`.

### 4.1 Stage 1: `loader_entry`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage loader_entry --out-dir candidate_breadcrumb/loader_entry
```
- **`candidate_loader.bin` Size**: `118,020` bytes
- **`candidate_loader.bin` SHA-256**: `0eb980aab0db7e968c33087568b6139103612e685d0544e9b3fcb443900376d5`
- **`DISKBOOT.BIN` Size**: `118,021` bytes
- **`DISKBOOT.BIN` SHA-256**: `60a78e40127d7aa2b05178a27d834545817ded7618fef9f26637b7789d92fe24`

### 4.2 Stage 2: `before_copy`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage before_copy --out-dir candidate_breadcrumb/before_copy
```
- **`candidate_loader.bin` Size**: `118,020` bytes
- **`candidate_loader.bin` SHA-256**: `facdd477760af95dd4abed86838a1997430d5257f50e032c3cce0c8f881cdbd4`
- **`DISKBOOT.BIN` Size**: `118,021` bytes
- **`DISKBOOT.BIN` SHA-256**: `a7cacf489791b436e002376dc1ca54bc51ae84a87d7675fcfb7b072516764353`

### 4.3 Stage 3: `after_copy`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage after_copy --out-dir candidate_breadcrumb/after_copy
```
- **`candidate_loader.bin` Size**: `118,024` bytes
- **`candidate_loader.bin` SHA-256**: `20a250c37f03ddb82d3a19fbb7daada55fc76d64883b2b2cbea0de4083943bd7`
- **`DISKBOOT.BIN` Size**: `118,025` bytes
- **`DISKBOOT.BIN` SHA-256**: `7322a4287d792950ecb5671bf3c21706f983ce90d56332d4394afdff01b670dc`

### 4.4 Stage 4: `witness_entry`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage witness_entry --out-dir candidate_breadcrumb/witness_entry
```
- **`candidate_loader.bin` Size**: `118,024` bytes
- **`candidate_loader.bin` SHA-256**: `20a250c37f03ddb82d3a19fbb7daada55fc76d64883b2b2cbea0de4083943bd7`
- **`DISKBOOT.BIN` Size**: `118,025` bytes
- **`DISKBOOT.BIN` SHA-256**: `7322a4287d792950ecb5671bf3c21706f983ce90d56332d4394afdff01b670dc`

### 4.5 Stage 5: `witness_write`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage witness_write --out-dir candidate_breadcrumb/witness_write
```
- **`candidate_loader.bin` Size**: `118,020` bytes
- **`candidate_loader.bin` SHA-256**: `bd255e561e609eec12c763a65dc0536ab5d6001ad5b2c34e8aee6c47a4561fe7`
- **`DISKBOOT.BIN` Size**: `118,021` bytes
- **`DISKBOOT.BIN` SHA-256**: `228138b90b08e6f23c3405c21d9562dc0b9d8c1dfd2f1d6da7fa647fbf887460`

### 4.6 Stage 6: `pre_jump`
```bash
python3 tools/build_candidate_port23_breadcrumb.py --stage pre_jump --out-dir candidate_breadcrumb/pre_jump
```
- **`candidate_loader.bin` Size**: `118,020` bytes
- **`candidate_loader.bin` SHA-256**: `c0c6bda42e9399212aec58f0bee2e42015b68d464dc9b5547a757c29e3ce182d`
- **`DISKBOOT.BIN` Size**: `118,021` bytes
- **`DISKBOOT.BIN` SHA-256**: `abe7432ea4f2a7df3778fb8023209639da675687e3eb0ab826de4a73cc767f75`

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
- **`DISKBOOT.BIN` Size**: `118,041` bytes
- **`DISKBOOT.BIN` SHA-256**: `865451e9dee0e9d19506c5b2d04f855456958dc52e705766205807bb50ab734f`

---

## 6. Safety Enforcements

1. **No Delays in Documented Builds**: Delay iterations default to `0`. No busy-wait loop is executed; the LED turns ON and execution proceeds immediately.
2. **Strict Delay Cap**: If `--delay` is specified, it is capped at `0x00600000` (6,291,456 iterations). Any larger value fails closed both at build script argument parsing and via compile-time preprocessor check (`#error`).
3. **Register / ABI Preservation**: Overwritten registers (`r0`, `r1`, `r2`) are dead at `my_restart` entry and fully declared in AAPCS clobber lists. Interrupt state is preserved until `cpsid if` at step 4.
4. **Isolated Paths**: No PORT-20 files (`loader_entry_led.S`, `build_candidate_port2a.py`) are modified. Scope-integrity tests pass cleanly.
