#!/usr/bin/env python3
"""tools/port13_u2_obligations.py

PORT-13 / Task p13-oblig-u2-r2: Fail-closed proof obligations for GM1.10C
InitFileModules (Prerequisite U2 / Interface I2) filesystem readiness.

This module formalizes the proof obligations required before anyone can claim
filesystem mount readiness after InitFileModules on Canon PowerShot G3 X GM1.10C.

Grounded strictly in:
  - docs/PORT13_REVIEW_U2.md (Final review of PR #24, findings CLM-01..16, remediation items 1..8)
  - docs/PORT11A_GM110C_ROM_EVIDENCE.md (ROM slices S2A & S2B static evidence)
  - tools/port9a_runtime_lifecycle.py (FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS & state machine)
  - tools/port9b_runtime_contract.py (I2 contract, Fact U2, C3.gate, C5.U2, C6.fs_readiness_contract)
  - docs/RESTART_SD_HOST_AUDIT.md (Warm-restart SD host retention and CMD0 / SD1stInit audit)
  - docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md (Historical port comparison)
  - docs/PORT5A_RANMA_PORT_RECOVERY.md (Historical port recovery audit)

Key Safety & Epistemic Invariants:
  - Standard library only; strictly NO subprocess calls, NO binary modifications,
    NO ROM dump scans, and NO hardware access.
  - Phase 0 read-only verification: static ROM entry evidence does NOT establish
    runtime filesystem readiness.
  - Statically evidenced Thumb entry 0xFC0BD071 (instruction address 0xFC0BD070)
    may satisfy ONLY the static task entry obligation. It must NEVER satisfy any
    runtime readiness obligation.
  - Fail-closed: evaluate() returns not-ready (is_ready=False) for shipped data;
    there is no path to ready from shipped data.
  - Zero new firmware addresses: every address appearing in this module is
    already registered in a tracked origin/main document, cited file:line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# -----------------------------------------------------------------------------
# Interoperability: Import PORT-9B and PORT-9A contracts (Standard Library Only)
# -----------------------------------------------------------------------------
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
REPO_ROOT_DEFAULT = TOOLS_DIR.parent
if str(REPO_ROOT_DEFAULT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_DEFAULT))

try:
    import port9b_runtime_contract as p9b  # type: ignore
    import port9a_runtime_lifecycle as rt  # type: ignore
except ImportError:
    try:
        import tools.port9b_runtime_contract as p9b  # type: ignore
        import tools.port9a_runtime_lifecycle as rt  # type: ignore
    except ImportError as err:
        raise ImportError(f"Cannot import port9b or port9a runtime contracts: {err}") from err


# -----------------------------------------------------------------------------
# Enums and Rule Constants
# -----------------------------------------------------------------------------

class ObligationKind(str, Enum):
    """Classification of proof obligation: static ROM evidence vs dynamic runtime."""
    STATIC = "static"
    RUNTIME = "runtime"

    @classmethod
    def from_string(cls, val: str) -> ObligationKind:
        norm = val.strip().lower()
        if norm in ("static", "rom_static"):
            return cls.STATIC
        if norm in ("runtime", "dynamic", "dynamic_runtime"):
            return cls.RUNTIME
        raise ValueError(f"Invalid ObligationKind '{val}'. Allowed: {[m.value for m in cls]}")


class ObligationStatus(str, Enum):
    """Epistemic certainty status of an obligation."""
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, val: str) -> ObligationStatus:
        norm = val.strip().upper()
        if norm in ("VERIFIED", "STATIC_VERIFIED"):
            return cls.VERIFIED
        if norm == "INFERRED":
            return cls.INFERRED
        if norm in ("UNKNOWN", "CONTRADICTED", "HISTORICAL_CANDIDATE"):
            return cls.UNKNOWN
        raise ValueError(f"Invalid ObligationStatus '{val}'. Allowed: {[m.value for m in cls]}")


class EvaluationVerdict(str, Enum):
    """Aggregate evaluation outcome."""
    NOT_READY = "not-ready"
    READY = "ready"


RULE_MISSING_CITATIONS = "RULE_MISSING_CITATIONS"
RULE_FORBIDDEN_LOCAL_PATH = "RULE_FORBIDDEN_LOCAL_PATH"
RULE_UNTRACKED_PATH = "RULE_UNTRACKED_PATH"
RULE_MISSING_CITED_PATH = "RULE_MISSING_CITED_PATH"
RULE_UNREADABLE_SOURCE = "RULE_UNREADABLE_SOURCE"
RULE_CONTENT_HASH_MISMATCH = "RULE_CONTENT_HASH_MISMATCH"
RULE_STATIC_CANNOT_DISCHARGE_RUNTIME = "RULE_STATIC_CANNOT_DISCHARGE_RUNTIME"
RULE_STATUS_UNVERIFIED = "RULE_STATUS_UNVERIFIED"
RULE_EVIDENCE_STATUS_NOT_VERIFIED = "RULE_EVIDENCE_STATUS_NOT_VERIFIED"
RULE_PRECONDITION_INVARIANT_VIOLATED = "RULE_PRECONDITION_INVARIANT_VIOLATED"
RULE_CONTRACT_INVARIANT_VIOLATED = "RULE_CONTRACT_INVARIANT_VIOLATED"
RULE_ADDRESS_NOT_TRACKED = "RULE_ADDRESS_NOT_TRACKED"
RULE_EMPTY_DATASET = "RULE_EMPTY_DATASET"
RULE_INCOMPLETE_OBLIGATION_SET = "RULE_INCOMPLETE_OBLIGATION_SET"
RULE_ARTIFACT_TYPE_MISMATCH = "RULE_ARTIFACT_TYPE_MISMATCH"
RULE_NONCANONICAL_OBLIGATION = "RULE_NONCANONICAL_OBLIGATION"
RULE_UNTRUSTED_RUNTIME_PROVENANCE = "RULE_UNTRUSTED_RUNTIME_PROVENANCE"


# -----------------------------------------------------------------------------
# Forbidden Local / Untracked Path Patterns
# -----------------------------------------------------------------------------

FORBIDDEN_PATH_PREFIXES: Tuple[str, ...] = (
    "firmware/",
    "firmware",
    "PORT-9A L1",
    "PORT-9A L2",
    "L1/L2",
    "PORT-9A_L1",
    "PORT-9A_L2",
)


# -----------------------------------------------------------------------------
# Tracked Origin/Main File Whitelist & SHA-256 Digest Pins
# -----------------------------------------------------------------------------

ORIGIN_MAIN_PIN_COMMIT: str = "581b1a4bb30456bf18c46dc4bcf61b0375aee251"
SUPPORTED_FIRMWARE: str = "GM1.10C"

PINNED_FILE_HASHES: Dict[str, str] = {
    "docs/PORT11A_GM110C_ROM_EVIDENCE.md": "45928b29efc2062796ae51a326fcfec2f650e9589944f530158b7a9dcaaec8da",
    "tools/port9a_runtime_lifecycle.py": "77da2bfa5fb018590ec60215afc440b48d2fe1d618e6ce121f4253d21b667d93",
    "tools/port9b_runtime_contract.py": "d51d03e01e2df820b03e659782fb5814f1dadc00cea95ba3760bbaaf4e7b3a4b",
    "docs/PORT13_REVIEW_U2.md": "6b7f5080db6a31a34da3a3c62ae52b3d6efe2449b82f322cfb0d836665ec666e",
    "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md": "9855a2316aba777065547f7e8f30a3aabff5cff8ce94be48deb3c10406df281c",
    "docs/PORT5A_RANMA_PORT_RECOVERY.md": "6c68897320b97c6d67a2ad6f6554c41a98d11105d8ab45394186a738364400e8",
    "docs/RESTART_SD_HOST_AUDIT.md": "50f96cfe651372b19536f2f70145217d6d291f4ce5be2eb56225e8423399ec4b",
    "docs/PORT9A_RUNTIME_INTEGRATION_MAP.md": "d9cb03e15c417625723dd516e4227a49c9938d3dae2ca42d8d09eab0d6c69c70",
}

# Complete set of git-tracked files in the repository baseline
ORIGIN_MAIN_TRACKED_FILES: frozenset[str] = frozenset({
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
    "chdk-port/platform/g3x/sub/110c/boot_witness.h",
    "chdk-port/platform/g3x/sub/110c/stubs_prototype.S",
    "docs/AGENT_PROMPT.md",
    "docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md",
    "docs/CHDK_PORT1C1_CRITICAL_AUDIT.md",
    "docs/CHDK_PORT_COMPARISON.md",
    "docs/CODEX_INDEPENDENT_RESTART_REVIEW.md",
    "docs/FIRMWARE_ACQUISITION_PLAN.md",
    "docs/FIRMWARE_MATRIX.md",
    "docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md",
    "docs/GM110C_FUNCTION_MAP.md",
    "docs/GM110C_GHIDRA_SETUP.md",
    "docs/GM110C_MEMORY_MAP.md",
    "docs/GM110C_ROM_ANALYSIS.md",
    "docs/HANDOFF.md",
    "docs/HDMI001_CANDIDATES.md",
    "docs/HDMI001_INDEPENDENT_REVIEW.md",
    "docs/HDMI001_OVERLAY_PIPELINE.md",
    "docs/PATCH_AUDIT_110E.md",
    "docs/PHASE0C_REPORT.md",
    "docs/PHASE0_REPORT.md",
    "docs/PHASE1_ENTRY_CHECKLIST.md",
    "docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md",
    "docs/PORT11A_GM110C_ROM_EVIDENCE.md",
    "docs/PORT11B_ADVERSARIAL_FINDINGS.md",
    "docs/PORT11B_RUNTIME_SAFETY_MODEL.md",
    "docs/PORT11C_EVIDENCE_HARNESS.md",
    "docs/PORT13_REVIEW_PR23.md",
    "docs/PORT13_REVIEW_U2.md",
    "docs/PORT13_REVIEW_U4.md",
    "docs/PORT3A_RESTART_IRQ_AUDIT.md",
    "docs/PORT3B_IRQ_REGISTER_SEMANTICS.md",
    "docs/PORT3C_RESTART_READINESS_MATRIX.md",
    "docs/PORT5A_RANMA_PORT_RECOVERY.md",
    "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
    "docs/PORT5C_EARLY_BOOT_CONSISTENCY_AUDIT.md",
    "docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md",
    "docs/PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md",
    "docs/PORT7B_PLAYBACK_MASK_CORRECTION.md",
    "docs/PORT7C_PLATFORM_VALIDATION_FRAMEWORK.md",
    "docs/PORT8A_PLATFORM_BOOTSTRAP.md",
    "docs/PORT9A_RUNTIME_INTEGRATION_MAP.md",
    "docs/PORT9B_RUNTIME_CONTRACT.md",
    "docs/PORT_READINESS.md",
    "docs/PROJECT_STATE.md",
    "docs/REPRODUCIBILITY_MANIFEST.md",
    "docs/RESEARCH_LOG.md",
    "docs/RESEARCH_PLAN.md",
    "docs/RESTART_SD_HOST_AUDIT.md",
    "docs/REVERSE_ENGINEERING.md",
    "docs/SAFETY.md",
    "docs/agentbridge/PORT13_BASELINE.md",
    "firmware/README.md",
    "firmware/tools/cbasic_activation_probe.m",
    "firmware/tools/extend.m",
    "firmware/tools/hdmi001_clean_overlay_gm110c.m",
    "firmware/tools/witness_inspector_gm110c.m",
    "firmware/tools/witness_inspector_metadata.json",
    "firmware/tools/witness_inspector_payload.S",
    "firmware/tools/witness_inspector_payload.bin",
    "patches/0001-sd1stinit-restart-prototype.patch",
    "patches/0002-port7b-keys-mask0.patch",
    "research/historical/g3x/g3x_100c_historical_symbols.csv",
    "research/historical/g3x/g3x_100c_historical_symbols.json",
    "research/historical/g3x/g3x_three_version_symbol_comparison.csv",
    "research/historical/g3x/g3x_three_version_symbol_comparison.json",
    "tests/fixtures/port11a_manifest.json",
    "tests/fixtures/port11a_trusted_scopes.json",
    "tests/fixtures/port7b/kbd.c",
    "tests/fixtures/port7b/platform_camera.h",
    "tests/fixtures/port7b/platform_kbd.h.preimage",
    "tests/fixtures/port7b/shooting.c",
    "tests/test_early_boot_literals.py",
    "tests/test_port11b_adversarial.py",
    "tests/test_port11c_evidence_validator.py",
    "tests/test_port7a_platform_configuration.py",
    "tests/test_port7b_reproducibility.py",
    "tests/test_port7c_platform_validation.py",
    "tests/test_port8a_platform_bootstrap.py",
    "tests/test_port9a_runtime_lifecycle.py",
    "tests/test_port9b_runtime_contract.py",
    "tests/test_restart_sd_audit.py",
    "tests/test_validate_hdmi001.py",
    "tests/test_validate_witness_inspector.py",
    "tools/analyze_rom.py",
    "tools/bootstrap_chdk_platform.py",
    "tools/build_witness_inspector.py",
    "tools/find_eventprocs.py",
    "tools/ghidra/ExpandAndReportHdmi.java",
    "tools/ghidra/ReportDisplayStringRefs.java",
    "tools/ghidra/SeedAndReportHdmi.java",
    "tools/ghidra/SeedAndReportOverlay.java",
    "tools/port11c_evidence_validator.py",
    "tools/port9a_runtime_lifecycle.py",
    "tools/port9b_runtime_contract.py",
    "tools/validate_hdmi001_script.py",
    "tools/validate_witness_inspector.py",
    "vendor/g3x-platform/MANIFEST.json",
    "vendor/g3x-platform/platform/g3x/kbd.c",
    "vendor/g3x-platform/platform/g3x/lib.c",
    "vendor/g3x-platform/platform/g3x/platform_camera.h",
    "vendor/g3x-platform/platform/g3x/platform_kbd.h",
    "vendor/g3x-platform/platform/g3x/shooting.c",
})


# -----------------------------------------------------------------------------
# Trusted Runtime Witnesses Registry (Positive Allowlist)
# -----------------------------------------------------------------------------
# Positive allowlist of approved runtime witness artifacts and citations.
# In Phase 0 offline verification, NO runtime execution witnesses exist on origin/main.
# Any existing tracked document, source file, review, or static analysis must never
# discharge a runtime obligation, regardless of caller-supplied labels or metadata.
#
# This registry is strictly EMPTY in shipped code. Populating any entry in this
# registry requires physical hardware execution, dynamic telemetry capture, and
# a separately authorized, human-reviewed pull request following phase transition.
#
# Because this registry is empty, aggregate ready is structurally unreachable
# from shipped data or any caller-supplied artifacts citing repository files.
TRUSTED_RUNTIME_WITNESSES: frozenset[str] = frozenset()


# -----------------------------------------------------------------------------
# Address Registry: Every firmware address cited in this module
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class AddressCitation:
    address: str
    document_ref: str
    line: int
    description: str


TRACKED_ADDRESS_CITATIONS: Dict[str, AddressCitation] = {
    "0xFC0BD071": AddressCitation("0xFC0BD071", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 21, "task_InitFileModules Thumb entry pointer in literal pool [0xFC0BD1A8]"),
    "0xFC0BD070": AddressCitation("0xFC0BD070", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 21, "task_InitFileModules Thumb instruction address (push {r4, r5, r6, lr})"),
    "0xFC0BD0B4": AddressCitation("0xFC0BD0B4", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 21, "sub_fc0bd0b4 InitFileModules creator function start"),
    "0xFC31BBC4": AddressCitation("0xFC31BBC4", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "j_CreateTask ARM kernel veneer in ROM"),
    "0xBFE14A3C": AddressCitation("0xBFE14A3C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "CreateTask Cortex-R4 ATCM entry instruction address"),
    "0xFC0BD1A8": AddressCitation("0xFC0BD1A8", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 235, "Literal pool entry holding 0xFC0BD071"),
    "0xFC0BD1AC": AddressCitation("0xFC0BD1AC", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 236, "String literal 'InitFileModules' in literal pool"),
    "0xFC0BD072": AddressCitation("0xFC0BD072", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 252, "task_InitFileModules call to sub_fc0d9ccc (bl 0xFC0D9CCC)"),
    "0xFC0BD076": AddressCitation("0xFC0BD076", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 253, "task_InitFileModules movs r4, r0 saving callee 1 return value"),
    "0xFC0BD078": AddressCitation("0xFC0BD078", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 254, "task_InitFileModules movw r5, #0x5006 loading event constant"),
    "0xFC0BD07C": AddressCitation("0xFC0BD07C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 255, "task_InitFileModules beq 0xFC0BD086 branching when r0 == 0"),
    "0xFC0BD082": AddressCitation("0xFC0BD082", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 258, "task_InitFileModules call to 0xFC35B93C(0x5006, 0)"),
    "0xFC0BD086": AddressCitation("0xFC0BD086", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 259, "task_InitFileModules call to sub_fc0d9cf6 (bl 0xFC0D9CF6)"),
    "0xFC0BD08A": AddressCitation("0xFC0BD08A", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 260, "task_InitFileModules cmp r4, #0"),
    "0xFC0BD08C": AddressCitation("0xFC0BD08C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 261, "task_InitFileModules bne 0xFC0BD09A"),
    "0xFC0BD096": AddressCitation("0xFC0BD096", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 265, "task_InitFileModules tail call b.w 0xFC35B93C(0x5006, 1)"),
    "0xFC0BD09A": AddressCitation("0xFC0BD09A", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 266, "task_InitFileModules pop {r4, r5, r6, pc} epilogue"),
    "0xFC0D9CCC": AddressCitation("0xFC0D9CCC", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 21, "sub_fc0d9ccc Callee 1 start in ROM slice S2B"),
    "0xFC0D9CF2": AddressCitation("0xFC0D9CF2", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 281, "sub_fc0d9ccc movs r0, #0 setting constant 0 return"),
    "0xFC0D9CF6": AddressCitation("0xFC0D9CF6", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 259, "sub_fc0d9cf6 Callee 2 start in ROM slice S2B"),
    "0xFC35B93C": AddressCitation("0xFC35B93C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 258, "Target routine called with event 0x5006"),
    "0xFC0BD049": AddressCitation("0xFC0BD049", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 21, "Historical refuted InitFileModules entry candidate (CONTRADICTED)"),
    "0xFC0BD048": AddressCitation("0xFC0BD048", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 245, "Literal pool address holding 0xFC66BBB0"),
    "0xFC66BBB0": AddressCitation("0xFC66BBB0", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 245, "Literal word at 0xFC0BD048 refuting 0xFC0BD049"),
    "0x010E17A5": AddressCitation("0x010E17A5", "docs/RESTART_SD_HOST_AUDIT.md", 56, "SD1stInit entry address created by StartDiskboot"),
    "0x010EE7D2": AddressCitation("0x010EE7D2", "docs/RESTART_SD_HOST_AUDIT.md", 26, "CMD0 issue in SD1stInit"),
    "0xFC41870C": AddressCitation("0xFC41870C", "docs/RESTART_SD_HOST_AUDIT.md", 16, "Intervening warm restart call site routine in ROM"),
    "0x4000": AddressCitation("0x4000", "docs/RESTART_SD_HOST_AUDIT.md", 16, "Intervening warm restart RAM vector [0x4000]"),
    "0x5006": AddressCitation("0x5006", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 254, "Event ID constant loaded into r5 at 0xFC0BD078"),
}


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Citation:
    """A documented citation supporting or contextualizing an obligation."""
    path: str
    line: Optional[int] = None
    end_line: Optional[int] = None
    target: Optional[str] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"path": self.path}
        if self.line is not None:
            res["line"] = self.line
        if self.end_line is not None:
            res["end_line"] = self.end_line
        if self.target is not None:
            res["target"] = self.target
        if self.note:
            res["note"] = self.note
        return res


@dataclass(frozen=True)
class RequiredEvidence:
    """Specification of artifact required to discharge an obligation."""
    artifact_type: str
    what_it_must_show: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "what_it_must_show": self.what_it_must_show,
        }


@dataclass(frozen=True)
class U2Obligation:
    """A formal proof obligation for U2 InitFileModules filesystem readiness."""
    id: str
    statement: str
    kind: ObligationKind
    status: ObligationStatus
    required_evidence: RequiredEvidence
    citations: Tuple[Citation, ...]
    notes: str = ""

    @property
    def is_static(self) -> bool:
        return self.kind == ObligationKind.STATIC or str(self.kind).lower() == "static"

    @property
    def is_runtime(self) -> bool:
        return self.kind == ObligationKind.RUNTIME or str(self.kind).lower() == "runtime"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "kind": self.kind.value,
            "status": self.status.value,
            "required_evidence": self.required_evidence.to_dict(),
            "citations": [c.to_dict() for c in self.citations],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EvidenceArtifact:
    """An evidence artifact submitted for evaluation."""
    artifact_id: str
    artifact_type: str
    status: ObligationStatus
    kind: ObligationKind = ObligationKind.STATIC
    description: str = ""
    citation: Optional[Citation] = None
    associated_addresses: Tuple[str, ...] = ()
    how_captured: str = ""

    @property
    def is_static(self) -> bool:
        return is_static_evidence(self)


STATIC_EVIDENCE_PATH_MARKERS: Tuple[str, ...] = (
    "PORT11A",
    "ROM_EVIDENCE",
)


def is_static_evidence(artifact: Any) -> bool:
    """True if artifact represents static ROM evidence (such as 0xFC0BD071, ROM slices, or ROM docs)."""
    if artifact is None:
        return False
    if isinstance(artifact, EvidenceArtifact):
        if artifact.kind == ObligationKind.STATIC or str(artifact.kind).lower() == "static":
            return True
        art_type = artifact.artifact_type.strip().upper()
        if art_type.startswith("STATIC_") or "ROM" in art_type:
            return True
        hc = artifact.how_captured.lower()
        if any(term in hc for term in ("static", "rom_disassembly", "offline_inspection", "rom_slice")):
            return True
        if any(addr in ("0xFC0BD071", "0xFC0BD070", "0xFC0BD0B4", "0xFC0BD1A8", "0xFC0D9CCC", "0xFC0D9CF2") for addr in artifact.associated_addresses):
            return True
        if artifact.citation is not None:
            cit_path = str(artifact.citation.path)
            if any(marker in cit_path for marker in STATIC_EVIDENCE_PATH_MARKERS):
                return True
        desc = artifact.description.lower()
        if any(term in desc for term in ("static rom", "slice s2a", "slice s2b", "rom slice")):
            return True
        return False
    # Generic object/duck typing
    if getattr(artifact, "is_static", False):
        return True
    kind = getattr(artifact, "kind", None)
    if kind is not None and (kind == ObligationKind.STATIC or str(kind).lower() == "static"):
        return True
    art_type = str(getattr(artifact, "artifact_type", "")).strip().upper()
    if art_type.startswith("STATIC_") or "ROM" in art_type:
        return True
    hc = str(getattr(artifact, "how_captured", "")).lower()
    if any(k in hc for k in ("static", "rom_disassembly", "offline_inspection", "rom_slice")):
        return True
    addrs = tuple(str(a) for a in getattr(artifact, "associated_addresses", ()))
    if any(a in ("0xFC0BD071", "0xFC0BD070", "0xFC0BD0B4", "0xFC0BD1A8", "0xFC0D9CCC", "0xFC0D9CF2") for a in addrs):
        return True
    cit = getattr(artifact, "citation", None)
    if cit is not None:
        cit_path = str(getattr(cit, "path", ""))
        if any(marker in cit_path for marker in STATIC_EVIDENCE_PATH_MARKERS):
            return True
    desc = str(getattr(artifact, "description", "")).lower()
    if any(term in desc for term in ("static rom", "slice s2a", "slice s2b", "rom slice")):
        return True
    return False


@dataclass(frozen=True)
class ObligationFinding:
    """An individual evaluation finding or policy violation."""
    rule_id: str
    obligation_id: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str


@dataclass(frozen=True)
class SingleObligationEvaluation:
    """Evaluation result for an individual obligation."""
    obligation_id: str
    kind: ObligationKind
    status: ObligationStatus
    is_satisfied: bool
    reason: str
    findings: Tuple[ObligationFinding, ...]


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregate evaluation report for U2 proof obligations."""
    is_ready: bool
    status: str
    total_obligations: int
    verified_count: int
    inferred_count: int
    unknown_count: int
    static_count: int
    runtime_count: int
    error_count: int
    warning_count: int
    findings: Tuple[ObligationFinding, ...]
    obligation_evaluations: Dict[str, SingleObligationEvaluation] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_ready

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            if other.strip().lower() in ("not-ready", "not_ready"):
                return not self.is_ready
            if other.strip().lower() in ("ready",):
                return self.is_ready
        return super().__eq__(other)

    @property
    def is_fail_closed(self) -> bool:
        """True if not ready and evaluated with fail-closed rules."""
        return not self.is_ready

    def is_obligation_satisfied(self, obligation_id: str) -> bool:
        """Check whether an individual obligation evaluated to satisfied."""
        ev = self.obligation_evaluations.get(obligation_id)
        return ev.is_satisfied if ev is not None else False

    def summary(self) -> str:
        lines = [
            "=" * 72,
            "PORT-13 / Task p13-oblig-u2-r2: U2 Filesystem Readiness Evaluation",
            "=" * 72,
            f"Overall Status   : {self.status.upper()} (is_ready={self.is_ready})",
            f"Total Obligations: {self.total_obligations}",
            f"  - VERIFIED     : {self.verified_count}",
            f"  - INFERRED     : {self.inferred_count}",
            f"  - UNKNOWN      : {self.unknown_count}",
            f"  - STATIC kind  : {self.static_count}",
            f"  - RUNTIME kind : {self.runtime_count}",
            f"Errors / Warnings: {self.error_count} / {self.warning_count}",
            f"Fail-Closed Active: {self.is_fail_closed}",
            "-" * 72,
        ]
        for ob_id, ev in self.obligation_evaluations.items():
            mark = "PASS" if ev.is_satisfied else "FAIL"
            lines.append(f"[{mark:4}] {ob_id} ({ev.kind.value.upper():7}, {ev.status.value:8}): {ev.reason}")
        if self.findings:
            lines.append("-" * 72)
            lines.append("Evaluation Findings:")
            for f in self.findings:
                lines.append(f"  [{f.severity:7}] {f.obligation_id} - {f.rule_id}: {f.message}")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "status": self.status,
            "total_obligations": self.total_obligations,
            "verified_count": self.verified_count,
            "inferred_count": self.inferred_count,
            "unknown_count": self.unknown_count,
            "static_count": self.static_count,
            "runtime_count": self.runtime_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "obligation_id": f.obligation_id,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "obligations": {
                ob_id: {
                    "kind": ev.kind.value,
                    "status": ev.status.value,
                    "is_satisfied": ev.is_satisfied,
                    "reason": ev.reason,
                }
                for ob_id, ev in self.obligation_evaluations.items()
            },
        }


# -----------------------------------------------------------------------------
# Canonical U2 Proof Obligations (Shipped Baseline Data)
# -----------------------------------------------------------------------------

DEFAULT_U2_OBLIGATIONS: Tuple[U2Obligation, ...] = (
    # (a) The static task entry
    U2Obligation(
        id="OBLIG-U2-01",
        statement=(
            "task_InitFileModules static task parameters and Thumb entry pointer "
            "0xFC0BD071 (instruction address 0xFC0BD070) are statically verified in "
            "GM1.10C ROM slice S2A"
        ),
        kind=ObligationKind.STATIC,
        status=ObligationStatus.VERIFIED,
        required_evidence=RequiredEvidence(
            artifact_type="STATIC_ROM_SLICE",
            what_it_must_show=(
                "Static creator sub_fc0bd0b4 passing task name 'InitFileModules', prio 0x19, "
                "stack 0x1000, and Thumb entry pointer 0xFC0BD071 to j_CreateTask (0xFC31BBC4), "
                "with entry instruction push {r4, r5, r6, lr} at 0xFC0BD070"
            ),
        ),
        citations=(
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21, note="Executive summary table U2: task identity and entry 0xFC0BD071 STATIC_VERIFIED"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=223, note="sub_fc0bd0b4 loads r3 = [0xFC0BD1A8] = 0xFC0BD071"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=235, note="Literal pool entry 0xFC0BD1A8 holding 0xFC0BD071"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=251, note="task_InitFileModules entry instruction at 0xFC0BD070"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=389, note="C-07: Entry 0xFC0BD071 STATIC_VERIFIED"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=402, note="InitFileModules creator sub_fc0bd0b4 details"),
        ),
        notes="Static entry evidence only; proves task entry vector but does NOT prove scheduler dispatch or filesystem readiness.",
    ),

    # (b) The runtime readiness signal - Stage 2: task started
    U2Obligation(
        id="OBLIG-U2-02",
        statement=(
            "Dynamic task creation and scheduler dispatch execution witness confirming "
            "task_InitFileModules ran in the current boot generation"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="EXECUTION_WITNESS",
            what_it_must_show=(
                "Dynamic execution trace confirming task_InitFileModules entry ran after "
                "DryOS scheduler dispatch in active boot generation context"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=296, note="FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS stage task_started"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=661, note="RuntimeLifecycle.init_file_modules_started() requires boot_generation match"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=24, note="Epistemic separation: observing entry vector 0xFC0BD071 does not prove scheduler dispatch"),
        ),
        notes="Static ROM entry 0xFC0BD071 cannot discharge this runtime obligation.",
    ),

    # (b) The runtime readiness signal - Stage 3: init returned normally
    U2Obligation(
        id="OBLIG-U2-03",
        statement=(
            "Current-generation normal completion witness confirming both sub_fc0d9ccc "
            "and sub_fc0d9cf6 return normally in current boot generation (note: sub_fc0d9ccc "
            "r0==0 is constant on normal return and does NOT prove mount)"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="COMPLETION_WITNESS",
            what_it_must_show=(
                "Dynamic completion witness verifying both sub_fc0d9ccc and sub_fc0d9cf6 returned "
                "in current boot generation without latched fault (noting that sub_fc0d9ccc r0==0 "
                "is constant on normal return and does NOT prove mount)"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=298, note="FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS stage init_returned_normally"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=670, note="RuntimeLifecycle.init_file_modules_returned() requires current boot generation, no faults"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=21, note="sub_fc0d9ccc contains zero conditional branches, returns r0=0 constant on normal return"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=281, note="movs r0, #0 at 0xFC0D9CF2 on normal return"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=25, note="Epilogue r0=0 is unconditional constant on normal return; does not prove mount"),
        ),
        notes="Requires dynamic completion witness for sub_fc0d9ccc and sub_fc0d9cf6 in active boot generation; r0==0 is constant on normal return and does not prove mount.",
    ),

    # (b) The runtime readiness signal - Stage 4: mount observed & event 0x5006 decoupling
    U2Obligation(
        id="OBLIG-U2-04",
        statement=(
            "Event 0x5006 decoupling from filesystem I/O gate: Event(0x5006) does not imply "
            "FilesystemReady(SD0); independent kernel/storage state proof required"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="STORAGE_MOUNT_PROOF",
            what_it_must_show=(
                "Independent kernel storage state proof that FAT volume mount succeeded "
                "without relying on event 0x5006"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=300, note="FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS stage mount_observed: event 0x5006 alone is insufficient"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=678, note="Posting event 0x5006 does not advance to mount_observed or fs_io_ready"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=708, note="RuntimeLifecycle.record_mount_observation() requires independent mount observation"),
            Citation(path="docs/PORT11A_GM110C_ROM_EVIDENCE.md", line=258, note="0xFC35B93C target outside S2A / UNKNOWN"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=26, note="Event 0x5006 alone is insufficient for filesystem readiness"),
        ),
        notes="Dispatch mechanism for event 0x5006 remains UNKNOWN; posting event does not prove filesystem mount completion.",
    ),

    # (c) The ordering of that signal relative to the first CHDK file access - Stage 5: fs_io_ready
    U2Obligation(
        id="OBLIG-U2-05",
        statement=(
            "Strict causal ordering of filesystem readiness signal prior to first CHDK file access "
            "with verified non-destructive open/read capability on mounted volume without contention or timeout"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="CAUSAL_ORDERING_TRACE",
            what_it_must_show=(
                "Verified non-destructive file open/read capability on mounted volume without contention "
                "or timeout, causally preceding any CHDK file access"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=302, note="FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS stage fs_io_ready: non-destructive file open/read capability"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=739, note="RuntimeLifecycle.record_filesystem_io_readiness()"),
            Citation(path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", line=190, note="Historical defect: core_spytask_can_start called without checking mount/return status"),
            Citation(path="docs/PORT5A_RANMA_PORT_RECOVERY.md", line=93, note="Historical port recovery notes on core_spytask_can_start"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=46, note="Missing obligation for verified non-destructive file open/read capability"),
        ),
        notes="Mandates verified non-destructive open/read capability before any Fopen_Fut/Fread_Fut/Fwrite_Fut access.",
    ),

    # (d) The failure/timeout behaviour - Fault latching & out-of-order handling
    U2Obligation(
        id="OBLIG-U2-06",
        statement=(
            "Fail-closed fault, error, timeout, and out-of-order execution handling: any violation "
            "immediately transitions filesystem state to FAILED and blocks the gate"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="FAULT_HANDLING_WITNESS",
            what_it_must_show=(
                "Verification that errors, timeouts, out-of-order calls, or latched CPU faults halt "
                "progression and permanently fail the filesystem gate"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=262, note="FilesystemReadinessState.stage returns FAILED if self.failed"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=686, note="init_file_modules_returned before task_started fails filesystem"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=692, note="Fault latched during init_file_modules_returned fails filesystem"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=27, note="Fail-closed invariant: latched CPU faults halt progression"),
        ),
        notes="Guarantees fail-closed safety under any exception, timeout, or sequencing anomaly.",
    ),

    # (d) The failure/timeout behaviour - Generation invalidation
    U2Obligation(
        id="OBLIG-U2-07",
        statement=(
            "Monotonic boot_generation binding: filesystem readiness latch <Ready, GenerationID> "
            "invalidated across soft reboot or warm restart"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="GENERATION_BINDING_PROOF",
            what_it_must_show=(
                "Monotonic generation token check rejecting stale tokens from prior generations "
                "across warm restart and resetting filesystem stages"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=250, note="boot_generation field in FilesystemReadinessState"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=343, note="RuntimeLifecycle.reset() increments boot_generation and resets fs state"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=394, note="RuntimeLifecycle._check_generation() validates active boot_generation"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=113, note="Latch state must be monotonically bound to boot_generation token"),
        ),
        notes="Prevents stale latch reuse after unexpected soft reboot or warm restart.",
    ),

    # (d) The failure/timeout behaviour - Warm restart storage safety
    U2Obligation(
        id="OBLIG-U2-08",
        statement=(
            "Resolution of warm-restart SD host/card preconditions (P11, P12, P13, P15) with host "
            "retention qualified as plausible and reset ownership decoupled"
        ),
        kind=ObligationKind.RUNTIME,
        status=ObligationStatus.UNKNOWN,
        required_evidence=RequiredEvidence(
            artifact_type="WARM_RESTART_AUDIT_WITNESS",
            what_it_must_show=(
                "Precondition resolution for SD host and card state across warm restart confirming "
                "re-enumeration safety without bus lockup"
            ),
        ),
        citations=(
            Citation(path="tools/port9a_runtime_lifecycle.py", line=304, note="FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS stage warm_restart_safe"),
            Citation(path="tools/port9a_runtime_lifecycle.py", line=767, note="RuntimeLifecycle.record_warm_restart_storage_safety()"),
            Citation(path="tools/port9b_runtime_contract.py", line=79, note="Fact U2 encompasses warm-restart storage safety"),
            Citation(path="docs/RESTART_SD_HOST_AUDIT.md", line=16, note="Host state retention is plausible (P); intervening routines 0xFC41870C and [0x4000] UNKNOWN"),
            Citation(path="docs/RESTART_SD_HOST_AUDIT.md", line=56, note="SD1stInit task entry 0x010E17A5; reset ownership decoupled from InitFileModules"),
            Citation(path="docs/PORT13_REVIEW_U2.md", line=52, note="Decouple lifecycle requirement from unverified reset ownership assignment"),
        ),
        notes="SD controller retention is plausible/inferred; reset ownership is not assigned to InitFileModules.",
    ),
)

CANONICAL_U2_OBLIGATION_IDS: Tuple[str, ...] = tuple(ob.id for ob in DEFAULT_U2_OBLIGATIONS)
CANONICAL_OBLIGATIONS_MAP: Dict[str, U2Obligation] = {ob.id: ob for ob in DEFAULT_U2_OBLIGATIONS}

PORT9A_SIX_STAGE_CORRESPONDENCE: Dict[str, Dict[str, Any]] = {
    "task_created": {
        "port9a_line": 294,
        "obligation_ids": ("OBLIG-U2-01", "OBLIG-U2-02"),
        "description": "Static creator call-chain proof + runtime observation that CreateTask was invoked for InitFileModules in current boot generation",
    },
    "task_started": {
        "port9a_line": 296,
        "obligation_ids": ("OBLIG-U2-02",),
        "description": "Execution witness confirming task_InitFileModules entry ran in current boot generation after scheduler dispatch",
    },
    "init_returned_normally": {
        "port9a_line": 298,
        "obligation_ids": ("OBLIG-U2-03",),
        "description": "Completion witness after sub_fc0d9ccc and sub_fc0d9cf6 return in current boot generation (note: sub_fc0d9ccc r0==0 is constant on normal return and does NOT prove mount)",
    },
    "mount_observed": {
        "port9a_line": 300,
        "obligation_ids": ("OBLIG-U2-04",),
        "description": "Independent kernel/storage state proof that FAT volume mount succeeded (event 0x5006 alone is insufficient)",
    },
    "fs_io_ready": {
        "port9a_line": 302,
        "obligation_ids": ("OBLIG-U2-05",),
        "description": "Verified non-destructive file open/read capability on mounted volume without contention or timeout",
    },
    "warm_restart_safe": {
        "port9a_line": 304,
        "obligation_ids": ("OBLIG-U2-08",),
        "description": "Resolution of warm-restart SD host/card state preconditions (P11 SD1stInit predicate, P12 controller reset, P13 card state, P15 IRQ state) for current boot generation",
    },
}


# -----------------------------------------------------------------------------
# Address & Contract Provenance Verification Helpers
# -----------------------------------------------------------------------------

HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{1,8}\b")


def verify_address_provenance(
    repo_root: Optional[Union[str, Path]] = None,
) -> Tuple[bool, List[str]]:
    """Verify that every address cited in TRACKED_ADDRESS_CITATIONS exists in the cited doc

    and that every address used in obligations statements/notes is registered.
    """
    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT_DEFAULT.resolve()
    errors: List[str] = []

    # 1. Verify every address cited in TRACKED_ADDRESS_CITATIONS exists at the cited file:line
    for addr_str, citation in TRACKED_ADDRESS_CITATIONS.items():
        doc_path = root / citation.document_ref
        if not doc_path.is_file():
            errors.append(f"Address {addr_str} cited document '{citation.document_ref}' missing on disk")
            continue
        if citation.document_ref not in ORIGIN_MAIN_TRACKED_FILES:
            errors.append(f"Address {addr_str} cited document '{citation.document_ref}' is not on origin/main")
            continue
        try:
            lines = doc_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if citation.line < 1 or citation.line > len(lines):
                errors.append(f"Address {addr_str} cited line {citation.line} out of range in {citation.document_ref}")
                continue
            line_text = lines[citation.line - 1]
            if addr_str.lower() not in line_text.lower():
                errors.append(
                    f"Address {addr_str} not present at cited line {citation.document_ref}:{citation.line} "
                    f"('{line_text[:60]}...')"
                )
        except Exception as exc:
            errors.append(f"Failed reading {citation.document_ref}: {exc}")

    # 2. Verify all hex addresses appearing in DEFAULT_U2_OBLIGATIONS statements/notes are registered
    for ob in DEFAULT_U2_OBLIGATIONS:
        combined_text = f"{ob.statement} {ob.notes} " + " ".join(c.note for c in ob.citations)
        found_addrs = HEX_ADDR_RE.findall(combined_text)
        for raw_addr in found_addrs:
            norm_addr = f"0x{int(raw_addr, 16):08X}"
            if norm_addr not in TRACKED_ADDRESS_CITATIONS and raw_addr not in TRACKED_ADDRESS_CITATIONS:
                errors.append(f"Obligation {ob.id} contains unregistered firmware address: {raw_addr}")

    return (len(errors) == 0, errors)


def verify_i2_contract_consistency() -> Tuple[bool, List[str]]:
    """Verify that U2 obligations data model agrees with PORT-9A and PORT-9B contracts."""
    errors: List[str] = []

    # 1. PORT-9A Precondition check: init_file_modules_entry_verified MUST be False
    if rt.GM110C_PRECONDITIONS.init_file_modules_entry_verified is not False:
        errors.append("PORT-9A GM110C_PRECONDITIONS.init_file_modules_entry_verified is not False")

    # 2. PORT-9A Static evidence profile separation
    if rt.GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry is not rt.EvidenceStatus.STATIC_VERIFIED:
        errors.append("PORT-9A GM110C_STATIC_EVIDENCE.u2_init_file_modules_entry is not STATIC_VERIFIED")
    if rt.GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness is not rt.EvidenceStatus.UNKNOWN:
        errors.append("PORT-9A GM110C_STATIC_EVIDENCE.u2_sd_fat_mount_readiness is not UNKNOWN")

    # 3. PORT-9B Fact U2 check
    u2_facts = [fact for fact in p9b.UNVERIFIED_RUNTIME_FACTS if fact[0] == "U2"]
    if not u2_facts:
        errors.append("PORT-9B UNVERIFIED_RUNTIME_FACTS lacks Fact U2")
    else:
        fid, flag, desc = u2_facts[0]
        if flag != "init_file_modules_entry_verified":
            errors.append(f"PORT-9B Fact U2 flag is '{flag}', expected 'init_file_modules_entry_verified'")

    # 4. PORT-9A 6-stage filesystem promotion completeness
    stages = tuple(stage for stage, _ in rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS)
    expected_stages = (
        "task_created",
        "task_started",
        "init_returned_normally",
        "mount_observed",
        "fs_io_ready",
        "warm_restart_safe",
    )
    if stages != expected_stages:
        errors.append(f"PORT-9A filesystem promotion stages mismatch: got {stages}, expected {expected_stages}")

    return (len(errors) == 0, errors)


# -----------------------------------------------------------------------------
# Fail-Closed Evaluator
# -----------------------------------------------------------------------------

def evaluate_obligation(
    obligation: U2Obligation,
    evidence: Optional[Union[EvidenceArtifact, Dict[str, EvidenceArtifact]]] = None,
    repo_root: Optional[Union[str, Path]] = None,
    check_disk: bool = True,
    pinned_hashes: Optional[Dict[str, str]] = None,
    file_reader: Optional[Callable[[Path], bytes]] = None,
) -> SingleObligationEvaluation:
    """Evaluate a single U2 obligation in isolation.

    Validates:
      - Supporting citations on the obligation (presence, tracking, no forbidden paths).
      - If evidence is provided:
        - Evidence citation (presence, tracking, no forbidden paths).
        - Evidence artifact_type matches obligation.required_evidence.artifact_type.
        - Evidence status is VERIFIED.
        - Static evidence cannot discharge runtime obligations (even with empty associated_addresses
          or when citing static documentation like PORT11A).
      - If no evidence is provided:
        - Shipped baseline status must be VERIFIED (only OBLIG-U2-01).

    Note:
      Satisfying an obligation in isolation (even OBLIG-U2-01) does NOT confer
      aggregate filesystem readiness. Aggregate readiness requires the full
      canonical set evaluated via evaluate().
    """
    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT_DEFAULT.resolve()
    active_pins = PINNED_FILE_HASHES if pinned_hashes is None else pinned_hashes
    ob_findings: List[ObligationFinding] = []

    # 0. Canonical definition equality check
    canonical_def = CANONICAL_OBLIGATIONS_MAP.get(obligation.id)
    if canonical_def is None:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_NONCANONICAL_OBLIGATION,
                obligation_id=obligation.id,
                severity="ERROR",
                message=f"Obligation '{obligation.id}' is not a recognized canonical obligation ID",
            )
        )
    elif obligation != canonical_def:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_NONCANONICAL_OBLIGATION,
                obligation_id=obligation.id,
                severity="ERROR",
                message=(
                    f"Obligation '{obligation.id}' does not match frozen canonical definition by full value equality "
                    f"(definitional fields have been modified)"
                ),
            )
        )

    # 1. Validate obligation supporting citations
    if not obligation.citations:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_MISSING_CITATIONS,
                obligation_id=obligation.id,
                severity="ERROR",
                message=f"Obligation {obligation.id} has no supporting citations",
            )
        )
    else:
        for cit in obligation.citations:
            if not cit.path or not cit.path.strip():
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_MISSING_CITATIONS,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=f"Obligation {obligation.id} carries an empty citation path",
                    )
                )
                continue

            clean_path = cit.path.strip().replace("\\", "/")

            # Check forbidden local-only or untracked paths
            if any(clean_path.startswith(prefix) or prefix in clean_path for prefix in FORBIDDEN_PATH_PREFIXES):
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_FORBIDDEN_LOCAL_PATH,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=f"Citation '{clean_path}' references forbidden local-only or untracked path",
                    )
                )
                continue

            # Check tracking on origin/main
            if clean_path not in ORIGIN_MAIN_TRACKED_FILES:
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_UNTRACKED_PATH,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=f"Citation '{clean_path}' is not a tracked file on origin/main",
                    )
                )
                continue

            # Disk existence and content authentication
            if check_disk:
                full_path = root / clean_path
                if not full_path.is_file():
                    ob_findings.append(
                        ObligationFinding(
                            rule_id=RULE_MISSING_CITED_PATH,
                            obligation_id=obligation.id,
                            severity="ERROR",
                            message=f"Cited file '{clean_path}' does not exist on disk",
                        )
                    )
                    continue

                if clean_path in active_pins:
                    try:
                        content_bytes = (
                            file_reader(full_path) if file_reader is not None else full_path.read_bytes()
                        )
                        digest = hashlib.sha256(content_bytes).hexdigest()
                        if digest.lower() != active_pins[clean_path].lower():
                            ob_findings.append(
                                ObligationFinding(
                                    rule_id=RULE_CONTENT_HASH_MISMATCH,
                                    obligation_id=obligation.id,
                                    severity="ERROR",
                                    message=(
                                        f"Cited file '{clean_path}' content hash mismatch "
                                        f"(expected {active_pins[clean_path]}, got {digest})"
                                    ),
                                )
                            )
                    except Exception as exc:
                        ob_findings.append(
                            ObligationFinding(
                                rule_id=RULE_UNREADABLE_SOURCE,
                                obligation_id=obligation.id,
                                severity="ERROR",
                                message=f"Cannot read cited file '{clean_path}': {exc}",
                            )
                        )

    # 2. Extract submitted evidence artifact for this obligation
    ev_artifact: Optional[EvidenceArtifact] = None
    if evidence is not None:
        if isinstance(evidence, EvidenceArtifact):
            ev_artifact = evidence
        elif isinstance(evidence, dict):
            ev_artifact = evidence.get(obligation.id)

    is_satisfied = False
    reason = ""

    if ev_artifact is not None:
        # A. Validate evidence citation
        if ev_artifact.citation is None or not ev_artifact.citation.path or not ev_artifact.citation.path.strip():
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_MISSING_CITATIONS,
                    obligation_id=obligation.id,
                    severity="ERROR",
                    message=f"Evidence artifact '{ev_artifact.artifact_id}' has missing or empty citation",
                )
            )
        else:
            ev_path = ev_artifact.citation.path.strip().replace("\\", "/")
            if any(ev_path.startswith(prefix) or prefix in ev_path for prefix in FORBIDDEN_PATH_PREFIXES):
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_FORBIDDEN_LOCAL_PATH,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=f"Evidence artifact citation '{ev_path}' references forbidden local-only path",
                    )
                )
            elif ev_path not in ORIGIN_MAIN_TRACKED_FILES:
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_UNTRACKED_PATH,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=f"Evidence artifact citation '{ev_path}' is not a tracked file on origin/main",
                    )
                )
            elif check_disk:
                full_ev_path = root / ev_path
                if not full_ev_path.is_file():
                    ob_findings.append(
                        ObligationFinding(
                            rule_id=RULE_MISSING_CITED_PATH,
                            obligation_id=obligation.id,
                            severity="ERROR",
                            message=f"Evidence artifact cited file '{ev_path}' does not exist on disk",
                        )
                    )
                elif ev_path in active_pins:
                    try:
                        content_bytes = (
                            file_reader(full_ev_path) if file_reader is not None else full_ev_path.read_bytes()
                        )
                        digest = hashlib.sha256(content_bytes).hexdigest()
                        if digest.lower() != active_pins[ev_path].lower():
                            ob_findings.append(
                                ObligationFinding(
                                    rule_id=RULE_CONTENT_HASH_MISMATCH,
                                    obligation_id=obligation.id,
                                    severity="ERROR",
                                    message=(
                                        f"Evidence cited file '{ev_path}' content hash mismatch "
                                        f"(expected {active_pins[ev_path]}, got {digest})"
                                    ),
                                )
                            )
                    except Exception as exc:
                        ob_findings.append(
                            ObligationFinding(
                                rule_id=RULE_UNREADABLE_SOURCE,
                                obligation_id=obligation.id,
                                severity="ERROR",
                                message=f"Cannot read evidence cited file '{ev_path}': {exc}",
                            )
                        )

        # B. Check artifact_type match
        req_type = obligation.required_evidence.artifact_type.strip().upper()
        act_type = ev_artifact.artifact_type.strip().upper()
        if req_type != act_type:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_ARTIFACT_TYPE_MISMATCH,
                    obligation_id=obligation.id,
                    severity="ERROR",
                    message=(
                        f"Evidence artifact '{ev_artifact.artifact_id}' artifact_type '{ev_artifact.artifact_type}' "
                        f"does not match required artifact_type '{obligation.required_evidence.artifact_type}' for {obligation.id}"
                    ),
                )
            )

        # C. Check status is VERIFIED
        if ev_artifact.status != ObligationStatus.VERIFIED:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_EVIDENCE_STATUS_NOT_VERIFIED,
                    obligation_id=obligation.id,
                    severity="ERROR",
                    message=f"Provided evidence status is {ev_artifact.status.value}, expected VERIFIED",
                )
            )

        # D. Static evidence CANNOT discharge runtime obligations
        if obligation.is_runtime and is_static_evidence(ev_artifact):
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_STATIC_CANNOT_DISCHARGE_RUNTIME,
                    obligation_id=obligation.id,
                    severity="ERROR",
                    message=(
                        f"Static evidence ({ev_artifact.artifact_id}) cannot discharge "
                        f"runtime obligation '{obligation.id}'; runtime readiness requires dynamic storage witness."
                    ),
                )
            )

        # E. Runtime provenance allowlist check
        # Existing tracked docs, source files, reviews, or tools on origin/main
        # can never discharge a runtime obligation. Only artifacts registered
        # in the TRUSTED_RUNTIME_WITNESSES positive allowlist can discharge runtime obligations.
        if obligation.is_runtime:
            ev_cit_path = ev_artifact.citation.path.strip().replace("\\", "/") if ev_artifact.citation else ""
            if (
                ev_artifact.artifact_id not in TRUSTED_RUNTIME_WITNESSES
                and ev_cit_path not in TRUSTED_RUNTIME_WITNESSES
            ):
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_UNTRUSTED_RUNTIME_PROVENANCE,
                        obligation_id=obligation.id,
                        severity="ERROR",
                        message=(
                            f"Runtime obligation '{obligation.id}' cannot be discharged by "
                            f"untrusted artifact '{ev_artifact.artifact_id}' citing '{ev_cit_path}'. "
                            f"Artifact/citation is not in TRUSTED_RUNTIME_WITNESSES allowlist. "
                            f"Tracked documentation and static files can never discharge runtime obligations."
                        ),
                    )
                )

        has_errors = any(f.severity == "ERROR" for f in ob_findings)
        if not has_errors:
            is_satisfied = True
            reason = f"Satisfied by verified evidence '{ev_artifact.artifact_id}'"
        else:
            is_satisfied = False
            reason = "Evidence validation errors prevent satisfaction"

    else:
        # No evidence artifact provided: evaluate baseline status
        # Only the canonical static-entry obligation (OBLIG-U2-01) may be satisfied without evidence,
        # and only if it matches its entry in CANONICAL_OBLIGATIONS_MAP by full value equality.
        canonical_static_entry = CANONICAL_OBLIGATIONS_MAP.get("OBLIG-U2-01")
        if (
            obligation.id == "OBLIG-U2-01"
            and canonical_static_entry is not None
            and obligation == canonical_static_entry
            and obligation.status == ObligationStatus.VERIFIED
        ):
            has_errors = any(f.severity == "ERROR" for f in ob_findings)
            if not has_errors:
                is_satisfied = True
                reason = "Canonical static task entry obligation is VERIFIED in repository baseline documentation"
            else:
                is_satisfied = False
                reason = "Obligation citations have errors"
        else:
            # Any other obligation cannot be satisfied without verified evidence.
            is_satisfied = False
            if obligation.is_runtime:
                # Any obligation with kind=RUNTIME, canonical or not, must always go through
                # the runtime-provenance check. With the shipped empty TRUSTED_RUNTIME_WITNESSES
                # it must fail closed (is_satisfied=False, with a finding).
                if obligation.status == ObligationStatus.VERIFIED:
                    ob_findings.append(
                        ObligationFinding(
                            rule_id=RULE_UNTRUSTED_RUNTIME_PROVENANCE,
                            obligation_id=obligation.id,
                            severity="ERROR",
                            message=(
                                f"Runtime obligation '{obligation.id}' cannot be marked VERIFIED without trusted runtime evidence. "
                                f"TRUSTED_RUNTIME_WITNESSES allowlist is empty in shipped code; "
                                f"tracked documentation and static ROM evidence can never satisfy runtime obligations."
                            ),
                        )
                    )
                    # If it cites static evidence or addresses, also enforce that static evidence cannot discharge runtime
                    has_static_cit = any(
                        any(m in str(c.path) for m in STATIC_EVIDENCE_PATH_MARKERS)
                        for c in obligation.citations
                        if c and c.path
                    )
                    has_static_addr = any(
                        addr in ("0xFC0BD071", "0xFC0BD070")
                        for addr in HEX_ADDR_RE.findall(f"{obligation.statement} {obligation.notes}")
                    )
                    if has_static_cit or has_static_addr:
                        ob_findings.append(
                            ObligationFinding(
                                rule_id=RULE_STATIC_CANNOT_DISCHARGE_RUNTIME,
                                obligation_id=obligation.id,
                                severity="ERROR",
                                message=(
                                    f"Static ROM evidence (citing 0xFC0BD071 / docs/PORT11A_GM110C_ROM_EVIDENCE.md) "
                                    f"cannot discharge runtime obligation '{obligation.id}'."
                                ),
                            )
                        )
                    reason = f"Runtime obligation '{obligation.id}' cannot be satisfied without trusted runtime evidence"
                else:
                    ob_findings.append(
                        ObligationFinding(
                            rule_id=RULE_STATUS_UNVERIFIED,
                            obligation_id=obligation.id,
                            severity="WARNING",
                            message=f"Obligation {obligation.id} status is {obligation.status.value}; requires verified evidence",
                        )
                    )
                    reason = f"Obligation status is {obligation.status.value}; fail-closed without verified evidence"
            else:
                # Static obligation that is not the canonical static-entry obligation
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_STATUS_UNVERIFIED,
                        obligation_id=obligation.id,
                        severity="ERROR" if obligation.status == ObligationStatus.VERIFIED else "WARNING",
                        message=(
                            f"Non-canonical or modified static obligation '{obligation.id}' cannot be satisfied without verified evidence"
                            if obligation.status == ObligationStatus.VERIFIED
                            else f"Obligation {obligation.id} status is {obligation.status.value}; requires verified evidence"
                        ),
                    )
                )
                reason = f"Obligation status is {obligation.status.value}; requires verified evidence"

    return SingleObligationEvaluation(
        obligation_id=obligation.id,
        kind=obligation.kind,
        status=obligation.status,
        is_satisfied=is_satisfied,
        reason=reason,
        findings=tuple(ob_findings),
    )


def evaluate(
    obligations: Optional[Sequence[U2Obligation]] = None,
    evidence: Optional[Dict[str, EvidenceArtifact]] = None,
    repo_root: Optional[Union[str, Path]] = None,
    check_disk: bool = True,
    pinned_hashes: Optional[Dict[str, str]] = None,
    file_reader: Optional[Callable[[Path], bytes]] = None,
) -> EvaluationResult:
    """Evaluate U2 filesystem readiness proof obligations fail-closed.

    Fail-closed guarantees:
      - Aggregate readiness requires the COMPLETE canonical obligation set
        (all 8 obligations OBLIG-U2-01..08). Any missing, extra, or substituted
        obligation causes aggregate evaluation to fail closed (is_ready=False).
      - Shipped data has 7 UNKNOWN runtime obligations and 1 VERIFIED static entry obligation;
        is_ready is False and status is 'not-ready'.
      - Static ROM evidence (0xFC0BD071 / ROM slices / PORT11A citations) CANNOT discharge
        any runtime obligation, even if associated_addresses is empty.
      - Missing citations, citations to untracked files, citations to forbidden local-only paths
        (e.g., firmware/ dumps or PORT-9A L1/L2), or artifact_type mismatches cause failure.
      - Agreement with PORT-9A model (preconditions False) and PORT-9B I2 contract is strictly enforced.
    """
    target_obligations = tuple(DEFAULT_U2_OBLIGATIONS if obligations is None else obligations)
    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT_DEFAULT.resolve()
    active_pins = PINNED_FILE_HASHES if pinned_hashes is None else pinned_hashes

    findings: List[ObligationFinding] = []
    obligation_evals: Dict[str, SingleObligationEvaluation] = {}

    if not target_obligations:
        findings.append(
            ObligationFinding(
                rule_id=RULE_EMPTY_DATASET,
                obligation_id="GLOBAL",
                severity="ERROR",
                message="No proof obligations provided for evaluation",
            )
        )
        return EvaluationResult(
            is_ready=False,
            status=EvaluationVerdict.NOT_READY.value,
            total_obligations=0,
            verified_count=0,
            inferred_count=0,
            unknown_count=0,
            static_count=0,
            runtime_count=0,
            error_count=1,
            warning_count=0,
            findings=tuple(findings),
        )

    # 1. Enforce consistency with PORT-9A and PORT-9B contracts
    contract_ok, contract_errors = verify_i2_contract_consistency()
    if not contract_ok:
        for err in contract_errors:
            findings.append(
                ObligationFinding(
                    rule_id=RULE_CONTRACT_INVARIANT_VIOLATED,
                    obligation_id="GLOBAL",
                    severity="ERROR",
                    message=f"I2 contract consistency violation: {err}",
                )
            )

    # 2. Check canonical set requirement for aggregate readiness
    # Aggregate readiness strictly requires full value equality with DEFAULT_U2_OBLIGATIONS.
    supplied_ids = tuple(ob.id for ob in target_obligations)
    is_canonical_set = (target_obligations == DEFAULT_U2_OBLIGATIONS)
    if not is_canonical_set:
        if supplied_ids != CANONICAL_U2_OBLIGATION_IDS:
            findings.append(
                ObligationFinding(
                    rule_id=RULE_INCOMPLETE_OBLIGATION_SET,
                    obligation_id="AGGREGATE",
                    severity="ERROR",
                    message=(
                        f"Aggregate filesystem readiness requires the complete canonical obligation set "
                        f"({len(CANONICAL_U2_OBLIGATION_IDS)} obligations: {list(CANONICAL_U2_OBLIGATION_IDS)}). "
                        f"Supplied set has {len(supplied_ids)} obligations: {list(supplied_ids)}."
                    ),
                )
            )
        else:
            findings.append(
                ObligationFinding(
                    rule_id=RULE_NONCANONICAL_OBLIGATION,
                    obligation_id="AGGREGATE",
                    severity="ERROR",
                    message=(
                        "Supplied obligation set does not match frozen canonical definitions by full value equality "
                        "(obligations have been substituted or modified)."
                    ),
                )
            )

    # 3. Evaluate each obligation
    for ob in target_obligations:
        single_eval = evaluate_obligation(
            obligation=ob,
            evidence=evidence,
            repo_root=root,
            check_disk=check_disk,
            pinned_hashes=active_pins,
            file_reader=file_reader,
        )
        obligation_evals[ob.id] = single_eval
        findings.extend(single_eval.findings)

    # 4. Aggregate counts
    total_obligations = len(target_obligations)
    verified_count = sum(1 for ev in obligation_evals.values() if ev.is_satisfied)
    inferred_count = sum(1 for ob in target_obligations if ob.status == ObligationStatus.INFERRED)
    unknown_count = sum(1 for ob in target_obligations if ob.status == ObligationStatus.UNKNOWN)
    static_count = sum(1 for ob in target_obligations if ob.is_static)
    runtime_count = sum(1 for ob in target_obligations if ob.is_runtime)
    error_count = sum(1 for f in findings if f.severity == "ERROR")
    warning_count = sum(1 for f in findings if f.severity == "WARNING")

    # Aggregate readiness: requires complete canonical set, zero errors, and all canonical obligations satisfied
    is_ready = (
        is_canonical_set
        and error_count == 0
        and verified_count == len(CANONICAL_U2_OBLIGATION_IDS)
        and total_obligations == len(CANONICAL_U2_OBLIGATION_IDS)
    )
    status = EvaluationVerdict.READY.value if is_ready else EvaluationVerdict.NOT_READY.value

    return EvaluationResult(
        is_ready=is_ready,
        status=status,
        total_obligations=total_obligations,
        verified_count=verified_count,
        inferred_count=inferred_count,
        unknown_count=unknown_count,
        static_count=static_count,
        runtime_count=runtime_count,
        error_count=error_count,
        warning_count=warning_count,
        findings=tuple(findings),
        obligation_evaluations=obligation_evals,
    )


def get_obligation(obligation_id: str) -> Optional[U2Obligation]:
    """Retrieve a canonical U2 obligation by ID."""
    for ob in DEFAULT_U2_OBLIGATIONS:
        if ob.id == obligation_id:
            return ob
    return None


def main() -> int:
    """CLI entrypoint."""
    res = evaluate()
    print(res.summary())
    return 0 if res.is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
