# PORT-46 baseline repair

Inspected 2026-11-13 at base `16158c6ef08f8f7cfba55a0dec0dd61b69c6382e`.
Host builds and regression tests only; no new ROM investigation, camera
operations or deployment. Existing tests retain their previously scoped ROM
comparisons; no research read ranges were added or widened.

| Cause | Evidence path:line | Fix |
|---|---|---|
| **VERIFIED:** stale ignored platform archive contents account for **58 failures and 39 errors**. Its `lib.o` is 3,348 B and exports an extra `update_screen_dimensions`; rebuilding from baseline source produces 3,304 B. The other five archive members are byte-identical. | Supplied `/var/lib/agentbridge/artifacts/tasks/238/attempt-3/validation-port_tests.log:4119` (PORT-24 builder refuses default hash), `:4135` and `:4344` (19 PORT-24..40 mismatches each in PORT-43 and PORT-44), `:4553` onward (58 candidate hash failures); prior diagnosis `docs/PORT45_NO_OVERDRAW.md:219`. | Move the existing six-source archive recipe into `tools/build_candidate_port2a.py:183`; rebuild privately with the pinned compiler and `ar rcsD`. Use it in every legacy core linker: `tools/build_candidate_port2a.py:518`, `tools/build_candidate_port24_poweron_fix.py:201`, `tools/build_candidate_port25_ladder_fix.py:1445`, `scripts/build_candidate_gui3.py:1762`. |
| **VERIFIED:** one additional failure treats the whole-file hash of an ignored archive as canonical. That hash includes stale contents and host timestamps/ownership; even repairing only the contents can leave a mismatch. | Supplied validation log `:5306`; prior explanation `docs/PORT45_NO_OVERDRAW.md:230`. Base version of `tests/test_port40_gui_layout.py:782` compares the entire shared archive hash, including metadata. | `tests/test_port40_gui_layout.py:773` now compares two independent source-built archives, replaces a deliberately stale private output, and asserts the shared archive is untouched. Existing candidate hash checks remain enforced, including the missing-cache GUI5 check at `tests/test_port40_gui_layout.py:795`. |
| **VERIFIED:** five additional failures on the first repaired run came from historical scope guards forbidding any shared-builder edit (including one nested no-ROM rerun), despite the explicit PORT-46 authorization. | Base `16158c6e`: `tests/test_port21_diskboot_timing.py:130`, `tests/test_port21_owner_session_plan.py:36`, `tests/test_port21_ram_lifetime.py:72`; dependent check `tests/test_port23_led_breadcrumbs.py:897`; first repaired run `out/port46-baseline/port-tests.log:5120`–`:5188` (all five failures). | Remove only the shared builder from the PORT-20 ownership restriction. Preserve the PORT-20 document/test and binary protections; the classifier regression at `tests/test_port21_ram_lifetime.py:974` now checks that the shared builder is allowed. Pinned binary compatibility checks are unchanged. |

**VERIFIED:** PORT-45 repaired only its local ignored archive
(`docs/PORT45_NO_OVERDRAW.md:224`, `:234`); this fresh worktree still contains the
stale archive. **INFERRED:** that uncommitted repair did not reach the inputs
provisioned for later worktrees. Rebuilding per candidate makes the fix durable
without changing the shared cache or requiring a manual repair step. The GUI
builder retains its existing explicit archive overrides; no flag was added.

**VERIFIED isolation experiment:** compiled the default core once, then relinked
it with only the platform archive substituted. The original archive produced
`6490ee58a8e544e2cf31bba073c274d67f9d50074a7436af372fc0b9175c96be`;
the source-built archive produced
`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`
(118,001 B), exactly the existing pin in `docs/PORT16_CANDIDATE_BUILD.md:362`.
The source-built archive hashes to
`c8eba0e13f263cb1b884f6f53ef6e055fb48e57a60ca7637e442fec98210b035`,
also matching the earlier repair record at `docs/PORT45_NO_OVERDRAW.md:235`.
The member comparison is retained locally in
`out/port46-baseline/archive-comparison.json`.

This experiment rules out compiler selection, link ordering, output paths,
timestamps in the loaded binary, and PORT-43/44/45 flag leakage as causes of
this default mismatch: the compiler, all other object inputs and flags were held constant.
All required local support inputs were present. **UNKNOWN:** a build without
the provisioned CHDK support sources/objects; this task does not replace that
existing prerequisite. No pinned expected hash or manifest was edited, and no
supersession exception was needed.

Primary repository evidence, retrieved 2026-11-13:
[PORT-45 local repair record](https://github.com/s4urj3ng/g3x-lite/blob/16158c6ef08f8f7cfba55a0dec0dd61b69c6382e/docs/PORT45_NO_OVERDRAW.md#L215-L247)
and [PORT-16 default pin](https://github.com/s4urj3ng/g3x-lite/blob/16158c6ef08f8f7cfba55a0dec0dd61b69c6382e/docs/PORT16_CANDIDATE_BUILD.md#L362).
These establish the earlier cache-only repair and the unchanged default pin,
respectively; the relink experiment above establishes causality on this host.

Validation uses normal `test_port*.py` discovery, with the one indirect witness
builder call skipped as required by `AGENTS.md:45`. The four existing PORT-27
NO-GO skips remain. The forbidden `test_validate_witness_inspector.py` is not in
this discovery pattern. To reproduce from the worktree root:

```sh
mkdir -p out/port46-baseline/tmp
TMPDIR="$PWD/out/port46-baseline/tmp" python3 -B - <<'PYTEST'
import sys
import unittest
sys.path[:0] = [".", "tools", "scripts"]
suite = unittest.defaultTestLoader.discover("tests", pattern="test_port*.py")
import test_port19_witness_address as p19
name = "test_validator_rejects_self_consistent_0035f780_under_python_optimize"
cls = p19.TestPort19WitnessAddress
setattr(cls, name, unittest.skip("AGENTS.md forbids the witness payload builder")(getattr(cls, name)))
result = unittest.TextTestRunner().run(suite)
sys.exit(not result.wasSuccessful())
PYTEST
```

**VERIFIED initial full run:** 1,428 tests in 888.466 s, with only the five
historical scope failures in the table above (five skips). Every candidate hash,
full distribution manifest, PORT-44 DBUF and PORT-45 NOOVERDRAW check passed.
The repaired PORT-21 suite passed 68/68 tests, and the dependent PORT-23 scope
check passed its focused rerun. PORT-24 passed 120/120 and PORT-17 integration
passed 12/12. `tools/validate_candidate_port2a.py` and `git diff --check` passed.
Logs are under `out/port46-baseline/` (ignored local artifacts).

**VERIFIED final full run:** **1,428 tests in 580.587 s, OK (skipped=5)**,
exit status 0, retained at `out/port46-baseline/port-tests-final.log`. This includes
all 19 PORT-24..40 candidate pins, default/GUI_FIX/FULL_HOOKS distributions,
PORT-44 DBUF and PORT-45 NOOVERDRAW manifest/reproducibility checks. The shared
archive remains unchanged at
`11b7bca6fdeb0d404af88e219f53a0d61b6f2b6a1f6be22fd3868978c975d6ee`;
the default DISKBOOT still equals the original `94682573...6136` pin.
No implementation changes were needed after the scope-check corrections.
Changes are intentionally uncommitted for AgentBridge integration; build outputs
and logs remain ignored. `PROJECT_STATE.md` and `HANDOFF.md` were not edited.
