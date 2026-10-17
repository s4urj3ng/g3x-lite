# HDMI-001 independent offline review (Phase 3C close-out)

Reviewed: 2026-10-17 (Asia/Seoul)
Reviewer: Claude (independent senior firmware RE review; did not author Phase 3C)
Inputs: `firmware/dumps/GM1.10C/PRIMARY.BIN` (SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`, re-verified), Phase 3C script/validator/docs as found uncommitted in the worktree.
Method: fresh Capstone 5.0.7 Thumb-2 disassembly plus an independent whole-ROM `BL`/`BLX`/`B.W` cross-reference scan over `0xFC000000..0xFCC9C6F0`. Nothing was executed on the camera; no ROM or SD bytes were modified.

**Verdict: `PASS — READY_FOR_HARDWARE_TEST`** after the fixes below. This means the implementation passed offline review only. Clean HDMI is **not** proven to work, and the restore path is **not** byte-exact (see R1).

## 1. Address verification

| Item | Address | Status | Independent evidence |
|---|---|---|---|
| SCM state base / dirty byte | `0x00015DA4` | **PROVEN** | Only two ROM literals (`0xFC33D500`, `0xFC33D618`), both in `SCM.c`. Byte is touched only by `ORR #2` (`0xFC33D110`), `ORR #3` (`0xFC33D2AA`, `0xFC33D2D4`), `BIC #1` (`0xFC33D2C2`) and cleared to 0 by the push (`0xFC33D30C`). Only bits 0–1 are used, so `Poke8(…,3)` is equivalent to Canon's own `ORR #3`. |
| Init flag | `0x00015DB0` (`+0x0C`) | **PROVEN** | `SCM_Init` `0xFC33D25E: movs r1,#1; str r1,[r2,#0xc]`; checked by `0xFC33D60C`. |
| Active palette index | `0x00015DB4` (`+0x10`) | **PROVEN** (location); value in Live View **UNKNOWN** | `SCM_GetActivePaletteObject` `0xFC33D132 ldr r4,[r5,#0x10]`; written only by `SCM_SetActivePalette` `0xFC33D282` (rejects ≥4). Callers: boot `0xFC0BFC40` (index 0) and the window manager (`0xFC33B7C6`, `0xFC33B83A`) from per-window field `+0x24`. That field is set via `0xFC33B7DA` from 27+ call sites using indices **0, 1 and 2** (and register-valued ones). Which index is active during Rec/Live View with HDMI is not statically proven. |
| Palette pointer | `0x00015DBC` (`+0x18`) | **PROVEN** | `0xFC33D262..66: ldr r1,=0x123140; adds r1,#0x78; str r1,[r2,#0x18]`; read at `0xFC33D14A`. |
| Palette pointer table | `0x001231B8` | **PROVEN** (base); length **UNKNOWN** (≥4 used) | `0x00123140 + 0x78`. **Correction:** the `SCM_Init` loop `0xFC33D26C..7A` initialises the *15 × 8-byte colour-override table at `0x00123140`* (`id=0xFFFF`, `value=0`), **not** 15 pointer slots at `0x001231B8`. The pointer array is never explicitly cleared in `SCM_Init` (assumed BSS-zero). |
| `Palette Class.` magic | `0xFC77B62C` | **PROVEN** | Literal `0xFC19D908`; `PaletteClass_ValidateMagic` `0xFC19D8F2` also rejects NULL and odd pointers. |
| ROM default palette 0 | `0xFC77C8B0` | **PROVEN** | `0xFC77C8AC + idx*0x60C + 4` (`0xFC33D5FA`); flag bytes `0xFC77C8A8..AB` are all 0, so slot = `tbl[active]` with no offset. |
| Object size / entry format | `0x408` B; `+4`: **257** × u32 | **PROVEN** (size) / **CORRECTED** (layout) | Alloc `movw r0,#0x408` (`0xFC19D82C`), copy `movw r2,#0x404` (`0xFC19D846`), Set/GetEntry accept index ≤ `0x100`. `+0x404` is palette entry 256 (ROM `0xFFF7F7F7`), **not a zero footer**. The script touches entries 0–255 only. |
| Alpha encoding | top byte | **PROVEN for ARM-side writers; Zico interpretation INFERRED** | `SCM_SetColorAlpha` `0xFC33D3DC` writes a full 8-bit alpha (`bfi r2,r5,#24,#8`, percent×255/100) and uses `0x00800080` as Canon's own "transparent" value. `0xFC1425FC` uses bits 25:24 for one display LUT path. Alpha 0 is transparent under both interpretations. |
| Push path | `0xFC33D2F0` | **PROVEN**, timing **INFERRED** | Only caller besides boot is `0xFC3809C0`, inside `0xFC3809AE`, gated by `*(0xD264+0x30)==0` and dirty bit 0; reached from VRAM-transfer routine `0xFC380A46`. **Correction:** the previously cited call sites `0xFC380684` and `0xFC380FD6` are not calls to the push. The push happens on the next OSD transfer, not "immediately". |
| `PaletteClass_SendToMzrm` | `0xFC19D800` | **CORRECTED** | Is `adds r0,#4; bx lr` (payload getter). The actual whole-palette send is `0xFC20BF42`; per-entry sends go through `0xFC20BF52` from `PaletteClass_SetEntry` `0xFC19D854`. |
| XIMR/GRYP | Zico blob `0xFCC9C6F0..0xFCDB14E0` | **NOT RE-VERIFIED** | Not needed for the RAM toggle; accepted as documented (E068). |
| Canon Basic eventprocs | System table `0xFC557A84..` | **PROVEN** | Name/pointer pairs (pointer precedes name): `Poke8→0xFC557801→0xFC602428 strb r1,[r0]`, `memset→0xFC5591C9`, `memcpy(dst,src,n)→0xFC13D68D`, `memcmp→0xFC382C01`, `strcmp→0xFC382A19` (standard 0-on-equal). `AllocateMemory`, `FreeMemory`, `sprintf`, `strlen`, `Fopen/Fwrite/Fclose_Fut` present. Canon Basic execution on this camera is proven by the earlier `CBPROBE.TXT`/`CBDUMPER.LOG` outputs. |

## 2. Critical findings

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| R1 | **High** | **ROM restore is not a true restore.** Canon mutates palette 0 at runtime outside the ROM default: `0xFC10C1F0` writes colour IDs `0xB..0xF` (palette indices 86–90) from setting-indexed table `0xFC7B0528` (ROM default is `0xFF000000` for all five); `SCM_SetColorAlpha` (`0xFC33D3DC`, caller `0xFC11DEDE`) rewrites alpha; range writer `0xFC33D4AA`. Copying ROM `0xFC77C8B0` back loses any such state until Canon re-applies it. Previous docs claimed an "exact stock palette" restore — **contradicted**. | Docs corrected; on-screen message changed to `Overlay ROM-restored!`; power cycle documented as the only authoritative restore. Not fixed in code: a same-session restore from `G3XPAL0.BAK` would require unverified `Fread_Fut` semantics. Effect is cosmetic and RAM-only. |
| R2 | **Medium** | **Clean mode is partial by design of the firmware.** After every full push, `0xFC33D1AE` re-applies the 15-entry override table via `PaletteClass_SetEntry`, which also sends each entry to Zico. Theme overrides registered by `0xFC3599DE` map to palette-0 indices 199–202 and 204 (opaque values). `0xFC10C1F0` may re-write 86–90. UI elements drawn with those indices can stay visible after "Overlay disabled". Plausibly explains ranma's residual square on GM1.10E (hypothesis). | Documented as an expected hardware-test observation. No additional RAM writes added (would be speculative). |
| R3 | **Medium** | Heap-object pointer was dereferenced without a range check (a corrupt slot could data-abort in Canon Basic). | **Fixed**: fail-closed `0x1000 ≤ slot < 0x10000000` before reading `*slot` (bound is conservative: lowest DIGIC 6 `MAXRAMADDR` in references is `0x0FFFFFFF`, E028/C009). Alignment is not checked (no verified Canon Basic bitwise/mod syntax); heap allocations and the magic check make a misaligned match implausible. |
| R4 | Medium | Toggle state was inferred from `entry[1]` only. | **Fixed**: "clean" requires entries 1, 2 **and** 3 to be zero (all non-zero in ROM; no known override maps to them — colour IDs `0x1`/`0xF3` map to index 1 but are not registered by any known override path). Any ambiguous state falls to "disable", which is the safe direction. |
| R5 | Medium | Live-View palette index is assumed to be 0 (see §1). | Unresolved statically. Script now logs `*0x00015DB4` to `A/HDMI001.LOG` so the hardware test records which palette was active. If Live View uses index 1/2, the toggle has no visible effect (no harm: palette 0 is still a valid Canon object). |
| R6 | Low | Push not "immediate"; `Poke8` is a non-atomic RMW-free store racing Canon's `ORR/BIC` on the same byte; `memset`/`memcpy` race `PaletteClass_SetEntry`. | Documented. Worst case: a missed/extra push or one stale entry until the next push. |
| R7 | Low | Validator default paths were CWD-relative (the documented absolute-path command fails outside the repo root); it checked snippet presence only, not ordering; docs claimed a literal *allowlist* that did not exist. | **Fixed** (see §3). |
| R8 | Low | Documentation errors: table-zeroing claim, `+0x404` "footer 0", push call sites, `SendToMzrm` label, "immediate" push, "exact" restore, palette 0 "in Rec/Live View" stated as proven. | Corrected here and in the affected docs (C018–C022). |

Historical comparison (GM1.10E `ranma` method): same mechanism (zero palette-0 payload of the active `Palette Class.` object). The GM1.10C script independently re-derives every address, adds firmware/RAM/heap/magic guards, fixes the inverted `strcmp` guard (C017), sets the dirty byte the same way Canon does, and offers an approximate in-place restore. No GM1.10E address is reused.

## 3. Changes made

- `firmware/tools/hdmi001_clean_overlay_gm110c.m` (now 3,186 B, 136 lines, ASCII/LF, SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545`): heap-pointer range guard; 3-entry clean-state detection; read-only diagnostic log `A/HDMI001.LOG` (`st`, active index, slot pointer, entry 1, backup status); restore message `Overlay ROM-restored!`; header states non-exact restore.
- `tools/validate_hdmi001_script.py`: repo-relative defaults; 28 ROM invariants (adds dirty-byte semantics, object size/copy length, entry-256, offset flags, eventproc bindings); hex-literal allowlist; exact `DIM` values; RAM-write call budget (`memset`1/`memcpy`1/`Poke8`2/`Poke16`0/`Poke32`0); guards must precede first write; no writes outside `toggle_palette`; `toggle_palette` gated by `check_compat`. The old script now FAILS (missing range guard).
- `tests/test_validate_hdmi001.py` (new): 20 offline tests, 15 mutation tests run without the ROM; 5 ROM tests auto-skip when the dump is absent.

Results: validator `PASS`; `python3 -m unittest discover -s tests` → 20 passed (15 + 5 skipped without ROM). ROM SHA-256 unchanged.

## 4. Remaining risks

1. Clean HDMI effect unproven; palette index in Live View/HDMI unknown (R5).
2. Partial cleanliness from override re-application (R2).
3. Restore is approximate until power cycle (R1).
4. Canon Basic `*` dereference and implicit locals are accepted from historical scripts, not from this camera; `sprintf`/`AllocateMemory` usage mirrors `extend.m`, which ran successfully.
5. Concurrency races (R6). Zero RAM writes occur if any guard fails, but a data abort in Canon Basic before a guard is theoretically possible only if `0x00015DB0`/`0x00015DBC`/`0x001231B8` themselves are unmapped (they are BSS addresses written by Canon at boot).
6. Nothing persistent: no ROM, flash, property or settings writes. SD writes: `G3XPAL0.BAK` (1,024 B) and `HDMI001.LOG`.

## 5. Hardware-test prerequisites (all required)

1. Explicit owner approval for this exact script SHA-256 `57fcc4ed…1545`.
2. Camera confirmed `GM1.10C` (BLK-01); fully charged battery; card **not** write-locked (backup/log need writes; the toggle still works without them).
3. Script-disk SD card already proven by `cbasic_activation_probe.m`; copy script as `extend.m`, verify SHA-256 on the card.
4. Rear-LCD test first, HDMI second. Power on in Shooting mode (allocates palette 0), then Playback → `FUNC./SET`.
5. Record: on-screen message, `A/HDMI001.LOG` line (`idx` value is the key datum), which UI elements remain, live view intact on LCD and HDMI.
6. Second run → expect `Overlay ROM-restored!`; record any colour/alpha differences vs. stock.
7. Power-cycle and confirm stock UI; compare `G3XPAL0.BAK` to ROM `0xFC77C8B0..0xFC77CCAF` (differences = runtime customisation, see R1).

## 6. Rollback and recovery

- Primary: power off/on (all changes are RAM-only; palette object is re-created from ROM on next boot).
- If the camera hangs: remove battery for ~10 s, reinsert, boot **without** the script card (or with `extend.m` removed).
- In-place: run the script again (ROM restore; approximate).
- To disable script execution permanently: delete `extend.m` or remove the `SCRIPT` VBR marker / `script.req` from the card.
