# PORT-11B adversarial QA revalidation

Date / retrieval date: **2026-10-28**. Reviewer: **Gemini Coordinator / Codex Integration (Worker G1)**.  
Current reference: Merged `origin/main` baseline [commit 7f39946010b802a4440b92f20e0cfd8fb9eb8916](https://github.com/s4urj3ng/g3x-lite/commit/7f39946010b802a4440b92f20e0cfd8fb9eb8916) (post-PR #16 merge).  
Prior reference: [PR #16](https://github.com/s4urj3ng/g3x-lite/pull/16) head `4e2f7929b0c8ebc890a065fb6f9a83215ce2e60c`.  
Original QA commit: `38710842cfbcf04079de583abd6e12c480868f53`, revalidated in `faeebac7727022a353f641daffcd2f414f67d94a`.  
Isolated branch: `test/port11b-adversarial-qa`.

**Recommendation: PASS revalidation.** All 21 adversarial test methods pass against the current merged `origin/main` baseline (`7f39946`). The previously identified trace-validator defect (QA-N1 / multiple `create_replaced` after fault) was resolved in PR #16 commit `dcf1b19` ("fix(port11b): consolidate worker additions for generation reset, fs_failed invariant, and N1 mutation pairs"). No genuine new regression was found in this revalidation. Production model, runtime contract, and default preconditions remain fail-closed. Hardware **STRICT NO-GO**.

---

## Isolation and procedure

- Established current `origin/main` SHA `7f39946010b802a4440b92f20e0cfd8fb9eb8916`.
- Branched isolated worktree `test/port11b-adversarial-qa` directly from `origin/main`.
- Selectively imported the 21 adversarial test methods from Codex's local QA commit `faeebac7727022a353f641daffcd2f414f67d94a` without modifying any production code or reverting merged PR #16 fixes.
- Ran all 21 test methods against current `origin/main`: **21 passed, 0 failed, 0 errors, 0 skips**.
- Ran full runtime lifecycle, contract, and adversarial test suites: **138 tests passed** (PORT-9A: 32 tests, PORT-9B: 85 tests, PORT-11B Adversarial: 21 tests).
- Verified that this worktree modifies only two files:
  - `tests/test_port11b_adversarial.py`
  - `docs/PORT11B_ADVERSARIAL_FINDINGS.md`

---

## Classification of prior failures and resolutions

| Group | Failures at `a21af676` | Failures at `4e2f7929` | Failures at `7f399460` (Merged Main) | Classification |
|---|---:|---:|---:|---|
| **K1**: invalid/stale/ambiguous evidence after READY | 13 subcases | 0 | **0** | **Verified fixed in PR #16** |
| **K2**: stock singleton before intercept | 2 subcases | 0 | **0** | **Verified fixed in PR #16** |
| **K3**: hypothetical override of supplied UNKNOWN contracts | 1 method | 0 | **0** | **Verified fixed in PR #16** |
| **QA-N1**: later replacement after fault hidden by earlier replacement | 2 subcases | 2 | **0** | **Verified fixed in PR #16 (`dcf1b19`)** |
| Genuine new regressions | 0 | 0 | **0** | None detected across all 21 methods |

### Detailed Resolution of QA-N1

In pre-merge baseline `4e2f7929`, `check_trace()` checked `create_replaced` events following a fault using a single-index break or early termination, allowing a second `create_replaced` for a different task to bypass validation if an earlier replacement was already recorded. In PR #16 consolidation commit `dcf1b19`, `check_trace()` in `tools/port9a_runtime_lifecycle.py` and `tools/port9b_runtime_contract.py` was hardened to scan all post-fault entries and reject any `create_replaced` event regardless of order or multiplicity:

```python
# tools/port9a_runtime_lifecycle.py
for event, payload in trace[fault_idx + 1:]:
    if event == "create_replaced":
        errors.append(f"Trace violation: replacement '{payload}' occurred after fault")
```

Both subcases of `test_N1_every_replacement_after_fault_is_rejected_by_trace_validator` (testing `TASKS[0] -> TASKS[1]` and `TASKS[1] -> TASKS[0]` permutations) and the positive control `test_first_post_fault_replacement_is_detected_positive_control` now pass cleanly.

---

## Verified Test Suites

| Suite | Command | Result |
|---|---|---|
| PORT-11B Adversarial QA | `python3 -m unittest tests/test_port11b_adversarial.py` | **21/21 PASS** (0.36s) |
| PORT-9A Runtime Lifecycle | `python3 -m unittest tests/test_port9a_runtime_lifecycle.py` | **32/32 PASS** (0.01s) |
| PORT-9B Runtime Contract | `python3 -m unittest tests/test_port9b_runtime_contract.py` | **85/85 PASS** (2.12s) |
| **Combined Lifecycle + Contract + QA** | `python3 -m unittest tests/test_port9a_runtime_lifecycle.py tests/test_port9b_runtime_contract.py tests/test_port11b_adversarial.py` | **138/138 PASS** (2.50s) |

---

## Negative Coverage Preservation

The 21 adversarial test methods are fully preserved and provide durable regression protection across four areas:
1. **Bounded Filesystem Exploration (7 methods)**: Verifies that missing, ambiguous, out-of-order, or failed filesystem mount witnesses cannot promote `core_spytask_can_start` to `True`.
2. **Contract Structure Controls (2 methods)**: Verifies that empty, duplicated, or missing hook requirements fail contract verification (C6).
3. **Creation & Authorization Matrices (7 methods)**: Verifies that untrusted caller context, unauthorized task names, and duplicate task interceptions fail closed.
4. **Post-Fault Trace Controls (5 methods)**: Verifies that after any reported fault, no replacement tasks can be spawned or permitted in execution traces.
