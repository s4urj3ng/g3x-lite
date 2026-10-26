# PORT-7C — CHDK Platform Offline Validation Framework

Date: **2026-10-26 (Asia/Seoul)**  
Author: Gemini (Primary Developer & Historical-Source Comparison Specialist)  
Tech Lead: ChatGPT  
Independent Reviewer: Codex  
Collaborators: Claude (PORT-7B owner)  
Target: Canon PowerShot G3 X (Firmware `GM1.10C`, Platform ID `0x32A8` = 12968, DIGIC 6, DryOS 57)  
Baseline: `main` after merged PR #5 (`f8cc7a9`)  
Historical Reference: Ranma's GM1.10E port patch (`g3x_110e.patch`, 336,714 B, SHA-256 `55927968...`, CHDK trunk r5480 base)  

---

## 1. Executive Summary & Framework Scope

The objective of **PORT-7C** is to establish a rigorous, reusable offline validation framework for Canon PowerShot G3 X platform configuration sources without modifying unsupported firmware-specific behavior.

Following the integration gap inventory in [PORT-6C](PORT6C_CHDK_INTEGRATION_GAPS.md), the static validation plan in [PORT-7A](PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md), and the Playback ALT mask resolution in [PORT-7B](PORT7B_PLAYBACK_MASK_CORRECTION.md), PORT-7C provides:

1. **In-depth comparative analysis** across Keyboard, Shooting Modes, Aperture/ND, and Display subsystems.
2. **Detection of historical inconsistencies**, including a mathematical proof that historical ND aperture steps in GM1.10E derive from a synthetic grid rather than physical lens aperture calibration.
3. **Dedicated offline regression suite** (`tests/test_port7c_platform_validation.py`), comprising 23 tests that validate proven invariants while reporting unverified historical features as `UNVERIFIED / HISTORICAL_ONLY` without triggering test failures.
4. **Ranked list of genuinely actionable source corrections**, strictly separated from speculative historical imports.

### Strict Governance & Boundaries
- **No Runtime/Code Modification**: Platform C files, loader trampolines, and headers are NOT modified in this milestone.
- **PORT-7B Boundary Respected**: Claude owns PORT-7B (`KEYS_MASK0 = 0x000533F9`). PORT-7C verifies that Playback is covered while Power remains excluded, without altering mask definitions.
- **Historical Address & Constant Insulation**: No historical GM1.10E addresses, mode mappings, or synthetic apertures are mechanically imported.
- **Hardware Status**: **STRICT NO-GO**.

---

## 2. Subsystem In-Depth Analysis

### 2.1 Section A: Keyboard Subsystem & Mask Coverage

#### 2.1.1 Historical (GM1.10E) vs. Current (GM1.10C) Keymap
The historical GM1.10E port (`g3x_110e.patch:138–158`) defines **19 non-sentinel entries** in `keymap[]`, whereas current GM1.10C `kbd.c` defines **14 entries**. All entries operate in switch word 0.

| Key Identifier | Current Mask (110C) | Historical Mask (110E) | Switch Word / Bit | Empirical Status (GM1.10C) | Architectural Classification |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `KEY_SHOOT_FULL` | `0x00040001` | `0x00040001` | Word 0, Bit 0 \| 18 | ROM switch table (idx 0/16); composite half\|full | **VERIFIED STATIC** |
| `KEY_SHOOT_HALF` | `0x00040000` | `0x00040000` | Word 0, Bit 18 | ROM switch table (idx 16) | **VERIFIED STATIC** |
| `KEY_SHOOT_FULL_ONLY` | `0x00000001` | `0x00000001` | Word 0, Bit 0 | ROM switch table (idx 0) | **VERIFIED STATIC** |
| `KEY_ZOOM_OUT` | **Absent** | `0x00000002` | Word 0, Bit 1 | `physw_bits.txt` event `0x16` (`0xFC66C950`) | **HISTORICAL REFERENCE ONLY** |
| `KEY_ZOOM_IN` | **Absent** | `0x00000004` | Word 0, Bit 2 | `physw_bits.txt` event `0x12` (`0xFC66C958`) | **HISTORICAL REFERENCE ONLY** |
| `KEY_VIDEO` | `0x00000008` | `0x00000008` | Word 0, Bit 3 | Observed `D0 = 0x8` in UI-001B-1 (event `0x2`) | **VERIFIED OBSERVED** |
| `KEY_MENU` | `0x00000010` | `0x00000010` | Word 0, Bit 4 | Observed `D0 = 0x10` in UI-001B-1 (event `0x14`) | **VERIFIED OBSERVED** |
| `KEY_UP` | `0x00000020` | `0x00000020` | Word 0, Bit 5 | Observed `D0 = 0x20` in UI-001B-1 (event `0x6`, 2 runs) | **VERIFIED OBSERVED** |
| `KEY_DOWN` | `0x00000040` | `0x00000040` | Word 0, Bit 6 | Observed `D0 = 0x40` in UI-001B-1 (event `0x7`) | **VERIFIED OBSERVED** |
| `KEY_RIGHT` | `0x00000080` | `0x00000080` | Word 0, Bit 7 | Observed `D0 = 0x80` in UI-001B-1 (event `0x9`) | **VERIFIED OBSERVED** |
| `KEY_LEFT` | `0x00000100` | `0x00000100` | Word 0, Bit 8 | Observed `D0 = 0x100` in UI-001B-1 (event `0x8`) | **VERIFIED OBSERVED** |
| `KEY_SET` | `0x00000200` | `0x00000200` | Word 0, Bit 9 | ROM switch table (idx 9, event `0xA`) | **VERIFIED STATIC** |
| `KEY_ERASE` | **Absent** | `0x00000800` | Word 0, Bit 11 | `physw_bits.txt` event `0xF` (`0xFC66C998`) | **HISTORICAL REFERENCE ONLY** |
| `KEY_DISPLAY` | `0x00001000` | `0x00001000` | Word 0, Bit 12 | Observed `D0 = 0x1000` in UI-001B-1 (event `0xD`) | **VERIFIED OBSERVED** |
| `KEY_WIFI` | `0x00002000` | `0x00002000` | Word 0, Bit 13 | Observed `D0 = 0x2000` in UI-001B-1 (event `0x103`) | **VERIFIED OBSERVED** |
| `KEY_PRINT` | **Absent** | `0x00004000` | Word 0, Bit 14 | `physw_bits.txt` event `0x10` (`0xFC66C9B0`) | **HISTORICAL REFERENCE ONLY** |
| `KEY_PLAYBACK` | `0x00010000` | `0x00010000` | Word 0, Bit 16 | ROM switch table (idx 14, event `0x101`) | **VERIFIED STATIC** |
| `KEY_POWER` | `0x00020000` | `0x00020000` | Word 0, Bit 17 | ROM switch table (idx 15, event `0x100`) | **VERIFIED STATIC** |
| `KEY_AE_LOCK` | **Absent** | `0x10000000` | Word 0, Bit 28 | `physw_bits.txt` event `0x11` (`0xFC66C9D0`) | **HISTORICAL REFERENCE ONLY** |

#### 2.1.2 Analysis of Mask Coverage & PORT-7B State
1. **Observed Keys Union**: Bits `{3, 4, 5, 6, 7, 8, 12, 13}` $\rightarrow$ `0x000031F8`. All 8 bits are hardware-observed in empirical UI-001B-1 runs.
2. **Current Override Mask (`KEYS_MASK0`)**: 
   - Initial value: `0x000433F9` (covered observed keys + SET + Shutter, but omitted Playback and Power).
   - Following **PORT-7B** (Claude): updated to **`0x000533F9`** (`0x000433F9 | 0x00010000`).
   - Bit 16 (`KEY_PLAYBACK`) is now covered, satisfying common CHDK ALT-key suppression (`kbd_common.c:179–183`).
   - Bit 17 (`KEY_POWER`) remains strictly excluded, preventing accidental hardware shutdown suppression.
3. **The Five Missing Historical Keys**:
   - The existence of switch-table entries in `physw_bits.txt` for events `0x16`, `0x12`, `0xF`, `0x10`, `0x11` proves that the physical switch matrix has bits at positions 1, 2, 11, 14, 28.
   - However, **symbolic naming** (Zoom In vs Out, Erase vs AE Lock) is purely a historical convention from Ranma's patch. Without physical keypress sampling or eventproc verification on GM1.10C hardware, these keys remain classified as **`HISTORICAL_REFERENCE_ONLY`** and must not be treated as missing verified keys.

---

### 2.2 Section B: Shooting Mode Mappings & Namespace Partitions

Current `shooting.c` maps **17 capture modes**, while Ranma's historical port maps **32 modes** (a deficit of 15 modes).

```
   +-----------------------------------------------------------------------+
   | Canon Firmware Mode ID Partitions                                     |
   +-----------------------------------------------------------------------+
   | Basic / Manual PAS:     32768..32773  [AUTO, M, AV, TV, P]            |
   | Creative / Hybrid:      33298..33299  [HYBRID_AUTO, CREATIVE_EFFECT]  |
   | Video Modes:             2643..2652   [STD, IFRAME, M, SHORT_CLIP]    |
   | Standard Scene Modes:   16406..16953  [PORTRAIT, FIREWORK, NIGHT...]  |
   | Historical "oo" Modes:   8753..8775   [HDR, NOSTALGIC, FISHEYE...]    |
   +-----------------------------------------------------------------------+
```

#### 2.2.1 Audit of Current 17 Modes vs. Missing 15 Modes
- **Current 17 Modes**:
  All 17 numeric IDs are verified members of the Canon GM1.10C 35-mode ROM list recorded in dossier reviews (E1 §7). Numeric values are unique, strictly positive, and match historical integers.
- **The 15 Missing Modes**:
  - `MODE_SPORTS` (`33288`)
  - 4 Scene Modes: `MODE_SMART_SHUTTER` (`16949`), `MODE_FACE_SELF_TIMER` (`16948`), `MODE_WINK_SELF_TIMER` (`16950`), `MODE_SNOW` (`16414`)
  - 10 Creative Filter Modes: `MODE_HDR` (`8775`), `MODE_NOSTALGIC` (`8753`), `MODE_FISHEYE` (`8759`), `MODE_MINIATURE` (`8760`), `MODE_TOY_CAMERA` (`8763`), `MODE_BACKGROUND_DEFOCUS` (`8764`), `MODE_SOFTFOCUS` (`8765`), `MODE_MONOCHROME` (`8767`), `MODE_SUPER_VIVID` (`8754`), `MODE_POSTER_EFFECT` (`8755`)
- **Validation Ruling**:
  Presence in Ranma's patch does not prove that GM1.10C ROM maps the exact same mode IDs to these symbolic names. In particular, creative filter IDs (`8753..8775`) are known to vary across DIGIC 6 firmware revisions. Therefore, the framework tests consistency of the 17 verified modes and records the 15 historical modes as **`HISTORICAL_UNVERIFIED_FOR_GM110C`** without failing the suite.

---

### 2.3 Section C: Aperture Tables & ND Filter Grid Inconsistency

Current GM1.10C `shooting.c` provides physical aperture sizes from f/2.8 to f/11.0 across 13 entries. Historical GM1.10E added 6 extended entries for the built-in 3-stop ND filter.

#### 2.3.1 Mathematical Audit of ND Attenuation
In CHDK/APEX96 conventions, 1 EV (stop) equals **96 APEX units**.  
The G3 X built-in ND filter provides **3 EV** of attenuation:
$$\Delta\text{APEX} = 3 \times 96 = 288\text{ units}$$

Subtracting 288 units from Ranma's historical ND entries:

| Historical Index | Total APEX | Attenuation ($\Delta$) | Derived Base APEX | Expected Physical APEX | Match Physical Table? |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 26 (f/13.0) | 704 | 288 | **416** | 401 (f/4.5) | **NO** |
| 27 (f/14.0) | 736 | 288 | **448** | 433 (f/5.0) | **NO** |
| 28 (f/16.0) | 768 | 288 | **480** | 465 (f/5.6) | **NO** |
| 29 (f/18.0) | 800 | 288 | **512** | 497 (f/6.3) | **NO** |
| 30 (f/20.0) | 832 | 288 | **544** | 529 (f/7.1) | **NO** |
| 31 (f/22.0) | 864 | 288 | **576** | 561 (f/8.0) | **NO** |

#### 2.3.2 Critical Finding: Synthetic 1/3-EV Grid vs. Physical Apertures
Notice the derived base sequence: `{416, 448, 480, 512, 544, 576}`.  
This is an idealized mathematical arithmetic sequence with constant step $32 = 96 / 3$ (standard 1/3-EV spacing):
$$384 + 32 = 416,\quad 416 + 32 = 448,\quad 448 + 32 = 480\dots$$

However, the actual physical G3 X zoom lens iris table in `shooting.c` uses non-uniform calibrated steps:
`{288, 320, 352, 369, 401, 433, 465, 497, 529, 561, 593, 625, 657}`.

**Conclusion**: Ranma's historical ND table did **not** derive from the physical G3 X iris aperture values. It represents a synthetic, idealized 1/3-EV arithmetic progression rather than a table calibrated to the physical G3 X iris aperture curve (its external or synthetic provenance cannot be conclusively attributed to a specific camera model).  
**Action**: Historical ND entries must **NOT** be mechanically imported into GM1.10C. Doing so would produce aperture calculation mismatches with Canon firmware's exposure engine.

---

### 2.4 Section D: Display Configuration & Compile-Time Consistency

#### 2.4.1 Geometry Containment
- Current GM1.10C:
  - `CAM_SCREEN_WIDTH = 720`, `CAM_SCREEN_HEIGHT = 480`
  - `CAM_BITMAP_WIDTH = 736`, `CAM_BITMAP_HEIGHT = 480`
  - Containment: $720 \le 736$ and $480 \le 480$ (**PASS**).
  - Stride: $736 \pmod{16} = 0$ and $736 \pmod{32} = 0$ (**PASS**).
- Historical GM1.10E:
  - `CAM_SCREEN_WIDTH = 900`, `CAM_SCREEN_HEIGHT = 600`
  - `CAM_BITMAP_WIDTH = 928`, `CAM_BITMAP_HEIGHT = 600`
  - EVF DC-2 mode: `1024x768`.

#### 2.4.2 Compile-Time Coupling & Linkage Hazards
In CHDK core (`core/shooting.c`), defining `CAM_SUPPORT_BITMAP_RES_CHANGE` causes the core to invoke `update_screen_dimensions()`.  
If a developer enables `#define CAM_SUPPORT_BITMAP_RES_CHANGE 1` in `platform_camera.h` without implementing `update_screen_dimensions()` in `lib.c`, compilation fails at link time with an unresolved external symbol.

Current configuration correctly satisfies this mutual exclusion invariant:
- `CAM_SUPPORT_BITMAP_RES_CHANGE` is **undefined**.
- `update_screen_dimensions()` is **unimplemented**.
- The offline test suite asserts that neither symbol is partially present.

---

## 3. Regression Framework Architecture

The regression framework is implemented in `tests/test_port7c_platform_validation.py` using Python standard library `unittest`.

### 3.1 Suite Structure & Test Classes

| Test Class | Scope & Focus | Test Count |
| :--- | :--- | :---: |
| `TestPort7cKeyboardValidation` | 14 keymap entries, 8 observed keys, 6 static keys, shutter composite, ancillary flags, mask coverage, Playback ownership boundary | 8 |
| `TestPort7cShootingModesValidation` | 17 current mode numbers, uniqueness, DryOS namespace partitions, 15 historical mode unverified classification | 3 |
| `TestPort7cApertureAndNdValidation` | 13 physical aperture monotonicity, f-number formatting, mathematical proof of historical ND synthetic grid inconsistency | 3 |
| `TestPort7cDisplayConfigurationValidation` | 720x480 screen containment in 736x480 bitmap, stride alignment, compile-time mutual exclusion of resolution change flags | 3 |
| `TestPort7cFailClosedNegativeControls` | Fail-closed on missing sources, commented macros, non-literal expressions, duplicate macros, malformed keymaps, bad geometry | 6 |
| **Total** | **Comprehensive Platform Configuration Invariants** | **23** |

### 3.2 Test Execution Results

```sh
python3 -B -m unittest discover -s tests -p test_port7c_platform_validation.py -v
```

```
test_current_aperture_string_labels (test_port7c_platform_validation.TestPort7cApertureAndNdValidation.test_current_aperture_string_labels) ... ok
test_current_aperture_table_invariants (test_port7c_platform_validation.TestPort7cApertureAndNdValidation.test_current_aperture_table_invariants) ... ok
test_historical_nd_aperture_grid_inconsistency (test_port7c_platform_validation.TestPort7cApertureAndNdValidation.test_historical_nd_aperture_grid_inconsistency) ... ok
test_compile_time_resolution_change_consistency (test_port7c_platform_validation.TestPort7cDisplayConfigurationValidation.test_compile_time_resolution_change_consistency) ... ok
test_current_display_containment (test_port7c_platform_validation.TestPort7cDisplayConfigurationValidation.test_current_display_containment) ... ok
test_display_dimension_classification (test_port7c_platform_validation.TestPort7cDisplayConfigurationValidation.test_display_dimension_classification) ... ok
test_commented_macro_rejected (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_commented_macro_rejected) ... ok
test_duplicate_macro_rejected (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_duplicate_macro_rejected) ... ok
test_expression_macro_rejected (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_expression_macro_rejected) ... ok
test_malformed_keymap_rejected (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_malformed_keymap_rejected) ... ok
test_missing_source_fails_closed (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_missing_source_fails_closed) ... ok
test_screen_exceeding_bitmap_fails_containment (test_port7c_platform_validation.TestPort7cFailClosedNegativeControls.test_screen_exceeding_bitmap_fails_containment) ... ok
test_ancillary_flag_definitions (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_ancillary_flag_definitions) ... ok
test_composite_shutter_invariants (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_composite_shutter_invariants) ... ok
test_historical_keys_unverified_discrepancy (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_historical_keys_unverified_discrepancy) ... ok
test_keymap_structural_invariants (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_keymap_structural_invariants) ... ok
test_observed_keys_integrity (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_observed_keys_integrity) ... ok
test_override_mask_covers_observed_keys (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_override_mask_covers_observed_keys) ... ok
test_playback_mask_ownership_boundary (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_playback_mask_ownership_boundary) ... ok
test_static_keys_integrity (test_port7c_platform_validation.TestPort7cKeyboardValidation.test_static_keys_integrity) ... ok
test_current_mode_namespace_partitions (test_port7c_platform_validation.TestPort7cShootingModesValidation.test_current_mode_namespace_partitions) ... ok
test_current_modes_count_and_uniqueness (test_port7c_platform_validation.TestPort7cShootingModesValidation.test_current_modes_count_and_uniqueness) ... ok
test_historical_modes_unverified_discrepancy (test_port7c_platform_validation.TestPort7cShootingModesValidation.test_historical_modes_unverified_discrepancy) ... ok

----------------------------------------------------------------------
Ran 23 tests in 0.014s

OK
```

---

## 4. Ranked List of Genuinely Actionable Source Corrections

The following ranked list distinguishes **evidence-supported, safe source improvements** from unverified historical features:

### Rank 1: Accurate Switch-Table Index Comments in `kbd.c` (Safe Documentation Fix)
- **Problem**: Comments in `kbd.c` (e.g. `// ROM table idx 0`, `idx 4`) reference an arbitrary condensed list rather than genuine 0-indexed positions in `physw_event_table` (`0xFC66C948`). For instance, `KEY_PLAYBACK` is commented as idx 10, but in the ROM table it is entry 14 (`0xFC66C9B8`).
- **Correction**: Update comment strings in `kbd.c` to reflect actual 0-indexed positions in `physw_bits.txt`.
- **Safety**: Purely comment text. Zero binary, assembly, or runtime impact.

### Rank 2: Compile-Time Mutual Exclusion Assertion for Bitmap Resolution Change
- **Problem**: If `CAM_SUPPORT_BITMAP_RES_CHANGE` is accidentally defined without implementing `update_screen_dimensions()`, build fails at link time.
- **Correction**: Add a preprocessor check in `platform_camera.h` or `lib.c`:
  ```c
  #if defined(CAM_SUPPORT_BITMAP_RES_CHANGE) && !defined(UPDATE_SCREEN_DIMENSIONS_IMPLEMENTED)
  #error "CAM_SUPPORT_BITMAP_RES_CHANGE requires update_screen_dimensions() implementation in lib.c"
  #endif
  ```
- **Safety**: Compile-time safety guard. Prevents broken intermediate builds.

### Rank 3: Optical/Firmware Aperture Table Extraction via Sigfinder
- **Problem**: Extended aperture steps for the ND filter cannot use Ranma's synthetic values without risking exposure calculation errors.
- **Correction**: Enhance `tools/finsig_thumb2.c` to extract Canon's native aperture table from GM1.10C ROM, and generate aperture values calibrated to actual lens steps.
- **Safety**: Tooling only. Offline ROM analysis without camera execution.

### Rank 4: Offline Canon Mode List Symbolic Name Corroboration
- **Problem**: 15 historical scene/creative modes are missing, but their GM1.10C symbolic mapping is unverified.
- **Correction**: Extract the Canon mode string table at `0xFCA90F10` (ref @ `0xFC07317C`) using a dedicated offline parser to correlate Canon internal mode strings with the 35 mode integers.
- **Safety**: Read-only offline script. No firmware modification.

---

### Non-Actionable / Rejected Historical Changes (Do NOT Apply)
- **REJECTED: Importing the 5 historical key names** (`KEY_ZOOM_IN/OUT`, `KEY_ERASE`, `KEY_PRINT`, `KEY_AE_LOCK`) without hardware sampling.
- **REJECTED: Importing synthetic ND aperture entries** (`26..31`), proven to clash with physical aperture steps.
- **REJECTED: Importing 15 unverified scene modes** without symbolic string proof.
- **REJECTED: Arbitrarily toggling `CAM_SUPPORT_BITMAP_RES_CHANGE`** without implementing viewport framebuffer getters and `update_screen_dimensions()`.

---

## 5. Verification & Handoff Summary

- **Deliverables**:
  1. Regression suite: [`tests/test_port7c_platform_validation.py`](../tests/test_port7c_platform_validation.py) (23/23 tests PASS).
  2. Documentation: [`docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md`](PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md).
- **Existing Tests Checked**:
  - `test_port7a_platform_configuration.py`: 18/18 PASS.
  - `test_port7b_reproducibility.py`: 19/19 PASS.
  - `test_port8a_platform_bootstrap.py`: 34/34 PASS.
  - `test_early_boot_literals.py`: 8/8 PASS.
- **Protocol**: Isolated git worktree branched from `origin/main` (`84573f6`), validated against `tools/bootstrap_chdk_platform.py`. All preexisting modifications in main working tree preserved.
- **Hardware Status**: **STRICT NO-GO**.
- **Exact Next Command**:
  ```sh
  python3 -B -m unittest discover -s tests -p test_port7c_platform_validation.py -v
  ```
