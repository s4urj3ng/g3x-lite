# PORT-51: Both-Buffer Sync Restore and Bypass-Path Analysis

**Date**: 2026-11-14  
**Scope**: Phase 0 read-only sibling and bounded ROM research (`PORT51-RESTORE2-SYNC`).
**Compile Flag**: `G3X_GUI_RESTORE2=1` (opt-in; with it off, PORT-42..50 behaviour is unchanged and default DISKBOOT.BIN remains byte-identical).

## 1. Overview and Both-Buffer Sync Restore

In PORT-49 and PORT-51a, the synchronous display-flip restore hook (`transfer_src_overlay` return interception via `*(volatile uint32_t *)0x0000E26C`) blitted the dirty rect exclusively into the single target buffer (`target_idx = r9 & 1`). Under high-frequency composition updates (such as AF tracking, face framing, or rapid display flips), a flip could occasionally land on the alternate buffer before it received the overlay, or before the 20 ms poll loop detected sentinel loss.

Under `G3X_GUI_RESTORE2=1` (PORT-51b), the sync hook in `g3x_shadow2_blit_restore_target` restores the dirty rect into **BOTH** bitmap buffers (`bitmap_buffer[0]` and `bitmap_buffer[1]`) and both opacity buffers (`opacity_buffer[0]` and `opacity_buffer[1]`), and sets opacity sentinel guards on both buffers (`g3x_sync_set_guard_target`). As a result, whichever buffer is currently active or flipped to by DryOS / VTM, the CHDK overlay is intact without flicker.

### Buffer Selection Citations

The selection of active and inactive buffers is cited to sibling DIGIC 6 `lib.c` implementations and FINSIG:

- **Active Buffer Selection (`active_bitmap_buffer & 1`)**:
  - `reference/finsig_gm110c/stubs_entry.S:186`: `DEF(active_bitmap_buffer, 0x0000d2a4) // (0xd264+0x40) Found @0xfc38116e` `[FINSIG]`
  - `reference/finsig_gm110c/stubs_entry.S:188`: `DEF(bitmap_buffer, 0x0000d2a8)` `[FINSIG]`
  - Sibling G7X: `chdk-port/platform/g7x/lib.c:279-281` (`vid_get_bitmap_active_buffer` returns `bitmap_buffer[active_bitmap_buffer & 1]`), lines 294-296 (`vid_get_opacity_active_buffer` returns `(void *)opacity_buffer[active_bitmap_buffer & 1]`) `[HISTORICAL_CHDK]`
  - Sibling SX60HS: `chdk-port/platform/sx60hs/lib.c:265-267` (`vid_get_bitmap_active_buffer` returns `bitmap_buffer[active_bitmap_buffer & 1]`), lines 272-274 (`vid_get_opacity_active_buffer` returns `(void *)opacity_buffer[active_bitmap_buffer & 1]`) `[HISTORICAL_CHDK]`
  - Sibling G5X: `chdk-port/platform/g5x/lib.c:21-25` (`vid_get_bitmap_fb` returns `bitmap_buffer[active_bitmap_buffer]`), lines 30-33 (`vid_get_opacity_active_buffer` returns `opacity_buffer[active_bitmap_buffer]`) `[HISTORICAL_CHDK]`
  - G3X platform: `chdk-port/platform/g3x/lib.c:20-23` (`vid_get_bitmap_fb` returns `bitmap_buffer[active_bitmap_buffer]`)
- **Inactive Buffer Selection**: `(active_bitmap_buffer & 1) ^ 1`.
- **Both-Buffer Addressing**:
  - `bitmap_buffer[0]` = `0x5FE80000` (loaded from literal pool `0xFC1837FC` at `0xFC183652`, stored to `0x0000D2A8` at `0xFC380AFC`) `[ROM_VERIFIED]`
  - `bitmap_buffer[1]` = `0x5FD00000` (loaded from literal pool `0xFC183818` at `0xFC18365A`, stored to `0x0000D2AC` at `0xFC380B02`) `[ROM_VERIFIED]`
  - `opacity_buffer[0]` = `0x5FC40000` (literal `0xFC183800`) `[ROM_VERIFIED]`
  - `opacity_buffer[1]` = `0x5FB80000` (literal `0xFC183804`) `[ROM_VERIFIED]`

## 2. Bypass-Path and Flip-Caller Analysis Table

The table below catalogs candidate callers of the display flip and writers of `active_bitmap_buffer` (`0x0000D2A4`), derived from FINSIG tables (`funcs_by_name.csv`, `funcs_by_address.csv`, `stubs_entry.S`), sibling ports (`g7x`, `g5x`, `sx60hs`), and recorded bounded ROM slices from `manifests/port49_gui_sync_evidence.json`. Zero full-ROM scans were conducted.

| Item | Sibling Path:Line | GM1.10C Address | Label | Hooked (Yes/No) | Rationale & Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`transfer_src_overlay` synchronous dirty-rect restore (both buffers)** | `chdk-port/platform/g7x/lib.c:15-19`; `chdk-port/platform/g5x/lib.c:11-17`; `chdk-port/platform/sx60hs/lib.c:17-19` | `0xFC380635` (calls `0xFC143493` at `0xFC380670`, return lr `0xFC380675`; `MakeOsdVram` at `0xFC3806F2`; epilogue pop at `0xFC3806F8`) | `FINSIG` / `ROM_VERIFIED` | **Yes** | Hooked via RAM callback pointer `*(0x0000E26C)` (`g3x_gui_sync_pre_cb`) intercepting return address at `sp_entry[23]` (`[sp, #92]`). Epilogue trampoline restores dirty rect to BOTH `bitmap_buffer[0..1]` and `opacity_buffer[0..1]` before flip. Counter: `Rs` / `Y`. |
| **`active_bitmap_buffer` buffer selection & pointer array** | `chdk-port/platform/g7x/lib.c:279-281`; `chdk-port/platform/sx60hs/lib.c:265-267`; `chdk-port/platform/g5x/lib.c:21-25`; `chdk-port/platform/g3x/lib.c:20-23` | `0x0000D2A4` (`active_bitmap_buffer`); `0x0000D2A8` (`bitmap_buffer[0..1]`) | `FINSIG` | **Yes** | Under `G3X_GUI_RESTORE2=1`, both active (`active_bitmap_buffer & 1`) and inactive (`(active_bitmap_buffer & 1) ^ 1`) buffers are restored synchronously. |
| **`VTM_FlipAndCommit` (`sub_fc38090a`) runtime writer of `active_bitmap_buffer`** | `chdk-port/platform/g5x/lib.c:12-18,206-219`; `chdk-port/platform/g7x/lib.c:5,279-281` | `0xFC38090B` (writes `active_bitmap_buffer` via `str r0, [r5, #64]` at `0xFC38091E`; calls `BmpDDev_SetBitmapVRAMAddress` at `0xFC38092E`, `0xFC38093E`) | `ROM_VERIFIED` | **Yes** (upstream) | Called exclusively by `VTMUnLock_flush` at `0xFC380A1C` immediately following `transfer_src_overlay` (`0xFC380A16`). Direct instruction patch avoided; protected upstream by sync hook on `transfer_src_overlay`. |
| **`transfer_src_overlay_helper` emergency single-buffer refresh** | `reference/finsig_gm110c/funcs_by_name.csv:2572`; `chdk-port/platform/g7x/sub/100c/funcs_by_name.csv:2528` | `0xFC38113F` (calls `transfer_src_overlay` at `0xFC38116E`, calls `BmpDDev_SetBitmapVRAMAddress` at `0xFC38117E`) | `FINSIG` / `ROM_VERIFIED` | **Yes** | Calls `transfer_src_overlay` at `0xFC38116E` with lr `0xFC381173`. Inside `transfer_src_overlay`, `GraphicSystemCoreFinish_helper` is called at `0xFC380670`, which hits `g3x_gui_sync_pre_cb` and intercepts return. |
| **`VTM_Init` (`sub_fc380a94`) boot initializer of `active_bitmap_buffer`** | None (boot initialization) | `0xFC380A95` (writes `0` to `active_bitmap_buffer` via `str r6, [r5, #64]` at `0xFC380B0A`) | `ROM_VERIFIED` | **No** | One-time cold boot initialization before display tasks and CHDK core are running. No live overlay exists to protect; left unhooked. |
| **`VTMUnLock_flush` pre-transfer finish (`GraphicSystemCoreFinish_helper`)** | None (internal VTM pipeline) | `0xFC3809DA` (calls `GraphicSystemCoreFinish_helper` at `0xFC143493`, return lr `0xFC3809DF`) | `ROM_VERIFIED` | **No** | Fires after dirty window redraw callback but *before* `MakeOsdVram` (`0xFC3806F2`) DMA overwrite. Blitting here would be overwritten by subsequent `MakeOsdVram`; safely ignored (`sp_entry[1] != 0xFC380675`). |
| **`BmpDDev_SetBitmapVRAMAddress` direct display commit** | `chdk-port/platform/g7x/lib.c:263-296`; `chdk-port/platform/g5x/lib.c:21-33` | `0xFC183691` (`0xFC183690`, called at `0xFC38092E`, `0xFC38093E`, `0xFC38117E`) | `ROM_VERIFIED` | **No** | Flash ROM routine with direct `bl` callers; no RAM function pointer exists. Protected upstream by `transfer_src_overlay` return interception before every call site. |
| **VSync ISR callback `*(0x00008364)` (`BmpDDev + 0x04`)** | `chdk-port/platform/sx710hs/sub/100a/stubs_min.S:26` | `0x00008364` (`0xFC18346B` -> `0xFC380A47`) | `ROM_VERIFIED` | **No** | Fires in hardware VSync interrupt context after display latch. Memory copy in ISR risks timing violations and audio/video jitter; left unhooked. |
| **`VTMLock` / `VTMUnLock` / `ScreenLock` / `ScreenUnlock`** | `chdk-port/platform/g5x/lib.c:9-19`; `chdk-port/platform/g7x/lib.c:7-20` | `0xFC3810A9` (`VTMLock`), `0xFC3810BD` (`VTMUnLock`), `0xFC3810F1` (`ScreenLock`), `0xFC381127` (`ScreenUnlock`) | `FINSIG` / `ROM_VERIFIED` | **No** | Concurrency mutex/semaphore primitives. UI flushes triggered upon unlocking delegate to `VTMUnLock_flush` (`0xFC3809AF`) and are fully captured by `transfer_src_overlay` hook. |
| **`DispCon_ShowBitmapColorBar_FW` factory test pattern** | None | `0xFC37C9CD` | `FINSIG` | **No** | Factory diagnostic test pattern generator; unused during standard camera operation; left unhooked. |

## 3. Evidence Manifest Citations

All ROM slice evidence referenced above is recorded with exact start, length, and SHA-256 in `manifests/port49_gui_sync_evidence.json` (zero full-ROM scans):
- **ROM `0xFC143480..0xFC14353F`** (192 B, SHA-256 `fc4ae66cff4891b65e94b150937c4613ff7ea844c85feff0fe9e4c199e46a7ce`): `GraphicSystemCoreFinish_helper` (`0xFC143493`) and literal pool pointer `0x0000E26C`.
- **ROM `0xFC18347E..0xFC18381F`** (930 B, SHA-256 `9fa1f49618f096c4a52fc996d93e157796934c9d7d42cf7b1981cb70678229ee`): `BmpDDev_SetBitmapVRAMAddress` (`0xFC183690`) and literal pool framebuffer addresses (`0x5FE80000`, `0x5FD00000`).
- **ROM `0xFC380634..0xFC38073F`** (268 B, SHA-256 `336d235df668ca1d9e05c010545ccf417c3b57a572326fb6dd35506c45d533ab`): `transfer_src_overlay` (`0xFC380635`), call to `GraphicSystemCoreFinish_helper` at `0xFC380670`, and epilogue at `0xFC3806F8`.
- **ROM `0xFC380740..0xFC3810EF`** (2480 B, SHA-256 `eb3c1a57c0e2a64c8a940368e0ec52ce8731f4b620a40b938a148c70e02484ba`): `VTM_FlipAndCommit` (`0xFC38090B`), `active_bitmap_buffer` write at `0xFC38091E`, `VTM_SelectNextBuffer` (`0xFC380985`), `VTMUnLock_flush` (`0xFC3809AF`), and `VTM_Init` (`0xFC380A95`).
- **ROM `0xFC3810F0..0xFC38119B`** (172 B, SHA-256 `188ac7d596935c5b3a6d4c04f91a15e9202676d70ef6712ef7d49e18f90dfcc0`): `ScreenLock` (`0xFC3810F1`), `ScreenUnlock` (`0xFC381127`), and `transfer_src_overlay_helper` (`0xFC38113F`).
