# PORT-13 — Fail-Closed Proof Obligations: GM1.10C Memory Ownership

**Document Date**: 2026-10-29  
**Author**: Antigravity (Independent Firmware Reviewer, AgentBridge worker `p13-oblig-mem`)  
**Target Module**: [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py)  
**Test Suite**: [`tests/test_port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tests/test_port13_memory_obligations.py)  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Offline Read-Only Investigation)  
**Current Evaluation Result**: **`NOT READY (FAIL-CLOSED)`** (`is_ready == False`)

---

## 1. Executive Summary & Purpose

The purpose of milestone **PORT-13 (`p13-oblig-mem`)** is to formalize memory-ownership proof obligations for the Canon PowerShot G3 X (Firmware **GM1.10C**, DIGIC 6, dual-core Cortex-R4) as machine-readable data, enforced by a deterministic, fail-closed evaluation engine.

Following the independent review of Draft PR #23 ([`docs/PORT13_REVIEW_PR23.md`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT13_REVIEW_PR23.md)), this module establishes the following evidentiary and security safeguards:
1. **Fail-Closed by Design**: Memory ownership cannot be presumed. Overall readiness evaluates strictly to `False` unless every obligation is `VERIFIED` with primary GM1.10C evidence tracked on `origin/main`.
2. **Epistemic Principle: Bounds ≠ Ownership**: Byte copy ranges do not verify subsystem ownership. In accordance with [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:26`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L26), static instruction copies are classified as `STATIC_VERIFIED`, while functional ownership, allocator rules, and scheduler semantics remain `INFERRED` or `UNKNOWN`.
3. **Rejection of Historical Heuristics**: Evidence from historical firmware (GM1.00C or Ranma's GM1.10E patch) cannot prove GM1.10C memory ownership. Any obligation attempting to claim `VERIFIED` based on historical-only citations is rejected.
4. **Pending PR Quarantine**: Evidence originating solely from unmerged Draft PR #23 is quarantined with status `UNKNOWN` and explicitly annotated with its pending PR reference.
5. **Zero New Firmware Addresses**: Every memory address appearing in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) and this document is already present in a tracked `origin/main` document, cited `file:line`.

---

## 2. Fail-Closed Evaluation Rules

The evaluation function `evaluate()` in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) enforces the following deterministic rules:

| Rule Identifier | Severity | Trigger Condition | Fail-Closed Consequence |
|---|:---:|---|---|
| **`RULE_MISSING_CITED_PATH`** | `ERROR` | A cited file path does not exist on disk in the worktree. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNTRACKED_SOURCE`** | `ERROR` | A cited path is not in the whitelist of 71 files tracked on `origin/main`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNACCEPTABLE_SOURCE`** | `ERROR` | A cited path is not explicitly listed in the obligation's `acceptable_tracked_sources`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_HISTORICAL_CANNOT_VERIFY`** | `ERROR` | A citation is marked `is_historical`, targets firmware `1.00C`/`1.10E`, or cites historical patch/symbols files, while the obligation is marked `VERIFIED`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_PENDING_PR_CANNOT_VERIFY`** | `ERROR` | An obligation claims `VERIFIED` status despite relying on evidence found only in an unmerged PR (`pending_pr`). | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_STATUS_NOT_VERIFIED`** | `WARNING` | An obligation has status `UNKNOWN` or `INFERRED`. | Aggregate `is_ready` forced to `False`. |
| **`RULE_EMPTY_CITATIONS`** | `ERROR` | An obligation has an empty citations tuple. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_EMPTY_DATASET`** | `ERROR` | Zero obligations provided to `evaluate()`. | `is_ready` forced to `False`. |

Overall readiness is `True` **if and only if**:
- `total_obligations > 0`
- `verified_count == total_obligations`
- `error_count == 0`
- `unknown_count == 0`
- `inferred_count == 0`

Because the shipped dataset contains 11 `INFERRED` and 6 `UNKNOWN` obligations, **current overall readiness is strictly `False`**, and there is no path to `True` from the shipped data without new, authorized GM1.10C ROM disassembly.

---

## 3. Inventory of GM1.10C Memory Ownership Obligations

The dataset in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) defines 18 structured proof obligations:

| Obligation ID | Target Memory Region / Subject | Current Status | Required Evidence Type | Acceptable Tracked Sources | Tracked Citations on `origin/main` | Pending PR Note |
|---|---|:---:|:---:|---|---|:---:|
| **`OBLIG-MEM-01`** | Low Vector & Hardware Scratch (`0x00000000..0x00003FFF` / `0x00008000`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/GM110C_MEMORY_MAP.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:166`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L166) | None |
| **`OBLIG-MEM-02`** | Low-RAM Data Section (`0x00008000..0x0003F4F3`, ROM `0xFCE91058`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:77, 167`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L77) | None |
| **`OBLIG-MEM-03`** | Canon Firmware BSS (`0x0003F4F4..0x003489B3`, literals `0xFC0200DC`, `0xFC05B450`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PROJECT_STATE.md`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:168`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L168), [`docs/PROJECT_STATE.md:295`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L295) | None |
| **`OBLIG-MEM-04`** | Low-Heap Core Relocation Target Isolation (`[0x003489B4, 0x003C89B4)`) | **`UNKNOWN`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L179), [`docs/HANDOFF.md:796`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/HANDOFF.md#L796) | **`PR #23`** |
| **`OBLIG-MEM-05`** | DryOS Main Heap Pool 0 (`0x003C89B4..0x00600014`, `AllocateMemory`) | **`INFERRED`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:210`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L210), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169) | None |
| **`OBLIG-MEM-06`** | DryOS Sub-Pool & Kernel Object Table Descriptors (`0x00600014..0x0060E000`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169) | None |
| **`OBLIG-MEM-07`** | DryOS Fixed Chunk Allocator Block Bounds (`0x0060E000..0x006CDFFF`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:170`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L170), [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:206`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L206) | None |
| **`OBLIG-MEM-08`** | DryOS System Headroom Comparator Limit (`0x006CE000 - r4 >= 0x000B1FEC`, `0xFC05B3C8`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PROJECT_STATE.md`, `docs/HANDOFF.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5A_RANMA_PORT_RECOVERY.md` | [`docs/PROJECT_STATE.md:294`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L294), [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L179), [`docs/PORT5A_RANMA_PORT_RECOVERY.md:108`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5A_RANMA_PORT_RECOVERY.md#L108) | None |
| **`OBLIG-MEM-09`** | AdditionAgent Conflict Zone (`0x006CE000..0x006EFFFF`, `0x22000` B, `0xFC55888C..0xFC5588C0`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L171), [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308) | None |
| **`OBLIG-MEM-10`** | OMAR Secondary Core Staging RAM Bounds & IPC Master (`0x00700000..0x0075FFFF`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L172) | None |
| **`OBLIG-MEM-11`** | Mid-DRAM Uninspected Gap Characterization (`0x00760000..0x00C80000`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173) | None |
| **`OBLIG-MEM-12`** | Disqualification of Ranma High-DRAM Placement (`0x00C80000..0x00DFFFFF`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175) | **`PR #23`** |
| **`OBLIG-MEM-13`** | High-DRAM Uninspected Gap Characterization (`0x00E00000..0x010E1000`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175) | None |
| **`OBLIG-MEM-14`** | Firmware Executable RAM Mirror Copy Bounds (`0x010E1000..0x01107CFF`, ROM `0xFCEC854C`) | **`INFERRED`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:108`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L108), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:75, 177`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L75) | None |
| **`OBLIG-MEM-15`** | Image Sensor RAW DMA Buffer Allocation Lower Bound (`0x43DBFCA0`) | **`UNKNOWN`** | `ROM_VERIFIED` | `vendor/g3x-platform/platform/g3x/platform_camera.h`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`vendor/g3x-platform/platform/g3x/platform_camera.h:44`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/vendor/g3x-platform/platform/g3x/platform_camera.h#L44), [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308) | **`PR #23`** |
| **`OBLIG-MEM-16A`** | Cortex-R4 ATCM Relocated Span Copy Bounds (`0xBFE10800..0xBFE1741B`, ROM `0xFCEEF24C..0xFCEF5E67`) | **`VERIFIED`** | `ROM_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, `docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md` | [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20) | None |
| **`OBLIG-MEM-16B`** | Cortex-R4 ATCM Routine Execution Role & Scheduler Ownership (`0xBFE14A3C`, `0xFC31BBC4`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, `docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md` | [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20), [`docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md:79`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md#L79) | None |
| **`OBLIG-MEM-17`** | Uncached Peripheral Memory Apertures & MPU Attributes (`0x40000000`, `0x406CE000`) | **`INFERRED`** | `ROM_VERIFIED` | `vendor/g3x-platform/platform/g3x/platform_camera.h`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`vendor/g3x-platform/platform/g3x/platform_camera.h:38`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/vendor/g3x-platform/platform/g3x/platform_camera.h#L38), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L179) | None |

---

## 4. Tracked Address Provenance Ledger

To comply strictly with the requirement that **no new firmware addresses are introduced**, every address appearing in the obligations data is registered in `TRACKED_ADDRESS_CITATIONS` in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py), verified by `verify_address_provenance()` against tracked `origin/main` files:

- `0x00000000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:166`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L166)
- `0x00003FFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:166`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L166)
- `0x00008000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:167`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L167)
- `0x0003F4F3`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:167`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L167)
- `0x0003F4F4`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:168`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L168)
- `0x003489B3`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:168`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L168)
- `0x003489B4`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169)
- `0x003C89B4`: [`docs/HANDOFF.md:796`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/HANDOFF.md#L796)
- `0x00600014`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169)
- `0x0060E000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:170`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L170)
- `0x006CDFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169)
- `0x006CE000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L171)
- `0x000B1FEC`: [`docs/PROJECT_STATE.md:294`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L294)
- `0x006EFFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L171)
- `0x22000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L171)
- `0x8000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:101`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L101)
- `0x00700000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L172)
- `0x0075FFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L172)
- `0x00760000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173)
- `0x00C80000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x00DFFFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x00E00000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x010E1000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L78)
- `0x01107CFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:177`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L177)
- `0x01107D00`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L78)
- `0x40000000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L179)
- `0x406CE000`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0x43DBFCA0`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0xBFE10800`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xBFE14A3C`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xBFE17419`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xBFE1741B`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xFC020040`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:60`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L60)
- `0xFC020052`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xFC0200C4`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:103`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L103)
- `0xFC0200C8`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:104`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L104)
- `0xFC0200CC`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xFC0200CF`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:60`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L60)
- `0xFC0200DC`: [`docs/PROJECT_STATE.md:295`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L295)
- `0xFC05B3C8`: [`docs/PROJECT_STATE.md:294`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L294)
- `0xFC05B450`: [`docs/PROJECT_STATE.md:295`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L295)
- `0xFC05B454`: [`docs/PORT5A_RANMA_PORT_RECOVERY.md:108`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5A_RANMA_PORT_RECOVERY.md#L108)
- `0xFC31BBC4`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xFC55888C`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0xFC5588C0`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0xFCE91058`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:77`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L77)
- `0xFCEC854C`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:75`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L75)
- `0xFCEEF24C`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xFCEF5E67`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)

---

## 5. Verification & Test Suite Status

The test suite [`tests/test_port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tests/test_port13_memory_obligations.py) executes deterministically under standard Python 3 `unittest` without external dependencies or subprocesses:

```sh
python3 -B -m unittest tests/test_port13_memory_obligations.py
```

### Test Results Ledger
- `test_current_overall_readiness_is_false`: **PASS** (18 obligations, readiness False, 17 warnings)
- `test_there_is_no_path_to_true_from_shipped_data`: **PASS** (17 of 18 unverified, subsets fail)
- `test_historical_only_citation_cannot_be_verified`: **PASS** (Historical tag and symbol paths force False)
- `test_nonexistent_cited_path_fails`: **PASS** (Missing path triggers `RULE_MISSING_CITED_PATH`)
- `test_untracked_source_fails`: **PASS** (Untracked path triggers `RULE_UNTRACKED_SOURCE`)
- `test_unacceptable_source_for_obligation_fails`: **PASS** (Unapproved source triggers `RULE_UNACCEPTABLE_SOURCE`)
- `test_empty_citations_fails`: **PASS** (Empty citation tuple triggers `RULE_EMPTY_CITATIONS`)
- `test_unknown_status_forces_false`: **PASS** (`UNKNOWN` status forces readiness False)
- `test_inferred_status_forces_false`: **PASS** (`INFERRED` status forces readiness False)
- `test_pr23_evidence_marked_unknown_with_pending_note`: **PASS** (PR #23 items annotated properly)
- `test_pending_pr_evidence_cannot_be_verified`: **PASS** (Pending PR claim triggers `RULE_PENDING_PR_CANNOT_VERIFY`)
- `test_every_address_is_present_in_tracked_origin_main_doc`: **PASS** (Address provenance passes with 0 errors)
- `test_tracked_address_citations_count`: **PASS** (Registry contains >= 45 verified addresses)
- `test_all_tracked_citations_have_valid_lines`: **PASS** (Exact file:line text verification passes)
- `test_no_subprocess_imported`: **PASS** (`subprocess` strictly absent from tool imports)
- `test_stdlib_only`: **PASS** (No third-party packages imported)
- `test_all_obligations_serialize_to_dict`: **PASS** (JSON serialization integrity confirmed)

**Total**: **17 executed, 17 PASS, 0 FAIL, 0 ERR** (0.021s).
