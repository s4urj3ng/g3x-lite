# PORT-28 Heartbeat Classifier Deferral Record

- **Status**: Classifier **DEFERRED** `[VERIFIED: Owner direction 2026-11-02; docs/PORT28_PORT27_OUTCOME.md §2.1-§2.2]`
- **Milestone / Task**: PORT-28 former task `p28-t2` (Heartbeat Classifier) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §1]`
- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8`) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:3]`

## 1. Reason for Deferral: PORT-27 NO-GO
1. **NO-GO Outcome**: Milestone PORT-27 concluded with an UNKNOWN / NO-GO record; no `G3X_RESIDENT=1` candidate binary was produced and zero code was modified `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §2.1-§2.2; docs/PORT27_RESIDENT_CANDIDATE.md §1.1-§1.2]`.
2. **No DISKBOOT Hash Recorded**: `docs/PORT28_PORT27_OUTCOME.md §5` records `candidate_exists: false` and `diskboot_sha256: null` `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md:185-188]`.
3. **No Trial to Ingest**: Without a resident candidate binary, there is no candidate DISKBOOT digest to pin and no physical hardware heartbeat trial to classify during PORT-28; the classifier will not be merged in PORT-28 `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §2.1, §3.1; Owner direction 2026-11-02]`.

## 2. Resumption Trigger
- **Trigger**: Resumption requires the existence of a verified `G3X_RESIDENT=1` candidate binary with a reproducible DISKBOOT SHA-256 digest and byte size `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §3.1, §5]`.
- **Target Milestone**: Resumption is targeted for **PORT-29**, following the authorized read and analysis of proposed ROM slices N1–N7 (`1,924 B` total) resolving the unverified `CreateTask` calling convention and stack allocator prerequisites `[INFERRED: docs/PORT28_PORT27_OUTCOME.md §4.2-§4.3]`.

## 3. Requirements Carry-Over for Implementation
Whoever implements the heartbeat classifier in a future milestone must satisfy the following compact specifications:
1. **Pure Python Standard Library**: Stdlib only; zero third-party runtime dependencies `[VERIFIED: tools/port26_ladder_decode.py:122-124; docs/SAFETY.md §2]`.
2. **Dual Input Formats**: Support both JSON and `key: value` formats via file path, CLI arguments, or inline string `[VERIFIED: tools/port26_ladder_decode.py:1624-1665]`.
3. **Path Safety Parity**: Path refusal logic must strictly match `tools/port26_ladder_decode.py` (`safe_open_report` / `validate_safety_path`), refusing whitespace alterations, control chars/NUL, and any basename or realpath starting with `PRIMARY` or ending in `.bin`/`.rom` (case-insensitive) `[VERIFIED: tools/port26_ladder_decode.py:714-775]`.
4. **Ladder Table Import**: Import `LADDER_STAGE_TABLE` directly from `tools/port26_ladder_decode.py`; do not duplicate or copy table entries `[VERIFIED: tools/port26_ladder_decode.py:161-516]`.
5. **Expected Hash Governance**: Default expected digest comes from a cited doc (`docs/PORT28_PORT27_OUTCOME.md §5`, currently `null`) and can be overridden via CLI (`--expected-hash`) or API parameter (`expected_sha256`) `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §5; tools/port26_ladder_decode.py:149-152]`.
6. **Seven Outcome Classes & Precedence**: Evaluated with deterministic precedence:
   - `1. INCOMPLETE_REPORT`: Missing or invalid required fields/values, or unrecognised ladder codes `[INFERRED: tools/port26_ladder_decode.py:1928-1941]`.
   - `2. WRONG_OR_UNKNOWN_BUILD`: Expected SHA-256 is `None` (unrecorded candidate in cited doc) or report hash mismatch `[VERIFIED: docs/PORT28_PORT27_OUTCOME.md §5; tools/port26_ladder_decode.py:1886-1898]`.
   - `3. HEARTBEAT_OK_UI_OK`: Heartbeat blinking (~1 Hz) and stock UI usable `[INFERRED: docs/PORT27_OWNER_TRIAL_PLAN.md §5.3]`.
   - `4. HEARTBEAT_OK_UI_DEGRADED`: Heartbeat blinking and stock UI degraded `[INFERRED: docs/PORT27_OWNER_TRIAL_PLAN.md §5.3]`.
   - `5. NO_HEARTBEAT_UI_OK`: Heartbeat none/steady and stock UI usable or degraded `[INFERRED: docs/PORT27_OWNER_TRIAL_PLAN.md §5.3]`.
   - `6. NO_HEARTBEAT_LADDER_STOPPED_AT_<code>`: Stock UI none, heartbeat none/steady, and terminal ladder code `< 44` `[VERIFIED: tools/port26_ladder_decode.py:504-515]`.
   - `7. HANG_OR_NO_UI`: Stock UI none, heartbeat none/steady, terminal code 44 or no pulses (fallback hang) `[INFERRED: tools/port26_ladder_decode.py:504-515, 1900-1920]`.

## 4. Lesson Learned from Review
- **Path Refusal vs. Inline Content**: Apply filename/extension refusal strictly to genuine path arguments, never to inline report content. Inline text or JSON mentioning names such as `DISKBOOT.BIN` or `PRIMARY.BIN` inside field values (e.g. `diskboot_filename: DISKBOOT.BIN` or notes referencing `PRIMARY.BIN`) must classify without triggering path safety violations `[VERIFIED: tools/port26_ladder_decode.py:1633-1660]`.
