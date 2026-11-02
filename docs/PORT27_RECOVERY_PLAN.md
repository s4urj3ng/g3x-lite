# PORT-27: Resident Heartbeat Recovery Plan & Reference (NO-GO Record)

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Milestone / Task**: PORT-27 T4 (`p27-t4-trial-recovery-plan`)
- **Baseline Candidate Document**: `docs/PORT27_RESIDENT_CANDIDATE.md`
- **Canonical Baseline Recovery Reference**: `docs/PORT25_OWNER_TRIAL_PLAN.md:334-369` (Section 5: Recovery Procedures) `[VERIFIED]`
- **Milestone Status / Verdict**: **NO TRIAL THIS MILESTONE (NO-GO RECORD)** `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:6-32; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]`
- **Candidate Production Status**: **No candidate produced**; zero code modified; build invariance preserved `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`

---

## 1. Milestone NO-GO Note & Reference to PORT-25 Recovery Plan

In milestone PORT-27, task T2 concluded with a strict **NO-GO record** because Item (b) DryOS `CreateTask` calling convention parameter semantics are `[INFERRED]` rather than `[VERIFIED]`, and internal callees (`0xBFE10B88`, `0xBFE10D14`, `0xBFE13E78`) lie outside the authorized read policy boundary `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:20-26; docs/PORT27_RESIDENT_EVIDENCE.md:575-580]`.

In accordance with milestone instructions:
> *"If T2 was NO-GO, write the trial plan as a 'no trial this milestone' note that carries the UNKNOWN list and the proposed next ROM ranges, and skip the recovery plan beyond a reference to the PORT-25 recovery plan."*

Therefore, for milestone PORT-27:
1. **No Hardware Trial Conducted**: Zero code changes were committed to `chdk-port/` or `tools/`, no resident candidate binary was produced, and no physical hardware trial was conducted `[VERIFIED: docs/PORT27_RESIDENT_CANDIDATE.md:28-32]`. There is zero physical hardware risk in PORT-27.
2. **Canonical Recovery Reference**: Detailed hardware recovery procedures and non-destructive invariants for the PowerShot G3 X are established in **`docs/PORT25_OWNER_TRIAL_PLAN.md:334-369` (Section 5: Recovery Procedures)** `[VERIFIED: docs/PORT25_OWNER_TRIAL_PLAN.md:334-369; docs/PORT18_OWNER_TRIAL_PLAN.md:318-355]`. If hardware trials resume in future milestones when a candidate is produced, all recovery operations (battery pull, 30-second capacitor discharge, SD card unlock/removal, and stock restart verification in Playback mode) and mandatory stop conditions will follow Section 5 of `docs/PORT25_OWNER_TRIAL_PLAN.md`.

---

## 2. Boot Method & Scope Restrictions

1. **Held-Press Boot Method**: The only verified boot method for reaching the stock UI in current prototype builds is the **Held-Press Boot Method** (pressing and holding the Power button down continuously until all ladder codes finish and the LCD displays the Canon stock UI) `[VERIFIED: docs/PORT26_CODE43_RECORD.md:40-44; docs/PORT26_TRIAL_2026-11-02.md:92-96]`.
2. **Short-Press Shutdown is Explicitly Out of Scope**: Short-press shutdown was localized in PORT-26 to **Code 43** (`task_Startup_my` helper-return checkpoint) `[VERIFIED: docs/PORT26_TRIAL_2026-11-02.md:63-65; docs/PORT26_CODE43_RECORD.md:12-38]`. The earlier power-check shutdown explanation is superseded (`docs/PORT23_POWER_SUPERVISION.md:43-50, 285-294` `[INFERRED / SUPERSEDED]`), and the remaining short-press shutdown mechanism at Code 43 is `[UNKNOWN: docs/PORT23_POWER_SUPERVISION.md:50, 294; docs/PORT26_CODE43_RECORD.md:38]`. By owner priority direction on 2026-11-02, short-press shutdown is deferred to Step 3 (`task_PhySw` hook / keyboard polling) `[VERIFIED: docs/PORT26_CODE43_RECORD.md:59-62]`. Short-press trials are NOT to be conducted for resident heartbeat testing.
