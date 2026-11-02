# PORT-28 Heartbeat Classifier Deferral Record

- **Status**: Classifier **DEFERRED** `[INFERRED: Owner direction 2026-11-02 (orchestrator milestone text, not a repo file), following PORT-27 NO-GO in docs/PORT28_PORT27_OUTCOME.md §2.1]`
- **Milestone / Task**: Former PORT-28 task T2 (heartbeat classifier) `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file)]`
- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8`) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:3]`

## 1. Reason for Deferral: PORT-27 NO-GO
1. **NO-GO Outcome**: Milestone PORT-27 concluded with an UNKNOWN / NO-GO record; no `G3X_RESIDENT=1` candidate was produced and zero code was modified `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §2.1-§2.2; docs/PORT27_RESIDENT_CANDIDATE.md §1.1-§1.2]`.
2. **No DISKBOOT Hash Recorded**: `docs/PORT28_PORT27_OUTCOME.md §5` records `candidate_exists: false` and `diskboot_sha256: null` `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:185-188]`.
3. **No Trial to Ingest**: Without a resident candidate binary, there is no candidate DISKBOOT digest to pin and no physical hardware heartbeat trial to classify; the classifier will not be merged in PORT-28 `[INFERRED: docs/PORT28_PORT27_OUTCOME.md §2.1, §3.1; Owner direction 2026-11-02 (orchestrator milestone text, not a repo file)]`.

## 2. Resumption Trigger
- **Trigger**: Resumption requires a `G3X_RESIDENT=1` candidate with reproducible DISKBOOT SHA-256 and byte size `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file); docs/PORT28_PORT27_OUTCOME.md §3.1, §5]`.
- **Target Milestone**: Resumption is targeted for **PORT-29**, after authorized inspection of proposed ROM slices N1–N7 (`1,924 B`) resolves `CreateTask` calling convention and stack allocator prerequisites `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file); docs/PORT28_PORT27_OUTCOME.md §4.2-§4.3]`.

## 3. Requirements Carry-Over for Implementation
Future implementations carry over the following specifications `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file)]`:
- **Standard Library Only**: Implement with Python stdlib only; zero third-party dependencies `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file); cf. tools/port26_ladder_decode.py:122]`.
- **Dual Formats**: Support JSON and `key: value` formats via file path or inline text `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file)]`.
- **Path Refusal Logic**: Binary and ROM path refusal must match `tools/port26_ladder_decode.py` (`safe_open_report` / `validate_safety_path`), refusing leading/trailing whitespace, control chars/NUL, basenames starting with `PRIMARY`, and suffixes `.bin`/`.rom` `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file); verified behaviour in tools/port26_ladder_decode.py:714-775]`.
- **Ladder Stage Table**: Must import the 29-checkpoint `LADDER_STAGE_TABLE` directly from `tools/port26_ladder_decode.py`, not copy it `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file); verified table in tools/port26_ladder_decode.py:154-516]`.
- **Hash Governance**: Default expected SHA-256 comes from cited doc (`docs/PORT28_PORT27_OUTCOME.md §5`, currently `null` `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:187]`) and can be overridden via CLI/API parameter `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file)]`.
- **Outcome Classes & Precedence Order**: The seven required outcome classes are `INCOMPLETE_REPORT`, `WRONG_OR_UNKNOWN_BUILD`, `HEARTBEAT_OK_UI_OK`, `HEARTBEAT_OK_UI_DEGRADED`, `NO_HEARTBEAT_UI_OK`, `NO_HEARTBEAT_LADDER_STOPPED_AT_<code>`, and `HANG_OR_NO_UI` (observation terms follow `docs/PORT27_OWNER_TRIAL_PLAN.md §4.4, §5`). The following deterministic precedence order and per-class trigger rules are a proposed design that a future implementer must confirm `[INFERRED: PORT-28 milestone goal, task T2 (orchestrator milestone text, not a repo file)]`:
  1. `INCOMPLETE_REPORT`: Missing or invalid required fields/values, or unrecognized ladder codes.
  2. `WRONG_OR_UNKNOWN_BUILD`: Expected SHA-256 is null in cited doc or does not match report hash.
  3. `HEARTBEAT_OK_UI_OK`: Heartbeat blinking (~1 Hz) and stock UI usable.
  4. `HEARTBEAT_OK_UI_DEGRADED`: Heartbeat blinking and stock UI degraded.
  5. `NO_HEARTBEAT_UI_OK`: Heartbeat none/steady and stock UI usable or degraded.
  6. `NO_HEARTBEAT_LADDER_STOPPED_AT_<code>`: Stock UI none, heartbeat none/steady, terminal code `< 44` (code 44 is final ladder checkpoint `[VERIFIED: tools/port26_ladder_decode.py:504-515]`).
  7. `HANG_OR_NO_UI`: Fallback catch-all for complete matching reports not matched above (e.g. blinking heartbeat with stock UI none, or heartbeat none/steady with code 44/no pulses).

## 4. Lesson Learned from Review
- **Path Refusal vs. Inline Content**: `tools/port26_ladder_decode.py:1643-1648` treats single-line input lacking newlines or braces as a file path argument, delegating to `safe_open_report` and refusing if matching forbidden names (e.g. ending in `.bin`) `[VERIFIED: tools/port26_ladder_decode.py:1643-1648]`. The future classifier must apply filename/path refusal only to genuine path arguments and must classify inline text or JSON containing names like `DISKBOOT.BIN` or `PRIMARY.BIN` in field values `[INFERRED: p28-t2 review history (orchestrator review, not a repo file)]`.
