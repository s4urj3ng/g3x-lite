# Project state
Updated: 2026-10-17
Canonical repository: `/Users/avp/project/g3x-lite` (`origin`: `https://github.com/s4urj3ng/g3x-lite`; `/Users/avp/Downloads/g3x-lite` is a retired read-only backup)
Phase: 3C — HDMI-001 Clean HDMI overlay/compositor reverse engineering & offline implementation
Status: **PASS — READY_FOR_HARDWARE_TEST** after independent offline review (`docs/HDMI001_INDEPENDENT_REVIEW.md`, E074, C018–C022; offline only — Clean HDMI not proven on hardware; ROM restore is approximate). Prior status note: (all offline reverse engineering, dual-method address confirmation, guarded RAM-only implementation `firmware/tools/hdmi001_clean_overlay_gm110c.m`, and static validation `tools/validate_hdmi001_script.py` complete; no camera execution performed).
Host target: Intel x86_64 Mac, Core i7-9750H, macOS 14.8.9 build `23J631` (E059).
Agents: Codex, Claude Code, Gemini CLI (interchangeable per AGENTS.md protocol).
Reverse tooling: MacPorts Ghidra 12.1.4, Capstone 5.0.6, Zulu JDK 25, and pinned CHDK r5491 `finsig_thumb2` (`/tmp/g3x-finsig-build/finsig_thumb2`) operational (E062, E069). Canonical ignored project: `analysis-workspace/ghidra/g3x-gm110c-v2` (E063).
Camera: Canon PowerShot G3 X; internal firmware **`GM1.10C`**, public firmware **`1.1.0.0`**, Platform ID **`0x32A8` (`12968`)**, `PAL D` (**BLK-01 RESOLVED**, E037; serial number intentionally omitted).
Firmware dump: ACQUIRED / VERIFIED locally at ignored `firmware/dumps/GM1.10C/PRIMARY.BIN`; 33,554,432 bytes; SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` (E047). Never commit or upload it.
CHDK G3 X port: Historical partial `1.10E`/`1.20A` proof of concept verified from author posts; patch attachment 16495 unavailable via guest access and targets `GM1.10E` rather than owner's `GM1.10C` (BLK-03, C011).
Hardware tests: One earlier owner-reported Canon Basic attempt on `GM1.10C` produced no output files and no visible SET response; dump was subsequently acquired and verified (`E047`). No agent camera/SD access occurred during Phase 2/3.

## Decisions

- Owner's “Phase 2: GM1.10C ROM Analysis” and “Phase 3C” instructions authorize offline, read-only binary analysis and offline Clean HDMI script preparation. They do not authorize flashing or unapproved camera execution.
- Preserve the acquired dump byte-for-byte. All generated Ghidra/stub artifacts stay in `/tmp` or ignored `analysis-workspace/`.
- Treat `0xFC004510` as a candidate ARM bootstrap and model ARM/Thumb state from evidence-backed transitions or odd pointers (E049, E053).
- Use GM1.10E only for structural comparison. Both the GM1.10E version-string address (`0xFC54E0B5` vs `0xFC54E08D`) and `ranma`'s inverted `strcmp("EC385\n\r", 0xfc000584)` check (`0xFC00052C` on `GM1.10C`, `C017`) prove addresses must be independently verified on `GM1.10C` (E051, C017).
- Standardized `/Users/avp/project/g3x-lite` (tracking `https://github.com/s4urj3ng/g3x-lite`) as the single source of truth; `/Users/avp/Downloads/g3x-lite` is preserved untouched as a read-only backup.
- Require two independent static confirmations before using any RAM address in a camera script. For HDMI-001, both CHDK `finsig_thumb2` (`E069`) and full Capstone/Ghidra disassembly of `SCM.c` / `PaletteClass` (`E070`–`E072`) confirm `palette_control = 0x00015DA4`, `palette_init_flag = 0x00015DB0`, `active_palette_buffer = 0x00015DB4`, `palette_buffer_ptr = 0x00015DBC` (`-> 0x001231B8`), `Palette Class.` magic `0xFC77B62C`, and ROM default Palette 0 `0xFC77C8B0`.
- Implement HDMI-001 as a five-guard, reversible RAM-only toggle (`firmware/tools/hdmi001_clean_overlay_gm110c.m`) validated offline by `tools/validate_hdmi001_script.py` (`E073`). Do not copy to SD or execute on camera without explicit owner approval.

## Current evidence

- The dump has correct size/hash (`33,554,432` B, SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`), unchanged filesystem metadata during analysis, and is excluded by `firmware/*` (E047).
- In-image identity includes `Firmware Ver GM1.10C` (`0xFC54E080`), `"EC385\n\r"` (`0xFC00052C`), `"gaonisoy"` (`0xFC020004`), DryOS 2.3 release 57, and ARM RVCT 4.0 [Build 902] (E048).
- Pinned CHDK r5491 `finsig_thumb2` (`/tmp/g3x-finsig-build/finsig_thumb2`) independently identifies `palette_control = 0x00015da4`, `active_palette_buffer = 0x00015db4`, `palette_buffer_ptr = 0x00015dbc`, `active_bitmap_buffer = 0x0000d2a4`, `bitmap_buffer = 0x0000d2a8`, `displaytype = 0x00009740`, and `transfer_src_overlay = 0xfc380635` (`E069`).
- Direct disassembly of `SCM.c` (`0xFC33D10C..0xFC33D616`) explains why raw 4-byte search missed `0x00015DBC` (`C015`): ARM RVCT 4.0 loads base `0x00015DA4` from literal pool `0xFC33D500` and accesses `palette_buffer_ptr` at offset `+0x18` (`0xFC33D14A`, `0xFC33D266`), initializing it to `0x00123140 + 0x78 = 0x001231B8` (`E070`).
- `SCM_GetActivePaletteObject` (`0xFC33D12C`) and `PaletteClass_Create` (`0xFC19D828`) lazy-allocate a `0x408`-byte heap object for Palette 0 (`slot = *0x001231B8`) with header magic `0xFC77B62C` (`"Palette Class."`) at `slot + 0x00` and `256 x 4B` `AYCrCb` entries at `slot + 0x04` copied from ROM default `0xFC77C8B0`, reusing the heap object across mode switches (`E070`).
- `DispDev_ConvertPaletteToHwLut` (`0xFC1425FC`) proves bits `25:24` of each `AYCrCb` entry hold 2-bit alpha (`0 -> 0x00` transparent), and `SCM_PushPaletteIfDirty` (`0xFC33D2F0`) pushes `slot + 4` to Zico via `Mzrm_SendPaletteMsg` (`0xFC4C2ABE`, message `0xC8`) whenever `*(uint8_t *)0x00015DA4 != 0` (`E071`).
- `ZicoKick_Start` (`0xFC3DFD3C`) copies ROM `0xFCC9C6F0..0xFCDB14E0` to Zico Xtensa RAM `0x80A00000`, resolving why late-ROM GRYP/XIMR strings (`0xFCC9CDD0..0xFCCB9464`) have no ARM xrefs (`E068`).
- After independent review: `firmware/tools/hdmi001_clean_overlay_gm110c.m` (`3,186` B, `136` lines, ASCII/LF, SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545`) passes the hardened `tools/validate_hdmi001_script.py` (28 ROM invariants, literal allowlist, guard-before-write ordering, RAM-write budget) and `tests/test_validate_hdmi001.py` (20 tests) (`E074`). The original `33dc5766…` script fails the hardened validator (no heap-pointer range guard).
- Review corrections: restore from ROM is not byte-exact (C021); Live-View palette index unproven (C022); overrides re-applied after each push can leave some UI elements visible (E074).

## Open questions / blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, E037).
- **BLK-02**: **RESOLVED** — verified owner-acquired GM1.10C `PRIMARY.BIN` is present locally and Git-ignored (E047).
- **BLK-03**: Historical patch `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (C011); superseded for `GM1.10C` by local `finsig_thumb2` + Ghidra analysis.
- **BLK-04**: Unresolved historical 1080p CHDK live-view crash report on `GM1.10E`; our `GM1.10C` Clean HDMI implementation uses a zero-allocation Canon Basic RAM palette toggle rather than a resident CHDK build.
- **BLK-05**: RESOLVED for offline ROM analysis and offline script development; hardware execution remains gated on explicit owner approval.
- **BLK-06**: **RESOLVED** — Ghidra 12.1.4, Capstone 5.0.6, and Zulu JDK 25 installed and functional (E062).
- **BLK-07**: **RESOLVED** — CHDK r5491 `finsig_thumb2` built and executed against `GM1.10C` (`/tmp/g3x-finsig-build/stubs_entry.S`, `E069`).
- **BLK-08**: **RESOLVED OFFLINE (`READY_FOR_HARDWARE_TEST`)** — `GM1.10C` `SCM.c` / `Palette Class.` layout, active index, ROM default table, and Zico Mzrm LUT push path verified by two independent static methods (`E069`–`E073`).

## Next recommended task

Owner decision on hardware testing of script SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545` per `docs/HDMI001_INDEPENDENT_REVIEW.md` §5 (record `A/HDMI001.LOG`). Do not start another feature until the owner directs. Earlier recommendation retained for reference:


While Mini HDMI hardware is unavailable (or awaiting owner approval for rear-LCD hardware testing of `hdmi001_clean_overlay_gm110c.m`), proceed to offline static analysis of the next prioritized feature in `docs/GM110C_FUNCTION_MAP.md` §9 (P0 AF Lock / Manual Focus distance control around `SS.DoAFLock` `0xFC558239`, `SS.MFOn` `0xFC558261`, and `MoveFocusLensToDistance` `0xFC604851`).
