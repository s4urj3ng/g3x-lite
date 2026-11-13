# PORT-46 — G3X GM1.10C keymap comparison

Retrieved locally **2026-11-13 UTC**, baseline [16158c6ef08f8f7cfba55a0dec0dd61b69c6382e](https://github.com/s4urj3ng/g3x-lite/commit/16158c6ef08f8f7cfba55a0dec0dd61b69c6382e). Documentation only; no source changes.

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

**No ROM read was done (0 ranges, 0 bytes).** Existing FINSIG text supplies every numeric entry used above. Its 50-entry validity warning remains applicable (`F:1`); words 1/2 contain flags/unnamed switches, not additional identified CHDK keys (`F:21-51`), and the trailing `F:52` entry is not promoted to a key. Re-reading raw tuples would not establish missing physical names. No build or hardware operation was performed.

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

Build-suite failures are tracked in PORT46-BASELINE-FIX.
