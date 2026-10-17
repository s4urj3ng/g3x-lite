# GM1.10C evidence-based function map

Updated: 2026-10-17  
Scope: read-only static candidates; no Ghidra session, execution, patching, or hardware validation

## Method and confidence vocabulary

`tools/find_eventprocs.py` scans adjacent 32-bit words for an in-ROM printable name pointer and an odd in-ROM pointer, then optionally decodes the first nearby Thumb-2 `BL`. The ROM was opened `rb`/`mmap.ACCESS_READ`; expected SHA-256 was enforced and metadata remained unchanged.

Because a continuous table produces overlapping two-word windows, each reported hit was manually aligned against neighboring entries. A standalone overlapping hit is not evidence. Two table layouts occur below:

- `name,function`: the name pointer is followed by its function pointer;
- `function,name`: the function pointer is followed by its name pointer.

Confidence meanings:

- **CONFIRMED binding**: the GM1.10C table directly binds the exact string to an aligned odd code pointer, and neighboring entries support the layout.
- **HIGH candidate**: direct table evidence plus plausible wrapper/call structure, but prototype and complete semantics are unverified.
- **MEDIUM candidate**: direct string or source-role evidence without a fully reviewed implementation/call graph.
- **UNKNOWN**: no function address is claimed.

These labels identify static objects; they do not establish that calling them externally is safe.

## 1. AF, AE, and MF event-procedure wrappers

The continuous table at `0xFC76E5A0` uses `name,function` entries. Each selected wrapper has a valid odd Thumb pointer and a short wrapper shape whose first `BL` target is shown separately.

| Name | Table entry | Named wrapper | First decoded `BL` target | Classification |
|---|---:|---:|---:|---|
| `SS.DoAFLock` | `0xFC76E5AC` | `0xFC558239` | `0xFC2A8207` | wrapper **CONFIRMED**; target **HIGH candidate** |
| `SS.UnlockAF` | `0xFC76E5B4` | `0xFC558243` | `0xFC2A8237` | wrapper **CONFIRMED**; target **HIGH candidate** |
| `SS.DoAELock` | `0xFC76E5BC` | `0xFC55824D` | `0xFC2A85D7` | wrapper **CONFIRMED**; target **HIGH candidate** |
| `SS.UnlockAE` | `0xFC76E5C4` | `0xFC558257` | `0xFC2A85F5` | wrapper **CONFIRMED**; target **HIGH candidate** |
| `SS.MFOn` | `0xFC76E5CC` | `0xFC558261` | `0xFC2A96B5` | wrapper **CONFIRMED**; target **HIGH candidate** |
| `SS.MFOff` | `0xFC76E5D4` | `0xFC55826B` | `0xFC2A96E9` | wrapper **CONFIRMED**; target **HIGH candidate** |

The names align with event-procedure knowledge in pinned CHDK [`finsig_thumb2.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/finsig_thumb2.c), including `SS.DoAFLock_FW`, `SS.UnlockAF_FW`, `SS.MFOn_FW`, and `SS.MFOff_FW`. CHDK source supports the role of the names, not these GM1.10C addresses; the addresses come only from the local image.

## 2. Lens, iris, ND, and mechanical-shutter services

The long service tables around `0xFCA5E17C` and `0xFCEB3508` use `function,name` alignment. The following are direct name bindings. Their prototypes, units, state preconditions, and whether each is a public wrapper or low-level actuator routine remain unresolved.

| Name | Table entry | Bound function | Classification |
|---|---:|---:|---|
| `MoveFocusLensWithDistance` | `0xFCA5E18C` | `0xFC5FE6B7` | **CONFIRMED binding**, semantics **HIGH candidate** |
| `GetFocusLensSubjectDistance` | `0xFCA5E26C` | `0xFC5FEFF9` | **CONFIRMED binding**, semantics **HIGH candidate** |
| `MoveIrisWithAv` | `0xFCA5E314` | `0xFC5FF335` | **CONFIRMED binding**, semantics **HIGH candidate** |
| `PutOutNdFilter` | `0xFCEB3508` | `0xFC61361D` | **CONFIRMED binding**, implementation layer unresolved |
| `PutInNdFilter` | `0xFCEB3510` | `0xFC60539B` | **CONFIRMED binding**, implementation layer unresolved |
| `MoveIrisToAv` | `0xFCEB3520` | `0xFC60535D` | **CONFIRMED binding**, implementation layer unresolved |
| `OpenMShutter` | `0xFCEB35A0` | `0xFC555DA9` | **CONFIRMED binding**, implementation layer unresolved |
| `CloseMShutter` | `0xFCEB35A8` | `0xFC602F5D` | **CONFIRMED binding**, implementation layer unresolved |
| `MoveFocusLensToDistance` | `0xFCEB3820` | `0xFC604851` | **CONFIRMED binding**, semantics **HIGH candidate** |

CHDK's G5 X [`wrappers.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/wrappers.c) warns that moving focus to a distance can crash unless the Canon UI has already put the camera in manual focus. That is reference-port historical evidence, not permission to call the GM1.10C function. ND signature selection also required manual corrections on some ports; table names do not settle which layer CHDK should use.

## 3. Shutter-time and exposure controls

The continuous `ShutterTool` table at `0xFC860B74` uses `name,function` alignment.

| Name | Table entry | Bound function | Classification |
|---|---:|---:|---|
| `ShutterTool.SetTv` | `0xFC860B74` | `0xFC47E647` | **CONFIRMED binding** |
| `ShutterTool.SetExpTime` | `0xFC860B84` | `0xFC47E77B` | **CONFIRMED binding** |
| `ShutterTool.GetCurTv` | `0xFC860B94` | `0xFC47E847` | **CONFIRMED binding** |
| `ShutterTool.GetCurExpTime` | `0xFC860B9C` | `0xFC47E85B` | **CONFIRMED binding** |
| `ShutterTool.CheckTv` | `0xFC860BC4` | `0xFC47E6EF` | **CONFIRMED binding** |
| `ShutterTool.CheckExpTime` | `0xFC860BD4` | `0xFC47E81F` | **CONFIRMED binding** |

These names expose useful analysis anchors for shutter-latency and exposure paths. They do not prove the source of user-visible shutter lag, the units of arguments, or safe invocation outside Canon's own state machine. The DryOS `ExpDrvTask` string is present at `0xFC2C23E4`, but a task entry address is not yet proven.

## 4. Movie and autofocus candidates

The table around `0xFC71BBC8` uses `name,function` alignment:

| Name | Table entry | Bound function | Classification |
|---|---:|---:|---|
| `MovieAF.Suspend` | `0xFC71BBC8` | `0xFC149B6D` | **CONFIRMED binding**; implementation semantics unreviewed |
| `MovieAF.Resume` | `0xFC71BBD0` | `0xFC149B77` | **CONFIRMED binding**; implementation semantics unreviewed |

Strings such as `MovieRecord`, `MovieAF.c`, and other movie-source diagnostics prove subsystem presence but not task/function entry points. No recording-limit check, file-size condition, elapsed-time condition, encoder loop, or `task_MovieRecord` address is presently confirmed. Removing a limit is therefore not yet a supported design.

## 5. DryOS task and file-module anchors

The following exact GM1.10C strings are useful Ghidra anchors, but are **not function addresses**:

| String | ROM address | Status |
|---|---:|---|
| `CaptSeqTask` | `0xFC06A308` | task-name string; entry **UNKNOWN** |
| `InitFileModules` | `0xFC0BD1AC` | task/subsystem string; entry **UNKNOWN** |
| `ExpDrvSubTask` | `0xFC214EB8` | task-name string; entry **UNKNOWN** |
| `FileWriteTask` | `0xFC25F484` | task-name string; entry **UNKNOWN** |
| `ExpDrvTask` | `0xFC2C23E4` | task-name string; entry **UNKNOWN** |

Pinned CHDK [`finsig_thumb2.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/finsig_thumb2.c) derives `task_CaptSeq`, `task_ExpDrv`, and `task_FileWrite` from firmware-specific task-signature logic. Running that tool against GM1.10C, then checking each result in disassembly, is the correct next route. Searching for a string alone cannot establish the task function.

## 6. HDMI-001 initial candidates

Continuous `function,name` service tables in GM1.10C provide the following direct bindings:

| Name | Table entry | Bound Thumb function | Classification |
|---|---:|---:|---|
| `DispCon_SetDisplayType` | `0xFC76E4A0` | `0xFC37CBFF` | **CONFIRMED binding** |
| `DispCon_TurnOnDisplay` | `0xFC76E4A8` | `0xFC37CAA5` | **CONFIRMED binding** |
| `DispCon_TurnOffDisplay` | `0xFC76E4B0` | `0xFC37CD09` | **CONFIRMED binding** |
| `StartDisplayHDMIForFAMode` | `0xFCEB2C10` | `0xFC5720D9` | **CONFIRMED binding** |
| `StopDisplayHDMIForFAMode` | `0xFCEB2C18` | `0xFC57226F` | **CONFIRMED binding** |
| `TurnOnVideoOutMode` | `0xFCEB2F10` | `0xFC613ABD` | **CONFIRMED binding** |
| `TurnOffVideoOutMode` | `0xFCEB2F18` | `0xFC2B4FE9` | **CONFIRMED binding** |
| `SetVideoOutType` | `0xFCEB3480` | `0xFC612C39` | **CONFIRMED binding** |
| `GetVideoOutType` | `0xFCEB3488` | `0xFC612979` | **CONFIRMED binding** |
| `SwitchOnDisplay` | `0xFCEB3490` | `0xFC61294B` | **CONFIRMED binding** |
| `SwitchOffDisplay` | `0xFCEB3498` | `0xFC612941` | **CONFIRMED binding** |

Additional exact string anchors include `Hdmi_Config.c` (`0xFC09C1E4`), `Edid.c` (`0xFC0A9374`), `Hdmi.c` (`0xFC0C2898`), `Hdmi_cec.c` (`0xFC0D7660`), `HdmiCecTask` (`0xFC0D767C`), `Hdmi_comm.c` (`0xFC287290`), `HDMIConnectCnt` (`0xFC33E2A4`), and the diagnostic commands `HdmiRegDump` through `HdmiSetOutputResolusion` at `0xFC5FBBC8`–`0xFC5FBC88`. These string addresses are not function addresses.

The most relevant first call-graph targets for HDMI-001 are the display-type transition, HDMI FA-mode start/stop, video-output mode on/off, and the HDMI/EDID/CEC task families. No static evidence yet ties any one function to the historically reported 1080p live-view crash, RAM exhaustion, ARAM relocation, or a safe fix.

### Targeted Ghidra results

Ghidra 12.1.4 confirms the six requested named entries as Thumb code and resolves these local flows:

| Named entry | Resolved flow | Confidence |
|---|---|---|
| `StartDisplayHDMIForFAMode` `0xFC5720D8` | one-instruction tail branch to implementation `0xFC57209E`; implementation calls `0xFC1285AC`, `0xFC57207E`, a thunk at `0xFC3542DE`, and `0xFC37F886` | **HIGH** for flow; callee roles unresolved |
| `StopDisplayHDMIForFAMode` `0xFC57226E` | one-instruction tail branch to implementation `0xFC572220`; implementation calls `0xFC41FB64`, `0xFC2B5A12`, `0xFC2B59E6`, `0xFC0D75FC`, `0xFC0C2576`, and `0xFC2B7DF0`, plus a RAM thunk | **HIGH** for flow |
| `TurnOnVideoOutMode` `0xFC613ABC` | calls ROM thunks `0xFC31BE44` and `0xFC31BF94`, then joins `0xFC613A5E` | **HIGH** for direct flow; function boundary **MEDIUM** |
| `TurnOffVideoOutMode` `0xFC2B4FE8` | calls ROM thunks `0xFC31BEC4`, `0xFC31BFF4`, and tail thunk `0xFC31B8E8` plus an internal branch | **HIGH** for direct flow |
| `SetVideoOutType` `0xFC612C38` | small leaf loading a value through a global pointer and returning | **HIGH** for instructions; semantic name/prototype still unresolved |
| `GetVideoOutType` `0xFC612978` | calls `0xFC61294C`, then returns zero | **HIGH** for flow; semantic layer unresolved |

`0xFC0D75FC` lies in the `Hdmi_cec.c`/`HdmiCecTask` code neighborhood, and `0xFC0C2576` lies in the `Hdmi.c` neighborhood. This makes the stop implementation's connection to HDMI/CEC state management **HIGH-confidence subsystem evidence**, but proximity alone does not name either function.

### Overlay, palette, VRAM, and compositor functions (Phase 3C verified)

Corrected aligned EventProc table bindings (`C016` — fixes earlier 1-slot table shift around `0xFC558578..` and `0xFCA5EA50..`), verified by both `finsig_thumb2` and direct ROM table inspection:

| Name | Table entry | Bound Thumb function (even entry) | Evidence/status |
|---|---:|---:|---|
| `DispCon_ShowBitmapColorBar` | `0xFC76E4C0` | `0xFC37C991` (`0xFC37C990`) | **CONFIRMED binding**; calls `0xFC37C868` |
| `SaveBmpVRAMData` | `0xFC558578` | `0xFC558349` (`0xFC558348`) | **CONFIRMED binding** (`C016`); diagnostic SD export of bitmap VRAM; calls `SavePaletteData` (`0xFC5584E8`) at `0xFC558432` |
| `SavePaletteData` | `0xFC558580` | `0xFC5584E9` (`0xFC5584E8`) | **CONFIRMED binding** (`C016`); exports 256-entry palette via `PaletteClass_GetEntry` (`0xFC19D8CA`) |
| `GetVRAMHPixelsSize` | `0xFCA5EA50` | `0xFC0D360B` (`0xFC0D360A`) | **CONFIRMED binding** (`C016`); returns `*(uint16_t *)(*(0x000083DC) + 0x18)` |
| `GetVRAMVPixelsSize` | `0xFCA5EA58` | `0xFC0D3613` (`0xFC0D3612`) | **CONFIRMED binding** (`C016`); returns `*(uint16_t *)(*(0x000083DC) + 0x1A)` |
| `GetContinuousVRAMData` | `0xFCA5EA68` | `0xFC612FA5` (`0xFC612FA4`) | **CONFIRMED binding** (`C016`); synchronized diagnostic wrapper |
| `GetContinuousVRAMDataWithRingBuffer` | `0xFCA5EA70` | `0xFC6134A9` (`0xFC6134A8`) | **CONFIRMED binding**; synchronized ring-buffer capture |
| `GetContinuousMovieJpegVRAMData` | `0xFCA5EA78` | `0xFC613507` (`0xFC613506`) | **CONFIRMED binding**; synchronized movie-JPEG capture |

Core `SCM.c`, `Palette Class.`, `VramTransferManager.c`, `MakeOsdVram.c`, `BmpDev.c`, `MzrmGraphic`, and `ZicoKick` functions and globals verified by `finsig_thumb2` (`r5491`) and Capstone/Ghidra disassembly (`SeedAndReportOverlay.java`):

| Symbol / Function | GM1.10C Address | Source Anchor / Evidence | Role |
|---|---:|---|---|
| `SCM_MarkDirtyBit1` | `0xFC33D10C` | `"SCM.c"` (`0xFC33D4EC`) | Sets bit 1 (`0x02`) of `palette_control` (`0x00015DA4`) |
| `SCM_GetActivePaletteObject` | `0xFC33D12C` | `finsig_thumb2` + `"SCM.c"` | Returns `palette_buffer_ptr[active_palette_buffer]`, lazy-allocating `0x408`-byte `PaletteClass` from ROM default if null |
| `SCM_Init` | `0xFC33D240` | `"SCM.c"` (`0xFC33D4EC`) | Initialises 15 x 8-byte colour-override table at `0x00123140` (C018), sets `palette_init_flag` (`0x00015DB0`) = `1`, `palette_buffer_ptr` (`0x00015DBC`) = `0x001231B8`, `palette_lookup_ptr` (`0x00015DC0`) = `0xFC77E0DC` |
| `SCM_SetActivePalette` | `0xFC33D282` | `"SCM.c"` (`0xFC33D4EC`) | Sets `active_palette_buffer` (`0x00015DB4`, `0..3`) and sets bits `0\|1` (`0x03`) of `palette_control` (`0x00015DA4`) |
| `SCM_IsDirtyBit0` / `SCM_ClearDirtyBit0` | `0xFC33D2B4` / `0xFC33D2BE` | `"SCM.c"` (`0xFC33D4EC`) | Tests / clears bit 0 of `palette_control` (`0x00015DA4`) |
| `SCM_MarkDirtyBits01` | `0xFC33D2D0` | `"SCM.c"` (`0xFC33D4EC`) | Sets bits `0\|1` (`0x03`) of `palette_control` (`0x00015DA4`) |
| `SCM_PushPaletteIfDirty` | `0xFC33D2F0` | `"SCM.c"` (`0xFC33D4EC`) | If `*(uint8_t *)0x00015DA4 != 0`, clears it to `0` and gets `slot + 4` via `0xFC19D800` and sends it with `0xFC20BF42`, then re-applies overrides (`0xFC33D1AE`) |
| `SCM_GetRomDefaultPalette` | `0xFC33D5FA` | `"SCM.c"` (`0xFC33D4EC`) | Returns `0xFC77C8AC + slot_id * 0x60C + 4` (`0xFC77C8B0` for slot 0) |
| `PaletteClass_GetPayload` (was `PaletteClass_SendToMzrm`) | `0xFC19D800` | `"Palette Class."` (`0xFC77B62C`) | **Corrected (C020):** `adds r0,#4; bx lr` returns `slot + 4`; the caller then sends it via `0xFC20BF42` (`-> 0xFC4C2ABE`). Magic validation happens in `0xFC19D804` |
| `PaletteClass_Create` | `0xFC19D828` | `"Palette Class."` (`0xFC77B62C`) | Allocates `0x408` bytes on heap, writes magic `0xFC77B62C` at `+0x00`, copies `0x404` bytes to `+0x04` |
| `PaletteClass_CopyData` | `0xFC19D898` | `"Palette Class."` (`0xFC77B62C`) | Validates magic and copies palette payload into `slot + 4` |
| `PaletteClass_GetEntry` | `0xFC19D8CA` | `"Palette Class."` (`0xFC77B62C`) | Validates magic and `idx < 0x100`, returns `*(uint32_t *)(slot + 4 + idx * 4)` |
| `PaletteClass_InitHeader` / `ValidateMagic` | `0xFC19D8E8` / `0xFC19D8F2` | `"Palette Class."` (`0xFC77B62C`) | Writes / verifies `*(uint32_t *)slot == 0xFC77B62C` |
| `DispDev_ConvertPaletteToHwLut` | `0xFC1425FC` | `DispDev` LUT converter | Converts 256 `AYCrCb` entries (`bits 25:24` = 2-bit alpha: `0->0x00, 1->0x40, 2->0x80, 3->0xFF`) |
| `MakeOsdVram_Create` | `0xFC183824` | `"MakeOsdVram.c"` (`0xFC183B7C`) | Allocates `0x10`-aligned OSD VRAM control struct at `*(0x0000B3EC)` |
| `BmpDev_Init` / `BmpDev_ConfigureBuffers` | `0xFC18347E` / `0xFC183610` | `"BmpDev.c"` (`0xFC1837E8`) | Initializes 960x480 / 720x480 bitmap buffers |
| `transfer_src_overlay` | `0xFC380634` | `finsig_thumb2` + `"VramTransferManager.c"` (`0xFC380828`) | Transfers active OSD bitmap (`active_bitmap_buffer` `0x0000D2A4`, `bitmap_buffer` `0x0000D2A8`) and calls `SCM_PushPaletteIfDirty` (`0xFC33D2F0`) at `0xFC380684` |
| `XimrExe` | `0xFC20C6D0` | `"MzrmGraphic"` (`0xFC20CA30`) | Populates XIMR composition descriptor at `0x0001A438` and sends Mzrm RPC `0x24`/`0x25` via `0xFC20BE22` |
| `Mzrm_SendPaletteMsg` | `0xFC4C2ABE` (thunk `0xFC20BF42`) | `"MzrmGraphic"` (`0xFC20CA30`) | Sends Mzrm message `0xC8` with `slot + 4` palette pointer via queue `*(0x00024900)` |
| `ZicoKick_Start` | `0xFC3DFD3C` | `"ZicoKick Start\n"` (`0xFC3DFDCC`) | Copies embedded Zico Xtensa firmware (`0xFCC9C6F0..0xFCDB14E0`, containing GRYP/XIMR strings `0xFCC9CDD0..0xFCCB9464`) to `0x80A00000` |

## 7. RAM-only extension architecture

Reference r5491 boot code for [G5 X](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/sub/100c/boot.c), [M10](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/m10/sub/110d/boot.c), and [SX710](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx710hs/sub/100a/boot.c) establishes this architecture:

1. Canon code/data is copied from ROM to RAM during boot.
2. A RAM-resident `CreateTask` instruction sequence is replaced with a jump to a CHDK wrapper.
3. The wrapper substitutes selected firmware task pointers and creates a separate SpyTask.

This is verified reference-source behavior and a plausible research direction for GM1.10C. For HDMI-001 (Clean HDMI), a simpler Canon Basic RAM-data toggle (`firmware/tools/hdmi001_clean_overlay_gm110c.m`) suffices without patching `CreateTask`.

## 8. Cross-firmware reuse boundary

Reusable from GM1.10E and reference ports:

- subsystem and event-procedure names;
- DryOS R57 task roles;
- source organization and signature-finder rules;
- wrapper/call-graph shapes and Version Tracking strategy;
- the general RAM task-redirection architecture.

Not reusable without GM1.10C proof:

- absolute ROM/RAM/MMIO addresses;
- structure offsets, prototypes, heap or display boundaries;
- task-hook preimages and task entry pointers;
- binary patches or claims of behavioral compatibility.

The GM1.10E version-string address (`0xFC54E0B5` vs `0xFC54E08D` on `GM1.10C`) and `ranma`'s inverted `strcmp("EC385\n\r", 0xfc000584)` check (`0xFC00052C` on `GM1.10C`, `C017`) provide direct counterexamples to unverified address reuse.

## 9. Prioritized analysis queue

| Priority | Goal | Anchors | Status / Next proof needed |
|---|---|---|---|
| **DONE (Offline)** | **HDMI-001 Clean HDMI overlay suppression** | `SCM.c` (`0xFC33D10C..0xFC33D616`), `PaletteClass` (`0xFC19D800..0xFC19D906`), `0x00015DA4..0x00015DBC`, `0xFC77C8B0` | **`READY_FOR_HARDWARE_TEST`** (`firmware/tools/hdmi001_clean_overlay_gm110c.m` + `tools/validate_hdmi001_script.py`) |
| P0 | AF Lock and focus-state behavior | `SS.DoAFLock`, `SS.UnlockAF`, `SS.MFOn`, `SS.MFOff`, focus-lens tables | wrapper disassembly, callers, state/error paths, prototypes |
| P0 | Focus-distance path | `MoveFocusLensToDistance`, subject-distance getter | cross-references, argument units, MF preconditions, actuator state machine |
| P1 | Shutter latency decomposition | `ShutterTool.*`, `OpenMShutter`, `CloseMShutter`, `CaptSeqTask` (`0xFC2B1DA5` via `finsig_thumb2`) | verify `task_CaptSeq` (`0xFC2B1DA5`) and `task_ExpDrv` (`0xFC2C1DC9`) in disassembly |
| P1 | Exposure/iris/ND path | AE wrappers, iris/ND tables, `ExpDrvTask` | verify `task_ExpDrv` (`0xFC2C1DC9`), message structures, table layer selection |
| P2 | Movie AF and recording limit | `MovieAF.Suspend/Resume`, movie strings | movie task entry, recording-state graph, independent time/size checks |

## 10. Unresolved blockers

- Ghidra 12.1.4, Capstone 5.0.6, and CHDK `finsig_thumb2` (`r5491`, built in `/tmp/g3x-finsig-build/finsig_thumb2`) are operational.
- **HDMI-001 (`BLK-08`) is RESOLVED OFFLINE (`READY_FOR_HARDWARE_TEST`)**.
- The historical `g3x_110e.patch` remains inaccessible (`BLK-03`), so `GM1.10C` uses clean-room symbol/task extraction.
- No video recording-limit implementation has been identified yet.
- No event-procedure or Canon Basic script has been executed on the camera in this session; hardware verification awaits owner approval.

## 11. Reproduction

```sh
python3 tools/find_eventprocs.py \
  firmware/dumps/GM1.10C/PRIMARY.BIN \
  --expect-sha256 9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578 \
  --pattern '^(SS\.(DoAF|UnlockAF|DoAE|UnlockAE|MFOn|MFOff)|MoveFocusLens(To|With)|GetFocusLensSubjectDistance|MoveIris|Put(In|Out)NdFilter|OpenMShutter|CloseMShutter|ShutterTool\.|MovieAF\.)' \
  > /tmp/g3x-eventprocs.json
```

Script SHA-256 at review time: `34b381874a9c2f69b74aabcaca61253033807e5cfa3f4d3c369ec665e940506f`. The JSON includes intentional overlapping structural candidates; reproduce the manual alignment from continuous neighboring entries before accepting a binding.

