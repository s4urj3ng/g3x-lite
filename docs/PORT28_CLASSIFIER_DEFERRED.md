# PORT-28 Heartbeat Classifier Deferral Record

- **Status**: Classifier **DEFERRED** `[VERIFIED: Owner direction 2026-11-02; docs/PORT28_PORT27_OUTCOME.md §2.1-§2.2]`
- **Milestone / Task**: PORT-28 former task `p28-t2` (Heartbeat Classifier) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §1]`
- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8`) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:3]`

## 1. Reason for Deferral: PORT-27 NO-GO
1. **NO-GO Outcome**: Milestone PORT-27 concluded with an UNKNOWN / NO-GO record; no `G3X_RESIDENT=1` candidate was produced and zero code was modified `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §2.1-§2.2; docs/PORT27_RESIDENT_CANDIDATE.md §1.1-§1.2]`.
2. **No DISKBOOT Hash Recorded**: `docs/PORT28_PORT27_OUTCOME.md §5` records `candidate_exists: false` and `diskboot_sha256: null` `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:185-188]`.
3. **No Trial to Ingest**: Without a resident candidate binary, there is no candidate DISKBOOT digest to pin and no physical hardware heartbeat trial to classify; the classifier will not be merged in PORT-28 `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §2.1, §3.1; Owner direction 2026-11-02]`.

## 2. Resumption Trigger
- **Trigger**: Resumption requires a `G3X_RESIDENT=1` candidate with reproducible DISKBOOT SHA-256 and byte size `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §3.1, §5]`.
- **Target Milestone**: Resumption is targeted for **PORT-29**, after authorized inspection of proposed ROM slices N1–N7 (`1,924 B`) resolves `CreateTask` calling convention and stack allocator prerequisites `[INFERRED: docs/PORT28_PORT27_OUTCOME.md §4.2-§4.3]`.

## 3. Requirements Carry-Over for Implementation

### (a) Verified Existing Decoder Behaviour
- **Standard Library Only**: Uses Python stdlib only; zero third-party dependencies `[VERIFIED: tools/port26_ladder_decode.py:122-124; docs/SAFETY.md §2]`.
- **Path Refusal Logic**: `tools/port26_ladder_decode.py` (`safe_open_report` / `validate_safety_path`) safely refuses whitespace alterations, control chars/NUL, and basenames/paths starting with `PRIMARY` or ending in `.bin`/`.rom` `[VERIFIED: tools/port26_ladder_decode.py:714-775]`.
- **Ladder Stage Table**: `LADDER_STAGE_TABLE` defines 29 checkpoints up to final checkpoint Code 44 (`STAGE_BC_PRE_FIRMWARE_CONT`) `[VERIFIED: tools/port26_ladder_decode.py:154-516]`. Future implementations must import this table directly from `tools/port26_ladder_decode.py`, not copy it.

### (b) Proposed Classifier Requirements
Future implementations must satisfy these specifications `[PROPOSED: PORT-28 milestone T2 spec; Owner direction 2026-11-02]`:
- **Dual Formats**: Support JSON and `key: value` formats via file path or inline text `[PROPOSED: PORT-28 T2 spec]`.
- **Hash Governance**: Default expected SHA-256 comes from cited doc (`docs/PORT28_PORT27_OUTCOME.md §5`, currently `null`) and can be overridden via CLI option `--expected-hash` or parameter `expected_sha256` `[PROPOSED: PORT-28 T2 spec; docs/PORT28_PORT27_OUTCOME.md §5]`.
- **Outcome Classes & Total Deterministic Precedence**: Every valid input maps deterministically to exactly one outcome class:
  1. `INCOMPLETE_REPORT`: Missing/invalid required fields/values, or unrecognized ladder codes `[PROPOSED: PORT-28 T2 spec]`.
  2. `WRONG_OR_UNKNOWN_BUILD`: Expected SHA-256 is null in cited doc or does not match report hash `[PROPOSED: PORT-28 T2 spec; docs/PORT28_PORT27_OUTCOME.md §5]`.
  3. `HEARTBEAT_OK_UI_OK`: Heartbeat blinking (~1 Hz) and stock UI usable `[PROPOSED: PORT-28 T2 spec; docs/PORT27_OWNER_TRIAL_PLAN.md §4.4(5), §5(3)]`.
  4. `HEARTBEAT_OK_UI_DEGRADED`: Heartbeat blinking and stock UI degraded `[PROPOSED: PORT-28 T2 spec; docs/PORT27_OWNER_TRIAL_PLAN.md §4.4(5), §5(3)]`.
  5. `NO_HEARTBEAT_UI_OK`: Heartbeat none/steady and stock UI usable or degraded `[PROPOSED: PORT-28 T2 spec; docs/PORT27_OWNER_TRIAL_PLAN.md §5(3)]`.
  6. `NO_HEARTBEAT_LADDER_STOPPED_AT_<code>`: Stock UI none, heartbeat none/steady, terminal code `< 44` (code 44 is final ladder checkpoint `[VERIFIED: tools/port26_ladder_decode.py:504-515]`) `[PROPOSED: PORT-28 T2 spec]`.
  7. `HANG_OR_NO_UI`: Fallback catch-all for any complete report with matching hash not matched by earlier rules (including blinking heartbeat with stock UI none, or heartbeat none/steady with code 44/no pulses) `[PROPOSED: PORT-28 T2 spec]`.

## 4. Lesson Learned from Review
- **Path Refusal vs. Inline Content**: `tools/port26_ladder_decode.py:1643-1648` refuses single-line inline text ending in `DISKBOOT.BIN` because single-line input without newlines or braces is treated as a path argument `[VERIFIED: tools/port26_ladder_decode.py:1643-1648]`. The future classifier must apply filename/path refusal only to genuine path arguments and must classify inline text or JSON containing names like `DISKBOOT.BIN` or `PRIMARY.BIN` in field values `[PROPOSED / REQUIREMENT: p28-t2 review]`.
