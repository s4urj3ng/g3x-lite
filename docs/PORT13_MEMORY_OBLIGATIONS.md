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

Following the independent review of Draft PR #23 ([`docs/PORT13_REVIEW_PR23.md`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT13_REVIEW_PR23.md)) and the resolution of reviewer defects, this module establishes the following evidentiary and security safeguards:
1. **Fail-Closed by Design & Canonical Required Obligation Set**: Memory ownership cannot be presumed. Overall readiness evaluates strictly to `False` unless every obligation in the canonical 18-obligation set (`REQUIRED_OBLIGATION_IDS`) is `VERIFIED` with primary GM1.10C evidence tracked on `origin/main`. Evaluating subsets or individual obligations (e.g. `OBLIG-MEM-16A`) never asserts overall readiness.
2. **Epistemic Principle: Bounds ≠ Ownership**: Byte copy ranges do not verify subsystem ownership. In accordance with [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:26`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L26), static instruction copies are classified as `STATIC_VERIFIED`, while functional ownership, allocator rules, and scheduler semantics remain `INFERRED` or `UNKNOWN`.
3. **Firmware Identity Strict Allowlist**: Normalized allowlist accepting strictly `GM1.10C`. Everything else—including `gm1.10e`, `GM1.10E `, `UNKNOWN`, `""`, `None`, `1.00C`, `1.10E`, or unrecognized variants (`GM1.10X`)—is rejected with an explicit error when claimed for `VERIFIED` status.
4. **Trusted Citation Provenance Registry & Anti-Tampering**: In mixed-firmware comparisons (e.g. [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md)), provenance is determined exclusively by the module's immutable `CITATION_PROVENANCE_REGISTRY` keyed by `(path, line)`. Caller-supplied flags cannot override historical status; citations with omitted flags never default to `GM1.10C`; and unrecorded citations force fail-closed evaluation.
5. **Authoritative Immutable Digest Pins & Non-Production Rejection**: File existence and path whitelists do not establish provenance. For every cited evidence file, [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) pins the cryptographic SHA-256 digest of its `origin/main` content at commit `581b1a4bb30456bf18c46dc4bcf61b0375aee251` as an immutable `MappingProxyType`. Any test hook usage (`pinned_hashes` override, custom `file_reader`, or alternate `repo_root`) immediately forces `is_ready = False` with `RULE_NON_PRODUCTION_EVIDENCE_CONFIG`.
6. **Pending PR Quarantine**: Evidence originating solely from unmerged Draft PR #23 is quarantined with status `UNKNOWN` and explicitly annotated with its pending PR reference.
7. **Zero New Firmware Addresses**: Every memory address appearing in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) and this document is already present in a tracked `origin/main` document, cited `file:line`.
8. **Trusted Obligation Requirements Binding (`OBLIGATION_REQUIREMENTS_REGISTRY`)**: Canonical obligation IDs are bound to immutable proof requirements via module constant `OBLIGATION_REQUIREMENTS_REGISTRY`. For each ID, the registry dictates the required evidence type, the exact acceptable tracked sources (by path string or `(path, line)` tuple), and PR #23 dependency. `evaluate()` treats this registry as the sole authority, ignoring caller-supplied requirement fields and raising `RULE_REQUIREMENT_CONFLICT` if a caller attempts to rewrite acceptable sources, change evidence types, or clear `pending_pr` on PR #23-dependent obligations.

---

## 2. Fail-Closed Evaluation Rules

The evaluation function `evaluate()` in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) enforces the following deterministic rules:

| Rule Identifier | Severity | Trigger Condition | Fail-Closed Consequence |
|---|:---:|---|---|
| **`RULE_INCOMPLETE_OBLIGATION_SET`** | `ERROR` | One or more canonical obligations from `REQUIRED_OBLIGATION_IDS` are missing from evaluation. | Aggregate `is_ready` forced to `False`. |
| **`RULE_DUPLICATE_OBLIGATION_ID`** | `ERROR` | Duplicate obligation IDs provided to `evaluate()`. | Aggregate `is_ready` forced to `False`. |
| **`RULE_UNKNOWN_OBLIGATION_ID`** | `ERROR` | An unrecognized obligation ID outside `REQUIRED_OBLIGATION_IDS` is supplied. | Aggregate `is_ready` forced to `False`. |
| **`RULE_NON_PRODUCTION_EVIDENCE_CONFIG`** | `ERROR` | Test hooks active (`pinned_hashes` override, custom `file_reader`, or alternate `repo_root`). | Production readiness forced to `False`. |
| **`RULE_REQUIREMENT_CONFLICT`** | `ERROR` | Caller-supplied required evidence type, acceptable sources, or pending PR status conflicts with trusted `OBLIGATION_REQUIREMENTS_REGISTRY`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNREGISTERED_CITATION`** | `ERROR` | Citation `(path, line)` is not in `CITATION_PROVENANCE_REGISTRY`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_PROVENANCE_CONFLICT`** | `ERROR` | Caller-supplied citation flags conflict with trusted provenance registry entries. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_MISSING_CITED_PATH`** | `ERROR` | A cited file path does not exist on disk or in the injected file reader. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNREADABLE_SOURCE`** | `ERROR` | A cited file cannot be read due to I/O or permissions error. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNTRACKED_SOURCE`** | `ERROR` | A cited path is not in the whitelist of 103 files tracked on `origin/main`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNPINNED_SOURCE`** | `ERROR` | A cited path lacks a cryptographic SHA-256 digest pin in `PINNED_ORIGIN_MAIN_FILE_HASHES`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_CONTENT_HASH_MISMATCH`** | `ERROR` | Local file SHA-256 digest differs from pinned `origin/main` digest. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_UNACCEPTABLE_SOURCE`** | `ERROR` | A cited path is not in the obligation's trusted acceptable tracked sources in `OBLIGATION_REQUIREMENTS_REGISTRY`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_HISTORICAL_CANNOT_VERIFY`** | `ERROR` | Citation line is historical, cites historical-only paths, or lacks verified `GM1.10C` provenance while obligation is marked `VERIFIED`. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_PENDING_PR_CANNOT_VERIFY`** | `ERROR` | An obligation claims `VERIFIED` status despite relying on evidence found only in an unmerged PR (`pending_pr` in registry or obligation). | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_STATUS_NOT_VERIFIED`** | `WARNING` | An obligation has status `UNKNOWN` or `INFERRED`. | Aggregate `is_ready` forced to `False`. |
| **`RULE_EMPTY_CITATIONS`** | `ERROR` | An obligation has an empty citations tuple. | Obligation disqualified; `is_ready` forced to `False`. |
| **`RULE_EMPTY_DATASET`** | `ERROR` | Zero obligations provided to `evaluate()`. | `is_ready` forced to `False`. |

Overall readiness is `True` **if and only if**:
- `total_obligations == len(REQUIRED_OBLIGATION_IDS) == 18`
- `passed_id_set == REQUIRED_OBLIGATION_IDS` (complete canonical set, zero missing, zero unknown, zero duplicates)
- `is_production_config == True` (zero test hooks: default root, immutable production pins, no injected readers)
- `verified_count == 18`
- `error_count == 0`
- `unknown_count == 0`
- `inferred_count == 0`

Because the shipped dataset contains 11 `INFERRED` and 6 `UNKNOWN` obligations, **current overall readiness is strictly `False`**, and there is no path to `True` from the shipped data without new, authorized GM1.10C ROM disassembly.

---

## 3. Inventory of GM1.10C Memory Ownership Obligations

The dataset in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py) defines 18 structured proof obligations:

| Obligation ID | Target Memory Region / Subject | Current Status | Required Evidence Type | Acceptable Tracked Sources | Tracked Citations on `origin/main` | Pending PR Note |
|---|---|:---:|:---:|---|---|:---:|
| **`OBLIG-MEM-01`** | Low Vector & Hardware Scratch (`0x00000000..0x00003FFF` / `0x00008000`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/GM110C_MEMORY_MAP.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:166`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L166) *(GM1.10E historical)* | None |
| **`OBLIG-MEM-02`** | Low-RAM Data Section (`0x00008000..0x0003F4F3`, ROM `0xFCE91058`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:77, 167`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L77) | None |
| **`OBLIG-MEM-03`** | Canon Firmware BSS (`0x0003F4F4..0x003489B3`, literals `0xFC0200DC`, `0xFC05B450`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PROJECT_STATE.md`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:168`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L168), [`docs/PROJECT_STATE.md:295`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L295) | None |
| **`OBLIG-MEM-04`** | Low-Heap Core Relocation Target Isolation (`[0x003489B4, 0x003C89B4)`) | **`UNKNOWN`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L179), [`docs/HANDOFF.md:796`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/HANDOFF.md#L796) | **`PR #23`** |
| **`OBLIG-MEM-05`** | DryOS Main Heap Pool 0 (`0x003C89B4..0x00600014`, `AllocateMemory`) | **`INFERRED`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:210`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L210), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169) | None |
| **`OBLIG-MEM-06`** | DryOS Sub-Pool & Kernel Object Table Descriptors (`0x00600014..0x0060E000`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L169) | None |
| **`OBLIG-MEM-07`** | DryOS Fixed Chunk Allocator Block Bounds (`0x0060E000..0x006CDFFF`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:170`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L170), [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:206`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L206) | None |
| **`OBLIG-MEM-08`** | DryOS System Headroom Comparator Limit (`0x006CE000 - r4 >= 0x000B1FEC`, `0xFC05B3C8`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PROJECT_STATE.md`, `docs/HANDOFF.md`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5A_RANMA_PORT_RECOVERY.md` | [`docs/PROJECT_STATE.md:294`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L294), [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L179), [`docs/PORT5A_RANMA_PORT_RECOVERY.md:108`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5A_RANMA_PORT_RECOVERY.md#L108) *(GM1.10E historical)* | None |
| **`OBLIG-MEM-09`** | AdditionAgent Conflict Zone (`0x006CE000..0x006EFFFF`, `0x22000` B, `0xFC55888C..0xFC5588C0`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:171`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L171), [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308) | None |
| **`OBLIG-MEM-10`** | OMAR Secondary Core Staging RAM Bounds & IPC Master (`0x00700000..0x0075FFFF`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:172`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L172) *(GM1.10E historical)* | None |
| **`OBLIG-MEM-11`** | Mid-DRAM Uninspected Gap Characterization (`0x00760000..0x00C80000`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173) *(GM1.10E historical)* | None |
| **`OBLIG-MEM-12`** | Disqualification of Ranma High-DRAM Placement (`0x00C80000..0x00DFFFFF`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175) *(GM1.10E historical)* | **`PR #23`** |
| **`OBLIG-MEM-13`** | High-DRAM Uninspected Gap Characterization (`0x00E00000..0x010E1000`) | **`UNKNOWN`** | `ROM_VERIFIED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:176`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L176) *(GM1.10E historical)* | None |
| **`OBLIG-MEM-14`** | Firmware Executable RAM Mirror Copy Bounds (`0x010E1000..0x01107CFF`, ROM `0xFCEC854C`) | **`INFERRED`** | `ROM_VERIFIED` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`chdk-port/platform/g3x/sub/110c/boot_prototype.c:108`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/chdk-port/platform/g3x/sub/110c/boot_prototype.c#L108), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:75, 177`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L75) | None |
| **`OBLIG-MEM-15`** | Image Sensor RAW DMA Buffer Allocation Lower Bound (`0x43DBFCA0`) | **`UNKNOWN`** | `ROM_VERIFIED` | `vendor/g3x-platform/platform/g3x/platform_camera.h`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md` | [`vendor/g3x-platform/platform/g3x/platform_camera.h:44`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/vendor/g3x-platform/platform/g3x/platform_camera.h#L44), [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308) | **`PR #23`** |
| **`OBLIG-MEM-16A`** | Cortex-R4 ATCM Relocated Span Copy Bounds (`0xBFE10800..0xBFE1741B`, ROM `0xFCEEF24C..0xFCEF5E67`) | **`VERIFIED`** | `ROM_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, `docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md` | [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 60`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20) | None |
| **`OBLIG-MEM-16B`** | Cortex-R4 ATCM Routine Execution Role & Scheduler Ownership (`0xBFE14A3C`, `0xFC31BBC4`) | **`INFERRED`** | `ROM_VERIFIED` | `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, `docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md` | [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20), [`docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md:79`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md#L79) | None |
| **`OBLIG-MEM-17`** | Uncached Peripheral Memory Apertures & MPU Attributes (`0x40000000`, `0x406CE000`) | **`INFERRED`** | `ROM_VERIFIED` | `vendor/g3x-platform/platform/g3x/platform_camera.h`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | [`vendor/g3x-platform/platform/g3x/platform_camera.h:38`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/vendor/g3x-platform/platform/g3x/platform_camera.h#L38), [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L179) *(GM1.10E historical)* | None |

---

## 4. Cryptographic Content Authentication & SHA-256 Digest Pins

### 4.1 Provenance Digest Ledger (`origin/main @ 581b1a4bb30456bf18c46dc4bcf61b0375aee251`)

To guarantee evidence authenticity and prevent local tampering or untracked injection from bypassing fail-closed checks, every cited evidence path is pinned with its SHA-256 digest in `PINNED_ORIGIN_MAIN_FILE_HASHES`:

| Cited Tracked File Path | Pinned SHA-256 Digest | Provenance Role |
|---|---|---|
| `chdk-port/platform/g3x/sub/110c/boot_prototype.c` | `f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68` | Boot prototype code model |
| `docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md` | `c04e83dec333fb6c41b4a854394a11f3fc36ce71c0eda6f3ef212da6a03bf74d` | Symbol comparison and reconciliation |
| `docs/GM110C_MEMORY_MAP.md` | `74561df2bd43b233ea35763df9689076791f67fcedf24291fb72f17571efdf05` | Target memory map candidate |
| `docs/HANDOFF.md` | `6c0c19054e6c6c68f71821ed300f456d41d8180569c48224e4660bc1e116a0d5` | Project handoff & scan report |
| `docs/PATCH_AUDIT_110E.md` | `6606f6c8b41bdb02748d12bac067079ebbbaf3b8912d24b85b27bfa63414cdfa` | Historical patch disassembly audit |
| `docs/PORT11A_GM110C_ROM_EVIDENCE.md` | `45928b29efc2062796ae51a326fcfec2f650e9589944f530158b7a9dcaaec8da` | Primary GM1.10C ROM slice evidence |
| `docs/PORT5A_RANMA_PORT_RECOVERY.md` | `6c68897320b97c6d67a2ad6f6554c41a98d11105d8ab45394186a738364400e8` | Historical Ranma recovery report |
| `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` | `9855a2316aba777065547f7e8f30a3aabff5cff8ce94be48deb3c10406df281c` | Historical vs prototype boot comparison |
| `docs/PROJECT_STATE.md` | `3b700ed093a4e2d37c9dc57e3cf8e296e679946ac618017f95ec9eb43cad8121` | Baseline state documentation |
| `docs/SAFETY.md` | `c50f25b07500a844a374193b839028ca82de6007e6778eeb3a04049ffaaaa30d` | Safety policy & protocol document |
| `research/historical/g3x/g3x_100c_historical_symbols.csv` | `6289e65e0c1f9d3c137315aacdd368a9da6f8eb4c9438d03464f5ac0342205c6` | Historical 1.00C symbol table CSV |
| `research/historical/g3x/g3x_100c_historical_symbols.json` | `13524f24b855dddc9eb44ab5141020e5c8d34eb8a4a7f50c8e5914269a6bb86d` | Historical 1.00C symbol table JSON |
| `vendor/g3x-platform/platform/g3x/platform_camera.h` | `0fed491abe86c069166c4aadc50eceec81dd0da835943049e03b370fede9f6ac` | Camera configuration header |

### 4.2 Trusted Citation Provenance Registry (`CITATION_PROVENANCE_REGISTRY`)

To eliminate reliance on caller-supplied flags or unverified assumptions in mixed-firmware documents (such as [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md) and [`docs/PORT5A_RANMA_PORT_RECOVERY.md`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5A_RANMA_PORT_RECOVERY.md)), every cited `(path, line)` pair is recorded in `CITATION_PROVENANCE_REGISTRY` as an immutable `MappingProxyType`:
- **Strict Provenance Lookup**: Firmware identity and historical status are looked up directly from the registry. Caller-supplied flags cannot override registered values.
- **Fail-Closed on Unspecified Provenance**: Omitted or `None` citation flags never default to `GM1.10C`.
- **Conflict Detection**: Any discrepancy between caller-supplied flags and the registry triggers `RULE_PROVENANCE_CONFLICT` (severity `ERROR`).
- **Unregistered Citation Rejection**: Any citation referencing an uncataloged file or line triggers `RULE_UNREGISTERED_CITATION` (severity `ERROR`).

### 4.3 Authoritative Immutable Pins & Non-Production Override Behavior

`PINNED_ORIGIN_MAIN_FILE_HASHES` is an immutable `MappingProxyType` constant anchoring file digests to `origin/main` commit `581b1a4bb30456bf18c46dc4bcf61b0375aee251`.
- **Strict Production Gate**: If any test hook is provided to `evaluate()`—such as a `pinned_hashes` override dictionary, a custom `file_reader` callable, or an alternate `repo_root`—the evaluation engine automatically registers a finding with `RULE_NON_PRODUCTION_EVIDENCE_CONFIG` (severity `ERROR`).
- **No Path to Ready under Test Hooks**: Test configurations can still verify error reporting and hash-mismatch rejection, but overall readiness is strictly forced to `False`.

### 4.4 How to Verify and Refresh Digest Pins

When upstream commits introduce approved changes to evidence documents, refresh the digest pins using read-only git operations:

1. **Verify the current `origin/main` commit**:
   ```sh
   git rev-parse origin/main
   ```

2. **Compute the cryptographic SHA-256 of the target document on `origin/main`**:
   ```sh
   # Shell / Python stdlib pipeline:
   python3 -c "import hashlib, subprocess; print(hashlib.sha256(subprocess.check_output(['git', 'show', 'origin/main:docs/PORT11A_GM110C_ROM_EVIDENCE.md'])).hexdigest())"
   ```

3. **Update `ORIGIN_MAIN_PIN_COMMIT` and `PINNED_ORIGIN_MAIN_FILE_HASHES`** in [`tools/port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tools/port13_memory_obligations.py).

4. **Run unit tests to verify consistency**:
   ```sh
   python3 -B -m unittest tests.test_port13_memory_obligations
   ```

---

## 5. Tracked Address Provenance Ledger

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
- `0x007FFFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173)
- `0x00A00000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:174`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L174)
- `0x00B14DEF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:174`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L174)
- `0x00B14DF0`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173)
- `0x00BFFFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173)
- `0x00C16B90`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:173`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L173)
- `0x00C80000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x00DFFFFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x00E00000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:175`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L175)
- `0x010E1000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L78)
- `0x01107CFF`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:177`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L177)
- `0x01107D00`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L78)
- `0x20000000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L179)
- `0x40000000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L179)
- `0x406CE000`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0x43DBFCA0`: [`docs/PROJECT_STATE.md:308`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PROJECT_STATE.md#L308)
- `0x80A00000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:174`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L174)
- `0xBFE10000`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:178`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L178)
- `0xBFE10800`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xBFE14A3C`: [`docs/PORT11A_GM110C_ROM_EVIDENCE.md:20`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT11A_GM110C_ROM_EVIDENCE.md#L20)
- `0xBFE17418`: [`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:178`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md#L178)
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

## 6. Verification & Test Suite Status

The test suite [`tests/test_port13_memory_obligations.py`](file:///var/lib/agentbridge/worktrees/g3x-lite/port-13-offline-p13-oblig-mem/tests/test_port13_memory_obligations.py) executes deterministically under standard Python 3 `unittest` without external dependencies, network access, or subprocesses:

```sh
python3 -B -m unittest tests.test_port13_memory_obligations
```

### Test Results Ledger
- `test_current_overall_readiness_is_false`: **PASS** (18 obligations, readiness False, 17 warnings, 0 errors)
- `test_there_is_no_path_to_true_from_shipped_data`: **PASS** (17 of 18 unverified, individual subsets fail)
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
- `test_strict_allowlist_accepts_only_normalized_gm110c`: **PASS** (Strict allowlist normalizes and permits only GM1.10C)
- `test_verified_obligation_rejects_unsupported_firmware_variants`: **PASS** (Variants `'gm1.10e'`, `'GM1.10E '`, `'UNKNOWN'`, `''`, `None`, `'GM1.10X'` fail closed)
- `test_shipped_oblig_mem_10_fails_if_promoted_to_verified`: **PASS** (OMAR GM1.10E citation forces False with `RULE_HISTORICAL_CANNOT_VERIFY`)
- `test_all_shipped_historical_obligations_fail_if_promoted_to_verified`: **PASS** (All mixed-version historical citations fail closed)
- `test_no_shipped_verified_obligation_depends_only_on_historical_citations`: **PASS** (Generic invariant verified across dataset)
- `test_all_pinned_hashes_match_disk_files`: **PASS** (Cryptographic SHA-256 matches all 13 pinned origin/main files)
- `test_altered_content_at_allowed_path_fails_via_injectable_reader`: **PASS** (Tampered bytes trigger `RULE_CONTENT_HASH_MISMATCH`)
- `test_altered_content_at_allowed_path_fails_via_temp_root`: **PASS** (Tampered disk copy triggers `RULE_CONTENT_HASH_MISMATCH`)
- `test_unpinned_path_at_allowed_path_fails`: **PASS** (Tracked origin/main path lacking pin triggers `RULE_UNPINNED_SOURCE`)
- `test_unreadable_file_fails_closed`: **PASS** (Read/permission errors trigger `RULE_UNREADABLE_SOURCE`)
- `test_no_subprocess_imported`: **PASS** (`subprocess` strictly absent from tool imports)
- `test_stdlib_only`: **PASS** (No third-party packages imported)
- `test_all_obligations_serialize_to_dict`: **PASS** (JSON serialization integrity confirmed)
- `test_p1_canonical_ids_bound_to_trusted_requirements_fails_closed`: **PASS** (Reviewer reproduction with mutated obligations fails closed with `RULE_UNACCEPTABLE_SOURCE`, `RULE_REQUIREMENT_CONFLICT`, `RULE_PENDING_PR_CANNOT_VERIFY`)
- `test_property_reassign_citations_to_other_ids_trusted_sources_stays_not_ready`: **PASS** (Reassigning citations to any other ID's trusted sources keeps readiness False)
- `test_caller_requirement_conflict_fails_closed`: **PASS** (Caller-supplied conflicting requirement fields trigger `RULE_REQUIREMENT_CONFLICT`)
- `test_immutable_module_constants`: **PASS** (Immutability enforced on all MappingProxyType registries including `OBLIGATION_REQUIREMENTS_REGISTRY`)

**Total**: **40 executed, 40 PASS, 0 FAIL, 0 ERR** (1.10s).
