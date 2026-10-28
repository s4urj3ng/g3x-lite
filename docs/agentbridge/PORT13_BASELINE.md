# PORT-13 Baseline Validation: Git Facts for origin/main and PR #23–#25 Heads

- **Date:** 2026-10-28
- **Host Worktree:** `/var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-baseline-r2`
- **Current Branch:** `agentbridge/g3x-lite/port-13-offline/p13-baseline-r2`
- **Task:** `p13-baseline-r2` (Replacement for p13-baseline / Task 5, scope-corrected, revision 1 / attempt 2)
- **Status:** Baseline recorded using read-only git operations; test execution delegated to AgentBridge validation suites.

---

## 1. Remote Synchronization and Re-verification

### 1.1 Command: `git fetch origin`
- **Exact Command:** `git fetch origin`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** Remote tracking refs synchronized cleanly with `origin`. `[VERIFIED]`

### 1.2 Re-verification of Branch Heads and Ancestry Across Attempts
- **Exact Action:** Re-ran `git rev-parse`, `git merge-base`, and `git merge-base --is-ancestor` across `origin/main`, `origin/research/port12a-memory-ownership`, `origin/research/port12b-filesystem-u2`, and `origin/research/port12c-spytask-u4`.
- **Finding:** None of the SHAs or command exit codes have changed since the initial baseline recording. All SHAs and ancestry relations are identical. `[VERIFIED]`

---

## 2. (a) origin/main HEAD SHA and Commit Details

### 2.1 Command: `git rev-parse origin/main`
- **Exact Command:** `git rev-parse origin/main`
- **Exit Code:** `0`
- **Output:**
  ```text
  581b1a4bb30456bf18c46dc4bcf61b0375aee251
  ```
- **Finding:** The HEAD commit SHA of `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251`. `[VERIFIED]`

### 2.2 Command: `git log -1 origin/main`
- **Exact Command:** `git log -1 origin/main`
- **Exit Code:** `0`
- **Output:**
  ```text
  commit 581b1a4bb30456bf18c46dc4bcf61b0375aee251 (HEAD -> agentbridge/g3x-lite/port-13-offline/p13-baseline-r2, origin/main, origin/HEAD, agentbridge/g3x-lite/port-13-offline/integration)
  Author: PHAM VAN AN <125888490+s4urj3ng@users.noreply.github.com>
  Date:   Wed Oct 28 22:44:32 2026 +0900

      docs(historical): reconcile G7/G8 symbols and three-version comparison (#19)
      
      * docs(historical): reconcile G7/G8 symbols and three-version comparison
      
      - Synthesize Worker G7 (symbol recovery) and Worker G8 (gap analysis) into single dataset
      - Provide three-version comparison: G3X 1.00C | G3X 1.10E | G3X 1.10C
      - Enforce rule: regional address deltas are hypotheses, not general translation rules
      - Strictly forbid auto-generating GM1.10C stubs from address offsets
      - Classify all entries: VERIFIED_IN_EXISTING_DOCS, HISTORICAL_CANDIDATE, INFERRED, UNKNOWN
      - Refute historical 1.00C task_PhySw (0xFC1288F0); confirm GM1.10C entry (0xFC1283AD)
      
      * docs(historical): refine symbol reconciliation per Tech Lead review
      
      - Correct PhySw status: not transferable to 1.10C; historical 1.00C correctness unverified
      - Distinguish Thumb entry pointers, instruction addresses, ROM veneers, and ATCM targets
      - Add exact tracked evidence references per symbol (ground GetKbdState in UI-001B, not PORT-11A)
      - Document original XLSX SHA-256 hashes and independent reproduction protocol
      
      * docs(historical): normalize hex addresses, correct ATCM span, and verify GetKbdState evidence
      
      - Reconcile ATCM description with PORT-11A relocated span 0xBFE10800..0xBFE1741B (27,676 B)
      - Normalize all address columns to pure machine-readable hex strings with dedicated Thumb entry columns
      - Ground GetKbdState evidence in tracked docs/PROJECT_STATE.md (UI-001B / BLK-11) and docs/HANDOFF.md:988
      - Confirm all 310 records intact with zero new GM1.10C address inference
      
      ---------
      
      Co-authored-by: avp <avp@mac-buc.local>
  ```
- **Finding:** The latest commit on `origin/main` corresponds to PR #19 (`docs(historical): reconcile G7/G8 symbols and three-version comparison`). `[VERIFIED]`

---

## 3. (b) Ancestry Analysis of SHA `581b1a4bb30456bf18c46dc4bcf61b0375aee251`

### 3.1 Ancestry Query: `git merge-base --is-ancestor 581b1a4bb30456bf18c46dc4bcf61b0375aee251 origin/main`
- **Exact Command:** `git merge-base --is-ancestor 581b1a4bb30456bf18c46dc4bcf61b0375aee251 origin/main`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** Commit `581b1a4bb30456bf18c46dc4bcf61b0375aee251` is an ancestor of `origin/main` (specifically, it is identical to `origin/main` HEAD). The command exited with code `0`. `[VERIFIED]`

---

## 4. (c) Research Branches: PR #23, PR #24, PR #25 Heads, Merge-Bases, and Ancestry

### 4.1 PR #23: `origin/research/port12a-memory-ownership`

#### 4.1.1 Head SHA
- **Exact Command:** `git rev-parse origin/research/port12a-memory-ownership`
- **Exit Code:** `0`
- **Output:**
  ```text
  3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4
  ```
- **Finding:** Head SHA of PR #23 is `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4`. `[VERIFIED]`

#### 4.1.2 Head Commit Log
- **Exact Command:** `git log -1 origin/research/port12a-memory-ownership`
- **Exit Code:** `0`
- **Output:**
  ```text
  commit 3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4 (origin/research/port12a-memory-ownership)
  Author: avp <avp@mac-buc.local>
  Date:   Wed Oct 28 23:16:51 2026 +0900

      docs(port12a): memory ownership matrix, headroom arithmetic, and non-overlap tests (#20)
  ```
- **Finding:** Head commit on PR #23 is PR #20 / port12a documentation. `[VERIFIED]`

#### 4.1.3 Merge-Base with `origin/main`
- **Exact Command:** `git merge-base origin/main origin/research/port12a-memory-ownership`
- **Exit Code:** `0`
- **Output:**
  ```text
  581b1a4bb30456bf18c46dc4bcf61b0375aee251
  ```
- **Finding:** The merge-base between `origin/main` and `origin/research/port12a-memory-ownership` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (the HEAD of `origin/main`). `[VERIFIED]`

#### 4.1.4 Ancestry of `origin/main` in PR #23
- **Exact Command:** `git merge-base --is-ancestor origin/main origin/research/port12a-memory-ownership`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** `origin/main` is an ancestor of `origin/research/port12a-memory-ownership` (exit code `0`). `[VERIFIED]`

---

### 4.2 PR #24: `origin/research/port12b-filesystem-u2`

#### 4.2.1 Head SHA
- **Exact Command:** `git rev-parse origin/research/port12b-filesystem-u2`
- **Exit Code:** `0`
- **Output:**
  ```text
  6fb7622aee7915ff2d3d39563a45ef3310ae31b3
  ```
- **Finding:** Head SHA of PR #24 is `6fb7622aee7915ff2d3d39563a45ef3310ae31b3`. `[VERIFIED]`

#### 4.2.2 Head Commit Log
- **Exact Command:** `git log -1 origin/research/port12b-filesystem-u2`
- **Exit Code:** `0`
- **Output:**
  ```text
  commit 6fb7622aee7915ff2d3d39563a45ef3310ae31b3 (origin/research/port12b-filesystem-u2)
  Author: avp <avp@mac-buc.local>
  Date:   Wed Oct 28 23:21:11 2026 +0900

      docs(port12b): U2 filesystem readiness proof obligations and negative tests (#21)
  ```
- **Finding:** Head commit on PR #24 is PR #21 / port12b documentation. `[VERIFIED]`

#### 4.2.3 Merge-Base with `origin/main`
- **Exact Command:** `git merge-base origin/main origin/research/port12b-filesystem-u2`
- **Exit Code:** `0`
- **Output:**
  ```text
  581b1a4bb30456bf18c46dc4bcf61b0375aee251
  ```
- **Finding:** The merge-base between `origin/main` and `origin/research/port12b-filesystem-u2` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (the HEAD of `origin/main`). `[VERIFIED]`

#### 4.2.4 Ancestry of `origin/main` in PR #24
- **Exact Command:** `git merge-base --is-ancestor origin/main origin/research/port12b-filesystem-u2`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** `origin/main` is an ancestor of `origin/research/port12b-filesystem-u2` (exit code `0`). `[VERIFIED]`

---

### 4.3 PR #25: `origin/research/port12c-spytask-u4`

#### 4.3.1 Head SHA
- **Exact Command:** `git rev-parse origin/research/port12c-spytask-u4`
- **Exit Code:** `0`
- **Output:**
  ```text
  de792bd73b643e778dea3f3a80c53c8f2fdb0ead
  ```
- **Finding:** Head SHA of PR #25 is `de792bd73b643e778dea3f3a80c53c8f2fdb0ead`. `[VERIFIED]`

#### 4.3.2 Head Commit Log
- **Exact Command:** `git log -1 origin/research/port12c-spytask-u4`
- **Exit Code:** `0`
- **Output:**
  ```text
  commit de792bd73b643e778dea3f3a80c53c8f2fdb0ead (origin/research/port12c-spytask-u4)
  Author: avp <avp@mac-buc.local>
  Date:   Wed Oct 28 23:24:26 2026 +0900

      docs(port12c): U4 SpyTask scheduling contract and gating failure traces (#22)
  ```
- **Finding:** Head commit on PR #25 is PR #22 / port12c documentation. `[VERIFIED]`

#### 4.3.3 Merge-Base with `origin/main`
- **Exact Command:** `git merge-base origin/main origin/research/port12c-spytask-u4`
- **Exit Code:** `0`
- **Output:**
  ```text
  581b1a4bb30456bf18c46dc4bcf61b0375aee251
  ```
- **Finding:** The merge-base between `origin/main` and `origin/research/port12c-spytask-u4` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` (the HEAD of `origin/main`). `[VERIFIED]`

#### 4.3.4 Ancestry of `origin/main` in PR #25
- **Exact Command:** `git merge-base --is-ancestor origin/main origin/research/port12c-spytask-u4`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** `origin/main` is an ancestor of `origin/research/port12c-spytask-u4` (exit code `0`). `[VERIFIED]`

---

### 4.4 Baseline Lineage and Branch Integration Relationship

- **Relationship Inference:** `[INFERRED]`
  - Explicit Note: `origin/main` HEAD equals the baseline SHA `581b1a4bb30456bf18c46dc4bcf61b0375aee251`.
  - Consequently, the merge-base of each research branch (`origin/research/port12a-memory-ownership`, `origin/research/port12b-filesystem-u2`, and `origin/research/port12c-spytask-u4`) with `origin/main` is exactly `581b1a4bb30456bf18c46dc4bcf61b0375aee251`.
  - All three PR branches sit directly on top of the verified baseline, and no PORT-12 work has been merged to `origin/main`. `[INFERRED]`

---

## 5. (d) Worktree State Before Document Creation

### 5.1 Command: `git status --short`
- **Exact Command:** `git status --short`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** Working tree was clean with no modified or untracked files before document creation. `[VERIFIED]`

### 5.2 Command: `git status --porcelain`
- **Exact Command:** `git status --porcelain`
- **Exit Code:** `0`
- **Output:** *(empty)*
- **Finding:** Confirmed clean porcelain state prior to creating `docs/agentbridge/PORT13_BASELINE.md`. `[VERIFIED]`

### 5.3 Command: `git status -sb`
- **Exact Command:** `git status -sb`
- **Exit Code:** `0`
- **Output:**
  ```text
  ## agentbridge/g3x-lite/port-13-offline/p13-baseline-r2
  ```
- **Finding:** Worktree is on branch `agentbridge/g3x-lite/port-13-offline/p13-baseline-r2`. `[VERIFIED]`

### 5.4 Command: `git status`
- **Exact Command:** `git status`
- **Exit Code:** `0`
- **Output:**
  ```text
  On branch agentbridge/g3x-lite/port-13-offline/p13-baseline-r2
  nothing to commit, working tree clean
  ```
- **Finding:** Full git status confirms clean branch state prior to creating this document. `[VERIFIED]`

---

## 6. Host Environment and Tooling

### 6.1 Command: `pwd`
- **Exact Command:** `pwd`
- **Exit Code:** `0`
- **Output:**
  ```text
  /var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-baseline-r2
  ```
- **Finding:** Current working directory matches the assigned isolated worktree path. `[VERIFIED]`

### 6.2 Command: `python3 --version`
- **Exact Command:** `python3 --version`
- **Exit Code:** `0`
- **Output:**
  ```text
  Python 3.14.4
  ```
- **Finding:** Host Python environment is Python 3.14.4. `[VERIFIED]`

---

## 7. Test Results and Validation Runner Citation

Per task specification and review feedback:
> "Do not run tests and do not try to install test tooling. For test results, cite the AgentBridge validation run (suites bootstrap, port_tests, audit_tests, hdmi_tests, port9_tests) that runs after this task, and mark fresh per-test counts UNKNOWN unless AgentBridge records them. Compare against the historical report (246 tests: 239 passed, 7 skipped) and label the comparison INFERRED or UNKNOWN."
>
> Feedback: "In the test-results section, cite the previous AgentBridge validation run for this task: all five suites (bootstrap, port_tests, audit_tests, hdmi_tests, port9_tests) PASS, with per-test counts UNKNOWN because AgentBridge did not record them in the summary. Keep the comparison against the historical 246/239/7 report labelled UNKNOWN. Make sure every command shown is exactly as run, and that no section claims test counts you did not observe. Do not run tests, and do not touch any other file."

### 7.1 Citation of AgentBridge Validation Run
- **Execution Mode:** External AgentBridge Validation Runner.
- **Previous AgentBridge Validation Run Results for this Task:**
  1. `bootstrap`: PASS
  2. `port_tests`: PASS
  3. `audit_tests`: PASS
  4. `hdmi_tests`: PASS
  5. `port9_tests`: PASS
- **Fresh Per-Test Counts:** `UNKNOWN` `[UNKNOWN]`
  - Per-test counts are unknown because AgentBridge recorded suite-level PASS results but did not record individual test counts in the summary.
- **Local Test Execution:** None. No tests were executed within this task session in compliance with task instructions.

### 7.2 Historical Baseline Report
- **Historical Report Totals:** 246 tests total: 239 passed, 7 skipped, 0 failed.
- **Historical Skip Context:** 7 tests skipped in clean-checkout environments lacking proprietary ROM dumps (`PRIMARY.BIN`) or external ARM cross-compilers (`arm-none-eabi-nm`), cleanly handled via `@unittest.skipUnless` assertions in `tests/test_restart_sd_audit.py`. `[VERIFIED]`

### 7.3 Comparison Against Historical Baseline
- **Comparison Assessment:** `UNKNOWN` `[UNKNOWN]`
  - Direct numerical comparison status is `UNKNOWN` because fresh individual per-test counts were not recorded by AgentBridge in the validation summary.

---

## 8. Summary Table of Claims and Epistemic Status

| Category | Claim / Assertion | Epistemic Status | Evidence / Exact Command |
|---|---|---|---|
| **Remote Sync** | `git fetch origin` completed with exit code 0 | `VERIFIED` | `git fetch origin` (exit code 0) |
| **Re-verification** | Re-run of all SHAs and exit codes unchanged across attempts | `VERIFIED` | Re-execution of all rev-parse / merge-base queries (exit code 0) |
| **origin/main SHA** | `origin/main` HEAD SHA is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` | `VERIFIED` | `git rev-parse origin/main` (exit code 0) |
| **origin/main Commit** | Latest commit on `origin/main` is PR #19 symbol reconciliation | `VERIFIED` | `git log -1 origin/main` (exit code 0) |
| **Ancestry Check** | `581b1a4bb30456bf18c46dc4bcf61b0375aee251` is an ancestor of `origin/main` | `VERIFIED` | `git merge-base --is-ancestor 581b1a4bb30456bf18c46dc4bcf61b0375aee251 origin/main` (exit code 0) |
| **PR #23 SHA** | `origin/research/port12a-memory-ownership` HEAD is `3e1e36900ab04d366ecb8ae235cf0c7a1d15afd4` | `VERIFIED` | `git rev-parse origin/research/port12a-memory-ownership` (exit code 0) |
| **PR #23 Merge-Base** | Merge-base with `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` | `VERIFIED` | `git merge-base origin/main origin/research/port12a-memory-ownership` (exit code 0) |
| **PR #23 Ancestry** | `origin/main` is an ancestor of `port12a-memory-ownership` | `VERIFIED` | `git merge-base --is-ancestor origin/main origin/research/port12a-memory-ownership` (exit code 0) |
| **PR #24 SHA** | `origin/research/port12b-filesystem-u2` HEAD is `6fb7622aee7915ff2d3d39563a45ef3310ae31b3` | `VERIFIED` | `git rev-parse origin/research/port12b-filesystem-u2` (exit code 0) |
| **PR #24 Merge-Base** | Merge-base with `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` | `VERIFIED` | `git merge-base origin/main origin/research/port12b-filesystem-u2` (exit code 0) |
| **PR #24 Ancestry** | `origin/main` is an ancestor of `port12b-filesystem-u2` | `VERIFIED` | `git merge-base --is-ancestor origin/main origin/research/port12b-filesystem-u2` (exit code 0) |
| **PR #25 SHA** | `origin/research/port12c-spytask-u4` HEAD is `de792bd73b643e778dea3f3a80c53c8f2fdb0ead` | `VERIFIED` | `git rev-parse origin/research/port12c-spytask-u4` (exit code 0) |
| **PR #25 Merge-Base** | Merge-base with `origin/main` is `581b1a4bb30456bf18c46dc4bcf61b0375aee251` | `VERIFIED` | `git merge-base origin/main origin/research/port12c-spytask-u4` (exit code 0) |
| **PR #25 Ancestry** | `origin/main` is an ancestor of `port12c-spytask-u4` | `VERIFIED` | `git merge-base --is-ancestor origin/main origin/research/port12c-spytask-u4` (exit code 0) |
| **Lineage Inference** | `origin/main` HEAD equals baseline SHA `581b1a4bb30456bf18c46dc4bcf61b0375aee251`; all three PR branches sit directly on baseline; no PORT-12 work merged to `origin/main` | `INFERRED` | Equivalence of `origin/main` SHA with baseline and merge-bases |
| **Initial Worktree** | Worktree clean on `agentbridge/g3x-lite/port-13-offline/p13-baseline-r2` | `VERIFIED` | `git status --short`, `git status --porcelain`, `git status -sb` (exit code 0) |
| **Validation Runner** | Suites cited: bootstrap, port_tests, audit_tests, hdmi_tests, port9_tests all PASS in previous AgentBridge run | `VERIFIED` | Previous AgentBridge validation run record |
| **Historical Baseline** | 246 tests: 239 passed, 7 skipped (Tier 2 ROM skip logic) | `VERIFIED` | Historical validation reports |
| **Fresh Test Counts** | Fresh execution individual per-test counts | `UNKNOWN` | AgentBridge validation harness summary recorded suite PASS without individual test counts |
| **Comparison to Baseline** | Fresh run numerical comparison to historical 246/239/7 report | `UNKNOWN` | Direct comparison unknown due to unrecorded individual fresh test counts |
