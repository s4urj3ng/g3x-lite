# PORT-52: Short-Press Boot Mechanism Table (Sibling Adaptation)

## Implementation Status in Existing G3X Code

> [!IMPORTANT]
> **EXISTING FIX: yes, active in default, PORT-50 GUI_MENU combo, and PORT-51 RESTORE2 builds via full_build overlay (`full_build/g3x/sub/110c/boot.c:66-69,141-144,398-410` and `full_build/g3x/kbd.c:124-162`); milestone PORT-52 stops early.**

### Build Path & Overlay Mechanism
The inert skeleton in `chdk-port/platform/g3x/sub/110c/boot.c:27-31` (`boot()` is `while(1);`) is never compiled into any shipping or candidate CHDK binary. Instead, all build paths stage sources from `full_build/g3x/` over the platform directory:
- `tools/build_port41_full.py:858-861`: Overlays `full_build/g3x/` onto `stage_chdk/platform/g3x/`.
- `scripts/build_port43_dbuf.py:2092-2095`: Overlays `full_build/g3x/` onto `stage_chdk/platform/g3x/`.

### Active Implementation in `full_build`
The active short-press fix is implemented directly in `full_build/`:
1. `full_build/g3x/sub/110c/boot.c:66-69`: Early boot hook `g3x_full_shortpress_boot_entry_hook` executes before copy loops, sampling and preserving the raw start cause from `0x00009BD0`.
2. `full_build/g3x/sub/110c/boot.c:141-144`: Post-BSS hook `g3x_full_shortpress_post_bss_hook` executes after BSS clearing, restoring `0x00080000` (Power) or preserving Playback at `0x00009BD0`, and clearing Power bit 17 in `physw_status[0]`.
3. `full_build/g3x/sub/110c/boot.c:398-410`: Power-cut bypass `sub_fc05b962_my` intercepts stock `0xFC05B962`, executes `sub_fc05ba68`, `sub_fc079404`, and `sub_fc1284ac`, forces `movs r0, #1`, and branches past the `sub_fc05ba56` power-down shutdown routine directly to `task_Startup_my` creation.
4. `full_build/g3x/kbd.c:102-107`: Defines `G3X_ADDR_STARTCAUSE (0x00009BD0)`, `G3X_STARTCAUSE_POWER (0x00080000)`, `G3X_STARTCAUSE_PLAYBACK (0x00100000)`, `G3X_KEY_POWER_BIT (0x00020000)`, `G3X_KEY_PLAYBACK_BIT (0x00010000)`, and `G3X_SHORTPRESS_MARGIN_POLLS (200)`.
5. `full_build/g3x/kbd.c:124-162`: In `my_kbd_read_keys()`, holds active-low Power key override (`physw_status[0] &= ~0x00020000`) and maintains `*(0x00009BD0) = g3x_full_saved_start_cause` for 200 polls (2.0 s @ 10 ms/poll) before releasing `g3x_full_shortpress_active = 0`. Defines `g3x_full_shortpress_boot_entry_hook` (142-156) and `g3x_full_shortpress_post_bss_hook` (158-163).

### Overlay Build Gating Audit
The short-press mechanism contains **zero** `#if` / `#ifdef` gating in `full_build/g3x/sub/110c/boot.c` and `full_build/g3x/kbd.c`. It is unconditionally compiled and always active across all build variants:

| Build Variant | Script Setting Flags | Gating `#if` Lines | Build Flags Passed | Short-Press Status |
|:---|:---|:---:|:---|:---:|
| **Default Build** | `tools/build_port41_full.py:904-918` | None | `PLATFORM=g3x PLATFORMSUB=110c G3X_FULL_BUILD=1` | **ALWAYS ON** (active) |
| **PORT-50 GUI_MENU combo** | `scripts/build_port43_dbuf.py:2203-2245`<br>`tests/test_port50_menu.py:242-255,279-293` | None | `G3X_FULL_BUILD=1 G3X_GUI_FIX=1 G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1 G3X_GUI_SYNC=1 G3X_GUI_MENU=1 G3X_DISABLE_CARD_WRITES=1 OPT_DISABLE_FILE_WRITES=1` | **ALWAYS ON** (active) |
| **PORT-51 RESTORE2 combo** | `scripts/build_port43_dbuf.py:2203-2245`<br>`tests/test_port51_restore2.py:613-633` | None | All PORT-50 flags plus `G3X_GUI_RESTORE2=1` | **ALWAYS ON** (active) |

Symbols confirmed in built binaries (`arm-none-eabi-nm`): `g3x_full_shortpress_active`, `g3x_full_shortpress_boot_entry_hook`, `g3x_full_shortpress_margin_polls`, `g3x_full_shortpress_post_bss_hook`, `sub_fc05b962_my`.

---

## Power Key Bit Verification & Sibling Architecture

- **Power Key Bit Verification**:
  - `reference/finsig_gm110c/physw_bits.txt:18`: Address `0xFC66C9C0`, info `0x01010211`, event `0x00000100` (PressPowerButton), index `0` (word 0), bit `0x00020000` (bit 17), non-inverted: 1.
  - `docs/PORT46_KEYMAP.md:28, 31, 176`: `KEY_POWER` mapped to word 0, bit 17 (`0x00020000`), event `0x100`. Excluded from `KEYS_MASK0` (`0x000533F9`).
  - `full_build/g3x/kbd.c:105`: `#define G3X_KEY_POWER_BIT 0x00020000` (word 0, bit 17).
  - **Disagreement Assessment**: **ZERO disagreement**. Both sources and active code agree that the Power button is word 0, bit 17 (`0x00020000`).
- **Closest Sibling Rationale**:
  - **PowerShot G5 X** (`chdk-port/platform/g5x/`) is the closest sibling.
  - Both G3 X and G5 X run DIGIC 6 (Cortex-A9) DryOS 57 and cannot use the soft-reboot flag `*(0x4FFC) = 0x12345678` used by G7 X (`loader/g7x/main.c:39`) and SX60HS (`loader/sx60hs/main.c:17`) (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:115`, `docs/PORT6A_POWERON_EVIDENCE.md:36,108`).
  - Active G3 X code (`full_build/g3x/sub/110c/boot.c:398-410`) follows the exact G5 X mechanism (`chdk-port/platform/g5x/sub/100c/boot.c:411-420`): intercepting startup check (`sub_fc05b962_my`), calling `sub_fc1284ac`, forcing `r0 = 1`, and jumping past the power cut (`sub_fc05ba56`) directly to `task_Startup_my`.

---

## Sibling Adaptation & Mechanism Table

| item | sibling path:line | G3X current state | GM1.10C address or value | label | change needed |
|:---|:---|:---|:---|:---:|:---|
| **Sibling short-press shutdown bypass** | `chdk-port/platform/g5x/sub/100c/boot.c:411-420`<br>`chdk-port/loader/g7x/main.c:39`<br>`chdk-port/loader/sx60hs/main.c:17` | Implemented in active build source `full_build/g3x/sub/110c/boot.c:398-410` (`sub_fc05b962_my`), forcing `movs r0, #1` past `sub_fc05ba56` power cut. Overlaid by `tools/build_port41_full.py:858-861` and `scripts/build_port43_dbuf.py:2092-2095` | `sub_fc05b962` @ `0xFC05B962`<br>`sub_fc05ba56` @ `0xFC05BA56`<br>`sub_fc1284ac` @ `0xFC1284AC` | `ROM_VERIFIED` | None (already implemented and active in all build variants; milestone stops early). |
| **Sibling start-cause discrimination** | `chdk-port/platform/g5x/sub/100c/boot.c:168-183`<br>`chdk-port/platform/g7x/sub/100d/boot.c:318`<br>`chdk-port/platform/sx60hs/sub/100b/boot.c:380` | Implemented in active build sources `full_build/g3x/sub/110c/boot.c:66-69,141-144` and `full_build/g3x/kbd.c:102-104,142-163`. Samples `0x00009BD0` before Copy Loop 3 and restores `0x00080000` (Power) / preserves `0x00100000` (Playback) post-BSS | `*(volatile unsigned int *)0x00009BD0`<br>Base `0x00009BC4` @ `0xFC08EEF0`<br>Power: `0x00080000` (bit 19)<br>Playback: `0x00100000` (bit 20) | `ROM_VERIFIED` | None (already implemented and active in all build variants; milestone stops early). |
| **Sibling physical switch override** | `chdk-port/platform/g5x/kbd.c:118-126`<br>`chdk-port/platform/g5x/sub/100c/boot.c:695-711`<br>`chdk-port/platform/g7x/kbd.c:70-82`<br>`chdk-port/platform/sx60hs/kbd.c:64-75` | Implemented in active build source `full_build/g3x/kbd.c:105,124-133,162`. Holds Power bit 17 active-low (`physw_status[0] &= ~0x00020000`) in `my_kbd_read_keys()` and post-BSS hook for 200 polls (~2.0 s) before auto-release | `physw_status[0]` @ `0x00040DAC`<br>Power bit 17 (`0x00020000`)<br>Active-low key logic: `&= ~0x00020000` | `FINSIG` | None (already implemented and active in all build variants; milestone stops early). |
| **Sibling task creation & stack size** | `chdk-port/platform/g5x/sub/100c/boot.c:479-506`<br>`chdk-port/platform/g7x/sub/100d/boot.c:382-407`<br>`chdk-port/platform/sx60hs/sub/100b/boot.c:491-518` | Implemented in active build source `full_build/g3x/sub/110c/boot.c:166-174,468`: `CreateTask_my` intercepts `task_PhySw` (0xFC1283AD), sets stack to `0x2000` (8192 B), and redirects to `mykbd_task` | `sub_fc1283d2` @ `0xFC1283D2`<br>Task `"PhySw"` @ `0xFC12870C`<br>Priority `0x17`, Stack `0x2000`<br>`j_CreateTaskStrictly` @ `0xFC31BE8C` | `ROM_VERIFIED` | None (already implemented and active in all build variants; milestone stops early). |
| **Closest sibling identification** | `chdk-port/platform/g5x/` (closest)<br>`chdk-port/platform/g7x/` (distant)<br>`chdk-port/platform/sx60hs/` (distant) | DIGIC 6 Cortex-A9, DryOS 57; direct GPIO power-cut supervision without `0x4FFC` reboot flag support. Followed by active code in `full_build/g3x/sub/110c/boot.c:398-410` | Target PID `0x32A8` (12968)<br>DryOS 57 | `INFERRED` | None (active code already follows G5 X architecture; milestone stops early). |
| **G3X Power key bit & mask** | `chdk-port/platform/g7x/kbd.c:50`<br>`chdk-port/platform/g5x/kbd.c:35`<br>`chdk-port/platform/sx60hs/kbd.c:47` | Mapped in `full_build/g3x/kbd.c:43,105` and `chdk-port/platform/g3x/kbd.c:43` as `{ 0, KEY_POWER, 0x00020000 }`; excluded from `KEYS_MASK0` (`0x000533F9`) | Word 0, bit 17 (`0x00020000`, `1u << 17`)<br>Event `0x100` (PressPowerButton) | `FINSIG` | None (`reference/finsig_gm110c/physw_bits.txt:18`, `docs/PORT46_KEYMAP.md:28`, and active code agree completely with zero discrepancy). |
| **Playback key bit & KEYS_MASK0 policy** | `chdk-port/platform/g7x/kbd.c:48`<br>`chdk-port/platform/g5x/kbd.c:33`<br>`chdk-port/platform/sx60hs/kbd.c:46` | Mapped in `full_build/g3x/kbd.c:42,106` and `chdk-port/platform/g3x/kbd.c:42` as `{ 0, KEY_PLAYBACK, 0x00010000 }`; included in `KEYS_MASK0` (`0x000533F9`) | Word 0, bit 16 (`0x00010000`, `1u << 16`)<br>Event `0x101`<br>`KEYS_MASK0 = 0x000533F9` | `HISTORICAL_CHDK` | None (Power bit 17 strictly excluded from `KEYS_MASK0` to allow normal power-off; Playback bit 16 included for ALT suppression). |
| **`physw_status` buffer address** | `chdk-port/platform/g7x/sub/100d/boot.c:382`<br>`chdk-port/platform/g5x/kbd.c:123` | Defined in `reference/finsig_gm110c/stubs_entry.S:173`; wired in active code `full_build/g3x/kbd.c:127,161` | `0x00040DAC` (`physw_status[0]`) | `FINSIG` | None (stub wired and active in `full_build/g3x/kbd.c`). |
| **`physw_run` and `physw_sleep_delay`** | `chdk-port/platform/g7x/kbd.c:73-74`<br>`chdk-port/platform/g5x/kbd.c:59-61`<br>`chdk-port/platform/sx60hs/kbd.c:72-73` | Defined in `reference/finsig_gm110c/stubs_entry.S:171-172`; wired in active code `full_build/g3x/kbd.c:167-168` | `physw_run`: `0x000082BC`<br>`physw_sleep_delay`: `0x000082C4` (10 ms) | `FINSIG` | None (`mykbd_task` loops with `_SleepTask(physw_sleep_delay)`). |
| **Power-on check & power-cut routines** | `chdk-port/platform/g5x/sub/100c/boot.c:411-420` | Implemented in active build source `full_build/g3x/sub/110c/boot.c:398-410` (`sub_fc05b962_my`), calling `sub_fc1284ac`, forcing `r0 = 1`, and jumping past `sub_fc05ba56` | `sub_fc05b962` @ `0xFC05B962`<br>`sub_fc05ba56` @ `0xFC05BA56`<br>`sub_fc1284ac` @ `0xFC1284AC` | `ROM_VERIFIED` | None (already implemented and active in all build variants; milestone stops early). |
| **Normal camera mode check** | `chdk-port/platform/sx60hs/sub/100b/boot.c:382` | Active code `full_build/g3x/sub/110c/boot.c:406` calls `sub_fc079404` before `sub_fc1284ac` | `sub_fc079404` (`IsNormalCameraMode_FW`) @ `0xFC079404`<br>ROM flag @ `0xFDF20380` | `ROM_VERIFIED` | None (wired in active code `full_build/g3x/sub/110c/boot.c:406`). |
| **Startup cause RAM retention & restore** | `chdk-port/platform/g5x/sub/100c/boot.c:168-183` | Active code `full_build/g3x/sub/110c/boot.c:66-69,141-144` and `full_build/g3x/kbd.c:129,142-163` preserves `0x00009BD0` across copy loops and restores `0x00080000` | `*(volatile unsigned int *)0x00009BD0`<br>Base `0x00009BC4` @ `0xFC08EEF0`<br>Power: `0x00080000`<br>Playback: `0x00100000` | `ROM_VERIFIED` | None (already implemented and active in all build variants; milestone stops early). |
| **Hold duration, pacing & auto release** | Owner observation (`PORT-38` trial, 2026-11) (held press of ~5 s until LED ladder finishes) | Active code `full_build/g3x/kbd.c:107,124-133` counts 200 polls @ 10 ms (`physw_sleep_delay`) = 2000 ms margin after boot ladder before auto-releasing override | Margin polls: 200 polls @ 10 ms = 2000 ms (`INFERRED`)<br>Pre-task ladder: ~5000 ms (`VERIFIED`)<br>Total hold: ~7000 ms (~7.0 s) | `INFERRED` | None (already active in `full_build/g3x/kbd.c:107,124-133`). |
| **Exact G3X file locations on build path** | `chdk-port/platform/g5x/sub/100c/boot.c:411-420`<br>`chdk-port/platform/g5x/kbd.c:118-127` | Active build sources:<br>`full_build/g3x/sub/110c/boot.c:66-69,141-144,398-410`<br>`full_build/g3x/kbd.c:124-162`<br>Overlaid via `tools/build_port41_full.py:858-861` and `scripts/build_port43_dbuf.py:2092-2095` | Overlay targets:<br>`stage_chdk/platform/g3x/sub/110c/boot.c`<br>`stage_chdk/platform/g3x/kbd.c` | `INFERRED` | None (canonical skeleton in `chdk-port/platform/g3x/sub/110c/boot.c:27-31` is unused by build scripts; active build sources already implement the fix; milestone stops early). |
| **Existing G3X code fix status (PORT-42..51 & default build)** | N/A (codebase & build pipeline audit) | **IMPLEMENTED AND ACTIVE** in default build, PORT-50 GUI_MENU combo, and PORT-51 RESTORE2 builds via `full_build` overlay. Unconditionally compiled with 0 gating `#if` directives | Active build sources:<br>`full_build/g3x/sub/110c/boot.c:66-69,141-144,398-410`<br>`full_build/g3x/kbd.c:124-162` | `HISTORICAL_CHDK` | None (milestone PORT-52 stops early). |

---

## Bounded ROM Evidence Audit

All required addresses and subroutines are verified by existing FINSIG exports (`reference/finsig_gm110c/stubs_entry.S`, `reference/finsig_gm110c/funcs_by_name.csv`, `reference/finsig_gm110c/physw_bits.txt`) and approved bounded ROM evidence entries in `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json` and `docs/port34_evidence_manifest.json`:
- `PORT24-ROM-CALLER-STARTUP`: `0xFC05B960..0xFC05B9BF` (96 B, SHA-256 `3403a6bdb72b4895d8a28cba2339318c32536439cd7ee35e06488000ccd8383d`)
- `PORT24-ROM-POWERCUT`: `0xFC05BA50..0xFC05BA6F` (32 B, SHA-256 `c7b43082682963f5df642e3d16af5971072984845a3bc0a88f31a5f54e76049c`)
- `PORT24-ROM-NORMAL-MODE`: `0xFC079400..0xFC0794BF` (192 B, SHA-256 `cc71c4d4d3014205a860babbed28baa316d475bf1932d2368b5b4cad983a8214`)
- `PORT24-ROM-NORMAL-FLAG`: `0xFDF20380..0xFDF2038F` (16 B, SHA-256 `7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64`)
- `PORT24-ROM-STARTCAUSE-SAVE`: `0xFC08ECB0..0xFC08ECFF` (80 B, SHA-256 `039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d`)
- `PORT24-ROM-STARTCAUSE-PTR`: `0xFC08EEE0..0xFC08EEFF` (32 B, SHA-256 `0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6`)
- `PORT24-ROM-POWERON-CHECK`: `0xFC1284A0..0xFC12851F` (128 B, SHA-256 `f683e2af7e75023d5e311752ab674c1a965933457698a33bf49e78f6a90e4eb0`)
- `PORT34-ROM-PHYSW-TASKCREATE`: `0xFC1283AC..0xFC128413` (104 B, SHA-256 `ac7d16ad69045ff89d81c71fba9305614b8df87d55397fa5ac096eb43f02a01c`)
- `PORT34-ROM-KBD-P1-F-LITERALS`: `0xFC12868C..0xFC12872F` (164 B, SHA-256 `bc6ca612429d161a14b2dee2d12599dbb8f9c824b4915ea8086371156f98aaee`)

Zero new ROM reads were required. Evidence manifests validate cleanly with 0 errors (`tools/port11c_evidence_validator.py`).
