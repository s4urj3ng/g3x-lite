# PORT-7A — G3 X platform configuration validation

Local retrieval/date: **2026-10-26 (Asia/Seoul)**. Author: Codex, implementation and test engineer under ChatGPT Tech Lead.

**Result:** a source-only correction plan and focused regression suite. One minimal, evidence-supported mask correction is proposed, not applied. The broader PORT-6C historical keymap, scene-mode, aperture and display substitutions are not validated for GM1.10C. Hardware readiness: **STRICT NO-GO**.

## 1. Baseline, classifications and isolation

Main is merged PR #5, **`f8cc7a9743a768351c6e95e80d956f3ee52dbd09`**. Important reproducibility boundary: the four platform configuration inputs are **Git-ignored local source files**, not files supplied by that main commit. The PORT-6C report and historical patch are untracked inputs. Their actual reviewed contents are identified by SHA-256 in §8; the main revision alone cannot reproduce them.

Classification attaches to a precise proposition:

- **VERIFIED for GM1.10C:** a matching constant or static membership is established by an existing GM1.10C-specific evidence record, with its scope stated. Earlier owner observations and independent ROM reviews are attributed evidence; neither is repeated here. Static position/membership does not establish physical override behavior, mode-label semantics or runtime readiness.
- **HISTORICAL REFERENCE ONLY:** a named value/design is supported by Ranma's GM1.10E patch, without sufficient independent GM1.10C evidence for that same proposition.
- **UNKNOWN:** necessary GM1.10C semantics, surface selection, runtime contract or evidence is absent. Agreement between copied source and the historical patch is not independent validation.

Only existing text sources and documentation were inspected. No ROM/dump reads, sigfinder runs, disassembly, display memory access, task/TCM interception, boot/loader edits, firmware build/execution, camera/SD operations, commits, pushes or merges. New Python tests read four ordinary source files and use integer/string checks only. Existing suites can import firmware validators or invoke build-capable tools, so none was run.

Outputs: this report; `tests/test_port7a_platform_configuration.py`; brief protocol entries in PROJECT_STATE/HANDOFF. Platform configuration files, earlier research and other agents' local edits are preserved. A pre-write snapshot records 380 existing files outside these outputs, including protected candidate/inspector artifacts and the four configuration inputs. State/handoff updates are limited to new entries after checking their preimages.

## 2. Keyboard values and exact gaps

### 2.1 All current and historical keymap entries

All rows use word/group **0** in both sources. Current `kbd.c` L29–45 has **14 non-sentinel virtual-key rows**, versus **19** in the patch; the full/half/full-only aliases mean these counts are not counts of distinct physical buttons. The current table covers 13 distinct bits.

Evidence E1 is the earlier independent GM1.10C review (§7); E2 is the owner-result report (§3.1); E3 is the existing generated `110c/physw_bits.txt` text. E3 was read as a recorded artifact, not regenerated or treated as a new ROM investigation. Its warning that 50 printed entries may not all be valid is preserved. Only the already identified button/event and ancillary rows are used.

| Key | Current mask | Historical mask | GM1.10C evidence and exact scope | Classification / disposition |
|---|---|---|---|---|
| `KEY_SHOOT_FULL` | `0x00040001` | `0x00040001` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. Composite half/full-only mask. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_SHOOT_HALF` | `0x00040000` | `0x00040000` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_SHOOT_FULL_ONLY` | `0x00000001` | `0x00000001` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. Alias for the full-only bit. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_ZOOM_OUT` | Absent | `0x00000002` | E3 records event `0x16`, group 0, mask `0x00000002` at `0xFC66C950`. Its physical/CHDK key label here comes from E4 (historical source), not an independent C observation/semantic record. | **HISTORICAL REFERENCE ONLY** for this named key assignment; GM1.10C physical meaning **UNKNOWN**. Do not add. |
| `KEY_ZOOM_IN` | Absent | `0x00000004` | E3 records event `0x12`, group 0, mask `0x00000004` at `0xFC66C958`. Its physical/CHDK key label here comes from E4 (historical source), not an independent C observation/semantic record. | **HISTORICAL REFERENCE ONLY** for this named key assignment; GM1.10C physical meaning **UNKNOWN**. Do not add. |
| `KEY_VIDEO` | `0x00000008` | `0x00000008` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_MENU` | `0x00000010` | `0x00000010` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_UP` | `0x00000020` | `0x00000020` | E2 owner-reported difference; E1 independently recorded switch assignment. Two active runs plus negative control; other observations unrepeated. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_DOWN` | `0x00000040` | `0x00000040` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_RIGHT` | `0x00000080` | `0x00000080` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_LEFT` | `0x00000100` | `0x00000100` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_SET` | `0x00000200` | `0x00000200` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_ERASE` | Absent | `0x00000800` | E3 records event `0xF`, group 0, mask `0x00000800` at `0xFC66C998`. Its physical/CHDK key label here comes from E4 (historical source), not an independent C observation/semantic record. | **HISTORICAL REFERENCE ONLY** for this named key assignment; GM1.10C physical meaning **UNKNOWN**. Do not add. |
| `KEY_DISPLAY` | `0x00001000` | `0x00001000` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_WIFI` | `0x00002000` | `0x00002000` | E2 owner-reported difference; E1 independently recorded switch assignment. | **VERIFIED for GM1.10C**, observed-bit scope only. Retain. |
| `KEY_PRINT` | Absent | `0x00004000` | E3 records event `0x10`, group 0, mask `0x00004000` at `0xFC66C9B0`. Its physical/CHDK key label here comes from E4 (historical source), not an independent C observation/semantic record. | **HISTORICAL REFERENCE ONLY** for this named key assignment; GM1.10C physical meaning **UNKNOWN**. Do not add. |
| `KEY_PLAYBACK` | `0x00010000` | `0x00010000` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_POWER` | `0x00020000` | `0x00020000` | E1 recorded switch-table assignment; E3 corroborates numeric word/bit/event. No dedicated physical-key observation. | **VERIFIED for GM1.10C**, static assignment only; runtime override **UNKNOWN**. Retain. |
| `KEY_AE_LOCK` | Absent | `0x10000000` | E3 records event `0x11`, group 0, mask `0x10000000` at `0xFC66C9D0`. Its physical/CHDK key label here comes from E4 (historical source), not an independent C observation/semantic record. | **HISTORICAL REFERENCE ONLY** for this named key assignment; GM1.10C physical meaning **UNKNOWN**. Do not add. |

The five missing rows are verified **source discrepancies**, not proof of five independently identified missing physical keys. Even though the C-generated event tuples numerically match the E tuples, that alone does not validate the five historical labels or input lifecycle. No new keys are applied.

### 2.2 Three different masks must not be conflated

| Value / location | Exact meaning supported by existing evidence | Classification | Action |
|---|---|---|---|
| `0x000031F8` | OR of eight historically observed C bit differences | VERIFIED for GM1.10C, observed-bit union only | Regression-pin the eight assignments; do not call it a complete override policy. |
| `0x000433F9`, `platform_kbd.h:7` | Current override mask; includes documented SET/shutter bits as well as eight observed bits | VERIFIED current source value; complete override policy UNKNOWN | It excludes both Playback and Power; do not label all included keys hardware-observed. |
| `0x000733F9` | OR of all current `keymap[]` masks | VERIFIED for GM1.10C as source/static arithmetic, not runtime interception | Difference from current override is `0x00030000` (Playback + Power). |
| `0x10077BFF` | E historical override mask; separately reported C quiescent/GetKbdState hardware mask | HISTORICAL REFERENCE ONLY as a proposed full C override policy | A valid-input/baseline mask is not automatically a safe CHDK suppression mask. Do not replace wholesale. |
| `0x000533F9` | Current override plus only C-recorded Playback bit `0x10000` | VERIFIED static derivation for the existing advertised ALT choice | Minimal proposal in §5; preserves current Power exclusion. Physical behavior remains UNKNOWN. |

**Exact verified gap:** `platform_camera.h:19–20` advertises Playback as one of four ALT choices, `kbd.c:42` maps it to bit 16, and `platform_kbd.h:7` excludes that bit. E1 already records the same inconsistency. Existing common CHDK source E6 (`core/kbd_common.c:179–183`) merges modified state only through KEYS_MASK*, so the advertised choice has no suppression coverage through that common mask. This is a static configuration gap; adding coverage neither installs the missing scanner nor proves a usable ALT mode.

ALT names/options currently pair **WiFi/KEY_WIFI**, **Video/KEY_VIDEO**, **Display/KEY_DISPLAY**, **Playback/KEY_PLAYBACK**. The historical list starts with **Shortcut/KEY_PRINT**, then WiFi/Display/Playback. Reinstating Shortcut is **HISTORICAL REFERENCE ONLY**, since KEY_PRINT's C physical assignment is unverified and currently absent. There is no evidence that the existing Video label/key pairing is numerically wrong.

### 2.3 Ancillary constants and comment accuracy

| Constant pair | Current value | Existing independent C evidence | Classification |
|---|---|---|---|
| `SD_READONLY_IDX / SD_READONLY_FLAG` | `1 / 0x20000000` | E1 §7; E3 event `0x20A` | VERIFIED for GM1.10C, recorded static position only |
| `USB_IDX / USB_MASK` | `2 / 0x00800000` | E1 §7; E3 event `0x202` | VERIFIED for GM1.10C, recorded static position only |
| `BATTCOVER_IDX / BATTCOVER_FLAG` | `2 / 0x00400000` | E1 §7; E3 event `0x205` | VERIFIED for GM1.10C, recorded static position only |
| `HOTSHOE_IDX / HOTSHOE_FLAG` | `1 / 0x00001000` | E1 §7; E3 event `0x204` | VERIFIED for GM1.10C, recorded static position only |

Some old source/dossier table-index comments refer to a condensed list and conflict with E3's full table. Full-table positions are: full-only **0**, video **3**, menu **4**, up **5**, down **6**, right **7**, left **8**, SET **9**, display **11**, WiFi **12**, Playback **14**, Power **15**, half-shutter **16**. Numeric masks agree; incorrect index comments do not justify shifting those masks. Correcting the explanatory index comments is text-only work, distinct from proving physical keys. The proposed header comment in §5 removes the blanket hardware-verified label.

## 3. All scene/mode mappings

`shooting.c:108–126` contains **17** current pairs. The historical patch contains **32** pairs, with **15** absent from current source. For the 17 current numbers, E1 §7 and E5 §6 independently record membership in the C **35-value** ROM list. They explicitly do **not** establish the complete name-to-value semantics. This review does not read that ROM list or infer the other 18 values.

| Mode label | Current ID | Historical ID | C numeric membership | Name-to-ID association for C / action |
|---|---|---|---|---|
| `MODE_AUTO` | 32768 | 32768 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_HYBRID_AUTO` | 33298 | 33298 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_P` | 32773 | 32773 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_TV` | 32772 | 32772 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_AV` | 32771 | 32771 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_M` | 32770 | 32770 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_SPORTS` | Absent | 33288 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_CREATIVE_EFFECT` | 33299 | 33299 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_VIDEO_STD` | 2643 | 2643 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_VIDEO_IFRAME_MOVIE` | 2650 | 2650 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_VIDEO_M` | 2651 | 2651 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_VIDEO_SHORT_CLIP` | 2652 | 2652 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_STAR_NIGHTSCAPE` | 16453 | 16453 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_STAR_TRAILS` | 16454 | 16454 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_VIDEO_STAR_TIME_LAPSE` | 16459 | 16459 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_PORTRAIT` | 16406 | 16406 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_SMART_SHUTTER` | Absent | 16949 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_FACE_SELF_TIMER` | Absent | 16948 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_WINK_SELF_TIMER` | Absent | 16950 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_NIGHT_SCENE` | 16953 | 16953 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_SNOW` | Absent | 16414 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_FIREWORK` | 16416 | 16416 | VERIFIED for GM1.10C (recorded membership only) | UNKNOWN semantics; retain existing pair without upgrading its claim |
| `MODE_HDR` | Absent | 8775 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_NOSTALGIC` | Absent | 8753 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_FISHEYE` | Absent | 8759 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_MINIATURE` | Absent | 8760 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_TOY_CAMERA` | Absent | 8763 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_BACKGROUND_DEFOCUS` | Absent | 8764 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_SOFTFOCUS` | Absent | 8765 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_MONOCHROME` | Absent | 8767 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_SUPER_VIVID` | Absent | 8754 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |
| `MODE_POSTER_EFFECT` | Absent | 8755 | UNKNOWN | HISTORICAL REFERENCE ONLY; do not add |

All 17 current IDs agree numerically with their historical counterparts. That is source agreement, not a second independent C semantic validation. No scene label, property transition or camera control is certified by the new tests. The 15-row deficit is confirmed; treating all 15 E pairs as known C corrections is unsupported.

## 4. Display dimensions and related declarative claims

| Source / setting | Current C source | Historical reference / other C evidence | Classification and decision |
|---|---|---|---|
| `platform_camera.h:73–76`: bitmap / logical screen | `736×480 / 720×480` | E4 header: `928×600 / 900×600` | C surface dimensions UNKNOWN. Historical replacements HISTORICAL REFERENCE ONLY; do not apply. |
| E4 dynamic LCD branch | No `update_screen_dimensions()` | Logical `900×600`, buffer width rounded to `928` | HISTORICAL REFERENCE ONLY for selected C LCD geometry; no rendering correction certified. |
| E4 EVF cases 10/11 | No dynamic EVF implementation | `1024×768`, buffer `1024×768`; case 10 marked uncertain, 11 annotated EVF-DC2 | HISTORICAL REFERENCE ONLY; C mode-to-surface contract UNKNOWN. |
| E4 HDMI cases 6/7 | Fixed current dimensions | `960×540`, buffer width `960` | HISTORICAL REFERENCE ONLY for the C HDMI mapping. E1/E5 record `960×540` on one C bitmap-device path: VERIFIED for GM1.10C only for that narrow path, not this surface selection. |
| E4 HDMI/other cases 1/2/8/9 | Fixed current dimensions | `720×480`, rounded buffer `736×480`; only case 8 explicitly called 480p in this group | HISTORICAL REFERENCE ONLY for C display-mode mapping. Matching a current pair does not validate it. |
| E4 other cases 0/3/4/5 | Fixed current dimensions | `640×480`, source comments `?` | HISTORICAL REFERENCE ONLY with uncertain historical interpretation; do not select it for C. |
| Coordinate-versus-buffer arithmetic | `720≤736`, `480≤480` | E4 aligns buffer width to 32; such a rule is not independently proved for the selected C surface | Current containment VERIFIED arithmetic only; actual pitch/format/geometry UNKNOWN. Test containment, not a physical dimension. |
| `CAM_SUPPORT_BITMAP_RES_CHANGE` | Absent/undefined in common defaults | E4 sets 1; common `core/shooting.c:1697` enables update function use | UNKNOWN C implementation contract. A define activates runtime-dependent behavior; do not enable it in a declarative-only plan. |

PORT-6C's asserted inevitable EVF corruption is not a demonstrated C outcome. Its useful verified point is that the source lacks dynamic sizing and has an unvalidated fixed layout. No surface, pixel format, stride or pointer is chosen here; no display memory is accessed.

Other PORT-6C configuration claims:

- **Jogdial:** CAM_HAS_JOGDIAL is undefined in the platform/default headers. E6 uses it to enable calls such as `jogdial_control()`. Historical value 1 is **HISTORICAL REFERENCE ONLY** as an integration recommendation, not a safe stand-alone header correction. No task/interception implementation is added.
- **ND aperture rows:** current table stops at index 25 (`657`, label `11.0`); E4 adds `(26,704,"13.0"), (27,736,"14.0"), (28,768,"16.0"), (29,800,"18.0"), (30,832,"20.0"), (31,864,"22.0")`. These six additions are **HISTORICAL REFERENCE ONLY**. E1 explicitly leaves aperture/ISO calibration unverified on G3 X. ND feature existence does not prove these IDs/APEX values; do not copy them as firmware-independent facts.
- **RAW exclusions:** E4 defines HANDHELD_NIGHT_SCN, HQ_BURST, HYBRID_AUTO, HDR, LOW_LIGHT_MODE and SPORTS exclusions. They are absent locally and undefined in common camera defaults. Their E applicability is **HISTORICAL REFERENCE ONLY**; the correct C exclusion policy is **UNKNOWN**. A historical precaution is not proof of a C crash, buffer corruption or a functioning RAW path. No macros are applied.

## 5. Exact proposed correction and validation boundary

**Proposal only — not applied to platform source.** Add only Playback coverage while retaining the present decision to exclude Power. This is the smallest fix to the advertised-option/mask inconsistency, not adoption of the full keymap union or historical mask. Choosing a general Power-suppression policy is separate and unsupported here.

```diff
--- a/chdk-port/platform/g3x/platform_kbd.h
+++ b/chdk-port/platform/g3x/platform_kbd.h
@@ -4 +4 @@
-// G3X verified key masks based on UI-001B-1 hardware observations
+// GM1.10C override mask: recorded switch bits, including Playback ALT.
@@ -6,2 +6,3 @@
-//         7 (Right), 8 (Left), 9 (Set), 12 (Disp), 13 (Phone), 18 (Shoot Half)
-#define KEYS_MASK0 (0x000433F9)
+//         7 (Right), 8 (Left), 9 (Set), 12 (Disp), 13 (Phone),
+//         16 (Playback), 18 (Shoot Half). Power (bit 17) remains excluded.
+#define KEYS_MASK0 (0x000533F9)
```

Independent support: E1/E5 identify Playback's C static bit and the existing defect; E3 records that bit/event tuple; E6 supplies the common source-level mask contract. PORT-6C/E4 is not the sole evidence for this proposal. New tests validate the resulting ALT-mask relationship in memory. They do not execute C, consume key events or prove that changing this constant alone makes CHDK keyboard integration work.

The remaining requested changes are declarative *in syntax* but not validated corrections: five named key additions, 15 mode pairs, six aperture rows, LCD/EVF dimensions, historical RAW flags and Shortcut selection. The jogdial and dynamic-sizing defines additionally select unavailable runtime dependencies. None is applied.

## 6. Offline regression tests and results

Added **`tests/test_port7a_platform_configuration.py`**, using Python standard library only. It imports no existing firmware validator, uses no subprocess/compiler, opens no ROM or binary artifact and writes no platform file. Required inputs are exactly the four configuration source files. This is a deliberately bounded text reader for the current initializer/define syntax, not a C preprocessor or compilation-equivalence claim.

Coverage:

1. Eight owner-observed key assignments, six recorded static assignments, four ancillary flag/index pairs.
2. Composite shutter bits and full-before-half ordering; override coverage of the eight observed bits; ALT names/options cardinality and mapped-key existence.
3. A marked **expected failure** for current ALT override coverage, plus an in-memory minimal-mask proposal test checking bit `0x10000` is the only addition and Power remains excluded.
4. All 17 current numeric mode IDs against recorded C membership, **without testing their unproved MODE_* labels as facts**.
5. Logical-screen containment in bitmap extents, **without pinning any display dimensions as verified**.
6. Negative controls: missing files; commented/duplicate/nonliteral definitions; swapped/missing observed keys; missing sentinel/duplicate keymap rows; changing logical width to 900 while leaving buffer width 736.

Exact command, already executed locally:

```sh
python3 -B -m unittest discover -s tests -p test_port7a_platform_configuration.py -v
```

**Actual result: Ran 17 tests; 16 passed, 1 expected failure; zero unexpected failures/errors/skips.** The expected failure is the uncorrected Playback ALT-mask gap. `OK (expected failures=1)` must not be reported as all configuration requirements satisfied. When an approved correction is applied, remove that one expected-failure marker and update the baseline-gap diagnostic assertions; unittest otherwise treats an unexpected success as a failure. No correction is applied here.

Reproduction without the default local directory:

```sh
G3X_PLATFORM_DIR=/absolute/path/to/reviewed/g3x-source python3 -B -m unittest discover -s tests -p test_port7a_platform_configuration.py -v
```

Supply the four ordinary source files with §8 identities; no firmware dump, toolchain, candidate ELF or generated physw text is required by the test. Because those inputs are Git-ignored, a public clean clone alone does not contain them. Missing inputs fail closed as errors rather than skips or a misleading PASS. The historical patch is also not a test dependency.

## 7. Exact gaps, deferred evidence and changed files

| Gap | What is verified now | Smallest missing evidence / disposition |
|---|---|---|
| Playback ALT mask | Existing mapped/advertised bit is excluded; minimal static fix checks correctly | Proposed diff only. Actual scanner/lifecycle/override behavior stays UNKNOWN and outside this task. |
| Five extra key names | Five E rows absent in C; raw C tuples exist for their event/bit positions | Independent C physical/logical-name association. Keep labels historical; no new probing or ROM investigation. |
| Fifteen extra modes | Count/set difference 32 versus 17 confirmed | Independent C name-to-ID evidence, plus a complete identified mode list if completeness is asserted. No new ROM read. |
| Current seventeen mode labels | Numeric membership supported by E1/E5 | Matching name semantics, not merely presence in a numeric list. Tests preserve that distinction. |
| Display replacement | Current fixed values and historical dynamic cases differ | Existing applicable C surface-to-display mapping with coordinate units, pitch/format and dimensions. One unrelated bitmap path is insufficient. |
| ND/RAW configuration | Six ND rows and six exclusion flags differ from E | Applicable C calibration/mode/exclusion evidence. Historical model similarity alone is insufficient. |
| Public reproducibility | Config inputs are ignored local text, not the main tree | Supply exact hashed source inputs for review; do not claim a clean clone contains the platform foundation. |

Changed files for PORT-7A:

- `docs/PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md` — this plan, classifications, exact proposed diff, test results and evidence identities.
- `tests/test_port7a_platform_configuration.py` — added source-only checks and explicit known-gap marker.
- `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` — short additive protocol entries, preserving earlier work.

No platform header/C source, boot/loader, hook, candidate or firmware artifact is changed. Final verification: all 380 protected inputs remained byte-identical, HEAD stayed at the merged baseline, and prior state/handoff content was preserved. All 19 key and 32 mode comparison rows were checked; the exact saved diff replayed successfully in memory. Markdown table/whitespace checks passed. Existing unrelated modified/untracked files remain deliberately untouched and all outputs are uncommitted.

Exact next command:

```sh
cat /Users/avp/Project/g3x-lite/docs/PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md
```

## 8. Source register

Local retrieval: **2026-10-26** for every row. Absolute links plus SHA-256 identify the actual inputs; ignored/untracked documents are not attributed to a public commit. No external pages were newly retrieved. E1's earlier ROM/source findings and E2's owner observations are inherited evidence, not new measurements. Earlier cited public-source retrieval dates remain those in the original documents. Exact original historical provenance locator: [G3 X port thread](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump?page=2), post 143437 (2020-05-11), as documented in merged PORT-5A/B; not fetched here.

| ID | Actual input and SHA-256 | What it proves here |
|---|---|---|
| E0 | [docs/PORT6C_CHDK_INTEGRATION_GAPS.md](/Users/avp/Project/g3x-lite/docs/PORT6C_CHDK_INTEGRATION_GAPS.md); `b4db02047487eed4f8cb910960fb9e2f9d088ebf1a8c530149c9860f1495526a` | Assigned source-comparison claims and proposed historical values, not independently established C semantics. |
| E1 | [docs/CHDK_PORT0_CODEX_REVIEW.md](/Users/avp/Project/g3x-lite/docs/CHDK_PORT0_CODEX_REVIEW.md); `b26c0ca791d8f152d55e8815b146cf838c27dd7bb5742cacf2f9f61535e9a78e` | Existing independent C switch assignments/ancillary flags; 17 mode-ID membership, not complete semantics; display and aperture qualifications. |
| E2 | [docs/UI001B1_HARDWARE_RESULT.md](/Users/avp/Project/g3x-lite/docs/UI001B1_HARDWARE_RESULT.md); `8359dd1ecfff480660b71dafec1a7a19c7920e261ac19062a2601bad8ac47cb3` | Attributed 2026-10-18 owner reports for eight bit differences, including observation-count limitations. |
| E3 | [chdk-port/platform/g3x/sub/110c/physw_bits.txt](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/sub/110c/physw_bits.txt); `b351ce88ff3860573b75086a314ae6ab2ef56dc13ff4a0fc51fd6118811ec78e` | Previously generated C switch tuple text; no new extraction and no physical-label proof for five missing names. |
| E4 | [g3x_110e.patch](/Users/avp/Project/g3x-lite/g3x_110e.patch); `55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba` | 336,714-byte historical source; r5480 base from PORT-5B. Text-only comparison, not applied or built. |
| E5 | [docs/CHDK_PORT0C_CODEX_INCREMENTAL_REVIEW.md](/Users/avp/Project/g3x-lite/docs/CHDK_PORT0C_CODEX_INCREMENTAL_REVIEW.md); `eda427a353dc119190642a64c46db28d0b98c0ef76eccbf6ab5c38a4bd9721b0` | Earlier independent qualifications for key mask, dimension path, mode membership and calibration. |
| E6 | [chdk-port/core/kbd_common.c](/Users/avp/Project/g3x-lite/chdk-port/core/kbd_common.c); `449e3139874653dad1696b6d1b8c90691c1d0c8ba7de714933c1a0a8b8e8648a` | Actual local common source: override mask contract and jogdial conditional dependency; not executed. |
| E7 | [chdk-port/platform/g3x/platform_camera.h](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/platform_camera.h); `0fed491abe86c069166c4aadc50eceec81dd0da835943049e03b370fede9f6ac` | Current ALT choices, dimensions and flags; ignored local source, not main-commit content. |
| E8 | [chdk-port/platform/g3x/platform_kbd.h](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/platform_kbd.h); `4d2594313c304ffb6598d47cfc9cd4bbffd0f3b1b64d35e734df8e8218d459b0` | Current override masks and ancillary definitions; ignored local source. |
| E9 | [chdk-port/platform/g3x/kbd.c](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/kbd.c); `ff4d62afd1d98cd22b6369eac0dde539b19a2dec2a44a255c9251c4272eed0ce` | Current fourteen-row map and inactive scanner integration; ignored local source. |
| E10 | [chdk-port/platform/g3x/shooting.c](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/shooting.c); `005eecdb840eeab16b16ef251fa8428653eabf34c8ee29a20cccb03f48af9b96` | Current seventeen-row mode map and aperture table; ignored local source. |
| E11 | [chdk-port/include/camera.h](/Users/avp/Project/g3x-lite/chdk-port/include/camera.h); `e84b9bd11da47ea217016cea20f3d7aa16b456982ad9557af3a245c66f019dee` | Common default undefined flags; no compiler/preprocessor run. |
| E12 | [chdk-port/core/shooting.c](/Users/avp/Project/g3x-lite/chdk-port/core/shooting.c); `b041e9b56d78d3696352e2aebb115bd38663d580845a68079651162e91faf9a6` | Existing runtime-dependent use of resolution-change flag; inspected as text only. |

Baseline locator: [merged PR #5 commit](https://github.com/s4urj3ng/g3x-lite/commit/f8cc7a9743a768351c6e95e80d956f3ee52dbd09). Historical provenance and scope: [PORT-5B at that revision](https://github.com/s4urj3ng/g3x-lite/blob/f8cc7a9743a768351c6e95e80d956f3ee52dbd09/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md). These locators do not imply that ignored platform files or new reports are in that commit.

**Hardware readiness: STRICT NO-GO.** Passing source checks or accepting the minimal declarative proposal supplies no boot, input-hook, display, capture or runtime approval.
