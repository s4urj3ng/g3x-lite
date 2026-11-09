# PORT-41 Short-Press Start-Mode Handoff

Handoff of short-press start-mode fix (PORT-39 DEFECT 1: short-press boot starts in Playback instead of shooting mode) for standard CHDK `boot.c` work in PORT-41:

| Item | Current Value / Location (`chdk-port/platform/g3x/sub/110c/`) | Required Value | Evidence Label |
|---|---|---|:---:|
| **(1) Start cause save & restore (`0x9BD0`)** | `kbd_candidate.h:130-131, 149, 164`: `g3x_shortpress_boot_entry_hook` saves `*(0x9BD0)` to `g3x_saved_start_cause`; restored in `post_bss_hook` and `read_keys` (may restore Playback `0x00100000`) | A Power start must restore `0x00080000`, not the Playback value `0x00100000` | `VERIFIED` |
| **(2) `physw_status` override bit (`0x40DAC`)** | `kbd_candidate.h:47-48, 113-120, 150, 162`: `physw_status[0]` fakes/clears `g3x_selected_button_bit` (can select Playback bit 16 `0x00010000` or Power bit 17 `0x00020000`) | Override must fake or clear Power bit 17 only (`0x00020000`), never Playback bit 16 (`0x00010000`) | `FINSIG` |
| **(3) Fallback for 0 or unknown start cause** | `kbd_candidate.h:134-136`: defaults `g3x_saved_start_cause = G3X_STARTCAUSE_POWER` (`0x00080000`) when neither Playback nor Power bit is set in raw cause | Fallback to Power start (`0x00080000` / Power bit 17) when saved cause is 0 or unknown | `INFERRED` |
| **(4) Override release mechanism** | `kbd_candidate.h:80-81, 165-168`: releases override (`g3x_shortpress_active = 0`) when 200 margin polls reach 0 (~7 s total from boot entry) | Keep the override release; PORT-39 addendum marks PASS: pressing Power later turns the camera off normally | `VERIFIED` |
| **(5) ~7 s bit-clear vs KEY_PLAYBACK** | `kbd_candidate.h:85-89, 158-164`: clearing active-low switch bit for ~7 s (~5 s LED ladder + 200 polls @ 10 ms) | Clearing a bit for about 7 s must not look like a held `KEY_PLAYBACK` (clearing bit 17 keeps power; never clear Playback bit 16) | `INFERRED` |
