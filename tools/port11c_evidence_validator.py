#!/usr/bin/env python3
"""PORT-11C: Offline evidence-validation utility for G3X Lite firmware research.

This tool enforces machine-readable evidence manifest schemas and validates:
  1. Duplicate evidence IDs.
  2. Malformed address ranges (inconsistent byte count, inverted start/end, non-hex).
  3. Classification validity (STATIC_VERIFIED, INFERRED, UNKNOWN).
  4. Provenance source authenticity and recognized categories.
  5. Missing authorization scope IDs.
  6. Evidence claims exceeding approved scope (address bounds, revision, quotas).
  7. Overlapping or inconsistent slices.
  8. Synthetic byte fixture integrity (exact byte count and SHA-256 matches).

Security and Scope Invariants:
  - MANIFEST-ONLY: Operates on JSON declarations and in-memory synthetic fixtures.
  - STRICTLY FORBIDDEN: Opening firmware/ROM dumps, scanning directories for ROMs,
    disassembling opcodes, subprocess calls, hardware access, or runtime modifications.
  - Standard library only (no external dependencies).

Usage:
  python3 -B tools/port11c_evidence_validator.py --manifest path/to/manifest.json
  python3 -B tools/port11c_evidence_validator.py --manifest path/to/manifest.json --json
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# -----------------------------------------------------------------------------
# Constants & Enums
# -----------------------------------------------------------------------------

MAX_MANIFEST_BYTES = 10 * 1024 * 1024  # 10 MiB limit to prevent memory exhaustion
FORBIDDEN_FILE_EXTENSIONS = {
    ".bin", ".rom", ".dump", ".fir", ".fi2", ".img", ".gpr", ".rep"
}

HEX_ADDRESS_PATTERN = re.compile(r"^(?:0x)?[0-9a-fA-F]{1,8}$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
RANGE_STR_PATTERN = re.compile(r"^(?:0x)?([0-9a-fA-F]{1,8})\.\.(?:0x)?([0-9a-fA-F]{1,8})$")


class Classification(str, Enum):
    """Evidence certainty classification."""
    STATIC_VERIFIED = "STATIC_VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, val: str) -> Classification:
        norm = val.strip().upper()
        for member in cls:
            if member.value == norm:
                return member
        raise ValueError(f"Invalid classification '{val}'. Allowed: {[m.value for m in cls]}")


class ProvenanceType(str, Enum):
    """Approved provenance source categories."""
    ROM_VERIFIED = "ROM_VERIFIED"
    SOURCE_REPO = "SOURCE_REPO"
    HISTORICAL_CHDK = "HISTORICAL_CHDK"
    HARDWARE_WITNESS = "HARDWARE_WITNESS"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"

    @classmethod
    def from_string(cls, val: str) -> ProvenanceType:
        norm = val.strip().upper()
        for member in cls:
            if member.value == norm:
                return member
        raise ValueError(f"Invalid provenance category '{val}'. Allowed: {[m.value for m in cls]}")


# Rule identifiers for auditing and reporting
RULE_SCHEMA_SYNTAX = "RULE_SCHEMA_SYNTAX"
RULE_DUPLICATE_ID = "RULE_DUPLICATE_ID"
RULE_MALFORMED_RANGE = "RULE_MALFORMED_RANGE"
RULE_INVALID_CLASSIFICATION = "RULE_INVALID_CLASSIFICATION"
RULE_UNSUPPORTED_PROVENANCE = "RULE_UNSUPPORTED_PROVENANCE"
RULE_MISSING_SCOPE = "RULE_MISSING_SCOPE"
RULE_UNAPPROVED_SCOPE = "RULE_UNAPPROVED_SCOPE"
RULE_SCOPE_EXCEEDED = "RULE_SCOPE_EXCEEDED"
RULE_SCOPE_POLICY_VIOLATION = "RULE_SCOPE_POLICY_VIOLATION"
RULE_TRUST_BOUNDARY_NOTICE = "RULE_TRUST_BOUNDARY_NOTICE"
RULE_OVERLAPPING_SLICES = "RULE_OVERLAPPING_SLICES"
RULE_INCONSISTENT_SLICES = "RULE_INCONSISTENT_SLICES"
RULE_FIXTURE_LENGTH_MISMATCH = "RULE_FIXTURE_LENGTH_MISMATCH"
RULE_FIXTURE_HASH_MISMATCH = "RULE_FIXTURE_HASH_MISMATCH"


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

def parse_address_int(val: Union[int, str], field_name: str = "address") -> int:
    """Parse integer or hex string address safely into a 32-bit unsigned int."""
    if isinstance(val, int):
        if val < 0 or val > 0xFFFFFFFF:
            raise ValueError(f"{field_name} integer 0x{val:X} out of 32-bit range (0..0xFFFFFFFF)")
        return val
    if isinstance(val, str):
        v = val.strip()
        if not HEX_ADDRESS_PATTERN.match(v):
            raise ValueError(f"Malformed {field_name} string '{val}'; must be hex string (e.g. 0xFC020040)")
        addr = int(v, 16)
        if addr < 0 or addr > 0xFFFFFFFF:
            raise ValueError(f"{field_name} 0x{addr:X} out of 32-bit range (0..0xFFFFFFFF)")
        return addr
    raise ValueError(f"{field_name} must be integer or hex string, got {type(val).__name__}")


@dataclass(frozen=True)
class ApprovedRange:
    """An approved address range authorized for inspection/evidence."""
    start_address: int
    end_address: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.start_address > self.end_address:
            raise ValueError(
                f"ApprovedRange start (0x{self.start_address:08X}) > end (0x{self.end_address:08X})"
            )

    @property
    def byte_count(self) -> int:
        return self.end_address - self.start_address + 1

    def contains(self, start: int, end: int) -> bool:
        """Check if [start, end] is completely contained within this approved range."""
        return self.start_address <= start and end <= self.end_address

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ApprovedRange:
        start = parse_address_int(data.get("start_address", 0), "start_address")
        end = parse_address_int(data.get("end_address", 0), "end_address")
        label = str(data.get("label", ""))
        return cls(start_address=start, end_address=end, label=label)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_address": f"0x{self.start_address:08X}",
            "end_address": f"0x{self.end_address:08X}",
            "byte_count": self.byte_count,
            "label": self.label,
        }


@dataclass(frozen=True)
class AuthorizationScope:
    """Authorization scope defining boundaries for research claims."""
    scope_id: str
    firmware_revision: str
    approved_ranges: List[ApprovedRange]
    max_bytes_total: Optional[int] = None
    allowed_classifications: Set[Classification] = field(
        default_factory=lambda: {
            Classification.STATIC_VERIFIED,
            Classification.INFERRED,
            Classification.UNKNOWN,
        }
    )
    description: str = ""

    def authorizes_range(self, start: int, end: int) -> bool:
        """Check if [start, end] is fully authorized by at least one approved range."""
        return any(ar.contains(start, end) for ar in self.approved_ranges)

    def authorizes_classification(self, cls: Classification) -> bool:
        return cls in self.allowed_classifications

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuthorizationScope:
        scope_id = str(data.get("scope_id", "")).strip()
        if not scope_id:
            raise ValueError("AuthorizationScope missing required 'scope_id'")
        fw_rev = str(data.get("firmware_revision", "")).strip()
        if not fw_rev:
            raise ValueError(f"AuthorizationScope '{scope_id}' missing 'firmware_revision'")

        raw_ranges = data.get("approved_ranges", [])
        if not isinstance(raw_ranges, list):
            raise ValueError(f"AuthorizationScope '{scope_id}' 'approved_ranges' must be a list")
        approved_ranges = [ApprovedRange.from_dict(r) for r in raw_ranges]

        max_bytes = data.get("max_bytes_total")
        if max_bytes is not None:
            max_bytes = int(max_bytes)
            if max_bytes <= 0:
                raise ValueError(f"Scope '{scope_id}' max_bytes_total must be positive")

        allowed_cls_raw = data.get("allowed_classifications")
        if allowed_cls_raw is not None:
            allowed_cls = {Classification.from_string(c) for c in allowed_cls_raw}
        else:
            allowed_cls = {
                Classification.STATIC_VERIFIED,
                Classification.INFERRED,
                Classification.UNKNOWN,
            }

        desc = str(data.get("description", ""))
        return cls(
            scope_id=scope_id,
            firmware_revision=fw_rev,
            approved_ranges=approved_ranges,
            max_bytes_total=max_bytes,
            allowed_classifications=allowed_cls,
            description=desc,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "firmware_revision": self.firmware_revision,
            "approved_ranges": [r.to_dict() for r in self.approved_ranges],
            "max_bytes_total": self.max_bytes_total,
            "allowed_classifications": [c.value for c in sorted(self.allowed_classifications)],
            "description": self.description,
        }


@dataclass(frozen=True)
class ProvenanceSource:
    """Provenance origin and reference for an evidence claim."""
    provenance_type: ProvenanceType
    reference: str
    detail: Optional[Dict[str, Any]] = None

    @classmethod
    def parse(cls, raw: Any) -> ProvenanceSource:
        """Parse structured dict or formatted string into ProvenanceSource."""
        if isinstance(raw, dict):
            ptype_raw = raw.get("type")
            if not ptype_raw:
                raise ValueError("Provenance dict missing 'type' key")
            ptype = ProvenanceType.from_string(str(ptype_raw))
            ref = str(raw.get("reference", raw.get("document_ref", ""))).strip()
            if not ref:
                raise ValueError(f"Provenance dict of type '{ptype.value}' missing reference")
            detail = {k: v for k, v in raw.items() if k not in ("type", "reference", "document_ref")}
            return cls(provenance_type=ptype, reference=ref, detail=detail if detail else None)

        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                raise ValueError("Provenance string cannot be empty")
            if ":" in s:
                prefix, rest = s.split(":", 1)
                prefix_clean = prefix.strip().upper()
                try:
                    ptype = ProvenanceType.from_string(prefix_clean)
                    return cls(provenance_type=ptype, reference=rest.strip())
                except ValueError:
                    pass
            # Check for recognized substrings/paths
            if "PRIMARY.BIN" in s or "ROM" in s.upper():
                return cls(provenance_type=ProvenanceType.ROM_VERIFIED, reference=s)
            if s.startswith("docs/") or s.startswith("platform/") or s.startswith("tools/"):
                return cls(provenance_type=ProvenanceType.SOURCE_REPO, reference=s)
            if "patch" in s or "r5480" in s or "r5491" in s or "CHDK" in s:
                return cls(provenance_type=ProvenanceType.HISTORICAL_CHDK, reference=s)
            if "HARDWARE" in s.upper() or "BOOT-001" in s or "UI-001" in s:
                return cls(provenance_type=ProvenanceType.HARDWARE_WITNESS, reference=s)
            if s.startswith("synthetic:") or "fixture" in s.lower():
                return cls(provenance_type=ProvenanceType.SYNTHETIC_FIXTURE, reference=s)

            raise ValueError(
                f"Unsupported provenance string '{raw}'. Must specify recognized category "
                f"({[p.value for p in ProvenanceType]}) as prefix (e.g. 'ROM_VERIFIED:...') "
                f"or known repo path."
            )

        raise ValueError(f"Provenance must be string or dict, got {type(raw).__name__}")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "type": self.provenance_type.value,
            "reference": self.reference,
        }
        if self.detail:
            res.update(self.detail)
        return res


@dataclass(frozen=True)
class EvidenceEntry:
    """A single machine-readable evidence claim."""
    evidence_id: str
    firmware_revision: str
    start_address: int
    end_address: int
    expected_byte_count: int
    sha256: str
    provenance: ProvenanceSource
    authorization_scope_id: str
    classification: Classification
    notes: str = ""

    @property
    def start_hex(self) -> str:
        return f"0x{self.start_address:08X}"

    @property
    def end_hex(self) -> str:
        return f"0x{self.end_address:08X}"

    @property
    def range_str(self) -> str:
        return f"{self.start_hex}..{self.end_hex}"

    def overlaps(self, other: EvidenceEntry) -> bool:
        """Check if this entry overlaps with another entry in the same firmware revision."""
        if self.firmware_revision != other.firmware_revision:
            return False
        return not (self.end_address < other.start_address or self.start_address > other.end_address)

    def intersection(self, other: EvidenceEntry) -> Optional[Tuple[int, int]]:
        """Return the inclusive address range of overlap, if any."""
        if not self.overlaps(other):
            return None
        start = max(self.start_address, other.start_address)
        end = min(self.end_address, other.end_address)
        return (start, end)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceEntry:
        eid = str(data.get("evidence_id", "")).strip()
        if not eid:
            raise ValueError("EvidenceEntry missing 'evidence_id'")

        fw_rev = str(data.get("firmware_revision", "")).strip()
        if not fw_rev:
            raise ValueError(f"EvidenceEntry '{eid}' missing 'firmware_revision'")

        # Parse range from explicit start/end or range string
        range_str = data.get("address_range")
        if range_str and isinstance(range_str, str):
            m = RANGE_STR_PATTERN.match(range_str.strip())
            if not m:
                raise ValueError(f"EvidenceEntry '{eid}' address_range malformed: '{range_str}'")
            start = int(m.group(1), 16)
            end = int(m.group(2), 16)
        else:
            if "start_address" not in data or "end_address" not in data:
                raise ValueError(f"EvidenceEntry '{eid}' missing start_address / end_address")
            start = parse_address_int(data["start_address"], "start_address")
            end = parse_address_int(data["end_address"], "end_address")

        if "expected_byte_count" not in data:
            raise ValueError(f"EvidenceEntry '{eid}' missing 'expected_byte_count'")
        byte_count = int(data["expected_byte_count"])

        sha = str(data.get("sha256", "")).strip().lower()
        if not SHA256_HEX_PATTERN.match(sha):
            raise ValueError(
                f"EvidenceEntry '{eid}' sha256 '{sha}' is not a valid 64-character hex string"
            )

        prov_raw = data.get("provenance_source", data.get("provenance"))
        if prov_raw is None:
            raise ValueError(f"EvidenceEntry '{eid}' missing 'provenance_source'")
        prov = ProvenanceSource.parse(prov_raw)

        scope_id = str(data.get("authorization_scope_id", data.get("scope_id", ""))).strip()
        if not scope_id:
            raise ValueError(f"EvidenceEntry '{eid}' missing 'authorization_scope_id'")

        cls_raw = data.get("classification")
        if not cls_raw:
            raise ValueError(f"EvidenceEntry '{eid}' missing 'classification'")
        classification = Classification.from_string(str(cls_raw))

        notes = str(data.get("notes", ""))
        return cls(
            evidence_id=eid,
            firmware_revision=fw_rev,
            start_address=start,
            end_address=end,
            expected_byte_count=byte_count,
            sha256=sha,
            provenance=prov,
            authorization_scope_id=scope_id,
            classification=classification,
            notes=notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "firmware_revision": self.firmware_revision,
            "start_address": self.start_hex,
            "end_address": self.end_hex,
            "address_range": self.range_str,
            "expected_byte_count": self.expected_byte_count,
            "sha256": self.sha256,
            "provenance_source": self.provenance.to_dict(),
            "authorization_scope_id": self.authorization_scope_id,
            "classification": self.classification.value,
            "notes": self.notes,
        }


@dataclass
class EvidenceManifest:
    """Top-level evidence manifest holding scopes and evidence entries."""
    manifest_version: str
    scopes: Dict[str, AuthorizationScope]
    entries: List[EvidenceEntry]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceManifest:
        version = str(data.get("manifest_version", "1.0.0")).strip()
        raw_scopes = data.get("authorization_scopes", [])
        scopes_dict: Dict[str, AuthorizationScope] = {}

        if isinstance(raw_scopes, list):
            for s_data in raw_scopes:
                scope = AuthorizationScope.from_dict(s_data)
                scopes_dict[scope.scope_id] = scope
        elif isinstance(raw_scopes, dict):
            for sid, s_data in raw_scopes.items():
                if "scope_id" not in s_data:
                    s_data = dict(s_data)
                    s_data["scope_id"] = sid
                scope = AuthorizationScope.from_dict(s_data)
                scopes_dict[scope.scope_id] = scope
        else:
            raise ValueError("authorization_scopes must be a list or dict")

        raw_entries = data.get("evidence_entries", [])
        if not isinstance(raw_entries, list):
            raise ValueError("evidence_entries must be a list")

        entries: List[EvidenceEntry] = []
        for e_data in raw_entries:
            entries.append(EvidenceEntry.from_dict(e_data))

        return cls(manifest_version=version, scopes=scopes_dict, entries=entries)

    @classmethod
    def from_json(cls, json_str: str) -> EvidenceManifest:
        if len(json_str) > MAX_MANIFEST_BYTES:
            raise ValueError(f"JSON input exceeds maximum allowed size ({MAX_MANIFEST_BYTES} B)")
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Manifest root must be a JSON object")
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "authorization_scopes": [s.to_dict() for s in self.scopes.values()],
            "evidence_entries": [e.to_dict() for e in self.entries],
        }


# -----------------------------------------------------------------------------
# Validation Results & Engine
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationFinding:
    """A single validation finding or diagnostic."""
    rule_id: str
    severity: str  # "ERROR", "WARNING", "INFO"
    evidence_id: Optional[str]
    message: str
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
        }
        if self.evidence_id:
            d["evidence_id"] = self.evidence_id
        if self.context:
            d["context"] = self.context
        return d


@dataclass
class ValidationResult:
    """Complete summary of a validation run."""
    findings: List[ValidationFinding] = field(default_factory=list)
    trust_level: str = "SELF_DECLARED_INTERNAL_ONLY"
    evidence_verification_boundary: str = (
        "OFFLINE_DECLARATIONS_AND_SYNTHETIC_FIXTURES_ONLY "
        "(ROM binary bytes not accessed or authenticated by this tool; "
        "external policy consistency != owner approval; authority remains UNVERIFIED without out-of-band record)"
    )
    rom_permission_granted: bool = False
    rom_permission_disclaimer: str = (
        "NON-AUTHORITY INVARIANT: This tool validates offline declarations and synthetic test fixtures only; "
        "it possesses NO authority to grant ROM-reading, firmware dumping, or camera execution permission. "
        "Providing an external policy file does NOT authenticate its creator or independent owner approval. "
        "rom_permission_granted remains permanently False."
    )

    @property
    def is_valid(self) -> bool:
        return not any(f.severity == "ERROR" for f in self.findings)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "WARNING")

    def add_error(
        self,
        rule_id: str,
        message: str,
        evidence_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.findings.append(
            ValidationFinding(
                rule_id=rule_id,
                severity="ERROR",
                evidence_id=evidence_id,
                message=message,
                context=context,
            )
        )

    def add_warning(
        self,
        rule_id: str,
        message: str,
        evidence_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.findings.append(
            ValidationFinding(
                rule_id=rule_id,
                severity="WARNING",
                evidence_id=evidence_id,
                message=message,
                context=context,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "trust_level": self.trust_level,
            "evidence_verification_boundary": self.evidence_verification_boundary,
            "rom_permission_granted": self.rom_permission_granted,
            "rom_permission_disclaimer": self.rom_permission_disclaimer,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "findings": [f.to_dict() for f in self.findings],
        }


class EvidenceValidator:
    """Auditable evidence validator enforcing bounds, scopes, and consistency."""

    def __init__(
        self,
        allow_overlapping_slices: bool = False,
        require_provenance: bool = True,
    ) -> None:
        self.allow_overlapping_slices = allow_overlapping_slices
        self.require_provenance = require_provenance

    def validate_manifest(
        self,
        manifest: EvidenceManifest,
        fixtures: Optional[Dict[str, bytes]] = None,
        trusted_scopes: Optional[Dict[str, AuthorizationScope]] = None,
    ) -> ValidationResult:
        """Run all validation rules against an EvidenceManifest.

        If trusted_scopes is provided, it serves as the authoritative trusted policy,
        and any manifest-declared scopes are checked against it.
        If trusted_scopes is None, validation proceeds in self-declared internal-consistency
        mode and emits RULE_TRUST_BOUNDARY_NOTICE.
        """
        result = ValidationResult()

        # Authorization Trust Boundary Evaluation
        effective_scopes: Dict[str, AuthorizationScope] = {}
        if trusted_scopes is not None:
            result.trust_level = "EXTERNAL_POLICY_CONSISTENCY_CHECKED"
            effective_scopes = trusted_scopes
            # Validate that manifest does not declare scopes exceeding or contradicting trusted policy
            self._check_scope_policy_compliance(manifest.scopes, trusted_scopes, result)
        else:
            result.trust_level = "SELF_DECLARED_INTERNAL_ONLY"
            effective_scopes = manifest.scopes
            result.add_warning(
                rule_id=RULE_TRUST_BOUNDARY_NOTICE,
                message=(
                    "Manifest validated against self-declared scopes only (internal consistency mode). "
                    "Manifest-declared scopes do NOT constitute actual human authorization to inspect "
                    "or access ROM. Supply --trusted-scopes to verify consistency against external policy. "
                    "External policy consistency != owner approval; authority remains UNVERIFIED without out-of-band record."
                ),
            )

        # 1. Duplicate ID validation
        self._check_duplicate_ids(manifest.entries, result)

        # 2. Malformed range validation
        self._check_ranges(manifest.entries, result)

        # 3. Provenance validation
        if self.require_provenance:
            self._check_provenance(manifest.entries, result)

        # 4. Authorization scope validation & scope bound enforcement
        self._check_authorization_scopes(effective_scopes, manifest.entries, result)

        # 5. Overlap and consistency validation
        self._check_overlaps_and_consistency(manifest.entries, fixtures, result)

        # 6. Synthetic byte fixture validation (if supplied)
        if fixtures:
            self._check_fixtures(manifest.entries, fixtures, result)

        return result

    def _check_scope_policy_compliance(
        self,
        manifest_scopes: Dict[str, AuthorizationScope],
        trusted_scopes: Dict[str, AuthorizationScope],
        result: ValidationResult,
    ) -> None:
        """Verify that manifest does not self-declare scopes that violate or expand trusted policy."""
        for sid, m_scope in manifest_scopes.items():
            if sid not in trusted_scopes:
                result.add_error(
                    rule_id=RULE_SCOPE_POLICY_VIOLATION,
                    message=(
                        f"Manifest declares scope '{sid}' that is not authorized in the "
                        f"trusted policy ({list(trusted_scopes.keys())})"
                    ),
                    context={"unauthorized_scope": sid},
                )
                continue

            t_scope = trusted_scopes[sid]
            if m_scope.firmware_revision != t_scope.firmware_revision:
                result.add_error(
                    rule_id=RULE_SCOPE_POLICY_VIOLATION,
                    message=(
                        f"Manifest scope '{sid}' targets firmware '{m_scope.firmware_revision}', "
                        f"contradicting trusted policy revision '{t_scope.firmware_revision}'"
                    ),
                    context={"manifest_fw": m_scope.firmware_revision, "trusted_fw": t_scope.firmware_revision},
                )

            for r in m_scope.approved_ranges:
                if not t_scope.authorizes_range(r.start_address, r.end_address):
                    result.add_error(
                        rule_id=RULE_SCOPE_POLICY_VIOLATION,
                        message=(
                            f"Manifest scope '{sid}' attempts to claim unapproved range "
                            f"0x{r.start_address:08X}..0x{r.end_address:08X} not authorized in trusted policy"
                        ),
                    )

            if t_scope.max_bytes_total is not None:
                if m_scope.max_bytes_total is None or m_scope.max_bytes_total > t_scope.max_bytes_total:
                    result.add_error(
                        rule_id=RULE_SCOPE_POLICY_VIOLATION,
                        message=(
                            f"Manifest scope '{sid}' max_bytes_total ({m_scope.max_bytes_total}) "
                            f"exceeds trusted policy quota ({t_scope.max_bytes_total})"
                        ),
                    )

    def _check_duplicate_ids(
        self,
        entries: List[EvidenceEntry],
        result: ValidationResult,
    ) -> None:
        seen_ids: Dict[str, int] = {}
        for entry in entries:
            seen_ids[entry.evidence_id] = seen_ids.get(entry.evidence_id, 0) + 1

        for eid, count in seen_ids.items():
            if count > 1:
                result.add_error(
                    rule_id=RULE_DUPLICATE_ID,
                    message=f"Duplicate evidence ID '{eid}' occurs {count} times",
                    evidence_id=eid,
                    context={"occurrences": count},
                )

    def _check_ranges(
        self,
        entries: List[EvidenceEntry],
        result: ValidationResult,
    ) -> None:
        for entry in entries:
            # Check inverted range
            if entry.start_address > entry.end_address:
                result.add_error(
                    rule_id=RULE_MALFORMED_RANGE,
                    message=(
                        f"Start address {entry.start_hex} is greater than "
                        f"end address {entry.end_hex}"
                    ),
                    evidence_id=entry.evidence_id,
                    context={"start": entry.start_hex, "end": entry.end_hex},
                )

            # Check byte count calculation: end - start + 1
            calculated_count = entry.end_address - entry.start_address + 1
            if calculated_count != entry.expected_byte_count:
                result.add_error(
                    rule_id=RULE_MALFORMED_RANGE,
                    message=(
                        f"Expected byte count ({entry.expected_byte_count}) does not match "
                        f"address range span ({calculated_count} bytes, {entry.range_str})"
                    ),
                    evidence_id=entry.evidence_id,
                    context={
                        "expected_byte_count": entry.expected_byte_count,
                        "span_bytes": calculated_count,
                        "range": entry.range_str,
                    },
                )

            # Check positive byte count
            if entry.expected_byte_count <= 0:
                result.add_error(
                    rule_id=RULE_MALFORMED_RANGE,
                    message=f"Expected byte count must be positive, got {entry.expected_byte_count}",
                    evidence_id=entry.evidence_id,
                )

    def _check_provenance(
        self,
        entries: List[EvidenceEntry],
        result: ValidationResult,
    ) -> None:
        for entry in entries:
            prov = entry.provenance
            if not prov.reference.strip():
                result.add_error(
                    rule_id=RULE_UNSUPPORTED_PROVENANCE,
                    message=f"Evidence provenance reference is empty for '{entry.evidence_id}'",
                    evidence_id=entry.evidence_id,
                )

    def _check_authorization_scopes(
        self,
        scopes: Dict[str, AuthorizationScope],
        entries: List[EvidenceEntry],
        result: ValidationResult,
    ) -> None:
        scope_byte_totals: Dict[str, int] = {sid: 0 for sid in scopes}

        for entry in entries:
            sid = entry.authorization_scope_id
            if not sid:
                result.add_error(
                    rule_id=RULE_MISSING_SCOPE,
                    message=f"Evidence entry '{entry.evidence_id}' is missing authorization_scope_id",
                    evidence_id=entry.evidence_id,
                )
                continue

            if sid not in scopes:
                result.add_error(
                    rule_id=RULE_UNAPPROVED_SCOPE,
                    message=(
                        f"Evidence entry '{entry.evidence_id}' references unknown or unapproved "
                        f"authorization scope '{sid}'"
                    ),
                    evidence_id=entry.evidence_id,
                    context={"referenced_scope": sid, "available_scopes": list(scopes.keys())},
                )
                continue

            scope = scopes[sid]

            # Check firmware revision alignment
            if entry.firmware_revision != scope.firmware_revision:
                result.add_error(
                    rule_id=RULE_SCOPE_EXCEEDED,
                    message=(
                        f"Evidence firmware revision '{entry.firmware_revision}' does not match "
                        f"scope '{sid}' authorized revision '{scope.firmware_revision}'"
                    ),
                    evidence_id=entry.evidence_id,
                    context={
                        "entry_fw": entry.firmware_revision,
                        "scope_fw": scope.firmware_revision,
                    },
                )

            # Check classification allowed
            if not scope.authorizes_classification(entry.classification):
                result.add_error(
                    rule_id=RULE_SCOPE_EXCEEDED,
                    message=(
                        f"Evidence classification '{entry.classification.value}' is not permitted "
                        f"under scope '{sid}'"
                    ),
                    evidence_id=entry.evidence_id,
                    context={
                        "entry_classification": entry.classification.value,
                        "allowed": [c.value for c in sorted(scope.allowed_classifications)],
                    },
                )

            # Check address bounds
            if not scope.authorizes_range(entry.start_address, entry.end_address):
                result.add_error(
                    rule_id=RULE_SCOPE_EXCEEDED,
                    message=(
                        f"Evidence range {entry.range_str} ({entry.expected_byte_count} B) exceeds "
                        f"approved ranges for scope '{sid}'"
                    ),
                    evidence_id=entry.evidence_id,
                    context={
                        "range": entry.range_str,
                        "approved_ranges": [r.to_dict() for r in scope.approved_ranges],
                    },
                )

            scope_byte_totals[sid] += entry.expected_byte_count

        # Check total byte quota per scope
        for sid, total_bytes in scope_byte_totals.items():
            scope = scopes[sid]
            if scope.max_bytes_total is not None and total_bytes > scope.max_bytes_total:
                result.add_error(
                    rule_id=RULE_SCOPE_EXCEEDED,
                    message=(
                        f"Total evidence bytes ({total_bytes} B) under scope '{sid}' exceeds "
                        f"approved maximum quota ({scope.max_bytes_total} B)"
                    ),
                    context={"scope_id": sid, "total_bytes": total_bytes, "max": scope.max_bytes_total},
                )

    def _check_overlaps_and_consistency(
        self,
        entries: List[EvidenceEntry],
        fixtures: Optional[Dict[str, bytes]],
        result: ValidationResult,
    ) -> None:
        n = len(entries)
        for i in range(n):
            e1 = entries[i]
            for j in range(i + 1, n):
                e2 = entries[j]
                if not e1.overlaps(e2):
                    continue

                inter = e1.intersection(e2)
                assert inter is not None
                inter_start, inter_end = inter
                inter_len = inter_end - inter_start + 1

                # Check if identical address range has conflicting claims
                if e1.start_address == e2.start_address and e1.end_address == e2.end_address:
                    if e1.sha256 != e2.sha256:
                        result.add_error(
                            rule_id=RULE_INCONSISTENT_SLICES,
                            message=(
                                f"Inconsistent SHA-256 for identical range {e1.range_str} between "
                                f"'{e1.evidence_id}' ({e1.sha256}) and '{e2.evidence_id}' ({e2.sha256})"
                            ),
                            evidence_id=e1.evidence_id,
                            context={"conflicting_id": e2.evidence_id, "range": e1.range_str},
                        )
                    if e1.classification != e2.classification:
                        result.add_error(
                            rule_id=RULE_INCONSISTENT_SLICES,
                            message=(
                                f"Inconsistent classification for identical range {e1.range_str} between "
                                f"'{e1.evidence_id}' ({e1.classification.value}) and "
                                f"'{e2.evidence_id}' ({e2.classification.value})"
                            ),
                            evidence_id=e1.evidence_id,
                            context={"conflicting_id": e2.evidence_id, "range": e1.range_str},
                        )

                # If overlapping slices are forbidden by policy
                if not self.allow_overlapping_slices:
                    result.add_error(
                        rule_id=RULE_OVERLAPPING_SLICES,
                        message=(
                            f"Evidence slices '{e1.evidence_id}' ({e1.range_str}) and "
                            f"'{e2.evidence_id}' ({e2.range_str}) overlap by {inter_len} bytes "
                            f"(0x{inter_start:08X}..0x{inter_end:08X})"
                        ),
                        evidence_id=e1.evidence_id,
                        context={
                            "conflicting_id": e2.evidence_id,
                            "intersection": f"0x{inter_start:08X}..0x{inter_end:08X}",
                            "intersection_bytes": inter_len,
                        },
                    )

                # Check synthetic fixture byte consistency in intersection
                if fixtures and e1.evidence_id in fixtures and e2.evidence_id in fixtures:
                    f1 = fixtures[e1.evidence_id]
                    f2 = fixtures[e2.evidence_id]
                    if len(f1) == e1.expected_byte_count and len(f2) == e2.expected_byte_count:
                        offset1 = inter_start - e1.start_address
                        offset2 = inter_start - e2.start_address
                        sub1 = f1[offset1 : offset1 + inter_len]
                        sub2 = f2[offset2 : offset2 + inter_len]
                        if sub1 != sub2:
                            result.add_error(
                                rule_id=RULE_INCONSISTENT_SLICES,
                                message=(
                                    f"Conflicting byte data in overlapping range 0x{inter_start:08X}.."
                                    f"0x{inter_end:08X} between fixtures for '{e1.evidence_id}' and '{e2.evidence_id}'"
                                ),
                                evidence_id=e1.evidence_id,
                                context={"conflicting_id": e2.evidence_id},
                            )

    def _check_fixtures(
        self,
        entries: List[EvidenceEntry],
        fixtures: Dict[str, bytes],
        result: ValidationResult,
    ) -> None:
        for entry in entries:
            if entry.evidence_id not in fixtures:
                continue

            fix_bytes = fixtures[entry.evidence_id]
            if not isinstance(fix_bytes, (bytes, bytearray)):
                result.add_error(
                    rule_id=RULE_FIXTURE_LENGTH_MISMATCH,
                    message=f"Fixture for '{entry.evidence_id}' must be bytes, got {type(fix_bytes).__name__}",
                    evidence_id=entry.evidence_id,
                )
                continue

            if len(fix_bytes) != entry.expected_byte_count:
                result.add_error(
                    rule_id=RULE_FIXTURE_LENGTH_MISMATCH,
                    message=(
                        f"Synthetic fixture byte count ({len(fix_bytes)}) does not match "
                        f"manifest expected byte count ({entry.expected_byte_count})"
                    ),
                    evidence_id=entry.evidence_id,
                    context={"actual_len": len(fix_bytes), "expected_len": entry.expected_byte_count},
                )
                continue

            calc_sha = hashlib.sha256(fix_bytes).hexdigest().lower()
            if calc_sha != entry.sha256.lower():
                result.add_error(
                    rule_id=RULE_FIXTURE_HASH_MISMATCH,
                    message=(
                        f"Synthetic fixture SHA-256 ({calc_sha}) does not match "
                        f"manifest SHA-256 ({entry.sha256})"
                    ),
                    evidence_id=entry.evidence_id,
                    context={"actual_sha": calc_sha, "expected_sha": entry.sha256},
                )


# -----------------------------------------------------------------------------
# Fail-Closed File Loader & CLI
# -----------------------------------------------------------------------------

def load_manifest_file(file_path: Union[str, Path]) -> Tuple[Optional[EvidenceManifest], Optional[str]]:
    """Safely load and parse manifest JSON file, rejecting forbidden binary files."""
    p = Path(file_path).resolve()

    # Security check: never open binary dumps
    name_lower = p.name.lower()
    if p.suffix.lower() in FORBIDDEN_FILE_EXTENSIONS or "primary" in name_lower or "rom" in name_lower:
        return None, f"Security Violation: Refusing to open forbidden binary/ROM file '{p.name}'"

    if not p.is_file():
        return None, f"Manifest file not found: {p}"

    try:
        size = p.stat().st_size
        if size > MAX_MANIFEST_BYTES:
            return None, f"Manifest file size ({size} B) exceeds maximum limit ({MAX_MANIFEST_BYTES} B)"
        content = p.read_text(encoding="utf-8")
        manifest = EvidenceManifest.from_json(content)
        return manifest, None
    except json.JSONDecodeError as e:
        return None, f"JSON syntax error in manifest: {e}"
    except Exception as e:
        return None, f"Manifest schema error: {e}"


def load_scopes_file(file_path: Union[str, Path]) -> Tuple[Optional[Dict[str, AuthorizationScope]], Optional[str]]:
    """Load an external authorization scopes JSON file."""
    p = Path(file_path).resolve()
    name_lower = p.name.lower()
    if p.suffix.lower() in FORBIDDEN_FILE_EXTENSIONS or "primary" in name_lower or "rom" in name_lower:
        return None, f"Security Violation: Refusing to open forbidden binary file '{p.name}'"

    if not p.is_file():
        return None, f"Scopes file not found: {p}"

    try:
        size = p.stat().st_size
        if size > MAX_MANIFEST_BYTES:
            return None, f"Scopes file size ({size} B) exceeds maximum limit ({MAX_MANIFEST_BYTES} B)"
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, (dict, list)):
            return None, "Error parsing authorization scopes: Root JSON must be an object or list"
        scopes_list: List[Dict[str, Any]] = []
        if isinstance(data, list):
            scopes_list = data
        elif isinstance(data, dict):
            raw_scopes = data.get("authorization_scopes", [])
            if not isinstance(raw_scopes, list):
                return None, "Error parsing authorization scopes: 'authorization_scopes' must be a list"
            scopes_list = raw_scopes
            if not scopes_list and "scope_id" in data:
                scopes_list = [data]
        res: Dict[str, AuthorizationScope] = {}
        for s_data in scopes_list:
            if not isinstance(s_data, dict):
                return None, "Error parsing authorization scopes: Scope entry must be a dictionary"
            scope = AuthorizationScope.from_dict(s_data)
            res[scope.scope_id] = scope
        return res, None
    except json.JSONDecodeError as e:
        return None, f"JSON syntax error in scopes file: {e}"
    except Exception as e:
        return None, f"Error parsing authorization scopes: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PORT-11C: Offline evidence manifest validator for G3X Lite firmware research."
    )
    parser.add_argument("--manifest", required=True, help="Path to evidence manifest JSON")
    parser.add_argument(
        "--trusted-scopes",
        "--scopes",
        dest="trusted_scopes",
        help="Path to external authorization scopes policy JSON for consistency check (does NOT authenticate owner approval)",
    )
    parser.add_argument(
        "--allow-overlap",
        action="store_true",
        help="Allow overlapping evidence slices if byte data and metadata are consistent",
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")

    args = parser.parse_args()

    manifest, err = load_manifest_file(args.manifest)
    if err:
        if args.json:
            print(json.dumps({"is_valid": False, "error": err}))
        else:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2

    assert manifest is not None

    trusted_scopes_map: Optional[Dict[str, AuthorizationScope]] = None
    if args.trusted_scopes:
        ext_scopes, s_err = load_scopes_file(args.trusted_scopes)
        if s_err:
            if args.json:
                print(json.dumps({"is_valid": False, "error": s_err}))
            else:
                print(f"ERROR: {s_err}", file=sys.stderr)
            return 2
        assert ext_scopes is not None
        trusted_scopes_map = ext_scopes

    validator = EvidenceValidator(allow_overlapping_slices=args.allow_overlap)
    result = validator.validate_manifest(manifest, trusted_scopes=trusted_scopes_map)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if not args.quiet:
            print(
                f"Evidence Manifest Validation: {len(manifest.entries)} entries, "
                f"Trust Level: {result.trust_level}"
            )
            print("-" * 70)

        for finding in result.findings:
            prefix = "ERROR" if finding.severity == "ERROR" else "WARN"
            eid = f" [{finding.evidence_id}]" if finding.evidence_id else ""
            print(f"[{prefix}]{eid} {finding.rule_id}: {finding.message}")

        if not args.quiet:
            print("-" * 70)
            status = "VALID" if result.is_valid else "INVALID"
            print(f"Result: {status} ({result.error_count} errors, {result.warning_count} warnings)")

    return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
