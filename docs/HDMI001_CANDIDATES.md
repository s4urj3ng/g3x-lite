# HDMI-001 static candidates

> **Independent review 2026-10-17 (`docs/HDMI001_INDEPENDENT_REVIEW.md`, C018–C022):** statements below about a 15-slot table zeroed at `0x001231B8`, a zero footer at `+0x404`, push call sites `0xFC380684`/`0xFC380FD6`, `PaletteClass_SendToMzrm` sending the palette, an *immediate* push, an *exact* ROM restore, and palette 0 being proven active in Rec/Live View are corrected there. The script was revised (range guard, 3-entry state check, diagnostic log); current SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545`.

Updated: 2026-10-17  
Scope: GM1.10C read-only static analysis and completed offline Clean HDMI candidate selection (`READY_FOR_HARDWARE_TEST`)

## Result

Phase 3C offline analysis of `GM1.10C` resolved the complete overlay/palette composition pipeline and verified the primary reversible RAM-only suppression target with two independent static methods (`finsig_thumb2` signature matching and Capstone/Ghidra disassembly of `SCM.c`, `PaletteClass`, `VramTransferManager.c`, `DispDev_ConvertPaletteToHwLut`, and `XimrExe`):

1. **Selected Candidate 1 (IMPLEMENTED OFFLINE — `READY_FOR_HARDWARE_TEST`)**:
   - **Target**: Active `Palette Class.` heap object for Palette 0 (`slot = *(0x001231B8)` pointed to by `palette_buffer_ptr = 0x00015DBC` in the `SCM.c` state struct at `0x00015DA4`).
   - **Mechanism**: Verify 5 runtime guards (`"gaonisoy"`, `"EC385\n\r"`, `"GM1.10C"`, `palette_init_flag == 1` at `0x00015DB0`, `palette_buffer_ptr == 0x001231B8` at `0x00015DBC`, and `*slot == 0xFC77B62C` `"Palette Class."`), back up `1024` bytes at `slot + 4` to `A/G3XPAL0.BAK`, zero `1024` bytes (`256 x 4B` `AYCrCb` entries, setting 2-bit alpha in bits `25:24` to `0`), and poke `palette_control` (`*(uint8_t *)0x00015DA4 = 3`) so `SCM_PushPaletteIfDirty` (`0xFC33D2F0`) immediately pushes the transparent LUT via `Mzrm_SendPaletteMsg` (`0xFC4C2ABE`, message `0xC8`) to the Zico compositor.
   - **Reversibility**: Running the script a second time copies `1024` bytes from the verified ROM default Palette 0 table (`0xFC77C8B0`) back to `slot + 4` and pokes `palette_control = 3`, restoring the ROM-default overlay in place (approximate; power cycle is authoritative, C021). Power-off also restores stock state because all edits are RAM-only.
   - **Artifact**: [`firmware/tools/hdmi001_clean_overlay_gm110c.m`](file:///Users/avp/project/g3x-lite/firmware/tools/hdmi001_clean_overlay_gm110c.m) (`3,186` B, SHA-256 `57fcc4ed493a4f6c611336c3530867452ef60b1ac4f95d2dfaa86d2ee31b1545`), validated by [`tools/validate_hdmi001_script.py`](file:///Users/avp/project/g3x-lite/tools/validate_hdmi001_script.py).

2. **Why `0x00015DBC` was previously marked unresolved (`C015`)**:
   - Earlier raw 4-byte word searches looked for `0x00015DBC` verbatim in `GM1.10C` ROM. In fact, ARM RVCT 4.0 loads the `SCM.c` struct base `0x00015DA4` from literal pool `0xFC33D500` and accesses `palette_buffer_ptr` via struct offset `+0x18` (`0xFC33D14A: ldr r1, [r4, #0x18]`, `0xFC33D266: str r0, [r4, #0x18]`).

3. **Corrected EventProc table alignment for VRAM/palette diagnostic functions (`C016`)**:
   - Earlier table seeds had a 1-slot shift in the `0xFC558578..` EventProc table. Direct table verification and `finsig_thumb2` confirm:
     - `SaveBmpVRAMData`: **`0xFC558349`** (Thumb entry `0xFC558348`, calls `SavePaletteData` at `0xFC558432`)
     - `SavePaletteData`: **`0xFC5584E9`** (Thumb entry `0xFC5584E8`)
     - `GetVRAMHPixelsSize`: **`0xFC0D360B`** (Thumb entry `0xFC0D360A`, reads `*(uint16_t *)(*(0x000083DC) + 0x18)`)
     - `GetVRAMVPixelsSize`: **`0xFC0D3613`** (Thumb entry `0xFC0D3612`, reads `*(uint16_t *)(*(0x000083DC) + 0x1A)`)

See [`docs/HDMI001_OVERLAY_PIPELINE.md`](file:///Users/avp/project/g3x-lite/docs/HDMI001_OVERLAY_PIPELINE.md) for the complete architecture, disassembly trace, and hardware test checklist.

## Phase 3C candidate ranking (final)

| Rank | Candidate | GM1.10C Address(es) | Status | Assessment |
|---:|---|---|---|---|
| **1** | **Active `Palette Class.` Palette 0 transparency + dirty-bit push (`SCM.c`)** | `0x00015DA4` (`palette_control`), `0x00015DB0` (`palette_init_flag`), `0x00015DBC` (`palette_buffer_ptr` -> `0x001231B8`), `0xFC77B62C` (magic), `0xFC77C8B0` (ROM default) | **VERIFIED & IMPLEMENTED OFFLINE (`READY_FOR_HARDWARE_TEST`)** | Confirmed by both `finsig_thumb2` and full `SCM.c` / `PaletteClass` disassembly. Reversible in-place via ROM `0xFC77C8B0` copy or reboot. |
| **2** | **`VramTransferManager.c` overlay transfer suppression (`transfer_src_overlay`)** | `0xFC380634` (ROM), `0x0000D2A4` (`active_bitmap_buffer`), `0x0000D2A8` (`bitmap_buffer`) | **VERIFIED BACKUP CANDIDATE (requires code hook)** | Confirmed by `finsig_thumb2` and disassembly (`0xFC380550..0xFC38142C`). Useful in a later CHDK RAM task-hook phase if residual non-palette elements need suppression, but not needed for a minimal Canon Basic RAM-data toggle. |
| **3** | **ARM `XimrExe` descriptor layer suppression (`MzrmGraphic`)** | `0xFC20C6D0` (ROM), `0x0001A438` (RAM descriptor) | **MAPPED / SECONDARY** | Builds the XIMR composition struct at `0x0001A438` and sends Mzrm RPC `0x24`/`0x25` (`0xFC20BE22`) to Zico (`0x80A00000`). Higher risk than palette transparency if mutated without hooking `XimrExe`. |
| **4** | **`SaveBmpVRAMData` (`0xFC558348`) / `SavePaletteData` (`0xFC5584E8`)** | `0xFC558348`, `0xFC5584E8` (ROM) | **REJECTED FOR SUPPRESSION** | Confirmed diagnostic SD file-dump routines (`SaveBmpVRAMData` writes bitmap VRAM and calls `SavePaletteData`). |
| **5** | **Continuous VRAM capture APIs (`GetContinuousVRAMData`, etc.)** | `0xFC612FA4`, `0xFC6134A8`, `0xFC613506` (ROM) | **REJECTED FOR SUPPRESSION** | Synchronized diagnostic capture wrappers using context global `0x00035E80`; not part of live display composition. |
| **6** | **HDMI transport lifecycle (`StartDisplayHDMIForFAMode`, `SetVideoOutType`, etc.)** | `0xFC5720D8`, `0xFC57226E`, `0xFC612C38`, `0xFC612978`, `0xFC613ABC`, `0xFC2B4FE8` | **TRANSPORT OBSERVABILITY ONLY** | Deliberately excluded from Clean HDMI overlay suppression so HDMI video signal negotiation and transport remain untouched. |

## Clean-HDMI independence assessment

### Confirmed

- The `SCM.c` (`0xFC33D10C..0xFC33D616`), `PaletteClass` (`0xFC19D800..0xFC19D906`), `MakeOsdVram.c` (`0xFC183824..0xFC183B7B`), `BmpDev.c` (`0xFC18347E..0xFC1837E7`), and `VramTransferManager.c` (`0xFC380550..0xFC38142C`) call graphs have **zero cross-calls** to the mapped AF/MF (`SS.DoAFLock`, `SS.MFOn`, `MoveFocusLensToDistance`), AE (`SS.DoAELock`), or shutter (`ShutterTool.*`, `OpenMShutter`/`CloseMShutter`) subsystems.
- Modifying the 256 `AYCrCb` palette entries at `(*(*0x00015DBC)) + 4` and setting `*(uint8_t *)0x00015DA4 = 3` alters only the alpha/color lookup table sent to the Zico compositor (`Mzrm` message `0xC8`) and UI color queries (`PaletteClass_GetEntry` `0xFC19D8CA`). It does not alter HDMI mode negotiation, sensor readout, AF state machines, or exposure calculation.

### Operational caveats for hardware testing

- Because the rear LCD and HDMI output share Palette 0 in Rec/Live View mode, Canon menus and on-screen indicators that use Palette 0 will also become transparent until the script is run a second time (putting `1024` bytes from `0xFC77C8B0` back into `slot + 4`) or the camera is power-cycled.
- On `GM1.10E`, `ranma` noted a residual focus-related square in the upper-left corner under some conditions; whether that element uses a separate XIMR layer or non-Palette-0 slot on `GM1.10C` will be observed during the hardware test.
