# PORT-24: Owner Session Sheet — Short-Press Boot Fix Candidate (GM1.10C)

**Target**: PowerShot G3 X (GM1.10C, `0x32A8`). Agents build on host only; owner runs session by hand.

## 1. Host Build & Candidate Hashes
Symbol targets: `boot_witness` @ `0x0035F7A0` [VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20; docs/PORT24_POWERON_FIX.md:10], `_end` @ `0x00366CB0` [VERIFIED: docs/PORT24_POWERON_FIX.md:10].
- **Opt-In Fix Candidate** (`G3X_POWERON_FIX=1`): `python3 -B tools/build_candidate_port24_poweron_fix.py --poweron-fix`  
  `DISKBOOT.BIN` (118,001 B) SHA-256: `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` [VERIFIED: docs/PORT24_POWERON_FIX.md:8, 276].
- **Default Control** (`G3X_POWERON_FIX=0` / O1 baseline): `python3 -B tools/build_candidate_port24_poweron_fix.py --default`  
  `DISKBOOT.BIN` (118,001 B) SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` [VERIFIED: docs/PROJECT_STATE.md:647; docs/HANDOFF.md:921; docs/PORT24_POWERON_FIX.md:7, 265].

## 2. Card Setup & File Layout (PORT-18/19 Reuse)
- **Card**: FAT32 primary partition (≤32 GB); write-protect tab **LOCKED** [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:183, 214].
- **VBR Markers**: `"BOOTDISK"` @ `0x1E0`; `"SCRIPT"` @ `0x1F0` [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:189-194; docs/PORT19_BOOTDISK_VBR.md:23, 31-34].
- **File Copy to Card Root (`A/`)** [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:198-206; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20, 50]:
  - Built at `candidate_port24_poweron_fix/DISKBOOT.BIN` -> copy to card root as `DISKBOOT.BIN`
  - Host `candidate_port24_poweron_fix/witness_inspector_gm110c.m` -> copy to card root as `extend.m`
  - Host `candidate_port24_poweron_fix/witness_inspector_payload.bin` (444 B) -> copy to card root as `WITNESS.BIN`
  - Host `printf 'for DC_scriptdisk' > /<card-root>/script.req` (17 B) -> card root `script.req`

## 3. Trial Steps & Observations (Opt-In Binary has NO LED breadcrumbs)
### Step 1: Short Power Press (Primary Trial)
1. Insert charged battery and LOCKED card. Normal short press (tap) of Power button.
2. **Observations** [INFERRED: docs/PORT24_POWERON_FIX.md:30, 252, 297; pending owner trial]:
   - *Short press boots with fix [INFERRED]*: Any Canon LED activity -> LCD backlight on -> Canon stock UI appears.
   - *Power cut recurs*: LCD backlight stays completely off/unpowered (clean power cut).
   - *Hang*: LCD backlight on (dim glow) with black screen / no UI, or camera frozen.
3. **Inspector Read (`0x0035F7A0`)**: In stock UI, press `FUNC./SET` to run `extend.m`. Record OSD readout.
   Expected: `CONT_ATTEMPTED / FRESHNESS_UNVERIFIED` (Yellow/Yellow, core `0x003489B5`) [VERIFIED: tools/port18_trial_report.py:95].
4. **Classification (`tools/port18_trial_report.py`)**:
   - Stock UI boots: `camera_behaviour: normal_stock_boot` [line 68]; with witness -> `outcome_id: O1` [lines 92-114, 1040], or without witness -> `outcome_id: O4` [lines 151-168, 1036].
   - Camera off / power cut: `camera_behaviour: no_power_on`, `outcome_id: O10` [lines 70, 248-257, 1019] (or `unclassifiable` / `O16` [lines 72, 314-323] if treating as post-loader anomaly).
   - Hang / black screen: `camera_behaviour: hang`, `outcome_id: O8` [lines 69, 222-237, 1015].

### Step 2: Held Power Press Fallback (Known-Good O1 Baseline)
1. If Step 1 cuts power, press and **HOLD Power button** continuously until LCD illuminates (~1–2 s).
2. **Observe**: Button held bypasses `sub_fc1284ac` check -> LCD illuminates -> stock UI appears [VERIFIED: owner O1 record].
3. **Inspector Read (`0x0035F7A0`)**: Press `FUNC./SET` for `extend.m` OSD readout.
4. **Classification**: `camera_behaviour: normal_stock_boot`, `outcome_id: O1` [tools/port18_trial_report.py:68, 92-114].

## 4. Recovery Procedures (docs/PORT18_OWNER_TRIAL_PLAN.md:318-338)
- **Normal Stock Boot**: Eject card OR slide switch to **UNLOCKED**; power on to boot factory firmware.
- **Hang / Freeze**: Remove battery immediately; eject card; wait 30 s; reinsert battery with card unlocked or removed.

## 5. Report-Back Checklist
- Exact `DISKBOOT.BIN` SHA-256 measured directly from card copy (`sha256sum /<card>/DISKBOOT.BIN`).
- Button action and count: number of presses tried, press duration (short tap vs held duration).
- Observations per step: Canon LED activity, LCD backlight state (unpowered vs illuminated), stock UI.
- If camera turned off: step and timing at which power cut occurred.
- Inspector readout at `0x0035F7A0` (`h_title`, `h_status`, colors, LCD photo).
- Filled `port18-report` block, `port18_trial_report.py` output, and confirmation of stock recovery.
