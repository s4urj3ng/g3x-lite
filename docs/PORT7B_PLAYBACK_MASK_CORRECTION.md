# PORT-7B — Playback ALT override mask correction

Local date: **2026-10-26**. Author: Claude (primary researcher / implementation agent) under ChatGPT Tech Lead. Follows [PORT-7A](PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md) §2.2 and §5.

**Result:** `KEYS_MASK0` changed from `0x000433F9` to `0x000533F9` in `chdk-port/platform/g3x/platform_kbd.h`. Only bit 16 (`0x00010000`, Playback) is added; Power (bit 17) stays excluded. The PORT-7A expected failure is now a normal passing test. Nothing was built, executed or committed. **Hardware readiness: STRICT NO-GO.**

Labels: **VERIFIED** = established by an existing GM1.10C evidence record or by arithmetic on the current source; **INFERRED** = a reasoned conclusion that no record states directly; **UNKNOWN** = not established.

## 1. Why the previous mask was `0x000433F9`

| # | Finding | Label |
|---|---|---|
| 1.1 | `0x000433F9` is exactly the OR of bits {0, 3, 4, 5, 6, 7, 8, 9, 12, 13, 18}. Recomputed here: `sum(1<<b) = 0x433F9`. | VERIFIED (arithmetic) |
| 1.2 | That bit list was written down in [CHDK_G3X_KEYBOARD_MAPPING.md](CHDK_G3X_KEYBOARD_MAPPING.md) §4.1 (`// Mask union: 0x40000 \| 0x2000 \| … \| 0x1 = 0x000433F9`) and copied into `platform_kbd.h` L4–7 with the label "verified key masks based on UI-001B-1 hardware observations". [CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md](CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md) §2 calls it the "Union of all 11 mapped buttons". | VERIFIED (source/document text) |
| 1.3 | The 11 bits are the 8 UI-001B-1 hardware-observed bits (`0x000031F8`) plus the three bits that the dossier table lists right after them: SET (9), Shoot Full (0) and Shoot Half (18). Playback (16) and Power (17), the last two rows of that table, were left out. | VERIFIED (document structure) |
| 1.4 | The selection rule was not applied consistently. SET, Shoot Full and Shoot Half have the same status as Playback and Power: "ROM-evidenced / not yet verified on hardware" (dossier §3; [UI001B1_HARDWARE_RESULT.md](UI001B1_HARDWARE_RESULT.md) §5 item 3). So neither "hardware verified" nor "all mapped keys" explains the exclusion of bit 16. No document states a reason for excluding Playback. | VERIFIED (that no stated reason exists in the reviewed docs); the origin is most likely the 11-row prefix from 1.3, not a deliberate decision — INFERRED |
| 1.5 | The 14-row `keymap[]` in `kbd.c` was later written with Playback and Power. Its union is `0x000733F9`, so the gap is `0x00030000`. [CHDK_PORT0_CODEX_REVIEW.md](CHDK_PORT0_CODEX_REVIEW.md) §7 and [CHDK_PORT0C_CODEX_INCREMENTAL_REVIEW.md](CHDK_PORT0C_CODEX_INCREMENTAL_REVIEW.md) L70/L264 already flagged the gap. They said excluding Power "can be intentional", but excluding Playback is a defect because it is an advertised ALT key. | VERIFIED |

## 2. Is `0x000533F9` supported?

| # | Evidence | What it shows | Label |
|---|---|---|---|
| 2.1 | `sub/110c/physw_bits.txt` (generated dump of the ROM table at `0xFC66C948`), row `0xfc66c9b8 0x01010210 0x00000101 0 0x00010000`. Decoded independently with `word = (info>>5)&7 = 0` and `bit = info&31 = 16`. Event `0x101`. | Word 0, bit 16 belongs to a switch with event `0x101`. | VERIFIED (static ROM table entry, as recorded) |
| 2.2 | Same dump, row `0xfc66c9c0 0x01010211 0x00000100 0 0x00020000`: word 0, bit 17, event `0x100`. | Power is a different bit and is not touched. | VERIFIED |
| 2.3 | [CHDK_G3X_KEYBOARD_MAPPING.md](CHDK_G3X_KEYBOARD_MAPPING.md) §3 row PLAYBACK: bit 16, event `0x0101`, `KEY_PLAYBACK`, "ROM-EVIDENCED (UNVERIFIED ON HARDWARE)". `kbd.c:42` maps `KEY_PLAYBACK` to `0x00010000`, and the PORT-7A test pins this as a recorded static assignment. | The doc, the source and the ROM dump agree on the numeric mapping. | VERIFIED (numeric agreement) |
| 2.4 | `platform_camera.h:19–20` advertises `"Playback"/KEY_PLAYBACK` as one of four ALT choices. | An ALT key must be covered by `KEYS_MASK0` to be suppressible. | VERIFIED |
| 2.5 | `chdk-port/core/kbd_common.c:179` merges `kbd_mod_state` into `physw_status` only through `KEYS_MASK0`. L324 (`kbd_key_release_all`) restores only `KEYS_MASK0` bits. L35 documents the masks as "keys used by CHDK in alt mode". | Without bit 16, a Playback ALT press or a scripted `KEY_PLAYBACK` press cannot reach or be suppressed in `physw_status`. | VERIFIED (source text; not executed) |
| 2.6 | UI-001B-1 hardware: quiescent `K0 = 0x10077BFF`, in which bit 16 is 1 (and so is bit 17). [UI001B1_HARDWARE_RESULT.md](UI001B1_HARDWARE_RESULT.md) §5 lists Playback as "Not Yet Verified (hypothesized `0x00010000`)". | The released level of bit 16 matches the active-low convention of the eight observed keys. Playback itself was never pressed or sampled. | Released level VERIFIED; the physical Playback press at bit 16 is UNKNOWN (only INFERRED from the ROM entry and the 8-for-8 match of the observed keys) |
| 2.7 | [CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md](CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md) §2 lists 11 keys and leaves Playback out. Its "ROM Table" address column does not match `physw_bits.txt`. For example, `0xFC66C9B8` is listed for `KEY_DISP`, but in the dump it is the Playback entry, and DISP is at `0xFC66C9A0`. | This audit neither supports nor contradicts bit 16. Its address column is unreliable, so it is not used here. | VERIFIED (the inconsistency); see §5 follow-up |

**Conclusion:** the bit-16 assignment of `KEY_PLAYBACK` is backed by GM1.10C evidence that does not depend on the historical patch (2.1, 2.3). The need for override coverage follows from the advertised ALT option and the common mask contract (2.4, 2.5). `0x000533F9 = 0x000433F9 | 0x00010000` is the smallest change that closes the gap. → Correction **justified at the static source level**. No `g3x_110e.patch` value was used.

## 3. Conflict check for bit 16

| Check | Result | Label |
|---|---|---|
| Other word-0 `keymap[]` rows that include `0x10000` | None. The 13 other rows are `0x40001, 0x40000, 0x1, 0x8, 0x10, 0x20, 0x40, 0x80, 0x100, 0x200, 0x1000, 0x2000, 0x20000`. | VERIFIED |
| Historical-only key names (Zoom In/Out `0x4`/`0x2`, Erase `0x800`, Print `0x4000`, AE Lock `0x10000000`) | None uses bit 16. None was added. | VERIFIED |
| Other word-0 entries in the ROM table with bit 16 | Only `0xFC66C9B8` (event `0x101`). The table entries from `0xFC66C9D8` onward are words 1/2. | VERIFIED (dump as recorded) |
| Word 1 has a bit-16 entry (`0xfc66ca40`, event `0x300`) | That is a different word. `KEYS_MASK1` stays `0` and is not affected. | VERIFIED |
| Ancillary flags (SD `1/0x20000000`, USB `2/0x00800000`, BATTCOVER `2/0x00400000`, HOTSHOE `1/0x00001000`) | All are in words 1/2. No overlap. | VERIFIED |
| Power exclusion still holds | `0x000533F9 & 0x00020000 = 0`. A test pins this. | VERIFIED |

## 4. Source diff

`chdk-port/platform/g3x/platform_kbd.h` (this file is **Git-ignored** by `.gitignore:43` and has never been tracked, so `git diff` does not show the change). The tracked form of this change is [patches/0002-port7b-keys-mask0.patch](../patches/0002-port7b-keys-mask0.patch). It uses paths relative to `chdk-port/`, as `0001` does. Applying it to the preimage reproduces the postimage hash below.

```diff
-// G3X verified key masks based on UI-001B-1 hardware observations
+// GM1.10C override mask: recorded switch bits, including Playback ALT.
 // Port 0: bits 0 (Shoot Full), 3 (Video), 4 (Menu), 5 (Up), 6 (Down),
-//         7 (Right), 8 (Left), 9 (Set), 12 (Disp), 13 (Phone), 18 (Shoot Half)
-#define KEYS_MASK0 (0x000433F9)
+//         7 (Right), 8 (Left), 9 (Set), 12 (Disp), 13 (Phone),
+//         16 (Playback), 18 (Shoot Half). Power (bit 17) remains excluded.
+#define KEYS_MASK0 (0x000533F9)
```

The comment change is the wording PORT-7A §5 proposed. It removes the inaccurate "verified … hardware observations" label (see 1.4). `KEYS_MASK1/2`, the ancillary flags, `kbd.c`, `platform_camera.h`, boot/loader code, hooks and stubs are unchanged.

`tests/test_port7a_platform_configuration.py` (untracked):
- Removed `@unittest.expectedFailure`. Renamed the coverage test to `test_alt_options_have_override_coverage`; it is now a normal test.
- Replaced the in-memory proposal test with `test_playback_correction_is_minimal_and_excludes_power`. This test pins `(0x000533F9, 0, 0)`, requires that the only difference from `0x000433F9` is `KEY_PLAYBACK`'s recorded bit, and requires the Power bit to stay excluded.
- Added `test_previous_mask_reproduces_playback_gap`. This test confirms that the old mask still yields exactly the `{KEY_PLAYBACK: 0x10000}` gap.
- Updated the docstring to match.

File identities after the edit (SHA-256): `platform_kbd.h` `4c9fd8b4df5d8f45e65827eba5588b6bb2a145765764c0ef0baa85e668f49b24` (before: `4d2594313c…d459b0`, matching PORT-7A E8). Test `69e2fe9fbeb9a364e3be045a763e20408766a1f5ae27fcbe596a5da3b54cc6b7` (before: `619e4a41…a5d1`). `kbd.c`, `platform_camera.h`, `shooting.c` and `physw_bits.txt` still match the PORT-7A §8 hashes.

## 5. Verification summary

```sh
python3 -B -m unittest discover -s tests -p test_port7a_platform_configuration.py -v
```

- **Corrected source:** `Ran 18 tests … OK`, with 0 failures, 0 errors, 0 skips and 0 expected failures.
- **Negative control:** the same suite, run with `G3X_PLATFORM_DIR` pointing at a scratch copy that holds the *original* `platform_kbd.h`, gives `FAILED (failures=2)`: `test_alt_options_have_override_coverage` and `test_playback_correction_is_minimal_and_excludes_power`. The tests therefore distinguish the two masks.
- No other suite was run, because the other suites can import firmware validators or build tools. Nothing was compiled or built. No ROM, dump or binary was read. The only input outside the platform sources was the existing `physw_bits.txt` text.

### What remains UNKNOWN

- Whether the physical Playback button actually toggles bit 16. It was never sampled, so a dedicated press observation is needed. That step is a hardware action and requires approval.
- Runtime override behaviour. `mykbd_task` / `task_PhySw` interception is still not implemented (`kbd.c:47–49`), so this mask has no runtime effect yet.
- Whether excluding Power is the right final policy. This change keeps the existing exclusion and does not decide it.

### Follow-ups (not done here)

- The address column of the [CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md](CHDK_PORT0B_KEYBOARD_DISPLAY_AUDIT.md) §2 table conflicts with `physw_bits.txt` (see 2.7). The table-index comments in `kbd.c` are also wrong (PORT-7A §2.3). Both are text-only fixes.
- PROJECT_STATE/HANDOFF were not updated: they have uncommitted edits from other agents, and the task scope limited the outputs to the files above.

**Hardware readiness: STRICT NO-GO.**
