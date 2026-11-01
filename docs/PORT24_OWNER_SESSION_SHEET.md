# PORT-24: Owner Session Sheet — Short-Press Fix Candidate (GM1.10C)

**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID `0x32A8`).  
**Protocol**: Phase 0 Read-Only. Manual owner trial only; no automated hardware execution.

## 1. Host Build & Expected Hashes (docs/PORT24_POWERON_FIX.md)
Symbol targets preserved: `boot_witness` @ `0x0035F7A0`, `_end` @ `0x00366CB0`.
- **Opt-in Candidate** (`G3X_POWERON_FIX=1`):
  `python3 -B tools/build_candidate_port24_poweron_fix.py --poweron-fix`
  `DISKBOOT.BIN` (`118,001` B) SHA-256: `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`
- **Default Control** (`G3X_POWERON_FIX=0` / PORT-19 baseline):
  `python3 -B tools/build_candidate_port24_poweron_fix.py --default`
  `DISKBOOT.BIN` (`118,001` B) SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`

## 2. Card Setup (PORT-18/19/23 Reuse)
- **Format & Lock**: FAT32 primary partition; write-protect tab set to **LOCKED**.
- **VBR Markers**: `"BOOTDISK"` at offset `0x1E0` (480); `"SCRIPT"` at offset `0x1F0` (496).
- **Files on Card Root (`A/`)**: `candidate_port24_poweron_fix/DISKBOOT.BIN`, `witness_inspector_gm110c.m` (as `extend.m`), `witness_inspector_payload.bin` (as `WITNESS.BIN`, 444 B, targets `0x0035F7A0`), `script.req` (`for DC_scriptdisk`).

## 3. Trial Steps & Observations
### Step 1: Short Power Press (Opt-In Fix Primary Trial)
1. Insert charged battery and LOCKED card. Perform a **normal short press (tap)** of the Power button.
2. **Observe**:
   - *Fix succeeds (expected)*: Rear green LED lights -> LCD illuminates -> Canon stock UI appears.
   - *Power cut recurs*: Rear green LED dark -> LCD completely unpowered and dark.
3. **Inspector Read (0x0035F7A0)**: In stock UI, press `FUNC./SET` to run `extend.m`.
   - Expected: `CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED` (Yellow/Yellow, core `0x003489B5`).
   - Overwritten by DryOS heap: `WITNESS_INVALID` / `INVALID / CORRUPT` (Light Blue).
4. **Classification (`tools/port18_trial_report.py`)**:
   - Stock UI reached + valid witness: `camera_behaviour: normal_stock_boot`, `outcome_id: O1`.
   - Immediate power cut (LCD unpowered): `camera_behaviour: no_power_on`, `outcome_id: O10`.

### Step 2: Held Power Press Fallback (Known-Good O1 Baseline)
1. If Step 1 cuts power, press and **HOLD Power button continuously** until LCD lights (~1–2 s).
2. **Observe**: Power button held through Stage 5 check (`sub_fc1284ac`) -> power cut bypassed -> stock UI appears.
3. **Inspector Read (0x0035F7A0)**: Press `FUNC./SET` to run `extend.m`; record OSD readout.
4. **Classification (`tools/port18_trial_report.py`)**: `camera_behaviour: normal_stock_boot`, `outcome_id: O1`.

## 4. Classification with `port18_trial_report.py`
Record trial data in a `port18-report` block (`candidate_sha256`, `candidate_size`, `trial_date`, `card_prepared: yes`, `camera_behaviour`, `witness_observed`, `trace_log_present: no`, `trace_log_path: none`, `witness_dump_path: none`, `outcome_id`, `notes`).
Validate & ingest: `python3 -B tools/port18_trial_report.py <report_file> --json`

## 5. Recovery Procedures
- **Normal Stock Boot**: Eject card OR slide switch to **UNLOCKED**; power on to boot factory firmware.
- **Hang / Freeze Recovery**: If camera freezes, pull battery immediately; eject card; wait 30 s; reinsert battery with card unlocked or removed.

## 6. What to Report Back
- Host DISKBOOT SHA-256 and byte size verification.
- Observations for each step: button action (short tap vs held duration), rear LED state, LCD backlight/UI state.
- Inspector readout at `0x0035F7A0`: `h_title`, `h_status`, colors, and digital photograph of LCD.
- Filled `port18-report` and `port18_trial_report.py` output; confirmation of stock recovery.
