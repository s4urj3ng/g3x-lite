# PORT-46 — G3X GM1.10C keymap comparison

Retrieved locally **2026-11-13 UTC**, comparison baseline [16158c6ef08f8f7cfba55a0dec0dd61b69c6382e](https://github.com/s4urj3ng/g3x-lite/commit/16158c6ef08f8f7cfba55a0dec0dd61b69c6382e). The comparison was documentation only; the subsequent opt-in diagnostic implementation is recorded below.

`wN.bN` = zero-based physw word/bit. `C:n` = `chdk-port/platform/g3x/kbd.c:n`; `F:n` = `reference/finsig_gm110c/physw_bits.txt:n`. Siblings appear G7X → G5X → SX60HS; differing assignments are explicit. `keep` retains the current mapping **or omission**.

**VERIFIED:** all 14 current mappings match the generated FINSIG keymap (`reference/finsig_gm110c/stubs_entry.S:57-70`), including the composite shutter; this does not establish hardware behavior. Five FINSIG-only word-0 button entries are listed as historical candidates below. **UNKNOWN:** their GM1.10C physical names; **HISTORICAL_CHDK** names come from `g3x_110e.patch:152-167`, not FINSIG. No unconditional keymap fix is supported.

| key | physw word/bit (current) | physw word/bit (FINSIG) | sibling path:line | label (FINSIG/INFERRED/HISTORICAL_CHDK) | action (keep/fix) |
|---|---|---|---|---|---|
| KEY_SHOOT_FULL | w0.b18+b0, `0x00040001` (C:30) | w0.b18+b0 (F:19 + F:3) | `chdk-port/platform/g7x/kbd.c:35`; `chdk-port/platform/g5x/kbd.c:37`; `chdk-port/platform/sx60hs/kbd.c:30` — same | FINSIG | keep |
| KEY_SHOOT_HALF | w0.b18, `0x00040000` (C:31) | w0.b18, event 0x00 (F:19) | `chdk-port/platform/g7x/kbd.c:36`; `chdk-port/platform/g5x/kbd.c:36`; `chdk-port/platform/sx60hs/kbd.c:31` — same | FINSIG | keep |
| KEY_SHOOT_FULL_ONLY | w0.b0, `0x00000001` (C:32) | w0.b0, event 0x01 (F:3) | `chdk-port/platform/g7x/kbd.c:37`; `chdk-port/platform/g5x/kbd.c:22`; `chdk-port/platform/sx60hs/kbd.c:32` — same | FINSIG | keep |
| KEY_ZOOM_OUT (historical candidate) | absent | w0.b1, `0x00000002`, event **0x16** (F:4); name unknown | `chdk-port/platform/g7x/kbd.c:38` — w0.b1, event **0x04**; `chdk-port/platform/g5x/kbd.c:23` — w0.b1; `chdk-port/platform/sx60hs/kbd.c:48-50` — w2.b3/b4, speed-dependent; its w0.b1 is FRAMING_ASSIST (`chdk-port/platform/sx60hs/kbd.c:44`) | HISTORICAL_CHDK | keep |
| KEY_ZOOM_IN (historical candidate) | absent | w0.b2, `0x00000004`, event **0x12** (F:5); name unknown | `chdk-port/platform/g7x/kbd.c:39` — w0.b2, event **0x03**; `chdk-port/platform/g5x/kbd.c:24` — w0.b2; `chdk-port/platform/sx60hs/kbd.c:51-53` — w2.b1/b2, speed-dependent; its w0.b2 is ZOOM_ASSIST (`chdk-port/platform/sx60hs/kbd.c:45`) | HISTORICAL_CHDK | keep |
| KEY_VIDEO — **ALT toggle option** | w0.b3, `0x00000008` (C:33) | w0.b3, event 0x02 (F:6) | `chdk-port/platform/g7x/kbd.c:40`; `chdk-port/platform/g5x/kbd.c:25`; `chdk-port/platform/sx60hs/kbd.c:33` — same | FINSIG | keep |
| KEY_MENU | w0.b4, `0x00000010` (C:34) | w0.b4, event 0x14 (F:7) | `chdk-port/platform/g7x/kbd.c:41`; `chdk-port/platform/g5x/kbd.c:26`; `chdk-port/platform/sx60hs/kbd.c:34` — same | FINSIG | keep |
| KEY_UP | w0.b5, `0x00000020` (C:35) | w0.b5, event 0x06 (F:8) | `chdk-port/platform/g7x/kbd.c:42`; `chdk-port/platform/g5x/kbd.c:27`; `chdk-port/platform/sx60hs/kbd.c:35` — same | FINSIG | keep |
| KEY_DOWN | w0.b6, `0x00000040` (C:36) | w0.b6, event 0x07 (F:9) | `chdk-port/platform/g7x/kbd.c:43`; `chdk-port/platform/g5x/kbd.c:28`; `chdk-port/platform/sx60hs/kbd.c:36` — same | FINSIG | keep |
| KEY_RIGHT | w0.b7, `0x00000080` (C:37) | w0.b7, event 0x09 (F:10) | `chdk-port/platform/g7x/kbd.c:44`; `chdk-port/platform/g5x/kbd.c:29`; `chdk-port/platform/sx60hs/kbd.c:37` — same | FINSIG | keep |
| KEY_LEFT | w0.b8, `0x00000100` (C:38) | w0.b8, event 0x08 (F:11) | `chdk-port/platform/g7x/kbd.c:45`; `chdk-port/platform/g5x/kbd.c:30`; `chdk-port/platform/sx60hs/kbd.c:38` — same | FINSIG | keep |
| KEY_SET | w0.b9, `0x00000200` (C:39) | w0.b9, event 0x0a (F:12) | `chdk-port/platform/g7x/kbd.c:46`; `chdk-port/platform/g5x/kbd.c:31`; `chdk-port/platform/sx60hs/kbd.c:39` — same | FINSIG | keep |
| KEY_ERASE (historical candidate) | absent | w0.b11, `0x00000800`, event 0x0f (F:13); name unknown | `chdk-port/platform/g7x/kbd.c:47`; `chdk-port/platform/g5x/kbd.c:32`; `chdk-port/platform/sx60hs/kbd.c:40` — all w0.b10, **different** | HISTORICAL_CHDK | keep |
| KEY_DISPLAY — **ALT toggle option** | w0.b12, `0x00001000` (C:40) | w0.b12, event 0x0d (F:14) | `chdk-port/platform/g7x/kbd.c:34-52` — absent; `chdk-port/platform/g5x/kbd.c:38` — w1.b4; `chdk-port/platform/sx60hs/kbd.c:29-56` — absent | FINSIG | keep |
| KEY_WIFI — **ALT toggle, normalized config default** | w0.b13, `0x00002000` (C:41) | w0.b13, event 0x103 (F:15) | `chdk-port/platform/g7x/kbd.c:49` — w0.b16; `chdk-port/platform/g5x/kbd.c:34` — w0.b16; `chdk-port/platform/sx60hs/kbd.c:41` — w0.b13 | FINSIG | keep |
| KEY_PRINT (historical Shortcut candidate; **not a current ALT choice**) | absent | w0.b14, `0x00004000`, event 0x10 (F:16); name unknown | `chdk-port/platform/g7x/kbd.c:34-52` — absent; `chdk-port/platform/g5x/kbd.c:21-40` — absent; `chdk-port/platform/sx60hs/kbd.c:43` — w0.b14 | HISTORICAL_CHDK | keep |
| KEY_PLAYBACK — **ALT toggle option; candidate fallback** | w0.b16, `0x00010000` (C:42) | w0.b16, event 0x101 (F:17) | `chdk-port/platform/g7x/kbd.c:48` — w0.b11; `chdk-port/platform/g5x/kbd.c:33` — w0.b11; `chdk-port/platform/sx60hs/kbd.c:46` — w0.b16 | FINSIG | keep |
| KEY_POWER | w0.b17, `0x00020000` (C:43) | w0.b17, event 0x100 (F:18) | `chdk-port/platform/g7x/kbd.c:50` — commented out; `chdk-port/platform/g5x/kbd.c:35` — mapped; `chdk-port/platform/sx60hs/kbd.c:47` — commented out; all w0.b17 | FINSIG | keep |
| KEY_AE_LOCK (historical candidate) | absent | w0.b28, `0x10000000`, event 0x11 (F:20); name unknown | `chdk-port/platform/g7x/kbd.c:34-52`; `chdk-port/platform/g5x/kbd.c:21-40`; `chdk-port/platform/sx60hs/kbd.c:29-56` — absent in all | HISTORICAL_CHDK | keep |

ALT evidence: `chdk-port/platform/g3x/platform_camera.h:18-20` offers WiFi/Video/Display/Playback. **INFERRED from source:** initial `KEY_PRINT` (`chdk-port/core/conf.c:515`) is invalid and normalization selects first option WiFi (`chdk-port/core/conf.c:69-71`, `chdk-port/core/gui.c:2080-2103`). Playback is assigned only if the candidate sees `conf.alt_mode_button == 0` (`chdk-port/platform/g3x/sub/110c/kbd_candidate.h:218-220`). The owner's saved selection is **UNKNOWN**.

## Masks

- **VERIFIED:** `chdk-port/platform/g3x/platform_kbd.h:8-10` = `0x000533F9 / 0 / 0`. Current keymap unions = `0x000733F9 / 0 / 0`. **MASK0 does not cover every mapped bit:** only Power w0.b17 is missing (`0x00020000`), intentionally excluded by header lines 4-7. All four ALT options are covered. **MASK1 and MASK2 cover every mapped bit:** neither word has mapped keys.
- **Required mask fixes:** none for the existing intentional Power pass-through policy. Literal all-mapped coverage would require MASK0 `0x000733F9` (+b17), changing that policy; do not apply solely to satisfy a union check. Common merge uses only masked bits (`chdk-port/core/kbd_common.c:179-183`).
- **HISTORICAL_CHDK comparison:** G7X masks `0x00050FFF / 0 / 0` (`chdk-port/platform/g7x/platform_kbd.h:5-7`); G5X `0x00050FFF / 0x10 / 0` (`chdk-port/platform/g5x/platform_kbd.h:5-7`) likewise excludes its mapped Power; SX60HS `0x00056FFF / 0 / 0x1E` (`chdk-port/platform/sx60hs/platform_kbd.h:5-8`). Do not copy their erase/display/zoom coverage to G3X.
- **Conditional fixes only if candidate names are established and mappings added:** OR MASK0 with zoom-out `0x2`, zoom-in `0x4`, erase `0x800`, Shortcut `0x4000`, AE-lock `0x10000000`; all five give `0x10057BFF`, still excluding Power. MASK1/2 stay zero. None is justified as a new GM1.10C key by raw event numbers alone; FINSIG's R57 logic expects zoom events 0x03/0x04 (`chdk-port/tools/finsig_thumb2.c:5781-5795`), absent here.

## Evidence manifest

**No ROM read was done (0 ranges, 0 bytes).** Existing FINSIG text supplies every numeric entry used above. Its 50-entry validity warning remains applicable (`F:1`); words 1/2 contain flags/unnamed switches, not additional identified CHDK keys (`F:21-51`), and the trailing `F:52` entry is not promoted to a key. Re-reading raw tuples would not establish missing physical names. The comparison involved no build or hardware operation; subsequent offline builds are recorded below.

Local text identities (SHA-256; retrieved 2026-11-13 UTC; ignored inputs are not claimed to exist in the baseline commit):

```text
6d815485016042c6fa7d856caf2f11154f8c012c75896c9b8e554ac4c4c73d3a  chdk-port/platform/g3x/kbd.c
4c9fd8b4df5d8f45e65827eba5588b6bb2a145765764c0ef0baa85e668f49b24  chdk-port/platform/g3x/platform_kbd.h
b351ce88ff3860573b75086a314ae6ab2ef56dc13ff4a0fc51fd6118811ec78e  reference/finsig_gm110c/physw_bits.txt
f8a4697cb42b48560d430b7f502ff2f6ce5f12a8980fe8c272aba5de18d05166  reference/finsig_gm110c/stubs_entry.S
55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba  g3x_110e.patch
ef3eb91dec34bf307ba54d182d67fe89ec3c4fbac896ffa492698efbcc98951a  chdk-port/platform/g7x/kbd.c
83831a444088eff3bb56a935c085a94b0e839fb562cd7030add9f7b4df0cc5b8  chdk-port/platform/g7x/platform_kbd.h
0d9475de7cb92aefc5a90640abf29d5c4357763fc97b19571e8c8674bc81c750  chdk-port/platform/g5x/kbd.c
270e37e4bb90e9f730c1c107f8c432adc3941810cea5c1d44a005dfc6543b705  chdk-port/platform/g5x/platform_kbd.h
678393584723921092796b4500a1f31eebacb04b2d9719a95727b928ed0afbe6  chdk-port/platform/sx60hs/kbd.c
a33bd1ac8206d4cb47a6b5d934ecf5563db803348484d12a1ba2cb8d8c894dd1  chdk-port/platform/sx60hs/platform_kbd.h
```

FINSIG generation provenance: `reference/finsig_gm110c/README.md:3-10` (2026-11-06 owner output); named current assignments also appear at `reference/finsig_gm110c/stubs_entry.S:54-71`, with its key-name warning retained. Historical provenance is recorded in [PORT-5A](https://github.com/s4urj3ng/g3x-lite/blob/16158c6ef08f8f7cfba55a0dec0dd61b69c6382e/docs/PORT5A_RANMA_PORT_RECOVERY.md); patch lines above establish historical assignments only. No external source was newly fetched. Hardware remains **STRICT NO-GO**.

## Revision validation

The baseline build-suite repair is recorded in [PORT46_BASELINE.md](PORT46_BASELINE.md).

## Opt-in key-check implementation — PORT46-KBD-BUILD-R

Inspected locally **2026-11-13 UTC**, implementation base
[`70accc9ea48d11916f3e9cec027457e0601eb4de`](https://github.com/s4urj3ng/g3x-lite/commit/70accc9ea48d11916f3e9cec027457e0601eb4de).
**VERIFIED:** the table still has **zero unconditional `fix` rows**. Both the
foundation and full-build keymaps remain unchanged. `KEYS_MASK0/1/2` remain
`0x000533F9 / 0 / 0`; Power w0.b17 remains intentionally outside the override
mask. No historical candidate mapping was added.

| Address, bit or hook | Implementation / evidence | Change |
|---|---|---|
| All keymap bits and `KEYS_MASK0/1/2` | Table and Masks section above; `chdk-port/platform/g3x/kbd.c:29-45`, `full_build/g3x/kbd.c:36-52`, `chdk-port/platform/g3x/platform_kbd.h:8-10` | **None**; all `keep` rows retained, including intentional Power pass-through. |
| `physw_status` at `0x00040DAC`; words 0/1/2 at `0x00040DAC/0x00040DB0/0x00040DB4` | **VERIFIED** existing FINSIG base symbol: [`reference/finsig_gm110c/stubs_entry.S:173`](https://github.com/s4urj3ng/g3x-lite/blob/70accc9ea48d11916f3e9cec027457e0601eb4de/reference/finsig_gm110c/stubs_entry.S#L173); **INFERRED** subsequent word addresses from the existing 32-bit array layout. `chdk-port/platform/g3x/kbd_check.h:16-19` uses the symbol, with no literal address. | **No address or bit changed**; three volatile reads per diagnostic draw, no writes. |
| ALT redraw hook | `scripts/build_port43_dbuf.py:352-366` inserts `gui_kbd_check_draw()` immediately after `console_draw(force_redraw)` in staged `core/gui.c:2713`, inside `gui_chdk_draw()`, before DBUF marks the shadow valid. | Added only for `G3X_KBD_CHECK=1`. |
| ALT idle hook | `scripts/build_port43_dbuf.py:368-382` inserts an ALT-only idle branch before `gui_is_module_mode()` in the selected DBUF/NOOVERDRAW scheduler; staged DBUF `core/main.c:355-358`. | Updates held keys, releases and raw words on idle ticks without a full overlay redraw. No diagnostic call in NONE/menu/module idle modes. |
| Draw target and font | `chdk-port/platform/g3x/kbd_check.h:41-48`; existing `draw_string()` → PORT-44 draw/opacity/shadow path; existing GUI_FIX 2x font (`FONT_WIDTH=16`, `FONT_HEIGHT=32`). | Fixed 46-cell white-on-black line, centered at `(82,504)` on the existing 900×600 logical screen; 736×32 pixels within the 880×576 overlay. |

The line is `%-19s %08x %08x %08x`: the decoded CHDK `KEY_*` name (or `none`),
then `physw_status[0]`, `[1]`, `[2]`, in that order. Fixed name padding clears
the previous longer name on release. Decode uses the existing
`kbd_get_pressed_key()` (`chdk-port/core/kbd_common.c:356-366`): active-low
`kbd_new_state`, first matching keymap entry, preserving composite shutter
precedence. The displayed raw hex words are the values currently stored in
`physw_status`, without masking or inversion by the diagnostic. They may
already contain the existing CHDK/Canon keyboard processing overrides
(`chdk-port/core/kbd_common.c:169-183,246-251`); this is not a second hardware
read or an atomic snapshot synchronized with the keyboard task.

**VERIFIED by source and host execution:** the diagnostic returns immediately
outside ALT, before sampling, formatting or drawing. The only new text buffer
is automatic `char line[47]`; names and format are read-only literals. It adds
no static buffer, writable state, boot hook, allocator call, firmware address
change or key bit write. PORT-44's existing lazy shadow allocation on first
overlay entry is retained. Without the opt-in, no diagnostic source or hook
is staged. `legacy_dbuf_snapshot=False` is selected only for this new variant,
so the legacy PORT-43 snapshot remains reproducible while PORT-46 uses the
PORT-44 heap-backed draw layer.

Reproduce offline with the pinned `gcc-arm-none-eabi-5_4-2016q3` toolchain:

```sh
G3X_KBD_CHECK=1 python3 -B scripts/build_port43_dbuf.py --out-dir out/port46-kbd-check
G3X_KBD_CHECK=1 python3 -B scripts/build_port43_dbuf.py --no-overdraw --out-dir out/port46-kbd-check-no-overdraw
python3 -B -m unittest discover -s tests -p test_port46_kbd_check.py -v
```

The CLI also accepts `--kbd-check`. The DBUF builder supplies `G3X_GUI_DBUF=1`
and `G3X_GUI_FIX=1`; both platform makefiles and the diagnostic header reject
KBD_CHECK without DBUF. Each new distribution has a
`port46_kbd_check_manifest.json` with flags, toolchain and all file hashes.
No new manifest pins replace any earlier candidate's expected bytes.

**VERIFIED offline build results:**

| Variant | DISKBOOT.BIN bytes / SHA-256 | `_end` | `gui_kbd_check_draw` linked address (not a ROM hook) |
|---|---|---|---|
| KBD_CHECK + DBUF | 127,233 / `890bc9ddc9152e49a46a95947ca1852e89f0eae62fa128391e5dea1c5f3d43f0` | `0x00369660` | `0x0034EF4C` |
| KBD_CHECK + DBUF + NOOVERDRAW | 127,449 / `7c91eaa622ff0ca44b8d60219da1418ca34dc4a837a6112c39b6bbd31e285798` | `0x00369730` | `0x0034F020` |

Both pass the PORT-44 `_end <= 0x003687B0 + 65536` guard and the no-data/BSS-symbol
over 64 KiB guard. The host harness compiles the actual diagnostic header,
foundation keymap and common decoder; it checks all 14 names, composite shutter
precedence, `none`, release padding, zero/all-one/high-bit hex words, screen
bounds and zero decoder/draw calls with ALT off. The two build checks verify
actual symbols, font dimensions, both draw hooks and unchanged staged keymaps
and masks. Logs are retained under `out/port46-validation/` and
`out/port46-test/` as ignored local artifacts.

**VERIFIED final regression run:** **1,432 tests in 931.138 s, OK (skipped=5)**,
exit status 0 (`out/port46-validation/port-tests.log:5122-5124`). This includes
all four new PORT-46 tests, both opt-in builds, all 19 legacy candidate pins,
default/GUI_FIX/FULL_HOOKS distributions, and PORT-43/44/45 reproducibility,
manifest, memory and draw-layer checks. The new standalone distribution also
matches the separate explicit `--kbd-check` build byte-for-byte. The full run
uses the reproduction harness in [PORT46_BASELINE.md](PORT46_BASELINE.md):
four existing PORT-27 NO-GO skips plus the indirect PORT-19 witness-builder
test skipped as required by `AGENTS.md:45`. Neither forbidden witness builder
nor `tests/test_validate_witness_inspector.py` was run.

The compiled PORT-46 and PORT-44 GUI objects have the same **142 writable
symbol names, types and sizes**, after normalizing compiler-generated local
numeric suffixes (`out/port46-validation/gui-writable-symbols.json`). This
independently confirms that the diagnostic adds no writable static state.
`git diff --check` passes. Changes remain uncommitted for AgentBridge; outputs
and logs remain ignored.

**UNKNOWN:** physical-camera appearance and timing. No camera operations,
deployment, SD writing or new ROM investigation were performed; hardware
remains **STRICT NO-GO**. `PROJECT_STATE.md` and `HANDOFF.md` are intentionally
unchanged under AgentBridge's per-task coordination rule.
