#!/usr/bin/env python3
"""PORT-13: Fail-closed proof obligations for GM1.10C memory ownership.

This module formalizes GM1.10C memory-ownership proof obligations as structured data.
It enforces fail-closed evaluation: overall readiness is False unless every obligation
is VERIFIED with primary GM1.10C evidence tracked on origin/main.

Safety & Scope Invariants:
  - Standard library only; strictly NO subprocess calls, NO binary modifications,
    NO ROM dump scans, and NO hardware access.
  - Phase 0 read-only verification: memory bounds do NOT imply subsystem ownership.
  - Fail-closed: missing sources, untracked files, historical-firmware-only (1.00C/1.10E)
    sources, or unmerged PR evidence force overall readiness to False.
  - Zero new firmware addresses: every address appearing in this module is already
    present in a tracked origin/main document, cited file:line.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sys
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# -----------------------------------------------------------------------------
# Interoperability with tools/port11c_evidence_validator.py
# -----------------------------------------------------------------------------
try:
    from tools.port11c_evidence_validator import (  # type: ignore
        Classification,
        ProvenanceType,
        parse_address_int,
    )
except ImportError:
    try:
        from port11c_evidence_validator import (  # type: ignore
            Classification,
            ProvenanceType,
            parse_address_int,
        )
    except ImportError:
        # Fallback definitions preserving exact semantics if port11c is unimported
        class Classification(str, Enum):  # type: ignore
            STATIC_VERIFIED = "STATIC_VERIFIED"
            INFERRED = "INFERRED"
            UNKNOWN = "UNKNOWN"

        class ProvenanceType(str, Enum):  # type: ignore
            ROM_VERIFIED = "ROM_VERIFIED"
            SOURCE_REPO = "SOURCE_REPO"
            HISTORICAL_CHDK = "HISTORICAL_CHDK"
            HARDWARE_WITNESS = "HARDWARE_WITNESS"
            SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"

        def parse_address_int(val: Union[int, str], field_name: str = "address") -> int:  # type: ignore
            if isinstance(val, int):
                return val
            return int(str(val).strip(), 16)


# -----------------------------------------------------------------------------
# Enums and Evaluation Rule Identifiers
# -----------------------------------------------------------------------------

class ObligationStatus(str, Enum):
    """Certainty status of a memory ownership obligation."""
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
        raise ValueError(
            f"Invalid ObligationStatus '{val}'. Allowed: {[m.value for m in cls]}"
        )


RULE_MISSING_CITED_PATH = "RULE_MISSING_CITED_PATH"
RULE_UNREADABLE_SOURCE = "RULE_UNREADABLE_SOURCE"
RULE_UNTRACKED_SOURCE = "RULE_UNTRACKED_SOURCE"
RULE_UNPINNED_SOURCE = "RULE_UNPINNED_SOURCE"
RULE_CONTENT_HASH_MISMATCH = "RULE_CONTENT_HASH_MISMATCH"
RULE_UNACCEPTABLE_SOURCE = "RULE_UNACCEPTABLE_SOURCE"
RULE_HISTORICAL_CANNOT_VERIFY = "RULE_HISTORICAL_CANNOT_VERIFY"
RULE_PENDING_PR_CANNOT_VERIFY = "RULE_PENDING_PR_CANNOT_VERIFY"
RULE_STATUS_NOT_VERIFIED = "RULE_STATUS_NOT_VERIFIED"
RULE_EMPTY_CITATIONS = "RULE_EMPTY_CITATIONS"
RULE_ADDRESS_NOT_TRACKED = "RULE_ADDRESS_NOT_TRACKED"
RULE_EMPTY_DATASET = "RULE_EMPTY_DATASET"
RULE_INCOMPLETE_OBLIGATION_SET = "RULE_INCOMPLETE_OBLIGATION_SET"
RULE_DUPLICATE_OBLIGATION_ID = "RULE_DUPLICATE_OBLIGATION_ID"
RULE_UNKNOWN_OBLIGATION_ID = "RULE_UNKNOWN_OBLIGATION_ID"
RULE_UNREGISTERED_CITATION = "RULE_UNREGISTERED_CITATION"
RULE_PROVENANCE_CONFLICT = "RULE_PROVENANCE_CONFLICT"
RULE_NON_PRODUCTION_EVIDENCE_CONFIG = "RULE_NON_PRODUCTION_EVIDENCE_CONFIG"


# -----------------------------------------------------------------------------
# Canonical Required Obligation Set
# -----------------------------------------------------------------------------

# Full canonical set of 18 GM1.10C memory ownership proof obligations.
# Overall readiness evaluates strictly to False unless all 18 obligations are
# present, unique, and verified with non-historical, pinned origin/main evidence.
REQUIRED_OBLIGATION_IDS: frozenset[str] = frozenset({
    "OBLIG-MEM-01",
    "OBLIG-MEM-02",
    "OBLIG-MEM-03",
    "OBLIG-MEM-04",
    "OBLIG-MEM-05",
    "OBLIG-MEM-06",
    "OBLIG-MEM-07",
    "OBLIG-MEM-08",
    "OBLIG-MEM-09",
    "OBLIG-MEM-10",
    "OBLIG-MEM-11",
    "OBLIG-MEM-12",
    "OBLIG-MEM-13",
    "OBLIG-MEM-14",
    "OBLIG-MEM-15",
    "OBLIG-MEM-16A",
    "OBLIG-MEM-16B",
    "OBLIG-MEM-17",
})


# -----------------------------------------------------------------------------
# Tracked Origin/Main File Whitelist, Digest Pins & Historical Constants
# -----------------------------------------------------------------------------

# Commit on origin/main from which file digests were authenticated
ORIGIN_MAIN_PIN_COMMIT: str = "581b1a4bb30456bf18c46dc4bcf61b0375aee251"

# Supported primary firmware revision identity (strict allowlist)
SUPPORTED_FIRMWARE: str = "GM1.10C"
SUPPORTED_FIRMWARES: frozenset[str] = frozenset({SUPPORTED_FIRMWARE})


def normalize_firmware(val: Optional[str]) -> str:
    """Normalize firmware revision string: strip whitespace and uppercase."""
    if val is None:
        return ""
    return str(val).strip().upper()


def is_supported_firmware(val: Optional[str]) -> bool:
    """Strict allowlist check: accepts only exact supported identity GM1.10C."""
    return normalize_firmware(val) == SUPPORTED_FIRMWARE


# SHA-256 digests of cited evidence files on origin/main @ 581b1a4bb30456bf18c46dc4bcf61b0375aee251
# Computed via read-only git show origin/main:<path> piped into python3 hashlib.
# Authoritative and immutable via MappingProxyType.
_PINNED_ORIGIN_MAIN_FILE_HASHES_RAW: Dict[str, str] = {
    "chdk-port/platform/g3x/sub/110c/boot_prototype.c": "f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68",
    "docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md": "c04e83dec333fb6c41b4a854394a11f3fc36ce71c0eda6f3ef212da6a03bf74d",
    "docs/GM110C_MEMORY_MAP.md": "74561df2bd43b233ea35763df9689076791f67fcedf24291fb72f17571efdf05",
    "docs/HANDOFF.md": "6c0c19054e6c6c68f71821ed300f456d41d8180569c48224e4660bc1e116a0d5",
    "docs/PATCH_AUDIT_110E.md": "6606f6c8b41bdb02748d12bac067079ebbbaf3b8912d24b85b27bfa63414cdfa",
    "docs/PORT11A_GM110C_ROM_EVIDENCE.md": "45928b29efc2062796ae51a326fcfec2f650e9589944f530158b7a9dcaaec8da",
    "docs/PORT5A_RANMA_PORT_RECOVERY.md": "6c68897320b97c6d67a2ad6f6554c41a98d11105d8ab45394186a738364400e8",
    "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md": "9855a2316aba777065547f7e8f30a3aabff5cff8ce94be48deb3c10406df281c",
    "docs/PROJECT_STATE.md": "3b700ed093a4e2d37c9dc57e3cf8e296e679946ac618017f95ec9eb43cad8121",
    "docs/SAFETY.md": "c50f25b07500a844a374193b839028ca82de6007e6778eeb3a04049ffaaaa30d",
    "research/historical/g3x/g3x_100c_historical_symbols.csv": "6289e65e0c1f9d3c137315aacdd368a9da6f8eb4c9438d03464f5ac0342205c6",
    "research/historical/g3x/g3x_100c_historical_symbols.json": "13524f24b855dddc9eb44ab5141020e5c8d34eb8a4a7f50c8e5914269a6bb86d",
    "vendor/g3x-platform/platform/g3x/platform_camera.h": "0fed491abe86c069166c4aadc50eceec81dd0da835943049e03b370fede9f6ac",
}

PINNED_ORIGIN_MAIN_FILE_HASHES: MappingProxyType[str, str] = MappingProxyType(
    _PINNED_ORIGIN_MAIN_FILE_HASHES_RAW
)

# Exactly 103 files tracked on origin/main @ 581b1a4bb30456bf18c46dc4bcf61b0375aee251
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

# Artifacts that represent historical firmware only (1.00C / 1.10E) and cannot verify GM1.10C
HISTORICAL_ONLY_PATHS: frozenset[str] = frozenset({
    "research/historical/g3x/g3x_100c_historical_symbols.csv",
    "research/historical/g3x/g3x_100c_historical_symbols.json",
    "docs/PATCH_AUDIT_110E.md",
    "g3x_110e.patch",
    "platform/g3x/notes.txt",
    "platform/g3x/makefile.inc",
})

# Historical firmware revision strings that are not GM1.10C
HISTORICAL_FIRMWARES: frozenset[str] = frozenset({
    "1.00C", "GM1.00C", "1.10E", "GM1.10E"
})


# -----------------------------------------------------------------------------
# Address Provenance Registry: Every Address Cited in This Module
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class AddressCitation:
    """Exact document and line provenance for an address on origin/main."""
    address: str
    document_ref: str
    line: int
    context: str
    firmware: str = "GM1.10C"


# All 57 addresses appearing in this module are verified present in tracked origin/main files.
# Authoritative and immutable via MappingProxyType.
_TRACKED_ADDRESS_CITATIONS_RAW: Dict[str, AddressCitation] = {
    "0x00000000": AddressCitation("0x00000000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 166, "Low vector table base"),
    "0x00003FFF": AddressCitation("0x00003FFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 166, "Historical exception vectors upper limit"),
    "0x00008000": AddressCitation("0x00008000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 167, "Low-RAM data copy destination start"),
    "0x0003F4F3": AddressCitation("0x0003F4F3", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 167, "Low-RAM data copy destination end"),
    "0x0003F4F4": AddressCitation("0x0003F4F4", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 168, "Canon static BSS start"),
    "0x003489B3": AddressCitation("0x003489B3", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 168, "Canon static BSS end inclusive"),
    "0x003489B4": AddressCitation("0x003489B4", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 169, "Default Canon heap base / BSS upper limit"),
    "0x003C89B4": AddressCitation("0x003C89B4", "docs/HANDOFF.md", 796, "Shifted heap base candidate (0x003489B4 + 512 KiB)"),
    "0x00600014": AddressCitation("0x00600014", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 169, "DryOS heap sub-pool 1 boundary / Pool 0 limit"),
    "0x0060E000": AddressCitation("0x0060E000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 170, "Heap Pool 0 upper chunk block descriptor sp[0x14]"),
    "0x006CDFFF": AddressCitation("0x006CDFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 169, "Default Canon heap upper limit before AdditionAgent"),
    "0x006CE000": AddressCitation("0x006CE000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 171, "AdditionAgent ARAM buffer base / headroom comparator"),
    "0x000B1FEC": AddressCitation("0x000B1FEC", "docs/PROJECT_STATE.md", 294, "Kernel minimum headroom assert threshold (712 KiB)"),
    "0x006EFFFF": AddressCitation("0x006EFFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 171, "AdditionAgent ARAM buffer end inclusive (0x22000 B)"),
    "0x22000": AddressCitation("0x22000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 171, "AdditionAgent buffer byte length in ARAM heap entry"),
    "0x8000": AddressCitation("0x8000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 101, "Historical Ranma loader stack pointer setup"),
    "0x00700000": AddressCitation("0x00700000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 172, "Historical OMAR staging RAM base"),
    "0x0075FFFF": AddressCitation("0x0075FFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 172, "Historical OMAR staging RAM end inclusive"),
    "0x00760000": AddressCitation("0x00760000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173, "Mid-DRAM unreferenced gap start"),
    "0x007FFFFF": AddressCitation("0x007FFFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173, "Mid-DRAM unreferenced gap sub-span end"),
    "0x00A00000": AddressCitation("0x00A00000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 174, "Zico Xtensa code cached mirror start"),
    "0x00B14DEF": AddressCitation("0x00B14DEF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 174, "Zico Xtensa code cached mirror end"),
    "0x00B14DF0": AddressCitation("0x00B14DF0", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173, "Unreferenced DRAM gap sub-span start"),
    "0x00BFFFFF": AddressCitation("0x00BFFFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173, "Unreferenced DRAM gap sub-span end"),
    "0x00C16B90": AddressCitation("0x00C16B90", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173, "Unreferenced DRAM gap sub-span start"),
    "0x00C80000": AddressCitation("0x00C80000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 175, "Ranma GM1.10E high-DRAM placement candidate"),
    "0x00DFFFFF": AddressCitation("0x00DFFFFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 175, "Ranma GM1.10E high-DRAM placement candidate end"),
    "0x00E00000": AddressCitation("0x00E00000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 175, "Historical audio/video avcore / Xtensa RAM base"),
    "0x010E1000": AddressCitation("0x010E1000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 78, "Firmware executable RAM mirror destination start"),
    "0x01107CFF": AddressCitation("0x01107CFF", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 177, "Firmware executable RAM mirror destination end inclusive"),
    "0x01107D00": AddressCitation("0x01107D00", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 78, "Firmware executable RAM mirror copy loop limit (blo)"),
    "0x20000000": AddressCitation("0x20000000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 179, "Historical RAM mirror aperture base"),
    "0x40000000": AddressCitation("0x40000000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 179, "CAM_UNCACHED_BIT / uncached peripheral mirror base"),
    "0x406CE000": AddressCitation("0x406CE000", "docs/PROJECT_STATE.md", 308, "AdditionAgent uncached memory alias"),
    "0x43DBFCA0": AddressCitation("0x43DBFCA0", "docs/PROJECT_STATE.md", 308, "Upper DRAM sensor raw DMA buffer pointer"),
    "0x80A00000": AddressCitation("0x80A00000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 174, "Zico Xtensa uncached copy destination"),
    "0xBFE10000": AddressCitation("0xBFE10000", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 178, "BTCM / early TCM initialization base"),
    "0xBFE10800": AddressCitation("0xBFE10800", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "Cortex-R4 ATCM relocated destination start"),
    "0xBFE14A3C": AddressCitation("0xBFE14A3C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "CreateTask Thumb instruction body address in ATCM"),
    "0xBFE17418": AddressCitation("0xBFE17418", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 178, "Historical ATCM kernel copy end word"),
    "0xBFE17419": AddressCitation("0xBFE17419", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "ATCM copy loop limit literal [0xFC0200CC]"),
    "0xBFE1741B": AddressCitation("0xBFE1741B", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "ATCM relocated span end inclusive (27,676 B)"),
    "0xFC020040": AddressCitation("0xFC020040", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 60, "Slice S1A ATCM copy loop start"),
    "0xFC020052": AddressCitation("0xFC020052", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "Slice S1A ATCM copy loop branch"),
    "0xFC0200C4": AddressCitation("0xFC0200C4", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 103, "ROM literal for ATCM source start (0xFCEEF24C)"),
    "0xFC0200C8": AddressCitation("0xFC0200C8", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 104, "ROM literal for ATCM destination start (0xBFE10800)"),
    "0xFC0200CC": AddressCitation("0xFC0200CC", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "ROM literal for ATCM loop limit (0xBFE17419)"),
    "0xFC0200CF": AddressCitation("0xFC0200CF", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 60, "Slice S1A literal pool end"),
    "0xFC0200DC": AddressCitation("0xFC0200DC", "docs/PROJECT_STATE.md", 295, "ROM literal anchoring Canon BSS zero end (0x003489B4)"),
    "0xFC05B3C8": AddressCitation("0xFC05B3C8", "docs/PROJECT_STATE.md", 294, "DryOS kernel heap setup routine"),
    "0xFC05B450": AddressCitation("0xFC05B450", "docs/PROJECT_STATE.md", 295, "ROM literal anchoring DryOS heap base (0x003489B4)"),
    "0xFC05B454": AddressCitation("0xFC05B454", "docs/PORT5A_RANMA_PORT_RECOVERY.md", 108, "ROM literal anchoring headroom limit (0x006CE000)"),
    "0xFC31BBC4": AddressCitation("0xFC31BBC4", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "ARM veneer j_CreateTask jumping to ATCM 0xBFE14A3D"),
    "0xFC55888C": AddressCitation("0xFC55888C", "docs/PROJECT_STATE.md", 308, "AdditionAgent ROM read routine start"),
    "0xFC5588C0": AddressCitation("0xFC5588C0", "docs/PROJECT_STATE.md", 308, "AdditionAgent ROM read routine end"),
    "0xFCE91058": AddressCitation("0xFCE91058", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 77, "Low-RAM data copy source in ROM"),
    "0xFCEC854C": AddressCitation("0xFCEC854C", "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 75, "Firmware executable RAM mirror copy source in ROM"),
    "0xFCEEF24C": AddressCitation("0xFCEEF24C", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "Cortex-R4 ATCM copy source in ROM start"),
    "0xFCEF5E67": AddressCitation("0xFCEF5E67", "docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20, "Cortex-R4 ATCM copy source in ROM end inclusive"),
}

TRACKED_ADDRESS_CITATIONS: MappingProxyType[str, AddressCitation] = MappingProxyType(
    _TRACKED_ADDRESS_CITATIONS_RAW
)


# -----------------------------------------------------------------------------
# Trusted Citation Provenance Registry
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class CitationProvenance:
    """Trusted provenance entry for a cited line in repository documentation."""
    firmware: str
    is_historical: bool
    context: str = ""


# Authoritative provenance registry keyed by (path, line).
# Immutable MappingProxyType module constant: caller-supplied flags are NOT trusted,
# and unspecified provenance never defaults to GM1.10C. Any citation not in this
# registry forces evaluate() to return not-ready (RULE_UNREGISTERED_CITATION).
_CITATION_PROVENANCE_REGISTRY_RAW: Dict[Tuple[str, int], CitationProvenance] = {
    # docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 75): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Firmware executable RAM mirror copy source in ROM (0xFCEC854C)",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 77): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Low-RAM data copy source in ROM (0xFCE91058)",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 78): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Firmware executable RAM mirror destination start (0x010E1000) and blo limit (0x01107D00)",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 101): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Historical Ranma loader stack pointer setup (0x8000)",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 166): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="ATCM exception vectors 0x00000000..0x00003FFF historically reported for GM1.10E",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 167): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Canon low-RAM data section 0x00008000..0x0003F4F3",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 168): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Canon static BSS 0x0003F4F4..0x003489B3",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 169): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Default Canon heap base 0x003489B4 / sub-pool 1 limit 0x00600014 / upper limit 0x006CDFFF",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 170): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Heap Pool 0 upper chunk block descriptor 0x0060E000",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 171): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="AdditionAgent ARAM buffer base 0x006CE000..0x006EFFFF (size 0x22000)",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 172): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Historical OMAR staging RAM 0x00700000..0x0075FFFF documented only for GM1.10E",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 173): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Mid-DRAM unreferenced gap 0x00760000..0x00C80000 documented only for GM1.10E",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 174): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Zico Xtensa code cached mirror 0x00A00000..0x00B14DEF / 0x80A00000",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 175): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Ranma GM1.10E high-DRAM placement candidate 0x00C80000..0x00DFFFFF",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 176): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Xtensa / avcore RAM base 0x00E00000 documented only for GM1.10E",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 177): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Firmware executable RAM mirror destination end 0x010E1000..0x01107CFF",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 178): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Historical ATCM/BTCM kernel copy 0xBFE10800..0xBFE17418",
    ),
    ("docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md", 179): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Historical RAM mirror 0x20000000 / uncached mirror 0x40000000",
    ),

    # docs/PORT5A_RANMA_PORT_RECOVERY.md
    ("docs/PORT5A_RANMA_PORT_RECOVERY.md", 108): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Ranma GM1.10E core placement comparison vs GM1.10C candidate",
    ),

    # docs/PROJECT_STATE.md
    ("docs/PROJECT_STATE.md", 294): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Kernel minimum headroom assert threshold 0x000B1FEC / routine 0xFC05B3C8",
    ),
    ("docs/PROJECT_STATE.md", 295): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="ROM literals 0xFC0200DC and 0xFC05B450 anchoring Canon BSS end and heap base",
    ),
    ("docs/PROJECT_STATE.md", 308): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="AdditionAgent DMA read routine 0xFC55888C..0xFC5588C0 and sensor raw buffer pointer 0x43DBFCA0",
    ),

    # docs/HANDOFF.md
    ("docs/HANDOFF.md", 796): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Shifted heap base candidate scan [0x003489B4, 0x003C89B4)",
    ),

    # chdk-port/platform/g3x/sub/110c/boot_prototype.c
    ("chdk-port/platform/g3x/sub/110c/boot_prototype.c", 108): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Executable RAM mirror copy loop blo against 0x01107D00",
    ),
    ("chdk-port/platform/g3x/sub/110c/boot_prototype.c", 179): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Shifted heap base model and headroom check 0x006CE000 - r4 >= 0x000B1FEC",
    ),
    ("chdk-port/platform/g3x/sub/110c/boot_prototype.c", 206): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Heap chunk block descriptor 0x0060E000",
    ),
    ("chdk-port/platform/g3x/sub/110c/boot_prototype.c", 210): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Sub-pool limit literal 0x00600014",
    ),

    # vendor/g3x-platform/platform/g3x/platform_camera.h
    ("vendor/g3x-platform/platform/g3x/platform_camera.h", 38): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="CAM_UNCACHED_BIT 0x40000000 definition",
    ),
    ("vendor/g3x-platform/platform/g3x/platform_camera.h", 44): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Sensor RAW buffer dimensions definition",
    ),

    # docs/PORT11A_GM110C_ROM_EVIDENCE.md
    ("docs/PORT11A_GM110C_ROM_EVIDENCE.md", 20): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Primary GM1.10C ROM Slice S1A evidence",
    ),
    ("docs/PORT11A_GM110C_ROM_EVIDENCE.md", 60): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Slice S1A ATCM copy loop start and literal pool end",
    ),
    ("docs/PORT11A_GM110C_ROM_EVIDENCE.md", 103): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="ROM literal for ATCM source start (0xFCEEF24C)",
    ),
    ("docs/PORT11A_GM110C_ROM_EVIDENCE.md", 104): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="ROM literal for ATCM destination start (0xBFE10800)",
    ),

    # docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md
    ("docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md", 79): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="ATCM target execution role in symbol reconciliation",
    ),

    # Tracked baseline files used in citations and tests
    ("docs/GM110C_MEMORY_MAP.md", 1): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="GM1.10C memory map header",
    ),
    ("docs/SAFETY.md", 1): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Project safety policy header",
    ),
    ("README.md", 1): CitationProvenance(
        firmware="GM1.10C",
        is_historical=False,
        context="Project README header",
    ),
    ("research/historical/g3x/g3x_100c_historical_symbols.csv", 1): CitationProvenance(
        firmware="1.00C",
        is_historical=True,
        context="Historical 1.00C symbol table CSV",
    ),
    ("research/historical/g3x/g3x_100c_historical_symbols.json", 1): CitationProvenance(
        firmware="1.00C",
        is_historical=True,
        context="Historical 1.00C symbol table JSON",
    ),
    ("docs/PATCH_AUDIT_110E.md", 1): CitationProvenance(
        firmware="GM1.10E",
        is_historical=True,
        context="Historical GM1.10E patch audit",
    ),
}

CITATION_PROVENANCE_REGISTRY: MappingProxyType[Tuple[str, int], CitationProvenance] = MappingProxyType(
    _CITATION_PROVENANCE_REGISTRY_RAW
)


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Citation:
    """A documented citation supporting or contextualizing an obligation."""
    path: str
    line: Optional[int] = None
    end_line: Optional[int] = None
    firmware: Optional[str] = None
    note: str = ""
    is_historical: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "path": self.path,
            "firmware": self.firmware,
            "is_historical": self.is_historical,
        }
        if self.line is not None:
            res["line"] = self.line
        if self.end_line is not None:
            res["end_line"] = self.end_line
        if self.note:
            res["note"] = self.note
        return res


@dataclass(frozen=True)
class MemoryObligation:
    """A proof obligation governing GM1.10C memory ownership."""
    id: str
    statement: str
    required_evidence_type: str
    acceptable_tracked_sources: Tuple[str, ...]
    current_status: ObligationStatus
    citations: Tuple[Citation, ...]
    pending_pr: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "required_evidence_type": self.required_evidence_type,
            "acceptable_tracked_sources": list(self.acceptable_tracked_sources),
            "current_status": self.current_status.value,
            "citations": [c.to_dict() for c in self.citations],
            "pending_pr": self.pending_pr,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ObligationFinding:
    """An individual evaluation finding or policy violation."""
    rule_id: str
    obligation_id: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str


@dataclass(frozen=True)
class SingleObligationEvaluation:
    """Evaluation output for an individual obligation."""
    obligation_id: str
    current_status: ObligationStatus
    is_verified: bool
    findings: Tuple[ObligationFinding, ...]


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregate fail-closed evaluation result across all proof obligations."""
    is_ready: bool
    total_obligations: int
    verified_count: int
    inferred_count: int
    unknown_count: int
    error_count: int
    warning_count: int
    obligation_results: Dict[str, SingleObligationEvaluation]
    findings: Tuple[ObligationFinding, ...]

    def __bool__(self) -> bool:
        return self.is_ready

    def summary(self) -> str:
        status_str = "READY" if self.is_ready else "NOT READY (FAIL-CLOSED)"
        lines = [
            "=" * 70,
            f"GM1.10C Memory Ownership Obligations Evaluation: {status_str}",
            "=" * 70,
            f"Total Obligations : {self.total_obligations}",
            f"  - VERIFIED      : {self.verified_count}",
            f"  - INFERRED      : {self.inferred_count}",
            f"  - UNKNOWN       : {self.unknown_count}",
            f"Evaluation Errors : {self.error_count}",
            f"Warnings          : {self.warning_count}",
            "-" * 70,
        ]
        for f in self.findings:
            lines.append(f"[{f.severity}] [{f.obligation_id}] {f.rule_id}: {f.message}")
        lines.append("=" * 70)
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Default GM1.10C Memory Ownership Proof Obligations Dataset
# -----------------------------------------------------------------------------

DEFAULT_MEMORY_OBLIGATIONS: Tuple[MemoryObligation, ...] = (
    MemoryObligation(
        id="OBLIG-MEM-01",
        statement=(
            "Primary ROM disassembly must prove Cortex-R4 exception vector table and "
            "hardware scratch layout at 0x00000000..0x00003FFF on GM1.10C; historical "
            "GM1.10E MEMBASEADDR=0x8000 does not prove GM1.10C vector layout."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "docs/GM110C_MEMORY_MAP.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=166,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 166 records ATCM exception vectors as HISTORICALLY REPORTED for GM1.10E; ROM vectors uninspected on GM1.10C",
            ),
        ),
        notes="Inferred from historical boot comparison; primary ROM disassembly required.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-02",
        statement=(
            "Primary ROM disassembly must prove bounds 0x00008000..0x0003F4F3, copy source "
            "0xFCE91058, and DryOS kernel data ownership (TCBs, interrupt vectors, timer tables) "
            "on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=77,
                firmware="GM1.10C",
                note="Low-RAM copy source 0xFCE91058 cited from prototype C:134; ROM uninspected",
            ),
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=167,
                firmware="GM1.10C",
                note="Low-RAM data section 0x00008000–0x0003F4F3 tracked; ownership inferred",
            ),
        ),
        notes="Low-RAM data copy bounds modeled in prototype; kernel object ownership unverified in ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-03",
        statement=(
            "Primary ROM disassembly must prove static BSS bounds 0x0003F4F4..0x003489B3 and "
            "early boot zeroing loop on GM1.10C; literal 0xFC0200DC / 0xFC05B450 requires "
            "instruction disassembly proof."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "docs/PROJECT_STATE.md",
            "docs/PORT11A_GM110C_ROM_EVIDENCE.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=168,
                firmware="GM1.10C",
                note="Canon BSS 0x0003F4F4–0x003489B3 tracked from prototype C:144–153",
            ),
            Citation(
                path="docs/PROJECT_STATE.md",
                line=295,
                firmware="GM1.10C",
                note="ROM literals 0xFC0200DC and 0xFC05B450 reported in narrative text",
            ),
        ),
        notes="BSS boundaries modeled from prototype; zeroing loop instructions uninspected in ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-04",
        statement=(
            "Prove that shifting heap base from 0x003489B4 to 0x003C89B4 safely isolates CHDK "
            "core from BSS collision and that DryOS allocator AllocateMemory never issues "
            "allocations below 0x003C89B4."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
            "docs/PROJECT_STATE.md",
            "docs/HANDOFF.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                line=179,
                firmware="GM1.10C",
                note="Prototype models shifted base r4; allocator exclusion proof unmerged in PR #23",
            ),
            Citation(
                path="docs/HANDOFF.md",
                line=796,
                firmware="GM1.10C",
                note="ROM scan of [0x003489B4, 0x003C89B4) reported in narrative handoff",
            ),
        ),
        pending_pr="PR #23",
        notes="Evidence found only in unmerged PR #23 (branch origin/research/port12a-memory-ownership).",
    ),
    MemoryObligation(
        id="OBLIG-MEM-05",
        statement=(
            "Primary ROM disassembly must prove DryOS dynamic system heap Pool 0 boundaries, "
            "allocation behavior of AllocateMemory, and sub-pool limit literal 0x00600014 on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                line=210,
                firmware="GM1.10C",
                note="Prototype models sub-pool limit 0x00600014; ROM allocator uninspected",
            ),
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=169,
                firmware="GM1.10C",
                note="Upper limit 0x00600014 recorded in comparison table",
            ),
        ),
        notes="Sub-pool limit modeled in prototype; allocator implementation uninspected.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-06",
        statement=(
            "Primary ROM disassembly must prove DryOS kernel object table descriptors and sub-pool "
            "memory ranges starting at 0x00600014 on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=169,
                firmware="GM1.10C",
                note="Descriptor slot values classified as INFERRED in tracked comparison",
            ),
        ),
        notes="Object table allocation details uninspected in GM1.10C ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-07",
        statement=(
            "Primary ROM disassembly must prove upper chunk block allocation bounds "
            "0x0060E000..0x006CDFFF and chunk size parameter in DryOS setup structure on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=170,
                firmware="GM1.10C",
                note="Descriptor field 0x0060E000 classified as INFERRED (Finding F6)",
            ),
            Citation(
                path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                line=206,
                firmware="GM1.10C",
                note="Prototype sets heap upper limit and chunk block descriptor to 0x0060E000",
            ),
        ),
        notes="Fixed chunk allocator mechanism is inferred from stack descriptor slots.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-08",
        statement=(
            "Primary ROM disassembly must prove DryOS kernel heap headroom check "
            "(0x006CE000 - r4 >= 0x000B1FEC) and comparator limit in kernel init 0xFC05B3C8 "
            "on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PROJECT_STATE.md",
            "docs/HANDOFF.md",
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
            "docs/PORT5A_RANMA_PORT_RECOVERY.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PROJECT_STATE.md",
                line=294,
                firmware="GM1.10C",
                note="Kernel setup trace models 0x006CE000 - r4 >= 0x000B1FEC; routine 0xFC05B3C8 uninspected in ROM",
            ),
            Citation(
                path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                line=179,
                firmware="GM1.10C",
                note="Prototype implements headroom check 0x006CE000 - r4 >= 0x000B1FEC",
            ),
            Citation(
                path="docs/PORT5A_RANMA_PORT_RECOVERY.md",
                line=108,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 108 compares GM1.10E core placement vs GM1.10C candidate; literal 0xFC05B454 in secondary comparison",
            ),
        ),
        notes="Formula is mathematically modeled and consistent; kernel init routine 0xFC05B3C8 uninspected in ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-09",
        statement=(
            "Primary ROM disassembly must prove AdditionAgent storage direct buffer bounds "
            "0x006CE000..0x006EFFFF (size 0x22000) and DMA access in routine "
            "0xFC55888C..0xFC5588C0 on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
            "docs/PROJECT_STATE.md",
            "docs/HANDOFF.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=171,
                firmware="GM1.10C",
                note="AdditionAgent ARAM heap 0x006CE000–0x006EFFFF (0x22000 B) tracked",
            ),
            Citation(
                path="docs/PROJECT_STATE.md",
                line=308,
                firmware="GM1.10C",
                note="AdditionAgent.c 0xFC55888C..0xFC5588C0 reads 0x22000 B into 0x006CE000 / 0x406CE000",
            ),
        ),
        notes="AdditionAgent reads up to 0x22000 bytes ending at 0x006EFFFF; ROM routine uninspected.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-10",
        statement=(
            "Prove bounds and Cortex-R4 CPU-1 / IPC DMA ownership of OMAR secondary core "
            "communication area 0x00700000..0x0075FFFF on GM1.10C via primary ROM disassembly."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=172,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 172 documents OMAR only for GM1.10E ('Not documented' on GM1.10C) and strictly HISTORICALLY REPORTED",
            ),
        ),
        notes="OMAR staging area is undocumented on GM1.10C; secondary core IPC unverified.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-11",
        statement=(
            "Characterize Mid-DRAM gap starting at 0x00760000 to prove absence of subsystem "
            "allocations, enforcing the rule that unreferenced DRAM is not empty."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=173,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 173 documents mid-DRAM unused ranges only for GM1.10E ('Not documented' on GM1.10C); ownership unknown",
            ),
        ),
        notes="Uninspected memory cannot be treated as empty or safe.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-12",
        statement=(
            "Formally verify the hazards (sensor RAW DMA collision, co-processor blob overlap, "
            "unverified DRAM boundary) that disqualify Ranma GM1.10E high-DRAM placement "
            "0x00C80000..0x00DFFFFF on GM1.10C."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=175,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 175 documents Ranma high-DRAM placement candidate only for GM1.10E ('Not used' on GM1.10C); hazard analysis in pending PR #23",
            ),
        ),
        pending_pr="PR #23",
        notes="Evidence found only in unmerged PR #23 (branch origin/research/port12a-memory-ownership).",
    ),
    MemoryObligation(
        id="OBLIG-MEM-13",
        statement=(
            "Characterize High-DRAM gap starting at 0x00E00000 to prove absence of audio/video "
            "co-processor firmware blobs or dynamic buffers."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=176,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 176 documents Xtensa / avcore RAM base at 0x00E00000 only for GM1.10E ('Not documented' on GM1.10C); blob loading uninspected",
            ),
        ),
        notes="Uninspected DRAM gap; audio/video codec blob loading uninspected in ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-14",
        statement=(
            "Prove bounds 0x010E1000..0x01107CFF (stopping strictly before limit literal "
            "0x01107D00) and ROM source 0xFCEC854C for executable RAM mirror on GM1.10C via "
            "primary ROM disassembly."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "chdk-port/platform/g3x/sub/110c/boot_prototype.c",
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="chdk-port/platform/g3x/sub/110c/boot_prototype.c",
                line=108,
                firmware="GM1.10C",
                note="Copy loop uses blo against limit 0x01107D00; ROM routines uninspected",
            ),
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=75,
                firmware="GM1.10C",
                note="RAM-code copy source 0xFCEC854C noted from prototype C:107",
            ),
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=177,
                firmware="GM1.10C",
                note="RAM-copied code 0x010E1000–0x01107CFF tracked in comparison matrix",
            ),
        ),
        notes="Copy loop bounds modeled in prototype; copied routines uninspected in ROM.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-15",
        statement=(
            "Prove physical DRAM placement and lower bound of dynamic 20.2 MP image sensor RAW "
            "circular DMA buffers via primary ROM disassembly of capture routines."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "vendor/g3x-platform/platform/g3x/platform_camera.h",
            "docs/PROJECT_STATE.md",
            "docs/HANDOFF.md",
        ),
        current_status=ObligationStatus.UNKNOWN,
        citations=(
            Citation(
                path="vendor/g3x-platform/platform/g3x/platform_camera.h",
                line=44,
                firmware="GM1.10C",
                note="Sensor geometry (5632x3710x14/8 = 36,565,760 B) verified in header; DMA placement unverified",
            ),
            Citation(
                path="docs/PROJECT_STATE.md",
                line=308,
                firmware="GM1.10C",
                note="Upper DRAM sensor raw DMA buffer pointer 0x43DBFCA0 documented in project state",
            ),
        ),
        pending_pr="PR #23",
        notes=(
            "Evidence found only in unmerged PR #23 (branch origin/research/port12a-memory-ownership, "
            "checklist item E-01)."
        ),
    ),
    MemoryObligation(
        id="OBLIG-MEM-16A",
        statement=(
            "Prove Cortex-R4 ATCM relocated span bounds 0xBFE10800..0xBFE1741B copied from "
            "ROM 0xFCEEF24C..0xFCEF5E67 by boot() copy loop (0xFC020040..0xFC020052, limit "
            "literal 0xBFE17419) via primary ROM disassembly."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT11A_GM110C_ROM_EVIDENCE.md",
            "docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md",
        ),
        current_status=ObligationStatus.VERIFIED,
        citations=(
            Citation(
                path="docs/PORT11A_GM110C_ROM_EVIDENCE.md",
                line=20,
                end_line=60,
                firmware="GM1.10C",
                note="STATIC_VERIFIED in pinned ROM Slice S1A; 6,919 words copied from 0xFCEEF24C to 0xBFE10800..0xBFE1741B",
            ),
        ),
        notes="Genuinely verified by tracked primary GM1.10C ROM evidence in Slice S1A.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-16B",
        statement=(
            "Prove that routines resident in ATCM (including CreateTask veneer target at "
            "0xBFE14A3C) and scheduler queues execute strictly in ATCM without runtime "
            "collision from other masters."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "docs/PORT11A_GM110C_ROM_EVIDENCE.md",
            "docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="docs/PORT11A_GM110C_ROM_EVIDENCE.md",
                line=20,
                firmware="GM1.10C",
                note="Instruction body verified; functional scheduler ownership is INFERRED per PORT11A:26",
            ),
            Citation(
                path="docs/G3X_HISTORICAL_SYMBOL_RECONCILIATION.md",
                line=79,
                firmware="GM1.10C",
                note="ATCM target execution role described in symbol reconciliation",
            ),
        ),
        notes="Static copy verified, but functional scheduler ownership remains INFERRED.",
    ),
    MemoryObligation(
        id="OBLIG-MEM-17",
        statement=(
            "Prove uncached peripheral apertures (0x40000000) and Cortex-R4 MPU region "
            "configurations on GM1.10C via primary ROM disassembly."
        ),
        required_evidence_type=ProvenanceType.ROM_VERIFIED.value,
        acceptable_tracked_sources=(
            "vendor/g3x-platform/platform/g3x/platform_camera.h",
            "docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
        ),
        current_status=ObligationStatus.INFERRED,
        citations=(
            Citation(
                path="vendor/g3x-platform/platform/g3x/platform_camera.h",
                line=38,
                firmware="GM1.10C",
                note="CAM_UNCACHED_BIT 0x40000000 defined in tracked header; MPU configuration uninspected",
            ),
            Citation(
                path="docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md",
                line=179,
                firmware="GM1.10E",
                is_historical=True,
                note="Line 179 documents uncached mirror 0x40000000 as HISTORICALLY REPORTED from GM1.10E notes",
            ),
        ),
        notes="Aperture bit is documented, but physical memory map and MPU configuration are INFERRED.",
    ),
)


# -----------------------------------------------------------------------------
# Internal Obligation Evaluator & Public Per-Obligation Helper
# -----------------------------------------------------------------------------

def _evaluate_obligation(
    oblig: MemoryObligation,
    resolved_root: Path,
    active_pins: MappingProxyType[str, str] | Dict[str, str],
    file_reader: Optional[Callable[[Path], bytes]] = None,
) -> Tuple[bool, List[ObligationFinding]]:
    """Internal helper to validate citations and evaluate single obligation certainty."""
    ob_findings: List[ObligationFinding] = []
    has_error = False

    # 1. Citations existence and tracking validation
    if not oblig.citations:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_EMPTY_CITATIONS,
                obligation_id=oblig.id,
                severity="ERROR",
                message=f"Obligation '{oblig.id}' has no supporting citations",
            )
        )
        has_error = True

    for cit in oblig.citations:
        cit_path = resolved_root / cit.path
        content_bytes: Optional[bytes] = None

        # Check 1a: File existence and readability
        if file_reader is not None:
            try:
                content_bytes = file_reader(cit_path)
            except FileNotFoundError:
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_MISSING_CITED_PATH,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=f"Cited path '{cit.path}' does not exist",
                    )
                )
                has_error = True
            except Exception as e:
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_UNREADABLE_SOURCE,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=f"Cited file '{cit.path}' cannot be read: {e}",
                    )
                )
                has_error = True
        else:
            if not cit_path.is_file():
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_MISSING_CITED_PATH,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=(
                            f"Cited path '{cit.path}' does not exist on disk at {cit_path}"
                        ),
                    )
                )
                has_error = True
            else:
                try:
                    content_bytes = cit_path.read_bytes()
                except Exception as e:
                    ob_findings.append(
                        ObligationFinding(
                            rule_id=RULE_UNREADABLE_SOURCE,
                            obligation_id=oblig.id,
                            severity="ERROR",
                            message=f"Cited file '{cit.path}' cannot be read: {e}",
                        )
                    )
                    has_error = True

        # Check 1b: Tracked on origin/main whitelist
        if cit.path not in ORIGIN_MAIN_TRACKED_FILES:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_UNTRACKED_SOURCE,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Cited path '{cit.path}' is not a tracked origin/main file"
                    ),
                )
            )
            has_error = True

        # Check 1c: Content authentication against pinned origin/main hash
        if cit.path not in active_pins:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_UNPINNED_SOURCE,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Cited path '{cit.path}' is not pinned in PINNED_ORIGIN_MAIN_FILE_HASHES "
                        f"(origin/main commit {ORIGIN_MAIN_PIN_COMMIT})"
                    ),
                )
            )
            has_error = True
        elif content_bytes is not None:
            local_sha256 = hashlib.sha256(content_bytes).hexdigest()
            expected_sha256 = active_pins[cit.path]
            if local_sha256.lower() != expected_sha256.lower():
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_CONTENT_HASH_MISMATCH,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=(
                            f"Content authentication failed for '{cit.path}': "
                            f"local SHA-256 {local_sha256} does not match pinned {expected_sha256} "
                            f"(origin/main commit {ORIGIN_MAIN_PIN_COMMIT})"
                        ),
                    )
                )
                has_error = True

        # Check 1d: Explicitly in obligation's acceptable tracked sources
        if cit.path not in oblig.acceptable_tracked_sources:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_UNACCEPTABLE_SOURCE,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Cited source '{cit.path}' is not listed in acceptable_tracked_sources "
                        f"{oblig.acceptable_tracked_sources}"
                    ),
                )
            )
            has_error = True

        # Check 1e: Citation Provenance Registry lookup & historical provenance enforcement
        reg_key = (cit.path, cit.line) if cit.line is not None else None
        reg_entry = CITATION_PROVENANCE_REGISTRY.get(reg_key) if reg_key else None

        if reg_entry is None:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_UNREGISTERED_CITATION,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Citation '{cit.path}:{cit.line}' is not registered in the trusted "
                        f"citation provenance registry; unverified provenance forces fail-closed"
                    ),
                )
            )
            has_error = True
        else:
            # Check for conflict between caller-supplied flags and trusted registry
            if cit.firmware is not None and normalize_firmware(cit.firmware) != normalize_firmware(reg_entry.firmware):
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_PROVENANCE_CONFLICT,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=(
                            f"Caller-supplied firmware {cit.firmware!r} conflicts with trusted registry "
                            f"firmware {reg_entry.firmware!r} for '{cit.path}:{cit.line}'"
                        ),
                    )
                )
                has_error = True

            if cit.is_historical is not None and cit.is_historical != reg_entry.is_historical:
                ob_findings.append(
                    ObligationFinding(
                        rule_id=RULE_PROVENANCE_CONFLICT,
                        obligation_id=oblig.id,
                        severity="ERROR",
                        message=(
                            f"Caller-supplied is_historical={cit.is_historical} conflicts with trusted "
                            f"registry is_historical={reg_entry.is_historical} for '{cit.path}:{cit.line}'"
                        ),
                    )
                )
                has_error = True

        # Determine effective historical and firmware identity from registry & caller flags
        # Unspecified provenance never defaults to GM1.10C; callers cannot bypass registry
        caller_is_hist = (
            cit.is_historical is True
            or not is_supported_firmware(cit.firmware)
        )
        registry_is_hist = (
            (reg_entry.is_historical if reg_entry else True)
            or not is_supported_firmware(reg_entry.firmware if reg_entry else None)
        )
        effective_is_historical = (
            caller_is_hist
            or registry_is_hist
            or (cit.path in HISTORICAL_ONLY_PATHS)
        )
        effective_firmware = reg_entry.firmware if reg_entry else (cit.firmware or "UNREGISTERED")

        if effective_is_historical and oblig.current_status == ObligationStatus.VERIFIED:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_HISTORICAL_CANNOT_VERIFY,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Historical or unsupported firmware citation '{cit.path}:{cit.line}' "
                        f"({effective_firmware!r}, is_historical={effective_is_historical}) "
                        f"cannot support VERIFIED status"
                    ),
                )
            )
            has_error = True

        # Check 1f: Pending PR evidence cannot be VERIFIED
        if oblig.pending_pr and oblig.current_status == ObligationStatus.VERIFIED:
            ob_findings.append(
                ObligationFinding(
                    rule_id=RULE_PENDING_PR_CANNOT_VERIFY,
                    obligation_id=oblig.id,
                    severity="ERROR",
                    message=(
                        f"Obligation cites evidence found only in unmerged {oblig.pending_pr}; "
                        f"cannot be VERIFIED"
                    ),
                )
            )
            has_error = True

    # 2. Obligation status categorization and readiness impact
    if oblig.current_status == ObligationStatus.UNKNOWN:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_STATUS_NOT_VERIFIED,
                obligation_id=oblig.id,
                severity="WARNING",
                message=f"Obligation is UNKNOWN: {oblig.statement[:80]}...",
            )
        )
        is_verified = False
    elif oblig.current_status == ObligationStatus.INFERRED:
        ob_findings.append(
            ObligationFinding(
                rule_id=RULE_STATUS_NOT_VERIFIED,
                obligation_id=oblig.id,
                severity="WARNING",
                message=f"Obligation is INFERRED: {oblig.statement[:80]}...",
            )
        )
        is_verified = False
    elif oblig.current_status == ObligationStatus.VERIFIED:
        is_verified = not has_error
    else:
        is_verified = False

    return (is_verified, ob_findings)


def evaluate_single_obligation(
    obligation: MemoryObligation,
    repo_root: Optional[Union[str, Path]] = None,
    file_reader: Optional[Callable[[Path], bytes]] = None,
) -> SingleObligationEvaluation:
    """Evaluate an individual obligation in isolation.

    NOTE: This returns whether the single obligation meets verification criteria.
    It NEVER sets or asserts overall readiness for the memory ownership model.
    """
    canonical_root = Path(__file__).resolve().parent.parent
    resolved_root = canonical_root if repo_root is None else Path(repo_root).resolve()
    is_verified, findings = _evaluate_obligation(
        oblig=obligation,
        resolved_root=resolved_root,
        active_pins=PINNED_ORIGIN_MAIN_FILE_HASHES,
        file_reader=file_reader,
    )
    return SingleObligationEvaluation(
        obligation_id=obligation.id,
        current_status=obligation.current_status,
        is_verified=is_verified,
        findings=tuple(findings),
    )


# -----------------------------------------------------------------------------
# Evaluation Engine
# -----------------------------------------------------------------------------

def evaluate(
    obligations: Optional[Sequence[MemoryObligation]] = None,
    repo_root: Optional[Union[str, Path]] = None,
    pinned_hashes: Optional[Dict[str, str]] = None,
    file_reader: Optional[Callable[[Path], bytes]] = None,
) -> EvaluationResult:
    """Evaluate memory ownership proof obligations against tracked repository evidence.

    This function is strictly fail-closed:
      - Overall readiness is False unless EVERY obligation in the canonical required set
        evaluates to VERIFIED with registered, non-historical, pinned origin/main evidence.
      - A missing obligation from REQUIRED_OBLIGATION_IDS forces False (RULE_INCOMPLETE_OBLIGATION_SET).
      - Duplicate obligation IDs force False (RULE_DUPLICATE_OBLIGATION_ID).
      - Unknown obligation IDs force False (RULE_UNKNOWN_OBLIGATION_ID).
      - Any non-production test hook (pinned_hashes override, custom file_reader, alternate repo_root)
        forces False (RULE_NON_PRODUCTION_EVIDENCE_CONFIG).
      - An unregistered citation forces False (RULE_UNREGISTERED_CITATION).
      - A citation flag conflicting with the provenance registry forces False (RULE_PROVENANCE_CONFLICT).
      - A missing cited file forces False (RULE_MISSING_CITED_PATH).
      - An unreadable cited file forces False (RULE_UNREADABLE_SOURCE).
      - An untracked or local-only source forces False (RULE_UNTRACKED_SOURCE).
      - An unpinned source forces False (RULE_UNPINNED_SOURCE).
      - A content digest mismatch against pinned origin/main forces False (RULE_CONTENT_HASH_MISMATCH).
      - An unacceptable source forces False (RULE_UNACCEPTABLE_SOURCE).
      - A historical-firmware-only (1.00C/1.10E) or non-GM1.10C source forces False (RULE_HISTORICAL_CANNOT_VERIFY).
      - An unmerged PR citation forces False (RULE_PENDING_PR_CANNOT_VERIFY).
      - An obligation status of UNKNOWN or INFERRED forces False (RULE_STATUS_NOT_VERIFIED).

    Returns:
        EvaluationResult containing aggregate readiness and individual findings.
    """
    if obligations is None:
        target_obligations = DEFAULT_MEMORY_OBLIGATIONS
    else:
        target_obligations = tuple(obligations)

    canonical_root = Path(__file__).resolve().parent.parent
    if repo_root is None:
        resolved_root = canonical_root
        is_alternate_root = False
    else:
        resolved_root = Path(repo_root).resolve()
        is_alternate_root = (resolved_root != canonical_root)

    findings: List[ObligationFinding] = []

    # Detect test hooks and enforce non-production rejection
    non_prod_hooks: List[str] = []
    if pinned_hashes is not None:
        non_prod_hooks.append("pinned_hashes override")
    if file_reader is not None:
        non_prod_hooks.append("custom file_reader")
    if is_alternate_root:
        non_prod_hooks.append("alternate repo_root")

    if non_prod_hooks:
        findings.append(
            ObligationFinding(
                rule_id=RULE_NON_PRODUCTION_EVIDENCE_CONFIG,
                obligation_id="GLOBAL",
                severity="ERROR",
                message=(
                    "Non-production evidence configuration active (test hooks in use: "
                    f"{', '.join(non_prod_hooks)}); evaluate() will never assert production readiness"
                ),
            )
        )

    active_pins = PINNED_ORIGIN_MAIN_FILE_HASHES if pinned_hashes is None else pinned_hashes

    if not target_obligations:
        findings.append(
            ObligationFinding(
                rule_id=RULE_EMPTY_DATASET,
                obligation_id="GLOBAL",
                severity="ERROR",
                message="No memory ownership proof obligations provided for evaluation",
            )
        )
        return EvaluationResult(
            is_ready=False,
            total_obligations=0,
            verified_count=0,
            inferred_count=0,
            unknown_count=0,
            error_count=len([f for f in findings if f.severity == "ERROR"]),
            warning_count=0,
            obligation_results={},
            findings=tuple(findings),
        )

    passed_ids = [ob.id for ob in target_obligations]
    passed_id_set = set(passed_ids)

    # Validate complete canonical set of obligations
    if len(passed_ids) != len(passed_id_set):
        seen = set()
        duplicates = set()
        for oid in passed_ids:
            if oid in seen:
                duplicates.add(oid)
            seen.add(oid)
        findings.append(
            ObligationFinding(
                rule_id=RULE_DUPLICATE_OBLIGATION_ID,
                obligation_id="GLOBAL",
                severity="ERROR",
                message=f"Duplicate obligation ID(s) supplied: {sorted(duplicates)}",
            )
        )

    unknown_ids = passed_id_set - REQUIRED_OBLIGATION_IDS
    if unknown_ids:
        findings.append(
            ObligationFinding(
                rule_id=RULE_UNKNOWN_OBLIGATION_ID,
                obligation_id="GLOBAL",
                severity="ERROR",
                message=f"Unknown obligation ID(s) supplied: {sorted(unknown_ids)}",
            )
        )

    missing_ids = REQUIRED_OBLIGATION_IDS - passed_id_set
    if missing_ids:
        findings.append(
            ObligationFinding(
                rule_id=RULE_INCOMPLETE_OBLIGATION_SET,
                obligation_id="GLOBAL",
                severity="ERROR",
                message=(
                    f"Obligation set is incomplete. Overall readiness requires all {len(REQUIRED_OBLIGATION_IDS)} "
                    f"canonical obligations. Missing {len(missing_ids)} obligation(s): {sorted(missing_ids)}"
                ),
            )
        )

    obligation_evals: Dict[str, SingleObligationEvaluation] = {}
    verified_count = 0
    inferred_count = 0
    unknown_count = 0

    for oblig in target_obligations:
        is_verified, ob_findings = _evaluate_obligation(
            oblig=oblig,
            resolved_root=resolved_root,
            active_pins=active_pins,
            file_reader=file_reader,
        )
        if oblig.current_status == ObligationStatus.UNKNOWN:
            unknown_count += 1
        elif oblig.current_status == ObligationStatus.INFERRED:
            inferred_count += 1
        elif oblig.current_status == ObligationStatus.VERIFIED and is_verified:
            verified_count += 1

        obligation_evals[oblig.id] = SingleObligationEvaluation(
            obligation_id=oblig.id,
            current_status=oblig.current_status,
            is_verified=is_verified,
            findings=tuple(ob_findings),
        )
        findings.extend(ob_findings)

    total = len(target_obligations)
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]

    is_complete_canonical_set = (
        passed_id_set == REQUIRED_OBLIGATION_IDS
        and len(passed_ids) == len(REQUIRED_OBLIGATION_IDS)
    )
    is_production_config = (len(non_prod_hooks) == 0)

    overall_ready = (
        is_complete_canonical_set
        and is_production_config
        and total == len(REQUIRED_OBLIGATION_IDS)
        and verified_count == len(REQUIRED_OBLIGATION_IDS)
        and len(errors) == 0
        and unknown_count == 0
        and inferred_count == 0
    )

    return EvaluationResult(
        is_ready=overall_ready,
        total_obligations=total,
        verified_count=verified_count,
        inferred_count=inferred_count,
        unknown_count=unknown_count,
        error_count=len(errors),
        warning_count=len(warnings),
        obligation_results=obligation_evals,
        findings=tuple(findings),
    )


# -----------------------------------------------------------------------------
# Address Integrity Verification Helper
# -----------------------------------------------------------------------------

HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{1,8}\b")


def verify_address_provenance(
    repo_root: Optional[Union[str, Path]] = None,
) -> Tuple[bool, List[str]]:
    """Verify that every address appearing in this module is registered in TRACKED_ADDRESS_CITATIONS

    and exists at the cited file:line in tracked origin/main documents.
    """
    if repo_root is None:
        resolved_root = Path(__file__).resolve().parent.parent
    else:
        resolved_root = Path(repo_root).resolve()

    errors: List[str] = []

    # 1. Verify every address cited in TRACKED_ADDRESS_CITATIONS exists at the cited file:line
    for addr_str, citation in TRACKED_ADDRESS_CITATIONS.items():
        doc_path = resolved_root / citation.document_ref
        if not doc_path.is_file():
            errors.append(
                f"Address {addr_str} cited document '{citation.document_ref}' does not exist on disk"
            )
            continue
        if citation.document_ref not in ORIGIN_MAIN_TRACKED_FILES:
            errors.append(
                f"Address {addr_str} cited document '{citation.document_ref}' is not on origin/main"
            )
            continue
        if citation.document_ref not in PINNED_ORIGIN_MAIN_FILE_HASHES:
            errors.append(
                f"Address {addr_str} cited document '{citation.document_ref}' is not pinned in PINNED_ORIGIN_MAIN_FILE_HASHES"
            )
            continue

        try:
            content_bytes = doc_path.read_bytes()
            doc_sha = hashlib.sha256(content_bytes).hexdigest()
            if doc_sha.lower() != PINNED_ORIGIN_MAIN_FILE_HASHES[citation.document_ref].lower():
                errors.append(
                    f"Address {addr_str} cited document '{citation.document_ref}' failed content authentication"
                )
                continue
            lines = content_bytes.decode("utf-8", errors="replace").splitlines()
            if citation.line < 1 or citation.line > len(lines):
                errors.append(
                    f"Address {addr_str} cited line {citation.line} out of range in {citation.document_ref}"
                )
                continue
            line_text = lines[citation.line - 1]
            if addr_str.lower() not in line_text.lower():
                errors.append(
                    f"Address {addr_str} not present at cited line {citation.document_ref}:{citation.line} "
                    f"('{line_text[:50]}...')"
                )
        except Exception as e:
            errors.append(f"Failed reading {citation.document_ref}: {e}")

    # 2. Verify all hex addresses appearing in DEFAULT_MEMORY_OBLIGATIONS statements/notes are registered
    for ob in DEFAULT_MEMORY_OBLIGATIONS:
        combined_text = f"{ob.statement} {ob.notes} " + " ".join(c.note for c in ob.citations)
        found_addrs = HEX_ADDR_RE.findall(combined_text)
        for raw_addr in found_addrs:
            # Normalize to 8 hex digits if in 32-bit address space
            norm_addr = f"0x{int(raw_addr, 16):08X}"
            if norm_addr not in TRACKED_ADDRESS_CITATIONS and raw_addr not in TRACKED_ADDRESS_CITATIONS:
                errors.append(
                    f"Obligation {ob.id} contains unregistered firmware address: {raw_addr} / {norm_addr}"
                )

    return (len(errors) == 0, errors)


# -----------------------------------------------------------------------------
# Main CLI
# -----------------------------------------------------------------------------

def main() -> int:
    """CLI entrypoint for standalone evaluation."""
    json_mode = "--json" in sys.argv
    res = evaluate()

    if json_mode:
        output_data = {
            "is_ready": res.is_ready,
            "total_obligations": res.total_obligations,
            "verified_count": res.verified_count,
            "inferred_count": res.inferred_count,
            "unknown_count": res.unknown_count,
            "error_count": res.error_count,
            "warning_count": res.warning_count,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "obligation_id": f.obligation_id,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in res.findings
            ],
        }
        print(json.dumps(output_data, indent=2))
    else:
        print(res.summary())

    # Exit code: fail-closed returns 1 if not ready, 0 if ready
    return 0 if res.is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
