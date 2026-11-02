# PORT-26: Code 43 Evidence Record & Short-Press Fix Deferral to GUI Step 3

**Platform**: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID `0x32A8`, DIGIC 6, DryOS 57) `[VERIFIED: README.md:3; tools/build_candidate_port2a.py:232-234]`  
**Date**: 2026-11-02  
**Task**: `p26-t8-code43-deferral-record` (Scope-reduced replacement for p26-t5 per owner instruction of 2026-11-02)  
**Status**: Recorded; short-press candidate spec deferred to GUI track Step 3 (no PORT-27 candidate spec written)  

---

## 1. PORT-25 Combined-Candidate Short-Press Result

On 2026-11-02, the owner executed a hardware trial on physical camera hardware with the PORT-25 combined candidate `[VERIFIED: owner report, 2026-11-02; docs/PORT26_TRIAL_2026-11-02.md:1-26]`:
- **Artifact**: `DISKBOOT.BIN` (size 124,865 bytes, SHA-256 `9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15`), built on the owner workstation from `origin/main` commit `2aea9cb` with `tools/build_candidate_port25_ladder_fix.py --combined` (`LED_LADDER=1` + `G3X_POWERON_FIX=1`) `[VERIFIED: owner report, 2026-11-02; docs/PORT25_LADDER_FIX_CANDIDATE.md:385; docs/PORT25_OWNER_TRIAL_PLAN.md:30, 81]`.
- **SD Card Environment**: `extend.m`, `WITNESS.BIN` (`241420a6...`, 444 bytes), and `script.req` unchanged from PORT-24 `[VERIFIED: owner report, 2026-11-02]`.
- **Operation**: Power-on 1 = short press (~100–200 ms button depression) `[VERIFIED: owner report, 2026-11-02; docs/PORT25_OWNER_TRIAL_PLAN.md:123, 139]`.
- **Optical Measurement**: High-speed video recorded at 240 fps with LED greenness measured frame by frame `[VERIFIED: owner report, 2026-11-02; docs/PORT26_TRIAL_2026-11-02.md:36]`.
- **Observed Sequence**: 7 single loader pulses (Steps 1–7), inter-phase transition gap, then core checkpoints 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 26, 31, 32, 33, 34, 35, 41, 42, 43 `[VERIFIED: owner report, 2026-11-02; docs/PORT26_TRIAL_2026-11-02.md:56-65]`.
- **Key Checkpoint Findings**:
  - Code 25 emitted directly after Code 24; Codes 28 & 29 were skipped, verifying `G3X_POWERON_FIX=1` successfully bypassed the native power cut at `sub_fc05ba56` `[VERIFIED: owner report, 2026-11-02; boot_prototype_ladder.c:361]`.
  - Code 43 (`STAGE_BC_POST_PHYSW_CREATE` at `boot_prototype_ladder.c:418`) was emitted, verifying helper `sub_fc1283d2` returned cleanly `[VERIFIED: owner report, 2026-11-02; boot_prototype_ladder.c:418]`.
  - Code 44 (`STAGE_BC_PRE_FIRMWARE_CONT` at `boot_prototype_ladder.c:442`) was NOT emitted `[VERIFIED: owner report, 2026-11-02]`.
  - Exactly 5.4 s of darkness followed Code 43 until the clip ended; rear LCD stayed dark `[VERIFIED: owner report, 2026-11-02]`.
  - Execution exhibited a single monotonic forward pass without reboot, looping, or reset; this supersedes the preliminary 30 fps reading `[VERIFIED: owner report, 2026-11-02; docs/PORT26_TRIAL_2026-11-02.md:66-69]`.
- **Decoder Output (Task p26-t4b)**:
  Running `tools/port26_ladder_decode.py tests/fixtures/port26/owner_report_2026-11-02_port25_short.json` classifies the trial output as `CODE_43` `[VERIFIED: tools/port26_ladder_decode.py:1-2258; docs/PORT26_TRIAL_2026-11-02.md:72-90]`:
  ```json
  {
    "class": "CODE_43",
    "evidence": "docs/PORT25_LADDER_FIX_CANDIDATE.md:353; boot_prototype_ladder.c:418",
    "last_stage_reached": "STAGE_BC_POST_PHYSW_CREATE",
    "next_stage": "STAGE_BC_PRE_FIRMWARE_CONT",
    "notes": "Helper-Return Checkpoint: `sub_fc1283d2` returned (does NOT prove `task_PhySw` ran) (Startup Task). Full ordered ladder sequence verified (20 checkpoints from loader through Code 43 / STAGE_BC_POST_PHYSW_CREATE). Next unreached stage: Code 44 (STAGE_BC_PRE_FIRMWARE_CONT)."
  }
  ```

---

## 2. Owner Follow-Up: Power State and Held-Press Control

Following the trial, the owner verified two additional hardware facts `[VERIFIED: owner follow-up, 2026-11-02]`:
1. **Fully-Off Power State (a)**: After the optical LED went dark at 5.4 s, the camera was confirmed to be FULLY OFF (complete power collapse, PMIC power rails dropped to zero draw), not hung in an idle, spinning, or quiescent low-power state `[VERIFIED: owner follow-up, 2026-11-02]`.
2. **Held-Press Control & Release Timing (b)**: A held press (Power-on 2 / O1 control) reaches the stock UI only if the power button remains held down continuously until the ladder finishes (i.e. throughout ladder execution until firmware handoff enters normal camera operation). Releasing the button earlier at any point during ladder execution produces the exact same shutdown behavior `[VERIFIED: owner follow-up, 2026-11-02]`.
3. **Held-Run Codes**: The optical pulse sequence for the held-press control run was not captured on video and stays UNKNOWN `[UNKNOWN: held run optical codes uncaptured, owner follow-up, 2026-11-02]`.

---

## 3. Candidate Re-Ranking (Candidates 5, 3, and 4)

Incorporating owner follow-up observations (a) and (b), Candidates 5, 3, and 4 from `docs/PORT25_SHORT_PRESS_LOCALISE.md` are re-ranked below. Every claim is labelled. **Candidate 5 ranking first is INFERRED, not VERIFIED.**

| Re-Rank | Candidate Name | Original Rank | Evidence Manifests & ROM Citations | Prior vs. Updated Status Under (a) & (b) |
|:---:|---|:---:|---|---|
| **1** | **Candidate 5: `task_PhySw` Power-Button-Release Dispatch** | Rank 5 (`docs/PORT25_SHORT_PRESS_LOCALISE.md:260, 317`) | `PORT25-ROM-PHYSW-TASK` (`0xFC1283A0..0xFC12849F`), `PORT25-ROM-PHYSW-LITERALS` (`0xFC128680..0xFC12877F`) in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json`; ROM `0xFC1283D2`, `0xFC1283AD`, `0xFC12868C`; RAM `0x00040DAC` | **Promoted to Rank 1 (Leading Hypothesis)** `[INFERRED, not VERIFIED]`. In `boot_prototype_ladder.c:418`, Code 43 confirms `sub_fc1283d2` returned cleanly, spawning `task_PhySw` (`0xFC1283AD`, priority 23, stack 2048 B) `[STATIC_VERIFIED: ROM 0xFC1283D2-0xFC1283FC]`. `task_PhySw` loops at `sub_fc12868c` polling switches/buttons into `0x00040DAC` `[STATIC_VERIFIED: ROM 0xFC12868C-0xFC128700]`. Owner observation (b) proves shutdown correlates directly with button release timing. Because `task_PhySw` is spawned right at line 413, polling button state and detecting premature release during startup to cut power directly explains the fully-off state (a) and the held-press dependency (b) `[INFERRED]`. The specific downstream shutdown edge in `task_PhySw` remains unmapped `[UNKNOWN: docs/PORT25_SHORT_PRESS_LOCALISE.md:258-261, 269-272; docs/PORT26_LADDER_NEXT_STEPS.md:170-171]`. |
| **2** | **Candidate 3: Hardware Watchdog Timer Expiry** | Rank 3 (`docs/PORT25_SHORT_PRESS_LOCALISE.md:230, 315`) | `PORT25-ROM-WATCHDOG-START` (`0xFC418F20..0xFC418F7F`), `PORT25-ROM-WATCHDOG-MODULE` (`0xFC135C00..0xFC135E3F`) in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` (also in `PORT23`, `PORT24`); ROM `0xFC418F2A`, `0xFC135D2C`, `0xFC135CB0`; MMIO `0xD20A0000`, `0xD20A0004` | **Demoted to Rank 2 (Secondary Hypothesis)** `[INFERRED]`. Armed at line 408 by `sub_fc418f2a` (`StartWDT_FW` `0xFC135D2C`), serviced by `task_WdtReset` (`0xFC135CB0`) via `SleepTask(2000)` resetting counter with `0xAA55` at `0xD20A0004` `[STATIC_VERIFIED: ROM 0xFC135CB0-0xFC135CC8, 0xFC418F2A]`. Watchdog expiry is clock-driven and cannot explain why holding the button until ladder completion prevents shutdown unless button state alters watchdog reset, for which zero evidence exists `[INFERRED]`. Additionally, watchdog underflow typically causes a hardware reset/reboot or NMI, not a clean fully-off power-down `[INFERRED]`. Hardware expiry duration and expiration action remain `[UNKNOWN: docs/PORT25_SHORT_PRESS_LOCALISE.md:226-228; docs/PORT26_LADDER_NEXT_STEPS.md:158]`. |
| **3** | **Candidate 4: Startup Cause at `0x00009BD0` (Bypassed `sub_fc08ecbc`)** | Rank 2 (`docs/PORT25_SHORT_PRESS_LOCALISE.md:246, 314`) | `PORT25-ROM-STARTCAUSE-SAVE` (`0xFC08ECB0..0xFC08ECFF`), `PORT25-ROM-STARTCAUSE-PTR` (`0xFC08EEE0..0xFC08EEFF`), `PORT25-ROM-POWERON-CHECK` (`0xFC1284A0..0xFC1285DF`) in `docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json` (also in `PORT24`, `PORT24_POWERON`); ROM `0xFC1284AC`, `0xFC08ECBC`, `0xFC08EEF0`; RAM `0x00009BD0` | **Demoted to Rank 3 (Lower Priority)** `[INFERRED]`. On short press, `sub_fc1284ac` branches past `bl sub_fc08ecbc` (`0xFC128510`), leaving `*(0x00009BD0)` unwritten by the recorder `[STATIC_VERIFIED: ROM 0xFC1284FC-0xFC12851A, 0xFC08ECBC-0xFC08ECEC]`. However, this occurs early at line 349 (`boot_prototype.c:349`) `[VERIFIED]`. If unwritten start-cause data were the sole shutdown trigger, holding the button past line 349 but releasing before ladder completion would have called `sub_fc08ecbc`, yet releasing earlier at any point still gives shutdown (b) `[INFERRED]`. Downstream consumers and shutdown reachability remain unmapped `[UNKNOWN: docs/PORT25_SHORT_PRESS_LOCALISE.md:243-246; docs/PORT26_LADDER_NEXT_STEPS.md:98]`. |

---

## 4. Deferral to GUI Track Step 3 (task_PhySw / Keyboard Hook)

Per owner instruction of 2026-11-02, project priority is shifted to the GUI track first. The short-press fix is deferred and folded directly into **GUI Track Step 3** (`task_PhySw` / keyboard hook).
- **No PORT-27 Short-Press Candidate Spec**: In accordance with the owner's directive, no PORT-27 short-press candidate specification, build tool, or diagnostic binary is generated in this task `[VERIFIED: owner directive, 2026-11-02]`.
- **Bounded UNKNOWN ROM Ranges for GUI Step 3**:
  GUI Step 3 will hook or replace `task_PhySw` with CHDK's `mykbd_task`. The ROM ranges that step will likely need are listed below as bounded UNKNOWN follow-ups only where the start address is already cited with evidence; uncited ranges are marked `range UNKNOWN`. Zero ROM was read during this task `[VERIFIED]`.

| Target Component | Start Address | Length | Purpose / Role in GUI Step 3 | Epistemic Status & Evidence Citation |
|---|:---:|:---:|---|:---:|
| **`task_PhySw` Task Entry & Spawner** | `0xFC1283A0` | 256 B | `task_PhySw` entry (`0xFC1283AD`, instruction `0xFC1283AC`) and creator helper `sub_fc1283d2` (`0xFC1283D2`) called at line 413; needed for hook/replacement by CHDK `mykbd_task` to prevent button-release shutdown | `[STATIC_VERIFIED: docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:PORT25-ROM-PHYSW-TASK; docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md:262]`; hook details `[UNKNOWN]` |
| **`task_PhySw` Polling Loop & State Literals** | `0xFC128680` | 256 B | Polling loop `sub_fc12868c` (`0xFC12868C`), literal pool containing `physw_status` pointer (`0x00040DAC`), and button mask decoding logic | `[STATIC_VERIFIED: docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json:PORT25-ROM-PHYSW-LITERALS; docs/PORT25_SHORT_PRESS_LOCALISE.md:257]`; mask details `[UNKNOWN]` |
| **`GetKbdState` Button Sampling Thunk** | `0xFC08EF66` (`0xFC08EF67`) | `range UNKNOWN` | Low-level button state accessor required by CHDK keyboard subsystem | `[VERIFIED: docs/HANDOFF.md:988; docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md:14]`; routine length `[UNKNOWN]` |
| **Button-Release Shutdown Dispatch Edge** | `range UNKNOWN` | `range UNKNOWN` | Downstream handler triggered by button release to drop GPIO 0x67 / PMIC power latch | `[UNKNOWN: start address and length uncited in existing evidence; no ROM read]` |
| **Logical UI Event Dispatch (`PostLogicalEventToUI`)** | `range UNKNOWN` | `range UNKNOWN` | Event dispatch mechanism forwarding non-power button transitions to the Canon UI queue | `[UNKNOWN: start address and length uncited in existing evidence; no ROM read]` |

---

## 5. Cross-References

- Ingestion and Optical Decode: `docs/PORT26_TRIAL_2026-11-02.md § 4` `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:72-90]`.
- Per-Class Ladder Next Steps: `docs/PORT26_LADDER_NEXT_STEPS.md § Code 43` `[VERIFIED: docs/PORT26_LADDER_NEXT_STEPS.md:167-172]`.
- Candidate Localisation Analysis: `docs/PORT25_SHORT_PRESS_LOCALISE.md § 4, § 5` `[VERIFIED: docs/PORT25_SHORT_PRESS_LOCALISE.md:181-320]`.
