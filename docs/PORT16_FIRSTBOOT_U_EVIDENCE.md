# PORT-16 — Evidence Closure for First-Boot Unknowns (U1–U4) and Validated Evidence Manifest

- **Document**: `docs/PORT16_FIRSTBOOT_U_EVIDENCE.md`
- **Milestone**: PORT-16 (First-Boot Pipeline Triage & Evidence Closure)
- **Task ID**: `p16-u-close` (Task 64)
- **Target Platform**: Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8` = 12968 dec, DIGIC 6)
- **Inputs**:
  1. Approved Triage Document: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` (task `p16-u-triage-r15`, commit `62e582d`)
  2. NEEDED-Item Range List: `docs/agentbridge/PORT16_U_CLOSE_RANGES.md` (task `p16-u-close-ranges`, id 63, commit `b4b45cb`)
- **Deliverables**:
  1. `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json`
  2. `docs/agentbridge/PORT16_TRUSTED_SCOPES.json`
  3. `docs/PORT16_FIRSTBOOT_U_EVIDENCE.md` (this document)
- **Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 read-only offline investigation; zero ROM bytes read from `PRIMARY.BIN`, zero binary builds, zero hardware operations) `[VERIFIED: docs/SAFETY.md:1-8]`.
- **Scope Restriction**: All claims in this document strictly enforce the narrow first-boot boundary. Infer no addresses, offsets, or CPU mode beyond what the tracked files and cited repository documentation establish `[VERIFIED]`.

---

## 1. Executive Summary & Authorisation Evaluation

### 1.1 Task Mandate and Range Budget Enforcement
Task `p16-u-close` directs:
1. Inputs: the approved triage document `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` and the NEEDED-item range list committed by task `p16-u-close-ranges` (`docs/agentbridge/PORT16_U_CLOSE_RANGES.md`).
2. Tech Lead Authorisation: Authorises reading exactly the ROM ranges in that id-63 list and nothing else from `firmware/dumps/GM1.10C/PRIMARY.BIN` with `python3 -B` (seek and read only those offsets).
3. Hard Limits:
   - Each individual range is at most 512 bytes.
   - All ranges together are at most 4096 bytes (4 KiB).
   - Read no range that is not in the id-63 list.
   - Never scan the full ROM.
   - If the id-63 list has no NEEDED items with closable ROM ranges, read nothing and record that in the evidence document.

### 1.2 Evaluation of the id-63 Range List
Inspection of `docs/agentbridge/PORT16_U_CLOSE_RANGES.md:74-109` reveals:
- **Total Proposed ROM Ranges**: Exactly **0 ranges** `[VERIFIED: docs/agentbridge/PORT16_U_CLOSE_RANGES.md:101; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:427, 499]`.
- **Total Authorized Byte Count**: Exactly **0 bytes** `[VERIFIED: docs/agentbridge/PORT16_U_CLOSE_RANGES.md:102; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:427, 499]`.
- **Reason**: Every item determined to be `NEEDED` for first boot under the narrow first-boot boundary (`U2(c)`, `U2(d)-stock`, `U4(b)(ii)`, `U4(c)`, and the four prerequisites `Witness Addr`, `Dual Markers`, `Witness Freshness`, `Mode Transition`) is explicitly triaged as **`not ROM-closable`** `[VERIFIED: docs/agentbridge/PORT16_U_CLOSE_RANGES.md:86-93; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:442-493]`.
- **Action Taken**: In strict compliance with the instruction *"If the id-63 list has no NEEDED items [with ROM ranges], read nothing and record that in the evidence doc"*, **zero bytes were seeked or read from `firmware/dumps/GM1.10C/PRIMARY.BIN`** `[VERIFIED]`. Zero full-ROM scans were executed `[VERIFIED]`.

### 1.3 Budget and Constraint Verification Table

| Constraint / Limit | Mandated Limit | Actual Applied | Status | Citation |
|---|:---:|:---:|:---:|---|
| **Max Bytes Per Range** | $\le 512\text{ B}$ | $0\text{ B}$ | **PASS** | `docs/agentbridge/PORT16_U_CLOSE_RANGES.md:104-105` |
| **Max Cumulative Bytes** | $\le 4096\text{ B}$ (4 KiB) | $0\text{ B}$ | **PASS** | `docs/agentbridge/PORT16_U_CLOSE_RANGES.md:107-108` |
| **Out-of-Scope Range Reads** | Strictly 0 | 0 | **PASS** | `docs/SAFETY.md:1-8` |
| **Full ROM Scans** | Strictly 0 | 0 | **PASS** | `docs/PORT11C_EVIDENCE_HARNESS.md:49-53` |
| **ROM Dumps Opened** | None | 0 (`PRIMARY.BIN` not opened) | **PASS** | `docs/SAFETY.md:1-8` |
| **External Packages / Toolchain** | Standard library only (`python3 -B`) | Standard library only | **PASS** | `tools/port11c_evidence_validator.py:18-19` |

---

## 2. Precheck and Environment Verification

Prior to document and manifest creation, repository state and commit history were verified:

### 2.1 Working Tree Status: `git status --porcelain --untracked-files=all`
```text
(clean working tree prior to task deliverables, exit code 0)
```

### 2.2 Baseline Commit History: `git log --oneline -4`
```text
fcdfdd6 (HEAD -> agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-close, origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/integration) agentbridge: integrate p16-u-close-ranges (List the NEEDED U1-U4 items and their proposed ROM ranges fr)
b4b45cb (origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-close-ranges) docs(p16): list NEEDED U1-U4 items and proposed ROM ranges from approved triage doc
baa30b3 agentbridge: integrate p16-u-triage-r15 (Triage U1-U4 for first boot (no ROM reads): carry the review)
62e582d (origin/agentbridge/g3x-lite/port-16-firstboot-pipeline/p16-u-triage-r15) docs(p16): triage U1-U4 unknowns for first boot under narrow boundary
```

---

## 3. Comprehensive First-Boot Items Triage & ROM Evidence Summary

The following table summarizes every U1–U4 item and first-boot prerequisite item from `docs/agentbridge/PORT16_U_CLOSE_RANGES.md:43-94` and `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:13-32, 125-144, 408-435`:

| Item ID | First-Boot Decision | Closability Status | ROM Ranges Read | Bytes Read | Epistemic Status | Manifest Entry Reference | Source Triage Citation |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **U1** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:17, 129, 358-366, 411, 510` |
| **U2(a)** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:18, 130, 206, 412, 511` |
| **U2(b)** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED: src; INFERRED: path]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:19, 131, 207, 413, 512` |
| **U2(c)** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:20, 132, 208, 414, 442-446, 538` |
| **U2(d)-stock** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:21, 133, 209, 415, 485-492, 539` |
| **U2(d)-CHDK** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED: src; INFERRED: path]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:22, 134, 210, 416, 513` |
| **U3** | `NOT_NEEDED` | N/A | None | 0 B | `[INFERRED]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:23, 135, 290, 417, 514` |
| **U4(a)** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:24, 136, 337, 418, 515` |
| **U4(b)(i)** | `NOT_NEEDED` | N/A | None | 0 B | `[VERIFIED: src; INFERRED: path]` | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:25, 137, 338, 419, 516` |
| **U4(b)(ii)** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:26, 138, 339, 420, 448-452, 542` |
| **U4(c)** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:27, 139, 340, 421, 454-458, 543` |
| **Witness Addr** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[VERIFIED: host; UNKNOWN: cam]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28, 140, 422, 460-466` |
| **Dual Markers** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:29, 141, 423, 467-472` |
| **Witness Freshness**| **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:30, 142, 424, 473-478` |
| **Mode Transition** | **`NEEDED`** | **`not ROM-closable`** | **None** | **0 B** | **`[UNKNOWN]`** | `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` | `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:31, 143, 425, 479-484` |

---

## 4. Evidentiary Detail for Each NEEDED Item

### 4.1 Item U2(c) — Stock SD Read Capability & SD Re-enumeration Without Bus Lockup (`OBLIG-U2-08`)
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Static ROM inspection cannot demonstrate dynamic SD controller re-initialization, SD bus clock/timing negotiation, or DMA buffer availability across warm restart `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:20, 132, 443]`.
- **Exact Citations**:
  - `firmware/tools/witness_inspector_gm110c.m:100-121`: Inspector script aborts via `exit sub` if `Fopen_Fut`, `Fread_Fut`, or `Fclose_Fut` fails on `"A/WITNESS.BIN"`.
  - `tools/port13_u2_obligations.py:782-806`: `OBLIG-U2-08` defined as `kind=ObligationKind.RUNTIME` (`:788`).
  - `docs/RESTART_SD_HOST_AUDIT.md:11-29`: SD host controller register state across warm restart requires runtime hardware execution evidence.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:442-446`: Triage determination that dynamic controller state across warm restart cannot be closed by reading static ROM bytes.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The camera completes startup into Playback mode, the owner launches the witness inspector script, and all three file operations (`Fopen_Fut("A/WITNESS.BIN", "rb")`, `Fread_Fut`, and `Fclose_Fut`) succeed without error (`read_sz == payload_size`, `cl == 0`), confirming that SD host re-enumeration succeeded without bus lockup `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:446]`.

---

### 4.2 Item U2(d)-stock — Stock `task_InitFileModules` Dispatch and Normal Completion (`OBLIG-U2-02`, `OBLIG-U2-03`)
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Static ROM inspection of `task_InitFileModules` creator or entry (`0xFC0BD070`) and callee `sub_fc0d9ccc` (`0xFC0D9CCC`) cannot demonstrate whether the DryOS scheduler actually dispatches the task or whether `sub_fc0d9ccc` / `sub_fc0d9cf6` complete normally without fault in the active boot generation `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:21, 133, 486]`.
- **Exact Citations**:
  - `tools/port13_u2_obligations.py:628-649`: `OBLIG-U2-02` defined as `kind=ObligationKind.RUNTIME` (`:634`), requiring current-generation DryOS scheduler dispatch evidence.
  - `tools/port13_u2_obligations.py:652-678`: `OBLIG-U2-03` defined as `kind=ObligationKind.RUNTIME` (`:659`), requiring current-generation completion evidence for `sub_fc0d9ccc` and `sub_fc0d9cf6`.
  - `firmware/tools/witness_inspector_gm110c.m:100-121`: Inspector file operations depend on stock filesystem subsystem availability.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:485-492`: Absence of CHDK file operations does not prove that stock reads are independent of stock initialization.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: Closure is bifurcated:
  1. *Functional First-Boot Observation `[INFERRED]`*: In the active trial, all three inspector file operations succeed (`firmware/tools/witness_inspector_gm110c.m:100-121`). This verifies functional file reading for the first-boot trial `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:490]`.
  2. *Canonical Obligation Discharge `[UNKNOWN]`*: Discharging `OBLIG-U2-02` and `OBLIG-U2-03` requires specific dynamic execution and completion witnesses in the active generation per `tools/port13_u2_obligations.py:628-678`. Because functional file reading does not establish scheduler internals, `OBLIG-U2-02` and `OBLIG-U2-03` remain `[UNKNOWN]` until specifically witnessed `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:491-492]`.

---

### 4.3 Item U4(b)(ii) — Continuation Branch Runtime Safety After Tail Branch `b.w sub_fc0d0126` (`OBLIG-U4-09`)
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Reading static ROM opcodes at `sub_fc0d0126` cannot prove that stack frame integrity, CPU exception state, or register conventions are preserved across the branch during actual execution `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:26, 138, 449]`.
- **Exact Citations**:
  - `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`: Boot stub executes tail branch `b.w sub_fc0d0126`.
  - `tools/port13_oblig_u4.py:295-309`: `OBLIG-U4-09` explicitly requires runtime execution evidence (`requires_runtime_evidence=True` at `:308`).
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:448-452`: Triage establishes that continuation branch safety is a dynamic execution invariant that cannot be settled by static ROM inspection.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The camera continues execution past `b.w sub_fc0d0126` without crashing, throwing a CPU exception, or hanging, successfully enters Playback mode, and the witness inspector executes and reports `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:452]`.

---

### 4.4 Item U4(c) — Warm-Restart Semaphores / Kernel Re-init Teardown (`OBLIG-U4-11`)
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Static ROM bytes cannot reveal whether lingering semaphores, mutexes, or event flags from aborted pre-restart stock tasks cause a deadlock or freeze during subsequent DryOS kernel initialization `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:27, 139, 455]`.
- **Exact Citations**:
  - `tools/port13_oblig_u4.py:326-341`: `OBLIG-U4-11` defined with `requires_runtime_evidence=True` (`:340`).
  - `docs/RESTART_SD_HOST_AUDIT.md:11-29`: `DISKBOOT.BIN` executes following warm restart after stock firmware initialization.
  - `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`: Re-running RAM copy loops does not guarantee that lingering OS sync primitives are neutralized.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:454-458`: Static ROM reads cannot resolve RTOS synchronization state across the warm restart boundary.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The camera executes DryOS kernel re-initialization without hanging on lingering semaphores, allowing startup to proceed through `task_Startup_my` to continuation, where the inspector runs and reports `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:458]`.

---

### 4.5 Item Witness Addr — Inspector / Build Witness-Address Alignment (`candidate_port2a/` @ `0x0035F7A0`)
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[VERIFIED: host binding; UNKNOWN: camera readout]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. This item is a host-side toolchain configuration and build artifact binding question, not a firmware ROM unknown `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:464]`.
- **Epistemic Classification**: **`[VERIFIED: host binding; UNKNOWN: camera readout]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28, 140, 461]`.
- **Exact Citations**:
  - `tools/build_candidate_port2a.py:651-701, 830-833`: Generates and validates aligned inspector payload and metadata targeted to `0x0035F7A0` inside `candidate_port2a/`.
  - `docs/PORT16_CANDIDATE_BUILD.md:26`: Documents successful completion and verification of host-side witness address binding.
  - `firmware/tools/witness_inspector_payload.S:57-93`: Inspector payload assembly logic verifying structure magic and fields at the bound target address.
  - `docs/PORT16_WITNESS_ADDRESS.md:14-29`: Tracks address resolution and validation.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The owner deploys the aligned build artifacts from `candidate_port2a/` to the SD card, executes `firmware/tools/witness_inspector_gm110c.m` on camera, and observes that the inspector reads the witness structure at `0x0035F7A0` without `ERR_READ` `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:465]`.

---

### 4.6 Item Dual Markers — Dual-Flag Boot Marker Coexistence & Post-Boot Script Activation
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Coexistence of volume boot record (VBR) markers (`BOOTDISK` at offset `0x1E0` and `SCRIPT` at `0x1F0`) and post-boot Canon Basic script triggering behavior depend on stock Canon bootloader interaction with physical SD card media formatting, which cannot be closed by static ROM reads `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:29, 141, 468]`.
- **Exact Citations**:
  - `docs/HANDOFF.md:435, 463`: Documents dual-flag marker dependency.
  - `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33`: Analyzes bootloader marker handling.
  - `docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25`: Evaluates script triggering behavior.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:467-472`: Clarifies this is a media formatting and bootloader interaction question, not a ROM unknown.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The owner prepares an SD card with dual markers (`BOOTDISK` at `0x1E0`, `SCRIPT` at `0x1F0`), boots the camera, and verifies that `DISKBOOT.BIN` executes, followed by successful execution of `firmware/tools/witness_inspector_gm110c.m` `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:471]`.

---

### 4.7 Item Witness Freshness — Current-Attempt Witness Freshness Verification
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Freshness verification requires an anti-replay protocol between boot stub and inspector. Reading static ROM bytes cannot close a protocol design gap `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:30, 142, 474]`.
- **Exact Citations**:
  - `tools/build_candidate_port2a.py:783`: Candidate build records fixed nonce `0x32A80001`.
  - `firmware/tools/witness_inspector_payload.S:96-113`: Inspector explicitly excludes constant nonce `0x32A80001` from freshness proof.
  - `firmware/tools/witness_inspector_gm110c.m:28`: Script sets `expected_nonce = 0`, producing `FRESHNESS_UNVERIFIED`.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:473-478`: Confirms that a dynamic challenge requires a producer-side dynamic nonce mechanism not present in the candidate, which cannot be settled by ROM reads.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: Remains `[UNKNOWN]` until an independently verified dynamic nonce producer mechanism or a physical cold power-cycle DRAM decay observation is established `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:477]`.

---

### 4.8 Item Mode Transition — Operational Mode Transition to Shooting Live View
- **First-Boot Decision**: `NEEDED_FOR_FIRST_BOOT` `[UNKNOWN]`.
- **ROM Ranges Read**: None (0 B read; start: `—`, length: `0 B`).
- **What the Bytes Show**: Zero ROM bytes were read. Retained message display registration in Playback mode and visual rendering upon transitioning to Shooting Live View is a physical camera UI operational procedure, not a ROM unknown `[UNKNOWN]`.
- **Epistemic Classification**: **`[UNKNOWN]`**; **`not ROM-closable`** `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:31, 143, 480]`.
- **Exact Citations**:
  - `firmware/tools/witness_inspector_gm110c.m:185-188`: Retained message descriptors allocated in Playback mode.
  - `docs/HANDOFF.md:1439`: Visual display renders only after user transitions camera into Shooting Live View.
  - `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:479-484`: Documents physical camera UI operational dependency.
- **Manifest Entry Reference**: `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT16-U` (0 evidence entries declared).
- **Proposed Observation for Owner Trial Plan `[INFERRED]`**: The owner half-presses the shutter button or operates the mode dial to switch from Playback to Shooting Live View and visually observes the message lines rendered on the LCD `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:483]`.

---

## 5. Confirmation of NOT_NEEDED Items

For complete audit traceability, all items triaged as `NOT_NEEDED_FOR_FIRST_BOOT` in `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:17-25, 129-137, 508-518` were reviewed. Zero ROM ranges were needed or read for any of them:

1. **U1 (`CreateTask` Prologue & Literal)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED]`. The boot prototype invokes the stock veneer at `0xFC31BBC4` directly (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366`, veneer at `:365`); no task interception is installed (`:411-416`).
2. **U2(a) (CHDK `InitFileModules` Gate)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED]`. CHDK performs zero file access during first boot; the CHDK filesystem hook is absent (`tools/port9b_runtime_contract.py:455-456; chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436`).
3. **U2(b) (Deferred CHDK Filesystem Preconditions)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: src; INFERRED: path]`. Boot witness is written directly to DRAM; CHDK SpyTask is commented out (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:27-29, 411-416`).
4. **U2(d)-CHDK (CHDK Consumption of FileModules)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: src; INFERRED: path]`. CHDK SpyTask is disabled; no CHDK filesystem tasks are spawned (`docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183; chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`).
5. **U3 (`task_PhySw` Keyboard Interception)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[INFERRED]`. The prototype launches unmodified stock `task_PhySw` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:409`); keyboard interception is disabled (`tools/port9b_runtime_contract.py:454`).
6. **U4(a) (SpyTask Lifecycle)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED]`. CHDK SpyTask is explicitly commented out (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416; tests/test_port9b_runtime_contract.py:86-89`).
7. **U4(b)(i) (Task Priority Policy)**: `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: src; INFERRED: path]`. `task_Startup_my` runs at fixed stock priority `0x19` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:363`); stub modifies no scheduling (`tools/port13_oblig_u4.py:199-215`).

---

## 6. Offline Evidence Manifest & Validator Execution

The evidence manifest `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json` and trusted scope policy `docs/agentbridge/PORT16_TRUSTED_SCOPES.json` were validated using the offline tool `tools/port11c_evidence_validator.py`.

### 6.1 Exact Validator Command
```bash
python3 -B tools/port11c_evidence_validator.py \
  --manifest docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json \
  --trusted-scopes docs/agentbridge/PORT16_TRUSTED_SCOPES.json
```

### 6.2 Verbatim Validator Output
```text
Evidence Manifest Validation: 0 entries, Trust Level: EXTERNAL_POLICY_CONSISTENCY_CHECKED
----------------------------------------------------------------------
----------------------------------------------------------------------
Result: VALID (0 errors, 0 warnings)
```

### 6.3 JSON Mode Validation Output
Executing with `--json`:
```json
{
  "is_valid": true,
  "trust_level": "EXTERNAL_POLICY_CONSISTENCY_CHECKED",
  "evidence_verification_boundary": "OFFLINE_DECLARATIONS_AND_SYNTHETIC_FIXTURES_ONLY (ROM binary bytes not accessed or authenticated by this tool; external policy consistency != owner approval; authority remains UNVERIFIED without out-of-band record)",
  "rom_permission_granted": false,
  "rom_permission_disclaimer": "NON-AUTHORITY INVARIANT: This tool validates offline declarations and synthetic test fixtures only; it possesses NO authority to grant ROM-reading, firmware dumping, or camera execution permission. Providing an external policy file does NOT authenticate its creator or independent owner approval. rom_permission_granted remains permanently False.",
  "error_count": 0,
  "warning_count": 0,
  "findings": []
}
```

### 6.4 Validation Analysis
- **Exit Code**: `0` (Success).
- **Error Count**: `0`.
- **Warning Count**: `0`.
- **Trust Level**: `EXTERNAL_POLICY_CONSISTENCY_CHECKED` (Verified against external trusted scope policy `docs/agentbridge/PORT16_TRUSTED_SCOPES.json`).
- **Policy Compliance**: `SCOPE-PORT16-U` declares `max_bytes_total: 4096`, `approved_ranges: []`, and revision `GM1.10C`, matching the external policy exactly. Zero unapproved slices or out-of-quota claims exist.

---

## 7. Deliverable File Contents

### 7.1 `docs/agentbridge/PORT16_TRUSTED_SCOPES.json`
```json
{
  "policy_version": "1.0.0",
  "policy_authority": "UNVERIFIED_EXTERNAL_POLICY (External consistency check policy; out-of-band owner approval required)",
  "authorization_scopes": [
    {
      "scope_id": "SCOPE-PORT16-U",
      "firmware_revision": "GM1.10C",
      "approved_ranges": [],
      "max_bytes_total": 4096,
      "allowed_classifications": [
        "STATIC_VERIFIED",
        "INFERRED",
        "UNKNOWN"
      ],
      "description": "PORT-16 U1-U4 first-boot triage scope (0 bytes approved; all NEEDED items not ROM-closable per docs/agentbridge/PORT16_U_CLOSE_RANGES.md)"
    }
  ]
}
```

### 7.2 `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json`
```json
{
  "manifest_version": "1.0.0",
  "authorization_scopes": [
    {
      "scope_id": "SCOPE-PORT16-U",
      "firmware_revision": "GM1.10C",
      "approved_ranges": [],
      "max_bytes_total": 4096,
      "allowed_classifications": [
        "STATIC_VERIFIED",
        "INFERRED",
        "UNKNOWN"
      ],
      "description": "PORT-16 U1-U4 first-boot triage scope (0 bytes approved; all NEEDED items not ROM-closable per docs/agentbridge/PORT16_U_CLOSE_RANGES.md)"
    }
  ],
  "evidence_entries": []
}
```

---

## 8. Verification and Compliance Summary

1. **Phase 0 Safety Gate Compliance**: In strict adherence to `docs/SAFETY.md:1-8`, zero ROM binary dumps were accessed or opened, zero camera hardware trials were performed, zero binaries were compiled, and zero scripts were executed on camera.
2. **Zero ROM Bytes Read**: Because the authorized id-63 list (`docs/agentbridge/PORT16_U_CLOSE_RANGES.md`) specifies 0 ranges / 0 bytes, exactly 0 bytes were read from `firmware/dumps/GM1.10C/PRIMARY.BIN`. No full ROM scans or heuristic searches were executed.
3. **Narrow First-Boot Scope**: Triage decisions strictly enforce the narrow first-boot boundary, separating runtime first-boot prerequisites from post-first-boot CHDK feature enablement (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:522-526`).
4. **Epistemic Discipline**: Every statement is labeled `[VERIFIED]`, `[INFERRED]`, or `[UNKNOWN]` with exact file:line citations to tracked repository artifacts. No addresses, offsets, or execution behaviors are inferred beyond what the evidence proves.
5. **Offline Tooling Compliance**: Validation relied exclusively on `python3 -B tools/port11c_evidence_validator.py`. No pip, pytest, or environment-modifying commands were run. Test scripts building payload binaries (`tests/test_validate_witness_inspector.py`, `tools/build_witness_inspector.py`) were strictly avoided.
6. **Path Modification Restraint**: Only the three authorized paths were created/modified:
   - `docs/PORT16_FIRSTBOOT_U_EVIDENCE.md`
   - `docs/agentbridge/PORT16_U_EVIDENCE_MANIFEST.json`
   - `docs/agentbridge/PORT16_TRUSTED_SCOPES.json`
