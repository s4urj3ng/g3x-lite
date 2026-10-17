# Agent handoff
Updated: 2026-10-17
Last agent: Claude (independent HDMI-001 review); previous: Antigravity
Canonical repository (SOLE source of truth): `/Users/avp/project/g3x-lite` (`origin`: `https://github.com/s4urj3ng/g3x-lite`)
Retired backup repository (DO NOT USE): `/Users/avp/Downloads/g3x-lite`
Branch/commit: `main` synchronized with `origin/main` (resolve with `git -C /Users/avp/project/g3x-lite log -1 --oneline`)

## Independent review handoff (2026-10-17, Claude) — `PASS — READY_FOR_HARDWARE_TEST`

- Full report: `docs/HDMI001_INDEPENDENT_REVIEW.md` (E074, C018–C022). Offline only; nothing run on the camera.
- Script revised to SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545` (heap-pointer range guard, entries 1–3 clean-state check, read-only log `A/HDMI001.LOG`, `Overlay ROM-restored!`).
- Validator hardened; new `tests/test_validate_hdmi001.py` (20 tests; ROM tests skip without the dump).
- Key caveats: ROM restore is approximate (power cycle authoritative); Live-View palette index unproven; override re-application may leave some UI visible.

Exact verification command (any CWD):

```sh
python3 /Users/avp/project/g3x-lite/tools/validate_hdmi001_script.py && python3 -m unittest discover -s /Users/avp/project/g3x-lite/tests -v
```

Next: owner decision on hardware test (§5 of the review). No new feature work until directed.

## Prior Phase 3C handoff (`READY_FOR_HARDWARE_TEST`, superseded by the review above)

- **Final Phase 3C HDMI-001 Status**: **`READY_FOR_HARDWARE_TEST`**.
- Built and executed pinned CHDK r5491 `finsig_thumb2` (`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`) in `/tmp/g3x-finsig-build/finsig_thumb2` against `firmware/dumps/GM1.10C/PRIMARY.BIN`, generating `/tmp/g3x-finsig-build/stubs_entry.S` (`E069`).
- Confirmed with two independent static methods (`finsig_thumb2` + full Capstone/Ghidra disassembly of `SCM.c` `0xFC33D10C..0xFC33D616` and `PaletteClass` `0xFC19D800..0xFC19D906`) the exact `GM1.10C` palette architecture (`E069`–`E072`, `C015`–`C017`):
  - `palette_control = 0x00015DA4` (`uint8_t` dirty bitmask; `0x03` triggers `SCM_PushPaletteIfDirty` `0xFC33D2F0`).
  - `palette_init_flag = 0x00015DB0` (`uint32_t`, set to `1` by `SCM_Init` `0xFC33D240`).
  - `active_palette_buffer = 0x00015DB4` (`uint32_t`, active index `0..3`; `0` in Rec/Live View).
  - `palette_buffer_ptr = 0x00015DBC` (`PaletteClass **`, initialized by `SCM_Init` at `0xFC33D262..0xFC33D266` to `0x00123140 + 0x78 = 0x001231B8`).
  - `Palette Class.` heap object (`0x408` B): `+0x00` magic `0xFC77B62C` (`"Palette Class."`), `+0x04` `256 x 4B` `AYCrCb` entries (`bits 25:24` = 2-bit alpha, proven by `DispDev_ConvertPaletteToHwLut` `0xFC1425FC`), `+0x404` footer `0`.
  - ROM default Palette 0 table: `0xFC77C8B0` (`entry[0] = 0x00800080`, `entry[1] = 0xFFFFFFFF`), computed by `SCM_GetRomDefaultPalette` (`0xFC33D5FA`).
- Resolved why `0x00015DBC` was missed by earlier raw 4-byte searches (`C015`), fixed the 1-slot EventProc alignment shift in `tools/ghidra/SeedAndReportOverlay.java` (`C016`), identified the inverted `strcmp("EC385\n\r", 0xfc000584)` bug in `ranma`'s `GM1.10E` script (`C017`), and proved via `ZicoKick_Start` (`0xFC3DFD3C`) why late-ROM GRYP/XIMR strings (`0xFCC9CDD0..0xFCCB9464`) reside in the embedded Zico Xtensa firmware blob copied to `0x80A00000` (`E068`).
- Updated and ran `tools/ghidra/SeedAndReportOverlay.java` and `tools/ghidra/ReportDisplayStringRefs.java` against `analysis-workspace/ghidra/g3x-gm110c-v2`, producing `/tmp/g3x-overlay-report.txt` and `/tmp/g3x-display-string-refs.txt`.
- Produced the five-guard, reversible RAM-only Clean HDMI Canon Basic script [`firmware/tools/hdmi001_clean_overlay_gm110c.m`](file:///Users/avp/project/g3x-lite/firmware/tools/hdmi001_clean_overlay_gm110c.m) (`2,081` B, `93` lines, pure 7-bit ASCII, SHA-256 `33dc57662be62432b09ee8fe45a7132be63519c1cc387951ccfe76d3f85850e7`) and offline validator [`tools/validate_hdmi001_script.py`](file:///Users/avp/project/g3x-lite/tools/validate_hdmi001_script.py) (`status: PASS`, `E073`).
- Updated `docs/HDMI001_OVERLAY_PIPELINE.md`, `docs/HDMI001_CANDIDATES.md`, `docs/GM110C_FUNCTION_MAP.md`, `docs/RESEARCH_LOG.md`, `docs/PROJECT_STATE.md`, and `docs/HANDOFF.md`.
- ROM SHA-256 remained `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`. No camera/SD access, ROM modification, commit, or push occurred.

Exact verification command:

```sh
python3 /Users/avp/project/g3x-lite/tools/validate_hdmi001_script.py && shasum -a 256 /Users/avp/project/g3x-lite/firmware/dumps/GM1.10C/PRIMARY.BIN /Users/avp/project/g3x-lite/firmware/tools/hdmi001_clean_overlay_gm110c.m
```

Next bounded task:
1. Owner review of the Phase 3C HDMI-001 implementation and documentation before committing/pushing.
2. While Mini HDMI hardware is unavailable, transition offline analysis to the next prioritized feature in `docs/GM110C_FUNCTION_MAP.md` §9 (P0 AF Lock / Manual Focus distance control: `SS.DoAFLock` `0xFC558239`, `SS.MFOn` `0xFC558261`, `MoveFocusLensToDistance` `0xFC604851`).

## Prior Phase 3B handoff

- Owner completed installation. Verified Ghidra 12.1.4, Capstone 5.0.6 and Zulu JDK 25; default Java remains Temurin 26 (`E062`).
- Verified ROM hash before and after analysis: `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`.
- Imported Raw Binary into ignored canonical project `analysis-workspace/ghidra/g3x-gm110c-v2` with `ARM:LE:32:v7:default`, base `0xFC000000`, length `0x02000000`, initial auto-analysis disabled (`E063`).
- Added reproducible targeted scripts `tools/ghidra/SeedAndReportHdmi.java` and `ExpandAndReportHdmi.java`. They set bounded Thumb context around verified odd pointers and do not linearly disassemble the ROM.
- Resolved six HDMI procedures and first-level flows. Start/stop wrappers tail-branch to implementations `0xFC57209E` and `0xFC572220`; stop reaches HDMI/CEC and HDMI-core code neighborhoods (`E064`).

## Prior Phase 3 & Phase 2 summary

- Added `docs/GM110C_GHIDRA_SETUP.md`, `docs/GM110C_FUNCTION_MAP.md`, `docs/GM110C_ROM_ANALYSIS.md`, `docs/GM110C_MEMORY_MAP.md`, `tools/find_eventprocs.py`, and `tools/analyze_rom.py` (`E047`–`E058`).
- Prepared `firmware/tools/cbasic_activation_probe.m` as Candidate P1 (`303` B, `13` lines, ASCII, SHA-256 `ffea8a5aa7a5d17e9fc0191c1552b77cc45ae0cdb9dfe7b90b7c908034191ea5`) and `firmware/tools/extend.m` (`2,689` B, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`, `E041`, `E046`).

## Blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, `E037`).
- **BLK-02**: **RESOLVED** — verified local GM1.10C image, 33,554,432 bytes, SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` (`E047`).
- **BLK-03**: `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (`C011`).
- **BLK-04**: Unresolved historical 1080p CHDK live-view crash report on `GM1.10E`; our `GM1.10C` Clean HDMI implementation uses a zero-allocation Canon Basic RAM palette toggle rather than a resident CHDK build.
- **BLK-05**: **RESOLVED for offline ROM analysis and offline script preparation**; hardware execution remains gated on explicit owner approval.
- **BLK-06**: **RESOLVED** — Ghidra 12.1.4, Capstone 5.0.6, and Zulu JDK 25 installed and functional (`E062`).
- **BLK-07**: **RESOLVED** — CHDK r5491 `finsig_thumb2` built and executed against `GM1.10C` (`E069`).
- **BLK-08**: **RESOLVED OFFLINE (`READY_FOR_HARDWARE_TEST`)** — `GM1.10C` `SCM.c` / `Palette Class.` layout, active index, ROM default table, and Zico Mzrm LUT push path verified by two independent static methods (`E069`–`E073`).

## Safety

Continue offline read-only analysis only until hardware testing is explicitly approved by the owner. Do NOT modify the ROM, SD card, or camera; generate boot payloads; execute camera code; update/flash firmware; or commit/upload proprietary bytes.
