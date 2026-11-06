# PORT-33: Owner Trial Plan — Opt-In `G3X_OSD=1` Overlay Candidate (GM1.10C)

**Target**: Canon PowerShot G3 X (`GM1.10C`, Platform ID `0x32A8`). Phase 0 safety rules apply (`docs/SAFETY.md`): agents build on the host only; the owner executes the hardware trial by hand. Candidate is strictly a RAM-only candidate (`DISKBOOT.BIN`), with zero firmware flashing.

## 1. Candidate Build & Artifact Pin (`docs/PORT33_OSD_ADDRESSES.md` §1)

| Field | Value |
|:---|:---|
| **Pinned Toolchain** | `toolchains/gcc-arm-none-eabi-5_4-2016q3` (`arm-none-eabi-gcc` 5.4.1 20160919) |
| **Build Command** | `G3X_OSD=1 python3 -B tools/build_candidate_port25_ladder_fix.py --osd --out-dir <dir>` |
| **Candidate `DISKBOOT.BIN` SHA-256** | `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` |
| **Candidate Sizes & Bounds** | `DISKBOOT.BIN`: `124,833` B; loaded `candidate_main.bin`: `123,392` B; linked `_end`: `0x00368660` $\le$ heap start `0x00368680` (`32` B clearance) |
| **Expected Heartbeat** | Rear green LED (`0xD20B0884`) double short blink at **~1.0 Hz** (`100 ms ON -> 100 ms OFF -> 100 ms ON -> 700 ms OFF`) |
| **Expected Test Overlay** | 120x40 px opaque rectangle near top-left `(16, 16)`: 2px white border, checkerboard tiles, "CHDK" text; redrawn every ~1 s for $\ge 30\text{ s}$ |

## 2. Held-Press Boot Procedure (At Most 2 Power-Ons)

- **Card Prep & Hard Gate**: Copy `DISKBOOT.BIN` to root (`A/DISKBOOT.BIN`) of FAT32 `BOOTDISK` SD card (`0x1E0` marker). Check `sha256sum <card>/DISKBOOT.BIN` equals `683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855` (STOP if mismatch). Unmount and slide write-protect switch to **LOCKED**.
- **Execution Order**:
  1. **Confirm PORT-32 heartbeat first**: Power on with button held continuously through PORT-25 ladder (`1..7`, `11..44`). After `Code 44`, release button and confirm rear green LED heartbeat (~1.0 Hz double-blink, distinct from the PORT-25 ladder).
  2. **Look for overlay second**: Observe LCD screen near top-left corner `(16, 16)` for $\ge 30\text{ s}$ to confirm test overlay persistence.
- **Power-On Limit (Max 2)**: Power-on 1 is primary. Power-on 2 is an optional repeat only if button was released early or to verify repeatability after clean recovery. Never exceed **2 power-ons**.

## 3. Observation & Result Mapping Table

| Observed Outcome | Meaning | Next Action | Implicated Address Table Rows (`docs/PORT33_OSD_ADDRESSES.md` §2) |
|:---|:---|:---|:---|
| **1. No heartbeat** | Step 1 regression (resident core failed before or during task spawn) | Fix resident path; ignore overlay | **Implicates**: `CreateTask` (`0xBFE14A3D`), `dryos_heap_base` (`0x00368680`), `SleepTask` veneer (`0xFC31BF84`), `sub_fc0d0126`, `G3X_LED_MMIO_ADDR` (`0xD20B0884`). |
| **2. Heartbeat present, no overlay** | Resident OK; overlay addresses or buffer pointers incorrect | Retain resident task; fix overlay addresses / buffers | **Suspected first (`INFERRED`/`FINSIG`)**: 1) `active_bitmap_buffer` (`0x0000D2A4`), 2) `bitmap_buffer` (`0x0000D2A8`), 3) `transfer_src_overlay` (`0xFC380635`), 4) `opacity_buffer` (`0xFC1837FC`), 5) `CreateTask` ("OSDOverlay" task spawn failure). |
| **3. Overlay garbled, wrong colour, or offset** | Buffer format, stride pitch, or opacity byte issue | Fix geometry constants, UYVY color pack, or opacity format | **Implicates**: `CAM_BITMAP_WIDTH` (`736` pitch), `CAM_SCREEN_WIDTH`/`HEIGHT` (`720x480`), `G3X_UYVY_WHITE`/`DARK`/`MEDIUM` color words, `opacity_buffer` (`0xFC1837FC`) format. |
| **4. Overlay flickers or vanishes** | Active-buffer index or compositor refresh sync issue | Fix ping-pong buffer indexing and refresh synchronization | **Implicates**: `active_bitmap_buffer` (`0x0000D2A4` ping-pong index toggle), `transfer_src_overlay` (`0xFC380635` refresh blit target `n` vs `n ^ 1`), or refresh loop interval. |
| **5. Overlay steady $\ge 30\text{ s}$ + heartbeat** | Full success: multi-tasking resident core and display pipeline verified | **GO for Step 3 (kbd / ALT mode)** | **Confirms all rows**: `CreateTask`, `SleepTask`, `dryos_heap_base`, `active_bitmap_buffer`, `bitmap_buffer`, `opacity_buffer`, `transfer_src_overlay`, `G3X_LED_MMIO_ADDR`, and display geometry. |

## 4. Recovery Procedure (Battery Pull -> Normal Boot Without Candidate)

1. **Battery Pull**: Open battery door, pull the NB-10L battery, eject SD card, and wait **30 seconds** for full capacitor discharge.
2. **Remove Candidate**: Slide SD card tab to **UNLOCKED** (or remove card / delete `A/DISKBOOT.BIN`).
3. **Normal Stock Boot**: Reinsert battery, close door, and power on normally **without candidate** to confirm clean stock GM1.10C UI operation.

## 5. What the Owner Should Record

Record a plain-text note with these items (plus confirmed SD card SHA-256 and total power-on count `1` or `2`):
- **Timing**: Ladder completion code seen, heartbeat start/rate (~1 Hz), and how long overlay persisted ($\ge 30\text{ s}$, transient, or none).
- **Position**: Exact screen location of overlay (confirming near top-left corner `(16, 16)` vs shifted/clipped).
- **Colours**: Appearance of white 2px border, checkerboard tiles, and "CHDK" text (crisp white/grey/dark vs inverted/discoloured).
- **Photo**: If possible, a photo of the rear LCD screen displaying the overlay over the stock UI.
- **Stock UI Side Effects**: Any UI glitches, dial/button unresponsiveness, live view stutter, or abnormal shutdown.
