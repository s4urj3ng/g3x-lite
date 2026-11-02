# PORT-26: Owner Trial Report Template & Worked Examples (GM1.10C)

**Platform**: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID `0x32A8` = `12968` decimal, DIGIC 6, DryOS 57) `[VERIFIED: README.md:3; tools/build_candidate_port2a.py:232-234]`  
**Milestone**: PORT-26 (Ladder Ingest & Short-Press Triage)  
**Task**: `p26-t3-owner-template`  
**Ingestion Decoder**: `tools/port26_ladder_decode.py` `[VERIFIED: tools/port26_ladder_decode.py:1-2023]`  
**Test Suite**: `tests/test_port26_owner_template.py` `[VERIFIED]`  
**Candidate Specification**: `docs/PORT25_LADDER_FIX_CANDIDATE.md` `[VERIFIED]`  
**Owner Trial Protocol**: `docs/PORT25_OWNER_TRIAL_PLAN.md` `[VERIFIED]`  

---

## 1. Overview & Report Ingestion Syntax

This document establishes the official fill-in owner trial report template in the `key = value` format ingested and verified by `tools/port26_ladder_decode.py`.

### 1.1 Ingestion Syntax Rules
- **Format**: Simple line-oriented `key = value` (or `key: value`) syntax `[VERIFIED: tools/port26_ladder_decode.py:1613-1632]`.
- **Comments**: Lines beginning with `#` and empty lines are ignored as comments `[VERIFIED: tools/port26_ladder_decode.py:1615-1616]`.
- **Whitespace & Quotes**: Keys and values are stripped of surrounding whitespace; values enclosed in double (`"..."`) or single (`'...'`) quotes have their outer quotes stripped `[VERIFIED: tools/port26_ladder_decode.py:1624-1629]`.
- **Case Sensitivity**: Key names and string values are normalized case-insensitively `[VERIFIED: tools/port26_ladder_decode.py:1462, 1490, 1500]`.
- **Duplicate Key Governance**: Duplicate keys with conflicting values produce class `AMBIGUOUS` with an explicit explanatory note; last-wins overwriting is strictly prohibited `[VERIFIED: tools/port26_ladder_decode.py:117-120, 1481-1537, 1681-1694]`.

---

## 2. Field Specifications & Allowed Values

Every owner report must provide the following five primary fields, with optional uncertainty and notes fields:

| Field Name | Status | Type | Allowed Values & Explanation | Epistemic Citation |
|---|---|---|---|:---:|
| `diskboot_sha256` | **Required** | Hex string | 64-character lowercase SHA-256 digest of `A/DISKBOOT.BIN`. Pinned value for the PORT-25 combined candidate is `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15`. Any differing digest triggers `INVALID_CANDIDATE`. | `[VERIFIED: docs/PORT25_LADDER_FIX_CANDIDATE.md:385; tools/port26_ladder_decode.py:149-151, 1698-1708]` |
| `press` | **Required** | Enum string | `short` or `held`.<br>- `short`: Brief power button tap (~100-200 ms). Primary diagnostic trial.<br>- `held`: Power button held continuously until UI/backlight illuminates. Positive control trial. | `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md:98, 465-485; tools/port26_ladder_decode.py:64-78, 1714-1728]` |
| `pulses` | **Required** | Integer, list, or enum | Decoded checkpoint code of the last observed ladder checkpoint (not raw total flash count; see detailed instructions in § 2.1).<br>- `none`: Exactly zero optical pulses observed -> `NO_PULSES`.<br>- Registered table integer: One of the 29 registered ladder stage codes (loader cumulative pulses `1..7`; core two-digit framed codes $10*T+U$: `11..15`, `21..26`, `28..29`, `31..35`, `41..44`).<br>- Multiple pulse counts: Conflicting candidate readings of ONE uncertain checkpoint (e.g. `22, 23` or `[22, 23]`) -> `AMBIGUOUS`.<br>- Out-of-table integers / invalid inputs: `UNKNOWN_CODE`. | `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:191-233; docs/PORT25_LADDER_FIX_CANDIDATE.md:328-354, 358-359; tools/port26_ladder_decode.py:45-62, 80-85, 1735-1865]` |
| `lcd` | **Required** | Enum string | Visual state of the camera rear LCD display.<br>- `stock_ui`: Matches allowlist (`stock_ui`, `stock ui`, `live_view`, `shooting`, `canon_ui`, `menu`).<br>- `dark` / `off`: Screen completely unpowered/black.<br>- `backlight_off`: Backlight disabled.<br>- `on_no_ui`: Backlight illuminated without graphical UI elements.<br>- `unknown`: Unclassifiable or ambiguous state. | `[VERIFIED: tools/port26_ladder_decode.py:566-580, 583-617]` |
| `inspector_status` | **Required** | String | Status readout rendered by Canon Basic witness inspector script (`extend.m` / `WITNESS.BIN`).<br>- `not_run`: Default when camera does not boot to stock UI or inspector is not invoked.<br>- `WITNESS_INVALID`: Light blue readout at historical address `0x0035F7A0` (expected for PORT-25 combined candidate).<br>- Other readouts: `CONT_ATTEMPTED`, `CORE_REACHED`, `LOADER_REACHED`, `STALE / REPLAY`, or error tokens (`ERR_OPEN`, etc.). | `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md:86, 468-470; tools/port26_ladder_decode.py:55-57, 1516-1524]` |
| `uncertain` | *Optional* | Boolean | `true` or `false`. When `true`, if the reported checkpoint code is adjacent to two valid table codes (e.g. `2..6`, `12..14`, `22..25`, `32..34`, `42..43`, or gap `27`), the report is classified as `AMBIGUOUS`. Aliased by `uncertainty` or `count_confidence`. | `[VERIFIED: tools/port26_ladder_decode.py:93-116, 858-916, 1887-1906]` |
| `notes` | *Optional* | Free-text string | Explanatory notes detailing owner observations. Checked for affirmative uncertainty phrases (`unsure`, `approx`, `+/-1`, etc.) if explicit `uncertain` key is omitted. | `[VERIFIED: tools/port26_ladder_decode.py:103-108, 809-830, 1525-1529]` |

---

### 2.1 Decoding and Entering the 'pulses' Field (Checkpoint Code Specification)

The `pulses` field records the **DECODED checkpoint code** of the last observed ladder checkpoint, **NOT the raw total count of optical flashes** seen `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:191-197; tools/port26_ladder_decode.py:45-62]`.

#### 2.1.1 Step-by-Step Decoding Instructions & 10*T+U Formula
Core ladder checkpoints emit framed two-digit decimal codes. To decode an observed core checkpoint:
1. **Count Tens flashes ($T$)**: Count the number of flashes in the first burst ($T \in \{1, 2, 3, 4\}$) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:193-194]`.
2. **Identify inter-digit gap**: Confirm the dark pause separating digits ($[48.0, 69.0]\text{ ms}$, nominal $48.50\text{ ms}$) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:254, 279]`.
3. **Count Units flashes ($U$)**: Count the number of flashes in the second burst ($U \in \{1..9\}$) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:193-194]`.
4. **Identify frame-end gap**: Confirm the longer dark gap or terminal darkness ($\ge 90.0\text{ ms}$, nominal $90.44\text{ ms}$) marking the end of the frame `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:256, 283]`.
5. **Compute decoded code ($10*T+U$)**: Calculate the two-digit checkpoint code using the formula:
   $$\text{code} = 10 \times T + U \quad (\text{or } 10*T+U)$$

**Worked Conversion**:
- If an owner observes $T = 2$ tens flashes, an inter-digit gap, and $U = 3$ units flashes before the camera halts or powers off:
  $$\text{code} = 10 \times 2 + 3 = 23 \quad (T=2, U=3 \to \text{pulses}=23)$$
- The owner enters:
  ```ini
  pulses = 23
  ```

#### 2.1.2 Loader Cumulative Pulses vs. Core Framed Codes (per docs/PORT25_OWNER_TRIAL_PLAN.md §4)
Per `docs/PORT25_OWNER_TRIAL_PLAN.md §4:191-233`, the PORT-25 candidate implements two distinct diagnostic transmission formats:
1. **Loader-Stage Cumulative Pulses (Steps 1–7)**:
   - *Transmission format*: Emits $N$ single blinks via `LADDER_ASM_PULSE` (20.97–50.0 ms ON, 57.62–138.28 ms OFF) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:191-193; docs/PORT25_LADDER_FIX_CANDIDATE.md:214-227]`.
   - *How entered*: Entered directly as the single integer $N$ (e.g. `pulses = 1` through `pulses = 7`) `[VERIFIED: tools/port26_ladder_decode.py:48-50]`. Each integer reflects the cumulative loader step reached (`STAGE_LOADER_AFTER_PROLOGUE` through `STAGE_LOADER_BEFORE_BX`) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:202-208]`.
2. **Core-Stage Two-Digit Framed Codes (Codes 11–44)**:
   - *Transmission format*: Emits Tens ($T$) blinks, an inter-digit dark gap (41.94–100.0 ms), Units ($U$) blinks, and a frame-end dark gap (83.89–200.0 ms) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:193-194; docs/PORT25_LADDER_FIX_CANDIDATE.md:236-249]`. Checkpoints are logically grouped into Group 1 (11..15), Group 2 (21..26; fail path 28..29), Group 3 (31..35), and Group 4 (41..44) `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:199-231]`.
   - *How entered*: Entered as the decoded two-digit integer $10*T+U$ (e.g. `pulses = 11`, `pulses = 23`, `pulses = 44`), NEVER as raw flash counts `[VERIFIED: tools/port26_ladder_decode.py:51-54]`.
   - Prior to trial observation, whether a failure halts in the loader or core cannot be known `[UNKNOWN: docs/PORT25_OWNER_TRIAL_PLAN.md §4:201-230]`.

#### 2.1.3 List Values: Conflicting Candidate Readings of ONE Checkpoint vs. Sequential History
- **List value semantics**: A list value (e.g. `pulses = 22, 23` or `pulses = [22, 23]`) specifies **conflicting candidate readings of ONE uncertain checkpoint** (such as optical ambiguity between 2 and 3 units blinks for a single terminal frame) `[VERIFIED: tools/port26_ladder_decode.py:1774-1778]`. The decoder evaluates multiple candidate readings for a single checkpoint as `AMBIGUOUS` `[VERIFIED: tools/port26_ladder_decode.py:1774-1778]`.
- **Do NOT enter the sequential history of passed checkpoints**: The camera executes ladder checkpoints sequentially ($1 \to \dots \to 7 \to 11 \to \dots \to 44$) `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §3.1.1:157]`. The owner must **NOT** enter the sequence of all checkpoints passed (e.g. `pulses = 1, 2, ..., 23`). Submitting a list of passed checkpoints tells the decoder that multiple conflicting codes were seen for the terminal checkpoint, causing it to return `AMBIGUOUS`.
- **Reporting the final/last code seen (docs/PORT25_OWNER_TRIAL_PLAN.md §4 & §3.1.1)**:
  The owner reports only the **final/last code seen** where camera execution halted `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md §4:197; §3.1.1:156-160]`. Per § 3.1.1, if execution cuts off during a units-digit gap, power loss can truncate a longer stage code into a shorter valid code (e.g. Code 32 truncated into Code 31) `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md §3.1.1:154-155]`. Under the § 3.1.1 lower-bound reporting rule:
  1. Record the terminal observed code in the `pulses` field (e.g. `pulses = 31`) `[VERIFIED: tools/port26_ladder_decode.py:1735-1865]`.
  2. In the `notes` field, phrase the finding with the **last confirmed checkpoint as a lower bound** (e.g. "Last confirmed checkpoint: Code 26 (lower bound); terminal observed code: Code 31 (unconfirmed due to truncation ambiguity; matching T2 Candidate 4)") `[INFERRED: docs/PORT25_OWNER_TRIAL_PLAN.md §3.1.1:158-160]`.

#### 2.1.4 Warning: Never Enter Raw Total Flash Count (T+U)
> [!WARNING]
> **Entering the raw total flash count ($T+U$) causes catastrophic misclassification!**  
> Entering the raw total flash count ($T+U$) instead of the decoded checkpoint code ($10*T+U$) quietly produces a false decoder class.  
> **Example**: If the camera halts at Code 23 (2 tens flashes followed by 3 units flashes), the owner sees a total of $2 + 3 = 5$ optical flashes. If the owner enters `pulses = 5`, the decoder quietly returns **`CODE_5`** (`STAGE_LOADER_BEFORE_ICACHE`). This erroneously diagnoses a Stage 5 Initial Task core checkpoint in `boot_prototype_ladder.c:347` as an early loader cache flush in `loader_main_breadcrumb.c:132`, misleading engineering triage.  
> **Always enter the decoded checkpoint code ($10*T+U$) for core checkpoints!**

---

## 3. Blank Report Template

To submit an owner trial result, copy the fenced template block below, fill in the observed values, and run `tools/port26_ladder_decode.py`:

```ini
# Template: BLANK
# PORT-26 GM1.10C Owner Trial Report — Blank Fill-in Template
# Required keys: diskboot_sha256, press, pulses, lcd, inspector_status
# Pinned candidate digest: 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15

diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 
lcd = dark
inspector_status = not_run
uncertain = false
notes = 
```

*(Note: In the unfilled template above, `pulses` is intentionally blank. Decoding the unfilled template produces `UNKNOWN_CODE` until a decoded checkpoint code or `'none'` is provided.)*

---

## 4. Decoder Classification Rules

The decoder maps trial reports deterministically into exactly **34 outcome classes** `[VERIFIED: tools/port26_ladder_decode.py:553-561]`:
1. **29 Valid Table Codes (`CODE_<N>`)**:
   - **Loader (Codes 1..7)**: Loader prologue, core DRAM relocation, cache flushing, and handoff jump.
   - **Core Group 1 (Codes 11..15)**: Pre-kernel setup, BSS zeroing, Stage 3 witness, DryOS memory descriptors, Initial Task spawn.
   - **Core Group 2 (Codes 21..26)**: Stage 5 entry, driver setups, Stage 5 button power check, bypass verification (`loc_fc05b978`), DryOS `CreateTask("Startup")`.
   - **Native Power-Cut Failure Path (Codes 28..29)**: Native unbypassed power cut via GPIO 0x67 (`0xD20B099C`) in `sub_fc05ba56` (only seen if `G3X_POWERON_FIX=0`).
   - **Core Group 3 (Codes 31..35)**: `task_Startup_my` execution, early driver initialization, SD1stInit gate check, SD1stInit veneer return, pre-watchdog arming.
   - **Core Group 4 (Codes 41..44)**: Hardware watchdog actively armed, task_PhySw spawner helper, helper return, pre-continuation handoff to `sub_fc0d0126`.
2. **5 Special Trial Classes**:
   - `NO_PULSES`: Exactly zero pulses observed (`pulses = none`).
   - `UNKNOWN_CODE`: Unregistered checkpoint codes (gaps like `27`, `30`, or out-of-range like `99`), non-positive codes, or invalid formats.
   - `AMBIGUOUS`: Conflicting duplicate keys, multiple conflicting candidate readings for one checkpoint (e.g. `pulses = 22, 23` or `[22, 23]`), or an off-by-one uncertain code adjacent to two valid codes.
   - `INVALID_CANDIDATE`: `diskboot_sha256` does not match the pinned PORT-25 combined candidate digest.
   - `CONTROL_HELD_O1`: Held button press (`press = held`) that affirmatively boots to the stock Canon UI (`lcd = stock_ui`).

---

## 5. Worked Examples by Decoder Class

Below is exactly one filled-in worked example for every decoder class in `tools/port26_ladder_decode.py`.

### 5.1 Loader Stage Checkpoints (Codes 1..7)

#### Worked Example: CODE_1
```ini
# Expected Class: CODE_1
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 1
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 1 (STAGE_LOADER_AFTER_PROLOGUE): Entry prologue and check_compat() completed.
```

#### Worked Example: CODE_2
```ini
# Expected Class: CODE_2
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 2
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 2 (STAGE_LOADER_AFTER_COPY): Core payload copied to 0x003489B4.
```

#### Worked Example: CODE_3
```ini
# Expected Class: CODE_3
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 3
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 3 (STAGE_LOADER_BEFORE_DCACHE): Immediately before ROM D-cache clean/invalidate (0xFC127AB1).
```

#### Worked Example: CODE_4
```ini
# Expected Class: CODE_4
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 4
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 4 (STAGE_LOADER_AFTER_DCACHE): D-cache clean/invalidate completed.
```

#### Worked Example: CODE_5
```ini
# Expected Class: CODE_5
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 5
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 5 (STAGE_LOADER_BEFORE_ICACHE): Immediately before ROM I-cache invalidate (0xFC127B09).
```

#### Worked Example: CODE_6
```ini
# Expected Class: CODE_6
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 6
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 6 (STAGE_LOADER_AFTER_ICACHE): I-cache invalidate completed.
```

#### Worked Example: CODE_7
```ini
# Expected Class: CODE_7
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 7
lcd = dark
inspector_status = not_run
uncertain = false
notes = Loader Step 7 (STAGE_LOADER_BEFORE_BX): Final loader step immediately before bx r0 to core (0x003489B5).
```

---

### 5.2 Core Group 1: Pre-Kernel & Trampoline (Codes 11..15)

#### Worked Example: CODE_11
```ini
# Expected Class: CODE_11
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 11
lcd = dark
inspector_status = not_run
uncertain = false
notes = Core Entry (STAGE_BC_CORE_ENTRY): Entry to core boot() immediately after SP reset (mov sp, r0).
```

#### Worked Example: CODE_12
```ini
# Expected Class: CODE_12
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 12
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post BSS (STAGE_BC_POST_BSS): Low/High RAM copies and Canon BSS zeroing completed.
```

#### Worked Example: CODE_13
```ini
# Expected Class: CODE_13
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 13
lcd = dark
inspector_status = not_run
uncertain = false
notes = Stage 3 Entry (STAGE_BC_STAGE3_ENTRY): Entry to sub_fc05b3c8_my immediately after witness_record_core.
```

#### Worked Example: CODE_14
```ini
# Expected Class: CODE_14
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 14
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-Kernel Init (STAGE_BC_PRE_KERNEL_INIT): DryOS memory descriptors initialized; before blx sub_fc31b408.
```

#### Worked Example: CODE_15
```ini
# Expected Class: CODE_15
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 15
lcd = dark
inspector_status = not_run
uncertain = false
notes = Stage 4 Entry (STAGE_BC_STAGE4_ENTRY): Entry to sub_fc05b558_my (Initial Task) after push {r4, lr}.
```

---

### 5.3 Core Group 2: Stage 5 Startup Creation & Power Checks (Codes 21..26)

#### Worked Example: CODE_21
```ini
# Expected Class: CODE_21
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 21
lcd = dark
inspector_status = not_run
uncertain = false
notes = Stage 5 Entry (STAGE_BC_STAGE5_ENTRY): Entry to sub_fc05b962_my after push {r3, lr}.
```

#### Worked Example: CODE_22
```ini
# Expected Class: CODE_22
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 22
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-MPU Setup (STAGE_BC_PRE_MPU_SETUP): Immediately before bl sub_fc05ba68 (pxSetup, dhcpc_setup, mpuSetup).
```

#### Worked Example: CODE_23
```ini
# Expected Class: CODE_23
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 23
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post-MPU Setup (STAGE_BC_POST_MPU_SETUP): Immediately after bl sub_fc05ba68; proves setup calls returned.
```

#### Worked Example: CODE_24
```ini
# Expected Class: CODE_24
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 24
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-Power Check (STAGE_BC_PRE_POWER_CHECK): After bl sub_fc079404, before button check sub_fc1284ac.
```

#### Worked Example: CODE_25
```ini
# Expected Class: CODE_25
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 25
lcd = dark
inspector_status = not_run
uncertain = false
notes = Power Check Pass (STAGE_BC_POWER_CHECK_PASS): Label loc_fc05b978 reached; button check passed or bypassed via G3X_POWERON_FIX.
```

#### Worked Example: CODE_26
```ini
# Expected Class: CODE_26
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 26
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-Create Startup (STAGE_BC_PRE_CREATE_STARTUP): Immediately before blx sub_fc31bbc4 (DryOS CreateTask Startup).
```

---

### 5.4 Native Power-Cut Failure Path (Codes 28..29)

#### Worked Example: CODE_28
```ini
# Expected Class: CODE_28
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 28
lcd = dark
inspector_status = not_run
uncertain = false
notes = Fail Power Cut (STAGE_BC_FAIL_POWER_CUT): Code 28 emitted if sub_fc1284ac returned 0, immediately before bl sub_fc05ba56 cuts power.
```

#### Worked Example: CODE_29
```ini
# Expected Class: CODE_29
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 29
lcd = dark
inspector_status = not_run
uncertain = false
notes = Halt Shutdown (STAGE_BC_HALT_SHUTDOWN): Code 29 emitted at label loc_fc05b976 if sub_fc05ba56 returns without immediate cut.
```

---

### 5.5 Core Group 3: task_Startup_my Pre-Watchdog (Codes 31..35)

#### Worked Example: CODE_31
```ini
# Expected Class: CODE_31
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 31
lcd = dark
inspector_status = not_run
uncertain = false
notes = Startup Entry (STAGE_BC_STARTUP_ENTRY): First frame emitted by created task (Startup entry).
```

#### Worked Example: CODE_32
```ini
# Expected Class: CODE_32
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 32
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post Early Init (STAGE_BC_POST_EARLY_INIT): Early driver calls (sub_fc0d0150..sub_fc418eec) returned.
```

#### Worked Example: CODE_33
```ini
# Expected Class: CODE_33
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 33
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-SD1stInit (STAGE_BC_PRE_SD1STINIT): Immediately before SD1stInit gate check sub_fc05c4e0.
```

#### Worked Example: CODE_34
```ini
# Expected Class: CODE_34
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 34
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post-SD1stInit (STAGE_BC_POST_SD1STINIT): Label 1: after SD1stInit task creation veneer.
```

#### Worked Example: CODE_35
```ini
# Expected Class: CODE_35
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 35
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-Watchdog Start (STAGE_BC_PRE_WATCHDOG_START): Immediately before bl sub_fc418f2a (watchdog arming helper).
```

---

### 5.6 Core Group 4: task_Startup_my Post-Watchdog & Continuation (Codes 41..44)

#### Worked Example: CODE_41
```ini
# Expected Class: CODE_41
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 41
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post-Watchdog Start (STAGE_BC_POST_WATCHDOG_START): Immediately after bl sub_fc418f2a; watchdog is actively armed.
```

#### Worked Example: CODE_42
```ini
# Expected Class: CODE_42
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 42
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-PhySw Create (STAGE_BC_PRE_PHYSW_CREATE): Immediately before bl sub_fc1283d2 (task_PhySw launcher helper).
```

#### Worked Example: CODE_43
```ini
# Expected Class: CODE_43
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 43
lcd = dark
inspector_status = not_run
uncertain = false
notes = Post-PhySw Create (STAGE_BC_POST_PHYSW_CREATE): sub_fc1283d2 returned (does NOT prove task_PhySw ran).
```

#### Worked Example: CODE_44
```ini
# Expected Class: CODE_44
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 44
lcd = dark
inspector_status = not_run
uncertain = false
notes = Pre-Firmware Continuation (STAGE_BC_PRE_FIRMWARE_CONT): Immediately before pop.w {r4, lr}; b.w sub_fc0d0126 (stock handoff).
```

---

### 5.7 Special Trial Classes

#### Worked Example: NO_PULSES
```ini
# Expected Class: NO_PULSES
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = none
lcd = dark
inspector_status = not_run
uncertain = false
notes = No LED pulses observed on short press; LED remained dark from start.
```

#### Worked Example: UNKNOWN_CODE
```ini
# Expected Class: UNKNOWN_CODE
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 99
lcd = dark
inspector_status = not_run
uncertain = false
notes = Decoded checkpoint code 99 does not match any registered code in the PORT-25 ladder stage table.
```

#### Worked Example: AMBIGUOUS
```ini
# Expected Class: AMBIGUOUS
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 22, 23
lcd = dark
inspector_status = not_run
uncertain = false
notes = Conflicting candidate readings (Code 22 vs 23) of ONE uncertain terminal checkpoint; classifies as AMBIGUOUS per § 2.1.
```

#### Worked Example: INVALID_CANDIDATE
```ini
# Expected Class: INVALID_CANDIDATE
diskboot_sha256 = 0000000000000000000000000000000000000000000000000000000000000000
press = short
pulses = 24
lcd = dark
inspector_status = not_run
uncertain = false
notes = Candidate DISKBOOT SHA-256 mismatch against expected PORT-25 combined candidate digest.
```

#### Worked Example: CONTROL_HELD_O1
```ini
# Expected Class: CONTROL_HELD_O1
diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = held
pulses = 44
lcd = stock_ui
inspector_status = not_run
uncertain = false
notes = Held-press control trial successfully booted to stock user interface (Outcome O1/O6). Confirms baseline hardware responsiveness.
```

---

## 6. Offline Tool Execution & Ingestion

Run `tools/port26_ladder_decode.py` on the host workstation to classify an owner trial report:

```bash
# Ingest report file in key=value format
python3 tools/port26_ladder_decode.py path/to/owner_report.txt

# Or pass via stdin
cat path/to/owner_report.txt | python3 tools/port26_ladder_decode.py -

# Or evaluate inline string via --report
python3 tools/port26_ladder_decode.py --report "diskboot_sha256 = 9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15
press = short
pulses = 25
lcd = dark
inspector_status = not_run"
```

The tool emits deterministic, sorted JSON summarizing the classification:
```json
{
  "class": "CODE_25",
  "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:344; boot_prototype_ladder.c:361",
  "last_stage_reached": "STAGE_BC_POWER_CHECK_PASS",
  "next_stage": "STAGE_BC_PRE_CREATE_STARTUP",
  "notes": "Checkpoint: Label loc_fc05b978; button check passed or bypassed via G3X_POWERON_FIX (Initial Task)."
}
```
