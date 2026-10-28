# PORT-11C — Offline Evidence Validation Harness

**Date**: 2026-10-28  
**Author**: Gemini Worker 6  
**Tech Lead**: ChatGPT  
**Base**: Latest Merged Main (`9c1c544`, merged PR #15)  
**Branch**: `research/port11c-evidence-harness`  
**Tool**: [`tools/port11c_evidence_validator.py`](../tools/port11c_evidence_validator.py)  
**Tests**: [`tests/test_port11c_evidence_validator.py`](../tests/test_port11c_evidence_validator.py)  
**Hardware Status**: **STRICT NO-GO** (Manifest-only offline validation utility; zero ROM inspection; zero camera/hardware access; standard library only).

---

## 1. Executive Summary & Purpose

The **PORT-11C Offline Evidence Harness** is a small, auditable, fail-closed offline validation tool designed for future G3X Lite firmware research.

### Why this tool is needed
During previous research milestones, two systematic vulnerabilities were uncovered:
1. **Contradictory and Unsupported Claims (PORT-10A Audit)**:
   In untracked documentation, conflicting prologue encodings (e.g. 16-bit Thumb `push {r4,r5,r6,lr}` vs 32-bit Thumb-2 `push.w {r1-r9,lr}`) and unverified historical constants (`0x8160`) from `GM1.10E` were repeatedly cited without clear provenance or address boundaries.
2. **Out-of-Scope Process Deviation (PORT-11A ROM Evidence)**:
   While verifying U1, U2, and U3 in `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, an agent conducted unauthorized full-ROM branch scans (`Step 223`, scanning 33.5 MB across `0x000000..0x1FFFFFD`) due to the absence of machine-enforced scope boundaries.

PORT-11C eliminates these risks by introducing a **machine-readable evidence manifest schema** and an **automated validation engine** that strictly enforces:
- **Scope Authorization**: Every evidence entry must reference an approved authorization scope ID with explicit address ranges and byte quotas. Claims outside approved ranges are rejected.
- **Range & Arithmetic Invariants**: Start/end bounds, hex formatting, span arithmetic (`end - start + 1 == expected_byte_count`), and 32-bit address spaces are mathematically verified.
- **Provenance Verification**: Sources must belong to recognized categories (`ROM_VERIFIED`, `SOURCE_REPO`, `HISTORICAL_CHDK`, `HARDWARE_WITNESS`, `SYNTHETIC_FIXTURE`).
- **Conflict & Overlap Detection**: Overlapping or conflicting slices (differing hashes, contradictory classifications, or byte mismatches) are flagged and rejected.
- **Deterministic Synthetic Fixtures**: Offline validation relies exclusively on synthetic byte fixtures, preserving zero-ROM security.

---

> [!CAUTION]
> **AUTHORIZATION TRUST BOUNDARY & NON-AUTHORITY NOTICE**:
> 1. **This utility DOES NOT and CANNOT grant permission to inspect, dump, or execute ROM/firmware.**
> 2. Authorization to inspect firmware regions is strictly an external human governance gate. It requires explicit owner/tech lead approval recorded in repository safety documentation *before* any inspection takes place.
> 3. **Manifest-declared scopes are self-assertions by the researcher/author.** A manifest cannot grant itself authority. When validated without an external trusted policy, the tool validates only internal self-consistency (`SELF_DECLARED_INTERNAL_ONLY`) and emits `RULE_TRUST_BOUNDARY_NOTICE`.
> 4. To verify actual research boundary compliance, the manifest must be validated against an independent, authenticated policy file via `--trusted-scopes <policy.json>` (`TRUSTED_POLICY_VERIFIED`). Any manifest attempt to define unapproved scopes or expand approved address bounds is rejected (`RULE_SCOPE_POLICY_VIOLATION`).

---

## 2. Security and Scope Invariants

The first version of the harness is **manifest-only** and strictly conforms to the following safety constraints:

| Constraint | Enforcement Mechanism |
|---|---|
| **No Firmware / ROM File Access** | Tool strictly refuses to open or inspect files with extensions `.bin`, `.rom`, `.dump`, `.fir`, `.fi2`, `.img`, `.gpr`, `.rep`, or files named `PRIMARY.*`. Fails closed with exit code 2. |
| **No Directory ROM Searches** | Operates strictly on explicitly provided manifest JSON paths; performs zero filesystem crawling or heuristic discovery. |
| **No Subprocesses** | Tool does not import or execute `subprocess`, `os.system`, or shell commands (`test_tool_does_not_import_subprocess` verifies this in AST/module imports). |
| **No Opcode Disassembly** | Does not import `capstone`, `radare2`, `ghidra`, or perform any instruction decoding. |
| **No Full-ROM Scans** | Manifest files are capped at 10 MiB to prevent memory exhaustion; no full-ROM byte searches. |
| **Synthetic Byte Fixtures Only** | Test suite uses deterministic in-memory synthetic byte patterns only. |
| **Python Standard Library Only** | Pure Python standard library (`argparse`, `dataclasses`, `enum`, `hashlib`, `json`, `pathlib`, `re`, `sys`, `typing`). |
| **Provenance Verification vs ROM Ground Truth** | Tool validates that declared provenance structures conform to schema formats and recognized types. It does **not** authenticate that declared SHA-256 hashes correspond to real Canon ROM; verifying physical ROM bytes requires external human audit trails. |

---

## 3. Evidence Manifest Schema Specification

An evidence manifest is a structured JSON document containing two primary sections: `authorization_scopes` and `evidence_entries`.

### 3.1 Authorization Scope Schema (`authorization_scopes`)
Authorization scopes represent explicit research boundaries approved by the project owner or tech lead.

```json
{
  "scope_id": "SCOPE-PORT11A-U1",
  "firmware_revision": "GM1.10C",
  "approved_ranges": [
    {
      "start_address": "0xFC020040",
      "end_address": "0xFC0200CF",
      "label": "S1A ATCM copy loop"
    },
    {
      "start_address": "0xFC31BBC4",
      "end_address": "0xFC31BBCB",
      "label": "S1B j_CreateTask veneer"
    }
  ],
  "max_bytes_total": 1024,
  "allowed_classifications": ["STATIC_VERIFIED", "INFERRED", "UNKNOWN"],
  "description": "U1 CreateTask prologue inspection scope"
}
```

Fields:
- `scope_id` (string, required): Unique identifier for the authorized scope.
- `firmware_revision` (string, required): Firmware revision authorized (e.g. `GM1.10C`).
- `approved_ranges` (list, required): List of authorized address intervals (`start_address`, `end_address`, optional `label`).
- `max_bytes_total` (integer, optional): Maximum cumulative bytes approved under this scope.
- `allowed_classifications` (list, optional): Allowed certainty classifications.
- `description` (string, optional): Human-readable purpose of the scope.

### 3.2 Evidence Entry Schema (`evidence_entries`)
Evidence entries represent discrete claims regarding firmware bytes or structures.

```json
{
  "evidence_id": "PORT11A-S1A",
  "firmware_revision": "GM1.10C",
  "start_address": "0xFC020040",
  "end_address": "0xFC0200CF",
  "expected_byte_count": 144,
  "sha256": "a8bea578f65643701322d3ce2fc500d04485323dbb28bfab6e89a51a6344c54b",
  "provenance_source": {
    "type": "ROM_VERIFIED",
    "reference": "PRIMARY.BIN#docs/PORT11A_GM110C_ROM_EVIDENCE.md#S1A"
  },
  "authorization_scope_id": "SCOPE-PORT11A-U1",
  "classification": "STATIC_VERIFIED",
  "notes": "Early boot ATCM copy loop & literal pool"
}
```

Fields:
- `evidence_id` (string, required): Unique identifier (e.g. `PORT11A-S1A`).
- `firmware_revision` (string, required): Target firmware revision (must match scope).
- `start_address` / `end_address` (hex string or integer, required): Address bounds (inclusive). Can alternatively be passed as `address_range: "0xFC020040..0xFC0200CF"`.
- `expected_byte_count` (integer, required): Must strictly equal `end_address - start_address + 1`.
- `sha256` (string, required): 64-character lowercase hex digest of the slice bytes.
- `provenance_source` (string or dict, required): Authenticated provenance descriptor. Supported types:
  - `ROM_VERIFIED`: Static inspection from owner-authorized ROM dump.
  - `SOURCE_REPO`: Tracked repository document or source code.
  - `HISTORICAL_CHDK`: Historical reference port or patch (e.g. `g3x_110e.patch`).
  - `HARDWARE_WITNESS`: Hardware witness or diagnostic report (e.g. `BOOT-001A`).
  - `SYNTHETIC_FIXTURE`: Test or synthetic fixture for offline validation.
- `authorization_scope_id` (string, required): Must reference a valid `scope_id` in `authorization_scopes`.
- `classification` (string, required): Must be one of `STATIC_VERIFIED`, `INFERRED`, `UNKNOWN`.
- `notes` (string, optional): Explanatory commentary.

---

## 4. Validation Rules & Failure Modes

The validator executes eight systematic checks, emitting structured diagnostic findings:

| Rule ID | Name | Failure Condition | Severity |
|---|---|---|:---:|
| `RULE_DUPLICATE_ID` | Duplicate Evidence ID | Two or more entries declare identical `evidence_id` values. | ERROR |
| `RULE_MALFORMED_RANGE` | Malformed Range | `start > end`, address out of 32-bit range (`> 0xFFFFFFFF`), unparseable hex, non-positive byte count, or `expected_byte_count != end - start + 1`. | ERROR |
| `RULE_INVALID_CLASSIFICATION` | Invalid Classification | Classification is not one of `STATIC_VERIFIED`, `INFERRED`, `UNKNOWN`. | ERROR |
| `RULE_UNSUPPORTED_PROVENANCE` | Unsupported Provenance | Missing, empty, or unrecognized provenance category/prefix. | ERROR |
| `RULE_MISSING_SCOPE` | Missing Scope ID | `authorization_scope_id` is missing or empty. | ERROR |
| `RULE_UNAPPROVED_SCOPE` | Unapproved Scope | `authorization_scope_id` does not exist in active scopes. | ERROR |
| `RULE_SCOPE_EXCEEDED` | Scope Exceeded | Range outside approved bounds, slice extends across boundary, firmware revision mismatch, disallowed classification, or total bytes exceed scope quota. | ERROR |
| `RULE_SCOPE_POLICY_VIOLATION` | Scope Policy Violation | Manifest attempts to self-declare scopes not authorized in external trusted policy, or attempts to broaden approved ranges/quotas. | ERROR |
| `RULE_TRUST_BOUNDARY_NOTICE` | Trust Boundary Notice | Emitted when manifest is evaluated in internal-consistency mode without an external trusted policy file. | WARN |
| `RULE_OVERLAPPING_SLICES` | Overlapping Slices | Two slices in the same firmware revision overlap in address space (under default strict non-overlapping policy). | ERROR |
| `RULE_INCONSISTENT_SLICES` | Inconsistent Slices | Identical address ranges claim conflicting SHA-256 or classifications; or overlapping synthetic fixtures contain conflicting byte data. | ERROR |
| `RULE_FIXTURE_LENGTH_MISMATCH` | Fixture Length Mismatch | Provided synthetic fixture length differs from `expected_byte_count`. | ERROR |
| `RULE_FIXTURE_HASH_MISMATCH` | Fixture Hash Mismatch | SHA-256 of synthetic fixture does not match manifest `sha256`. | ERROR |

---

## 5. Real-World Case Study: Canonical PORT-11A Slices

To demonstrate how the validator protects research integrity, the nine canonical slices from `docs/PORT11A_GM110C_ROM_EVIDENCE.md` (§2.3) were codified and verified:

| Slice ID | Address Range | Size | Scope | Status in Validator |
|---|---|---:|---|:---:|
| `PORT11A-S1A` | `0xFC020040..0xFC0200CF` | 144 B | `SCOPE-PORT11A-U1` | PASS |
| `PORT11A-S1B` | `0xFC31BBC4..0xFC31BBCB` | 8 B | `SCOPE-PORT11A-U1` | PASS |
| `PORT11A-S1C` | `0xFCEF3488..0xFCEF36B3` | 556 B | `SCOPE-PORT11A-U1` | PASS |
| `PORT11A-S1D` | `0xFC31BE8C..0xFC31BE93` | 8 B | `SCOPE-PORT11A-U1` | PASS |
| `PORT11A-S1E` | `0xFCEF3F34..0xFCEF3F55` | 34 B | `SCOPE-PORT11A-U1` | PASS |
| `PORT11A-S2A` | `0xFC0BD070..0xFC0BD1BB` | 332 B | `SCOPE-PORT11A-U2` | PASS |
| `PORT11A-S2B` | `0xFC0D9CCC..0xFC0D9D25` | 90 B | `SCOPE-PORT11A-U2` | PASS |
| `PORT11A-S3A` | `0xFC1283AC..0xFC1283FF` | 84 B | `SCOPE-PORT11A-U3` | PASS |
| `PORT11A-S3B` | `0xFC128704..0xFC12871F` | 28 B | `SCOPE-PORT11A-U3` | PASS |

- **Total Canonical Bytes**: `1,284` bytes.
- **Overlap Result**: All 9 slices are mutually disjoint. Overlap count = 0.
- **Process Deviation Prevention**: When an entry representing the out-of-scope branch scan target (`0xFC079130`) is added, the validator immediately rejects it with `RULE_SCOPE_EXCEEDED` (`test_out_of_scope_scan_claim_is_rejected`).

---

## 6. CLI & API Usage

### Command Line Interface

```sh
# Validate a manifest against an external trusted scope policy (Authoritative Mode)
python3 -B tools/port11c_evidence_validator.py --manifest path/to/evidence_manifest.json --trusted-scopes path/to/trusted_policy.json

# Validate a manifest file in self-declared internal consistency mode
python3 -B tools/port11c_evidence_validator.py --manifest path/to/evidence_manifest.json

# Output findings in JSON format
python3 -B tools/port11c_evidence_validator.py --manifest path/to/evidence_manifest.json --json

# Allow consistent overlapping slices
python3 -B tools/port11c_evidence_validator.py --manifest manifest.json --allow-overlap
```

#### Exit Codes
- `0`: Manifest is completely valid (zero errors).
- `1`: Validation failed (one or more `ERROR` findings).
- `2`: Invocation / file load / security violation error (e.g. file not found, forbidden binary file).

### Python Library Interface

```python
from tools.port11c_evidence_validator import (
    EvidenceManifest,
    EvidenceValidator,
    load_manifest_file,
    load_scopes_file,
)

manifest, err = load_manifest_file("manifest.json")
if err:
    raise RuntimeError(err)

trusted_scopes, s_err = load_scopes_file("trusted_scopes.json")
if s_err:
    raise RuntimeError(s_err)

validator = EvidenceValidator(allow_overlapping_slices=False)
result = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes)

if not result.is_valid:
    for finding in result.findings:
        print(f"[{finding.rule_id}] {finding.message}")
```

---

## 7. Verification & Test Suite

The test suite in [`tests/test_port11c_evidence_validator.py`](../tests/test_port11c_evidence_validator.py) provides 43 deterministic offline unit tests:

1. **Manifest Parsing (6 tests)**: Valid dictionaries, JSON strings, address range syntax (`0x...0x...`), invalid JSON, non-object roots, and missing mandatory fields.
2. **Validation Rules (17 tests)**: Inverted ranges, byte count mismatches, non-positive byte counts, duplicate IDs, unsupported provenance, empty provenance, missing scopes, unapproved scopes, address outside scope, slices extending past scope bounds, firmware revision mismatches, disallowed classifications, scope byte quotas, and strict overlapping slice rejection.
3. **Synthetic Byte Fixtures (4 tests)**: Matching fixture verification, length mismatches, bit-flip SHA-256 corruption detection, and conflicting byte data in overlapping fixtures.
4. **Security & Scope Enforcement (4 tests)**: Verification of zero `subprocess` imports, refusal of `.bin`/`.rom`/`.dump`/`.fir` extensions, refusal of `PRIMARY.*` files, and rejection of oversized manifests (> 10 MiB).
5. **Real-World Case Study (2 tests)**: End-to-end verification of the 9 canonical PORT-11A slices (`1,284` B) and rejection of out-of-scope scan claims.
6. **Authorization Trust Boundary (5 tests)**: Enforcement of external trusted policy vs manifest declarations, rejection of unauthorized manifest-declared scopes, rejection of range expansions, trust level labeling, and CLI `--trusted-scopes` policy enforcement.
7. **Command-Line Interface (5 tests)**: Exit codes 0, 1, 2, security refusal via CLI, and formatted JSON output.

### Test Execution Command
```sh
python3 -B -m unittest tests/test_port11c_evidence_validator.py -v
# Output: Ran 43 tests in 0.054s — OK
```

Full repository port tests also pass cleanly:
```sh
python3 -B tools/bootstrap_chdk_platform.py && python3 -B tools/port9b_runtime_contract.py --target chdk-port && python3 -B -m unittest discover -s tests -p 'test_port*.py' -v
# Output: Ran 220 tests — OK
```

---

---

## 8. Independent Security & Trust Boundary Audit (Worker G2, Post-PR #16)

Following the PR #16 merge (`7f39946`), an independent audit of the PORT-11C Evidence Harness was conducted across seven critical trust and security dimensions:

### 8.1 External Trusted-Scopes Policy vs. Actual Human Authorization
- **Audit Finding**: Supplying an external `--trusted-scopes` JSON file merely proves that the manifest entries comply syntactically with that file's declared schema boundaries.
- **Critical Distinction**: A file on disk does **NOT** constitute authentic human authorization. In an automated multi-agent workflow, an agent could synthesize a permissive policy file.
- **Fail-Closed Resolution**: The validator does not evaluate human identities, digital signatures, or authorization authority. It explicitly marks external policy validation as `TRUSTED_POLICY_VERIFIED` against the provided file, but includes the permanent invariant: `rom_permission_granted = False`.
- Actual human authorization to inspect or execute firmware remains strictly an external governance gate requiring explicit Owner/Tech Lead sign-off documented in `docs/SAFETY.md`.

### 8.2 Trusted Policy Fixture Merely Asserts Approval
- **Audit Finding**: In `tests/fixtures/port11a_trusted_scopes.json`, the field `"policy_authority": "Owner/Tech Lead Authorized PORT-11A Research Scope"` is a descriptive metadata string, not cryptographic proof.
- **Resolution**: Fixtures are classified as offline test specifications only. They cannot be used as automated authorization tokens for future phases.

### 8.3 Parser Validation & Malformed-Input Fail-Closed Handling
- **Audit Finding**: `load_scopes_file()` previously lacked an explicit file-size bound and did not strictly validate that root JSON or `authorization_scopes` structures were lists of dictionaries.
- **Resolution**: Hardened both `load_manifest_file()` and `load_scopes_file()` with:
  1. Strict `MAX_MANIFEST_BYTES` (10 MiB) size guard before reading content.
  2. Root-type validation: root JSON must be a dict or list; scalar roots (`int`, `str`, `bool`, `null`) fail closed.
  3. Schema type validation: `authorization_scopes` must be a list of dicts.
  4. Non-positive byte count rejection: `expected_byte_count <= 0` is strictly rejected.

### 8.4 Path and Binary-Access Restrictions
- **Audit Finding**: The validator must enforce a total ban on opening raw binary firmware files.
- **Resolution**: Hardened `FORBIDDEN_FILE_EXTENSIONS` (`.bin`, `.rom`, `.dump`, `.fir`, `.fi2`, `.img`, `.gpr`, `.rep`) with case-insensitive basename inspection rejecting any path containing `"primary"` or `"rom"` in both manifest and scopes loaders. Symlinks are resolved via `.resolve()` prior to inspection.

### 8.5 Scope Boundaries & Cumulative Quota Accounting
- **Audit Finding**: Slices must not exceed individual range bounds or aggregate scope quotas.
- **Resolution**: Verified that `EvidenceValidator` enforces cumulative byte quota accounting per scope (`scope_byte_totals[sid] += entry.expected_byte_count`). Boundary unit tests (`test_scope_cumulative_quota_boundary_enforcement`) verify that an exact quota (e.g. 100 B) passes, while quota + 1 B fails closed with `RULE_SCOPE_EXCEEDED`.

### 8.6 Manifest / Provenance Trust Assumptions
- **Audit Finding**: Manifests declare provenance strings (e.g., `ROM_VERIFIED:PRIMARY.BIN@0xFC020040`).
- **Resolution**: The validator checks category membership against `ProvenanceType` enums and syntax structure, but does not claim that the underlying binary bytes exist or have been read. Provenance verification is structural, not physical.

### 8.7 Synthetic Fixture Test Completeness
- **Audit Finding**: Offline tests must never require or open proprietary ROM dumps.
- **Resolution**: All 49 unit tests operate exclusively on synthetic in-memory byte buffers and JSON fixtures. All tests execute deterministically in <= 0.05 s.

### 8.8 Non-Authority Invariant: Zero ROM-Reading Permission
- **Non-Negotiable Invariant**:
  **The validator must NEVER claim to grant ROM-reading permission.**
- Both internal and trusted-policy validation results guarantee `rom_permission_granted == False` and embed the canonical disclaimer:
  > *"This tool validates offline declarations and synthetic test fixtures only; it possesses NO authority to grant ROM-reading, firmware dumping, or camera execution permission."*

---

## 9. Remaining Limitations


1. **Manifest-Only Scope**: The tool validates declarations, hashes, and synthetic byte fixtures. It does not inspect physical camera hardware, execute live code, or evaluate dynamic DryOS runtime states.
2. **Provenance Trust Boundary**: The tool verifies that declared provenance strings/objects match recognized types and valid formats, but cannot independently vouch for external human statements without cryptographic proof or tracked repository artifacts.
3. **Instruction Semantics**: The validator verifies address spans and byte digests; it deliberately performs zero instruction decoding or control-flow analysis. Instruction semantics remain governed by PORT-9B contracts and human review.
