# PORT-20: Owner Session Sheet — Loader LED Boot-Signal Trial

**Target Device**: Canon PowerShot G3 X `[VERIFIED: README.md:3]`  
**Target Firmware**: internal build `GM1.10C`, platform ID `0x32A8` (`12968`) `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:19; tools/build_candidate_port2a.py:232]`  
**Milestone**: PORT-20 (Visible Boot Signal) — Task P20-T3-owner-session `[VERIFIED]`  
**Safety Protocol**: Phase 0 is READ-ONLY regarding camera hardware `[VERIFIED: AGENTS.md:18-19; docs/SAFETY.md:3-4]`. This sheet is a one-page manual guide for the human owner to execute by hand only after explicit owner approval `[VERIFIED: docs/SAFETY.md:7; AGENTS.md:22]`. No automated agent performs hardware execution `[INFERRED: AGENTS.md:18-22]`.

---

## 1. Candidate Artifact & Host Build

The owner builds the opt-in LED candidate on the host workstation from repository root `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:51-62]`:

```bash
# Build opt-in LED candidate (writes artifacts to candidate_led/)
python3 tools/build_candidate_port2a.py --led

# Verify checksum and byte size match candidate specification exactly
sha256sum candidate_led/DISKBOOT.BIN
stat -c %s candidate_led/DISKBOOT.BIN
```

- **File for SD card root**: `candidate_led/DISKBOOT.BIN` `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:26-30, 71]`.
- **Exact Byte Size**: **`118041`** bytes (`0x1CCF1`, exactly +40 B over default build) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:71, 250]`.
- **Exact SHA-256**: **`757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286`** `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:71]`.
- **Witness Address Alignment**: Target `boot_witness` address is pinned at `0x0035F7A0` (identical across default and LED builds) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:85, 94-96]`.

---

## 2. Card Preparation (PORT-19 Setup Reuse)

Reuse the verified PORT-19 card configuration per `docs/PORT18_OWNER_TRIAL_PLAN.md:181-216` and `docs/PORT19_BOOTDISK_VBR.md:20-34`:

1. **Filesystem**: Primary partition formatted as **FAT32** (exFAT is `UNSUPPORTED`) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:183; docs/PORT19_BOOTDISK_VBR.md:24, 138-155]`.
2. **VBR Markers** (written into FAT32 volume boot sector, offset within partition):
   - `"BOOTDISK"` (8 ASCII bytes: `42 4F 4F 54 44 49 53 4B`) at VBR offset **`0x1E0`** (`480` dec) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:190; docs/PORT19_BOOTDISK_VBR.md:23, 67-69]`.
   - `"SCRIPT"` (6 ASCII bytes: `53 43 52 49 50 54`) at VBR offset **`0x1F0`** (`496` dec) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:193; docs/PORT19_BOOTDISK_VBR.md:31-34, 69-72]`.
3. **Files in Card Root (`A/`)**:
   - `DISKBOOT.BIN`: copy from `candidate_led/DISKBOOT.BIN` (`118041` bytes, SHA-256 `757dfb7f...`) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:71]`.
   - `extend.m`: copy from `candidate_led/witness_inspector_gm110c.m` (targets `0x0035F7A0`) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:94; docs/PORT18_OWNER_TRIAL_PLAN.md:201]`.
   - `WITNESS.BIN`: copy from `candidate_led/witness_inspector_payload.bin` (444 bytes, targets `0x0035F7A0`) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:95; docs/PORT18_OWNER_TRIAL_PLAN.md:202]`.
   - `script.req`: text file containing `for DC_scriptdisk` (17 bytes) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:203; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20, 49]`.
4. **Lock Card**: Run `sync`, unmount cleanly, and slide the SD write-protect switch to **LOCKED** (required by ROM check at `0xFC05BC04`) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:213-214; docs/PORT19_DISKBOOT_ENCODING.md:89-93]`.

---

## 3. What to Watch For (LED Signal & Timing)

- **Target LED**: Rear green status LED (GPIO pin 33, MMIO register `0xD20B0884`) `[VERIFIED: docs/PORT20_LED_EVIDENCE.md:23, 27; INFERRED: docs/PORT20_LED_EVIDENCE.md:28]`.
- **Signal Mechanism**: At loader entry (`0x8000`), the prologue writes action 0 (`0x004D0002`), runs a busy-wait delay of `0x06000000` (100,663,296) iterations, and writes action 1 (`0x004C0003`) before branching to `my_restart` `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:31-37, 218-230]`.
- **Polarity**: Electrical ON/OFF polarity of action 0 vs action 1 is `UNKNOWN` `[UNKNOWN: docs/PORT20_LED_EVIDENCE.md:29; docs/PORT20_LED_CANDIDATE.md:16]`. Watch for an observable **state change** on the rear green LED: either an active-ON illuminated pulse or a distinct dark OFF pause against normal standby `[INFERRED: docs/PORT20_LED_CANDIDATE.md:161]`.
- **Timing**:
  - Expected signal duration is nominal **~1.0 to 2.0 seconds** (150–250 MHz core clock) `[INFERRED: docs/PORT20_LED_CANDIDATE.md:177-189]`; strictly bounded under **5.0 seconds** even on reference PLL clocks `[INFERRED: docs/PORT20_LED_CANDIDATE.md:191-196]`.
  - Normal stock boot reaches Playback UI in ~1 s; with the LED delay, screen display is delayed by ~1-2 s (~2-3 s total after button press) `[INFERRED]`.
- **Trial Steps**:
  1. Camera powered off; insert charged battery and LOCKED trial card `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:222]`.
  2. Power on by pressing **Playback** button once; immediately observe rear green status LED and stopwatch `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:224]`.
  3. If Playback UI appears, press center **`FUNC./SET`** once to execute `extend.m`, then switch to Live View (half-press shutter) `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:238-240]`.
  4. Observe OSD readout. *Note*: on this camera, `LCDMsg_ChangeColor` index 3 renders **light blue**, not red `[VERIFIED: owner PORT-19 trial session observation; docs/PORT18_OWNER_TRIAL_PLAN.md:267]`.

---

## 4. Outcome Table & Diagnostic Conclusions

| Outcome ID | LED Signal Observed? | Camera Boot State | Inspector OSD Result | Diagnostic Conclusion | Technical Meaning & Next Step |
|:---:|:---:|:---:|:---:|:---:|---|
| **P20-O1** | **Yes** (~1-2 s pulse/pause) | Stock Playback UI up | Valid witness (`CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED`) | **`loader ran and witness valid`** `[INFERRED]` | Loader executed LED signal at `0x8000`, completed core handoff, and witness survived into stock firmware `[INFERRED]`. Photograph LCD. Full success. |
| **P20-O2** | **Yes** (~1-2 s pulse/pause) | Stock Playback UI up | Valid witness (`CORE_REACHED` or `LOADER_REACHED`) | **`loader ran and witness valid`** `[INFERRED]` | Loader executed at `0x8000` (proven by LED); intermediate stage reached `[INFERRED]`. Photograph LCD. Review later stage handoff. |
| **P20-O3** | **Yes** (~1-2 s pulse/pause) | Stock Playback UI up | Absent, clean screen, or `WITNESS_INVALID` (Light Blue) | **`loader ran, witness later overwritten`** `[INFERRED]` | Loader definitively ran at `0x8000` (proven by LED signal); missing/corrupt witness proves RAM was later zeroed or reused by DryOS `[INFERRED]`. Resolves O4 ambiguity. |
| **P20-O4** | **No** (no blink/change) | Stock Playback UI up | Absent / standard Canon UI only | **`loader never ran`** `[INFERRED]` | Custom loader was never entered `[INFERRED]`. ROM `StartDiskboot` bypassed or rejected `DISKBOOT.BIN` (check lock tab, VBR offsets, FAT32 format). |
| **P20-O5** | **No** (no blink/change) | Stock Playback UI up | Valid witness (Stage 1/2/3) | **`loader ran and witness valid`** `[INFERRED]` | Loader ran, but LED transition was unobserved or invisible due to polarity/ambient state `[INFERRED]`. Witness proves execution. |
| **P20-O6** | **Yes** (~1-2 s pulse/pause) | Hang (freeze / black screen) | N/A (unreachable) | **`hang`** `[INFERRED]` | Loader executed entry prologue at `0x8000`, but hung in delay loop, `my_restart`, `core_copy`, or stock startup `[INFERRED]`. Execute Section 5 recovery. |
| **P20-O7** | **No** (no blink/change) | Hang (freeze / black screen) | N/A (unreachable) | **`hang`** `[INFERRED]` | Crash or hang occurred before or during ROM `StartDiskboot` / decoding before loader entry `[INFERRED]`. Execute Section 5 recovery. |

---

## 5. Recovery Steps

If the camera hangs, freezes, or fails to respond normally `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:329-354]`:

1. **Remove Battery Immediately**: Open the battery compartment door and pull the battery out `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:332]`. Do not press buttons repeatedly.
2. **Remove the SD Card**: Eject the trial SD card `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:333]`.
3. **Quiescence**: Leave the camera completely without power for at least 30 seconds `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:334]`.
4. **Make Card Safe / Use Stock Card**:
   - Unlock the trial SD card (slide write-protect switch to **UNLOCKED**) `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:324, 337]`, OR
   - Insert a known standard, unbootable stock SD card, OR
   - Test with **no card** inserted `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:335]`.
5. **Restore Stock Boot**: Re-insert the charged battery with the unlocked or stock card (or no card), and power on by pressing the Playback button to confirm normal factory operation `[INFERRED: docs/PORT18_OWNER_TRIAL_PLAN.md:335-336]`.

---

## 6. What to Report Back

Record and report the following observations from the trial session:

- [ ] **Trial Date & Host Checksum**: Date of trial, host verification that `candidate_led/DISKBOOT.BIN` was `118041` bytes with SHA-256 `757dfb7f7824ba968951724416a058a6881ad99a7a7a6cf7cd6e6f0e44db5286`.
- [ ] **Card Configuration**: FAT32 verified, `BOOTDISK` at `0x1E0`, `SCRIPT` at `0x1F0`, write-protect tab locked.
- [ ] **LED Observation**:
  - Did the rear green status LED change state (blink / pulse)? (`yes` / `no`)
  - Estimated duration of changed state (e.g. 1–2 s).
  - Physical appearance: did it illuminate (active ON) or extinguish (active OFF)?
- [ ] **Camera Screen & Responsiveness**:
  - Did normal Canon Playback UI appear? (Time to screen display).
  - Or did camera hang / display black screen?
- [ ] **Inspector OSD Readout** (if stock UI reached):
  - Line 1 (`h_title`): string and color (e.g. `CONT_ATTEMPTED` in Yellow, or `WITNESS_INVALID` in Light Blue).
  - Line 2 (`h_status`): string and color (e.g. `FRESHNESS_UNVERIFIED` in Yellow).
  - Digital photograph of the LCD overlay.
- [ ] **Outcome Classification**: Matched Outcome ID (`P20-O1` through `P20-O7`) and conclusion (`loader never ran`, `loader ran, witness later overwritten`, `loader ran and witness valid`, or `hang`).
- [ ] **Recovery Result**: Confirmation that camera recovered and booted normally when card was unlocked or removed.
