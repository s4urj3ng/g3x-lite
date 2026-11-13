# PORT-42 GUI-Fixed Full Build: Owner Trial and Recovery Plan

## Overview & Safety Controls

Owner trial plan for the GUI-fixed full CHDK builds on the Canon PowerShot G3 X (GM1.10C, PID `0x32A8`, DIGIC 6).

- **Execution Order**: The GUI-fixed default build must be tested and pass **first**. The `FULL_HOOKS=1` variant is tested **only after** the default build passes.
- **Card-Write Safety**: SD card writes are strictly disabled at compile time (`G3X_DISABLE_CARD_WRITES=1`, `OPT_DISABLE_FILE_WRITES=1`, `conf_save` and file logging stubbed). The physical SD card write-protect switch must remain locked (**LOCK** position).
- **RAM Execution**: Code executes strictly from DRAM (`DISKBOOT.BIN`). No flash ROM, NVRAM, or persistent camera firmware is modified.
- **Recovery Protocol**: **Battery pull**. Remove the NB-10L battery for at least 10 seconds to fully discharge DRAM. Inserting a standard (non-bootable or unlocked) SD card and powering on returns the camera to 100% stock Canon operation.

---

## Trial Protocol Table

| Step | Build Variant | DISKBOOT Checksum & Size | Action / Test Check | Expected Behavior & Acceptance Criteria | Observation / Result |
|:---|:---|:---|:---|:---|:---|
| **1.1** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | SHA-256: `760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738`<br>Size: `124,257` bytes | **Preflight**: Verify checksum of `DISKBOOT.BIN` on host; verify SD card write-protect switch is set to LOCK. | Exact SHA-256 and size match; card write-protect physical switch locked. | `[ ] PASS  [ ] FAIL` |
| **1.2** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **Boot Method**: Test short press (<0.5 s) vs held press (1–2 s) of Power / Playback button. Record boot method used. | Camera powers on and loads Canon UI with CHDK resident in DRAM. Record whether short press or held press succeeded. | `[ ] Held Press`<br>`[ ] Short Press` |
| **1.3** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **ALT Panel & Zero-Flicker**: Press ALT key (Play/Shortcut) to open ALT key-help panel; **hold and observe for 10 s**. | **No flicker** on the ALT panel; panel remains rock-solid and stable throughout 10 s hold (periodic forced redraw eliminated). | `[ ] PASS  [ ] FAIL` |
| **1.4** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **Colour Neutrality**: Inspect panel background and text colours on LCD screen. | **No pink blocks**; background uses neutral UYVY black (`0x00800080`) and text uses neutral white (`0xFF80FF80`), no magenta chroma artifacts. | `[ ] PASS  [ ] FAIL` |
| **1.5** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **Opacity & Font Scale**: Inspect background opacity and font readability on 900x600 LCD. | **Opaque black panel** (opacity `0xFF` in `opacity_buffer[active_bitmap_buffer & 1]`, zero live view show-through) with crisp, readable **2x integer text (16x32 font)**. | `[ ] PASS  [ ] FAIL` |
| **1.6** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **CHDK Menu Operation**: Press Menu key while in ALT mode to enter CHDK Menu. | **CHDK Menu opens cleanly and is readable**; centered 880x576 layout with solid black background and legible white text. | `[ ] PASS  [ ] FAIL` |
| **1.7** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **Power-Off Behaviour**: Press Power button to turn off camera. Record power-off behaviour. | Camera powers off cleanly, or record if shutdown requires button hold / battery pull. | `[ ] Clean Power-Off`<br>`[ ] Other (record):` |
| **1.8** | **GUI-Fixed Default** (`G3X_GUI_FIX=1`) | (same as 1.1) | **Recovery / Clean State**: Perform **battery pull** (remove battery for $\ge 10\text{ s}$). | DRAM fully discharged. Camera is ready for next step or stock boot. | `[ ] PASS  [ ] FAIL` |
| **GATE** | **Variant Progression Gate** | — | **Check Results of Steps 1.1–1.8**: Default build must pass all checks before proceeding. | **Proceed to Variant 2 ONLY after Default GUI build passes.** If any check fails, STOP and report. | `[ ] GO to Variant 2`<br>`[ ] NO-GO (abort)` |
| **2.1** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | SHA-256: `d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb`<br>Size: `124,321` bytes | **Preflight**: Verify checksum of `DISKBOOT.BIN` on host; verify SD card write-protect switch is set to LOCK. | Exact SHA-256 and size match; card write-protect physical switch locked. | `[ ] PASS  [ ] FAIL` |
| **2.2** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **Boot Method**: Power on via recorded boot method (held press or short press). Record boot method used. | Camera powers on and loads Canon UI with hooked tasks (`task_PhySw`, `task_InitFileModules`, `task_CaptSeq`, `task_FileWrite`) active. | `[ ] Held Press`<br>`[ ] Short Press` |
| **2.3** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **ALT Panel & Zero-Flicker**: Press ALT key to open ALT panel; **hold and observe for 10 s**. | **No flicker** on ALT panel; `mykbd_task` responds smoothly to keyboard events. | `[ ] PASS  [ ] FAIL` |
| **2.4** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **Colour Neutrality**: Inspect panel and text colours. | **No pink blocks**; neutral UYVY black/white colours preserved under full hooks. | `[ ] PASS  [ ] FAIL` |
| **2.5** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **Opacity & Font Scale**: Inspect panel background and font readability. | **Opaque black panel** with readable **2x integer text (16x32 font)**. | `[ ] PASS  [ ] FAIL` |
| **2.6** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **CHDK Menu & Navigation**: Press Menu key in ALT mode to enter CHDK Menu; test key navigation. | **CHDK Menu opens and is readable**; navigation works via hooked keyboard handler; menu items legible. | `[ ] PASS  [ ] FAIL` |
| **2.7** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **Power-Off Behaviour**: Press Power button to turn off camera. Record power-off behaviour. | Camera powers off cleanly, or record behaviour. | `[ ] Clean Power-Off`<br>`[ ] Other (record):` |
| **2.8** | **GUI Fix + FULL_HOOKS** (`G3X_GUI_FIX=1 FULL_HOOKS=1`) | (same as 2.1) | **Final Recovery**: Perform **battery pull** (remove battery for $\ge 10\text{ s}$). | DRAM fully discharged. Camera returns to 100% clean stock state. | `[ ] PASS  [ ] FAIL` |
