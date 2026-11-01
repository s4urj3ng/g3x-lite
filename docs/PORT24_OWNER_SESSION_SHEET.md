# PORT-24: Owner Session Sheet — Short-Press Boot Fix Candidate (GM1.10C)

**Target**: PowerShot G3 X (GM1.10C, `0x32A8`). Agents build on host only; owner runs session by hand.

## 1. Host Build & Candidate Hashes
Symbol targets: `boot_witness` @ `0x0035F7A0` [VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20; docs/PORT24_POWERON_FIX.md:10], `_end` @ `0x00366CB0` [VERIFIED: docs/PORT24_POWERON_FIX.md:10].
- **Opt-In Fix Candidate** (`G3X_POWERON_FIX=1`): `python3 -B tools/build_candidate_port24_poweron_fix.py --poweron-fix --out-dir candidate_port24_poweron_fix`  
  Flag `--out-dir` [VERIFIED: tools/build_candidate_port24_poweron_fix.py:277-281]. `DISKBOOT.BIN` (118,001 B) SHA-256: `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` [VERIFIED: docs/PORT24_POWERON_FIX.md:8, 276].
- **Default Control** (optional, baseline check only, `G3X_POWERON_FIX=0`): `python3 -B tools/build_candidate_port24_poweron_fix.py --default --out-dir candidate_port24_default`  
  Flag `--out-dir` [VERIFIED: tools/build_candidate_port24_poweron_fix.py:277-281]. `DISKBOOT.BIN` (118,001 B) SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` [VERIFIED: docs/PROJECT_STATE.md:647; docs/HANDOFF.md:921; docs/PORT24_POWERON_FIX.md:7, 265].

## 2. Card Setup & File Layout (PORT-18/19 Reuse)
- **Card**: FAT32 primary partition (≤32 GB); write-protect tab **LOCKED** [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:183, 214].
- **VBR Markers**: `"BOOTDISK"` @ `0x1E0`; `"SCRIPT"` @ `0x1F0` [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:189-194; docs/PORT19_BOOTDISK_VBR.md:23, 31-34].
- **File Copy to Card Root (`A/`)** (all from opt-in `candidate_port24_poweron_fix/`) [VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:198-206; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20, 50]:
  - Built `candidate_port24_poweron_fix/DISKBOOT.BIN` -> copy to card root as `DISKBOOT.BIN`
  - Built `candidate_port24_poweron_fix/witness_inspector_gm110c.m` -> copy to card root as `extend.m`
  - Built `candidate_port24_poweron_fix/witness_inspector_payload.bin` (444 B) -> copy to card root as `WITNESS.BIN`
  - Host `printf 'for DC_scriptdisk' > /<card-root>/script.req` (17 B) -> card root `script.req`
- **HARD GATE**: Verify `sha256sum /<card>/DISKBOOT.BIN` equals `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` [VERIFIED: docs/PORT24_POWERON_FIX.md:8]. If it does not, STOP immediately and do not run the trial.

## 3. Trial Steps & Observations (Opt-In Binary has NO LED breadcrumbs)
### Step 1: Short Power Press (Primary Trial)
1. Insert charged battery and LOCKED card. Normal short press (brief tap) of Power button.
2. **Observe Boot Behavior**:
   - *Stock UI boots [INFERRED: docs/PORT24_POWERON_FIX.md:30]*: LED activity -> LCD backlight illuminates -> Canon stock UI appears.
   - *Power cut recurs*: LCD backlight remains completely unpowered/dark (clean power cut).
   - *Hang*: LCD backlight illuminates (dim glow) with black screen / no UI, or camera frozen.
3. **Inspector Activation Sequence** [VERIFIED sequence: docs/PORT19_GO_NOGO.md:164-167; docs/PORT18_OWNER_TRIAL_PLAN.md:238-247]:
   - After stock UI boots, enter Playback mode without restarting and press `FUNC./SET` once to execute `extend.m`.
   - Return to Shooting/Live View without restarting (e.g. half-press shutter) so retained OSD renders unoccluded; photograph LCD.
   - *Warning*: Skipping this sequence (e.g. pressing `FUNC./SET` outside Playback or not returning to Live View) can produce a false O4 [docs/PORT18_OWNER_TRIAL_PLAN.md:265; tools/port18_trial_report.py:1037].
4. **Classification (`tools/port18_trial_report.py:1011-1051`)**:
   - Record exact readout (`h_title`, `h_status`, colours, photo) and whether `TRACE.LOG` exists on card. Owner fills `port18-report` block and lets `port18_trial_report.py` classify.
   - *Stock UI boot* (`camera_behaviour: normal_stock_boot`): if no `TRACE.LOG` and overlay observed -> `CONT_ATTEMPTED` (Yellow) -> `O1` [tools/port18_trial_report.py:847, 1041-1042]; other readouts map to `O2` (`CORE_REACHED`), `O3` (`LOADER_REACHED`), `O6` (`WITNESS_INVALID`), `O7` (`STALE / REPLAY`), or `O13` (`SCRIPT_ERROR`) [tools/port18_trial_report.py:846-853, 1041-1042]; no overlay observed (`witness_observed: no/unknown`) -> `O4` [lines 1036-1038]. If `TRACE.LOG` is present -> `O5` if witness observed, `O14` otherwise [lines 1028-1034].
   - *Power cut / off*: `camera_behaviour: no_power_on` maps to `O15` if `TRACE.LOG` is present and to `O10` otherwise [tools/port18_trial_report.py:1019-1020] (or `unclassifiable` -> `O16` [lines 1011-1013, 1050-1051]).
   - *Hang*: `camera_behaviour: hang` maps to `O9` if `TRACE.LOG` is present and to `O8` otherwise [tools/port18_trial_report.py:1015-1016].

### Step 2: Held Power Press Fallback Procedure
1. If Step 1 cuts power, press and **HOLD Power button** continuously until LCD illuminates (~1–2 s).
2. **Status & Context**: The held-button press is VERIFIED to have reached O1 only with the default control build (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) [VERIFIED: docs/PORT24_POWERON_FIX.md:16-18; owner O1 record]. The opt-in candidate has never run on hardware, so the result of a held press with the opt-in still installed is **UNKNOWN** [VERIFIED: docs/PORT24_POWERON_FIX.md:18].
3. **Observe**: Holding button keeps GPIO 0x97 asserted so second `sub_fc1284ac` check returns 1 -> LCD illuminates -> stock UI appears [INFERRED: owner O1 record; PORT-23 T1 in docs/PORT23_POWER_SUPERVISION.md:43-50, 284-293; docs/HANDOFF.md:2251]. If the held press on the opt-in also fails, the owner can recover to the known O1 state by putting the default control DISKBOOT.BIN on the card and repeating the held press.
4. **Inspector Activation**: Use the same sequence: enter Playback without restarting, press `FUNC./SET` once, return to Shooting/Live View without restarting, photograph LCD [docs/PORT19_GO_NOGO.md:164-167; docs/PORT18_OWNER_TRIAL_PLAN.md:238-247].
5. **Classification**: Record exact readout (`h_title`, `h_status`, colours, photo) and whether `TRACE.LOG` exists. Fill `port18-report` and let `tools/port18_trial_report.py` classify using the same conditional mappings as Step 1 [tools/port18_trial_report.py:1011-1051].

## 4. Recovery Procedures (docs/PORT18_OWNER_TRIAL_PLAN.md:318-338)
- **Normal Stock Boot**: Eject card OR slide switch to **UNLOCKED**; power on to boot factory firmware.
- **Hang / Freeze**: Remove battery immediately; eject card; wait 30 s; reinsert battery with card unlocked or removed.

## 5. Report-Back Checklist
- Exact `DISKBOOT.BIN` SHA-256 measured directly from card copy (`sha256sum /<card>/DISKBOOT.BIN`).
- Button action and duration: short tap vs held press duration (~1–2 s).
- Observations per step: LED activity, LCD state (unpowered vs illuminated), stock UI. If power cut occurred, note timing.
- Inspector readout at `0x0035F7A0` (`h_title`, `h_status`, colours, LCD photo).
- Card check for `TRACE.LOG` (present: yes/no).
- Filled `port18-report` block, `port18_trial_report.py` output, and confirmation of stock recovery.
