# PORT-16 — NEEDED U1–U4 Items and Proposed ROM Ranges (No ROM Reads)

- **Document**: `docs/agentbridge/PORT16_U_CLOSE_RANGES.md`
- **Milestone**: PORT-16 (First-Boot Pipeline Triage)
- **Task ID**: `p16-u-close-ranges` (Task 63)
- **Target Platform**: Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8` = 12968 dec, DIGIC 6)
- **Source Document**: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` (commit `62e582d`, task 62)
- **Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 read-only offline investigation; zero ROM bytes read, zero binary builds, zero hardware operations) `[VERIFIED: docs/SAFETY.md:1-8]`.
- **Scope Restriction**: This document is derived exclusively from the approved triage document `docs/PORT16_FIRSTBOOT_U_TRIAGE.md`. No ROM bytes were read or quoted, no builds were executed, and no new ranges were added or altered.

---

## 0. Precheck Verification

The following precheck commands were executed prior to document creation, with output captured verbatim:

### Precheck 1: `git status --porcelain --untracked-files=all`
```text
(clean working tree, exit code 0, zero output)
```

### Precheck 2: `git log --oneline -3`
```text
baa30b3 (HEAD -> agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-close-ranges, origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/integration, agentbridge/g3x-lite/port-16-firstboot-pipeline/integration) agentbridge: integrate p16-u-triage-r15 (Triage U1-U4 for first boot (no ROM reads): carry the review)
62e582d (origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-triage-r15, agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-triage-r15) docs(p16): triage U1-U4 unknowns for first boot under narrow boundary
393b00f agentbridge: integrate p16-owner-trial-plan-r5 (Owner trial and recovery plan: carry the reviewer-corrected )
```

### Precheck 3: `git show --stat 62e582d`
```text
commit 62e582d3835f9f40990ccfe78a7d9c2c751545c8 (origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-triage-r15, agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-triage-r15)
Author: AgentBridge <agentbridge@localhost>
Date:   Fri Oct 30 13:53:12 2026 +0000

    docs(p16): triage U1-U4 unknowns for first boot under narrow boundary

 docs/PORT16_FIRSTBOOT_U_TRIAGE.md | 546 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 546 insertions(+)
```

---

## 1. Table (1): First-Boot Triage Decisions for U1–U4 Items and Sub-items

The following table lists every U1–U4 item and sub-item, its first-boot decision under the narrow first-boot boundary, and its exact line citation from `docs/PORT16_FIRSTBOOT_U_TRIAGE.md`.

Per repository architecture and triage specifications:
- **U2 Sub-items**: U2 is partitioned into U2(a), U2(b), U2(c), U2(d)-stock, and U2(d)-CHDK (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:18-22, 130-134, 194-204, 536-540`).
- **U4 Sub-items**: U4 is partitioned into U4(a), U4(b)(i), U4(b)(ii), and U4(c) (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:24-27, 136-139, 329-334, 541-543, 546`).

| Item ID | Decision | Triage Doc Line Citation (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:N`) | Full Triage Document Decision String | Epistemic Label | Scope Summary / Notes |
|---|:---:|---|---|:---:|---|
| **U1** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:17` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED]` | `CreateTask` prologue bytes and replayed literal; prototype invokes stock veneer directly (`:358-366`, veneer at `:365`); no task interception installed (`:129, 158, 411, 510`). |
| **U2(a)** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:18` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED]` | CHDK `InitFileModules` gate, replacement task and CHDK readiness latch; CHDK performs zero file access during first boot; hook absent (`:130, 206, 412, 511`). |
| **U2(b)** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:19` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED: source; INFERRED: path]` | Deferred CHDK filesystem assertions & mount state preconditions (`OBLIG-U2-04`, `OBLIG-U2-05`); boot witness written directly to DRAM; SpyTask disabled (`:131, 207, 413, 512`). |
| **U2(c)** | **`NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:20` | `NEEDED_FOR_FIRST_BOOT` | `[UNKNOWN]` | Stock SD read capability (`Fopen_Fut`, `Fread_Fut`, `Fclose_Fut` on `"A/WITNESS.BIN"`) & warm-restart SD re-enumeration without bus lockup (`OBLIG-U2-08`) (`:132, 208, 414, 442-446, 538`). |
| **U2(d)-stock** | **`NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:21` | `NEEDED_FOR_FIRST_BOOT` | `[UNKNOWN]` | Stock `task_InitFileModules` scheduler dispatch (`OBLIG-U2-02`) and normal completion of `sub_fc0d9ccc` / `sub_fc0d9cf6` (`OBLIG-U2-03`) in current boot generation (`:133, 209, 415, 485-492, 539`). |
| **U2(d)-CHDK** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:22` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED: source; INFERRED: path]` | CHDK SpyTask-driven consumption of `InitFileModules` completion; CHDK SpyTask commented out; no CHDK filesystem tasks spawned (`:134, 210, 416, 513`). |
| **U3** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:23` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[INFERRED]` | `task_PhySw` keyboard interception entry & creator; prototype launches unmodified stock `task_PhySw` (`:409`); keyboard hook disabled (`:135, 290, 417, 514`). |
| **U4(a)** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:24` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED]` | SpyTask lifecycle & launch obligations (`OBLIG-U4-01..08, 10`); SpyTask explicitly commented out (`:411-416`) for first-boot hardening (`:136, 337, 418, 515`). |
| **U4(b)(i)** | **`NOT_NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:25` | `NOT_NEEDED_FOR_FIRST_BOOT` | `[VERIFIED: source; INFERRED: path]` | Task-priority behaviour / RTOS scheduling policy (`OBLIG-U4-03`); `task_Startup_my` runs at fixed stock priority `0x19` (`:363`); stub modifies no scheduling (`:137, 338, 419, 516`). |
| **U4(b)(ii)** | **`NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:26` | `NEEDED_FOR_FIRST_BOOT` | `[UNKNOWN]` | Continuation branch runtime safety after tail branch `b.w sub_fc0d0126` (`:434`) (`OBLIG-U4-09`); inspector runs only if startup continues without crash (`:138, 339, 420, 448-452, 542`). |
| **U4(c)** | **`NEEDED`** | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:27` | `NEEDED_FOR_FIRST_BOOT` | `[UNKNOWN]` | Warm-restart semaphores / kernel re-init teardown (`OBLIG-U4-11`); lingering semaphores from aborted pre-restart tasks could induce boot freeze (`:139, 340, 421, 454-458, 543`). |

> **Note on Non-U Prerequisite Items**:  
> In addition to the U1–U4 unknowns above, `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28-31` triages four first-boot prerequisite items as `NEEDED_FOR_FIRST_BOOT`:
> 1. `Witness Addr` (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28, 140, 422, 460-466`) — Decision: `NEEDED_FOR_FIRST_BOOT`
> 2. `Dual Markers` (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:29, 141, 423, 467-472`) — Decision: `NEEDED_FOR_FIRST_BOOT`
> 3. `Witness Freshness` (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:30, 142, 424, 473-478`) — Decision: `NEEDED_FOR_FIRST_BOOT`
> 4. `Mode Transition` (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:31, 143, 425, 479-484`) — Decision: `NEEDED_FOR_FIRST_BOOT`

---

## 2. Table (2): NEEDED Items — Proposed ROM Ranges & Closability Reasons

The table below lists each item determined to be `NEEDED` for first boot. For every item, the proposed ROM range is copied exactly from the approved triage document `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` (start address, length in bytes, purpose, file:line), and each item is marked `'not ROM-closable'` with the triage document's exact reason copied verbatim.

Section 2 is presented in two parts:
- **Part A**: The 4 NEEDED items belonging to the U1–U4 unknown set (`U2(c)`, `U2(d)-stock`, `U4(b)(ii)`, `U4(c)`).
- **Part B**: The 4 additional prerequisite items needed for first boot triaged in `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28-31, 460-484` (`Witness Addr`, `Dual Markers`, `Witness Freshness`, `Mode Transition`).

### Table 2: NEEDED Items and Proposed ROM Ranges (or 'not ROM-closable' Reason)

| Item ID | Proposed ROM Range (Start, Length, Purpose, Triage Citation) | Closability Status | Triage Doc Exact Reason ('not ROM-closable') | Triage File:Line Citation |
|---|---|:---:|---|---|
| **U2(c)** | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:20, 132, 431` | **`not ROM-closable`** | The witness inspector script aborts via `exit sub` before executing or inspecting if `Fopen_Fut`, `Fread_Fut`, or `Fclose_Fut` fails on `"A/WITNESS.BIN"` (`firmware/tools/witness_inspector_gm110c.m:100-121`). `OBLIG-U2-08` covers SD host and card re-enumeration across warm restart without bus lockup (`tools/port13_u2_obligations.py:782-806`). Dynamic controller state across warm restart cannot be closed by reading static ROM bytes (`kind=ObligationKind.RUNTIME`, `tools/port13_u2_obligations.py:788`). | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:445` (also `:20, 132, 264-265`) |
| **U2(d)-stock** | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:21, 133, 431` | **`not ROM-closable`** | Whether the inspector's stock file reads depend on stock `task_InitFileModules` dispatch and normal completion cannot be shown from the cited source, and no cited boot-stub, build or inspector line shows first boot is independent of it. Both obligations are `kind=ObligationKind.RUNTIME` requiring an execution/completion witness in the current boot generation, and their notes state static ROM entry evidence cannot discharge them (`tools/port13_u2_obligations.py:634-637, 648, 659-662, 676`). | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:488` (also `:21, 133, 272-273`) |
| **U4(b)(ii)** | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:26, 138, 431` | **`not ROM-closable`** | The boot stub executes the terminal branch `b.w sub_fc0d0126` at line 434 (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`). The witness inspector only runs if Canon firmware startup continues without stack corruption, CPU exception, or hang (`tools/port13_oblig_u4.py:295-309`). Dynamic continuation execution safety across the branch cannot be settled by reading static ROM bytes (`requires_runtime_evidence=True`). | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:451` (also `:26, 138, 386-387`) |
| **U4(c)** | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:27, 139, 431` | **`not ROM-closable`** | `DISKBOOT.BIN` executes as a warm restart after stock firmware initialization (`docs/RESTART_SD_HOST_AUDIT.md:11-29`). The candidate boot stub recreates kernel state (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-258`), but RAM copy loops do not prove that lingering semaphores from aborted pre-restart tasks are harmless (`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`). If lingering semaphores induce a boot freeze (`OBLIG-U4-11`), startup halts and the inspector cannot run. Lingering RTOS state across warm restart cannot be resolved by static ROM reads (`requires_runtime_evidence=True`). | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:457` (also `:27, 139, 400-401`) |
| **Witness Addr** *(Prerequisite)* | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28, 140, 431` | **`not ROM-closable`** | Host-side build and toolchain configuration item, not a static ROM unknown. Reading static ROM bytes cannot configure host build tooling or compile inspector binaries. | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:464` (also `:28, 140, 461`) |
| **Dual Markers** *(Prerequisite)* | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:29, 141, 431` | **`not ROM-closable`** | Coexistence of volume boot record (VBR) markers (`BOOTDISK` at `0x1E0` and `SCRIPT` at `0x1F0`) and post-boot Canon Basic script triggering behavior depend on stock Canon bootloader interaction with physical SD card media formatting. This is a media formatting and bootloader interaction question, not a static ROM unknown. | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:470` (also `:29, 141, 468`) |
| **Witness Freshness** *(Prerequisite)* | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:30, 142, 431` | **`not ROM-closable`** | Candidate build configuration records a fixed nonce `0x32A80001` (`tools/build_candidate_port2a.py:783`). Inspector payload logic explicitly excludes that constant from the freshness proof (`firmware/tools/witness_inspector_payload.S:96-113`), noting that constant nonce `0x32A80001` is never considered freshness proof and proceeds to stage checks without confirming freshness. In the offline prototype script, `expected_nonce = 0` produces `FRESHNESS_UNVERIFIED` (`firmware/tools/witness_inspector_gm110c.m:28; firmware/tools/witness_inspector_payload.S:165-174`). Supplying a different or dynamic expected nonce does not close freshness: a dynamic challenge would need an independently established producer-side mechanism (such as the boot stub generating and recording a fresh unpredictable nonce per boot attempt), and no such producer-side mechanism exists in the documented candidate. This protocol and architecture gap cannot be settled by reading static ROM bytes. | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:476` (also `:30, 142, 474`) |
| **Mode Transition** *(Prerequisite)* | Start: `—`<br>Length: `0 B`<br>Purpose: `None (0 B)`<br>Citation: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:31, 143, 431` | **`not ROM-closable`** | Retained message descriptors (`h_title`, `h_status`) allocated by the inspector in Playback mode render on the camera LCD only upon transitioning the physical camera into Shooting Live View (`firmware/tools/witness_inspector_gm110c.m:185-188; docs/HANDOFF.md:1439`). This is a physical camera UI operational procedure, not a static ROM unknown. | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:482` (also `:31, 143, 480`) |

---

## 3. Total Proposed ROM Range Byte Count and Sizing Checks

Per `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:427-435, 498-503`:

1. **Total Number of Proposed ROM Ranges**: Exactly **0 ranges** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:427, 499]`.
2. **Total Byte Count**: Exactly **0 bytes** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:427, 499]`.
3. **Per-Range Constraint Check**:
   $$\text{Each proposed range length} = 0\text{ B} \le 512\text{ B} \quad (\mathbf{PASS})$$
   `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:433]`.
4. **Cumulative Total Budget Constraint Check**:
   $$\text{Total proposed range bytes} = 0\text{ B} \le 4096\text{ B} \ (4\text{ KiB}) \quad (\mathbf{PASS})$$
   `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:434, 499]`.

---

## 4. Triage Document Consistency Audit

A line-by-line comparison of all items across `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` was performed, checking:
1. First-Boot Triage Summary Table (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:13-32`)
2. Comprehensive Triage Matrix (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:125-144`)
3. Section 3 Detailed Analyses (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:147-403`)
4. Section 4 Minimal ROM Ranges & Open-Items Inventory (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:406-494`)

### Consistency Audit Result
- **Discrepancies / Inconsistencies Found**: **Zero (0)**.
- **Verification Details**:
  - `U1`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:17, 129, 158, 411, 510`); proposed ROM ranges: None (0 B).
  - `U2(a)`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:18, 130, 206, 412, 511`); proposed ROM ranges: None (0 B).
  - `U2(b)`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:19, 131, 207, 413, 512`); proposed ROM ranges: None (0 B).
  - `U2(c)`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:20, 132, 208, 414, 442-446, 538`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `U2(d)-stock`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:21, 133, 209, 415, 485-492, 539`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `U2(d)-CHDK`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:22, 134, 210, 416, 513`); proposed ROM ranges: None (0 B).
  - `U3`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:23, 135, 290, 417, 514`); proposed ROM ranges: None (0 B).
  - `U4(a)`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:24, 136, 337, 418, 515`); proposed ROM ranges: None (0 B).
  - `U4(b)(i)`: Decided `NOT_NEEDED_FOR_FIRST_BOOT` across all sections (`:25, 137, 338, 419, 516`); proposed ROM ranges: None (0 B).
  - `U4(b)(ii)`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:26, 138, 339, 420, 448-452, 542`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `U4(c)`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:27, 139, 340, 421, 454-458, 543`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `Witness Addr`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:28, 140, 422, 460-466`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `Dual Markers`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:29, 141, 423, 467-472`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `Witness Freshness`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:30, 142, 424, 473-478`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
  - `Mode Transition`: Decided `NEEDED_FOR_FIRST_BOOT` across all sections (`:31, 143, 425, 479-484`); marked 'not ROM-closable'; proposed ROM ranges: None (0 B).
- **Conclusion**: The summary table and body in `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` are 100% consistent. Zero ROM ranges were added, modified, or omitted.
