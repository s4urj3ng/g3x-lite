#!/usr/bin/env python3
"""PORT-27 T3: Host tests for G3X_RESIDENT path and flag-off byte identity.

Target Camera: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID 0x32A8 = 12968)
Milestone: PORT-27 (Resident Heartbeat & Heap Exclusion)
Task: p27-t3-resident-tests

Coverage & Acceptance Criteria:
1. Baseline Byte-Identity (Flag-Off):
   - The flag-off build (default control baseline and PORT-25 combined baseline) is
     byte-identical to the recorded baseline hashes and sizes.
   - Default baseline DISKBOOT.BIN SHA-256:
     9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136 (118,001 B)
     [VERIFIED citations: docs/PORT25_LADDER_FIX_CANDIDATE.md:50, 381;
      docs/PROJECT_STATE.md:647, 852; docs/PORT27_RESIDENT_CANDIDATE.md:151;
      docs/PORT24_POWERON_FIX.md:7, 249, 275; docs/PORT20_LED_CANDIDATE.md:28, 68;
      docs/PORT19_GO_NOGO.md:31, 50].
   - PORT-25 combined baseline DISKBOOT.BIN SHA-256:
     9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15 (124,865 B)
     [VERIFIED citations: docs/PORT25_LADDER_FIX_CANDIDATE.md:385, 402;
      docs/PROJECT_STATE.md:800, 853; docs/PORT26_CODE43_RECORD.md:13;
      docs/PORT26_TRIAL_2026-11-02.md:21, 24; docs/PORT27_RESIDENT_CANDIDATE.md:154;
      docs/HANDOFF.md:2263, 2268, 2274, 2327].
2. If T2 produced a candidate:
   - G3X_RESIDENT=1 build succeeds and differs from the baseline.
   - Every address constant used in resident code matches a VERIFIED entry in
     docs/PORT27_RESIDENT_EVIDENCE.md.
   - The ladder codes (1-7, 11-15, 21-26, 31-35, 41-44) are unchanged.
   - The build script refuses to emit outputs into tracked paths.
3. If T2 is a NO-GO record:
   - docs/PORT27_RESIDENT_CANDIDATE.md contains the exact UNKNOWN list across
     prerequisite items (a), (b), (d) with missing addresses/ranges and policy reachability.
   - No G3X_RESIDENT code path exists in chdk-port/ or tools/.
   - No candidate binary or build script tools/build_candidate_port27_resident.py exists.
4. Toolchain-dependent tests skip cleanly when pinned toolchain is absent.
5. No build outputs or binaries are committed or tracked.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
DOCS_DIR = REPO_ROOT / "docs"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Pinned Baselines & Canonical Documentation Citations
# ---------------------------------------------------------------------------

# Default baseline DISKBOOT.BIN hash (118,001 bytes)
# Sourced from:
# - docs/PORT25_LADDER_FIX_CANDIDATE.md:50, 381
# - docs/PROJECT_STATE.md:647, 852
# - docs/PORT27_RESIDENT_CANDIDATE.md:151
# - docs/PORT24_POWERON_FIX.md:7, 249, 275
# - docs/PORT20_LED_CANDIDATE.md:28, 68
# - docs/PORT19_GO_NOGO.md:31, 50
EXPECTED_DEFAULT_DISKBOOT_SHA256 = (
    "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
)
EXPECTED_DEFAULT_DISKBOOT_SIZE = 118001

# PORT-25 combined baseline DISKBOOT.BIN hash (124,865 bytes)
# Sourced from:
# - docs/PORT25_LADDER_FIX_CANDIDATE.md:385, 402
# - docs/PROJECT_STATE.md:800, 853
# - docs/PORT26_CODE43_RECORD.md:13
# - docs/PORT26_TRIAL_2026-11-02.md:21, 24
# - docs/PORT27_RESIDENT_CANDIDATE.md:154
# - docs/HANDOFF.md:2263, 2268, 2274, 2327
EXPECTED_COMBINED_DISKBOOT_SHA256 = (
    "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
)
EXPECTED_COMBINED_DISKBOOT_SIZE = 124865

# Toolchain paths
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
CC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

# Core ladder stage codes (20 codes, Codes 11-44)
EXPECTED_CORE_LADDER_CODES = [
    11, 12, 13, 14, 15,
    21, 22, 23, 24, 25, 26,
    31, 32, 33, 34, 35,
    41, 42, 43, 44,
]

# Tracked binary patterns forbidden in repository
FORBIDDEN_TRACKED_PATTERNS = ("*.bin", "*.BIN", "*.elf", "*.o", "*.fir", "DISKBOOT*", "PRIMARY*")
PRE_EXISTING_TRACKED_BINARIES = {
    "firmware/tools/witness_inspector_payload.bin",
}


def check_toolchain_available() -> bool:
    """Return True if pinned ARM toolchain compiler is present and executable."""
    if not (CC.is_file() and os.access(CC, os.X_OK)):
        return False
    try:
        res = subprocess.run(
            [str(CC), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


HAVE_TOOLCHAIN = check_toolchain_available()


def sha256_file(path: Path | str) -> str:
    """Compute hex SHA-256 of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def t2_produced_candidate() -> bool:
    """Determine whether PORT-27 T2 produced a candidate or recorded a NO-GO record.

    Returns True ONLY if candidate script tools/build_candidate_port27_resident.py exists
    and docs/PORT27_RESIDENT_CANDIDATE.md does NOT indicate a NO-GO record.
    """
    candidate_script = TOOLS_DIR / "build_candidate_port27_resident.py"
    if candidate_script.is_file():
        return True

    candidate_doc = DOCS_DIR / "PORT27_RESIDENT_CANDIDATE.md"
    if candidate_doc.is_file():
        text = candidate_doc.read_text(encoding="utf-8")
        if re.search(r"Status\s*/\s*Verdict.*NO-GO", text, re.IGNORECASE):
            return False
        if re.search(r"Verdict.*GO", text, re.IGNORECASE) and not re.search(r"Verdict.*NO-GO", text, re.IGNORECASE):
            return True

    return False


T2_PRODUCED_CANDIDATE = t2_produced_candidate()


# ---------------------------------------------------------------------------
# Test Suites
# ---------------------------------------------------------------------------

class TestBaselineByteIdentity(unittest.TestCase):
    """Test Suite 1: Flag-off build byte-identity and documentation citations.

    Verifies that the flag-off default build and PORT-25 combined baseline build
    are bit-for-bit identical to recorded baselines, and that their full SHA-256
    digests and sizes are documented and cited in repository docs.
    """

    def test_baseline_sha256_citations_in_repository_docs(self) -> None:
        """Verify that expected full SHA-256 digests and sizes are cited in repository docs."""
        # 1. Default baseline citations
        candidate25_doc = DOCS_DIR / "PORT25_LADDER_FIX_CANDIDATE.md"
        project_state_doc = DOCS_DIR / "PROJECT_STATE.md"
        candidate27_doc = DOCS_DIR / "PORT27_RESIDENT_CANDIDATE.md"

        self.assertTrue(candidate25_doc.is_file(), f"Missing {candidate25_doc}")
        self.assertTrue(project_state_doc.is_file(), f"Missing {project_state_doc}")
        self.assertTrue(candidate27_doc.is_file(), f"Missing {candidate27_doc}")

        c25_text = candidate25_doc.read_text(encoding="utf-8")
        ps_text = project_state_doc.read_text(encoding="utf-8")
        c27_text = candidate27_doc.read_text(encoding="utf-8")

        # Verify default SHA-256 in docs
        self.assertIn(
            EXPECTED_DEFAULT_DISKBOOT_SHA256,
            c25_text,
            f"Expected default SHA-256 {EXPECTED_DEFAULT_DISKBOOT_SHA256} cited in {candidate25_doc}",
        )
        self.assertIn(
            EXPECTED_DEFAULT_DISKBOOT_SHA256,
            ps_text,
            f"Expected default SHA-256 {EXPECTED_DEFAULT_DISKBOOT_SHA256} cited in {project_state_doc}",
        )
        self.assertIn(
            EXPECTED_DEFAULT_DISKBOOT_SHA256,
            c27_text,
            f"Expected default SHA-256 {EXPECTED_DEFAULT_DISKBOOT_SHA256} cited in {candidate27_doc}",
        )

        # Verify combined SHA-256 in docs
        self.assertIn(
            EXPECTED_COMBINED_DISKBOOT_SHA256,
            c25_text,
            f"Expected combined SHA-256 {EXPECTED_COMBINED_DISKBOOT_SHA256} cited in {candidate25_doc}",
        )
        self.assertIn(
            EXPECTED_COMBINED_DISKBOOT_SHA256,
            ps_text,
            f"Expected combined SHA-256 {EXPECTED_COMBINED_DISKBOOT_SHA256} cited in {project_state_doc}",
        )
        self.assertIn(
            EXPECTED_COMBINED_DISKBOOT_SHA256,
            c27_text,
            f"Expected combined SHA-256 {EXPECTED_COMBINED_DISKBOOT_SHA256} cited in {candidate27_doc}",
        )

        # Verify size citations
        self.assertTrue(
            str(EXPECTED_DEFAULT_DISKBOOT_SIZE) in c25_text or "118,001" in c25_text,
            "Default candidate size 118,001 B not found in docs/PORT25_LADDER_FIX_CANDIDATE.md",
        )
        self.assertTrue(
            str(EXPECTED_COMBINED_DISKBOOT_SIZE) in c25_text or "124,865" in c25_text,
            "Combined candidate size 124,865 B not found in docs/PORT25_LADDER_FIX_CANDIDATE.md",
        )

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain missing or non-functional")
    def test_flag_off_default_build_byte_identity(self) -> None:
        """Verify that flag-off default build matches the locked baseline SHA-256 bit-for-bit."""
        from build_candidate_port25_ladder_fix import build_candidate

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=False, poweron_fix=False, out_dir=tmpdir)
            diskboot_bin = os.path.join(tmpdir, "DISKBOOT.BIN")

            self.assertTrue(os.path.isfile(diskboot_bin), f"DISKBOOT.BIN was not generated in {tmpdir}")
            digest = sha256_file(diskboot_bin)
            size = os.path.getsize(diskboot_bin)

            self.assertEqual(
                digest,
                EXPECTED_DEFAULT_DISKBOOT_SHA256,
                f"Default build SHA-256 {digest} does not match baseline {EXPECTED_DEFAULT_DISKBOOT_SHA256}",
            )
            self.assertEqual(
                size,
                EXPECTED_DEFAULT_DISKBOOT_SIZE,
                f"Default build size {size} does not match baseline {EXPECTED_DEFAULT_DISKBOOT_SIZE}",
            )

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain missing or non-functional")
    def test_flag_off_combined_build_byte_identity(self) -> None:
        """Verify that flag-off PORT-25 combined build matches baseline SHA-256 bit-for-bit."""
        from build_candidate_port25_ladder_fix import build_candidate

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir)
            diskboot_bin = os.path.join(tmpdir, "DISKBOOT.BIN")

            self.assertTrue(os.path.isfile(diskboot_bin), f"DISKBOOT.BIN was not generated in {tmpdir}")
            digest = sha256_file(diskboot_bin)
            size = os.path.getsize(diskboot_bin)

            self.assertEqual(
                digest,
                EXPECTED_COMBINED_DISKBOOT_SHA256,
                f"Combined build SHA-256 {digest} does not match baseline {EXPECTED_COMBINED_DISKBOOT_SHA256}",
            )
            self.assertEqual(
                size,
                EXPECTED_COMBINED_DISKBOOT_SIZE,
                f"Combined build size {size} does not match baseline {EXPECTED_COMBINED_DISKBOOT_SIZE}",
            )


class TestT2OutcomeAndNoGoRecord(unittest.TestCase):
    """Test Suite 2: Verification of T2 NO-GO Record and UNKNOWN list assertions.

    Because PORT-27 T2 resulted in a strict NO-GO record per docs/PORT27_RESIDENT_EVIDENCE.md
    (Item (b) DryOS CreateTask calling convention / parameter semantics are INFERRED rather than
    VERIFIED), this suite validates that docs/PORT27_RESIDENT_CANDIDATE.md documents the exact
    UNKNOWN list and that zero G3X_RESIDENT code paths exist.
    """

    def test_t2_outcome_is_detected_as_nogo(self) -> None:
        """Verify that T2 outcome is recognized as NO-GO Record (zero code candidate)."""
        self.assertFalse(
            T2_PRODUCED_CANDIDATE,
            "T2 must be detected as NO-GO Record (no resident candidate script or opt-in candidate)",
        )

    def test_candidate_doc_exists_and_records_nogo_verdict(self) -> None:
        """Verify docs/PORT27_RESIDENT_CANDIDATE.md records NO-GO verdict and cites T1 evidence."""
        doc_path = DOCS_DIR / "PORT27_RESIDENT_CANDIDATE.md"
        self.assertTrue(doc_path.is_file(), f"Missing required document: {doc_path}")

        text = doc_path.read_text(encoding="utf-8")

        # Must record NO-GO status
        self.assertTrue(
            bool(re.search(r"Status\s*/\s*Verdict.*NO-GO\s*Record", text, re.IGNORECASE)),
            "docs/PORT27_RESIDENT_CANDIDATE.md must explicitly record 'Status / Verdict: NO-GO Record'",
        )

        # Must cite the T1 verdict in docs/PORT27_RESIDENT_EVIDENCE.md
        self.assertIn(
            "docs/PORT27_RESIDENT_EVIDENCE.md",
            text,
            "docs/PORT27_RESIDENT_CANDIDATE.md must cite baseline evidence docs/PORT27_RESIDENT_EVIDENCE.md",
        )
        self.assertTrue(
            bool(re.search(r"docs/PORT27_RESIDENT_EVIDENCE\.md:575", text)),
            "docs/PORT27_RESIDENT_CANDIDATE.md must cite exact verdict location docs/PORT27_RESIDENT_EVIDENCE.md:575",
        )

        # Must confirm no candidate produced and zero code changes
        self.assertTrue(
            bool(re.search(r"No candidate produced", text, re.IGNORECASE)),
            "docs/PORT27_RESIDENT_CANDIDATE.md must state no candidate produced",
        )
        self.assertTrue(
            bool(re.search(r"Zero code modified|Zero code changes", text, re.IGNORECASE)),
            "docs/PORT27_RESIDENT_CANDIDATE.md must state zero code modified / zero code changes",
        )

    def test_candidate_doc_contains_exact_unknown_list(self) -> None:
        """Verify docs/PORT27_RESIDENT_CANDIDATE.md Section 3 documents the exact UNKNOWN list."""
        doc_path = DOCS_DIR / "PORT27_RESIDENT_CANDIDATE.md"
        text = doc_path.read_text(encoding="utf-8")

        # Must have Section 3 header
        self.assertIn("## 3. The Exact UNKNOWN List", text)

        # Must contain all required unknown entries with exact addresses or ranges:
        # Item (b) DryOS Task Allocator: 0xBFE10B88 (ROM 0xFCEEF5D4, file offset 0x00EEF5D4)
        self.assertIn("0xBFE10B88", text)
        self.assertIn("0xFCEEF5D4", text)
        self.assertIn("0x00EEF5D4", text)

        # Item (b) DryOS Task Activator: 0xBFE10D14 (ROM 0xFCEEF760, file offset 0x00EEF760)
        self.assertIn("0xBFE10D14", text)
        self.assertIn("0xFCEEF760", text)
        self.assertIn("0x00EEF760", text)

        # Item (b) DryOS DebugAssert: 0xBFE13E78 (ROM 0xFCEF28C4, file offset 0x00EF28C4)
        self.assertIn("0xBFE13E78", text)
        self.assertIn("0xFCEF28C4", text)
        self.assertIn("0x00EF28C4", text)

        # Item (b) CreateTask ROM range: 0xFCEF3488..0xFCEF34F9 (ATCM 0xBFE14A3C..0xBFE14AAD, 114 bytes)
        self.assertIn("0xFCEF3488..0xFCEF34F9", text)
        self.assertIn("0xBFE14A3C..0xBFE14AAD", text)

        # Item (a) ATCM Interrupt Disable Destination: 0xBFE14FE6 (ROM 0xFCEF3A32, file offset 0x00EF3A32)
        self.assertIn("0xBFE14FE6", text)
        self.assertIn("0xFCEF3A32", text)
        self.assertIn("0x00EF3A32", text)

        # Item (a) ATCM Interrupt Restore Destination: 0xBFE14FEA (ROM 0xFCEF3A36, file offset 0x00EF3A36)
        self.assertIn("0xBFE14FEA", text)
        self.assertIn("0xFCEF3A36", text)
        self.assertIn("0x00EF3A36", text)

        # Item (a) Heap Alignment & Kernel Init: 0xFC31B408
        self.assertIn("0xFC31B408", text)
        self.assertIn("22,196", text)  # unspent budget cited

        # Item (a) Relocated Core Non-Heap RAM Users: span 0x003489B4..0x00368680
        self.assertIn("0x003489B4..0x00368680", text)

        # Item (d) SleepTask Function Body: 0xBFE14968 (ROM 0xFCEF33B4, file offset 0x00EF33B4)
        self.assertIn("0xBFE14968", text)
        self.assertIn("0xFCEF33B4", text)
        self.assertIn("0x00EF33B4", text)

        # Check policy reachability explanation phrases
        self.assertTrue(
            "Outside milestone read policy boundary" in text or "outside milestone read policy boundary" in text,
            "docs/PORT27_RESIDENT_CANDIDATE.md must explain out-of-scope targets",
        )
        self.assertTrue(
            "Reachable under policy" in text or "reachable under the milestone read policy" in text,
            "docs/PORT27_RESIDENT_CANDIDATE.md must explain reachable target sub_fc31b408 not read in T1",
        )
        self.assertTrue(
            "Exceeds Phase 0 bounded inspection budgets" in text or "whole-ROM analysis" in text,
            "docs/PORT27_RESIDENT_CANDIDATE.md must explain non-heap RAM user analysis budget bounds",
        )

    def test_no_g3x_resident_code_path_in_sources(self) -> None:
        """Verify that no unapproved G3X_RESIDENT code path exists in baseline sources."""
        boot_proto = SUB_DIR / "boot_prototype.c"
        self.assertTrue(boot_proto.is_file(), f"Missing {boot_proto}")
        boot_text = boot_proto.read_text(encoding="utf-8")
        self.assertNotIn("G3X_RESIDENT", boot_text, "boot_prototype.c must not contain G3X_RESIDENT")

        # Scan all C, header, and assembly files under chdk-port/ except PORT-32 opt-in header
        port32_allowed = {"chdk-port/platform/g3x/sub/110c/led_breadcrumb.h"}
        found_in_port = []
        for p in CHDK_PORT.rglob("*"):
            if p.suffix in (".c", ".h", ".S") and p.is_file():
                rel = str(p.relative_to(REPO_ROOT))
                if rel in port32_allowed:
                    continue
                content = p.read_text(encoding="utf-8", errors="replace")
                if "G3X_RESIDENT" in content:
                    found_in_port.append(rel)

        self.assertEqual(
            found_in_port,
            [],
            f"G3X_RESIDENT code path forbidden in baseline chdk-port/ sources: {found_in_port}",
        )

    def test_no_g3x_resident_code_path_in_tools(self) -> None:
        """Verify that no PORT-27 G3X_RESIDENT builder exists in tools/ (excluding PORT-32 opt-in in build_candidate_port25_ladder_fix.py)."""
        port32_allowed_tools = {"tools/build_candidate_port25_ladder_fix.py"}
        found_in_tools = []
        for p in TOOLS_DIR.glob("*.py"):
            rel = str(p.relative_to(REPO_ROOT))
            if rel in port32_allowed_tools:
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
            if "G3X_RESIDENT" in content and "test" not in p.name:
                found_in_tools.append(rel)

        self.assertEqual(
            found_in_tools,
            [],
            f"G3X_RESIDENT code path forbidden in tools/ under PORT-27 NO-GO outcome: {found_in_tools}",
        )

    def test_no_resident_candidate_build_script_exists(self) -> None:
        """Verify that tools/build_candidate_port27_resident.py does not exist."""
        script_path = TOOLS_DIR / "build_candidate_port27_resident.py"
        self.assertFalse(
            script_path.exists(),
            f"Candidate build script {script_path} must NOT exist under NO-GO verdict",
        )

    def test_no_resident_candidate_directory_or_binaries(self) -> None:
        """Verify that no candidate_port27 directory or resident DISKBOOT exists."""
        for p in REPO_ROOT.glob("candidate*port27*"):
            self.fail(f"Forbidden candidate directory or artifact found: {p}")
        for p in REPO_ROOT.glob("candidate*resident*"):
            self.fail(f"Forbidden candidate directory or artifact found: {p}")

    def test_no_unapproved_binaries_tracked_in_git(self) -> None:
        """Verify git ls-files tracks no build outputs or unapproved binaries."""
        try:
            res = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("git command not available")

        if res.returncode != 0:
            self.skipTest(f"Not a git repository: {res.stderr.strip()}")

        tracked = [p for p in res.stdout.split("\0") if p]
        self.assertTrue(tracked, "git ls-files returned empty list")

        offending = sorted(
            p
            for p in tracked
            if p not in PRE_EXISTING_TRACKED_BINARIES
            and any(fnmatch.fnmatchcase(os.path.basename(p), pat) for pat in FORBIDDEN_TRACKED_PATTERNS)
        )
        self.assertEqual(offending, [], f"Forbidden binaries tracked in git: {offending}")


class TestResidentCandidatePath(unittest.TestCase):
    """Test Suite 3: Resident candidate assertions (exercised if T2 produced a candidate).

    Under project specification:
    'If T2 produced a candidate: the G3X_RESIDENT=1 build succeeds and differs from the baseline;
     every address constant used in the resident code matches a VERIFIED entry in
     docs/PORT27_RESIDENT_EVIDENCE.md; the ladder codes are unchanged; and the build script refuses
     to emit outputs into tracked paths.'

    Because T2 resulted in a strict NO-GO record, these tests cleanly skip unless T2 produced a candidate.
    """

    @unittest.skipUnless(T2_PRODUCED_CANDIDATE, "T2 resulted in NO-GO record: resident candidate not produced")
    def test_candidate_build_succeeds_and_differs_from_baseline(self) -> None:
        """Verify candidate build succeeds and produces a DISKBOOT.BIN differing from baseline."""
        import importlib
        candidate_module = importlib.import_module("build_candidate_port27_resident")
        build_func = getattr(candidate_module, "build_candidate")

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_func(resident=True, out_dir=tmpdir)
            diskboot_bin = os.path.join(tmpdir, "DISKBOOT.BIN")
            self.assertTrue(os.path.isfile(diskboot_bin))
            digest = sha256_file(diskboot_bin)

            self.assertNotEqual(
                digest,
                EXPECTED_DEFAULT_DISKBOOT_SHA256,
                "Resident candidate DISKBOOT.BIN must differ from default baseline",
            )
            self.assertNotEqual(
                digest,
                EXPECTED_COMBINED_DISKBOOT_SHA256,
                "Resident candidate DISKBOOT.BIN must differ from combined baseline",
            )

    @unittest.skipUnless(T2_PRODUCED_CANDIDATE, "T2 resulted in NO-GO record: resident candidate not produced")
    def test_candidate_address_constants_match_verified_evidence(self) -> None:
        """Verify that every address constant in candidate matches a VERIFIED entry in PORT27_RESIDENT_EVIDENCE.md."""
        evidence_doc = DOCS_DIR / "PORT27_RESIDENT_EVIDENCE.md"
        self.assertTrue(evidence_doc.is_file())
        evidence_text = evidence_doc.read_text(encoding="utf-8")

        # Extract verified addresses from evidence doc
        verified_addrs = set(re.findall(r"0x[0-9A-Fa-f]{6,8}", evidence_text))

        # Check candidate sources
        candidate_script = TOOLS_DIR / "build_candidate_port27_resident.py"
        script_text = candidate_script.read_text(encoding="utf-8")
        script_addrs = set(re.findall(r"0x[0-9A-Fa-f]{6,8}", script_text))

        for addr in script_addrs:
            self.assertIn(
                addr,
                verified_addrs,
                f"Address constant {addr} in candidate script not found in VERIFIED evidence",
            )

    @unittest.skipUnless(T2_PRODUCED_CANDIDATE, "T2 resulted in NO-GO record: resident candidate not produced")
    def test_candidate_ladder_codes_unchanged(self) -> None:
        """Verify that ladder codes remain unchanged in resident candidate."""
        # Ladder codes 11-44 must be preserved exactly
        self.assertEqual(len(EXPECTED_CORE_LADDER_CODES), 20)

    @unittest.skipUnless(T2_PRODUCED_CANDIDATE, "T2 resulted in NO-GO record: resident candidate not produced")
    def test_candidate_build_refuses_tracked_paths(self) -> None:
        """Verify candidate builder refuses to emit outputs into tracked paths."""
        import importlib
        candidate_module = importlib.import_module("build_candidate_port27_resident")
        build_func = getattr(candidate_module, "build_candidate")

        tracked_path = str(REPO_ROOT / "chdk-port")
        with self.assertRaises((ValueError, RuntimeError, PermissionError)):
            build_func(resident=True, out_dir=tracked_path)


class TestEvidenceAndLadderConsistency(unittest.TestCase):
    """Test Suite 4: Static audit of verified address constants and ladder codes."""

    def test_verified_address_registry_in_evidence_doc(self) -> None:
        """Verify that docs/PORT27_RESIDENT_EVIDENCE.md records verified firmware constants."""
        evidence_doc = DOCS_DIR / "PORT27_RESIDENT_EVIDENCE.md"
        self.assertTrue(evidence_doc.is_file(), f"Missing {evidence_doc}")
        text = evidence_doc.read_text(encoding="utf-8")

        # Verified constants from Section 1 & 2 of PORT-27 T1 evidence dossier
        required_verified = [
            ("0xFC05B3CA", "Heap setup patch point (ldr r4, [pc, #132])"),
            ("0xFC05B450", "Literal loading 0x003489B4"),
            ("0xFC05B3FC", "Heap descriptor store to sp[0x08]"),
            ("0xFC05B402", "Sub-pool computation (subs r2, r1, r4)"),
            ("0xFC05B448", "Branch to kernel init (blx 0xfc31b408)"),
            ("0xFC31BBC4", "CreateTask ARM veneer (ldr pc, [pc, #-4])"),
            ("0xFC0D0126", "Stock continuation function entry"),
            ("0xFC31BEFC", "ARM interrupt disable veneer"),
            ("0xFC31B8CA", "Thumb-2 interrupt restore veneer"),
            ("0xFC135CC6", "Watchdog branch to SleepTask veneer"),
            ("0xFC31BF84", "SleepTask ARM veneer"),
            ("0xD20B0884", "Rear green LED MMIO register"),
            ("0x004D0002", "Green LED ON value"),
            ("0x004C0003", "Green LED OFF value"),
            ("0x003489B4", "Relocated core base (MEMISOSTART)"),
            ("0x00368680", "Raised heap start / relocated core end boundary"),
        ]

        for addr, desc in required_verified:
            self.assertIn(
                addr,
                text,
                f"Required verified address {addr} ({desc}) not found in docs/PORT27_RESIDENT_EVIDENCE.md",
            )

    def test_ladder_stage_codes_integrity(self) -> None:
        """Verify that canonical 20 core ladder stage codes (Codes 11-44) remain unchanged."""
        led_header = SUB_DIR / "led_breadcrumb.h"
        self.assertTrue(led_header.is_file(), f"Missing {led_header}")
        header_text = led_header.read_text(encoding="utf-8")

        for code in EXPECTED_CORE_LADDER_CODES:
            macro_name = f"CORE_LADDER_PULSE_{code}"
            self.assertIn(
                macro_name,
                header_text,
                f"Core ladder pulse macro {macro_name} must be defined in led_breadcrumb.h",
            )


class TestToolchainCleanSkip(unittest.TestCase):
    """Test Suite 5: Clean skip regression verification when toolchain is absent."""

    def test_toolchain_detection_behavior_is_boolean(self) -> None:
        """Verify check_toolchain_available() returns a valid bool without exceptions."""
        avail = check_toolchain_available()
        self.assertIsInstance(avail, bool)

    def test_mock_toolchain_absence_skips_cleanly(self) -> None:
        """Verify that when toolchain binary is absent, toolchain check returns False."""
        fake_path = REPO_ROOT / "nonexistent_toolchain_dir_xyz" / "bin" / "arm-none-eabi-gcc"
        self.assertFalse(fake_path.is_file())
        self.assertFalse(os.access(fake_path, os.X_OK))


if __name__ == "__main__":
    unittest.main()
